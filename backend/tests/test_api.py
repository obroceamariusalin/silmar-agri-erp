import io
from decimal import Decimal

import openpyxl
import pytest
from docx import Document

import models
from database import SessionLocal
from tests.conftest import cnp_valid
from validators import valideaza_cnp, valideaza_cui


# ------------------------------------------------------------------ Validatori
def test_cnp_si_cui():
    assert valideaza_cnp(cnp_valid("180010112345"))
    assert not valideaza_cnp("1800101123450" if not valideaza_cnp("1800101123450") else "1800101123451")
    assert valideaza_cui("49659242")       # CUI Silmar
    assert valideaza_cui("RO49659242".removeprefix("RO"))
    assert not valideaza_cui("49659243")


# ------------------------------------------------------------------ Autentificare
def test_fara_login_401(anonim):
    anonim.cookies.clear()
    r = anonim.get("/api/arendasi")
    assert r.status_code == 401
    assert "autentificat" in r.json()["detail"]


def test_login_gresit(anonim):
    r = anonim.post("/api/auth/login", json={"username": "admin", "password": "gresit"})
    assert r.status_code == 401


def test_me(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "admin"
    assert r.json()["config"]["kg_per_ha"] == 600


def test_pagini_statice(anonim):
    assert anonim.get("/").status_code == 200
    assert anonim.get("/login").status_code == 200


# ------------------------------------------------------------------ Arendași
def test_creare_cu_validari(client):
    r = client.post("/api/arendasi", json={"nume_complet": "Ion Popescu", "cnp": "1234567890123"})
    assert r.status_code == 422
    assert "CNP" in r.json()["detail"]

    r = client.post("/api/arendasi", json={"nume_complet": "Ion Popescu", "cnp": "", "adresa": "Comuna Argetoaia, Sat X"})
    assert r.status_code == 201, r.text
    assert r.json()["cnp"] is None
    assert r.json()["localitate"] == "Comuna Argetoaia"

    cnp = cnp_valid("180010112345")
    r = client.post("/api/arendasi", json={
        "nume_complet": "Maria Ionescu", "cnp": cnp,
        "nr_data_contract": "12/01.03.2020", "durata_contract": "7",
        "terenuri": [
            {"tarlaua": "129", "parcela": "12/1", "suprafata_ha": "0,29"},
            {"tarlaua": "130", "parcela": "4", "suprafata_ha": 0.1},
        ],
    })
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["suprafata_totala"] == 0.39       # fără 0.39000000000000007
    assert d["data_expirare"] == "2027-03-01"

    r = client.post("/api/arendasi", json={"nume_complet": "Alt Om", "cnp": cnp})
    assert r.status_code == 409


def test_suprafata_invalida(client):
    om = client.post("/api/arendasi", json={"nume_complet": "Test Suprafata"}).json()
    for val, cuvant in [("-1", "mai mare"), ("abc", "număr"), ("0.123456", "zecimale")]:
        r = client.post(f"/api/arendasi/{om['id']}/terenuri", json={"tarlaua": "1", "parcela": "2", "suprafata_ha": val})
        assert r.status_code == 422 and cuvant in r.json()["detail"], r.text
    r = client.post(f"/api/arendasi/{om['id']}/terenuri", json={"tarlaua": "<script>", "parcela": "2", "suprafata_ha": 1})
    assert r.status_code == 422


def test_teren_plata_preferinta_returneaza_dosarul(client):
    om = client.post("/api/arendasi", json={"nume_complet": "Dosar Complet"}).json()
    d = client.post(f"/api/arendasi/{om['id']}/terenuri", json={"tarlaua": "1", "parcela": "1", "suprafata_ha": 1.5}).json()
    assert d["suprafata_totala"] == 1.5
    teren_id = d["terenuri"][0]["id"]

    d = client.patch(f"/api/terenuri/{teren_id}", json={"suprafata_ha": "2"}).json()
    assert d["suprafata_totala"] == 2.0

    d = client.post(f"/api/arendasi/{om['id']}/preferinte", json={"anul_agricol": 2026, "tip_cereala": "porumb"}).json()
    assert d["preferinte"][0]["tip_cereala"] == "porumb"

    d = client.post(f"/api/arendasi/{om['id']}/plati", json={"cantitate_kg": 500, "anul_agricol": 2026}).json()
    assert d["plati"][0]["produs"] == "porumb"

    b = client.get(f"/api/arendasi/{om['id']}/bilant?an=2026").json()
    assert b["total_de_plata_kg"] == 1200 and b["rest_de_plata_kg"] == 700

    r = client.post("/api/arendasi/plata-totala-multipla", json={"ids": [om["id"]], "an": 2026})
    assert r.status_code == 200 and r.json()["procesati"] == 1
    b = client.get(f"/api/arendasi/{om['id']}/bilant?an=2026").json()
    assert b["rest_de_plata_kg"] == 0

    r = client.post("/api/arendasi/preferinte-multiple", json={"ids": [om["id"], 999999], "anul_agricol": 2027, "tip_cereala": "grau"})
    assert r.json()["actualizati"] == 1

    assert client.delete(f"/api/plati/{d['plati'][0]['id']}").status_code == 200
    assert client.delete(f"/api/terenuri/{teren_id}").json()["terenuri"] == []
    assert client.delete(f"/api/arendasi/{om['id']}").status_code == 200
    assert client.get(f"/api/arendasi/{om['id']}").status_code == 404


def test_plata_in_bani_si_borderou(client):
    om = client.post("/api/arendasi", json={"nume_complet": "Plata In Bani", "terenuri": [
        {"tarlaua": "1", "parcela": "1", "suprafata_ha": "1"}]}).json()   # 600 kg datorat
    client.post(f"/api/arendasi/{om['id']}/preferinte", json={"anul_agricol": 2030, "tip_cereala": "bani"})

    # lipsește prețul -> eroare clară
    r = client.post(f"/api/arendasi/{om['id']}/plati", json={"tip_plata": "bani", "suma_lei": 100, "anul_agricol": 2030})
    assert r.status_code == 422 and "prețul" in r.json()["detail"]

    # sumă + preț -> kg echivalent calculat (220 lei / 1,10 = 200 kg)
    d = client.post(f"/api/arendasi/{om['id']}/plati", json={"tip_plata": "bani", "suma_lei": "220", "pret_lei_kg": "1,10", "anul_agricol": 2030}).json()
    p = d["plati"][-1]
    assert p["tip_plata"] == "bani" and p["produs"] == "bani" and p["cantitate_kg"] == 200 and p["suma_lei"] == 220

    # plata completă în bloc pentru cei pe bani cere preț
    r = client.post("/api/arendasi/plata-totala-multipla", json={"ids": [om["id"]], "an": 2030})
    assert r.status_code == 400 and "prețul" in r.json()["detail"]
    r = client.post("/api/arendasi/plata-totala-multipla", json={"ids": [om["id"]], "an": 2030, "pret_lei_kg": "1.10"})
    assert r.json()["procesati"] == 1
    b = client.get(f"/api/arendasi/{om['id']}/bilant?an=2030").json()
    assert b["rest_de_plata_kg"] == 0

    wb = openpyxl.load_workbook(io.BytesIO(client.get("/api/rapoarte/borderou?an=2030").content))
    ws = wb["Bani 2030"]
    rand = next(r for r in ws.iter_rows(min_row=6, values_only=True) if r[1] == "Plata In Bani")
    # 600 kg × 1,10 = 660 lei brut; ded. 40% -> 396; impozit 39,60; net 620,40; TVA 68,24; primit 688,64
    assert rand[4] == 600 and rand[5] == 1.1 and rand[6] == 660
    assert rand[8] == 39.6 and rand[9] == 620.4 and rand[11] == 688.64 and rand[12] == 660
    client.delete(f"/api/arendasi/{om['id']}")


def test_plata_arendas_inexistent(client):
    r = client.post("/api/arendasi/999999/plati", json={"cantitate_kg": 1, "anul_agricol": 2026})
    assert r.status_code == 404


# ------------------------------------------------------------------ Documente cu date incomplete
@pytest.fixture
def date_incomplete():
    with SessionLocal() as db:
        om = models.Arendas(nume_complet="Om Cu Date Lipsa", cnp=None, adresa=None,
                            nr_data_contract=None, durata_contract=None)
        om.terenuri = [
            models.Teren(tarlaua=None, parcela=None, suprafata_ha=Decimal("1.2345")),
            models.Teren(tarlaua="5", parcela="7", suprafata_ha=None),
        ]
        db.add(om)
        db.add(models.Arendas(nume_complet="Fara Terenuri"))
        db.commit()
        yield om.id
        db.delete(db.get(models.Arendas, om.id))
        db.commit()


def test_tabel_primarie_date_incomplete(client, date_incomplete):
    r = client.get("/api/rapoarte/tabel-primarie")
    assert r.status_code == 200
    doc = Document(io.BytesIO(r.content))
    text = "\n".join(c.text for row in doc.tables[0].rows for c in row.cells)
    assert "Om Cu Date Lipsa" in text and "None" not in text
    assert "1.2345" in text


def test_borderou_si_csv(client, date_incomplete):
    r = client.get("/api/rapoarte/borderou?an=2026")
    assert r.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Grâu 2026", "Porumb 2026", "Bani 2026"]
    r = client.get("/api/rapoarte/arendasi.csv?an=2026")
    assert r.status_code == 200 and r.content.startswith(b"\xef\xbb\xbf")


def test_contract_rapid(client):
    r = client.post("/api/contracte/rapid", json={
        "nume": "ion popescu", "cnp": cnp_valid("180010112345"), "adresa": "Sat {{X}}",
        "terenuri": [{"tarla": "129", "parcela": "3", "ha": "0,29"}, {"tarla": "", "parcela": "", "ha": ""}],
    })
    assert r.status_code == 200, r.text
    doc = Document(io.BytesIO(r.content))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "2900 mp" in text            # bug-ul vechi: 2899 mp
    assert "J2024000482163" in text and "J16/482/2024" not in text
    # toate terenurile încep din aceeași coloană (fără spațiu în plus doar pe primul rând)
    lista = next(p.text for p in doc.paragraphs if "Tarlaua 129" in p.text)
    assert all(linie.startswith("- Tarlaua") for linie in lista.split("\n")), repr(lista)
    # niciun text completat de aplicație nu rămâne în alt font decât Times New Roman
    import zipfile
    xml = zipfile.ZipFile(io.BytesIO(r.content)).read("word/document.xml").decode()
    assert "Roboto" not in xml
    assert "domnul" in text and "Ion Popescu" in text
    assert "{{NUME}}" not in text and "{{HA}}" not in text and "0.29" in text


def test_jurnal(client):
    r = client.post("/api/jurnal", json={"data_operatiune": "2026-04-01", "tarla_parcela": "T129", "lucrare": "Arat"})
    assert r.status_code == 201
    assert client.post("/api/jurnal", json={"data_operatiune": "nu", "tarla_parcela": "", "lucrare": ""}).status_code == 422
    assert any(j["lucrare"] == "Arat" for j in client.get("/api/jurnal").json())
    assert client.delete(f"/api/jurnal/{r.json()['id']}").status_code == 200


def test_document_alt_arendas_interzis(client):
    r = client.delete("/api/arendasi/1/documente", params={"public_id": "2_buletin", "resource_type": "image"})
    assert r.status_code == 403
