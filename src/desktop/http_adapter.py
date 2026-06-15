"""HTTPX-Adapter des Desktop-Clients zum Bibliotheksserver."""

from urllib.parse import quote

import httpx
from pydantic import BaseModel

from src.shared.catalog import (
    Buchansicht,
    BuchNichtGefunden,
    Katalogseite,
    Katalogsuche,
)
from src.shared.http_models import (
    BuchaufnahmeRequest,
    BuchentfernungResponse,
    ErrorResponse,
    HealthResponse,
)
from src.shared.models import BookMetadata


class HttpBibliothekszugang:
    """Erfüllt das Bibliothekszugang-Interface über HTTPX."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )

    def suchen(self, suche: Katalogsuche) -> Katalogseite:
        """Lädt eine Katalogseite vom Server."""

        return self._request(
            "POST",
            "/v1/katalog/suchen",
            Katalogseite,
            payload=suche,
        )

    def buch(self, isbn: str) -> Buchansicht:
        """Lädt die Katalogansicht eines Buches vom Server."""

        return self._request(
            "GET",
            f"/v1/buecher/{quote(isbn, safe='')}",
            Buchansicht,
        )

    def buch_aufnehmen(
        self,
        isbn: str,
        exemplaranzahl: int | str,
    ) -> BookMetadata:
        """Nimmt ein Buch über den Server auf."""

        return self._request(
            "POST",
            "/v1/buecher",
            BookMetadata,
            payload=BuchaufnahmeRequest(
                isbn=isbn,
                exemplaranzahl=exemplaranzahl,
            ),
        )

    def buch_entfernen(self, isbn: str) -> str:
        """Entfernt ein Buch über den Server."""

        response = self._request(
            "DELETE",
            f"/v1/buecher/{quote(isbn, safe='')}",
            BuchentfernungResponse,
        )
        return response.isbn

    def health(self) -> bool:
        """Prüft, ob der Server erreichbar ist."""

        response = self._request("GET", "/health", HealthResponse)
        return response.status == "ok"

    def close(self) -> None:
        """Schließt den eigenen HTTPX-Client und dessen Verbindungen."""

        if self._owns_client:
            self._client.close()

    def _request[ResponseModel: BaseModel](
        self,
        method: str,
        path: str,
        response_model: type[ResponseModel],
        payload: BaseModel | None = None,
    ) -> ResponseModel:
        try:
            response = self._client.request(
                method,
                path,
                json=payload.model_dump(mode="json") if payload else None,
            )
        except httpx.RequestError as error:
            raise RuntimeError(
                "Der Bibliotheksserver ist momentan nicht erreichbar."
            ) from error

        if response.is_error:
            self._raise_server_error(response)

        try:
            return response_model.model_validate(response.json())
        except ValueError as error:
            raise RuntimeError(
                "Der Bibliotheksserver hat ungültige Daten geliefert."
            ) from error

    @staticmethod
    def _raise_server_error(response: httpx.Response) -> None:
        try:
            error = ErrorResponse.model_validate(response.json())
        except ValueError:
            raise RuntimeError(
                f"Der Bibliotheksserver antwortet mit Fehler {response.status_code}."
            ) from None

        if error.error == "book_not_found":
            raise BuchNichtGefunden(error.message)
        if error.error == "invalid_request":
            raise ValueError(error.message)
        raise RuntimeError(error.message)
