#!/usr/bin/env python3
"""B19 bounded optimization; prices and all calculations stay on GitHub Actions."""
import os,json,inspect,itertools,functools,zipfile,traceback,subprocess
from pathlib import Path
import numpy as np,pandas as pd
import foxconn_b18 as b
R=Path('research/foxconn_t0_20260928_b19'); CHECK=[]
def save(n,x):
 p=R/n;p.parent.mkdir(parents=True,exist_ok=True)
 z=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x);z.to_csv(p,index=False);return z
def js(n,x):(R/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def check(x):CHECK.append(x);print('PASS',x,flush=True)
def registry():
 out=[]
 for pi,policy in enumerate(['all']+[a+'_'+c+'_'+sg for a in ['filter','switch'] for c in ['r20','market20'] for sg in ['pos','neg']]):
  for di,deadline in enumerate(['10:30','13:30','14:50']):
   for si,stop in enumerate([None,.01,.02]):
    key='H00' if (pi,di,si)==(0,2,0) else f'R{pi}{di}{si}'
    out.append(dict(id=key,line='H00',policy=policy,kind='adaptive',gap=None,tp=None,stop=stop,deadline=deadline,path=f'R{di}{si}'))
 for gi,gap in enumerate([.005,.01,None]):
  for ti,tp in enumerate([.005,.01]):
   for si,stop in enumerate([.005,.01,.02]):
    for di,deadline in enumerate(['10:00','10:30','11:00']):
     key='H01' if (gi,ti,si,di)==(0,0,1,1) else f'W{gi}{ti}{si}{di}'
     out.append(dict(id=key,line='H01',policy='all',kind='adaptive',gap=gap,tp=tp,stop=stop,deadline=deadline,path=f'W{gi}{ti}{si}{di}'))
 assert len(out)==135 and len({x['id'] for x in out})==135
 for key,line in [('H02','H00'),('H03','H01'),('C08','C08')]:out.append(dict(id=key,line=line,policy='all',kind='open',gap=None,tp=None,stop=None,deadline=None,path='open',baseline_only=True))
 return out
STARTS=[f'{h:02d}:{m:02d}' for h,mins in [(9,range(30,60,5)),(10,range(0,60,5)),(11,range(0,30,5)),(13,range(0,60,5)),(14,range(0,60,5))] for m in mins]
ENDS=[b.minutes_after(x,5) for x in STARTS]
def delayed_start(clock):
 j=ENDS.index(clock)+2
 return STARTS[j] if j<len(STARTS) else None

def first_buy(sell,r,bars,spec):
 if spec['kind']=='open':return b.first_buy(sell,r,bars,dict(kind='open'))
 issues=[];deadline=spec['deadline']
 def at(clock):
  bar=bars.get(b.minutes_after(clock,5));p=float(bar['open']) if bar else np.nan
  if not np.isfinite(p):issues.append('missing_'+clock)
  return (clock,p,'fixed_or_trigger_next_interval') if b.valid(p,r) else None
 if spec.get('gap') is not None and r.open/sell-1<=-spec['gap']:
  x=at('09:30')
  if x:return x,issues,'observed_gap_then_continuous_open'
 for clock in ENDS:
  fill=delayed_start(clock)
  if fill is None or fill>=deadline:break
  bar=bars.get(clock)
  if bar is None:issues.append('missing_observation_'+clock);continue
  p=float(bar['close']);tp=spec.get('tp');st=spec.get('stop')
  hit_target=tp is not None and p<=sell*(1-tp);hit_stop=st is not None and p>=sell*(1+st)
  assert not(hit_target and hit_stop)
  if hit_target or hit_stop:
   x=at(fill)
   if x:return x,issues,'target_close' if hit_target else 'stop_close'
 x=at(deadline)
 if x:return x,issues,'fixed' if spec.get('tp') is None and spec.get('stop') is None else 'deadline'
 x=at('14:50')
 if x:return x,issues,'emergency_1450'
 return None,issues,'next_open_forced_retry'

# Reuse the exact inherited accounting function. Only start date and iteration speed change.
# Runtime source is saved for inspection; no separate financial implementation.
b.old.taxrate=functools.lru_cache(maxsize=None)(b.old.taxrate)
source=inspect.getsource(b.b17.account).replace("d.date.ge('2020-01-01')","d.date.ge(ACCOUNT_START)")
source=source.replace('d.iloc[start:].iterrows()','((r.Index,r) for r in d.iloc[start:].itertuples())')
source=source.replace('z.iterrows()','((r.Index,r) for r in z.itertuples())')
source=source.replace('ff.iterrows()','((r.Index,r) for r in ff.itertuples())')
source=source.replace('ff=pd.DataFrame(funds)',"ff=pd.DataFrame(funds,columns=['date','clock','entry','buy_cost','sale_net','single_gap','cash_before','tax_reserve','receivable','deposit','cumulative_deposit','zero_capital_pool_before'])")
source=source.replace('oo=pd.DataFrame(orders)',"oo=pd.DataFrame(orders,columns=['date','clock','side','quantity','reference','value','fee','tax','deposit','cash','shares','entry'])")
ns=dict(b.b17.__dict__);ns['ACCOUNT_START']='2020-01-01';exec(source,ns);account=ns['account']

def plan(d,mask,paths,start='2020-01-01',capacity=None):
 pending=[];trades=[];needs=[];reasons=[]
 for i,r in ((r.Index,r) for r in d[d.date.ge(start)].itertuples()):
  bought=0
  for t in list(pending):
   if pd.notna(t['exit_i']) and int(t['exit_i'])==i:pending.remove(t);bought+=1
  s=mask.iloc[i]
  if pd.isna(s):reason='unknown_signal'
  elif not s:reason='no_signal'
  elif i==len(d)-1:reason='terminal_no_next_day'
  elif r.close<=r.limit_down+.005 or r.volume<=0:reason='blocked_sale'
  elif capacity is not None and len(pending)+bought>=capacity:reason='inventory_participation'
  else:
   t=paths.loc[i].to_dict();trades.append(t);pending.append(t);needs.append((len(pending)+bought)*1000);reason='sold_1000'
  reasons.append(dict(date=r.date,reason=reason))
 cols=['entry_i','entry','sell_ref','exit_i','exit','buy_ref','buy_clock','kind','trigger','missing_windows','delayed','path']
 return pd.DataFrame(trades,columns=cols),max(needs,default=1000),pd.DataFrame(reasons)

def audit(d,z,o,t,s):
 assert s['stock']==3000 and s['pending']==int(t.exit_i.isna().sum())
 assert o.quantity.eq(1000).all() and z.cash.ge(-1e-6).all()
 assert np.max(np.abs(z.equity-z.hold_equity-z.relative))<1e-6
 if len(o):
  flow=o.assign(ds=np.where(o.side.eq('BUY'),1000,-1000)).groupby('date').ds.sum().reindex(z.date,fill_value=0).cumsum().to_numpy()+3000
  assert np.array_equal(flow,z.shares.to_numpy())
  f=o.apply(lambda x:b.old.sf(x.value,x.date,x.side=='SELL'),axis=1)
  assert np.max(abs(f-o.fee))<1e-6
  cash=o.assign(delta=np.where(o.side.eq('BUY'),-o.value-o.fee,o.value-o.fee-o.tax)+o.deposit).groupby('date').delta.sum().reindex(z.date,fill_value=0).cumsum().to_numpy()+z.payment.cumsum().to_numpy()
  assert np.max(abs(cash-z.cash))<1e-5
 assert abs(s['increment']-(t.cash_increment.sum()-s['terminal_tax_reserve']+sum(x.sale_net-1000*d.close.iloc[-1]-x.missed_dividend for x in t[t.exit_i.isna()].itertuples())))<1e-5

def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true','Remote calculations only'
 R.mkdir(parents=True,exist_ok=True)
 if (R/'failure.json').exists():
  (R/'failures').mkdir(exist_ok=True);(R/'failure.json').rename(R/'failures'/('before_'+os.environ.get('GITHUB_RUN_ID','run')+'.json'))
 reg=registry();save('registry.csv',reg);js('registry.json',reg)
 parent_folders=[b.P,b.b16.R,b.b17.R,b.R]
 raw_sources=[b.old.P/'source/601138-full-5min-history.zip',b.r1.B13/'tdx_recovered_1m.csv',b.old.B2/'source/sse_index.csv']
 subprocess.run(['git','diff','--exit-code','524c7cd31f8fc8200288bd85596c1c6806ec6f9d','--']+[str(p) for p in raw_sources],check=True)
 subprocess.run(['git','diff','--exit-code','524c7cd31f8fc8200288bd85596c1c6806ec6f9d','--']+[str(p) for p in parent_folders],check=True)
 parents={str(p):b.sha(p) for folder in parent_folders for p in folder.rglob('*') if p.is_file()}
 parents.update({str(p):b.sha(p) for p in raw_sources})
 # Historical manifests may include a pre-final tee log. Pin actual bytes at the requested commit.
 discrepancies=[]
 for folder in parent_folders:
  for manifest in folder.rglob('*manifest.json'):
   for p,h in json.loads(manifest.read_text()).get('files',{}).items():
    if Path(p).exists() and b.sha(p)!=h:discrepancies.append(dict(manifest=str(manifest),path=p,declared=h,parent_snapshot=b.sha(p)))
 save('inherited_manifest_discrepancies.csv',discrepancies)
 js('frozen_input_hashes.json',dict(parent_commit='524c7cd31f8fc8200288bd85596c1c6806ec6f9d',files=parents,registry_sha256=b.sha(R/'registry.json'),code_sha256=b.sha(__file__)))
 (R/'inherited_account_runtime.py.txt').write_text(source)
 # Read market data only after immutable candidate registry and input hashes are written.
 d=pd.read_csv(b.P/'daily_ledger.csv',parse_dates=['date','exit_date'])
 with zipfile.ZipFile(b.old.P/'source/601138-full-5min-history.zip') as z:m=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('601138_5min_all.csv'))))
 m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
 f=pd.read_csv(b.R/'features.csv');sig=pd.read_csv(b.R/'signals.csv')
 base={'H00':sig['S1_clv_ge_0p8__AND__S1_vr_le_1'].astype('boolean'),'H01':sig['S1_clv_ge_0p7__AND__S1_r3_le_m4'].astype('boolean'),'C08':sig['S1_clv_ge_0p8'].astype('boolean')}
 events=json.loads((b.b16.R/'verified_events.json').read_text());schedule=b.b16.schedule_for(d,events,0)
 specs={x['path']:x for x in reg};paths={};attempts=[]
 original=b.first_buy;b.first_buy=first_buy_proxy=first_buy
 # b.build_paths calls b.first_buy; open must not recurse through that reference.
 global OPEN_BUY
 OPEN_BUY=original
 for key,spec in specs.items():
  p,a=b.build_paths(d,m,spec);paths[key]=p;attempts.append(a);save('paths/'+key+'.csv',p)
 b.first_buy=original
 save('all_failed_and_missing_attempts.csv',pd.concat(attempts,ignore_index=True))
 def config(a):
  mask=base[a['line']].copy();p=paths[a['path']].copy()
  if a['policy']!='all':
   kind,col,sign=a['policy'].split('_');v=f['S1_'+col];env=(v.ge(0) if sign=='pos' else v.lt(0)).where(v.notna(),False)
   if kind=='filter':mask=mask&env
   else:p.loc[~env.reindex(p.index),:]=paths['open'].loc[~env.reindex(p.index),:]
  return mask,p
 configs={a['id']:config(a) for a in reg};plans={};needs={}
 for a in reg:
  key=a['id'];mask,p=configs[key];t,need,reasons=plan(d,mask,p,capacity=1 if key=='C08' else None);assert need<=3000,(key,need)
  plans[key]=t;needs[key]=need;save('participation/'+key+'.csv.gz',reasons)
 check('138 registered unique candidates; resource plans fixed across costs')
 rows=[];periods=[];cache={}
 def job(key,t,bp=5,dd=d,start='2020-01-01',group='main',persist=True):
  ns['ACCOUNT_START']=start
  z,o,tt,ff,s=account(dd,t,3000,bp/10000,schedule);audit(dd,z,o,tt,s)
  done=tt[tt.exit_i.notna()];stats=b.stats(done.cash_increment,done.net_pct)
  row=dict(id=key,group=group,bp=bp,**s,**{'trade_'+k:v for k,v in stats.items()},missing_windows=int(tt.missing_windows.sum()),delayed=int(tt.delayed.sum()),minimum_old_shares=needs.get(key,3000))
  rows.append(row)
  if persist:
   tag=f'{group}/{key}_{bp}';save('accounts/'+tag+'.csv.gz',z);save('orders/'+tag+'.csv.gz',o);save('trades/'+tag+'.csv',tt);save('funds/'+tag+'.csv.gz',ff)
  for name,select in [('2020-2023',done.entry.lt('2024-01-01'))]+[(str(y),done.entry.dt.year.eq(y)) for y in range(2024,2027)]:
   g=done[select];periods.append(dict(id=key,group=group,bp=bp,period=name,**b.stats(g.cash_increment,g.net_pct),scope='completed episodes grouped by entry; terminal reserve separate'))
  if group=='main' and bp==5:cache[key]=(z,o,tt,ff,row)
  return z,o,tt,ff,row
 expected={'H00':(154,23052.3209344564),'H01':(41,14614.9743356811),'H02':(154,8332.4964663394),'H03':(41,13874.4574622811),'C08':(286,10014.4072574457)}
 for a in reg:
  key=a['id']
  for bp in [5,11]:
   z,o,t,ff,s=job(key,plans[key],bp)
   if bp==5 and key in expected:
    n,v=expected[key];assert s['completed']==n and abs(s['increment']-v)<1e-5,(key,s)
    b.b17.verify(d,z,o,3000,.0005,0.,schedule)
  print('MAIN',key,s['increment'],flush=True)
 save('account_summary.csv',rows);check('all five B18 baseline accounts exactly reproduced and independently reconciled')
 main=pd.DataFrame(rows);main=main[(main.group=='main')&main.bp.eq(5)]
 grid={x['id']:x for x in reg if not x.get('baseline_only')};top=set();leaders=[]
 for line in ['H00','H01']:
  pool=main[main.id.isin([k for k,a in grid.items() if a['line']==line])&main.completed.ge(40)]
  for objective,col in [('profit','increment'),('win','trade_win')]:
   eligible=pool if objective=='profit' else pool[pool.increment.gt(0)]
   pick=eligible.sort_values([col]+(['increment'] if col!='increment' else [])+['id'],ascending=[False]+([False] if col!='increment' else [])+[True]).head(3)
   for rank,x in enumerate(pick.itertuples(),1):top.add(x.id);leaders.append(dict(line=line,objective=objective,rank=rank,id=x.id))
 save('top3_per_objective.csv',leaders)
 # Training scores contain only episodes observably completed by the prior year end.
 # Pending episodes are explicitly excluded, then the closed-episode account is replayed.
 train=[];selections=[]
 for year in [2024,2025,2026]:
  dd=d[d.date.lt(f'{year}-01-01')];last=dd.index[-1];scores=[]
  for key,a in grid.items():
   tt=plans[key];closed=tt[tt.exit_i.notna()&tt.exit_i.le(last)].copy().reset_index(drop=True)
   z,o,t,ff,s=job(key,closed,5,dd=dd,group=f'train{year}',persist=False)
   s={**s,'line':a['line'],'test_year':year,'cutoff':str(dd.date.iloc[-1].date()),'pending_excluded':int((tt.entry_i.le(last)&(tt.exit_i.isna()|tt.exit_i.gt(last))).sum())};scores.append(s)
  frame=pd.DataFrame(scores);train.extend(scores)
  for line in ['H00','H01']:
   pool=frame[frame.line.eq(line)&frame.completed.ge(40)&frame.increment.gt(0)]
   for objective,col in [('profit','increment'),('win','trade_win')]:
    chosen=pool.sort_values([col]+(['increment'] if col!='increment' else [])+['id'],ascending=[False]+([False] if col!='increment' else [])+[True]).iloc[0] if len(pool) else None
    selections.append(dict(line=line,objective=objective,test_year=year,cutoff=str(dd.date.iloc[-1].date()),id=chosen.id if chosen is not None else 'NONE',eligible=len(pool),training_net=chosen.increment if chosen is not None else 0,training_n=int(chosen.completed) if chosen is not None else 0,training_win=chosen.trade_win if chosen is not None else None,reason='highest eligible score; fixed ID tie break' if chosen is not None else 'no positive candidate with >=40 completed trades'))
    if chosen is not None:top.add(chosen.id)
  print('TRAIN',year,selections[-4:],flush=True)
 save('training_all_candidates.csv',train);save('annual_selection.csv',selections)
 for line,obj in itertools.product(['H00','H01'],['profit','win']):
  key='A_'+line+'_'+obj;parts=[]
  for sel in selections:
   if (sel['line'],sel['objective'])==(line,obj) and sel['id']!='NONE':
    t=plans[sel['id']];parts.append(t[t.entry.dt.year.eq(sel['test_year'])].assign(selected_rule=sel['id']))
  t=pd.concat(parts,ignore_index=True) if parts else plans['H01'].iloc[:0].copy()
  for bp in [5,11,20]:job(key,t,bp,group='annual')
 # Fixed same-day priority combinations, defined before results; not an extra search.
 for other in ['H01','H03']:
  p=pd.concat([plans[other],plans['H00'][~plans['H00'].entry_i.isin(plans[other].entry_i)]],ignore_index=True).sort_values('entry_i').reset_index(drop=True)
  for bp in [5,11,20]:job('COMBO_'+other,p,bp,group='combo')
 for key in sorted(top|set(expected)):
  job(key,plans[key],20)
  z,o,t,ff,s=cache[key];b.b17.verify(d,z,o,3000,.0005,0.,schedule)
 # 2018-19 existing history is checked with all fallback days retained; no parameter selection.
 early=d[d.date.lt('2020-01-01')]
 early_keys=set(x['id'] for x in leaders)|{'H00','H01','H03'}
 early_diag=[]
 for key in sorted(early_keys):
  mask,p=configs[key];pe=p.copy();bad=pe.exit_i.gt(early.index[-1]);pe.loc[bad,['exit_i','buy_ref']]=np.nan;pe.loc[bad,'exit']=pd.NaT;pe.loc[bad,'buy_clock']=None
  t,need,_=plan(early,mask,pe,start='2018-01-01');needs[key]=max(needs[key],need);assert need<=3000
  job(key,t,5,dd=early,start='2018-01-01',group='early')
  early_diag.append(dict(id=key,days=len(early),minute_days=m[m.date.lt('2020-01-01')].date.nunique(),trades=len(t),missing_windows=int(t.missing_windows.sum()),fallback_delayed=int(t.delayed.sum())))
 save('early_coverage.csv',early_diag)
 # Nearby signal thresholds are descriptive checks only, not candidate expansion.
 for key in sorted(set(x['id'] for x in leaders)):
  a=grid[key];mask,p=configs[key]
  alternatives=[('vr08',f.S1_vr.le(.8))] if a['line']=='H00' else [('clv08',f.S1_clv.ge(.8)),('clv09',f.S1_clv.ge(.9))]
  for label,extra in alternatives:
   t,need,_=plan(d,mask&extra,p);assert need<=3000
   job(key+'_'+label,t,5,group='signal_neighbor')
 save('account_summary.csv',rows);save('periods.csv',periods)
 neighbors=[]
 for key in sorted(set(x['id'] for x in leaders)):
  a=grid[key];fields=['deadline','stop'] if a['line']=='H00' else ['gap','tp','stop','deadline']
  choices={'deadline':['10:30','13:30','14:50'] if a['line']=='H00' else ['10:00','10:30','11:00'],'stop':[None,.01,.02] if a['line']=='H00' else [.005,.01,.02],'gap':[.005,.01,None],'tp':[.005,.01]}
  for other,c in grid.items():
   if c['line']!=a['line'] or c['policy']!=a['policy']:continue
   dif=[k for k in fields if a[k]!=c[k]]
   if len(dif)==1 and abs(choices[dif[0]].index(a[dif[0]])-choices[dif[0]].index(c[dif[0]]))==1:
    neighbors.append(dict(center=key,neighbor=other,dimension=dif[0],**{k:cache[other][4][k] for k in ['increment','trade_win','completed','trade_worst','relative_mdd']}))
 save('adjacent_actions.csv',neighbors)
 attribution=[];details=[]
 for key in sorted(grid):
  baseline=grid[key]['line'];t=cache[key][2].set_index('entry_i');ref=cache[baseline][2].set_index('entry_i');both=t.index.intersection(ref.index);removed=ref.loc[ref.index.difference(t.index)]
  delta=t.loc[both,'cash_increment']-ref.loc[both,'cash_increment'];flipup=(t.loc[both,'cash_increment']>0)&(ref.loc[both,'cash_increment']<=0);flipdown=(t.loc[both,'cash_increment']<=0)&(ref.loc[both,'cash_increment']>0)
  attribution.append(dict(id=key,baseline=baseline,shared=len(both),removed=len(removed),forgone_positive=float(removed.cash_increment.clip(lower=0).sum()),avoided_negative=float(-removed.cash_increment.clip(upper=0).sum()),same_dates_episode_improvement=float(delta.sum()),loss_to_win=int(flipup.sum()),win_to_loss=int(flipdown.sum()),reserve_change=cache[key][4]['terminal_tax_reserve']-cache[baseline][4]['terminal_tax_reserve']))
  if key in top:
   for i in both:details.append(dict(id=key,entry=t.loc[i,'entry'],trigger=t.loc[i,'trigger'],baseline_trigger=ref.loc[i,'trigger'],cash=t.loc[i,'cash_increment'],baseline_cash=ref.loc[i,'cash_increment'],change=delta.loc[i],loss_to_win=bool(flipup.loc[i]),win_to_loss=bool(flipdown.loc[i])))
 save('attribution.csv',attribution);save('attribution_trades.csv',details)
 # Same dates, independently costed reverse buy-close/sell-next-open diagnostic.
 mirrors=[]
 for col,sign in itertools.product(['r20','market20'],['pos','neg']):
  env=f['S1_'+col].ge(0) if sign=='pos' else f['S1_'+col].lt(0);g=d[base['H00'].fillna(False)&env&d.date.ge('2020-01-01')&d.exit_date.notna()]
  if len(g):
   normal=b.old.ledger(g);reverse=b.old.ledger(g,reverse=True)
   mirrors.append(dict(region=col+'_'+sign,n=len(g),normal_cash=normal.cash.sum(),reverse_cash=reverse.cash.sum(),normal_pct=normal.net.mean(),reverse_pct=reverse.net.mean(),status='nominal costed direction candidate; no continuous account or adoption'))
 save('opposite_direction_regions.csv',mirrors)
 # Qualified 1m replay at identical five-minute observation cadence.
 fine=pd.read_csv(b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);fine['clock']=fine.datetime.dt.strftime('%H:%M');ds=d.set_index('date');fine_days={}
 expected1=[b.minutes_after(s,k) for s in STARTS for k in range(1,6)]
 for day,g in fine.groupby('date'):
  g=g.sort_values('clock').copy()
  if day not in ds.index or list(g.clock)!=expected1:continue
  rr=ds.loc[day]
  if max(abs(g.open.iloc[0]-rr.open),abs(g.close.iloc[-1]-rr.close),abs(g.high.max()-rr.high),abs(g.low.min()-rr.low))>=.011:continue
  if not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))&(g.volume>=0)).all():continue
  g['block']=np.arange(240)//5;agg=g.groupby('block').agg(open=('open','first'),close=('close','last'),clock=('clock','last'));fine_days[day]=agg.set_index('clock').to_dict('index')
 replay=[]
 for key in sorted(set(x['id'] for x in leaders)|{'H00','H01','H03'}):
  for tr in cache[key][2].itertuples():
   rr=d.iloc[int(tr.entry_i)+1];spec=specs[tr.path];covered=rr.date in fine_days;row=dict(id=key,entry=tr.entry,expected_exit=rr.date,old_trigger=tr.trigger,old_clock=tr.buy_clock,old_price=tr.buy_ref,covered=covered)
   if covered:
    fill,issues,reason=first_buy(tr.sell_ref,rr,fine_days[rr.date],spec);row.update(new_trigger=reason,new_clock=fill[0] if fill else None,new_price=fill[1] if fill else np.nan)
    if fill and tr.exit==rr.date:row['cash_change']=1000*(tr.buy_ref-fill[1])*1.0005+b.old.sf(1000*tr.buy_ref*1.0005,rr.date)-b.old.sf(1000*fill[1]*1.0005,rr.date)
   replay.append(row)
 save('fine_path_replay.csv',replay)
 tests(d,m,reg,paths,configs,plans,cache,job)
 for p,h in parents.items():assert b.sha(p)==h,p
 check('parent hashes unchanged')
 js('validation.json',dict(status='PASS',checks=CHECK,candidates=135,fixed_extra_baselines=3,accounts=len(rows),qualified_1m_days=len(fine_days),data_cutoff=str(d.date.max().date()),parent_files=len(parents)))
 js('manifest.json',dict(files={str(p):b.sha(p) for p in sorted(R.rglob('*')) if p.is_file() and p.name not in ['manifest.json','calculation.log','failure.json']}))
 print('COMPLETE',len(rows),flush=True)

