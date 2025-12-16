# -*- coding: utf-8 -*-
"""Dialog for exporting inventory (magazzino) data to CSV."""

from __future__ import annotations

import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from magazzino_manager import list_items
from utils import iso_to_ddmmyyyy

STATUS_AVAILABLE = "Disponibile"
STATUS_LOANED = "In prestito"

EXPORT_FIELDS = [
    ("numero_inventario", "Numero inventario"),
    ("marca", "Marca"),
    ("modello", "Modello"),
    ("descrizione", "Descrizione"),
    ("note", "Note"),
    ("stato", "Stato"),
    ("assegnato_a", "Assegnato a"),
    ("assegnato_matricola", "Matricola assegnatario"),
    ("data_prestito", "Data prestito attivo"),
    ("updated_at", "Ultimo aggiornamento"),
]

DEFAULT_FIELDS = [
    "numero_inventario",
    "marca",
    "modello",
    "descrizione",
    "stato",
    "assegnato_a",
    "assegnato_matricola",
]


class MagazzinoExportDialog(tk.Toplevel):
    """Simple dialog that lets the user export the magazzino list to CSV."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.title("Esporta magazzino in CSV")
        self.geometry("540x520")
        self.transient(parent)
        self.grab_set()

        self.field_vars: dict[str, tk.BooleanVar] = {}
        self.status_filter = tk.StringVar(value="tutti")

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            container,
            text=(
                "Seleziona i campi da includere e scegli se esportare solo gli "
                "oggetti disponibili o quelli attualmente in prestito."
            ),
            wraplength=480,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 10))

        # Field presets
        preset_frame = ttk.Frame(container)
        preset_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(preset_frame, text="Tutti", command=self._select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Nessuno", command=self._deselect_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Essenziali", command=self._select_default).pack(side=tk.LEFT, padx=2)

        # Scrollable field list
        list_frame = ttk.Frame(container)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        fields_holder = ttk.Frame(canvas)
        fields_holder.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=fields_holder, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for key, label in EXPORT_FIELDS:
            var = tk.BooleanVar(value=key in DEFAULT_FIELDS)
            chk = ttk.Checkbutton(fields_holder, text=label, variable=var)
            chk.pack(anchor="w", padx=4, pady=2)
            self.field_vars[key] = var

        filter_frame = ttk.LabelFrame(container, text="Filtro stato")
        filter_frame.pack(fill=tk.X, pady=6)
        ttk.Radiobutton(filter_frame, text="Tutti", value="tutti", variable=self.status_filter).pack(
            side=tk.LEFT, padx=4, pady=4
        )
        ttk.Radiobutton(filter_frame, text="Solo disponibili", value="disponibili", variable=self.status_filter).pack(
            side=tk.LEFT, padx=4, pady=4
        )
        ttk.Radiobutton(filter_frame, text="Solo in prestito", value="prestito", variable=self.status_filter).pack(
            side=tk.LEFT, padx=4, pady=4
        )

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(button_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(button_frame, text="Esporta", command=self._export).pack(side=tk.RIGHT, padx=4)

    def _select_all(self) -> None:
        for var in self.field_vars.values():
            var.set(True)

    def _deselect_all(self) -> None:
        for var in self.field_vars.values():
            var.set(False)

    def _select_default(self) -> None:
        for key, var in self.field_vars.items():
            var.set(key in DEFAULT_FIELDS)

    # ------------------------------------------------------------------
    # Export logic
    # ------------------------------------------------------------------
    def _export(self) -> None:
        fields = [key for key, var in self.field_vars.items() if var.get()]
        if not fields:
            messagebox.showwarning("Export", "Seleziona almeno un campo." , parent=self)
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            title="Esporta magazzino",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tutti i file", "*.*")],
            initialfile="magazzino.csv",
        )
        if not path:
            return

        try:
            items = list_items()
        except Exception as exc:
            messagebox.showerror("Export", f"Impossibile leggere il magazzino:\n{exc}", parent=self)
            return

        filtered = [item for item in items if self._matches_filter(item)]
        if not filtered:
            messagebox.showinfo("Export", "Nessun oggetto corrisponde al filtro selezionato.", parent=self)
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
                writer.writeheader()
                for item in filtered:
                    writer.writerow({key: self._extract_field(key, item) for key in fields})
        except Exception as exc:
            messagebox.showerror("Export", f"Errore durante il salvataggio:\n{exc}", parent=self)
            return

        messagebox.showinfo("Export", f"File generato:\n{path}", parent=self)
        self.destroy()

    def _matches_filter(self, item: dict) -> bool:
        status = self.status_filter.get()
        is_loaned = bool(item.get("active_loan_id"))
        if status == "disponibili" and is_loaned:
            return False
        if status == "prestito" and not is_loaned:
            return False
        return True

    def _extract_field(self, key: str, item: dict) -> str:
        if key == "stato":
            return STATUS_LOANED if item.get("active_loan_id") else STATUS_AVAILABLE
        if key == "assegnato_a":
            nome = (item.get("active_socio_nome") or "").strip()
            cognome = (item.get("active_socio_cognome") or "").strip()
            full = f"{cognome} {nome}".strip()
            return full
        if key == "assegnato_matricola":
            return item.get("active_socio_matricola") or ""
        if key == "data_prestito":
            return iso_to_ddmmyyyy(item.get("active_data_prestito")) or ""
        value = item.get(key)
        return "" if value is None else str(value)
