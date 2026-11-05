from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db

router = APIRouter(prefix="/api/jurnal", tags=["jurnal câmp"])


@router.get("", response_model=list[schemas.JurnalCampResponse])
def lista_jurnal(db: Session = Depends(get_db)):
    return db.query(models.JurnalCamp).order_by(models.JurnalCamp.data_operatiune.desc(), models.JurnalCamp.id.desc()).all()


@router.post("", response_model=schemas.JurnalCampResponse, status_code=201)
def adauga_jurnal(intrare: schemas.JurnalCampCreate, db: Session = Depends(get_db)):
    date = intrare.model_dump()
    date["data_operatiune"] = intrare.data_operatiune.isoformat()
    noua = models.JurnalCamp(**date)
    db.add(noua)
    db.commit()
    return noua


@router.delete("/{lucrare_id}")
def sterge_jurnal(lucrare_id: int, db: Session = Depends(get_db)):
    lucrare = db.get(models.JurnalCamp, lucrare_id)
    if not lucrare:
        raise HTTPException(status_code=404, detail="Lucrarea nu a fost găsită.")
    db.delete(lucrare)
    db.commit()
    return {"mesaj": "Lucrare ștearsă."}
