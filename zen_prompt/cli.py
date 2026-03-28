import typer
from typing import Optional
import click
from typer.main import get_command
from zen_prompt import __version__
from zen_prompt.commands import crawl as crawl_mod
from zen_prompt.commands import export as export_mod
from zen_prompt.commands import sync as sync_mod
from zen_prompt.commands import random as random_mod
from zen_prompt.commands import search as search_mod
from zen_prompt.commands import stat as stat_mod
from zen_prompt.commands import distill as distill_mod
from zen_prompt.commands import get as get_mod
from zen_prompt.commands import history as history_mod
from zen_prompt.commands import profile as profile_mod

app = typer.Typer(
    help="Aesthetic inspiration for your shell.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def version_callback(value: bool):
    if value:
        typer.echo(f"zen-prompt {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
):
    """
    Zen Prompt: Aesthetic inspiration for your shell.
    """
    if ctx.invoked_subcommand is None:
        click_ctx = click.get_current_context()
        click_app = get_command(app)
        random_cmd = click_app.commands["random"]
        sub_ctx = random_cmd.make_context("random", [], parent=click_ctx)
        random_cmd.invoke(sub_ctx)


# Register commands
app.command()(crawl_mod.crawl)
app.command()(export_mod.export)
app.command()(sync_mod.sync)
app.command()(random_mod.random)
app.command()(search_mod.search)
app.command()(stat_mod.stat)
app.command()(distill_mod.distill)
app.command()(get_mod.get)
app.add_typer(history_mod.app, name="history")
app.add_typer(profile_mod.app, name="profile")

if __name__ == "__main__":
    app()
