"""Fachlogik für die Suche im Bibliotheksbestand.

Die GUI kennt nur ``search_books``. Diese Funktion übersetzt die vier
Suchfelder in eine SQL-Abfrage und übergibt sie an die Datenbankschicht.
"""

# ``execute_query`` öffnet die Datenbank, führt SQL aus und schließt sie wieder.
import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from database import execute_query, run_transaction

type BookRow = tuple[
    str,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    int,
]
type BookCopy = tuple[str, str | None, str | None]
type JsonObject = dict[str, Any]


class BookMetadata(TypedDict):
    isbn: str
    title: str
    authors: list[str]
    publisher: str
    release_date: str
    page_count: int
    language: str
    main_category: str


OPEN_LIBRARY_BOOKS_URL = "https://openlibrary.org/api/books"
OPEN_LIBRARY_ISBN_URL = "https://openlibrary.org/isbn/{isbn}.json"
USER_AGENT = "SchoolLibraryCatalog/1.0 (educational project)"

LANGUAGES = {
    "de": "Deutsch",
    "deu": "Deutsch",
    "ger": "Deutsch",
    "en": "Englisch",
    "eng": "Englisch",
}


def search_books(
    book_query: str,
    author_query: str,
    genre_query: str,
    isbn_query: str,
) -> list[BookRow]:
    """Sucht Bücher anhand optionaler Teiltexte und einer Kategorie.

    Die vier Parameter kommen direkt aus den Suchfeldern der Oberfläche.
    Zurückgegeben wird eine Liste aus Tupeln. Jedes Tupel enthält:
    ISBN, Titel, Autor(en), Kategorie, Sprache, Erscheinungsdatum und Anzahl
    der vorhandenen Exemplare.
    """

    # Das SQL steht als mehrzeiliger String hier im Code, damit die komplette
    # Abfrage lesbar bleibt. Die Fragezeichen sind Platzhalter für Werte.
    # Konkrete Benutzereingaben werden NICHT direkt in den SQL-Text eingebaut.
    # Das schützt vor SQL Injection und vermeidet Probleme mit Anführungszeichen.
    query = """
    SELECT
        -- Nur Spalten auswählen, die die Tabelle tatsächlich anzeigt.
        books.isbn,
        books.title,

        -- Ein Buch kann mehrere Autoren haben. GROUP_CONCAT verbindet deren
        -- Namen für die Anzeige zu einem Text wie "Name A, Name B".
        GROUP_CONCAT(authors.name, ', ') AS authors,
        books.main_category,
        books.language,
        books.release_date,

        -- Für jedes Buch zählt diese Unterabfrage die physischen Exemplare
        -- mit derselben ISBN. Eine Unterabfrage ist hier sicherer als ein
        -- zusätzlicher JOIN: Bei mehreren Autoren UND mehreren Exemplaren
        -- würden sich die verbundenen Zeilen sonst gegenseitig vervielfachen.
        (
            SELECT COUNT(*)
            FROM book_copies
            WHERE book_copies.isbn = books.isbn
        ) AS copy_count

    -- Die Suche beginnt bei der Tabelle books.
    FROM books

    -- book_authors ist eine Verbindungstabelle. Sie ordnet ISBNs den IDs
    -- ihrer Autoren zu, weil Bücher mehrere Autoren haben können.
    JOIN book_authors ON book_authors.isbn = books.isbn

    -- Über die author_id erhalten wir aus authors den sichtbaren Namen.
    JOIN authors ON authors.author_id = book_authors.author_id

    -- LIKE erlaubt Teiltreffer. Die Prozentzeichen werden weiter unten an die
    -- Parameter gesetzt: Aus "Harry" wird "%Harry%".
    WHERE books.title LIKE ?
      AND authors.name LIKE ?

      -- Eine leere Kategorie bedeutet "alle Kategorien". Ist der Parameter
      -- nicht leer, muss main_category genau diesem Wert entsprechen.
      AND (? = '' OR books.main_category = ?)
      AND books.isbn LIKE ?

    -- Wegen GROUP_CONCAT müssen alle Zeilen desselben Buches gruppiert werden.
    GROUP BY books.isbn

    -- Grundsortierung nach Titel, unabhängig von Groß-/Kleinschreibung.
    -- Die GUI kann diese Reihenfolge danach durch Spaltenklicks ändern.
    ORDER BY books.title COLLATE NOCASE
    """

    # Die Reihenfolge muss genau zur Reihenfolge der Fragezeichen passen.
    # genre_query kommt zweimal vor, weil es im Kategorieausdruck zweimal
    # geprüft wird. Das sqlite3-Modul setzt die Werte sicher in die Abfrage ein.
    parameters = (
        f"%{book_query}%",
        f"%{author_query}%",
        genre_query,
        genre_query,
        f"%{isbn_query}%",
    )

    # Die Datenbankschicht führt die vorbereitete Abfrage aus und liefert alle
    # Treffer zurück. Diese Funktion reicht das Ergebnis an die GUI weiter.
    return cast(list[BookRow], execute_query(query, parameters))


