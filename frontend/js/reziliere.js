// Reziliere de contract (act adițional), moștenire și transfer de terenuri.
import { api, descarca } from "./api.js";
import { collator, eroareIdentificator, fmtData, fmtHa, isoAzi, sumHa } from "./format.js";
import { store, upsertArendas } from "./store.js";
import { $$, aratoEroriServer, cuIncarcare, curataErori, eroare, eroareCamp, field, html, icon, ok, openModal, render } from "./ui.js";

const MOTIVE = {
  deces: { label: "Deces", icon: "flower3", text: (om) => `decesului arendatorului ${om.nume_complet}` },
  contract_nou: { label: "Contract nou cu alt arendator", icon: "arrow-left-right", text: () => "încheierii unui nou contract de arendare pentru terenul respectiv" },
  renuntare: { label: "Nu mai dorește să arendeze", icon: "hand-thumbs-down", text: () => "dorinței arendatorului de a nu mai arenda terenul" },
  alt: { label: "Alt motiv", icon: "pencil", text: () => "" },
};

/** Câmpuri persoană (nume, CNP, adresă, CI) cu prefix pentru maparea erorilor de pe server. */
function campuriPersoana(prefix, p = {}) {
  return html`
    ${field({ name: `${prefix}.nume_complet`, label: "Nume complet", value: p.nume_complet || "", col: 6, required: true })}
    ${field({ name: `${prefix}.cnp`, label: "CNP", value: p.cnp || "", col: 6, inputmode: "numeric", placeholder: "Opțional" })}
    ${field({ name: `${prefix}.adresa`, label: "Adresă domiciliu", value: p.adresa || "", col: 12 })}
    ${field({ name: `${prefix}.ci_seria`, label: "CI seria", value: p.ci_seria || "", col: 3, placeholder: "DZ" })}
    ${field({ name: `${prefix}.ci_numar`, label: "CI număr", value: p.ci_numar || "", col: 3, inputmode: "numeric" })}
    ${field({ name: `${prefix}.ci_eliberat`, label: "Eliberat de", value: p.ci_eliberat || "", col: 3 })}
    ${field({ name: `${prefix}.ci_data`, label: "Data eliberării", value: p.ci_data || "", col: 3, placeholder: "zz.ll.aaaa" })}`;
}

function citestePersoana(form, prefix) {
  const v = (k) => (form.elements[`${prefix}.${k}`]?.value || "").trim();
  return {
    nume_complet: v("nume_complet"), cnp: v("cnp"), adresa: v("adresa"),
    ci_seria: v("ci_seria"), ci_numar: v("ci_numar"), ci_eliberat: v("ci_eliberat"), ci_data: v("ci_data"),
  };
}

function valideazaPersoana(form, prefix, p) {
  let are = false;
  if (p.nume_complet.length < 2) are = eroareCamp(form, `${prefix}.nume_complet`, "Numele este obligatoriu.");
  const e = eroareIdentificator(p.cnp);
  if (e) are = eroareCamp(form, `${prefix}.cnp`, e);
  return are;
}

function optiuniArendasi(excludeId) {
  return store.arendasi
    .filter((a) => a.id !== excludeId && a.stare !== "reziliat")
    .sort((a, b) => collator.compare(a.nume_complet, b.nume_complet))
    .map((a) => html`<option value="${a.id}">${a.nume_complet}${a.cnp ? ` · ${a.cnp}` : ""}</option>`);
}

function listaTerenuri(om) {
  return om.terenuri.length
    ? html`<div class="stack" style="gap:6px">${om.terenuri.map((t) => html`
        <label class="check"><input type="checkbox" name="teren" value="${t.id}" checked>
          T. ${t.tarlaua || "—"}, P. ${t.parcela || "—"} <span class="muted num">· ${fmtHa(t.suprafata_ha)}</span></label>`)}</div>`
    : html`<div class="muted small">Dosarul nu are terenuri.</div>`;
}

