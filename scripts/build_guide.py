"""Build docs/ReviewLens_Build_Guide.pdf - a step-by-step guide to building and deploying ReviewLens.

    pip install reportlab
    python scripts/build_guide.py
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

OUT = Path(__file__).resolve().parents[1] / "docs" / "ReviewLens_Build_Guide.pdf"
SHOTS = OUT.parent / "screenshots"

SCREENS = [
    ("01_start_page", "Start page", "Upload box (max 500 reviews), sample CSV download, sidebar with model, "
     "parallel-request slider and reply-language option."),
    ("02_upload_validation", "Upload and validation", "Empty and duplicate rows are dropped with a warning before "
     "any LLM call; 248 valid reviews are ready to analyse."),
    ("03_dashboard", "Dashboard", "KPI tiles, sentiment split, reviews by category, urgency and platform charts, "
     "languages detected (English, Tanglish, Tamil)."),
    ("04_high_urgency_reviews", "HIGH urgency filter", "Only the 25 reviews that need a reply today, with summary, "
     "suggested reply and the Excel-ready CSV download."),
    ("05_weekly_report", "Weekly report", "Top complaints, top praise, urgent count, 3 action items and the "
     "'VS LAST WEEK' trend section. Saved as the official report for the Monday email."),
    ("06_trend_vs_last_week", "Trend vs last week", "Automatic comparison with the last saved week: arrows and "
     "deltas for sentiment, urgency and each complaint category."),
    ("07_same_language_replies", "Replies in the review's language", "Tamil reviews get Tamil replies, Tanglish "
     "gets Tanglish, English gets English - summaries stay in English."),
    ("08_review_limit", "500-review limit", "Files over the limit are rejected with a clear message - a cost guard "
     "for a public app."),
    ("09_weekly_email", "Monday email", "The saved weekly report as it arrives every Monday 09:00 IST, with the "
     "enriched CSV attached."),
]
REPO = "https://github.com/prasanth-sundararajan/reviewlens"

INK = colors.HexColor("#1F2328")
MUTED = colors.HexColor("#57606A")
ACCENT = colors.HexColor("#C0392B")
CODE_BG = colors.HexColor("#F4F5F7")
RULE = colors.HexColor("#D0D7DE")

ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=26, leading=31,
                            textColor=INK, alignment=TA_CENTER, spaceAfter=6),
    "subtitle": ParagraphStyle("st", parent=ss["Normal"], fontSize=12.5, leading=17, textColor=MUTED,
                               alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=16.5, leading=21,
                         textColor=INK, spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=16,
                         textColor=ACCENT, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica", fontSize=10, leading=14.5,
                           textColor=INK, spaceAfter=6),
    "bullet": ParagraphStyle("bl", parent=ss["Normal"], fontName="Helvetica", fontSize=10, leading=14.5,
                             textColor=INK, leftIndent=14, bulletIndent=3, spaceAfter=2),
    "note": ParagraphStyle("n", parent=ss["Normal"], fontName="Helvetica-Oblique", fontSize=9.5, leading=13.5,
                           textColor=MUTED, spaceAfter=6),
    "code": ParagraphStyle("c", fontName="Courier", fontSize=8.4, leading=10.8, textColor=INK),
    "cell": ParagraphStyle("cell", parent=ss["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=INK),
    "cellb": ParagraphStyle("cellb", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12,
                            textColor=colors.white),
}


def p(text): return Paragraph(text, S["body"])
def h1(text): return Paragraph(text, S["h1"])
def h2(text): return Paragraph(text, S["h2"])
def note(text): return Paragraph(text, S["note"])
def bullets(items): return [Paragraph(i, S["bullet"], bulletText="•") for i in items]


def code(text: str):
    pre = Preformatted(text.strip("\n"), S["code"])
    t = Table([[pre]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CODE_BG), ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 6)])


def table(rows, widths):
    data = [[Paragraph(c, S["cellb"]) for c in rows[0]]] + [[Paragraph(c, S["cell"]) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), INK), ("GRID", (0, 0), (-1, -1), 0.5, RULE),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFBFC")]),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return KeepTogether([t, Spacer(1, 8)])


def screenshot(name: str, max_w=170 * mm, max_h=200 * mm):
    path = SHOTS / f"{name}.png"
    if not path.exists():
        return Paragraph(f"(missing screenshot {name}.png)", S["note"])
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    scale = min(max_w / w, max_h / h)
    img = Image(str(path), width=w * scale, height=h * scale)
    frame = Table([[img]], colWidths=[w * scale + 2])
    frame.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return frame


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, "ReviewLens - Step-by-step build & deploy guide")
    canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.line(20 * mm, 16 * mm, 190 * mm, 16 * mm)
    canvas.restoreState()


def build() -> Path:
    s: list = []

    # ------------------------------------------------------------------ cover
    s += [Spacer(1, 55 * mm), Paragraph("ReviewLens", S["title"]),
          Paragraph("Customer Feedback Analyzer", S["subtitle"]), Spacer(1, 4 * mm),
          Paragraph("Step-by-step guide: build it with LangChain + Streamlit, test it, "
                    "run it in Docker and deploy it live with HTTPS and a weekly email", S["subtitle"]),
          Spacer(1, 18 * mm),
          table([["Track", "Level", "Interface", "Core skill"],
                 ["Gen AI | LangChain (Use case 01)", "Intermediate", "Streamlit web app", "Structured LLM output"]],
                [55, 30, 40, 45]),
          Spacer(1, 10 * mm), Paragraph(f"Source code: {REPO}", S["subtitle"]), PageBreak()]

    # ------------------------------------------------------------------ 1 overview
    s += [h1("1. What you are building"),
          p("A restaurant chain or online store receives 200-500 reviews a week from Google, Zomato, Swiggy "
            "and Amazon, in English, Tamil and Tanglish. Today a manager reads them by hand, urgent complaints "
            "are missed for days and nobody can say with numbers what customers complain about most."),
          p("<b>ReviewLens</b> turns that weekly CSV into tagged, prioritised insights and a weekly report a "
            "manager can act on in five minutes:"),
          *bullets([
              "Every review gets <b>sentiment, category, urgency, language, a one-line English summary and a "
              "polite suggested reply</b> from a LangChain chain with a fixed (Pydantic) structure.",
              "Tamil and Tanglish reviews are understood and summarised in English.",
              "A second chain writes the <b>weekly report</b>: top complaints, top praise and 3 action items. "
              "All numbers are calculated in pandas, never guessed by the LLM.",
              "A <b>dashboard</b> (sentiment split, category chart, HIGH-urgency filter) and an "
              "<b>Excel-ready CSV export</b>.",
              "Stretch goals: <b>trend arrows vs last week</b>, <b>replies in the review's own language</b>, "
              "and the <b>report emailed automatically every Monday</b>.",
          ]),
          h2("How it works"),
          table([["#", "Step", "Where in the code"],
                 ["01", "Upload CSV (review_id, date, platform, rating, review_text)", "app.py"],
                 ["02", "Validate: check columns, drop empty / duplicate rows, max 500 reviews", "reviewlens/validate.py"],
                 ["03", "Classify every review in batches; retry invalid output, else 'needs_review'", "reviewlens/classify.py"],
                 ["04", "Aggregate counts by sentiment, category, urgency (pandas)", "reviewlens/aggregate.py"],
                 ["05", "Report chain writes weekly insights (map -> reduce)", "reviewlens/report.py"],
                 ["06", "Dashboard + Excel CSV download", "app.py, reviewlens/export.py"],
                 ["+", "Saved weeks, trend arrows, Monday email", "history.py, emailer.py, scheduler.py"]],
                [10, 105, 55]),
          h2("Tech stack"),
          table([["Part", "Used for"],
                 ["LangChain (ChatPromptTemplate, LCEL | chains)", "Clean, reusable prompt pipelines"],
                 ["Pydantic + with_structured_output()", "Forcing valid, typed JSON from the LLM every time"],
                 ["chain.batch(max_concurrency=...)", "Processing hundreds of reviews fast, within rate limits"],
                 ["OpenAI gpt-4o-mini (Gemini / Claude also supported)", "The LLM - swappable in .env"],
                 ["Streamlit + pandas + Plotly", "Web UI, numbers and charts"],
                 ["Docker + Caddy", "Packaging, HTTPS reverse proxy with automatic Let's Encrypt certificates"],
                 ["pytest", "Offline tests (no API key needed)"]],
                [80, 90]),
          PageBreak()]

    # ------------------------------------------------------------------ 2 prerequisites
    s += [h1("2. Prerequisites"),
          table([["You need", "Why"],
                 ["Python 3.11 or newer", "Runs the app and tests"],
                 ["Git + a GitHub account", "Version control and hosting the code"],
                 ["Docker Desktop (Windows/Mac) or Docker Engine (Linux)", "Run it the same way locally and on the server"],
                 ["An OpenAI API key", "platform.openai.com -> API keys. Set a monthly budget under Settings -> Limits."],
                 ["(Deploy) A Linux VPS + a domain", "Live website, e.g. Ubuntu on Hostinger KVM"],
                 ["(Email) A Gmail account with 2-Step Verification", "To create a Gmail App Password for the Monday email"]],
                [75, 95]),
          note("Never put API keys or passwords in code or in Git. They live only in a .env file, "
               "which is listed in .gitignore."),

          h1("3. Step 1 - Create the project"),
          code("""
