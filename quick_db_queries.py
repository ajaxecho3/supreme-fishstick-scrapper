#!/usr/bin/env python3
"""
Simple database query examples for web scraper.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import db_manager
from sqlalchemy import text

def quick_queries():
    """Run some quick database queries."""
    
    print("🗄️ Database Quick Queries")
    print("=" * 50)
    
    with db_manager.get_session() as db:
        
        # 1. Total posts count
        total = db.execute(text("SELECT COUNT(*) FROM scraped_posts")).scalar()
        print(f"📊 Total Posts: {total}")
        
        # 2. Posts by subreddit
        print(f"\n📍 Posts by Subreddit:")
        subreddits = db.execute(text("""
            SELECT subreddit, COUNT(*) as count 
            FROM scraped_posts 
            WHERE subreddit IS NOT NULL 
            GROUP BY subreddit 
            ORDER BY count DESC 
            LIMIT 5
        """)).fetchall()
        
        for subreddit, count in subreddits:
            print(f"   r/{subreddit}: {count} posts")
        
        # 3. Top scoring posts
        print(f"\n🏆 Top Scoring Posts:")
        top_posts = db.execute(text("""
            SELECT author, content, score, subreddit 
            FROM scraped_posts 
            ORDER BY score DESC 
            LIMIT 3
        """)).fetchall()
        
        for i, (author, content, score, subreddit) in enumerate(top_posts, 1):
            print(f"   {i}. {content[:60]}...")
            print(f"      👤 u/{author} | 📊 {score} | 📍 r/{subreddit}")
        
        # 4. Recent activity
        print(f"\n⏰ Recent Activity:")
        recent = db.execute(text("""
            SELECT author, content, scraped_at 
            FROM scraped_posts 
            ORDER BY scraped_at DESC 
            LIMIT 3
        """)).fetchall()
        
        for author, content, scraped_at in recent:
            print(f"   📝 {content[:50]}...")
            print(f"      👤 u/{author} | 🕐 {scraped_at}")
        
        # 5. Authors with most posts
        print(f"\n👥 Most Active Authors:")
        authors = db.execute(text("""
            SELECT author, COUNT(*) as post_count 
            FROM scraped_posts 
            GROUP BY author 
            ORDER BY post_count DESC 
            LIMIT 5
        """)).fetchall()
        
        for author, count in authors:
            print(f"   u/{author}: {count} posts")

if __name__ == "__main__":
    quick_queries()
