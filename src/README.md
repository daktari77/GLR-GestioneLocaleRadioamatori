# GestioneSoci
Software GTK/Tkinter per gestione Libro Soci ARI — import CSV, documenti, CD, duplicati, ecc.

## Script e moduli legacy

Per compatibilità con automazioni pregresse restano in `src/` alcuni moduli "orfani" che non sono caricati dall'applicazione principale ma sono ancora utili per manutenzioni spot:

- `check_soci_da_disattivare.py`: utility CLI per individuare velocemente i soci da disattivare prima delle campagne di rinnovo.
- `documents.py`: vecchio wrapper usato da script esterni per aggiungere/eliminare documenti; il codice nuovo usa `documents_manager.py` ma il file resta per non rompere gli automatismi.
- `models.py`: dataclass `Member` e helper di validazione condivisi con i test (`tests/test_models.py`) e con importatori batch fuori banda.
- `v4_ui/__init__.py` e `v4_ui/styles.py`: mantenuti per chi sviluppa plugin/packaging personalizzati e desidera richiamare `configure_styles()` direttamente senza passare da `main.py`.

Se non servono in produzione possono essere ignorati: sono documentati qui per evitare rimozioni accidentali.

## Branching (betatest vs sviluppo)

- `betatest/0.4.5a`: baseline stabile per i betatester (solo bugfix mirati).
- `dev`: sviluppo continuo (versione `*-dev`).

Regola pratica:
- La portable per i betatester si builda dal branch `betatest/*`.
- Le build di sviluppo si buildano dal branch `dev`.
