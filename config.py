import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

class Settings:
    """FastAPI Settings"""
    DATABASE_URL: str = os.getenv('DATABASE_URL')
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    DEBUG: bool = os.getenv('DEBUG', 'True').lower() == 'true'
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'development')

settings = Settings()

