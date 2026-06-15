"""FastAPI-Adapter für das Interface des Bibliotheksbackends."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.server.backend import Bibliotheksbackend
from src.shared.catalog import (
    Buchansicht,
    BuchNichtGefunden,
    KatalogansichtFehler,
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


def create_app(backend: Bibliotheksbackend) -> FastAPI:
    """Erzeugt den FastAPI-Adapter für ein konfiguriertes Backend."""

    app = FastAPI(
        title="Bibliotheksserver",
        version="1.0.0",
    )

    @app.exception_handler(BuchNichtGefunden)
    async def handle_book_not_found(
        _request: Request,
        error: Exception,
    ) -> JSONResponse:
        return _error_response(404, "book_not_found", str(error))

    @app.exception_handler(ValueError)
    async def handle_invalid_request(
        _request: Request,
        error: Exception,
    ) -> JSONResponse:
        return _error_response(400, "invalid_request", str(error))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        _error: Exception,
    ) -> JSONResponse:
        return _error_response(
            400,
            "invalid_request",
            "Die Anfrage enthält ungültige oder fehlende Werte.",
        )

    @app.exception_handler(KatalogansichtFehler)
    @app.exception_handler(RuntimeError)
    async def handle_backend_error(
        _request: Request,
        error: Exception,
    ) -> JSONResponse:
        return _error_response(500, "backend_error", str(error))

    @app.get("/health")
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/v1/katalog/suchen")
    def search_catalog(suche: Katalogsuche) -> Katalogseite:
        return backend.suchen(suche)

    @app.get("/v1/buecher/{isbn}")
    def get_book(isbn: str) -> Buchansicht:
        return backend.buch(isbn)

    @app.post("/v1/buecher")
    def add_book(request: BuchaufnahmeRequest) -> BookMetadata:
        return backend.buch_aufnehmen(request.isbn, request.exemplaranzahl)

    @app.delete("/v1/buecher/{isbn}")
    def delete_book(isbn: str) -> BuchentfernungResponse:
        return BuchentfernungResponse(isbn=backend.buch_entfernen(isbn))

    return app


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    error = ErrorResponse(error=code, message=message)
    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(mode="json"),
    )
