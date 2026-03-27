import scrapy
from scrapy.http import HtmlResponse, Request
from zen_prompt.spider import GoodreadsQuotesSpider


def test_spider_init_with_tags():
    spider = GoodreadsQuotesSpider(tags="inspirational,life")
    assert spider.tags == ["inspirational", "life"]


def test_spider_init_default():
    spider = GoodreadsQuotesSpider()
    assert spider.tags == []


def test_parse_zen_prompt():
    spider = GoodreadsQuotesSpider()
    html = """
    <div class="quote">
        <div class="quoteDetails">
            <div class="quoteText">
                “Quote 1 text”
                <br>  ―
                <span class="authorOrTitle">
                    Author 1
                </span>
            </div>
            <div class="quoteFooter">
                <div class="greyText smallText left">
                                        tags:
                                        <a href="/zen_prompt/tag/tag1">tag1</a>,
                                        <a href="/zen_prompt/tag/tag2">tag2</a>
                </div>
                <div class="right">
                    <a class="smallText" href="/quotes/1-quote-1">1,234 likes</a>
                </div>
            </div>
        </div>
    </div>
    <div class="quote">
        <div class="quoteDetails">
            <div class="quoteText">
                “Quote 2 text”
                <br>  ―
                <span class="authorOrTitle">
                    Author 2
                </span>
                <a class="authorOrTitle" href="/book/show/123">Book Title 2</a>
            </div>
            <div class="quoteFooter">
                <div class="greyText smallText left">
                                        tags:
                                        <a href="/zen_prompt/tag/tag3">tag3</a>
                </div>
                <div class="right">
                    <a class="smallText" href="/quotes/2-quote-2">567 likes</a>
                </div>
            </div>
        </div>
    </div>
    <div class="pagination">
        <a class="next_page" href="/zen_prompt/tag/inspirational?page=2">Next</a>
    </div>
    """
    request = Request(
        url="https://www.goodreads.com/zen_prompt/tag/inspirational",
        meta={
            "tag_url": "https://www.goodreads.com/zen_prompt/tag/inspirational",
            "page": 1,
        },
    )
    response = HtmlResponse(
        url="https://www.goodreads.com/zen_prompt/tag/inspirational",
        body=html,
        encoding="utf-8",
        request=request,
    )

    results = list(spider.parse(response))

    # Extract only quote items (ignore state updates)
    zen_prompt = [
        r for r in results if isinstance(r, dict) and r.get("type") != "crawl_state"
    ]

    assert len(zen_prompt) == 2
    assert zen_prompt[0]["text"] == "Quote 1 text"
    assert zen_prompt[0]["author"] == "Author 1"
    assert zen_prompt[0]["book_title"] is None
    assert zen_prompt[0]["tags"] == ["tag1", "tag2"]
    assert zen_prompt[0]["likes"] == 1234
    assert zen_prompt[0]["link"] == "https://www.goodreads.com/quotes/1-quote-1"

    assert zen_prompt[1]["text"] == "Quote 2 text"
    assert zen_prompt[1]["author"] == "Author 2"
    assert zen_prompt[1]["book_title"] == "Book Title 2"
    assert zen_prompt[1]["tags"] == ["tag3"]
    assert zen_prompt[1]["likes"] == 567
    assert zen_prompt[1]["link"] == "https://www.goodreads.com/quotes/2-quote-2"


def test_parse_multi_line_quote():
    spider = GoodreadsQuotesSpider()
    html = """
    <div class="quote">
        <div class="quoteText">
            &ldquo;Line 1<br />Line 2<br />Line 3&rdquo;
            <br />
            ―
            <span class="authorOrTitle">Author</span>
        </div>
    </div>
    """
    request = Request(
        url="https://www.goodreads.com/tag/test", meta={"tag_url": "test", "page": 1}
    )
    response = HtmlResponse(url="test", body=html, encoding="utf-8", request=request)

    results = list(spider.parse(response))
    items = [
        r for r in results if isinstance(r, dict) and r.get("type") != "crawl_state"
    ]

    assert len(items) == 1
    assert items[0]["text"] == "Line 1\nLine 2\nLine 3"
    assert items[0]["author"] == "Author"


def test_pagination_logic():
    spider = GoodreadsQuotesSpider()
    html = """
    <div class="pagination">
        <a class="next_page" href="/zen_prompt/tag/inspirational?page=2">Next</a>
    </div>
    """
    request = Request(
        url="https://www.goodreads.com/zen_prompt/tag/inspirational",
        meta={
            "tag_url": "https://www.goodreads.com/zen_prompt/tag/inspirational",
            "page": 1,
        },
    )
    response = HtmlResponse(
        url="https://www.goodreads.com/zen_prompt/tag/inspirational",
        body=html,
        encoding="utf-8",
        request=request,
    )

    results = list(spider.parse(response))
    requests = [r for r in results if isinstance(r, scrapy.Request)]

    assert len(requests) == 1
    assert "page=2" in requests[0].url
    assert requests[0].meta["page"] == 2
    assert (
        requests[0].meta["tag_url"]
        == "https://www.goodreads.com/zen_prompt/tag/inspirational"
    )


def test_spider_init_with_url():
    spider = GoodreadsQuotesSpider(
        url="https://www.goodreads.com/author/zen_prompt/123"
    )
    assert spider.url == "https://www.goodreads.com/author/zen_prompt/123"
