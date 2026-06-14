# Domain Context

## Bibliotheksbestand

Der **Bibliotheksbestand** ist die gespeicherte Gesamtheit aus Büchern,
Autoren, Verlagen und physischen Exemplaren. Das gleichnamige Modul besitzt die
SQLite-Implementierung, das Datenbankschema, Transaktionen und
Persistenzinvarianten. Aufrufer verwenden sein Interface mit Fachwerten und
kennen weder SQL noch Cursor oder Tabellenreihenfolgen.

## Buch

Ein **Buch** wird durch seine ISBN eindeutig identifiziert und besitzt
Metadaten wie Titel, Autoren, Verlag, Kategorie, Sprache, Erscheinungsdatum und
Seitenzahl.

## Exemplar

Ein **Exemplar** ist eine physische Ausgabe eines Buches. Es besitzt eine
Exemplar-ID, einen Zustand und eine Verfügbarkeit.
