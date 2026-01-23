import os
import json
import sqlite3
from paths import get_data_dir, get_log_dir, get_db_path, get_config_path, get_sentinel_path, get_app_state_path
from logging_setup import get_bootstrap_logger

def bootstrap(app_version, schema_version):
    logger = get_bootstrap_logger()
    data_dir = get_data_dir()
    log_dir = get_log_dir()
    db_path = get_db_path()
    config_path = get_config_path()
    sentinel = get_sentinel_path()
    app_state_path = get_app_state_path()

    try:
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)
        logger.info("Cartelle dati e log create/verificate.")

        # Crea DB e schema base
        if not os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("""CREATE TABLE IF NOT EXISTS example (id INTEGER PRIMARY KEY, name TEXT);""")
                cur.execute(f"PRAGMA user_version = {schema_version};")
                conn.commit()
            logger.info("Database e schema base creati.")

        # Crea config di default se mancante
        if not os.path.exists(config_path):
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"app_version": app_version}, f, indent=2)
            logger.info("File di configurazione creato.")

        # Scrivi app_state.json
        app_state = {
            "state": "NORMAL_RUN",
            "app_version": app_version,
            "schema_version": schema_version
        }
        with open(app_state_path, "w", encoding="utf-8") as f:
            json.dump(app_state, f, indent=2)
        logger.info("File app_state.json scritto.")

        # Crea file sentinel SOLO a fine successo
        with open(sentinel, "w") as f:
            f.write("initialized")
        logger.info("File sentinel .initialized creato.")

    except Exception as e:
        logger.critical(f"Errore bootstrap: {e}")
        raise
