"""Step 03: tag every review with a structured-output LCEL chain (the "map" step)."""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import ValidationError

from .llm import get_llm, is_mock
from .mock import mock_analyse
from .schema import NEEDS_REVIEW, ReviewAnalysis

SYSTEM_PROMPT = """You are a customer-feedback analyst for an Indian restaurant / food-delivery business.
Reviews come from Google, Zomato, Swiggy and Amazon and may be written in English, Tamil
(Tamil script) or Tanglish (Tamil written in English letters, often mixed with English).
Understand the meaning in any of these languages.

Rules:
- category must be exactly one of: food_quality, delivery, price, staff, packaging, app.
  Pick the MAIN problem (or main praise) of the review.
- urgency = high when the review mentions food poisoning, illness, hygiene (hair, insects,
  stale food), wrong or missing order, refund or overcharge demands, rude/abusive staff or
  safety. medium = a clear complaint without those risks. low = praise, neutral or minor.
- summary: ONE short English sentence, even when the review is Tamil or Tanglish. Keep facts
  such as times, amounts and dish names.
- suggested_reply: polite, warm, 2-3 sentences, apologise for complaints, thank for praise,
  never promise specific compensation, invite the customer to DM their order ID when
  something went wrong. {reply_language_rule}

Tanglish hints: "nalla" = good, "irundhuchu" = was, "romba" = very, "saapadu" = food,
"late ah" = late, "bill la extra charge pottanga" = they added an extra charge to the bill,
"kovama pesunanga" = spoke angrily, "kedu" / "kettu pochu" = spoiled."""

HUMAN_PROMPT = """Review ID: {review_id}
Platform: {platform}
Star rating: {rating}
Review text:
\"\"\"{review_text}\"\"\""""

REPLY_RULES = {
    "english": "Write the reply in English.",
    "same": (
        "Write the reply in the SAME language and script as the review "
        "(English review -> English, Tamil script -> Tamil script, Tanglish -> Tanglish)."
    ),
}

PROMPT = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)])

OUTPUT_COLUMNS = ["sentiment", "category", "urgency", "language", "summary", "suggested_reply", "status"]


def build_review_chain(llm=None) -> Runnable:
    """prompt | llm.with_structured_output(ReviewAnalysis)

    Passing ``llm=None`` while LLM_PROVIDER=mock returns an offline keyword-based
    chain with the same input/output contract (useful for demos and tests).
    """
    if llm is None and is_mock():
        return RunnableLambda(mock_analyse)
    llm = llm or get_llm()
    return PROMPT | llm.with_structured_output(ReviewAnalysis)


def _to_inputs(df: pd.DataFrame, reply_language: str) -> list[dict[str, Any]]:
    rule = REPLY_RULES.get(reply_language, REPLY_RULES["english"])
    return [
        {
            "review_id": row.review_id,
            "platform": row.platform,
            "rating": "" if pd.isna(row.rating) else int(row.rating),
            "review_text": row.review_text,
            "reply_language_rule": rule,
        }
        for row in df.itertuples(index=False)
    ]


def _coerce(result: Any) -> ReviewAnalysis:
    """Re-validate whatever the model returned. Raises on anything invalid."""
    if isinstance(result, Exception):
        raise result
    if isinstance(result, ReviewAnalysis):
        return ReviewAnalysis.model_validate(result.model_dump())
    if isinstance(result, dict):
        return ReviewAnalysis.model_validate(result)
    raise ValueError(f"Unexpected model output: {type(result).__name__}")


def analyse_reviews(
    df: pd.DataFrame,
    chain: Runnable | None = None,
    *,
    max_concurrency: int = 8,
    batch_size: int = 25,
    max_retries: int = 2,
    reply_language: str = "english",
    progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Run the chain over every review with ``chain.batch`` and retry failures.

    A review whose output is invalid (bad enum value, empty field, API error)
    is retried up to ``max_retries`` times; if it still fails it is marked
    ``needs_review`` instead of crashing the whole run.
    """
    chain = chain or build_review_chain()
    inputs = _to_inputs(df, reply_language)
    total = len(inputs)
    results: list[ReviewAnalysis | None] = [None] * total
    errors: list[str] = [""] * total
    config = {"max_concurrency": max_concurrency}

    def run(indices: list[int]) -> list[int]:
        failed: list[int] = []
        outputs = chain.batch([inputs[i] for i in indices], config=config, return_exceptions=True)
        for i, out in zip(indices, outputs):
            try:
                results[i] = _coerce(out)
            except (ValidationError, ValueError, Exception) as exc:  # noqa: BLE001
                errors[i] = f"{type(exc).__name__}: {str(exc)[:200]}"
                failed.append(i)
        return failed

    pending: list[int] = []
    done = 0
    for start in range(0, total, batch_size):
        chunk = list(range(start, min(start + batch_size, total)))
        pending.extend(run(chunk))
        done += len(chunk)
        if progress:
            progress(done, total)

    for _ in range(max_retries):
        if not pending:
            break
        pending = run(pending)

    rows = []
    for i, res in enumerate(results):
        if res is None:
            rows.append(
                {
                    "sentiment": NEEDS_REVIEW,
                    "category": NEEDS_REVIEW,
                    "urgency": NEEDS_REVIEW,
                    "language": NEEDS_REVIEW,
                    "summary": "Could not be analysed automatically - please read manually.",
                    "suggested_reply": "",
                    "status": f"needs_review ({errors[i]})",
                }
            )
        else:
            rows.append({**res.model_dump(), "status": "ok"})

    enriched = pd.concat([df.reset_index(drop=True), pd.DataFrame(rows, columns=OUTPUT_COLUMNS)], axis=1)
    return enriched
