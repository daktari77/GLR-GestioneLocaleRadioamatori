# -*- coding: utf-8 -*-
"""
Templates management dialog for GLR - Gestione Locale Radioamatori
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
import os

logger = logging.getLogger("librosoci")

class TemplatesDialog(tk.Toplevel):
    """Dialog for managing document templates."""
    
    def __init__(self, parent):
        """Initialize templates dialog."""
        super().__init__(parent)
        self.title("Gestione Template Documenti")
        self.geometry("900x600")
        self.resizable(True, True)
        
        self._build_ui()
        self._refresh_templates()
        
        # Setup shortcuts
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<F5>", lambda e: self._refresh_templates())
        
        # Make modal
        self.transient(parent)
        self.grab_set()
    
    def _build_ui(self):
        """Build the dialog UI."""
        # Header
        header = ttk.Frame(self, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Template Documenti", font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        
        # Toolbar
        toolbar = ttk.Frame(self, padding=(10, 0, 10, 10))
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="📄 Nuovo Template", command=self._add_template).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="✏️ Modifica", command=self._edit_template).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🗑️ Elimina", command=self._delete_template).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="👁️ Visualizza", command=self._view_template).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔄 Aggiorna", command=self._refresh_templates).pack(side=tk.LEFT, padx=2)
        
        # Type filter
        ttk.Label(toolbar, text="  |  Tipo:").pack(side=tk.LEFT, padx=5)
        self.type_filter_var = tk.StringVar(value="tutti")
        
        from templates_manager import TEMPLATE_TYPES
        ttk.Radiobutton(toolbar, text="Tutti", variable=self.type_filter_var, value="tutti", 
                       command=self._apply_filter).pack(side=tk.LEFT, padx=2)
        for type_key in TEMPLATE_TYPES.keys():
            ttk.Radiobutton(toolbar, text=TEMPLATE_TYPES[type_key][:20], variable=self.type_filter_var, 
                           value=type_key, command=self._apply_filter).pack(side=tk.LEFT, padx=2)
        
        # Templates list
        list_frame = ttk.Frame(self, padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        scrollbar_v = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar_h = ttk.Scrollbar(list_frame, orient="horizontal")
        
        self.tv_templates = ttk.Treeview(
            list_frame,
            columns=("id", "nome", "tipo", "descrizione", "placeholders", "created_at"),
            show="headings",
            yscrollcommand=scrollbar_v.set,
            xscrollcommand=scrollbar_h.set
        )
        scrollbar_v.config(command=self.tv_templates.yview)
        scrollbar_h.config(command=self.tv_templates.xview)
        
        # Configure columns
        self.tv_templates.column("id", width=50)
        self.tv_templates.column("nome", width=200)
        self.tv_templates.column("tipo", width=150)
        self.tv_templates.column("descrizione", width=250)
        self.tv_templates.column("placeholders", width=150)
        self.tv_templates.column("created_at", width=120)
        
        self.tv_templates.heading("id", text="ID")
        self.tv_templates.heading("nome", text="Nome Template")
        self.tv_templates.heading("tipo", text="Tipo")
        self.tv_templates.heading("descrizione", text="Descrizione")
        self.tv_templates.heading("placeholders", text="Placeholder")
        self.tv_templates.heading("created_at", text="Creato")
        
        self.tv_templates.grid(row=0, column=0, sticky="nsew")
        scrollbar_v.grid(row=0, column=1, sticky="ns")
        scrollbar_h.grid(row=1, column=0, sticky="ew")
        
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Info panel
        info_frame = ttk.LabelFrame(self, text="Informazioni", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        info_text = """
📝 I template sono modelli di documento per generare comunicazioni ufficiali.

Placeholder supportati:
  • [nome_placeholder] o {nome_placeholder}
  • Esempi: [presidente], [data], [numero_cd], [odg]

