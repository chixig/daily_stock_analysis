"""B24 shared logical/broker account. Runs exclusively in GitHub Actions."""
import os,sys,json,hashlib,itertools,traceback,subprocess,copy
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
import foxconn_b23 as z
import foxconn_t0_audit as pt
import foxconn_overnight_b11 as n11
import foxconn_overnight_b08 as n8
b=z.b
R=Path('research/foxconn_t0_20261002_b24')
PARENT='ac7759ea0d94948b3b0af837d3459d10ee2e34da'
START='2022-01-01'
RM={'R1':'R1122','R05':'R1111','Rsmall':'R0112','Rprofit':'R2112'}
BASE='Pall_N2_R1_F'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,data):
    p=R/name;p.parent.mkdir(parents=True,exist_ok=True)
    f=data if isinstance(data,pd.DataFrame) else pd.DataFrame(data)
    f.to_csv(p,index=False);return f
def js(name,data):
    p=R/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str))
def registry():
    out=[]
    for p,n,r in itertools.product(['-','Pall','PUR'],['-','N0','N2'],['-']+list(RM)):
        if p==n==r=='-':continue
        combo='_'.join(v for v in [p,n,r] if v!='-')
        for policy in ['F','L1','L2']:out.append(dict(id=combo+'_'+policy,combo=combo,P=p,N=n,R=r,policy=policy,modules=sum(v!='-' for v in [p,n,r])))
    assert len(out)==132
    return out
def freeze():
    if (R/'failure.json').exists():
        (R/'failures').mkdir(exist_ok=True)
        (R/'failure.json').rename(R/'failures'/('before_'+os.environ['GITHUB_RUN_ID']+'.json'))
    files=json.loads((z.R/'frozen_input_hashes.json').read_text())['files']
    for p,h in files.items():assert sha(p)==h,p
    roots=[z.R,n11.R,Path('research/foxconn_overnight_20260917_b12'),Path('research/foxconn_t0_20260913_b03'),Path('research/foxconn_t0_20260915_b07'),n8.R,Path('research/foxconn_overnight_20260916_b10')]
    for root in roots:
        for p in root.rglob('*'):
            if p.is_file():files[str(p)]=sha(p)
    for p in Path('scripts/research').glob('foxconn*.py'):
        if 'b24' not in p.name:files[str(p)]=sha(p)
    subprocess.run(['git','diff','--exit-code',PARENT,'--']+[str(p) for p in roots],check=True)
    js('registry.json',registry());save('registry.csv',registry())
    sources=dict(P=dict(code='scripts/research/foxconn_t0_audit.py;foxconn_t0_b03.py',commit='9c13b3e507e00b05222f8e332ebc38cae301f17b',entry='09:40 labelled bar open =09:35 start',signal='frozen exact prepare/stage plus B03 masks'),N=dict(code='scripts/research/foxconn_overnight_b11.py;foxconn_overnight_b12.py',commits=['087b33677618f6048ee5490bb2e155d253db382e','18b5840d86d075dc7a4499c3dcff94926a21eb09'],trigger='B11 main-cost stop line, completed low trigger or opening gap',fill='B12 next bar close'),R=dict(code='scripts/research/foxconn_b23.py',commit=PARENT,aliases=RM),account=dict(parent_runtime=str(z.R/'inherited_account_runtime.py.txt'),new='scripts/research/foxconn_b24.py',fee='B15 sf date schedule',tax='B15 taxrate FIFO',dividends='B16 verified_events plus B23 daily ledger'))
    js('action_sources.json',sources)
    js('frozen_input_hashes.json',dict(parent=PARENT,files=files,code={str(p):sha(p) for p in Path('scripts/research').glob('foxconn_b24*.py')},protocol_sha256=sha(R/'PROTOCOL.md'),registry_sha256=sha(R/'registry.json')))
def pmasks(d,ix):
    chain=(d.close/d.preclose).cumprod()*100
    stage=pt.stage(chain,'frozen')
    clv=((d.close-d.low)/(d.high-d.low)).where(d.high!=d.low,.5).shift()
    vr=(d.volume/d.volume.rolling(20).mean()).shift()
    down=chain.pct_change().lt(0);streak=down.groupby((~down).cumsum()).cumsum().shift().fillna(0)
    gap=100*(d.open/d.preclose-1)
    a=stage.isin(['U','D'])&clv.lt(.4)&gap.le(-1)
    a|=stage.eq('R')&streak.ge(3)&vr.lt(.8)
    a|=stage.eq('C')&(d.close<d.open).shift().fillna(False)&ix.pct_change().shift().lt(0)&gap.lt(0)
    return dict(Pall=a,PUR=a&stage.isin(['U','R'])),stage
def valid(price,row,side):
    if not np.isfinite(price) or price<=0:return False
    return price<row.limit_up-.005 if side==1 else price>row.limit_down+.005
def newplan(module,i,date,price,clock,basis,known,ex_i=None,ex_clock=None,ex_price=np.nan,ex_basis=None,**kw):
    return dict(tid=module+'_'+str(i),module=module[0],variant=module,entry_i=int(i),entry=str(date.date()),entry_clock=clock,entry_price=float(price),entry_basis=basis,known=known,exit_i=ex_i,exit_clock=ex_clock,exit_price=float(ex_price),exit_basis=ex_basis,direction=-1 if module[0]=='R' else 1,**kw)
