"""
Data models for the web scraper.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


class Platform(str, Enum):
    """Supported social media platforms."""
    REDDIT = "reddit"
    TWITTER = "twitter"


class PostType(str, Enum):
    """Types of posts that can be scraped."""
    POST = "post"
    COMMENT = "comment"
    TWEET = "tweet"
    REPLY = "reply"


class ScrapingStrategy(str, Enum):
    """Available scraping strategies."""
    API = "api"              # Official APIs (current)
    WEB = "web"              # Web scraping
    BROWSER = "browser"      # Browser automation  
    FEED = "feed"            # RSS/JSON feeds
    ALTERNATIVE = "alternative"  # Third-party APIs


class ScrapedPost(BaseModel):
    """Base model for scraped social media posts."""
    id: str = Field(..., description="Unique identifier for the post")
    platform: Platform = Field(..., description="Platform where the post was found")
    post_type: PostType = Field(..., description="Type of the post")
    author: str = Field(..., description="Username of the post author")
    content: str = Field(..., description="Text content of the post")
    url: str = Field(..., description="URL to the original post")
    created_at: datetime = Field(..., description="When the post was created")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="When the post was scraped")
    
    # Engagement metrics
    upvotes: Optional[int] = Field(None, description="Number of upvotes (Reddit)")
    downvotes: Optional[int] = Field(None, description="Number of downvotes (Reddit)")
    score: Optional[int] = Field(None, description="Post score (Reddit)")
    likes: Optional[int] = Field(None, description="Number of likes (Twitter)")
    retweets: Optional[int] = Field(None, description="Number of retweets (Twitter)")
    replies: Optional[int] = Field(None, description="Number of replies")
    
    # Additional metadata
    subreddit: Optional[str] = Field(None, description="Subreddit name (Reddit only)")
    hashtags: List[str] = Field(default_factory=list, description="Hashtags in the post")
    mentions: List[str] = Field(default_factory=list, description="User mentions in the post")
    media_urls: List[str] = Field(default_factory=list, description="URLs to media content")
    
    # Raw data for debugging
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw API response data")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RedditPost(ScrapedPost):
    """Reddit-specific post model."""
    platform: Literal[Platform.REDDIT] = Platform.REDDIT
    subreddit: str = Field(..., description="Subreddit where the post was found")
    flair: Optional[str] = Field(None, description="Post flair")
    is_self: bool = Field(False, description="Whether this is a self post")
    selftext: Optional[str] = Field(None, description="Self post text content")
    num_comments: int = Field(0, description="Number of comments")
    over_18: bool = Field(False, description="Whether the post is NSFW")
    spoiler: bool = Field(False, description="Whether the post is marked as spoiler")
    stickied: bool = Field(False, description="Whether the post is stickied")
    locked: bool = Field(False, description="Whether the post is locked")


class TwitterPost(ScrapedPost):
    """Twitter-specific post model."""
    platform: Literal[Platform.TWITTER] = Platform.TWITTER
    tweet_id: str = Field(..., description="Twitter tweet ID")
    in_reply_to_user_id: Optional[str] = Field(None, description="ID of user being replied to")
    in_reply_to_tweet_id: Optional[str] = Field(None, description="ID of tweet being replied to")
    is_retweet: bool = Field(False, description="Whether this is a retweet")
    retweeted_tweet_id: Optional[str] = Field(None, description="ID of original tweet if retweet")
    lang: Optional[str] = Field(None, description="Detected language of the tweet")
    source: Optional[str] = Field(None, description="Source application used to post")
    verified: bool = Field(False, description="Whether the author is verified")


class ScrapingJob(BaseModel):
    """Model for scraping job configuration."""
    job_id: str = Field(..., description="Unique job identifier")
    platform: Platform = Field(..., description="Platform to scrape")
    target: str = Field(..., description="Target to scrape (subreddit, username, hashtag, etc.)")
    max_posts: int = Field(100, description="Maximum number of posts to scrape")
    include_comments: bool = Field(False, description="Whether to scrape comments")
    keywords: List[str] = Field(default_factory=list, description="Keywords to filter by")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field("pending", description="Job status")
    
    
class ScrapingResult(BaseModel):
    """Model for scraping job results."""
    job_id: str = Field(..., description="Associated job ID")
    posts_scraped: int = Field(0, description="Number of posts scraped")
    comments_scraped: int = Field(0, description="Number of comments scraped")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")
    started_at: Optional[datetime] = Field(None, description="When scraping started")
    completed_at: Optional[datetime] = Field(None, description="When scraping completed")
    success: bool = Field(False, description="Whether the job completed successfully")
