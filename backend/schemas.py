from pydantic import BaseModel, ConfigDict
from typing import List
from datetime import datetime

# --- SCHEME PENTRU TERENURI ---
class TerenCreate(BaseModel):
    comuna: str
    suprafata_ha: float

class TerenResponse(BaseModel):
    id: int
    comuna: str
    suprafata_ha: float
    arendas_id: int

    model_config = ConfigDict(from_attributes=True)

# --- SCHEME PENTRU ARENDAȘI ---
class ArendasCreate(BaseModel):
    nume_complet: str
    cnp: str
    adresa: str

class ArendasResponse(BaseModel):
    id: int
    nume_complet: str
    cnp: str
    adresa: str
    
    # Aici e magia: când afișăm omul, afișăm și o listă cu terenurile lui!
    terenuri: List[TerenResponse] = []

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