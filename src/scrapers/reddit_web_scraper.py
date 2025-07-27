"""
Reddit web scraper implementation - no API credentials required.
"""
import asyncio
import json
import re
from typing import AsyncGenerator, Dict, List, Any, Optional
from datetime import datetime
from loguru import logger
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from ..models import RedditPost, Platform, PostType, ScrapingStrategy
from ..config import settings
from .base import BaseScraper


class RedditWebScraper(BaseScraper):
    """Scrape Reddit without API using web scraping."""
    
    def __init__(self):
        super().__init__(Platform.REDDIT, ScrapingStrategy.WEB)
        self.base_url = "https://www.reddit.com"
        
    async def scrape_posts(
        self, 
        target: str, 
        max_posts: int = 100, 
        sort: str = "hot",
        time_filter: str = "all"
    ) -> AsyncGenerator[RedditPost, None]:
        """
        Scrape posts from subreddit using Reddit's JSON endpoint.
        
        Args:
            target: Subreddit name (without r/)
            max_posts: Maximum number of posts to scrape
            sort: Sort method (hot, new, top, rising)
            time_filter: Time filter for 'top' sort (hour, day, week, month, year, all)
        """
        logger.info(f"Web scraping r/{target} - {sort} posts (max: {max_posts})")
        
        # Build URL for Reddit JSON endpoint
        if sort == "top":
            url = f"{self.base_url}/r/{target}/{sort}.json?t={time_filter}"
        else:
            url = f"{self.base_url}/r/{target}/{sort}.json"
            
        params = {"limit": min(100, max_posts)}
        
        try:
            # Reddit's JSON endpoint doesn't require authentication
            response = await self._make_request(url, params=params)
            
            if 'data' in response and 'children' in response['data']:
                posts_yielded = 0
                
                for item in response['data']['children']:
                    if posts_yielded >= max_posts:
                        break
                        
                    post_data = item['data']
                    
                    try:
                        post = self._convert_json_to_post(post_data, target)
                        yield post
                        posts_yielded += 1
                        
                        # Respectful delay
                        await asyncio.sleep(settings.min_request_delay)
                        
                    except Exception as e:
                        logger.error(f"Error processing post {post_data.get('id', 'unknown')}: {str(e)}")
                        continue
                        
                logger.info(f"Successfully scraped {posts_yielded} posts from r/{target}")
                
            else:
                logger.warning(f"No data found for r/{target}")
                
        except Exception as e:
            logger.error(f"Error scraping r/{target}: {str(e)}")
            raise
            
    async def scrape_search(
        self, 
        query: str, 
        max_posts: int = 100,
        subreddit: Optional[str] = None,
        sort: str = "relevance"
    ) -> AsyncGenerator[RedditPost, None]:
        """Search Reddit posts without API."""
        logger.info(f"Web scraping Reddit search for: '{query}' (max: {max_posts})")
        
        url = f"{self.base_url}/search.json"
        params = {
            "q": query,
            "sort": sort,
            "limit": min(100, max_posts),
            "type": "link"
        }
        
        if subreddit:
            params["q"] = f"subreddit:{subreddit} {query}"
            
        try:
            response = await self._make_request(url, params=params)
            
            if 'data' in response and 'children' in response['data']:
                posts_yielded = 0
                
                for item in response['data']['children']:
                    if posts_yielded >= max_posts:
                        break
                        
                    post_data = item['data']
                    
                    try:
                        post = self._convert_json_to_post(post_data, post_data.get('subreddit', 'unknown'))
                        yield post
                        posts_yielded += 1
                        
                        await asyncio.sleep(settings.min_request_delay)
                        
                    except Exception as e:
                        logger.error(f"Error processing search result {post_data.get('id', 'unknown')}: {str(e)}")
                        continue
                        
                logger.info(f"Successfully scraped {posts_yielded} search results")
                
        except Exception as e:
            logger.error(f"Error searching Reddit for '{query}': {str(e)}")
            raise
            
    async def scrape_comments(
        self, 
        post_url: str, 
        max_comments: int = 100
    ) -> AsyncGenerator[RedditPost, None]:
        """Scrape comments from a Reddit post using JSON endpoint."""
        logger.info(f"Web scraping comments from: {post_url} (max: {max_comments})")
        
        # Convert Reddit URL to JSON endpoint
        if not post_url.endswith('.json'):
            json_url = f"{post_url}.json"
        else:
            json_url = post_url
            
        try:
            response = await self._make_request(json_url)
            
            if isinstance(response, list) and len(response) > 1:
                comments_data = response[1]  # Comments are in the second element
                
                if 'data' in comments_data and 'children' in comments_data['data']:
                    comments_yielded = 0
                    
                    # Recursively process comment tree
                    async for comment in self._process_comment_tree(
                        comments_data['data']['children'], 
                        max_comments - comments_yielded
                    ):
                        yield comment
                        comments_yielded += 1
                        
                        if comments_yielded >= max_comments:
                            break
                            
                        await asyncio.sleep(0.5)
                        
                    logger.info(f"Successfully scraped {comments_yielded} comments")
                    
        except Exception as e:
            logger.error(f"Error scraping comments from {post_url}: {str(e)}")
            raise
            
    async def _process_comment_tree(
        self, 
        comments: List[Dict], 
        max_comments: int
    ) -> AsyncGenerator[RedditPost, None]:
        """Recursively process comment tree."""
        comments_processed = 0
        
        for comment_item in comments:
            if comments_processed >= max_comments:
                break
                
            if comment_item['kind'] == 't1':  # Comment
                comment_data = comment_item['data']
                
                if comment_data.get('body') and comment_data['body'] != '[deleted]':
                    try:
                        comment_post = RedditPost(
                            id=comment_data['id'],
                            post_type=PostType.COMMENT,
                            author=comment_data.get('author', '[deleted]'),
                            content=comment_data.get('body', ''),
                            url=f"{self.base_url}{comment_data.get('permalink', '')}",
                            created_at=datetime.fromtimestamp(comment_data.get('created_utc', 0)),
                            score=comment_data.get('score', 0),
                            upvotes=comment_data.get('ups', 0),
                            replies=len(comment_data.get('replies', {}).get('data', {}).get('children', [])),
                            subreddit=comment_data.get('subreddit', 'unknown'),
                            raw_data=comment_data
                        )
                        
                        yield comment_post
                        comments_processed += 1
                        
                        # Process replies if they exist
                        if comment_data.get('replies') and isinstance(comment_data['replies'], dict):
                            replies_data = comment_data['replies'].get('data', {}).get('children', [])
                            
                            async for reply in self._process_comment_tree(
                                replies_data, 
                                max_comments - comments_processed
                            ):
                                yield reply
                                comments_processed += 1
                                
                                if comments_processed >= max_comments:
                                    break
                                    
                    except Exception as e:
                        logger.error(f"Error processing comment {comment_data.get('id', 'unknown')}: {str(e)}")
                        continue
                        
    def _convert_json_to_post(self, post_data: Dict[str, Any], subreddit: str) -> RedditPost:
        """Convert Reddit JSON data to RedditPost model."""
        
        # Extract hashtags and mentions from title and selftext
        title = post_data.get('title', '')
        selftext = post_data.get('selftext', '')
        combined_text = f"{title} {selftext}"
        
        hashtags = re.findall(r'#\w+', combined_text)
        mentions = re.findall(r'/u/(\w+)', combined_text)
        
        # Extract media URLs
        media_urls = []
        if post_data.get('url'):
            media_urls.append(post_data['url'])
        if post_data.get('preview', {}).get('images'):
            for img in post_data['preview']['images']:
                if img.get('source', {}).get('url'):
                    media_urls.append(img['source']['url'])
                    
        return RedditPost(
            id=post_data['id'],
            post_type=PostType.POST,
            author=post_data.get('author', '[deleted]'),
            content=title,
            url=f"{self.base_url}{post_data.get('permalink', '')}",
            created_at=datetime.fromtimestamp(post_data.get('created_utc', 0)),
            score=post_data.get('score', 0),
            upvotes=post_data.get('ups', 0),
            downvotes=post_data.get('downs', 0),
            replies=post_data.get('num_comments', 0),
            subreddit=subreddit,
            hashtags=hashtags,
            mentions=mentions,
            media_urls=media_urls,
            
            # Reddit-specific fields
            flair=post_data.get('link_flair_text'),
            is_self=post_data.get('is_self', False),
            selftext=selftext,
            num_comments=post_data.get('num_comments', 0),
            over_18=post_data.get('over_18', False),
            spoiler=post_data.get('spoiler', False),
            stickied=post_data.get('stickied', False),
            locked=post_data.get('locked', False),
            
            raw_data=post_data
        )
        
    async def get_subreddit_info(self, subreddit: str) -> Dict[str, Any]:
        """Get subreddit information using web scraping."""
        url = f"{self.base_url}/r/{subreddit}/about.json"
        
        try:
            response = await self._make_request(url)
            
            if 'data' in response:
                data = response['data']
                return {
                    'name': data.get('display_name', subreddit),
                    'title': data.get('title', ''),
                    'description': data.get('public_description', ''),
                    'subscribers': data.get('subscribers', 0),
                    'created_utc': data.get('created_utc', 0),
                    'over18': data.get('over18', False)
                }
                
        except Exception as e:
            logger.error(f"Error getting info for r/{subreddit}: {str(e)}")
            
        return {}
