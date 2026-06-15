# Bibliotheksprojekt

Client-Server-Anwendung zur Verwaltung und Auswertung eines
Bibliotheksbestands. Desktop, Server und geteilte Fachwerte liegen ohne
Duplikation in einem Monorepo.

Die Tkinter-Oberfläche ist als Admin-Dashboard ausgelegt und zeigt deshalb
bewusst keine Buchcover.

## Voraussetzungen

- Python 3.14.6
- [uv](https://docs.astral.sh/uv/)

## Struktur

```text
.
├── main.py                         # Kompatibler Startpunkt des Desktop-Clients
├── server_main.py                  # Kompatibler Startpunkt des Servers
├── bibliothek.db                   # Standardmäßiger SQLite-Bibliotheksbestand
├── CONTEXT.md                      # Gemeinsame Fachsprache des Projekts
├── pyproject.toml                  # Abhängigkeiten und Werkzeugkonfiguration
├── uv.lock                         # Reproduzierbar aufgelöste Abhängigkeiten
│
├── src/
│   ├── __init__.py                 # Markiert das gemeinsame Python-Paket
│   ├── desktop/
│   │   ├── __init__.py             # Markiert das Desktop-Paket
│   │   ├── __main__.py             # Start mit: python -m src.desktop
│   │   ├── main.py                 # Konfiguration und Adapteraufbau
│   │   ├── gui.py                  # Tkinter-Fenster und Bedienlogik
│   │   ├── http_adapter.py         # HTTPX-Adapter zum Server
│   │   └── assets/
│   │       └── Logo Bibliothek.png # Desktop-Logo und Fenstersymbole
│   │
│   ├── server/
│   │   ├── __init__.py             # Markiert das Serverpaket
│   │   ├── __main__.py             # Start mit: python -m src.server
│   │   ├── main.py                 # Serverkonfiguration und Uvicorn-Start
│   │   ├── http_adapter.py         # FastAPI-Routen und Fehlerabbildung
│   │   ├── backend.py              # Interface für Serveroperationen
│   │   ├── katalogansicht.py       # Suche, Sortierung und Anzeigewerte
│   │   ├── buchlebenszyklus.py     # Aufnahme, Entfernung, Metadatenabruf
│   │   ├── bestand.py              # SQLite und Persistenzregeln
│   │   ├── models.py               # Serverinterne Datenformen
│   │   └── sql_scripts/
│   │       └── create_database.sql # SQLite-Schema
│   │
│   └── shared/
│       ├── __init__.py             # Markiert das geteilte Paket
│       ├── catalog.py              # Bibliothekszugang und Katalogmodelle
│       ├── models.py               # Geteilte Buchmetadaten
│       ├── http_models.py          # HTTP-Request- und Responsemodelle
│       └── domain_values.py        # Kategorien und Exemplarstatus
│
└── tests/
    ├── integration/
    │   └── test_http_transport.py  # FastAPI + Uvicorn + HTTPX gemeinsam
    ├── server/
    │   ├── test_katalogansicht.py  # Katalogansicht am Fachinterface
    │   └── test_server_modules.py  # Bestand und Buchlebenszyklus
    ├── shared/
    │   └── test_domain_values.py   # Geteilte Fachwerte
    └── test_architecture.py        # Erlaubte Paketabhängigkeiten
```

### Paketverantwortung

`src/desktop` enthält ausschließlich den Desktop-Client. `gui.py` kennt
Tkinter und das Interface `Bibliothekszugang`, aber keine Servermodule, kein
SQL und keine FastAPI-Routen. `http_adapter.py` erfüllt dieses Interface mit
einem persistenten HTTPX-Client. Dadurch kann der Desktop auf einem anderen
Rechner als der Server ausgeführt werden.

`src/server` enthält die gesamte serverseitige Implementierung.
`Bibliotheksbackend` konstruiert `Katalogansicht` und `Buchlebenszyklus` mit
demselben `Bibliotheksbestand`. Der FastAPI-Adapter ruft ausschließlich dieses
Backend-Interface auf. SQLite, Open-Library-Zugriff und Transaktionsregeln
bleiben hinter den serverseitigen Interfaces.

`src/shared` enthält ausschließlich Wissen, das beide Prozesse benötigen:
geteilte Pydantic-Modelle, Fachwerte und das transport-unabhängige
`Bibliothekszugang`-Interface. Dort liegt keine SQLite-, Tkinter-, FastAPI- oder
HTTPX-Implementierung.

### Abhängigkeitsrichtung

```text
Desktop GUI
    │
    ▼
Bibliothekszugang ───── geteilte Pydantic-Modelle
    ▲                              ▲
    │                              │
HTTPX-Adapter ── HTTP/JSON ── FastAPI-Adapter
                                   │
                                   ▼
                         Bibliotheksbackend
                          ├── Katalogansicht
                          └── Buchlebenszyklus
                                   │
                                   ▼
                         Bibliotheksbestand
                                   │
                                   ▼
                                 SQLite
```

Erlaubte Importabhängigkeiten:

- `desktop` darf `shared` importieren.
- `server` darf `shared` und andere Servermodule importieren.
- `shared` darf weder `desktop` noch `server` importieren.
- `desktop` darf keine Serverimplementierung importieren.
- Client und Server kommunizieren ausschließlich über HTTP und die geteilten
  Pydantic-Modelle.

Diese Regeln werden in `tests/test_architecture.py` geprüft.

### Ablauf einer Anfrage

1. Die Tkinter-GUI erzeugt beispielsweise eine `Katalogsuche`.
2. Der HTTPX-Adapter serialisiert das Pydantic-Modell als JSON.
3. FastAPI validiert dieselbe Modellklasse und ruft `Bibliotheksbackend` auf.
4. Das Backend leitet die Anfrage an `Katalogansicht` oder
   `Buchlebenszyklus` weiter.
5. `Bibliotheksbestand` kapselt SQLite-Verbindungen, SQL und Transaktionen.
6. Das Ergebnis läuft als geteiltes Pydantic-Modell zurück zum Desktop.
7. HTTPX und Pydantic validieren die Antwort, bevor Tkinter sie zeichnet.

FastAPI erzeugt aus den geteilten Modellen zusätzlich die OpenAPI-Beschreibung
und die interaktive Dokumentation.

### Daten und Konfiguration

Die Standarddatenbank liegt als `bibliothek.db` im Projektstamm. Der
Serverprozess bestimmt ihren Pfad; der Desktop greift niemals direkt auf die
Datei zu. Das Schema liegt unter
`src/server/sql_scripts/create_database.sql`.

Serveradresse, Port, Datenbankpfad und Desktop-Zielserver werden über
Kommandozeilenargumente oder Umgebungsvariablen konfiguriert. Dadurch benötigt
eine getrennte Bereitstellung keine Änderungen an den Fachmodulen.

### Startpunkte

- `python -m src.server`: bevorzugter Serverstart.
- `python -m src.desktop`: bevorzugter Desktopstart.
- `server_main.py`: kompatibler Serverstart aus dem Projektstamm.
- `main.py`: kompatibler Desktopstart aus dem Projektstamm.

Die `__main__.py`-Dateien delegieren an die jeweiligen `main.py`-Module. Dort
werden Konfiguration und konkrete Adapter aufgebaut; Fachmodule erstellen
keine globalen Server- oder Desktopinstanzen.

### Teststruktur

Servertests verwenden temporäre SQLite-Dateien und prüfen Verhalten über die
Interfaces von Bibliotheksbestand, Katalogansicht und Buchlebenszyklus.
Integrationstests starten FastAPI mit Uvicorn auf einem freien lokalen Port und
verwenden den echten HTTPX-Adapter. Sie prüfen außerdem, dass die geteilten
Pydantic-Modelle im OpenAPI-Schema erscheinen.

## Verwendung

Server starten:

```powershell
uv run python -m src.server
```

Desktop in einem zweiten Terminal starten:

```powershell
uv sync
uv run python -m src.desktop
```

Die kompatiblen Startdateien `server_main.py` und `main.py` starten dieselben
Prozesse. Standardmäßig verbindet sich der Desktop mit
`http://127.0.0.1:8765`.

Die automatisch erzeugte FastAPI-Dokumentation ist unter
`http://127.0.0.1:8765/docs` erreichbar.

Der FastAPI-Adapter besitzt noch keine Anmeldung oder
Transportverschlüsselung. Für einen öffentlich erreichbaren Server müssen
Authentifizierung und TLS ergänzt werden.

Konfiguration:

```powershell
$env:BIBLIOTHEK_SERVER_URL = "http://server.example:8765"
$env:BIBLIOTHEK_SERVER_HOST = "0.0.0.0"
$env:BIBLIOTHEK_SERVER_PORT = "8765"
$env:BIBLIOTHEK_DATABASE_PATH = "C:\data\bibliothek.db"
```

## Qualitätssicherung

```powershell
uv run python -m unittest -v
uv run ruff check .
uv run ruff format --check .
uv run ty check
```
