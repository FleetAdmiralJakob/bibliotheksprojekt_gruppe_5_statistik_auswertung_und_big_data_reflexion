"""Startpunkt des eigenständigen Desktop-Clients."""

import argparse
import os

from src.desktop.gui import run
from src.desktop.http_adapter import HttpBibliothekszugang


def main() -> None:
    """Startet die GUI mit einem HTTP-Adapter zum Server."""

    parser = argparse.ArgumentParser(description="Bibliotheks-Desktop")
    parser.add_argument(
        "--server-url",
        default=os.environ.get(
            "BIBLIOTHEK_SERVER_URL",
            "http://127.0.0.1:8765",
        ),
    )
    args = parser.parse_args()
    bibliothek = HttpBibliothekszugang(args.server_url)
    try:
        run(bibliothek)
    finally:
        bibliothek.close()


if __name__ == "__main__":
    main()
