# -*- coding: utf-8 -*-
"""Dialog for application preferences (customizable options)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable

from preferences import (
    DEFAULT_ROLE_OPTIONS,
    build_document_categories,
    build_section_document_categories,
    get_role_options,
    sanitize_custom_document_categories,
    sanitize_custom_section_document_categories,
    save_custom_role_options,
    sanitize_custom_role_options,
)
from documents_catalog import DOCUMENT_CATEGORIES
from section_documents import SECTION_DOCUMENT_CATEGORIES
from config_manager import load_config, save_config


class PreferencesDialog(tk.Toplevel):
    """Simple preferences dialog focused on editable member role options."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        *,
        cfg: dict | None = None,
        on_save: Callable[[dict], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("Preferenze")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.parent = parent
        self.on_save = on_save
        self.current_cfg = cfg or {}

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self) -> None:
        try:
            from .styles import ensure_app_named_fonts

            ensure_app_named_fonts(self.winfo_toplevel())
        except Exception:
            pass

        container = ttk.Frame(self, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style(self)
        style.configure(
            "PreferencesNotebook.TNotebook.Tab",
            font=("Segoe UI", 10, "bold"),
            padding=(16, 6, 16, 6),
        )
        notebook = ttk.Notebook(container, style="PreferencesNotebook.TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True)

        roles_frame = ttk.Frame(notebook, padding=10)
        notebook.add(roles_frame, text="Stato socio")

        mail_frame = ttk.Frame(notebook, padding=10)
        notebook.add(mail_frame, text="Client posta")

        backup_frame = ttk.Frame(notebook, padding=10)
        notebook.add(backup_frame, text="Backup")

        categories_frame = ttk.Frame(notebook, padding=10)
        notebook.add(categories_frame, text="Tipi documenti")

        ttk.Label(
            roles_frame,
            text="Voci predefinite (sempre disponibili):",
            font="AppBold",
        ).pack(anchor="w")

        defaults_box = tk.Text(roles_frame, height=6, width=40, state="disabled", wrap=tk.WORD)
        defaults_box.pack(fill=tk.X, pady=(4, 10))
        defaults_box.configure(state="normal")
        defaults_box.insert("1.0", "\n".join(DEFAULT_ROLE_OPTIONS))
        defaults_box.configure(state="disabled")

        ttk.Label(
            roles_frame,
            text=(
                "Voci personalizzate (una per riga).\n"
                "Sono aggiunte dopo le voci predefinite e possono essere modificate in qualsiasi momento."
            ),
        ).pack(anchor="w", pady=(0, 4))

        self.custom_roles_text = tk.Text(roles_frame, height=8, width=50)
        self.custom_roles_text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.custom_roles_text.bind("<KeyRelease>", self._update_preview)

        custom_values = self.current_cfg.get("custom_role_options")
        if isinstance(custom_values, list) and custom_values:
            self.custom_roles_text.insert("1.0", "\n".join(custom_values))

        current_preview = ttk.LabelFrame(roles_frame, text="Anteprima voci disponibili")
        current_preview.pack(fill=tk.X, pady=(4, 10))
        self.preview_var = tk.StringVar(value=self._format_preview(self.current_cfg))
        ttk.Label(current_preview, textvariable=self.preview_var, wraplength=380).pack(anchor="w", padx=6, pady=4)

        # Client posta
        ttk.Label(mail_frame, text="Percorso Thunderbird Portable", font="AppBold").grid(row=0, column=0, sticky="w")
        self.th_path_var = tk.StringVar(value=(self.current_cfg.get("thunderbird_path") or ""))
        entry = ttk.Entry(mail_frame, textvariable=self.th_path_var, width=60)
        entry.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        ttk.Button(mail_frame, text="Sfoglia...", command=self._browse_thunderbird).grid(row=1, column=1, sticky="w", padx=(6, 0))
        ttk.Label(mail_frame, text="Lascia vuoto per usare il default configurato in config.py", foreground="gray40").grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        mail_frame.columnconfigure(0, weight=1)

        # Backup
        ttk.Label(backup_frame, text="Cartella backup locale", font="AppBold").grid(row=0, column=0, sticky="w")
        self.backup_dir_var = tk.StringVar(value=(self.current_cfg.get("backup_dir") or ""))
        backup_entry = ttk.Entry(backup_frame, textvariable=self.backup_dir_var, width=60)
        backup_entry.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        ttk.Button(backup_frame, text="Sfoglia...", command=self._browse_backup_dir).grid(row=1, column=1, sticky="w", padx=(6, 0))
        ttk.Label(
            backup_frame,
            text="Lascia vuoto per usare la cartella 'backup' di default (accanto all'app).",
            foreground="gray40",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        ttk.Separator(backup_frame, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 10))

        ttk.Label(backup_frame, text="Repository backup (cloud)", font="AppBold").grid(row=4, column=0, sticky="w")
        self.backup_repo_dir_var = tk.StringVar(value=(self.current_cfg.get("backup_repo_dir") or ""))
        repo_entry = ttk.Entry(backup_frame, textvariable=self.backup_repo_dir_var, width=60)
        repo_entry.grid(row=5, column=0, sticky="ew", pady=(4, 4))
        ttk.Button(backup_frame, text="Sfoglia...", command=self._browse_backup_repo_dir).grid(row=5, column=1, sticky="w", padx=(6, 0))
        ttk.Label(
            backup_frame,
            text=(
                "Se valorizzato, ogni backup creato viene copiato anche qui. "
                "Nota: la variabile ambiente GESTIONESOCI_BACKUP_REPO_DIR ha priorità."
            ),
            foreground="gray40",
            wraplength=420,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(2, 0))
        backup_frame.columnconfigure(0, weight=1)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Salva", command=self._save_preferences).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(btn_frame, text="Reimposta", command=self._reset_custom_roles).pack(side=tk.LEFT)

        # Categorie documenti
        self._build_categories_tab(categories_frame)

    def _format_preview(self, cfg_override: dict | None = None) -> str:
        """Return a readable preview string filtered from empty values."""
        options = [role for role in get_role_options(cfg_override) if role]
        return ", ".join(options) if options else "Nessuna voce disponibile"

    def _reset_custom_roles(self) -> None:
        """Clear custom roles text area."""
        self.custom_roles_text.delete("1.0", tk.END)
        self._update_preview()

    def _build_categories_tab(self, frame: ttk.Frame) -> None:
        """Build the 'Tipi documenti' preferences tab."""
        ttk.Label(
            frame,
            text="Tipi documenti Soci",
            font="AppBold",
        ).grid(row=0, column=0, sticky="w")

        defaults_member = tk.Text(frame, height=5, width=46, state="disabled", wrap=tk.WORD)
        defaults_member.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        defaults_member.configure(state="normal")
        defaults_member.insert("1.0", "\n".join(DOCUMENT_CATEGORIES))
        defaults_member.configure(state="disabled")

        ttk.Label(frame, text="Tipi personalizzati Soci (uno per riga):").grid(row=2, column=0, sticky="w")
        self.custom_doc_categories_text = tk.Text(frame, height=6, width=56)
        self.custom_doc_categories_text.grid(row=3, column=0, sticky="nsew", pady=(4, 8))
        self.custom_doc_categories_text.bind("<KeyRelease>", self._update_categories_preview)

        member_custom = self.current_cfg.get("custom_document_categories")
        if isinstance(member_custom, list) and member_custom:
            self.custom_doc_categories_text.insert("1.0", "\n".join(member_custom))

        self.member_categories_preview_var = tk.StringVar(value=self._format_member_categories_preview(self.current_cfg))
        member_preview = ttk.LabelFrame(frame, text="Anteprima tipi Soci")
        member_preview.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(member_preview, textvariable=self.member_categories_preview_var, wraplength=420).pack(
            anchor="w", padx=6, pady=4
        )

        ttk.Separator(frame, orient="horizontal").grid(row=5, column=0, sticky="ew", pady=(6, 10))

        ttk.Label(
            frame,
            text="Tipi documenti Sezione",
            font="AppBold",
        ).grid(row=6, column=0, sticky="w")

        defaults_section = tk.Text(frame, height=6, width=46, state="disabled", wrap=tk.WORD)
        defaults_section.grid(row=7, column=0, sticky="ew", pady=(4, 8))
        defaults_section.configure(state="normal")
        defaults_section.insert("1.0", "\n".join(SECTION_DOCUMENT_CATEGORIES))
        defaults_section.configure(state="disabled")

        ttk.Label(frame, text="Tipi personalizzati Sezione (uno per riga):").grid(row=8, column=0, sticky="w")
        self.custom_section_categories_text = tk.Text(frame, height=6, width=56)
        self.custom_section_categories_text.grid(row=9, column=0, sticky="nsew", pady=(4, 8))
        self.custom_section_categories_text.bind("<KeyRelease>", self._update_categories_preview)

        section_custom = self.current_cfg.get("custom_section_document_categories")
        if isinstance(section_custom, list) and section_custom:
            self.custom_section_categories_text.insert("1.0", "\n".join(section_custom))

        self.section_categories_preview_var = tk.StringVar(value=self._format_section_categories_preview(self.current_cfg))
        section_preview = ttk.LabelFrame(frame, text="Anteprima tipi Sezione")
        section_preview.grid(row=10, column=0, sticky="ew")
        ttk.Label(section_preview, textvariable=self.section_categories_preview_var, wraplength=420).pack(
            anchor="w", padx=6, pady=4
        )

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        frame.rowconfigure(9, weight=1)

    def _format_member_categories_preview(self, cfg_override: dict | None = None) -> str:
        """Return a readable preview for member document categories."""
        cfg = cfg_override or {}
        custom = cfg.get("custom_document_categories") if isinstance(cfg, dict) else None
        if not isinstance(custom, list):
            custom = []
        cats = build_document_categories(custom)
        return ", ".join(cats) if cats else "Nessuna categoria disponibile"

    def _format_section_categories_preview(self, cfg_override: dict | None = None) -> str:
        """Return a readable preview for section document categories."""
        cfg = cfg_override or {}
        custom = cfg.get("custom_section_document_categories") if isinstance(cfg, dict) else None
        if not isinstance(custom, list):
            custom = []
        cats = build_section_document_categories(custom)
        return ", ".join(cats) if cats else "Nessuna categoria disponibile"

    def _update_categories_preview(self, *_args) -> None:
        member_lines = self.custom_doc_categories_text.get("1.0", tk.END).splitlines()
        member_custom = sanitize_custom_document_categories(member_lines)
        self.member_categories_preview_var.set(self._format_member_categories_preview({"custom_document_categories": member_custom}))

        section_lines = self.custom_section_categories_text.get("1.0", tk.END).splitlines()
        section_custom = sanitize_custom_section_document_categories(section_lines)
        self.section_categories_preview_var.set(
            self._format_section_categories_preview({"custom_section_document_categories": section_custom})
        )

    def _update_preview(self, *_args) -> None:
        """Update live preview whenever text changes."""
        raw_lines = self.custom_roles_text.get("1.0", tk.END).splitlines()
        sanitized = sanitize_custom_role_options(raw_lines)
        preview_cfg = {"custom_role_options": sanitized}
        self.preview_var.set(self._format_preview(preview_cfg))

    def _save_preferences(self) -> None:
        """Persist preferences and propagate the changes."""
        lines = self.custom_roles_text.get("1.0", tk.END).splitlines()
        try:
            updated_cfg = save_custom_role_options(lines)
            cfg = load_config()
            cfg["thunderbird_path"] = (self.th_path_var.get() or "").strip()
            cfg["backup_dir"] = (self.backup_dir_var.get() or "").strip()
            cfg["backup_repo_dir"] = (self.backup_repo_dir_var.get() or "").strip()

            member_lines = self.custom_doc_categories_text.get("1.0", tk.END).splitlines()
            cfg["custom_document_categories"] = sanitize_custom_document_categories(member_lines)
            section_lines = self.custom_section_categories_text.get("1.0", tk.END).splitlines()
            cfg["custom_section_document_categories"] = sanitize_custom_section_document_categories(section_lines)

            save_config(cfg)
            updated_cfg = cfg
        except Exception as exc:  # pragma: no cover - unexpected I/O errors
            messagebox.showerror("Preferenze", f"Impossibile salvare le preferenze:\n{exc}")
            return

        if self.on_save:
            try:
                self.on_save(updated_cfg)
            except Exception as exc:  # pragma: no cover - callbacks are external
                messagebox.showwarning("Preferenze", f"Preferenze salvate ma aggiornamento UI fallito:\n{exc}")
        self.destroy()

    def _browse_thunderbird(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Seleziona eseguibile Thunderbird",
            filetypes=[("Eseguibili", "*.exe"), ("Tutti i file", "*.*")],
        )
        if path:
            self.th_path_var.set(path)

    def _browse_backup_dir(self) -> None:
        path = filedialog.askdirectory(parent=self, title="Seleziona cartella backup")
        if path:
            self.backup_dir_var.set(path)

    def _browse_backup_repo_dir(self) -> None:
        path = filedialog.askdirectory(parent=self, title="Seleziona cartella repository backup")
        if path:
            self.backup_repo_dir_var.set(path)
