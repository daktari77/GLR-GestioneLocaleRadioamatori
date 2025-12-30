import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Controlled upgrade: drop section_documents.original_name and migrate its values into descrizione when empty."
        )
    )
    p.add_argument(
        "--app-root",
        default=None,
        help="GestioneSoci root folder (contains data/soci.db). If omitted, uses current directory.",
    )
    p.add_argument(
        "--db",
        default=None,
        help="Explicit path to soci.db (overrides --app-root).",
    )
    p.add_argument(
        "--backup-dir",
        default=None,
        help="Directory where a DB backup will be written. Defaults under <app-root>/backup/.",
    )
    p.add_argument("--dry-run", action="store_true", help="Show what would change without modifying the DB.")
    return p.parse_args()


def _backup_db(db_path: Path, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup_dir / db_path.name)
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            shutil.copy2(side, backup_dir / side.name)


def _has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    return any(r["name"] == col for r in conn.execute(f"PRAGMA table_info({table})"))


def main() -> int:
    args = _parse_args()

    app_root = Path(args.app_root).resolve() if args.app_root else Path.cwd().resolve()
    db_path = Path(args.db).resolve() if args.db else (app_root / "data" / "soci.db").resolve()
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = (
        Path(args.backup_dir).resolve()
        if args.backup_dir
        else (app_root / "backup" / f"upgrade_section_documents_{ts}").resolve()
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if not _has_column(conn, "section_documents", "original_name"):
            print("No action: section_documents.original_name does not exist.")
            return 0

        # Preview impact
        preview = conn.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN (descrizione IS NULL OR TRIM(descrizione) = '') AND original_name IS NOT NULL AND TRIM(original_name) != '' THEN 1 ELSE 0 END) AS will_copy
            FROM section_documents
            """
        ).fetchone()
        print("Rows:", int(preview["total"]))
        print("Rows where descrizione will be filled from original_name:", int(preview["will_copy"]))

        if args.dry_run:
            print("Dry-run: no changes applied.")
            return 0

        # Backup first
        _backup_db(db_path, backup_dir)
        print("Backup written to:", str(backup_dir))

        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        try:
            conn.execute(
                """
                CREATE TABLE section_documents_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    socio_id INTEGER,
                    hash_id TEXT NOT NULL UNIQUE,
                    nome_file TEXT,
                    percorso TEXT,
                    tipo TEXT,
                    categoria TEXT,
                    descrizione TEXT,
                    data_caricamento TEXT,
                    protocollo TEXT,
                    verbale_numero TEXT,
                    stored_name TEXT,
                    relative_path TEXT NOT NULL,
                    uploaded_at TEXT,
                    deleted_at TEXT
                )
                """
            )

            conn.execute(
                """
                INSERT INTO section_documents_new (
                    id,
                    socio_id,
                    hash_id,
                    nome_file,
                    percorso,
                    tipo,
                    categoria,
                    descrizione,
                    data_caricamento,
                    protocollo,
                    verbale_numero,
                    stored_name,
                    relative_path,
                    uploaded_at,
                    deleted_at
                )
                SELECT
                    id,
                    socio_id,
                    hash_id,
                    nome_file,
                    percorso,
                    tipo,
                    categoria,
                    CASE
                        WHEN (descrizione IS NULL OR TRIM(descrizione) = '')
                        THEN COALESCE(NULLIF(TRIM(original_name), ''), '')
                        ELSE descrizione
                    END AS descrizione,
                    data_caricamento,
                    protocollo,
                    verbale_numero,
                    stored_name,
                    relative_path,
                    uploaded_at,
                    deleted_at
                FROM section_documents
                """
            )

            conn.execute("DROP TABLE section_documents")
            conn.execute("ALTER TABLE section_documents_new RENAME TO section_documents")

            # Recreate indexes (match database.py)
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_section_documents_relative_path ON section_documents(relative_path) WHERE deleted_at IS NULL"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_section_documents_percorso ON section_documents(percorso) WHERE deleted_at IS NULL"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_section_documents_categoria ON section_documents(categoria)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_section_documents_data ON section_documents(data_caricamento)")

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys=ON")

        print("Upgrade completed.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
