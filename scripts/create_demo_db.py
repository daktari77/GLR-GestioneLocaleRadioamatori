# -*- coding: utf-8 -*-
"""Utility script to generate a demo soci.db with fake members."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Dict, Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
DATA_DIR = SRC_DIR / "data"

# Ensure project modules are importable
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database import set_db_path, init_db, exec_query  # type: ignore  # noqa: E402


def _sample_members() -> List[Dict[str, Any]]:
    """Return a curated list of demo members covering common scenarios."""
    current_year = date.today().year
    return [
        {
            "matricola": "DEM001",
            "nominativo": "IU2ALFA",
            "nome": "Luca",
            "cognome": "Bianchi",
            "data_nascita": "1984-02-12",
            "luogo_nascita": "Bergamo",
            "indirizzo": "Via Roma 12",
            "cap": "24121",
            "citta": "Bergamo",
            "provincia": "BG",
            "codicefiscale": "BNCLCU84B12A794D",
            "email": "luca.bianchi@example.com",
            "telefono": "+39 347 1234567",
            "attivo": 1,
            "data_iscrizione": "2018-05-10",
            "delibera_numero": "12/2018",
            "delibera_data": "2018-05-05",
            "note": "Coordinatore attività EMCOM",
            "voto": 1,
            "familiare": "No",
            "socio": "Ordinario",
            "cd_ruolo": "Consigliere",
            "privacy_ok": 1,
            "privacy_data": "2023-03-12",
            "privacy_scadenza": f"{current_year + 1}-03-11",
            "privacy_signed": 1,
            "q0": "52",
            "q1": "52",
        },
        {
            "matricola": "DEM002",
            "nominativo": "IU2BRAVO",
            "nome": "Sara",
            "cognome": "Fontana",
            "data_nascita": "1992-09-04",
            "luogo_nascita": "Milano",
            "indirizzo": "Via delle Magnolie 8",
            "cap": "20133",
            "citta": "Milano",
            "provincia": "MI",
            "codicefiscale": "FNTMRA92P44F205Y",
            "email": "sara.fontana@example.com",
            "telefono": "+39 349 9988776",
            "attivo": 1,
            "data_iscrizione": "2021-09-15",
            "delibera_numero": "21/2021",
            "delibera_data": "2021-09-10",
            "note": "Responsabile formazione neofiti",
            "voto": 1,
            "familiare": "No",
            "socio": "OM Ordinario",
            "privacy_ok": 1,
            "privacy_data": "2024-02-01",
            "privacy_scadenza": f"{current_year + 2}-02-01",
            "privacy_signed": 1,
            "q0": "53",
            "q1": "53",
            "q2": "53",
        },
        {
            "matricola": "DEM003",
            "nominativo": "SWL123",
            "nome": "Davide",
            "cognome": "Conti",
            "data_nascita": "2005-07-18",
            "luogo_nascita": "Lecco",
            "indirizzo": "Via Lago 22",
            "cap": "23900",
            "citta": "Lecco",
            "provincia": "LC",
            "email": "davide.conti@example.com",
            "telefono": "+39 333 1112233",
            "attivo": 1,
            "data_iscrizione": "2023-02-03",
            "note": "Junior SWL, partecipa al progetto scuole",
            "familiare": "Si",
            "socio": "Juniores",
            "privacy_ok": 0,
            "privacy_signed": 0,
            "q0": "94",
        },
        {
            "matricola": "DEM004",
            "nominativo": "ARI-BG",
            "nome": "Associazione Radio Club Bergamo",
            "cognome": "",
            "indirizzo": "Via Hertz 5",
            "cap": "24123",
            "citta": "Bergamo",
            "provincia": "BG",
            "email": "segreteria@aribg.example.com",
            "telefono": "+39 035 123456",
            "attivo": 1,
            "data_iscrizione": "2015-03-01",
            "note": "Radio club satellitare - sezione sperimentale",
            "familiare": "No",
            "socio": "Radio Club",
            "privacy_ok": 1,
            "privacy_signed": 1,
            "q0": "58",
            "q1": "59",
        },
        {
            "matricola": "DEM005",
            "nominativo": "IU2CHARLIE",
            "nome": "Elisa",
            "cognome": "Moretti",
            "data_nascita": "1978-11-29",
            "luogo_nascita": "Brescia",
            "indirizzo": "Via dei Mille 4",
            "cap": "25121",
            "citta": "Brescia",
            "provincia": "BS",
            "codicefiscale": "MRTLSE78S69B157X",
            "email": "elisa.moretti@example.com",
            "telefono": "+39 328 5554433",
            "attivo": 0,
            "data_iscrizione": "2010-04-18",
            "data_dimissioni": "2022-12-31",
            "motivo_uscita": "Trasferimento estero",
            "note": "Ex segretaria di sezione",
            "voto": 1,
            "familiare": "No",
            "socio": "Ordinario",
            "privacy_ok": 1,
            "privacy_data": "2021-01-12",
            "privacy_signed": 1,
            "deleted_at": None,
        },
        {
            "matricola": "DEM006",
            "nominativo": "IU2DELTA",
            "nome": "Riccardo",
            "cognome": "Villa",
            "data_nascita": "1990-01-09",
            "luogo_nascita": "Sondrio",
            "indirizzo": "Via Stelvio 77",
            "cap": "23100",
            "citta": "Sondrio",
            "provincia": "SO",
            "email": "riccardo.villa@example.com",
            "telefono": "+39 347 2220001",
            "attivo": 1,
            "data_iscrizione": "2016-06-07",
            "note": "Referente digital mode",
            "voto": 1,
            "familiare": "No",
            "socio": "Ordinario",
            "privacy_ok": 1,
            "privacy_signed": 1,
            "q0": "74",
            "q1": "75",
        },
        {
            "matricola": "DEM007",
            "nominativo": "IU2ECHO",
            "nome": "Paola",
            "cognome": "Ferri",
            "data_nascita": "1988-04-02",
            "luogo_nascita": "Monza",
            "indirizzo": "Via Brianza 9",
            "cap": "20900",
            "citta": "Monza",
            "provincia": "MB",
            "email": "paola.ferri@example.com",
            "telefono": "+39 320 8899441",
            "attivo": 1,
            "data_iscrizione": "2019-01-14",
            "note": "Tutor corsi CW",
            "familiare": "No",
            "socio": "Ordinario",
            "privacy_ok": 1,
            "privacy_signed": 1,
            "q0": "52",
        },
        {
            "matricola": "DEM008",
            "nominativo": "IU2FOXTROT",
            "nome": "Matteo",
            "cognome": "Locatelli",
            "data_nascita": "1995-12-19",
            "luogo_nascita": "Crema",
            "indirizzo": "Via Manzoni 3",
            "cap": "26013",
            "citta": "Crema",
            "provincia": "CR",
            "email": "matteo.locatelli@example.com",
            "telefono": "+39 331 6677889",
            "attivo": 1,
            "data_iscrizione": "2022-10-05",
            "note": "Team gare ARDF",
            "familiare": "Si",
            "socio": "Familiare",
            "privacy_ok": 0,
            "privacy_signed": 0,
        },
    ]


def populate_demo_members():
    """Wipe soci table and insert demo rows."""
    exec_query("DELETE FROM soci")
    exec_query("DELETE FROM sqlite_sequence WHERE name='soci'")
    members = _sample_members()
    for member in members:
        columns = ", ".join(member.keys())
        placeholders = ", ".join(["?"] * len(member))
        sql = f"INSERT INTO soci ({columns}) VALUES ({placeholders})"
        exec_query(sql, tuple(member.values()))


def main():
    parser = argparse.ArgumentParser(description="Generate a demo soci.db with fake members")
    parser.add_argument(
        "-o",
        "--output",
        default="soci_demo.db",
        help="File name to create inside src/data (default: soci_demo.db)",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite the destination file if it already exists",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    destination = (DATA_DIR / args.output).resolve()
    if destination.exists() and not args.force:
        raise SystemExit(f"Destination {destination} already exists. Use --force to overwrite.")

    if destination.exists():
        destination.unlink()

    set_db_path(str(destination))
    init_db()
    populate_demo_members()
    print(f"Demo database created at {destination}")


if __name__ == "__main__":
    main()
