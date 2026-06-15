"""Grafische Benutzeroberfläche für den Bibliothekskatalog.

Dieses Modul enthält ausschließlich die Oberfläche und deren Bedienlogik:

1. Tkinter zeichnet Fenster, Eingabefelder, Buttons und Tabellen.
2. Geteilte Fachwerte beschreiben Katalogseiten und Buchansichten.
3. ``Bibliothekszugang`` liefert sie unabhängig vom Transport-Adapter.

Dadurch besitzt die GUI weder Server-, SQL- noch Transportwissen. Sie bleibt
für Widgets, Farben und Dialoge zuständig.
"""

import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Literal, TypedDict

from src.shared.catalog import (
    Bibliothekszugang,
    Buchansicht,
    Katalogseite,
    Katalogsuche,
    Katalogzeile,
    Sortierfeld,
    Sortierung,
)
from src.shared.domain_values import (
    Kategorie,
    Verfuegbarkeitsklasse,
)
from src.shared.models import BookMetadata

type RGB = tuple[int, int, int]
type ActionButtonVariant = Literal["primary", "secondary"]

APP_DIRECTORY = Path(__file__).resolve().parent
LOGO_PATH = APP_DIRECTORY / "assets" / "Logo Bibliothek.png"
WINDOWS_APP_ID = "FSG.Bibliothekskatalog"
HEADER_LOGO_MAX_WIDTH = 64
HEADER_LOGO_MAX_HEIGHT = 72
WINDOW_ICON_SIZES = (256, 64, 32, 16)


# Diese Auswahl bedeutet bewusst keinen Kategorie-Filter. Alle konkreten
# Kategorien und ihre Übersetzung besitzt das Katalogansicht-Interface.
ALL_CATEGORIES_LABEL = "Alle Kategorien"

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


def _hex_to_rgb(hex_color: str) -> RGB:
    """Wandelt einen Hex‑Farbcode in ein RGB‑Tupel um.

    Tkinter erwartet Farben als Hex‑Strings, für Berechnungen werden sie jedoch
    zunächst in ihre drei Komponenten aufgeteilt.
    """
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _rgb_to_hex(rgb: RGB) -> str:
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


def _subsample_to_fit(
    image: tk.PhotoImage,
    *,
    max_width: int,
    max_height: int,
) -> tk.PhotoImage:
    """Verkleinert ein Tk-Bild proportional auf die angegebenen Grenzen."""

    width_factor = (image.width() + max_width - 1) // max_width
    height_factor = (image.height() + max_height - 1) // max_height
    factor = max(1, width_factor, height_factor)
    return image.subsample(factor)


def _center_square_image(
    master: tk.Misc,
    source: tk.PhotoImage,
) -> tk.PhotoImage:
    """Schneidet mittig eine quadratische Icon-Version des Logos aus."""

    size = min(source.width(), source.height())
    left = (source.width() - size) // 2
    top = (source.height() - size) // 2
    square = tk.PhotoImage(master=master, width=size, height=size)
    square.tk.call(
        str(square),
        "copy",
        str(source),
        "-from",
        left,
        top,
        left + size,
        top + size,
        "-to",
        0,
        0,
    )
    return square


def _set_windows_app_id() -> None:
    """Sorgt unter Windows für ein eigenes Taskleisten-Symbol der Anwendung."""

    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except AttributeError, OSError:
        # Ältere oder eingeschränkte Windows-Umgebungen unterstützen die API
        # gegebenenfalls nicht; Tkinter kann dann weiterhin normal starten.
        return


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

ACTION_BUTTON_WIDTH = 144
ACTION_BUTTON_HEIGHT = 39
ACTION_BUTTON_RADIUS = 12


class ButtonPalette(TypedDict):
    background: str
    foreground: str
    hover: str
    pressed: str
    disabled_background: str
    disabled_foreground: str
    focus: str


