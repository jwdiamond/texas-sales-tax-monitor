"""Add CPI download and deployment to existing GitHub Actions, without rewriting other steps."""
from pathlib import Path
import shutil
import datetime as dt

p=Path.cwd()/'.github/workflows/update-dashboard.yml'
if not p.exists():raise SystemExit('Workflow not found; run from repository root')
s=p.read_text(encoding='utf-8')
if 'Download national CPI-U' in s:raise SystemExit('CPI workflow already installed; no changes')
needle='      - name: Commit validated monthly observations'
if s.count(needle)!=1:raise SystemExit('Unexpected workflow structure: missing commit step')
new='      - name: Download national CPI-U\n        run: python fetch_cpi.py\n'+needle
s=s.replace(needle,new)
needle='git add normalized/monthly.csv local/city_allocations.csv local/years/*.csv'
if s.count(needle)!=1:raise SystemExit('Unexpected workflow git add step')
s=s.replace(needle,needle+' inflation/cpi_u.csv')
needle='mkdir -p _site/normalized _site/local'
if s.count(needle)!=1:raise SystemExit('Unexpected public site assembly')
s=s.replace(needle,'mkdir -p _site/normalized _site/local _site/inflation')
needle='cp local/city_allocations.csv _site/local/city_allocations.csv'
if s.count(needle)!=1:raise SystemExit('Unexpected city CSV deployment')
s=s.replace(needle,needle+'\n          cp inflation/cpi_u.csv _site/inflation/cpi_u.csv')
# Ensure changes to CPI fetch source trigger a fresh workflow.
needle="      - 'fetch_city_history.py'"
if needle in s:s=s.replace(needle,needle+"\n      - 'fetch_cpi.py'")
backup=p.with_name('update-dashboard.yml.before-real-growth-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
shutil.copy2(p,backup)
p.write_text(s,encoding='utf8')
print('Workflow upgraded; backup: '+backup.name)
