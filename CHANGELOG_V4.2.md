# GestioneSoci v4.2 – Changelog

**Data:** 15 Dicembre 2025  
**Versione:** 4.2 (Inventory & Lending)

---

## 🚀 Highlights

- **Gestione Magazzino** completa per beni di sezione (anagrafica hardware, prestiti, resi).
- **UI dedicata** su notebook principale con filtri stato e riepilogo prestiti.
- **Test automatici** per il nuovo dominio (`tests/test_magazzino_manager.py`).
- **Ambiente di sviluppo ripulito**: nuovo virtualenv + dipendenze reinstallate per esecuzioni stabili.

---

## 🗂️ Database & Business Logic

| Area | Dettagli |
| --- | --- |
| Schema | Tabelle `magazzino_items` e `magazzino_loans` create da `init_db()` con chiavi esterne verso `soci`. |
| Manager | Nuovo modulo [`src/magazzino_manager.py`](src/magazzino_manager.py) con CRUD, validazione campi, normalizzazione date, controllo prestiti attivi e gestione resi. |
| Backup | Nessuna regressione: nuove tabelle incluse automaticamente nei backup incrementali. |

---

## 💻 Interfaccia Utente

| Area | Dettagli |
| --- | --- |
| Tab "Magazzino" | Inserito tra "Documenti" e "Ponti" in [`v4_ui/main_window.py`](src/v4_ui/main_window.py). |
| Pannello dedicato | [`v4_ui/magazzino_panel.py`](src/v4_ui/magazzino_panel.py) con:
- toolbar (nuovo/salva/elimina/refresh, filtri stato, search live)
- griglia oggetti con evidenza prestiti attivi
- form dettagli + note
- sezione prestiti storici con pulsanti "Nuovo prestito" e "Registra reso" |
| Dialoghi | Member picker riusa `soci` attivi; loan/return dialog gestiscono date in formato locale. |

---

## 🧪 Test

| File | Copertura |
| --- | --- |
| [`tests/test_magazzino_manager.py`](tests/test_magazzino_manager.py) | CRUD items, flusso prestito → doppio prestito bloccato → registrazione reso + verifica date. |
| Esecuzione | `python -m venv .venv && .venv\\Scripts\\python.exe tests/run_tests.py test_magazzino_manager` (passati il 15/12/2025). |
| Note | In ambiente di test vengono creati DB temporanei con `init_db()` e un socio sintetico; warning innocuo sui template quando il file è bloccato. |

---

## 🔧 DevOps / Tooling

- Ricreata virtualenv (`python -m venv .venv`) e reinstallato `pyinstaller` per eliminare riferimenti a interpreter mancanti.
- Documentato comando di avvio (`python src/main.py`) dopo la nuova configurazione.

---

## 📌 TODO Futuri

1. **Stato oggetti avanzato** (es. manutenzione, fuori servizio) con timeline.
2. **Reportistica** prestiti/export CSV dal tab Magazzino.
3. **Notifiche** automatiche per prestiti scaduti (integrazione con `calendar_events`).
4. **Test end-to-end** UI per garantire interazione con `MagazzinoPanel`.

---

*_Changelog generato automaticamente dal lavoro di ottimizzazione del 15/12/2025._*
