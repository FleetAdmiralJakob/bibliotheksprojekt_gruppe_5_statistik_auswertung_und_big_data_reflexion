"""Tests für Diagrammdaten der Desktop-Oberfläche."""

import unittest

from src.desktop.gui import _category_chart_counts
from src.shared.catalog import Katalogzeile
from src.shared.domain_values import Kategorie


class CategoryChartCountsTests(unittest.TestCase):
    """Prüft die Aggregation der sichtbaren Katalogzeilen für das Kreisdiagramm."""

    @staticmethod
    def row(isbn: str, category: Kategorie) -> Katalogzeile:
        return Katalogzeile(
            isbn=isbn,
            titel=f"Titel {isbn}",
            autoren="Testautor",
            kategorie=category.label,
            sprache="Deutsch",
            erscheinung="2026",
            exemplarzahl=1,
        )

    def test_counts_only_displayed_rows_in_category_order(self):
        rows = (
            self.row("9780306406157", Kategorie.TECHNOLOGIE),
            self.row("9783161484100", Kategorie.BELLETRISTIK),
            self.row("9781861972712", Kategorie.TECHNOLOGIE),
            self.row("9780132350884", Kategorie.SONSTIGES),
        )

        self.assertEqual(
            _category_chart_counts(rows),
            (
                (Kategorie.BELLETRISTIK.label, 1),
                (Kategorie.TECHNOLOGIE.label, 2),
                (Kategorie.SONSTIGES.label, 1),
            ),
        )


if __name__ == "__main__":
    unittest.main()
