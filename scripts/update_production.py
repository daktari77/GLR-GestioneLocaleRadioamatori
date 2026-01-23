
# Script robusto di aggiornamento produzione GestioneSoci
# Esegue backup completo (conserva 5 copie), aggiorna build, DB e documenti

import os
import shutil
from datetime import datetime

PORTABLE_ROOT = r'G:/Il mio Drive/GestioneSoci/GestioneSoci_Current/GRL_0.4.7-TKinter-dev/artifacts/dist_portable'
PROD_ROOT = r'E:/PortableApps/GestioneSoci'
BACKUP_ROOT = r'E:/Backup_GestioneSoci'

# 1. Backup produzione (conserva 5 copie)
def backup_produzione():
    if not os.path.exists(PROD_ROOT):
        print(f'Produzione non trovata: {PROD_ROOT}')
        return None
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    backup_dir = os.path.join(BACKUP_ROOT, f'backup_{ts}')
    print(f'Backup produzione in {backup_dir} ...')
    shutil.copytree(PROD_ROOT, backup_dir)
    # Mantieni solo gli ultimi 5 backup
    backups = sorted([d for d in os.listdir(BACKUP_ROOT) if d.startswith('backup_')])
    while len(backups) > 5:
        to_remove = os.path.join(BACKUP_ROOT, backups.pop(0))
        print(f'Rimuovo backup vecchio: {to_remove}')
        shutil.rmtree(to_remove)
    return backup_dir

# 2. Trova build portatile più recente
def get_latest_build():
    builds = [d for d in os.listdir(PORTABLE_ROOT) if os.path.isdir(os.path.join(PORTABLE_ROOT, d))]
    builds.sort(reverse=True)
    if not builds:
        raise RuntimeError('Nessuna build portatile trovata in artifacts/dist_portable')
    return os.path.join(PORTABLE_ROOT, builds[0])

# 3. Aggiorna produzione con build, DB e documenti
import hashlib

def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def aggiorna_produzione(latest_build):
    print(f'Aggiorno solo EXE e DB se necessario -> {PROD_ROOT}')
    # 1. Trova l'exe nella build
    exe = None
    for f in os.listdir(latest_build):
        if f.lower().endswith('.exe'):
            exe = f
            break
    if not exe:
        print('Nessun file EXE trovato nella build!')
        return
    exe_src = os.path.join(latest_build, exe)
    exe_dst = os.path.join(PROD_ROOT, exe)
    shutil.copy2(exe_src, exe_dst)
    print(f'EXE aggiornato: {exe_src} -> {exe_dst}')

    # 2. Aggiorna DB solo se diverso (hash)
    db_src = os.path.join(latest_build, 'data', 'soci.db')
    db_dst = os.path.join(PROD_ROOT, 'data', 'soci.db')
    if os.path.exists(db_src):
        update_db = True
        if os.path.exists(db_dst):
            if file_hash(db_src) == file_hash(db_dst):
                update_db = False
        if update_db:
            os.makedirs(os.path.dirname(db_dst), exist_ok=True)
            shutil.copy2(db_src, db_dst)
            print(f'DB aggiornato: {db_src} -> {db_dst}')
        else:
            print('DB già aggiornato, nessuna copia necessaria.')
    else:
        print('Attenzione: soci.db non trovato nella build portatile!')
    print('Aggiornamento produzione completato (nessun documento toccato).')

if __name__ == '__main__':
    backup_dir = backup_produzione()
    latest_build = get_latest_build()
    aggiorna_produzione(latest_build)
    print('Procedura terminata. Backup in:', backup_dir)
