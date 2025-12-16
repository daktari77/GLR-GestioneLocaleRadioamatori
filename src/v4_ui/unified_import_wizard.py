# -*- coding: utf-8 -*-
"""Unified CSV import wizard launcher for Soci and Magazzino flows."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Iterable


class UnifiedImportWizard:
    """Small wizard that lets the user pick which CSV flow to start."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_soci_complete: Callable[[int], None] | None = None,
        on_magazzino_complete: Callable[[int], None] | None = None,
    ) -> None:
        self.parent = parent
        self.on_soci_complete = on_soci_complete
        self.on_magazzino_complete = on_magazzino_complete
        self.choice_var = tk.StringVar(value="soci")

        self.win = tk.Toplevel(parent)
        self.win.title("Importazione CSV")
        self.win.geometry("540x460")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.win, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Importa dati da file CSV", font=("Segoe UI", 12, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            container,
            text=(
                "Scegli il tipo di importazione da eseguire. Il flusso include selezione file, "
                "mapping dei campi, verifica e inserimento finale."
            ),
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 12))

        options = ttk.LabelFrame(container, text="Modalità disponibili")
        options.pack(fill=tk.X, pady=(0, 16))

        self._add_option(
            options,
            value="soci",
            title="Soci",
            details=[
                "Importa nuovi soci o aggiorna quelli esistenti",
                "Wizard completo con mapping campi personalizzabile",
            ],
        )
        self._add_option(
            options,
            value="magazzino",
            title="Magazzino",
            details=[
                "Carica o aggiorna gli oggetti di inventario",
                "Supporto CSV ed Excel, gestione duplicati",
            ],
        )

        steps = ttk.LabelFrame(container, text="Fasi")
        steps.pack(fill=tk.X)
        ttk.Label(
            steps,
            text="1. Selezione file e rilevazione delimitatore",
        ).pack(anchor="w", padx=8, pady=(6, 0))
        ttk.Label(steps, text="2. Mapping campi e opzioni di importazione").pack(anchor="w", padx=8)
        ttk.Label(steps, text="3. Controlli, verifica finale e importazione").pack(anchor="w", padx=8, pady=(0, 6))

        btns = ttk.Frame(container)
        btns.pack(fill=tk.X, pady=(18, 0))
        ttk.Button(btns, text="Annulla", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Avvia wizard", command=self._start_wizard).pack(side=tk.RIGHT, padx=(0, 8))

        self.win.protocol("WM_DELETE_WINDOW", self._cancel)

    def _add_option(self, parent: ttk.LabelFrame, *, value: str, title: str, details: Iterable[str]) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, padx=10, pady=(8, 2))
        ttk.Radiobutton(row, value=value, variable=self.choice_var).pack(side=tk.LEFT)
        text_block = ttk.Frame(row)
        text_block.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        ttk.Label(text_block, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        for detail in details:
            ttk.Label(text_block, text=f"• {detail}", foreground="#555").pack(anchor="w")

    def _cancel(self) -> None:
        self.win.destroy()

    def _start_wizard(self) -> None:
        choice = self.choice_var.get()
        self.win.destroy()
        if choice == "magazzino":
            self._open_magazzino_import()
        else:
            self._open_soci_import()

    def _open_soci_import(self) -> None:
        try:
            from import_wizard import ImportWizard

            ImportWizard(self.parent, on_complete_callback=self.on_soci_complete)
        except Exception as exc:  # pragma: no cover - UI safeguard
            messagebox.showerror("Import CSV", f"Errore aprendo il wizard Soci:\n{exc}", parent=self.parent)

    def _open_magazzino_import(self) -> None:
        try:
            from .magazzino_import_dialog import MagazzinoImportDialog

            MagazzinoImportDialog(self.parent, on_complete=self.on_magazzino_complete)
        except Exception as exc:  # pragma: no cover - UI safeguard
            messagebox.showerror(
                "Import CSV",
                f"Errore aprendo il wizard Magazzino:\n{exc}",
                parent=self.parent,
            )
