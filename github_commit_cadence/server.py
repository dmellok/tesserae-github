"""github_commit_cadence, daily commits across the last 30 days.

GitHub's /repos/{repo}/stats/commit_activity gives 52 weeks, each
with a 7-element ``days`` array (Sunday-first) plus a weekly
``total``. We take the trailing 30 days, expand into per-day bars,
and compute headline + sub stats. The endpoint is async and may
return 202 while stats compute, which the github_core helper raises
as ``GithubAcceptedError`` so we know to skip caching.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import current_app

CACHE_TTL_S = 1800
WINDOW_DAYS = 30
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


def _core() -> Any:
    return current_app.config["PLUGIN_REGISTRY"].get("github_core").server_module


def _flatten(weeks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand the stats response into a sorted list of {date, count}
    daily entries."""
    out: list[dict[str, Any]] = []
    for week in weeks or []:
        ts = week.get("week")
        days = week.get("days") or []
        if not isinstance(ts, int) or len(days) != 7:
            continue
        sunday = datetime.fromtimestamp(ts, tz=UTC).date()
        for offset, count in enumerate(days):
            out.append(
                {
                    "date": (sunday + timedelta(days=offset)).isoformat(),
                    "count": int(count or 0),
                }
            )
    out.sort(key=lambda d: d["date"])
    return out


def _tail(days: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    if not days:
        return []
    today = datetime.now(UTC).date()
    cutoff = today - timedelta(days=n - 1)
    cutoff_key = cutoff.isoformat()
    out = [d for d in days if d["date"] >= cutoff_key]
    # Pad with zero days so the bar count is always n (clean axis).
    have = {d["date"] for d in out}
    cursor: date = cutoff
    while cursor <= today:
        key = cursor.isoformat()
        if key not in have:
            out.append({"date": key, "count": 0})
        cursor += timedelta(days=1)
    out.sort(key=lambda d: d["date"])
    return out[-n:]


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    del settings
    repo = (options.get("repo") or "").strip()
    if not REPO_RE.match(repo):
        return {"error": "Set repo as 'owner/repo' (e.g. dmellok/tesserae)."}

    core = _core()
    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    safe = repo.replace("/", "__")
    cache = data_dir / f"commit_cadence_{safe}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_S:
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("bars"):
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    pending = False
    try:
        weeks = core.request_json(
            f"https://api.github.com/repos/{repo}/stats/commit_activity"
        )
    except core.GithubAcceptedError:
        weeks = []
        pending = True
    except Exception as err:
        return {"error": core.coerce_error(err)}

    days = _flatten(weeks if isinstance(weeks, list) else [])
    bars = _tail(days, WINDOW_DAYS)
    last7 = sum(d["count"] for d in bars[-7:])
    last30 = sum(d["count"] for d in bars)
    weekly_avg = round(last30 / 4.3, 1) if last30 else 0.0
    busiest = max(bars, key=lambda d: d["count"], default={"date": "", "count": 0})

    result = {
        "repo": repo,
        "bars": bars,
        "last7": last7,
        "last30": last30,
        "weekly_avg": weekly_avg,
        "busiest": busiest,
        "pending": pending,
    }
    if not pending and bars:
        cache.write_text(json.dumps(result), encoding="utf-8")
    return result
