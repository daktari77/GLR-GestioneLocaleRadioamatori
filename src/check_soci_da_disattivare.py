#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script per confrontare soci nel database con file ARI ufficiale
e identificare soci da disattivare
"""

import sqlite3
import csv
import os

# Leggi nominativi dal file CSV ufficiale ARI
nominativi_ari = set()
csv_path = 'CVS/soci_merged_import.csv'

if not os.path.exists(csv_path):
    print(f"Errore: File {csv_path} non trovato")
    exit(1)

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['nominativo'].strip():
            nominativi_ari.add(row['nominativo'].strip().upper())

print(f'Nominativi nel file ARI ufficiale: {len(nominativi_ari)}')

# Leggi nominativi dal database esistente
db_path = 'data/soci.db'
if not os.path.exists(db_path):
    print(f"Errore: Database {db_path} non trovato")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT id, nominativo, nome, cognome, attivo 
    FROM soci 
    WHERE nominativo IS NOT NULL AND nominativo != ''
""")
soci_db = cursor.fetchall()

print(f'Soci nel database con nominativo: {len(soci_db)}')

# Trova soci nel DB ma NON nel file ARI
soci_non_in_ari = []
for socio in soci_db:
    nom = socio['nominativo'].strip().upper()
    if nom and nom not in nominativi_ari:
        soci_non_in_ari.append({
            'id': socio['id'],
            'nominativo': socio['nominativo'],
            'nome': socio['nome'] or '',
            'cognome': socio['cognome'] or '',
            'attivo': socio['attivo']
        })

conn.close()

print(f'\n{"="*80}')
print(f'=== SOCI DA DISATTIVARE ===')
print(f'{"="*80}')
print(f'Trovati {len(soci_non_in_ari)} soci nel database che NON sono nel file ufficiale ARI\n')

if soci_non_in_ari:
    print(f'{"ID":4} {"Nominativo":12} {"Nome":20} {"Cognome":20} {"Attivo":6}')
    print('-' * 80)
    for socio in soci_non_in_ari:
        attivo_status = 'SI' if socio['attivo'] in [1, '1', 'Si', 'Sì'] else 'NO'
        nome_display = socio['nome'][:18] if len(socio['nome']) > 18 else socio['nome']
        cognome_display = socio['cognome'][:18] if len(socio['cognome']) > 18 else socio['cognome']
        print(f'{socio["id"]:4} {socio["nominativo"]:12} {nome_display:20} {cognome_display:20} {attivo_status:6}')
    
    print(f'\n⚠️  ATTENZIONE: Questi {len(soci_non_in_ari)} soci dovrebbero essere marcati come NON ATTIVI')
    print(f'    prima di procedere con l\'importazione del file ARI ufficiale.')
    print(f'\nVuoi procedere con la disattivazione automatica? (si/no)')
else:
    print('✓ Tutti i soci nel database sono presenti nel file ARI ufficiale')
    print('  Nessuna disattivazione necessaria.')