def load():
    d,masks,paths,spec,schedule=z.load();m=z.q.load_minutes()
    ix=d.date.map(pd.read_csv(b.old.B2/'source/sse_index.csv',parse_dates=['date']).set_index('date').close)
    pm,stage=pmasks(d,ix)
    bars={day:g.set_index('clock').to_dict('index') for day,g in m.groupby('date')}
    # Parent reconstruction before changed-account computation.
    pd0=pd.read_csv(b.old.P/'results/daily_features_and_cashflows.csv',parse_dates=['date'])
    pd.testing.assert_series_equal(d.date,pd0.date)
    np.testing.assert_allclose(d[['open','high','low','close','preclose','volume']],pd0[['open','high','low','close','preclose','volume']],atol=1e-12)
    assert stage.equals(pd0.stage)
    oldcomp=pd.read_csv('research/foxconn_t0_20260913_b03/results/comparison_trades.csv',parse_dates=['date'])
    oldp=oldcomp[oldcomp.name.eq('PT_PT_matrix')]
    now=pd0[pm['Pall']&pd0.date.ge('2024-01-02')]
    assert list(oldp.date)==list(now.date)
    np.testing.assert_allclose(pt.cashflow(now.open,now.close,now.date,'PT'),oldp.cash,atol=1e-7)
    nold=pd.read_csv(n11.R/'exit_trades.csv',parse_dates=['date','actual_exit','exit_date'])
    nlat=pd.read_csv('research/foxconn_overnight_20260917_b12/latency_trades.csv',parse_dates=['date','actual_exit','exit_date'])
    nf=pd.read_csv('research/foxconn_overnight_20260916_b10/features.csv')
    nmask=(100*((d.close/d.preclose).cumprod().pct_change(20))).shift().le(-16.1565018)
    np.testing.assert_allclose((100*((d.close/d.preclose).cumprod().pct_change(20))).shift(),nf.prev_r20,equal_nan=True,atol=1e-10)
    allplans={};alignment=[dict(module='P',check='B03 exact original opportunity dates/cash',n=len(now),status='PASS')]
    differences=[];days=d.to_dict('records')
    nbars={day:[dict(clock=clock,**v) for clock,v in bb.items()] for day,bb in bars.items()}
    for module,mask in pm.items():
        pp=[]
        for i in d.index[mask&d.date.ge(START)]:
            row=d.iloc[i];bb=bars.get(row.date,{}).get('09:40',{})
            pp.append(newplan(module,i,row.date,bb.get('open',np.nan),'09:35','bar_open_0935','09:25',i,'15:00',row.close,'daily_close',stage=stage.iloc[i]))
        allplans[module]=pp
    for module,stop,mode in [('N0',None,'1000_S0'),('N2',.02,'1000_S2')]:
        pp=[];old=nold[nold.entry.eq('C')&nold.exit_model.eq(mode)].set_index('date');lat=nlat[nlat.entry.eq('C')&nlat.exit_model.eq(mode)&nlat.latency.eq('next_bar_close')].set_index('date')
        for i in d.index[nmask&d.date.ge(START)]:
            row=d.iloc[i];xx=n11.morning_exit(row.close,days,nbars,i+1,'10:00',stop)
            exi=None;clock=None;price=np.nan;basis=None
            if pd.notna(xx.get('price')):
                dt=xx['actual_exit']
                cutbars={day:[v for v in vv if day<dt or v['clock']<=xx['clock']] for day,vv in nbars.items() if day<=dt}
                xxcut=n11.morning_exit(row.close,days[:int(d.index[d.date.eq(dt)][0])+1],cutbars,i+1,'10:00',stop)
                assert xxcut==xx,('N future-bar availability changed earlier decision',module,row.date)
                future=[(c,v) for c,v in bars[dt].items() if c>xx['clock']]
                if future:
                    clock,bar=future[0];price=float(bar['close']);exi=int(d.index[d.date.eq(dt)][0]);basis='bar_close_'+clock.replace(':','')
                if row.date in old.index:
                    rr=old.loc[row.date];ll=lat.loc[row.date]
                    assert xx['clock']==rr.exit_clock and xx['actual_exit']==rr.actual_exit and abs(xx['price']-rr.model_exit)<1e-8
                    assert clock==ll.latency_clock and abs(price-ll.model_exit)<1e-8
                    test=rr.to_frame().T
                    # Vector parent economics verified separately below.
                else:differences.append(dict(module=module,date=row.date,reason='raw_signal_outside_old_tradable_feature_universe'))
            pp.append(newplan(module,i,row.date,row.close,'15:00','daily_close','previous_close',exi,clock,price,basis,trigger=xx.get('reason'),observation_clock=xx.get('clock'),parent_price=xx.get('price'),parent_delayed=xx.get('delayed',False)))
        for frame,title in [(old,'B11'),(lat,'B12')]:
            cash,net,_=n8.pnl(frame.reset_index(),exitcol='model_exit')
            np.testing.assert_allclose(cash,frame.cash,atol=1e-7);np.testing.assert_allclose(net,frame.net,atol=1e-8)
            alignment.append(dict(module=module,check=title+' original prices/fees',n=len(frame),status='PASS'))
        assert len(old)==len(lat)==61
        allplans[module]=pp
    states=z.states(d,m);family,_=z.z.origins(masks)
    for module,key in RM.items():
        rule=next(v for v in z.registry() if v['id']==key);selected,_,_=z.choose(rule,states,family);pp=[]
        for i in d.index[family.ne('')&d.date.ge(START)]:
            row=d.iloc[i];act=selected.iloc[i]
            if i in paths[act].index:
                rr=paths[act].loc[i];exi=int(rr.exit_i) if pd.notna(rr.exit_i) else None;clock=rr.buy_clock if exi is not None else None;price=rr.buy_ref
            else:exi=None;clock=None;price=np.nan
            basis='daily_open' if clock=='09:25' else 'bar_open_'+clock.replace(':','') if clock else None
            pp.append(newplan(module,i,row.date,row.close,'15:00','daily_close','14:50',exi,clock,price,basis,family=family.iloc[i],state=states.state.iloc[i],action=act))
        allplans[module]=pp
    # Source price differences are reported, never select the favorable vendor.
    for day,g in m.groupby('date'):
        rr=d[d.date.eq(day)]
        if len(rr)!=1:continue
        rr=rr.iloc[0]
        differences.append(dict(module='all',date=day,reason='daily_vs_5m',open_diff=g.open.iloc[0]-rr.open,close_diff=g.close.iloc[-1]-rr.close,high_diff=g.high.max()-rr.high,low_diff=g.low.min()-rr.low,bars=len(g)))
    for module,pp in allplans.items():save('plans/'+module+'.csv',pp)
    save('parent_alignment.csv',alignment);save('source_differences.csv',differences)
    tests_prefix(d,ix)
    return d,m,bars,schedule,allplans
def tests_prefix(d,ix):
    pm,st=pmasks(d,ix);checks=[]
    for cut in [900,1400,len(d)-2]:
        alt=d.copy();alt.loc[cut+1:,['open','close','high','low','preclose','volume']]*=1.71
        ai=ix.copy();ai.iloc[cut+1:]*=.83
        am,ss=pmasks(alt,ai)
        for key in pm:pd.testing.assert_series_equal(pm[key].iloc[:cut+1],am[key].iloc[:cut+1])
        pd.testing.assert_series_equal(st.iloc[:cut+1],ss.iloc[:cut+1])
        for key in pm:pd.testing.assert_series_equal(pmasks(d.iloc[:cut+1],ix.iloc[:cut+1])[0][key],pm[key].iloc[:cut+1])
        checks.append(dict(cut=cut,status='PASS',scope='P frozen stages and signals'))
    n11.tests()
    js('prefix_validation.json',dict(checks=checks,N='inherited B11 future-bar/gap/locked/deadline tests',R='frozen B23 inherited causality; additional decision prefix checked by B24 verifier'))
def ddmetric(values):
    a=np.r_[0,np.asarray(values,float)];return float(np.max(np.maximum.accumulate(a)-a))
def durations(dates,values):
    peak=0.;peak_day=dates.iloc[0];under=None;lag=None;longest=behind=0
    for day,value in zip(dates,values):
        if value<peak-1e-7:
            if under is None:under=day
            longest=max(longest,(day-peak_day).days)
        else:peak=max(peak,value);peak_day=day;under=None
        if value< -1e-7:
            if lag is None:lag=day
            behind=max(behind,(day-lag).days)
        else:lag=None
    return longest,behind
def priority(o):
    return (0 if o['kind']=='exit' else 1,o.get('plan',{}).get('entry_i',0), {'previous_close':'00:00'}.get(o['known'],o['known']),'PNR'.index(o['module']),o['tid'])
