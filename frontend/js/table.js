// Tabel de date reutilizabil: sortare, paginare, selecție multiplă, export CSV, carduri pe mobil.
import { collator } from "./format.js";
import { html, icon, render } from "./ui.js";
import { salveazaBlob } from "./api.js";

/**
 * coloane: [{ key, label, value(row) (sortare/CSV), render(row) (HTML), align: 'right'|'center',
 *            sortable (implicit true), mobile: 'title'|'hide'|'actions', csv(row) | false, footer(rows) }]
 */
export class DataTable {
  constructor(container, { columns, rowKey = (r) => r.id, pageSize = 25, selectable = false,
    onRowClick = null, onSelect = null, emptyText = "Nicio înregistrare.", emptyIcon = "inbox",
    sort = null, storageKey = null } = {}) {
    Object.assign(this, { container, columns, rowKey, selectable, onRowClick, onSelect, emptyText, emptyIcon, storageKey });
    this.rows = [];
    this.page = 1;
    this.selected = new Set();
    let salvat = {};
    try { salvat = storageKey ? JSON.parse(localStorage.getItem(`dt:${storageKey}`) || "{}") : {}; } catch { /* storage blocat */ }
    this.pageSize = salvat.pageSize || pageSize;
    this.sort = salvat.sort || sort; // { key, dir: 1|-1 }
    this._bind();
  }

  _persist() {
    if (!this.storageKey) return;
    try { localStorage.setItem(`dt:${this.storageKey}`, JSON.stringify({ pageSize: this.pageSize, sort: this.sort })); } catch { /* ignore */ }
  }

  setRows(rows, { resetPage = false } = {}) {
    this.rows = rows;
    const ids = new Set(rows.map(this.rowKey));
    for (const id of [...this.selected]) if (!ids.has(id)) this.selected.delete(id);
    if (resetPage) this.page = 1;
    this.render();
    this.onSelect?.(this.getSelected());
  }

  getSelected() { return [...this.selected]; }
  clearSelection() { this.selected.clear(); this.render(); this.onSelect?.([]); }

  sorted() {
    if (!this.sort) return this.rows;
    const col = this.columns.find((c) => c.key === this.sort.key);
    if (!col) return this.rows;
    const val = col.value || ((r) => r[col.key]);
    const dir = this.sort.dir;
    return [...this.rows].sort((a, b) => {
      const x = val(a), y = val(b);
      if (x == null || x === "") return 1;
      if (y == null || y === "") return -1;
      if (typeof x === "number" && typeof y === "number") return (x - y) * dir;
      return collator.compare(String(x), String(y)) * dir;
    });
  }

  render() {
    const rows = this.sorted();
    const total = rows.length;
    const pages = Math.max(1, Math.ceil(total / this.pageSize));
    this.page = Math.min(this.page, pages);
    const start = (this.page - 1) * this.pageSize;
    const vizibile = rows.slice(start, start + this.pageSize);
    const toateSel = vizibile.length > 0 && vizibile.every((r) => this.selected.has(this.rowKey(r)));
    const areFooter = this.columns.some((c) => c.footer);

    const th = (c) => {
      const sortabil = c.sortable !== false;
      const activ = this.sort?.key === c.key;
      const aria = activ ? (this.sort.dir === 1 ? "ascending" : "descending") : null;
      const ic = activ ? (this.sort.dir === 1 ? "sort-up" : "sort-down") : "chevron-expand";
      return html`<th class="${c.align || ""}" ${aria ? html`aria-sort="${aria}"` : ""}>
        ${sortabil ? html`<button type="button" class="dt-sort" data-sort="${c.key}" ${aria ? html`aria-sort="${aria}"` : ""}>${c.label}${icon(ic)}</button>` : c.label}
      </th>`;
    };
    const td = (c, r) => {
      const cls = [c.align, c.mobile === "title" ? "m-title" : "", c.mobile === "hide" ? "m-hide" : "", c.mobile === "actions" ? "m-actions" : ""].filter(Boolean).join(" ");
      const continut = c.render ? c.render(r) : (c.value ? c.value(r) : r[c.key]);
      return html`<td class="${cls}" data-label="${c.label}">${continut}</td>`;
    };

    render(this.container, html`
      <div class="dt-wrap">
        <table class="dt ${this.selectable ? "has-check" : ""}">
          <thead><tr>
            ${this.selectable ? html`<th class="w-check"><input type="checkbox" data-check-all ${toateSel ? "checked" : ""} aria-label="Selectează pagina"></th>` : ""}
            ${this.columns.map(th)}
          </tr></thead>
          <tbody>
            ${vizibile.length ? vizibile.map((r) => {
              const id = this.rowKey(r);
              const sel = this.selected.has(id);
              return html`<tr data-id="${id}" class="${this.onRowClick ? "clickable" : ""} ${sel ? "selected" : ""}">
                ${this.selectable ? html`<td class="w-check"><input type="checkbox" data-check="${id}" ${sel ? "checked" : ""} aria-label="Selectează"></td>` : ""}
                ${this.columns.map((c) => td(c, r))}
              </tr>`;
            }) : html`<tr><td colspan="${this.columns.length + (this.selectable ? 1 : 0)}" class="dt-empty">${icon(this.emptyIcon)}${this.emptyText}</td></tr>`}
          </tbody>
          ${areFooter && total ? html`<tfoot><tr>
            ${this.selectable ? html`<td class="w-check"></td>` : ""}
            ${this.columns.map((c) => html`<td class="${c.align || ""}" data-label="${c.footer ? c.label : ""}">${c.footer ? c.footer(rows) : ""}</td>`)}
          </tr></tfoot>` : ""}
        </table>
      </div>
      ${total > 10 ? html`
      <div class="dt-pager">
        <span>${total ? `${start + 1}–${Math.min(start + this.pageSize, total)} din ${total}` : "0 rezultate"}</span>
        <span class="spacer"></span>
        <label class="row small muted hide-mobile">Pe pagină
          <select class="select select-sm" data-page-size>
            ${[10, 25, 50, 100].map((n) => html`<option value="${n}" ${n === this.pageSize ? "selected" : ""}>${n}</option>`)}
          </select>
        </label>
        <button class="btn btn-sm btn-icon" data-page="prev" ${this.page <= 1 ? "disabled" : ""} aria-label="Pagina anterioară">${icon("chevron-left")}</button>
        <span class="num">${this.page} / ${pages}</span>
        <button class="btn btn-sm btn-icon" data-page="next" ${this.page >= pages ? "disabled" : ""} aria-label="Pagina următoare">${icon("chevron-right")}</button>
      </div>` : ""}`);
  }

