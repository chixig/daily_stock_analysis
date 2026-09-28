#!/usr/bin/env python3
"""Fresh-process independent account reconciliation and report tables."""
import os,json,inspect,functools,subprocess,traceback,zipfile
from pathlib import Path
import numpy as np,pandas as pd
import foxconn_b19 as x
b=x.b;R=x.R

def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true'
 original=json.loads((R/'manifest.json').read_text())['files']
 for p,h in original.items():assert b.sha(p)==h,p
 parents=json.loads((R/'frozen_input_hashes.json').read_text())['files']
 for p,h in parents.items():assert b.sha(p)==h,p
 extra=[b.old.P/'source/601138-full-5min-history.zip',b.r1.B13/'tdx_recovered_1m.csv',b.old.B2/'source/sse_index.csv']
 for p in extra:
  subprocess.run(['git','diff','--exit-code','524c7cd31f8fc8200288bd85596c1c6806ec6f9d','--',str(p)],check=True);parents[str(p)]=b.sha(p)
 d=pd.read_csv(b.P/'daily_ledger.csv',parse_dates=['date','exit_date']);events=json.loads((b.b16.R/'verified_events.json').read_text());schedule=b.b16.schedule_for(d,events,0)
 # Independent inherited verifier uses its own fee and FIFO tax definitions.
 src=inspect.getsource(b.b17.verify).replace("d.date.ge('2020-01-01')","d.date.ge(VERIFY_START)")
 src=src.replace(' def rate(a,b):',' @functools.lru_cache(maxsize=None)\n def rate(a,b):')
 src=src.replace("for (_,r),(_,zr) in zip(d[d.date.ge(VERIFY_START)].iterrows(),z.iterrows()):","for r,zr in zip(d[d.date.ge(VERIFY_START)].itertuples(index=False),z.itertuples(index=False)):")
 src=src.replace(' cash=initialcash;holdcash=initialcash;', ' indices=dict(zip(d.date,d.index))\n cash=initialcash;holdcash=initialcash;').replace("i=int(d.index[d.date.eq(day)][0])","i=indices[day]")
 src=src.replace('for _,x in dayorders.iterrows():','for x in dayorders.itertuples(index=False):')
 scope=dict(b.b17.__dict__);scope.update(functools=functools,VERIFY_START='2020-01-01');exec(src,scope)
 summary=pd.read_csv(R/'account_summary.csv');checked=[]
 supplemental=[]
 for key in ['H00','H01','H03']:
  t=pd.read_csv(R/f'trades/main/{key}_5.csv',parse_dates=['entry','exit']);t=t[t.entry.ge('2024-01-01')].reset_index(drop=True)
  for bp in [5,11,20]:
   x.ns['ACCOUNT_START']='2020-01-01';z,o,tt,ff,met=x.account(d,t,3000,bp/10000,schedule);x.audit(d,z,o,tt,met)
   stats=b.stats(tt.loc[tt.exit_i.notna(),'cash_increment'],tt.loc[tt.exit_i.notna(),'net_pct'])
   supplemental.append(dict(id=key,group='annual_baseline',bp=bp,**met,**{'trade_'+k:v for k,v in stats.items()}))
   tag=f'annual_baseline/{key}_{bp}';x.save('accounts/'+tag+'.csv.gz',z);x.save('orders/'+tag+'.csv.gz',o);x.save('trades/'+tag+'.csv',tt);x.save('funds/'+tag+'.csv.gz',ff)
 x.save('supplemental_account_summary.csv',supplemental);summary=pd.concat([summary,pd.DataFrame(supplemental)],ignore_index=True)
 for a in summary.itertuples():
  p=R/f'accounts/{a.group}/{a.id}_{int(a.bp)}.csv.gz'
  if not p.exists():continue
  z=pd.read_csv(p,parse_dates=['date']);o=pd.read_csv(R/f'orders/{a.group}/{a.id}_{int(a.bp)}.csv.gz',parse_dates=['date','entry']);tt=pd.read_csv(R/f'trades/{a.group}/{a.id}_{int(a.bp)}.csv',parse_dates=['entry','exit']);ff=pd.read_csv(R/f'funds/{a.group}/{a.id}_{int(a.bp)}.csv.gz')
  dd=d[d.date.le(z.date.max())];scope['VERIFY_START']=str(z.date.min().date());scope['verify'](dd,z,o,3000,a.bp/10000,0.,schedule)
  assert abs(z.relative.iloc[-1]-a.increment)<1e-5
  assert len(tt[tt.exit_i.notna()])==a.completed and (tt.cash_increment>0).sum()==a.trade_wins
  if a.group=='main':
   if a.bp==5:ref=tt[['entry_i','exit_i','buy_ref','buy_clock']]
   else:
    ref=pd.read_csv(R/f'trades/main/{a.id}_5.csv')[['entry_i','exit_i','buy_ref','buy_clock']]
    pd.testing.assert_frame_equal(tt[ref.columns].reset_index(drop=True),ref.reset_index(drop=True),check_dtype=False)
  checked.append(dict(id=a.id,group=a.group,bp=a.bp,orders=len(o),days=len(z),status='PASS'))
  if len(checked)%50==0:print('VERIFIED',len(checked),flush=True)
 x.save('independent_accounts_verified.csv',checked)
 # Cash does not change entry/exit decisions or economic relative return.
 key='H01';tt=pd.read_csv(R/f'trades/main/{key}_5.csv',parse_dates=['entry','exit']);x.ns['ACCOUNT_START']='2020-01-01'
 zz,oo,tr,ff,s=x.account(d,tt,3000,.0005,schedule,initialcash=200000.)
 a=summary[(summary.group=='main')&summary.id.eq(key)&summary.bp.eq(5)].iloc[0];assert abs(a.increment-s['increment'])<1e-5
 # Future mutation, recomputed S1 feature masks, never affects past signals.
 with zipfile.ZipFile(b.old.P/'source/601138-full-5min-history.zip') as z:m=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('601138_5min_all.csv'))))
 m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
 ixraw=pd.read_csv(b.old.B2/'source/sse_index.csv',parse_dates=['date']).set_index('date').close;ix=d.date.map(ixraw)
 before,_,features=b.signals(d,m,ix);changed=d.copy();cut=pd.Timestamp('2024-01-01');future=d.date.ge(cut);changed.loc[future,['open','high','low','close','volume','preclose']]*=1.71
 altered,_,f2=b.signals(changed,m,ix)
 for key in before:pd.testing.assert_series_equal(before[key][~future],altered[key][~future])
 f_saved=pd.read_csv(b.R/'features.csv')
 for col in ['S1_r20','S1_market20','S1_clv','S1_vr','S1_r3']:np.testing.assert_allclose(features[col],f_saved[col],equal_nan=True)
 # Path causality: modifying future bars after any completed fill cannot change it.
 days=b.lookup_days(m);reg=x.registry();specs={a['path']:a for a in reg};nperturb=0
 for key,spec in specs.items():
  p=pd.read_csv(R/f'paths/{key}.csv',parse_dates=['entry','exit'])
  for tr in p[(p.exit_i==p.entry_i+1)&p.entry.ge('2024-01-01')].head(3).itertuples():
   rr=d.iloc[int(tr.exit_i)];bars={k:dict(v) for k,v in days.get(rr.date,{}).items()}
   fill,_,_=x.first_buy(tr.sell_ref,rr,bars,spec)
   if fill is None:continue
   for clock,bar in bars.items():
    if clock>b.minutes_after(fill[0],5):
     for field in ['open','close','high','low']:bar[field]*=1.71
   again,_,_=x.first_buy(tr.sell_ref,rr,bars,spec);assert fill==again;nperturb+=1
 # Cross-year entry rule retained: actual saved fixed paths spanning year ends.
 cross=[]
 for key in ['H00','H01']:
  p=pd.read_csv(R/f'paths/{next(a["path"] for a in reg if a["id"]==key)}.csv',parse_dates=['entry','exit'])
  g=p[p.entry.dt.year.ne(p.exit.dt.year)&p.exit.notna()]
  for tr in g.itertuples():
   spec=next(a for a in reg if a['id']==key);rr=d.iloc[int(tr.entry_i)+1];fill,_,_=x.first_buy(tr.sell_ref,rr,days.get(rr.date,{}),spec)
   if fill and int(tr.exit_i)==int(tr.entry_i)+1:assert fill[0]==tr.buy_clock and abs(fill[1]-tr.buy_ref)<1e-9
   cross.append(dict(rule=key,entry=tr.entry,exit=tr.exit,attached_path=tr.path))
 x.save('cross_year_paths_verified.csv',cross)
 # Synthetic missing window and locked-open retries, including an unresolved liability.
 sd=pd.DataFrame(dict(date=pd.to_datetime(['2023-12-29','2024-01-02','2024-01-03','2024-01-04']),open=[100.,100.,110.,101.],close=[100.,100.,100.,101.],limit_down=[90.]*4,limit_up=[110.]*4,dividend_today=[0.]*4,volume=[100.]*4))
 sm=pd.DataFrame(columns=['date','clock','open','close']);orig=b.first_buy;b.first_buy=x.first_buy
 sp=dict(kind='adaptive',gap=None,tp=None,stop=None,deadline='13:30',path='test_missing')
 pp,_=b.build_paths(sd,sm,sp);assert int(pp.loc[0,'exit_i'])==3 and pp.loc[0,'kind']=='forced_open_retry'
 pending,_=b.build_paths(sd.iloc[:3],sm,sp);assert pd.isna(pending.loc[0,'exit_i'])
 b.first_buy=orig
 x.ns['ACCOUNT_START']='2023-01-01';t=pending.loc[[0]].reset_index(drop=True)
 zz,oo,tr,ff,met=x.account(sd.iloc[:3],t,3000,.0005,{})
 assert met['pending']==1 and met['terminal_missing']==1000 and met['increment']<0
 assert abs(met['increment']-(tr.sale_net.iloc[0]-1000*sd.close.iloc[2]))<1e-6
 x.ns['ACCOUNT_START']='2020-01-01'

 # A bar whose high/low cross both thresholds but close crosses neither does not trigger.
 from types import SimpleNamespace
 rr=SimpleNamespace(open=100.,limit_down=90.,limit_up=110.);bars={c:dict(open=100.,close=100.,high=105.,low=95.) for c in x.ENDS}
 fill,_,reason=x.first_buy(100.,rr,bars,dict(kind='adaptive',gap=None,tp=.005,stop=.005,deadline='10:00'));assert fill[0]=='10:00' and reason=='deadline'
 x.js('independent_validation.json',dict(status='PASS',accounts=len(checked),checks=['all saved accounts independently FIFO/fee/dividend/stock/cash verified','5/11/20bp same orders','positive initial cash invariance','future daily data mutation','future bars after execution mutation','high/low conflict cannot substitute for completed close','cross-year fixed paths retain entry rule','missing windows and locked retry preserve pending marked liability','parent/source hashes and original manifest unchanged'],future_path_mutations=nperturb,cross_year_cases=len(cross),parent_files=len(parents)))
 x.js('source_hashes_verified.json',dict(parent='524c7cd31f8fc8200288bd85596c1c6806ec6f9d',files=parents))
 report(summary,reg)
 for p,h in original.items():assert b.sha(p)==h,p
 x.js('verification_manifest.json',dict(files={str(p):b.sha(p) for p in sorted(R.rglob('*')) if p.is_file() and str(p) not in original and p.name not in ['verification_manifest.json','finalize.log','finalize_failure.json']}))
 print('FINALIZER COMPLETE',len(checked),flush=True)

