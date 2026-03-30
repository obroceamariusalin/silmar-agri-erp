from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# ATENȚIE: Înlocuiește 'parola_ta' cu parola ta reală de la PostgreSQL
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:silmarsolution@localhost/arenda_db"

# Creăm "motorul" care comunică cu baza de date
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Creăm o sesiune (o "conversație" cu baza de date)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clasa de bază pentru tabelele noastre
Base = declarative_base()