"""Tests am Interface der tiefen Katalogansicht."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from database import Bibliotheksbestand
from domain_values import (
    Exemplarverfuegbarkeit,
    Exemplarzustand,
    Kategorie,
)
from katalogansicht import (
    BuchNichtGefunden,
    Katalogansicht,
    Katalogsuche,
    Sortierfeld,
    Sortierung,
)
from models import BookMetadata


class KatalogansichtTests(unittest.TestCase):
    """Prüft Anzeige, Sortierung und Identität ohne Tkinter-Widgets."""

    def setUp(self):
        """Erzeugt einen isolierten Bestand und die zu prüfende Ansicht."""

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            self.database_path = Path(temp_file.name)

        self.bestand = Bibliotheksbestand(database_path=self.database_path)
        self.bestand.recreate()
        self.katalog = Katalogansicht(self.bestand)

    def tearDown(self):
        """Entfernt den lokalen SQLite-Testadapter."""

        self.database_path.unlink(missing_ok=True)

    @staticmethod
    def metadata(
        isbn: str,
        title: str,
        *,
        category: Kategorie = Kategorie.WISSENSCHAFT,
        release_date: str = "2026",
    ) -> BookMetadata:
        """Erstellt vollständige Metadaten mit gezielt variierbaren Werten."""

        return {
            "isbn": isbn,
            "title": title,
            "authors": [f"Autor {title}"],
            "publisher": "Testverlag",
            "release_date": release_date,
            "page_count": 200,
            "language": "Deutsch",
            "main_category": category,
        }

    def test_translates_category_and_formats_date(self):
        """Gespeicherte Werte verlassen den Seam als sichtbare Fachwerte."""

        self.bestand.add_book(
            self.metadata(
                "9780306406157",
                "Ansichtstest",
                category=Kategorie.BELLETRISTIK,
                release_date="2025-02-10",
            ),
            2,
        )

        page = self.katalog.suchen(Katalogsuche(kategorie=Kategorie.BELLETRISTIK))

        self.assertEqual(page.status, "1 Treffer gefunden")
        self.assertEqual(page.zeilen[0].isbn, "9780306406157")
        self.assertEqual(page.zeilen[0].kategorie, Kategorie.BELLETRISTIK.label)
        self.assertEqual(page.zeilen[0].erscheinung, "10.02.2025")
        self.assertEqual(page.zeilen[0].exemplarzahl, 2)

    def test_single_copy_summary_uses_singular(self):
        """Ein einzelnes Exemplar erhält grammatisch den Singular."""

        isbn = "9780306406157"
        self.bestand.add_book(self.metadata(isbn, "Einzelstück"), 1)

        book = self.katalog.buch(isbn)

        self.assertEqual(
            book.exemplarzusammenfassung,
            (f"1 Exemplar insgesamt · 1 {Exemplarverfuegbarkeit.VERFUEGBAR.label}"),
        )

    def test_sorts_dates_chronologically_without_parsing_visible_text(self):
        """Gemischte Jahres- und ISO-Werte werden über Rohwerte sortiert."""

        self.bestand.add_book(
            self.metadata("9780306406157", "Mitte", release_date="2001-05-01"),
            1,
        )
        self.bestand.add_book(
            self.metadata("9783161484100", "Früh", release_date="1995"),
            1,
        )
        self.bestand.add_book(
            self.metadata("9781861972712", "Spät", release_date="2025-02-10"),
            1,
        )

        ascending = self.katalog.suchen(
            Katalogsuche(
                sortierung=Sortierung(Sortierfeld.ERSCHEINUNG),
            )
        )
        descending = self.katalog.suchen(
            Katalogsuche(
                sortierung=Sortierung(
                    Sortierfeld.ERSCHEINUNG,
                    absteigend=True,
                ),
            )
        )

        self.assertEqual(
            [row.titel for row in ascending.zeilen],
            ["Früh", "Mitte", "Spät"],
        )
        self.assertEqual(
            [row.titel for row in descending.zeilen],
            ["Spät", "Mitte", "Früh"],
        )

    def test_sorts_copy_counts_numerically(self):
        """Exemplarzahlen werden als Zahlen statt als sichtbare Texte sortiert."""

        self.bestand.add_book(self.metadata("9780306406157", "Zwei"), 2)
        self.bestand.add_book(self.metadata("9783161484100", "Zehn"), 10)

        page = self.katalog.suchen(
            Katalogsuche(
                sortierung=Sortierung(Sortierfeld.EXEMPLARE),
            )
        )

        self.assertEqual(
            [(row.titel, row.exemplarzahl) for row in page.zeilen],
            [("Zwei", 2), ("Zehn", 10)],
        )

    def test_book_detail_maps_every_schema_status(self):
        """Alle erlaubten Zustände und Verfügbarkeiten erhalten Bedeutung."""

        isbn = "9780306406157"
        self.bestand.add_book(self.metadata(isbn, "Exemplartest"), 5)

        # Das aktuelle Bestandsinterface kann Statuswerte noch nicht ändern.
        # Die Fixture setzt deshalb ausschließlich erlaubte Schemawerte; die
        # Beobachtung erfolgt danach nur über das Katalogansicht-Interface.
        fixtures = list(zip(Exemplarzustand, Exemplarverfuegbarkeit, strict=True))
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            for number, (state, availability) in enumerate(fixtures, start=1):
                connection.execute(
                    """
                    UPDATE book_copies
                    SET state = ?, availability = ?
                    WHERE copy_id = ?
                    """,
                    (state, availability, f"{isbn}-{number:03}"),
                )

        book = self.katalog.buch(isbn)

        self.assertEqual(
            [copy.zustand for copy in book.exemplare],
            [state.label for state in Exemplarzustand],
        )
        self.assertEqual(
            [copy.verfuegbarkeit for copy in book.exemplare],
            [availability.label for availability in Exemplarverfuegbarkeit],
        )
        self.assertEqual(
            [copy.klasse for copy in book.exemplare],
            [
                availability.presentation_class
                for availability in Exemplarverfuegbarkeit
            ],
        )
        self.assertEqual(
            book.exemplarzusammenfassung,
            (
                "5 Exemplare insgesamt · "
                + ", ".join(
                    f"1 {availability.label}" for availability in Exemplarverfuegbarkeit
                )
            ),
        )

    def test_missing_book_has_a_catalog_error(self):
        """Eine unbekannte ISBN besitzt einen stabilen Fehler am Interface."""

        with self.assertRaises(BuchNichtGefunden):
            self.katalog.buch("9780306406157")


if __name__ == "__main__":
    unittest.main()
