"""Silmar Agri ERP — punctul de intrare FastAPI.

Pornire locală:   uvicorn main:app --reload        (din folderul backend/)
Pe Render:        uvicorn main:app --host 0.0.0.0 --port $PORT
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from config import FRONTEND_DIR, log
from migrations import ruleaza_migrari
from routers import arendasi, auth, documente, jurnal, rapoarte, terenuri
from security import get_current_user

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    ruleaza_migrari()
    yield


app = FastAPI(title="Silmar Agri ERP", lifespan=lifespan, docs_url="/api/docs", redoc_url=None,
              openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ------------------------------------------------------------------ Erori -> mesaje clare în română
_ETICHETE = {
    "nume_complet": "Nume", "cnp": "CNP/CUI", "adresa": "Adresă", "tarlaua": "Tarla",
    "parcela": "Parcelă", "suprafata_ha": "Suprafață", "cantitate_kg": "Cantitate",
    "anul_agricol": "An agricol", "tip_cereala": "Cereală", "data_operatiune": "Data",
    "durata_contract": "Durată", "nr_data_contract": "Nr./data contract", "username": "Utilizator",
    "password": "Parolă", "ids": "Selecție", "nume": "Nume", "ha": "Suprafață",
}
_MESAJE = {
    "missing": "Câmp obligatoriu.",
    "int_parsing": "Trebuie să fie un număr întreg.",
    "int_type": "Trebuie să fie un număr întreg.",
    "float_parsing": "Trebuie să fie un număr.",
    "date_from_datetime_parsing": "Dată invalidă.",
    "date_parsing": "Dată invalidă.",
    "literal_error": "Valoare nepermisă.",
    "string_too_short": "Valoare prea scurtă.",
    "string_too_long": "Valoare prea lungă.",
    "too_short": "Selectează cel puțin un element.",
    "json_invalid": "Date trimise invalide.",
}


@app.exception_handler(RequestValidationError)
async def _validare(_: Request, exc: RequestValidationError):
    erori = []
    for e in exc.errors():
        loc = [str(x) for x in e.get("loc", []) if x not in ("body", "query", "path")]
        camp = next((x for x in reversed(loc) if not x.isdigit()), "")
        if e.get("type") == "value_error":
            mesaj = str(e.get("msg", "")).removeprefix("Value error, ")
        else:
            mesaj = _MESAJE.get(e.get("type"), "Valoare invalidă.")
        erori.append({"camp": camp, "cale": ".".join(loc), "mesaj": mesaj})
    primul = erori[0] if erori else {"camp": "", "mesaj": "Date invalide."}
    eticheta = _ETICHETE.get(primul["camp"], "")
    return JSONResponse(status_code=422, content={
        "detail": f"{eticheta}: {primul['mesaj']}" if eticheta else primul["mesaj"],
        "erori": erori,
    })


@app.exception_handler(IntegrityError)
async def _integritate(_: Request, exc: IntegrityError):
    log.warning("IntegrityError: %s", exc.orig)
    return JSONResponse(status_code=409, content={
        "detail": "Operațiunea încalcă o regulă a bazei de date (ex: CNP duplicat sau înregistrare legată)."})


@app.exception_handler(OperationalError)
async def _db_indisponibila(_: Request, exc: OperationalError):
    log.error("Baza de date indisponibilă: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Baza de date nu răspunde. Încearcă din nou în câteva secunde."})


@app.exception_handler(SQLAlchemyError)
async def _db(_: Request, exc: SQLAlchemyError):
    log.exception("Eroare bază de date", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Eroare la baza de date. Operațiunea nu a fost salvată."})


@app.exception_handler(Exception)
async def _neasteptat(_: Request, exc: Exception):
    log.exception("Eroare neașteptată", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "A apărut o eroare neașteptată pe server. Încearcă din nou."})


@app.middleware("http")
async def _antete(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    elif path.endswith((".js", ".css", ".html", "/")) or path == "/sw.js":
        # Revalidare la fiecare încărcare (304 dacă nu s-a schimbat): după deploy nu rămân fișiere vechi în cache
        response.headers["Cache-Control"] = "no-cache"
    return response


# ------------------------------------------------------------------ Rute
app.include_router(auth.router)
_protejat = [Depends(get_current_user)]
for modul in (arendasi, terenuri, documente, rapoarte, jurnal):
    app.include_router(modul.router, dependencies=_protejat)


@app.get("/api/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def _api_inexistent(rest: str):
    raise HTTPException(status_code=404, detail="Ruta API nu există.")


@app.get("/login", include_in_schema=False)
def _login_page():
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/repara-baza", include_in_schema=False)
def _ruta_veche():
    # Ruta veche; migrările rulează acum automat la pornire
    return RedirectResponse("/")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
