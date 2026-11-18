"""Long-running job that emails the weekly report every Monday.

Runs as its own container (see docker-compose.yml):
    python -m reviewlens.scheduler

Settings (.env): REPORT_DAY (default monday), REPORT_TIME (default 09:00),
REPORT_TIMEZONE (default Asia/Kolkata) plus the SMTP_* settings used by emailer.py.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .emailer import send_weekly_report

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def next_run(now: datetime, weekday: int, hour: int, minute: int) -> datetime:
    """Next datetime (same tz as ``now``) on ``weekday`` at hour:minute, strictly after ``now``."""
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    candidate += timedelta(days=(weekday - now.weekday()) % 7)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def _log(text: str) -> None:
    print(f"[scheduler {datetime.now().isoformat(timespec='seconds')}] {text}", flush=True)


def main() -> None:
    tz = ZoneInfo(os.getenv("REPORT_TIMEZONE", "Asia/Kolkata"))
    day = os.getenv("REPORT_DAY", "monday").strip().lower()
    weekday = DAYS.index(day) if day in DAYS else 0
    hour, minute = (int(x) for x in os.getenv("REPORT_TIME", "09:00").split(":"))

    while True:
        target = next_run(datetime.now(tz), weekday, hour, minute)
        _log(f"next weekly email at {target.isoformat()}")
        while (remaining := (target - datetime.now(tz)).total_seconds()) > 0:
            time.sleep(min(remaining, 3600))
        try:
            _log(send_weekly_report())
        except Exception as exc:  # noqa: BLE001 - keep the scheduler alive, retry next week
            _log(f"ERROR sending weekly report: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