def desc(a):
 if a['id']=='C08':return '旧CLV≥0.8单批，开盘回补'
 if a['kind']=='open':return a['line']+'条件，开盘回补'
 policy=a['policy'];s='不加环境'
 if policy!='all':
  mode,col,sign=policy.split('_');s=('仅' if mode=='filter' else '切换：')+('个股' if col=='r20' else '指数')+'20日'+('非负' if sign=='pos' else '负')+('参与' if mode=='filter' else '用候选、其余开盘')
 if a['line']=='H00':return s+'；'+a['deadline']+'前回补；'+('无上涨保护' if a['stop'] is None else f'涨{100*a["stop"]:g}%触发')
 return ('不设低开立即买' if a['gap'] is None else f'低开{100*a["gap"]:g}%立即买')+f'；跌{100*a["tp"]:g}%目标；涨{100*a["stop"]:g}%触发；{a["deadline"]}截止'

def report(s,reg):
 main=s[(s.group=='main')&s.bp.eq(5)].set_index('id');leaders=pd.read_csv(R/'top3_per_objective.csv');selection=pd.read_csv(R/'annual_selection.csv');rules={a['id']:a for a in reg}
 top=list(dict.fromkeys(leaders.id));best=list(dict.fromkeys(leaders[leaders['rank'].eq(1)].id));periods=pd.read_csv(R/'periods.csv');neigh=pd.read_csv(R/'adjacent_actions.csv');attr=pd.read_csv(R/'attribution.csv');early=s[s.group.eq('early')];fine=pd.read_csv(R/'fine_path_replay.csv')
 compare=[]
 # The descriptive win champion is checked without a profit filter.
 for line in ['H00','H01']:
  eligible=main[main.index.isin([a['id'] for a in reg if a['line']==line and not a.get('baseline_only')])&main.completed.ge(40)]
  winner=eligible.reset_index().sort_values(['trade_win','increment','id'],ascending=[False,False,True]).iloc[0].id
  assert winner==leaders[(leaders.line==line)&(leaders.objective=='win')&(leaders['rank']==1)].iloc[0].id
 for key,a in rules.items():
  row=main.loc[key];base=main.loc[a['line']] if a['line'] in main.index else main.loc['C08'];h03=main.loc['H03']
  compare.append(dict(id=key,line=a['line'],rule=desc(a),completed=row.completed,wins=row.trade_wins,win=row.trade_win,net=row.increment,delta_base=row.increment-base.increment,win_delta_base=row.trade_win-base.trade_win,delta_H03=row.increment-h03.increment if a['line']=='H01' else np.nan,win_delta_H03=row.trade_win-h03.trade_win if a['line']=='H01' else np.nan,worst=row.trade_worst,mdd=row.relative_mdd,mean=row.trade_mean,terminal_reserve=row.terminal_tax_reserve))
 comp=x.save('candidate_comparison.csv',compare).set_index('id')
 keys=list(dict.fromkeys(['H00','H01','H03']+best));front=comp.loc[keys].reset_index()[['id','rule','completed','wins','win','net','delta_base','mean','worst','mdd']]
 annual=s[s.group.eq('annual')&s.bp.eq(5)]
 annualrows=[]
 for a in annual.itertuples():
  basekey=a.id.split('_')[1];base=s[(s.group=='annual_baseline')&s.id.eq(basekey)&s.bp.eq(5)].iloc[0]
  annualrows.append(dict(id=a.id,rule='逐年'+a.id,completed=a.completed,wins=a.trade_wins,win=a.trade_win,net=a.increment,delta_base=a.increment-base.increment,mean=a.trade_mean,worst=a.trade_worst,mdd=a.relative_mdd))
 front=pd.concat([front,pd.DataFrame(annualrows)],ignore_index=True)
 blocks=['# B19计算结果审阅稿（模型事实，尚非最终研究判断）','行情截至2026-09-11；全部元为1000股/笔、3000股研究旧仓的成本后相对持有增量；5bp每边另扣历史税费。',front.to_markdown(index=False,floatfmt='.2f')]
 def add(title,df):blocks.extend(['## '+title,df.to_markdown(index=False,floatfmt='.4f') if len(df) else '无记录'])
 add('各目标前3',leaders.merge(comp.reset_index(),on='id'))
 small=comp[comp.completed.lt(40)].sort_values(['win','net'],ascending=False).head(5).reset_index();add('低于40笔线索',small)
 add('成本比较',s[s.group.eq('main')&s.id.isin(keys)][['id','bp','completed','increment','trade_win','trade_worst','relative_mdd','terminal_tax_reserve','deposits','peak_requirement','single_max','minimum_old_shares']])
 add('逐年选择',selection)
 add('同测试时段固定基准',s[s.group.eq('annual_baseline')][['id','bp','completed','increment','trade_win','trade_worst','relative_mdd']])
 add('训练未选中原因统计',pd.read_csv(R/'training_all_candidates.csv').assign(too_few=lambda z:z.completed.lt(40),nonpositive=lambda z:z.increment.le(0)).groupby(['line','test_year']).agg(candidates=('id','size'),too_few=('too_few','sum'),nonpositive=('nonpositive','sum'),pending_excluded=('pending_excluded','max')).reset_index())
 add('分段每笔损益与价格标准化百分比',periods[periods.group.eq('main')&periods.bp.eq(5)&periods.id.isin(keys)][['id','period','n','wins','win','cash','mean_pct','worst']])
 changes=[]
 for a in s[s.group.isin(['main','annual','annual_baseline','combo'])&s.bp.eq(5)&(s.id.isin(keys)|s.group.ne('main'))].itertuples():
  z=pd.read_csv(R/f'accounts/{a.group}/{a.id}_5.csv.gz',parse_dates=['date']);prior=0.
  for year,g in z.groupby(z.date.dt.year):
   val=g.relative.iloc[-1];changes.append(dict(id=a.id,group=a.group,year=year,equity_increment=val-prior,year_end_relative=val,year_end_reserve=g.tax_reserve.iloc[-1],year_end_missing=3000-g.shares.iloc[-1]));prior=val
 x.save('annual_equity_changes.csv',changes);add('日历年连续账户权益变化',pd.DataFrame(changes))
 add('前3相邻参数',neigh)
 add('已登记卖出相邻阈值',s[s.group.eq('signal_neighbor')][['id','completed','increment','trade_win','mean_pct','trade_worst','relative_mdd']])
 fullattr=[]
 for key in [a['id'] for a in reg if not a.get('baseline_only')]:
  baseline=rules[key]['line'];t=pd.read_csv(R/f'trades/main/{key}_5.csv').set_index('entry_i');ref=pd.read_csv(R/f'trades/main/{baseline}_5.csv').set_index('entry_i');both=t.index.intersection(ref.index);removed=ref.loc[ref.index.difference(t.index)]
  buy_improvement=(ref.loc[both,'buy_cost']-t.loc[both,'buy_cost']).sum();tax_improvement=(ref.loc[both,'dividend_tax']-t.loc[both,'dividend_tax']).sum();div_improvement=(ref.loc[both,'missed_dividend']-t.loc[both,'missed_dividend']).sum();reserve_improvement=main.loc[baseline,'terminal_tax_reserve']-main.loc[key,'terminal_tax_reserve'];skip=-removed.cash_increment.sum()
  difference=main.loc[key,'increment']-main.loc[baseline,'increment']
  assert abs(difference-buy_improvement-tax_improvement-div_improvement-reserve_improvement-skip)<1e-5
  fullattr.append(dict(id=key,baseline=baseline,net_change=difference,buy_price_and_fee_improvement=buy_improvement,realized_fifo_tax_improvement=tax_improvement,missed_dividend_improvement=div_improvement,terminal_reserve_improvement=reserve_improvement,skipped_trades_improvement=skip))
 x.save('attribution_full.csv',fullattr)
 add('收益差额完整桥接',pd.DataFrame(fullattr)[pd.DataFrame(fullattr).id.isin(top)])
 add('归因：减少参与与改变回补',attr[attr.id.isin(top)])
 details=pd.read_csv(R/'attribution_trades.csv');add('动作分支与翻转归因',details.groupby(['id','trigger']).agg(n=('entry','size'),change=('change','sum'),loss_to_win=('loss_to_win','sum'),win_to_loss=('win_to_loss','sum')).reset_index())
 add('2018—19已有历史',early[['id','completed','pending','increment','trade_win','mean_pct','delayed','missing_windows','terminal_missing']]);add('2018—19覆盖',pd.read_csv(R/'early_coverage.csv'))
 add('细路径覆盖及差异',fine.groupby(['id','old_trigger']).agg(total=('entry','size'),covered=('covered','sum'),cash_change=('cash_change','sum')).reset_index());add('实际覆盖的非低开路径',fine[fine.covered&fine.old_trigger.ne('observed_gap_then_continuous_open')])
 add('固定组合',s[s.group.eq('combo')][['id','bp','completed','increment','trade_win','trade_worst','relative_mdd','deposits','peak_requirement','single_max']])
 overlap=[]
 h0=pd.read_csv(R/'trades/main/H00_5.csv').set_index('entry_i')
 for key in ['H01','H03']:
  other=pd.read_csv(R/f'trades/main/{key}_5.csv').set_index('entry_i');both=h0.index.intersection(other.index);left=h0.loc[both,'cash_increment'];right=other.loc[both,'cash_increment']
  overlap.append(dict(pair='H00+'+key,shared_sale_dates=len(both),union_sale_dates=len(h0)+len(other)-len(both),opposite_contribution_dates=int(((left>0)&(right<=0)|(left<=0)&(right>0)).sum()),H00_shared_cash=left.sum(),other_shared_cash=right.sum()))
 add('固定组合日期重叠',x.save('combo_overlap.csv',overlap));add('同日反向独立成本核算',pd.read_csv(R/'opposite_direction_regions.csv'))
 add('资金占用',s[s.group.isin(['main','annual','annual_baseline','combo'])&s.bp.eq(5)&(s.id.isin(keys)|s.group.ne('main'))][['id','group','deposits','peak_requirement','single_max','single_p95','longest_relative_deficit_calendar_days','deposit_yuan_days','minimum_old_shares','pending']])
 add('全部主窗候选',comp.reset_index())
 blocks+=['## 独立验证',json.dumps(json.loads((R/'independent_validation.json').read_text()),ensure_ascii=False,indent=2)]
 (R/'REVIEW_DATA.md').write_text('\n\n'.join(blocks)+'\n')

if __name__=='__main__':
 try:run()
 except Exception:
  x.js('finalize_failure.json',dict(traceback=traceback.format_exc()));raise
