"""Step 05: weekly insights report (the "reduce" step).

Map:    every review was already condensed to a one-line English summary.
Reduce: summaries are grouped by category; if a group is too large for one
        prompt, chunks are first condensed into notes (chunk_chain.batch),
        then one report chain writes headlines, praise and action items.

The LLM only writes the words. Every count and percentage in the final
report is inserted from pandas (``aggregate.WeeklyStats``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda

from .aggregate import WeeklyStats
from .llm import get_llm, is_mock
from .mock import mock_insights
from .schema import CATEGORY_LABELS, WeeklyInsights

MAX_LINES_PER_PROMPT = 120  # summaries per category before we condense (map-reduce)
CHUNK_SIZE = 60

CHUNK_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You condense customer review summaries into the recurring themes. "
                   "Return 3-6 short bullet points, each naming a concrete issue or praise and "
                   "roughly how often it appears (many / several / a few). No preamble."),
        ("human", "Category: {category}\nSummaries:\n{lines}"),
    ]
)

REPORT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", """You are an operations analyst writing a weekly customer-feedback brief for a
restaurant manager who has five minutes. Be specific and practical. Do NOT invent numbers:
counts are added by the system. Use details such as time slots, platforms and dish names when
the evidence shows them.

- complaint_themes: one headline per complaint category listed below, in the same order,
  max 8 words, specific (e.g. 'Late delivery, mostly 8pm-10pm on Swiggy').
- praise_highlights: up to 3 short phrases on what customers loved.
- action_items: exactly 3 concrete actions for this week. One of them should be about
  replying to the HIGH urgency reviews if there are any."""),
        ("human", """Week: {date_from} to {date_to}
Stats (from the database): {stats_line}
HIGH urgency reviews: {high_urgency}

Complaint categories (most frequent first), with evidence:
{complaint_evidence}

