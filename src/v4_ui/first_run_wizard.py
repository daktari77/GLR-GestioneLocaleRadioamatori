# -*- coding: utf-8 -*-
"""
Wizard di primo avvio per GLR - Gestione Locale Radioamatori
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Any

from typing import Optional



# --- Wizard State Object ---
class WizardState:
    def __init__(self, section_data=None, import_result=None, cd_config=None, thunderbird=None, completed=False):
        self.section_data = section_data or {}
        self.import_result = import_result
        self.cd_config = cd_config
        self.thunderbird = thunderbird
        self.completed = completed

# --- Base Step Frame ---
class WizardStep(ttk.Frame):
    def __init__(self, master, wizard, wizard_state: WizardState):
        super().__init__(master)
        self.wizard = wizard
        self.wizard_state = wizard_state
    def on_next(self):
        return True
    def on_back(self):
        return True
    def on_skip(self):
        return True

# --- Placeholder for steps (to be implemented in next steps) ---
class WelcomeStep(WizardStep):
    def __init__(self, master, wizard, state):
        super().__init__(master, wizard, state)
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Benvenuto in GLR", font="AppBold", anchor="center").grid(row=0, column=0, pady=(0, 16), sticky="ew")
        ttk.Label(
            self,
            text="Questa procedura guidata ti aiuterà a configurare i dati iniziali della sezione.\n\nPotrai inserire i dati della sezione, importare i soci, configurare il consiglio direttivo, integrare Thunderbird e salvare la configurazione.",
            wraplength=420,
            justify="left"
        ).grid(row=1, column=0, pady=(0, 8), sticky="ew")
class SectionDataStep(WizardStep):
    def __init__(self, master, wizard, state):
        super().__init__(master, wizard, state)
        self.columnconfigure(1, weight=1)
        fields = [
            ("Nome sezione", "nome_sezione"),
            ("Codice sezione", "codice_sezione"),
            ("Sede operativa", "sede_operativa"),
            ("Sede legale", "sede_legale"),
            ("Indirizzo postale", "indirizzo_postale"),
            ("Email", "email"),
            ("Telefono", "telefono"),
            ("Sito web", "sito_web"),
            ("Coordinate bancarie", "iban"),
            ("Recapiti di sezione", "recapiti"),
            ("Mandato (es. Mandato 2024-2027)", "mandato"),
        ]
        self.vars = {}
        for i, (label, key) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 8))
            var = tk.StringVar(value=self.wizard_state.section_data.get(key, ""))
            self.vars[key] = var
            ttk.Entry(self, textvariable=var, width=40).grid(row=i, column=1, sticky="ew", pady=2)

    def on_next(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        if not data["nome_sezione"] or not data["codice_sezione"]:
            messagebox.showwarning("Dati sezione", "Nome e codice sezione sono obbligatori.", parent=self)
            return False
        self.wizard_state.section_data = data
        return True
class ImportSociStep(WizardStep):
    def __init__(self, master, wizard, state):
        super().__init__(master, wizard, state)
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="Importazione soci da CSV", font="AppBold").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(self, text="Seleziona un file CSV per importare l'elenco soci. Sono supportati i formati ARI e altri già previsti dal gestionale.", wraplength=420, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.csv_path_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.csv_path_var, width=40).grid(row=2, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(self, text="Sfoglia...", command=self._browse_csv).grid(row=2, column=1, sticky="w", padx=(8, 0))
        self.import_result_var = tk.StringVar(value="Nessun file importato.")
        ttk.Label(self, textvariable=self.import_result_var, foreground="gray40").grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._import_result = None

    def _browse_csv(self):
        path = filedialog.askopenfilename(title="Seleziona file CSV", filetypes=[("CSV files", "*.csv"), ("Tutti i file", "*.*")], parent=self)
        if path:
            self.csv_path_var.set(path)

    def on_next(self):
        path = self.csv_path_var.get().strip()
        if not path:
            self.import_result_var.set("Nessun file selezionato.")
            return False
        try:
            from src.import_soci_csv import import_soci_csv
            result = import_soci_csv(path)
            self._import_result = result
            msg = f"Importati: {result.get('imported', 0)} | Errori: {result.get('errors', 0)} | Duplicati: {result.get('duplicates', 0)}"
            self.import_result_var.set(msg)
            self.wizard_state.import_result = result
        except Exception as exc:
            self.import_result_var.set(f"Errore importazione: {exc}")
            return False
        return True

    def on_skip(self):
        self.wizard_state.import_result = None
        return True
class CdStep(WizardStep):
    def __init__(self, master, wizard, state):
        super().__init__(master, wizard, state)
        self.cd_roles = [
            ("Presidente", "presidente"),
            ("Vicepresidente", "vicepresidente"),
            ("Segretario", "segretario"),
            ("Tesoriere", "tesoriere"),
            ("Consigliere", "consigliere1"),
            ("Consigliere", "consigliere2"),
            ("Consigliere", "consigliere3"),
        ]
        self.soci_list = []
        self.vars = {}
        imp_result = self.wizard_state.import_result
        imported = imp_result is not None and isinstance(imp_result, dict) and imp_result.get("imported", 0) > 0 and imp_result.get("soci")
        if imported:
            soci = (imp_result.get("soci") if imp_result else []) or []
            self.soci_list = [f"{s.get('nome','')} {s.get('cognome','')} ({s.get('matricola','')})" for s in soci]
            ttk.Label(self, text="Composizione Consiglio Direttivo", font="AppBold").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
            for i, (role, key) in enumerate(self.cd_roles):
                ttk.Label(self, text=role).grid(row=i+1, column=0, sticky="w", pady=2, padx=(0, 8))
                var = tk.StringVar()
                self.vars[key] = var
                cb = ttk.Combobox(self, textvariable=var, values=self.soci_list, state="readonly", width=36)
                cb.grid(row=i+1, column=1, sticky="ew", pady=2)
        else:
            ttk.Label(self, text="Consiglio Direttivo", font="AppBold").pack(anchor="w", pady=(0, 8))
            ttk.Label(self, text="Per configurare il consiglio direttivo è necessario prima importare l'elenco soci.\nPuoi saltare questo passaggio e configurare il consiglio in seguito.", wraplength=420, justify="left").pack(anchor="w", pady=(0, 8))

    def on_next(self):
            imported = self.wizard_state.import_result and self.wizard_state.import_result.get("imported", 0) > 0 and self.wizard_state.import_result.get("soci")
            if imported:
                cd_config = {}
                for role, key in self.cd_roles:
                    val = self.vars[key].get().strip()
                    if not val:
                        messagebox.showwarning("Consiglio direttivo", f"Selezionare un socio per la carica di {role}.", parent=self)
                        return False
                    cd_config[key] = val
                self.wizard_state.cd_config = cd_config
            else:
                self.wizard_state.cd_config = None
            return True

    def on_skip(self):
        self.wizard_state.cd_config = None
        return True
class ThunderbirdStep(WizardStep):
    def __init__(self, master, wizard, state):
        super().__init__(master, wizard, state)
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="Configurazione Thunderbird Portable", font="AppBold").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(self, text="GLR può integrarsi con Thunderbird Portable per la gestione email. Puoi scaricare Thunderbird Portable o specificare un percorso personalizzato.", wraplength=420, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.th_path_var = tk.StringVar()
        self.th_auto_var = tk.BooleanVar(value=False)
        # Percorso suggerito
        import os
        default_path = os.path.abspath(os.path.join(os.getcwd(), "ThunderbirdPortable"))
        self.th_path_var.set(self.wizard_state.thunderbird["path"] if self.wizard_state.thunderbird and "path" in self.wizard_state.thunderbird else default_path)
        ttk.Label(self, text="Percorso Thunderbird Portable").grid(row=2, column=0, sticky="w", pady=(0, 2))
        ttk.Entry(self, textvariable=self.th_path_var, width=40).grid(row=2, column=1, sticky="ew", pady=(0, 2))
        ttk.Button(self, text="Sfoglia...", command=self._browse_thunderbird).grid(row=3, column=1, sticky="w", padx=(8, 0))
        ttk.Checkbutton(self, text="Scarica automaticamente Thunderbird Portable", variable=self.th_auto_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _browse_thunderbird(self):
        path = filedialog.askdirectory(title="Seleziona cartella Thunderbird Portable", parent=self)
        if path:
            self.th_path_var.set(path)

    def on_next(self):
        self.wizard_state.thunderbird = {
            "path": self.th_path_var.get().strip(),
            "auto_download": self.th_auto_var.get(),
        }
        return True

    def on_skip(self):
        self.wizard_state.thunderbird = None
        return True
class SummaryStep(WizardStep):
    def __init__(self, master, wizard, state):
        super().__init__(master, wizard, state)
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Riepilogo configurazione", font="AppBold").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.summary = tk.Text(self, height=18, width=70, state="normal", wrap=tk.WORD)
        self.summary.grid(row=1, column=0, sticky="nsew")
        self._update_summary()
        self.summary.config(state="disabled")

    def _update_summary(self):
        s = self.wizard_state.section_data
        lines = []
        lines.append(f"Sezione: {s.get('nome_sezione', '')} ({s.get('codice_sezione', '')})")
        lines.append(f"Sede operativa: {s.get('sede_operativa', '')}")
        lines.append(f"Sede legale: {s.get('sede_legale', '')}")
        lines.append(f"Email: {s.get('email', '')}")
        lines.append(f"Telefono: {s.get('telefono', '')}")
        lines.append(f"Sito web: {s.get('sito_web', '')}")
        lines.append(f"Mandato: {s.get('mandato', '')}")
        lines.append("")
        imp = self.wizard_state.import_result
        if imp:
            lines.append(f"Soci importati: {imp.get('imported', 0)} | Errori: {imp.get('errors', 0)} | Duplicati: {imp.get('duplicates', 0)}")
        else:
            lines.append("Importazione soci: saltata")
        lines.append("")
        cd = self.wizard_state.cd_config
        if cd:
            lines.append("Consiglio direttivo:")
            for k, v in cd.items():
                lines.append(f"  {k.capitalize()}: {v}")
        else:
            lines.append("Consiglio direttivo: non configurato")
        lines.append("")
        th = self.wizard_state.thunderbird
        if th:
            if th.get("path"):
                lines.append(f"Thunderbird configurato: {th['path']}")
            elif th.get("auto_download"):
                lines.append("Thunderbird: da scaricare automaticamente")
            else:
                lines.append("Thunderbird: non configurato")
        else:
            lines.append("Thunderbird: non configurato")
        self.summary.config(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("end", "\n".join(lines))
        self.summary.config(state="disabled")



class FirstRunWizard(tk.Toplevel):
    """Wizard multi-step per la configurazione iniziale della sezione GLR (Frame-per-step, stato centralizzato, supporto ADMIN/FIRST_RUN)."""
    def __init__(self, parent, on_complete: Optional[Callable[[WizardState], None]] = None, on_cancel: Optional[Callable[[], None]] = None, mode: str = "FIRST_RUN", prefill: Optional[dict] = None):
        import threading
        try:
            print("[DIAG] FirstRunWizard: thread ident:", threading.get_ident())
        except Exception:
            pass
        super().__init__(parent)
        self.mode = mode.upper() if mode else "FIRST_RUN"
        self.title("Configurazione GLR" + (" – Admin" if self.mode == "ADMIN" else ""))
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Center the window on screen
        self.update_idletasks()
        width = 500
        height = 400
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.lift()
        self.attributes('-topmost', True)
        self.after(100, lambda: self.attributes('-topmost', False))
        
        self.parent = parent
        self.on_complete = on_complete
        self.on_cancel = on_cancel
        self.result = None
        try:
            print("[DIAG] FirstRunWizard: finestra creata e visibile")
        except Exception:
            pass
        # Precompila stato se in ADMIN
        if self.mode == "ADMIN" and prefill:
            self._wizard_state = WizardState(
                section_data=prefill.get("section_data", {}),
                import_result=prefill.get("import_result"),
                cd_config=prefill.get("cd_config"),
                thunderbird=prefill.get("thunderbird"),
                completed=prefill.get("completed", False)
            )
        else:
            self._wizard_state = WizardState()
        self._step = 0
        self._step_classes = [
            WelcomeStep,
            SectionDataStep,
            ImportSociStep,
            CdStep,
            ThunderbirdStep,
            SummaryStep,
        ]
        self._frames = [None] * len(self._step_classes)
        self._main_frame = ttk.Frame(self)
        self._main_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        self._nav_frame = ttk.Frame(self)
        self._nav_frame.pack(fill=tk.X, padx=16, pady=(0, 12))
        self._show_step(0)

    def _show_step(self, idx):
        if hasattr(self, '_current_frame') and self._current_frame:
            self._current_frame.pack_forget()
        self._step = idx
        if not self._frames[idx]:
            self._frames[idx] = self._step_classes[idx](self._main_frame, self, self._wizard_state)
        self._current_frame = self._frames[idx]
        self._current_frame.pack(fill=tk.BOTH, expand=True)
        self._update_nav()

    def _update_nav(self):
        for w in self._nav_frame.winfo_children():
            w.destroy()
        # Cancel button
        ttk.Button(self._nav_frame, text="Annulla", command=self._on_cancel, width=12).pack(side=tk.RIGHT, padx=(6, 0))
        # Navigation buttons
        if self._step > 0:
            ttk.Button(self._nav_frame, text="Indietro", command=self._prev, width=12).pack(side=tk.RIGHT, padx=(6, 0))
        # Step-specific buttons
        if hasattr(self._current_frame, 'on_skip') and callable(getattr(self._current_frame, 'on_skip', None)):
            ttk.Button(self._nav_frame, text="Salta", command=self._skip, width=12).pack(side=tk.RIGHT, padx=(6, 0))
        if self._step < len(self._step_classes) - 1:
            ttk.Button(self._nav_frame, text="Avanti", command=self._next, width=16).pack(side=tk.RIGHT)
        else:
            ttk.Button(self._nav_frame, text="Salva", command=self._on_save, width=16).pack(side=tk.RIGHT)

    def _next(self):
        frame = self._frames[self._step]
        if frame is not None and hasattr(frame, 'on_next') and not frame.on_next():
            return
        if self._step < len(self._step_classes) - 1:
            self._show_step(self._step + 1)

    def _prev(self):
        frame = self._frames[self._step]
        if frame is not None and hasattr(frame, 'on_back') and not frame.on_back():
            return
        if self._step > 0:
            self._show_step(self._step - 1)

    def _skip(self):
        frame = self._frames[self._step]
        if frame is not None and hasattr(frame, 'on_skip') and not frame.on_skip():
            return
        if self._step < len(self._step_classes) - 1:
            self._show_step(self._step + 1)

    def _on_cancel(self):
        if self.mode == "FIRST_RUN":
            if messagebox.askyesno("Annulla configurazione", "Annullare la configurazione guidata? I dati inseriti andranno persi.", parent=self):
                self.result = None
                if self.on_cancel:
                    self.on_cancel()
                self.destroy()
        else:
            # In ADMIN si può sempre annullare liberamente
            self.result = None
            if self.on_cancel:
                self.on_cancel()
            self.destroy()

    def _on_save(self):
        try:
            print("[DIAG] FirstRunWizard: chiusura wizard")
        except Exception:
            pass
        if self.mode == "FIRST_RUN":
            self._wizard_state.completed = True
        if self.on_complete:
            self.on_complete(self._wizard_state)
        self.result = self._wizard_state
        self.destroy()

