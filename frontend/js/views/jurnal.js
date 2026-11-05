import { api } from "../api.js";
import { collator, fmtData, isoAzi, normalizeaza } from "../format.js";
import { store } from "../store.js";
import { DataTable } from "../table.js";
import { aratoEroriServer, confirma, cuIncarcare, curataErori, debounce, eroare, eroareCamp, html, icon, ok, render, valori } from "../ui.js";

export const titlu = "Jurnal câmp";
export const sub = () => `Lucrări agricole și condiții meteo · ${store.an}`;

const LAT = 44.51, LON = 23.38; // Argetoaia
const VREME = {
  0: ["Senin", "sun"], 1: ["Predominant senin", "sun"], 2: ["Parțial noros", "cloud-sun"], 3: ["Înnorat", "clouds"],
  45: ["Ceață", "cloud-fog"], 48: ["Ceață cu chiciură", "cloud-fog"], 51: ["Burniță", "cloud-drizzle"], 53: ["Burniță", "cloud-drizzle"],
  55: ["Burniță densă", "cloud-drizzle"], 61: ["Ploaie ușoară", "cloud-rain"], 63: ["Ploaie", "cloud-rain"], 65: ["Ploaie torențială", "cloud-rain-heavy"],
  71: ["Ninsoare ușoară", "snow"], 73: ["Ninsoare", "snow"], 75: ["Ninsoare abundentă", "snow"], 80: ["Averse", "cloud-rain"],
  81: ["Averse", "cloud-rain"], 82: ["Averse puternice", "cloud-rain-heavy"], 95: ["Furtună", "cloud-lightning-rain"],
};
const LUCRARI = ["Arat", "Discuit", "Semănat", "Erbicidat", "Fertilizat", "Tratament fitosanitar", "Recoltat", "Irigat", "Pregătit patul germinativ"];
const cacheMeteo = new Map();

let root, tabel, meteoCurent = { temperatura: null, vremea: null };
const filtre = { q: "", de: "", pana: "" };

