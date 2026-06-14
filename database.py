"""Gemeinsamer Zugriff auf die SQLite-Datenbank.

Alle Verbindungen zur Datei ``bibliothek.db`` laufen durch dieses Modul.
Dadurch müssen andere Dateien nicht selbst Verbindungen öffnen und schließen.
"""

import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

type QueryParameters = Sequence[object]
type QueryResult = list[tuple[Any, ...]]


# ``__file__`` ist der Pfad dieser Python-Datei. Daraus bestimmen wir den
# Projektordner. Das ist zuverlässiger als nur "bibliothek.db", weil das
# Programm dann auch funktioniert, wenn es aus einem anderen Ordner gestartet
# wird.
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "bibliothek.db"


def create_database() -> None:
    """Erstellt die Tabellen mit dem vorbereiteten SQL-Skript neu.

    Achtung: Das aktuelle SQL-Skript enthält DROP TABLE-Anweisungen. Diese
    Funktion sollte deshalb nur bewusst zur Neuerstellung verwendet werden.
    Sie wird beim normalen Start der GUI nicht automatisch ausgeführt.
    """

    sql_script = (BASE_DIR / "sql_scripts" / "create_database.sql").read_text(
        encoding="utf-8"
    )

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            connection.executescript(sql_script)

    print("Alle Tabellen wurden erfolgreich erstellt.")


def execute_query(
    query: str,
    parameters: QueryParameters = (),
) -> QueryResult:
    """Führt eine parametrisierte SQL-Abfrage aus und liefert alle Zeilen.

    ``query`` enthält SQL mit Fragezeichen-Platzhaltern.
    ``parameters`` enthält die dazugehörigen Werte in derselben Reihenfolge.
    """

    # Eine leere Abfrage hat kein sinnvolles Ergebnis. Eine leere Liste ist für
    # Aufrufer leichter zu verarbeiten als None.
    if not query.strip():
        return []

    try:
        with closing(sqlite3.connect(DATABASE_PATH)) as connection:
            cursor = connection.execute(query, parameters)
            return cursor.fetchall()
    except sqlite3.Error as error:
        # Wir geben einen verständlicheren Fehlertyp an die GUI weiter.
        # ``from error`` bewahrt zusätzlich die ursprüngliche Fehlerursache.
        raise RuntimeError(f"Datenbankfehler: {error}") from error


def run_transaction[Result](
    operation: Callable[[sqlite3.Cursor], Result],
) -> Result:
    """Führt mehrere zusammengehörige Schreibzugriffe atomar aus."""

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with closing(connection.cursor()) as cursor, connection:
            return operation(cursor)
