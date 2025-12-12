# -*- coding: utf-8 -*-
"""
Esempio di utilizzo del sistema di backup avanzato

Questo script mostra come utilizzare le nuove funzionalità di backup
implementate in v41_backup.py
"""

import sys
import os

# Aggiungi src al path per import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from v41_backup import (
    backup_incremental,
    restore_from_backup,
    list_backups,
    verify_db_integrity
)

def example_incremental_backup():
    """Esempio: Backup incrementale automatico"""
    print("=" * 60)
    print("ESEMPIO 1: Backup Incrementale")
    print("=" * 60)
    
    db_path = "data/soci.db"
    backup_dir = "backup/"
    
    # Crea backup solo se DB è cambiato
    success, message = backup_incremental(db_path, backup_dir, max_backups=20)
    
    if success:
        print(f"✅ Backup creato: {message}")
    else:
        print(f"ℹ️ Backup saltato: {message}")
    
    print()

def example_forced_backup():
    """Esempio: Backup forzato (ignora hash check)"""
    print("=" * 60)
    print("ESEMPIO 2: Backup Forzato")
    print("=" * 60)
    
    db_path = "data/soci.db"
    backup_dir = "backup/"
    
    # Forza backup anche se DB non è cambiato
    success, message = backup_incremental(
        db_path, 
        backup_dir, 
        max_backups=20,
        force=True  # Forza backup
    )
    
    if success:
        print(f"✅ Backup forzato creato: {message}")
    else:
        print(f"❌ Backup fallito: {message}")
    
    print()

def example_list_backups():
    """Esempio: Lista tutti i backup con validazione"""
    print("=" * 60)
    print("ESEMPIO 3: Lista Backup Disponibili")
    print("=" * 60)
    
    backup_dir = "backup/"
    backups = list_backups(backup_dir)
    
    if not backups:
        print("Nessun backup trovato")
        return
    
    print(f"Trovati {len(backups)} backup:\n")
    
    for i, backup in enumerate(backups, 1):
        size_mb = backup['size'] / (1024 * 1024)
        status = "✅ Valido" if backup['is_valid'] else "❌ Corrotto"
        
        print(f"{i}. {backup['filename']}")
        print(f"   Data: {backup['created'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Dimensione: {size_mb:.2f} MB")
        print(f"   Stato: {status}")
        print()

def example_verify_integrity():
    """Esempio: Verifica integrità database"""
    print("=" * 60)
    print("ESEMPIO 4: Verifica Integrità Database")
    print("=" * 60)
    
    db_path = "data/soci.db"
    
    is_valid, error_msg = verify_db_integrity(db_path)
    
    if is_valid:
        print(f"✅ Database valido: {db_path}")
    else:
        print(f"❌ Database corrotto: {db_path}")
        print(f"   Errore: {error_msg}")
    
    print()

def example_restore_backup():
    """Esempio: Restore da backup con safety backup"""
    print("=" * 60)
    print("ESEMPIO 5: Restore da Backup")
    print("=" * 60)
    
    backup_dir = "backup/"
    target_db = "data/soci.db"
    
    # Lista backup disponibili
    backups = list_backups(backup_dir)
    if not backups:
        print("❌ Nessun backup disponibile per restore")
        return
    
    # Usa il backup più recente (primo della lista)
    latest_backup = backups[0]
    
    print(f"Backup selezionato: {latest_backup['filename']}")
    print(f"Data: {latest_backup['created']}")
    print(f"Valido: {latest_backup['is_valid']}")
    print()
    
    # ATTENZIONE: Questa operazione sovrascrive il DB corrente!
    # In produzione, chiedere conferma all'utente
    
    # Decommentare per eseguire il restore:
    # success, message = restore_from_backup(
    #     latest_backup['path'],
    #     target_db,
    #     create_safety_backup=True
    # )
    # 
    # if success:
    #     print(f"✅ {message}")
    # else:
    #     print(f"❌ {message}")
    
    print("⚠️  Restore commentato per sicurezza")
    print("    Decommentare il codice per eseguire")
    print()

def example_scheduled_backup():
    """Esempio: Backup programmato (da usare con cron/task scheduler)"""
    print("=" * 60)
    print("ESEMPIO 6: Script per Backup Programmato")
    print("=" * 60)
    
    print("""
Script da usare con Windows Task Scheduler o cron:

Windows (Task Scheduler):
1. Apri Task Scheduler
2. Crea Nuova Attività
3. Trigger: Ogni giorno alle 02:00
4. Azione: Esegui programma
   - Programma: python.exe
   - Argomenti: scheduled_backup.py
   - Inizio in: C:\\Path\\To\\GestioneSoci

Linux/Mac (crontab):
```bash
# Backup alle 2:00 ogni notte
0 2 * * * cd /path/to/GestioneSoci && python3 scheduled_backup.py
```

scheduled_backup.py:
```python
import sys
import os
sys.path.insert(0, 'src')

from v41_backup import backup_incremental
import logging

logging.basicConfig(
    filename='logs/scheduled_backup.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

success, message = backup_incremental(
    'data/soci.db',
    'backup/',
    max_backups=30  # Mantieni 30 backup
)

if success:
    logging.info(f"Backup completato: {message}")
else:
    logging.info(f"Backup saltato: {message}")
```
    """)

def example_backup_rotation():
    """Esempio: Gestione rotazione backup"""
    print("=" * 60)
    print("ESEMPIO 7: Strategia Rotazione Backup")
    print("=" * 60)
    
    print("""
Strategia consigliata per rotazione backup:

1. BACKUP GIORNALIERI (ultimi 7 giorni)
   - Eseguiti automaticamente all'avvio
   - max_backups=20 (conserva ultimi 20)
   
2. BACKUP SETTIMANALI (ultimi 4 settimane)
   - Eseguiti ogni domenica
   - Copiare manualmente in folder separato
   
3. BACKUP MENSILI (ultimi 12 mesi)
   - Primo del mese
   - Copiare in folder archivio
   
4. BACKUP ANNUALI (illimitati)
   - Fine anno fiscale
   - Archiviare su storage esterno

Esempio script:
```python
from datetime import datetime
from v41_backup import backup_incremental
import shutil

def smart_backup():
    now = datetime.now()
    
    # Backup standard
    success, backup_path = backup_incremental(
        'data/soci.db',
        'backup/',
        max_backups=20
    )
    
    if not success:
        return
    
    # Backup settimanale (domenica)
    if now.weekday() == 6:  # Domenica
        weekly_dir = 'backup/weekly/'
        os.makedirs(weekly_dir, exist_ok=True)
        shutil.copy2(
            backup_path,
            f"{weekly_dir}weekly_{now.strftime('%Y-%W')}.db"
        )
    
    # Backup mensile (primo del mese)
    if now.day == 1:
        monthly_dir = 'backup/monthly/'
        os.makedirs(monthly_dir, exist_ok=True)
        shutil.copy2(
            backup_path,
            f"{monthly_dir}monthly_{now.strftime('%Y-%m')}.db"
        )
```
    """)

def main():
    """Esegui tutti gli esempi"""
    print("\n" + "=" * 60)
    print("SISTEMA DI BACKUP AVANZATO - Esempi di Utilizzo")
    print("=" * 60 + "\n")
    
    # Esegui esempi in sequenza
    example_incremental_backup()
    example_forced_backup()
    example_list_backups()
    example_verify_integrity()
    example_restore_backup()
    example_scheduled_backup()
    example_backup_rotation()
    
    print("=" * 60)
    print("Fine esempi")
    print("=" * 60)

if __name__ == "__main__":
    main()
