# -*- coding: utf-8 -*-
"""
Backup operations for Libro Soci

Enhanced with:
- Incremental backup based on SHA256 hash
- Database integrity verification before backup
- Restore functionality with safety backup
- Detailed backup metadata
"""

import os
import re
import shutil
import logging
import hashlib
import sqlite3
import json
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple
from exceptions import BackupError, BackupIntegrityError, RestoreError, DatabaseIntegrityError

logger = logging.getLogger("librosoci")

def calculate_db_hash(db_path: str) -> str:
    """
    Calculate SHA256 hash of database file.
    
    Args:
        db_path: Path to database file
    
    Returns:
        SHA256 hash as hexadecimal string
    """
    sha256 = hashlib.sha256()
    try:
        with open(db_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate hash for {db_path}: {e}")
        return ""

def verify_db_integrity(db_path: str) -> Tuple[bool, Optional[str]]:
    """
    Verify database integrity using PRAGMA integrity_check.
    
    Args:
        db_path: Path to database file
    
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if integrity check passes
        - (False, error_message) if check fails
    """
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == "ok":
            return True, None
        else:
            error_msg = result[0] if result else "Unknown integrity error"
            return False, error_msg
    except Exception as e:
        return False, str(e)

def get_backup_metadata(backup_dir: str) -> Dict:
    """
    Load backup metadata from .backup_meta.json file.
    
    Args:
        backup_dir: Directory containing backups
    
    Returns:
        Dictionary with metadata or empty dict if file doesn't exist
    """
    meta_file = os.path.join(backup_dir, ".backup_meta.json")
    if os.path.exists(meta_file):
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load backup metadata: {e}")
    return {}

def save_backup_metadata(backup_dir: str, metadata: Dict):
    """
    Save backup metadata to .backup_meta.json file.
    
    Args:
        backup_dir: Directory containing backups
        metadata: Metadata dictionary to save
    """
    meta_file = os.path.join(backup_dir, ".backup_meta.json")
    try:
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save backup metadata: {e}")

def backup_incremental(db_path: str, backup_dir: str, max_backups: int = 20, force: bool = False) -> Tuple[bool, str]:
    """
    Create incremental backup only if database has changed.
    
    Args:
        db_path: Path to database file
        backup_dir: Directory to store backups
        max_backups: Maximum number of backups to keep
        force: Force backup even if database hasn't changed
    
    Returns:
        Tuple of (success, message)
        - (True, backup_path) if backup was created
        - (False, reason) if backup was skipped or failed
    """
    try:
        if not os.path.exists(db_path):
            return False, f"Database not found: {db_path}"
        
        os.makedirs(backup_dir, exist_ok=True)
        
        # Verify database integrity before backup
        is_valid, error_msg = verify_db_integrity(db_path)
        if not is_valid:
            logger.error(f"Database integrity check failed: {error_msg}")
            return False, f"Database corrupted: {error_msg}"
        
        # Calculate current database hash
        current_hash = calculate_db_hash(db_path)
        if not current_hash:
            return False, "Failed to calculate database hash"
        
        # Load metadata
        metadata = get_backup_metadata(backup_dir)
        last_hash = metadata.get('last_backup_hash')
        
        # Check if backup needed
        if not force and last_hash == current_hash:
            logger.info("Database unchanged since last backup, skipping")
            return False, "No changes detected"
        
        # Create backup with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = f"soci_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        
        shutil.copy2(db_path, backup_path)
        logger.info(f"Incremental backup created: {backup_name}")
        
        # Update metadata
        metadata['last_backup_hash'] = current_hash
        metadata['last_backup_time'] = datetime.now().isoformat()
        metadata['last_backup_file'] = backup_name
        save_backup_metadata(backup_dir, metadata)
        
        # Cleanup old backups
        _cleanup_old_backups(backup_dir, max_backups)
        
        return True, backup_path
        
    except Exception as e:
        logger.error(f"Incremental backup failed: {e}")
        return False, str(e)


def _backup_sqlite_file(source_db: str, destination_db: str):
    """Create a consistent SQLite copy using the backup API."""
    try:
        dest_parent = os.path.dirname(destination_db)
        if dest_parent:
            os.makedirs(dest_parent, exist_ok=True)
        src_conn = sqlite3.connect(source_db)
        dst_conn = sqlite3.connect(destination_db)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()
    except Exception as exc:
        raise BackupError(f"Database backup failed: {exc}")


def backup_on_demand(data_dir: str, db_path: str, backup_dir: str) -> Tuple[bool, str]:
    """Create a full on-demand backup (data directory + DB) and compress it."""
    if not os.path.isdir(data_dir):
        return False, f"Data directory not found: {data_dir}"

    if not os.path.exists(db_path):
        return False, f"Database not found: {db_path}"

    is_valid, error_msg = verify_db_integrity(db_path)
    if not is_valid:
        return False, f"Database corrupted: {error_msg}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{timestamp}_backup"
    target_dir = os.path.join(backup_dir, folder_name)

    try:
        os.makedirs(backup_dir, exist_ok=True)

        if os.path.exists(target_dir):
            return False, f"Backup folder already exists: {target_dir}"

        db_name = os.path.basename(db_path)
        try:
            db_within_data = os.path.commonpath([
                os.path.abspath(db_path),
                os.path.abspath(data_dir)
            ]) == os.path.abspath(data_dir)
        except ValueError:
            db_within_data = False

        ignore_patterns = None
        if db_within_data:
            ignore_patterns = shutil.ignore_patterns(db_name)

        os.makedirs(target_dir)

        data_destination = os.path.join(target_dir, "data")
        shutil.copytree(data_dir, data_destination, ignore=ignore_patterns)

        db_destination = os.path.join(target_dir, db_name)
        _backup_sqlite_file(db_path, db_destination)

        metadata = {
            "created_at": datetime.now().isoformat(),
            "data_source": os.path.abspath(data_dir),
            "db_source": os.path.abspath(db_path),
            "db_hash": calculate_db_hash(db_path),
            "items": {
                "data_dir": "data",
                "database": db_name
            }
        }
        manifest_path = os.path.join(target_dir, "backup_manifest.json")
        with open(manifest_path, 'w', encoding='utf-8') as manifest_file:
            json.dump(metadata, manifest_file, indent=2, ensure_ascii=False)

        archive_path = shutil.make_archive(
            os.path.join(backup_dir, folder_name),
            "zip",
            root_dir=backup_dir,
            base_dir=folder_name
        )

        shutil.rmtree(target_dir, ignore_errors=True)
        logger.info(f"On-demand backup archive created: {archive_path}")
        return True, archive_path

    except Exception as exc:
        logger.error(f"On-demand backup failed: {exc}")
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)
        archive_candidate = os.path.join(backup_dir, f"{folder_name}.zip")
        if os.path.exists(archive_candidate):
            try:
                os.remove(archive_candidate)
            except OSError:
                pass
        return False, str(exc)

