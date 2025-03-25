import time
import uuid
from fastapi import FastAPI, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import asyncio

from starlette.middleware.sessions import SessionMiddleware

from app.services.token_cleanup import start_token_cleanup_scheduler

from app.api import auth, users, companies, reviews, salaries, search, admin, files, oauth
from app.core.config import settings
from app.db.base import get_db
from app.utils.redis_cache import get_redis, RedisClient

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check(
        db=Depends(get_db),
        redis: RedisClient = Depends(get_redis)
):
    """
    Health check endpoint to verify database and Redis connections
    """
    try:
        db.execute(text("SELECT 1")).fetchall()
        db_status = "ok"
    except SQLAlchemyError as e:
        db_status = f"error: {str(e)}"

    # Check Redis connection
    redis_status = "ok"
    try:
        test_key = f"health_check:{uuid.uuid4()}"
        await redis.set(test_key, "test", expire=10)
        test_value = await redis.get(test_key)
        if test_value != "test":
            redis_status = "error: unexpected value returned"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    status_code = status.HTTP_200_OK
    if "error" in db_status or "error" in redis_status:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if status_code == status.HTTP_200_OK else "unhealthy",
            "timestamp": time.time(),
            "services": {
                "database": db_status,
                "redis": redis_status
            }
        }
    )

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
app.include_router(auth.router, tags=["auth"])
app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
app.include_router(users.router, prefix= "/users", tags=["users"])
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
app.include_router(salaries.router, prefix="/salaries", tags=["salaries"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(files.router, prefix="/files", tags=["files"])

@app.on_event("startup")
async def start_scheduler():
    # Start the token cleanup task
    asyncio.create_task(start_token_cleanup_scheduler())

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)