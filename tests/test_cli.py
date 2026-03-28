import os
import re
import sys
import importlib
import inspect
from PIL import Image as PILImage
from typer.testing import CliRunner
from zen_prompt.cli import app
from zen_prompt.commands.get import get as get_command
from zen_prompt.commands.history import clear_history as history_clear_command
from zen_prompt.commands.history import history_stat as history_stat_command
from zen_prompt.commands.history import list_history as history_list_command
from zen_prompt.commands.random import random as random_command
from zen_prompt.commands.search import search as search_command
from zen_prompt.commands.stat import stat as stat_command
from unittest.mock import patch, MagicMock, ANY

runner = CliRunner()

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain_output(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def test_root_help_uses_refined_cli_contract():
    result = runner.invoke(app, ["--help"])
    stdout = _plain_output(result.stdout)
    assert result.exit_code == 0
    assert "Aesthetic inspiration for your shell" in stdout
    assert "-h" in stdout
    assert "--help" in stdout


def test_crawl_module_defers_scrapy_import():
    for module_name in list(sys.modules):
        if module_name == "zen_prompt.commands.crawl" or module_name.startswith(
            ("scrapy", "twisted")
        ):
            sys.modules.pop(module_name, None)

    importlib.import_module("zen_prompt.commands.crawl")

    assert "scrapy" not in sys.modules
    assert "twisted" not in sys.modules


def test_stat_module_defers_rich_markdown_import():
    for module_name in ["zen_prompt.commands.stat", "rich.markdown"]:
        sys.modules.pop(module_name, None)

    importlib.import_module("zen_prompt.commands.stat")

    assert "rich.markdown" not in sys.modules


def test_runtime_commands_default_to_data_root_working_dir():
    commands = [
        random_command,
        search_command,
        get_command,
        stat_command,
        history_list_command,
        history_clear_command,
        history_stat_command,
    ]

    for command in commands:
        working_dir = inspect.signature(command).parameters["working_dir"].default
        assert working_dir.default == "docs/data"


def test_crawl_command_creates_dir(tmp_path):
    working_dir = tmp_path / "test_data"
    # Mocking CrawlerProcess to avoid live crawl
    with patch("zen_prompt.commands.crawl._load_crawler_process") as mock_loader:
        mock_loader.return_value = MagicMock()
        result = runner.invoke(
            app, ["crawl", "--working-dir", str(working_dir), "--tags", "test"]
        )
        assert result.exit_code == 0
        assert os.path.exists(working_dir)


def test_crawl_command_explains_missing_all_extra(tmp_path):
    working_dir = tmp_path / "test_data"

    with patch(
        "zen_prompt.commands.crawl._load_crawler_process",
        side_effect=ModuleNotFoundError("scrapy"),
    ):
        result = runner.invoke(
            app, ["crawl", "--working-dir", str(working_dir), "--tags", "test"]
        )

    assert result.exit_code == 1
    assert "requires the optional 'all' extras" in result.stderr


def test_crawl_help_uses_download_delay():
    result = runner.invoke(app, ["crawl", "--help"])
    stdout = _plain_output(result.stdout)
    assert result.exit_code == 0
    assert "--download-delay" in stdout


def test_export_help_uses_small_limit_and_output_dir():
    result = runner.invoke(app, ["export", "--help"])
    stdout = _plain_output(result.stdout)
    assert result.exit_code == 0
    assert "--output-dir" in stdout
    assert "--small-limit" in stdout


def test_sync_help_uses_all_formats():
    result = runner.invoke(app, ["sync", "--help"])
    stdout = _plain_output(result.stdout)
    assert result.exit_code == 0
    assert "--all-formats" in stdout


def test_distill_help_uses_working_dir_and_quote_filters():
    result = runner.invoke(app, ["distill", "--help"])
    stdout = _plain_output(result.stdout)
    assert result.exit_code == 0
    assert "--working-dir" in stdout
    assert "--quote-min-chars" in stdout
    assert "--quote-min-words" in stdout
    assert "--quote-min-likes" in stdout


def test_export_command_missing_db(tmp_path):
    working_dir = tmp_path / "empty_dir"
    os.makedirs(working_dir)
    # Check stderr for the error message
    result = runner.invoke(app, ["export", "--working-dir", str(working_dir)])
    assert result.exit_code == 1
    assert "Distilled database not found" in result.stderr


def test_export_with_mock_db(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes-distilled.db"
    # Create an empty db file to pass the existence check
    open(db_path, "a").close()

    output_dir = tmp_path / "output"

    with (
        patch("zen_prompt.commands.export.sqlite3.connect") as mock_connect,
        patch("zen_prompt.commands.export.optimize_db"),
        patch("zen_prompt.commands.export.create_subset_db"),
        patch("zen_prompt.commands.export.get_all_quotes") as mock_get_quotes,
    ):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_get_quotes.return_value = []

        result = runner.invoke(
            app,
            [
                "export",
                "--working-dir",
                str(working_dir),
                "--output-dir",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Successfully exported" in result.stdout


def test_random_command(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
        patch("zen_prompt.commands.random.render_photo") as mock_render_photo,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": "Random quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["tag1"],
        }
        # Test without verbose
        result = runner.invoke(
            app, ["random", "--no-photo", "--working-dir", str(working_dir)]
        )
        assert result.exit_code == 0
        assert "Random quote" in result.stdout
        assert "Author" in result.stdout
        assert "Tags:" not in result.stdout
        mock_render_photo.assert_not_called()

        # Test with verbose
        result = runner.invoke(
            app,
            ["random", "--no-photo", "--verbose", "--working-dir", str(working_dir)],
        )
        assert result.exit_code == 0
        assert "Random quote" in result.stdout
        assert "Tags: tag1" in result.stdout
        mock_render_photo.assert_not_called()


def test_random_passes_quote_length_filters(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": "Random quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["tag1"],
        }
        result = runner.invoke(
            app,
            [
                "random",
                "--no-photo",
                "--quote-max-words",
                "10",
                "--quote-max-chars",
                "80",
                "--working-dir",
                str(working_dir),
            ],
        )
        assert result.exit_code == 0
        mock_get_random.assert_called_with(
            ANY,
            tags=None,
            authors=None,
            min_likes=0,
            max_words=10,
            max_chars=80,
        )


def test_random_wraps_long_quote_with_quote_width(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"
    long_quote = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": long_quote,
            "author": "Author",
            "book_title": "Book",
            "tags": ["tag1"],
        }

        result = runner.invoke(
            app,
            [
                "random",
                "--no-photo",
                "--quote-width",
                "20",
                "--working-dir",
                str(working_dir),
            ],
        )
        assert result.exit_code == 0
        assert '"alpha beta gamma' in result.stdout
        assert "delta epsilon zeta" in result.stdout
        assert "eta theta iota kappa" in result.stdout


def test_random_wraps_long_attribution_with_quote_width(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": "Short quote",
            "author": "Firstname Middlename Lastname",
            "book_title": "An Extremely Long Book Title",
            "tags": ["tag1"],
        }

        result = runner.invoke(
            app,
            [
                "random",
                "--no-photo",
                "--quote-width",
                "25",
                "--working-dir",
                str(working_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Firstname Middlename" in result.stdout
        assert "Lastname (from 'An" in result.stdout
        assert "Extremely Long Book" in result.stdout


def test_search_command(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.search.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.search.sqlite3.connect"),
        patch("zen_prompt.commands.search.search_quotes") as mock_search,
    ):
        mock_get_db.return_value = str(db_path)
        mock_search.return_value = [
            {
                "text": "Found quote",
                "author": "Author",
                "book_title": "Book",
                "tags": ["tag1"],
            }
        ]

        result = runner.invoke(
            app, ["search", "query", "--working-dir", str(working_dir)]
        )
        assert result.exit_code == 0
        assert "Found quote" in result.stdout
        assert "Author" in result.stdout
        assert "tag1" in result.stdout


def test_sync_rejects_removed_all_alias(tmp_path):
    working_dir = tmp_path / "data_all"

    result = runner.invoke(app, ["sync", "--working-dir", str(working_dir), "--all"])
    assert result.exit_code != 0
    assert "No such option" in result.stderr


def test_sync_command_default_only_sqlite(tmp_path):
    working_dir = tmp_path / "data"

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        # Return a valid JSON for manifest.json, then dummy data for others
        mock_response.read.side_effect = [
            b'{"version": "2026.03.26", "total_quotes": 100}',  # remote manifest.json
            b"fake data",  # sqlite/quotes.db
            b"fake data",  # sqlite/quotes-small.db
        ]
        mock_urlopen.return_value = mock_response

        # Test default (only sqlite)
        result = runner.invoke(app, ["sync", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        assert "SQLite database" in result.stdout
        assert "Small SQLite database" in result.stdout
        assert "CSV quotes" not in result.stdout
        assert "JSON quotes" not in result.stdout
        assert os.path.exists(working_dir / "sqlite" / "quotes.db")
        assert not os.path.exists(working_dir / "csv" / "quotes.csv")
        assert not os.path.exists(working_dir / "csv" / "quotes-small.csv")
        assert not os.path.exists(working_dir / "json" / "quotes.json")
        assert not os.path.exists(working_dir / "json" / "quotes-small.json")


def test_sync_command_all_formats(tmp_path):
    working_dir = tmp_path / "data_all"

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.side_effect = [
            b'{"version": "2026.03.26", "total_quotes": 100}',  # remote manifest.json
            b"fake data",  # sqlite/quotes.db
            b"fake data",  # sqlite/quotes-small.db
            b"fake data",  # csv/quotes.csv
            b"fake data",  # csv/quotes-small.csv
            b"fake data",  # json/quotes.json
            b"fake data",  # json/quotes-small.json
        ]
        mock_urlopen.return_value = mock_response

        # Test with --all-formats
        result = runner.invoke(
            app, ["sync", "--working-dir", str(working_dir), "--all-formats"]
        )
        assert result.exit_code == 0
        assert "SQLite database" in result.stdout
        assert "CSV quotes" in result.stdout
        assert "JSON quotes" in result.stdout
        assert os.path.exists(working_dir / "sqlite" / "quotes.db")
        assert os.path.exists(working_dir / "csv" / "quotes.csv")
        assert os.path.exists(working_dir / "json" / "quotes.json")


def test_stat_command(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.stat.utils.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.stat.sqlite3.connect"),
        patch("zen_prompt.commands.stat.db.get_stats") as mock_get_stats,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_stats.return_value = {
            "total_quotes": 100,
            "total_authors": 10,
            "total_likes": 500,
            "top_authors": [{"author": "Author A", "count": 20, "likes": 100}],
            "top_tags": [{"tag": "tag1", "count": 50}],
            "top_liked_quotes": [
                {"id": 1, "text": "Top liked", "author": "Author A", "likes": 100}
            ],
            "avg_length": 150.0,
            "min_length": 10,
            "max_length": 500,
            "avg_words": 20.0,
            "min_words": 2,
            "max_words": 100,
            "longest_quotes": [
                {"id": 1, "text": "Long quote", "author": "Author A", "length": 500}
            ],
            "shortest_quotes": [
                {"id": 2, "text": "Short", "author": "Author B", "length": 10}
            ],
            "similar_authors": [],
        }

        # Test standard output
        result = runner.invoke(app, ["stat", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        assert "Total Quotes" in result.stdout
        assert "100" in result.stdout
        assert "Total Authors" in result.stdout
        assert "10" in result.stdout
        assert "Total Likes" in result.stdout
        assert "500" in result.stdout
        assert "Author A" in result.stdout
        assert "tag1" in result.stdout
        assert "150.0" in result.stdout
        assert "20.0" in result.stdout
        # Rich might render [1] differently or keep it
        assert "1" in result.stdout
        assert "2" in result.stdout

        # Test output to file
        output_file = tmp_path / "stats.md"
        result = runner.invoke(
            app,
            ["stat", "--output", str(output_file), "--working-dir", str(working_dir)],
        )
        assert result.exit_code == 0
        assert f"Statistics saved to {output_file}" in result.stdout
        assert os.path.exists(output_file)
        with open(output_file, "r") as f:
            content = f.read()
            assert "# 📊 Quote Database Statistics" in content
            assert "**Total Quotes:**  100" in content


def test_distill_rejects_removed_filter_aliases(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)

    for option in ("--min-length", "--min-words", "--min-likes"):
        result = runner.invoke(
            app,
            ["distill", "--working-dir", str(working_dir), option, "1", "--force"],
        )
        assert result.exit_code != 0
        assert "No such option" in result.stderr


def test_distill_command(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    raw_db_path = working_dir / "quotes-raw.db"
    raw_db_path.write_text("db")
    distilled_db_path = working_dir / "quotes-distilled.db"

    with (
        patch("zen_prompt.commands.distill.db.copy_database") as mock_copy_database,
        patch("zen_prompt.commands.distill.db.init_db") as mock_init_db,
        patch("zen_prompt.commands.distill.sqlite3.connect") as mock_connect,
        patch("zen_prompt.commands.distill.db.distill_quotes") as mock_distill,
        patch("zen_prompt.commands.distill.db.repopulate_fts"),
    ):
        mock_distill.return_value = (5, 0)

        # Test with force to avoid confirmation
        result = runner.invoke(
            app,
            [
                "distill",
                "--force",
                "--working-dir",
                str(working_dir),
                "--quote-min-chars",
                "1",
                "--quote-min-words",
                "2",
                "--lowercase",
                "--uppercase",
            ],
        )
        assert result.exit_code == 0
        assert "Successfully removed 5 quotes" in result.stdout
        assert "Rebuilding search index" in result.stdout
        assert "VACUUM" in result.stdout
        mock_copy_database.assert_called_once_with(
            str(raw_db_path), str(distilled_db_path)
        )
        mock_init_db.assert_called_once_with(str(distilled_db_path))

        mock_distill.assert_called_with(
            mock_connect.return_value,
            min_length=1,
            min_words=2,
            min_likes=100,
            remove_lowercase=True,
            remove_uppercase=True,
            normalize=True,
        )


def test_get_command(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.get.utils.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.get.sqlite3.connect"),
        patch("zen_prompt.commands.get.db.get_quote_by_id") as mock_get_quote,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_quote.return_value = {
            "id": 1,
            "text": "Specific quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["tag1"],
            "likes": 100,
            "link": "https://example.com/1",
        }

        # Test without verbose
        result = runner.invoke(app, ["get", "1", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        assert "Specific quote" in result.stdout
        assert "Author" in result.stdout
        assert "Tags:" not in result.stdout
        assert "Likes:" not in result.stdout

        # Test with verbose
        result = runner.invoke(
            app, ["get", "1", "-v", "--working-dir", str(working_dir)]
        )
        assert result.exit_code == 0
        assert "Specific quote" in result.stdout
        assert "tag1" in result.stdout
        assert "100" in result.stdout
        assert "https://example.com/1" in result.stdout


def test_random_with_topic_photo_option(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
        patch("zen_prompt.commands.random.render_photo") as mock_render_photo,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": "Random quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["love"],
        }

        result = runner.invoke(
            app,
            [
                "random",
                "--photo",
                "topic@monochrome",
                "--photo-layout",
                "stack",
                "--photo-max-height",
                "12",
                "--photo-max-width",
                "48",
                "--working-dir",
                str(working_dir),
            ],
        )
        assert result.exit_code == 0
        mock_render_photo.assert_called_with(
            "topic@monochrome",
            image_max_height=12,
            image_max_width=48,
        )


def test_random_with_table_photo_layout(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
        patch(
            "zen_prompt.commands.random._render_photo_table_layout"
        ) as mock_render_table,
        patch("zen_prompt.commands.random.render_photo") as mock_render_photo,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": "Random quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["love"],
        }

        result = runner.invoke(
            app,
            [
                "random",
                "--photo",
                "topic@monochrome",
                "--photo-layout",
                "table",
                "--photo-max-height",
                "12",
                "--photo-max-width",
                "48",
                "--working-dir",
                str(working_dir),
            ],
        )
        assert result.exit_code == 0
        mock_render_table.assert_called_once_with(
            mock_get_random.return_value,
            "topic@monochrome",
            image_max_height=12,
            image_max_width=48,
            verbose=False,
            quote_width=80,
        )
        mock_render_photo.assert_not_called()
        assert "Random quote" not in result.stdout


def test_random_with_file_photo_option(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"
    image_path = tmp_path / "fixed.png"
    PILImage.new("RGB", (4, 4), "red").save(image_path)

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
        patch("zen_prompt.commands.random.render_photo") as mock_render_photo,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": "Random quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["love"],
        }

        result = runner.invoke(
            app,
            [
                "random",
                "--photo",
                f"file@{image_path}",
                "--photo-layout",
                "stack",
                "--working-dir",
                str(working_dir),
            ],
        )
        assert result.exit_code == 0
        mock_render_photo.assert_called_with(
            f"file@{image_path}",
            image_max_height=10,
            image_max_width=None,
        )


def test_random_with_invalid_photo_option():
    result = runner.invoke(app, ["random", "--photo", "unknown-mode"])
    assert result.exit_code == 2
    assert "Photo mode must be one of" in result.stderr


def test_random_rejects_removed_image_photo_mode():
    result = runner.invoke(app, ["random", "--photo", "image"])
    assert result.exit_code == 2
    assert "Photo mode must be one of" in result.stderr


def test_random_with_invalid_photo_layout():
    result = runner.invoke(app, ["random", "--photo-layout", "grid"])
    assert result.exit_code == 2
    assert "Photo layout must be one of" in result.stderr


def test_random_with_removed_no_art_option():
    result = runner.invoke(app, ["random", "--no-art"])
    assert result.exit_code != 0
    assert "No such option" in result.stderr


def test_random_with_no_photo_option(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
        patch("zen_prompt.commands.random.render_photo") as mock_render_photo,
        patch(
            "zen_prompt.commands.random._render_photo_table_layout"
        ) as mock_render_table,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": "Random quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["love"],
        }

        result = runner.invoke(
            app, ["random", "--no-photo", "--working-dir", str(working_dir)]
        )
        assert result.exit_code == 0
        assert "Random quote" in result.stdout
        mock_render_photo.assert_not_called()
        mock_render_table.assert_not_called()


def test_random_passes_topic_mode_to_renderer(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
        patch("zen_prompt.commands.random.render_photo") as mock_render_photo,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": "Random quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["love"],
        }

        result = runner.invoke(
            app,
            [
                "random",
                "--photo",
                "topic@monochrome",
                "--photo-layout",
                "stack",
                "--working-dir",
                str(working_dir),
            ],
        )
        assert result.exit_code == 0
        mock_render_photo.assert_called_with(
            "topic@monochrome",
            image_max_height=10,
            image_max_width=None,
        )


def test_random_with_removed_photo_topic_option():
    result = runner.invoke(app, ["random", "--photo-topic", "nature"])
    assert result.exit_code != 0
    assert "No such option" in result.stderr


def test_random_uses_monochrome_photo_by_default(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)
    db_path = working_dir / "quotes.db"

    with (
        patch("zen_prompt.commands.random.get_cached_db") as mock_get_db,
        patch("zen_prompt.commands.random.connect_db"),
        patch("zen_prompt.commands.random.get_random_quote") as mock_get_random,
        patch(
            "zen_prompt.commands.random._render_photo_table_layout"
        ) as mock_render_table,
    ):
        mock_get_db.return_value = str(db_path)
        mock_get_random.return_value = {
            "id": 1,
            "text": "Random quote",
            "author": "Author",
            "book_title": "Book",
            "tags": ["love"],
        }

        result = runner.invoke(app, ["random", "--working-dir", str(working_dir)])
        assert result.exit_code == 0
        mock_render_table.assert_called_once_with(
            mock_get_random.return_value,
            "topic@monochrome",
            image_max_height=10,
            image_max_width=None,
            verbose=False,
            quote_width=80,
        )


def test_random_rejects_invalid_image_size(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)

    result = runner.invoke(
        app,
        [
            "random",
            "--photo",
            "topic@monochrome",
            "--photo-max-height",
            "0",
            "--working-dir",
            str(working_dir),
        ],
    )
    assert result.exit_code == 2
    assert "Invalid value for '--photo-max-height'" in _plain_output(result.stderr)


def test_random_rejects_invalid_quote_length_filters(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)

    result = runner.invoke(
        app,
        [
            "random",
            "--no-photo",
            "--quote-max-words",
            "0",
            "--working-dir",
            str(working_dir),
        ],
    )
    assert result.exit_code == 2
    assert "Invalid value for '--quote-max-words'" in _plain_output(result.stderr)

    result = runner.invoke(
        app,
        [
            "random",
            "--no-photo",
            "--quote-max-chars",
            "0",
            "--working-dir",
            str(working_dir),
        ],
    )
    assert result.exit_code == 2
    assert "Invalid value for '--quote-max-chars'" in _plain_output(result.stderr)


def test_export_rejects_removed_output_alias(tmp_path):
    working_dir = tmp_path / "data/sqlite"
    os.makedirs(working_dir)

    result = runner.invoke(
        app, ["export", "--output", str(tmp_path), "--working-dir", str(working_dir)]
    )
    assert result.exit_code != 0
    assert "No such option" in result.stderr
