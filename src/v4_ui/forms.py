# -*- coding: utf-8 -*-
"""
Form components for Libro Soci
Handles member data entry and editing
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from preferences import get_role_options

logger = logging.getLogger("librosoci")

SECTION_TITLE_FONT = ("Segoe UI", 11, "bold")
LABEL_FONT = ("Segoe UI", 9)
INPUT_FONT = ("Segoe UI", 9)
PASTEL_SECTION_COLORS = {
    "base": "#ebeff6",
    "identificazione": "#ffe1d7",
    "contatti": "#d4ebff",
    "anagrafica": "#d8f4dc",
    "residenza": "#ffe9c0",
    "stato": "#dcdfff",
    "note": "#f9d7ff",
    "default": "#e9edf5",
}
TAG_BACKGROUND = "#c8d5ff"
TAG_BORDER = "#7f90d9"
TAG_TEXT = "#182040"


class RoleTagEditor(tk.Frame):
    """Simple tag-style editor for selecting multiple roles."""

    def __init__(
        self,
        parent,
        *,
        options: list[str] | None = None,
        background: str | None = None,
        tag_background: str | None = None,
        tag_border: str | None = None,
        tag_text: str | None = None,
        button_style: str | None = None,
    ):
        parent_bg = background or self._detect_background(parent)
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0)
        self.available_options = options or []
        self.roles: list[str] = []
        self._bg = parent_bg
        self._tag_bg = tag_background or TAG_BACKGROUND
        self._tag_border = tag_border or TAG_BORDER
        self._tag_text = tag_text or TAG_TEXT
        self._button_style = button_style
        self.tags_frame = tk.Frame(self, bg=self._bg, highlightthickness=0, bd=0)
        self.tags_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        button_kwargs: dict[str, str] = {}
        if self._button_style:
            button_kwargs["style"] = self._button_style
        self.add_button = ttk.Button(self, text="+", width=3, command=self._open_selector, **button_kwargs)
        self.add_button.pack(side=tk.RIGHT, padx=(6, 0))
        self._placeholder = tk.Label(self.tags_frame, text="Nessun ruolo", font=LABEL_FONT, bg=self._bg, fg=self._tag_text)
        self._placeholder.pack(anchor="w")

    @staticmethod
    def _detect_background(widget) -> str:
        try:
            return widget.cget("background")
        except Exception:
            return PASTEL_SECTION_COLORS["base"]

    def reload_options(self, options: list[str]):
        self.available_options = options or []

    def set_roles(self, roles: list[str] | None):
        self.roles = [] if roles is None else [r for r in roles if r]
        self._render_tags()

    def clear(self):
        self.roles = []
        self._render_tags()

    def get_roles(self) -> list[str]:
        return list(self.roles)

    def _render_tags(self):
        for child in self.tags_frame.winfo_children():
            child.destroy()
        if not self.roles:
            self._placeholder = tk.Label(self.tags_frame, text="Nessun ruolo", font=LABEL_FONT, bg=self._bg, fg=self._tag_text)
            self._placeholder.pack(anchor="w")
            return
        for role in self.roles:
            tag = tk.Frame(
                self.tags_frame,
                bg=self._tag_bg,
                highlightbackground=self._tag_border,
                highlightthickness=1,
                bd=0,
            )
            tag.pack(side=tk.LEFT, padx=2, pady=1)
            tk.Label(tag, text=role, font=LABEL_FONT, bg=self._tag_bg, fg=self._tag_text).pack(side=tk.LEFT, padx=(6, 2))
            tk.Button(
                tag,
                text="x",
                command=lambda r=role: self._remove_role(r),
                bg=self._tag_bg,
                fg=self._tag_text,
                relief=tk.FLAT,
                bd=0,
                padx=4,
                pady=0,
                activebackground=self._tag_bg,
                highlightthickness=0,
                font=LABEL_FONT,
            ).pack(side=tk.LEFT, padx=(0, 4))

    def _remove_role(self, role: str):
        self.roles = [r for r in self.roles if r != role]
        self._render_tags()

    def _open_selector(self):
        dialog = tk.Toplevel(self)
        dialog.title("Seleziona ruoli")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=False, height=10, width=30)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for idx, option in enumerate(self.available_options):
            listbox.insert(tk.END, option)
            if option in self.roles:
                listbox.selection_set(idx)

        def _apply_selection():
            selected = [self.available_options[i] for i in listbox.curselection()]
            self.roles = selected
            self._render_tags()
            dialog.destroy()

        ttk.Button(dialog, text="Applica", command=_apply_selection).pack(side=tk.RIGHT, padx=10, pady=(0, 10))
        ttk.Button(dialog, text="Annulla", command=dialog.destroy).pack(side=tk.RIGHT, pady=(0, 10))

class MemberForm(ttk.Frame):
    """Fixed member data form with logical grid layout - NO SCROLLING"""

    def __init__(self, parent, *, cfg: dict | None = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.widgets = {}
        self.current_id = None  # Track the current socio ID for validation
        self.note_action_frame = None  # Holds external action buttons (e.g., Salva/Annulla)
        self.role_editor: RoleTagEditor | None = None
        self._cfg = cfg or {}
        self._section_palette = dict(PASTEL_SECTION_COLORS)
        self._section_styles: dict[str, str] = {}
        self._section_style = "Section.TLabelframe"
        self._base_frame_style = "Pastel.TFrame"
        self._tag_button_style = "RoleAdd.TButton"
        self._init_styles()
        self._build_form()

    def _init_styles(self):
        style = ttk.Style(self)
        style.configure(self._base_frame_style, background=self._section_palette["base"])
        self.configure(style=self._base_frame_style)
        self._section_styles["default"] = self._create_section_style(style, "DefaultSection", self._section_palette["default"])
        self._section_styles["identificazione"] = self._create_section_style(style, "IdentSection", self._section_palette["identificazione"])
        self._section_styles["contatti"] = self._create_section_style(style, "ContactSection", self._section_palette["contatti"])
        self._section_styles["anagrafica"] = self._create_section_style(style, "AnagraficaSection", self._section_palette["anagrafica"])
        self._section_styles["residenza"] = self._create_section_style(style, "ResidenzaSection", self._section_palette["residenza"])
        self._section_styles["stato"] = self._create_section_style(style, "StatoSection", self._section_palette["stato"])
        self._section_styles["note"] = self._create_section_style(style, "NoteSection", self._section_palette["note"])
        self._section_style = self._section_styles["default"]
        style.configure(self._tag_button_style, font=LABEL_FONT, padding=(4, 0))

    def _create_section_style(self, style: ttk.Style, key: str, background: str) -> str:
        section_style = f"{key}.TLabelframe"
        label_style = f"{section_style}.Label"
        style.configure(
            section_style,
            font=SECTION_TITLE_FONT,
            background=background,
            borderwidth=1,
            relief="ridge",
            labelmargins=(8, 4, 8, 6),
        )
        style.configure(label_style, font=SECTION_TITLE_FONT, background=background)
        style.map(section_style, background=[("active", background)])
        return section_style

    def _apply_section_metadata(self, widget, palette_key: str):
        bg_color = self._section_palette.get(palette_key, self._section_palette["default"])
        setattr(widget, "_bg_color", bg_color)

    def _label_background(self, widget) -> str:
        return getattr(widget, "_bg_color", self._section_palette["default"])

    def _create_label(self, parent, text: str):
        return tk.Label(parent, text=text, font=LABEL_FONT, bg=self._label_background(parent), fg="#1c2a46")

    def _create_checkbutton(self, parent, text: str, variable: tk.BooleanVar):
        bg_color = self._label_background(parent)
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            font=LABEL_FONT,
            bg=bg_color,
            fg="#1c2a46",
            activebackground=bg_color,
            selectcolor=bg_color,
            highlightthickness=0,
            bd=0,
            anchor="w",
        )
    
    def _build_form(self):
        """Build the member form in a compact fixed grid layout"""
        # Main container with reduced padding
        main_frame = ttk.Frame(self, style=self._base_frame_style)
        main_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)
        self._apply_section_metadata(main_frame, "base")
        
        # Row counter for grid
        row = 0
        
        # === SECTION 1: IDENTIFICAZIONE (full width, reduced padding) ===
        section1 = ttk.LabelFrame(main_frame, text="Identificazione", padding=5, style=self._section_styles["identificazione"])
        self._apply_section_metadata(section1, "identificazione")
        section1.grid(row=row, column=0, columnspan=2, sticky='ew', padx=3, pady=2)
        
        self._add_field(section1, 0, 0, "matricola", "Matricola:", width=12)
        self._add_field(section1, 1, 0, "nominativo", "Nominativo:", width=10)
        self._add_field(section1, 1, 2, "nominativo2", "Nominativo 2:", width=10)
        self._add_field(section1, 0, 2, "familiare", "Familiare:", width=12)

        self._create_label(section1, "Tipo socio:").grid(row=0, column=4, sticky='w', padx=3, pady=1)
        socio_var = tk.StringVar()
        socio_combo = ttk.Combobox(
            section1,
            textvariable=socio_var,
            values=("", "HAM", "RCL", "THR"),
            state="readonly",
            width=8
        )
        socio_combo.configure(font=INPUT_FONT)
        socio_combo.grid(row=0, column=5, sticky='w', padx=3, pady=1)
        self.widgets['socio'] = socio_var
        section1.columnconfigure(5, weight=1)

        # === SECTION 1B: CONTATTI (aligned to the right of Identificazione) ===
        section_contatti = ttk.LabelFrame(main_frame, text="Contatti", padding=5, style=self._section_styles["contatti"])
        self._apply_section_metadata(section_contatti, "contatti")
        section_contatti.grid(row=row, column=2, sticky='ew', padx=3, pady=2)
        self._add_field(section_contatti, 0, 0, "email", "Email:", width=20)
        self._add_field(section_contatti, 1, 0, "telefono", "Telefono:", width=12)
        row += 1
        
        # === SECTION 2: DATI ANAGRAFICI (compact, 2 rows) ===
        section2 = ttk.LabelFrame(main_frame, text="Dati Anagrafici", padding=5, style=self._section_styles["anagrafica"])
        self._apply_section_metadata(section2, "anagrafica")
        section2.grid(row=row, column=0, columnspan=2, sticky='ew', padx=3, pady=2)
        
        # Row 1: Nome, Cognome, Cod.Fiscale
        self._add_field(section2, 0, 0, "nome", "Nome:", width=18)
        self._add_field(section2, 0, 2, "cognome", "Cognome:", width=18)
        self._add_field(section2, 0, 4, "codicefiscale", "Cod. Fiscale:", width=16)
        
        # Row 2: Data nascita, Luogo nascita
        self._add_field(section2, 1, 0, "data_nascita", "Data nascita:", width=10)
        self._add_field(section2, 1, 2, "luogo_nascita", "Luogo nascita:", width=25, columnspan=3)
        
        # === SECTION 3: RESIDENZA (compact, 2 rows) ===
        section3 = ttk.LabelFrame(main_frame, text="Residenza", padding=5, style=self._section_styles["residenza"])
        self._apply_section_metadata(section3, "residenza")
        section3.grid(row=row, column=2, sticky='ew', padx=3, pady=2)
        row += 1
        
        # Row 1: Indirizzo (full width)
        self._add_field(section3, 0, 0, "indirizzo", "Indirizzo:", width=40, columnspan=5)
        
        # Row 2: CAP, Città, Provincia (all on one line)
        self._add_field(section3, 1, 0, "cap", "CAP:", width=6)
        self._add_field(section3, 1, 2, "citta", "Città:", width=20)
        self._add_field(section3, 1, 4, "provincia", "Prov:", width=4)
        
        # === SECTION 5: STATO (compact, reduced padding) ===
        section5 = ttk.LabelFrame(main_frame, text="Stato", padding=5, style=self._section_styles["stato"])
        self._apply_section_metadata(section5, "stato")
        section5.grid(row=row, column=0, columnspan=3, sticky='ew', padx=3, pady=2)
        row += 1
        
        # Single row with all stato fields (reduced spacing)
        self.widgets['attivo'] = tk.BooleanVar()
        self._create_checkbutton(section5, "Attivo", self.widgets['attivo']).grid(row=0, column=0, sticky='w', padx=5, pady=2)
        
        self.widgets['voto'] = tk.BooleanVar()
        self._create_checkbutton(section5, "Voto", self.widgets['voto']).grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        self.widgets['privacy_signed'] = tk.BooleanVar()
        self._create_checkbutton(section5, "Privacy", self.widgets['privacy_signed']).grid(row=0, column=2, sticky='w', padx=5, pady=2)
        
        # Q fields inline with status controls (width=2 chars)
        q_fields = [("q0", "Q0:"), ("q1", "Q1:"), ("q2", "Q2:" )]
        base_col = 3
        for idx, (field, label) in enumerate(q_fields):
            col = base_col + idx * 2
            self._create_label(section5, label).grid(row=0, column=col, sticky='w', padx=4, pady=2)
            entry = ttk.Entry(section5, width=4, justify='left')
            entry.configure(font=INPUT_FONT)
            entry.grid(row=0, column=col + 1, sticky='w', padx=2, pady=2)
            self.widgets[field] = entry
            section5.columnconfigure(col + 1, weight=0)

        # Row 0: Stato combobox allineato con i flag di stato
        self._create_label(section5, "Stato:").grid(row=0, column=11, sticky='w', padx=6, pady=2)
        self.role_editor = RoleTagEditor(
            section5,
            options=list(get_role_options(self._cfg)),
            background=self._section_palette["stato"],
            tag_background=TAG_BACKGROUND,
            tag_border=TAG_BORDER,
            tag_text=TAG_TEXT,
            button_style=self._tag_button_style,
        )
        self.role_editor.grid(row=0, column=12, columnspan=3, sticky='ew', padx=5, pady=2)
        section5.columnconfigure(12, weight=1)

        # Balance column expansion for cleaner spacing
        for col in range(0, 15):
            section5.columnconfigure(col, weight=0)
        
        # === SECTION 6: NOTE (compact, reduced height) ===
        section6 = ttk.LabelFrame(main_frame, text="Note", padding=5, style=self._section_styles["note"])
        self._apply_section_metadata(section6, "note")
        section6.grid(row=row, column=0, columnspan=3, sticky='ew', padx=3, pady=2)
        row += 1
        
        self._create_label(section6, "Note:").grid(row=0, column=0, sticky='nw', padx=3, pady=2)
        note_text = tk.Text(section6, height=2, width=80, wrap=tk.WORD, font=INPUT_FONT)
        note_text.grid(row=0, column=1, columnspan=4, sticky='ew', padx=3, pady=2)
        self.widgets['note'] = note_text
        section6.columnconfigure(1, weight=1)

        # Reserve a slim column for action buttons (e.g., Salva/Annulla)
        action_frame = tk.Frame(section6, bg=self._section_palette["note"], highlightthickness=0, bd=0)
        action_frame.grid(row=0, column=5, sticky='ne', padx=(6, 3), pady=2)
        self.note_action_frame = action_frame
        
        # Configure column weights for responsiveness
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
    
    def _add_field(self, parent, row, col, field_name, label_text, width=20, columnspan=1):
        """Add a labeled entry field to the grid with compact spacing"""
        self._create_label(parent, label_text).grid(row=row, column=col, sticky='w', padx=3, pady=1)
        entry = ttk.Entry(parent, width=width)
        entry.configure(font=INPUT_FONT)
        entry.grid(row=row, column=col+1, columnspan=columnspan, sticky='ew', padx=3, pady=1)
        self.widgets[field_name] = entry
        
        # Configure column weights
        parent.columnconfigure(col+1, weight=1)
    
    def _build_section(self, parent, title, fields, multiline=False):
        """Build a form section with two columns"""
        section_frame = ttk.LabelFrame(parent, text=title, padding=10, style=self._section_style)
        self._apply_section_metadata(section_frame, "default")
        section_frame.pack(fill=tk.X, padx=5, pady=5)

        # Due colonne: label/input a sinistra e a destra, alternando
        col_count = 2
        for i, (field_name, label_text) in enumerate(fields):
            col = i % col_count
            row = i // col_count
            label = self._create_label(section_frame, label_text)
            label.grid(row=row, column=col*2, sticky="e", padx=5, pady=3)
            if multiline:
                widget = tk.Text(section_frame, height=5, width=30, font=INPUT_FONT)
                widget.grid(row=row, column=col*2+1, sticky="ew", padx=5, pady=3)
            else:
                widget = ttk.Entry(section_frame, width=30)
                widget.configure(font=INPUT_FONT)
                widget.grid(row=row, column=col*2+1, sticky="ew", padx=5, pady=3)
            self.widgets[field_name] = widget
            section_frame.columnconfigure(col*2+1, weight=1)
    
    def get_values(self) -> dict:
        """Get all form values"""
        values = {}
        for field_name, widget in self.widgets.items():
            if isinstance(widget, tk.Text):
                values[field_name] = widget.get("1.0", tk.END).strip()
            elif isinstance(widget, tk.BooleanVar):
                # Checkbox - convert to 1/0
                values[field_name] = '1' if widget.get() else '0'
            elif isinstance(widget, tk.StringVar):
                # Combobox or other StringVar widget
                val = widget.get().strip()
                values[field_name] = val if val else None
            elif isinstance(widget, ttk.Entry):
                val = widget.get().strip()
                values[field_name] = val if val else None
        if self.role_editor is not None:
            roles = self.role_editor.get_roles()
            values['roles'] = roles
            values['cd_ruolo'] = roles[0] if roles else None
        return values

    def reload_role_options(self, cfg: dict | None = None):
        """Reload role options from preferences and keep the current selection."""
        if cfg is not None:
            self._cfg = cfg
        if not isinstance(self.role_editor, RoleTagEditor):
            return
        current = self.role_editor.get_roles()
        self.role_editor.reload_options(list(get_role_options(self._cfg)))
        self.role_editor.set_roles(current)

    def get_note_action_frame(self):
        """Expose the action frame placed next to the Note field."""
        return self.note_action_frame
    
    def set_values(self, data: dict):
        """Set all form values"""
        # Store the socio ID for validation purposes
        if "id" in data:
            self.current_id = data["id"]
        
        for field_name, value in data.items():
            if field_name in self.widgets:
                widget = self.widgets[field_name]
                if isinstance(widget, tk.Text):
                    widget.delete("1.0", tk.END)
                    widget.insert("1.0", str(value or ""))
                elif isinstance(widget, tk.BooleanVar):
                    # Checkbox - set boolean value
                    if value in (1, '1', True) or (isinstance(value, str) and value.lower() in ("1", "true", "si", "sì", "yes")):
                        widget.set(True)
                    else:
                        widget.set(False)
                elif isinstance(widget, tk.StringVar):
                    # Combobox or other StringVar widget
                    widget.set(str(value or ""))
                elif isinstance(widget, ttk.Entry):
                    widget.delete(0, tk.END)
                    widget.insert(0, str(value or ""))
        if isinstance(self.role_editor, RoleTagEditor):
            assigned_roles = data.get('roles')
            primary_role = data.get('cd_ruolo')
            if isinstance(assigned_roles, (list, tuple)):
                cleaned = [str(role) for role in assigned_roles if role]
                self.role_editor.set_roles(cleaned)
            elif primary_role:
                self.role_editor.set_roles([str(primary_role)])
            else:
                self.role_editor.clear()
    
    def clear(self):
        """Clear all form fields"""
        self.current_id = None  # Reset the current ID
        for field_name, widget in self.widgets.items():
            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
            elif isinstance(widget, tk.BooleanVar):
                widget.set(False)
            elif isinstance(widget, tk.StringVar):
                widget.set("")
            elif isinstance(widget, ttk.Entry):
                widget.delete(0, tk.END)
            elif isinstance(widget, tk.BooleanVar):
                widget.set(False)
            elif isinstance(widget, ttk.Entry):
                widget.delete(0, tk.END)
        if isinstance(self.role_editor, RoleTagEditor):
            self.role_editor.clear()
    
    def validate(self) -> tuple[bool, str]:
        """Validate form data"""
        values = self.get_values()
        
        # Basic validations
        nominativo = (values.get("nominativo") or "").strip()
        socio_type = (values.get("socio") or "").strip().upper()
        if not nominativo:
            if socio_type == "RCL":
                # RCL records can omit nominativo; store a dash for clarity
                entry = self.widgets.get("nominativo")
                if isinstance(entry, ttk.Entry):
                    entry.delete(0, tk.END)
                    entry.insert(0, "-")
                values["nominativo"] = "-"
            else:
                return False, "Il nominativo è obbligatorio"
        
        # Email validation if provided
        email = values.get("email") or ""
        if isinstance(email, str):
            email = email.strip()
        if email and "@" not in email:
            return False, "Email non valida"
        
        # Matricola validation if provided
        matricola = values.get("matricola") or ""
        if isinstance(matricola, str):
            matricola = matricola.strip()
        if matricola:
            from database import fetch_one
            # Check if matricola already exists (excluding current record if editing)
            # Use self.current_id which is set when loading a member
            sql = "SELECT id, deleted_at FROM soci WHERE matricola = ? AND id != ?"
            existing = fetch_one(sql, (matricola, self.current_id or -1))
            if existing:
                if existing.get("deleted_at"):
                    return False, (
                        f"Matricola '{matricola}' già assegnata al socio #{existing['id']} nel cestino. "
                        "Ripristinare il socio o utilizzare una matricola diversa."
                    )
                return False, f"Matricola '{matricola}' già utilizzata"
        
        # Date validation if provided
        from utils import ddmmyyyy_to_iso
        for field in ["data_nascita"]:
            date_val = values.get(field) or ""
            if isinstance(date_val, str):
                date_val = date_val.strip()
            if date_val:
                try:
                    ddmmyyyy_to_iso(date_val)
                except ValueError as e:
                    return False, str(e)
        
                socio_val = values.get("socio")
                if socio_val and socio_val not in {"HAM", "RCL", "THR"}:
                    return False, "Tipo socio non valido (HAM, RCL, THR)"
        
        return True, "OK"


class QuotePanel(tk.Frame):
    """Panel for quota management"""
    
    def __init__(self, parent, causali_codes=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.causali_codes = causali_codes or []
        self.configure(bg=PASTEL_SECTION_COLORS["base"])
        self._build_ui()
    
    def _build_ui(self):
        """Build quota selection panel"""
        bg = PASTEL_SECTION_COLORS["base"]
        label = tk.Label(self, text="Quota Codes", font=SECTION_TITLE_FONT, bg=bg, fg="#1c2a46")
        label.pack(anchor="w", padx=5, pady=5)
        
        frame = tk.Frame(self, bg=bg)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.q_vars = {}
        for q_name in ["q0", "q1", "q2"]:
            tk.Label(frame, text=f"{q_name.upper()}:", font=LABEL_FONT, bg=bg, fg="#1c2a46").grid(
                row=int(q_name[-1]), column=0, sticky="e", padx=5, pady=2
            )
            var = tk.StringVar()
            combo = ttk.Combobox(
                frame, textvariable=var, values=self.causali_codes,
                state="readonly", width=10
            )
            combo.configure(font=INPUT_FONT)
            combo.grid(row=int(q_name[-1]), column=1, sticky="w", padx=5)
            self.q_vars[q_name] = var
    
    def get_values(self) -> dict:
        """Get quota values"""
        return {k: v.get() or None for k, v in self.q_vars.items()}
    
    def set_values(self, data: dict):
        """Set quota values"""
        for field, var in self.q_vars.items():
            if field in data and data[field]:
                var.set(data[field])


class CDRuoloPanel(tk.Frame):
    """Panel for CD role selection"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=PASTEL_SECTION_COLORS["base"])
        self.cd_ruoli = [
            "Presidente",
            "Vice Presidente",
            "Segretario",
            "Tesoriere",
            "Sindaco",
            "Consigliere",
            "(nessuno)"
        ]
        self._build_ui()
    
    def _build_ui(self):
        """Build CD role selection"""
        bg = PASTEL_SECTION_COLORS["base"]
        tk.Label(self, text="Stato", font=SECTION_TITLE_FONT, bg=bg, fg="#1c2a46").pack(anchor="w", padx=5, pady=5)
        
        self.var = tk.StringVar(value="(nessuno)")
        combo = ttk.Combobox(
            self, textvariable=self.var, values=self.cd_ruoli,
            state="readonly", width=30
        )
        combo.configure(font=INPUT_FONT)
        combo.pack(fill=tk.X, padx=5, pady=5)
    
    def get_value(self) -> str | None:
        """Get selected role"""
        val = self.var.get()
        return val if val != "(nessuno)" else None
    
    def set_value(self, value: str):
        """Set selected role"""
        if value in self.cd_ruoli:
            self.var.set(value)
        else:
            self.var.set("(nessuno)")
