# -*- coding: utf-8 -*-
"""Ponti (radio repeaters) management panel."""

from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, simpledialog, ttk

from utils import open_path

from .treeview_tags import CategoryTagStyler, SECTION_CATEGORY_PALETTE

from ponti_manager import (
    DEFAULT_REMINDER_DAYS,
    add_ponte_document,
    create_ponte,
    delete_authorization,
    delete_ponte,
    delete_ponte_document,
    get_ponte,
    list_authorizations,
    list_ponte_documents,
    list_ponti,
    save_authorization,
    update_ponte,
    update_ponte_document,
)

DUE_SOON_DAYS = 60
DEFAULT_STATES = ("ATTIVO", "MANUTENZIONE", "DISMESSO")
STATE_COLOR_TAGS = {
    "ATTIVO": ("state_attivo", "#e8f5e9"),
    "MANUTENZIONE": ("state_manutenzione", "#fff8e1"),
    "DISMESSO": ("state_dismesso", "#fdecea"),
}


class PontiPanel(ttk.Frame):
    """Interactive panel used inside the main notebook to manage ponti."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.current_id: int | None = None
        self.ponte_rows: list[dict] = []
        self.auth_rows: dict[int, dict] = {}
        self.doc_rows: dict[int, dict] = {}
        self.search_var = tk.StringVar()
        self.state_filter_var = tk.StringVar(value="Tutti")
        self.status_var = tk.StringVar(value="Nessun ponte selezionato")
        self.next_due_var = tk.StringVar(value="—")
        self._build_ui()
        self.refresh_list()

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------
    def _build_ui(self):
        self._build_toolbar()
        self._build_tree()
        self._build_detail_form()
        self._build_authorizations_block()
        self._build_documents_block()

    def _build_toolbar(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text="Nuovo ponte", command=self._new_ponte).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Salva", command=self._save_ponte).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Elimina", command=self._delete_ponte).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Aggiorna", command=lambda: self.refresh_list(keep_selection=False)).pack(side=tk.LEFT, padx=(12, 2))

        ttk.Label(toolbar, text="Filtro stato:").pack(side=tk.LEFT, padx=(18, 4))
        self.state_combo = ttk.Combobox(
            toolbar,
            textvariable=self.state_filter_var,
            values=("Tutti",) + DEFAULT_STATES,
            width=16,
            state="readonly",
        )
        self.state_combo.pack(side=tk.LEFT)
        self.state_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_list())

        ttk.Label(toolbar, text="Cerca:").pack(side=tk.LEFT, padx=(18, 4))
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=28)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<Return>", lambda _e: self.refresh_list())
        ttk.Button(toolbar, text="Applica", command=self.refresh_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Reset", command=self._reset_filters).pack(side=tk.LEFT, padx=2)

    def _build_tree(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=(0, 5))

        columns = ("nome", "nominativo", "localita", "stato", "scadenza")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=6, selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.X, expand=True)

        headings = {
            "nome": "Nome",
            "nominativo": "Nominativo",
            "localita": "Località",
            "stato": "Stato",
            "scadenza": "Prossima scadenza",
        }
        widths = {
            "nome": 200,
            "nominativo": 140,
            "localita": 180,
            "stato": 120,
            "scadenza": 150,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            anchor = "center" if col in {"stato", "scadenza"} else "w"
            self.tree.column(col, width=widths[col], anchor=anchor, stretch=True)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        for _state, (tag_name, color) in STATE_COLOR_TAGS.items():
            self.tree.tag_configure(tag_name, background=color)
        self.tree.tag_configure("due_soon", background="#fff4ce")
        self.tree.tag_configure("expired", background="#ffe0e0")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._load_selected())

    def _build_detail_form(self):
        form = ttk.LabelFrame(self, text="Dettaglio ponte")
        form.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.nome_var = tk.StringVar()
        self.nominativo_var = tk.StringVar()
        self.localita_var = tk.StringVar()
        self.stato_var = tk.StringVar(value=DEFAULT_STATES[0])

        ttk.Label(form, text="Nome *").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.nome_var, width=32).grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(form, text="Nominativo").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.nominativo_var, width=20).grid(row=0, column=3, sticky="ew", padx=4, pady=2)

        ttk.Label(form, text="Località").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.localita_var, width=32).grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(form, text="Stato").grid(row=1, column=2, sticky="w", padx=4, pady=2)
        self.stato_combo = ttk.Combobox(form, textvariable=self.stato_var, values=DEFAULT_STATES, width=18, state="readonly")
        self.stato_combo.grid(row=1, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(form, text="Note").grid(row=2, column=0, sticky="nw", padx=4, pady=2)
        self.note_text = tk.Text(form, height=3, width=80, wrap=tk.WORD)
        self.note_text.grid(row=2, column=1, columnspan=3, sticky="ew", padx=4, pady=2)

        ttk.Label(form, text="Prossima scadenza autorizzazione:").grid(row=3, column=0, sticky="w", padx=4, pady=(6, 2))
        ttk.Label(form, textvariable=self.next_due_var, foreground="#b35a00").grid(row=3, column=1, sticky="w", padx=4, pady=(6, 2))
        ttk.Label(form, textvariable=self.status_var).grid(row=3, column=2, columnspan=2, sticky="e", padx=4, pady=(6, 2))

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

    def _build_authorizations_block(self):
        frame = ttk.LabelFrame(self, text="Autorizzazioni e promemoria")
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=4, pady=(4, 0))
        ttk.Button(btn_frame, text="Aggiungi", command=self._add_authorization).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Modifica", command=self._edit_authorization).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Elimina", command=self._delete_authorization).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Apri documento", command=self._open_authorization_document).pack(side=tk.LEFT, padx=(12, 2))

        columns = (
            "tipo",
            "ente",
            "numero",
            "rilascio",
            "scadenza",
            "reminder",
            "note",
            "documento",
        )
        self.auth_tree = ttk.Treeview(frame, columns=columns, show="headings", height=5, selectmode="browse")
        self.auth_tree.pack(fill=tk.X, padx=4, pady=4)
        self.auth_tree.bind("<<TreeviewSelect>>", lambda _e: None)

        headings = {
            "tipo": "Tipo",
            "ente": "Ente",
            "numero": "Numero",
            "rilascio": "Rilascio",
            "scadenza": "Scadenza",
            "reminder": "Promemoria",
            "note": "Note",
            "documento": "Documento",
        }
        widths = {
            "tipo": 120,
            "ente": 140,
            "numero": 110,
            "rilascio": 100,
            "scadenza": 110,
            "reminder": 110,
            "note": 200,
            "documento": 200,
        }
        for col in columns:
            self.auth_tree.heading(col, text=headings[col])
            anchor = "center" if col in {"rilascio", "scadenza", "reminder"} else "w"
            self.auth_tree.column(col, width=widths[col], anchor=anchor)

    def _build_documents_block(self):
        frame = ttk.LabelFrame(self, text="Documenti allegati")
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=4, pady=(4, 0))
        ttk.Button(btn_frame, text="Aggiungi", command=self._add_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Modifica", command=self._edit_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Elimina", command=self._delete_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Apri file", command=self._open_document).pack(side=tk.LEFT, padx=(12, 2))
        ttk.Button(btn_frame, text="Apri cartella", command=self._open_document_folder).pack(side=tk.LEFT, padx=2)

        columns = ("tipo", "note", "percorso")
        self.docs_tree = ttk.Treeview(frame, columns=columns, show="headings", height=4, selectmode="browse")
        self.docs_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.docs_tree.heading("tipo", text="Tipo")
        self.docs_tree.heading("note", text="Note")
        self.docs_tree.heading("percorso", text="Percorso")
        self.docs_tree.column("tipo", width=120)
        self.docs_tree.column("note", width=240)
        self.docs_tree.column("percorso", width=360)

        self._doc_type_tags = CategoryTagStyler(
            self.docs_tree,
            default_label="Altro",
            palette=SECTION_CATEGORY_PALETTE,
            tag_prefix="ponte_doc::",
        )

    # ------------------------------------------------------------------
    # Data handling
    # ------------------------------------------------------------------
    def refresh_list(self, *, keep_selection: bool = True):
        try:
            rows = list_ponti()
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore nel caricamento elenco:\n{exc}")
            return

        search = self.search_var.get().strip().lower()
        state_filter = self.state_filter_var.get().strip().upper()
        filtered: list[dict] = []
        for row in rows:
            testo = " ".join(
                [
                    str(row.get("nome") or ""),
                    str(row.get("nominativo") or ""),
                    str(row.get("qth") or ""),
                    str(row.get("note_tecniche") or ""),
                ]
            ).lower()
            stato = (row.get("stato_corrente") or "").upper()
            if search and search not in testo:
                continue
            if state_filter and state_filter != "TUTTI" and stato != state_filter:
                continue
            filtered.append(row)

        tree = self.tree
        prev_selection = tree.selection()
        prev_id = prev_selection[0] if keep_selection and prev_selection else None
        for item in tree.get_children():
            tree.delete(item)

        now = datetime.now().date()
        soon = now + timedelta(days=DUE_SOON_DAYS)
        for row in filtered:
            iid = str(row.get("id"))
            scadenza_iso = row.get("next_scadenza")
            display_scadenza = format_iso_date(scadenza_iso) or "—"
            tags: list[str] = []
            stato_tag = STATE_COLOR_TAGS.get((row.get("stato_corrente") or "").upper())
            if stato_tag:
                tags.append(stato_tag[0])
            if scadenza_iso:
                try:
                    due_date = datetime.strptime(scadenza_iso, "%Y-%m-%d").date()
                    if due_date < now:
                        tags.append("expired")
                    elif due_date <= soon:
                        tags.append("due_soon")
                except ValueError:
                    pass
            tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    row.get("nome", ""),
                    row.get("nominativo", ""),
                    row.get("qth", ""),
                    row.get("stato_corrente", ""),
                    display_scadenza,
                ),
                tags=tags,
            )

        self.ponte_rows = filtered
        if prev_id and tree.exists(prev_id):
            tree.selection_set(prev_id)
            tree.focus(prev_id)
        elif filtered:
            first_id = str(filtered[0].get("id"))
            tree.selection_set(first_id)
            tree.focus(first_id)
        else:
            self._clear_detail()
            return
        self._load_selected()

    def _reset_filters(self):
        self.search_var.set("")
        self.state_filter_var.set("Tutti")
        self.refresh_list()

    def _load_selected(self):
        selection = self.tree.selection()
        if not selection:
            self._clear_detail()
            return
        ponte_id = int(selection[0])
        try:
            data = get_ponte(ponte_id)
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore caricando il ponte:\n{exc}")
            return
        if not data:
            self._clear_detail()
            return
        self.current_id = ponte_id
        self.nome_var.set(data.get("nome") or "")
        self.nominativo_var.set(data.get("nominativo") or "")
        self.localita_var.set(data.get("qth") or "")
        stato = (data.get("stato_corrente") or DEFAULT_STATES[0]).upper()
        self.stato_var.set(stato)
        self.note_text.delete("1.0", tk.END)
        self.note_text.insert("1.0", data.get("note_tecniche") or "")
        self.next_due_var.set(format_iso_date(data.get("next_scadenza")) or "—")
        self.status_var.set(f"Ponte #{ponte_id} selezionato")
        self._refresh_authorizations()
        self._refresh_documents()

    def _clear_detail(self):
        self.current_id = None
        self.nome_var.set("")
        self.nominativo_var.set("")
        self.localita_var.set("")
        self.stato_var.set(DEFAULT_STATES[0])
        self.note_text.delete("1.0", tk.END)
        self.next_due_var.set("—")
        self.status_var.set("Nessun ponte selezionato")
        for tree in (getattr(self, "auth_tree", None), getattr(self, "docs_tree", None)):
            if tree is None:
                continue
            for item in tree.get_children():
                tree.delete(item)
        self.auth_rows.clear()
        self.doc_rows.clear()

    def _collect_form_data(self) -> dict:
        return {
            "nome": self.nome_var.get().strip(),
            "nominativo": self.nominativo_var.get().strip() or None,
            "localita": self.localita_var.get().strip() or None,
            "stato": self.stato_var.get().strip() or DEFAULT_STATES[0],
            "note": self.note_text.get("1.0", tk.END).strip() or None,
        }

    def _new_ponte(self):
        self._clear_detail()
        self.status_var.set("Nuovo ponte — completa i campi e salva")

    def _save_ponte(self):
        data = self._collect_form_data()
        if not data["nome"]:
            messagebox.showwarning("Ponti", "Il nome del ponte è obbligatorio")
            return
        try:
            if self.current_id:
                update_ponte(
                    self.current_id,
                    nome=data["nome"],
                    nominativo=data["nominativo"],
                    localita=data["localita"],
                    stato=data["stato"],
                    note=data["note"],
                )
                messagebox.showinfo("Ponti", "Ponte aggiornato")
                target_id = self.current_id
            else:
                target_id = create_ponte(
                    nome=data["nome"],
                    nominativo=data["nominativo"],
                    localita=data["localita"],
                    stato=data["stato"],
                    note=data["note"],
                )
                messagebox.showinfo("Ponti", "Ponte creato")
            self.refresh_list(keep_selection=False)
            if target_id:
                self.tree.selection_set(str(target_id))
                self.tree.focus(str(target_id))
                self._load_selected()
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore nel salvataggio:\n{exc}")

    def _delete_ponte(self):
        if not self.current_id:
            messagebox.showinfo("Ponti", "Seleziona un ponte da eliminare")
            return
        if not messagebox.askyesno("Conferma", "Eliminare il ponte selezionato?", icon="warning"):
            return
        try:
            delete_ponte(self.current_id)
            self._clear_detail()
            self.refresh_list(keep_selection=False)
            messagebox.showinfo("Ponti", "Ponte eliminato")
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore nell'eliminazione:\n{exc}")

    # ------------------------------------------------------------------
    # Authorizations
    # ------------------------------------------------------------------
    def _refresh_authorizations(self):
        tree = self.auth_tree
        for item in tree.get_children():
            tree.delete(item)
        self.auth_rows.clear()
        if not self.current_id:
            return
        try:
            rows = list_authorizations(self.current_id)
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore caricando le autorizzazioni:\n{exc}")
            return
        for row in rows:
            auth_id = int(row.get("id"))
            self.auth_rows[auth_id] = row
            reminder_label = "—"
            if row.get("calendar_event_id"):
                days = row.get("reminder_days") or DEFAULT_REMINDER_DAYS
                reminder_label = f"✓ {days}g prima"
            tree.insert(
                "",
                tk.END,
                iid=str(auth_id),
                values=(
                    row.get("tipo", ""),
                    row.get("ente", ""),
                    row.get("numero", ""),
                    format_iso_date(row.get("data_rilascio")) or "",
                    format_iso_date(row.get("data_scadenza")) or "",
                    reminder_label,
                    row.get("note", ""),
                    row.get("documento_path", ""),
                ),
            )

    def _selected_authorization(self) -> dict | None:
        selection = self.auth_tree.selection()
        if not selection:
            return None
        auth_id = int(selection[0])
        return self.auth_rows.get(auth_id)

    def _add_authorization(self):
        if not self.current_id:
            messagebox.showinfo("Ponti", "Seleziona un ponte prima di aggiungere un'autorizzazione")
            return
        dialog = PontiAuthorizationDialog(self, title="Nuova autorizzazione")
        if not dialog.result:
            return
        self._persist_authorization(dialog.result)

    def _edit_authorization(self):
        row = self._selected_authorization()
        if not row:
            messagebox.showinfo("Ponti", "Seleziona un'autorizzazione da modificare")
            return
        dialog = PontiAuthorizationDialog(self, title="Modifica autorizzazione", initial=row)
        if not dialog.result:
            return
        dialog.result["authorization_id"] = int(row["id"])
        self._persist_authorization(dialog.result)

    def _persist_authorization(self, payload: dict):
        if not self.current_id:
            return
        try:
            save_authorization(self.current_id, **payload)
            self._refresh_authorizations()
            self.refresh_list()
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore salvando l'autorizzazione:\n{exc}")

    def _delete_authorization(self):
        row = self._selected_authorization()
        if not row:
            messagebox.showinfo("Ponti", "Seleziona un'autorizzazione da eliminare")
            return
        if not messagebox.askyesno("Conferma", "Eliminare l'autorizzazione selezionata?", icon="warning"):
            return
        try:
            delete_authorization(int(row["id"]))
            self._refresh_authorizations()
            self.refresh_list()
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore eliminando l'autorizzazione:\n{exc}")

    def _open_authorization_document(self):
        row = self._selected_authorization()
        if not row:
            messagebox.showinfo("Ponti", "Seleziona un'autorizzazione")
            return
        path = (row.get("documento_path") or "").strip()
        if not path:
            messagebox.showinfo("Ponti", "Nessun documento associato")
            return
        open_path(path, on_error=lambda msg: messagebox.showerror("Documenti", msg))

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------
    def _refresh_documents(self):
        tree = self.docs_tree
        for item in tree.get_children():
            tree.delete(item)
        self.doc_rows.clear()
        if not self.current_id:
            return
        try:
            rows = list_ponte_documents(self.current_id)
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore caricando i documenti:\n{exc}")
            return
        for row in rows:
            doc_id = int(row.get("id"))
            self.doc_rows[doc_id] = row
            tipo = str(row.get("tipo") or "").strip()
            tag_manager = getattr(self, "_doc_type_tags", None)
            tags = (tag_manager.tag_for(tipo),) if tag_manager is not None else ()
            tree.insert(
                "",
                tk.END,
                iid=str(doc_id),
                values=(row.get("tipo", ""), row.get("note", ""), row.get("document_path", "")),
                tags=tags,
            )

    def _selected_document(self) -> dict | None:
        selection = self.docs_tree.selection()
        if not selection:
            return None
        doc_id = int(selection[0])
        return self.doc_rows.get(doc_id)

    def _add_document(self):
        if not self.current_id:
            messagebox.showinfo("Ponti", "Seleziona un ponte prima di allegare un documento")
            return
        dialog = PontiDocumentDialog(self, title="Nuovo documento", allow_path_edit=True)
        if not dialog.result:
            return
        path = dialog.result.get("document_path")
        if not path:
            messagebox.showwarning("Ponti", "Il percorso del documento è obbligatorio")
            return
        try:
            add_ponte_document(
                self.current_id,
                path,
                tipo=dialog.result.get("tipo"),
                note=dialog.result.get("note"),
            )
            self._refresh_documents()
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore aggiungendo il documento:\n{exc}")

    def _edit_document(self):
        row = self._selected_document()
        if not row:
            messagebox.showinfo("Ponti", "Seleziona un documento da modificare")
            return
        dialog = PontiDocumentDialog(self, title="Modifica documento", initial=row, allow_path_edit=False)
        if not dialog.result:
            return
        try:
            update_ponte_document(
                int(row["id"]),
                tipo=dialog.result.get("tipo"),
                note=dialog.result.get("note"),
            )
            self._refresh_documents()
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore aggiornando il documento:\n{exc}")

    def _delete_document(self):
        row = self._selected_document()
        if not row:
            messagebox.showinfo("Ponti", "Seleziona un documento da eliminare")
            return
        if not messagebox.askyesno("Conferma", "Eliminare il documento selezionato?", icon="warning"):
            return
        try:
            delete_ponte_document(int(row["id"]))
            self._refresh_documents()
        except Exception as exc:
            messagebox.showerror("Ponti", f"Errore eliminando il documento:\n{exc}")

    def _open_document(self):
        row = self._selected_document()
        if not row:
            messagebox.showinfo("Ponti", "Seleziona un documento da aprire")
            return
        path = row.get("document_path")
        if not path:
            messagebox.showinfo("Ponti", "Percorso mancante")
            return
        open_path(path, on_error=lambda msg: messagebox.showerror("Documenti", msg))

    def _open_document_folder(self):
        row = self._selected_document()
        if not row:
            messagebox.showinfo("Ponti", "Seleziona un documento")
            return
        path = row.get("document_path")
        if not path:
            messagebox.showinfo("Ponti", "Percorso mancante")
            return
        folder = os.path.dirname(path) or path
        open_path(
            folder,
            select_target=path if os.path.isfile(path) else None,
            on_error=lambda msg: messagebox.showerror("Documenti", msg),
        )


class PontiAuthorizationDialog(simpledialog.Dialog):
    """Dialog used to add or edit an authorization entry."""

    def __init__(self, parent, *, title: str, initial: dict | None = None):
        self.initial = initial or {}
        self.result: dict | None = None
        super().__init__(parent, title=title)

    def body(self, master):
        self.tipo_var = tk.StringVar(value=self.initial.get("tipo", ""))
        self.ente_var = tk.StringVar(value=self.initial.get("ente", ""))
        self.numero_var = tk.StringVar(value=self.initial.get("numero", ""))
        self.rilascio_var = tk.StringVar(value=format_iso_date(self.initial.get("data_rilascio")) or "")
        self.scadenza_var = tk.StringVar(value=format_iso_date(self.initial.get("data_scadenza")) or "")
        self.doc_path_var = tk.StringVar(value=self.initial.get("documento_path", ""))
        reminder_default = bool(self.initial.get("calendar_event_id") and self.initial.get("data_scadenza"))
        self.reminder_var = tk.BooleanVar(value=reminder_default or not bool(self.initial))
        self.reminder_days_var = tk.IntVar(value=self.initial.get("reminder_days") or DEFAULT_REMINDER_DAYS)

        ttk.Label(master, text="Tipo *").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(master, textvariable=self.tipo_var, width=28).grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(master, text="Ente").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        ttk.Entry(master, textvariable=self.ente_var, width=22).grid(row=0, column=3, sticky="ew", padx=4, pady=2)

        ttk.Label(master, text="Numero").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(master, textvariable=self.numero_var, width=28).grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(master, text="Data rilascio (gg/mm/aaaa)").grid(row=1, column=2, sticky="w", padx=4, pady=2)
        ttk.Entry(master, textvariable=self.rilascio_var, width=22).grid(row=1, column=3, sticky="ew", padx=4, pady=2)

        ttk.Label(master, text="Data scadenza (gg/mm/aaaa)").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(master, textvariable=self.scadenza_var, width=28).grid(row=2, column=1, sticky="ew", padx=4, pady=2)

        reminder_frame = ttk.Frame(master)
        reminder_frame.grid(row=2, column=2, columnspan=2, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(reminder_frame, text="Promemoria", variable=self.reminder_var).pack(side=tk.LEFT)
        ttk.Label(reminder_frame, text="giorni prima:").pack(side=tk.LEFT, padx=(6, 2))
        ttk.Spinbox(reminder_frame, from_=1, to=180, width=5, textvariable=self.reminder_days_var).pack(side=tk.LEFT)

        ttk.Label(master, text="Documento").grid(row=3, column=0, sticky="w", padx=4, pady=2)
        doc_entry = ttk.Entry(master, textvariable=self.doc_path_var)
        doc_entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=4, pady=2)
        ttk.Button(master, text="Sfoglia", command=self._browse_document).grid(row=3, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(master, text="Note").grid(row=4, column=0, sticky="nw", padx=4, pady=2)
        self.note_text = tk.Text(master, height=4, width=60, wrap=tk.WORD)
        self.note_text.grid(row=4, column=1, columnspan=3, sticky="ew", padx=4, pady=2)
        self.note_text.insert("1.0", self.initial.get("note", ""))

        master.columnconfigure(1, weight=1)
        master.columnconfigure(3, weight=1)
        return doc_entry

    def _browse_document(self):
        path = filedialog.askopenfilename(parent=self, title="Seleziona documento")
        if path:
            self.doc_path_var.set(path)

    def validate(self):
        if not self.tipo_var.get().strip():
            messagebox.showwarning("Ponti", "Il tipo è obbligatorio")
            return False
        if self.reminder_var.get() and not self.scadenza_var.get().strip():
            messagebox.showwarning("Ponti", "Per attivare il promemoria serve la data di scadenza")
            return False
        return True

    def apply(self):
        self.result = {
            "tipo": self.tipo_var.get().strip(),
            "ente": self.ente_var.get().strip() or None,
            "numero": self.numero_var.get().strip() or None,
            "data_rilascio": self.rilascio_var.get().strip() or None,
            "data_scadenza": self.scadenza_var.get().strip() or None,
            "documento_path": self.doc_path_var.get().strip() or None,
            "note": self.note_text.get("1.0", tk.END).strip() or None,
            "reminder_days": self.reminder_days_var.get() or DEFAULT_REMINDER_DAYS,
            "enable_reminder": bool(self.reminder_var.get()),
        }


class PontiDocumentDialog(simpledialog.Dialog):
    """Dialog to add or edit a ponte document."""

    def __init__(self, parent, *, title: str, initial: dict | None = None, allow_path_edit: bool = True):
        self.initial = initial or {}
        self.allow_path_edit = allow_path_edit
        self.result: dict | None = None
        super().__init__(parent, title=title)

    def body(self, master):
        self.tipo_var = tk.StringVar(value=self.initial.get("tipo", ""))
        self.note_var = tk.StringVar(value=self.initial.get("note", ""))
        self.path_var = tk.StringVar(value=self.initial.get("document_path") or self.initial.get("percorso", ""))

        ttk.Label(master, text="Tipo").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(master, textvariable=self.tipo_var, width=30).grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(master, text="Note").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(master, textvariable=self.note_var, width=30).grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(master, text="Percorso").grid(row=2, column=0, sticky="w", padx=4, pady=2)
        self.path_entry = ttk.Entry(master, textvariable=self.path_var, state="normal" if self.allow_path_edit else "disabled")
        self.path_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=2)
        btn = ttk.Button(master, text="Sfoglia", command=self._browse_path, state="normal" if self.allow_path_edit else "disabled")
        btn.grid(row=2, column=2, sticky="w", padx=4, pady=2)
        ttk.Label(
            master,
            text="Il file selezionato verrà copiato nell'archivio ponti.",
            foreground="gray40",
        ).grid(row=3, column=1, columnspan=2, sticky="w", padx=4, pady=(0, 6))

        master.columnconfigure(1, weight=1)
        return self.path_entry

    def _browse_path(self):
        path = filedialog.askopenfilename(parent=self, title="Seleziona documento")
        if path:
            self.path_var.set(path)

    def validate(self):
        if self.allow_path_edit and not self.path_var.get().strip():
            messagebox.showwarning("Ponti", "Il percorso è obbligatorio")
            return False
        return True

    def apply(self):
        self.result = {
            "tipo": self.tipo_var.get().strip() or None,
            "note": self.note_var.get().strip() or None,
            "document_path": self.path_var.get().strip() or None,
        }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def format_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return value


