"""Generarea documentelor Word / Excel.

Toate funcțiile întorc bytes generați în memorie (fără fișiere comune pe disc, deci fără
amestecarea documentelor între doi utilizatori simultani) și tolerează date incomplete (NULL).
"""
import io
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

import openpyxl
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import schemas
from config import FIRMA_CUI, FIRMA_NUME, KG_PER_HA, TEMPLATE_CONTRACT
from services import calcule


def _txt(valoare, implicit: str = "") -> str:
    if valoare is None:
        return implicit
    s = str(valoare).strip()
    return s if s else implicit


def _bytes(doc_sau_wb) -> bytes:
    buf = io.BytesIO()
    doc_sau_wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ Tabel primărie
def tabel_primarie(arendasi) -> bytes:
    doc = Document()

    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    for marg in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, marg, Cm(1))

    run_antet = doc.add_paragraph().add_run("JUDETUL DOLJ\nCOMUNA ARGETOAIA\nPRIMARIA COMUNEI ARGETOAIA\n")
    run_antet.bold = True
    doc.add_paragraph(f"NR. .................... din {datetime.now().strftime('%d.%m.%Y')}")

    p_titlu = doc.add_paragraph()
    p_titlu.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_titlu = p_titlu.add_run(
        f"TABEL CENTRALIZATOR AL CONTRACTELOR DE ARENDA\nSILMAR SOLUTION SRL, CUI {FIRMA_CUI} = arendaș")
    run_titlu.bold = True

    capete = [
        "NR. CRT.", "NUME SI PRENUME ARENDATOR", "TERENURI (Tarla/Parcelă)", "CNP/CUI",
        "NR./DATA CONTRACT", "DURATA (ANI)", "SUPRAFATA TOTALA (Ha)", "Arabil (ha)",
        "Pasuni", "Fanete", "Vii", "Alte cat.", "Pruni", "TITULAR REGISTRUL AGRICOL",
    ]
    table = doc.add_table(rows=1, cols=len(capete))
    table.style = "Table Grid"
    for celula, text in zip(table.rows[0].cells, capete):
        celula.text = text
        for run in celula.paragraphs[0].runs:
            run.font.bold = True
            run.font.size = Pt(8)

    total_general = calcule.ZERO
    nr_crt = 1
    for om in sorted(arendasi, key=lambda x: _txt(x.nume_complet).lower()):
        if (om.stare or "activ") == "reziliat":
            continue  # tabelul centralizator cuprinde doar contractele în vigoare
        suprafata = calcule.suprafata_totala(om.terenuri)
        if suprafata <= 0:
            continue
        total_general += suprafata

        cells = table.add_row().cells
        cells[0].text = str(nr_crt)
        cells[1].paragraphs[0].add_run(_txt(om.nume_complet, "-")).font.bold = True
        cells[2].text = "\n".join(
            f"T. {_txt(t.tarlaua, '...')}, P. {_txt(t.parcela, '...')} ({calcule.rotunjeste_ha(t.suprafata_ha):.2f} ha)"
            for t in om.terenuri
        )
        cells[3].text = _txt(om.cnp, "..............")
        cells[4].text = _txt(om.nr_data_contract, "......./..........")
        cells[5].text = _txt(om.durata_contract, "7")
        cells[6].text = f"{suprafata:.4f}"
        cells[7].text = f"{suprafata:.4f}"
        for i in range(8, 13):
            cells[i].text = "-"
        cells[13].text = _txt(om.nume_complet, "-")

        for cell in cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    if not run.font.bold:
                        run.font.size = Pt(9)
        nr_crt += 1

    total = table.add_row().cells
    total[1].text = "TOTAL"
    total[6].text = f"{calcule.rotunjeste_ha(total_general):.4f}"
    total[7].text = f"{calcule.rotunjeste_ha(total_general):.4f}"
    for cell in total:
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(9)

    doc.add_paragraph("\n")
    p_semn = doc.add_paragraph()
    p_semn.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_semn.add_run("SECRETAR GENERAL,\nVÎNĂTORU DRAGOȘ-VICTOR").bold = True

    return _bytes(doc)