def resolve(pending,exits,news,cap,sellable):
    """Solve netting/whole-order resource feasibility and policy slots jointly."""
    goodex=list(exits);reason={}
    for _ in range(len(exits)+3):
        counts={s:sum(t['direction']==s for t in pending.values())-sum(o['direction']==s for o in goodex) for s in [1,-1]}
        selected=list(goodex)
        reason={}
        for o in sorted(news,key=priority):
            side=o['direction']
            if counts[side]>=cap:reason[o['tid']]='policy_rejected'
            else:selected.append(o);counts[side]+=1
        buys=sorted([o for o in selected if o['side']==1],key=priority);sells=sorted([o for o in selected if o['side']==-1],key=priority)
        allowed=len(buys)+sellable//1000
        rejected=sells[allowed:]
        accepted=[o for o in selected if o not in rejected]
        for o in rejected:reason[o['tid']]='old_shares_insufficient'
        nex=[o for o in goodex if o in accepted]
        if len(nex)==len(goodex):return accepted,reason
        goodex=nex
    raise AssertionError('resource/policy resolution did not converge')
def simulate(d,bars,schedule,plans,rule,stock,bp,persist=False,intraday=False):
    start=int(d.index[d.date.ge(START)][0]);end=len(d)-1
    lots=[dict(lot_id=0,q=stock,date=d.date.iloc[start]-pd.DateOffset(years=2),div=0.)];nextlot=1
    pending={};trades={};newby=defaultdict(list);events=[];orders=[];pairs=[];disposals=[];lotrows=[];signals=[];funds=[];curve=[];stress=[]
    for mod in [rule['P'],rule['N'],rule['R']]:
        for t in plans.get(mod,[]):newby[t['entry_i']].append(t)
    cash=hc=external=paid=hpaid=fees=taxes=0.;recv=[];hr=[];minsell=stock;maxstock=stock
    initial=stock*d.close.iloc[start];previous_modules={v:0. for v in 'PNR'};previous_adjust=0.;oid=0
    def qty():return sum(l['q'] for l in lots)
    def reserve(day):return sum(l['q']*l['div']*b.old.taxrate(l['date'],day) for l in lots)
    def mark(day,price):
        eq=cash+sum(v for _,v in recv)+qty()*price-reserve(day)
        hold=hc+sum(v for _,v in hr)+stock*price
        return eq,hold
    def intent(t,kind,price,clock,basis,known):
        return dict(tid=t['tid'],module=t['module'],direction=t['direction'],kind=kind,side=t['direction']*(1 if kind=='entry' else -1),price=price,clock=clock,basis=basis,known=known,plan=t)
    for i in range(start,len(d)):
        row=d.iloc[i];day=row.date;dayin=dayfee=daytax=daypaid=dayhp=0.
        if row.dividend_today:
            recv.append((schedule.get(day,len(d)+10),qty()*row.dividend_today));hr.append((schedule.get(day,len(d)+10),stock*row.dividend_today))
            for lot in lots:lot['div']+=row.dividend_today
            for t in pending.values():t['dividend']+=t['direction']*1000*row.dividend_today
        exby=defaultdict(list)
        for t in list(pending.values()):
            due=t['exit_i']
            if t.get('retry') or (due is not None and due<i):
                clock='09:25';price=float(row.open);basis='daily_open'
            elif due==i:clock=t['exit_clock'];price=t['exit_price'];basis=t['exit_basis']
            else:continue
            exby[(clock,basis)].append(intent(t,'exit',price,clock,basis,'previous_close'))
        # P entries schedule same-day close exit only after accepted.
        groups=set(exby)|{(t['entry_clock'],t['entry_basis']) for t in newby[i]}
        if any(t['module']=='P' for t in newby[i]):groups.add(('15:00','daily_close'))
        if intraday:groups|={(c,'mark_close') for c in bars.get(day,{})}
        groups.add(('15:00','daily_close'))
        paid_today=False
        for clock,basis in sorted(groups,key=lambda v:(v[0],0 if v[1].startswith('bar_close') else 1 if v[1]=='mark_close' else 2)):
            if clock=='15:00' and not paid_today:
                for due,amt in list(recv):
                    if due<=i:cash+=amt;paid+=amt;daypaid+=amt;recv.remove((due,amt))
                for due,amt in list(hr):
                    if due<=i:hc+=amt;hpaid+=amt;dayhp+=amt;hr.remove((due,amt))
                paid_today=True
            if basis=='mark_close':
                price=bars[day][clock]['close'];eq,he=mark(day,price)
                stress.append(dict(date=day,clock=clock,basis=basis,relative=eq-he,absolute=eq-initial-external,hold_absolute=he-initial-external));continue
            exits=exby.get((clock,basis),[]).copy()
            if clock=='15:00' and basis=='daily_close':
                exits += [intent(t,'exit',float(row.close),clock,basis,'09:35') for t in list(pending.values()) if t['module']=='P' and t['entry_i']==i]
            news=[intent(t,'entry',t['entry_price'],clock,basis,t['known']) for t in newby[i] if t['entry_clock']==clock and t['entry_basis']==basis]
            eligibleex=[];eligiblenew=[];why={}
            for o in exits+news:
                p=o['price'];reason='quote_unknown' if not np.isfinite(p) or p<=0 else 'untradeable' if not valid(p,row,o['side']) else None
                if basis=='daily_close' and row.volume<=0:reason='untradeable'
                if basis.startswith('bar_close_') and bars.get(day,{}).get(clock,{}).get('volume',0)<=0:reason='untradeable'
                if reason:
                    why[o['tid']]=reason
                    if o['kind']=='exit':pending[o['tid']]['retry']=True
                elif o['kind']=='exit':eligibleex.append(o)
                else:eligiblenew.append(o)
            sellable=sum(l['q'] for l in lots if l['date']<day)
            cap={'F':10**9,'L1':1,'L2':2}[rule['policy']]
            accepted,reasons=resolve(pending,eligibleex,eligiblenew,cap,sellable);why.update(reasons)
            accepted_ids={(o['tid'],o['kind']) for o in accepted}
            for o in exits:
                if (o['tid'],'exit') not in accepted_ids:
                    pending[o['tid']]['retry']=True
                    events.append(dict(date=day,clock=clock,tid=o['tid'],kind='exit',reason=why.get(o['tid'],'old_shares_insufficient')))
            for o in news:
                signals.append(dict(date=day,clock=clock,tid=o['tid'],module=o['module'],reason='accepted' if (o['tid'],'entry') in accepted_ids else why.get(o['tid'],'policy_rejected'),known=o['known'],basis=basis,price=o['price']))
            if not accepted:continue
            price=accepted[0]['price'];assert all(abs(o['price']-price)<1e-8 for o in accepted)
            buys=sorted([o for o in accepted if o['side']==1],key=priority);sells=sorted([o for o in accepted if o['side']==-1],key=priority)
            for buy,sell in zip(buys,sells):pairs.append(dict(date=day,clock=clock,basis=basis,buy_tid=buy['tid'],sell_tid=sell['tid'],quantity=1000,reference=price))
            net=1000*(len(buys)-len(sells));fee=tax=slipcost=deposit=0.;order_id=None
            if net:
                oid+=1;order_id=oid;side=1 if net>0 else -1;quant=abs(net);value=quant*price*(1+side*bp/10000);slipcost=quant*price*bp/10000
                fee=b.old.sf(value,day,side==-1)
                beforecash=cash;beforeqty=qty()
                if side==1:
                    cost=value+fee;deposit=max(0.,cost+reserve(day)-cash);cash+=deposit;hc+=deposit;external+=deposit;dayin+=deposit;cash-=cost
                    funds.append(dict(date=day,clock=clock,order_id=oid,buy_cost=cost,deposit=deposit,external=external,cash_before=beforecash,tax_reserve=reserve(day)))
                    lots.append(dict(lot_id=nextlot,q=quant,date=day,div=0.));nextlot+=1
                else:
                    need=quant
                    for lot in list(lots):
                        if lot['date']>=day:continue
                        n=min(need,lot['q']);lt=n*lot['div']*b.old.taxrate(lot['date'],day);tax+=lt
                        disposals.append(dict(order_id=oid,date=day,lot_id=lot['lot_id'],acquired=lot['date'],quantity=n,dividend_per_share=lot['div'],tax=lt))
                        lot['q']-=n;need-=n
                        if lot['q']==0:lots.remove(lot)
                        if need==0:break
                    assert need==0
                    cash+=value-fee-tax
                fees+=fee;taxes+=tax;dayfee+=fee;daytax+=tax
                orders.append(dict(order_id=oid,date=day,clock=clock,basis=basis,side='BUY' if net>0 else 'SELL',quantity=quant,reference=price,value=value,fee=fee,tax=tax,slip=slipcost,deposit=deposit,cash=cash,shares=qty(),before_shares=beforeqty,old_available=sellable))
            # Gross logical reference cash cancels internal pairs; external costs only.
            external_side=1 if net>0 else -1 if net<0 else 0
            contributors=[o for o in accepted if o['side']==external_side];den=len(contributors)
            for o in sorted(accepted,key=priority):
                if o['kind']=='entry':
                    t=copy.deepcopy(o['plan']);t.update(cash=0.,dividend=0.,fee=0.,tax=0.,slip=0.,retry=False,actual_exit_i=None,actual_exit=None,actual_exit_clock=None)
                    trades[t['tid']]=t;pending[t['tid']]=t
                t=trades[o['tid']];fraction=(1/den if o['side']==external_side else 0.)
                t['cash']+=-o['side']*1000*price-(fee+tax+slipcost)*fraction
                t['fee']+=fee*fraction;t['tax']+=tax*fraction;t['slip']+=slipcost*fraction
                events.append(dict(date=day,clock=clock,tid=o['tid'],module=o['module'],kind=o['kind'],side=o['side'],quantity=1000,basis=basis,reference=price,order_id=order_id,external_share=fraction,fee=fee*fraction,tax=tax*fraction,slip=slipcost*fraction,reason='filled',known=o['known']))
                if o['kind']=='exit':
                    t['actual_exit_i']=i;t['actual_exit']=str(day.date());t['actual_exit_clock']=clock
                    t['realized']=t['cash']+t['dividend'];pending.pop(t['tid']);t['retry']=False
            minsell=min(minsell,sum(l['q'] for l in lots if l['date']<day));maxstock=max(maxstock,qty())
            assert qty()==stock+1000*sum(t['direction'] for t in pending.values())
            assert cash>=-1e-6
            eq,he=mark(day,price)
            stress.append(dict(date=day,clock=clock,basis=basis,relative=eq-he,absolute=eq-initial-external,hold_absolute=he-initial-external))
        eq,he=mark(day,float(row.close));res=reserve(day)
        mods={v:sum(t['cash']+t['dividend']+(t['direction']*1000*row.close if tid in pending else 0.) for tid,t in trades.items() if t['module']==v) for v in 'PNR'}
        assert abs(sum(mods.values())-res-(eq-he))<1e-5,(rule['id'],day,mods,res,eq-he)
        rr=dict(date=day,cash=cash,hold_cash=hc,shares=qty(),old_available=sum(l['q'] for l in lots if l['date']<day),receivable=sum(v for _,v in recv),hold_receivable=sum(v for _,v in hr),tax_reserve=res,fee=dayfee,tax=daytax,payment=daypaid,hold_payment=dayhp,deposit=dayin,external=external,equity=eq,hold_equity=he,relative=eq-he,absolute=eq-initial-external,hold_absolute=he-initial-external,pending_add=sum(t['direction']==1 for t in pending.values()),pending_reduce=sum(t['direction']==-1 for t in pending.values()),adjust=-res,adjust_pnl=-res-previous_adjust)
        for v in 'PNR':rr[v]=mods[v];rr[v+'_pnl']=mods[v]-previous_modules[v]
        previous_modules=mods;previous_adjust=-res;curve.append(rr)
        for lot in lots:lotrows.append(dict(lot_id=lot['lot_id'],q=lot['q'],div=lot['div'],acquired=lot['date'],date=day))
    a=pd.DataFrame(curve);tt=pd.DataFrame(list(trades.values()));ss=pd.DataFrame(signals)
    done=tt[tt.actual_exit_i.notna()].sort_values(['actual_exit_i','actual_exit_clock','tid']) if len(tt) else tt;pn=done.realized if len(done) else pd.Series(dtype=float)
    run=longest=0
    for v in pn:run=run+1 if v<0 else 0;longest=max(longest,run)
    recovery,behind=durations(a.date,a.relative)
    meta=dict(**rule,stock=stock,bp=bp,increment=a.relative.iloc[-1],relative_mdd=ddmetric(a.relative),absolute_mdd=ddmetric(a.absolute),hold_mdd=ddmetric(a.hold_absolute),absolute_profit=a.absolute.iloc[-1],completed=len(done),pending=len(pending),signals=len(ss),accepted=len(tt),policy_rejected=int(ss.reason.eq('policy_rejected').sum()) if len(ss) else 0,inventory_rejected=int(ss.reason.eq('old_shares_insufficient').sum()) if len(ss) else 0,quote_unknown=int(ss.reason.eq('quote_unknown').sum()) if len(ss) else 0,untradeable=int(ss.reason.eq('untradeable').sum()) if len(ss) else 0,exit_failed=sum(e['kind']=='exit' and e['reason']!='filled' for e in events),inventory_exit_failed=sum(e['kind']=='exit' and e['reason']=='old_shares_insufficient' for e in events),win=100*(pn>0).mean() if len(pn) else np.nan,worst=pn.min() if len(pn) else 0,worst5=pn.nsmallest(5).sum(),avg_profit=pn[pn>0].mean(),avg_loss=pn[pn<0].mean(),longest_loss=longest,recovery_days=recovery,behind_days=behind,winning_day_pct=100*a.relative.diff().fillna(a.relative.iloc[0]).gt(0).mean(),deposits=external,max_deposit=max([v['deposit'] for v in funds],default=0),max_buy_cash=max([v['buy_cost'] for v in funds],default=0),buy_cash_total=sum(v['buy_cost'] for v in funds),deposit_yuan_days=sum(v['deposit']*(d.date.iloc[-1]-v['date']).days for v in funds),max_shares=maxstock,min_old_available=minsell,fee=fees,tax=taxes,terminal_reserve=a.tax_reserve.iloc[-1],dividend_relative=(a.payment-a.hold_payment).sum()+a.receivable.iloc[-1]-a.hold_receivable.iloc[-1],internal_pairs=len(pairs),external_orders=len(orders),slippage=sum(v['slip'] for v in orders),reference_cash=sum((1 if v['side']=='SELL' else -1)*v['quantity']*v['reference'] for v in orders),pending_mark=(qty()-stock)*d.close.iloc[-1],max_batch_days=max([(pd.Timestamp(t['actual_exit']) if t['actual_exit'] else d.date.iloc[-1])-pd.Timestamp(t['entry']) for t in trades.values()],default=pd.Timedelta(0)).days,event_relative_mdd=ddmetric([v['relative'] for v in stress]),event_absolute_mdd=ddmetric([v['absolute'] for v in stress]))
    if persist:
        name=f"{rule['id']}_{stock}_{bp}"
        for folder,data in [('accounts',a),('trades',tt),('signals',ss),('events',events),('orders',orders),('pairs',pairs),('disposals',disposals),('lots',lotrows),('funds',funds),('stress',stress)]:save(folder+'/'+name+'.csv.gz',data)
    return meta,a,tt,ss
