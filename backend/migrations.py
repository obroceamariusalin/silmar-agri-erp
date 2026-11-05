"""Migrări idempotente rulate la pornire (înlocuiesc ruta /repara-baza).

Fiecare pas verifică starea curentă înainte să modifice ceva, deci se poate rula de oricâte ori,
atât pe SQLite (local) cât și pe PostgreSQL (Render).
"""
import secrets

from sqlalchemy import inspect, text

import models
from config import ADMIN_NUME, ADMIN_PASSWORD, ADMIN_USERNAME, log
from database import Base, SessionLocal, engine
from security import hash_password


def _coloane(insp, tabel: str) -> dict:
    return {c["name"]: c for c in insp.get_columns(tabel)}


def ruleaza_migrari() -> None:
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    dialect = engine.dialect.name

    with engine.begin() as conn:
        col_arendasi = _coloane(insp, "arendasi")
        if "nr_data_contract" not in col_arendasi:
            conn.execute(text("ALTER TABLE arendasi ADD COLUMN nr_data_contract VARCHAR"))
        if "durata_contract" not in col_arendasi:
            conn.execute(text("ALTER TABLE arendasi ADD COLUMN durata_contract VARCHAR DEFAULT '7'"))

        # CI, reziliere, moștenire
        coloane_noi = {
            "ci_seria": "VARCHAR", "ci_numar": "VARCHAR", "ci_eliberat": "VARCHAR", "ci_data": "VARCHAR",
            "stare": "VARCHAR DEFAULT 'activ'", "data_reziliere": "DATE", "motiv_reziliere": "VARCHAR",
            "arendas_precedent_id": "INTEGER REFERENCES arendasi(id) ON DELETE SET NULL",
        }
        for nume, tip in coloane_noi.items():
            if nume not in col_arendasi:
                conn.execute(text(f"ALTER TABLE arendasi ADD COLUMN {nume} {tip}"))

        # Plăți în bani
        col_plati = _coloane(insp, "plati")
        if "tip_plata" not in col_plati:
            conn.execute(text("ALTER TABLE plati ADD COLUMN tip_plata VARCHAR DEFAULT 'natura'"))
        if "suma_lei" not in col_plati:
            conn.execute(text("ALTER TABLE plati ADD COLUMN suma_lei NUMERIC(12,2)"))
        if "pret_lei_kg" not in col_plati:
            conn.execute(text("ALTER TABLE plati ADD COLUMN pret_lei_kg NUMERIC(10,4)"))

        # CNP-urile false "LIPSA-xxxx" devin NULL
        conn.execute(text("UPDATE arendasi SET cnp = NULL WHERE cnp LIKE 'LIPSA%' OR TRIM(cnp) = ''"))

        # Rotunjim zgomotul de virgulă mobilă acumulat în coloanele Float vechi
        conn.execute(text("UPDATE terenuri SET suprafata_ha = ROUND(CAST(suprafata_ha AS NUMERIC), 4) WHERE suprafata_ha IS NOT NULL"))

        if dialect == "postgresql":
            tip_sup = str(_coloane(insp, "terenuri")["suprafata_ha"]["type"]).upper()
            if not tip_sup.startswith("NUMERIC"):
                conn.execute(text(
                    "ALTER TABLE terenuri ALTER COLUMN suprafata_ha TYPE NUMERIC(12,4) "
                    "USING ROUND(suprafata_ha::numeric, 4)"
                ))
                log.info("Migrare: terenuri.suprafata_ha -> NUMERIC(12,4)")
            tip_kg = str(_coloane(insp, "plati")["cantitate_kg"]["type"]).upper()
            if not tip_kg.startswith("NUMERIC"):
                conn.execute(text(
                    "ALTER TABLE plati ALTER COLUMN cantitate_kg TYPE NUMERIC(12,2) "
                    "USING ROUND(cantitate_kg::numeric, 2)"
                ))
                log.info("Migrare: plati.cantitate_kg -> NUMERIC(12,2)")

        # Indexuri pe cheile străine (create_all nu le adaugă pe tabele existente)
        for tabel in ("terenuri", "plati", "preferinte_anuale"):
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{tabel}_arendas_id ON {tabel} (arendas_id)"))

    _creeaza_admin()


def _creeaza_admin() -> None:
    with SessionLocal() as db:
        if db.query(models.User).count() > 0:
            return
        parola = ADMIN_PASSWORD
        generata = parola is None
        if generata:
            parola = secrets.token_urlsafe(10)
        db.add(models.User(
            username=ADMIN_USERNAME,
            nume=ADMIN_NUME,
            password_hash=hash_password(parola),
            is_admin=True,
        ))
        db.commit()
        if generata:
            # Afișat o singură dată, la crearea contului
            print("=" * 60)
            print(f"  Cont admin creat:  utilizator = {ADMIN_USERNAME}")
            print(f"                     parolă     = {parola}")
            print("  Schimb-o cu:  python manage_users.py set-password admin")
            print("=" * 60, flush=True)
        else:
            log.info("Cont admin '%s' creat din ADMIN_PASSWORD.", ADMIN_USERNAME)
