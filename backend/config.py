"""Configurare centralizată. Toate valorile pot fi suprascrise din variabile de mediu / fișier .env."""
import logging
import os
import secrets
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
TEMPLATE_CONTRACT = BASE_DIR / "template_contract.docx"

load_dotenv(BASE_DIR / ".env")

log = logging.getLogger("silmar")


def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


# --- Bază de date ---
DATABASE_URL = _env("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'sql_app.db').as_posix()}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- Autentificare (JWT în cookie httpOnly) ---
SECRET_KEY = _env("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(48)
    log.warning(
        "SECRET_KEY nu este setat: s-a generat unul temporar. "
        "Toți utilizatorii vor fi delogați la repornirea serverului. Setează SECRET_KEY în mediu."
    )
JWT_ALGORITHM = "HS256"
SESSION_HOURS = int(_env("SESSION_HOURS", "168"))  # 7 zile
COOKIE_NAME = "silmar_session"
# Pe Render (HTTPS) cookie-ul trebuie marcat Secure; local (http://127.0.0.1) nu.
COOKIE_SECURE = _env("COOKIE_SECURE", "true" if _env("RENDER") else "false").lower() == "true"

ADMIN_USERNAME = _env("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = _env("ADMIN_PASSWORD")  # dacă lipsește, se generează una și se afișează o singură dată în log
ADMIN_NUME = _env("ADMIN_NUME", "Administrator")

# --- Cloudinary (valorile vechi rămân ca fallback, la cererea proprietarului) ---
CLOUDINARY_CLOUD_NAME = _env("CLOUDINARY_CLOUD_NAME", "dmsgvmhy2")
CLOUDINARY_API_KEY = _env("CLOUDINARY_API_KEY", "615547999745442")
CLOUDINARY_API_SECRET = _env("CLOUDINARY_API_SECRET", "2hSOqmsiV5gbUct_NJwSFxMDWQk")

# --- Reguli de business ---
KG_PER_HA = Decimal(_env("KG_PER_HA", "600"))
FIRMA_NUME = "S.C. SILMAR SOLUTION SRL"
FIRMA_CUI = "49659242"

# --- Limite upload ---
MAX_UPLOAD_MB = int(_env("MAX_UPLOAD_MB", "15"))
EXTENSII_PERMISE = {"pdf", "jpg", "jpeg", "png", "webp", "heic", "doc", "docx", "xls", "xlsx"}
