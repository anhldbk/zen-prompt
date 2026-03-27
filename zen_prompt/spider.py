import scrapy
import sqlite3
from .db import init_db, get_crawl_state


class GoodreadsQuotesSpider(scrapy.Spider):
    name = "goodreads_quotes"

    def __init__(self, tags: str = None, url: str = None, *args, **kwargs):
        super(GoodreadsQuotesSpider, self).__init__(*args, **kwargs)
        self.tags = tags.split(",") if tags else []
        self.url = url

    async def start(self):
        db_path = self.settings.get("DB_PATH", "quotes.db")
        init_db(db_path)
        conn = sqlite3.connect(db_path)

        requests = []
        # Handle direct URL
        if self.url:
            last_page = get_crawl_state(conn, self.url)
            start_page = last_page + 1
            # Append page parameter if it's not already there
            sep = "&" if "?" in self.url else "?"
            url = f"{self.url}{sep}page={start_page}"
            requests.append(
                scrapy.Request(
                    url, self.parse, meta={"tag_url": self.url, "page": start_page}
                )
            )

        # Handle tags
        for tag in self.tags:
            tag_url = f"https://www.goodreads.com/quotes/tag/{tag}"
            last_page = get_crawl_state(conn, tag_url)
            start_page = last_page + 1
            url = f"{tag_url}?page={start_page}"
            requests.append(
                scrapy.Request(
                    url, self.parse, meta={"tag_url": tag_url, "page": start_page}
                )
            )

        conn.close()
        for req in requests:
            yield req

    def parse(self, response):
        tag_url = response.meta["tag_url"]
        current_page = response.meta["page"]

        for quote in response.css("div.quote"):
            # Text is in div.quoteText
            text_nodes = quote.css("div.quoteText::text").getall()

            # Extract all text before the dash (―)
            text_parts = []
            for node in text_nodes:
                node = node.strip()
                if not node:
                    continue
                # Stop if we hit the dash separator
                if node == "―" or node.startswith("―"):
                    break
                text_parts.append(node)

            text_raw = "\n".join(text_parts)

            # Author and Title have class="authorOrTitle"
            author = quote.css("span.authorOrTitle::text").get()
            book_title = quote.css("a.authorOrTitle::text").get()

            # Tags are usually in a specific div within or near footer
            tags = quote.css("div.greyText.smallText.left a::text").getall()

            # Extract likes and link from div.quoteFooter
            footer = quote.css("div.quoteFooter")
            likes_text = footer.css("div.right a.smallText::text").re_first(r"([\d,]+)")
            likes = int(likes_text.replace(",", "")) if likes_text else 0

            link_path = footer.css("div.right a.smallText::attr(href)").get()
            link = response.urljoin(link_path) if link_path else None

            if text_raw:
                # Clean text: remove leading/trailing whitespace and quotes
                text = text_raw.strip().strip("“").strip("”").strip()
                author = author.strip().strip(",") if author else "Unknown"
                book_title = book_title.strip() if book_title else None

                yield {
                    "text": text,
                    "author": author,
                    "book_title": book_title,
                    "tags": tags,
                    "likes": likes,
                    "link": link,
                    "page": current_page,
                    "tag_url": tag_url,
                }

        # Yield state update item after processing all quotes on the page
        yield {"type": "crawl_state", "tag_url": tag_url, "page": current_page}

        # Follow pagination
        next_page = response.css("a.next_page::attr(href)").get()
        if next_page:
            yield response.follow(
                next_page,
                self.parse,
                meta={"tag_url": tag_url, "page": current_page + 1},
            )
