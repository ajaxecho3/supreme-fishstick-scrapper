"""
Reddit scraper implementation.
"""
import asyncio
import praw
from typing import AsyncGenerator, Dict, List, Any, Optional
from datetime import datetime
from loguru import logger
import re

from ..models import RedditPost, Platform, PostType, ScrapingStrategy
from ..config import settings
from .base import BaseScraper


class RedditScraper(BaseScraper):
    """Scraper for Reddit posts and comments using official API."""
    
    def __init__(self):
        super().__init__(Platform.REDDIT, ScrapingStrategy.API)
        self.reddit = None
        self._setup_reddit_client()
        
    def _setup_reddit_client(self):
        """Initialize Reddit API client."""
        try:
            self.reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
                ratelimit_seconds=1  # Built-in rate limiting
            )
            logger.info("Reddit client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {str(e)}")
            raise
            
    async def scrape_posts(
        self, 
        target: str, 
        max_posts: int = 100, 
        sort: str = "hot",
        time_filter: str = "all"
    ) -> AsyncGenerator[RedditPost, None]:
        """
        Scrape posts from a subreddit.
        
        Args:
            target: Subreddit name (without r/)
            max_posts: Maximum number of posts to scrape
            sort: Sort method (hot, new, top, rising)
            time_filter: Time filter for 'top' sort (hour, day, week, month, year, all)
        """
        if not self.reddit:
            raise ValueError("Reddit client not initialized")
            
        try:
            subreddit = self.reddit.subreddit(target)
            logger.info(f"Scraping r/{target} - {sort} posts (max: {max_posts})")
            
            # Get posts based on sort method
            if sort == "hot":
                submissions = subreddit.hot(limit=max_posts)
            elif sort == "new":
                submissions = subreddit.new(limit=max_posts)
            elif sort == "top":
                submissions = subreddit.top(time_filter=time_filter, limit=max_posts)
            elif sort == "rising":
                submissions = subreddit.rising(limit=max_posts)
            else:
                submissions = subreddit.hot(limit=max_posts)
                
            posts_yielded = 0
            
            for submission in submissions:
                if posts_yielded >= max_posts:
                    break
                    
                try:
                    post = await self._convert_submission_to_post(submission)
                    yield post
                    posts_yielded += 1
                    
                    # Add small delay to avoid overwhelming
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing submission {submission.id}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping subreddit r/{target}: {str(e)}")
            raise
            
    async def scrape_comments(
        self, 
        post_id: str, 
        max_comments: int = 100
    ) -> AsyncGenerator[RedditPost, None]:
        """Scrape comments for a specific Reddit post."""
        if not self.reddit:
            raise ValueError("Reddit client not initialized")
            
        try:
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)  # Remove "more comments" objects
            
            logger.info(f"Scraping comments for post {post_id} (max: {max_comments})")
            
            comments_yielded = 0
            
            for comment in submission.comments.list():
                if comments_yielded >= max_comments:
                    break
                    
                try:
                    if hasattr(comment, 'body') and comment.body != '[deleted]':
                        comment_post = await self._convert_comment_to_post(comment, submission)
                        yield comment_post
                        comments_yielded += 1
                        
                except Exception as e:
                    logger.error(f"Error processing comment {comment.id}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping comments for post {post_id}: {str(e)}")
            raise
            
    async def _convert_submission_to_post(self, submission) -> RedditPost:
        """Convert Reddit submission to RedditPost model."""
        # Extract hashtags and mentions
        hashtags = self._extract_hashtags(submission.title + " " + (submission.selftext or ""))
        mentions = self._extract_mentions(submission.title + " " + (submission.selftext or ""))
        
        # Extract media URLs
        media_urls = []
        if hasattr(submission, 'url') and submission.url:
            if any(ext in submission.url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                media_urls.append(submission.url)
                
        return RedditPost(
            id=submission.id,
            post_type=PostType.POST,
            author=str(submission.author) if submission.author else "[deleted]",
            content=submission.title,
            url=f"https://reddit.com{submission.permalink}",
            created_at=datetime.fromtimestamp(submission.created_utc),
            
            # Engagement metrics
            upvotes=submission.ups if hasattr(submission, 'ups') else 0,
            downvotes=submission.downs if hasattr(submission, 'downs') else 0,
            score=submission.score,
            replies=submission.num_comments,
            
            # Reddit-specific fields
            subreddit=submission.subreddit.display_name,
            flair=submission.link_flair_text,
            is_self=submission.is_self,
            selftext=submission.selftext if submission.selftext else None,
            num_comments=submission.num_comments,
            over_18=submission.over_18,
            spoiler=submission.spoiler,
            stickied=submission.stickied,
            locked=submission.locked,
            
            # Additional metadata
            hashtags=hashtags,
            mentions=mentions,
            media_urls=media_urls,
            
            # Raw data
            raw_data={
                'title': submission.title,
                'selftext': submission.selftext,
                'domain': submission.domain,
                'url': submission.url,
                'thumbnail': getattr(submission, 'thumbnail', None),
                'gilded': getattr(submission, 'gilded', 0),
                'distinguished': getattr(submission, 'distinguished', None),
            }
        )
        
    async def _convert_comment_to_post(self, comment, submission) -> RedditPost:
        """Convert Reddit comment to RedditPost model."""
        # Extract hashtags and mentions
        hashtags = self._extract_hashtags(comment.body)
        mentions = self._extract_mentions(comment.body)
        
        return RedditPost(
            id=comment.id,
            post_type=PostType.COMMENT,
            author=str(comment.author) if comment.author else "[deleted]",
            content=comment.body,
            url=f"https://reddit.com{comment.permalink}",
            created_at=datetime.fromtimestamp(comment.created_utc),
            
            # Engagement metrics
            upvotes=comment.ups if hasattr(comment, 'ups') else 0,
            downvotes=comment.downs if hasattr(comment, 'downs') else 0,
            score=comment.score,
            replies=len(comment.replies) if hasattr(comment, 'replies') else 0,
            
            # Reddit-specific fields
            subreddit=submission.subreddit.display_name,
            is_self=False,
            num_comments=0,
            over_18=submission.over_18,
            
            # Additional metadata
            hashtags=hashtags,
            mentions=mentions,
            media_urls=[],
            
            # Raw data
            raw_data={
                'parent_id': comment.parent_id,
                'link_id': comment.link_id,
                'depth': getattr(comment, 'depth', 0),
                'gilded': getattr(comment, 'gilded', 0),
                'distinguished': getattr(comment, 'distinguished', None),
            }
        )
        
    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text."""
        if not text:
            return []
        return re.findall(r'#\w+', text)
        
    def _extract_mentions(self, text: str) -> List[str]:
        """Extract user mentions from text."""
        if not text:
            return []
        return re.findall(r'u/\w+', text)
        
    async def search_posts(
        self, 
        query: str, 
        subreddit: Optional[str] = None,
        max_posts: int = 100,
        sort: str = "relevance",
        time_filter: str = "all"
    ) -> AsyncGenerator[RedditPost, None]:
        """
        Search for posts across Reddit or within a specific subreddit.
        
        Args:
            query: Search query
            subreddit: Optional subreddit to limit search to
            max_posts: Maximum number of posts to return
            sort: Sort method (relevance, hot, top, new, comments)
            time_filter: Time filter (hour, day, week, month, year, all)
        """
        if not self.reddit:
            raise ValueError("Reddit client not initialized")
            
        try:
            if subreddit:
                search_target = self.reddit.subreddit(subreddit)
                logger.info(f"Searching r/{subreddit} for '{query}'")
            else:
                search_target = self.reddit.subreddit("all")
                logger.info(f"Searching all of Reddit for '{query}'")
                
            submissions = search_target.search(
                query=query,
                sort=sort,
                time_filter=time_filter,
                limit=max_posts
            )
            
            posts_yielded = 0
            
            for submission in submissions:
                if posts_yielded >= max_posts:
                    break
                    
                try:
                    post = await self._convert_submission_to_post(submission)
                    yield post
                    posts_yielded += 1
                    
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing search result {submission.id}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error searching Reddit: {str(e)}")
            raise
            
    async def get_user_posts(
        self, 
        username: str, 
        max_posts: int = 100,
        sort: str = "new"
    ) -> AsyncGenerator[RedditPost, None]:
        """Get posts from a specific Reddit user."""
        if not self.reddit:
            raise ValueError("Reddit client not initialized")
            
        try:
            user = self.reddit.redditor(username)
            logger.info(f"Scraping posts from u/{username}")
            
            if sort == "new":
                submissions = user.submissions.new(limit=max_posts)
            elif sort == "top":
                submissions = user.submissions.top(limit=max_posts)
            elif sort == "hot":
                submissions = user.submissions.hot(limit=max_posts)
            else:
                submissions = user.submissions.new(limit=max_posts)
                
            posts_yielded = 0
            
            for submission in submissions:
                if posts_yielded >= max_posts:
                    break
                    
                try:
                    post = await self._convert_submission_to_post(submission)
                    yield post
                    posts_yielded += 1
                    
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing user post {submission.id}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping user u/{username}: {str(e)}")
            raise
