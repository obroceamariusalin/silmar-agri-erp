import { deschideDosar, editeazaTeren } from "../dialogs.js";
import { collator, fmtHa, fmtInt, normalizeaza, sumHa } from "../format.js";
import { store, toateTerenurile } from "../store.js";
import { DataTable } from "../table.js";
import { debounce, html, icon, render } from "../ui.js";

export const titlu = "Terenuri";
export const sub = () => "Evidența cadastrală a parcelelor arendate";

let root, tabel;
const filtre = { q: "", tarla: "", parcela: "", comuna: "" };

export function mount(el) {
  root = el;
  render(root, html`
    <div class="card">
      <div class="card-header"><h2>Parcele</h2><span class="sub" data-sum></span>
        <div class="actions"><button class="btn btn-sm" data-act="csv">${icon("filetype-csv")}<span class="hide-mobile">Export CSV</span></button></div>
      </div>
      <div class="toolbar">
        <div class="input-icon">${icon("search")}<input class="input input-sm" type="search" placeholder="Caută după proprietar…" data-f="q" value="${filtre.q}"></div>
        <select class="select select-sm" data-f="tarla" aria-label="Tarla"></select>
        <input class="input input-sm" data-f="parcela" placeholder="Parcelă" value="${filtre.parcela}" style="max-width:130px" aria-label="Parcelă">
        <select class="select select-sm" data-f="comuna" aria-label="Comuna"></select>
      </div>
      <div data-table></div>
    </div>`);

  tabel = new DataTable(root.querySelector("[data-table]"), {
    storageKey: "terenuri", sort: { key: "tarla", dir: 1 }, pageSize: 50,
    emptyText: "Nicio parcelă nu corespunde filtrelor.", emptyIcon: "map",
    onRowClick: (t) => deschideDosar(t.proprietar.id, "terenuri"),
    columns: [
      { key: "tarla", label: "Tarla", mobile: "title", value: (t) => `${t.tarlaua || ""} ${t.parcela || ""}`, csv: (t) => t.tarlaua,
        render: (t) => html`<span class="cell-title">T. ${t.tarlaua || "—"}</span><span class="cell-sub" style="margin-left:6px">P. ${t.parcela || "—"}</span>` },
      { key: "parcela", label: "Parcelă", value: (t) => t.parcela || "", mobile: "hide" },
      { key: "comuna", label: "Comuna", value: (t) => t.comuna || "", render: (t) => t.comuna || "—" },
      { key: "ha", label: "Suprafață", align: "right", value: (t) => t.suprafata_ha, render: (t) => html`<span class="num">${fmtHa(t.suprafata_ha)}</span>`,
        footer: (rows) => html`<span class="num">${fmtHa(sumHa(rows.map((t) => t.suprafata_ha)))}</span>` },
      { key: "proprietar", label: "Proprietar", value: (t) => t.proprietar.nume_complet,
        render: (t) => html`<div class="cell-title" style="font-weight:500">${t.proprietar.nume_complet}</div>` },
      { key: "act", label: "", sortable: false, align: "right", mobile: "actions", csv: false,
        render: (t) => html`<div class="row-actions"><button class="btn btn-ghost btn-sm btn-icon" data-edit="${t.id}" aria-label="Editează">${icon("pencil")}</button>
          <button class="btn btn-ghost btn-sm" data-open="${t.proprietar.id}">Dosar ${icon("chevron-right")}</button></div>` },
    ],
  });

  root.querySelector("[data-f=q]").addEventListener("input", debounce((e) => { filtre.q = e.target.value; update(true); }));
  root.querySelector("[data-f=parcela]").addEventListener("input", debounce((e) => { filtre.parcela = e.target.value; update(true); }));
  root.querySelectorAll("select[data-f]").forEach((s) => s.addEventListener("change", (e) => { filtre[e.target.dataset.f] = e.target.value; update(true); }));
  root.addEventListener("click", (e) => {
    const ed = e.target.closest("[data-edit]");
    if (ed) return editeazaTeren(toateTerenurile().find((t) => t.id === +ed.dataset.edit));
    const o = e.target.closest("[data-open]");
    if (o) return deschideDosar(+o.dataset.open, "terenuri");
    if (e.target.closest("[data-act=csv]")) tabel.exportCsv("Terenuri.csv");
  });
  update();
}

export function update(resetPage = false) {
  if (!root) return;
  const toate = toateTerenurile();
  const optiuni = (sel, valori, eticheta, curent) => render(sel, html`<option value="">${eticheta}</option>${valori.map((v) => html`<option value="${v}" ${v === curent ? "selected" : ""}>${v}</option>`)}`);
  optiuni(root.querySelector("[data-f=tarla]"), [...new Set(toate.map((t) => t.tarlaua).filter(Boolean))].sort(collator.compare), "Toate tarlalele", filtre.tarla);
  optiuni(root.querySelector("[data-f=comuna]"), [...new Set(toate.map((t) => t.comuna).filter(Boolean))].sort(collator.compare), "Toate comunele", filtre.comuna);

  const q = normalizeaza(filtre.q.trim());
  const p = normalizeaza(filtre.parcela.trim());
  const rows = toate.filter((t) =>
    (!q || normalizeaza(t.proprietar.nume_complet).includes(q)) &&
    (!filtre.tarla || t.tarlaua === filtre.tarla) &&
    (!p || normalizeaza(t.parcela).includes(p)) &&
    (!filtre.comuna || t.comuna === filtre.comuna));
  root.querySelector("[data-sum]").textContent = `${fmtInt(rows.length)} parcele · ${fmtHa(sumHa(rows.map((t) => t.suprafata_ha)))} · ${store.arendasi.length} proprietari`;
  tabel.setRows(rows, { resetPage });
}
