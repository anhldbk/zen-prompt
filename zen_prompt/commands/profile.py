import typer
from typing import Optional, List
from zen_prompt.models import Profile
from zen_prompt.commands.utils import load_profile_config, save_profile_config
from zen_prompt.commands.arts import DEFAULT_PHOTO_TOPIC

app = typer.Typer(help="Manage user profiles for personalized quotes.")


@app.command()
def save(
    name: str = typer.Argument(..., help="Name of the profile"),
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
        help="Visual mode: topic@<name> or file@<path to image file>",
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
):
    """
    Save current flags as a named profile.
    """
    config = load_profile_config()
    profile = Profile(
        tag=tag,
        author=author,
        min_likes=min_likes,
        quote_max_words=quote_max_words,
        quote_max_chars=quote_max_chars,
        quote_width=quote_width,
        photo=photo,
        no_photo=no_photo,
        photo_layout=photo_layout,
        image_max_height=image_max_height,
        image_max_width=image_max_width,
        verbose=verbose,
    )
    config.profiles[name] = profile
    save_profile_config(config)
    typer.echo(f"Profile '{name}' saved.")


@app.command(name="list")
def list_profiles():
    """
    Show all saved profiles and their settings.
    """
    config = load_profile_config()
    if not config.profiles:
        typer.echo("No profiles saved.")
        return

    for name, profile in config.profiles.items():
        is_default = " (default)" if config.default_profile == name else ""
        typer.echo(f"{name}{is_default}:")
        typer.echo(f"  Settings: {profile.model_dump(exclude_none=True)}")


@app.command()
def delete(name: str = typer.Argument(..., help="Name of the profile to delete")):
    """
    Remove a profile.
    """
    config = load_profile_config()
    if name in config.profiles:
        del config.profiles[name]
        if config.default_profile == name:
            config.default_profile = None
        save_profile_config(config)
        typer.echo(f"Profile '{name}' deleted.")
    else:
        typer.echo(f"Profile '{name}' not found.", err=True)
        raise typer.Exit(code=1)


@app.command()
def default(
    name: str = typer.Argument(..., help="Name of the profile to set as default"),
):
    """
    Set a specific profile to be used automatically.
    """
    config = load_profile_config()
    if name in config.profiles:
        config.default_profile = name
        save_profile_config(config)
        typer.echo(f"Default profile set to '{name}'.")
    else:
        typer.echo(f"Profile '{name}' not found.", err=True)
        raise typer.Exit(code=1)
