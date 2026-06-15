"""Gemeinsame Fachbegriffe an den Interfaces der Bibliotheksmodule.

Die Pydantic-Modelle in diesem Modul werden von Server und Client gemeinsam
verwendet. SQLite-Zeilen und externe JSON-Strukturen bleiben
Implementierungsdetails der serverseitigen Module.
"""

from pydantic import BaseModel, ConfigDict

from src.shared.domain_values import Kategorie


class BookMetadata(BaseModel):
    """Geprüfte Metadaten, die zum Speichern eines Buches benötigt werden."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    isbn: str
    title: str
    authors: tuple[str, ...]
    publisher: str
    release_date: str
    page_count: int
    language: str
    main_category: Kategorie
