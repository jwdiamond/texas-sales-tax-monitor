"""Apply an idempotent nominal/real + UI refinement patch to current index.html.
Run from Texas Sales Tax Monitor repository root, not from this package folder.
Only index.html is edited; creates a timestamped backup. No source or forecast data overwritten.
"""
from pathlib import Path
import datetime as dt
import re
import shutil

INDEX=Path.cwd()/'index.html'
MARK='TEXAS_REAL_GROWTH_V1'

def replace_span(s, start, end, value):
    a=s.find(start)
    if a<0: raise ValueError('Missing expected start: '+start[:80])
    b=s.find(end,a+len(start))
    if b<0: raise ValueError('Missing expected end: '+end[:80])
    return s[:a]+value+'\n'+s[b:]

def replace_once(s, old, new):
    if s.count(old)!=1: raise ValueError(f'Expected once ({s.count(old)}): '+old[:90])
    return s.replace(old,new,1)

# Replacement functions remain within existing dashboard closure; other handlers untouched.
HISTORY_JS=r'''function renderHistory(){
  const lev=el('history-level').value;
  const opts=[...new Set(history.filter(r=>r.level===lev).map(r=>r.name))].sort();
  const old=el('history-sector').value;
  el('history-sector').innerHTML='<option value="__total__">All '+(lev==='retail'?'retail subsectors':'industries')+'</option>'+opts.map(n=>'<option value="'+escapeText(n)+'">'+escapeText(n)+'</option>').join('');
  el('history-sector').value=opts.includes(old)?old:'__total__';
  renderTrend();
}'''
TREND_JS=r'''function renderTrend(){
  const rows=selectedHistory(), totals=new Map();
  for(const r of rows) totals.set(r.period,(totals.get(r.period)||0)+r.receipts);
  const nominal=[...totals].sort((a,b)=>a[0].localeCompare(b[0]));
  const real=isReal();
  const data=nominal.map(([period,value])=>[period,real?realDollars(period,value):value]);
  const valid=data.filter(d=>d[1]!==null && Number.isFinite(d[1]));
  el('history-count').textContent=nominal.length+' observed month(s), '+rows.length+' source rows.';
  const latest=nominal.at(-1);
  const latestValue=latest ? (real?realDollars(latest[0],latest[1]):latest[1]):null;
  el('history-latest').textContent=latestValue===null?'—':fmtShort(latestValue);
  el('history-latest-date').textContent=latest?prettyMonth(latest[0])+(real?' · constant '+prettyMonth(cpiBasePeriod)+' dollars':''):'No observations';
  const prev=latest ? totals.get(lastYear(latest[0])):null;
  let yoy=null;
  if(latest && prev!==undefined && prev!==0){
    const nominalRate=latest[1]/prev-1;
    const priceRatio=latest?inflationRatio(latest[0]):null;
    yoy=real?(priceRatio===null?null:100*((1+nominalRate)/priceRatio-1)):100*nominalRate;
  }
  el('history-yoy').textContent=yoy===null?'—':yoy.toFixed(2)+'%';
  const chart=el('history-chart');
  if(!valid.length){chart.innerHTML='<p class="status">No data for this selection or CPI is unavailable.</p>';return;}
  let min=Math.min(...valid.map(d=>d[1])),max=Math.max(...valid.map(d=>d[1]));
  if(min===max){min-=1;max+=1;}
  const W=850,H=340,L=95,R=24,T=18,B=47;
  const px=i=>L+i*(W-L-R)/Math.max(1,data.length-1);
  const py=v=>T+(max-v)*(H-T-B)/(max-min);
  let path='',drawing=false;
  data.forEach(([period,value],i)=>{
    if(value===null || !Number.isFinite(value)){drawing=false;return;}
    path+=(drawing?'L':'M')+px(i).toFixed(1)+','+py(value).toFixed(1)+' ';drawing=true;
  });
  const grids=Array.from({length:5},(_,i)=>{
    const v=min+(max-min)*(4-i)/4,y=py(v);
    return `<line class="gridline" x1="${L}" x2="${W-R}" y1="${y}" y2="${y}"/><text x="${L-8}" y="${y+4}" text-anchor="end">${escapeText(fmtShort(v))}</text>`;
  }).join('');
  const ticks=data.filter((_,i)=>i===0 || i===data.length-1 || i%Math.max(1,Math.ceil(data.length/6))===0)
    .map(d=>{const i=data.indexOf(d);return `<text x="${px(i)}" y="${H-14}" text-anchor="middle">${escapeText(d[0].slice(2))}</text>`}).join('');
  chart.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${real?'Inflation adjusted':'Nominal'} monthly industry receipts">${grids}<path class="line" d="${path.trim()}"/>${ticks}</svg>`;
}'''
LOCAL_JS=r'''function renderLocal(){
  const county=el('local-county').value,period=el('local-period').value,real=isReal();
  const a=locals.filter(x=>x.county===county&&x.period===period).sort((x,y)=>y.payment-x.payment);
  const total=a.reduce((v,x)=>v+x.payment,0);
  const totalDisplay=real?realDollars(period,total):total;
  const head=el('local-module').querySelectorAll('thead th');
  if(head.length>=4){head[1].textContent=real?'Real allocation':'Allocation';head[2].textContent=real?'Prior year (real)':'Prior year';head[3].textContent=real?'Real YoY':'YoY';}
  el('local-rows').innerHTML=a.map(x=>{
    const current=real?realDollars(period,x.payment):x.payment;
    const prev=real?realDollars(lastYear(period),x.prior):x.prior;
    const growth=prev!==null && current!==null && prev!==0?100*(current/prev-1):null;
    return `<tr><td>${escapeText(x.city)}</td><td class="num">${current===null?'—':fmoney(current)}</td><td class="num">${prev===null?'—':fmoney(prev)}</td><td class="num">${growth===null?'—':growth.toFixed(1)+'%'}</td></tr>`;
  }).join('')||'<tr><td colspan="4">No records for this selection.</td></tr>';
  el('local-msg').innerHTML=`<strong>${a.length} cities</strong> · <strong>${totalDisplay===null?'—':fmoney(totalDisplay)}</strong> ${real?'real':'nominal'} allocations · <strong>${escapeText(prettyMonth(period))}</strong><span class="city-source-note">${real&&totalDisplay===null?'CPI for this month not yet available. ':'Not countywide taxable sales.'}</span>`;
}'''
CITY_JS=r'''function renderCityComparisons(){
  const ids=[el('city-compare-a').value,el('city-compare-b').value];
  const metric=el('city-compare-metric').value,real=isReal();
  const maps=ids.map(id=>new Map(cityHistoryRows.filter(x=>x.id===id).map(x=>[x.period,x])));
  const periods=[...new Set([...maps[0].keys(),...maps[1].keys()])].sort();
  const first=periods.find(p=>maps.every(m=>m.has(p)&&(real?realDollars(p,m.get(p).payment)!==null:true)));
  const series=maps.map(m=>{
    const anchor=first&&m.has(first)?(real?realDollars(first,m.get(first).payment):m.get(first).payment):null;
    const values=periods.map(p=>{
      const r=m.get(p);if(!r)return null;
      const cur=real?realDollars(p,r.payment):r.payment;
      if(cur===null)return null;
      if(metric==='amount')return cur;
      if(metric==='index')return anchor!==null && anchor!==0?100*cur/anchor:null;
      if(metric==='ma12'){
        let sum=0;
        for(let k=0;k<12;k++){
          const yr=Number(p.slice(0,4)),mo=Number(p.slice(5));
          const d=new Date(Date.UTC(yr,mo-1-k,1));
          const key=d.getUTCFullYear()+'-'+String(d.getUTCMonth()+1).padStart(2,'0');
          const found=m.get(key);if(!found)return null;
          const v=real?realDollars(key,found.payment):found.payment;
          if(v===null)return null;
          sum+=v;
        }
        return sum/12;
      }
      const ratio=real?inflationRatio(p):1;
      return r.prior!==0 && ratio!==null?100*((r.payment/r.prior)/ratio-1):null;
    });
    return values;
  });
  const valid=series.flat().filter(x=>x!==null && Number.isFinite(x));
  if(!valid.length){el('city-compare-chart').textContent='No comparable observations for this selection.';el('city-compare-summary').textContent='Check CPI availability or select another metric.';return;}
  let lo=Math.min(...valid),hi=Math.max(...valid);if(lo===hi){lo-=1;hi+=1;}
  const W=980,H=355,L=110,R=25,T=24,B=52,w=W-L-R,h=H-T-B;
  const xp=i=>L+i*w/Math.max(1,periods.length-1),yp=v=>T+h-(v-lo)*h/(hi-lo), colors=['#3d68b1','#b87c39'];
  function pathFor(points){let d='',open=false;points.forEach((v,i)=>{if(v===null || !Number.isFinite(v)){open=false;return;}d+=(open?'L':'M')+xp(i).toFixed(2)+','+yp(v).toFixed(2)+' ';open=true;});return d;}
  const format=v=>metric==='amount'||metric==='ma12'?fmoney(v):metric==='index'?v.toFixed(1):v.toFixed(1)+'%';
  const axis=v=>metric==='amount'||metric==='ma12'?fmtShort(v):metric==='index'?v.toFixed(0):v.toFixed(1)+'%';
  const grid=[0,.25,.5,.75,1].map(t=>{let y=T+t*h,v=hi-t*(hi-lo);return `<line x1="${L}" x2="${W-R}" y1="${y}" y2="${y}" stroke="#e3e8f0"/><text x="${L-9}" y="${y+4}" font-size="12" text-anchor="end" fill="#64748b">${escapeText(axis(v))}</text>`}).join('');
  const labels=[0,.25,.5,.75,1].map(t=>{let i=Math.min(periods.length-1,Math.floor(t*(periods.length-1)));return `<text x="${xp(i)}" y="${H-20}" font-size="12" text-anchor="middle" fill="#64748b">${periods[i]}</text>`}).join('');
  el('city-compare-chart').innerHTML=`<svg viewBox="0 0 ${W} ${H}" style="width:100%;min-width:580px" role="img" aria-label="Monthly municipal allocations comparison">${grid}${labels}${series.map((s,i)=>`<path d="${pathFor(s)}" fill="none" stroke="${colors[i]}" stroke-width="2.7"/>`).join('')}</svg>`;
  el('city-compare-summary').innerHTML=ids.map((id,i)=>{
    const idx=series[i].findLastIndex(v=>v!==null && Number.isFinite(v));
    const last=idx>=0?`${format(series[i][idx])} (${prettyMonth(periods[idx])})`:'not available';
    return `<span style="display:inline-block;margin:0 28px 7px 0"><span style="color:${colors[i]}">●</span> <b>${escapeText(id.replace('|',' / '))}</b>: ${escapeText(last)}</span>`;
  }).join('')+`<div>${periods.length} months · ${real?'inflation-adjusted':'nominal'} · ${metric==='index'?'index base '+(first||'unavailable')+' = 100':metric==='ma12'?'trailing 12-month average':'missing months are not interpolated'}</div>`;
}'''
INFLATION_JS=r'''/* TEXAS_REAL_GROWTH_V1 — National CPI-U, not seasonally adjusted. */
let cpiMonths=new Map(),cpiBasePeriod=null,cpiBaseValue=null;
const isReal=()=>el('price-mode').value==='real';
const prettyMonth=p=>/^\d{4}-\d{2}$/.test(p)?new Date(p+'-01T12:00:00Z').toLocaleDateString('en-US',{month:'long',year:'numeric',timeZone:'UTC'}):p;
const lastYear=p=>String(Number(p.slice(0,4))-1)+p.slice(4);
function inflationRatio(p){const c=cpiMonths.get(p),prior=cpiMonths.get(lastYear(p));return c!==undefined&&prior!==undefined&&prior>0?c/prior:null;}
function realDollars(p,n){const c=cpiMonths.get(p);return c!==undefined&&c>0&&cpiBaseValue!==null?n*cpiBaseValue/c:null;}
function repaintPriceViews(){
  renderTrend();renderLocal();
  if(cityHistoryRows.length)renderCityComparisons();
  const note=el('cpi-indicator');
  note.textContent=cpiBasePeriod?('CPI-U national · through '+prettyMonth(cpiBasePeriod)+' · '+(isReal()?'constant '+prettyMonth(cpiBasePeriod)+' dollars':'nominal dollars')):'CPI not loaded — real values unavailable';
}
async function loadCPI(){
  try{
    const response=await fetch('./inflation/cpi_u.csv',{cache:'no-cache'});
    if(!response.ok)throw Error('HTTP '+response.status);
    const csv=parseCSV(await response.text());
    const map=new Map();
    for(const row of csv){
      if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(row.period))throw Error('Invalid CPI month');
      const v=Number(row.cpi);
      if(!Number.isFinite(v)||v<=0||map.has(row.period))throw Error('Invalid or duplicate CPI value');
      map.set(row.period,v);
    }
    if(map.size<250)throw Error('CPI history unexpectedly short');
    cpiMonths=map;cpiBasePeriod=[...map.keys()].sort().at(-1);cpiBaseValue=map.get(cpiBasePeriod);
    repaintPriceViews();
  }catch(error){el('cpi-indicator').textContent='CPI unavailable; nominal data still accessible';console.error('CPI load failed',error);}
}
el('price-mode').onchange=repaintPriceViews;
loadCPI();'''

