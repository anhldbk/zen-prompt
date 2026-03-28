import textwrap
import typer
from typing import Optional, List
from zen_prompt.commands.utils import get_cached_db
from zen_prompt.db import (
    connect_db,
    get_random_quote,
    get_rotation_state,
    record_history,
    update_rotation_state,
)
from zen_prompt.commands.arts import (
    DEFAULT_PHOTO_TOPIC,
    get_folder_image_paths,
    get_photo_renderable,
    render_photo,
    validate_photo_mode,
)


def validate_photo_layout(layout: str) -> str:
    if layout in {"stack", "table"}:
        return layout

    raise ValueError("Photo layout must be one of: stack, table")


def _wrap_text(text: str, width: int) -> str:
    wrapped_lines = []
    for paragraph in text.splitlines() or [""]:
        if paragraph.strip():
            wrapped_lines.append(textwrap.fill(paragraph, width=width))
        else:
            wrapped_lines.append("")
    return "\n".join(wrapped_lines)


def _build_quote_renderable(quote, verbose: bool, quote_width: int):
    from rich.console import Group
    from rich.text import Text

    attribution = f"  -- {quote['author']}" + (
        f" (from '{quote['book_title']}')" if quote["book_title"] else ""
    )

    lines = [
        Text(f'"{_wrap_text(quote["text"], quote_width)}"', style="bold white"),
        Text(""),
        Text(_wrap_text(attribution, quote_width)),
    ]

    if verbose:
        lines.append(Text(f"  Tags: {', '.join(quote['tags'])}"))
        if quote.get("likes"):
            lines.append(Text(f"  Likes: {quote['likes']}"))
        if quote.get("link"):
            lines.append(Text(f"  Link: {quote['link']}"))

    return Group(*lines)


def _resolve_folder_photo(photo: str, conn) -> str:
    if not photo.startswith("folder@"):
        return photo

    folder_path = photo[7:]
    image_paths = get_folder_image_paths(folder_path)
    last_file = get_rotation_state(conn, folder_path)

    next_index = 0
    if last_file:
        for index, image_path in enumerate(image_paths):
            if image_path.name == last_file:
                next_index = (index + 1) % len(image_paths)
                break

    selected = image_paths[next_index]
    update_rotation_state(conn, folder_path, selected.name)
    return f"file@{selected}"