// ================================================================ Reziliere
export function rezilieazaDialog(om, laFinal) {
  let motivEditat = false;
  const m = openModal({
    title: "Reziliere contract", sub: `${om.nume_complet} · contract ${om.nr_data_contract || "fără număr"}`,
    iconName: "file-earmark-x", iconClass: "danger", size: "lg",
    body: html`
      <form class="form-grid" novalidate data-form>
        <div class="form-section">Motivul rezilierii</div>
        <div class="col-12 segmented" role="radiogroup" style="flex-wrap:wrap">
          ${Object.entries(MOTIVE).map(([k, v]) => html`<button type="button" data-motiv="${k}">${icon(v.icon)} ${v.label}</button>`)}
        </div>
        <div class="field col-12"><label for="f-motiv">Textul din act: „…ca urmare a <i>[motiv]</i>”</label>
          <textarea class="input" id="f-motiv" name="motiv_text" rows="2"></textarea>
          <div class="field-error" data-error-for="motiv_text"></div></div>
        <div class="field col-6"><label for="f-data-rez">Data de la care se reziliază</label>
          <input class="input" type="date" id="f-data-rez" name="data_reziliere" value="${isoAzi()}">
          <div class="hint">Lasă gol ca în act să rămână „_________” de completat de mână.</div></div>

        <div class="form-section">Cine semnează ca arendator</div>
        <div class="col-12 segmented" role="radiogroup">
          <button type="button" data-semnatar="titular">Arendatorul din dosar</button>
          <button type="button" data-semnatar="mostenitor">Moștenitor / împuternicit</button>
        </div>
        <div class="col-12 form-grid" data-bloc="titular" style="gap:14px 16px">
          <div class="col-12 small muted">Seria și numărul CI se salvează în dosar pentru documentele viitoare.</div>
          ${field({ name: "titular.ci_seria", label: "CI seria", value: om.ci_seria || "", col: 3, placeholder: "DZ" })}
          ${field({ name: "titular.ci_numar", label: "CI număr", value: om.ci_numar || "", col: 3, inputmode: "numeric" })}
        </div>
        <div class="col-12 form-grid" data-bloc="mostenitor" style="gap:14px 16px">${campuriPersoana("semnatar")}</div>

        <div class="form-section">Terenuri</div>
        <label class="check col-12"><input type="checkbox" name="cu_transfer"> Transferă terenurile la alt arendator (moștenire / contract nou)</label>
        <div class="col-12 form-grid" data-bloc="transfer" style="gap:14px 16px">
          <div class="col-12 segmented" role="radiogroup" style="flex-wrap:wrap">
            <button type="button" data-dest="mostenitor">Moștenitorul de mai sus (dosar nou)</button>
            <button type="button" data-dest="nou">Altă persoană (dosar nou)</button>
            <button type="button" data-dest="existent">Arendator existent</button>
          </div>
          <div class="col-12 form-grid" data-dest-bloc="nou" style="gap:14px 16px">${campuriPersoana("nou")}</div>
          <div class="field col-12" data-dest-bloc="existent"><label for="f-exist">Arendator existent</label>
            <select class="select" id="f-exist" name="existent_id"><option value="">Alege…</option>${optiuniArendasi(om.id)}</select>
            <div class="field-error" data-error-for="existent_id"></div></div>
          <div class="col-12 form-grid" data-dest-bloc="contract" style="gap:14px 16px">
            ${field({ name: "contract_nou", label: "Nr. / dată contract nou", col: 8, placeholder: "ex: 210/02.05.2026 (opțional)" })}
            ${field({ name: "durata_noua", label: "Durată (ani)", value: om.durata_contract || "7", col: 4, inputmode: "numeric" })}
            <label class="check col-12"><input type="checkbox" name="gen_contract" checked> Generează și contractul nou (Word) cu datele moștenite</label>
          </div>
          <div class="col-12"><div class="label" style="margin-bottom:8px">Terenuri transferate</div>${listaTerenuri(om)}</div>
        </div>
      </form>`,
    footer: html`
      <button class="btn" data-close>Renunță</button>
      <button class="btn" data-doar-act>${icon("file-earmark-word")} Doar descarcă actul</button>
      <button class="btn btn-danger" data-reziliaza>${icon("file-earmark-x")} Reziliază și descarcă actul</button>`,
  });
  const form = m.$("[data-form]");
  form.addEventListener("submit", (e) => e.preventDefault());
  const stare = { motiv: "renuntare", semnatar: "titular", dest: "mostenitor" };

  const actualizeaza = () => {
    m.$$("[data-motiv]").forEach((b) => b.classList.toggle("active", b.dataset.motiv === stare.motiv));
    m.$$("[data-semnatar]").forEach((b) => b.classList.toggle("active", b.dataset.semnatar === stare.semnatar));
    m.$$("[data-dest]").forEach((b) => b.classList.toggle("active", b.dataset.dest === stare.dest));
    m.$('[data-bloc="titular"]').hidden = stare.semnatar !== "titular";
    m.$('[data-bloc="mostenitor"]').hidden = stare.semnatar !== "mostenitor";
    m.$('[data-dest="mostenitor"]').hidden = stare.semnatar !== "mostenitor";
    if (stare.dest === "mostenitor" && stare.semnatar !== "mostenitor") stare.dest = "nou";
    const cuTransfer = form.cu_transfer.checked;
    m.$('[data-bloc="transfer"]').hidden = !cuTransfer;
    m.$('[data-dest-bloc="nou"]').hidden = stare.dest !== "nou";
    m.$('[data-dest-bloc="existent"]').hidden = stare.dest !== "existent";
    m.$('[data-dest-bloc="contract"]').hidden = stare.dest === "existent";
    m.$$("[data-dest]").forEach((b) => b.classList.toggle("active", b.dataset.dest === stare.dest));
  };
  const alegeMotiv = (k) => {
    stare.motiv = k;
    if (!motivEditat) form.motiv_text.value = MOTIVE[k].text(om);
    if (k === "deces") {
      stare.semnatar = "mostenitor";
      stare.dest = "mostenitor";
      form.cu_transfer.checked = om.terenuri.length > 0;
    } else if (k === "contract_nou") {
      if (stare.dest === "mostenitor" && stare.semnatar !== "mostenitor") stare.dest = "nou";
      form.cu_transfer.checked = om.terenuri.length > 0;
    } else {
      stare.semnatar = "titular";
      form.cu_transfer.checked = false;
    }
    actualizeaza();
  };
  form.motiv_text.addEventListener("input", () => (motivEditat = form.motiv_text.value.trim() !== ""));
  m.el.addEventListener("click", (e) => {
    const b = e.target.closest("[data-motiv],[data-semnatar],[data-dest]");
    if (!b) return;
    if (b.dataset.motiv) return alegeMotiv(b.dataset.motiv);
    if (b.dataset.semnatar) stare.semnatar = b.dataset.semnatar;
    if (b.dataset.dest) stare.dest = b.dataset.dest;
    actualizeaza();
  });
  form.cu_transfer.addEventListener("change", actualizeaza);
  alegeMotiv("renuntare");

  /** Construiește cererea; întoarce null dacă există erori de validare locale. */
  function cerere(cuTransfer) {
    curataErori(form);
    let are = false;
    const motiv_text = form.motiv_text.value.trim();
    if (!motiv_text) are = eroareCamp(form, "motiv_text", "Completează motivul rezilierii.");
    const body = { motiv_tip: stare.motiv, motiv_text, data_reziliere: form.data_reziliere.value || null };
    if (stare.semnatar === "mostenitor") {
      body.semnatar = citestePersoana(form, "semnatar");
      if (valideazaPersoana(form, "semnatar", body.semnatar)) are = true;
    } else {
      body.semnatar = {
        nume_complet: om.nume_complet, cnp: om.cnp, adresa: om.adresa,
        ci_seria: form.elements["titular.ci_seria"].value.trim(), ci_numar: form.elements["titular.ci_numar"].value.trim(),
        ci_eliberat: om.ci_eliberat, ci_data: om.ci_data,
      };
    }
    if (cuTransfer && form.cu_transfer.checked) {
      const teren_ids = $$("input[name=teren]:checked", form).map((x) => +x.value);
      if (!teren_ids.length && om.terenuri.length) { eroare(new Error("Selectează cel puțin un teren de transferat.")); are = true; }
      if (stare.dest === "existent") {
        const id = +form.existent_id.value;
        if (!id) are = eroareCamp(form, "existent_id", "Alege arendatorul.");
        body.transfer = { existent_id: id, teren_ids };
      } else {
        const p = stare.dest === "mostenitor" ? { ...body.semnatar } : citestePersoana(form, "nou");
        if (stare.dest === "nou" && valideazaPersoana(form, "nou", p)) are = true;
        body.transfer = { nou: { ...p, nr_data_contract: form.contract_nou.value.trim(), durata_contract: form.durata_noua.value.trim() }, teren_ids };
      }
      if (!om.terenuri.length) delete body.transfer;
    }
    if (are) { form.querySelector("[aria-invalid='true']")?.focus(); return null; }
    return body;
  }

  const fisierAct = () => `Act_aditional_reziliere_${om.nume_complet.replace(/\s+/g, "_")}.docx`;

  m.$("[data-doar-act]").addEventListener("click", (e) => cuIncarcare(e.currentTarget, async () => {
    const body = cerere(false);
    if (!body) return;
    try { await descarca("POST", `/api/arendasi/${om.id}/reziliere/act`, body, fisierAct()); ok("Act adițional generat", "Contractul NU a fost marcat ca reziliat."); }
    catch (err) { aratoEroriServer(form, err); }
  }));

  m.$("[data-reziliaza]").addEventListener("click", (e) => cuIncarcare(e.currentTarget, async () => {
    const body = cerere(true);
    if (!body) return;
    try {
      // CI-ul titularului se păstrează în dosar
      if (stare.semnatar === "titular" && (body.semnatar.ci_seria !== (om.ci_seria || "") || body.semnatar.ci_numar !== (om.ci_numar || ""))) {
        upsertArendas(await api.patch(`/api/arendasi/${om.id}`, { ci_seria: body.semnatar.ci_seria, ci_numar: body.semnatar.ci_numar }));
      }
      await descarca("POST", `/api/arendasi/${om.id}/reziliere/act`, body, fisierAct());
      const rez = await api.post(`/api/arendasi/${om.id}/reziliere`, body);
      upsertArendas(rez.arendas);
      if (rez.nou) {
        upsertArendas(rez.nou);
        if (form.gen_contract.checked && stare.dest !== "existent") {
          await descarca("GET", `/api/arendasi/${rez.nou.id}/contract`, undefined, `Contract_${rez.nou.nume_complet}.docx`);
        }
      } else if (body.transfer?.existent_id) {
        upsertArendas(await api.get(`/api/arendasi/${body.transfer.existent_id}`));
      }
      m.close();
      ok("Contract reziliat", rez.nou ? `Terenurile au trecut la ${rez.nou.nume_complet}.` : "Actul adițional a fost descărcat.");
      laFinal?.(rez);
    } catch (err) { aratoEroriServer(form, err); }
  }));
}