def tests(d,m,reg,paths,configs,plans,cache,job):
 from types import SimpleNamespace
 r=SimpleNamespace(open=99.,limit_down=90.,limit_up=110.)
 bars={c:dict(open=100.,close=100.) for c in ENDS};bars['09:35']['open']=99.2
 spec=dict(kind='adaptive',gap=.005,tp=.005,stop=.01,deadline='10:30')
 fill,_,reason=first_buy(100.,r,bars,spec);assert fill[0]=='09:30' and fill[1]==99.2
 r.open=100.;bars['09:35']['close']=99.;bars['09:45']['open']=98.8
 fill,_,reason=first_buy(100.,r,bars,spec);assert fill[:2]==('09:40',98.8) and reason=='target_close'
 bars['09:35']['close']=102.;fill,_,reason=first_buy(100.,r,bars,spec);assert fill[0]=='09:40' and reason=='stop_close'
 assert delayed_start('11:25')=='13:00' and delayed_start('11:30')=='13:05'
 bars={c:dict(open=100.,close=100.) for c in ENDS};bars['11:25']['close']=102.;bars['13:05']['open']=103.
 fill,_,reason=first_buy(100.,r,bars,dict(kind='adaptive',gap=None,tp=None,stop=.01,deadline='13:30'));assert fill[:2]==('13:00',103.)
 bars={c:dict(open=100.,close=100.) for c in ENDS};bars['10:25']['close']=102.
 fill,_,reason=first_buy(100.,r,bars,spec);assert fill[0]=='10:30' and reason=='deadline'
 bars.pop('10:35');fill,issues,reason=first_buy(100.,r,bars,spec);assert fill[0]=='14:50' and reason=='emergency_1450'
 fill,issues,reason=first_buy(100.,r,{},spec);assert fill is None and reason=='next_open_forced_retry'
 check('gap observation, target/stop separate branches, lunch 11:25->13:00 /11:30->13:05, deadline priority, missing recovery')
 # Replay a prefix for every unique exit action; future quotes cannot alter past fills.
 cut=int(d.index[d.date.lt('2024-01-01')][-1]);orig=b.first_buy;b.first_buy=first_buy
 for name,s in {x['path']:x for x in reg}.items():
  p,_=b.build_paths(d.iloc[:cut+1],m[m.date.le(d.date.iloc[cut])],s);ix=p.index[p.exit_i.notna()]
  pd.testing.assert_frame_equal(p.loc[ix,['exit_i','buy_ref','buy_clock']],paths[name].loc[ix,['exit_i','buy_ref','buy_clock']],check_dtype=False)
 b.first_buy=orig
 check('all 64 unique execution actions invariant to future data removal; cross-year exit attached to entry rule')
 # Empty annual track is intentional when H01 lacks 40 earlier episodes.
 check('all accounts cash/share and cost reconciliation; five baselines and all selected finalists independently FIFO verified')

# open implementation captured before temporary dispatch replacement
OPEN_BUY=b.first_buy
_original_first=first_buy
def first_buy(sell,r,bars,spec):
 if spec['kind']=='open':return OPEN_BUY(sell,r,bars,dict(kind='open'))
 return _original_first(sell,r,bars,spec)

if __name__=='__main__':
 try:run()
 except Exception:
  R.mkdir(parents=True,exist_ok=True);js('failure.json',dict(traceback=traceback.format_exc(),checks=CHECK));raise
