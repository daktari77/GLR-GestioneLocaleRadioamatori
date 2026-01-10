# -*- coding: utf-8 -*-
"""
Export dialog for advanced CSV export with field selection
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import logging

logger = logging.getLogger("librosoci")

class ExportDialog(tk.Toplevel):
    """Dialog for exporting members to CSV with field selection."""
    
    def __init__(self, parent):
        """Initialize export dialog."""
        super().__init__(parent)
        self.title("Esporta soci in CSV")
        self.geometry("600x500")
        self.resizable(True, True)

        try:
            from .styles import ensure_app_named_fonts

            ensure_app_named_fonts(self.winfo_toplevel())
        except Exception:
            pass
        
        # Available fields from COLONNE
        self.all_fields = [
            ("id", "ID"),
            ("attivo", "Attivo"),
            ("nominativo", "Nominativo"),
            ("nome", "Nome"),
            ("cognome", "Cognome"),
            ("matricola", "Matricola"),
            ("data_nascita", "Data nascita"),
            ("luogo_nascita", "Luogo nascita"),
            ("codicefiscale", "Codice Fiscale"),
            ("indirizzo", "Indirizzo"),
            ("cap", "CAP"),
            ("citta", "Città"),
            ("provincia", "Provincia"),
            ("email", "Email"),
            ("telefono", "Telefono"),
            ("familiare", "Familiare"),
            ("privacy_signed", "Privacy firmato"),
            ("privacy_ok", "Privacy accordato"),
            ("privacy_data", "Data privacy"),
            ("cd_ruolo", "Stato"),
            ("voto", "Diritto voto"),
            ("data_iscrizione", "Data iscrizione"),
            ("delibera_numero", "Delibera numero"),
            ("delibera_data", "Delibera data"),
            ("note", "Note"),
        ]
        
        # Default selected fields
        self.default_fields = ["nominativo", "nome", "cognome", "matricola", "email", "attivo", "privacy_signed", "data_iscrizione"]
        
        self._build_ui()
        
        # Make modal
        self.transient(parent)
        self.grab_set()
    
    def _build_ui(self):
        """Build the dialog UI."""
        # Header
        header = ttk.Label(self, text="Seleziona i campi da esportare:", font="AppBold")
        header.pack(pady=10, padx=10)
        
        # Buttons for presets
        preset_frame = ttk.Frame(self)
        preset_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(preset_frame, text="Seleziona tutto", command=self._select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Deseleziona tutto", command=self._select_none).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Campi essenziali", command=self._select_default).pack(side=tk.LEFT, padx=2)
        
        # Scrollable frame with checkboxes
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create checkboxes
        self.field_vars = {}
        for field, label in self.all_fields:
            var = tk.BooleanVar(value=field in self.default_fields)
            check = ttk.Checkbutton(scrollable_frame, text=label, variable=var)
            check.pack(anchor="w", padx=5, pady=2)
            self.field_vars[field] = var
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Filter options
        filter_frame = ttk.LabelFrame(self, text="Opzioni di esportazione")
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.include_inactive_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="Includi soci inattivi", variable=self.include_inactive_var).pack(anchor="w", padx=5)
        
        self.include_deleted_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="Includi soci eliminati", variable=self.include_deleted_var).pack(anchor="w", padx=5)
        
        # Buttons at bottom
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text="Esporta", command=self._export).pack(side=tk.RIGHT, padx=2)
        ttk.Button(button_frame, text="Annulla", command=self.destroy).pack(side=tk.RIGHT, padx=2)
    
    def _select_all(self):
        """Select all fields."""
        for var in self.field_vars.values():
            var.set(True)
    
    def _select_none(self):
        """Deselect all fields."""
        for var in self.field_vars.values():
            var.set(False)
    
    def _select_default(self):
        """Select default fields."""
        for field, var in self.field_vars.items():
            var.set(field in self.default_fields)
    
    def _export(self):
        """Export selected fields to CSV."""
        # Get selected fields
        selected_fields = [field for field, var in self.field_vars.items() if var.get()]
        
        if not selected_fields:
            messagebox.showwarning("Selezione", "Selezionare almeno un campo")
            return
        
        # Get file path
        file_path = filedialog.asksaveasfilename(
            parent=self,
            defaultext=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="soci_export.csv"
        )
        
        if not file_path:
            return
        
        try:
            from database import fetch_all
            
            # Build SQL
            sql = f"SELECT {', '.join(selected_fields)} FROM soci WHERE 1=1"
            if not self.include_inactive_var.get():
                sql += " AND attivo = 1"
            if not self.include_deleted_var.get():
                sql += " AND deleted_at IS NULL"
            sql += " ORDER BY nominativo"
            
            rows = fetch_all(sql)
            
            if not rows:
                messagebox.showwarning("Export", "Nessun socio da esportare")
                return
            
            # Write CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=selected_fields)
                writer.writeheader()

                for row in rows:
                    out_row = {}
                    for field in selected_fields:
                        val = row[field]
                        # If field is None or empty, write empty string
                        if val is None or (isinstance(val, str) and val == ''):
                            out_row[field] = ''
                            continue

                        # Map boolean-like fields to Si/No
                        if field in ('attivo', 'voto'):
                            try:
                                ival = int(val)
                                out_row[field] = 'Si' if ival == 1 else 'No' if ival == 0 else str(val)
                            except Exception:
                                # Fallback: truthy -> Si, falsy -> No
                                out_row[field] = 'Si' if val else 'No'
                        else:
                            out_row[field] = val

                    writer.writerow(out_row)
            
            messagebox.showinfo("Successo", f"Esportati {len(rows)} soci in:\n{file_path}")
            self.destroy()
            
        except Exception as e:
            logger.error("Export failed: %s", e)
            messagebox.showerror("Errore", f"Errore nell'esportazione: {str(e)}")
