"""Geteilte Pydantic-Modelle des HTTP-Adapters."""

from pydantic import BaseModel, ConfigDict

from src.shared.domain_values import Exemplarverfuegbarkeit, Exemplarzustand


class HttpModel(BaseModel):
    """Unveränderliches, strikt benanntes Modell am HTTP-Seam."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class BuchaufnahmeRequest(HttpModel):
    """Eingabe für die Aufnahme eines Buches."""

    isbn: str
    exemplaranzahl: int | str


class ExemplaraufnahmeRequest(HttpModel):
    """Eingabe für neue Exemplare eines vorhandenen Buches."""

    exemplaranzahl: int | str


class ExemplarstatusAenderungRequest(HttpModel):
    """Eingabe für Zustand und Verfügbarkeit eines vorhandenen Exemplars."""

    zustand: Exemplarzustand
    verfuegbarkeit: Exemplarverfuegbarkeit


class BuchentfernungResponse(HttpModel):
    """Bestätigung einer Buchentfernung."""

    isbn: str


class HealthResponse(HttpModel):
    """Zustand des Serverprozesses."""

    status: str


class ErrorResponse(HttpModel):
    """Stabile Fehlerantwort des HTTP-Adapters."""

    error: str
    message: str
