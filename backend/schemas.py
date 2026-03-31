from pydantic import BaseModel, ConfigDict, computed_field
from typing import List, Optional
from datetime import datetime

# --- SCHEME PENTRU TERENURI ---
class TerenCreate(BaseModel):
    comuna: str = "Argetoaia"
    tarlaua: str
    parcela: str
    suprafata_ha: float

class TerenUpdate(BaseModel): 
    comuna: Optional[str] = None
    tarlaua: Optional[str] = None
    parcela: Optional[str] = None
    suprafata_ha: Optional[float] = None

class TerenResponse(BaseModel):
    id: int
    comuna: str
    tarlaua: str
    parcela: str
    suprafata_ha: float
    arendas_id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEME PENTRU ARENDAȘI ---
class ArendasCreate(BaseModel):
    nume_complet: str
    cnp: str
    adresa: str

class ArendasUpdate(BaseModel): 
    nume_complet: Optional[str] = None
    cnp: Optional[str] = None
    adresa: Optional[str] = None

class ArendasResponse(BaseModel):
    id: int
    nume_complet: str
    cnp: str
    adresa: str
    terenuri: List[TerenResponse] = []
    plati: List[PlataResponse] = []

    @computed_field
    def suprafata_totala(self) -> float:
        return sum(teren.suprafata_ha for teren in self.terenuri)

    model_config = ConfigDict(from_attributes=True)


class PlataCreate(BaseModel):
    cantitate_kg: float
    anul_agricol: int

class PlataResponse(BaseModel):
    id: int
    cantitate_kg: float
    anul_agricol: int
    data_operatiune: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMĂ BILANȚ (Raportul final) ---
class BilantArendas(BaseModel):
    nume_arendas: str
    total_hectare: float
    total_de_plata_kg: float
    total_achitat_kg: float
    rest_de_plata_kg: float
    istoric_plati: List[PlataResponse]