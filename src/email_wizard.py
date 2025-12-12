# -*- coding: utf-8 -*-
"""
Email Wizard for Libro Soci v4.2a
Simplified wizard for creating emails from templates
"""

import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import logging
from datetime import datetime
from typing import List, Dict, Optional
import urllib.parse
import webbrowser
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import format_datetime, parsedate_to_datetime, getaddresses
from config import SEC_DOCS, THUNDERBIRD_EXE
from config_manager import load_config

logger = logging.getLogger("librosoci")


class EmailWizard:
    """Wizard for creating emails from templates"""
    
    # Email templates
    TEMPLATES = {
        "convocazione_cd": """Gentili Consiglieri,

siete convocati per la riunione del Consiglio Direttivo che si terrà in data {data} alle ore {ora} presso {luogo}.

Ordine del giorno:
{odg}

Cordiali saluti,
Il Presidente""",
        "comunicazione_generale": """Cari Soci,

vi informiamo che {messaggio}

Per ulteriori informazioni potete contattarci rispondendo a questa email.

Cordiali saluti,
La Segreteria""",
        "convocazione_assemblea": """Gentili Soci,

siete convocati per l'Assemblea Ordinaria/Straordinaria dei Soci che si terrà in:

PRIMA CONVOCAZIONE: {data} ore {ora}
SECONDA CONVOCAZIONE: {data2} ore {ora2}

Presso: {luogo}

Ordine del giorno:
{odg}

La vostra presenza è importante.

Cordiali saluti,
Il Presidente""",
        "promemoria_quota": """Caro Socio,

ti ricordiamo che la quota sociale per l'anno {anno} non risulta ancora versata.

Importo: {importo}
Causale: {causale}
IBAN: {iban}

Per qualsiasi chiarimento siamo a disposizione.

Cordiali saluti,
Il Tesoriere""",
        "personalizzata": ""
    }
    
    def __init__(self, parent):
        self.parent = parent
        self.win = tk.Toplevel(parent)
        self.win.title("📧 Gestione Email")
        self.win.geometry("800x750")
        self.win.transient(parent)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the wizard UI"""
        # Title
        title_frame = ttk.Frame(self.win)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(title_frame, text="📧 Gestione Email", font=("Arial", 14, "bold")).pack(anchor="w")
        
        notebook = ttk.Notebook(self.win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab: composizione
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="Composizione")
        
        # Data
        row = 0
        ttk.Label(main_frame, text="Data:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.entry_data = ttk.Entry(main_frame, width=15)
        self.entry_data.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        self.entry_data.insert(0, datetime.now().strftime("%d/%m/%Y"))
        ttk.Button(main_frame, text="Oggi", command=self._set_today).grid(row=row, column=2, sticky="w", padx=5, pady=5)
        
        # Oggetto
        row += 1
        ttk.Label(main_frame, text="Oggetto:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.entry_oggetto = ttk.Entry(main_frame, width=60)
        self.entry_oggetto.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        # Selezione soci
        row += 1
        ttk.Label(main_frame, text="Destinatari:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        self.destinatari_var = tk.StringVar(value="attivi")
        dest_frame = ttk.Frame(main_frame)
        dest_frame.grid(row=row, column=1, columnspan=3, sticky="w", padx=5, pady=5)
        ttk.Radiobutton(dest_frame, text="Soci Attivi", variable=self.destinatari_var, value="attivi", command=self._update_recipient_count).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(dest_frame, text="Consiglio Direttivo", variable=self.destinatari_var, value="cd", command=self._update_recipient_count).pack(side=tk.LEFT, padx=5)
        ttk.Button(dest_frame, text="Anteprima destinatari", command=self._show_recipients).pack(side=tk.LEFT, padx=10)
        self.label_count = ttk.Label(dest_frame, text="", foreground="blue")
        self.label_count.pack(side=tk.LEFT, padx=5)
        
        # Template selector
        row += 1
        ttk.Label(main_frame, text="Testo email:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="nw", padx=5, pady=5)
        template_frame = ttk.Frame(main_frame)
        template_frame.grid(row=row, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(template_frame, text="Seleziona template:").pack(side=tk.LEFT, padx=5)
        self.template_var = tk.StringVar()
        template_combo = ttk.Combobox(template_frame, textvariable=self.template_var, width=30, state="readonly")
        template_combo['values'] = (
            'Nessuno (testo libero)',
            'Convocazione CD',
            'Comunicazione Generale',
            'Convocazione Assemblea',
            'Promemoria Quota'
        )
        template_combo.current(0)
        template_combo.pack(side=tk.LEFT, padx=5)
        template_combo.bind('<<ComboboxSelected>>', self._on_template_selected)
        
        # Testo email
        row += 1
        text_frame = ttk.LabelFrame(main_frame, text="Corpo del messaggio", padding=5)
        text_frame.grid(row=row, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
        
        self.text_email = scrolledtext.ScrolledText(text_frame, height=15, wrap=tk.WORD)
        self.text_email.pack(fill=tk.BOTH, expand=True)
        
        # ODG section
        row += 1
        odg_frame = ttk.LabelFrame(main_frame, text="Ordine del Giorno (opzionale)", padding=5)
        odg_frame.grid(row=row, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
        
        odg_buttons = ttk.Frame(odg_frame)
        odg_buttons.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(odg_buttons, text="Incolla ODG da riunione:").pack(side=tk.LEFT, padx=5)
        ttk.Button(odg_buttons, text="📋 Carica da Riunione", command=self._load_odg_from_meeting).pack(side=tk.LEFT, padx=5)
        
        self.text_odg = scrolledtext.ScrolledText(odg_frame, height=8, wrap=tk.WORD)
        self.text_odg.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=2)
        main_frame.rowconfigure(5, weight=1)
        
        # Tab: email salvate
        saved_frame = ttk.Frame(notebook)
        notebook.add(saved_frame, text="Email salvate")
        self._build_saved_tab(saved_frame)

        # Buttons (composizione tab actions)
        button_frame = ttk.Frame(self.win)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Invia con Thunderbird", command=self._send_with_thunderbird).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Salva .eml", command=self._save_eml).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="✓ Crea Email", command=self._create_email, style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Anteprima", command=self._preview_email).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Annulla", command=self.win.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Update recipient count on load
        self._update_recipient_count()
        self._refresh_eml_list()

    def _build_saved_tab(self, frame: ttk.Frame):
        """Build the tab that lists saved EML files."""
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, pady=5, padx=5)
        ttk.Button(toolbar, text="Aggiorna elenco", command=self._refresh_eml_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Apri .eml", command=self._open_selected_eml).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Elimina .eml", command=self._delete_selected_eml).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Apri cartella EML", command=self._open_eml_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Avvia Thunderbird", command=self._launch_thunderbird).pack(side=tk.LEFT, padx=2)

        columns = ("oggetto", "data", "file")
        self.eml_tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        self.eml_tree.heading("oggetto", text="Oggetto")
        self.eml_tree.heading("data", text="Data")
        self.eml_tree.heading("file", text="File")
        self.eml_tree.column("oggetto", width=340, anchor="w")
        self.eml_tree.column("data", width=140, anchor="center")
        self.eml_tree.column("file", width=260, anchor="w")

        scrollbar_y = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.eml_tree.yview)
        scrollbar_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.eml_tree.xview)
        self.eml_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.eml_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5))
        scrollbar_x.pack(fill=tk.X, padx=5)
    
    def _set_today(self):
        """Set data field to today"""
        self.entry_data.delete(0, tk.END)
        self.entry_data.insert(0, datetime.now().strftime("%d/%m/%Y"))
    
    def _update_recipient_count(self):
        """Update recipient count label"""
        try:
            recipients = self._get_recipients()
            count = len(recipients)
            self.label_count.config(text=f"({count} destinatari)")
        except Exception as e:
            logger.error("Error counting recipients: %s", e)
            self.label_count.config(text="")
    
    def _get_recipients(self):
        """Get list of recipients based on selection"""
        from database import fetch_all
        
        filter_type = self.destinatari_var.get()
        
        if filter_type == "cd":
            # Only CD members with email
            sql = """
                SELECT DISTINCT email, nome, cognome 
                FROM soci 
                WHERE attivo = 1 
                AND cd_ruolo IS NOT NULL 
                AND cd_ruolo != '' 
                AND cd_ruolo != 'Socio'
                AND cd_ruolo != 'Ex Socio'
                AND email IS NOT NULL 
                AND email != ''
                ORDER BY cognome, nome
            """
        else:  # attivi
            # All active members with email
            sql = """
                SELECT DISTINCT email, nome, cognome 
                FROM soci 
                WHERE attivo = 1 
                AND email IS NOT NULL 
                AND email != ''
                ORDER BY cognome, nome
            """
        
        return fetch_all(sql)
    
    def _show_recipients(self):
        """Show recipients in a dialog"""
        recipients = self._get_recipients()
        
        dialog = tk.Toplevel(self.win)
        dialog.title("Anteprima Destinatari")
        dialog.geometry("600x400")
        dialog.transient(self.win)
        
        ttk.Label(dialog, text=f"Destinatari selezionati: {len(recipients)}", font=("Arial", 10, "bold")).pack(padx=10, pady=10)
        
        # Treeview with scrollbar
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(frame, columns=('email', 'nome'), show='headings', height=15)
        tree.heading('email', text='Email')
        tree.heading('nome', text='Nome')
        tree.column('email', width=250)
        tree.column('nome', width=200)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        for r in recipients:
            tree.insert('', 'end', values=(r[0], f"{r[2]} {r[1]}"))
        
        ttk.Button(dialog, text="Chiudi", command=dialog.destroy).pack(pady=10)
    
    def _on_template_selected(self, event=None):
        """Load template text when selected"""
        template_name = self.template_var.get()
        
        template_map = {
            'Nessuno (testo libero)': 'personalizzata',
            'Convocazione CD': 'convocazione_cd',
            'Comunicazione Generale': 'comunicazione_generale',
            'Convocazione Assemblea': 'convocazione_assemblea',
            'Promemoria Quota': 'promemoria_quota'
        }
        
        key = template_map.get(template_name, 'personalizzata')
        template_text = self.TEMPLATES.get(key, '')
        
        self.text_email.delete('1.0', tk.END)
        self.text_email.insert('1.0', template_text)
        
        # Suggest oggetto if not set
        if not self.entry_oggetto.get():
            if key == 'convocazione_cd':
                self.entry_oggetto.delete(0, tk.END)
                self.entry_oggetto.insert(0, "Convocazione Consiglio Direttivo")
            elif key == 'convocazione_assemblea':
                self.entry_oggetto.delete(0, tk.END)
                self.entry_oggetto.insert(0, "Convocazione Assemblea Soci")
    
    def _load_odg_from_meeting(self):
        """Load ODG from a CD meeting"""
        from cd_meetings import get_all_meetings
        
        # Get recent meetings
        meetings = get_all_meetings()
        if not meetings:
            messagebox.showinfo("Info", "Nessuna riunione trovata nel database.", parent=self.win)
            return
        
        # Create selection dialog
        dialog = tk.Toplevel(self.win)
        dialog.title("Seleziona Riunione")
        dialog.geometry("700x400")
        dialog.transient(self.win)
        
        ttk.Label(dialog, text="Seleziona una riunione da cui copiare l'ODG:", font=("Arial", 10, "bold")).pack(padx=10, pady=10)
        
        # Treeview
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(frame, columns=('id', 'data', 'titolo'), show='headings', height=12)
        tree.heading('id', text='ID')
        tree.heading('data', text='Data')
        tree.heading('titolo', text='Titolo')
        tree.column('id', width=50)
        tree.column('data', width=100)
        tree.column('titolo', width=400)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        for m in meetings:
            tree.insert('', 'end', values=(m['id'], m['data'], m['titolo'] or ''))
        
        def on_select():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Attenzione", "Seleziona una riunione.", parent=dialog)
                return
            
            meeting_id = tree.item(selection[0])['values'][0]
            from cd_meetings import get_meeting_by_id
            meeting = get_meeting_by_id(int(meeting_id))
            
            if meeting and meeting.get('odg'):
                self.text_odg.delete('1.0', tk.END)
                self.text_odg.insert('1.0', meeting['odg'])
                dialog.destroy()
            else:
                messagebox.showinfo("Info", "Questa riunione non ha un ODG associato.", parent=dialog)
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text="Carica ODG", command=on_select).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Annulla", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _preview_email(self):
        """Show email preview"""
        subject = self.entry_oggetto.get().strip()
        body = self._build_body_text()
        
        # Show preview dialog
        dialog = tk.Toplevel(self.win)
        dialog.title("Anteprima Email")
        dialog.geometry("700x500")
        dialog.transient(self.win)
        
        ttk.Label(dialog, text="Oggetto:", font=("Arial", 10, "bold")).pack(anchor='w', padx=10, pady=(10, 0))
        subject_text = tk.Text(dialog, height=2, wrap=tk.WORD)
        subject_text.pack(fill=tk.X, padx=10, pady=5)
        subject_text.insert('1.0', subject)
        subject_text.config(state='disabled')
        
        ttk.Label(dialog, text="Corpo:", font=("Arial", 10, "bold")).pack(anchor='w', padx=10, pady=(10, 0))
        body_text = scrolledtext.ScrolledText(dialog, height=20, wrap=tk.WORD)
        body_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        body_text.insert('1.0', body)
        body_text.config(state='disabled')
        
        ttk.Button(dialog, text="Chiudi", command=dialog.destroy).pack(pady=10)
    
    def _create_email(self):
        """Generate mailto URL and open email client"""
        try:
            subject, body, bcc_emails = self._collect_email_parts()
        except ValueError:
            return
        bcc_str = ','.join(bcc_emails)
        
        # Create mailto URL
        mailto_url = f"mailto:?subject={urllib.parse.quote(subject)}&bcc={urllib.parse.quote(bcc_str)}&body={urllib.parse.quote(body)}"
        
        # Check URL length (some email clients have limits)
        if len(mailto_url) > 2000:
            # Fallback: copy to clipboard
            result = messagebox.askyesno(
                "URL Troppo Lungo",
                f"L'email è troppo lunga per il comando mailto.\n\n"
                f"Destinatari: {len(bcc_emails)}\n\n"
                f"Vuoi copiare i dati negli appunti?",
                parent=self.win
            )
            if result:
                clipboard_text = f"Oggetto:\n{subject}\n\nDestinatari (BCC):\n{bcc_str}\n\nCorpo:\n{body}"
                self.win.clipboard_clear()
                self.win.clipboard_append(clipboard_text)
                messagebox.showinfo("Successo", "Dati copiati negli appunti!", parent=self.win)
        else:
            # Open email client
            try:
                webbrowser.open(mailto_url)
                messagebox.showinfo("Successo", f"Email preparata con {len(bcc_emails)} destinatari in BCC.", parent=self.win)
                self.win.destroy()
            except Exception as e:
                logger.error("Failed to open email client: %s", e)
                messagebox.showerror("Errore", f"Impossibile aprire il client email:\n{e}", parent=self.win)

    def _send_with_thunderbird(self):
        """Apri la composizione in Thunderbird con i dati correnti o dalla selezione EML."""
        subject = body = None
        bcc_emails: List[str] = []

        try:
            subject, body, bcc_emails = self._collect_email_parts(show_warnings=False)
        except ValueError:
            eml_parts = self._get_selected_eml_parts()
            if eml_parts:
                subject, body, bcc_emails = eml_parts
            else:
                # show the validation warning from the form
                self._collect_email_parts(show_warnings=True)
                return

        exe = self._get_thunderbird_path()
        if not exe or not os.path.exists(exe):
            messagebox.showerror(
                "Thunderbird",
                "Percorso Thunderbird non configurato o non trovato. Imposta il percorso in Preferenze > Client posta.",
                parent=self.win,
            )
            return

        compose_parts = [
            f"subject='{self._escape_thunderbird_value(subject or '')}'",
            f"body='{self._escape_thunderbird_value(body or '')}'",
        ]
        if bcc_emails:
            bcc_joined = ",".join(bcc_emails)
            compose_parts.append(f"bcc='{self._escape_thunderbird_value(bcc_joined)}'")
        compose_str = ",".join(compose_parts)

        try:
            subprocess.Popen([exe, "-compose", compose_str])
            messagebox.showinfo(
                "Thunderbird",
                f"Bozza creata con {len(bcc_emails)} destinatari in BCC.",
                parent=self.win,
            )
        except FileNotFoundError:
            messagebox.showerror("Thunderbird", f"Percorso Thunderbird non valido:\n{exe}", parent=self.win)
        except Exception as exc:
            logger.error("Impossibile avviare Thunderbird: %s", exc)
            messagebox.showerror("Thunderbird", f"Impossibile avviare Thunderbird:\n{exc}", parent=self.win)

    def _get_selected_eml_parts(self):
        """Se è selezionato un .eml nella tab, restituisce (subject, body, bcc list)."""
        if not hasattr(self, 'eml_tree'):
            return None
        selection = self.eml_tree.selection()
        if not selection:
            messagebox.showwarning(
                "Thunderbird",
                "Compila l'oggetto oppure seleziona un .eml dalla tab Email salvate.",
                parent=self.win,
            )
            return None
        fname = self.eml_tree.item(selection[0]).get('values', ['','', ''])[-1]
        path = os.path.join(SEC_DOCS, "email_eml", fname)
        if not os.path.exists(path):
            messagebox.showerror("Thunderbird", f"File non trovato:\n{path}", parent=self.win)
            self._refresh_eml_list()
            return None
        try:
            with open(path, 'rb') as fp:
                msg = BytesParser(policy=policy.default).parse(fp)
        except Exception as exc:
            logger.error("Impossibile leggere il file .eml %s: %s", path, exc)
            messagebox.showerror("Thunderbird", f"Impossibile leggere il file .eml:\n{exc}", parent=self.win)
            return None

        subject = (msg.get('Subject') or '').strip()
        bcc_header = msg.get('Bcc') or ''
        bcc_emails = [addr for _name, addr in getaddresses([bcc_header]) if addr]

        body = ""
        try:
            if msg.is_multipart():
                preferred = msg.get_body(preferencelist=('plain',))
                if preferred:
                    body = preferred.get_content()
                else:
                    alt = msg.get_body(preferencelist=('html',))
                    body = alt.get_content() if alt else ""
            else:
                body = msg.get_content()
        except Exception as exc:
            logger.warning("Errore leggendo il corpo da %s: %s", fname, exc)
            try:
                body = msg.get_content()
            except Exception:
                body = ""

        return subject, body, bcc_emails

    def _build_body_text(self) -> str:
        body = self.text_email.get('1.0', tk.END).strip()
        odg = self.text_odg.get('1.0', tk.END).strip()
        if '{odg}' in body and odg:
            body = body.replace('{odg}', odg)
        return body

    def _collect_email_parts(self, show_warnings: bool = True):
        """Return (subject, body, bcc_emails); raise ValueError if validation fails."""
        subject = self.entry_oggetto.get().strip()
        if not subject:
            if show_warnings:
                messagebox.showwarning("Attenzione", "Inserisci l'oggetto dell'email.", parent=self.win)
            raise ValueError("missing subject")

        body = self._build_body_text()
        if not body:
            if show_warnings:
                messagebox.showwarning("Attenzione", "Inserisci il testo dell'email.", parent=self.win)
            raise ValueError("missing body")

        recipients = self._get_recipients()
        if not recipients:
            if show_warnings:
                messagebox.showwarning("Attenzione", "Nessun destinatario trovato.", parent=self.win)
            raise ValueError("no recipients")

        bcc_emails = [r[0] for r in recipients]
        return subject, body, bcc_emails

    def _save_eml(self):
        """Export the composed email to a .eml file."""
        try:
            subject, body, bcc_emails = self._collect_email_parts()
        except ValueError:
            return

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['To'] = 'undisclosed-recipients:;'
        if bcc_emails:
            msg['Bcc'] = ', '.join(bcc_emails)
        msg['Date'] = format_datetime(datetime.now())
        msg.set_content(body)

        safe_subject = subject.replace(' ', '_').replace('/', '-').replace('\\', '-').replace(':', '-').replace('*', '-').replace('?', '-').replace('"', "'").replace('<', '-').replace('>', '-').replace('|', '-')[0:60]
        default_name = f"eml_{safe_subject}-{datetime.now():%Y%m%d}.eml"
        default_dir = os.path.join(SEC_DOCS, "email_eml")
        try:
            os.makedirs(default_dir, exist_ok=True)
        except Exception as exc:
            logger.warning("Impossibile creare cartella EML %s: %s", default_dir, exc)
            default_dir = None
        path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Salva email come .eml",
            defaultextension=".eml",
            filetypes=[("EML file", "*.eml"), ("Tutti i file", "*.*")],
            initialdir=default_dir,
            initialfile=default_name,
        )
        if not path:
            return

        if not path.lower().endswith('.eml'):
            path += '.eml'

        try:
            with open(path, 'wb') as f:
                f.write(msg.as_bytes())
            messagebox.showinfo("Esporta .eml", f"File salvato:\n{path}", parent=self.win)
        except Exception as exc:
            logger.error("Errore salvataggio EML: %s", exc)
            messagebox.showerror("Errore", f"Impossibile salvare il file .eml:\n{exc}", parent=self.win)

    # --------------------------------------------------
    # Email salvate (.eml)
    # --------------------------------------------------
    def _refresh_eml_list(self):
        directory = os.path.join(SEC_DOCS, "email_eml")
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as exc:
            logger.error("Impossibile creare cartella EML: %s", exc)
            messagebox.showerror("Errore", f"Impossibile creare la cartella EML:\n{exc}", parent=self.win)
            return

        if not hasattr(self, 'eml_tree'):
            return

        for item in self.eml_tree.get_children():
            self.eml_tree.delete(item)

        try:
            files = [f for f in os.listdir(directory) if f.lower().endswith('.eml')]
        except Exception as exc:
            logger.error("Impossibile elencare i file EML: %s", exc)
            messagebox.showerror("Errore", f"Impossibile leggere la cartella EML:\n{exc}", parent=self.win)
            return

        rows = []
        for fname in files:
            path = os.path.join(directory, fname)
            subject = "(senza oggetto)"
            date_str = ""
            try:
                with open(path, 'rb') as fp:
                    msg = BytesParser(policy=policy.default).parse(fp)
                subject = msg.get('Subject') or subject
                dt = None
                try:
                    if msg.get('Date'):
                        dt = parsedate_to_datetime(msg.get('Date'))
                except Exception:
                    dt = None
                if not dt:
                    ts = os.path.getmtime(path)
                    dt = datetime.fromtimestamp(ts)
                date_str = dt.strftime('%Y-%m-%d %H:%M') if dt else ""
            except Exception as exc:
                logger.warning("Errore leggendo %s: %s", fname, exc)
                try:
                    ts = os.path.getmtime(path)
                    date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    date_str = ""

            rows.append((subject, date_str, fname))

        # sort by date desc
        rows.sort(key=lambda r: r[1], reverse=True)
        for subject, date_str, fname in rows:
            self.eml_tree.insert('', 'end', values=(subject, date_str, fname))

    def _open_selected_eml(self):
        if not hasattr(self, 'eml_tree'):
            return
        selection = self.eml_tree.selection()
        if not selection:
            messagebox.showinfo("Apri .eml", "Seleziona un file dall'elenco.", parent=self.win)
            return
        fname = self.eml_tree.item(selection[0]).get('values', ['','', ''])[-1]
        path = os.path.join(SEC_DOCS, "email_eml", fname)
        if not os.path.exists(path):
            messagebox.showerror("Errore", f"File non trovato:\n{path}", parent=self.win)
            self._refresh_eml_list()
            return
        try:
            os.startfile(path)
        except Exception as exc:
            logger.error("Impossibile aprire %s: %s", path, exc)
            messagebox.showerror("Errore", f"Impossibile aprire il file .eml:\n{exc}", parent=self.win)

    def _delete_selected_eml(self):
        if not hasattr(self, 'eml_tree'):
            return
        selection = self.eml_tree.selection()
        if not selection:
            messagebox.showinfo("Elimina .eml", "Seleziona un file dall'elenco.", parent=self.win)
            return
        fname = self.eml_tree.item(selection[0]).get('values', ['','', ''])[-1]
        path = os.path.join(SEC_DOCS, "email_eml", fname)
        if not os.path.exists(path):
            messagebox.showerror("Errore", f"File non trovato:\n{path}", parent=self.win)
            self._refresh_eml_list()
            return
        if not messagebox.askyesno("Conferma", f"Vuoi eliminare il file:\n{fname}?", parent=self.win):
            return
        try:
            os.remove(path)
            self.eml_tree.delete(selection[0])
        except Exception as exc:
            logger.error("Impossibile eliminare %s: %s", path, exc)
            messagebox.showerror("Errore", f"Impossibile eliminare il file .eml:\n{exc}", parent=self.win)

    def _open_eml_folder(self):
        directory = os.path.join(SEC_DOCS, "email_eml")
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("Errore", f"Impossibile creare la cartella EML:\n{exc}", parent=self.win)
            return
        try:
            os.startfile(directory)
        except Exception as exc:
            logger.error("Impossibile aprire la cartella EML: %s", exc)
            messagebox.showerror("Errore", f"Impossibile aprire la cartella EML:\n{exc}", parent=self.win)

    def _launch_thunderbird(self):
        directory = os.path.join(SEC_DOCS, "email_eml")
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("Errore", f"Impossibile creare la cartella EML:\n{exc}", parent=self.win)
            return
        exe = self._get_thunderbird_path()
        if not exe or not os.path.exists(exe):
            messagebox.showerror("Thunderbird", "Percorso Thunderbird non configurato o non trovato. Imposta il percorso in Preferenze > Client posta.", parent=self.win)
            return
        try:
            subprocess.Popen([exe], cwd=directory)
        except Exception as exc:
            logger.error("Impossibile avviare Thunderbird: %s", exc)
            messagebox.showerror("Thunderbird", f"Impossibile avviare Thunderbird:\n{exc}", parent=self.win)

    @staticmethod
    def _escape_thunderbird_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _get_thunderbird_path(self) -> str:
        try:
            cfg = load_config()
            cfg_path = (cfg or {}).get("thunderbird_path") or ""
        except Exception:
            cfg_path = ""
        return cfg_path or THUNDERBIRD_EXE


def show_email_wizard(parent):
    """Show the email wizard"""
    EmailWizard(parent)
