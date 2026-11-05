"""Scheme Pydantic v2. Ordinea claselor contează (Python 3.12 evaluează adnotările imediat):
fiecare schemă e definită ÎNAINTE de a fi folosită în alta."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from services import calcule
from validators import (
    parse_decimal,
    valideaza_an_agricol,
    valideaza_identificator,
    valideaza_tarla_parcela,
)

Cereala = Literal["grau", "porumb"]


def _text_optional(v, max_len: int, camp: str):
    if v is None:
        return None
    v = " ".join(str(v).split())
    if len(v) > max_len:
        raise ValueError(f"{camp} poate avea cel mult {max_len} caractere.")
    return v or None


def _durata(v):
    if v is None or str(v).strip() == "":
        return None
    v = str(v).strip()
    if not v.isdigit() or not (1 <= int(v) <= 99):
        raise ValueError("Durata contractului trebuie să fie un număr de ani între 1 și 99.")
    return v


# ---------------------------------------------------------------- Autentificare
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    nume: Optional[str] = None
    is_admin: bool


# ---------------------------------------------------------------- Terenuri
class TerenCreate(BaseModel):
    comuna: str = "Argetoaia"
    tarlaua: str
    parcela: str
    suprafata_ha: Decimal

    @field_validator("comuna", mode="before")
    @classmethod
    def _comuna(cls, v):
        return _text_optional(v, 60, "Comuna") or "Argetoaia"

    @field_validator("tarlaua", mode="before")
    @classmethod
    def _tarla(cls, v):
        return valideaza_tarla_parcela(v, "Tarlaua")

    @field_validator("parcela", mode="before")
    @classmethod
    def _parcela(cls, v):
        return valideaza_tarla_parcela(v, "Parcela")

    @field_validator("suprafata_ha", mode="before")
    @classmethod
    def _sup(cls, v):
        return parse_decimal(v, 4, "Suprafața", maxim=Decimal("10000"))


class TerenUpdate(BaseModel):
    comuna: Optional[str] = None
    tarlaua: Optional[str] = None
    parcela: Optional[str] = None
    suprafata_ha: Optional[Decimal] = None

    _comuna = field_validator("comuna", mode="before")(TerenCreate._comuna.__func__)
    _tarla = field_validator("tarlaua", mode="before")(TerenCreate._tarla.__func__)
    _parcela = field_validator("parcela", mode="before")(TerenCreate._parcela.__func__)
    _sup = field_validator("suprafata_ha", mode="before")(TerenCreate._sup.__func__)


class TerenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    comuna: Optional[str] = None
    tarlaua: Optional[str] = None
    parcela: Optional[str] = None
    suprafata_ha: float = 0.0
    arendas_id: int

    @field_validator("suprafata_ha", mode="before")
    @classmethod
    def _f(cls, v):
        return float(calcule.rotunjeste_ha(v))


class TerenCuProprietar(TerenResponse):
    proprietar_nume: str = ""


# ---------------------------------------------------------------- Preferințe
class PreferintaAnualaCreate(BaseModel):
    anul_agricol: int
    tip_cereala: Cereala

    @field_validator("anul_agricol")
    @classmethod
    def _an(cls, v):
        return valideaza_an_agricol(v)


class PreferintaAnualaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    arendas_id: int
    anul_agricol: int
    tip_cereala: str


class PreferinteMultipleRequest(BaseModel):
    ids: List[int] = Field(min_length=1, max_length=5000)
    anul_agricol: int
    tip_cereala: Cereala

    _an = field_validator("anul_agricol")(PreferintaAnualaCreate._an.__func__)


# ---------------------------------------------------------------- Plăți
class PlataCreate(BaseModel):
    cantitate_kg: Decimal
    anul_agricol: int
    produs: Optional[Cereala] = None
    observatii: Optional[str] = None

    @field_validator("cantitate_kg", mode="before")
    @classmethod
    def _kg(cls, v):
        return parse_decimal(v, 2, "Cantitatea", maxim=Decimal("10000000"))

    @field_validator("anul_agricol")
    @classmethod
    def _an(cls, v):
        return valideaza_an_agricol(v)

    @field_validator("observatii", mode="before")
    @classmethod
    def _obs(cls, v):
        return _text_optional(v, 300, "Observațiile")


class PlataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cantitate_kg: float = 0.0
    anul_agricol: Optional[int] = None
    data_operatiune: Optional[datetime] = None
    produs: Optional[str] = None
    observatii: Optional[str] = None

    @field_validator("cantitate_kg", mode="before")
    @classmethod
    def _f(cls, v):
        return float(calcule.rotunjeste_kg(v))


class PlataMultiplaRequest(BaseModel):
    ids: List[int] = Field(min_length=1, max_length=5000)
    an: int

    _an = field_validator("an")(PlataCreate._an.__func__)


class BilantArendas(BaseModel):
    nume_arendas: str
    anul_agricol: int
    total_hectare: float
    total_de_plata_kg: float
    total_achitat_kg: float
    rest_de_plata_kg: float
    istoric_plati: List[PlataResponse]


# ---------------------------------------------------------------- Arendași
class ArendasCreate(BaseModel):
    nume_complet: str
    cnp: Optional[str] = None
    adresa: Optional[str] = None
    nr_data_contract: Optional[str] = None
    durata_contract: Optional[str] = None
    terenuri: List[TerenCreate] = Field(default_factory=list, max_length=500)

    @field_validator("nume_complet", mode="before")
    @classmethod
    def _nume(cls, v):
        v = _text_optional(v, 120, "Numele")
        if not v or len(v) < 2:
            raise ValueError("Numele este obligatoriu (minim 2 caractere).")
        return v

    @field_validator("cnp", mode="before")
    @classmethod
    def _cnp(cls, v):
        return valideaza_identificator(v)

    @field_validator("adresa", mode="before")
    @classmethod
    def _adresa(cls, v):
        return _text_optional(v, 300, "Adresa")

    @field_validator("nr_data_contract", mode="before")
    @classmethod
    def _nr(cls, v):
        return _text_optional(v, 60, "Nr./data contractului")

    @field_validator("durata_contract", mode="before")
    @classmethod
    def _durata(cls, v):
        return _durata(v)


class ArendasUpdate(BaseModel):
    nume_complet: Optional[str] = None
    cnp: Optional[str] = None
    adresa: Optional[str] = None
    nr_data_contract: Optional[str] = None
    durata_contract: Optional[str] = None

    _nume = field_validator("nume_complet", mode="before")(ArendasCreate._nume.__func__)
    _cnp = field_validator("cnp", mode="before")(ArendasCreate._cnp.__func__)
    _adresa = field_validator("adresa", mode="before")(ArendasCreate._adresa.__func__)
    _nr = field_validator("nr_data_contract", mode="before")(ArendasCreate._nr.__func__)
    _durata = field_validator("durata_contract", mode="before")(ArendasCreate._durata.__func__)


class ArendasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nume_complet: str
    cnp: Optional[str] = None
    adresa: Optional[str] = None
    nr_data_contract: Optional[str] = None
    durata_contract: Optional[str] = None
    terenuri: List[TerenResponse] = []
    plati: List[PlataResponse] = []
    preferinte: List[PreferintaAnualaResponse] = []

    @computed_field
    @property
    def suprafata_totala(self) -> float:
        return float(calcule.rotunjeste_ha(sum(
            (calcule.to_decimal(t.suprafata_ha) for t in self.terenuri), calcule.ZERO)))

    @computed_field
    @property
    def localitate(self) -> str:
        return calcule.extrage_localitate(self.adresa)

    @computed_field
    @property
    def data_expirare(self) -> Optional[date]:
        return calcule.data_expirare(self.nr_data_contract, self.durata_contract)

    @computed_field
    @property
    def status_contract(self) -> str:
        return calcule.status_contract(self.nr_data_contract, self.durata_contract)


# ---------------------------------------------------------------- Jurnal
class JurnalCampCreate(BaseModel):
    data_operatiune: date
    tarla_parcela: str
    lucrare: str
    temperatura: Optional[str] = None
    vremea: Optional[str] = None

    @field_validator("tarla_parcela", "lucrare", mode="before")
    @classmethod
    def _oblig(cls, v, info):
        eticheta = "Tarla/parcela" if info.field_name == "tarla_parcela" else "Lucrarea"
        v = _text_optional(v, 200, eticheta)
        if not v:
            raise ValueError(f"{eticheta} este obligatorie.")
        return v

    @field_validator("temperatura", "vremea", mode="before")
    @classmethod
    def _opt(cls, v):
        return _text_optional(v, 60, "Câmpul")


class JurnalCampResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    data_operatiune: Optional[str] = None
    tarla_parcela: Optional[str] = None
    lucrare: Optional[str] = None
    temperatura: Optional[str] = None
    vremea: Optional[str] = None


# ---------------------------------------------------------------- Contract rapid
class TerenRapid(BaseModel):
    tarla: str = "..."
    parcela: str = "..."
    ha: Decimal = Decimal("0")

    @field_validator("tarla", "parcela", mode="before")
    @classmethod
    def _txt(cls, v):
        return _text_optional(v, 30, "Tarla/parcela") or "..."

    @field_validator("ha", mode="before")
    @classmethod
    def _ha(cls, v):
        if v is None or str(v).strip() == "":
            return Decimal("0")
        return parse_decimal(v, 4, "Suprafața", maxim=Decimal("10000"), strict_minim=False)


class ContractRapidCreate(BaseModel):
    nume: str
    cnp: Optional[str] = None
    ci_seria: str = "..."
    ci_numar: str = "..."
    ci_eliberat: str = "..."
    ci_data: str = "..."
    adresa: str = "..."
    terenuri: List[TerenRapid] = Field(default_factory=list, max_length=200)

    _nume = field_validator("nume", mode="before")(ArendasCreate._nume.__func__)
    _cnp = field_validator("cnp", mode="before")(ArendasCreate._cnp.__func__)

    @field_validator("ci_seria", "ci_numar", "ci_eliberat", "ci_data", "adresa", mode="before")
    @classmethod
    def _txt(cls, v):
        return _text_optional(v, 300, "Câmpul") or "..."
