"""
Enhanced scraper manager with multiple strategies and automatic fallback.
"""
import asyncio
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
from loguru import logger
import uuid

from ..models import Platform, ScrapingJob, ScrapingResult, ScrapingStrategy
from ..config import settings
from ..database import db_manager
from .reddit_scraper import RedditScraper
from .reddit_web_scraper import RedditWebScraper  
from .reddit_feed_scraper import RedditFeedScraper
# from .twitter_scraper import TwitterScraper


class EnhancedScraperManager:
    """Enhanced manager with multiple scraping strategies and automatic fallback."""
    
    def __init__(self):
        self.strategies: Dict[Platform, Dict[ScrapingStrategy, Any]] = {}
        self.active_jobs: Dict[str, asyncio.Task] = {}
        
    async def __aenter__(self):
        """Initialize all available scrapers with fallback strategies."""
        logger.info("Initializing enhanced scraper manager with multiple strategies...")
        
        # Initialize Reddit scrapers
        await self._init_reddit_scrapers()
        
        # Initialize Twitter scrapers (future enhancement)
        # await self._init_twitter_scrapers()
        
        logger.info(f"Scraper manager initialized with strategies: {list(self.strategies.keys())}")
        return self
        
    async def _init_reddit_scrapers(self):
        """Initialize Reddit scrapers with multiple strategies."""
        self.strategies[Platform.REDDIT] = {}
        
        # Try API scraper first (if enabled and credentials available)
        if settings.enable_api_scrapers:
            try:
                reddit_api = RedditScraper()
                await reddit_api.__aenter__()
                self.strategies[Platform.REDDIT][ScrapingStrategy.API] = reddit_api
                logger.info("✅ Reddit API scraper initialized")
            except Exception as e:
                logger.warning(f"❌ Reddit API scraper failed: {e}")
        
        # Always initialize web scraper (no credentials needed)
        try:
            reddit_web = RedditWebScraper()
            await reddit_web.__aenter__()
            self.strategies[Platform.REDDIT][ScrapingStrategy.WEB] = reddit_web
            logger.info("✅ Reddit web scraper initialized")
        except Exception as e:
            logger.error(f"❌ Reddit web scraper failed: {e}")
            
        # Initialize RSS feed scraper
        try:
            reddit_feed = RedditFeedScraper()
            await reddit_feed.__aenter__()
            self.strategies[Platform.REDDIT][ScrapingStrategy.FEED] = reddit_feed
            logger.info("✅ Reddit RSS feed scraper initialized")
        except Exception as e:
            logger.warning(f"❌ Reddit RSS feed scraper failed: {e}")
            
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up all scrapers."""
        for platform_strategies in self.strategies.values():
            for scraper in platform_strategies.values():
                if hasattr(scraper, '__aexit__'):
                    try:
                        await scraper.__aexit__(exc_type, exc_val, exc_tb)
                    except Exception as e:
                        logger.error(f"Error closing scraper: {e}")
                        
        # Cancel active jobs
        for job_id, task in self.active_jobs.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info(f"Cancelled job: {job_id}")
                
    async def scrape_with_fallback(
        self, 
        platform: Platform, 
        target: str, 
        max_posts: int = 100,
        preferred_strategy: Optional[ScrapingStrategy] = None,
        **kwargs
    ) -> List[Any]:
        """
        Scrape with automatic fallback strategies.
        
        Args:
            platform: Platform to scrape
            target: Target to scrape (subreddit, username, etc.)
            max_posts: Maximum number of posts
            preferred_strategy: Preferred strategy to try first
            **kwargs: Additional arguments for scrapers
        """
        if platform not in self.strategies:
            raise ValueError(f"No scrapers available for {platform}")
            
        available_strategies = list(self.strategies[platform].keys())
        
        if not available_strategies:
            raise ValueError(f"No working scrapers available for {platform}")
            
        # Determine strategy order
        if preferred_strategy and preferred_strategy in available_strategies:
            strategies_to_try = [preferred_strategy]
            # Add other strategies as fallbacks  
            for strategy in [ScrapingStrategy.WEB, ScrapingStrategy.FEED, ScrapingStrategy.API]:
                if strategy != preferred_strategy and strategy in available_strategies:
                    strategies_to_try.append(strategy)
        else:
            # Default order: web -> feed -> api
            strategies_to_try = []
            default_order = [ScrapingStrategy.WEB, ScrapingStrategy.FEED, ScrapingStrategy.API]
            for strategy in default_order:
                if strategy in available_strategies:
                    strategies_to_try.append(strategy)
                    
        if not strategies_to_try:
            raise ValueError(f"No strategies available for {platform}")
            
        last_error = None
        
        for strategy in strategies_to_try:
            try:
                scraper = self.strategies[platform][strategy]
                logger.info(f"🔄 Trying {strategy.value} strategy for {platform.value}")
                
                posts = []
                async for post in scraper.scrape_posts(target, max_posts, **kwargs):
                    posts.append(post)
                    
                if posts:
                    logger.info(f"✅ Successfully scraped {len(posts)} posts with {strategy.value} strategy")
                    return posts
                else:
                    logger.warning(f"⚠️ {strategy.value} strategy returned no posts")
                    continue
                    
            except Exception as e:
                logger.warning(f"❌ {strategy.value} strategy failed: {e}")
                last_error = e
                continue
                
        raise Exception(f"All scraping strategies failed for {platform}. Last error: {last_error}")
        
    async def scrape_search_with_fallback(
        self,
        platform: Platform,
        query: str,
        max_posts: int = 100,
        preferred_strategy: Optional[ScrapingStrategy] = None,
        **kwargs
    ) -> List[Any]:
        """Search with fallback strategies."""
        if platform not in self.strategies:
            raise ValueError(f"No scrapers available for {platform}")
            
        available_strategies = list(self.strategies[platform].keys())
        
        # Some strategies don't support search, so filter them
        search_capable_strategies = []
        for strategy in available_strategies:
            scraper = self.strategies[platform][strategy]
            if hasattr(scraper, 'scrape_search'):
                search_capable_strategies.append(strategy)
                
        if not search_capable_strategies:
            raise ValueError(f"No search-capable scrapers available for {platform}")
            
        # Try preferred strategy first, then others
        if preferred_strategy and preferred_strategy in search_capable_strategies:
            strategies_to_try = [preferred_strategy]
            for strategy in search_capable_strategies:
                if strategy != preferred_strategy:
                    strategies_to_try.append(strategy)
        else:
            strategies_to_try = search_capable_strategies
            
        last_error = None
        
        for strategy in strategies_to_try:
            try:
                scraper = self.strategies[platform][strategy]
                logger.info(f"🔍 Searching with {strategy.value} strategy")
                
                posts = []
                async for post in scraper.scrape_search(query, max_posts, **kwargs):
                    posts.append(post)
                    
                if posts:
                    logger.info(f"✅ Found {len(posts)} posts with {strategy.value} strategy")
                    return posts
                else:
                    logger.warning(f"⚠️ {strategy.value} search returned no results")
                    continue
                    
            except Exception as e:
                logger.warning(f"❌ {strategy.value} search failed: {e}")
                last_error = e
                continue
                
        raise Exception(f"All search strategies failed for {platform}. Last error: {last_error}")
        
    async def get_available_strategies(self, platform: Platform) -> List[ScrapingStrategy]:
        """Get list of available strategies for a platform."""
        if platform in self.strategies:
            return list(self.strategies[platform].keys())
        return []
        
    async def get_strategy_info(self) -> Dict[Platform, Dict[str, Any]]:
        """Get information about available strategies."""
        info = {}
        
        for platform, strategies in self.strategies.items():
            info[platform] = {
                'available_strategies': list(strategies.keys()),
                'strategy_details': {}
            }
            
            for strategy, scraper in strategies.items():
                info[platform]['strategy_details'][strategy] = {
                    'name': strategy.value,
                    'requires_auth': strategy == ScrapingStrategy.API,
                    'supports_search': hasattr(scraper, 'scrape_search'),
                    'supports_comments': hasattr(scraper, 'scrape_comments'),
                    'class': scraper.__class__.__name__
                }
                
        return info
        
    # Legacy methods for backward compatibility
    async def create_job(
        self,
        platform: Platform,
        target: str,
        max_posts: int = 100,
        include_comments: bool = False,
        keywords: Optional[List[str]] = None,
        strategy: Optional[ScrapingStrategy] = None
    ) -> str:
        """Create a new scraping job with strategy selection."""
        job_id = str(uuid.uuid4())
        
        job = ScrapingJob(
            job_id=job_id,
            platform=platform,
            target=target,
            max_posts=max_posts,
            include_comments=include_comments,
            keywords=keywords or []
        )
        
        # Save job to database
        db_manager.save_job(job.dict())
        
        # Automatically start the job with fallback
        task = asyncio.create_task(
            self._run_job_with_fallback(job, strategy)
        )
        self.active_jobs[job_id] = task
        
        logger.info(f"Created and started scraping job {job_id} for {platform.value} target '{target}'")
        return job_id
        
    async def _run_job_with_fallback(self, job: ScrapingJob, preferred_strategy: Optional[ScrapingStrategy] = None):
        """Run a scraping job with automatic fallback."""
        try:
            # Update job status to running
            db_manager.update_job_status(job.job_id, "running", started_at=datetime.utcnow())
            
            posts = await self.scrape_with_fallback(
                platform=job.platform,
                target=job.target,
                max_posts=job.max_posts,
                preferred_strategy=preferred_strategy
            )
            
            # Save posts to database
            posts_saved = 0
            for post in posts:
                try:
                    db_manager.save_post(post.dict())
                    posts_saved += 1
                except Exception as e:
                    logger.error(f"Error saving post {post.id}: {e}")
                    
            # Update job status to completed
            db_manager.update_job_status(
                job.job_id, 
                "completed", 
                completed_at=datetime.utcnow(),
                posts_scraped=posts_saved,
                success=True
            )
            
            logger.info(f"Job {job.job_id} completed successfully. Saved {posts_saved} posts.")
            
        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            db_manager.update_job_status(
                job.job_id, 
                "failed", 
                completed_at=datetime.utcnow(),
                success=False,
                errors=[str(e)]
            )
        finally:
            # Remove from active jobs
            if job.job_id in self.active_jobs:
                del self.active_jobs[job.job_id]
                
    async def scrape_reddit_subreddit(
        self,
        subreddit: str,
        max_posts: int = 100,
        include_comments: bool = False,
        sort: str = "hot",
        strategy: Optional[ScrapingStrategy] = None
    ) -> str:
        """Convenience method to scrape a Reddit subreddit with strategy selection."""
        return await self.create_job(
            platform=Platform.REDDIT,
            target=subreddit,
            max_posts=max_posts,
            include_comments=include_comments,
            strategy=strategy
        )
        
    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get the status of a scraping job."""
        job_data = db_manager.get_job_status(job_id)
        if not job_data:
            return None
            
        is_running = job_id in self.active_jobs
        
        return {
            'job_id': job_data.job_id,
            'platform': job_data.platform,
            'target': job_data.target,
            'status': job_data.status,
            'is_running': is_running,
            'created_at': job_data.created_at,
            'started_at': job_data.started_at,
            'completed_at': job_data.completed_at,
            'posts_scraped': job_data.posts_scraped,
            'comments_scraped': job_data.comments_scraped,
            'success': job_data.success,
            'errors': job_data.errors
        }
        
    async def stop_job(self, job_id: str) -> bool:
        """Stop a running scraping job."""
        if job_id not in self.active_jobs:
            logger.warning(f"Job {job_id} is not running")
            return False
            
        task = self.active_jobs[job_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
            
        del self.active_jobs[job_id]
        
        # Update job status in database
        db_manager.update_job_status(job_id, "cancelled", completed_at=datetime.utcnow())
        
        logger.info(f"Stopped scraping job {job_id}")
        return True
        
    async def list_active_jobs(self) -> List[str]:
        """List all currently active job IDs."""
        return list(self.active_jobs.keys())
        for job_id, task in self.active_jobs.items():
            if not task.done():
                logger.info(f"Cancelling active job {job_id}")
                task.cancel()
                
    async def create_job(
        self,
        platform: Platform,
        target: str,
        max_posts: int = 100,
        include_comments: bool = False,
        keywords: Optional[List[str]] = None
    ) -> str:
        """Create a new scraping job."""
        job_id = str(uuid.uuid4())
        
        job = ScrapingJob(
            job_id=job_id,
            platform=platform,
            target=target,
            max_posts=max_posts,
            include_comments=include_comments,
            keywords=keywords or []
        )
        
        # Save job to database
        db_manager.save_job(job.dict())
        
        logger.info(f"Created scraping job {job_id} for {platform.value} target '{target}'")
        return job_id
        
    async def start_job(self, job_id: str) -> bool:
        """Start a scraping job."""
        if job_id in self.active_jobs:
            logger.warning(f"Job {job_id} is already running")
            return False
            
        # Get job from database
        job_data = db_manager.get_job_status(job_id)
        if not job_data:
            logger.error(f"Job {job_id} not found")
            return False
            
        job = ScrapingJob(
            job_id=job_data.job_id,
            platform=Platform(job_data.platform),
            target=job_data.target,
            max_posts=job_data.max_posts,
            include_comments=job_data.include_comments,
            keywords=job_data.keywords or []
        )
        
        # Get appropriate scraper
        scraper = self.scrapers.get(job.platform)
        if not scraper:
            logger.error(f"No scraper available for platform {job.platform.value}")
            return False
            
        # Start job as background task
        task = asyncio.create_task(scraper.run_scraping_job(job))
        self.active_jobs[job_id] = task
        
        logger.info(f"Started scraping job {job_id}")
        return True
        
    async def stop_job(self, job_id: str) -> bool:
        """Stop a running scraping job."""
        if job_id not in self.active_jobs:
            logger.warning(f"Job {job_id} is not running")
            return False
            
        task = self.active_jobs[job_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
            
        del self.active_jobs[job_id]
        
        # Update job status in database
        db_manager.update_job_status(job_id, "cancelled", completed_at=datetime.utcnow())
        
        logger.info(f"Stopped scraping job {job_id}")
        return True
        
    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get the status of a scraping job."""
        job_data = db_manager.get_job_status(job_id)
        if not job_data:
            return None
            
        is_running = job_id in self.active_jobs
        
        return {
            'job_id': job_data.job_id,
            'platform': job_data.platform,
            'target': job_data.target,
            'status': job_data.status,
            'is_running': is_running,
            'created_at': job_data.created_at,
            'started_at': job_data.started_at,
            'completed_at': job_data.completed_at,
            'posts_scraped': job_data.posts_scraped,
            'comments_scraped': job_data.comments_scraped,
            'success': job_data.success,
            'errors': job_data.errors
        }
        
    async def list_active_jobs(self) -> List[str]:
        """List all currently active job IDs."""
        return list(self.active_jobs.keys())
        
    async def scrape_reddit_subreddit(
        self,
        subreddit: str,
        max_posts: int = 100,
        include_comments: bool = False,
        sort: str = "hot"
    ) -> str:
        """Convenience method to scrape a Reddit subreddit."""
        job_id = await self.create_job(
            platform=Platform.REDDIT,
            target=subreddit,
            max_posts=max_posts,
            include_comments=include_comments
        )
        
        await self.start_job(job_id)
        return job_id
        
    async def scrape_twitter_user(
        self,
        username: str,
        max_posts: int = 100,
        include_comments: bool = False
    ) -> str:
        """Convenience method to scrape a Twitter user."""
        if not username.startswith('@'):
            username = f"@{username}"
            
        job_id = await self.create_job(
            platform=Platform.TWITTER,
            target=username,
            max_posts=max_posts,
            include_comments=include_comments
        )
        
        await self.start_job(job_id)
        return job_id
        
    async def search_twitter(
        self,
        query: str,
        max_posts: int = 100,
        keywords: Optional[List[str]] = None
    ) -> str:
        """Convenience method to search Twitter."""
        job_id = await self.create_job(
            platform=Platform.TWITTER,
            target=query,
            max_posts=max_posts,
            include_comments=False,
            keywords=keywords
        )
        
        await self.start_job(job_id)
        return job_id
        
    async def health_check(self) -> Dict[str, bool]:
        """Perform health check on all scrapers."""
        results = {}
        
        for platform, scraper in self.scrapers.items():
            try:
                is_healthy = await scraper.health_check()
                results[platform.value] = is_healthy
            except Exception as e:
                logger.error(f"Health check failed for {platform.value}: {str(e)}")
                results[platform.value] = False
                
        return results
        
    async def get_scraped_posts(
        self,
        platform: Optional[Platform] = None,
        limit: int = 100,
        author: Optional[str] = None,
        subreddit: Optional[str] = None
    ) -> List[Dict]:
        """Get scraped posts from database with optional filters."""
        with db_manager.get_session() as db:
            from ..database import ScrapedPostDB
            
            query = db.query(ScrapedPostDB)
            
            if platform:
                query = query.filter(ScrapedPostDB.platform == platform.value)
                
            if author:
                query = query.filter(ScrapedPostDB.author == author)
                
            if subreddit:
                query = query.filter(ScrapedPostDB.subreddit == subreddit)
                
            posts = query.order_by(ScrapedPostDB.scraped_at.desc()).limit(limit).all()
            
            return [
                {
                    'id': post.id,
                    'platform': post.platform,
                    'post_type': post.post_type,
                    'author': post.author,
                    'content': post.content[:200] + '...' if len(post.content) > 200 else post.content,
                    'url': post.url,
                    'created_at': post.created_at,
                    'scraped_at': post.scraped_at,
                    'score': post.score,
                    'likes': post.likes,
                    'retweets': post.retweets,
                    'replies': post.replies,
                    'subreddit': post.subreddit,
                    'hashtags': post.hashtags,
                    'mentions': post.mentions
                }
                for post in posts
            ]
            
    async def cleanup_old_jobs(self, days: int = 7):
        """Clean up old completed jobs from database."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with db_manager.get_session() as db:
            from ..database import ScrapingJobDB
            
            old_jobs = db.query(ScrapingJobDB).filter(
                ScrapingJobDB.completed_at < cutoff_date,
                ScrapingJobDB.status.in_(['completed', 'failed', 'cancelled'])
            ).all()
            
            for job in old_jobs:
                db.delete(job)
                
            db.commit()
            logger.info(f"Cleaned up {len(old_jobs)} old jobs")


# Global scraper manager instance
scraper_manager = EnhancedScraperManager()

# Backward compatibility alias
ScraperManager = EnhancedScraperManager
