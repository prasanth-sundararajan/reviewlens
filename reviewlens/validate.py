"""Step 02: validate and clean the uploaded CSV."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import IO

import pandas as pd

REQUIRED_COLUMNS = ["review_id", "date", "platform", "rating", "review_text"]


def max_reviews() -> int:
    """Upper limit of reviews per upload (MAX_REVIEWS env, default 500). Caps cost per run."""
    try:
        return max(1, int(os.getenv("MAX_REVIEWS", "500")))
    except ValueError:
        return 500


@dataclass
class ValidationResult:
    df: pd.DataFrame
    warnings: list[str] = field(default_factory=list)


class CSVValidationError(ValueError):
    pass


def load_reviews(source: str | IO) -> ValidationResult:
    """Read a CSV (path or file-like) and validate it."""
    try:
        raw = pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except UnicodeDecodeError:
        if hasattr(source, "seek"):
            source.seek(0)
        raw = pd.read_csv(source, dtype=str, keep_default_na=False, encoding="latin-1")
    except pd.errors.EmptyDataError as exc:
        raise CSVValidationError("The file is empty.") from exc
    return validate_reviews(raw)


def validate_reviews(raw: pd.DataFrame) -> ValidationResult:
    warnings: list[str] = []
    df = raw.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise CSVValidationError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected: {', '.join(REQUIRED_COLUMNS)}."
        )

    df = df[REQUIRED_COLUMNS].copy()
    for col in REQUIRED_COLUMNS:
        df[col] = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})

    empty = df["review_text"] == ""
    if empty.any():
        warnings.append(f"Dropped {int(empty.sum())} row(s) with empty review_text.")
        df = df[~empty]

    no_id = df["review_id"] == ""
    if no_id.any():
        df.loc[no_id, "review_id"] = [f"AUTO-{i + 1:04d}" for i in range(int(no_id.sum()))]
        warnings.append(f"Generated IDs for {int(no_id.sum())} row(s) without review_id.")

    dupes = df["review_id"].duplicated(keep="first")
    if dupes.any():
        warnings.append(f"Dropped {int(dupes.sum())} duplicate review_id row(s).")
        df = df[~dupes]

    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    bad_rating = df["rating"].notna() & ~df["rating"].between(1, 5)
    if bad_rating.any():
        warnings.append(f"{int(bad_rating.sum())} rating(s) outside 1-5 were cleared.")
        df.loc[bad_rating, "rating"] = pd.NA
    df["rating"] = df["rating"].astype("Int64")

    parsed = pd.to_datetime(df["date"], errors="coerce", dayfirst=False)
    bad_dates = parsed.isna() & (df["date"] != "")
    if bad_dates.any():
        warnings.append(f"{int(bad_dates.sum())} date(s) could not be parsed and were left blank.")
    df["date"] = parsed.dt.strftime("%Y-%m-%d").fillna("")

    df["platform"] = df["platform"].replace("", "Unknown")

    if df.empty:
        raise CSVValidationError("No usable reviews found after cleaning.")

    limit = max_reviews()
    if len(df) > limit:
        raise CSVValidationError(
            f"This file has {len(df)} reviews, but the limit is {limit} per upload. "
            f"Please split it into smaller files (for example one file per week)."
        )

    return ValidationResult(df=df.reset_index(drop=True), warnings=warnings)
