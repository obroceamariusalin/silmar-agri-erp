"""Validări de domeniu (CNP, CUI, suprafețe, tarla/parcelă) folosite de schemele Pydantic."""
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_CHEIE_CNP = "279146358279"
_CHEIE_CUI = "753217532"
_RE_TARLA_PARCELA = re.compile(r"^[0-9A-Za-z][0-9A-Za-z/\-. ]{0,29}$")


def valideaza_cnp(cnp: str) -> bool:
    if not re.fullmatch(r"[1-9]\d{12}", cnp):
        return False
    luna, zi = int(cnp[3:5]), int(cnp[5:7])
    if not (1 <= luna <= 12 and 1 <= zi <= 31):
        return False
    suma = sum(int(c) * int(k) for c, k in zip(cnp[:12], _CHEIE_CNP))
    control = suma % 11
    if control == 10:
        control = 1
    return control == int(cnp[12])


def normalizeaza_cui(cui: str) -> str:
    return re.sub(r"\s+", "", cui).upper().removeprefix("RO")


def valideaza_cui(cui: str) -> bool:
    cui = normalizeaza_cui(cui)
    if not re.fullmatch(r"\d{2,10}", cui):
        return False
    corp, control = cui[:-1].rjust(9, "0"), int(cui[-1])
    suma = sum(int(c) * int(k) for c, k in zip(corp, _CHEIE_CUI))
    calculat = (suma * 10) % 11
    if calculat == 10:
        calculat = 0
    return calculat == control


def valideaza_identificator(valoare: str | None) -> str | None:
    """Acceptă gol (-> None), un CNP valid (13 cifre) sau un CUI valid (2-10 cifre, opțional prefix RO)."""
    if valoare is None:
        return None
    v = re.sub(r"\s+", "", str(valoare))
    if v == "":
        return None
    if re.fullmatch(r"\d{13}", v):
        if not valideaza_cnp(v):
            raise ValueError("CNP invalid: cifra de control sau data nașterii nu se potrivesc.")
        return v
    if re.fullmatch(r"(?i)(RO)?\d{2,10}", v):
        if not valideaza_cui(v):
            raise ValueError("CUI invalid: cifra de control nu se potrivește.")
        return normalizeaza_cui(v)
    raise ValueError("Introdu un CNP (13 cifre) sau un CUI (2-10 cifre, opțional cu prefix RO).")


def parse_decimal(valoare, zecimale: int, camp: str, minim: Decimal | None = Decimal("0"),
                  maxim: Decimal | None = None, strict_minim: bool = True) -> Decimal:
    """Convertește "0,29" / 0.29 / "0.29" în Decimal exact; respinge mai multe zecimale decât permis."""
    if isinstance(valoare, float):
        valoare = repr(valoare)
    if isinstance(valoare, str):
        valoare = valoare.strip().replace(" ", "").replace(",", ".")
    try:
        d = Decimal(valoare)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{camp} trebuie să fie un număr.")
    if not d.is_finite():
        raise ValueError(f"{camp} trebuie să fie un număr.")
    if -d.as_tuple().exponent > zecimale and d != d.quantize(Decimal(1).scaleb(-zecimale)):
        raise ValueError(f"{camp} poate avea cel mult {zecimale} zecimale.")
    if minim is not None and (d <= minim if strict_minim else d < minim):
        raise ValueError(f"{camp} trebuie să fie mai mare decât {minim}.")
    if maxim is not None and d > maxim:
        raise ValueError(f"{camp} nu poate depăși {maxim}.")
    return d.quantize(Decimal(1).scaleb(-zecimale), rounding=ROUND_HALF_UP)


def valideaza_tarla_parcela(valoare: str, camp: str) -> str:
    v = re.sub(r"\s+", " ", str(valoare or "")).strip()
    if not v:
        raise ValueError(f"{camp} este obligatorie.")
    if not _RE_TARLA_PARCELA.fullmatch(v):
        raise ValueError(f"{camp} poate conține doar litere, cifre și / - . (max. 30 caractere).")
    return v


def valideaza_an_agricol(an: int) -> int:
    curent = date.today().year
    if not (2000 <= an <= curent + 5):
        raise ValueError(f"Anul agricol trebuie să fie între 2000 și {curent + 5}.")
    return an
