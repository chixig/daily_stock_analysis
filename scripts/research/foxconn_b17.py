#!/usr/bin/env python3
"""B17: fixed quantity, externally funded; remote-only immutable evidence."""
import os,json,hashlib,zipfile,sys,traceback
from pathlib import Path
import numpy as np,pandas as pd
import foxconn_overnight_sell_b15 as old
import foxconn_overnight_sell_b15_r1 as r1
import foxconn_b16_accounts as b16
P=r1.P; B=b16.R; R=Path('research/foxconn_t0_20260923_b17')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 z=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x);z.to_csv(R/name,index=False);return z
def js(name,x):(R/name).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
CHECK=[]
def check(s,detail=''):CHECK.append(dict(test=s,status='PASS',detail=detail))
def plan(d,mask,op,post,window,capacity=None):
 """Chronological resource-only scheduler; no cash, slippage, or future QC."""
 pending=[];trades=[];reasons=[];needs=[];attempts=[]
 for i,r in d[d.date.ge('2020-01-01')].iterrows():
  bought=0
  for t in list(pending):
   windows=post[i] if window=='post0935' and i==t['entry_i']+1 else op[i]
   if not windows:
    attempts.append(dict(entry=t['entry'],date=r.date,status='unavailable_open_or_proxy',first=i==t['entry_i']+1))
    continue
   clock,p,kind=windows[0]
   t.update(exit_i=i,exit=r.date,buy_ref=p,buy_clock=clock,kind=kind)
   pending.remove(t);bought+=1
  sig=mask.iloc[i]
  if pd.isna(sig):reason='signal_unknown'
  elif not bool(sig):reason='no_signal'
  elif pd.isna(r.exit_date):reason='terminal_signal_no_next_day'
  elif not np.isfinite(r.close) or r.volume<=0:reason='sale_data_or_no_volume'
  elif r.close<=r.limit_down+.005:reason='sale_lower_limit'
  elif capacity is not None and len(pending)+bought>=capacity:reason='T1_inventory' if bought else 'inventory_occupied_unfilled'
  else:
   need=len(pending)+bought+1
   needs.append(dict(date=r.date,minimum_old_shares=1000*need,outstanding_before=len(pending),bought_today=bought))
   t=dict(entry_i=i,entry=r.date,sell_ref=float(r.close),exit_i=None,exit=pd.NaT,buy_ref=np.nan,buy_clock=None)
   trades.append(t);pending.append(t);reason='sold_1000'
  reasons.append(dict(date=r.date,reason=reason))
 return pd.DataFrame(trades),pd.DataFrame(reasons),pd.DataFrame(needs),pd.DataFrame(attempts)

