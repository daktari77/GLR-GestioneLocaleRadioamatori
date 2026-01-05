# CSV di test (Soci + Magazzino)

Questi file sono inclusi nella portable **seeded** in `data\csv\`.

## Soci

1) Importa base
- Apri: **Soci → Importa CSV**
- Seleziona: `data\csv\soci_base.csv`
- Esegui importazione (inserisce nuovi soci)

2) Importa update
- Ripeti l’import con: `data\csv\soci_update.csv`
- Quando viene chiesto come gestire i duplicati:
  - scegli **No** (decidi caso per caso)
  - poi al primo duplicato scegli **Sì** = “aggiorna solo i campi vuoti”

Risultato atteso: per la matricola `001` vengono valorizzati email e note (nel base l’email è volutamente vuota).

## Magazzino

1) Importa base
- Apri: **Magazzino → Importa**
- Seleziona: `data\csv\magazzino_base.csv`
- Lascia modalità duplicati: **Aggiorna solo i campi vuoti**

2) Importa update
- Ripeti con: `data\csv\magazzino_update.csv`

Risultato atteso: per `INV-0001` viene valorizzata la nota (nel base è volutamente vuota).
