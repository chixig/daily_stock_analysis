#!/usr/bin/env python3
"""B15 R1: immutable-parent, remote-only causal and data evidence repair."""
import os,json,hashlib,zipfile,sys,subprocess,traceback
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_overnight_sell_b15 as old
from foxconn_overnight_sell_b15 import sf,taxrate
P=Path('research/foxconn_overnight_sell_20260921_b15');R=P/'revision_r1';B13=Path('research/foxconn_overnight_20260917_b13')
BASE='9c34181d7b63ccbdc72ac65481a0d3be1f24f471';RULES=['S0','S1_F1','S2_F2'];CHECKS=[];INPUTS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 z=x if isinstance(x,pd.DataFrame)else pd.DataFrame(x);z.to_csv(R/name,index=False);return z
def js(name,x):(R/name).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
def check(name,detail=''):CHECKS.append(dict(name=name,status='PASS',detail=detail))
def audit(d,m):
 a=m.groupby('date').agg(first=('open','first'),last=('close','last'),h5=('high','max'),l5=('low','min'),v5=('volume','sum'),bars=('clock','size'),first_clock=('clock','first'),last_clock=('clock','last'))
 a=d[['date','open','close','high','low','volume']].join(a,on='date');a['endpoint_good']=(a.open-a['first']).abs().lt(.011)&(a.close-a['last']).abs().lt(.011)&a.bars.eq(48)&a.first_clock.eq('09:35')&a.last_clock.eq('15:00')
 a['high_bad']=(a.high-a.h5).abs().ge(.011);a['low_bad']=(a.low-a.l5).abs().ge(.011);a['volume_bad']=(a.v5/a.volume-1).abs().ge(.001)
 a['strict']=a.endpoint_good&~a.high_bad&~a.low_bad&~a.volume_bad
 return a

def pipeline(d,m):
 # QC is returned as an audit annotation only. Causal window constructors never read it.
 au=audit(d,m);ix=pd.Series(np.nan,index=d.index);f1,f2,_=old.features(d,m,ix);masks=old.rule_masks(f1,f2)
 op={};post={};lookup=m[m.clock.eq('09:45')].set_index('date').open
 for i,r in d.iterrows():
  op[i]=[('09:25',float(r.open),'daily_open_indicative')]if pd.notna(r.open)and r.open>0 and r.open<r.limit_up-.005 else []
  p=lookup.get(r.date,np.nan)
  post[i]=[('09:40',float(p),'post0935_window_indicative_unknown')]if pd.notna(p)and p>0 and p<r.limit_up-.005 else []
 return au,{k:masks[k]for k in RULES},op,post

# Account implementation below is a scoped copy of the B15 function; differences
# are parameterized slippage, causal first/retry windows, prefix stopping, and
# explicit missing-window counts. FIFO/capital/T+1 arithmetic is unchanged.
def account(d,mask,win,buffer,conservative=True,pay_delay=False,slip=.0005,first_window="open",post=None,until=None):
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
   ent=shares()*r.dividend_today;recv.append({'amount':ent,'due':i if not pay_delay else len(d)+1});brecv.append({'amount':q*r.dividend_today,'due':i if not pay_delay else len(d)+1})
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
  # Pay at end of ex-date in documented same-pay-date scenario, conservative reserve alternative locks them to end.
  for a in list(recv):
   if a['due']<=i:cash+=a['amount'];daydiv+=a['amount'];div_paid+=a['amount'];recv.remove(a)
  for a in list(brecv):
   if a['due']<=i:bcash+=a['amount'];brecv.remove(a)
  sig=pd.notna(mask.iloc[i]) and bool(mask.iloc[i])
  held_before_sale=shares();uncovered=q-held_before_sale
  # Remaining intraday shortfall is marked at close; use actual buy prices to attribute covered parts.
  today_orders=[o for o in orders if o['date']==day and o['side']=='BUY']
  intra=-uncovered*(r.close-r.open)-sum(o['quantity']*(o['reference']-r.open) for o in today_orders)
  missed_up+=max(0,-intra);avoided_down+=max(0,intra)
  if sig and i<len(d)-1:
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
 if active is not None:episodes.append(dict(entry=active['date'],exit=pd.NaT,days=len(d)-1-active['i'],restored=False))
 z=pd.DataFrame(records);eq=np.r_[initial,z[['equity_open_before','equity_open','equity_close']].to_numpy().ravel()];bh=np.r_[initial,z[['hold_equity_open','hold_equity_after','hold_equity_close']].to_numpy().ravel()]
 rel=eq-bh
 summary=dict(buffer=buffer,mode='conservative' if conservative else 'nominal',settlement='receivable_locked' if pay_delay else 'ex_date_close_scenario',initial=initial,final=eq[-1],hold_final=bh[-1],return_pct=100*(eq[-1]/initial-1),hold_return_pct=100*(bh[-1]/initial-1),increment_cash=eq[-1]-bh[-1],increment_pct=100*(eq[-1]-bh[-1])/initial,mdd_pct=100*(eq/np.maximum.accumulate(eq)-1).min(),hold_mdd_pct=100*(bh/np.maximum.accumulate(bh)-1).min(),relative_mdd_cash=(rel-np.maximum.accumulate(rel)).min(),completed=completed,sales=attempt,skip_t1=skip_t1,skip_missing=skip_missing,sale_blocked=blocked_sell,failed_restore_days=need_count,max_consecutive_deficit_days=max_def_days,insufficient_cash_windows=fundfails,max_extra_cash_required=max_restore_cash,terminal_missing=q-shares(),terminal_cash=cash,terminal_cash_gap=z.restore_cash_gap.iloc[-1],terminal_receivable=z.receivable.iloc[-1],terminal_tax_reserve=z.dividend_tax_reserve.iloc[-1],unobserved_first_windows=unobserved_first_windows,missed_rise_cash=missed_up,avoided_fall_cash=avoided_down,fees=total_fees,dividend_tax=tax_paid)
 return z,pd.DataFrame(orders),pd.DataFrame(episodes),summary