def account(d,t,q,slip,schedule,initialcash=0.):
 """Execution of a causal stock plan; deposits only fund deficits, never alter orders."""
 start=d.index[d.date.ge('2020-01-01')][0]
 lots=[dict(q=q,date=d.date.iloc[start]-pd.DateOffset(years=2),div=0.)]
 cash=initialcash;hc=initialcash;recv=[];hr=[];external=0.;rows=[];orders=[];funds=[];payments=[]
 tradecash=0.;paid=0.;hpaid=0.;taxsum=0.;fees=0.
 sales={int(x.entry_i):k for k,x in t.iterrows()};buys={}
 for k,x in t.iterrows():
  if pd.notna(x.exit_i):buys.setdefault(int(x.exit_i),[]).append(k)
 tt=t.copy();tt['sale_net']=np.nan;tt['buy_cost']=np.nan;tt['dividend_tax']=0.;tt['missed_dividend']=0.
 def qty():return sum(l['q'] for l in lots)
 def reserve(day):return sum(l['q']*l['div']*old.taxrate(l['date'],day) for l in lots)
 for i,r in d.iloc[start:].iterrows():
  day=r.date;dayfee=0.;daytax=0.;dayin=0.;daypaid=0.;dayhpaid=0.
  if r.dividend_today:
   recv.append((schedule.get(day,len(d)+10),qty()*r.dividend_today))
   hr.append((schedule.get(day,len(d)+10),q*r.dividend_today))
   for l in lots:l['div']+=r.dividend_today
   for k,x in tt.iterrows():
    if x.entry_i<i and (pd.isna(x.exit_i) or x.exit_i>=i):tt.loc[k,'missed_dividend']+=1000*r.dividend_today
  for k in buys.get(i,[]):
   x=tt.loc[k];value=1000*x.buy_ref*(1+slip);fee=old.sf(value,day);cost=value+fee
   res=reserve(day);gap=max(0.,cost+res-cash)
   if gap>0:cash+=gap;hc+=gap;external+=gap;dayin+=gap
   funds.append(dict(date=day,clock=x.buy_clock,entry=x.entry,buy_cost=cost,sale_net=tt.loc[k,'sale_net'],single_gap=max(0.,cost-tt.loc[k,'sale_net']),cash_before=cash-gap,tax_reserve=res,receivable=sum(a for _,a in recv),deposit=gap,cumulative_deposit=external,zero_capital_pool_before=cash-gap-external+gap))
   cash-=cost;tradecash-=cost;fees+=fee;dayfee+=fee
   lots.append(dict(q=1000,date=day,div=0.));tt.loc[k,'buy_cost']=cost
   orders.append(dict(date=day,clock=x.buy_clock,side='BUY',quantity=1000,reference=x.buy_ref,value=value,fee=fee,tax=0.,deposit=gap,cash=cash,shares=qty(),entry=x.entry))
  # Payment after morning attempts; identical entitlement clock as B16.
  for due,amt in list(recv):
   if due<=i:cash+=amt;paid+=amt;daypaid+=amt;recv.remove((due,amt))
  for due,amt in list(hr):
   if due<=i:hc+=amt;hpaid+=amt;dayhpaid+=amt;hr.remove((due,amt))
  if daypaid or dayhpaid:payments.append(dict(date=day,strategy=daypaid,hold=dayhpaid))
  if i in sales:
   k=sales[i];need=1000;tax=0.
   for l in list(lots):
    if l['date']>=day:continue
    n=min(need,l['q']);tax+=n*l['div']*old.taxrate(l['date'],day);l['q']-=n;need-=n
    if l['q']==0:lots.remove(l)
    if need==0:break
   assert need==0,('insufficient actual stock',day,q)
   value=1000*r.close*(1-slip);fee=old.sf(value,day,True);net=value-fee-tax
   cash+=net;tradecash+=net;taxsum+=tax;fees+=fee;dayfee+=fee;daytax+=tax
   tt.loc[k,'sale_net']=net;tt.loc[k,'dividend_tax']=tax
   orders.append(dict(date=day,clock='15:00',side='SELL',quantity=1000,reference=r.close,value=value,fee=fee,tax=tax,deposit=0.,cash=cash,shares=qty(),entry=day))
  ar=sum(a for _,a in recv);har=sum(a for _,a in hr);res=reserve(day)
  eq=cash+ar+qty()*r.close-res;hold=hc+har+q*r.close
  assert cash>=-1e-6
  assert abs(cash-(initialcash+external+tradecash+paid))<1e-6
  assert abs(hc-(initialcash+external+hpaid))<1e-6
  rows.append(dict(date=day,cash=cash,hold_cash=hc,shares=qty(),receivable=ar,hold_receivable=har,tax_reserve=res,fee=dayfee,tax=daytax,payment=daypaid,hold_payment=dayhpaid,deposit=dayin,external=external,equity=eq,hold_equity=hold,relative=eq-hold,pool_ex_external=cash-external-initialcash,relative_cash_pool=cash-hc))
 z=pd.DataFrame(rows);oo=pd.DataFrame(orders);ff=pd.DataFrame(funds)
 tt['cash_increment']=tt.sale_net-tt.buy_cost-tt.missed_dividend
 tt['net_pct']=100*tt.cash_increment/(1000*tt.sell_ref)
 # Uncompleted episode retains marked missing shares, never zeroes losses.
 unfinished=tt[tt.exit_i.isna()]
 marked=sum(x.sale_net-1000*d.close.iloc[-1]-x.missed_dividend for _,x in unfinished.iterrows())
 assert abs(tt.cash_increment.sum()+marked-z.tax_reserve.iloc[-1]-z.relative.iloc[-1])<1e-5
 k=ff.cumulative_deposit.idxmax() if len(ff) else None
 peak=ff.loc[k] if k is not None else None
 periods=[];on=None
 # Economic cumulative deficit relative to HOLD, distinct from deposit retention.
 for _,rr in z.iterrows():
  neg=rr.relative_cash_pool-rr.tax_reserve< -1e-7
  if neg and on is None:on=rr.date
  if not neg and on is not None:periods.append((on,rr.date,int((rr.date-on).days)));on=None
 if on is not None:periods.append((on,z.date.iloc[-1],int((z.date.iloc[-1]-on).days)))
 done=tt[tt.exit_i.notna()];maxgap=ff.loc[ff.single_gap.idxmax()] if len(ff) else None
 # Hindsight capital requirement excluding both initial cash and all external flows.
 minpool=min([0.]+[(x.cash_before-x.cumulative_deposit+x.deposit-x.tax_reserve-x.buy_cost-initialcash) for _,x in ff.iterrows()])
 summary=dict(stock=q,initialcash=initialcash,slip_bp=slip*10000,sales=len(tt),completed=len(done),pending=len(unfinished),increment=z.relative.iloc[-1],completed_increment=done.cash_increment.sum(),mean_pct=done.net_pct.mean(),fees=fees,tax_paid=taxsum,terminal_tax_reserve=z.tax_reserve.iloc[-1],terminal_receivable=z.receivable.iloc[-1],terminal_missing=q-z.shares.iloc[-1],deposits=external,withdrawals=0.,unreturned=external,peak_requirement=-minpool,peak_date=peak.date if peak is not None else None,peak_pct_1000_value=100*external/(1000*d.loc[d.date.eq(peak.date),'close'].iloc[0]) if peak is not None else 0.,single_median=ff.single_gap.median(),single_p95=ff.single_gap.quantile(.95),single_max=maxgap.single_gap if maxgap is not None else 0.,single_max_date=maxgap.date if maxgap is not None else None,single_positive=int(ff.single_gap.gt(0).sum()),first_deposit=ff.loc[ff.deposit.gt(0),'date'].min(),deposit_yuan_days=float(sum(x.deposit*(d.date.iloc[-1]-x.date).days for _,x in ff.iterrows())),longest_relative_deficit_calendar_days=max([p[2] for p in periods],default=0),relative_mdd=float((z.relative-z.relative.cummax().clip(lower=0)).min()),flow_adjusted_absolute_profit=z.equity.iloc[-1]-(q*d.close.iloc[start]+initialcash)-external,hold_flow_adjusted_absolute_profit=z.hold_equity.iloc[-1]-(q*d.close.iloc[start]+initialcash)-external)
 return z,oo,tt,ff,summary

