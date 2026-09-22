"""Final R1 independent persisted-order checks and reviewable attribution."""
import os,json,hashlib,subprocess,io,zipfile
from pathlib import Path
import pandas as pd
import numpy as np
import foxconn_overnight_sell_b15_r1 as r1
P=r1.P;R=r1.R
assert os.environ.get('GITHUB_ACTIONS')=='true'
man=json.loads((R/'manifest.json').read_text())
for path,h in man['files'].items():assert r1.sha(path)==h,path
parent=json.loads((P/'manifest.json').read_text())
for path,h in parent['files'].items():assert r1.sha(path)==h,path
ac=pd.read_csv(R/'account_summary.csv');d=pd.read_csv(P/'daily_ledger.csv',parse_dates=['date','exit_date']);ds=d.set_index('date')
with zipfile.ZipFile('research/foxconn_t0_20260913/source/601138-full-5min-history.zip')as z:m=pd.read_csv(z.open(next(n for n in z.namelist()if n.endswith('601138_5min_all.csv'))))
m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');pm=m[m.clock.eq('09:45')].set_index('date').open
checks=[]
for _,s in ac.iterrows():
 o=r1.readorders(R/f'orders_{s.scenario}.csv');z=pd.read_csv(R/f'account_{s.scenario}.csv',parse_dates=['date']);slip=s.slip_bp/10000;last_sale=None;balance=s.initial-1000*d[d.date.ge('2020-01-01')].close.iloc[0];shares=1000
 r1.independent(z,o,s.buffer,d)
 for _,row in o.iterrows():
  if row.side=='SELL':
   assert shares==1000;last_sale=row.date;shares-=row.quantity;ref=ds.loc[row.date,'close'];sign=-1
  else:
   # Check the execution timestamp from episode age and fixed rule, independent of full-day QC.
   i=int(d.index[d.date.eq(row.date)][0]);prev=d.date.iloc[i-1]
   first=last_sale==prev
   expect='09:40'if s.first_window=='post0935'and first else'09:25'
   assert row.clock==expect,(s.scenario,row.date,row.clock,expect)
   ref=pm.get(row.date)if expect=='09:40'else ds.loc[row.date,'open'];assert ref<ds.loc[row.date,'limit_up']-.005 and ref>=ds.loc[row.date,'limit_down']-.005
   sign=1;shares+=row.quantity
  assert abs(ref-row.reference)<1e-9
  assert abs(row.value-row.quantity*ref*(1+sign*slip))<1e-6
  transfer=.00002 if row.date<pd.Timestamp('2022-04-29')else .00001
  stamp=(.001 if row.date<pd.Timestamp('2023-08-28')else .0005)if row.side=='SELL'else 0
  fee=max(5,row.value*.0001354)+row.value*(transfer+stamp);assert abs(fee-row.fee)<1e-6
  assert shares==row.shares_after and shares%100==0 and 0<=shares<=1000
 checks.append(dict(scenario=s.scenario,orders=len(o),status='PASS',checks='independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants'))
r1.save('final_order_verification.csv',checks)
# Static refinements must not silently change economic findings from the first R1 run.
prior='54d81b55ee5b48f1502845358fb0b7c1c9893872';subprocess.run(['git','fetch','--depth=1','origin',prior],check=True,capture_output=True)
old=pd.read_csv(io.StringIO(subprocess.check_output(['git','show',prior+':'+str(R/'account_summary.csv')],text=True)))
changed=[]
for c in ac.columns:
 if c not in old.columns:changed.append(c);continue
 if pd.api.types.is_numeric_dtype(ac[c]):same=np.allclose(ac[c],old[c],equal_nan=True,rtol=0,atol=1e-8)
 else:same=ac[c].fillna('').equals(old[c].fillna(''))
 if not same:changed.append(c)
