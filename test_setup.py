"""
Test script to verify the web scraper setup.
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database import db_manager
from src.config import settings
from src.models import Platform


def test_config():
    """Test configuration loading."""
    print("🔧 Testing configuration...")
    print(f"   Database URL: {settings.database_url}")
    print(f"   Max concurrent requests: {settings.max_concurrent_requests}")
    print(f"   Rate limit: {settings.rate_limit_requests}/{settings.rate_limit_window}s")
    print("✅ Configuration loaded successfully")


def test_database():
    """Test database setup."""
    print("\n💾 Testing database...")
    try:
        db_manager.create_tables()
        print("✅ Database tables created successfully")
        
        # Test database connection
        with db_manager.get_session() as db:
            from src.database import ScrapingJobDB
            count = db.query(ScrapingJobDB).count()
            print(f"   Current jobs in database: {count}")
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    return True


async def test_scrapers():
    """Test scraper initialization."""
    print("\n🕷️  Testing scrapers...")
    
    try:
        from src.scrapers.manager import scraper_manager
        
        async with scraper_manager:
            print("✅ Scraper manager initialized")
            
            # Test health check
            health = await scraper_manager.health_check()
            print(f"   Health status: {health}")
            
            # Test creating a job (without running it)
            job_id = await scraper_manager.create_job(
                platform=Platform.REDDIT,
                target="test",
                max_posts=1
            )
            print(f"✅ Test job created: {job_id}")
            
            # Check job status
            status = await scraper_manager.get_job_status(job_id)
            print(f"   Job status: {status['status']}")
            
    except Exception as e:
        print(f"❌ Scraper test failed: {e}")
        return False
    return True


def test_models():
    """Test data models."""
    print("\n📋 Testing data models...")
    
    try:
        from src.models import RedditPost, TwitterPost, PostType
        from datetime import datetime
        
        # Test Reddit post model
        reddit_post = RedditPost(
            id="test123",
            post_type=PostType.POST,
            author="test_user",
            content="Test post content",
            url="https://reddit.com/test",
            created_at=datetime.utcnow(),
            subreddit="test"
        )
        print("✅ Reddit post model works")
        
        # Test Twitter post model
        twitter_post = TwitterPost(
            id="test456",
            tweet_id="test456",
            post_type=PostType.TWEET,
            author="test_user",
            content="Test tweet content",
            url="https://twitter.com/test",
            created_at=datetime.utcnow()
        )
        print("✅ Twitter post model works")
        
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False
    return True


async def main():
    """Run all tests."""
    print("🧪 Running Web Scraper Tests\n")
    
    success = True
    
    # Test configuration
    try:
        test_config()
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        success = False
    
    # Test models
    if not test_models():
        success = False
    
    # Test database
    if not test_database():
        success = False
    
    # Test scrapers
    if not await test_scrapers():
        success = False
    
    print(f"\n{'🎉 All tests passed!' if success else '❌ Some tests failed'}")
    
    if success:
        print("\n📋 Setup verification completed successfully!")
        print("   You can now use the scraper with:")
        print("   python main.py --help")
    else:
        print("\n⚠️  Please check the error messages above and fix any issues.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
