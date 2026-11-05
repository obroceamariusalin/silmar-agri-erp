// Modale de lucru: dosar arendaș, adăugare arendaș (cu import PDF), contract rapid, editare teren.
import { api, descarca } from "./api.js";
import { randeazaIstoric, rezilieazaDialog, transferDialog } from "./reziliere.js";
import {
  eroareIdentificator, eroareSuprafata, fmtData, fmtHa, fmtKg, fmtLei, fmtNumHa, fmtPret, initiale, parseNr, sumHa,
} from "./format.js";
import {
  cereala, datorat, getArendas, onChange, platit, rest, stergeArendasLocal, store, upsertArendas, aniDisponibili,
  leiPlatit, memoreazaPret, ultimulPret,
} from "./store.js";
import {
  $$, ETICHETA_CEREALA, aratoEroriServer, badgeCereala, badgeStatusContract, confirma, cuIncarcare, curataErori, eroare, eroareCamp,
  field, html, icon, ok, openModal, render, valori,
} from "./ui.js";

// ================================================================ Editor rânduri teren (reutilizat)
function randTeren(prefix, i, t = {}, chei = ["tarlaua", "parcela", "suprafata_ha"]) {
  const [kT, kP, kH] = chei;
  return html`
    <div class="teren-row" data-row>
      <div class="field"><input class="input input-sm" name="${prefix}.${i}.${kT}" value="${t[kT] ?? ""}" placeholder="ex: 129" aria-label="Tarla"><div class="field-error" data-error-for="${prefix}.${i}.${kT}"></div></div>
      <div class="field"><input class="input input-sm" name="${prefix}.${i}.${kP}" value="${t[kP] ?? ""}" placeholder="ex: 12/1" aria-label="Parcelă"><div class="field-error" data-error-for="${prefix}.${i}.${kP}"></div></div>
      <div class="field"><input class="input input-sm" name="${prefix}.${i}.${kH}" value="${t[kH] ?? ""}" placeholder="0,0000" inputmode="decimal" aria-label="Suprafață (ha)" data-ha><div class="field-error" data-error-for="${prefix}.${i}.${kH}"></div></div>
      <button type="button" class="btn btn-ghost btn-sm btn-icon btn-danger-soft" data-del-row aria-label="Elimină">${icon("trash3")}</button>
    </div>`;
}

function editorTerenuri(root, prefix, initiale = [], chei, laSchimbare) {
  const box = root.querySelector("[data-teren-rows]");
  let n = 0;
  const adauga = (t = {}) => {
    box.insertAdjacentHTML("beforeend", String(randTeren(prefix, n++, t, chei)));
    // amânat: la construcție, apelantul încă nu are referința la editor
    if (laSchimbare) queueMicrotask(laSchimbare);
  };
  initiale.forEach(adauga);
  root.querySelector("[data-add-row]").addEventListener("click", () => {
    adauga();
    box.lastElementChild?.querySelector("input")?.focus();
  });
  box.addEventListener("click", (e) => {
    if (e.target.closest("[data-del-row]")) { e.target.closest("[data-row]").remove(); laSchimbare?.(); }
  });
  box.addEventListener("input", (e) => { if (e.target.matches("[data-ha]")) laSchimbare?.(); });
  return {
    adauga,
    reset: (lista = []) => { box.innerHTML = ""; n = 0; lista.forEach(adauga); },
    citeste: () => $$("[data-row]", box).map((row) => {
      const ins = row.querySelectorAll("input");
      return { [chei[0]]: ins[0].value.trim(), [chei[1]]: ins[1].value.trim(), [chei[2]]: ins[2].value.trim().replace(",", "."), _nume: [...ins].map((x) => x.name) };
    }),
    totalHa: () => sumHa($$("[data-ha]", box).map((x) => parseFloat(x.value.replace(",", ".")) || 0)),
  };
}

/** Validare locală instant a rândurilor; întoarce true dacă există erori. */
function valideazaRanduri(root, randuri, chei, obligatorii = true) {
  let are = false;
  randuri.forEach((r) => {
    const gol = !r[chei[0]] && !r[chei[1]] && !r[chei[2]];
    if (gol && !obligatorii) return;
    if (obligatorii && !r[chei[0]]) are = eroareCamp(root, r._nume[0], "Obligatoriu") || are;
    if (obligatorii && !r[chei[1]]) are = eroareCamp(root, r._nume[1], "Obligatoriu") || are;
    const e = (obligatorii || r[chei[2]]) ? eroareSuprafata(r[chei[2]]) : null;
    if (e) are = eroareCamp(root, r._nume[2], e) || are;
  });
  return are;
}

