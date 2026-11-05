// Componente UI: HTML sigur (anti-XSS), toast-uri, modale, confirmări, formulare.

// ---------------------------------------------------------------- HTML sigur
class SafeHTML {
  constructor(s) { this.s = s; }
  toString() { return this.s; }
}
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;" };
export const esc = (v) => String(v ?? "").replace(/[&<>"'`]/g, (c) => ESC[c]);
export const raw = (s) => new SafeHTML(String(s ?? ""));

function valoare(v) {
  if (v === null || v === undefined || v === false) return "";
  if (v instanceof SafeHTML) return v.s;
  if (Array.isArray(v)) return v.map(valoare).join("");
  return esc(v);
}

/** Template literal care escapează AUTOMAT orice valoare interpolată (doar `html`/`raw` trec neschimbate). */
export function html(strings, ...vals) {
  let out = strings[0];
  for (let i = 0; i < vals.length; i++) out += valoare(vals[i]) + strings[i + 1];
  return new SafeHTML(out);
}

export function render(el, content) {
  el.innerHTML = valoare(content);
  return el;
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const icon = (name) => html`<i class="bi bi-${name}" aria-hidden="true"></i>`;

// ---------------------------------------------------------------- Toast
const TOAST_ICON = { success: "check-lg", error: "exclamation-triangle", info: "info-lg" };

export function toast(type, title, message = "", ms = type === "error" ? 6500 : 3800) {
  let box = $(".toasts");
  if (!box) {
    box = document.createElement("div");
    box.className = "toasts";
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    document.body.appendChild(box);
  }
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  render(el, html`
    <div class="ti">${icon(TOAST_ICON[type] || "info-lg")}</div>
    <div class="tb"><div class="tt">${title}</div>${message ? html`<div class="tm">${message}</div>` : ""}</div>
    <button class="btn btn-ghost btn-sm btn-icon tx" aria-label="Închide">${icon("x")}</button>`);
  const inchide = () => {
    if (el.classList.contains("out")) return;
    el.classList.add("out");
    el.addEventListener("animationend", () => el.remove(), { once: true });
  };
  el.querySelector(".tx").addEventListener("click", inchide);
  box.appendChild(el);
  setTimeout(inchide, ms);
}
export const ok = (title, msg) => toast("success", title, msg);
export const eroare = (err, title = "Operațiunea nu a reușit") =>
  toast("error", title, err?.message || String(err || "Eroare necunoscută"));

// ---------------------------------------------------------------- Modal
let modaleDeschise = 0;

/**
 * openModal({ title, sub, icon, size: 'sm'|'md'|'lg'|'xl', body, footer, header, onClose })
 * Folosește <dialog>: focus trap, Esc și backdrop native.
 */
export function openModal({ title = "", sub = "", iconName, iconClass = "", size = "md", body = "", footer = "", header, onClose } = {}) {
  const dlg = document.createElement("dialog");
  dlg.className = `modal size-${size}`;
  render(dlg, html`
    <div class="modal-header">
      ${header ?? html`
        ${iconName ? html`<div class="modal-icon ${iconClass}">${icon(iconName)}</div>` : ""}
        <div><h3>${title}</h3>${sub ? html`<div class="sub">${sub}</div>` : ""}</div>`}
      <button type="button" class="btn btn-ghost btn-icon close" data-close aria-label="Închide">${icon("x-lg")}</button>
    </div>
    <div class="modal-main" style="display:contents">
      <div class="modal-body">${body}</div>
      ${footer ? html`<div class="modal-footer">${footer}</div>` : ""}
    </div>`);
  document.body.appendChild(dlg);
  dlg.showModal();
  modaleDeschise++;
  document.body.classList.add("modal-open");

  let inchis = false;
  const close = (rezultat) => {
    if (inchis) return;
    inchis = true;
    dlg.classList.add("closing");
    const final = () => {
      dlg.close();
      dlg.remove();
      modaleDeschise = Math.max(0, modaleDeschise - 1);
      if (!modaleDeschise) document.body.classList.remove("modal-open");
      onClose?.(rezultat);
    };
    const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) final(); else dlg.addEventListener("animationend", final, { once: true });
  };
  dlg.addEventListener("cancel", (e) => { e.preventDefault(); close(); });
  dlg.addEventListener("mousedown", (e) => { if (e.target === dlg) close(); });
  dlg.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) close(); });
  const autofocus = dlg.querySelector("[autofocus]");
  if (autofocus) setTimeout(() => autofocus.focus(), 30);

  return { el: dlg, close, $: (s) => dlg.querySelector(s), $$: (s) => [...dlg.querySelectorAll(s)] };
}