mkdir reviewlens && cd reviewlens
git init -b main
python -m venv .venv
.venv\\Scripts\\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
mkdir reviewlens data tests scripts docs
"""),
          p("Create <b>requirements.txt</b> and install it:"),
          code("""
streamlit>=1.40
pandas>=2.2
plotly>=5.20
pydantic>=2.7
python-dotenv>=1.0
langchain-core>=0.3
langchain-openai>=0.2
tzdata>=2024.1
pytest>=8.0
"""),
          code("pip install -r requirements.txt"),
          p("Create <b>.gitignore</b> so secrets and generated files never reach GitHub:"),
          code("""
.env
__pycache__/
.venv/
.pytest_cache/
history/
"""),

          h1("4. Step 2 - Settings (.env) and the model factory"),
          p("Create <b>.env.example</b> (committed, no real values) and copy it to <b>.env</b> (never committed):"),
          code("""
LLM_PROVIDER=openai          # openai | gemini | anthropic | mock (offline demo)
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=              # paste your key in .env only
MAX_REVIEWS=500              # cost guard per upload
"""),
          p("<b>reviewlens/llm.py</b> reads these with python-dotenv and returns a LangChain chat model. Because "
            "every chain receives the model from here, switching OpenAI -> Gemini -> Claude needs no chain changes:"),
          code("""