def restore_from_backup(backup_path: str, target_db_path: str, create_safety_backup: bool = True) -> Tuple[bool, str]:
    """
    Restore database from backup with safety measures.
    
    Args:
        backup_path: Path to backup file
        target_db_path: Path to restore database to
        create_safety_backup: Create safety backup of current DB before restore
    
    Returns:
        Tuple of (success, message)
    """
    try:
        if not os.path.exists(backup_path):
            return False, f"Backup file not found: {backup_path}"
        
        # Verify backup integrity
        is_valid, error_msg = verify_db_integrity(backup_path)
        if not is_valid:
            logger.error(f"Backup file corrupted: {error_msg}")
            return False, f"Backup corrupted: {error_msg}"
        
        # Create safety backup of current database
        safety_backup_path = None
        if create_safety_backup and os.path.exists(target_db_path):
            safety_backup_path = f"{target_db_path}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                shutil.copy2(target_db_path, safety_backup_path)
                logger.info(f"Safety backup created: {safety_backup_path}")
            except Exception as e:
                logger.warning(f"Failed to create safety backup: {e}")
                # Continue anyway
        
        # Restore database
        shutil.copy2(backup_path, target_db_path)
        logger.info(f"Database restored from {backup_path}")
        
        # Verify restored database
        is_valid, error_msg = verify_db_integrity(target_db_path)
        if not is_valid:
            # Restore failed, try to recover from safety backup
            if safety_backup_path and os.path.exists(safety_backup_path):
                logger.error("Restored database corrupted, reverting to safety backup")
                shutil.copy2(safety_backup_path, target_db_path)
                return False, f"Restore failed and reverted: {error_msg}"
            return False, f"Restore failed: {error_msg}"
        
        return True, f"Successfully restored from {os.path.basename(backup_path)}"
        
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return False, str(e)

