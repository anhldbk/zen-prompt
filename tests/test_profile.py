import json
from typer.testing import CliRunner
from zen_prompt.cli import app
from zen_prompt.commands.utils import get_profile_config_path
from unittest.mock import patch, ANY

runner = CliRunner()

def test_profile_save(tmp_path, monkeypatch):
    # Mock config path to use tmp_path
    config_path = tmp_path / "profiles.json"
    monkeypatch.setattr("zen_prompt.commands.utils.get_profile_config_path", lambda: config_path)
    
    # Save a profile
    result = runner.invoke(app, ["profile", "save", "work", "--tag", "focus", "--photo-max-height", "5"])
    assert result.exit_code == 0
    assert "Profile 'work' saved" in result.stdout
    
    # Verify file exists and has correct content
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "work" in data["profiles"]
    assert data["profiles"]["work"]["tag"] == ["focus"]
    assert data["profiles"]["work"]["image_max_height"] == 5

def test_profile_list(tmp_path, monkeypatch):
    config_path = tmp_path / "profiles.json"
    monkeypatch.setattr("zen_prompt.commands.utils.get_profile_config_path", lambda: config_path)
    
    # Save a couple of profiles
    runner.invoke(app, ["profile", "save", "work", "--tag", "focus"])
    runner.invoke(app, ["profile", "save", "relax", "--tag", "nature"])
    
    result = runner.invoke(app, ["profile", "list"])
    assert result.exit_code == 0
    assert "work" in result.stdout
    assert "relax" in result.stdout
    assert "focus" in result.stdout
    assert "nature" in result.stdout

def test_profile_delete(tmp_path, monkeypatch):
    config_path = tmp_path / "profiles.json"
    monkeypatch.setattr("zen_prompt.commands.utils.get_profile_config_path", lambda: config_path)
    
    runner.invoke(app, ["profile", "save", "work", "--tag", "focus"])
    
    result = runner.invoke(app, ["profile", "delete", "work"])
    assert result.exit_code == 0
    assert "Profile 'work' deleted" in result.stdout
    
    data = json.loads(config_path.read_text())
    assert "work" not in data["profiles"]

def test_profile_default(tmp_path, monkeypatch):
    config_path = tmp_path / "profiles.json"
    monkeypatch.setattr("zen_prompt.commands.utils.get_profile_config_path", lambda: config_path)
    
    runner.invoke(app, ["profile", "save", "work", "--tag", "focus"])
    
    result = runner.invoke(app, ["profile", "default", "work"])
    assert result.exit_code == 0
    assert "Default profile set to 'work'" in result.stdout
    
    data = json.loads(config_path.read_text())
    assert data["default_profile"] == "work"

def test_random_with_profile(tmp_path, monkeypatch):
    config_path = tmp_path / "profiles.json"
    monkeypatch.setattr("zen_prompt.commands.utils.get_profile_config_path", lambda: config_path)
    
    # Save a profile
    runner.invoke(app, ["profile", "save", "work", "--tag", "focus", "--no-photo"])
    
    working_dir = tmp_path / "data/sqlite"
    working_dir.mkdir(parents=True)
    db_path = working_dir / "quotes.db"
    db_path.touch()

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.sqlite3.connect"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "text": "Focus quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["focus"],
            "id": 1,
        }

        # Run random with profile
        result = runner.invoke(app, ["random", "--profile", "work", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        mock_get_random.assert_called_with(
            ANY,
            tags=["focus"],
            authors=None,
            min_likes=0,
            max_words=None,
            max_chars=None,
        )

def test_random_profile_override(tmp_path, monkeypatch):
    config_path = tmp_path / "profiles.json"
    monkeypatch.setattr("zen_prompt.commands.utils.get_profile_config_path", lambda: config_path)
    
    # Save a profile with tag 'focus'
    runner.invoke(app, ["profile", "save", "work", "--tag", "focus", "--no-photo"])
    
    working_dir = tmp_path / "data/sqlite"
    working_dir.mkdir(parents=True)
    db_path = working_dir / "quotes.db"
    db_path.touch()

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.sqlite3.connect"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "text": "Nature quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["nature"],
            "id": 1,
        }

        # Run random with profile 'work' but override tag with 'nature'
        result = runner.invoke(app, ["random", "--profile", "work", "--tag", "nature", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        # Manual tag 'nature' should override profile tag 'focus'
        mock_get_random.assert_called_with(
            ANY,
            tags=["nature"],
            authors=None,
            min_likes=0,
            max_words=None,
            max_chars=None,
        )

def test_random_default_profile(tmp_path, monkeypatch):
    config_path = tmp_path / "profiles.json"
    monkeypatch.setattr("zen_prompt.commands.utils.get_profile_config_path", lambda: config_path)
    
    # Save and set default profile
    runner.invoke(app, ["profile", "save", "work", "--tag", "focus", "--no-photo"])
    runner.invoke(app, ["profile", "default", "work"])
    
    working_dir = tmp_path / "data/sqlite"
    working_dir.mkdir(parents=True)
    db_path = working_dir / "quotes.db"
    db_path.touch()

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.sqlite3.connect"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "text": "Focus quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["focus"],
            "id": 1,
        }

        # Run random without explicit profile, should use default 'work'
        result = runner.invoke(app, ["random", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        mock_get_random.assert_called_with(
            ANY,
            tags=["focus"],
            authors=None,
            min_likes=0,
            max_words=None,
            max_chars=None,
        )
