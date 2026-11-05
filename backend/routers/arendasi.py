from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from config import log
from database import get_db
from routers.common import arendas_sau_404, query_arendasi, reincarca
from services import calcule, cloud

router = APIRouter(prefix="/api/arendasi", tags=["arendași"])


def _verifica_cnp_unic(db: Session, cnp: str | None, exclude_id: int | None = None):
    if not cnp:
        return
    q = db.query(models.Arendas.id).filter(models.Arendas.cnp == cnp)
    if exclude_id:
        q = q.filter(models.Arendas.id != exclude_id)
    existent = q.first()
    if existent:
        raise HTTPException(status_code=409, detail="Acest CNP/CUI este deja înregistrat la alt arendaș.")


@router.get("", response_model=list[schemas.ArendasResponse])
def lista_arendasi(db: Session = Depends(get_db)):
    return query_arendasi(db).order_by(models.Arendas.id).all()


@router.get("/{arendas_id}", response_model=schemas.ArendasResponse)
def detalii_arendas(arendas_id: int, db: Session = Depends(get_db)):
    return arendas_sau_404(db, arendas_id)


@router.post("", response_model=schemas.ArendasResponse, status_code=201)
def adauga_arendas(date: schemas.ArendasCreate, db: Session = Depends(get_db)):
    _verifica_cnp_unic(db, date.cnp)
    om = models.Arendas(**date.model_dump(exclude={"terenuri"}), stare="activ")
    om.durata_contract = om.durata_contract or "7"
    # Terenurile (ex. extrase din PDF) se salvează în aceeași tranzacție: totul sau nimic
    om.terenuri = [models.Teren(**t.model_dump()) for t in date.terenuri]
    db.add(om)
    db.commit()
    return reincarca(db, om.id)


@router.patch("/{arendas_id}", response_model=schemas.ArendasResponse)
def editeaza_arendas(arendas_id: int, date: schemas.ArendasUpdate, db: Session = Depends(get_db)):
    om = arendas_sau_404(db, arendas_id)
    modificari = date.model_dump(exclude_unset=True)
    if "cnp" in modificari:
        _verifica_cnp_unic(db, modificari["cnp"], exclude_id=arendas_id)
    for cheie, valoare in modificari.items():
        setattr(om, cheie, valoare)
    db.commit()
    return reincarca(db, arendas_id)


@router.delete("/{arendas_id}")
def sterge_arendas(arendas_id: int, sterge_documente: bool = False, db: Session = Depends(get_db)):
    om = arendas_sau_404(db, arendas_id)
    nume = om.nume_complet
    db.delete(om)
    db.commit()
    if sterge_documente:
        try:
            cloud.sterge_tot(arendas_id)
        except Exception:
            log.exception("Ștergerea documentelor din cloud a eșuat pentru arendașul %s", arendas_id)
            return {"mesaj": f"Dosarul lui {nume} a fost șters, dar documentele din cloud nu au putut fi șterse."}
    return {"mesaj": f"Dosarul lui {nume} a fost șters."}


# ------------------------------------------------------------------ Terenuri
@router.post("/{arendas_id}/terenuri", response_model=schemas.ArendasResponse, status_code=201)
def adauga_teren(arendas_id: int, teren: schemas.TerenCreate, db: Session = Depends(get_db)):
    arendas_sau_404(db, arendas_id)
    db.add(models.Teren(**teren.model_dump(), arendas_id=arendas_id))
    db.commit()
    return reincarca(db, arendas_id)


# ------------------------------------------------------------------ Plăți
@router.post("/{arendas_id}/plati", response_model=schemas.ArendasResponse, status_code=201)
def inregistreaza_plata(arendas_id: int, plata: schemas.PlataCreate, db: Session = Depends(get_db)):
    om = arendas_sau_404(db, arendas_id)
    date = plata.model_dump()
    if not date["produs"]:
        pref = calcule.cereala_pentru_an(om.preferinte, plata.anul_agricol)
        date["produs"] = pref if pref in ("grau", "porumb") else "grau"
    db.add(models.Plata(**date, arendas_id=arendas_id))
    db.commit()
    return reincarca(db, arendas_id)


