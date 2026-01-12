# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import exec_query, init_db, set_db_path


class TestCdReportsLibroDelibere(unittest.TestCase):
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

    def test_iter_libro_delibere_excludes_future_meeting_when_tipo_missing(self):
        import cd_reports

        today = date.today()
        past = (today - timedelta(days=10)).isoformat()
        future = (today + timedelta(days=10)).isoformat()

        # Two meetings: legacy (tipo_riunione NULL)
        exec_query(
            """
            INSERT INTO cd_riunioni (numero_cd, data, titolo, note, tipo_riunione, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("1", past, "Riunione passata", "", None, past + "T00:00:00"),
        )
        exec_query(
            """
            INSERT INTO cd_riunioni (numero_cd, data, titolo, note, tipo_riunione, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("2", future, "Riunione futura", "", None, past + "T00:00:00"),
        )

        # exec_query returns None; fetch ids explicitly
        from database import fetch_one

        past_row = fetch_one("SELECT id FROM cd_riunioni WHERE numero_cd = ?", ("1",))
        future_row = fetch_one("SELECT id FROM cd_riunioni WHERE numero_cd = ?", ("2",))
        self.assertIsNotNone(past_row)
        self.assertIsNotNone(future_row)
        past_cd_id = int(past_row["id"])
        future_cd_id = int(future_row["id"])

        # Add one delibera per meeting
        exec_query(
            """
            INSERT INTO cd_delibere (cd_id, numero, oggetto, esito, data_votazione, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (past_cd_id, "1/2026", "Oggetto passata", "APPROVATA", past, past + "T00:00:00"),
        )
        exec_query(
            """
            INSERT INTO cd_delibere (cd_id, numero, oggetto, esito, data_votazione, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (future_cd_id, "2/2026", "Oggetto futura", "APPROVATA", future, past + "T00:00:00"),
        )

        rows = cd_reports._iter_libro_delibere_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].numero_delibera, "1/2026")
        self.assertEqual(rows[0].data_iso, past)


if __name__ == "__main__":
    unittest.main()
