"""Step 04: all numbers come from pandas, never from the LLM."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .schema import CATEGORIES, NEEDS_REVIEW, SENTIMENTS, URGENCIES


def percentages(counts: dict[str, int], total: int) -> dict[str, int]:
    """Whole-number percentages that always add up to exactly 100 (largest remainder)."""
    if total <= 0:
        return {k: 0 for k in counts}
    raw = {k: v * 100 / total for k, v in counts.items()}
    floored = {k: int(v) for k, v in raw.items()}
    short = 100 - sum(floored.values())
    for k in sorted(raw, key=lambda k: raw[k] - floored[k], reverse=True)[:max(short, 0)]:
        floored[k] += 1
    return floored


@dataclass
class CategoryStat:
    category: str
    count: int
    top_platform: str
    top_platform_share: int  # percent of this category's reviews
    peak_language: str


@dataclass
class WeeklyStats:
    total: int
    analysed: int
    needs_review: int
    date_from: str
    date_to: str
    sentiment_counts: dict[str, int]
    sentiment_pct: dict[str, int]
    category_counts: dict[str, int]
    urgency_counts: dict[str, int]
    language_counts: dict[str, int]
    negative_by_category: dict[str, int] = field(default_factory=dict)
    top_complaints: list[CategoryStat] = field(default_factory=list)
    top_praises: list[CategoryStat] = field(default_factory=list)

    @property
    def high_urgency(self) -> int:
        return self.urgency_counts.get("high", 0)


def _category_stats(sub: pd.DataFrame, limit: int) -> list[CategoryStat]:
    out = []
    for cat, group in sub.groupby("category"):
        plat = group["platform"].value_counts()
        lang = group["language"].value_counts()
        out.append(
            CategoryStat(
                category=str(cat),
                count=len(group),
                top_platform=str(plat.index[0]),
                top_platform_share=round(plat.iloc[0] * 100 / len(group)),
                peak_language=str(lang.index[0]),
            )
        )
    out.sort(key=lambda s: (-s.count, s.category))
    return out[:limit]


def compute_stats(df: pd.DataFrame, top_n: int = 3) -> WeeklyStats:
    ok = df[df["sentiment"] != NEEDS_REVIEW]
    total = len(df)
    analysed = len(ok)

    sentiment_counts = {s: int((ok["sentiment"] == s).sum()) for s in SENTIMENTS}
    dates = df["date"][df["date"] != ""]
    return WeeklyStats(
        total=total,
        analysed=analysed,
        needs_review=total - analysed,
        date_from=str(dates.min()) if not dates.empty else "",
        date_to=str(dates.max()) if not dates.empty else "",
        sentiment_counts=sentiment_counts,
        sentiment_pct=percentages(sentiment_counts, analysed),
        category_counts={c: int((ok["category"] == c).sum()) for c in CATEGORIES},
        urgency_counts={u: int((ok["urgency"] == u).sum()) for u in URGENCIES},
        language_counts={str(k): int(v) for k, v in ok["language"].value_counts().items()},
        negative_by_category={
            c: int(((ok["category"] == c) & (ok["sentiment"] == "negative")).sum()) for c in CATEGORIES
        },
        top_complaints=_category_stats(ok[ok["sentiment"] == "negative"], top_n),
        top_praises=_category_stats(ok[ok["sentiment"] == "positive"], top_n),
    )


def compare_weeks(current: WeeklyStats, previous: WeeklyStats) -> pd.DataFrame:
    """Week-over-week trend table (stretch goal)."""
    rows = []
    for s in SENTIMENTS:
        rows.append((f"{s.title()} %", previous.sentiment_pct[s], current.sentiment_pct[s]))
    rows.append(("HIGH urgency reviews", previous.high_urgency, current.high_urgency))
    rows.append(("Total reviews", previous.total, current.total))
    for c in CATEGORIES:
        rows.append((f"Complaints: {c}", _neg(previous, c), _neg(current, c)))

    def arrow(prev, cur):
        return "▲" if cur > prev else "▼" if cur < prev else "▶"

    return pd.DataFrame(
        [{"metric": m, "last_week": p, "this_week": c, "change": c - p, "trend": arrow(p, c)} for m, p, c in rows]
    )


def _neg(stats: WeeklyStats, category: str) -> int:
    return stats.negative_by_category.get(category, 0)
