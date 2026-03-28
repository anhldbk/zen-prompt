import os
from typer.testing import CliRunner
from zen_prompt.cli import app
from unittest.mock import patch, MagicMock

runner = CliRunner()

def test_history_list_command(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.history.utils.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.history.sqlite3.connect") as mock_connect,
        patch("zen_prompt.commands.history.db.get_history") as mock_get_history,
    ):
        mock_get_db.return_value = str(db_path)
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_get_history.return_value = [
            {"text": "Quote 1", "author": "Author 1", "shown_at": "2023-01-01 12:00:00"},
            {"text": "Quote 2", "author": "Author 2", "shown_at": "2023-01-01 12:01:00"},
        ]

        result = runner.invoke(app, ["history", "list", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        assert "Quote 1" in result.stdout
        assert "Author 1" in result.stdout
        assert "Quote 2" in result.stdout
        assert "Author 2" in result.stdout

def test_history_clear_command(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.history.utils.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.history.sqlite3.connect") as mock_connect,
    ):
        mock_get_db.return_value = str(db_path)
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Test clear with force
        result = runner.invoke(app, ["history", "clear", "--force", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        assert "History cleared" in result.stdout
        mock_conn.cursor.return_value.execute.assert_called_with("DELETE FROM history")

def test_history_stat_command(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.history.utils.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.history.sqlite3.connect") as mock_connect,
        patch("zen_prompt.commands.history.db.get_history_stats") as mock_get_history_stats,
    ):
        mock_get_db.return_value = str(db_path)
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_get_history_stats.return_value = {
            "total_seen": 10,
            "streak": 3,
            "top_authors": [("Author 1", 5), ("Author 2", 3)],
            "top_tags": [("tag1", 4), ("tag2", 2)],
        }

        result = runner.invoke(app, ["history", "stat", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        assert "Total quotes seen: 10" in result.stdout
        assert "Inspiration Streak: 3 days" in result.stdout
        assert "Author 1" in result.stdout
        assert "tag1" in result.stdout