// ================================================================ Adaugă arendaș
export function adaugaArendas() {
  const m = openModal({
    title: "Arendaș nou", sub: "Completează manual sau importă datele dintr-un contract PDF.",
    iconName: "person-plus", size: "lg",
    body: html`
      <label class="dropzone" data-drop>
        ${icon("file-earmark-arrow-up")}
        <div><div class="t">Autocompletare din contract PDF</div><div class="small muted">Trage fișierul aici sau apasă pentru a-l alege</div></div>
        <input type="file" accept="application/pdf,.pdf" data-pdf>
      </label>
      <div data-pdf-status style="margin-top:10px"></div>
      <form class="form-grid" style="margin-top:16px" novalidate data-form>
        <div class="form-section">Date personale</div>
        ${field({ name: "nume_complet", label: "Nume complet", placeholder: "ex: Ion Popescu", required: true, col: 6, attrs: "autofocus" })}
        ${field({ name: "cnp", label: "CNP / CUI", placeholder: "Opțional", hint: "Se validează cifra de control", col: 6, inputmode: "numeric" })}
        ${field({ name: "adresa", label: "Adresă", placeholder: "ex: Comuna Argetoaia, Sat Salcia, nr. 12", col: 12 })}
        ${field({ name: "nr_data_contract", label: "Nr. / dată contract", placeholder: "ex: 122/23.11.2017", col: 8 })}
        ${field({ name: "durata_contract", label: "Durată (ani)", value: "7", col: 4, inputmode: "numeric" })}
        <div class="form-section">Carte de identitate (opțional)</div>
        ${field({ name: "ci_seria", label: "Seria", col: 3, placeholder: "DZ" })}
        ${field({ name: "ci_numar", label: "Număr", col: 3, inputmode: "numeric" })}
        ${field({ name: "ci_eliberat", label: "Eliberat de", col: 3 })}
        ${field({ name: "ci_data", label: "Data eliberării", col: 3, placeholder: "zz.ll.aaaa" })}
        <div class="form-section">Terenuri</div>
        <div class="col-12">
          <div class="teren-row-head"><span>Tarla</span><span>Parcelă</span><span>Suprafață (ha)</span><span></span></div>
          <div class="teren-rows" data-teren-rows style="margin-top:6px"></div>
          <div class="row" style="margin-top:10px">
            <button type="button" class="btn btn-sm" data-add-row>${icon("plus-lg")} Adaugă teren</button>
            <span class="spacer"></span><span class="muted small">Total: <b class="num" data-total>0,0000 ha</b></span>
          </div>
        </div>
      </form>`,
    footer: html`<button class="btn" data-close>Renunță</button><button class="btn btn-primary" data-save>${icon("check2")} Salvează arendaș</button>`,
  });
  const form = m.$("[data-form]");
  const total = m.$("[data-total]");
  const ed = editorTerenuri(form, "terenuri", [], ["tarlaua", "parcela", "suprafata_ha"], () => (total.textContent = fmtHa(ed.totalHa())));

  // --- import PDF
  const drop = m.$("[data-drop]");
  const inputPdf = m.$("[data-pdf]");
  const status = m.$("[data-pdf-status]");
  const proceseaza = async (file) => {
    if (!file) return;
    render(status, html`<div class="callout">${icon("hourglass-split")} Se citește <b>${file.name}</b>…</div>`);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const d = await api.post("/api/extrage-contract", fd);
      if (d.nume) form.nume_complet.value = d.nume;
      if (d.adresa) form.adresa.value = d.adresa;
      ed.reset(d.terenuri);
      render(status, d.terenuri.length
        ? html`<div class="callout">${icon("check-circle")} <div>Am extras <b>${d.nume || "datele"}</b> și <b>${d.terenuri.length}</b> terenuri (${fmtHa(ed.totalHa())}). Verifică-le înainte de salvare.</div></div>`
        : html`<div class="callout warn">${icon("exclamation-circle")} <div>Datele personale au fost extrase, dar nu am identificat parcelele. Adaugă-le manual.</div></div>`);
    } catch (err) {
      render(status, html`<div class="callout warn">${icon("exclamation-circle")} <div>${err.message}</div></div>`);
    }
  };
  inputPdf.addEventListener("change", () => proceseaza(inputPdf.files[0]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); proceseaza(e.dataTransfer.files[0]); });

  m.$("[data-save]").addEventListener("click", (e) => cuIncarcare(e.currentTarget, async () => {
    curataErori(form);
    const v = valori(form);
    const randuri = ed.citeste().filter((r) => r.tarlaua || r.parcela || r.suprafata_ha);
    let are = false;
    if (!v.nume_complet.trim()) are = eroareCamp(form, "nume_complet", "Numele este obligatoriu.");
    const eCnp = eroareIdentificator(v.cnp);
    if (eCnp) are = eroareCamp(form, "cnp", eCnp);
    if (valideazaRanduri(form, randuri, ["tarlaua", "parcela", "suprafata_ha"])) are = true;
    if (are) return toastValidare(form);
    try {
      const om = await api.post("/api/arendasi", { ...v, terenuri: randuri.map(({ _nume, ...t }) => t) });
      upsertArendas(om);
      m.close();
      ok("Arendaș adăugat", `${om.nume_complet} · ${fmtHa(om.suprafata_totala)}`);
      deschideDosar(om.id);
    } catch (err) {
      aratoEroriServer(form, err);
    }
  }));
}

function toastValidare(form) {
  form.querySelector("[aria-invalid='true']")?.focus();
}

