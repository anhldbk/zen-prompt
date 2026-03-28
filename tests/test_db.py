import sqlite3
import pytest
from zen_prompt.db import init_db, save_quote, get_crawl_state, update_crawl_state
from zen_prompt.models import Quote


@pytest.fixture
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_zen_prompt.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


def test_init_db(tmp_path):
    db_path = str(tmp_path / "init_test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    assert "quotes" in tables
    assert "crawl_state" in tables
    cursor.execute("PRAGMA table_info(quotes)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "char_count" in columns
    assert "word_count" in columns
    conn.close()


def test_save_quote(db_conn):
    quote = Quote(
        text="Test quote",
        author="Author",
        book_title="Book",
        tags=["tag1", "tag2"],
        likes=123,
        link="https://example.com/quote/1",
    )
    save_quote(db_conn, quote)

    cursor = db_conn.cursor()
    cursor.execute("SELECT text, author, tags, likes, link FROM quotes")
    row = cursor.fetchone()
    assert row[0] == "Test quote"
    assert row[1] == "Author"
    assert "tag1" in row[2]
    assert "tag2" in row[2]
    assert row[3] == 123
    assert row[4] == "https://example.com/quote/1"


def test_deduplication(db_conn):
    quote = Quote(text="Unique quote", author="Author", tags=[], likes=10)
    save_quote(db_conn, quote)
    save_quote(db_conn, quote)  # Should be ignored

    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM quotes")
    assert cursor.fetchone()[0] == 1


def test_create_subset_db_with_tag(tmp_path):
    from zen_prompt.db import create_subset_db, get_all_quotes

    src_db = str(tmp_path / "source.db")
    dst_db = str(tmp_path / "subset.db")

    init_db(src_db)
    conn = sqlite3.connect(src_db)

    # Save mixed quotes
    q1 = Quote(
        text="Buddhism quote", author="Author1", tags=["buddhism", "life"], likes=100
    )
    q2 = Quote(
        text="Inspirational quote", author="Author2", tags=["inspirational"], likes=50
    )
    save_quote(conn, q1)
    save_quote(conn, q2)
    conn.close()

    # Create subset for 'buddhism'
    create_subset_db(src_db, dst_db, limit=10, tag="buddhism")

    # Verify
    subset_conn = sqlite3.connect(dst_db)
    quotes_data = get_all_quotes(subset_conn)
    subset_conn.close()

    assert len(quotes_data) == 1
    assert quotes_data[0]["text"] == "Buddhism quote"
    assert "buddhism" in quotes_data[0]["tags"]
    assert quotes_data[0]["likes"] == 100


def test_crawl_state(db_conn):
    tag_url = "https://example.com/tag"
    update_crawl_state(db_conn, tag_url, 5)
    assert get_crawl_state(db_conn, tag_url) == 5

    update_crawl_state(db_conn, tag_url, 10)
    assert get_crawl_state(db_conn, tag_url) == 10


def test_photo_rotation_state(db_conn):
    from zen_prompt.db import get_rotation_state, update_rotation_state

    folder_path = "/path/to/photos"
    assert get_rotation_state(db_conn, folder_path) is None

    update_rotation_state(db_conn, folder_path, "photo1.jpg")
    assert get_rotation_state(db_conn, folder_path) == "photo1.jpg"

    update_rotation_state(db_conn, folder_path, "photo2.jpg")
    assert get_rotation_state(db_conn, folder_path) == "photo2.jpg"


def test_get_stats(db_conn):
    from zen_prompt.db import get_stats

    # Save test quotes
    quotes = [
        Quote(text="Short", author="Author A", tags=["tag1"], likes=10),
        Quote(text="Medium quote", author="Author A", tags=["tag1", "tag2"], likes=20),
        Quote(
            text="Very long quote text",
            author="Author B",
            tags=["tag2", "tag3"],
            likes=30,
        ),
    ]
    for q in quotes:
        save_quote(db_conn, q)

    stats = get_stats(db_conn)

    assert stats["total_quotes"] == 3
    assert stats["total_authors"] == 2
    assert stats["total_likes"] == 60
    assert stats["avg_length"] == sum(len(q.text) for q in quotes) / 3
    assert stats["min_length"] == 5  # "Short"
    assert stats["max_length"] == 20  # "Very long quote text"

    # Word counts
    assert stats["min_words"] == 1
    assert stats["max_words"] == 4

    # Check top authors
    assert stats["top_authors"][0]["author"] == "Author A"
    assert stats["top_authors"][0]["count"] == 2
    assert stats["top_authors"][0]["likes"] == 30

    # Check top liked quotes
    assert stats["top_liked_quotes"][0]["likes"] == 30
    assert stats["top_liked_quotes"][0]["author"] == "Author B"

    # IDs in longest/shortest
    assert "id" in stats["longest_quotes"][0]
    assert stats["longest_quotes"][0]["length"] == 20

    # Check top tags
    # tag1 and tag2 both have count 2, tag3 has count 1
    tags_dict = {t["tag"]: t["count"] for t in stats["top_tags"]}
    assert tags_dict["tag1"] == 2
    assert tags_dict["tag2"] == 2
    assert tags_dict["tag3"] == 1


def test_distill_quotes(db_conn):
    from zen_prompt.db import distill_quotes

    # Save test quotes
    quotes = [
        Quote(text="", author="Author A"),
        Quote(text="a", author="Author B"),
        Quote(text="Abc", author="Author C"),
        Quote(text="One word", author="Author D", likes=200),
        Quote(text="two words", author="Author E"),
        Quote(text="ALL UPPER", author="Author F"),
    ]
    for q in quotes:
        save_quote(db_conn, q)

    # Prune quotes with length < 1 (only the empty one)
    removed, updated = distill_quotes(db_conn, min_length=1)
    assert removed == 1

    # Prune quotes starting with lowercase ("a", "two words")
    removed, updated = distill_quotes(db_conn, remove_lowercase=True, min_length=0)
    assert removed == 2

    # Prune all uppercase ("ALL UPPER")
    removed, updated = distill_quotes(db_conn, remove_uppercase=True, min_length=0)
    assert removed == 1

    # Prune by word count < 2 (only "Abc" left among targets)
    # "Abc" is 1 word
    removed, updated = distill_quotes(db_conn, min_words=2, min_length=0)
    assert removed == 1

    # Prune by likes < 100 ("One word" has 200, so it stays)
    # But wait, we need another quote with low likes to test removal
    q_low_likes = Quote(text="Stay here", author="Author G", likes=10)
    save_quote(db_conn, q_low_likes)
    removed, updated = distill_quotes(db_conn, min_likes=100)
    assert removed == 1  # "Stay here" should be removed

    cursor = db_conn.cursor()
    cursor.execute("SELECT text FROM quotes")
    remaining = [r[0] for r in cursor.fetchall()]
    assert len(remaining) == 1
    assert remaining[0] == "One word"


def test_get_random_quote_with_min_likes(db_conn):
    from zen_prompt.db import get_random_quote, save_quote
    from zen_prompt.models import Quote

    # Save test quotes
    save_quote(db_conn, Quote(text="Popular", author="A", likes=1000))
    save_quote(db_conn, Quote(text="Unpopular", author="B", likes=10))

    # Fetch a quote with at least 1000 likes
    quote = get_random_quote(db_conn, min_likes=1000)
    assert quote is not None
    assert quote["likes"] >= 1000
    assert quote["text"] == "Popular"

    # Fetch with even higher threshold, should get nothing
    quote = get_random_quote(db_conn, min_likes=2000)
    assert quote is None


def test_get_random_quote_with_max_words_and_chars(db_conn):
    from zen_prompt.db import get_random_quote, save_quote
    from zen_prompt.models import Quote

    save_quote(db_conn, Quote(text="tiny quote", author="A", likes=10))
    save_quote(
        db_conn, Quote(text="this quote is definitely too long", author="B", likes=10)
    )

    quote = get_random_quote(db_conn, max_words=2)
    assert quote is not None
    assert quote["text"] == "tiny quote"

    quote = get_random_quote(db_conn, max_chars=10)
    assert quote is not None
    assert quote["text"] == "tiny quote"

    quote = get_random_quote(db_conn, max_words=1)
    assert quote is None


def test_init_db_backfills_length_columns_for_existing_schema(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash_id TEXT UNIQUE,
            text TEXT NOT NULL,
            author TEXT NOT NULL,
            book_title TEXT,
            tags TEXT,
            likes INTEGER DEFAULT 0,
            link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE crawl_state (
            tag_url TEXT PRIMARY KEY,
            last_page_processed INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        "INSERT INTO quotes (hash_id, text, author, tags, likes) VALUES (?, ?, ?, ?, ?)",
        ("legacy", "two words", "Author", "[]", 0),
    )
    conn.commit()
    conn.close()

    init_db(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT char_count, word_count FROM quotes WHERE hash_id = ?", ("legacy",)
    )
    row = cursor.fetchone()
    conn.close()

    assert row == (9, 2)
