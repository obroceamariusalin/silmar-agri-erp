import { adaugaArendas, contractRapid, deschideDosar, descarcaRaport } from "../dialogs.js";
import { collator, fmtCompact, fmtData, fmtHa, fmtHaScurt, fmtInt, fmtKg, fmtPct, sumHa, zileRamase } from "../format.js";
import { cereala, datorat, haOm, platit, rest, store } from "../store.js";
import { html, icon, render } from "../ui.js";

export const titlu = "Dashboard";
export const sub = () => `Situația generală · anul agricol ${store.an}`;

let root;

export function mount(el) {
  root = el;
  root.addEventListener("click", (e) => {
    const b = e.target.closest("[data-act]");
    if (b) {
      const a = b.dataset.act;
      if (a === "adauga") adaugaArendas();
      else if (a === "contract") contractRapid();
      else descarcaRaport(a, b);
      return;
    }
    const d = e.target.closest("[data-dosar]");
    if (d) deschideDosar(+d.dataset.dosar, d.dataset.tab || "date");
  });
  update();
}

function kpi(iconName, label, value, foot, cls = "") {
  return html`<div class="card kpi ${cls}">
    <div class="kpi-label"><span class="kpi-icon">${icon(iconName)}</span>${label}</div>
    <div class="kpi-value">${value}</div>
    <div class="kpi-foot">${foot}</div>
  </div>`;
}

function meter(label, plat, dat, cls = "") {
  const pct = dat > 0 ? Math.min(1, plat / dat) : 0;
  return html`<div class="meter-row">
    <div class="meter-head"><span class="strong">${label}</span><span class="pct">${fmtPct(pct)}</span></div>
    <div class="meter ${cls}" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct * 100)}" aria-label="${label}: achitat"><span style="width:${(pct * 100).toFixed(1)}%"></span></div>
    <div class="meter-legend"><span>Datorat <b class="num">${fmtKg(dat)}</b></span><span>Achitat <b class="num">${fmtKg(plat)}</b></span><span>Rest <b class="num">${fmtKg(Math.max(dat - plat, 0))}</b></span></div>
  </div>`;
}

