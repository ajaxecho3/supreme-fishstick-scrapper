"""
Base scraper class and common utilities.
"""
import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timedelta
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from aiolimiter import AsyncLimiter
import backoff

from ..models import ScrapedPost, ScrapingJob, ScrapingResult, Platform, ScrapingStrategy
from ..config import settings
from ..database import db_manager


class RateLimiter:
    """Async rate limiter for API requests."""
    
    def __init__(self, requests_per_window: int = 60, window_seconds: int = 60):
        self.limiter = AsyncLimiter(requests_per_window, window_seconds)
        
    async def acquire(self):
        """Acquire rate limit permission."""
        await self.limiter.acquire()


class BaseScraper(ABC):
    """Base class for all scrapers."""
    
    def __init__(self, platform: Platform, strategy: ScrapingStrategy = ScrapingStrategy.API):
        self.platform = platform
        self.strategy = strategy
        self.rate_limiter = RateLimiter(
            settings.rate_limit_requests,
            settings.rate_limit_window
        )
        self.session: Optional[aiohttp.ClientSession] = None
        self._setup_logging()
        
    def _setup_logging(self):
        """Set up logging for the scraper."""
        logger.add(
            f"logs/{self.platform.value}_{self.strategy.value}_scraper.log",
            rotation="1 day",
            retention="30 days",
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
        )
        
    async def __aenter__(self):
        """Async context manager entry."""
        connector = aiohttp.TCPConnector(
            limit=settings.max_concurrent_requests,
            limit_per_host=10,
            ttl_dns_cache=300,
            use_dns_cache=True,
            ssl=False  # Disable SSL verification for web scraping
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self._get_default_headers()
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for HTTP requests."""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def _make_request(self, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        await self.rate_limiter.acquire()
        
        try:
            async with self.session.get(url, **kwargs) as response:
                response.raise_for_status()
                
                if 'application/json' in response.headers.get('content-type', ''):
                    return await response.json()
                else:
                    return {'text': await response.text()}
                    
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error {e.status} for URL {url}: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Request failed for URL {url}: {str(e)}")
            raise
            
    @abstractmethod
    async def scrape_posts(self, target: str, max_posts: int = 100, **kwargs) -> AsyncGenerator[ScrapedPost, None]:
        """Scrape posts from the platform."""
        pass
        
    @abstractmethod
    async def scrape_comments(self, post_id: str, max_comments: int = 100) -> AsyncGenerator[ScrapedPost, None]:
        """Scrape comments for a specific post."""
        pass
        
    async def run_scraping_job(self, job: ScrapingJob) -> ScrapingResult:
        """Run a complete scraping job."""
        result = ScrapingResult(job_id=job.job_id, started_at=datetime.utcnow())
        
        try:
            # Update job status
            db_manager.update_job_status(
                job.job_id, 
                "running", 
                started_at=result.started_at
            )
            
            logger.info(f"Starting scraping job {job.job_id} for {job.platform.value}")
            
            posts_scraped = 0
            comments_scraped = 0
            
            # Scrape posts
            async for post in self.scrape_posts(job.target, job.max_posts):
                try:
                    # Filter by keywords if specified
                    if job.keywords and not self._matches_keywords(post.content, job.keywords):
                        continue
                        
                    # Save post to database
                    post_data = post.dict()
                    db_manager.save_post(post_data)
                    posts_scraped += 1
                    
                    # Scrape comments if requested
                    if job.include_comments:
                        async for comment in self.scrape_comments(post.id):
                            try:
                                comment_data = comment.dict()
                                db_manager.save_post(comment_data)
                                comments_scraped += 1
                            except Exception as e:
                                logger.error(f"Error saving comment: {str(e)}")
                                result.errors.append(f"Comment save error: {str(e)}")
                                
                    # Add delay between posts
                    await asyncio.sleep(settings.request_delay)
                    
                except Exception as e:
                    logger.error(f"Error processing post {post.id}: {str(e)}")
                    result.errors.append(f"Post processing error: {str(e)}")
                    
            result.posts_scraped = posts_scraped
            result.comments_scraped = comments_scraped
            result.completed_at = datetime.utcnow()
            result.success = True
            
            # Update job status
            db_manager.update_job_status(
                job.job_id,
                "completed",
                posts_scraped=posts_scraped,
                comments_scraped=comments_scraped,
                completed_at=result.completed_at,
                success=True,
                errors=result.errors
            )
            
            logger.info(f"Completed job {job.job_id}: {posts_scraped} posts, {comments_scraped} comments")
            
        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {str(e)}")
            result.errors.append(f"Job failed: {str(e)}")
            result.completed_at = datetime.utcnow()
            
            # Update job status
            db_manager.update_job_status(
                job.job_id,
                "failed",
                completed_at=result.completed_at,
                errors=result.errors
            )
            
        return result
        
    def _matches_keywords(self, content: str, keywords: List[str]) -> bool:
        """Check if content matches any of the specified keywords."""
        content_lower = content.lower()
        return any(keyword.lower() in content_lower for keyword in keywords)
        
    async def health_check(self) -> bool:
        """Perform health check for the scraper."""
        try:
            await self._make_request("https://httpbin.org/status/200")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
