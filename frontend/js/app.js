// Shell-ul aplicației: autentificare, navigare (hash router), selector an agricol.
import { api } from "./api.js";
import { contractRapid, descarcaRaport } from "./dialogs.js";
import { initiale } from "./format.js";
import { aniDisponibili, incarcaArendasi, onChange, setAn, store } from "./store.js";
import { $, $$, eroare, html, render } from "./ui.js";
import * as dashboard from "./views/dashboard.js";
import * as plati from "./views/plati.js";
import * as arendasi from "./views/arendasi.js";
import * as terenuri from "./views/terenuri.js";
import * as jurnal from "./views/jurnal.js";

const RUTE = { dashboard, plati, arendasi, terenuri, jurnal };
let viewCurent = null;

function rutaCurenta() {
  const r = location.hash.replace(/^#\/?/, "").split("?")[0];
  return RUTE[r] ? r : "dashboard";
}

function navigheaza() {
  const nume = rutaCurenta();
  const view = RUTE[nume];
  viewCurent = view;
  $$("[data-route]").forEach((a) => a.classList.toggle("active", a.dataset.route === nume));
  $$("[data-route]").forEach((a) => a.toggleAttribute("aria-current", a.dataset.route === nume));
  $("#page-title").textContent = view.titlu;
  $("#page-sub").textContent = view.sub();
  document.title = `${view.titlu} · Silmar Agri ERP`;
  const el = document.createElement("div");
  el.className = "view";
  $("#content").replaceChildren(el);
  view.mount(el);
  document.body.querySelector(".app").classList.remove("nav-open");
  window.scrollTo({ top: 0 });
}

function deseneazaAni() {
  const sel = $("#an-agricol");
  render(sel, aniDisponibili().map((a) => html`<option value="${a}" ${a === store.an ? "selected" : ""}>An agricol ${a}</option>`));
}

async function start() {
  try {
    const me = await api.get("/api/auth/me");
    store.user = me.user;
    store.config = me.config;
  } catch {
    return; // api.js redirecționează la /login la 401
  }

  const u = store.user;
  render($("#user-card"), html`
    <div class="avatar">${initiale(u.nume || u.username)}</div>
    <div style="min-width:0;flex:1"><div class="user-name">${u.nume || u.username}</div><div class="user-role">${u.is_admin ? "Administrator" : "Utilizator"}</div></div>
    <button class="btn btn-ghost btn-sm btn-icon" id="logout" title="Deconectare" aria-label="Deconectare" style="color:#cfe0d6"><i class="bi bi-box-arrow-right"></i></button>`);

  $("#logout").addEventListener("click", async () => {
    try { await api.post("/api/auth/logout"); } finally { location.replace("/login"); }
  });
  $("#menu-btn").addEventListener("click", () => $(".app").classList.toggle("nav-open"));
  $(".scrim").addEventListener("click", () => $(".app").classList.remove("nav-open"));
  $("#an-agricol").addEventListener("change", (e) => setAn(+e.target.value));
  document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-global]");
    if (!a) return;
    $(".app").classList.remove("nav-open");
    if (a.dataset.global === "contract") contractRapid();
    else descarcaRaport(a.dataset.global, a);
  });

  try {
    await incarcaArendasi();
  } catch (err) {
    eroare(err, "Datele nu au putut fi încărcate");
  }
  deseneazaAni();

  onChange((motiv) => {
    if (motiv === "an") {
      $("#page-sub").textContent = viewCurent.sub();
      deseneazaAni();
    }
    viewCurent?.update?.();
  });
  window.addEventListener("hashchange", navigheaza);
  navigheaza();
  $(".boot").classList.add("hide");
  setTimeout(() => $(".boot")?.remove(), 400);
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

start();
