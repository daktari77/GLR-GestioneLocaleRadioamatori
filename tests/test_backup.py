# -*- coding: utf-8 -*-
"""
Unit tests for v41_backup.py

Tests backup operations: incremental backup, restore, integrity checks.
"""

import unittest
import tempfile
import os
import shutil
import sqlite3
import json
import zipfile
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from backup import (
    backup_incremental,
    restore_from_backup,
    list_backups,
    calculate_db_hash,
    verify_db_integrity,
    get_backup_metadata,
    save_backup_metadata,
    verify_db,
    rebuild_indexes,
    backup_on_demand
)
from database import set_db_path, init_db, exec_query
from exceptions import BackupError, BackupIntegrityError, RestoreError


class TestBackupBasics(unittest.TestCase):
    """Test basic backup operations."""
    
    def setUp(self):
        """Create temporary database and backup directory."""
        # Create temp database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create backup directory
        self.backup_dir = tempfile.mkdtemp()
        
        # Initialize database
        set_db_path(self.db_path)
        init_db()
        
        # Add some test data
        exec_query(
            "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
            ("Mario", "Rossi", 1)
        )
    
    def tearDown(self):
        """Clean up temporary files."""
        try:
            os.unlink(self.db_path)
        except Exception:
            pass
        
        try:
            shutil.rmtree(self.backup_dir)
        except Exception:
            pass
    
    def test_calculate_db_hash(self):
        """Test SHA256 hash calculation."""
        hash1 = calculate_db_hash(self.db_path)
        self.assertIsNotNone(hash1)
        self.assertEqual(len(hash1), 64)  # SHA256 is 64 hex chars
        
        # Same file should have same hash
        hash2 = calculate_db_hash(self.db_path)
        self.assertEqual(hash1, hash2)
    
    def test_hash_changes_with_content(self):
        """Test that hash changes when content changes."""
        hash1 = calculate_db_hash(self.db_path)
        
        # Modify database
        exec_query(
            "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
            ("Luigi", "Verdi", 1)
        )
        
        hash2 = calculate_db_hash(self.db_path)
        self.assertNotEqual(hash1, hash2)
    
    def test_verify_db_integrity(self):
        """Test database integrity check."""
        is_ok, msg = verify_db_integrity(self.db_path)
        self.assertTrue(is_ok)
        # msg is None when OK
        self.assertIsNone(msg)
    
    def test_backup_incremental_creates_backup(self):
        """Test that incremental backup creates a backup file."""
        success, backup_path = backup_incremental(self.db_path, self.backup_dir, force=True)
        
        self.assertTrue(success)
        self.assertIsNotNone(backup_path)
        self.assertTrue(os.path.exists(backup_path))
        
        # Verify backup is valid SQLite database
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        
        self.assertGreater(len(tables), 0)
    
    def test_backup_incremental_skips_unchanged(self):
        """Test that backup is skipped when DB hasn't changed."""
        # First backup
        success1, backup1 = backup_incremental(self.db_path, self.backup_dir, force=True)
        self.assertTrue(success1)
        self.assertIsNotNone(backup1)
        
        # Second backup without changes (should be skipped)
        success2, message2 = backup_incremental(self.db_path, self.backup_dir, force=False)
        self.assertFalse(success2)
        self.assertIn("No changes", message2)
    
    def test_backup_incremental_force_override(self):
        """Test that force=True creates backup even if unchanged."""
        import time
        
        # First backup
        success1, backup1 = backup_incremental(self.db_path, self.backup_dir, force=True)
        self.assertTrue(success1)
        self.assertIsNotNone(backup1)
        
        # Wait 1 second to ensure different timestamp
        time.sleep(1)
        
        # Second backup with force=True (should create new backup)
        success2, backup2 = backup_incremental(self.db_path, self.backup_dir, force=True)
        self.assertTrue(success2)
        self.assertIsNotNone(backup2)
        self.assertNotEqual(backup1, backup2)


