from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.staticfiles import StaticFiles
import openpyxl
from fastapi.responses import FileResponse 
import shutil
import os
from sqlalchemy.orm import Session
import models
import schemas
from database import engine, Base, SessionLocal
from fpdf import FPDF 


Base.metadata.create_all(bind=engine)
os.makedirs("acte_salvate", exist_ok=True)

app = FastAPI(title="Sistem Arenda API")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Ruta pentru a adăuga un Arendaș ---
@app.post("/arendasi/", response_model=schemas.ArendasResponse)
def adauga_arendas(arendas: schemas.ArendasCreate, db: Session = Depends(get_db)):
 
    cnp_existent = db.query(models.Arendas).filter(models.Arendas.cnp == arendas.cnp).first()
    if cnp_existent:
        raise HTTPException(status_code=400, detail="Eroare: Acest CNP este deja inregistrat!")
    
    noul_arendas = models.Arendas(
        nume_complet=arendas.nume_complet,
        cnp=arendas.cnp,
        adresa=arendas.adresa
    )
    

    db.add(noul_arendas)
    db.commit()
    db.refresh(noul_arendas) 
    
    return noul_arendas


    # --- Ruta pentru a afisa toti arendasii ---
@app.get("/arendasi/", response_model=list[schemas.ArendasResponse])
def citeste_arendasi(db: Session = Depends(get_db)):
    arendasi = db.query(models.Arendas).all()
    return arendasi

# --- Ruta pentru a adăuga un teren unui arendas ---
@app.post("/arendasi/{arendas_id}/terenuri/", response_model=schemas.TerenResponse)
def adauga_teren(arendas_id: int, teren: schemas.TerenCreate, db: Session = Depends(get_db)):
   
    om = db.query(models.Arendas).filter(models.Arendas.id == arendas_id).first()
    if not om:
        raise HTTPException(status_code=404, detail="Eroare: Arendasul nu a fost gasit!")

    noul_teren = models.Teren(
        comuna=teren.comuna,
        tarlaua=teren.tarlaua,       
        parcela=teren.parcela,       
        suprafata_ha=teren.suprafata_ha,
        arendas_id=arendas_id 
    )
    
   
    db.add(noul_teren)
    db.commit()
    db.refresh(noul_teren)
    
    return noul_teren


    # --- Ruta pentru incarcarea documentelor (Buletin, Act Teren, etc.) ---
@app.post("/arendasi/{arendas_id}/upload-document/")
def incarca_document(arendas_id: int, file: UploadFile = File(...)):

    nume_fisier_nou = f"{arendas_id}_{file.filename}"
    cale_salvare = f"acte_salvate/{nume_fisier_nou}"

    with open(cale_salvare, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "mesaj": "Fisier incarcat si salvat cu succes!",
        "fisier": nume_fisier_nou
    }


# --- Înregistrarea unei plăți noi ---
@app.post("/arendasi/{arendas_id}/plati/", response_model=schemas.PlataResponse)
def inregistreaza_plata(arendas_id: int, plata: schemas.PlataCreate, db: Session = Depends(get_db)):
    noul_pachet = models.Plata(**plata.model_dump(), arendas_id=arendas_id)
    db.add(noul_pachet)
    db.commit()
    db.refresh(noul_pachet)
    return noul_pachet

# --- Calculul Bilanțului ---
@app.get("/arendasi/{arendas_id}/bilant/", response_model=schemas.BilantArendas)
def obtine_bilant(arendas_id: int, db: Session = Depends(get_db)):
    om = db.query(models.Arendas).filter(models.Arendas.id == arendas_id).first()
    if not om:
        raise HTTPException(status_code=404, detail="Arendasul nu exista")

    total_ha = sum(t.suprafata_ha for t in om.terenuri)

    total_datorat = total_ha * 600

    total_platit = sum(p.cantitate_kg for p in om.plati)
    
    return {
        "nume_arendas": om.nume_complet,
        "total_hectare": total_ha,
        "total_de_plata_kg": total_datorat,
        "total_achitat_kg": total_platit,
        "rest_de_plata_kg": total_datorat - total_platit,
        "istoric_plati": om.plati
    }


# ---  EDITARE ARENDAȘ ---
@app.patch("/arendasi/{arendas_id}", response_model=schemas.ArendasResponse)
def editeaza_arendas(arendas_id: int, date_noi: schemas.ArendasUpdate, db: Session = Depends(get_db)):
    om = db.query(models.Arendas).filter(models.Arendas.id == arendas_id).first()
    if not om:
        raise HTTPException(status_code=404, detail="Arendasul nu a fost gasit!")

    date_trimise = date_noi.model_dump(exclude_unset=True)

    for cheie, valoare in date_trimise.items():
        setattr(om, cheie, valoare)

    db.commit()
    db.refresh(om)
    return om

