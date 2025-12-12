# -*- coding: utf-8 -*-
"""
CSV Import Wizard orchestrator for Libro Soci v4.2a
Manages the complete import workflow: File → Preset → Mapping → Preview → Insert
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
import csv

logger = logging.getLogger("librosoci")

class ImportWizard:
    """Main import wizard dialog - manages the complete import process"""
    
    def __init__(self, parent, on_complete_callback=None):
        """
        Initialize the import wizard
        
        Args:
            parent: Parent window
            on_complete_callback: Function to call when import completes (passes count)
        """
        self.parent = parent
        self.on_complete_callback = on_complete_callback
        
        # Import workflow state
        self.csv_path = None
        self.delimiter = None
        self.headers = []
        self.rows = []
        self.mapping = {}
        self.presets = {}
        self.import_count = 0
        self.selected_fields = {}  # Which fields to update during import
        
        # Create main window
        self.win = tk.Toplevel(parent)
        self.win.title("Importazione CSV - Nuovo socio")
        self.win.geometry("700x600")
        self.win.transient(parent)
        self.win.grab_set()
        
        # Wizard pages
        self.current_page = 0
        self.pages = [
            ("Seleziona file CSV", self._build_page_file),
            ("Configura importazione", self._build_page_config),
            ("Esegui importazione", self._build_page_import),
        ]
        
        # Main frame
        self.main_frame = ttk.Frame(self.win)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        self.title_label = ttk.Label(self.main_frame, text="", font=("Segoe UI", 12, "bold"))
        self.title_label.pack(fill=tk.X, pady=(0, 10))
        
        # Content frame (changes per page)
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Buttons
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.btn_prev = ttk.Button(button_frame, text="Indietro", command=self._prev_page)
        self.btn_prev.pack(side=tk.LEFT, padx=2)
        
        self.btn_next = ttk.Button(button_frame, text="Avanti", command=self._next_page)
        self.btn_next.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(button_frame, text="Annulla", command=self._cancel).pack(side=tk.RIGHT, padx=2)
        
        # Progress indicator
        self.progress_label = ttk.Label(self.main_frame, text="Pagina 1 di 3")
        self.progress_label.pack(fill=tk.X, pady=(5, 0))
        
        # Show first page
        self._show_page()
    
    def _build_page_file(self):
        """Page 1: File selection"""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Selezionare il file CSV da importare").pack(pady=10)
        
        file_frame = ttk.Frame(frame)
        file_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(file_frame, text="File:").pack(side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(file_frame, text="Nessun file selezionato", foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        ttk.Button(frame, text="Sfoglia...", command=self._select_file).pack(pady=10)
        
        # Delimiter info
        delim_frame = ttk.LabelFrame(frame, text="Delimitatore (auto-rilevato)")
        delim_frame.pack(fill=tk.X, pady=10)
        
        self.delim_label = ttk.Label(delim_frame, text="Nessun file selezionato")
        self.delim_label.pack(padx=5, pady=5)
        
        # Preview
        preview_frame = ttk.LabelFrame(frame, text="Anteprima intestazioni")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        scrollbar = ttk.Scrollbar(preview_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tv_file_preview = ttk.Treeview(
            preview_frame, columns=["header"], show="tree", height=8,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.tv_file_preview.yview)
        self.tv_file_preview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # Enable click-to-sort on the headers
        try:
            self._make_treeview_sortable(self.tv_file_preview, ['header'])
        except Exception:
            pass
    
    def _build_page_config(self):
        """Page 2: Complete configuration with mapping, field selection and preview"""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Tab 1: Mapping and Field Selection
        mapping_frame = ttk.Frame(notebook)
        notebook.add(mapping_frame, text="Mapping e Campi")
        
        ttk.Label(mapping_frame, text="Configura mapping colonne e seleziona campi da aggiornare", font=("Segoe UI", 10, "bold")).pack(pady=5)
        
        # Control buttons
        btn_frame = ttk.Frame(mapping_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Auto-rileva", command=self._auto_detect_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Seleziona tutto", command=self._select_all_fields).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Deseleziona tutto", command=self._deselect_all_fields).pack(side=tk.LEFT, padx=5)
        
        # Scrollable mapping area
        canvas = tk.Canvas(mapping_frame, height=300)
        scrollbar = ttk.Scrollbar(mapping_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Header
        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(header_frame, text="✓", font=("Segoe UI", 9, "bold"), width=3).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="Campo DB", font=("Segoe UI", 9, "bold"), width=18).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Colonna CSV", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        # Create mapping widgets
        self._create_mapping_widgets(scrollable_frame)
        
        # Tab 2: Preview
        preview_frame = ttk.Frame(notebook)
        notebook.add(preview_frame, text="Anteprima Dati")
        
        ttk.Label(preview_frame, text="Anteprima dei primi 20 record che saranno importati", font=("Segoe UI", 10, "bold")).pack(pady=5)
        
        # Preview treeview
        preview_tree_frame = ttk.Frame(preview_frame)
        preview_tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        preview_scroll = ttk.Scrollbar(preview_tree_frame)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.preview_tree = ttk.Treeview(preview_tree_frame, yscrollcommand=preview_scroll.set, height=15)
        preview_scroll.config(command=self.preview_tree.yview)
        self.preview_tree.pack(fill=tk.BOTH, expand=True)
        
        # Preview info
        self.preview_info = ttk.Label(preview_frame, text="Configurare il mapping per vedere l'anteprima")
        self.preview_info.pack(pady=5)
        
        # Import options
        options_frame = ttk.LabelFrame(frame, text="Opzioni di Importazione")
        options_frame.pack(fill=tk.X, pady=10)
        
        self.name_split_var = tk.StringVar(value="smart")
        ttk.Label(options_frame, text="Divisione nome:").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(options_frame, text="Automatica", variable=self.name_split_var, value="smart").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(options_frame, text="Primo=Nome", variable=self.name_split_var, value="first").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(options_frame, text="Ultimo=Cognome", variable=self.name_split_var, value="last").pack(side=tk.LEFT, padx=5)
        """Page 2: Preset loading"""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Carica un preset di mapping salvato (opzionale)").pack(pady=10)
        
        # Preset list
        list_frame = ttk.LabelFrame(frame, text="Preset disponibili")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox_presets = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=10)
        scrollbar.config(command=self.listbox_presets.yview)
        self.listbox_presets.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.listbox_presets.bind("<<ListboxSelect>>", self._on_preset_selected)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.btn_use_preset = ttk.Button(button_frame, text="Usa preset", command=self._use_preset, state=tk.DISABLED)
        self.btn_use_preset.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(button_frame, text="Salta (configura manualmente)", command=lambda: None).pack(side=tk.LEFT, padx=2)
        
        # Load presets
        self._refresh_preset_list()
    
    def _build_page_mapping(self):
        """Page 3: Column mapping and field selection"""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Associa le colonne CSV ai campi del database e seleziona quali aggiornare").pack(pady=10)
        
        # Info text
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill=tk.X, pady=5)
        info_text = ttk.Label(info_frame, 
            text="✓ = Campo sarà aggiornato durante l'importazione",
            foreground="blue", font=("Segoe UI", 9))
        info_text.pack()
        
        # Scrollable frame
        canvas = tk.Canvas(frame, height=350)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Get target fields
        try:
            from csv_import import TARGET_FIELDS
        except Exception:
            TARGET_FIELDS = [("matricola", "Matricola"), ("nome", "Nome"), ("cognome", "Cognome")]
        
        # Control buttons
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Auto-rileva mapping", command=self._auto_detect_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Seleziona tutto", command=self._select_all_fields).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Deseleziona tutto", command=self._deselect_all_fields).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(scrollable_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Header
        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(header_frame, text="✓", font=("Segoe UI", 9, "bold"), width=3).pack(side=tk.LEFT, padx=2)
        ttk.Label(header_frame, text="Campo database", font=("Segoe UI", 9, "bold"), width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Colonna CSV", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        # CSV column options
        csv_options = [""] + self.headers
        
        # Mapping widgets and checkboxes
        self.mapping_widgets = {}
        self.field_checkboxes = {}
        
        for field_key, field_label in TARGET_FIELDS:
            # Skip ID (not mappable)
            if field_key == 'id':
                continue
                
            row_frame = ttk.Frame(scrollable_frame)
            row_frame.pack(fill=tk.X, padx=10, pady=2)
            
            # Checkbox (except matricola which is always needed)
            if field_key == 'matricola':
                # Matricola always selected, show disabled checkbox
                var = tk.BooleanVar()
                var.set(True)
                cb = ttk.Checkbutton(row_frame, variable=var, state="disabled", width=3)
                self.field_checkboxes[field_key] = var
            else:
                var = tk.BooleanVar()
                # Default: select all fields except attivo (let user choose)
                if field_key != 'attivo':
                    var.set(True)
                else:
                    var.set(False)  # attivo requires user choice
                cb = ttk.Checkbutton(row_frame, variable=var, width=3)
                self.field_checkboxes[field_key] = var
            
            cb.pack(side=tk.LEFT, padx=2)
            
            # Field label
            ttk.Label(row_frame, text=field_label, width=20, anchor="w").pack(side=tk.LEFT, padx=5)
            
            # Mapping combo
            combo = ttk.Combobox(row_frame, values=csv_options, state="readonly", width=25)
            combo.pack(side=tk.LEFT, padx=5)
            
            self.mapping_widgets[field_key] = combo
        
        # Special note for attivo field
        note_frame = ttk.Frame(frame)
        note_frame.pack(fill=tk.X, pady=10)
        note_text = ttk.Label(note_frame, 
            text="Nota: Il campo 'Attivo' applica la regola basata su Voto e Q0. Selezionalo solo se vuoi aggiornare lo stato.",
            foreground="red", font=("Segoe UI", 9), justify=tk.LEFT)
        note_text.pack()
    
    def _build_page_import(self):
        """Page 3: Import execution"""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Pronto per l'importazione", font=("Segoe UI", 12, "bold")).pack(pady=20)
        
        # Summary
        summary_frame = ttk.LabelFrame(frame, text="Riepilogo Importazione")
        summary_frame.pack(fill=tk.X, pady=20)
        
        if hasattr(self, 'csv_path') and self.csv_path:
            ttk.Label(summary_frame, text=f"File: {self.csv_path}").pack(anchor="w", padx=10, pady=5)
            ttk.Label(summary_frame, text=f"Righe da importare: {len(self.rows) if hasattr(self, 'rows') else '0'}").pack(anchor="w", padx=10, pady=5)
            
            # Show selected fields
            if hasattr(self, 'selected_fields'):
                selected = [k for k, v in self.selected_fields.items() if v]
                ttk.Label(summary_frame, text=f"Campi selezionati: {', '.join(selected[:5])}{'...' if len(selected) > 5 else ''}").pack(anchor="w", padx=10, pady=5)
        
        # Progress
        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, pady=20, padx=50)
        
        self.progress_text = ttk.Label(frame, text="Cliccare 'Importa' per iniziare")
        self.progress_text.pack(pady=10)
        
        # Import button
        ttk.Button(frame, text="Importa Ora", command=self._execute_import, style="Accent.TButton").pack(pady=20)


        
    def _create_mapping_widgets(self, parent):
        """Create mapping widgets for field configuration"""
        try:
            from csv_import import TARGET_FIELDS
        except Exception:
            TARGET_FIELDS = [("matricola", "Matricola"), ("nome", "Nome"), ("cognome", "Cognome")]
        
        csv_options = [""]
        if hasattr(self, 'headers'):
            csv_options.extend(self.headers)
        
        self.mapping_widgets = {}
        self.field_checkboxes = {}
        
        for field_key, field_label in TARGET_FIELDS:
            if field_key == 'id':
                continue
                
            row_frame = ttk.Frame(parent)
            row_frame.pack(fill=tk.X, padx=5, pady=1)
            
            # Checkbox
            var = tk.BooleanVar()
            if field_key == 'matricola':
                var.set(True)
                cb = ttk.Checkbutton(row_frame, variable=var, state="disabled", width=3)
            else:
                var.set(field_key != 'attivo')  # All except attivo selected by default
                cb = ttk.Checkbutton(row_frame, variable=var, width=3)
            
            cb.pack(side=tk.LEFT)
            self.field_checkboxes[field_key] = var
            
            # Field label
            ttk.Label(row_frame, text=field_label, width=18, anchor="w").pack(side=tk.LEFT, padx=5)
            
            # Mapping combo
            combo = ttk.Combobox(row_frame, values=csv_options, state="readonly", width=20)
            combo.pack(side=tk.LEFT, padx=5)
            self.mapping_widgets[field_key] = combo
            
            # Bind combo change to update preview
            combo.bind('<<ComboboxSelected>>', self._on_mapping_change)
        """Select all field checkboxes (except matricola which is always selected)"""
        for field_key, var in self.field_checkboxes.items():
            if field_key != 'matricola':  # Skip matricola as it's disabled
                var.set(True)
            
    def _deselect_all_fields(self):
        """Deselect all field checkboxes (except matricola which is always selected)"""
        for field_key, var in self.field_checkboxes.items():
            if field_key != 'matricola':  # Skip matricola as it's disabled
                var.set(False)

    def _build_page_preview(self):
        """Page 4: Preview mapped data"""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Anteprima dei dati mappati (prime 100 righe)").pack(pady=8)

        # Build treeview with target fields as columns
        try:
            from csv_import import TARGET_FIELDS, apply_mapping
        except Exception:
            TARGET_FIELDS = []
            apply_mapping = None

        cols = [k for k, _ in TARGET_FIELDS]
        headings = {k: lbl for k, lbl in TARGET_FIELDS}

        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tv_preview = ttk.Treeview(tree_frame, columns=cols, show='headings', height=15,
                                       yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.tv_preview.yview)

        for c in cols:
            self.tv_preview.heading(c, text=headings.get(c, c))
            self.tv_preview.column(c, width=120, anchor='w')

        self.tv_preview.pack(fill=tk.BOTH, expand=True)

        # Enable sorting on preview columns
        try:
            self._make_treeview_sortable(self.tv_preview, cols)
        except Exception:
            pass

        # Info label
        self.preview_info = ttk.Label(frame, text="Caricamento anteprima...")
        self.preview_info.pack(pady=4)

        # Populate preview
        try:
            if apply_mapping is None:
                raise RuntimeError("Modulo v41_csv_import non disponibile")

            # Ensure mapping has type Dict[str, Optional[str]] to satisfy type checkers
            # Create a mapping dict with Optional[str] values to satisfy type checkers
            mapping_cast = {k: (v if v is not None else None) for k, v in self.mapping.items()}
            mapped = apply_mapping(self.rows, mapping_cast)

            def _display_val(val, key=None):
                if val is None:
                    return ""
                s = str(val)
                if key in ('attivo', 'voto'):
                    if s == '1':
                        return 'Si'
                    if s == '0':
                        return 'No'
                return s

            for i, r in enumerate(mapped[:100]):
                values = [ _display_val(r.get(c), c) for c in cols ]
                self.tv_preview.insert('', tk.END, values=values)

            self.preview_info.config(text=f"Righe mappate: {len(mapped)} (mostrate: {min(100, len(mapped))})")
        except Exception as e:
            self.preview_info.config(text=f"Errore anteprima: {e}")
            logger.exception("Preview build failed: %s", e)

        # Allow saving mapping from preview page
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=6)
        ttk.Button(btn_frame, text="Salva mapping come preset", command=self._save_mapping_preset).pack(side=tk.LEFT, padx=4)
    
    def _select_file(self):
        """File selection"""
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        
        try:
            from csv_import import sniff_delimiter, read_csv_file, auto_detect_mapping
            
            self.csv_path = path
            
            # Detect delimiter
            self.delimiter = sniff_delimiter(path)
            self.delim_label.config(text=f"Rilevato: {repr(self.delimiter)}")
            
            # Load CSV
            self.headers, self.rows = read_csv_file(path, self.delimiter)
            
            # Update file label
            self.file_label.config(text=path, foreground="black")
            
            # Update preview
            for item in self.tv_file_preview.get_children():
                self.tv_file_preview.delete(item)
            for header in self.headers:
                self.tv_file_preview.insert("", tk.END, values=(header,))
            
            # Auto-detect mapping
            self.mapping = auto_detect_mapping(self.headers)
            
            logger.info(f"Loaded CSV: {len(self.rows)} rows, {len(self.headers)} columns")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore caricamento file: {e}")
    
    def _refresh_preset_list(self):
        """Refresh preset list"""
        try:
            from csv_import import load_presets
            self.presets = load_presets()
            
            self.listbox_presets.delete(0, tk.END)
            for name in sorted(self.presets.keys()):
                self.listbox_presets.insert(tk.END, name)
        except Exception as e:
            logger.warning(f"Failed to load presets: {e}")
    
    def _on_preset_selected(self, event):
        """Handle preset selection"""
        sel = self.listbox_presets.curselection()
        self.btn_use_preset.config(state=tk.NORMAL if sel else tk.DISABLED)
    
    def _use_preset(self):
        """Load selected preset"""
        sel = self.listbox_presets.curselection()
        if not sel:
            return
        
        preset_name = self.listbox_presets.get(sel[0])
        self.mapping = self.presets.get(preset_name, {})
        
        # Update mapping widgets
        for field, combo in self.mapping_widgets.items():
            combo.set(self.mapping.get(field, ""))
        
        messagebox.showinfo("Preset", f"Preset '{preset_name}' caricato.")
    
    def _auto_detect_mapping(self):
        """Auto-detect column mapping"""
        try:
            from csv_import import auto_detect_mapping
            self.mapping = auto_detect_mapping(self.headers)
            
            # Update widgets with safe method
            if hasattr(self, 'mapping_widgets'):
                for field, combo in self.mapping_widgets.items():
                    try:
                        if hasattr(combo, 'set'):
                            value = self.mapping.get(field, "")
                            if value in combo['values'] or value == "":
                                combo.set(value)
                            else:
                                combo.set("")
                    except Exception as e:
                        logger.warning(f"Cannot set combo {field}: {e}")
            
            messagebox.showinfo("Mapping", "Mapping auto-rilevato!")
        except Exception as e:
            logger.error(f"Auto detect mapping failed: {e}")
            messagebox.showerror("Errore", f"Errore nel rilevamento automatico: {e}")
    
    def _save_mapping_preset(self):
        """Save current mapping as preset"""
        dialog = tk.Toplevel(self.win)
        dialog.title("Salva mapping")
        dialog.geometry("300x150")
        dialog.transient(self.win)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Nome preset:").pack(padx=10, pady=10)
        entry = ttk.Entry(dialog, width=30)
        entry.pack(padx=10, pady=5)
        
        def save_it():
            name = entry.get().strip()
            if not name:
                messagebox.showwarning("Salva", "Inserire un nome.")
                return
            
            try:
                from csv_import import save_presets
                
                # Use self.mapping (already contains the current mapping)
                mapping = {k: v for k, v in self.mapping.items() if v}
                
                self.presets[name] = mapping
                save_presets(self.presets)
                messagebox.showinfo("Salva", f"Preset '{name}' salvato.")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Errore", f"Errore: {e}")
        
        ttk.Button(dialog, text="Salva", command=save_it).pack(pady=5)

    def _make_treeview_sortable(self, tv, cols):
        """Enable click-to-sort on the given Treeview for the provided columns."""
        # store per-tree sort state
        if not hasattr(tv, '_sort_state'):
            tv._sort_state = {}

        def _on_heading(col):
            # toggle sort order
            rev = tv._sort_state.get(col, False)
            new_rev = not rev
            self._treeview_sort_column(tv, col, new_rev)
            tv._sort_state[col] = new_rev
            tv._last_sorted = (col, new_rev)

        for c in cols:
            try:
                # assign command to heading (supported by ttk.Treeview)
                tv.heading(c, command=lambda _c=c: _on_heading(_c))
            except Exception:
                # fallback: bind generic header click (less reliable)
                pass

    def _treeview_sort_column(self, tv, col, reverse=False):
        """Sort treeview `tv` by column `col`. Reverse if `reverse` True."""
        try:
            # gather items and their values for the column
            items = [(tv.set(k, col), k) for k in tv.get_children('')]

            def _conv(v):
                if v is None:
                    return ''
                s = str(v).strip()
                # try int, then float, otherwise lowercase string
                try:
                    return int(s)
                except Exception:
                    try:
                        return float(s)
                    except Exception:
                        return s.lower()

            items.sort(key=lambda t: _conv(t[0]), reverse=reverse)

            # reorder items in treeview
            for index, (_, k) in enumerate(items):
                tv.move(k, '', index)

            # Update heading indicators
            try:
                last = getattr(tv, '_last_sorted', (None, None))
                if last and last[0] and last[0] in tv['columns']:
                    text = tv.heading(last[0])['text']
                    text = text.replace(' ▲', '').replace(' ▼', '')
                    tv.heading(last[0], text=text)

                h = tv.heading(col)
                base = h.get('text', col)
                arrow = ' ▲' if reverse else ' ▼'
                base = base.replace(' ▲', '').replace(' ▼', '')
                tv.heading(col, text=base + arrow)
            except Exception:
                pass
        except Exception as e:
            logger.debug('Treeview sort failed for col %s: %s', col, e)

    def _split_name(self, full_name: str, mode: str):
        """Split a combined name field into (cognome, nome) using heuristics.

        Handles common compound surname prefixes (De, Di, D', Del, Della, Van, Von, Mc, Mac, etc.).
        `mode` is 'first' (first token as cognome) or 'last' (last token as cognome).
        Returns a tuple (cognome, nome). If no split possible returns (None, full_name).
        """
        if not full_name:
            return None, ''

        s = ' '.join(str(full_name).strip().split())
        tokens = s.split(' ')
        if len(tokens) < 2:
            return None, s

        # common prefixes that often form part of a compound surname (lowercase)
        prefixes = {"de", "di", "d'", "del", "della", "de la", "van", "von", "mac", "mc", "la", "le"}

        def clean(t):
            return t.lower().strip(".,'")

        if mode == 'first':
            # If the second token is a prefix, include it in the surname (e.g. "ROSSI DE" -> "ROSSI DE ...")
            if len(tokens) >= 3 and clean(tokens[1]) in prefixes:
                cognome = ' '.join(tokens[0:2])
                nome = ' '.join(tokens[2:])
                return cognome.strip(), nome.strip()
            # otherwise first token is surname
            return tokens[0].strip(), ' '.join(tokens[1:]).strip()
        else:
            # mode == 'last'
            # If penultimate token is a prefix, include it in the surname (e.g. "Maria De Rosa")
            if len(tokens) >= 3 and clean(tokens[-2]) in prefixes:
                cognome = ' '.join(tokens[-2:])
                nome = ' '.join(tokens[:-2])
                return cognome.strip(), nome.strip()
            # otherwise last token is surname
            return tokens[-1].strip(), ' '.join(tokens[:-1]).strip()
    
    def _execute_import(self):
        """Execute the import process"""
        try:
            from database import exec_query, fetch_one
            from csv_import import apply_mapping
            import sqlite3

            # Ask user which name-splitting strategy to use when `cognome` is missing
            def _ask_name_split_mode():
                dlg = tk.Toplevel(self.win)
                dlg.title("Strategia split nome/cognome")
                dlg.transient(self.win)
                dlg.grab_set()
                var = tk.StringVar(value="first")
                ttk.Label(dlg, text="Se il CSV contiene un unico campo con 'COGNOME NOME', come dividerlo?").pack(padx=10, pady=8)
                ttk.Radiobutton(dlg, text="Primo token = Cognome (es. 'ROSSI PAOLA')", variable=var, value="first").pack(anchor="w", padx=20, pady=2)
                ttk.Radiobutton(dlg, text="Ultimo token = Cognome (es. 'Paola Rossi')", variable=var, value="last").pack(anchor="w", padx=20, pady=2)
                btn_frame = ttk.Frame(dlg)
                btn_frame.pack(pady=10)
                res = {}
                def _ok():
                    res['mode'] = var.get()
                    dlg.destroy()
                def _cancel():
                    res['mode'] = None
                    dlg.destroy()
                ttk.Button(btn_frame, text="OK", command=_ok).pack(side=tk.LEFT, padx=5)
                ttk.Button(btn_frame, text="Annulla", command=_cancel).pack(side=tk.LEFT, padx=5)
                self.win.wait_window(dlg)
                return res.get('mode', None)

            name_split_mode = _ask_name_split_mode()
            if name_split_mode is None:
                # User cancelled split choice -> abort import
                messagebox.showinfo("Importazione", "Importazione annullata dall'utente.")
                return

            # Apply mapping to data (returns list of dicts)
            mapping_cast = {k: (v if v is not None else None) for k, v in self.mapping.items()}
            # Ensure any mapping that pointed to 'attivo' is ignored
            if 'attivo' in mapping_cast:
                mapping_cast.pop('attivo', None)
            mapped_rows = apply_mapping(self.rows, mapping_cast)

            def _voto_to_bool(v):
                if v is None:
                    return None
                s = str(v).strip()
                if s in ('1', 'True', 'true'):
                    return 1
                if s in ('0', 'False', 'false'):
                    return 0
                return None
            # Apply attivo rule per user specification:
            # - If Voto == 1 => Attivo = 1
            # - If Voto == 0 and Q0 != NULL => Attivo = 1
            # - If Voto == 0 and Q0 == NULL => Attivo = 0
            # Leave Attivo unchanged when Voto is None (no information)
            def _is_present(val):
                return val is not None and str(val).strip() != ""

            for r in mapped_rows:
                voto_val = _voto_to_bool(r.get('voto'))
                q0_val = r.get('q0')

                if voto_val == 1:
                    r['attivo'] = 1
                elif voto_val == 0:
                    if _is_present(q0_val):
                        r['attivo'] = 1
                    else:
                        r['attivo'] = 0
                else:
                    # No voto information -> do not set/modify 'attivo'
                    if 'attivo' in r:
                        del r['attivo']

            total = len(mapped_rows)
            if total == 0:
                messagebox.showwarning("Importazione", "Nessuna riga da importare.")
                return

            # Ask user for global duplicate/update strategy before importing
            # Options: 'status_only' (update only attivo/voto),
            # otherwise user will be asked on first duplicate whether to update only empty fields or overwrite all fields.
            duplicate_strategy = None  # 'update_empty' or 'overwrite' or 'status_only'
            res = messagebox.askyesnocancel(
                "Modalità aggiornamento",
                "Scegli modalità di aggiornamento:\n"
                "'Sì' = Aggiorna solo Stato e Voto\n"
                "'No' = Alla prima anomalia scegli tra: Aggiorna solo i campi vuoti / Sovrascrivi tutti i campi\n"
                "'Annulla' = Annulla importazione"
            )
            if res is None:
                messagebox.showinfo("Importazione", "Importazione annullata dall'utente.")
                return
            if res is True:
                duplicate_strategy = 'status_only'

            self.import_count = 0
            for i, row in enumerate(mapped_rows):
                # Update progress
                progress = int((i / total) * 100)
                self.progress["value"] = progress
                self.progress_text.config(text=f"Importazione: {i+1}/{total}")
                self.win.update()

                try:
                    # If CSV provides a single 'nome' field containing both surname and given name
                    # (e.g. 'ROSSI PAOLA') and 'cognome' mapping is empty/None, attempt to split with heuristics.
                    nome_val = row.get('nome')
                    cognome_val = row.get('cognome')
                    if (cognome_val is None or str(cognome_val).strip() == "") and nome_val:
                        cognome, nome = self._split_name(nome_val, name_split_mode)
                        if cognome:
                            row['cognome'] = cognome
                            row['nome'] = nome

                    # Determine matricola and check existing record to avoid IntegrityError
                    matricola = row.get('matricola')
                    existing = None
                    if matricola:
                        existing = fetch_one("SELECT * FROM soci WHERE matricola=?", (matricola,))

                    if existing:
                        # Handle duplicate according to chosen strategy
                        if duplicate_strategy is None:
                            res = messagebox.askyesnocancel(
                                "Duplicato trovato",
                                "È stato trovato un socio con la stessa 'matricola'.\n"
                                "Scegli: 'Sì' = Aggiorna solo i campi vuoti; 'No' = Sovrascrivi tutti i campi; 'Annulla' = Interrompi importazione."
                            )
                            if res is None:
                                messagebox.showinfo("Importazione", "Importazione annullata dall'utente.")
                                return
                            duplicate_strategy = 'update_empty' if res else 'overwrite'

                        update_cols = []
                        update_vals = []
                        if duplicate_strategy == 'status_only':
                            for col in ('attivo', 'voto'):
                                # Check if field is selected for update
                                if not self.selected_fields.get(col, True):
                                    continue
                                val = row.get(col)
                                if val is not None and str(val).strip() != "":
                                    update_cols.append(f"{col}=?")
                                    update_vals.append(val)
                        else:
                            for col, val in row.items():
                                if col == 'id':
                                    continue
                                    
                                # Check if field is selected for update (matricola always allowed)
                                if col != 'matricola' and not self.selected_fields.get(col, True):
                                    continue
                                    
                                # Use the value provided in the mapped row for 'attivo' (do not force)
                                if col == 'attivo':
                                    if val is not None and str(val).strip() != "":
                                        update_cols.append(f"{col}=?")
                                        update_vals.append(val)
                                    continue

                                if duplicate_strategy == 'overwrite':
                                    if val is not None and str(val).strip() != "":
                                        update_cols.append(f"{col}=?")
                                        update_vals.append(val)
                                else:  # update_empty
                                    # only update if existing value is empty
                                    try:
                                        existing_val = existing[col]
                                    except Exception:
                                        existing_val = None
                                    if (existing_val is None or str(existing_val).strip() == "") and val:
                                        update_cols.append(f"{col}=?")
                                        update_vals.append(val)

                        if update_cols:
                            sql_upd = f"UPDATE soci SET {', '.join(update_cols)} WHERE matricola=?"
                            exec_query(sql_upd, update_vals + [matricola])
                            self.import_count += 1
                        else:
                            logger.debug("No fields to update for matricola %s", matricola)
                    else:
                        # Insert new record (only non-empty and selected fields)
                        cols = []
                        for k, v in row.items():
                            if v is not None and str(v).strip() != "":
                                # Check if field is selected (matricola always included)
                                if k == 'matricola' or self.selected_fields.get(k, True):
                                    cols.append(k)
                        if not cols:
                            continue
                        placeholders = ["?" for _ in cols]
                        sql = f"INSERT INTO soci ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                        params = [row[c] for c in cols]
                        exec_query(sql, params)
                        self.import_count += 1
                except Exception as e:
                    logger.error("Unexpected error importing row %s: %s", i, e)
                    continue

            # Complete
            self.progress["value"] = 100
            self.progress_text.config(text="Importazione completata!")
            messagebox.showinfo("Importazione", f"{self.import_count} soci importati/aggiornati con successo.")

            # Callback
            if self.on_complete_callback:
                self.on_complete_callback(self.import_count)

            # Close wizard
            self.win.after(1000, self.win.destroy)
        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante l'importazione: {e}")
            logger.error(f"Import failed: {e}", exc_info=True)
    
    def _show_page(self):
        """Display current page"""
        # Clear content
        for child in self.content_frame.winfo_children():
            child.destroy()
        
        # Build page
        title, builder = self.pages[self.current_page]
        self.title_label.config(text=title)
        builder()
        
        # Update buttons
        self.btn_prev.config(state=tk.NORMAL if self.current_page > 0 else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if self.current_page < len(self.pages) - 1 else tk.DISABLED)
        
        # On last page, next becomes Import
        if self.current_page == len(self.pages) - 1:
            self.btn_next.config(text="Importa", state=tk.NORMAL)
        else:
            self.btn_next.config(text="Avanti")
        
        # Update progress
        self.progress_label.config(text=f"Pagina {self.current_page + 1} di {len(self.pages)}")
    
    def _next_page(self):
        """Go to next page"""
        if self.current_page == len(self.pages) - 1:
            self._execute_import()
        else:
            # Validate current page before proceeding
            if self.current_page == 0 and not self.csv_path:
                messagebox.showwarning("Validazione", "Selezionare un file CSV.")
                return
            
            if self.current_page == 1:
                # Extract mapping and field selection from page 2
                if hasattr(self, 'mapping_widgets'):
                    for field, combo in self.mapping_widgets.items():
                        val = combo.get()
                        if val:
                            self.mapping[field] = val
                
                if hasattr(self, 'field_checkboxes'):
                    self.selected_fields = {}
                    for field_key, var in self.field_checkboxes.items():
                        self.selected_fields[field_key] = var.get()
            
            self.current_page += 1
            self._show_page()
    
    def _prev_page(self):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self._show_page()
    
    def _cancel(self):
        """Cancel wizard"""
        if messagebox.askyesno("Annulla", "Annullare l'importazione?"):
            self.win.destroy()