class TestBackupMetadata(unittest.TestCase):
    """Test backup metadata management."""
    
    def setUp(self):
        """Create temporary backup directory."""
        self.backup_dir = tempfile.mkdtemp()
        self.metadata_file = os.path.join(self.backup_dir, ".backup_metadata.json")
    
    def tearDown(self):
        """Clean up temporary files."""
        try:
            shutil.rmtree(self.backup_dir)
        except Exception:
            pass
    
    def test_save_and_load_metadata(self):
        """Test saving and loading metadata."""
        test_metadata = {
            "last_backup": "2025-01-21_12-00-00",
            "last_hash": "abc123",
            "backup_count": 5
        }
        
        save_backup_metadata(self.backup_dir, test_metadata)
        # Metadata file uses .backup_meta.json (not .backup_metadata.json)
        metadata_file = os.path.join(self.backup_dir, ".backup_meta.json")
        self.assertTrue(os.path.exists(metadata_file))
        
        loaded_metadata = get_backup_metadata(self.backup_dir)
        self.assertEqual(loaded_metadata, test_metadata)
    
    def test_load_missing_metadata(self):
        """Test loading metadata when file doesn't exist."""
        metadata = get_backup_metadata(self.backup_dir)
        # Returns empty dict when file doesn't exist
        self.assertEqual(metadata, {})


class TestBackupRestore(unittest.TestCase):
    """Test backup restore operations."""
    
    def setUp(self):
        """Create temporary database and backup directory."""
        # Create temp database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create backup directory
        self.backup_dir = tempfile.mkdtemp()
        
        # Initialize database
        set_db_path(self.db_path)
        init_db()
        
        # Add initial data
        exec_query(
            "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
            ("Mario", "Rossi", 1)
        )
        
        # Create backup
        success, self.backup_path = backup_incremental(self.db_path, self.backup_dir, force=True)
        self.assertTrue(success)
        
        # Modify database after backup
        exec_query(
            "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
            ("Luigi", "Verdi", 1)
        )
    
    def tearDown(self):
        """Clean up temporary files."""
        try:
            os.unlink(self.db_path)
        except Exception:
            pass
        
        try:
            shutil.rmtree(self.backup_dir)
        except Exception:
            pass
    
    def test_restore_from_backup(self):
        """Test restoring database from backup."""
        # Verify current state (2 members)
        from database import fetch_all
        members_before = fetch_all("SELECT * FROM soci")
        self.assertEqual(len(members_before), 2)
        
        # Restore from backup
        success, message = restore_from_backup(self.backup_path, self.db_path)
        self.assertTrue(success)
        
        # Verify restored state (1 member)
        set_db_path(self.db_path)
        members_after = fetch_all("SELECT * FROM soci")
        self.assertEqual(len(members_after), 1)
        self.assertEqual(members_after[0]['nome'], "Mario")
    
    def test_restore_creates_safety_backup(self):
        """Test that restore creates a safety backup."""
        # Safety backup is created in the same directory as target DB (not backup_dir)
        db_dir = os.path.dirname(self.db_path)
        files_before = os.listdir(db_dir)
        
        # Restore
        success, message = restore_from_backup(self.backup_path, self.db_path)
        self.assertTrue(success)
        
        # Count files after restore (should have +1 for safety backup in DB directory)
        files_after = os.listdir(db_dir)
        safety_backups = [f for f in files_after if "pre_restore" in f]
        self.assertGreater(len(safety_backups), 0)
    
    def test_restore_corrupted_backup_fails(self):
        """Test that restoring corrupted backup fails."""
        # Create corrupted backup
        corrupted_path = os.path.join(self.backup_dir, "corrupted.db")
        with open(corrupted_path, 'w') as f:
            f.write("NOT A VALID SQLITE DATABASE")
        
        # Try to restore - should return False
        success, message = restore_from_backup(corrupted_path, self.db_path)
        self.assertFalse(success)
        self.assertIn("corrupt", message.lower())


