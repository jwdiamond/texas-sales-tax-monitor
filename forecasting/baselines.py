"""Vintage-conscious baseline forecasts for *normalized observed* monthly tax series.

Input CSV must have: series_id, period (YYYY-MM), amount, vintage_date (YYYY-MM-DD).
Optional dimensions can be encoded in series_id (e.g. state:naics:23).
Rows for the same series and month may have multiple historical vintages.

Run: python -m forecasting.baselines --input normalized/monthly.csv --asof 2026-11-03
No results are generated when source observations do not exist.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

REQUIRED = {'series_id', 'period', 'amount', 'vintage_date'}


def month_shift(period: str, delta: int) -> str:
    y, m = map(int, period.split('-'))
    k = y * 12 + (m - 1) + delta
    return f'{k // 12:04d}-{k % 12 + 1:02d}'


def read_vintages(path: Path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError(f'Missing fields: {sorted(REQUIRED - set(reader.fieldnames or []))}')
        rows = []
        for i, r in enumerate(reader, 2):
            try:
                dt.date.fromisoformat(r['period'] + '-01')
                vintage = dt.date.fromisoformat(r['vintage_date'])
                amount = float(r['amount'])
                if not math.isfinite(amount) or amount < 0: raise ValueError('nonnegative finite amount required')
                if not r['series_id'].strip(): raise ValueError('empty series_id')
                rows.append((r['series_id'].strip(), r['period'], amount, vintage))
            except (ValueError, TypeError) as e:
                raise ValueError(f'Invalid row {i}: {e}') from e
    if not rows: raise ValueError('Input CSV contains no observations')
    return rows


def known_at(rows, cutoff: dt.date):
    """Only information published as of the specific forecast date."""
    latest = {}
    for series, period, amount, vintage in rows:
        if vintage > cutoff: continue
        key = series, period
        if key not in latest or vintage > latest[key][1]:
            latest[key] = (amount, vintage)
    out = defaultdict(dict)
    for (series, period), (amount, _) in latest.items():
        # Do not let a future-dated economic period enter an earlier forecast.
        if period <= cutoff.strftime('%Y-%m'):
            out[series][period] = amount
    return out


def forecast_one(history: dict[str, float], target: str):
    """One-step seasonal naive and a seasonal naive adjusted by recent YoY growth.

    Requires a previous-year value for the target. Growth-adjusted requires 3 paired
    months from both prior year and its previous year. No model selected yet.
    """
    last_year = month_shift(target, -12)
    if last_year not in history: return None
    previous = [month_shift(target, -i) for i in (1, 2, 3)]
    paired = [month_shift(m, -12) for m in previous]
    baseline = history[last_year]
    result = {'seasonal_naive': baseline}
    if all(x in history for x in previous + paired):
        denom = sum(history[x] for x in paired)
        if denom > 0:
            growth = sum(history[x] for x in previous) / denom - 1
            result['recent_yoy_adjusted'] = baseline * max(0.0, 1 + growth)
    return result


def backtest(rows, series, asof: dt.date, max_origins=24):
    """Rolling one-month-ahead forecasts, respecting historical release vintages.

    Uses calendar month-end as the forecast date. If a data point had not yet
    been published at that date, it is unavailable. Report errors only when
    the target has been observed by `asof`.
    """
    final = known_at(rows, asof).get(series, {})
    targets = sorted(p for p in final if p < asof.strftime('%Y-%m'))[-max_origins:]
    errors = defaultdict(list)
    for target in targets:
        first = dt.date.fromisoformat(target + '-01')
        cutoff = first - dt.timedelta(days=1)
        history = known_at(rows, cutoff).get(series, {})
        preds = forecast_one(history, target)
        if not preds: continue
        for model, prediction in preds.items():
            actual = final[target]
            errors[model].append({'target_period': target, 'forecast_asof': cutoff.isoformat(), 'forecast': round(prediction, 2), 'actual_final_asof': round(actual, 2), 'absolute_error': abs(prediction - actual)})
    metrics = {}
    for model, records in errors.items():
        metrics[model] = {'n':len(records),'mae':round(sum(r['absolute_error'] for r in records)/len(records),2)}
    return metrics


def run(path, asof, output):
    rows = read_vintages(path)
    historical = known_at(rows, asof)
    target = month_shift(asof.strftime('%Y-%m'), 1)  # explicit forward month forecast
    result = {'asof': asof.isoformat(), 'target_period': target, 'basis': 'observed normalized series; preliminary baselines', 'forecasts': [], 'note': 'Not production estimates. Target is next calendar month and depends on data publication lags.'}
    for series, hist in sorted(historical.items()):
        estimates = forecast_one(hist, target)
        if estimates:
            result['forecasts'].append({'series_id': series, 'models': {k:round(v,2) for k,v in estimates.items()}, 'backtest': backtest(rows,series,asof)})
    if not result['forecasts']:
        raise ValueError('Insufficient historical data for the selected target; refusing to publish empty forecasts')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--asof',type=dt.date.fromisoformat,default=dt.date.today())
    p.add_argument('--output',type=Path,default=Path('forecasts/latest.json'))
    a=p.parse_args()
    print(json.dumps({'generated_forecasts':len(run(a.input,a.asof,a.output)['forecasts'])}))
