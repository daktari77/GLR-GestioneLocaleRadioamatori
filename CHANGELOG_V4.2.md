# GestioneSoci v0.4.2 – Changelog

**Data:** 15 Dicembre 2025  
**Versione:** 0.4.2 (Inventory & Lending)

---

## 0.4.2e · 31 Dicembre 2025

- **Portable**: build con icona (assets/gestionale.ico, generabile da PNG via Pillow) + cleanup script build/deploy.

## 0.4.3a · 31 Dicembre 2025

- TBD

## 0.4.2b · 16 Dicembre 2025

- **Import Magazzino**: controllo preventivo su duplicati/mancanze per `numero inventario` e `marca` con elenco immediato delle righe bloccanti.
- **Esporta errori**: al termine dell'import è possibile salvare un CSV con le righe fallite (numero riga, inventario, marca e motivo) per correggere rapidamente il file sorgente.
- **Ricerca case-insensitive** sugli oggetti magazzino, così un nuovo inserimento non duplica record esistenti che differiscono solo per il casing.
- **Documentazione** aggiornata per chiarire perché alcuni script legacy restano nel repo (`src/README.md`).

---

## 🚀 Highlights

- **Gestione Magazzino** completa per beni di sezione (anagrafica hardware, prestiti, resi).
- **UI dedicata** su notebook principale con filtri stato e riepilogo prestiti.
- **Test automatici** per il nuovo dominio (`tests/test_magazzino_manager.py`).
- **Ambiente di sviluppo ripulito**: nuovo virtualenv + dipendenze reinstallate per esecuzioni stabili.
- **Splash brandizzata** con finestra di caricamento GLR e feed log in tempo reale all'avvio.
- **Documenti di sezione** più affidabili: percorsi assoluti/relativi tracciati e indici TXT rigenerati prima di aprire l'Explorer.

---

## 🗂️ Database & Business Logic

| Area | Dettagli |
| --- | --- |
| Schema | Tabelle `magazzino_items` e `magazzino_loans` create da `init_db()` con chiavi esterne verso `soci`. |
| Manager | Nuovo modulo [`src/magazzino_manager.py`](src/magazzino_manager.py) con CRUD, validazione campi, normalizzazione date, controllo prestiti attivi e gestione resi. |
| Documenti sezione | Refactoring di [`src/section_documents.py`](src/section_documents.py#L1-L220) con salvataggio sia del percorso relativo sia assoluto, rigenerazione dell'indice `elenco_documenti.txt` ([`ensure_section_index_file()`](src/section_documents.py#L155-L212)) e sincronizzazione metadati quando un file manca su disco. |
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
| Splash/Loading | Nuovo modulo [`src/v4_ui/loading_window.py`](src/v4_ui/loading_window.py) che mostra nome app, versione, autore e log di avvio con minimo tempo di permanenza per un avvio più curato. |
| Documenti sezione | [`SectionDocumentPanel`](src/v4_ui/panels.py#L832-L1033) mantiene una mappa dei metadati, rigenera l'indice TXT via `ensure_section_index_file()` e apre la cartella selezionata usando `explorer /select` su Windows o gli equivalenti macOS/Linux. |
| Preferenze | Il notebook del dialogo usa lo stile `PreferencesNotebook` in [`src/v4_ui/preferences_dialog.py`](src/v4_ui/preferences_dialog.py#L1-L120) con tab bold e padding extra per rendere visibile la sezione "Client posta" e il campo del percorso Thunderbird. |

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
