from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Arendas(Base):
    __tablename__ = "arendasi"

    id = Column(Integer, primary_key=True, index=True)
    nume_complet = Column(String, index=True)
    cnp = Column(String, unique=True, index=True)
    adresa = Column(String)

    preferinte = relationship("PreferintaAnuala", back_populates="arendas", cascade="all, delete-orphan")
    terenuri = relationship("Teren", back_populates="proprietar", cascade="all, delete-orphan")
    plati = relationship("Plata", back_populates="beneficiar", cascade="all, delete-orphan")


class Teren(Base):
    __tablename__ = "terenuri"

    id = Column(Integer, primary_key=True, index=True)
    comuna = Column(String, default="Argetoaia")
    tarlaua = Column(String) 
    parcela = Column(String) 
    suprafata_ha = Column(Float)
    
    arendas_id = Column(Integer, ForeignKey("arendasi.id"))
    proprietar = relationship("Arendas", back_populates="terenuri")


class Plata(Base):
    __tablename__ = "plati"
    id = Column(Integer, primary_key=True, index=True)
    cantitate_kg = Column(Float)
    anul_agricol = Column(Integer)
    data_operatiune = Column(DateTime, default=datetime.datetime.utcnow)

    arendas_id = Column(Integer, ForeignKey("arendasi.id"))
    beneficiar = relationship("Arendas", back_populates="plati")

class PreferintaAnuala(Base):
    __tablename__ = "preferinte_anuale"
    
    id = Column(Integer, primary_key=True, index=True)
    arendas_id = Column(Integer, ForeignKey("arendasi.id"))
    anul_agricol = Column(Integer)
    tip_cereala = Column(String, default="grau") 
    arendas = relationship("Arendas", back_populates="preferinte")

class JurnalCamp(Base):
    __tablename__ = "jurnal_camp"
    
    id = Column(Integer, primary_key=True, index=True)
    data_operatiune = Column(String)  
    tarla_parcela = Column(String)    
    lucrare = Column(String)          
    temperatura = Column(String)      
    vremea = Column(String)           