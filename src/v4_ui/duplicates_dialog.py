# -*- coding: utf-8 -*-
"""
Duplicates detection and merge dialog for GLR - Gestione Locale Radioamatori
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger("librosoci")

class DuplicatesDialog:
    """Dialog for finding and merging duplicate members."""
    
    def __init__(self, parent):
        """Initialize the duplicates dialog."""
        self.parent = parent
        self.duplicates_groups = []
        self.current_group_index = 0
        self.current_group_members = []
        self.merge_fields = [
            'nome', 'cognome', 'nominativo', 'nominativo2',
            'data_nascita', 'luogo_nascita', 'codicefiscale',
            'indirizzo', 'cap', 'citta', 'provincia',
            'email', 'telefono', 'attivo',
            'delibera_numero', 'delibera_data',
            'voto', 'familiare', 'socio', 'cd_ruolo',
            'privacy_ok', 'privacy_data', 'privacy_scadenza', 'privacy_signed',
            'note'
        ]
        self.master_var = tk.IntVar(value=0)
        self.field_checkbox_vars: dict[str, dict[int, tk.BooleanVar]] = {}
        self.field_selection_labels: dict[str, ttk.Label] = {}
        self.field_value_labels: dict[str, dict[int, ttk.Label]] = {}
        self.field_value_labels: dict[str, dict[int, ttk.Label]] = {}
        
        # Create dialog window
        self.window = tk.Toplevel(parent)
        self.window.title("Ricerca e Merge Duplicati")
        self.window.geometry("1200x720")
        self.window.resizable(True, True)
        
        self._build_ui()
        self._find_duplicates()
        self._setup_shortcuts()
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for dialog."""
        # Esc: Close dialog
        self.window.bind("<Escape>", lambda e: self.window.destroy())
        
        # Left/Right arrows: Navigate between groups
        self.window.bind("<Left>", lambda e: self._prev_group())
        self.window.bind("<Right>", lambda e: self._next_group())
        
        # Ctrl+M: Perform merge
        self.window.bind("<Control-m>", lambda e: self._perform_merge())
        self.window.bind("<Control-M>", lambda e: self._perform_merge())
        
        # Ctrl+R: Refresh/Combined search
        self.window.bind("<Control-r>", lambda e: self._search_combined())
        self.window.bind("<Control-R>", lambda e: self._search_combined())
    
    def _build_ui(self):
        """Build the dialog UI."""
        # Main container
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(toolbar, text="Ricerca per Matricola", command=self._search_matricola).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Ricerca per Nominativo", command=self._search_nominativo).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Ricerca Combinata", command=self._search_combined).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT, padx=5)
        
        self.group_label = ttk.Label(toolbar, text="Gruppo: 0/0")
        self.group_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(toolbar, text="◀ Precedente", command=self._prev_group).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Successivo ▶", command=self._next_group).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar, text="  |  ").pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Merge Selezionati", command=self._perform_merge).pack(side=tk.LEFT, padx=2)
        
        # Containers for the single-page layout
        self.members_container = ttk.LabelFrame(main_frame, text="Dettagli Soci Duplicati", padding=10)
        self.members_container.pack(fill=tk.X, expand=False)
        
        self.selection_container = ttk.LabelFrame(main_frame, text="Selezione Campi da Copiare", padding=10)
        self.selection_container.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self._init_selection_canvas()
    
    def _init_selection_canvas(self):
        """Prepare scrollable area for field selectors."""
        if hasattr(self, "selection_canvas"):
            self.selection_canvas.destroy()
        if hasattr(self, "selection_scrollbar"):
            self.selection_scrollbar.destroy()
        self.selection_canvas = tk.Canvas(self.selection_container, highlightthickness=0)
        self.selection_scrollbar = ttk.Scrollbar(
            self.selection_container,
            orient="vertical",
            command=self.selection_canvas.yview
        )
        self.selection_canvas.configure(yscrollcommand=self.selection_scrollbar.set)
        self.selection_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.selection_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.selection_inner = ttk.Frame(self.selection_canvas)
        self.selection_inner.bind(
            "<Configure>",
            lambda e: self.selection_canvas.configure(scrollregion=self.selection_canvas.bbox("all"))
        )
        self.selection_canvas.create_window((0, 0), window=self.selection_inner, anchor="nw")
    
    def _clear_frame(self, frame):
        """Remove all children widgets from a frame."""
        for child in frame.winfo_children():
            child.destroy()
    
    def _find_duplicates(self):
        """Find duplicates and populate display."""
        from duplicates_manager import find_duplicates_combined
        self.duplicates_groups = find_duplicates_combined()
        
        if not self.duplicates_groups:
            messagebox.showinfo("Ricerca Duplicati", "Nessun duplicato trovato!")
            self.window.destroy()
            return
        
        self.current_group_index = 0
        self._show_group(0)
    
    def _search_matricola(self):
        """Search duplicates by matricola."""
        from duplicates_manager import find_duplicates_by_matricola
        self.duplicates_groups = find_duplicates_by_matricola()
        
        if not self.duplicates_groups:
            messagebox.showinfo("Ricerca per Matricola", "Nessun duplicato trovato per matricola!")
            return
        
        self.current_group_index = 0
        self._refresh_display()
    
    def _search_nominativo(self):
        """Search duplicates by nominativo."""
        from duplicates_manager import find_duplicates_by_nominativo
        self.duplicates_groups = find_duplicates_by_nominativo()
        
        if not self.duplicates_groups:
            messagebox.showinfo("Ricerca per Nominativo", "Nessun duplicato trovato per nominativo!")
            return
        
        self.current_group_index = 0
        self._refresh_display()
    
    def _search_combined(self):
        """Search duplicates combined."""
        from duplicates_manager import find_duplicates_combined
        self.duplicates_groups = find_duplicates_combined()
        
        if not self.duplicates_groups:
            messagebox.showinfo("Ricerca Combinata", "Nessun duplicato trovato!")
            return
        
        self.current_group_index = 0
        self._refresh_display()
    
    def _refresh_display(self):
        """Refresh the display for current group."""
        self._show_group(self.current_group_index)
    
    def _show_group(self, index):
        """Display a specific duplicate group."""
        if index < 0 or index >= len(self.duplicates_groups):
            return
        
        group = self.duplicates_groups[index]
        # Fetch full member records for accurate field values (some duplicate-finding
        # queries return only partial columns). Use full records for selection UI.
        from duplicates_manager import get_all_fields_for_member
        full_group = []
        for m in group:
            full = get_all_fields_for_member(m.get('id'))
            if full:
                full_group.append(full)
            else:
                full_group.append(m)

        self.current_group_members = full_group
        self.current_group_index = index
        self.group_label.config(text=f"Gruppo: {index + 1}/{len(self.duplicates_groups)}")
        
        # Choose as default MASTER the first member that has a non-empty 'matricola',
        # otherwise fallback to the first member.
        master_idx = 0
        for i, m in enumerate(self.current_group_members):
            mat = (m.get('matricola') or "").strip()
            if mat:
                master_idx = i
                break
        self.master_var.set(master_idx)

        # Render member summary using the original (possibly partial) data for compactness,
        # but use the full_group for the selectors so values are present. The radio button
        # for MASTER will reflect `self.master_var`.
        self._render_member_cards(group)
        self._render_field_selectors(self.current_group_members)
        self._update_all_field_previews()
    
    def _format_member_info(self, member, member_index, group):
        """Format member information for display."""
        text = f"Membro #{member_index + 1}\n"
        text += "=" * 70 + "\n\n"
        
        fields_to_show = [
            ('id', 'ID'),
            ('matricola', 'Matricola'),
            ('nominativo', 'Nominativo'),
            ('nome', 'Nome'),
            ('cognome', 'Cognome'),
            ('email', 'Email'),
            ('data_iscrizione', 'Data Iscrizione'),
            ('attivo', 'Attivo'),
        ]
        
        # Show differences with other members
        if len(group) > 1:
            from duplicates_manager import get_field_differences
            
            for other_idx, other_member in enumerate(group):
                if other_idx == member_index:
                    continue
                
                diffs = get_field_differences(member.get('id'), other_member.get('id'))
                if diffs:
                    text += f"\n⚠️  DIFFERENZE CON MEMBRO #{other_idx + 1}:\n"
                    text += "-" * 70 + "\n"
                    for field, (v1, v2) in sorted(diffs.items()):
                        text += f"  {field:20} | Questo: {str(v1)[:25]:25} | Altro: {str(v2)[:25]:25}\n"
        
        text += "\n" + "=" * 70 + "\n"
        text += "INFORMAZIONI COMPLETE:\n"
        text += "-" * 70 + "\n"
        
        # Get all fields for detailed view
        from duplicates_manager import get_all_fields_for_member
        all_fields = get_all_fields_for_member(member.get('id'))
        
        for key, value in sorted(all_fields.items()):
            if key not in ['id']:
                text += f"{key:20} | {str(value)}\n"
        
        return text

    def _render_member_cards(self, group):
        """Render compact cards with member information and master selection."""
        self._clear_frame(self.members_container)
        summary_frame = ttk.Frame(self.members_container)
        summary_frame.pack(fill=tk.X, expand=False)
        
        for i, member in enumerate(group):
            card = ttk.LabelFrame(summary_frame, text=f"Membro #{i+1}", padding=8)
            card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5, pady=5)
            
            info_lines = [
                f"ID: {member.get('id', '—')}",
                f"Matricola: {member.get('matricola', '—')}",
                f"Nominativo: {member.get('nominativo', '—')}",
                f"Nome: {member.get('nome', '—')} {member.get('cognome', '')}",
                f"Email: {member.get('email', '—')}",
            ]
            ttk.Radiobutton(
                card,
                text="Imposta come MASTER",
                variable=self.master_var,
                value=i,
                command=self._on_master_changed
            ).pack(anchor=tk.W, pady=(0, 5))
            
            for line in info_lines:
                ttk.Label(card, text=line, wraplength=200, justify=tk.LEFT).pack(anchor=tk.W)
    
    def _render_field_selectors(self, group):
        """Build the selector widgets used to choose source values per field."""
        self._init_selection_canvas()
        self.field_checkbox_vars = {}
        self.field_selection_labels = {}
        self.field_value_labels = {}
        
        if len(group) < 2:
            ttk.Label(self.selection_inner, text="Servono almeno due soci per il merge").pack(anchor=tk.W)
            return
        
        ttk.Label(
            self.selection_inner,
            text="Seleziona con le checkbox i campi da copiare scegliendo il socio sorgente (default: lascia il MASTER).",
            font=("Segoe UI", 10, "bold"),
            wraplength=900,
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(0, 10))
        
        if len(group) == 2:
            self._render_two_member_selector(group)
        else:
            self._render_multi_member_selector(group)
        
        ttk.Label(
            self.selection_inner,
            text="Suggerimento: imposta il MASTER sopra, poi scegli solo i campi realmente differenti.",
            font=("Segoe UI", 9, "italic")
        ).pack(anchor=tk.W, pady=(8, 0))
    
    def _render_two_member_selector(self, group):
        rows_container = ttk.Frame(self.selection_inner)
        rows_container.pack(fill=tk.BOTH, expand=True)
        # Configure columns: Campo | Valore A | Scelta | Valore B
        rows_container.grid_columnconfigure(0, weight=0, minsize=180)
        rows_container.grid_columnconfigure(1, weight=2, minsize=260)
        rows_container.grid_columnconfigure(2, weight=0, minsize=160)
        rows_container.grid_columnconfigure(3, weight=2, minsize=260)
        
        ttk.Label(rows_container, text="Campo", font=("Segoe UI", 9, "bold"), anchor=tk.W).grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(rows_container, text="Valore A", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(rows_container, text="Scelta", font=("Segoe UI", 9, "bold"), anchor=tk.CENTER).grid(row=0, column=2, padx=4, pady=2)
        ttk.Label(rows_container, text="Valore B", font=("Segoe UI", 9, "bold")).grid(row=0, column=3, sticky="w", padx=4, pady=2)
        
        for row_index, field in enumerate(self.merge_fields, start=1):
            ttk.Label(rows_container, text=field, anchor=tk.W).grid(row=row_index, column=0, sticky="w", padx=4, pady=2)
            
            value_labels = {}
            for member_idx, member in enumerate(group):
                value = member.get(field)
                text = self._format_field_value(value)
                col = 1 if member_idx == 0 else 3
                lbl = ttk.Label(
                    rows_container,
                    text=text,
                    anchor=tk.W,
                    wraplength=320,
                    justify=tk.LEFT
                )
                lbl.grid(row=row_index, column=col, sticky="we", padx=6, pady=2)
                value_labels[member_idx] = lbl
            self.field_value_labels[field] = value_labels
            
            selector = ttk.Frame(rows_container)
            selector.grid(row=row_index, column=2, padx=6, pady=2, sticky="nsew")

            checkbox_map = {}
            # Place A and B horizontally and center them inside the selector cell
            btn_frame = ttk.Frame(selector)
            btn_frame.pack(anchor=tk.CENTER)
            for idx, label in enumerate(("A", "B")):
                var = tk.BooleanVar(value=False)
                checkbox_map[idx] = var
                ttk.Checkbutton(
                    btn_frame,
                    text=label,
                    variable=var,
                    command=lambda f=field, i=idx, v=var: self._on_field_checkbox(f, i, v)
                ).pack(side=tk.LEFT, padx=8)

            self.field_checkbox_vars[field] = checkbox_map

            preview = ttk.Label(selector, text="(MASTER)", anchor=tk.CENTER, foreground="#555555")
            preview.pack(anchor=tk.CENTER, pady=(6, 0))
            self.field_selection_labels[field] = preview
    
    def _render_multi_member_selector(self, group):
        rows_container = ttk.Frame(self.selection_inner)
        rows_container.pack(fill=tk.BOTH, expand=True)
        preview_col = len(group) + 1

        # Configure columns (campo + each member + preview)
        rows_container.grid_columnconfigure(0, weight=0, minsize=180)
        for col_idx in range(1, preview_col):
            rows_container.grid_columnconfigure(col_idx, weight=1, minsize=160)
        rows_container.grid_columnconfigure(preview_col, weight=1, minsize=220)

        ttk.Label(rows_container, text="Campo", font=("Segoe UI", 9, "bold"), anchor=tk.W).grid(row=0, column=0, sticky="w", padx=6, pady=2)
        for idx, member in enumerate(group):
            ttk.Label(
                rows_container,
                text=f"Membro #{idx+1}\n(ID {member.get('id', '—')})",
                anchor=tk.CENTER,
                font=("Segoe UI", 9, "bold")
            ).grid(row=0, column=idx + 1, padx=6, pady=2, sticky="we")
        ttk.Label(rows_container, text="Anteprima", font=("Segoe UI", 9, "bold")).grid(row=0, column=preview_col, sticky="w", padx=6, pady=2)
        
        for row_index, field in enumerate(self.merge_fields, start=1):
            ttk.Label(rows_container, text=field, anchor=tk.W).grid(row=row_index, column=0, sticky="w", padx=4, pady=2)
            
            checkbox_map = {}
            value_label_map = {}
            for member_index, member in enumerate(group):
                var = tk.BooleanVar(value=False)
                checkbox_map[member_index] = var

                cell = ttk.Frame(rows_container)
                cell.grid(row=row_index, column=member_index + 1, padx=6, pady=2, sticky="nwe")

                # checkbox on top
                ttk.Checkbutton(
                    cell,
                    variable=var,
                    command=lambda f=field, i=member_index, v=var: self._on_field_checkbox(f, i, v)
                ).pack(anchor=tk.NW)

                # value below with generous wraplength
                value = member.get(field)
                display_val = self._format_field_value(value)
                val_label = ttk.Label(cell, text=display_val, anchor=tk.W, wraplength=180, justify=tk.LEFT)
                val_label.pack(anchor=tk.W, pady=(4, 0), fill=tk.X)
                value_label_map[member_index] = val_label
            self.field_checkbox_vars[field] = checkbox_map
            self.field_value_labels[field] = value_label_map

            preview = ttk.Label(rows_container, text="(MASTER)", anchor=tk.W)
            preview.grid(row=row_index, column=preview_col, sticky="we", padx=6, pady=2)
            self.field_selection_labels[field] = preview
    
    def _format_field_value(self, value):
        """Format value preview for display near each checkbox."""
        if value in (None, ""):
            return "—"
        text = str(value)
        return text if len(text) <= 30 else text[:27] + "…"
    
    def _on_field_checkbox(self, field, index, var):
        """Ensure only one checkbox per field stays active and refresh preview."""
        if var.get():
            for idx, other_var in self.field_checkbox_vars[field].items():
                if idx != index and other_var.get():
                    other_var.set(False)
        self._update_field_preview(field)
    
    def _on_master_changed(self):
        """When master selection changes, update previews."""
        self._update_all_field_previews()
    
    def _update_field_preview(self, field):
        """Update the textual preview for a single field selection."""
        if field not in self.field_selection_labels:
            return
        selected_idx = None
        for idx, var in self.field_checkbox_vars.get(field, {}).items():
            if var.get():
                selected_idx = idx
                break
        if selected_idx is None:
            master_idx = self.master_var.get()
            value = self.current_group_members[master_idx].get(field)
            display = f"(MASTER) {value}" if value not in (None, "") else "(MASTER) —"
        else:
            member = self.current_group_members[selected_idx]
            value = member.get(field)
            display = f"Membro #{selected_idx + 1} → {value}" if value not in (None, "") else f"Membro #{selected_idx + 1} → —"
        self.field_selection_labels[field].config(text=display)
    
    def _update_all_field_previews(self):
        """Refresh previews for every field."""
        for field in self.merge_fields:
            self._update_field_preview(field)
    
    def _prev_group(self):
        """Show previous group."""
        if self.current_group_index > 0:
            self._show_group(self.current_group_index - 1)
    
    def _next_group(self):
        """Show next group."""
        if self.current_group_index < len(self.duplicates_groups) - 1:
            self._show_group(self.current_group_index + 1)
    
    def _perform_merge(self):
        """Perform the merge operation."""
        if not self.duplicates_groups:
            messagebox.showwarning("Merge", "Nessun gruppo selezionato")
            return
        
        group = self.duplicates_groups[self.current_group_index]
        self.current_group_members = group
        
        master_index = self.master_var.get()
        if master_index < 0 or master_index >= len(group):
            messagebox.showwarning("Merge", "Selezionare un membro come MASTER")
            return
        
        master_member = group[master_index]
        master_id = master_member['id']
        
        field_values, report_entries = self._collect_field_selections(group)
        duplicates = [member for idx, member in enumerate(group) if idx != master_index]
        
        if not duplicates:
            messagebox.showwarning("Merge", "Nessun duplicato da unire con il master selezionato.")
            return
        
        report_text = self._build_merge_report(master_member, duplicates, report_entries)
        self._show_report_dialog(master_index, duplicates, field_values, report_text)
    
    def _collect_field_selections(self, group):
        """Collect selected fields and build report metadata."""
        field_values = {}
        report_entries = []
        
        for field in self.merge_fields:
            checkbox_map = self.field_checkbox_vars.get(field, {})
            selected_idx = None
            for idx, var in checkbox_map.items():
                if var.get():
                    selected_idx = idx
                    break
            if selected_idx is None:
                continue
            value = group[selected_idx].get(field)
            if value in (None, ""):
                continue
            field_values[field] = value
            report_entries.append({
                "field": field,
                "source_index": selected_idx,
                "value": value
            })
        return field_values, report_entries
    
    def _build_merge_report(self, master_member, duplicates, report_entries):
        """Create textual summary before applying merge."""
        lines = []
        lines.append("=== REPORT MERGE DUPLICATI ===")
        lines.append(f"MASTER: ID {master_member.get('id')} - {master_member.get('nome', '')} {master_member.get('cognome', '')}")
        lines.append("")
        lines.append("Duplicati che verranno uniti/eliminati:")
        for member in duplicates:
            lines.append(f"  • ID {member.get('id')} - {member.get('nome', '')} {member.get('cognome', '')} (Matricola {member.get('matricola', '—')})")
        lines.append("")
        if report_entries:
            lines.append("Campi copiati sul MASTER:")
            for entry in report_entries:
                idx = entry["source_index"]
                value = entry["value"]
                lines.append(f"  - {entry['field']}: da Membro #{idx + 1} → {value}")
        else:
            lines.append("Nessun campo selezionato: verranno solo eliminati i duplicati mantenendo i valori del MASTER.")
        lines.append("")
        lines.append("Confermi l'operazione?")
        return "\n".join(lines)
    
    def _show_report_dialog(self, master_index, duplicates, field_values, report_text):
        """Display confirmation dialog with textual report."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Conferma Merge Duplicati")
        dialog.geometry("700x500")
        dialog.transient(self.window)
        dialog.grab_set()
        
        text = tk.Text(dialog, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert("1.0", report_text)
        text.config(state=tk.DISABLED)
        
        buttons = ttk.Frame(dialog)
        buttons.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(buttons, text="Annulla", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(
            buttons,
            text="Conferma Merge",
            command=lambda: self._execute_merge(dialog, master_index, duplicates, field_values)
        ).pack(side=tk.RIGHT, padx=5)
    
    def _execute_merge(self, dialog, master_index, duplicates, field_values):
        """Execute merge after confirmation."""
        dialog.destroy()
        from duplicates_manager import merge_duplicates
        
        master_id = self.current_group_members[master_index]['id']
        merged_count = 0
        
        for idx, member in enumerate(self.current_group_members):
            if idx == master_index:
                continue
            if member not in duplicates:
                continue
            if merge_duplicates(master_id, member['id'], field_values):
                merged_count += 1
        
        if merged_count > 0:
            messagebox.showinfo(
                "Merge Completato",
                f"✓ {merged_count} duplicati uniti nel socio con ID {master_id}"
            )
            self._search_combined()
        else:
            messagebox.showerror("Merge Fallito", "Nessun merge effettuato")
