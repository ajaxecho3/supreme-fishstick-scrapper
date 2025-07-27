"""
Twitter/X scraper implementation.
"""
import asyncio
import tweepy
from typing import AsyncGenerator, Dict, List, Any, Optional
from datetime import datetime
from loguru import logger
import re

from ..models import TwitterPost, Platform, PostType
from ..config import settings
from .base import BaseScraper


class TwitterScraper(BaseScraper):
    """Scraper for Twitter/X posts and replies."""
    
    def __init__(self):
        super().__init__(Platform.TWITTER)
        self.client = None
        self._setup_twitter_client()
        
    def _setup_twitter_client(self):
        """Initialize Twitter API client."""
        try:
            if settings.twitter_bearer_token:
                # Twitter API v2 client with Bearer Token (App-only auth)
                self.client = tweepy.Client(bearer_token=settings.twitter_bearer_token)
                logger.info("Twitter client initialized with Bearer Token")
            elif all([
                settings.twitter_api_key,
                settings.twitter_api_secret,
                settings.twitter_access_token,
                settings.twitter_access_token_secret
            ]):
                # Twitter API v2 client with OAuth 1.0a (User context)
                self.client = tweepy.Client(
                    consumer_key=settings.twitter_api_key,
                    consumer_secret=settings.twitter_api_secret,
                    access_token=settings.twitter_access_token,
                    access_token_secret=settings.twitter_access_token_secret,
                    wait_on_rate_limit=True
                )
                logger.info("Twitter client initialized with OAuth 1.0a")
            else:
                raise ValueError("No valid Twitter API credentials provided")
                
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {str(e)}")
            raise
            
    async def scrape_posts(
        self, 
        target: str, 
        max_posts: int = 100, 
        **kwargs
    ) -> AsyncGenerator[TwitterPost, None]:
        """
        Scrape posts from Twitter.
        
        Args:
            target: Can be a username (without @), hashtag (with #), or search query
            max_posts: Maximum number of tweets to scrape
        """
        if not self.client:
            raise ValueError("Twitter client not initialized")
            
        try:
            if target.startswith('@'):
                # User timeline
                username = target[1:]  # Remove @ symbol
                async for tweet in self._scrape_user_timeline(username, max_posts):
                    yield tweet
            elif target.startswith('#'):
                # Hashtag search
                async for tweet in self._search_tweets(target, max_posts):
                    yield tweet
            else:
                # General search query
                async for tweet in self._search_tweets(target, max_posts):
                    yield tweet
                    
        except Exception as e:
            logger.error(f"Error scraping Twitter target '{target}': {str(e)}")
            raise
            
    async def _scrape_user_timeline(
        self, 
        username: str, 
        max_posts: int = 100
    ) -> AsyncGenerator[TwitterPost, None]:
        """Scrape tweets from a user's timeline."""
        try:
            logger.info(f"Scraping timeline for @{username} (max: {max_posts})")
            
            # Get user ID first
            user = self.client.get_user(username=username)
            if not user.data:
                logger.error(f"User @{username} not found")
                return
                
            user_id = user.data.id
            
            # Get user's tweets
            tweets = tweepy.Paginator(
                self.client.get_users_tweets,
                id=user_id,
                tweet_fields=['created_at', 'author_id', 'public_metrics', 'context_annotations', 
                             'entities', 'in_reply_to_user_id', 'lang', 'source'],
                user_fields=['verified', 'public_metrics'],
                expansions=['author_id'],
                max_results=min(100, max_posts),
                limit=max(1, max_posts // 100)
            ).flatten(limit=max_posts)
            
            tweets_yielded = 0
            
            for tweet in tweets:
                if tweets_yielded >= max_posts:
                    break
                    
                try:
                    twitter_post = await self._convert_tweet_to_post(tweet, user.data)
                    yield twitter_post
                    tweets_yielded += 1
                    
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing tweet {tweet.id}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping user timeline @{username}: {str(e)}")
            raise
            
    async def _search_tweets(
        self, 
        query: str, 
        max_posts: int = 100
    ) -> AsyncGenerator[TwitterPost, None]:
        """Search for tweets matching a query."""
        try:
            logger.info(f"Searching Twitter for '{query}' (max: {max_posts})")
            
            tweets = tweepy.Paginator(
                self.client.search_recent_tweets,
                query=query,
                tweet_fields=['created_at', 'author_id', 'public_metrics', 'context_annotations',
                             'entities', 'in_reply_to_user_id', 'lang', 'source'],
                user_fields=['verified', 'public_metrics'],
                expansions=['author_id'],
                max_results=min(100, max_posts),
                limit=max(1, max_posts // 100)
            ).flatten(limit=max_posts)
            
            tweets_yielded = 0
            
            for tweet in tweets:
                if tweets_yielded >= max_posts:
                    break
                    
                try:
                    # Get user info for this tweet
                    user_info = None
                    if hasattr(tweet, 'includes') and 'users' in tweet.includes:
                        user_info = next(
                            (u for u in tweet.includes['users'] if u.id == tweet.author_id), 
                            None
                        )
                        
                    twitter_post = await self._convert_tweet_to_post(tweet, user_info)
                    yield twitter_post
                    tweets_yielded += 1
                    
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing search tweet {tweet.id}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error searching Twitter for '{query}': {str(e)}")
            raise
            
    async def scrape_comments(
        self, 
        post_id: str, 
        max_comments: int = 100
    ) -> AsyncGenerator[TwitterPost, None]:
        """Scrape replies to a specific tweet."""
        if not self.client:
            raise ValueError("Twitter client not initialized")
            
        try:
            logger.info(f"Scraping replies for tweet {post_id} (max: {max_comments})")
            
            # Search for replies using Twitter search
            query = f"conversation_id:{post_id} is:reply"
            
            tweets = tweepy.Paginator(
                self.client.search_recent_tweets,
                query=query,
                tweet_fields=['created_at', 'author_id', 'public_metrics', 'context_annotations',
                             'entities', 'in_reply_to_user_id', 'lang', 'source', 'conversation_id'],
                user_fields=['verified', 'public_metrics'],
                expansions=['author_id', 'in_reply_to_user_id'],
                max_results=min(100, max_comments),
                limit=max(1, max_comments // 100)
            ).flatten(limit=max_comments)
            
            replies_yielded = 0
            
            for tweet in tweets:
                if replies_yielded >= max_comments:
                    break
                    
                try:
                    # Get user info for this tweet
                    user_info = None
                    if hasattr(tweet, 'includes') and 'users' in tweet.includes:
                        user_info = next(
                            (u for u in tweet.includes['users'] if u.id == tweet.author_id), 
                            None
                        )
                        
                    twitter_post = await self._convert_tweet_to_post(tweet, user_info, is_reply=True)
                    yield twitter_post
                    replies_yielded += 1
                    
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing reply {tweet.id}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping replies for tweet {post_id}: {str(e)}")
            raise
            
    async def _convert_tweet_to_post(
        self, 
        tweet, 
        user_info=None, 
        is_reply: bool = False
    ) -> TwitterPost:
        """Convert Twitter tweet to TwitterPost model."""
        
        # Extract hashtags and mentions
        hashtags = []
        mentions = []
        media_urls = []
        
        if hasattr(tweet, 'entities'):
            if 'hashtags' in tweet.entities:
                hashtags = [f"#{tag['tag']}" for tag in tweet.entities['hashtags']]
            if 'mentions' in tweet.entities:
                mentions = [f"@{mention['username']}" for mention in tweet.entities['mentions']]
            if 'urls' in tweet.entities:
                media_urls = [url['expanded_url'] for url in tweet.entities['urls'] if url.get('expanded_url')]
                
        # Get engagement metrics
        public_metrics = getattr(tweet, 'public_metrics', {})
        
        return TwitterPost(
            id=str(tweet.id),
            tweet_id=str(tweet.id),
            post_type=PostType.REPLY if is_reply else PostType.TWEET,
            author=user_info.username if user_info else f"user_{tweet.author_id}",
            content=tweet.text,
            url=f"https://twitter.com/user/status/{tweet.id}",
            created_at=tweet.created_at,
            
            # Engagement metrics
            likes=public_metrics.get('like_count', 0),
            retweets=public_metrics.get('retweet_count', 0),
            replies=public_metrics.get('reply_count', 0),
            
            # Twitter-specific fields
            in_reply_to_user_id=getattr(tweet, 'in_reply_to_user_id', None),
            in_reply_to_tweet_id=None,  # Not available in API v2
            is_retweet=tweet.text.startswith('RT @'),
            lang=getattr(tweet, 'lang', None),
            source=getattr(tweet, 'source', None),
            verified=user_info.verified if user_info else False,
            
            # Additional metadata
            hashtags=hashtags,
            mentions=mentions,
            media_urls=media_urls,
            
            # Raw data
            raw_data={
                'conversation_id': getattr(tweet, 'conversation_id', None),
                'context_annotations': getattr(tweet, 'context_annotations', []),
                'public_metrics': public_metrics,
                'user_metrics': user_info.public_metrics if user_info else {},
            }
        )
        
    async def get_trending_topics(self, woeid: int = 1) -> List[Dict[str, Any]]:
        """
        Get trending topics for a location.
        
        Args:
            woeid: Where On Earth ID (1 = Worldwide)
        """
        if not self.client:
            raise ValueError("Twitter client not initialized")
            
        try:
            # Note: Trending topics require API v1.1, which is not available in tweepy.Client
            # This would require using the legacy tweepy.API
            logger.warning("Trending topics not implemented - requires Twitter API v1.1")
            return []
            
        except Exception as e:
            logger.error(f"Error getting trending topics: {str(e)}")
            raise
            
    async def search_tweets_by_hashtag(
        self, 
        hashtag: str, 
        max_posts: int = 100
    ) -> AsyncGenerator[TwitterPost, None]:
        """Search for tweets by hashtag."""
        if not hashtag.startswith('#'):
            hashtag = f"#{hashtag}"
            
        async for tweet in self._search_tweets(hashtag, max_posts):
            yield tweet
            
    async def get_user_info(self, username: str) -> Dict[str, Any]:
        """Get information about a Twitter user."""
        if not self.client:
            raise ValueError("Twitter client not initialized")
            
        try:
            user = self.client.get_user(
                username=username,
                user_fields=['created_at', 'description', 'location', 'public_metrics', 'verified']
            )
            
            if user.data:
                return {
                    'id': user.data.id,
                    'username': user.data.username,
                    'name': user.data.name,
                    'description': user.data.description,
                    'location': user.data.location,
                    'created_at': user.data.created_at,
                    'verified': user.data.verified,
                    'public_metrics': user.data.public_metrics,
                }
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Error getting user info for @{username}: {str(e)}")
            raise
