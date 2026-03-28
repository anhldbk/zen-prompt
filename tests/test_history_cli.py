import os
import sqlite3
import pytest
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
    ):
        mock_get_db.return_value = str(db_path)
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Mocking the cursor and the return value for history list
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchall.return_value = [
            (1, "Quote 1", "Author 1", "2023-01-01 12:00:00"),
            (2, "Quote 2", "Author 2", "2023-01-01 12:01:00"),
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
    ):
        mock_get_db.return_value = str(db_path)
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Mocking statistics queries
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.side_effect = [
            (10,), # Total quotes
            (3,),  # Streak (consecutive days)
        ]
        mock_cursor.fetchall.side_effect = [
            [("Author 1", 5), ("Author 2", 3)], # Top authors
            [("tag1", 4), ("tag2", 2)],         # Top tags
        ]

        result = runner.invoke(app, ["history", "stat", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        assert "Total quotes seen: 10" in result.stdout
        assert "Inspiration Streak: 3 days" in result.stdout
        assert "Author 1" in result.stdout
        assert "tag1" in result.stdout
