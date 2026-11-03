# Texas Sales Tax Monitor — v0.1 research prototype

## Open the dashboard
Open `index.html` in Chrome, Edge, or Safari. No server, package install, API key, or account is needed. The HTML includes a validated **September 2026** snapshot from the Comptroller's published NAICS industry and retail subsector tables. It is NOT a complete monthly historical database or automatically refreshing dashboard yet.

The dashboard includes:
- Monthly statewide NAICS industry receipts and YoY growth (September 2026)
- Retail subsector detail
- Approximate dollar contributions to YoY growth, reconstructed from rounded published growth rates
- Initial **nonofficial** industry groupings (consumer-facing, business/industrial, mixed, etc.)
- Sortable searchable tables, sector growth rankings, data source links and methodological caveats
- October 2026 cash sales tax figure, *clearly distinguished* from NAICS-account data

## Official source downloads
- Industry historical XLSX: https://comptroller.texas.gov/transparency/revenue/watch/naics/data/sales-tax-naics-historical.xlsx
- Retail historical XLSX: https://comptroller.texas.gov/transparency/revenue/watch/naics/data/retail-sector-historical.xlsx
- Industry current report: https://comptroller.texas.gov/transparency/revenue/watch/naics/naics-industry.php
- Retail current report: https://comptroller.texas.gov/transparency/revenue/watch/naics/naics-retail.php
- Local city-by-county allocations API: https://data.texas.gov/resource/53pa-m7sm.json
- Cash revenue series: https://comptroller.texas.gov/transparency/revenue/watch/all-funds/

## Data pipeline: local allocations
Requires Python 3.9+ and Internet access:

```bash
python fetch_local.py --year 2026 --output local_2026.csv
```

Output has city, county, local sales tax rate, monthly allocation, prior-year comparable, and YTD fields. County is a geographical *grouping of cities*, not automatically the county government's own sales tax revenue or a measure of total county taxable sales. Other local government allocation datasets need their own treatment.

## Refreshing the prototype snapshot
`build.py` creates `data.json` and `index.html` from the verified snapshot values embedded in the script. Execute `python build.py`. This does **not** scrape or ingest the historical XLSX files automatically; it is a reproducible snapshot build. The first production extension should ingest the XLSX files with sheet-format validation and historical vintage archiving.

## Forecasting architecture (not implemented yet)
The research dataset should ultimately store `source`, `period_type`, `date_of_economic_activity` (if available), `collection_period`, `publication_date`, `data_vintage`, `geography`, `naics`, `amount`, `basis`, `revision_status`, and `local_tax_rate`. Baseline: seasonal naïve forecast, then ridge/elastic-net and dynamic factor model using employment, earnings, CPI/PPI, oil/gas activity, construction and consumer spending. Evaluate by rolling-origin vintage-aware out-of-sample backtesting. Treat allocations and statewide remittances as separate targets.

## Caveats
- Data may be revised, including tax returns with late NAICS assignment.
- NAICS records represent industry of *remitting business*, not the identity or purpose of ultimate purchaser.
- The Sep 2026 retail trade industry total differs slightly from the retail-subsector total; this is preserved, not silently corrected.
- September 2026 NAICS receipts are **not** the same time series as October 2026 state Treasury cash receipts.
- Percentages are rounded in the source; derived prior-year dollar contributions are approximate.
- No city/county industry-level monthly tax revenue is claimed to be observed.
