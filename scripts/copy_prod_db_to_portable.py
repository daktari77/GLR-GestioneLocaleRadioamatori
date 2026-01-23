# Script di copia/migrazione automatica del DB soci
# Copia il file soci.db dalla produzione corrente nella nuova build portatile

import os
import shutil
from datetime import datetime

# Percorsi
SRC_DB = r'E:/PortableApps/GestioneSoci/data/soci.db'
PORTABLE_ROOT = r'G:/Il mio Drive/GestioneSoci/GestioneSoci_Current/GRL_0.4.7-TKinter-dev/artifacts/dist_portable'

# Trova la build più recente
builds = [d for d in os.listdir(PORTABLE_ROOT) if os.path.isdir(os.path.join(PORTABLE_ROOT, d))]
builds.sort(reverse=True)
if not builds:
    raise RuntimeError('Nessuna build portatile trovata in artifacts/dist_portable')
LATEST_BUILD = os.path.join(PORTABLE_ROOT, builds[0])
DEST_DB = os.path.join(LATEST_BUILD, 'data', 'soci.db')

# Crea la cartella data se non esiste
os.makedirs(os.path.dirname(DEST_DB), exist_ok=True)

# Copia il DB
print(f'Copia {SRC_DB} -> {DEST_DB}')
shutil.copy2(SRC_DB, DEST_DB)
print('Copia completata.')
