"""
Example usage of the web scraper.
"""
import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.scrapers.manager import scraper_manager
from src.models import Platform
from src.database import db_manager


async def main():
    """Example scraping workflow."""
    
    # Initialize database
    db_manager.create_tables()
    print("📋 Database initialized")
    
    # Start scraper manager
    async with scraper_manager:
        print("🚀 Scraper manager started")
        
        # Health check
        health = await scraper_manager.health_check()
        print(f"🏥 Health check: {health}")
        
        # Example 1: Scrape Reddit subreddit
        print("\n🔴 Starting Reddit scraping...")
        reddit_job_id = await scraper_manager.scrape_reddit_subreddit(
            subreddit="python",
            max_posts=20,
            include_comments=False
        )
        print(f"📝 Created Reddit job: {reddit_job_id}")
        
        # Example 2: Scrape Twitter user (requires API credentials)
        print("\n🐦 Starting Twitter scraping...")
        try:
            twitter_job_id = await scraper_manager.scrape_twitter_user(
                username="@python",
                max_posts=20,
                include_comments=False
            )
            print(f"📝 Created Twitter job: {twitter_job_id}")
        except Exception as e:
            print(f"⚠️  Twitter scraping failed (likely missing credentials): {e}")
        
        # Wait a bit for jobs to process
        print("\n⏳ Waiting for jobs to process...")
        await asyncio.sleep(10)
        
        # Check job statuses
        reddit_status = await scraper_manager.get_job_status(reddit_job_id)
        print(f"\n📊 Reddit job status: {reddit_status['status']}")
        print(f"   Posts scraped: {reddit_status['posts_scraped']}")
        
        # Get some scraped posts
        posts = await scraper_manager.get_scraped_posts(
            platform=Platform.REDDIT,
            limit=5
        )
        
        print(f"\n📋 Sample of {len(posts)} scraped posts:")
        for i, post in enumerate(posts[:3], 1):
            print(f"  {i}. [{post['author']}] {post['content'][:100]}...")
            
        print("\n✅ Example completed!")


if __name__ == "__main__":
    asyncio.run(main())
