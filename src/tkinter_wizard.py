# -*- coding: utf-8 -*-
"""
Wizard di configurazione GLR con Tkinter
"""


import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import urllib.request
import zipfile
import threading

from config import CONFIG_JSON
from database import init_db, get_connection

logger = logging.getLogger("tkinter_wizard")


# --- Wizard State Object ---
class WizardState:
    def __init__(self, section_data=None, import_result=None, cd_config=None, thunderbird=None, completed=False):
        self.section_data = section_data or {}
        self.import_result = import_result
        self.cd_config = cd_config or {}
        self.thunderbird = thunderbird or {}
        self.completed = completed


# --- Base Step Frame ---
class WizardStepFrame(ttk.Frame):
    def __init__(self, parent, wizard_controller, wizard_state: WizardState):
        super().__init__(parent)
        self.wizard_controller = wizard_controller
        self.wizard_state = wizard_state

    def build_ui(self):
        """Build the step UI"""
        raise NotImplementedError

    def validate_and_next(self) -> bool:
        """Validate and proceed to next step"""
        return True

    def on_back(self) -> bool:
        """Handle back navigation"""
        return True

    def on_skip(self) -> bool:
        """Handle skip action"""
        return True


# --- Step 1: Welcome ---
class WelcomeStep(WizardStepFrame):
    def build_ui(self):
        ttk.Label(self, text="Benvenuto in GLR", font=("Arial", 16, "bold")).pack(pady=20)

        text = ("Questa procedura guidata ti accompagnerà nella configurazione iniziale "
                "del gestionale GLR.\n\n"
                "Nei prossimi passaggi potrai:\n"
                "• inserire i dati della sezione\n"
                "• importare l'elenco soci\n"
                "• configurare il consiglio direttivo\n"
                "• impostare eventuali integrazioni opzionali\n\n"
                "La configurazione richiede solo pochi minuti "
                "e potrà essere modificata successivamente.")

        if self.wizard_controller.mode == "ADMIN":
            text += "\n\nStai operando in modalità amministratore."

        ttk.Label(self, text=text, justify="left").pack(pady=10)


# --- Step 2: Section Data ---
class SectionDataStep(WizardStepFrame):
    def __init__(self, parent, wizard_controller, wizard_state: WizardState):
        super().__init__(parent, wizard_controller, wizard_state)
        self.fields = {}
        self.field_values = {}  # Store values separately from widgets

    def build_ui(self):
        ttk.Label(self, text="Dati della sezione", font=("Arial", 14, "bold")).pack(pady=10)

        # Create scrollable frame for fields
        canvas = tk.Canvas(self, height=400)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

        # Pre-fill fields in ADMIN mode
        initial_values = {}
        if self.wizard_controller.mode == "ADMIN":
            try:
                config_path = Path(CONFIG_JSON)
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        initial_values = {
                            'nome_sezione': config.get('nome_sezione', ''),
                            'codice_sezione': config.get('codice_sezione', ''),
                            'sede_operativa': config.get('sede_operativa', ''),
                            'sede_legale': config.get('sede_legale', ''),
                            'indirizzo_postale': config.get('indirizzo_postale', ''),
                            'email': config.get('email', ''),
                            'telefono': config.get('telefono', ''),
                            'sito_web': config.get('sito_web', ''),
                            'coordinate_bancarie': config.get('coordinate_bancarie', ''),
                            'recapiti': config.get('recapiti', ''),
                            'mandato': config.get('mandato', ''),
                        }
            except Exception:
                pass

        fields_config = [
            ('Nome sezione', 'nome_sezione', False),
            ('Codice sezione', 'codice_sezione', False),
            ('Sede operativa', 'sede_operativa', True),
            ('Sede legale', 'sede_legale', True),
            ('Indirizzo postale', 'indirizzo_postale', True),
            ('Indirizzo email', 'email', False),
            ('Telefono', 'telefono', False),
            ('Sito web', 'sito_web', False),
            ('Coordinate bancarie', 'coordinate_bancarie', True),
            ('Recapiti di sezione', 'recapiti', True),
            ('Mandato (formato: Mandato aaaa-aaaa)', 'mandato', False),
        ]

        for label, key, multiline in fields_config:
            ttk.Label(scrollable_frame, text=label + ":").pack(anchor="w", pady=2)
            if multiline:
                text = tk.Text(scrollable_frame, height=3, width=60, wrap=tk.WORD)
                text.insert("1.0", initial_values.get(key, ''))
            else:
                text = ttk.Entry(scrollable_frame, width=60)
                text.insert(0, initial_values.get(key, ''))
            text.pack(fill="x", pady=2, padx=5)
            self.fields[key] = text
            # Initialize field values
            if multiline:
                self.field_values[key] = initial_values.get(key, '')
            else:
                self.field_values[key] = initial_values.get(key, '')

    def validate_and_next(self) -> bool:
        # Update field values from widgets before validation
        self._update_field_values()

        # Basic validation - check required fields
        nome = self.field_values.get('nome_sezione', '').strip()
        codice = self.field_values.get('codice_sezione', '').strip()

        if not nome or not codice:
            messagebox.showerror("Errore", "Nome sezione e Codice sezione sono obbligatori.")
            return False

        # Save to state
        self.wizard_state.section_data = self.field_values.copy()
        return True

    def _update_field_values(self):
        """Update field values from current widget states"""
        for key, widget in self.fields.items():
            try:
                if isinstance(widget, tk.Text):
                    self.field_values[key] = widget.get("1.0", "end-1c")
                else:
                    self.field_values[key] = widget.get()
            except:
                # Widget might be destroyed, keep existing value
                pass


