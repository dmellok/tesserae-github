// github_ci_status, full-bleed CI status banner. Background fills the
// cell with the worst-state colour (terracotta failure, ochre running,
// moss passing) and the headline names what's broken or running.

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

const STATE_PRESET = {
  failing: { color: "var(--accent-1)",  on: "var(--on-accent)", glyph: "ph-x-circle",      verb: "FAILING" },
  running: { color: "var(--accent-2)",  on: "var(--on-accent)", glyph: "ph-arrow-clockwise", verb: "RUNNING" },
  passing: { color: "var(--accent-3)",  on: "var(--on-accent)", glyph: "ph-check-circle",  verb: "GREEN"   },
};

export default function render(shadow, ctx) {
  const data = ctx?.data ?? {};
  const css = `<link rel="stylesheet" href="/static/style/spectra-widgets.css">`;

  if (data.error) {
    shadow.innerHTML = `
      ${css}
      <div class="w" data-widget="github_ci_status">
        <div class="w-title"><i class="ph-bold ph-warning-circle"></i><h3>CI</h3></div>
        <div class="w-body"><p class="u-muted">${escapeHtml(data.error)}</p></div>
      </div>`;
    return;
  }

  const state = data.state || "passing";
  const preset = STATE_PRESET[state] || STATE_PRESET.passing;
  const failing = Array.isArray(data.failing) ? data.failing : [];
  const running = Array.isArray(data.running) ? data.running : [];
  const total = Number(data.total) || 0;
  const failCount = failing.length;
  const runCount = running.length;

  const headline = (() => {
    if (state === "failing") {
      return `${failCount} ${failCount === 1 ? "REPO" : "REPOS"} FAILING`;
    }
    if (state === "running") {
      return `${runCount} ${runCount === 1 ? "REPO" : "REPOS"} RUNNING`;
    }
    return "ALL GREEN";
  })();

  const callout = (() => {
    if (state === "failing") return failing.slice(0, 6).join(" · ");
    if (state === "running") return running.slice(0, 6).join(" · ");
    return total === 1 ? "1 repo watched" : `${total} repos watched`;
  })();

  const layout = `
    .ci-banner {
      flex: 1 1 auto;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      gap: var(--space-2);
      text-align: center;
      padding: var(--space-3);
      background: ${preset.color};
      color: ${preset.on};
    }
    .ci-state {
      font-size: clamp(1.6rem, 8cqi, 4rem);
      font-weight: var(--fw-black);
      letter-spacing: 0.02em;
      line-height: 1;
    }
    .ci-callout {
      font-size: var(--fs-body);
      font-weight: var(--fw-semi);
      opacity: 0.92;
      max-width: 90%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .ci-glyph {
      font-size: clamp(2rem, 14cqi, 6rem);
      line-height: 1;
    }
  `;

  shadow.innerHTML = `
    ${css}
    <style>${layout}</style>
    <div class="w w-bleed" data-widget="github_ci_status" data-state="${escapeHtml(state)}">
      <div class="ci-banner">
        <i class="ph-bold ${preset.glyph} ci-glyph"></i>
        <div class="ci-state">${escapeHtml(headline)}</div>
        <div class="ci-callout">${escapeHtml(callout)}</div>
      </div>
    </div>`;
}
