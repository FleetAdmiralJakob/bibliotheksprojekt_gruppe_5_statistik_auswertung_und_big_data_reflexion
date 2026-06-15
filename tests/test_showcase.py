"""Tests für den kombinierten Showcase-Startpunkt."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import showcase_main


class ShowcaseDatabaseTests(unittest.TestCase):
    def test_database_is_seeded_in_local_app_data(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            local_app_data = Path(temporary_directory) / "LocalAppData"
            seed_database = Path(temporary_directory) / "seed.db"
            seed_database.write_bytes(b"seed data")

            with (
                patch.dict(
                    os.environ,
                    {"LOCALAPPDATA": str(local_app_data)},
                    clear=True,
                ),
                patch.object(
                    showcase_main,
                    "resource_path",
                    return_value=seed_database,
                ),
            ):
                database_path = showcase_main.prepare_database()

            self.assertEqual(
                database_path,
                local_app_data
                / showcase_main.APP_DATA_DIRECTORY
                / showcase_main.DATABASE_FILENAME,
            )
            self.assertEqual(database_path.read_bytes(), b"seed data")

    def test_existing_database_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "custom.db"
            database_path.write_bytes(b"existing data")
            seed_database = Path(temporary_directory) / "seed.db"
            seed_database.write_bytes(b"seed data")

            with (
                patch.dict(
                    os.environ,
                    {"BIBLIOTHEK_DATABASE_PATH": str(database_path)},
                    clear=True,
                ),
                patch.object(
                    showcase_main,
                    "resource_path",
                    return_value=seed_database,
                ),
            ):
                result = showcase_main.prepare_database()

            self.assertEqual(result, database_path)
            self.assertEqual(database_path.read_bytes(), b"existing data")
