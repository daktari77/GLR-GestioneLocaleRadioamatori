# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database import exec_query, init_db, set_db_path


class TestCdClosureChecks(unittest.TestCase):
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

    def test_delibera_missing_date_is_reported_within_mandate_by_meeting_date(self):
        import cd_closure_checks

        mandate_start = "2026-01-01"
        mandate_end = "2026-12-31"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as fp:
            verbale_path = fp.name

        try:
            # Meeting in period
            exec_query(
                """
                INSERT INTO cd_riunioni (numero_cd, data, titolo, note, tipo_riunione, verbale_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("1", "2026-02-10", "Riunione", "", "passata", verbale_path, "2026-02-10T00:00:00"),
            )

            from database import fetch_one

            meeting_row = fetch_one("SELECT id FROM cd_riunioni WHERE numero_cd = ?", ("1",))
            self.assertIsNotNone(meeting_row)
            cd_id = int(meeting_row["id"])

            # Delibera in that meeting, but missing data_votazione
            exec_query(
                """
                INSERT INTO cd_delibere (cd_id, numero, oggetto, esito, data_votazione, allegato_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (cd_id, "1/2026", "Oggetto", "APPROVATA", None, None, "2026-02-10T00:00:00"),
            )

            # Avoid touching section-documents filesystem in this unit test
            with mock.patch("section_documents.list_cd_verbali_documents", return_value=[]):
                report = cd_closure_checks.run_cd_mandato_closure_checks(
                    start_date=mandate_start,
                    end_date=mandate_end,
                )

            self.assertEqual(report.get("stats", {}).get("delibere_in_period"), 1)
            kinds = {e.get("kind") for e in (report.get("errors") or [])}
            self.assertIn("delibera_missing_date", kinds)
        finally:
            try:
                os.unlink(verbale_path)
            except Exception:
                pass

    def test_future_meeting_is_excluded_from_meeting_checks(self):
        import cd_closure_checks

        mandate_start = "2026-01-01"
        mandate_end = "2026-12-31"

        # A meeting marked as 'futura' should be excluded even if in range
        exec_query(
            """
            INSERT INTO cd_riunioni (numero_cd, data, titolo, note, tipo_riunione, verbale_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("F1", "2026-06-01", "Riunione futura", "", "futura", "", "2026-06-01T00:00:00"),
        )

        with mock.patch("section_documents.list_cd_verbali_documents", return_value=[]):
            report = cd_closure_checks.run_cd_mandato_closure_checks(
                start_date=mandate_start,
                end_date=mandate_end,
            )

        # No meetings should be considered in-period (since it's futura)
        self.assertEqual(report.get("stats", {}).get("meetings_in_period"), 0)
        kinds = {e.get("kind") for e in (report.get("errors") or [])}
        self.assertNotIn("missing_meeting_verbale", kinds)


if __name__ == "__main__":
    unittest.main()