# --- EDITARE TEREN ---
@app.patch("/terenuri/{teren_id}", response_model=schemas.TerenResponse)
def editeaza_teren(teren_id: int, date_noi: schemas.TerenUpdate, db: Session = Depends(get_db)):
    teren = db.query(models.Teren).filter(models.Teren.id == teren_id).first()
    if not teren:
        raise HTTPException(status_code=404, detail="Terenul nu a fost gasit!")

    date_trimise = date_noi.model_dump(exclude_unset=True)

    for cheie, valoare in date_trimise.items():
        setattr(teren, cheie, valoare)

    db.commit()
    db.refresh(teren)
    return teren

# --- ȘTERGERE ARENDAȘ ---
@app.delete("/arendasi/{arendas_id}")
def sterge_arendas(arendas_id: int, db: Session = Depends(get_db)):
    om = db.query(models.Arendas).filter(models.Arendas.id == arendas_id).first()
    if not om:
        raise HTTPException(status_code=404, detail="Arendasul nu a fost gasit!")

    db.delete(om)
    db.commit()
    return {"mesaj": f"Arendasul {om.nume_complet} si toate terenurile lui au fost sterse cu succes!"}


# --- EXPORT BORDEROU EXCEL ---
@app.get("/borderou/descarca-excel")
def descarca_borderou_excel(db: Session = Depends(get_db)):
    arendasi = db.query(models.Arendas).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Borderou 2026"

    ws.append(["S.C. SILMAR SOLUTION SRL"])
    ws.append(["C.F. 49659242"])
    ws.append(["COMUNA ARGETOAIA"])
    ws.append([]) 
    ws.append(["", "", "", "BORDEROU PRIVIND PLATA ARENDEI IN PRODUSE PENTRU ANUL AGRICOL 2026"])
    ws.append([]) 

 
    headers = [
        "NR. CRT.", "NUME SI PRENUME", "ADRESA", "SUPRAFATA HA", 
        "CANTIT. BRUTA KG", "CANT. DUPA DED. 40%", "IMPOZIT 10%", 
        "CANTITA NETA", "VALOARE TVA", "CANTITATE PRIMITA", "SEMNATURA"
    ]
    ws.append(headers)

    nr_crt = 1
    for om in arendasi:
        suprafata_totala = sum(t.suprafata_ha for t in om.terenuri)

        if suprafata_totala == 0:
            continue

        cant_bruta = round(suprafata_totala * 600)
        cant_dupa_ded = round(cant_bruta * 60 / 100)
        impozit = round(cant_dupa_ded * 10 / 100)
        cant_neta = cant_bruta - impozit
        valoare_tva = round(cant_neta * 11 / 100)
        cantitate_primita = cant_neta + valoare_tva

        rand_nou = [
            nr_crt,
            om.nume_complet,
            om.adresa,
            round(suprafata_totala, 3), 
            cant_bruta,
            cant_dupa_ded,
            impozit,
            cant_neta,
            valoare_tva,
            cantitate_primita,
            "" 
        ]
        ws.append(rand_nou)
        nr_crt += 1

    nume_fisier = "acte_salvate/Borderou_Arenda_2026.xlsx"
    wb.save(nume_fisier)

    
    return FileResponse(
        path=nume_fisier, 
        filename="Borderou_Arenda_2026.xlsx",
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )



# --- CITIRE LISTĂ DOCUMENTE ---
@app.get("/arendasi/{arendas_id}/documente")
def get_documente(arendas_id: int):
    if not os.path.exists("acte_salvate"):
        return []

    toate_fisierele = os.listdir("acte_salvate")
    fisierele_omului = [f for f in toate_fisierele if f.startswith(f"{arendas_id}_")]

    return fisierele_omului


# --- UPLOAD DOCUMENT ---
@app.post("/arendasi/{arendas_id}/upload/")
def upload_document(arendas_id: int, file: UploadFile = File(...)):

    os.makedirs("acte_salvate", exist_ok=True)

    file_location = f"acte_salvate/{arendas_id}_{file.filename}"

    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)

    return {"mesaj": f"Documentul {file.filename} a fost salvat cu succes!"}


# --- ȘTERGERE DOCUMENT ---
@app.delete("/arendasi/{arendas_id}/documente/{nume_fisier}")
def sterge_document(arendas_id: int, nume_fisier: str):
    cale_fisier = f"acte_salvate/{nume_fisier}"

    if os.path.exists(cale_fisier) and nume_fisier.startswith(f"{arendas_id}_"):
        os.remove(cale_fisier) 
        return {"mesaj": "Document șters cu succes!"}
        
    raise HTTPException(status_code=404, detail="Fisierul nu a fost gasit!")

# --- ȘTERGERE TEREN INDIVIDUAL ---
@app.delete("/terenuri/{teren_id}")
def sterge_teren(teren_id: int, db: Session = Depends(get_db)):
    teren = db.query(models.Teren).filter(models.Teren.id == teren_id).first()
    if not teren:
        raise HTTPException(status_code=404, detail="Terenul nu a fost gasit!")
    
    db.delete(teren)
    db.commit()
    return {"mesaj": "Teren sters cu succes!"}

app.mount("/acte", StaticFiles(directory="acte_salvate"), name="acte")
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