export function update() {
  if (!root) return;
  const A = store.arendasi;
  const totalHa = sumHa(A.map(haOm));
  const parcele = A.reduce((s, om) => s + om.terenuri.length, 0);
  const faraCnp = A.filter((om) => !om.cnp).length;
  const active = A.filter((om) => om.status_contract === "activ" || om.status_contract === "expira_curand").length;
  const curand = A.filter((om) => om.status_contract === "expira_curand").length;
  const expirate = A.filter((om) => om.status_contract === "expirat").length;
  const faraData = A.filter((om) => om.status_contract === "necunoscut").length;

  const pe = { grau: { d: 0, p: 0 }, porumb: { d: 0, p: 0 } };
  for (const om of A) {
    const c = cereala(om);
    pe[c].d += datorat(om);
    pe[c].p += Math.min(platit(om), datorat(om));
  }
  const totD = pe.grau.d + pe.porumb.d, totP = pe.grau.p + pe.porumb.p;

  // Suprafață pe tarla (top 8)
  const peTarla = new Map();
  for (const om of A) for (const t of om.terenuri) {
    const k = t.tarlaua || "—";
    peTarla.set(k, (peTarla.get(k) || 0) + Math.round((t.suprafata_ha || 0) * 10000));
  }
  const topTarle = [...peTarla.entries()].map(([k, mp]) => [k, mp / 10000]).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const maxTarla = topTarle[0]?.[1] || 1;

  const restante = A.map((om) => ({ om, r: rest(om) })).filter((x) => x.r > 0.5).sort((a, b) => b.r - a.r).slice(0, 6);
  const deReinnoit = A.filter((om) => om.status_contract === "expira_curand" || om.status_contract === "expirat")
    .sort((a, b) => collator.compare(a.data_expirare || "", b.data_expirare || "")).slice(0, 6);

  render(root, html`
    <div class="row" style="margin-bottom:16px;gap:8px">
      <button class="btn btn-primary" data-act="adauga">${icon("person-plus")} Arendaș nou</button>
      <button class="btn" data-act="contract">${icon("lightning-charge")} Contract rapid</button>
      <span class="spacer"></span>
      <button class="btn" data-act="primarie">${icon("file-earmark-word")}<span>Tabel primărie</span></button>
      <button class="btn" data-act="borderou">${icon("file-earmark-excel")}<span>Borderou ${store.an}</span></button>
    </div>

    <div class="kpis">
      ${kpi("people", "Arendași", fmtInt(A.length), faraCnp ? `${faraCnp} fără CNP completat` : "Toți au CNP/CUI")}
      ${kpi("map", "Suprafață arendată", html`${fmtHaScurt(totalHa)}<small>ha</small>`, `${fmtInt(parcele)} parcele · ${fmtHa(totalHa)}`)}
      ${kpi("file-earmark-check", "Contracte active", fmtInt(active), faraData ? `${faraData} fără dată de contract` : "Toate au dată")}
      ${kpi(curand ? "hourglass-split" : "calendar-check", "Expiră în 6 luni", fmtInt(curand),
            expirate ? html`${icon("x-circle")} ${expirate} deja expirate` : "Niciun contract expirat", curand || expirate ? "is-warn" : "")}
      ${kpi("basket", `De plătit ${store.an}`, html`${fmtCompact(Math.max(totD - totP, 0))}<small>kg</small>`, `${fmtPct(totD ? totP / totD : 0)} achitat din ${fmtKg(totD)}`)}
    </div>

    <div class="grid grid-3">
      <div class="card">
        <div class="card-header"><h2>Plata arendei ${store.an}</h2><span class="sub">${store.config.kg_per_ha} kg/ha</span>
          <div class="actions"><a class="btn btn-sm" href="#/plati">Vezi plățile ${icon("arrow-right")}</a></div></div>
        <div class="card-body">
          ${meter("Total", totP, totD)}
          ${meter("🌾 Grâu", pe.grau.p, pe.grau.d, "grau")}
          ${meter("🌽 Porumb", pe.porumb.p, pe.porumb.d, "porumb")}
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h2>Suprafață pe tarla</h2><span class="sub">top ${topTarle.length}</span></div>
        <div class="card-body">
          ${topTarle.length ? html`<div class="bars">${topTarle.map(([t, ha]) => html`
            <div class="bar-row" title="Tarla ${t}: ${fmtHa(ha)}">
              <span class="strong">T. ${t}</span>
              <div class="bar-track"><div class="bar-fill" style="width:${((ha / maxTarla) * 100).toFixed(1)}%"></div></div>
              <span class="num right muted" style="text-align:right">${fmtHaScurt(ha)} ha</span>
            </div>`)}</div>` : html`<div class="list-empty">Nu există terenuri.</div>`}
        </div>
      </div>
    </div>

    <div class="grid grid-2" style="margin-top:18px">
      <div class="card">
        <div class="card-header"><h2>Restanțe mari ${store.an}</h2></div>
        <ul class="list">
          ${restante.length ? restante.map(({ om, r }) => html`
            <li class="list-item">
              <div class="grow"><div class="title">${om.nume_complet}</div><div class="small muted">${om.localitate || "—"} · ${fmtHa(om.suprafata_totala)}</div></div>
              <span class="num strong" style="color:var(--danger)">${fmtKg(r)}</span>
              <button class="btn btn-sm" data-dosar="${om.id}" data-tab="plati">Plătește</button>
            </li>`) : html`<li class="list-empty">${icon("check-circle")} Toate plățile pentru ${store.an} sunt la zi.</li>`}
        </ul>
      </div>
      <div class="card">
        <div class="card-header"><h2>Contracte de reînnoit</h2></div>
        <ul class="list">
          ${deReinnoit.length ? deReinnoit.map((om) => {
            const z = zileRamase(om.data_expirare);
            return html`<li class="list-item">
              <div class="grow"><div class="title">${om.nume_complet}</div><div class="small muted">Contract ${om.nr_data_contract || "—"}</div></div>
              <span class="badge ${z < 0 ? "badge-danger" : "badge-warn"}">${icon(z < 0 ? "x-circle" : "hourglass-split")}${z < 0 ? `Expirat ${fmtData(om.data_expirare)}` : `${z} zile`}</span>
              <button class="btn btn-sm btn-ghost btn-icon" data-dosar="${om.id}" aria-label="Deschide dosar">${icon("chevron-right")}</button>
            </li>`;
          }) : html`<li class="list-empty">${icon("check-circle")} Niciun contract nu expiră în următoarele 6 luni.</li>`}
        </ul>
      </div>
    </div>`);
}
