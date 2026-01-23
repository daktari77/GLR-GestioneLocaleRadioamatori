# GLR - Gestione Locale Radioamatori  
# Procedura GOLD di Ciclo di Vita Applicativo  

---

## 0. Principi Non Negoziabili

Queste regole valgono sempre:

- Mai buildare in produzione  
- Mai sovrascrivere dati o configurazioni  
- Mai fare deploy non reversibile  
- Ogni rilascio deve essere rollbackabile in < 5 minuti  
- Codice, dati e configurazione sono sempre separati  

Violazione di uno solo di questi principi = rilascio NON autorizzato.

---

## 1. Preparazione alla Build

**Obiettivo:** Garantire build pulita, ripetibile e tracciabile.

| Stato Ammesso        | Stato Vietato              |
|---------------------|---------------------------|
| Codice versionato   | Codice non tracciato      |
| Dipendenze fisse    | Dipendenze dinamiche      |
| Ambiente isolato   | Build da ambiente locale  |

**Rischi:**  
Build contaminata, dipendenze non riproducibili, path hardcoded.

**Controlli Obbligatori:**

- Codice su branch stabile/tag  
- `requirements.txt` aggiornato  
- `APP_VERSION` incrementata  
- Changelog aggiornato  
- Nessun file dati/config incluso nella build  

**Checklist:**

- [ ] Checkout tag/branch corretto  
- [ ] Aggiorna versione e changelog  
- [ ] Ricrea ambiente virtuale pulito  
- [ ] Esegui lint e test automatici  
- [ ] Verifica assenza file dati/config nella build  

---

## 2. Build dell’EXE Auto-inizializzante

**Obiettivo:** Generare un EXE onefile che funzioni da cartella vuota.

| Stato Ammesso      | Stato Vietato             |
|-------------------|--------------------------|
| EXE senza dati    | EXE con dati/config      |

**Rischi:**  
Inclusione accidentale di dati, build non portabile.

**Controlli Obbligatori:**

- Esclusione esplicita cartelle dati/config  
- Calcolo hash EXE post-build  
- Test in cartella vuota  

**Checklist:**

- [ ] Build in modalità onefile  
- [ ] Verifica opzioni di esclusione  
- [ ] Calcola hash EXE  
- [ ] Testa avvio in cartella completamente vuota  

---

## 3. Gestione Stati Applicativi all’Avvio (Macchina a Stati)

**Obiettivo:** Determinare formalmente lo stato dell’applicazione e agire di conseguenza.

| Stato             | Descrizione                              | Azione Ammessa        |
|------------------|------------------------------------------|----------------------|
| FIRST_INSTALL    | Nessuna struttura dati presente          | Bootstrap            |
| PARTIAL_INSTALL  | Struttura incompleta/corrotta            | Blocco               |
| UPGRADE          | Schema DB < schema applicazione          | Migrazione           |
| NORMAL_RUN       | Tutto coerente                           | Avvio normale        |
| INCOMPATIBLE     | Schema DB > schema applicazione          | Blocco               |

**Regola di Sicurezza Fondamentale:**

Per ogni **stato vietato**:

- Log critico  
- Messaggio utente chiaro  
- Terminazione immediata dell’applicazione  
- Nessuna operazione distruttiva ammessa  

**Controlli Obbligatori:**

- File sentinel `.initialized`  
- `SCHEMA_VERSION` nel DB  
- `app_state.json` presente e leggibile  

**Checklist:**

- [ ] Rileva presenza cartelle dati  
- [ ] Rileva presenza DB  
- [ ] Leggi SCHEMA_VERSION  
- [ ] Determina stato macchina  
- [ ] Blocca se stato PARTIAL_INSTALL o INCOMPATIBLE  

---

## 4. Bootstrap Sicuro della Prima Installazione

**Obiettivo:** Creare struttura dati e DB in modo idempotente e tracciabile.

| Stato Ammesso     | Stato Vietato             |
|------------------|--------------------------|
| FIRST_INSTALL    | Qualsiasi altro stato    |

**Rischi:**  
Creazione parziale, doppia inizializzazione, sovrascrittura dati.

**Regole Chiave:**

- Bootstrap consentito **solo** in FIRST_INSTALL  
- File `.initialized` creato **solo a fine successo**  
- Mai cancellare dati automaticamente  

**Checklist:**

- [ ] Crea cartelle dati, backup, logs  
- [ ] Crea DB vuoto  
- [ ] Inizializza schema base  
- [ ] Scrivi SCHEMA_VERSION  
- [ ] Scrivi `app_state.json`  
- [ ] Crea `.initialized` SOLO a fine successo  
- [ ] Log completo in `bootstrap.log`  

---

## 5. Protezione da Reinstallazione Accidentale

**Obiettivo:** Impedire perdita dati per reinstallazione sopra ambiente esistente.

**Regole Obbligatorie:**

- Se `data/` esiste e `.initialized` esiste →  
  bootstrap **vietato**
- Se DB esiste ma `.initialized` non esiste →  
  stato = PARTIAL_INSTALL → blocco
- Mai cancellare dati automaticamente  
- Reset dati solo con comando amministrativo esplicito  

**Checklist:**

- [ ] Verifica presenza `.initialized`  
- [ ] Verifica coerenza DB / stato  
- [ ] Blocca ogni tentativo di reinizializzazione  

---

## 6. Migrazioni DB Sicure e Versionate

**Obiettivo:** Aggiornare schema DB senza rischio di corruzione.

| Stato Ammesso | Stato Vietato            |
|--------------|-------------------------|
| UPGRADE      | Migrazione parziale     |

**Regole Fondamentali:**

- Migrazioni separate dal bootstrap  
- Ogni migrazione in transazione  
- Backup DB prima di ogni migrazione  

**Gestione Errore di Migrazione (OBBLIGATORIA):**

Se una migrazione fallisce:

- Rollback transazione  
- NON aggiornare SCHEMA_VERSION  
- Scrivere errore in `migration.log`  
- Impostare stato = PARTIAL_INSTALL  
- Bloccare avvio normale  

**Checklist:**

- [ ] Backup DB  
- [ ] Leggi SCHEMA_VERSION  
- [ ] Applica solo migrazioni necessarie  
- [ ] Ogni step in transazione  
- [ ] Aggiorna SCHEMA_VERSION solo a fine successo  
- [ ] Aggiorna `app_state.json`  
- [ ] Log dettagliato in `migration.log`  

---

## 7. Test Pre-Produzione Completi

**Obiettivo:** Validare tutti i casi critici prima del deploy.

**Test Obbligatori:**

- Cartella completamente vuota  
- Dati presenti, EXE nuovo  
- DB con schema vecchio  
- Simulazione errore bootstrap  
- Simulazione errore migrazione  

**Checklist:**

- [ ] Test FIRST_INSTALL  
- [ ] Test UPGRADE  
- [ ] Test PARTIAL_INSTALL  
- [ ] Verifica nessuna sovrascrittura dati  
- [ ] Verifica log completi  

---

## 8. Strategia di Backup

**Obiettivo:** Rendere ogni rilascio totalmente reversibile.

**Backup Obbligatori Prima di Ogni Deploy:**

- data/  
- config/  
- DB  
- EXE attuale  

Struttura consigliata:

