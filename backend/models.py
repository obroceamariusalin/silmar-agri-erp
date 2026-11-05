from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "utilizatori"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    nume = Column(String(120), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    last_login = Column(DateTime, nullable=True)


class Arendas(Base):
    __tablename__ = "arendasi"

    id = Column(Integer, primary_key=True, index=True)
    nume_complet = Column(String, index=True, nullable=False)
    # CNP (13 cifre) sau CUI (persoană juridică). NULL = necunoscut (mai multe NULL-uri sunt permise de UNIQUE).
    cnp = Column(String, unique=True, index=True, nullable=True)
    adresa = Column(String, nullable=True)
    nr_data_contract = Column(String, nullable=True)
    durata_contract = Column(String, default="7", nullable=True)

    terenuri = relationship("Teren", back_populates="proprietar", cascade="all, delete-orphan", order_by="Teren.id")
    plati = relationship("Plata", back_populates="arendas", cascade="all, delete-orphan", order_by="Plata.id")
    preferinte = relationship("PreferintaAnuala", back_populates="arendas", cascade="all, delete-orphan")


class Teren(Base):
    __tablename__ = "terenuri"

    id = Column(Integer, primary_key=True, index=True)
    comuna = Column(String, default="Argetoaia")
    tarlaua = Column(String)
    parcela = Column(String)
    # Numeric(12,4): precizie exactă de 1 mp (0.0001 ha), fără erori de virgulă mobilă
    suprafata_ha = Column(Numeric(12, 4, asdecimal=True))

    arendas_id = Column(Integer, ForeignKey("arendasi.id", ondelete="CASCADE"), index=True)
    proprietar = relationship("Arendas", back_populates="terenuri")


class Plata(Base):
    __tablename__ = "plati"

    id = Column(Integer, primary_key=True, index=True)
    cantitate_kg = Column(Numeric(12, 2, asdecimal=True))
    anul_agricol = Column(Integer, index=True)
    data_operatiune = Column(DateTime, default=_utcnow)
    produs = Column(String, default="grau")
    observatii = Column(String, nullable=True)

    arendas_id = Column(Integer, ForeignKey("arendasi.id", ondelete="CASCADE"), index=True)
    arendas = relationship("Arendas", back_populates="plati")


class PreferintaAnuala(Base):
    __tablename__ = "preferinte_anuale"
    __table_args__ = (UniqueConstraint("arendas_id", "anul_agricol", name="uq_preferinta_an"),)

    id = Column(Integer, primary_key=True, index=True)
    arendas_id = Column(Integer, ForeignKey("arendasi.id", ondelete="CASCADE"), index=True)
    anul_agricol = Column(Integer)
    tip_cereala = Column(String, default="grau")
    arendas = relationship("Arendas", back_populates="preferinte")


class JurnalCamp(Base):
    __tablename__ = "jurnal_camp"

    id = Column(Integer, primary_key=True, index=True)
    data_operatiune = Column(String)  # ISO YYYY-MM-DD
    tarla_parcela = Column(String)
    lucrare = Column(String)
    temperatura = Column(String)
    vremea = Column(String)
