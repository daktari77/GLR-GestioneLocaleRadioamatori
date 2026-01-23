# -*- coding: utf-8 -*-
"""Main application window for GLR - Gestione Locale Radioamatori."""

import csv
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from pathlib import Path
import os
from datetime import datetime, timedelta
from typing import Literal, Mapping, Sequence

from calendar_utils import events_to_ics
from .calendar_wizard import CalendarWizard, EVENT_TYPES as CALENDAR_EVENT_TYPES
from .treeview_tags import CategoryTagStyler, MEMBER_CATEGORY_PALETTE, SECTION_CATEGORY_PALETTE
from .ponti_panel import PontiPanel
from .magazzino_panel import MagazzinoPanel
from .unified_export_wizard import UnifiedExportWizard
from .unified_import_wizard import UnifiedImportWizard
from startup_checks import StartupIssue, format_startup_issues

logger = logging.getLogger("librosoci")

__all__ = ["App"]

TreeviewAnchor = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]


class App:
    """Main application class for GLR - Gestione Locale Radioamatori"""
    
    COLONNE = (
        "id",
        "matricola",
        "nominativo",
        "nome",
        "cognome",
        "socio",
        "attivo",
        "voto",
        "q0",
        "q1",
        "q2",
        "familiare",
        "email",
        "citta",
        "provincia",
        "privacy_signed",
    )
    VISIBLE_COLUMNS = tuple(col for col in COLONNE if col != "id")
    COLONNE_DISPLAY = ("⚠",) + VISIBLE_COLUMNS
    HEADER_TITLES = {
        "⚠": "⚠",
        "matricola": "Matricola",
        "nominativo": "Nominativo",
        "nome": "Nome",
        "cognome": "Cognome",
        "socio": "Tipo",
        "attivo": "Attivo",
        "voto": "Voto",
        "q0": "Q0",
        "q1": "Q1",
        "q2": "Q2",
        "familiare": "Familiare",
        "email": "Email",
        "citta": "Città",
        "provincia": "Provincia",
        "privacy_signed": "Privacy",
    }
    
    def __init__(self, *, startup_issues: Sequence[StartupIssue] | None = None):
        """Initialize the application."""
        # Import configuration after logger is set up; DB setup already happens in main.py
        from config import APP_NAME, APP_VERSION, AUTHOR, BUILD_ID, BUILD_DATE
        
        # Create root window
        self.root = tk.Tk()

        # Global typography (Tk/ttk): keep it consistent across the whole app
        try:
            from .styles import configure_global_fonts, ensure_app_named_fonts

            configure_global_fonts(self.root, family="Segoe UI", size=9)
            ensure_app_named_fonts(self.root)
        except Exception:
            pass

        self.root.title(f"{APP_NAME} - Revisione {APP_VERSION} - Build {BUILD_ID}")
        # Window sized to comfortably fit 20 rows while staying within 1900x850 footprint
        self.root.geometry("1300x860")
        # Enforce a minimum so layout widgets never collapse
        self.root.minsize(1300, 860)
        # Center the window on screen
        self.root.update_idletasks()
        width = 1300
        height = 860
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        # Ensure closing main window also closes all Toplevel dialogs
        self.root.protocol("WM_DELETE_WINDOW", self._on_root_close)
        
        # Load configuration
        from config_manager import load_config
        self.cfg = load_config()
        
        # State variables
        self.current_member_id = None
        self.calendar_events = []
        self.calendar_type_labels = {code: label for code, label in CALENDAR_EVENT_TYPES}
        self.member_lookup = {}
        self.startup_issues = list(startup_issues or [])

        # Optional UI widgets created lazily by tab builders (helps static analysis)
        self.tv_cd_riunioni: ttk.Treeview | None = None
        self.tv_cd_delibere_overview: ttk.Treeview | None = None
        # Legacy attribute used by older CD delibere tab implementations
        self.tv_cd_delibere: ttk.Treeview | None = None
        
        # Update title with section info
        self._update_title()
        
        # Build UI
        self._build_ui()
        
        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()
        
        # Load initial data
        self._refresh_member_list()

        # Betatest presentation (first run only, per version)
        try:
            self.root.after(500, self._maybe_show_betatest_intro)
        except Exception:
            pass
        
        # Start event loop
        self.root.mainloop()

    def _maybe_show_betatest_intro(self):
        """Show the betatest welcome guide once per app version."""
        try:
            from config import APP_VERSION

            # Betatest is scoped to the 0.4.5* line.
            if not str(APP_VERSION).startswith("0.4.5"):
                return

            key = f"betatest_intro_shown::{APP_VERSION}"
            already_shown = bool((self.cfg or {}).get(key))
            if already_shown:
                return

            self._show_betatest_intro_dialog(version=APP_VERSION, flag_key=key)
        except Exception:
            return

    def _read_betatest_guide_text(self) -> str:
        """Load the betatest guide markdown as plain text (best-effort)."""
        candidates: list[Path] = []
        try:
            # Source layout: repo root is two levels above v4_ui/
            candidates.append(Path(__file__).resolve().parents[2] / "docs" / "BETATEST_GUIDE.md")
        except Exception:
            pass

        try:
            if getattr(sys, "frozen", False):
                exe_dir = Path(sys.executable).resolve().parent
                candidates.append(exe_dir / "docs" / "BETATEST_GUIDE.md")
                # Seeded portable layout: build script copies seed under dist\data\...
                candidates.append(exe_dir / "data" / "docs" / "BETATEST_GUIDE.md")
                candidates.append(exe_dir / "data" / "BETATEST_GUIDE.md")
        except Exception:
            pass

        for p in candidates:
            try:
                if p.exists():
                    return p.read_text(encoding="utf-8")
            except Exception:
                continue

        return (
            "Benvenuto nel betatest di GLR – Gestione Locale Radioamatori.\n\n"
            "La guida completa non è stata trovata sul disco (docs/BETATEST_GUIDE.md).\n"
            "Contatta il coordinatore del betatest per ottenerla.\n"
        )

    def _show_betatest_intro_dialog(self, *, version: str, flag_key: str) -> None:
        """Modal welcome dialog that displays the betatest guide."""
        win = tk.Toplevel(self.root)
        win.title(f"Benvenuto al betatest – v{version}")
        try:
            win.transient(self.root)
        except Exception:
            pass

        # Reasonable default size; user can resize.
        try:
            win.geometry("900x700")
            win.minsize(720, 520)
        except Exception:
            pass

        container = ttk.Frame(win)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        header = ttk.Label(container, text=f"Guida Betatest (v{version})", font="AppBold")
        header.pack(anchor="w")

        sub = ttk.Label(
            container,
            text="Leggi le istruzioni e la checklist. Questa schermata viene mostrata solo al primo avvio.",
        )
        sub.pack(anchor="w", pady=(2, 10))

        text_frame = ttk.Frame(container)
        text_frame.pack(fill=tk.BOTH, expand=True)

        yscroll = ttk.Scrollbar(text_frame, orient="vertical")
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        text = tk.Text(
            text_frame,
            wrap="word",
            yscrollcommand=yscroll.set,
        )
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.config(command=text.yview)

        guide_text = self._read_betatest_guide_text()
        try:
            text.insert("1.0", guide_text)
        except Exception:
            pass
        try:
            text.config(state="disabled")
        except Exception:
            pass

        btns = ttk.Frame(container)
        btns.pack(fill=tk.X, pady=(10, 0))

        def _close():
            try:
                cfg = dict(self.cfg or {})
                cfg[flag_key] = True
                self.cfg = cfg
                from config_manager import save_config

                save_config(cfg)
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

        ttk.Button(btns, text="Chiudi", command=_close).pack(side=tk.RIGHT)

        try:
            win.protocol("WM_DELETE_WINDOW", _close)
        except Exception:
            pass

        try:
            win.grab_set()
            win.focus_set()
        except Exception:
            pass
    
    def _update_title(self):
        """Update window title with section information."""
        from config import APP_NAME, APP_VERSION, BUILD_ID
        title = f"{APP_NAME} - Revisione {APP_VERSION} (Build {BUILD_ID})"
        if self.cfg.get("nome_sezione"):
            code = self.cfg.get("codice_sezione") or ""
            title += f" — {self.cfg['nome_sezione']}"
            if code:
                title += f" ({code})"
        self.root.title(title)
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for common operations."""
        # Ctrl+N: New member
        self.root.bind("<Control-n>", lambda e: self._add_member())
        self.root.bind("<Control-N>", lambda e: self._add_member())
        
        # Ctrl+S: Save (if in edit mode)
        self.root.bind("<Control-s>", lambda e: self._save_if_editing())
        self.root.bind("<Control-S>", lambda e: self._save_if_editing())
        
        # F5: Refresh member list
        self.root.bind("<F5>", lambda e: self._refresh_member_list())
        
        # Ctrl+F: Focus search field
        self.root.bind("<Control-f>", lambda e: self._focus_search())
        self.root.bind("<Control-F>", lambda e: self._focus_search())
        
        # Ctrl+E: Export
        self.root.bind("<Control-e>", lambda e: self._show_export_dialog())
        self.root.bind("<Control-E>", lambda e: self._show_export_dialog())
        
        # Ctrl+B: Backup
        self.root.bind("<Control-b>", lambda e: self._manual_backup())

        # Global Delete handling (only for Magazzino treeview)
        # This improves reliability of the "Canc" key without affecting text fields.
        try:
            self.root.bind("<Delete>", self._on_global_delete_key)
            self.root.bind("<KP_Delete>", self._on_global_delete_key)
        except Exception:
            pass

    def _on_global_delete_key(self, event):
        """Handle Delete key globally but only when Magazzino Treeview has focus."""
        try:
            panel = getattr(self, "magazzino_panel", None)
            if panel is None:
                return None

            tree = getattr(panel, "tree", None)
            if tree is None:
                return None

            try:
                focused = self.root.focus_get()
            except Exception:
                focused = None

            if focused is tree:
                handler = getattr(panel, "_on_delete_key", None)
                if callable(handler):
                    try:
                        return handler(event)
                    except Exception:
                        return "break"
        except Exception:
            return None

        return None

    def _show_preferences_dialog(self):
        """Show the preferences dialog for customizable options."""
        try:
            from v4_ui.preferences_dialog import PreferencesDialog

            PreferencesDialog(self.root, cfg=self.cfg, on_save=self._on_preferences_saved)
        except Exception as exc:
            logger.error("Errore apertura preferenze: %s", exc)
            messagebox.showerror("Preferenze", f"Impossibile aprire le preferenze:\n{exc}")

    def _on_preferences_saved(self, new_cfg: dict | None = None):
        """Refresh UI elements after preference changes."""
        if new_cfg is not None:
            self.cfg = new_cfg
        try:
            self.form_member.reload_role_options(self.cfg)
        except Exception as exc:
            logger.warning("Impossibile ricaricare le opzioni ruolo: %s", exc)

        try:
            panel = getattr(self, "panel_docs", None)
            if panel is not None and hasattr(panel, "reload_category_options"):
                panel.reload_category_options(self.cfg)
        except Exception as exc:
            logger.warning("Impossibile ricaricare le categorie documenti soci: %s", exc)

        try:
            panel = getattr(self, "section_docs_panel", None)
            if panel is not None and hasattr(panel, "reload_category_options"):
                panel.reload_category_options(self.cfg)
        except Exception as exc:
            logger.warning("Impossibile ricaricare le categorie documenti sezione: %s", exc)
        else:
            self._set_status_message("Preferenze aggiornate")
    
    def _save_if_editing(self):
        """Save if currently editing a member."""
        # This will be implemented when form has save button reference
        logger.debug("Save shortcut pressed (Ctrl+S)")
        # Could check if form is visible and call save
    
    def _focus_search(self):
        """Focus the search field."""
        if hasattr(self, 'search_var'):
            # Find the search entry widget and focus it
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.Frame):
                    self._find_and_focus_search(widget)
    
    def _find_and_focus_search(self, parent):
        """Recursively find and focus search entry."""
        for widget in parent.winfo_children():
            if isinstance(widget, ttk.Entry) and hasattr(widget, 'textvariable'):
                if widget['textvariable'] == str(self.search_var):
                    widget.focus_set()
                    return True
            elif isinstance(widget, (ttk.Frame, tk.Frame)):
                if self._find_and_focus_search(widget):
                    return True
        return False
    
    def _next_tab(self):
        """Switch to next notebook tab."""
        try:
            current = self.notebook.index(self.notebook.select())
            total = self.notebook.index("end")
            next_tab = (current + 1) % total
            self.notebook.select(next_tab)
        except Exception:
            pass
    
    def _prev_tab(self):
        """Switch to previous notebook tab."""
        try:
            current = self.notebook.index(self.notebook.select())
            total = self.notebook.index("end")
            prev_tab = (current - 1) % total
            self.notebook.select(prev_tab)
        except Exception:
            pass
    
    def _select_tab(self, index: int):
        """Select tab by index."""
        try:
            total = self.notebook.index("end")
            if 0 <= index < total:
                self.notebook.select(index)
        except Exception:
            pass
    
    def _manual_backup(self):
        """Chiede all'utente se eseguire backup solo DB o FULL (DB+documenti) e agisce di conseguenza."""
        from backup import backup_on_demand
        from documents_backup import backup_documents
        from config import DATA_DIR, DB_NAME, get_backup_dir
        from tkinter import messagebox, simpledialog

        # Chiedi all'utente la modalità di backup
        resp = messagebox.askyesnocancel(
            "Backup manuale",
            "Vuoi eseguire il backup FULL (database + documenti)?\n\n"
            "Sì = FULL (DB + documenti)\nNo = Solo database\nAnnulla = Annulla backup."
        )
        if resp is None:
            return  # Annullato
        try:
            if resp:
                # FULL: backup DB + documenti
                success, result = backup_on_demand(DATA_DIR, DB_NAME, get_backup_dir())
                if success:
                    # Backup documenti FULL
                    dest_dir, changed = backup_documents(DATA_DIR, get_backup_dir(), mode='full')
                    messagebox.showinfo(
                        "Backup FULL",
                        f"Backup DB creato:\n{result}\n\nBackup documenti (full): {changed} file in {dest_dir}"
                    )
                else:
                    messagebox.showerror("Errore Backup", f"Backup DB non riuscito:\n{result}")
            else:
                # Solo DB
                success, result = backup_on_demand(DATA_DIR, DB_NAME, get_backup_dir())
                if success:
                    messagebox.showinfo("Backup DB", f"Archivio DB creato:\n{result}")
                else:
                    messagebox.showerror("Errore Backup", f"Backup DB non riuscito:\n{result}")
        except Exception as e:
            messagebox.showerror("Errore Backup", f"Errore durante il backup manuale:\n{str(e)}")
            logger.error(f"Manual backup failed: {e}")

    def _reset_to_factory(self):
        """Reset application to factory defaults with optional backup."""
        # First confirmation
        if not messagebox.askyesno(
            "Reset ai dati di fabbrica",
            "⚠️ ATTENZIONE: Questa operazione eliminerà tutti i dati dell'applicazione!\n\n"
            "• Tutti i soci e i loro documenti verranno eliminati\n"
            "• Il database verrà svuotato\n"
            "• La configurazione verrà resettata\n\n"
            "L'applicazione verrà riavviata e mostrerà nuovamente il wizard di configurazione iniziale.\n\n"
            "Sei sicuro di voler procedere?",
            icon="warning"
        ):
            return

        # Ask about backup
        do_backup = messagebox.askyesno(
            "Backup prima del reset",
            "Vuoi creare una copia di backup dei dati attuali prima del reset?\n\n"
            "Questo salverà tutti i documenti e il database in un archivio ZIP.",
            icon="question"
        )

        # Perform backup if requested
        backup_path = None
        if do_backup:
            try:
                from backup import backup_on_demand
                from config import DATA_DIR, DB_NAME, get_backup_dir

                self._set_status_message("Creazione backup in corso...")
                self.root.update()

                success, result = backup_on_demand(DATA_DIR, DB_NAME, get_backup_dir())
                if success:
                    backup_path = result
                    messagebox.showinfo(
                        "Backup completato",
                        f"Backup creato con successo:\n{backup_path}\n\n"
                        "Conserva questo file in un luogo sicuro."
                    )
                else:
                    if not messagebox.askyesno(
                        "Backup fallito",
                        f"Il backup non è riuscito: {result}\n\n"
                        "Vuoi procedere comunque con il reset?",
                        icon="warning"
                    ):
                        return
            except Exception as e:
                if not messagebox.askyesno(
                    "Errore backup",
                    f"Errore durante il backup: {str(e)}\n\n"
                    "Vuoi procedere comunque con il reset?",
                    icon="warning"
                ):
                    return

        # Final confirmation
        if not messagebox.askyesno(
            "Conferma reset finale",
            "Questa è l'ultima conferma.\n\n"
            "Tutti i dati verranno eliminati e l'applicazione verrà riavviata.\n\n"
            "Procedere con il reset?",
            icon="warning"
        ):
            return

        try:
            self._set_status_message("Reset in corso...")
            self.root.update()

            # Reset configuration
            from config_manager import save_config
            from config import DEFAULT_CONFIG

            # Save default config with wizard_completed = False
            reset_config = DEFAULT_CONFIG.copy()
            reset_config['wizard_completed'] = False
            save_config(reset_config)

            # Delete database
            from config import DB_NAME
            if os.path.exists(DB_NAME):
                try:
                    os.remove(DB_NAME)
                    logger.info(f"Database deleted: {DB_NAME}")
                except Exception as e:
                    logger.warning(f"Failed to delete database: {e}")

            # Delete data directory contents (but keep the directory structure)
            from config import DATA_DIR
            if os.path.exists(DATA_DIR):
                try:
                    # Remove documents but keep directory structure
                    docs_dir = os.path.join(DATA_DIR, "documents")
                    if os.path.exists(docs_dir):
                        import shutil
                        shutil.rmtree(docs_dir, ignore_errors=True)
                        logger.info(f"Documents directory cleared: {docs_dir}")

                    # Clear other data subdirectories as needed
                    for subdir in ["section_docs", "tools"]:
                        subpath = os.path.join(DATA_DIR, subdir)
                        if os.path.exists(subpath):
                            shutil.rmtree(subpath, ignore_errors=True)
                            logger.info(f"Data subdirectory cleared: {subpath}")

                except Exception as e:
                    logger.warning(f"Failed to clear data directory: {e}")

            # Show success message
            messagebox.showinfo(
                "Reset completato",
                "Reset ai dati di fabbrica completato con successo!\n\n"
                f"{'Backup salvato: ' + os.path.basename(backup_path) if backup_path else 'Nessun backup creato.'}\n\n"
                "L'applicazione verrà riavviata."
            )

            # Restart application
            self.root.quit()
            # Note: The main.py should detect wizard_completed=False and show the wizard

        except Exception as e:
            logger.error(f"Reset failed: {e}")
            messagebox.showerror(
                "Errore reset",
                f"Si è verificato un errore durante il reset:\n{str(e)}\n\n"
                "Alcuni dati potrebbero non essere stati eliminati correttamente."
            )

    def _relink_document_paths(self):
        """Prompt user for a new documents root and attempt to relink missing files."""
        new_root = filedialog.askdirectory(parent=self.root, title="Seleziona nuova cartella documenti")
        if not new_root:
            return
        try:
            from documents_manager import relink_missing_documents

            updated, unresolved, details = relink_missing_documents(new_root)
            message = [f"Percorsi aggiornati: {updated}"]
            if unresolved:
                message.append(f"Documenti ancora mancanti: {unresolved}")
                if details:
                    preview = "\n".join(details[:8])
                    if unresolved > 8:
                        preview += "\n..."
                    message.append("\nDettagli:\n" + preview)
                messagebox.showwarning("Riallinea percorsi", "\n".join(message))
            else:
                messagebox.showinfo("Riallinea percorsi", "\n".join(message))

            # Refresh documents views so changes are visible immediately (no restart needed).
            try:
                panel_docs = getattr(self, "panel_docs", None)
                if panel_docs is not None:
                    panel_docs.refresh()
            except Exception:
                pass

            try:
                section_docs_panel = getattr(self, "section_docs_panel", None)
                if section_docs_panel is not None:
                    section_docs_panel.refresh()
            except Exception:
                pass

            try:
                member_id = None
                selection = getattr(self, "tv_soci", None)
                if selection is not None:
                    selected = selection.selection()
                    if len(selected) == 1:
                        member_id = self._get_member_id_from_item(selected[0])
                self._refresh_docs_preview(member_id)
            except Exception:
                pass
        except Exception as exc:
            logger.error("Errore riallineando i percorsi: %s", exc)
            messagebox.showerror("Riallinea percorsi", f"Errore durante l'operazione:\n{exc}")
    
    def _build_ui(self):
        """Build the main user interface."""
        # Create menu bar
        self._build_menu()
        
        # Create main content area
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create notebook (tabs) with custom style for delimiters
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)
        
    # Create tabs
    # ordine tab: soci, Consiglio Direttivo, Ponti, Magazzino, Calendario, Documenti, Statistiche (spostare sotto menu strumenti?)
        self._create_soci_tab()
        self._add_tab_delimiter()
        self._create_consiglio_direttivo_tab()
        self._add_tab_delimiter()
        self._create_ponti_tab()
        self._add_tab_delimiter()
        self._create_magazzino_tab()
        self._add_tab_delimiter()
        self._create_calendar_tab()
        self._add_tab_delimiter()
        self._create_docs_tab()
        self._add_tab_delimiter()
        self._create_section_tab()
        self._add_tab_delimiter()
        self._create_statistics_tab()
        
        # Create status bar
        self._create_statusbar()
        if self.startup_issues:
            self.root.after(300, self._show_startup_issues)

    @staticmethod
    def _normalize_tab_label(label: str) -> str:
        """Normalize a tab label by removing leading emoji/pictograms.

        This allows changing visible labels (e.g. adding emojis) without breaking
        code that navigates tabs by text.
        """
        text = (label or "").strip()
        # Strip leading non-alphanumeric symbols (emoji/pictograms) plus spaces.
        while text and not text[0].isalnum():
            text = text[1:].lstrip()
        return text

    @staticmethod
    def _select_notebook_tab_by_text(notebook: ttk.Notebook, label: str) -> bool:
        """Select a notebook tab by its visible label."""
        try:
            wanted_raw = (label or "").strip()
            if not wanted_raw:
                return False
            wanted_raw_cf = wanted_raw.casefold()
            wanted_norm_cf = App._normalize_tab_label(wanted_raw).casefold()
            for tab_id in notebook.tabs():
                try:
                    tab_text = (notebook.tab(tab_id, "text") or "").strip()
                    tab_text_cf = tab_text.casefold()
                    tab_norm_cf = App._normalize_tab_label(tab_text).casefold()
                    if tab_text_cf == wanted_raw_cf or tab_norm_cf == wanted_norm_cf:
                        notebook.select(tab_id)
                        return True
                except Exception:
                    continue
        except Exception:
            return False
        return False
    
    def _build_menu(self):
        """Build the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="📂 Apri...", command=self._not_implemented)
        file_menu.add_command(label="💾 Salva", accelerator="Ctrl+S", command=self._save_if_editing)
        file_menu.add_separator()
        file_menu.add_command(label="🚪 Esci", accelerator="Ctrl+Q", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Modifica", menu=edit_menu)
        edit_menu.add_command(label="➕  Nuovo socio", accelerator="Ctrl+N", command=self._add_member)
        edit_menu.add_command(label="✏️  Modifica socio", command=self._edit_member)
        edit_menu.add_command(label="🗑️  Elimina socio", accelerator="Ctrl+Del", command=self._delete_member)
        edit_menu.add_separator()
        edit_menu.add_command(label="🔎 Cerca...", accelerator="Ctrl+F", command=self._focus_search)
        edit_menu.add_command(label="🔄 Aggiorna lista", accelerator="F5", command=self._refresh_member_list)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Strumenti", menu=tools_menu)
        tools_menu.add_command(label="📥 Importa dati CSV", command=self._show_import_wizard)
        tools_menu.add_command(label="📤 Esporta dati CSV", accelerator="Ctrl+E", command=self._show_export_dialog)
        tools_menu.add_command(label="🧩 Ricerca duplicati...", accelerator="Ctrl+M", command=self._show_duplicates_dialog)
        tools_menu.add_command(label="📄 Importa documenti...", command=self._import_documents_wizard)
        tools_menu.add_separator()
        tools_menu.add_command(label="🧾 Modifica campi comuni...", command=self._show_batch_edit_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="🔁 Aggiorna stato soci...", command=self._show_update_status_wizard)
        tools_menu.add_separator()
        tools_menu.add_command(label="🧩 Gestione template...", command=self._show_templates_dialog)
        tools_menu.add_command(label="✉️ Email...", command=self._open_email_wizard)
        tools_menu.add_separator()
        tools_menu.add_command(label="🏷️ Legenda codici quote...", command=self._show_quota_legend)
        tools_menu.add_separator()
        tools_menu.add_command(label="⚙️ Preferenze...", command=self._show_preferences_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="🏠 Configurazione sezione...", command=self._show_section_config_dialog)
        tools_menu.add_command(label="🧙‍♂️ Configurazione guidata (Admin)...", command=self._show_admin_wizard)
        tools_menu.add_command(label="🛡️ Backup database...", accelerator="Ctrl+B", command=self._manual_backup)
        tools_menu.add_command(label="🔗 Riallinea percorsi documenti...", command=self._relink_document_paths)
        tools_menu.add_command(label="🧪 Verifica integrità DB...", command=self._not_implemented)
        tools_menu.add_command(label="📜 Log eventi...", command=self._show_event_log)
        tools_menu.add_separator()
        tools_menu.add_command(label="🔄 Reset ai dati di fabbrica...", command=self._reset_to_factory)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Aiuto", menu=help_menu)
        help_menu.add_command(label="📖 Guida rapida", command=self._open_help)
        help_menu.add_command(label="⌨️ Scorciatoie da tastiera", command=self._show_shortcuts_help)
        help_menu.add_separator()
        help_menu.add_command(label="ℹ️ Informazioni", command=self._show_about)

    def _open_help(self):
        """Apri il file HELP.md con il visualizzatore di default."""
        help_path = Path(__file__).resolve().parents[2] / "HELP.md"
        if not help_path.exists():
            messagebox.showerror("Aiuto", f"File HELP non trovato:\n{help_path}")
            return
        try:
            from utils import open_path

            def _on_open_help_error(msg: str) -> None:
                messagebox.showerror("Aiuto", msg)

            open_path(str(help_path), on_error=_on_open_help_error)
        except Exception as exc:
            logger.error("Impossibile aprire l'help: %s", exc)
            messagebox.showerror("Aiuto", f"Impossibile aprire l'help:\n{exc}")

    def _get_selected_member_for_import(self) -> tuple[int | None, str]:
        """Return (member_id, display_name) for the currently selected socio."""
        try:
            selection = self.tv_soci.selection() if hasattr(self, "tv_soci") else ()
            if not selection:
                return (None, "")
            member_id = self._get_member_id_from_item(selection[0])
            if member_id is None:
                return (None, "")

            try:
                from database import fetch_one

                member = fetch_one(
                    "SELECT id, nominativo, nome, cognome FROM soci WHERE id = ?",
                    (member_id,),
                )
                member_dict = dict(member) if member else {"id": member_id}
                return (int(member_id), self._format_member_display_name(member_dict))
            except Exception:
                return (int(member_id), f"Socio #{member_id}")
        except Exception:
            return (None, "")

    def _import_documents_wizard(self):
        """Open the 'Import documenti' wizard (Socio/Sezione + categoria)."""
        try:
            from .import_documents_wizard import ImportDocumentsWizard

            dlg = ImportDocumentsWizard(self.root, get_selected_member=self._get_selected_member_for_import)
            self.root.wait_window(dlg)

            # Best-effort refresh: section docs view might be visible.
            if dlg.result and dlg.result.get("target") == "sezione":
                panel = getattr(self, "section_docs_panel", None)
                if panel is not None and hasattr(panel, "refresh"):
                    try:
                        panel.refresh()
                    except Exception:
                        pass
        except Exception as exc:
            logger.error("Errore apertura wizard import documenti: %s", exc)
            messagebox.showerror("Import documenti", f"Errore:\n{exc}")

    def _show_admin_wizard(self):
        """Lancia il wizard di configurazione in modalità ADMIN, precompilando i dati dalla configurazione attuale."""
        try:
            from tkinter_wizard import run_wizard
        except ImportError:
            messagebox.showerror("Configurazione guidata", "Modulo wizard non trovato.")
            return

        def on_complete(state):
            # Reload configuration
            from config_manager import load_config
            self.cfg = load_config()
            self._update_title()
            messagebox.showinfo("Configurazione guidata", "Configurazione aggiornata con successo.", parent=self.root)

        run_wizard(mode="ADMIN", parent=self.root, on_complete=on_complete)
    
    def _create_soci_tab(self):
        """Create the Soci (members) tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="👥 Soci")

        # Main toolbar
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(toolbar, text="Nuovo", command=self._add_member).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Modifica", command=self._edit_member).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Elimina", command=self._delete_member).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="🗑️ Cestino", command=self._show_trash).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Modifica campi", command=self._show_batch_edit_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT)
        ttk.Label(toolbar, text="  |  Cerca:").pack(side=tk.LEFT, padx=2)

        # Search field
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search_changed)
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Reset", command=self._reset_search).pack(side=tk.LEFT, padx=2)

        # Filter toolbar
        filter_toolbar = ttk.Frame(tab)
        filter_toolbar.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(filter_toolbar, text="Filtri:", font="AppNormal").pack(side=tk.LEFT, padx=5)

        # Status filter
        ttk.Label(filter_toolbar, text="  |  Stato:").pack(side=tk.LEFT, padx=5)
        self.status_filter_var = tk.StringVar(value="tutti")
        ttk.Radiobutton(filter_toolbar, text="Tutti", variable=self.status_filter_var, value="tutti", command=self._apply_filters).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(filter_toolbar, text="Attivi", variable=self.status_filter_var, value="active", command=self._apply_filters).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(filter_toolbar, text="Inattivi", variable=self.status_filter_var, value="inactive", command=self._apply_filters).pack(side=tk.LEFT, padx=2)
        
        # Missing data filter
        ttk.Label(filter_toolbar, text="  |  Dati:").pack(side=tk.LEFT, padx=5)
        self.missing_data_filter_var = tk.StringVar(value="tutti")
        ttk.Radiobutton(filter_toolbar, text="Tutti", variable=self.missing_data_filter_var, value="tutti", command=self._apply_filters).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(filter_toolbar, text="⚠ Dati mancanti", variable=self.missing_data_filter_var, value="missing", command=self._apply_filters).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(filter_toolbar, text="✓ Completi", variable=self.missing_data_filter_var, value="complete", command=self._apply_filters).pack(side=tk.LEFT, padx=2)

        # Nuova disposizione: tabella sopra, form + riepilogo sotto
        main_content = ttk.Frame(tab)
        main_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tabella soci (parte superiore - altezza fissa per 8 righe)
        table_container = ttk.Frame(main_content)
        table_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        table_container.columnconfigure(0, weight=1)
        table_container.rowconfigure(0, weight=1)

        scrollbar_y = ttk.Scrollbar(table_container, orient="vertical")
        scrollbar_x = ttk.Scrollbar(table_container, orient="horizontal")

        self.tv_soci = ttk.Treeview(
            table_container,
            columns=self.COLONNE_DISPLAY,
            show="headings",
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
            height=8,
            selectmode="extended",
        )

        scrollbar_y.config(command=self.tv_soci.yview)
        scrollbar_x.config(command=self.tv_soci.xview)

        self.tv_soci.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        # Bind doppio click per popolare il form
        self.tv_soci.bind("<Double-1>", self._on_member_double_click)
        self.tv_soci.bind("<<TreeviewSelect>>", self._on_tree_selection_changed)
        column_widths = {
            "⚠": 40,
            "matricola": 90,
            "nominativo": 160,
            "nome": 120,
            "cognome": 140,
            "socio": 80,
            "attivo": 70,
            "voto": 70,
            "q0": 55,
            "q1": 55,
            "q2": 55,
            "familiare": 80,
            "email": 180,
            "citta": 120,
            "provincia": 80,
        }
        center_columns = {"⚠", "attivo", "voto", "q0", "q1", "q2"}
        for col in self.COLONNE_DISPLAY:
            self.tv_soci.heading(col, text=self.HEADER_TITLES.get(col, col))
            width = column_widths.get(col, 100)
            anchor = "center" if col in center_columns else "w"
            self.tv_soci.column(col, width=width, anchor=anchor)
        # layout gestito con grid (vedi sopra)
        # Enable click-to-sort on the main members treeview
        try:
            self._make_treeview_sortable(self.tv_soci, list(self.VISIBLE_COLUMNS))
        except Exception:
            pass
        # Configure simple visual tags for active/inactive rows and missing privacy
        try:
            # light green for active, light red for inactive
            self.tv_soci.tag_configure('active', background='#e9f7ef')
            self.tv_soci.tag_configure('inactive', background='#f8d7da')
            # rows with missing critical data (matricola, email, telefono, indirizzo)
            self.tv_soci.tag_configure('missing_data', background='#fff3cd', foreground='#856404')
        except Exception:
            pass

        # Area inferiore: form e note senza spazio vuoto aggiuntivo
        bottom_area = ttk.Frame(main_content)
        bottom_area.pack(fill=tk.X, expand=False, padx=5, pady=(0, 5))

        # Form socio
        form_container = ttk.Frame(bottom_area)
        form_container.pack(fill=tk.X, expand=False, padx=0, pady=(0, 3))
        from .forms import MemberForm
        self.form_member = MemberForm(form_container, cfg=self.cfg)
        self.form_member.pack(fill=tk.X, expand=False)

        # All'avvio il form è vuoto
        self.form_member.clear()

        # Riepilogo socio compatto removed for cleaner data entry interface

        # Form buttons: align to the right of the Note textbox for a shorter layout
        note_action_host = None
        try:
            note_action_host = self.form_member.get_note_action_frame()
        except AttributeError:
            note_action_host = None

        if note_action_host is not None:
            ttk.Button(note_action_host, text="Salva", command=self._save_member).pack(side=tk.RIGHT, padx=2)
            ttk.Button(note_action_host, text="Annulla", command=self._cancel_edit).pack(side=tk.RIGHT, padx=2)
        else:
            # Fallback: keep buttons under the form if the frame is unavailable
            button_frame = ttk.Frame(main_content)
            button_frame.pack(fill=tk.X, padx=5, pady=5)
            ttk.Button(button_frame, text="Salva", command=self._save_member).pack(side=tk.RIGHT, padx=2)
            ttk.Button(button_frame, text="Annulla", command=self._cancel_edit).pack(side=tk.RIGHT, padx=2)

        # Azioni legate al socio selezionato (documenti), visibili nel tab Soci.
        socio_actions = ttk.Frame(bottom_area)
        socio_actions.pack(fill=tk.X, expand=False, padx=0, pady=(0, 5))
        ttk.Label(socio_actions, text="Azioni socio selezionato:").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(socio_actions, text="Aggiungi documento", command=self._socio_add_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(socio_actions, text="Carica privacy", command=self._socio_upload_privacy).pack(side=tk.LEFT, padx=2)
        ttk.Button(socio_actions, text="Apri cartella socio", command=self._socio_open_member_folder).pack(side=tk.LEFT, padx=2)

        # Inline document preview placed right below the Note field
        docs_preview_frame = ttk.LabelFrame(bottom_area, text="Documenti del socio")
        docs_preview_frame.pack(fill=tk.X, expand=False, padx=0, pady=(0, 5))

        self.docs_preview_info_var = tk.StringVar(value="Seleziona un socio per visualizzare i documenti.")
        ttk.Label(
            docs_preview_frame,
            textvariable=self.docs_preview_info_var,
            foreground="gray40"
        ).pack(anchor="w", padx=5, pady=(4, 0))

        docs_tree_frame = ttk.Frame(docs_preview_frame)
        docs_tree_frame.pack(fill=tk.X, expand=False, padx=5, pady=5)

        docs_scrollbar = ttk.Scrollbar(docs_tree_frame, orient="vertical")
        docs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        columns = ("id", "descrizione", "categoria", "tipo", "nome", "data", "info")
        self.docs_preview_tree = ttk.Treeview(
            docs_tree_frame,
            columns=columns,
            show="headings",
            height=4,
            selectmode="browse",
            yscrollcommand=docs_scrollbar.set,
        )
        docs_scrollbar.config(command=self.docs_preview_tree.yview)

        heading_config: dict[str, tuple[str, int, TreeviewAnchor]] = {
            "id": ("ID", 45, "center"),
            "descrizione": ("Descrizione", 220, "w"),
            "categoria": ("Tipo", 140, "w"),
            "tipo": ("Tipo doc", 90, "center"),
            "nome": ("Nome file", 220, "w"),
            "data": ("Data", 110, "center"),
            "info": ("Informazioni file", 180, "w"),
        }
        for col in columns:
            title, width, anchor = heading_config[col]
            self.docs_preview_tree.heading(col, text=title)
            self.docs_preview_tree.column(col, width=width, anchor=anchor)

        # Soft color cue for missing files in the preview.
        try:
            self.docs_preview_tree.tag_configure("missing", foreground="#b00020")
        except Exception:
            pass

        # Row coloring by document category/type.
        self._docs_preview_category_tags = CategoryTagStyler(
            self.docs_preview_tree,
            default_label="Altro",
            palette=MEMBER_CATEGORY_PALETTE,
            tag_prefix="docprev::",
        )

        self.docs_preview_tree.pack(fill=tk.X, expand=False)
    
    def _create_docs_tab(self):
        """Create the Documents tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📄 Documenti")
        
        from .panels import DocumentPanel, SectionDocumentPanel

        self.docs_notebook = ttk.Notebook(tab)
        self.docs_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.section_docs_panel = SectionDocumentPanel(self.docs_notebook)
        self.docs_notebook.add(self.section_docs_panel, text="🏠 Doc sezione")

        self.panel_docs = DocumentPanel(self.docs_notebook, show_all_documents=True)
        self.docs_notebook.add(self.panel_docs, text="👥 Doc soci")

    def _create_magazzino_tab(self):
        """Create the inventory (magazzino) tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📦 Magazzino")
        self.magazzino_panel = MagazzinoPanel(tab)
        self.magazzino_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_ponti_tab(self):
        """Create the Ponti (repeaters) management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📡 Ponti")
        self.ponti_panel = PontiPanel(tab)
        self.ponti_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _on_notebook_tab_changed(self, _event):
        """Refresh expensive tabs when they become visible."""
        try:
            tab_id = self.notebook.select()
        except Exception:
            return
        tab_text = (self.notebook.tab(tab_id, "text") or "").strip()
        tab_key = self._normalize_tab_label(tab_text)
        if tab_key == "Consiglio Direttivo":
            try:
                self._refresh_cd_riunioni()
            except Exception:
                pass
        elif tab_key == "Statistiche" and hasattr(self, "stats_panel"):
            self.stats_panel.refresh()

    def _make_treeview_sortable(self, tv, cols):
        """Enable click-to-sort on the given Treeview for the provided columns."""
        if not hasattr(tv, '_sort_state'):
            tv._sort_state = {}

        def _on_heading(col):
            prev_rev = tv._sort_state.get(col)
            new_rev = False if prev_rev is None else not prev_rev  # first click asc, second desc
            self._treeview_sort_column(tv, col, new_rev)
            tv._sort_state[col] = new_rev
            # track last sorted
            tv._last_sorted = (col, new_rev)

        for c in cols:
            try:
                tv.heading(c, command=lambda _c=c: _on_heading(_c))
            except Exception:
                pass

    def _create_consiglio_direttivo_tab(self):
        """Create the Consiglio Direttivo area (single consolidated view)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🏛️ Consiglio Direttivo")

        # CD actions toolbar (single access point for Riunioni CD)
        cd_toolbar = ttk.Frame(tab)
        cd_toolbar.pack(fill=tk.X, padx=5, pady=(5, 0))
        ttk.Button(cd_toolbar, text="Esporta libro verbali", command=self._export_libro_verbali).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(cd_toolbar, text="Esporta libro delibere", command=self._export_libro_delibere).pack(
            side=tk.LEFT, padx=2
        )

        # --- Nuovo tab: Libro Delibere (tabellare + esportazione PDF/DOCX) ---
        self.cd_notebook = ttk.Notebook(tab)
        self.cd_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Vista riunioni/delibere classica
        cd_main_frame = ttk.Frame(self.cd_notebook)
        self.cd_notebook.add(cd_main_frame, text="Riunioni")
        self._build_cd_riunioni_view(cd_main_frame)

        # Tab 2: Libro Delibere (tabellare per triennio)
        libro_frame = ttk.Frame(self.cd_notebook)
        self.cd_notebook.add(libro_frame, text="Libro Delibere (tabella)")
        self._build_libro_delibere_tab(libro_frame)
    def _build_libro_delibere_tab(self, parent):
        """Crea la tabella delle delibere raggruppate per triennio e pulsanti di esportazione."""
        from libro_delibere import group_delibere_by_triennio, get_all_delibere
        from tkinter import messagebox, filedialog
        import os

        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, padx=5, pady=(5, 0))
        ttk.Button(toolbar, text="Esporta DOCX", command=self._export_libro_delibere_docx).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Esporta PDF", command=self._export_libro_delibere_pdf).pack(side=tk.LEFT, padx=2)

        # Tabella principale
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tv_libro_delibere = ttk.Treeview(table_frame, columns=("triennio", "numero", "data", "oggetto", "esito", "favorevoli", "contrari", "astenuti", "verbale_rif"), show="headings")
        columns = [
            ("triennio", "Triennio", 90),
            ("numero", "Numero", 70),
            ("data", "Data", 90),
            ("oggetto", "Oggetto", 320),
            ("esito", "Esito", 80),
            ("favorevoli", "Fav.", 50),
            ("contrari", "Contr.", 50),
            ("astenuti", "Asten.", 50),
            ("verbale_rif", "Verbale Rif.", 120),
        ]
        for col, title, width in columns:
            self.tv_libro_delibere.heading(col, text=title)
            self.tv_libro_delibere.column(col, width=width, anchor="center" if col!="oggetto" else "w")
        self.tv_libro_delibere.pack(fill=tk.BOTH, expand=True)

        self._refresh_libro_delibere_table()

    def _refresh_libro_delibere_table(self):
        from libro_delibere import group_delibere_by_triennio, get_all_delibere
        tv = getattr(self, "tv_libro_delibere", None)
        if tv is None:
            return
        for item in tv.get_children():
            tv.delete(item)
        delibere = get_all_delibere()
        grouped = group_delibere_by_triennio(delibere)
        for triennio, items in sorted(grouped.items()):
            for d in items:
                tv.insert("", "end", values=(
                    triennio,
                    d.get("numero", ""),
                    d.get("data_votazione", ""),
                    d.get("oggetto", ""),
                    d.get("esito", ""),
                    d.get("favorevoli", ""),
                    d.get("contrari", ""),
                    d.get("astenuti", ""),
                    d.get("verbale_riferimento", ""),
                ))

    def _export_libro_delibere_docx(self):
        from tkinter import filedialog, messagebox
        from libro_delibere import export_libro_delibere_docx
        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Esporta libro delibere (DOCX)",
            initialfile="Libro_delibere.docx",
            defaultextension=".docx",
            filetypes=(("Word (.docx)", "*.docx"), ("Tutti i file", "*.*")),
        )
        if not file_path:
            return
        try:
            export_libro_delibere_docx(file_path)
            messagebox.showinfo("Libro delibere", "Libro delle delibere esportato:\n" + str(file_path))
        except Exception as exc:
            messagebox.showerror("Libro delibere", f"Errore durante l'esportazione DOCX:\n{exc}")

    def _export_libro_delibere_pdf(self):
        from tkinter import filedialog, messagebox
        from libro_delibere import export_libro_delibere_pdf
        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Esporta libro delibere (PDF)",
            initialfile="Libro_delibere.pdf",
            defaultextension=".pdf",
            filetypes=(("PDF (.pdf)", "*.pdf"), ("Tutti i file", "*.*")),
        )
        if not file_path:
            return
        try:
            export_libro_delibere_pdf(file_path)
            messagebox.showinfo("Libro delibere", "Libro delle delibere esportato:\n" + str(file_path))
        except Exception as exc:
            messagebox.showerror("Libro delibere", f"Errore durante l'esportazione PDF:\n{exc}")

    def _export_libro_verbali(self):
        """Export the 'Libro verbali' Excel file from cd_riunioni."""
        from tkinter import filedialog, messagebox

        default_name = "Libro_verbali.xlsx"
        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Esporta libro verbali",
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=(("Excel (.xlsx)", "*.xlsx"), ("Tutti i file", "*.*")),
        )
        if not file_path:
            return

        try:
            from cd_reports import export_libro_verbali_xlsx

            count, warnings = export_libro_verbali_xlsx(file_path)
            lines = [f"Righe esportate: {count}", f"File: {file_path}"]
            if warnings:
                lines.append("")
                lines.append("Avvisi:")
                lines.extend(warnings)
            messagebox.showinfo("Libro verbali", "\n".join(lines))
        except Exception as exc:
            messagebox.showerror("Libro verbali", f"Errore durante l'esportazione:\n{exc}")

    def _export_libro_delibere(self):
        """Export the 'Libro delibere' (Word or Excel) from cd_delibere."""
        from tkinter import filedialog, messagebox

        default_name = "Libro_delibere.docx"
        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Esporta libro delibere",
            initialfile=default_name,
            defaultextension=".docx",
            filetypes=(
                ("Word (.docx)", "*.docx"),
                ("Excel (.xlsx)", "*.xlsx"),
                ("Tutti i file", "*.*"),
            ),
        )
        if not file_path:
            return

        try:
            suffix = (str(file_path).lower().rsplit(".", 1)[-1] if "." in str(file_path) else "").strip()
            if suffix == "xlsx":
                from cd_reports import export_libro_delibere_xlsx

                count, warnings = export_libro_delibere_xlsx(file_path)
            else:
                # Default: DOCX template-based export (best-effort).
                template = r"e:\ARI-BG - 2023-2025\CD\Delibere\ARIBG_Libro Delibere 2023.docx"
                from cd_reports import export_libro_delibere_docx

                count, warnings = export_libro_delibere_docx(file_path, template_path=template)

            lines = [f"Righe esportate: {count}", f"File: {file_path}"]
            if warnings:
                lines.append("")
                lines.append("Avvisi:")
                lines.extend(warnings)
            messagebox.showinfo("Libro delibere", "\n".join(lines))
        except Exception as exc:
            messagebox.showerror("Libro delibere", f"Errore durante l'esportazione:\n{exc}")

    def _build_cd_riunioni_view(self, parent: ttk.Frame):
        """Build the single CD view (riunioni overview + delibere list) inside the CD tab."""
        try:
            toolbar = ttk.Frame(parent)
            toolbar.pack(fill=tk.X, padx=5, pady=5)
            ttk.Button(toolbar, text="Gestione Mandato/Composizione CD", command=self._open_cd_mandato_wizard).pack(side=tk.LEFT, padx=2)
            ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT)
            ttk.Button(toolbar, text="Nuova riunione", command=self._new_cd_meeting_from_tab).pack(side=tk.LEFT, padx=2)
            ttk.Button(toolbar, text="Modifica riunione", command=self._edit_cd_meeting_from_tab).pack(side=tk.LEFT, padx=2)
            ttk.Button(toolbar, text="Elimina riunione", command=self._delete_cd_meeting_from_tab).pack(side=tk.LEFT, padx=2)

            ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT)
            ttk.Button(toolbar, text="Nuova delibera", command=self._new_cd_delibera_from_overview).pack(side=tk.LEFT, padx=2)
            ttk.Button(toolbar, text="Modifica delibera", command=self._edit_cd_delibera_from_overview).pack(side=tk.LEFT, padx=2)
            ttk.Button(toolbar, text="Elimina delibera", command=self._delete_cd_delibera_from_overview).pack(side=tk.LEFT, padx=2)

            ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT)
            ttk.Button(toolbar, text="Apri verbale", command=self._open_cd_verbale_from_overview).pack(side=tk.LEFT, padx=2)
            ttk.Button(toolbar, text="Esporta verbale...", command=self._export_cd_verbale_from_overview).pack(side=tk.LEFT, padx=2)

            ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT)
            ttk.Button(toolbar, text="Delibere di questo verbale", command=self._show_delibere_of_selected_verbale).pack(side=tk.LEFT, padx=2)

            # PanedWindow
            paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
            paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # Add top and bottom frames to the paned window
            top = ttk.Frame(paned)
            bottom = ttk.Frame(paned)
            paned.add(top, weight=3)
            paned.add(bottom, weight=2)

            # Treeview delle riunioni (usa pack, non grid)
            try:
                scrollbar_h = ttk.Scrollbar(top, orient="horizontal")
                scrollbar_v = ttk.Scrollbar(top, orient="vertical")
                self.tv_cd_riunioni = ttk.Treeview(
                    top,
                    columns=("data", "titolo_riunione", "numero", "titolo_verbale", "mandato", "delibere"),
                    show="headings",
                    xscrollcommand=scrollbar_h.set,
                    yscrollcommand=scrollbar_v.set,
                )
                scrollbar_h.config(command=self.tv_cd_riunioni.xview)
                scrollbar_v.config(command=self.tv_cd_riunioni.yview)

                self.tv_cd_riunioni.column("data", width=110)
                self.tv_cd_riunioni.column("titolo_riunione", width=320)
                self.tv_cd_riunioni.column("numero", width=110)
                self.tv_cd_riunioni.column("titolo_verbale", width=420)
                self.tv_cd_riunioni.column("mandato", width=120)
                self.tv_cd_riunioni.column("delibere", width=220)

                self.tv_cd_riunioni.heading("data", text="Data")
                self.tv_cd_riunioni.heading("titolo_riunione", text="Titolo riunione")
                self.tv_cd_riunioni.heading("numero", text="Numero CD")
                self.tv_cd_riunioni.heading("titolo_verbale", text="Titolo verbale")
                self.tv_cd_riunioni.heading("mandato", text="Mandato")
                self.tv_cd_riunioni.heading("delibere", text="Delibere")

                self.tv_cd_riunioni.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
                scrollbar_v.pack(fill=tk.Y, side=tk.RIGHT)
                scrollbar_h.pack(fill=tk.X, side=tk.BOTTOM)

                try:
                    self._make_treeview_sortable(
                        self.tv_cd_riunioni,
                        ["data", "titolo_riunione", "numero", "titolo_verbale", "mandato", "delibere"],
                    )
                except Exception:
                    pass

                try:
                    self.tv_cd_riunioni.bind("<Double-1>", lambda _e: self._edit_cd_meeting_from_tab())
                except Exception:
                    pass

                try:
                    self.tv_cd_riunioni.bind("<<TreeviewSelect>>", lambda _e: self._refresh_cd_delibere_overview())
                except Exception:
                    pass
            except Exception as exc:
                ttk.Label(top, text=f"DEBUG: Treeview riunioni non creata: {exc}", foreground="red").pack()

            # Bottom: delibere list filtered by selected meeting (usa pack)
            bottom_toolbar = ttk.Frame(bottom)
            bottom_toolbar.pack(fill=tk.X, padx=0, pady=(0, 4))
            self._lbl_cd_delibere_badge = ttk.Label(bottom_toolbar, text="Delibere: (seleziona una riunione)")
            self._lbl_cd_delibere_badge.pack(side=tk.LEFT)

            dframe = ttk.Frame(bottom)
            dframe.pack(fill=tk.BOTH, expand=True)

            dscroll_h = ttk.Scrollbar(dframe, orient="horizontal")
            dscroll_v = ttk.Scrollbar(dframe, orient="vertical")

            self.tv_cd_delibere_overview = ttk.Treeview(
                dframe,
                columns=("id", "numero", "oggetto", "esito", "data"),
                show="headings",
                xscrollcommand=dscroll_h.set,
                yscrollcommand=dscroll_v.set,
            )
            dscroll_h.config(command=self.tv_cd_delibere_overview.xview)
            dscroll_v.config(command=self.tv_cd_delibere_overview.yview)

            self.tv_cd_delibere_overview.column("id", width=50)
            self.tv_cd_delibere_overview.column("numero", width=90)
            self.tv_cd_delibere_overview.column("oggetto", width=520)
            self.tv_cd_delibere_overview.column("esito", width=120)
            self.tv_cd_delibere_overview.column("data", width=110)

            self.tv_cd_delibere_overview.heading("id", text="ID")
            self.tv_cd_delibere_overview.heading("numero", text="Numero")
            self.tv_cd_delibere_overview.heading("oggetto", text="Oggetto")
            self.tv_cd_delibere_overview.heading("esito", text="Esito")
            self.tv_cd_delibere_overview.heading("data", text="Data votazione")

            try:
                self.tv_cd_delibere_overview.tag_configure("esito_ok", background="#e9f7ef")
                self.tv_cd_delibere_overview.tag_configure("esito_ko", background="#f8d7da")
                self.tv_cd_delibere_overview.tag_configure("esito_pending", background="#fff3cd", foreground="#856404")
            except Exception:
                pass

            self.tv_cd_delibere_overview.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
            dscroll_v.pack(fill=tk.Y, side=tk.RIGHT)
            dscroll_h.pack(fill=tk.X, side=tk.BOTTOM)

            dframe.columnconfigure(0, weight=1)
            dframe.rowconfigure(0, weight=1)

            try:
                self._make_treeview_sortable(self.tv_cd_delibere_overview, ["id", "numero", "oggetto", "esito", "data"])
            except Exception:
                pass
        except Exception as exc:
            logging.error(f"ERRORE in _build_cd_riunioni_view: {exc}")
            raise
    def _show_delibere_of_selected_verbale(self):
        """Mostra tutte le delibere collegate al verbale selezionato nella tabella riunioni."""
        from tkinter import messagebox, Toplevel
        from cd_delibere import get_all_delibere
        from cd_verbali import get_all_verbali
        sel_meeting_id = self._selected_cd_meeting_id_from_overview()
        if sel_meeting_id is None:
            messagebox.showwarning("Delibere", "Seleziona una riunione con verbale.")
            return
        # Recupera il verbale associato alla riunione
        try:
            from cd_verbali import get_all_verbali
            verbali = get_all_verbali(sel_meeting_id)
            if not verbali:
                messagebox.showinfo("Delibere", "Nessun verbale associato alla riunione selezionata.")
                return
            verbale_id = verbali[0].get('id')
        except Exception:
            messagebox.showerror("Delibere", "Errore nel recupero del verbale.")
            return
        # Recupera tutte le delibere che hanno quel verbale_id (diretto o ereditato)
        all_delibere = get_all_delibere()
        filtered = [d for d in all_delibere if (d.get('verbale_id') == verbale_id)]
        if not filtered:
            messagebox.showinfo("Delibere", "Nessuna delibera collegata a questo verbale.")
            return
        # Mostra in una finestra
        win = Toplevel(self.root)
        win.title(f"Delibere collegate al verbale ID {verbale_id}")
        win.geometry("900x400")
        frame = ttk.Frame(win)


        self._refresh_cd_riunioni()

    def _refresh_cd_riunioni(self):
        tv = getattr(self, "tv_cd_riunioni", None)
        if tv is None:
            return
        try:
            from cd_meetings import get_all_meetings
            meetings = get_all_meetings() or []
            tv.delete(*tv.get_children())
            for m in meetings:
                tv.insert(
                    "",
                    tk.END,
                    iid=str(m.get("id")),
                    values=(
                        m.get("data", ""),
                        m.get("titolo", ""),
                        m.get("numero_cd", ""),
                        "",  # Titolo verbale (da implementare se serve)
                        m.get("mandato_id", ""),
                        "",  # Delibere (da implementare se serve)
                    ),
                )
        except Exception as exc:
            import traceback
            from tkinter import messagebox
            logger.error(f"Errore caricamento riunioni CD: {exc}\n{traceback.format_exc()}")
            messagebox.showerror("Riunioni CD", f"Errore caricamento riunioni:\n{exc}")
        try:
            self._refresh_cd_delibere_overview()
        except Exception as exc:
            import traceback
            from tkinter import messagebox
            logger.error(f"Errore refresh delibere overview: {exc}\n{traceback.format_exc()}")
            messagebox.showerror("Delibere CD", f"Errore refresh delibere overview:\n{exc}")

    def _selected_cd_meeting_id_from_overview(self) -> int | None:
        tv = getattr(self, "tv_cd_riunioni", None)
        if tv is None:
            return None
        sel = tv.selection()
        if not sel:
            return None
        try:
            return int(str(sel[0]))
        except Exception:
            return None

    def _refresh_cd_delibere_overview(self):
        tv = getattr(self, "tv_cd_delibere_overview", None)
        if tv is None:
            return
        try:
            meeting_id = self._selected_cd_meeting_id_from_overview()
            for item in tv.get_children():
                tv.delete(item)
            lbl = getattr(self, "_lbl_cd_delibere_badge", None)
            if meeting_id is None:
                if lbl is not None:
                    lbl.config(text="Delibere: (seleziona una riunione)")
                return
            from cd_delibere import get_all_delibere
            delibere = get_all_delibere(meeting_id=meeting_id) or []
            def _esito_tag(esito_value: object) -> tuple[str, ...]:
                s = str(esito_value or "").strip().lower()
                if not s:
                    return ("esito_pending",)
                ok_words = ("approv", "favorev", "ok", "si", "sì")
                ko_words = ("resp", "boc", "no", "contr")
                if any(w in s for w in ok_words):
                    return ("esito_ok",)
                if any(w in s for w in ko_words):
                    return ("esito_ko",)
                if "rinv" in s or "sosp" in s or "att" in s:
                    return ("esito_pending",)
                return ()
            for d in delibere:
                esito = d.get("esito", "")
                tv.insert(
                    "",
                    tk.END,
                    iid=str(d.get("id")),
                    values=(
                        d.get("id", ""),
                        d.get("numero", ""),
                        d.get("oggetto", ""),
                        esito,
                        d.get("data_votazione", ""),
                    ),
                    tags=_esito_tag(esito),
                )
            if lbl is not None:
                lbl.config(text=f"Delibere: {len(delibere)}")
        except Exception as exc:
            import traceback
            from tkinter import messagebox
            logger.error(f"Errore caricamento delibere CD: {exc}\n{traceback.format_exc()}")
            messagebox.showerror("Delibere CD", f"Errore caricamento delibere:\n{exc}")

    def _new_cd_delibera_from_overview(self):
        from tkinter import messagebox

        meeting_id = self._selected_cd_meeting_id_from_overview()
        if meeting_id is None:
            messagebox.showwarning("Delibere", "Selezionare prima una riunione")
            return
        from cd_delibere_dialog import DeliberaDialog

        DeliberaDialog(self.root, meeting_id=meeting_id)
        try:
            self._refresh_cd_delibere_overview()
        except Exception:
            pass
        try:
            self._refresh_cd_riunioni()
        except Exception:
            pass

    def _edit_cd_delibera_from_overview(self):
        from tkinter import messagebox

        tv = getattr(self, "tv_cd_delibere_overview", None)
        if tv is None:
            return
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("Delibere", "Selezionare una delibera da modificare")
            return

        delibera_id = None
        meeting_id = None
        try:
            meeting_id = self._selected_cd_meeting_id_from_overview()
        except Exception:
            meeting_id = None
        try:
            item = tv.item(sel[0])
            values = item.get("values") or []
            logger.info(
                "CD delibere edit: selection=%r iid=%r values=%r meeting_id=%r",
                sel,
                sel[0] if sel else None,
                values,
                meeting_id,
            )
            if values:
                delibera_id = int(str(values[0]))
        except Exception:
            delibera_id = None
        if delibera_id is None:
            try:
                delibera_id = int(str(sel[0]))
            except Exception:
                messagebox.showerror("Delibere", "Delibera non valida")
                return
        from cd_delibere_dialog import DeliberaDialog

        logger.info("CD delibere edit: resolved delibera_id=%r meeting_id=%r", delibera_id, meeting_id)
        DeliberaDialog(self.root, delibera_id=delibera_id, meeting_id=meeting_id)
        try:
            self._refresh_cd_delibere_overview()
        except Exception:
            pass
        try:
            self._refresh_cd_riunioni()
        except Exception:
            pass

    def _delete_cd_delibera_from_overview(self):
        from tkinter import messagebox

        tv = getattr(self, "tv_cd_delibere_overview", None)
        if tv is None:
            return
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("Delibere", "Selezionare una delibera da eliminare")
            return

        delibera_id = None
        meeting_id = None
        try:
            meeting_id = self._selected_cd_meeting_id_from_overview()
        except Exception:
            meeting_id = None
        try:
            item = tv.item(sel[0])
            values = item.get("values") or []
            logger.info(
                "CD delibere delete: selection=%r iid=%r values=%r meeting_id=%r",
                sel,
                sel[0] if sel else None,
                values,
                meeting_id,
            )
            if values:
                delibera_id = int(str(values[0]))
        except Exception:
            delibera_id = None
        if delibera_id is None:
            try:
                delibera_id = int(str(sel[0]))
            except Exception:
                messagebox.showerror("Delibere", "Delibera non valida")
                return

        logger.info("CD delibere delete: resolved delibera_id=%r meeting_id=%r", delibera_id, meeting_id)

        if not messagebox.askyesno("Conferma", "Eliminare la delibera selezionata?"):
            return
        from cd_delibere import delete_delibera

        if delete_delibera(delibera_id):
            try:
                self._refresh_cd_delibere_overview()
            except Exception:
                pass
            try:
                self._refresh_cd_riunioni()
            except Exception:
                pass
        else:
            messagebox.showerror("Errore", "Impossibile eliminare la delibera")

    def _open_cd_verbale_from_overview(self):
        from tkinter import messagebox

        meeting_id = self._selected_cd_meeting_id_from_overview()
        if meeting_id is None:
            messagebox.showwarning("Verbali", "Selezionare una riunione")
            return
        path = str(getattr(self, "_cd_overview_verbale_path_map", {}).get(str(meeting_id)) or "").strip()
        if not path:
            messagebox.showwarning("Verbali", "Nessun verbale collegato alla riunione selezionata")
            return
        from utils import open_path

        def _on_err(msg: str) -> None:
            messagebox.showerror("Verbali", msg)

        ok = open_path(path, on_error=_on_err)
        if not ok:
            try:
                self._refresh_cd_riunioni()
            except Exception:
                pass

    def _export_cd_verbale_from_overview(self):
        from tkinter import filedialog, messagebox

        meeting_id = self._selected_cd_meeting_id_from_overview()
        if meeting_id is None:
            messagebox.showwarning("Verbali", "Selezionare una riunione")
            return

        iid = str(meeting_id)
        abs_path = str(getattr(self, "_cd_overview_verbale_path_map", {}).get(iid) or "").strip()
        if not abs_path:
            messagebox.showwarning("Verbali", "Nessun verbale collegato alla riunione selezionata")
            return

        try:
            import os
            from pathlib import Path
            import shutil

            if not os.path.exists(abs_path):
                messagebox.showerror("Verbali", "File non trovato sul disco.")
                return

            tv = getattr(self, "tv_cd_riunioni", None)
            values = (tv.item(iid, "values") or ()) if tv is not None else ()
            data = str(values[0]) if len(values) > 0 else ""
            numero = str(values[2]) if len(values) > 2 else ""

            def _safe(s: str) -> str:
                s2 = (s or "").strip()
                for ch in '<>:\\"/|?*':
                    s2 = s2.replace(ch, "_")
                return s2

            numero_safe = _safe(numero) or "NA"
            data_safe = _safe(data) or "DATA"

            src = Path(abs_path)
            ext = (src.suffix or "").lower()
            if ext not in (".pdf", ".docx", ".doc"):
                ext = src.suffix or ""
            initial_name = f"Verbale_{numero_safe}_{data_safe}{ext}"

            if ext == ".pdf":
                filetypes = [("PDF", "*.pdf"), ("Tutti i file", "*.*")]
                defext = ".pdf"
            elif ext in (".docx", ".doc"):
                filetypes = [("Word", "*.docx *.doc"), ("Tutti i file", "*.*")]
                defext = ".docx" if ext == ".docx" else ".doc"
            else:
                filetypes = [("Tutti i file", "*.*")]
                defext = ext

            dest = filedialog.asksaveasfilename(
                title="Esporta verbale",
                initialfile=initial_name,
                defaultextension=defext,
                filetypes=filetypes,
            )
            if not dest:
                return

            shutil.copy2(abs_path, dest)
            messagebox.showinfo("Verbali", "Verbale esportato correttamente.")
        except Exception as exc:
            messagebox.showerror("Verbali", f"Errore durante l'esportazione:\n{exc}")

    def _new_cd_meeting_from_tab(self):
        from cd_meetings_dialog import MeetingDialog

        MeetingDialog(self.root)
        self._refresh_cd_riunioni()

    def _edit_cd_meeting_from_tab(self):
        from tkinter import messagebox

        tv = getattr(self, "tv_cd_riunioni", None)
        if tv is None:
            return
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("Riunioni CD", "Selezionare una riunione da modificare")
            return

        try:
            meeting_id = int(str(sel[0]))
        except Exception:
            messagebox.showwarning("Riunioni CD", "Riunione non valida")
            return

        from cd_meetings_dialog import MeetingDialog

        MeetingDialog(self.root, meeting_id=meeting_id)
        self._refresh_cd_riunioni()

    def _delete_cd_meeting_from_tab(self):
        from tkinter import messagebox

        tv = getattr(self, "tv_cd_riunioni", None)
        if tv is None:
            return
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("Riunioni CD", "Selezionare una riunione da eliminare")
            return

        try:
            meeting_id = int(str(sel[0]))
        except Exception:
            messagebox.showwarning("Riunioni CD", "Riunione non valida")
            return

        if not messagebox.askyesno("Conferma", "Eliminare la riunione selezionata?"):
            return

        delete_verbale = False
        try:
            from cd_meetings import get_meeting_by_id

            meeting = get_meeting_by_id(meeting_id)
            has_verbale = False
            if isinstance(meeting, dict):
                has_verbale = bool(
                    meeting.get("verbale_section_doc_id")
                    or str(meeting.get("verbale_path") or "").strip()
                )
            if not has_verbale:
                path = str(getattr(self, "_cd_overview_verbale_path_map", {}).get(str(meeting_id)) or "").strip()
                has_verbale = bool(path)

            if has_verbale:
                delete_verbale = bool(
                    messagebox.askyesno(
                        "Verbale",
                        "Vuoi eliminare anche il verbale collegato?\n\n"
                        "Se scegli Sì, verrà eliminato anche il documento collegato (e il file associato, se presente).",
                    )
                )
        except Exception:
            delete_verbale = False

        try:
            from cd_meetings import delete_meeting

            ok = bool(delete_meeting(meeting_id, delete_verbale=delete_verbale))
        except Exception as exc:
            logger.error("Errore eliminando riunione CD %s: %s", meeting_id, exc)
            ok = False

        if not ok:
            messagebox.showerror("Riunioni CD", "Impossibile eliminare la riunione.")
            return

        try:
            self._refresh_cd_riunioni()
        except Exception:
            pass
        try:
            self._refresh_cd_delibere_overview()
        except Exception:
            pass

        try:
            messagebox.showinfo("Riunioni CD", "Riunione eliminata.")
        except Exception:
            pass

    def _open_cd_verbale_meeting(self):
        tv = getattr(self, "tv_cd_verbali_docs", None)
        if tv is None:
            return
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("Verbali", "Selezionare un verbale/riunione")
            return
        try:
            meeting_id = int(str(sel[0]))
        except Exception:
            messagebox.showerror("Verbali", "Riunione non valida")
            return
        try:
            from cd_meetings_dialog import MeetingDialog

            MeetingDialog(self.root, meeting_id=meeting_id)
            self._refresh_cd_verbali_docs()
        except Exception as exc:
            messagebox.showerror("Verbali", f"Impossibile aprire la riunione:\n{exc}")

    def _pick_cd_meeting_id(self) -> int | None:
        """Pick a CD meeting (past or future) and return its ID."""

        try:
            from cd_meetings import get_all_meetings
        except Exception as exc:
            messagebox.showerror("Riunioni CD", f"Impossibile caricare le riunioni.\n\nDettagli: {exc}")
            return None

        try:
            meetings = get_all_meetings() or []
        except Exception as exc:
            messagebox.showerror("Riunioni CD", f"Errore caricamento riunioni.\n\nDettagli: {exc}")
            return None

        if not meetings:
            messagebox.showinfo("Riunioni CD", "Nessuna riunione disponibile.")
            return None

        dlg = tk.Toplevel(self.root)
        dlg.title("Seleziona riunione CD")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry("860x420")

        container = ttk.Frame(dlg, padding=8)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Seleziona una riunione (doppio click per scegliere):").pack(anchor="w")

        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

        columns = ("data", "numero", "titolo")
        tv = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)

        tv.heading("data", text="Data")
        tv.heading("numero", text="N. CD")
        tv.heading("titolo", text="Titolo")

        tv.column("data", width=110, anchor="center")
        tv.column("numero", width=80, anchor="center")
        tv.column("titolo", width=610, anchor="w")

        tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        category_tags = CategoryTagStyler(
            tv,
            default_label="Altro",
            palette=SECTION_CATEGORY_PALETTE,
            tag_prefix="cdverb::",
        )

        for m in meetings:
            mid = m.get("id")
            if mid is None:
                continue
            iid = str(mid)
            tv.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    str(m.get("data") or ""),
                    str(m.get("numero_cd") or ""),
                    str(m.get("titolo") or ""),
                ),
            )

        actions = ttk.Frame(container)
        actions.pack(fill=tk.X)

        result: dict[str, int | None] = {"id": None}

        def _choose_selected() -> None:
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Riunioni CD", "Seleziona una riunione.", parent=dlg)
                return
            try:
                result["id"] = int(str(sel[0]))
            except Exception:
                messagebox.showwarning("Riunioni CD", "Riunione non valida.", parent=dlg)
                return
            try:
                dlg.destroy()
            except Exception:
                pass

        tv.bind("<Double-1>", lambda _e: _choose_selected())

        ttk.Button(actions, text="Annulla", command=dlg.destroy).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Seleziona", command=_choose_selected).pack(side=tk.RIGHT, padx=(0, 8))

        self.root.wait_window(dlg)
        return result.get("id")

    def _link_cd_verbale_flow(self):
        """Single-entry flow: pick meeting (past/future) then choose source (file vs section-doc library)."""

        meeting_id = self._pick_cd_meeting_id()
        if not meeting_id:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Collega verbale")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        container = ttk.Frame(dlg, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Scegli la sorgente del verbale:").pack(anchor="w", pady=(0, 8))

        actions = ttk.Frame(container)
        actions.pack(fill=tk.X)

        def _from_file() -> None:
            try:
                dlg.destroy()
            except Exception:
                pass
            self._link_cd_verbale_to_meeting_from_file(meeting_id=meeting_id)

        def _from_library() -> None:
            try:
                dlg.destroy()
            except Exception:
                pass
            self._link_cd_verbale_to_meeting_from_docs(meeting_id=meeting_id)

        ttk.Button(actions, text="Da file...", command=_from_file, width=26).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Da libreria (section docs)...", command=_from_library, width=28).pack(side=tk.LEFT)

        ttk.Button(container, text="Annulla", command=dlg.destroy).pack(anchor="e", pady=(10, 0))

        self.root.wait_window(dlg)

    def _link_cd_verbale_to_meeting_from_file(self, *, meeting_id: int | None = None):
        """Attach a verbale to a meeting importing it from a file."""

        if not meeting_id:
            meeting_id = self._pick_cd_meeting_id()
        if not meeting_id:
            return

        file_path = filedialog.askopenfilename(
            title="Seleziona documento verbale",
            filetypes=[
                ("Documenti", "*.pdf *.doc *.docx"),
                ("PDF", "*.pdf"),
                ("Word", "*.doc *.docx"),
                ("Tutti i file", "*.*"),
            ],
        )
        if not file_path:
            return

        try:
            from section_documents import add_section_document
            from database import get_section_document_by_relative_path
            from cd_meetings import update_meeting

            dest_abs = add_section_document(file_path, "Verbali CD")
            row = get_section_document_by_relative_path(dest_abs)
            if not row or row.get("id") is None:
                messagebox.showerror("Verbali", "Impossibile registrare il documento nei documenti di sezione.")
                return
            ok = update_meeting(int(meeting_id), verbale_section_doc_id=int(row["id"]))
            if not ok:
                messagebox.showerror("Verbali", "Impossibile collegare il verbale alla riunione.")
                return
            self._refresh_cd_verbali_docs()
        except Exception as exc:
            messagebox.showerror("Verbali", f"Errore collegamento verbale:\n{exc}")

    def _link_cd_verbale_to_meeting_from_docs(self, *, meeting_id: int | None = None):
        """Attach a verbale to a meeting from existing section documents."""

        if not meeting_id:
            meeting_id = self._pick_cd_meeting_id()
        if not meeting_id:
            return

        import os

        try:
            from section_documents import list_cd_verbali_documents
        except Exception as exc:
            messagebox.showerror(
                "Verbali",
                f"Impossibile caricare l'elenco dei documenti importati.\n\nDettagli: {exc}",
            )
            return

        try:
            all_docs = list_cd_verbali_documents(include_missing=False)
        except Exception as exc:
            messagebox.showerror(
                "Verbali",
                f"Errore nel caricamento dei documenti importati.\n\nDettagli: {exc}",
            )
            return

        docs: list[dict] = []
        for d in all_docs or []:
            abs_path = str(d.get("absolute_path") or "").strip()
            if not abs_path:
                continue
            try:
                if not os.path.exists(abs_path):
                    continue
            except Exception:
                continue
            docs.append(d)

        if not docs:
            messagebox.showinfo("Verbali", "Nessun documento importato disponibile tra i Verbali CD.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Seleziona verbale (documenti importati)")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry("840x420")

        container = ttk.Frame(dlg, padding=8)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Seleziona un documento (doppio click per scegliere):").pack(anchor="w")

        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

        columns = ("data", "numero", "nome", "categoria")
        tv = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)

        tv.heading("data", text="Data")
        tv.heading("numero", text="N.")
        tv.heading("nome", text="Nome file")
        tv.heading("categoria", text="Categoria")

        tv.column("data", width=100, anchor="w")
        tv.column("numero", width=90, anchor="w")
        tv.column("nome", width=430, anchor="w")
        tv.column("categoria", width=160, anchor="w")

        tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        category_tags = CategoryTagStyler(
            tv,
            default_label="Altro",
            palette=SECTION_CATEGORY_PALETTE,
            tag_prefix="cdverb::",
        )

        picked_by_iid: dict[str, int] = {}
        for idx, d in enumerate(docs):
            iid = str(idx)
            uploaded_at = str(d.get("uploaded_at") or "").strip()
            date_display = uploaded_at[:10] if len(uploaded_at) >= 10 else uploaded_at
            verbale_numero = str(d.get("verbale_numero") or "").strip()
            nome = str(d.get("nome_file") or "").strip()
            categoria = str(d.get("categoria") or "").strip()
            tv.insert(
                "",
                tk.END,
                iid=iid,
                values=(date_display, verbale_numero, nome, categoria),
                tags=(category_tags.tag_for(categoria),),
            )
            raw_id = d.get("id")
            try:
                doc_id = int(str(raw_id)) if raw_id is not None else 0
            except Exception:
                doc_id = 0
            picked_by_iid[iid] = doc_id

        actions = ttk.Frame(container)
        actions.pack(fill=tk.X)

        result: dict[str, int | None] = {"id": None}

        def _choose_selected() -> None:
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Verbali", "Seleziona un documento.", parent=dlg)
                return
            picked_id = picked_by_iid.get(str(sel[0]))
            if not picked_id:
                messagebox.showwarning("Verbali", "Documento non valido.", parent=dlg)
                return
            result["id"] = int(picked_id)
            try:
                dlg.destroy()
            except Exception:
                pass

        tv.bind("<Double-1>", lambda _e: _choose_selected())

        ttk.Button(actions, text="Annulla", command=dlg.destroy).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Seleziona", command=_choose_selected).pack(side=tk.RIGHT, padx=(0, 8))

        self.root.wait_window(dlg)
        picked_id = result.get("id")
        if not picked_id:
            return

        try:
            from cd_meetings import update_meeting

            ok = update_meeting(int(meeting_id), verbale_section_doc_id=int(picked_id))
            if not ok:
                messagebox.showerror("Verbali", "Impossibile collegare il verbale alla riunione.")
                return
            self._refresh_cd_verbali_docs()
        except Exception as exc:
            messagebox.showerror("Verbali", f"Errore collegamento verbale:\n{exc}")

    def _import_cd_verbali_from_folder(self):
        """Bulk-import verbali into section docs (Verbali CD)."""

        try:
            from document_types_catalog import SECTION_DOCUMENT_CATEGORIES
            from v4_ui.bulk_import_dialog import BulkImportDialog
            from section_documents import bulk_import_section_documents
            from v4_ui.import_report import build_import_summary
        except Exception as exc:
            messagebox.showerror("Import", f"Impossibile avviare l'import.\n\nDettagli: {exc}")
            return

        dlg = BulkImportDialog(
            self.root,
            title="Importa verbali CD da cartella",
            categories=list(SECTION_DOCUMENT_CATEGORIES),
            initial_category="Verbali CD",
        )
        self.root.wait_window(dlg)
        if not dlg.result:
            return

        folder, categoria, move = dlg.result
        try:
            imported, failed, details = bulk_import_section_documents(folder, categoria, move=move)
            messagebox.showinfo("Import", build_import_summary(imported, failed, details))
        except Exception as exc:
            messagebox.showerror("Import", f"Errore durante l'import:\n{exc}")
            return

        # Refresh lists: linked view + section docs panel (if present)
        try:
            self._refresh_cd_verbali_docs()
        except Exception:
            pass
        try:
            panel = getattr(self, "cd_section_docs_panel", None)
            if panel is not None:
                panel.refresh()
        except Exception:
            pass

    def _refresh_cd_verbali_docs(self):
        """Refresh the verbali list showing only verbali linked to CD meetings (past and future)."""
        tv = getattr(self, "tv_cd_verbali_docs", None)
        if tv is None:
            return

        from section_documents import list_cd_verbali_linked_documents

        start_date = None
        end_date = None
        label = ""
        mandato_id = None
        try:
            from cd_mandati import get_active_cd_mandato

            mandato = get_active_cd_mandato()
            if mandato:
                mandato_id = mandato.get("id")
                start_date = mandato.get("start_date")
                end_date = mandato.get("end_date")
                label = str(mandato.get("label") or "").strip()
        except Exception:
            mandato = None

        try:
            lbl = getattr(self, "_lbl_cd_mandato", None)
            if lbl is not None:
                if start_date and end_date:
                    shown = label or f"{str(start_date)[:4]}-{str(end_date)[:4]}"
                    lbl.config(text=f"Mandato attivo: {shown}")
                else:
                    lbl.config(text="Mandato attivo: (non impostato)")
        except Exception:
            pass

        # If the active mandate has ended, prompt a one-time end-of-mandate verification.
        try:
            from utils import today_iso

            today = today_iso()
            expired = bool(end_date and str(end_date) < str(today))
            already_prompted = getattr(self, "_cd_closure_prompted_mandato_id", None)
            if expired and mandato_id and already_prompted != mandato_id:
                self._cd_closure_prompted_mandato_id = mandato_id
                if messagebox.askyesno(
                    "Mandato CD terminato",
                    "Il mandato CD risulta terminato.\n\nVuoi verificare che verbali e libro delibere siano a posto?",
                ):
                    from cd_closure_checks import format_cd_mandato_closure_report, run_cd_mandato_closure_checks

                    report = run_cd_mandato_closure_checks(start_date=start_date, end_date=end_date)
                    text = format_cd_mandato_closure_report(report)
                    title = "Verifica fine mandato: OK" if report.get("ok") else "Verifica fine mandato: ATTENZIONE"
                    messagebox.showinfo(title, text)
        except Exception:
            pass

        for item in tv.get_children():
            tv.delete(item)

        self._cd_verbali_doc_path_map = {}

        # Show all verbali linked to meetings, regardless of the currently active mandate.
        # The mandate is still shown for context in the UI column.
        verbali = list_cd_verbali_linked_documents(start_date=None, end_date=None, include_missing=True)

        def _extract_iso_date_from_text(text: str | None) -> str | None:
            s = str(text or "")
            if not s:
                return None

            # Normalize separators to '-'
            norm = []
            for ch in s:
                if ch in "_./\\":
                    norm.append("-")
                else:
                    norm.append(ch)
            s2 = "".join(norm)

            def _is_valid_ymd(y: int, m: int, d: int) -> bool:
                if y < 1900 or y > 2200:
                    return False
                if m < 1 or m > 12:
                    return False
                if d < 1 or d > 31:
                    return False
                return True

            # Scan for YYYY-MM-DD
            for i in range(0, max(0, len(s2) - 9)):
                chunk = s2[i : i + 10]
                if len(chunk) != 10:
                    continue
                if chunk[4] != "-" or chunk[7] != "-":
                    continue
                y_str, m_str, d_str = chunk[0:4], chunk[5:7], chunk[8:10]
                if not (y_str.isdigit() and m_str.isdigit() and d_str.isdigit()):
                    continue
                y, m, d = int(y_str), int(m_str), int(d_str)
                if _is_valid_ymd(y, m, d):
                    return f"{y:04d}-{m:02d}-{d:02d}"

            # Scan for DD-MM-YYYY
            for i in range(0, max(0, len(s2) - 9)):
                chunk = s2[i : i + 10]
                if len(chunk) != 10:
                    continue
                if chunk[2] != "-" or chunk[5] != "-":
                    continue
                d_str, m_str, y_str = chunk[0:2], chunk[3:5], chunk[6:10]
                if not (y_str.isdigit() and m_str.isdigit() and d_str.isdigit()):
                    continue
                y, m, d = int(y_str), int(m_str), int(d_str)
                if _is_valid_ymd(y, m, d):
                    return f"{y:04d}-{m:02d}-{d:02d}"

            return None

        def _load_all_cd_mandati() -> list[dict]:
            try:
                from database import fetch_all

                rows = fetch_all(
                    """
                    SELECT id, label, start_date, end_date, is_active
                    FROM cd_mandati
                    WHERE start_date IS NOT NULL AND TRIM(start_date) <> ''
                      AND end_date IS NOT NULL AND TRIM(end_date) <> ''
                    ORDER BY start_date DESC, id DESC
                    """
                )
                return [dict(r) for r in rows]
            except Exception:
                return []

        mandati = _load_all_cd_mandati()

        def _mandato_label_for_date(iso_date: str | None) -> str:
            dv = (iso_date or "").strip()
            if not dv:
                return ""
            for m in mandati:
                s = str(m.get("start_date") or "").strip()
                e = str(m.get("end_date") or "").strip()
                if not s or not e:
                    continue
                if s <= dv <= e:
                    lbl = str(m.get("label") or "").strip()
                    if lbl:
                        return lbl
                    return f"Mandato {s[:4]}-{e[:4]}"
            return ""

        def _verbale_ref_date(doc: dict) -> str:
            # Prefer extracting the verbale date from filename/description.
            extracted = (
                _extract_iso_date_from_text(doc.get("original_name"))
                or _extract_iso_date_from_text(doc.get("nome_file"))
                or _extract_iso_date_from_text(doc.get("descrizione"))
            )
            if extracted:
                return extracted
            return _date_value(doc)

        def _date_value(d: dict) -> str:
            raw = str(d.get("uploaded_at") or "").strip()
            return raw[:10] if len(raw) >= 10 else raw

        try:
            import os
        except Exception:  # pragma: no cover
            os = None

        for idx, doc in enumerate(verbali, start=1):
            # One row per meeting (canonical link)
            iid = str(doc.get("meeting_id") or doc.get("id") or f"v{idx}")
            meeting_date = str(doc.get("meeting_date") or "").strip()
            data = meeting_date or _date_value(doc)
            mandato_lbl = _mandato_label_for_date(meeting_date or _verbale_ref_date(doc))
            numero = str(doc.get("meeting_numero_cd") or doc.get("verbale_numero") or "")
            descrizione = str(doc.get("descrizione") or "")
            filename = str(doc.get("nome_file") or "")
            abs_path = str(doc.get("absolute_path") or doc.get("percorso") or "")

            tags: tuple[str, ...] = ()
            try:
                if (not abs_path) or (os is not None and not os.path.exists(abs_path)):
                    tags = ("missing",)
            except Exception:
                pass

            tv.insert("", tk.END, iid=iid, values=(data, numero, mandato_lbl, descrizione, filename), tags=tags)
            if abs_path:
                self._cd_verbali_doc_path_map[iid] = abs_path

    def _export_cd_verbale_doc(self):
        tv = getattr(self, "tv_cd_verbali_docs", None)
        if tv is None:
            return

        sel = tv.selection()
        if not sel:
            messagebox.showwarning("Verbali", "Selezionare un verbale")
            return

        iid = str(sel[0])
        abs_path = str(getattr(self, "_cd_verbali_doc_path_map", {}).get(iid) or "").strip()
        if not abs_path:
            messagebox.showerror("Verbali", "Percorso file non disponibile per l'elemento selezionato.")
            return

        try:
            import os
            from pathlib import Path
            import shutil

            if not os.path.exists(abs_path):
                messagebox.showerror("Verbali", "File non trovato sul disco.")
                return

            values = tv.item(iid, "values") or ()
            data = str(values[0]) if len(values) > 0 else ""
            numero = str(values[1]) if len(values) > 1 else ""

            # Build a safe filename: Verbale_{numero_cd}_{data}
            def _safe(s: str) -> str:
                s2 = (s or "").strip()
                for ch in '<>:\\"/|?*':
                    s2 = s2.replace(ch, "_")
                return s2

            numero_safe = _safe(numero) or "NA"
            data_safe = _safe(data) or "DATA"

            src = Path(abs_path)
            ext = (src.suffix or "").lower()
            if ext not in (".pdf", ".docx", ".doc"):
                # Fallback: preserve whatever extension the source has.
                ext = src.suffix or ""

            initial_name = f"Verbale_{numero_safe}_{data_safe}{ext}"

            if ext == ".pdf":
                filetypes = [("PDF", "*.pdf"), ("Tutti i file", "*.*")]
                defext = ".pdf"
            elif ext in (".docx", ".doc"):
                filetypes = [("Word", "*.docx *.doc"), ("Tutti i file", "*.*")]
                defext = ".docx" if ext == ".docx" else ".doc"
            else:
                filetypes = [("Tutti i file", "*.*")]
                defext = ext

            dest = filedialog.asksaveasfilename(
                title="Esporta verbale",
                initialfile=initial_name,
                defaultextension=defext,
                filetypes=filetypes,
            )
            if not dest:
                return

            shutil.copy2(abs_path, dest)
            messagebox.showinfo("Verbali", "Verbale esportato correttamente.")
        except Exception as exc:
            messagebox.showerror("Verbali", f"Errore durante l'esportazione:\n{exc}")

    def _open_cd_mandato_wizard(self):
        try:
            from .cd_mandato_wizard import CdMandatoWizard

            CdMandatoWizard(self.root, on_saved=lambda _r=None: self._refresh_cd_verbali_docs())
        except Exception as exc:
            logger.error("Errore apertura wizard mandato CD: %s", exc)
            messagebox.showerror("Mandato CD", f"Impossibile aprire il wizard:\n{exc}")

    def _open_cd_verbale_doc(self):
        tv = getattr(self, "tv_cd_verbali_docs", None)
        if tv is None:
            return
        sel = tv.selection()
        if not sel:
            messagebox.showwarning("Verbali", "Selezionare un verbale da aprire")
            return
        path = self._cd_verbali_doc_path_map.get(sel[0])
        if not path:
            messagebox.showerror("Verbali", "Percorso documento non disponibile")
            return
        from utils import open_path

        def _on_open_verbali_error(msg: str) -> None:
            messagebox.showerror("Verbali", msg)

        ok = open_path(path, on_error=_on_open_verbali_error)
        if not ok:
            self._refresh_cd_verbali_docs()

    def _treeview_sort_column(self, tv, col, reverse=False):
        """Sort treeview `tv` by column `col`. Reverse if `reverse` True."""
        try:
            items = [(tv.set(k, col), k) for k in tv.get_children('')]

            def _conv(v):
                if v is None:
                    return ('', '')
                s = str(v).strip()
                # Special handling: matricola "familiare" should sort by numeric matricola if possible
                if col == 'familiare':
                    if s.isdigit():
                        return (0, int(s))
                    return (1, s.lower())
                try:
                    return (0, int(s))
                except Exception:
                    try:
                        return (1, float(s))
                    except Exception:
                        return (2, s.lower())

            items.sort(key=lambda t: _conv(t[0]), reverse=reverse)

            for index, (_, k) in enumerate(items):
                tv.move(k, '', index)

            # Update heading indicators (▲ descending, ▼ ascending)
            try:
                # Clear previous indicators
                last = getattr(tv, '_last_sorted', (None, None))
                if last and last[0] and last[0] in tv['columns']:
                    # restore previous heading text without arrow
                    text = tv.heading(last[0])['text']
                    # strip arrows
                    text = text.replace(' ▲', '').replace(' ▼', '')
                    tv.heading(last[0], text=text)

                # set current heading text
                h = tv.heading(col)
                base = h.get('text', col)
                arrow = '▲' if not reverse else '▼'  # ascending on first click
                # strip any existing arrows then set
                base = base.replace('▲', '').replace('▼', '').strip()
                tv.heading(col, text=f"{base} {arrow}")
            except Exception:
                pass
        except Exception as e:
            logger.debug('Treeview sort failed for col %s: %s', col, e)
    
    def _new_cd_meeting(self):
        """Open dialog to create a new CD meeting"""
        from cd_meetings_dialog import MeetingDialog
        MeetingDialog(self.root)
    
    def _open_cd_meetings_list(self):
        """Open the comprehensive CD meetings manager"""
        from cd_meetings_dialog import MeetingsListDialog
        MeetingsListDialog(self.root)
    
    def _refresh_cd_delibere(self):
        """Refresh the CD delibere list"""
        from cd_delibere import get_all_delibere

        tv = getattr(self, "tv_cd_delibere", None) or getattr(self, "tv_cd_delibere_overview", None)
        if tv is None:
            return
        
        # Clear existing items
        for item in tv.get_children():
            tv.delete(item)
        
        def _esito_tag(esito_value: object) -> tuple[str, ...]:
            s = str(esito_value or "").strip().lower()
            if not s:
                return ("esito_pending",)
            ok_words = ("approv", "favorev", "ok", "si", "sì")
            ko_words = ("resp", "boc", "no", "contr")
            if any(w in s for w in ok_words):
                return ("esito_ok",)
            if any(w in s for w in ko_words):
                return ("esito_ko",)
            if "rinv" in s or "sosp" in s or "att" in s:
                return ("esito_pending",)
            return ()

        # Load delibere
        delibere = get_all_delibere()
        for delibera in delibere:
            esito = delibera.get('esito', '')
            tv.insert(
                "",
                tk.END,
                iid=delibera['id'],
                values=(
                    delibera['id'],
                    delibera.get('numero', ''),
                    delibera.get('oggetto', ''),
                    esito,
                    delibera.get('data_votazione', '')
                ),
                tags=_esito_tag(esito),
            )
    
    def _new_cd_delibera(self):
        """Open dialog to create a new delibera"""
        from cd_delibere_dialog import DeliberaDialog
        DeliberaDialog(self.root)
        self._refresh_cd_delibere()
    
    def _edit_cd_delibera(self):
        """Open dialog to edit selected delibera"""
        tv = getattr(self, "tv_cd_delibere", None) or getattr(self, "tv_cd_delibere_overview", None)
        if tv is None:
            messagebox.showwarning("Selezione", "Lista delibere non disponibile")
            return

        selection = tv.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Selezionare una delibera da modificare")
            return
        
        delibera_id = int(selection[0])
        from cd_delibere_dialog import DeliberaDialog
        DeliberaDialog(self.root, delibera_id=delibera_id)
        self._refresh_cd_delibere()
    
    def _delete_cd_delibera(self):
        """Delete selected delibera"""
        tv = getattr(self, "tv_cd_delibere", None) or getattr(self, "tv_cd_delibere_overview", None)
        if tv is None:
            messagebox.showwarning("Selezione", "Lista delibere non disponibile")
            return

        selection = tv.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Selezionare una delibera da eliminare")
            return
        
        if messagebox.askyesno("Conferma", "Eliminare la delibera selezionata?"):
            delibera_id = int(selection[0])
            from cd_delibere import delete_delibera
            if delete_delibera(delibera_id):
                self._refresh_cd_delibere()
            else:
                messagebox.showerror("Errore", "Impossibile eliminare la delibera")

    def _create_calendar_tab(self):
        """Create the Calendario tab with event list and actions."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📅 Calendario")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(toolbar, text="Nuovo evento", command=self._open_calendar_wizard).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Modifica", command=self._edit_calendar_event).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Elimina", command=self._delete_calendar_event).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Esporta tutto (.ics)", command=self._export_calendar_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Esporta selezionato (.ics)", command=self._export_calendar_single).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Aggiorna", command=self._refresh_calendar_events).pack(side=tk.LEFT, padx=2)

        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Label(filter_frame, text="Filtra per tipo:").pack(side=tk.LEFT)
        options = [("tutti", "Tutti gli eventi")] + list(CALENDAR_EVENT_TYPES)
        self.calendar_filter_map = {label: code for code, label in options}
        self.calendar_filter_display = tk.StringVar(value=options[0][1])
        self.calendar_filter_var = tk.StringVar(value="tutti")
        filter_combo = ttk.Combobox(
            filter_frame,
            state="readonly",
            values=[label for _, label in options],
            textvariable=self.calendar_filter_display,
            width=28,
        )
        filter_combo.current(0)
        filter_combo.pack(side=tk.LEFT, padx=6)
        filter_combo.bind("<<ComboboxSelected>>", self._on_calendar_filter_change)
        self.calendar_badge_var = tk.StringVar(value="Nessun evento pianificato.")
        ttk.Label(filter_frame, textvariable=self.calendar_badge_var, foreground="#b35a00").pack(side=tk.RIGHT)

        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        columns = ("badge", "titolo", "tipo", "data", "ora", "luogo", "reminder")
        self.calendar_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        headings = {
            "badge": "🔔",
            "titolo": "Titolo",
            "tipo": "Tipo",
            "data": "Data",
            "ora": "Ora",
            "luogo": "Luogo",
            "reminder": "Promemoria",
        }
        widths = {
            "badge": 40,
            "titolo": 260,
            "tipo": 130,
            "data": 100,
            "ora": 70,
            "luogo": 160,
            "reminder": 120,
        }
        for col in columns:
            self.calendar_tree.heading(col, text=headings.get(col, col))
            anchor = "center" if col in {"badge", "data", "ora", "reminder"} else "w"
            self.calendar_tree.column(col, width=widths.get(col, 120), anchor=anchor)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.calendar_tree.yview)
        self.calendar_tree.configure(yscrollcommand=scrollbar.set)
        self.calendar_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.calendar_tree.bind("<<TreeviewSelect>>", self._on_calendar_select)

        # Row coloring by event type.
        self._calendar_type_tags = CategoryTagStyler(
            self.calendar_tree,
            default_label="Altro",
            palette=SECTION_CATEGORY_PALETTE,
            tag_prefix="cal::",
        )
        try:
            self._calendar_type_tags.prime(self.calendar_type_labels.values())
        except Exception:
            pass

        details = ttk.LabelFrame(tab, text="Dettagli evento")
        details.pack(fill=tk.BOTH, expand=False, padx=5, pady=(0, 5))
        self.calendar_details = tk.Text(details, height=6, wrap=tk.WORD, state=tk.DISABLED)
        self.calendar_details.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._refresh_calendar_events()

    def _calendar_type_label(self, code: str | None) -> str:
        if not code:
            return "Altro"
        return self.calendar_type_labels.get(code, code)

    def _parse_calendar_ts(self, ts: str | None):
        if not ts:
            return None
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None

    def _on_calendar_filter_change(self, _event=None):
        label = getattr(self, "calendar_filter_display", None)
        if label:
            self.calendar_filter_var.set(self.calendar_filter_map.get(label.get(), "tutti"))
        self._refresh_calendar_events()

    def _refresh_calendar_events(self):
        if not hasattr(self, "calendar_tree"):
            return
        try:
            from database import fetch_calendar_events

            filtro = getattr(self, "calendar_filter_var", None)
            tipo = filtro.get() if filtro else "tutti"
            query_tipo = None if tipo == "tutti" else tipo
            events = fetch_calendar_events(tipo=query_tipo)
        except Exception as exc:
            logger.error("Failed to load calendar events: %s", exc)
            messagebox.showerror("Calendario", f"Errore nel caricamento eventi:\n{exc}")
            return

        self.calendar_events = events
        tree = self.calendar_tree
        previous = tree.selection()
        prev_id = previous[0] if previous else None
        for item in tree.get_children():
            tree.delete(item)

        now = datetime.now()
        horizon = now + timedelta(days=14)
        upcoming = 0

        for ev in events:
            dt = self._parse_calendar_ts(ev.get("start_ts"))
            date_str = ""
            time_str = ""
            badge = ""
            if dt:
                date_str = dt.strftime("%d/%m/%Y")
                time_str = dt.strftime("%H:%M")
                if now <= dt <= horizon:
                    badge = "🔔"
                    upcoming += 1
            else:
                raw = ev.get("start_ts", "")
                date_str = raw[:10]
            reminder = ev.get("reminder_days")
            reminder_display = f"{reminder}g" if reminder not in (None, "") else ""
            values = (
                badge,
                ev.get("titolo", ""),
                self._calendar_type_label(ev.get("tipo")),
                date_str,
                time_str,
                ev.get("luogo", "") or "",
                reminder_display,
            )
            type_label = values[2]
            tag_manager = getattr(self, "_calendar_type_tags", None)
            tags = (tag_manager.tag_for(type_label),) if tag_manager is not None else ()
            tree.insert("", tk.END, iid=str(ev.get("id")), values=values, tags=tags)

        if upcoming:
            suffix = "evento" if upcoming == 1 else "eventi"
            self.calendar_badge_var.set(f"🔔 {upcoming} {suffix} entro 14 giorni")
        elif events:
            self.calendar_badge_var.set("Nessun evento imminente (14gg)")
        else:
            self.calendar_badge_var.set("Nessun evento pianificato.")

        target = prev_id if prev_id and tree.exists(prev_id) else None
        if not target:
            children = tree.get_children()
            target = children[0] if children else None
        if target:
            tree.selection_set(target)
            tree.focus(target)
            self._on_calendar_select()
        else:
            self._show_calendar_details(None)

    def _get_selected_calendar_event(self):
        if not hasattr(self, "calendar_tree"):
            return None
        selection = self.calendar_tree.selection()
        if not selection:
            return None
        event_id = selection[0]
        for ev in self.calendar_events:
            if str(ev.get("id")) == str(event_id):
                return ev
        return None

    def _on_calendar_select(self, _event=None):
        self._show_calendar_details(self._get_selected_calendar_event())

    def _show_calendar_details(self, event_data):
        if not hasattr(self, "calendar_details"):
            return
        widget = self.calendar_details
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        if not event_data:
            widget.insert("1.0", "Nessun evento selezionato.")
        else:
            dt = self._parse_calendar_ts(event_data.get("start_ts"))
            if dt:
                date_line = dt.strftime("Data: %d/%m/%Y alle %H:%M")
            else:
                date_line = f"Data: {event_data.get('start_ts', '')}"
            lines = [
                event_data.get("titolo", "Evento"),
                date_line,
                f"Tipo: {self._calendar_type_label(event_data.get('tipo'))}",
            ]
            luogo = event_data.get("luogo")
            if luogo:
                lines.append(f"Luogo: {luogo}")
            reminder = event_data.get("reminder_days")
            if reminder not in (None, ""):
                lines.append(f"Promemoria: {reminder} giorni prima")
            descr = event_data.get("descrizione")
            if descr:
                lines.append("")
                lines.append(descr)
            widget.insert("1.0", "\n".join(lines))
        widget.config(state=tk.DISABLED)

    def _open_calendar_wizard(self):
        CalendarWizard(self.root, on_saved=lambda _eid: self._refresh_calendar_events())

    def _edit_calendar_event(self):
        event = self._get_selected_calendar_event()
        if not event:
            messagebox.showinfo("Calendario", "Seleziona un evento da modificare.")
            return
        CalendarWizard(self.root, event=event, on_saved=lambda _eid: self._refresh_calendar_events())

    def _delete_calendar_event(self):
        event = self._get_selected_calendar_event()
        if not event:
            messagebox.showinfo("Calendario", "Seleziona un evento da eliminare.")
            return
        titolo = event.get("titolo", "evento")
        if not messagebox.askyesno("Conferma", f"Eliminare l'evento:\n{titolo}?"):
            return
        try:
            from database import delete_calendar_event

            if delete_calendar_event(event["id"]):
                self._refresh_calendar_events()
                self._set_status_message("Evento calendario eliminato.")
            else:
                messagebox.showerror("Calendario", "Impossibile eliminare l'evento selezionato.")
        except Exception as exc:
            logger.error("Calendar delete failed: %s", exc)
            messagebox.showerror("Calendario", f"Errore eliminazione evento:\n{exc}")

    def _export_calendar_all(self):
        try:
            from database import fetch_calendar_events

            events = fetch_calendar_events()
        except Exception as exc:
            logger.error("Calendar export-all failed: %s", exc)
            messagebox.showerror("Calendario", f"Errore lettura eventi:\n{exc}")
            return
        if not events:
            messagebox.showinfo("Calendario", "Non ci sono eventi da esportare.")
            return
        path = self._prompt_calendar_export_path("calendario_librosoci.ics")
        if not path:
            return
        try:
            self._write_calendar_ics(path, events)
            messagebox.showinfo("Calendario", f"Esportazione completata:\n{path}")
        except Exception as exc:
            logger.error("Calendar export write failed: %s", exc)
            messagebox.showerror("Calendario", f"Errore durante il salvataggio:\n{exc}")

    def _export_calendar_single(self):
        event = self._get_selected_calendar_event()
        if not event:
            messagebox.showinfo("Calendario", "Seleziona un evento da esportare.")
            return
        slug = self._calendar_slug(event.get("titolo") or f"evento_{event['id']}")
        path = self._prompt_calendar_export_path(f"{slug}.ics")
        if not path:
            return
        try:
            self._write_calendar_ics(path, [event])
            messagebox.showinfo("Calendario", f"Evento esportato in:\n{path}")
        except Exception as exc:
            logger.error("Calendar single export failed: %s", exc)
            messagebox.showerror("Calendario", f"Errore durante il salvataggio:\n{exc}")

    def _prompt_calendar_export_path(self, default_name: str) -> str | None:
        return filedialog.asksaveasfilename(
            parent=self.root,
            title="Salva file ICS",
            defaultextension=".ics",
            filetypes=[("Calendario ICS", "*.ics")],
            initialfile=default_name,
        )

    def _write_calendar_ics(self, file_path: str, events):
        content = events_to_ics(events)
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _calendar_slug(self, title: str) -> str:
        if not title:
            return "evento"
        cleaned = ["".join(ch for ch in part if ch.isalnum()) for part in title.lower().split()]
        cleaned = [part for part in cleaned if part]
        return "_".join(cleaned) or "evento"
    
    def _create_section_tab(self):
        """Create the Section Info tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🏠 Sezione")
        
        # Content frame
        content_frame = ttk.Frame(tab)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        from .panels import SectionInfoPanel
        self.panel_section = SectionInfoPanel(content_frame, editable=False)
        self.panel_section.pack(fill=tk.BOTH, expand=True)
        
        # Load section config
        self.panel_section.set_values(self.cfg)
        
        # Reminder label to direct edits to the Tools dialog
        ttk.Label(
            tab,
            text="Le informazioni di sezione sono modificabili solo da Strumenti ▶ Configurazione Sezione",
            foreground="gray40",
        ).pack(fill=tk.X, padx=10, pady=(0, 8))
    
    def _create_statistics_tab(self):
        """Create the Statistics tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📊 Statistiche")
        
        from v4_ui.stats_panel import StatsPanel
        self.stats_panel = StatsPanel(tab)
        self.stats_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _create_statusbar(self):
        """Create the status bar and keep track of appended selection info."""
        self.status_message = "Pronto"
        self.selection_summary = ""
        self.statusbar = ttk.Label(self.root, relief=tk.SUNKEN)
        self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        self._refresh_statusbar_text()

    def _show_startup_issues(self):
        """Display cumulative startup warnings detected before UI launch."""
        if not getattr(self, "startup_issues", None):
            return
        message = format_startup_issues(self.startup_issues)
        if not message:
            return
        logger.warning("Problemi rilevati all'avvio:\n%s", message)
        try:
            messagebox.showwarning("Verifiche iniziali", message)
        except Exception as exc:  # pragma: no cover - UI safeguard
            logger.error("Impossibile mostrare l'avviso iniziale: %s", exc)
        finally:
            self.startup_issues = []

    def _set_status_message(self, message: str | None):
        """Set the base status message and refresh the UI label."""
        self.status_message = message or "Pronto"
        self._refresh_statusbar_text()

    def _refresh_statusbar_text(self):
        """Recompute the composed status string (message + selection summary)."""
        if not hasattr(self, "statusbar"):
            return
        base = self.status_message or "Pronto"
        if getattr(self, "selection_summary", ""):
            base = f"{base} — {self.selection_summary}"
        self.statusbar.config(text=base)

    def _refresh_docs_preview(self, socio_id: int | None):
        """Populate the inline document list shown under the Note field."""
        tree = getattr(self, 'docs_preview_tree', None)
        info_var = getattr(self, 'docs_preview_info_var', None)
        if tree is None or info_var is None:
            return

        for item in tree.get_children():
            tree.delete(item)

        if not socio_id:
            info_var.set("Seleziona un socio per visualizzare i documenti.")
            return

        try:
            from database import get_documenti
            docs = get_documenti(socio_id)
            from documents_manager import format_file_info
        except Exception as exc:
            logger.error("Impossibile caricare i documenti per il socio %s: %s", socio_id, exc)
            info_var.set("Errore durante il caricamento dei documenti.")
            return

        if not docs:
            info_var.set("Nessun documento caricato per questo socio.")
            return

        docs_sorted = sorted(
            docs,
            key=lambda d: (d.get('data_caricamento') or ''),
            reverse=True,
        )

        for doc in docs_sorted:
            info_text = format_file_info(doc.get('percorso') or '')
            row_tags: list[str] = []
            try:
                if not os.path.exists(doc.get('percorso') or ''):
                    row_tags.append("missing")
            except Exception:
                pass

            tag_manager = getattr(self, "_docs_preview_category_tags", None)
            if tag_manager is not None:
                try:
                    row_tags.append(tag_manager.tag_for(doc.get('categoria') or ''))
                except Exception:
                    pass

            tree.insert(
                "",
                tk.END,
                values=(
                    doc.get('id', ''),
                    doc.get('descrizione', '') or '',
                    doc.get('categoria', ''),
                    doc.get('tipo', ''),
                    doc.get('nome_file', ''),
                    (doc.get('data_caricamento') or '')[:10],
                    info_text,
                ),
                tags=tuple(row_tags) if row_tags else (),
            )

        count = len(docs_sorted)
        suffix = "i" if count != 1 else "o"
        info_var.set(f"{count} document{suffix} trovati per il socio selezionato.")

    def _on_tree_selection_changed(self, _event=None):
        self._update_selection_summary()
        member_id = None
        selection = self.tv_soci.selection()
        if len(selection) == 1:
            member_id = self._get_member_id_from_item(selection[0])
        self._refresh_docs_preview(member_id)

    def _update_selection_summary(self):
        """Update the selection summary appended to the status bar text."""
        if not hasattr(self, "tv_soci"):
            return
        count = len(self.tv_soci.selection())
        if count > 0:
            label = "socio selezionato" if count == 1 else "soci selezionati"
            self.selection_summary = f"{count} {label}"
        else:
            self.selection_summary = ""
        self._refresh_statusbar_text()
    
    def _add_tab_delimiter(self):
        """Add a visual delimiter (separator) between tabs."""
        delimiter_frame = ttk.Frame(self.notebook)
        self.notebook.add(delimiter_frame, text="")
        # Make the delimiter visually distinct with minimal height
        ttk.Separator(delimiter_frame, orient="vertical").pack(fill=tk.BOTH, expand=False)
    
    def _not_implemented(self):
        """Show placeholder for unimplemented features."""
        messagebox.showinfo("In arrivo", "Questa funzione sarà disponibile presto!")
    
    def _show_about(self):
        """Show about dialog."""
        from config import APP_NAME, APP_VERSION, AUTHOR, BUILD_DATE
        messagebox.showinfo(
            "Informazioni",
            f"{APP_NAME} v{APP_VERSION}\n"
            f"Build: {BUILD_DATE}\n"
            f"Autore: {AUTHOR}"
        )
    
    def _show_shortcuts_help(self):
        """Show keyboard shortcuts help dialog."""
        shortcuts_text = """
