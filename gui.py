"""Grafische Benutzeroberfläche für den Bibliothekskatalog.

Dieses Modul enthält ausschließlich die Oberfläche und deren Bedienlogik:

1. Tkinter zeichnet Fenster, Eingabefelder, Buttons und die Ergebnistabelle.
2. ``search_books`` aus ``bibliothek.py`` übernimmt die fachliche Suche.
3. ``database.py`` kümmert sich eine Ebene tiefer um die SQLite-Datenbank.

Diese Trennung ist absichtlich gewählt. Dadurch muss die GUI nicht wissen,
wie SQL funktioniert, und der Datenbankcode muss nichts über Buttons wissen.
"""

import tkinter as tk
from typing import Tuple, Optional, List
from collections import Counter
from datetime import datetime
from queue import Empty, Queue
from threading import Thread
from tkinter import messagebox, ttk

# Wir importieren nur die Funktion, die die Oberfläche tatsächlich benötigt.
# Die GUI gibt Suchbegriffe hinein und erhält eine Liste mit Büchern zurück.
from bibliothek import add_book, delete_book, get_book_copies, search_books


# In der Datenbank stehen englische Kategorien, in der deutschen Oberfläche
# sollen aber deutsche Namen erscheinen. Dieses Dictionary ist eine
# Übersetzungstabelle: links steht der Datenbankwert, rechts der Anzeigetext.
CATEGORIES = {
    "Fiction": "Belletristik",
    "Non-Fiction": "Sachbuch",
    "Science": "Wissenschaft",
    "History": "Geschichte",
    "Technology": "Technologie",
    "Other": "Sonstiges",
}

# Für eine Suche brauchen wir die Übersetzung auch rückwärts:
# "Wissenschaft" in der Auswahlbox muss wieder zu "Science" werden.
# Die Dictionary Comprehension erzeugt automatisch das umgedrehte Dictionary.
CATEGORY_BY_LABEL = {label: value for value, label in CATEGORIES.items()}

# -----------------------------------------------------------------------------
# Design System
#
# Um ein konsistentes und schönes Erscheinungsbild zu gewährleisten, sind alle
# zentralen Farben in einem separaten Design‑System definiert. Die Farben
# basieren auf einer Primär‑, Sekundär‑ und Akzentfarbe sowie einer Text- und
# Hintergrundfarbe. Daraus werden automatisch abgeleitete Farbtöne erzeugt.
#
# Laut der 60/30/10‑Regel aus der Farbtheorie besteht eine ausgewogene Palette
# aus ca. 60 % Primärfarbe, 30 % Sekundärfarbe und 10 % Akzentfarbe. Die
# Akzentfarbe sollte die aufmerksamkeitsstärkste Farbe sein und wird daher für
# interaktive Elemente wie Buttons verwendet【410334702801063†L94-L100】. Durch
# diese Trennung lassen sich spätere Änderungen einfach zentral vornehmen.

# Basiskonfiguration für das Projekt. Diese Werte können bei Bedarf durch andere
# Farben ersetzt werden, ohne die restliche Oberfläche anzupassen. Alle
# Hex‑Farbcodes müssen sechsstellige Farben sein.
DESIGN_SYSTEM = {
    "text": "#0e080b",
    "background": "#faf6f8",
    "primary": "#65c1ce",
    "secondary": "#c8c8a3",
    "accent": "#9bb785",
}


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Wandelt einen Hex‑Farbcode in ein RGB‑Tupel um.

    Tkinter erwartet Farben als Hex‑Strings, für Berechnungen werden sie jedoch
    zunächst in ihre drei Komponenten aufgeteilt.
    """
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Wandelt ein RGB‑Tupel in einen Hex‑Farbcode um."""
    return "#" + "".join(f"{c:02x}" for c in rgb)


def _lighten(hex_color: str, factor: float) -> str:
    """Hellt einen Farbwert auf.

    Der Faktor muss zwischen 0 (keine Änderung) und 1 (weiß) liegen. Größere
    Faktoren erzeugen hellere Farbtöne. Jeder Farbkanal wird linear in Richtung
    255 verschoben.
    """
    r, g, b = _hex_to_rgb(hex_color)
    new_r = int(r + (255 - r) * factor)
    new_g = int(g + (255 - g) * factor)
    new_b = int(b + (255 - b) * factor)
    return _rgb_to_hex((new_r, new_g, new_b))


def _darken(hex_color: str, factor: float) -> str:
    """Verdunkelt einen Farbwert.

    Der Faktor muss zwischen 0 (keine Änderung) und 1 (schwarz) liegen. Größere
    Faktoren erzeugen dunklere Farbtöne. Jeder Farbkanal wird linear in Richtung
    0 verschoben.
    """
    r, g, b = _hex_to_rgb(hex_color)
    new_r = int(r * (1 - factor))
    new_g = int(g * (1 - factor))
    new_b = int(b * (1 - factor))
    return _rgb_to_hex((new_r, new_g, new_b))


# Abgeleitete Farben. Das Layout verwendet überwiegend den Hintergrundton,
# während Karten und Felder eine leicht abgesetzte Oberfläche (surface)
# erhalten. Der Text wird vom Hintergrundkontrast abgeleitet. Um interaktive
# Elemente hervorzuheben, werden hellere bzw. dunklere Varianten der Primärfarbe
# erzeugt. Änderungen am DESIGN_SYSTEM wirken sich automatisch auf diese
# Konstanten aus.
COLORS = {
    "background": DESIGN_SYSTEM["background"],
    # Die Oberfläche ist absichtlich reinweiß, damit Karten und Eingabefelder
    # gut vom pastelligen Hintergrund abheben.
    "surface": "#ffffff",
    "text": DESIGN_SYSTEM["text"],
    # Muted‑Texte sind eine aufgehellte Variante des Haupttexts. 50 % Aufhellung
    # sorgt für eine dezente, aber gut lesbare Nuance.
    "muted": _lighten(DESIGN_SYSTEM["text"], 0.5),
    # Die Rahmenfarbe ist ein deutlich sichtbarer Grauton. Um eine klare
    # Abgrenzung zur hellen Kartenfläche zu erzielen, hellen wir die
    # Textfarbe nur um 50 % auf. Dies ergibt einen markanten Grauwert,
    # der die abgerundeten Kanten klar hervorhebt.
    "border": _lighten(DESIGN_SYSTEM["text"], 0.5),
    # Die Akzentfarbe für Buttons wird aus der Primärfarbe übernommen.
    "accent": DESIGN_SYSTEM["primary"],
    # Beim Drücken wird die Farbe um 20 % abgedunkelt, um einen visuellen
    # Feedbackeffekt zu erzeugen.
    "accent_active": _darken(DESIGN_SYSTEM["primary"], 0.2),
    # Auswahlhervorhebungen in Tabellen sind eine helle Variante der Primärfarbe.
    "selection": _lighten(DESIGN_SYSTEM["primary"], 0.8),
}

