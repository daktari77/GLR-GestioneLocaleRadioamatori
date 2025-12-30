# Path standard (dev / test / produzione)

Questi sono i tre path di riferimento per lavorare su GestioneSoci in modo consistente.

## Sviluppo (repo)
- `G:\Il mio Drive\GestioneSoci\GestioneSoci_Current\GestioneSoci_v0.4.2`

## Test (output portable)
- `G:\Il mio Drive\GestioneSoci\GestioneSoci_Current\GestioneSoci_v0.4.2\artifacts\dist_portable`

## Produzione (installazione portable)
- `E:\PortableApps\GestioneSoci`

## Note operative
- Le build di test vengono create sotto `artifacts\dist_portable\dist_portable_test_*`.
- Il DB in produzione (portable) è tipicamente: `E:\PortableApps\GestioneSoci\data\soci.db`.

## Deploy produzione
- Script: `scripts\deploy_to_production.ps1`
- Fa backup (EXE + DB) e poi aggiorna solo l'EXE in `E:\PortableApps\GestioneSoci`.
