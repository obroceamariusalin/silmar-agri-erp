import { api } from "../api.js";
import { deschideDosar, descarcaRaport } from "../dialogs.js";
import { collator, fmtHa, fmtInt, fmtKg, normalizeaza, roundKg, sumHa } from "../format.js";
import { cereala, datorat, haOm, incarcaArendasi, platit, rest, statusPlata, store } from "../store.js";
import { DataTable } from "../table.js";
import { $, badgeCereala, confirma, cuIncarcare, debounce, eroare, html, icon, ok, render } from "../ui.js";

export const titlu = "Plăți arendă";
export const sub = () => `Bilanțul plăților în natură · anul agricol ${store.an}`;

let root, tabel;
const filtre = { q: "", cereala: "", status: "", localitate: "" };

const STATUS = {
  achitat: ["ok", "check-circle", "Achitat"],
  partial: ["warn", "circle-half", "Parțial"],
  neachitat: ["danger", "exclamation-circle", "Neachitat"],
  fara_teren: ["", "dash-circle", "Fără teren"],
};
const badgeStatus = (s) => { const [c, i, t] = STATUS[s]; return html`<span class="badge ${c ? `badge-${c}` : ""}">${icon(i)}${t}</span>`; };

export function mount(el) {
  root = el;
  render(root, html`
    <div class="card">
      <div class="card-header">
        <h2>Situația plăților</h2>
        <div class="actions">
          <button class="btn btn-sm" data-act="csv-tabel">${icon("filetype-csv")}<span class="hide-mobile">Export CSV</span></button>
          <button class="btn btn-sm" data-act="borderou">${icon("file-earmark-excel")}<span class="hide-mobile">Borderou Excel</span></button>
          <button class="btn btn-sm" data-act="primarie">${icon("file-earmark-word")}<span class="hide-mobile">Tabel primărie</span></button>
        </div>
      </div>
      <div class="toolbar">
        <div class="input-icon">${icon("search")}<input class="input input-sm" type="search" placeholder="Caută nume, CNP, localitate…" data-f="q" value="${filtre.q}"></div>
        <select class="select select-sm" data-f="cereala" aria-label="Cereală">
          <option value="">Toate cerealele</option><option value="grau">🌾 Grâu</option><option value="porumb">🌽 Porumb</option>
        </select>
        <select class="select select-sm" data-f="status" aria-label="Status plată">
          <option value="">Toate statusurile</option><option value="neachitat">Neachitat</option><option value="partial">Parțial</option><option value="achitat">Achitat</option>
        </select>
        <select class="select select-sm" data-f="localitate" aria-label="Localitate"></select>
      </div>
      <div class="chips" data-chips></div>
      <div data-table></div>
    </div>
    <div class="bulkbar" data-bulk hidden>
      <span class="count" data-count></span>
      <button class="btn btn-sm btn-ghost" data-bulk-act="grau">🌾 Setează grâu</button>
      <button class="btn btn-sm btn-ghost" data-bulk-act="porumb">🌽 Setează porumb</button>
      <button class="btn btn-sm btn-primary" data-bulk-act="plata">${icon("check2-all")} Plată completă</button>
      <button class="btn btn-sm btn-ghost btn-icon" data-bulk-act="clear" aria-label="Deselectează">${icon("x-lg")}</button>
    </div>`);

  root.querySelector("[data-f=cereala]").value = filtre.cereala;
  root.querySelector("[data-f=status]").value = filtre.status;

  tabel = new DataTable(root.querySelector("[data-table]"), {
    storageKey: "plati", selectable: true, sort: { key: "nume", dir: 1 },
    emptyText: "Niciun arendaș nu corespunde filtrelor.", emptyIcon: "search",
    onRowClick: (r) => deschideDosar(r.om.id, "plati"),
    onSelect: (ids) => {
      const bar = $("[data-bulk]", root);
      bar.hidden = ids.length === 0;
      $("[data-count]", root).textContent = `${ids.length} selectați`;
    },
    rowKey: (r) => r.om.id,
    columns: [
      { key: "nume", label: "Arendaș", mobile: "title", value: (r) => r.om.nume_complet,
        render: (r) => html`<div class="cell-title">${r.om.nume_complet}</div><div class="cell-sub">${r.om.localitate || "—"}</div>` },
      { key: "ha", label: "Suprafață", align: "right", value: (r) => r.ha, render: (r) => html`<span class="num">${fmtHa(r.ha)}</span>`,
        footer: (rows) => html`<span class="num">${fmtHa(sumHa(rows.map((r) => r.ha)))}</span>` },
      { key: "cereala", label: "Cereală", value: (r) => r.cer, render: (r) => badgeCereala(r.cer) },
      { key: "datorat", label: "Datorat", align: "right", value: (r) => r.dat, render: (r) => html`<span class="num">${fmtKg(r.dat)}</span>`,
        footer: (rows) => html`<span class="num">${fmtKg(rows.reduce((s, r) => s + r.dat, 0))}</span>` },
      { key: "platit", label: "Plătit", align: "right", value: (r) => r.plat, render: (r) => html`<span class="num" style="color:var(--ok)">${fmtKg(r.plat)}</span>`,
        footer: (rows) => html`<span class="num">${fmtKg(rows.reduce((s, r) => s + r.plat, 0))}</span>` },
      { key: "rest", label: "Rest", align: "right", value: (r) => r.rest,
        render: (r) => html`<span class="num strong" style="color:${r.rest > 0.5 ? "var(--danger)" : "var(--muted)"}">${fmtKg(Math.max(r.rest, 0))}</span>`,
        footer: (rows) => html`<span class="num">${fmtKg(rows.reduce((s, r) => s + Math.max(r.rest, 0), 0))}</span>` },
      { key: "status", label: "Status", value: (r) => ["neachitat", "partial", "achitat", "fara_teren"].indexOf(r.status), csv: (r) => STATUS[r.status][2], render: (r) => badgeStatus(r.status) },
      { key: "act", label: "", sortable: false, align: "right", mobile: "actions", csv: false,
        render: (r) => html`<button class="btn btn-sm" data-open="${r.om.id}">${icon("folder2-open")} Dosar</button>` },
    ],
  });

  const aplica = () => update(true);
  root.querySelector("[data-f=q]").addEventListener("input", debounce((e) => { filtre.q = e.target.value; aplica(); }));
  root.querySelectorAll("select[data-f]").forEach((s) => s.addEventListener("change", (e) => { filtre[e.target.dataset.f] = e.target.value; aplica(); }));
  root.addEventListener("click", onClick);
  update();
}

