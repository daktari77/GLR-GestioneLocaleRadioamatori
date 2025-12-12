# -*- coding: utf-8 -*-
"""
UI Styling and theming for Libro Soci v4.2a
Manages colors, fonts, and widget styling
"""

from tkinter import font as tkfont

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
