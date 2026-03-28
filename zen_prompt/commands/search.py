import sqlite3
import typer
from zen_prompt.commands.utils import get_cached_db
from zen_prompt.db import search_quotes


def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(5, "--limit", "-l", help="Number of results to show"),
    working_dir: str = typer.Option(
        "docs/data",
        "--working-dir",
        "-w",
        help="Working directory for local cache",
    ),
):
    """
    Search for quotes using Full Text Search (FTS5).
    """
    db_path = get_cached_db(working_dir)
    if not db_path:
        typer.echo(
            "Error: No runtime database found. Run 'sync' first or 'export' to create one.",
            err=True,
        )
        raise typer.Exit(code=1)

    conn = sqlite3.connect(db_path)
    try:
        quotes = search_quotes(conn, query, limit)

        if not quotes:
            typer.echo(f"No results found for '{query}'.")
            return

        typer.echo(f"\nFound {len(quotes)} results for '{query}':\n")
        for quote in quotes:
            typer.secho(f'"{quote["text"]}"', fg=typer.colors.GREEN)
            typer.echo(
                f"  -- {quote['author']}"
                + (f" (from '{quote['book_title']}')" if quote["book_title"] else "")
            )
            likes_str = f" | {quote['likes']} likes" if quote.get("likes") else ""
            typer.echo(f"  Tags: {', '.join(quote['tags'])}{likes_str}")
            if quote.get("link"):
                typer.secho(f"  {quote['link']}", fg=typer.colors.BRIGHT_BLACK)
            typer.echo("")
    finally:
        conn.close()
