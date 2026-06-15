"""github_streak, current contribution streak as a single number.

Pulls the year's contribution calendar via GraphQL (same shape as
github_contributions but only the streak metrics survive into the
payload). Streak counts consecutive days with contributionCount > 0
ending today; the longest run anywhere in the window is reported
alongside so a broken streak still shows progress.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from flask import current_app

CACHE_TTL_S = 900
USERNAME_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")

_QUERY = """
query($user: String!) {
  user(login: $user) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
""".strip()


def _core() -> Any:
    return current_app.config["PLUGIN_REGISTRY"].get("github_core").server_module


def _flatten(weeks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    days: list[dict[str, Any]] = []
    for week in weeks or []:
        for day in week.get("contributionDays") or []:
            date = day.get("date")
            count = int(day.get("contributionCount") or 0)
            if date:
                days.append({"date": date, "count": count})
    days.sort(key=lambda d: d["date"])
    return days


def _current_streak(days: list[dict[str, Any]]) -> int:
    """Count consecutive days with count > 0 ending at today (or the
    most recent day in the calendar). A blank today doesn't break the
    streak yet, the user might still commit before UTC rollover."""
    if not days:
        return 0
    # Skip today if it's still zero so a streak built up to yesterday
    # is still "current" until the day actually closes.
    tail = list(reversed(days))
    started = False
    streak = 0
    for entry in tail:
        if not started and entry["count"] == 0:
            continue
        started = True
        if entry["count"] > 0:
            streak += 1
        else:
            break
    return streak


def _longest_streak(days: list[dict[str, Any]]) -> int:
    best = 0
    run = 0
    for entry in days:
        if entry["count"] > 0:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    del settings
    core = _core()
    if not core.get_token():
        return {"error": "Set a GitHub token in GitHub Core (GraphQL API requires auth)."}
    user = (options.get("user") or "").strip() or core.get_username()
    if not user:
        return {"error": "Set a username here or a default in GitHub Core."}
    if not USERNAME_RE.match(user):
        return {"error": f"'{user}' isn't a valid GitHub username."}

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"streak_{user}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_S:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    try:
        payload = core.request_graphql(_QUERY, {"user": user})
    except Exception as err:
        return {"error": core.coerce_error(err)}

    if isinstance(payload, dict) and payload.get("errors"):
        msg = payload["errors"][0].get("message") if payload["errors"] else "GraphQL error"
        return {"error": f"GitHub GraphQL: {msg}"}

    cal = (
        ((payload.get("data") or {}).get("user") or {}).get("contributionsCollection") or {}
    ).get("contributionCalendar") or {}
    days = _flatten(cal.get("weeks") or [])
    today = days[-1] if days else None

    result = {
        "user": user,
        "current_streak": _current_streak(days),
        "longest_streak": _longest_streak(days),
        "today_count": int((today or {}).get("count") or 0),
        "year_total": int(cal.get("totalContributions") or 0),
    }
    cache.write_text(json.dumps(result), encoding="utf-8")
    return result
