# -*- coding: utf-8 -*-
"""
v4_ui package - UI components for Libro Soci v4.2a
"""

from .main_window import App
from .forms import MemberForm, QuotePanel, CDRuoloPanel
from .panels import DocumentPanel, SectionDocumentPanel, SectionInfoPanel, EventLogPanel
from .magazzino_panel import MagazzinoPanel
from .styles import Theme, DarkTheme, configure_styles, get_theme, get_fonts

__version__ = "4.1.0"

__all__ = [
    "App",
    "MemberForm",
    "QuotePanel",
    "CDRuoloPanel",
    "DocumentPanel",
    "SectionDocumentPanel",
    "SectionInfoPanel",
    "EventLogPanel",
    "MagazzinoPanel",
    "Theme",
    "DarkTheme",
    "configure_styles",
    "get_theme",
    "get_fonts",
]