def run():
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in {**frozen['files'],**frozen['code']}.items():assert sha(p)==h,p
    oldplans={p.name:sha(p) for p in (R/'plans').glob('*.csv')} if (R/'plans').exists() else {}
    d,m,bars,schedule,plans=load();reg=registry()
    if oldplans:
        current={p.name:sha(p) for p in (R/'plans').glob('*.csv')}
        assert oldplans==current,'historical path changed unexpectedly; retain outputs and investigate'
        js('causal_revision_path_alignment.json',dict(status='PASS',unchanged_paths=len(current),scope='N driver no future-day completeness filter; all historical plan bytes unchanged'))
    tests()
    needs=[];K=3000
    for rule in reg:
        if rule['policy']!='F':continue
        k=3000
        while True:
            met,_,_,_=simulate(d,bars,schedule,plans,rule,k,5)
            if met['inventory_rejected']==0 and met['inventory_exit_failed']==0:break
            k+=1000;assert k<=100000,'resource cannot resolve; retain failure for inspection'
        K=max(K,k);needs.append(dict(combo=rule['combo'],minimum_initial_old_shares=k-met['min_old_available'],diagnostic_stock=k,inventory_rejected=met['inventory_rejected']))
    save('resource_diagnostic.csv',needs);js('resource_lock.json',dict(K=K,determined_before_profit_rankings=True,algorithm='all44F first3000; increase only if inventory blocked; minimum historical requirement inferred from actual old-share trough; no lower-resource account grid',resources=[3000]+([K] if K>3000 else [])))
    rows=[];cache={}
    for stock in [3000]+([K] if K>3000 else []):
        for rule in reg:
            for bp in [5,11,20]:
                met,a,t,s=simulate(d,bars,schedule,plans,rule,stock,bp,True)
                rows.append(met);cache[(rule['id'],stock,bp)]=(a,t,s)
                print('ACCOUNT',rule['id'],stock,bp,round(met['increment'],4),flush=True)
    summary=save('account_summary.csv',rows)
    analyze(d,bars,schedule,plans,summary,cache)
    for p,h in frozen['files'].items():assert sha(p)==h,p
    js('calculation_validation.json',dict(status='PASS',accounts=len(rows),registered=132,versions=44,K=K,parent_files=len(frozen['files']),end=str(d.date.max().date())))
    js('manifest.json',dict(files={str(p):sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['manifest.json','calculation.log','verification.log','failure.json']}))
