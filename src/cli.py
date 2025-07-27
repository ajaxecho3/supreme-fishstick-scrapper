"""
Command Line Interface for the web scraper.
"""
import asyncio
import json
from typing import Optional, List
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint

from .models import Platform, ScrapingStrategy
from .database import db_manager
from .scrapers.manager import scraper_manager

app = typer.Typer(help="🕷️ Web Scraper for Reddit and Twitter/X")
console = Console()


@app.command()
def setup():
    """Initialize the database and create tables."""
    try:
        db_manager.create_tables()
        rprint("✅ [green]Database tables created successfully![/green]")
    except Exception as e:
        rprint(f"❌ [red]Error setting up database: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command() 
def scrape_reddit(
    subreddit: str = typer.Argument(..., help="Subreddit name (without r/)"),
    max_posts: int = typer.Option(100, "--max-posts", "-n", help="Maximum number of posts to scrape"),
    strategy: str = typer.Option("web", "--strategy", "-s", help="Scraping strategy: api/web/feed/browser"),
    include_comments: bool = typer.Option(False, "--comments", "-c", help="Include comments"),
    keywords: Optional[str] = typer.Option(None, "--keywords", "-k", help="Comma-separated keywords to filter by"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for job completion")
):
    """Scrape posts from a Reddit subreddit with configurable strategy."""
    
    async def run_scrape():
        # Validate strategy
        try:
            strategy_enum = ScrapingStrategy(strategy.lower())
        except ValueError:
            rprint(f"❌ [red]Invalid strategy: {strategy}. Use: api, web, feed, or browser[/red]")
            return
            
        keyword_list = keywords.split(",") if keywords else None
        
        async with scraper_manager:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Scraping r/{subreddit} with {strategy} strategy...", total=None)
                
                try:
                    posts = await scraper_manager.scrape_with_fallback(
                        platform=Platform.REDDIT,
                        target=subreddit,
                        max_posts=max_posts,
                        preferred_strategy=strategy_enum
                    )
                    
                    progress.update(task, description="Saving posts to database...")
                    
                    # Save posts to database
                    posts_saved = 0
                    for post in posts:
                        try:
                            db_manager.save_post(post.model_dump())
                            posts_saved += 1
                        except Exception as e:
                            rprint(f"⚠️ [yellow]Error saving post {post.id}: {e}[/yellow]")
                    
                    progress.update(task, description="Complete!")
                    
                    rprint(f"✅ [green]Successfully scraped {len(posts)} posts from r/{subreddit}![/green]")
                    rprint(f"💾 [blue]Saved {posts_saved} posts to database[/blue]")
                    rprint(f"� [cyan]Strategy used: {strategy}[/cyan]")
                    
                    # Show sample posts
                    if posts:
                        rprint("\n📝 [bold]Sample posts:[/bold]")
                        for i, post in enumerate(posts[:3]):
                            rprint(f"  {i+1}. {post.content[:100]}..." if len(post.content) > 100 else f"  {i+1}. {post.content}")
                    
                except Exception as e:
                    rprint(f"❌ [red]Scraping failed: {e}[/red]")
                    
    asyncio.run(run_scrape())


@app.command()
def scrape_twitter(
    target: str = typer.Argument(..., help="Username (@user), hashtag (#tag), or search query"),
    max_posts: int = typer.Option(100, "--max-posts", "-n", help="Maximum number of posts to scrape"),
    include_comments: bool = typer.Option(False, "--comments", "-c", help="Include replies"),
    keywords: Optional[str] = typer.Option(None, "--keywords", "-k", help="Comma-separated keywords to filter by"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for job completion")
):
    """Scrape posts from Twitter/X."""
    
    async def run_scrape():
        keyword_list = keywords.split(",") if keywords else None
        
        async with scraper_manager:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Creating job for {target}...", total=None)
                
                job_id = await scraper_manager.create_job(
                    platform=Platform.TWITTER,
                    target=target,
                    max_posts=max_posts,
                    include_comments=include_comments,
                    keywords=keyword_list
                )
                
                progress.update(task, description=f"Starting scraping job {job_id}...")
                await scraper_manager.start_job(job_id)
                
                rprint(f"✅ [green]Started Twitter scraping job: {job_id}[/green]")
                
                if wait:
                    progress.update(task, description="Waiting for job completion...")
                    while True:
                        status = await scraper_manager.get_job_status(job_id)
                        if status and status['status'] in ['completed', 'failed', 'cancelled']:
                            break
                        await asyncio.sleep(2)
                    
                    progress.update(task, description="Job completed!")
                    
                    # Show results
                    if status['success']:
                        rprint(f"🎉 [green]Job completed successfully![/green]")
                        rprint(f"📊 Posts scraped: {status['posts_scraped']}")
                        rprint(f"💬 Comments scraped: {status['comments_scraped']}")
                    else:
                        rprint(f"❌ [red]Job failed[/red]")
                        if status.get('errors'):
                            for error in status['errors'][:5]:  # Show first 5 errors
                                rprint(f"  • {error}")
    
    asyncio.run(run_scrape())


@app.command()
def list_jobs():
    """List all scraping jobs."""
    
    async def run_list():
        async with scraper_manager:
            # Get active jobs
            active_jobs = await scraper_manager.list_active_jobs()
            
            # Get all jobs from database
            with db_manager.get_session() as db:
                from .database import ScrapingJobDB
                jobs = db.query(ScrapingJobDB).order_by(ScrapingJobDB.created_at.desc()).limit(20).all()
            
            if not jobs:
                rprint("[yellow]No jobs found.[/yellow]")
                return
                
            table = Table(title="Scraping Jobs")
            table.add_column("Job ID", style="cyan", no_wrap=True)
            table.add_column("Platform", style="magenta")
            table.add_column("Target", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Posts", justify="right")
            table.add_column("Comments", justify="right")
            table.add_column("Created", style="blue")
            
            for job in jobs:
                status = job.status
                if job.job_id in active_jobs:
                    status = f"🔄 {status}"
                elif job.success:
                    status = f"✅ {status}"
                elif job.status == "failed":
                    status = f"❌ {status}"
                    
                table.add_row(
                    job.job_id[:8] + "...",
                    job.platform,
                    job.target[:20] + "..." if len(job.target) > 20 else job.target,
                    status,
                    str(job.posts_scraped),
                    str(job.comments_scraped),
                    job.created_at.strftime("%m/%d %H:%M")
                )
            
            console.print(table)
    
    asyncio.run(run_list())


@app.command()
def job_status(
    job_id: str = typer.Argument(..., help="Job ID to check")
):
    """Get detailed status of a specific job."""
    
    async def run_status():
        async with scraper_manager:
            status = await scraper_manager.get_job_status(job_id)
            
            if not status:
                rprint(f"❌ [red]Job {job_id} not found[/red]")
                return
                
            # Create status panel
            status_text = f"""
[bold]Job ID:[/bold] {status['job_id']}
[bold]Platform:[/bold] {status['platform']}
[bold]Target:[/bold] {status['target']}
[bold]Status:[/bold] {status['status']}
[bold]Running:[/bold] {"Yes" if status['is_running'] else "No"}

[bold]Created:[/bold] {status['created_at']}
[bold]Started:[/bold] {status['started_at'] or 'Not started'}
[bold]Completed:[/bold] {status['completed_at'] or 'Not completed'}

[bold]Posts Scraped:[/bold] {status['posts_scraped']}
[bold]Comments Scraped:[/bold] {status['comments_scraped']}
[bold]Success:[/bold] {status['success']}
            """
            
            console.print(Panel(status_text, title="Job Status", border_style="blue"))
            
            if status.get('errors'):
                error_text = "\n".join(f"• {error}" for error in status['errors'][:10])
                console.print(Panel(error_text, title="Errors", border_style="red"))
    
    asyncio.run(run_status())


@app.command()
def stop_job(
    job_id: str = typer.Argument(..., help="Job ID to stop")
):
    """Stop a running job."""
    
    async def run_stop():
        async with scraper_manager:
            success = await scraper_manager.stop_job(job_id)
            
            if success:
                rprint(f"✅ [green]Successfully stopped job {job_id}[/green]")
            else:
                rprint(f"❌ [red]Job {job_id} is not running or not found[/red]")
    
    asyncio.run(run_stop())


@app.command()
def show_posts(
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Filter by platform (reddit/twitter)"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Filter by author"),
    subreddit: Optional[str] = typer.Option(None, "--subreddit", "-s", help="Filter by subreddit"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of posts to show")
):
    """Show scraped posts."""
    
    async def run_show():
        platform_enum = None
        if platform:
            try:
                platform_enum = Platform(platform.lower())
            except ValueError:
                rprint(f"❌ [red]Invalid platform: {platform}. Use 'reddit' or 'twitter'.[/red]")
                return
        
        async with scraper_manager:
            posts = await scraper_manager.get_scraped_posts(
                platform=platform_enum,
                limit=limit,
                author=author,
                subreddit=subreddit
            )
            
            if not posts:
                rprint("[yellow]No posts found.[/yellow]")
                return
                
            table = Table(title=f"Scraped Posts ({len(posts)} results)")
            table.add_column("Platform", style="magenta", width=8)
            table.add_column("Author", style="cyan", width=15)
            table.add_column("Content", style="white", width=50)
            table.add_column("Score/Likes", justify="right", width=10)
            table.add_column("Scraped", style="blue", width=12)
            
            for post in posts:
                score_likes = str(post.get('score') or post.get('likes') or 0)
                
                table.add_row(
                    post['platform'][:7],
                    post['author'][:14],
                    post['content'][:47] + "..." if len(post['content']) > 47 else post['content'],
                    score_likes,
                    post['scraped_at'].strftime("%m/%d %H:%M")
                )
            
            console.print(table)
    
    asyncio.run(run_show())


@app.command()
def health():
    """Check health status of all scrapers."""
    
    async def run_health():
        async with scraper_manager:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Checking scraper health...", total=None)
                
                health_status = await scraper_manager.health_check()
                
                progress.stop()
                
                table = Table(title="Scraper Health Status")
                table.add_column("Platform", style="cyan")
                table.add_column("Status", style="green")
                
                for platform, is_healthy in health_status.items():
                    status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
                    table.add_row(platform.title(), status)
                
                console.print(table)
    
    asyncio.run(run_health())


@app.command()
def strategies():
    """Show available scraping strategies for each platform."""
    
    async def run_strategies():
        async with scraper_manager:
            strategy_info = await scraper_manager.get_strategy_info()
            
            if not strategy_info:
                rprint("[yellow]No strategies available.[/yellow]")
                return
                
            for platform, info in strategy_info.items():
                console.print(f"\n[bold magenta]{platform.value.upper()} Strategies:[/bold magenta]")
                
                table = Table()
                table.add_column("Strategy", style="cyan")
                table.add_column("Requires Auth", style="yellow")
                table.add_column("Supports Search", style="green")
                table.add_column("Supports Comments", style="blue")
                table.add_column("Class", style="white")
                
                for strategy, details in info['strategy_details'].items():
                    table.add_row(
                        details['name'],
                        "✅" if details['requires_auth'] else "❌",
                        "✅" if details['supports_search'] else "❌",
                        "✅" if details['supports_comments'] else "❌",
                        details['class']
                    )
                
                console.print(table)
    
    asyncio.run(run_strategies())


@app.command()
def search_reddit(
    query: str = typer.Argument(..., help="Search query"),
    max_posts: int = typer.Option(50, "--max-posts", "-n", help="Maximum number of posts to find"),
    strategy: str = typer.Option("web", "--strategy", "-s", help="Scraping strategy: api/web/feed"),
    subreddit: Optional[str] = typer.Option(None, "--subreddit", "-r", help="Limit search to specific subreddit")
):
    """Search Reddit posts with configurable strategy."""
    
    async def run_search():
        try:
            strategy_enum = ScrapingStrategy(strategy.lower())
        except ValueError:
            rprint(f"❌ [red]Invalid strategy: {strategy}. Use: api, web, or feed[/red]")
            return
            
        async with scraper_manager:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Searching Reddit for '{query}'...", total=None)
                
                try:
                    posts = await scraper_manager.scrape_search_with_fallback(
                        platform=Platform.REDDIT,
                        query=query,
                        max_posts=max_posts,
                        preferred_strategy=strategy_enum,
                        subreddit=subreddit
                    )
                    
                    progress.update(task, description="Saving results...")
                    
                    # Save posts to database
                    posts_saved = 0
                    for post in posts:
                        try:
                            db_manager.save_post(post.model_dump())
                            posts_saved += 1
                        except Exception as e:
                            rprint(f"⚠️ [yellow]Error saving post {post.id}: {e}[/yellow]")
                    
                    progress.update(task, description="Complete!")
                    
                    rprint(f"✅ [green]Found {len(posts)} posts matching '{query}'![/green]")
                    rprint(f"💾 [blue]Saved {posts_saved} posts to database[/blue]")
                    
                    # Show sample results
                    if posts:
                        rprint("\n🔍 [bold]Search results:[/bold]")
                        for i, post in enumerate(posts[:5]):
                            content = post.content[:80] + "..." if len(post.content) > 80 else post.content
                            rprint(f"  {i+1}. [r/{post.subreddit}] {content}")
                            rprint(f"     👤 u/{post.author} | 👍 {post.score} | 💬 {post.replies}")
                    
                except Exception as e:
                    rprint(f"❌ [red]Search failed: {e}[/red]")
                    
    asyncio.run(run_search())


@app.command()
def test_strategy(
    platform: str = typer.Argument(..., help="Platform to test (reddit/twitter)"),
    strategy: str = typer.Argument(..., help="Strategy to test (api/web/feed/browser)"),
    target: str = typer.Option("python", "--target", "-t", help="Target to test with (subreddit, username, etc.)")
):
    """Test a specific scraping strategy."""
    
    async def run_test():
        try:
            platform_enum = Platform(platform.lower())
            strategy_enum = ScrapingStrategy(strategy.lower())
        except ValueError as e:
            rprint(f"❌ [red]Invalid parameter: {e}[/red]")
            return
            
        async with scraper_manager:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Testing {strategy} strategy for {platform}...", total=None)
                
                try:
                    # Check if strategy is available
                    available_strategies = await scraper_manager.get_available_strategies(platform_enum)
                    
                    if strategy_enum not in available_strategies:
                        rprint(f"❌ [red]Strategy '{strategy}' not available for {platform}[/red]")
                        rprint(f"Available strategies: {[s.value for s in available_strategies]}")
                        return
                    
                    # Test with just 5 posts
                    posts = await scraper_manager.scrape_with_fallback(
                        platform=platform_enum,
                        target=target,
                        max_posts=5,
                        preferred_strategy=strategy_enum
                    )
                    
                    progress.update(task, description="Test complete!")
                    
                    if posts:
                        rprint(f"✅ [green]Strategy '{strategy}' working! Got {len(posts)} test posts[/green]")
                        
                        # Show first post as example
                        sample_post = posts[0]
                        rprint(f"\n📝 [bold]Sample post:[/bold]")
                        rprint(f"  👤 Author: {sample_post.author}")
                        rprint(f"  📅 Created: {sample_post.created_at}")
                        rprint(f"  📊 Score: {sample_post.score}")
                        rprint(f"  📄 Content: {sample_post.content[:100]}...")
                    else:
                        rprint(f"⚠️ [yellow]Strategy '{strategy}' available but returned no posts[/yellow]")
                    
                except Exception as e:
                    rprint(f"❌ [red]Strategy '{strategy}' failed: {e}[/red]")
                    
    asyncio.run(run_test())


@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", help="Export format (json, csv)"),
    output: str = typer.Option("scraped_data", "--output", "-o", help="Output filename (without extension)"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Filter by platform"),
    limit: int = typer.Option(1000, "--limit", "-l", help="Maximum number of posts to export")
):
    """Export scraped data to file."""
    
    async def run_export():
        platform_enum = None
        if platform:
            try:
                platform_enum = Platform(platform.lower())
            except ValueError:
                rprint(f"❌ [red]Invalid platform: {platform}[/red]")
                return
        
        async with scraper_manager:
            posts = await scraper_manager.get_scraped_posts(
                platform=platform_enum,
                limit=limit
            )
            
            if not posts:
                rprint("[yellow]No posts to export.[/yellow]")
                return
            
            filename = f"{output}.{format}"
            
            if format.lower() == "json":
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(posts, f, indent=2, default=str)
            elif format.lower() == "csv":
                try:
                    import pandas as pd
                    df = pd.DataFrame(posts)
                    df.to_csv(filename, index=False)
                except ImportError:
                    rprint(f"❌ [red]Pandas not installed. Install with: pip install pandas[/red]")
                    return
            else:
                rprint(f"❌ [red]Unsupported format: {format}[/red]")
                return
                
            rprint(f"✅ [green]Exported {len(posts)} posts to {filename}[/green]")
    
    asyncio.run(run_export())


if __name__ == "__main__":
    app()
