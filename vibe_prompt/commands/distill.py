import sqlite3
import typer
from zen_prompt import db
from zen_prompt.commands import utils


def distill(
    min_length: int = typer.Option(
        1,
        "--quote-min-chars",
        "-c",
        help="Minimum character length for a quote to keep.",
    ),
    min_words: int = typer.Option(
        0,
        "--quote-min-words",
        "-m",
        help="Minimum word count for a quote to keep.",
    ),
    min_likes: int = typer.Option(
        100,
        "--quote-min-likes",
        "-k",
        help="Minimum likes for a quote to keep.",
    ),
    remove_lowercase: bool = typer.Option(
        False, "--lowercase", help="Remove quotes starting with a lowercase letter."
    ),
    remove_uppercase: bool = typer.Option(
        False, "--uppercase", help="Remove quotes that are entirely in uppercase."
    ),
    normalize_authors: bool = typer.Option(
        True,
        "--normalize-authors",
        help="Group similar names (accents/case) to canonical ones.",
    ),
    vacuum: bool = typer.Option(
        True, "--vacuum/--no-vacuum", help="Run VACUUM after pruning to reclaim space."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Skip confirmation prompt."
    ),
    working_dir: str = typer.Option(
        "docs/data/sqlite",
        "--working-dir",
        "-w",
        help="Working directory for the local cache",
    ),
):
    """
    Prune the database by removing low-quality quotes (e.g., empty ones).
    """
    db_path = utils.get_cached_db(working_dir)

    if not db_path:
        typer.secho("❌ Database not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Ensure schema migrations are applied before pruning older databases.
    db.init_db(db_path)

    if not force:
        msg = f"Distilling {db_path}:\n"
        if min_length > 0:
            msg += f" - length < {min_length}\n"
        if min_words > 0:
            msg += f" - words < {min_words}\n"
        if min_likes > 0:
            msg += f" - likes < {min_likes}\n"
        if remove_lowercase:
            msg += " - starts with lowercase\n"
        if remove_uppercase:
            msg += " - all uppercase\n"
        if normalize_authors:
            msg += " - normalize similar author names\n"

        if not typer.confirm(f"Are you sure you want to proceed?\n{msg}"):
            raise typer.Abort()

    conn = sqlite3.connect(db_path)
    try:
        removed, updated_authors = db.distill_quotes(
            conn,
            min_length=min_length,
            min_words=min_words,
            min_likes=min_likes,
            remove_lowercase=remove_lowercase,
            remove_uppercase=remove_uppercase,
            normalize=normalize_authors,
        )

        if removed > 0 or updated_authors > 0:
            if removed > 0:
                typer.secho(
                    f"✨ Successfully removed {removed} quotes.", fg=typer.colors.GREEN
                )

            if updated_authors > 0:
                typer.secho(
                    f"👥 Successfully normalized {updated_authors} quotes with similar author names.",
                    fg=typer.colors.GREEN,
                )

            typer.echo("🔄 Rebuilding search index...")
            db.repopulate_fts(conn)

            if vacuum:
                typer.echo("🧹 Reclaiming space (VACUUM)...")
                conn.execute("VACUUM")
        else:
            typer.echo("✅ No changes were necessary.")

    finally:
        conn.close()