// ================================================================ Contract rapid
export function contractRapid() {
  const m = openModal({
    title: "Contract rapid", sub: "Generează instant contractul Word, gata de semnat.", iconName: "lightning-charge", size: "lg",
    body: html`
      <form class="form-grid" novalidate data-form>
        <div class="form-section">Arendator</div>
        ${field({ name: "nume", label: "Nume complet", required: true, col: 6, placeholder: "Ion Popescu", attrs: "autofocus" })}
        ${field({ name: "cnp", label: "CNP", col: 6, placeholder: "13 cifre", inputmode: "numeric", hint: "Determină automat domnul/doamna" })}
        ${field({ name: "adresa", label: "Adresă domiciliu", col: 12, placeholder: "Comuna X, Sat Y, Strada Z" })}
        <div class="form-section">Carte de identitate</div>
        ${field({ name: "ci_seria", label: "Seria", col: 3, placeholder: "DX" })}
        ${field({ name: "ci_numar", label: "Număr", col: 3, placeholder: "123456", inputmode: "numeric" })}
        ${field({ name: "ci_eliberat", label: "Eliberat de", col: 3, placeholder: "SPCLEP Craiova" })}
        ${field({ name: "ci_data", label: "Data eliberării", col: 3, placeholder: "zz.ll.aaaa" })}
        <div class="form-section">Terenuri arendate</div>
        <div class="col-12">
          <div class="teren-row-head"><span>Tarla</span><span>Parcelă</span><span>Suprafață (ha)</span><span></span></div>
          <div class="teren-rows" data-teren-rows style="margin-top:6px"></div>
          <div class="row" style="margin-top:10px">
            <button type="button" class="btn btn-sm" data-add-row>${icon("plus-lg")} Adaugă teren</button>
            <span class="spacer"></span><span class="muted small">Total: <b class="num" data-total>0,0000 ha</b></span>
          </div>
        </div>
        <label class="check col-12" style="margin-top:4px"><input type="checkbox" name="salveaza"> Salvează și ca arendaș nou în baza de date</label>
      </form>`,
    footer: html`<button class="btn" data-close>Renunță</button><button class="btn btn-primary" data-gen>${icon("file-earmark-word")} Generează contract</button>`,
  });
  const form = m.$("[data-form]");
  const total = m.$("[data-total]");
  const ed = editorTerenuri(form, "terenuri", [{}], ["tarla", "parcela", "ha"], () => (total.textContent = fmtHa(ed.totalHa())));

  m.$("[data-gen]").addEventListener("click", (e) => cuIncarcare(e.currentTarget, async () => {
    curataErori(form);
    const v = valori(form);
    const randuri = ed.citeste().filter((r) => r.tarla || r.parcela || r.ha);
    let are = false;
    if (!v.nume.trim()) are = eroareCamp(form, "nume", "Numele este obligatoriu.");
    const eCnp = eroareIdentificator(v.cnp);
    if (eCnp) are = eroareCamp(form, "cnp", eCnp);
    if (valideazaRanduri(form, randuri, ["tarla", "parcela", "ha"], false)) are = true;
    if (are) return toastValidare(form);
    const terenuri = randuri.map(({ _nume, ...t }) => t);
    try {
      await descarca("POST", "/api/contracte/rapid", { ...v, salveaza: undefined, terenuri }, "Contract.docx");
      if (v.salveaza) {
        const om = await api.post("/api/arendasi", {
          nume_complet: v.nume, cnp: v.cnp, adresa: v.adresa,
          ci_seria: v.ci_seria, ci_numar: v.ci_numar, ci_eliberat: v.ci_eliberat, ci_data: v.ci_data,
          terenuri: terenuri.filter((t) => t.tarla && t.parcela && Number(t.ha) > 0)
            .map((t) => ({ tarlaua: t.tarla, parcela: t.parcela, suprafata_ha: t.ha })),
        });
        upsertArendas(om);
        ok("Contract generat și arendaș salvat", om.nume_complet);
      } else {
        ok("Contract generat", "Fișierul Word a fost descărcat.");
      }
      m.close();
    } catch (err) {
      aratoEroriServer(form, err);
    }
  }));
}

// ================================================================ Editare teren
export function editeazaTeren(teren) {
  const m = openModal({
    title: "Editează teren", sub: `Proprietar: ${getArendas(teren.arendas_id)?.nume_complet || ""}`, iconName: "geo-alt", size: "sm",
    body: html`<form class="form-grid" novalidate data-form>
      ${field({ name: "tarlaua", label: "Tarla", value: teren.tarlaua, col: 6, required: true })}
      ${field({ name: "parcela", label: "Parcelă", value: teren.parcela, col: 6, required: true })}
      ${field({ name: "suprafata_ha", label: "Suprafață (ha)", value: fmtNumHa(teren.suprafata_ha).replace(/\./g, ""), col: 6, required: true, inputmode: "decimal", attrs: "autofocus" })}
      ${field({ name: "comuna", label: "Comuna", value: teren.comuna || "Argetoaia", col: 6 })}
    </form>`,
    footer: html`<button class="btn" data-close>Renunță</button><button class="btn btn-primary" data-save>Salvează</button>`,
  });
  const form = m.$("[data-form]");
  form.addEventListener("submit", (e) => { e.preventDefault(); m.$("[data-save]").click(); });
  m.$("[data-save]").addEventListener("click", (e) => cuIncarcare(e.currentTarget, async () => {
    curataErori(form);
    const v = valori(form);
    const eSup = eroareSuprafata(v.suprafata_ha);
    if (eSup) return eroareCamp(form, "suprafata_ha", eSup);
    try {
      upsertArendas(await api.patch(`/api/terenuri/${teren.id}`, { ...v, suprafata_ha: v.suprafata_ha.replace(",", ".") }));
      m.close();
      ok("Teren actualizat");
    } catch (err) { aratoEroriServer(form, err); }
  }));
}

