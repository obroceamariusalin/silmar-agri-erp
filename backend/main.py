from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.responses import FileResponse # Am adaugat asta pentru a returna fisierul
import shutil
import os
from sqlalchemy.orm import Session
import models
import schemas
from database import engine, Base, SessionLocal
from fpdf import FPDF # Am adaugat biblioteca de desenat PDF-uri

# Creăm tabelele
Base.metadata.create_all(bind=engine)
os.makedirs("acte_salvate", exist_ok=True)

app = FastAPI(title="Sistem Arenda API")

# O funcție de ajutor care ne deschide o "conversație" cu baza de date
# și o închide automat când terminăm, ca să nu blocăm serverul.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def salut():
    return {"mesaj": "Salut! Serverul functioneaza!"}

# --- AICI ESTE MAGIA: Ruta pentru a adăuga un Arendaș ---
@app.post("/arendasi/", response_model=schemas.ArendasResponse)
def adauga_arendas(arendas: schemas.ArendasCreate, db: Session = Depends(get_db)):
    
    # 1. Verificăm dacă există deja cineva cu acest CNP în baza de date
    cnp_existent = db.query(models.Arendas).filter(models.Arendas.cnp == arendas.cnp).first()
    if cnp_existent:
        raise HTTPException(status_code=400, detail="Eroare: Acest CNP este deja inregistrat!")
    
    # 2. Pregătim "pachetul" cu datele omului pentru baza de date
    noul_arendas = models.Arendas(
        nume_complet=arendas.nume_complet,
        cnp=arendas.cnp,
        adresa=arendas.adresa
    )
    
    # 3. Adăugăm în baza de date și salvăm
    db.add(noul_arendas)
    db.commit()
    db.refresh(noul_arendas) # Îi aducem ID-ul proaspăt generat
    
    return noul_arendas


    # --- Ruta pentru a afisa toti arendasii ---
@app.get("/arendasi/", response_model=list[schemas.ArendasResponse])
def citeste_arendasi(db: Session = Depends(get_db)):
    # Cautam in baza de date toti oamenii din tabelul Arendas
    arendasi = db.query(models.Arendas).all()
    return arendasi


# --- Ruta pentru a adauga un teren unui arendas ---
@app.post("/arendasi/{arendas_id}/terenuri/", response_model=schemas.TerenResponse)
def adauga_teren(arendas_id: int, teren: schemas.TerenCreate, db: Session = Depends(get_db)):
    
    # 1. Verificăm dacă omul cu acest ID chiar există în baza de date
    om = db.query(models.Arendas).filter(models.Arendas.id == arendas_id).first()
    if not om:
        raise HTTPException(status_code=404, detail="Eroare: Arendasul nu a fost gasit!")

    # 2. Creăm terenul și îl lipim de ID-ul omului găsit
    noul_teren = models.Teren(
        comuna=teren.comuna,
        suprafata_ha=teren.suprafata_ha,
        arendas_id=arendas_id # Aici facem legătura!
    )
    
    # 3. Salvăm în baza de date
    db.add(noul_teren)
    db.commit()
    db.refresh(noul_teren)
    
    return noul_teren


    # --- Ruta pentru incarcarea documentelor (Buletin, Act Teren, etc.) ---
@app.post("/arendasi/{arendas_id}/upload-document/")
def incarca_document(arendas_id: int, file: UploadFile = File(...)):
    
    # 1. Construim numele fișierului ca să știm al cui este
    # Ex: "1_buletin_popescu.pdf"
    nume_fisier_nou = f"{arendas_id}_{file.filename}"
    cale_salvare = f"acte_salvate/{nume_fisier_nou}"
    
    # 2. Deschidem un fișier gol pe hard disk și copiem conținutul primit în el
    with open(cale_salvare, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "mesaj": "Fisier incarcat si salvat cu succes!",
        "fisier": nume_fisier_nou
    }


# --- 1. Înregistrarea unei plăți noi ---
@app.post("/arendasi/{arendas_id}/plati/", response_model=schemas.PlataResponse)
def inregistreaza_plata(arendas_id: int, plata: schemas.PlataCreate, db: Session = Depends(get_db)):
    noul_pachet = models.Plata(**plata.model_dump(), arendas_id=arendas_id)
    db.add(noul_pachet)
    db.commit()
    db.refresh(noul_pachet)
    return noul_pachet

# --- 2. Calculul Bilanțului (Matematica Proiectului) ---
@app.get("/arendasi/{arendas_id}/bilant/", response_model=schemas.BilantArendas)
def obtine_bilant(arendas_id: int, db: Session = Depends(get_db)):
    om = db.query(models.Arendas).filter(models.Arendas.id == arendas_id).first()
    if not om:
        raise HTTPException(status_code=404, detail="Arendasul nu exista")

    # Calculăm total hectare
    total_ha = sum(t.suprafata_ha for t in om.terenuri)
    
    # Calculăm cât ar trebui să primească (600 kg pe hectar)
    total_datorat = total_ha * 600
    
    # Calculăm cât i-am dat deja
    total_platit = sum(p.cantitate_kg for p in om.plati)
    
    return {
        "nume_arendas": om.nume_complet,
        "total_hectare": total_ha,
        "total_de_plata_kg": total_datorat,
        "total_achitat_kg": total_platit,
        "rest_de_plata_kg": total_datorat - total_platit,
        "istoric_plati": om.plati
    }


