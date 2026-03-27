import os
import typer
from typing import Optional
from scrapy.crawler import CrawlerProcess
from zen_prompt.spider import GoodreadsQuotesSpider
from zen_prompt.db import init_db


def crawl(
    working_dir: str = typer.Option(
        "docs/data/sqlite",
        "--working-dir",
        "-w",
        help="Working directory for data storage",
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Comma-separated tags to crawl"
    ),
    url: Optional[str] = typer.Option(
        None, "--url", "-u", help="A Goodreads URL (author, book title, etc.)"
    ),
    download_delay: float = typer.Option(
        1.0, "--download-delay", "-d", help="Download delay in seconds"
    ),
):
    """
    Run the Goodreads quotes crawler and store results in SQLite.
    """
    # If no tags or url provided, use default tags
    if not tags and not url:
        tags = "inspirational,motivational,buddhism"

    # Create working directory and initialize database
    if not os.path.exists(working_dir):
        os.makedirs(working_dir, exist_ok=True)

    db_path = os.path.abspath(os.path.join(working_dir, "quotes.db"))
    typer.echo(f"Initializing database at {db_path}...")
    init_db(db_path)

    # Configure Scrapy settings
    settings = {
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_DELAY": download_delay,
        "ITEM_PIPELINES": {
            "zen_prompt.pipelines.SQLitePipeline": 300,
        },
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "DB_PATH": db_path,
        "LOG_LEVEL": "WARNING",
        "ROBOTSTXT_OBEY": True,
    }

    if url:
        typer.echo(f"Starting crawl for URL: {url}...")
    if tags:
        typer.echo(f"Starting crawl for tags: {tags}...")

    process = CrawlerProcess(settings)
    process.crawl(GoodreadsQuotesSpider, tags=tags, url=url)
    process.start()
    typer.echo("\nCrawl completed successfully.")
