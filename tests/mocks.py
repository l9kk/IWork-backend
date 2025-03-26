from unittest.mock import AsyncMock


class AsyncMockSendEmail(AsyncMock):
    """Mock for email sending functionality"""

    async def __call__(self, *args, **kwargs):
        print("Mock email service called")
        return None


class MockEmailService:
    """Mock for the entire email service"""

    @staticmethod
    async def send_verification_email(*args, **kwargs):
        print("Mock verification email sent")
        return None

    @staticmethod
    async def send_password_reset_email(*args, **kwargs):
        print("Mock password reset email sent")
        return None

    @staticmethod
    async def send_review_approved_email(*args, **kwargs):
        print("Mock review approved email sent")
        return None

    @staticmethod
    async def send_review_rejected_email(*args, **kwargs):
        print("Mock review rejected email sent")
        return None