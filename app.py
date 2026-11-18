"""ReviewLens - Streamlit UI.

Run:  streamlit run app.py
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from reviewlens.aggregate import compare_weeks, compute_stats
from reviewlens.classify import analyse_reviews, build_review_chain
from reviewlens.export import to_excel_csv
from reviewlens.history import list_weeks, previous_week, save_week
from reviewlens.llm import get_model_name, get_provider, is_mock
from reviewlens.report import generate_insights, render_report
from reviewlens.schema import CATEGORIES, CATEGORY_LABELS, NEEDS_REVIEW, SENTIMENTS, URGENCIES
from reviewlens.validate import CSVValidationError, load_reviews, max_reviews

st.set_page_config(page_title="ReviewLens", page_icon="🔎", layout="wide")


def _require_password() -> None:
    """If APP_PASSWORD is set (e.g. on a public server), ask for it before anything runs."""
    expected = os.getenv("APP_PASSWORD", "")
    if not expected or st.session_state.get("authed"):
        return
    st.title("🔎 ReviewLens")
    entered = st.text_input("Password", type="password")
    if entered:
        if hmac.compare_digest(entered, expected):
            st.session_state.authed = True
            st.rerun()
        st.error("Wrong password.")
    st.stop()


_require_password()

SENTIMENT_COLORS = {"positive": "#2E9E5B", "neutral": "#9AA0A6", "negative": "#D64545", NEEDS_REVIEW: "#E0A800"}
URGENCY_COLORS = {"high": "#D64545", "medium": "#E8912D", "low": "#4C8BF5", NEEDS_REVIEW: "#E0A800"}

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("🔎 ReviewLens")
    st.caption("Customer feedback analyser")
    provider = get_provider()
    if is_mock(provider):
        st.warning("**Offline demo mode** (LLM_PROVIDER=mock). Results are keyword-based. "
                   "Set a real provider and API key in `.env` for LLM analysis.")
    else:
        st.success(f"Model: **{provider}** / `{get_model_name(provider)}`")

    st.subheader("Settings")
    max_concurrency = st.slider("Parallel requests (max_concurrency)", 1, 20, 8,
                                help="Lower this if you hit rate limits.")
    reply_lang = st.radio("Suggested reply language", ["English", "Same as review"], index=0)
    st.divider()
    prev_file = st.file_uploader("Optional: last week's enriched CSV (for trends)", type="csv", key="prev",
                                 help="Not needed if last week was saved as an official report - it is used automatically.")

st.title("ReviewLens: Customer Feedback Analyzer")
st.write("Upload this week's reviews (`review_id, date, platform, rating, review_text`). "
         "Every review is tagged by an LLM; counts are calculated with pandas.")

uploaded = st.file_uploader(f"Reviews CSV (up to {max_reviews()} reviews per upload)", type="csv")
if uploaded is None:
    st.info("No file yet? Download the sample week below, then upload it above.")
    sample = Path(__file__).parent / "data" / "reviews_week40.csv"
    if sample.exists():
        st.download_button("⬇️ Download sample reviews_week40.csv", sample.read_bytes(),
                           file_name="reviews_week40.csv", mime="text/csv")
    st.stop()

# ---------------------------------------------------------------- validate
try:
    validation = load_reviews(uploaded)
except CSVValidationError as exc:
    st.error(f"CSV problem: {exc}")
    st.stop()

reviews = validation.df
for w in validation.warnings:
    st.warning(w)
st.success(f"{len(reviews)} valid reviews loaded.")
with st.expander("Preview input"):
    st.dataframe(reviews.head(20), use_container_width=True, hide_index=True)

file_key = hashlib.md5(uploaded.getvalue()).hexdigest() + reply_lang + provider
if st.session_state.get("file_key") != file_key:
    st.session_state.pop("enriched", None)
    st.session_state.pop("report", None)

if "enriched" not in st.session_state:
    if not st.button(f"Analyse {len(reviews)} reviews", type="primary"):
        st.stop()
    bar = st.progress(0.0, text="Classifying reviews…")
    started = time.time()
    try:
        chain = build_review_chain()
        enriched = analyse_reviews(
            reviews,
            chain,
            max_concurrency=max_concurrency,
            reply_language="same" if reply_lang == "Same as review" else "english",
            progress=lambda done, total: bar.progress(done / total, text=f"Classified {done}/{total} reviews"),
        )
    except Exception as exc:  # noqa: BLE001 - surface config/API errors to the user
        st.error(f"Analysis failed: {exc}")
        st.stop()
    bar.progress(1.0, text=f"Done in {time.time() - started:.0f}s")
    st.session_state.enriched = enriched
    st.session_state.file_key = file_key

enriched: pd.DataFrame = st.session_state.enriched
stats = compute_stats(enriched)

# ---------------------------------------------------------------- last week (for trend arrows)
prev_stats, prev_label = None, ""
if prev_file is not None:
    prev_df = pd.read_csv(prev_file, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if {"sentiment", "category", "urgency", "language", "platform", "date"}.issubset(prev_df.columns):
        prev_stats, prev_label = compute_stats(prev_df), f"uploaded file {prev_file.name}"
    else:
        st.sidebar.error("That file is not an enriched ReviewLens export.")
if prev_stats is None and stats.date_to:
    saved_prev = previous_week(stats.date_to)
    if saved_prev is not None:
        prev_stats, prev_label = compute_stats(saved_prev.load_enriched()), f"saved week ending {saved_prev.week_end}"

if st.session_state.get("prev_label") != prev_label:
    st.session_state.prev_label = prev_label
    st.session_state.pop("report", None)

if "report" not in st.session_state:
    with st.spinner("Writing weekly insights report…"):
        try:
            insights = generate_insights(enriched, stats)
            st.session_state.report = render_report(stats, insights, prev_stats)
        except Exception as exc:  # noqa: BLE001
            st.session_state.report = f"Report could not be generated: {exc}"

# ---------------------------------------------------------------- KPIs
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total reviews", stats.total)
k2.metric("Positive", f"{stats.sentiment_pct['positive']}%")
k3.metric("Negative", f"{stats.sentiment_pct['negative']}%")
k4.metric("🔴 HIGH urgency", stats.high_urgency)
k5.metric("Needs review", stats.needs_review)

tab_dash, tab_reviews, tab_report, tab_trend = st.tabs(["📊 Dashboard", "📝 Reviews", "📄 Weekly report", "📈 Trend"])

with tab_dash:
    c1, c2 = st.columns(2)
    sent_df = pd.DataFrame({"sentiment": list(stats.sentiment_counts), "reviews": list(stats.sentiment_counts.values())})
    c1.plotly_chart(
        px.pie(sent_df, names="sentiment", values="reviews", hole=0.5, title="Sentiment split",
               color="sentiment", color_discrete_map=SENTIMENT_COLORS),
        use_container_width=True,
    )
    ok = enriched[enriched["sentiment"] != NEEDS_REVIEW]
    cat_df = (ok.groupby(["category", "sentiment"]).size().reset_index(name="reviews"))
    cat_df["category"] = cat_df["category"].map(CATEGORY_LABELS)
    c2.plotly_chart(
        px.bar(cat_df, x="reviews", y="category", color="sentiment", orientation="h", title="Reviews by category",
               color_discrete_map=SENTIMENT_COLORS, category_orders={"sentiment": list(SENTIMENTS)}),
        use_container_width=True,
    )
    c3, c4 = st.columns(2)
    urg_df = pd.DataFrame({"urgency": list(stats.urgency_counts), "reviews": list(stats.urgency_counts.values())})
    c3.plotly_chart(px.bar(urg_df, x="urgency", y="reviews", title="Urgency", color="urgency",
                           color_discrete_map=URGENCY_COLORS), use_container_width=True)
    plat_df = ok.groupby(["platform", "sentiment"]).size().reset_index(name="reviews")
    c4.plotly_chart(px.bar(plat_df, x="platform", y="reviews", color="sentiment", title="By platform",
                           color_discrete_map=SENTIMENT_COLORS), use_container_width=True)
    st.caption("Languages detected: " + ", ".join(f"{k} {v}" for k, v in stats.language_counts.items()))

with tab_reviews:
    f1, f2, f3, f4 = st.columns([1, 2, 2, 2])
    high_only = f1.toggle("HIGH urgency only", value=False)
    sel_sent = f2.multiselect("Sentiment", list(SENTIMENTS) + [NEEDS_REVIEW])
    sel_cat = f3.multiselect("Category", list(CATEGORIES) + [NEEDS_REVIEW])
    sel_plat = f4.multiselect("Platform", sorted(enriched["platform"].unique()))
    view = enriched
    if high_only:
        view = view[view["urgency"] == "high"]
    if sel_sent:
        view = view[view["sentiment"].isin(sel_sent)]
    if sel_cat:
        view = view[view["category"].isin(sel_cat)]
    if sel_plat:
        view = view[view["platform"].isin(sel_plat)]
    urgency_rank = {u: i for i, u in enumerate(reversed(URGENCIES))}
    view = view.sort_values("urgency", key=lambda s: s.map(urgency_rank).fillna(9))
    st.write(f"Showing **{len(view)}** of {len(enriched)} reviews")
    st.dataframe(
        view[["review_id", "date", "platform", "rating", "urgency", "sentiment", "category", "language",
              "summary", "suggested_reply", "review_text"]],
        use_container_width=True, hide_index=True, height=520,
        column_config={"suggested_reply": st.column_config.TextColumn(width="large"),
                       "summary": st.column_config.TextColumn(width="medium")},
    )
    st.download_button("⬇️ Download enriched CSV (Excel-ready)", to_excel_csv(enriched),
                       file_name=f"reviews_enriched_{stats.date_to or 'week'}.csv", mime="text/csv", type="primary")
    if len(view) != len(enriched):
        st.download_button("⬇️ Download filtered rows", to_excel_csv(view),
                           file_name="reviews_filtered.csv", mime="text/csv")

with tab_report:
    st.code(st.session_state.report, language=None, wrap_lines=True)
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Download report (.txt)", st.session_state.report.encode("utf-8"),
                       file_name=f"weekly_report_{stats.date_to or 'week'}.txt")
    if c2.button("🔄 Regenerate report"):
        st.session_state.pop("report", None)
        st.rerun()

    st.divider()
    st.subheader("Official weekly report")
    st.caption(f"Saving keeps this week's results on the server for next week's trend arrows "
               f"and for the automatic Monday email. Week: {stats.date_from} to {stats.date_to}.")
    if st.button("💾 Save as this week's official report"):
        try:
            saved = save_week(enriched, st.session_state.report, stats.date_from, stats.date_to)
            st.success(f"Saved as the official report for the week ending {saved.week_end}.")
        except OSError as exc:
            st.error(f"Could not save: {exc}")
    weeks = list_weeks()
    if weeks:
        st.caption("Saved weeks: " + ", ".join(w.week_end for w in weeks[:8]))

with tab_trend:
    if prev_stats is None:
        st.info("No previous week to compare with yet. Save each week as the official report (Weekly report tab) "
                "and next week's upload shows trend arrows automatically - or upload last week's enriched CSV "
                "in the sidebar.")
    else:
        st.write(f"Compared with **{prev_label}**")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total reviews", stats.total, stats.total - prev_stats.total)
        m2.metric("Positive %", f"{stats.sentiment_pct['positive']}%",
                  f"{stats.sentiment_pct['positive'] - prev_stats.sentiment_pct['positive']} pts")
        m3.metric("Negative %", f"{stats.sentiment_pct['negative']}%",
                  f"{stats.sentiment_pct['negative'] - prev_stats.sentiment_pct['negative']} pts", delta_color="inverse")
        m4.metric("HIGH urgency", stats.high_urgency, stats.high_urgency - prev_stats.high_urgency,
                  delta_color="inverse")
        st.dataframe(compare_weeks(stats, prev_stats), use_container_width=True, hide_index=True)
        st.caption("▲ went up, ▼ went down. For complaints and urgency, ▼ is good news.")