BUTTON_PALETTES: dict[ActionButtonVariant, ButtonPalette] = {
    "primary": {
        "background": DESIGN_SYSTEM["primary"],
        "foreground": COLORS["surface"],
        "hover": _darken(DESIGN_SYSTEM["primary"], 0.08),
        "pressed": _darken(DESIGN_SYSTEM["primary"], 0.2),
        "disabled_background": _lighten(DESIGN_SYSTEM["primary"], 0.4),
        "disabled_foreground": _lighten(COLORS["surface"], 0.2),
        "focus": _darken(DESIGN_SYSTEM["primary"], 0.32),
    },
    "secondary": {
        "background": DESIGN_SYSTEM["secondary"],
        "foreground": COLORS["text"],
        "hover": _lighten(DESIGN_SYSTEM["secondary"], 0.1),
        "pressed": _darken(DESIGN_SYSTEM["secondary"], 0.08),
        "disabled_background": _lighten(DESIGN_SYSTEM["secondary"], 0.45),
        "disabled_foreground": COLORS["muted"],
        "focus": _darken(DESIGN_SYSTEM["secondary"], 0.32),
    },
}


def _widget_background(widget: tk.Misc) -> str:
    """Ermittelt die sichtbare Hintergrundfarbe eines Tk- oder ttk-Widgets."""

    if isinstance(widget, ttk.Widget):
        style_name = widget.cget("style") or widget.winfo_class()
        background = ttk.Style(widget).lookup(style_name, "background")
        if background:
            return str(background)

    if isinstance(widget, tk.Widget):
        try:
            return str(widget.cget("background"))
        except tk.TclError:
            pass

    return COLORS["background"]


