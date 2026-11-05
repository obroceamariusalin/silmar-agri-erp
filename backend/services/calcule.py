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


def nr_si_data_contract(nr_data: str | None) -> tuple[str, str]:
    """"152/26.04.2024" -> ("152", "26.04.2024"); câmpurile lipsă devin linii punctate."""
    nr, data = "........", "................"
    if nr_data:
        m = _RE_DATA.search(nr_data)
        if m:
            data = f"{int(m.group(1)):02d}.{int(m.group(2)):02d}.{m.group(3)}"
            inainte = nr_data[:m.start()].strip(" /-,")
            if inainte:
                nr = inainte.replace("nr.", "").replace("Nr.", "").strip()
        else:
            nr = nr_data.strip()
    return nr, data


def gen_din_cnp(cnp: str | None) -> tuple[str, str, str]:
    """(domnul/doamna, domiciliat/ă, identificat/ă) după prima cifră a CNP-ului."""
    if cnp and len(cnp) == 13:
        if cnp[0] in "1357":
            return "domnul", "domiciliat", "identificat"
        if cnp[0] in "2468":
            return "doamna", "domiciliată", "identificată"
    return "domnul/doamna", "domiciliat(ă)", "identificat(ă)"


def activ_in_an(om, an: int) -> bool:
    """Un contract reziliat mai contează pentru plăți doar până în anul rezilierii (inclusiv)."""
    if (getattr(om, "stare", None) or "activ") != "reziliat":
        return True
    return om.data_reziliere is not None and om.data_reziliere.year >= an


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
