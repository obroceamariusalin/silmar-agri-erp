from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
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
import cloudinary
import cloudinary.uploader
import cloudinary.api
import secrets
import pdfplumber
import re
import io


Base.metadata.create_all(bind=engine)
os.makedirs("acte_salvate", exist_ok=True)

security = HTTPBasic()

def verifica_parola(credentials: HTTPBasicCredentials = Depends(security)):
    user_corect = secrets.compare_digest(credentials.username, "silmar")
    parola_corecta = secrets.compare_digest(credentials.password, "silmar")
    
    if not (user_corect and parola_corecta):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Date de conectare incorecte",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app = FastAPI(dependencies=[Depends(verifica_parola)])

cloudinary.config( 
  cloud_name = "dmsgvmhy2", 
  api_key = "615547999745442", 
  api_secret = "2hSOqmsiV5gbUct_NJwSFxMDWQk",
  secure = True
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Ruta pentru a adăuga un Arendaș ---
@app.post("/arendasi/", response_model=schemas.ArendasResponse)
def adauga_arendas(arendas: schemas.ArendasCreate, db: Session = Depends(get_db)):

    if arendas.cnp and arendas.cnp.strip() != "":
        cnp_existent = db.query(models.Arendas).filter(models.Arendas.cnp == arendas.cnp).first()
        if cnp_existent:
            raise HTTPException(status_code=400, detail="Eroare: Acest CNP este deja inregistrat!")
    else:
        arendas.cnp = f"LIPSA-{secrets.token_hex(3).upper()}"
    
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
    try:
        rezultate = cloudinary.api.resources(type="upload", prefix=f"{arendas_id}_", max_results=50)
        
        fisiere_gasite = []
        for doc in rezultate.get('resources', []):
            extensie = doc.get('format', '')
            nume_complet = f"{doc['public_id']}.{extensie}" if extensie else doc['public_id']
            
            fisiere_gasite.append({
                "nume": nume_complet,
                "url": doc['secure_url'] 
            })
        return fisiere_gasite
    except Exception as e:
        print(f"Eroare la citirea din cloud: {e}")
        return []


# ---  UPLOAD ÎN CLOUD ---
@app.post("/arendasi/{arendas_id}/upload/")
def upload_document(arendas_id: int, file: UploadFile = File(...)):
    nume_fara_extensie = file.filename.rsplit('.', 1)[0]
    nume_public = f"{arendas_id}_{nume_fara_extensie}"

    cloudinary.uploader.upload(file.file, public_id=nume_public, resource_type="auto")
    return {"mesaj": "Document salvat în siguranță în cloud!"}


# --- ȘTERGERE DIN CLOUD ---
@app.delete("/arendasi/{arendas_id}/documente/{nume_fisier}")
def sterge_document(arendas_id: int, nume_fisier: str):
    public_id = nume_fisier.rsplit('.', 1)[0]
    
    try:
        cloudinary.uploader.destroy(public_id, resource_type="image")
        cloudinary.uploader.destroy(public_id, resource_type="raw")
        return {"mesaj": "Document sters definitiv din cloud!"}
    except:
        raise HTTPException(status_code=404, detail="Eroare la stergere")

# --- ȘTERGERE TEREN INDIVIDUAL ---
@app.delete("/terenuri/{teren_id}")
def sterge_teren(teren_id: int, db: Session = Depends(get_db)):
    teren = db.query(models.Teren).filter(models.Teren.id == teren_id).first()
    if not teren:
        raise HTTPException(status_code=404, detail="Terenul nu a fost gasit!")
    
    db.delete(teren)
    db.commit()
    return {"mesaj": "Teren sters cu succes!"}

# --- ȘTERGERE PLATĂ ---
@app.delete("/plati/{id_plata}")
def sterge_plata(id_plata: int, db: Session = Depends(get_db)):
    plata = db.query(models.Plata).filter(models.Plata.id == id_plata).first()
    if not plata:
        raise HTTPException(status_code=404, detail="Plata nu a fost gasita")
    
    db.delete(plata)
    db.commit()
    return {"mesaj": "Plată ștearsă cu succes!"}

# --- EXTRAGERE DATE DIN PDF ---
@app.post("/extrage-contract/")
async def extrage_contract(file: UploadFile = File(...)):
    try:
        continut = await file.read()
        text_complet = ""
        
        with pdfplumber.open(io.BytesIO(continut)) as pdf:
            for page in pdf.pages:
                extragere = page.extract_text()
                if extragere:
                    text_complet += extragere + " "

        text = " ".join(text_complet.split())

        print(f"DEBUG TEXT PDF: {text}")

        nume_match = re.search(r'(?:Intre\s+doamna|Intre\s+domnul)\s+(.*?)\s+domiciliat', text, re.IGNORECASE)
        nume = nume_match.group(1).strip() if nume_match else ""

        adresa_match = re.search(r'domiciliat[aă]?\s+(?:in|în)\s+(.*?),\s+identificat', text, re.IGNORECASE)
        adresa = adresa_match.group(1).strip() if adresa_match else ""
        pattern_terenuri = r'Tarlaua\s*(\d+).*?parcel[aă]?\s*([\d\/A-Za-z]+).*?suprafa[tțţ]a\s*(?:de)?\s*([\d\s\.,]+)\s*(mp|ha)'
        
        terenuri_gasite = re.findall(pattern_terenuri, text, re.IGNORECASE)
        
        lista_terenuri = []
        for t in terenuri_gasite:
            tarla = t[0]
            parcela = t[1] 
            valoare_raw = t[2].replace(' ', '').replace(',', '.')
            unitate = t[3].lower()
            
            try:
                ha_parcela = float(valoare_raw)
                if unitate == 'mp':
                    ha_parcela = ha_parcela / 10000.0
            except:
                ha_parcela = 0.0
                
            lista_terenuri.append({
                "tarlaua": tarla,
                "parcela": parcela,
                "suprafata_ha": round(ha_parcela, 4)
            })

        return {
            "nume": nume,
            "adresa": adresa,
            "terenuri": lista_terenuri
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare la citire PDF: {str(e)}")

app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
