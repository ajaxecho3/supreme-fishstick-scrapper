"""
Configuration management for the web scraper.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Reddit API
    reddit_client_id: str = Field(..., env="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(..., env="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(..., env="REDDIT_USER_AGENT")
    
    # Twitter/X API
    twitter_bearer_token: Optional[str] = Field(None, env="TWITTER_BEARER_TOKEN")
    twitter_api_key: Optional[str] = Field(None, env="TWITTER_API_KEY")
    twitter_api_secret: Optional[str] = Field(None, env="TWITTER_API_SECRET")
    twitter_access_token: Optional[str] = Field(None, env="TWITTER_ACCESS_TOKEN")
    twitter_access_token_secret: Optional[str] = Field(None, env="TWITTER_ACCESS_TOKEN_SECRET")
    
    # Database
    database_url: str = Field("sqlite:///./webscraper.db", env="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    
    # Scraping configuration
    max_concurrent_requests: int = Field(5, env="MAX_CONCURRENT_REQUESTS")  # Lower for web scraping
    request_delay: float = Field(2.0, env="REQUEST_DELAY")  # Higher delay for respectful scraping
    retry_attempts: int = Field(3, env="RETRY_ATTEMPTS")
    rate_limit_requests: int = Field(30, env="RATE_LIMIT_REQUESTS")  # More conservative
    rate_limit_window: int = Field(60, env="RATE_LIMIT_WINDOW")
    
    # Scraping strategies
    default_scraping_strategy: str = Field("web", env="DEFAULT_SCRAPING_STRATEGY")
    enable_api_scrapers: bool = Field(False, env="ENABLE_API_SCRAPERS")
    enable_browser_scrapers: bool = Field(False, env="ENABLE_BROWSER_SCRAPERS")
    
    # Browser settings
    browser_headless: bool = Field(True, env="BROWSER_HEADLESS")
    browser_timeout: int = Field(30000, env="BROWSER_TIMEOUT")
    
    # Respectful scraping
    min_request_delay: float = Field(2.0, env="MIN_REQUEST_DELAY")
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