def verify(d,z,o,q,slip,initialcash,schedule):
 """Separate scalar reconciliation including FIFO, fees, settlement, paired flow."""
 cash=initialcash;holdcash=initialcash;lots=[[q,d.date[d.date.ge('2020-01-01')].iloc[0]-pd.DateOffset(years=2),0.]]
 ar=[];hr=[];flow=0.;by={day:g for day,g in o.groupby('date')}
 def rate(a,b):
  e=b-pd.Timedelta(days=1)
  return .2 if e<a+pd.DateOffset(months=1) else (.1 if e<a+pd.DateOffset(years=1) else 0.)
 def fee(v,date,sell):
  return max(5,v*.0001354)+v*((.00002 if date<pd.Timestamp('2022-04-29') else .00001)+((.001 if date<pd.Timestamp('2023-08-28') else .0005) if sell else 0))
 for (_,r),(_,zr) in zip(d[d.date.ge('2020-01-01')].iterrows(),z.iterrows()):
  day=r.date
  if r.dividend_today:
   ar.append([schedule.get(day,len(d)+10),sum(x[0] for x in lots)*r.dividend_today]);hr.append([schedule.get(day,len(d)+10),q*r.dividend_today])
   for l in lots:l[2]+=r.dividend_today
  dayorders=by.get(day,pd.DataFrame())
  for _,x in dayorders.iterrows():
   if x.side!='BUY':continue
   assert x.quantity==1000
   v=x.quantity*x.reference*(1+slip);f=fee(v,day,False)
   assert abs(v-x.value)<1e-7 and abs(f-x.fee)<1e-7
   cash+=x.deposit-v-f;holdcash+=x.deposit;flow+=x.deposit
   lots.append([1000,day,0.]);assert abs(cash-x.cash)<1e-5
  i=int(d.index[d.date.eq(day)][0])
  for a in list(ar):
   if a[0]<=i:cash+=a[1];ar.remove(a)
  for a in list(hr):
   if a[0]<=i:holdcash+=a[1];hr.remove(a)
  for _,x in dayorders.iterrows():
   if x.side!='SELL':continue
   assert x.quantity==1000
   n=1000;tax=0.
   for l in list(lots):
    if l[1]>=day:continue
    take=min(l[0],n);tax+=take*l[2]*rate(l[1],day);l[0]-=take;n-=take
    if l[0]==0:lots.remove(l)
    if n==0:break
   assert n==0 and abs(tax-x.tax)<1e-7
   v=1000*x.reference*(1-slip);f=fee(v,day,True);cash+=v-f-tax
   assert abs(f-x.fee)<1e-7 and abs(cash-x.cash)<1e-5
  qty=sum(l[0] for l in lots);res=sum(l[0]*l[2]*rate(l[1],day) for l in lots)
  assert abs(cash-zr.cash)<1e-5 and qty==zr.shares and abs(res-zr.tax_reserve)<1e-5
  assert abs(sum(a[1] for a in ar)-zr.receivable)<1e-5 and abs(holdcash-zr.hold_cash)<1e-5
  assert abs(flow-zr.external)<1e-5
  assert abs(cash+sum(a[1] for a in ar)+qty*r.close-res-zr.equity)<1e-5
  assert abs(holdcash+sum(a[1] for a in hr)+q*r.close-zr.hold_equity)<1e-5

