"""Build a reproducible panel of monthly Texas city allocations.

Usage: python fetch_city_history.py --start-year 2023
Years missing in local/years are fetched; the current and previous year are
refreshed every run. --refresh-all re-fetches all years.
Official *municipal allocations* are not taxable sales or county government revenue.
"""
import argparse
import csv
import datetime as dt
import io
import os
from pathlib import Path
import tempfile

from fetch_local import FIELDS, download

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'local'
KEY = ('county', 'city', 'report_year', 'report_month', 'report_period_type')

def money(value):
    try:
        result = float(str(value).replace(',', '').replace('$', ''))
        if not -1e15 < result < 1e15:
            raise ValueError('outside range')
        return result
    except (ValueError, TypeError):
        raise ValueError(f'Invalid allocation amount: {value!r}')

def read_year(path, expected_year):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError(f'Unexpected field names in {path}')
        records = []
        seen = set()
        for line, row in enumerate(reader, 2):
            year = int(row['report_year'])
            month = int(row['report_month'])
            if year != expected_year or not 1 <= month <= 12:
                raise ValueError(f'{path}:{line} invalid reporting period')
            if not row['city'] or not row['county']:
                raise ValueError(f'{path}:{line} missing city/county')
            money(row['net_payment_this_period'])
            money(row['comparable_payment_prior_year'])
            key = tuple(row.get(k, '') for k in KEY)
            if key in seen:
                raise ValueError(f'{path}:{line} duplicate key {key}')
            seen.add(key)
            records.append({k: row.get(k, '') for k in FIELDS})
    if len(records) < 100:
        raise ValueError(f'{path} unexpectedly sparse: {len(records)} records')
    return records

def atomic_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                     dir=path.parent, delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        tmp = f.name
    os.replace(tmp, path)

def run(start_year, end_year, refresh_all=False):
    if not 2013 <= start_year <= end_year <= dt.date.today().year:
        raise ValueError('Invalid year range')
    years_dir = OUT / 'years'
    years_dir.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for year in range(start_year, end_year + 1):
        path = years_dir / f'{year}.csv'
        refresh = refresh_all or not path.exists() or year >= dt.date.today().year - 1
        if refresh:
            with tempfile.TemporaryDirectory() as tmp:
                downloaded = Path(tmp) / f'{year}.csv'
                download(year, str(downloaded))
                rows = read_year(downloaded, year)
                atomic_csv(path, rows)
        else:
            rows = read_year(path, year)
        all_rows.extend(rows)
        print(f'{year}: {len(rows):,} validated city allocations')
    # Rows are sorted so unchanged releases don't cause needless Git commits.
    all_rows.sort(key=lambda r: (int(r['report_year']), int(r['report_month']), r['county'], r['city'], r['report_period_type']))
    atomic_csv(OUT / 'city_allocations.csv', all_rows)
    print(f'Wrote {len(all_rows):,} allocations to {OUT / "city_allocations.csv"}')

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--start-year', type=int, default=2023)
    p.add_argument('--end-year', type=int, default=dt.date.today().year)
    p.add_argument('--refresh-all', action='store_true')
    args = p.parse_args()
    run(args.start_year, args.end_year, args.refresh_all)
