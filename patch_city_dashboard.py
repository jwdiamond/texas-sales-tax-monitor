"""Idempotently add auto-loaded city history and city comparisons to existing index.html.

Backs up index.html first. Never rewrites the existing statewide dashboard functions.
Usage: python patch_city_dashboard.py
"""
from pathlib import Path
import shutil

p = Path(__file__).resolve().parent / 'index.html'
if not p.exists():
    raise SystemExit('index.html not found: copy this script into your project root')
s = p.read_text(encoding='utf-8')
if 'Texas City History Upgrade v1' in s:
    print('City history upgrade already present; no changes')
    raise SystemExit(0)
marker = '})();\n</script>'
if marker not in s or 'function renderLocal()' not in s or 'function parseCSV(' not in s:
    raise SystemExit('Could not find expected city module; no changes made')
shutil.copy2(p, p.with_suffix('.html.before-city-upgrade'))
addition = r'''
/* Texas City History Upgrade v1: auto-load normalized official municipal allocations. */
const cityHistorySection = document.createElement('section');
cityHistorySection.className = 'section card';
cityHistorySection.innerHTML = `
  <h2>Historical city comparisons</h2>
  <p>Monthly municipal sales tax allocations (payment month). These are not taxable sales or county revenue.</p>
  <div style="display:flex;gap:12px;flex-wrap:wrap;margin:14px 0">
    <label>First city <select id="city-compare-a" aria-label="First city"></select></label>
    <label>Second city <select id="city-compare-b" aria-label="Second city"></select></label>
    <label>Metric <select id="city-compare-metric"><option value="amount">Monthly allocation ($)</option><option value="yoy">Year-over-year (%)</option></select></label>
  </div>
  <div id="city-compare-summary" class="status">Loading historical allocations…</div>
  <div id="city-compare-chart" style="width:100%;overflow-x:auto"></div>
  <p style="font-size:12px;color:#66758b">Monthly allocation values may include corrections and tax-rate changes. YoY growth is computed from the reported comparable prior-year payment, not an economic activity month.</p>`;
const localModule = document.getElementById('local-module');
if (localModule) localModule.insertAdjacentElement('afterend', cityHistorySection);
let cityHistoryRows = [];
function parseCityHistoryRows(rows) {
  const required = ['county','city','report_year','report_month','net_payment_this_period','comparable_payment_prior_year'];
  if (!rows.length || required.some(k => !(k in rows[0]))) throw Error('Missing required city allocation fields');
  const seen = new Set();
  return rows.map((r, i) => {
    const year = Number(r.report_year), month = Number(r.report_month);
    const payment = toNumber(r.net_payment_this_period), prior = toNumber(r.comparable_payment_prior_year);
    if (!Number.isInteger(year) || year < 2000 || year > 2100 || !Number.isInteger(month) || month < 1 || month > 12 ||
        !Number.isFinite(payment) || !Number.isFinite(prior) || !r.county || !r.city)
      throw Error('Invalid city allocation at row ' + (i+2));
    const period = `${year}-${String(month).padStart(2,'0')}`;
    const id = `${r.county}|${r.city}`;
    const key = `${period}|${id}|${r.report_period_type||''}`;
    if (seen.has(key)) throw Error('Duplicate city/month: ' + key);
    seen.add(key);
    return {county:r.county,city:r.city,id,period,payment,prior};
  });
}
function setCityHistoryRows(out) {
  locals = out;
  cityHistoryRows = out;
  const counties = [...new Set(out.map(x => x.county))].sort();
  const months = [...new Set(out.map(x => x.period))].sort();
  el('local-county').innerHTML = counties.map(x => `<option value="${escapeText(x)}">${escapeText(x)}</option>`).join('');
  el('local-period').innerHTML = months.map(x => `<option value="${x}">${x}</option>`).join('');
  el('local-county').value = counties.includes('Harris') ? 'Harris' : counties[0];
  el('local-period').value = months.at(-1);
  renderLocal();
  el('local-msg').textContent += ` Historical data loaded automatically (${out.length.toLocaleString()} records).`;
  setupCityComparisons();
}
function setupCityComparisons() {
  const cities = [...new Map(cityHistoryRows.map(x => [x.id, `${x.city} (${x.county})`])).entries()]
    .sort((a,b) => a[1].localeCompare(b[1]));
  const opts = cities.map(([id,label]) => `<option value="${escapeText(id)}">${escapeText(label)}</option>`).join('');
  for (const name of ['city-compare-a','city-compare-b']) el(name).innerHTML = opts;
  const pick = (county,city) => cities.find(([id]) => id === county+'|'+city)?.[0];
  el('city-compare-a').value = pick('Harris','Houston') || cities[0][0];
  el('city-compare-b').value = pick('Dallas','Dallas') || cities[Math.min(1,cities.length-1)][0];
  for (const name of ['city-compare-a','city-compare-b','city-compare-metric']) el(name).onchange = renderCityComparisons;
  renderCityComparisons();
}
function renderCityComparisons() {
  const ids = [el('city-compare-a').value,el('city-compare-b').value];
  const metric = el('city-compare-metric').value;
  const maps = ids.map(id => new Map(cityHistoryRows.filter(x=>x.id===id).map(x=>[x.period, x])));
  const periods = [...new Set([...maps[0].keys(),...maps[1].keys()])].sort();
  const series = maps.map(m => periods.map(p => {
    const r=m.get(p);return r?(metric==='amount'?r.payment:(r.prior!==0?100*(r.payment/r.prior-1):null)):null;
  }));
  const values=series.flat().filter(x=>x!==null && Number.isFinite(x));
  if (!values.length) {el('city-compare-chart').textContent='No comparable observations.';return;}
  let lo=Math.min(...values),hi=Math.max(...values);if(lo===hi){lo-=1;hi+=1;}
  const W=980,H=330,L=105,R=22,T=25,B=52, w=W-L-R,h=H-T-B;
  const xp=i=>L+i*w/Math.max(1,periods.length-1),yp=v=>T+h-(v-lo)*h/(hi-lo);
  const colors=['#3d68b1','#b87c39'];
  function pathFor(points){let d='',open=false;points.forEach((v,i)=>{if(v===null || !Number.isFinite(v)){open=false;return;}d+=(open?'L':'M')+xp(i).toFixed(2)+','+yp(v).toFixed(2)+' ';open=true;});return d;}
  const fmt=v=>metric==='amount'?fmoney(v):v.toFixed(1)+'%';
  const grid=[0,0.25,0.5,0.75,1].map(t=>{let y=T+t*h,v=hi-t*(hi-lo);return `<line x1="${L}" x2="${W-R}" y1="${y}" y2="${y}" stroke="#e3e8f0"/><text x="${L-9}" y="${y+4}" font-size="12" text-anchor="end" fill="#64748b">${escapeText(metric==='amount'?fmtShort(v):v.toFixed(1)+'%')}</text>`;}).join('');
  const labels=[0,0.25,0.5,0.75,1].map(t=>{let i=Math.min(periods.length-1,Math.floor(t*(periods.length-1)));return `<text x="${xp(i)}" y="${H-20}" font-size="12" text-anchor="middle" fill="#64748b">${periods[i]}</text>`;}).join('');
  el('city-compare-chart').innerHTML=`<svg viewBox="0 0 ${W} ${H}" style="width:100%;min-width:580px" role="img" aria-label="Comparison of two city allocation series">${grid}${labels}${series.map((s,i)=>`<path d="${pathFor(s)}" fill="none" stroke="${colors[i]}" stroke-width="2.7"/>`).join('')}</svg>`;
  el('city-compare-summary').innerHTML=ids.map((id,i)=>{
    const idx=series[i].findLastIndex(v=>v!==null && Number.isFinite(v));
    const last=idx>=0?`${fmt(series[i][idx])} (${periods[idx]})`:'no observations';
    return `<span style="display:inline-block;margin:0 28px 7px 0"><span style="color:${colors[i]}">●</span> <b>${escapeText(id.replace('|',' / '))}</b>: ${escapeText(last)}</span>`;
  }).join('') + `<div>${periods.length} months represented; missing months are not interpolated.</div>`;
}
async function autoLoadCities() {
  try {
    const response=await fetch('./local/city_allocations.csv', {cache:'no-cache'});
    if(!response.ok) throw Error('HTTP '+response.status);
    const rows=parseCSV(await response.text());
    setCityHistoryRows(parseCityHistoryRows(rows));
    console.log(`Loaded ${cityHistoryRows.length} municipal allocation records`);
  } catch(e) {
    el('local-msg').textContent='Automatic city-data load unavailable: '+e.message+'. You can still import a CSV manually.';
    el('city-compare-summary').textContent='City comparisons unavailable until the historical CSV is published.';
    console.error('City data loading error:',e);
  }
}
autoLoadCities();
'''
s = s.replace(marker, addition + '\n' + marker, 1)
p.write_text(s, encoding='utf-8')
print('Updated index.html; backup saved to index.html.before-city-upgrade')
