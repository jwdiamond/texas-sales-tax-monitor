"""Pre-publication checks for Comptroller historical NAICS receipts.

Fails closed: a bad or truncated import must not replace the live dashboard.
The preexisting normalized/monthly.csv (if any) is checked with Git at HEAD.
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import pathlib
import re
import subprocess
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent
PATH = ROOT / "normalized" / "monthly.csv"
EXPECTED = {"period", "level", "name", "receipts"}


def load_rows(text):
    reader = csv.DictReader(text.splitlines())
    if not EXPECTED.issubset(reader.fieldnames or []):
        raise ValueError(f"Missing required CSV columns: {EXPECTED - set(reader.fieldnames or [])}")
    rows = list(reader)
    if not rows:
        raise ValueError("Monthly history is empty")
    keys = set()
    for row in rows:
        period = row["period"]
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
            raise ValueError(f"Invalid period: {period!r}")
        if row["level"] not in {"industry", "retail"} or not row["name"].strip():
            raise ValueError(f"Invalid industry/retail observation: {row!r}")
        key = (period, row["level"], row["name"])
        if key in keys:
            raise ValueError(f"Duplicate observation: {key}")
        keys.add(key)
        receipt = float(row["receipts"])
        if not math.isfinite(receipt):
            raise ValueError(f"Non-finite receipts for {key}")
        # Negative receipts ARE permitted: refunds or administrative adjustments.
    return rows


def main():
    rows = load_rows(PATH.read_text(encoding="utf-8-sig"))
    counts = Counter(r["level"] for r in rows)
    periods = sorted({r["period"] for r in rows})
    if counts["industry"] < 4000 or counts["retail"] < 3000 or len(periods) < 250:
        raise ValueError(f"Suspiciously short dataset: {counts}, {len(periods)} months")
    if periods[0] > "2005-01":
        raise ValueError(f"Unexpectedly late historical start: {periods[0]}")
    if periods[-1] > dt.datetime.now(dt.timezone.utc).strftime("%Y-%m"):
        raise ValueError(f"Unexpected future period: {periods[-1]}")

    previous = subprocess.run(
        ["git", "show", "HEAD:normalized/monthly.csv"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if previous.returncode == 0:
        old = load_rows(previous.stdout)
        old_periods = {r["period"] for r in old}
        new_periods = set(periods)
        if not old_periods.issubset(new_periods):
            raise ValueError(f"Previously published months missing: {sorted(old_periods-new_periods)[:10]}")
        if len(rows) < len(old) * 0.98:
            raise ValueError(f"Unexplained drop in observations: {len(old)} -> {len(rows)}")
    print(f"Validated {len(rows):,} rows; {counts['industry']:,} industry; "
          f"{counts['retail']:,} retail; {periods[0]} through {periods[-1]}")


if __name__ == "__main__":
    main()