def tests():
    def t(key,direction=1,module='P'):return dict(tid=key,direction=direction,module=module,known='09:25')
    def o(key,kind,side,direction=1,module='P'):return dict(**t(key,direction,module),kind=kind,side=side)
    p=t('p');ex=o('p','exit',-1)
    n=o('n','entry',1,1,'N');r=o('r','entry',-1,-1,'R')
    a,_=resolve({'p':p},[ex],[n,r],1,1000);assert len(a)==3 and sum(v['side'] for v in a)==-1
    a,_=resolve({},[],[n,r],1,0);assert len(a)==2 and sum(v['side'] for v in a)==0
    a,why=resolve({'p':p},[],[n],1,5000);assert not a and why['n']=='policy_rejected'
    a,why=resolve({'p':p},[ex],[],1,0);assert not a
    a,_=resolve({'p':p},[ex],[n],1,0);assert len(a)==2 # valid simultaneous ownership transfer
    a,why=resolve({'p':p},[],[n],2,0);assert len(a)==1
    dates=pd.date_range('2026-01-01',periods=4)
    d=pd.DataFrame(dict(date=dates,open=[100]*4,close=[100]*4,limit_up=[110]*4,limit_down=[90]*4,volume=[100]*4,dividend_today=[0,1,0,0]))
    rule=dict(id='synthetic',P='Pall',N='N2',R='R1',policy='F',combo='synthetic',modules=3)
    plans={'Pall':[newplan('Pall',0,dates[0],100,'09:35','bar_open_0935','09:25',0,'15:00',100,'daily_close')],'N2':[newplan('N2',0,dates[0],100,'15:00','daily_close','previous_close',1,'10:05',100,'bar_close_1005')],'R1':[newplan('R1',0,dates[0],100,'15:00','daily_close','14:50',2,'09:25',100,'daily_open')]}
    met,a,tt,_=simulate(d,{dates[1]:{'10:05':dict(volume=100)}}, {dates[1]:1},plans,rule,1000,5)
    assert met['completed']==3 and met['internal_pairs']==1 and met['external_orders']==4
    assert a.shares.tolist()==[1000,0,1000,1000]
    assert abs(a.iloc[-1].relative-(tt.cash.sum()+tt.dividend.sum()-a.iloc[-1].tax_reserve))<1e-6
    # No old stock: P same-day close cannot externally sell its new purchase, retries day1.
    rr=dict(rule,P='Pall',N='-',R='-')
    met,a,tt,ss=simulate(d,{dates[1]:{'10:05':dict(volume=100)}}, {dates[1]:1},plans,rr,0,5)
    assert tt.actual_exit_i.iloc[0]==1 and met['exit_failed']==1
    # N/R pair opens with zero broker inventory, different dates exit: N must wait for R's bought shares to age.
    rr=dict(rule,P='-',N='N2',R='R1')
    met,a,tt,ss=simulate(d,{dates[1]:{'10:05':dict(volume=100)}}, {dates[1]:1},plans,rr,0,5)
    assert met['accepted']==2 and tt.set_index('module').loc['N','actual_exit_i']==2
    assert ddmetric([10,-5,5])==15
    js('synthetic_validation.json',dict(status='PASS',cases=['three_way_close_net','two_opposite_entries_distinct_future_exits','L1_full','L2_slot','Tplus1_new_shares_retry','exit_failure_slot_retained','dividend_receivable_FIFO_transfer','external_flow_identity','initial_zero_drawdown']))

