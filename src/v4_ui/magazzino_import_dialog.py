# -*- coding: utf-8 -*-
"""Wizard dialog that imports inventory items from CSV or Excel."""

from __future__ import annotations

import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import logging
from datetime import datetime

from magazzino_importer import (
    INVENTORY_FIELDS,
    InventoryImportError,
    apply_mapping,
    auto_detect_mapping,
    normalize_inventory_code,
    read_source_file,
)
from magazzino_manager import create_item, get_item_by_inventory_number, update_item


logger = logging.getLogger("librosoci")

DEFAULT_MARCA = "N/D"
ATTENZIONE_PREFIX = "ATTENZIONE"


def _unique_header_name(existing: list[str], base: str) -> str:
    if base not in existing:
        return base
    idx = 2
    while f"{base}_{idx}" in existing:
        idx += 1
    return f"{base}_{idx}"


def add_virtual_notes_column(headers: list[str], rows: list[dict]) -> tuple[list[str], list[dict], str | None]:
    """Add a virtual column that composes a richer note from multiple fields.

    This is especially useful for inventory exports where useful context is spread
    across columns like UBICAZIONE/MATRICOLA/PROVENIENZA and notes are separate.
    """

    # Case-insensitive header lookup preserving original casing.
    lookup = {str(h).strip().lower(): h for h in headers}
    candidates = {
        "ubicazione": lookup.get("ubicazione"),
        "matricola": lookup.get("matricola"),
        "provenienza": lookup.get("provenienza"),
        "altre_notizie": lookup.get("altre notizie"),
        "doc_fisc": lookup.get("doc fisc/prov."),
        "valore_acq": lookup.get("valore acq €") or lookup.get("valore acq") or lookup.get("valore"),
    }

    # Only activate if we recognize at least one of the context columns.
    if not any(candidates.values()):
        return headers, rows, None

    virtual_header = _unique_header_name(headers, "NOTE (auto)")
    new_headers = list(headers) + [virtual_header]
    new_rows: list[dict] = []

    def get_value(row: dict, key: str) -> str:
        header = candidates.get(key)
        if not header:
            return ""
        value = row.get(header)
        return str(value).strip() if value is not None else ""

    for row in rows:
        parts: list[str] = []
        ubicazione = get_value(row, "ubicazione")
        matricola = get_value(row, "matricola")
        provenienza = get_value(row, "provenienza")
        doc_fisc = get_value(row, "doc_fisc")
        valore_acq = get_value(row, "valore_acq")
        altre_notizie = get_value(row, "altre_notizie")

        if ubicazione:
            parts.append(f"Ubicazione: {ubicazione}")
        if matricola:
            parts.append(f"Matricola: {matricola}")
        if provenienza:
            parts.append(f"Provenienza: {provenienza}")
        if doc_fisc:
            parts.append(f"Doc fisc/prov.: {doc_fisc}")
        if valore_acq:
            parts.append(f"Valore acq: {valore_acq}")
        if altre_notizie:
            parts.append(altre_notizie)

        composed = " — ".join(parts).strip() or None
        new_row = dict(row)
        new_row[virtual_header] = composed
        new_rows.append(new_row)

    return new_headers, new_rows, virtual_header

