"""Architekturregeln für die getrennten Desktop- und Serverpakete."""

import unittest
from pathlib import Path


class PackageDependencyTests(unittest.TestCase):
    """Verhindert direkte Serverabhängigkeiten im Desktop-Paket."""

    def test_desktop_does_not_import_server_implementation(self):
        desktop_directory = Path(__file__).resolve().parents[1] / "src" / "desktop"
        desktop_sources = "\n".join(
            path.read_text(encoding="utf-8") for path in desktop_directory.glob("*.py")
        )

        self.assertNotIn("src.server", desktop_sources)

    def test_http_seam_uses_fastapi_and_httpx(self):
        """Verhindert die Rückkehr zu handgeschriebenem Standardbibliothek-HTTP."""

        root = Path(__file__).resolve().parents[1]
        server_adapter = (root / "src" / "server" / "http_adapter.py").read_text(
            encoding="utf-8"
        )
        desktop_adapter = (root / "src" / "desktop" / "http_adapter.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("from fastapi import", server_adapter)
        self.assertNotIn("http.server", server_adapter)
        self.assertIn("import httpx", desktop_adapter)
        self.assertNotIn("urllib.request", desktop_adapter)