def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true'
 parents={}
 for folder in [P,P/'revision_r1',B]:parents.update(json.loads((folder/'manifest.json').read_text())['files'])
 for p,h in parents.items():assert sha(p)==h,p
 check('parent hashes before',str(len(parents)))
 frozen=json.loads((R/'frozen_input_hashes.json').read_text())['sha256']
 paths={'5m':'research/foxconn_t0_20260913/source/601138-full-5min-history.zip','1m':str(r1.B13/'tdx_recovered_1m.csv'),'daily_ledger':str(P/'daily_ledger.csv'),'signals':str(P/'signals.csv'),'original_results':str(P/'results.csv')}
 for k,p in paths.items():assert sha(p)==frozen[k]
 d=pd.read_csv(P/'daily_ledger.csv',parse_dates=['date','exit_date'])
 with zipfile.ZipFile(paths['5m']) as f:m=pd.read_csv(f.open(next(n for n in f.namelist() if n.endswith('601138_5min_all.csv'))))
 m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
 au,ss,op,post=r1.pipeline(d,m);sig=pd.read_csv(P/'signals.csv')
 for k in ss:pd.testing.assert_series_equal(ss[k].reset_index(drop=True),sig[k].astype('boolean'),check_names=False)
 check('unchanged causal signals for main three')
 events=json.loads((B/'verified_events.json').read_text());schedule=b16.schedule_for(d,events,0)
 # All-rule baseline reconciliation and full-window presentation.
 orig=pd.read_csv(P/'results.csv');windows={'full':d.exit_date.notna(),'main':d.date.ge('2020-01-01')&d.exit_date.notna(),'early':d.date.between('2020-01-01','2023-12-31')&d.exit_date.notna(),'recent':d.date.ge('2024-01-01')&d.exit_date.notna()}
 for y in range(2018,2027):windows[str(y)]=d.date.dt.year.eq(y)&d.exit_date.notna()
 baseline=[];mirrors=[]
 for k in sig.columns:
  if not k.startswith('S'):continue
  mask=sig[k].astype('boolean');g=old.ledger(d[d.exit_date.notna()])
  # Match original main regardless of original window spelling.
  h=g.loc[mask.reindex(g.index).fillna(False)&g.date.ge('2020-01-01')]
  oldrow=orig[(orig.id==k)&(orig.kind=='hit')&orig.n.eq(len(h))]
  if len(h):assert any(abs(oldrow.cash-h.cash.sum())<1e-5),(k,len(h),h.cash.sum())
  for w,sel in windows.items():
   base=g[sel.reindex(g.index).fillna(False)&mask.reindex(g.index).notna()]
   hit=base[mask.reindex(base.index).fillna(False)]
   for kind,v in [('hit',hit),('valid_S0',base)]:
    met=old.metrics(v);baseline.append(dict(rule=k,window=w,kind=kind,**met))
  if len(h) and h.net.mean()<0:
   rev=old.ledger(d.loc[h.index],reverse=True);mirrors.append(dict(rule=k,samples=len(h),direction='independent opposite buy/sell candidate only',cash=rev.cash.sum(),mean=rev.net.mean(),original_mean=h.net.mean()))
 save('all_rules_baseline.csv',baseline);save('negative_region_mirrors.csv',mirrors)
 check('all original nominal rule main ledgers matched; all windows recomputed with frozen inputs')
 nominal=[];summ=[];years=[];tails=[];eventrows=[];bridge=[];book={}
 reg=pd.read_csv(R/'experiment_registry.csv');eventmap={}
 ev=pd.read_csv(P/'events_leave_one_out.csv')
 for rule in ['S0','S1_F1','S2_F2']:
  eventmap[rule]={pd.Timestamp(dt):int(row.event) for _,row in ev[ev.id.eq(rule)].iterrows() for dt in row.dates.split(';')}
 for _,rr in reg.iterrows():
  rule,w,bp=rr.rule,rr.window,int(rr.bp);mask=sig[rule].astype('boolean');label=f'{rule}_{w}_{bp}'
  g=d[d.date.ge('2020-01-01')&d.exit_date.notna()&mask.fillna(False)].copy()
  if w=='post0935':
   lookup=m[m.clock.eq('09:45')].set_index('date').open;g['next_open']=g.exit_date.map(lookup);g=g[g.next_open.notna()]
  led=old.ledger(g,slip=bp/10000);save('nominal_'+label+'.csv',led)
  nominal.append(dict(scenario=label,rule=rule,window=w,bp=bp,**old.metrics(led)))
  for inventory in ['all','1000']:
   t,reasons,needs,attempts=plan(d,mask,op,post,w,None if inventory=='all' else 1)
   q=int(needs.minimum_old_shares.max()) if inventory=='all' else 1000
   key=label+'_'+inventory
   z,o,tt,f,a=account(d,t,q,bp/10000,schedule);verify(d,z,o,q,bp/10000,0,schedule)
   a.update(scenario=key,rule=rule,window=w,bp=bp,inventory=inventory,signals=int((mask.fillna(False)&d.date.ge('2020-01-01')&d.exit_date.notna()).sum()),unknown=int((mask.isna()&d.date.ge('2020-01-01')).sum()),t1_skip=int(reasons.reason.eq('T1_inventory').sum()),occupied_skip=int(reasons.reason.eq('inventory_occupied_unfilled').sum()),sale_blocked=int(reasons.reason.eq('sale_lower_limit').sum()),first_window_unavailable=int(attempts['first'].sum()) if len(attempts) else 0)
   for name,data in [('daily',z),('orders',o),('trades',tt),('funding',f),('reasons',reasons),('inventory',needs),('unavailable',attempts)]:save(name+'_'+key+'.csv',data)
   summ.append(a);book[key]=(z,o,tt,f,a,t)
   yy=z.copy();yy['delta']=yy.relative.diff().fillna(yy.relative.iloc[0])
   for yr,gg in yy.groupby(yy.date.dt.year):
    years.append(dict(scenario=key,year=yr,increment=gg.delta.sum(),sales=int(tt.entry.dt.year.eq(yr).sum()),deposits=gg.deposit.sum()))
   ee=tt.copy();ee['event']=ee.entry.map(eventmap[rule])
   for e,gg in ee.groupby('event'):
    eventrows.append(dict(scenario=key,event=e,n=len(gg),increment=gg.cash_increment.sum(),remaining=a['increment']-gg.cash_increment.sum()))
   vals=tt.cash_increment.dropna().sort_values()
   for n in [1,3,5]:
    tails.append(dict(scenario=key,remove_n=n,without_best=a['increment']-vals.tail(n).sum(),without_worst=a['increment']-vals.head(n).sum()))
   print(key,a['increment'],q,a['deposits'],flush=True)
 # Constant participation across costs by rule/window/inventory.
 for rule,w,inventory in {(x['rule'],x['window'],x['inventory']) for x in summ}:
  keys=[x['scenario'] for x in summ if (x['rule'],x['window'],x['inventory'])==(rule,w,inventory)]
  shape=None
  for key in keys:
   oo=book[key][1][['date','clock','side','quantity']].reset_index(drop=True)
   if shape is not None:pd.testing.assert_frame_equal(shape,oo)
   shape=oo
 check('1000 per order and participation invariant to cost',str(len(summ))+' independently verified accounts')
 # Deposit bridge 5514 and payment-delay proof; all main scenarios.
 delayrows=[]
 for a in summ:
  key=a['scenario'];z,o,tt,f,_,t=book[key]
  zz,oo,_,_,aa=account(d,t,a['stock'],a['bp']/10000,schedule,5514.)
  assert abs(aa['increment']-a['increment'])<1e-5
  assert abs(aa['deposits']-max(0,a['deposits']-5514))<1e-5
  a['additional_over_5514']=aa['deposits']
  for delay in [1,3]:
   sc=b16.schedule_for(d,events,delay)
   dz,do,_,_,da=account(d,t,a['stock'],a['bp']/10000,sc)
   pd.testing.assert_frame_equal(o[['date','clock','side','quantity']],do[['date','clock','side','quantity']])
   assert abs(da['increment']-a['increment'])<1e-5
   delayrows.append(dict(scenario=key,delay=delay,increment=da['increment'],deposits=da['deposits'],delta_deposit=da['deposits']-a['deposits']))
 save('payment_delay_proof.csv',delayrows);check('payment delays0/1/3 and5514 reference preserve orders and profit')
 # Fixed B16 old participation11bp vs new funded1000 and all-stock; same dates and exact costs.
 bs=pd.read_csv(B/'account_summary.csv')
 for w in ['open','post0935']:
  oldkey=f'S1_F1_{w}_b10_e0_d0_main'
  oo=pd.read_csv(B/f'orders_{oldkey}.csv',parse_dates=['date'])
  origcash=float(bs.loc[bs.scenario.eq(oldkey),'increment_cash'].iloc[0])
  vals=oo.quantity*oo.reference*np.where(oo.side.eq('BUY'),1.0011,.9989)
  fees=np.array([old.sf(v,x.date,x.side=='SELL') for v,(_,x) in zip(vals,oo.iterrows())])
  direct=float(((vals-oo.value)*np.where(oo.side.eq('SELL'),1,-1)-(fees-oo.fee)).sum())
  fixed=origcash+direct;new=book[f'S1_F1_{w}_11_1000'][4];main=book[f'S1_F1_{w}_11_all'][4]
  neworders=book[f'S1_F1_{w}_11_1000'][1]
  pd.testing.assert_frame_equal(oo[['date','clock','side','quantity']].reset_index(drop=True),neworders[['date','clock','side','quantity']].reset_index(drop=True),check_dtype=False)
  assert abs(fixed-new['increment'])<1e-5
  stresskey=f'S1_F1_{w}_b10_e1_d0_extra_cost';stress=bs[bs.scenario.eq(stresskey)].iloc[0]
  so=pd.read_csv(B/f'orders_{stresskey}.csv',parse_dates=['date'])
  bridge.append(dict(window=w,old10bp=origcash,direct_extra1bp=direct,fixed_old11bp=fixed,old_truncated11bp=stress.increment_cash,corrected1000stock11bp=new['increment'],corrected_allstock11bp=main['increment'],cash_truncation_effect=stress.increment_cash-fixed,inventory_and_tax_effect=main['increment']-fixed,old2025sales=int((oo.side.eq('SELL')&oo.date.dt.year.eq(2025)).sum()),oldstress2025sales=int((so.side.eq('SELL')&so.date.dt.year.eq(2025)).sum()),new1000_2025=int((neworders.side.eq('SELL')&neworders.date.dt.year.eq(2025)).sum()),newall2025=int(book[f'S1_F1_{w}_11_all'][2].entry.dt.year.eq(2025).sum())))
 check('B16 fixed old dates11bp exactly equal funded1000-stock path')
 # Old and new reasons in a full date bridge for all three, including original actual shrinking quantities.
 for rule in ['S0','S1_F1','S2_F2']:
  for bp in [5,10]:
   path=P/'revision_r1'/f'orders_{rule}_30_paid_open_{bp}.csv'
   if not path.exists():continue
   oo=pd.read_csv(path,parse_dates=['date']);sell=oo[oo.side.eq('SELL')].set_index('date').quantity;buy=oo[oo.side.eq('BUY')].groupby('date').quantity.sum()
   z=d[['date']].copy();z['signal']=sig[rule];z['old_sold']=z.date.map(sell).fillna(0);z['old_bought']=z.date.map(buy).fillna(0)
   for inv in ['all','1000']:
    rs=pd.read_csv(R/f'reasons_{rule}_open_{bp}_{inv}.csv',parse_dates=['date']).set_index('date').reason;z['new_'+inv]=z.date.map(rs)
   save(f'bridge_dates_{rule}_{bp}.csv',z)
 # Future suffix cannot change past plan, financial state or order quantities.
 causal=[]
 for dt in ['2023-03-24','2024-01-22','2025-10-16']:
  cutoff=pd.Timestamp(dt);dd=d.copy();dd.loc[dd.date.gt(cutoff),['close','open','volume','dividend_today']]*=1.17
  for w in ['open','post0935']:
   mask=sig.S1_F1.astype('boolean');t,*_=plan(dd,mask,op,post,w,None)
   q=book[f'S1_F1_{w}_11_all'][4]['stock']
   zz,oo,*_=account(dd,t,q,.0011,schedule)
   z,o,*_=book[f'S1_F1_{w}_11_all']
   pd.testing.assert_frame_equal(z[z.date.le(cutoff)].reset_index(drop=True),zz[zz.date.le(cutoff)].reset_index(drop=True))
   pd.testing.assert_frame_equal(o[o.date.le(cutoff)].reset_index(drop=True),oo[oo.date.le(cutoff)].reset_index(drop=True))
   causal.append(dict(cutoff=dt,window=w,status='PASS'))
 save('causality.csv',causal);check('six new engine future-suffix cases; inherited signal-prefix/QC tests reused')
 # Small cash difference: deposit pays all1000, loss remains, later eligible trade proceeds.
 ds=pd.DataFrame(dict(date=pd.bdate_range('2020-01-02',periods=5),open=10.,close=10.,dividend_today=0.))
 ds['exit_date']=ds.date.shift(-1);ds['volume']=1000.;ds['limit_down']=1.
 ts=pd.DataFrame([dict(entry_i=0,entry=ds.date[0],sell_ref=10.,exit_i=1,exit=ds.date[1],buy_ref=10.,buy_clock='09:25'),dict(entry_i=2,entry=ds.date[2],sell_ref=10.,exit_i=3,exit=ds.date[3],buy_ref=10.,buy_clock='09:25')])
 zz,oo,tt,ff,aa=account(ds,ts,1000,.0012,{})
 assert oo.quantity.eq(1000).all() and len(oo)==4 and 0<ff.deposit.iloc[0]<100 and aa['increment']<0
 verify(ds,zz,oo,1000,.0012,0,{})
 save('small_gap_example.csv',oo);check('small tens-of-yuan gap funded, complete next trade, true loss retained',str(aa['increment']))
 for p,h in parents.items():assert sha(p)==h,p
 check('parent hashes after',str(len(parents)))
 save('nominal_matrix.csv',nominal);save('account_summary.csv',summ);save('years.csv',years);save('events.csv',eventrows);save('symmetric_tails.csv',tails);save('old_new_bridge.csv',bridge)
 js('validation.json',CHECK)
 review=['# B17 remote computed evidence','Historical model only; full-stock assumption and1000-stock contrast separate. All flows retained.']
 frames=[('Nominal',pd.DataFrame(nominal)),('Accounts',pd.DataFrame(summ)),('Bridge',pd.DataFrame(bridge)),('Years',pd.DataFrame(years)),('Tail deletion',pd.DataFrame(tails))]
 for title,x in frames:review+=['## '+title,x.to_markdown(index=False,floatfmt='.6f')]
 (R/'RESULTS_REVIEW.md').write_text('\n\n'.join(review))
 js('runtime.json',dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],python=sys.version))
 js('manifest.json',dict(parent='86ceac2137830b28ca7b97c3218654adf0b5931a',code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],inputs={p:sha(p) for p in paths.values()},files={str(p):sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['manifest.json','calculation.log']}))
 print('B17_COMPLETE',len(summ),flush=True)
if __name__=='__main__':
 try:run()
 except Exception:
  (R/('failure_'+os.environ.get('GITHUB_RUN_ID','unknown')+'.txt')).write_text(traceback.format_exc());js('validation.json',CHECK);raise
