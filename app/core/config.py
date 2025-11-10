"""
Core configuration settings
"""
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "Binary Options Trading System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str = "sqlite:///./trading_system.db"

    # MB Option API
    MBOPTION_API_URL: str = "https://trade.mboption.com"
    MBOPTION_WS_URL: str = "wss://trade.mboption.com/ws"

    # Telegram (Optional)
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # Trading Settings
    DEFAULT_TIMEFRAME: int = 5
    DEFAULT_SENSITIVITY: str = "moderate"
    MAX_CONCURRENT_PAIRS: int = 10

    # Access control
    ACCESS_TOKENS_FILE: str = "data/access_tokens.json"

    # IQ Option API - DADOS REAIS!
    IQOPTION_EMAIL: Optional[str] = None
    IQOPTION_PASSWORD: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