// ================================================================ Transfer terenuri (fără reziliere)
export function transferDialog(om, laFinal) {
  let dest = "existent";
  const m = openModal({
    title: "Transferă terenuri", sub: `De la ${om.nume_complet} · moștenire parțială, vânzare, donație`, iconName: "arrow-left-right", size: "lg",
    body: html`
      <form class="form-grid" novalidate data-form>
        <div class="form-section">Terenuri</div>
        <div class="col-12">${listaTerenuri(om)}</div>
        <div class="form-section">Către</div>
        <div class="col-12 segmented" role="radiogroup">
          <button type="button" data-dest="existent">Arendator existent</button>
          <button type="button" data-dest="nou">Persoană nouă (dosar nou)</button>
        </div>
        <div class="field col-12" data-dest-bloc="existent"><label for="f-exist2">Arendator existent</label>
          <select class="select" id="f-exist2" name="existent_id"><option value="">Alege…</option>${optiuniArendasi(om.id)}</select>
          <div class="field-error" data-error-for="existent_id"></div></div>
        <div class="col-12 form-grid" data-dest-bloc="nou" style="gap:14px 16px">
          ${campuriPersoana("nou")}
          ${field({ name: "contract_nou", label: "Nr. / dată contract nou", col: 8, placeholder: "opțional" })}
          ${field({ name: "durata_noua", label: "Durată (ani)", value: "7", col: 4, inputmode: "numeric" })}
          <label class="check col-12"><input type="checkbox" name="gen_contract" checked> Generează contractul nou (Word)</label>
        </div>
        <div class="form-section">Detalii</div>
        <div class="field col-4"><label for="f-data-tr">Data</label><input class="input" type="date" id="f-data-tr" name="data" value="${isoAzi()}"></div>
        ${field({ name: "motiv", label: "Motiv", col: 8, placeholder: "ex: moștenire, vânzare, donație" })}
      </form>`,
    footer: html`<button class="btn" data-close>Renunță</button><button class="btn btn-primary" data-ok>${icon("arrow-left-right")} Transferă</button>`,
  });
  const form = m.$("[data-form]");
  form.addEventListener("submit", (e) => e.preventDefault());
  const actualizeaza = () => {
    m.$$("[data-dest]").forEach((b) => b.classList.toggle("active", b.dataset.dest === dest));
    m.$$("[data-dest-bloc]").forEach((b) => (b.hidden = b.dataset.destBloc !== dest));
  };
  m.el.addEventListener("click", (e) => { const b = e.target.closest("[data-dest]"); if (b) { dest = b.dataset.dest; actualizeaza(); } });
  actualizeaza();

  m.$("[data-ok]").addEventListener("click", (e) => cuIncarcare(e.currentTarget, async () => {
    curataErori(form);
    const teren_ids = $$("input[name=teren]:checked", form).map((x) => +x.value);
    if (!teren_ids.length) return eroare(new Error("Selectează cel puțin un teren."));
    const body = { teren_ids, data: form.data.value || null, motiv: form.motiv.value.trim() || null };
    if (dest === "existent") {
      if (!+form.existent_id.value) return eroareCamp(form, "existent_id", "Alege arendatorul.");
      body.existent_id = +form.existent_id.value;
    } else {
      const p = citestePersoana(form, "nou");
      if (valideazaPersoana(form, "nou", p)) return;
      body.nou = { ...p, nr_data_contract: form.contract_nou.value.trim(), durata_contract: form.durata_noua.value.trim() };
    }
    try {
      const rez = await api.post(`/api/arendasi/${om.id}/transfer-terenuri`, body);
      upsertArendas(rez.arendas);
      upsertArendas(rez.nou);
      if (dest === "nou" && form.gen_contract.checked) {
        await descarca("GET", `/api/arendasi/${rez.nou.id}/contract`, undefined, `Contract_${rez.nou.nume_complet}.docx`);
      }
      m.close();
      const ha = sumHa(rez.nou.terenuri.filter((t) => teren_ids.includes(t.id)).map((t) => t.suprafata_ha));
      ok("Terenuri transferate", `${teren_ids.length} parcele (${fmtHa(ha)}) → ${rez.nou.nume_complet}`);
      laFinal?.(rez);
    } catch (err) { aratoEroriServer(form, err); }
  }));
}

