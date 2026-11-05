from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from config import EXTENSII_PERMISE, MAX_UPLOAD_MB, log
from database import get_db
from routers.common import arendas_sau_404
from services import cloud, pdf_extract

router = APIRouter(prefix="/api", tags=["documente"])

# NOTĂ: rutele sunt `def` (nu `async def`), deci FastAPI le rulează într-un thread pool:
# upload-ul în Cloudinary și parsarea PDF nu mai blochează event loop-ul.


def _citeste_limitat(file: UploadFile) -> bytes:
    maxim = MAX_UPLOAD_MB * 1024 * 1024
    continut = file.file.read(maxim + 1)
    if len(continut) > maxim:
        raise HTTPException(status_code=413, detail=f"Fișierul depășește limita de {MAX_UPLOAD_MB} MB.")
    if not continut:
        raise HTTPException(status_code=400, detail="Fișierul este gol.")
    return continut


@router.get("/arendasi/{arendas_id}/documente")
def lista_documente(arendas_id: int):
    try:
        return cloud.listeaza(arendas_id)
    except Exception:
        log.exception("Citirea documentelor din Cloudinary a eșuat")
        raise HTTPException(status_code=502, detail="Nu am putut citi arhiva de documente. Încearcă din nou.")


@router.post("/arendasi/{arendas_id}/documente", status_code=201)
def incarca_document(arendas_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    arendas_sau_404(db, arendas_id)
    _, ext = cloud.nume_sigur(file.filename or "")
    if ext not in EXTENSII_PERMISE:
        raise HTTPException(status_code=400, detail=f"Tip de fișier nepermis. Acceptate: {', '.join(sorted(EXTENSII_PERMISE))}.")
    continut = _citeste_limitat(file)
    try:
        rez = cloud.incarca(arendas_id, continut, file.filename)
    except Exception as e:
        log.exception("Upload Cloudinary eșuat")
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=409, detail="Există deja un document cu acest nume. Redenumește fișierul.")
        raise HTTPException(status_code=502, detail="Încărcarea în cloud a eșuat. Încearcă din nou.")
    return {"mesaj": "Document salvat în arhivă.", **rez}


@router.delete("/arendasi/{arendas_id}/documente")
def sterge_document(arendas_id: int, public_id: str = Query(...), resource_type: str = Query("image")):
    # Se pot șterge DOAR documentele care aparțin acestui arendaș
    if not public_id.startswith(cloud.prefix(arendas_id)) or resource_type not in ("image", "raw"):
        raise HTTPException(status_code=403, detail="Documentul nu aparține acestui arendaș.")
    try:
        ok = cloud.sterge(public_id, resource_type)
    except Exception:
        log.exception("Ștergere Cloudinary eșuată")
        raise HTTPException(status_code=502, detail="Ștergerea din cloud a eșuat. Încearcă din nou.")
    if not ok:
        raise HTTPException(status_code=404, detail="Documentul nu a fost găsit (poate a fost deja șters).")
    return {"mesaj": "Document șters definitiv."}


@router.post("/extrage-contract")
def extrage_contract(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Selectează un fișier PDF.")
    continut = _citeste_limitat(file)
    try:
        rez = pdf_extract.extrage(continut)
    except Exception:
        log.exception("Citire PDF eșuată")
        raise HTTPException(status_code=422, detail="PDF-ul nu a putut fi citit. Este corupt sau protejat cu parolă?")
    if not rez["text_gasit"]:
        raise HTTPException(status_code=422, detail="PDF-ul nu conține text (pare scanat ca imagine). Completează manual.")
    return rez
