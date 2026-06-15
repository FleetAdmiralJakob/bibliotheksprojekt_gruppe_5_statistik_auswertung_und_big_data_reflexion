"""Tiefe serverseitige Bibliotheksanwendung."""

from src.server.bestand import Bibliotheksbestand
from src.server.buchlebenszyklus import Buchlebenszyklus
from src.server.katalogansicht import Katalogansicht
from src.shared.catalog import (
    Buchansicht,
    Katalogseite,
    Katalogsuche,
)
from src.shared.models import BookMetadata


class Bibliotheksbackend:
    """Bündelt Katalogansicht und Buchlebenszyklus an einem Bestand."""

    def __init__(self, bestand: Bibliotheksbestand) -> None:
        """Erzeugt alle serverseitigen Module mit demselben Bestand."""

        self._katalog = Katalogansicht(bestand)
        self._buchlebenszyklus = Buchlebenszyklus(bestand)

    def suchen(self, suche: Katalogsuche) -> Katalogseite:
        """Liefert eine aufbereitete Katalogseite."""

        return self._katalog.suchen(suche)

    def buch(self, isbn: str) -> Buchansicht:
        """Liefert die Katalogansicht eines Buches."""

        return self._katalog.buch(isbn)

    def buch_aufnehmen(
        self,
        isbn: str,
        exemplaranzahl: int | str,
    ) -> BookMetadata:
        """Nimmt ein Buch mit Exemplaren in den Bibliotheksbestand auf."""

        return self._buchlebenszyklus.aufnehmen(isbn, exemplaranzahl)

    def buch_entfernen(self, isbn: str) -> str:
        """Entfernt ein Buch aus dem Bibliotheksbestand."""

        return self._buchlebenszyklus.entfernen(isbn)
