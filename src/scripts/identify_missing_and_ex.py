#!/usr/bin/env python3
"""Identify DB rows that are ex-soci (deleted) or missing in CSV using flexible keys.
Keys considered (in order): matricola, callsign, cf (codice fiscale).
Writes two CSVs into src/backup/: ex_soci_cleaned_<ts>.csv and missing_in_csv_cleaned_<ts>.csv
"""
import csv
import sqlite3
import sys
import os
from datetime import datetime

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else '92123141013182813621016673722328424233.csv'
DB_PATH = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', 'data', 'soci.db')
CSV_PATH = os.path.normpath(CSV_PATH)
DB_PATH = os.path.normpath(DB_PATH)


def read_csv(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        rows = [dict((k.strip(), (v.strip() if v is not None else '')) for k, v in row.items()) for row in r]
    return rows


def load_db(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM soci")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


def key_variants_from_csv_row(r):
    # return a set of normalized keys from CSV row
    keys = set()
    m = (r.get('matricola') or '').strip()
    cs = (r.get('callsign') or '').strip()
    cf = (r.get('cf') or '').strip()
    if m:
        keys.add(('matricola', m))
        # also add zero-stripped variant
        keys.add(('matricola', m.lstrip('0')))
    if cs:
        keys.add(('callsign', cs.upper()))
    if cf:
        keys.add(('cf', cf.upper()))
    return keys


def key_variants_from_db_row(r):
    keys = set()
    m = str(r.get('matricola') or '').strip()
    cs = str(r.get('callsign') or r.get('callsign', '') or '').strip() if 'callsign' in r else ''
    cf = str(r.get('cf') or r.get('codice_fiscale') or r.get('codiceFiscale') or '').strip()
    # Some DBs store callsign under 'callsign' or 'cap' etc. try multiple common names
    # Add variations
    if m:
        keys.add(('matricola', m))
        keys.add(('matricola', m.lstrip('0')))
    if cs:
        keys.add(('callsign', cs.upper()))
    if cf:
        keys.add(('cf', cf.upper()))
    return keys


def main():
    csv_rows = read_csv(CSV_PATH)
    db_rows = load_db(DB_PATH)

    # Build CSV key maps for prioritized matching: cf -> matricola -> callsign
    csv_map = {'cf': {}, 'matricola': {}, 'callsign': {}}
    for r in csv_rows:
        # collect variants
        m = (r.get('matricola') or '').strip()
        cs = (r.get('callsign') or '').strip()
        cf = (r.get('cf') or '').strip()
        if cf:
            csv_map['cf'][cf.upper()] = r
        if m:
            csv_map['matricola'][m] = r
            csv_map['matricola'][m.lstrip('0')] = r
        if cs:
            csv_map['callsign'][cs.upper()] = r

    # Map DB rows to whether they match CSV using priority: cf -> matricola -> callsign
    matched = []
    missing = []
    ex_soci = []

    for r in db_rows:
        # generate primary key values
        cf_vals = []
        m_vals = []
        cs_vals = []
        # try to find cf in known db columns
        cf_val = (r.get('cf') or r.get('codice_fiscale') or r.get('codiceFiscale') or '').strip()
        if cf_val:
            cf_vals.append(cf_val.upper())

        m_val = str(r.get('matricola') or '').strip()
        if m_val:
            m_vals.append(m_val)
            m_vals.append(m_val.lstrip('0'))

        cs_val = (r.get('callsign') or r.get('cap') or '').strip()
        if cs_val:
            cs_vals.append(cs_val.upper())

        found = False
        # priority: cf
        for v in cf_vals:
            if v in csv_map['cf']:
                matched.append(r)
                found = True
                break
        if found:
            continue

        # then matricola
        for v in m_vals:
            if v in csv_map['matricola']:
                matched.append(r)
                found = True
                break
        if found:
            continue

        # then callsign
        for v in cs_vals:
            if v in csv_map['callsign']:
                matched.append(r)
                found = True
                break
        if found:
            continue

        deleted = bool(r.get('deleted_at'))
        if deleted:
            ex_soci.append(r)
        else:
            missing.append(r)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backup')
    os.makedirs(out_dir, exist_ok=True)
    ex_path = os.path.join(out_dir, f'ex_soci_cleaned_{ts}.csv')
    miss_path = os.path.join(out_dir, f'missing_in_csv_cleaned_{ts}.csv')

    def write(path, rows):
        if not rows:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                f.write('')
            return
        keys = sorted(rows[0].keys())
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    write(ex_path, ex_soci)
    write(miss_path, missing)

    print(f'Ex-soci: {len(ex_soci)}, Missing-in-CSV: {len(missing)}')
    print('Ex-soci file:', ex_path)
    print('Missing-in-CSV file:', miss_path)

    # Also print brief lists
    print('\nEx-soci (matricola - nominativo - deleted_at):')
    for r in ex_soci:
        print(r.get('matricola'), '-', r.get('nominativo'), '-', r.get('deleted_at'))

    print('\nMissing in CSV (matricola - nominativo):')
    for r in missing:
        print(r.get('matricola'), '-', r.get('nominativo'))

if __name__ == '__main__':
    main()
