"""
Web Scraper Package
A performant, scalable, and reliable web scraper for Reddit and Twitter/X.
"""

__version__ = "1.0.0"
__author__ = "Web Scraper Team"

from .config import settings
from .models import Platform, ScrapedPost, RedditPost, TwitterPost
from .scrapers.manager import scraper_manager

__all__ = [
    "settings",
    "Platform", 
    "ScrapedPost",
    "RedditPost", 
    "TwitterPost",
    "scraper_manager"
]
