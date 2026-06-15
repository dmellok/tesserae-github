// github_activity_heatmap, 12-week public events grid. Three pills
// above show commit / PR / issue totals for the window. The grid
// uses the accent-2 ramp (ochre) for cell intensity so it doesn't
// collide visually with github_contributions which already uses the
// moss-green contribution ramp.

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// Level 0 (empty) through 4 (busiest) → CSS background.
const LEVEL_FILL = [
  "var(--surface-sunken)",
  "color-mix(in oklab, var(--accent-2) 18%, var(--surface))",
  "color-mix(in oklab, var(--accent-2) 38%, var(--surface))",
  "color-mix(in oklab, var(--accent-2) 62%, var(--surface))",
  "var(--accent-2)",
];

export default function render(shadow, ctx) {
  const data = ctx?.data ?? {};
  const css = `<link rel="stylesheet" href="/static/style/spectra-widgets.css">`;

  if (data.error) {
    shadow.innerHTML = `
      ${css}
      <div class="w" data-widget="github_activity_heatmap">
        <div class="w-title"><i class="ph-bold ph-warning-circle"></i><h3>Activity</h3></div>
        <div class="w-body"><p class="u-muted">${escapeHtml(data.error)}</p></div>
      </div>`;
    return;
  }

  const grid = Array.isArray(data.grid) ? data.grid : [];
  const totals = data.totals || {};
  const busiest = data.busiest || {};
  const topRepos = Array.isArray(data.top_repos) ? data.top_repos : [];

  const pill = (label, value, color) => `
    <span class="pill" style="background:${color};color:var(--on-accent)">
      ${escapeHtml(`${value} ${label}`)}
    </span>`;

  const pillRow = `
    <div class="u-row" style="gap:var(--space-1);flex-wrap:wrap">
      ${pill("commits", Number(totals.commits) || 0, "var(--accent-3)")}
      ${pill("PRs",     Number(totals.prs)     || 0, "var(--accent-5)")}
      ${pill("issues",  Number(totals.issues)  || 0, "var(--accent-1)")}
    </div>`;

  const weekCols = grid.map((week) => {
    const cells = week.map((cell) => {
      const lvl = Math.max(0, Math.min(4, Number(cell.level) || 0));
      const title = `${cell.date}: ${cell.count} events`;
      return `<span class="hm-cell" style="background:${LEVEL_FILL[lvl]}" title="${escapeHtml(title)}"></span>`;
    }).join("");
    return `<div class="hm-col">${cells}</div>`;
  }).join("");

  const topReposRow = topRepos.length
    ? `<div class="u-row" style="gap:var(--space-1);flex-wrap:wrap">
        ${topRepos.map((r) => `<span class="pill" style="background:var(--surface-sunken);color:var(--text-secondary)">${escapeHtml(`${r.name} · ${r.count}`)}</span>`).join("")}
      </div>`
    : "";

  const layout = `
    .hm-grid {
      display: flex;
      gap: 3px;
      align-items: flex-start;
      flex: 1 1 auto;
      min-height: 0;
    }
    .hm-col {
      display: flex;
      flex-direction: column;
      gap: 3px;
      flex: 1 1 0;
    }
    .hm-cell {
      flex: 1 1 0;
      aspect-ratio: 1 / 1;
      min-height: 6px;
      border-radius: 2px;
    }
    .hm-foot {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: var(--space-2);
      font-size: var(--fs-caption);
      color: var(--text-muted);
    }
  `;

  shadow.innerHTML = `
    ${css}
    <style>${layout}</style>
    <div class="w" data-widget="github_activity_heatmap">
      <div class="w-title">
        <i class="ph-bold ph-grid-four" style="color:var(--accent-2)"></i>
        <h3>Activity</h3>
      </div>
      <div class="w-body" style="display:flex;flex-direction:column;gap:var(--space-2)">
        ${pillRow}
        <div class="hm-grid">${weekCols}</div>
        ${topReposRow}
        ${busiest.count ? `<div class="hm-foot"><span>Busiest day</span><span>${escapeHtml(`${busiest.date} · ${busiest.count}`)}</span></div>` : ""}
      </div>
    </div>`;
}
