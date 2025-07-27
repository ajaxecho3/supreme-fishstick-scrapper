"""
Reddit RSS feed scraper implementation.
"""
import asyncio
import feedparser
from typing import AsyncGenerator, Dict, List, Any, Optional
from datetime import datetime
from loguru import logger
import re
from urllib.parse import urljoin

from ..models import RedditPost, Platform, PostType, ScrapingStrategy
from ..config import settings
from .base import BaseScraper


class RedditFeedScraper(BaseScraper):
    """Scrape Reddit using RSS feeds."""
    
    def __init__(self):
        super().__init__(Platform.REDDIT, ScrapingStrategy.FEED)
        self.base_url = "https://www.reddit.com"
        
    async def scrape_posts(
        self, 
        target: str, 
        max_posts: int = 100, 
        sort: str = "hot",
        time_filter: str = "all"
    ) -> AsyncGenerator[RedditPost, None]:
        """
        Scrape posts from subreddit using RSS feeds.
        
        Args:
            target: Subreddit name (without r/)
            max_posts: Maximum number of posts to scrape
            sort: Sort method (hot, new, top, rising)
            time_filter: Time filter (not used for RSS)
        """
        logger.info(f"RSS scraping r/{target} - {sort} posts (max: {max_posts})")
        
        # Build RSS URL
        if sort == "new":
            rss_url = f"{self.base_url}/r/{target}/new.rss"
        elif sort == "top":
            rss_url = f"{self.base_url}/r/{target}/top.rss"
        elif sort == "rising":
            rss_url = f"{self.base_url}/r/{target}/rising.rss"
        else:  # default to hot
            rss_url = f"{self.base_url}/r/{target}.rss"
            
        try:
            # Make request to get RSS content
            response = await self._make_request(rss_url)
            
            if 'text' in response:
                # Parse RSS feed
                feed = feedparser.parse(response['text'])
                
                if feed.bozo:
                    logger.warning(f"RSS feed parsing warning for r/{target}: {feed.bozo_exception}")
                
                posts_yielded = 0
                
                for entry in feed.entries[:max_posts]:
                    try:
                        post = self._convert_rss_entry_to_post(entry, target)
                        yield post
                        posts_yielded += 1
                        
                        # Respectful delay
                        await asyncio.sleep(settings.min_request_delay)
                        
                    except Exception as e:
                        logger.error(f"Error processing RSS entry: {str(e)}")
                        continue
                        
                logger.info(f"Successfully scraped {posts_yielded} posts from r/{target} RSS")
                
            else:
                logger.warning(f"No RSS content found for r/{target}")
                
        except Exception as e:
            logger.error(f"Error scraping RSS for r/{target}: {str(e)}")
            raise
            
    async def scrape_search(
        self, 
        query: str, 
        max_posts: int = 100,
        subreddit: Optional[str] = None,
        sort: str = "relevance"
    ) -> AsyncGenerator[RedditPost, None]:
        """RSS feeds don't support search - fallback to web scraping method."""
        logger.warning("RSS feeds don't support search. Consider using web scraping strategy.")
        # RSS doesn't support search, so we'll return empty results
        return
        yield  # Make this a generator
            
    async def scrape_comments(
        self, 
        post_url: str, 
        max_comments: int = 100
    ) -> AsyncGenerator[RedditPost, None]:
        """RSS feeds don't support comment scraping - return empty results."""
        logger.warning("RSS feeds don't support comment scraping. Consider using web scraping strategy.")
        # RSS doesn't support comment scraping, so we'll return empty results
        return
        yield  # Make this a generator
            
    async def scrape_comments(
        self, 
        post_url: str, 
        max_comments: int = 100
    ) -> AsyncGenerator[RedditPost, None]:
        """RSS feeds don't support comment scraping - return empty results."""
        logger.warning("RSS feeds don't support comment scraping. Consider using web scraping strategy.")
        # RSS doesn't support comment scraping, so we'll return empty results
        return
        yield  # Make this a generator
        
    async def scrape_user_posts(
        self, 
        username: str, 
        max_posts: int = 100
    ) -> AsyncGenerator[RedditPost, None]:
        """Scrape posts from a specific user using RSS."""
        logger.info(f"RSS scraping user u/{username} posts (max: {max_posts})")
        
        rss_url = f"{self.base_url}/u/{username}.rss"
        
        try:
            response = await self._make_request(rss_url)
            
            if 'text' in response:
                feed = feedparser.parse(response['text'])
                
                posts_yielded = 0
                
                for entry in feed.entries[:max_posts]:
                    try:
                        # Extract subreddit from the entry
                        subreddit = self._extract_subreddit_from_entry(entry)
                        post = self._convert_rss_entry_to_post(entry, subreddit, username)
                        yield post
                        posts_yielded += 1
                        
                        await asyncio.sleep(settings.min_request_delay)
                        
                    except Exception as e:
                        logger.error(f"Error processing user RSS entry: {str(e)}")
                        continue
                        
                logger.info(f"Successfully scraped {posts_yielded} posts from u/{username}")
                
        except Exception as e:
            logger.error(f"Error scraping RSS for u/{username}: {str(e)}")
            raise
            
    def _convert_rss_entry_to_post(
        self, 
        entry: Any, 
        subreddit: str, 
        author: Optional[str] = None
    ) -> RedditPost:
        """Convert RSS entry to RedditPost model."""
        
        # Extract post ID from link
        post_id = self._extract_post_id_from_url(entry.link)
        
        # Parse the entry content
        title = entry.title
        content = getattr(entry, 'summary', '')
        
        # Extract author from title if not provided
        if not author:
            # RSS titles often have format: "Title by u/username in r/subreddit"
            author_match = re.search(r'by u/(\w+)', title)
            author = author_match.group(1) if author_match else 'unknown'
            
        # Clean up title (remove "by u/username in r/subreddit" part)
        clean_title = re.sub(r'\s+by u/\w+ in r/\w+$', '', title)
        
        # Extract hashtags and mentions
        combined_text = f"{clean_title} {content}"
        hashtags = re.findall(r'#\w+', combined_text)
        mentions = re.findall(r'/u/(\w+)', combined_text)
        
        # Parse publication date
        created_at = datetime.now()
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                created_at = datetime(*entry.published_parsed[:6])
            except (TypeError, ValueError):
                pass
                
        return RedditPost(
            id=post_id,
            post_type=PostType.POST,
            author=author,
            content=clean_title,
            url=entry.link,
            created_at=created_at,
            score=0,  # RSS doesn't provide score
            upvotes=0,  # RSS doesn't provide upvotes
            downvotes=0,  # RSS doesn't provide downvotes
            replies=0,  # RSS doesn't provide comment count
            subreddit=subreddit,
            hashtags=hashtags,
            mentions=mentions,
            media_urls=[entry.link] if entry.link else [],
            
            # Reddit-specific fields (limited in RSS)
            flair=None,
            is_self=False,  # Can't determine from RSS
            selftext=content,
            num_comments=0,
            over_18=False,  # Can't determine from RSS
            spoiler=False,
            stickied=False,
            locked=False,
            
            raw_data={
                'rss_entry': {
                    'title': entry.title,
                    'link': entry.link,
                    'summary': getattr(entry, 'summary', ''),
                    'published': getattr(entry, 'published', ''),
                    'id': getattr(entry, 'id', ''),
                }
            }
        )
        
    def _extract_post_id_from_url(self, url: str) -> str:
        """Extract Reddit post ID from URL."""
        # Reddit URLs have format: https://www.reddit.com/r/subreddit/comments/POST_ID/title/
        id_match = re.search(r'/comments/([a-zA-Z0-9]+)/', url)
        if id_match:
            return id_match.group(1)
        
        # Fallback: use the last part of the URL or generate a hash
        return url.split('/')[-1] or str(hash(url))[-8:]
        
    def _extract_subreddit_from_entry(self, entry: Any) -> str:
        """Extract subreddit name from RSS entry."""
        # Try to extract from title first
        title = entry.title
        subreddit_match = re.search(r'in r/(\w+)', title)
        if subreddit_match:
            return subreddit_match.group(1)
            
        # Try to extract from link
        link = entry.link
        link_match = re.search(r'/r/(\w+)/', link)
        if link_match:
            return link_match.group(1)
            
        return 'unknown'
        
    async def get_available_feeds(self) -> List[Dict[str, str]]:
        """Get list of available RSS feed types."""
        return [
            {"name": "Hot Posts", "url_suffix": ".rss", "description": "Hot posts from subreddit"},
            {"name": "New Posts", "url_suffix": "/new.rss", "description": "Newest posts from subreddit"},
            {"name": "Top Posts", "url_suffix": "/top.rss", "description": "Top posts from subreddit"},
            {"name": "Rising Posts", "url_suffix": "/rising.rss", "description": "Rising posts from subreddit"},
        ]