/** Confirmare elegantă (înlocuiește confirm()). Rezolvă cu false sau cu valorile din `extra` (obiect). */
export function confirma({ title, message, confirmLabel = "Confirmă", danger = false, extra = "" }) {
  return new Promise((resolve) => {
    let rezultat = false;
    const m = openModal({
      title, size: "sm", iconName: danger ? "exclamation-triangle" : "question-lg", iconClass: danger ? "danger" : "",
      body: html`<p style="margin:0;color:var(--text-2)">${message}</p>${extra ? html`<form class="confirm-extra" style="margin-top:14px">${extra}</form>` : ""}`,
      footer: html`
        <button type="button" class="btn" data-close>Renunță</button>
        <button type="button" class="btn ${danger ? "btn-danger" : "btn-primary"}" data-ok autofocus>${confirmLabel}</button>`,
      onClose: () => resolve(rezultat),
    });
    m.$(".confirm-extra")?.addEventListener("submit", (e) => { e.preventDefault(); m.$("[data-ok]").click(); });
    m.$("[data-ok]").addEventListener("click", () => {
      const f = m.$(".confirm-extra");
      rezultat = f ? Object.fromEntries([...f.elements].filter((x) => x.name).map((x) => [x.name, x.type === "checkbox" ? x.checked : x.value])) : {};
      m.close();
    });
  });
}

// ---------------------------------------------------------------- Formulare
export function field({ name, label, value = "", type = "text", placeholder = "", hint = "", col = 12, required = false, attrs = "", inputmode = "" }) {
  return html`
    <div class="field col-${col}">
      <label for="f-${name}">${label}${required ? html` <span style="color:var(--danger)">*</span>` : ""}</label>
      <input class="input" id="f-${name}" name="${name}" type="${type}" value="${value ?? ""}" placeholder="${placeholder}"
        ${inputmode ? raw(`inputmode="${esc(inputmode)}"`) : ""} ${raw(attrs)} autocomplete="off">
      ${hint ? html`<div class="hint">${hint}</div>` : ""}
      <div class="field-error" data-error-for="${name}"></div>
    </div>`;
}

export const valori = (form) => Object.fromEntries(new FormData(form).entries());

export function curataErori(root) {
  $$("[aria-invalid]", root).forEach((el) => el.removeAttribute("aria-invalid"));
  $$(".field-error", root).forEach((el) => (el.textContent = ""));
}

export function eroareCamp(root, name, mesaj) {
  const input = root.querySelector(`[name="${CSS.escape(name)}"]`);
  const box = root.querySelector(`[data-error-for="${CSS.escape(name)}"]`);
  if (input) input.setAttribute("aria-invalid", "true");
  if (box) box.textContent = mesaj;
  return Boolean(input || box);
}

/** Afișează erorile de validare venite de la server lângă câmpuri; restul în toast. */
export function aratoEroriServer(root, err) {
  curataErori(root);
  let mapate = 0;
  for (const e of err?.erori || []) {
    if ((e.cale && eroareCamp(root, e.cale, e.mesaj)) || (e.camp && eroareCamp(root, e.camp, e.mesaj))) mapate++;
  }
  if (mapate) {
    root.querySelector("[aria-invalid='true']")?.focus();
    toast("error", "Verifică câmpurile marcate", err.message);
  } else {
    eroare(err);
  }
}

export async function cuIncarcare(btn, fn) {
  if (!btn) return fn();
  btn.classList.add("is-busy");
  btn.disabled = true;
  try {
    return await fn();
  } finally {
    btn.classList.remove("is-busy");
    btn.disabled = false;
  }
}

export function debounce(fn, ms = 180) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export function badgeStatusContract(status, dataExp) {
  const map = {
    activ: ["ok", "check-circle", "Activ"],
    expira_curand: ["warn", "hourglass-split", "Expiră curând"],
    expirat: ["danger", "x-circle", "Expirat"],
    necunoscut: ["", "question-circle", "Fără dată"],
  };
  const [cls, ic, text] = map[status] || map.necunoscut;
  return html`<span class="badge ${cls ? `badge-${cls}` : ""}" title="${dataExp ? `Expiră la ${dataExp}` : "Completează nr./data contractului"}">${icon(ic)}${text}</span>`;
}

export function badgeCereala(c) {
  if (c === "bani") return html`<span class="badge badge-bani">💵 Bani</span>`;
  return c === "porumb"
    ? html`<span class="badge badge-porumb">🌽 Porumb</span>`
    : html`<span class="badge badge-grau">🌾 Grâu</span>`;
}

export const ETICHETA_CEREALA = { grau: "🌾 Grâu", porumb: "🌽 Porumb", bani: "💵 Bani" };
