# Web Scraper for Reddit and X (Twitter)

A performant, scalable, and reliable web scraper built with Python that can scrape data from Reddit and Twitter/X platforms.

## Features

- 🚀 **Async/Await Architecture** - High performance concurrent scraping
- 🔄 **Rate Limiting** - Built-in rate limiting to respect API limits
- 🔧 **Retry Logic** - Automatic retry with exponential backoff
- 💾 **Database Storage** - SQLAlchemy ORM with SQLite/PostgreSQL support
- 📊 **Structured Data** - Pydantic models for data validation
- 🎯 **Keyword Filtering** - Filter posts by keywords
- 💬 **Comments Support** - Scrape comments and replies
- 🏥 **Health Monitoring** - Health checks and error tracking
- 🎨 **Rich CLI** - Beautiful command-line interface
- 📈 **Job Management** - Background job processing

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd web-scrapper
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API credentials
```

5. Initialize the database:
```bash
python main.py setup
```

## Configuration

### Reddit API Setup
1. Go to https://www.reddit.com/prefs/apps
2. Create a new application (script type)
3. Add credentials to `.env`:
```bash
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=WebScraper/1.0 by YourUsername
```

### Twitter API Setup
1. Apply for Twitter Developer Account at https://developer.twitter.com
2. Create a new app and get API keys
3. Add credentials to `.env`:
```bash
TWITTER_BEARER_TOKEN=your_bearer_token
# OR for OAuth 1.0a
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
```

## Usage

### Command Line Interface

#### Scrape Reddit Subreddit
```bash
# Basic subreddit scraping
python main.py scrape-reddit python --max-posts 100

# Include comments and filter by keywords
python main.py scrape-reddit machinelearning --max-posts 50 --comments --keywords "pytorch,tensorflow" --wait

# Wait for completion and see results
python main.py scrape-reddit datascience --max-posts 25 --wait
```

#### Scrape Twitter/X
```bash
# Scrape user timeline
python main.py scrape-twitter @elonmusk --max-posts 50

# Search by hashtag
python main.py scrape-twitter "#AI" --max-posts 100 --keywords "machine learning,deep learning"

# Search query
python main.py scrape-twitter "python programming" --max-posts 75
```

#### Job Management
```bash
# List all jobs
python main.py list-jobs

# Check job status
python main.py job-status <job-id>

# Stop running job
python main.py stop-job <job-id>
```

#### View Data
```bash
# Show scraped posts
python main.py show-posts --platform reddit --limit 20

# Filter by author
python main.py show-posts --author "username" --limit 10

# Filter by subreddit
python main.py show-posts --subreddit "python" --limit 15
```

#### Export Data
```bash
# Export to JSON
python main.py export --format json --output reddit_data --platform reddit

# Export to CSV
python main.py export --format csv --output twitter_data --platform twitter --limit 500
```

#### Health Check
```bash
python main.py health
```

### Programmatic Usage

```python
import asyncio
from src.scrapers.manager import scraper_manager
from src.models import Platform
from src.database import db_manager

async def scrape_example():
    # Initialize database
    db_manager.create_tables()
    
    async with scraper_manager:
        # Scrape Reddit subreddit
        job_id = await scraper_manager.scrape_reddit_subreddit(
            subreddit="python",
            max_posts=100,
            include_comments=True
        )
        
        # Check job status
        status = await scraper_manager.get_job_status(job_id)
        print(f"Job status: {status}")
        
        # Get scraped posts
        posts = await scraper_manager.get_scraped_posts(
            platform=Platform.REDDIT,
            limit=10
        )
        
        for post in posts:
            print(f"[{post['author']}] {post['content'][:100]}")

asyncio.run(scrape_example())
```

## Architecture

### Project Structure
```
web-scrapper/
├── src/
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── models.py           # Pydantic data models
│   ├── database.py         # SQLAlchemy database models
│   ├── cli.py             # Command-line interface
│   └── scrapers/
│       ├── __init__.py
│       ├── base.py        # Base scraper class
│       ├── reddit_scraper.py   # Reddit implementation
│       ├── twitter_scraper.py  # Twitter implementation
│       └── manager.py     # Scraper orchestrator
├── examples/
│   └── basic_usage.py     # Usage examples
├── logs/                  # Log files
├── main.py               # Main entry point
├── requirements.txt      # Dependencies
├── .env.example         # Environment template
└── README.md
```

### Key Components

**Models (models.py)**
- `ScrapedPost`: Base model for all posts
- `RedditPost`: Reddit-specific fields
- `TwitterPost`: Twitter-specific fields
- `ScrapingJob`: Job configuration
- `ScrapingResult`: Job results

**Scrapers**
- `BaseScraper`: Abstract base with rate limiting and retry logic
- `RedditScraper`: Reddit API integration using PRAW
- `TwitterScraper`: Twitter API v2 integration using Tweepy
- `ScraperManager`: Orchestrates multiple scrapers

**Database**
- SQLAlchemy ORM with support for SQLite and PostgreSQL
- Async-ready with connection pooling
- Automatic table creation and migrations

## Performance Features

- **Async I/O**: Non-blocking concurrent requests
- **Rate Limiting**: Configurable per-platform rate limits
- **Connection Pooling**: Efficient database connections
- **Retry Logic**: Exponential backoff for failed requests
- **Memory Efficient**: Streaming data processing
- **Background Jobs**: Non-blocking job execution

## Monitoring

- **Health Checks**: Monitor scraper availability
- **Structured Logging**: JSON logs with rotation
- **Error Tracking**: Comprehensive error handling
- **Job Status**: Real-time job monitoring
- **Metrics**: Request counts and success rates

## Configuration Options

Environment variables in `.env`:
- `MAX_CONCURRENT_REQUESTS`: Concurrent request limit (default: 10)
- `REQUEST_DELAY`: Delay between requests in seconds (default: 1.0)
- `RETRY_ATTEMPTS`: Max retry attempts (default: 3)
- `RATE_LIMIT_REQUESTS`: Requests per window (default: 60)
- `RATE_LIMIT_WINDOW`: Rate limit window in seconds (default: 60)
- `LOG_LEVEL`: Logging level (default: INFO)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Disclaimer

This tool is for educational and research purposes. Always respect the terms of service of the platforms you're scraping and follow ethical scraping practices. Be mindful of rate limits and don't overload servers.