def get_book_copies(isbn_value: str) -> list[BookCopy]:
    """Liefert alle Exemplare eines Buches mit Zustand und Verfügbarkeit.

    Die GUI ruft diese Funktion auf, sobald ein Buch in der Ergebnisliste
    geöffnet wird. Zurückgegeben werden Tupel mit: Exemplar-ID, Zustand und
    Verfügbarkeit.
    """

    isbn = normalize_isbn(isbn_value)

    if not execute_query("SELECT 1 FROM books WHERE isbn = ?", (isbn,)):
        raise ValueError("Ein Buch mit dieser ISBN ist nicht vorhanden.")

    query = """
    SELECT
        copy_id,
        state,
        availability
    FROM book_copies
    WHERE isbn = ?
    ORDER BY copy_id COLLATE NOCASE
    """

    return cast(list[BookCopy], execute_query(query, (isbn,)))


def normalize_isbn(value: str) -> str:
    """Entfernt Trennzeichen und prüft eine ISBN‑10 oder ISBN‑13."""

    isbn = re.sub(r"[\s-]", "", value).upper()
    if len(isbn) == 10 and re.fullmatch(r"\d{9}[\dX]", isbn):
        total = sum(
            (10 - index) * (10 if char == "X" else int(char))
            for index, char in enumerate(isbn)
        )
        if total % 11 == 0:
            return isbn
    elif len(isbn) == 13 and isbn.isdigit():
        total = sum(
            int(char) * (1 if index % 2 == 0 else 3)
            for index, char in enumerate(isbn[:12])
        )
        if (10 - total % 10) % 10 == int(isbn[-1]):
            return isbn

    raise ValueError("Bitte eine gültige ISBN-10 oder ISBN-13 eingeben.")


