import os
import sqlite3
import json
import logging
import random
import shutil
import unicodedata
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


def count_words(text: str) -> int:
    normalized = " ".join((text or "").split())
    if not normalized:
        return 0
    return len(normalized.split(" "))


QUOTE_WORD_COUNT_SQL = """
CASE
    WHEN LENGTH(TRIM(REPLACE(REPLACE(COALESCE(text, ''), CHAR(10), ' '), CHAR(13), ' '))) = 0 THEN 0
    ELSE LENGTH(TRIM(REPLACE(REPLACE(COALESCE(text, ''), CHAR(10), ' '), CHAR(13), ' ')))
        - LENGTH(REPLACE(TRIM(REPLACE(REPLACE(COALESCE(text, ''), CHAR(10), ' '), CHAR(13), ' ')), ' ', ''))
        + 1
END
"""


def strip_diacritics(s: str) -> str:
    """
    Remove diacritics (accents) from a string.
    Example: "Thích Nhất Hạnh" -> "Thich Nhat Hanh"
    """
    if not s:
        return ""
    # Normalize to decomposition form and filter out non-spacing mark characters
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def init_db(db_path: str, *, backfill_lengths: bool = True):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Quotes table with timestamps and unique hash_id
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash_id TEXT UNIQUE,
            text TEXT NOT NULL,
            author TEXT NOT NULL,
            book_title TEXT,
            tags TEXT,
            likes INTEGER DEFAULT 0,
            link TEXT,
            char_count INTEGER,
            word_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Check if we need to add new columns to existing table
    cursor.execute("PRAGMA table_info(quotes)")
    columns = [row[1] for row in cursor.fetchall()]
    if "likes" not in columns:
        cursor.execute("ALTER TABLE quotes ADD COLUMN likes INTEGER DEFAULT 0")
    if "link" not in columns:
        cursor.execute("ALTER TABLE quotes ADD COLUMN link TEXT")
    if "char_count" not in columns:
        cursor.execute("ALTER TABLE quotes ADD COLUMN char_count INTEGER")
    if "word_count" not in columns:
        cursor.execute("ALTER TABLE quotes ADD COLUMN word_count INTEGER")

    if backfill_lengths:
        cursor.execute(
            """
            UPDATE quotes
            SET
                char_count = LENGTH(text),
                word_count = """
            + QUOTE_WORD_COUNT_SQL
            + """
            WHERE char_count IS NULL OR word_count IS NULL
            """
        )

    # Crawl state table with updated_at timestamp
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawl_state (
            tag_url TEXT PRIMARY KEY,
            last_page_processed INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # History table for shown quotes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            quote_id INTEGER,
            shown_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Photo rotation table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photo_rotation (
            folder_path TEXT PRIMARY KEY,
            last_file TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_likes ON quotes(likes)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_author_nocase ON quotes(author COLLATE NOCASE)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_quotes_word_count ON quotes(word_count)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_quotes_char_count ON quotes(char_count)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_quote_shown_at ON history(quote_id, shown_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_shown_at_quote ON history(shown_at, quote_id)"
    )

    conn.commit()
    conn.close()


def connect_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.execute("PRAGMA temp_store = MEMORY")
    cursor.execute("PRAGMA cache_size = -20000")
    return conn


def ensure_runtime_db(db_path: str):
    # Avoid the full backfill scan on latency-sensitive read paths.
    init_db(db_path, backfill_lengths=False)


def _build_random_quote_filters(
    tags: Optional[List[str]] = None,
    authors: Optional[List[str]] = None,
    min_likes: int = 0,
    max_words: Optional[int] = None,
    max_chars: Optional[int] = None,
    exclude_recent_history: bool = True,
):
    where_clauses = []
    params: list[object] = []
    word_count_expr = (
        """
        COALESCE(
            q.word_count,
            """
        + QUOTE_WORD_COUNT_SQL.replace("text", "q.text")
        + """
        )
    """
    )
    char_count_expr = "COALESCE(q.char_count, LENGTH(COALESCE(q.text, '')))"

    if exclude_recent_history:
        where_clauses.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM history h
                WHERE h.quote_id = q.id
                  AND h.shown_at >= datetime('now', '-7 days')
            )
            """
        )

    if min_likes > 0:
        where_clauses.append("q.likes >= ?")
        params.append(min_likes)

    if max_words is not None:
        where_clauses.append(f"{word_count_expr} <= ?")
        params.append(max_words)

    if max_chars is not None:
        where_clauses.append(f"{char_count_expr} <= ?")
        params.append(max_chars)

    if tags:
        tag_conditions = []
        for tag in tags:
            tag = tag.lower()
            if "*" in tag or "?" in tag:
                tag_pattern = tag.replace("*", "%").replace("?", "_")
                if '"' not in tag_pattern:
                    if not tag_pattern.startswith("%"):
                        tag_pattern = "%" + '"' + tag_pattern
                    if not tag_pattern.endswith("%"):
                        tag_pattern = tag_pattern + '"' + "%"
                tag_conditions.append("q.tags LIKE ? COLLATE NOCASE")
                params.append(tag_pattern)
            else:
                tag_conditions.append("q.tags LIKE ? COLLATE NOCASE")
                params.append(f'%"{tag}"%')
        if tag_conditions:
            where_clauses.append("(" + " OR ".join(tag_conditions) + ")")

    if authors:
        author_conditions = []
        for author in authors:
            author_lower = author.lower()
            if "*" in author_lower or "?" in author_lower:
                author_pattern = author_lower.replace("*", "%").replace("?", "_")
                author_conditions.append("q.author LIKE ? COLLATE NOCASE")
                params.append(author_pattern)
            else:
                author_conditions.append("q.author LIKE ? COLLATE NOCASE")
                params.append(f"%{author_lower}%")
        if author_conditions:
            where_clauses.append("(" + " OR ".join(author_conditions) + ")")

    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    return where_clause, params


def _fetch_random_quote_row(
    cursor: sqlite3.Cursor,
    where_clause: str,
    params: list[object],
    pivot: int,
):
    select_columns = """
        q.id, q.text, q.author, q.book_title, q.tags, q.likes, q.link
    """
    forward_query = f"""
        SELECT {select_columns}
        FROM quotes q
        WHERE q.id >= ? AND {where_clause}
        ORDER BY q.id
        LIMIT 1
    """
    row = cursor.execute(forward_query, [pivot, *params]).fetchone()
    if row:
        return row

    wrap_query = f"""
        SELECT {select_columns}
        FROM quotes q
        WHERE q.id < ? AND {where_clause}
        ORDER BY q.id
        LIMIT 1
    """
    return cursor.execute(wrap_query, [pivot, *params]).fetchone()


def _get_quote_id_bounds(cursor: sqlite3.Cursor):
    min_row = cursor.execute("SELECT id FROM quotes ORDER BY id ASC LIMIT 1").fetchone()
    if not min_row:
        return None

    max_row = cursor.execute(
        "SELECT id FROM quotes ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return {"min_id": min_row["id"], "max_id": max_row["id"]}


def get_random_quote(
    conn: sqlite3.Connection,
    tags: Optional[List[str]] = None,
    authors: Optional[List[str]] = None,
    min_likes: int = 0,
    max_words: Optional[int] = None,
    max_chars: Optional[int] = None,
    exclude_recent_history: bool = True,
):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    where_clause, params = _build_random_quote_filters(
        tags=tags,
        authors=authors,
        min_likes=min_likes,
        max_words=max_words,
        max_chars=max_chars,
        exclude_recent_history=exclude_recent_history,
    )

    bounds = _get_quote_id_bounds(cursor)
    if not bounds or bounds["min_id"] is None or bounds["max_id"] is None:
        return None

    min_id = bounds["min_id"]
    max_id = bounds["max_id"]
    pivot = random.randint(min_id, max_id)
    row = _fetch_random_quote_row(cursor, where_clause, params, pivot)
    if not row:
        return None

    return {
        "id": row["id"],
        "text": row["text"],
        "author": row["author"],
        "book_title": row["book_title"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "likes": row["likes"],
        "link": row["link"],
    }


def get_quote_by_id(conn: sqlite3.Connection, quote_id: int):
    """
    Retrieve a specific quote by its database ID.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute(
        """
        SELECT id, text, author, book_title, tags, likes, link 
        FROM quotes 
        WHERE id = ?
    """,
        (quote_id,),
    ).fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "text": row["text"],
        "author": row["author"],
        "book_title": row["book_title"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "likes": row["likes"],
        "link": row["link"],
    }


def search_quotes(conn: sqlite3.Connection, query: str, limit: int = 5):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Use FTS5 for searching
    rows = cursor.execute(
        """
        SELECT q.text, q.author, q.book_title, q.tags, q.likes, q.link 
        FROM quotes q
        JOIN quotes_fts f ON q.id = f.rowid
        WHERE quotes_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()

    quotes = []
    for row in rows:
        quotes.append(
            {
                "text": row["text"],
                "author": row["author"],
                "book_title": row["book_title"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "likes": row["likes"],
                "link": row["link"],
            }
        )
    return quotes


def save_quote(conn: sqlite3.Connection, quote):
    cursor = conn.cursor()
    hash_id = quote.hash_id
    tags_json = json.dumps(quote.tags)
    char_count = len(quote.text or "")
    word_count = count_words(quote.text or "")

    try:
        cursor.execute(
            """
            INSERT INTO quotes (hash_id, text, author, book_title, tags, likes, link, char_count, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                hash_id,
                quote.text,
                quote.author,
                quote.book_title,
                tags_json,
                quote.likes,
                quote.link,
                char_count,
                word_count,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Duplicate quote, ignore
        return False
    except sqlite3.Error as e:
        # Log other DB errors
        logger.error(f"Database error: {e}")
        return False


def get_crawl_state(conn: sqlite3.Connection, tag_url: str) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_page_processed FROM crawl_state WHERE tag_url = ?", (tag_url,)
    )
    result = cursor.fetchone()
    return result[0] if result else 0


def update_crawl_state(conn: sqlite3.Connection, tag_url: str, page: int):
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO crawl_state (tag_url, last_page_processed, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(tag_url) DO UPDATE SET
            last_page_processed = excluded.last_page_processed,
            updated_at = excluded.updated_at
    """,
        (tag_url, page, now),
    )
    conn.commit()


def record_history(conn: sqlite3.Connection, quote_id: int):
    """
    Record that a quote has been shown.
    """
    cursor = conn.cursor()
    cursor.execute("INSERT INTO history (quote_id) VALUES (?)", (quote_id,))
    conn.commit()


def get_rotation_state(conn: sqlite3.Connection, folder_path: str) -> Optional[str]:
    """
    Retrieve the last shown file for a given folder.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT last_file FROM photo_rotation WHERE folder_path = ?", (folder_path,)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def update_rotation_state(conn: sqlite3.Connection, folder_path: str, filename: str):
    """
    Store the "last shown" photo for a given folder.
    """
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO photo_rotation (folder_path, last_file, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(folder_path) DO UPDATE SET
            last_file = excluded.last_file,
            updated_at = excluded.updated_at
    """,
        (folder_path, filename, now),
    )
    conn.commit()


def get_history(conn: sqlite3.Connection, limit: int = 10):
    """
    Retrieve the most recent quotes shown to the user.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT q.text, q.author, h.shown_at
        FROM history h
        JOIN quotes q ON h.quote_id = q.id
        ORDER BY h.shown_at DESC
        LIMIT ?
    """,
        (limit,),
    )
    return cursor.fetchall()


def clear_history(conn: sqlite3.Connection):
    """
    Clear all entries from the history table.
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history")
    conn.commit()


def get_history_stats(conn: sqlite3.Connection):
    """
    Retrieve statistics from the history table.
    """
    cursor = conn.cursor()

    # 1. Total quotes seen
    cursor.execute("SELECT COUNT(*) FROM history")
    total_seen = cursor.fetchone()[0]

    # 2. Inspiration Streak (consecutive days)
    # This is a bit complex in SQL, so we'll do it by fetching dates
    cursor.execute(
        "SELECT DISTINCT date(shown_at) as day FROM history ORDER BY day DESC"
    )
    rows = cursor.fetchall()
    days = [datetime.strptime(row[0], "%Y-%m-%d").date() for row in rows]

    streak = 0
    if days:
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        # If last seen was today or yesterday, start counting
        if days[0] == today or days[0] == yesterday:
            streak = 1
            for i in range(len(days) - 1):
                if (days[i] - days[i + 1]).days == 1:
                    streak += 1
                else:
                    break

    # 3. Top authors in history
    cursor.execute(
        """
        SELECT q.author, COUNT(*) as count
        FROM history h
        JOIN quotes q ON h.quote_id = q.id
        GROUP BY q.author
        ORDER BY count DESC
        LIMIT 5
    """
    )
    top_authors = cursor.fetchall()

    # 4. Top tags in history
    # Again, handle JSON tags
    cursor.execute("SELECT q.tags FROM history h JOIN quotes q ON h.quote_id = q.id")
    rows = cursor.fetchall()
    tag_counts = {}
    for row in rows:
        tags = json.loads(row[0]) if row[0] else []
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_seen": total_seen,
        "streak": streak,
        "top_authors": top_authors,
        "top_tags": top_tags,
    }


def get_all_quotes(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT text, author, book_title, tags, likes, link FROM quotes")
    rows = cursor.fetchall()

    quotes = []
    for row in rows:
        quotes.append(
            {
                "text": row["text"],
                "author": row["author"],
                "book_title": row["book_title"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "likes": row["likes"],
                "link": row["link"],
            }
        )
    return quotes


def get_stats(conn: sqlite3.Connection):
    """
    Retrieve statistics from the quotes database.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Total counts
    counts = cursor.execute("""
        SELECT 
            COUNT(*) as total_quotes,
            COUNT(DISTINCT author) as total_authors,
            SUM(likes) as total_likes
        FROM quotes
    """).fetchone()

    # 2. Top authors
    top_authors = cursor.execute("""
        SELECT author, COUNT(*) as count, SUM(likes) as likes
        FROM quotes
        GROUP BY author
        ORDER BY count DESC
        LIMIT 10
    """).fetchall()

    # 3. Top tags
    # We use json_each if available (SQLite 3.38+)
    # Otherwise we'll have to do it in Python
    try:
        top_tags = cursor.execute("""
            SELECT j.value as tag, COUNT(*) as count
            FROM quotes, json_each(quotes.tags) j
            GROUP BY tag
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()
    except sqlite3.OperationalError:
        # Fallback for older SQLite versions
        all_tags = cursor.execute("SELECT tags FROM quotes").fetchall()
        tag_counts = {}
        for row in all_tags:
            tags = json.loads(row["tags"]) if row["tags"] else []
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        # Normalize to list of dicts for consistency
        top_tags = [{"tag": t, "count": c} for t, c in top_tags]

    # 4. Quote length and word stats
    stats_query = """
        SELECT 
            AVG(LENGTH(text)) as avg_len,
            MIN(LENGTH(text)) as min_len,
            MAX(LENGTH(text)) as max_len,
            AVG(CASE WHEN LENGTH(TRIM(text)) = 0 THEN 0 ELSE LENGTH(TRIM(REPLACE(REPLACE(text, CHAR(10), ' '), CHAR(13), ' '))) - LENGTH(REPLACE(TRIM(REPLACE(REPLACE(text, CHAR(10), ' '), CHAR(13), ' ')), ' ', '')) + 1 END) as avg_words,
            MIN(CASE WHEN LENGTH(TRIM(text)) = 0 THEN 0 ELSE LENGTH(TRIM(REPLACE(REPLACE(text, CHAR(10), ' '), CHAR(13), ' '))) - LENGTH(REPLACE(TRIM(REPLACE(REPLACE(text, CHAR(10), ' '), CHAR(13), ' ')), ' ', '')) + 1 END) as min_words,
            MAX(CASE WHEN LENGTH(TRIM(text)) = 0 THEN 0 ELSE LENGTH(TRIM(REPLACE(REPLACE(text, CHAR(10), ' '), CHAR(13), ' '))) - LENGTH(REPLACE(TRIM(REPLACE(REPLACE(text, CHAR(10), ' '), CHAR(13), ' ')), ' ', '')) + 1 END) as max_words
        FROM quotes
    """
    combined_stats = cursor.execute(stats_query).fetchone()

    # 5. Longest and shortest quotes (top 5 each)
    longest_quotes = cursor.execute("""
        SELECT id, text, author, LENGTH(text) as length
        FROM quotes
        ORDER BY length DESC
        LIMIT 5
    """).fetchall()

    shortest_quotes = cursor.execute("""
        SELECT id, text, author, LENGTH(text) as length
        FROM quotes
        ORDER BY length ASC
        LIMIT 5
    """).fetchall()

    # 6. Top liked quotes
    top_liked_quotes = cursor.execute("""
        SELECT id, text, author, likes
        FROM quotes
        ORDER BY likes DESC
        LIMIT 10
    """).fetchall()

    # 7. Similar authors (same name after stripping diacritics)
    all_authors = cursor.execute("SELECT DISTINCT author FROM quotes").fetchall()
    normalized_authors = {}
    for row in all_authors:
        original = row["author"]
        normalized = strip_diacritics(original).lower()
        if normalized not in normalized_authors:
            normalized_authors[normalized] = []
        normalized_authors[normalized].append(original)

    similar_authors = []
    for normalized, originals in normalized_authors.items():
        if len(originals) > 1:
            similar_authors.append(
                {"normalized": normalized, "originals": sorted(originals)}
            )

    return {
        "total_quotes": counts["total_quotes"],
        "total_authors": counts["total_authors"],
        "total_likes": counts["total_likes"],
        "top_authors": [
            {"author": row["author"], "count": row["count"], "likes": row["likes"]}
            for row in top_authors
        ],
        "top_tags": [{"tag": row["tag"], "count": row["count"]} for row in top_tags]
        if isinstance(top_tags[0], sqlite3.Row)
        else top_tags,
        "avg_length": combined_stats["avg_len"],
        "min_length": combined_stats["min_len"],
        "max_length": combined_stats["max_len"],
        "avg_words": combined_stats["avg_words"],
        "min_words": combined_stats["min_words"],
        "max_words": combined_stats["max_words"],
        "longest_quotes": [
            {
                "id": row["id"],
                "text": row["text"],
                "author": row["author"],
                "length": row["length"],
            }
            for row in longest_quotes
        ],
        "shortest_quotes": [
            {
                "id": row["id"],
                "text": row["text"],
                "author": row["author"],
                "length": row["length"],
            }
            for row in shortest_quotes
        ],
        "top_liked_quotes": [
            {
                "id": row["id"],
                "text": row["text"],
                "author": row["author"],
                "likes": row["likes"],
            }
            for row in top_liked_quotes
        ],
        "similar_authors": similar_authors,
    }


def normalize_authors(conn: sqlite3.Connection):
    """
    Find authors with similar names (same normalized name but different accents/case)
    and update them to use a single canonical name.
    """
    cursor = conn.cursor()

    # 1. Get all authors and their quote counts
    authors_data = cursor.execute("""
        SELECT author, COUNT(*) as count 
        FROM quotes 
        GROUP BY author
    """).fetchall()

    # 2. Group by normalized name
    groups = {}
    for row in authors_data:
        original = row[0]
        count = row[1]
        normalized = strip_diacritics(original).lower()

        if normalized not in groups:
            groups[normalized] = []
        groups[normalized].append({"name": original, "count": count})

    total_updated = 0

    # 3. For each group with more than one name, pick a canonical one
    for normalized, variants in groups.items():
        if len(variants) <= 1:
            continue

        # Strategy for picking canonical name:
        # 1. Prefer name with more accents (usually more correct/complete)
        # 2. Prefer name with highest quote count (most established)
        # 3. Prefer mixed case over all lowercase/uppercase

        def score_name(v):
            name = v["name"]
            # Diacritic count (original length - normalized length)
            diacritics = len(name) - len(strip_diacritics(name))
            # Case score (prefer Mixed Case over all upper or all lower)
            case_score = 1 if (name != name.lower() and name != name.upper()) else 0
            return (diacritics, v["count"], case_score)

        canonical_variant = max(variants, key=score_name)
        canonical_name = canonical_variant["name"]

        # 4. Update all variants to the canonical one
        for v in variants:
            if v["name"] != canonical_name:
                cursor.execute(
                    "UPDATE quotes SET author = ? WHERE author = ?",
                    (canonical_name, v["name"]),
                )
                total_updated += cursor.rowcount

    conn.commit()
    return total_updated


def distill_quotes(
    conn: sqlite3.Connection,
    min_length: int = 1,
    min_words: int = 0,
    min_likes: int = 0,
    remove_lowercase: bool = False,
    remove_uppercase: bool = False,
    normalize: bool = False,
):
    """
    Prune the database by removing quotes that don't meet quality criteria.
    Returns the number of removed quotes.
    """
    cursor = conn.cursor()

    # 1. Handle author normalization if requested
    updated_authors = 0
    if normalize:
        updated_authors = normalize_authors(conn)

    # 2. Handle pruning
    conditions = []
    params = []

    # 1. Minimum length
    if min_length > 0:
        conditions.append("LENGTH(text) < ?")
        params.append(min_length)

    # 2. Minimum words
    # SQLite approximation for word count: spaces + 1
    if min_words > 0:
        word_count_sql = "(CASE WHEN LENGTH(TRIM(text)) = 0 THEN 0 ELSE LENGTH(TRIM(REPLACE(REPLACE(text, CHAR(10), ' '), CHAR(13), ' '))) - LENGTH(REPLACE(TRIM(REPLACE(REPLACE(text, CHAR(10), ' '), CHAR(13), ' ')), ' ', '')) + 1 END)"
        conditions.append(f"{word_count_sql} < ?")
        params.append(min_words)

    # 3. Minimum likes
    if min_likes > 0:
        conditions.append("likes < ?")
        params.append(min_likes)

    # 4. Starts with lowercase
    if remove_lowercase:
        # GLOB is case-sensitive in SQLite
        conditions.append("text GLOB '[a-z]*'")

    # 4. ALL UPPERCASE
    if remove_uppercase:
        # Check if text is equal to its uppercase version and not equal to its lowercase version
        # (to avoid matching numbers/symbols only)
        conditions.append("(text = UPPER(text) AND text != LOWER(text))")

    if not conditions:
        return 0

    where_clause = " OR ".join(conditions)

    # Get count to remove
    cursor.execute(f"SELECT COUNT(*) FROM quotes WHERE {where_clause}", params)
    to_remove = cursor.fetchone()[0]

    if to_remove > 0:
        cursor.execute(f"DELETE FROM quotes WHERE {where_clause}", params)
        conn.commit()

    return to_remove, updated_authors


def repopulate_fts(conn: sqlite3.Connection):
    """
    Rebuild the FTS index from the current quotes table.
    """
    cursor = conn.cursor()
    # Check if FTS table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='quotes_fts'"
    )
    if cursor.fetchone():
        cursor.execute("DELETE FROM quotes_fts")
        cursor.execute("""
            INSERT INTO quotes_fts(rowid, text, author, book_title)
            SELECT id, text, author, book_title FROM quotes
        """)
        conn.commit()


def get_unique_tags(conn: sqlite3.Connection) -> List[str]:
    cursor = conn.cursor()
    cursor.execute("SELECT tags FROM quotes")
    rows = cursor.fetchall()

    unique_tags = set()
    for row in rows:
        tags = json.loads(row["tags"]) if row["tags"] else []
        unique_tags.update(tags)
    return sorted(list(unique_tags))


def optimize_db(db_path: str):
    """
    Apply SQLite optimizations: indexes, FTS5 virtual table, and VACUUM.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create standard indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_author ON quotes(author)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_author_nocase ON quotes(author COLLATE NOCASE)"
    )

    # Create FTS5 virtual table for searching
    cursor.execute("DROP TABLE IF EXISTS quotes_fts")
    cursor.execute("""
        CREATE VIRTUAL TABLE quotes_fts USING fts5(
            text, 
            author, 
            book_title,
            content='quotes',
            content_rowid='id'
        )
    """)

    # Populate FTS5 table
    cursor.execute("""
        INSERT INTO quotes_fts(rowid, text, author, book_title)
        SELECT id, text, author, book_title FROM quotes
    """)

    conn.commit()

    # Vacuum to minimize file size
    cursor.execute("VACUUM")
    conn.close()


def copy_database(source_db: str, target_db: str):
    os.makedirs(os.path.dirname(target_db), exist_ok=True)
    shutil.copy2(source_db, target_db)


def create_subset_db(
    source_db: str, target_db: str, limit: int = 500, tag: Optional[str] = None
):
    """
    Create a smaller subset of the database for the 'starter' API.
    Can be filtered by a specific tag.
    """
    if os.path.exists(target_db):
        os.remove(target_db)

    init_db(target_db)

    src_conn = sqlite3.connect(source_db)
    dst_conn = sqlite3.connect(target_db)

    # Build query with optional tag filter
    query = "SELECT hash_id, text, author, book_title, tags, likes, link FROM quotes"
    params = []

    if tag:
        query += " WHERE tags LIKE ?"
        params.append(f'%"{tag.lower()}"%')

    query += " ORDER BY RANDOM() LIMIT ?"
    params.append(limit)

    # Copy subset of quotes
    quotes = src_conn.execute(query, params).fetchall()

    dst_conn.executemany(
        """
        INSERT INTO quotes (
            hash_id, text, author, book_title, tags, likes, link, char_count, word_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                quote[0],
                quote[1],
                quote[2],
                quote[3],
                quote[4],
                quote[5],
                quote[6],
                len(quote[1] or ""),
                count_words(quote[1] or ""),
            )
            for quote in quotes
        ],
    )

    dst_conn.commit()
    src_conn.close()
    dst_conn.close()

    # Optimize the subset
    optimize_db(target_db)
