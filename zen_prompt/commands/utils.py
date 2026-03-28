import os
import json
import sqlite3
import shutil
import importlib.resources
from datetime import datetime
from typing import Optional, Dict, Any

from zen_prompt.db import ensure_runtime_db

RAW_DB_FILENAME = "quotes-raw.db"
DISTILLED_DB_FILENAME = "quotes-distilled.db"
RUNTIME_DB_FILENAME = "quotes.db"


def _ensure_runtime_db_if_valid(db_path: str):
    try:
        ensure_runtime_db(db_path)
    except sqlite3.Error:
        # Some tests and placeholder files use non-SQLite content. Keep lookup tolerant.
        pass


def get_raw_db_path(working_dir: str) -> str:
    return os.path.abspath(os.path.join(working_dir, RAW_DB_FILENAME))


def get_distilled_db_path(working_dir: str) -> str:
    return os.path.abspath(os.path.join(working_dir, DISTILLED_DB_FILENAME))


def get_runtime_db(working_dir: str) -> Optional[str]:
    """
    Helper to find the best available runtime database.
    If not found in working_dir/cache, it provisions it from the bundled data.
    """
    cache_dir = os.path.join(working_dir, "cache")
    db_path = os.path.join(cache_dir, RUNTIME_DB_FILENAME)

    # 1. Check if it already exists
    if os.path.exists(db_path):
        _ensure_runtime_db_if_valid(db_path)
        return db_path

    # 2. Try to provision from bundled data
    try:
        source = importlib.resources.files("zen_prompt.data").joinpath(
            RUNTIME_DB_FILENAME
        )
        if source.is_file():
            os.makedirs(cache_dir, exist_ok=True)
            with importlib.resources.as_file(source) as src_path:
                shutil.copy(src_path, db_path)
            _ensure_runtime_db_if_valid(db_path)
            return db_path
    except Exception:
        # Fallback to old behavior if provisioning fails or resource not found
        pass

    # 3. Fallback for development/legacy (check other locations)
    # Check the working_dir itself
    direct_path = os.path.join(working_dir, RUNTIME_DB_FILENAME)
    if os.path.exists(direct_path):
        _ensure_runtime_db_if_valid(direct_path)
        return direct_path

    # Check project-root docs/data/sqlite (fallback for development)
    # The utils.py is in zen_prompt/commands/
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(package_dir)
    dev_path = os.path.join(project_root, "docs", "data", "sqlite", RUNTIME_DB_FILENAME)
    dev_small_path = os.path.join(
        project_root, "docs", "data", "sqlite", "quotes-small.db"
    )

    if os.path.exists(dev_path):
        _ensure_runtime_db_if_valid(dev_path)
        return dev_path
    if os.path.exists(dev_small_path):
        _ensure_runtime_db_if_valid(dev_small_path)
        return dev_small_path

    return None


def get_cached_db(working_dir: str) -> Optional[str]:
    return get_runtime_db(working_dir)


def get_manifest(manifest_path: str) -> Dict[str, Any]:
    """
    Read the manifest from the specified path.
    Fall back to shipped manifest if local one is not found.
    Return an empty manifest if not found at all.
    """
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback to shipped manifest
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shipped_manifest = os.path.join(package_dir, "data", "manifest.json")
    if os.path.exists(shipped_manifest):
        try:
            with open(shipped_manifest, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback for development (project-root docs/data)
    project_root = os.path.dirname(package_dir)
    dev_manifest = os.path.join(project_root, "docs", "data", "manifest.json")
    if os.path.exists(dev_manifest):
        try:
            with open(dev_manifest, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {"version": "0.0.0", "total_quotes": 0}


def save_manifest(manifest_path: str, manifest: Dict[str, Any]):
    """
    Save the manifest to the specified path.
    """
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


from pathlib import Path
from zen_prompt.models import ProfileConfig


def get_profile_config_path() -> Path:
    """
    Get the path to the profiles configuration file.
    """
    config_dir = Path.home() / ".config" / "zen-prompt"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "profiles.json"


def load_profile_config() -> ProfileConfig:
    """
    Load the profile configuration from the profiles.json file.
    """
    config_path = get_profile_config_path()
    if config_path.exists():
        try:
            return ProfileConfig.model_validate_json(config_path.read_text())
        except Exception:
            pass
    return ProfileConfig()


def save_profile_config(config: ProfileConfig):
    """
    Save the profile configuration to the profiles.json file.
    """
    config_path = get_profile_config_path()
    config_path.write_text(config.model_dump_json(indent=2))


def generate_calver(current_version: str) -> str:
    """
    Generate a CalVer version string (YYYY.MM.DD).
    If the current version is from today, increment a revision suffix (.N).
    """
    today = datetime.now().strftime("%Y.%m.%d")
    if not current_version.startswith(today):
        return today

    # Same day, handle revision
    parts = current_version.split(".")
    if len(parts) == 4:
        # e.g., 2024.03.01.1 -> 2024.03.01.2
        try:
            rev = int(parts[3])
            return f"{today}.{rev + 1}"
        except ValueError:
            pass

    return f"{today}.1"
