from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

import models


def query_arendasi(db: Session):
    """Arendașii împreună cu toate relațiile, în 4 interogări fixe (nu 1 + 3×N)."""
    return db.query(models.Arendas).options(
        selectinload(models.Arendas.terenuri),
        selectinload(models.Arendas.plati),
        selectinload(models.Arendas.preferinte),
    )


def arendas_sau_404(db: Session, arendas_id: int) -> models.Arendas:
    om = query_arendasi(db).filter(models.Arendas.id == arendas_id).first()
    if not om:
        raise HTTPException(status_code=404, detail="Arendașul nu a fost găsit.")
    return om


def reincarca(db: Session, arendas_id: int) -> models.Arendas:
    """După commit, expiră cache-ul sesiunii ca relațiile să fie recitite proaspăt."""
    db.expire_all()
    return arendas_sau_404(db, arendas_id)


def nume_fisier_sigur(text: str) -> str:
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")[:60] or "document"
