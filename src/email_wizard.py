# -*- coding: utf-8 -*-
"""
Email Wizard for GLR Gestione Locale Radioamatori
Simplified wizard for creating emails from templates
"""

import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
import urllib.parse
import webbrowser
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import format_datetime, parsedate_to_datetime, getaddresses
from config import SEC_DOCS, THUNDERBIRD_EXE, DATA_DIR
from config_manager import load_config

logger = logging.getLogger("librosoci")


EMAIL_TEMPLATES_SUBDIR = "email_templates"

TEMPLATE_NONE_LABEL = "Nessuno (testo libero)"

# UI label -> template key -> filename
EMAIL_TEMPLATE_SPECS: list[tuple[str, str, str]] = [
    ("Convocazione CD", "convocazione_cd", "Convocazione CD.txt"),
    ("Comunicazione Generale", "comunicazione_generale", "Comunicazione Generale.txt"),
    ("Convocazione Assemblea", "convocazione_assemblea", "Convocazione Assemblea.txt"),
    ("Promemoria Quota", "promemoria_quota", "Promemoria Quota.txt"),
    ("Email personalizzata", "personalizzata", "Email personalizzata.txt"),
]


DEFAULT_EMAIL_TEMPLATES: dict[str, str] = {
    "convocazione_cd": """Gentili Consiglieri,

siete convocati per la riunione del Consiglio Direttivo n. {num} che si terrà in data {data} alle ore {ora} presso {luogo}.

Ordine del giorno:
{odg}

Cordiali saluti,
Il Presidente
{presidente}""",
    "comunicazione_generale": """Cari Soci,

vi informiamo che {messaggio}

Per ulteriori informazioni potete contattarci rispondendo a questa email.

Cordiali saluti,
    Il Segretario""",
    "convocazione_assemblea": """Gentili Soci,

siete convocati per l'Assemblea Ordinaria/Straordinaria dei Soci che si terrà in:

PRIMA CONVOCAZIONE: {data} ore {ora}
SECONDA CONVOCAZIONE: {data2} ore {ora2}

Presso: {luogo}

Ordine del giorno:
{odg}

La vostra presenza è importante.

Cordiali saluti,
Il Presidente
{presidente}""",
    "promemoria_quota": """Caro Socio,

ti ricordiamo che la quota sociale per l'anno {anno} non risulta ancora versata.

Importo: {importo}
Causale: {causale}
IBAN: {iban}

Per qualsiasi chiarimento siamo a disposizione.

Cordiali saluti,
Il Tesoriere""",
    "personalizzata": "",
}


def get_email_templates_dir() -> str:
    """Return the writable folder containing email template .txt files."""
    templates_dir = os.path.join(DATA_DIR, EMAIL_TEMPLATES_SUBDIR)
    os.makedirs(templates_dir, exist_ok=True)
    return templates_dir


def list_email_template_names() -> list[str]:
    """Return available template names (file stems) from the templates folder."""
    templates_dir = get_email_templates_dir()
    names: list[str] = []
    try:
        for entry in os.listdir(templates_dir):
            if not entry.lower().endswith(".txt"):
                continue
            stem = os.path.splitext(entry)[0].strip()
            if not stem:
                continue
            names.append(stem)
    except Exception as exc:
        logger.debug("Impossibile elencare template email in %s: %s", templates_dir, exc)
        return []

    names = sorted(set(names), key=lambda s: s.casefold())
    # keep the special one at the end if present
    if "Email personalizzata" in names:
        names = [n for n in names if n != "Email personalizzata"] + ["Email personalizzata"]
    return names


def _safe_template_filename_from_name(name: str) -> str:
    """Map a display name to a safe .txt filename inside templates dir."""
    raw = (name or "").strip()
    if not raw:
        return ""
    # Disallow path traversal
    raw = raw.replace("/", " ").replace("\\", " ")
    raw = raw.replace("..", ".")
    return f"{raw}.txt"


def _email_template_file_path(template_key: str) -> str:
    templates_dir = get_email_templates_dir()
    for _, key, filename in EMAIL_TEMPLATE_SPECS:
        if key == template_key:
            return os.path.join(templates_dir, filename)
    return os.path.join(templates_dir, f"{template_key}.txt")


def ensure_default_email_templates() -> None:
    """Create missing template files with default content (non-destructive)."""
    templates_dir = get_email_templates_dir()
    for _, key, filename in EMAIL_TEMPLATE_SPECS:
        path = os.path.join(templates_dir, filename)
        if os.path.exists(path):
            continue
        content = DEFAULT_EMAIL_TEMPLATES.get(key, "")
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
                if content and not content.endswith("\n"):
                    f.write("\n")
        except Exception as exc:
            logger.debug("Impossibile creare template email %s: %s", path, exc)


def get_email_template_content(template_key: str) -> str:
    """Read template text from disk.

    Supports both:
    - internal keys (e.g. 'convocazione_cd')
    - display/file names (e.g. 'Convocazione CD – Modalità online')
    """
    # Internal key path (known templates)
    path = _email_template_file_path(template_key)
    # If not a known key, treat it as a filename stem in templates dir
    if not os.path.exists(path):
        filename = _safe_template_filename_from_name(template_key)
        if filename:
            path = os.path.join(get_email_templates_dir(), filename)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as exc:
        logger.debug("Impossibile leggere template email %s: %s", path, exc)
    return DEFAULT_EMAIL_TEMPLATES.get(template_key, "")