SCORCIATOIE DA TASTIERA

Gestione Soci:
  Ctrl+N        Nuovo socio
  Ctrl+S        Salva modifiche
  Ctrl+Del      Elimina socio selezionato
  Ctrl+M        Ricerca duplicati
  
Navigazione:
  Ctrl+F        Cerca socio
  F5            Aggiorna lista soci
  Ctrl+Tab      Pannello successivo
  Ctrl+Shift+Tab Pannello precedente
  Ctrl+1/2/3    Vai a pannello Soci/CD/Stats
  
Operazioni:
    Ctrl+E        Esporta dati
  Ctrl+B        Backup manuale database
  
Generale:
  Ctrl+Q        Esci dall'applicazione
        """
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Scorciatoie da Tastiera")
        dialog.geometry("450x400")
        dialog.resizable(False, False)
        
        # Center dialog
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Text widget with shortcuts
        text = tk.Text(dialog, wrap=tk.WORD, font="AppMono", padx=20, pady=20)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert("1.0", shortcuts_text.strip())
        text.config(state=tk.DISABLED)
        
        # Close button
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Chiudi", command=dialog.destroy).pack()

    def _show_quota_legend(self):
        """Display a legend of the available quota (causali) codes."""
        rows = self._load_causali_quote_rows()
        if not rows:
            messagebox.showerror(
                "Legenda quote",
                "Impossibile leggere il file causali_quote.csv. Verificare che sia presente nella cartella dell'applicazione.",
            )
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Legenda codici quote")
        dialog.geometry("720x520")
        dialog.transient(self.root)
        dialog.grab_set()

        info = (
            "Legenda delle causali quote.\n"
            "La tabella seguente riporta i codici da utilizzare per ogni tipo di quota." 
        )
        ttk.Label(dialog, text=info, justify=tk.LEFT).pack(fill=tk.X, padx=12, pady=(12, 0))

        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tree = ttk.Treeview(
            frame,
            columns=("corrente", "successiva", "descrizione"),
            show="headings",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=tree.yview)

        tree.heading("corrente", text="Quota versata entro 31/12")
        tree.heading("successiva", text="Quota versata dopo 01/01")
        tree.heading("descrizione", text="Descrizione")

        tree.column("corrente", width=150, anchor="center")
        tree.column("successiva", width=150, anchor="center")
        tree.column("descrizione", width=360, anchor="w")

        for row in rows:
            tree.insert(
                "",
                tk.END,
                values=(
                    row.get("quotaannocorr", ""),
                    row.get("quotaannosucc", ""),
                    row.get("descrizione", ""),
                ),
            )

        tree.pack(fill=tk.BOTH, expand=True)

        ttk.Button(dialog, text="Chiudi", command=dialog.destroy).pack(pady=(4, 10))

    def _load_causali_quote_rows(self):
        """Load legend rows from the bundled CSV file."""
        try:
            csv_path = Path(__file__).with_name("causali_quote.csv")
            if not csv_path.exists():
                logger.error("Causali quote CSV missing: %s", csv_path)
                return []
            with csv_path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = []
                for row in reader:
                    rows.append({k: (v or "").strip() for k, v in row.items()})
                return rows
        except Exception as exc:
            logger.error("Failed to load causali legend: %s", exc)
            return []
    
    def _add_member(self):
        """Add new member."""
        self.form_member.clear()
        self.tv_soci.selection_remove(self.tv_soci.selection())
        self.current_member_id = None
        self._set_status_message("Nuovo socio - Compilare il form e fare clic su Salva")
        # Summary panel removed - no need to clear
        # if hasattr(self, '_clear_summary'):
        #     self._clear_summary()
    
    def _edit_member(self):
        """Edit selected member."""
        sel = self.tv_soci.selection()
        if not sel:
            messagebox.showinfo("Modifica", "Selezionare un socio.")
            return
        
        member_id = self._get_member_id_from_item(sel[0])
        if member_id is None:
            messagebox.showerror("Errore", "Impossibile leggere l'ID del socio selezionato.")
            return

        self.current_member_id = member_id
        self._load_member(self.current_member_id)
        self._set_status_message(f"Modifica socio #{self.current_member_id}")
    
    def _delete_member(self):
        """Delete selected member (soft delete)."""
        sel = self.tv_soci.selection()
        if not sel:
            messagebox.showinfo("Elimina", "Selezionare un socio.")
            return
        
        # Get member info for confirmation
        from database import fetch_one
        socio_id = self._get_member_id_from_item(sel[0])
        if socio_id is None:
            messagebox.showerror("Errore", "Impossibile leggere l'ID del socio selezionato.")
            return
        
        socio = fetch_one("SELECT nominativo, nome, cognome, matricola FROM soci WHERE id = ?", [socio_id])
        if not socio:
            messagebox.showerror("Errore", "Socio non trovato.")
            return
        
        # Build display name
        nominativo = socio['nominativo'] if 'nominativo' in socio.keys() and socio['nominativo'] else ""
        nome = socio['nome'] if 'nome' in socio.keys() and socio['nome'] else ""
        cognome = socio['cognome'] if 'cognome' in socio.keys() and socio['cognome'] else ""
        matricola = socio['matricola'] if 'matricola' in socio.keys() and socio['matricola'] else ""
        
        display_name = nominativo if nominativo else f"{nome} {cognome}".strip()
        if matricola:
            display_name = f"{display_name} (Mat. {matricola})"
        
        if not messagebox.askyesno("Elimina", f"Eliminare il socio:\n{display_name}?\n\nL'eliminazione è reversibile (soft delete)."):
            return
        
        try:
            from database import exec_query
            exec_query("UPDATE soci SET deleted_at = datetime('now') WHERE id = ?", [socio_id])
            self._refresh_member_list()
            self._set_status_message(f"Socio {display_name} eliminato (soft delete).")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")

    def _get_display_value(self, values, column):
        """Return the value for a display column, accounting for the warning column."""
        if not values:
            return ""

        try:
            idx = self.COLONNE_DISPLAY.index(column)
        except ValueError:
            return ""

        if idx >= len(values):
            return ""
        return values[idx]

    def _get_member_id_from_item(self, item_id):
        """Resolve the member ID associated with a Treeview item."""
        if not item_id:
            return None

        lookup = getattr(self, 'member_lookup', None)
        if lookup is None:
            lookup = {}
            self.member_lookup = lookup

        member_id = lookup.get(item_id)
        if member_id is not None:
            return member_id

        # Fallback: attempt to resolve via the matricola shown in the row
        try:
            values = self.tv_soci.item(item_id).get("values", [])
            matricola_val = self._get_display_value(values, "matricola")
            if matricola_val:
                from database import fetch_one
                row = fetch_one(
                    "SELECT id FROM soci WHERE matricola = ? AND deleted_at IS NULL",
                    (matricola_val,),
                )
                if row:
                    resolved_id = row['id'] if hasattr(row, 'keys') else row[0]
                    lookup[item_id] = resolved_id
                    return resolved_id
        except Exception as exc:
            logger.debug("Member lookup fallback failed for %s: %s", item_id, exc)
        return None
    
    def _open_email_wizard(self):
        """Open email wizard for creating emails from templates."""
        from email_wizard import show_email_wizard
        show_email_wizard(self.root)
    
    def _show_trash(self):
        """Show deleted members (trash bin) with restore option."""
        trash_win = tk.Toplevel(self.root)
        trash_win.title("Cestino - Soci Eliminati")
        trash_win.geometry("900x500")
        trash_win.transient(self.root)
        
        # Toolbar
        toolbar = ttk.Frame(trash_win)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(toolbar, text="Soci eliminati (soft delete)", font="AppBold").pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Svuota cestino", command=lambda: self._empty_trash(trash_tree)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="Ripristina", command=lambda: self._restore_member(trash_tree, trash_win)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="Elimina definitivamente", command=lambda: self._hard_delete_member(trash_tree)).pack(side=tk.RIGHT, padx=2)
        
        # Treeview
        tree_frame = ttk.Frame(trash_win)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("id", "matricola", "nominativo", "nome", "cognome", "email", "deleted_at")
        trash_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", yscrollcommand=scrollbar.set)
        scrollbar.config(command=trash_tree.yview)
        
        trash_tree.heading("id", text="ID")
        trash_tree.heading("matricola", text="Matricola")
        trash_tree.heading("nominativo", text="Nominativo")
        trash_tree.heading("nome", text="Nome")
        trash_tree.heading("cognome", text="Cognome")
        trash_tree.heading("email", text="Email")
        trash_tree.heading("deleted_at", text="Data eliminazione")
        
        trash_tree.column("id", width=50)
        trash_tree.column("matricola", width=80)
        trash_tree.column("nominativo", width=100)
        trash_tree.column("nome", width=100)
        trash_tree.column("cognome", width=100)
        trash_tree.column("email", width=200)
        trash_tree.column("deleted_at", width=150)
        
        trash_tree.pack(fill=tk.BOTH, expand=True)
        
        # Load deleted members
        self._refresh_trash(trash_tree)
        
        ttk.Button(trash_win, text="Chiudi", command=trash_win.destroy).pack(pady=5)
    
    def _refresh_trash(self, tree):
        """Refresh trash bin treeview."""
        from database import fetch_all
        
        # Clear tree
        for item in tree.get_children():
            tree.delete(item)
        
        # Load deleted members
        rows = fetch_all(
            "SELECT id, matricola, nominativo, nome, cognome, email, deleted_at FROM soci WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC"
        )
        
        for row in rows:
            values = [
                row['id'] if 'id' in row.keys() else '',
                row['matricola'] if 'matricola' in row.keys() else '',
                row['nominativo'] if 'nominativo' in row.keys() else '',
                row['nome'] if 'nome' in row.keys() else '',
                row['cognome'] if 'cognome' in row.keys() else '',
                row['email'] if 'email' in row.keys() else '',
                row['deleted_at'] if 'deleted_at' in row.keys() else '',
            ]
            tree.insert("", "end", values=values)
    
    def _restore_member(self, tree, window):
        """Restore a deleted member."""
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Ripristina", "Selezionare un socio da ripristinare.")
            return
        
        item = tree.item(sel[0])
        socio_id = item["values"][0]
        nominativo = item["values"][2] or f"{item['values'][3]} {item['values'][4]}".strip()
        
        if not messagebox.askyesno("Ripristina", f"Ripristinare il socio:\n{nominativo}?"):
            return
        
        try:
            from database import exec_query
            exec_query("UPDATE soci SET deleted_at = NULL WHERE id = ?", [socio_id])
            self._refresh_trash(tree)
            self._refresh_member_list()
            self._set_status_message(f"Socio {nominativo} ripristinato.")
            messagebox.showinfo("Ripristina", "Socio ripristinato con successo!")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")
    
    def _hard_delete_member(self, tree):
        """Permanently delete a member from database."""
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Elimina", "Selezionare un socio da eliminare definitivamente.")
            return
        
        item = tree.item(sel[0])
        socio_id = item["values"][0]
        nominativo = item["values"][2] or f"{item['values'][3]} {item['values'][4]}".strip()
        
        if not messagebox.askyesno("Elimina definitivamente", 
                                    f"ATTENZIONE: Eliminare definitivamente il socio:\n{nominativo}?\n\nQuesta operazione è IRREVERSIBILE!",
                                    icon='warning'):
            return
        
        try:
            from database import exec_query
            exec_query("DELETE FROM soci WHERE id = ?", [socio_id])
            self._refresh_trash(tree)
            self._set_status_message(f"Socio {nominativo} eliminato definitivamente.")
            messagebox.showinfo("Eliminato", "Socio eliminato definitivamente.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")

    def _empty_trash(self, tree):
        """Permanently delete all members currently in trash."""
        items = tree.get_children()
        if not items:
            messagebox.showinfo("Svuota cestino", "Il cestino è già vuoto.")
            return

        count = len(items)
        if not messagebox.askyesno(
            "Svuota cestino",
            (
                "ATTENZIONE: Eliminare definitivamente tutti i soci nel cestino?\n"
                f"Totale soci da eliminare: {count}.\n\nQuesta operazione è IRREVERSIBILE!"
            ),
            icon='warning'
        ):
            return

        try:
            from database import exec_query
            exec_query("DELETE FROM soci WHERE deleted_at IS NOT NULL")
            self._refresh_trash(tree)
            self._set_status_message(f"Cestino svuotato: eliminati definitivamente {count} soci.")
            messagebox.showinfo("Svuota cestino", "Cestino svuotato correttamente.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")

    def _on_member_double_click(self, event):
        """Popola il form solo su doppio click su socio."""
        sel = self.tv_soci.selection()
        if not sel:
            return

        member_id = self._get_member_id_from_item(sel[0])
        if member_id is None:
            messagebox.showerror("Errore", "Impossibile determinare il socio selezionato.")
            return

        self.current_member_id = member_id
        self._load_member(self.current_member_id)
            
            # Check and warn about missing data
            # Temporarily disabled during data entry phase
            # if values[0] and "⚠" in str(values[0]):
            #     self._show_missing_data_warning(member_id)
    
    def _show_missing_data_warning(self, member_id):
        """Show warning message for missing data."""
        try:
            from database import fetch_one
            row = fetch_one(
                "SELECT matricola, email, telefono, indirizzo FROM soci WHERE id = ?",
                (member_id,)
            )
            if not row:
                return
            
            # Convert to dict for easier access
            data = dict(row)
            
            missing = []
            if not data.get('matricola', '') or str(data.get('matricola', '')).strip() == '':
                missing.append('• Matricola')
            if not data.get('email', '') or str(data.get('email', '')).strip() == '':
                missing.append('• Email')
            if not data.get('telefono', '') or str(data.get('telefono', '')).strip() == '':
                missing.append('• Telefono')
            if not data.get('indirizzo', '') or str(data.get('indirizzo', '')).strip() == '':
                missing.append('• Indirizzo di residenza')
            
            if missing:
                msg = "⚠ ATTENZIONE: Dati importanti mancanti\n\n" + "\n".join(missing)
                msg += "\n\nCompilare i campi mancanti per completare la scheda socio."
                messagebox.showwarning("Dati Mancanti", msg)
        except Exception as e:
            logger.error(f"Error showing missing data warning: {e}")
    
    def _load_member(self, socio_id: int):
        """Load member data into form."""
        try:
            from database import fetch_one, get_member_roles
            row = fetch_one("SELECT * FROM soci WHERE id = ?", [socio_id])
            if row:
                data = dict(row)
                try:
                    data['roles'] = get_member_roles(socio_id)
                except Exception as roles_exc:
                    logger.warning("Impossibile caricare i ruoli per il socio %s: %s", socio_id, roles_exc)
                self.form_member.set_values(data)
                self.panel_docs.set_socio(socio_id)
                self._refresh_docs_preview(socio_id)
                # Summary panel removed - update logic disabled
                # Update summary panel
                # try:
                #     mat = data.get('matricola') or ''
                #     att = data.get('attivo')
                #     voto = data.get('voto')
                #     tel = data.get('telefono') or ''
                #     if hasattr(self, 'summary_vars'):
                #         self.summary_vars['matricola'].set(str(mat))
                #         self.summary_vars['attivo'].set('Si' if str(att) in ('1', 'True', 'true') else 'No')
                #         self.summary_vars['voto'].set('Si' if str(voto) in ('1', 'True', 'true') else 'No')
                #         self.summary_vars['telefono'].set(str(tel))
                #         # Compute privacy status using DB helper
                #         try:
                #             from database import get_privacy_status
                #             ps = get_privacy_status(socio_id)
                #             signed = bool(ps.get('privacy_signed'))
                #             ok = bool(ps.get('privacy_ok'))
                #             if signed and ok:
                #                 self.summary_vars['privacy'].set('Si')
                #                 try:
                #                     self._privacy_label.config(foreground='green')
                #                 except Exception:
                #                     pass
                #             else:
                #                 self.summary_vars['privacy'].set('No')
                #                 try:
                #                     self._privacy_label.config(foreground='red')
                #                 except Exception:
                #                     pass
                #         except Exception:
                #             self.summary_vars['privacy'].set('')
                #             try:
                #                 self._privacy_label.config(foreground='black')
                #             except Exception:
                #                 pass
                # except Exception:
                #     pass
        except Exception as e:
            logger.error("Failed to load member: %s", e)
    
    def _save_member(self):
        """Save member data from form."""
        valid, error = self.form_member.validate()
        if not valid:
            messagebox.showerror("Validazione", error)
            return
        
        try:
            data = self.form_member.get_values()
            roles = data.pop('roles', [])
            from database import exec_query, set_member_roles, get_connection
            
            if self.current_member_id:
                # Update existing
                updates = []
                values = []
                for key, val in data.items():
                    if key != "id":
                        updates.append(f"{key} = ?")
                        values.append(val)
                values.append(self.current_member_id)
                
                sql = f"UPDATE soci SET {', '.join(updates)} WHERE id = ?"
                exec_query(sql, values)
                set_member_roles(self.current_member_id, roles)
                messagebox.showinfo("Salvataggio", "Socio modificato.")
            else:
                # Insert new
                cols = list(data.keys())
                placeholders = ["?" for _ in cols]
                sql = f"INSERT INTO soci ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                new_id = None
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, [data[col] for col in cols])
                    new_id = cursor.lastrowid
                if new_id is None:
                    raise RuntimeError("Impossibile determinare l'ID del nuovo socio")
                set_member_roles(int(new_id), roles)
                messagebox.showinfo("Salvataggio", "Socio creato.")
            
            # Apply filters instead of refresh to preserve filter state
            self._apply_filters()
            self.form_member.clear()
            self.current_member_id = None
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nel salvataggio: {e}")
    
    def _cancel_edit(self):
        """Cancel editing."""
        self.form_member.clear()
        self.tv_soci.selection_remove(self.tv_soci.selection())
        self.current_member_id = None
        self._set_status_message("Pronto")
        # Summary panel removed - no need to clear
        # if hasattr(self, '_clear_summary'):
        #     self._clear_summary()
    
    def _refresh_member_list(self):
        """Refresh member list from database."""
        try:
            from database import fetch_all

            # Cache dettagli socio per questa renderizzazione (evita query duplicate)
            self._member_detail_cache = {}
            
            # Clear treeview
            for item in self.tv_soci.get_children():
                self.tv_soci.delete(item)
            self.member_lookup = {}
            
            # Load members (exclude deleted)
            rows = fetch_all(
                f"SELECT {', '.join(self.COLONNE)} FROM soci WHERE deleted_at IS NULL ORDER BY nominativo"
            )
            
            for row in rows:
                # Check for missing critical data
                has_missing, warning_icon, missing_fields = self._check_missing_data(row)

                # Statuto-driven warnings (quota/voto/morosità)
                statuto_warnings = self._get_statuto_warnings(row)
                
                # Prepare display values
                display_row = self._strip_hidden_columns(self._format_member_row(row))
                total_warnings = len(missing_fields) + len(statuto_warnings)
                warning_label = f"⚠ {total_warnings}" if total_warnings else warning_icon
                display = (warning_label,) + display_row

                # Determine tags based on raw DB values (prefer explicit checks)
                tags = []
                att_idx = self.COLONNE.index('attivo')

                try:
                    att_val = row['attivo']
                except Exception:
                    att_val = row[att_idx] if len(row) > att_idx else None

                if str(att_val) in ('1', 'True', 'true', 1, True):
                    tags.append('active')
                else:
                    tags.append('inactive')
                
                if has_missing:
                    tags.append('missing_data')

                member_id = self._get_row_value(row, 'id')
                matricola_val = self._get_row_value(row, 'matricola')
                iid = self._register_member_identifier(matricola_val, member_id)
                self.tv_soci.insert("", "end", iid=iid, values=display, tags=tags)
        except Exception as e:
            logger.error("Failed to refresh member list: %s", e)
        finally:
            self._update_selection_summary()
    
    def _check_missing_data(self, row):
        """Check if member has missing critical data.
        
        Returns tuple: (has_missing, warning_icon, missing_fields_list)
        """
        missing = []
        
        try:
            # Check matricola
            matricola = row.get('matricola', '') if hasattr(row, 'get') else row[self.COLONNE.index('matricola')]
            if not matricola or str(matricola).strip() == '':
                missing.append('Matricola')
            
            # Check email  
            email = row.get('email', '') if hasattr(row, 'get') else row[self.COLONNE.index('email')]
            if not email or str(email).strip() == '':
                missing.append('Email')
            
            # Check privacy_signed
            privacy_signed = row.get('privacy_signed', '') if hasattr(row, 'get') else row[self.COLONNE.index('privacy_signed')]
            if not (str(privacy_signed) in ('1', 'True', 'true', 1, True)):
                missing.append('Privacy')
            
            # Need to fetch telefono and indirizzo from full record
            member_id = row.get('id', '') if hasattr(row, 'get') else row[0]
            if member_id:
                from database import fetch_one

                if not hasattr(self, '_member_detail_cache') or self._member_detail_cache is None:
                    self._member_detail_cache = {}

                full_row = self._member_detail_cache.get(member_id)
                if full_row is None:
                    full_row = fetch_one(
                        "SELECT telefono, indirizzo, data_iscrizione, socio FROM soci WHERE id = ?",
                        (member_id,)
                    )
                    self._member_detail_cache[member_id] = full_row

                if full_row:
                    telefono = full_row.get('telefono', '') if hasattr(full_row, 'get') else full_row[0]
                    indirizzo = full_row.get('indirizzo', '') if hasattr(full_row, 'get') else full_row[1]
                    
                    if not telefono or str(telefono).strip() == '':
                        missing.append('Telefono')
                    if not indirizzo or str(indirizzo).strip() == '':
                        missing.append('Indirizzo')
        except Exception as e:
            logger.debug(f"Error checking missing data: {e}")
        
        if missing:
            return True, "⚠", missing
        return False, "", []

    def _get_statuto_warnings(self, row):
        """Return a list of statuto-related warnings for a member.

        Nota: non influisce sul filtro "⚠ Dati mancanti" (che resta basato su _check_missing_data).
        """
        try:
            from utils import (
                to_bool01,
                normalize_q,
                statuto_diritti_sospesi,
                statuto_morosita_continua_anni,
                statuto_voto_coerente,
            )
        except Exception:
            return []

        warnings = []

        # Only apply to active members
        attivo_raw = self._get_row_value(row, 'attivo')
        if to_bool01(attivo_raw) != 1:
            return warnings

        socio_raw = self._get_row_value(row, 'socio')
        socio_norm = str(socio_raw).strip().upper() if socio_raw is not None else ""

        q0 = normalize_q(self._get_row_value(row, 'q0'))
        q1 = normalize_q(self._get_row_value(row, 'q1'))
        voto_raw = self._get_row_value(row, 'voto')

        # THR (Honor Roll) = soci onorari, quota esente
        if socio_norm != 'THR':
            if statuto_diritti_sospesi(q0=q0):
                warnings.append('Quota non in regola (Q0)')

            if statuto_morosita_continua_anni(q0=q0, q1=q1) >= 2:
                warnings.append('Morosità continuata 2 anni')

        # Voto: coerenza minima (3 mesi + quota)
        member_id = self._get_row_value(row, 'id')
        data_iscrizione = None
        if member_id:
            try:
                if not hasattr(self, '_member_detail_cache') or self._member_detail_cache is None:
                    self._member_detail_cache = {}

                detail = self._member_detail_cache.get(member_id)
                if detail is None:
                    from database import fetch_one
                    detail = fetch_one(
                        "SELECT telefono, indirizzo, data_iscrizione, socio FROM soci WHERE id = ?",
                        (member_id,)
                    )
                    self._member_detail_cache[member_id] = detail

                if detail:
                    data_iscrizione = detail.get('data_iscrizione') if hasattr(detail, 'get') else detail[2]
            except Exception:
                data_iscrizione = None

        # Per THR non imponiamo coerenza voto basata sulla quota (quota esente)
        if socio_norm != 'THR':
            if not statuto_voto_coerente(voto=voto_raw, data_iscrizione=data_iscrizione, q0=q0):
                warnings.append('Voto non coerente (3 mesi/Quota)')

        return warnings
    
    def _on_search_changed(self, *args):
        """Handle search field changes."""
        self._apply_filters()

    def _format_member_row(self, row):
        """Return a tuple for display where 'attivo' and 'voto' are 'Si'/'No'.

        `row` may be a sqlite3.Row or a sequence.
        """
        try:
            r = list(row)
        except Exception:
            r = list(tuple(row))

        # Normalize None/empty values to empty string for all columns
        for i, val in enumerate(r):
            if val is None:
                r[i] = ''
            else:
                # Keep string values trimmed
                try:
                    s = str(val)
                    if s.strip() == 'None':
                        r[i] = ''
                    else:
                        r[i] = s
                except Exception:
                    r[i] = val

        # attivo column — display 'Si' or 'No' (treat empty/null/non truthy as 'No')
        try:
            att_idx = self.COLONNE.index('attivo')
            att = r[att_idx]
            att_str = '' if att is None else str(att).strip().lower()
            if not att_str:
                r[att_idx] = 'No'
            else:
                r[att_idx] = 'Si' if att_str in ('1', 'true', 'si', 'sì', 'yes') else 'No'
        except Exception:
            pass

        # voto column — display 'Si' or 'No' (treat empty/null as 'No')
        try:
            voto_idx = self.COLONNE.index('voto')
            v = r[voto_idx]
            if v is None or str(v).strip() == '':
                r[voto_idx] = 'No'
            else:
                r[voto_idx] = 'Si' if str(v) in ('1', 'True', 'true') else 'No'
        except Exception:
            pass

        # privacy_signed column — display 'Si'/'No' when present (treat empty as 'No')
        try:
            priv_idx = self.COLONNE.index('privacy_signed')
            p = r[priv_idx]
            if p is None or str(p).strip() == '':
                r[priv_idx] = 'No'
            else:
                r[priv_idx] = 'Si' if str(p) in ('1', 'True', 'true') else 'No'
        except Exception:
            pass

        return tuple(r)

    def _strip_hidden_columns(self, formatted_row):
        """Remove non-visual columns (like ID) from the formatted row."""
        values = list(formatted_row)
        try:
            hidden_idx = self.COLONNE.index('id')
            if 0 <= hidden_idx < len(values):
                values.pop(hidden_idx)
        except ValueError:
            pass
        return tuple(values)

    def _get_row_value(self, row, column):
        """Return a column value from a sqlite row or plain tuple."""
        if hasattr(row, 'keys'):
            try:
                return row[column]
            except Exception:
                pass
        try:
            idx = self.COLONNE.index(column)
        except ValueError:
            return None
        try:
            return row[idx]
        except Exception:
            return None

    def _register_member_identifier(self, matricola, member_id):
        """Store the mapping matricola->member_id and return the tree iid."""
        if not hasattr(self, 'member_lookup') or self.member_lookup is None:
            self.member_lookup = {}

        base_key = self._normalize_matricola_key(matricola)
        if not base_key:
            base_key = f"id-{member_id}" if member_id is not None else f"row-{len(self.member_lookup) + 1}"

        iid = base_key
        counter = 2
        while iid in self.member_lookup:
            iid = f"{base_key}#{counter}"
            counter += 1

        self.member_lookup[iid] = member_id
        return iid

    @staticmethod
    def _normalize_matricola_key(value):
        if value is None:
            return ""
        return str(value).strip()
    
    def _reset_search(self):
        """Reset search field and show all members."""
        self.search_var.set("")
        self._refresh_member_list()
    
    def _apply_filters(self):
        """Apply status filters."""
        status_filter = self.status_filter_var.get()
        missing_data_filter = self.missing_data_filter_var.get() if hasattr(self, 'missing_data_filter_var') else "tutti"
        keyword = self.search_var.get().strip()
        
        # Clear treeview
        for item in self.tv_soci.get_children():
            self.tv_soci.delete(item)
        self.member_lookup = {}
        
        try:
            from database import fetch_all

            # Cache dettagli socio per questa renderizzazione (evita query duplicate)
            self._member_detail_cache = {}
            
            # Build SQL with filters
            sql = "SELECT " + ", ".join(self.COLONNE) + " FROM soci WHERE deleted_at IS NULL"
            params = []
            
            # Add keyword filter
            if keyword:
                sql += " AND (nome LIKE ? OR cognome LIKE ? OR nominativo LIKE ? OR matricola LIKE ? OR email LIKE ?)"
                pattern = f"%{keyword}%"
                params.extend([pattern, pattern, pattern, pattern, pattern])
            
            # use LOWER so accented characters like "sì" compare reliably even without full UTF-8 upper support
            attivo_truthy = "LOWER(TRIM(COALESCE(CAST(attivo AS TEXT), ''))) IN ('1','true','si','sì','yes')"
            # Add status filter
            if status_filter == "active":
                sql += f" AND {attivo_truthy}"
            elif status_filter == "inactive":
                sql += f" AND NOT {attivo_truthy}"
            
            sql += " ORDER BY nominativo"
            
            rows = fetch_all(sql, tuple(params))
            for row in rows:
                # Check for missing data
                has_missing, warning_icon, missing_fields = self._check_missing_data(row)

                statuto_warnings = self._get_statuto_warnings(row)
                
                # Apply missing data filter
                if missing_data_filter == "missing" and not has_missing:
                    continue
                elif missing_data_filter == "complete" and has_missing:
                    continue
                
                # Prepare display values
                display_row = self._strip_hidden_columns(self._format_member_row(row))
                total_warnings = len(missing_fields) + len(statuto_warnings)
                warning_label = f"⚠ {total_warnings}" if total_warnings else warning_icon
                display = (warning_label,) + display_row
                
                # Determine tags
                tags = []
                att_idx = self.COLONNE.index('attivo')
                raw_att = row.get('attivo') if hasattr(row, 'get') else row[att_idx]
                att_str = str(raw_att).strip().lower() if raw_att is not None else ''
                
                if att_str in ('1', 'true', 'si', 'sì', 'yes'):
                    tags.append('active')
                else:
                    tags.append('inactive')
                
                if has_missing:
                    tags.append('missing_data')
                
                row_id = None
                try:
                    row_id = row['id'] if hasattr(row, 'keys') else row[0]
                except Exception:
                    row_id = None
                member_id = self._get_row_value(row, 'id')
                matricola_val = self._get_row_value(row, 'matricola')
                iid = self._register_member_identifier(matricola_val, member_id)
                self.tv_soci.insert("", "end", iid=iid, values=display, tags=tags)
            self._update_selection_summary()
        except Exception as e:
            logger.error("Filter failed: %s", e)
    
    def _open_documentale(self):
        """Open document management dialog for selected member."""
        selection = self.tv_soci.selection()
        if not selection:
            messagebox.showwarning("Selezione", "Selezionare un socio")
            return

        member_id = self._get_member_id_from_item(selection[0])
        if member_id is None:
            messagebox.showerror("Documenti", "Impossibile determinare l'ID del socio selezionato.")
            return

        self._navigate_to_member_documents(member_id)

    def _navigate_to_member_documents(self, member_id: int):
        """Navigate to Documenti → Documenti soci and pre-filter the panel to the given socio."""
        try:
            panel = getattr(self, "panel_docs", None)
            if panel is not None and hasattr(panel, "set_socio"):
                try:
                    panel.set_socio(int(member_id))
                except Exception:
                    pass

            self._select_notebook_tab_by_text(self.notebook, "Documenti")
            docs_nb = getattr(self, "docs_notebook", None)
            if isinstance(docs_nb, ttk.Notebook):
                self._select_notebook_tab_by_text(docs_nb, "Documenti soci")
        except Exception as e:
            messagebox.showerror("Documenti", f"Errore nell'apertura dei documenti: {e}")
            logger.error("Failed to navigate to documents: %s", e)

    def _get_target_member_id_for_actions(self) -> int | None:
        """Return selected socio id (prefer selection, fallback to current_member_id)."""
        try:
            selection = self.tv_soci.selection()
            if len(selection) == 1:
                member_id = self._get_member_id_from_item(selection[0])
                if member_id is not None:
                    return int(member_id)
        except Exception:
            pass
        current_member_id = getattr(self, "current_member_id", None)
        if current_member_id is not None:
            try:
                return int(current_member_id)
            except Exception:
                return None
        return None

    def _socio_add_document(self):
        member_id = self._get_target_member_id_for_actions()
        if not member_id:
            messagebox.showwarning("Documenti", "Selezionare un socio")
            return
        self._navigate_to_member_documents(member_id)
        panel = getattr(self, "panel_docs", None)
        if panel is None or not hasattr(panel, "add_document_for_socio"):
            messagebox.showerror("Documenti", "Pannello documenti non disponibile")
            return
        panel.add_document_for_socio(int(member_id))

    def _socio_upload_privacy(self):
        member_id = self._get_target_member_id_for_actions()
        if not member_id:
            messagebox.showwarning("Documenti", "Selezionare un socio")
            return
        self._navigate_to_member_documents(member_id)
        panel = getattr(self, "panel_docs", None)
        if panel is None or not hasattr(panel, "upload_privacy_for_socio"):
            messagebox.showerror("Documenti", "Pannello documenti non disponibile")
            return
        panel.upload_privacy_for_socio(int(member_id))

    def _socio_open_member_folder(self):
        member_id = self._get_target_member_id_for_actions()
        if not member_id:
            messagebox.showwarning("Documenti", "Selezionare un socio")
            return
        self._navigate_to_member_documents(member_id)
        panel = getattr(self, "panel_docs", None)
        if panel is None or not hasattr(panel, "open_member_folder_for_socio"):
            messagebox.showerror("Documenti", "Pannello documenti non disponibile")
            return
        panel.open_member_folder_for_socio(int(member_id))

    @staticmethod
    def _format_member_display_name(member: Mapping[str, object] | None) -> str:
        """Return a readable label for a socio using nominativo or nome+cognome."""
        if not member:
            return "Socio"
        nominativo = str(member.get("nominativo") or "").strip()
        if nominativo and nominativo != "-":
            return nominativo
        nome = str(member.get("nome") or "").strip()
        cognome = str(member.get("cognome") or "").strip()
        full = " ".join(part for part in (nome, cognome) if part)
        if full:
            return full
        member_id = member.get("id")
        return f"Socio #{member_id}" if member_id else "Socio"
    
    def _save_section_config(self):
        """Save section configuration."""
        try:
            from config_manager import save_config
            cfg = self.panel_section.get_values()
            save_config(cfg)
            self._update_title()
            messagebox.showinfo("Configurazione", "Configurazione sezione salvata.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")
    
    def _show_section_config_dialog(self):
        """Show section configuration dialog."""
        win = tk.Toplevel(self.root)
        win.title("Configurazione Sezione")
        win.geometry("600x500")
        win.transient(self.root)
        win.grab_set()
        
        # Content frame
        content_frame = ttk.Frame(win)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        from .panels import SectionInfoPanel
        panel = SectionInfoPanel(content_frame)
        panel.pack(fill=tk.BOTH, expand=True)
        
        # Load current config
        panel.set_values(self.cfg)
        
        # Buttons frame
        button_frame = ttk.Frame(win)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save_and_close():
            try:
                from config_manager import save_config
                cfg = panel.get_values()
                save_config(cfg)
                self.cfg = cfg
                self.panel_section.set_values(cfg)
                self._update_title()
                win.destroy()
                messagebox.showinfo("Configurazione", "Configurazione sezione salvata.")
            except Exception as e:
                messagebox.showerror("Errore", f"Errore: {e}")
        
        ttk.Button(button_frame, text="Salva", command=save_and_close).pack(side=tk.RIGHT, padx=2)
        ttk.Button(button_frame, text="Annulla", command=win.destroy).pack(side=tk.RIGHT, padx=2)
    
    def _reload_section_config(self):
        """Reload section configuration (discard changes)."""
        self.panel_section.set_values(self.cfg)
    
    def _show_event_log(self):
        """Show event log dialog."""
        win = tk.Toplevel(self.root)
        win.title("Log eventi")
        win.geometry("800x600")
        
        from .panels import EventLogPanel
        panel = EventLogPanel(win)
        panel.pack(fill=tk.BOTH, expand=True)
        panel.refresh()
    
    def _show_import_wizard(self):
        """Show unified CSV import wizard"""
        try:
            UnifiedImportWizard(
                self.root,
                on_soci_complete=self._on_import_complete,
                on_magazzino_complete=self._on_magazzino_import_complete,
            )
        except Exception as exc:
            messagebox.showerror("Import CSV", f"Impossibile aprire il wizard:\n{exc}")
    
    def _show_templates_dialog(self):
        """Show templates management dialog."""
        try:
            from v4_ui.templates_dialog import TemplatesDialog
            TemplatesDialog(self.root)
        except Exception as e:
            logger.error(f"Failed to show templates dialog: {e}")
            messagebox.showerror("Errore", f"Errore apertura gestione template: {e}")

    def _on_root_close(self):
        """Handle main window close: destroy any Toplevel windows then root."""
        try:
            # Destroy any child Toplevel windows to ensure clean exit
            for w in list(self.root.winfo_children()):
                try:
                    if isinstance(w, tk.Toplevel):
                        w.destroy()
                except Exception:
                    pass
        finally:
            try:
                self.root.destroy()
            except Exception:
                try:
                    self.root.quit()
                except Exception:
                    pass
    
    def _on_import_complete(self, count):
        """Handle import completion"""
        self._refresh_member_list()
        self._set_status_message(f"{count} soci importati con successo")
    
    def _on_magazzino_import_complete(self, *counts):
        """Refresh magazzino after import completion."""
        total = 0
        for value in counts:
            try:
                total += int(value)
            except (TypeError, ValueError):
                continue
        if total <= 0:
            message = "Import magazzino completato"
        else:
            message = f"Import magazzino completato: {total} oggetti elaborati"
        panel = getattr(self, "magazzino_panel", None)
        if panel is not None:
            try:
                panel.refresh_list()
            except Exception as exc:
                logger.error("Errore aggiornando il magazzino dopo import: %s", exc)
        self._set_status_message(message)

    def _show_export_dialog(self):
        """Show the unified export wizard."""
        try:
            UnifiedExportWizard(self.root)
        except Exception as exc:
            logger.error("Errore apertura export: %s", exc)

    def _get_matricola_to_name_mapping(self) -> dict[str, str]:
        """Get a mapping from matricola to full name for quick lookup."""
        try:
            from database import get_connection
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT matricola, nominativo FROM soci WHERE matricola IS NOT NULL AND nominativo IS NOT NULL")
                rows = cursor.fetchall()
                return {row[0]: row[1] for row in rows}
        except Exception as exc:
            logger.error("Errore caricamento mapping matricola-nome: %s", exc)
            return {}
    
    def _show_duplicates_dialog(self):
        """Show duplicates detection and merge dialog"""
        try:
            from v4_ui.duplicates_dialog import DuplicatesDialog
            DuplicatesDialog(self.root)
            # Refresh member list after potential merge
            self._refresh_member_list()
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")
    
    def _show_batch_edit_dialog(self):
        """Open the batch edit dialog for the selected members."""
        selection = self.tv_soci.selection()
        if not selection:
            messagebox.showinfo("Modifica campi", "Seleziona almeno un socio dall'elenco.")
            return

        members = []
        for item_id in selection:
            item = self.tv_soci.item(item_id)
            values = list(item.get("values", []))
            if not values:
                continue

            member_id = self._get_member_id_from_item(item_id)
            if member_id is None:
                continue

            member = {
                "id": member_id,
                "nominativo": self._get_display_value(values, "nominativo"),
                "nome": self._get_display_value(values, "nome"),
                "cognome": self._get_display_value(values, "cognome"),
                "matricola": self._get_display_value(values, "matricola"),
            }
            members.append(member)

        if not members:
            messagebox.showwarning("Modifica campi", "Impossibile leggere i dati selezionati.")
            return

        try:
            from v4_ui.batch_edit_dialog import BatchFieldEditDialog

            BatchFieldEditDialog(self.root, members, on_complete=self._on_batch_edit_complete)
        except Exception as exc:
            logger.error("Errore apertura dialog Modifica campi: %s", exc)
            messagebox.showerror("Errore", f"Errore apertura dialogo:\n{exc}")

    def _on_batch_edit_complete(self, count: int):
        """Refresh the UI after a batch edit operation."""
        try:
            self._refresh_member_list()
            self._set_status_message(f"Campi aggiornati per {count} socio/i")
        except Exception as exc:
            logger.error("Errore post batch edit: %s", exc)

    def _show_update_status_wizard(self):
        """Show wizard to update member status (Voto, Q0, Q1, Q2)"""
        try:
            from update_status_wizard import UpdateStatusWizard
            UpdateStatusWizard(self.root, on_complete_callback=lambda count: self._refresh_member_list())
        except Exception as e:
            logger.error(f"Error showing update status wizard: {e}")
            messagebox.showerror("Errore", f"Errore apertura wizard: {e}")
    

