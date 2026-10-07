"""Mock big-win generator for the Big Wins feed.

Inserts a realistic fake win into Supabase every few seconds. Multipliers follow
a crash-game distribution (P(multiplier > x) ~ 0.97 / x), so x20 is common,
x500 is rare and x5000 almost never happens - which is what makes it feel live.

    py -3.11 mock_wins.py                 # one win every 2-7 seconds, until Ctrl+C
    py -3.11 mock_wins.py --backfill 40   # first add 40 wins spread over the last 6 hours
    py -3.11 mock_wins.py --once          # a single win, then exit

Also writes config.js for index.html from .env, so the page needs no editing.
"""
import argparse
import json
import os
import random
import string
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))

# Made-up brands on purpose: this is mock data and must not read as partner data.
BRANDS = {
    "Zambia": ["Savanna Bet", "Copperline"], "Kenya": ["Simba Play", "Rift Bet"],
    "Ghana": ["Gold Coast Bet", "Kente Games"], "Nigeria": ["Lagos Lucky", "Naija Spin"],
    "Tanzania": ["Kili Bet"], "Malawi": ["Lake Play"], "Uganda": ["Pearl Bet"],
    "Mozambique": ["Indico Jogos"], "Brazil": ["Rio Rush", "Samba Bet"],
    "Mexico": ["Azteca Play"], "Turkey": ["Bosphorus Bet"], "India": ["Monsoon Play"],
}
COUNTRY_WEIGHTS = {"Zambia": 14, "Kenya": 12, "Ghana": 10, "Nigeria": 12, "Tanzania": 9,
                   "Malawi": 6, "Uganda": 6, "Mozambique": 6, "Brazil": 9, "Mexico": 5,
                   "Turkey": 6, "India": 5}
# Roughly the live turnover mix: Navigator dominates.
GAME_WEIGHTS = {"Navigator": 70, "Chicken Runner": 6, "Swiminator": 5, "Fishinator": 4,
                "Punchinator": 4, "Rushinator": 3, "Quackinator": 3, "Dragon Run": 3,
                "Lucky Leap": 2}

MIN_MULT = 20.0      # a "big win" is at least x20 ...
MIN_WIN_EUR = 150.0  # ... or at least EUR 150 won
MAX_WIN_EUR = 25000.0  # games cap a single win; without it a EUR 250 bet at x10,000 pays 2.5m


def load_env():
    for path in (os.path.join(HERE, ".env"),
                 os.path.join(HERE, "..", "supabase-check", ".env")):
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
            return path
    return None


def write_config(url, key):
    """config.js for the page. Git-ignored like .env, though the key is public-safe."""
    with open(os.path.join(HERE, "config.js"), "w", encoding="utf-8") as fh:
        fh.write(f"window.BIG_WINS_CONFIG = {json.dumps({'url': url, 'key': key})};\n")


def pick(weights):
    return random.choices(list(weights), weights=list(weights.values()))[0]


def crash_multiplier():
    # Inverse-CDF of P(m > x) = 0.97 / x, floored at 1.00, capped like a real game.
    u = random.random()
    return min(max(1.0, 0.97 / max(u, 1e-9)), 10000.0)


def bet_eur():
    # Lognormal: median ~EUR 0.80, occasional EUR 20-100 high rollers.
    return round(min(max(random.lognormvariate(-0.2, 1.3), 0.10), 250.0), 2)


def masked_player():
    a = random.choice(string.ascii_lowercase) + random.choice(string.ascii_lowercase)
    return f"{a}***{random.randint(10, 99)}"


def big_win(at=None):
    """Draw spins until one qualifies as a big win - keeps the distribution honest."""
    while True:
        m, bet = crash_multiplier(), bet_eur()
        win = round(bet * m, 2)
        if (m >= MIN_MULT or win >= MIN_WIN_EUR) and win <= MAX_WIN_EUR:
            country = pick(COUNTRY_WEIGHTS)
            row = {"game": pick(GAME_WEIGHTS), "brand": random.choice(BRANDS[country]),
                   "country": country, "player": masked_player(),
                   "bet_eur": bet, "multiplier": round(m, 2), "win_eur": win}
            if at:
                row["created_at"] = at.isoformat()
            return row


def insert(rest, headers, rows):
    r = requests.post(rest, headers={**headers, "Prefer": "return=minimal"}, json=rows, timeout=15)
    if "42501" in r.text or r.status_code == 404:
        sys.exit("Table big_wins is missing or not granted - run setup.sql in the Supabase SQL editor.")
    if r.status_code >= 300:
        sys.exit(f"Insert failed ({r.status_code}): {r.text[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=0, help="add N past wins over the last 6 hours first")
    ap.add_argument("--once", action="store_true", help="insert one win and exit")
    ap.add_argument("--min-gap", type=float, default=2.0)
    ap.add_argument("--max-gap", type=float, default=7.0)
    args = ap.parse_args()

    if not load_env():
        sys.exit("No .env found - copy .env.example to .env and fill it in.")
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        sys.exit("SUPABASE_URL / SUPABASE_KEY missing in .env")
    write_config(url, key)

    rest = f"{url}/rest/v1/big_wins"
    headers = {"apikey": key, "Content-Type": "application/json"}

    if args.backfill:
        now = datetime.now(timezone.utc)
        times = sorted(now - timedelta(seconds=random.uniform(60, 6 * 3600))
                       for _ in range(args.backfill))
        insert(rest, headers, [big_win(t) for t in times])
        print(f"Backfilled {args.backfill} wins over the last 6 hours.")

    while True:
        row = big_win()
        insert(rest, headers, [row])
        print(f"{datetime.now():%H:%M:%S}  x{row['multiplier']:>8,.2f}  EUR {row['win_eur']:>9,.2f}"
              f"  {row['game']:<15} {row['country']}")
        if args.once:
            break
        time.sleep(random.uniform(args.min_gap, args.max_gap))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
