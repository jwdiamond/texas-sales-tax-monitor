# Texas Sales Tax Monitor — Automated Maintenance

## What this automation does now
- Runs every day in GitHub Actions (and on demand).
- Downloads **official historical XLSX files** for statewide NAICS industries and retail subsectors.
- Validates each file as a nonempty XLSX workbook before storing it.
- Records SHA-256 checksums, observed workbook sheets, and UTC check time.
- Keeps changed files in `source_data/archive/` (date+hash) to allow research-vintage comparisons.
- Updates `source_data/latest/` and commits validated data to GitHub.
- On Sunday (or manual request), retrieves current-year city-level allocation records from the Texas Open Data API; validates fields and row count.
- Opens a GitHub issue if an update fails; preserves previous validated files.

## What it does *not* do yet
- It does **not** parse the two Excel workbooks into monthly normalized NAICS observations. Their live field structure needs validation before safely mapping columns. Therefore the dashboard's existing embedded September 2026 snapshot **does not automatically advance**, even when new source XLSX files are fetched.
- It does **not** currently publish to GitHub Pages; configure Pages from the repository separately. A future rendering step must normalize source data then build the current interactive historical view from them.
- It does not run an LLM, forecast sales tax, or generate economic commentary yet. These are a later analyst-agent layer, contingent on reliable underlying observations.

## Deployment
1. Create a new GitHub repository, for example `texas-sales-tax-monitor`, and copy **the contents of this folder** to its root (including `.github/workflows/maintain.yml`).
2. In repository Settings → Actions → General, allow GitHub Actions to create and approve pull requests if you later choose PR review; Actions must have read/write workflow permission for the current commit-based updater.
3. Run Actions → Texas Sales Tax Data Maintenance → Run workflow. Use `include_local=true` to fetch city allocations immediately.
4. Review the `source_data/manifest.json` and `source_data/status.json` files. If a check fails, review the generated issue and workflow logs.
5. For a static public page, Settings → Pages → Deploy from branch, `main`, root `/`. The dashboard is currently `index.html`; its *snapshot data* will remain unchanged until a validated parsing/render step is added.

## Research safety and next steps
- The Comptroller explicitly warns NAICS receipt data are revised, and are not the same as Treasury cash deposits; retain these as distinct series.
- Local municipal allocations cannot be relabeled county taxable sales; the county field is a geographical grouping.
- When ingesting Excel, validate each expected column, month, industry, and summation checks. Refuse to publish on schema drift.
- After normalized monthly data are working, implement a daily automatic `index.html` render with a displayed `last_updated` date, and only then connect an AI narrative generator and forecast-evaluation agent.
- Github Actions scheduled jobs can be delayed. Use time-stamped release checks rather than assuming a fixed Comptroller publication hour.

## Source URLs
- https://comptroller.texas.gov/transparency/revenue/watch/naics/
- https://comptroller.texas.gov/transparency/revenue/watch/naics/data/sales-tax-naics-historical.xlsx
- https://comptroller.texas.gov/transparency/revenue/watch/naics/data/retail-sector-historical.xlsx
- https://data.texas.gov/resource/53pa-m7sm.json
