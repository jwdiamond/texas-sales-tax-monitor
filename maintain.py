"""Refresh and archive official Texas tax sources; reject suspicious changes.

Usage: python maintain.py [--with-local] [--dry-run]
Run in GitHub Actions with Python 3.11+, openpyxl installed.
Does not infer an unknown XLSX schema or fabricate time series.
"""
import argparse, csv, datetime as dt, hashlib, io, json, os, pathlib, shutil, sys, tempfile, urllib.error, urllib.request
from openpyxl import load_workbook

ROOT=pathlib.Path(__file__).resolve().parent
DATA=ROOT/'source_data'
SOURCES={
 'industry': 'https://comptroller.texas.gov/transparency/revenue/watch/naics/data/sales-tax-naics-historical.xlsx',
 'retail': 'https://comptroller.texas.gov/transparency/revenue/watch/naics/data/retail-sector-historical.xlsx',
}
HEADERS={'User-Agent':'TexasSalesTaxMonitor/0.3 (public research; contact via repository)'}

def fetch(url):
 request=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(request,timeout=65) as resp:
  data=resp.read(50_000_001)
  if len(data)>50_000_000: raise ValueError('Download exceeds 50 MB guardrail')
 return data

def validate_xlsx(data,kind):
 if len(data)<1000 or not data.startswith(b'PK'):
  raise ValueError(f'{kind}: file is not an XLSX workbook')
 wb=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
 try:
  sheets=[]; total_rows=0
  for ws in wb.worksheets:
   nonempty=0
   for row in ws.iter_rows(max_row=3000,values_only=True):
    if any(v is not None for v in row): nonempty+=1
   if nonempty: sheets.append({'name':ws.title,'observed_nonempty_rows':nonempty});total_rows+=nonempty
  if total_rows<5: raise ValueError(f'{kind}: unexpectedly sparse workbook')
  return {'sheets':sheets,'observed_nonempty_rows':total_rows}
 finally: wb.close()

def atomic_write(path,content):
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
  f.write(content);tmp=pathlib.Path(f.name)
 os.replace(tmp,path)

def run(with_local=False,dry_run=False):
 DATA.mkdir(exist_ok=True)
 manifest_path=DATA/'manifest.json'
 manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'sources':{},'history':[]}
 timestamp=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
 changes=[]; errors=[]
 for name,url in SOURCES.items():
  try:
   data=fetch(url);meta=validate_xlsx(data,name);sha=hashlib.sha256(data).hexdigest()
   prior=manifest['sources'].get(name,{})
   if sha!=prior.get('sha256'):
    if not dry_run:
     atomic_write(DATA/'latest'/f'{name}.xlsx',data)
     atomic_write(DATA/'archive'/name/f'{timestamp[:10]}_{sha[:12]}.xlsx',data)
     manifest['sources'][name]={'url':url,'sha256':sha,'downloaded_at_utc':timestamp,'bytes':len(data),'validation':meta}
     manifest['history'].append({'source':name,'observed_at_utc':timestamp,'sha256':sha})
    changes.append(name)
   print(json.dumps({'source':name,'status':'changed' if sha!=prior.get('sha256') else 'unchanged','sha256':sha,'validation':meta}))
  except Exception as e:
   errors.append(f'{name}: {e}')
 if with_local:
  try:
   import fetch_local
   year=dt.datetime.now(dt.timezone.utc).year
   if not dry_run:
    with tempfile.TemporaryDirectory() as tmp:
     output=pathlib.Path(tmp)/'city_allocations.csv'
     fetch_local.download(year,str(output))
     with output.open(newline='',encoding='utf8') as f:
      reader=csv.DictReader(f);expected=set(fetch_local.FIELDS)
      if not expected.issubset(reader.fieldnames or []):raise ValueError('Local API schema mismatch')
      count=sum(1 for _ in reader)
      if count<100:raise ValueError(f'Local allocations unexpectedly sparse: {count} rows')
     data=output.read_bytes();sha=hashlib.sha256(data).hexdigest()
     if sha!=manifest['sources'].get('city_allocations',{}).get('sha256'):
      atomic_write(DATA/'latest'/'city_allocations.csv',data)
      manifest['sources']['city_allocations']={'url':fetch_local.API,'year':year,'sha256':sha,'downloaded_at_utc':timestamp,'rows':count}
      manifest['history'].append({'source':'city_allocations','observed_at_utc':timestamp,'sha256':sha})
      changes.append('city_allocations')
     print(json.dumps({'source':'city_allocations','rows':count,'status':'validated'}))
  except Exception as e: errors.append(f'city_allocations: {e}')
 if not dry_run:
  manifest['last_check_utc']=timestamp
  manifest['last_check_errors']=errors
  atomic_write(manifest_path,json.dumps(manifest,indent=2,sort_keys=True).encode()+b'\n')
  atomic_write(DATA/'status.json',json.dumps({'checked_at_utc':timestamp,'changed_sources':changes,'errors':errors,'source_count':len(manifest['sources'])},indent=2).encode()+b'\n')
 print(json.dumps({'checked_at_utc':timestamp,'changes':changes,'errors':errors}))
 if errors:raise SystemExit(1)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--with-local',action='store_true');p.add_argument('--dry-run',action='store_true');a=p.parse_args();run(a.with_local,a.dry_run)
