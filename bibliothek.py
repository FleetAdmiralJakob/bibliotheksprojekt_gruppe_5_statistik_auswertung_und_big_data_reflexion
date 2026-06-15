"""Fachlogik für Buchaufnahme und Buchlöschung.

Dieses Modul prüft Benutzereingaben und übersetzt externe Buchmetadaten. Der
gespeicherte Bibliotheksbestand liegt hinter dem Interface von
``Bibliotheksbestand``; SQL und Transaktionsreihenfolgen sind hier unbekannt.
"""

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from database import Bibliotheksbestand
from domain_values import Kategorie
from models import BookMetadata

type JsonObject = dict[str, Any]

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

# Die laufende Anwendung verwendet genau einen Bestand. Tests ersetzen dieses
# Objekt durch einen Bestand mit temporärer SQLite-Datei, ohne Pfadkonstanten
# oder interne Datenbankfunktionen zu verändern.
_BESTAND = Bibliotheksbestand()


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


def _category_from_subjects(subjects: Sequence[Mapping[str, Any]]) -> Kategorie:
    names = [subject.get("name", "") for subject in subjects]
    normalized = {name.casefold() for name in names}
    combined = " ".join(names).casefold()

    categories_by_priority = sorted(
        Kategorie,
        key=lambda category: category.classification_priority,
    )
    for category in categories_by_priority:
        if normalized & category.exact_subjects:
            return category
        if any(keyword in combined for keyword in category.subject_keywords):
            return category
    return Kategorie.SONSTIGES


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


def delete_book(isbn_value: str) -> str:
    """Löscht ein Buch mit seinen zugehörigen Autoren-Zuordnungen und Exemplaren."""

    isbn = normalize_isbn(isbn_value)

    # Existenzprüfung, Löschreihenfolge und Transaktion gehören zum
    # Bibliotheksbestand und werden nicht über dieses Interface offengelegt.
    _BESTAND.delete_book(isbn)
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

    # Open Library bleibt außerhalb des Bestandsmoduls, weil es eine echte
    # externe Abhängigkeit mit eigenen Fehlerarten und Datenformaten ist.
    metadata = fetch_book_metadata(isbn)

    # Das Bestandsmodul besitzt die Persistenzinvarianten für Buch, Autoren,
    # Verlag und Exemplare und bestätigt die Änderung atomar.
    _BESTAND.add_book(metadata, copy_count)
    return metadata
