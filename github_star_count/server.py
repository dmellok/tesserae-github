"""github_star_count, hero total-stars widget.

Single GraphQL call pulls the user's owned repositories with their
stargazer counts; we sum the lot for the headline number and keep
the top three named for the sub-line. A daily snapshot is appended
to a per-user history file so the sparkline accumulates a real
30-day curve over time without the cost of paginating every repo's
stargazers endpoint on every render.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import current_app

CACHE_TTL_S = 600
HISTORY_DAYS = 30
USERNAME_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")

_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(
      first: 100,
      ownerAffiliations: OWNER,
      privacy: PUBLIC,
      isFork: false,
      orderBy: { field: STARGAZERS, direction: DESC }
    ) {
      totalCount
      nodes { name stargazerCount url }
    }
  }
}
"""


def _core() -> Any:
    return current_app.config["PLUGIN_REGISTRY"].get("github_core").server_module


def _resolve_user(options: dict[str, Any], core: Any) -> str:
    user = (options.get("user") or "").strip() or core.get_username()
    return user.strip()


def _read_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [entry for entry in raw if isinstance(entry, dict)]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _append_snapshot(history: list[dict[str, Any]], total: int) -> list[dict[str, Any]]:
    """Append today's total, replacing today's entry if one already
    exists so successive renders within the same UTC day don't bloat
    the history."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    out = [e for e in history if e.get("date") != today]
    out.append({"date": today, "total": int(total)})
    out.sort(key=lambda e: e.get("date", ""))
    if len(out) > HISTORY_DAYS:
        out = out[-HISTORY_DAYS:]
    return out


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    del settings
    core = _core()
    if not core.get_token():
        return {"error": "Set a GitHub token in GitHub Core (GraphQL API requires auth)."}

    user = _resolve_user(options, core)
    if not user:
        return {"error": "Set a username here or a default in GitHub Core."}
    if not USERNAME_RE.match(user):
        return {"error": f"'{user}' isn't a valid GitHub username."}

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"star_count_{user}.json"
    history_path = data_dir / f"star_history_{user}.json"

    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_S:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    try:
        payload = core.request_graphql(_QUERY, {"login": user})
    except Exception as err:
        return {"error": core.coerce_error(err)}

    if isinstance(payload, dict) and payload.get("errors"):
        msg = payload["errors"][0].get("message") if payload["errors"] else "GraphQL error"
        return {"error": f"GitHub GraphQL: {msg}"}

    repos_block = (payload or {}).get("data", {}).get("user", {}).get("repositories") or {}
    nodes = repos_block.get("nodes") or []
    total_repos = int(repos_block.get("totalCount") or 0)
    total_stars = sum(int(n.get("stargazerCount") or 0) for n in nodes)

    top = sorted(nodes, key=lambda n: int(n.get("stargazerCount") or 0), reverse=True)[:3]
    top_clean = [
        {
            "name": str(t.get("name") or ""),
            "stars": int(t.get("stargazerCount") or 0),
            "url": str(t.get("url") or ""),
        }
        for t in top
        if t.get("name")
    ]

    history = _append_snapshot(_read_history(history_path), total_stars)
    history_path.write_text(json.dumps(history), encoding="utf-8")

    result: dict[str, Any] = {
        "user": user,
        "total_stars": total_stars,
        "total_repos": total_repos,
        "top": top_clean,
        "history": history,
    }
    cache.write_text(json.dumps(result), encoding="utf-8")
    return result