load_dotenv()

def get_llm():
    provider = os.getenv("LLM_PROVIDER", "openai")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set - add it to .env")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                      temperature=0, max_retries=3, timeout=60)
"""),
          note("The repo version also supports gemini, anthropic and an offline 'mock' provider used by the tests."),
          PageBreak()]

    # ------------------------------------------------------------------ schema + validate
    s += [h1("5. Step 3 - The output contract (Pydantic schema)"),
          p("This is the heart of 'structured LLM output'. Allowed values are <b>Literal</b> types, so a "
            "category outside the list fails validation automatically. File: <b>reviewlens/schema.py</b>"),
          code("""
Sentiment = Literal["positive", "neutral", "negative"]
Category  = Literal["food_quality", "delivery", "price", "staff", "packaging", "app"]
Urgency   = Literal["low", "medium", "high"]
Language  = Literal["English", "Tamil", "Tanglish", "Other"]

class ReviewAnalysis(BaseModel):
    sentiment: Sentiment
    category: Category
    urgency: Urgency = Field(description="high = health/hygiene, wrong or missing "
                             "order, refund/overcharge, rude staff -> reply today")
    language: Language
    summary: str = Field(description="ONE short English sentence")
    suggested_reply: str = Field(description="Polite, ready-to-post reply")
"""),
          p("A second model, <b>WeeklyInsights</b>, holds the report's words: complaint headlines, praise "
            "highlights and exactly 3 action items."),

          h1("6. Step 4 - Validate the CSV"),
          p("<b>reviewlens/validate.py</b> runs before any LLM call, so bad files fail fast and cheap:"),
          *bullets(["Normalise column names; stop with a clear message if a required column is missing.",
                    "Drop rows with empty review_text and duplicate review_ids (reported as warnings).",
                    "Clean ratings to 1-5 and parse dates.",
                    "Reject files with more than <b>MAX_REVIEWS</b> (default 500) reviews - a cost guard."]),
          code("""
missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
if missing:
    raise CSVValidationError(f"Missing required column(s): {', '.join(missing)}")
df = df[df["review_text"] != ""]                          # drop empty reviews
df = df[~df["review_id"].duplicated(keep="first")]        # drop duplicates
if len(df) > max_reviews():
    raise CSVValidationError("... limit is 500 per upload. Please split the file.")
