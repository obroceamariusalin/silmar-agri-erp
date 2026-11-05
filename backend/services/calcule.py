"""Calcule cu precizie exactă (Decimal) pentru suprafețe, cantități și contracte."""
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from config import KG_PER_HA

HA = Decimal("0.0001")   # 1 mp
KG = Decimal("0.01")
ZERO = Decimal("0")


def to_decimal(valoare) -> Decimal:
    """None / valori invalide -> 0. Float-urile trec prin str() ca să nu importe zgomotul binar."""
    if valoare is None:
        return ZERO
    if isinstance(valoare, Decimal):
        return valoare
    try:
        return Decimal(str(valoare))
    except Exception:
        return ZERO


def rotunjeste_ha(valoare) -> Decimal:
    return to_decimal(valoare).quantize(HA, rounding=ROUND_HALF_UP)


def rotunjeste_kg(valoare) -> Decimal:
    return to_decimal(valoare).quantize(KG, rounding=ROUND_HALF_UP)


def suprafata_totala(terenuri: Iterable) -> Decimal:
    return rotunjeste_ha(sum((to_decimal(t.suprafata_ha) for t in terenuri), ZERO))


def ha_in_mp(ha) -> int:
    """0.29 ha -> 2900 mp (vechiul int(0.29*10000) dădea 2899)."""
    return int((to_decimal(ha) * 10000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def kg_datorat(ha: Decimal) -> Decimal:
    return rotunjeste_kg(to_decimal(ha) * KG_PER_HA)


def kg_platit(plati: Iterable, an: int | None = None) -> Decimal:
    return rotunjeste_kg(sum(
        (to_decimal(p.cantitate_kg) for p in plati if an is None or p.anul_agricol == an), ZERO
    ))


def cereala_pentru_an(preferinte: Iterable, an: int) -> str:
    pref = next((p for p in preferinte if p.anul_agricol == an), None)
    return pref.tip_cereala if pref and pref.tip_cereala else "grau"


# --- Contracte ---
_RE_DATA = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})")


def data_contract(nr_data: str | None) -> date | None:
    """Extrage data din "122/23.11.2017" sau "23.11.2017"."""
    if not nr_data:
        return None
    m = _RE_DATA.search(nr_data)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def durata_ani(durata: str | None) -> int | None:
    if not durata:
        return 7
    m = re.search(r"\d+", str(durata))
    return int(m.group()) if m else None


def data_expirare(nr_data: str | None, durata: str | None) -> date | None:
    start, ani = data_contract(nr_data), durata_ani(durata)
    if not start or not ani:
        return None
    try:
        return start.replace(year=start.year + ani)
    except ValueError:  # 29 februarie
        return start.replace(year=start.year + ani, day=28)


def status_contract(nr_data: str | None, durata: str | None, azi: date | None = None) -> str:
    """'activ' | 'expira_curand' (≤ 180 zile) | 'expirat' | 'necunoscut'."""
    exp = data_expirare(nr_data, durata)
    if not exp:
        return "necunoscut"
    azi = azi or date.today()
    if exp < azi:
        return "expirat"
    if (exp - azi).days <= 180:
        return "expira_curand"
    return "activ"


def extrage_localitate(adresa: str | None) -> str:
    if not adresa:
        return ""
    m = re.search(r"(Comuna|Com\.|Mun\.|Municipiul|Ora[sș])\s+([A-ZĂÎÂȘȚa-zăîâșț\-\s]+)", adresa, re.IGNORECASE)
    if m:
        nume = m.group(2).split(",")[0].strip()
        prefix = m.group(1).title().replace("Com.", "Comuna")
        return f"{prefix} {nume}"
    return adresa.split(",")[0].strip()
