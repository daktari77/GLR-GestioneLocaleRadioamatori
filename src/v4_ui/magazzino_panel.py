# -*- coding: utf-8 -*-
"""Tk panel for inventory (magazzino) management."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from datetime import datetime

from magazzino_manager import (
    create_item,
    create_loan,
    delete_item,
    get_active_loan,
    get_item,
    list_items,
    list_loans,
    register_return,
    update_item,
)
from database import fetch_all
from utils import iso_to_ddmmyyyy

STATUS_DISPONIBILE = "Disponibile"
STATUS_PRESTITO = "In prestito"


class MagazzinoPanel(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.current_id: int | None = None
        self.items: list[dict] = []
        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="tutti")
        self.status_var = tk.StringVar(value="Nessun oggetto selezionato")
        self.loan_info_var = tk.StringVar(value="—")
        self._build_ui()
        self.refresh_list()

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------
    def _build_ui(self):
        self._build_toolbar()
        self._build_tree()
        self._build_form()
        self._build_loans_block()

    def _build_toolbar(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text="Nuovo oggetto", command=self._new_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Salva", command=self._save_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Elimina", command=self._delete_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Aggiorna", command=self.refresh_list).pack(side=tk.LEFT, padx=12)

        ttk.Label(toolbar, text="Filtro stato:").pack(side=tk.LEFT, padx=(10, 2))
        filter_combo = ttk.Combobox(
            toolbar,
            values=("tutti", STATUS_DISPONIBILE, STATUS_PRESTITO),
            textvariable=self.filter_var,
            width=14,
            state="readonly",
        )
        filter_combo.pack(side=tk.LEFT)
        filter_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_list())

        ttk.Label(toolbar, text="Cerca:").pack(side=tk.LEFT, padx=(14, 2))
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=28)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<Return>", lambda _e: self.refresh_list())
        ttk.Button(toolbar, text="Applica", command=self.refresh_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Reset", command=self._reset_filters).pack(side=tk.LEFT, padx=2)

    def _build_tree(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        columns = ("numero", "marca", "modello", "descrizione", "stato", "assegnato")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=8, selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        headings = {
            "numero": "Inventario",
            "marca": "Marca",
            "modello": "Modello",
            "descrizione": "Descrizione",
            "stato": "Stato",
            "assegnato": "Assegnato a",
        }
        widths = {"numero": 120, "marca": 130, "modello": 130, "descrizione": 260, "stato": 100, "assegnato": 220}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            anchor = "center" if col in {"stato"} else "w"
            self.tree.column(col, width=widths[col], anchor=anchor)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.tag_configure("loaned", background="#fff4ce")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._load_selected())

    def _build_form(self):
        form = ttk.LabelFrame(self, text="Dettagli oggetto")
        form.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.numero_var = tk.StringVar()
        self.marca_var = tk.StringVar()
        self.modello_var = tk.StringVar()

        ttk.Label(form, text="Numero inventario *").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.numero_var, width=24).grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(form, text="Marca *").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.marca_var, width=24).grid(row=0, column=3, sticky="ew", padx=4, pady=2)

        ttk.Label(form, text="Modello").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.modello_var, width=24).grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(form, text="Descrizione").grid(row=1, column=2, sticky="w", padx=4, pady=2)
        self.descrizione_text = tk.Text(form, height=3, width=50, wrap=tk.WORD)
        self.descrizione_text.grid(row=1, column=3, sticky="ew", padx=4, pady=2)

        ttk.Label(form, text="Note interne").grid(row=2, column=0, sticky="nw", padx=4, pady=2)
        self.note_text = tk.Text(form, height=3, width=80, wrap=tk.WORD)
        self.note_text.grid(row=2, column=1, columnspan=3, sticky="ew", padx=4, pady=2)

        ttk.Label(form, textvariable=self.status_var, foreground="#444").grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 2))
        ttk.Label(form, textvariable=self.loan_info_var, foreground="#b35a00").grid(row=3, column=2, columnspan=2, sticky="e", padx=4, pady=(4, 2))

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=2)

    def _build_loans_block(self):
        block = ttk.LabelFrame(self, text="Prestiti")
        block.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        btn_frame = ttk.Frame(block)
        btn_frame.pack(fill=tk.X, padx=4, pady=(4, 0))
        ttk.Button(btn_frame, text="Nuovo prestito", command=self._new_loan).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Registra reso", command=self._register_return).pack(side=tk.LEFT, padx=2)

        columns = ("socio", "matricola", "data_out", "data_in", "note")
        self.loans_tree = ttk.Treeview(block, columns=columns, show="headings", height=5)
        self.loans_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        headings = {
            "socio": "Socio",
            "matricola": "Matricola",
            "data_out": "Prestato il",
            "data_in": "Restituito il",
            "note": "Note",
        }
        widths = {"socio": 220, "matricola": 90, "data_out": 110, "data_in": 110, "note": 280}
        for col in columns:
            self.loans_tree.heading(col, text=headings[col])
            anchor = "center" if col in {"matricola", "data_out", "data_in"} else "w"
            self.loans_tree.column(col, width=widths[col], anchor=anchor)
        self.loan_rows: dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Data handling
    # ------------------------------------------------------------------
    def refresh_list(self):
        try:
            rows = list_items()
        except Exception as exc:
            messagebox.showerror("Magazzino", f"Errore caricando il magazzino:\n{exc}")
            return
        search = self.search_var.get().strip().lower()
        filter_state = self.filter_var.get()
        filtered: list[dict] = []
        for row in rows:
            testo = " ".join(
                [
                    str(row.get("numero_inventario", "")),
                    str(row.get("marca", "")),
                    str(row.get("modello", "")),
                    str(row.get("descrizione", "")),
                ]
            ).lower()
            status_label = STATUS_PRESTITO if row.get("active_loan_id") else STATUS_DISPONIBILE
            row["_status_label"] = status_label
            if search and search not in testo:
                continue
            if filter_state != "tutti" and status_label != filter_state:
                continue
            filtered.append(row)

        tree = self.tree
        prev = tree.selection()
        prev_id = prev[0] if prev else None
        for item in tree.get_children():
            tree.delete(item)

        for row in filtered:
            iid = str(row.get("id"))
            assigned = self._format_member(row)
            tags = ["loaned"] if row.get("active_loan_id") else []
            tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    row.get("numero_inventario", ""),
                    row.get("marca", ""),
                    row.get("modello", ""),
                    row.get("descrizione", ""),
                    row.get("_status_label"),
                    assigned,
                ),
                tags=tags,
            )
        self.items = filtered
        if prev_id and tree.exists(prev_id):
            tree.selection_set(prev_id)
            tree.focus(prev_id)
        elif filtered:
            first = str(filtered[0].get("id"))
            tree.selection_set(first)
            tree.focus(first)
        else:
            self._clear_form()
            self._clear_loans()
            self.status_var.set("Nessun oggetto trovato")
            return
        self._load_selected()

    def _reset_filters(self):
        self.search_var.set("")
        self.filter_var.set("tutti")
        self.refresh_list()

    def _format_member(self, row: dict) -> str:
        if not row.get("active_socio_id"):
            return ""
        nome = row.get("active_socio_nome") or ""
        cognome = row.get("active_socio_cognome") or ""
        nominativo = f"{cognome} {nome}".strip()
        matricola = row.get("active_socio_matricola") or ""
        if matricola:
            return f"{nominativo} (Mat. {matricola})"
        return nominativo

    def _load_selected(self):
        selection = self.tree.selection()
        if not selection:
            self._clear_form()
            self._clear_loans()
            return
        item_id = int(selection[0])
        self.current_id = item_id
        data = next((row for row in self.items if row.get("id") == item_id), get_item(item_id))
        if not data:
            self._clear_form()
            self._clear_loans()
            return
        self.numero_var.set(data.get("numero_inventario") or "")
        self.marca_var.set(data.get("marca") or "")
        self.modello_var.set(data.get("modello") or "")
        self.descrizione_text.delete("1.0", tk.END)
        self.descrizione_text.insert("1.0", data.get("descrizione") or "")
        self.note_text.delete("1.0", tk.END)
        self.note_text.insert("1.0", data.get("note") or "")
        active = get_active_loan(item_id)
        if active:
            socio = self._format_loan_member(active)
            self.status_var.set(f"Oggetto #{item_id} - {STATUS_PRESTITO}")
            self.loan_info_var.set(f"Prestato a {socio} dal {iso_to_ddmmyyyy(active.get('data_prestito'))}")
        else:
            self.status_var.set(f"Oggetto #{item_id} - {STATUS_DISPONIBILE}")
            self.loan_info_var.set("—")
        self._refresh_loans()

    def _clear_form(self):
        self.current_id = None
        for var in (self.numero_var, self.marca_var, self.modello_var):
            var.set("")
        self.descrizione_text.delete("1.0", tk.END)
        self.note_text.delete("1.0", tk.END)
        self.status_var.set("Nessun oggetto selezionato")
        self.loan_info_var.set("—")

    def _refresh_loans(self):
        tree = self.loans_tree
        for item in tree.get_children():
            tree.delete(item)
        self.loan_rows.clear()
        if not self.current_id:
            return
        try:
            rows = list_loans(self.current_id)
        except Exception as exc:
            messagebox.showerror("Magazzino", f"Errore caricando i prestiti:\n{exc}")
            return
        for row in rows:
            loan_id_raw = row.get("id")
            if loan_id_raw is None:
                continue
            loan_id = int(loan_id_raw)
            self.loan_rows[loan_id] = row
            tree.insert(
                "",
                tk.END,
                iid=str(loan_id),
                values=(
                    self._format_loan_member(row),
                    row.get("matricola", ""),
                    iso_to_ddmmyyyy(row.get("data_prestito")),
                    iso_to_ddmmyyyy(row.get("data_reso")),
                    row.get("note", ""),
                ),
            )

    def _clear_loans(self):
        for item in self.loans_tree.get_children():
            self.loans_tree.delete(item)
        self.loan_rows.clear()

    def _format_loan_member(self, row: dict) -> str:
        nome = row.get("nome") or row.get("active_socio_nome") or ""
        cognome = row.get("cognome") or row.get("active_socio_cognome") or ""
        nominativo = f"{cognome} {nome}".strip()
        if not nominativo:
            nominativo = "Socio" if row.get("socio_id") else ""
        matricola = row.get("matricola") or row.get("active_socio_matricola") or ""
        if matricola:
            return f"{nominativo} (Mat. {matricola})" if nominativo else f"Mat. {matricola}"
        return nominativo

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def _collect_form_data(self) -> dict:
        return {
            "numero_inventario": self.numero_var.get().strip(),
            "marca": self.marca_var.get().strip(),
            "modello": self.modello_var.get().strip(),
            "descrizione": self.descrizione_text.get("1.0", tk.END).strip(),
            "note": self.note_text.get("1.0", tk.END).strip(),
        }

    def _new_item(self):
        self._clear_form()
        self._clear_loans()
        self.status_var.set("Nuovo oggetto")

    def _save_item(self):
        data = self._collect_form_data()
        try:
            if self.current_id:
                update_item(
                    self.current_id,
                    marca=data["marca"],
                    modello=data["modello"],
                    descrizione=data["descrizione"],
                    numero_inventario=data["numero_inventario"],
                    note=data["note"],
                )
                messagebox.showinfo("Magazzino", "Oggetto aggiornato")
            else:
                new_id = create_item(**data)
                self.current_id = new_id
                messagebox.showinfo("Magazzino", "Oggetto creato")
        except Exception as exc:
            messagebox.showerror("Magazzino", f"Errore nel salvataggio:\n{exc}")
            return
        self.refresh_list()

    def _delete_item(self):
        if not self.current_id:
            messagebox.showinfo("Magazzino", "Seleziona un oggetto da eliminare")
            return
        if not messagebox.askyesno("Conferma", "Eliminare l'oggetto selezionato?", icon="warning"):
            return
        try:
            delete_item(self.current_id)
            messagebox.showinfo("Magazzino", "Oggetto eliminato")
        except Exception as exc:
            messagebox.showerror("Magazzino", f"Errore nell'eliminazione:\n{exc}")
            return
        self.refresh_list()

    # ------------------------------------------------------------------
    # Loan handling
    # ------------------------------------------------------------------
    def _new_loan(self):
        if not self.current_id:
            messagebox.showinfo("Magazzino", "Seleziona un oggetto prima di registrare un prestito")
            return
        dialog = LoanDialog(self, title="Nuovo prestito")
        if not dialog.result:
            return
        try:
            create_loan(
                self.current_id,
                socio_id=dialog.result["socio_id"],
                data_prestito=dialog.result["data_prestito"],
                note=dialog.result.get("note"),
            )
            messagebox.showinfo("Magazzino", "Prestito registrato")
        except Exception as exc:
            messagebox.showerror("Magazzino", f"Errore nel prestito:\n{exc}")
            return
        self.refresh_list()

    def _register_return(self):
        loan = self._selected_loan()
        if not loan:
            messagebox.showinfo("Magazzino", "Seleziona un prestito da chiudere")
            return
        if loan.get("data_reso"):
            messagebox.showinfo("Magazzino", "Il prestito risulta già chiuso")
            return
        dialog = ReturnDialog(self, title="Registra reso")
        if dialog.result is None:
            return
        try:
            register_return(int(loan["id"]), data_reso=dialog.result)
            messagebox.showinfo("Magazzino", "Reso registrato")
        except Exception as exc:
            messagebox.showerror("Magazzino", f"Errore nel reso:\n{exc}")
            return
        self.refresh_list()

    def _selected_loan(self) -> dict | None:
        selection = self.loans_tree.selection()
        if not selection:
            return None
        loan_id = int(selection[0])
        return self.loan_rows.get(loan_id)


class LoanDialog(simpledialog.Dialog):
    def __init__(self, parent, *, title: str):
        self.result: dict | None = None
        self.socio_id: int | None = None
        self.socio_label = tk.StringVar(value="Nessun socio selezionato")
        self.date_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        super().__init__(parent, title=title)

    def body(self, master):
        ttk.Label(master, text="Socio").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(master, textvariable=self.socio_label, foreground="#444").grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Button(master, text="Seleziona", command=self._pick_member).grid(row=0, column=2, sticky="w", padx=4, pady=2)

        ttk.Label(master, text="Data prestito (gg/mm/aaaa)").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(master, textvariable=self.date_var, width=16).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(master, text="Note").grid(row=2, column=0, sticky="nw", padx=4, pady=2)
        self.note_text = tk.Text(master, height=4, width=40, wrap=tk.WORD)
        self.note_text.grid(row=2, column=1, columnspan=2, sticky="ew", padx=4, pady=2)
        master.columnconfigure(1, weight=1)
        return master

    def _pick_member(self):
        dialog = MemberPickerDialog(self)
        if dialog.result:
            self.socio_id = dialog.result["id"]
            self.socio_label.set(dialog.result["label"])

    def validate(self):
        if not self.socio_id:
            messagebox.showwarning("Magazzino", "Seleziona un socio")
            return False
        return True

    def apply(self):
        self.result = {
            "socio_id": self.socio_id,
            "data_prestito": self.date_var.get().strip(),
            "note": self.note_text.get("1.0", tk.END).strip() or None,
        }


class ReturnDialog(simpledialog.Dialog):
    def __init__(self, parent, *, title: str):
        self.date_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self.result: str | None = None
        super().__init__(parent, title=title)

    def body(self, master):
        ttk.Label(master, text="Data reso (gg/mm/aaaa)").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(master, textvariable=self.date_var, width=18).grid(row=0, column=1, sticky="w", padx=4, pady=4)
        return master

    def apply(self):
        self.result = self.date_var.get().strip()


class MemberPickerDialog(simpledialog.Dialog):
    def __init__(self, parent):
        self.result: dict | None = None
        self.members: list[dict] = []
        self.search_var = tk.StringVar()
        super().__init__(parent, title="Seleziona socio")

    def body(self, master):
        ttk.Label(master, text="Cerca").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        entry = ttk.Entry(master, textvariable=self.search_var)
        entry.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        entry.bind("<KeyRelease>", lambda _e: self._apply_filter())

        columns = ("matricola", "nome", "cognome")
        self.tree = ttk.Treeview(master, columns=columns, show="headings", height=10, selectmode="browse")
        self.tree.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.tree.heading("matricola", text="Matricola")
        self.tree.heading("nome", text="Nome")
        self.tree.heading("cognome", text="Cognome")
        widths = {"matricola": 90, "nome": 160, "cognome": 180}
        for col in columns:
            self.tree.column(col, width=widths[col], anchor="w" if col != "matricola" else "center")
        self.tree.bind("<Double-1>", lambda _e: self.ok())

        master.columnconfigure(1, weight=1)
        master.rowconfigure(1, weight=1)
        self._load_members()
        self._apply_filter()
        return entry

    def _load_members(self):
        try:
            rows = fetch_all(
                "SELECT id, matricola, nome, cognome FROM soci WHERE deleted_at IS NULL ORDER BY cognome, nome"
            )
        except Exception as exc:
            messagebox.showerror("Magazzino", f"Errore caricando i soci:\n{exc}")
            rows = []
        self.members = [dict(row) for row in rows]

    def _apply_filter(self):
        query = self.search_var.get().strip().lower()
        tree = self.tree
        for item in tree.get_children():
            tree.delete(item)
        for row in self.members:
            testo = " ".join(
                [
                    str(row.get("matricola") or ""),
                    str(row.get("nome") or ""),
                    str(row.get("cognome") or ""),
                ]
            ).lower()
            if query and query not in testo:
                continue
            tree.insert(
                "",
                tk.END,
                iid=str(row["id"]),
                values=(row.get("matricola", ""), row.get("nome", ""), row.get("cognome", "")),
            )

    def validate(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Magazzino", "Seleziona un socio dalla lista")
            return False
        return True

    def apply(self):
        sel = self.tree.selection()
        if not sel:
            self.result = None
            return
        socio_id = int(sel[0])
        row = next((m for m in self.members if m["id"] == socio_id), None)
        if not row:
            self.result = None
            return
        label = f"{row.get('cognome', '')} {row.get('nome', '')}".strip()
        matricola = row.get("matricola")
        if matricola:
            label = f"{label} (Mat. {matricola})" if label else f"Mat. {matricola}"
        self.result = {"id": socio_id, "label": label}