class MagazzinoImportDialog:
    def __init__(self, parent, on_complete=None):
        self.parent = parent
        self.on_complete = on_complete

        self.file_path: str | None = None
        self.headers: list[str] = []
        self.rows: list[dict] = []
        self.mapping: dict[str, str | None] = {field["key"]: None for field in INVENTORY_FIELDS}
        self.selected_fields: dict[str, bool] = {field["key"]: True for field in INVENTORY_FIELDS}
        self.duplicate_mode = tk.StringVar(value="update_empty")
        self.import_stats = {"created": 0, "updated": 0, "skipped": 0}
        self.failed_rows: list[dict[str, str]] = []
        self.btn_export_errors: ttk.Button | None = None

        # UI widgets that exist only on specific pages (they get destroyed on page change).
        self.preview_tree: ttk.Treeview | None = None
        self.summary_label: ttk.Label | None = None

        self.win = tk.Toplevel(parent)
        self.win.title("Importa magazzino")
        self.win.geometry("780x620")
        self.win.transient(parent)
        self.win.grab_set()

        try:
            from .styles import ensure_app_named_fonts

            ensure_app_named_fonts(self.win.winfo_toplevel())
        except Exception:
            pass

        self.pages = [
            ("Seleziona sorgente", self._build_page_file),
            ("Mappa i campi", self._build_page_mapping),
            ("Importa", self._build_page_import),
        ]
        self.current_page = 0

        self.main_frame = ttk.Frame(self.win)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.title_label = ttk.Label(self.main_frame, text="", font="AppTitle")
        self.title_label.pack(fill=tk.X, pady=(0, 10))

        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        nav = ttk.Frame(self.main_frame)
        nav.pack(fill=tk.X, pady=(10, 0))
        self.btn_prev = ttk.Button(nav, text="Indietro", command=self._prev_page)
        self.btn_prev.pack(side=tk.LEFT)
        self.btn_next = ttk.Button(nav, text="Avanti", command=self._next_page)
        self.btn_next.pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Annulla", command=self._cancel).pack(side=tk.RIGHT)

        self.progress_label = ttk.Label(self.main_frame, text="Pagina 1 di 3")
        self.progress_label.pack(fill=tk.X, pady=(6, 0))

        self.summary_text = tk.StringVar(value="Nessun file selezionato")

        self._show_page()

    # ------------------------------------------------------------------
    # Page builders
    # ------------------------------------------------------------------
    def _build_page_file(self):
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Seleziona un file CSV o Excel da analizzare").pack(anchor="w")
        ttk.Button(frame, text="Scegli file...", command=self._select_file).pack(anchor="w", pady=6)

        self.file_label = ttk.Label(frame, text="Nessun file selezionato", foreground="gray40")
        self.file_label.pack(anchor="w")

        self.file_info_label = ttk.Label(frame, text="")
        self.file_info_label.pack(anchor="w", pady=(0, 8))

        preview_group = ttk.LabelFrame(frame, text="Anteprima (prime 20 righe)")
        preview_group.pack(fill=tk.BOTH, expand=True, pady=6)

        self.preview_tree = ttk.Treeview(preview_group, show="headings", height=12)
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(preview_group, orient=tk.VERTICAL, command=self.preview_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_tree.configure(yscrollcommand=scrollbar.set)

    def _build_page_mapping(self):
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Associa le colonne del file ai campi del magazzino e scegli quali aggiornare",
        ).pack(anchor="w")
        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=6)
        ttk.Button(btns, text="Auto-mappa", command=self._auto_map).pack(side=tk.LEFT)
        ttk.Label(btns, text=" ").pack(side=tk.LEFT)
        ttk.Button(btns, text="Seleziona tutto", command=lambda: self._toggle_fields(True)).pack(side=tk.LEFT)
        ttk.Button(btns, text="Deseleziona tutto", command=lambda: self._toggle_fields(False)).pack(side=tk.LEFT, padx=(4, 0))

        canvas = tk.Canvas(frame)
        canvas.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=scroll.set)

        self.mapping_container = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=self.mapping_container, anchor="nw")
        self.mapping_container.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        header = ttk.Frame(self.mapping_container)
        header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(header, text="✓", width=4).pack(side=tk.LEFT)
        ttk.Label(header, text="Campo", width=24).pack(side=tk.LEFT)
        ttk.Label(header, text="Colonna sorgente").pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.mapping_widgets: dict[str, ttk.Combobox] = {}
        self.field_vars: dict[str, tk.BooleanVar] = {}
        for field in INVENTORY_FIELDS:
            row = ttk.Frame(self.mapping_container)
            row.pack(fill=tk.X, pady=2)
            var = tk.BooleanVar(value=True)
            if field["required"]:
                var.set(True)
                chk = ttk.Checkbutton(row, variable=var, width=4, state=tk.DISABLED)
            else:
                chk = ttk.Checkbutton(row, variable=var, width=4)
            chk.pack(side=tk.LEFT)
            self.field_vars[field["key"]] = var

            label = ttk.Label(row, text=field["label"], width=24, anchor="w")
            if field["required"]:
                label.configure(font="AppBold")
            label.pack(side=tk.LEFT)

            combo = ttk.Combobox(row, state="readonly", width=40)
            combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.mapping_widgets[field["key"]] = combo

        self._refresh_mapping_widgets()

    def _build_page_import(self):
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill=tk.BOTH, expand=True)

        summary = ttk.LabelFrame(frame, text="Riepilogo")
        summary.pack(fill=tk.X, pady=6)
        self.summary_label = ttk.Label(summary, textvariable=self.summary_text)
        self.summary_label.pack(anchor="w", padx=6, pady=4)

        options = ttk.LabelFrame(frame, text="Oggetti già presenti")
        options.pack(fill=tk.X, pady=6)
        ttk.Radiobutton(
            options,
            text="Aggiorna solo i campi vuoti",
            variable=self.duplicate_mode,
            value="update_empty",
        ).pack(anchor="w", padx=6, pady=2)
        ttk.Radiobutton(
            options,
            text="Sovrascrivi sempre i campi selezionati",
            variable=self.duplicate_mode,
            value="overwrite",
        ).pack(anchor="w", padx=6, pady=2)
        ttk.Radiobutton(
            options,
            text="Salta gli oggetti già presenti",
            variable=self.duplicate_mode,
            value="skip",
        ).pack(anchor="w", padx=6, pady=2)

        progress_block = ttk.LabelFrame(frame, text="Avanzamento")
        progress_block.pack(fill=tk.BOTH, expand=True, pady=10)
        self.progress = ttk.Progressbar(progress_block, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, padx=8, pady=8)
        self.progress_text = ttk.Label(progress_block, text="In attesa di avvio")
        self.progress_text.pack(anchor="w", padx=8, pady=(0, 8))
        self.btn_export_errors = ttk.Button(
            progress_block,
            text="Esporta errori...",
            state=tk.DISABLED,
            command=self._export_failures,
        )
        self.btn_export_errors.pack(anchor="w", padx=8, pady=(0, 8))

    # ------------------------------------------------------------------
    # Actions and helpers
    # ------------------------------------------------------------------
    def _select_file(self):
        filetypes = [
            ("File CSV", "*.csv *.txt *.tsv"),
            ("Excel (.xlsx)", "*.xlsx *.xlsm"),
            ("Tutti i file", "*.*"),
        ]
        path = filedialog.askopenfilename(parent=self.win, title="Scegli file", filetypes=filetypes)
        if not path:
            return
        self._load_file(path)

    def _load_file(self, path: str):
        try:
            headers, rows = read_source_file(path)
        except InventoryImportError as exc:
            messagebox.showerror("Import", str(exc), parent=self.win)
            return

        # Enrich notes for common ARI inventory exports.
        try:
            headers, rows, virtual_note_header = add_virtual_notes_column(headers, rows)
        except Exception as exc:
            logger.debug("Impossibile comporre NOTE (auto): %s", exc)
            virtual_note_header = None

        self.file_path = path
        self.headers = headers
        self.rows = rows
        self.mapping = auto_detect_mapping(headers)
        if virtual_note_header:
            self.mapping["note"] = virtual_note_header
        self.file_label.config(text=Path(path).name)
        self.file_info_label.config(
            text=f"Intestazioni: {len(headers)} — Righe valide: {len(rows)}"
        )
        self._populate_preview()
        self._refresh_mapping_widgets()
        self._update_summary()
        self.failed_rows.clear()
        self._update_error_export_button()

    def _populate_preview(self):
        # Preview only exists on the first page; after navigating away the widget is destroyed.
        if getattr(self, "current_page", None) != 0:
            return
        tree = getattr(self, "preview_tree", None)
        if tree is None:
            return
        try:
            if not bool(tree.winfo_exists()):
                return
        except Exception:
            return
        for item in tree.get_children():
            tree.delete(item)

        # Highlight rows missing inventory number.
        try:
            tree.tag_configure("missing_num", background="khaki1")
        except Exception:
            pass

        columns = [f"c{i}" for i in range(len(self.headers))]
        tree["columns"] = columns
        for idx, col in enumerate(columns):
            header = self.headers[idx] if idx < len(self.headers) else f"Col {idx+1}"
            tree.heading(col, text=header)
            tree.column(col, width=120, anchor="w")

        inv_header = None
        if getattr(self, "mapping", None):
            inv_header = self.mapping.get("numero_inventario")
        if not inv_header:
            lookup = {str(h).strip().lower(): h for h in self.headers}
            inv_header = (
                lookup.get("n. inv")
                or lookup.get("n inv")
                or lookup.get("numero inventario")
                or lookup.get("inventario")
            )

        preview_rows = self.rows[:20]
        for row in preview_rows:
            values = [row.get(header, "") for header in self.headers]
            inv_value = (row.get(inv_header) if inv_header else None)
            missing_num = inv_value is None or str(inv_value).strip() == ""
            tags = ("missing_num",) if missing_num else ()
            tree.insert("", tk.END, values=values, tags=tags)

    def _refresh_mapping_widgets(self):
        headers = [""] + self.headers
        for key, combo in getattr(self, "mapping_widgets", {}).items():
            combo["values"] = headers
            value = self.mapping.get(key) or ""
            combo.set(value)
        for key, var in getattr(self, "field_vars", {}).items():
            if key in self.selected_fields:
                var.set(self.selected_fields[key] or False)
            else:
                self.selected_fields[key] = var.get()

        # Preview lives only on page 0; do not touch it on mapping/import pages.
        if getattr(self, "current_page", None) == 0 and getattr(self, "rows", None):
            self._populate_preview()

    def _auto_map(self):
        if not self.headers:
            messagebox.showinfo("Import", "Seleziona prima un file.", parent=self.win)
            return
        self.mapping = auto_detect_mapping(self.headers)
        self._refresh_mapping_widgets()

    def _toggle_fields(self, value: bool):
        for field in INVENTORY_FIELDS:
            if field["required"]:
                continue
            var = self.field_vars.get(field["key"])
            if var:
                var.set(value)

    def _update_summary(self):
        if not self.file_path:
            self.summary_text.set("Nessun file selezionato")
            return
        total = len(self.rows)
        mapped = sum(1 for f in INVENTORY_FIELDS if self.mapping.get(f["key"]))
        file_name = Path(self.file_path).name
        self.summary_text.set(
            f"File: {file_name}\nRighe totali: {total}\nCampi mappati: {mapped}/{len(INVENTORY_FIELDS)}"
        )

    def _capture_mapping(self):
        for key, combo in self.mapping_widgets.items():
            val = combo.get().strip()
            self.mapping[key] = val or None
        for key, var in self.field_vars.items():
            self.selected_fields[key] = bool(var.get())

    def _validate_mapping(self) -> bool:
        missing = [f["label"] for f in INVENTORY_FIELDS if f["required"] and not self.mapping.get(f["key"])]
        if missing:
            messagebox.showwarning(
                "Mapping incompleto",
                "Mappa tutti i campi obbligatori: " + ", ".join(missing),
                parent=self.win,
            )
            return False
        if not self.rows:
            messagebox.showwarning("Import", "Il file non contiene righe valide.", parent=self.win)
            return False
        return True

    def _execute_import(self):
        if not self.file_path:
            messagebox.showwarning("Import", "Seleziona un file prima di continuare.", parent=self.win)
            return
        mapped_rows = apply_mapping(self.rows, self.mapping)
        total = len(mapped_rows)
        if total == 0:
            messagebox.showwarning("Import", "Nessuna riga da importare.", parent=self.win)
            return

        self.failed_rows = []
        self._update_error_export_button()

        # If the source inventory number is missing, still import the row with a generated
        # ATTENZIONE-* code to satisfy DB constraints and to make these records easy to spot.
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        for idx, row in enumerate(mapped_rows, start=1):
            raw_num = row.get("numero_inventario")
            if normalize_inventory_code(raw_num):
                continue
            generated = f"{ATTENZIONE_PREFIX}-{stamp}-{idx:04d}"
            row["numero_inventario"] = generated
            self._record_failure(idx, raw_num, None, f"Numero inventario mancante: assegnato '{generated}'")

        preflight_errors = self._preflight_rows(mapped_rows)
        if preflight_errors:
            self.failed_rows.extend(preflight_errors)
            self._update_error_export_button()
            preview = self._format_failure_preview(preflight_errors)
            messagebox.showerror(
                "Import",
                "Correggere gli errori rilevati prima di procedere:\n" + preview,
                parent=self.win,
            )
            self.progress_text.config(text="Importazione annullata: dati da correggere")
            return

        created = updated = skipped = 0
        duplicate_mode = self.duplicate_mode.get()
        self.progress["value"] = 0
        self.progress_text.config(text="Importazione in corso...")

        for idx, row in enumerate(mapped_rows, start=1):
            numero = row.get("numero_inventario")
            numero_clean = (numero or "").strip()
            numero_norm = normalize_inventory_code(numero)
            marca = row.get("marca")
            marca_clean = (marca or "").strip()
            modello = row.get("modello")
            descrizione = row.get("descrizione")
            note = row.get("note")
            quantita = row.get("quantita")
            ubicazione = row.get("ubicazione")
            matricola = row.get("matricola")
            doc_fisc_prov = row.get("doc_fisc_prov")
            valore_acq_eur = row.get("valore_acq_eur")
            scheda_tecnica = row.get("scheda_tecnica")
            provenienza = row.get("provenienza")
            altre_notizie = row.get("altre_notizie")

            if not numero_norm:
                skipped += 1
                # Should not happen (we generate ATTENZIONE-* codes above), but keep safe.
                self._record_failure(idx, numero, marca, "Numero inventario non valido")
                continue

            try:
                existing = get_item_by_inventory_number(numero_clean)
                if existing:
                    if duplicate_mode == "skip":
                        skipped += 1
                        self._record_failure(idx, numero, marca, "Duplicato ignorato (modalità 'Salta')")
                    else:
                        payload = {}
                        for field_key, value in (
                            ("marca", marca),
                            ("modello", modello),
                            ("descrizione", descrizione),
                            ("note", note),
                            ("quantita", quantita),
                            ("ubicazione", ubicazione),
                            ("matricola", matricola),
                            ("doc_fisc_prov", doc_fisc_prov),
                            ("valore_acq_eur", valore_acq_eur),
                            ("scheda_tecnica", scheda_tecnica),
                            ("provenienza", provenienza),
                            ("altre_notizie", altre_notizie),
                        ):
                            if not self.selected_fields.get(field_key, True):
                                continue
                            if field_key == "marca" and not value:
                                continue
                            if duplicate_mode == "overwrite":
                                if value:
                                    payload[field_key] = value
                            else:  # update_empty
                                current = existing.get(field_key)
                                if (current is None or str(current).strip() == "") and value:
                                    payload[field_key] = value
                        if payload:
                            update_item(existing["id"], **payload)
                            updated += 1
                        else:
                            skipped += 1
                            self._record_failure(idx, numero, marca, "Duplicato senza campi aggiornabili")
                else:
                    # 'marca' is stored as NOT NULL; when missing we import with a safe default.
                    marca_final = marca_clean or DEFAULT_MARCA
                    payload = {
                        "numero_inventario": numero_clean,
                        "marca": marca_final,
                        "modello": modello if self.selected_fields.get("modello", True) else None,
                        "descrizione": descrizione if self.selected_fields.get("descrizione", True) else None,
                        "note": note if self.selected_fields.get("note", True) else None,
                        "quantita": quantita if self.selected_fields.get("quantita", True) else None,
                        "ubicazione": ubicazione if self.selected_fields.get("ubicazione", True) else None,
                        "matricola": matricola if self.selected_fields.get("matricola", True) else None,
                        "doc_fisc_prov": doc_fisc_prov if self.selected_fields.get("doc_fisc_prov", True) else None,
                        "valore_acq_eur": valore_acq_eur if self.selected_fields.get("valore_acq_eur", True) else None,
                        "scheda_tecnica": scheda_tecnica if self.selected_fields.get("scheda_tecnica", True) else None,
                        "provenienza": provenienza if self.selected_fields.get("provenienza", True) else None,
                        "altre_notizie": altre_notizie if self.selected_fields.get("altre_notizie", True) else None,
                    }
                    create_item(**payload)
                    created += 1
            except Exception as exc:
                logger.error("Errore importando l'oggetto %s: %s", numero, exc)
                skipped += 1
                self._record_failure(idx, numero, marca, f"Errore: {exc}")

            self.progress["value"] = int(idx / total * 100)
            self.progress_text.config(text=f"Righe importate: {idx}/{total}")
            self.win.update_idletasks()

        self._update_error_export_button()
        self.import_stats = {"created": created, "updated": updated, "skipped": skipped}
        self.progress_text.config(
            text=f"Completato. Nuovi: {created}, Aggiornati: {updated}, Saltati: {skipped}"
        )
        messagebox.showinfo(
            "Importazione completata",
            f"Nuovi oggetti: {created}\nAggiornati: {updated}\nSaltati: {skipped}",
            parent=self.win,
        )

        if self.on_complete:
            try:
                self.on_complete(created, updated)
            except TypeError:
                # Retrocompatibilità con callback a singolo argomento
                self.on_complete(created + updated)

        self.win.destroy()

    def _preflight_rows(self, rows: list[dict]) -> list[dict[str, str]]:
        failures: list[dict[str, str]] = []
        seen: dict[str, int] = {}
        for idx, row in enumerate(rows, start=1):
            raw_num = row.get("numero_inventario")
            normalized = normalize_inventory_code(raw_num)
            # Missing inventory number is a warning handled elsewhere (skip row).
            if not normalized:
                continue
            if normalized in seen:
                failures.append(
                    self._build_failure_entry(
                        idx,
                        raw_num,
                        "",
                        f"Numero inventario duplicato (già alla riga {seen[normalized]})",
                    )
                )
            else:
                seen[normalized] = idx
        return failures

    def _build_failure_entry(self, row_index: int, numero: str | None, marca: str | None, reason: str) -> dict[str, str]:
        return {
            "row": str(row_index),
            "numero": (numero or "").strip(),
            "marca": (marca or "").strip(),
            "reason": reason,
        }

    def _record_failure(self, row_index: int, numero: str | None, marca: str | None, reason: str):
        self.failed_rows.append(self._build_failure_entry(row_index, numero, marca, reason))
        self._update_error_export_button()

    def _update_error_export_button(self):
        state = tk.NORMAL if self.failed_rows else tk.DISABLED
        if self.btn_export_errors is not None:
            self.btn_export_errors.config(state=state)

    def _format_failure_preview(self, entries: list[dict[str, str]], limit: int = 5) -> str:
        if not entries:
            return ""
        preview = []
        for entry in entries[:limit]:
            preview.append(f"• Riga {entry['row']}: {entry['reason']}")
        remaining = len(entries) - limit
        if remaining > 0:
            preview.append(f"… e altre {remaining} righe")
        return "\n".join(preview)

    def _export_failures(self):
        if not self.failed_rows:
            messagebox.showinfo("Import", "Non ci sono errori da esportare.", parent=self.win)
            return
        path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Esporta errori",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tutti i file", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(["riga", "numero_inventario", "marca", "motivo"])
                for entry in self.failed_rows:
                    writer.writerow([entry["row"], entry["numero"], entry["marca"], entry["reason"]])
        except Exception as exc:
            messagebox.showerror("Esporta errori", f"Impossibile salvare il file:\n{exc}", parent=self.win)
            return
        messagebox.showinfo("Esporta errori", f"File generato:\n{path}", parent=self.win)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _show_page(self):
        for child in self.content_frame.winfo_children():
            child.destroy()
        title, builder = self.pages[self.current_page]
        self.title_label.config(text=title)
        builder()
        self.btn_prev.config(state=tk.NORMAL if self.current_page > 0 else tk.DISABLED)
        if self.current_page == len(self.pages) - 1:
            self.btn_next.config(text="Avvia importazione")
            self._update_summary()
        else:
            self.btn_next.config(text="Avanti")
        self.progress_label.config(text=f"Pagina {self.current_page + 1} di {len(self.pages)}")

    def _next_page(self):
        if self.current_page == 0:
            if not self.file_path:
                messagebox.showwarning("Import", "Seleziona un file.", parent=self.win)
                return
        if self.current_page == 1:
            self._capture_mapping()
            if not self._validate_mapping():
                return
        if self.current_page == len(self.pages) - 1:
            self._execute_import()
            return
        self.current_page += 1
        self._show_page()

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._show_page()

    def _cancel(self):
        if messagebox.askyesno("Import", "Annullare l'importazione?", parent=self.win):
            self.win.destroy()
