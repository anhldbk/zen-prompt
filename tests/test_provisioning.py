import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock
import pytest
from zen_prompt.commands.utils import get_cached_db

def test_get_cached_db_provisions_when_missing():
    """
    Test that get_cached_db provisions the database from bundled resources
    if it's missing in the cache directory.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Mocking importlib.resources to return a dummy bundled db path
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as dummy_bundled_db:
            dummy_bundled_db.write(b"dummy database content")
            dummy_bundled_db_path = dummy_bundled_db.name

        try:
            # We need to mock importlib.resources.files and as_file
            with patch("importlib.resources.files") as mock_files, \
                 patch("importlib.resources.as_file") as mock_as_file:
                mock_resource = MagicMock()
                mock_resource.joinpath.return_value.is_file.return_value = True
                mock_files.return_value = mock_resource

                # as_file is a context manager
                mock_as_file.return_value.__enter__.return_value = dummy_bundled_db_path

                # Ensure cache directory doesn't exist yet
                cache_dir = os.path.join(tmp_dir, "cache")
                assert not os.path.exists(os.path.join(cache_dir, "quotes.db"))

                # Call get_cached_db
                db_path = get_cached_db(tmp_dir)

                # Verify it returned the correct path in the cache directory
                expected_path = os.path.join(cache_dir, "quotes.db")
                assert db_path == expected_path
                assert os.path.exists(expected_path)

                # Verify content was copied
                with open(expected_path, "rb") as f:
                    assert f.read() == b"dummy database content"
        finally:
            if os.path.exists(dummy_bundled_db_path):
                os.unlink(dummy_bundled_db_path)

def test_get_cached_db_returns_existing_when_present():
    """
    Test that get_cached_db returns the existing database if it's already in the cache.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_dir = os.path.join(tmp_dir, "cache")
        os.makedirs(cache_dir)
        db_path = os.path.join(cache_dir, "quotes.db")
        with open(db_path, "w") as f:
            f.write("existing content")

        returned_path = get_cached_db(tmp_dir)
        assert returned_path == db_path
        with open(returned_path, "r") as f:
            assert f.read() == "existing content"
