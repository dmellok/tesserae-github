"""github_ci_status, full-bleed CI status banner.

For each watched repo we fetch the most recent run per workflow, take
its conclusion, and bucket the repo by worst-state across its
workflows: failing > running > passing. The widget paints the
worst-state colour edge-to-edge and names any failing repos so the
banner answers "is anything red right now" without a click.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from flask import current_app

CACHE_TTL_S = 120
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

# Conclusion → severity rank. Higher rank wins when summarising a
# repo's many workflows down to one badge.
SEVERITY = {
    "failure": 3,
    "timed_out": 3,
    "startup_failure": 3,
    "action_required": 3,
    "in_progress": 2,
    "queued": 2,
    "waiting": 2,
    "neutral": 1,
    "cancelled": 1,
    "skipped": 1,
    "success": 0,
}


def _core() -> Any:
    return current_app.config["PLUGIN_REGISTRY"].get("github_core").server_module


def _state(run: dict[str, Any]) -> str:
    status = (run.get("status") or "").lower()
    conclusion = (run.get("conclusion") or "").lower()
    if status in {"in_progress", "queued", "waiting"}:
        return status
    return conclusion or "neutral"


def _summarise_repo(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Reduce a repo's recent runs to one summary: pick the most-severe
    state across the latest run of each workflow, plus counts."""
    by_workflow: dict[str, dict[str, Any]] = {}
    for r in runs:
        name = r.get("name") or ""
        if name not in by_workflow:
            by_workflow[name] = r
    states: dict[str, int] = {}
    worst = "success"
    for r in by_workflow.values():
        s = _state(r)
        states[s] = states.get(s, 0) + 1
        if SEVERITY.get(s, 0) > SEVERITY.get(worst, 0):
            worst = s
    return {
        "worst": worst,
        "states": states,
        "workflow_count": len(by_workflow),
    }


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    del settings
    raw = options.get("repos") or ""
    repos = [r.strip() for r in raw.replace(",", "\n").splitlines() if REPO_RE.match(r.strip())]
    if not repos:
        return {"error": "Add one or more repos (owner/repo, one per line)."}

    core = _core()
    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^A-Za-z0-9]", "_", ",".join(repos))[:120]
    cache = data_dir / f"ci_status_{key}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_S:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    per_repo: list[dict[str, Any]] = []
    fail_repos: list[str] = []
    running_repos: list[str] = []
    pass_repos: list[str] = []
    fetch_errors: list[str] = []

    for repo in repos:
        try:
            payload = core.request_json(
                f"https://api.github.com/repos/{repo}/actions/runs?per_page=30"
            )
        except Exception as err:
            fetch_errors.append(f"{repo}: {core.coerce_error(err)}")
            continue
        runs = payload.get("workflow_runs") or []
        if not runs:
            continue
        summary = _summarise_repo(runs)
        worst = summary["worst"]
        per_repo.append(
            {
                "repo": repo,
                "worst": worst,
                "workflow_count": summary["workflow_count"],
            }
        )
        if SEVERITY.get(worst, 0) >= SEVERITY["failure"]:
            fail_repos.append(repo)
        elif SEVERITY.get(worst, 0) >= SEVERITY["in_progress"]:
            running_repos.append(repo)
        else:
            pass_repos.append(repo)

    if not per_repo and fetch_errors:
        return {"error": fetch_errors[0]}

    if fail_repos:
        state = "failing"
    elif running_repos:
        state = "running"
    else:
        state = "passing"

    result = {
        "state": state,
        "repos": per_repo,
        "failing": fail_repos,
        "running": running_repos,
        "passing": pass_repos,
        "total": len(per_repo),
        "errors": fetch_errors,
    }
    cache.write_text(json.dumps(result), encoding="utf-8")
    return result
