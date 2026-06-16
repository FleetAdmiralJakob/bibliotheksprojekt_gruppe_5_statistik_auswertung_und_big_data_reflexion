"""Fachlogik für Buchaufnahme und Buchlöschung.

Dieses Modul prüft Benutzereingaben und übersetzt externe Buchmetadaten. Der
gespeicherte Bibliotheksbestand liegt hinter dem Interface von
``Bibliotheksbestand``; SQL und Transaktionsreihenfolgen sind hier unbekannt.
"""

import json
import re
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from src.server.bestand import Bibliotheksbestand
from src.shared.domain_values import (
    Exemplarverfuegbarkeit,
    Exemplarzustand,
    Kategorie,
)
from src.shared.models import BookMetadata

type JsonObject = dict[str, Any]

OPEN_LIBRARY_BOOKS_URL = "https://openlibrary.org/api/books"
OPEN_LIBRARY_ISBN_URL = "https://openlibrary.org/isbn/{isbn}.json"
DNB_SRU_URL = "https://services.dnb.de/sru/dnb"
USER_AGENT = "SchoolLibraryCatalog/1.0 (educational project)"
MARC_NAMESPACE = "http://www.loc.gov/MARC21/slim"

LANGUAGES: dict[str, str] = {
    "de": "Deutsch",
    "deu": "Deutsch",
    "ger": "Deutsch",
    "en": "Englisch",
    "eng": "Englisch",
}


def normalize_isbn(value: str) -> str:
    """Entfernt Trennzeichen und prüft eine ISBN‑10 oder ISBN‑13."""

    # Upper ist für ISBN-10 wichtig, weil die Prüfziffer manchmal X (steht für 10) lautet, dadurch wird
    # die Prüfziffer korrekt erkannt, selbst wenn sie fälschlicherweise klein geschrieben
    # ist und die ISBN korrekt validiert.
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


