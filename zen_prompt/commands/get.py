import sqlite3
import typer
from zen_prompt import db
from zen_prompt.commands import utils


def get(
    quote_id: int = typer.Argument(..., help="The ID of the quote to retrieve."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Display extra metadata like tags."
    ),
    working_dir: str = typer.Option(
        "docs/data/sqlite",
        "--working-dir",
        "-w",
        help="Working directory for local cache",
    ),
):
    """
    Retrieve a specific quote from the database by its ID.
    """
    db_path = utils.get_cached_db(working_dir)

    if not db_path:
        typer.secho("❌ Database not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

    conn = sqlite3.connect(db_path)
    try:
        quote = db.get_quote_by_id(conn, quote_id)

        if not quote:
            typer.secho(
                f"❌ Quote with ID {quote_id} not found.", fg=typer.colors.YELLOW
            )
            raise typer.Exit(1)

        # Display the quote
        typer.secho(f"\n[{quote['id']}]", fg=typer.colors.CYAN, dim=True)
        typer.secho(f'"{quote["text"]}"', fg=typer.colors.WHITE, bold=True)

        author_line = f"  — {quote['author']}"
        if quote["book_title"]:
            author_line += f", {quote['book_title']}"
        typer.secho(author_line, fg=typer.colors.GREEN)

        if verbose:
            if quote["tags"]:
                typer.echo(f"\n🏷️  Tags: {', '.join(quote['tags'])}")
            if quote.get("likes"):
                typer.echo(f"❤️  Likes: {quote['likes']}")
            if quote.get("link"):
                typer.secho(f"🔗 Link: {quote['link']}", fg=typer.colors.BRIGHT_BLACK)

        typer.echo("")

    finally:
        conn.close()
