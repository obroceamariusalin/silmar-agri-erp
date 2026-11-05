// Starea aplicației: datele se încarcă O SINGURĂ dată; după fiecare modificare serverul întoarce
// dosarul actualizat, iar store-ul înlocuiește doar acel arendaș (fără reîncărcarea întregii baze).
import { api } from "./api.js";
import { roundKg, sumHa } from "./format.js";

const ascultatori = new Set();

function anInitial() {
  try {
    const v = parseInt(localStorage.getItem("anAgricol"), 10);
    if (v > 2000) return v;
  } catch { /* storage blocat */ }
  return new Date().getFullYear();
}

export const store = {
  user: null,
  config: { kg_per_ha: 600 },
  an: anInitial(),
  arendasi: [],
  jurnal: null, // încărcat leneș, doar când se deschide ecranul Jurnal
  incarcat: false,
};

export const onChange = (fn) => (ascultatori.add(fn), () => ascultatori.delete(fn));
const emite = (motiv) => ascultatori.forEach((fn) => fn(motiv));

export async function incarcaArendasi() {
  store.arendasi = await api.get("/api/arendasi");
  store.incarcat = true;
  emite("arendasi");
}

export function upsertArendas(om) {
  const i = store.arendasi.findIndex((x) => x.id === om.id);
  if (i >= 0) store.arendasi[i] = om; else store.arendasi.push(om);
  emite("arendasi");
  return om;
}

export function stergeArendasLocal(id) {
  store.arendasi = store.arendasi.filter((x) => x.id !== id);
  emite("arendasi");
}

export function setAn(an) {
  store.an = an;
  try { localStorage.setItem("anAgricol", String(an)); } catch { /* ignore */ }
  emite("an");
}

export const getArendas = (id) => store.arendasi.find((x) => x.id === id);

export function aniDisponibili() {
  const curent = new Date().getFullYear();
  const ani = new Set([curent - 2, curent - 1, curent, curent + 1, store.an]);
  for (const om of store.arendasi) {
    for (const p of om.plati) if (p.anul_agricol) ani.add(p.anul_agricol);
    for (const p of om.preferinte) ani.add(p.anul_agricol);
  }
  return [...ani].sort((a, b) => b - a);
}

// ---------------------------------------------------------------- Calcule derivate
export const haOm = (om) => sumHa(om.terenuri.map((t) => t.suprafata_ha));
export const cereala = (om, an = store.an) => om.preferinte.find((p) => p.anul_agricol === an)?.tip_cereala || "grau";
export const datorat = (om) => roundKg(haOm(om) * store.config.kg_per_ha);
export const platit = (om, an = store.an) =>
  roundKg(om.plati.filter((p) => p.anul_agricol === an).reduce((s, p) => s + p.cantitate_kg, 0));
export const rest = (om, an = store.an) => roundKg(datorat(om) - platit(om, an));

/** 'achitat' | 'partial' | 'neachitat' | 'fara_teren' */
export function statusPlata(om, an = store.an) {
  const d = datorat(om);
  if (d <= 0) return "fara_teren";
  const p = platit(om, an);
  if (p >= d - 0.5) return "achitat";
  return p > 0 ? "partial" : "neachitat";
}

export function toateTerenurile() {
  const out = [];
  for (const om of store.arendasi) for (const t of om.terenuri) out.push({ ...t, proprietar: om });
  return out;
}
