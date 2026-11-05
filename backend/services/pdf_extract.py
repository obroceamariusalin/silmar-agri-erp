"""Extragerea datelor (nume, adresă, terenuri) dintr-un contract PDF scanat cu text."""
import io
import re

import pdfplumber

from services import calcule

_RE_NUME = re.compile(r"(?:Intre|Între)\s+(?:doamna|domnul)\s+(.*?)\s+domiciliat", re.IGNORECASE)
_RE_ADRESA = re.compile(r"domiciliat[aă]?\s+(?:in|în)\s+(.*?),\s+identificat", re.IGNORECASE)
_RE_TEREN = re.compile(
    r"Tarlaua\s*(\d+).*?parcel[aă]?\s*([\d\/A-Za-z]+).*?suprafa[tțţ]a\s*(?:de)?\s*([\d\s\.,]+)\s*(mp|ha)",
    re.IGNORECASE,
)


def extrage(continut: bytes, max_pagini: int = 30) -> dict:
    bucati = []
    with pdfplumber.open(io.BytesIO(continut)) as pdf:
        for page in pdf.pages[:max_pagini]:
            t = page.extract_text()
            if t:
                bucati.append(t)
    text = " ".join(" ".join(bucati).split())

    nume = _RE_NUME.search(text)
    adresa = _RE_ADRESA.search(text)

    terenuri = []
    for tarla, parcela, valoare_raw, unitate in _RE_TEREN.findall(text):
        valoare = calcule.to_decimal(valoare_raw.replace(" ", "").replace(",", "."))
        if unitate.lower() == "mp":
            valoare = valoare / 10000
        terenuri.append({
            "tarlaua": tarla,
            "parcela": parcela,
            "suprafata_ha": float(calcule.rotunjeste_ha(valoare)),
        })

    return {
        "nume": nume.group(1).strip() if nume else "",
        "adresa": adresa.group(1).strip() if adresa else "",
        "terenuri": terenuri,
        "text_gasit": bool(text),
    }
