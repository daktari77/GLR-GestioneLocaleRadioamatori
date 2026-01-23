import sqlite3
import os
from paths import get_db_path
from logging_setup import get_migration_logger

# Registry delle migrazioni: (from_version, to_version, function)
MIGRATIONS = []

def migration(from_version, to_version):
    def decorator(func):
        MIGRATIONS.append((from_version, to_version, func))
        return func
    return decorator

# Esempio di migrazione
@migration(1, 2)
def migrate_1_to_2(conn):
    cur = conn.cursor()
    cur.execute("ALTER TABLE example ADD COLUMN email TEXT;")

def apply_migrations(expected_schema_version):
    logger = get_migration_logger()
    db_path = get_db_path()
    if not os.path.exists(db_path):
        logger.critical("DB non trovato per migrazione.")
        return False

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA user_version;")
        current_version = cur.fetchone()[0]
        logger.info(f"Schema attuale: {current_version}, atteso: {expected_schema_version}")

        try:
            for from_v, to_v, func in sorted(MIGRATIONS):
                if current_version == from_v and to_v <= expected_schema_version:
                    logger.info(f"Migrazione {from_v} -> {to_v} in corso...")
                    with conn:
                        func(conn)
                        conn.execute(f"PRAGMA user_version = {to_v};")
                        logger.info(f"Migrazione {from_v} -> {to_v} completata.")
                    current_version = to_v
            if current_version < expected_schema_version:
                logger.critical("Non tutte le migrazioni applicate.")
                return False
            return True
        except Exception as e:
            logger.critical(f"Errore migrazione: {e}")
            # Stato PARTIAL_INSTALL e blocco avvio
            return False
