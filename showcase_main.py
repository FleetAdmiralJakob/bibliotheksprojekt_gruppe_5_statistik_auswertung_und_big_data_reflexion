"""Startet Server und Desktop gemeinsam für die gebündelte Showcase-App."""

import os
import shutil
import socket
import sys
import time
from pathlib import Path
from threading import Thread

import uvicorn

from src.desktop.gui import run as run_desktop
from src.desktop.http_adapter import HttpBibliothekszugang
from src.server.backend import Bibliotheksbackend
from src.server.bestand import Bibliotheksbestand
from src.server.http_adapter import create_app

APP_DATA_DIRECTORY = "BibliotheksprojektGruppe5"
DATABASE_FILENAME = "bibliothek.db"
SERVER_START_TIMEOUT_SECONDS = 10.0


def resource_path(relative_path: str) -> Path:
    """Liefert einen Pfad aus dem Quellbaum oder dem PyInstaller-Bundle."""

    bundle_directory = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_directory / relative_path


def prepare_database() -> Path:
    """Legt beim ersten Start eine beschreibbare Kopie der Beispieldatenbank an."""

    configured_path = os.environ.get("BIBLIOTHEK_DATABASE_PATH")
    if configured_path:
        database_path = Path(configured_path).expanduser()
    else:
        local_app_data = os.environ.get("LOCALAPPDATA")
        data_directory = (
            Path(local_app_data) / APP_DATA_DIRECTORY
            if local_app_data
            else Path.home() / f".{APP_DATA_DIRECTORY}"
        )
        database_path = data_directory / DATABASE_FILENAME

    database_path.parent.mkdir(parents=True, exist_ok=True)
    if not database_path.exists():
        shutil.copy2(resource_path(DATABASE_FILENAME), database_path)
    return database_path


class LocalServer:
    """Verwaltet den nur lokal erreichbaren Uvicorn-Server."""

    def __init__(self, database_path: Path) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen()

        port = self._socket.getsockname()[1]
        backend = Bibliotheksbackend(Bibliotheksbestand(database_path=database_path))
        config = uvicorn.Config(
            create_app(backend),
            host="127.0.0.1",
            port=port,
            loop="asyncio",
            http="h11",
            ws="none",
            lifespan="on",
            log_config=None,
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = Thread(
            target=self._server.run,
            kwargs={"sockets": [self._socket]},
            name="bibliotheksserver",
            daemon=True,
        )
        self.base_url = f"http://127.0.0.1:{port}"

    def start(self) -> None:
        """Startet den Server und wartet, bis er Anfragen annehmen kann."""

        self._thread.start()
        deadline = time.monotonic() + SERVER_START_TIMEOUT_SECONDS
        while not self._server.started:
            if not self._thread.is_alive():
                raise RuntimeError("Der interne Bibliotheksserver ist abgestürzt.")
            if time.monotonic() >= deadline:
                self.close()
                raise RuntimeError(
                    "Der interne Bibliotheksserver konnte nicht gestartet werden."
                )
            time.sleep(0.05)

    def close(self) -> None:
        """Fährt den Server herunter und gibt seinen lokalen Port frei."""

        self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=5)
        if self._thread.is_alive():
            self._server.force_exit = True
            self._thread.join(timeout=1)
        self._socket.close()


def run_showcase() -> None:
    """Startet die vollständige Anwendung als einen lokalen Prozess."""

    server = LocalServer(prepare_database())
    server.start()
    bibliothek = HttpBibliothekszugang(server.base_url)
    try:
        if not bibliothek.health():
            raise RuntimeError("Der interne Bibliotheksserver ist nicht bereit.")
        run_desktop(bibliothek)
    finally:
        bibliothek.close()
        server.close()


def show_startup_error(error: Exception) -> None:
    """Zeigt Startfehler auch bei einer Anwendung ohne Konsolenfenster an."""

    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Bibliothekskatalog konnte nicht gestartet werden",
        str(error),
        parent=root,
    )
    root.destroy()


def main() -> None:
    try:
        run_showcase()
    except Exception as error:
        show_startup_error(error)


if __name__ == "__main__":
    main()
