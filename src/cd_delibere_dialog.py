# -*- coding: utf-8 -*-
"""
CD Delibere UI Dialogs for Libro Soci
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from datetime import datetime

logger = logging.getLogger("librosoci")

class DeliberaDialog:
    """Dialog for adding/editing CD delibere"""
    
    def __init__(self, parent, meeting_id=None, delibera_id=None):
        """
        Initialize delibera dialog.
        
        Args:
            parent: Parent window
            meeting_id: CD meeting ID (required)
            delibera_id: If provided, edit existing delibera; otherwise create new
        """
        self.parent = parent
        self.meeting_id = meeting_id
        self.delibera_id = delibera_id
        self.result = None
        self.selected_allegato = None
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Nuova delibera" if not delibera_id else "Modifica delibera")
        self.dialog.geometry("600x500")
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
        
        # Numero
        num_frame = ttk.LabelFrame(scrollable_frame, text="Numero delibera")
        num_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Entry(num_frame, width=20).pack(side=tk.LEFT, padx=5, pady=5)
        self.entry_numero = num_frame.winfo_children()[-1]
        ttk.Label(num_frame, text="(es: 1/2025)").pack(side=tk.LEFT, padx=5)
        
        # Oggetto
        obj_frame = ttk.LabelFrame(scrollable_frame, text="Oggetto (Materia)")
        obj_frame.pack(fill=tk.X, padx=10, pady=5)
        self.text_oggetto = tk.Text(obj_frame, height=3, width=60)
        self.text_oggetto.pack(fill=tk.X, padx=5, pady=5)
        
        # Esito
        esito_frame = ttk.LabelFrame(scrollable_frame, text="Esito")
        esito_frame.pack(fill=tk.X, padx=10, pady=5)
        self.var_esito = tk.StringVar(value="APPROVATA")
        for esito in ["APPROVATA", "RESPINTA", "RINVIATA"]:
            ttk.Radiobutton(esito_frame, text=esito, variable=self.var_esito, value=esito).pack(side=tk.LEFT, padx=10, pady=5)
        
        # Data votazione
        data_frame = ttk.LabelFrame(scrollable_frame, text="Data votazione (YYYY-MM-DD)")
        data_frame.pack(fill=tk.X, padx=10, pady=5)
        self.entry_data_votazione = ttk.Entry(data_frame, width=15)
        self.entry_data_votazione.pack(side=tk.LEFT, padx=5, pady=5)
        self.entry_data_votazione.insert(0, datetime.now().strftime("%Y-%m-%d"))
        ttk.Button(data_frame, text="Oggi", command=lambda: self._set_data_today()).pack(side=tk.LEFT, padx=2)
        
        # Voti frame
        voti_frame = ttk.LabelFrame(scrollable_frame, text="Voti")
        voti_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(voti_frame, text="Favorevoli:").grid(row=0, column=0, padx=5, pady=3)
        self.entry_favorevoli = ttk.Spinbox(voti_frame, from_=0, to=999, width=5)
        self.entry_favorevoli.grid(row=0, column=1, padx=5, pady=3)
        
        ttk.Label(voti_frame, text="Contrari:").grid(row=0, column=2, padx=5, pady=3)
        self.entry_contrari = ttk.Spinbox(voti_frame, from_=0, to=999, width=5)
        self.entry_contrari.grid(row=0, column=3, padx=5, pady=3)
        
        ttk.Label(voti_frame, text="Astenuti:").grid(row=0, column=4, padx=5, pady=3)
        self.entry_astenuti = ttk.Spinbox(voti_frame, from_=0, to=999, width=5)
        self.entry_astenuti.grid(row=0, column=5, padx=5, pady=3)
        
        # Allegato
        all_frame = ttk.LabelFrame(scrollable_frame, text="Allegato (.doc/.pdf)")
        all_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_sub = ttk.Frame(all_frame)
        button_sub.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(button_sub, text="Sfoglia...", command=self._select_allegato).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_sub, text="Cancella", command=self._clear_allegato).pack(side=tk.LEFT, padx=2)
        
        self.label_allegato = ttk.Label(all_frame, text="Nessun file selezionato", foreground="gray")
        self.label_allegato.pack(anchor="w", padx=5, pady=5)
        

        # Verbale di riferimento
        verbale_frame = ttk.LabelFrame(scrollable_frame, text="Verbale di riferimento (opzionale)")
        verbale_frame.pack(fill=tk.X, padx=10, pady=5)

        self.verbale_id_var = tk.StringVar()
        self.combo_verbale = ttk.Combobox(verbale_frame, textvariable=self.verbale_id_var, state="readonly", width=40)
        self.combo_verbale.pack(side=tk.LEFT, padx=5, pady=5)
        self.verbale_map = {}
        default_verbale_id = None
        try:
            from cd_verbali import get_all_verbali
            verbali = get_all_verbali(self.meeting_id) if self.meeting_id else get_all_verbali()
            items = []
            for v in verbali:
                label = f"Verbale n. {v.get('id')} del {v.get('data_redazione','')}"
                self.verbale_map[label] = v.get('id')
                items.append(label)
            self.combo_verbale['values'] = ["(Nessuno)"] + items
            # Preseleziona il verbale della riunione, se esiste
            if self.meeting_id:
                try:
                    from cd_meetings import get_meeting_by_id
                    meeting = get_meeting_by_id(self.meeting_id)
                    # Cerca verbale associato (verbale_section_doc_id o simile)
                    if meeting:
                        # Cerca un verbale con cd_id uguale e data più vicina
                        for v in verbali:
                            if v.get('cd_id') == self.meeting_id:
                                default_verbale_id = v.get('id')
                                break
                except Exception:
                    pass
            if default_verbale_id:
                for label, vid in self.verbale_map.items():
                    if vid == default_verbale_id:
                        self.combo_verbale.set(label)
                        break
            else:
                self.combo_verbale.set("(Nessuno)")
        except Exception:
            self.combo_verbale['values'] = ["(Nessuno)"]
            self.combo_verbale.set("(Nessuno)")

        ttk.Label(verbale_frame, text="Riferimento (testo libero):").pack(side=tk.LEFT, padx=5)
        self.entry_verbale_rif = ttk.Entry(verbale_frame, width=30)
        self.entry_verbale_rif.pack(side=tk.LEFT, padx=5)

        # Note
        note_frame = ttk.LabelFrame(scrollable_frame, text="Note")
        note_frame.pack(fill=tk.X, padx=10, pady=5)
        self.text_note = tk.Text(note_frame, height=3, width=60)
        self.text_note.pack(fill=tk.X, padx=5, pady=5)
        
        # Load existing if editing
        if delibera_id:
            self._load_delibera()
        
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
        self.entry_data_votazione.delete(0, tk.END)
        self.entry_data_votazione.insert(0, datetime.now().strftime("%Y-%m-%d"))
    
    def _select_allegato(self):
        """Select allegato file"""
        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Seleziona allegato",
            filetypes=[
                ("Documenti", "*.doc *.docx *.pdf"),
                ("Word", "*.doc *.docx"),
                ("PDF", "*.pdf"),
                ("Tutti i file", "*.*")
            ]
        )
        
        if file_path:
            is_valid, msg = validate_allegato_file(file_path)
            if is_valid:
                self.selected_allegato = file_path
                self.label_allegato.config(text=file_path.split("\\")[-1], foreground="black")
            else:
                messagebox.showerror("Errore", f"File non valido: {msg}")
    
    def _clear_allegato(self):
        """Clear selected allegato"""
        self.selected_allegato = None
        self.label_allegato.config(text="Nessun file selezionato", foreground="gray")
    
    def _load_delibera(self):
        """Load existing delibera data for editing"""
        from cd_delibere import get_delibera_by_id
        delibera = get_delibera_by_id(self.delibera_id)

        if not delibera:
            try:
                from database import get_db_path
                db_path = get_db_path()
            except Exception:
                db_path = None

            try:
                logger.warning(
                    "DeliberaDialog: delibera not found (delibera_id=%r meeting_id=%r db=%r)",
                    self.delibera_id,
                    self.meeting_id,
                    db_path,
                )
            except Exception:
                pass
            messagebox.showerror(
                "Delibere",
                f"Impossibile caricare la delibera selezionata (ID: {self.delibera_id}).\n"
                "Potrebbe essere stata eliminata oppure c\u2019\u00e8 un errore di accesso al database."
            )
            try:
                self.dialog.destroy()
            except Exception:
                pass
            return

        try:
            loaded_meeting_id = delibera.get('cd_id')
            if loaded_meeting_id and (self.meeting_id is None or int(self.meeting_id) != int(loaded_meeting_id)):
                self.meeting_id = int(loaded_meeting_id)
        except Exception:
            pass

        if delibera:
            # Verbale di riferimento
            verbale_id = delibera.get('verbale_id')
            verbale_rif = delibera.get('verbale_riferimento') or ''
            if verbale_id:
                for label, vid in getattr(self, 'verbale_map', {}).items():
                    if str(vid) == str(verbale_id):
                        self.combo_verbale.set(label)
                        break
            else:
                self.combo_verbale.set("(Nessuno)")
            self.entry_verbale_rif.delete(0, tk.END)
            self.entry_verbale_rif.insert(0, verbale_rif)
            self.entry_numero.delete(0, tk.END)
            self.entry_numero.insert(0, delibera.get('numero', ''))
            
            self.text_oggetto.delete('1.0', tk.END)
            self.text_oggetto.insert('1.0', delibera.get('oggetto', ''))
            
            self.var_esito.set(delibera.get('esito', 'APPROVATA'))
            
            self.entry_data_votazione.delete(0, tk.END)
            self.entry_data_votazione.insert(0, delibera.get('data_votazione', ''))
            
            if delibera.get('favorevoli'):
                self.entry_favorevoli.delete(0, tk.END)
                self.entry_favorevoli.insert(0, str(delibera['favorevoli']))
            
            if delibera.get('contrari'):
                self.entry_contrari.delete(0, tk.END)
                self.entry_contrari.insert(0, str(delibera['contrari']))
            
            if delibera.get('astenuti'):
                self.entry_astenuti.delete(0, tk.END)
                self.entry_astenuti.insert(0, str(delibera['astenuti']))
            
            if delibera.get('allegato_path'):
                self.selected_allegato = delibera['allegato_path']
                self.label_allegato.config(text=delibera['allegato_path'].split("\\")[-1], foreground="black")
            
            self.text_note.delete('1.0', tk.END)
            self.text_note.insert('1.0', delibera.get('note', ''))
    
    def _save(self):
        """Save delibera"""
        numero = self.entry_numero.get().strip()
        oggetto = self.text_oggetto.get('1.0', tk.END).strip()
        esito = self.var_esito.get()
        data_votazione = self.entry_data_votazione.get().strip()
        favorevoli = self.entry_favorevoli.get() or None
        contrari = self.entry_contrari.get() or None
        astenuti = self.entry_astenuti.get() or None
        allegato_path = self.selected_allegato
        note = self.text_note.get('1.0', tk.END).strip()
        # Verbale di riferimento
        verbale_id = None
        verbale_rif = self.entry_verbale_rif.get().strip() or None
        if hasattr(self, 'combo_verbale'):
            label = self.combo_verbale.get()
            if label and label != "(Nessuno)":
                verbale_id = self.verbale_map.get(label)
        # Se non selezionato, eredita il verbale della riunione (se esiste)
        if not verbale_id and self.meeting_id:
            try:
                from cd_verbali import get_all_verbali
                verbali = get_all_verbali(self.meeting_id)
                if verbali:
                    verbale_id = verbali[0].get('id')
            except Exception:
                pass
        
        if not numero or not oggetto:
            messagebox.showwarning("Validazione", "Inserire numero e oggetto della delibera.")
            return
        
        try:
            if self.delibera_id:
                from cd_delibere import update_delibera
                if update_delibera(self.delibera_id, numero=numero, oggetto=oggetto, esito=esito,
                                   data_votazione=data_votazione if data_votazione else None,
                                   favorevoli=int(favorevoli) if favorevoli else None,
                                   contrari=int(contrari) if contrari else None,
                                   astenuti=int(astenuti) if astenuti else None,
                                   allegato_path=allegato_path, note=note if note else None,
                                   verbale_id=verbale_id, verbale_riferimento=verbale_rif):
                    messagebox.showinfo("Successo", "Delibera aggiornata.")
                    self.result = True
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Errore", "Errore durante l'aggiornamento.")
            else:
                if not self.meeting_id:
                    messagebox.showerror("Errore", "Selezionare prima una riunione CD per associare la delibera.")
                    return
                from cd_delibere import add_delibera
                delibera_id = add_delibera(self.meeting_id, numero, oggetto, esito=esito,
                                          data_votazione=data_votazione if data_votazione else None,
                                          favorevoli=int(favorevoli) if favorevoli else None,
                                          contrari=int(contrari) if contrari else None,
                                          astenuti=int(astenuti) if astenuti else None,
                                          allegato_path=allegato_path, note=note if note else None,
                                          verbale_id=verbale_id, verbale_riferimento=verbale_rif)
                if delibera_id > 0:
                    messagebox.showinfo("Successo", f"Delibera creata (ID: {delibera_id}).")
                    self.result = True
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Errore", "Errore durante la creazione.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore: {e}")
            logger.error("Error saving delibera: %s", e)


def validate_allegato_file(file_path: str):
    """Validate allegato file"""
    import os
    if not os.path.exists(file_path):
        return False, "File non trovato"
    
    valid_extensions = {'.doc', '.docx', '.pdf'}
    _, ext = os.path.splitext(file_path)
    
    if ext.lower() not in valid_extensions:
        return False, f"Formato non supportato: {ext}. Usa .doc, .docx o .pdf"
    
    return True, "OK"
