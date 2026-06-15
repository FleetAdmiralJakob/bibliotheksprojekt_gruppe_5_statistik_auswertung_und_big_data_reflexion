"""Zentrale Definitionen für Kategorien und Exemplarstatus.

Gespeicherte Werte, sichtbare Bezeichnungen, Standardwerte und bekannte
Altwerte werden hier einmalig beschrieben. Datenbank, Fachlogik und
Oberfläche leiten ihre jeweilige Darstellung daraus ab.
"""

from enum import StrEnum


class Kategorie(StrEnum):
    """Erlaubte Hauptkategorie eines Buches."""

    label: str
    exact_subjects: frozenset[str]
    subject_keywords: tuple[str, ...]
    classification_priority: int

    def __new__(
        cls,
        value: str,
        label: str,
        exact_subjects: tuple[str, ...] = (),
        subject_keywords: tuple[str, ...] = (),
        classification_priority: int = 99,
    ):
        member = str.__new__(cls, value)
        member._value_ = value
        member.label = label
        member.exact_subjects = frozenset(exact_subjects)
        member.subject_keywords = subject_keywords
        member.classification_priority = classification_priority
        return member

    BELLETRISTIK = (
        "Fiction",
        "Belletristik",
        ("fiction", "belletristik", "roman"),
        (),
        0,
    )
    SACHBUCH = (
        "Non-Fiction",
        "Sachbuch",
        ("nonfiction", "non-fiction", "non fiction", "sachbuch"),
        (),
        1,
    )
    WISSENSCHAFT = (
        "Science",
        "Wissenschaft",
        (),
        ("science", "wissenschaft", "mathemat"),
        3,
    )
    GESCHICHTE = (
        "History",
        "Geschichte",
        (),
        ("history", "geschichte", "histor"),
        4,
    )
    TECHNOLOGIE = (
        "Technology",
        "Technologie",
        (),
        ("computer", "technology", "software", "technik"),
        2,
    )
    SONSTIGES = "Other", "Sonstiges"

    @classmethod
    def from_label(cls, label: str) -> Kategorie:
        """Löst eine sichtbare Bezeichnung in ihren gespeicherten Wert auf."""

        for category in cls:
            if category.label == label:
                return category
        raise ValueError(f"Unbekannte Kategorie: {label}")


class Exemplarzustand(StrEnum):
    """Erlaubter gespeicherter Zustand eines physischen Exemplars."""

    label: str

    def __new__(cls, value: str, label: str):
        member = str.__new__(cls, value)
        member._value_ = value
        member.label = label
        return member

    SCHLECHT = "bad", "Schlecht"
    IN_ORDNUNG = "okay", "In Ordnung"
    GUT = "good", "Gut"
    SEHR_GUT = "very good", "Sehr gut"
    NEU = "new", "Neu"


class Verfuegbarkeitsklasse(StrEnum):
    """Semantische Gruppe für die farbliche Darstellung eines Exemplars."""

    VERFUEGBAR = "available"
    AUSGELIEHEN = "borrowed"
    RESERVIERT = "reserved"
    PROBLEM = "problem"
    UNBEKANNT = "unknown"


class Exemplarverfuegbarkeit(StrEnum):
    """Erlaubte gespeicherte Verfügbarkeit eines Exemplars."""

    label: str
    presentation_class: Verfuegbarkeitsklasse

    def __new__(
        cls,
        value: str,
        label: str,
        presentation_class: Verfuegbarkeitsklasse,
    ):
        member = str.__new__(cls, value)
        member._value_ = value
        member.label = label
        member.presentation_class = presentation_class
        return member

    VERFUEGBAR = "available", "Verfügbar", Verfuegbarkeitsklasse.VERFUEGBAR
    AUSGELIEHEN = "borrowed", "Ausgeliehen", Verfuegbarkeitsklasse.AUSGELIEHEN
    RESERVIERT = "reserved", "Reserviert", Verfuegbarkeitsklasse.RESERVIERT
    DEFEKT = "broken", "Defekt", Verfuegbarkeitsklasse.PROBLEM
    VERLOREN = "lost", "Verloren", Verfuegbarkeitsklasse.PROBLEM


DEFAULT_COPY_STATE = Exemplarzustand.NEU
DEFAULT_COPY_AVAILABILITY = Exemplarverfuegbarkeit.VERFUEGBAR

# Bekannte Werte aus älteren Datenbanken bleiben lesbar, gehören aber nicht
# zu den aktuell erlaubten Werten für neue Einträge.
LEGACY_STATE_LABELS = {
    "used": "Gebraucht",
    "worn": "Abgenutzt",
    "damaged": "Beschädigt",
}
LEGACY_AVAILABILITY_PRESENTATION = {
    "borrowed_out": (
        "Ausgeliehen",
        Verfuegbarkeitsklasse.AUSGELIEHEN,
    ),
    "lent": ("Ausgeliehen", Verfuegbarkeitsklasse.AUSGELIEHEN),
    "loaned": ("Ausgeliehen", Verfuegbarkeitsklasse.AUSGELIEHEN),
    "unavailable": ("Nicht verfügbar", Verfuegbarkeitsklasse.UNBEKANNT),
    "maintenance": ("In Bearbeitung", Verfuegbarkeitsklasse.PROBLEM),
    "damaged": ("Beschädigt", Verfuegbarkeitsklasse.PROBLEM),
}


def category_label(value: str | None) -> str:
    """Liefert die sichtbare Bezeichnung einer gespeicherten Kategorie."""

    text = str(value or "").strip()
    try:
        return Kategorie(text).label
    except ValueError:
        return text


def copy_state_label(value: str | None) -> str:
    """Liefert die sichtbare Bezeichnung eines Exemplarzustands."""

    text = str(value or "").strip()
    try:
        return Exemplarzustand(text.casefold()).label
    except ValueError:
        return LEGACY_STATE_LABELS.get(text.casefold(), text or "Unbekannt")


def availability_presentation(
    value: str | None,
) -> tuple[str, Verfuegbarkeitsklasse]:
    """Liefert sichtbaren Text und semantische Klasse einer Verfügbarkeit."""

    text = str(value or "").strip()
    try:
        availability = Exemplarverfuegbarkeit(text.casefold())
        return availability.label, availability.presentation_class
    except ValueError:
        return LEGACY_AVAILABILITY_PRESENTATION.get(
            text.casefold(),
            (text or "Unbekannt", Verfuegbarkeitsklasse.UNBEKANNT),
        )


def render_schema_value_lists(schema_template: str) -> str:
    """Setzt die erlaubten Fachwerte in die Platzhalter des SQL-Schemas ein."""

    value_groups = {
        "{{MAIN_CATEGORIES}}": Kategorie,
        "{{COPY_STATES}}": Exemplarzustand,
        "{{COPY_AVAILABILITIES}}": Exemplarverfuegbarkeit,
    }
    rendered = schema_template
    for placeholder, values in value_groups.items():
        if placeholder not in rendered:
            raise ValueError(f"Schema-Platzhalter fehlt: {placeholder}")
        sql_values = ", ".join(_sql_string(value.value) for value in values)
        rendered = rendered.replace(placeholder, sql_values)
    return rendered


def _sql_string(value: str) -> str:
    """Maskiert einen festen Fachwert als SQLite-Zeichenkette."""

    escaped = value.replace("'", "''")
    return f"'{escaped}'"