def list_backups(backup_dir: str) -> List[Dict]:
    """
    List all available backups with metadata.
    
    Args:
        backup_dir: Directory containing backups
    
    Returns:
        List of dictionaries with backup info:
        - filename: Backup filename
        - path: Full path
        - size: File size in bytes
        - created: Creation timestamp
        - is_valid: Whether integrity check passed
    """
    backups = []
    
    if not os.path.exists(backup_dir):
        return backups
    
    for filename in os.listdir(backup_dir):
        if filename.endswith('.db') and 'backup' in filename.lower():
            full_path = os.path.join(backup_dir, filename)
            try:
                stat = os.stat(full_path)
                is_valid, _ = verify_db_integrity(full_path)
                
                backups.append({
                    'filename': filename,
                    'path': full_path,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_mtime),
                    'is_valid': is_valid
                })
            except Exception as e:
                logger.warning(f"Failed to get info for {filename}: {e}")
    
    # Sort by creation time, newest first
    backups.sort(key=lambda x: x['created'], reverse=True)
    return backups

def _cleanup_old_backups(backup_dir: str, max_backups: int):
    """
    Remove oldest backups keeping only max_backups most recent.
    
    Args:
        backup_dir: Directory containing backups
        max_backups: Maximum number of backups to keep
    """
    try:
        backups = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.db') and ('backup' in filename.lower() or re.match(r'\d{4}-\d{2}-\d{2}.*\.db', filename)):
                full_path = os.path.join(backup_dir, filename)
                try:
                    mtime = os.path.getmtime(full_path)
                    backups.append((mtime, full_path))
                except OSError:
                    continue
        
        # Sort by modification time (oldest first)
        backups.sort(key=lambda x: x[0])
        
        # Remove oldest backups
        while len(backups) > max_backups:
            old_mtime, old_path = backups.pop(0)
            try:
                os.remove(old_path)
                logger.info(f"Old backup removed: {os.path.basename(old_path)}")
            except Exception as e:
                logger.warning(f"Failed to remove old backup {old_path}: {e}")
    
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

def backup_on_startup(db_name: str, backup_dir: str):
    """
    Create a database backup on startup using incremental backup system.
    
    This function now uses the enhanced incremental backup system which:
    - Verifies database integrity before backup
    - Only creates backup if database changed
    - Maintains backup metadata
    - Keeps last 20 backups by default
    
    Args:
        db_name: Path to database file
        backup_dir: Directory to store backups
    """
    try:
        if not os.path.exists(db_name):
            logger.warning("Startup backup not created: database does not exist.")
            return
        
        success, message = backup_incremental(db_name, backup_dir, max_backups=20, force=False)
        
        if success:
            logger.info(f"Startup backup: {message}")
        else:
            logger.info(f"Startup backup skipped: {message}")
            
    except Exception as e:
        logger.error(f"Error during startup backup: {e}")

def verify_db(db_name: str) -> bool:
    """
    Verify database integrity.
    
    Args:
        db_name: Path to database file
    
    Returns:
        True if database is valid, False otherwise
    """
    is_valid, error_msg = verify_db_integrity(db_name)
    if not is_valid:
        logger.error(f"Database verification failed: {error_msg}")
    return is_valid

def rebuild_indexes(db_name: str):
    """
    Rebuild all database indexes.
    
    Args:
        db_name: Path to database file
    """
    try:
        from database import CREATE_INDEXES
        conn = sqlite3.connect(db_name)
        try:
            for idx in CREATE_INDEXES:
                try:
                    conn.execute(idx)
                except Exception as e:
                    logger.warning(f"Index not rebuilt: {e}")
            conn.commit()
            logger.info("Database indexes rebuilt successfully")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error rebuilding indexes: {e}")