class TestBackupList(unittest.TestCase):
    """Test backup listing operations."""
    
    def setUp(self):
        """Create temporary database and backup directory."""
        # Create temp database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create backup directory
        self.backup_dir = tempfile.mkdtemp()
        
        # Initialize database
        set_db_path(self.db_path)
        init_db()
        
        # Add test data
        exec_query(
            "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
            ("Mario", "Rossi", 1)
        )
        
        # Create multiple backups
        for i in range(3):
            backup_incremental(self.db_path, self.backup_dir, force=True)
            # Modify data for next backup
            exec_query(
                f"INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
                (f"Test{i}", "User", 1)
            )
    
    def tearDown(self):
        """Clean up temporary files."""
        try:
            os.unlink(self.db_path)
        except Exception:
            pass
        
        try:
            shutil.rmtree(self.backup_dir)
        except Exception:
            pass
    
    def test_list_backups(self):
        """Test listing backups."""
        backups = list_backups(self.backup_dir)
        
        # Should have multiple backups (at least 2 created in setUp)
        # Filter only .db files that are not metadata or safety backups
        valid_backups = [
            b for b in backups 
            if b.get('is_valid', False) and 
            'soci_backup_' in b.get('filename', '') and
            'pre_restore' not in b.get('filename', '')
        ]
        self.assertGreaterEqual(len(valid_backups), 1)  # At least 1 backup
        
        # Each backup should have required keys
        for backup in valid_backups:
            self.assertIn('path', backup)
            self.assertIn('filename', backup)
            self.assertIn('created', backup)
            self.assertIn('size', backup)
            self.assertIn('is_valid', backup)
    
    def test_list_backups_sorted_by_date(self):
        """Test that backups are sorted by timestamp (newest first)."""
        backups = list_backups(self.backup_dir)
        valid_backups = [b for b in backups if b.get('is_valid', False)]
        
        if len(valid_backups) >= 2:
            # Timestamps should be in descending order (newest first)
            for i in range(len(valid_backups) - 1):
                self.assertGreaterEqual(
                    valid_backups[i]['created'],
                    valid_backups[i + 1]['created']
                )


class TestOnDemandBackup(unittest.TestCase):
    """Test on-demand full backup workflow."""

    def setUp(self):
        """Prepare temporary data and backup directories."""
        self.temp_root = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_root, "data")
        self.backup_dir = os.path.join(self.temp_root, "backup")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

        # Create database inside data directory
        self.db_path = os.path.join(self.data_dir, "soci.db")
        set_db_path(self.db_path)
        init_db()
        exec_query(
            "INSERT INTO soci (nome, cognome, attivo) VALUES (?, ?, ?)",
            ("Giulia", "Bianchi", 1)
        )

        # Add sample file to data directory
        self.sample_file = os.path.join(self.data_dir, "dummy.txt")
        with open(self.sample_file, 'w', encoding='utf-8') as handle:
            handle.write("sample data")

    def tearDown(self):
        """Clean up temp directories."""
        try:
            shutil.rmtree(self.temp_root)
        except Exception:
            pass

    def test_backup_on_demand_creates_archive(self):
        """Verify that on-demand backup creates a zip archive with expected contents."""
        success, archive_path = backup_on_demand(self.data_dir, self.db_path, self.backup_dir)

        self.assertTrue(success)
        self.assertTrue(archive_path.endswith('.zip'))
        self.assertTrue(os.path.exists(archive_path))

        prefix = Path(archive_path).stem
        expected_data_entry = f"{prefix}/data/dummy.txt"
        expected_db_entry = f"{prefix}/soci.db"
        expected_manifest_entry = f"{prefix}/backup_manifest.json"

        with zipfile.ZipFile(archive_path, 'r') as archive:
            names = archive.namelist()

            self.assertIn(expected_data_entry, names)
            self.assertIn(expected_db_entry, names)
            self.assertIn(expected_manifest_entry, names)



class TestDatabaseUtilities(unittest.TestCase):
    """Test database utility functions."""
    
    def setUp(self):
        """Create temporary database."""
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
    
    def test_verify_db(self):
        """Test database verification wrapper."""
        result = verify_db(self.db_path)
        self.assertTrue(result)
    
    def test_rebuild_indexes(self):
        """Test index rebuild."""
        # Should not raise any errors
        try:
            rebuild_indexes(self.db_path)
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success)


if __name__ == '__main__':
    unittest.main(verbosity=2)
