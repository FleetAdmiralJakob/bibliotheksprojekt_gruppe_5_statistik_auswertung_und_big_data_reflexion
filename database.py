"""Gemeinsamer Zugriff auf die SQLite-Datenbank.

Alle Verbindungen zur Datei ``bibliothek.db`` laufen durch dieses Modul.
Dadurch müssen andere Dateien nicht selbst Verbindungen öffnen und schließen.
"""

import sqlite3
from pathlib import Path


# ``__file__`` ist der Pfad dieser Python-Datei. Daraus bestimmen wir den
# Projektordner. Das ist zuverlässiger als nur "bibliothek.db", weil das
# Programm dann auch funktioniert, wenn es aus einem anderen Ordner gestartet
# wird.
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "bibliothek.db"


def createDatabase():
    """Erstellt die Tabellen mit dem vorbereiteten SQL-Skript neu.

    Achtung: Das aktuelle SQL-Skript enthält DROP TABLE-Anweisungen. Diese
    Funktion sollte deshalb nur bewusst zur Neuerstellung verwendet werden.
    Sie wird beim normalen Start der GUI nicht automatisch ausgeführt.
    """

    # Verbindung zur SQLite-Datei öffnen. Existiert sie nicht, würde SQLite
    # grundsätzlich eine neue Datei anlegen.
    con = sqlite3.connect(DATABASE_PATH)

    # Der Cursor ist das Objekt, über das SQL-Befehle ausgeführt werden.
    cursor = con.cursor()

    # SQLite prüft Fremdschlüssel nicht immer automatisch. Dieses PRAGMA
    # aktiviert die Prüfung für die aktuelle Verbindung.
    cursor.execute("PRAGMA foreign_keys = ON")

    # ``with`` schließt die Datei automatisch, auch falls beim Lesen ein Fehler
    # auftritt. UTF-8 sorgt für eine eindeutige Textkodierung.
    with open(
        BASE_DIR / "sql_scripts" / "create_database.sql",
        "r",
        encoding="utf-8",
    ) as file:
        sql_script = file.read()

    try:
        # executescript kann mehrere SQL-Anweisungen auf einmal ausführen.
        cursor.executescript(sql_script)

        # Änderungen werden erst mit commit dauerhaft gespeichert.
        con.commit()
        print("Alle Tabellen wurden erfolgreich erstellt.")

    except Exception as e:
        # Bei der manuellen Datenbankerstellung genügt hier zunächst eine
        # Konsolenausgabe. Die GUI verwendet für Suchfehler einen Dialog.
        print("Fehler:", e)

    # Cursor und Verbindung immer explizit freigeben.
    cursor.close()
    con.close()


def executeQuery(query, parameters=()):
    """Führt eine parametrisierte SQL-Abfrage aus und liefert alle Zeilen.

    ``query`` enthält SQL mit Fragezeichen-Platzhaltern.
    ``parameters`` enthält die dazugehörigen Werte in derselben Reihenfolge.
    """

    # Für jeden Aufruf wird eine kurze, eigene Verbindung geöffnet.
    con = sqlite3.connect(DATABASE_PATH)
    cursor = con.cursor()

    # Eine leere Abfrage hat kein sinnvolles Ergebnis. Eine leere Liste ist für
    # Aufrufer leichter zu verarbeiten als None.
    if not query.strip():
        cursor.close()
        con.close()
        return []

    try:
        # Parameter werden getrennt vom SQL übergeben. sqlite3 übernimmt
        # korrektes Escaping und verhindert, dass Eingaben zu SQL-Code werden.
        cursor.execute(query, parameters)

        # fetchall liest alle gefundenen Zeilen als Liste von Tupeln.
        result = cursor.fetchall()
    except Exception as e:
        # Wir geben einen verständlicheren Fehlertyp an die GUI weiter.
        # ``from e`` bewahrt zusätzlich die ursprüngliche Fehlerursache.
        raise RuntimeError(f"Datenbankfehler: {e}") from e
    finally:
        # ``finally`` läuft bei Erfolg UND bei Fehlern. Dadurch bleiben keine
        # offenen Datenbankverbindungen zurück.
        cursor.close()
        con.close()

    return result


def runTransaction(operation):
    """Führt mehrere zusammengehörige Schreibzugriffe atomar aus."""

    con = sqlite3.connect(DATABASE_PATH)
    cursor = con.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    try:
        result = operation(cursor)
        con.commit()
        return result
    except Exception:
        con.rollback()
        raise
    finally:
        cursor.close()
        con.close()
