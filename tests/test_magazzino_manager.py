# -*- coding: utf-8 -*-
"""Tests for magazzino_manager module."""

import os
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import get_connection, init_db, set_db_path
from magazzino_manager import (
    create_item,
    create_loan,
    delete_item,
    get_active_loan,
    get_item,
    list_items,
    list_loans,
    register_return,
    update_item,
)
from utils import today_iso


class TestMagazzinoManager(unittest.TestCase):
    def setUp(self):
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp.close()
        self.db_path = temp.name
        set_db_path(self.db_path)
        init_db()
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO soci (nome, cognome, matricola) VALUES (?, ?, ?)",
                ("Mario", "Rossi", "001"),
            )
            socio_id = cur.lastrowid
            if socio_id is None:
                raise RuntimeError("Impossibile creare il socio di test")
            self.socio_id = int(socio_id)
        item_id = create_item(
            numero_inventario="INV-01",
            marca="Yaesu",
            modello="FT-818",
            descrizione="Ricetrasmettitore portatile",
            note="Test",
        )
        self.item_id = int(item_id)

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_item_crud(self):
        item = get_item(self.item_id)
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item["marca"], "Yaesu")
        items = list_items()
        self.assertEqual(len(items), 1)
        update_item(
            self.item_id,
            marca="Icom",
            modello="IC-7300",
            descrizione="Base station",
            note="Aggiornato",
        )
        updated = get_item(self.item_id)
        assert updated is not None
        self.assertEqual(updated["marca"], "Icom")
        self.assertEqual(updated["modello"], "IC-7300")
        self.assertEqual(updated["note"], "Aggiornato")
        delete_item(self.item_id)
        self.assertIsNone(get_item(self.item_id))
        self.assertEqual(len(list_items()), 0)

    def test_loans_flow(self):
        loan_id = create_loan(self.item_id, socio_id=self.socio_id, data_prestito="01/12/2025")
        self.assertGreater(loan_id, 0)
        active = get_active_loan(self.item_id)
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active["socio_id"], self.socio_id)
        self.assertEqual(active["data_prestito"], "2025-12-01")
        loans = list_loans(self.item_id)
        self.assertEqual(len(loans), 1)
        with self.assertRaises(ValueError):
            create_loan(self.item_id, socio_id=self.socio_id)
        register_return(loan_id)
        active_after = get_active_loan(self.item_id)
        self.assertIsNone(active_after)
        loans = list_loans(self.item_id)
        self.assertEqual(loans[0]["data_reso"], today_iso())


if __name__ == "__main__":
    unittest.main(verbosity=2)
