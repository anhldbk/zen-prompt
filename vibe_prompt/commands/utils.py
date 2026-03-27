import os
import json
from datetime import datetime
from typing import Optional, Dict, Any


def get_cached_db(working_dir: str) -> Optional[str]:
    """
    Helper to find the best available local database (quotes.db > quotes-small.db).
    Order: working_dir/cache -> working_dir -> shipped data (package data).
    """
    # 1. Check working_dir/cache
    cache_dir = os.path.join(working_dir, "cache")
    main_path = os.path.join(cache_dir, "quotes.db")
    small_path = os.path.join(cache_dir, "quotes-small.db")

    if os.path.exists(main_path):
        return main_path
    if os.path.exists(small_path):
        return small_path

    # 2. Check the working_dir itself
    direct_path = os.path.join(working_dir, "quotes.db")
    if os.path.exists(direct_path):
        return direct_path

    # 3. Check shipped data in the package (fallback for installed package)
    # The utils.py is in zen_prompt/commands/
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shipped_path = os.path.join(package_dir, "data", "sqlite", "quotes.db")
    shipped_small_path = os.path.join(package_dir, "data", "sqlite", "quotes-small.db")

    if os.path.exists(shipped_path):
        return shipped_path
    if os.path.exists(shipped_small_path):
        return shipped_small_path

    # 4. Check project-root docs/data/sqlite (fallback for development)
    project_root = os.path.dirname(package_dir)
    dev_path = os.path.join(project_root, "docs", "data", "sqlite", "quotes.db")
    dev_small_path = os.path.join(
        project_root, "docs", "data", "sqlite", "quotes-small.db"
    )

    if os.path.exists(dev_path):
        return dev_path
    if os.path.exists(dev_small_path):
        return dev_small_path

    return None


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
