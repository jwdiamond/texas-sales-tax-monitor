# Texas Sales Tax Monitor — City History Upgrade

This upgrade uses **official municipal sales tax allocations**, not city taxable sales, county tax revenue, or countywide taxable sales.

## Apply in VS Code (PowerShell)

Copy these files into the root of your existing `texas-sales-tax-monitor` repository:
- `fetch_city_history.py` (new)
- `patch_city_dashboard.py` (one-time update to your existing `index.html`)
- `.github/workflows/update-dashboard.yml` (replace existing workflow with the same name)

Keep the existing `fetch_local.py`, `normalize_history.py`, `validate_history.py`, `index.html`, and `normalized/monthly.csv`.

In a **new terminal** opened in the Texas repository:

```powershell
python fetch_city_history.py --start-year 2023
python patch_city_dashboard.py
python -m http.server 8001
```

Open http://localhost:8001. The city explorer should automatically load the merged file; below it, a new city comparison chart should let you compare Houston, Dallas, or other cities. It defaults to the latest available allocation month. The old manual file input still works, but **the comparison chart is based on the automatically loaded historical file**.

The importer normally refreshes the current and prior year and reuses older validated local year files. To refetch all years, run `python fetch_city_history.py --start-year 2023 --refresh-all`. Earlier records back to 2013 can be added later by setting `--start-year 2013`; this increases file size and runtime.

The patch writes `index.html.before-city-upgrade` as a backup, and refuses to apply more than once. It inserts an independent city-history module inside the existing JavaScript closure rather than replacing your statewide analytics.

Before publication, check that the local Explorer and historical chart render correctly, and review the Git diff:

```powershell
git status
git diff --stat
git diff -- index.html
```

Avoid adding the backup file or any unrelated project files. Publish:

```powershell
git add index.html fetch_city_history.py patch_city_dashboard.py .github/workflows/update-dashboard.yml local/city_allocations.csv local/years
git commit -m "Add automated city sales tax history and comparisons"
git push origin main
```

Then use **Actions → Update and publish Texas Sales Tax Monitor → Run workflow** and confirm both jobs are green. GitHub Pages Source should remain **GitHub Actions**.

The workflow re-downloads the current and previous years, validates all city allocation rows, combines the published CSV and deploys it. A failure stops the Pages build. Pushing a changed CSV from an Actions job does not cause a recursive build.

### Data cautions

- The chart uses `report_year` and `report_month`: **allocation/payment month**, not transaction month.
- Rate changes, reallocations, refunds and audit adjustments can drive reported changes.
- Counties in the Explorer aggregate allocations for listed cities, **not** county taxable sales or county government revenue.
- City comparison names use both county and city. Municipal boundaries can cross counties; avoid interpreting county-assigned city records as the city's complete revenue without confirming the Comptroller's geographic conventions.
- The dashboard's historical statewide fiscal-year series remains separate from city allocation history.
- Forecasting requires release-date vintages, robust seasonal benchmarks, and out-of-sample testing; this upgrade displays observations only.
