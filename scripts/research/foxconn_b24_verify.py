"""Independent replay of all B24 broker ledgers, no simulate() use."""
import os,json,hashlib,sys
from pathlib import Path
from collections import defaultdict
from functools import lru_cache
import numpy as np
import pandas as pd
import foxconn_b24 as c
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
def run():
    s=pd.read_csv(R/'account_summary.csv')
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in {**frozen['files'],**frozen['code']}.items():assert c.sha(p)==h,p
    d,_,_,_,schedule=c.z.load()
    start=int(d.index[d.date.ge(c.START)][0]);verify=[];prefix=[]
    for rr in s.itertuples():
        name=f'{rr.id}_{rr.stock}_{rr.bp}'
        a=read('accounts',name);o=read('orders',name);ev=read('events',name);tr=read('trades',name);pa=read('pairs',name);ls=read('lots',name);dis=read('disposals',name)
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
            for order in oo.itertuples():
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
        verify.append(dict(id=rr.id,stock=rr.stock,bp=rr.bp,days=len(a),external_orders=len(o),logical_entries=len(tr),status='PASS'))
        print('VERIFIED',name,flush=True)
    c.save('independent_accounts_verified.csv',verify)
    # New-account path prefix replay: truncation retains previously filled events, never uses future balance.
    dd,mm,bars,sched,plans=c.load()
    for cut in [1000,1500,len(dd)-30]:
        rule=next(v for v in c.registry() if v['id']==c.BASE)
        pp={key:[dict(t) for t in val if t['entry_i']<=cut] for key,val in plans.items()}
        _,a,t,ss=c.simulate(dd.iloc[:cut+1],bars,sched,pp,rule,3000,5)
        full=read('accounts',f'{c.BASE}_3000_5')
        want=full[pd.to_datetime(full.date)<=dd.date.iloc[cut]].reset_index(drop=True)
        for col in ['cash','shares','relative','external','tax_reserve','P','N','R']:np.testing.assert_allclose(a[col],want[col],atol=1e-5)
        prefix.append(dict(cut=cut,status='PASS',scope='full shared account prefix, all three modules'))
    c.save('account_prefix_validation.csv',prefix)
    # Exact new common-window R-only bridge to inherited B23 accounting.
    rd,mask,path,sp,sch=c.z.load();st=c.z.states(rd,mm);fam,_=c.z.z.origins(mask);align=[]
    c.z.x.ns['ACCOUNT_START']=c.START
    for mod,key in c.RM.items():
        rule=next(v for v in c.z.registry() if v['id']==key)
        selected,_,_=c.z.choose(rule,st,fam);p=path['A1'].copy()
        for act,pp in path.items():
            ix=p.index[selected.reindex(p.index)==act];p.loc[ix,:]=pp.loc[ix,:]
        tt,_,_=c.z.x.plan(rd,fam.ne(''),p,start=c.START,capacity=3)
        for bp in [5,11,20]:
            a,o,t,f,met=c.z.x.account(rd,tt,3000,bp/10000,sch)
            rr=s[(s.id==mod+'_F')&(s.stock==3000)&(s.bp==bp)].iloc[0]
            assert abs(rr.increment-met['increment'])<1e-5,(mod,bp,rr.increment,met['increment'])
            align.append(dict(module=mod,bp=bp,new_window_parent_increment=met['increment'],shared_account_increment=rr.increment,status='PASS'))
    c.save('R_common_window_parent_alignment.csv',align)
    assert len(verify)==len(s)==396*(2 if json.loads((R/'resource_lock.json').read_text())['K']>3000 else 1)
    c.js('independent_validation.json',dict(status='PASS',accounts=len(verify),prefixes=prefix,R_parent_alignments=len(align),independent='cash/shares/FIFO/fees/tax/receivable/payment/hold/flow-adjusted equity and drawdowns replay from persisted net orders',limitations='market price proxy/exchange execution not certified; causal module source tests plus 3 account prefixes, not exhaustive all possible price paths'))
    c.js('result_sha256.json',dict(parent=c.PARENT,commit=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],files={str(p):c.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['result_sha256.json','verification.log','calculation.log','failure.json']}))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:run()
    except Exception:
        import traceback
        c.js('independent_failure.json',dict(run=os.environ.get('GITHUB_RUN_ID'),traceback=traceback.format_exc()))
        raise
