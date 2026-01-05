# GLR – Gestione Locale Radioamatori
## Guida Betatest (v0.4.5a) – 5 Gennaio 2026

Questo documento serve a:
- presentare lo scopo del betatest;
- spiegare come avviare la versione portable in modo sicuro;
- indicare cosa testare e come riportare bug/feedback.

---

## 1) Scopo del betatest

Obiettivo: validare che la release **0.4.5a** sia **stabile** e **distribuibile** per l’uso reale di sezione.

Focus principali:
- affidabilità anagrafica Soci;
- gestione Documenti (import, apertura, riallineamento percorsi);
- Magazzino (beni/prestiti);
- Ponti (repeaters);
- Consiglio Direttivo (riunioni/delibere/verbali/documenti);
- Calendario eventi;
- backup e ripristino.

---

## 2) Requisiti e ambiente

- **Windows 10/11** consigliato.
- Nessuna installazione: si usa l’**EXE portable**.
- Permessi: per usare alcune funzioni (es. scrittura in cartelle protette) può servire avviare in una cartella dove hai diritti di scrittura.

Consiglio: evita di lavorare direttamente su percorsi “sensibili” (Desktop aziendale, cartelle di sistema). Preferisci una cartella tipo:
- `C:\GLR_GestioneSoci\` oppure una chiavetta/drive locale.

---

## 3) Struttura della portable (cartelle importanti)

La portable lavora **nella stessa cartella dell’EXE** e usa tipicamente queste sottocartelle:
- `data\`  → configurazione di sezione e file applicativi
- `data\soci.db` → database principale (SQLite)
- `data\documents\` → documenti soci (per matricola)
- `data\section_docs\` → documenti di sezione
- `backup\` → backup automatici/manuali
- `data\logs\` → log applicazione (se presenti)

Nota: se stai usando una build “seeded” (per test), può esserci una `data\` iniziale senza DB reale.

---

## 4) Prima esecuzione (setup consigliato)

1. Copia la cartella portable in una posizione con permessi di scrittura.
2. Avvia l’EXE.
3. Vai in **Strumenti → Configurazione sezione** e imposta almeno:
   - nome sezione
   - dati di contatto
   - eventuali preferenze (es. categorie documenti sezione)
4. Se devi usare un DB reale:
   - chiudi l’app
   - sostituisci `data\soci.db` con il tuo `soci.db` (facendo prima una copia di sicurezza)
   - riapri l’app

Nota (build di test): nella cartella `data\csv\` trovi dei CSV di esempio per testare **import** e **update** di:
- Soci (`soci_base.csv`, `soci_update.csv`)
- Magazzino (`magazzino_base.csv`, `magazzino_update.csv`)
Vedi anche `data\csv\README_TEST_CSV.md`.

---

## 5) Regole di sicurezza (molto importanti)

- Se stai testando con **dati reali**, prima di iniziare:
  - fai una copia di `data\soci.db`
  - fai una copia di `data\documents\` e `data\section_docs\` (se presenti)
- Evita di fare test “distruttivi” sul DB di produzione.
- Se qualcosa va storto: non insistere. Ferma e segnala.

---

## 6) Cosa testare (checklist)

### A) Soci (anagrafica)
- Ricerca rapida: testo, filtri (attivi/inattivi, privacy, dati mancanti).
- CRUD:
  - inserimento nuovo socio
  - modifica campi chiave
  - eliminazione / cestino / ripristino (se disponibile)
- Validazioni: email, CAP, provincia, date (formato ISO), codici quota.

### B) Documenti
- Apertura tab Documenti.
- Import documenti:
  - import su socio
  - import su sezione
- Apertura file e cartella socio.
- **Riallinea percorsi documenti**:
  - prova scenario “cartella documenti rinominata” (`documents` vs `documenti`)
  - prova con percorsi assoluti se presenti nel DB
  - verifica che dopo il riallineamento la UI si aggiorni senza riavvio

### C) Backup / Ripristino
- Esegui **Backup database** (manuale).
- Verifica presenza backup in `backup\`.
- Se previsto dalle funzioni: prova un ripristino su copia di test.

### D) Magazzino
- Inserimento bene.
- Prestito a socio → verifica stato “in prestito”.
- Registrazione reso.
- Ricerca e filtri.

### E) Ponti
- CRUD ponte / autorizzazioni / storico (se attivi nel pannello).
- Verifica che le date e gli stati risultino coerenti.

### F) Consiglio Direttivo
- Nuova riunione.
- Delibere: crea/modifica/elimina.
- Verbali/documenti: inserimento e visualizzazione.

### G) Calendario
- Nuovo evento.
- Modifica/Elimina.
- Export `.ics` (tutti e singolo).

---

## 7) Come segnalare bug/feedback (senza GitHub)

Se non usi GitHub, va benissimo: usa uno di questi canali alternativi.

### Opzione A) Email (consigliata)
- Invia una mail al **coordinatore del betatest**: iu2glr@yahoo.com
- Oggetto consigliato: `GLR 0.4.5a – Bug – <titolo breve>`
- Nel corpo, usa il template in [docs/BUG_REPORT_TEMPLATE.md](docs/BUG_REPORT_TEMPLATE.md)
- Allega quando possibile:
  - screenshot della schermata
  - `data\logs\` (l’ultimo file di log)
  - se riguarda import: il CSV usato (o un estratto anonimo)

### Opzione B) WhatsApp/Telegram
- Manda messaggio al coordinatore con:
  - titolo breve + passi per riprodurre
  - screenshot
  - (se serve) invio del log `data\logs\...`

### Opzione C) Google Form / Modulo
- Se preferisci un modulo, il coordinatore può fornire un link.
- Anche qui: incolla il template e allega screenshot/log.

---

## 7) Come segnalare un bug (template)

Quando segnali un bug, includi **sempre**:
- Versione: `0.4.5a`
- Build folder (se disponibile): es. `dist_portable_YYYYMMDD_HHMMSS`
- Sistema operativo: es. Windows 10 / Windows 11

### Template segnalazione

**Titolo**: [breve descrizione]

**Passi per riprodurre**:
1.
2.
3.

**Risultato atteso**:

**Risultato ottenuto**:

**Dati usati**:
- DB di test / DB reale (specificare)
- Documenti: sì/no (specificare)

**Allegati utili**:
- screenshot (se UI)
- eventuale log (se presente in `data\logs\`)

---

## 8) Feedback non-bug (migliorie/usabilità)

Per feedback su usabilità o nomi voci:
- indica la schermata (tab/menu)
- proponi testo alternativo
- specifica se è un problema “bloccante” o solo miglioramento.

---

## 9) Contatti e canale di raccolta

(Compilare dal coordinatore del test)
- Referente: …
- Canale: GitHub Issues / email / WhatsApp / altro
- Frequenza report: …

---

## 10) Nota su privacy e responsabilità

I dati dei soci possono essere sensibili. Il betatest deve rispettare le policy interne di sezione e le regole di conservazione. In caso di dubbio, usa un DB anonimo o di test.
