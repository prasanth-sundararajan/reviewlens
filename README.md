# 🔎 ReviewLens: Customer Feedback Analyzer

> Track 1 Gen AI | LangChain — Use case 01 (Intermediate)

Turn hundreds of raw customer reviews (English, Tamil and Tanglish) from Google, Zomato, Swiggy and Amazon into **tagged, prioritised insights** and a **weekly report a manager can act on in five minutes**.

## Features

| Requirement | How it is done |
|---|---|
| Upload a CSV (`review_id, date, platform, rating, review_text`) | Streamlit uploader + `reviewlens/validate.py` (checks columns, drops empty/duplicate rows, cleans ratings/dates) |
| Fixed structure per review: sentiment, category, urgency, language, summary, suggested reply | LCEL chain `ChatPromptTemplate \| llm.with_structured_output(ReviewAnalysis)` with a Pydantic model whose fields are `Literal` enums |
| Invalid LLM value → automatic retry → `needs_review` | `analyse_reviews()` re-validates every output, retries failed reviews (default 2 retries), then marks them `needs_review` instead of crashing |
| Hundreds of reviews fast and within rate limits | `chain.batch(..., config={"max_concurrency": n})` in chunks of 25 with a progress bar |
| Tamil & Tanglish understood, summarised in English | Prompt rules + Tanglish glossary; `language` field detected per review |
| Weekly insights report (map → reduce) | Per-review summaries (map) → grouped by category, condensed in chunks if large → one report chain writes headlines, praise and **exactly 3 action items** |
| Report numbers are exact | All counts/percentages come from pandas (`aggregate.py`); the LLM only writes words. Percentages use largest-remainder rounding so they sum to 100 |
| Dashboard | Sentiment donut, category × sentiment bar, urgency bar, platform bar, language counts, KPI tiles |
| HIGH urgency filter | Toggle in the *Reviews* tab (+ sentiment / category / platform filters) |
| Excel-ready export | UTF-8 **with BOM** CSV so Tamil text and ₹ show correctly in Excel |
| API key from `.env`, never hard-coded | `python-dotenv`; provider SDKs read the key from the environment |
| Swap models without changing the chain | `LLM_PROVIDER=openai \| gemini \| anthropic \| mock` in `.env` |

**Stretch goals done:** week-over-week trend arrows (upload last week's enriched CSV), replies in the same language as the review (sidebar toggle).
Not done: automatic Monday email.

## Quick start

```bash
git clone https://github.com/prasanth-sundararajan/reviewlens.git
cd reviewlens
python -m venv .venv && .venv\Scripts\activate      # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env                              # cp on macOS/Linux, then add your API key
streamlit run app.py
```

Upload `data/reviews_week40.csv` (248 reviews + a few dirty rows) and press **Analyse**.

📥 **Sample data:** [download reviews_week40.csv](https://github.com/prasanth-sundararajan/reviewlens/releases/download/v1.0/reviews_week40.csv) (also in [`data/`](data/reviews_week40.csv) and on the [v1.0 release](https://github.com/prasanth-sundararajan/reviewlens/releases/tag/v1.0); the live app has a download button too).

No API key yet? Set `LLM_PROVIDER=mock` in `.env` to try the full app offline (keyword-based results, same pipeline).

### Using Gemini or Claude instead of OpenAI

```bash
pip install langchain-google-genai     # then LLM_PROVIDER=gemini   + GOOGLE_API_KEY
pip install langchain-anthropic        # then LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY
```
Optionally set `LLM_MODEL` to pick a specific model.

## How it works

```
01 Upload CSV → 02 Validate → 03 Classify (chain.batch, retries) → 04 Aggregate (pandas)
             → 05 Report (map-reduce chain) → 06 Dashboard + CSV export
```

```
reviewlens/
  schema.py     Pydantic models: ReviewAnalysis, WeeklyInsights (allowed values as Literals)
  llm.py        Provider factory (OpenAI / Gemini / Claude / mock) - reads .env
  validate.py   Step 02: column checks and cleaning
  classify.py   Step 03: prompt | llm.with_structured_output(...), batching, retry, needs_review
  aggregate.py  Step 04: counts, percentages, top complaints/praise, week-over-week trend
  report.py     Step 05: map-reduce report chain + plain-text renderer (numbers from pandas)
  export.py     Step 06: Excel-friendly CSV
  mock.py       Offline stand-in chains with the same contracts (demo + tests)
app.py          Streamlit UI
scripts/make_sample_data.py   Generates data/reviews_week40.csv and reviews_week39.csv
tests/          Offline pytest suite
```

### Output A: one analysed review

```json
{
  "review_id": "R-1042",
  "sentiment": "negative",
  "category": "delivery",
  "urgency": "high",
  "language": "English",
  "summary": "Order arrived 70 minutes late and the food was cold.",
  "suggested_reply": "We are really sorry your order reached late and cold. ..."
}
```

| Field | Allowed values |
|---|---|
| sentiment | positive, neutral, negative |
| category | food_quality, delivery, price, staff, packaging, app |
| urgency | low, medium, high (high = health, refund, abuse, wrong/missing order) |
| language | English, Tamil, Tanglish, Other |

### Output B: weekly report (format)

```
WEEKLY FEEDBACK REPORT  |  29 Sep 2026 to 5 Oct 2026

Total reviews: 248   Positive 57%   Neutral 8%   Negative 35%

TOP 3 COMPLAINTS
 1. Late delivery, mostly 8pm-10pm .... 51 reviews  (mostly Swiggy, 82%)
 ...
URGENT: 22 review(s) need a reply within 24 hours

ACTION ITEMS
 1. ...
```

## Tests

```bash
pytest -q
```
Runs offline (no API key): validation, 200+ row pipeline, retry → `needs_review`, report numbers == table, percentages sum to 100, Excel export round-trip with Tamil text, trend table.

## Verified run (OpenAI `gpt-4o-mini`, `data/reviews_week40.csv`)

- 248 reviews classified in ~52 s at `max_concurrency=8`; 248/248 valid on the first attempt, 0 `needs_review`
- Languages detected: English 173, Tanglish 52, Tamil 23 — all with correct English summaries, e.g.
  - *"Order late ah vandhuchu, 9:30 ku dhaan vandhuchu. Food suda illa."* → "The order was delivered late at 9:30 PM and the food was cold."
  - *"பில்லில் கூடுதல் கட்டணம் போட்டாங்க, சொல்லவே இல்லை."* → "They added an extra charge to the bill without informing me."
- HIGH urgency: food poisoning / spoiled food, hair, wrong or missing orders, refund demands, money debited without an order, rude staff
- Weekly report generated in ~6 s; all counts match the enriched table

## Done checklist

- [x] Processes a 200+ row CSV without crashing or timing out (batched, concurrent, per-review error isolation)
- [x] Every review has all 6 fields and every value is from the allowed list (Pydantic enums + re-validation + retry)
- [x] Tamil and Tanglish reviews get an English summary
- [x] Report numbers exactly match the table (calculated in pandas, tested)
- [x] HIGH urgency filter works; enriched CSV opens correctly in Excel
- [x] API key loaded from `.env`, never hard-coded