// ================================================================ Istoric
export async function randeazaIstoric(container, om) {
  try {
    const ist = await api.get(`/api/arendasi/${om.id}/istoric-terenuri`);
    if (!ist.length) { container.innerHTML = ""; return; }
    render(container, html`
      <h4 style="margin:22px 0 10px;font-size:14px">${icon("clock-history")} Istoric transferuri</h4>
      <ul class="list card" style="box-shadow:none">${ist.map((i) => {
        const primit = i.la_id === om.id;
        return html`<li class="list-item">
          <span class="badge ${primit ? "badge-ok" : "badge-warn"}">${icon(primit ? "box-arrow-in-down" : "box-arrow-up")}${primit ? "Primit" : "Cedat"}</span>
          <div class="grow"><div class="title">T. ${i.tarlaua || "—"}, P. ${i.parcela || "—"}</div>
            <div class="small muted">${primit ? `de la ${i.de_la_nume}` : `către ${i.la_nume}`}${i.motiv ? ` · ${i.motiv}` : ""}</div></div>
          <span class="small muted num">${fmtData(i.data)}</span>
          ${(primit ? i.de_la_id : i.la_id) ? html`<button class="btn btn-ghost btn-sm" data-dosar-link="${primit ? i.de_la_id : i.la_id}">Dosar ${icon("chevron-right")}</button>` : ""}
        </li>`;
      })}</ul>`);
  } catch { container.innerHTML = ""; }
}
