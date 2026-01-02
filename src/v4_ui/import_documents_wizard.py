# -*- coding: utf-8 -*-
"""Wizard for importing documents.

Allows choosing the target (Socio vs Sezione) and then a type coming from
the existing catalogs. The import itself reuses the existing bulk import
functions in the business layer.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable


class ImportDocumentsWizard(tk.Toplevel):
    """Modal wizard that performs a bulk import.

    The wizard asks:
    1) target: socio / sezione
    2) type (from the existing catalogs)
    3) source folder + copy/move

    For the "Socio" target, the import is executed against the currently
    selected member in the main list (provided via callback).
    """

    def __init__(
        self,
        parent,
        *,
        get_selected_member: Callable[[], tuple[int | None, str]],
        title: str = "Import documenti",
    ):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)

        self._get_selected_member = get_selected_member
        self._step = 0

        self._result: dict[str, object] | None = None

        self.target_var = tk.StringVar(value="")
        self.category_var = tk.StringVar(value="")
        self.folder_var = tk.StringVar(value="")
        self.move_var = tk.BooleanVar(value=False)

        self._categories: list[str] = []

        self._build_ui()
        self._show_step(0)

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

    @property
    def result(self) -> dict[str, object] | None:
        return self._result

    def _build_ui(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Steps container
        self.steps_frame = ttk.Frame(container)
        self.steps_frame.grid(row=0, column=0, sticky="nsew")

        self.step_frames: list[ttk.Frame] = []

        # Step 0: target
        f0 = ttk.Frame(self.steps_frame)
        ttk.Label(
            f0,
            text="Seleziona cosa vuoi importare:",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Radiobutton(f0, text="Socio (documenti del socio selezionato)", variable=self.target_var, value="socio", command=self._on_target_changed).grid(
            row=1, column=0, sticky="w", pady=2
        )
        ttk.Radiobutton(f0, text="Sezione (documenti di sezione)", variable=self.target_var, value="sezione", command=self._on_target_changed).grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.step_frames.append(f0)

        # Step 1: type
        f1 = ttk.Frame(self.steps_frame)
        ttk.Label(f1, text="Seleziona il tipo:").grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.member_info_label = ttk.Label(f1, text="")
        self.member_info_label.grid(row=1, column=0, sticky="w", pady=(0, 6))

        self.category_combo = ttk.Combobox(
            f1,
            textvariable=self.category_var,
            values=self._categories,
            state="readonly",
            width=34,
        )
        self.category_combo.grid(row=2, column=0, sticky="we")
        f1.columnconfigure(0, weight=1)
        self.step_frames.append(f1)

        # Step 2: folder + move/copy
        f2 = ttk.Frame(self.steps_frame)
        ttk.Label(
            f2,
            text="Seleziona la cartella sorgente (solo i file nella cartella, non include sottocartelle).",
            wraplength=440,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(f2, text="Cartella sorgente:").grid(row=1, column=0, sticky="w")
        ttk.Entry(f2, textvariable=self.folder_var, width=44).grid(row=1, column=1, sticky="we", pady=2)
        ttk.Button(f2, text="Sfoglia...", command=self._browse).grid(row=1, column=2, sticky="e", padx=(6, 0))

        ttk.Checkbutton(f2, text="Sposta (anziché copiare)", variable=self.move_var).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(8, 2)
        )
        f2.columnconfigure(1, weight=1)
        self.step_frames.append(f2)

        # Buttons
        buttons = ttk.Frame(container)
        buttons.grid(row=1, column=0, sticky="e", pady=(10, 0))

        self.back_btn = ttk.Button(buttons, text="Indietro", command=self._back)
        self.next_btn = ttk.Button(buttons, text="Avanti", command=self._next)
        self.import_btn = ttk.Button(buttons, text="Importa", command=self._import)
        ttk.Button(buttons, text="Annulla", command=self._cancel).pack(side=tk.RIGHT)
        self.import_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.next_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.back_btn.pack(side=tk.RIGHT, padx=(0, 6))

        container.columnconfigure(0, weight=1)

    def _show_step(self, index: int) -> None:
        self._step = max(0, min(index, len(self.step_frames) - 1))
        for i, frame in enumerate(self.step_frames):
            frame.grid_forget()
            if i == self._step:
                frame.grid(row=0, column=0, sticky="nsew")

        self.back_btn.configure(state=("disabled" if self._step == 0 else "normal"))
        is_last = self._step == (len(self.step_frames) - 1)
        self.next_btn.pack_forget()
        self.import_btn.pack_forget()
        if is_last:
            self.import_btn.pack(side=tk.RIGHT, padx=(6, 0))
        else:
            self.next_btn.pack(side=tk.RIGHT, padx=(6, 0))

        if self._step == 1:
            self._refresh_member_info()

    def _on_target_changed(self) -> None:
        self._update_categories()
        self._refresh_member_info()

    def _update_categories(self) -> None:
        target = (self.target_var.get() or "").strip().lower()

        from preferences import get_document_categories, get_section_document_categories

        if target == "sezione":
            self._categories = list(get_section_document_categories())
        else:
            self._categories = list(get_document_categories())
        self.category_combo.configure(values=self._categories)

        if self._categories:
            current = (self.category_var.get() or "").strip()
            if current not in self._categories:
                self.category_var.set(self._categories[0])
        else:
            self.category_var.set("")

    def _refresh_member_info(self) -> None:
        target = (self.target_var.get() or "").strip().lower()
        if target != "socio":
            self.member_info_label.configure(text="")
            return
        member_id, label = self._get_selected_member()
        if member_id is None:
            self.member_info_label.configure(text="Socio selezionato: (nessuno)")
        else:
            self.member_info_label.configure(text=f"Socio selezionato: {label} (#{member_id})")

    def _browse(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="Seleziona cartella sorgente")
        if folder:
            self.folder_var.set(folder)

    def _validate_step(self) -> bool:
        if self._step == 0:
            target = (self.target_var.get() or "").strip().lower()
            if target not in ("socio", "sezione"):
                messagebox.showwarning("Import documenti", "Seleziona 'Socio' o 'Sezione'.", parent=self)
                return False
            self._update_categories()
            return True

        if self._step == 1:
            target = (self.target_var.get() or "").strip().lower()
            categoria = (self.category_var.get() or "").strip()
            if not categoria:
                messagebox.showwarning("Import documenti", "Seleziona una categoria.", parent=self)
                return False
            if target == "socio":
                member_id, _label = self._get_selected_member()
                if member_id is None:
                    messagebox.showwarning("Import documenti", "Seleziona prima un socio nella lista Soci.", parent=self)
                    return False
            return True

        if self._step == 2:
            folder = (self.folder_var.get() or "").strip()
            if not folder or not os.path.isdir(folder):
                messagebox.showwarning("Import documenti", "Seleziona una cartella sorgente valida.", parent=self)
                return False
            return True

        return True

    def _next(self) -> None:
        if not self._validate_step():
            return
        self._show_step(self._step + 1)

    def _back(self) -> None:
        self._show_step(self._step - 1)

    def _import(self) -> None:
        if not self._validate_step():
            return

        target = (self.target_var.get() or "").strip().lower()
        categoria = (self.category_var.get() or "").strip()
        folder = (self.folder_var.get() or "").strip()
        move = bool(self.move_var.get())

        try:
            if target == "sezione":
                from section_documents import bulk_import_section_documents

                imported, failed, details = bulk_import_section_documents(folder, categoria, move=move)
            else:
                member_id, _label = self._get_selected_member()
                if member_id is None:
                    messagebox.showwarning("Import documenti", "Seleziona prima un socio nella lista Soci.", parent=self)
                    return
                from documents_manager import bulk_import_member_documents

                imported, failed, details = bulk_import_member_documents(member_id, folder, categoria, move=move)
                try:
                    if imported > 0 and (categoria or "").strip().lower() == "privacy":
                        from database import set_privacy_signed

                        set_privacy_signed(member_id, True)
                except Exception:
                    pass
        except Exception as exc:
            messagebox.showerror("Import documenti", f"Errore importazione:\n{exc}", parent=self)
            return

        if imported == 0 and failed == 0:
            messagebox.showinfo("Import documenti", "Nessun file trovato nella cartella selezionata.", parent=self)
        else:
            from .import_report import build_import_summary

            messagebox.showinfo("Import documenti", build_import_summary(imported, failed, details), parent=self)

        self._result = {
            "target": target,
            "categoria": categoria,
            "folder": folder,
            "move": move,
            "imported": imported,
            "failed": failed,
        }
        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()
