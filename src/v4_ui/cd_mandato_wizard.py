# -*- coding: utf-8 -*-

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import cast

from utils import ddmmyyyy_to_iso


class _SocioPickerDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, *, initial_query: str = ""):
        super().__init__(parent)
        self.title("Seleziona socio")
        self.resizable(True, True)
        self.transient(cast(tk.Wm, parent))
        self.grab_set()

        self.result: dict | None = None
        self._all_rows: list[dict] = []

        self.var_q = tk.StringVar(value=(initial_query or "").strip())

        self._build_ui()
        self._load_rows()
        self._apply_filter()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda _e: self._on_cancel())

    def _build_ui(self):
        root = ttk.Frame(self)
        root.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top = ttk.Frame(root)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Cerca:").pack(side=tk.LEFT)
        ent = ttk.Entry(top, textvariable=self.var_q)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        ent.bind("<KeyRelease>", lambda _e: self._apply_filter())

        mid = ttk.Frame(root)
        mid.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        sb_v = ttk.Scrollbar(mid, orient="vertical")
        self.tv = ttk.Treeview(
            mid,
            columns=("id", "matricola", "nominativo"),
            show="headings",
            displaycolumns=("matricola", "nominativo"),
            yscrollcommand=sb_v.set,
        )
        sb_v.config(command=self.tv.yview)

        self.tv.heading("matricola", text="Matricola")
        self.tv.heading("nominativo", text="Nominativo")

        self.tv.column("id", width=0, stretch=False)
        self.tv.column("matricola", width=90)
        self.tv.column("nominativo", width=380)

        self.tv.grid(row=0, column=0, sticky="nsew")
        sb_v.grid(row=0, column=1, sticky="ns")
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(0, weight=1)

        self.tv.bind("<Double-1>", lambda _e: self._on_ok())

        bottom = ttk.Frame(root)
        bottom.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(bottom, text="Inserisci manualmente", command=self._on_manual).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Annulla", command=self._on_cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(bottom, text="Seleziona", command=self._on_ok).pack(side=tk.RIGHT)

    def _load_rows(self):
        try:
            from database import fetch_all

            rows = fetch_all(
                """
                SELECT id, matricola, nominativo, nome, cognome
                FROM soci
                WHERE deleted_at IS NULL
                ORDER BY COALESCE(cognome,''), COALESCE(nome,''), COALESCE(nominativo,'')
                """
            )
            self._all_rows = [dict(r) for r in rows or []]
        except Exception:
            self._all_rows = []

    @staticmethod
    def _format_row(r: dict) -> str:
        nominativo = str(r.get("nominativo") or "").strip()
        nome = str(r.get("nome") or "").strip()
        cognome = str(r.get("cognome") or "").strip()
        if nominativo:
            base = nominativo
        else:
            base = (f"{cognome} {nome}").strip()
        mat = str(r.get("matricola") or "").strip()
        if mat:
            return f"{base} ({mat})" if base else f"Socio {mat}"
        return base or "Socio"

    def _apply_filter(self):
        q = (self.var_q.get() or "").strip().lower()
        for iid in self.tv.get_children():
            self.tv.delete(iid)

        def match(r: dict) -> bool:
            if not q:
                return True
            hay = " ".join(
                [
                    str(r.get("matricola") or ""),
                    str(r.get("nominativo") or ""),
                    str(r.get("cognome") or ""),
                    str(r.get("nome") or ""),
                ]
            ).lower()
            return q in hay

        for r in self._all_rows:
            if not match(r):
                continue
            try:
                rid = r.get("id")
                if rid is None:
                    continue
                sid = int(str(rid))
            except Exception:
                continue
            mat = str(r.get("matricola") or "").strip()
            display = self._format_row(r)
            self.tv.insert("", tk.END, iid=f"s{sid}", values=(str(sid), mat, display))

    def _on_ok(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("Seleziona socio", "Selezionare un socio dalla lista oppure usare inserimento manuale.")
            return
        vals = self.tv.item(sel[0], "values")
        socio_id_raw = vals[0] if len(vals) > 0 else ""
        nominativo = vals[2] if len(vals) > 2 else ""
        try:
            socio_id = int(str(socio_id_raw))
        except Exception:
            socio_id = None
        self.result = {"mode": "socio", "socio_id": socio_id, "nome": str(nominativo or "").strip()}
        self.destroy()

    def _on_manual(self):
        self.result = {"mode": "manual"}
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


def _ask_member_manual_name(parent: tk.Misc, *, initial_value: str = "") -> str | None:
    nome = simpledialog.askstring("Componente CD", "Nominativo", initialvalue=str(initial_value or ""), parent=parent)
    if nome is None:
        return None
    nome = nome.strip()
    return nome or None


class _RolePickerDialog(simpledialog.Dialog):
    """Dialog with dropdown to select or edit the role."""

    def __init__(self, parent, *, roles: list[str] | tuple[str, ...], initial_role: str):
        self._roles = tuple(roles)
        self._initial_role = initial_role
        super().__init__(parent, title="Ruolo componente CD")

    def body(self, master):
        ttk.Label(master, text="Seleziona il ruolo").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.var = tk.StringVar(value=self._initial_role)
        self.combo = ttk.Combobox(master, textvariable=self.var, values=self._roles, state="normal", width=30)
        self.combo.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.combo.focus_set()
        return self.combo

    def apply(self):
        self.result = (self.var.get() or "").strip()



class CdMandatoWizard(tk.Toplevel):
    def _backup_before_save(self):
        """Esegue un backup automatico prima di modifiche strutturali ai mandati."""
        try:
            from backup import run_incremental_backup
            run_incremental_backup(interactive=False)
        except Exception as exc:
            messagebox.showwarning(
                "Backup non riuscito",
                f"Backup automatico non riuscito: {exc}\nProcedere solo se si dispone di un backup recente."
            )

    """Wizard/dialog per aggiornare Mandato + composizione Consiglio Direttivo."""

    DEFAULT_CARICHE = (
        "Presidente",
        "Vicepresidente",
        "Segretario",
        "Tesoriere",
        "Consigliere",
        "Sindaco/Revisore",
        "Altro",
    )

    def __init__(self, parent: tk.Misc, *, on_saved=None):
        super().__init__(parent)
        self.title("Mandato Consiglio Direttivo")
        self.resizable(True, True)
        self.transient(cast(tk.Wm, parent))
        self.grab_set()

        self.on_saved = on_saved
        self.result = None

        self._selected_mandato_id: int | None = None
        self._mandato_display_to_id: dict[str, int | None] = {}
        self._autofill_attempted = False

        self.var_label = tk.StringVar()
        self.var_start = tk.StringVar()
        self.var_end = tk.StringVar()
        self.var_note = tk.StringVar()
        self.var_is_active = tk.BooleanVar(value=True)

        self._build_ui()
        self._reload_mandati_list()
        self._load_current()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda _e: self._on_cancel())

    def _build_ui(self):
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        frm = ttk.LabelFrame(container, text="Periodo mandato")
        frm.pack(fill=tk.X, padx=0, pady=(0, 10))

        ttk.Label(frm, text="Mandato").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.var_pick = tk.StringVar()
        self.combo_pick = ttk.Combobox(frm, textvariable=self.var_pick, state="readonly", width=35, values=())
        self.combo_pick.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        self.combo_pick.bind("<<ComboboxSelected>>", lambda _e: self._on_pick_mandato())

        ttk.Button(frm, text="Nuovo", command=self._new_mandato).grid(row=0, column=2, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(frm, text="Attivo", variable=self.var_is_active).grid(row=0, column=3, sticky="w", padx=6, pady=4)

        ttk.Label(frm, text="Etichetta (es. Mandato 2023-2025)").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm, textvariable=self.var_label, width=30).grid(row=1, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

        ttk.Label(frm, text="Inizio").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm, textvariable=self.var_start, width=20).grid(row=2, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(frm, text="Fine").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm, textvariable=self.var_end, width=20).grid(row=3, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(frm, text="Note").grid(row=4, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frm, textvariable=self.var_note).grid(row=4, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

        frm.columnconfigure(1, weight=1)

        comp = ttk.LabelFrame(container, text="Componenti e cariche")
        comp.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(comp)
        toolbar.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(toolbar, text="Aggiungi", command=self._add_member).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Modifica", command=self._edit_member).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Rimuovi", command=self._remove_member).pack(side=tk.LEFT, padx=2)

        frame = ttk.Frame(comp)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        sb_v = ttk.Scrollbar(frame, orient="vertical")
        self.tv = ttk.Treeview(
            frame,
            columns=("socio_id", "carica", "nome", "note"),
            show="headings",
            displaycolumns=("carica", "nome", "note"),
            yscrollcommand=sb_v.set,
        )
        sb_v.config(command=self.tv.yview)

        self.tv.heading("carica", text="Carica")
        self.tv.heading("nome", text="Nominativo")
        self.tv.heading("note", text="Note")

        self.tv.column("socio_id", width=0, stretch=False)
        self.tv.column("carica", width=160)
        self.tv.column("nome", width=320)
        self.tv.column("note", width=260)

        self.tv.grid(row=0, column=0, sticky="nsew")
        sb_v.grid(row=0, column=1, sticky="ns")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        bottom = ttk.Frame(container)
        bottom.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(bottom, text="Annulla", command=self._on_cancel).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bottom, text="Salva", command=self._on_save).pack(side=tk.RIGHT, padx=4)

    def _load_current(self):
        try:
            from cd_mandati import get_active_cd_mandato

            cur = get_active_cd_mandato()
        except Exception:
            cur = None

        if cur:
            try:
                raw_id = cur.get("id")
                self._selected_mandato_id = int(str(raw_id)) if raw_id is not None and str(raw_id).strip() else None
            except Exception:
                self._selected_mandato_id = None
            self.var_label.set(str(cur.get("label") or ""))
            self.var_start.set(str(cur.get("start_date") or ""))
            self.var_end.set(str(cur.get("end_date") or ""))
            self.var_note.set(str(cur.get("note") or ""))
            self.var_is_active.set(True)
            for row in self.tv.get_children():
                self.tv.delete(row)
            for idx, m in enumerate(cur.get("composizione") or [], start=1):
                iid = f"m{idx}"
                socio_id = m.get("socio_id")
                try:
                    socio_id_s = str(int(socio_id)) if socio_id is not None and str(socio_id).strip() else ""
                except Exception:
                    socio_id_s = ""
                self.tv.insert(
                    "",
                    tk.END,
                    iid=iid,
                    values=(
                        socio_id_s,
                        str(m.get("carica") or ""),
                        str(m.get("nome") or ""),
                        str(m.get("note") or ""),
                    ),
                )
        else:
            # Prefill per triennio corrente citato (2023-2025)
            if not self.var_label.get().strip():
                self.var_label.set("2023-2025")
            if not self.var_start.get().strip():
                self.var_start.set("2023-01-01")
            if not self.var_end.get().strip():
                self.var_end.set("2025-12-31")

        # Select the active mandate in the dropdown if available
        try:
            if self._selected_mandato_id is not None:
                for display, mid in self._mandato_display_to_id.items():
                    if mid == self._selected_mandato_id:
                        self.var_pick.set(display)
                        break
        except Exception:
            pass

        self._maybe_autofill_from_roles()

    def _reload_mandati_list(self):
        try:
            from cd_mandati import get_all_cd_mandati

            all_rows = get_all_cd_mandati()
        except Exception:
            all_rows = []

        self._mandato_display_to_id = {"(nuovo)": None}
        values = ["(nuovo)"]

        for m in all_rows:
            mid = m.get("id")
            try:
                mid_i = int(str(mid)) if mid is not None and str(mid).strip() else None
            except Exception:
                continue

            if mid_i is None:
                continue

            lbl = str(m.get("label") or "").strip()
            s = str(m.get("start_date") or "").strip()
            e = str(m.get("end_date") or "").strip()
            span = f"{s[:4]}-{e[:4]}" if s and e else ""
            base = lbl or (f"Mandato {span}" if span else f"Mandato ID {mid_i}")
            if span and span not in base:
                base = f"{base} ({span})"
            if int(m.get("is_active") or 0) == 1:
                base = f"{base} [attivo]"

            display = base
            if display in self._mandato_display_to_id and self._mandato_display_to_id.get(display) != mid_i:
                display = f"{display} #{mid_i}"

            self._mandato_display_to_id[display] = mid_i
            values.append(display)

        try:
            self.combo_pick.configure(values=values)
            if not self.var_pick.get().strip():
                self.var_pick.set(values[0] if values else "(nuovo)")
        except Exception:
            pass

    def _next_member_iid(self) -> str:
        """Return a unique iid for the Treeview rows (avoids duplicate mX ids)."""
        existing = set(self.tv.get_children())
        counter = 1
        while True:
            candidate = f"m{counter}"
            if candidate not in existing:
                return candidate
            counter += 1

    def _composition_is_empty(self) -> bool:
        return len(self.tv.get_children()) == 0

    def _fetch_roles_from_members(self) -> list[dict]:
        try:
            from database import fetch_all

            rows = fetch_all(
                """
                SELECT id, nominativo, nome, cognome, cd_ruolo
                FROM soci
                WHERE deleted_at IS NULL AND TRIM(COALESCE(cd_ruolo, '')) <> ''
                ORDER BY cognome, nome
                """
            )
        except Exception:
            return []

        role_map: list[dict] = []
        for r in rows or []:
            role_raw = str((r.get("cd_ruolo") if hasattr(r, "get") else r[4]) or "").strip().lower()
            if not role_raw:
                continue
            if role_raw.startswith("pres"):
                carica = "Presidente"
            elif "vice" in role_raw:
                carica = "Vicepresidente"
            elif role_raw.startswith("segr"):
                carica = "Segretario"
            elif role_raw.startswith("tes"):
                carica = "Tesoriere"
            elif "sindac" in role_raw or "revisor" in role_raw:
                carica = "Sindaco/Revisore"
            elif role_raw.startswith("consig"):
                carica = "Consigliere"
            else:
                continue

            socio_id = None
            try:
                socio_id_val = r.get("id") if hasattr(r, "get") else r[0]
                socio_id = int(str(socio_id_val)) if socio_id_val is not None else None
            except Exception:
                socio_id = None

            nominativo = str((r.get("nominativo") if hasattr(r, "get") else r[1]) or "").strip()
            nome = str((r.get("nome") if hasattr(r, "get") else r[2]) or "").strip()
            cognome = str((r.get("cognome") if hasattr(r, "get") else r[3]) or "").strip()
            display_nome = nominativo if nominativo else f"{nome} {cognome}".strip()
            if not display_nome:
                display_nome = "Socio"

            role_map.append({
                "carica": carica,
                "nome": display_nome,
                "note": "",
                "socio_id": socio_id,
            })

        # Ordina per importanza carica
        order: dict[str, int] = {
            "Presidente": 1,
            "Vicepresidente": 2,
            "Segretario": 3,
            "Tesoriere": 4,
            "Sindaco/Revisore": 5,
            "Consigliere": 6,
        }
        role_map.sort(key=lambda x: order.get(str(x.get("carica") or ""), 99))
        return role_map

    def _maybe_autofill_from_roles(self):
        if self._autofill_attempted:
            return
        self._autofill_attempted = True

        if not self._composition_is_empty():
            return

        roles = self._fetch_roles_from_members()
        if not roles:
            return

        summary_lines = ["Ruoli trovati nei soci:"]
        for r in roles:
            summary_lines.append(f"- {r['carica']}: {r['nome']}")

        if not messagebox.askyesno(
            "Precompila mandato",
            "\n".join(summary_lines + ["", "Vuoi usare questi ruoli per compilare il mandato corrente?"])
        ):
            return

        for r in roles:
            socio_id_s = str(int(r["socio_id"])) if r.get("socio_id") else ""
            iid = self._next_member_iid()
            self.tv.insert("", tk.END, iid=iid, values=(socio_id_s, r["carica"], r["nome"], r["note"]))

    def _new_mandato(self):
        # Conferma se ci sono modifiche non salvate
        if self._composition_is_empty() is False and self._selected_mandato_id is None:
            if not messagebox.askyesno(
                "Attenzione",
                "Ci sono componenti inseriti non ancora salvati. Vuoi davvero creare un nuovo mandato e perdere le modifiche?"
            ):
                return
        self._selected_mandato_id = None
        self.var_pick.set("(nuovo)")
        self.var_label.set("")
        self.var_start.set("")
        self.var_end.set("")
        self.var_note.set("")
        self.var_is_active.set(False)
        for row in self.tv.get_children():
            self.tv.delete(row)
        self._autofill_attempted = False
        self._maybe_autofill_from_roles()

    def _on_pick_mandato(self):
        choice = (self.var_pick.get() or "").strip()
        mid = self._mandato_display_to_id.get(choice)
        if mid is None:
            self._new_mandato()
            return

        # Conferma se ci sono modifiche non salvate
        if self._composition_is_empty() is False and self._selected_mandato_id is None:
            if not messagebox.askyesno(
                "Attenzione",
                "Ci sono componenti inseriti non ancora salvati. Vuoi davvero cambiare mandato e perdere le modifiche?"
            ):
                return

        self._autofill_attempted = False

        try:
            from cd_mandati import get_cd_mandato_by_id

            m = get_cd_mandato_by_id(int(mid))
        except Exception:
            m = None

        if not m:
            return

        self._selected_mandato_id = int(mid)
        self.var_label.set(str(m.get("label") or ""))
        self.var_start.set(str(m.get("start_date") or ""))
        self.var_end.set(str(m.get("end_date") or ""))
        self.var_note.set(str(m.get("note") or ""))
        self.var_is_active.set(int(m.get("is_active") or 0) == 1)

        for row in self.tv.get_children():
            self.tv.delete(row)
        for idx, r in enumerate(m.get("composizione") or [], start=1):
            iid = f"m{idx}"
            socio_id = r.get("socio_id")
            try:
                socio_id_s = str(int(socio_id)) if socio_id is not None and str(socio_id).strip() else ""
            except Exception:
                socio_id_s = ""
            self.tv.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    socio_id_s,
                    str(r.get("carica") or ""),
                    str(r.get("nome") or ""),
                    str(r.get("note") or ""),
                ),
            )

        self._maybe_autofill_from_roles()

    def _ask_member_data(self, *, initial=None):
        initial = initial or {}

        # Socio selection (preferred) with manual fallback
        socio_id: int | None = None
        nome: str | None = None

        dlg = _SocioPickerDialog(self, initial_query=str(initial.get("nome") or ""))
        self.wait_window(dlg)
        if dlg.result is None:
            return None

        if dlg.result.get("mode") == "socio":
            socio_id = dlg.result.get("socio_id")
            nome = str(dlg.result.get("nome") or "").strip() or None
        else:
            nome = _ask_member_manual_name(self, initial_value=str(initial.get("nome") or ""))
            if nome is None:
                return None

        if not nome:
            messagebox.showwarning("Componente CD", "Inserire un nominativo.")
            return None
        role_dialog = _RolePickerDialog(
            self,
            roles=self.DEFAULT_CARICHE,
            initial_role=str(initial.get("carica") or "Consigliere"),
        )
        carica = role_dialog.result
        if carica is None:
            return None
        carica = str(carica).strip() or "Consigliere"

        note = simpledialog.askstring("Componente CD", "Note (opzionale)", initialvalue=str(initial.get("note") or ""), parent=self)
        if note is None:
            note = ""

        return {"nome": nome, "carica": carica, "note": note, "socio_id": socio_id}

    def _add_member(self):
        data = self._ask_member_data()
        if not data:
            return
        iid = self._next_member_iid()
        socio_id_s = str(int(data["socio_id"])) if data.get("socio_id") else ""
        self.tv.insert("", tk.END, iid=iid, values=(socio_id_s, data["carica"], data["nome"], data["note"]))

    def _edit_member(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("Componenti CD", "Selezionare una riga da modificare")
            return
        iid = sel[0]
        vals = self.tv.item(iid, "values")
        socio_id_raw = vals[0] if len(vals) > 0 else ""
        try:
            socio_id = int(str(socio_id_raw)) if str(socio_id_raw).strip() else None
        except Exception:
            socio_id = None
        initial = {
            "socio_id": socio_id,
            "carica": vals[1] if len(vals) > 1 else "",
            "nome": vals[2] if len(vals) > 2 else "",
            "note": vals[3] if len(vals) > 3 else "",
        }
        data = self._ask_member_data(initial=initial)
        if not data:
            return
        socio_id_s = str(int(data["socio_id"])) if data.get("socio_id") else ""
        self.tv.item(iid, values=(socio_id_s, data["carica"], data["nome"], data["note"]))

    def _remove_member(self):
        sel = self.tv.selection()
        if not sel:
            return
        for iid in sel:
            self.tv.delete(iid)

    def _on_save(self):
        # Backup automatico prima di ogni salvataggio
        self._backup_before_save()
        # Parse/normalize dates (accept DD/MM/YYYY or ISO)
        try:
            start_iso = ddmmyyyy_to_iso(self.var_start.get())
            end_iso = ddmmyyyy_to_iso(self.var_end.get())
        except Exception as exc:
            messagebox.showerror("Mandato CD", f"Date non valide: {exc}")
            return

        if not start_iso or not end_iso:
            messagebox.showerror("Mandato CD", "Inserire sia data inizio che data fine")
            return
        if start_iso > end_iso:
            messagebox.showerror("Mandato CD", "La data di inizio non può essere successiva alla data di fine")
            return

        label = (self.var_label.get() or "").strip()
        note = (self.var_note.get() or "").strip()

        composizione = []
        for iid in self.tv.get_children():
            vals = self.tv.item(iid, "values")
            socio_id_raw = vals[0] if len(vals) > 0 else ""
            carica = vals[1] if len(vals) > 1 else ""
            nome = vals[2] if len(vals) > 2 else ""
            note_riga = vals[3] if len(vals) > 3 else ""
            try:
                socio_id = int(str(socio_id_raw)) if str(socio_id_raw).strip() else None
            except Exception:
                socio_id = None
            composizione.append({"carica": str(carica), "nome": str(nome), "note": str(note_riga), "socio_id": socio_id})

        try:
            from cd_mandati import save_cd_mandato

            mandato_id = save_cd_mandato(
                mandato_id=self._selected_mandato_id,
                label=label,
                start_date=start_iso,
                end_date=end_iso,
                composizione=composizione,
                note=note,
                is_active=bool(self.var_is_active.get()),
            )
        except Exception as exc:
            messagebox.showerror("Mandato CD", f"Errore salvataggio: {exc}")
            return

        if mandato_id < 0:
            messagebox.showerror("Mandato CD", "Impossibile salvare il mandato")
            return

        self.result = {"id": mandato_id, "label": label, "start_date": start_iso, "end_date": end_iso}
        if callable(self.on_saved):
            try:
                self.on_saved(self.result)
            except Exception:
                pass

        self._autofill_attempted = False

        # Refresh list so the newly created mandate is selectable
        try:
            self._reload_mandati_list()
        except Exception:
            pass

        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
