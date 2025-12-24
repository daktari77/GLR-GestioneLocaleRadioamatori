# UI Map – GestioneSoci (Tkinter)

Generato: 2025-12-24

## 1) Shell UI (finestra principale)

- **Classe principale**: `App`
- **File**: `src/v4_ui/main_window.py`
- **Responsabilità**:
  - Costruzione UI (menu, tab principali, status bar)
  - Routing comandi (metodi `_show_*`, `_open_*`, `_goto_*`)
  - Refresh selettivi su cambio tab (`<<NotebookTabChanged>>`)
  - Dialog/flow “first run” e gestione warning startup (messagebox)

### Menu (entrypoint principali)

**File**
- Backup DB (Ctrl+B) → `_manual_backup()` → `backup_on_demand(...)`
- Export (Ctrl+E) → `_show_export_dialog()` → `UnifiedExportWizard`
- Import CSV → `_show_import_wizard()` → `UnifiedImportWizard`

**Soci**
- Nuovo/Modifica/Elimina
- Ricerca duplicati (Ctrl+M) → `_show_duplicates_dialog()` → `DuplicatesDialog`
- Modifica campi multipli → `_show_batch_edit_dialog()` → `BatchFieldEditDialog`
- Aggiorna stato soci → `_show_update_status_wizard()` → `UpdateStatusWizard`
- Cestino → `_show_trash()` (Toplevel interno)
- Documentale (Ctrl+D) → `_open_documentale()` → `DocumentsDialog`

**Consiglio Direttivo**
- Nuova riunione → `_new_cd_meeting()` → `MeetingDialog`
- Gestisci riunioni → `_open_cd_meetings_list()` → `MeetingsListDialog`
- Visualizza delibere / verbali → `_goto_delibere_tab()` / `_goto_verbali_tab()`

**Gestione**
- Email wizard → `_open_email_wizard()` → `show_email_wizard()`
- Template documenti → `_show_templates_dialog()` → `TemplatesDialog`
- Magazzino / Assicurazioni / Ponti → `_goto_*_tab()`
- Legenda codici quote → `_show_quota_legend()` (Toplevel interno)

**Visualizza**
- Calendario eventi → `_goto_calendar_tab()`
- Statistiche → `_goto_statistics_tab()`
- Log eventi → `_show_event_log()` (Toplevel interno + `EventLogPanel`)

**Configurazione**
- Preferenze → `_show_preferences_dialog()` → `PreferencesDialog`
- Configurazione sezione → `_show_section_config_dialog()` (Toplevel interno + `SectionInfoPanel`)
- Riallinea percorsi documenti → `_relink_document_paths()`

**Aiuto**
- Guida rapida → `_open_help()` apre `HELP.md`
- Scorciatoie → `_show_shortcuts_help()` (Toplevel interno)
- Info → `_show_about()` (messagebox)

## 2) Tab principali (Notebook)

Le tab sono create in `_build_ui()` (ordine e gruppi).

### Gruppo A – Gestione associazione

1. **Soci**
   - File: `src/v4_ui/main_window.py`
   - Widget principali:
     - Treeview elenco soci (`self.tv_soci`)
     - Form scheda socio: `MemberForm` (`src/v4_ui/forms.py`)
     - Preview documenti (Treeview compatta)
   - Azioni tipiche:
     - CRUD socio + soft delete → DB tabella `soci`
     - Apertura documentale socio → `DocumentsDialog`
     - Batch edit / merge duplicati / update status

2. **Documenti**
   - File: `src/v4_ui/main_window.py`
   - Sottotab (Notebook interno):
     - **Documenti sezione** → `SectionDocumentPanel` (`src/v4_ui/panels.py`)
     - **Documenti soci** → `DocumentPanel` (`src/v4_ui/panels.py`, `show_all_documents=True`)

### Gruppo B – Patrimonio e risorse

3. **Magazzino**
   - Panel: `MagazzinoPanel` (`src/v4_ui/magazzino_panel.py`)

4. **Assicurazioni**
   - Panel: `AssicurazioniPanel` (`src/v4_ui/assicurazioni_panel.py`)

5. **Ponti**
   - Panel: `PontiPanel` (`src/v4_ui/ponti_panel.py`)