"""),
          PageBreak()]

    # ------------------------------------------------------------------ classify
    s += [h1("7. Step 5 - Classify every review (the 'map' step)"),
          p("<b>reviewlens/classify.py</b> builds an LCEL chain: <b>prompt | llm.with_structured_output(ReviewAnalysis)</b>. "
            "The system prompt explains the categories, the urgency rules and gives Tanglish hints "
            "(nalla = good, romba = very, saapadu = food, ...)."),
          code("""
PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),   # rules + Tanglish glossary + {reply_language_rule}
    ("human", "Platform: {platform}\\nStar rating: {rating}\\nReview: {review_text}"),
])
chain = PROMPT | get_llm().with_structured_output(ReviewAnalysis)
"""),
          h2("Batching with a concurrency limit"),
          code("""
outputs = chain.batch(inputs, config={"max_concurrency": 8},
                      return_exceptions=True)   # one bad review never stops the run
"""),
          h2("Retry, then 'needs_review'"),
          p("Every output is re-validated with Pydantic. Reviews that failed (invalid value, empty field, API "
            "error) are sent again up to 2 times; whatever still fails is marked <b>needs_review</b> with the reason:"),
          code("""
for attempt in range(max_retries):
    if not pending:
        break
    pending = run(pending)            # re-batch only the failed reviews
# still failing -> sentiment/category/urgency = "needs_review", status = reason
"""),
          h2("Replies in the review's own language (stretch goal)"),
          p("The prompt variable <b>{reply_language_rule}</b> is either 'Write the reply in English' or 'Write "
            "the reply in the SAME language and script as the review'. A sidebar toggle in the app chooses it. "
            "Summaries always stay in English."),

          h1("8. Step 6 - Aggregate with pandas"),
          p("<b>reviewlens/aggregate.py</b> computes every number in the report: counts and percentages by "
            "sentiment, category, urgency and language, the top complaint and praise categories with their main "
            "platform, and week-over-week differences. Percentages use largest-remainder rounding so they always "
            "add up to exactly 100."),
          note("Rule of thumb: the LLM writes words, pandas writes numbers. That is why the report's counts "
               "always match the table."),
          PageBreak()]

    # ------------------------------------------------------------------ report + export + UI
    s += [h1("9. Step 7 - The weekly report (the 'reduce' step)"),
          p("All reviews do not fit in one prompt, so <b>reviewlens/report.py</b> uses map -> reduce: the per-review "
            "summaries (map) are grouped by category; very large groups are first condensed in chunks "
            "(chunk_chain.batch); then one report chain returns <b>WeeklyInsights</b>. Python then renders the text "
            "and inserts the pandas numbers:"),
          code("""
WEEKLY FEEDBACK REPORT  |  29 Sep 2026 to 5 Oct 2026
Total reviews: 248   Positive 57%   Neutral 12%   Negative 31%
TOP 3 COMPLAINTS
 1. Late delivery, mostly 9:30 PM on Swiggy ... 40 reviews (mostly Swiggy, 82%)
 ...
URGENT: 25 review(s) need a reply within 24 hours
ACTION ITEMS
 1. Respond to all 25 HIGH urgency reviews promptly
 ...
VS LAST WEEK  (week ending 28 Sep 2026)
 up   HIGH urgency: 25 (last week 17, +8)
"""),

          h1("10. Step 8 - Excel-ready export"),
          p("<b>reviewlens/export.py</b> writes the enriched table as CSV with a UTF-8 byte-order mark (BOM) and "
            "Windows line endings, so Excel shows Tamil text and the rupee sign correctly:"),
          code('df.to_csv(index=False, lineterminator="\\r\\n").encode("utf-8-sig")'),

          h1("11. Step 9 - The Streamlit app"),
          p("<b>app.py</b> wires everything together:"),
          *bullets(["Sidebar: model in use, parallel-request slider, reply-language toggle, optional last-week CSV.",
                    "Upload -> validation messages -> <b>Analyse N reviews</b> button with a progress bar.",
                    "KPI tiles (total, positive %, negative %, HIGH urgency, needs review).",
                    "Tabs: <b>Dashboard</b> (charts), <b>Reviews</b> (HIGH-urgency toggle, filters, CSV download), "
                    "<b>Weekly report</b> (report, .txt download, <b>Save as this week's official report</b>), "
                    "<b>Trend</b> (arrows vs last saved week).",
                    "Results are kept in st.session_state so re-runs do not call the LLM again."]),
          code("streamlit run app.py          # opens http://localhost:8501"),
          note("No API key yet? Set LLM_PROVIDER=mock in .env to click through the whole app offline."),
          PageBreak()]

    # ------------------------------------------------------------------ data, tests, stretch
    s += [h1("12. Step 10 - Sample data and tests"),
          p("<b>scripts/make_sample_data.py</b> generates <b>data/reviews_week40.csv</b> (248 reviews in English, "
            "Tamil and Tanglish plus 3 dirty rows) and <b>reviews_week39.csv</b> (previous week)."),
          code("""
