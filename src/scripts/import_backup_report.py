# -*- coding: utf-8 -*-
"""
Perform a test import onto a copied (backup) SQLite DB and generate a CSV report
listing before/after snapshots for rows inserted or updated.

Usage:
  python scripts/import_backup_report.py [path/to/file.csv]
If no CSV is given, the script will pick the first .csv found in the current directory.

Report written to: src/backup/import_report_<timestamp>.csv
Backup DB created at: src/backup/soci_import_backup_<timestamp>.db
"""

import sys
import os
import shutil
import sqlite3
import json
import csv
from datetime import datetime
from pathlib import Path

# Ensure project src directory is on sys.path so we can import local modules
THIS_DIR = Path(__file__).resolve().parents[1]
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

# Import CSV helpers from project
from csv_import import sniff_delimiter, read_csv_file, auto_detect_mapping, apply_mapping

SRC_DIR = Path(__file__).resolve().parents[1]
BACKUP_DIR = SRC_DIR / 'backup'
DATA_DB = SRC_DIR / 'data' / 'soci.db'

TS = datetime.now().strftime('%Y%m%d_%H%M%S')


def voto_to_bool(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ('1', 'True', 'true'):
        return 1
    if s in ('0', 'False', 'false'):
        return 0
    return None


def is_present(v):
    return v is not None and str(v).strip() != ''


def row_to_dict(row: sqlite3.Row):
    d = {}
    for k in row.keys():
        d[k] = row[k]
    return d


def find_csv_file(arg_path=None):
    if arg_path:
        p = Path(arg_path)
        if p.exists():
            return p
        raise FileNotFoundError(arg_path)
    # search for csv files in SRC_DIR
    for f in sorted(SRC_DIR.glob('*.csv')):
        return f
    raise FileNotFoundError('No CSV file found in src/')


def main(csv_arg=None):
    csv_path = find_csv_file(csv_arg)
    print(f"Using CSV: {csv_path}")

    # prepare backup dir
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # copy DB
    if not DATA_DB.exists():
        raise FileNotFoundError(f"DB not found: {DATA_DB}")
    backup_db = BACKUP_DIR / f'soci_import_backup_{TS}.db'
    shutil.copy2(DATA_DB, backup_db)
    print(f"Backup DB created: {backup_db}")

    # read csv
    delim = sniff_delimiter(str(csv_path))
    headers, rows = read_csv_file(str(csv_path), delim)
    if not headers:
        raise RuntimeError('CSV has no headers or could not be read')

    mapping = auto_detect_mapping(headers)
    # ignore attivo mapping (as wizard does)
    mapping.pop('attivo', None)

    mapped = apply_mapping(rows, mapping)

    # apply attivo rule to mapped rows
    for r in mapped:
        voto = voto_to_bool(r.get('voto'))
        q0 = r.get('q0')
        if voto == 1:
            r['attivo'] = 1
        elif voto == 0:
            r['attivo'] = 1 if is_present(q0) else 0
        else:
            if 'attivo' in r:
                del r['attivo']

    # connect to backup db
    conn = sqlite3.connect(str(backup_db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    report_path = BACKUP_DIR / f'import_report_{TS}.csv'
    changed = []

    # conservative duplicate handling: update only empty fields (like 'update_empty')
    total = len(mapped)
    for i, r in enumerate(mapped):
        # determine keys
        matricola = r.get('matricola')
        cf = r.get('codicefiscale')
        call = r.get('nominativo') or r.get('nominativo2')

        existing = None
        if matricola and str(matricola).strip() != '':
            cur.execute('SELECT * FROM soci WHERE matricola=?', (matricola,))
            existing = cur.fetchone()
        if existing is None and cf and str(cf).strip() != '':
            cur.execute('SELECT * FROM soci WHERE codicefiscale=?', (cf,))
            existing = cur.fetchone()
        if existing is None and call and str(call).strip() != '':
            cur.execute('SELECT * FROM soci WHERE nominativo=?', (call,))
            existing = cur.fetchone()

        if existing:
            before = row_to_dict(existing)
            # prepare updates only where existing value is empty and incoming has value
            update_cols = []
            update_vals = []
            for col, val in r.items():
                if col == 'id':
                    continue
                # existing value
                ev = before.get(col)
                ev_empty = (ev is None or str(ev).strip() == '')
                if val is not None and str(val).strip() != '' and ev_empty:
                    update_cols.append(f"{col}=?")
                    update_vals.append(val)
            if update_cols:
                sql = f"UPDATE soci SET {', '.join(update_cols)} WHERE matricola=?"
                # use matricola if present, else try codicefiscale, else nominativo
                key_val = matricola or before.get('matricola') or before.get('codicefiscale') or before.get('nominativo')
                cur.execute(sql, update_vals + [key_val])
                conn.commit()
                # Re-query to fetch 'after' state; prefer matricola, then codicefiscale, then nominativo
                after_row = None
                if matricola and str(matricola).strip() != '':
                    cur.execute('SELECT * FROM soci WHERE matricola=?', (matricola,))
                    after_row = cur.fetchone()
                if after_row is None and cf and str(cf).strip() != '':
                    cur.execute('SELECT * FROM soci WHERE codicefiscale=?', (cf,))
                    after_row = cur.fetchone()
                if after_row is None and call and str(call).strip() != '':
                    cur.execute('SELECT * FROM soci WHERE nominativo=?', (call,))
                    after_row = cur.fetchone()
                after = row_to_dict(after_row) if after_row else {}
                changed.append(('update', matricola, cf, call, before, after))
        else:
            # insert
            cols = [k for k, v in r.items() if v is not None and str(v).strip() != '']
            if not cols:
                continue
            placeholders = ','.join('?' for _ in cols)
            sql = f"INSERT INTO soci ({', '.join(cols)}) VALUES ({placeholders})"
            params = [r[c] for c in cols]
            cur.execute(sql, params)
            conn.commit()
            # fetch inserted row
            lastrowid = cur.lastrowid
            cur.execute('SELECT * FROM soci WHERE rowid=?', (lastrowid,))
            newrow = cur.fetchone()
            after = row_to_dict(newrow) if newrow else {}
            changed.append(('insert', r.get('matricola'), r.get('codicefiscale'), r.get('nominativo'), {}, after))

    # write report CSV
    fieldnames = ['action', 'matricola', 'codicefiscale', 'nominativo', 'before', 'after']
    with open(report_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for act, mat, cf, call, before, after in changed:
            writer.writerow({
                'action': act,
                'matricola': mat,
                'codicefiscale': cf,
                'nominativo': call,
                'before': json.dumps(before, ensure_ascii=False),
                'after': json.dumps(after, ensure_ascii=False),
            })

    conn.close()
    print(f"Report written: {report_path}")
    print(f"Total changed rows: {len(changed)} / {total}")


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg)
