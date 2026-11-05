// Formatare și calcule numerice exacte (suprafețele se adună în unități de 1 mp = 0,0001 ha).

const nf = (min, max) => new Intl.NumberFormat("ro-RO", { minimumFractionDigits: min, maximumFractionDigits: max });
const F_HA = nf(4, 4);
const F_HA2 = nf(2, 2);
const F_KG = nf(0, 0);
const F_INT = nf(0, 0);

export const toMp = (ha) => Math.round((Number(ha) || 0) * 10000);
export const sumHa = (valori) => valori.reduce((s, v) => s + toMp(v), 0) / 10000;
export const roundKg = (x) => Math.round((Number(x) || 0) * 100) / 100;

export const fmtHa = (x) => `${F_HA.format(Number(x) || 0)} ha`;
export const fmtHaScurt = (x) => F_HA2.format(Number(x) || 0);
export const fmtNumHa = (x) => F_HA.format(Number(x) || 0);
export const fmtKg = (x) => `${F_KG.format(Math.round(Number(x) || 0))} kg`;
export const fmtInt = (x) => F_INT.format(Number(x) || 0);
export const fmtPct = (x) => `${Math.round((Number(x) || 0) * 100)}%`;

/** Compact pentru KPI: 1.284 / 12,9 mii / 4,2 mil. */
export function fmtCompact(x) {
  const n = Number(x) || 0;
  if (Math.abs(n) >= 1e6) return `${nf(0, 1).format(n / 1e6)} mil.`;
  if (Math.abs(n) >= 1e4) return `${nf(0, 1).format(n / 1e3)} mii`;
  return F_INT.format(Math.round(n));
}

export function fmtData(iso) {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("ro-RO", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function zileRamase(iso) {
  if (!iso) return null;
  const azi = new Date(); azi.setHours(0, 0, 0, 0);
  return Math.round((new Date(`${iso}T00:00:00`) - azi) / 86400000);
}

export function initiale(nume = "") {
  const p = nume.trim().split(/\s+/).filter(Boolean);
  return ((p[0]?.[0] || "") + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase() || "?";
}

export function normalizeaza(s) {
  return String(s ?? "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

/** Comparator natural ("T2" < "T10"), în limba română. */
export const collator = new Intl.Collator("ro", { numeric: true, sensitivity: "base" });

export function isoAzi() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

// ---- Validare CNP / CUI în browser (aceleași reguli ca pe server, pentru feedback instant)
export function cnpValid(cnp) {
  if (!/^[1-9]\d{12}$/.test(cnp)) return false;
  const luna = +cnp.slice(3, 5), zi = +cnp.slice(5, 7);
  if (luna < 1 || luna > 12 || zi < 1 || zi > 31) return false;
  const k = "279146358279";
  let s = 0;
  for (let i = 0; i < 12; i++) s += +cnp[i] * +k[i];
  let c = s % 11; if (c === 10) c = 1;
  return c === +cnp[12];
}

export function cuiValid(cui) {
  cui = cui.toUpperCase().replace(/^RO/, "");
  if (!/^\d{2,10}$/.test(cui)) return false;
  const corp = cui.slice(0, -1).padStart(9, "0"), k = "753217532";
  let s = 0;
  for (let i = 0; i < 9; i++) s += +corp[i] * +k[i];
  let c = (s * 10) % 11; if (c === 10) c = 0;
  return c === +cui.slice(-1);
}

/** "" -> null (ok); altfel mesaj de eroare sau null dacă e valid. */
export function eroareIdentificator(v) {
  v = String(v || "").replace(/\s+/g, "");
  if (!v) return null;
  if (/^\d{13}$/.test(v)) return cnpValid(v) ? null : "CNP invalid (cifra de control nu se potrivește).";
  if (/^(RO)?\d{2,10}$/i.test(v)) return cuiValid(v) ? null : "CUI invalid (cifra de control nu se potrivește).";
  return "Introdu un CNP (13 cifre) sau un CUI.";
}

export function eroareSuprafata(v) {
  const s = String(v ?? "").trim().replace(",", ".");
  if (!s) return "Suprafața este obligatorie.";
  if (!/^\d+(\.\d+)?$/.test(s)) return "Introdu un număr (ex: 0,2900).";
  if (Number(s) <= 0) return "Trebuie să fie mai mare decât 0.";
  if ((s.split(".")[1] || "").replace(/0+$/, "").length > 4) return "Maxim 4 zecimale.";
  return null;
}