python scripts/make_sample_data.py
pytest -q          # 15 tests, offline, no API key needed
"""),
          p("The tests cover: CSV cleaning, the 500 limit, a 200+ row run, retry -> needs_review, report numbers "
            "matching the table, percentages summing to 100, Excel export with Tamil text, trend comparison, "
            "the email (sent once per week, reminder when nothing saved) and the Monday schedule."),

          h1("13. Step 11 - Stretch goals"),
          h2("Trend arrows vs last week"),
          p("<b>reviewlens/history.py</b> stores each <i>official</i> week on disk (enriched.csv, report.txt, meta.json). "
            "When a new week is analysed, the most recent earlier saved week is loaded automatically and compared: "
            "the Trend tab shows deltas and the report gets a 'VS LAST WEEK' section. Saving is a button, so visitors "
            "of a public app cannot overwrite the official history by accident."),
          h2("Weekly report by email every Monday"),
          p("<b>reviewlens/emailer.py</b> sends the latest saved report (CSV attached) over SMTP and remembers that the "
            "week was sent. <b>reviewlens/scheduler.py</b> runs in its own container and sleeps until Monday 09:00 "
            "(Asia/Kolkata), then sends. If nothing was saved that week, it sends a reminder instead. Add to .env:"),
          code("""
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=sender@gmail.com           # the SAME account that created the App Password
SMTP_PASSWORD=abcd efgh ijkl mnop    # 16-letter Google App Password, not the normal password
REPORT_RECIPIENTS=manager@example.com, owner@example.com
REPORT_DAY=monday
REPORT_TIME=09:00
REPORT_TIMEZONE=Asia/Kolkata
APP_URL=https://www.example.com/techstack/
"""),
          p("Create the App Password at <b>myaccount.google.com/apppasswords</b> (2-Step Verification must be on). "
            "Check the setup without waiting for Monday:"),
          code("""
python -m reviewlens.emailer --dry-run     # shows what would be sent
python -m reviewlens.emailer --test        # sends a [TEST] email now
"""),
          PageBreak()]

    # ------------------------------------------------------------------ docker + github
    s += [h1("14. Step 12 - Run it in Docker locally"),
          p("<b>Dockerfile</b>: python:3.12-slim, install requirements, run as a non-root user, health check, start "
            "Streamlit on port 8501. <b>docker-compose.yml</b> defines two services from the same image - "
            "<b>reviewlens</b> (the web app) and <b>scheduler</b> (Monday email) - sharing a <b>history</b> volume, "
            "and reads secrets from .env."),
          code("""
docker compose up -d --build        # http://localhost:8501
docker compose ps                   # both services should be Up
docker compose logs scheduler       # shows the next weekly email time
docker compose down                 # stop
"""),

          h1("15. Step 13 - Put it on GitHub"),
          code("""
git add -A
git commit -m "ReviewLens: LangChain customer feedback analyzer"
gh repo create reviewlens --public --source . --remote origin --push
# later changes:
git add -A && git commit -m "Describe the change" && git push
"""),
          p("Before every push, check that <b>.env</b> is not listed by <b>git status</b>. Sample data can also be "
            "attached to a GitHub release: <b>gh release create v1.0 data/reviews_week40.csv</b>."),

          h1("16. Step 14 - Deploy live with HTTPS"),
          h2("a) Prepare the server (Ubuntu VPS)"),
          code("""
ssh-keygen -t ed25519 -f ~/.ssh/reviewlens_vps      # add the .pub key in the VPS panel
ssh -i ~/.ssh/reviewlens_vps root@<server-ip>
apt-get update && apt-get install -y docker.io docker-compose-v2 git
systemctl enable --now docker
"""),
          h2("b) Point the domain at the server"),
          p("In your DNS panel add an <b>A record</b>: name <b>www</b> -> <b>&lt;server-ip&gt;</b> (replace an existing "
            "www CNAME). Check with <b>nslookup www.example.com</b>."),
          h2("c) Clone, configure and start"),
          code("""
