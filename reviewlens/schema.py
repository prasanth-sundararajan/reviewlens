"""Typed output contracts for every LLM call.

The per-review chain is forced (via ``with_structured_output``) to return a
``ReviewAnalysis``. Any value outside the allowed lists fails Pydantic
validation, which triggers the automatic retry in ``classify.py``.
"""
from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator

Sentiment = Literal["positive", "neutral", "negative"]
Category = Literal["food_quality", "delivery", "price", "staff", "packaging", "app"]
Urgency = Literal["low", "medium", "high"]
Language = Literal["English", "Tamil", "Tanglish", "Other"]

SENTIMENTS: tuple[str, ...] = get_args(Sentiment)
CATEGORIES: tuple[str, ...] = get_args(Category)
URGENCIES: tuple[str, ...] = get_args(Urgency)
LANGUAGES: tuple[str, ...] = get_args(Language)

NEEDS_REVIEW = "needs_review"

CATEGORY_LABELS = {
    "food_quality": "Food quality",
    "delivery": "Delivery",
    "price": "Price / billing",
    "staff": "Staff / service",
    "packaging": "Packaging",
    "app": "App / ordering",
}


class ReviewAnalysis(BaseModel):
    """Structured analysis of one customer review."""

    sentiment: Sentiment = Field(description="Overall customer mood: positive, neutral or negative.")
    category: Category = Field(
        description=(
            "The single main topic. food_quality = taste, freshness, quantity, hygiene; "
            "delivery = late, cold, missing or wrong order in transit; price = bill, extra "
            "charges, value for money, refunds; staff = behaviour of waiters, cashier, rider; "
            "packaging = leaks, spills, container quality; app = ordering app, payment, coupons."
        )
    )
    urgency: Urgency = Field(
        description=(
            "high = needs a reply today: health/hygiene/food poisoning, wrong or missing order, "
            "refund or overcharge demand, abusive or rude staff, safety; medium = clear complaint "
            "without those risks; low = praise, neutral remarks or minor suggestions."
        )
    )
    language: Language = Field(
        description="Language of the original review: English, Tamil (Tamil script), Tanglish (Tamil in Latin script, often mixed with English) or Other."
    )
    summary: str = Field(description="ONE short English sentence describing what the customer said.")
    suggested_reply: str = Field(description="A polite, ready-to-post reply to the customer (2-3 sentences).")

    @field_validator("summary", "suggested_reply")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("must not be empty")
        return value


class ComplaintTheme(BaseModel):
    category: Category = Field(description="Category this complaint theme belongs to.")
    headline: str = Field(description="Short specific label, e.g. 'Late delivery, mostly 8pm-10pm'. Max 8 words.")


class WeeklyInsights(BaseModel):
    """Qualitative part of the weekly report. All numbers are added later by pandas."""

    complaint_themes: list[ComplaintTheme] = Field(
        description="One specific headline for each complaint category given in the input, same order."
    )
    praise_highlights: list[str] = Field(
        description="Up to 3 short phrases naming what customers praised most, e.g. 'Biryani taste'."
    )
    action_items: list[str] = Field(
        description="Exactly 3 concrete, practical actions the manager can take this week."
    )
