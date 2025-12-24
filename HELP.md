# GestioneSoci v0.4.2b - Guida rapida

## Avvio
- Windows: apri terminale nella cartella `src` e lancia `python main.py`.
- Verifica che i percorsi dati (soci.db, section_docs, documents) siano accessibili sul disco.

## Operazioni principali
- **Anagrafica soci**: vista principale con soci attivi/disattivi; doppio click per modificare, tasto destro per azioni rapide.
- **Import CSV**: menu Importa > CSV. Usa il preset ARI; controlla anteprima e gli avvisi prima di confermare.
- **Documenti socio**: seleziona un socio > "Documenti". Puoi aggiungere file per categorie catalogate; i file finiscono in `data/documents/<MATRICOLA>/`.
- **Documenti di sezione**: menu Documenti di Sezione; categorie da `documents_catalog.py`. Il cestino è `data/.trash/`.
- **Backup**: menu Backup > Crea/Importa. I backup incrementali sono in `backup/`; usa sempre il pulsante Importa per ripristinare.
  - **Backup on demand**: apri il menu Backup > "Crea archivio dati" (oppure premi `Ctrl+B`). L'app verifica `data/soci.db`, duplica l'intera cartella `data/` e genera un archivio ZIP in `backup/[YYYYMMDD_HHMMSS]_backup.zip`. All'interno dell'archivio trovi `data/` (mirror della cartella originale), `soci.db` (copia coerente del database) e `backup_manifest.json` con i percorsi sorgente. Conserva o sposta questo file ZIP per mantenere uno snapshot completo.
- **Privacy e scadenze**: calcolo automatico da data privacy; formati date ISO `YYYY-MM-DD`.

## Email Wizard
- **Scheda Composizione**: inserisci oggetto, testo (puoi usare template), seleziona destinatari (Attivi o Consiglio Direttivo). "Anteprima destinatari" mostra l'elenco.
- **ODG**: puoi caricare l'ordine del giorno da una riunione CD tramite pulsante dedicato.
- **Invio**:
  - "✓ Crea Email" usa `mailto:` con destinatari in BCC (limiti su URL lunghi).
  - "Salva .eml" esporta una bozza in `data/section_docs/email_eml/`.
  - "Invia con Thunderbird" apre la composizione di Thunderbird con oggetto, corpo e BCC precompilati; se la form è vuota ma hai selezionato un .eml nella scheda "Email salvate", usa i dati di quel file.
- **Scheda Email salvate**: puoi elencare/aprire/eliminare i .eml salvati, aprire la cartella o avviare Thunderbird.

## Preferenze
- Menu Preferenze > "Client posta": imposta il percorso di Thunderbird Portable (oppure lascia vuoto per usare il default in `config.py`).
- Menu Preferenze > "Stato socio": gestisci le voci aggiuntive per lo stato del socio.

## Note d'uso
- Usa sempre caratteri ASCII nei percorsi per evitare problemi con strumenti esterni.
- Le operazioni di scrittura DB sono serializzate; non aprire più istanze dell'app sulla stessa cartella dati.
- Per assistenza o segnalazioni, annota il messaggio d'errore completo e la versione (APP_VERSION/BUILD_ID da schermata principale).
