"""Tests an den Interfaces der Fach- und Bestandsmodule."""

import tempfile
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from unittest.mock import patch

from src.server import buchlebenszyklus
from src.server.bestand import Bibliotheksbestand
from src.server.buchlebenszyklus import Buchlebenszyklus
from src.shared.domain_values import (
    DEFAULT_COPY_AVAILABILITY,
    DEFAULT_COPY_STATE,
    Exemplarverfuegbarkeit,
    Exemplarzustand,
    Kategorie,
)
from src.shared.models import BookMetadata


class IsbnTests(unittest.TestCase):
    """Prüft die reine ISBN-Fachlogik ohne Datenbankzugriff."""

    def test_normalizes_valid_isbn(self):
        """Trennzeichen werden entfernt, gültige Prüfziffern bleiben erhalten."""

        self.assertEqual(
            buchlebenszyklus.normalize_isbn("978-3-596-18094-3"),
            "9783596180943",
        )
        self.assertEqual(
            buchlebenszyklus.normalize_isbn("0-306-40615-2"),
            "0306406152",
        )

    def test_rejects_invalid_isbn(self):
        """Eine falsche Prüfziffer wird als ungültige ISBN gemeldet."""

        with self.assertRaises(ValueError):
            buchlebenszyklus.normalize_isbn("9783596180944")


class CategoryClassificationTests(unittest.TestCase):
    """Prüft die zentral konfigurierte Zuordnung externer Themen."""

    def test_uses_category_priority_for_overlapping_subjects(self):
        """Technik bleibt bei einem zugleich wissenschaftlichen Thema vorrangig."""

        category = buchlebenszyklus._category_from_subjects(
            [{"name": "Computer Science"}]
        )

        self.assertEqual(category, Kategorie.TECHNOLOGIE)


class BookMetadataFetchTests(unittest.TestCase):
    """Prüft die Katalog-Fallbacks ohne echte Netzwerkzugriffe."""

    DNB_RESPONSE = """\
    <searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
      <numberOfRecords>1</numberOfRecords>
      <records>
        <record>
          <recordData>
            <record xmlns="http://www.loc.gov/MARC21/slim">
              <datafield tag="041"><subfield code="a">ger</subfield></datafield>
              <datafield tag="100">
                <subfield code="a">Scamander, Newt</subfield>
                <subfield code="4">aut</subfield>
              </datafield>
              <datafield tag="245">
                <subfield code="a">
                  Phantastische Tierwesen und wo sie zu finden sind
                </subfield>
              </datafield>
              <datafield tag="264">
                <subfield code="b">Carlsen</subfield>
                <subfield code="c">2017</subfield>
              </datafield>
              <datafield tag="300">
                <subfield code="a">133 Seiten</subfield>
              </datafield>
              <datafield tag="653">
                <subfield code="a">Fantasy-Bücher</subfield>
              </datafield>
              <datafield tag="700">
                <subfield code="a">Rowling, J. K.</subfield>
                <subfield code="4">aut</subfield>
              </datafield>
              <datafield tag="700">
                <subfield code="a">Gill, Olivia Lomenech</subfield>
                <subfield code="4">art</subfield>
              </datafield>
            </record>
          </recordData>
        </record>
      </records>
    </searchRetrieveResponse>
    """

    @patch("src.server.buchlebenszyklus._load_xml")
    @patch("src.server.buchlebenszyklus._load_json")
    def test_uses_dnb_when_open_library_has_no_isbn(
        self,
        load_json,
        load_xml,
    ):
        """Die gemeldete Carlsen-ISBN wird über den DNB-Katalog gefunden."""

        load_json.return_value = {}
        load_xml.return_value = ElementTree.fromstring(self.DNB_RESPONSE)

        metadata = buchlebenszyklus.fetch_book_metadata("9783551556981")

        self.assertEqual(
            metadata.title,
            "Phantastische Tierwesen und wo sie zu finden sind",
        )
        self.assertEqual(metadata.authors, ("Newt Scamander", "J. K. Rowling"))
        self.assertEqual(metadata.publisher, "Carlsen")
        self.assertEqual(metadata.release_date, "2017")
        self.assertEqual(metadata.page_count, 133)
        self.assertEqual(metadata.language, "Deutsch")
        self.assertEqual(metadata.main_category, Kategorie.BELLETRISTIK)
        load_xml.assert_called_once()


