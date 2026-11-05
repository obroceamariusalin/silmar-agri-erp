"""Arhiva de documente în Cloudinary. Fiecare fișier are public_id = "<arendas_id>_<nume>"."""
import re
import unicodedata

import cloudinary
import cloudinary.api
import cloudinary.uploader

from config import CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)

_TIPURI = ("image", "raw")


def prefix(arendas_id: int) -> str:
    return f"{arendas_id}_"


def nume_sigur(nume_fisier: str) -> tuple[str, str]:
    """'Buletin Ștefan (1).PDF' -> ('Buletin_Stefan_1', 'pdf'). Elimină căi și caractere periculoase."""
    nume_fisier = nume_fisier.replace("\\", "/").rsplit("/", 1)[-1]
    baza, _, ext = nume_fisier.rpartition(".")
    if not baza:
        baza, ext = ext, ""
    baza = unicodedata.normalize("NFKD", baza).encode("ascii", "ignore").decode()
    baza = re.sub(r"[^A-Za-z0-9_-]+", "_", baza).strip("_")[:80] or "document"
    return baza, ext.lower()


def listeaza(arendas_id: int) -> list[dict]:
    fisiere = []
    for tip in _TIPURI:
        rez = cloudinary.api.resources(type="upload", resource_type=tip, prefix=prefix(arendas_id), max_results=100)
        for r in rez.get("resources", []):
            public_id = r["public_id"]
            ext = r.get("format") or (public_id.rsplit(".", 1)[-1] if "." in public_id else "")
            afisat = public_id[len(prefix(arendas_id)):]
            if ext and not afisat.lower().endswith("." + ext.lower()):
                afisat = f"{afisat}.{ext}"
            fisiere.append({
                "public_id": public_id,
                "resource_type": tip,
                "nume": afisat,
                "format": ext,
                "url": r.get("secure_url"),
                "bytes": r.get("bytes", 0),
                "creat_la": r.get("created_at"),
            })
    fisiere.sort(key=lambda f: f.get("creat_la") or "", reverse=True)
    return fisiere


def incarca(arendas_id: int, fisier, nume_fisier: str) -> dict:
    baza, ext = nume_sigur(nume_fisier)
    # Documentele Office merg ca "raw" (păstrând extensia); PDF/imagini ca "image" (previzualizare)
    if ext in {"doc", "docx", "xls", "xlsx"}:
        rez = cloudinary.uploader.upload(fisier, public_id=f"{prefix(arendas_id)}{baza}.{ext}",
                                         resource_type="raw", overwrite=False, unique_filename=False)
    else:
        rez = cloudinary.uploader.upload(fisier, public_id=f"{prefix(arendas_id)}{baza}",
                                         resource_type="image", overwrite=False, unique_filename=False)
    return {"public_id": rez.get("public_id"), "url": rez.get("secure_url")}


def sterge(public_id: str, resource_type: str) -> bool:
    rez = cloudinary.uploader.destroy(public_id, resource_type=resource_type, invalidate=True)
    return rez.get("result") == "ok"


def sterge_tot(arendas_id: int) -> None:
    for tip in _TIPURI:
        cloudinary.api.delete_resources_by_prefix(prefix(arendas_id), resource_type=tip)
