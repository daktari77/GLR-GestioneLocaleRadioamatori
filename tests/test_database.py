# -*- coding: utf-8 -*-
"""
Unit tests for v41_database.py

Tests database operations: CRUD, connections, transactions, exceptions.
"""

import unittest
import tempfile
import os
import sqlite3
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import (
    set_db_path,
    init_db,
    fetch_one,
    fetch_all,
    exec_query,
    get_connection,
    add_documento,
    get_documenti,
    delete_documento,
    add_section_document_record,
    list_section_document_records,
    get_section_document_by_relative_path,
    update_section_document_record,
    soft_delete_section_document_record,
)
from exceptions import (
    DatabaseError,
    DatabaseIntegrityError,
    RequiredFieldError
)


class TestDatabaseBasics(unittest.TestCase):
    """Test basic database operations."""
    
    def setUp(self):
        """Create temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        set_db_path(self.db_path)
        init_db()
    
    def tearDown(self):
        """Clean up temporary database."""
        try:
            os.unlink(self.db_path)
        except Exception:
            pass
    
    def test_init_db_creates_tables(self):
        """Test that init_db creates all required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check soci table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='soci'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check documenti table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documenti'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check cd_riunioni table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cd_riunioni'")
        self.assertIsNotNone(cursor.fetchone())

        # Check cd_riunioni has MVP JSON columns
        cursor.execute("PRAGMA table_info(cd_riunioni)")
        cols = {row[1] for row in cursor.fetchall()}  # row[1] is column name
        for col in ("meta_json", "odg_json", "presenze_json"):
            self.assertIn(col, cols, msg=f"Missing column cd_riunioni.{col}")

        # Check cd_mandati table exists (mandato Consiglio Direttivo)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cd_mandati'")
        self.assertIsNotNone(cursor.fetchone())

        # Check new ponti tables exist
        for table_name in (
            "ponti",
            "ponti_status_history",
            "ponti_authorizations",
            "ponti_interventi",
            "ponti_documents",
            "section_documents",
        ):
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            self.assertIsNotNone(cursor.fetchone(), msg=f"Missing table {table_name}")
        
        conn.close()


