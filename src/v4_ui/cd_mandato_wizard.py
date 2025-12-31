# -*- coding: utf-8 -*-

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from utils import ddmmyyyy_to_iso


class CdMandatoWizard(tk.Toplevel):
    """Wizard/dialog per aggiornare Mandato + composizione Consiglio Direttivo."""

    DEFAULT_CARICHE = (
        "Presidente",
        "Vicepresidente",
        "Segretario",
        "Tesoriere",
        "Consigliere",
        "Sindaco/Revisore",
        "Altro",
    )

    def __init__(self, parent: tk.Misc, *, on_saved=None):
        super().__init__(parent)
        self.title("Mandato Consiglio Direttivo")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.on_saved = on_saved
        self.result = None

        self.var_label = tk.StringVar()
        self.var_start = tk.StringVar()
        self.var_end = tk.StringVar()
        self.var_note = tk.StringVar()

        self._build_ui()
        self._load_current()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda _e: self._on_cancel())

    def _build_ui(self):
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        frm = ttk.LabelFrame(container, text="Periodo mandato")
        frm.pack(fill=tk.X, padx=0, pady=(0, 10))

        ttk.Label(frm, text="Etichetta (es. 2023-2025)").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm, textvariable=self.var_label, width=30).grid(row=0, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(frm, text="Inizio").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm, textvariable=self.var_start, width=20).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(frm, text="Fine").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm, textvariable=self.var_end, width=20).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(frm, text="Note").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm, textvariable=self.var_note).grid(row=3, column=1, sticky="ew", padx=6, pady=4)

        frm.columnconfigure(1, weight=1)

        comp = ttk.LabelFrame(container, text="Componenti e cariche")
        comp.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(comp)
        toolbar.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(toolbar, text="Aggiungi", command=self._add_member).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Modifica", command=self._edit_member).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Rimuovi", command=self._remove_member).pack(side=tk.LEFT, padx=2)

        frame = ttk.Frame(comp)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        sb_v = ttk.Scrollbar(frame, orient="vertical")
        self.tv = ttk.Treeview(
            frame,
            columns=("carica", "nome", "note"),
            show="headings",
            yscrollcommand=sb_v.set,
        )
        sb_v.config(command=self.tv.yview)

        self.tv.heading("carica", text="Carica")
        self.tv.heading("nome", text="Nominativo")
        self.tv.heading("note", text="Note")

        self.tv.column("carica", width=160)
        self.tv.column("nome", width=320)
        self.tv.column("note", width=260)

        self.tv.grid(row=0, column=0, sticky="nsew")
        sb_v.grid(row=0, column=1, sticky="ns")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        bottom = ttk.Frame(container)
        bottom.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(bottom, text="Annulla", command=self._on_cancel).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bottom, text="Salva", command=self._on_save).pack(side=tk.RIGHT, padx=4)

    def _load_current(self):
        try:
            from cd_mandati import get_active_cd_mandato

            cur = get_active_cd_mandato()
        except Exception:
            cur = None

        if cur:
            self.var_label.set(str(cur.get("label") or ""))
            self.var_start.set(str(cur.get("start_date") or ""))
            self.var_end.set(str(cur.get("end_date") or ""))
            self.var_note.set(str(cur.get("note") or ""))
            for row in self.tv.get_children():
                self.tv.delete(row)
            for idx, m in enumerate(cur.get("composizione") or [], start=1):
                iid = f"m{idx}"
                self.tv.insert(
                    "",
                    tk.END,
                    iid=iid,
                    values=(
                        str(m.get("carica") or ""),
                        str(m.get("nome") or ""),
                        str(m.get("note") or ""),
                    ),
                )
        else:
            # Prefill per triennio corrente citato (2023-2025)
            if not self.var_label.get().strip():
                self.var_label.set("2023-2025")
            if not self.var_start.get().strip():
                self.var_start.set("2023-01-01")
            if not self.var_end.get().strip():
                self.var_end.set("2025-12-31")

    def _ask_member_data(self, *, initial=None):
        initial = initial or {}
        nome = simpledialog.askstring("Componente CD", "Nominativo", initialvalue=str(initial.get("nome") or ""), parent=self)
        if nome is None:
            return None
        nome = nome.strip()
        if not nome:
            messagebox.showwarning("Componente CD", "Inserire un nominativo.")
            return None

        carica = simpledialog.askstring(
            "Componente CD",
            "Carica (es. Presidente, Segretario, Consigliere)",
            initialvalue=str(initial.get("carica") or "Consigliere"),
            parent=self,
        )
        if carica is None:
            return None
        carica = carica.strip() or "Consigliere"

        note = simpledialog.askstring("Componente CD", "Note (opzionale)", initialvalue=str(initial.get("note") or ""), parent=self)
        if note is None:
            note = ""

        return {"nome": nome, "carica": carica, "note": note}

    def _add_member(self):
        data = self._ask_member_data()
        if not data:
            return
        iid = f"m{len(self.tv.get_children()) + 1}"
        self.tv.insert("", tk.END, iid=iid, values=(data["carica"], data["nome"], data["note"]))

    def _edit_member(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("Componenti CD", "Selezionare una riga da modificare")
            return
        iid = sel[0]
        vals = self.tv.item(iid, "values")
        initial = {"carica": vals[0] if len(vals) > 0 else "", "nome": vals[1] if len(vals) > 1 else "", "note": vals[2] if len(vals) > 2 else ""}
        data = self._ask_member_data(initial=initial)
        if not data:
            return
        self.tv.item(iid, values=(data["carica"], data["nome"], data["note"]))

    def _remove_member(self):
        sel = self.tv.selection()
        if not sel:
            return
        for iid in sel:
            self.tv.delete(iid)

    def _on_save(self):
        # Parse/normalize dates (accept DD/MM/YYYY or ISO)
        try:
            start_iso = ddmmyyyy_to_iso(self.var_start.get())
            end_iso = ddmmyyyy_to_iso(self.var_end.get())
        except Exception as exc:
            messagebox.showerror("Mandato CD", f"Date non valide: {exc}")
            return

        if not start_iso or not end_iso:
            messagebox.showerror("Mandato CD", "Inserire sia data inizio che data fine")
            return
        if start_iso > end_iso:
            messagebox.showerror("Mandato CD", "La data di inizio non può essere successiva alla data di fine")
            return

        label = (self.var_label.get() or "").strip()
        note = (self.var_note.get() or "").strip()

        composizione = []
        for iid in self.tv.get_children():
            carica, nome, note_riga = self.tv.item(iid, "values")
            composizione.append({"carica": str(carica), "nome": str(nome), "note": str(note_riga)})

        try:
            from cd_mandati import save_cd_mandato

            mandato_id = save_cd_mandato(
                label=label,
                start_date=start_iso,
                end_date=end_iso,
                composizione=composizione,
                note=note,
            )
        except Exception as exc:
            messagebox.showerror("Mandato CD", f"Errore salvataggio: {exc}")
            return

        if mandato_id < 0:
            messagebox.showerror("Mandato CD", "Impossibile salvare il mandato")
            return

        self.result = {"id": mandato_id, "label": label, "start_date": start_iso, "end_date": end_iso}
        if callable(self.on_saved):
            try:
                self.on_saved(self.result)
            except Exception:
                pass

        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
