"""Interne Fachwerte der serverseitigen Implementierung."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BookSearchResult:
    """Ein Buch, wie es der Bibliotheksbestand intern zurückgibt."""

    isbn: str
    title: str | None
    authors: str | None
    main_category: str | None
    language: str | None
    release_date: str | None
    copy_count: int


@dataclass(frozen=True, slots=True)
class BookCopy:
    """Ein physisches Exemplar aus dem Bibliotheksbestand."""

    copy_id: str
    state: str | None
    availability: str | None
