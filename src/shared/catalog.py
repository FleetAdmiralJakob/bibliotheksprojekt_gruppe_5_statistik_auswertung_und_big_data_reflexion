"""Geteilte Fachwerte am Interface der Katalogansicht."""

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from src.shared.domain_values import (
    Kategorie,
    Verfuegbarkeitsklasse,
)
from src.shared.models import BookMetadata


class SharedModel(BaseModel):
    """Unveränderliches Pydantic-Modell am Client-Server-Seam."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Sortierfeld(StrEnum):
    """Fachlich sortierbare Spalten der Katalogansicht."""

    ISBN = "isbn"
    TITEL = "title"
    AUTOR = "author"
    KATEGORIE = "category"
    SPRACHE = "language"
    ERSCHEINUNG = "year"
    EXEMPLARE = "copies"


class Sortierung(SharedModel):
    """Gewähltes Sortierfeld und seine Richtung."""

    feld: Sortierfeld
    absteigend: bool = False


class Katalogsuche(SharedModel):
    """Alle Filter und die optionale Sortierung einer Katalogabfrage."""

    titel: str = ""
    autor: str = ""
    kategorie: Kategorie | None = None
    isbn: str = ""
    sortierung: Sortierung | None = None


class Katalogzeile(SharedModel):
    """Fertig aufbereitete Zeile der Buchergebnisliste."""

    isbn: str
    titel: str
    autoren: str
    kategorie: str
    sprache: str
    erscheinung: str
    exemplarzahl: int


class Katalogseite(SharedModel):
    """Ergebnis einer Suche mit Zeilen und passendem Statustext."""

    zeilen: tuple[Katalogzeile, ...]
    status: str


class Exemplarzeile(SharedModel):
    """Aufbereitetes Exemplar für die Detailansicht."""

    exemplar_id: str
    zustand: str
    verfuegbarkeit: str
    klasse: Verfuegbarkeitsklasse


class Buchansicht(SharedModel):
    """Vollständige Katalogansicht eines Buches und seiner Exemplare."""

    isbn: str
    titel: str
    metadatenzeile: str
    exemplarzusammenfassung: str
    exemplare: tuple[Exemplarzeile, ...]


class KatalogansichtFehler(RuntimeError):
    """Stabiler Fehlertyp für nicht lesbare Katalogdaten."""


class BuchNichtGefunden(KatalogansichtFehler):
    """Das angeforderte Buch ist im Bibliotheksbestand nicht vorhanden."""


class Bibliothekszugang(Protocol):
    """Transport-unabhängiges Interface des Desktop-Clients zum Server."""

    def suchen(self, suche: Katalogsuche) -> Katalogseite:
        """Liefert eine aufbereitete Katalogseite."""

    def buch(self, isbn: str) -> Buchansicht:
        """Liefert die Katalogansicht eines Buches."""

    def buch_aufnehmen(
        self,
        isbn: str,
        exemplaranzahl: int | str,
    ) -> BookMetadata:
        """Nimmt ein Buch mit Exemplaren in den Bibliotheksbestand auf."""

    def buch_entfernen(self, isbn: str) -> str:
        """Entfernt ein Buch aus dem Bibliotheksbestand."""