git clone https://github.com/<you>/reviewlens.git /opt/reviewlens
cd /opt/reviewlens
nano .env            # OPENAI_API_KEY, SMTP_*, REPORT_RECIPIENTS, plus:
                     # APP_DOMAIN=www.example.com   APP_PATH=techstack
chmod 600 .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
"""),
          p("<b>docker-compose.prod.yml</b> adds <b>Caddy</b>, which gets and renews the Let's Encrypt certificate by "
            "itself, serves the app at <b>https://www.example.com/techstack/</b>, redirects everything else there "
            "and hides port 8501 from the internet. Streamlit is told its sub-path with "
            "STREAMLIT_SERVER_BASE_URL_PATH."),
          h2("d) Update after a change"),
          code("""
ssh -i ~/.ssh/reviewlens_vps root@<server-ip> "cd /opt/reviewlens && git pull && \\
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build"
"""),
          PageBreak()]

    # ------------------------------------------------------------------ checklist, ops, troubleshooting
    s += [h1("17. Step 15 - Deploy on Hostinger VPS (hPanel)"),
          p("This is exactly how the live app was deployed. Hostinger <b>shared / web hosting cannot run Python "
            "apps</b> - use a <b>Hostinger VPS</b> (KVM plan) with an Ubuntu template."),
          table([["#", "Where", "What to do"],
                 ["1", "hPanel -> VPS", "Pick the VPS (Ubuntu 24.04 or newer). Note its <b>IP address</b>. Recommended: "
                  "create a <b>snapshot</b> first (Snapshots &amp; backups) so you can roll back."],
                 ["2", "Laptop + hPanel -> VPS -> Settings -> SSH keys", "Create a key with ssh-keygen (below) and paste "
                  "the <b>.pub</b> line into hPanel. Test: ssh -i key root@&lt;VPS-IP&gt;."],
                 ["3", "hPanel -> Domains -> DNS", "Add an <b>A record</b> www -> &lt;VPS-IP&gt; (TTL 300). Delete an existing "
                  "www <b>CNAME</b> first. Check with nslookup."],
                 ["4", "SSH session", "Install Docker: apt-get install docker.io docker-compose-v2 git."],
                 ["5", "SSH session", "git clone to /opt/reviewlens, cp .env.example .env, fill it in, chmod 600 .env."],
                 ["6", "SSH session", "Start with the production compose file - Caddy gets the HTTPS certificate."],
                 ["7", "SSH session", "Optional: send a [TEST] email; check the scheduler log."],
                 ["8", "Laptop", "After every git push: git pull + rebuild over SSH (one command)."]],
                [8, 52, 110]),
          h2("Step 2 - SSH key (Windows PowerShell on your laptop)"),
          code(r"""
ssh-keygen -t ed25519 -f $HOME\.ssh\reviewlens_vps     # Enter = no passphrase
Get-Content $HOME\.ssh\reviewlens_vps.pub              # copy into hPanel -> SSH keys
ssh -i $HOME\.ssh\reviewlens_vps root@<VPS-IP>         # test the login
"""),
          h2("Steps 4-6 - On the VPS"),
          code("""
apt-get update && apt-get install -y docker.io docker-compose-v2 git
systemctl enable --now docker
git clone https://github.com/<you>/reviewlens.git /opt/reviewlens
cd /opt/reviewlens && cp .env.example .env && nano .env && chmod 600 .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
"""),
          table([["Setting in the server .env", "Example / note"],
                 ["OPENAI_API_KEY", "sk-...  (required)"],
                 ["APP_DOMAIN", "www.yourdomain.com - must match the DNS A record"],
                 ["APP_PATH", "techstack -> app at https://www.yourdomain.com/techstack/"],
                 ["MAX_REVIEWS", "500 - cost guard per upload"],
                 ["APP_PASSWORD", "empty = public; set a value to require a login"],
                 ["SMTP_HOST / PORT / USER / PASSWORD, REPORT_RECIPIENTS", "Optional Monday email (Gmail App Password)"],
                 ["APP_URL", "https://www.yourdomain.com/techstack/ - link in the email"]],
                [75, 95]),
          KeepTogether([h2("Steps 7-8 - Test the email and update later"), code(r"""
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec scheduler \
  python -m reviewlens.emailer --test
