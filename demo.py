#!/usr/bin/env python3
"""
Simple demo of the web scraper functionality.
"""
import asyncio
import sys
import os
from datetime import datetime

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.scrapers.reddit_scraper import RedditScraper
from src.models import Platform
from src.database import db_manager

async def demo_reddit_scraper():
    """Demo Reddit scraping functionality."""
    print("🚀 Starting Reddit Scraper Demo")
    print("=" * 50)
    
    # Initialize database
    db_manager.create_tables()
    print("✅ Database initialized")
    
    # Create Reddit scraper
    scraper = RedditScraper()
    
    async with scraper:
        print("\n🔴 Testing Reddit scraper...")
        
        try:
            # Test scraping a few posts from r/python
            print("📋 Scraping posts from r/python (limit: 5)...")
            
            posts_scraped = 0
            async for post in scraper.scrape_posts("python", max_posts=5):
                posts_scraped += 1
                print(f"\n📝 Post {posts_scraped}:")
                print(f"   Author: {post.author}")
                print(f"   Title: {post.content[:100]}...")
                print(f"   Score: {post.score}")
                print(f"   URL: {post.url}")
                print(f"   Created: {post.created_at}")
                
                # Save to database
                try:
                    db_manager.save_post(post.dict())
                    print("   ✅ Saved to database")
                except Exception as e:
                    print(f"   ❌ Error saving: {e}")
                
                # Break after a few posts for demo
                if posts_scraped >= 3:
                    break
                    
            print(f"\n🎉 Successfully scraped {posts_scraped} posts from Reddit!")
            
        except Exception as e:
            print(f"❌ Error during scraping: {e}")
            print("   This might be due to missing Reddit API credentials.")
            print("   To use real Reddit scraping, set up your .env file with:")
            print("   - REDDIT_CLIENT_ID")
            print("   - REDDIT_CLIENT_SECRET") 
            print("   - REDDIT_USER_AGENT")
    
    # Show database stats
    print(f"\n📊 Database Statistics:")
    try:
        with db_manager.get_session() as db:
            from src.database import ScrapedPostDB
            total_posts = db.query(ScrapedPostDB).count()
            reddit_posts = db.query(ScrapedPostDB).filter(ScrapedPostDB.platform == "reddit").count()
            print(f"   Total posts in database: {total_posts}")
            print(f"   Reddit posts: {reddit_posts}")
    except Exception as e:
        print(f"   Error querying database: {e}")
    
    print("\n✅ Demo completed!")

if __name__ == "__main__":
    # Run the demo
    asyncio.run(demo_reddit_scraper())
