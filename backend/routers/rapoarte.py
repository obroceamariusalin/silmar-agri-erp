from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

import schemas
from database import get_db
from routers.common import nume_fisier_sigur, query_arendasi
from services import documente

router = APIRouter(prefix="/api", tags=["rapoarte"])

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _fisier(continut: bytes, nume: str, media_type: str) -> Response:
    return Response(
        content=continut,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nume}"', "Cache-Control": "no-store"},
    )


def _an_implicit() -> int:
    return date.today().year


@router.get("/rapoarte/tabel-primarie")
def tabel_primarie(db: Session = Depends(get_db)):
    continut = documente.tabel_primarie(query_arendasi(db).all())
    return _fisier(continut, f"Tabel_Primarie_{datetime.now():%Y}.docx", DOCX)


@router.get("/rapoarte/borderou")
def borderou(an: int | None = Query(None, ge=2000, le=2100), db: Session = Depends(get_db)):
    an = an or _an_implicit()
    continut = documente.borderou_excel(query_arendasi(db).all(), an)
    return _fisier(continut, f"Borderou_Arenda_{an}.xlsx", XLSX)


@router.get("/rapoarte/arendasi.csv")
def export_csv(an: int | None = Query(None, ge=2000, le=2100), db: Session = Depends(get_db)):
    an = an or _an_implicit()
    continut = documente.csv_arendasi(query_arendasi(db).all(), an)
    return _fisier(continut, f"Arendasi_{an}.csv", "text/csv; charset=utf-8")


@router.post("/contracte/rapid")
def contract_rapid(date_contract: schemas.ContractRapidCreate):
    continut = documente.contract_rapid(date_contract)
    return _fisier(continut, f"Contract_{nume_fisier_sigur(date_contract.nume)}.docx", DOCX)