def analyze(d,bars,schedule,plans,s,cache):
    rows=[];edges=[];gains=[];concentrations=[];periods=[];policy=[];mirrors=[];front=[]
    by={(v.id,v.stock,v.bp):v for v in s.itertuples()}
    metrics=['increment','relative_mdd','absolute_mdd','deposits','max_shares','min_old_available','worst','worst5','completed','win','longest_loss','recovery_days']
    for rr in s.itertuples():
        a,t,sg=cache[rr.id,rr.stock,rr.bp]
        for year,gg in a.groupby(a.date.dt.year):
            ix=gg.index;prior=a.loc[ix[0]-1] if ix[0]>0 else None
            periods.append(dict(id=rr.id,stock=rr.stock,bp=rr.bp,period=str(year),increment=gg.relative.iloc[-1]-(prior.relative if prior is not None else 0),absolute_profit=gg.absolute.iloc[-1]-(prior.absolute if prior is not None else 0),relative_mdd=ddmetric(np.r_[0,gg.relative.to_numpy()-(prior.relative if prior is not None else 0)]),absolute_mdd=ddmetric(np.r_[0,gg.absolute.to_numpy()-(prior.absolute if prior is not None else 0)])))
        gg=a[a.date.lt('2024-01-01')]
        periods.append(dict(id=rr.id,stock=rr.stock,bp=rr.bp,period='2022-2023',increment=gg.relative.iloc[-1],absolute_profit=gg.absolute.iloc[-1],relative_mdd=ddmetric(gg.relative),absolute_mdd=ddmetric(gg.absolute)))
        base=by[BASE,rr.stock,rr.bp]
        full=by[rr.combo+'_F',rr.stock,rr.bp]
        one=s[(s.stock==rr.stock)&(s.bp==rr.bp)&(s.modules==1)].sort_values(['increment','id'],ascending=[False,True]).iloc[0]
        for ref in dict.fromkeys([BASE,full.id,one.id]):
            br=by[ref,rr.stock,rr.bp];ba,bt,bs=cache[ref,rr.stock,rr.bp]
            ds=(a.relative-ba.relative).diff().fillna(a.relative.iloc[0]-ba.relative.iloc[0]);v=ds.sort_values(ascending=False)
            rows.append(dict(id=rr.id,stock=rr.stock,bp=rr.bp,reference=ref,**{k:getattr(rr,k)-getattr(br,k) for k in metrics},reference_cash_change=rr.reference_cash-br.reference_cash,slippage_change=rr.slippage-br.slippage,pending_mark_change=rr.pending_mark-br.pending_mark,fee_change=rr.fee-br.fee,tax_change=rr.tax-br.tax,reserve_change=rr.terminal_reserve-br.terminal_reserve,dividend_change=rr.dividend_relative-br.dividend_relative))
            concentrations.append(dict(id=rr.id,stock=rr.stock,bp=rr.bp,reference=ref,delta=rr.increment-br.increment,top1=v.head(1).sum(),top3=v.head(3).sum(),top5=v.head(5).sum(),without1=rr.increment-br.increment-v.head(1).sum(),without3=rr.increment-br.increment-v.head(3).sum(),without5=rr.increment-br.increment-v.head(5).sum()))
            for side,inds in [('gain',ds.nlargest(5).index),('loss',ds.nsmallest(5).index)]:
                for ii in inds:gains.append(dict(id=rr.id,stock=rr.stock,bp=rr.bp,reference=ref,side=side,date=a.date.iloc[ii],change=ds.iloc[ii],P=a.P_pnl.iloc[ii]-ba.P_pnl.iloc[ii],N=a.N_pnl.iloc[ii]-ba.N_pnl.iloc[ii],R=a.R_pnl.iloc[ii]-ba.R_pnl.iloc[ii],adjustment=a.adjust_pnl.iloc[ii]-ba.adjust_pnl.iloc[ii]))
        if rr.policy!='F':
            fa,ft,fs=cache[rr.combo+'_F',rr.stock,rr.bp]
            removed=ft[~ft.tid.isin(t.tid)] if len(t) else ft
            kept=ft[ft.tid.isin(t.tid)] if len(t) else ft.iloc[:0]
            loss=removed.realized[removed.actual_exit_i.notna()] if len(removed) else pd.Series(dtype=float)
            policy.append(dict(id=rr.id,stock=rr.stock,bp=rr.bp,reference=rr.combo+'_F',removed=len(removed),avoided_loss=-loss[loss<0].sum(),missed_profit=loss[loss>0].sum(),actual_increment_change=rr.increment-full.increment,remaining_interaction=rr.increment-full.increment+loss.sum(),note='removed logical profits use F allocation; remaining interaction includes changed fees/tax/netting/pending paths'))
        # Predeclared adjacent comparison changes only one of P,N,R,policy, includes removals.
        for other in s[(s.stock==rr.stock)&(s.bp==rr.bp)].itertuples():
            dims=[v for v in ['P','N','R','policy'] if getattr(rr,v)!=getattr(other,v)]
            if len(dims)==1:
                edges.append(dict(from_id=rr.id,to_id=other.id,stock=rr.stock,bp=rr.bp,dimension=dims[0],**{k:getattr(other,k)-getattr(rr,k) for k in metrics},reference_cash_change=other.reference_cash-rr.reference_cash,slippage_change=other.slippage-rr.slippage,pending_mark_change=other.pending_mark-rr.pending_mark,fee_change=other.fee-rr.fee,tax_change=other.tax-rr.tax,reserve_change=other.terminal_reserve-rr.terminal_reserve))
        # Full-account identity bridge to separately recomputed single modules, not old cash ledgers.
        singles=[]
        for mod in [rr.P,rr.N,rr.R]:
            if mod!='-':singles.append(by[mod+'_'+rr.policy,rr.stock,rr.bp])
        rows.append(dict(id=rr.id,stock=rr.stock,bp=rr.bp,reference='sum_same_window_single_accounts',increment=rr.increment-sum(v.increment for v in singles),reference_cash_change=rr.reference_cash-sum(v.reference_cash for v in singles),slippage_change=rr.slippage-sum(v.slippage for v in singles),pending_mark_change=rr.pending_mark-sum(v.pending_mark for v in singles),fee_change=rr.fee-sum(v.fee for v in singles),tax_change=rr.tax-sum(v.tax for v in singles),reserve_change=rr.terminal_reserve-sum(v.terminal_reserve for v in singles),dividend_change=rr.dividend_relative-sum(v.dividend_relative for v in singles),note='interaction; policy changes participation when modules share slots'))
        if rr.bp==5 and len(t):
            for yr,g in t[t.actual_exit_i.notna()].groupby(pd.to_datetime(t[t.actual_exit_i.notna()].entry).dt.year):
                if g.realized.sum()>=0:continue
                # Independently cost opposite reference legs; no reverse-account certification.
                vals=[]
                for tr in g.itertuples():
                    ep=tr.entry_price
                    exit_events=pd.read_csv(R/f'events/{rr.id}_{rr.stock}_{rr.bp}.csv.gz')
                    ev=exit_events[(exit_events.tid==tr.tid)&(exit_events.kind=='exit')&(exit_events.reason=='filled')].iloc[0]
                    xp=ev.reference;ed=pd.Timestamp(tr.entry);xd=pd.Timestamp(tr.actual_exit)
                    if tr.direction==1:
                        sv=1000*ep*.9995;bv=1000*xp*1.0005
                        val=sv-bv-b.old.sf(sv,ed,True)-b.old.sf(bv,xd)-tr.dividend
                    else:
                        bv=1000*ep*1.0005;sv=1000*xp*.9995
                        val=sv-bv-b.old.sf(bv,ed)-b.old.sf(sv,xd,True)-tr.dividend
                    vals.append(val)
                mirrors.append(dict(id=rr.id,stock=rr.stock,year=yr,n=len(g),original=g.realized.sum(),opposite_price_fees_gross_dividend=sum(vals),status='candidate only; reverse shared FIFO account unverified, not included in pool'))
    for v in rows:
        bridge=v['reference_cash_change']-v['slippage_change']-v['fee_change']-v['tax_change']-v['reserve_change']+v['dividend_change']+v['pending_mark_change']
        assert abs(bridge-v['increment'])<1e-5,(v['id'],v['reference'],bridge,v['increment'])
        v['account_identity_error']=bridge-v['increment']
    save('comparisons.csv',rows);save('adjacent_rules.csv',edges);save('key_dates.csv',gains);save('concentration.csv',concentrations);save('periods.csv',periods);save('policy_opportunity_cost.csv',policy);save('opposite_direction_regions.csv',mirrors)
    # Exact multiobjective dominance: profit, two drawdowns, extra cash and peak shares.
    chosen={}
    for (stock,bp),pool in s.groupby(['stock','bp']):
        for r in pool.itertuples():
            dom=pool[(pool.increment>=r.increment-1e-8)&(pool.relative_mdd<=r.relative_mdd+1e-8)&(pool.absolute_mdd<=r.absolute_mdd+1e-8)&(pool.deposits<=r.deposits+1e-8)&(pool.max_shares<=r.max_shares)]
            strict=(dom.increment>r.increment+1e-7)|(dom.relative_mdd<r.relative_mdd-1e-7)|(dom.absolute_mdd<r.absolute_mdd-1e-7)|(dom.deposits<r.deposits-1e-7)|(dom.max_shares<r.max_shares)
            front.append(dict(id=r.id,stock=stock,bp=bp,pareto=not strict.any(),dominated_by=';'.join(dom.loc[strict,'id'])))
        if bp!=5:continue
        fp=pd.DataFrame(front);ids=fp[(fp.stock==stock)&(fp.bp==bp)&fp.pareto].id
        nd=pool[pool.id.isin(ids)]
        champion=pool.sort_values(['increment','modules','id'],ascending=[False,True,True]).iloc[0]
        base=pool[pool.id==BASE].iloc[0]
        improving=nd[(nd.relative_mdd<base.relative_mdd-1e-7)&(nd.absolute_mdd<base.absolute_mdd-1e-7)]
        risk=improving.sort_values(['increment','modules','id'],ascending=[False,True,True]).iloc[0] if len(improving) else None
        simple=nd.sort_values(['modules','increment','id'],ascending=[True,False,True]).iloc[0]
        picks=list(dict.fromkeys([champion.id]+([risk.id] if risk is not None else [])+[simple.id]))
        chosen[int(stock)]=dict(profit=champion.id,risk=risk.id if risk is not None else None,simple=simple.id,focus=list(dict.fromkeys([BASE]+picks)))
    save('pareto.csv',front);js('focus.json',chosen)
    fine(d,bars,plans,s,cache,chosen)
    stressrows=[];co=[];corr=[]
    for stock,ch in chosen.items():
        for key in ch['focus']:
            rr=next(v for v in registry() if v['id']==key)
            met,a,t,sg=simulate(d,bars,schedule,plans,rr,int(stock),5,False,True)
            stressrows.append(dict(id=key,stock=stock,bp=5,observed_5m_relative_mdd=met['event_relative_mdd'],observed_5m_absolute_mdd=met['event_absolute_mdd'],coverage='available 5m close plus actual event reference; not unknown intrabar max'))
            for aa,bb in itertools.combinations('PNR',2):
                corr.append(dict(id=key,stock=stock,first=aa,second=bb,all_days=len(a),correlation=a[aa+'_pnl'].corr(a[bb+'_pnl']),both_loss_days=int((a[aa+'_pnl'].lt(0)&a[bb+'_pnl'].lt(0)).sum())))
            bad=a.assign(pnl=a.relative.diff().fillna(a.relative.iloc[0])).nsmallest(10,'pnl')
            for v in bad.itertuples():co.append(dict(id=key,stock=stock,date=v.date,relative_day=v.pnl,P=v.P_pnl,N=v.N_pnl,R=v.R_pnl,adjust=v.adjust_pnl,absolute_day=v.absolute-a.absolute.iloc[v.Index-1] if v.Index else v.absolute))
    save('sampled_intraday_stress.csv',stressrows);save('daily_correlations.csv',corr);save('worst_daily_contributions.csv',co)
    bridge_old(d,s,cache)
    report(s,chosen,periods,policy,co,stressrows)
