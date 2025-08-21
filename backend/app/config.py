from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    robinhood_api_key: Optional[str] = None
    robinhood_private_key: Optional[str] = None
    robinhood_api_url: str = "https://api.robinhood.com"
    
    trading_budget: float = 100.0
    max_loss_per_trade: float = 0.02  # 2% max loss per trade
    daily_loss_limit: float = 0.10    # 10% daily loss limit
    paper_trading_mode: bool = False
    
    coingecko_api_key: Optional[str] = None
    newsdata_api_key: Optional[str] = None
    
    database_url: str = "sqlite:///./trading_bot.db"
    
    secret_key: str = "dev-secret-key-change-in-production"
    
    class Config:
        env_file = ".env"

settings = Settings()
