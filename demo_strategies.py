#!/usr/bin/env python3
"""
Enhanced Web Scraper Example Usage - Multiple Strategies
"""
import asyncio
from src.scrapers.manager import EnhancedScraperManager
from src.models import Platform, ScrapingStrategy
from src.database import db_manager

async def demo_reddit_strategies():
    """Demonstrate different Reddit scraping strategies."""
    print("🚀 Enhanced Web Scraper - Strategy Demo")
    print("=" * 50)
    
    # Initialize database
    db_manager.create_tables()
    
    async with EnhancedScraperManager() as manager:
        
        # Show available strategies
        print("\n📋 Available Strategies:")
        strategy_info = await manager.get_strategy_info()
        
        for platform, info in strategy_info.items():
            print(f"\n{platform.value.upper()}:")
            for strategy in info['available_strategies']:
                print(f"  ✅ {strategy.value}")
        
        # Test each strategy with a small sample
        test_subreddit = "python"
        test_posts = 5
        
        strategies_to_test = await manager.get_available_strategies(Platform.REDDIT)
        
        for strategy in strategies_to_test:
            print(f"\n🔄 Testing {strategy.value} strategy...")
            
            try:
                posts = await manager.scrape_with_fallback(
                    platform=Platform.REDDIT,
                    target=test_subreddit,
                    max_posts=test_posts,
                    preferred_strategy=strategy
                )
                
                if posts:
                    print(f"  ✅ Success! Got {len(posts)} posts")
                    
                    # Show first post as example
                    sample = posts[0]
                    print(f"  📝 Sample: {sample.content[:60]}...")
                    print(f"  👤 Author: u/{sample.author}")
                    print(f"  📊 Score: {sample.score}")
                    
                    # Save to database
                    saved_count = 0
                    for post in posts:
                        try:
                            db_manager.save_post(post.dict())
                            saved_count += 1
                        except Exception as e:
                            print(f"  ⚠️ Error saving post: {e}")
                    
                    print(f"  💾 Saved {saved_count} posts to database")
                    
                else:
                    print(f"  ⚠️ No posts returned")
                    
            except Exception as e:
                print(f"  ❌ Failed: {e}")
        
        # Demonstrate fallback behavior
        print(f"\n🔄 Testing automatic fallback...")
        try:
            posts = await manager.scrape_with_fallback(
                platform=Platform.REDDIT,
                target="programming",
                max_posts=3,
                preferred_strategy=ScrapingStrategy.API  # This might fail without credentials
            )
            
            print(f"  ✅ Fallback successful! Got {len(posts)} posts")
            
        except Exception as e:
            print(f"  ❌ All strategies failed: {e}")

        # Test search functionality
        print(f"\n🔍 Testing search functionality...")
        try:
            search_posts = await manager.scrape_search_with_fallback(
                platform=Platform.REDDIT,
                query="python tutorial",
                max_posts=3
            )
            
            if search_posts:
                print(f"  ✅ Search successful! Found {len(search_posts)} posts")
                for i, post in enumerate(search_posts[:2]):
                    print(f"    {i+1}. [{post.subreddit}] {post.content[:50]}...")
            else:
                print(f"  ⚠️ No search results")
                
        except Exception as e:
            print(f"  ❌ Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(demo_reddit_strategies())