def fine(d,bars,plans,s,cache,chosen):
    raw=pd.read_csv(b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime'])
    raw['clock']=raw.datetime.dt.strftime('%H:%M');qualified={}
    expected=[b.minutes_after(start,k) for start in z.x.STARTS for k in range(1,6)]
    for day,g in raw.groupby('date'):
        g=g.sort_values('clock');rr=d[d.date.eq(day)]
        if len(rr)!=1 or list(g.clock)!=expected:continue
        row=rr.iloc[0]
        if max(abs(g.open.iloc[0]-row.open),abs(g.close.iloc[-1]-row.close),abs(g.high.max()-row.high),abs(g.low.min()-row.low))>=.011:continue
        if not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))&(g.volume>=0)).all():continue
        qualified[day]=g
    details=[];coverage=[]
    for rr in s[s.bp.eq(5)].itertuples():
        a,t,sg=cache[rr.id,rr.stock,rr.bp]
        for tr in t.itertuples():
            ent=pd.Timestamp(tr.entry);ex=pd.Timestamp(tr.actual_exit) if pd.notna(tr.actual_exit) else None
            en=ent in qualified;out=ex in qualified;auction=tr.actual_exit_clock=='09:25' or tr.entry_clock=='15:00'
            price_diff=np.nan
            if en and tr.module=='P':
                g=qualified[ent];bar=g[g.clock=='09:36'];price_diff=bar.open.iloc[0]-tr.entry_price if len(bar)==1 else np.nan
            details.append(dict(id=rr.id,stock=rr.stock,tid=tr.tid,module=tr.module,entry=ent,exit=ex,entry_fine=en,exit_fine=out,both=en and out,state_fine=en if tr.module=='R' else None,auction_proxy_uncertified=auction,entry_price_diff=price_diff,realized=tr.realized if pd.notna(tr.actual_exit_i) else np.nan))
    ff=save('fine_coverage_detail.csv',details)
    save('fine_coverage_summary.csv',ff.groupby(['id','stock','module']).agg(n=('tid','size'),entry_fine=('entry_fine','sum'),exit_fine=('exit_fine','sum'),both=('both','sum'),auction_uncertified=('auction_proxy_uncertified','sum')).reset_index())
    js('fine_quality.json',dict(qualified_days=len(qualified),source=str(b.r1.B13/'tdx_recovered_1m.csv'),interpretation='date coverage is not fill certification; auction always unknown; P entry quote independently compared; R inherited path comparisons in B23; N B13 inherited9 paired paths'))