def _render_photo_table_layout(
    quote,
    photo: str,
    image_max_height: int,
    image_max_width: int | None,
    verbose: bool,
    quote_width: int,
):
    from rich.console import Console
    from rich.table import Table

    console = Console()
    photo_width = image_max_width or max(20, console.width // 3)
    photo_renderable = get_photo_renderable(
        photo,
        image_max_height=image_max_height,
        image_max_width=photo_width,
        console=console,
    )
    if photo_renderable is None:
        return

    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(vertical="middle", no_wrap=True)
    table.add_column(vertical="middle", ratio=1)
    table.add_row(
        photo_renderable, _build_quote_renderable(quote, verbose, quote_width)
    )

    console.print()
    console.print(table)
    console.print()


def random(
    ctx: typer.Context,
    tag: Optional[List[str]] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Choose quotes from a given tag (can specify multiple)",
    ),
    author: Optional[List[str]] = typer.Option(
        None,
        "--author",
        "-a",
        help="Choose quotes from a certain author (can specify multiple)",
    ),
    min_likes: int = typer.Option(
        0, "--quote-min-likes", "-m", help="Minimum likes for the quote"
    ),
    quote_max_words: Optional[int] = typer.Option(
        None,
        "--quote-max-words",
        help="Maximum word count for a selected quote",
        min=1,
    ),
    quote_max_chars: Optional[int] = typer.Option(
        None,
        "--quote-max-chars",
        help="Maximum character count for a selected quote",
        min=1,
    ),
    quote_width: int = typer.Option(
        80,
        "--quote-width",
        help="Maximum quote line width before wrapping",
        min=10,
    ),
    photo: str = typer.Option(
        f"topic@{DEFAULT_PHOTO_TOPIC}",
        "--photo",
        "-p",
        help="Visual mode: topic@<name>, file@<path>, or folder@<path>",
    ),
    no_photo: bool = typer.Option(
        False,
        "--no-photo",
        help="Disable photo rendering and print only the quote text",
    ),
    photo_layout: str = typer.Option(
        "table",
        "--photo-layout",
        "-l",
        help="Photo layout: stack or table",
    ),
    image_max_height: int = typer.Option(
        10,
        "--photo-max-height",
        help="Maximum image height in terminal lines",
        min=1,
    ),
    image_max_width: Optional[int] = typer.Option(
        None,
        "--photo-max-width",
        help="Maximum image width in terminal characters; defaults to terminal width",
        min=1,
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Display tags for the quote"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Use a saved profile for settings"
    ),
    working_dir: str = typer.Option(
        "docs/data",
        "--working-dir",
        "-w",
        help="Working directory for local cache",
    ),
):
    """
    Get a random quote from the local cached database.
    """
    from zen_prompt.commands.utils import load_profile_config
    import click

    config = load_profile_config()
    profile_name = profile or config.default_profile
    if profile_name:
        if profile_name in config.profiles:
            p_data = config.profiles[profile_name]

            # Override only if not provided by user
            def is_provided(name):
                return (
                    ctx.get_parameter_source(name)
                    == click.core.ParameterSource.COMMANDLINE
                )

            if not is_provided("tag"):
                tag = p_data.tag
            if not is_provided("author"):
                author = p_data.author
            if not is_provided("min_likes"):
                min_likes = p_data.min_likes
            if not is_provided("quote_max_words"):
                quote_max_words = p_data.quote_max_words
            if not is_provided("quote_max_chars"):
                quote_max_chars = p_data.quote_max_chars
            if not is_provided("quote_width"):
                quote_width = p_data.quote_width
            if not is_provided("photo"):
                photo = p_data.photo
            if not is_provided("no_photo"):
                no_photo = p_data.no_photo
            if not is_provided("photo_layout"):
                photo_layout = p_data.photo_layout
            if not is_provided("image_max_height"):
                image_max_height = p_data.image_max_height
            if not is_provided("image_max_width"):
                image_max_width = p_data.image_max_width
            if not is_provided("verbose"):
                verbose = p_data.verbose
        elif profile:
            typer.echo(f"Error: Profile '{profile}' not found.", err=True)
            raise typer.Exit(code=1)

    db_path = get_cached_db(working_dir)
    if not db_path:
        typer.echo(
            "Error: No runtime database found. Run 'sync' first or 'export' to create one.",
            err=True,
        )
        raise typer.Exit(code=1)

    if no_photo:
        photo = ""
    else:
        try:
            photo = validate_photo_mode(photo)
        except ValueError as exc:
            raise typer.BadParameter(str(exc), param_hint="--photo") from exc

    try:
        photo_layout = validate_photo_layout(photo_layout)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--photo-layout") from exc

    conn = connect_db(db_path)
    try:
        photo = _resolve_folder_photo(photo, conn)
        quote = get_random_quote(
            conn,
            tags=tag,
            authors=author,
            min_likes=min_likes,
            max_words=quote_max_words,
            max_chars=quote_max_chars,
        )
        if quote:
            if photo and photo_layout == "table":
                _render_photo_table_layout(
                    quote,
                    photo,
                    image_max_height=image_max_height,
                    image_max_width=image_max_width,
                    verbose=verbose,
                    quote_width=quote_width,
                )
            else:
                if photo:
                    render_photo(
                        photo,
                        image_max_height=image_max_height,
                        image_max_width=image_max_width,
                    )

                typer.echo("")  # Newline
                typer.secho(
                    f'"{_wrap_text(quote["text"], quote_width)}"',
                    fg=typer.colors.WHITE,
                    bold=True,
                )
                typer.echo("")
                typer.echo(
                    _wrap_text(
                        f" -- {quote['author']}"
                        + (
                            f" (from '{quote['book_title']}')"
                            if quote["book_title"]
                            else ""
                        ),
                        quote_width,
                    )
                )

                if verbose:
                    typer.echo(f"  Tags: {', '.join(quote['tags'])}")
                    if quote.get("likes"):
                        typer.echo(f"  Likes: {quote['likes']}")
                    if quote.get("link"):
                        typer.echo(f"  Link: {quote['link']}")

                typer.echo("")  # Newline

            # Record that this quote was shown
            record_history(conn, quote["id"])

        else:
            msg = "No quotes found in database"
            if tag or author:
                filters = []
                if tag:
                    filters.append(f"tags: {', '.join(tag)}")
                if author:
                    filters.append(f"authors: {', '.join(author)}")
                msg += f" matching {' and '.join(filters)}"
            typer.echo(msg + ".")
    finally:
        conn.close()
