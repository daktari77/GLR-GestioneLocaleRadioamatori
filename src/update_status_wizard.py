# -*- coding: utf-8 -*-
"""
Update Status Wizard - Aggiorna Voto e Quote (Q0, Q1, Q2) in batch
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging

logger = logging.getLogger("librosoci")

class UpdateStatusWizard:
    """Wizard to update member status fields (Voto, Q0, Q1, Q2) from CSV"""
    
    def __init__(self, parent, on_complete_callback=None):
        self.parent = parent
        self.on_complete_callback = on_complete_callback
        
        # State
        self.csv_path = None
        self.delimiter = None
        self.headers = []
        self.rows = []
        self.mapping = {}
        self.update_count = 0
        self.inserted_count = 0
        self.skipped_count = 0

        # Options
        self.dry_run_var = tk.BooleanVar(value=False)
        
        # Create window
        self.win = tk.Toplevel(parent)
        self.win.title("Aggiorna Stato Soci - Voto e Quote")
        self.win.geometry("800x700")
        self.win.transient(parent)
        self.win.grab_set()

        try:
            from v4_ui.styles import ensure_app_named_fonts

            ensure_app_named_fonts(self.win.winfo_toplevel())
        except Exception:
            pass
        
        # Pages
        self.current_page = 0
        self.pages = [
            ("1. Seleziona File CSV", self._build_page_file),
            ("2. Configura Mapping", self._build_page_mapping),
            ("3. Conferma e Aggiorna", self._build_page_execute),
        ]
        
        self._setup_ui()
        # React to dry-run toggle (button label on last page)
        try:
            self.dry_run_var.trace_add("write", lambda *_: self._update_execute_button_label())
        except Exception:
            pass
        self._show_page()

    def _update_execute_button_label(self):
        """Update the label of the final action button based on dry-run."""
        try:
            if self.current_page == len(self.pages) - 1:
                self.btn_next.config(text=("Anteprima" if bool(self.dry_run_var.get()) else "Aggiorna"))
                self._update_execute_warning_text()
        except Exception:
            return

    def _update_execute_warning_text(self):
        """Update warning text on execute page based on dry-run."""
        try:
            if self.current_page != len(self.pages) - 1:
                return
            if not hasattr(self, "execute_warning_label"):
                return
            if not self.execute_warning_label.winfo_exists():
                return
            if bool(self.dry_run_var.get()):
                self.execute_warning_label.config(text="ℹ️ Modalità anteprima: nessuna modifica verrà salvata nel DB")
            else:
                self.execute_warning_label.config(text="⚠️ Premi 'Aggiorna' per sovrascrivere i campi Voto e Quote")
        except Exception:
            return
    
    def _setup_ui(self):
        """Setup main UI structure"""
        # Main container
        main_frame = ttk.Frame(self.win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        self.title_label = ttk.Label(main_frame, text="", font=("Segoe UI", 12, "bold"))
        self.title_label.pack(pady=(0, 10))
        
        # Content area
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.btn_prev = ttk.Button(btn_frame, text="← Indietro", command=self._prev_page)
        self.btn_prev.pack(side=tk.LEFT)
        
        self.btn_next = ttk.Button(btn_frame, text="Avanti →", command=self._next_page)
        self.btn_next.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Button(btn_frame, text="Annulla", command=self._cancel).pack(side=tk.RIGHT)
        
        # Progress
        self.progress_label = ttk.Label(main_frame, text="")
        self.progress_label.pack(pady=(10, 0))
    
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
        
        if self.current_page == len(self.pages) - 1:
            self._update_execute_button_label()
            self.btn_next.config(state=tk.NORMAL)
        else:
            self.btn_next.config(text="Avanti →", state=tk.NORMAL)
        
        # Progress
        self.progress_label.config(text=f"Pagina {self.current_page + 1} di {len(self.pages)}")
    
    def _build_page_file(self):
        """Page 1: File selection"""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Seleziona il file CSV contenente i dati aggiornati di Voto e Quote",
                 font=("Segoe UI", 10)).pack(pady=20)
        
        # File selection
        file_frame = ttk.Frame(frame)
        file_frame.pack(fill=tk.X, pady=20)
        
        ttk.Label(file_frame, text="File CSV:").pack(anchor="w")
        
        select_frame = ttk.Frame(file_frame)
        select_frame.pack(fill=tk.X, pady=5)
        
        self.file_var = tk.StringVar(value=self.csv_path or "Nessun file selezionato")
        file_entry = ttk.Entry(select_frame, textvariable=self.file_var, state="readonly")
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        ttk.Button(select_frame, text="Sfoglia...", command=self._select_file).pack(side=tk.RIGHT)
        
        # File info
        info_frame = ttk.LabelFrame(frame, text="Informazioni File")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        self.info_text = tk.Text(info_frame, height=15, wrap=tk.WORD, font=("Courier", 9))
        info_scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=info_scroll.set)
        
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5), pady=5)
        
        self.info_text.insert("1.0", "Seleziona un file CSV contenente almeno:\n" +
                              "- Colonna identificativa (Matricola o Nominativo)\n" +
                              "- Una o più colonne tra: Voto, Q0, Q1, Q2")
        self.info_text.config(state=tk.DISABLED)
    
    def _build_page_mapping(self):
        """Page 2: Field mapping"""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Help text
        help_frame = ttk.Frame(frame)
        help_frame.pack(fill=tk.X, pady=(0, 10))
        
        help_text = ("📋 Istruzioni:\n"
                    "1. Mappa la colonna identificativa (Matricola o Nominativo)\n"
                    "2. Mappa i campi che vuoi aggiornare (Voto, Q0, Q1, Q2)\n"
                    "3. I valori nel CSV sovrascriveranno TUTTI i valori esistenti")
        ttk.Label(
            help_frame,
            text=help_text,
            foreground="blue",
            font="AppNormal",
            justify=tk.LEFT,
        ).pack(anchor="w", padx=10)
        
        # Mapping area
        map_frame = ttk.LabelFrame(frame, text="Mapping Colonne")
        map_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Scrollable area
        canvas = tk.Canvas(map_frame, height=400)
        scrollbar = ttk.Scrollbar(map_frame, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Headers
        hdr_frame = ttk.Frame(scroll_frame)
        hdr_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(hdr_frame, text="Campo Database", width=25, font="AppBold").pack(side=tk.LEFT, padx=5)
        ttk.Label(hdr_frame, text="Colonna CSV", font="AppBold").pack(side=tk.LEFT, padx=5)
        
        # Create mapping widgets
        self.mapping_widgets = {}
        
        fields = [
            ("matricola", "Matricola (identificativo)", True),
            ("nominativo", "Nominativo (identificativo)", False),
            ("voto", "Voto (1/0, Sì/No)", False),
            ("q0", "Q0 - Quota Anno Corrente", False),
            ("q1", "Q1 - Quota Anno -1", False),
            ("q2", "Q2 - Quota Anno -2", False),
        ]
        
        csv_options = [""] + (self.headers if self.headers else [])
        
        for field_key, field_label, is_bold in fields:
            row_frame = ttk.Frame(scroll_frame)
            row_frame.pack(fill=tk.X, padx=5, pady=3)
            
            # Label
            label_font = "AppBold" if is_bold else "AppNormal"
            ttk.Label(row_frame, text=field_label, width=25, font=label_font).pack(side=tk.LEFT, padx=5)
            
            # Combobox
            combo = ttk.Combobox(row_frame, values=csv_options, state="readonly", width=30)
            combo.pack(side=tk.LEFT, padx=5)
            self.mapping_widgets[field_key] = combo
        
        # Auto-detect button
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Auto-rileva Mapping", command=self._auto_detect).pack()
        
        # Note
        note_frame = ttk.Frame(frame)
        note_frame.pack(fill=tk.X, pady=5)
        
        note_text = ("⚠️ ATTENZIONE: L'aggiornamento sovrascriverà TUTTI i valori esistenti di Voto, Q0, Q1 e Q2\n"
                    "per i soci trovati nel file CSV. Assicurati che il file contenga i dati corretti.")
        ttk.Label(note_frame, text=note_text, foreground="red", font=("Segoe UI", 8, "bold"), 
                 wraplength=750, justify=tk.LEFT).pack(padx=10)
    
    def _build_page_execute(self):
        """Page 3: Confirm and execute"""
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Conferma aggiornamento stato soci", 
                 font=("Segoe UI", 12, "bold")).pack(pady=20)
        
        # Summary
        summary_frame = ttk.LabelFrame(frame, text="Riepilogo Aggiornamento")
        summary_frame.pack(fill=tk.X, pady=20, padx=20)
        
        if self.csv_path:
            import os
            ttk.Label(summary_frame, text=f"📄 File: {os.path.basename(self.csv_path)}", 
                     font="AppBold").pack(anchor="w", padx=10, pady=5)
            ttk.Label(summary_frame, text=f"📊 Righe da processare: {len(self.rows)}").pack(anchor="w", padx=10, pady=5)
            
            # Show mapped fields
            mapped = [k for k, v in self.mapping.items() if v]
            if mapped:
                ttk.Label(summary_frame, text=f"🔗 Campi mappati:").pack(anchor="w", padx=10, pady=(10, 2))
                fields_text = ""
                for field in mapped:
                    fields_text += f"  • {field} → {self.mapping[field]}\n"
                ttk.Label(summary_frame, text=fields_text, font=("Segoe UI", 8), 
                         foreground="darkgreen").pack(anchor="w", padx=25, pady=(0, 5))
        
        # Warning
        warning_frame = ttk.Frame(frame)
        warning_frame.pack(fill=tk.X, pady=10, padx=20)
        self.execute_warning_label = ttk.Label(
            warning_frame,
            text="⚠️ Premi 'Aggiorna' per sovrascrivere i campi Voto e Quote",
            foreground="red",
            font="AppBold",
        )
        self.execute_warning_label.pack()

        # Dry-run option
        dry_frame = ttk.Frame(frame)
        dry_frame.pack(fill=tk.X, pady=(5, 0), padx=20)
        ttk.Checkbutton(
            dry_frame,
            text="Solo anteprima (non modifica il DB)",
            variable=self.dry_run_var,
        ).pack(anchor="w")
        self._update_execute_button_label()
        self._update_execute_warning_text()
        
        # Progress
        prog_frame = ttk.Frame(frame)
        prog_frame.pack(fill=tk.X, pady=30, padx=50)
        
        self.progress = ttk.Progressbar(prog_frame, mode="determinate")
        self.progress.pack(fill=tk.X)
        
        self.progress_text = ttk.Label(prog_frame, text="Pronto per l'aggiornamento")
        self.progress_text.pack(pady=10)
    
    def _select_file(self):
        """Select CSV file"""
        path = filedialog.askopenfilename(
            title="Seleziona file CSV",
            filetypes=[("File CSV", "*.csv"), ("Tutti i file", "*.*")]
        )
        
        if path:
            self.csv_path = path
            self.file_var.set(path)
            self._load_csv()
    
    def _load_csv(self):
        """Load and preview CSV"""
        try:
            if not self.csv_path:
                return
            
            # Read file
            from csv_import import read_csv_file, sniff_delimiter
            
            # Detect delimiter
            self.delimiter = sniff_delimiter(self.csv_path)
            
            # Read CSV
            result = read_csv_file(self.csv_path, delimiter=self.delimiter)
            
            if result and len(result) == 2:
                self.headers, self.rows = result
            else:
                raise ValueError("Impossibile leggere il file CSV")
            
            if not self.headers or not self.rows:
                raise ValueError("File CSV vuoto o formato non valido")
            
            # Populate file info
            self._populate_file_info()
            
            logger.info(f"Loaded CSV: {len(self.rows)} rows, {len(self.headers)} columns")
            
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            messagebox.showerror("Errore", f"Errore caricamento file:\n{e}")
    
    def _populate_file_info(self):
        """Populate file info text widget"""
        if not hasattr(self, 'info_text') or not self.info_text.winfo_exists():
            return
        
        if not self.csv_path:
            return
        
        try:
            import os
            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete("1.0", tk.END)
            
            info = f"File: {os.path.basename(self.csv_path)}\n"
            info += f"Righe: {len(self.rows)}\n"
            info += f"Colonne: {len(self.headers)}\n"
            info += f"Delimitatore: {repr(self.delimiter)}\n\n"
            info += "Colonne trovate:\n"
            
            for i, header in enumerate(self.headers, 1):
                info += f"{i:2}. {header}\n"
            
            info += "\n--- Anteprima prime 5 righe ---\n\n"
            
            for i, row in enumerate(self.rows[:5]):
                info += f"Riga {i+1}:\n"
                for header in self.headers:
                    value = row.get(header, "")
                    info += f"  {header}: {value}\n"
                info += "\n"
            
            self.info_text.insert("1.0", info)
            self.info_text.config(state=tk.DISABLED)
        except Exception as e:
            logger.error(f"Error populating file info: {e}")
    
    def _auto_detect(self):
        """Auto-detect mapping"""
        if not self.headers:
            messagebox.showwarning("Attenzione", "Carica prima un file CSV")
            return
        
        try:
            # Simple auto-detect for common column names
            auto_map = {}
            headers_lower = {h.lower(): h for h in self.headers}
            
            patterns = {
                'matricola': {'matricola', 'id', 'member_id'},
                'nominativo': {'nominativo', 'callsign', 'call'},
                'voto': {'voto', 'vote', 'voter'},
                'q0': {'q0', 'quota0', 'causale0'},
                'q1': {'q1', 'quota1', 'causale1'},
                'q2': {'q2', 'quota2', 'causale2'},
            }
            
            for field, pattern_set in patterns.items():
                for pattern in pattern_set:
                    if pattern in headers_lower:
                        auto_map[field] = headers_lower[pattern]
                        break
            
            # Update widgets
            for field, combo in self.mapping_widgets.items():
                if field in auto_map:
                    combo.set(auto_map[field])
                else:
                    combo.set("")
            
        except Exception as e:
            logger.error(f"Auto-detect failed: {e}")
            messagebox.showerror("Errore", f"Errore auto-rilevamento:\n{e}")
    
    def _next_page(self):
        """Go to next page or execute update"""
        if self.current_page == len(self.pages) - 1:
            self._execute_update()
        else:
            # Validate current page
            if self.current_page == 0 and not self.csv_path:
                messagebox.showwarning("Validazione", "Seleziona un file CSV")
                return
            
            if self.current_page == 1:
                # Extract mapping
                self.mapping = {}
                for field, combo in self.mapping_widgets.items():
                    val = combo.get()
                    if val:
                        self.mapping[field] = val
                
                # Validate: need either matricola or nominativo
                if not self.mapping.get('matricola') and not self.mapping.get('nominativo'):
                    messagebox.showwarning("Validazione", 
                                         "Seleziona almeno un identificativo:\n- Matricola\n- Nominativo")
                    return
                
                # Validate: need at least one status field
                status_fields = ['voto', 'q0', 'q1', 'q2']
                if not any(self.mapping.get(f) for f in status_fields):
                    messagebox.showwarning("Validazione", 
                                         "Seleziona almeno un campo da aggiornare:\n- Voto\n- Q0\n- Q1\n- Q2")
                    return
            
            self.current_page += 1
            self._show_page()
    
    def _prev_page(self):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self._show_page()
    
    def _execute_update(self):
        """Execute the status update"""
        try:
            from database import fetch_one, get_db_path
            from soci_import_engine import fetch_socio_id, insert_socio, update_socio_by_id
            from utils import to_bool01

            dry_run = bool(self.dry_run_var.get())
            write_enabled = not dry_run
            
            # Usa le righe originali: permette di importare campi extra per i nuovi soci
            rows = list(self.rows or [])
            total = len(rows)
            if total == 0:
                messagebox.showwarning("Aggiornamento", "Nessuna riga da processare.")
                return
            
            # Start update
            self.progress["maximum"] = total
            self.update_count = 0
            self.inserted_count = 0
            self.skipped_count = 0
            
            # Pre-derive CSV column names from mapping
            col_matricola = self.mapping.get('matricola')
            col_nominativo = self.mapping.get('nominativo')
            col_voto = self.mapping.get('voto')
            col_q0 = self.mapping.get('q0')
            col_q1 = self.mapping.get('q1')
            col_q2 = self.mapping.get('q2')

            def _csv_get(r: dict, key: str):
                if not isinstance(r, dict):
                    return None
                # exact
                if key in r:
                    return r.get(key)
                # case-insensitive fallback
                k_low = key.lower()
                for k in r.keys():
                    try:
                        if str(k).lower() == k_low:
                            return r.get(k)
                    except Exception:
                        continue
                return None

            def _get_by_col(r: dict, colname: str | None):
                if not colname:
                    return None
                v = _csv_get(r, colname)
                if v is None:
                    return None
                s = str(v).strip()
                return s if s != "" else None

            def _split_fullname(full: str | None):
                s = (full or "").strip()
                if not s:
                    return "", ""
                parts = [p for p in s.split() if p]
                if len(parts) >= 2:
                    return " ".join(parts[:-1]).strip(), parts[-1].strip()
                # Fallback: duplicate to satisfy required fields
                return parts[0].strip(), parts[0].strip()

            def _build_new_member_payload(r: dict, *, matricola_val: str | None, nominativo_val: str | None, q0_val, q1_val, q2_val, voto_val):
                # Official ARI columns (if present)
                fullname = _csv_get(r, 'nome')
                callsign = _csv_get(r, 'callsign')
                cf = _csv_get(r, 'cf')
                nascita = _csv_get(r, 'nascita')
                email = _csv_get(r, 'email')
                numeri = _csv_get(r, 'numeri')
                family = _csv_get(r, 'family')
                flag = _csv_get(r, 'flag')
                thr = _csv_get(r, 'thr')
                sezione = _csv_get(r, 'sezione')

                cognome, nome = _split_fullname(str(fullname) if fullname is not None else None)

                note_parts = []
                # Preserve what we can't map cleanly without changing schema
                if nascita is not None and str(nascita).strip() != "":
                    note_parts.append(f"ARI anno_nascita={str(nascita).strip()}")
                if sezione is not None and str(sezione).strip() != "":
                    note_parts.append(f"ARI sezione={str(sezione).strip()}")
                if flag is not None and str(flag).strip() != "":
                    note_parts.append(f"ARI flag={str(flag).strip()}")
                if thr is not None and str(thr).strip() != "":
                    note_parts.append(f"ARI thr={str(thr).strip()}")
                note = " | ".join(note_parts) if note_parts else None

                # Normalize values (regole ARI):
                # - Se THR=1 => VOTO=1
                # - Se VOTO=1 => socio attivo; altrimenti EX socio
                thr_norm = to_bool01(thr) or 0
                voto_norm = 1 if thr_norm == 1 else (to_bool01(voto_val) or 0)
                attivo_norm = 1 if voto_norm == 1 else 0

                payload = {
                    'matricola': (matricola_val or None),
                    'nominativo': (str(callsign).strip().upper() if callsign is not None and str(callsign).strip() else (nominativo_val or None)),
                    'nome': nome,
                    'cognome': cognome,
                    'codicefiscale': (str(cf).strip().upper() if cf is not None and str(cf).strip() else None),
                    'email': (str(email).strip().lower() if email is not None and str(email).strip() else None),
                    'telefono': (str(numeri).strip() if numeri is not None and str(numeri).strip() else None),
                    'familiare': (str(family).strip() if family is not None and str(family).strip() else None),
                    # THR (Honor Roll) = socio onorario: quota esente
                    'socio': ('THR' if thr_norm == 1 else None),
                    'voto': voto_norm,
                    'q0': (str(q0_val).strip().upper() if q0_val is not None and str(q0_val).strip() else None),
                    'q1': (str(q1_val).strip().upper() if q1_val is not None and str(q1_val).strip() else None),
                    'q2': (str(q2_val).strip().upper() if q2_val is not None and str(q2_val).strip() else None),
                    'attivo': attivo_norm,
                    'note': note,
                }

                # Ensure required fields are non-empty
                if not payload.get('nome'):
                    payload['nome'] = payload.get('cognome') or 'ND'
                if not payload.get('cognome'):
                    payload['cognome'] = payload.get('nome') or 'ND'

                return payload

            for i, row in enumerate(rows):
                # Update progress
                self.progress["value"] = i
                self.progress_text.config(text=f"Aggiornamento: {i+1}/{total}")
                self.win.update()
                
                try:
                    # Find member by matricola or nominativo
                    matricola = _get_by_col(row, col_matricola) if col_matricola else _csv_get(row, 'matricola')
                    nominativo = _get_by_col(row, col_nominativo) if col_nominativo else _csv_get(row, 'callsign')

                    existing = fetch_socio_id(matricola=matricola, nominativo=nominativo)

                    # Values to update
                    voto_val = _get_by_col(row, col_voto)
                    q0_val = _get_by_col(row, col_q0)
                    q1_val = _get_by_col(row, col_q1)
                    q2_val = _get_by_col(row, col_q2)

                    # Regole ARI per stato:
                    # - Se THR=1 => VOTO=1
                    # - Se VOTO=1 => socio attivo; altrimenti EX socio
                    thr_norm = to_bool01(_csv_get(row, 'thr')) or 0
                    voto_norm = None
                    if thr_norm == 1:
                        voto_norm = 1
                    elif col_voto:
                        voto_norm = to_bool01(voto_val) or 0

                    if not existing:
                        # Nuovo socio: importa tutte le informazioni disponibili dal CSV ufficiale
                        try:
                            matricola_s = str(matricola).strip() if matricola is not None else None
                            nominativo_s = str(nominativo).strip() if nominativo is not None else None
                            if not (matricola_s or nominativo_s):
                                self.skipped_count += 1
                                continue
                            payload = _build_new_member_payload(
                                row,
                                matricola_val=matricola_s,
                                nominativo_val=nominativo_s,
                                q0_val=q0_val,
                                q1_val=q1_val,
                                q2_val=q2_val,
                                voto_val=voto_val,
                            )
                            insert_socio(payload, write_enabled=write_enabled)
                            self.inserted_count += 1
                        except Exception as ins_exc:
                            logger.error(f"Error inserting row {i}: {ins_exc}")
                            self.skipped_count += 1
                        continue
                    
                    # Build UPDATE query for status fields only
                    updates = {}

                    # Collect values for status fields (voto/attivo/q0/q1/q2)
                    # Nota: attivo è derivato da voto secondo regole ARI.
                    if voto_norm is not None:
                        updates["voto"] = voto_norm
                        updates["attivo"] = 1 if voto_norm == 1 else 0
                    if col_q0 and (q0_val is not None or q0_val == ""):
                        updates["q0"] = q0_val
                    if col_q1 and (q1_val is not None or q1_val == ""):
                        updates["q1"] = q1_val
                    if col_q2 and (q2_val is not None or q2_val == ""):
                        updates["q2"] = q2_val

                    if updates:
                        update_socio_by_id(
                            socio_id=existing['id'],
                            updates=updates,
                            write_enabled=write_enabled,
                            # Keep current behavior: empty strings are not written.
                            keep_empty_strings=False,
                        )
                        self.update_count += 1
                    else:
                        self.skipped_count += 1
                
                except Exception as e:
                    logger.error(f"Error updating row {i}: {e}")
                    self.skipped_count += 1
                    continue
            
            # Complete
            self.progress["value"] = total
            self.progress_text.config(text=f"Completato! {self.update_count} aggiornati, {self.inserted_count} inseriti, {self.skipped_count} saltati")

            msg_title = "Anteprima" if dry_run else "Aggiornamento"
            msg = f"{'ANTEPRIMA (dry-run)' if dry_run else 'Aggiornamento completato!'}\n\n"
            msg += f"Soci aggiornati (Quote/Voto): {self.update_count}\n"
            msg += f"Nuovi soci inseriti: {self.inserted_count}\n"
            if self.skipped_count > 0:
                msg += f"Soci saltati (non trovati / errori): {self.skipped_count}"

            # Diagnostic: DB path + record counts (helps when UI shows few records due to different DB)
            try:
                db_path = get_db_path()
                total_db = fetch_one("SELECT COUNT(*) AS n FROM soci")["n"]
                total_visible = fetch_one("SELECT COUNT(*) AS n FROM soci WHERE deleted_at IS NULL")["n"]
                msg += f"\n\nDB: {db_path}\nRecord soci: {total_visible} (visibili) / {total_db} (totali)"
            except Exception:
                pass

            messagebox.showinfo(msg_title, msg)

            # In dry-run non chiamiamo callback e non chiudiamo automaticamente
            if not dry_run:
                if self.on_complete_callback:
                    self.on_complete_callback(self.update_count)

                # Close after delay
                self.win.after(2000, self.win.destroy)
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
            messagebox.showerror("Errore", f"Errore durante l'aggiornamento:\n{e}")
    
    def _cancel(self):
        """Cancel update"""
        if messagebox.askyesno("Annulla", "Annullare l'aggiornamento?"):
            self.win.destroy()