def independent(z,o,buffer,d):
 ds=d[d.date.ge('2020-01-01')].reset_index(drop=True);n=len(z);ds=ds.iloc[:n]
 np.testing.assert_allclose(z.equity_close,z.cash+z.receivable+z.shares*ds.close-z.dividend_tax_reserve,atol=1e-6)
 np.testing.assert_allclose(z.hold_equity_close,1000*ds.close+1000*ds.close.iloc[0]*buffer+1000*ds.dividend_today.cumsum(),atol=1e-6)
 if len(o):
  flow=(o.value*np.where(o.side.eq('SELL'),1,-1)-o.fee-o.dividend_tax).groupby(o.date).sum().reindex(z.date,fill_value=0).to_numpy()
  qty=(o.quantity*np.where(o.side.eq('BUY'),1,-1)).groupby(o.date).sum().reindex(z.date,fill_value=0).to_numpy()
  b=o.groupby(['date','side']).quantity.sum().unstack(fill_value=0);assert not ((b.get('BUY',0)>0)&(b.get('SELL',0)>0)).any()
 else:flow=np.zeros(n);qty=np.zeros(n)
 np.testing.assert_allclose(z.cash,1000*ds.close.iloc[0]*buffer+np.cumsum(flow+z.dividend_received.to_numpy()),atol=1e-5)
 np.testing.assert_array_equal(z.shares,1000+np.cumsum(qty));assert z.cash.min()>=-1e-6
 return dict(check='independent cash, inventory, receivable/equity, identical-capital hold, T+1',status='PASS')

def oldtag(rule,buf,locked):return f'{rule}_{int(buf*100)}_'+('locked'if locked else'restricted')
def readorders(p):
 return pd.read_csv(p,parse_dates=['date'])if p.stat().st_size>5 else pd.DataFrame(columns=['date','clock','side','quantity','reference','value','fee','dividend_tax'])
def orderdiff(a,b,label):
 keys=['date','clock','side'];cols=['quantity','reference','value','fee','dividend_tax'];aa=a[keys+cols].copy();bb=b[keys+cols].copy()
 aa['sequence']=aa.groupby(keys).cumcount();bb['sequence']=bb.groupby(keys).cumcount();z=aa.merge(bb,on=keys+['sequence'],how='outer',suffixes=('_old','_new'),indicator=True)
 changed=z['_merge'].ne('both')
 for c in cols:changed|=~np.isclose(z[c+'_old'],z[c+'_new'],equal_nan=True,atol=1e-8,rtol=0)
 z=z[changed].copy();z.insert(0,'scenario',label);return z.sort_values(keys)

def differences(oz,z,oo,o,label):
 out=[];a=oz.set_index('date');b=z.set_index('date');cols=[c for c in a.columns if c in b.columns]
 for c in cols:
  x=a[c];y=b[c].reindex(a.index)
  changed=~np.isclose(x,y,equal_nan=True,atol=1e-7,rtol=0)
  for day in a.index[changed]:out.append(dict(scenario=label,date=day,field=c,old=x.loc[day],new=y.loc[day]))
 od=orderdiff(oo,o,label);first=od.date.min()if len(od)else pd.NaT
 return out,od,dict(scenario=label,first_order_difference=first,changed_orders=len(od),changed_daily_fields=len(out),first_daily_difference=min((r['date']for r in out),default=pd.NaT),order_equal=len(od)==0)