def _load_json(url: str) -> JsonObject | None:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=10) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError(
            f"Die Buch-API antwortet mit Fehler {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError("Die Buch-API ist momentan nicht erreichbar.") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError("Die Buch-API hat ungültige Daten geliefert.") from error


def _language_from_edition(edition: Mapping[str, Any] | None) -> str:
    languages = edition.get("languages", []) if edition else []
    if not languages:
        return ""
    code = languages[0].get("key", "").rsplit("/", 1)[-1].lower()
    return LANGUAGES.get(code, code.upper())


def _category_from_subjects(subjects: Sequence[Mapping[str, Any]]) -> str:
    names = [subject.get("name", "") for subject in subjects]
    normalized = {name.casefold() for name in names}
    combined = " ".join(names).casefold()

    if normalized & {"fiction", "belletristik", "roman"}:
        return "Fiction"
    if normalized & {"nonfiction", "non-fiction", "non fiction", "sachbuch"}:
        return "Non-Fiction"
    if any(
        word in combined for word in ("computer", "technology", "software", "technik")
    ):
        return "Technology"
    if any(word in combined for word in ("science", "wissenschaft", "mathemat")):
        return "Science"
    if any(word in combined for word in ("history", "geschichte", "histor")):
        return "History"
    return "Other"


def fetch_book_metadata(isbn: str) -> BookMetadata:
    """Lädt die Metadaten einer ISBN aus der Open‑Library‑API."""

    query = urlencode({"bibkeys": f"ISBN:{isbn}", "jscmd": "data", "format": "json"})
    response = _load_json(f"{OPEN_LIBRARY_BOOKS_URL}?{query}")
    book = (response or {}).get(f"ISBN:{isbn}")
    if not book:
        raise ValueError("Zu dieser ISBN wurden keine Buchdaten gefunden.")

    edition = _load_json(OPEN_LIBRARY_ISBN_URL.format(isbn=quote(isbn)))
    authors = [
        author.get("name", "").strip()
        for author in book.get("authors", [])
        if author.get("name", "").strip()
    ]
    publishers = [
        publisher.get("name", "").strip()
        for publisher in book.get("publishers", [])
        if publisher.get("name", "").strip()
    ]
    page_count = book.get("number_of_pages")

    if not book.get("title"):
        raise ValueError("Die Buch-API liefert keinen Titel für diese ISBN.")
    if not authors:
        raise ValueError("Die Buch-API liefert keinen Autor für diese ISBN.")
    if not isinstance(page_count, int) or page_count <= 0:
        raise ValueError("Die Buch-API liefert keine gültige Seitenzahl.")

    return {
        "isbn": isbn,
        "title": book["title"].strip(),
        "authors": authors,
        "publisher": publishers[0] if publishers else "",
        "release_date": str(book.get("publish_date", "")).strip(),
        "page_count": page_count,
        "language": _language_from_edition(edition),
        "main_category": _category_from_subjects(book.get("subjects", [])),
    }


def _find_or_create_named_record(
    cursor: sqlite3.Cursor,
    table: str,
    id_column: str,
    prefix: str,
    name: str,
) -> str | None:
    if not name:
        return None

    row = cursor.execute(
        f"SELECT {id_column} FROM {table} WHERE name = ? COLLATE NOCASE",
        (name,),
    ).fetchone()
    if row:
        return row[0]

    record_id = f"{prefix}_{uuid4().hex[:12]}"
    if table == "publishers":
        cursor.execute(
            "INSERT INTO publishers (publisher_id, name, location) VALUES (?, ?, ?)",
            (record_id, name, ""),
        )
    else:
        cursor.execute(
            "INSERT INTO authors (author_id, name) VALUES (?, ?)",
            (record_id, name),
        )
    return record_id


def delete_book(isbn_value: str) -> str:
    """Löscht ein Buch mit seinen zugehörigen Autoren-Zuordnungen und Exemplaren."""

    isbn = normalize_isbn(isbn_value)

    if not execute_query("SELECT 1 FROM books WHERE isbn = ?", (isbn,)):
        raise ValueError("Ein Buch mit dieser ISBN ist nicht vorhanden.")

    def delete_existing_book(cursor: sqlite3.Cursor) -> None:
        # Erst abhängige Datensätze löschen, danach den eigentlichen Bucheintrag.
        # Dadurch funktioniert das auch, wenn die Tabellen per Fremdschlüssel
        # miteinander verbunden sind.
        cursor.execute("DELETE FROM book_copies WHERE isbn = ?", (isbn,))
        cursor.execute("DELETE FROM book_authors WHERE isbn = ?", (isbn,))
        cursor.execute("DELETE FROM books WHERE isbn = ?", (isbn,))

        if cursor.rowcount == 0:
            raise ValueError("Ein Buch mit dieser ISBN ist nicht vorhanden.")

    run_transaction(delete_existing_book)
    return isbn


def add_book(isbn_value: str, copy_count: int | str) -> BookMetadata:
    """Lädt Metadaten und speichert ein neues Buch mit seinen Exemplaren."""

    isbn = normalize_isbn(isbn_value)
    try:
        copy_count = int(copy_count)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Die Anzahl der Exemplare muss eine ganze Zahl sein."
        ) from error
    if copy_count < 1 or copy_count > 999:
        raise ValueError("Die Anzahl der Exemplare muss zwischen 1 und 999 liegen.")

    if execute_query("SELECT 1 FROM books WHERE isbn = ?", (isbn,)):
        raise ValueError("Ein Buch mit dieser ISBN ist bereits vorhanden.")

    metadata = fetch_book_metadata(isbn)

    def insert_book(cursor: sqlite3.Cursor) -> None:
        if cursor.execute("SELECT 1 FROM books WHERE isbn = ?", (isbn,)).fetchone():
            raise ValueError("Ein Buch mit dieser ISBN ist bereits vorhanden.")

        publisher_id = _find_or_create_named_record(
            cursor, "publishers", "publisher_id", "PUB", metadata["publisher"]
        )
        cursor.execute(
            """
            INSERT INTO books (
                isbn, title, main_category, language, publisher_id,
                release_date, page_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                isbn,
                metadata["title"],
                metadata["main_category"],
                metadata["language"],
                publisher_id,
                metadata["release_date"],
                metadata["page_count"],
            ),
        )

        for author_name in dict.fromkeys(metadata["authors"]):
            author_id = _find_or_create_named_record(
                cursor, "authors", "author_id", "A", author_name
            )
            cursor.execute(
                "INSERT INTO book_authors (isbn, author_id) VALUES (?, ?)",
                (isbn, author_id),
            )

        cursor.executemany(
            """
            INSERT INTO book_copies (copy_id, isbn, state, availability)
            VALUES (?, ?, 'new', 'available')
            """,
            [(f"{isbn}-{number:03}", isbn) for number in range(1, copy_count + 1)],
        )

    run_transaction(insert_book)
    return metadata