class EmailWizard:
    """Wizard for creating emails from templates"""
    def __init__(self, parent, initial: Optional[Dict[str, Any]] = None):
        ensure_default_email_templates()
        self.parent = parent
        self.initial = initial or {}
        self._template_names = list_email_template_names()
        self._template_display_to_key = {
            **{label: key for (label, key, _) in EMAIL_TEMPLATE_SPECS},
            TEMPLATE_NONE_LABEL: "personalizzata",
        }
        self.win = tk.Toplevel(parent)
        self.win.title("📧 Gestione Email")
        self.win.geometry("803x803")
        self.win.transient(parent)

        try:
            self.win.bind("<F5>", lambda e: self._reload_current_template())
        except Exception:
            pass

        self._extra_emails_var = tk.StringVar(value="")
        
        self._build_ui()

        # Apply initial values after UI exists
        try:
            self._apply_initial_values()
        except Exception as exc:
            logger.debug("Failed applying initial values: %s", exc)
    
    def _build_ui(self):
        """Build the wizard UI"""
        # Title
        title_frame = ttk.Frame(self.win)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(title_frame, text="📧 Gestione Email", font=("Segoe UI", 14, "bold")).pack(anchor="w")

        # Main composition area
        main_frame = ttk.Frame(self.win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Data
        row = 0
        ttk.Label(main_frame, text="Data:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.entry_data = ttk.Entry(main_frame, width=15)
        self.entry_data.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        self.entry_data.insert(0, datetime.now().strftime("%d/%m/%Y"))
        ttk.Button(main_frame, text="Oggi", command=self._set_today).grid(row=row, column=2, sticky="w", padx=5, pady=5)
        
        # Oggetto
        row += 1
        ttk.Label(main_frame, text="Oggetto:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.entry_oggetto = ttk.Entry(main_frame, width=60)
        self.entry_oggetto.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        # Selezione soci
        row += 1
        ttk.Label(main_frame, text="Destinatari:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.destinatari_var = tk.StringVar(value="attivi")
        dest_frame = ttk.Frame(main_frame)
        dest_frame.grid(row=row, column=1, columnspan=3, sticky="w", padx=5, pady=5)
        ttk.Radiobutton(dest_frame, text="Soci Attivi", variable=self.destinatari_var, value="attivi", command=self._update_recipient_count).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(dest_frame, text="Consiglio Direttivo", variable=self.destinatari_var, value="cd", command=self._update_recipient_count).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(dest_frame, text="CD + CP", variable=self.destinatari_var, value="cd_cp", command=self._update_recipient_count).pack(side=tk.LEFT, padx=5)
        ttk.Button(dest_frame, text="Anteprima destinatari", command=self._show_recipients).pack(side=tk.LEFT, padx=10)
        self.label_count = ttk.Label(dest_frame, text="", foreground="blue")
        self.label_count.pack(side=tk.LEFT, padx=5)

        # Extra destinatari (aggiuntivi)
        row += 1
        ttk.Label(main_frame, text="Altri destinatari:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        extra_frame = ttk.Frame(main_frame)
        extra_frame.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        self.entry_extra = ttk.Entry(extra_frame, textvariable=self._extra_emails_var, width=60)
        self.entry_extra.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(extra_frame, text="Seleziona...", command=self._select_extra_recipients).pack(side=tk.LEFT, padx=2)
        ttk.Button(extra_frame, text="Pulisci", command=self._clear_extra_recipients).pack(side=tk.LEFT, padx=2)

        # Update count also when extra recipients change
        try:
            self._extra_emails_var.trace_add('write', lambda *_: self._update_recipient_count())
        except Exception:
            pass
        
        # Template selector
        row += 1
        ttk.Label(main_frame, text="Testo email:", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="nw", padx=5, pady=5)
        template_frame = ttk.Frame(main_frame)
        template_frame.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(template_frame, text="Seleziona template:").pack(side=tk.LEFT, padx=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(template_frame, textvariable=self.template_var, width=30, state="readonly")
        self._refresh_template_list(initial=True)
        self.template_combo.current(0)
        self.template_combo.pack(side=tk.LEFT, padx=5)
        self.template_combo.bind('<<ComboboxSelected>>', self._on_template_selected)

        ttk.Button(template_frame, text="↻ Aggiorna", command=self._reload_current_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_frame, text="📁 Template", command=self._open_email_templates_folder).pack(side=tk.LEFT, padx=5)
        
        # Testo email
        row += 1
        text_frame = ttk.LabelFrame(main_frame, text="Corpo del messaggio", padding=5)
        text_frame.grid(row=row, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
        
        self.text_email = scrolledtext.ScrolledText(text_frame, height=15, wrap=tk.WORD)
        self.text_email.pack(fill=tk.BOTH, expand=True)

        # Placeholder fields (optional)
        row += 1
        ph_frame = ttk.LabelFrame(main_frame, text="Placeholder (opzionale)", padding=5)
        ph_frame.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=5)

        ttk.Label(ph_frame, text="Numero CD:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.entry_num_cd = ttk.Entry(ph_frame, width=10)
        self.entry_num_cd.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(ph_frame, text="Data riunione:").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.entry_data_riunione = ttk.Entry(ph_frame, width=15)
        self.entry_data_riunione.grid(row=0, column=3, sticky="w", padx=5, pady=2)

        ttk.Label(ph_frame, text="Ora:").grid(row=0, column=4, sticky="w", padx=5, pady=2)
        self.entry_ora_riunione = ttk.Entry(ph_frame, width=10)
        self.entry_ora_riunione.grid(row=0, column=5, sticky="w", padx=5, pady=2)

        ttk.Label(ph_frame, text="Luogo:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.entry_luogo = ttk.Entry(ph_frame, width=60)
        self.entry_luogo.grid(row=1, column=1, columnspan=5, sticky="ew", padx=5, pady=2)

        ph_frame.columnconfigure(1, weight=1)
        ph_frame.columnconfigure(3, weight=0)
        ph_frame.columnconfigure(5, weight=0)

        row += 1
        online_frame = ttk.LabelFrame(main_frame, text="Modalità online (opzionale)", padding=5)
        online_frame.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=5)

        ttk.Label(online_frame, text="Piattaforma:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.entry_piattaforma = ttk.Entry(online_frame, width=25)
        self.entry_piattaforma.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(online_frame, text="Link:").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.entry_link = ttk.Entry(online_frame, width=55)
        self.entry_link.grid(row=0, column=3, sticky="ew", padx=5, pady=2)

        ttk.Label(online_frame, text="ID riunione:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.entry_id_riunione = ttk.Entry(online_frame, width=25)
        self.entry_id_riunione.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(online_frame, text="Codice accesso:").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.entry_codice_accesso = ttk.Entry(online_frame, width=25)
        self.entry_codice_accesso.grid(row=1, column=3, sticky="w", padx=5, pady=2)

        online_frame.columnconfigure(3, weight=1)
        
        # ODG section
        row += 1
        odg_frame = ttk.LabelFrame(main_frame, text="Ordine del Giorno (opzionale)", padding=5)
        odg_frame.grid(row=row, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
        
        odg_buttons = ttk.Frame(odg_frame)
        odg_buttons.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(odg_buttons, text="Incolla ODG da riunione:").pack(side=tk.LEFT, padx=5)
        ttk.Button(odg_buttons, text="📋 Carica da Riunione", command=self._load_odg_from_meeting).pack(side=tk.LEFT, padx=5)
        
        self.text_odg = scrolledtext.ScrolledText(odg_frame, height=8, wrap=tk.WORD)
        self.text_odg.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        try:
            main_frame.rowconfigure(text_frame.grid_info().get('row', 0), weight=2)
            main_frame.rowconfigure(odg_frame.grid_info().get('row', 0), weight=1)
        except Exception:
            pass
        
        # Buttons (composizione tab actions)
        button_frame = ttk.Frame(self.win)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Gestisci bozze (.eml)", command=self._open_drafts_manager).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Invia con Thunderbird", command=self._send_with_thunderbird).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Salva .eml", command=self._save_eml).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="✓ Crea Email", command=self._create_email, style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Anteprima", command=self._preview_email).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Annulla", command=self.win.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Update recipient count on load
        self._update_recipient_count()
        # Drafts list is loaded on demand via 'Gestisci bozze (.eml)'

    def _open_drafts_manager(self):
        """Open a compact manager for saved .eml drafts."""
        try:
            if hasattr(self, "_drafts_win") and self._drafts_win and self._drafts_win.winfo_exists():
                try:
                    self._drafts_win.lift()
                    self._drafts_win.focus_force()
                except Exception:
                    pass
                self._refresh_eml_list()
                return
        except Exception:
            pass

        dialog = tk.Toplevel(self.win)
        dialog.title("Bozze email (.eml)")
        dialog.geometry("760x520")
        dialog.transient(self.win)

        self._drafts_win = dialog
        self._build_saved_tab(dialog)
        self._refresh_eml_list()

        ttk.Button(dialog, text="Chiudi", command=dialog.destroy).pack(pady=(0, 10))

    def _build_saved_tab(self, frame: tk.Misc):
        """Build the tab that lists saved EML files."""
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, pady=5, padx=5)
        ttk.Button(toolbar, text="Aggiorna elenco", command=self._refresh_eml_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Apri .eml", command=self._open_selected_eml).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Elimina .eml", command=self._delete_selected_eml).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Apri cartella EML", command=self._open_eml_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Avvia Thunderbird", command=self._launch_thunderbird).pack(side=tk.LEFT, padx=2)

        columns = ("oggetto", "data", "file")
        self.eml_tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        self.eml_tree.heading("oggetto", text="Oggetto")
        self.eml_tree.heading("data", text="Data")
        self.eml_tree.heading("file", text="File")
        self.eml_tree.column("oggetto", width=340, anchor="w")
        self.eml_tree.column("data", width=140, anchor="center")
        self.eml_tree.column("file", width=260, anchor="w")

        scrollbar_y = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.eml_tree.yview)
        scrollbar_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.eml_tree.xview)
        self.eml_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.eml_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5))
        scrollbar_x.pack(fill=tk.X, padx=5)
    
    def _set_today(self):
        """Set data field to today"""
        self.entry_data.delete(0, tk.END)
        self.entry_data.insert(0, datetime.now().strftime("%d/%m/%Y"))
    
    def _update_recipient_count(self):
        """Update recipient count label"""
        try:
            base_count = len(self._get_effective_base_recipients())
            extra_count = len(self._parse_extra_emails())
            count = len(self._get_all_recipient_emails())
            suffix = ""
            if extra_count:
                suffix = f" (extra: {extra_count})"
            self.label_count.config(text=f"({count} destinatari; base: {base_count}{suffix})")
        except Exception as e:
            logger.error("Error counting recipients: %s", e)
            self.label_count.config(text="")
    
    def _get_base_recipients(self):
        """Get list of base recipients based on selection."""
        from database import fetch_all
        
        filter_type = self.destinatari_var.get()

        if filter_type in ("cd", "cd_cp"):
            # Roles from definitions (preferred), fallback to legacy filter.
            roles_cd, roles_cp = self._get_roles_for_groups()
            roles: list[str] = list(roles_cd)
            if filter_type == "cd_cp":
                roles = list(dict.fromkeys(list(roles_cd) + list(roles_cp)))

            if roles:
                placeholders = ",".join(["?"] * len(roles))
                sql = f"""
                    SELECT DISTINCT email, nome, cognome
                    FROM soci
                    WHERE attivo = 1
                    AND cd_ruolo IS NOT NULL
                    AND TRIM(cd_ruolo) != ''
                    AND cd_ruolo IN ({placeholders})
                    AND email IS NOT NULL
                    AND email != ''
                    ORDER BY cognome, nome
                """
                return fetch_all(sql, tuple(roles))

        if filter_type == "cd":
            # Only CD members with email
            sql = """
                SELECT DISTINCT email, nome, cognome 
                FROM soci 
                WHERE attivo = 1 
                AND cd_ruolo IS NOT NULL 
                AND cd_ruolo != '' 
                AND cd_ruolo != 'Socio'
                AND cd_ruolo != 'Ex Socio'
                AND email IS NOT NULL 
                AND email != ''
                ORDER BY cognome, nome
            """
        else:  # attivi
            # All active members with email
            sql = """
                SELECT DISTINCT email, nome, cognome 
                FROM soci 
                WHERE attivo = 1 
                AND email IS NOT NULL 
                AND email != ''
                ORDER BY cognome, nome
            """
        
        return fetch_all(sql)

    def _get_effective_base_recipients(self):
        """Return base recipients actually used for sending.

        Se l'utente inserisce/seleziona "Altri destinatari" e la base è CD/CD+CP,
        NON aggiungere automaticamente tutti i destinatari del CD.
        """
        try:
            extra = self._parse_extra_emails()
            base = (self.destinatari_var.get() or "").strip().lower()
            if extra and base in ("cd", "cd_cp"):
                return []
        except Exception:
            pass
        return self._get_base_recipients()

    def _apply_initial_values(self) -> None:
        """Apply initial values passed by caller (e.g., from meeting creation)."""
        # Template selection (do NOT auto-load text if body is provided)
        tmpl = self.initial.get("template") or self.initial.get("template_name")
        if isinstance(tmpl, str) and tmpl.strip():
            try:
                self.template_var.set(tmpl.strip())
            except Exception:
                pass

        dest = (self.initial.get("destinatari") or "").strip().lower()
        if dest in ("attivi", "cd", "cd_cp"):
            try:
                self.destinatari_var.set(dest)
            except Exception:
                pass

        extra = self.initial.get("extra_emails")
        if isinstance(extra, str) and extra.strip():
            self._extra_emails_var.set(extra.strip())
        elif isinstance(extra, list):
            self._append_extra_emails([str(x) for x in extra if str(x).strip()])

        oggetto = self.initial.get("oggetto")
        if isinstance(oggetto, str) and oggetto.strip():
            try:
                self.entry_oggetto.delete(0, tk.END)
                self.entry_oggetto.insert(0, oggetto.strip())
            except Exception:
                pass

        body = self.initial.get("body")
        if isinstance(body, str) and body.strip():
            try:
                self.text_email.delete('1.0', tk.END)
                self.text_email.insert('1.0', body.strip())
            except Exception:
                pass

        # Auto-select Convocazione CD when coming from a meeting, unless caller specified a template
        try:
            is_from_meeting = bool(self.initial.get("from_meeting"))
            if is_from_meeting and not (isinstance(tmpl, str) and tmpl.strip()):
                self.template_var.set("Convocazione CD")
        except Exception:
            pass

        odg = self.initial.get("odg")
        if isinstance(odg, str) and odg.strip():
            try:
                self.text_odg.delete('1.0', tk.END)
                self.text_odg.insert('1.0', odg.strip())
            except Exception:
                pass

        # Optional placeholders
        try:
            num_cd = self.initial.get("num") or self.initial.get("numero_cd")
            if isinstance(num_cd, str) and num_cd.strip() and hasattr(self, 'entry_num_cd'):
                self.entry_num_cd.delete(0, tk.END)
                self.entry_num_cd.insert(0, num_cd.strip())
        except Exception:
            pass

        try:
            data_riunione = self.initial.get("data") or self.initial.get("data_riunione")
            if isinstance(data_riunione, str) and data_riunione.strip() and hasattr(self, 'entry_data_riunione'):
                self.entry_data_riunione.delete(0, tk.END)
                self.entry_data_riunione.insert(0, data_riunione.strip())
        except Exception:
            pass

        try:
            ora = self.initial.get("ora") or self.initial.get("ora_riunione")
            if isinstance(ora, str) and ora.strip() and hasattr(self, 'entry_ora_riunione'):
                self.entry_ora_riunione.delete(0, tk.END)
                self.entry_ora_riunione.insert(0, ora.strip())
        except Exception:
            pass

        try:
            luogo = self.initial.get("luogo")
            if isinstance(luogo, str) and luogo.strip() and hasattr(self, 'entry_luogo'):
                self.entry_luogo.delete(0, tk.END)
                self.entry_luogo.insert(0, luogo.strip())
        except Exception:
            pass

        try:
            piattaforma = self.initial.get("piattaforma")
            if isinstance(piattaforma, str) and piattaforma.strip() and hasattr(self, 'entry_piattaforma'):
                self.entry_piattaforma.delete(0, tk.END)
                self.entry_piattaforma.insert(0, piattaforma.strip())
        except Exception:
            pass

        try:
            link = self.initial.get("link")
            if isinstance(link, str) and link.strip() and hasattr(self, 'entry_link'):
                self.entry_link.delete(0, tk.END)
                self.entry_link.insert(0, link.strip())
        except Exception:
            pass

        try:
            id_riunione = self.initial.get("id_riunione")
            if isinstance(id_riunione, str) and id_riunione.strip() and hasattr(self, 'entry_id_riunione'):
                self.entry_id_riunione.delete(0, tk.END)
                self.entry_id_riunione.insert(0, id_riunione.strip())
        except Exception:
            pass

        try:
            codice_accesso = self.initial.get("codice_accesso")
            if isinstance(codice_accesso, str) and codice_accesso.strip() and hasattr(self, 'entry_codice_accesso'):
                self.entry_codice_accesso.delete(0, tk.END)
                self.entry_codice_accesso.insert(0, codice_accesso.strip())
        except Exception:
            pass

        # Refresh count after all fields
        self._update_recipient_count()

    def _read_definizioni_gruppi(self) -> Dict[str, List[str]]:
        """Parse src/Definizioni/DefinizioniGruppi into {group_line: [role_lines...]}."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, "Definizioni", "DefinizioniGruppi")
        groups: Dict[str, List[str]] = {}
        try:
            if not os.path.exists(path):
                return {}
            current_group: Optional[str] = None
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for raw in f.read().splitlines():
                    line = raw.rstrip("\n")
                    if not line.strip():
                        current_group = None
                        continue
                    if line[:1].isspace():
                        if current_group is None:
                            continue
                        role = line.strip()
                        if role:
                            groups.setdefault(current_group, []).append(role)
                        continue
                    current_group = line.strip()
                    groups.setdefault(current_group, [])
        except Exception:
            return {}
        return groups

    def _normalize_role_label(self, role: str) -> str:
        r = (role or "").strip().lower()
        mapping = {
            "presidente": "Presidente",
            "vicepresidente": "Vice Presidente",
            "vice presidente": "Vice Presidente",
            "segretario": "Segretario",
            "tesoriere": "Tesoriere",
            "consigliere": "Consigliere",
            "probiviro (sindaco)": "Sindaco",
            "probiviro": "Sindaco",
            "sindaco": "Sindaco",
            "socio": "Socio",
        }
        if r in mapping:
            return mapping[r]
        return (role or "").strip().title()

    def _get_roles_for_groups(self) -> tuple[list[str], list[str]]:
        """Return (CD roles, CP roles) using DefinizioniGruppi."""
        groups = self._read_definizioni_gruppi()
        if not groups:
            return ([], [])
        roles_cd: list[str] = []
        roles_cp: list[str] = []
        for group_name, roles in groups.items():
            g = (group_name or "").strip().lower()
            is_cd = "(cd" in g or "consiglio direttivo" in g
            is_cp = "probiviri" in g or "(dp" in g or "(cp" in g
            if not roles:
                continue
            if is_cd:
                for role in roles:
                    val = self._normalize_role_label(role)
                    if val and val not in roles_cd:
                        roles_cd.append(val)
            if is_cp:
                for role in roles:
                    val = self._normalize_role_label(role)
                    if val and val not in roles_cp:
                        roles_cp.append(val)
        return (roles_cd, roles_cp)

    def _parse_extra_emails(self) -> List[str]:
        raw = (self._extra_emails_var.get() or "").strip()
        if not raw:
            return []

        # Normalize separators for getaddresses
        normalized = raw.replace(";", ",").replace("\n", ",").replace("\r", ",")
        emails: List[str] = []
        for _name, addr in getaddresses([normalized]):
            addr = (addr or "").strip()
            if addr:
                emails.append(addr)

        # Deduplicate case-insensitive while preserving order
        seen = set()
        unique: List[str] = []
        for e in emails:
            key = e.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(e)
        return unique

    def _get_all_recipient_emails(self) -> List[str]:
        base_rows = self._get_effective_base_recipients()
        base_emails = [r[0] for r in base_rows]
        extra_emails = self._parse_extra_emails()

        # Merge + dedupe case-insensitive, preserving base order then extra
        seen = set()
        merged: List[str] = []
        for e in base_emails + extra_emails:
            e = (e or "").strip()
            if not e:
                continue
            key = e.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(e)
        return merged

    def _append_extra_emails(self, emails: List[str]) -> None:
        if not emails:
            return
        current = self._parse_extra_emails()
        merged = current + emails
        # Deduplicate (case-insensitive)
        seen = set()
        unique: List[str] = []
        for e in merged:
            key = (e or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(e.strip())
        self._extra_emails_var.set("; ".join(unique))

    def _clear_extra_recipients(self) -> None:
        self._extra_emails_var.set("")
        self._update_recipient_count()

    def _select_extra_recipients(self) -> None:
        """Select additional recipients from members list (multi-select)."""
        from database import fetch_all

        rows = fetch_all(
            """
            SELECT DISTINCT email, nome, cognome, attivo
            FROM soci
            WHERE email IS NOT NULL AND email != ''
            ORDER BY cognome, nome
            """
        )

        dialog = tk.Toplevel(self.win)
        dialog.title("Seleziona altri destinatari")
        dialog.geometry("780x620")
        try:
            dialog.minsize(740, 540)
        except Exception:
            pass
        dialog.transient(self.win)
        dialog.grab_set()
        ttk.Label(
            dialog,
            text="Seleziona i soci da aggiungere:",
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.TOP, anchor="w", padx=10, pady=10)

        # PACK-only layout: body (header + scroll) expands, buttons stay visible.
        outer = ttk.Frame(dialog)
        outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Fixed header row (not scrollable)
        header = ttk.Frame(outer)
        header.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0, 6))
        ttk.Label(header, text="Nome", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Email", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Label(header, text="Attivo", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=(12, 0))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=1)

        # Scrollable list area
        list_area = ttk.Frame(outer)
        list_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(list_area, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_area, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        inner = ttk.Frame(canvas)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(_event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass

        def _on_canvas_configure(event):
            try:
                canvas.itemconfigure(inner_id, width=event.width)
            except Exception:
                pass

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scrolling (Windows)
        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
            except Exception:
                return

        canvas.bind("<MouseWheel>", _on_mousewheel)

        selected_vars: dict[str, tk.BooleanVar] = {}

        for r in rows:
            email = str(r[0] or "").strip()
            if not email:
                continue

            cognome = str(r[2] or "").strip()
            nome = str(r[1] or "").strip()
            attivo = "Sì" if int(r[3]) == 1 else "No"
            name_text = f"{cognome} {nome}".strip() or "(senza nome)"

            var = tk.BooleanVar(value=False)
            selected_vars[email] = var

            rowf = ttk.Frame(inner)
            rowf.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
            rowf.columnconfigure(0, weight=1)
            rowf.columnconfigure(1, weight=1)

            cb = ttk.Checkbutton(rowf, text=name_text, variable=var)
            cb.grid(row=0, column=0, sticky="w")
            ttk.Label(rowf, text=email).grid(row=0, column=1, sticky="w", padx=(12, 0))
            ttk.Label(rowf, text=attivo).grid(row=0, column=2, sticky="w", padx=(12, 0))

        def on_add():
            emails = [e for e, v in selected_vars.items() if bool(v.get())]
            if not emails:
                messagebox.showwarning("Attenzione", "Spunta almeno un destinatario.", parent=dialog)
                return
            self._append_extra_emails(emails)
            self._update_recipient_count()
            dialog.destroy()

        def select_all():
            for v in selected_vars.values():
                v.set(True)

        def clear_all():
            for v in selected_vars.values():
                v.set(False)

        # Buttons row (fixed at bottom)
        btns = ttk.Frame(dialog)
        btns.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        ttk.Button(btns, text="Seleziona tutti", command=select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Deseleziona", command=clear_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Aggiungi selezionati", command=on_add).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text="Annulla", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Finalize geometry so the bottom bar is laid out immediately
        try:
            dialog.update_idletasks()
        except Exception:
            pass
    
    def _show_recipients(self):
        """Show recipients in a dialog"""
        base_recipients = self._get_effective_base_recipients()
        extra_emails = self._parse_extra_emails()
        all_emails = self._get_all_recipient_emails()
        
        dialog = tk.Toplevel(self.win)
        dialog.title("Anteprima Destinatari")
        dialog.geometry("600x400")
        dialog.transient(self.win)
        
        ttk.Label(
            dialog,
            text=f"Destinatari selezionati: {len(all_emails)} (base: {len(base_recipients)}, extra: {len(extra_emails)})",
            font=("Segoe UI", 10, "bold"),
        ).pack(padx=10, pady=10)
        
        # Treeview with scrollbar
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(frame, columns=('email', 'nome'), show='headings', height=15, selectmode='extended')
        tree.heading('email', text='Email')
        tree.heading('nome', text='Nome')
        tree.column('email', width=250)
        tree.column('nome', width=200)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Base recipients (with names)
        for r in base_recipients:
            tree.insert('', 'end', values=(r[0], f"{r[2]} {r[1]}".strip()))

        # Extra recipients (emails only)
        base_lower = {str(r[0]).strip().lower() for r in base_recipients if r and r[0]}
        for email in extra_emails:
            if email.lower() in base_lower:
                continue
            tree.insert('', 'end', values=(email, "(extra)"))

        def on_add_selected_to_extra():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Attenzione", "Seleziona almeno un destinatario.", parent=dialog)
                return
            emails: list[str] = []
            for item in selection:
                vals = tree.item(item).get('values', [])
                if vals and str(vals[0]).strip():
                    emails.append(str(vals[0]).strip())
            self._append_extra_emails(emails)
            self._update_recipient_count()
            dialog.destroy()

        btns = ttk.Frame(dialog)
        btns.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btns, text="Aggiungi selezionati (extra)", command=on_add_selected_to_extra).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text="Chiudi", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _on_template_selected(self, event=None):
        """Load template text when selected"""
        template_name = self.template_var.get()

        if template_name == TEMPLATE_NONE_LABEL:
            key = 'personalizzata'
            template_text = ''
        else:
            key = self._template_display_to_key.get(template_name, template_name)
            template_text = get_email_template_content(key)
        
        self.text_email.delete('1.0', tk.END)
        self.text_email.insert('1.0', template_text)
        
        # Suggest oggetto if not set
        if not self.entry_oggetto.get():
            if key == 'convocazione_cd':
                self.entry_oggetto.delete(0, tk.END)
                self.entry_oggetto.insert(0, "Convocazione Consiglio Direttivo n. {num}")
            elif key == 'convocazione_assemblea':
                self.entry_oggetto.delete(0, tk.END)
                self.entry_oggetto.insert(0, "Convocazione Assemblea Soci")

    def _reload_current_template(self):
        """Aggiorna elenco template e ricarica quello selezionato dal disco.

        Utile quando modifichi un .txt esternamente e vuoi vederlo nel wizard
        senza cambiare selezione nella combobox.
        """
        try:
            self._refresh_template_list()
            template_name = self.template_var.get() or ""
            if template_name == TEMPLATE_NONE_LABEL:
                key = 'personalizzata'
                template_text = ''
            else:
                key = self._template_display_to_key.get(template_name, template_name)
                template_text = get_email_template_content(key)

            current = self.text_email.get('1.0', tk.END)
            current = (current or "").rstrip("\n")
            incoming = (template_text or "").rstrip("\n")

            # Ask confirmation only when overwriting user edits
            if current and current != incoming:
                if not messagebox.askyesno(
                    "Ricarica template",
                    "Il testo attuale sembra modificato.\n\nSovrascrivere con il contenuto del template?",
                    parent=self.win,
                ):
                    return

            self.text_email.delete('1.0', tk.END)
            self.text_email.insert('1.0', template_text)
        except Exception as exc:
            logger.error("Failed reloading email template: %s", exc)
            messagebox.showerror(
                "Template",
                f"Impossibile ricaricare il template:\n{exc}",
                parent=self.win,
            )

    def _refresh_template_list(self, *, initial: bool = False):
        """Refresh combobox values from the templates folder."""
        try:
            current = self.template_var.get() if not initial else ""
            names = list_email_template_names()
            self._template_names = names
            values = (TEMPLATE_NONE_LABEL, *names)
            self.template_combo['values'] = values
            if initial:
                self.template_var.set(TEMPLATE_NONE_LABEL)
                return
            if current and current in values:
                self.template_var.set(current)
            else:
                self.template_var.set(TEMPLATE_NONE_LABEL)
        except Exception as exc:
            logger.debug("Failed refreshing template list: %s", exc)

    def _open_email_templates_folder(self):
        """Open the folder containing email template .txt files."""
        try:
            from utils import open_path

            open_path(get_email_templates_dir())
        except Exception as exc:
            logger.error("Failed opening email templates folder: %s", exc)
            messagebox.showerror(
                "Template",
                f"Impossibile aprire la cartella template:\n{exc}",
                parent=self.win,
            )
    
    def _load_odg_from_meeting(self):
        """Load ODG from a CD meeting"""
        from cd_meetings import get_all_meetings
        
        # Get recent meetings
        meetings = get_all_meetings()
        if not meetings:
            messagebox.showinfo("Info", "Nessuna riunione trovata nel database.", parent=self.win)
            return
        
        # Create selection dialog
        dialog = tk.Toplevel(self.win)
        dialog.title("Seleziona Riunione")
        dialog.geometry("700x400")
        dialog.transient(self.win)
        
        ttk.Label(dialog, text="Seleziona una riunione da cui copiare l'ODG:", font=("Segoe UI", 10, "bold")).pack(padx=10, pady=10)
        
        # Treeview
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(frame, columns=('id', 'data', 'titolo'), show='headings', height=12)
        tree.heading('id', text='ID')
        tree.heading('data', text='Data')
        tree.heading('titolo', text='Titolo')
        tree.column('id', width=50)
        tree.column('data', width=100)
        tree.column('titolo', width=400)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        for m in meetings:
            tree.insert('', 'end', values=(m['id'], m['data'], m['titolo'] or ''))
        
        def on_select():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Attenzione", "Seleziona una riunione.", parent=dialog)
                return
            
            meeting_id = tree.item(selection[0])['values'][0]
            from cd_meetings import get_meeting_by_id
            meeting = get_meeting_by_id(int(meeting_id))
            
            if meeting and meeting.get('odg'):
                self.text_odg.delete('1.0', tk.END)
                self.text_odg.insert('1.0', meeting['odg'])
                dialog.destroy()
            else:
                messagebox.showinfo("Info", "Questa riunione non ha un ODG associato.", parent=dialog)
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text="Carica ODG", command=on_select).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Annulla", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _preview_email(self):
        """Show email preview"""
        subject = self.entry_oggetto.get().strip()
        body = self._build_body_text()
        
        # Show preview dialog
        dialog = tk.Toplevel(self.win)
        dialog.title("Anteprima Email")
        dialog.geometry("700x500")
        dialog.transient(self.win)
        
        ttk.Label(dialog, text="Oggetto:", font=("Segoe UI", 10, "bold")).pack(anchor='w', padx=10, pady=(10, 0))
        subject_text = tk.Text(dialog, height=2, wrap=tk.WORD)
        subject_text.pack(fill=tk.X, padx=10, pady=5)
        subject_text.insert('1.0', subject)
        subject_text.config(state='disabled')
        
        ttk.Label(dialog, text="Corpo:", font=("Segoe UI", 10, "bold")).pack(anchor='w', padx=10, pady=(10, 0))
        body_text = scrolledtext.ScrolledText(dialog, height=20, wrap=tk.WORD)
        body_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        body_text.insert('1.0', body)
        body_text.config(state='disabled')
        
        ttk.Button(dialog, text="Chiudi", command=dialog.destroy).pack(pady=10)
    
    def _create_email(self):
        """Generate mailto URL and open email client"""
        try:
            subject, body, bcc_emails = self._collect_email_parts()
        except ValueError:
            return
        bcc_str = ','.join(bcc_emails)
        
        # Create mailto URL
        mailto_url = f"mailto:?subject={urllib.parse.quote(subject)}&bcc={urllib.parse.quote(bcc_str)}&body={urllib.parse.quote(body)}"
        
        # Check URL length (some email clients have limits)
        if len(mailto_url) > 2000:
            # Fallback: copy to clipboard
            result = messagebox.askyesno(
                "URL Troppo Lungo",
                f"L'email è troppo lunga per il comando mailto.\n\n"
                f"Destinatari: {len(bcc_emails)}\n\n"
                f"Vuoi copiare i dati negli appunti?",
                parent=self.win
            )
            if result:
                clipboard_text = f"Oggetto:\n{subject}\n\nDestinatari (BCC):\n{bcc_str}\n\nCorpo:\n{body}"
                self.win.clipboard_clear()
                self.win.clipboard_append(clipboard_text)
                messagebox.showinfo("Successo", "Dati copiati negli appunti!", parent=self.win)
        else:
            # Open email client
            try:
                webbrowser.open(mailto_url)
                messagebox.showinfo("Successo", f"Email preparata con {len(bcc_emails)} destinatari in BCC.", parent=self.win)
                self.win.destroy()
            except Exception as e:
                logger.error("Failed to open email client: %s", e)
                messagebox.showerror("Errore", f"Impossibile aprire il client email:\n{e}", parent=self.win)

    def _send_with_thunderbird(self):
        """Apri la composizione in Thunderbird con i dati correnti o dalla selezione EML."""
        subject = body = None
        bcc_emails: List[str] = []

        try:
            subject, body, bcc_emails = self._collect_email_parts(show_warnings=False)
        except ValueError:
            eml_parts = self._get_selected_eml_parts()
            if eml_parts:
                subject, body, bcc_emails = eml_parts
            else:
                # show the validation warning from the form
                self._collect_email_parts(show_warnings=True)
                return

        exe = self._get_thunderbird_path()
        if not exe or not os.path.exists(exe):
            messagebox.showerror(
                "Thunderbird",
                "Percorso Thunderbird non configurato o non trovato. Imposta il percorso in Preferenze > Client posta.",
                parent=self.win,
            )
            return

        compose_parts = [
            f"subject='{self._escape_thunderbird_value(subject or '')}'",
            f"body='{self._escape_thunderbird_value(body or '')}'",
        ]
        if bcc_emails:
            bcc_joined = ",".join(bcc_emails)
            compose_parts.append(f"bcc='{self._escape_thunderbird_value(bcc_joined)}'")
        compose_str = ",".join(compose_parts)

        try:
            subprocess.Popen([exe, "-compose", compose_str])
            messagebox.showinfo(
                "Thunderbird",
                f"Bozza creata con {len(bcc_emails)} destinatari in BCC.",
                parent=self.win,
            )
        except FileNotFoundError:
            messagebox.showerror("Thunderbird", f"Percorso Thunderbird non valido:\n{exe}", parent=self.win)
        except Exception as exc:
            logger.error("Impossibile avviare Thunderbird: %s", exc)
            messagebox.showerror("Thunderbird", f"Impossibile avviare Thunderbird:\n{exc}", parent=self.win)

    def _get_selected_eml_parts(self):
        """Se è selezionato un .eml nella tab, restituisce (subject, body, bcc list)."""
        if not hasattr(self, 'eml_tree'):
            return None
        selection = self.eml_tree.selection()
        if not selection:
            messagebox.showwarning(
                "Thunderbird",
                "Compila l'oggetto oppure seleziona un .eml dalla tab Email salvate.",
                parent=self.win,
            )
            return None
        fname = self.eml_tree.item(selection[0]).get('values', ['','', ''])[-1]
        path = os.path.join(SEC_DOCS, "email_eml", fname)
        if not os.path.exists(path):
            messagebox.showerror("Thunderbird", f"File non trovato:\n{path}", parent=self.win)
            self._refresh_eml_list()
            return None
        try:
            with open(path, 'rb') as fp:
                msg = BytesParser(policy=policy.default).parse(fp)
        except Exception as exc:
            logger.error("Impossibile leggere il file .eml %s: %s", path, exc)
            messagebox.showerror("Thunderbird", f"Impossibile leggere il file .eml:\n{exc}", parent=self.win)
            return None

        subject = (msg.get('Subject') or '').strip()
        bcc_header = msg.get('Bcc') or ''
        bcc_emails = [addr for _name, addr in getaddresses([bcc_header]) if addr]

        body = ""
        try:
            if msg.is_multipart():
                preferred = msg.get_body(preferencelist=('plain',))
                if preferred:
                    body = preferred.get_content()
                else:
                    alt = msg.get_body(preferencelist=('html',))
                    body = alt.get_content() if alt else ""
            else:
                body = msg.get_content()
        except Exception as exc:
            logger.warning("Errore leggendo il corpo da %s: %s", fname, exc)
            try:
                body = msg.get_content()
            except Exception:
                body = ""

        return subject, body, bcc_emails

    def _build_body_text(self) -> str:
        return self.text_email.get('1.0', tk.END).strip()

    def _safe_get_entry_value(self, entry: Any) -> str:
        try:
            return (entry.get() or "").strip()
        except Exception:
            return ""

    def _get_role_person_display(self, role_label: str) -> str:
        """Return 'Nome Cognome, CALL' for the first active member with cd_ruolo matching role."""
        try:
            from database import fetch_one

            role = (role_label or "").strip()
            if not role:
                return ""
            row = fetch_one(
                """
                SELECT nome, cognome, nominativo
                FROM soci
                WHERE attivo = 1
                  AND cd_ruolo IS NOT NULL
                  AND TRIM(cd_ruolo) != ''
                  AND LOWER(TRIM(cd_ruolo)) = LOWER(?)
                ORDER BY cognome, nome
                LIMIT 1
                """,
                (role,),
            )
            if not row:
                return ""
            nome = (row[0] if not hasattr(row, 'keys') else row['nome']) or ""
            cognome = (row[1] if not hasattr(row, 'keys') else row['cognome']) or ""
            call = (row[2] if not hasattr(row, 'keys') else row['nominativo']) or ""
            base = f"{nome} {cognome}".strip()
            call = str(call).strip()
            if call:
                return f"{base}, {call}" if base else call
            return base
        except Exception:
            return ""

    def _get_placeholder_values(self) -> Dict[str, str]:
        """Collect placeholder values from UI and DB."""
        odg = ""
        try:
            odg = (self.text_odg.get('1.0', tk.END) or "").strip()
        except Exception:
            odg = ""

        data_riunione = self._safe_get_entry_value(getattr(self, 'entry_data_riunione', None))
        if not data_riunione:
            # fallback to the generic 'Data' field
            data_riunione = self._safe_get_entry_value(getattr(self, 'entry_data', None))

        values: Dict[str, str] = {
            "presidente": self._get_role_person_display("Presidente"),
            "segretario": self._get_role_person_display("Segretario"),
            "num": self._safe_get_entry_value(getattr(self, 'entry_num_cd', None)),
            "data": data_riunione,
            "ora": self._safe_get_entry_value(getattr(self, 'entry_ora_riunione', None)),
            "odg": odg,
            "luogo": self._safe_get_entry_value(getattr(self, 'entry_luogo', None)),
            "piattaforma": self._safe_get_entry_value(getattr(self, 'entry_piattaforma', None)),
            "link": self._safe_get_entry_value(getattr(self, 'entry_link', None)),
            "id_riunione": self._safe_get_entry_value(getattr(self, 'entry_id_riunione', None)),
            "codice_accesso": self._safe_get_entry_value(getattr(self, 'entry_codice_accesso', None)),
        }
        return values

    def _apply_placeholders(self, text: str) -> str:
        """Replace {placeholder} tokens when values are available.

        If a value is empty, the placeholder is left as-is.
        """
        out = text or ""
        values = self._get_placeholder_values()
        for key, value in values.items():
            if not value:
                continue
            out = out.replace(f"{{{key}}}", value)
        return out

    def _collect_email_parts(self, show_warnings: bool = True):
        """Return (subject, body, bcc_emails); raise ValueError if validation fails."""
        subject = self.entry_oggetto.get().strip()
        if not subject:
            if show_warnings:
                messagebox.showwarning("Attenzione", "Inserisci l'oggetto dell'email.", parent=self.win)
            raise ValueError("missing subject")

        subject = self._apply_placeholders(subject)

        body = self._build_body_text()
        body = self._apply_placeholders(body)
        if not body:
            if show_warnings:
                messagebox.showwarning("Attenzione", "Inserisci il testo dell'email.", parent=self.win)
            raise ValueError("missing body")

        bcc_emails = self._get_all_recipient_emails()
        if not bcc_emails:
            if show_warnings:
                messagebox.showwarning("Attenzione", "Nessun destinatario trovato.", parent=self.win)
            raise ValueError("no recipients")
        return subject, body, bcc_emails

    def _save_eml(self):
        """Export the composed email to a .eml file."""
        try:
            subject, body, bcc_emails = self._collect_email_parts()
        except ValueError:
            return

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['To'] = 'undisclosed-recipients:;'
        if bcc_emails:
            msg['Bcc'] = ', '.join(bcc_emails)
        msg['Date'] = format_datetime(datetime.now())
        msg.set_content(body)

        safe_subject = subject.replace(' ', '_').replace('/', '-').replace('\\', '-').replace(':', '-').replace('*', '-').replace('?', '-').replace('"', "'").replace('<', '-').replace('>', '-').replace('|', '-')[0:60]
        default_name = f"eml_{safe_subject}-{datetime.now():%Y%m%d}.eml"
        default_dir = os.path.join(SEC_DOCS, "email_eml")
        try:
            os.makedirs(default_dir, exist_ok=True)
        except Exception as exc:
            logger.warning("Impossibile creare cartella EML %s: %s", default_dir, exc)
            default_dir = None
        path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Salva email come .eml",
            defaultextension=".eml",
            filetypes=[("EML file", "*.eml"), ("Tutti i file", "*.*")],
            initialdir=default_dir,
            initialfile=default_name,
        )
        if not path:
            return

        if not path.lower().endswith('.eml'):
            path += '.eml'

        try:
            with open(path, 'wb') as f:
                f.write(msg.as_bytes())
            messagebox.showinfo("Esporta .eml", f"File salvato:\n{path}", parent=self.win)
        except Exception as exc:
            logger.error("Errore salvataggio EML: %s", exc)
            messagebox.showerror("Errore", f"Impossibile salvare il file .eml:\n{exc}", parent=self.win)

    # --------------------------------------------------
    # Email salvate (.eml)
    # --------------------------------------------------
    def _refresh_eml_list(self):
        directory = os.path.join(SEC_DOCS, "email_eml")
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as exc:
            logger.error("Impossibile creare cartella EML: %s", exc)
            messagebox.showerror("Errore", f"Impossibile creare la cartella EML:\n{exc}", parent=self.win)
            return

        if not hasattr(self, 'eml_tree'):
            return

        for item in self.eml_tree.get_children():
            self.eml_tree.delete(item)

        try:
            files = [f for f in os.listdir(directory) if f.lower().endswith('.eml')]
        except Exception as exc:
            logger.error("Impossibile elencare i file EML: %s", exc)
            messagebox.showerror("Errore", f"Impossibile leggere la cartella EML:\n{exc}", parent=self.win)
            return

        rows = []
        for fname in files:
            path = os.path.join(directory, fname)
            subject = "(senza oggetto)"
            date_str = ""
            try:
                with open(path, 'rb') as fp:
                    msg = BytesParser(policy=policy.default).parse(fp)
                subject = msg.get('Subject') or subject
                dt = None
                try:
                    if msg.get('Date'):
                        dt = parsedate_to_datetime(msg.get('Date'))
                except Exception:
                    dt = None
                if not dt:
                    ts = os.path.getmtime(path)
                    dt = datetime.fromtimestamp(ts)
                date_str = dt.strftime('%Y-%m-%d %H:%M') if dt else ""
            except Exception as exc:
                logger.warning("Errore leggendo %s: %s", fname, exc)
                try:
                    ts = os.path.getmtime(path)
                    date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    date_str = ""

            rows.append((subject, date_str, fname))

        # sort by date desc
        rows.sort(key=lambda r: r[1], reverse=True)
        for subject, date_str, fname in rows:
            self.eml_tree.insert('', 'end', values=(subject, date_str, fname))

    def _open_selected_eml(self):
        if not hasattr(self, 'eml_tree'):
            return
        selection = self.eml_tree.selection()
        if not selection:
            messagebox.showinfo("Apri .eml", "Seleziona un file dall'elenco.", parent=self.win)
            return
        fname = self.eml_tree.item(selection[0]).get('values', ['','', ''])[-1]
        path = os.path.join(SEC_DOCS, "email_eml", fname)
        if not os.path.exists(path):
            messagebox.showerror("Errore", f"File non trovato:\n{path}", parent=self.win)
            self._refresh_eml_list()
            return
        try:
            os.startfile(path)
        except Exception as exc:
            logger.error("Impossibile aprire %s: %s", path, exc)
            messagebox.showerror("Errore", f"Impossibile aprire il file .eml:\n{exc}", parent=self.win)

    def _delete_selected_eml(self):
        if not hasattr(self, 'eml_tree'):
            return
        selection = self.eml_tree.selection()
        if not selection:
            messagebox.showinfo("Elimina .eml", "Seleziona un file dall'elenco.", parent=self.win)
            return
        fname = self.eml_tree.item(selection[0]).get('values', ['','', ''])[-1]
        path = os.path.join(SEC_DOCS, "email_eml", fname)
        if not os.path.exists(path):
            messagebox.showerror("Errore", f"File non trovato:\n{path}", parent=self.win)
            self._refresh_eml_list()
            return
        if not messagebox.askyesno("Conferma", f"Vuoi eliminare il file:\n{fname}?", parent=self.win):
            return
        try:
            os.remove(path)
            self.eml_tree.delete(selection[0])
        except Exception as exc:
            logger.error("Impossibile eliminare %s: %s", path, exc)
            messagebox.showerror("Errore", f"Impossibile eliminare il file .eml:\n{exc}", parent=self.win)

    def _open_eml_folder(self):
        directory = os.path.join(SEC_DOCS, "email_eml")
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("Errore", f"Impossibile creare la cartella EML:\n{exc}", parent=self.win)
            return
        try:
            os.startfile(directory)
        except Exception as exc:
            logger.error("Impossibile aprire la cartella EML: %s", exc)
            messagebox.showerror("Errore", f"Impossibile aprire la cartella EML:\n{exc}", parent=self.win)

    def _launch_thunderbird(self):
        directory = os.path.join(SEC_DOCS, "email_eml")
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("Errore", f"Impossibile creare la cartella EML:\n{exc}", parent=self.win)
            return
        exe = self._get_thunderbird_path()
        if not exe or not os.path.exists(exe):
            messagebox.showerror("Thunderbird", "Percorso Thunderbird non configurato o non trovato. Imposta il percorso in Preferenze > Client posta.", parent=self.win)
            return
        try:
            subprocess.Popen([exe], cwd=directory)
        except Exception as exc:
            logger.error("Impossibile avviare Thunderbird: %s", exc)
            messagebox.showerror("Thunderbird", f"Impossibile avviare Thunderbird:\n{exc}", parent=self.win)

    @staticmethod
    def _escape_thunderbird_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _get_thunderbird_path(self) -> str:
        try:
            cfg = load_config()
            cfg_path = (cfg or {}).get("thunderbird_path") or ""
        except Exception:
            cfg_path = ""
        return cfg_path or THUNDERBIRD_EXE


def show_email_wizard(parent, initial: Optional[Dict[str, Any]] = None):
    """Show the email wizard."""
    EmailWizard(parent, initial=initial)
