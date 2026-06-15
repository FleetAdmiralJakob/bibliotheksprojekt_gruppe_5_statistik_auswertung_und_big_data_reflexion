"""Tiefe, Tkinter-unabhängige Katalogansicht.

Das Modul übersetzt gespeicherte Bücher und Exemplare in eine für Menschen
lesbare Ansicht. Kategorie, Datumsformat, Sortierwerte, Zustand,
Verfügbarkeit und Zusammenfassungen bleiben hinter diesem Interface.
Tkinter zeichnet die fertigen Werte nur noch und verwendet die ISBN als
stabile Identität eines Buches.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from database import Bibliotheksbestand
from domain_values import (
    Kategorie,
    Verfuegbarkeitsklasse,
    availability_presentation,
    category_label,
    copy_state_label,
)
from models import BookCopy, BookSearchResult


class Sortierfeld(StrEnum):
    """Fachlich sortierbare Spalten der Katalogansicht."""

    ISBN = "isbn"
    TITEL = "title"
    AUTOR = "author"
    KATEGORIE = "category"
    SPRACHE = "language"
    ERSCHEINUNG = "year"
    EXEMPLARE = "copies"


@dataclass(frozen=True, slots=True)
class Sortierung:
    """Gewähltes Sortierfeld und seine Richtung."""

    feld: Sortierfeld
    absteigend: bool = False


@dataclass(frozen=True, slots=True)
class Katalogsuche:
    """Alle Filter und die optionale Sortierung einer Katalogabfrage."""

    titel: str = ""
    autor: str = ""
    kategorie: Kategorie | None = None
    isbn: str = ""
    sortierung: Sortierung | None = None


@dataclass(frozen=True, slots=True)
class Katalogzeile:
    """Fertig aufbereitete Zeile der Buchergebnisliste."""

    isbn: str
    titel: str
    autoren: str
    kategorie: str
    sprache: str
    erscheinung: str
    exemplarzahl: int


@dataclass(frozen=True, slots=True)
class Katalogseite:
    """Ergebnis einer Suche mit Zeilen und passendem Statustext."""

    zeilen: tuple[Katalogzeile, ...]
    status: str


@dataclass(frozen=True, slots=True)
class Exemplarzeile:
    """Aufbereitetes Exemplar für die Detailansicht."""

    exemplar_id: str
    zustand: str
    verfuegbarkeit: str
    klasse: Verfuegbarkeitsklasse


@dataclass(frozen=True, slots=True)
class Buchansicht:
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


class Katalogansicht:
    """Bereitet den Bibliotheksbestand für eine menschliche Ansicht auf.

    Das Interface besitzt nur zwei Operationen: eine Ergebnisliste suchen und
    ein Buch anhand seiner zuvor ausgegebenen ISBN öffnen. Der Zustand einer
    konkreten Tkinter-Tabelle gehört nicht zur Implementierung dieses Moduls.
    """

    def __init__(self, bestand: Bibliotheksbestand) -> None:
        """Verbindet die Ansicht mit dem bestehenden Bibliotheksbestand."""

        self._bestand = bestand

    def suchen(self, suche: Katalogsuche) -> Katalogseite:
        """Sucht, sortiert und formatiert Bücher ohne sichtbaren Text zu parsen."""

        category_query = suche.kategorie.value if suche.kategorie else ""

        try:
            books = self._bestand.search_books(
                book_query=suche.titel.strip(),
                author_query=suche.autor.strip(),
                category_query=category_query,
                isbn_query=suche.isbn.strip(),
            )
        except RuntimeError as error:
            # SQLite-Details bleiben hinter dem Bibliotheksbestand. Die
            # Katalogansicht ergänzt nur den Kontext der fehlgeschlagenen Sicht.
            raise KatalogansichtFehler(
                "Die Bibliotheksdaten konnten nicht geladen werden."
            ) from error

        ordered_books = self._sort_books(books, suche.sortierung)
        rows = tuple(self._book_row(book) for book in ordered_books)
        count = len(rows)
        status = (
            f"{count} Treffer gefunden" if count else "Keine passenden Bücher gefunden"
        )
        return Katalogseite(zeilen=rows, status=status)

    def buch(self, isbn: str) -> Buchansicht:
        """Lädt ein Buch exakt über seine ISBN und bereitet Exemplare auf."""

        try:
            # Die Bestandsabfrage unterstützt Teiltexte. Die zusätzliche exakte
            # Prüfung verhindert deshalb, dass eine Teil-ISBN das falsche Buch
            # für die Detailansicht auswählt.
            matches = self._bestand.search_books(
                book_query="",
                author_query="",
                category_query="",
                isbn_query=isbn,
            )
            book = next((entry for entry in matches if entry.isbn == isbn), None)
            if book is None:
                raise BuchNichtGefunden("Ein Buch mit dieser ISBN ist nicht vorhanden.")

            copies = self._bestand.get_book_copies(isbn)
        except BuchNichtGefunden:
            raise
        except ValueError as error:
            # Das Buch kann zwischen Ergebnisliste und Detailaufruf gelöscht
            # worden sein. Für den Aufrufer ist das ein fehlendes Buch.
            raise BuchNichtGefunden(
                "Ein Buch mit dieser ISBN ist nicht vorhanden."
            ) from error
        except RuntimeError as error:
            raise KatalogansichtFehler(
                "Die Exemplare dieses Buches konnten nicht geladen werden."
            ) from error

        copy_rows = tuple(self._copy_row(copy) for copy in copies)
        return Buchansicht(
            isbn=book.isbn,
            titel=self._text(book.title) or book.isbn,
            metadatenzeile=self._metadata_line(book),
            exemplarzusammenfassung=self._copies_summary(copy_rows),
            exemplare=copy_rows,
        )

    @classmethod
    def _book_row(cls, book: BookSearchResult) -> Katalogzeile:
        """Bildet einen gespeicherten Buchtreffer auf sichtbare Werte ab."""

        return Katalogzeile(
            isbn=book.isbn,
            titel=cls._text(book.title),
            autoren=cls._text(book.authors),
            kategorie=cls._category_label(book.main_category),
            sprache=cls._text(book.language),
            erscheinung=cls._format_date(book.release_date),
            exemplarzahl=book.copy_count,
        )

    @classmethod
    def _copy_row(cls, copy: BookCopy) -> Exemplarzeile:
        """Übersetzt Zustand und Verfügbarkeit eines Exemplars genau einmal."""

        state_label = copy_state_label(copy.state)
        availability_label, availability_class = availability_presentation(
            copy.availability
        )
        return Exemplarzeile(
            exemplar_id=copy.copy_id,
            zustand=state_label,
            verfuegbarkeit=availability_label,
            klasse=availability_class,
        )

    @classmethod
    def _metadata_line(cls, book: BookSearchResult) -> str:
        """Erzeugt die kompakte Metadatenzeile der Buchdetailansicht."""

        parts = [f"ISBN: {book.isbn}"]
        if book.authors:
            parts.append(f"Autor: {book.authors}")
        if book.main_category:
            parts.append(f"Kategorie: {cls._category_label(book.main_category)}")
        if book.language:
            parts.append(f"Sprache: {book.language}")
        if book.release_date:
            parts.append(f"Erscheinung: {cls._format_date(book.release_date)}")
        return " · ".join(parts)

    @staticmethod
    def _copies_summary(copies: tuple[Exemplarzeile, ...]) -> str:
        """Fasst die sichtbaren Verfügbarkeiten deterministisch zusammen."""

        if not copies:
            return "Für dieses Buch sind keine Exemplare gespeichert."

        # Counter bewahrt die Reihenfolge des ersten Auftretens. Da Exemplare
        # nach ihrer ID geladen werden, bleibt die Zusammenfassung stabil.
        availability_counts = Counter(copy.verfuegbarkeit for copy in copies)
        details = ", ".join(
            f"{count} {label}" for label, count in availability_counts.items()
        )
        noun = "Exemplar" if len(copies) == 1 else "Exemplare"
        return f"{len(copies)} {noun} insgesamt · {details}"

    @classmethod
    def _sort_books(
        cls,
        books: list[BookSearchResult],
        ordering: Sortierung | None,
    ) -> list[BookSearchResult]:
        """Sortiert auf Rohwerten; sichtbare Texte werden nie zurückgeparst."""

        field = ordering.feld if ordering else Sortierfeld.TITEL
        descending = ordering.absteigend if ordering else False

        # ISBN und Titel bilden eine stabile aufsteigende Grundordnung. Die
        # anschließende stabile Sortierung nach dem gewählten Feld erhält diese
        # Reihenfolge für gleiche Werte.
        ordered = sorted(
            books,
            key=lambda book: (
                cls._text(book.title).casefold(),
                book.isbn.casefold(),
            ),
        )

        populated = [
            book for book in ordered if not cls._is_empty_sort_value(book, field)
        ]
        empty = [book for book in ordered if cls._is_empty_sort_value(book, field)]
        populated.sort(
            key=lambda book: cls._sort_value(book, field),
            reverse=descending,
        )
        return [*populated, *empty]

    @classmethod
    def _is_empty_sort_value(
        cls,
        book: BookSearchResult,
        field: Sortierfeld,
    ) -> bool:
        """Erkennt leere Werte, die in beiden Richtungen unten bleiben."""

        if field is Sortierfeld.EXEMPLARE:
            return False
        return cls._sort_source(book, field) in (None, "")

    @classmethod
    def _sort_value(
        cls,
        book: BookSearchResult,
        field: Sortierfeld,
    ) -> Any:
        """Liefert vergleichbare Rohwerte für das gewählte Sortierfeld."""

        value = cls._sort_source(book, field)
        if field is Sortierfeld.EXEMPLARE:
            return book.copy_count
        if field is Sortierfeld.ERSCHEINUNG:
            return cls._date_sort_value(value)
        if field is Sortierfeld.KATEGORIE:
            return cls._category_label(cls._text(value)).casefold()
        return cls._text(value).casefold()

    @staticmethod
    def _sort_source(
        book: BookSearchResult,
        field: Sortierfeld,
    ) -> str | int | None:
        """Ordnet ein Sortierfeld dem unveränderten Bestandswert zu."""

        values: dict[Sortierfeld, str | int | None] = {
            Sortierfeld.ISBN: book.isbn,
            Sortierfeld.TITEL: book.title,
            Sortierfeld.AUTOR: book.authors,
            Sortierfeld.KATEGORIE: book.main_category,
            Sortierfeld.SPRACHE: book.language,
            Sortierfeld.ERSCHEINUNG: book.release_date,
            Sortierfeld.EXEMPLARE: book.copy_count,
        }
        return values[field]

    @staticmethod
    def _date_sort_value(value: str | int | None) -> tuple[Any, ...]:
        """Normalisiert vollständige Daten, Jahreszahlen und unbekannte Texte."""

        text = str(value or "").strip()
        for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                parsed = datetime.strptime(text, date_format)
                return (0, parsed.year, parsed.month, parsed.day)
            except ValueError:
                continue

        if text.isdigit() and len(text) == 4:
            return (0, int(text), 0, 0)

        # Unbekannte Altformate bleiben sichtbar und werden nach gültigen
        # Datumswerten alphabetisch eingeordnet.
        return (1, text.casefold())

    @staticmethod
    def _format_date(value: str | None) -> str:
        """Formatiert ISO-Daten deutsch und lässt unvollständige Werte intakt."""

        text = str(value or "").strip()
        if not text:
            return ""
        try:
            return datetime.strptime(text, "%Y-%m-%d").strftime("%d.%m.%Y")
        except ValueError:
            return text

    @staticmethod
    def _category_label(value: str | None) -> str:
        """Übersetzt eine gespeicherte Kategorie für die sichtbare Ansicht."""

        text = str(value or "").strip()
        return category_label(text)

    @staticmethod
    def _text(value: object | None) -> str:
        """Vereinheitlicht fehlende und textuelle Werte für die Ansicht."""

        return str(value).strip() if value is not None else ""
