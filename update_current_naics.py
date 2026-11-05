"""Import current fiscal-year NAICS web tables into normalized/monthly.csv.

Usage:
  python update_current_naics.py --check
  python update_current_naics.py --apply
  python update_current_naics.py --apply --snapshot-september-2026

Snapshot is a documented fallback when HTML cannot be fetched locally; do not
mistake it for a fresh web check. Requires requests and beautifulsoup4.
"""
import argparse
import csv
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

URLS = {
    'industry': 'https://comptroller.texas.gov/transparency/revenue/watch/naics/naics-industry.php',
    'retail': 'https://comptroller.texas.gov/transparency/revenue/watch/naics/naics-retail.php',
}
FIELDS = ['period', 'level', 'name', 'receipts', 'group']
MONTHS = ['September','October','November','December','January','February','March','April','May','June','July','August']
# Verified on official Comptroller webpages, 2026-11-04. Not a live feed.
SEPT_2026 = {
 'industry': {
 'Agriculture':2318549,'Mining':187647021,'Utilities':134404529,'Construction':228626065,
 'Manufacturing':354688385,'Wholesale Trade':411469024,'Retail Trade':1572930560,
 'Transportation':56993453,'Information':297638243,'Finance and Insurance':33404507,
 'Real Estate, Rental and Leasing':128284403,'Services':473422344,
 'Eating and Drinking Places':441750107,'Public Administration':20668400,'No Code':62099175,
 },
 'retail': {
 'Automotive Dealers':103838032,'Building Materials and Garden Equipment Stores':186098526,
 'Clothing and Accessories Stores':130470023,
 'Electronic Shopping, Vending Machine, and Direct Sellers':304079153,
 'Electronics and Appliances':75374377,'Food and Beverage Stores':138296262,
 'Furniture and Home Furnishing Stores':56627701,'Gasoline Stations':88431341,
 'General Merchandise Stores':272090250,'Health and Personal Care Stores':27091873,
 'Miscellaneous Retail':137772300,
 'Sporting Goods, Hobby, Musical, and Book Stores':52740756,
 },
}
EXPECTED_SEPT_TOTALS={'industry':4406344765,'retail':1572910594}


def amount(s):
    s = str(s).replace('$','').replace(',','').replace('\u00a0','').strip()
    return int(s) if re.fullmatch(r'-?\d+',s) else None


def parse_live(html, level):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html,'html.parser')
    text = soup.get_text(' ',strip=True)
    m = re.search(r'Fiscal\s+(20\d{2})', text, re.I)
    if not m: raise ValueError(f'{level}: fiscal year not found')
    fy=int(m.group(1))
    # The official page may have several layout tables. Identify the data table
    # by its full sector labels, not by its order in the document.
    match=None
    anchor='Agriculture' if level=='industry' else 'Automotive Dealers'
    for table in soup.find_all('table'):
        if anchor in table.get_text(' ',strip=True) and 'Total' in table.get_text(' ',strip=True):
            match=table;break
    if match is None: raise ValueError(f'{level}: could not locate fiscal data table; site markup may have changed')
    # First column = sector, then one monthly amount per published month,
    # then fiscal YTD total and percent change. The site also inserts
    # Percentage Change rows; those must not be confused with sectors.
    headings=[x.get_text(' ',strip=True) for x in match.find_all('th')]
    months=[]
    for h in headings:
        for mon in MONTHS:
            if re.search(r'\b'+mon+r'\b',h,re.I) and mon not in months:
                months.append(mon)
    # Some site templates put heading values in td instead of th.
    if not months:
        header_rows=match.find_all('tr')[:5]
        for tr in header_rows:
            for cell in tr.find_all(['td','th'],recursive=False):
                h=cell.get_text(' ',strip=True)
                for mon in MONTHS:
                    if re.search(r'\b'+mon+r'\b',h,re.I) and mon not in months:
                        months.append(mon)
    if not months: raise ValueError(f'{level}: published month headings not detected; refusing to guess')
    if months != MONTHS[:len(months)]:
        raise ValueError(f'{level}: nonconsecutive month headings {months}')
    records={mon:{} for mon in months}
    totals={}
    for tr in match.find_all('tr'):
        cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
        if not cells: continue
        name=cells[0].strip()
        if name.lower()=='percentage change' or not name:continue
        if name.lower()=='total' or name in SEPT_2026[level]:
            values=[amount(v) for v in cells[1:]]
            # Only take the first N cells, no interpreting fiscal YTD as a month.
            if len(values)<len(months) or any(v is None for v in values[:len(months)]):
                raise ValueError(f'{level}: invalid monthly data for {name}: {cells}')
            for mon,v in zip(months,values):
                (totals if name.lower()=='total' else records[mon])[mon if name.lower()=='total' else name]=v
    for mon in months:
        if set(records[mon]) != set(SEPT_2026[level]):
            raise ValueError(f'{level}: unexpected sector names for {mon}; got {sorted(records[mon])}')
        if sum(records[mon].values())!=totals.get(mon):
            raise ValueError(f'{level}: {mon} sector sum differs from published total: {sum(records[mon].values())} vs {totals.get(mon)}')
    output={}
    for mon in months:
        year=fy-1 if MONTHS.index(mon)<=3 else fy  # Sep-Dec fiscal FY-1; Jan-Aug FY
        output[f'{year}-{MONTHS.index(mon)+9:02d}' if MONTHS.index(mon)<=3 else f'{year}-{MONTHS.index(mon)-3:02d}']=records[mon]
    return output,totals,fy