class BibliotheksbestandTests(unittest.TestCase):
    """Prüft SQLite ausschließlich über das Bibliotheksbestand-Interface."""

    def setUp(self):
        """Erzeugt für jeden Test einen vollständig isolierten Bestand."""

        # Eine echte temporäre SQLite-Datei ist der lokale Testadapter. Dadurch
        # prüfen die Tests SQL, Fremdschlüssel und Transaktionen gemeinsam.
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            self.database_path = Path(temp_file.name)

        self.bestand = Bibliotheksbestand(database_path=self.database_path)
        self.bestand.recreate()

    def tearDown(self):
        """Entfernt die nur für den aktuellen Test angelegte Datenbankdatei."""

        self.database_path.unlink(missing_ok=True)

    @staticmethod
    def metadata() -> BookMetadata:
        """Liefert vollständige, gültige Metadaten für Bestandsoperationen."""

        return BookMetadata(
            isbn="9780306406157",
            title="Test Book",
            authors=("Ada Example", "Max Example"),
            publisher="Test Publisher",
            release_date="2026",
            page_count=240,
            language="Englisch",
            main_category=Kategorie.WISSENSCHAFT,
        )

    def test_adds_and_reads_book_through_the_interface(self):
        """Buch, Beziehungen und Exemplare sind über Fachwerte beobachtbar."""

        self.bestand.add_book(self.metadata(), 3)

        # Die Suche prüft Buch, Autoren, Kategorie und Exemplaranzahl, ohne
        # Tabellen oder SELECT-Spalten im Test zu kennen.
        results = self.bestand.search_books(
            book_query="Test",
            author_query="",
            category_query=Kategorie.WISSENSCHAFT,
            isbn_query="978030",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].isbn, "9780306406157")
        self.assertEqual(results[0].title, "Test Book")
        self.assertEqual(results[0].authors, "Ada Example, Max Example")
        self.assertEqual(results[0].copy_count, 3)

        # Die Exemplarabfrage bestätigt die Persistenzinvarianten für Zustand,
        # Verfügbarkeit und reproduzierbare Exemplar-IDs.
        copies = self.bestand.get_book_copies("9780306406157")
        self.assertEqual(
            [copy.copy_id for copy in copies],
            [
                "9780306406157-001",
                "9780306406157-002",
                "9780306406157-003",
            ],
        )
        self.assertEqual(
            [(copy.state, copy.availability) for copy in copies],
            [(DEFAULT_COPY_STATE, DEFAULT_COPY_AVAILABILITY)] * 3,
        )

    def test_recreate_resets_a_populated_database(self):
        """Das Schema kann trotz vorhandener Fremdschlüssel neu erstellt werden."""

        self.bestand.add_book(self.metadata(), 1)

        # Dieser Aufruf reproduzierte vor der Korrektur der DROP-Reihenfolge
        # einen Fremdschlüsselfehler auf einer gefüllten Datenbank.
        self.bestand.recreate()

        self.assertEqual(self.bestand.search_books("", "", "", ""), [])

    def test_rejects_invalid_copy_count_at_the_interface(self):
        """Der Bestand schützt seine Exemplaranzahl unabhängig von der GUI."""

        with self.assertRaises(ValueError):
            self.bestand.add_book(self.metadata(), 0)

        self.assertEqual(self.bestand.search_books("", "", "", ""), [])

    def test_adds_copies_to_an_existing_book(self):
        """Neue Exemplare setzen IDs und Standardwerte lückenlos fort."""

        self.bestand.add_book(self.metadata(), 2)

        self.bestand.add_book_copies("9780306406157", 2)

        copies = self.bestand.get_book_copies("9780306406157")
        self.assertEqual(
            [copy.copy_id for copy in copies],
            [
                "9780306406157-001",
                "9780306406157-002",
                "9780306406157-003",
                "9780306406157-004",
            ],
        )
        self.assertEqual(
            [(copy.state, copy.availability) for copy in copies[-2:]],
            [(DEFAULT_COPY_STATE, DEFAULT_COPY_AVAILABILITY)] * 2,
        )

    def test_updates_copy_state_and_availability(self):
        """Ein vorhandenes Exemplar kann über das Bestandsinterface geändert werden."""

        self.bestand.add_book(self.metadata(), 2)

        self.bestand.update_book_copy(
            "9780306406157",
            "9780306406157-002",
            Exemplarzustand.GUT,
            Exemplarverfuegbarkeit.RESERVIERT,
        )

        copies = self.bestand.get_book_copies("9780306406157")
        self.assertEqual(
            [(copy.state, copy.availability) for copy in copies],
            [
                (DEFAULT_COPY_STATE, DEFAULT_COPY_AVAILABILITY),
                (Exemplarzustand.GUT, Exemplarverfuegbarkeit.RESERVIERT),
            ],
        )

    def test_deletes_single_copy_without_removing_book(self):
        """Ein einzelnes Exemplar kann entfernt werden, ohne das Buch zu löschen."""

        self.bestand.add_book(self.metadata(), 3)

        self.bestand.delete_book_copy("9780306406157", "9780306406157-002")

        copies = self.bestand.get_book_copies("9780306406157")
        self.assertEqual(
            [copy.copy_id for copy in copies],
            [
                "9780306406157-001",
                "9780306406157-003",
            ],
        )
        self.assertEqual(
            self.bestand.search_books("", "", "", "9780306406157")[0].copy_count,
            2,
        )

    def test_rejects_unknown_copy_status_updates(self):
        """Unbekannte Exemplare ändern keinen gespeicherten Status."""

        self.bestand.add_book(self.metadata(), 1)

        with self.assertRaises(ValueError):
            self.bestand.update_book_copy(
                "9780306406157",
                "9780306406157-999",
                Exemplarzustand.SCHLECHT,
                Exemplarverfuegbarkeit.DEFEKT,
            )

        copies = self.bestand.get_book_copies("9780306406157")
        self.assertEqual(
            [(copy.state, copy.availability) for copy in copies],
            [(DEFAULT_COPY_STATE, DEFAULT_COPY_AVAILABILITY)],
        )

    def test_rejects_unknown_copy_deletion(self):
        """Unbekannte Exemplare werden nicht stillschweigend gelöscht."""

        self.bestand.add_book(self.metadata(), 1)

        with self.assertRaises(ValueError):
            self.bestand.delete_book_copy("9780306406157", "9780306406157-999")

        self.assertEqual(len(self.bestand.get_book_copies("9780306406157")), 1)

    def test_rejects_more_than_999_total_copies_without_partial_insert(self):
        """Die Gesamtgrenze wird innerhalb derselben Transaktion geschützt."""

        self.bestand.add_book(self.metadata(), 2)

        with self.assertRaises(ValueError):
            self.bestand.add_book_copies("9780306406157", 998)

        self.assertEqual(len(self.bestand.get_book_copies("9780306406157")), 2)

    def test_delete_removes_book_and_copies_atomically(self):
        """Nach dem Löschen ist das Buch über kein Bestandsinterface erreichbar."""

        self.bestand.add_book(self.metadata(), 2)
        self.bestand.delete_book("9780306406157")

        self.assertEqual(self.bestand.search_books("", "", "", ""), [])
        with self.assertRaises(ValueError):
            self.bestand.get_book_copies("9780306406157")


