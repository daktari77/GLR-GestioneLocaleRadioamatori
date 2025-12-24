# -*- coding: utf-8 -*-
"""
Panel components for Libro Soci
Handles documents, section info, events, etc.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import logging
import os
import subprocess
import sys
import csv

from documents_catalog import DOCUMENT_CATEGORIES, DEFAULT_DOCUMENT_CATEGORY
from .document_metadata_prompt import ask_document_metadata
from section_documents import (
    SECTION_DOCUMENT_CATEGORIES,
    add_section_document,
    delete_section_document,
    ensure_section_index_file,
    human_readable_mtime,
    human_readable_size,
    list_section_documents,
    update_section_document_metadata,
)

logger = logging.getLogger("librosoci")

class DocumentPanel(ttk.Frame):
    """Panel for managing member documents"""
    
    def __init__(self, parent, socio_id=None, show_all_documents: bool = False, **kwargs):
        super().__init__(parent, **kwargs)
        self.socio_id = socio_id
        self.show_all_documents = show_all_documents
        self.documents: dict[int, dict] = {}
        self.member_filter_map: dict[str, int | None] = {"Tutti i soci": None}
        self.active_member_filter_id: int | None = None
        self.pending_member_filter: int | None = None
        self.category_filter_default = "Tutte le categorie"
        self.member_filter_var = tk.StringVar(value="Tutti i soci")
        self.category_filter_var = tk.StringVar(value=self.category_filter_default)
        self.search_var = tk.StringVar()
        default_message = (
            "Visualizzazione di tutti i documenti caricati."
            if self.show_all_documents
            else "Seleziona un socio per gestire i documenti."
        )
        self.info_var = tk.StringVar(value=default_message)
        self._build_filters()
        self._build_ui()
        self._update_toolbar_states()
        self.refresh()
    
    def _build_filters(self):
        """Create the filter bar for socio/category/search."""
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        ttk.Label(filter_frame, text="Socio:").pack(side=tk.LEFT, padx=(0, 4))
        self.member_filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.member_filter_var,
            state="readonly",
            width=28,
            values=list(self.member_filter_map.keys()),
        )
        self.member_filter_combo.pack(side=tk.LEFT, padx=2)
        self.member_filter_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

        ttk.Label(filter_frame, text="Categoria:").pack(side=tk.LEFT, padx=(12, 4))
        category_values = (self.category_filter_default,) + tuple(DOCUMENT_CATEGORIES)
        self.category_filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.category_filter_var,
            values=category_values,
            state="readonly",
            width=22,
        )
        self.category_filter_combo.pack(side=tk.LEFT, padx=2)
        self.category_filter_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_filters())

        ttk.Label(filter_frame, text="Cerca:").pack(side=tk.LEFT, padx=(12, 4))
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=22)
        search_entry.pack(side=tk.LEFT, padx=2)
        search_entry.bind("<Return>", lambda _e: self._apply_filters())
        ttk.Button(filter_frame, text="Applica", command=self._apply_filters).pack(side=tk.LEFT, padx=(8, 2))
        ttk.Button(filter_frame, text="Reset", command=self._reset_filters).pack(side=tk.LEFT, padx=2)

    def _build_ui(self):
        """Build document panel UI"""
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        self.btn_open = ttk.Button(toolbar, text="Apri", command=self._open_document)
        self.btn_open.pack(side=tk.LEFT, padx=2)
        self.btn_open_folder = ttk.Button(toolbar, text="Apri percorso", command=self._open_document_location)
        self.btn_open_folder.pack(side=tk.LEFT, padx=2)
        self.btn_delete = ttk.Button(toolbar, text="Elimina", command=self._delete_document)
        self.btn_delete.pack(side=tk.LEFT, padx=2)
        self.btn_edit = ttk.Button(toolbar, text="Modifica", command=self._edit_document)
        self.btn_edit.pack(side=tk.LEFT, padx=2)
        self.btn_bulk_delete = ttk.Button(toolbar, text="Elimina selezionati", command=self._delete_selected_documents)
        self.btn_bulk_delete.pack(side=tk.LEFT, padx=(12, 2))
        self.btn_bulk_category = ttk.Button(toolbar, text="Imposta categoria", command=self._bulk_update_category)
        self.btn_bulk_category.pack(side=tk.LEFT, padx=2)
        self.btn_export = ttk.Button(toolbar, text="Esporta CSV", command=self._export_selected_documents)
        self.btn_export.pack(side=tk.LEFT, padx=2)

        member_toolbar = ttk.Frame(self)
        member_toolbar.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Label(member_toolbar, text="Azioni socio selezionato:").pack(side=tk.LEFT, padx=(0, 6))
        self.btn_add = ttk.Button(member_toolbar, text="Aggiungi documento", command=self._add_document)
        self.btn_add.pack(side=tk.LEFT, padx=2)
        self.btn_privacy = ttk.Button(member_toolbar, text="Carica privacy", command=self._upload_privacy)
        self.btn_privacy.pack(side=tk.LEFT, padx=2)
        self.btn_member_folder = ttk.Button(member_toolbar, text="Apri cartella socio", command=self._open_member_folder)
        self.btn_member_folder.pack(side=tk.LEFT, padx=2)

        ttk.Label(member_toolbar, text="Categoria: ").pack(side=tk.LEFT, padx=(20, 2))
        self.category_var = tk.StringVar(value=DEFAULT_DOCUMENT_CATEGORY)
        self.category_combo = ttk.Combobox(
            member_toolbar,
            textvariable=self.category_var,
            values=DOCUMENT_CATEGORIES,
            state="readonly",
            width=24
        )
        self.category_combo.pack(side=tk.LEFT, padx=2)
        self.btn_update_category = ttk.Button(member_toolbar, text="Aggiorna categoria", command=self._update_document_category)
        self.btn_update_category.pack(side=tk.LEFT, padx=4)

        info_label = ttk.Label(self, textvariable=self.info_var, foreground="gray40")
        info_label.pack(fill=tk.X, padx=5)
        
        # Document list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tv_docs = ttk.Treeview(
            list_frame,
            columns=("id", "socio", "descrizione", "categoria", "tipo", "nome", "data", "info"),
            show="headings",
            yscrollcommand=scrollbar.set,
            height=11,
            selectmode="extended",
        )
        scrollbar.config(command=self.tv_docs.yview)
        self.tv_docs.tag_configure("missing", foreground="#b00020")
        
        self.tv_docs.heading("id", text="ID")
        self.tv_docs.heading("socio", text="Socio")
        self.tv_docs.heading("descrizione", text="Descrizione")
        self.tv_docs.heading("categoria", text="Categoria")
        self.tv_docs.heading("tipo", text="Tipo")
        self.tv_docs.heading("nome", text="Nome File")
        self.tv_docs.heading("data", text="Data")
        self.tv_docs.heading("info", text="Informazioni file")

        self.tv_docs.column("id", width=55, anchor="center")
        self.tv_docs.column("socio", width=200)
        self.tv_docs.column("descrizione", width=220)
        self.tv_docs.column("categoria", width=150)
        self.tv_docs.column("tipo", width=90, anchor="center")
        self.tv_docs.column("nome", width=240)
        self.tv_docs.column("data", width=120, anchor="center")
        self.tv_docs.column("info", width=210)
        
        self.tv_docs.pack(fill=tk.BOTH, expand=True)
        self.tv_docs.bind("<<TreeviewSelect>>", self._on_tree_selection_changed)
        self.tv_docs.bind("<Double-1>", lambda _e: self._open_document())
    
    def set_socio(self, socio_id: int):
        """Set the current socio and refresh documents"""
        self.socio_id = socio_id
        if self.show_all_documents:
            self.pending_member_filter = socio_id
        self.refresh()
    
    def refresh(self):
        """Refresh document list from database"""
        # Clear treeview
        for item in self.tv_docs.get_children():
            self.tv_docs.delete(item)
        self.documents.clear()

        try:
            from database import get_documenti, get_all_documenti_with_member_names
            from documents_manager import format_file_info

            if self.show_all_documents:
                rows = get_all_documenti_with_member_names()
            elif self.socio_id:
                rows = get_documenti(self.socio_id)
            else:
                self.info_var.set("Seleziona un socio per gestire i documenti.")
                self._update_toolbar_states()
                return

            total_docs = len(rows)
            self._update_member_filter_options(rows)
            for row in rows:
                doc = dict(row)
                doc_id = int(doc["id"])
                if doc.get("socio_id") is None and self.socio_id is not None:
                    doc["socio_id"] = int(self.socio_id)
                doc["socio_display"] = self._format_owner(doc)
                if not self._document_matches_filters(doc):
                    continue
                self.documents[doc_id] = doc
                info = format_file_info(doc.get("percorso") or "")
                description_value = doc.get("descrizione") or ""
                path_exists = os.path.exists(doc.get("percorso") or "")
                self.tv_docs.insert(
                    "",
                    tk.END,
                    iid=str(doc_id),
                    values=(
                        doc_id,
                        doc.get("socio_display", ""),
                        description_value,
                        doc.get("categoria", ""),
                        doc.get("tipo", ""),
                        doc.get("nome_file", ""),
                        (doc.get("data_caricamento", "") or "")[:10],
                        info,
                    ),
                    tags=("missing",) if not path_exists else (),
                )
            shown = len(self.documents)
            if self.show_all_documents:
                if shown:
                    self.info_var.set(f"{shown} documenti mostrati (su {total_docs} totali)")
                else:
                    self.info_var.set("Nessun documento corrisponde ai filtri.")
            else:
                self.info_var.set(f"{shown} documenti caricati")
        except Exception as exc:
            logger.error("Failed to load documents: %s", exc)
            self.info_var.set("Errore nel caricamento documenti")
        finally:
            self.category_var.set(DEFAULT_DOCUMENT_CATEGORY)
            self._update_toolbar_states()

    def _format_owner(self, doc: dict) -> str:
        nominativo = (doc.get("nominativo") or "").strip()
        if nominativo:
            return nominativo
        full_name = f"{(doc.get('nome') or '').strip()} {(doc.get('cognome') or '').strip()}".strip()
        if full_name:
            return full_name
        socio_id = doc.get("socio_id")
        if socio_id:
            return f"Socio #{socio_id}"
        return "—"

    def _resolve_doc_owner_id(self, doc: dict | None) -> int | None:
        if not doc:
            return None
        owner = doc.get("socio_id")
        if owner is not None:
            try:
                return int(owner)
            except (TypeError, ValueError):
                return None
        if self.socio_id is not None:
            try:
                return int(self.socio_id)
            except (TypeError, ValueError):
                return None
        return None

    def _current_target_member_id(self) -> int | None:
        if not self.show_all_documents:
            return self.socio_id
        if self.active_member_filter_id is not None:
            return self.active_member_filter_id
        if self.socio_id is not None:
            return self.socio_id
        return None

    def _apply_filters(self):
        self.active_member_filter_id = self._member_id_from_label(self.member_filter_var.get())
        self.refresh()

    def _reset_filters(self):
        self.member_filter_var.set("Tutti i soci")
        self.category_filter_var.set(self.category_filter_default)
        self.search_var.set("")
        self.active_member_filter_id = None
        self.refresh()

    def _update_member_filter_options(self, rows: list[dict]):
        if not self.show_all_documents:
            self.member_filter_combo.configure(state="disabled")
            return
        mapping: dict[str, int | None] = {"Tutti i soci": None}
        for doc in rows:
            socio_id = doc.get("socio_id")
            if socio_id is None:
                continue
            label = self._format_owner(doc)
            mapping[label] = int(socio_id)
        labels = sorted(label for label in mapping.keys() if label != "Tutti i soci")
        values = ["Tutti i soci"] + labels
        self.member_filter_map = {"Tutti i soci": None}
        for label in labels:
            self.member_filter_map[label] = mapping[label]
        self.member_filter_combo.configure(values=values, state="readonly" if values else "disabled")
        self._apply_pending_member_filter()
        if self.active_member_filter_id is None:
            self.member_filter_var.set("Tutti i soci")
        else:
            label = self._label_for_member_id(self.active_member_filter_id)
            if label:
                self.member_filter_var.set(label)

    def _apply_pending_member_filter(self):
        if self.pending_member_filter is None:
            return
        label = self._label_for_member_id(self.pending_member_filter)
        if label:
            self.member_filter_var.set(label)
            self.active_member_filter_id = self.pending_member_filter
        self.pending_member_filter = None

    def _member_id_from_label(self, label: str) -> int | None:
        if label in self.member_filter_map:
            return self.member_filter_map[label]
        return None

    def _label_for_member_id(self, socio_id: int | None) -> str | None:
        if socio_id is None:
            return None
        for label, value in self.member_filter_map.items():
            if value == socio_id:
                return label
        return None

    def _document_matches_filters(self, doc: dict) -> bool:
        member_filter = self.active_member_filter_id
        if member_filter is None and self.show_all_documents and self.pending_member_filter is not None:
            member_filter = self.pending_member_filter
        if member_filter is not None and int(doc.get("socio_id") or -1) != int(member_filter):
            return False
        category_filter = self.category_filter_var.get()
        if category_filter and category_filter != self.category_filter_default:
            if (doc.get("categoria") or DEFAULT_DOCUMENT_CATEGORY) != category_filter:
                return False
        search_text = self.search_var.get().strip().lower()
        if search_text:
            haystack = " ".join([
                doc.get("descrizione") or "",
                doc.get("nome_file") or "",
                doc.get("categoria") or "",
                doc.get("tipo") or "",
                doc.get("socio_display") or "",
            ]).lower()
            if search_text not in haystack:
                return False
        return True

    def _update_toolbar_states(self):
        has_selection = bool(self._selected_doc_ids())
        doc_state = "normal" if has_selection else "disabled"
        for widget in (
            getattr(self, "btn_open", None),
            getattr(self, "btn_open_folder", None),
            getattr(self, "btn_delete", None),
            getattr(self, "btn_edit", None),
            getattr(self, "btn_bulk_delete", None),
            getattr(self, "btn_bulk_category", None),
            getattr(self, "btn_export", None),
            getattr(self, "btn_update_category", None),
        ):
            if widget is not None:
                try:
                    widget.configure(state=doc_state)
                except tk.TclError:
                    pass

        member_available = self._current_target_member_id() is not None
        member_state = "normal" if member_available else "disabled"
        for widget in (
            getattr(self, "btn_add", None),
            getattr(self, "btn_privacy", None),
            getattr(self, "btn_member_folder", None),
        ):
            if widget is not None:
                try:
                    widget.configure(state=member_state)
                except tk.TclError:
                    pass

        if getattr(self, "category_combo", None) is not None:
            try:
                combo_state = "readonly" if has_selection else "disabled"
                self.category_combo.configure(state=combo_state)
            except tk.TclError:
                pass

    def _ensure_socio_selected(self) -> bool:
        if self._current_target_member_id() is None:
            messagebox.showwarning(
                "Documenti",
                "Seleziona un socio dalla tab Soci oppure imposta un filtro socio prima di continuare",
            )
            return False
        return True

    def _current_socio_id(self) -> int:
        target = self._current_target_member_id()
        if target is None:
            raise ValueError("Socio non selezionato")
        return int(target)
    
    def _selected_doc_ids(self) -> list[int]:
        selection = self.tv_docs.selection()
        ids: list[int] = []
        for item in selection:
            try:
                ids.append(int(item))
            except ValueError:
                values = self.tv_docs.item(item, "values")
                if values:
                    try:
                        ids.append(int(values[0]))
                    except (TypeError, ValueError):
                        continue
        return ids

    def _selected_doc_id(self) -> int | None:
        ids = self._selected_doc_ids()
        return ids[0] if ids else None

    def _selected_doc(self) -> dict | None:
        doc_id = self._selected_doc_id()
        if doc_id is None:
            return None
        return self.documents.get(doc_id)

    def _selected_docs(self) -> list[dict]:
        docs: list[dict] = []
        for doc_id in self._selected_doc_ids():
            doc = self.documents.get(doc_id)
            if doc:
                docs.append(doc)
        return docs

    def _on_tree_selection_changed(self, _event=None):
        self._sync_category_from_selection()
        self._update_toolbar_states()

    def _sync_category_from_selection(self, _event=None):
        doc = self._selected_doc()
        if not doc:
            return
        current_category = doc.get("categoria") or DEFAULT_DOCUMENT_CATEGORY
        if current_category not in DOCUMENT_CATEGORIES:
            current_category = DEFAULT_DOCUMENT_CATEGORY
        self.category_var.set(current_category)

    def _add_document(self):
        """Add a new generic document using documents_manager utilities."""
        if not self._ensure_socio_selected():
            return
        socio_id = self._current_socio_id()

        file_path = filedialog.askopenfilename(
            parent=self,
            title="Seleziona documento",
            filetypes=[
                ("Tutti i file", "*.*"),
                ("PDF", "*.pdf"),
                ("Documenti Office", "*.doc;*.docx;*.xls;*.xlsx"),
                ("Immagini", "*.jpg;*.jpeg;*.png;*.gif"),
            ],
        )
        if not file_path:
            return
        metadata = ask_document_metadata(
            self,
            title="Dettagli documento",
            categories=DOCUMENT_CATEGORIES,
            default_category=DEFAULT_DOCUMENT_CATEGORY,
            initial_category=self.category_var.get(),
            initial_description="",
        )
        if not metadata:
            return
        categoria, descrizione = metadata
        self.category_var.set(categoria)

        from documents_manager import upload_document

        success, message = upload_document(socio_id, file_path, "documento", categoria, descrizione)
        if success:
            messagebox.showinfo("Documenti", message)
            self.refresh()
        else:
            messagebox.showerror("Documenti", message)

    def _prompt_category_choice(self) -> str | None:
        dialog = _CategoryChoiceDialog(self, DEFAULT_DOCUMENT_CATEGORY)
        return dialog.result

    def _upload_privacy(self):
        if not self._ensure_socio_selected():
            return
        socio_id = self._current_socio_id()

        file_path = filedialog.askopenfilename(
            parent=self,
            title="Seleziona modulo privacy",
            filetypes=[
                ("Tutti i file", "*.*"),
                ("PDF", "*.pdf"),
                ("Documenti Office", "*.doc;*.docx"),
                ("Immagini", "*.jpg;*.jpeg;*.png"),
            ],
        )
        if not file_path:
            return
        metadata = ask_document_metadata(
            self,
            title="Dettagli modulo privacy",
            categories=DOCUMENT_CATEGORIES,
            default_category=DEFAULT_DOCUMENT_CATEGORY,
            initial_category=self.category_var.get(),
            initial_description="",
        )
        if not metadata:
            return
        categoria, descrizione = metadata
        self.category_var.set(categoria)

        from documents_manager import upload_document
        from database import set_privacy_signed

        success, message = upload_document(socio_id, file_path, "privacy", categoria, descrizione)
        if success:
            set_privacy_signed(socio_id, True)
            messagebox.showinfo("Documenti", message + "\n✓ Modulo privacy marcato come firmato")
            self.refresh()
        else:
            messagebox.showerror("Documenti", message)

    def _update_document_category(self):
        doc = self._selected_doc()
        if not doc:
            messagebox.showwarning("Documenti", "Seleziona un documento da aggiornare")
            return

        categoria = self.category_var.get() or DEFAULT_DOCUMENT_CATEGORY
        from documents_manager import update_document_category

        success, message = update_document_category(int(doc["id"]), categoria)
        if success:
            messagebox.showinfo("Documenti", message)
            self.refresh()
        else:
            messagebox.showerror("Documenti", message)

    def _edit_document(self):
        doc = self._selected_doc()
        if not doc:
            messagebox.showwarning("Documenti", "Seleziona un documento da modificare")
            return
        metadata = ask_document_metadata(
            self,
            title="Modifica documento",
            categories=DOCUMENT_CATEGORIES,
            default_category=DEFAULT_DOCUMENT_CATEGORY,
            initial_category=doc.get("categoria") or DEFAULT_DOCUMENT_CATEGORY,
            initial_description=doc.get("descrizione") or "",
        )
        if not metadata:
            return
        new_category, new_description = metadata
        actions = []
        from documents_manager import update_document_category, update_document_description

        if new_category != (doc.get("categoria") or DEFAULT_DOCUMENT_CATEGORY):
            success, message = update_document_category(int(doc["id"]), new_category)
            if success:
                actions.append(message)
            else:
                messagebox.showerror("Documenti", message)
                return

        current_description = doc.get("descrizione") or ""
        if new_description != current_description:
            success, message = update_document_description(int(doc["id"]), new_description)
            if success:
                actions.append("Descrizione aggiornata")
            else:
                messagebox.showerror("Documenti", message)
                return

        if actions:
            messagebox.showinfo("Documenti", "\n".join(actions))
            self.refresh()
        else:
            messagebox.showinfo("Documenti", "Nessuna modifica applicata")

    def _open_document(self):
        doc = self._selected_doc()
        if not doc:
            messagebox.showinfo("Documenti", "Seleziona un documento da aprire")
            return

        path = doc.get("percorso") or ""
        if not path or not os.path.exists(path):
            messagebox.showerror("Documenti", "File non trovato sul disco")
            self.refresh()
            return

        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception as exc:
            messagebox.showerror("Documenti", f"Impossibile aprire il documento:\n{exc}")

    def _open_document_location(self):
        doc = self._selected_doc()
        if not doc:
            messagebox.showinfo("Documenti", "Seleziona un documento per aprire la cartella")
            return

        path = doc.get("percorso") or ""
        if not path:
            messagebox.showerror("Documenti", "Percorso del documento non disponibile")
            return

        folder = os.path.dirname(path) or os.path.dirname(os.path.abspath(path))
        if not folder:
            messagebox.showerror("Documenti", "Impossibile determinare la cartella del documento")
            return

        if not os.path.exists(path) and not os.path.isdir(folder):
            messagebox.showerror("Documenti", "File non trovato sul disco")
            return

        try:
            if os.name == "nt":
                if os.path.exists(path):
                    normalized = os.path.normpath(path)
                    cmd = f'explorer /select,"{normalized}"'
                    subprocess.run(cmd, check=False, shell=True)
                else:
                    os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                if os.path.exists(path):
                    subprocess.run(["open", "-R", path], check=False)
                else:
                    subprocess.run(["open", folder], check=False)
            else:
                subprocess.run(["xdg-open", folder], check=False)
        except Exception as exc:
            messagebox.showerror("Documenti", f"Impossibile aprire la cartella:\n{exc}")

    def _delete_document(self):
        doc = self._selected_doc()
        if not doc:
            messagebox.showwarning("Documenti", "Seleziona un documento da eliminare")
            return
        if not messagebox.askyesno("Conferma", "Eliminare il documento selezionato?"):
            return

        from documents_manager import delete_document

        socio_id = self._resolve_doc_owner_id(doc)
        if socio_id is None:
            messagebox.showerror("Documenti", "Impossibile determinare il socio proprietario del documento.")
            return
        success, message = delete_document(socio_id, int(doc["id"]))
        if success:
            messagebox.showinfo("Documenti", message)
            self.refresh()
        else:
            messagebox.showerror("Documenti", message)

    def _delete_selected_documents(self):
        docs = self._selected_docs()
        if not docs:
            messagebox.showwarning("Documenti", "Seleziona almeno un documento")
            return
        if not messagebox.askyesno(
            "Conferma",
            f"Eliminare {len(docs)} documenti selezionati?",
            icon="warning",
        ):
            return
        from documents_manager import delete_document

        errors: list[str] = []
        for doc in docs:
            socio_id = self._resolve_doc_owner_id(doc)
            if socio_id is None:
                errors.append(f"Documento {doc.get('id')} senza socio associato")
                continue
            success, message = delete_document(socio_id, int(doc["id"]))
            if not success:
                errors.append(message)
        if errors:
            messagebox.showerror("Documenti", "\n".join(errors))
        else:
            messagebox.showinfo("Documenti", "Documenti eliminati")
        self.refresh()

    def _bulk_update_category(self):
        docs = self._selected_docs()
        if not docs:
            messagebox.showwarning("Documenti", "Seleziona almeno un documento")
            return
        category = self._prompt_category_choice()
        if not category:
            return
        from documents_manager import update_document_category

        errors: list[str] = []
        for doc in docs:
            success, message = update_document_category(int(doc["id"]), category)
            if not success:
                errors.append(message)
        if errors:
            messagebox.showerror("Documenti", "\n".join(errors))
        else:
            messagebox.showinfo("Documenti", f"Categoria impostata su {category}")
        self.refresh()

    def _export_selected_documents(self):
        docs = self._selected_docs()
        if not docs:
            messagebox.showwarning("Documenti", "Seleziona almeno un documento da esportare")
            return
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Esporta documenti",
            defaultextension=".csv",
            filetypes=(("CSV", "*.csv"), ("Tutti i file", "*.*")),
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["ID", "Socio", "Descrizione", "Categoria", "Tipo", "Nome file", "Data", "Percorso"])
                for doc in docs:
                    writer.writerow(
                        [
                            doc.get("id"),
                            doc.get("socio_display"),
                            doc.get("descrizione"),
                            doc.get("categoria"),
                            doc.get("tipo"),
                            doc.get("nome_file"),
                            doc.get("data_caricamento"),
                            doc.get("percorso"),
                        ]
                    )
            messagebox.showinfo("Esporta", f"Esportazione completata:\n{file_path}")
        except Exception as exc:
            messagebox.showerror("Esporta", f"Impossibile scrivere il file:\n{exc}")

    def _open_member_folder(self):
        member_id = self._current_target_member_id()
        if not member_id:
            messagebox.showwarning("Documenti", "Seleziona un socio prima di aprire la cartella")
            return
        try:
            from documents_manager import get_member_docs_dir

            folder = get_member_docs_dir(int(member_id))
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", folder], check=False)
            else:
                subprocess.run(["xdg-open", folder], check=False)
        except Exception as exc:
            messagebox.showerror("Documenti", f"Impossibile aprire la cartella del socio:\n{exc}")


class _CategoryChoiceDialog(simpledialog.Dialog):
    """Simple dialog to pick a document category."""

    def __init__(self, parent, initial_category: str):
        self._initial_category = initial_category
        super().__init__(parent, title="Seleziona categoria")

    def body(self, master):
        ttk.Label(master, text="Categoria da applicare ai documenti selezionati:").grid(row=0, column=0, padx=10, pady=(10, 4))
        self.combo = ttk.Combobox(master, values=DOCUMENT_CATEGORIES, state="readonly", width=32)
        self.combo.grid(row=1, column=0, padx=10, pady=(0, 10))
        initial = self._initial_category if self._initial_category in DOCUMENT_CATEGORIES else DEFAULT_DOCUMENT_CATEGORY
        self.combo.set(initial)
        return self.combo

    def apply(self):
        self.result = self.combo.get()


class SectionDocumentPanel(ttk.Frame):
    """Panel for section-wide documents stored under data/section_docs."""

    ALL_LABEL = "Tutte"

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.docs = []
        self.filter_var = tk.StringVar(value=self.ALL_LABEL)
        default_cat = SECTION_DOCUMENT_CATEGORIES[0] if SECTION_DOCUMENT_CATEGORIES else "Altro"
        self.upload_category_var = tk.StringVar(value=default_cat)
        self._doc_path_map: dict[str, str] = {}
        self._doc_meta_map: dict[str, dict] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text="Carica", command=self._add_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Apri", command=self._open_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Apri cartella", command=self._open_document_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Modifica", command=self._edit_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Elimina", command=self._delete_document).pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar, text="Carica in:").pack(side=tk.LEFT, padx=(15, 2))
        self.upload_category_combo = ttk.Combobox(
            toolbar,
            textvariable=self.upload_category_var,
            values=SECTION_DOCUMENT_CATEGORIES,
            state="readonly",
            width=24,
        )
        self.upload_category_combo.pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar, text="Filtro categoria:").pack(side=tk.LEFT, padx=(15, 2))
        filter_values = (self.ALL_LABEL,) + tuple(SECTION_DOCUMENT_CATEGORIES)
        self.filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=filter_values,
            state="readonly",
            width=20,
        )
        self.filter_combo.pack(side=tk.LEFT, padx=2)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tv_docs = ttk.Treeview(
            frame,
            columns=("originale", "hash", "categoria", "descrizione", "dimensione", "modificato"),
            show="headings",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.tv_docs.yview)

        self.tv_docs.heading("originale", text="Nome originale")
        self.tv_docs.heading("hash", text="ID (hash)")
        self.tv_docs.heading("categoria", text="Categoria")
        self.tv_docs.heading("descrizione", text="Descrizione")
        self.tv_docs.heading("dimensione", text="Dimensione")
        self.tv_docs.heading("modificato", text="Ultima modifica")

        self.tv_docs.column("originale", width=220)
        self.tv_docs.column("hash", width=110)
        self.tv_docs.column("categoria", width=140)
        self.tv_docs.column("descrizione", width=240)
        self.tv_docs.column("dimensione", width=110, anchor="e")
        self.tv_docs.column("modificato", width=150)

        self.tv_docs.pack(fill=tk.BOTH, expand=True)

    def refresh(self):
        """Reload section documents from disk applying current filter."""
        for item in self.tv_docs.get_children():
            self.tv_docs.delete(item)
        self._doc_path_map.clear()
        self._doc_meta_map.clear()

        try:
            self.docs = list_section_documents()
        except Exception as exc:
            logger.error("Failed to read section documents: %s", exc)
            messagebox.showerror("Documenti", f"Errore lettura documenti sezione:\n{exc}")
            self.docs = []
            return

        active_filter = self.filter_var.get()
        for doc in self.docs:
            categoria = str(doc.get("categoria") or "")
            if active_filter not in (self.ALL_LABEL, "") and categoria != active_filter:
                continue

            path = str(doc.get("percorso") or "")
            absolute_path = str(doc.get("absolute_path") or path)
            original_name = str(doc.get("original_name") or doc.get("nome_file") or "")
            hash_id = str(doc.get("hash_id") or "-")
            descrizione = str(doc.get("descrizione") or "")

            size_value = doc.get("size")
            if isinstance(size_value, (int, float)):
                size_int = int(size_value)
            elif isinstance(size_value, str):
                try:
                    size_int = int(float(size_value))
                except ValueError:
                    size_int = 0
            else:
                size_int = 0

            mtime_value = doc.get("mtime")
            if isinstance(mtime_value, (int, float)):
                mtime = mtime_value
            elif isinstance(mtime_value, str):
                try:
                    mtime = float(mtime_value)
                except ValueError:
                    mtime = None
            else:
                mtime = None

            item_id = self.tv_docs.insert(
                "",
                tk.END,
                values=(
                    original_name,
                    hash_id,
                    categoria,
                    descrizione,
                    human_readable_size(size_int),
                    human_readable_mtime(mtime),
                ),
            )
            self._doc_path_map[item_id] = absolute_path
            self._doc_meta_map[item_id] = doc

    def _selected_path(self):
        sel = self.tv_docs.selection()
        if not sel:
            return None
        return self._doc_path_map.get(sel[0])

    def _selected_doc_entry(self):
        sel = self.tv_docs.selection()
        if not sel:
            return None
        return self._doc_meta_map.get(sel[0])

    def _add_document(self):
        file_path = filedialog.askopenfilename(parent=self, title="Seleziona documento di sezione")
        if not file_path:
            return
        default_cat = SECTION_DOCUMENT_CATEGORIES[0] if SECTION_DOCUMENT_CATEGORIES else "Altro"
        metadata = ask_document_metadata(
            self,
            title="Dettagli documento di sezione",
            categories=SECTION_DOCUMENT_CATEGORIES,
            default_category=default_cat,
            initial_category=self.upload_category_var.get(),
            initial_description="",
        )
        if not metadata:
            return
        categoria, descrizione = metadata
        self.upload_category_var.set(categoria)
        try:
            dest = add_section_document(file_path, categoria, descrizione)
            messagebox.showinfo("Documenti", f"Documento caricato in {categoria}:\n{os.path.basename(dest)}")
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Documenti", f"Errore caricamento documento:\n{exc}")

    def _open_document(self):
        path = self._selected_path()
        if not path:
            messagebox.showwarning("Documenti", "Selezionare un documento da aprire")
            return
        if not os.path.exists(path):
            messagebox.showerror("Documenti", "File non trovato sul disco")
            self.refresh()
            return
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception as exc:
            messagebox.showerror("Documenti", f"Impossibile aprire il documento:\n{exc}")

    def _open_document_folder(self):
        path = self._selected_path()
        if not path:
            messagebox.showwarning("Documenti", "Selezionare un documento per aprire la cartella")
            return

        folder = os.path.dirname(path) or os.path.dirname(os.path.abspath(path))
        if not folder:
            messagebox.showerror("Documenti", "Impossibile determinare la cartella del documento")
            return

        if not os.path.exists(path) and not os.path.isdir(folder):
            messagebox.showerror("Documenti", "File non trovato sul disco")
            self.refresh()
            return

        doc = self._selected_doc_entry()
        default_cat = SECTION_DOCUMENT_CATEGORIES[0] if SECTION_DOCUMENT_CATEGORIES else "Altro"
        category = str(doc.get("categoria") or default_cat) if doc else default_cat

        try:
            ensure_section_index_file(category)
        except Exception as exc:
            logger.warning("Impossibile aggiornare l'indice per la categoria %s: %s", category, exc)

        try:
            if os.name == "nt":
                if os.path.exists(path):
                    normalized = os.path.normpath(path)
                    cmd = f'explorer /select,"{normalized}"'
                    subprocess.run(cmd, check=False, shell=True)
                else:
                    os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                if os.path.exists(path):
                    subprocess.run(["open", "-R", path], check=False)
                else:
                    subprocess.run(["open", folder], check=False)
            else:
                subprocess.run(["xdg-open", folder], check=False)
        except Exception as exc:
            messagebox.showerror("Documenti", f"Impossibile aprire la cartella:\n{exc}")

    def _edit_document(self):
        path = self._selected_path()
        if not path:
            messagebox.showwarning("Documenti", "Selezionare un documento da modificare")
            return
        doc = self._selected_doc_entry()
        if not doc:
            messagebox.showwarning("Documenti", "Documento non trovato nella lista")
            return

        default_cat = SECTION_DOCUMENT_CATEGORIES[0] if SECTION_DOCUMENT_CATEGORIES else "Altro"
        metadata = ask_document_metadata(
            self,
            title="Modifica documento di sezione",
            categories=SECTION_DOCUMENT_CATEGORIES,
            default_category=default_cat,
            initial_category=str(doc.get("categoria") or default_cat),
            initial_description=str(doc.get("descrizione") or ""),
        )
        if not metadata:
            return
        categoria, descrizione = metadata
        try:
            update_section_document_metadata(path, categoria, descrizione)
            messagebox.showinfo("Documenti", "Documento aggiornato")
            self.refresh()
        except ValueError as exc:
            messagebox.showerror("Documenti", str(exc))
        except FileNotFoundError as exc:
            messagebox.showerror("Documenti", str(exc))
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Documenti", f"Errore aggiornamento documento:\n{exc}")

    def _delete_document(self):
        path = self._selected_path()
        if not path:
            messagebox.showwarning("Documenti", "Selezionare un documento da eliminare")
            return
        if not messagebox.askyesno("Conferma", "Eliminare il documento selezionato? Questa operazione non è reversibile."):
            return
        try:
            if delete_section_document(path):
                self.refresh()
                messagebox.showinfo("Documenti", "Documento eliminato")
            else:
                messagebox.showwarning("Documenti", "Il file non esiste più.")
                self.refresh()
        except Exception as exc:
            messagebox.showerror("Documenti", f"Errore eliminazione documento:\n{exc}")


class SectionInfoPanel(ttk.Frame):
    """Panel for section information."""

    def __init__(self, parent, *, editable: bool = True, **kwargs):
        super().__init__(parent, **kwargs)
        self.widgets = {}
        self.editable = editable
        self._build_ui()
    
    def _build_ui(self):
        """Build section info UI"""
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        fields = [
            ("nome_sezione", "Nome Sezione"),
            ("codice_sezione", "Codice Sezione (4 cifre)"),
            ("sede_operativa", "Sede Operativa"),
            ("sede_legale", "Sede Legale"),
            ("indirizzo_postale", "Indirizzo Postale"),
            ("email", "Email"),
            ("telefono", "Telefono"),
            ("sito_web", "Sito Web"),
            ("coordinate_bancarie", "Coordinate Bancarie"),
            ("recapiti", "Recapiti (descrizione)"),
            ("cd_componenti", "Consiglio Direttivo"),
            ("cd_triennio", "Triennio validità CD (es: 2023-2026)"),
            ("privacy_validita_anni", "Validità Privacy (anni)"),
        ]
        
        for field_name, label_text in fields:
            ttk.Label(scrollable_frame, text=label_text).grid(
                row=len(self.widgets), column=0, sticky="e", padx=5, pady=5
            )
            
            if field_name == "cd_componenti":
                widget = tk.Text(scrollable_frame, height=16, width=100)
                if self.editable:
                    ttk.Button(
                        scrollable_frame,
                        text="🔄 Aggiorna",
                        command=self._refresh_cd_members,
                        width=12,
                    ).grid(row=len(self.widgets), column=2, sticky="w", padx=5, pady=5)
            elif field_name == "recapiti":
                widget = tk.Text(scrollable_frame, height=4, width=60)
            else:
                widget = ttk.Entry(scrollable_frame, width=60)
            
            widget.grid(row=len(self.widgets), column=1, sticky="ew", padx=5, pady=5)
            if isinstance(widget, tk.Text) and not self.editable:
                widget.configure(state=tk.DISABLED)
            elif isinstance(widget, ttk.Entry) and not self.editable:
                widget_state = widget.cget("state")
                if widget_state != "readonly":
                    widget.configure(state="readonly")
            self.widgets[field_name] = widget
            scrollable_frame.columnconfigure(1, weight=1)
        
        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def get_values(self) -> dict:
        """Get all section info values"""
        values = {}
        for field_name, widget in self.widgets.items():
            if isinstance(widget, tk.Text):
                values[field_name] = widget.get("1.0", tk.END).strip()
            else:
                values[field_name] = widget.get().strip()
        return values
    
    def set_values(self, data: dict):
        """Set all section info values"""
        # Populate CD members automatically
        data = data.copy()  # Don't modify original dict
        if 'cd_componenti' not in data or not data['cd_componenti']:
            data['cd_componenti'] = self._get_cd_members()
        
        for field_name, value in data.items():
            if field_name not in self.widgets:
                continue

            widget = self.widgets[field_name]
            text_value = str(value or "")

            if isinstance(widget, tk.Text):
                restore = False
                if not self.editable:
                    widget.configure(state=tk.NORMAL)
                    restore = True
                widget.delete("1.0", tk.END)
                widget.insert("1.0", text_value)
                if restore:
                    widget.configure(state=tk.DISABLED)
            else:
                restore = False
                if not self.editable:
                    widget.configure(state=tk.NORMAL)
                    restore = True
                widget.delete(0, tk.END)
                widget.insert(0, text_value)
                if restore:
                    widget.configure(state="readonly")
    
    def _get_cd_members(self) -> str:
        """Get list of CD members from database, grouped by role."""
        try:
            from database import fetch_all
            
            # Fetch all active members with CD roles
            rows = fetch_all("""
                SELECT nome, cognome, nominativo, cd_ruolo 
                FROM soci 
                WHERE cd_ruolo IN ('Presidente', 'Vice Presidente', 'Segretario', 'Tesoriere', 'Sindaco', 'Consigliere')
                AND deleted_at IS NULL
                ORDER BY 
                    CASE cd_ruolo
                        WHEN 'Presidente' THEN 1
                        WHEN 'Vice Presidente' THEN 2
                        WHEN 'Segretario' THEN 3
                        WHEN 'Tesoriere' THEN 4
                        WHEN 'Sindaco' THEN 5
                        WHEN 'Consigliere' THEN 6
                    END,
                    cognome, nome
            """)
            
            if not rows:
                return ""
            
            # Group by role
            grouped = {}
            for row in rows:
                nome = row['nome'] if hasattr(row, 'get') else row[0]
                cognome = row['cognome'] if hasattr(row, 'get') else row[1]
                nominativo = row['nominativo'] if hasattr(row, 'get') else row[2]
                cd_ruolo = row['cd_ruolo'] if hasattr(row, 'get') else row[3]
                # Format: NOMINATIVO, Nome Cognome (or just Nome Cognome if nominativo is empty)
                if nominativo and nominativo.strip():
                    display_name = f"{nominativo}, {nome} {cognome}"
                else:
                    display_name = f"{nome} {cognome}"
                if cd_ruolo not in grouped:
                    grouped[cd_ruolo] = []
                grouped[cd_ruolo].append(display_name)
            
            # Format output with indentation
            lines = []
            role_order = ['Presidente', 'Vice Presidente', 'Segretario', 'Tesoriere', 'Sindaco', 'Consigliere']
            for role in role_order:
                if role in grouped:
                    lines.append(f"{role}:")
                    for member in grouped[role]:
                        lines.append(f"    {member}")
            
            return '\n'.join(lines)
        except Exception as e:
            logger.error(f"Failed to get CD members: {e}")
            return ""
    
    def _refresh_cd_members(self):
        """Refresh CD members list in the text widget."""
        cd_widget = self.widgets.get('cd_componenti')
        if cd_widget and isinstance(cd_widget, tk.Text):
            cd_members = self._get_cd_members()
            cd_widget.delete("1.0", tk.END)
            cd_widget.insert("1.0", cd_members)


class EventLogPanel(ttk.Frame):
    """Panel for activity log"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build_ui()
    
    def _build_ui(self):
        """Build event log UI"""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Ricarica", command=self.refresh).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Cancella log", command=self._clear_log).pack(side=tk.LEFT, padx=2)
        
        # Event list
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tv_events = ttk.Treeview(
            frame, columns=("timestamp", "tipo", "socio", "dettagli"),
            show="headings", yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.tv_events.yview)
        
        self.tv_events.heading("timestamp", text="Timestamp")
        self.tv_events.heading("tipo", text="Tipo")
        self.tv_events.heading("socio", text="Socio")
        self.tv_events.heading("dettagli", text="Dettagli")
        
        self.tv_events.column("timestamp", width=150)
        self.tv_events.column("tipo", width=100)
        self.tv_events.column("socio", width=150)
        self.tv_events.column("dettagli", width=300)
        
        self.tv_events.pack(fill=tk.BOTH, expand=True)
    
    def refresh(self):
        """Refresh event log"""
        # Clear treeview
        for item in self.tv_events.get_children():
            self.tv_events.delete(item)
        
        # Load events from database
        try:
            from database import fetch_all
            events = fetch_all(
                "SELECT ts, tipo_evento, socio_id, dettagli_json FROM eventi_libro_soci "
                "ORDER BY ts DESC LIMIT 100"
            )
            
            for event in events:
                self.tv_events.insert("", tk.END, values=(
                    event["ts"],
                    event["tipo_evento"],
                    f"#{event['socio_id']}",
                    event["dettagli_json"][:50]
                ))
        except Exception as e:
            logger.warning("Failed to load events: %s", e)
    
    def _clear_log(self):
        """Clear event log"""
        if messagebox.askyesno("Cancella log", "Eliminare tutti gli eventi?"):
            try:
                from database import exec_query
                exec_query("DELETE FROM eventi_libro_soci")
                self.refresh()
                messagebox.showinfo("Log", "Log svuotato.")
            except Exception as e:
                messagebox.showerror("Log", f"Errore: {e}")