Formati supportati: .txt, .html, .doc, .docx, .odt
        """
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack()
    
    def _refresh_templates(self):
        """Refresh templates list."""
        # Clear treeview
        for item in self.tv_templates.get_children():
            self.tv_templates.delete(item)
        
        try:
            from templates_manager import get_all_templates, TEMPLATE_TYPES
            
            templates = get_all_templates()
            for tmpl in templates:
                tipo_label = TEMPLATE_TYPES.get(tmpl['tipo'], tmpl['tipo'])
                created = tmpl.get('created_at', '')[:10] if tmpl.get('created_at') else ''
                
                self.tv_templates.insert("", "end", values=(
                    tmpl['id'],
                    tmpl['nome'],
                    tipo_label,
                    tmpl.get('descrizione', ''),
                    tmpl.get('placeholders', ''),
                    created
                ))
        except Exception as e:
            logger.error(f"Failed to refresh templates: {e}")
            messagebox.showerror("Errore", f"Errore nel caricamento template: {e}")
    
    def _apply_filter(self):
        """Apply type filter."""
        # Clear treeview
        for item in self.tv_templates.get_children():
            self.tv_templates.delete(item)
        
        try:
            from templates_manager import get_all_templates, get_templates_by_type, TEMPLATE_TYPES
            
            filter_type = self.type_filter_var.get()
            if filter_type == "tutti":
                templates = get_all_templates()
            else:
                templates = get_templates_by_type(filter_type)
            
            for tmpl in templates:
                tipo_label = TEMPLATE_TYPES.get(tmpl['tipo'], tmpl['tipo'])
                created = tmpl.get('created_at', '')[:10] if tmpl.get('created_at') else ''
                
                self.tv_templates.insert("", "end", values=(
                    tmpl['id'],
                    tmpl['nome'],
                    tipo_label,
                    tmpl.get('descrizione', ''),
                    tmpl.get('placeholders', ''),
                    created
                ))
        except Exception as e:
            logger.error(f"Failed to apply filter: {e}")
    
    def _add_template(self):
        """Add new template."""
        dialog = AddTemplateDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            self._refresh_templates()
    
    def _edit_template(self):
        """Edit selected template."""
        selection = self.tv_templates.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Selezionare un template da modificare")
            return
        
        template_id = int(self.tv_templates.item(selection[0])['values'][0])
        messagebox.showinfo("Info", "Funzione di modifica in sviluppo")
    
    def _delete_template(self):
        """Delete selected template."""
        selection = self.tv_templates.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Selezionare un template da eliminare")
            return
        
        values = self.tv_templates.item(selection[0])['values']
        template_id = int(values[0])
        template_name = values[1]
        
        if not messagebox.askyesno("Conferma", f"Eliminare il template '{template_name}'?"):
            return
        
        try:
            from templates_manager import delete_template
            success, message = delete_template(template_id)
            
            if success:
                messagebox.showinfo("Successo", message)
                self._refresh_templates()
            else:
                messagebox.showerror("Errore", message)
        except Exception as e:
            logger.error(f"Failed to delete template: {e}")
            messagebox.showerror("Errore", f"Errore: {e}")
    
    def _view_template(self):
        """View template file."""
        selection = self.tv_templates.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Selezionare un template da visualizzare")
            return
        
        template_id = int(self.tv_templates.item(selection[0])['values'][0])
        
        try:
            from templates_manager import get_template_by_id
            import subprocess
            
            template = get_template_by_id(template_id)
            if template and os.path.exists(template['file_path']):
                os.startfile(template['file_path'])
            else:
                messagebox.showerror("Errore", "File template non trovato")
        except Exception as e:
            logger.error(f"Failed to view template: {e}")
            messagebox.showerror("Errore", f"Errore: {e}")


class AddTemplateDialog(tk.Toplevel):
    """Dialog for adding a new template."""
    
    def __init__(self, parent):
        """Initialize add template dialog."""
        super().__init__(parent)
        self.title("Aggiungi Template")
        self.geometry("500x400")
        self.resizable(False, False)
        
        self.result = None
        self.source_file = None
        
        self._build_ui()
        
        # Make modal
        self.transient(parent)
        self.grab_set()
    
    def _build_ui(self):
        """Build the dialog UI."""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Nome
        ttk.Label(main_frame, text="Nome Template:").grid(row=0, column=0, sticky="w", pady=5)
        self.nome_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.nome_var, width=40).grid(row=0, column=1, pady=5)
        
        # Tipo
        ttk.Label(main_frame, text="Tipo:").grid(row=1, column=0, sticky="w", pady=5)
        from templates_manager import TEMPLATE_TYPES
        self.tipo_var = tk.StringVar()
        tipo_combo = ttk.Combobox(main_frame, textvariable=self.tipo_var, width=37, state="readonly")
        tipo_combo['values'] = list(TEMPLATE_TYPES.values())
        tipo_combo.grid(row=1, column=1, pady=5)
        tipo_combo.current(0)
        
        # Descrizione
        ttk.Label(main_frame, text="Descrizione:").grid(row=2, column=0, sticky="nw", pady=5)
        self.desc_text = tk.Text(main_frame, width=40, height=4)
        self.desc_text.grid(row=2, column=1, pady=5)
        
        # Placeholders
        ttk.Label(main_frame, text="Placeholder:").grid(row=3, column=0, sticky="w", pady=5)
        self.placeholders_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.placeholders_var, width=40).grid(row=3, column=1, pady=5)
        ttk.Label(main_frame, text="(separati da virgola)", font=("Arial", 8)).grid(row=4, column=1, sticky="w")
        
        # File selection
        ttk.Label(main_frame, text="File Template:").grid(row=5, column=0, sticky="w", pady=5)
        file_frame = ttk.Frame(main_frame)
        file_frame.grid(row=5, column=1, pady=5, sticky="ew")
        
        self.file_label = ttk.Label(file_frame, text="Nessun file selezionato", foreground="gray")
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(file_frame, text="Sfoglia...", command=self._select_file).pack(side=tk.RIGHT)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Salva", command=self._save).pack(side=tk.RIGHT, padx=5)
    
    def _select_file(self):
        """Select template file."""
        filename = filedialog.askopenfilename(
            title="Seleziona file template",
            filetypes=[
                ("Tutti i formati", "*.txt *.html *.doc *.docx *.odt"),
                ("File di testo", "*.txt"),
                ("HTML", "*.html"),
                ("Word", "*.doc *.docx"),
                ("OpenDocument", "*.odt"),
            ]
        )
        
        if filename:
            self.source_file = filename
            self.file_label.config(text=os.path.basename(filename), foreground="black")
    
    def _save(self):
        """Save template."""
        nome = self.nome_var.get().strip()
        if not nome:
            messagebox.showwarning("Validazione", "Inserire il nome del template")
            return
        
        if not self.source_file:
            messagebox.showwarning("Validazione", "Selezionare un file template")
            return
        
        try:
            from templates_manager import add_template, TEMPLATE_TYPES
            
            # Get tipo key from value
            tipo_value = self.tipo_var.get()
            tipo_key = None
            for key, value in TEMPLATE_TYPES.items():
                if value == tipo_value:
                    tipo_key = key
                    break
            
            if not tipo_key:
                messagebox.showerror("Errore", "Tipo template non valido")
                return
            
            descrizione = self.desc_text.get("1.0", "end-1c").strip()
            placeholders = self.placeholders_var.get().strip()
            
            success, message = add_template(nome, tipo_key, self.source_file, descrizione, placeholders)
            
            if success:
                messagebox.showinfo("Successo", message)
                self.result = True
                self.destroy()
            else:
                messagebox.showerror("Errore", message)
        except Exception as e:
            logger.error(f"Failed to add template: {e}")
            messagebox.showerror("Errore", f"Errore: {e}")
