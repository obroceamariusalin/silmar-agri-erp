from pydantic import BaseModel, ConfigDict, computed_field
from typing import List, Optional
from datetime import datetime


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

class PreferintaAnualaBase(BaseModel):
    anul_agricol: int
    tip_cereala: str

class PreferintaAnualaCreate(PreferintaAnualaBase):
    pass

class PreferintaAnualaResponse(PreferintaAnualaBase):
    id: int
    arendas_id: int
    
    class Config:
        from_attributes = True


class ArendasCreate(BaseModel):
    nume_complet: str
    cnp: str
    adresa: str

class ArendasUpdate(BaseModel): 
    nume_complet: Optional[str] = None
    cnp: Optional[str] = None
    adresa: Optional[str] = None
    nr_data_contract: Optional[str] = None
    durata_contract: Optional[str] = None

class ArendasResponse(BaseModel):
    id: int
    nume_complet: str
    cnp: str
    adresa: str
    nr_data_contract: Optional[str] = None
    durata_contract: Optional[str] = None  
    terenuri: List[TerenResponse] = []
    plati: List[PlataResponse] = []
    preferinte: List[PreferintaAnualaResponse] = []

    @computed_field
    def suprafata_totala(self) -> float:
        return sum(teren.suprafata_ha for teren in self.terenuri)

    model_config = ConfigDict(from_attributes=True)


class PlataCreate(BaseModel):
    cantitate_kg: float
    anul_agricol: int
    produs: Optional[str] = None
    observatii: Optional[str] = None

class PlataResponse(BaseModel):
    id: int
    cantitate_kg: float
    anul_agricol: int
    data_operatiune: datetime
    
    model_config = ConfigDict(from_attributes=True)

class BilantArendas(BaseModel):
    nume_arendas: str
    total_hectare: float
    total_de_plata_kg: float
    total_achitat_kg: float
    rest_de_plata_kg: float
    istoric_plati: List[PlataResponse]

class JurnalCampBase(BaseModel):
    data_operatiune: str
    tarla_parcela: str
    lucrare: str
    temperatura: str
    vremea: str

class JurnalCampCreate(JurnalCampBase):
    pass

class JurnalCampResponse(JurnalCampBase):
    id: int
    
    class Config:
        from_attributes = True



class TerenRapid(BaseModel):
    tarla: str
    parcela: str
    ha: str

class ContractRapidCreate(BaseModel):
    nume: str
    cnp: str
    ci_seria: str
    ci_numar: str
    ci_eliberat: str
    ci_data: str
    adresa: str
    terenuri: List[TerenRapid]