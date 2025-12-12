# -*- coding: utf-8 -*-
"""Dialog to update common member fields in batch."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, List, Sequence

from preferences import get_role_options

from database import exec_query


class BatchFieldEditDialog(tk.Toplevel):
    """Dialog that lets the operator update selected fields for many members."""

    FIELD_CONFIG = (
        {"key": "attivo", "label": "Attivo", "type": "boolean"},
        {"key": "voto", "label": "Diritto di voto", "type": "boolean"},
        {"key": "privacy_signed", "label": "Privacy firmata", "type": "boolean"},
        {
            "key": "socio",
            "label": "Tipo socio",
            "type": "combo",
            "options": ("", "HAM", "RCL", "THR"),
        },
        {
            "key": "cd_ruolo",
            "label": "Ruolo / Stato",
            "type": "combo",
            "options": None,
        },
        {"key": "q0", "label": "Quota anno (Q0)", "type": "text"},
        {"key": "q1", "label": "Quota anno -1 (Q1)", "type": "text"},
        {"key": "q2", "label": "Quota anno -2 (Q2)", "type": "text"},
    )

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel | None,
        members: Sequence[dict],
        *,
        on_complete: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("Modifica campi comuni")
        self.resizable(False, False)
        if parent is not None:
            self.transient(parent)
        self.grab_set()

        self.members: List[dict] = [dict(m) for m in members]
        self.on_complete = on_complete
        self.field_states: dict[str, dict] = {}

        self._build_ui()
        self.bind("<Escape>", lambda _e: self.destroy())

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=f"Soci selezionati: {len(self.members)}",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        members_frame = ttk.LabelFrame(main_frame, text="Elenco soci", padding=6)
        members_frame.pack(fill=tk.X, expand=False, pady=(6, 10))

        columns = ("id", "nominativo", "matricola")
        tree = ttk.Treeview(
            members_frame,
            columns=columns,
            show="headings",
            height=6,
        )
        tree.pack(fill=tk.X, expand=True)
        tree.heading("id", text="ID")
        tree.heading("nominativo", text="Nominativo")
        tree.heading("matricola", text="Matricola")
        tree.column("id", width=70, anchor="center")
        tree.column("nominativo", width=240)
        tree.column("matricola", width=100)

        for member in self.members:
            tree.insert(
                "",
                tk.END,
                values=(member.get("id"), member.get("nominativo"), member.get("matricola")),
            )

        ttk.Label(
            main_frame,
            text="Seleziona i campi da aggiornare e specifica il nuovo valore.",
        ).pack(anchor="w", pady=(4, 2))

        fields_frame = ttk.LabelFrame(main_frame, text="Campi disponibili", padding=6)
        fields_frame.pack(fill=tk.BOTH, expand=True)

        role_options = get_role_options()

        for idx, field in enumerate(self.FIELD_CONFIG):
            field_cfg = dict(field)
            if field_cfg.get("key") == "cd_ruolo" and field_cfg.get("type") == "combo":
                field_cfg["options"] = role_options
            row = ttk.Frame(fields_frame)
            row.grid(row=idx, column=0, sticky="ew", pady=2)
            fields_frame.columnconfigure(0, weight=1)

            apply_var = tk.BooleanVar(value=False)
            chk = ttk.Checkbutton(
                row,
                text="",
                variable=apply_var,
                command=lambda key=field_cfg["key"]: self._toggle_field(key),
            )
            chk.pack(side=tk.LEFT, padx=(0, 6))

            ttk.Label(row, text=field_cfg["label"], width=24).pack(side=tk.LEFT)

            control_info = self._create_field_widget(row, field_cfg)
            self.field_states[field_cfg["key"]] = {
                "apply_var": apply_var,
                "value_var": control_info["var"],
                "widget": control_info["widget"],
                "type": field_cfg["type"],
                "options": field_cfg.get("options"),
                "enabled_state": control_info["enabled_state"],
            }
            self._toggle_field(field_cfg["key"])

        # Action buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Aggiorna", command=self._apply_changes).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

    def _create_field_widget(self, parent: ttk.Frame, field: dict) -> dict:
        f_type = field["type"]
        if f_type == "boolean":
            value_var = tk.StringVar(value="")
            combo = ttk.Combobox(parent, textvariable=value_var, values=("Si", "No"), state="readonly")
            combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            return {"var": value_var, "widget": combo, "enabled_state": "readonly"}
        if f_type == "combo":
            value_var = tk.StringVar(value="")
            combo = ttk.Combobox(parent, textvariable=value_var, values=field.get("options") or ("",), state="readonly")
            combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            return {"var": value_var, "widget": combo, "enabled_state": "readonly"}

        # Default to simple entry
        value_var = tk.StringVar(value="")
        entry = ttk.Entry(parent, textvariable=value_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        return {"var": value_var, "widget": entry, "enabled_state": "normal"}

    def _toggle_field(self, key: str) -> None:
        state = self.field_states[key]
        widget = state["widget"]
        enabled_state = state["enabled_state"]
        if state["apply_var"].get():
            widget.configure(state=enabled_state)
        else:
            widget.configure(state="disabled")
            state["value_var"].set("")

    def _collect_updates(self) -> dict[str, object] | None:
        updates: dict[str, object] = {}
        for key, cfg in self.field_states.items():
            if not cfg["apply_var"].get():
                continue
            raw_value = cfg["value_var"].get()
            f_type = cfg["type"]
            if f_type == "boolean":
                if raw_value not in ("Si", "No"):
                    messagebox.showwarning("Modifica campi", f"Seleziona un valore valido per '{key}'.")
                    return None
                updates[key] = 1 if raw_value == "Si" else 0
            elif f_type == "text":
                updates[key] = raw_value.strip() if raw_value.strip() else None
            else:
                updates[key] = raw_value.strip() if isinstance(raw_value, str) else raw_value
        return updates

    def _apply_changes(self) -> None:
        updates = self._collect_updates()
        if updates is None:
            return
        if not updates:
            messagebox.showinfo("Modifica campi", "Nessun campo selezionato per l'aggiornamento.")
            return

        placeholders = ", ".join(f"{col} = ?" for col in updates.keys())
        params_base = list(updates.values())

        updated = 0
        errors: list[str] = []
        for member in self.members:
            try:
                params = params_base + [member["id"]]
                sql = f"UPDATE soci SET {placeholders} WHERE id = ?"
                exec_query(sql, params)
                updated += 1
            except Exception as exc:  # pragma: no cover - UI feedback
                errors.append(f"ID {member.get('id')}: {exc}")

        if errors:
            messagebox.showerror(
                "Modifica campi",
                "Impossibile aggiornare alcuni soci:\n" + "\n".join(errors[:5]),
            )

        if updated:
            if self.on_complete:
                self.on_complete(updated)
            messagebox.showinfo("Modifica campi", f"Aggiornamento completato per {updated} socio/i.")
            self.destroy()
        elif not errors:
            messagebox.showinfo("Modifica campi", "Nessun socio aggiornato.")