# --- Step 3: Import Soci ---
class ImportSociStep(WizardStepFrame):
    def __init__(self, parent, wizard_controller, wizard_state: WizardState):
        super().__init__(parent, wizard_controller, wizard_state)
        self.import_result = None
        
        # Restore previous state if available
        if wizard_state.import_result:
            self.import_result = wizard_state.import_result

    def build_ui(self):
        ttk.Label(self, text="Importazione soci da CSV", font=("Arial", 14, "bold")).pack(pady=10)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        ttk.Label(frame, text="Fare clic su 'Importa soci' per avviare il wizard di importazione completo.").pack(pady=10)

        self.result_label = ttk.Label(frame, text="", foreground="green")
        self.result_label.pack(pady=5)

        self.import_btn = ttk.Button(frame, text="Importa soci", command=self._launch_import_wizard)
        self.import_btn.pack(pady=10)

        # Restore previous results if available
        if self.import_result:
            imported = self.import_result.get('imported', 0)
            errors = self.import_result.get('errors', 0)
            duplicates = self.import_result.get('duplicates', 0)
            
            if imported > 0:
                self.result_label.config(text=f"✓ Importati {imported} soci. Errori: {errors}. Duplicati: {duplicates}", foreground="green")
            else:
                self.result_label.config(text=f"✗ Nessun socio importato. Errori: {errors}", foreground="red")

    def _launch_import_wizard(self):
        # Initialize database if not already done
        try:
            from database import init_db
            init_db()
        except Exception as e:
            messagebox.showerror("Errore", f"Errore inizializzazione database: {e}")
            return
        
        # Launch the full import wizard
        from import_wizard import ImportWizard
        
        def on_complete(count):
            # Update wizard state with import result
            self.wizard_state.import_result = {'imported': count, 'errors': 0, 'duplicates': 0}
            # Update UI
            self.result_label.config(text=f"✓ Importati {count} soci.", foreground="green")
        
        # Create and show import wizard
        ImportWizard(self.winfo_toplevel(), on_complete)

    def validate_and_next(self) -> bool:
        # Check if soci have been imported by counting records in database
        try:
            from database import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM soci")
                soci_count = cursor.fetchone()[0]
                if soci_count > 0:
                    self.wizard_state.import_result = {'imported': soci_count, 'errors': 0, 'duplicates': 0}
                    return True
                else:
                    messagebox.showwarning("Importazione richiesta", 
                                         "È necessario importare i soci prima di procedere.\n\n"
                                         "Utilizza il pulsante 'Importa soci' per caricare l'elenco soci da CSV.")
                    return False
        except Exception as e:
            logger.error(f"Errore controllo soci: {e}")
            messagebox.showerror("Errore", f"Errore durante il controllo dei soci importati:\n{e}")
            return False

    def on_skip(self) -> bool:
        return True