async function onClick(e) {
  const open = e.target.closest("[data-open]");
  if (open) return deschideDosar(+open.dataset.open, "plati");
  const act = e.target.closest("[data-act]");
  if (act) {
    if (act.dataset.act === "csv-tabel") return tabel.exportCsv(`Plati_${store.an}.csv`);
    return descarcaRaport(act.dataset.act, act);
  }
  const b = e.target.closest("[data-bulk-act]");
  if (!b) return;
  const ids = tabel.getSelected();
  const a = b.dataset.bulkAct;
  if (a === "clear") return tabel.clearSelection();
  if (a === "grau" || a === "porumb") {
    return cuIncarcare(b, async () => {
      try {
        const r = await api.post("/api/arendasi/preferinte-multiple", { ids, anul_agricol: store.an, tip_cereala: a });
        await incarcaArendasi();
        ok("Preferințe actualizate", r.mesaj);
      } catch (err) { eroare(err); }
    });
  }
  if (a === "plata") {
    const sel = store.arendasi.filter((om) => ids.includes(om.id));
    const deDat = roundKg(sel.reduce((s, om) => s + Math.max(rest(om), 0), 0));
    if (!(await confirma({
      title: "Înregistrezi plata completă?", confirmLabel: "Da, înregistrează",
      message: `Se va înregistra restul de plată pentru ${ids.length} arendași, anul ${store.an}: total ${fmtKg(deDat)}. Cei deja achitați sunt ignorați.`,
    }))) return;
    return cuIncarcare(b, async () => {
      try {
        const r = await api.post("/api/arendasi/plata-totala-multipla", { ids, an: store.an });
        await incarcaArendasi();
        tabel.clearSelection();
        ok("Plăți înregistrate", r.mesaj);
      } catch (err) { eroare(err); }
    });
  }
}

export function update(resetPage = false) {
  if (!root) return;
  const loc = root.querySelector("[data-f=localitate]");
  const localitati = [...new Set(store.arendasi.map((o) => o.localitate).filter(Boolean))].sort(collator.compare);
  render(loc, html`<option value="">Toate localitățile</option>${localitati.map((l) => html`<option ${l === filtre.localitate ? "selected" : ""}>${l}</option>`)}`);

  const q = normalizeaza(filtre.q.trim());
  const rows = store.arendasi.map((om) => ({
    om, ha: haOm(om), cer: cereala(om), dat: datorat(om), plat: platit(om), rest: rest(om), status: statusPlata(om),
  })).filter((r) =>
    (!q || normalizeaza(`${r.om.nume_complet} ${r.om.cnp || ""} ${r.om.adresa || ""}`).includes(q)) &&
    (!filtre.cereala || r.cer === filtre.cereala) &&
    (!filtre.status || r.status === filtre.status) &&
    (!filtre.localitate || r.om.localitate === filtre.localitate));

  const n = (s) => rows.filter((r) => r.status === s).length;
  render(root.querySelector("[data-chips]"), html`
    <span class="chip">Arendași <b>${fmtInt(rows.length)}</b></span>
    <span class="chip">Neachitați <b>${n("neachitat")}</b></span>
    <span class="chip">Parțial <b>${n("partial")}</b></span>
    <span class="chip">Achitați <b>${n("achitat")}</b></span>
    <span class="chip">Rest total <b>${fmtKg(rows.reduce((s, r) => s + Math.max(r.rest, 0), 0))}</b></span>`);
  tabel.setRows(rows, { resetPage });
}
