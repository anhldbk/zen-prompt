import sqlite3
import typer
from rich.console import Console
from rich.table import Table
from zen_prompt import db
from zen_prompt.commands import utils

app = typer.Typer(help="Manage your quote history.")


@app.command("list")
def list_history(
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of recent quotes to show."
    ),
    working_dir: str = typer.Option(
        "docs/data/sqlite",
        "--working-dir",
        "-w",
        help="Working directory for the local cache",
    ),
):
    """
    Show the last N quotes seen.
    """
    db_path = utils.get_cached_db(working_dir)
    if not db_path:
        typer.secho("❌ Database not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

    conn = sqlite3.connect(db_path)
    try:
        history = db.get_history(conn, limit)
        if not history:
            typer.echo("No history found.")
            return

        table = Table(title=f"Recent Quotes (Last {len(history)})")
        table.add_column("Quote", style="italic")
        table.add_column("Author", style="bold cyan")
        table.add_column("Date", style="dim")

        for row in history:
            # Shorten long quotes for table view
            text = row["text"]
            if len(text) > 100:
                text = text[:97] + "..."
            table.add_row(text, row["author"], row["shown_at"])

        console = Console()
        console.print(table)
    finally:
        conn.close()


@app.command("clear")
def clear_history(
    force: bool = typer.Option(
        False, "--force", "-f", help="Force clear without confirmation."
    ),
    working_dir: str = typer.Option(
        "docs/data/sqlite",
        "--working-dir",
        "-w",
        help="Working directory for the local cache",
    ),
):
    """
    Clear all entries from the history table.
    """
    if not force:
        typer.confirm("Are you sure you want to clear your history?", abort=True)

    db_path = utils.get_cached_db(working_dir)
    if not db_path:
        typer.secho("❌ Database not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

    conn = sqlite3.connect(db_path)
    try:
        db.clear_history(conn)
        typer.secho("✅ History cleared.", fg=typer.colors.GREEN)
    finally:
        conn.close()


@app.command("stat")
def history_stat(
    working_dir: str = typer.Option(
        "docs/data/sqlite",
        "--working-dir",
        "-w",
        help="Working directory for the local cache",
    ),
):
    """
    Show history statistics.
    """
    db_path = utils.get_cached_db(working_dir)
    if not db_path:
        typer.secho("❌ Database not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

    conn = sqlite3.connect(db_path)
    try:
        stats = db.get_history_stats(conn)

        typer.echo(f"Total quotes seen: {stats['total_seen']}")
        typer.echo(f"Inspiration Streak: {stats['streak']} days")

        if stats["top_authors"]:
            typer.echo("\nTop Authors:")
            for author, count in stats["top_authors"]:
                typer.echo(f"- {author}: {count} times")

        if stats["top_tags"]:
            typer.echo("\nTop Tags:")
            for tag, count in stats["top_tags"]:
                typer.echo(f"- {tag}: {count} times")
    finally:
        conn.close()
