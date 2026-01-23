# -*- coding: utf-8 -*-
"""
CD Meetings UI Dialogs for GLR Gestione Locale Radioamatori
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import logging
from datetime import datetime
import json
import os

logger = logging.getLogger("librosoci")

class MeetingDialog:
    """Dialog for adding/editing CD meetings."""

    def _reload_mandati_combo(self, *, keep_selection: bool = True) -> None:
        """Reload mandates list for the Mandato combobox (includes past mandates)."""
        if not hasattr(self, "combo_mandato"):
            return

        previous = None
        try:
            previous = self.mandato_display_var.get() if keep_selection and hasattr(self, "mandato_display_var") else None
        except Exception:
            previous = None

        self._mandato_display_to_id: dict[str, int | None] = {"Auto (da data)": None}
        mandato_values = ["Auto (da data)"]

        try:
            from cd_mandati import get_all_cd_mandati

            rows = get_all_cd_mandati()
            for r in rows or []:
                raw_id = r.get("id")
                raw_id_s = str(raw_id or "").strip()
                if not raw_id_s:
                    continue
                try:
                    mid = int(raw_id_s)
                except Exception:
                    continue
                lbl = str(r.get("label") or "").strip()
                s = str(r.get("start_date") or "").strip()
                e = str(r.get("end_date") or "").strip()
                span = f"{s[:4]}-{e[:4]}" if s and e else ""
                span_lbl = f"Mandato {span}" if span else ""

                display = lbl
                if span_lbl and lbl:
                    display = f"{lbl} ({span_lbl})"
                elif span_lbl and not lbl:
                    display = span_lbl
                else:
                    display = lbl or f"Mandato ID {mid}"

                if display in self._mandato_display_to_id and self._mandato_display_to_id.get(display) != mid:
                    display = f"{display} #{mid}"
                self._mandato_display_to_id[display] = mid
                mandato_values.append(display)
        except Exception:
            pass

        try:
            self.combo_mandato.configure(values=mandato_values)
        except Exception:
            pass

        try:
            if previous and previous in self._mandato_display_to_id:
                self.mandato_display_var.set(previous)
        except Exception:
            pass

    def _open_mandati_wizard(self) -> None:
        """Open the Mandato CD wizard (to create/edit past mandates) and refresh the dropdown."""
        try:
            from v4_ui.cd_mandato_wizard import CdMandatoWizard

            CdMandatoWizard(self.dialog, on_saved=lambda _r=None: self._reload_mandati_combo())
        except Exception as exc:
            messagebox.showerror("Mandato CD", f"Impossibile aprire il wizard mandato:\n{exc}", parent=self.dialog)

    def _set_verbale_path_in_entry(self, path: str | None) -> None:
        if not hasattr(self, "entry_verbale_path"):
            return
        try:
            self.entry_verbale_path.configure(state="normal")
            self.entry_verbale_path.delete(0, tk.END)
            if path:
                self.entry_verbale_path.insert(0, str(path))
            self.entry_verbale_path.configure(state="readonly")
        except Exception:
            pass

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
        self.verbale_section_doc_id: int | None = None
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Nuova riunione CD" if not meeting_id else "Modifica riunione CD")
        # More compact default size; content remains scrollable.
        self.dialog.geometry("760x990")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Main content (scrollable)
        content_frame = ttk.Frame(self.dialog)
        content_frame.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(content_frame)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        main_frame = ttk.Frame(canvas)
        
        main_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        scrollbar.pack(side="right", fill="y")

        # Fixed bottom action bar (always visible)
        actions_frame = ttk.Frame(self.dialog)
        actions_frame.pack(side="bottom", fill="x", padx=6, pady=6)
        
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

        # Mandato (optional override; otherwise inferred from date)
        row += 1
        ttk.Label(main_frame, text="Mandato:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.mandato_display_var = tk.StringVar(value="Auto (da data)")
        self.combo_mandato = ttk.Combobox(
            main_frame,
            state="readonly",
            width=28,
            values=["Auto (da data)"],
            textvariable=self.mandato_display_var,
        )
        self.combo_mandato.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=5)
        ttk.Button(main_frame, text="Gestisci...", command=self._open_mandati_wizard).grid(row=row, column=3, sticky="w", padx=5, pady=5)

        # Populate mandates list (includes past mandates)
        self._reload_mandati_combo(keep_selection=False)
        
        # Oggetto
        row += 1
        self.label_oggetto = ttk.Label(main_frame, text="Oggetto:", font=("Arial", 10, "bold"))
        self.label_oggetto.grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.entry_oggetto = ttk.Entry(main_frame, width=60)
        self.entry_oggetto.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        # Note generali riunione
        row += 1
        self.label_note = ttk.Label(main_frame, text="Note riunione (campo libero):", font=("Arial", 10, "bold"))
        self.label_note.grid(row=row, column=0, sticky="nw", padx=5, pady=(5, 2))
        self.text_note = scrolledtext.ScrolledText(main_frame, height=3, wrap=tk.WORD)
        self.text_note.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=(5, 2))

        # Metadati riunione
        row += 1
        self.meta_frame = ttk.LabelFrame(main_frame, text="Metadati riunione", padding=4)
        self.meta_frame.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
        self.meta_frame.columnconfigure(1, weight=1)
        self.meta_frame.columnconfigure(3, weight=1)

        self.label_meta_tipo = ttk.Label(self.meta_frame, text="Tipo:")
        self.label_meta_tipo.grid(row=0, column=0, sticky="w", padx=5, pady=3)
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

        self.label_meta_modalita = ttk.Label(self.meta_frame, text="Modalità:")
        self.label_meta_modalita.grid(row=0, column=2, sticky="w", padx=5, pady=3)
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

        self.label_meta_ora_inizio = ttk.Label(self.meta_frame, text="Ora inizio:")
        self.label_meta_ora_inizio.grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.entry_meta_ora_inizio = ttk.Entry(self.meta_frame, width=10)
        self.entry_meta_ora_inizio.grid(row=2, column=1, sticky="w", padx=5, pady=3)
        self.label_meta_ora_fine = ttk.Label(self.meta_frame, text="Ora fine:")
        self.label_meta_ora_fine.grid(row=2, column=2, sticky="w", padx=5, pady=3)
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
        
        # ODG section
        row += 1
        self.odg_frame = ttk.LabelFrame(main_frame, text="Ordine del Giorno", padding=4)
        self.odg_frame.grid(row=row, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)

        ttk.Label(self.odg_frame, text="ODG (un punto per riga; usa [D] per punti che richiedono delibera):").pack(anchor="w", padx=5, pady=(0, 5))
        ttk.Label(self.odg_frame, text="Esempio: [D] Approvazione bilancio", foreground="gray").pack(anchor="w", padx=5, pady=(0, 5))
        self.text_odg = scrolledtext.ScrolledText(self.odg_frame, height=6, wrap=tk.WORD)
        self.text_odg.pack(fill=tk.BOTH, expand=True)
        
        # Verbale section (anche bozza per riunioni future)
        row += 1
        self.verbale_frame = ttk.LabelFrame(main_frame, text="Verbale / Bozza", padding=4)
        self.verbale_frame.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=5)
        
        verbale_row = 0
        ttk.Label(self.verbale_frame, text="Documento verbale:").grid(row=verbale_row, column=0, sticky="w", padx=5, pady=5)
        self.entry_verbale_path = ttk.Entry(self.verbale_frame, width=50, state="readonly")
        self.entry_verbale_path.grid(row=verbale_row, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(self.verbale_frame, text="Seleziona...", command=self._select_verbale).grid(row=verbale_row, column=2, padx=5, pady=5)
        ttk.Button(self.verbale_frame, text="Da documenti...", command=self._select_verbale_from_docs).grid(row=verbale_row, column=3, padx=5, pady=5)
        self.verbale_frame.columnconfigure(1, weight=1)

        verbale_row += 1
        self.btn_generate_verbale_docx = ttk.Button(
            self.verbale_frame,
            text="Rigenera da template (DOCX)...",
            command=self._generate_verbale_docx,
        )
        self.btn_generate_verbale_docx.grid(row=verbale_row, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))
        
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
            # Toggle visibility based on tipo_riunione
            self._toggle_tipo_riunione()

        self._on_meta_tipo_changed()
        self._update_presenze_visibility()
        
        ttk.Button(actions_frame, text="Annulla", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        self.btn_prepare_email = ttk.Button(actions_frame, text="Prepara e-mail...", command=self._open_email_wizard_from_ui)
        if meeting_id:
            self.btn_prepare_email.pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Salva", command=self._save).pack(side=tk.LEFT, padx=5)

        # Initial state for prepare button
        self._update_prepare_email_button_state()

        try:
            if not self.meeting_id:
                self.btn_generate_verbale_docx.configure(state="disabled")
        except Exception:
            pass

    def _generate_verbale_docx(self):
        if not self.meeting_id:
            messagebox.showinfo(
                "Verbale",
                "Salvare prima la riunione per poter generare il verbale.",
                parent=self.dialog,
            )
            return

        try:
            from templates_manager import get_templates_dir

            initial_dir = get_templates_dir()
        except Exception:
            initial_dir = None

        template_path = filedialog.askopenfilename(
            title="Seleziona template Verbale CD (DOCX) (opzionale)",
            initialdir=initial_dir,
            filetypes=[
                ("Word (.docx)", "*.docx"),
                ("Tutti i file", "*.*"),
            ],
        )
        if not template_path:
            template_path = None

        try:
            import tempfile
            import os

            from cd_reports import export_verbale_cd_docx
            from section_documents import add_section_document
            from database import get_section_document_by_relative_path
            from cd_meetings import update_meeting

            fd, tmp_path = tempfile.mkstemp(prefix="verbale_cd_", suffix=".docx")
            try:
                os.close(fd)
            except Exception:
                pass

            ok, warnings = export_verbale_cd_docx(int(self.meeting_id), tmp_path, template_path=template_path)
            if not ok:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                messagebox.showerror(
                    "Verbale",
                    "Errore durante la generazione del verbale.",
                    parent=self.dialog,
                )
                return

            dest_abs = add_section_document(tmp_path, "Verbali CD")
            try:
                os.remove(tmp_path)
            except Exception:
                pass

            row = get_section_document_by_relative_path(dest_abs)
            if row and row.get("id") is not None:
                doc_id = int(row["id"])
                update_meeting(int(self.meeting_id), verbale_section_doc_id=doc_id)
                self.verbale_section_doc_id = doc_id
                self._set_verbale_path_in_entry(dest_abs)

            msg = "Verbale generato e collegato correttamente."
            if warnings:
                msg += "\n\nAvvisi:\n- " + "\n- ".join([str(w) for w in warnings])
            messagebox.showinfo("Verbale", msg, parent=self.dialog)
        except Exception as exc:
            messagebox.showerror(
                "Verbale",
                f"Errore durante la generazione/link del verbale:\n{exc}",
                parent=self.dialog,
            )

    def _build_email_initial_for_wizard(self, data: str, numero_cd: str, odg_text: str) -> tuple[str, str]:
        """Build (subject, body) for Email Wizard from meeting fields."""
        is_assemblea = False
        try:
            is_assemblea = self._is_meta_tipo_assemblea()
        except Exception:
            is_assemblea = False

        num_display = (numero_cd or "").strip()
        if num_display:
            num_display = num_display.zfill(2)

        ora = (self.entry_meta_ora_inizio.get() or "").strip()
        luogo = (self.entry_meta_luogo.get() or "").strip()

        if is_assemblea:
            subject = "Convocazione Assemblea Soci"
            body = (
                "Gentili Soci,\n\n"
                "siete convocati per l'Assemblea Ordinaria/Straordinaria dei Soci che si terrà in:\n\n"
                f"PRIMA CONVOCAZIONE: {data or '{data}'}"
            )
            body += f" ore {ora}" if ora else " ore {ora}"
            body += "\n"
            body += "SECONDA CONVOCAZIONE: {data2}"
            body += " ore {ora2}\n\n"
            body += "Presso: " + (luogo if luogo else "{luogo}") + "\n\n"
            body += "Ordine del giorno:\n{odg}\n\nLa vostra presenza è importante.\n\nCordiali saluti,\nIl Presidente\n{presidente}"
            return subject, body

        subject = "Convocazione Consiglio Direttivo"
        if num_display:
            subject = f"Convocazione Consiglio Direttivo n. {num_display}"

        body = (
            "Gentili Consiglieri,\n\n"
            f"siete convocati per la riunione del Consiglio Direttivo n. {num_display or '{num}'} "
            f"che si terrà in data {data or '{data}'}"
        )
        if ora:
            body += f" alle ore {ora}"
        else:
            body += " alle ore {ora}"
        if luogo:
            body += f" presso {luogo}.\n\n"
        else:
            body += " presso {luogo}.\n\n"

        body += "Ordine del giorno:\n{odg}\n\nCordiali saluti,\nIl Presidente\n{presidente}"
        return subject, body

    def _template_for_meeting(self) -> str:
        try:
            if self._is_meta_tipo_assemblea():
                return "Convocazione Assemblea"
        except Exception:
            pass

        try:
            modalita = (self.meta_modalita_var.get() or "").strip().lower()
        except Exception:
            modalita = ""

        candidates: list[str] = []
        if modalita == "presenza":
            candidates = ["Convocazione CD – presenza", "Convocazione CD – Modalità presenza"]
        elif modalita == "online":
            candidates = ["Convocazione CD – online", "Convocazione CD – Modalità online"]
        elif modalita in ("ibrida", "mista"):
            candidates = ["Convocazione CD – mista", "Convocazione CD – Modalità mista"]

        # Use the specific template only if the corresponding .txt exists.
        try:
            from config import DATA_DIR

            templates_dir = os.path.join(DATA_DIR, "email_templates")
            for name in candidates:
                if os.path.exists(os.path.join(templates_dir, f"{name}.txt")):
                    return name
        except Exception:
            pass

        return "Convocazione CD"

    def _destinatari_for_email_wizard(self) -> str:
        """Destinatari: assemblea -> soci attivi; CD -> CD (la scelta si fa nel wizard)."""
        try:
            if self._is_meta_tipo_assemblea():
                return "attivi"
        except Exception:
            pass
        return "cd"

    def _update_prepare_email_button_state(self):
        """Enable 'Prepara e-mail' only for saved future meetings."""
        try:
            if not hasattr(self, "btn_prepare_email"):
                return
            if not self.meeting_id:
                self.btn_prepare_email.configure(state="disabled")
                return
            is_futura = self.tipo_riunione_var.get() == "futura"
            self.btn_prepare_email.configure(state=("normal" if is_futura else "disabled"))
        except Exception:
            pass

    def _open_email_wizard_from_ui(self):
        """Open Email Wizard prefilled for an existing (future) meeting."""
        if not self.meeting_id:
            return
        if self.tipo_riunione_var.get() != "futura":
            messagebox.showinfo("Info", "Disponibile solo per riunioni future.", parent=self.dialog)
            return

        numero_cd = self.entry_numero_cd.get().strip()
        data = self.entry_date.get().strip()
        odg_text = self.text_odg.get("1.0", tk.END).strip()

        ora = (self.entry_meta_ora_inizio.get() or "").strip()
        luogo_link = (self.entry_meta_luogo.get() or "").strip()
        modalita = (self.meta_modalita_var.get() or "").strip().lower()

        subject, body = self._build_email_initial_for_wizard(data=data, numero_cd=numero_cd, odg_text=odg_text)

        try:
            from email_wizard import show_email_wizard

            initial = {
                "from_meeting": True,
                "template": self._template_for_meeting(),
                "oggetto": subject,
                "body": body,
                "odg": odg_text,
                "num": numero_cd,
                "data": data,
                "ora": ora,
                "luogo": luogo_link,
                "link": luogo_link if (modalita in ("online", "ibrida") and luogo_link) else "",
                "destinatari": self._destinatari_for_email_wizard(),
            }
            # Close meeting dialog first to release grab/focus.
            try:
                self.dialog.destroy()
            except Exception:
                pass
            show_email_wizard(self.parent, initial=initial)
        except Exception as exc:
            logger.error("Impossibile aprire il wizard email: %s", exc)
            messagebox.showerror("Errore", f"Impossibile aprire il wizard email:\n{exc}", parent=self.dialog)

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
        
        # Verbale: sempre visibile (permette bozza anche per riunioni future)
        if hasattr(self, 'verbale_frame'):
            self.verbale_frame.grid()

        # Delibere: solo per riunioni passate
        if hasattr(self, 'delibere_frame'):
            if is_passata:
                self.delibere_frame.grid()
            else:
                self.delibere_frame.grid_remove()

        self._update_prepare_email_button_state()
    
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
        if not file_path:
            return

        # Canonical: import into section documents and link by ID
        try:
            from section_documents import add_section_document
            from database import get_section_document_by_relative_path

            dest_abs = add_section_document(file_path, "Verbali CD")
            row = get_section_document_by_relative_path(dest_abs)
            if row and row.get("id") is not None:
                self.verbale_section_doc_id = int(row["id"])
                self._set_verbale_path_in_entry(dest_abs)
                return
        except Exception:
            pass

        # Fallback: keep raw path
        self.verbale_section_doc_id = None
        self._set_verbale_path_in_entry(file_path)

    def _select_verbale_from_docs(self):
        """Select verbale from already-imported section documents (Verbali CD)."""

        try:
            from section_documents import list_cd_verbali_documents
        except Exception as exc:
            messagebox.showerror(
                "Verbale",
                f"Impossibile caricare l'elenco dei documenti importati.\n\nDettagli: {exc}",
                parent=self.dialog,
            )
            return

        try:
            all_docs = list_cd_verbali_documents(include_missing=False)
        except Exception as exc:
            messagebox.showerror(
                "Verbale",
                f"Errore nel caricamento dei documenti importati.\n\nDettagli: {exc}",
                parent=self.dialog,
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
            messagebox.showinfo(
                "Verbale",
                "Nessun documento importato disponibile tra i Verbali CD.",
                parent=self.dialog,
            )
            return

        dlg = tk.Toplevel(self.dialog)
        dlg.title("Seleziona verbale (documenti importati)")
        dlg.transient(self.dialog)
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

        picked_by_iid: dict[str, tuple[int, str]] = {}
        for idx, d in enumerate(docs):
            iid = str(idx)
            uploaded_at = str(d.get("uploaded_at") or "").strip()
            date_display = uploaded_at[:10] if len(uploaded_at) >= 10 else uploaded_at
            verbale_numero = str(d.get("verbale_numero") or "").strip()
            nome = str(d.get("nome_file") or "").strip()
            categoria = str(d.get("categoria") or "").strip()
            abs_path = str(d.get("absolute_path") or "").strip()
            tv.insert("", tk.END, iid=iid, values=(date_display, verbale_numero, nome, categoria))
            raw_id = d.get("id")
            try:
                doc_id = int(str(raw_id)) if raw_id is not None else 0
            except Exception:
                doc_id = 0
            picked_by_iid[iid] = (doc_id, abs_path)

        actions = ttk.Frame(container)
        actions.pack(fill=tk.X)

        result: dict[str, str | None] = {"path": None}
        result_id: dict[str, int | None] = {"id": None}

        def _choose_selected() -> None:
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Verbale", "Seleziona un documento.", parent=dlg)
                return
            picked = picked_by_iid.get(str(sel[0]))
            if not picked:
                messagebox.showwarning("Verbale", "Documento non valido.", parent=dlg)
                return
            picked_id, picked_path = picked
            if not picked_id or not picked_path:
                messagebox.showwarning("Verbale", "Documento non valido.", parent=dlg)
                return
            try:
                if not os.path.exists(picked_path):
                    messagebox.showwarning("Verbale", "File non trovato sul disco.", parent=dlg)
                    return
            except Exception:
                messagebox.showwarning("Verbale", "Impossibile verificare il file selezionato.", parent=dlg)
                return
            result["path"] = picked_path
            result_id["id"] = int(picked_id)
            try:
                dlg.destroy()
            except Exception:
                pass

        def _on_double_click(_evt) -> None:
            _choose_selected()

        tv.bind("<Double-1>", _on_double_click)

        ttk.Button(actions, text="Annulla", command=dlg.destroy).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Seleziona", command=_choose_selected).pack(side=tk.RIGHT, padx=(0, 8))

        self.dialog.wait_window(dlg)
        picked_path = result.get("path")
        picked_id = result_id.get("id")
        if picked_path and picked_id:
            self.verbale_section_doc_id = int(picked_id)
            self._set_verbale_path_in_entry(picked_path)
    
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

            # Load mandato override if present
            try:
                raw_mid = meeting.get("mandato_id")
                mandato_id = int(raw_mid) if raw_mid is not None and str(raw_mid).strip() else None
            except Exception:
                mandato_id = None
            try:
                if mandato_id:
                    for display, mid in getattr(self, "_mandato_display_to_id", {}).items():
                        if mid == mandato_id:
                            self.mandato_display_var.set(display)
                            break
                else:
                    self.mandato_display_var.set("Auto (da data)")
            except Exception:
                pass
            
            self.entry_oggetto.delete(0, tk.END)
            self.entry_oggetto.insert(0, meeting.get('titolo', ''))

            # Carica note generali riunione
            if meeting.get('note') is not None:
                self.text_note.delete("1.0", tk.END)
                self.text_note.insert("1.0", meeting.get('note'))
            
            if meeting.get('odg'):
                self.text_odg.delete("1.0", tk.END)
                self.text_odg.insert("1.0", meeting.get('odg', ''))

            # Load verbale link/path
            try:
                sid = meeting.get("verbale_section_doc_id")
                self.verbale_section_doc_id = int(sid) if sid is not None else None
            except Exception:
                self.verbale_section_doc_id = None

            from cd_meetings import resolve_meeting_verbale_path

            verbale_path = resolve_meeting_verbale_path(meeting)
            if verbale_path:
                self._set_verbale_path_in_entry(verbale_path)

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
    
    
    def _save(self):
        """Save meeting and optionally send email"""
        numero_cd = self.entry_numero_cd.get().strip()
        data = self.entry_date.get().strip()
        oggetto = self.entry_oggetto.get().strip() if hasattr(self, 'entry_oggetto') else ""
        note = self.text_note.get("1.0", tk.END).strip() if hasattr(self, 'text_note') else None
        odg_text = self.text_odg.get("1.0", tk.END).strip()
        corpo_email = ""
        # Canonical: link via section document ID when available
        verbale_section_doc_id = self.verbale_section_doc_id
        verbale_path_raw = self.entry_verbale_path.get().strip() if hasattr(self, 'entry_verbale_path') else ""
        verbale_path = verbale_path_raw if (verbale_path_raw and not verbale_section_doc_id) else None
        delibere_text = self.text_delibere.get("1.0", tk.END).strip() if hasattr(self, 'text_delibere') else None

        mandato_display = getattr(self, "mandato_display_var", None)
        mandato_id = None
        try:
            choice = mandato_display.get() if mandato_display is not None else "Auto (da data)"
            mandato_id = getattr(self, "_mandato_display_to_id", {}).get(choice)
        except Exception:
            mandato_id = None

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
                    mandato_id=mandato_id,
                    verbale_path=verbale_path,
                    verbale_section_doc_id=verbale_section_doc_id,
                    tipo_riunione=self.tipo_riunione_var.get(),
                    meta_json=meta_json,
                    presenze_json=presenze_json,
                    note=note,
                ):
                    meeting_id = self.meeting_id
                else:
                    messagebox.showerror("Errore", "Errore durante l'aggiornamento.", parent=self.dialog)
                    return
            else:
                from cd_meetings import add_meeting
                # If oggetto is hidden/empty (2B), generate a reasonable title
                if not oggetto:
                    gen_subject, _gen_body = self._build_email_initial_for_wizard(data=data, numero_cd=numero_cd, odg_text=odg_text)
                    oggetto = gen_subject
                meeting_id = add_meeting(
                    data,
                    numero_cd=numero_cd if numero_cd else None,
                    titolo=oggetto if oggetto else None,
                    odg=odg_text if odg_text else None,
                    mandato_id=mandato_id,
                    verbale_path=verbale_path,
                    verbale_section_doc_id=verbale_section_doc_id,
                    tipo_riunione=self.tipo_riunione_var.get(),
                    meta_json=meta_json,
                    presenze_json=presenze_json,
                    note=note,
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
            
            # Ask if user wants to prepare email (solo per riunioni future)
            open_wizard = False
            if (not self.meeting_id) and self.tipo_riunione_var.get() == "futura":
                open_wizard = messagebox.askyesno(
                    "Email convocazione",
                    "Riunione salvata!\n\nVuoi preparare l'email di convocazione?",
                    parent=self.dialog,
                )
            else:
                messagebox.showinfo("Successo", "Riunione salvata con successo.", parent=self.dialog)

            # Close meeting dialog; optionally open Email Wizard prefilled
            try:
                self.dialog.destroy()
            except Exception:
                pass

            if open_wizard:
                try:
                    from email_wizard import show_email_wizard

                    if not oggetto or not corpo_email:
                        gen_subject, gen_body = self._build_email_initial_for_wizard(data=data, numero_cd=numero_cd, odg_text=odg_text)
                        if not oggetto:
                            oggetto = gen_subject
                        if not corpo_email:
                            corpo_email = gen_body

                    ora = (self.entry_meta_ora_inizio.get() or "").strip()
                    luogo_link = (self.entry_meta_luogo.get() or "").strip()
                    modalita = (self.meta_modalita_var.get() or "").strip().lower()

                    initial = {
                        "from_meeting": True,
                        "template": self._template_for_meeting(),
                        "oggetto": oggetto,
                        "body": corpo_email,
                        "odg": odg_text,
                        "num": numero_cd,
                        "data": data,
                        "ora": ora,
                        "luogo": luogo_link,
                        "link": luogo_link if (modalita in ("online", "ibrida") and luogo_link) else "",
                        "destinatari": self._destinatari_for_email_wizard(),
                    }
                    show_email_wizard(self.parent, initial=initial)
                except Exception as exc:
                    logger.error("Impossibile aprire il wizard email: %s", exc)
            
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}", parent=self.dialog)
            logger.error("Error saving meeting: %s", e)

    # Niente mappatura destinatari: la selezione avviene nel wizard email.
    
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
        self.tv.column("verbale", width=220, anchor="w")
        
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
            verbale_path = str(meeting.get('verbale_path') or "").strip()
            if not verbale_path:
                verbale = "—"
            else:
                base = os.path.basename(verbale_path) or verbale_path
                try:
                    verbale = base if os.path.exists(verbale_path) else f"{base} (manca)"
                except Exception:
                    verbale = base

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
