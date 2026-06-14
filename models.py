"""Gemeinsame Fachbegriffe an den Interfaces der Bibliotheksmodule.

Die Klassen in diesem Modul beschreiben Daten, die zwischen Modulen
ausgetauscht werden. SQLite-Zeilen und externe JSON-Strukturen bleiben dadurch
Implementierungsdetails der jeweiligen Module.
"""

from dataclasses import dataclass
from typing import TypedDict


@dataclass(frozen=True, slots=True)
class BookSearchResult:
    """Ein Buch, wie es die Katalogsuche an Aufrufer zurückgibt."""

    isbn: str
    title: str | None
    authors: str | None
    main_category: str | None
    language: str | None
    release_date: str | None
    copy_count: int


@dataclass(frozen=True, slots=True)
class BookCopy:
    """Ein physisches Exemplar mit Zustand und Verfügbarkeit."""

    copy_id: str
    state: str | None
    availability: str | None


class BookMetadata(TypedDict):
    """Geprüfte Metadaten, die zum Speichern eines Buches benötigt werden."""

    isbn: str
    title: str
    authors: list[str]
    publisher: str
    release_date: str
    page_count: int
    language: str
    main_category: str
