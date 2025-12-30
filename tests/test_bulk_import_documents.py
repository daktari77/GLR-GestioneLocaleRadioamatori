# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import set_db_path, init_db, exec_query, fetch_one, get_documenti, list_section_document_records


class TestBulkImportDocuments(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        set_db_path(self.db_path)
        init_db()

        exec_query(
            "INSERT INTO soci (nome, cognome, email, attivo) VALUES (?, ?, ?, ?)",
            ("Mario", "Rossi", "mario@example.com", 1),
        )
        row = fetch_one("SELECT id FROM soci WHERE email = ?", ("mario@example.com",))
        self.socio_id = int(row["id"]) if isinstance(row, dict) else int(row[0])

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    def test_bulk_import_member_documents_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_dir = tmp_path / "src"
            docs_root = tmp_path / "docs"
            src_dir.mkdir(parents=True, exist_ok=True)

            (src_dir / "a.pdf").write_bytes(b"A")
            (src_dir / "b.pdf").write_bytes(b"B")

            import documents_manager

            old_base = documents_manager.DOCS_BASE_DIR
            documents_manager.DOCS_BASE_DIR = str(docs_root)
            try:
                imported, failed, details = documents_manager.bulk_import_member_documents(
                    self.socio_id,
                    str(src_dir),
                    "Ricevute",
                    move=False,
                )
            finally:
                documents_manager.DOCS_BASE_DIR = old_base

            self.assertEqual(imported, 2)
            self.assertEqual(failed, 0, msg=f"details={details}")
            self.assertTrue((src_dir / "a.pdf").exists())
            self.assertTrue((src_dir / "b.pdf").exists())

            docs = get_documenti(self.socio_id)
            self.assertEqual(len(docs), 2)
            for doc in docs:
                self.assertTrue(os.path.exists(doc["percorso"]))

    def test_bulk_import_section_documents_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_dir = tmp_path / "src"
            sec_root = tmp_path / "section_docs"
            src_dir.mkdir(parents=True, exist_ok=True)

            (src_dir / "v1.pdf").write_bytes(b"V1")
            (src_dir / "v2.pdf").write_bytes(b"V2")

            import section_documents

            # Patch root to keep test isolated
            old_root = section_documents.SECTION_DOCUMENT_ROOT
            old_meta = section_documents.SECTION_METADATA_FILE
            section_documents.SECTION_DOCUMENT_ROOT = sec_root
            section_documents.SECTION_METADATA_FILE = sec_root / "metadata.json"
            try:
                imported, failed, details = section_documents.bulk_import_section_documents(
                    str(src_dir),
                    "Verbali CD",
                    move=True,
                )
            finally:
                section_documents.SECTION_DOCUMENT_ROOT = old_root
                section_documents.SECTION_METADATA_FILE = old_meta

            self.assertEqual(imported, 2)
            self.assertEqual(failed, 0, msg=f"details={details}")
            self.assertFalse((src_dir / "v1.pdf").exists())
            self.assertFalse((src_dir / "v2.pdf").exists())

            rows = list_section_document_records(include_deleted=False)
            self.assertEqual(len(rows), 2)
            for row in rows:
                path = row.get("percorso")
                self.assertTrue(path and os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
