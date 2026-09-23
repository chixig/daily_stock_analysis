#!/usr/bin/env python3
"""B17 evidence-consumer checks and reporting; no new strategy parameters."""
import os,json,hashlib,traceback
from pathlib import Path
import numpy as np,pandas as pd
R=Path('research/foxconn_t0_20260923_b17');B=Path('research/foxconn_t0_20260922_b16');P=Path('research/foxconn_overnight_sell_20260921_b15')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 z=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x);z.to_csv(R/n,index=False);return z
def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true'
 man=json.loads((R/'manifest.json').read_text())
 for p,h in man['files'].items():assert sha(p)==h,p
 a=pd.read_csv(R/'account_summary.csv');n=pd.read_csv(R/'nominal_matrix.csv')
 d=pd.read_csv(P/'daily_ledger.csv',parse_dates=['date'])
 attrib=[];periods=[];annualbridge=[];checks=[];concentration=[];pricechecks=[]
 for _,s in a.iterrows():
  key=s.scenario;z=pd.read_csv(R/f'daily_{key}.csv',parse_dates=['date']);o=pd.read_csv(R/f'orders_{key}.csv',parse_dates=['date']);t=pd.read_csv(R/f'trades_{key}.csv',parse_dates=['entry','exit']);f=pd.read_csv(R/f'funding_{key}.csv',parse_dates=['date'])
  assert o.quantity.eq(1000).all()
  buys=o[o.side.eq('BUY')];sells=o[o.side.eq('SELL')]
  trade=float((sells.value-sells.fee-sells.tax).sum()-(buys.value+buys.fee).sum())
  assert abs(z.cash.iloc[-1]-(s.initialcash+z.deposit.sum()+trade+z.payment.sum()))<1e-5
  assert abs(z.relative.iloc[-1]-s.increment)<1e-5
  assert abs(z.equity.iloc[-1]-s.flow_adjusted_absolute_profit-s.stock*d.loc[d.date.ge('2020-01-01'),'close'].iloc[0]-s.initialcash-z.deposit.sum())<1e-5
  assert s.pending==0,('pending requires explicit marked attribution',key)
  pretax=float((t.sale_net+t.dividend_tax-t.buy_cost-t.missed_dividend).sum())
  assert abs(pretax-t.dividend_tax.sum()-z.tax_reserve.iloc[-1]-s.increment)<1e-5
  attrib.append(dict(scenario=key,price_fee_missed_dividend=pretax,fifo_dividend_tax=t.dividend_tax.sum(),terminal_reserve=z.tax_reserve.iloc[-1],net=s.increment))
  # Cash stock conservation independent of summary counters.
  assert s.stock+1000*(len(buys)-len(sells))==z.shares.iloc[-1]
  assert abs(f.deposit.sum()-s.deposits)<1e-5 and abs(s.deposits-max(0,s.peak_requirement-s.initialcash))<1e-5
  # Periods of negative cash against baseline hold, reserve included. No withdrawals implied.
  series=z.relative_cash_pool-z.tax_reserve;start=None;mini=0.;minday=None
  for i,v in enumerate(series):
   if v < -1e-7:
    if start is None:start=i;mini=v;minday=z.date.iloc[i]
    if v<mini:mini=v;minday=z.date.iloc[i]
   elif start is not None:
    periods.append(dict(scenario=key,start=z.date.iloc[start],recovered=z.date.iloc[i],duration_calendar_days=(z.date.iloc[i]-z.date.iloc[start]).days,peak_deficit=-mini,peak_date=minday,open_at_end=False));start=None
  if start is not None:periods.append(dict(scenario=key,start=z.date.iloc[start],recovered=pd.NaT,duration_calendar_days=(z.date.iloc[-1]-z.date.iloc[start]).days,peak_deficit=-mini,peak_date=minday,open_at_end=True))
  vals=t.cash_increment
  # Transaction event attribution, explicitly distinct from old daily carried assignment.
  ev=pd.read_csv(R/'events.csv');ee=ev[ev.scenario.eq(key)]
  best=ee.loc[ee.increment.idxmax()];worst=ee.loc[ee.increment.idxmin()]
  e92=ee[ee.event.eq(92)].increment.sum()
  concentration.append(dict(scenario=key,event92=e92,best_event=best.event,best_cash=best.increment,without_best_event=s.increment-best.increment,worst_event=worst.event,worst_cash=worst.increment,without_worst_event=s.increment-worst.increment))
  pp=buys[buys.date.eq(pd.Timestamp('2026-05-15'))]
  if s.window=='post0935':
   pricechecks.append(dict(scenario=key,traded_disputed_day=bool(len(pp)),reference=float(pp.reference.iloc[0]) if len(pp) else None,alternate_not_adopted=70.44,approx_cash_difference_if_confirmed=(70.60-70.44)*1000*(1+s.bp/10000) if len(pp) else 0.))
  checks.append(dict(scenario=key,status='PASS',cash_shares_flows=True,leg_relative_tax_reconciliation=True))
 save('independent_summary_validation.csv',checks)
 at=save('profit_components.csv',attrib);save('funding_deficit_periods.csv',periods);co=save('concentration.csv',concentration);save('disputed_price_scope.csv',pricechecks)
 # Separate participation/price-cost effects and taxes for same rule/window costs.
 diff=[]
 for rule in ['S0','S1_F1','S2_F2']:
  for w in (['open','post0935'] if rule=='S1_F1' else ['open']):
   for bp in ([5,6,7,10,11,12] if rule=='S1_F1' else [5,10,11,12]):
    x=at[at.scenario.eq(f'{rule}_{w}_{bp}_all')].iloc[0];y=at[at.scenario.eq(f'{rule}_{w}_{bp}_1000')].iloc[0]
    diff.append(dict(rule=rule,window=w,bp=bp,inventory_participation_price_fee_effect=x.price_fee_missed_dividend-y.price_fee_missed_dividend,tax_effect=-(x.fifo_dividend_tax-y.fifo_dividend_tax)-(x.terminal_reserve-y.terminal_reserve),total=x.net-y.net))
 save('inventory_attribution.csv',diff)
 # Old year46 vs2 and full-signal bridge, all years, not only chosen winner.
 ys=pd.read_csv(R/'years.csv')
 for w in ['open','post0935']:
  for bp,base,extra in [(5,5,0),(10,10,0),(11,10,1),(12,10,2)]:
   oo=pd.read_csv(B/f'orders_S1_F1_{w}_b{base}_e{extra}_d0_'+('main' if extra==0 else 'extra_cost')+'.csv',parse_dates=['date'])
   for year in range(2020,2027):
    annualbridge.append(dict(window=w,bp=bp,year=year,old_sales=int((oo.side.eq('SELL')&oo.date.dt.year.eq(year)).sum()),old_partial_buy_orders=int((oo.side.eq('BUY')&oo.quantity.lt(1000)&oo.date.dt.year.eq(year)).sum()),corrected1000_sales=int(ys.loc[ys.scenario.eq(f'S1_F1_{w}_{bp}_1000')&ys.year.eq(year),'sales'].iloc[0]),corrected_all_sales=int(ys.loc[ys.scenario.eq(f'S1_F1_{w}_{bp}_all')&ys.year.eq(year),'sales'].iloc[0])))
 save('year_participation_bridge.csv',annualbridge)
 # A compact self-contained Chinese data appendix; no current market assertions.
 text=['## 计算表附录','以下均为截至2026-09-11的固定历史模型结果，金额为元，百分比为每笔现金增量÷当次1000股卖出参考收价；不是账户年化。all表示满足全部可参与信号的库存路径，1000表示仅1000股底仓对照。']
 def table(title,x):text.extend(['### '+title,x.to_markdown(index=False,floatfmt='.4f')])
 bl=pd.read_csv(R/'all_rules_baseline.csv');main=bl[(bl.window=='main')&(bl.kind=='hit')][['rule','n','mean','cash']].copy()
 valid=bl[(bl.window=='main')&(bl.kind=='valid_S0')].set_index('rule')
 main['同有效日期S0均净%']=main.rule.map(valid['mean']);main['改善百分点']=main['mean']-main['同有效日期S0均净%']
 table('全部原规则：主窗5bp开盘独立机会',main)
 pivot=bl[bl.kind.eq('hit')&bl.window.isin(['full','early','recent'])].copy()
 pivot['N/均净%/现金']=pivot.apply(lambda r:f"{int(r.n)}/{r.get('mean',float('nan')):.4f}/{r.cash:.2f}" if r.n else '不可计算',axis=1)
 table('全部原规则：全历史、早期与近期',pivot.pivot(index='rule',columns='window',values='N/均净%/现金').reset_index())
 yearly=bl[bl.kind.eq('hit')&bl.window.str.match(r'^\d{4}$')].copy()
 yearly['N/均净%/现金']=yearly.apply(lambda r:f"{int(r.n)}/{r['mean']:.4f}/{r.cash:.2f}" if r.n else '不可计算',axis=1)
 table('全部原规则：逐年独立机会（2026为部分年度）',yearly.pivot(index='rule',columns='window',values='N/均净%/现金').reset_index())
 table('固定成本与时点：名义机会',n[['scenario','n','mean','cash']])
 table('固定1000股连续路径',a[['scenario','stock','signals','sales','completed','t1_skip','occupied_skip','sale_blocked','first_window_unavailable','increment','mean_pct','fees','tax_paid']])
 table('资金需求（初始额外现金0，利润及调入款留存）',a[['scenario','single_median','single_p95','single_max','single_max_date','deposits','peak_date','peak_pct_1000_value','additional_over_5514','longest_relative_deficit_calendar_days']])
 table('S1_F1逐年连续路径增量',ys[ys.scenario.str.startswith('S1_F1')].pivot(index='scenario',columns='year',values='increment').reset_index())
 table('旧新11bp桥接',pd.read_csv(R/'old_new_bridge.csv'))
 table('库存参与变化与权益税费拆分',pd.DataFrame(diff))
 table('事件集中及对称反证',co)
 table('单笔对称尾部删除诊断',pd.read_csv(R/'symmetric_tails.csv'))
 table('支付日短延迟影响摘要',pd.read_csv(R/'payment_delay_proof.csv').groupby('delay')[['delta_deposit']].agg(['min','max']).reset_index())
 table('新路径09:40争议价覆盖',pd.DataFrame(pricechecks))
 (R/'REPORT_TABLES.md').write_text('\n\n'.join(text))
 # Preserve first manifest, then close hashes including completed calculation log.
 (R/'calculation_manifest.json').write_text(json.dumps(man,ensure_ascii=False,indent=2))
 result=dict(status='PASS',accounts=len(checks),code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],checks=['parent manifest','all order quantities1000','cash/shares and equal external flows','per-leg dividend-tax reconciliation','historical funding min and deposits','all pending explicitly zero','inventory vs tax decomposition'],limitations=['real auction capacity unknown','09:40 indicative unverified','S2 signal quality remains unresolved'])
 (R/'final_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 final=dict(parent='86ceac2137830b28ca7b97c3218654adf0b5931a',code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],files={str(p):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='manifest.json'})
 (R/'manifest.json').write_text(json.dumps(final,ensure_ascii=False,indent=2))
 print(json.dumps(result))
if __name__=='__main__':
 try:run()
 except Exception:
  (R/('verify_failure_'+os.environ.get('GITHUB_RUN_ID','unknown')+'.txt')).write_text(traceback.format_exc());raise
