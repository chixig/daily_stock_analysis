"""Independent replay of all B27 broker ledgers, no simulate() use."""
import os,json,hashlib,sys
from pathlib import Path
from collections import defaultdict
from functools import lru_cache
import numpy as np
import pandas as pd
import foxconn_b27 as c
R=c.R
def read(folder,name):
    p=R/f'{folder}/{name}.csv.gz'
    try:return pd.read_csv(p)
    except pd.errors.EmptyDataError:return pd.DataFrame()
def fee(v,day,sell):
    return max(5,v*.0001354)+v*((.00002 if day<pd.Timestamp('2022-04-29') else .00001)+((.001 if day<pd.Timestamp('2023-08-28') else .0005) if sell else 0))
@lru_cache(maxsize=None)
def taxrate(acquired,sold):
    end=sold-pd.Timedelta(days=1)
    return .2 if end<acquired+pd.DateOffset(months=1) else .1 if end<acquired+pd.DateOffset(years=1) else 0.

def validate_decisions():
    from fractions import Fraction
    import zipfile
    with zipfile.ZipFile(c.c.b.old.P/'source/601138-full-5min-history.zip') as arc:
        raw=pd.read_csv(arc.open(next(n for n in arc.namelist() if n.endswith('601138_5min_all.csv'))),dtype=str,keep_default_na=False)
    raw['date']=pd.to_datetime(raw.date);raw['clock']=pd.to_datetime(raw.time.str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M')
    groups={str(dt.date()):g.set_index('clock') for dt,g in raw.groupby('date')}
    dec=pd.read_csv(R/'exit_decisions.csv',dtype=str,keep_default_na=False);out=[]
    times=[x.strftime('%H:%M') for a,b in [('09:40','11:30'),('13:05','14:50')] for x in pd.date_range('2000-01-01 '+a,'2000-01-01 '+b,freq='5min')]
    def q(v):
        try:
            x=Fraction(str(v));return x if x>0 else None
        except Exception:return None
    for r in dec.itertuples():
        obs='';armed='';peak=None;threshold=None;observed=unknown=0;reason='original_close' if r.mode=='Pclose' else 'no_trigger_close'
        g=groups.get(r.date,pd.DataFrame());entry=q(g.loc['09:40','open']) if '09:40' in g.index else None
        if r.mode!='Pclose' and entry is None:reason='entry_unknown'
        if r.mode!='Pclose' and entry is not None:
            if r.mode in ['PT1','PT2']:gain=Fraction(1 if r.mode=='PT1' else 2,100);pull=None
            else:gain=Fraction(int(r.mode[2]),100);pull=Fraction(5 if r.mode.endswith('05') else 10,1000)
            line=entry*(1+gain)
            for clock in times:
                px=q(g.loc[clock,'close']) if clock in g.index else None;vol=q(g.loc[clock,'volume']) if clock in g.index else None
                if px is None or vol is None:unknown+=1;continue
                observed+=1
                if pull is None:threshold=line;fire=px>=line
                else:
                    if peak is None and px>=line:armed=clock;peak=px
                    if peak is not None:peak=max(px,peak)
                    threshold=peak*(1-pull) if peak is not None else None
                    fire=threshold is not None and px<=threshold
                if fire:obs=clock;reason='fixed_profit' if pull is None else 'armed_pullback';break
        assert (r.observation,r.armed,r.reason)==(obs,armed,reason),(r.mode,r.date,r.observation,obs)
        assert int(r.observed)==observed and int(r.unknown)==unknown
        assert (q(r.peak)==peak if peak else not r.peak) and (q(r.threshold)==threshold if threshold else not r.threshold)
        out.append(dict(mode=r.mode,date=r.date,observation=obs,armed=armed,reason=reason,status='PASS'))
    c.save('independent_decision_checks.csv',out)
    c.js('independent_feature_validation.json',dict(status='PASS',decisions=len(out),implementation='Fraction from original raw CSV; independent gain/pullback spec, peak/arming/first trigger and unknown counts'))
def verify_P_exit(rule,d,bars,trades,events):
    if rule.anchor or rule.P=='Pclose':return
    dec=pd.read_csv(R/'independent_decision_checks.csv',keep_default_na=False)
    dec=dec[dec['mode'].eq(rule.P)].set_index('date')
    dates=list(d.date);dm=d.set_index('date')
    clocks=[v.strftime('%H:%M') for a,b in [('09:35','11:30'),('13:05','14:55')] for v in pd.date_range('2000-01-01 '+a,'2000-01-01 '+b,freq='5min')]
    for t in trades[trades.module.eq('P')].itertuples():
        dt=pd.Timestamp(t.entry);obs=dec.loc[t.entry,'observation'];row=dm.loc[dt]
        candidates=[(dt,k,'bar_close_'+k.replace(':','')) for k in clocks if obs and k>obs]+[(dt,'15:00','daily_close')]
        candidates += [(day,'09:25','daily_open') for day in dates if day>dt]
        # Actual history has no inventory exit block at locked K; preserve this explicit scope.
        failures=events[(events.tid==t.tid)&events.kind.eq('exit')&events.reason.ne('filled')]
        assert not failures.reason.eq('old_shares_insufficient').any()
        expected=None
        for day,clock,basis in candidates:
            row=dm.loc[day]
            if basis=='daily_close':price=row.close;volume=row.volume
            elif basis=='daily_open':price=row.open;volume=1
            else:bar=bars.get((day,clock));price=bar.close if bar is not None else np.nan;volume=bar.volume if bar is not None else 0
            if np.isfinite(price) and price>0 and price>row.limit_down+.005 and volume>0:expected=(str(day.date()),clock,basis,price);break
        ex=events[(events.tid==t.tid)&events.kind.eq('exit')&events.reason.eq('filled')]
        if expected is None:assert not len(ex)
        else:
            assert len(ex)==1
            e=ex.iloc[0]
            assert (str(e.date)[:10],e.clock,e.basis)==expected[:3],(rule.id,t.entry,expected,(e.date,e.clock,e.basis))
            assert abs(e.reference-expected[3])<1e-9

def run():
    validate_decisions()
    s=pd.read_csv(R/'account_summary.csv')
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in {**frozen['files'],**frozen['code']}.items():assert c.sha(p)==h,p
    d,_,_,_,schedule=c.z.load()
    grid=pd.read_csv(R/'common_grid.csv.gz',parse_dates=['date']);grid_days={dt:list(g.itertuples()) for dt,g in grid.groupby('date')}
    raw=c.z.q.load_minutes();bm={(r.date,r.clock):r for r in raw.itertuples()};dm=d.set_index('date')
    for g in grid.itertuples():
        if g.basis=='daily_open':p=dm.loc[g.date,'open']
        elif g.basis=='daily_close':p=dm.loc[g.date,'close']
        elif g.basis.startswith('bar_close_'):p=bm[(g.date,g.clock)].close
        else:p=bm[(g.date,c.c.b.minutes_after(g.clock,5))].open
        assert abs(p-g.price)<1e-10
    start=int(d.index[d.date.ge(c.START)][0]);verify=[];prefix=[]
    for rr in s.itertuples():
        name=f'{rr.id}_{rr.stock}_{rr.bp}'
        a=read('accounts',name);o=read('orders',name);ev=read('events',name);tr=read('trades',name);pa=read('pairs',name);ls=read('lots',name);dis=read('disposals',name)
        verify_P_exit(rr,d,bm,tr,ev)
        intr=read('stress',name);assert list(intr.grid_id)==list(grid.grid_id)
        intrmap={r.grid_id:r for r in intr.itertuples()};tidmodule=dict(zip(tr.tid,tr.module))
        a.date=pd.to_datetime(a.date)
        for frame in [o,ev,pa,ls,dis]:
            if len(frame):frame.date=pd.to_datetime(frame.date)
        lots=[dict(q=rr.stock,date=d.date.iloc[start]-pd.DateOffset(years=2),div=0.,id=0)];nextid=1
        cash=holdcash=flow=paid=hpaid=0.;recv=[];hr=[];initial=rr.stock*d.close.iloc[start]
        daily={day:g for day,g in o.groupby('date')} if len(o) else {}
        daily_ac={pd.Timestamp(row.date):row._asdict() for row in a.itertuples(index=False)}
        daily_lots=defaultdict(dict)
        assert not ls.duplicated(['date','lot_id']).any()
        ls['acquired']=pd.to_datetime(ls.acquired)
        for lr in ls.itertuples(index=False):daily_lots[lr.date][lr.lot_id]=lr._asdict()
        filled_by_order={oid:g for oid,g in ev[ev.reason.eq('filled')].groupby('order_id')} if len(ev) else {}
        pairs_by_time={key:g for key,g in pa.groupby(['date','clock','basis'])} if len(pa) else {}
        empty=pd.DataFrame()
        disp={(row.order_id,row.lot_id):row for row in dis.itertuples()} if len(dis) else {}
        daily_e={day:g for day,g in ev.groupby('date')} if len(ev) else {}
        group_fills={k:list(g.itertuples()) for k,g in ev[ev.reason.eq('filled')].groupby(['date','clock','basis'])}
        logical={};lcash=defaultdict(float);ldiv=defaultdict(float);seen=set()
        for row in d.iloc[start:].itertuples():
            i=row.Index;day=row.date;ac=daily_ac[day]
            if row.dividend_today:
                recv.append((schedule.get(day,len(d)+10),sum(l['q'] for l in lots)*row.dividend_today))
                hr.append((schedule.get(day,len(d)+10),rr.stock*row.dividend_today))
                for l in lots:l['div']+=row.dividend_today
                for tid,v in logical.items():ldiv[tid]+=v*1000*row.dividend_today
            oo=daily.get(day,empty);haspaid=False
            daypay=dayhpay=0.
            gvalues={v:sum(lcash[tid]+ldiv[tid] for tid in seen if tidmodule[tid]==v) for v in 'PNR'}
            gpositions={v:sum(pos for tid,pos in logical.items() if tidmodule[tid]==v) for v in 'PNR'}
            ordergroups={(clock,basis):list(gg.itertuples()) for (clock,basis),gg in oo.groupby(['clock','basis'])} if len(oo) else {}
            daygrid={(g.clock,g.basis):g for g in grid_days[day]}
            allkeys=sorted(set(daygrid)|set(ordergroups),key=c.sortkey)
            for clock,basis in allkeys:
                if clock=='15:00' and not haspaid:
                    daypay=sum(v for ix,v in recv if ix<=i);dayhpay=sum(v for ix,v in hr if ix<=i)
                    cash+=daypay;holdcash+=dayhpay;recv=[(ix,v) for ix,v in recv if ix>i]
                    hr=[(ix,v) for ix,v in hr if ix>i];haspaid=True
                for order in ordergroups.get((clock,basis),[]):
                    if order.clock=='15:00' and not haspaid:
                        due=[v for ix,v in recv if ix<=i];hdue=[v for ix,v in hr if ix<=i]
                        daypay=sum(due);dayhpay=sum(hdue);cash+=daypay;holdcash+=dayhpay
                        recv=[v for v in recv if v[0]>i];hr=[v for v in hr if v[0]>i];haspaid=True
                    side=order.side;quant=int(order.quantity);assert quant%1000==0 and quant>0
                    val=quant*order.reference*(1+(rr.bp/10000 if side=='BUY' else -rr.bp/10000))
                    f=fee(val,day,side=='SELL');assert abs(val-order.value)<1e-6 and abs(f-order.fee)<1e-6
                    tx=0.;sale_parts=[];res=sum(v['q']*v['div']*taxrate(v['date'],day) for v in lots)
                    if side=='BUY':
                        dep=max(0,val+f+res-cash)
                        assert abs(dep-order.deposit)<1e-6
                        flow+=dep;cash+=dep-val-f;holdcash+=dep
                        lots.append(dict(q=quant,date=day,div=0.,id=nextid));nextid+=1
                    else:
                        assert order.deposit==0
                        need=quant
                        for l in list(lots):
                            if l['date']>=day:continue
                            n=min(need,l['q']);dtax=n*l['div']*taxrate(l['date'],day);tx+=dtax
                            sale_parts.append(dict(lot_id=l['id'],q=n,unit_tax=dtax/n))
                            dd=disp[(order.order_id,l['id'])]
                            assert int(dd.quantity)==n and abs(dd.tax-dtax)<1e-6
                            l['q']-=n;need-=n
                            if l['q']==0:lots.remove(l)
                            if need==0:break
                        assert need==0
                        cash+=val-f-tx
                    assert abs(tx-order.tax)<1e-6
                    assert abs(cash-order.cash)<1e-5 and sum(l['q'] for l in lots)==order.shares
                    filled=filled_by_order[order.order_id]
                    assert abs(filled.fee.sum()-f)<1e-6 and abs(filled.tax.sum()-tx)<1e-6
                    assert int(filled.side.sum()*1000)==quant*(1 if side=='BUY' else -1)
                    assert filled.basis.nunique()==1 and filled.clock.nunique()==1
                    paired=pairs_by_time.get((day,order.clock,order.basis),empty)
                    paired_ids=set(paired.buy_tid)|set(paired.sell_tid) if len(paired) else set()
                    ext=filled[(filled.side==(1 if side=='BUY' else -1))&~filled.tid.isin(paired_ids)]
                    assert len(ext)*1000==quant
                    expected_tax={};expected_lots={}
                    if side=='SELL':
                        for ee in ext.itertuples():
                            need=1000;ttax=0.;parts=[]
                            while need:
                                pp=sale_parts[0];n=min(need,pp['q']);amt=n*pp['unit_tax'];ttax+=amt
                                parts.append(dict(lot_id=pp['lot_id'],quantity=n,tax=amt))
                                pp['q']-=n;need-=n
                                if pp['q']==0:sale_parts.pop(0)
                            expected_tax[ee.tid]=ttax;expected_lots[ee.tid]=parts
                        assert not sale_parts
                    for ee in filled.itertuples():
                        share=1/len(ext) if ee.tid in set(ext.tid) else 0.
                        assert abs(ee.external_share-share)<1e-12
                        assert abs(ee.fee-f*share)<1e-6 and abs(ee.tax-expected_tax.get(ee.tid,0))<1e-6
                        parts=json.loads(ee.fifo_lots)
                        assert len(parts)==len(expected_lots.get(ee.tid,[]))
                        for got,want in zip(parts,expected_lots.get(ee.tid,[])):
                            assert got['lot_id']==want['lot_id'] and got['quantity']==want['quantity'] and abs(got['tax']-want['tax'])<1e-6
    
                for e in group_fills.get((day,clock,basis),[]):
                    gvalues[e.module]+=-e.side*1000*e.reference-e.fee-e.tax-e.slip
                    gpositions[e.module]+=int(e.side)
                if (clock,basis) in daygrid:
                    qg=daygrid[(clock,basis)];p=qg.price;got=intrmap[qg.grid_id]
                    q=sum(l['q'] for l in lots);res=sum(l['q']*l['div']*taxrate(l['date'],day) for l in lots)
                    eq=cash+sum(v for _,v in recv)+q*p-res;he=holdcash+sum(v for _,v in hr)+rr.stock*p
                    vals=dict(cash=cash,hold_cash=holdcash,shares=q,external=flow,receivable=sum(v for _,v in recv),hold_receivable=sum(v for _,v in hr),tax_reserve=res,equity=eq,hold_equity=he,relative=eq-he,absolute=eq-initial-flow,hold_absolute=he-initial-flow,adjust=-res)
                    vals.update({v:gvalues[v]+1000*p*gpositions[v] for v in 'PNR'})
                    for k,value in vals.items():assert abs(getattr(got,k)-value)<1e-5,(name,qg.grid_id,k)
            if not haspaid:
                daypay=sum(v for ix,v in recv if ix<=i);dayhpay=sum(v for ix,v in hr if ix<=i)
                cash+=daypay;holdcash+=dayhpay;recv=[v for v in recv if v[0]>i];hr=[v for v in hr if v[0]>i]
            gg=daily_e.get(day,empty)
            if len(gg):
                fills=gg[gg.reason=='filled']
                for e in fills.itertuples():
                    assert e.quantity==1000
                    if e.kind=='entry':
                        assert e.tid not in seen;seen.add(e.tid);logical[e.tid]=int(e.side)
                    else:assert e.tid in logical and logical.pop(e.tid)==-e.side
                    lcash[e.tid]+=-e.side*1000*e.reference-e.fee-e.tax-e.slip
                for (clock,basis),g in fills.groupby(['clock','basis']):
                    order=oo[(oo.clock==clock)&(oo.basis==basis)] if len(oo) else pd.DataFrame()
                    net=g.side.sum()*1000
                    assert (len(order)==1 and abs(order.quantity.iloc[0])==abs(net)) if net else len(order)==0
                    paired=pairs_by_time.get((day,clock,basis),empty)
                    assert len(paired)==min(int(g.side.eq(1).sum()),int(g.side.eq(-1).sum()))
                    if len(paired):
                        assert paired.quantity.eq(1000).all() and not paired.buy_tid.duplicated().any() and not paired.sell_tid.duplicated().any()
                        internal=g[g.tid.isin(set(paired.buy_tid)|set(paired.sell_tid))]
                        assert internal[['fee','tax','slip','external_share']].abs().to_numpy().max()<1e-8
                    # Policies are measured on unfinished logical batches, group exits before entries.
                adds=sum(v==1 for v in logical.values());reds=sum(v==-1 for v in logical.values())
                if rr.policy!='F':assert max(adds,reds)<=int(rr.policy[-1])
            qty=sum(l['q'] for l in lots);res=sum(l['q']*l['div']*taxrate(l['date'],day) for l in lots)
            eq=cash+sum(v for _,v in recv)+qty*row.close-res
            he=holdcash+sum(v for _,v in hr)+rr.stock*row.close
            for key,v in dict(cash=cash,hold_cash=holdcash,shares=qty,receivable=sum(v for _,v in recv),hold_receivable=sum(v for _,v in hr),tax_reserve=res,equity=eq,hold_equity=he,external=flow,relative=eq-he,absolute=eq-initial-flow,hold_absolute=he-initial-flow,payment=daypay,hold_payment=dayhpay).items():
                assert abs(ac[key]-v)<1e-5,(name,day,key,ac[key],v)
            assert qty==rr.stock+1000*sum(logical.values())
            marked=sum(lcash.values())+sum(ldiv.values())+1000*row.close*sum(logical.values())-res
            assert abs(marked-(eq-he))<1e-5
            dl=daily_lots.get(day,{})
            assert sum(v['q'] for v in dl.values())==qty and set(dl)==set(l['id'] for l in lots)
            for l in lots:
                v=dl[l['id']]
                assert pd.Timestamp(v['acquired'])==l['date'] and v['q']==l['q'] and abs(v['div']-l['div'])<1e-10
        for t in tr.itertuples():
            assert abs(t.cash-lcash[t.tid])<1e-5 and abs(t.dividend-ldiv[t.tid])<1e-5
        def dd(x):
            peak=0.;worst=0.
            for v in x:peak=max(peak,v);worst=max(worst,peak-v)
            return worst
        assert abs(dd(a.relative)-rr.relative_mdd)<1e-5 and abs(dd(a.absolute)-rr.absolute_mdd)<1e-5
        assert abs(a.relative.iloc[-1]-rr.increment)<1e-5
        assert abs(dd(intr.relative)-rr.intraday_relative_mdd)<1e-5 and abs(dd(intr.absolute)-rr.intraday_absolute_mdd)<1e-5
        assert abs(dd(intr.hold_absolute)-rr.intraday_hold_mdd)<1e-5
        verify.append(dict(id=rr.id,stock=rr.stock,bp=rr.bp,days=len(a),external_orders=len(o),logical_entries=len(tr),status='PASS'))
        print('VERIFIED',name,flush=True)
    c.save('independent_accounts_verified.csv',verify)
    d,m,bars,sched,plans=c.load();c.make_grid(d,bars,plans);sim=c.engine()
    for key in [c.BASE,'PF105_N2_R1_L1','PT2_N2_R1_F']:
        rule=next(v for v in c.registry() if v['id']==key)
        for cut in [1400,len(d)-30]:
            pp={k:[t for t in vv if t['entry_i']<=cut] for k,vv in plans.items()}
            _,a,_,_=sim(d.iloc[:cut+1],bars,sched,pp,rule,3000,5)
            full=read('accounts',key+'_3000_5');want=full[pd.to_datetime(full.date)<=d.date.iloc[cut]]
            for col in ['cash','shares','relative','absolute','external','P','N','R']:np.testing.assert_allclose(a[col],want[col],atol=1e-5)
            prefix.append(dict(id=key,cut=cut,status='PASS'))
    c.save('account_prefix_validation.csv',prefix)
    assert len(verify)==len(s)==51*(2 if json.loads((R/'resource_lock.json').read_text())['K']>3000 else 1)
    for p,h in frozen['files'].items():assert c.sha(p)==h,p
    c.js('independent_validation.json',dict(status='PASS',accounts=len(verify),intraday_points_per_account=len(grid),total_intraday_points=len(grid)*len(verify),prefixes=len(prefix),scope='independent broker/FIFO/receivable/payment/hold/flow and all daily/common-grid equities, module attribution and four drawdowns',limitations='inherited execution proxies; not independently sourced market data'))
    c.js('result_sha256.json',dict(parent=c.PARENT,code_sha=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],files={str(p):c.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['result_sha256.json','calculation.log','verification.log']}))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:run()
    except Exception:
        import traceback
        c.js('independent_failure_'+os.environ.get('GITHUB_RUN_ID','unknown')+'.json',dict(traceback=traceback.format_exc()));raise