class TestSectionDocumentsRegistry(unittest.TestCase):
    """Test DB registry for section documents (filesystem is not exercised here)."""

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

    def test_section_documents_crud(self):
        record_id = add_section_document_record(
            hash_id="deadbeef00",
            categoria="Verbali CD",
            descrizione="Prova",
            protocollo="PROT-123/2025",
            verbale_numero="7",
            stored_name="deadbeef00.docx",
            relative_path="verbali_cd/deadbeef00.docx",
            uploaded_at="2025-12-24T10:00:00",
        )
        self.assertIsNotNone(record_id)

        rows = list_section_document_records(include_deleted=False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["hash_id"], "deadbeef00")

        found = get_section_document_by_relative_path("verbali_cd/deadbeef00.docx")
        self.assertIsNotNone(found)
        # Colonne uniformate devono essere valorizzate via backfill/insert
        self.assertTrue((found.get("percorso") or "").endswith("verbali_cd/deadbeef00.docx"))
        self.assertEqual(found.get("tipo"), "documento")
        self.assertEqual(found.get("protocollo"), "PROT-123/2025")
        self.assertEqual(found.get("verbale_numero"), "7")

        ok = update_section_document_record(
            int(found["id"]),
            categoria="Bilanci",
            descrizione="Aggiornata",
            protocollo="PROT-999/2025",
            verbale_numero="8",
        )
        self.assertTrue(ok)
        found2 = get_section_document_by_relative_path("verbali_cd/deadbeef00.docx")
        self.assertEqual(found2["categoria"], "Bilanci")
        self.assertEqual(found2.get("protocollo"), "PROT-999/2025")
        self.assertEqual(found2.get("verbale_numero"), "8")

        self.assertTrue(soft_delete_section_document_record(int(found2["id"])))
        rows_after = list_section_document_records(include_deleted=False)
        self.assertEqual(len(rows_after), 0)
    
    def test_insert_and_fetch_member(self):
        """Test inserting and fetching a member."""
        # Insert member
        exec_query(
            "INSERT INTO soci (nome, cognome, email, attivo) VALUES (?, ?, ?, ?)",
            ("Mario", "Rossi", "mario@example.com", 1)
        )
        
        # Fetch member
        member = fetch_one("SELECT * FROM soci WHERE nome = ?", ("Mario",))
        
        self.assertIsNotNone(member)
        self.assertEqual(member['nome'], "Mario")
        self.assertEqual(member['cognome'], "Rossi")
        self.assertEqual(member['email'], "mario@example.com")
        self.assertEqual(member['attivo'], 1)
    
    def test_fetch_all_members(self):
        """Test fetching multiple members."""
        # Insert multiple members
        members_data = [
            ("Mario", "Rossi"),
            ("Luigi", "Verdi"),
            ("Anna", "Bianchi")
        ]
        
        for nome, cognome in members_data:
            exec_query(
                "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
                (nome, cognome, 1)
            )
        
        # Fetch all
        members = fetch_all("SELECT * FROM soci WHERE attivo = ?", (1,))
        
        self.assertEqual(len(members), 3)
        self.assertEqual(members[0]['nome'], "Mario")
        self.assertEqual(members[1]['nome'], "Luigi")
        self.assertEqual(members[2]['nome'], "Anna")
    
    def test_update_member(self):
        """Test updating a member."""
        # Insert member
        exec_query(
            "INSERT INTO soci (nome, cognome, email, attivo) VALUES (?, ?, ?, ?)",
            ("Mario", "Rossi", "mario@old.com", 1)
        )
        
        # Update email
        exec_query(
            "UPDATE soci SET email = ? WHERE nome = ?",
            ("mario@new.com", "Mario")
        )
        
        # Verify update
        member = fetch_one("SELECT * FROM soci WHERE nome = ?", ("Mario",))
        self.assertEqual(member['email'], "mario@new.com")
    
    def test_delete_member_soft_delete(self):
        """Test soft delete (setting deleted_at)."""
        # Insert member
        exec_query(
            "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
            ("Mario", "Rossi", 1)
        )
        
        # Soft delete
        exec_query(
            "UPDATE soci SET deleted_at = datetime('now') WHERE nome = ?",
            ("Mario",)
        )
        
        # Verify deleted_at is set
        member = fetch_one("SELECT * FROM soci WHERE nome = ?", ("Mario",))
        self.assertIsNotNone(member['deleted_at'])
        
        # Verify not in active list
        active_members = fetch_all("SELECT * FROM soci WHERE deleted_at IS NULL")
        self.assertEqual(len(active_members), 0)


