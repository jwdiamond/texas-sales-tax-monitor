# Normalized monthly observed data schema

This directory is deliberately empty until live Comptroller XLSX schemas have been inspected and a parser has been validated. **Do not copy the September 2026 snapshot into a historical series.**

Required columns for `monthly.csv`:
- `series_id`: stable name, e.g. `state:naics:retail_trade` (avoid ambiguous abbreviations)
- `period`: `YYYY-MM`, the *economic or reporting period* consistently defined for each series
- `amount`: nonnegative USD dollars, unrounded when source permits
- `vintage_date`: date `YYYY-MM-DD` when that observation/revision became available

Multiple observations for one period are allowed only across different vintages. A future importer should preserve raw industry codes and distinguish `industry_receipts` from `local_allocations` in series identifiers and metadata. Month-end backtests must never use revisions published after the forecast cutoff.

**Release lag warning**: the baseline currently predicts the month following the calendar month of `--asof`, not the current not-yet-released collections month. Production forecasting requires a release calendar and explicit target metadata.
