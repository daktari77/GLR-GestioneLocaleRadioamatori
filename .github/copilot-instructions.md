# GestioneSoci v0.4.2b – AI Coding Agent Notes
- Desktop Tkinter + SQLite app for ARI member management (registry, documents, board meetings, repeaters, CSV import). Modular, dependency-injected startup.

## Startup pattern (must follow)
- In `src/main.py`: call setters before any module use/UI import:
    `set_db_path(DB_NAME)`, `set_causali_path(CAUSALI_JSON)`, `set_config_paths(CONFIG_JSON, SEC_DOCS, DEFAULT_CONFIG, list(SEC_CATEGORIES))`, `set_docs_base(DOCS_BASE)`; then `from v4_ui.main_window import App`. Applies to `database.py`, `causali.py`, `config_manager.py`, `utils.py`.

## Layers & key modules
- Config: `config.py` (APP_VERSION, BUILD_ID, paths, regexes)
- DB: `database.py` (`get_connection()`, helpers `fetch_all/one`, `exec_query`, `init_db`)
- Models: `models.py` (`Member` validation: email, CF, CAP, provincia, ISO dates, quota codes)
- Business logic: `documents.py`, `backup.py` (incremental SHA256), `causali.py`, `config_manager.py`
- UI: `v4_ui/main_window.py` (big Tkinter App), dialogs/panels under `v4_ui/`

## Data model (SQLite)
- Tables: `soci`, `documenti`, `cd_riunioni`, `cd_delibere`, `cd_verbali`, `ponti`, `ponti_status_history`, `ponti_authorizations`, `calendar_events`.
- Use `?` parameters only; f-strings allowed solely for column names.

## Working patterns
- DB ops: wrap writes in `with get_connection(): ...`; simple queries via helpers. Handle sqlite errors with `map_sqlite_exception`; custom exceptions in `exceptions.py`.
- Docs: files under `data/documents/<MATRICOLA>/`; categories from `documents_catalog.py` (`DOCUMENT_CATEGORIES`, `normalize_category`); trash at `data/.trash/`.
- UI: dialogs inherit `tk.Toplevel`, modal with `grab_set()`, return via `self.result`; Treeview columns in `App.COLONNE`/`VISIBLE_COLUMNS`, first column "⚠" for warnings.
- Dates: ISO `YYYY-MM-DD`; helpers in `utils.py` (`now_iso`, `ddmmyyyy_to_iso`, etc.); privacy expires via `calc_privacy_scadenza`.
- Quota codes: stored in `data/causali.json`, validated by `CAUSALI_CODE_RE` in `config.py`.

## Dev workflows
- Run app: `cd src; python main.py`
- Tests: `python tests/run_tests.py` (or `test_database`, `test_backup`, `test_models`)
- Type check: `pyright src` (see `pyrightconfig.json`)
- Build portable EXE: `cd src; ..\scripts\build_exe.ps1` (outputs `dist_portable_*`)

## References
- Architecture: `src/V4_ARCHITECTURE.md`, `src/V4_MODULE_INDEX.md`, `src/V4_PHASE2_SUMMARY.md`
- Improvements log: `IMPROVEMENTS_IMPLEMENTED.md` (SQL injection review, connection handling, incremental backup)
- Tests doc: `tests/README.md`; build script: `scripts/build_exe.ps1`

## Common pitfalls
- Forgetting setters before imports; calling `get_conn()` without closing (use `get_connection()`)
- Schema changes must update `init_db()`
- Avoid `&&` in PowerShell (use `;`)
- Do not hard-code doc categories; use catalog helpers

Version: computed from `config.py` mtime (`BUILD_ID = YYYYMMDD.HHMM`); current APP_VERSION 0.4.2b (includes repeater/ponti features).
