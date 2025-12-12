# -*- coding: utf-8 -*-
"""Unit tests for ponti_manager."""

import os
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import init_db, set_db_path, fetch_one
from ponti_manager import (
    add_ponte_document,
    create_ponte,
    delete_authorization,
    delete_ponte,
    delete_ponte_document,
    get_ponte,
    list_authorizations,
    list_ponte_documents,
    list_ponti,
    save_authorization,
    set_ponti_docs_base,
    update_ponte,
    update_ponte_document,
)


def _safe_unlink(path: str):
    try:
        os.unlink(path)
    except OSError:
        pass


class TestPontiManager(unittest.TestCase):
    def setUp(self):
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp.close()
        self.db_path = temp.name
        set_db_path(self.db_path)
        init_db()
        self.docs_root_context = tempfile.TemporaryDirectory()
        self.ponti_docs_root = Path(self.docs_root_context.name) / "ponti_docs"
        set_ponti_docs_base(self.ponti_docs_root)
        self.addCleanup(set_ponti_docs_base, "data/documents/ponti")
        self.addCleanup(self.docs_root_context.cleanup)
        self.ponte_id = create_ponte(
            nome="Ponte Test",
            nominativo="IR2TEST",
            localita="Milano",
            stato="attivo",
            note="Note iniziali",
        )

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except Exception:
            pass

    def _create_source_file(self, suffix: str = ".pdf") -> str:
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        handle.write(b"ponti document test")
        handle.flush()
        handle.close()
        self.addCleanup(lambda path=handle.name: _safe_unlink(path))
        return handle.name

    def test_create_get_and_list(self):
        ponte = get_ponte(self.ponte_id)
        self.assertIsNotNone(ponte)
        assert ponte is not None
        self.assertEqual(ponte["nome"], "Ponte Test")
        self.assertEqual(ponte["nominativo"], "IR2TEST")
        self.assertIsNone(ponte["next_scadenza"])

        elenco = list_ponti()
        self.assertEqual(len(elenco), 1)
        self.assertEqual(elenco[0]["nome"], "Ponte Test")

    def test_update_and_delete(self):
        update_result = update_ponte(
            self.ponte_id,
            nome="Ponte Aggiornato",
            stato="manutenzione",
            note="Nuove note",
        )
        self.assertTrue(update_result)
        ponte = get_ponte(self.ponte_id)
        self.assertEqual(ponte["nome"], "Ponte Aggiornato")
        self.assertEqual(ponte["stato_corrente"], "MANUTENZIONE")
        self.assertEqual(ponte["note_tecniche"], "Nuove note")

        deleted = delete_ponte(self.ponte_id)
        self.assertTrue(deleted)
        self.assertIsNone(get_ponte(self.ponte_id))

    def test_authorization_with_reminder(self):
        auth_id = save_authorization(
            self.ponte_id,
            tipo="MISE",
            ente="MIMIT",
            numero="AUT-01",
            data_rilascio="01/01/2024",
            data_scadenza="01/12/2025",
            note="Promemoria test",
        )
        self.assertGreater(auth_id, 0)
        dati = fetch_one(
            "SELECT * FROM ponti_authorizations WHERE id = ?",
            (auth_id,),
        )
        self.assertIsNotNone(dati)
        assert dati is not None
        self.assertEqual(dati["data_scadenza"], "2025-12-01")
        self.assertIsNotNone(dati["calendar_event_id"])

        event = fetch_one(
            "SELECT * FROM calendar_events WHERE id = ?",
            (dati["calendar_event_id"],),
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["start_ts"], "2025-12-01T09:00:00")

        lista = list_authorizations(self.ponte_id)
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["id"], auth_id)

        # Disable reminder and ensure calendar event removed
        save_authorization(
            self.ponte_id,
            tipo="MISE",
            ente="MIMIT",
            numero="AUT-01",
            data_rilascio="01/01/2024",
            data_scadenza="01/12/2025",
            authorization_id=auth_id,
            enable_reminder=False,
        )
        dati = fetch_one(
            "SELECT calendar_event_id FROM ponti_authorizations WHERE id = ?",
            (auth_id,),
        )
        self.assertIsNone(dati["calendar_event_id"])

        remaining_event = fetch_one(
            "SELECT id FROM calendar_events WHERE id = ?",
            (event["id"],),
        )
        self.assertIsNone(remaining_event)

        # Create another authorization with reminder and test delete
        auth2 = save_authorization(
            self.ponte_id,
            tipo="MISE",
            ente="MIMIT",
            numero="AUT-02",
            data_rilascio="01/02/2024",
            data_scadenza="01/01/2026",
        )
        dati2 = fetch_one(
            "SELECT calendar_event_id FROM ponti_authorizations WHERE id = ?",
            (auth2,),
        )
        self.assertIsNotNone(dati2)
        event2 = fetch_one(
            "SELECT * FROM calendar_events WHERE id = ?",
            (dati2["calendar_event_id"],),
        )
        self.assertIsNotNone(event2)
        self.assertTrue(delete_authorization(auth2))
        self.assertIsNone(
            fetch_one("SELECT id FROM ponti_authorizations WHERE id = ?", (auth2,))
        )
        self.assertIsNone(
            fetch_one("SELECT id FROM calendar_events WHERE id = ?", (event2["id"],))
        )

    def test_documents_crud(self):
        source_path = self._create_source_file()
        doc_id = add_ponte_document(
            self.ponte_id,
            source_path,
            tipo="autorizzazione",
            note="Documento iniziale",
        )
        self.assertGreater(doc_id, 0)

        docs = list_ponte_documents(self.ponte_id)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["tipo"], "autorizzazione")
        stored_path = Path(docs[0]["document_path"])
        self.assertTrue(stored_path.exists())
        self.assertTrue(str(stored_path).startswith(str(self.ponti_docs_root)))
        self.assertNotEqual(stored_path.resolve(), Path(source_path).resolve())

        # Update document metadata
        self.assertTrue(
            update_ponte_document(doc_id, tipo="verbale", note="Aggiornato")
        )
        docs = list_ponte_documents(self.ponte_id)
        self.assertEqual(docs[0]["tipo"], "verbale")
        self.assertEqual(docs[0]["note"], "Aggiornato")

        deleted = delete_ponte_document(doc_id)
        self.assertTrue(deleted)
        self.assertEqual(len(list_ponte_documents(self.ponte_id)), 0)
        self.assertFalse(stored_path.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
