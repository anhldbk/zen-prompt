import sqlite3
from scrapy.exceptions import DropItem
from pydantic import ValidationError
from .models import Quote
from .db import init_db, save_quote, update_crawl_state


class SQLitePipeline:
    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.crawler = crawler
        return pipeline

    def open_spider(self):
        # Use settings from crawler
        settings = self.crawler.settings
        db_path = settings.get("DB_PATH", "quotes.db")
        init_db(db_path)
        self.conn = sqlite3.connect(db_path)
        self.item_count = 0
        self.total_processed = 0

    def close_spider(self):
        if hasattr(self, "conn"):
            self.conn.close()

    def process_item(self, item):
        # Handle crawl state items
        if item.get("type") == "crawl_state":
            tag_url = item["tag_url"]
            page = item["page"]
            update_crawl_state(self.conn, tag_url, page)
            print(
                f"\r[Page {page}] {tag_url} | New: {self.item_count} | Total: {self.total_processed}\033[K",
                end="",
                flush=True,
            )
            return item

        # Handle quote items
        try:
            # Drop the Scrapy internal metadata before Pydantic validation
            quote_data = {k: v for k, v in item.items() if k in Quote.model_fields}
            quote = Quote(**quote_data)
            saved = save_quote(self.conn, quote)

            self.total_processed += 1
            if saved:
                self.item_count += 1

            # Update for every item to make it feel alive
            print(
                f"\rNew: {self.item_count} | Total: {self.total_processed} items collected...\033[K",
                end="",
                flush=True,
            )

            return item
        except ValidationError as e:
            raise DropItem(f"Invalid quote item: {e}")
        except Exception as e:
            if hasattr(self, "crawler") and self.crawler.spider:
                self.crawler.spider.logger.error(f"Error processing item: {e}")
            raise DropItem(f"Error processing item: {e}")