export function mount(el) {
  root = el;
  render(root, html`
    <div class="grid grid-13">
      <div class="card weather"><div class="card-body" data-meteo><div class="skeleton" style="height:120px;opacity:.2"></div></div></div>
      <div class="card">
        <div class="card-header"><h2>Înregistrează o lucrare</h2></div>
        <div class="card-body">
          <form class="form-grid" novalidate data-form>
            <div class="field col-4"><label for="j-data">Data</label><input class="input" id="j-data" type="date" name="data_operatiune" value="${isoAzi()}"><div class="field-error" data-error-for="data_operatiune"></div></div>
            <div class="field col-4"><label for="j-tarla">Tarla / parcelă</label><input class="input" id="j-tarla" name="tarla_parcela" list="dl-tarle" placeholder="ex: T. 129" autocomplete="off"><div class="field-error" data-error-for="tarla_parcela"></div></div>
            <div class="field col-4"><label for="j-lucrare">Lucrare</label><input class="input" id="j-lucrare" name="lucrare" list="dl-lucrari" placeholder="ex: Erbicidat" autocomplete="off"><div class="field-error" data-error-for="lucrare"></div></div>
            <datalist id="dl-tarle"></datalist>
            <datalist id="dl-lucrari">${LUCRARI.map((l) => html`<option value="${l}">`)}</datalist>
            <div class="col-12 row"><span class="small muted" data-meteo-hint></span><span class="spacer"></span>
              <button class="btn btn-primary" data-save>${icon("journal-plus")} Salvează în jurnal</button></div>
          </form>
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:18px">
      <div class="card-header"><h2>Istoric lucrări</h2>
        <div class="actions"><button class="btn btn-sm" data-act="csv">${icon("filetype-csv")}<span class="hide-mobile">Export CSV</span></button></div></div>
      <div class="toolbar">
        <div class="input-icon">${icon("search")}<input class="input input-sm" type="search" placeholder="Caută tarla sau lucrare…" data-f="q" value="${filtre.q}"></div>
        <label class="row small muted" style="gap:6px">De la <input class="input input-sm" type="date" data-f="de" value="${filtre.de}"></label>
        <label class="row small muted" style="gap:6px">Până la <input class="input input-sm" type="date" data-f="pana" value="${filtre.pana}"></label>
      </div>
      <div data-table><div style="padding:20px"><div class="skeleton" style="height:120px"></div></div></div>
    </div>`);

  const form = root.querySelector("[data-form]");
  form.data_operatiune.addEventListener("change", (e) => meteo(e.target.value));
  form.addEventListener("submit", (e) => e.preventDefault());
  root.querySelector("[data-save]").addEventListener("click", (e) => cuIncarcare(e.currentTarget, async () => {
    curataErori(form);
    const v = valori(form);
    let are = false;
    if (!v.tarla_parcela.trim()) are = eroareCamp(form, "tarla_parcela", "Completează tarla/parcela.");
    if (!v.lucrare.trim()) are = eroareCamp(form, "lucrare", "Completează lucrarea.");
    if (are) return;
    try {
      const nou = await api.post("/api/jurnal", { ...v, ...meteoCurent });
      store.jurnal = [nou, ...(store.jurnal || [])];
      form.tarla_parcela.value = "";
      form.lucrare.value = "";
      ok("Lucrare salvată", `${nou.lucrare} · ${nou.tarla_parcela}`);
      update();
    } catch (err) { aratoEroriServer(form, err); }
  }));

  tabel = new DataTable(root.querySelector("[data-table]"), {
    storageKey: "jurnal", sort: { key: "data", dir: -1 }, rowKey: (j) => j.id,
    emptyText: "Nicio lucrare înregistrată în perioada selectată.", emptyIcon: "journal",
    columns: [
      { key: "data", label: "Data", mobile: "title", value: (j) => j.data_operatiune, csv: (j) => fmtData(j.data_operatiune),
        render: (j) => html`<span class="cell-title">${fmtData(j.data_operatiune)}</span>` },
      { key: "loc", label: "Locație", value: (j) => j.tarla_parcela, render: (j) => html`${icon("geo-alt")} ${j.tarla_parcela}` },
      { key: "lucrare", label: "Lucrare", value: (j) => j.lucrare, render: (j) => html`<span class="strong">${j.lucrare}</span>` },
      { key: "vreme", label: "Vremea", value: (j) => `${j.temperatura || ""} ${j.vremea || ""}`.trim(),
        render: (j) => j.temperatura || j.vremea ? html`<span class="badge">${j.temperatura || ""}</span> <span class="small muted">${j.vremea || ""}</span>` : html`<span class="muted">—</span>` },
      { key: "act", label: "", sortable: false, align: "right", mobile: "actions", csv: false,
        render: (j) => html`<button class="btn btn-ghost btn-sm btn-icon btn-danger-soft" data-del="${j.id}" aria-label="Șterge">${icon("trash3")}</button>` },
    ],
  });

  root.querySelector("[data-f=q]").addEventListener("input", debounce((e) => { filtre.q = e.target.value; update(true); }));
  root.querySelectorAll("input[type=date][data-f]").forEach((i) => i.addEventListener("change", (e) => { filtre[e.target.dataset.f] = e.target.value; update(true); }));
  root.addEventListener("click", async (e) => {
    if (e.target.closest("[data-act=csv]")) return tabel.exportCsv(`Jurnal_${store.an}.csv`);
    const d = e.target.closest("[data-del]");
    if (!d) return;
    const j = store.jurnal.find((x) => x.id === +d.dataset.del);
    if (!(await confirma({ title: "Ștergi lucrarea?", danger: true, confirmLabel: "Șterge", message: `${j.lucrare} · ${j.tarla_parcela} (${fmtData(j.data_operatiune)})` }))) return;
    try {
      await api.del(`/api/jurnal/${j.id}`);
      store.jurnal = store.jurnal.filter((x) => x.id !== j.id);
      ok("Lucrare ștearsă");
      update();
    } catch (err) { eroare(err); }
  });

  meteo(form.data_operatiune.value);
  (store.jurnal ? Promise.resolve() : api.get("/api/jurnal").then((j) => (store.jurnal = j)))
    .then(() => update())
    .catch((err) => eroare(err, "Jurnalul nu a putut fi încărcat"));
}

