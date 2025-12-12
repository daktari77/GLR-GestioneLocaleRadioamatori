# -*- coding: utf-8 -*-
"""
Documents dialog for member document management
"""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging

logger = logging.getLogger("librosoci")

from documents_catalog import DOCUMENT_CATEGORIES, DEFAULT_DOCUMENT_CATEGORY
from .document_metadata_prompt import ask_document_metadata

class DocumentsDialog(tk.Toplevel):
    """Dialog for managing documents for a member."""
    
    def __init__(self, parent, socio_id: int, nome_socio: str = ""):
        """Initialize documents dialog."""
        super().__init__(parent)
        self.socio_id = socio_id
        clean_name = (nome_socio or "").strip()
        self.nome_socio = clean_name if clean_name and clean_name != "-" else f"Socio {socio_id}"
        
        self.title(f"Documentale - {self.nome_socio}")
        self.geometry("800x500")
        self.resizable(True, True)
        
        self._build_ui()
        self._refresh_documents()
        
        # Setup keyboard shortcuts
        self._setup_shortcuts()
        
        # Make modal
        self.transient(parent)
        self.grab_set()
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for dialog."""
        # Esc: Close dialog
        self.bind("<Escape>", lambda e: self.destroy())
        
        # Enter: View selected document
        self.bind("<Return>", lambda e: self._view_document())
        
        # Delete: Delete selected document
        self.bind("<Delete>", lambda e: self._delete_document())
        
        # Ctrl+U: Upload document
        self.bind("<Control-u>", lambda e: self._upload_document())
        self.bind("<Control-U>", lambda e: self._upload_document())
        
        # Ctrl+P: Upload privacy
        self.bind("<Control-p>", lambda e: self._upload_privacy())
        self.bind("<Control-P>", lambda e: self._upload_privacy())
    
    def _build_ui(self):
        """Build the dialog UI."""
        # Header with socio info
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(header, text=f"Socio: {self.nome_socio}", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        # Privacy status
        self.privacy_label = ttk.Label(header, text="", foreground="red")
        self.privacy_label.pack(side=tk.RIGHT, padx=5)
        self._refresh_privacy_badge()
        
        # Document type filter
        filter_frame = ttk.LabelFrame(self, text="Filtri")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.doc_type_var = tk.StringVar(value="tutti")
        ttk.Radiobutton(filter_frame, text="Tutti", variable=self.doc_type_var, value="tutti", command=self._refresh_documents).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(filter_frame, text="Privacy", variable=self.doc_type_var, value="privacy", command=self._refresh_documents).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(filter_frame, text="Documenti", variable=self.doc_type_var, value="documento", command=self._refresh_documents).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(filter_frame, text="Altro", variable=self.doc_type_var, value="altro", command=self._refresh_documents).pack(side=tk.LEFT, padx=5)
        
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(toolbar, text="Carica documento", command=self._upload_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Carica privacy", command=self._upload_privacy).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Visualizza", command=self._view_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Modifica", command=self._edit_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Elimina", command=self._delete_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Apri cartella", command=self._open_folder).pack(side=tk.LEFT, padx=2)

        # Keep an internal category tracker for dialogs, even without exposing the combo box
        self.category_var = tk.StringVar(value=DEFAULT_DOCUMENT_CATEGORY)
        
        # Documents treeview
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar_v = ttk.Scrollbar(frame, orient="vertical")
        scrollbar_h = ttk.Scrollbar(frame, orient="horizontal")
        
        self.tv_docs = ttk.Treeview(
            frame,
            columns=("id", "descrizione", "categoria", "tipo", "nome", "data", "info"),
            show="headings",
            yscrollcommand=scrollbar_v.set,
            xscrollcommand=scrollbar_h.set
        )
        scrollbar_v.config(command=self.tv_docs.yview)
        scrollbar_h.config(command=self.tv_docs.xview)
        
        # Configure columns
        self.tv_docs.column("id", width=50, anchor="center")
        self.tv_docs.column("descrizione", width=240)
        self.tv_docs.column("categoria", width=160)
        self.tv_docs.column("tipo", width=110, anchor="center")
        self.tv_docs.column("nome", width=260)
        self.tv_docs.column("data", width=130, anchor="center")
        self.tv_docs.column("info", width=220)

        self.tv_docs.heading("id", text="ID")
        self.tv_docs.heading("descrizione", text="Descrizione")
        self.tv_docs.heading("categoria", text="Categoria")
        self.tv_docs.heading("tipo", text="Tipo")
        self.tv_docs.heading("nome", text="Nome file")
        self.tv_docs.heading("data", text="Data")
        self.tv_docs.heading("info", text="Informazioni file")
        
        self.tv_docs.grid(row=0, column=0, sticky="nsew")
        scrollbar_v.grid(row=0, column=1, sticky="ns")
        scrollbar_h.grid(row=1, column=0, sticky="ew")
        self.tv_docs.bind("<<TreeviewSelect>>", self._sync_category_from_selection)
        
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(button_frame, text="Chiudi", command=self.destroy).pack(side=tk.RIGHT, padx=2)
    
    def _refresh_documents(self):
        """Refresh the documents list."""
        from database import get_documenti
        from documents_manager import format_file_info
        
        # Clear treeview
        for item in self.tv_docs.get_children():
            self.tv_docs.delete(item)
        
        # Load documents
        docs = get_documenti(self.socio_id)
        doc_type_filter = self.doc_type_var.get()
        has_privacy_doc = any((doc.get('tipo') or '').lower() == 'privacy' for doc in docs)
        
        for doc in docs:
            if doc_type_filter != "tutti" and doc['tipo'] != doc_type_filter:
                continue

            info = format_file_info(doc['percorso'])
            descr_value = doc.get('descrizione') or ''
            self.tv_docs.insert("", tk.END, iid=doc['id'], values=(
                doc['id'],
                descr_value,
                doc.get('categoria', ''),
                doc['tipo'],
                doc['nome_file'],
                doc.get('data_caricamento', '')[:10],
                info,
            ))
        self.category_var.set(DEFAULT_DOCUMENT_CATEGORY)
        self._sync_privacy_status_from_docs(has_privacy_doc)

    def _refresh_privacy_badge(self) -> bool:
        """Update the privacy label based on the database flag."""
        try:
            from database import get_privacy_status

            status = get_privacy_status(self.socio_id)
        except Exception as exc:  # pragma: no cover - UI safeguard
            logger.error("Impossibile leggere lo stato privacy per socio %s: %s", self.socio_id, exc)
            status = {"privacy_signed": 0}

        signed = str(status.get("privacy_signed") or "").strip().lower() in {"1", "true", "si", "sì", "yes"}
        text = "✓ Modulo privacy firmato" if signed else "⚠ Modulo privacy NON firmato"
        color = "green" if signed else "red"
        self.privacy_label.config(text=text, foreground=color)
        return signed

    def _sync_privacy_status_from_docs(self, has_privacy_doc: bool) -> None:
        """Ensure privacy flag follows the actual presence of privacy documents."""
        signed = self._refresh_privacy_badge()
        if not has_privacy_doc or signed:
            return
        try:
            from database import set_privacy_signed

            set_privacy_signed(self.socio_id, True)
            self._refresh_privacy_badge()
        except Exception as exc:  # pragma: no cover - DB safeguard
            logger.error("Impossibile aggiornare lo stato privacy per socio %s: %s", self.socio_id, exc)

    def _sync_category_from_selection(self, _event=None):
        """Keep the internal category tracker aligned with the selected document."""
        selection = self.tv_docs.selection()
        if not selection:
            return
        values = self.tv_docs.item(selection[0], "values")
        selected_category = values[2] if len(values) > 2 and values[2] else DEFAULT_DOCUMENT_CATEGORY
        self.category_var.set(selected_category if selected_category in DOCUMENT_CATEGORIES else DEFAULT_DOCUMENT_CATEGORY)

    def _upload_document(self):
        """Upload a generic document."""
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Seleziona documento",
            filetypes=[
                ("Tutti i file", "*.*"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx;*.doc"),
                ("Immagini", "*.jpg;*.png;*.gif")
            ]
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

        success, msg = upload_document(self.socio_id, file_path, "documento", categoria, descrizione)
        if success:
            messagebox.showinfo("Successo", msg)
            self._refresh_documents()
        else:
            messagebox.showerror("Errore", msg)
    
    def _upload_privacy(self):
        """Upload privacy form and mark as signed."""
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Seleziona modulo privacy",
            filetypes=[
                ("Tutti i file", "*.*"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx;*.doc"),
                ("Immagini", "*.jpg;*.png;*.gif")
            ]
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

        success, msg = upload_document(self.socio_id, file_path, "privacy", categoria, descrizione)
        if success:
            set_privacy_signed(self.socio_id, True)
            messagebox.showinfo("Successo", msg + "\n✓ Modulo privacy marcato come firmato")
            self._refresh_documents()
        else:
            messagebox.showerror("Errore", msg)

    def _edit_document(self):
        selection = self.tv_docs.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Selezionare un documento da modificare")
            return

        from database import get_documenti
        doc_id = int(selection[0])
        docs = get_documenti(self.socio_id)
        doc = next((d for d in docs if d['id'] == doc_id), None)
        if not doc:
            messagebox.showwarning("Documenti", "Documento non trovato")
            return

        metadata = ask_document_metadata(
            self,
            title="Modifica documento",
            categories=DOCUMENT_CATEGORIES,
            default_category=DEFAULT_DOCUMENT_CATEGORY,
            initial_category=doc.get('categoria') or DEFAULT_DOCUMENT_CATEGORY,
            initial_description=doc.get('descrizione') or "",
        )
        if not metadata:
            return
        nuova_categoria, nuova_descrizione = metadata

        actions: list[str] = []
        from documents_manager import update_document_category, update_document_description

        if (doc.get('categoria') or DEFAULT_DOCUMENT_CATEGORY) != nuova_categoria:
            success, msg = update_document_category(doc_id, nuova_categoria)
            if success:
                actions.append(msg)
            else:
                messagebox.showerror("Errore", msg)
                return

        descr_corrente = doc.get('descrizione') or ""
        if descr_corrente != nuova_descrizione:
            success, msg = update_document_description(doc_id, nuova_descrizione)
            if success:
                actions.append("Descrizione aggiornata")
            else:
                messagebox.showerror("Errore", msg)
                return

        if actions:
            messagebox.showinfo("Successo", "\n".join(actions))
            self._refresh_documents()
        else:
            messagebox.showinfo("Documenti", "Nessuna modifica applicata")

    def _open_folder(self):
        from documents_manager import get_member_docs_dir

        folder = get_member_docs_dir(self.socio_id)
        if not os.path.isdir(folder):
            messagebox.showwarning("Documenti", "Cartella documenti non trovata")
            return
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", folder], check=False)
            else:
                subprocess.run(["xdg-open", folder], check=False)
        except Exception as exc:
            messagebox.showerror("Documenti", f"Impossibile aprire la cartella:\n{exc}")
    
    def _view_document(self):
        """Open selected document."""
        selection = self.tv_docs.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Selezionare un documento")
            return
        
        from database import get_documenti
        docs = get_documenti(self.socio_id)
        doc_id = int(selection[0])
        doc = next((d for d in docs if d['id'] == doc_id), None)
        
        if doc and os.path.exists(doc['percorso']):
            import os
            import subprocess
            try:
                if os.name == 'nt':
                    os.startfile(doc['percorso'])
                else:
                    subprocess.run(['xdg-open', doc['percorso']], check=True)
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aprire il documento: {str(e)}")
        else:
            messagebox.showerror("Errore", "File non trovato")
    
    def _delete_document(self):
        """Delete selected document."""
        selection = self.tv_docs.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Selezionare un documento da eliminare")
            return
        
        if messagebox.askyesno("Conferma", "Eliminare il documento selezionato?"):
            doc_id = int(selection[0])
            from documents_manager import delete_document
            success, msg = delete_document(self.socio_id, doc_id)
            
            if success:
                messagebox.showinfo("Successo", msg)
                self._refresh_documents()
            else:
                messagebox.showerror("Errore", msg)
