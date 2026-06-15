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

## Katalogansicht

Die **Katalogansicht** ist die für Menschen aufbereitete Sicht auf den
Bibliotheksbestand. Sie behält die Identität eines Buches unabhängig von
sichtbaren Tabellenzellen und bestimmt Anzeigetexte, fachliche Sortierwerte
sowie Zusammenfassungen für Exemplare. Tkinter zeichnet diese Werte, besitzt
aber nicht ihre fachliche Bedeutung.

## Buchlebenszyklus

Der **Buchlebenszyklus** umfasst die Aufnahme und Entfernung eines Buches aus
dem Bibliotheksbestand. Bei der Aufnahme werden ISBN und Exemplaranzahl
geprüft, externe Metadaten interpretiert und Buch, Autoren, Verlag sowie
Exemplare gemeinsam gespeichert. Bei der Entfernung werden alle abhängigen
Bestandsdaten und nicht mehr verwendete Beziehungen konsistent bereinigt.

## Bibliothekszugang

Der **Bibliothekszugang** ist das transport-unabhängige Interface, über das ein
Client die Katalogansicht und den Buchlebenszyklus verwendet. Der
Desktop-Client kennt nur dieses Interface und geteilte Pydantic-Modelle. Der
Serverprozess erfüllt es mit dem Bibliotheksbestand. FastAPI validiert und
serialisiert die Modelle auf dem Server; HTTPX überträgt und validiert sie im
Desktop-Client.

## Serverprozess

Der **Serverprozess** besitzt Bibliotheksbestand, Katalogansicht und
Buchlebenszyklus. Er konstruiert diese Module mit genau einem
Bibliotheksbestand und veröffentlicht den Bibliothekszugang über einen
FastAPI-Adapter, der von Uvicorn ausgeführt wird.

## Desktop-Client

Der **Desktop-Client** besitzt Tkinter, Fensterzustand und Bedienlogik. Er
zeichnet die Fachwerte des Bibliothekszugangs, besitzt aber weder SQL noch
serverseitige Implementierung.
