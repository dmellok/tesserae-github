// github_star_growth, single-repo cumulative star history. Headline =
// current total stars. The chart shows cumulative growth across the
// chosen window. A "truncated" flag from the server means we hit our
// pagination cap, so we add a small caveat chip rather than implying
// the early curve is precise.

import { sparkline, tokens } from "../../static/spectra-chart.js";

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtCount(n) {
  const v = Number(n) || 0;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return String(v);
}

export default function render(shadow, ctx) {
  const data = ctx?.data ?? {};
  const css = `<link rel="stylesheet" href="/static/style/spectra-widgets.css">`;

  if (data.error) {
    shadow.innerHTML = `
      ${css}
      <div class="w" data-widget="github_star_growth">
        <div class="w-title"><i class="ph-bold ph-warning-circle"></i><h3>Star Growth</h3></div>
        <div class="w-body"><p class="u-muted">${escapeHtml(data.error)}</p></div>
      </div>`;
    return;
  }

  const repo = data.repo || "";
  const total = Number(data.total_stars) || 0;
  const window = Number(data.window_days) || 0;
  const series = Array.isArray(data.series) ? data.series : [];
  const truncated = !!data.truncated;
  const totals = series.map((p) => Number(p.total) || 0);

  // Delta = current total minus first point in window. Falls back to
  // zero if the series is empty (new repo or no fetch yet).
  const baseline = totals.length ? totals[0] : total;
  const delta = total - baseline;
  const deltaText = delta >= 0 ? `+${fmtCount(delta)}` : `-${fmtCount(-delta)}`;
  const deltaPill = totals.length >= 2
    ? `<span class="pill" style="background:var(--accent-3)">${escapeHtml(`${deltaText} / ${window}d`)}</span>`
    : "";

  shadow.innerHTML = `
    ${css}
    <div class="w" data-widget="github_star_growth">
      <div class="w-title">
        <i class="ph-bold ph-trend-up" style="color:var(--accent-2)"></i>
        <h3>${escapeHtml(repo)}</h3>
        ${deltaPill}
        ${truncated ? `<span class="pill" style="background:var(--surface-sunken);color:var(--text-secondary)">approx</span>` : ""}
      </div>
      <div class="w-body status-body">
        <div class="status-hero">
          <i class="ph-bold ph-star" style="color:var(--accent-2)"></i>
          <div class="lockup">
            <span class="status-state">${escapeHtml(fmtCount(total))}</span>
            <span class="status-sub">stars</span>
          </div>
        </div>
        ${totals.length >= 2 ? `<div style="flex:1 1 auto;min-height:3em;position:relative"><canvas></canvas></div>` : `<p class="u-muted">No history yet. Build will fetch on the next render.</p>`}
      </div>
    </div>`;

  if (totals.length >= 2) {
    const canvas = shadow.querySelector("canvas");
    const t = tokens(shadow.host);
    sparkline(canvas, totals, t.accent2);
  }
}
