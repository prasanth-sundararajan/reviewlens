"""Step 06: Excel-friendly CSV export."""
from __future__ import annotations

import pandas as pd

EXPORT_COLUMNS = [
    "review_id", "date", "platform", "rating", "sentiment", "category", "urgency",
    "language", "summary", "suggested_reply", "review_text", "status", "guardrails",
]


def to_excel_csv(df: pd.DataFrame) -> bytes:
    """UTF-8 with BOM so Excel shows Tamil text and ₹ correctly; CRLF line endings."""
    cols = [c for c in EXPORT_COLUMNS if c in df.columns]
    return df[cols].to_csv(index=False, lineterminator="\r\n").encode("utf-8-sig")
