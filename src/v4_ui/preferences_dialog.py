# -*- coding: utf-8 -*-
"""Dialog for application preferences (customizable options)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable

from preferences import (
    DEFAULT_ROLE_OPTIONS,
    get_role_options,
    save_custom_role_options,
    sanitize_custom_role_options,
)
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
        container = ttk.Frame(self, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(container)
        notebook.pack(fill=tk.BOTH, expand=True)

        roles_frame = ttk.Frame(notebook, padding=10)
        notebook.add(roles_frame, text="Stato socio")

        mail_frame = ttk.Frame(notebook, padding=10)
        notebook.add(mail_frame, text="Client posta")

        ttk.Label(
            roles_frame,
            text="Voci predefinite (sempre disponibili):",
            font=("Segoe UI", 9, "bold"),
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
        ttk.Label(mail_frame, text="Percorso Thunderbird Portable", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.th_path_var = tk.StringVar(value=(self.current_cfg.get("thunderbird_path") or ""))
        entry = ttk.Entry(mail_frame, textvariable=self.th_path_var, width=60)
        entry.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        ttk.Button(mail_frame, text="Sfoglia...", command=self._browse_thunderbird).grid(row=1, column=1, sticky="w", padx=(6, 0))
        ttk.Label(mail_frame, text="Lascia vuoto per usare il default configurato in config.py", foreground="gray40").grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        mail_frame.columnconfigure(0, weight=1)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Salva", command=self._save_preferences).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(btn_frame, text="Reimposta", command=self._reset_custom_roles).pack(side=tk.LEFT)

    def _format_preview(self, cfg_override: dict | None = None) -> str:
        """Return a readable preview string filtered from empty values."""
        options = [role for role in get_role_options(cfg_override) if role]
        return ", ".join(options) if options else "Nessuna voce disponibile"

    def _reset_custom_roles(self) -> None:
        """Clear custom roles text area."""
        self.custom_roles_text.delete("1.0", tk.END)
        self._update_preview()

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