Praise categories (most frequent first), with evidence:
{praise_evidence}"""),
    ]
)


def build_chunk_chain(llm=None) -> Runnable:
    if llm is None and is_mock():
        return RunnableLambda(lambda inp: "\n".join(inp["lines"].splitlines()[:5]))
    return CHUNK_PROMPT | (llm or get_llm()) | StrOutputParser()


def build_report_chain(llm=None) -> Runnable:
    if llm is None and is_mock():
        return RunnableLambda(mock_insights)
    return REPORT_PROMPT | (llm or get_llm()).with_structured_output(WeeklyInsights)


def _evidence(df: pd.DataFrame, sentiment: str, categories: list[str], chunk_chain: Runnable) -> str:
    blocks = []
    for cat in categories:
        sub = df[(df["sentiment"] == sentiment) & (df["category"] == cat)]
        lines = [f"- [{r.platform}, {r.date}] {r.summary}" for r in sub.itertuples(index=False)]
        if len(lines) > MAX_LINES_PER_PROMPT:
            chunks = ["\n".join(lines[i:i + CHUNK_SIZE]) for i in range(0, len(lines), CHUNK_SIZE)]
            notes = chunk_chain.batch([{"category": cat, "lines": c} for c in chunks])
            body = "\n".join(notes)
        else:
            body = "\n".join(lines)
        blocks.append(f"## {cat} ({len(sub)} reviews)\n{body}")
    return "\n\n".join(blocks) or "(none)"


def generate_insights(
    df: pd.DataFrame,
    stats: WeeklyStats,
    report_chain: Runnable | None = None,
    chunk_chain: Runnable | None = None,
) -> WeeklyInsights:
    report_chain = report_chain or build_report_chain()
    chunk_chain = chunk_chain or build_chunk_chain()
    complaint_cats = [c.category for c in stats.top_complaints]
    praise_cats = [c.category for c in stats.top_praises]
    payload: dict[str, Any] = {
        "date_from": stats.date_from or "?",
        "date_to": stats.date_to or "?",
        "stats_line": (f"{stats.total} reviews; positive {stats.sentiment_pct['positive']}%, "
                       f"neutral {stats.sentiment_pct['neutral']}%, negative {stats.sentiment_pct['negative']}%"),
        "high_urgency": stats.high_urgency,
        "complaint_evidence": _evidence(df, "negative", complaint_cats, chunk_chain),
        "praise_evidence": _evidence(df, "positive", praise_cats, chunk_chain),
        # extra keys used by the offline mock chain
        "complaint_categories": complaint_cats,
        "praise_categories": praise_cats,
    }
    result = report_chain.invoke(payload)
    insights = result if isinstance(result, WeeklyInsights) else WeeklyInsights.model_validate(result)
    # Guarantee exactly 3 action items whatever the model returned.
    actions = [a.strip() for a in insights.action_items if a.strip()][:3]
    fallback = ["Reply to all HIGH urgency reviews today using the suggested replies.",
                "Brief the team on this week's top complaint.",
                "Check the 'needs review' rows manually."]
    while len(actions) < 3:
        actions.append(fallback[len(actions)])
    insights.action_items = actions
    return insights


def _fmt_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y").lstrip("0")
    except ValueError:
        return value or "?"


def render_report(stats: WeeklyStats, insights: WeeklyInsights, previous: WeeklyStats | None = None) -> str:
    """Plain-text report. Numbers from ``stats`` only (and ``previous`` for trend arrows)."""
    headlines = {t.category: t.headline.strip() for t in insights.complaint_themes}
    pct = stats.sentiment_pct
    width = 34
    lines = [
        f"WEEKLY FEEDBACK REPORT  |  {_fmt_date(stats.date_from)} to {_fmt_date(stats.date_to)}",
        "",
        f"Total reviews: {stats.total}   Positive {pct['positive']}%   "
        f"Neutral {pct['neutral']}%   Negative {pct['negative']}%",
    ]
    if stats.needs_review:
        lines.append(f"({stats.needs_review} review(s) could not be analysed and are marked 'needs_review')")

    lines += ["", f"TOP {len(stats.top_complaints)} COMPLAINTS" if stats.top_complaints else "TOP COMPLAINTS: none"]
    for i, c in enumerate(stats.top_complaints, 1):
        label = headlines.get(c.category) or CATEGORY_LABELS[c.category]
        noun = "review" if c.count == 1 else "reviews"
        lines.append(f" {i}. {label} {'.' * max(3, width - len(label))} {c.count} {noun}  "
                     f"(mostly {c.top_platform}, {c.top_platform_share}%)")

    lines += ["", "TOP PRAISE"]
    if stats.top_praises:
        lines.append(" " + ", ".join(f"{CATEGORY_LABELS[p.category]} ({p.count} mentions)" for p in stats.top_praises))
    if insights.praise_highlights:
        lines.append(" Customers loved: " + "; ".join(insights.praise_highlights[:3]))

    lines += ["", f"URGENT: {stats.high_urgency} review(s) need a reply within 24 hours", "", "ACTION ITEMS"]
    lines += [f" {i}. {a}" for i, a in enumerate(insights.action_items, 1)]

    if previous is not None:
        lines += ["", f"VS LAST WEEK  (week ending {_fmt_date(previous.date_to)})"]
        lines += [" " + trend_line(label, before, now) for label, before, now in _trend_rows(stats, previous)]
    return "\n".join(lines)


def trend_arrow(before: int, now: int) -> str:
    return "▲" if now > before else "▼" if now < before else "▶"


def trend_line(label: str, before: int, now: int, unit: str = "") -> str:
    diff = now - before
    sign = "+" if diff > 0 else ""
    return f"{trend_arrow(before, now)} {label}: {now}{unit} (last week {before}{unit}, {sign}{diff})"


def _trend_rows(cur: WeeklyStats, prev: WeeklyStats) -> list[tuple[str, int, int]]:
    rows = [
        ("Total reviews", prev.total, cur.total),
        ("Positive %", prev.sentiment_pct["positive"], cur.sentiment_pct["positive"]),
        ("Negative %", prev.sentiment_pct["negative"], cur.sentiment_pct["negative"]),
        ("HIGH urgency", prev.high_urgency, cur.high_urgency),
    ]
    for c in cur.top_complaints:
        rows.append((f"{CATEGORY_LABELS[c.category]} complaints",
                     prev.negative_by_category.get(c.category, 0), c.count))
    return rows
