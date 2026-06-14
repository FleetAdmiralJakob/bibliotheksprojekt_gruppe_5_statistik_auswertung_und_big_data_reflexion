# Bibliotheksprojekt

Desktop-Anwendung zur Verwaltung und Auswertung eines Bibliotheksbestands.
Die Oberfläche ist als Admin-Dashboard ausgelegt und zeigt deshalb bewusst
keine Buchcover.

## Voraussetzungen

- Python 3.14.6
- [uv](https://docs.astral.sh/uv/)

## Verwendung

```powershell
uv sync
uv run python main.py
```

## Qualitätssicherung

```powershell
uv run python -m unittest -v
uv run ruff check .
uv run ruff format --check .
uv run ty check
```