class RoundedButton(tk.Canvas):
    """Ein Button mit abgerundeten Ecken.

    Dieser Button zeichnet eine gefüllte abgerundete Form auf einem Canvas und
    setzt darüber einen Text. Er unterstützt Primär- und Sekundärfarben aus
    dem Designsystem, reagiert auf Hover- und Klick-Ereignisse und kann
    deaktiviert werden. Die Größe wird anhand des Textinhalts und einer
    angegebenen Polsterung automatisch berechnet.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        text: str,
        command: Optional[callable] = None,
        radius: int = 12,
        padding: Tuple[int, int] = (16, 8),
        bg: Optional[str] = None,
        fg: Optional[str] = None,
        active_bg: Optional[str] = None,
        disabled_bg: Optional[str] = None,
        disabled_fg: Optional[str] = None,
        font: Optional[Tuple[str, int]] = None,
        **kwargs,
    ) -> None:
        # Hintergrund des Canvas entspricht dem Hintergrund des Elternwidgets.
        parent_bg = None
        if isinstance(master, tk.Widget):
            try:
                parent_bg = master.cget("background")
            except tk.TclError:
                parent_bg = None
        if parent_bg is None:
            parent_bg = COLORS.get("background", "#ffffff")
        super().__init__(master, highlightthickness=0, bd=0, bg=parent_bg, **kwargs)
        self.text = text
        self.command = command
        self.radius = radius
        self.padding = padding
        self.bg = bg or COLORS["accent"]
        self.fg = fg or COLORS["surface"]
        self.active_bg = active_bg or _darken(self.bg, 0.2)
        # Farben für deaktivierten Zustand
        self.disabled_bg = disabled_bg or _lighten(self.bg, 0.4)
        self.disabled_fg = disabled_fg or _lighten(self.fg, 0.4)
        # Zustandsverwaltung
        self.state = "normal"
        # Schriftart bestimmen – wir nutzen die Standard-TkFont, falls keine
        # explizite Schrift angegeben wurde.
        if font is None:
            try:
                # TkDefaultFont liefert die Standard-Schrift des Systems.
                import tkinter.font as tkfont

                self.font = tkfont.nametofont("TkDefaultFont").copy()
                # Füge Fettung hinzu, damit Buttons präsenter wirken.
                self.font.configure(weight="bold")
            except Exception:
                self.font = None
        else:
            # Falls der Benutzer ein Tupel wie ("Helvetica", 12) übergibt.
            try:
                import tkinter.font as tkfont

                self.font = tkfont.Font(master=self, font=font)
            except Exception:
                self.font = None
        # Interne IDs für das Polygon und den Text
        self._rect_id: Optional[int] = None
        self._text_id: Optional[int] = None
        # Zeichne den Button initial
        self._draw(self.bg, self.fg)
        # Events für Hover und Klick
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)

    def _measure_text(self) -> Tuple[int, int]:
        """Gibt die Breite und Höhe des Textes in Pixeln zurück."""
        # Temporärer Text, um die Bounding Box zu bestimmen
        temp_id = self.create_text(0, 0, text=self.text, font=self.font, anchor="nw")
        bbox = self.bbox(temp_id)
        # Falls Font nicht messbar ist, setze Standardwerte
        if not bbox:
            width, height = 0, 0
        else:
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
        self.delete(temp_id)
        return width, height

    def _draw(self, fill: str, text_color: str) -> None:
        """Zeichnet die Button-Oberfläche neu."""
        # Lösche vorhandene Elemente
        self.delete("all")
        # Textmaße bestimmen
        text_width, text_height = self._measure_text()
        width = text_width + 2 * self.padding[0]
        height = text_height + 2 * self.padding[1]
        # Radius anpassen, damit er nicht größer als das halbe Widget ist
        r = min(self.radius, width // 2, height // 2)
        # Punkte für die abgerundete Form berechnen; wir ziehen 1 Pixel ab,
        # damit der Rand vollständig sichtbar bleibt.
        points = _rounded_polygon_points(width - 1, height - 1, r)
        self._rect_id = self.create_polygon(
            points,
            fill=fill,
            outline=fill,
            width=1,
            smooth=True,
        )
        # Zentrierten Text zeichnen
        self._text_id = self.create_text(
            width / 2,
            height / 2,
            text=self.text,
            fill=text_color,
            font=self.font,
            anchor="center",
        )
        # Canvas-Größe anpassen
        self.config(width=width, height=height)

    def _on_enter(self, event: tk.Event) -> None:
        if self.state == "normal":
            self.itemconfig(self._rect_id, fill=self.active_bg, outline=self.active_bg)

    def _on_leave(self, event: tk.Event) -> None:
        if self.state == "normal":
            self.itemconfig(self._rect_id, fill=self.bg, outline=self.bg)

    def _on_press(self, event: tk.Event) -> None:
        if self.state == "normal" and self.command:
            # Visual feedback für Klick
            self.itemconfig(self._rect_id, fill=self.active_bg, outline=self.active_bg)
            # Nach kurzer Verzögerung zur ursprünglichen Farbe zurückkehren
            self.after(100, lambda: self.itemconfig(self._rect_id, fill=self.bg, outline=self.bg))
            self.command()

    def configure(self, **kwargs) -> None:  # type: ignore[override]
        """Erlaubt das Ändern des Zustands oder anderer Parameter."""
        # Insbesondere erlauben wir die Einstellung des States über configure
        state = kwargs.pop("state", None)
        if state is not None:
            self.state = state
            if state == "disabled":
                self.itemconfig(self._rect_id, fill=self.disabled_bg, outline=self.disabled_bg)
                self.itemconfig(self._text_id, fill=self.disabled_fg)
            else:
                self.itemconfig(self._rect_id, fill=self.bg, outline=self.bg)
                self.itemconfig(self._text_id, fill=self.fg)
        # Andere Konfigurationsoptionen an Canvas weiterreichen
        if kwargs:
            super().configure(**kwargs)

# Eine kleine Hilfsfunktion erzeugt eine abgerundete Polygonform für den Canvas.
def _rounded_polygon_points(width: int, height: int, r: int) -> List[int]:
    """Berechnet Eckpunkte für ein Rechteck mit abgerundeten Ecken.

    Die Liste enthält 20 Koordinatenpaare (insgesamt 40 Werte). Mehrfach
    vorkommende Punkte sorgen dafür, dass Tkinter die Kurven sauber glättet.
    """
    return [
        r, 0,
        r, 0,
        width - r, 0,
        width - r, 0,
        width, 0,
        width, r,
        width, r,
        width, height - r,
        width, height - r,
        width, height,
        width - r, height,
        width - r, height,
        r, height,
        r, height,
        0, height,
        0, height - r,
        0, height - r,
        0, r,
        0, r,
        0, 0,
    ]


class RoundedFrame(tk.Frame):
    """Ein Container mit abgerundeten Ecken.

    Dieses Widget zeichnet automatisch einen abgerundeten Hintergrund in der
    angegebenen Farbe und stellt einen internen Frame (``inner_frame``) bereit,
    in dem weitere Widgets platziert werden können. Die abgerundete Form wird
    beim Größenwechsel neu berechnet, sodass sich das Element flexibel anpasst.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        radius: int = 16,
        bg: Optional[str] = None,
        bordercolor: Optional[str] = None,
        padding: Tuple[int, int] = (0, 0),
        **kwargs,
    ) -> None:
        # Hintergrundfarben und Randfarben aus dem Design übernehmen, falls
        # keine spezifischen Werte angegeben wurden.
        if bg is None:
            bg = COLORS["surface"]
        if bordercolor is None:
            bordercolor = COLORS["border"]

        # Der äußere Frame erbt den Hintergrund vom übergeordneten Element, um
        # die runden Ecken sichtbar zu machen. Border und Highlight werden
        # deaktiviert, damit keine zusätzlichen Linien gezeichnet werden.
        # Versuche, die Hintergrundfarbe des Elternwidgets zu ermitteln. Nicht alle
        # Widgets unterstützen die Option "background", daher fangen wir Fehler ab
        # und verwenden eine Standardfarbe aus dem Designsystem als Fallback.
        parent_bg = None
        if isinstance(master, tk.Widget):
            try:
                parent_bg = master.cget("background")
            except tk.TclError:
                # Einige ttk‑Widgets besitzen keine "-background"‑Option.
                parent_bg = None
        # Wenn keine Hintergrundfarbe ermittelt werden konnte, auf die
        # Hintergrundfarbe des Designsystems zurückgreifen.
        if parent_bg is None:
            parent_bg = COLORS.get("background", "#ffffff")

        super().__init__(
            master,
            bg=parent_bg,
            bd=0,
            highlightthickness=0,
            **kwargs,
        )
        self.radius = max(radius, 0)
        self.bg_color = bg
        self.border_color = bordercolor
        self.padding = padding
        # Canvas für die gezeichnete Hintergrundform
        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            bd=0,
            bg=self.cget("background"),
            relief="flat",
        )
        self.canvas.pack(fill="both", expand=True)
        # Interner Frame für Inhalte. Wir verwenden denselben Style wie für
        # Karten, damit Schriften und Eingabefelder identisch aussehen.
        self.inner_frame = ttk.Frame(self.canvas, style="Card.TFrame")
        # Die ID des Canvas-Elements, das den inneren Frame enthält. Diese
        # benötigen wir später, um die Größe anzupassen.
        self._inner_window_id = self.canvas.create_window(
            self.padding[0],
            self.padding[1],
            window=self.inner_frame,
            anchor="nw",
        )
        # Die ID des gezeichneten Polygons für den runden Hintergrund.
        self._rect_id: Optional[int] = None
        # Bei jeder Größenänderung des Canvas aktualisieren wir Form und Größe.
        self.canvas.bind("<Configure>", self._on_configure)

    def _on_configure(self, event: tk.Event) -> None:
        """Reagiert auf Größenänderungen und zeichnet die runde Form neu."""
        width = event.width
        height = event.height
        # Die Größe des inneren Fensters wird anhand der gewünschten Polsterung
        # angepasst. Dabei bleibt die obere linke Ecke an der selben Position.
        inner_width = max(0, width - 2 * self.padding[0])
        inner_height = max(0, height - 2 * self.padding[1])
        self.canvas.itemconfig(self._inner_window_id, width=inner_width, height=inner_height)
        # Punkte für das abgerundete Polygon berechnen
        r = min(self.radius, width // 2, height // 2)
        # Wir ziehen 1 Pixel von Breite und Höhe ab, damit der Rand innen
        # vollständig sichtbar bleibt. Sonst kann der rechte und untere Rand
        # abgeschnitten erscheinen.
        points = _rounded_polygon_points(width - 1, height - 1, r)
        # Vorhandene Form löschen und neu zeichnen
        if self._rect_id:
            self.canvas.delete(self._rect_id)
        self._rect_id = self.canvas.create_polygon(
            points,
            fill=self.bg_color,
            outline=self.border_color,
            width=1,
            smooth=True,
        )

# Datenbankwerte für Verfügbarkeit und Zustand werden in der Oberfläche
# freundlich übersetzt. Unbekannte Werte werden später einfach unverändert
# angezeigt, damit keine Information verloren geht.
AVAILABILITY_LABELS = {
    "available": "Verfügbar",
    "borrowed": "Ausgeliehen",
    "borrowed_out": "Ausgeliehen",
    "lent": "Ausgeliehen",
    "loaned": "Ausgeliehen",
    "reserved": "Reserviert",
    "unavailable": "Nicht verfügbar",
    "maintenance": "In Bearbeitung",
    "damaged": "Beschädigt",
    "lost": "Verloren",
}

STATE_LABELS = {
    "new": "Neu",
    "good": "Gut",
    "used": "Gebraucht",
    "worn": "Abgenutzt",
    "damaged": "Beschädigt",
    "lost": "Verloren",
}

# Jedes Tag bekommt in der Exemplartabelle eine eigene Farbe. Die Tag-Namen
# bleiben technisch/englisch, weil sie nicht sichtbar sind.
AVAILABILITY_ROW_STYLES = {
    "availability_available": ("#DCFCE7", "#14532D"),
    "availability_borrowed": ("#FEE2E2", "#991B1B"),
    "availability_reserved": ("#FEF3C7", "#92400E"),
    "availability_unavailable": ("#E5E7EB", "#374151"),
    "availability_problem": ("#FFEDD5", "#9A3412"),
    "availability_unknown": (COLORS["surface"], COLORS["text"]),
}


class LibraryApp:
    """Baut die Anwendung auf und verarbeitet alle Benutzeraktionen.

    Eine Klasse ist hier sinnvoll, weil viele Widgets und Zustände
    zusammengehören. Über ``self`` können Methoden wie ``run_search`` später
    auf Eingabefelder, Tabelle und Statuszeile zugreifen.
    """

    def __init__(self, root: tk.Tk):
        """Initialisiert Fensterzustand, Design und Oberfläche.

        ``__init__`` wird automatisch ausgeführt, sobald unten mit
        ``LibraryApp(root)`` ein Objekt dieser Klasse erzeugt wird.
        """

        # ``root`` ist das Hauptfenster, das in ``main`` mit ``tk.Tk()``
        # erstellt wird. Wir speichern es, damit alle Methoden darauf zugreifen.
        self.root = root

        # Fenstertitel und Startgröße. ``minsize`` verhindert, dass das Fenster
        # so klein gezogen wird, dass Eingabefelder und Tabelle unbrauchbar sind.
        self.root.title("Bibliothek")
        self.root.geometry("1040x680")
        self.root.minsize(820, 560)
        self.root.configure(background=COLORS["background"])

        # StringVar verbindet einen Python-Textwert mit einem Tkinter-Widget.
        # Wenn ein Benutzer tippt, liefert ``variable.get()`` den aktuellen
        # Inhalt. Mit ``variable.set(...)`` kann der Inhalt geändert werden.
        self.title_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.category_var = tk.StringVar(value="Alle Kategorien")
        self.isbn_var = tk.StringVar()

        # Die Statusvariable wird mit dem Text unterhalb der Tabelle verbunden.
        # Such- und Sortiermethoden können dort Rückmeldungen anzeigen.
        self.status_var = tk.StringVar(value="Bereit für die Suche")

        # Hier merken wir uns den aktuellen Sortierzustand:
        # ``None`` bedeutet, dass noch keine Spalte gewählt wurde.
        # ``False`` steht für aufsteigend, ``True`` für absteigend.
        self.sort_column = None
        self.sort_descending = False

        # Geöffnete Exemplarseiten werden hier nach ISBN gemerkt. So wird ein
        # bereits offenes Detailfenster nur nach vorne geholt statt dupliziert.
        self.copy_detail_windows = {}

        # Zuerst definieren wir das Aussehen, danach werden die Widgets gebaut.
        # So kennen alle Widgets ihre Styles bereits bei der Erstellung.
        self._configure_styles()
        self._build_ui()

        # ``bind`` verbindet ein Tastaturereignis mit einer Funktion. Tkinter
        # übergibt dabei automatisch ein Event-Objekt. Da ``run_search`` dieses
        # Objekt nicht benötigt, nimmt die Lambda-Funktion es als ``_event`` an
        # und ruft anschließend die eigentliche Suchmethode ohne Argument auf.
        self.root.bind("<Return>", lambda _event: self.run_search())

        # Der Cursor soll beim Start direkt im Titelfeld stehen.
        self.title_entry.focus_set()

    def _configure_styles(self):
        """Definiert das gemeinsame visuelle Erscheinungsbild der Widgets."""

        # ttk ist die modernere Widget-Sammlung von Tkinter. Ein Style-Objekt
        # kontrolliert ihr Aussehen zentral, ähnlich wie CSS auf einer Webseite.
        style = ttk.Style(self.root)

        # "clam" lässt sich plattformübergreifend zuverlässig einfärben.
        # Manche nativen Themes ignorieren eigene Farben teilweise.
        style.theme_use("clam")

        # Der Style "." gilt als Grundeinstellung für alle ttk-Widgets.
        style.configure(".", font=("Segoe UI", 10))

        # Eigene Namen wie "Card.TFrame" erlauben verschiedene Varianten
        # desselben Widget-Typs. Ein Frame kann dadurch z.B. Hintergrund oder
        # weiße Kartenfläche sein.
        style.configure("App.TFrame", background=COLORS["background"])
        style.configure("Card.TFrame", background=COLORS["surface"])

        # Große Überschrift der Anwendung.
        style.configure(
            "Title.TLabel",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=("Segoe UI Semibold", 24),
        )

        # Unauffälligere Beschreibung direkt unter der Überschrift.
        style.configure(
            "Subtitle.TLabel",
            background=COLORS["background"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 10),
        )

        # Überschriften innerhalb der weißen Karten.
        style.configure(
            "Section.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Segoe UI Semibold", 12),
        )

        # Kleine Beschriftungen über den Eingabefeldern.
        style.configure(
            "Field.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["muted"],
            font=("Segoe UI Semibold", 9),
        )

        # Rückmeldung unterhalb der Ergebnistabelle.
        style.configure(
            "Status.TLabel",
            background=COLORS["background"],
            foreground=COLORS["muted"],
        )

        # Innenabstand und Randfarben der normalen Texteingaben.
        style.configure(
            "TEntry",
            padding=(10, 8),
            fieldbackground=COLORS["surface"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
        )

        # Combobox ist das Auswahlfeld für Kategorien.
        style.configure(
            "TCombobox",
            padding=(10, 8),
            fieldbackground=COLORS["surface"],
            bordercolor=COLORS["border"],
            arrowcolor=COLORS["muted"],
        )

        # Der primäre Button ist die wichtigste Aktion und deshalb blau.
        style.configure(
            "Primary.TButton",
            padding=(20, 10),
            background=COLORS["accent"],
            foreground="#FFFFFF",
            borderwidth=0,
            font=("Segoe UI Semibold", 10),
        )

        # ``map`` definiert zustandsabhängige Farben. Beim Darüberfahren
        # ("active") oder Klicken ("pressed") wird der Button dunkler.
        style.map(
            "Primary.TButton",
            background=[
                ("pressed", COLORS["accent_active"]),
                ("active", COLORS["accent_active"]),
            ],
        )

        # Der Zurücksetzen-Button ist bewusst zurückhaltender gestaltet,
        # weil er gegenüber der Suche eine sekundäre Aktion ist. Hier verwenden
        # wir die im Design‑System definierte Sekundärfarbe. Eine leichte
        # Aufhellung beim Darüberfahren vermittelt Feedback und erzeugt ein
        # hochwertiges Gefühl.
        secondary_bg = DESIGN_SYSTEM["secondary"]
        style.configure(
            "Secondary.TButton",
            padding=(16, 10),
            background=secondary_bg,
            foreground=COLORS["text"],
            bordercolor=_lighten(COLORS["border"], 0.1),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", _lighten(secondary_bg, 0.1))],
        )

        # Treeview ist das ttk-Widget für tabellarische Daten.
        style.configure(
            "Treeview",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=34,
            borderwidth=0,
        )

        # Eine ausgewählte Tabellenzeile erhält einen hellblauen Hintergrund.
        style.map(
            "Treeview",
            background=[("selected", COLORS["selection"])],
            foreground=[("selected", COLORS["text"])],
        )

        # Separater Style für die Spaltenüberschriften.
        # Für die Spaltenüberschriften nutzen wir einen sehr hellen Ton der
        # Primärfarbe. Diese dezente Einfärbung grenzt die Überschriften von
        # den Datenzeilen ab, ohne zu viel Aufmerksamkeit zu erregen. Beim
        # Darüberfahren wird die Farbe minimal dunkler.
        heading_bg = _lighten(DESIGN_SYSTEM["primary"], 0.9)
        heading_active = _lighten(DESIGN_SYSTEM["primary"], 0.85)
        style.configure(
            "Treeview.Heading",
            background=heading_bg,
            foreground=COLORS["text"],
            padding=(10, 9),
            borderwidth=0,
            font=("Segoe UI Semibold", 9),
        )
        style.map("Treeview.Heading", background=[("active", heading_active)])

    def _build_ui(self):
        """Erstellt alle sichtbaren Bereiche und ordnet sie im Fenster an."""

        # Der äußere Container hält die gesamte Oberfläche zusammen.
        # ``padding`` erzeugt Abstand zum Fensterrand.
        container = ttk.Frame(self.root, style="App.TFrame", padding=(32, 26, 32, 20))

        # ``pack`` füllt mit diesem einen Hauptcontainer das komplette Fenster.
        # Innerhalb des Containers verwenden wir danach ``grid`` für ein
        # genaueres Zeilen-/Spaltenlayout. Pack und Grid sollten nicht im
        # gleichen Eltern-Widget gemischt werden, in verschiedenen aber schon.
        container.pack(fill="both", expand=True)

        # Gewicht 1 bedeutet: Spalte 0 und Zeile 2 erhalten zusätzlichen Platz,
        # wenn das Fenster vergrößert wird. Zeile 2 enthält die Tabelle.
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        # Kopfbereich mit Titel und kurzer Beschreibung.
        header = ttk.Frame(container, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 22))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Bibliothekskatalog", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Durchsuche den Bestand nach Titel, Autor, Kategorie oder ISBN.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(
            header,
            text="Buch hinzufügen",
            style="Primary.TButton",
            command=self.open_add_book_dialog,
        ).grid(row=0, column=1, rowspan=2, sticky="ne")

        # Die Suchfelder liegen zusammen in einer weißen "Karte". Wir nutzen
        # einen abgerundeten Frame, um weichere Ecken zu erhalten.
        search_card = RoundedFrame(
            container,
            radius=24,
            bg=COLORS["surface"],
            bordercolor=COLORS["border"],
            padding=(20, 20),
        )
        search_card.grid(row=1, column=0, sticky="ew", pady=(0, 18))

        # Alle vier Spalten erhalten dasselbe Gewicht und werden gleichmäßig
        # breiter, wenn mehr horizontaler Platz vorhanden ist. Die Konfiguration
        # erfolgt auf dem inneren Frame des RoundedFrame.
        for column in range(4):
            search_card.inner_frame.columnconfigure(column, weight=1)

        ttk.Label(
            search_card.inner_frame,
            text="Suche",
            style="Section.TLabel",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 16))

        # Titel, Autor und ISBN bestehen jeweils aus Label + Entry. Die
        # Hilfsmethode verhindert, dass derselbe Aufbau dreimal kopiert wird.
        # Das Titelfeld speichern wir zusätzlich, weil es später fokussiert wird.
        self.title_entry = self._add_field(
            search_card.inner_frame, "TITEL", self.title_var, 1, 0
        )
        self._add_field(search_card.inner_frame, "AUTOR", self.author_var, 1, 1)

        # Die Kategorie ist keine freie Texteingabe, sondern eine Combobox.
        # Dadurch können nur gültige Kategorien ausgewählt werden.
        ttk.Label(
            search_card.inner_frame,
            text="KATEGORIE",
            style="Field.TLabel",
        ).grid(row=1, column=2, sticky="w", padx=(0, 12))
        category = ttk.Combobox(
            search_card.inner_frame,
            textvariable=self.category_var,
            values=["Alle Kategorien", *CATEGORIES.values()],
            state="readonly",
        )

        # ``sticky="ew"`` zieht das Widget an den linken und rechten Rand
        # seiner Grid-Zelle, es füllt die verfügbare Breite also aus.
        category.grid(row=2, column=2, sticky="ew", padx=(0, 12), pady=(6, 0))

        self._add_field(search_card.inner_frame, "ISBN", self.isbn_var, 1, 3, right_padding=0)

        # Ein eigener Frame hält beide Buttons als zusammengehörige Gruppe.
        # ``sticky="e"`` richtet diese Gruppe am rechten Rand aus. Wir
        # platzieren ihn ebenfalls im inneren Bereich des abgerundeten
        # Rahmens. Statt Standard-Buttons verwenden wir eigens definierte
        # ``RoundedButton``-Widgets, die weiche Kanten besitzen und sich
        # optisch in das restliche Design einfügen.
        actions = ttk.Frame(search_card.inner_frame, style="Card.TFrame")
        actions.grid(row=3, column=0, columnspan=4, sticky="e", pady=(18, 0))
        reset_btn = RoundedButton(
            actions,
            text="Zurücksetzen",
            command=self.reset_search,
            bg=DESIGN_SYSTEM["secondary"],
            fg=COLORS["text"],
            active_bg=_lighten(DESIGN_SYSTEM["secondary"], 0.1),
            radius=12,
            padding=(16, 8),
        )
        reset_btn.pack(side="left", padx=(0, 10))
        search_btn = RoundedButton(
            actions,
            text="Bestand durchsuchen",
            command=self.run_search,
            bg=DESIGN_SYSTEM["primary"],
            fg=COLORS["surface"],
            active_bg=_darken(DESIGN_SYSTEM["primary"], 0.2),
            radius=12,
            padding=(16, 8),
        )
        search_btn.pack(side="left")

        # Zweite weiße Karte für Überschrift, Tabelle und Scrollbar. Die
        # abgerundeten Ecken sorgen für ein ruhigeres Erscheinungsbild.
        results_card = RoundedFrame(
            container,
            radius=24,
            bg=COLORS["surface"],
            bordercolor=COLORS["border"],
            padding=(20, 18),
        )
        results_card.grid(row=2, column=0, sticky="nsew")
        results_card.inner_frame.columnconfigure(0, weight=1)
        results_card.inner_frame.rowconfigure(1, weight=1)
        ttk.Label(
            results_card.inner_frame,
            text="Suchergebnisse",
            style="Section.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        # Interne Spaltennamen. Sie werden zum Lesen und Sortieren verwendet,
        # während die deutschen Texte weiter unten nur zur Anzeige dienen.
        columns = (
            "isbn",
            "title",
            "author",
            "category",
            "language",
            "year",
            "copies",
        )

        # ``show="headings"`` blendet die sonst standardmäßig vorhandene
        # Baumspalte aus. ``browse`` erlaubt die Auswahl genau einer Zeile.
        self.results = ttk.Treeview(
            results_card.inner_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        # Trennung von internen Namen und sichtbaren Überschriften.
        self.column_headings = {
            "isbn": "ISBN",
            "title": "Titel",
            "author": "Autor",
            "category": "Kategorie",
            "language": "Sprache",
            "year": "Erscheinungsdatum",
            "copies": "Exemplare",
        }

        # Sinnvolle Startbreiten. Titel und Autor dürfen sich später dehnen.
        widths = {
            "isbn": 120,
            "title": 250,
            "author": 180,
            "category": 120,
            "language": 90,
            "year": 125,
            "copies": 85,
        }

        # Jede Spalte erhält Überschrift, Klickfunktion und Größenregeln.
        for column in columns:
            self.results.heading(
                column,
                text=self.column_headings[column],

                # Wichtiges Lambda-Detail: ``selected_column=column`` speichert
                # den aktuellen Schleifenwert sofort. Ohne diesen Standardwert
                # würden später alle Überschriften auf die letzte Spalte zeigen.
                command=lambda selected_column=column: self.sort_results(
                    selected_column
                ),
            )
            self.results.column(
                column,
                width=widths[column],
                minwidth=70,
                stretch=column in {"title", "author"},
                # Zahlen lassen sich mittig schneller erfassen. Textspalten
                # bleiben linksbündig, wie man es beim Lesen erwartet.
                anchor="center" if column == "copies" else "w",
            )

        # Treeview und Scrollbar müssen gegenseitig verbunden werden:
        # Der Scrollbar-Befehl bewegt die Tabelle; ``yscrollcommand`` bewegt
        # umgekehrt den Scrollbar-Regler, wenn die Tabelle gescrollt wird.
        scrollbar = ttk.Scrollbar(
            results_card.inner_frame, orient="vertical", command=self.results.yview
        )
        self.results.configure(yscrollcommand=scrollbar.set)
        self.results.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        # Rechtsklick-Menü für Tabellenzeilen. Beim Rechtsklick wird zuerst
        # die Zeile unter dem Mauszeiger ausgewählt. Danach kann der Benutzer
        # den Eintrag über den Menüpunkt löschen.
        self.results_menu = tk.Menu(self.root, tearoff=False)
        self.results_menu.add_command(
            label="Exemplare anzeigen",
            command=self.open_selected_book_detail,
        )
        self.results_menu.add_separator()
        self.results_menu.add_command(
            label="Eintrag löschen",
            command=self.delete_selected_entry,
        )

        # Linksklick auf eine Buchzeile öffnet die neue Exemplarseite.
        # Rechtsklick bleibt weiterhin für das Kontextmenü zum Löschen frei.
        self.results.bind("<ButtonRelease-1>", self.open_clicked_book_detail)
        self.results.bind("<Button-3>", self.open_results_context_menu)

        # Statuszeile außerhalb der Karte, z.B. "25 Treffer gefunden".
        ttk.Label(container, textvariable=self.status_var, style="Status.TLabel").grid(
            row=3, column=0, sticky="w", pady=(10, 0)
        )

    @staticmethod
    def _add_field(parent, label, variable, row, column, right_padding=12):
        """Erstellt ein beschriftetes Eingabefeld und gibt das Entry zurück.

        Die Methode benötigt keinen Zustand aus ``self`` und ist deshalb
        ``staticmethod``. ``parent`` ist der Frame, in den die Widgets kommen.
        ``row`` und ``column`` bestimmen ihre Position im Grid.
        """

        # Das Label steht in der übergebenen Zeile.
        ttk.Label(parent, text=label, style="Field.TLabel").grid(
            row=row, column=column, sticky="w", padx=(0, right_padding)
        )

        # Das Eingabefeld steht genau eine Zeile darunter. ``textvariable``
        # verbindet es mit der passenden StringVar der Anwendung.
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(
            row=row + 1,
            column=column,
            sticky="ew",
            padx=(0, right_padding),
            pady=(6, 0),
        )

        # Der Aufrufer kann das Entry dadurch speichern und später fokussieren.
        return entry

    def run_search(self):
        """Liest die Filter, sucht Bücher und füllt die Ergebnistabelle."""

        # Die Combobox zeigt deutsche Namen. Für die Datenbank übersetzen wir
        # zurück. "Alle Kategorien" kommt im Dictionary nicht vor und ergibt
        # durch ``get(..., "")`` einen leeren Filter.
        category = CATEGORY_BY_LABEL.get(self.category_var.get(), "")

        # Datenbankzugriffe können fehlschlagen, z.B. wenn die Datei fehlt.
        # Die GUI fängt den Fehler ab, damit nicht das gesamte Fenster abstürzt.
        try:
            rows = search_books(
                # ``strip`` entfernt versehentliche Leerzeichen am Anfang/Ende.
                self.title_var.get().strip(),
                self.author_var.get().strip(),
                category,
                self.isbn_var.get().strip(),
            )
        except Exception as error:
            # Eine Messagebox ist für Benutzer verständlicher als ein
            # Python-Traceback in einem möglicherweise unsichtbaren Terminal.
            messagebox.showerror(
                "Suche fehlgeschlagen",
                f"Die Bibliotheksdaten konnten nicht geladen werden.\n\n{error}",
            )
            self.status_var.set("Fehler beim Laden der Suchergebnisse")
            return

        # Vor jeder neuen Suche entfernen wir alte Zeilen. ``get_children``
        # liefert ihre IDs; der Stern entpackt diese IDs als Einzelargumente.
        self.results.delete(*self.results.get_children())

        # Jede Datenbankzeile ist ein Tupel mit genau den sieben SELECT-Spalten.
        for (
            isbn,
            title,
            author,
            category_name,
            language,
            release_date,
            copy_count,
        ) in rows:
            self.results.insert(
                # Leerer String als Eltern-ID bedeutet: normale oberste Zeile.
                "",
                # "end" hängt die neue Zeile unten an.
                "end",
                values=(
                    # SQLite kann für fehlende Werte ``None`` liefern.
                    # ``or ""`` zeigt stattdessen eine saubere leere Zelle.
                    isbn or "",
                    title or "",
                    author or "",

                    # Die englische Kategorie wird nur für die Anzeige übersetzt.
                    CATEGORIES.get(category_name, category_name) if category_name else "",
                    language or "",

                    # Die Datenbank speichert vollständige Daten im technisch
                    # üblichen ISO-Format JJJJ-MM-TT. In der deutschen
                    # Oberfläche zeigen wir sie als TT.MM.JJJJ an.
                    self._format_date(release_date),

                    # COUNT(*) liefert immer eine Zahl, auch wenn sie 0 ist.
                    # Deshalb verwenden wir hier nicht ``or ""``: Eine Null
                    # ist eine wichtige Information und soll sichtbar bleiben.
                    copy_count,
                ),
            )

        count = len(rows)

        # Falls vorher schon sortiert wurde, soll diese Sortierung auch auf die
        # neuen Suchergebnisse angewendet werden.
        if self.sort_column:
            self._apply_sort()

        # Kurze Rückmeldung, auch wenn keine Treffer vorhanden sind.
        self.status_var.set(
            f"{count} {'Treffer' if count == 1 else 'Treffer'} gefunden"
            if count
            else "Keine passenden Bücher gefunden"
        )

    def sort_results(self, column):
        """Reagiert auf einen Klick auf eine Tabellenüberschrift.

        Erster Klick auf eine Spalte: aufsteigend.
        Zweiter Klick auf dieselbe Spalte: absteigend.
        Klick auf eine andere Spalte: dort wieder aufsteigend beginnen.
        """

        if self.sort_column == column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            self.sort_descending = False
        self._apply_sort()

    def _apply_sort(self):
        """Sortiert vorhandene Treeview-Zeilen und aktualisiert den Pfeil."""

        # Treeview speichert jede Zeile unter einer internen ID wie "I001".
        # Wir sortieren diese IDs und verschieben danach die zugehörigen Zeilen.
        items = list(self.results.get_children())

        # Leere Werte werden getrennt gesammelt. So bleiben sie sowohl bei
        # aufsteigender als auch bei absteigender Sortierung immer unten.
        populated = []
        empty = []

        for item in items:
            # ``set(item, column)`` liest den sichtbaren Zelleninhalt.
            value = self.results.set(item, self.sort_column).strip()
            target = populated if value else empty

            # Gespeichert werden der vergleichbare Sortierwert und die Zeilen-ID.
            target.append((self._sort_value(self.sort_column, value), item))

        # Python sortiert standardmäßig aufsteigend. ``reverse=True`` dreht die
        # Reihenfolge für eine absteigende Sortierung um.
        populated.sort(key=lambda entry: entry[0], reverse=self.sort_descending)

        # Zuerst alle gefüllten, danach alle leeren Einträge.
        ordered_items = [item for _value, item in populated + empty]
        for position, item in enumerate(ordered_items):
            # ``move`` verändert nur die Position der vorhandenen Tabellenzeile.
            self.results.move(item, "", position)

        # Nur die aktive Spalte erhält einen Richtungspfeil. Alle anderen
        # Überschriften werden gleichzeitig auf ihren Grundtext zurückgesetzt.
        for column, heading in self.column_headings.items():
            indicator = ""
            if column == self.sort_column:
                indicator = " ▼" if self.sort_descending else " ▲"
            self.results.heading(column, text=f"{heading}{indicator}")

        # Auch textlich anzeigen, nach welcher Richtung sortiert wurde.
        direction = "absteigend" if self.sort_descending else "aufsteigend"
        self.status_var.set(
            f"Sortiert nach {self.column_headings[self.sort_column]} ({direction})"
        )

    @staticmethod
    def _sort_value(column, value):
        """Wandelt sichtbaren Text in einen sinnvoll sortierbaren Wert um."""

        # Exemplarzahlen müssen numerisch sortiert werden. Als Text würde
        # beispielsweise "10" fälschlich vor "2" einsortiert.
        if column == "copies":
            return int(value)

        # Datumsangaben müssen als Datum statt alphabetisch verglichen werden.
        # Sonst könnte z.B. "31.12.2020" falsch vor "01.01.2024" landen.
        if column == "year":
            # Die Datenbank kann mehrere übliche Datumsformate enthalten.
            # Wir probieren sie nacheinander, bis eines passt.
            for date_format in ("%Y-%m-%d", "%d.%m.%Y", "%Y"):
                try:
                    return datetime.strptime(value, date_format)
                except ValueError:
                    # ValueError bedeutet hier nur: Dieses Format war es nicht.
                    continue

        # ``casefold`` ist eine robuste Kleinschreibung für Vergleiche.
        # Groß-/Kleinschreibung beeinflusst damit die Reihenfolge nicht.
        return value.casefold()

    @staticmethod
    def _format_date(value):
        """Formatiert ein Datenbankdatum für die deutsche Oberfläche.

        Vollständige ISO-Daten wie ``2025-02-10`` werden zu ``10.02.2025``.
        Reine Jahreszahlen bleiben unverändert, weil Monat und Tag unbekannt
        sind und deshalb nicht künstlich ergänzt werden dürfen.
        """

        # Ein SQL-NULL kommt in Python als None an und soll leer erscheinen.
        if not value:
            return ""

        # SQLite besitzt keinen verpflichtenden Datumstyp. Der Wert könnte
        # deshalb theoretisch auch als Zahl ankommen; str macht ihn einheitlich.
        value = str(value)

        try:
            # strptime liest den ISO-Text als echtes Datum ein. strftime gibt
            # dasselbe Datum anschließend in deutscher Reihenfolge wieder aus.
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
        except ValueError:
            # Jahreszahlen und unbekannte Altformate zeigen wir unverändert.
            # Damit gehen keine Informationen durch eine falsche Annahme verloren.
            return value

    @staticmethod
    def _translate_value(value, translations):
        """Übersetzt technische Datenbankwerte für die Anzeige."""

        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        return translations.get(text.casefold(), text)

    @classmethod
    def _availability_label(cls, availability):
        """Liefert den deutschen Anzeigetext für eine Verfügbarkeit."""

        return cls._translate_value(availability, AVAILABILITY_LABELS)

    @classmethod
    def _state_label(cls, state):
        """Liefert den deutschen Anzeigetext für einen Exemplarzustand."""

        return cls._translate_value(state, STATE_LABELS)

    @staticmethod
    def _availability_tag(availability):
        """Ordnet eine Verfügbarkeit dem passenden Farb‑Tag zu."""

        normalized = str(availability or "").strip().casefold()
        if normalized in {"available", "verfügbar", "verfuegbar", "frei"}:
            return "availability_available"
        if normalized in {
            "borrowed",
            "borrowed_out",
            "lent",
            "loaned",
            "ausgeliehen",
            "entliehen",
        }:
            return "availability_borrowed"
        if normalized in {"reserved", "reserviert"}:
            return "availability_reserved"
        if normalized in {
            "unavailable",
            "nicht verfügbar",
            "nicht verfuegbar",
            "gesperrt",
        }:
            return "availability_unavailable"
        if normalized in {
            "maintenance",
            "in bearbeitung",
            "damaged",
            "beschädigt",
            "beschaedigt",
            "lost",
            "verloren",
        }:
            return "availability_problem"
        return "availability_unknown"

    def open_clicked_book_detail(self, event):
        """Öffnet die Exemplarseite, wenn eine Buchzeile angeklickt wurde."""

        # Klicks auf Überschriften oder leere Flächen sollen keine Seite
        # öffnen. Nur echte Tabellenzellen reagieren.
        if self.results.identify_region(event.x, event.y) != "cell":
            return

        item = self.results.identify_row(event.y)
        if not item:
            return

        self.results.selection_set(item)
        self.results.focus(item)
        self.open_book_detail(item)

    def open_selected_book_detail(self):
        """Öffnet die Exemplarseite für die aktuell ausgewählte Zeile."""

        selection = self.results.selection()
        if selection:
            self.open_book_detail(selection[0])

    def open_book_detail(self, item):
        """Lädt alle Exemplare eines Buches und zeigt sie in einem neuen Fenster."""

        values = self.results.item(item, "values")
        if not values:
            return

        isbn = values[0]
        title = values[1] if len(values) > 1 and values[1] else isbn
        author = values[2] if len(values) > 2 else ""
        category = values[3] if len(values) > 3 else ""
        language = values[4] if len(values) > 4 else ""
        release_date = values[5] if len(values) > 5 else ""

        if not isbn:
            messagebox.showerror(
                "Exemplare nicht gefunden",
                "Dieser Eintrag hat keine ISBN und kann deshalb nicht eindeutig geöffnet werden.",
                parent=self.root,
            )
            return

        existing_window = self.copy_detail_windows.get(isbn)
        if existing_window and existing_window.winfo_exists():
            existing_window.lift()
            existing_window.focus_force()
            return

        try:
            copies = get_book_copies(isbn)
        except Exception as error:
            messagebox.showerror(
                "Exemplare konnten nicht geladen werden",
                f"Die Exemplare dieses Buches konnten nicht geladen werden.\n\n{error}",
                parent=self.root,
            )
            self.status_var.set("Fehler beim Laden der Exemplare")
            return

        detail = tk.Toplevel(self.root)
        detail.title(f"Exemplare: {title}")
        detail.geometry("760x460")
        detail.minsize(620, 360)
        detail.configure(background=COLORS["background"])
        detail.transient(self.root)
        self.copy_detail_windows[isbn] = detail

        def close_detail():
            self.copy_detail_windows.pop(isbn, None)
            detail.destroy()

        detail.protocol("WM_DELETE_WINDOW", close_detail)

        container = ttk.Frame(
            detail, style="App.TFrame", padding=(28, 24, 28, 20)
        )
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        ttk.Label(
            container,
            text=title,
            style="Title.TLabel",
            wraplength=680,
        ).grid(row=0, column=0, sticky="w")

        meta_parts = [f"ISBN: {isbn}"]
        if author:
            meta_parts.append(f"Autor: {author}")
        if category:
            meta_parts.append(f"Kategorie: {category}")
        if language:
            meta_parts.append(f"Sprache: {language}")
        if release_date:
            meta_parts.append(f"Erscheinung: {release_date}")

        ttk.Label(
            container,
            text=" · ".join(meta_parts),
            style="Subtitle.TLabel",
            wraplength=700,
        ).grid(row=1, column=0, sticky="w", pady=(4, 18))

        # Ersetze die einfache Frame-Karte durch einen abgerundeten Frame für
        # die Exemplartabelle. So bleibt die Detailansicht konsistent mit dem
        # restlichen Design. Der Inhalt wird über den inneren Frame platziert.
        copies_card = RoundedFrame(
            container,
            radius=24,
            bg=COLORS["surface"],
            bordercolor=COLORS["border"],
            padding=(18, 16),
        )
        copies_card.grid(row=2, column=0, sticky="nsew")
        copies_card.inner_frame.columnconfigure(0, weight=1)
        copies_card.inner_frame.rowconfigure(2, weight=1)

        ttk.Label(copies_card.inner_frame, text="Exemplare", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            copies_card.inner_frame,
            text=self._copies_summary(copies),
            style="Field.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        columns = ("copy_id", "state", "availability")
        copy_table = ttk.Treeview(
            copies_card.inner_frame, columns=columns, show="headings", selectmode="browse"
        )

        copy_table.heading("copy_id", text="Exemplar-ID")
        copy_table.heading("state", text="Zustand")
        copy_table.heading("availability", text="Verfügbarkeit")
        copy_table.column("copy_id", width=180, minwidth=120, anchor="w")
        copy_table.column("state", width=160, minwidth=100, anchor="w")
        copy_table.column("availability", width=180, minwidth=120, anchor="w")

        for tag, (background, foreground) in AVAILABILITY_ROW_STYLES.items():
            copy_table.tag_configure(
                tag, background=background, foreground=foreground
            )

        if copies:
            for copy_id, state, availability in copies:
                copy_table.insert(
                    "",
                    "end",
                    values=(
                        copy_id or "",
                        self._state_label(state),
                        self._availability_label(availability),
                    ),
                    tags=(self._availability_tag(availability),),
                )
        else:
            copy_table.insert(
                "",
                "end",
                values=("", "Keine Exemplare gespeichert", ""),
                tags=("availability_unknown",),
            )

        scrollbar = ttk.Scrollbar(
            copies_card.inner_frame, orient="vertical", command=copy_table.yview
        )
        copy_table.configure(yscrollcommand=scrollbar.set)
        copy_table.grid(row=2, column=0, sticky="nsew")
        scrollbar.grid(row=2, column=1, sticky="ns")

        self.status_var.set(f'Exemplare von "{title}" geöffnet')

    def _copies_summary(self, copies):
        """Erzeugt eine kurze Zusammenfassung der Verfügbarkeiten."""

        if not copies:
            return "Für dieses Buch sind keine Exemplare gespeichert."

        availability_counts = Counter(
            self._availability_label(availability) or "Unbekannt"
            for _copy_id, _state, availability in copies
        )
        summary = ", ".join(
            f"{count} {label}" for label, count in availability_counts.items()
        )
        return f"{len(copies)} Exemplare insgesamt · {summary}"

    def open_results_context_menu(self, event):
        """Öffnet beim Rechtsklick ein Menü für die angeklickte Tabellenzeile."""

        # ``identify_row`` liefert die interne Treeview-ID der Zeile unter dem
        # Mauszeiger. Bei Rechtsklick auf leere Tabellenfläche passiert nichts.
        item = self.results.identify_row(event.y)
        if not item:
            return

        self.results.selection_set(item)
        self.results.focus(item)

        try:
            self.results_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.results_menu.grab_release()

    def delete_selected_entry(self):
        """Löscht den ausgewählten Bucheintrag nach einer Sicherheitsabfrage."""

        selection = self.results.selection()
        if not selection:
            return

        item = selection[0]
        values = self.results.item(item, "values")
        if not values:
            return

        isbn = values[0]
        title = values[1] if len(values) > 1 and values[1] else isbn

        if not isbn:
            messagebox.showerror(
                "Löschen nicht möglich",
                "Dieser Eintrag hat keine ISBN und kann deshalb nicht eindeutig gelöscht werden.",
                parent=self.root,
            )
            return

        confirmed = messagebox.askyesno(
            "Eintrag wirklich löschen?",
            f'Möchtest du "{title}" wirklich aus der Datenbank löschen?\n\n'
            "Dabei werden auch die zugehörigen Exemplare gelöscht.",
            icon="warning",
            parent=self.root,
        )
        if not confirmed:
            return

        try:
            delete_book(isbn)
        except Exception as error:
            messagebox.showerror(
                "Löschen fehlgeschlagen",
                f"Der Eintrag konnte nicht gelöscht werden.\n\n{error}",
                parent=self.root,
            )
            self.status_var.set("Fehler beim Löschen des Eintrags")
            return

        # Die aktuelle Suche erneut ausführen, damit Trefferzahl, Sortierung und
        # Tabelle sicher zum Datenbankstand passen.
        self.run_search()
        self.status_var.set(f'"{title}" wurde gelöscht')

    def reset_search(self):
        """Leert Filter, Tabelle und Sortierzustand."""

        # StringVars mit einem leeren Text leeren automatisch ihre Eingabefelder.
        self.title_var.set("")
        self.author_var.set("")
        self.category_var.set("Alle Kategorien")
        self.isbn_var.set("")

        # Alle aktuell dargestellten Ergebniszeilen löschen.
        self.results.delete(*self.results.get_children())

        # Sortierung vollständig zurücksetzen.
        self.sort_column = None
        self.sort_descending = False

        # Die Pfeile aus den Tabellenüberschriften entfernen.
        for column, heading in self.column_headings.items():
            self.results.heading(column, text=heading)

        self.status_var.set("Suchfilter zurückgesetzt")
        self.title_entry.focus_set()


    def open_add_book_dialog(self):
        """Öffnet das Formular zum Eintragen eines neuen Buches."""

        dialog = tk.Toplevel(self.root)
        dialog.title("Buch hinzufügen")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        isbn_var = tk.StringVar()
        copies_var = tk.StringVar(value="1")
        dialog_status = tk.StringVar(
            value="Titel, Autor, Verlag und Seitenzahl werden automatisch geladen."
        )

        # Verwendet einen abgerundeten Rahmen für das Formular, damit der Dialog
        # den restlichen Karten der Anwendung entspricht. Der äußere Rahmen
        # erhält dieselbe Oberfläche und Randfarbe wie andere Karten. Über den
        # "inner_frame" werden die Inhalte eingefügt.
        card = RoundedFrame(
            dialog,
            radius=24,
            bg=COLORS["surface"],
            bordercolor=COLORS["border"],
            padding=(24, 24),
        )
        card.pack(fill="both", expand=True)
        card.inner_frame.columnconfigure(0, weight=1)

        ttk.Label(card.inner_frame, text="Neues Buch", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 18)
        )
        ttk.Label(card.inner_frame, text="ISBN", style="Field.TLabel").grid(
            row=1, column=0, sticky="w"
        )
        isbn_entry = ttk.Entry(card.inner_frame, textvariable=isbn_var, width=42)
        isbn_entry.grid(row=2, column=0, sticky="ew", pady=(6, 14))

        ttk.Label(card.inner_frame, text="ANZAHL EXEMPLARE", style="Field.TLabel").grid(
            row=3, column=0, sticky="w"
        )
        copies = ttk.Spinbox(
            card.inner_frame, from_=1, to=999, textvariable=copies_var, width=10
        )
        copies.grid(row=4, column=0, sticky="w", pady=(6, 14))

        ttk.Label(
            card.inner_frame,
            textvariable=dialog_status,
            style="Field.TLabel",
            wraplength=360,
        ).grid(row=5, column=0, sticky="w")

        actions = ttk.Frame(card.inner_frame, style="Card.TFrame")
        actions.grid(row=6, column=0, sticky="e", pady=(22, 0))
        # Abgerundete Buttons im Dialog: Abbrechen (sekundär) und Hinzufügen (primär)
        cancel_btn = RoundedButton(
            actions,
            text="Abbrechen",
            command=dialog.destroy,
            bg=DESIGN_SYSTEM["secondary"],
            fg=COLORS["text"],
            active_bg=_lighten(DESIGN_SYSTEM["secondary"], 0.1),
            radius=12,
            padding=(16, 8),
        )
        cancel_btn.pack(side="left", padx=(0, 10))
        add_btn = RoundedButton(
            actions,
            text="Buch hinzufügen",
            bg=DESIGN_SYSTEM["primary"],
            fg=COLORS["surface"],
            active_bg=_darken(DESIGN_SYSTEM["primary"], 0.2),
            radius=12,
            padding=(16, 8),
        )
        add_btn.pack(side="left")
        submitting = False

        def finish_success(metadata):
            if not dialog.winfo_exists():
                return
            dialog.destroy()
            self.isbn_var.set(metadata["isbn"])
            self.run_search()
            self.status_var.set(f'"{metadata["title"]}" wurde hinzugefügt')
            messagebox.showinfo(
                "Buch hinzugefügt",
                f'"{metadata["title"]}" wurde erfolgreich gespeichert.',
                parent=self.root,
            )

        def finish_error(error):
            nonlocal submitting
            if not dialog.winfo_exists():
                return
            submitting = False
            add_btn.configure(state="normal")
            cancel_btn.configure(state="normal")
            dialog_status.set("Das Buch konnte nicht hinzugefügt werden.")
            messagebox.showerror(
                "Hinzufügen fehlgeschlagen", str(error), parent=dialog
            )

        def submit():
            nonlocal submitting
            if submitting:
                return
            submitting = True
            isbn = isbn_var.get().strip()
            copy_count = copies_var.get().strip()
            add_btn.configure(state="disabled")
            cancel_btn.configure(state="disabled")
            dialog_status.set("Buchdaten werden geladen und gespeichert ...")
            result_queue = Queue()

            def worker():
                try:
                    metadata = add_book(isbn, copy_count)
                except Exception as error:
                    result_queue.put(("error", error))
                else:
                    result_queue.put(("success", metadata))

            Thread(target=worker, daemon=True).start()

            def poll_result():
                try:
                    result_type, value = result_queue.get_nowait()
                except Empty:
                    if dialog.winfo_exists():
                        self.root.after(50, poll_result)
                    return

                if result_type == "success":
                    finish_success(value)
                else:
                    finish_error(value)

            self.root.after(50, poll_result)

        add_btn.configure(command=submit)
        dialog.bind("<Return>", lambda _event: submit())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        isbn_entry.focus_set()


def main():
    """Startet das Hauptfenster und die Tkinter-Ereignisschleife."""

    # Jede Tkinter-Anwendung braucht genau ein Hauptfenster.
    root = tk.Tk()

    # Die Klasse baut alle Inhalte in dieses Fenster ein.
    LibraryApp(root)

    # ``mainloop`` wartet auf Ereignisse wie Klicks, Tastatureingaben oder
    # Fensteränderungen. Ohne diese Schleife würde das Programm sofort enden.
    root.mainloop()


# Dieser Schutz sorgt dafür, dass ``main`` nur beim direkten Start von gui.py
# ausgeführt wird. Beim Import in einem Test wird nicht automatisch ein Fenster
# geöffnet. ``__name__`` ist beim direkten Start genau "__main__".
if __name__ == "__main__":
    main()
