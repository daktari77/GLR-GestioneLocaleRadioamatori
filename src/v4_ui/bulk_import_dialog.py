# -*- coding: utf-8 -*-
"""Minimal dialog for bulk importing documents from a folder."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog


class BulkImportDialog(tk.Toplevel):
    """Modal dialog returning (folder, category, move)."""

    def __init__(
        self,
        parent,
        *,
        title: str,
        categories: tuple[str, ...] | list[str],
        initial_category: str,
    ):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)

        self._categories = list(categories)
        self._result: tuple[str, str, bool] | None = None

        self.folder_var = tk.StringVar(value="")
        default_cat = initial_category if initial_category in self._categories else (self._categories[0] if self._categories else "")
        self.category_var = tk.StringVar(value=default_cat)
        self.move_var = tk.BooleanVar(value=False)

        self._build_ui()

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

    @property
    def result(self) -> tuple[str, str, bool] | None:
        return self._result

    def _build_ui(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(
            container,
            text="Importa tutti i file presenti nella cartella selezionata (non include sottocartelle).",
            wraplength=420,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(container, text="Categoria:").grid(row=1, column=0, sticky="w")
        self.category_combo = ttk.Combobox(
            container,
            textvariable=self.category_var,
            values=self._categories,
            state="readonly",
            width=30,
        )
        self.category_combo.grid(row=1, column=1, columnspan=2, sticky="we", pady=2)

        ttk.Label(container, text="Cartella sorgente:").grid(row=2, column=0, sticky="w")
        folder_entry = ttk.Entry(container, textvariable=self.folder_var, width=44)
        folder_entry.grid(row=2, column=1, sticky="we", pady=2)
        ttk.Button(container, text="Sfoglia...", command=self._browse).grid(row=2, column=2, sticky="e", padx=(6, 0))

        ttk.Checkbutton(container, text="Sposta (anziché copiare)", variable=self.move_var).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(6, 2)
        )

        buttons = ttk.Frame(container)
        buttons.grid(row=4, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Annulla", command=self._cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(buttons, text="Importa", command=self._confirm).pack(side=tk.RIGHT)

        container.columnconfigure(1, weight=1)

    def _browse(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="Seleziona cartella sorgente")
        if folder:
            self.folder_var.set(folder)

    def _confirm(self) -> None:
        folder = (self.folder_var.get() or "").strip()
        category = (self.category_var.get() or "").strip()
        move = bool(self.move_var.get())
        if not folder or not os.path.isdir(folder) or not category:
            return
        self._result = (folder, category, move)
        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()
