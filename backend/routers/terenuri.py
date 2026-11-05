from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from routers.common import reincarca

router = APIRouter(prefix="/api", tags=["terenuri și plăți"])


@router.patch("/terenuri/{teren_id}", response_model=schemas.ArendasResponse)
def editeaza_teren(teren_id: int, date: schemas.TerenUpdate, db: Session = Depends(get_db)):
    teren = db.get(models.Teren, teren_id)
    if not teren:
        raise HTTPException(status_code=404, detail="Terenul nu a fost găsit.")
    for cheie, valoare in date.model_dump(exclude_unset=True).items():
        setattr(teren, cheie, valoare)
    db.commit()
    return reincarca(db, teren.arendas_id)


@router.delete("/terenuri/{teren_id}", response_model=schemas.ArendasResponse)
def sterge_teren(teren_id: int, db: Session = Depends(get_db)):
    teren = db.get(models.Teren, teren_id)
    if not teren:
        raise HTTPException(status_code=404, detail="Terenul nu a fost găsit.")
    arendas_id = teren.arendas_id
    db.delete(teren)
    db.commit()
    return reincarca(db, arendas_id)


@router.delete("/plati/{plata_id}", response_model=schemas.ArendasResponse)
def sterge_plata(plata_id: int, db: Session = Depends(get_db)):
    plata = db.get(models.Plata, plata_id)
    if not plata:
        raise HTTPException(status_code=404, detail="Plata nu a fost găsită.")
    arendas_id = plata.arendas_id
    db.delete(plata)
    db.commit()
    return reincarca(db, arendas_id)
