import sqlite3
import typer
from typing import Optional
from rich.console import Console
from rich.markdown import Markdown
from zen_prompt import db
from zen_prompt.commands import utils


def stat(
    output_path: Optional[str] = typer.Option(
        None, "--output", "-o", help="Path to save the statistics as a Markdown file."
    ),
    working_dir: str = typer.Option(
        "docs/data/sqlite",
        "--working-dir",
        "-w",
        help="Working directory for the local cache",
    ),
):
    """
    Generate statistics about the quote database.
    """
    db_path = utils.get_cached_db(working_dir)

    if not db_path:
        typer.secho(
            "❌ Database not found. Please run 'sync' or 'crawl' first.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    conn = sqlite3.connect(db_path)
    console = Console()

    try:
        stats = db.get_stats(conn)

        md_text = "# 📊 Quote Database Statistics\n\n"
        md_text += f"**Database:** `{db_path}`\n\n"

        # ... (rest of the md_text generation remains the same)

        # Summary
        md_text += "## 📋 Summary\n\n"
        md_text += f"- **Total Quotes:**  {stats['total_quotes']}\n"
        md_text += f"- **Total Authors:** {stats['total_authors']}\n"
        md_text += f"- **Total Likes:**   {stats.get('total_likes', 0)}\n\n"

        # Top Authors
        md_text += "## ✍️ Top 10 Authors\n\n"
        for i, author in enumerate(stats["top_authors"], 1):
            likes_str = (
                f" ({author.get('likes', 0)} likes)" if "likes" in author else ""
            )
            md_text += (
                f"{i}. **{author['author']}**: {author['count']} quotes{likes_str}\n"
            )
        md_text += "\n"

        # Top Tags
        md_text += "## 🏷️ Top 10 Tags\n\n"
        for i, tag in enumerate(stats["top_tags"], 1):
            tag_name = tag["tag"].strip('"')
            md_text += f"{i}. **{tag_name}**: {tag['count']} times\n"
        md_text += "\n"

        # Top Liked Quotes
        if stats.get("top_liked_quotes"):
            md_text += "## ❤️ Top 10 Liked Quotes\n\n"
            for i, quote in enumerate(stats["top_liked_quotes"], 1):
                text_preview = (
                    (quote["text"][:100] + "..")
                    if len(quote["text"]) > 100
                    else quote["text"]
                )
                md_text += f'{i}. [{quote["id"]}] **{quote["likes"]} likes** | *"{text_preview}"* — **{quote["author"]}**\n'
            md_text += "\n"

        # Length stats
        md_text += "## 📏 Distribution\n\n"
        md_text += f"- **Avg Length:** {stats['avg_length']:.1f} chars | {stats['avg_words']:.1f} words\n"
        md_text += f"- **Shortest:**   {stats['min_length']} chars | {stats['min_words']} words\n"
        md_text += f"- **Longest:**    {stats['max_length']} chars | {stats['max_words']} words\n\n"

        # Longest Quotes
        md_text += "## 📜 Longest Quotes (Top 5)\n\n"
        for i, quote in enumerate(stats["longest_quotes"], 1):
            text_preview = (
                (quote["text"][:100] + "..")
                if len(quote["text"]) > 100
                else quote["text"]
            )
            md_text += f'{i}. [{quote["id"]}] **{quote["length"]} chars** | *"{text_preview}"* — **{quote["author"]}**\n'
        md_text += "\n"

        # Shortest Quotes
        md_text += "## 🤏 Shortest Quotes (Top 5)\n\n"
        for i, quote in enumerate(stats["shortest_quotes"], 1):
            md_text += f'{i}. [{quote["id"]}] **{quote["length"]} chars** | *"{quote["text"]}"* — **{quote["author"]}**\n'
        md_text += "\n"

        # Similar Authors
        if stats["similar_authors"]:
            total_groups = len(stats["similar_authors"])
            md_text += (
                f"## 👥 Potential Duplicate Authors ({total_groups} groups found)\n\n"
            )
            for group in stats["similar_authors"][:5]:
                md_text += (
                    f"- **{group['normalized']}**: {', '.join(group['originals'])}\n"
                )

            if total_groups > 5:
                md_text += f"\n*... and {total_groups - 5} more groups.*\n"
            md_text += "\n"

        console.print(Markdown(md_text))

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_text)
            typer.secho(
                f"\n✅ Statistics saved to {output_path}", fg=typer.colors.GREEN
            )

    finally:
        conn.close()
