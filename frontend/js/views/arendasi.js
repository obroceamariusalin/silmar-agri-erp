import { adaugaArendas, contractRapid, deschideDosar, descarcaRaport } from "../dialogs.js";
import { collator, fmtData, fmtHa, fmtInt, normalizeaza, sumHa } from "../format.js";
import { haOm, store } from "../store.js";
import { DataTable } from "../table.js";
import { badgeStatusContract, debounce, html, icon, render } from "../ui.js";

export const titlu = "Arendași";
export const sub = () => "Dosare, contracte și date de identificare";

let root, tabel;
const filtre = { q: "", status: "", localitate: "", incomplete: false };

export function mount(el) {
  root = el;
  render(root, html`
    <div class="card">
      <div class="card-header">
        <h2>Dosare arendași</h2>
        <div class="actions">
          <button class="btn btn-sm" data-act="csv">${icon("filetype-csv")}<span class="hide-mobile">Export CSV</span></button>
          <button class="btn btn-sm" data-act="contract">${icon("lightning-charge")}<span class="hide-mobile">Contract rapid</span></button>
          <button class="btn btn-sm btn-primary" data-act="adauga">${icon("person-plus")} Arendaș nou</button>
        </div>
      </div>
      <div class="toolbar">
        <div class="input-icon">${icon("search")}<input class="input input-sm" type="search" placeholder="Caută nume, CNP, adresă, nr. contract…" data-f="q" value="${filtre.q}"></div>
        <select class="select select-sm" data-f="status" aria-label="Status contract">
          <option value="">Toate contractele</option>
          <option value="activ">Active</option>
          <option value="expira_curand">Expiră în 6 luni</option>
          <option value="expirat">Expirate</option>
          <option value="necunoscut">Fără dată</option>
        </select>
        <select class="select select-sm" data-f="localitate" aria-label="Localitate"></select>
        <label class="check small"><input type="checkbox" data-f="incomplete" ${filtre.incomplete ? "checked" : ""}> Doar date incomplete</label>
      </div>
      <div data-table></div>
    </div>`);
  root.querySelector("[data-f=status]").value = filtre.status;

  tabel = new DataTable(root.querySelector("[data-table]"), {
    storageKey: "arendasi", sort: { key: "nume", dir: 1 },
    emptyText: "Niciun arendaș nu corespunde filtrelor.", emptyIcon: "people",
    onRowClick: (om) => deschideDosar(om.id),
    columns: [
      { key: "nume", label: "Arendaș", mobile: "title", value: (o) => o.nume_complet,
        render: (o) => html`<div class="cell-title">${o.nume_complet}</div><div class="cell-sub">${o.cnp ? o.cnp : html`<span style="color:var(--warn)">${icon("exclamation-circle")} fără CNP</span>`}</div>` },
      { key: "cnp", label: "CNP/CUI", value: (o) => o.cnp || "", render: (o) => o.cnp || "—", mobile: "hide" },
      { key: "localitate", label: "Localitate", value: (o) => o.localitate || "" , render: (o) => o.localitate || "—" },
      { key: "parcele", label: "Parcele", align: "right", value: (o) => o.terenuri.length, render: (o) => html`<span class="num">${o.terenuri.length}</span>` },
      { key: "ha", label: "Suprafață", align: "right", value: (o) => haOm(o), render: (o) => html`<span class="num">${fmtHa(o.suprafata_totala)}</span>`,
        footer: (rows) => html`<span class="num">${fmtHa(sumHa(rows.map(haOm)))}</span>` },
      { key: "contract", label: "Contract", value: (o) => o.nr_data_contract || "", render: (o) => o.nr_data_contract || html`<span class="muted">—</span>` },
      { key: "expira", label: "Expiră", value: (o) => o.data_expirare || "", csv: (o) => fmtData(o.data_expirare),
        render: (o) => html`<div class="row" style="gap:6px;justify-content:inherit">${badgeStatusContract(o.status_contract, fmtData(o.data_expirare))}<span class="small muted num hide-mobile">${o.data_expirare ? fmtData(o.data_expirare) : ""}</span></div>` },
      { key: "act", label: "", sortable: false, align: "right", mobile: "actions", csv: false,
        render: (o) => html`<button class="btn btn-sm btn-ghost" data-open="${o.id}">Deschide ${icon("chevron-right")}</button>` },
    ],
  });

  root.querySelector("[data-f=q]").addEventListener("input", debounce((e) => { filtre.q = e.target.value; update(true); }));
  root.querySelectorAll("select[data-f]").forEach((s) => s.addEventListener("change", (e) => { filtre[e.target.dataset.f] = e.target.value; update(true); }));
  root.querySelector("[data-f=incomplete]").addEventListener("change", (e) => { filtre.incomplete = e.target.checked; update(true); });
  root.addEventListener("click", (e) => {
    const o = e.target.closest("[data-open]");
    if (o) return deschideDosar(+o.dataset.open);
    const a = e.target.closest("[data-act]");
    if (!a) return;
    if (a.dataset.act === "adauga") adaugaArendas();
    else if (a.dataset.act === "contract") contractRapid();
    else if (a.dataset.act === "csv") descarcaRaport("csv", a);
  });
  update();
}

export function update(resetPage = false) {
  if (!root) return;
  const loc = root.querySelector("[data-f=localitate]");
  const localitati = [...new Set(store.arendasi.map((o) => o.localitate).filter(Boolean))].sort(collator.compare);
  render(loc, html`<option value="">Toate localitățile</option>${localitati.map((l) => html`<option ${l === filtre.localitate ? "selected" : ""}>${l}</option>`)}`);

  const q = normalizeaza(filtre.q.trim());
  const rows = store.arendasi.filter((o) =>
    (!q || normalizeaza(`${o.nume_complet} ${o.cnp || ""} ${o.adresa || ""} ${o.nr_data_contract || ""}`).includes(q)) &&
    (!filtre.status || o.status_contract === filtre.status) &&
    (!filtre.localitate || o.localitate === filtre.localitate) &&
    (!filtre.incomplete || !o.cnp || !o.adresa || !o.nr_data_contract || o.terenuri.length === 0));
  tabel.setRows(rows, { resetPage });
  root.querySelector(".card-header h2").textContent = `Dosare arendași (${fmtInt(rows.length)})`;
}
