import pytest
from unittest.mock import MagicMock
from scrapy.spiders import Spider
from scrapy.utils.project import get_project_settings
from zen_prompt.pipelines import SQLitePipeline


class MockSpider(Spider):
    name = "mock"
    settings = get_project_settings()


@pytest.fixture
def pipeline(tmp_path):
    db_path = str(tmp_path / "test_pipeline.db")

    # Mock crawler and settings
    mock_crawler = MagicMock()
    mock_crawler.settings = get_project_settings()
    mock_crawler.settings.set("DB_PATH", db_path)
    mock_crawler.spider = MockSpider()

    pipeline = SQLitePipeline.from_crawler(mock_crawler)
    pipeline.open_spider()
    yield pipeline
    pipeline.close_spider()


def test_pipeline_save_quote(pipeline):
    item = {
        "text": "Test quote",
        "author": "Author",
        "book_title": "Book",
        "tags": ["tag1"],
        "page": 1,
        "tag_url": "http://example.com",
    }
    pipeline.process_item(item)

    cursor = pipeline.conn.cursor()
    cursor.execute("SELECT text FROM quotes")
    assert cursor.fetchone()[0] == "Test quote"


def test_pipeline_update_state(pipeline):
    item = {"type": "crawl_state", "tag_url": "http://example.com/tag", "page": 5}
    pipeline.process_item(item)

    cursor = pipeline.conn.cursor()
    cursor.execute("SELECT last_page_processed FROM crawl_state")
    assert cursor.fetchone()[0] == 5