def annotate_original(d,m,au):
 amap=au.set_index('date');rows=[];deps=[]
 for p in sorted(P.glob('account_S*.csv')):
  tag=p.stem[8:];z=pd.read_csv(p,parse_dates=['date']);o=readorders(P/f'orders_{tag}.csv');inside=o[o.side.eq('BUY')&o.clock.ne('09:25')].copy()
  unknown=z[z.restoration_missing_shares.gt(0)&~z.date.map(amap.strict).fillna(False)]
  for _,r in inside.iterrows():deps.append(dict(account=tag,dependency='actual_intraday_fill_conditioned_on_full_day_QC',date=r.date,clock=r.clock,quantity=r.quantity,reference=r.reference,fee=r.fee,day_qc=bool(amap.loc[r.date,'strict']),available_at='after15:00_or_unknown_provider_latency'))
  for _,r in unknown.iterrows():deps.append(dict(account=tag,dependency='restoration_deficit_on_QC_rejected_day_potential_suppression_not_proven_fill',date=r.date,quantity=r.restoration_missing_shares,day_qc=False,available_at='after15:00_or_unknown_provider_latency'))
  rows.append(dict(account=tag,intraday_buy_orders=len(inside),intraday_quantity=inside.quantity.sum(),intraday_fees=inside.fee.sum(),suppressed_window_exposure_days=len(unknown),first_intraday=inside.date.min()if len(inside)else pd.NaT,classification='no_intraday_or_suppressed_exposure'if len(inside)==len(unknown)==0 else'retrospective_QC_dependency'))
 save('A_original_dependency_summary.csv',rows);save('A_original_dependency_dates.csv',deps)


def open_opportunities(d,win):
 rows=[];paths=[]
 for i,r in d.iloc[:-1].iterrows():
  if r.close<=r.limit_down+.005 or i==0:
   rows.append(dict(ordinal=i,date=r.date,cash=0.,net=0.,status='retained_sale_limit_or_IPO',restore_date=r.date,days_missing=0));continue
  sv=1000*r.close*.9995;cash=sv-sf(sv,r.date,True);div=0.;done=False
  for j in range(i+1,len(d)):
   a=d.iloc[j];div+=1000*a.dividend_today
   if win[j]:
    price=win[j][0][1];bv=1000*price*1.0005;net=cash-bv-sf(bv,a.date)-div
    rows.append(dict(ordinal=i,date=r.date,cash=net,net=100*net/(1000*r.close),status='restored_at_open',restore_date=a.date,restore_clock='09:25',days_missing=j-i,missed_dividend=div,fee=sf(sv,r.date,True)+sf(bv,a.date),extra_cash=max(0,bv+sf(bv,a.date)-cash)))
    paths.append(dict(entry=r.date,date=a.date,missing=0,relative_equity=net));done=True;break
   paths.append(dict(entry=r.date,date=a.date,missing=1000,relative_equity=cash-1000*a.close-div))
  if not done:rows.append(dict(ordinal=i,date=r.date,cash=cash-1000*a.close-div,net=100*(cash-1000*a.close-div)/(1000*r.close),status='unresolved',restore_date=pd.NaT,days_missing=len(d)-1-i,terminal_missing=1000))
 save('A_open_only_opportunities.csv',rows);save('A_open_only_opportunity_paths.csv',paths);return pd.DataFrame(rows)


