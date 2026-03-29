import os
import json
import csv
import sqlite3
import typer
from zen_prompt.db import get_all_quotes, optimize_db, create_subset_db
from zen_prompt.commands.utils import (
    generate_calver,
    get_distilled_db_path,
    get_manifest,
    save_manifest,
)


def export(
    output_dir: str = typer.Option(
        "./docs",
        "--output-dir",
        "-o",
        help="Target output directory for exported web assets",
    ),
    working_dir: str = typer.Option(
        "docs/data/sqlite",
        "--working-dir",
        "-w",
        help="Working directory where the source database is located",
    ),
    small_limit: int = typer.Option(
        500,
        "--small-limit",
        "-l",
        help="Number of quotes to include in the small database",
    ),
):
    """
    Export the database as optimized SQLite, JSON, CSV, and text files.
    This command optimizes the main database, creates a small subset, and
    exports everything to the 'data' directory within the target output.
    """
    db_path = get_distilled_db_path(working_dir)
    if not os.path.exists(db_path):
        typer.echo(
            f"Error: Distilled database not found at {db_path}. Run 'distill' first.",
            err=True,
        )
        raise typer.Exit(code=1)

    db_out_dir = os.path.join(output_dir, "data", "sqlite")
    json_out_dir = os.path.join(output_dir, "data", "json")
    csv_out_dir = os.path.join(output_dir, "data", "csv")
    text_out_dir = os.path.join(output_dir, "data", "text")
    manifest_path = os.path.join(output_dir, "data", "manifest.json")

    os.makedirs(db_out_dir, exist_ok=True)
    os.makedirs(json_out_dir, exist_ok=True)
    os.makedirs(csv_out_dir, exist_ok=True)
    os.makedirs(text_out_dir, exist_ok=True)

    # 1. Export SQLite Files
    # 1.1 Create quotes-small.db for buddhism tag
    small_db_path = os.path.join(db_out_dir, "quotes-small.db")
    typer.echo(
        f"Creating optimized small database ({small_limit} quotes, tag: buddhism) at {small_db_path}..."
    )
    create_subset_db(db_path, small_db_path, limit=small_limit, tag="buddhism")

    # 1.2 Optimize main quotes.db
    final_main_db_path = os.path.join(db_out_dir, "quotes.db")
    if os.path.abspath(db_path) != os.path.abspath(final_main_db_path):
        import shutil

        typer.echo(f"Copying main database to {final_main_db_path}...")
        shutil.copy2(db_path, final_main_db_path)

    typer.echo(f"Optimizing main database at {final_main_db_path}...")
    optimize_db(final_main_db_path)

    def write_csv(quotes_list, output_path):
        fieldnames = ["text", "author", "book_title", "tags", "likes", "link"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for q in quotes_list:
                row = q.copy()
                row["tags"] = "|".join(q["tags"])
                writer.writerow(row)

    def write_fortune_text(quotes_list, output_path):
        def format_quote(quote):
            lines = [quote["text"].rstrip()]
            if quote.get("author"):
                attribution = f"  -- {quote['author']}"
                if quote.get("book_title"):
                    attribution += f" (from '{quote['book_title']}')"
                lines.append(attribution)
            return "\n".join(lines)

        def escape_separator(text):
            return "\n".join(
                r"\%" if line == "%" else line for line in text.splitlines()
            )

        with open(output_path, "w", encoding="utf-8") as f:
            for quote in quotes_list:
                f.write(escape_separator(format_quote(quote)))
                f.write("\n%\n")

    # 2. Export JSON, CSV, and text files
    conn = sqlite3.connect(final_main_db_path)
    conn.row_factory = sqlite3.Row
    try:
        # 2.1 Full Collection (quotes.json & quotes.csv)
        full_quotes = get_all_quotes(conn)
        total_quotes = len(full_quotes)

        # 2.1.1 Handle Manifest
        manifest = get_manifest(manifest_path)
        old_count = manifest.get("total_quotes", 0)

        if total_quotes > old_count:
            manifest["version"] = generate_calver(manifest.get("version", "0.0.0"))
            manifest["total_quotes"] = total_quotes
            save_manifest(manifest_path, manifest)
            typer.echo(
                f"Bumping data version to {manifest['version']} (Total: {total_quotes})"
            )
        else:
            typer.echo(
                f"Data version remains at {manifest.get('version', '0.0.0')} (Total: {total_quotes})"
            )

        full_json_path = os.path.join(json_out_dir, "quotes.json")
        typer.echo(f"Exporting all quotes to {full_json_path}...")
        with open(full_json_path, "w", encoding="utf-8") as f:
            json.dump(full_quotes, f, indent=2, ensure_ascii=False)

        full_csv_path = os.path.join(csv_out_dir, "quotes.csv")
        typer.echo(f"Exporting all quotes to {full_csv_path}...")
        write_csv(full_quotes, full_csv_path)

        full_text_path = os.path.join(text_out_dir, "quotes.txt")
        typer.echo(f"Exporting all quotes to {full_text_path}...")
        write_fortune_text(full_quotes, full_text_path)

        # 2.2 Small Collection (quotes-small.json, quotes-small.csv & quotes-small.txt)
        small_conn = sqlite3.connect(small_db_path)
        small_conn.row_factory = sqlite3.Row
        try:
            small_quotes = get_all_quotes(small_conn)

            small_json_path = os.path.join(json_out_dir, "quotes-small.json")
            typer.echo(f"Exporting small collection to {small_json_path}...")
            with open(small_json_path, "w", encoding="utf-8") as f:
                json.dump(small_quotes, f, indent=2, ensure_ascii=False)

            small_csv_path = os.path.join(csv_out_dir, "quotes-small.csv")
            typer.echo(f"Exporting small collection to {small_csv_path}...")
            write_csv(small_quotes, small_csv_path)

            small_text_path = os.path.join(text_out_dir, "quotes-small.txt")
            typer.echo(f"Exporting small collection to {small_text_path}...")
            write_fortune_text(small_quotes, small_text_path)
        finally:
            small_conn.close()

    finally:
        conn.close()

    typer.echo(f"Successfully exported all assets to {output_dir}")
