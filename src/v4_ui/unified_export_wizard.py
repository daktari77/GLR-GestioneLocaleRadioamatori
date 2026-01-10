# -*- coding: utf-8 -*-
"""Unified launcher dialog for soci/magazzino export flows."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk


class UnifiedExportWizard:
    """Small helper that lets the operator choose which export to run."""

    def __init__(self, parent: tk.Misc):
        self.parent = parent
        self.choice_var = tk.StringVar(value="soci")

        self.win = tk.Toplevel(parent)
        self.win.title("Esporta dati")
        self.win.geometry("520x450")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()

        try:
            from .styles import ensure_app_named_fonts

            ensure_app_named_fonts(self.win.winfo_toplevel())
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.win, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Scegli il tipo di esportazione", font="AppTitle").pack(
            anchor="w"
        )
        ttk.Label(
            frame,
            text=(
                "Entrambe le modalità generano un file CSV. Per i soci potrai scegliere i campi "
                "da includere, mentre per il magazzino sono disponibili filtri basati sullo stato "
                "(disponibile/in prestito)."
            ),
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 14))

        options = ttk.LabelFrame(frame, text="Modalità")
        options.pack(fill=tk.X, pady=(0, 14))
        self._add_option(
            options,
            value="soci",
            title="Soci",
            details=[
                "Esporta l'elenco soci in CSV",
                "Selezione personalizzata dei campi",
                "Filtri per inattivi ed eliminati",
            ],
        )
        self._add_option(
            options,
            value="magazzino",
            title="Magazzino",
            details=[
                "Esporta inventario e prestiti attivi",
                "Filtro per disponibili o oggetti prestati",
                "Campi configurabili",
            ],
        )

        steps = ttk.LabelFrame(frame, text="Passi")
        steps.pack(fill=tk.X)
        ttk.Label(steps, text="1. Seleziona la modalità", anchor="w").pack(fill=tk.X, padx=8, pady=(6, 0))
        ttk.Label(steps, text="2. Configura i campi/filtro nella finestra dedicata", anchor="w").pack(
            fill=tk.X, padx=8
        )
        ttk.Label(steps, text="3. Salva il file CSV risultante", anchor="w").pack(fill=tk.X, padx=8, pady=(0, 6))

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(button_frame, text="Annulla", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Apri dialogo", command=self._start).pack(side=tk.RIGHT, padx=(0, 8))

        self.win.protocol("WM_DELETE_WINDOW", self._cancel)

    def _add_option(self, parent: ttk.LabelFrame, *, value: str, title: str, details: list[str]) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, padx=10, pady=(8, 2))
        ttk.Radiobutton(row, variable=self.choice_var, value=value).pack(side=tk.LEFT)
        text_block = ttk.Frame(row)
        text_block.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        ttk.Label(text_block, text=title, font="AppBold").pack(anchor="w")
        for detail in details:
            ttk.Label(text_block, text=f"• {detail}", foreground="gray40").pack(anchor="w")

    def _cancel(self) -> None:
        self.win.destroy()

    def _start(self) -> None:
        choice = self.choice_var.get()
        self.win.destroy()
        if choice == "magazzino":
            self._open_magazzino_dialog()
        else:
            self._open_soci_dialog()

    def _open_soci_dialog(self) -> None:
        try:
            from .export_dialog import ExportDialog

            ExportDialog(self.parent)
        except Exception as exc:  # pragma: no cover - UI safeguard
            messagebox.showerror("Export", f"Impossibile aprire il dialogo soci:\n{exc}", parent=self.parent)

    def _open_magazzino_dialog(self) -> None:
        try:
            from .magazzino_export_dialog import MagazzinoExportDialog

            MagazzinoExportDialog(self.parent)
        except Exception as exc:  # pragma: no cover - UI safeguard
            messagebox.showerror(
                "Export",
                f"Impossibile aprire il dialogo magazzino:\n{exc}",
                parent=self.parent,
            )
