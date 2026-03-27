from datetime import datetime
from zen_prompt.commands.utils import get_manifest, save_manifest, generate_calver

from unittest.mock import patch


def test_get_manifest_missing(tmp_path):
    path = tmp_path / "manifest.json"
    # Mock os.path.exists to always return False for all fallback checks
    with patch("os.path.exists", return_value=False):
        manifest = get_manifest(str(path))
        assert manifest["version"] == "0.0.0"
        assert manifest["total_quotes"] == 0


def test_save_and_get_manifest(tmp_path):
    path = tmp_path / "manifest.json"
    data = {"version": "2026.03.26", "total_quotes": 5}
    save_manifest(str(path), data)

    manifest = get_manifest(str(path))
    assert manifest == data


def test_generate_calver():
    today = datetime.now().strftime("%Y.%m.%d")

    # New day
    assert generate_calver("2024.01.01") == today
    assert generate_calver("0.0.0") == today

    # Same day, first revision
    assert generate_calver(today) == f"{today}.1"

    # Same day, subsequent revision
    assert generate_calver(f"{today}.1") == f"{today}.2"
    assert generate_calver(f"{today}.9") == f"{today}.10"
