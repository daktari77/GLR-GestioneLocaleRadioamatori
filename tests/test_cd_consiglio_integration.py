# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import set_db_path, init_db


class TestConsiglioDirettivoVerbaliIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        set_db_path(self.db_path)
        init_db()

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    def test_list_cd_verbali_documents_includes_category_or_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sec_root = tmp_path / "section_docs"
            src_dir = tmp_path / "src"
            src_dir.mkdir(parents=True, exist_ok=True)

            # Prepare two files
            f1 = src_dir / "verbale1.pdf"
            f2 = src_dir / "altro_con_numero.pdf"
            f1.write_bytes(b"V1")
            f2.write_bytes(b"V2")

            import section_documents

            old_root = section_documents.SECTION_DOCUMENT_ROOT
            old_meta = section_documents.SECTION_METADATA_FILE
            section_documents.SECTION_DOCUMENT_ROOT = sec_root
            section_documents.SECTION_METADATA_FILE = sec_root / "metadata.json"
            try:
                # Included because category contains 'verbale'
                # (must match a real configured category; unknown labels are normalized to "Altro")
                section_documents.add_section_document(str(f1), "Verbali CD", "Verbale CD")

                # Included because verbale_numero is present even if category isn't
                section_documents.add_section_document(
                    str(f2),
                    "Bilanci",
                    "Documento non verbale ma numerato",
                    verbale_numero="12",
                )

                verbali = section_documents.list_cd_verbali_documents()
                self.assertEqual(len(verbali), 2)

                abs_paths = {str(v.get("absolute_path") or "") for v in verbali}
                self.assertEqual(len([p for p in abs_paths if p]), 2)
                for p in abs_paths:
                    self.assertTrue(p and os.path.exists(p), msg=f"Missing file: {p}")
            finally:
                section_documents.SECTION_DOCUMENT_ROOT = old_root
                section_documents.SECTION_METADATA_FILE = old_meta


if __name__ == "__main__":
    unittest.main()
