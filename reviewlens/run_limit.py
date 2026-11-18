"""Daily run limit: at most MAX_RUNS_PER_DAY review analyses per day (default 3).

- An analysis is counted the moment it starts (failed ones count too: they also spend API credit).
- The count resets at midnight India time (IST, UTC+5:30).
- The counter lives in HISTORY_DIR/run_limit.json (the persistent volume on the server) and is
  updated under a lock, so two people pressing Analyse at once cannot both slip past the limit.
- Offline demo mode (LLM_PROVIDER=mock) spends nothing and is not counted.

Settings (environment):
    MAX_RUNS_PER_DAY    analyses allowed per day, default 3 (0 = no limit)
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))
_lock = threading.RLock()


class RunLimitReached(RuntimeError):
    """Raised when today's analyses are used up."""


def _path() -> Path:
    return Path(os.getenv("HISTORY_DIR", Path(__file__).resolve().parent.parent / "history")) / "run_limit.json"


def limit_per_day() -> int:
    try:
        return max(0, int(os.getenv("MAX_RUNS_PER_DAY", "3")))
    except ValueError:
        return 3


def _today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def _load() -> dict[str, Any]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if data.get("day") != _today():
        data = {"day": _today(), "runs": []}
    return data


def _save(data: dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)


def status() -> dict[str, Any]:
    with _lock:
        data = _load()
    limit = limit_per_day()
    used = len(data["runs"])
    return {"day": data["day"], "limit": limit, "used": used,
            "runs_left": max(limit - used, 0) if limit else None,
            "can_start": (not limit) or used < limit}


def start_run(reviews: int) -> None:
    """Reserve one analysis for today; raises RunLimitReached when none are left."""
    with _lock:
        data = _load()
        limit = limit_per_day()
        if limit and len(data["runs"]) >= limit:
            raise RunLimitReached(f"Daily limit reached: {limit} of {limit} analyses used today. "
                                  "New analyses open again at midnight (India time).")
        data["runs"].append({"at": datetime.now(IST).isoformat(timespec="seconds"), "reviews": reviews})
        _save(data)
