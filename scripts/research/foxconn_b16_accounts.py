#!/usr/bin/env python3
"""B16 bounded payment/cost matrix; GitHub-only, immutable B15/R1 parents."""
import os,json,hashlib,zipfile,sys,subprocess,traceback
from pathlib import Path
import numpy as np,pandas as pd
import foxconn_overnight_sell_b15 as old
import foxconn_overnight_sell_b15_r1 as r1
from foxconn_overnight_sell_b15 import sf,taxrate
R=Path('research/foxconn_t0_20260922_b16');P=r1.P;Q=P/'revision_r1'
CHECKS=[];INPUTS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(name,x):(R/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def save(name,x):
 z=x if isinstance(x,pd.DataFrame)else pd.DataFrame(x);z.to_csv(R/name,index=False);return z
def check(name,detail=''):CHECKS.append(dict(name=name,status='PASS',detail=detail))
def schedule_for(d,events,delay):
 out={}
 for e in events:
  ex=pd.Timestamp(e['ex_date']);pay=e.get('payment_date')
  if pay is None:out[ex]=len(d)+10;continue
  p=pd.Timestamp(pay);pos=int(d.date.searchsorted(p))+delay
  assert p>=ex
  out[ex]=pos if pos<len(d) else len(d)+10
 return out

def account(d,mask,win,buffer,conservative=True,pay_delay=False,slip=.0005,first_window="open",post=None,until=None,schedule=None,eventlog=None,fundinglog=None):
 start=d.index[d.date.ge('2020-01-01')][0];q=1000;initial=q*d.loc[start,'close']*(1+buffer)
 cash=q*d.loc[start,'close']*buffer;bcash=cash;recv=[];brecv=[]
 lots=[{'q':q,'acquired':d.loc[start,'date']-pd.DateOffset(years=2),'divps':0.}]
 unobserved_first_windows=0;records=[];orders=[];episodes=[];active=None;attempt=0;completed=0;skip_t1=0;skip_missing=0;blocked_sell=0;need_count=0
 total_fees=0.;tax_paid=0.;net_trade=0.;div_paid=0.;missed_up=0.;avoided_down=0.;max_restore_cash=0.;max_def_days=0;defrun=0;fundfails=0
 def shares():return sum(l['q'] for l in lots)
 def reserve(date):return sum(l['q']*l['divps']*taxrate(l['acquired'],date) for l in lots)
 for i in range(start,len(d)):
  r=d.iloc[i];day=r.date;day_buys=0;day_sells=0;day_fees=0.;daytax=0.;daydiv=0.;short_before=q-shares();prevclose=d.loc[i-1,'close'] if i>start else r.close
  # Entitlements belong to stock held at preceding register close. Cash credited at close, never before opening repurchase.
  if r.dividend_today:
   due=(i if not pay_delay else len(d)+1) if schedule is None else schedule.get(day,len(d)+1)
   ent=shares()*r.dividend_today;recv.append({'amount':ent,'due':due,'event':day});brecv.append({'amount':q*r.dividend_today,'due':due,'event':day})
   if eventlog is not None:eventlog.append(dict(event=day,action='entitlement',date=day,clock='before_open',quantity=shares(),per_share=r.dividend_today,amount=ent,due_index=due))
   for l in lots:l['divps']+=r.dividend_today
  gap_impact=-short_before*(r.open-prevclose+r.dividend_today)
  missed_up+=max(0,-gap_impact);avoided_down+=max(0,gap_impact)
  eq_open_before=cash+sum(a['amount']for a in recv)+shares()*r.open-reserve(day)
  bopen=bcash+sum(a['amount']for a in brecv)+q*r.open
  last_buy_price=float(r.open)
  opportunities=win[i] if conservative else [('09:25',float(r.open),'nominal_open')]
  if first_window=='post0935' and active is not None and i==active['i']+1:
   opportunities=post[i]
   if not opportunities:unobserved_first_windows+=1
  if until is not None:opportunities=[w for w in opportunities if day+pd.Timedelta(w[0]+':00')<=until]
  # Cash shortages cannot be remedied by repeated minimum-fee orders at the SAME observation.
  for clock,price,kind in opportunities:
   missing=q-shares()
   if missing==0:break
   fullvalue=missing*price*(1+slip);need=max(0,fullvalue+sf(fullvalue,day)-(cash-reserve(day)));max_restore_cash=max(max_restore_cash,need)
   if fundinglog is not None:fundinglog.append(dict(date=day,clock=clock,missing=missing,reference=price,cash_before=cash,tax_reserve=reserve(day),receivable=sum(a['amount']for a in recv),full_cost=fullvalue+sf(fullvalue,day),cash_gap=need))
   if need>1e-7:fundfails+=1
   n=missing
   while n>0 and n*price*(1+slip)+sf(n*price*(1+slip),day)>cash-reserve(day)+1e-8:n-=100
   if n<=0:continue
   last_buy_price=price
   v=n*price*(1+slip);cost=sf(v,day);cash-=v+cost;total_fees+=cost;day_fees+=cost;net_trade-=v+cost;day_buys+=n
   lots.append({'q':n,'acquired':day,'divps':0.});orders.append(dict(date=day,clock=clock,side='BUY',quantity=n,reference=price,value=v,fee=cost,dividend_tax=0.,cash_after=cash,shares_after=shares(),kind=kind))
   if shares()==q and active is not None:
    episodes.append(dict(entry=active['date'],exit=day,days=i-active['i'],sale_cash=active['sale_cash'],final_cash=cash,restored=True));active=None;completed+=1
  mark=last_buy_price
  eq_open=cash+sum(a['amount']for a in recv)+shares()*mark-reserve(day)
  bmark=bcash+sum(a['amount']for a in brecv)+q*mark
  if until is not None and day==until.normalize() and until.strftime('%H:%M')<'15:00':
   return pd.DataFrame(records),pd.DataFrame(orders),pd.DataFrame(episodes),dict(prefix_state=dict(cash=cash,shares=shares(),receivable=sum(a['amount']for a in recv),tax_reserve=reserve(day),lots=lots,active=active))
  # Payment is credited after the last buy window; available only on subsequent trading days. Close sale has no cash condition.
  for a in list(recv):
   if a['due']<=i:
    cash+=a['amount'];daydiv+=a['amount'];div_paid+=a['amount'];recv.remove(a)
    if eventlog is not None:eventlog.append(dict(event=a.get('event',day),action='payment',date=day,clock='after_close',amount=a['amount'],due_index=a['due']))
  for a in list(brecv):
   if a['due']<=i:bcash+=a['amount'];brecv.remove(a)
  sig=pd.notna(mask.iloc[i]) and bool(mask.iloc[i])
  held_before_sale=shares();uncovered=q-held_before_sale
  # Remaining intraday shortfall is marked at close; use actual buy prices to attribute covered parts.
  today_orders=[o for o in orders if o['date']==day and o['side']=='BUY']
  intra=-uncovered*(r.close-r.open)-sum(o['quantity']*(o['reference']-r.open) for o in today_orders)
  missed_up+=max(0,-intra);avoided_down+=max(0,intra)
  if sig and pd.notna(r.exit_date):
   if active is not None or shares()<q:skip_missing+=1
   elif sum(l['q']for l in lots if l['acquired']<day)<q:skip_t1+=1
   elif conservative and (r.close<=r.limit_down+.005 or r.volume<=0):blocked_sell+=1
   else:
    assert all(l['acquired']<day for l in lots)
    taxes=sum(l['q']*l['divps']*taxrate(l['acquired'],day)for l in lots)
    v=q*r.close*(1-slip);cost=sf(v,day,True);cash+=v-cost-taxes;total_fees+=cost;day_fees+=cost;tax_paid+=taxes;daytax+=taxes;net_trade+=v-cost-taxes
    lots=[];day_sells=q;attempt+=1;active={'date':day,'i':i,'sale_cash':v-cost-taxes}
    orders.append(dict(date=day,clock='15:00',side='SELL',quantity=q,reference=r.close,value=v,fee=cost,dividend_tax=taxes,cash_after=cash,shares_after=0,kind='close_proxy'))
  # Postponed cash isn't fabricated; it remains a receivable in both accounts.
  ar=sum(a['amount']for a in recv);br=sum(a['amount']for a in brecv);tax_res=reserve(day)
  eq=cash+ar+shares()*r.close-tax_res;beq=bcash+br+q*r.close
  # Restore deficits measured BEFORE fresh planned sale, not the intentional overnight absence itself.
  defrun=defrun+1 if held_before_sale<q else 0;max_def_days=max(max_def_days,defrun)
  if held_before_sale<q:need_count+=1
  assert cash>=-1e-6 and shares()>=0 and shares()<=q and shares()%100==0
  assert abs(cash-(q*d.loc[start,'close']*buffer+net_trade+div_paid))<1e-5
  assert shares()==q+sum(o['quantity']*(1 if o['side']=='BUY' else -1)for o in orders)
  records.append(dict(date=day,cash=cash,receivable=ar,shares=shares(),settled_next_day=shares(),dividend_tax_reserve=tax_res,fees=day_fees,dividend_tax_paid=daytax,dividend_received=daydiv,buy_quantity=day_buys,sell_quantity=day_sells,restoration_missing_shares=uncovered,equity_open_before=eq_open_before,equity_open=eq_open,equity_close=eq,hold_equity_open=bopen,hold_equity_after=bmark,hold_equity_close=beq,relative_equity=eq-beq,restore_cash_gap=max(0,(q-shares())*r.close*(1+slip)+sf((q-shares())*r.close*(1+slip),day)-cash+tax_res)if shares()<q else 0.))
  if until is not None and day==until.normalize():
   return pd.DataFrame(records),pd.DataFrame(orders),pd.DataFrame(episodes),dict(prefix_state=dict(cash=cash,shares=shares(),receivable=sum(a['amount']for a in recv),tax_reserve=reserve(day),lots=lots,active=active))
 if active is not None:episodes.append(dict(entry=active['date'],exit=pd.NaT,days=len(d)-1-active['i'],restored=False))
 z=pd.DataFrame(records);eq=np.r_[initial,z[['equity_open_before','equity_open','equity_close']].to_numpy().ravel()];bh=np.r_[initial,z[['hold_equity_open','hold_equity_after','hold_equity_close']].to_numpy().ravel()]
 rel=eq-bh
 summary=dict(buffer=buffer,mode='conservative' if conservative else 'nominal',settlement='scheduled_payment_close' if schedule is not None else ('receivable_locked' if pay_delay else 'ex_date_close_scenario'),initial=initial,final=eq[-1],hold_final=bh[-1],return_pct=100*(eq[-1]/initial-1),hold_return_pct=100*(bh[-1]/initial-1),increment_cash=eq[-1]-bh[-1],increment_pct=100*(eq[-1]-bh[-1])/initial,mdd_pct=100*(eq/np.maximum.accumulate(eq)-1).min(),hold_mdd_pct=100*(bh/np.maximum.accumulate(bh)-1).min(),relative_mdd_cash=(rel-np.maximum.accumulate(rel)).min(),completed=completed,sales=attempt,skip_t1=skip_t1,skip_missing=skip_missing,sale_blocked=blocked_sell,failed_restore_days=need_count,max_consecutive_deficit_days=max_def_days,insufficient_cash_windows=fundfails,max_extra_cash_required=max_restore_cash,terminal_missing=q-shares(),terminal_cash=cash,terminal_cash_gap=z.restore_cash_gap.iloc[-1],terminal_receivable=z.receivable.iloc[-1],terminal_tax_reserve=z.dividend_tax_reserve.iloc[-1],unobserved_first_windows=unobserved_first_windows,missed_rise_cash=missed_up,avoided_fall_cash=avoided_down,fees=total_fees,dividend_tax=tax_paid)
 return z,pd.DataFrame(orders),pd.DataFrame(episodes),summary

def verify_account(d,z,o,ev,buf,slip,schedule):
 r1.independent(z,o,buf,d)
 # Independent scalar reconstruction: no account-engine settlement or tax-reserve helper.
 ds=d[d.date.ge('2020-01-01')];initialcash=1000*ds.close.iloc[0]*buf
 lots=[dict(q=1000,date=ds.date.iloc[0]-pd.DateOffset(years=2),div=0.)]
 cash=initialcash;owed={};received=0.;entitled=0.;taxes=0.;fees=0.
 byday={day:g for day,g in o.groupby('date')}
 def rate(buy,sell):
  last=sell-pd.Timedelta(days=1)
  return .2 if last<buy+pd.DateOffset(months=1)else(.1 if last<buy+pd.DateOffset(years=1)else 0.)
 def comm(v,day,sell):
  return max(5.,v*.0001354)+v*((.00002 if day<pd.Timestamp('2022-04-29')else .00001)+((.001 if day<pd.Timestamp('2023-08-28')else .0005)if sell else 0.))
 for (i,dayrow),(_,r)in zip(ds.iterrows(),z.iterrows()):
  day=dayrow.date;q=sum(l['q']for l in lots)
  if dayrow.dividend_today:
   amt=q*dayrow.dividend_today;owed[day]=amt;entitled+=amt
   for l in lots:l['div']+=dayrow.dividend_today
  for _,t in byday.get(day,pd.DataFrame()).iterrows():
   if t.side!='BUY':continue
   assert t.quantity%100==0
   value=t.quantity*t.reference*(1+slip);fee=comm(value,day,False)
   assert abs(t.value-value)<1e-6 and abs(t.fee-fee)<1e-6
   cash-=value+fee;fees+=fee;lots.append(dict(q=int(t.quantity),date=day,div=0.))
   assert abs(cash-t.cash_after)<1e-5 and sum(l['q']for l in lots)==t.shares_after
  daypay=0.
  for ex,amt in list(owed.items()):
   if schedule.get(ex,len(d)+10)<=i:
    daypay+=amt;cash+=amt;received+=amt;del owed[ex]
  assert abs(daypay-r.dividend_received)<1e-6
  for _,t in byday.get(day,pd.DataFrame()).iterrows():
   if t.side!='SELL':continue
   assert sum(l['q']for l in lots)==1000 and all(l['date']<day for l in lots)
   value=t.quantity*t.reference*(1-slip);fee=comm(value,day,True)
   tax=sum(l['q']*l['div']*rate(l['date'],day)for l in lots)
   assert abs(t.value-value)<1e-6 and abs(t.fee-fee)<1e-6 and abs(t.dividend_tax-tax)<1e-6
   cash+=value-fee-tax;fees+=fee;taxes+=tax;lots=[]
   assert abs(cash-t.cash_after)<1e-5 and t.shares_after==0
  q=sum(l['q']for l in lots);reserve=sum(l['q']*l['div']*rate(l['date'],day)for l in lots)
  assert abs(r.receivable-sum(owed.values()))<1e-6
  assert abs(received+sum(owed.values())-entitled)<1e-6
  assert abs(cash-r.cash)<1e-5 and q==r.shares and abs(reserve-r.dividend_tax_reserve)<1e-6
 assert abs(taxes-z.dividend_tax_paid.sum())<1e-6 and abs(fees-z.fees.sum())<1e-6
 # Each entitlement paid once or explicitly still owed, with same amount; zero-amount rows retained.
 ee=pd.DataFrame(ev)
 for event,g in ee.groupby('event'):
  assert sum(g.action.eq('entitlement'))==1 and sum(g.action.eq('payment'))<=1
  if sum(g.action.eq('payment')):
   assert abs(g[g.action.eq('payment')].amount.iloc[0]-g[g.action.eq('entitlement')].amount.iloc[0])<1e-6
 return dict(status='PASS',orders=len(o),days=len(z),fees=fees,tax=taxes,entitled=entitled,received=received,receivable=sum(owed.values()))

def order_shape(o):
 return o[['date','clock','side','quantity']].reset_index(drop=True)
def firstshape(a,b):
 x=order_shape(a).merge(order_shape(b),on=['date','clock','side'],how='outer',suffixes=('_a','_b'))
 x=x[~x.quantity_a.eq(x.quantity_b)]
 return str(x.date.min().date())if len(x)else None

def synthetic_tests():
 dates=pd.bdate_range('2020-01-02',periods=8)
 d=pd.DataFrame(dict(date=dates,open=10.,high=10.,low=10.,close=10.,preclose=10.,volume=1000.,dividend_today=0.,limit_up=20.,limit_down=1.))
 d['exit_date']=d.date.shift(-1);d.loc[1,'dividend_today']=.5
 mask=pd.Series(False,index=d.index,dtype='boolean');mask.iloc[1]=True
 w={i:[('09:25',10.,'synthetic')]for i in d.index};p={i:[('09:40',10.,'synthetic')]for i in d.index}
 for delay in [0,1,3]:
  sc={dates[1]:1+delay};e=[];f=[]
  z,o,_,a=account(d,mask,w,.3,schedule=sc,eventlog=e,fundinglog=f)
  assert z.dividend_received.iloc[1+delay]==500 and z.dividend_received.sum()==500
  assert np.allclose(z.receivable.iloc[1:1+delay],500)
  # Prefix before close on payable day must keep receivable uncredited.
  _,oo,_,state=account(d,mask,w,.3,schedule=sc,until=dates[1+delay]+pd.Timedelta('09:35:00'))
  assert state['prefix_state']['receivable']==500
  verify_account(d,z,o,e,.3,.0005,sc)
 sc={dates[1]:100};e=[];z,o,_,a=account(d,mask,w,.3,schedule=sc,eventlog=e);assert z.dividend_received.sum()==0 and z.receivable.iloc[-1]==500
 verify_account(d,z,o,e,.3,.0005,sc)
 # Calendar offsets must count observed exchange sessions, not weekdays.
 dd=d.copy();dd.loc[2:,'date']+=pd.Timedelta(days=5)
 events=[dict(ex_date=str(dates[1].date()),payment_date=str(dates[1].date()))]
 assert schedule_for(dd,events,1)[dates[1]]==2
 check('synthetic close-only settlement, delays0/1/3, unknown receivable, no duplicate and exchange-session shift')

def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true','GitHub-only calculation'
 # Immutable originals and all input files verified both before and after.
 parents={}
 for folder in [P,Q]:
  man=json.loads((folder/'manifest.json').read_text());parents.update(man['files'])
 for p,h in parents.items():assert sha(p)==h,p
 frozen=json.loads((R/'frozen_input_hashes.json').read_text())['sha256']
 paths={'5m':'research/foxconn_t0_20260913/source/601138-full-5min-history.zip','1m':str(r1.B13/'tdx_recovered_1m.csv'),'daily_ledger':str(P/'daily_ledger.csv'),'signals':str(P/'signals.csv'),'original_results':str(P/'results.csv')}
 for key,p in paths.items():assert sha(p)==frozen[key],p;INPUTS[p]=sha(p)
 for p in [R/'protocol.md',R/'experiment_registry.csv',R/'verified_events.json',R/'price_decision.md',Path(__file__),Path(r1.__file__),Path(old.__file__)]:INPUTS[str(p)]=sha(p)
 check('parent snapshots and frozen inputs',str(len(parents))+' B15/R1 files')
 events=json.loads((R/'verified_events.json').read_text())
 reviewed=pd.read_csv(R/'dividend_review.csv')
 for e in events:
  row=reviewed[reviewed.ex_date.eq(e['ex_date'])].iloc[0];p=Path(row.path)
  assert p.read_bytes().startswith(b'%PDF') and sha(p)==row.sha256
  tx=Path(row.text_path).read_text();compact=''.join(tx.split())
  assert '富士康工业互联网股份有限公司'in compact and '现金红利发放日'in compact
  day=pd.Timestamp(e['payment_date']);assert f'{day.year}/{day.month}/{day.day}'in compact
  assert str(e['per_share'])in compact
  e.update(source_path=str(p),source_sha256=sha(p),text_path=row.text_path)
 save('dividend_source_table.csv',events)
 d=pd.read_csv(P/'daily_ledger.csv',parse_dates=['date','exit_date']);assert d.date.max()==pd.Timestamp('2026-09-11')
 with zipfile.ZipFile(paths['5m'])as zipf:m=pd.read_csv(zipf.open(next(n for n in zipf.namelist()if n.endswith('601138_5min_all.csv'))))
 m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
 au,sigs,op,post=r1.pipeline(d,m)
 sigold=pd.read_csv(P/'signals.csv')
 for rule in ['S0','S1_F1']:pd.testing.assert_series_equal(sigs[rule].reset_index(drop=True),sigold[rule].astype('boolean'),check_names=False)
 for e in events:
  ix=d.index[d.date.eq(e['ex_date'])][0]
  assert d.date.iloc[ix-1]==pd.Timestamp(e['record_date'])
  assert abs(d.dividend_today.iloc[ix]-e['per_share'])<1e-10
 check('nine announcements and prior-register-close entitlement mapping')
 synthetic_tests()
 registry=pd.read_csv(R/'experiment_registry.csv')
 original_events=pd.read_csv(P/'events_leave_one_out.csv')
 book={};summary=[];checks=[];years=[];attribution=[];payouts=[];funding=[]
 def execute(rule,first,bp,extra,delay,purpose):
  label=f'{rule}_{first}_b{bp}_e{extra}_d{delay}_{purpose}'
  sc={r.date:i for i,r in d.iterrows()}if purpose=='exdate_reference'else({r.date:len(d)+10 for i,r in d.iterrows()}if purpose=='locked_reference'else schedule_for(d,events,delay))
  el=[];fl=[];slip=(bp+extra)/10000
  z,o,ep,a=account(d,sigs[rule],op,.3,slip=slip,first_window=first,post=post,schedule=sc,eventlog=el,fundinglog=fl)
  v=verify_account(d,z,o,el,.3,slip,sc);v['scenario']=label;checks.append(v)
  a.update(scenario=label,rule=rule,first_window=first,base_bp=bp,extra_bp=extra,delay=delay,purpose=purpose,deficit_days=int(z.restoration_missing_shares.gt(0).sum()),traded_notional=o.value.sum(),reference_notional=(o.quantity*o.reference).sum())
  for l in [el,fl]:
   for row in l:row['scenario']=label
  payouts.extend(el);funding.extend(fl)
  save('account_'+label+'.csv',z);save('orders_'+label+'.csv',o);save('episodes_'+label+'.csv',ep);summary.append(a);book[label]=(z,o,a,el,fl)
  zz=z.copy();zz['delta']=zz.relative_equity.diff().fillna(zz.relative_equity.iloc[0]);zz['year']=zz.date.dt.year
  for yr,g in zz.groupby('year'):years.append(dict(scenario=label,year=yr,increment=g.delta.sum(),fees=g.fees.sum(),tax=g.dividend_tax_paid.sum(),deficit_days=int(g.restoration_missing_shares.gt(0).sum()),sales=int(g.sell_quantity.gt(0).sum())))
  emap={}
  for _,er in original_events[original_events.id.eq(rule)].iterrows():
   for dt in str(er.dates).split(';'):emap[pd.Timestamp(dt)]=int(er.event)
  tag='before_first_sale';labels=[]
  for _,rr in zz.iterrows():
   if rr.sell_quantity:tag=str(emap.get(rr.date,'unmapped'))
   labels.append(tag)
  zz['event']=labels
  for ev,g in zz.groupby('event'):attribution.append(dict(scenario=label,event=ev,increment=g.delta.sum(),start=g.date.min(),end=g.date.max()))
  print('ACCOUNT',label,'increment',a['increment_cash'],flush=True)
  return label
 # Baseline reference before scheduled accounts; unchanged windows and financial fields.
 baseline=[]
 for rule in ['S1_F1','S0']:
  for first in ['open','post0935']:
   for bp in [5,10]:
    label=execute(rule,first,bp,0,0,'exdate_reference');z,o,a,el,fl=book[label]
    oz=pd.read_csv(Q/f'account_{rule}_30_paid_{first}_{bp}.csv',parse_dates=['date'])
    oo=r1.readorders(Q/f'orders_{rule}_30_paid_{first}_{bp}.csv')
    pd.testing.assert_frame_equal(z,oz,check_exact=False,atol=1e-7,rtol=0)
    assert len(r1.orderdiff(oo,o,label))==0
    baseline.append(dict(scenario=label,daily_fields_equal=True,orders_equal=True,increment=a['increment_cash']))
 save('baseline_reproduction.csv',baseline);check('all eight R1 paid baseline accounts reproduced')
 for _,r in registry.iterrows():execute(r.rule,r.first_window,int(r.base_bp),int(r.extra_bp),int(r.payment_delay),r.purpose)
 # Existing locked references only, no new strategy grid.
 for first in ['open','post0935']:
  for bp in [5,10]:
   label=execute('S1_F1',first,bp,0,0,'locked_reference');z,o,*_=book[label]
   oz=pd.read_csv(Q/f'account_S1_F1_30_locked_{first}_{bp}.csv',parse_dates=['date'])
   pd.testing.assert_frame_equal(z,oz,check_exact=False,atol=1e-7,rtol=0)
 check('four inherited S1 locked reference accounts reproduced')
 # Budget and static-execution versus dynamic participation accounting.
 budgets=[];stress=[];divergences=[];dependency=[]
 for first in ['open','post0935']:
  for bp in [5,10]:
   base=f'S1_F1_{first}_b{bp}_e0_d0_main';z,o,a,el,fl=book[base];turn=o.value.sum();refturn=(o.reference*o.quantity).sum()
   budgets.append(dict(scenario=base,net_increment=a['increment_cash'],completed=a['completed'],traded_notional=turn,reference_notional=refturn,yuan_per_episode=a['increment_cash']/a['completed'],uniform_extra_bp_per_side=a['increment_cash']/turn*10000,reference_price_bp_budget=a['increment_cash']/refturn*10000,basis='extra proportional fee on BOTH actual legs; not empirical slippage estimate'))
   for extra in [1,2]:
    label=f'S1_F1_{first}_b{bp}_e{extra}_d0_extra_cost';nz,no,na,*_=book[label]
    changed=firstshape(o,no)
    newvalues=o.quantity*o.reference*np.where(o.side.eq('BUY'),1+(bp+extra)/10000,1-(bp+extra)/10000)
    newfees=np.array([sf(float(v),r.date,r.side=='SELL')for v,(_,r)in zip(newvalues,o.iterrows())])
    signed=np.where(o.side.eq('SELL'),1,-1)
    cash_effect=float(((newvalues-o.value)*signed-(newfees-o.fee)).sum())
    fixed=a['increment_cash']+cash_effect
    if changed is None:assert abs(na['increment_cash']-fixed)<1e-5
    stress.append(dict(scenario=label,base_increment=a['increment_cash'],linear_budget_consumption=turn*extra/10000,exact_fixed_order_cost_consumption=-cash_effect,fixed_order_increment=fixed,rerun_increment=na['increment_cash'],path_feedback=na['increment_cash']-fixed,first_quantity_participation_change=changed,sales=na['sales'],completed=na['completed'],deficit_days=na['deficit_days'],terminal_missing=na['terminal_missing']))
   locked=f'S1_F1_{first}_b{bp}_e0_d0_locked_reference';lz,lo,la,le,lf=book[locked]
   date=firstshape(o,lo);divergences.append(dict(reference=locked,comparison=base,first_quantity_participation_change=date,increment_difference=a['increment_cash']-la['increment_cash']))
   if date:
    day=pd.Timestamp(date);ff=pd.DataFrame(fl);ll=pd.DataFrame(lf);a0=ff[ff.date.eq(day)].iloc[0];b0=ll[ll.date.eq(day)].iloc[0]
    for ee in el:
     if ee['action']=='entitlement'and ee['event']<day:
      payment=next((x for x in el if x['action']=='payment'and x['event']==ee['event']),None)
      dependency.append(dict(scenario=base,first_change=day,event=ee['event'],entitled_quantity=ee['quantity'],gross_entitlement=ee['amount'],payment_date=payment['date']if payment else None,payment_before_dependency=bool(payment and payment['date']<day),cash_before_paid=a0.cash_before,cash_before_locked=b0.cash_before,full_restore_cost=a0.full_cost,locked_cash_shortfall=b0.cash_gap,paid_cash_surplus=a0.cash_before-a0.tax_reserve-a0.full_cost,cumulative_paid=float(pd.DataFrame(el).query("action=='payment'").loc[lambda x:x.date.lt(day),'amount'].sum())))
 # Delay path effects including S0; find first inventory/participation difference and daily cash/AR difference.
 for rule in ['S1_F1','S0']:
  for first in ['open','post0935']:
   for bp in [5,10]:
    base=f'{rule}_{first}_b{bp}_e0_d0_main';z,o,a,*_=book[base]
    for delay in [1,3]:
     key=f'{rule}_{first}_b{bp}_e0_d{delay}_main';zz,oo,aa,*_=book[key]
     cashdiff=~np.isclose(z.cash,zz.cash,atol=1e-7,rtol=0)
     divergences.append(dict(reference=base,comparison=key,first_quantity_participation_change=firstshape(o,oo),first_cash_field_difference=str(z.loc[cashdiff,'date'].iloc[0].date())if cashdiff.any()else None,increment_difference=aa['increment_cash']-a['increment_cash']))
 save('fixed_participation_budgets.csv',budgets);save('extra_cost_attribution.csv',stress);save('payment_path_divergences.csv',divergences);save('cash_dependencies.csv',dependency)
 # Daily full event cash dependencies for ALL events, not only known first divergence.
 save('event_entitlement_payment_ledger.csv',payouts);save('restoration_funding_ledger.csv',funding)
 save('account_summary.csv',summary);save('independent_verification.csv',checks);save('year_attribution.csv',years);save('original_event_attribution.csv',attribution)
 # Causal suffix mutation in NEW payment code, at each settlement cutoff and known funding divergence.
 causality=[];sc=schedule_for(d,events,0)
 for dt in ['2023-03-24','2023-08-24','2026-08-03']:
  for first in ['open','post0935']:
   until=pd.Timestamp(dt)+pd.Timedelta('09:41:00')
   dd=d.copy();mm=m.copy();day=until.normalize();future=dd.date.gt(day)
   dd.loc[future,['open','high','low','close','preclose','volume']]*=1.17
   dd.loc[dd.date.eq(day),['high','low','close','volume']]*=1.4
   masklate=(mm.date>day)|((mm.date==day)&mm.clock.gt('09:41'));mm.loc[masklate,['high','low','close','volume']]*=1.4
   om=(mm.date>day)|((mm.date==day)&mm.clock.gt('09:46'));mm.loc[om,'open']*=1.4
   _,ss,ww,pp=r1.pipeline(dd,mm)
   _,o,_,state=account(d,sigs['S1_F1'],op,.3,slip=.001,first_window=first,post=post,schedule=sc,until=until)
   _,oo,_,state2=account(dd,ss['S1_F1'],ww,.3,slip=.001,first_window=first,post=pp,schedule=sc,until=until)
   pd.testing.assert_frame_equal(o,oo,check_exact=True);assert state==state2
   # A later, not-yet-paid event cannot affect prior orders/cash even if changed to unknown.
   sc2={k:(v if k<=day else len(d)+10)for k,v in sc.items()}
   _,ooo,_,state3=account(d,sigs['S1_F1'],op,.3,slip=.001,first_window=first,post=post,schedule=sc2,until=until)
   pd.testing.assert_frame_equal(o,ooo,check_exact=True);assert state==state3
   causality.append(dict(date=dt,first=first,market_future_orders_equal=True,market_future_state_equal=True,future_payments_equal=True))
 save('new_logic_causality.csv',causality);check('six new payment-code future mutation and future schedule cases')
 # Existing fine overlap classification reused byte-exact; inspect only saved known discrepant day's time and aggregation.
 pe=pd.read_csv(Q/'C_post0935_price_evidence.csv',parse_dates=['date'])
 pp=pe[pe.scenario.eq('S1_F1_30_paid_post0935_5')]
 assert len(pp)==286 and int(pp.fine_price_available.sum())==20
 assert int(pp.price_status.eq('agrees_with_qualified_1m').sum())==19
 err=pp[pp.price_status.eq('disagrees_with_qualified_1m')];assert len(err)==1 and err.date.iloc[0]==pd.Timestamp('2026-05-15')
 check('original19 fine matches and one discrepancy reused; no unsupported price substitution')
 for p,h in parents.items():assert sha(p)==h,p
 check('all original evidence unchanged at completion',str(len(parents)))
 check('independent scalar financial verification',str(len(checks))+' accounts; FIFO tax, fee dates, payout clocks, cash, shares, same-capital hold')
 ac=pd.DataFrame(summary);ys=pd.DataFrame(years);ev=pd.DataFrame(attribution)
 cols=['scenario','increment_cash','increment_pct','return_pct','mdd_pct','hold_mdd_pct','relative_mdd_cash','sales','completed','deficit_days','max_consecutive_deficit_days','terminal_missing','fees','dividend_tax','terminal_receivable','terminal_tax_reserve']
 text=['# B16 bounded remote results','All model results; not actual fills. Original uncorrected09:40 proxy retained.']
 for title,data in [('Main and stress',ac[~ac.purpose.str.contains('reference')][cols]),('Fixed budgets',pd.DataFrame(budgets)),('Extra cost vs participation',pd.DataFrame(stress)),('Payment path differences',pd.DataFrame(divergences)),('Cash dependencies',pd.DataFrame(dependency)),('S1 primary years',ys[ys.scenario.str.startswith('S1_F1')&ys.scenario.str.endswith('_e0_d0_main')]),('S1 primary event92',ev[ev.scenario.str.startswith('S1_F1')&ev.scenario.str.endswith('_e0_d0_main')&ev.event.eq('92')]),('Validation',pd.DataFrame(CHECKS))]:
  text+=['## '+title,data.to_markdown(index=False,floatfmt='.6f')]
 (R/'RESULTS_REVIEW.md').write_text('\n\n'.join(text))
 js('validation.json',CHECKS);js('runtime.json',dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],python=sys.version,pip_freeze=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)))
 js('manifest.json',dict(parent='87fb15808cb4c707ace2b510ba9dc6d8dc9696d2',code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],inputs=INPUTS,files={str(p):sha(p)for p in R.rglob('*')if p.is_file()and p.name!='manifest.json'}))
 print('B16_COMPLETE',len(ac),flush=True)
if __name__=='__main__':
 try:run()
 except Exception:
  (R/('failure_'+os.environ.get('GITHUB_RUN_ID','local')+'.txt')).write_text(traceback.format_exc());js('validation.json',CHECKS);raise