assert not changed,changed
parts=['# R1 final verification and attribution','All arithmetic remains remote. No new scenarios or parameters.']
def table(title,z):parts.extend(['## '+title,z.to_markdown(index=False,floatfmt='.6f')])
table('Final order verification',pd.DataFrame(checks))
dep=pd.read_csv(R/'A_original_dependency_summary.csv');table('A selected original dependencies',dep[dep.account.str.match(r'(S0|S1_F1|S2_F2)_(0|10|30)_(restricted|locked)$')])
# Cash availability changes are not the same as first trading-path divergence.
funding=[];contexts=[]
for rule in ['S1_F1','S0']:
 for first,bp in [('open',5),('open',10),('post0935',5),('post0935',10)]:
  paid=f'{rule}_30_paid_{first}_{bp}';locked=f'{rule}_30_locked_{first}_{bp}'
  oo=r1.readorders(R/f'orders_{paid}.csv');nn=r1.readorders(R/f'orders_{locked}.csv');diff=r1.orderdiff(oo,nn,paid+' versus locked');firstday=diff.date.min()if len(diff)else pd.NaT
  # Exclude accumulated cash_after divergence before actual orders differ.
  physical=diff[(diff['_merge']!='both')|~np.isclose(diff.quantity_old,diff.quantity_new,equal_nan=True)|~np.isclose(diff.value_old,diff.value_new,equal_nan=True)]
  physday=physical.date.min()if len(physical)else pd.NaT
  funding.append(dict(rule=rule,first_window=first,slip_bp=bp,first_order_record_difference=firstday,first_quantity_or_participation_difference=physday,changed_physical_orders=len(physical)))
  if pd.notna(physday):
   i=int(d.index[d.date.eq(physday)][0]);dates=d.date.iloc[max(0,i-1):i+3]
   for key in [paid,locked]:
    z=pd.read_csv(R/f'account_{key}.csv',parse_dates=['date']);g=z[z.date.isin(dates)].copy();g.insert(0,'scenario',key);contexts.append(g[['scenario','date','cash','receivable','shares','buy_quantity','sell_quantity','restoration_missing_shares','relative_equity']])
r1.save('C_payment_path_divergence.csv',funding);r1.save('C_payment_divergence_cases.csv',pd.concat(contexts,ignore_index=True));table('C paid versus locked trading divergence',pd.DataFrame(funding));table('C payment first divergence cases',pd.concat(contexts,ignore_index=True))
# Detailed causal repair examples for the large S2 locked-path difference.
for key in ['S0_0_paid_open_5','S2_F2_30_locked_open_5']:
 oldkey='S0_0_restricted'if key.startswith('S0')else'S2_F2_30_locked';oo=r1.readorders(P/f'orders_{oldkey}.csv');nn=r1.readorders(R/f'orders_{key}.csv');diff=r1.orderdiff(oo,nn,key);first=diff.date.min();g=diff[diff.date.le(first+pd.Timedelta(days=5))]
 table('A first repair divergence '+key,g)
y=pd.read_csv(R/'account_year_attribution.csv');table('S1_F1 paid annual attribution',y[y.scenario.str.contains('S1_F1_30_paid')]);table('S1_F1 locked annual attribution',y[y.scenario.str.contains('S1_F1_30_locked')])
ev=pd.read_csv(R/'account_original_event_attribution.csv');table('S1_F1 paid largest negative original events',ev[ev.scenario.str.contains('S1_F1_30_paid')].sort_values('increment_cash').groupby('scenario').head(3));table('S1_F1 paid largest positive original events',ev[ev.scenario.str.contains('S1_F1_30_paid')].sort_values('increment_cash',ascending=False).groupby('scenario').head(3))
pe=pd.read_csv(R/'C_post0935_price_evidence.csv');table('C independently mismatching price cases',pe[pe.price_status.eq('disagrees_with_qualified_1m')])
b=pd.read_csv(R/'B_all_valid_date_quality.csv');table('B matched/unmatched1m aggregate',b[b.original_signal.notna()].groupby(['fine_qualified','original_signal']).agg(n=('date','size'),mean=('original_net','mean'),cash=('original_cash','sum')).reset_index());table('B QC flag counts on original411',pd.DataFrame([dict(flag=c,count=int(b.loc[b.original_signal.eq(True),c].sum()))for c in ['endpoint_good','high_bad','low_bad','volume_bad','strict','fine_qualified']]))
summary=dict(main_run=man['run_id'],main_code_sha=man['code_sha'],verification_run=os.environ['GITHUB_RUN_ID'],verification_code_sha=os.environ['GITHUB_SHA'],verified_accounts=len(checks),parent500_hashes_unchanged=True,first_R1_result=prior,economic_account_summary_unchanged=True,first_vs_final_changed_summary_columns=changed)
r1.js('final_verification.json',summary);(R/'FINAL_REVIEW.md').write_text('\n\n'.join(parts));man.update(verification_run=os.environ['GITHUB_RUN_ID'],verification_code_sha=os.environ['GITHUB_SHA'],files={str(p):r1.sha(p)for p in R.rglob('*')if p.is_file()and p.name!='manifest.json'});r1.js('manifest.json',man);print(json.dumps(summary),flush=True)
