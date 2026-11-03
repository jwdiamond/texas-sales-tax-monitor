# Separate GitHub Pages deployment — Texas Sales Tax Monitor

## 1. Create the separate repo
Create a GitHub repository named `texas-sales-tax-monitor`. Choose **Public** for easiest GitHub Pages publishing. You can make the initial repo private and enable public Pages later if supported by your account.

Upload/extract **all files from this package at the repository root**, preserving `.github/workflows/` (the leading dot matters). Better: clone locally and push the extracted folder with git to preserve hidden files.

```bash
git init -b main
git add .
git commit -m "Initialize standalone Texas Sales Tax Monitor"
git remote add origin https://github.com/YOUR_USERNAME/texas-sales-tax-monitor.git
git push -u origin main
```

If you created the GitHub repository with a README, clone the repository first and copy these files in, instead of attempting the above push against an unrelated initial commit.

## 2. Turn on Pages
GitHub repository → Settings → Pages → Build and deployment → Deploy from a branch → `main`, `/ (root)` → Save.

After deployment, your URL should be `https://YOUR_USERNAME.github.io/texas-sales-tax-monitor/` (replace YOUR_USERNAME). The published home page currently shows the **September 2026 verified prototype**, not a live time series.

## 3. Enable daily maintenance
Repository → Settings → Actions → General → Workflow permissions → Read and write permissions → Save.

Repository → Actions → Texas Sales Tax Data Maintenance → Run workflow; enable `include_local` if wanted.

**Important**: the updater stores raw validated source files and checks them for changes. It does not yet parse them into the historical dashboard, and does not publish new charts. Watch the Actions log: if the Comptroller download URLs or workbook format change, validation fails and no guessed data are introduced.

## 4. Forecasting
`python -m unittest discover -s tests -v` runs without external dependencies. The `Validate forecasting code` workflow also runs tests on commits.

Once `normalized/monthly.csv` contains real time-vintaged observations, run:

```bash
python -m forecasting.baselines --input normalized/monthly.csv --asof 2026-11-03 --output forecasts/latest.json
```

The forecast task is *not* scheduled yet because verified normalized histories do not yet exist. The module implements (i) seasonal naive and (ii) recent YoY-adjusted benchmarks with rolling evaluation on the versions available at each historical cutoff. Research models and publication-quality prediction intervals come after source normalization and adequate historical validation.

## 5. First milestones
1. Run GitHub Actions source downloads successfully, inspect both Excel workbook column layouts and choose stable normalized column mapping.
2. Build tested normalizer to generate `normalized/monthly.csv`, including true vintage dates for new observations (past data vintage dates may be unknown; do not invent them).
3. Replace the hard-coded prototype snapshot with validated multi-month charts and publication date badges.
4. Produce and backtest forecast baselines, then integrate external leading indicators and publish forecasts with clear confidence/limitations.

## Important source distinction
NAICS taxpayer receipts, Treasury cash collections, municipal allocations and quarterly taxable sales are different sources and accounting concepts. They must not be silently merged into one series or compared as if identical.
