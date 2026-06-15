"""Tests für die zentralen Kategorien und Exemplarstatus."""

import unittest

from src.shared.domain_values import (
    DEFAULT_COPY_AVAILABILITY,
    DEFAULT_COPY_STATE,
    Exemplarverfuegbarkeit,
    Exemplarzustand,
    Kategorie,
    render_schema_value_lists,
)


class DomainValueTests(unittest.TestCase):
    """Prüft, dass alle Verbraucher aus denselben Definitionen ableiten."""

    def test_renders_every_allowed_value_into_schema(self):
        """Das Datenbankschema erhält seine CHECK-Werte aus den Enums."""

        template = "{{MAIN_CATEGORIES}}\n{{COPY_STATES}}\n{{COPY_AVAILABILITIES}}"

        rendered = render_schema_value_lists(template)

        for value in (*Kategorie, *Exemplarzustand, *Exemplarverfuegbarkeit):
            self.assertIn(f"'{value.value}'", rendered)

    def test_defaults_are_allowed_values(self):
        """Neue Exemplare verwenden Mitglieder der zentralen Wertemengen."""

        self.assertIn(DEFAULT_COPY_STATE, Exemplarzustand)
        self.assertIn(DEFAULT_COPY_AVAILABILITY, Exemplarverfuegbarkeit)


if __name__ == "__main__":
    unittest.main()
