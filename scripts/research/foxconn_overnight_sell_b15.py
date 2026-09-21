#!/usr/bin/env python3
"""B15: remote-only independent overnight sale/repurchase research."""
import os,json,hashlib,zipfile,math,sys,platform,subprocess,traceback
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
import numpy as np
import pandas as pd
import requests
import foxconn_t0_audit as old
R=Path('research/foxconn_overnight_sell_20260921_b15')
P=Path('research/foxconn_t0_20260913'); B2=Path('research/foxconn_t0_20260913_b02'); B8=Path('research/foxconn_overnight_20260916_b08')
DIV={'2019-06-20':.129,'2020-06-30':.2,'2021-07-27':.25,'2022-08-05':.5,'2023-07-28':.55,'2024-08-15':.58,'2025-07-31':.64,'2026-01-16':.33,'2026-08-03':.65}
CHECKS=[]; LIMITS=[]; INPUTS={}; SOURCELOG=[]
def js(name,obj):
 (R/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str),encoding='utf8')
def save(name,x):
 z=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x);z.to_csv(R/name,index=False);return z
def check(name,fn):
 try:
  fn(); CHECKS.append({'name':name,'status':'PASS'})
 except Exception as e:
  CHECKS.append({'name':name,'status':'FAIL','detail':str(e)});js('validation.json',CHECKS);raise

def fee(v,date,sell=False,current=False):
 dt=pd.to_datetime(date)
 tr=np.where(dt<pd.Timestamp('2022-04-29'),.00002,.00001) if not current else .00001
 st=np.where(dt<pd.Timestamp('2023-08-28'),.001,.0005) if not current else .0005
 return np.maximum(np.asarray(v)*.0001354,5)+np.asarray(v)*(tr+(st if sell else 0))
