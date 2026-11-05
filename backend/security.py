"""Hash-uri de parolă (PBKDF2-SHA256, din biblioteca standard) și sesiuni JWT în cookie httpOnly."""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import models
from config import COOKIE_NAME, JWT_ALGORITHM, SECRET_KEY, SESSION_HOURS
from database import get_db

_ITERATII = 390_000


def hash_password(parola: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", parola.encode(), salt, _ITERATII)
    return f"pbkdf2_sha256${_ITERATII}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(parola: str, stocat: str) -> bool:
    try:
        _, iteratii, salt_b64, hash_b64 = stocat.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", parola.encode(), base64.b64decode(salt_b64), int(iteratii))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def creeaza_token(user: models.User) -> tuple[str, int]:
    durata = timedelta(hours=SESSION_HOURS)
    payload = {
        "sub": str(user.id),
        "usr": user.username,
        "exp": datetime.now(timezone.utc) + durata,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM), int(durata.total_seconds())


def _neautentificat(mesaj: str = "Sesiunea a expirat. Te rugăm să te autentifici din nou.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=mesaj)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        # Acceptăm și "Authorization: Bearer ..." (util pentru scripturi / teste)
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    if not token:
        raise _neautentificat("Nu ești autentificat.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _neautentificat()
    user = db.get(models.User, user_id)
    if not user or not user.is_active:
        raise _neautentificat("Contul nu mai este activ.")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Doar administratorii pot face această operațiune.")
    return user
