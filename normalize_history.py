"""Normalize Texas Comptroller fiscal-year NAICS Excel sheets to monthly CSV.

Run from the texas-sales-tax-monitor repository:
    python normalize_history.py

Uses SOURCE URLs and fetch() from maintain.py. Does not modify index.html.
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook
from maintain import SOURCES, fetch

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "normalized" / "monthly.csv"
MONTHS = ["September", "October", "November", "December", "January", "February", "March", "April", "May", "June", "July", "August"]
MONTH_NUM = {month.lower(): index for index, month in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], start=1
)}

def parse_source(level: str, url: str) -> list[dict]:
    wb = load_workbook(io.BytesIO(fetch(url)), read_only=True, data_only=True)
    result: list[dict] = []
    seen = set()
    try:
        for ws in wb.worksheets:
            match = re.fullmatch(r"FY\s*(\d{4})", ws.title.strip(), flags=re.I)
            if not match:
                continue
            fiscal_year = int(match.group(1))
            rows = ws.iter_rows(values_only=True)
            next(rows, None)  # Title
            header = next(rows, None)
            if header is None:
                raise ValueError(f"{level}/{ws.title}: missing header")
            month_headings = [str(v).strip().lower() if v is not None else "" for v in header[1:13]]
            if month_headings != [m.lower() for m in MONTHS]:
                raise ValueError(f"{level}/{ws.title}: unexpected months: {month_headings!r}")
            for row in rows:
                name = str(row[0]).strip() if row and row[0] is not None else ""
                if not name or name.lower() in {"total", "grand total", "all industries"}:
                    continue
                values = list(row[1:13])
                if not any(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
                    continue
                for month, raw in zip(MONTHS, values):
                    if raw is None or raw == "":
                        continue  # Unreleased future month; do not fabricate zeros
                    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                        raise ValueError(f"{level}/{ws.title}/{name}/{month}: unexpected value {raw!r}")
                    month_number = MONTH_NUM[month.lower()]
                    calendar_year = fiscal_year - 1 if month_number >= 9 else fiscal_year
                    period = f"{calendar_year:04d}-{month_number:02d}"
                    key = (level, period, name)
                    if key in seen:
                        raise ValueError(f"Duplicate observation: {key}")
                    seen.add(key)
                    result.append({"period": period, "level": level, "name": name, "receipts": int(round(raw)), "group": ""})
    finally:
        wb.close()
    if not result:
        raise ValueError(f"{level}: no monthly records were extracted")
    return result


def main():
    observations = []
    for kind, level in (("industry", "industry"), ("retail", "retail")):
        records = parse_source(level, SOURCES[kind])
        observations.extend(records)
        periods = sorted({r["period"] for r in records})
        print(f"{level}: {len(records):,} rows; {periods[0]} through {periods[-1]}")
    observations.sort(key=lambda r: (r["period"], r["level"], r["name"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["period", "level", "name", "receipts", "group"])
        writer.writeheader()
        writer.writerows(observations)
    print(f"Saved {len(observations):,} observations to {OUT}")
    print("Note: 'retail' subsectors overlap with 'industry' Retail Trade; do not sum across levels.")

if __name__ == "__main__":
    main()