# from the laptop, after git push:
ssh -i $HOME\.ssh\reviewlens_vps root@<VPS-IP> "cd /opt/reviewlens && git pull && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build"
""")]),
          table([["Problem on Hostinger", "Fix"],
                 ["Certificate not issued", "DNS A record not on the VPS yet, or ports 80/443 used by another service"],
                 ["Hostinger 'Parked domain' page shows", "www is still a CNAME to the parked root - replace it with an A record"],
                 ["Permission denied (publickey)", "Add the .pub key in hPanel -> VPS -> SSH keys and use ssh -i"],
                 ["Docker Manager in hPanel does not list the app", "Normal: it only covers Hostinger's Docker OS template; "
                  "manage the app with docker compose over SSH"]],
                [62, 108]),
          PageBreak()]

    s += [h1("18. Done checklist"),
          table([["Requirement", "How it is met", "Status"],
                 ["Processes a 200+ row CSV without crashing", "Batched, concurrent, per-review error isolation (248 rows in about 1 minute)", "Done"],
                 ["All 6 fields, only allowed values", "Pydantic Literal enums + re-validation + retry", "Done"],
                 ["Tamil / Tanglish -> correct English summary", "Prompt rules + Tanglish glossary; verified with OpenAI", "Done"],
                 ["Report numbers match the table", "Calculated in pandas; covered by a test", "Done"],
                 ["HIGH urgency filter; CSV opens in Excel", "Toggle in Reviews tab; UTF-8 BOM export", "Done"],
                 ["API key from .env, never hard-coded", "python-dotenv; .env in .gitignore", "Done"],
                 ["Stretch: trend arrows", "Saved weeks + automatic comparison", "Done"],
                 ["Stretch: replies in the review's language", "Sidebar toggle; verified with OpenAI", "Done"],
                 ["Stretch: Monday email", "scheduler container + Gmail SMTP", "Done"]],
                [55, 95, 20]),

          h1("19. Weekly routine for the manager"),
          *bullets(["Export the week's reviews to a CSV (review_id, date, platform, rating, review_text).",
                    "Open the app, upload, click <b>Analyse</b>; read the dashboard and filter <b>HIGH urgency only</b>.",
                    "Reply to urgent reviews using the suggested replies; download the enriched CSV for the support team.",
                    "Click <b>Save as this week's official report</b> - next week shows trend arrows, and the report "
                    "is emailed on Monday at 09:00."]),

          h1("20. Troubleshooting"),
          table([["Problem", "Fix"],
                 ["'OPENAI_API_KEY is not set'", "Add the key to .env (locally) or the server's .env, then restart."],
                 ["Analysis failed / rate limit", "Lower 'Parallel requests' in the sidebar; check your OpenAI budget."],
                 ["'limit is 500 per upload'", "Split the file (e.g. one per week) or raise MAX_REVIEWS."],
                 ["Email: 535 Username and Password not accepted", "SMTP_USER must be the same Gmail account that created the "
                  "App Password, and SMTP_PASSWORD must be the App Password, not the normal password."],
                 ["Email not received", "Check Spam; run 'python -m reviewlens.emailer --test'; read 'docker compose logs scheduler'."],
                 ["HTTPS certificate not issued", "The domain's A record must point at the server and ports 80/443 must be open."],
                 ["Page loads but stays blank behind a sub-path", "Set APP_PATH and recreate both containers so Streamlit "
                  "and Caddy use the same base path."]],
                [62, 108]),
          note("Security: keep the OpenAI key and Gmail App Password only in .env files (chmod 600 on the server). "
               "Use a separate Gmail account for sending and set a monthly OpenAI budget - a public app spends on your key."),
          PageBreak(),
          h1("21. Usage outputs (screenshots)"),
          p("Real output from the finished app (OpenAI gpt-4o-mini, sample week 40 compared with saved week 39). "
            "The same images are in <b>docs/screenshots/</b> in the repository."),
          ]
    for i, (name, title, caption) in enumerate(SCREENS, 1):
        block = [h2(f"{i}. {title}"), p(caption), screenshot(name, max_h=(150 if i == 1 else 195) * mm),
                 Spacer(1, 8)]
        s.append(KeepTogether(block))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=22 * mm, title="ReviewLens - Step-by-step build & deploy guide",
                            author="ReviewLens", subject="LangChain customer feedback analyzer")
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    return OUT


if __name__ == "__main__":
    print("wrote", build())
