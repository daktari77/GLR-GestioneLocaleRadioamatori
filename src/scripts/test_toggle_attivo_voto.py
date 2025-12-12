import os
import sys

# Ensure project src is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import DB_NAME
from database import set_db_path, fetch_one, exec_query

set_db_path(DB_NAME)

print('Using DB:', DB_NAME)
try:
    row = fetch_one("SELECT id, attivo, voto FROM soci WHERE deleted_at IS NULL LIMIT 1")
    if not row:
        print('No member found (or table empty).')
    else:
        mid = row['id']
        before_attivo = row['attivo']
        before_voto = row['voto']
        print(f'Before (id={mid}): attivo={before_attivo}, voto={before_voto}')
        new_attivo = 0 if before_attivo else 1
        new_voto = 0 if before_voto else 1
        exec_query("UPDATE soci SET attivo=?, voto=? WHERE id=?", (new_attivo, new_voto, mid))
        row2 = fetch_one("SELECT id, attivo, voto FROM soci WHERE id=?", (mid,))
        print(f'After  (id={mid}): attivo={row2["attivo"]}, voto={row2["voto"]}')
except Exception as e:
    print('Error during test:', e)