def bridge_old(d,s,cache):
    rows=[]
    for mod in ['Pall','PUR','N0','N2']:
        a,t,ss=cache[mod+'_F',3000,5]
        # New account exact decomposition into logical reference profit, fees, FIFO and reserve.
        vals=t.cash.sum()+t.dividend.sum()+sum(v.direction*1000*d.close.iloc[-1] for v in t[t.actual_exit_i.isna()].itertuples())
        rr=s[(s.id==mod+'_F')&(s.stock==3000)&(s.bp==5)].iloc[0]
        rows.append(dict(module=mod,new_window='2022-start',new_account_increment=rr.increment,logical_marked_cash=vals,terminal_reserve=rr.terminal_reserve,identity_error=rr.increment-vals+rr.terminal_reserve,date_fee=rr.fee,FIFO_tax=rr.tax,entry_timing='09:35 interval open' if mod[0]=='P' else 'close',exit_timing='close with T+1 old shares' if mod[0]=='P' else 'B12 next bar close'))
    save('account_bridge.csv',rows)
def report(s,chosen,periods,policy,co,stressrows):
    cols=['id','increment','relative_mdd','absolute_mdd','hold_mdd','completed','win','worst','worst5','deposits','max_buy_cash','max_shares','min_old_available','policy_rejected']
    text=['# B24多方向同时参与与收益回撤组合研究报告','状态：submitted（须结合独立验证文件）。数据截至2026-09-11；共同2022起点；历史模型事实，非实际成交。']
    for stock,ch in chosen.items():
        p=s[(s.stock==stock)&(s.bp==5)].set_index('id');a=p.loc[BASE];best=p.loc[ch['profit']]
        text+= [f'共同旧仓{stock}股、每笔1000股、主成本每边0.05%加费用税费。全机会主对照：P四阶段09:35买/收盘卖旧股＋N深跌收盘买/2%触发或10:00决策后下一bar收价卖＋R原两入口卖出/原买回。最终相对持有多赚{a.increment:,.2f}元，做T相对回撤{a.relative_mdd:,.2f}元，全账户剔除补款回撤{a.absolute_mdd:,.2f}元（持有{a.hold_mdd:,.2f}）。累计补款{a.deposits:,.2f}元、最高持股{int(a.max_shares)}股。']
        text+= [f'本固定矩阵利润最多：{best.name}，净增量{best.increment:,.2f}元，比主对照多{best.increment-a.increment:,.2f}元；两种回撤{best.relative_mdd:,.2f}/{best.absolute_mdd:,.2f}元；补款{best.deposits:,.2f}元。此处为已比较历史最大值，不是未来最优。']
        text+=['## 主对照与最多三种取舍',s[(s.stock==stock)&s.bp.eq(5)&s.id.isin(ch['focus'])][cols].to_markdown(index=False,floatfmt='.2f')]
        if ch['risk'] is None:text+=['观点：本轮没有找到同时降低主对照两种回撤的非支配候选，不强造风险改善方案。']
        else:
            rr=p.loc[ch['risk']]
            text+=[f'同时降低两种回撤且利润最高的非支配取舍：{rr.name}，比主对照利润变化{rr.increment-a.increment:,.2f}元，相对回撤降低{a.relative_mdd-rr.relative_mdd:,.2f}元，全账户回撤降低{a.absolute_mdd-rr.absolute_mdd:,.2f}元；补款{rr.deposits:,.2f}元。']
        text+=['## 全44版本组合与三政策（主成本）',s[(s.stock==stock)&s.bp.eq(5)][cols].to_markdown(index=False,floatfmt='.2f')]
        text+=['## 主对照与取舍三成本',s[(s.stock==stock)&s.id.isin(ch['focus'])][['bp']+cols].to_markdown(index=False,floatfmt='.2f')]
        pf=pd.DataFrame(periods);text+=['## 逐年及2022—2023',pf[(pf.stock==stock)&pf.id.isin(ch['focus'])].to_markdown(index=False,floatfmt='.2f')]
        pol=pd.DataFrame(policy);text+=['## 限同向参与的机会代价（主对照版本）',pol[(pol.stock==stock)&pol.bp.eq(5)&pol.id.isin(['Pall_N2_R1_L1','Pall_N2_R1_L2'])].to_markdown(index=False,floatfmt='.2f')]
    text+=['## 完整规则说明',
    'Pall（P全）：冻结U上升/R震荡/D下降/C修复阶段；U/D前日收盘位置<40%且今日低开至少1%；R截至昨日连跌至少3日且前日量比<0.8；C前日个股阴线、上证下跌、今日低开。PUR（P主）仅U/R。09:25知道开盘后09:35开始区间开价买1000，收盘卖1000可卖旧股；卖出失败保留待退出。',
    'N0/N2：前日20日收益≤−16.1565018%，今日收盘买1000；次日10:00截止，N0无止损，N2沿用原2%触发。所有触发按B12下一bar收价延迟；不是净亏2%封顶。',
    'R入口A：昨日收于顶部20%、量≤昨日之前20日均量、20日累计涨幅非负；否则B：昨日3日累计跌至少4%、收于顶部30%。今日收盘卖1000，A优先，模块每天最多1000。R1：A涨1%触发否则14:50；B低开0.5%后最早09:30，否则跌1%/涨2%/11:00。R05仅B等待改跌0.5%。Rsmall：A卖出日14:50未跌则明日预定开盘、已跌仍涨1%/14:50；B未跌等跌0.5%、已跌等跌1%，其余同R1。Rprofit仅将Rsmall的A未跌改明日固定14:50。未跌为14:50完成价≥当日preclose；全部买回阈值相对本笔卖出参考价。',
    'F全部参加；L1/L2分别每个加股/减股方向最多一/两笔未完成逻辑批次；退出不受政策限制。同刻同基准预知反向意图内部配对，余量真实成交。经纪账户遵守FIFO和T+1，只对真实订单收费。ID由上述规则名顺次拼接。',
    '## 证据边界',
    '完整矩阵、邻接对照、逐一剔除方向重算、归因桥、全年每日含零交易日净损益及共同亏损、前1/3/5日集中性、资金与双账位于本批远端目录。单笔胜率是逻辑分摊口径；账户人民币净增量与两种回撤为主。',
    '三成本是固定N主成本决策路径成本压力，不重新优化止损。全历史已经反复筛选，不能称独立样本外。5分钟区间开/收价和涨跌停代理不是排队成交保证，细数据覆盖与竞价未知见fine文件。日终回撤不是盘中最大浮亏；sampled_intraday_stress仅现有离散报价观测。',
    '3000股及K均为历史研究资源，不是用户真实持仓或未来最低保证。补款是本金，同流量持有对照收相同金额，不计收益。初始按首日收盘共同估值，与父口径一致。',
    '本报告只提交研究，不采用策略、不交易、不启动下一批。独立验证失败时本报告不得作为完成结论。']
    (R/'REPORT.md').write_text('\n\n'.join(text)+'\n')

if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true','Calculations stay on GitHub'
    R.mkdir(parents=True,exist_ok=True)
    try:
        if sys.argv[1]=='freeze':freeze()
        else:run()
    except Exception:js('failure.json',dict(run=os.environ.get('GITHUB_RUN_ID'),traceback=traceback.format_exc()));raise
