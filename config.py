import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "Online Teaching & Learning Platform"
    APP_ENV: str = "development"
    PORT: int = 8000
    SECRET_KEY: str = "super-secret-key-change-this-in-production-min-32-chars-long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/online_teaching_db"
    FALLBACK_TO_SQLITE: bool = True
    SQLITE_URL: str = "sqlite:///./online_teaching.db"

    LIVEKIT_URL: str = "ws://localhost:7880"
    LIVEKIT_API_KEY: str = "devkey"
    LIVEKIT_API_SECRET: str = "secret"

    UPLOAD_DIR: str = "./uploads/books"
    MAX_UPLOAD_SIZE_MB: int = 50

    PERMANENT_CLASS_ID: str = "CLASS-PERMANENT-01"
    DEFAULT_CLASS_NAME: str = "Master Live Classroom"
    DEFAULT_CLASS_PASSWORD: str = "Learn123"
    MAX_STUDENTS_LIMIT: int = 20

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