def _load_xml(url: str) -> ElementTree.Element | None:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=10) as response:
            return ElementTree.parse(response).getroot()
    except HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError(
            f"Die Buch-API antwortet mit Fehler {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError("Die Buch-API ist momentan nicht erreichbar.") from error
    except ElementTree.ParseError as error:
        raise RuntimeError("Die Buch-API hat ungültige Daten geliefert.") from error


def _language_from_edition(edition: Mapping[str, Any] | None) -> str:
    languages = edition.get("languages") if edition else None
    if not isinstance(languages, Sequence) or isinstance(languages, str):
        return ""
    first_language = languages[0] if languages else None
    if not isinstance(first_language, Mapping):
        return ""

    language_key = first_language.get("key")
    if not isinstance(language_key, str):
        return ""

    code = language_key.rsplit("/", 1)[-1].lower()
    language = LANGUAGES.get(code)
    return language if language is not None else code.upper()


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


def _metadata_from_open_library(isbn: str) -> BookMetadata | None:
    query = urlencode({"bibkeys": f"ISBN:{isbn}", "jscmd": "data", "format": "json"})
    response = _load_json(f"{OPEN_LIBRARY_BOOKS_URL}?{query}")
    book = (response or {}).get(f"ISBN:{isbn}")
    if not book:
        return None

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

    return BookMetadata(
        isbn=isbn,
        title=book["title"].strip(),
        authors=tuple(authors),
        publisher=publishers[0] if publishers else "",
        release_date=str(book.get("publish_date", "")).strip(),
        page_count=page_count,
        language=_language_from_edition(edition),
        main_category=_category_from_subjects(book.get("subjects", [])),
    )


def _marc_fields(
    record: ElementTree.Element,
    tags: Sequence[str],
) -> list[ElementTree.Element]:
    fields: list[ElementTree.Element] = []
    for tag in tags:
        fields.extend(record.findall(f"{{{MARC_NAMESPACE}}}datafield[@tag='{tag}']"))
    return fields


def _marc_values(field: ElementTree.Element, code: str) -> list[str]:
    return [
        str(subfield.text or "").strip()
        for subfield in field.findall(f"{{{MARC_NAMESPACE}}}subfield[@code='{code}']")
        if str(subfield.text or "").strip()
    ]


def _first_marc_value(
    record: ElementTree.Element,
    tags: Sequence[str],
    code: str,
) -> str:
    for field in _marc_fields(record, tags):
        values = _marc_values(field, code)
        if values:
            return values[0].rstrip(" /:;,")
    return ""


def _personal_name(value: str) -> str:
    family_name, separator, given_names = value.partition(",")
    if not separator:
        return value
    return f"{given_names.strip()} {family_name.strip()}".strip()


def _authors_from_marc(record: ElementTree.Element) -> tuple[str, ...]:
    authors: list[str] = []
    author_role_codes = {"aut"}
    author_role_names = {"autor", "verfasser", "verfasserin"}

    for field in _marc_fields(record, ("100", "110", "700", "710")):
        tag = field.get("tag", "")
        role_codes = {value.casefold() for value in _marc_values(field, "4")}
        role_names = {value.casefold() for value in _marc_values(field, "e")}
        has_role = bool(role_codes or role_names)
        is_author = bool(
            role_codes & author_role_codes or role_names & author_role_names
        )
        if has_role and not is_author:
            continue
        if tag.startswith("7") and not is_author:
            continue

        names = _marc_values(field, "a")
        if not names:
            continue
        name = _personal_name(names[0]) if tag in {"100", "700"} else names[0]
        if name not in authors:
            authors.append(name)

    return tuple(authors)


def _metadata_from_dnb(isbn: str) -> BookMetadata | None:
    query = urlencode(
        {
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": f"num={isbn}",
            "recordSchema": "MARC21-xml",
            "maximumRecords": 1,
        }
    )
    response = _load_xml(f"{DNB_SRU_URL}?{query}")
    if response is None:
        return None

    record = response.find(f".//{{{MARC_NAMESPACE}}}record")
    if record is None:
        return None

    title_parts = [_first_marc_value(record, ("245",), code) for code in ("a", "b")]
    title = ": ".join(part for part in title_parts if part)
    authors = _authors_from_marc(record)
    page_text = _first_marc_value(record, ("300",), "a")
    page_match = re.search(r"\d+", page_text)
    page_count = int(page_match.group()) if page_match else 0

    language_code = _first_marc_value(record, ("041",), "a").casefold()
    subject_names = [
        value
        for field in _marc_fields(record, ("650", "653", "655", "689", "926"))
        for code in ("a", "x")
        for value in _marc_values(field, code)
    ]

    if not title:
        raise ValueError("Die Buch-API liefert keinen Titel für diese ISBN.")
    if not authors:
        raise ValueError("Die Buch-API liefert keinen Autor für diese ISBN.")
    if page_count <= 0:
        raise ValueError("Die Buch-API liefert keine gültige Seitenzahl.")

    return BookMetadata(
        isbn=isbn,
        title=title,
        authors=authors,
        publisher=_first_marc_value(record, ("264", "260"), "b"),
        release_date=_first_marc_value(record, ("264", "260"), "c"),
        page_count=page_count,
        language=LANGUAGES.get(language_code, language_code.upper()),
        main_category=_category_from_subjects(
            [{"name": name} for name in subject_names]
        ),
    )


def fetch_book_metadata(isbn: str) -> BookMetadata:
    """Lädt Metadaten zuerst aus Open Library, dann aus dem DNB-Katalog."""

    open_library_error: ValueError | RuntimeError | None = None
    try:
        metadata = _metadata_from_open_library(isbn)
    except (ValueError, RuntimeError) as error:
        open_library_error = error
    else:
        if metadata is not None:
            return metadata

    try:
        metadata = _metadata_from_dnb(isbn)
    except RuntimeError as error:
        if isinstance(open_library_error, RuntimeError):
            raise RuntimeError(
                "Die Buch-APIs sind momentan nicht erreichbar."
            ) from error
        raise

    if metadata is not None:
        return metadata
    if open_library_error is not None:
        raise open_library_error
    raise ValueError("Zu dieser ISBN wurden keine Buchdaten gefunden.")


class Buchlebenszyklus:
    """Prüft und koordiniert Aufnahme und Entfernung eines Buches."""

    def __init__(self, bestand: Bibliotheksbestand) -> None:
        """Verbindet den Buchlebenszyklus mit genau einem Bibliotheksbestand."""

        self._bestand = bestand

    def entfernen(self, isbn_value: str) -> str:
        """Löscht ein Buch mit seinen Autoren-Zuordnungen und Exemplaren."""

        isbn = normalize_isbn(isbn_value)

        # Existenzprüfung, Löschreihenfolge und Transaktion gehören zum
        # Bibliotheksbestand und werden nicht über dieses Interface offengelegt.
        self._bestand.delete_book(isbn)
        return isbn

    def aufnehmen(
        self,
        isbn_value: str,
        copy_count: int | str,
    ) -> BookMetadata:
        """Lädt Metadaten und speichert ein neues Buch mit seinen Exemplaren."""

        isbn = normalize_isbn(isbn_value)
        copy_count = self._copy_count(copy_count)

        # Die externen Kataloge bleiben vorerst in der Implementierung des
        # Buchlebenszyklus. Ein eigener Adapter ist eine separate Vertiefung.
        metadata = fetch_book_metadata(isbn)

        # Das Bestandsmodul besitzt die Persistenzinvarianten für Buch, Autoren,
        # Verlag und Exemplare und bestätigt die Änderung atomar.
        self._bestand.add_book(metadata, copy_count)
        return metadata

    def exemplare_hinzufuegen(
        self,
        isbn_value: str,
        copy_count: int | str,
    ) -> str:
        """Fügt einem vorhandenen Buch die angeforderte Exemplarzahl hinzu."""

        isbn = normalize_isbn(isbn_value)
        self._bestand.add_book_copies(isbn, self._copy_count(copy_count))
        return isbn

    def exemplarstatus_aendern(
        self,
        isbn_value: str,
        copy_id: str,
        state: Exemplarzustand,
        availability: Exemplarverfuegbarkeit,
    ) -> str:
        """Ändert den Status eines vorhandenen Exemplars."""

        isbn = normalize_isbn(isbn_value)
        self._bestand.update_book_copy(isbn, copy_id, state, availability)
        return isbn

    def exemplar_entfernen(self, isbn_value: str, copy_id: str) -> str:
        """Löscht ein einzelnes Exemplar eines vorhandenen Buches."""

        isbn = normalize_isbn(isbn_value)
        self._bestand.delete_book_copy(isbn, copy_id)
        return isbn

    @staticmethod
    def _copy_count(copy_count: int | str) -> int:
        """Prüft eine eingegebene Exemplarzahl für alle Aufnahmewege."""

        try:
            copy_count = int(copy_count)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Die Anzahl der Exemplare muss eine ganze Zahl sein."
            ) from error
        if copy_count < 1 or copy_count > 999:
            raise ValueError("Die Anzahl der Exemplare muss zwischen 1 und 999 liegen.")
        return copy_count
