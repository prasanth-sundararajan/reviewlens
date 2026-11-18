"""Generate realistic synthetic review CSVs for demos and tests.

python scripts/make_sample_data.py
-> data/reviews_week40.csv (248 rows + a few dirty rows), data/reviews_week39.csv
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

# (text, rating, preferred platforms)
TEMPLATES = [
    # --- praise (English)
    ("Biryani was amazing, packing also neat. Will order again!", 5, ["Zomato", "Swiggy"]),
    ("Best chicken biryani in the area, perfectly spiced and hot.", 5, ["Google", "Zomato"]),
    ("Great taste and generous portion. Loved the mutton chukka.", 5, ["Zomato", "Google"]),
    ("Staff were very friendly and the service was quick.", 5, ["Google"]),
    ("Neat packaging, nothing spilled, food still warm. Good job.", 4, ["Swiggy", "Amazon"]),
    ("Good food at a fair price. Parotta and salna were excellent.", 4, ["Google", "Swiggy"]),
    ("Delivered 10 minutes early and the rider was polite.", 5, ["Swiggy"]),
    ("The ready-to-eat biryani kit tastes great, easy to cook.", 4, ["Amazon"]),
    ("Nice ambience, tasty food, will come again with family.", 5, ["Google"]),
    # --- praise (Tanglish / Tamil)
    ("Biryani semma taste, vera level! Packing um nalla irundhuchu.", 5, ["Zomato", "Swiggy"]),
    ("Saapadu romba nalla irundhuchu, staff um friendly ah pesunanga.", 5, ["Google"]),
    ("பிரியாணி மிகவும் சுவையாக இருந்தது. பேக்கிங் அருமை.", 5, ["Zomato", "Google"]),
    ("சாப்பாடு சூப்பர், விலையும் நியாயமாக இருந்தது.", 4, ["Google"]),
    # --- neutral
    ("Food was okay, nothing special. Delivery on time.", 3, ["Swiggy", "Zomato"]),
    ("Average taste, portion could be a bit bigger.", 3, ["Zomato", "Google"]),
    ("Saapadu ok dhaan, aana konjam oily ah irundhuchu.", 3, ["Google", "Swiggy"]),
    ("Decent place. App ordering was a bit confusing but worked.", 3, ["Google"]),
    # --- delivery complaints
    ("Ordered at 8pm, came at 9:10. Food fully cold. Very bad.", 1, ["Swiggy"]),
    ("Delivery took 75 minutes on Friday night, biryani was cold.", 2, ["Swiggy", "Zomato"]),
    ("Order late ah vandhuchu, 9:30 ku dhaan vandhuchu. Food suda illa.", 1, ["Swiggy"]),
    ("Wrong order delivered! I ordered veg biryani and got chicken. I am vegetarian.", 1, ["Zomato", "Swiggy"]),
    ("Missing item - raita and gulab jamun were not in the bag. Need refund.", 1, ["Swiggy", "Zomato"]),
    ("டெலிவரி ரொம்ப தாமதம், உணவு ஆறிப்போச்சு.", 2, ["Swiggy"]),
    # --- price complaints
    ("Saapadu nalla irundhuchu but bill la extra charge pottanga", 2, ["Google"]),
    ("Service charge added without telling us. Rs 120 extra on the bill.", 2, ["Google"]),
    ("Prices increased again, biryani now costs too much for the portion.", 2, ["Zomato", "Google"]),
    ("I was overcharged by Rs 200 and the cashier refused to refund. Fraud.", 1, ["Google"]),
    ("பில்லில் கூடுதல் கட்டணம் போட்டாங்க, சொல்லவே இல்லை.", 2, ["Google"]),
    # --- food quality complaints
    ("Found a hair in my biryani. Disgusting.", 1, ["Zomato", "Google"]),
    ("Chicken was stale and smelled bad. My son vomited after eating.", 1, ["Zomato", "Swiggy"]),
    ("Portion size is very small for the price.", 2, ["Zomato", "Swiggy", "Google"]),
    ("Too much salt in the gravy, could not eat it.", 2, ["Swiggy", "Google"]),
    ("Biryani kettu pochu, smell vandhuchu. Saapta aprom vayiru vali.", 1, ["Zomato"]),
    # --- staff complaints
    ("Waiter was rude and ignored us for 20 minutes.", 1, ["Google"]),
    ("Manager kovama pesunanga when we asked for water. Very rude staff.", 1, ["Google"]),
    ("Delivery rider shouted at me over the phone. Unacceptable behaviour.", 1, ["Swiggy"]),
    # --- packaging complaints
    ("Gravy leaked all over the bag, container lid was not sealed.", 2, ["Swiggy", "Zomato"]),
    ("Box was crushed and rice spilled everywhere.", 2, ["Amazon", "Swiggy"]),
    # --- app complaints
    ("Coupon not applied at checkout and payment failed twice.", 2, ["Google", "Amazon"]),
    ("App crashed while paying via UPI, money debited but no order.", 1, ["Google"]),
]

# relative weights per template index -> roughly 60% positive, 15% neutral, 25% negative
WEIGHTS = [9, 7, 6, 5, 5, 5, 3, 3, 4, 6, 5, 4, 3, 4, 4, 3, 2,
           6, 4, 4, 2, 2, 2, 3, 2, 2, 1, 1, 1, 1, 2, 2, 1, 1, 1, 1, 2, 1, 1, 1]
assert len(WEIGHTS) == len(TEMPLATES)


def make_week(start: date, n: int, prefix_start: int, seed: int) -> list[list]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        text, rating, platforms = rng.choices(TEMPLATES, weights=WEIGHTS)[0]
        d = start + timedelta(days=rng.randint(0, 6))
        rows.append([f"R-{prefix_start + i}", d.isoformat(), rng.choice(platforms), rating, text])
    return rows


def write(path: Path, rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["review_id", "date", "platform", "rating", "review_text"])
        writer.writerows(rows)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "data"
    week40 = make_week(date(2026, 9, 29), 248, 1041, seed=40)
    # a few dirty rows the validator should clean up
    week40 += [["R-9001", "2026-10-02", "Google", 4, ""], ["R-9002", "2026-10-03", "Zomato", 3, "   "], week40[0]]
    write(root / "reviews_week40.csv", week40)
    write(root / "reviews_week39.csv", make_week(date(2026, 9, 22), 215, 801, seed=39))
    print("wrote", root / "reviews_week40.csv", "and reviews_week39.csv")


if __name__ == "__main__":
    main()
