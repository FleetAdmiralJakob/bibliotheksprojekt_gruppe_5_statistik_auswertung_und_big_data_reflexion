"""Tiefe SQLite-Implementierung für den Bibliotheksbestand.

Aufrufer arbeiten über das Interface von :class:`Bibliotheksbestand` mit
Büchern und Exemplaren. SQL, Tabellen, Fremdschlüssel, Transaktionen und die
Abbildung von Datenbankzeilen bleiben innerhalb dieses Moduls.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from src.server.models import BookCopy, BookSearchResult
from src.shared.domain_values import (
    DEFAULT_COPY_AVAILABILITY,
    DEFAULT_COPY_STATE,
    Exemplarverfuegbarkeit,
    Exemplarzustand,
    render_schema_value_lists,
)
from src.shared.models import BookMetadata

type QueryParameters = tuple[object, ...]

# Der Standardpfad wird relativ zu dieser Datei bestimmt. Dadurch hängt die
# Anwendung nicht vom aktuellen Arbeitsordner des gestarteten Prozesses ab.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "bibliothek.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "sql_scripts" / "create_database.sql"


class Bibliotheksbestand:
    """Verwaltet den gespeicherten Bibliotheksbestand hinter einem Interface.

    Der Datenbankpfad ist Teil der Konfiguration, nicht Teil jeder einzelnen
    Operation. Produktion verwendet die Projektdatei; Tests verwenden eine
    temporäre SQLite-Datei als lokalen Adapter.
    """

    def __init__(
        self,
        database_path: Path = DATABASE_PATH,
        schema_path: Path = SCHEMA_PATH,
    ) -> None:
        """Speichert die Pfade für alle späteren Bestandsoperationen."""

        self.database_path = Path(database_path)
        self.schema_path = Path(schema_path)

    def recreate(self) -> None:
        """Erstellt das Schema neu und entfernt dabei vorhandene Bestandsdaten.

        Diese Operation ist absichtlich destruktiv. Sie wird nicht beim
        normalen Programmstart ausgeführt, sondern nur bei bewusster
        Neuerstellung oder in isolierten Tests.
        """

        # Die Tabellenstruktur bleibt als SQL-Datei lesbar. Erlaubte Fachwerte
        # werden vor der Ausführung aus den zentralen Definitionen eingesetzt.
        sql_template = self.schema_path.read_text(encoding="utf-8")
        sql_script = render_schema_value_lists(sql_template)

        def recreate_schema(cursor: sqlite3.Cursor) -> None:
            # ``executescript`` bestätigt sonst eine vorherige Transaktion
            # automatisch. Ein expliziter Block hält daher auch alle
            # Schemaänderungen zusammen und verhindert Teilstände.
            cursor.executescript(f"BEGIN IMMEDIATE;\n{sql_script}\nCOMMIT;")

        self._run_transaction(recreate_schema)

    def search_books(
        self,
        book_query: str,
        author_query: str,
        category_query: str,
        isbn_query: str,
    ) -> list[BookSearchResult]:
        """Sucht Bücher und bildet SQLite-Zeilen auf benannte Fachwerte ab."""

        # Die Abfrage bleibt Teil der Implementierung des Bestandsmoduls. Der
        # Aufrufer muss weder Tabellen noch JOINs oder Spaltenreihenfolgen kennen.
        query = """
        SELECT
            books.isbn,
            books.title,
            GROUP_CONCAT(authors.name, ', ') AS authors,
            books.main_category,
            books.language,
            books.release_date,
            (
                SELECT COUNT(*)
                FROM book_copies
                WHERE book_copies.isbn = books.isbn
            ) AS copy_count
        FROM books
        JOIN book_authors ON book_authors.isbn = books.isbn
        JOIN authors ON authors.author_id = book_authors.author_id
        WHERE books.title LIKE ?
          AND authors.name LIKE ?
          AND (? = '' OR books.main_category = ?)
          AND books.isbn LIKE ?
        GROUP BY books.isbn
        ORDER BY books.title COLLATE NOCASE
        """

        # Platzhalter halten Benutzereingaben vom SQL-Text getrennt. Die
        # Kategorie wird zweimal benötigt, weil ein leerer Wert den Filter
        # deaktiviert.
        parameters = (
            f"%{book_query}%",
            f"%{author_query}%",
            category_query,
            category_query,
            f"%{isbn_query}%",
        )
        rows = self._read_all(query, parameters)

        # Die Abbildung an dieser Stelle verhindert, dass positionsabhängige
        # SQLite-Tupel das Interface des Moduls verlassen.
        return [
            BookSearchResult(
                isbn=cast(str, row[0]),
                title=cast(str | None, row[1]),
                authors=cast(str | None, row[2]),
                main_category=cast(str | None, row[3]),
                language=cast(str | None, row[4]),
                release_date=cast(str | None, row[5]),
                copy_count=cast(int, row[6]),
            )
            for row in rows
        ]

    def get_book_copies(self, isbn: str) -> list[BookCopy]:
        """Liefert die Exemplare eines vorhandenen Buches."""

        def load_copies(cursor: sqlite3.Cursor) -> list[BookCopy]:
            # Existenzprüfung und Lesen laufen über dieselbe Verbindung. So kann
            # sich der beobachtete Bestand nicht zwischen zwei Verbindungen ändern.
            if not cursor.execute(
                "SELECT 1 FROM books WHERE isbn = ?",
                (isbn,),
            ).fetchone():
                raise ValueError("Ein Buch mit dieser ISBN ist nicht vorhanden.")

            rows = cursor.execute(
                """
                SELECT copy_id, state, availability
                FROM book_copies
                WHERE isbn = ?
                ORDER BY copy_id COLLATE NOCASE
                """,
                (isbn,),
            ).fetchall()

            # Auch Exemplare verlassen das Modul als benannte Werte statt als
            # Tupel mit einer impliziten Spaltenreihenfolge.
            return [
                BookCopy(
                    copy_id=cast(str, row[0]),
                    state=cast(str | None, row[1]),
                    availability=cast(str | None, row[2]),
                )
                for row in rows
            ]

        return self._run_read(load_copies)

    def add_book(
        self,
        metadata: BookMetadata,
        copy_count: int,
    ) -> None:
        """Speichert Buch, Verlag, Autoren und Exemplare atomar."""

        # Der Bestand verteidigt seine eigene Invariante auch dann, wenn ein
        # anderer Aufrufer die frühzeitige Eingabeprüfung der GUI umgeht.
        if copy_count < 1 or copy_count > 999:
            raise ValueError("Die Anzahl der Exemplare muss zwischen 1 und 999 liegen.")

        isbn = metadata.isbn

        def insert_book(cursor: sqlite3.Cursor) -> None:
            # Die Duplikatprüfung liegt innerhalb derselben Transaktion wie das
            # Schreiben. Eine frühere Prüfung außerhalb wäre bei konkurrierenden
            # Änderungen keine verlässliche Invariante.
            if cursor.execute(
                "SELECT 1 FROM books WHERE isbn = ?",
                (isbn,),
            ).fetchone():
                raise ValueError("Ein Buch mit dieser ISBN ist bereits vorhanden.")

            publisher_id = self._find_or_create_named_record(
                cursor=cursor,
                table="publishers",
                id_column="publisher_id",
                prefix="PUB",
                name=metadata.publisher,
            )

            # Der Bucheintrag referenziert den gefundenen oder neu angelegten
            # Verlag. Ein leerer Verlag wird als NULL gespeichert.
            cursor.execute(
                """
                INSERT INTO books (
                    isbn, title, main_category, language, publisher_id,
                    release_date, page_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    isbn,
                    metadata.title,
                    metadata.main_category,
                    metadata.language,
                    publisher_id,
                    metadata.release_date,
                    metadata.page_count,
                ),
            )

            # ``dict.fromkeys`` entfernt doppelte Autorennamen, behält aber ihre
            # Reihenfolge aus den Metadaten bei.
            for author_name in dict.fromkeys(metadata.authors):
                author_id = self._find_or_create_named_record(
                    cursor=cursor,
                    table="authors",
                    id_column="author_id",
                    prefix="A",
                    name=author_name,
                )
                cursor.execute(
                    "INSERT INTO book_authors (isbn, author_id) VALUES (?, ?)",
                    (isbn, author_id),
                )

            # Exemplar-IDs werden reproduzierbar aus ISBN und laufender Nummer
            # gebildet. Der gesamte Satz gehört zur Buchtransaktion.
            cursor.executemany(
                """
                INSERT INTO book_copies (copy_id, isbn, state, availability)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        f"{isbn}-{number:03}",
                        isbn,
                        DEFAULT_COPY_STATE,
                        DEFAULT_COPY_AVAILABILITY,
                    )
                    for number in range(1, copy_count + 1)
                ],
            )

        self._run_transaction(insert_book)

    def add_book_copies(self, isbn: str, copy_count: int) -> None:
        """Fügt einem vorhandenen Buch neue Exemplare atomar hinzu."""

        if copy_count < 1 or copy_count > 999:
            raise ValueError("Die Anzahl der Exemplare muss zwischen 1 und 999 liegen.")

        def insert_copies(cursor: sqlite3.Cursor) -> None:
            if not cursor.execute(
                "SELECT 1 FROM books WHERE isbn = ?",
                (isbn,),
            ).fetchone():
                raise ValueError("Ein Buch mit dieser ISBN ist nicht vorhanden.")

            existing_ids = {
                cast(str, row[0])
                for row in cursor.execute(
                    "SELECT copy_id FROM book_copies WHERE isbn = ?",
                    (isbn,),
                ).fetchall()
            }
            if len(existing_ids) + copy_count > 999:
                raise ValueError(
                    "Ein Buch darf insgesamt höchstens 999 Exemplare besitzen."
                )

            available_ids = (
                copy_id
                for number in range(1, 1000)
                if (copy_id := f"{isbn}-{number:03}") not in existing_ids
            )
            new_ids = [next(available_ids) for _ in range(copy_count)]
            cursor.executemany(
                """
                INSERT INTO book_copies (copy_id, isbn, state, availability)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        copy_id,
                        isbn,
                        DEFAULT_COPY_STATE,
                        DEFAULT_COPY_AVAILABILITY,
                    )
                    for copy_id in new_ids
                ],
            )

        self._run_transaction(insert_copies)

    def update_book_copy(
        self,
        isbn: str,
        copy_id: str,
        state: Exemplarzustand | str,
        availability: Exemplarverfuegbarkeit | str,
    ) -> None:
        """Ändert Zustand und Verfügbarkeit eines vorhandenen Exemplars."""

        try:
            normalized_state = Exemplarzustand(state)
        except ValueError as error:
            raise ValueError("Der Zustand des Exemplars ist ungültig.") from error

        try:
            normalized_availability = Exemplarverfuegbarkeit(availability)
        except ValueError as error:
            raise ValueError(
                "Die Verfügbarkeit des Exemplars ist ungültig."
            ) from error

        copy_id = copy_id.strip()
        if not copy_id:
            raise ValueError("Die Exemplar-ID darf nicht leer sein.")

        def update_copy(cursor: sqlite3.Cursor) -> None:
            if not cursor.execute(
                "SELECT 1 FROM books WHERE isbn = ?",
                (isbn,),
            ).fetchone():
                raise ValueError("Ein Buch mit dieser ISBN ist nicht vorhanden.")

            result = cursor.execute(
                """
                UPDATE book_copies
                SET state = ?, availability = ?
                WHERE isbn = ? AND copy_id = ?
                """,
                (
                    normalized_state.value,
                    normalized_availability.value,
                    isbn,
                    copy_id,
                ),
            )
            if result.rowcount == 0:
                raise ValueError("Ein Exemplar mit dieser ID ist nicht vorhanden.")

        self._run_transaction(update_copy)

    def delete_book(self, isbn: str) -> None:
        """Löscht ein Buch und seine direkt abhängigen Bestandsdaten atomar."""

        def delete_existing_book(cursor: sqlite3.Cursor) -> None:
            # Die Existenzprüfung gehört zur Transaktion. Dadurch gelten Prüfung
            # und Löschung für denselben Datenbankstand.
            if not cursor.execute(
                "SELECT 1 FROM books WHERE isbn = ?",
                (isbn,),
            ).fetchone():
                raise ValueError("Ein Buch mit dieser ISBN ist nicht vorhanden.")

            # Abhängige Datensätze werden vor dem Buch entfernt, weil das Schema
            # keine automatische Kaskadenlöschung definiert.
            cursor.execute("DELETE FROM book_copies WHERE isbn = ?", (isbn,))
            cursor.execute("DELETE FROM book_authors WHERE isbn = ?", (isbn,))
            cursor.execute("DELETE FROM books WHERE isbn = ?", (isbn,))

        self._run_transaction(delete_existing_book)

    def _connect(self) -> sqlite3.Connection:
        """Öffnet eine Verbindung mit aktivierter Fremdschlüsselprüfung."""

        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _read_all(
        self,
        query: str,
        parameters: QueryParameters = (),
    ) -> list[tuple[Any, ...]]:
        """Führt eine interne Leseabfrage aus und übersetzt SQLite-Fehler."""

        def read_rows(cursor: sqlite3.Cursor) -> list[tuple[Any, ...]]:
            return cursor.execute(query, parameters).fetchall()

        return self._run_read(read_rows)

    def _run_read[Result](
        self,
        operation: Callable[[sqlite3.Cursor], Result],
    ) -> Result:
        """Führt eine interne Leseoperation über genau eine Verbindung aus."""

        try:
            with (
                closing(self._connect()) as connection,
                closing(connection.cursor()) as cursor,
            ):
                return operation(cursor)
        except sqlite3.Error as error:
            # Aufrufer erhalten einen stabilen Fehlertyp und müssen keine
            # SQLite-spezifischen Ausnahmen kennen.
            raise RuntimeError(f"Datenbankfehler: {error}") from error

    def _run_transaction[Result](
        self,
        operation: Callable[[sqlite3.Cursor], Result],
    ) -> Result:
        """Führt eine interne Schreiboperation vollständig oder gar nicht aus."""

        try:
            with (
                closing(self._connect()) as connection,
                # Der Connection-Kontext bestätigt erfolgreiche Änderungen und
                # setzt bei Ausnahmen die gesamte Transaktion zurück.
                connection,
                closing(connection.cursor()) as cursor,
            ):
                return operation(cursor)
        except sqlite3.Error as error:
            raise RuntimeError(f"Datenbankfehler: {error}") from error

    @staticmethod
    def _find_or_create_named_record(
        cursor: sqlite3.Cursor,
        table: str,
        id_column: str,
        prefix: str,
        name: str,
    ) -> str | None:
        """Findet Autor oder Verlag ohne Beachtung der Groß-/Kleinschreibung."""

        # Leere Verlagsnamen sind erlaubt und werden ohne zusätzlichen
        # Tabelleneintrag als NULL-Beziehung dargestellt.
        if not name:
            return None

        row = cursor.execute(
            f"SELECT {id_column} FROM {table} WHERE name = ? COLLATE NOCASE",
            (name,),
        ).fetchone()
        if row:
            return cast(str, row[0])

        # Zufällige IDs vermeiden Abhängigkeiten von der aktuellen Zeilenzahl
        # und funktionieren auch nach Löschungen zuverlässig.
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


def create_database() -> None:
    """Erstellt aus Kompatibilitätsgründen den standardmäßigen Bestand neu."""

    Bibliotheksbestand().recreate()
    print("Alle Tabellen wurden erfolgreich erstellt.")