// ================================================================ Dosar arendaș
export function deschideDosar(id, tabInitial = "date") {
  let tab = tabInitial;
  let documente = null;
  const m = openModal({
    size: "xl",
    header: html`<div class="dosar-head" data-head style="flex:1;min-width:0"></div>`,
    body: html`<div data-dosar></div>`,
    onClose: () => dezabonare(),
  });
  m.$(".modal-body").style.padding = "0";
  const dezabonare = onChange((motiv) => { if (motiv === "arendasi" || motiv === "an") deseneaza(); });

  function deseneaza() {
    const om = getArendas(id);
    if (!om) { m.close(); return; }
    const r = rest(om);
    render(m.$("[data-head]"), html`
      <div class="dosar-avatar">${initiale(om.nume_complet)}</div>
      <div style="min-width:0">
        <h3 style="font-size:18px">${om.nume_complet}</h3>
        <div class="row small muted" style="gap:8px;margin-top:3px">
          <span>${om.cnp ? `CNP/CUI ${om.cnp}` : "Fără CNP"}</span>·<span>${om.localitate || "Fără adresă"}</span>
          ${badgeStatusContract(om.status_contract, fmtData(om.data_expirare))}
        </div>
      </div>`);
    const precedent = om.arendas_precedent_id ? getArendas(om.arendas_precedent_id) : null;
    const succesori = store.arendasi.filter((a) => a.arendas_precedent_id === om.id);
    render(m.$("[data-dosar]"), html`
      ${om.stare === "reziliat" ? html`
        <div class="callout warn" style="margin:14px 22px 0;align-items:center;flex-wrap:wrap">
          ${icon("file-earmark-x")}
          <div style="flex:1;min-width:200px"><b>Contract reziliat</b> din ${fmtData(om.data_reziliere)}${om.motiv_reziliere ? ` — ca urmare a ${om.motiv_reziliere}` : ""}.
            ${succesori.length ? html`<br>Terenurile au trecut la ${succesori.map((s, i) => html`${i ? ", " : ""}<a href="#" data-dosar-link="${s.id}">${s.nume_complet}</a>`)}.` : ""}</div>
          <button class="btn btn-sm" data-reactiveaza>${icon("arrow-counterclockwise")} Anulează rezilierea</button>
        </div>` : ""}
      ${precedent ? html`<div class="callout" style="margin:14px 22px 0">${icon("diagram-2")}
        <div>Contract moștenit / preluat de la <a href="#" data-dosar-link="${precedent.id}">${precedent.nume_complet}</a>.</div></div>` : ""}
      <div class="mini-stats" style="${om.stare === "reziliat" || precedent ? "margin-top:14px;border-top:1px solid var(--border)" : ""}">
        <div class="mini-stat"><div class="l">Suprafață</div><div class="v">${fmtHa(om.suprafata_totala)}</div></div>
        <div class="mini-stat"><div class="l">Datorat ${store.an}</div><div class="v">${fmtKg(datorat(om))}</div></div>
        <div class="mini-stat"><div class="l">Plătit ${store.an}</div><div class="v" style="color:var(--ok)">${fmtKg(platit(om))}</div></div>
        <div class="mini-stat"><div class="l">Rest ${store.an}</div><div class="v" style="color:${r > 0 ? "var(--danger)" : "var(--ok)"}">${fmtKg(Math.max(r, 0))}</div></div>
      </div>
      <div class="tabs" role="tablist">
        ${[["date", "person-vcard", "Date & contract", null], ["terenuri", "map", "Terenuri", om.terenuri.length],
           ["plati", "cash-stack", "Plăți", om.plati.length], ["documente", "folder2-open", "Documente", documente?.length ?? null]]
          .map(([k, ic, l, c]) => html`<button class="tab ${tab === k ? "active" : ""}" role="tab" data-tab="${k}">${icon(ic)}${l}${c != null ? html`<span class="count">${c}</span>` : ""}</button>`)}
      </div>
      <div class="modal-pad" style="padding:20px 22px" data-panel></div>`);
    const panel = m.$("[data-panel]");
    ({ date: panelDate, terenuri: panelTerenuri, plati: panelPlati, documente: panelDocumente })[tab](panel, om);
  }

  m.el.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-tab]");
    if (t) { tab = t.dataset.tab; deseneaza(); return; }
    const link = e.target.closest("[data-dosar-link]");
    if (link) {
      e.preventDefault();
      m.close();
      deschideDosar(+link.dataset.dosarLink);
      return;
    }
    if (e.target.closest("[data-reactiveaza]")) {
      const om = getArendas(id);
      if (!(await confirma({ title: "Anulezi rezilierea?", confirmLabel: "Da, reactivează",
        message: `Contractul lui ${om.nume_complet} redevine activ. Terenurile transferate între timp NU se mută înapoi automat (le poți transfera manual).` }))) return;
      try { upsertArendas(await api.post(`/api/arendasi/${id}/reactivare`)); ok("Contract reactivat"); } catch (err) { eroare(err); }
    }
  });

  // ---------------- Date & contract
  function panelDate(panel, om) {
    render(panel, html`
      <form class="form-grid" novalidate data-form>
        ${field({ name: "nume_complet", label: "Nume complet", value: om.nume_complet, col: 6, required: true })}
        ${field({ name: "cnp", label: "CNP / CUI", value: om.cnp || "", col: 6, placeholder: "Necompletat", inputmode: "numeric" })}
        ${field({ name: "adresa", label: "Adresă", value: om.adresa || "", col: 12 })}
        ${field({ name: "nr_data_contract", label: "Nr. / dată contract", value: om.nr_data_contract || "", col: 6, placeholder: "ex: 122/23.11.2017", hint: om.data_expirare ? `Expiră la ${fmtData(om.data_expirare)}` : "Data din contract permite calculul expirării" })}
        ${field({ name: "durata_contract", label: "Durată (ani)", value: om.durata_contract || "7", col: 6, inputmode: "numeric" })}
        <div class="form-section">Carte de identitate</div>
        ${field({ name: "ci_seria", label: "Seria", value: om.ci_seria || "", col: 3, placeholder: "DZ" })}
        ${field({ name: "ci_numar", label: "Număr", value: om.ci_numar || "", col: 3, inputmode: "numeric" })}
        ${field({ name: "ci_eliberat", label: "Eliberat de", value: om.ci_eliberat || "", col: 3, placeholder: "SPCLEP Craiova" })}
        ${field({ name: "ci_data", label: "Data eliberării", value: om.ci_data || "", col: 3, placeholder: "zz.ll.aaaa" })}
        <div class="col-12 row"><span class="spacer"></span><button class="btn btn-primary" data-save>${icon("check2")} Salvează modificările</button></div>
      </form>
      <div class="card" style="box-shadow:none;margin-top:22px"><div class="card-body row" style="gap:10px">
        <div style="flex:1;min-width:200px"><div class="strong">Documente contract</div>
          <div class="small muted">Contract completat cu datele și terenurile din dosar · act adițional de reziliere</div></div>
        <button class="btn" data-gen-contract>${icon("file-earmark-word")} Generează contract</button>
        ${om.stare !== "reziliat" ? html`<button class="btn btn-danger-soft" data-reziliaza>${icon("file-earmark-x")} Reziliază contractul</button>` : ""}
      </div></div>
      <div class="danger-zone" style="margin-top:22px">
        <div style="flex:1;min-width:200px"><div class="strong">Șterge dosarul</div><div class="small muted">Se șterg definitiv terenurile, plățile și preferințele.</div></div>
        <button class="btn btn-danger-soft" data-delete>${icon("trash3")} Șterge dosar</button>
      </div>`);
    const form = panel.querySelector("[data-form]");
    form.addEventListener("submit", (e) => e.preventDefault());
    panel.querySelector("[data-save]").addEventListener("click", (e) => cuIncarcare(e.currentTarget, async () => {
      curataErori(form);
      const v = valori(form);
      const eCnp = eroareIdentificator(v.cnp);
      if (eCnp) return eroareCamp(form, "cnp", eCnp);
      try {
        upsertArendas(await api.patch(`/api/arendasi/${om.id}`, v));
        ok("Date salvate");
      } catch (err) { aratoEroriServer(form, err); }
    }));
    panel.querySelector("[data-gen-contract]").addEventListener("click", (e) => cuIncarcare(e.currentTarget, async () => {
      try {
        await descarca("GET", `/api/arendasi/${om.id}/contract`, undefined, `Contract_${om.nume_complet}.docx`);
        ok("Contract generat", om.ci_seria ? "" : "Completează datele din CI ca să apară în contract.");
      } catch (err) { eroare(err); }
    }));
    panel.querySelector("[data-reziliaza]")?.addEventListener("click", () => rezilieazaDialog(om));
    panel.querySelector("[data-delete]").addEventListener("click", async () => {
      const r = await confirma({
        title: "Ștergi dosarul?", danger: true, confirmLabel: "Șterge definitiv",
        message: `Dosarul lui ${om.nume_complet} va fi șters împreună cu ${om.terenuri.length} terenuri și ${om.plati.length} plăți. Acțiunea nu poate fi anulată.`,
        extra: html`<label class="check"><input type="checkbox" name="docs"> Șterge și documentele scanate din arhivă</label>`,
      });
      if (!r) return;
      try {
        const rez = await api.del(`/api/arendasi/${om.id}?sterge_documente=${r.docs ? "true" : "false"}`);
        stergeArendasLocal(om.id);
        ok("Dosar șters", rez.mesaj);
      } catch (err) { eroare(err); }
    });
  }

  // ---------------- Terenuri
  function panelTerenuri(panel, om) {
    const total = om.suprafata_totala;
    render(panel, html`
      <form class="row" style="align-items:flex-start;gap:8px;margin-bottom:16px" novalidate data-form>
        <div class="field" style="flex:1 1 90px"><label>Tarla</label><input class="input input-sm" name="tarlaua" placeholder="129"><div class="field-error" data-error-for="tarlaua"></div></div>
        <div class="field" style="flex:1 1 90px"><label>Parcelă</label><input class="input input-sm" name="parcela" placeholder="12/1"><div class="field-error" data-error-for="parcela"></div></div>
        <div class="field" style="flex:1 1 110px"><label>Suprafață (ha)</label><input class="input input-sm" name="suprafata_ha" placeholder="0,0000" inputmode="decimal"><div class="field-error" data-error-for="suprafata_ha"></div></div>
        <div class="field" style="flex:1 1 110px"><label>Comuna</label><input class="input input-sm" name="comuna" value="Argetoaia"></div>
        <div class="field" style="flex:0 0 auto"><label>&nbsp;</label><button class="btn btn-primary btn-sm" style="height:34px" data-add>${icon("plus-lg")} Adaugă</button></div>
      </form>
      ${om.terenuri.length ? html`
      <div class="card" style="box-shadow:none">
        <table class="dt">
          <thead><tr><th>Tarla</th><th>Parcelă</th><th>Comuna</th><th class="right">Suprafață</th><th class="right">Acțiuni</th></tr></thead>
          <tbody>${om.terenuri.map((t) => html`<tr>
            <td class="m-title" data-label="Tarla"><span class="cell-title">T. ${t.tarlaua || "—"}</span> <span class="cell-sub">· P. ${t.parcela || "—"}</span></td>
            <td class="m-hide" data-label="Parcelă">${t.parcela || "—"}</td>
            <td data-label="Comuna">${t.comuna || "—"}</td>
            <td class="right num" data-label="Suprafață">${fmtHa(t.suprafata_ha)}</td>
            <td class="right m-actions" data-label=""><div class="row-actions">
              <button class="btn btn-ghost btn-sm btn-icon" data-edit="${t.id}" aria-label="Editează">${icon("pencil")}</button>
              <button class="btn btn-ghost btn-sm btn-icon btn-danger-soft" data-del="${t.id}" aria-label="Șterge">${icon("trash3")}</button>
            </div></td></tr>`)}</tbody>
          <tfoot><tr><td data-label="">Total</td><td class="m-hide"></td><td></td><td class="right num" data-label="Suprafață">${fmtHa(total)}</td><td></td></tr></tfoot>
        </table>
      </div>` : html`<div class="dt-empty">${icon("map")}Niciun teren înregistrat.</div>`}
      ${om.terenuri.length ? html`<div class="row" style="margin-top:14px"><span class="spacer"></span>
        <button class="btn" data-transfer>${icon("arrow-left-right")} Transferă terenuri (moștenire / vânzare)</button></div>` : ""}
      <div data-istoric></div>`);
    panel.querySelector("[data-transfer]")?.addEventListener("click", () => transferDialog(om));
    randeazaIstoric(panel.querySelector("[data-istoric]"), om);
    const form = panel.querySelector("[data-form]");
    form.addEventListener("submit", (e) => { e.preventDefault(); panel.querySelector("[data-add]").click(); });
    panel.querySelector("[data-add]").addEventListener("click", (e) => { e.preventDefault(); cuIncarcare(e.currentTarget, async () => {
      curataErori(form);
      const v = valori(form);
      let are = false;
      if (!v.tarlaua.trim()) are = eroareCamp(form, "tarlaua", "Obligatoriu");
      if (!v.parcela.trim()) are = eroareCamp(form, "parcela", "Obligatoriu");
      const eSup = eroareSuprafata(v.suprafata_ha);
      if (eSup) are = eroareCamp(form, "suprafata_ha", eSup);
      if (are) return;
      try {
        upsertArendas(await api.post(`/api/arendasi/${om.id}/terenuri`, { ...v, suprafata_ha: v.suprafata_ha.replace(",", ".") }));
        ok("Teren adăugat", `T. ${v.tarlaua}, P. ${v.parcela}`);
        setTimeout(() => m.$("[data-panel] [name=tarlaua]")?.focus(), 50);
      } catch (err) { aratoEroriServer(form, err); }
    }); });
    panel.addEventListener("click", async (e) => {
      const ed = e.target.closest("[data-edit]");
      if (ed) return editeazaTeren(om.terenuri.find((t) => t.id === +ed.dataset.edit));
      const del = e.target.closest("[data-del]");
      if (!del) return;
      const t = om.terenuri.find((x) => x.id === +del.dataset.del);
      if (!(await confirma({ title: "Elimini terenul?", danger: true, confirmLabel: "Elimină", message: `Tarla ${t.tarlaua}, parcela ${t.parcela} (${fmtHa(t.suprafata_ha)}).` }))) return;
      try { upsertArendas(await api.del(`/api/terenuri/${t.id}`)); ok("Teren eliminat"); } catch (err) { eroare(err); }
    });
  }

  // ---------------- Plăți (în natură sau în bani)
  function panelPlati(panel, om) {
    const r = rest(om);
    const plati = [...om.plati].sort((a, b) => (b.anul_agricol - a.anul_agricol) || (b.data_operatiune || "").localeCompare(a.data_operatiune || ""));
    const cer = cereala(om);
    let tip = cer === "bani" ? "bani" : "natura";
    const lei = leiPlatit(om);
    render(panel, html`
      <div class="grid grid-2">
        <div class="card" style="box-shadow:none"><div class="card-body stack" style="gap:14px">
          <div class="row"><div class="strong">Ce primește în ${store.an}</div><span class="spacer"></span>
            <div class="segmented" role="group" aria-label="Tip arendă">
              ${["grau", "porumb", "bani"].map((c) => html`<button type="button" class="${cer === c ? "active" : ""}" data-cer="${c}">${ETICHETA_CEREALA[c]}</button>`)}
            </div>
          </div>
          <div class="small muted">${fmtHa(om.suprafata_totala)} × ${store.config.kg_per_ha} kg/ha = <b>${fmtKg(datorat(om))}</b>${cer === "bani" ? " (plătit în bani la prețul pe kg)" : ""}</div>
          ${lei > 0 ? html`<div class="small">💵 Plătit în bani în ${store.an}: <b class="num">${fmtLei(lei)}</b></div>` : ""}
          ${r > 0 ? html`<button class="btn btn-dark" data-full>${icon("check2-all")} Achită restul: ${fmtKg(r)}${cer === "bani" ? " în bani" : ""}</button>`
                  : html`<div class="badge badge-ok" style="align-self:flex-start">${icon("check-circle")} Achitat integral pentru ${store.an}</div>`}
        </div></div>
        <div class="card" style="box-shadow:none"><div class="card-body">
          <form class="form-grid" novalidate data-form>
            <div class="col-12 row">
              <span class="label">Plată nouă</span><span class="spacer"></span>
              <div class="segmented" role="group" aria-label="Mod de plată">
                <button type="button" data-tip="natura">🌾 În natură</button>
                <button type="button" data-tip="bani">💵 În bani</button>
              </div>
            </div>
            <div class="field col-6" data-grup="bani"><label for="f-pret">Preț (lei/kg)</label>
              <input class="input" id="f-pret" name="pret_lei_kg" inputmode="decimal" placeholder="ex: 1,10" value="${ultimulPret()}">
              <div class="field-error" data-error-for="pret_lei_kg"></div></div>
            <div class="field col-6" data-grup="bani"><label for="f-suma">Sumă (lei)</label>
              <input class="input" id="f-suma" name="suma_lei" inputmode="decimal" placeholder="0,00">
              <div class="field-error" data-error-for="suma_lei"></div></div>
            <div class="field col-6"><label for="f-kg" data-kg-label>Cantitate (kg)</label>
              <input class="input" id="f-kg" name="cantitate_kg" inputmode="decimal" placeholder="0">
              <div class="hint" data-grup="bani">Se calculează automat din sumă și preț (sau invers)</div>
              <div class="field-error" data-error-for="cantitate_kg"></div></div>
            <div class="field col-6"><label>An agricol</label><select class="select" name="anul_agricol">
              ${aniDisponibili().map((a) => html`<option value="${a}" ${a === store.an ? "selected" : ""}>${a}</option>`)}</select></div>
            ${field({ name: "observatii", label: "Observații", col: 12, placeholder: "Opțional (ex: livrat la domiciliu)" })}
            <div class="col-12"><button class="btn btn-primary btn-block" data-add>${icon("plus-lg")} Înregistrează plata</button></div>
          </form>
        </div></div>
      </div>
      <h4 style="margin:22px 0 10px;font-size:14px">Istoric plăți</h4>
      ${plati.length ? html`<div class="card" style="box-shadow:none"><table class="dt">
        <thead><tr><th>Data</th><th>An agricol</th><th>Tip</th><th>Observații</th><th class="right">Cantitate</th><th></th></tr></thead>
        <tbody>${plati.map((p) => html`<tr>
          <td class="m-title" data-label="Data"><span class="cell-title">${p.tip_plata === "bani" ? fmtLei(p.suma_lei) : fmtKg(p.cantitate_kg)}</span> <span class="cell-sub">· ${fmtData(p.data_operatiune)}</span></td>
          <td data-label="An agricol"><span class="badge badge-brand">${p.anul_agricol}</span></td>
          <td data-label="Tip">${badgeCereala(p.tip_plata === "bani" ? "bani" : p.produs)}
            ${p.tip_plata === "bani" ? html`<div class="cell-sub">${fmtLei(p.suma_lei)} · ${fmtPret(p.pret_lei_kg)}</div>` : ""}</td>
          <td data-label="Observații" class="small muted">${p.observatii || "—"}</td>
          <td class="right num strong m-hide" data-label="Cantitate" style="color:var(--ok)">+ ${fmtKg(p.cantitate_kg)}</td>
          <td class="right m-actions"><button class="btn btn-ghost btn-sm btn-icon btn-danger-soft" data-del="${p.id}" aria-label="Anulează plata">${icon("trash3")}</button></td>
        </tr>`)}</tbody></table></div>` : html`<div class="dt-empty">${icon("cash-stack")}Nicio plată înregistrată.</div>`}`);

    const form = panel.querySelector("[data-form]");
    form.addEventListener("submit", (e) => e.preventDefault());

    // --- comutare natură / bani
    const aplicaTip = () => {
      form.querySelectorAll("[data-tip]").forEach((b) => b.classList.toggle("active", b.dataset.tip === tip));
      form.querySelectorAll("[data-grup=bani]").forEach((el) => (el.hidden = tip !== "bani"));
      form.querySelector("[data-kg-label]").textContent = tip === "bani" ? "Echivalent (kg)" : "Cantitate (kg)";
      curataErori(form);
    };
    form.querySelectorAll("[data-tip]").forEach((b) => b.addEventListener("click", () => { tip = b.dataset.tip; aplicaTip(); }));
    aplicaTip();

    // --- calcul automat sumă <-> kg (ultimul câmp editat de utilizator câștigă)
    let ultim = "suma_lei";
    const recalc = () => {
      if (tip !== "bani") return;
      const pret = parseNr(form.pret_lei_kg.value);
      if (!(pret > 0)) return;
      if (ultim === "suma_lei") {
        const s = parseNr(form.suma_lei.value);
        form.cantitate_kg.value = s > 0 ? String(Math.round((s / pret) * 100) / 100).replace(".", ",") : "";
      } else {
        const kg = parseNr(form.cantitate_kg.value);
        form.suma_lei.value = kg > 0 ? (Math.round(kg * pret * 100) / 100).toFixed(2).replace(".", ",") : "";
      }
    };
    form.suma_lei.addEventListener("input", () => { ultim = "suma_lei"; recalc(); });
    form.cantitate_kg.addEventListener("input", () => { if (tip === "bani") { ultim = "cantitate_kg"; recalc(); } });
    form.pret_lei_kg.addEventListener("input", recalc);

    panel.querySelectorAll("[data-cer]").forEach((b) => b.addEventListener("click", async () => {
      try {
        upsertArendas(await api.post(`/api/arendasi/${om.id}/preferinte`, { anul_agricol: store.an, tip_cereala: b.dataset.cer }));
        ok("Preferință salvată", `${ETICHETA_CEREALA[b.dataset.cer]} pentru ${store.an}`);
      } catch (err) { eroare(err); }
    }));

    panel.querySelector("[data-full]")?.addEventListener("click", (e) => {
      const btn = e.currentTarget;
      if (cer !== "bani") {
        return cuIncarcare(btn, async () => {
          try {
            upsertArendas(await api.post(`/api/arendasi/${om.id}/plati`, { cantitate_kg: r.toFixed(2), anul_agricol: store.an, observatii: "Plată integrală" }));
            ok("Plată înregistrată", `${fmtKg(r)} pentru ${store.an}`);
          } catch (err) { eroare(err); }
        });
      }
      // în bani: cerem prețul, arătăm suma
      (async () => {
        const rez = await confirma({
          title: "Achiți restul în bani?", confirmLabel: "Înregistrează plata",
          message: `Rest de plată ${store.an}: ${fmtKg(r)}.`,
          extra: html`<div class="field"><label for="f-pret-full">Preț (lei/kg)</label>
            <input class="input" id="f-pret-full" name="pret" inputmode="decimal" placeholder="ex: 1,10" value="${ultimulPret()}" autofocus></div>`,
        });
        if (!rez) return;
        const pret = parseNr(rez.pret);
        if (!(pret > 0)) return eroare(new Error("Introdu un preț pe kg mai mare decât 0."), "Prețul lipsește");
        memoreazaPret(rez.pret);
        await cuIncarcare(btn, async () => {
          try {
            upsertArendas(await api.post(`/api/arendasi/${om.id}/plati`, {
              tip_plata: "bani", cantitate_kg: r.toFixed(2), pret_lei_kg: String(pret), anul_agricol: store.an, observatii: "Plată integrală în bani",
            }));
            ok("Plată în bani înregistrată", `${fmtLei(Math.round(r * pret * 100) / 100)} pentru ${store.an}`);
          } catch (err) { eroare(err); }
        });
      })();
    });

    panel.querySelector("[data-add]").addEventListener("click", (e) => { e.preventDefault(); cuIncarcare(e.currentTarget, async () => {
      curataErori(form);
      const v = valori(form);
      const kg = parseNr(v.cantitate_kg);
      const body = { anul_agricol: +v.anul_agricol, observatii: v.observatii, tip_plata: tip };
      if (tip === "natura") {
        if (!(kg > 0)) return eroareCamp(form, "cantitate_kg", "Introdu o cantitate mai mare decât 0.");
        body.cantitate_kg = String(kg);
      } else {
        const pret = parseNr(v.pret_lei_kg), suma = parseNr(v.suma_lei);
        if (!(pret > 0)) return eroareCamp(form, "pret_lei_kg", "Introdu prețul pe kg.");
        if (!(suma > 0) && !(kg > 0)) return eroareCamp(form, "suma_lei", "Introdu suma sau cantitatea echivalentă.");
        body.pret_lei_kg = String(pret);
        if (suma > 0) body.suma_lei = String(suma);
        if (kg > 0) body.cantitate_kg = String(kg);
        memoreazaPret(v.pret_lei_kg);
      }
      try {
        upsertArendas(await api.post(`/api/arendasi/${om.id}/plati`, body));
        ok("Plată înregistrată", tip === "bani" ? `${fmtLei(parseNr(v.suma_lei) || kg * parseNr(v.pret_lei_kg))} pentru ${v.anul_agricol}` : `${fmtKg(kg)} pentru ${v.anul_agricol}`);
      } catch (err) { aratoEroriServer(form, err); }
    }); });

    panel.addEventListener("click", async (e) => {
      const del = e.target.closest("[data-del]");
      if (!del) return;
      const p = om.plati.find((x) => x.id === +del.dataset.del);
      const descriere = p.tip_plata === "bani" ? `${fmtLei(p.suma_lei)} (${fmtKg(p.cantitate_kg)} echivalent)` : fmtKg(p.cantitate_kg);
      if (!(await confirma({ title: "Anulezi plata?", danger: true, confirmLabel: "Anulează plata", message: `${descriere} din ${fmtData(p.data_operatiune)} (anul ${p.anul_agricol}). Restul de plată va crește la loc.` }))) return;
      try { upsertArendas(await api.del(`/api/plati/${p.id}`)); ok("Plată anulată"); } catch (err) { eroare(err); }
    });
  }

  // ---------------- Documente
  function panelDocumente(panel, om) {
    render(panel, html`
      <label class="dropzone" data-drop>
        ${icon("cloud-arrow-up")}
        <div><div class="t">Încarcă documente</div><div class="small muted">Buletin, titlu de proprietate, contract — PDF, imagini sau Word (max. 15 MB). Poți selecta mai multe.</div></div>
        <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.doc,.docx,.xls,.xlsx" data-file>
      </label>
      <div data-up style="margin-top:10px"></div>
      <div data-list style="margin-top:14px">${documente ? "" : html`<div class="skeleton" style="height:58px"></div><div class="skeleton" style="height:58px;margin-top:8px"></div>`}</div>`);
    const lista = panel.querySelector("[data-list]");
    const deseneazaLista = () => {
      if (!documente) return;
      const icDoc = (f) => /pdf/i.test(f.format) ? ["", "file-earmark-pdf"] : /docx?|xlsx?/i.test(f.format) ? ["office", "file-earmark-word"] : ["img", "file-earmark-image"];
      render(lista, documente.length ? documente.map((f) => {
        const [cls, ic] = icDoc(f);
        return html`<div class="doc-item">
          <div class="doc-icon ${cls}">${icon(ic)}</div>
          <div style="flex:1;min-width:0"><div class="strong" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${f.nume}</div>
            <div class="small muted">${f.bytes ? `${(f.bytes / 1024 / 1024).toFixed(2)} MB` : ""} ${f.creat_la ? `· ${fmtData(f.creat_la)}` : ""}</div></div>
          <a class="btn btn-sm" href="${f.url}" target="_blank" rel="noopener">${icon("box-arrow-up-right")}<span class="hide-mobile">Deschide</span></a>
          <button class="btn btn-ghost btn-sm btn-icon btn-danger-soft" data-del-doc="${f.public_id}" data-rt="${f.resource_type}" aria-label="Șterge">${icon("trash3")}</button>
        </div>`;
      }) : html`<div class="dt-empty">${icon("folder2-open")}Niciun document în arhivă.</div>`);
    };
    const reincarca = async () => {
      try { documente = await api.get(`/api/arendasi/${om.id}/documente`); deseneazaLista(); actualizeazaCount(); }
      catch (err) { render(lista, html`<div class="callout warn">${icon("exclamation-circle")}${err.message}</div>`); }
    };
    const actualizeazaCount = () => {
      const t = m.$('[data-tab="documente"]');
      if (t && documente) render(t, html`${icon("folder2-open")}Documente<span class="count">${documente.length}</span>`);
    };
    if (documente) deseneazaLista(); else reincarca();

    const up = panel.querySelector("[data-up]");
    const incarca = async (files) => {
      for (const file of files) {
        render(up, html`<div class="callout">${icon("hourglass-split")} Se încarcă <b>${file.name}</b>…</div>`);
        const fd = new FormData();
        fd.append("file", file);
        try { await api.post(`/api/arendasi/${om.id}/documente`, fd); ok("Document încărcat", file.name); }
        catch (err) { eroare(err, `Nu am putut încărca ${file.name}`); }
      }
      up.innerHTML = "";
      await reincarca();
    };
    const drop = panel.querySelector("[data-drop]");
    panel.querySelector("[data-file]").addEventListener("change", (e) => incarca([...e.target.files]));
    drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("over"));
    drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); incarca([...e.dataTransfer.files]); });
    lista.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-del-doc]");
      if (!b) return;
      if (!(await confirma({ title: "Ștergi documentul?", danger: true, confirmLabel: "Șterge", message: "Documentul va fi șters definitiv din arhiva cloud." }))) return;
      try {
        await api.del(`/api/arendasi/${om.id}/documente?public_id=${encodeURIComponent(b.dataset.delDoc)}&resource_type=${b.dataset.rt}`);
        ok("Document șters");
        await reincarca();
      } catch (err) { eroare(err); }
    });
  }

  deseneaza();
  return m;
}

// ================================================================ Rapoarte
export async function descarcaRaport(tip, btn) {
  const map = {
    primarie: ["/api/rapoarte/tabel-primarie", "Tabel_Primarie.docx", "Tabelul pentru primărie a fost generat"],
    borderou: [`/api/rapoarte/borderou?an=${store.an}`, `Borderou_${store.an}.xlsx`, `Borderoul ${store.an} a fost generat`],
    csv: [`/api/rapoarte/arendasi.csv?an=${store.an}`, `Arendasi_${store.an}.csv`, "Exportul CSV a fost generat"],
  };
  const [url, nume, mesaj] = map[tip];
  await cuIncarcare(btn, async () => {
    try { await descarca("GET", url, undefined, nume); ok(mesaj); } catch (err) { eroare(err, "Generarea a eșuat"); }
  });
}

