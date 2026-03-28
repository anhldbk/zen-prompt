import os
import sqlite3
from pathlib import Path
from unittest.mock import patch
import pytest
from typer.testing import CliRunner
from zen_prompt.cli import app
from zen_prompt.db import init_db, save_quote
from zen_prompt.models import Quote

runner = CliRunner()

@pytest.fixture
def temp_workspace(tmp_path):
    # Setup a temp DB
    db_path = tmp_path / "test.db"
    init_db(str(db_path))
    
    # Add a quote
    conn = sqlite3.connect(str(db_path))
    save_quote(conn, Quote(text="Test", author="Author", tags=["test"]))
    conn.close()
    
    # Setup a photo folder
    photo_folder = tmp_path / "photos"
    photo_folder.mkdir()
    (photo_folder / "a.jpg").write_bytes(b"a")
    (photo_folder / "b.png").write_bytes(b"b")
    (photo_folder / "c.webp").write_bytes(b"c")
    
    return {
        "db_path": str(db_path),
        "photo_folder": str(photo_folder),
        "working_dir": str(tmp_path)
    }

def test_photo_folder_rotation(temp_workspace):
    db_path = temp_workspace["db_path"]
    photo_folder = temp_workspace["photo_folder"]
    working_dir = temp_workspace["working_dir"]
    
    # Mock get_photo_renderable and render_photo to avoid actual image processing
    with (
        patch("zen_prompt.commands.random.get_cached_db", return_value=db_path),
        patch("zen_prompt.commands.random.get_photo_renderable", return_value="renderable"),
        patch("zen_prompt.commands.random.render_photo") as mock_render,
        patch("zen_prompt.commands.random._render_photo_table_layout") as mock_render_table
    ):
        # First call: should pick 'a.jpg'
        result = runner.invoke(app, ["random", "--photo", f"folder@{photo_folder}", "--working-dir", working_dir])
        assert result.exit_code == 0
        
        # Second call: should pick 'b.png'
        result = runner.invoke(app, ["random", "--photo", f"folder@{photo_folder}", "--working-dir", working_dir])
        assert result.exit_code == 0
        
        # Third call: should pick 'c.webp'
        result = runner.invoke(app, ["random", "--photo", f"folder@{photo_folder}", "--working-dir", working_dir])
        assert result.exit_code == 0
        
        # Fourth call: should loop back to 'a.jpg'
        result = runner.invoke(app, ["random", "--photo", f"folder@{photo_folder}", "--working-dir", working_dir])
        assert result.exit_code == 0

    # Verify rotation state in DB
    from zen_prompt.db import get_rotation_state
    conn = sqlite3.connect(db_path)
    last_file = get_rotation_state(conn, photo_folder)
    assert last_file == "a.jpg"
    conn.close()
