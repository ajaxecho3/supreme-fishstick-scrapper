"""
Database models and setup using SQLAlchemy.
"""
from datetime import datetime
from typing import List, Dict, Any, Generator
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import uuid

from .config import settings

Base = declarative_base()


class ScrapedPostDB(Base):
    """Database model for scraped posts."""
    __tablename__ = "scraped_posts"
    
    id = Column(String, primary_key=True, index=True)
    platform = Column(String, nullable=False, index=True)
    post_type = Column(String, nullable=False)
    author = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    url = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, index=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Engagement metrics
    upvotes = Column(Integer)
    downvotes = Column(Integer)
    score = Column(Integer)
    likes = Column(Integer)
    retweets = Column(Integer)
    replies = Column(Integer)
    
    # Additional metadata
    subreddit = Column(String, index=True)
    hashtags = Column(JSON)
    mentions = Column(JSON)
    media_urls = Column(JSON)
    
    # Platform-specific fields
    flair = Column(String)
    is_self = Column(Boolean, default=False)
    selftext = Column(Text)
    num_comments = Column(Integer, default=0)
    over_18 = Column(Boolean, default=False)
    spoiler = Column(Boolean, default=False)
    stickied = Column(Boolean, default=False)
    locked = Column(Boolean, default=False)
    
    # Twitter-specific fields
    tweet_id = Column(String, index=True)
    in_reply_to_user_id = Column(String)
    in_reply_to_tweet_id = Column(String)
    is_retweet = Column(Boolean, default=False)
    retweeted_tweet_id = Column(String)
    lang = Column(String)
    source = Column(String)
    verified = Column(Boolean, default=False)
    
    # Raw data for debugging
    raw_data = Column(JSON)


class ScrapingJobDB(Base):
    """Database model for scraping jobs."""
    __tablename__ = "scraping_jobs"
    
    job_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    platform = Column(String, nullable=False, index=True)
    target = Column(String, nullable=False)
    max_posts = Column(Integer, default=100)
    include_comments = Column(Boolean, default=False)
    keywords = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String, default="pending", index=True)
    
    # Results
    posts_scraped = Column(Integer, default=0)
    comments_scraped = Column(Integer, default=0)
    errors = Column(JSON)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    success = Column(Boolean, default=False)


# Database engine and session setup
engine = create_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL debugging
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseManager:
    """Database operations manager."""
    
    def __init__(self):
        self.engine = engine
        
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
        
    def get_session(self) -> Session:
        """Get a new database session."""
        return SessionLocal()
        
    def save_post(self, post_data: dict) -> str:
        """Save a scraped post to the database."""
        with self.get_session() as db:
            post = ScrapedPostDB(**post_data)
            db.add(post)
            db.commit()
            db.refresh(post)
            return post.id
            
    def save_job(self, job_data: dict) -> str:
        """Save a scraping job to the database."""
        with self.get_session() as db:
            job = ScrapingJobDB(**job_data)
            db.add(job)
            db.commit()
            db.refresh(job)
            return job.job_id
            
    def update_job_status(self, job_id: str, status: str, **kwargs):
        """Update job status and other fields."""
        with self.get_session() as db:
            job = db.query(ScrapingJobDB).filter(ScrapingJobDB.job_id == job_id).first()
            if job:
                job.status = status
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                db.commit()
                
    def get_posts_by_platform(self, platform: str, limit: int = 100) -> List[ScrapedPostDB]:
        """Get posts by platform."""
        with self.get_session() as db:
            return db.query(ScrapedPostDB).filter(
                ScrapedPostDB.platform == platform
            ).order_by(ScrapedPostDB.scraped_at.desc()).limit(limit).all()
            
    def get_job_status(self, job_id: str) -> ScrapingJobDB:
        """Get job status by ID."""
        with self.get_session() as db:
            return db.query(ScrapingJobDB).filter(ScrapingJobDB.job_id == job_id).first()


# Global database manager instance
db_manager = DatabaseManager()
