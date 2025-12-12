# -*- coding: utf-8 -*-
"""Simple wizard/dialog to create calendar events."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from database import add_calendar_event, update_calendar_event

EVENT_TYPES = (
    ("riunione_cd", "Riunione CD"),
    ("assemblea", "Assemblea ordinaria"),
    ("elezioni", "Elezioni"),
    ("altro", "Altro"),
)


def _suggest_title(event_type: str) -> str:
    mapping = {
        "riunione_cd": "Riunione Consiglio Direttivo",
        "assemblea": "Assemblea ordinaria soci",
        "elezioni": "Sessione elettorale",
    }
    return mapping.get(event_type, "Evento calendario")


class CalendarWizard(tk.Toplevel):
    """Dialog to create or edit a single calendar event."""

    def __init__(self, parent, *, event: dict | None = None, on_saved=None):
        super().__init__(parent)
        self.event = event or {}
        self.event_id = self.event.get("id") if isinstance(self.event, dict) else None
        self.is_edit = self.event_id is not None
        self.title("Modifica evento" if self.is_edit else "Nuovo evento calendario")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.on_saved = on_saved

        default_type = self.event.get("tipo") or EVENT_TYPES[0][0]
        self.type_var = tk.StringVar(value=default_type)
        self.type_display_var = tk.StringVar(value=self._display_for_type(default_type))
        default_title = self.event.get("titolo") or _suggest_title(default_type)
        self.title_var = tk.StringVar(value=default_title)
        start_ts = self.event.get("start_ts")
        if start_ts:
            try:
                dt = datetime.strptime(start_ts, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                dt = None
        else:
            dt = None
        now = datetime.now()
        dt = dt or now
        self.date_var = tk.StringVar(value=dt.strftime("%Y-%m-%d"))
        self.time_var = tk.StringVar(value=dt.strftime("%H:%M"))
        self.location_var = tk.StringVar(value=self.event.get("luogo") or "")
        reminder_default = self.event.get("reminder_days")
        self.reminder_var = tk.IntVar(value=reminder_default if reminder_default is not None else 14)

        self._build_ui()
        self._setup_bindings()
        descr = self.event.get("descrizione")
        if isinstance(descr, str) and descr.strip():
            self.notes.insert("1.0", descr)

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Tipo evento:").grid(row=0, column=0, sticky="e", pady=4, padx=4)
        type_combo = ttk.Combobox(
            frm,
            state="readonly",
            values=[label for _, label in EVENT_TYPES],
            textvariable=self.type_display_var,
        )
        self.type_combo = type_combo
        self._select_type_combo()
        type_combo.grid(row=0, column=1, sticky="we", pady=4, padx=4)

        ttk.Label(frm, text="Titolo:").grid(row=1, column=0, sticky="e", pady=4, padx=4)
        ttk.Entry(frm, textvariable=self.title_var, width=40).grid(row=1, column=1, sticky="we", pady=4, padx=4)

        ttk.Label(frm, text="Data (YYYY-MM-DD):").grid(row=2, column=0, sticky="e", pady=4, padx=4)
        ttk.Entry(frm, textvariable=self.date_var).grid(row=2, column=1, sticky="we", pady=4, padx=4)

        ttk.Label(frm, text="Ora (HH:MM):").grid(row=3, column=0, sticky="e", pady=4, padx=4)
        ttk.Entry(frm, textvariable=self.time_var).grid(row=3, column=1, sticky="we", pady=4, padx=4)

        ttk.Label(frm, text="Luogo:").grid(row=4, column=0, sticky="e", pady=4, padx=4)
        ttk.Entry(frm, textvariable=self.location_var).grid(row=4, column=1, sticky="we", pady=4, padx=4)

        ttk.Label(frm, text="Promemoria (giorni prima):").grid(row=5, column=0, sticky="e", pady=4, padx=4)
        ttk.Spinbox(frm, from_=0, to=90, textvariable=self.reminder_var, width=5).grid(row=5, column=1, sticky="w", pady=4, padx=4)

        ttk.Label(frm, text="Note:").grid(row=6, column=0, sticky="ne", pady=4, padx=4)
        self.notes = tk.Text(frm, width=40, height=4)
        self.notes.grid(row=6, column=1, sticky="we", pady=4, padx=4)

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btns, text="Annulla", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="Salva", command=self._save).pack(side=tk.RIGHT, padx=4)

        frm.columnconfigure(1, weight=1)

    def _setup_bindings(self):
        self.type_combo.bind("<<ComboboxSelected>>", self._on_type_change)

    def _select_type_combo(self):
        selected = self.type_var.get()
        labels = [label for _, label in EVENT_TYPES]
        values = [code for code, _ in EVENT_TYPES]
        try:
            idx = values.index(selected)
        except ValueError:
            idx = 0
        self.type_combo.current(idx)
        self.type_display_var.set(labels[idx])

    def _on_type_change(self, event=None):
        idx = self.type_combo.current()
        if idx < 0:
            return
        tipo = EVENT_TYPES[idx][0]
        self.type_var.set(tipo)
        if not self.title_var.get().strip() or self.title_var.get() == _suggest_title(self.type_var.get()):
            self.title_var.set(_suggest_title(tipo))

    def _display_for_type(self, code: str) -> str:
        for c, label in EVENT_TYPES:
            if c == code:
                return label
        return code

    def _parse_datetime(self) -> str | None:
        try:
            dt = datetime.strptime(f"{self.date_var.get().strip()} {self.time_var.get().strip()}", "%Y-%m-%d %H:%M")
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None

    def _save(self):
        start_ts = self._parse_datetime()
        if not start_ts:
            messagebox.showerror("Data/ora", "Inserire data e ora nel formato richiesto.")
            return
        titolo = self.title_var.get().strip()
        if not titolo:
            messagebox.showerror("Titolo", "Inserire un titolo per l'evento.")
            return

        descrizione = self.notes.get("1.0", tk.END).strip() or None
        tipo = self.type_var.get()
        luogo = self.location_var.get().strip() or None
        reminder_days = int(self.reminder_var.get() or 0)
        if self.is_edit and self.event_id:
            update_calendar_event(
                self.event_id,
                tipo=tipo,
                titolo=titolo,
                start_ts=start_ts,
                descrizione=descrizione,
                luogo=luogo,
                reminder_days=reminder_days,
            )
            event_id = self.event_id
        else:
            event_id = add_calendar_event(
                tipo=tipo,
                titolo=titolo,
                start_ts=start_ts,
                descrizione=descrizione,
                luogo=luogo,
                reminder_days=reminder_days,
            )
        if self.on_saved:
            self.on_saved(event_id)
        self.destroy()