@router.get("/{arendas_id}/bilant", response_model=schemas.BilantArendas)
def bilant(arendas_id: int, an: int, db: Session = Depends(get_db)):
    om = arendas_sau_404(db, arendas_id)
    ha = calcule.suprafata_totala(om.terenuri)
    datorat = calcule.kg_datorat(ha)
    platit = calcule.kg_platit(om.plati, an)  # doar plățile anului cerut (înainte se adunau toți anii)
    return {
        "nume_arendas": om.nume_complet,
        "anul_agricol": an,
        "total_hectare": float(ha),
        "total_de_plata_kg": float(datorat),
        "total_achitat_kg": float(platit),
        "rest_de_plata_kg": float(datorat - platit),
        "istoric_plati": [p for p in om.plati if p.anul_agricol == an],
    }


@router.post("/plata-totala-multipla")
def plata_totala_multipla(date: schemas.PlataMultiplaRequest, db: Session = Depends(get_db)):
    oameni = [om for om in query_arendasi(db).filter(models.Arendas.id.in_(set(date.ids))).all()
              if calcule.activ_in_an(om, date.an)]
    resturi = {
        om.id: calcule.kg_datorat(calcule.suprafata_totala(om.terenuri)) - calcule.kg_platit(om.plati, date.an)
        for om in oameni
    }
    in_bani = [om for om in oameni
               if resturi[om.id] > 0 and calcule.cereala_pentru_an(om.preferinte, date.an) == "bani"]
    if in_bani and date.pret_lei_kg is None:
        nume = ", ".join(om.nume_complet for om in in_bani[:5]) + ("…" if len(in_bani) > 5 else "")
        raise HTTPException(status_code=400, detail=f"Introdu prețul pe kg: {len(in_bani)} arendași sunt plătiți în bani ({nume}).")

    procesati = 0
    for om in oameni:
        rest = resturi[om.id]
        if rest <= 0:
            continue
        cereala = calcule.cereala_pentru_an(om.preferinte, date.an)
        plata = models.Plata(
            arendas_id=om.id,
            anul_agricol=date.an,
            cantitate_kg=rest,
            produs=cereala,
            observatii="Plată totală automată (în bloc)",
        )
        if cereala == "bani":
            plata.tip_plata = "bani"
            plata.pret_lei_kg = date.pret_lei_kg
            plata.suma_lei = calcule.rotunjeste_kg(rest * date.pret_lei_kg)
        db.add(plata)
        procesati += 1
    db.commit()
    return {
        "mesaj": f"Plată completă înregistrată pentru {procesati} arendași"
                 + (f" ({len(oameni) - procesati} erau deja achitați)." if len(oameni) > procesati else "."),
        "procesati": procesati,
    }


# ------------------------------------------------------------------ Preferințe cereale
def _seteaza_preferinta(db: Session, arendas_id: int, an: int, cereala: str, existente: dict):
    pref = existente.get((arendas_id, an))
    if pref:
        pref.tip_cereala = cereala
    else:
        db.add(models.PreferintaAnuala(arendas_id=arendas_id, anul_agricol=an, tip_cereala=cereala))


@router.post("/{arendas_id}/preferinte", response_model=schemas.ArendasResponse)
def salveaza_preferinta(arendas_id: int, pref: schemas.PreferintaAnualaCreate, db: Session = Depends(get_db)):
    om = arendas_sau_404(db, arendas_id)
    existente = {(p.arendas_id, p.anul_agricol): p for p in om.preferinte}
    _seteaza_preferinta(db, arendas_id, pref.anul_agricol, pref.tip_cereala, existente)
    db.commit()
    return reincarca(db, arendas_id)


@router.post("/preferinte-multiple")
def preferinte_multiple(date: schemas.PreferinteMultipleRequest, db: Session = Depends(get_db)):
    """O singură cerere pentru N arendași (înainte frontend-ul trimitea N cereri în paralel)."""
    ids = set(date.ids)
    valide = {i for (i,) in db.query(models.Arendas.id).filter(models.Arendas.id.in_(ids))}
    existente = {
        (p.arendas_id, p.anul_agricol): p
        for p in db.query(models.PreferintaAnuala).filter(
            models.PreferintaAnuala.arendas_id.in_(valide),
            models.PreferintaAnuala.anul_agricol == date.anul_agricol,
        )
    }
    for arendas_id in valide:
        _seteaza_preferinta(db, arendas_id, date.anul_agricol, date.tip_cereala, existente)
    db.commit()
    eticheta = {"grau": "grâu", "porumb": "porumb", "bani": "plata în bani"}[date.tip_cereala]
    return {"mesaj": f"Am setat {eticheta} pentru {date.anul_agricol} la {len(valide)} arendași.", "actualizati": len(valide)}
