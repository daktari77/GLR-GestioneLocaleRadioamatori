# Libro Soci v4.1 - Modular Architecture

## Overview

Libro Soci v4.1 represents a significant architectural refactoring from the monolithic v3.x codebase. The application is now organized as a collection of focused, single-responsibility modules.

## Module Structure

### Core Modules

#### `v41_config.py`
- **Purpose**: Application configuration and constants
- **Contents**: 
  - APP_VERSION, AUTHOR, BUILD_ID, BUILD_DATE
  - Directory paths (BASE_DIR, DATA_DIR, BACKUP_DIR, etc.)
  - File paths (DB_NAME, CONFIG_JSON, etc.)
  - Section categories
  - Default configuration dictionary
  - Regular expressions (CAUSALI_CODE_RE)

#### `v41_logger.py`
- **Purpose**: Centralized logging configuration
- **Key Function**: `setup_logger(app_log_path, app_version) → Logger`
- **Features**:
  - File handler with rotation (1MB, 5 backups)
  - Console handler
  - Consistent formatting

#### `v41_utils.py`
- **Purpose**: Utility functions for general use
- **Categories**:
  - **Date utilities**: `now_iso()`, `today_iso()`, `iso_to_ddmmyyyy()`, `ddmmyyyy_to_iso()`, `calc_privacy_scadenza()`
  - **Value utilities**: `isempty()`, `to_bool01()`, `normalize_q()`
  - **File system**: `open_path()`, `docs_dir_for_matricola()`, `set_docs_base()`
  - **Quota utilities**: CAUSALI_CODE_RE, quota validation

#### `v41_database.py`
- **Purpose**: Database operations and schema
- **Key Functions**:
  - `set_db_path(db_name)` - Configure database path
  - `get_conn() → Connection` - Get database connection
  - `fetch_all()`, `fetch_one()`, `exec_query()` - Query operations
  - `init_db()` - Initialize database schema
  - `log_evento()` - Log application events
  - `next_num_iscrizione()` - Get next registration number
- **Schema**:
  - `soci` - Members table (30+ columns)
  - `documenti` - Member documents
  - `eventi_libro_soci` - Activity log
  - `cd_riunioni` - Board meetings
  - `cd_delibere` - Board resolutions
  - `cd_verbali` - Minutes attached to meetings
  - `calendar_events` - Agenda and reminders
  - `ponti` - Sezione repeaters/nodes/beacons registry (rev4.2a)
  - `ponti_status_history` - Operational status log per ponte
  - `ponti_authorizations` - MISE/convenzione/contratto metadata with expiries
  - `ponti_interventi` - Maintenance/upgrade interventions linked to calendario
  - `ponti_documents` - Attachments referencing section documents

#### `v41_causali.py`
- **Purpose**: Quota code management (Q0/Q1/Q2)
- **Key Functions**:
  - `set_causali_path(causali_json)` - Configure path
  - `load_causali_codes() → List[str]` - Load valid quota codes
  - `save_causali_codes(codes)` - Save quota codes

#### `v41_config_manager.py`
- **Purpose**: Section configuration management
- **Key Functions**:
  - `set_config_paths()` - Configure paths
  - `load_config() → dict` - Load section config
  - `save_config(cfg)` - Save section config
  - `ensure_sec_category_dirs()` - Create category directories
  - `copy_into_section()` - Copy files to section docs

#### `v41_documents.py`
- **Purpose**: Document management for members
- **Key Functions**:
  - `list_documenti_for_socio(socio_id)` - List member documents
  - `add_documento_record()` - Record document in DB
  - `delete_documento_record()` - Remove document
  - `copy_in_socio_folder()` - Copy file to member folder
  - `move_file_to_trash()` - Move file to trash

#### `v41_backup.py`
- **Purpose**: Backup and maintenance operations
- **Key Functions**:
  - `backup_on_startup()` - Create startup backup (keeps 10 latest)
  - `verify_db()` - Check database integrity
  - `rebuild_indexes()` - Rebuild database indexes

### Planned Modules (Phase 2)

#### `v41_csv_import.py`
- CSV import wizard
- Preset management
- Column mapping dialogs

#### `v4_dialogs.py`
- CDWindow - Consiglio Direttivo management
- MergeDuplicatesDialog - Merge duplicate members
- MeetingDialog - Board meeting management
- DeliberaDialog - Resolution management
- PresetDialog - Import preset management

#### `v4_ui/main_window.py`
- Main App class
- Root window setup
- Menu bar
- Tabbed interface

#### `v4_ui/forms.py`
- Member data form
- Biographical data
- Contact information
- Role and quota fields

#### `v4_ui/panels.py`
- Document panel
- Quota panel
- Section documents
- Events log

#### `v4_ui/styles.py`
- Theme configuration
- Widget styles
- Color schemes

## Initialization Sequence

The `v41_main.py` entry point follows this sequence:

1. Import configuration constants
2. Setup logger
3. Set database path
4. Set causali path
5. Set config paths
6. Set docs base directory
7. Initialize database schema
8. Perform startup backup
9. Create and run App instance

## Configuration Pattern

Most modules use a "set configuration" pattern to enable dependency injection:

```python
# In module
_config_value = None

def set_config(value):
    global _config_value
    _config_value = value

def use_config():
    if _config_value is None:
        raise RuntimeError("Config not set. Call set_config() first.")
    # Use _config_value
```

This allows:
- Easy testing with different configurations
- Circular dependency avoidance
- Clear dependency declaration
- Runtime flexibility

## Module Dependencies

```
v41_config
    ↓
v41_logger
    ↓
v41_database ← v41_utils, v41_backup
v41_causali ← v41_utils
v41_config_manager
v41_documents ← v41_database, v41_utils
v41_backup ← v41_database
    ↓
v41_main (coordinates all above)
```

## Transition from v3.x to v4.1

### Preserved
- All database operations and schema
- All utility functions
- Configuration management
- Document handling
- Backup system
- CSV import functionality

### Refactored
- Code organization (monolithic → modular)
- Dependency injection (implicit globals → explicit setup)
- Module responsibilities (clear separation)

### In Development
- UI layer separation (complete as Phase 2)
- Dialog implementations
- Form components

## Testing

Each module can be tested independently:

```python
# Test v41_utils
from v41_utils import iso_to_ddmmyyyy
assert iso_to_ddmmyyyy("2025-11-20") == "20/11/2025"

# Test v41_causali
from v41_causali import set_causali_path, load_causali_codes
set_causali_path("/path/to/causali.json")
codes = load_causali_codes()

# Test v41_database
from v41_database import set_db_path, init_db
set_db_path("/path/to/test.db")
init_db()
```

## Future Enhancements

1. **Configuration validation**: Schema validation for config.json
2. **Migration system**: Database schema versioning
3. **Caching layer**: Config and causali caching
4. **Event system**: Internal pub/sub for UI updates
5. **Plugin system**: Allow custom quota handlers, export formats
6. **Async operations**: Background backup, indexing