# --- Step 4: Consiglio Direttivo ---
class CdStep(WizardStepFrame):
    def __init__(self, parent, wizard_controller, wizard_state: WizardState):
        super().__init__(parent, wizard_controller, wizard_state)
        self.soci_list = []
        self.role_assignments = {}
        self.manual_entries = {}
        self.selected_roles = {}  # Store selected values separately from widgets
        
        # Restore previous selections if available
        if wizard_state.cd_config:
            self.selected_roles = wizard_state.cd_config.copy()
        
    def build_ui(self):
        ttk.Label(self, text="Composizione consiglio direttivo", font=("Arial", 14, "bold")).pack(pady=10)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Check if soci have been imported by counting records in database
        try:
            from database import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM soci")
                soci_count = cursor.fetchone()[0]
                import_success = soci_count > 0
        except Exception as e:
            logger.warning(f"Errore controllo soci importati: {e}")
            import_success = False

        if import_success:
            self._build_member_selection_ui(frame)
        else:
            self._build_manual_entry_ui(frame)

    def _build_member_selection_ui(self, parent):
        ttk.Label(parent, text="Seleziona i soci per le cariche del consiglio direttivo").pack(pady=10)
        
        # Load soci from database
        try:
            from database import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT matricola, nominativo, nome, cognome FROM soci ORDER BY cognome, nome")
                self.soci_list = cursor.fetchall()
        except Exception as e:
            logger.error(f"Errore caricamento soci: {e}")
            ttk.Label(parent, text="Errore nel caricamento dei soci dal database", foreground="red").pack(pady=10)
            return

        if not self.soci_list:
            ttk.Label(parent, text="Nessun socio trovato nel database", foreground="orange").pack(pady=10)
            return

        # Create scrollable frame for role assignments
        canvas = tk.Canvas(parent, height=400)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Standard CD roles with multiple positions
        roles = [
            "Presidente",
            "Vice Presidente", 
            "Segretario",
            "Tesoriere",
            "Consigliere 1",
            "Consigliere 2", 
            "Consigliere 3",
            "Probiviro 1 (referente)",
            "Probiviro 2",
            "Probiviro 3"
        ]

        ttk.Label(scrollable_frame, text="Assegna le cariche:", font=("Arial", 10, "bold")).pack(anchor="w", pady=5)

        self.role_combos = {}
        for role in roles:
            role_frame = ttk.Frame(scrollable_frame)
            role_frame.pack(fill="x", pady=2)
            
            ttk.Label(role_frame, text=f"{role}:", width=20, anchor="w").pack(side="left")
            
            combo = ttk.Combobox(role_frame, state="readonly", width=40)
            # Display format: nominativo (nome cognome)
            combo['values'] = [""] + [f"{s[1] or 'N/A'} ({s[2] or ''} {s[3] or ''})".strip() for s in self.soci_list]
            
            # Restore previous selection if available
            if role in self.selected_roles:
                combo.set(self.selected_roles[role])
            
            # Save selection when changed
            def make_save_func(r=role, c=combo):
                def save_selection(*args):
                    self.selected_roles[r] = c.get()
                return save_selection
            
            combo.bind('<<ComboboxSelected>>', make_save_func())
            
            combo.pack(side="left", fill="x", expand=True, padx=(5,0))
            
            self.role_combos[role] = combo

    def _build_manual_entry_ui(self, parent):
        ttk.Label(parent, text="Nessun socio importato. Inserisci manualmente i membri del consiglio direttivo").pack(pady=10)

        # Create scrollable frame for manual entries
        canvas = tk.Canvas(parent, height=300)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Manual entry fields
        roles = [
            "Presidente",
            "Vice Presidente", 
            "Segretario",
            "Tesoriere",
            "Consigliere 1",
            "Consigliere 2",
            "Consigliere 3",
            "Probiviro 1 (referente)",
            "Probiviro 2",
            "Probiviro 3"
        ]

        ttk.Label(scrollable_frame, text="Inserisci i nominativi:", font=("Arial", 10, "bold")).pack(anchor="w", pady=5)

        self.manual_entries = {}
        for role in roles:
            role_frame = ttk.Frame(scrollable_frame)
            role_frame.pack(fill="x", pady=2)
            
            ttk.Label(role_frame, text=f"{role}:", width=20, anchor="w").pack(side="left")
            
            entry = ttk.Entry(role_frame, width=40)
            
            # Restore previous value if available
            if role in self.selected_roles:
                entry.insert(0, self.selected_roles[role])
            
            # Save value when changed
            def make_save_func(r=role, e=entry):
                def save_value(*args):
                    self.selected_roles[r] = e.get().strip()
                return save_value
            
            entry.bind('<KeyRelease>', make_save_func())
            
            entry.pack(side="left", fill="x", expand=True, padx=(5,0))
            
            self.manual_entries[role] = entry

    def validate_and_next(self) -> bool:
        # Collect role assignments
        cd_config = {}
        
        if hasattr(self, 'role_combos') and self.role_combos:
            # From stored selections
            for role in self.selected_roles:
                selected = self.selected_roles[role]
                if selected:
                    # Find the corresponding matricola from soci_list
                    matricola = None
                    for socio in self.soci_list:
                        matricola_socio, nominativo, nome, cognome = socio
                        display_text = f"{nominativo or 'N/A'} ({nome or ''} {cognome or ''})".strip()
                        if display_text == selected:
                            matricola = matricola_socio
                            break
                    if matricola:
                        cd_config[role] = matricola
                    else:
                        cd_config[role] = selected  # Fallback to selected text
        elif hasattr(self, 'manual_entries') and self.manual_entries:
            # Manual entries
            for role, entry in self.manual_entries.items():
                try:
                    value = entry.get().strip()
                    if value:
                        cd_config[role] = value
                except:
                    # Widget might be destroyed, use stored value if available
                    if role in self.selected_roles:
                        cd_config[role] = self.selected_roles[role]
        
        self.wizard_state.cd_config = cd_config
        return True