def fetch_live():
    import requests
    data={};meta={}
    for level,url in URLS.items():
        response=requests.get(url,headers={'User-Agent':'TexasSalesTaxMonitorResearch/1.0'},timeout=30)
        response.raise_for_status()
        months, totals, fy = parse_live(response.text,level)
        data[level]=months
        meta[level]={'url':url,'fiscal_year':fy,'totals':totals}
    if set(data['industry'])!=set(data['retail']):
        raise ValueError('Industry and retail webpage months differ; refusing partial update')
    return data,meta


def prepare(csvpath,data):
    if not csvpath.exists(): raise FileNotFoundError(csvpath)
    with csvpath.open('r',encoding='utf-8-sig',newline='') as fh:
        reader=csv.DictReader(fh)
        if reader.fieldnames!=FIELDS:raise ValueError(f'CSV columns unexpectedly changed: {reader.fieldnames}')
        rows=list(reader)
    existing={(r['period'],r['level'],r['name']):r for r in rows}
    additions=[];conflicts=[]
    for level,by_month in data.items():
        for period,sectors in by_month.items():
            if sum(sectors.values())<=0:raise ValueError('Nonpositive period total')
            for name,value in sectors.items():
                key=(period,level,name)
                if key in existing:
                    old=amount(existing[key]['receipts'])
                    if old!=value:conflicts.append((key,old,value))
                else:
                    additions.append({'period':period,'level':level,'name':name,'receipts':str(value),'group':''})
    return rows,additions,conflicts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    action=p.add_mutually_exclusive_group(required=True)
    action.add_argument('--check',action='store_true')
    action.add_argument('--apply',action='store_true')
    p.add_argument('--snapshot-september-2026',action='store_true',help='Use preverified Nov 4 Sep values; NOT live checking')
    p.add_argument('--csv',default='normalized/monthly.csv')
    a=p.parse_args()
    if a.snapshot_september_2026:
        for level in SEPT_2026:
            s=sum(SEPT_2026[level].values())
            if s!=EXPECTED_SEPT_TOTALS[level]:raise ValueError(f'{level} hardcoded snapshot sum mismatch {s}')
        data={level:{'2026-09':sectors} for level,sectors in SEPT_2026.items()}
        meta={'source':'Official Comptroller NAICS pages, verified 2026-11-04; manual snapshot (not current live verification)'}
    else:
        data,meta=fetch_live()
    path=Path(a.csv)
    original,additions,conflicts=prepare(path,data)
    print('Source:',json.dumps(meta,default=str))
    for level in data:print(level,'months:',', '.join(sorted(data[level])))
    print('Existing:',len(original),'New rows:',len(additions),'Revisions/conflicts:',len(conflicts))
    if conflicts:
        for entry in conflicts[:12]:print('  CONFLICT:',entry)
        raise SystemExit('ABORT: previously stored official values differ. Review revisions before applying.')
    if not a.apply:
        print('CHECK ONLY. Nothing written.');return
    if not additions:
        print('Nothing new to append.');return
    backup=path.with_suffix('.csv.before_current_naics.bak')
    if backup.exists():raise SystemExit(f'ABORT: backup already exists: {backup}; preserve it before rerunning')
    import shutil
    shutil.copy2(path,backup)
    additions.sort(key=lambda r:(r['period'],r['level'],r['name']))
    with path.open('w',encoding='utf-8',newline='') as fh:
        writer=csv.DictWriter(fh,fieldnames=FIELDS,lineterminator='\n')
        writer.writeheader();writer.writerows(original+additions)
    receipt=path.parent/'current_naics_import_receipt.json'
    receipt.write_text(json.dumps({'imported_at_utc':datetime.now(timezone.utc).isoformat(),
      'source':meta,'added_rows':len(additions),'months':{level:sorted(data[level]) for level in data},
      'backup':str(backup)},indent=2)+'\n',encoding='utf-8')
    print('UPDATED',path,'BACKUP',backup,'RECEIPT',receipt)

if __name__=='__main__':main()
