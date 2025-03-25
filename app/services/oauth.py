import json
import logging
from typing import Dict, Any, Tuple

import httpx
from fastapi import HTTPException, status, Request
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

from app.core.config import settings
from app.models.user import User
from app import crud
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Configure OAuth client
config = Config(environ={
    "GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET
})

oauth = OAuth(config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


async def get_google_oauth_url(request: Request) -> str:
    """
    Generate the URL for Google OAuth login
    """
    try:
        redirect_uri = settings.OAUTH_REDIRECT_URL
        logger.debug(f"Starting OAuth flow with redirect URI: {redirect_uri}")

        # With Authlib, this returns a RedirectResponse
        return await oauth.google.authorize_redirect(request, redirect_uri)
    except Exception as e:
        logger.error(f"Error generating OAuth URL: {e}")
        raise


async def exchange_google_code(code: str) -> Dict[str, Any]:
    try:
        token_params = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.OAUTH_REDIRECT_URL,
            "grant_type": "authorization_code"
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(settings.GOOGLE_TOKEN_URL, data=token_params)
            token_data = token_response.json()

            if "error" in token_data:
                logger.error(f"Error exchanging code: {token_data}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to exchange code: {token_data.get('error_description', token_data.get('error'))}"
                )

            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            user_response = await client.get(settings.GOOGLE_USERINFO_URL, headers=headers)
            user_info = user_response.json()

            return user_info

    except httpx.RequestError as e:
        logger.error(f"Error in Google OAuth exchange: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error communicating with Google OAuth service"
        )


async def process_google_user(
        db: Session, user_info: Dict[str, Any]
) -> Tuple[User, bool]:
    oauth_id = user_info.get("sub")
    email = user_info.get("email")

    if not oauth_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incomplete user information from Google"
        )

    user = crud.user.get_by_oauth_id(db, provider="google", oauth_id=oauth_id)
    if user:
        return user, False

    user = crud.user.get_by_email(db, email=email)
    if user:
        user = crud.user.update_oauth_info(
            db,
            user_id=user.id,
            provider="google",
            oauth_id=oauth_id,
            oauth_data=json.dumps(user_info)
        )
        return user, False

    first_name = user_info.get("given_name", "")
    last_name = user_info.get("family_name", "")
    profile_image = user_info.get("picture")

    user = crud.user.create_oauth_user(
        db,
        email=email,
        first_name=first_name,
        last_name=last_name,
        profile_image=profile_image,
        provider="google",
        oauth_id=oauth_id,
        oauth_data=json.dumps(user_info),
        is_verified=user_info.get("email_verified", False)
    )

    from app.schemas.settings import AccountSettingsUpdate
    crud.account_settings.create_or_update(
        db,
        user_id=user.id,
        obj_in=AccountSettingsUpdate()
    )

    return user, True