### Gruppo C – Amministrazione

6. **⚖️ Consiglio Direttivo** (Notebook con sottotab)
   - File: `src/v4_ui/main_window.py`
   - Sub-tab:
     - **Riunioni**: tab “informativo” con pulsanti verso `MeetingDialog` / `MeetingsListDialog`
     - **Delibere**: lista + CRUD → `cd_delibere_dialog.DeliberaDialog`
     - **Verbali**: lista + CRUD → `cd_verbali_dialog.VerbaleDialog`

7. **Calendario**
   - File: `src/v4_ui/main_window.py`
   - Wizard evento: `CalendarWizard` (`src/v4_ui/calendar_wizard.py`)
   - Export: `.ics` (tutto o selezionato)

### Gruppo D – Configurazione

8. **Sezione**
   - Panel: `SectionInfoPanel` (`src/v4_ui/panels.py`, `editable=False`)
   - Modifica config: dialog “Configurazione Sezione” (Toplevel interno, stesso panel in modalità edit)

9. **Statistiche**
   - Panel: `StatsPanel` (`src/v4_ui/stats_panel.py`)

## 3) Dialog/Wizard (Toplevel) principali

> Nota: alcune UI non ereditano `tk.Toplevel` come classe, ma creano `tk.Toplevel(...)` dentro un wrapper (pattern `self.win = tk.Toplevel(parent)` / `self.window = tk.Toplevel(parent)`).

- **Documentale socio**: `DocumentsDialog` (`src/v4_ui/documents_dialog.py`)
  - Entry: tab Soci → pulsante “📄 Documentale” / menu Soci → Documentale / Ctrl+D

- **Preferenze**: `PreferencesDialog` (`src/v4_ui/preferences_dialog.py`)
  - Entry: menu Configurazione → Preferenze

- **Export (wizard)**: `UnifiedExportWizard` (`src/v4_ui/unified_export_wizard.py`)
  - Entry: menu File → Esporta dati (Ctrl+E)

- **Import (wizard)**: `UnifiedImportWizard` (`src/v4_ui/unified_import_wizard.py`)
  - Entry: menu File → Importa dati CSV

- **Merge duplicati**: `DuplicatesDialog` (wrapper) (`src/v4_ui/duplicates_dialog.py`)
  - Entry: menu Soci → Ricerca duplicati (Ctrl+M)

- **Batch edit campi soci**: `BatchFieldEditDialog` (`src/v4_ui/batch_edit_dialog.py`)
  - Entry: menu Soci → Modifica campi multipli / pulsante “Modifica campi”

- **Aggiorna stato soci**: `UpdateStatusWizard` (`src/update_status_wizard.py`)
  - Entry: menu Soci → Aggiorna stato soci

- **Email wizard**: `show_email_wizard()` + UI su `tk.Toplevel` (`src/email_wizard.py`)
  - Entry: menu Gestione → 📧 Email wizard

- **Template documenti**: `TemplatesDialog` / `AddTemplateDialog` (`src/v4_ui/templates_dialog.py`)
  - Entry: menu Gestione → 📄 Template documenti

- **Consiglio Direttivo** (dialog separati)
  - Riunioni: `MeetingDialog`, `MeetingsListDialog` (`src/cd_meetings_dialog.py`)
  - Delibere: `DeliberaDialog` (`src/cd_delibere_dialog.py`)
  - Verbali: `VerbaleDialog` (`src/cd_verbali_dialog.py`)

- **Calendario**
  - `CalendarWizard` (`src/v4_ui/calendar_wizard.py`) da tab Calendario

- **Report**
  - `ReportsDialog` (`src/export_dialogs.py`) da `_show_reports_dialog()`

## 4) Pattern UI ricorrenti (da tenere come linee guida)

- **Modalità dialog**: `transient(parent)` + `grab_set()` + pulsanti Salva/Annulla; ritorno spesso via callback o stato interno.
- **Refresh su cambio tab**: `_on_notebook_tab_changed()` aggiorna solo tab costose (es. CD, Statistiche).
- **DB access**: la UI chiama helper in `src/database.py` o manager dedicati; usare `?` per parametri.
- **Documenti**: UI appoggia a `documents_manager.py` e al catalogo categorie (`documents_catalog.py`).
