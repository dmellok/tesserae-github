// github_commit_cadence, 30-day commits as Spectra bauhaus bars.
// Headline = weekly average. Two sub-cells for the 7- and 30-day
// totals. Bars stand in for the chart axis so even a quiet repo
// reads as "this is a week" not "noise at the bottom".

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

export default function render(shadow, ctx) {
  const data = ctx?.data ?? {};
  const css = `<link rel="stylesheet" href="/static/style/spectra-widgets.css">`;

  if (data.error) {
    shadow.innerHTML = `
      ${css}
      <div class="w" data-widget="github_commit_cadence">
        <div class="w-title"><i class="ph-bold ph-warning-circle"></i><h3>Commit Cadence</h3></div>
        <div class="w-body"><p class="u-muted">${escapeHtml(data.error)}</p></div>
      </div>`;
    return;
  }

  const repo = data.repo || "";
  const bars = Array.isArray(data.bars) ? data.bars : [];
  const last7 = Number(data.last7) || 0;
  const last30 = Number(data.last30) || 0;
  const weeklyAvg = Number(data.weekly_avg) || 0;
  const busiest = data.busiest || { date: "", count: 0 };
  const pending = !!data.pending;
  const peak = Math.max(1, ...bars.map((b) => Number(b.count) || 0));

  // Render bars with weekend separators so the rhythm of the week
  // reads visually. Sunday + Saturday get a slightly different bar
  // background to soften them.
  const barEls = bars.map((b) => {
    const v = Number(b.count) || 0;
    const pct = Math.max(1, Math.round((v / peak) * 100));
    const dow = (() => {
      try { return new Date(b.date).getUTCDay(); } catch { return -1; }
    })();
    const isWeekend = dow === 0 || dow === 6;
    const fill = v === 0
      ? "var(--surface-sunken)"
      : (isWeekend ? "color-mix(in oklab, var(--accent-3) 70%, var(--surface))" : "var(--accent-3)");
    return `
      <div class="cad-bar" title="${escapeHtml(`${b.date}: ${v}`)}">
        <div class="cad-bar-fill" style="height:${pct}%;background:${fill}"></div>
      </div>`;
  }).join("");

  const layout = `
    .cad-chart {
      flex: 1 1 auto;
      min-height: 4em;
      display: flex;
      align-items: stretch;
      gap: 2px;
    }
    .cad-bar {
      flex: 1 1 0;
      display: flex;
      align-items: flex-end;
      min-width: 0;
    }
    .cad-bar-fill {
      width: 100%;
      border-radius: 2px 2px 0 0;
      transition: none;
    }
    .cad-foot {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: var(--fs-caption);
      color: var(--text-muted);
    }
  `;

  shadow.innerHTML = `
    ${css}
    <style>${layout}</style>
    <div class="w" data-widget="github_commit_cadence">
      <div class="w-title">
        <i class="ph-bold ph-chart-bar" style="color:var(--accent-3)"></i>
        <h3>${escapeHtml(repo)}</h3>
        ${pending ? `<span class="pill" style="background:var(--surface-sunken);color:var(--text-secondary)">computing</span>` : ""}
      </div>
      <div class="w-body status-body">
        <div class="status-hero">
          <i class="ph-bold ph-chart-bar" style="color:var(--accent-3)"></i>
          <div class="lockup">
            <span class="status-state">${escapeHtml(String(weeklyAvg))}</span>
            <span class="status-sub">avg / week</span>
          </div>
        </div>
        <div class="status-grid">
          <div class="status-cell">
            <span class="u-label">7 days</span>
            <span class="v" style="color:var(--accent-4)">${escapeHtml(String(last7))}</span>
          </div>
          <div class="status-cell">
            <span class="u-label">30 days</span>
            <span class="v" style="color:var(--accent-5)">${escapeHtml(String(last30))}</span>
          </div>
        </div>
        <div class="cad-chart">${barEls}</div>
        ${busiest.count ? `<div class="cad-foot"><span>Busiest day</span><span>${escapeHtml(`${busiest.date} · ${busiest.count}`)}</span></div>` : ""}
      </div>
    </div>`;
}