class BuchlebenszyklusTests(unittest.TestCase):
    """Prüft Buchaufnahme mit externer Metadatenquelle und tiefem Bestand."""

    def setUp(self):
        """Verdrahtet die Fachlogik mit einem temporären Bibliotheksbestand."""

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            self.database_path = Path(temp_file.name)

        self.bestand = Bibliotheksbestand(database_path=self.database_path)
        self.bestand.recreate()
        self.lebenszyklus = Buchlebenszyklus(self.bestand)

    def tearDown(self):
        """Entfernt die temporären Bestandsdaten."""

        self.database_path.unlink(missing_ok=True)

    @patch("src.server.buchlebenszyklus.fetch_book_metadata")
    def test_adds_metadata_and_requested_copies(self, fetch_metadata):
        """Buchaufnahme reicht geprüfte Metadaten atomar an den Bestand weiter."""

        fetch_metadata.return_value = BibliotheksbestandTests.metadata()

        metadata = self.lebenszyklus.aufnehmen("978-0-306-40615-7", 3)

        # Beobachtungen laufen über dasselbe Bestandsinterface wie in der
        # Anwendung. Der Test greift nicht hinter den Seam auf Tabellen zu.
        results = self.bestand.search_books("", "", "", metadata.isbn)
        copies = self.bestand.get_book_copies(metadata.isbn)

        self.assertEqual(results[0].title, "Test Book")
        self.assertEqual(results[0].authors, "Ada Example, Max Example")
        self.assertEqual(len(copies), 3)

    def test_removes_book_from_the_same_inventory(self):
        """Aufnahme und Entfernung verwenden denselben Bibliotheksbestand."""

        self.bestand.add_book(BibliotheksbestandTests.metadata(), 1)

        isbn = self.lebenszyklus.entfernen("978-0-306-40615-7")

        self.assertEqual(isbn, "9780306406157")
        self.assertEqual(self.bestand.search_books("", "", "", ""), [])

    def test_adds_copies_with_normalized_isbn_and_string_count(self):
        """Auch der nachträgliche Aufnahmeweg prüft seine Eingabewerte."""

        self.bestand.add_book(BibliotheksbestandTests.metadata(), 1)

        isbn = self.lebenszyklus.exemplare_hinzufuegen(
            "978-0-306-40615-7",
            "2",
        )

        self.assertEqual(isbn, "9780306406157")
        self.assertEqual(len(self.bestand.get_book_copies(isbn)), 3)

    def test_removes_single_copy_with_normalized_isbn(self):
        """Auch das Entfernen eines Exemplars normalisiert die ISBN."""

        self.bestand.add_book(BibliotheksbestandTests.metadata(), 2)

        isbn = self.lebenszyklus.exemplar_entfernen(
            "978-0-306-40615-7",
            "9780306406157-001",
        )

        self.assertEqual(isbn, "9780306406157")
        self.assertEqual(
            [copy.copy_id for copy in self.bestand.get_book_copies(isbn)],
            ["9780306406157-002"],
        )


if __name__ == "__main__":
    unittest.main()
