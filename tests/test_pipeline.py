"""Offline tests: no API key needed (uses fake / mock runnables)."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest
from langchain_core.runnables import RunnableLambda

from reviewlens.aggregate import compare_weeks, compute_stats, percentages
from reviewlens.classify import analyse_reviews
from reviewlens.export import to_excel_csv
from reviewlens.mock import mock_analyse
from reviewlens.report import build_chunk_chain, build_report_chain, generate_insights, render_report
from reviewlens.schema import CATEGORIES, LANGUAGES, NEEDS_REVIEW, SENTIMENTS, URGENCIES
from reviewlens.validate import CSVValidationError, load_reviews

DATA = Path(__file__).resolve().parents[1] / "data"
MOCK = RunnableLambda(mock_analyse)


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")


def test_validation_cleans_dirty_rows():
    res = load_reviews(DATA / "reviews_week40.csv")
    assert len(res.df) == 248  # 251 rows - 2 empty - 1 duplicate
    assert any("empty review_text" in w for w in res.warnings)
    assert any("duplicate" in w for w in res.warnings)


def test_validation_missing_column():
    with pytest.raises(CSVValidationError, match="review_text"):
        load_reviews(io.StringIO("review_id,date,platform,rating\nR-1,2026-10-01,Google,5\n"))


def test_full_pipeline_200_plus_rows():
    df = load_reviews(DATA / "reviews_week40.csv").df
    enriched = analyse_reviews(df, MOCK, max_concurrency=10)
    assert len(enriched) == len(df) >= 200
    assert enriched["sentiment"].isin(SENTIMENTS).all()
    assert enriched["category"].isin(CATEGORIES).all()
    assert enriched["urgency"].isin(URGENCIES).all()
    assert enriched["language"].isin(LANGUAGES).all()
    assert (enriched["summary"].str.len() > 0).all()
    assert (enriched["suggested_reply"].str.len() > 0).all()
    assert set(enriched["language"]) >= {"English", "Tamil", "Tanglish"}


def test_invalid_output_is_retried_then_marked_needs_review():
    df = load_reviews(DATA / "reviews_week40.csv").df.head(5)
    calls: dict[str, int] = {}

    def flaky(inp):
        rid = inp["review_id"]
        calls[rid] = calls.get(rid, 0) + 1
        out = mock_analyse(inp).model_dump()
        if rid == df.review_id[0] and calls[rid] == 1:
            out["category"] = "ambience"  # not in the allowed list -> retried, then OK
        if rid == df.review_id[1]:
            out["urgency"] = "critical"  # always invalid -> needs_review
        return out

    enriched = analyse_reviews(df, RunnableLambda(flaky), max_retries=2)
    assert enriched.loc[0, "status"] == "ok" and calls[df.review_id[0]] == 2
    assert enriched.loc[1, "category"] == NEEDS_REVIEW
    assert enriched.loc[1, "status"].startswith("needs_review")
    assert calls[df.review_id[1]] == 3  # first try + 2 retries
    assert (enriched.loc[2:, "status"] == "ok").all()


def test_report_numbers_match_table():
    df = load_reviews(DATA / "reviews_week40.csv").df
    enriched = analyse_reviews(df, MOCK)
    stats = compute_stats(enriched)
    assert sum(stats.sentiment_pct.values()) == 100
    assert stats.sentiment_counts["negative"] == (enriched["sentiment"] == "negative").sum()
    assert stats.high_urgency == (enriched["urgency"] == "high").sum()
    top = stats.top_complaints[0]
    expected = ((enriched["sentiment"] == "negative") & (enriched["category"] == top.category)).sum()
    assert top.count == expected

    insights = generate_insights(enriched, stats, build_report_chain(), build_chunk_chain())
    text = render_report(stats, insights)
    assert f"Total reviews: {stats.total}" in text
    assert f"URGENT: {stats.high_urgency} review(s)" in text
    assert f"{top.count} reviews" in text
    assert len(insights.action_items) == 3


def test_percentages_sum_to_100():
    assert percentages({"a": 1, "b": 1, "c": 1}, 3) == {"a": 34, "b": 33, "c": 33}
    assert sum(percentages({"a": 151, "b": 35, "c": 62}, 248).values()) == 100


def test_export_is_excel_friendly_and_roundtrips():
    df = load_reviews(DATA / "reviews_week40.csv").df
    enriched = analyse_reviews(df, MOCK)
    data = to_excel_csv(enriched)
    assert data.startswith(b"\xef\xbb\xbf")  # BOM for Excel
    back = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
    assert len(back) == len(enriched)
    assert back["review_text"].str.contains("பிரியாணி").any()


def test_week_over_week_trend():
    cur = compute_stats(analyse_reviews(load_reviews(DATA / "reviews_week40.csv").df, MOCK))
    prev = compute_stats(analyse_reviews(load_reviews(DATA / "reviews_week39.csv").df, MOCK))
    trend = compare_weeks(cur, prev)
    assert {"metric", "last_week", "this_week", "trend"} <= set(trend.columns)
    assert set(trend["trend"]) <= {"▲", "▼", "▶"}
