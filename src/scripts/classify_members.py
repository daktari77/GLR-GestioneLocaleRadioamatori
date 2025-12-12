#!/usr/bin/env python3
"""Compare CSV and DB to classify members.
Usage:
    python scripts/classify_members.py <csv_path> [--db src/data/soci.db]
Outputs a report to stdout and writes CSV `src/backup/import_classification_<timestamp>.csv`.
"""
import csv
import sqlite3
import sys
import os
from datetime import datetime

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else None
DB_PATH = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', 'data', 'soci.db')
DB_PATH = os.path.normpath(DB_PATH)

if not CSV_PATH:
    print("Usage: python scripts/classify_members.py <csv_path> [db_path]")
    sys.exit(2)

CSV_PATH = os.path.normpath(CSV_PATH)

def read_csv(csv_path):
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def load_db_members(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT id, matricola, nominativo, attivo, voto, deleted_at FROM soci")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


def normalize_mat(m):
    if m is None:
        return ''
    return str(m).strip()


def normalize_voto(v):
    if v is None:
        return ''
    s = str(v).strip()
    if s in ('1','True','true'):
        return '1'
    if s in ('0','False','false'):
        return '0'
    return s


def main():
    csv_rows = read_csv(CSV_PATH)
    db_rows = load_db_members(DB_PATH)

    db_by_m = {normalize_mat(r.get('matricola')): r for r in db_rows if normalize_mat(r.get('matricola'))}
    csv_by_m = {normalize_mat(r.get('matricola')): r for r in csv_rows if normalize_mat(r.get('matricola'))}

    classifications = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_name = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backup', f'import_classification_{timestamp}.csv')
    os.makedirs(os.path.dirname(out_name), exist_ok=True)

    # Classify CSV rows
    for m, crow in csv_by_m.items():
        voto = normalize_voto(crow.get('voto'))
        name = crow.get('nome') or crow.get('nominativo') or ''
        in_db = 'Y' if m in db_by_m else 'N'
        db_att = db_by_m[m]['attivo'] if m in db_by_m else ''
        db_voto = db_by_m[m]['voto'] if m in db_by_m else ''
        if voto == '1':
            cls = 'active_with_voto'
        else:
            cls = 'active_without_voto'
        classifications.append({
            'matricola': m,
            'name_csv': name,
            'in_db': in_db,
            'db_attivo': db_att,
            'db_voto': db_voto,
            'classification': cls
        })

    # Members in DB but not in CSV -> ex_soci (or missing in CSV)
    for m, drow in db_by_m.items():
        if m not in csv_by_m:
            # consider deleted_at as explicit ex-socio marker
            deleted = drow.get('deleted_at')
            cls = 'ex_socio' if deleted else 'missing_in_csv'
            classifications.append({
                'matricola': m,
                'name_csv': drow.get('nominativo') or '',
                'in_db': 'Y',
                'db_attivo': drow.get('attivo'),
                'db_voto': drow.get('voto'),
                'classification': cls
            })

    # Write report
    fieldnames = ['matricola', 'name_csv', 'in_db', 'db_attivo', 'db_voto', 'classification']
    with open(out_name, 'w', newline='', encoding='utf-8') as out:
        w = csv.DictWriter(out, fieldnames=fieldnames)
        w.writeheader()
        for r in classifications:
            w.writerow(r)

    # Print summary
    counts = {}
    for r in classifications:
        counts[r['classification']] = counts.get(r['classification'], 0) + 1
    print('Classification summary:')
    for k, v in counts.items():
        print(f'  {k}: {v}')
    print(f'Report written to: {out_name}')

if __name__ == '__main__':
    main()
