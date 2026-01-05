# -*- coding: utf-8 -*-

import unittest
from datetime import date

from utils import (
    statuto_diritti_sospesi,
    statuto_morosita_continua_anni,
    statuto_voto_coerente,
)


class TestStatutoRules(unittest.TestCase):
    def test_diritti_sospesi_when_q0_missing_after_jan1(self):
        self.assertTrue(statuto_diritti_sospesi(q0=None, oggi=date(2026, 1, 3)))
        self.assertTrue(statuto_diritti_sospesi(q0="", oggi=date(2026, 1, 3)))

    def test_diritti_not_sospesi_when_q0_present(self):
        self.assertFalse(statuto_diritti_sospesi(q0="AD", oggi=date(2026, 1, 3)))
        # Il CSV ARI usa anche codici a 1 carattere (es. '4')
        self.assertFalse(statuto_diritti_sospesi(q0="4", oggi=date(2026, 1, 3)))

    def test_morosita_continua_anni(self):
        self.assertEqual(2, statuto_morosita_continua_anni(q0=None, q1=None))
        self.assertEqual(2, statuto_morosita_continua_anni(q0="", q1=""))
        self.assertEqual(1, statuto_morosita_continua_anni(q0=None, q1="AD"))
        self.assertEqual(0, statuto_morosita_continua_anni(q0="AD", q1=None))

    def test_voto_coerente_rules(self):
        # voto != 1 -> always "coerente" (no warning)
        self.assertTrue(
            statuto_voto_coerente(voto=0, data_iscrizione=None, q0=None, oggi=date(2026, 1, 3))
        )

        # voto=1 requires Q0 and data_iscrizione
        self.assertFalse(
            statuto_voto_coerente(voto=1, data_iscrizione="2025-10-01", q0=None, oggi=date(2026, 1, 3))
        )
        self.assertFalse(
            statuto_voto_coerente(voto=1, data_iscrizione=None, q0="AD", oggi=date(2026, 1, 3))
        )

        # voto=1 requires >= 90 days
        self.assertFalse(
            statuto_voto_coerente(voto=1, data_iscrizione="2025-10-10", q0="AD", oggi=date(2026, 1, 3))
        )
        self.assertTrue(
            statuto_voto_coerente(voto=1, data_iscrizione="2025-10-01", q0="AD", oggi=date(2026, 1, 3))
        )


if __name__ == "__main__":
    unittest.main()
