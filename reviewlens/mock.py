"""Offline stand-ins for the LLM chains (LLM_PROVIDER=mock).

They follow the exact same input/output contracts as the real chains, so the
whole app - batching, retries, aggregation, report, export - can be demoed
and tested without an API key. Quality is keyword-level only.
"""
from __future__ import annotations

import re
from typing import Any

from .schema import CATEGORY_LABELS, ReviewAnalysis, WeeklyInsights, ComplaintTheme

_TAMIL_SCRIPT = re.compile(r"[஀-௿]")
_TANGLISH_WORDS = {
    "nalla", "romba", "irundhuchu", "irunthuchu", "saapadu", "sapadu", "pottanga", "illa",
    "vandhuchu", "vanthuchu", "kovama", "pesunanga", "semma", "kedu", "konjam", "aana",
    "chumma", "vera", "level", "suda", "panna", "pannanga", "kudukala", "theriyala", "ah",
}

_CATEGORY_KEYWORDS = {
    "delivery": ["late", "delivery", "deliver", "rider", "cold", "came at", "missing", "wrong order",
                 "wrong item", "vandhuchu", "vanthuchu", "டெலிவரி", "தாமதம்"],
    "price": ["bill", "charge", "price", "cost", "expensive", "refund", "overcharg", "money", "rs",
              "₹", "பில்", "விலை"],
    "staff": ["staff", "waiter", "rude", "manager", "service", "cashier", "behav", "kovama",
              "ஊழியர்"],
    "packaging": ["pack", "spill", "leak", "container", "box", "seal", "பேக்"],
    "app": ["app", "payment", "coupon", "promo", "crash", "otp", "upi"],
    "food_quality": ["taste", "biryani", "food", "spicy", "salt", "fresh", "stale", "portion",
                     "saapadu", "sapadu", "சாப்பாடு", "சுவை", "hair", "oily"],
}
_HIGH = ["poison", "vomit", "sick", "hospital", "hair", "insect", "cockroach", "stale", "wrong order",
         "wrong item", "missing", "refund", "rude", "abus", "overcharg", "extra charge", "fraud",
         "kedu", "kettu", "kovama", "வாந்தி", "கெட்டு"]
_NEG = ["bad", "worst", "late", "cold", "rude", "poor", "not", "never", "disappoint", "extra",
        "missing", "wrong", "stale", "spill", "leak", "crash", "illa", "mosam", "kedu", "மோசம்"]
_POS = ["amazing", "great", "good", "excellent", "love", "tasty", "nice", "neat", "best",
        "nalla", "semma", "super", "awesome", "delicious", "நன்றாக", "சூப்பர்", "அருமை"]


def _language(text: str) -> str:
    if _TAMIL_SCRIPT.search(text):
        return "Tamil"
    words = set(re.findall(r"[a-z]+", text.lower()))
    return "Tanglish" if len(words & _TANGLISH_WORDS) >= 1 else "English"


def mock_analyse(inp: dict[str, Any]) -> ReviewAnalysis:
    text = str(inp.get("review_text", ""))
    low = text.lower()
    try:
        rating = int(inp.get("rating") or 3)
    except (TypeError, ValueError):
        rating = 3

    scores = {cat: sum(k in low for k in kws) for cat, kws in _CATEGORY_KEYWORDS.items()}
    category = max(scores, key=lambda c: (scores[c], c == "food_quality"))

    neg = sum(k in low for k in _NEG)
    pos = sum(k in low for k in _POS)
    if rating >= 4 and neg <= pos:
        sentiment = "positive"
    elif rating <= 2 or neg > pos:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    if sentiment == "negative" and any(k in low for k in _HIGH):
        urgency = "high"
    elif sentiment == "negative":
        urgency = "medium"
    else:
        urgency = "low"

    label = CATEGORY_LABELS[category].lower()
    language = _language(text)
    if sentiment == "positive":
        summary = f"Customer is happy with the {label}."
        reply = "Thank you so much for your kind words! We are glad you enjoyed it and hope to serve you again soon."
    elif sentiment == "negative":
        summary = f"Customer complains about {label} ({rating}-star review)."
        reply = (f"We are really sorry about the {label} issue you faced. We have shared this with our team. "
                 "Please DM us your order ID so we can make it right.")
    else:
        summary = f"Customer gives mixed feedback about {label}."
        reply = "Thank you for your feedback. We will use it to keep improving."
    return ReviewAnalysis(sentiment=sentiment, category=category, urgency=urgency, language=language,
                          summary=summary, suggested_reply=reply)


def mock_insights(inp: dict[str, Any]) -> WeeklyInsights:
    cats = inp.get("complaint_categories", [])
    themes = [ComplaintTheme(category=c, headline=f"{CATEGORY_LABELS[c]} complaints") for c in cats]
    praise = [CATEGORY_LABELS[c] for c in inp.get("praise_categories", [])][:3]
    actions = []
    if cats:
        actions.append(f"Review the {CATEGORY_LABELS[cats[0]].lower()} process with the team this week.")
    actions.append("Reply to all HIGH urgency reviews today using the suggested replies.")
    actions.append("Share this week's top praise with staff to keep what works.")
    while len(actions) < 3:
        actions.append("Re-check the 'needs review' rows manually.")
    return WeeklyInsights(complaint_themes=themes, praise_highlights=praise, action_items=actions[:3])