# --- Step 5: Email Configuration ---
class EmailStep(WizardStepFrame):
    def __init__(self, parent, wizard_controller, wizard_state: WizardState):
        super().__init__(parent, wizard_controller, wizard_state)
        self.email_method = tk.StringVar(value="default")
        self.thunderbird_path = tk.StringVar(value="data/tools/thunderbird")
        self.test_result = tk.StringVar(value="")
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="")

    def build_ui(self):
        ttk.Label(self, text="Configurazione invio email", font=("Arial", 14, "bold")).pack(pady=10)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        ttk.Label(frame, text="L'app può interagire con i seguenti client di posta:").pack(anchor="w", pady=5)

        # Email method selection
        method_frame = ttk.LabelFrame(frame, text="Metodo di invio email", padding=10)
        method_frame.pack(fill="x", pady=10)

        ttk.Radiobutton(method_frame, text="Client di posta predefinito del sistema", 
                       variable=self.email_method, value="default").pack(anchor="w", pady=2)
        
        ttk.Radiobutton(method_frame, text="Thunderbird Portable", 
                       variable=self.email_method, value="thunderbird").pack(anchor="w", pady=2)

        # Thunderbird configuration
        thunderbird_frame = ttk.LabelFrame(frame, text="Configurazione Thunderbird Portable", padding=10)
        thunderbird_frame.pack(fill="x", pady=10)

        self.download_var = tk.BooleanVar()
        ttk.Checkbutton(thunderbird_frame, text="Scarica automaticamente Thunderbird Portable", 
                       variable=self.download_var, command=self._on_download_toggle).pack(anchor="w", pady=5)

        path_frame = ttk.Frame(thunderbird_frame)
        path_frame.pack(fill="x", pady=5)
        ttk.Label(path_frame, text="Percorso installazione:").pack(side="left")
        ttk.Entry(path_frame, textvariable=self.thunderbird_path, width=40).pack(side="left", fill="x", expand=True, padx=(5,0))
        ttk.Button(path_frame, text="Sfoglia", command=self._select_path).pack(side="right")

        # Download button
        download_frame = ttk.Frame(thunderbird_frame)
        download_frame.pack(fill="x", pady=5)
        
        def download():
            if not self.download_var.get():
                return
                
            # Disable download button during download
            download_btn.config(state="disabled")
            self.test_result.set("Scaricamento Thunderbird in corso...")
            
            # Run download in separate thread to avoid blocking UI
            def do_download():
                try:
                    success = self._download_thunderbird_portable()
                    if success:
                        self.test_result.set("✓ Thunderbird scaricato con successo")
                        # Update path to downloaded location
                        self.thunderbird_path.set("data/tools/thunderbird")
                    else:
                        self.test_result.set("✗ Errore durante il download")
                except Exception as e:
                    logger.error(f"Errore download Thunderbird: {e}")
                    self.test_result.set(f"✗ Errore download: {str(e)}")
                finally:
                    download_btn.config(state="normal")
            
            threading.Thread(target=do_download, daemon=True).start()

        download_btn = ttk.Button(download_frame, text="Scarica ora", command=download)
        download_btn.pack(side="left")
        
        ttk.Label(download_frame, text="(Download automatico al primo utilizzo se abilitato)", 
                 foreground="gray").pack(side="left", padx=(10,0))

        # Download progress
        progress_frame = ttk.Frame(thunderbird_frame)
        progress_frame.pack(fill="x", pady=5)
        
        ttk.Label(progress_frame, textvariable=self.status_var).pack(anchor="w")
        self.download_progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.download_progress.pack(fill="x", pady=2)

        # Test connection
        test_frame = ttk.Frame(frame)
        test_frame.pack(fill="x", pady=10)
        
        ttk.Button(test_frame, text="Test connessione", command=self._test_connection).pack(side="left")
        ttk.Label(test_frame, textvariable=self.test_result, foreground="blue").pack(side="left", padx=(10,0))

        # Info text
        info_text = ("Nota: Thunderbird Portable offre funzionalità avanzate come invio massivo "
                    "e gestione template email. Il client predefinito è più semplice ma limitato.")
        ttk.Label(frame, text=info_text, wraplength=600, justify="left").pack(anchor="w", pady=10)

    def _on_download_toggle(self):
        if self.download_var.get():
            # Auto-set path for download
            self.thunderbird_path.set("data/tools/thunderbird")
        else:
            # Clear path when download disabled
            self.thunderbird_path.set("")

    def _test_connection(self):
        self.test_result.set("Test in corso...")
        self.update()
        
        try:
            if self.email_method.get() == "thunderbird":
                # Test Thunderbird
                import os
                import subprocess
                
                tb_path = self.thunderbird_path.get()
                if not tb_path:
                    self.test_result.set("✗ Percorso Thunderbird non specificato")
                    return
                    
                exe_path = os.path.join(tb_path, "thunderbird.exe")
                if not os.path.exists(exe_path):
                    if self.download_var.get():
                        self.test_result.set("⚠ Thunderbird verrà scaricato al primo utilizzo")
                    else:
                        self.test_result.set("✗ Thunderbird non trovato nel percorso specificato")
                    return
                
                # Try to get version (basic test)
                try:
                    result = subprocess.run([exe_path, "--version"], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        version = result.stdout.strip().split()[-1] if result.stdout.strip() else "Sconosciuta"
                        self.test_result.set(f"✓ Thunderbird {version} trovato")
                    else:
                        self.test_result.set("✗ Thunderbird non risponde correttamente")
                except subprocess.TimeoutExpired:
                    self.test_result.set("✗ Timeout test Thunderbird")
                except Exception as e:
                    self.test_result.set(f"✗ Errore test Thunderbird: {str(e)}")
                    
            else:
                # Test default client
                import webbrowser
                try:
                    # Try to open mailto link
                    webbrowser.open("mailto:test@example.com", new=0)
                    self.test_result.set("✓ Client di posta predefinito aperto")
                except Exception as e:
                    self.test_result.set(f"✗ Errore apertura client predefinito: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Errore durante test connessione: {e}")
            self.test_result.set(f"✗ Errore test: {str(e)}")

    def validate_and_next(self) -> bool:
        config = {
            'method': self.email_method.get(),
            'thunderbird_path': self.thunderbird_path.get() if self.email_method.get() == "thunderbird" else "",
            'auto_download': self.download_var.get()
        }
        self.wizard_state.thunderbird = config
        return True

    def _download_thunderbird_portable(self) -> bool:
        """Download and extract Thunderbird Portable."""
        try:
            import urllib.request
            import zipfile
            import os
            import tempfile
            
            # Create destination directory
            dest_dir = os.path.join("data", "tools", "thunderbird")
            os.makedirs(dest_dir, exist_ok=True)
            
            # For simplicity, open the download page in browser
            # Direct download of Thunderbird Portable is complex due to changing URLs
            import webbrowser
            
            self.status_var.set("Apertura pagina download Thunderbird...")
            self.progress_var.set(10)
            self.update()
            
            # Open PortableApps download page
            webbrowser.open("https://portableapps.com/apps/internet/thunderbird_portable")
            
            self.progress_var.set(50)
            self.status_var.set("Segui le istruzioni per scaricare Thunderbird Portable")
            self.update()
            
            # Wait a bit and check if user has downloaded
            import time
            time.sleep(2)
            
            self.progress_var.set(100)
            self.status_var.set("Scarica completato - configura il percorso manualmente")
            self.update()
            
            # Ask user to select the downloaded file
            downloaded_path = filedialog.askdirectory(
                title="Seleziona la cartella dove hai estratto Thunderbird Portable",
                initialdir=os.path.expanduser("~/Downloads")
            )
            
            if downloaded_path:
                self.thunderbird_path.set(downloaded_path)
                return True
            else:
                return False
            
        except Exception as e:
            logger.error(f"Errore download Thunderbird: {e}")
            self.status_var.set(f"Errore: {str(e)}")
            return False

    def _select_path(self):
        path = filedialog.askdirectory(title="Seleziona percorso installazione Thunderbird")
        if path:
            self.thunderbird_path.set(path)
            self.download_var.set(False)  # Disable auto-download if manual path selected

    def on_skip(self) -> bool:
        self.wizard_state.thunderbird = {'method': 'default', 'thunderbird_path': '', 'auto_download': False}
        return True


# --- Step 6: Summary ---
class SummaryStep(WizardStepFrame):
    def build_ui(self):
        ttk.Label(self, text="Riepilogo configurazione", font=("Arial", 14, "bold")).pack(pady=10)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Section data
        ttk.Label(frame, text="✓ Dati sezione:", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)
        section_data = self.wizard_state.section_data
        if section_data:
            ttk.Label(frame, text=f"Nome: {section_data.get('nome_sezione', 'N/A')}").pack(anchor="w", padx=10)
            ttk.Label(frame, text=f"Codice: {section_data.get('codice_sezione', 'N/A')}").pack(anchor="w", padx=10)
            ttk.Label(frame, text=f"Email: {section_data.get('email', 'N/A')}").pack(anchor="w", padx=10)
        else:
            ttk.Label(frame, text="Nessun dato sezione inserito", foreground="red").pack(anchor="w", padx=10)

        # Import result
        ttk.Label(frame, text="✓ Importazione soci:", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)
        if self.wizard_state.import_result:
            imported = self.wizard_state.import_result.get('imported', 0)
            errors = self.wizard_state.import_result.get('errors', 0)
            duplicates = self.wizard_state.import_result.get('duplicates', 0)
            
            if imported > 0:
                ttk.Label(frame, text=f"Soci importati: {imported}", foreground="green").pack(anchor="w", padx=10)
            else:
                ttk.Label(frame, text="Nessun socio importato", foreground="orange").pack(anchor="w", padx=10)
                
            if errors > 0:
                ttk.Label(frame, text=f"Errori: {errors}", foreground="red").pack(anchor="w", padx=10)
            if duplicates > 0:
                ttk.Label(frame, text=f"Duplicati: {duplicates}", foreground="orange").pack(anchor="w", padx=10)
        else:
            ttk.Label(frame, text="Importazione saltata", foreground="orange").pack(anchor="w", padx=10)

        # CD config
        ttk.Label(frame, text="✓ Consiglio direttivo:", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)
        if self.wizard_state.cd_config:
            assigned_roles = [role for role, member in self.wizard_state.cd_config.items() if member]
            if assigned_roles:
                for role in assigned_roles:
                    member = self.wizard_state.cd_config[role]
                    ttk.Label(frame, text=f"{role}: {member}", foreground="green").pack(anchor="w", padx=10)
            else:
                ttk.Label(frame, text="Nessuna carica assegnata", foreground="orange").pack(anchor="w", padx=10)
        else:
            ttk.Label(frame, text="Configurazione CD saltata", foreground="orange").pack(anchor="w", padx=10)

        # Email config
        ttk.Label(frame, text="✓ Configurazione email:", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)
        thunderbird_config = self.wizard_state.thunderbird
        if thunderbird_config:
            method = thunderbird_config.get('method', 'default')
            if method == 'thunderbird':
                path = thunderbird_config.get('thunderbird_path', '')
                auto_download = thunderbird_config.get('auto_download', False)
                ttk.Label(frame, text="Metodo: Thunderbird Portable", foreground="green").pack(anchor="w", padx=10)
                if auto_download:
                    ttk.Label(frame, text="Download automatico abilitato", foreground="blue").pack(anchor="w", padx=10)
                elif path:
                    ttk.Label(frame, text=f"Percorso: {path}", foreground="green").pack(anchor="w", padx=10)
            else:
                ttk.Label(frame, text="Metodo: Client predefinito", foreground="green").pack(anchor="w", padx=10)
        else:
            ttk.Label(frame, text="Configurazione email saltata", foreground="orange").pack(anchor="w", padx=10)

        # Completion message
        ttk.Label(frame, text="\nConfigurazione completata! I dati verranno salvati nel database.", 
                 font=("Arial", 10, "italic")).pack(anchor="w", pady=10)


# --- Wizard Controller ---
class WizardController:
    def __init__(self, mode: str = "FIRST_RUN", on_complete: Optional[Callable] = None):
        self.mode = mode.upper()
        self.on_complete = on_complete
        self.wizard_state = WizardState()

        # Pre-fill in ADMIN mode
        if self.mode == "ADMIN":
            self._load_existing_config()

        self.step_classes = [
            WelcomeStep,
            SectionDataStep,
            ImportSociStep,
            CdStep,
            EmailStep,
            SummaryStep,
        ]
        self.current_step = 0
        self.step_instances = []

        self.root = None
        self.main_frame = None
        self.step_frame = None
        self.nav_frame = None

    def _load_existing_config(self):
        try:
            config_path = Path(CONFIG_JSON)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.wizard_state.section_data = config
        except Exception:
            pass

    def show_wizard(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title(f"Configurazione GLR - {'Amministratore' if self.mode == 'ADMIN' else 'Prima esecuzione'}")
        self.root.geometry("800x700")
        self.root.resizable(False, False)

        if parent:
            self.root.transient(parent)
            self.root.grab_set()

        self.root.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Step indicator
        self.step_label = ttk.Label(self.main_frame, text=f"Passo {self.current_step + 1} di {len(self.step_classes)}")
        self.step_label.pack(pady=5)

        # Step container
        self.step_frame = ttk.Frame(self.main_frame)
        self.step_frame.pack(fill="both", expand=True)

        # Navigation
        self.nav_frame = ttk.Frame(self.main_frame)
        self.nav_frame.pack(fill="x", pady=10)

        self.prev_btn = ttk.Button(self.nav_frame, text="Indietro", command=self._prev_step, state="disabled")
        self.prev_btn.pack(side="left", padx=5)

        self.skip_btn = ttk.Button(self.nav_frame, text="Salta", command=self._skip_step)

        self.next_btn = ttk.Button(self.nav_frame, text="Avanti", command=self._next_step)
        self.next_btn.pack(side="right", padx=5)

        self.cancel_btn = ttk.Button(self.nav_frame, text="Annulla", command=self._on_cancel)
        self.cancel_btn.pack(side="right", padx=5)

        self.save_btn = ttk.Button(self.nav_frame, text="Salva", command=self._on_save)

        self._show_step(0)

        if not parent:
            self.root.mainloop()

    def _show_step(self, step_idx: int):
        assert self.step_frame is not None, "Wizard not initialized"
        self.current_step = step_idx
        self.step_label.config(text=f"Passo {self.current_step + 1} di {len(self.step_classes)}")

        # Clear current step
        for widget in self.step_frame.winfo_children():
            widget.destroy()

        # Create new step
        step_class = self.step_classes[step_idx]
        step_instance = step_class(self.step_frame, self, self.wizard_state)
        step_instance.pack(fill="both", expand=True)
        step_instance.build_ui()
        self.step_instances.append(step_instance)

        # Update navigation
        self.prev_btn.config(state="normal" if step_idx > 0 else "disabled")
        self.skip_btn.pack_forget()
        self.save_btn.pack_forget()
        self.next_btn.pack_forget()
        self.cancel_btn.pack_forget()  # Always show cancel

        self.cancel_btn.pack(side="right", padx=5)

        if step_idx == len(self.step_classes) - 1:  # Summary
            self.save_btn.pack(side="right", padx=5)
        else:
            self.next_btn.pack(side="right", padx=5)
            if hasattr(step_instance, 'on_skip') and step_idx in [2, 3, 4]:  # Import, CD, Email
                self.skip_btn.pack(side="right", padx=5)

    def _next_step(self):
        if self.step_instances and self.step_instances[-1].validate_and_next():
            if self.current_step < len(self.step_classes) - 1:
                self._show_step(self.current_step + 1)

    def _prev_step(self):
        if self.step_instances and self.step_instances[-1].on_back():
            if self.current_step > 0:
                self._show_step(self.current_step - 1)

    def _skip_step(self):
        if self.step_instances and self.step_instances[-1].on_skip():
            self._next_step()

    def _on_cancel(self):
        assert self.root is not None, "Wizard not shown"
        if self.mode == "FIRST_RUN":
            if messagebox.askyesno("Annulla configurazione",
                                   "Annullare la configurazione? I dati inseriti andranno persi.",
                                   parent=self.root):
                self.root.destroy()
        else:
            self.root.destroy()

    def _on_save(self):
        assert self.root is not None, "Wizard not shown"
        # Save configuration
        config = self.wizard_state.section_data.copy()

        if self.wizard_state.import_result:
            config['import_result'] = self.wizard_state.import_result

        if self.wizard_state.cd_config:
            config['cd_config'] = self.wizard_state.cd_config

        if self.wizard_state.thunderbird:
            config['thunderbird'] = self.wizard_state.thunderbird

        # Save to file
        config_path = Path(CONFIG_JSON)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # Save CD assignments to database if configured
        if self.wizard_state.cd_config:
            self._save_cd_assignments_to_database()

        # Set completed flag only in FIRST_RUN mode
        if self.mode == "FIRST_RUN":
            config['wizard_completed'] = True
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        if self.on_complete:
            self.on_complete(self.wizard_state)

        messagebox.showinfo("Completato", "Configurazione salvata con successo!", parent=self.root)
        self.root.destroy()

    def _save_cd_assignments_to_database(self):
        """Save CD role assignments to database."""
        try:
            from database import get_connection
            from utils import now_iso
            
            cd_config = self.wizard_state.cd_config
            if not cd_config:
                return

            with get_connection() as conn:
                # Create or get active mandate
                mandate_label = "Mandato Wizard"
                start_date = now_iso()[:10]  # YYYY-MM-DD
                end_date = f"{int(start_date[:4]) + 3}-{start_date[5:]}"  # +3 years
                
                # Check if mandate already exists
                existing_mandate = conn.execute(
                    "SELECT id FROM cd_mandati WHERE is_active = 1"
                ).fetchone()
                
                if existing_mandate:
                    mandate_id = existing_mandate[0]
                else:
                    # Create new mandate
                    cursor = conn.execute(
                        """
                        INSERT INTO cd_mandati (label, start_date, end_date, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, 1, ?, ?)
                        """,
                        (mandate_label, start_date, end_date, now_iso(), now_iso())
                    )
                    mandate_id = cursor.lastrowid

                # Save role assignments
                for role_name, member_info in cd_config.items():
                    if not member_info:
                        continue
                    
                    # Get or create role
                    role_code = self._normalize_role_name(role_name)
                    conn.execute(
                        "INSERT OR IGNORE INTO cd_cariche (codice, nome, ordine, is_cd_member, allow_multiple) VALUES (?, ?, 0, 1, 0)",
                        (role_code, role_name)
                    )
                    
                    role_row = conn.execute("SELECT id FROM cd_cariche WHERE codice = ?", (role_code,)).fetchone()
                    if not role_row:
                        continue
                    role_id = role_row[0]
                    
                    # Try to find socio_id from matricola or name
                    socio_id = None
                    if isinstance(member_info, str) and member_info.isdigit():
                        # It's a matricola
                        socio_row = conn.execute("SELECT id FROM soci WHERE matricola = ?", (member_info,)).fetchone()
                        if socio_row:
                            socio_id = socio_row[0]
                    
                    # Save assignment
                    conn.execute(
                        """
                        INSERT INTO cd_assegnazioni_cariche (mandato_id, carica_id, socio_id, nominativo, data_inizio, data_fine, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (mandate_id, role_id, socio_id, str(member_info), start_date, end_date, now_iso(), now_iso())
                    )
                    
            logger.info("Assegnazioni CD salvate nel database")
            
        except Exception as e:
            logger.error(f"Errore nel salvataggio assegnazioni CD: {e}")
            # Don't fail the entire save process for CD assignment errors

    def _normalize_role_name(self, role_name: str) -> str:
        """Normalize role name to code."""
        role_map = {
            "Presidente": "PRESIDENTE",
            "Vice Presidente": "VICE_PRESIDENTE", 
            "Segretario": "SEGRETARIO",
            "Tesoriere": "TESORIERE",
            "Consigliere": "CONSIGLIERE",
            "Revisore dei Conti": "REVISORE_CONTI"
        }
        return role_map.get(role_name, role_name.upper().replace(" ", "_"))


def run_wizard(mode: str = "FIRST_RUN", parent=None, on_complete: Optional[Callable] = None):
    """Run the GLR configuration wizard"""
    wizard = WizardController(mode=mode, on_complete=on_complete)
    wizard.show_wizard(parent)


if __name__ == "__main__":
    run_wizard()