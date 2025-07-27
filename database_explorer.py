#!/usr/bin/env python3
"""
Database access examples for the web scraper.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import db_manager
from src.models import Platform
from sqlalchemy import text

def show_database_stats():
    """Show database statistics."""
    print("📊 Database Statistics")
    print("=" * 50)
    
    with db_manager.get_session() as db:
        # Count total posts
        total_posts = db.execute(text("SELECT COUNT(*) FROM scraped_posts")).scalar()
        print(f"Total Posts: {total_posts}")
        
        # Count by platform
        platform_counts = db.execute(text("""
            SELECT platform, COUNT(*) as count 
            FROM scraped_posts 
            GROUP BY platform
        """)).fetchall()
        
        print("\nPosts by Platform:")
        for platform, count in platform_counts:
            print(f"  - {platform}: {count}")
        
        # Count by subreddit (for Reddit posts)
        subreddit_counts = db.execute(text("""
            SELECT subreddit, COUNT(*) as count 
            FROM scraped_posts 
            WHERE platform = 'reddit' AND subreddit IS NOT NULL
            GROUP BY subreddit 
            ORDER BY count DESC 
            LIMIT 10
        """)).fetchall()
        
        print("\nTop Subreddits:")
        for subreddit, count in subreddit_counts:
            print(f"  - r/{subreddit}: {count}")

def show_recent_posts(limit=5):
    """Show recent posts from database."""
    print(f"\n📝 {limit} Most Recent Posts")
    print("=" * 50)
    
    with db_manager.get_session() as db:
        posts = db.execute(text("""
            SELECT 
                platform,
                author,
                content,
                score,
                subreddit,
                created_at,
                scraped_at
            FROM scraped_posts 
            ORDER BY scraped_at DESC 
            LIMIT :limit
        """), {"limit": limit}).fetchall()
        
        for i, post in enumerate(posts, 1):
            print(f"\n{i}. [{post.platform}] {post.content[:60]}...")
            print(f"   👤 Author: {post.author}")
            if post.subreddit:
                print(f"   📍 Subreddit: r/{post.subreddit}")
            print(f"   📊 Score: {post.score}")
            print(f"   📅 Created: {post.created_at}")
            print(f"   🕐 Scraped: {post.scraped_at}")

def search_posts(query, limit=5):
    """Search posts in database."""
    print(f"\n🔍 Search Results for '{query}'")
    print("=" * 50)
    
    with db_manager.get_session() as db:
        posts = db.execute(text("""
            SELECT 
                platform,
                author,
                content,
                score,
                subreddit,
                url
            FROM scraped_posts 
            WHERE content LIKE :query 
            ORDER BY score DESC 
            LIMIT :limit
        """), {"query": f"%{query}%", "limit": limit}).fetchall()
        
        if not posts:
            print("No posts found matching your query.")
            return
        
        for i, post in enumerate(posts, 1):
            print(f"\n{i}. {post.content[:80]}...")
            print(f"   👤 Author: {post.author}")
            if post.subreddit:
                print(f"   📍 Subreddit: r/{post.subreddit}")
            print(f"   📊 Score: {post.score}")
            print(f"   🔗 URL: {post.url}")

def export_to_json(filename="exported_posts.json", limit=100):
    """Export posts to JSON file."""
    import json
    from datetime import datetime
    
    print(f"\n💾 Exporting {limit} posts to {filename}")
    print("=" * 50)
    
    with db_manager.get_session() as db:
        posts = db.execute(text("""
            SELECT 
                platform,
                author,
                content,
                score,
                subreddit,
                url,
                created_at,
                scraped_at
            FROM scraped_posts 
            ORDER BY scraped_at DESC 
            LIMIT :limit
        """), {"limit": limit}).fetchall()
        
        # Convert to list of dictionaries
        posts_data = []
        for post in posts:
            posts_data.append({
                "platform": post.platform,
                "author": post.author,
                "content": post.content,
                "score": post.score,
                "subreddit": post.subreddit,
                "url": post.url,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "scraped_at": post.scraped_at.isoformat() if post.scraped_at else None
            })
        
        # Write to JSON file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(posts_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Exported {len(posts_data)} posts to {filename}")

def interactive_database_explorer():
    """Interactive database explorer."""
    print("🔍 Interactive Database Explorer")
    print("=" * 50)
    print("Commands:")
    print("  1. stats    - Show database statistics")
    print("  2. recent   - Show recent posts")
    print("  3. search   - Search posts")
    print("  4. export   - Export posts to JSON")
    print("  5. sql      - Execute custom SQL query")
    print("  6. quit     - Exit")
    
    while True:
        try:
            command = input("\n> ").strip().lower()
            
            if command == "quit" or command == "q":
                break
            elif command == "stats" or command == "1":
                show_database_stats()
            elif command == "recent" or command == "2":
                limit = input("How many posts? (default 5): ").strip()
                limit = int(limit) if limit.isdigit() else 5
                show_recent_posts(limit)
            elif command == "search" or command == "3":
                query = input("Search query: ").strip()
                if query:
                    search_posts(query)
            elif command == "export" or command == "4":
                filename = input("Filename (default: exported_posts.json): ").strip()
                filename = filename if filename else "exported_posts.json"
                limit = input("How many posts? (default 100): ").strip()
                limit = int(limit) if limit.isdigit() else 100
                export_to_json(filename, limit)
            elif command == "sql" or command == "5":
                query = input("SQL query: ").strip()
                if query:
                    execute_custom_query(query)
            else:
                print("Unknown command. Type 'quit' to exit.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

def execute_custom_query(query):
    """Execute custom SQL query."""
    try:
        with db_manager.get_session() as db:
            result = db.execute(text(query))
            
            if query.strip().upper().startswith('SELECT'):
                rows = result.fetchall()
                if rows:
                    # Print column headers
                    if hasattr(result, 'keys'):
                        headers = result.keys()
                        print(" | ".join(headers))
                        print("-" * (len(" | ".join(headers))))
                    
                    # Print rows
                    for row in rows[:20]:  # Limit to 20 rows
                        print(" | ".join(str(col) for col in row))
                    
                    if len(rows) > 20:
                        print(f"... and {len(rows) - 20} more rows")
                else:
                    print("No results found.")
            else:
                print("Query executed successfully.")
                
    except Exception as e:
        print(f"❌ SQL Error: {e}")

if __name__ == "__main__":
    print("🗄️ Database Access Tool")
    print("=" * 50)
    
    # Initialize database
    db_manager.create_tables()
    
    # Show quick stats
    show_database_stats()
    show_recent_posts(3)
    
    # Start interactive explorer
    print("\n" + "="*50)
    interactive_database_explorer()
