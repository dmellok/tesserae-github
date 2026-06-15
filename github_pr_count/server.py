"""github_pr_count, total-open-PRs hero number.

Hits the same /search/issues endpoint github_pr_queue uses but only
keeps the counts and the oldest PR age per bucket. Two searches: PRs
you authored that are still open, and PRs that have explicitly
requested your review. The combined count is the headline; the
oldest age drives the "stale" indicator.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import current_app

CACHE_TTL_S = 300
USERNAME_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")


def _core() -> Any:
    return current_app.config["PLUGIN_REGISTRY"].get("github_core").server_module


def _days_open(iso: str | None) -> int:
    if not iso:
        return 0
    try:
        ts = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((datetime.now(UTC) - ts).total_seconds() // 86400))


def _bucket(core: Any, query: str) -> dict[str, Any]:
    """Search one query, return total_count + oldest open age."""
    url = (
        "https://api.github.com/search/issues?"
        + urllib.parse.urlencode({"q": query, "sort": "created", "order": "asc", "per_page": 1})
    )
    payload = core.request_json(url)
    items = payload.get("items") or []
    oldest = _days_open(items[0].get("created_at")) if items else 0
    return {
        "count": int(payload.get("total_count") or 0),
        "oldest_days": oldest,
    }


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    del settings
    core = _core()
    if not core.get_token():
        return {"error": "Set a GitHub token in GitHub Core (search API requires auth)."}

    user = (options.get("user") or "").strip() or core.get_username()
    if not user:
        return {"error": "Set a username here or a default in GitHub Core."}
    if not USERNAME_RE.match(user):
        return {"error": f"'{user}' isn't a valid GitHub username."}

    stale_days = max(1, int(options.get("stale_days") or 7))

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"pr_count_{user}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_S:
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            cached["stale_days"] = stale_days
            return cached
        except (json.JSONDecodeError, OSError):
            pass

    try:
        yours = _bucket(core, f"is:pr is:open author:{user}")
        review = _bucket(core, f"is:pr is:open review-requested:{user}")
    except Exception as err:
        return {"error": core.coerce_error(err)}

    result = {
        "user": user,
        "yours": yours,
        "review": review,
        "total": yours["count"] + review["count"],
        "oldest_days": max(yours["oldest_days"], review["oldest_days"]),
        "stale_days": stale_days,
    }
    cache.write_text(json.dumps(result), encoding="utf-8")
    return result
