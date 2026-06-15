// github_star_count, Spectra hero-number archetype. Big total stars
// across the user's owned repos as the headline. Sub-line shows
// repo count and a delta over the recorded history. Top three repos
// listed below by stars, and a cumulative sparkline draws at the
// bottom once at least two history snapshots exist (each render
// writes a UTC-day snapshot so the curve fills in over time).

import { sparkline, tokens } from "../../static/spectra-chart.js";

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtCount(n) {
  if (n == null) return "-";
  const v = Number(n) || 0;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return String(v);
}

function fmtDelta(n) {
  const v = Number(n) || 0;
  if (v > 0) return `+${fmtCount(v)}`;
  if (v < 0) return `-${fmtCount(-v)}`;
  return "+0";
}

// Compute a delta in stars from the start of the history window to
// the latest snapshot. Used as a sub-stat chip; for a fresh install
// with only one snapshot we return null so the chip is hidden.
function deltaSince(history, days) {
  if (!Array.isArray(history) || history.length < 2) return null;
  const latest = history[history.length - 1];
  const cutoff = new Date(latest.date);
  cutoff.setUTCDate(cutoff.getUTCDate() - days);
  const cutoffKey = cutoff.toISOString().slice(0, 10);
  // First entry on or after the cutoff (history is sorted ascending).
  const baseline = history.find((e) => e.date >= cutoffKey);
  if (!baseline || baseline === latest) return null;
  return Number(latest.total || 0) - Number(baseline.total || 0);
}

export default function render(shadow, ctx) {
  const data = ctx?.data ?? {};
  const css = `<link rel="stylesheet" href="/static/style/spectra-widgets.css">`;

  if (data.error) {
    shadow.innerHTML = `
      ${css}
      <div class="w" data-widget="github_star_count">
        <div class="w-title"><i class="ph-bold ph-warning-circle"></i><h3>Star Count</h3></div>
        <div class="w-body"><p class="u-muted">${escapeHtml(data.error)}</p></div>
      </div>`;
    return;
  }

  const total = Number(data.total_stars) || 0;
  const totalRepos = Number(data.total_repos) || 0;
  const top = Array.isArray(data.top) ? data.top : [];
  const history = Array.isArray(data.history) ? data.history : [];
  const delta30 = deltaSince(history, 30);
  const delta7 = deltaSince(history, 7);
  const series = history.map((e) => Number(e.total) || 0);

  const topList = top.length
    ? `
      <ul class="top-list">
        ${top.map((t, i) => `
          <li>
            <span class="top-rank">${i + 1}</span>
            <span class="top-name">${escapeHtml(t.name)}</span>
            <span class="top-stars">${fmtCount(t.stars)}</span>
          </li>`).join("")}
      </ul>`
    : "";

  const deltaChip = (() => {
    if (delta7 != null && Math.abs(delta7) > 0) {
      return `<span class="pill" style="background:var(--accent-3)">${escapeHtml(fmtDelta(delta7))} 7d</span>`;
    }
    if (delta30 != null && Math.abs(delta30) > 0) {
      return `<span class="pill" style="background:var(--accent-3)">${escapeHtml(fmtDelta(delta30))} 30d</span>`;
    }
    return "";
  })();

  const subline = (() => {
    const repoLabel = totalRepos === 1 ? "repo" : "repos";
    if (totalRepos > 0) return `across ${totalRepos} ${repoLabel}`;
    return data.user ? `for @${data.user}` : "";
  })();

  const layout = `
    .top-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: var(--space-1);
    }
    .top-list li {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      padding: var(--space-1) var(--space-2);
      background: color-mix(in oklab, var(--text-primary) 4%, transparent);
      border-radius: var(--radius-1);
      font-variant-numeric: tabular-nums;
      min-width: 0;
    }
    .top-rank {
      flex: 0 0 auto;
      width: 1.6em;
      height: 1.6em;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: var(--surface-sunken);
      color: var(--text-secondary);
      border-radius: 50%;
      font-weight: var(--fw-black);
      font-size: var(--fs-caption);
    }
    .top-name {
      flex: 1 1 auto;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--text-primary);
      font-weight: var(--fw-semi);
    }
    .top-stars {
      flex: 0 0 auto;
      color: var(--accent-2);
      font-weight: var(--fw-bold);
    }
    @container (max-width: 240px) {
      .top-list { display: none; }
    }
    @container (max-width: 200px) {
      .status-sub { display: none; }
    }
  `;

  shadow.innerHTML = `
    ${css}
    <style>${layout}</style>
    <div class="w" data-widget="github_star_count">
      <div class="w-title">
        <i class="ph-bold ph-star" style="color:var(--accent-2)"></i>
        <h3>Total stars</h3>
        ${deltaChip}
      </div>
      <div class="w-body status-body">
        <div class="status-hero">
          <i class="ph-bold ph-star-four" style="color:var(--accent-2)"></i>
          <div class="lockup">
            <span class="status-state">${escapeHtml(fmtCount(total))}</span>
            <span class="status-sub">${escapeHtml(subline)}</span>
          </div>
        </div>
        ${topList}
        ${series.length >= 2 ? `<div style="flex:0 0 18%;min-height:1.8em;position:relative"><canvas></canvas></div>` : ""}
      </div>
    </div>`;

  if (series.length >= 2) {
    const canvas = shadow.querySelector("canvas");
    const t = tokens(shadow.host);
    sparkline(canvas, series, t.accent2);
  }
}