def minute_quality(d,m,sig,k,au):
 expected=(pd.date_range('2000-01-01 09:31','2000-01-01 11:30',freq='min').strftime('%H:%M').tolist()+pd.date_range('2000-01-01 13:01','2000-01-01 15:00',freq='min').strftime('%H:%M').tolist())
 fine={};q=[];ds=d.set_index('date');fine5={}
 for day,g in k.groupby('date'):
  g=g.sort_values('clock');r=ds.loc[day];grid=g.clock.tolist()==expected
  sane=bool((g.high>=g[['open','close','low']].max(axis=1)-1e-6).all()and(g.low<=g[['open','close','high']].min(axis=1)+1e-6).all()and g.volume.ge(0).all())
  diff=max(abs(g.open.iloc[0]-r.open),abs(g.close.iloc[-1]-r.close),abs(g.high.max()-r.high),abs(g.low.min()-r.low))
  good=grid and sane and diff<.011
  q.append(dict(date=day,grid240=grid,ohlc_sane=sane,daily_price_max_gap=diff,price_qualified=good,volume_unit='unverified_not_used_for_price_qualification'))
  if good:
   fine[day]=g
   gg=g.copy();gg['block']=np.arange(240)//5
   z=gg.groupby('block').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),clock=('clock','last'));fine5[day]=z
 save('B_fine_price_quality.csv',q)
 ma={day:g.set_index('clock')for day,g in m.groupby('date')};rows=[]
 for i,r in d[d.date.ge('2020-01-01')&d.next_open.notna()].iterrows():
  day=r.date;a=au.loc[i];hit=sig['S2_F2'].iloc[i];g=ma.get(day);row=dict(date=day,original_signal=hit,endpoint_good=a.endpoint_good,high_bad=a.high_bad,low_bad=a.low_bad,volume_bad=a.volume_bad,strict=a.strict,original_net=r.net,original_cash=r.cash,fine_qualified=day in fine)
  if g is None:row.update(layer='no5m_unknown',signal_status='unknown');rows.append(row);continue
  pre=g[g.index<='14:50'];direct=bool((pre.high>r.high+.011).any()or(pre.low<r.low-.011).any())
  row['direct_pre_daily_bounds_conflict']=direct
  if day in fine:
   f=fine[day];fp=f[f.clock.le('14:50')];h=fp.high.max();l=fp.low.min();clv=(fp.close.iloc[-1]-l)/(h-l)if h>l else np.nan;fs=clv<=.2 if pd.notna(clv)else pd.NA
   ff=fine5[day].set_index('clock');join=g[['open','high','low','close']].join(ff[['open','high','low','close']],rsuffix='_fine');delta=np.column_stack([abs(join[c]-join[c+'_fine'])for c in ['open','high','low','close']]);per=pd.Series(np.nanmax(delta,axis=1),index=join.index)
   prebad=bool(per[per.index<='14:50'].ge(.011).any());postbad=bool(per[per.index>'14:50'].ge(.011).any())
   status='original_unknown'if pd.isna(hit)else ('fine_unknown'if pd.isna(fs)else('same'if bool(hit)==bool(fs)else'flip'))
   layer='pre1450_price_discrepancy'if prebad else('post1450_price_only'if postbad else'fine_price_consistent')
   row.update(layer=layer,fine_clv=clv,fine_signal=fs,signal_status=status,pre_max_price_gap=per[per.index<='14:50'].max(),post_max_price_gap=per[per.index>'14:50'].max(),volume_timing='unlocalized'if a.volume_bad else'full_day_volume_consistent',post0940_price_gap=abs(float(g.loc['09:45','open'])-float(ff.loc['09:45','open']))if'09:45'in g.index else np.nan)
  else:
   row.update(layer='pre1450_bounds_conflict'if direct else('full_day_consistent_unconfirmed'if a.strict else'anomaly_unlocalized'),signal_status='unconfirmed',volume_timing='unlocalized'if a.volume_bad else'full_day_volume_consistent')
  rows.append(row)
 b=save('B_all_valid_date_quality.csv',rows);hit=b[b.original_signal.eq(True)];assert len(hit)==411;save('B_original_411_signal_audit.csv',hit)
 sums=[]
 for label,g in b.groupby('layer'):
  valid=g[g.original_signal.notna()];hh=valid[valid.original_signal.eq(True)];nn=valid[valid.original_signal.eq(False)]
  sums.append(dict(layer=label,valid=len(valid),hit=len(hh),nonhit=len(nn),unknown=int(g.original_signal.isna().sum()),hit_fine_checkable=int(hh.signal_status.isin(['same','flip']).sum()),hit_flips=int(hh.signal_status.eq('flip').sum()),hit_unconfirmed=int((~hh.signal_status.isin(['same','flip'])).sum()),hit_mean=hh.original_net.mean(),hit_cash=hh.original_cash.sum(),matched_S0_mean=valid.original_net.mean(),matched_S0_cash=valid.original_cash.sum(),improvement=hh.original_net.mean()-valid.original_net.mean(),nonhit_mean=nn.original_net.mean(),all_fine_flips=int(valid.signal_status.eq('flip').sum())))
 save('B_quality_summary.csv',sums);return b,pd.DataFrame(sums),fine5


