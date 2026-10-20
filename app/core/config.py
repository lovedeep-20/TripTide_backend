from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Travel Assistant API"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # LLM Configuration
    DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "groq")
    DEFAULT_GROQ_MODEL: str = os.getenv("DEFAULT_GROQ_MODEL", "openai/gpt-oss-20b")
    DEFAULT_OPENAI_MODEL: str = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4o-mini")
    
    # API Keys
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    
    # Session settings
    SESSION_EXPIRY_MINUTES: int = int(os.getenv("SESSION_EXPIRY_MINUTES", "30"))
    
    # Duplicate detection settings
    DUPLICATE_SIMILARITY_THRESHOLD: float = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.85"))
    DUPLICATE_CHECK_RECENT_MESSAGES: int = int(os.getenv("DUPLICATE_CHECK_RECENT_MESSAGES", "5"))
    
    # Google Chat webhook for error alerts (incoming webhook URL)
    GOOGLE_CHAT_WEBHOOK: Optional[str] = os.getenv("GOOGLE_CHAT_WEBHOOK")

    AMADEUS_API_KEY: str = os.getenv("AMADEUS_API_KEY")
    AMADEUS_API_SECRET: str = os.getenv("AMADEUS_API_SECRET")
    AMADEUS_BASE_URL: str = os.getenv("AMADEUS_BASE_URL")
    
    SABRE_CLIENT_ID: str = os.getenv("SABRE_CLIENT_ID")
    SABRE_CLIENT_SECRET: str = os.getenv("SABRE_CLIENT_SECRET")
    SABRE_ENV: str = "CERT"
    SABRE_BASE_URL: str = os.getenv("SABRE_BASE_URL")

    # PKFare settings
    PKFARE_BASE_URL: Optional[str] = os.getenv("PKFARE_BASE_URL")
    PKFARE_PARTNER_ID: Optional[str] = os.getenv("PKFARE_PARTNER_ID")
    PKFARE_PARTNER_KEY: Optional[str] = os.getenv("PKFARE_PARTNER_KEY")


    # MongoDB settings
    MONGO_URL: str = os.getenv("MONGO_URL")
    MONGO_DB: str = os.getenv("MONGO_DB")

    class Config:
        case_sensitive = True

settings = Settings()
