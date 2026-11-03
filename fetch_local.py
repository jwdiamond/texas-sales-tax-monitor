"""Download official monthly city allocations grouped by county.
Requires internet access. No Socrata token needed for moderate request volume.
Run: python fetch_local.py --year 2026 --output local_2026.csv
"""
import argparse,csv,json,time,urllib.parse,urllib.request
API='https://data.texas.gov/resource/53pa-m7sm.json'
FIELDS=['county','city','current_rate','net_payment_this_period','comparable_payment_prior_year','period_percent_change','payments_to_date','previous_payments_to_date','year_percent_change','report_month','report_year','report_period_type']

def download(year,output):
    seen=set();count=0;offset=0;limit=5000
    with open(output,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
        while True:
            params={'$where':f'report_year = {int(year)}','$limit':limit,'$offset':offset,'$order':'county,city,report_month'}
            url=API+'?'+urllib.parse.urlencode(params)
            req=urllib.request.Request(url,headers={'User-Agent':'TexasSalesTaxMonitor/0.1'})
            with urllib.request.urlopen(req,timeout=45) as r: rows=json.load(r)
            for row in rows:
                key=(row.get('county'),row.get('city'),row.get('report_month'),row.get('report_year'),row.get('report_period_type'))
                if key in seen:continue
                seen.add(key);w.writerow({k:row.get(k,'') for k in FIELDS});count+=1
            print(f'Fetched {len(rows)} rows at offset {offset}; saved {count}')
            if len(rows)<limit:break
            offset+=limit;time.sleep(.1)
    print(f'Wrote {output}. IMPORTANT: these are municipal ALLOCATIONS, not total taxable sales by county.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--year',type=int,default=2026);p.add_argument('--output',default='local_2026.csv');a=p.parse_args();download(a.year,a.output)
