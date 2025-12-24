# -*- coding: utf-8 -*-
"""
CD Verbali UI Dialogs for GLR Gestione Locale Radioamatori
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from datetime import datetime

logger = logging.getLogger("librosoci")

class VerbaleDialog:
    """Dialog for adding/editing CD verbali"""
    
    def __init__(self, parent, meeting_id=None, verbale_id=None):
        """
        Initialize verbale dialog.
        
        Args:
            parent: Parent window
            meeting_id: CD meeting ID (optional). If omitted, creation is disabled.
            verbale_id: If provided, edit existing verbale; otherwise create new
        """
        self.parent = parent
        self.meeting_id = meeting_id
        self.verbale_id = verbale_id
        self.result = None
        self.selected_documento = None
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Nuovo verbale" if not verbale_id else "Modifica verbale")
        self.dialog.geometry("650x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Main frame with scrollbar
        canvas = tk.Canvas(self.dialog, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Data redazione
        data_frame = ttk.LabelFrame(scrollable_frame, text="Data redazione (YYYY-MM-DD)")
        data_frame.pack(fill=tk.X, padx=10, pady=5)
        self.entry_data_redazione = ttk.Entry(data_frame, width=15)
        self.entry_data_redazione.pack(side=tk.LEFT, padx=5, pady=5)
        self.entry_data_redazione.insert(0, datetime.now().strftime("%Y-%m-%d"))
        ttk.Button(data_frame, text="Oggi", command=self._set_data_today).pack(side=tk.LEFT, padx=2)
        
        # Presidente
        pres_frame = ttk.LabelFrame(scrollable_frame, text="Presidente/Coordinatore")
        pres_frame.pack(fill=tk.X, padx=10, pady=5)
        self.entry_presidente = ttk.Entry(pres_frame, width=50)
        self.entry_presidente.pack(fill=tk.X, padx=5, pady=5)
        
        # Segretario
        segr_frame = ttk.LabelFrame(scrollable_frame, text="Segretario (Redattore)")
        segr_frame.pack(fill=tk.X, padx=10, pady=5)
        self.entry_segretario = ttk.Entry(segr_frame, width=50)
        self.entry_segretario.pack(fill=tk.X, padx=5, pady=5)
        
        # OdG (Ordine del Giorno)
        odg_frame = ttk.LabelFrame(scrollable_frame, text="Ordine del Giorno (OdG)")
        odg_frame.pack(fill=tk.X, padx=10, pady=5)
        self.text_odg = tk.Text(odg_frame, height=5, width=70)
        self.text_odg.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(odg_frame, text="Elenca i punti dell'ordine del giorno", foreground="gray").pack(anchor="w", padx=5)
        
        # Documento
        doc_frame = ttk.LabelFrame(scrollable_frame, text="Documento verbale (.doc/.pdf)")
        doc_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_sub = ttk.Frame(doc_frame)
        button_sub.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(button_sub, text="Sfoglia...", command=self._select_documento).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_sub, text="Cancella", command=self._clear_documento).pack(side=tk.LEFT, padx=2)
        
        self.label_documento = ttk.Label(doc_frame, text="Nessun file selezionato", foreground="gray")
        self.label_documento.pack(anchor="w", padx=5, pady=5)
        
        # Note
        note_frame = ttk.LabelFrame(scrollable_frame, text="Note aggiuntive")
        note_frame.pack(fill=tk.X, padx=10, pady=5)
        self.text_note = tk.Text(note_frame, height=3, width=70)
        self.text_note.pack(fill=tk.X, padx=5, pady=5)
        
        # Load existing if editing
        if verbale_id:
            self._load_verbale()
        
        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons frame at bottom
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Salva", command=self._save).pack(side=tk.RIGHT, padx=2)
        ttk.Button(button_frame, text="Annulla", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=2)
    
    def _set_data_today(self):
        """Set date to today"""
        self.entry_data_redazione.delete(0, tk.END)
        self.entry_data_redazione.insert(0, datetime.now().strftime("%Y-%m-%d"))
    
    def _select_documento(self):
        """Select documento file"""
        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Seleziona verbale",
            filetypes=[
                ("Documenti", "*.doc *.docx *.pdf"),
                ("Word", "*.doc *.docx"),
                ("PDF", "*.pdf"),
                ("Tutti i file", "*.*")
            ]
        )
        
        if file_path:
            from cd_verbali import validate_documento
            is_valid, msg = validate_documento(file_path)
            if is_valid:
                self.selected_documento = file_path
                self.label_documento.config(text=file_path.split("\\")[-1], foreground="black")
            else:
                messagebox.showerror("Errore", f"File non valido: {msg}")
    
    def _clear_documento(self):
        """Clear selected documento"""
        self.selected_documento = None
        self.label_documento.config(text="Nessun file selezionato", foreground="gray")
    
    def _load_verbale(self):
        """Load existing verbale data for editing"""
        from cd_verbali import get_verbale_by_id
        # self.verbale_id may be optional; ensure we pass an int
        if self.verbale_id is None:
            return
        verbale = get_verbale_by_id(int(self.verbale_id))
        
        if verbale:
            self.entry_data_redazione.delete(0, tk.END)
            self.entry_data_redazione.insert(0, verbale.get('data_redazione', ''))
            
            self.entry_presidente.delete(0, tk.END)
            self.entry_presidente.insert(0, verbale.get('presidente', ''))
            
            self.entry_segretario.delete(0, tk.END)
            self.entry_segretario.insert(0, verbale.get('segretario', ''))
            
            self.text_odg.delete('1.0', tk.END)
            self.text_odg.insert('1.0', verbale.get('odg', ''))
            
            if verbale.get('documento_path'):
                self.selected_documento = verbale['documento_path']
                self.label_documento.config(text=verbale['documento_path'].split("\\")[-1], foreground="black")
            
            self.text_note.delete('1.0', tk.END)
            self.text_note.insert('1.0', verbale.get('note', ''))
    
    def _save(self):
        """Save verbale"""
        data_redazione = self.entry_data_redazione.get().strip()
        presidente = self.entry_presidente.get().strip()
        segretario = self.entry_segretario.get().strip()
        odg = self.text_odg.get('1.0', tk.END).strip()
        documento_path = self.selected_documento
        note = self.text_note.get('1.0', tk.END).strip()
        
        if not data_redazione:
            messagebox.showwarning("Validazione", "Inserire la data di redazione del verbale.")
            return
        
        try:
            datetime.strptime(data_redazione, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Errore", "Formato data non valido. Usa YYYY-MM-DD")
            return
        
        try:
            if self.verbale_id:
                from cd_verbali import update_verbale
                # Build kwargs only for fields provided to avoid passing None
                upd_kwargs = {}
                if data_redazione:
                    upd_kwargs['data_redazione'] = data_redazione
                if presidente:
                    upd_kwargs['presidente'] = presidente
                if segretario:
                    upd_kwargs['segretario'] = segretario
                if odg:
                    upd_kwargs['odg'] = odg
                if documento_path:
                    upd_kwargs['documento_path'] = documento_path
                if note:
                    upd_kwargs['note'] = note

                if update_verbale(int(self.verbale_id), **upd_kwargs):
                    messagebox.showinfo("Successo", "Verbale aggiornato.")
                    self.result = True
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Errore", "Errore durante l'aggiornamento.")
            else:
                if not self.meeting_id:
                    messagebox.showerror("Errore", "Impossibile creare verbale: nessuna riunione selezionata.")
                    return
                from cd_verbali import add_verbale
                add_kwargs = {}
                if segretario:
                    add_kwargs['segretario'] = segretario
                if presidente:
                    add_kwargs['presidente'] = presidente
                if odg:
                    add_kwargs['odg'] = odg
                if documento_path:
                    add_kwargs['documento_path'] = documento_path
                if note:
                    add_kwargs['note'] = note

                verbale_id = add_verbale(int(self.meeting_id), data_redazione, **add_kwargs)
                if verbale_id > 0:
                    messagebox.showinfo("Successo", f"Verbale creato (ID: {verbale_id}).")
                    self.result = True
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Errore", "Errore durante la creazione.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")
            logger.error("Error saving verbale: %s", e)
