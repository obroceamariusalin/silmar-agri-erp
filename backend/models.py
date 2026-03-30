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

    terenuri = relationship("Teren", back_populates="proprietar")
    # Nou: Legătura către plăți
    plati = relationship("Plata", back_populates="beneficiar")

class Teren(Base):
    __tablename__ = "terenuri"
    id = Column(Integer, primary_key=True, index=True)
    comuna = Column(String)
    suprafata_ha = Column(Float)
    arendas_id = Column(Integer, ForeignKey("arendasi.id"))
    proprietar = relationship("Arendas", back_populates="terenuri")

# --- TABELUL NOU PENTRU PLĂȚI ---
class Plata(Base):
    __tablename__ = "plati"
    id = Column(Integer, primary_key=True, index=True)
    cantitate_kg = Column(Float)
    anul_agricol = Column(Integer)
    data_operatiune = Column(DateTime, default=datetime.datetime.utcnow)
    arendas_id = Column(Integer, ForeignKey("arendasi.id"))
    
    beneficiar = relationship("Arendas", back_populates="plati")