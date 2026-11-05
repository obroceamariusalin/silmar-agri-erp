// Client HTTP: un singur loc pentru erori, sesiune expirată și descărcări.

export class ApiError extends Error {
  constructor(message, status = 0, erori = []) {
    super(message);
    this.status = status;
    this.erori = erori;
  }
}

function laLogin() {
  const next = encodeURIComponent(location.pathname + location.hash);
  location.replace(`/login?next=${next}`);
}

async function citesteEroare(res) {
  let detail = `Eroare ${res.status}`;
  let erori = [];
  try {
    const data = await res.json();
    if (typeof data.detail === "string") detail = data.detail;
    if (Array.isArray(data.erori)) erori = data.erori;
  } catch { /* răspuns non-JSON */ }
  if (res.status >= 500 && detail.startsWith("Eroare ")) detail = "Serverul a întâmpinat o problemă. Încearcă din nou.";
  return new ApiError(detail, res.status, erori);
}

export async function request(method, url, body, { raw = false } = {}) {
  const opts = { method, headers: {}, credentials: "same-origin" };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, opts);
  } catch {
    throw new ApiError("Nu există conexiune la server. Verifică internetul și încearcă din nou.");
  }
  if (res.status === 401 && !url.startsWith("/api/auth/login")) {
    laLogin();
    throw new ApiError("Sesiunea a expirat.", 401);
  }
  if (!res.ok) throw await citesteEroare(res);
  if (raw) return res;
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  get: (url) => request("GET", url),
  post: (url, body) => request("POST", url, body),
  patch: (url, body) => request("PATCH", url, body),
  del: (url) => request("DELETE", url),
};

function numeDinAntet(res, implicit) {
  const cd = res.headers.get("Content-Disposition") || "";
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
  return m ? decodeURIComponent(m[1]) : implicit;
}

export function salveazaBlob(blob, nume) {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: nume });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** Descarcă un fișier generat de server; erorile ajung în toast, nu pe o pagină JSON. */
export async function descarca(method, url, body, numeImplicit = "document") {
  const res = await request(method, url, body, { raw: true });
  const blob = await res.blob();
  salveazaBlob(blob, numeDinAntet(res, numeImplicit));
}