# ------------------------------------------------------------------ Borderou Excel
def borderou_excel(arendasi, an: int) -> bytes:
    """Formulele fiscale sunt IDENTICE cu versiunea inițială (cerință explicită). Singura diferență:
    suprafața totală e adunată exact (Decimal) înainte de a intra în formulă."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws_grau = wb.create_sheet(f"Grâu {an}")
    ws_porumb = wb.create_sheet(f"Porumb {an}")

    headers = [
        "NR. CRT.", "NUME SI PRENUME", "LOCALITATE", "SUPRAFATA HA",
        "CANTIT. BRUTA KG", "CANT. DUPA DED. 40%", "IMPOZIT 10%",
        "CANTITA NETA", "VALOARE TVA", "CANTITATE PRIMITA", "SEMNATURA",
    ]
    bold = Font(bold=True)
    antet_fill = PatternFill("solid", fgColor="E8F0EA")
    subtire = Side(style="thin", color="B7C4BB")
    chenar = Border(left=subtire, right=subtire, top=subtire, bottom=subtire)

    ws_bani = wb.create_sheet(f"Bani {an}")
    headers_bani = [
        "NR. CRT.", "NUME SI PRENUME", "LOCALITATE", "SUPRAFATA HA",
        "CANTIT. BRUTA KG", "PRET LEI/KG", "SUMA BRUTA LEI", "SUMA DUPA DED. 40%", "IMPOZIT 10%",
        "SUMA NETA", "VALOARE TVA", "SUMA PRIMITA", "ACHITAT LEI", "SEMNATURA",
    ]

    def setup_sheet(ws, titlu, capete, latimi):
        ws.append([FIRMA_NUME])
        ws.append([f"C.F. {FIRMA_CUI}"])
        ws.append([f"BORDEROU PRIVIND PLATA ARENDEI ({titlu}) PENTRU ANUL AGRICOL {an}"])
        ws.append([])
        ws.append(capete)
        for r in range(1, 4):
            ws.cell(row=r, column=1).font = bold
        for c in range(1, len(capete) + 1):
            cell = ws.cell(row=5, column=c)
            cell.font = bold
            cell.fill = antet_fill
            cell.border = chenar
            cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        for i, w in enumerate(latimi, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A6"

    latimi_cereale = [8, 32, 22, 13, 14, 14, 12, 13, 12, 15, 18]
    setup_sheet(ws_grau, "GRÂU", headers, latimi_cereale)
    setup_sheet(ws_porumb, "PORUMB", headers, latimi_cereale)
    setup_sheet(ws_bani, "ÎN BANI", headers_bani, [8, 32, 22, 13, 14, 12, 14, 14, 12, 14, 12, 14, 14, 18])

    nr = {"grau": 1, "porumb": 1, "bani": 1}
    for om in arendasi:
        if not calcule.activ_in_an(om, an):
            continue
        suprafata_totala = float(calcule.suprafata_totala(om.terenuri))
        if suprafata_totala == 0:
            continue
        tip_cereala = calcule.cereala_pentru_an(om.preferinte, an)
        if tip_cereala == "bani":
            _rand_bani(ws_bani, nr["bani"], om, an, suprafata_totala, chenar)
            nr["bani"] += 1
            continue
        cheie = "grau" if tip_cereala == "grau" else "porumb"

        # --- formule păstrate exact ---
        cant_bruta = round(suprafata_totala * float(KG_PER_HA))
        cant_dupa_ded = round(cant_bruta * 60 / 100)
        impozit = round(cant_dupa_ded * 10 / 100)
        cant_neta = cant_bruta - impozit
        valoare_tva = round(cant_neta * 11 / 100)
        cantitate_primita = cant_neta + valoare_tva

        ws = ws_grau if cheie == "grau" else ws_porumb
        ws.append([
            nr[cheie], _txt(om.nume_complet, "-"), calcule.extrage_localitate(om.adresa),
            round(suprafata_totala, 3), cant_bruta, cant_dupa_ded, impozit,
            cant_neta, valoare_tva, cantitate_primita, "",
        ])
        for cell in ws[ws.max_row]:
            cell.border = chenar
        nr[cheie] += 1

    return _bytes(wb)


def _lei2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rand_bani(ws, nr_crt, om, an, suprafata_totala, chenar) -> None:
    """Aceeași structură de calcul ca la cereale (deducere 40%, impozit 10%, TVA 11%), aplicată pe lei.
    Prețul/kg = media ponderată a plăților în bani din anul respectiv (preț introdus la fiecare plată)."""
    cant_bruta = round(suprafata_totala * float(KG_PER_HA))
    plati_bani = [p for p in om.plati if p.anul_agricol == an and (p.tip_plata or "natura") == "bani"]
    kg_bani = sum((calcule.to_decimal(p.cantitate_kg) for p in plati_bani), calcule.ZERO)
    lei_achitat = _lei2(sum((calcule.to_decimal(p.suma_lei) for p in plati_bani), calcule.ZERO))
    pret = (lei_achitat / kg_bani).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if kg_bani > 0 else None

    rand = [nr_crt, _txt(om.nume_complet, "-"), calcule.extrage_localitate(om.adresa),
            round(suprafata_totala, 3), cant_bruta]
    if pret is None:
        # fără plată în bani încă: prețul nu e cunoscut, sumele rămân de completat
        rand += ["", "", "", "", "", "", "", float(lei_achitat), ""]
    else:
        suma_bruta = _lei2(Decimal(cant_bruta) * pret)
        suma_dupa_ded = _lei2(suma_bruta * 60 / 100)
        impozit = _lei2(suma_dupa_ded * 10 / 100)
        suma_neta = suma_bruta - impozit
        valoare_tva = _lei2(suma_neta * 11 / 100)
        suma_primita = suma_neta + valoare_tva
        rand += [float(pret), float(suma_bruta), float(suma_dupa_ded), float(impozit), float(suma_neta),
                 float(valoare_tva), float(suma_primita), float(lei_achitat), ""]
    ws.append(rand)
    for i, cell in enumerate(ws[ws.max_row], start=1):
        cell.border = chenar
        if 6 <= i <= 13:
            cell.number_format = "#,##0.0000" if i == 6 else "#,##0.00"


# ------------------------------------------------------------------ Contract rapid
def _inlocuieste_in_paragraf(paragraph, placeholders: dict) -> None:
    """Înlocuiește placeholder-ele păstrând formatarea (bold, font) a run-ului în care începe
    fiecare placeholder; funcționează și când Word a spart placeholder-ul în mai multe run-uri."""
    for cheie, valoare in placeholders.items():
        cauta_de_la = 0  # nu re-scanăm textul inserat (ex. o adresă care conține "{{")
        while True:
            runs = paragraph.runs
            text_complet = "".join(r.text for r in runs)
            start = text_complet.find(cheie, cauta_de_la)
            if start < 0:
                break
            cauta_de_la = start + len(valoare)
            end = start + len(cheie)
            poz = 0
            run_start = run_end = None
            for i, r in enumerate(runs):
                lungime = len(r.text)
                if run_start is None and poz + lungime > start:
                    run_start, off_start = i, start - poz
                if poz + lungime >= end:
                    run_end, off_end = i, end - poz
                    break
                poz += lungime
            if run_start is None or run_end is None:
                break
            if run_start == run_end:
                r = runs[run_start]
                r.text = r.text[:off_start] + valoare + r.text[off_end:]
            else:
                runs[run_start].text = runs[run_start].text[:off_start] + valoare
                for r in runs[run_start + 1:run_end]:
                    r.text = ""
                runs[run_end].text = runs[run_end].text[off_end:]
            _font_contract(runs[run_start])


FONT_CONTRACT = "Times New Roman"


def _font_contract(run) -> None:
    """Textul completat de aplicație folosește același font ca restul contractului."""
    run.font.name = FONT_CONTRACT
    rfonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    for atribut in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(atribut), FONT_CONTRACT)


def _paragrafe(doc):
    yield from doc.paragraphs
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from cell.paragraphs
    for section in doc.sections:
        for parte in (section.header, section.footer):
            yield from parte.paragraphs


def contract_rapid(date: schemas.ContractRapidCreate) -> bytes:
    gen, domiciliat, identificat = calcule.gen_din_cnp(date.cnp)

    linii, total_ha = [], calcule.ZERO
    for t in date.terenuri:
        total_ha += t.ha
        linii.append(f"- Tarlaua {t.tarla}, parcela {t.parcela}, în suprafață de {calcule.ha_in_mp(t.ha)} mp")

    placeholders = {
        "{{GEN}}": gen,
        "{{NUME}}": date.nume.title(),
        "{{DOMICILIAT}}": domiciliat,
        "{{IDENTIFICAT}}": identificat,
        "{{adresa}}": date.adresa,
        "{{CNP}}": date.cnp or "....................",
        "{{SERIA}}": date.ci_seria.upper(),
        "{{NR_CI}}": date.ci_numar,
        "{{ELIBERAT}}": date.ci_eliberat.upper(),
        "{{DATA_CI}}": date.ci_data,
        "{{HA}}": f"{calcule.rotunjeste_ha(total_ha):.2f}",
        "{{LISTA_TERENURI}}": "\n".join(linii) if linii else "Nu a fost adăugat niciun teren.",
    }

    doc = Document(str(TEMPLATE_CONTRACT))
    for p in _paragrafe(doc):
        if "{{" in p.text:
            _inlocuieste_in_paragraf(p, placeholders)
    return _bytes(doc)


def contract_pentru_arendas(om) -> bytes:
    """Contract nou din șablon, completat cu datele unui arendaș din baza de date (ex. moștenitorul)."""
    date = schemas.ContractRapidCreate(
        nume=om.nume_complet,
        cnp=om.cnp,
        adresa=om.adresa or "...",
        ci_seria=om.ci_seria or "...",
        ci_numar=om.ci_numar or "...",
        ci_eliberat=om.ci_eliberat or "...",
        ci_data=om.ci_data or "...",
        terenuri=[schemas.TerenRapid(tarla=t.tarlaua or "...", parcela=t.parcela or "...",
                                     ha=calcule.rotunjeste_ha(t.suprafata_ha)) for t in om.terenuri],
    )
    return contract_rapid(date)


# ------------------------------------------------------------------ Act adițional de reziliere
def _doc_times(marime: int = 12) -> Document:
    doc = Document()
    stil = doc.styles["Normal"]
    stil.font.name = FONT_CONTRACT
    stil.font.size = Pt(marime)
    stil.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT_CONTRACT)
    stil.paragraph_format.space_after = Pt(0)
    s = doc.sections[0]
    s.left_margin = s.right_margin = Cm(2.5)
    s.top_margin = s.bottom_margin = Cm(2)
    return doc


def _p(doc, *bucati, align=None, indent_cm=None, spatiu_dupa=0):
    """Adaugă un paragraf din bucăți (text, bold)."""
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    if indent_cm is not None:
        p.paragraph_format.first_line_indent = Cm(indent_cm)
    p.paragraph_format.space_after = Pt(spatiu_dupa)
    for b in bucati:
        text, bold = (b, False) if isinstance(b, str) else b
        p.add_run(text).bold = bold
    return p


def act_reziliere(om, cerere: schemas.RezilieRequest) -> bytes:
    """Act adițional de reziliere, după modelul folosit la Primăria Argetoaia."""
    pers = cerere.semnatar or om  # la deces semnează moștenitorul
    gen, domiciliat, identificat = calcule.gen_din_cnp(pers.cnp)
    nr, data = calcule.nr_si_data_contract(om.nr_data_contract)
    contract = f"Contractul de arendare nr. {nr} / {data}"
    seria = _txt(pers.ci_seria, "....")
    numar = _txt(pers.ci_numar, "...........")
    data_ef = cerere.data_reziliere.strftime("%d.%m.%Y") if cerere.data_reziliere else "_________"
    J = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc = _doc_times()
    _p(doc, "PRIMARIA COMUNEI ARGETOAIA,")
    _p(doc, "JUDETUL DOLJ")
    _p(doc, "NR. .............................din Registrul arendelor", spatiu_dupa=36)

    _p(doc, ("ACT ADIȚIONAL NR.       /", True), align=WD_ALIGN_PARAGRAPH.CENTER)
    _p(doc, "la Contract de arendare", align=WD_ALIGN_PARAGRAPH.CENTER)
    _p(doc, f"înregistrat la Primăria Argetoaia sub nr.  {nr} / {data}", align=WD_ALIGN_PARAGRAPH.CENTER, spatiu_dupa=36)

    _p(doc, "I.. ", ("PARTILE CONTRACTANTE", True))
    _p(doc, ("1", True), f". Intre {gen} {_txt(pers.nume_complet)} {domiciliat} {_txt(pers.adresa, '....................')}, "
       f"{identificat} cu CI seria {seria}, nr. {numar}, proprietar/moștenitor al terenului, in calitate de ",
       ("arendator", True), ",", align=J, indent_cm=2)
    _p(doc, " și")
    _p(doc, ("2", True), f". Subscrisa SILMAR SOLUTION SRL, cu sediul în comuna Argetoaia, sat Poiana Fîntînii, "
       f"str. Bălăcești, nr. 51, județul Dolj, CUI {FIRMA_CUI} , în calitate de ", ("arendas", True), ",",
       align=J, indent_cm=2)
    _p(doc, f"Am convenit încheierea prezentului act adițional la {contract} cu respectarea prevederilor "
       "Legii 287/2009 privind Codul civil prin care stabilim :", align=J, indent_cm=1.25, spatiu_dupa=12)

    motiv = cerere.motiv_text.rstrip(".")
    _p(doc, "-   ", ("REZILIEREA", True), f" de comun acord a Contractului de arendare nr. {nr} / {data} ca urmare a {motiv}.",
       align=J, indent_cm=1.25, spatiu_dupa=12)
    _p(doc, f"Prezentul act adițional modifică {contract} începând cu data de {data_ef}, "
       "pentru care suntem de acord și semnăm.", align=J, indent_cm=1.25, spatiu_dupa=36)

    semn = doc.add_table(rows=1, cols=2)
    for cell, text in zip(semn.rows[0].cells, ("ARENDAȘ", "ARENDATOR,")):
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(text).bold = True
    return _bytes(doc)


# ------------------------------------------------------------------ CSV
def csv_arendasi(arendasi, an: int) -> bytes:
    import csv

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Nume", "CNP/CUI", "Localitate", "Nr./data contract", "Durata (ani)",
                "Nr. terenuri", "Suprafata (ha)", f"Cereala {an}", "Datorat (kg)", "Platit (kg)", "Rest (kg)", "Stare"])
    for om in sorted(arendasi, key=lambda x: _txt(x.nume_complet).lower()):
        ha = calcule.suprafata_totala(om.terenuri)
        dat = calcule.kg_datorat(ha)
        plat = calcule.kg_platit(om.plati, an)
        w.writerow([
            _txt(om.nume_complet), _txt(om.cnp), calcule.extrage_localitate(om.adresa),
            _txt(om.nr_data_contract), _txt(om.durata_contract, "7"), len(om.terenuri),
            f"{ha:.4f}".replace(".", ","), calcule.cereala_pentru_an(om.preferinte, an),
            f"{dat:.2f}".replace(".", ","), f"{plat:.2f}".replace(".", ","),
            f"{dat - plat:.2f}".replace(".", ","),
            "reziliat " + om.data_reziliere.strftime("%d.%m.%Y") if (om.stare == "reziliat" and om.data_reziliere) else (om.stare or "activ"),
        ])
    # BOM ca Excel să recunoască diacriticele
    return ("﻿" + buf.getvalue()).encode("utf-8")
