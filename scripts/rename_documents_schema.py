#!/usr/bin/env python
"""Utility to enforce the NOMINATIVO_CATEGORIA_DATA schema on stored documents."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    DB_NAME,
    CAUSALI_JSON,
    CONFIG_JSON,
    SEC_DOCS,
    DEFAULT_CONFIG,
    SEC_CATEGORIES,
    DOCS_BASE,
)
from causali import set_causali_path
from config_manager import set_config_paths
from database import set_db_path, init_db
from utils import set_docs_base
from documents_manager import bulk_rename_documents_to_schema  # noqa:E402
from section_documents import rename_section_documents_to_schema  # noqa:E402


def _bootstrap_environment() -> None:
    set_db_path(DB_NAME)
    set_causali_path(CAUSALI_JSON)
    set_config_paths(CONFIG_JSON, SEC_DOCS, DEFAULT_CONFIG, list(SEC_CATEGORIES))
    set_docs_base(DOCS_BASE)
    init_db()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rinomina i documenti esistenti seguendo lo schema NOMINATIVO_CATEGORIA_DATA. "
            "Usa --dry-run per vedere solo l'elenco dei cambi." 
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Non applica modifiche, mostra solo le rinomine pianificate.",
    )
    args = parser.parse_args()

    _bootstrap_environment()

    member_changes = bulk_rename_documents_to_schema(dry_run=args.dry_run)
    section_changes = rename_section_documents_to_schema(dry_run=args.dry_run)

    total_changes = member_changes + section_changes
    if not total_changes:
        print("Nessun documento da rinominare: tutto conforme.")
        return

    action = "Pianificate" if args.dry_run else "Applicate"
    print(f"{action} {len(total_changes)} rinomine complessive.\n")

    if member_changes:
        print("Documenti soci:")
        for old, new in member_changes:
            print(f"- {old} -> {new}")
        print()

    if section_changes:
        print("Documenti di sezione:")
        for old, new in section_changes:
            print(f"- {old} -> {new}")


if __name__ == "__main__":
    main()