CSS=r'''<style id="TEXAS_REAL_GROWTH_V1">
#real-growth-controls {display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:0 0 14px;padding:13px 17px;border:1px solid #dce5f0;border-radius:12px;background:#fff}
#real-growth-controls label{font-size:13px;font-weight:650;color:#263a57}
#real-growth-controls select{border:1px solid #ccd6e4;padding:9px 13px;border-radius:9px;color:#263a57;background:#fff}
#cpi-indicator{font-size:12px;color:#63758d}
.city-source-note{margin-left:12px;font-size:12px;color:#718198;font-weight:400}
#historical-module .three-cols{grid-template-columns:minmax(0,1.9fr) minmax(210px, .8fr)}
#historical-module #history-chart svg{width:100%;height:auto;min-height:300px}
#historical-module .status,#local-module .status{line-height:1.5}
#local-module .local-table{max-height:520px;overflow:auto}
#local-module .local-table thead{position:sticky;top:0;background:#f2f5fa;z-index:1}
@media(max-width:800px){#historical-module .three-cols{grid-template-columns:1fr}.city-source-note{display:block;margin-left:0}}
</style>'''

def main():
    if not INDEX.exists():raise SystemExit('Run from the directory containing index.html')
    s=INDEX.read_text(encoding='utf-8')
    if MARK in s:raise SystemExit('This upgrade has already been applied. No changes made.')
    required=['function renderHistory()', 'function renderTrend()', 'function renderLocal()', 'function renderCityComparisons()', "let cityHistoryRows = [];", "autoLoadCities();"]
    for r in required:
        if r not in s:raise SystemExit('Incompatible dashboard version: '+r)
    s=replace_once(s,'</head>',CSS+'\n</head>')
    controls='''<div id="real-growth-controls"><label for="price-mode">Revenue values</label><select id="price-mode" aria-label="Nominal or inflation-adjusted"><option value="nominal">Nominal dollars</option><option value="real">Real (CPI-adjusted)</option></select><span id="cpi-indicator">Loading CPI-U…</span></div>'''
    s=replace_once(s,'<div class="section card" id="historical-module">',controls+'<div class="section card" id="historical-module">')
    s=replace_once(s,'<option value="amount">Monthly allocation ($)</option><option value="yoy">Year-over-year (%)</option>', '<option value="amount">Monthly allocation ($)</option><option value="yoy">Year-over-year growth (%)</option><option value="ma12">12-month moving average ($)</option><option value="index">Indexed (first common month = 100)</option>')
    s=replace_span(s,'function renderHistory(){','function escapeText(s)',HISTORY_JS)
    s=replace_span(s,'function renderTrend(){','async function readFile(id)',TREND_JS)
    s=replace_span(s,'function renderLocal(){',"el('local-file').onchange",LOCAL_JS)
    s=replace_span(s,'function renderCityComparisons() {','async function autoLoadCities() {',CITY_JS)
    s=replace_once(s,'function selectedHistory(){',INFLATION_JS+'\nfunction selectedHistory(){')
    # Make old manual CSV parser consistent with historical negative adjustments.
    s=s.replace("!Number.isFinite(n)||n<0||!name", "!Number.isFinite(n)||!name")
    # Shorter, clearer on-screen copy; never claim 2026-10 national CPI exists.
    s=s.replace('Monthly taxpayer remittances by NAICS sector (nominal dollars)', 'Monthly taxpayer remittances by NAICS sector (reported nominal receipts)')
    s=s.replace('Source: Texas Comptroller. Reported net receipts may be revised.', 'Source: Texas Comptroller. Real values use national CPI-U (not seasonally adjusted); figures may be revised.')
    s=s.replace('Source: Texas Comptroller. Payment-month allocations may include adjustments and tax-rate changes.', 'Source: Texas Comptroller. Allocation month, not taxable-sales month; values may include adjustments or tax-rate changes.')
    backup=INDEX.with_name('index.html.before-real-growth-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(INDEX,backup)
    INDEX.write_text(s,encoding='utf-8')
    print('Updated index.html. Backup: '+backup.name)
    print('Controls: nominal / CPI-adjusted; city YoY, 12-month average, indexed series.')
    print('Run fetch_cpi.py before local testing; CPI-missing months remain unavailable.')

if __name__=='__main__':main()
