import os,json,hashlib,re,io,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np
import requests
from pypdf import PdfReader
R=Path('research/foxconn_overnight_sell_20260921_b15');assert os.environ.get('GITHUB_ACTIONS')=='true'
# Validate the result snapshot before enriching documentation.
man=json.loads((R/'manifest.json').read_text());source_run=man['run_id'];source_sha=man['code_sha']
for path,h in man['files'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
links=[
 ('2019-06-20',.129,'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2019-06-14/601138_20190614_1.pdf'),
 ('2020-06-30',.2,'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2020-06-20/601138_20200620_1.pdf'),
 ('2021-07-27',.25,'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2021-07-20/601138_20210720_1_QiOMKFgd.pdf'),
 ('2022-08-05',.5,'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2022-07-30/601138_20220730_1_dCGEMwuO.pdf'),
 ('2023-07-28',.55,'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2023-07-22/601138_20230722_MCQB.pdf'),
 ('2024-08-15',.58,'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2024-08-08/601138_20240808_QRAN.pdf'),
 ('2025-07-31',.64,'https://static.cninfo.com.cn/finalpage/2025-07-24/1224269794.PDF'),
 ('2026-01-16',.33,'https://static.cninfo.com.cn/finalpage/2026-01-09/1224926202.PDF'),
 ('2026-08-03',.65,'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-07-24/601138_20260724_AYP4.pdf')]
(R/'primary_sources').mkdir(exist_ok=True)
def fetch(item):
 date,amount,url=item;row=dict(ex_date=date,amount=amount,url=url,source_type='issuer_primary')
 try:
  r=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'});r.raise_for_status();row['http']=r.status_code
  if not r.content.startswith(b'%PDF'):raise ValueError('HTTP success but body is not PDF')
  p=R/'primary_sources'/f'{date}.pdf';p.write_bytes(r.content);txt='\n'.join(page.extract_text()or''for page in PdfReader(io.BytesIO(r.content)).pages);(p.with_suffix('.txt')).write_text(txt)
  compact=re.sub(r'\s+','',txt);dt=pd.Timestamp(date);datepat=f'{dt.year}/{dt.month}/{dt.day}';count=compact.count(datepat)
  row.update(status='captured_text_requires_review',sha256=hashlib.sha256(r.content).hexdigest(),date_occurrences=count,amount_string_found=str(amount)in compact,issuer_found='601138'in compact,chars=len(compact),text_excerpt=compact[:1100])
  if count>=2 and str(amount)in compact and '601138'in compact:row['status']='amount_and_ex_pay_table_matched'
 except Exception as e:row.update(status='unverified',error=str(e))
 return row
if (R/'primary_source_verification.csv').exists():
 source=pd.read_csv(R/'primary_source_verification.csv').to_dict('records')
else:
 with ThreadPoolExecutor(max_workers=5)as ex:source=list(ex.map(fetch,links))
pd.DataFrame(source).to_csv(R/'primary_source_verification.csv',index=False)
# Official rules and fee page, archive attachments from observed official links.
rules_urls={
 'sse_stock_investing':'https://one.sse.com.cn/onething/gptz/',
 'sse_stamp2022':'https://www.sse.com.cn/services/investors/questions/pay/c/c_20220421_5701222.shtml',
 'sse_2023':'https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20250612_10824490.shtml',
 'sse_2026':'https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml'}
if (R/'official_rules_capture.csv').exists():
 rulelog=pd.read_csv(R/'official_rules_capture.csv').to_dict('records')
else:
 rulelog=[]
 for name,url in rules_urls.items():
  try:
   r=requests.get(url,timeout=25);r.raise_for_status();p=R/'primary_sources'/(name+'.html');p.write_bytes(r.content);r.encoding=r.apparent_encoding;txt=r.text
   rulelog.append(dict(name=name,url=url,status='captured',sha256=hashlib.sha256(r.content).hexdigest()))
   if name in ['sse_2023','sse_2026']:
    from urllib.parse import urljoin
    for k,href in enumerate(re.findall(r'href=[\"\']([^\"\']+\.docx?)[\"\']',txt)):
     link=urljoin(url,href)
     try:
      rr=requests.get(link,timeout=20);rr.raise_for_status();pp=R/'primary_sources'/(name+f'_attachment{k}'+('.docx'if'.docx'in href else'.doc'));pp.write_bytes(rr.content)
      if pp.suffix=='.docx':
       import zipfile,xml.etree.ElementTree as ET
       z=zipfile.ZipFile(io.BytesIO(rr.content));tree=ET.fromstring(z.read('word/document.xml'));plain=''.join(tree.itertext());pp.with_suffix('.txt').write_text(plain)
      rulelog.append(dict(name=pp.name,url=link,status='captured',sha256=hashlib.sha256(rr.content).hexdigest()))
     except Exception as e:rulelog.append(dict(name=link,status='failed',error=str(e)))
  except Exception as e:rulelog.append(dict(name=name,url=url,status='failed',error=str(e)))
 pd.DataFrame(rulelog).to_csv(R/'official_rules_capture.csv',index=False)
# Independent balance-sheet review based on persisted order and account files.
d=pd.read_csv(R/'daily_ledger.csv',parse_dates=['date','exit_date']);ds=d[d.date.ge('2020-01-01')].reset_index(drop=True);checks=[]
oldsha='2690d4ee20e3d885d29e7da65ccd7075e0bdf615'
subprocess.run(['git','fetch','--depth=1','origin',oldsha],check=True,capture_output=True)
oldman=json.loads(subprocess.check_output(['git','show',oldsha+':'+str(R/'manifest.json')],text=True))
for p0 in list(R.glob('orders_*.csv'))+[R/'signals.csv']:
 assert hashlib.sha256(p0.read_bytes()).hexdigest()==oldman['files'][str(p0)],p0
for p in sorted(R.glob('account_S*.csv')):
 z=pd.read_csv(p,parse_dates=['date']);tag=p.stem[len('account_'):];op=R/f'orders_{tag}.csv'
 previous=pd.read_csv(io.StringIO(subprocess.check_output(['git','show',oldsha+':'+str(p)],text=True)),parse_dates=['date'])
 pd.testing.assert_frame_equal(z.drop(columns=['equity_open','hold_equity_after']),previous.drop(columns=['equity_open','hold_equity_after']),check_exact=True)
 if op.stat().st_size<5:o=pd.DataFrame(columns=['date','side','quantity','value','fee','dividend_tax'])
 else:o=pd.read_csv(op,parse_dates=['date'])
 sign=o.side.map({'BUY':1,'SELL':-1});inventory=1000+(o.quantity*sign).groupby(o.date).sum().reindex(z.date,fill_value=0).cumsum().to_numpy()
 np.testing.assert_array_equal(z.shares,inventory)
 np.testing.assert_allclose(z.equity_close,z.cash+z.receivable+z.shares*ds.close-z.dividend_tax_reserve,atol=1e-6)
 # Hold cash/receivable must equal initial cash plus all accrued gross dividends for the same 1000 shares.
 buf=int(tag.split('_')[-2])/100 if tag.split('_')[-1]in['nominal','restricted','locked']else None
 expected=1000*ds.close+1000*ds.close.iloc[0]*buf+1000*ds.dividend_today.cumsum()
 np.testing.assert_allclose(z.hold_equity_close,expected,atol=1e-6)
 if len(o):
  oq=o.groupby(['date','side']).quantity.sum().unstack(fill_value=0)
  assert not ((oq.get('BUY',0)>0)&(oq.get('SELL',0)>0)).any()
  flow=(o.value*np.where(o.side.eq('SELL'),1,-1)-o.fee-o.dividend_tax).groupby(o.date).sum().reindex(z.date,fill_value=0).to_numpy()
 else:flow=np.zeros(len(z))
 expectedcash=1000*ds.close.iloc[0]*buf+np.cumsum(flow+z.dividend_received.to_numpy())
 np.testing.assert_allclose(z.cash,expectedcash,atol=1e-5)
 assert z.cash.min()>=-1e-6
 checks.append(dict(file=p.name,status='PASS',tests='order inventory, equity identity, hold dividends, no same-day buy+sell, independent cashflow'))
pd.DataFrame(checks).to_csv(R/'independent_account_verification.csv',index=False)
# Small reviewer tables; full ledgers never need to be downloaded for review.
x=pd.read_csv(R/'results.csv');cov=pd.read_csv(R/'coverage_bootstrap.csv');st=pd.read_csv(R/'stress.csv');ac=pd.read_csv(R/'accounts.csv');ev=pd.read_csv(R/'events_leave_one_out.csv');trim=pd.read_csv(R/'symmetric_trim.csv');desc=pd.read_csv(R/'descriptive_groups.csv')
# Isolate the valuation-mark correction against the first complete run.
assert hashlib.sha256((R/'results.csv').read_bytes()).hexdigest()=='fa57ad2d23ad32857e3a18d9094bd64c99db79644cd047a7b597968cea6ad645'
old=pd.read_csv(io.StringIO(subprocess.check_output(['git','show',oldsha+':'+str(R/'accounts.csv')],text=True)))
assert old.shape==ac.shape and list(old.columns)==list(ac.columns)
changed=[]
for col in ac.columns:
 if pd.api.types.is_numeric_dtype(ac[col]):same=np.allclose(old[col],ac[col],equal_nan=True,atol=1e-8,rtol=0)
 else:same=old[col].fillna('').equals(ac[col].fillna(''))
 if not same:changed.append(col)
assert all('drawdown'in col or 'mdd'in col for col in changed),changed
(R/'correction_impact.json').write_text(json.dumps(dict(previous_result=oldsha,opportunity_result_bytes_identical=True,changed_account_summary_fields=changed,all_other_account_summary_fields_unchanged=True,signals_and_all_orders_bytes_identical=True,all_daily_account_fields_except_two_mark_fields_identical=True,source_retrieval='Reused already hashed source snapshots; unsuccessful captures remain unverified'),indent=2))
parts=['# B15 review tables','Computed remotely from preserved result tables; no new rules or parameter search.']
def table(title,z,cols=None):
 parts.extend(['## '+title,(z[cols]if cols else z).to_markdown(index=False,floatfmt='.6f')])
main=x[(x.window=='main2020')&(x.kind=='hit')].copy();non=x[(x.window=='main2020')&(x.kind=='nonhit')].set_index('id');base=x[(x.window=='main2020')&(x.kind=='valid_S0')].set_index('id');main['nonhit_mean']=main.id.map(non['mean']);main['valid_S0']=main.id.map(base['mean']);main=main.merge(cov[cov.window=='main2020'].drop(columns=['window']),on='id')
price_rows=[]
for window,mask in [('full',d.next_open.notna()),('main2020',d.next_open.notna()&d.date.ge('2020-01-01')),('early2020_2023',d.next_open.notna()&d.date.ge('2020-01-01')&d.date.lt('2024-01-01')),('recent2024',d.next_open.notna()&d.date.ge('2024-01-01'))]:
 g=d[mask];price_rows.append(dict(window=window,n=len(g),raw_price_gap_cash=g.price_gross_cash.sum(),raw_price_gap_mean_pct=(100*(g.close-g.next_open)/g.close).mean(),economic_gross_cash=g.economic_gross_cash.sum(),economic_gross_mean_pct=g.gross.mean(),missed_dividend_cash=(g.price_gross_cash-g.economic_gross_cash).sum(),slippage_cash=(g.economic_gross_cash-g.cash-g.fee).sum(),fees_cash=g.fee.sum(),net_cash=g.cash.sum(),net_mean_pct=g.net.mean()))
pd.DataFrame(price_rows).to_csv(R/'price_space_summary.csv',index=False)
table('S0 price space versus net increment',pd.DataFrame(price_rows))
table('Final drawdowns',ac[ac.id.isin(['S0','S1_F1','S2_F2'])&ac['mode'].eq('conservative')&ac.settlement.eq('ex_date_close_scenario')],['id','buffer','mdd_pct','hold_mdd_pct','relative_mdd_cash'])
table('All conditional main results',main,['id','n','unknown','mean','cash','nonhit_mean','valid_S0','increment','ci_low','ci_high','inc_low','inc_high'])
table('All conditional early/recent',x[(x.window.isin(['early2020_2023','recent2024']))&(x.kind=='hit')],['id','window','n','mean','cash'])
table('All rules annual',x[(x.window.astype(str).str.fullmatch(r'\d{4}'))&(x.kind=='hit')],['id','window','n','mean','cash'])
table('Endpoint pressures',st[st.kind.isin(['sell1455','buy0935','joint'])],['id','kind','n','mean','cash','excluded','matched_own_base','paired_S0_n','paired_S0','increment'])
table('Cost pressures10/20bp',st[st.kind.eq('slip')&st.value.isin([10,20])&st.window.eq('main2020')],['id','value','n','mean','cash'])
table('Conservative opportunity',st[st.kind.eq('conservative_repurchase')],['id','n','mean','cash','unresolved','sell_restricted','delayed','max_missing_days','max_extra_cash'])
table('Events summary',ev.groupby('id').agg(events=('event','count'),min_leave_event_mean=('remaining_mean','min'),max_leave_event_mean=('remaining_mean','max'),max_event_cash=('event_cash','max'),min_event_cash=('event_cash','min')).reset_index())
table('Symmetric trims by return',trim[trim['sort'].eq('net')],['id','k','delete','n','mean','cash'])
table('Dividend/cash sensitivities',ac[ac.id.isin(['S0','S1_F1','S1_F2','S1_F3','S1_F4','S1_F5','S1_F6','S1_F7','S1_F8','S2_F1','S2_F2','S2_F3','S2_F4','S2_F5','S2_F6'])],['id','buffer','mode','settlement','sales','completed','increment_cash','increment_pct','terminal_missing','terminal_cash_gap','max_extra_cash_required','max_consecutive_deficit_days'])
# Account-year attribution and actual-sell subset, descriptive only.
periods=[];selection=[]
sig=pd.read_csv(R/'signals.csv',parse_dates=['date'])
for name in sig.columns[1:]:
 z=pd.read_csv(R/f'account_{name}_30_restricted.csv',parse_dates=['date'])
 z['change_relative']=z.relative_equity.diff().fillna(z.relative_equity.iloc[0])
 for year,g in z.groupby(z.date.dt.year):
  periods.append(dict(id=name,year=year,increment_cash=g.change_relative.sum(),sales=int(g.sell_quantity.gt(0).sum()),buys=int(g.buy_quantity.gt(0).sum()),end_missing=int(1000-g.shares.iloc[-1]),tax=g.dividend_tax_paid.sum(),fees=g.fees.sum()))
 sold=set(z.loc[z.sell_quantity.gt(0),'date']);h=d.date.isin(sig.loc[sig[name].eq(True),'date'])&d.next_open.notna()&d.date.ge('2020-01-01')
 for typ,mask in [('actually_sold',h&d.date.isin(sold)),('not_sold',h&~d.date.isin(sold))]:
  g=d[mask];selection.append(dict(id=name,subset=typ,n=len(g),nominal_cash=g.cash.sum(),nominal_mean=g.net.mean()))
pd.DataFrame(periods).to_csv(R/'account_annual_attribution.csv',index=False)
pd.DataFrame(selection).to_csv(R/'account_signal_selection.csv',index=False)
table('Account30percent annual attribution',pd.DataFrame(periods))
table('Account30percent actual-sell nominal subset',pd.DataFrame(selection))
# Reference cases for real funding shortage, range limits and corporate cash treatment.
z=pd.read_csv(R/'account_S0_0_restricted.csv');problem=z[z.restoration_missing_shares.gt(0)].head(5);table('S0 zero cash first deficit cases',problem)
con=pd.read_csv(R/'conservative_opportunities.csv');table('Conservative delayed cases',con[con.days_missing.gt(1)].head(12))
table('S0 corporate and break attribution',desc[desc.id.eq('S0')]);table('Primary source results',pd.DataFrame(source).drop(columns=['text_excerpt','sha256'],errors='ignore'))
(R/'REVIEW_TABLES.md').write_text('\n\n'.join(parts))
if (R/'failure.txt').exists():(R/'failure.txt').rename(R/'first_run_failure.txt')
(R/'verification_summary.json').write_text(json.dumps(dict(source_run=source_run,source_code_sha=source_sha,verification_run=os.environ['GITHUB_RUN_ID'],verification_code_sha=os.environ['GITHUB_SHA'],input_manifest_verified=True,accounts_independently_verified=len(checks),primary_matches=sum(s['status']=='amount_and_ex_pay_table_matched'for s in source),primary_failures=[s['ex_date']for s in source if s['status']=='unverified']),indent=2))
(R/'manifest.json').write_text(json.dumps(dict(code_sha=source_sha,run_id=source_run,verification_sha=os.environ['GITHUB_SHA'],verification_run_id=os.environ['GITHUB_RUN_ID'],inputs=man['inputs'],files={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in R.rglob('*')if p.is_file()and p.name!='manifest.json'}),indent=2))
print((R/'verification_summary.json').read_text())