  _bind() {
    this.container.addEventListener("click", (e) => {
      const sortBtn = e.target.closest("[data-sort]");
      if (sortBtn) {
        const key = sortBtn.dataset.sort;
        this.sort = this.sort?.key === key ? (this.sort.dir === 1 ? { key, dir: -1 } : null) : { key, dir: 1 };
        this._persist();
        this.render();
        return;
      }
      const pg = e.target.closest("[data-page]");
      if (pg) {
        this.page += pg.dataset.page === "next" ? 1 : -1;
        this.render();
        this.container.scrollIntoView({ block: "nearest", behavior: "smooth" });
        return;
      }
      if (e.target.closest("input[type=checkbox], button, a, select, label")) return;
      const tr = e.target.closest("tbody tr[data-id]");
      if (tr && this.onRowClick) {
        const row = this.rows.find((r) => String(this.rowKey(r)) === tr.dataset.id);
        if (row) this.onRowClick(row);
      }
    });
    this.container.addEventListener("change", (e) => {
      if (e.target.matches("[data-page-size]")) {
        this.pageSize = +e.target.value;
        this.page = 1;
        this._persist();
        this.render();
      } else if (e.target.matches("[data-check-all]")) {
        const rows = this.sorted().slice((this.page - 1) * this.pageSize, this.page * this.pageSize);
        rows.forEach((r) => (e.target.checked ? this.selected.add(this.rowKey(r)) : this.selected.delete(this.rowKey(r))));
        this.render();
        this.onSelect?.(this.getSelected());
      } else if (e.target.matches("[data-check]")) {
        const id = this.rows.map(this.rowKey).find((k) => String(k) === e.target.dataset.check);
        e.target.checked ? this.selected.add(id) : this.selected.delete(id);
        e.target.closest("tr").classList.toggle("selected", e.target.checked);
        this.onSelect?.(this.getSelected());
      }
    });
  }

  /** Exportă TOATE rândurile filtrate (nu doar pagina curentă), în ordinea sortării. */
  exportCsv(numeFisier) {
    const cols = this.columns.filter((c) => c.csv !== false && c.mobile !== "actions");
    const cel = (v) => {
      const s = v == null ? "" : typeof v === "number" ? String(v).replace(".", ",") : String(v);
      return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const linii = [cols.map((c) => cel(c.label)).join(";")];
    for (const r of this.sorted()) {
      linii.push(cols.map((c) => cel(c.csv ? c.csv(r) : c.value ? c.value(r) : r[c.key])).join(";"));
    }
    salveazaBlob(new Blob(["﻿" + linii.join("\r\n")], { type: "text/csv;charset=utf-8" }), numeFisier);
  }
}