async function meteo(data) {
  const box = root?.querySelector("[data-meteo]");
  if (!box || !data) return;
  const hint = root.querySelector("[data-meteo-hint]");
  try {
    let d = cacheMeteo.get(data);
    if (!d) {
      const sfarsit = new Date(`${data}T00:00:00`);
      sfarsit.setDate(sfarsit.getDate() + 6);
      const fin = sfarsit.toISOString().slice(0, 10);
      const azi = new Date(`${isoAzi()}T00:00:00`);
      const trecut = new Date(`${data}T00:00:00`) < new Date(azi.getTime() - 60 * 86400000);
      const baza = trecut ? "https://archive-api.open-meteo.com/v1/archive" : "https://api.open-meteo.com/v1/forecast";
      const url = `${baza}?latitude=${LAT}&longitude=${LON}&daily=temperature_2m_max,weathercode,windspeed_10m_max&timezone=auto&start_date=${data}&end_date=${trecut ? data : fin}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error();
      d = (await res.json()).daily;
      cacheMeteo.set(data, d);
    }
    const [desc, ic] = VREME[d.weathercode[0]] || ["Variabil", "cloud-sun"];
    meteoCurent = { temperatura: `${Math.round(d.temperature_2m_max[0])}°C`, vremea: desc };
    render(box, html`
      <div class="row" style="align-items:flex-start">
        <div><div class="small" style="opacity:.75">${icon("geo-alt")} Argetoaia · ${fmtData(data)}</div>
          <div class="temp" style="margin-top:12px">${Math.round(d.temperature_2m_max[0])}°</div>
          <div class="desc">${desc}</div><div class="meta">Vânt max. ${Math.round(d.windspeed_10m_max[0])} km/h</div></div>
        <span class="spacer"></span><i class="bi bi-${ic}" style="font-size:54px;opacity:.9" aria-hidden="true"></i>
      </div>
      ${d.time.length > 1 ? html`<div class="week">${d.time.slice(1, 7).map((t, i) => html`
        <div>${new Date(`${t}T00:00:00`).toLocaleDateString("ro-RO", { weekday: "short" })}<b>${Math.round(d.temperature_2m_max[i + 1])}°</b></div>`)}</div>` : ""}`);
    hint.textContent = `Vremea (${meteoCurent.temperatura}, ${desc}) se salvează automat cu lucrarea.`;
  } catch {
    meteoCurent = { temperatura: null, vremea: null };
    render(box, html`<div class="desc">${icon("cloud-slash")} Prognoza nu este disponibilă pentru această dată.</div>`);
    hint.textContent = "";
  }
}

export function update(resetPage = false) {
  if (!root || !tabel || !store.jurnal) return;
  const tarle = new Set();
  for (const om of store.arendasi) for (const t of om.terenuri) if (t.tarlaua) tarle.add(`T. ${t.tarlaua}`);
  render(root.querySelector("#dl-tarle"), [...tarle].sort(collator.compare).map((t) => html`<option value="${t}">`));

  const q = normalizeaza(filtre.q.trim());
  const an = String(store.an);
  const rows = store.jurnal.filter((j) => {
    const d = j.data_operatiune || "";
    if (filtre.de || filtre.pana) {
      if (filtre.de && d < filtre.de) return false;
      if (filtre.pana && d > filtre.pana) return false;
    } else if (!d.startsWith(an)) return false;
    return !q || normalizeaza(`${j.tarla_parcela} ${j.lucrare}`).includes(q);
  });
  tabel.setRows(rows, { resetPage });
}
