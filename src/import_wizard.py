# -*- coding: utf-8 -*-
"""
CSV Import Wizard orchestrator for GLR Gestione Locale Radioamatori
Manages the complete import workflow: File → Preset → Mapping → Preview → Insert
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
import csv

# Configure logging for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler('import_wizard.log', mode='a', encoding='utf-8')  # Log to file
    ]
)

logger = logging.getLogger("import_wizard")

class ImportWizard:
    @staticmethod
    def bind_import_shortcut(root, callback):
        """Associa Ctrl+I per avviare il wizard di importazione CSV."""
        def _on_ctrl_i(event):
            callback()
            return "break"
        root.bind_all('<Control-i>', _on_ctrl_i)
    def _clean_row(self, row):
        """Converte una riga in lista di stringhe, pad con '' se necessario."""
        if row is None:
            return []
        if not hasattr(row, '__getitem__'):
            row = [str(row)]
        else:
            row = list(row)
        return [str(x).strip() if x is not None else '' for x in row]

    def _remove_duplicate_header(self):
        """Rimuove header duplicato se presente come prima riga dei dati. Ritorna True se rimosso."""
        if hasattr(self, 'rows') and hasattr(self, 'headers') and self.rows and self.headers:
            first_row = self._clean_row(self.rows[0])[:len(self.headers)]
            headers_clean = [str(h).strip() for h in self.headers]
            if first_row == headers_clean:
                logger.info("Headers found as first row, removing from data rows")
                self.rows = self.rows[1:]
                logger.info(f"Rows after header removal: {len(self.rows)}")
                return True
        return False

    def _pad_row(self, row, target_len, fill_last_with_ellipsis=False):
        """Pad a row to target_len, optionally fill last col with '...' if needed."""
        padded_row = list(row[:target_len])
        while len(padded_row) < target_len:
            if fill_last_with_ellipsis and len(padded_row) == target_len - 1:
                padded_row.append("...")
            else:
                padded_row.append('')
        return padded_row
    """Main import wizard dialog - manages the complete import process"""
    
    def __init__(self, parent, on_complete_callback=None):
        """
        Initialize the import wizard
        
        Args:
            parent: Parent window
            on_complete_callback: Function to call when import completes (passes count)
        """
        logger.info("Initializing ImportWizard")
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
        self.win.geometry("760x680")
        self.win.transient(parent)
        self.win.grab_set()

        try:
            from v4_ui.styles import ensure_app_named_fonts

            ensure_app_named_fonts(self.win.winfo_toplevel())
        except Exception:
            pass
        
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
        logger.info("ImportWizard initialized successfully")
    
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
        preview_frame = ttk.LabelFrame(frame, text="Anteprima file CSV")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(preview_frame)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        h_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tv_file_preview = ttk.Treeview(
            preview_frame, show="headings", columns=(), height=8,
            yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set
        )
        self.tv_file_preview.column("#0", width=0, stretch=False)  # Hide the default column
        v_scrollbar.config(command=self.tv_file_preview.yview)
        h_scrollbar.config(command=self.tv_file_preview.xview)
        self.tv_file_preview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
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
        canvas = tk.Canvas(mapping_frame, height=380)
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
        ttk.Label(header_frame, text="✓", font="AppBold", width=3).pack(side=tk.LEFT, padx=2)
        ttk.Label(header_frame, text="Campo database", font="AppBold", width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Colonna CSV", font="AppBold").pack(side=tk.LEFT, padx=5)
        
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
        
        self.progress_text = ttk.Label(frame, text="Premi 'Avvia importazione' per iniziare")
        self.progress_text.pack(pady=10)
        
        
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

        # Ensure all optional fields start selected by default
        for field_key, var in self.field_checkboxes.items():
            if field_key != 'matricola':
                var.set(True)

    def _select_all_fields(self):
        """Select every optional field checkbox (matricola remains enforced)."""
        if not hasattr(self, 'field_checkboxes'):
            return
        for field_key, var in self.field_checkboxes.items():
            if field_key != 'matricola':
                var.set(True)

    def _deselect_all_fields(self):
        """Deselect every optional field checkbox (matricola remains enforced)."""
        if not hasattr(self, 'field_checkboxes'):
            return
        for field_key, var in self.field_checkboxes.items():
            if field_key != 'matricola':  # Skip matricola as it's disabled
                var.set(False)

    def _on_mapping_change(self, event):
        """Keep self.mapping synced with combo selections."""
        if not hasattr(self, 'mapping_widgets'):
            return
        widget = getattr(event, 'widget', None)
        if widget is None:
            return
        target_field = next((field for field, combo in self.mapping_widgets.items() if combo is widget), None)
        if target_field is None:
            return
        value = widget.get().strip()
        if value:
            self.mapping[target_field] = value
        else:
            self.mapping.pop(target_field, None)
    
    def _select_file(self):
        """File selection"""
        logger.info("Opening file selection dialog")
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            logger.info("File selection cancelled")
            return
        
        logger.info(f"Selected file: {path}")
        try:
            from csv_import import sniff_delimiter, read_csv_file, auto_detect_mapping
            
            self.csv_path = path
            
            # Detect delimiter
            self.delimiter = sniff_delimiter(path)
            self.delim_label.config(text=f"Rilevato: {repr(self.delimiter)}")
            logger.info(f"Detected delimiter: {repr(self.delimiter)}")
            
            # Load CSV
            self.headers, self.rows = read_csv_file(path, self.delimiter)
            logger.info(f"Loaded CSV: {len(self.headers)} headers, {len(self.rows)} rows")
            logger.debug(f"Headers: {self.headers}")
            logger.debug(f"First 3 rows: {self.rows[:3] if self.rows else 'No rows'}")
            
            # Rimuovi header duplicato se presente e mostra solo i dati veri
            header_removed = self._remove_duplicate_header()
            
            # Update file label
            self.file_label.config(text=path, foreground="black")
            
            # Update preview
            if not self.headers:
                logger.warning("No headers found in CSV file")
                # No headers, show message
                self.tv_file_preview['columns'] = ['message']
                self.tv_file_preview.heading('message', text='Messaggio')
                self.tv_file_preview.column('message', width=300)
                for item in self.tv_file_preview.get_children():
                    self.tv_file_preview.delete(item)
                self.tv_file_preview.insert("", tk.END, values=['Nessuna intestazione trovata nel file CSV'])
                return
            
            # Limit to first 10 columns to avoid overly wide display
            display_headers = self.headers[:10]
            if len(self.headers) > 10:
                display_headers.append("...")  # Indicate truncation
                logger.info(f"Truncated headers to first 10 columns (total: {len(self.headers)})")
            
            self.tv_file_preview['columns'] = display_headers
            logger.debug(f"Display headers: {display_headers}")
            
            # Calculate column widths based on content
            max_lengths = {}
            for header in display_headers:
                if header != "...":
                    max_lengths[header] = len(str(header))
                else:
                    max_lengths[header] = 3
            
            # Check first 5 rows for max lengths
            for row in self.rows[:5]:
                clean_row = self._clean_row(row)
                for i, value in enumerate(clean_row[:10]):  # Only check first 10 columns
                    if i < len(display_headers) and display_headers[i] != "...":
                        header = display_headers[i]
                        max_lengths[header] = max(max_lengths[header], len(str(value) if value is not None else ''))
            
            # Set headings and column widths (min 80, max 200 pixels)
            for col in display_headers:
                self.tv_file_preview.heading(col, text=col)
                width = min(max(max_lengths[col] * 8, 80), 200)  # Rough char to pixel conversion
                self.tv_file_preview.column(col, width=width, minwidth=50)
            
            # Clear existing items
            for item in self.tv_file_preview.get_children():
                self.tv_file_preview.delete(item)
            
            # Insert first 5 data rows (headers are already shown as column headings)
            if not self.rows:
                logger.warning("No data rows found in CSV file")
                self.tv_file_preview.insert("", tk.END, values=['Nessun dato trovato nel file CSV'] + [''] * (len(display_headers) - 1))
            else:
                logger.info(f"Inserting first {min(5, len(self.rows))} data rows into preview")
                fill_last = ("..." in display_headers)
                # Convert dict rows to value lists in header order for preview
                for row in self.rows[:5]:
                    if isinstance(row, dict):
                        # Use self.headers for column order, not display_headers (which may be truncated)
                        values = [str(row.get(h, '')) if row.get(h, '') is not None else '' for h in self.headers[:10]]
                    else:
                        values = [str(val) if val is not None else '' for val in self._clean_row(row)[:10]]
                    padded_row = self._pad_row(values, len(display_headers), fill_last_with_ellipsis=fill_last)
                    self.tv_file_preview.insert("", tk.END, values=padded_row)
            
            # Enable click-to-sort on the headers (only for actual columns)
            sortable_cols = [col for col in display_headers if col != "..."]
            try:
                self._make_treeview_sortable(self.tv_file_preview, sortable_cols)
                logger.debug("Enabled sorting on columns")
            except Exception as e:
                logger.error(f"Failed to enable sorting: {e}")
            
            # Auto-detect mapping
            self.mapping = auto_detect_mapping(self.headers)
            logger.info("Auto-detected mapping completed")
            
            logger.info(f"Loaded CSV: {len(self.rows)} rows, {len(self.headers)} columns")
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}", exc_info=True)
            messagebox.showerror("Errore", f"Errore caricamento file: {e}")
    
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
        logger.info("Starting detailed import execution")
        try:
            from soci_import_engine import fetch_socio_by_matricola, insert_socio, update_socio_by_matricola
            from csv_import import apply_mapping

            # Ask user which name-splitting strategy to use when `cognome` is missing
            def _ask_name_split_mode():
                dlg = tk.Toplevel(self.win)
                dlg.title("Divisione Nome/Cognome")
                dlg.transient(self.win)
                dlg.grab_set()
                var = tk.StringVar(value="first")
                ttk.Label(
                    dlg,
                    text=(
                        "Nel CSV c'è un solo campo con Nome e Cognome insieme.\n"
                        "Scegli l'ordine con cui sono scritti nel campo:"
                    ),
                ).pack(padx=10, pady=8)
                ttk.Radiobutton(
                    dlg,
                    text="Cognome prima (es. 'ROSSI PAOLA' o 'ROSSI MARIA PAOLA')",
                    variable=var,
                    value="first",
                ).pack(anchor="w", padx=20, pady=2)
                ttk.Radiobutton(
                    dlg,
                    text="Nome prima (es. 'Paola Rossi' o 'Maria Paola Rossi')",
                    variable=var,
                    value="last",
                ).pack(anchor="w", padx=20, pady=2)

                ttk.Label(
                    dlg,
                    text=(
                        "Nota: se il cognome è composto (es. 'De Luca'), questa scelta può non essere affidabile;\n"
                        "se possibile usa colonne separate per Nome e Cognome."
                    ),
                    foreground="#666",
                ).pack(padx=10, pady=(6, 0))
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
                logger.info("Import cancelled by user during name split mode selection")
                messagebox.showinfo("Importazione", "Importazione annullata dall'utente.")
                return

            logger.info(f"Name split mode selected: {name_split_mode}")
            
            # Apply mapping to data (returns list of dicts)
            mapping_cast = {k: (v if v is not None else None) for k, v in self.mapping.items()}
            # Ensure any mapping that pointed to 'attivo' is ignored
            if 'attivo' in mapping_cast:
                mapping_cast.pop('attivo', None)
            mapped_rows = apply_mapping(self.rows, mapping_cast)
            logger.info(f"Applied mapping to {len(mapped_rows)} rows")

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

            # Calculate data_scadenza if data_iscrizione is present but data_scadenza is not
            # Membership validity is 3 years from inscription date
            for r in mapped_rows:
                if r.get('data_iscrizione') and not r.get('data_scadenza'):
                    try:
                        from datetime import datetime, timedelta
                        iscrizione_date = datetime.fromisoformat(r['data_iscrizione'])
                        scadenza_date = iscrizione_date + timedelta(days=365*3)  # 3 years
                        r['data_scadenza'] = scadenza_date.date().isoformat()
                    except Exception as e:
                        logger.warning(f"Could not calculate scadenza for iscrizione {r.get('data_iscrizione')}: {e}")

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
                "Come vuoi gestire i soci già presenti (duplicati)?\n\n"
                "Premi 'Sì' per aggiornare SOLO 'Stato' e 'Voto' (non modifica gli altri campi).\n\n"
                "Premi 'No' per decidere caso per caso: al primo duplicato ti verrà chiesto se\n"
                "- aggiornare solo i campi vuoti\n"
                "- sovrascrivere tutti i campi\n\n"
                "Premi 'Annulla' per interrompere l'importazione."
            )
            if res is None:
                logger.info("Import cancelled by user during duplicate strategy selection")
                messagebox.showinfo("Importazione", "Importazione annullata dall'utente.")
                return
            if res is True:
                duplicate_strategy = 'status_only'
                logger.info("Duplicate strategy set to: status_only")

            logger.info(f"Starting import of {total} records")
            self.import_count = 0
            for i, row in enumerate(mapped_rows):
                # Update progress
                progress = int((i / total) * 100)
                self.progress["value"] = progress
                self.progress_text.config(text=f"Importazione: {i+1}/{total}")
                self.win.update()

                try:
                    matricola = row.get('matricola')
                    logger.debug(f"Processing row {i+1}: matricola={matricola}")
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
                        existing = fetch_socio_by_matricola(str(matricola))

                    if existing:
                        # Handle duplicate according to chosen strategy
                        if duplicate_strategy is None:
                            res = messagebox.askyesnocancel(
                                "Duplicato trovato",
                                "È stato trovato un socio con la stessa 'matricola'.\n\n"
                                "Come vuoi aggiornare i dati?\n\n"
                                "Premi 'Sì' per aggiornare SOLO i campi vuoti (non sovrascrive quelli già compilati).\n\n"
                                "Premi 'No' per SOVRASCRIVERE tutti i campi con i valori del CSV.\n\n"
                                "Premi 'Annulla' per interrompere l'importazione."
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
                            updates = {}
                            for part, v in zip(update_cols, update_vals):
                                try:
                                    colname = part.split("=")[0]
                                except Exception:
                                    continue
                                updates[colname] = v
                            update_socio_by_matricola(
                                matricola=str(matricola),
                                updates=updates,
                                write_enabled=True,
                                keep_empty_strings=False,
                            )
                            self.import_count += 1
                            logger.debug(f"Updated existing socio matricola {matricola}")
                        else:
                            logger.debug("No fields to update for matricola %s", matricola)
                    else:
                        # Insert new record (only non-empty and selected fields)
                        payload = {}
                        for k, v in row.items():
                            if v is None or str(v).strip() == "":
                                continue
                            if k == 'matricola' or self.selected_fields.get(k, True):
                                payload[k] = v
                        if not payload:
                            continue
                        insert_socio(payload, write_enabled=True)
                        self.import_count += 1
                        logger.debug(f"Inserted new socio matricola {matricola}")
                except Exception as e:
                    logger.error("Unexpected error importing row %s: %s", i, e)
                    continue

            # Complete
            self.progress["value"] = 100
            self.progress_text.config(text="Importazione completata!")
            messagebox.showinfo("Importazione", f"{self.import_count} soci importati/aggiornati con successo.")
            logger.info(f"Import completed successfully: {self.import_count} records imported/updated")

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
            self.btn_next.config(text="Avvia importazione", state=tk.NORMAL)
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
