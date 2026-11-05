from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas
from config import COOKIE_NAME, COOKIE_SECURE, KG_PER_HA
from database import get_db
from security import creeaza_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["autentificare"])

# Protecție simplă anti-brute-force: max. 10 încercări greșite / 10 minute / IP
_ESECURI: dict[str, deque] = defaultdict(deque)
_FEREASTRA_SEC, _MAX_ESECURI = 600, 10
_lock = Lock()


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


@router.post("/login", response_model=schemas.UserResponse)
def login(date: schemas.LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip, acum = _ip(request), monotonic()
    with _lock:
        esecuri = _ESECURI[ip]
        while esecuri and acum - esecuri[0] > _FEREASTRA_SEC:
            esecuri.popleft()
        if len(esecuri) >= _MAX_ESECURI:
            raise HTTPException(status_code=429, detail="Prea multe încercări greșite. Încearcă din nou peste câteva minute.")

    user = db.query(models.User).filter(func.lower(models.User.username) == date.username.strip().lower()).first()
    if not user or not user.is_active or not verify_password(date.password, user.password_hash):
        with _lock:
            _ESECURI[ip].append(acum)
        raise HTTPException(status_code=401, detail="Utilizator sau parolă incorectă.")
    with _lock:
        _ESECURI.pop(ip, None)
    token, max_age = creeaza_token(user)
    response.set_cookie(
        COOKIE_NAME, token, max_age=max_age, httponly=True,
        secure=COOKIE_SECURE, samesite="lax", path="/",
    )
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"mesaj": "Te-ai delogat."}


@router.get("/me")
def eu(user: models.User = Depends(get_current_user)):
    return {
        "user": schemas.UserResponse.model_validate(user).model_dump(),
        "config": {"kg_per_ha": float(KG_PER_HA)},
    }