def causal_tests(d,m,sig,op,post):
 # Whole pipeline is rebuilt, including deliberately changed retrospective QC.
 cases=[('2020-01-03','09:35'),('2024-10-08','09:35'),('2024-10-08','14:50'),('2025-06-30','09:41'),('2026-07-30','14:50')];out=[]
 for dates,clock in cases:
  day=pd.Timestamp(dates);until=day+pd.Timedelta(clock+':00');idx=int(d.index[d.date.eq(day)][0])
  dd=d.copy();mm=m.copy();future=dd.date.gt(day);dd.loc[future,['open','high','low','close','preclose','volume']]*=1.17
  # Current final H/L/V are after the cutoff; do not mutate earlier known opening price.
  dd.loc[dd.date.eq(day),'high']*=1.5;dd.loc[dd.date.eq(day),'low']*=.5;dd.loc[dd.date.eq(day),'volume']*=1.5
  mm.loc[(mm.date>day)|((mm.date==day)&mm.clock.gt(clock)),['high','low','close','volume']]*=1.4
  # An end-labelled bar open has event_time five minutes earlier. Keep an already observed open unchanged.
  open_event=pd.to_datetime(mm.clock,format='%H:%M')-pd.Timedelta(minutes=5)
  change_open=(mm.date>day)|((mm.date==day)&open_event.dt.strftime('%H:%M').gt(clock));mm.loc[change_open,'open']*=1.4
  _,ss,oo,pp=pipeline(dd,mm)
  # Prefix drops every post-cutoff bar, retaining a stub of an ongoing bar's OPEN if already observable.
  pre=m[(m.date<day)|((m.date==day)&((pd.to_datetime(m.clock,format='%H:%M')-pd.Timedelta(minutes=5)).dt.strftime('%H:%M')<=clock))].copy()
  ongoing=(pre.date==day)&pre.clock.gt(clock);pre.loc[ongoing,['high','low','close','volume']]=np.nan
  dp=d.iloc[:idx+1].copy();dp.loc[dp.date.eq(day),['high','low','close','volume']]=np.nan
  _,sp,ow,pw=pipeline(dp,pre)
  for rule in RULES:
   for first in ['open','post0935']:
    _,a,_,ast=account(d,sig[rule],op,.3,post=post,first_window=first,until=until)
    _,b,_,bst=account(dd,ss[rule],oo,.3,post=pp,first_window=first,until=until)
    _,c,_,cst=account(dp,sp[rule],ow,.3,post=pw,first_window=first,until=until)
    pd.testing.assert_frame_equal(a,b,check_exact=True);pd.testing.assert_frame_equal(a,c,check_exact=True)
    assert ast==bst==cst
    out.append(dict(date=day,cutoff=clock,rule=rule,first_window=first,mutation_orders_equal=True,prefix_orders_equal=True,cash_inventory_state_equal=True))
 save('A_execution_causality_tests.csv',out);check('execution prefix and future suffix mutation',f'{len(out)} account/cutoff combinations; pipeline QC/windows/signals rebuilt')
 # Reviewer counterexample: choose first original intraday BUY and corrupt only the later final high.
 oo=readorders(P/'orders_S0_0_restricted.csv');inside=oo[oo.side.eq('BUY')&oo.clock.lt('15:00')&oo.clock.ne('09:25')];assert len(inside)>0
 r=inside.iloc[0];day=r.date;clock=r.clock;until=day+pd.Timedelta(clock+':00');au=audit(d,m);mc=m.copy();mc.attrs['qualified_days']=set(au.index[au.strict]);w=old.windows_for(d,mc)
 dd=d.copy();dd.loc[dd.date.eq(day),'high']*=1.5;au2=audit(dd,m);mc2=m.copy();mc2.attrs['qualified_days']=set(au2.index[au2.strict]);w2=old.windows_for(dd,mc2)
 _,x,_,_=account(d,sig['S0'],w,0,until=until);_,y,_,_=account(dd,sig['S0'],w2,0,until=until);diff=orderdiff(x,y,'old_full_day_gate_negative_control');assert len(diff)>0
 save('A_old_gate_negative_control.csv',diff);check('negative control detects old execution leakage',f'{day.date()} cutoff{clock}; changed later daily high changes {len(diff)} earlier order rows')


