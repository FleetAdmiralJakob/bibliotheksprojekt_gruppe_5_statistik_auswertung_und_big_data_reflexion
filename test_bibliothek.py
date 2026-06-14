import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import database
from bibliothek import add_book, normalize_isbn


class IsbnTests(unittest.TestCase):
    def test_normalizes_valid_isbn(self):
        self.assertEqual(normalize_isbn("978-3-596-18094-3"), "9783596180943")
        self.assertEqual(normalize_isbn("0-306-40615-2"), "0306406152")

    def test_rejects_invalid_isbn(self):
        with self.assertRaises(ValueError):
            normalize_isbn("9783596180944")


class AddBookTests(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            self.database_path = Path(temp_file.name)

        schema_path = Path(__file__).parent / "sql_scripts" / "create_database.sql"
        with (
            closing(sqlite3.connect(self.database_path)) as connection,
            connection,
        ):
            connection.executescript(schema_path.read_text(encoding="utf-8"))

        self.database_patch = patch.object(
            database, "DATABASE_PATH", self.database_path
        )
        self.database_patch.start()

    def tearDown(self):
        self.database_patch.stop()
        self.database_path.unlink(missing_ok=True)

    @patch("bibliothek.fetch_book_metadata")
    def test_adds_metadata_relations_and_requested_copies(self, fetch_metadata):
        fetch_metadata.return_value = {
            "isbn": "9780306406157",
            "title": "Test Book",
            "authors": ["Ada Example", "Max Example"],
            "publisher": "Test Publisher",
            "release_date": "2026",
            "page_count": 240,
            "language": "Englisch",
            "main_category": "Science",
        }

        add_book("978-0-306-40615-7", 3)

        with closing(sqlite3.connect(self.database_path)) as connection:
            book = connection.execute(
                """
                SELECT title, main_category, language, release_date, page_count
                FROM books WHERE isbn = ?
                """,
                ("9780306406157",),
            ).fetchone()
            author_count = connection.execute(
                "SELECT COUNT(*) FROM book_authors WHERE isbn = ?",
                ("9780306406157",),
            ).fetchone()[0]
            copies = connection.execute(
                """
                SELECT state, availability
                FROM book_copies WHERE isbn = ? ORDER BY copy_id
                """,
                ("9780306406157",),
            ).fetchall()

        self.assertEqual(book, ("Test Book", "Science", "Englisch", "2026", 240))
        self.assertEqual(author_count, 2)
        self.assertEqual(copies, [("new", "available")] * 3)


if __name__ == "__main__":
    unittest.main()
