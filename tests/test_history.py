import sqlite3
from datetime import datetime, timedelta
import pytest
from zen_prompt.db import init_db, save_quote, get_random_quote, record_history
from zen_prompt.models import Quote


@pytest.fixture
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_zen_prompt_history.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


def test_record_history(db_conn):
    # Save a quote first
    quote = Quote(text="Test quote", author="Author", tags=[], likes=10)
    save_quote(db_conn, quote)

    # Get the ID of the saved quote
    cursor = db_conn.cursor()
    cursor.execute("SELECT id FROM quotes WHERE text = ?", (quote.text,))
    quote_id = cursor.fetchone()[0]

    # Record history
    record_history(db_conn, quote_id)

    # Verify it was recorded
    cursor.execute("SELECT quote_id FROM history")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == quote_id


def test_get_random_quote_filters_recent_history(db_conn):
    # Save two quotes
    q1 = Quote(text="Quote 1", author="Author 1", tags=[], likes=10)
    q2 = Quote(text="Quote 2", author="Author 2", tags=[], likes=10)
    save_quote(db_conn, q1)
    save_quote(db_conn, q2)

    # Get IDs
    cursor = db_conn.cursor()
    cursor.execute("SELECT id, text FROM quotes")
    quotes = {row[1]: row[0] for row in cursor.fetchall()}

    id1 = quotes["Quote 1"]
    id2 = quotes["Quote 2"]

    # Record history for Quote 1 (very recent)
    record_history(db_conn, id1)

    # Record history for Quote 2 (long ago, more than 7 days)
    long_ago = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
    db_conn.execute(
        "INSERT INTO history (quote_id, shown_at) VALUES (?, ?)", (id2, long_ago)
    )
    db_conn.commit()

    # Fetch random quote - should only get Quote 2 because Quote 1 was shown recently
    # and Quote 2 was shown long ago
    for _ in range(10):  # Run several times to be sure
        quote = get_random_quote(db_conn)
        assert quote is not None
        assert quote["text"] == "Quote 2"


def test_get_random_quote_returns_none_if_all_recent(db_conn):
    # Save a quote
    q1 = Quote(text="Quote 1", author="Author 1", tags=[], likes=10)
    save_quote(db_conn, q1)

    # Get ID
    cursor = db_conn.cursor()
    cursor.execute("SELECT id FROM quotes")
    id1 = cursor.fetchone()[0]

    # Record history for Quote 1 (recent)
    record_history(db_conn, id1)

    # Fetch random quote - should get None
    quote = get_random_quote(db_conn)
    assert quote is None


def test_get_random_quote_includes_id(db_conn):
    # Save a quote
    q1 = Quote(text="Quote 1", author="Author 1", tags=[], likes=10)
    save_quote(db_conn, q1)

    # Fetch random quote
    quote = get_random_quote(db_conn)
    assert quote is not None
    assert "id" in quote
    assert isinstance(quote["id"], int)


def test_get_random_quote_handles_sparse_ids(db_conn):
    save_quote(db_conn, Quote(text="Quote 1", author="Author 1", tags=[], likes=10))
    save_quote(db_conn, Quote(text="Quote 2", author="Author 2", tags=[], likes=10))
    save_quote(db_conn, Quote(text="Quote 3", author="Author 3", tags=[], likes=10))

    db_conn.execute("DELETE FROM quotes WHERE text = ?", ("Quote 2",))
    db_conn.commit()

    seen = set()
    for _ in range(20):
        quote = get_random_quote(db_conn)
        assert quote is not None
        seen.add(quote["text"])

    assert seen == {"Quote 1", "Quote 3"}


def test_get_random_quote_uses_wraparound_when_random_pivot_misses(
    db_conn, monkeypatch
):
    save_quote(db_conn, Quote(text="First", author="Author 1", tags=[], likes=10))
    save_quote(db_conn, Quote(text="Second", author="Author 2", tags=[], likes=10))

    monkeypatch.setattr("zen_prompt.db.random.randint", lambda _min_id, max_id: max_id)
    db_conn.execute("DELETE FROM quotes WHERE text = ?", ("Second",))
    db_conn.commit()

    quote = get_random_quote(db_conn)
    assert quote is not None
    assert quote["text"] == "First"