def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true','All price processing must run on GitHub';R.mkdir(exist_ok=True)
 man=json.loads((P/'manifest.json').read_text())
 for path,h in man['files'].items():assert sha(path)==h,path
 check('immutable B15 snapshot verified',str(len(man['files']))+' parent files')
 for path in ['research/foxconn_t0_20260913/source/601138-full-5min-history.zip',str(B13/'tdx_recovered_1m.csv')]:
  expected=man['inputs'].get(path)if'full-5min'in path else json.loads((B13/'manifest.json').read_text())['files'][path]
  assert sha(path)==expected;INPUTS[path]=expected
 for path in [P/'daily_ledger.csv',P/'signals.csv',P/'accounts.csv',P/'events_leave_one_out.csv',P/'manifest.json',R/'protocol.md']:
  INPUTS[str(path)]=sha(path)
 d=pd.read_csv(P/'daily_ledger.csv',parse_dates=['date','exit_date']);sigold=pd.read_csv(P/'signals.csv',parse_dates=['date']);accounts_old=pd.read_csv(P/'accounts.csv')
 with zipfile.ZipFile('research/foxconn_t0_20260913/source/601138-full-5min-history.zip')as z:m=pd.read_csv(z.open(next(n for n in z.namelist()if n.endswith('601138_5min_all.csv'))))
 m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
 k=pd.read_csv(B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);k=k[k.date.le('2026-09-11')];k['clock']=k.datetime.dt.strftime('%H:%M')
 au,sig,op,post=pipeline(d,m);save('A_QC_annotations_only.csv',au)
 for rule in RULES:pd.testing.assert_series_equal(sig[rule].reset_index(drop=True),sigold[rule].astype('boolean'),check_names=False)
 recalc=old.ledger(d)
 np.testing.assert_allclose(recalc[['cash','net','fee']],d[['cash','net','fee']],equal_nan=True,atol=1e-8)
 js('unchanged_parent_proof.json',dict(original_results_sha256=sha(P/'results.csv'),original_signals_sha256=sha(P/'signals.csv'),S0_independent_cashflow_recomputed_equal=True,S1_F1_and_S2_F2_signals_reconstructed_equal=True,parent_snapshot=BASE))
 check('opportunity and frozen signals unaffected')
 annotate_original(d,m,au)
 # Reuse the original replay byte snapshots and verify engine arithmetic on representative baselines.
 mc=m.copy();mc.attrs['qualified_days']=set(au.index[au.strict]);rw=old.windows_for(d,mc)
 for rule in RULES:
  z,o,e,a=account(d,sig[rule],rw,.3);oz=pd.read_csv(P/f'account_{oldtag(rule,.3,False)}.csv',parse_dates=['date']);pd.testing.assert_frame_equal(z,oz,check_exact=False,atol=1e-7,rtol=0)
 check('new engine replay mode reproduces all three original30pct baselines')
 newop=open_opportunities(d,op);oldop=pd.read_csv(P/'conservative_opportunities.csv',parse_dates=['date','restore_date']);comp=oldop.merge(newop,on=['ordinal','date'],suffixes=('_old','_openonly'));save('A_opportunity_comparison.csv',comp)
 ops=[]
 for rule in RULES:
  idx=d.index[d.date.ge('2020-01-01')&d.next_open.notna()&sig[rule].fillna(False)];g=comp[comp.ordinal.isin(idx)]
  ops.append(dict(rule=rule,n=len(g),old_cash=g.cash_old.sum(),new_cash=g.cash_openonly.sum(),old_mean=g.net_old.mean(),new_mean=g.net_openonly.mean(),changed=int((g.cash_old-g.cash_openonly).abs().gt(1e-7).sum()),delayed_new=int(g.days_missing_openonly.gt(1).sum())))
 save('A_opportunity_summary.csv',ops)
 allsum=[];diffs=[];odiffs=[];diffsum=[];checks=[];book={};years=[];events=[];original_events=pd.read_csv(P/'events_leave_one_out.csv')
 def execute(rule,buf,locked,first,bp,work):
  key=f'{rule}_{int(buf*100)}_{"locked"if locked else"paid"}_{first}_{bp}';z,o,e,a=account(d,sig[rule],op,buf,pay_delay=locked,slip=bp/10000,first_window=first,post=post)
  v=independent(z,o,buf,d);v['scenario']=key;checks.append(v)
  save('account_'+key+'.csv',z);save('orders_'+key+'.csv',o);save('episodes_'+key+'.csv',e);a.update(scenario=key,rule=rule,work=work,first_window=first,slip_bp=bp,deficit_days=int(z.restoration_missing_shares.gt(0).sum()),intraday_buys=int((o.side.eq('BUY')&o.clock.ne('09:25')).sum())if len(o)else 0)
  tag=oldtag(rule,buf,locked);oz=pd.read_csv(P/f'account_{tag}.csv',parse_dates=['date']);oo=readorders(P/f'orders_{tag}.csv');dd,od,ds=differences(oz,z,oo,o,key);diffs.extend(dd);odiffs.append(od);diffsum.append(ds);a['first_difference_from_B15']=ds['first_order_difference'];a['old_increment_cash']=float(accounts_old[(accounts_old.id==rule)&accounts_old.buffer.eq(buf)&accounts_old['mode'].eq('conservative')&accounts_old.settlement.eq('receivable_locked'if locked else'ex_date_close_scenario')].increment_cash.iloc[0]);allsum.append(a);book[key]=(z,o,a)
  zz=z.copy();zz['delta']=zz.relative_equity.diff().fillna(zz.relative_equity.iloc[0]);zz['year']=zz.date.dt.year
  for yr,g in zz.groupby('year'):years.append(dict(scenario=key,year=yr,increment_cash=g.delta.sum(),fees=g.fees.sum(),dividend_tax=g.dividend_tax_paid.sum(),sales=int(g.sell_quantity.gt(0).sum()),deficit_days=int(g.restoration_missing_shares.gt(0).sum()),ending_relative=g.relative_equity.iloc[-1]))
  emap={}
  for _,er in original_events[original_events.id.eq(rule)].iterrows():
   for day in str(er.dates).split(';'):emap[pd.Timestamp(day)]=int(er.event)
  label='before_first_sale';labels=[]
  for _,rr in zz.iterrows():
   if rr.sell_quantity>0:label=str(emap.get(rr.date,'unmapped'))
   labels.append(label)
  zz['original_event']=labels
  for ev,g in zz.groupby('original_event'):events.append(dict(scenario=key,original_event=ev,increment_cash=g.delta.sum(),start=g.date.min(),end=g.date.max(),method='daily relative change assigned to latest actual sale original event; residual holding attribution retained'))
  return key
 for rule in RULES:
  for buf in [0,.1,.3]:
   for locked in [False,True]:execute(rule,buf,locked,'open',5,'A')
 print('A_ACCOUNTS_COMPLETE',flush=True)
 bs,bsum,fine5=minute_quality(d,m,sig,k,au)
 # Gate C on exact baseline order evidence, not an assumption about no deficits.
 gate=[]
 for rule in ['S1_F1','S0']:
  key=f'{rule}_30_paid_open_5';z,o,a=book[key];oo=readorders(P/f'orders_{oldtag(rule,.3,False)}.csv');eq=len(orderdiff(oo,o,key))==0
  gate.append(dict(rule=rule,openonly_orders_equal_original=eq,increment_cash=a['increment_cash'],old_increment_cash=a['old_increment_cash'],causal_openonly_baseline_available=True,C_scope='continue_fixed_matrix; original result not execution-certified'))
 save('C_dependency_gate.csv',gate)
 # A provides a causal indicative baseline even if it differs; inspect S1 original positive source.
 s1gate=gate[0];assert s1gate['openonly_orders_equal_original'],'S1_F1 original positive baseline changed: stop dependent C pending attribution'
 for rule in ['S1_F1','S0']:
  for locked in [False,True]:
   for first,bp in [('open',10),('post0935',5),('post0935',10)]:execute(rule,.3,locked,first,bp,'C')
 print('C_MATRIX_COMPLETE',flush=True)
 save('account_summary.csv',allsum);save('account_differences.csv',diffs);save('order_differences.csv',pd.concat(odiffs,ignore_index=True));save('account_difference_summary.csv',diffsum);save('independent_account_checks.csv',checks);save('account_year_attribution.csv',years);save('account_original_event_attribution.csv',events)
 # Original participation dates are diagnostic, not imposed on new finite accounts.
 diagnostics=[];dsums=[]
 for rule in ['S1_F1','S0']:
  oo=readorders(P/f'orders_{oldtag(rule,.3,False)}.csv');dates=oo.loc[oo.side.eq('SELL'),'date'];g=d[d.date.isin(dates)].copy()
  for first,bp in [('open',5),('open',10),('post0935',5),('post0935',10),('0935_close_diagnostic',5),('0935_close_diagnostic',10)]:
   lookup=m[m.clock.eq('09:45'if first=='post0935'else'09:35')].set_index('date')['open'if first=='post0935'else'close']
   g['test_buy']=g.next_open if first=='open'else g.exit_date.map(lookup)
   known=g.test_buy.notna();v=old.ledger(g[known],slip=bp/10000,buycol='test_buy');unknown=g[~known]
   for _,r in v.iterrows():diagnostics.append(dict(rule=rule,first_window=first,slip_bp=bp,date=r.date,exit_date=r.exit_date,cash=r.cash,net=r.net,fee=r.fee,status='indicative_independent_opportunity_not_account'))
   for _,r in unknown.iterrows():diagnostics.append(dict(rule=rule,first_window=first,slip_bp=bp,date=r.date,exit_date=r.exit_date,status='unknown_price_not_zero'))
   dsums.append(dict(rule=rule,first_window=first,slip_bp=bp,frozen_dates=len(g),known=int(known.sum()),unknown=int((~known).sum()),known_cash=v.cash.sum(),known_mean=v.net.mean(),fees=v.fee.sum(),basis='original30pct paid actual-sale dates; independent cash and gross missed dividend'))
 save('C_fixed_participation_diagnostics.csv',diagnostics);save('C_fixed_participation_summary.csv',dsums)
 # Price evidence labels never influence account orders. Unknown prices do not certify fills.
 pe=[]
 for key,(z,o,a)in book.items():
  if a['first_window']!='post0935':continue
  for _,r in o[o.side.eq('BUY')&o.clock.eq('09:40')].iterrows():
   f=fine5.get(r.date);gap=abs(r.reference-f.set_index('clock').loc['09:45','open'])if f is not None else np.nan
   pe.append(dict(scenario=key,date=r.date,clock=r.clock,quantity=r.quantity,reference=r.reference,fine_price_available=f is not None,price_gap=gap,price_status='agrees_with_qualified_1m'if pd.notna(gap)and gap<.011 else('disagrees_with_qualified_1m'if pd.notna(gap)else'unknown_no_qualified_fine_overlap'),fill_status='unproven_auction_queue_receipt_and_capacity'))
 save('C_post0935_price_evidence.csv',pe)
 causal_tests(d,m,sig,op,post)
 check('independent financial invariants',str(len(checks))+' new continuous accounts')
 for path,h in man['files'].items():assert sha(path)==h,path
 check('all500 original evidence files unchanged after R1')
 ac=pd.DataFrame(allsum);ys=pd.DataFrame(years);parts=['# B15 R1 remote reviewer tables','Historical model outputs only. Ex-post replay / open-only indicative rule / post0935 unknown-price diagnostics are distinct.']
 def table(title,x):parts.extend(['## '+title,x.to_markdown(index=False,floatfmt='.6f')])
 table('A old dependence',pd.read_csv(R/'A_original_dependency_summary.csv').query("account.str.contains('S0_|S1_F1_|S2_F2_')",engine='python'))
 table('A opportunity comparison',pd.DataFrame(ops))
 cols=['scenario','old_increment_cash','increment_cash','return_pct','increment_pct','mdd_pct','hold_mdd_pct','relative_mdd_cash','sales','completed','deficit_days','max_consecutive_deficit_days','terminal_missing','terminal_cash_gap','fees','dividend_tax','intraday_buys','unobserved_first_windows','first_difference_from_B15']
 table('All A and C accounts',ac[cols]);table('B quality strata',bsum);table('B independent signal comparison',bs[bs.fine_qualified].groupby(['original_signal','signal_status'],dropna=False).size().reset_index(name='n'));table('C fixed-date diagnostics',pd.DataFrame(dsums));table('C annual attribution30pct',ys[ys.scenario.str.contains('_30_')]);table('C price evidence summary',pd.DataFrame(pe).groupby(['scenario','price_status']).agg(orders=('date','size'),shares=('quantity','sum')).reset_index());table('C largest original-event contributions',pd.DataFrame(events).query("scenario.str.contains('S1_F1_30_paid')",engine='python').sort_values('increment_cash',ascending=False).groupby('scenario').head(5));table('Execution tests',pd.DataFrame(CHECKS))
 table('First order divergence cases',pd.concat(odiffs,ignore_index=True).groupby('scenario',sort=False).head(2))
 (R/'REVIEW.md').write_text('\n\n'.join(parts))
 js('validation.json',CHECKS);js('runtime.json',dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],command='python scripts/research/foxconn_overnight_sell_b15_r1.py',python=sys.version,pip_freeze=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)))
 js('manifest.json',dict(parent=BASE,code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],inputs=INPUTS,files={str(p):sha(p)for p in R.rglob('*')if p.is_file()and p.name!='manifest.json'}))
 print(json.dumps(dict(accounts=len(ac),original_signals=int(bs.original_signal.eq(True).sum()),checks=CHECKS),ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:run()
 except Exception:
  R.mkdir(exist_ok=True);(R/('failure_'+os.environ.get('GITHUB_RUN_ID','local')+'.txt')).write_text(traceback.format_exc());js('validation.json',CHECKS);raise