def sf(v,date,sell=False,current=False):return float(fee(v,date,sell,current)) if v>0 else 0.
def price_limit(p,up):return float((Decimal(str(p))*Decimal('1.10' if up else '0.90')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
def ledger(g,slip=.0005,q=1000,sellcol='close',buycol='next_open',tax=0.,current=False,reverse=False):
 z=g.copy();sv=q*z[sellcol]*(1-slip);bv=q*z[buycol]*(1+slip)
 if reverse:
  bv=q*z[sellcol]*(1+slip);sv=q*z[buycol]*(1-slip)
  fc=fee(bv,z.date,False,current)+fee(sv,z.exit_date,True,current)
  net=sv-bv-fc+q*z.dividend*(1-tax)
 else:
  fc=fee(sv,z.date,True,current)+fee(bv,z.exit_date,False,current)
  net=sv-bv-fc-q*z.dividend*(1-tax)
 z['sale_value']=sv;z['buy_value']=bv;z['fee']=fc;z['cash']=net
 z['net']=100*net/(q*z.close);z['gross']=100*(z[sellcol]-z[buycol]-z.dividend*(1-tax))/z.close
 z['price_gross_cash']=q*(z[sellcol]-z[buycol]);z['economic_gross_cash']=z.price_gross_cash-q*z.dividend*(1-tax)
 z['extra_cash']=np.maximum(0,bv+fee(bv,z.exit_date,False,current)-(sv-fee(sv,z.date,True,current))) if not reverse else np.nan
 return z

def metrics(g):
 if len(g)==0:return {'n':0}
 x=g.net.to_numpy(float);c=g.cash.to_numpy(float);run=mx=0
 for v in x:run=run+1 if v<0 else 0;mx=max(mx,run)
 def pf(a):return float(a[a>0].sum()/-a[a<0].sum()) if (a<0).any() else np.nan
 return dict(n=len(g),years=g.date.dt.year.nunique(),months=g.date.dt.to_period('M').nunique(),mean=x.mean(),median=np.median(x),win=100*(x>0).mean(),cash=c.sum(),mean_cash=c.mean(),pf=pf(x),pf_cash=pf(c),worst=x.min(),worst_cash=c.min(),tail5=np.sort(x)[:max(1,math.ceil(.05*len(x)))].mean(),tail5_cash=np.sort(c)[:max(1,math.ceil(.05*len(c)))].mean(),longest_loss=mx,fee=g.fee.sum(),max_extra_cash=g.extra_cash.max() if 'extra_cash'in g else np.nan,need_extra_n=int(g.extra_cash.gt(0).sum()) if 'extra_cash'in g else 0)

def boot(g,h):
 if len(g)==0 or not h.any():return {}
 a=pd.DataFrame({'month':g.date.dt.to_period('M'),'s':g.net.where(h,0),'n':h.astype(int),'b':g.net,'bn':1}).groupby('month').sum().to_numpy()
 rng=np.random.default_rng(601138);v=a[rng.integers(0,len(a),(2000,len(a)))].sum(axis=1);v=v[v[:,1]>0]
 me=v[:,0]/v[:,1];delta=me-v[:,2]/v[:,3]
 return dict(ci_low=np.quantile(me,.025),ci_high=np.quantile(me,.975),increment=g.loc[h,'net'].mean()-g.net.mean(),inc_low=np.quantile(delta,.025),inc_high=np.quantile(delta,.975),bootstrap_valid=len(v))

def features(d,m,ix):
 # Cumulative price chain is rebuilt causally, not reused from any future-normalized file.
 chain=(d.close/d.preclose).cumprod()*100
 s1=pd.DataFrame({'clv':(d.close-d.low)/(d.high-d.low).replace(0,np.nan),'r3':100*(chain/chain.shift(3)-1),'vr':d.volume/d.volume.shift().rolling(20).mean(),'relative':chain.pct_change(fill_method=None)-ix.pct_change(fill_method=None)}).shift()
 a=m[m.clock.le('14:50')].groupby('date').agg(p=('close','last'),h=('high','max'),l=('low','min'),v=('volume','sum'),bars=('clock','size'),nonpos=('volume',lambda x:int((x<=0).sum())))
 a=a.reindex(pd.DatetimeIndex(d.date));a.index=d.index
 a.loc[a.bars.ne(46)|a.nonpos.gt(0),['p','h','l','v']]=np.nan
 # chain[t]/close[t]=chain[t-1]/preclose[t], so t final close cancels exactly.
 factor=chain.shift()/d.preclose
 s2=pd.DataFrame({'clv':(a.p-a.l)/(a.h-a.l).replace(0,np.nan),'r3':100*(a.p*factor/chain.shift(3)-1),'vr':a.v/a.v.shift().rolling(20).mean(),'relative':np.nan},index=d.index)
 for f in [s1,s2]:f['gapdays']=(d.exit_date-d.date).dt.days.astype(float)
 return s1,s2,a

def rule_masks(f1,f2):
 out={'S0':pd.Series(True,index=f1.index,dtype='boolean')}
 for s,f in [('S1',f1),('S2',f2)]:
  specs=[('clv','ge',.8),('clv','le',.2),('r3','ge',4),('r3','le',-4),('vr','ge',1.5),('vr','le',.8),('relative','gt',0),('gapdays','ge',3)]
  for k,(col,fn,x) in enumerate(specs,1):
   if s=='S2' and k==8:continue
   out[f'{s}_F{k}']=getattr(f[col],fn)(x).astype('boolean').where(f[col].notna(),pd.NA)
 return out

def fetch_sources():
 urls={
 'sse_2018':'https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml',
 'sse_2026':'https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml',
 'stamp2023':'https://m.mof.gov.cn/czxw/202308/t20230827_3904226.htm',
 'div_tax2015':'https://www.csrc.gov.cn/csrc/c100028/c1001875/content.shtml',
 'fifo':'https://www.csrc.gov.cn/shenzhen/c105614/c1575308/content.shtml',
 'div_table':'https://money.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/601138.phtml',
 'div2026_primary':'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-07-24/601138_20260724_AYP4.pdf',
 'transfer_report':'https://finance.sina.cn/2022-04-28/detail-imcwipii6993883.d.html',
 'div2019_primary':'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2019-06-14/601138_20190614_1.pdf',
 'div2020_primary':'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2020-06-20/601138_20200620_1.pdf',
 'div2022_issuer_reprint':'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=8390542&stockid=601138',
 'div2023_issuer_reprint':'https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=9364665&stockid=601138',
 'div2024_issuer_reprint':'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=10363980&stockid=601138',
 'div2026half_primary':'https://static.cninfo.com.cn/finalpage/2026-01-09/1224926202.PDF'}
 (R/'sources').mkdir(exist_ok=True)
 for key,url in urls.items():
  try:
   r=requests.get(url,timeout=25,headers={'User-Agent':'Mozilla/5.0'});r.raise_for_status();p=R/'sources'/(key+('.pdf' if '.pdf' in url.lower() else '.html'));p.write_bytes(r.content)
   SOURCELOG.append(dict(id=key,url=url,status=r.status_code,bytes=len(r.content),sha256=hashlib.sha256(r.content).hexdigest(),path=str(p)))
  except Exception as e:SOURCELOG.append(dict(id=key,url=url,status='FAILED',error=str(e)))
 save('sources.csv',SOURCELOG)

# Window evidence for conservative restoration. Date/bar opening information is never used as a condition signal.
def windows_for(d,m):
 out={}; good=m.copy(); good=good[(good.volume>0)&(good.high>=good.low)]
 for i,r in d.iterrows():
  w=[]
  if r.volume>0 and pd.notna(r.open) and r.open<r.limit_up-.005:w.append(('09:25',float(r.open),'open_proxy'))
  if i in m.attrs.get('qualified_days',set()):
   for b in good[good.date.eq(r.date)].itertuples():
    if b.high<r.limit_up-.005:w.append((b.clock,float(b.close),'complete_bar_proxy'))
  out[i]=w
 return out

def conservative_opportunities(d,win):
 rows=[];path=[]
 for i in range(len(d)-1):
  r=d.iloc[i];q=1000
  if r.close<=r.limit_down+.005 or r.volume<=0 or i==0:
   rows.append(dict(ordinal=i,date=r.date,status='retained_sale_restricted',cash=0.,net=0.,fee=0.,extra_cash=0.,days_missing=0,restore_date=r.date,auction_quantity='unknown'));continue
  sv=q*r.close*.9995;fc=sf(sv,r.date,True);cash=sv-fc;missdiv=0.;restored=False
  for j in range(i+1,len(d)):
   a=d.iloc[j];missdiv+=q*a.dividend_today
   if win[j]:
    clock,price,kind=win[j][0];bv=q*price*1.0005;bf=sf(bv,a.date);net=cash-bv-bf-missdiv
    rows.append(dict(ordinal=i,date=r.date,status='completed',cash=net,net=100*net/(q*r.close),fee=fc+bf,extra_cash=max(0,bv+bf-cash),days_missing=j-i,restore_date=a.date,restore_clock=clock,restore_price=price,restore_kind=kind,missed_dividend=missdiv,auction_quantity='unknown'))
    path.append(dict(entry=r.date,date=a.date,uncovered_shares_before=1000,relative_equity=net,restored=True));restored=True;break
   relative=cash-q*a.close-missdiv
   path.append(dict(entry=r.date,date=a.date,uncovered_shares_before=1000,relative_equity=relative,restored=False))
  if not restored:
   a=d.iloc[-1];v=q*a.close*1.0005;net=cash-q*a.close-missdiv
   rows.append(dict(ordinal=i,date=r.date,status='unresolved',cash=net,net=100*net/(q*r.close),fee=fc,extra_cash=max(0,v+sf(v,a.date)-cash),days_missing=len(d)-1-i,restore_date=pd.NaT,terminal_missing_shares=q,missed_dividend=missdiv,auction_quantity='unknown'))
 save('conservative_opportunity_paths.csv',path)
 return save('conservative_opportunities.csv',rows)

def taxrate(acquired,sold):
 # Calendar-month/year boundaries; holding ends day before disposal.
 end=sold-pd.Timedelta(days=1)
 if end<acquired+pd.DateOffset(months=1):return .2
 if end<acquired+pd.DateOffset(years=1):return .1
 return 0.

def account(d,mask,win,buffer,conservative=True,pay_delay=False):
 start=d.index[d.date.ge('2020-01-01')][0];q=1000;initial=q*d.loc[start,'close']*(1+buffer)
 cash=q*d.loc[start,'close']*buffer;bcash=cash;recv=[];brecv=[]
 lots=[{'q':q,'acquired':d.loc[start,'date']-pd.DateOffset(years=2),'divps':0.}]
 records=[];orders=[];episodes=[];active=None;attempt=0;completed=0;skip_t1=0;skip_missing=0;blocked_sell=0;need_count=0
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
  opportunities=win[i] if conservative else [('09:25',float(r.open),'nominal_open')]
  # Cash shortages cannot be remedied by repeated minimum-fee orders at the SAME observation.
  for clock,price,kind in opportunities:
   missing=q-shares()
   if missing==0:break
   fullvalue=missing*price*1.0005;need=max(0,fullvalue+sf(fullvalue,day)-(cash-reserve(day)));max_restore_cash=max(max_restore_cash,need)
   if need>1e-7:fundfails+=1
   n=missing
   while n>0 and n*price*1.0005+sf(n*price*1.0005,day)>cash-reserve(day)+1e-8:n-=100
   if n<=0:continue
   v=n*price*1.0005;cost=sf(v,day);cash-=v+cost;total_fees+=cost;day_fees+=cost;net_trade-=v+cost;day_buys+=n
   lots.append({'q':n,'acquired':day,'divps':0.});orders.append(dict(date=day,clock=clock,side='BUY',quantity=n,reference=price,value=v,fee=cost,dividend_tax=0.,cash_after=cash,shares_after=shares(),kind=kind))
   if shares()==q and active is not None:
    episodes.append(dict(entry=active['date'],exit=day,days=i-active['i'],sale_cash=active['sale_cash'],final_cash=cash,restored=True));active=None;completed+=1
  mark=price if day_buys else r.open
  eq_open=cash+sum(a['amount']for a in recv)+shares()*mark-reserve(day)
  bmark=bcash+sum(a['amount']for a in brecv)+q*mark
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
    v=q*r.close*.9995;cost=sf(v,day,True);cash+=v-cost-taxes;total_fees+=cost;day_fees+=cost;tax_paid+=taxes;daytax+=taxes;net_trade+=v-cost-taxes
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
  records.append(dict(date=day,cash=cash,receivable=ar,shares=shares(),settled_next_day=shares(),dividend_tax_reserve=tax_res,fees=day_fees,dividend_tax_paid=daytax,dividend_received=daydiv,buy_quantity=day_buys,sell_quantity=day_sells,restoration_missing_shares=uncovered,equity_open_before=eq_open_before,equity_open=eq_open,equity_close=eq,hold_equity_open=bopen,hold_equity_after=bmark,hold_equity_close=beq,relative_equity=eq-beq,restore_cash_gap=max(0,(q-shares())*r.close*1.0005+sf((q-shares())*r.close*1.0005,day)-cash+tax_res)if shares()<q else 0.))
 if active is not None:episodes.append(dict(entry=active['date'],exit=pd.NaT,days=len(d)-1-active['i'],restored=False))
 z=pd.DataFrame(records);eq=np.r_[initial,z[['equity_open_before','equity_open','equity_close']].to_numpy().ravel()];bh=np.r_[initial,z[['hold_equity_open','hold_equity_after','hold_equity_close']].to_numpy().ravel()]
 rel=eq-bh
 summary=dict(buffer=buffer,mode='conservative' if conservative else 'nominal',settlement='receivable_locked' if pay_delay else 'ex_date_close_scenario',initial=initial,final=eq[-1],hold_final=bh[-1],return_pct=100*(eq[-1]/initial-1),hold_return_pct=100*(bh[-1]/initial-1),increment_cash=eq[-1]-bh[-1],increment_pct=100*(eq[-1]-bh[-1])/initial,mdd_pct=100*(eq/np.maximum.accumulate(eq)-1).min(),hold_mdd_pct=100*(bh/np.maximum.accumulate(bh)-1).min(),relative_mdd_cash=(rel-np.maximum.accumulate(rel)).min(),completed=completed,sales=attempt,skip_t1=skip_t1,skip_missing=skip_missing,sale_blocked=blocked_sell,failed_restore_days=need_count,max_consecutive_deficit_days=max_def_days,insufficient_cash_windows=fundfails,max_extra_cash_required=max_restore_cash,terminal_missing=q-shares(),terminal_cash=cash,terminal_cash_gap=z.restore_cash_gap.iloc[-1],terminal_receivable=z.receivable.iloc[-1],terminal_tax_reserve=z.dividend_tax_reserve.iloc[-1],missed_rise_cash=missed_up,avoided_fall_cash=avoided_down,fees=total_fees,dividend_tax=tax_paid)
 return z,pd.DataFrame(orders),pd.DataFrame(episodes),summary

def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true','Market computation must be remote'
 R.mkdir(parents=True,exist_ok=True)
 # All prerequisite hash checks occur on runner. Local machine never loads a price series.
 for root,names,key in [(P,['results/daily_features_and_cashflows.csv','source/601138-full-5min-history.zip','source/baostock_raw_crosscheck.csv'],'sha256'),(B2,['source/sse_index.csv'],'files'),(B8,['corporate_actions.csv'],'files')]:
  man=json.loads((root/'manifest.json').read_text())
  for name in names:
   p=root/name;h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==man[key][str(p)],str(p);INPUTS[str(p)]=h
 CHECKS.append(dict(name='inherited input hashes',status='PASS'))
 d=pd.read_csv(P/'results/daily_features_and_cashflows.csv',parse_dates=['date']).sort_values('date').reset_index(drop=True)
 d['exit_date']=d.date.shift(-1);d['next_open']=d.open.shift(-1);d['dividend_today']=d.date.dt.strftime('%Y-%m-%d').map(DIV).fillna(0);d['dividend']=d.dividend_today.shift(-1).fillna(0);d['ordinal']=range(len(d));d['gapdays']=(d.exit_date-d.date).dt.days
 d['limit_up']=d.preclose.map(lambda p:price_limit(p,True));d['limit_down']=d.preclose.map(lambda p:price_limit(p,False));d['close_auction_regime']=d.date.ge('2018-08-20')
 assert len(d)==2007 and str(d.date.max().date())=='2026-09-11' and not d.date.duplicated().any()
 assert d[['open','high','low','close','preclose','volume']].notna().all().all()
 assert (d.volume>0).all() and (d.high>=d[['open','low','close']].max(axis=1)).all() and (d.low<=d[['open','close']].min(axis=1)).all()
 assert d.tradestatus.astype(str).eq('1').all()
 raw=pd.read_csv(P/'source/baostock_raw_crosscheck.csv',parse_dates=['date']).set_index('date');cross=d[['date','open','close']].join(raw[['open','close']],on='date',rsuffix='_cross');cross['open_gap']=cross.open-cross.open_cross;cross['close_gap']=cross.close-cross.close_cross
 assert cross.open_cross.notna().all() and cross.close_cross.notna().all() and cross.open_gap.abs().max()<.011 and cross.close_gap.abs().max()<.011
 save('daily_crosscheck.csv',cross)
 calp=Path('data/601138_intraday/pytdxdata_1min/daily_trade_calendar.csv');INPUTS[str(calp)]=hashlib.sha256(calp.read_bytes()).hexdigest();cal=pd.read_csv(calp,parse_dates=['date']).date
 assert set(cal)==set(d.date)
 calendar_audit={'provider_calendar_equal':True,'provider_circularity':'Stock-derived calendar alone does not prove no suspensions','exchange_calendar':'pending'}
 try:
  import exchange_calendars as xc
  sessions=xc.get_calendar('XSHG',start='2018-06-08',end='2026-09-11').sessions
  sessions=pd.DatetimeIndex(sessions).tz_localize(None)
  missing=sorted(set(sessions)-set(d.date));extra=sorted(set(d.date)-set(sessions))
  calendar_audit.update(exchange_calendar='XSHG library third-party exchange calendar, not exchange-certified',missing=[str(x.date())for x in missing],extra=[str(x.date())for x in extra],library_version=xc.__version__)
  assert not missing and not extra,'Exchange session disagreement'
 except Exception as e:
  calendar_audit['exchange_error']=str(e);LIMITS.append('Exchange calendar independent full coverage not certified: '+str(e))
 ixraw=pd.read_csv(B2/'source/sse_index.csv',parse_dates=['date']).set_index('date');ix=d.date.map(ixraw.close)
 missing_stock=sorted(set(ixraw.index[(ixraw.index>=d.date.min())&(ixraw.index<=d.date.max())])-set(d.date))
 assert not missing_stock,'Index traded while stock data absent; do not bridge'
 calendar_audit['sse_index_calendar_missing_stock']=len(missing_stock);calendar_audit['sse_index_covered_days']=int(ix.notna().sum());js('calendar_audit.json',calendar_audit)
 CHECKS.append(dict(name='daily OHLC, same-vendor raw crosscheck and available index calendar',status='PASS'))
 # Keep all dividends with exact source status, never erase affected nights.
 corp=pd.read_csv(B8/'corporate_actions.csv',parse_dates=['date','announcement']);corp['record_date']=corp.date.map(d.set_index('exit_date').date.to_dict());corp['pay_date_assumption']=corp.date;corp['share_ratio']=1;corp['primary_verified']=False
 corp['status']='vendor_event_reconciled; pay-date scenario, source snapshot retained'
 assert set(d.loc[d.action_ratio.sub(1).abs().gt(.0001),'date'])==set(corp.date)
 assert (corp.vendor_dividend_gap.abs()<.011).all();assert (corp.announcement<corp.record_date).all();save('corporate_actions.csv',corp)
 with zipfile.ZipFile(P/'source/601138-full-5min-history.zip')as z:m=pd.read_csv(z.open(next(n for n in z.namelist()if n.endswith('601138_5min_all.csv'))))
 m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
 assert not m.duplicated(['date','clock']).any()
 ma=m.groupby('date').agg(first=('open','first'),last=('close','last'),high5=('high','max'),low5=('low','min'),bars=('clock','size'),vol5=('volume','sum'),first_clock=('clock','first'),last_clock=('clock','last'))
 au=d[['date','open','close','high','low','volume']].join(ma,on='date');au['open_gap']=au.open-au['first'];au['close_gap']=au.close-au['last'];au['high_gap']=au.high-au.high5;au['low_gap']=au.low-au.low5;au['volume_ratio']=au.vol5/au.volume
 au['endpoint_good']=au.open_gap.abs().lt(.011)&au.close_gap.abs().lt(.011)&au.bars.eq(48)&au.first_clock.eq('09:35')&au.last_clock.eq('15:00')
 au['path_strict_good']=au.endpoint_good&au.high_gap.abs().lt(.011)&au.low_gap.abs().lt(.011)&au.volume_ratio.sub(1).abs().lt(.001)
 # Endpoint stress does not need intrabar extremes, conservative fill windows do.
 m.attrs['qualified_days']=set(au.index[au.path_strict_good]);save('minute_audit.csv',au)
 js('bar_semantics.json',{'interpretation':'end stamped complete five-minute bars inferred from 48 labels09:35..15:00 and first open/daily open agreement; not provider timestamp delivery certification','endpoint_good_days':int(au.endpoint_good.sum()),'path_strict_good_days':int(au.path_strict_good.sum()),'minute_days':m.date.nunique(),'failures_kept':True,'B14_transactions_used':False})
 f1,f2,tail=features(d,m,ix);masks=rule_masks(f1,f2)
 # Prefix/mutation tests reconstruct chain and include current final close for S2.
 for cut in [900,1600]:
  a=d.copy();a['volume']=a.volume.astype(float);a.loc[cut:,['open','high','low','close','preclose','volume']]*=1.3
  aa,bb,_=features(a,m,ix);pd.testing.assert_frame_equal(aa.iloc[:cut+1],f1.iloc[:cut+1])
  a=d.copy();a.loc[cut:,'close']*=1.37
  mm=m.copy();mm.loc[(mm.date>d.date.iloc[cut])|((mm.date==d.date.iloc[cut])&mm.clock.gt('14:50')),['open','high','low','close','volume']]*=2
  _,bb,_=features(a,mm,ix);np.testing.assert_allclose(bb.iloc[:cut+1].to_numpy(float),f2.iloc[:cut+1].to_numpy(float),equal_nan=True,atol=1e-9)
  aa,bb,_=features(d.iloc[:cut+1],m[m.date<=d.date.iloc[cut]],ix.iloc[:cut+1]);pd.testing.assert_frame_equal(aa,f1.iloc[:cut+1]);pd.testing.assert_frame_equal(bb,f2.iloc[:cut+1])
 CHECKS.append(dict(name='causal rebuild/current-future mutation and prefix signals',status='PASS'))
 for name,clock in [('sell1455','14:55'),('buy0935_today','09:35')]:
  d[name]=d.date.map(m[m.clock.eq(clock)].set_index('date').close).where(au.endpoint_good)
 d['buy0935']=d.buy0935_today.shift(-1)
 full=d.next_open.notna();d=ledger(d)
 # Independent scalar standard-day calculation, both fee dates and dividend are explicit.
 for r in d[full].itertuples():
  sell=1000*r.close*.9995;buy=1000*r.next_open*1.0005
  st=.001 if r.date<pd.Timestamp('2023-08-28') else .0005
  ts=.00002 if r.date<pd.Timestamp('2022-04-29') else .00001;tb=.00002 if r.exit_date<pd.Timestamp('2022-04-29') else .00001
  net=sell-buy-max(5,sell*.0001354)-max(5,buy*.0001354)-sell*(st+ts)-buy*tb-1000*r.dividend
  assert abs(net-r.cash)<1e-7
 ordinary=d[full&d.dividend.eq(0)];rev=ledger(ordinary,reverse=True)
 np.testing.assert_allclose(ordinary.price_gross_cash,-1000*(ordinary.next_open-ordinary.close),atol=1e-8)
 assert ((ordinary.cash+rev.cash)<0).all()
 assert abs(sf(1000,pd.Timestamp('2026-01-01'))-5.01)<1e-8
 assert sf(1000,pd.Timestamp('2023-08-25'),True)>sf(1000,pd.Timestamp('2023-08-28'),True)
 CHECKS.append(dict(name='all independent scalar ledgers, fee floors/date switches, two directions cost identity',status='PASS'))
 save('daily_ledger.csv',d);save('features.csv',pd.concat([d[['date']],f1.add_prefix('S1_'),f2.add_prefix('S2_')],axis=1));signals=save('signals.csv',pd.DataFrame({'date':d.date,**masks}))
 wins={'full':full,'main2020':full&d.date.ge('2020-01-01'),'early2020_2023':full&d.date.between('2020-01-01','2023-12-31'),'recent2024':full&d.date.ge('2024-01-01')};wins.update({str(y):full&d.date.dt.year.eq(y)for y in range(2018,2027)})
 rows=[];coverage=[];stress=[];trims=[];events=[];descs=[];mirror=[];overlap=[];accounts=[]
 win=windows_for(d,m);con=conservative_opportunities(d,win).set_index('ordinal')
 def mirror_if_negative(name,scope,g):
  if len(g)and g.net.mean()<0:
   v=ledger(g,reverse=True);mirror.append(dict(id=name,scope=scope,direction='close_buy_next_open_sell',**metrics(v),dates=';'.join(g.date.dt.strftime('%Y-%m-%d')),stage_version='frozen t-1 descriptive'))
 for name,mask in masks.items():
  hit=mask.fillna(False).astype(bool);valid=mask.notna()
  for wn,wm in wins.items():
   g=d[wm&valid];h=hit.loc[g.index];sel=g[h];no=g[~h]
   assert len(sel)+len(no)+int((wm&~valid).sum())==int(wm.sum())
   for kind,x in [('hit',sel),('nonhit',no),('valid_S0',g)]:rows.append(dict(id=name,window=wn,kind=kind,**metrics(x)))
   ci=boot(g,h)if wn in ['main2020','early2020_2023','recent2024']else{}
   coverage.append(dict(id=name,window=wn,universe=int(wm.sum()),hit=len(sel),nonhit=len(no),unknown=int((wm&~valid).sum()),**ci))
   mirror_if_negative(name,wn,sel)
  g=d[wins['main2020']&hit]
  for slip in [0,.0005,.001,.002]:
   for wn in ['main2020','early2020_2023','recent2024']:
    gg=d[wins[wn]&hit];gg=ledger(gg,slip=slip);stress.append(dict(id=name,window=wn,kind='slip',value=slip*10000,**metrics(gg)))
  for kind,values in [('quantity',[100,500,1000]),('benchmark_dividend_tax',[0,.1,.2]),('unified_fee',[1])]:
   for v in values:
    kw={'q':v}if kind=='quantity'else {'tax':v}if kind=='benchmark_dividend_tax'else {'current':True}
    stress.append(dict(id=name,window='main2020',kind=kind,value=v,**metrics(ledger(g,**kw))))
  for kind,sellcol,buycol in [('sell1455','sell1455','next_open'),('buy0935','close','buy0935'),('joint','sell1455','buy0935')]:
   good=d[sellcol].notna()&d[buycol].notna();base=d[wins['main2020']&hit&good];v=ledger(base,sellcol=sellcol,buycol=buycol)
   universe=d[wins['main2020']&valid&good];b0=ledger(universe,sellcol=sellcol,buycol=buycol)
   stress.append(dict(id=name,window='main2020',kind=kind,value=5,excluded=int((wins['main2020']&hit&~good).sum()),matched_own_base=base.net.mean(),matched_own_cash=base.cash.sum(),paired_S0_n=len(universe),paired_S0=b0.net.mean(),increment=v.net.mean()-b0.net.mean(),**metrics(v)))
  cg=con.loc[con.index.isin(g.index)].copy();stress.append(dict(id=name,window='main2020',kind='conservative_repurchase',value=0,unresolved=int(cg.status.eq('unresolved').sum()),sell_restricted=int(cg.status.eq('retained_sale_restricted').sum()),delayed=int(cg.days_missing.gt(1).sum()),max_missing_days=cg.days_missing.max(),**metrics(cg)))
  for by in ['net','cash']:
   for k in [1,5]:
    for side in ['best','worst','both']:
     if len(g)<(2*k+1 if side=='both'else k+1):trims.append(dict(id=name,sort=by,k=k,delete=side,status='not_applicable'));continue
     ordered=g.sort_values(by);x=ordered.iloc[k:-k]if side=='both'else ordered.iloc[:-k]if side=='best'else ordered.iloc[k:]
     trims.append(dict(id=name,sort=by,k=k,delete=side,status='diagnostic_only',**metrics(x)))
  if len(g):
   labels=g.ordinal.diff().gt(5).cumsum()
   for event,x in g.groupby(labels):
    rest=g.drop(index=x.index);events.append(dict(id=name,event=int(event),start=x.date.min(),end=x.date.max(),share_total_cash=x.cash.sum()/g.cash.sum()if g.cash.sum()!=0 else np.nan,excluded_n=len(x),event_cash=x.cash.sum(),event_pct_sum=x.net.sum(),remaining_mean=rest.net.mean(),remaining_cash=rest.cash.sum(),remaining_n=len(rest),dates=';'.join(x.date.dt.strftime('%Y-%m-%d'))))
   for s in ['U','R','D','C','UNKNOWN']:
    x=g[g.stage.eq(s)];descs.append(dict(id=name,group='stage_frozen_tminus1',value=s,**metrics(x)));mirror_if_negative(name,'stage_'+s,x)
   for group,ms in [('corporate_action',g.dividend.gt(0)),('non_action',g.dividend.eq(0)),('long_break',g.gapdays.ge(3)),('ordinary_break',g.gapdays.lt(3))]:
    x=g[ms];descs.append(dict(id=name,group='description',value=group,**metrics(x)));mirror_if_negative(name,group,x)
  for other,om in masks.items():overlap.append(dict(id=name,other=other,intersection=int((wins['main2020']&hit&om.fillna(False)).sum())))
  # All planned rules get account outputs including unavailable rule -> no trades.
  for buf in [0,.1,.3]:
   for cons in [False,True]:
    z,o,ep,a=account(d,mask,win,buf,cons);tag=f'{name}_{int(buf*100)}_{"restricted"if cons else "nominal"}'
    save('account_'+tag+'.csv',z);save('orders_'+tag+'.csv',o);save('episodes_'+tag+'.csv',ep);accounts.append(dict(id=name,**a))
   # Receivable-locked sensitivity addresses uncertain payment timing, no speculative cash used.
   z,o,ep,a=account(d,mask,win,buf,True,True);tag=f'{name}_{int(buf*100)}_locked';save('account_'+tag+'.csv',z);save('orders_'+tag+'.csv',o);accounts.append(dict(id=name,**a))
 print('RULES_COMPLETE',flush=True)
 results=save('results.csv',rows);cv=save('coverage_bootstrap.csv',coverage);st=save('stress.csv',stress);save('symmetric_trim.csv',trims);ev=save('events_leave_one_out.csv',events);save('descriptive_groups.csv',descs);save('mirror_registry.csv',mirror);save('overlap.csv',overlap);ac=save('accounts.csv',accounts)
 CHECKS.append(dict(name='tri-state partitions and complete rule output',status='PASS'));CHECKS.append(dict(name='all accounts cash/inventory/FIFO/T+1/self-financing assertions',status='PASS'))
 # Actual hand-check extraction retains arithmetic inputs, not just profitability labels.
 sample=[]
 ordinary=d[full&d.dividend.eq(0)&d.date.ge('2020-01-01')]
 for kind,x in [('ordinary_profit',ordinary[ordinary.cash.gt(0)].head(1)),('ordinary_loss',ordinary[ordinary.cash.lt(0)].head(1)),('corporate',d[full&d.dividend.gt(0)]),('limit_buy',d[full&d.next_open.ge(d.limit_up.shift(-1)-.005)])]:
  for _,r in x.iterrows():sample.append(dict(case=kind,**r[['date','exit_date','close','next_open','dividend','sale_value','buy_value','fee','cash','net','extra_cash']].to_dict()))
 save('case_checks.csv',sample)
 # Explicit synthetic invariants covering branches even if actual constraints absent.
 toy=d.iloc[383:389].copy().reset_index(drop=True)
 toy['date']=pd.bdate_range('2020-01-02',periods=6);toy['open']=10.;toy['close']=10.;toy['preclose']=10.;toy['dividend_today']=0.;toy['limit_up']=11.;toy['limit_down']=9.;toy['volume']=100000.
 tw={i:[('09:25',float(toy.loc[i,'open']),'toy')]for i in toy.index};tm=pd.Series(True,index=toy.index)
 z,o,ep,a=account(toy,tm,tw,.3,False);assert a['skip_t1']>=2 and a['sales']==3 and a['terminal_missing']==0
 toy.loc[1:,'open']=12.;toy.loc[1:,'close']=12.;tw={i:[('09:25',float(toy.loc[i,'open']),'toy')]for i in toy.index}
 z,o,ep,a=account(toy,tm,tw,0,False);assert a['terminal_missing']>0 and a['skip_missing']>0 and a['terminal_cash_gap']>0
 tw={i:[]for i in toy.index};z,o,ep,a=account(toy,tm,tw,.3,True);assert a['terminal_missing']==1000 and a['completed']==0
 CHECKS.append(dict(name='synthetic same-day resale forbidden, funding partials persist, blocked repurchase terminal retained',status='PASS'))
 fetch_sources()
 LIMITS.extend(['All auction queue quantities unknown; proxies are not fills. Partial fills due to liquidity not identifiable; modeled partials are budget-limited only.','Cash action amounts/dates reconcile retained vendor references; all-nine primary announcement/pay-date certification incomplete. Main account ex-date-close payment is explicit scenario; locked receivable sensitivity included.','Single-stock calendar and index plus third-party calendar are crosschecks, not primary exchange suspension certification.','S2 timestamps inferred as bar end; receipt latency unknown. Endpoint/path quality filters are audit common-date restrictions, not deployable ex-ante filters.','Monthly blocks preserve within-month dependence; events crossing month boundary may split. Dense S0 may form one connected event; leave-event evidence then not identifiable.','All data historical explored; no holdout or forward evidence. Slippage-cost model may exceed statutory limits near boundaries; conservative limit flags refer to reference market price.','Opportunity same-day availability assumed per independent sale; continuous accounts enforce settled inventory, no daily reuse. Opportunity sum not account return.'])
 audit=dict(data_start=str(d.date.min().date()),data_end=str(d.date.max().date()),rows=len(d),completed_opportunities=int(full.sum()),main_opportunities=int(wins['main2020'].sum()),last_pending_date=str(d.date.iloc[-1].date()),input_hashes=INPUTS,rule_slots=len(masks)-1,unavailable=['S2_F7'],minute_days=m.date.nunique(),qualified_endpoint_days=int(au.endpoint_good.sum()),qualified_path_days=int(au.path_strict_good.sum()),dividend_events=len(corp),source_capture_failures=[s['id']for s in SOURCELOG if s['status']=='FAILED'],validation_count=len(CHECKS),limitations=LIMITS)
 js('audit.json',audit);js('validation.json',CHECKS);js('fee_config.json',dict(commission=.0001354,min_commission=5,commission_status='assumed inclusive broker commission, no account proof',transfer_before_20220429=.00002,transfer_after=.00001,stamp_before_20230828=.001,stamp_after=.0005,slip_each_bp=[0,5,10,20],base_bp=5,dividend_tax='FIFO calendar duration continuous account, opportunity benchmark0/10/20pct scenarios',transfer_source='Official historical primary announcement not fetched; secondary report preserved; do not call fully primary-certified'))
 # Concise remote report is safe to retrieve locally; detailed price data stay remote.
 texts=['# B15 remote research summary','All numbers are historical model outputs, not account records. Percentage = net/(1000*raw reference close).',json.dumps(audit,ensure_ascii=False,indent=2),'## Main hit results',results[(results.window=='main2020')&(results.kind=='hit')].to_markdown(index=False,floatfmt='.6f'),'## Main coverage / intervals',cv[cv.window=='main2020'].to_markdown(index=False,floatfmt='.6f'),'## S0 windows',results[(results.id=='S0')&(results.kind=='hit')].to_markdown(index=False,floatfmt='.6f'),'## Conservative accounts, payment-date scenario',ac[(ac['mode']=='conservative')&(ac.settlement=='ex_date_close_scenario')].to_markdown(index=False,floatfmt='.4f'),'## S0 stress',st[st.id=='S0'].to_markdown(index=False,floatfmt='.6f'),'## Cases',pd.DataFrame(sample).to_markdown(index=False,floatfmt='.6f'),'## Validation',pd.DataFrame(CHECKS).to_markdown(index=False)]
 (R/'REPORT.md').write_text('\n\n'.join(texts),encoding='utf8')
 js('runtime.json',{'python':sys.version,'platform':platform.platform(),'pip_freeze':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True),'command':'python scripts/research/foxconn_overnight_sell_b15.py','run_id':os.environ['GITHUB_RUN_ID'],'code_sha':os.environ['GITHUB_SHA']})
 js('manifest.json',dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],inputs=INPUTS,files={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in R.rglob('*')if p.is_file()and p.name!='manifest.json'}))
 print(json.dumps(audit,ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:run()
 except Exception:
  R.mkdir(parents=True,exist_ok=True);(R/'failure.txt').write_text(traceback.format_exc());raise
