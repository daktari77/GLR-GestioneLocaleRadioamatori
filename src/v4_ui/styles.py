# -*- coding: utf-8 -*-
"""
UI Styling and theming for GLR - Gestione Locale Radioamatori
Manages colors, fonts, and widget styling
"""

from tkinter import font as tkfont
import tkinter as tk


def configure_global_fonts(root, *, family: str = "Segoe UI", size: int = 9) -> None:
    """Configure Tk named fonts so the whole UI uses a consistent base font.

    This affects both Tk widgets and ttk widgets that inherit from Tk named fonts.
    """

    if root is None:
        return

    # Tk uses named fonts; not all of them exist on every platform.
    candidates = (
        "TkDefaultFont",
        "TkTextFont",
        "TkMenuFont",
        "TkHeadingFont",
        "TkCaptionFont",
        "TkSmallCaptionFont",
        "TkIconFont",
        "TkTooltipFont",
    )

    for name in candidates:
        try:
            f = tkfont.nametofont(name)
        except Exception:
            continue
        try:
            f.configure(family=family, size=size)
        except Exception:
            continue


def ensure_app_named_fonts(root) -> None:
    """Create/update app-level named fonts derived from TkDefaultFont."""

    if root is None:
        return

    try:
        base = tkfont.nametofont("TkDefaultFont")
    except Exception:
        return

    base_actual = base.actual()

    def _upsert(
        name: str,
        *,
        weight: str = "normal",
        slant: str | None = None,
        size: int | None = None,
        family: str | None = None,
    ):
        try:
            f = tkfont.nametofont(name)
        except tk.TclError:
            f = tkfont.Font(master=root, name=name, exists=False)
        cfg = dict(base_actual)
        cfg["weight"] = weight
        if slant is not None:
            cfg["slant"] = slant
        if size is not None:
            cfg["size"] = size
        if family is not None:
            cfg["family"] = family
        try:
            f.configure(**cfg)
        except Exception:
            pass

    base_size = int(base_actual.get("size") or 9)

    _upsert("AppSmall", weight="normal", size=max(8, base_size - 1))
    _upsert("AppNormal", weight="normal", size=base_size)
    _upsert("AppBold", weight="bold", size=base_size)
    _upsert("AppItalic", weight="normal", slant="italic", size=base_size)
    _upsert("AppTitle", weight="bold", size=base_size + 3)
    _upsert("AppHeading", weight="bold", size=base_size + 5)
    _upsert("AppMono", weight="normal", family="Courier New", size=base_size + 1)

class Theme:
    """Base theme class"""
    
    # Colors
    BG_PRIMARY = "#ffffff"
    BG_SECONDARY = "#f5f5f5"
    BG_ACCENT = "#e8f4f8"
    
    FG_PRIMARY = "#000000"
    FG_SECONDARY = "#666666"
    FG_ACCENT = "#0066cc"
    
    BORDER_COLOR = "#cccccc"
    SUCCESS_COLOR = "#28a745"
    WARNING_COLOR = "#ffc107"
    ERROR_COLOR = "#dc3545"
    
    # Fonts
    FONT_SMALL = ("Segoe UI", 9)
    FONT_NORMAL = ("Segoe UI", 10)
    FONT_LARGE = ("Segoe UI", 11)
    FONT_TITLE = ("Segoe UI", 12, "bold")
    FONT_HEADING = ("Segoe UI", 14, "bold")
    
    # Padding and spacing
    PADX = 5
    PADY = 5
    
    @staticmethod
    def create_fonts():
        """Create font objects"""
        return {
            "small": tkfont.Font(family="Segoe UI", size=9),
            "normal": tkfont.Font(family="Segoe UI", size=10),
            "large": tkfont.Font(family="Segoe UI", size=11),
            "title": tkfont.Font(family="Segoe UI", size=12, weight="bold"),
            "heading": tkfont.Font(family="Segoe UI", size=14, weight="bold"),
            "mono": tkfont.Font(family="Courier New", size=10),
        }


class DarkTheme(Theme):
    """Dark theme variant"""
    
    BG_PRIMARY = "#1e1e1e"
    BG_SECONDARY = "#2d2d2d"
    BG_ACCENT = "#3d4d5f"
    
    FG_PRIMARY = "#ffffff"
    FG_SECONDARY = "#aaaaaa"
    FG_ACCENT = "#66ccff"
    
    BORDER_COLOR = "#444444"


def configure_styles(root):
    """Configure ttk styles for the application"""
    from tkinter import ttk
    
    style = ttk.Style()
    style.theme_use("clam")
    
    # Define custom colors
    style.configure("TFrame", background=Theme.BG_PRIMARY, foreground=Theme.FG_PRIMARY)
    style.configure("TLabel", background=Theme.BG_PRIMARY, foreground=Theme.FG_PRIMARY)
    style.configure("TButton", background=Theme.BG_SECONDARY, foreground=Theme.FG_PRIMARY)
    style.configure("TEntry", fieldbackground=Theme.BG_PRIMARY, foreground=Theme.FG_PRIMARY)
    style.configure("TCombobox", fieldbackground=Theme.BG_PRIMARY, foreground=Theme.FG_PRIMARY)
    
    # Status bar styling
    style.configure("Status.TLabel", background=Theme.BG_SECONDARY, foreground=Theme.FG_SECONDARY, font=Theme.FONT_SMALL)
    
    # Title styling
    style.configure("Title.TLabel", background=Theme.BG_PRIMARY, foreground=Theme.FG_ACCENT, font=Theme.FONT_HEADING)
    
    # Section styling
    style.configure("Section.TLabel", background=Theme.BG_PRIMARY, foreground=Theme.FG_ACCENT, font=Theme.FONT_TITLE)
    
    # Button variants
    style.configure("Success.TButton")
    style.configure("Warning.TButton")
    style.configure("Error.TButton")
    
    # Notebook styling
    style.configure("TNotebook", background=Theme.BG_PRIMARY, foreground=Theme.FG_PRIMARY)
    style.configure("TNotebook.Tab", padding=[20, 10])
    
    # Treeview styling
    style.configure("Treeview", background=Theme.BG_PRIMARY, foreground=Theme.FG_PRIMARY, fieldbackground=Theme.BG_PRIMARY)
    style.configure("Treeview.Heading", background=Theme.BG_SECONDARY, foreground=Theme.FG_PRIMARY, font=Theme.FONT_NORMAL)
    style.map("Treeview", background=[("selected", Theme.BG_ACCENT)])


def get_theme() -> Theme:
    """Get current theme instance"""
    return Theme()


def get_fonts() -> dict:
    """Get font dictionary"""
    return Theme.create_fonts()
