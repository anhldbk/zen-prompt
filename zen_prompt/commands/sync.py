import os
import urllib.request
import typer
from zen_prompt.commands.utils import get_manifest


def sync(
    base_url: str = typer.Argument(
        "https://anhldbk.github.io/zen-prompt/data/",
        help="Base URL where the data files are hosted",
    ),
    working_dir: str = typer.Option(
        "docs/data", "--working-dir", "-w", help="Working directory for local cache"
    ),
    all_formats: bool = typer.Option(
        False,
        "--all-formats",
        "-a",
        help="Sync all data formats (SQLite, CSV, JSON, text)",
    ),
):
    """
    Sync data files (SQLite, CSV, JSON, text) from the remote static website.
    """
    # Ensure URL ends with slash
    if not base_url.endswith("/"):
        base_url += "/"

    def download_file(url, path, label, silent=False):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not silent:
            typer.echo(f"Downloading {label} from {url}...")
        try:
            with urllib.request.urlopen(url) as response, open(path, "wb") as out_file:
                out_file.write(response.read())
            if not silent:
                typer.echo(f"Successfully downloaded {label}.")
            return True
        except Exception as e:
            if not silent:
                typer.echo(f"Error downloading {label}: {e}", err=True)
            return False

    # 1. Check manifest.json
    local_manifest_path = os.path.join(working_dir, "manifest.json")
    remote_manifest_url = f"{base_url}manifest.json"

    # Temporarily download remote manifest to compare
    remote_manifest_tmp = os.path.join(working_dir, "manifest.remote.json")

    if download_file(
        remote_manifest_url, remote_manifest_tmp, "remote manifest", silent=True
    ):
        remote_manifest = get_manifest(remote_manifest_tmp)
        local_manifest = get_manifest(local_manifest_path)

        if (
            remote_manifest.get("version") == local_manifest.get("version")
            and local_manifest.get("version") != "0.0.0"
        ):
            typer.echo(
                f"Data is already up to date (version: {local_manifest.get('version')})."
            )
            if os.path.exists(remote_manifest_tmp):
                os.remove(remote_manifest_tmp)
            return

        typer.echo(
            f"New data version found: {remote_manifest.get('version')} (Local: {local_manifest.get('version')})"
        )
        # Update local manifest
        os.rename(remote_manifest_tmp, local_manifest_path)
    else:
        typer.echo(
            "Warning: Could not fetch remote manifest. Proceeding with full sync.",
            err=True,
        )

    # 2. Define targets
    targets = [
        ("sqlite/quotes.db", "SQLite database"),
        ("sqlite/quotes-small.db", "Small SQLite database"),
    ]

    if all_formats:
        targets.extend(
            [
                ("csv/quotes.csv", "CSV quotes"),
                ("csv/quotes-small.csv", "Small CSV quotes"),
                ("json/quotes.json", "JSON quotes"),
                ("json/quotes-small.json", "Small JSON quotes"),
                ("text/quotes.txt", "Text quotes"),
                ("text/quotes-small.txt", "Small text quotes"),
            ]
        )

    for rel_path, label in targets:
        url = f"{base_url}{rel_path}"
        dest_path = os.path.join(working_dir, rel_path)
        download_file(url, dest_path, label)
