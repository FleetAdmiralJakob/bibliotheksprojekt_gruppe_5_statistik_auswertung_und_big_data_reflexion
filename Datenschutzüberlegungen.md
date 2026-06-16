# Datenschutzreflexion

Unsere Bibliothekssoftware arbeitet bei Büchern und Exemplaren mit echten
Bestandsdaten aus der Schulbibliothek. Es ist aber nur ein Teilbestand erfasst,
nicht der vollständige Bestand der ganzen Bibliothek. Die Daten beschreiben zum
Beispiel ISBN, Titel, Kategorie, Zustand und Verfügbarkeit der bereits
eingetragenen Bücher und Exemplare. Sie sind normalerweise nicht
personenbezogen, solange sie nicht mit konkreten Nutzerinnen, Nutzern oder
Ausleihvorgängen verbunden werden.

Personenbezogen wären vor allem Nutzerkonten und Ausleihen. Daraus könnte man
Interessen, Gewohnheiten und teilweise auch sensible Themen einzelner
Schülerinnen und Schüler ableiten. Deshalb müssen Auswertungen nützlich sein,
ohne unnötig Personen sichtbar zu machen.

## Welche Daten speichern wir?

Die Bücher und Exemplare stammen aus der echten Bibliothek, aber nur ein
Bruchteil des Bestands wurde bisher eingetragen. Das ist für unser Projekt
trotzdem sinnvoll, weil dadurch die Statistik nicht leer oder künstlich wirkt
und die Kategorien und Verfügbarkeiten realistisch sind. Gleichzeitig dürfen wir
die Ergebnisse nicht so darstellen, als würden sie die gesamte Schulbibliothek
vollständig abbilden.

Bei Nutzerinnen und Nutzern würden wir höchstens eine ID, einen Namen und eine
E-Mail-Adresse speichern. Adressen, Telefonnummern, Klassen, Geburtsdaten oder
private Notizen speichern wir bewusst nicht. Für die Demonstration sollen bei
Nutzerkonten und Ausleihen nur fiktive Personen verwendet werden.

Personenbezogen wird es erst, wenn ein echtes Exemplar mit einer echten Nutzerin
oder einem echten Nutzer über eine Ausleihe verbunden wird. Deshalb sollten echte
Ausleihdaten in unserem Projekt nicht gespeichert oder vorgeführt werden.

## Sinnvolle Auswertungen

Für die Schulbibliothek sind zusammengefasste Statistiken sinnvoll:

- Anzahl der Bücher pro Kategorie.
- Anzahl verfügbarer, ausgeliehener, defekter oder verlorener Exemplare.
 -------- NICHT EINGEBAUT, WEIL IN DER AUFGABENSTELLUNG NICHT SO VIELE GEWÜNSCHT WAREN; KANN ABER DANK DER SEHR GEILEN PROJEKTSTRUKTUUR SEHR EINFACH EINGEBAUT  WERDEN:
- Häufig ausgeliehene Bücher, damit beliebte Bücher nachgekauft werden können.
- Kategorien mit vielen oder wenigen Ausleihen, um den Bestand besser zu planen.

Diese Auswertungen sollten möglichst aggregiert angezeigt werden. Es reicht zum
Beispiel zu wissen, dass ein Buch oft ausgeliehen wurde. Es ist für die normale
Bestandsplanung nicht nötig anzuzeigen, welche konkrete Person dieses Buch wie
oft ausgeliehen hat.

## Problematische Auswertungen

Problematisch wären personenbezogene Ranglisten oder Detailauswertungen, zum
Beispiel:

- Welche Schülerin oder welcher Schüler liest am meisten oder am wenigsten?
- Welche Person leiht Bücher zu bestimmten Themen aus?
- Ausleihverläufe einzelner Personen über längere Zeit.
- Kombinationen aus Name, Kategorie und Datum, weil dadurch Interessen sichtbar
  werden können.

Solche Auswertungen können unfair oder unangenehm sein. Besonders bei kleinen
Gruppen besteht die Gefahr, dass Personen auch dann erkennbar sind, wenn nur
wenige Details angezeigt werden. Deshalb sollten Auswertungen für Präsentation
und Verwaltung möglichst ohne einzelne Namen funktionieren.

## Datenschutzgrenzen bei Statistiken

Auch aggregierte Statistiken haben Grenzen. Wenn eine Kategorie nur ein einziges
Buch oder nur eine einzige Ausleihe enthält, kann man manchmal trotzdem
zurückschließen, wer gemeint ist. Deshalb sollte man bei echten Daten kleine
Fallzahlen vorsichtig behandeln, zum Beispiel durch Zusammenfassen mehrerer
Kategorien oder durch Ausblenden sehr kleiner Gruppen.

Für unser Projekt bedeutet das: Die Statistik soll zeigen, welche Kategorien und
Bücher im bisher erfassten Teilbestand wichtig sind. Sie soll nicht dazu dienen,
einzelne Nutzerinnen und Nutzer zu überwachen. Außerdem sind unsere Ergebnisse
nur eingeschränkt aussagekräftig, solange nicht alle Bücher und Exemplare der
Bibliothek erfasst wurden.

## Sicherheit und SQL-Injection

Benutzereingaben dürfen nicht direkt in SQL-Text eingebaut werden. Unsere
SQL-Abfragen verwenden Platzhalter wie `?`, damit Eingaben getrennt vom
SQL-Befehl an SQLite übergeben werden. Dadurch wird SQL-Injection verhindert,
zum Beispiel bei Suchfeldern für Titel, Autor oder ISBN.

Zusätzlich werden einige Werte durch feste Auswahllisten begrenzt, zum Beispiel
Kategorien, Zustand und Verfügbarkeit eines Exemplars. Dadurch können keine
beliebigen Statuswerte in die Datenbank geschrieben werden.

## Grenzen unserer Projektlösung

Unsere Software ist ein Schulprojekt und kein vollständig abgesichertes
Produktivsystem. Es fehlen noch Funktionen, die für einen echten Einsatz wichtig
wären:

- Anmeldung mit Rollen, zum Beispiel Admin und normale Nutzerin.
- Transportverschlüsselung, falls Client und Server über ein Netzwerk laufen.
- Klare Löschfristen für alte Ausleihdaten.
- Protokollierung wichtiger Änderungen ohne unnötige personenbezogene Details.
- Ein Berechtigungskonzept, damit nicht jede Person alle Daten sehen kann.

Für die Präsentation ist deshalb wichtig: Wir können erklären, welche Daten
unsere Software verarbeitet und welche Auswertungen sinnvoll sind. Gleichzeitig
müssen wir klar sagen, dass echte personenbezogene Ausleihdaten nur sparsam,
geschützt und mit einem konkreten Zweck gespeichert werden dürften.
