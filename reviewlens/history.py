"""Week-by-week storage of analysed results.

Every analysed upload is saved under HISTORY_DIR (default ./history) as

    <week_end>/enriched.csv   - the enriched table (Excel-ready)
    <week_end>/report.txt     - the weekly report text
    <week_end>/meta.json      - date range, totals, saved_at

so that the next upload can show trend arrows against the previous week
automatically, and the Monday email job has a report to send.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd

from .export import to_excel_csv

_WEEK_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def history_dir() -> Path:
    return Path(os.getenv("HISTORY_DIR", "history"))


@dataclass
class SavedWeek:
    week_end: str
    path: Path

    @property
    def enriched_path(self) -> Path:
        return self.path / "enriched.csv"

    @property
    def report_path(self) -> Path:
        return self.path / "report.txt"

    @property
    def meta(self) -> dict:
        try:
            return json.loads((self.path / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def load_enriched(self) -> pd.DataFrame:
        return pd.read_csv(BytesIO(self.enriched_path.read_bytes()), dtype=str,
                           keep_default_na=False, encoding="utf-8-sig")

    def report_text(self) -> str:
        return self.report_path.read_text(encoding="utf-8")


def save_week(enriched: pd.DataFrame, report: str, week_start: str, week_end: str,
              root: Path | None = None) -> SavedWeek:
    """Save (or overwrite) the results for the week ending ``week_end``."""
    if not _WEEK_RE.match(week_end or ""):
        week_end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder = (root or history_dir()) / week_end
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "enriched.csv").write_bytes(to_excel_csv(enriched))
    (folder / "report.txt").write_text(report, encoding="utf-8")
    meta = {"week_start": week_start, "week_end": week_end, "total": int(len(enriched)),
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return SavedWeek(week_end, folder)


def list_weeks(root: Path | None = None) -> list[SavedWeek]:
    """All saved weeks, newest first."""
    base = root or history_dir()
    if not base.is_dir():
        return []
    weeks = [SavedWeek(p.name, p) for p in base.iterdir()
             if p.is_dir() and _WEEK_RE.match(p.name) and (p / "report.txt").exists()]
    return sorted(weeks, key=lambda w: w.week_end, reverse=True)


def latest_week(root: Path | None = None) -> SavedWeek | None:
    weeks = list_weeks(root)
    return weeks[0] if weeks else None


def previous_week(week_end: str, root: Path | None = None) -> SavedWeek | None:
    """Most recent saved week that ended before ``week_end``."""
    return next((w for w in list_weeks(root) if w.week_end < week_end), None)