class ActionButton(tk.Canvas):
    """Ein einheitlicher, abgerundeter Aktionsbutton für die ttk-Oberfläche.

    ttk besitzt unter Windows keine verlässliche, theme-unabhängige Option für
    runde Button-Ecken. Deshalb zeichnet diese wiederverwendbare Komponente nur
    die Button-Fläche auf einem Canvas; Layout, Typografie und Farbvarianten
    bleiben zentral definiert und passen zu den übrigen ttk-Widgets.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        text: str,
        command: Callable[[], None] | None = None,
        variant: ActionButtonVariant = "primary",
    ) -> None:
        super().__init__(
            master,
            width=ACTION_BUTTON_WIDTH,
            height=ACTION_BUTTON_HEIGHT,
            background=_widget_background(master),
            borderwidth=0,
            cursor="hand2",
            highlightthickness=0,
            takefocus=True,
        )
        self.text = text
        self.command = command
        self.palette = BUTTON_PALETTES[variant]
        self.enabled = True
        self.focused = False
        self.font = tkfont.Font(
            root=self,
            family="Segoe UI",
            size=10,
            weight="bold",
        )
        self._draw()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Return>", self._on_key_press)
        self.bind("<space>", self._on_key_press)

    def _draw(self) -> None:
        """Zeichnet Hintergrund und Beschriftung in der Standardgröße."""

        points = _rounded_polygon_points(
            ACTION_BUTTON_WIDTH - 1,
            ACTION_BUTTON_HEIGHT - 1,
            ACTION_BUTTON_RADIUS,
        )
        self._rect_id = self.create_polygon(
            points,
            fill=self.palette["background"],
            outline=self.palette["background"],
            width=1,
            smooth=True,
            splinesteps=36,
        )
        self._text_id = self.create_text(
            ACTION_BUTTON_WIDTH / 2,
            ACTION_BUTTON_HEIGHT / 2,
            text=self.text,
            fill=self.palette["foreground"],
            font=self.font,
            anchor="center",
        )

    def _on_enter(self, _event: tk.Event) -> None:
        if self.enabled:
            self._render(self.palette["hover"])

    def _on_leave(self, _event: tk.Event) -> None:
        if self.enabled:
            self._render(self.palette["background"])

    def _on_press(self, _event: tk.Event) -> None:
        if self.enabled and self.command:
            self.focus_set()
            self._invoke()

    def _on_key_press(self, _event: tk.Event) -> str:
        if self.enabled and self.command:
            self._invoke()
        return "break"

    def _on_focus_in(self, _event: tk.Event) -> None:
        self.focused = True
        self._render(self.palette["background"])

    def _on_focus_out(self, _event: tk.Event) -> None:
        self.focused = False
        self._render(self.palette["background"])

    def _invoke(self) -> None:
        self._render(self.palette["pressed"])
        self.after(100, self._restore_background)
        if self.command:
            self.command()

    def _restore_background(self) -> None:
        if self.winfo_exists() and self.enabled:
            self._render(self.palette["background"])

    def _render(self, background: str) -> None:
        outline = self.palette["focus"] if self.focused else background
        self.itemconfig(
            self._rect_id,
            fill=background,
            outline=outline,
            width=2 if self.focused else 1,
        )

    def set_enabled(self, enabled: bool) -> None:
        """Aktiviert oder deaktiviert den Button."""

        self.enabled = enabled
        background = (
            self.palette["background"]
            if enabled
            else self.palette["disabled_background"]
        )
        foreground = (
            self.palette["foreground"]
            if enabled
            else self.palette["disabled_foreground"]
        )
        self.configure(cursor="hand2" if enabled else "arrow")
        self._render(background)
        self.itemconfig(self._text_id, fill=foreground)

    def set_command(self, command: Callable[[], None]) -> None:
        """Setzt die Aktion, die beim Klick ausgeführt wird."""

        self.command = command


# Eine kleine Hilfsfunktion erzeugt eine abgerundete Polygonform für den Canvas.
def _rounded_polygon_points(width: int, height: int, r: int) -> list[int]:
    """Berechnet Eckpunkte für ein Rechteck mit abgerundeten Ecken.

    Die Liste enthält 20 Koordinatenpaare (insgesamt 40 Werte). Mehrfach
    vorkommende Punkte sorgen dafür, dass Tkinter die Kurven sauber glättet.
    """
    return [
        r,
        0,
        r,
        0,
        width - r,
        0,
        width - r,
        0,
        width,
        0,
        width,
        r,
        width,
        r,
        width,
        height - r,
        width,
        height - r,
        width,
        height,
        width - r,
        height,
        width - r,
        height,
        r,
        height,
        r,
        height,
        0,
        height,
        0,
        height - r,
        0,
        height - r,
        0,
        r,
        0,
        r,
        0,
        0,
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
        bg: str | None = None,
        bordercolor: str | None = None,
        padding: tuple[int, int] = (0, 0),
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
        self._rect_id: int | None = None
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
        self.canvas.itemconfig(
            self._inner_window_id, width=inner_width, height=inner_height
        )
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


# Jedes Tag bekommt in der Exemplartabelle eine eigene Farbe. Die Tag-Namen
# bleiben technisch/englisch, weil sie nicht sichtbar sind.
AVAILABILITY_ROW_STYLES = {
    Verfuegbarkeitsklasse.VERFUEGBAR: ("#DCFCE7", "#14532D"),
    Verfuegbarkeitsklasse.AUSGELIEHEN: ("#FEE2E2", "#991B1B"),
    Verfuegbarkeitsklasse.RESERVIERT: ("#FEF3C7", "#92400E"),
    Verfuegbarkeitsklasse.PROBLEM: ("#FFEDD5", "#9A3412"),
    Verfuegbarkeitsklasse.UNBEKANNT: (COLORS["surface"], COLORS["text"]),
}


class LibraryApp:
    """Baut die Anwendung auf und verarbeitet alle Benutzeraktionen.

    Eine Klasse ist hier sinnvoll, weil viele Widgets und Zustände
    zusammengehören. Über ``self`` können Methoden wie ``run_search`` später
    auf Eingabefelder, Tabelle und Statuszeile zugreifen.
    """

    def __init__(self, root: tk.Tk, bibliothek: Bibliothekszugang):
        """Initialisiert Fensterzustand, Design und Oberfläche.

        ``__init__`` wird automatisch ausgeführt, sobald unten ein
        ``LibraryApp``-Objekt mit Fenster und Bibliothekszugang erzeugt wird.
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
        self._load_branding()

        # Der Transport-Adapter erfüllt das geteilte Bibliothekszugang-Interface.
        # Servermodule und Transportdetails bleiben außerhalb der GUI.
        self.bibliothek = bibliothek

        # StringVar verbindet einen Python-Textwert mit einem Tkinter-Widget.
        # Wenn ein Benutzer tippt, liefert ``variable.get()`` den aktuellen
        # Inhalt. Mit ``variable.set(...)`` kann der Inhalt geändert werden.
        self.title_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.category_var = tk.StringVar(value=ALL_CATEGORIES_LABEL)
        self.isbn_var = tk.StringVar()

        # Die Statusvariable wird mit dem Text unterhalb der Tabelle verbunden.
        # Such- und Sortiermethoden können dort Rückmeldungen anzeigen.
        self.status_var = tk.StringVar(value="Bereit für die Suche")

        # Hier merken wir uns den aktuellen Sortierzustand:
        # ``None`` bedeutet, dass noch keine Spalte gewählt wurde.
        # ``False`` steht für aufsteigend, ``True`` für absteigend.
        self.sort_column: str | None = None
        self.sort_descending = False

        # Die sichtbaren Zellen sind keine Fachwerte. Diese Abbildung bewahrt
        # die zuletzt geladenen, typisierten Zeilen für Bestätigungsdialoge.
        self.catalog_rows_by_isbn: dict[str, Katalogzeile] = {}

        # Geöffnete Exemplarseiten werden hier nach ISBN gemerkt. So wird ein
        # bereits offenes Detailfenster nur nach vorne geholt statt dupliziert.
        self.copy_detail_windows: dict[str, tk.Toplevel] = {}

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

    def _load_branding(self) -> None:
        """Lädt Logo sowie passende Varianten für Kopfzeile und Fenster."""

        self.logo_source_image = tk.PhotoImage(
            master=self.root,
            file=str(LOGO_PATH),
        )
        self.header_logo_image = _subsample_to_fit(
            self.logo_source_image,
            max_width=HEADER_LOGO_MAX_WIDTH,
            max_height=HEADER_LOGO_MAX_HEIGHT,
        )

        square_logo = _center_square_image(self.root, self.logo_source_image)
        self.window_icon_images = tuple(
            _subsample_to_fit(
                square_logo,
                max_width=size,
                max_height=size,
            )
            for size in WINDOW_ICON_SIZES
        )
        self.root.iconphoto(True, *self.window_icon_images)

    def _apply_window_icon(self, window: tk.Toplevel) -> None:
        """Wendet das Anwendungslogo explizit auf ein Unterfenster an."""

        window.iconphoto(False, *self.window_icon_images)

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
        style.configure("HeaderLogo.TLabel", background=COLORS["background"])

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
        header.columnconfigure(1, weight=1)
        ttk.Label(
            header,
            image=self.header_logo_image,
            style="HeaderLogo.TLabel",
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 16))
        ttk.Label(header, text="Bibliothekskatalog", style="Title.TLabel").grid(
            row=0, column=1, sticky="sw"
        )
        ttk.Label(
            header,
            text="Durchsuche den Bestand nach Titel, Autor, Kategorie oder ISBN.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=1, sticky="nw", pady=(4, 0))
        ActionButton(
            header,
            text="Buch hinzufügen",
            command=self.open_add_book_dialog,
            variant="primary",
        ).grid(row=0, column=2, rowspan=2, sticky="ne")

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
            values=[ALL_CATEGORIES_LABEL, *(category.label for category in Kategorie)],
            state="readonly",
        )

        # ``sticky="ew"`` zieht das Widget an den linken und rechten Rand
        # seiner Grid-Zelle, es füllt die verfügbare Breite also aus.
        category.grid(row=2, column=2, sticky="ew", padx=(0, 12), pady=(6, 0))

        self._add_field(
            search_card.inner_frame, "ISBN", self.isbn_var, 1, 3, right_padding=0
        )

        # Ein eigener Frame hält beide Buttons als zusammengehörige Gruppe.
        # ``sticky="e"`` richtet diese Gruppe am rechten Rand aus. Wir
        # platzieren ihn ebenfalls im inneren Bereich des abgerundeten
        # Rahmens. Alle Aktionen verwenden dieselbe wiederverwendbare
        # ``ActionButton``-Komponente und unterscheiden sich nur in ihrer
        # primären oder sekundären Farbvariante.
        actions = ttk.Frame(search_card.inner_frame, style="Card.TFrame")
        actions.grid(row=3, column=0, columnspan=4, sticky="e", pady=(18, 0))
        reset_btn = ActionButton(
            actions,
            text="Zurücksetzen",
            command=self.reset_search,
            variant="secondary",
        )
        reset_btn.pack(side="left", padx=(0, 10))
        search_btn = ActionButton(
            actions,
            text="Bestand durchsuchen",
            command=self.run_search,
            variant="primary",
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

        page = self._load_catalog()
        if page is not None:
            self.status_var.set(page.status)

    def sort_results(self, column):
        """Ändert die typisierte Sortierung und lädt die Katalogseite neu."""

        if self.sort_column == column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            self.sort_descending = False
        page = self._load_catalog()
        if page is None:
            return

        self._update_sort_headings()
        direction = "absteigend" if self.sort_descending else "aufsteigend"
        self.status_var.set(
            f"Sortiert nach {self.column_headings[column]} ({direction})"
        )

    def _load_catalog(self) -> Katalogseite | None:
        """Lädt eine neue Seite über das Katalogansicht-Interface."""

        try:
            page = self.bibliothek.suchen(self._current_catalog_search())
        except Exception as error:
            # Eine Messagebox ist für Benutzer verständlicher als ein
            # Python-Traceback in einem möglicherweise unsichtbaren Terminal.
            messagebox.showerror(
                "Suche fehlgeschlagen",
                f"Die Bibliotheksdaten konnten nicht geladen werden.\n\n{error}",
            )
            self.status_var.set("Fehler beim Laden der Suchergebnisse")
            return None

        self._render_catalog(page)
        return page

    def _current_catalog_search(self) -> Katalogsuche:
        """Baut aus Widgets eine typisierte, Tkinter-unabhängige Suche."""

        category_label = self.category_var.get()
        category = (
            None
            if category_label == ALL_CATEGORIES_LABEL
            else Kategorie.from_label(category_label)
        )
        ordering = (
            Sortierung(
                feld=Sortierfeld(self.sort_column),
                absteigend=self.sort_descending,
            )
            if self.sort_column
            else None
        )
        return Katalogsuche(
            titel=self.title_var.get(),
            autor=self.author_var.get(),
            kategorie=category,
            isbn=self.isbn_var.get(),
            sortierung=ordering,
        )

    def _render_catalog(self, page: Katalogseite) -> None:
        """Zeichnet eine Katalogseite, ohne Werte später zurückzuparsen."""

        # Die sichtbaren Zeilen und die typisierten Zeilen werden gemeinsam
        # ersetzt. Die ISBN dient zugleich als stabile Treeview-Identität.
        self.results.delete(*self.results.get_children())
        self.catalog_rows_by_isbn = {row.isbn: row for row in page.zeilen}

        for book in page.zeilen:
            self.results.insert(
                "",
                "end",
                iid=book.isbn,
                values=(
                    book.isbn,
                    book.titel,
                    book.autoren,
                    book.kategorie,
                    book.sprache,
                    book.erscheinung,
                    book.exemplarzahl,
                ),
            )

    def _update_sort_headings(self) -> None:
        """Zeigt ausschließlich am aktiven Sortierfeld einen Richtungspfeil."""

        for column, heading in self.column_headings.items():
            indicator = ""
            if column == self.sort_column:
                indicator = " ▼" if self.sort_descending else " ▲"
            self.results.heading(column, text=f"{heading}{indicator}")

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

        # Die Treeview-ID ist die ISBN. Sichtbare Zellen werden weder gelesen
        # noch als Quelle für Buchidentität oder Metadaten verwendet.
        isbn = item

        existing_window = self.copy_detail_windows.get(isbn)
        if existing_window and existing_window.winfo_exists():
            existing_window.lift()
            existing_window.focus_force()
            return

        try:
            book = self.bibliothek.buch(isbn)
        except Exception as error:
            messagebox.showerror(
                "Exemplare konnten nicht geladen werden",
                f"Die Exemplare dieses Buches konnten nicht geladen werden.\n\n{error}",
                parent=self.root,
            )
            self.status_var.set("Fehler beim Laden der Exemplare")
            return

        detail = tk.Toplevel(self.root)
        self._apply_window_icon(detail)
        detail.title(f"Exemplare: {book.titel}")
        detail.geometry("760x460")
        detail.minsize(620, 360)
        detail.configure(background=COLORS["background"])
        detail.transient(self.root)
        self.copy_detail_windows[isbn] = detail

        def close_detail():
            self.copy_detail_windows.pop(isbn, None)
            detail.destroy()

        detail.protocol("WM_DELETE_WINDOW", close_detail)

        container = ttk.Frame(detail, style="App.TFrame", padding=(28, 24, 28, 20))
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        ttk.Label(
            container,
            text=book.titel,
            style="Title.TLabel",
            wraplength=680,
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            container,
            text=book.metadatenzeile,
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

        ttk.Label(
            copies_card.inner_frame, text="Exemplare", style="Section.TLabel"
        ).grid(row=0, column=0, sticky="w")
        summary_var = tk.StringVar(value=book.exemplarzusammenfassung)
        ttk.Label(
            copies_card.inner_frame,
            textvariable=summary_var,
            style="Field.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        columns = ("copy_id", "state", "availability")
        copy_table = ttk.Treeview(
            copies_card.inner_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        copy_table.heading("copy_id", text="Exemplar-ID")
        copy_table.heading("state", text="Zustand")
        copy_table.heading("availability", text="Verfügbarkeit")
        copy_table.column("copy_id", width=180, minwidth=120, anchor="w")
        copy_table.column("state", width=160, minwidth=100, anchor="w")
        copy_table.column("availability", width=180, minwidth=120, anchor="w")

        for availability_class, (
            background,
            foreground,
        ) in AVAILABILITY_ROW_STYLES.items():
            copy_table.tag_configure(
                availability_class.value,
                background=background,
                foreground=foreground,
            )

        def render_copies(updated_book: Buchansicht) -> None:
            """Aktualisiert Zusammenfassung und Tabelle nach einer Änderung."""

            summary_var.set(updated_book.exemplarzusammenfassung)
            copy_table.delete(*copy_table.get_children())
            if updated_book.exemplare:
                # Texte und semantische Verfügbarkeitsklasse kommen fertig aus
                # der Katalogansicht; Tkinter ergänzt nur die konkrete Farbe.
                for copy in updated_book.exemplare:
                    copy_table.insert(
                        "",
                        "end",
                        values=(
                            copy.exemplar_id,
                            copy.zustand,
                            copy.verfuegbarkeit,
                        ),
                        tags=(copy.klasse.value,),
                    )
                return

            copy_table.insert(
                "",
                "end",
                values=("", "Keine Exemplare gespeichert", ""),
                tags=(Verfuegbarkeitsklasse.UNBEKANNT.value,),
            )

        add_copy_btn = ActionButton(
            copies_card.inner_frame,
            text="Exemplar hinzufügen",
            command=lambda: self.open_add_copies_dialog(
                parent=detail,
                isbn=book.isbn,
                title=book.titel,
                on_success=render_copies,
            ),
        )
        add_copy_btn.grid(row=0, column=1, sticky="e")

        scrollbar = ttk.Scrollbar(
            copies_card.inner_frame, orient="vertical", command=copy_table.yview
        )
        copy_table.configure(yscrollcommand=scrollbar.set)
        copy_table.grid(row=2, column=0, sticky="nsew")
        scrollbar.grid(row=2, column=1, sticky="ns")
        render_copies(book)

        self.status_var.set(f'Exemplare von "{book.titel}" geöffnet')

    def open_add_copies_dialog(
        self,
        *,
        parent: tk.Toplevel,
        isbn: str,
        title: str,
        on_success: Callable[[Buchansicht], None],
    ) -> None:
        """Öffnet ein Formular für neue Exemplare eines vorhandenen Buches."""

        dialog = tk.Toplevel(parent)
        self._apply_window_icon(dialog)
        dialog.title("Exemplare hinzufügen")
        dialog.resizable(False, False)
        dialog.transient(parent)
        dialog.grab_set()

        copies_var = tk.StringVar(value="1")
        dialog_status = tk.StringVar(value=f'Neue Exemplare für "{title}" anlegen.')

        card = RoundedFrame(
            dialog,
            radius=24,
            bg=COLORS["surface"],
            bordercolor=COLORS["border"],
            padding=(24, 24),
        )
        card.pack(fill="both", expand=True)
        card.inner_frame.columnconfigure(0, weight=1)

        ttk.Label(
            card.inner_frame,
            text="Neue Exemplare",
            style="Section.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 18))
        ttk.Label(
            card.inner_frame,
            text="ANZAHL EXEMPLARE",
            style="Field.TLabel",
        ).grid(row=1, column=0, sticky="w")
        copies = ttk.Spinbox(
            card.inner_frame,
            from_=1,
            to=999,
            textvariable=copies_var,
            width=10,
        )
        copies.grid(row=2, column=0, sticky="w", pady=(6, 14))

        ttk.Label(
            card.inner_frame,
            textvariable=dialog_status,
            style="Field.TLabel",
            wraplength=360,
        ).grid(row=3, column=0, sticky="w")

        actions = ttk.Frame(card.inner_frame, style="Card.TFrame")
        actions.grid(row=4, column=0, sticky="e", pady=(22, 0))
        cancel_btn = ActionButton(
            actions,
            text="Abbrechen",
            command=dialog.destroy,
            variant="secondary",
        )
        cancel_btn.pack(side="left", padx=(0, 10))
        add_btn = ActionButton(
            actions,
            text="Hinzufügen",
            variant="primary",
        )
        add_btn.pack(side="left")
        submitting = False

        def finish_success(updated_book: Buchansicht) -> None:
            if not dialog.winfo_exists():
                return
            dialog.destroy()
            on_success(updated_book)
            self.run_search()
            self.status_var.set(f'Neue Exemplare für "{title}" wurden hinzugefügt')
            messagebox.showinfo(
                "Exemplare hinzugefügt",
                "Die neuen Exemplare wurden erfolgreich gespeichert.",
                parent=parent,
            )

        def finish_error(error: Exception) -> None:
            nonlocal submitting
            if not dialog.winfo_exists():
                return
            submitting = False
            add_btn.set_enabled(True)
            cancel_btn.set_enabled(True)
            dialog_status.set("Die Exemplare konnten nicht hinzugefügt werden.")
            messagebox.showerror("Hinzufügen fehlgeschlagen", str(error), parent=dialog)

        def submit() -> None:
            nonlocal submitting
            if submitting:
                return
            submitting = True
            copy_count = copies_var.get().strip()
            add_btn.set_enabled(False)
            cancel_btn.set_enabled(False)
            dialog_status.set("Exemplare werden gespeichert ...")
            result_queue: Queue[Buchansicht | Exception] = Queue()

            def worker() -> None:
                try:
                    result_queue.put(
                        self.bibliothek.exemplare_hinzufuegen(isbn, copy_count)
                    )
                except Exception as error:
                    result_queue.put(error)

            Thread(target=worker, daemon=True).start()

            def poll_result() -> None:
                try:
                    result = result_queue.get_nowait()
                except Empty:
                    if dialog.winfo_exists():
                        self.root.after(50, poll_result)
                    return

                if isinstance(result, Exception):
                    finish_error(result)
                else:
                    finish_success(result)

            self.root.after(50, poll_result)

        add_btn.set_command(submit)
        dialog.bind("<Return>", lambda _event: submit())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        copies.focus_set()
        copies.selection_range(0, "end")

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

        isbn = selection[0]
        book = self.catalog_rows_by_isbn.get(isbn)
        if book is None:
            return

        title = book.titel or isbn

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
            self.bibliothek.buch_entfernen(isbn)
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
        self.category_var.set(ALL_CATEGORIES_LABEL)
        self.isbn_var.set("")

        # Sichtbare und typisierte Ergebniszeilen werden gemeinsam verworfen.
        self.results.delete(*self.results.get_children())
        self.catalog_rows_by_isbn.clear()

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
        self._apply_window_icon(dialog)
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
        cancel_btn = ActionButton(
            actions,
            text="Abbrechen",
            command=dialog.destroy,
            variant="secondary",
        )
        cancel_btn.pack(side="left", padx=(0, 10))
        add_btn = ActionButton(
            actions,
            text="Buch hinzufügen",
            variant="primary",
        )
        add_btn.pack(side="left")
        submitting = False

        def finish_success(metadata: BookMetadata) -> None:
            if not dialog.winfo_exists():
                return
            dialog.destroy()
            self.isbn_var.set(metadata.isbn)
            self.run_search()
            self.status_var.set(f'"{metadata.title}" wurde hinzugefügt')
            messagebox.showinfo(
                "Buch hinzugefügt",
                f'"{metadata.title}" wurde erfolgreich gespeichert.',
                parent=self.root,
            )

        def finish_error(error: Exception) -> None:
            nonlocal submitting
            if not dialog.winfo_exists():
                return
            submitting = False
            add_btn.set_enabled(True)
            cancel_btn.set_enabled(True)
            dialog_status.set("Das Buch konnte nicht hinzugefügt werden.")
            messagebox.showerror("Hinzufügen fehlgeschlagen", str(error), parent=dialog)

        def submit() -> None:
            nonlocal submitting
            if submitting:
                return
            submitting = True
            isbn = isbn_var.get().strip()
            copy_count = copies_var.get().strip()
            add_btn.set_enabled(False)
            cancel_btn.set_enabled(False)
            dialog_status.set("Buchdaten werden geladen und gespeichert ...")
            result_queue: Queue[BookMetadata | Exception] = Queue()

            def worker() -> None:
                try:
                    result_queue.put(self.bibliothek.buch_aufnehmen(isbn, copy_count))
                except Exception as error:
                    result_queue.put(error)

            Thread(target=worker, daemon=True).start()

            def poll_result() -> None:
                try:
                    result = result_queue.get_nowait()
                except Empty:
                    if dialog.winfo_exists():
                        self.root.after(50, poll_result)
                    return

                if isinstance(result, Exception):
                    finish_error(result)
                else:
                    finish_success(result)

            self.root.after(50, poll_result)

        add_btn.set_command(submit)
        dialog.bind("<Return>", lambda _event: submit())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        isbn_entry.focus_set()


def run(bibliothek: Bibliothekszugang) -> None:
    """Startet das Hauptfenster mit einem konfigurierten Bibliothekszugang."""

    _set_windows_app_id()

    # Jede Tkinter-Anwendung braucht genau ein Hauptfenster.
    root = tk.Tk(className="Bibliothekskatalog")

    # Die Klasse baut alle Inhalte in dieses Fenster ein.
    LibraryApp(root, bibliothek)

    # ``mainloop`` wartet auf Ereignisse wie Klicks, Tastatureingaben oder
    # Fensteränderungen. Ohne diese Schleife würde das Programm sofort enden.
    root.mainloop()
