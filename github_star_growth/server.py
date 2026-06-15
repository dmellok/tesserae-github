"""github_star_growth, cumulative star history for one repo.

GitHub's /stargazers endpoint can return per-star timestamps when the
custom Accept header is set. We paginate the tail (most recent
stargazers first by reverse-walking from the last page) until we
cover the requested window or run out of budget, then resample to a
daily cumulative series anchored at the repo's current
stargazer_count.

The full per-star history isn't pulled for hot repos (could be
hundreds of thousands of stargazers); we cap at PAGE_BUDGET pages of
100 stars each and fall back to a single "rest" anchor at the
window's start when the cap is hit.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import current_app

CACHE_TTL_S = 3600
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
PAGE_BUDGET = 40
PER_PAGE = 100
STAR_ACCEPT = "application/vnd.github.star+json"


def _core() -> Any:
    return current_app.config["PLUGIN_REGISTRY"].get("github_core").server_module


def _last_page_url(link_header: str) -> str | None:
    """Parse the GitHub Link header to find the rel=\"last\" URL."""
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.strip()
        if 'rel="last"' in section and "<" in section and ">" in section:
            return section[section.index("<") + 1 : section.index(">")]
    return None


def _last_page_number(url: str | None) -> int:
    if not url:
        return 1
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    try:
        return int(qs.get("page", ["1"])[0])
    except ValueError:
        return 1


def _fetch_page(core: Any, repo: str, page: int) -> tuple[list[dict[str, Any]], str]:
    url = (
        f"https://api.github.com/repos/{repo}/stargazers"
        f"?per_page={PER_PAGE}&page={page}"
    )
    req = urllib.request.Request(url, headers=core.headers(accept=STAR_ACCEPT), method="GET")
    with urllib.request.urlopen(req, timeout=12) as resp:
        link = resp.headers.get("Link") or ""
        body = resp.read().decode("utf-8")
        return json.loads(body) if body.strip() else [], link


def _build_series(
    stars_timeline: list[str],
    *,
    window_start: datetime,
    today: datetime,
    starting_count: int,
) -> list[dict[str, Any]]:
    """Resample raw star timestamps into a daily cumulative series
    from window_start to today. starting_count is the count at
    window_start (i.e. before any of the captured stars)."""
    by_day: dict[str, int] = {}
    for ts in stars_timeline:
        try:
            day = datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            continue
        by_day[day] = by_day.get(day, 0) + 1

    out: list[dict[str, Any]] = []
    cumulative = starting_count
    cursor = window_start.date()
    end = today.date()
    while cursor <= end:
        key = cursor.isoformat()
        cumulative += by_day.get(key, 0)
        out.append({"date": key, "total": cumulative})
        cursor += timedelta(days=1)
    return out


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    del settings
    repo = (options.get("repo") or "").strip()
    if not REPO_RE.match(repo):
        return {"error": "Set repo as 'owner/repo' (e.g. dmellok/tesserae)."}

    try:
        window_days = int(options.get("window_days") or 90)
    except (TypeError, ValueError):
        window_days = 90
    window_days = max(7, min(365, window_days))

    core = _core()
    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    safe = repo.replace("/", "__")
    cache = data_dir / f"star_growth_{safe}_{window_days}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_S:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Get repo metadata for the current total + a sanity check.
    try:
        info = core.request_json(f"https://api.github.com/repos/{repo}")
    except Exception as err:
        return {"error": core.coerce_error(err)}

    total_stars = int(info.get("stargazers_count") or 0)
    if total_stars == 0:
        return {"repo": repo, "total_stars": 0, "series": [], "truncated": False}

    # Walk pages from the END backwards (the last page has the newest
    # stargazers). We need to know the last page number, which means
    # one initial request to read the Link header.
    try:
        first, link = _fetch_page(core, repo, 1)
    except Exception as err:
        return {"error": core.coerce_error(err)}

    last_page = _last_page_number(_last_page_url(link)) or 1
    today = datetime.now(UTC)
    window_start = today - timedelta(days=window_days)
    timestamps: list[str] = []
    pages_walked = 0
    crossed_window = False

    # Walk from last_page down to page 1 (or the budget cap).
    page = last_page
    while page >= 1 and pages_walked < PAGE_BUDGET:
        if page == 1:
            entries = first
        else:
            try:
                entries, _ = _fetch_page(core, repo, page)
            except Exception:
                break
        pages_walked += 1
        for entry in entries:
            ts = entry.get("starred_at")
            if not ts:
                continue
            try:
                when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if when < window_start:
                crossed_window = True
                continue
            timestamps.append(ts)
        if crossed_window:
            break
        page -= 1

    # Stars older than the window form the baseline at window_start.
    starting_count = total_stars - len(timestamps)
    series = _build_series(
        timestamps,
        window_start=window_start,
        today=today,
        starting_count=max(0, starting_count),
    )

    result = {
        "repo": repo,
        "total_stars": total_stars,
        "series": series,
        "window_days": window_days,
        "truncated": pages_walked >= PAGE_BUDGET and not crossed_window,
    }
    cache.write_text(json.dumps(result), encoding="utf-8")
    return result
