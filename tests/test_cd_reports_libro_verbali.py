# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import exec_query, init_db, set_db_path


class TestCdReportsLibroVerbali(unittest.TestCase):
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

    def test_iter_libro_verbali_excludes_future_date_when_tipo_missing(self):
        import cd_reports

        today = date.today()
        past = (today - timedelta(days=10)).isoformat()
        future = (today + timedelta(days=10)).isoformat()

        # tipo_riunione is intentionally NULL to simulate legacy rows.
        exec_query(
            """
            INSERT INTO cd_riunioni (numero_cd, data, titolo, note, tipo_riunione, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("1", past, "Passata", "ODG passata", None, past + "T00:00:00"),
        )
        exec_query(
            """
            INSERT INTO cd_riunioni (numero_cd, data, titolo, note, tipo_riunione, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("2", future, "Futura (legacy)", "ODG futura", None, past + "T00:00:00"),
        )

        rows = cd_reports._iter_libro_verbali_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].data_iso, past)
        self.assertIn("ODG passata", rows[0].odg)


if __name__ == "__main__":
    unittest.main()
