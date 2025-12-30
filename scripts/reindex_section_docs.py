import argparse
import json
import os
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Re-index section documents (DB ↔ filesystem reconciliation).")
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
        "--section-root",
        default=None,
        help="Explicit path to data/section_docs (overrides --app-root).",
    )
    p.add_argument("--dry-run", action="store_true", help="Compute changes but do not write DB.")
    p.add_argument(
        "--import-orphans",
        action="store_true",
        help="Import orphan files found on disk into DB (best effort).",
    )
    p.add_argument(
        "--backfill",
        action="store_true",
        help="Backfill DB from metadata.json + on-disk scan before reindex (can create duplicates on broken DBs).",
    )
    p.add_argument(
        "--prune-missing",
        action="store_true",
        help="Soft-delete records that are missing and point outside section root (stale absolute paths).",
    )
    p.add_argument(
        "--report",
        default=None,
        help="Write JSON report to this path.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    app_root = Path(args.app_root).resolve() if args.app_root else Path.cwd().resolve()
    db_path = Path(args.db).resolve() if args.db else (app_root / "data" / "soci.db").resolve()
    section_root = (
        Path(args.section_root).resolve() if args.section_root else (app_root / "data" / "section_docs").resolve()
    )

    # Make src importable when launched from repo root.
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = (repo_root / "src").resolve()
    sys.path.insert(0, str(src_dir))

    # Ensure relative paths in config work as expected.
    os.chdir(str(app_root))

    from database import init_db, set_db_path
    from section_documents import reindex_section_documents

    set_db_path(str(db_path))
    init_db()

    result = reindex_section_documents(
        root_dir=section_root,
        dry_run=bool(args.dry_run),
        import_orphans=bool(args.import_orphans),
        backfill_registry=bool(args.backfill),
        prune_missing=bool(args.prune_missing),
    )

    print("root:", result.get("root"))
    print("dry_run:", result.get("dry_run"))
    print("scanned:", result.get("scanned"))
    print("updated:", result.get("updated"))
    print("missing:", result.get("missing"))
    print("imported:", result.get("imported"))

    errors = (result.get("details") or {}).get("errors") or []
    if errors:
        print("errors:", len(errors))
        for e in errors[:20]:
            print(" -", e)

    if args.report:
        report_path = Path(args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("report:", str(report_path))

    # Exit non-zero when there are errors (useful in automation)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
