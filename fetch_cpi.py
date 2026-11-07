"""Download monthly, unadjusted CPI-U and write deterministic observations.

BLS series CUUR0000SA0; FRED mirror CPIAUCNS. No API key required.
Use: python fetch_cpi.py
"""
import csv
import datetime as dt
import io
import math
import os
from pathlib import Path
import tempfile
import urllib.request
import time

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'inflation' / 'cpi_u.csv'
URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS'

def parse(text):
    rows = list(csv.DictReader(io.StringIO(text.lstrip('\ufeff'))))
    if not rows or not {'observation_date', 'CPIAUCNS'}.issubset(rows[0]):
        # FRED has also used DATE for the observation date in older exports.
        if not rows or not {'DATE', 'CPIAUCNS'}.issubset(rows[0]):
            raise ValueError('Unexpected CPI CSV schema')
        date_key = 'DATE'
    else:
        date_key = 'observation_date'
    out = {}
    for r in rows:
        date = dt.date.fromisoformat(r[date_key])
        if date.day != 1:
            raise ValueError('CPI date is not a monthly first-of-month date')
        v = r['CPIAUCNS'].strip()
        if v in ('', '.'):
            continue
        n = float(v)
        if not (math.isfinite(n) and 0 < n < 10000):
            raise ValueError('Invalid CPI observation')
        k = date.strftime('%Y-%m')
        if k in out:
            raise ValueError('Duplicate CPI month: '+k)
        out[k] = n
    if len(out) < 250 or max(out) < '2025-01':
        raise ValueError('CPI history unexpectedly sparse or stale')
    months = sorted(out)
    # The dashboard only needs modern history, but keep pre-2003 data for reproducibility.
    sio = io.StringIO(newline='')
    writer = csv.writer(sio, lineterminator='\n')
    writer.writerow(['period','cpi'])
    writer.writerows((m,format(out[m],'.3f')) for m in months)
    return sio.getvalue().encode('utf-8'), len(months), months[-1]


def main():
    req = urllib.request.Request(
        URL,
        headers={'User-Agent': 'TexasSalesTaxMonitor/1.0 public research'}
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = resp.read(5_000_001)
            break
        except (TimeoutError, OSError) as exc:
            if attempt == 2:
                raise
            print(f'CPI download attempt {attempt + 1} failed: {exc}')
            time.sleep(5 * (attempt + 1))

    if len(body) > 5_000_000:
        raise ValueError('CPI download exceeds maximum size')
    result, count, last = parse(body.decode('utf-8-sig'))
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    # Write only if bytes change, avoiding gratuitous Git commits.
    if OUTPUT.exists() and OUTPUT.read_bytes()==result:
        print(f'CPI unchanged: {count} months, latest {last}')
        return
    with tempfile.NamedTemporaryFile(dir=OUTPUT.parent,delete=False) as f:
        f.write(result); temp=Path(f.name)
    os.replace(temp, OUTPUT)
    print(f'CPI updated: {count} months; latest {last}; {OUTPUT}')

if __name__ == '__main__':
    main()