class TestDatabaseTransactions(unittest.TestCase):
    """Test transaction handling."""
    
    def setUp(self):
        """Create temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        set_db_path(self.db_path)
        init_db()
    
    def tearDown(self):
        """Clean up temporary database."""
        try:
            os.unlink(self.db_path)
        except Exception:
            pass
    
    def test_context_manager_commit(self):
        """Test that context manager commits on success."""
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
                ("Mario", "Rossi", 1)
            )
        
        # Verify data was committed
        member = fetch_one("SELECT * FROM soci WHERE nome = ?", ("Mario",))
        self.assertIsNotNone(member)
    
    def test_context_manager_rollback(self):
        """Test that context manager rolls back on error."""
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
                    ("Mario", "Rossi", 1)
                )
                # Force an error
                raise Exception("Test error")
        except Exception:
            pass
        
        # Verify data was rolled back
        members = fetch_all("SELECT * FROM soci")
        self.assertEqual(len(members), 0)


class TestDatabaseConstraints(unittest.TestCase):
    """Test database constraints and integrity."""
    
    def setUp(self):
        """Create temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        set_db_path(self.db_path)
        init_db()
    
    def tearDown(self):
        """Clean up temporary database."""
        try:
            os.unlink(self.db_path)
        except Exception:
            pass
    
    def test_unique_matricola_constraint(self):
        """Test that matricola must be unique."""
        # Insert first member with matricola
        exec_query(
            "INSERT INTO soci (nome, cognome, matricola, attivo) VALUES (?, ?, ?, ?)",
            ("Mario", "Rossi", "001", 1)
        )
        
        # Try to insert duplicate matricola
        with self.assertRaises(DatabaseIntegrityError):
            exec_query(
                "INSERT INTO soci (nome, cognome, matricola, attivo) VALUES (?, ?, ?, ?)",
                ("Luigi", "Verdi", "001", 1)
            )
    
    def test_foreign_key_constraint(self):
        """Test foreign key constraint on documenti."""
        # Try to insert document for non-existent member - should raise DatabaseIntegrityError
        with self.assertRaises(DatabaseIntegrityError):
            add_documento(
                socio_id=99999,
                nome_file="test.pdf",
                percorso="/path/to/test.pdf",
                tipo="privacy"
            )
    
    def test_cascade_delete(self):
        """Test that deleting member cascades to documents."""
        # Insert member
        exec_query(
            "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
            ("Mario", "Rossi", 1)
        )
        
        # Get member ID
        member = fetch_one("SELECT id FROM soci WHERE nome = ?", ("Mario",))
        member_id = member['id']
        
        # Add document
        add_documento(
            socio_id=member_id,
            nome_file="test.pdf",
            percorso="/path/to/test.pdf",
            tipo="privacy"
        )
        
        # Verify document exists
        docs = get_documenti(member_id)
        self.assertEqual(len(docs), 1)
        
        # Delete member
        exec_query("DELETE FROM soci WHERE id = ?", (member_id,))
        
        # Verify document was also deleted (cascade)
        docs = get_documenti(member_id)
        self.assertEqual(len(docs), 0)


class TestDocumentManagement(unittest.TestCase):
    """Test document management functions."""
    
    def setUp(self):
        """Create temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        set_db_path(self.db_path)
        init_db()
        
        # Create test member
        exec_query(
            "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
            ("Mario", "Rossi", 1)
        )
        self.member = fetch_one("SELECT id FROM soci WHERE nome = ?", ("Mario",))
        self.member_id = self.member['id']
    
    def tearDown(self):
        """Clean up temporary database."""
        try:
            os.unlink(self.db_path)
        except Exception:
            pass
    
    def test_add_document(self):
        """Test adding a document."""
        doc_id = add_documento(
            socio_id=self.member_id,
            nome_file="privacy.pdf",
            percorso="/docs/privacy.pdf",
            tipo="privacy"
        )
        
        self.assertIsNotNone(doc_id)
        assert doc_id is not None  # Type narrowing for mypy/pylance
        self.assertGreater(doc_id, 0)
        
        # Verify document was added
        docs = get_documenti(self.member_id)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['nome_file'], "privacy.pdf")
        self.assertEqual(docs[0]['tipo'], "privacy")
    
    def test_get_multiple_documents(self):
        """Test getting multiple documents."""
        # Add multiple documents
        add_documento(self.member_id, "doc1.pdf", "/path/doc1.pdf", "privacy")
        add_documento(self.member_id, "doc2.pdf", "/path/doc2.pdf", "carta_identita")
        add_documento(self.member_id, "doc3.pdf", "/path/doc3.pdf", "altro")
        
        docs = get_documenti(self.member_id)
        self.assertEqual(len(docs), 3)
    
    def test_delete_document(self):
        """Test deleting a document."""
        # Add document
        doc_id = add_documento(
            self.member_id,
            "test.pdf",
            "/path/test.pdf",
            "privacy"
        )
        
        self.assertIsNotNone(doc_id)
        assert doc_id is not None  # Type narrowing
        
        # Delete document
        result = delete_documento(doc_id)
        self.assertTrue(result)
        
        # Verify deleted
        docs = get_documenti(self.member_id)
        self.assertEqual(len(docs), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
