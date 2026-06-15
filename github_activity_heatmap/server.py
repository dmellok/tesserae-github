"""github_activity_heatmap, 12-week public-events heatmap.

Walks /users/{user}/events/public over up to PAGE_BUDGET pages of
100, bucketing each event by UTC day. The events feed only reaches
back about 90 days (and ~300 entries for unauthenticated calls), so
the 12-week window is a natural fit. Day cells get a quantile level
0-4 so the renderer can paint with the Spectra accent ramp the same
way github_contributions does.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import current_app

CACHE_TTL_S = 600
PAGE_BUDGET = 6
PER_PAGE = 100
USERNAME_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
WINDOW_DAYS = 84  # 12 full weeks

TYPE_BUCKET = {
    "PushEvent": "commits",
    "PullRequestEvent": "prs",
    "IssuesEvent": "issues",
    "ReleaseEvent": "releases",
    "PullRequestReviewEvent": "reviews",
    "PullRequestReviewCommentEvent": "reviews",
    "IssueCommentEvent": "issues",
    "CommitCommentEvent": "commits",
}


def _core() -> Any:
    return current_app.config["PLUGIN_REGISTRY"].get("github_core").server_module


def _level(count: int, breakpoints: list[int]) -> int:
    """Map a day's count to a 0..4 level using the supplied breakpoints
    (which we compute from the percentiles of the actual data so a
    quiet user's busiest day still shows a fourth-quartile cell)."""
    if count <= 0:
        return 0
    for idx, bp in enumerate(breakpoints, start=1):
        if count <= bp:
            return idx
    return 4


def _breakpoints(counts: list[int]) -> list[int]:
    """Quartile-ish breakpoints from non-zero counts. Returns three
    thresholds so [0, b1, b2, b3, b4] maps to levels 0..4."""
    nz = sorted(c for c in counts if c > 0)
    if not nz:
        return [1, 2, 3]
    n = len(nz)

    def q(p: float) -> int:
        idx = max(0, min(n - 1, int(round(p * (n - 1)))))
        return nz[idx]

    return [q(0.33), q(0.66), q(0.95)]


def _grid(by_day: dict[str, dict[str, int]], today: datetime) -> list[list[dict[str, Any]]]:
    """Build a 12 (cols, weeks oldest→newest) × 7 (rows, Mon-Sun) grid
    of day cells. Each cell has total count, per-type breakdown, and a
    level 0-4 once breakpoints are applied."""
    start = (today - timedelta(days=WINDOW_DAYS - 1)).date()
    # Align to Monday so the rows read as days-of-week.
    while start.weekday() != 0:
        start -= timedelta(days=1)

    weeks: list[list[dict[str, Any]]] = []
    cursor = start
    end = today.date()
    while cursor <= end:
        week: list[dict[str, Any]] = []
        for _ in range(7):
            key = cursor.isoformat()
            day = by_day.get(key, {})
            total = sum(v for k, v in day.items() if k != "events")
            week.append(
                {
                    "date": key,
                    "count": total,
                    "by_type": dict(day),
                }
            )
            cursor += timedelta(days=1)
            if cursor > end:
                break
        weeks.append(week)

    flat_counts = [cell["count"] for w in weeks for cell in w]
    bp = _breakpoints(flat_counts)
    for w in weeks:
        for cell in w:
            cell["level"] = _level(cell["count"], bp)
    return weeks


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    del settings
    core = _core()
    user = (options.get("user") or "").strip() or core.get_username()
    if not user:
        return {"error": "Set a GitHub username, here or as github_core default."}
    if not USERNAME_RE.match(user):
        return {"error": f"'{user}' isn't a valid GitHub username."}

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"activity_heatmap_{user}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_S:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    today = datetime.now(UTC)
    cutoff = today - timedelta(days=WINDOW_DAYS)
    by_day: dict[str, dict[str, int]] = {}
    totals = {"commits": 0, "prs": 0, "issues": 0, "releases": 0, "reviews": 0}
    by_repo: dict[str, int] = {}
    fetched = 0

    for page in range(1, PAGE_BUDGET + 1):
        url = f"https://api.github.com/users/{user}/events/public?per_page={PER_PAGE}&page={page}"
        try:
            events = core.request_json(url)
        except Exception as err:
            if page == 1:
                return {"error": core.coerce_error(err)}
            break
        if not isinstance(events, list) or not events:
            break
        oldest_in_page = None
        for event in events:
            ts = event.get("created_at")
            if not ts:
                continue
            try:
                when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if when < cutoff:
                continue
            oldest_in_page = when
            day_key = when.date().isoformat()
            bucket = TYPE_BUCKET.get(event.get("type") or "")
            if bucket is None:
                continue
            slot = by_day.setdefault(day_key, {})
            slot[bucket] = int(slot.get(bucket, 0)) + 1
            totals[bucket] = totals.get(bucket, 0) + 1
            fetched += 1
            repo_name = (event.get("repo") or {}).get("name")
            if repo_name:
                by_repo[repo_name] = by_repo.get(repo_name, 0) + 1
        # Stop walking pages once the oldest event we saw drops past
        # our window.
        if oldest_in_page and oldest_in_page < cutoff:
            break

    grid = _grid(by_day, today)
    busiest = max(
        (cell for w in grid for cell in w),
        key=lambda c: c["count"],
        default={"date": "", "count": 0},
    )
    top_repos = sorted(by_repo.items(), key=lambda kv: kv[1], reverse=True)[:3]

    result = {
        "user": user,
        "grid": grid,
        "totals": totals,
        "fetched": fetched,
        "busiest": busiest,
        "top_repos": [{"name": n, "count": c} for n, c in top_repos],
    }
    cache.write_text(json.dumps(result), encoding="utf-8")
    return result
