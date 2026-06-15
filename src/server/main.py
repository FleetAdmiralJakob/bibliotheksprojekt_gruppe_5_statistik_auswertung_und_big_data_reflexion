"""Startpunkt des eigenständigen Bibliotheksservers."""

import argparse
import os
from pathlib import Path

import uvicorn

from src.server.backend import Bibliotheksbackend
from src.server.bestand import DATABASE_PATH, Bibliotheksbestand
from src.server.http_adapter import create_app


def main() -> None:
    """Startet den HTTP-Adapter und blockiert bis zum Herunterfahren."""

    parser = argparse.ArgumentParser(description="Bibliotheksserver")
    parser.add_argument(
        "--host",
        default=os.environ.get("BIBLIOTHEK_SERVER_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("BIBLIOTHEK_SERVER_PORT", "8765")),
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("BIBLIOTHEK_DATABASE_PATH", str(DATABASE_PATH))),
    )
    args = parser.parse_args()

    backend = Bibliotheksbackend(Bibliotheksbestand(database_path=args.database))
    uvicorn.run(
        create_app(backend),
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
