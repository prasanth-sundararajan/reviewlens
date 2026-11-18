"""Tests for the 500-review limit, weekly history/trends, email and scheduler (offline)."""
from __future__ import annotations

import io
from datetime import datetime
from email import message_from_bytes
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from langchain_core.runnables import RunnableLambda

from reviewlens import emailer, history
from reviewlens.aggregate import compute_stats
from reviewlens.classify import analyse_reviews
from reviewlens.mock import mock_analyse
from reviewlens.report import build_chunk_chain, build_report_chain, generate_insights, render_report
from reviewlens.scheduler import next_run
from reviewlens.validate import CSVValidationError, load_reviews

DATA = Path(__file__).resolve().parents[1] / "data"
MOCK = RunnableLambda(mock_analyse)


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path / "history"))
    for k in ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "REPORT_RECIPIENTS", "SMTP_FROM"]:
        monkeypatch.delenv(k, raising=False)


def _week(name: str):
    df = load_reviews(DATA / name).df
    enriched = analyse_reviews(df, MOCK)
    stats = compute_stats(enriched)
    return enriched, stats


def test_review_limit(monkeypatch):
    rows = "\n".join(f"R{i},2026-10-01,Google,5,good food {i}" for i in range(501))
    csv = "review_id,date,platform,rating,review_text\n" + rows
    with pytest.raises(CSVValidationError, match="limit is 500"):
        load_reviews(io.StringIO(csv))
    monkeypatch.setenv("MAX_REVIEWS", "1000")
    assert len(load_reviews(io.StringIO(csv)).df) == 501


def test_history_and_trend_in_report():
    e39, s39 = _week("reviews_week39.csv")
    history.save_week(e39, "week 39 report", s39.date_from, s39.date_to)
    e40, s40 = _week("reviews_week40.csv")

    prev = history.previous_week(s40.date_to)
    assert prev is not None and prev.week_end == s39.date_to
    prev_stats = compute_stats(prev.load_enriched())
    assert prev_stats.total == s39.total
    assert prev_stats.negative_by_category == s39.negative_by_category

    text = render_report(s40, generate_insights(e40, s40, build_report_chain(), build_chunk_chain()), prev_stats)
    assert "VS LAST WEEK" in text
    assert f"Total reviews: {s40.total} (last week {s39.total}" in text
    assert any(a in text for a in "▲▼▶")


def _configure_smtp(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "x")
    monkeypatch.setenv("REPORT_RECIPIENTS", "a@example.com, b@example.com")


def test_email_sends_latest_week_once(monkeypatch):
    _configure_smtp(monkeypatch)
    e40, s40 = _week("reviews_week40.csv")
    history.save_week(e40, "REPORT BODY 40", s40.date_from, s40.date_to)
    sent = []
    monkeypatch.setattr(emailer, "send_message", lambda msg, settings: sent.append(msg))

    assert emailer.send_weekly_report().startswith("Sent")
    msg = message_from_bytes(sent[0].as_bytes())
    assert s40.date_to in msg["Subject"] and msg["To"] == "a@example.com, b@example.com"
    parts = list(msg.walk())
    assert any("REPORT BODY 40" in (p.get_payload(decode=True) or b"").decode("utf-8", "ignore") for p in parts)
    assert any((p.get_filename() or "").endswith(".csv") for p in parts)

    assert emailer.send_weekly_report().startswith("Skipped")  # only once per week
    assert emailer.send_weekly_report(force=True).startswith("Sent")
    assert len(sent) == 2


def test_email_reminder_when_nothing_saved(monkeypatch):
    _configure_smtp(monkeypatch)
    sent = []
    monkeypatch.setattr(emailer, "send_message", lambda msg, settings: sent.append(msg))
    emailer.send_weekly_report()
    assert "no weekly report" in sent[0]["Subject"]


def test_email_not_sent_without_settings():
    assert emailer.send_weekly_report().startswith("Not sent: missing settings")


def test_scheduler_next_monday():
    ist = ZoneInfo("Asia/Kolkata")
    wed = datetime(2026, 11, 18, 12, 0, tzinfo=ist)
    assert next_run(wed, 0, 9, 0) == datetime(2026, 11, 23, 9, 0, tzinfo=ist)
    mon_early = datetime(2026, 11, 23, 8, 0, tzinfo=ist)
    assert next_run(mon_early, 0, 9, 0) == datetime(2026, 11, 23, 9, 0, tzinfo=ist)
    mon_late = datetime(2026, 11, 23, 9, 0, tzinfo=ist)
    assert next_run(mon_late, 0, 9, 0) == datetime(2026, 11, 30, 9, 0, tzinfo=ist)
