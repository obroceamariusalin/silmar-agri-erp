"""Reziliere de contract, moștenire și transfer de terenuri între arendatori."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from routers.common import arendas_sau_404, nume_fisier_sigur, reincarca
from routers.rapoarte import DOCX, _fisier
from services import documente

router = APIRouter(prefix="/api/arendasi", tags=["reziliere și moșteniri"])


class TransferRequest(schemas.TransferTerenuri):
    data: date | None = None
    motiv: str | None = None


def _transfera(db: Session, om: models.Arendas, transfer: schemas.TransferTerenuri,
               data: date, motiv: str | None) -> models.Arendas:
    if transfer.nou:
        date_nou = transfer.nou.model_dump()
        if date_nou.get("cnp") and db.query(models.Arendas.id).filter(models.Arendas.cnp == date_nou["cnp"]).first():
            raise HTTPException(status_code=409, detail="CNP-ul noului arendator este deja înregistrat. Alege „arendator existent”.")
        date_nou["durata_contract"] = date_nou.get("durata_contract") or "7"
        nou = models.Arendas(**date_nou, stare="activ", arendas_precedent_id=om.id)
        db.add(nou)
        db.flush()
    else:
        nou = arendas_sau_404(db, transfer.existent_id)
        if nou.id == om.id:
            raise HTTPException(status_code=400, detail="Nu poți transfera terenurile către același arendator.")
        if (nou.stare or "activ") == "reziliat":
            raise HTTPException(status_code=400, detail="Arendatorul ales are contractul reziliat.")

    if transfer.teren_ids is None:
        de_mutat = list(om.terenuri)
    else:
        ids = set(transfer.teren_ids)
        de_mutat = [t for t in om.terenuri if t.id in ids]
        if len(de_mutat) != len(ids):
            raise HTTPException(status_code=400, detail="Unele terenuri selectate nu aparțin acestui arendator.")
    if not de_mutat:
        raise HTTPException(status_code=400, detail="Nu există terenuri de transferat.")

    for t in de_mutat:
        t.proprietar = nou
        db.add(models.IstoricTeren(
            teren_id=t.id, de_la_id=om.id, la_id=nou.id,
            de_la_nume=om.nume_complet, la_nume=nou.nume_complet, data=data, motiv=motiv,
        ))
    return nou


@router.post("/{arendas_id}/reziliere")
def reziliaza(arendas_id: int, cerere: schemas.RezilieRequest, db: Session = Depends(get_db)):
    om = arendas_sau_404(db, arendas_id)
    if (om.stare or "activ") == "reziliat":
        raise HTTPException(status_code=400, detail="Contractul este deja reziliat.")
    data = cerere.data_reziliere or date.today()
    nou = _transfera(db, om, cerere.transfer, data, cerere.motiv_text) if cerere.transfer else None
    om.stare = "reziliat"
    om.data_reziliere = data
    om.motiv_reziliere = cerere.motiv_text
    db.commit()
    rez = {"arendas": schemas.ArendasResponse.model_validate(reincarca(db, arendas_id)).model_dump(mode="json"), "nou": None}
    if nou:
        rez["nou"] = schemas.ArendasResponse.model_validate(reincarca(db, nou.id)).model_dump(mode="json")
    return rez


@router.post("/{arendas_id}/reziliere/act")
def act_reziliere(arendas_id: int, cerere: schemas.RezilieRequest, db: Session = Depends(get_db)):
    """Generează actul adițional (Word). Nu modifică nimic în baza de date."""
    om = arendas_sau_404(db, arendas_id)
    return _fisier(documente.act_reziliere(om, cerere), f"Act_aditional_reziliere_{nume_fisier_sigur(om.nume_complet)}.docx", DOCX)


@router.post("/{arendas_id}/reactivare", response_model=schemas.ArendasResponse)
def reactiveaza(arendas_id: int, db: Session = Depends(get_db)):
    """Anulează marcarea ca reziliat (ex. greșeală). Terenurile transferate NU se mută înapoi automat."""
    om = arendas_sau_404(db, arendas_id)
    om.stare = "activ"
    om.data_reziliere = None
    om.motiv_reziliere = None
    db.commit()
    return reincarca(db, arendas_id)


@router.post("/{arendas_id}/transfer-terenuri")
def transfer_terenuri(arendas_id: int, cerere: TransferRequest, db: Session = Depends(get_db)):
    """Mută una sau mai multe parcele la alt arendator (moștenire parțială, vânzare) fără reziliere."""
    om = arendas_sau_404(db, arendas_id)
    nou = _transfera(db, om, cerere, cerere.data or date.today(), cerere.motiv)
    db.commit()
    return {
        "arendas": schemas.ArendasResponse.model_validate(reincarca(db, arendas_id)).model_dump(mode="json"),
        "nou": schemas.ArendasResponse.model_validate(reincarca(db, nou.id)).model_dump(mode="json"),
    }


class IstoricResponse(BaseModel):
    id: int
    teren_id: int | None
    de_la_id: int | None
    la_id: int | None
    de_la_nume: str | None
    la_nume: str | None
    data: date | None
    motiv: str | None
    tarlaua: str | None = None
    parcela: str | None = None


@router.get("/{arendas_id}/istoric-terenuri", response_model=list[IstoricResponse])
def istoric_terenuri(arendas_id: int, db: Session = Depends(get_db)):
    rez = (db.query(models.IstoricTeren, models.Teren)
           .outerjoin(models.Teren, models.Teren.id == models.IstoricTeren.teren_id)
           .filter((models.IstoricTeren.de_la_id == arendas_id) | (models.IstoricTeren.la_id == arendas_id))
           .order_by(models.IstoricTeren.data.desc(), models.IstoricTeren.id.desc()).all())
    return [IstoricResponse(
        id=i.id, teren_id=i.teren_id, de_la_id=i.de_la_id, la_id=i.la_id, de_la_nume=i.de_la_nume,
        la_nume=i.la_nume, data=i.data, motiv=i.motiv,
        tarlaua=t.tarlaua if t else None, parcela=t.parcela if t else None,
    ) for i, t in rez]


@router.get("/{arendas_id}/contract")
def contract_arendas(arendas_id: int, db: Session = Depends(get_db)):
    """Contract nou (Word) completat cu datele și terenurile din dosar — ex. pentru moștenitor."""
    om = arendas_sau_404(db, arendas_id)
    return _fisier(documente.contract_pentru_arendas(om), f"Contract_{nume_fisier_sigur(om.nume_complet)}.docx", DOCX)
