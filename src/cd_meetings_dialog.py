# -*- coding: utf-8 -*-
"""
CD Meetings UI Dialogs for GLR Gestione Locale Radioamatori
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import logging
from datetime import datetime
import json
import urllib.parse
import webbrowser
import os
import subprocess

logger = logging.getLogger("librosoci")

class MeetingDialog:
    """Dialog for adding/editing CD meetings with email invitation"""
    
    # Email templates
    TEMPLATES = {
        "convocazione_cd": """Gentili Consiglieri,

siete convocati per la riunione del Consiglio Direttivo che si terrà in data {data} alle ore {ora} presso {luogo}.

Ordine del giorno:
{odg}

Cordiali saluti,
Il Presidente""",
        "comunicazione_generale": """Cari Soci,

vi informiamo che {messaggio}

Per ulteriori informazioni potete contattarci rispondendo a questa email.

Cordiali saluti,
La Segreteria""",
        "libero": ""
    }

    def _load_custom_email_templates(self) -> dict[str, str]:
        """Load custom email templates from config.

        Supported formats in config (best-effort):
        - {"email_templates": {"Nome": "Testo...", ...}}
        - {"email_templates": [{"name": "Nome", "body": "Testo..."}, ...]}
        """
        try:
            from config_manager import load_config

            cfg = load_config() or {}
            raw = cfg.get("email_templates")
            out: dict[str, str] = {}

            if isinstance(raw, dict):
                for name, body in raw.items():
                    if not isinstance(name, str):
                        continue
                    if not isinstance(body, str):
                        continue
                    n = name.strip()
                    if not n:
                        continue
                    out[n] = body
                return out

            if isinstance(raw, list):
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name")
                    body = item.get("body")
                    if not isinstance(name, str) or not isinstance(body, str):
                        continue
                    n = name.strip()
                    if not n:
                        continue
                    out[n] = body
                return out
        except Exception:
            return {}

        return {}

    class EmailTemplatesWizard:
        """Wizard/dialog to manage custom email templates stored in config ('email_templates')."""

        RESERVED_DEFAULT_NAMES = {
            "Testo libero",
            "Convocazione CD",
            "Comunicazione Generale",
        }

        def __init__(self, parent, get_defaults, on_saved=None):
            self.parent = parent
            self.get_defaults = get_defaults
            self.on_saved = on_saved

            self.win = tk.Toplevel(parent)
            self.win.title("Wizard template email")
            self.win.geometry("760x520")
            self.win.transient(parent)
            self.win.grab_set()

            self.custom: dict[str, str] = self._load_custom_templates_dict()
            defaults = (self.get_defaults() or {}) if callable(self.get_defaults) else {}
            self.defaults: dict[str, str] = defaults if isinstance(defaults, dict) else {}

            self._editing_original_name: str | None = None

            self._build_ui()
            self._refresh_listbox()

        def _load_custom_templates_dict(self) -> dict[str, str]:
            try:
                from config_manager import load_config

                cfg = load_config() or {}
                raw = cfg.get("email_templates")
                out: dict[str, str] = {}

                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if isinstance(k, str) and isinstance(v, str) and k.strip():
                            out[k.strip()] = v
                    return out

                if isinstance(raw, list):
                    for item in raw:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("name")
                        body = item.get("body")
                        if isinstance(name, str) and isinstance(body, str) and name.strip():
                            out[name.strip()] = body
                    return out
            except Exception:
                return {}

            return {}

        def _save_custom_templates_dict(self, data: dict[str, str]) -> bool:
            try:
                from config_manager import load_config, save_config

                cfg = load_config() or {}
                cfg["email_templates"] = dict(sorted((data or {}).items(), key=lambda kv: (kv[0] or "").strip().lower()))
                save_config(cfg)
                return True
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile salvare la configurazione:\n{e}", parent=self.win)
                return False

        def _build_ui(self) -> None:
            top = ttk.Frame(self.win, padding=8)
            top.pack(fill=tk.BOTH, expand=True)

            header = ttk.Label(top, text="Template personalizzati (salvati in configurazione)", font=("Arial", 10, "bold"))
            header.pack(anchor="w", pady=(0, 6))

            self.manage_frame = ttk.Frame(top)
            self.manage_frame.pack(fill=tk.BOTH, expand=True)

            left = ttk.Frame(self.manage_frame)
            left.pack(side=tk.LEFT, fill=tk.Y)

            ttk.Label(left, text="I tuoi template:").pack(anchor="w")
            self.listbox = tk.Listbox(left, height=16, width=30)
            self.listbox.pack(fill=tk.Y, expand=False, pady=(4, 8))
            self.listbox.bind("<<ListboxSelect>>", lambda _e: self._update_preview())

            btns = ttk.Frame(left)
            btns.pack(fill=tk.X)
            ttk.Button(btns, text="Nuovo...", command=self._new_from_base).pack(fill=tk.X, pady=2)
            ttk.Button(btns, text="Modifica...", command=self._edit_selected).pack(fill=tk.X, pady=2)
            ttk.Button(btns, text="Elimina", command=self._delete_selected).pack(fill=tk.X, pady=2)

            right = ttk.Frame(self.manage_frame)
            right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

            ttk.Label(right, text="Crea da base:").pack(anchor="w")
            self.base_var = tk.StringVar(value="Vuoto")
            self.base_combo = ttk.Combobox(right, textvariable=self.base_var, state="readonly", width=40)
            self.base_combo.pack(anchor="w", pady=(4, 6))
            self._refresh_base_combo_values()
            ttk.Button(right, text="Crea da questa base", command=self._new_from_base).pack(anchor="w", pady=(0, 10))

            ttk.Label(right, text="Anteprima:").pack(anchor="w")
            self.preview = scrolledtext.ScrolledText(right, height=14, wrap=tk.WORD)
            self.preview.pack(fill=tk.BOTH, expand=True)
            self.preview.configure(state="disabled")

            footer = ttk.Frame(top)
            footer.pack(fill=tk.X, pady=(8, 0))
            ttk.Button(footer, text="Chiudi", command=self.win.destroy).pack(side=tk.RIGHT)

            # Edit frame (hidden by default)
            self.edit_frame = ttk.Frame(top)

            row1 = ttk.Frame(self.edit_frame)
            row1.pack(fill=tk.X)
            ttk.Label(row1, text="Nome template:").pack(side=tk.LEFT)
            self.name_entry = ttk.Entry(row1, width=50)
            self.name_entry.pack(side=tk.LEFT, padx=8)

            hint = "Placeholder disponibili: {data} {ora} {luogo} {odg} {messaggio}"
            ttk.Label(self.edit_frame, text=hint, foreground="gray").pack(anchor="w", pady=(6, 2))

            ttk.Label(self.edit_frame, text="Corpo template:").pack(anchor="w")
            self.body_text = scrolledtext.ScrolledText(self.edit_frame, height=14, wrap=tk.WORD)
            self.body_text.pack(fill=tk.BOTH, expand=True)

            edit_footer = ttk.Frame(self.edit_frame)
            edit_footer.pack(fill=tk.X, pady=(8, 0))
            ttk.Button(edit_footer, text="Annulla", command=self._back_to_manage).pack(side=tk.RIGHT, padx=5)
            ttk.Button(edit_footer, text="Salva", command=self._save_current).pack(side=tk.RIGHT)

        def _refresh_base_combo_values(self) -> None:
            values = ["Vuoto"]
            for k in ("Convocazione CD", "Comunicazione Generale"):
                if k in self.defaults:
                    values.append(k)
            self.base_combo["values"] = tuple(values)
            if self.base_var.get() not in values:
                self.base_var.set(values[0] if values else "Vuoto")

        def _refresh_listbox(self) -> None:
            self.listbox.delete(0, tk.END)
            for name in sorted(self.custom.keys(), key=lambda s: (s or "").strip().lower()):
                self.listbox.insert(tk.END, name)
            self._update_preview()

        def _get_selected_name(self) -> str | None:
            try:
                sel = self.listbox.curselection()
                if not sel:
                    return None
                return self.listbox.get(sel[0])
            except Exception:
                return None

        def _update_preview(self) -> None:
            name = self._get_selected_name()
            text = ""
            if name and name in self.custom:
                text = self.custom.get(name) or ""
            self.preview.configure(state="normal")
            self.preview.delete("1.0", tk.END)
            self.preview.insert("1.0", text)
            self.preview.configure(state="disabled")

        def _new_from_base(self) -> None:
            base_name = (self.base_var.get() or "Vuoto").strip()
            body = ""
            if base_name and base_name != "Vuoto":
                body = self.defaults.get(base_name, "")
            self._open_edit(name="", body=body, original=None)

        def _edit_selected(self) -> None:
            name = self._get_selected_name()
            if not name:
                messagebox.showinfo("Info", "Seleziona un template da modificare.", parent=self.win)
                return
            self._open_edit(name=name, body=self.custom.get(name, ""), original=name)

        def _delete_selected(self) -> None:
            name = self._get_selected_name()
            if not name:
                messagebox.showinfo("Info", "Seleziona un template da eliminare.", parent=self.win)
                return
            ok = messagebox.askyesno("Conferma", f"Eliminare il template '{name}'?", parent=self.win)
            if not ok:
                return
            self.custom.pop(name, None)
            if self._save_custom_templates_dict(self.custom):
                self._refresh_listbox()
                if callable(self.on_saved):
                    self.on_saved()

        def _open_edit(self, name: str, body: str, original: str | None) -> None:
            self._editing_original_name = original
            self.manage_frame.pack_forget()
            self.edit_frame.pack(fill=tk.BOTH, expand=True)

            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, name or "")
            self.body_text.delete("1.0", tk.END)
            self.body_text.insert("1.0", body or "")

        def _back_to_manage(self) -> None:
            self.edit_frame.pack_forget()
            self.manage_frame.pack(fill=tk.BOTH, expand=True)
            self._editing_original_name = None
            self._refresh_listbox()

        def _save_current(self) -> None:
            name = (self.name_entry.get() or "").strip()
            body = (self.body_text.get("1.0", tk.END) or "").rstrip()

            if not name:
                messagebox.showwarning("Validazione", "Inserire un nome per il template.", parent=self.win)
                return
            if name in self.RESERVED_DEFAULT_NAMES:
                messagebox.showwarning(
                    "Validazione",
                    "Nome non valido: coincide con un template di sistema. Scegli un nome diverso.",
                    parent=self.win,
                )
                return

            if self._editing_original_name and self._editing_original_name != name:
                self.custom.pop(self._editing_original_name, None)

            if name in self.custom and (self._editing_original_name != name):
                ok = messagebox.askyesno("Conferma", f"Il template '{name}' esiste già. Sovrascrivere?", parent=self.win)
                if not ok:
                    return

            self.custom[name] = body
            if self._save_custom_templates_dict(self.custom):
                if callable(self.on_saved):
                    self.on_saved()
                self._back_to_manage()

    def _build_template_text_map(self) -> dict[str, str]:
        base: dict[str, str] = {
            "Testo libero": self.TEMPLATES.get("libero", ""),
            "Convocazione CD": self.TEMPLATES.get("convocazione_cd", ""),
            "Comunicazione Generale": self.TEMPLATES.get("comunicazione_generale", ""),
        }

        custom = self._load_custom_email_templates()
        for name in sorted((custom or {}).keys(), key=lambda s: (s or "").strip().lower()):
            body = (custom or {}).get(name)
            n = (name or "").strip()
            if not n:
                continue
            if n in base:
                continue
            base[n] = body or ""

        return base

    def _refresh_template_combo(self, keep_selection: bool = True) -> None:
        try:
            current = self.template_var.get() if (keep_selection and hasattr(self, "template_var")) else None
            self._template_text_by_name = self._build_template_text_map()
            if hasattr(self, "template_combo"):
                self.template_combo["values"] = tuple(self._template_text_by_name.keys())

            if current and current in self._template_text_by_name:
                self.template_var.set(current)
            else:
                # Keep default behavior: new meeting -> Convocazione CD, edit -> Testo libero
                default_name = "Testo libero" if self.meeting_id else "Convocazione CD"
                if default_name in self._template_text_by_name:
                    self.template_var.set(default_name)
                elif self._template_text_by_name:
                    self.template_var.set(next(iter(self._template_text_by_name.keys())))

        except Exception:
            pass

    def _open_templates_wizard(self) -> None:
        try:
            self.EmailTemplatesWizard(
                parent=self.dialog,
                get_defaults=lambda: {
                    "Convocazione CD": self.TEMPLATES.get("convocazione_cd", ""),
                    "Comunicazione Generale": self.TEMPLATES.get("comunicazione_generale", ""),
                },
                on_saved=lambda: self._refresh_template_combo(keep_selection=True),
            )
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile aprire il wizard template:\n{e}", parent=self.dialog)

    def _is_meta_tipo_assemblea(self) -> bool:
        try:
            tipo = (self.meta_tipo_var.get() or "").strip().lower()
            return "assemblea" in tipo
        except Exception:
            return False

    def _update_presenze_visibility(self):
        """Presenze/Quorum: visible only in edit AND for Assemblea soci."""
        should_show = bool(self.meeting_id) and self._is_meta_tipo_assemblea()

        try:
            if should_show:
                self.presenze_frame.grid()
            else:
                self.presenze_frame.grid_remove()
        except Exception:
            pass

        # Even if hidden, keep widgets disabled to prevent accidental edits.
        self._set_presenze_enabled(enabled=should_show)
    
    def __init__(self, parent, meeting_id=None):
        """
        Initialize meeting dialog.
        
        Args:
            parent: Parent window
            meeting_id: If provided, edit existing meeting; otherwise create new
        """
        self.parent = parent
        self.meeting_id = meeting_id
        self.result = None
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Nuova riunione CD" if not meeting_id else "Modifica riunione CD")
        # More compact default size; content remains scrollable.
        self.dialog.geometry("760x990")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Main frame with scrollbar
        canvas = tk.Canvas(self.dialog)
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        main_frame = ttk.Frame(canvas)
        
        main_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        scrollbar.pack(side="right", fill="y")
        
        # Tipo riunione (solo per nuove riunioni)
        row = 0
        if not meeting_id:
            ttk.Label(main_frame, text="Tipo riunione:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
            self.tipo_riunione_var = tk.StringVar(value="futura")
            tipo_frame = ttk.Frame(main_frame)
            tipo_frame.grid(row=row, column=1, columnspan=3, sticky="w", padx=5, pady=5)
            ttk.Radiobutton(tipo_frame, text="Riunione futura (con convocazione email)", variable=self.tipo_riunione_var, value="futura", command=self._toggle_tipo_riunione).pack(side=tk.LEFT, padx=5)
            ttk.Radiobutton(tipo_frame, text="Riunione già svolta (solo archiviazione)", variable=self.tipo_riunione_var, value="passata", command=self._toggle_tipo_riunione).pack(side=tk.LEFT, padx=5)
            row += 1
        else:
            # Per riunioni esistenti, lo determiniamo da DB in _load_meeting (fallback: passata)
            self.tipo_riunione_var = tk.StringVar(value="passata")
        
        # Numero CD
        ttk.Label(main_frame, text="Numero CD:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.entry_numero_cd = ttk.Entry(main_frame, width=10)
        self.entry_numero_cd.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        
        # Date
        row += 1
        ttk.Label(main_frame, text="Data:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.entry_date = ttk.Entry(main_frame, width=15)
        self.entry_date.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        self.entry_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        ttk.Button(main_frame, text="Oggi", command=self._set_today).grid(row=row, column=2, sticky="w", padx=5, pady=5)
        
        # Oggetto
        row += 1
        ttk.Label(main_frame, text="Oggetto:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.entry_oggetto = ttk.Entry(main_frame, width=60)
        self.entry_oggetto.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        # Metadati riunione
        row += 1
        self.meta_frame = ttk.LabelFrame(main_frame, text="Metadati riunione", padding=4)
        self.meta_frame.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
        self.meta_frame.columnconfigure(1, weight=1)
        self.meta_frame.columnconfigure(3, weight=1)

        ttk.Label(self.meta_frame, text="Tipo:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.meta_tipo_var = tk.StringVar(value="Riunione del CD")
        self.combo_meta_tipo = ttk.Combobox(
            self.meta_frame,
            textvariable=self.meta_tipo_var,
            state="readonly",
            width=28,
            values=(
                "Riunione del CD",
                "Riunione del CD straordinario",
                "Assemblea ordinaria dei soci",
                "Assemblea straordinaria dei soci",
            ),
        )
        self.combo_meta_tipo.grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        self.combo_meta_tipo.bind("<<ComboboxSelected>>", lambda _e: self._on_meta_tipo_changed())

        ttk.Label(self.meta_frame, text="Modalità:").grid(row=0, column=2, sticky="w", padx=5, pady=3)
        self.meta_modalita_var = tk.StringVar(value="presenza")
        self.combo_meta_modalita = ttk.Combobox(
            self.meta_frame,
            textvariable=self.meta_modalita_var,
            state="readonly",
            width=18,
            values=("presenza", "online", "ibrida"),
        )
        self.combo_meta_modalita.grid(row=0, column=3, sticky="ew", padx=5, pady=3)

        ttk.Label(self.meta_frame, text="Luogo / Link:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.entry_meta_luogo = ttk.Entry(self.meta_frame, width=60)
        self.entry_meta_luogo.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=3)

        ttk.Label(self.meta_frame, text="Ora inizio:").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.entry_meta_ora_inizio = ttk.Entry(self.meta_frame, width=10)
        self.entry_meta_ora_inizio.grid(row=2, column=1, sticky="w", padx=5, pady=3)
        ttk.Label(self.meta_frame, text="Ora fine:").grid(row=2, column=2, sticky="w", padx=5, pady=3)
        self.entry_meta_ora_fine = ttk.Entry(self.meta_frame, width=10)
        self.entry_meta_ora_fine.grid(row=2, column=3, sticky="w", padx=5, pady=3)

        # Presenze / Quorum
        row += 1
        self.presenze_frame = ttk.LabelFrame(main_frame, text="Presenze / Quorum", padding=4)
        self.presenze_frame.grid(row=row, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
        self.presenze_frame.columnconfigure(1, weight=1)
        self.presenze_frame.columnconfigure(3, weight=1)

        self.label_presenze_hint = ttk.Label(self.presenze_frame, text="", foreground="gray")
        self.label_presenze_hint.grid(row=0, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))

        self.label_presenze_hint2 = ttk.Label(
            self.presenze_frame,
            text="Deleghe: solo per Assemblee soci.",
            foreground="gray",
        )
        self.label_presenze_hint2.grid(row=0, column=3, sticky="e", padx=5, pady=(0, 5))

        ttk.Label(self.presenze_frame, text="Aventi diritto:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.entry_aventi_diritto = ttk.Entry(self.presenze_frame, width=8)
        self.entry_aventi_diritto.grid(row=1, column=1, sticky="w", padx=5, pady=3)

        ttk.Label(self.presenze_frame, text="Presenti:").grid(row=1, column=2, sticky="w", padx=5, pady=3)
        self.entry_presenti = ttk.Entry(self.presenze_frame, width=8)
        self.entry_presenti.grid(row=1, column=3, sticky="w", padx=5, pady=3)

        self.label_deleghe = ttk.Label(self.presenze_frame, text="Deleghe:")
        self.label_deleghe.grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.entry_deleghe = ttk.Entry(self.presenze_frame, width=8)
        self.entry_deleghe.grid(row=2, column=1, sticky="w", padx=5, pady=3)

        ttk.Label(self.presenze_frame, text="Quorum richiesto:").grid(row=2, column=2, sticky="w", padx=5, pady=3)
        self.entry_quorum = ttk.Entry(self.presenze_frame, width=8)
        self.entry_quorum.grid(row=2, column=3, sticky="w", padx=5, pady=3)

        self.label_quorum_esito = ttk.Label(self.presenze_frame, text="", foreground="gray")
        self.label_quorum_esito.grid(row=3, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))

        ttk.Label(self.presenze_frame, text="Note presenze/deleghe (testo libero):").grid(row=4, column=0, columnspan=4, sticky="w", padx=5, pady=(2, 2))
        self.text_presenze = scrolledtext.ScrolledText(self.presenze_frame, height=3, wrap=tk.WORD)
        self.text_presenze.grid(row=5, column=0, columnspan=4, sticky="nsew", padx=5, pady=(0, 5))

        self.presenze_frame.rowconfigure(5, weight=1)

        for ent in (self.entry_aventi_diritto, self.entry_presenti, self.entry_deleghe, self.entry_quorum):
            ent.bind("<KeyRelease>", lambda _e: self._update_quorum_label())
        
        # Selezione soci
        row += 1
        ttk.Label(main_frame, text="Destinatari email:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.destinatari_var = tk.StringVar(value="cd")
        self.dest_frame = ttk.Frame(main_frame)
        self.dest_frame.grid(row=row, column=1, columnspan=3, sticky="w", padx=5, pady=5)
        ttk.Radiobutton(self.dest_frame, text="Soci (tutti attivi)", variable=self.destinatari_var, value="soci", command=self._update_recipient_count).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(self.dest_frame, text="Solo CD", variable=self.destinatari_var, value="cd", command=self._update_recipient_count).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(self.dest_frame, text="CD + CP", variable=self.destinatari_var, value="cd_cp", command=self._update_recipient_count).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.dest_frame, text="Anteprima", command=self._show_recipients).pack(side=tk.LEFT, padx=10)
        self.label_count = ttk.Label(self.dest_frame, text="", foreground="blue")
        self.label_count.pack(side=tk.LEFT, padx=5)
        
        # Template selector
        row += 1
        ttk.Label(main_frame, text="Corpo email:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="nw", padx=5, pady=5)
        self.template_frame = ttk.Frame(main_frame)
        self.template_frame.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(self.template_frame, text="Template:").pack(side=tk.LEFT, padx=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(self.template_frame, textvariable=self.template_var, width=30, state="readonly")

        self._template_text_by_name = self._build_template_text_map()
        self.template_combo['values'] = tuple(self._template_text_by_name.keys())

        default_template_name = "Testo libero" if meeting_id else "Convocazione CD"
        if default_template_name in self._template_text_by_name:
            self.template_var.set(default_template_name)
        elif self._template_text_by_name:
            self.template_var.set(next(iter(self._template_text_by_name.keys())))
        self.template_combo.pack(side=tk.LEFT, padx=5)
        self.template_combo.bind('<<ComboboxSelected>>', self._on_template_selected)

        ttk.Button(self.template_frame, text="Wizard template...", command=self._open_templates_wizard).pack(side=tk.LEFT, padx=8)
        
        # Corpo email
        row += 1
        text_frame = ttk.LabelFrame(main_frame, text="Testo email", padding=4)
        text_frame.grid(row=row, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
        
        self.text_email = scrolledtext.ScrolledText(text_frame, height=8, wrap=tk.WORD)
        self.text_email.pack(fill=tk.BOTH, expand=True)
        
        # ODG section
        row += 1
        self.odg_frame = ttk.LabelFrame(main_frame, text="Ordine del Giorno", padding=4)
        self.odg_frame.grid(row=row, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)

        ttk.Label(self.odg_frame, text="ODG (un punto per riga; usa [D] per punti che richiedono delibera):").pack(anchor="w", padx=5, pady=(0, 5))
        ttk.Label(self.odg_frame, text="Esempio: [D] Approvazione bilancio", foreground="gray").pack(anchor="w", padx=5, pady=(0, 5))
        self.text_odg = scrolledtext.ScrolledText(self.odg_frame, height=6, wrap=tk.WORD)
        self.text_odg.pack(fill=tk.BOTH, expand=True)
        
        # Verbale section (solo per riunioni passate)
        row += 1
        self.verbale_frame = ttk.LabelFrame(main_frame, text="Verbale", padding=4)
        self.verbale_frame.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
        
        verbale_row = 0
        ttk.Label(self.verbale_frame, text="Documento verbale:").grid(row=verbale_row, column=0, sticky="w", padx=5, pady=5)
        self.entry_verbale_path = ttk.Entry(self.verbale_frame, width=50, state="readonly")
        self.entry_verbale_path.grid(row=verbale_row, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(self.verbale_frame, text="Seleziona...", command=self._select_verbale).grid(row=verbale_row, column=2, padx=5, pady=5)
        self.verbale_frame.columnconfigure(1, weight=1)
        
        # Delibere section (solo per riunioni passate)
        row += 1
        self.delibere_frame = ttk.LabelFrame(main_frame, text="Delibere", padding=4)
        self.delibere_frame.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
        
        ttk.Label(self.delibere_frame, text="Elenco delibere (una per riga, formato: Numero - Oggetto):").pack(anchor="w", padx=5, pady=(0, 5))
        self.text_delibere = scrolledtext.ScrolledText(self.delibere_frame, height=5, wrap=tk.WORD)
        self.text_delibere.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        
        # Load existing meeting if editing
        if meeting_id:
            self._load_meeting()
        else:
            # Set default template for new meeting
            self._on_template_selected()
            # Toggle visibility based on tipo_riunione
            self._toggle_tipo_riunione()

        self._on_meta_tipo_changed()
        self._update_presenze_visibility()
        
        # Update recipient count
        self._update_recipient_count()
        
        # Buttons in first column
        row += 1
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=4, sticky="w", padx=5, pady=15)
        
        ttk.Button(button_frame, text="Annulla", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Anteprima e-mail", command=self._preview_email).pack(side=tk.LEFT, padx=5)
        self.btn_send_email = ttk.Button(button_frame, text="Invia e-mail", command=self._send_email_from_ui)
        if meeting_id:
            self.btn_send_email.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Salva", command=self._save).pack(side=tk.LEFT, padx=5)

        # Initial state for send button
        self._update_send_email_button_state()

    def _update_send_email_button_state(self):
        try:
            if not hasattr(self, "btn_send_email"):
                return
            if not self.meeting_id:
                self.btn_send_email.configure(state="disabled")
                return
            is_futura = self.tipo_riunione_var.get() == "futura"
            self.btn_send_email.configure(state=("normal" if is_futura else "disabled"))
        except Exception:
            pass

    def _send_email_from_ui(self):
        """Send email for an existing (future) meeting."""
        if not self.meeting_id:
            return
        if self.tipo_riunione_var.get() != "futura":
            messagebox.showinfo("Info", "Invio e-mail disponibile solo per riunioni future.", parent=self.dialog)
            return

        subject = self.entry_oggetto.get().strip()
        body = self.text_email.get("1.0", tk.END).strip()
        odg_text = self.text_odg.get("1.0", tk.END).strip()

        if not subject:
            messagebox.showwarning("Validazione", "Inserire l'oggetto dell'e-mail.", parent=self.dialog)
            return
        if not body:
            messagebox.showwarning("Validazione", "Inserire il corpo dell'e-mail.", parent=self.dialog)
            return

        send = messagebox.askyesno(
            "Invia Email",
            "Vuoi inviare l'e-mail di convocazione adesso?",
            parent=self.dialog,
        )
        if not send:
            return

        self._send_email(subject, body, odg_text)

    def _safe_int(self, s: str) -> int | None:
        s = (s or "").strip()
        if not s:
            return None
        try:
            return int(s)
        except Exception:
            return None

    def _update_quorum_label(self):
        aventi = self._safe_int(self.entry_aventi_diritto.get())
        presenti = self._safe_int(self.entry_presenti.get())
        deleghe = self._safe_int(self.entry_deleghe.get()) if self._deleghe_enabled() else 0
        quorum = self._safe_int(self.entry_quorum.get())

        totale = None
        if presenti is not None or deleghe is not None:
            totale = (presenti or 0) + (deleghe or 0)

        if quorum is None or totale is None:
            self.label_quorum_esito.configure(text="Quorum: (inserisci presenti/deleghe e quorum)", foreground="gray")
            return

        if totale >= quorum:
            self.label_quorum_esito.configure(text=f"Quorum OK: {totale} ≥ {quorum}", foreground="green")
        else:
            self.label_quorum_esito.configure(text=f"Quorum KO: {totale} < {quorum}", foreground="red")

    def _deleghe_enabled(self) -> bool:
        try:
            return self.entry_deleghe.winfo_ismapped() and str(self.entry_deleghe.cget("state")) != "disabled"
        except Exception:
            return False

    def _on_meta_tipo_changed(self):
        is_assemblea = self._is_meta_tipo_assemblea()
        if is_assemblea:
            self.label_deleghe.grid()
            self.entry_deleghe.grid()
        else:
            self.label_deleghe.grid_remove()
            self.entry_deleghe.grid_remove()
            self.entry_deleghe.delete(0, tk.END)
        self._update_presenze_visibility()
        self._update_quorum_label()

    def _set_presenze_enabled(self, enabled: bool):
        hint = "" if enabled else "Compilabile dopo il salvataggio (in modifica riunione)."
        self.label_presenze_hint.configure(text=hint)

        state = "normal" if enabled else "disabled"
        for w in (self.entry_aventi_diritto, self.entry_presenti, self.entry_deleghe, self.entry_quorum, self.text_presenze):
            try:
                w.configure(state=state)
            except Exception:
                pass
    
    def _set_today(self):
        """Set date to today"""
        self.entry_date.delete(0, tk.END)
        self.entry_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
    
    def _toggle_tipo_riunione(self):
        """Toggle visibility of sections based on meeting type"""
        is_passata = self.tipo_riunione_var.get() == "passata"
        
        # Gestisci visibilità sezioni in base al tipo di riunione
        if is_passata:
            # Nascondi/disabilita sezioni email per riunioni passate
            if hasattr(self, 'dest_frame'):
                for child in self.dest_frame.winfo_children():
                    if isinstance(child, (ttk.Radiobutton, ttk.Button)):
                        child.configure(state="disabled")
            if hasattr(self, 'template_combo'):
                self.template_combo.configure(state="disabled")
            if hasattr(self, 'text_email'):
                self.text_email.configure(state="disabled", bg="#f0f0f0")
            # Mostra sezioni verbale e delibere
            if hasattr(self, 'verbale_frame'):
                self.verbale_frame.grid()
            if hasattr(self, 'delibere_frame'):
                self.delibere_frame.grid()
        else:
            # Abilita sezioni email per riunioni future
            if hasattr(self, 'dest_frame'):
                for child in self.dest_frame.winfo_children():
                    if isinstance(child, (ttk.Radiobutton, ttk.Button)):
                        child.configure(state="normal")
            if hasattr(self, 'template_combo'):
                self.template_combo.configure(state="readonly")
            if hasattr(self, 'text_email'):
                self.text_email.configure(state="normal", bg="white")
            # Nascondi sezioni verbale e delibere
            if hasattr(self, 'verbale_frame'):
                self.verbale_frame.grid_remove()
            if hasattr(self, 'delibere_frame'):
                self.delibere_frame.grid_remove()

        self._update_send_email_button_state()
    
    def _select_verbale(self):
        """Select verbale document file"""
        file_path = filedialog.askopenfilename(
            title="Seleziona documento verbale",
            filetypes=[
                ("Documenti", "*.pdf *.doc *.docx"),
                ("PDF", "*.pdf"),
                ("Word", "*.doc *.docx"),
                ("Tutti i file", "*.*")
            ]
        )
        if file_path:
            self.entry_verbale_path.configure(state="normal")
            self.entry_verbale_path.delete(0, tk.END)
            self.entry_verbale_path.insert(0, file_path)
            self.entry_verbale_path.configure(state="readonly")
    
    def _update_recipient_count(self):
        """Update recipient count label"""
        try:
            recipients = self._get_recipients()
            count = len(recipients)
            self.label_count.config(text=f"({count} destinatari)")
        except Exception as e:
            logger.error("Error counting recipients: %s", e)
            self.label_count.config(text="")
    
    def _get_recipients(self):
        """Get list of recipients based on selection"""
        from database import fetch_all

        filter_type = (self.destinatari_var.get() or "").strip().lower()

        if filter_type in ("cd", "cd_cp"):
            roles_cd, roles_cp = self._get_roles_for_groups()
            roles: list[str] = list(roles_cd)
            if filter_type == "cd_cp":
                roles = list(dict.fromkeys(list(roles_cd) + list(roles_cp)))

            # Fallback to previous logic if definitions are missing/empty
            if not roles:
                sql = """
                    SELECT DISTINCT email, nome, cognome
                    FROM soci
                    WHERE attivo = 1
                    AND cd_ruolo IS NOT NULL
                    AND TRIM(cd_ruolo) != ''
                    AND cd_ruolo != 'Socio'
                    AND cd_ruolo != 'Ex Socio'
                    AND email IS NOT NULL
                    AND email != ''
                    ORDER BY cognome, nome
                """
                return fetch_all(sql)

            placeholders = ",".join(["?"] * len(roles))
            sql = f"""
                SELECT DISTINCT email, nome, cognome
                FROM soci
                WHERE attivo = 1
                AND email IS NOT NULL
                AND email != ''
                AND cd_ruolo IN ({placeholders})
                ORDER BY cognome, nome
            """
            return fetch_all(sql, tuple(roles))

        # Soci (default): all active members with email
        sql = """
            SELECT DISTINCT email, nome, cognome
            FROM soci
            WHERE attivo = 1
            AND email IS NOT NULL
            AND email != ''
            ORDER BY cognome, nome
        """
        return fetch_all(sql)

    def _read_definizioni_gruppi(self) -> dict[str, list[str]]:
        """Parse src/Definizioni/DefinizioniGruppi into {group_line: [role_lines...]}."""
        groups: dict[str, list[str]] = {}
        try:
            base_dir = os.path.dirname(__file__)
            path = os.path.join(base_dir, "Definizioni", "DefinizioniGruppi")
            if not os.path.isfile(path):
                return {}

            current_group: str | None = None
            with open(path, "r", encoding="utf-8") as f:
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
                    # group header
                    current_group = line.strip()
                    groups.setdefault(current_group, [])
        except Exception:
            return {}
        return groups

    def _normalize_role_label(self, role: str) -> str:
        r = (role or "").strip().lower()
        # Map definitions to DB labels
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

        # Fallback: title-case
        return (role or "").strip().title()

    def _get_roles_for_groups(self) -> tuple[list[str], list[str]]:
        """Return (CD roles, CP roles) using DefinizioniGruppi.

        For now only handles: CD, CP (Probiviri/Sindaci) as requested.
        """
        groups = self._read_definizioni_gruppi()
        if not groups:
            return ([], [])

        roles_cd: list[str] = []
        roles_cp: list[str] = []
        for group_name, roles in groups.items():
            g = (group_name or "").strip().lower()
            # Identify group by code in parentheses or name
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
    
    def _show_recipients(self):
        """Show recipients in a dialog"""
        recipients = self._get_recipients()
        
        dialog = tk.Toplevel(self.dialog)
        dialog.title("Anteprima Destinatari")
        dialog.geometry("600x400")
        dialog.transient(self.dialog)
        
        ttk.Label(dialog, text=f"Destinatari selezionati: {len(recipients)}", font=("Arial", 10, "bold")).pack(padx=10, pady=10)
        
        # Treeview with scrollbar
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(frame, columns=('email', 'nome'), show='headings', height=15)
        tree.heading('email', text='Email')
        tree.heading('nome', text='Nome')
        tree.column('email', width=250)
        tree.column('nome', width=200)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        for r in recipients:
            tree.insert('', 'end', values=(r[0], f"{r[2]} {r[1]}"))
        
        ttk.Button(dialog, text="Chiudi", command=dialog.destroy).pack(pady=10)
    
    def _on_template_selected(self, event=None):
        """Load template text when selected"""
        template_name = self.template_var.get()

        template_text = ""
        try:
            template_text = (self._template_text_by_name or {}).get(template_name, "")
        except Exception:
            template_text = ""
        
        self.text_email.delete('1.0', tk.END)
        self.text_email.insert('1.0', template_text)
        
        # Suggest oggetto if not set
        if not self.entry_oggetto.get() and template_name == 'Convocazione CD':
            self.entry_oggetto.delete(0, tk.END)
            self.entry_oggetto.insert(0, "Convocazione Consiglio Direttivo")

    def _ensure_default_email_template_for_edit(self):
        """For edited future meetings, prefill email template if body is empty.

        We don't persist email body in DB; this provides a sensible default without
        overwriting any text the user already typed in the dialog.
        """
        try:
            if not self.meeting_id:
                return
            if self.tipo_riunione_var.get() != "futura":
                return
            current_body = self.text_email.get("1.0", tk.END).strip() if hasattr(self, "text_email") else ""
            if current_body:
                return

            # Set template to "Convocazione CD" if available
            if hasattr(self, "template_var"):
                self.template_var.set("Convocazione CD")
                self._on_template_selected()
        except Exception:
            pass

    def _render_email_body(self, body: str, odg: str) -> str:
        """Render common placeholders in email body from current UI fields."""
        rendered = body

        data = self.entry_date.get().strip() if hasattr(self, "entry_date") else ""
        ora = self.entry_meta_ora_inizio.get().strip() if hasattr(self, "entry_meta_ora_inizio") else ""
        luogo = self.entry_meta_luogo.get().strip() if hasattr(self, "entry_meta_luogo") else ""
        modalita = self.meta_modalita_var.get().strip().lower() if hasattr(self, "meta_modalita_var") else ""

        # Small wording tweak for the default convocazione sentence.
        # Do not add new templates: just adjust the existing phrase when present.
        if '{luogo}' in rendered:
            if modalita == 'online':
                rendered = rendered.replace('presso {luogo}', 'tramite {luogo}')
            elif modalita == 'ibrida':
                rendered = rendered.replace('presso {luogo}', 'presso / tramite {luogo}')

        if '{data}' in rendered and data:
            rendered = rendered.replace('{data}', data)
        if '{ora}' in rendered and ora:
            rendered = rendered.replace('{ora}', ora)
        if '{luogo}' in rendered and luogo:
            rendered = rendered.replace('{luogo}', luogo)
        if '{odg}' in rendered and odg:
            rendered = rendered.replace('{odg}', odg)

        return rendered

    def _format_odg_for_email(self, odg_text: str) -> str:
        """Normalize ODG for emails by hiding internal markers.

        Removes markers like [D]/[DEL]/DEL:/D:/! at line start.
        """
        lines_out: list[str] = []
        for ln in (odg_text or "").splitlines():
            raw = ln.rstrip()
            if not raw.strip():
                continue

            stripped = raw.lstrip()
            up = stripped.upper()
            is_delibera = False

            for prefix in ("[D]", "[DEL]", "DEL:", "D:", "!"):
                if up.startswith(prefix):
                    is_delibera = True
                    stripped = stripped[len(prefix):].lstrip()
                    break

            clean = stripped if is_delibera else raw.strip()
            if clean:
                lines_out.append(clean)

        return "\n".join(lines_out)

    def _extract_delibere_from_odg(self, odg_text: str) -> list[str]:
        """Extract delibera titles from ODG points marked as requiring delibera."""
        titles: list[str] = []
        for ln in (odg_text or "").splitlines():
            raw = ln.strip()
            if not raw:
                continue

            up = raw.upper()
            requires = False
            for prefix in ("[D]", "[DEL]", "DEL:", "D:", "!"):
                if up.startswith(prefix):
                    requires = True
                    raw = raw[len(prefix):].strip()
                    break

            if requires and raw:
                titles.append(raw)

        return titles

    def _sync_delibere_from_odg(self, meeting_id: int, odg_text: str, data_riunione: str) -> None:
        """Ensure delibere exist for ODG points marked [D].

        - Creates missing delibere from ODG order.
        - Assigns a progressive `numero` (01, 02, ...) only when missing.
        - Never duplicates delibere already present (match by oggetto, case-insensitive).
        """
        titles = self._extract_delibere_from_odg(odg_text)
        if not titles:
            return

        try:
            from cd_delibere import get_all_delibere, add_delibera, update_delibera

            existing = get_all_delibere(meeting_id=int(meeting_id))
            by_oggetto = {
                str(d.get("oggetto") or "").strip().lower(): d
                for d in existing
                if str(d.get("oggetto") or "").strip()
            }

            for idx, title in enumerate(titles, start=1):
                title_norm = title.strip().lower()
                if not title_norm:
                    continue

                numero_auto = f"{idx:02d}"
                found = by_oggetto.get(title_norm)
                if found:
                    # Only fill numero if missing/empty
                    cur_num = str(found.get("numero") or "").strip()
                    if not cur_num and found.get("id") is not None:
                        update_delibera(int(found["id"]), numero=numero_auto)
                    continue

                delibera_id = add_delibera(
                    cd_id=int(meeting_id),
                    numero=numero_auto,
                    oggetto=title.strip(),
                    esito="APPROVATA",
                    data_votazione=data_riunione,
                )
                if delibera_id != -1:
                    by_oggetto[title_norm] = {"id": delibera_id, "numero": numero_auto, "oggetto": title.strip()}
        except Exception as exc:
            logger.warning("Sync delibere da ODG fallita: %s", exc)
    
    def _preview_email(self):
        """Show email preview"""
        subject = self.entry_oggetto.get().strip()
        body = self.text_email.get('1.0', tk.END).strip()
        odg_raw = self.text_odg.get('1.0', tk.END).strip()
        odg = self._format_odg_for_email(odg_raw)

        body = self._render_email_body(body, odg)
        
        # Show preview dialog
        preview = tk.Toplevel(self.dialog)
        preview.title("Anteprima Email")
        preview.geometry("700x500")
        preview.transient(self.dialog)
        
        ttk.Label(preview, text="Oggetto:", font=("Arial", 10, "bold")).pack(anchor='w', padx=10, pady=(10, 0))
        subject_text = tk.Text(preview, height=2, wrap=tk.WORD)
        subject_text.pack(fill=tk.X, padx=10, pady=5)
        subject_text.insert('1.0', subject)
        subject_text.config(state='disabled')
        
        ttk.Label(preview, text="Corpo:", font=("Arial", 10, "bold")).pack(anchor='w', padx=10, pady=(10, 0))
        body_text = scrolledtext.ScrolledText(preview, height=20, wrap=tk.WORD)
        body_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        body_text.insert('1.0', body)
        body_text.config(state='disabled')
        
        ttk.Button(preview, text="Chiudi", command=preview.destroy).pack(pady=10)
    
    def _load_meeting(self):
        """Load existing meeting data for editing"""
        if not self.meeting_id:
            return
        
        from cd_meetings import get_meeting_by_id
        meeting = get_meeting_by_id(self.meeting_id)
        
        if meeting:
            # Determine tipo_riunione from DB if available; fallback by date
            try:
                tr = (meeting.get("tipo_riunione") or "").strip().lower()
                if tr in ("futura", "passata"):
                    self.tipo_riunione_var.set(tr)
                else:
                    data_str = (meeting.get("data") or "").strip()
                    try:
                        d = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else None
                    except Exception:
                        d = None
                    if d is not None:
                        self.tipo_riunione_var.set("futura" if d >= datetime.now().date() else "passata")
                    else:
                        self.tipo_riunione_var.set("passata")
            except Exception:
                self.tipo_riunione_var.set("passata")

            if meeting.get('numero_cd'):
                self.entry_numero_cd.delete(0, tk.END)
                self.entry_numero_cd.insert(0, meeting.get('numero_cd', ''))
            
            self.entry_date.delete(0, tk.END)
            self.entry_date.insert(0, meeting.get('data', ''))
            
            self.entry_oggetto.delete(0, tk.END)
            self.entry_oggetto.insert(0, meeting.get('titolo', ''))
            
            if meeting.get('odg'):
                self.text_odg.delete("1.0", tk.END)
                self.text_odg.insert("1.0", meeting.get('odg', ''))

            # Load meta_json
            meta_json = meeting.get("meta_json")
            if meta_json:
                try:
                    meta = json.loads(meta_json)
                    if isinstance(meta, dict):
                        if (meta.get("tipo") or "").strip():
                            self.meta_tipo_var.set((meta.get("tipo") or "").strip())
                        if (meta.get("modalita") or "").strip():
                            self.meta_modalita_var.set((meta.get("modalita") or "").strip())
                        self.entry_meta_luogo.delete(0, tk.END)
                        self.entry_meta_luogo.insert(0, (meta.get("luogo_link") or "").strip())
                        self.entry_meta_ora_inizio.delete(0, tk.END)
                        self.entry_meta_ora_inizio.insert(0, (meta.get("ora_inizio") or "").strip())
                        self.entry_meta_ora_fine.delete(0, tk.END)
                        self.entry_meta_ora_fine.insert(0, (meta.get("ora_fine") or "").strip())
                except Exception:
                    pass

            self._on_meta_tipo_changed()

            # Load presenze_json
            presenze_json = meeting.get("presenze_json")
            if presenze_json:
                try:
                    pres = json.loads(presenze_json)
                    if isinstance(pres, dict):
                        counts = pres.get("counts") if isinstance(pres.get("counts"), dict) else {}
                        if counts:
                            if counts.get("aventi_diritto") is not None:
                                self.entry_aventi_diritto.delete(0, tk.END)
                                self.entry_aventi_diritto.insert(0, str(counts.get("aventi_diritto")))
                            if counts.get("presenti") is not None:
                                self.entry_presenti.delete(0, tk.END)
                                self.entry_presenti.insert(0, str(counts.get("presenti")))
                            if counts.get("deleghe") is not None:
                                self.entry_deleghe.delete(0, tk.END)
                                self.entry_deleghe.insert(0, str(counts.get("deleghe")))
                            if counts.get("quorum_richiesto") is not None:
                                self.entry_quorum.delete(0, tk.END)
                                self.entry_quorum.insert(0, str(counts.get("quorum_richiesto")))
                        raw_text = pres.get("raw_text")
                        if isinstance(raw_text, str) and raw_text.strip():
                            self.text_presenze.delete("1.0", tk.END)
                            self.text_presenze.insert("1.0", raw_text)
                except Exception:
                    pass

            self._update_quorum_label()

            # Apply UI visibility/state based on loaded tipo_riunione
            self._toggle_tipo_riunione()

            # If future meeting, keep a sensible template in edit mode
            self._ensure_default_email_template_for_edit()

            # Load existing delibere (if any) into the text box
            try:
                from cd_delibere import get_all_delibere

                delibere = get_all_delibere(meeting_id=int(self.meeting_id))
                if delibere and hasattr(self, 'text_delibere'):
                    self.text_delibere.delete("1.0", tk.END)
                    lines: list[str] = []
                    for d in delibere:
                        numero = (d.get('numero') or '').strip()
                        oggetto = (d.get('oggetto') or '').strip()
                        if numero and oggetto:
                            lines.append(f"{numero} - {oggetto}")
                        elif oggetto:
                            lines.append(oggetto)
                    if lines:
                        self.text_delibere.insert("1.0", "\n".join(lines))
            except Exception:
                pass
    
    def _send_email(self, subject, body, odg):
        """Generate EML file and/or mailto URL"""
        # Get recipients
        recipients = self._get_recipients()
        if not recipients:
            messagebox.showwarning("Attenzione", "Nessun destinatario trovato.", parent=self.dialog)
            return False
        
        body = self._render_email_body(body, self._format_odg_for_email(odg))
        
        # Build email list
        bcc_emails = [r[0] for r in recipients]

        mailto_url = self._build_mailto_url(subject, body, bcc_emails)
        mailto_too_long = len(mailto_url) > 2000

        tb_exe = self._find_thunderbird_exe()
        tb_available = bool(tb_exe)
        
        # Ask user which method to use
        choice_dialog = tk.Toplevel(self.dialog)
        choice_dialog.title("Modalità Invio Email")
        choice_dialog.geometry("500x300")
        choice_dialog.transient(self.dialog)
        choice_dialog.grab_set()
        
        ttk.Label(choice_dialog, text=f"Email preparata per {len(bcc_emails)} destinatari", 
                 font=("Arial", 12, "bold")).pack(pady=20)
        
        ttk.Label(choice_dialog, text="Come vuoi procedere?", font=("Arial", 10)).pack(pady=10)
        
        result: dict[str, str | None] = {'action': None}
        
        def create_eml():
            result['action'] = 'eml'
            choice_dialog.destroy()
        
        def copy_emails():
            result['action'] = 'copy'
            choice_dialog.destroy()
        
        def use_mailto():
            result['action'] = 'mailto'
            choice_dialog.destroy()

        def use_thunderbird():
            result['action'] = 'thunderbird'
            choice_dialog.destroy()

        def select_thunderbird_portable():
            try:
                exe_path = filedialog.askopenfilename(
                    parent=choice_dialog,
                    title="Seleziona thunderbird.exe (Portable)",
                    filetypes=[("Thunderbird", "thunderbird.exe"), ("Eseguibili", "*.exe"), ("Tutti i file", "*.*")],
                )
                if not exe_path:
                    return
                if not os.path.isfile(exe_path):
                    messagebox.showwarning("Validazione", "Percorso non valido.", parent=choice_dialog)
                    return
                self._save_thunderbird_exe_path(exe_path)
                result['action'] = 'thunderbird'
                choice_dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Errore", f"Impossibile selezionare Thunderbird:\n{exc}", parent=choice_dialog)
        
        def cancel():
            result['action'] = 'cancel'
            choice_dialog.destroy()
        
        btn_frame = ttk.Frame(choice_dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="🦅 Apri in Thunderbird", command=use_thunderbird, width=25).pack(pady=5)
        ttk.Label(btn_frame, text="(Consigliato: evita problemi con mailto)", font=("Arial", 8), foreground="gray").pack()
        
        ttk.Button(btn_frame, text="📧 Genera file EML", command=create_eml, width=25).pack(pady=5)
        ttk.Label(btn_frame, text="(Apribile con Outlook, Thunderbird, IONOS, ecc.)", 
                 font=("Arial", 8), foreground="gray").pack()
        
        ttk.Button(btn_frame, text="📋 Copia indirizzi email", command=copy_emails, width=25).pack(pady=5)
        ttk.Label(btn_frame, text="(Incolla manualmente nel tuo client)", 
                 font=("Arial", 8), foreground="gray").pack()
        
        ttk.Button(btn_frame, text="🌐 Apri con mailto:", command=use_mailto, width=25).pack(pady=5)
        ttk.Label(btn_frame, text="(Client email predefinito)", 
                 font=("Arial", 8), foreground="gray").pack()

        if not tb_available:
            try:
                for child in btn_frame.winfo_children():
                    if isinstance(child, ttk.Button) and str(child.cget("text")).startswith("🦅"):
                        child.configure(state="disabled")
                        break
            except Exception:
                pass

            ttk.Button(
                btn_frame,
                text="📂 Seleziona Thunderbird portable…",
                command=select_thunderbird_portable,
                width=25,
            ).pack(pady=(10, 5))
            ttk.Label(
                btn_frame,
                text="(Seleziona thunderbird.exe e riapri la composizione)",
                font=("Arial", 8),
                foreground="gray",
            ).pack()
            ttk.Label(
                choice_dialog,
                text="Nota: Thunderbird non trovato automaticamente.",
                font=("Arial", 9),
                foreground="gray",
            ).pack(pady=(0, 10))

        if mailto_too_long:
            try:
                # Disable mailto option proactively; EML/copy remain available.
                for child in btn_frame.winfo_children():
                    if isinstance(child, ttk.Button) and str(child.cget("text")).startswith("🌐"):
                        child.configure(state="disabled")
                        break
            except Exception:
                pass
            ttk.Label(
                choice_dialog,
                text=f"Nota: mailto disabilitato (URL troppo lungo: {len(mailto_url)} caratteri).",
                font=("Arial", 9),
                foreground="gray",
            ).pack(pady=(0, 10))
        
        ttk.Button(choice_dialog, text="Annulla", command=cancel).pack(pady=10)
        
        choice_dialog.wait_window()
        
        if result['action'] == 'eml':
            return self._create_eml_file(subject, body, bcc_emails)
        elif result['action'] == 'copy':
            return self._copy_emails_to_clipboard(bcc_emails)
        elif result['action'] == 'thunderbird':
            return self._open_thunderbird(subject, body, bcc_emails)
        elif result['action'] == 'mailto':
            return self._open_mailto(subject, body, bcc_emails)
        else:
            return False

    def _find_thunderbird_exe(self) -> str | None:
        """Try to locate thunderbird.exe on Windows.

        We avoid relying on the MAILTO handler because Windows may still prompt for an app.
        """
        # Configured portable path (highest priority)
        try:
            cfg_path = self._load_thunderbird_exe_path()
            if cfg_path and os.path.isfile(cfg_path):
                return cfg_path
        except Exception:
            pass

        candidates: list[str] = []
        try:
            pf = os.environ.get("ProgramFiles")
            pfx86 = os.environ.get("ProgramFiles(x86)")
            if pf:
                candidates.append(os.path.join(pf, "Mozilla Thunderbird", "thunderbird.exe"))
            if pfx86:
                candidates.append(os.path.join(pfx86, "Mozilla Thunderbird", "thunderbird.exe"))
        except Exception:
            pass

        # Registry App Paths (most reliable)
        try:
            import winreg

            reg_paths = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\thunderbird.exe",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\thunderbird.exe",
            ]
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for subkey in reg_paths:
                    try:
                        with winreg.OpenKey(root, subkey) as k:
                            val, _typ = winreg.QueryValueEx(k, "")
                            if isinstance(val, str) and val:
                                candidates.insert(0, val)
                    except Exception:
                        continue
        except Exception:
            pass

        for path in candidates:
            try:
                if path and os.path.isfile(path):
                    return path
            except Exception:
                continue
        return None

    def _load_thunderbird_exe_path(self) -> str | None:
        try:
            from config_manager import load_config

            cfg = load_config()
            value = cfg.get("thunderbird_exe_path") if isinstance(cfg, dict) else None
            if isinstance(value, str) and value.strip():
                return value.strip()
        except Exception:
            return None
        return None

    def _save_thunderbird_exe_path(self, exe_path: str) -> None:
        try:
            from config_manager import load_config, save_config

            cfg = load_config()
            if not isinstance(cfg, dict):
                cfg = {}
            cfg["thunderbird_exe_path"] = exe_path
            save_config(cfg)
        except Exception:
            # Best effort: if config is not initialized (e.g. in some dev contexts), ignore.
            pass

    def _escape_thunderbird_compose_value(self, s: str) -> str:
        # Use double quotes in -compose values; escape backslash and double quotes.
        # Keep real newlines so the body renders correctly.
        s = (s or "").replace("\\", "\\\\").replace('"', '\\"')
        return s

    def _open_thunderbird(self, subject: str, body: str, bcc_emails: list[str]) -> bool:
        """Open Thunderbird compose window directly with fields prefilled."""
        tb_exe = self._find_thunderbird_exe()
        if not tb_exe:
            messagebox.showwarning(
                "Thunderbird non trovato",
                "Thunderbird non risulta installato o non è stato trovato.\n\n"
                "Usa 'Genera file EML' o 'Copia indirizzi email'.",
                parent=self.dialog,
            )
            return False

        try:
            bcc_str = ",".join([e for e in (bcc_emails or []) if e])
            compose = ",".join(
                [
                    'to=""',
                    f'bcc="{self._escape_thunderbird_compose_value(bcc_str)}"',
                    f'subject="{self._escape_thunderbird_compose_value(subject or "")}"',
                    f'body="{self._escape_thunderbird_compose_value(body or "")}"',
                ]
            )
            subprocess.Popen([tb_exe, "-compose", compose], close_fds=True)
            messagebox.showinfo(
                "Thunderbird",
                f"Thunderbird aperto con {len(bcc_emails)} destinatari in BCC.",
                parent=self.dialog,
            )
            return True
        except Exception as e:
            logger.error("Failed to open Thunderbird compose: %s", e)
            messagebox.showerror(
                "Errore",
                f"Impossibile aprire Thunderbird:\n{e}",
                parent=self.dialog,
            )
            return False
    
    def _create_eml_file(self, subject, body, bcc_emails):
        """Create EML file"""
        import os
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = ''  # Will be filled by email client
            msg['Bcc'] = ', '.join(bcc_emails)
            
            # Add body
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Ask where to save
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                parent=self.dialog,
                title="Salva file EML",
                defaultextension=".eml",
                filetypes=[("Email Message", "*.eml"), ("All Files", "*.*")],
                initialfile=f"convocazione_{datetime.now().strftime('%Y%m%d')}.eml"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(msg.as_string())
                
                # Ask if user wants to open it
                open_it = messagebox.askyesno(
                    "File Creato",
                    f"File EML salvato:\n{filename}\n\nVuoi aprirlo ora?",
                    parent=self.dialog
                )
                
                if open_it:
                    os.startfile(filename)
                
                return True
            return False
            
        except Exception as e:
            logger.error("Failed to create EML file: %s", e)
            messagebox.showerror("Errore", f"Impossibile creare il file EML:\n{e}", parent=self.dialog)
            return False
    
    def _copy_emails_to_clipboard(self, bcc_emails):
        """Copy email addresses to clipboard"""
        try:
            # Create formatted list
            emails_text = '; '.join(bcc_emails)
            
            self.dialog.clipboard_clear()
            self.dialog.clipboard_append(emails_text)
            
            # Show dialog with emails
            copy_dialog = tk.Toplevel(self.dialog)
            copy_dialog.title("Indirizzi Email Copiati")
            copy_dialog.geometry("600x400")
            copy_dialog.transient(self.dialog)
            
            ttk.Label(copy_dialog, text=f"✓ {len(bcc_emails)} indirizzi copiati negli appunti", 
                     font=("Arial", 11, "bold"), foreground="green").pack(pady=10)
            
            ttk.Label(copy_dialog, text="Incolla nel campo BCC/CCN del tuo client email:", 
                     font=("Arial", 10)).pack(pady=5)
            
            # Show emails in text widget
            text_frame = ttk.Frame(copy_dialog)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            text_widget = scrolledtext.ScrolledText(text_frame, height=15, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True)
            text_widget.insert('1.0', emails_text)
            text_widget.config(state='disabled')
            
            ttk.Button(copy_dialog, text="Chiudi", command=copy_dialog.destroy).pack(pady=10)
            
            return True
            
        except Exception as e:
            logger.error("Failed to copy emails: %s", e)
            messagebox.showerror("Errore", f"Impossibile copiare gli indirizzi:\n{e}", parent=self.dialog)
            return False
    
    def _open_mailto(self, subject, body, bcc_emails):
        """Open mailto URL in default email client"""
        try:
            mailto_url = self._build_mailto_url(subject, body, bcc_emails)
            
            # Check URL length
            if len(mailto_url) > 2000:
                messagebox.showwarning(
                    "URL Troppo Lungo",
                    f"L'URL mailto è troppo lungo ({len(mailto_url)} caratteri).\n\n"
                    f"Usa invece 'Genera file EML' o 'Copia indirizzi email'.",
                    parent=self.dialog
                )
                return False
            
            webbrowser.open(mailto_url)
            messagebox.showinfo("Email Aperta", f"Email preparata con {len(bcc_emails)} destinatari in BCC.", parent=self.dialog)
            return True
            
        except Exception as e:
            logger.error("Failed to open mailto: %s", e)
            messagebox.showerror("Errore", f"Impossibile aprire il client email:\n{e}", parent=self.dialog)
            return False

    def _build_mailto_url(self, subject: str, body: str, bcc_emails: list[str]) -> str:
        bcc_str = ','.join(bcc_emails or [])
        return (
            f"mailto:?subject={urllib.parse.quote(subject or '')}"
            f"&bcc={urllib.parse.quote(bcc_str)}"
            f"&body={urllib.parse.quote(body or '')}"
        )
    
    def _save(self):
        """Save meeting and optionally send email"""
        numero_cd = self.entry_numero_cd.get().strip()
        data = self.entry_date.get().strip()
        oggetto = self.entry_oggetto.get().strip()
        odg_text = self.text_odg.get("1.0", tk.END).strip()
        corpo_email = self.text_email.get("1.0", tk.END).strip()
        verbale_path = self.entry_verbale_path.get().strip() if hasattr(self, 'entry_verbale_path') else None
        delibere_text = self.text_delibere.get("1.0", tk.END).strip() if hasattr(self, 'text_delibere') else None

        meta_payload = {
            "version": 1,
            "tipo": self.meta_tipo_var.get().strip(),
            "modalita": self.meta_modalita_var.get().strip(),
            "luogo_link": self.entry_meta_luogo.get().strip(),
            "ora_inizio": self.entry_meta_ora_inizio.get().strip(),
            "ora_fine": self.entry_meta_ora_fine.get().strip(),
        }
        # drop empty values to keep JSON tidy
        meta_payload = {k: v for k, v in meta_payload.items() if v not in (None, "")}
        meta_json = json.dumps(meta_payload, ensure_ascii=False) if meta_payload else None

        presenze_json = None
        if bool(self.meeting_id) and self._is_meta_tipo_assemblea():
            counts = {
                "aventi_diritto": self._safe_int(self.entry_aventi_diritto.get()),
                "presenti": self._safe_int(self.entry_presenti.get()),
                "deleghe": self._safe_int(self.entry_deleghe.get()) if self._deleghe_enabled() else None,
                "quorum_richiesto": self._safe_int(self.entry_quorum.get()),
            }
            counts = {k: v for k, v in counts.items() if v is not None}
            presenze_payload = {
                "version": 1,
                "counts": counts,
                "raw_text": self.text_presenze.get("1.0", tk.END).strip(),
            }
            if not presenze_payload["raw_text"]:
                presenze_payload.pop("raw_text", None)
            if not presenze_payload["counts"]:
                presenze_payload.pop("counts", None)
            presenze_json = json.dumps(presenze_payload, ensure_ascii=False) if len(presenze_payload) > 1 else None
        
        if not data:
            messagebox.showwarning("Validazione", "Inserire la data della riunione.", parent=self.dialog)
            return
        
        # Validate numero_cd format (optional, but if provided must be 2 digits)
        if numero_cd and not numero_cd.isdigit():
            messagebox.showwarning("Validazione", "Il numero CD deve contenere solo cifre.", parent=self.dialog)
            return
        
        # Format numero_cd to 2 digits if provided
        if numero_cd:
            numero_cd = numero_cd.zfill(2)
        
        try:
            # Validate date format
            datetime.strptime(data, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Errore", "Formato data non valido. Usa YYYY-MM-DD", parent=self.dialog)
            return
        
        try:
            # Save meeting first
            if self.meeting_id:
                from cd_meetings import update_meeting
                if update_meeting(
                    self.meeting_id,
                    numero_cd=numero_cd if numero_cd else None,
                    data=data,
                    titolo=oggetto if oggetto else None,
                    odg=odg_text if odg_text else None,
                    verbale_path=verbale_path,
                    tipo_riunione=self.tipo_riunione_var.get(),
                    meta_json=meta_json,
                    presenze_json=presenze_json,
                ):
                    meeting_id = self.meeting_id
                else:
                    messagebox.showerror("Errore", "Errore durante l'aggiornamento.", parent=self.dialog)
                    return
            else:
                from cd_meetings import add_meeting
                meeting_id = add_meeting(
                    data,
                    numero_cd=numero_cd if numero_cd else None,
                    titolo=oggetto if oggetto else None,
                    odg=odg_text if odg_text else None,
                    verbale_path=verbale_path,
                    tipo_riunione=self.tipo_riunione_var.get(),
                    meta_json=meta_json,
                    presenze_json=presenze_json,
                )
                if meeting_id <= 0:
                    messagebox.showerror("Errore", "Errore durante la creazione della riunione.", parent=self.dialog)
                    return
                logger.info(f"Meeting created with ID: {meeting_id}")
            
            # Se è una riunione passata, salva delibere
            if self.tipo_riunione_var.get() == "passata":
                # If left empty, auto-generate delibere from ODG [D] points (only if none exist yet)
                if not delibere_text:
                    try:
                        from cd_delibere import get_all_delibere

                        existing = get_all_delibere(meeting_id=int(meeting_id))
                    except Exception:
                        existing = []

                    if not existing:
                        auto_titles = self._extract_delibere_from_odg(odg_text)
                        if auto_titles:
                            delibere_text = "\n".join(auto_titles)

                if delibere_text:
                    self._save_delibere(meeting_id, delibere_text, data)

                # Always ensure [D] ODG points have a corresponding delibera (create missing only)
                if odg_text:
                    self._sync_delibere_from_odg(int(meeting_id), odg_text, data)
            
            self.result = True
            
            # Ask if user wants to send email (solo per riunioni future)
            if (not self.meeting_id) and self.tipo_riunione_var.get() == "futura" and corpo_email.strip() and oggetto:
                send = messagebox.askyesno(
                    "Invia Email",
                    "Riunione salvata!\n\nVuoi inviare l'email di convocazione?",
                    parent=self.dialog
                )
                if send:
                    self._send_email(oggetto, corpo_email, odg_text)
            else:
                messagebox.showinfo("Successo", "Riunione salvata con successo.", parent=self.dialog)
            
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}", parent=self.dialog)
            logger.error("Error saving meeting: %s", e)
    
    def _save_delibere(self, meeting_id: int, delibere_text: str, data_riunione: str):
        """Save delibere from text"""
        from cd_delibere import add_delibera, get_all_delibere

        existing = get_all_delibere(meeting_id=int(meeting_id))
        existing_oggetti = {
            str(d.get("oggetto") or "").strip().lower()
            for d in existing
            if str(d.get("oggetto") or "").strip()
        }
        
        lines = delibere_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse formato: Numero - Oggetto
            if ' - ' in line:
                parts = line.split(' - ', 1)
                numero = parts[0].strip()
                oggetto = parts[1].strip() if len(parts) > 1 else ""
            else:
                # Se non c'è separatore, usa tutta la riga come oggetto
                numero = ""
                oggetto = line
            
            try:
                oggetto_norm = oggetto.strip().lower()
                if oggetto_norm and oggetto_norm in existing_oggetti:
                    continue
                add_delibera(
                    cd_id=meeting_id,
                    numero=numero if numero else "",
                    oggetto=oggetto,
                    esito="APPROVATA",
                    data_votazione=data_riunione
                )
                if oggetto_norm:
                    existing_oggetti.add(oggetto_norm)
            except Exception as e:
                logger.error(f"Error saving delibera: {e}")


class MeetingsListDialog:
    """Dialog to display and manage list of CD meetings"""
    
    def __init__(self, parent):
        """
        Initialize meetings list dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Riunioni CD")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(button_frame, text="Nuova riunione", command=self._new_meeting).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Modifica", command=self._edit_meeting).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Visualizza verbale", command=self._view_verbale).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Elimina", command=self._delete_meeting).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Chiudi", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=2)
        
        # Treeview frame
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar_h = ttk.Scrollbar(tree_frame, orient="horizontal")
        scrollbar_v = ttk.Scrollbar(tree_frame, orient="vertical")
        
        self.tv = ttk.Treeview(
            tree_frame,
            columns=("id", "numero_cd", "data", "tipo", "titolo", "verbale"),
            show="headings",
            xscrollcommand=scrollbar_h.set,
            yscrollcommand=scrollbar_v.set,
            height=15
        )
        scrollbar_h.config(command=self.tv.xview)
        scrollbar_v.config(command=self.tv.yview)
        
        # Configure columns
        self.tv.column("id", width=40, anchor="center")
        self.tv.column("numero_cd", width=70, anchor="center")
        self.tv.column("data", width=100, anchor="center")
        self.tv.column("tipo", width=220, anchor="w")
        self.tv.column("titolo", width=260, anchor="w")
        self.tv.column("verbale", width=80, anchor="center")
        
        self.tv.heading("id", text="ID")
        self.tv.heading("numero_cd", text="N. CD")
        self.tv.heading("data", text="Data")
        self.tv.heading("tipo", text="Tipo")
        self.tv.heading("titolo", text="Titolo")
        self.tv.heading("verbale", text="Verbale")
        
        self.tv.grid(row=0, column=0, sticky="nsew")
        scrollbar_h.grid(row=1, column=0, sticky="ew")
        scrollbar_v.grid(row=0, column=1, sticky="ns")
        
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Load meetings
        self._refresh()
    
    def _refresh(self):
        """Refresh meetings list"""
        from cd_meetings import get_all_meetings
        
        # Clear existing items
        for item in self.tv.get_children():
            self.tv.delete(item)
        
        # Load meetings
        meetings = get_all_meetings()
        for meeting in meetings:
            verbale = "✓" if meeting.get('verbale_path') else "—"

            tipo = ""
            meta_json = meeting.get("meta_json")
            if isinstance(meta_json, str) and meta_json.strip():
                try:
                    meta = json.loads(meta_json)
                    if isinstance(meta, dict):
                        tipo = str(meta.get("tipo") or "").strip()
                except Exception:
                    tipo = ""

            self.tv.insert("", tk.END, iid=meeting['id'], values=(
                meeting['id'],
                meeting.get('numero_cd', '—'),
                meeting.get('data', ''),
                tipo,
                meeting.get('titolo', '—'),
                verbale
            ))
    
    def _get_selected(self):
        """Get selected meeting ID"""
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("Selezione", "Seleziona una riunione.")
            return None
        return int(sel[0])
    
    def _new_meeting(self):
        """Open dialog to create new meeting"""
        MeetingDialog(self.dialog)
        self._refresh()
    
    def _edit_meeting(self):
        """Edit selected meeting"""
        meeting_id = self._get_selected()
        if meeting_id:
            MeetingDialog(self.dialog, meeting_id=meeting_id)
            self._refresh()
    
    def _delete_meeting(self):
        """Delete selected meeting"""
        meeting_id = self._get_selected()
        if not meeting_id:
            return
        
        res = messagebox.askyesnocancel(
            "Elimina riunione",
            "Eliminare la riunione?\n\nScegli 'Sì' per eliminare anche il verbale."
        )
        
        if res is None:
            return  # Cancel
        
        from cd_meetings import delete_meeting
        if delete_meeting(meeting_id, delete_verbale=res):
            messagebox.showinfo("Successo", "Riunione eliminata.")
            self._refresh()
        else:
            messagebox.showerror("Errore", "Errore durante l'eliminazione.")
    
    def _view_verbale(self):
        """View/open verbale document"""
        meeting_id = self._get_selected()
        if not meeting_id:
            return
        
        from cd_meetings import get_verbale_info
        verbale_info = get_verbale_info(meeting_id)
        
        if not verbale_info:
            messagebox.showinfo("Verbale", "Nessun verbale per questa riunione.")
            return
        
        try:
            import os
            verbale_path = verbale_info['path']
            if os.path.exists(verbale_path):
                os.startfile(verbale_path)
            else:
                messagebox.showerror("Errore", f"File non trovato: {verbale_path}")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante l'apertura: {e}")
