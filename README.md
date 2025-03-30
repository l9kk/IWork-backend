# IWork Backend

A comprehensive backend for the IWork platform - connecting professionals with company insights through reviews and salary data.

## 📋 Overview

IWork is a platform that allows professionals to share and access company reviews, salary information, and workplace insights. This repository contains the backend API built with FastAPI, using Neon PostgreSQL as a serverless database and Upstash Redis for caching.

## ✨ Features

- 🔐 Authentication and authorization with JWT tokens and refresh token rotation
- 👥 User management and profile settings
- 🏢 Company information and statistics
- ⭐ Review submission, moderation, and display
- 💰 Salary data submission and analytics
- 🔍 Advanced search capabilities with filtering
- 🤖 AI-powered content moderation
- 📊 Admin dashboard with moderation tools
- 🚀 High performance with serverless PostgreSQL and Redis
- 📧 Email notifications for account verification and review status
- 📄 File attachment support for reviews
- 🔄 Scheduled tasks for database maintenance

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.9+)
- **Database**: [Neon PostgreSQL](https://neon.tech/) (Serverless PostgreSQL)
- **Caching**: [Upstash Redis](https://upstash.com/) (Serverless Redis)
- **ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) 2.0
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Authentication**: JWT with [python-jose](https://github.com/mpdavis/python-jose)
- **Password Hashing**: [Passlib](https://passlib.readthedocs.io/) with Bcrypt
- **Dependency Management**: [Poetry](https://python-poetry.org/)
- **Email Templates**: Jinja2 templates
- **File Storage**: AWS S3 with CloudFront CDN
- **AI Services**: Google Gemini AI for content moderation

## 🔧 Installation and Setup

### Prerequisites

- Python 3.9 or higher
- Poetry

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/iwork-backend.git
   cd iwork-backend
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Create a `.env` file in the root directory (see [Configuration](#%EF%B8%8F-configuration) section)

4. Run database migrations:
   ```bash
   alembic upgrade head
   ```

5. Start the application:
   ```bash
   # Development mode with auto-reload
   uvicorn app.main:app --reload

   # Production mode
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## ⚙️ Configuration

Create a `.env` file in the root directory with the following variables:

```
# Application settings
PROJECT_NAME="IWork API"
SECRET_KEY="your-secure-secret-key-change-this-in-production"
ACCESS_TOKEN_EXPIRE_MINUTES=60
ENVIRONMENT="development"  # Options: development, staging, production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Neon PostgreSQL settings
DATABASE_URL=postgresql://neondb_owner:your-password@your-instance-id.eu-central-1.aws.neon.tech/neondb?sslmode=require

# Upstash Redis settings
REDIS_URL=https://your-instance.upstash.io
REDIS_TOKEN=your-token

# AWS S3 settings
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_S3_BUCKET_NAME=your-bucket-name
AWS_CLOUDFRONT_URL=https://your-cloudfront-url

# Email settings
EMAIL_HOST=smtp.your-email-provider.com
EMAIL_PORT=587
EMAIL_USERNAME=your-email-username
EMAIL_PASSWORD=your-email-password
EMAIL_FROM=your-email@example.com
```

## 📂 Project Structure

```
iwork-backend/
├── alembic/                # Database migrations
├── app/
│   ├── api/                # API endpoints
│   ├── core/               # Core functionality
│   │   ├── config.py       # Application configuration
│   │   ├── dependencies.py # FastAPI dependencies
│   │   └── security.py     # Authentication & security
│   ├── crud/               # Database CRUD operations
│   ├── db/                 # Database configuration
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic services
│   │   ├── email.py        # Email service implementation
│   │   ├── file_storage.py # File storage service
│   │   └── token_cleanup.py # Scheduled tasks for token cleanup
│   ├── templates/          # Jinja2 email templates
│   ├── utils/              # Utility functions
│   │   └── redis_cache.py  # Redis client implementation
│   └── main.py             # FastAPI application
├── .env                    # Environment variables
├── alembic.ini             # Alembic configuration
└── pyproject.toml          # Poetry configuration
```

## 🚀 Development

### Creating Database Migrations

When you make changes to database models:

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migrations
alembic downgrade -1
```

## 📱 API Documentation

Once the application is running, you can explore the API documentation:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/health

### Main API Endpoints

- 🔐 **Authentication**: `/api/auth/login`, `/api/auth/register` 
- 👥 **Users**: `/api/users/me`, `/api/users/me/settings`
- 🏢 **Companies**: `/api/companies`
- ⭐ **Reviews**: `/api/reviews`
- 💰 **Salaries**: `/api/salaries`
- 🔍 **Search**: `/api/search/companies`, `/api/search/reviews`, `/api/search/salaries`
- 👮 **Admin**: `/api/admin/dashboard`, `/api/admin/reviews/pending`

## 💾 Database Models

- **User**: User accounts and authentication
- **Company**: Company information
- **Review**: Company reviews with moderation
- **Salary**: Anonymized salary data
- **AccountSettings**: User preferences and settings
- **Token**: Refresh token management

## 🔍 Cache Strategy

The application uses Upstash Redis for caching:

- Company details and statistics (1 hour TTL)
- Review listings (1 hour TTL)
- Search results (15 minutes TTL)
- Salary statistics (3 hours TTL)
- Admin dashboard data (10 minutes TTL)

Cache is automatically invalidated when relevant data is updated.

## 🌍 Deployment

### Production Considerations

1. Set `ENVIRONMENT=production` and `DEBUG=False` in your `.env` file
2. Use a production ASGI server like Gunicorn with Uvicorn workers:
   ```bash
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
   ```
3. Generate a secure random `SECRET_KEY` for production
4. Set appropriate `ALLOWED_HOSTS` for your domain

---
