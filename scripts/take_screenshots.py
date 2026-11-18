"""Capture documentation screenshots of a running ReviewLens app into docs/screenshots/.

    pip install playwright && python -m playwright install chromium
    docker compose up -d            # app on http://localhost:8501 with a real LLM key
    python scripts/take_screenshots.py [--url http://localhost:8501]

For the Trend screenshot, save an earlier week (e.g. reviews_week39.csv) as the official
report in the app first. Each run analyses the sample files with the configured LLM.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
WEEK40 = ROOT / "data" / "reviews_week40.csv"

MIXED_LANGUAGE_CSV = """review_id,date,platform,rating,review_text
T-1,2026-10-03,Swiggy,2,"டெலிவரி ரொம்ப தாமதம், உணவு ஆறிப்போச்சு."
T-2,2026-10-03,Zomato,5,"பிரியாணி மிகவும் சுவையாக இருந்தது. பேக்கிங் அருமை."
T-3,2026-10-04,Google,2,"Saapadu nalla irundhuchu but bill la extra charge pottanga"
T-4,2026-10-04,Swiggy,1,"Order late ah vandhuchu, 9:30 ku dhaan vandhuchu. Food suda illa."
T-5,2026-10-05,Zomato,1,"Ordered at 8pm, came at 9:10. Food fully cold. Very bad."
"""


def trim_bottom(path: Path, margin: int = 24, from_x: int = 8) -> None:
    """Cut the empty white area below the content (measured from column ``from_x``, e.g. right of a sidebar)."""
    img = Image.open(path).convert("RGB")
    inner = img.crop((from_x, 0, img.width - 8, img.height))  # ignore borders / sidebar
    bg = Image.new("RGB", inner.size, inner.getpixel((inner.width // 2, inner.height - 2)))
    box = ImageChops.difference(inner, bg).point(lambda v: 255 if v > 12 else 0).getbbox()
    if box:
        img.crop((0, 0, img.width, min(img.height, box[3] + margin))).save(path, optimize=True)


def shot(page: Page, name: str, locator: str = "[data-testid=stMain]", from_kpis: bool = False) -> None:
    """Screenshot ``locator``; with ``from_kpis`` start at the KPI row (skips the repeated upload header)."""
    page.wait_for_timeout(1200)
    path = OUT / f"{name}.png"
    target = page.locator(locator).locator("visible=true").first
    target.screenshot(path=str(path))
    if from_kpis:
        top = page.locator("[data-testid=stMetric]").first.bounding_box()["y"] - target.bounding_box()["y"] - 16
        img = Image.open(path)
        img.crop((0, max(0, int(top)), img.width, img.height)).save(path)
    trim_bottom(path, from_x=400 if "stAppViewContainer" in locator else 8)
    print("saved", name)


def open_app(page: Page, url: str) -> None:
    page.goto(url)
    page.get_by_text("Reviews CSV").first.wait_for(timeout=60_000)


def upload(page: Page, path: Path) -> None:
    page.locator("[data-testid=stMain] input[type=file]").first.set_input_files(str(path))
    page.get_by_text("valid reviews loaded").or_(page.get_by_text("CSV problem")).first.wait_for(timeout=60_000)


def analyse(page: Page) -> None:
    page.get_by_role("button", name="Analyse").click()
    page.get_by_role("tab", name="Weekly report").wait_for(timeout=300_000)
    page.get_by_text("WEEKLY FEEDBACK REPORT").first.wait_for(state="attached", timeout=300_000)


def tab(page: Page, name: str) -> None:
    t = page.get_by_role("tab", name=name)
    t.click()
    page.wait_for_function("el => el.getAttribute('aria-selected') === 'true'", arg=t.element_handle())
    page.wait_for_timeout(1500)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8501")
    parser.add_argument("--only", choices=["main", "extra"], help="main = screens 1-6, extra = 7-8")
    args = parser.parse_args()
    url = args.url
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 2400}, device_scale_factor=1,
                                  color_scheme="light")

        if args.only != "extra":
            run_main(ctx, url)
        if args.only != "main":
            run_extra(ctx, url)
        browser.close()


def run_main(ctx, url: str) -> None:
    if True:
        # 1. Start page + 2. validation
        page = ctx.new_page()
        open_app(page, url)
        shot(page, "01_start_page", "[data-testid=stAppViewContainer]")
        upload(page, WEEK40)
        shot(page, "02_upload_validation", "[data-testid=stAppViewContainer]")

        # 3-7. Analysis results
        analyse(page)
        tab(page, "Dashboard")
        shot(page, "03_dashboard", from_kpis=True)
        tab(page, "Reviews")
        page.get_by_text("HIGH urgency only").click()
        page.wait_for_timeout(2500)
        tab(page, "Reviews")  # toggling re-runs the script, which resets the selected tab
        page.get_by_text("Showing").locator("visible=true").first.wait_for()
        shot(page, "04_high_urgency_reviews", from_kpis=True)
        tab(page, "Weekly report")
        shot(page, "05_weekly_report", from_kpis=True)
        tab(page, "Trend")
        shot(page, "06_trend_vs_last_week", from_kpis=True)
        page.close()


def run_extra(ctx, url: str) -> None:
    if True:
        # 7. Replies in the review's own language
        page = ctx.new_page()
        open_app(page, url)
        page.get_by_text("Same as review").click()
        with tempfile.TemporaryDirectory() as tmp:
            mixed = Path(tmp) / "mixed_language_reviews.csv"
            mixed.write_text(MIXED_LANGUAGE_CSV, encoding="utf-8")
            upload(page, mixed)
            analyse(page)
        tab(page, "Reviews")
        shot(page, "07_same_language_replies", "[data-testid=stDataFrame]")
        page.close()

        # 9. 500-review limit
        page = ctx.new_page()
        open_app(page, url)
        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / "too_many_reviews.csv"
            rows = "\n".join(f"R-{i},2026-10-01,Google,5,Good food {i}" for i in range(620))
            big.write_text("review_id,date,platform,rating,review_text\n" + rows, encoding="utf-8")
            upload(page, big)
        shot(page, "08_review_limit", "[data-testid=stAppViewContainer]")


if __name__ == "__main__":
    main()
