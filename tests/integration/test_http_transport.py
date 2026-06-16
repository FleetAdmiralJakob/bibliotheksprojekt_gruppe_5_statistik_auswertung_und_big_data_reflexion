"""Tests über den FastAPI- und HTTPX-Seam zwischen Desktop und Server."""

import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import uvicorn

from src.desktop.http_adapter import HttpBibliothekszugang
from src.server.backend import Bibliotheksbackend
from src.server.bestand import Bibliotheksbestand
from src.server.http_adapter import create_app
from src.shared.catalog import Katalogsuche
from src.shared.domain_values import (
    Exemplarverfuegbarkeit,
    Exemplarzustand,
    Kategorie,
)
from src.shared.models import BookMetadata


class HttpTransportTests(unittest.TestCase):
    """Prüft Pydantic-Modelle über FastAPI, Uvicorn und HTTPX."""

    def setUp(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            self.database_path = Path(temp_file.name)

        bestand = Bibliotheksbestand(database_path=self.database_path)
        bestand.recreate()
        app = create_app(Bibliotheksbackend(bestand))

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen()
        port = self.socket.getsockname()[1]

        config = uvicorn.Config(
            app,
            log_level="error",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.server_thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [self.socket]},
            daemon=True,
        )
        self.server_thread.start()

        deadline = time.monotonic() + 5
        while not self.server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        if not self.server.started:
            self.fail("Der Uvicorn-Testserver ist nicht gestartet.")

        self.http_client = httpx.Client(base_url=f"http://127.0.0.1:{port}")
        self.client = HttpBibliothekszugang(
            f"http://127.0.0.1:{port}",
            client=self.http_client,
        )

    def tearDown(self):
        self.http_client.close()
        self.server.should_exit = True
        self.server_thread.join(timeout=5)
        self.socket.close()
        self.database_path.unlink(missing_ok=True)

    @staticmethod
    def metadata() -> BookMetadata:
        return BookMetadata(
            isbn="9780306406157",
            title="Remote Test",
            authors=("Ada Example",),
            publisher="Test Publisher",
            release_date="2026",
            page_count=200,
            language="Deutsch",
            main_category=Kategorie.TECHNOLOGIE,
        )

    @patch("src.server.buchlebenszyklus.fetch_book_metadata")
    def test_full_book_lifecycle_crosses_http_seam(self, fetch_metadata):
        """Desktop und Server teilen Pydantic-Modelle, keine Implementierung."""

        fetch_metadata.return_value = self.metadata()

        self.assertTrue(self.client.health())
        metadata = self.client.buch_aufnehmen("978-0-306-40615-7", 2)
        page = self.client.suchen(Katalogsuche(isbn=metadata.isbn))
        book = self.client.exemplare_hinzufuegen(metadata.isbn, 2)
        updated_book = self.client.exemplarstatus_aendern(
            metadata.isbn,
            "9780306406157-002",
            Exemplarzustand.GUT,
            Exemplarverfuegbarkeit.RESERVIERT,
        )
        book_after_copy_deletion = self.client.exemplar_entfernen(
            metadata.isbn,
            "9780306406157-003",
        )
        removed_isbn = self.client.buch_entfernen(metadata.isbn)

        self.assertEqual(page.zeilen[0].titel, "Remote Test")
        self.assertEqual(len(book.exemplare), 4)
        self.assertEqual(book.exemplare[-1].exemplar_id, "9780306406157-004")
        self.assertEqual(updated_book.exemplare[1].zustand, Exemplarzustand.GUT.label)
        self.assertEqual(
            updated_book.exemplare[1].verfuegbarkeit,
            Exemplarverfuegbarkeit.RESERVIERT.label,
        )
        self.assertEqual(len(book_after_copy_deletion.exemplare), 3)
        self.assertNotIn(
            "9780306406157-003",
            [copy.exemplar_id for copy in book_after_copy_deletion.exemplare],
        )
        self.assertEqual(removed_isbn, metadata.isbn)
        self.assertEqual(
            self.client.suchen(Katalogsuche(isbn=metadata.isbn)).zeilen,
            (),
        )

    def test_fastapi_openapi_uses_shared_pydantic_models(self):
        """OpenAPI benennt die geteilten Request- und Response-Modelle."""

        schemas = self.http_client.get("/openapi.json").json()["components"]["schemas"]

        self.assertIn("Katalogsuche", schemas)
        self.assertIn("Katalogseite", schemas)
        self.assertIn("BookMetadata", schemas)
        self.assertIn("BuchaufnahmeRequest", schemas)
        self.assertIn("ExemplaraufnahmeRequest", schemas)
        self.assertIn("ExemplarstatusAenderungRequest", schemas)
