"""B27 fixed exit experiment. All computation confined to GitHub Actions."""
import os,sys,json,hashlib,inspect,itertools,copy,subprocess,traceback
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
import numpy as np
import pandas as pd
import foxconn_b24 as c
R=Path('research/foxconn_t0_20261003_b27')
OLD=Path('research/foxconn_t0_20261003_b26')
PARENT='7160be728e0a0848b5e12899f056def1c0de0eba'
START=c.START
z=c.z
sha=c.sha
c.R=R
save=c.save
js=c.js
BASE='Pclose_N2_R1_F'
ANCHORS=['Pall_N2_R1_F','Pall_N0_Rprofit_F','PUR_N0_Rprofit_F']
CLOSES=[v.strftime('%H:%M') for a,b in [('09:35','11:30'),('13:05','15:00')] for v in pd.date_range('2000-01-01 '+a,'2000-01-01 '+b,freq='5min')]
GRID={}
SPECS={'Pclose':(None,None),'PT1':('0.01',None),'PT2':('0.02',None),'PF105':('0.01','0.005'),'PF110':('0.01','0.01'),'PF205':('0.02','0.005'),'PF210':('0.02','0.01')}
def registry():
    out=[]
    for p,pol in itertools.product(SPECS,['F','L1']):
        out.append(dict(id=p+'_N2_R1_'+pol,P=p,N='N2',R='R1',policy=pol,anchor=False,parent='P0935_N2_R1_'+pol if p=='Pclose' else '',modules=3))
    for key in ANCHORS:
        p,n,r,pol=key.split('_');out.append(dict(id=key,P=p,N=n,R=r,policy=pol,anchor=True,parent=key,modules=3))
    assert len(out)==17
    return out
def freeze():
    R.mkdir(parents=True,exist_ok=True)
    old=json.loads((OLD/'frozen_input_hashes.json').read_text());files=dict(old['files'])
    for p in OLD.rglob('*'):
        if p.is_file():files[str(p)]=sha(p)
    for p in Path('scripts/research').glob('foxconn*.py'):
        if 'b27' not in p.name:files[str(p)]=sha(p)
    for p,h in old['files'].items():assert sha(p)==h,p
    subprocess.run(['git','diff','--exit-code',PARENT,'--',str(OLD)],check=True)
    reg=registry()
    if (R/'registry.json').exists():assert json.loads((R/'registry.json').read_text())==reg
    js('registry.json',reg);save('registry.csv',reg)
    js('frozen_input_hashes.json',dict(parent=PARENT,files=files,code={str(p):sha(p) for p in Path('scripts/research').glob('foxconn_b27*.py')},protocol=sha(R/'PROTOCOL.md'),task=sha(R/'TASK.md'),registry=sha(R/'registry.json')))
def raw_inputs():
    import zipfile
    with zipfile.ZipFile(c.b.old.P/'source/601138-full-5min-history.zip') as zz:
        f=pd.read_csv(zz.open(next(n for n in zz.namelist() if n.endswith('601138_5min_all.csv'))),dtype=str,keep_default_na=False)
    f['date']=pd.to_datetime(f.date);f['clock']=pd.to_datetime(f.time.str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M')
    assert not f.duplicated(['date','clock']).any()
    bars={dt:g.set_index('clock').to_dict('index') for dt,g in f.groupby('date')}
    daily=pd.read_csv(c.b.old.P/'results/daily_features_and_cashflows.csv',dtype=str,keep_default_na=False)
    opens=dict(zip(pd.to_datetime(daily.date),daily.open))
    return bars,opens
def decimal_value(v):
    try:
        x=Decimal(str(v))
        return x if x.is_finite() and x>0 else None
    except Exception:return None

def pdecision(t,bb,mode,trace=None):
    gain,pull=SPECS[mode];entry=decimal_value(t.get('entry_price_decimal',t['entry_price']))
    result=dict(observation=None,reason='original_close' if gain is None else 'no_trigger_close',armed=None,peak=None,threshold=None,observed=0,unknown=0)
    if gain is None:return result
    if entry is None:result['reason']='entry_unknown';return result
    line=entry*(Decimal(1)+Decimal(gain));peak=None
    for clock in CLOSES:
        if not '09:40'<=clock<='14:50':continue
        bar=bb.get(clock,{});px=decimal_value(bar.get('close'));vol=decimal_value(bar.get('volume'))
        if px is None or vol is None:
            result['unknown']+=1
            if trace is not None:trace.append(dict(clock=clock,state='observation_unknown',close=str(bar.get('close','')),volume=str(bar.get('volume',''))))
            continue
        result['observed']+=1
        fire=False
        if pull is None:
            threshold=line;fire=px>=line
        else:
            if peak is None and px>=line:result['armed']=clock;peak=px
            if peak is not None:peak=max(peak,px)
            threshold=peak*(Decimal(1)-Decimal(pull)) if peak is not None else None
            fire=threshold is not None and px<=threshold
        result.update(peak=str(peak) if peak is not None else None,threshold=str(threshold) if threshold is not None else None)
        if trace is not None:trace.append(dict(clock=clock,state='trigger' if fire else 'armed' if result['armed'] else 'waiting',close=str(px),volume=str(vol),arming_line=str(line),peak=result['peak'],threshold=result['threshold']))
        if fire:result.update(observation=clock,reason='fixed_profit' if pull is None else 'armed_pullback');return result
    return result
def pplan(t,bb,mode):
    t=copy.deepcopy(t)
    if mode=='Pclose':return t
    t['variant']=mode;dec=pdecision(t,bb,mode);obs=dec['observation']
    t.update(observation_clock=obs,trigger=dec['reason'],armed_clock=dec['armed'])
    attempts=[]
    if obs:
        for clock in CLOSES:
            if obs<clock<='14:55':
                value=decimal_value(bb.get(clock,{}).get('close'))
                attempts.append(dict(clock=clock,basis='bar_close_'+clock.replace(':',''),price=float(value) if value else np.nan))
    attempts.append(dict(clock='15:00',basis='daily_close',price=t['exit_price']))
    t.update(exit_attempts=attempts,new_P_exit=True)
    return t
def load():
    d,m,bars,sched,plans=c.load();raw,_=raw_inputs();decisions=[];causal=[];trace=[]
    for mode in SPECS:
        pp=[]
        for orig in plans['PUR']:
            t=copy.deepcopy(orig);dt=pd.Timestamp(t['entry']);bb=raw.get(dt,{})
            if mode!='Pclose':t['entry_price_decimal']=bb.get('09:40',{}).get('open','')
            else:t.update(confirmation='not_required',confirmation_reason='not_required')
            rows=[];dec=pdecision(t,bb,mode,rows);nt=pplan(t,bb,mode);pp.append(nt)
            decisions.append(dict(mode=mode,tid=t['tid'],date=t['entry'],entry_price=str(t.get('entry_price_decimal',t['entry_price'])),**dec))
            trace.extend(dict(mode=mode,tid=t['tid'],date=t['entry'],**r) for r in rows)
            cut=dec['observation'] or '14:50'
            assert pdecision(t,{k:v for k,v in bb.items() if k<=cut},mode)==dec
            future={k:({**v,'close':'99999','low':'0.01','high':'99999','volume':'0'} if k>cut else v) for k,v in bb.items()}
            assert pdecision(t,future,mode)==dec
            # No high/low path ordering assumption: signal must ignore all bar high/low.
            altered={k:{**v,'high':'99999','low':'0.001'} for k,v in bb.items()}
            assert pdecision(t,altered,mode)==dec
            causal.append(dict(mode=mode,tid=t['tid'],date=t['entry'],cut=cut,status='PASS'))
        plans[mode]=pp
    used={v[k] for v in registry() for k in ['P','N','R']};plans={k:v for k,v in plans.items() if k in used}
    save('exit_decisions.csv',decisions);save('decision_trace.csv.gz',trace);save('path_causality.csv',causal)
    for k,v in plans.items():save('plans/'+k+'.csv',v)
    return d,m,bars,sched,plans
def sortkey(v):
    clock,basis=v
    return (clock,0 if basis.startswith('bar_close_') else 1 if basis=='daily_open' else 3 if basis=='daily_close' else 2,basis)
def make_grid(d,bars,plans):
    global GRID
    need=defaultdict(set)
    for vv in plans.values():
        for t in vv:
            i=t['entry_i'];need[i].add((t['entry_clock'],t['entry_basis']))
            if t.get('exit_i') is not None:need[t['exit_i']].add((t['exit_clock'],t['exit_basis']))
            for a in t.get('exit_attempts',[]):need[i].add((a['clock'],a['basis']))
    rows=[];missing=[];gid=0;GRID={}
    for i in d.index[d.date.ge(START)]:
        row=d.loc[i];day=row.date;bb=bars.get(day,{})
        want=need[i]|{('09:25','daily_open'),('15:00','daily_close')}|{(k,'bar_close_'+k.replace(':','')) for k in CLOSES}
        for clock,basis in sorted(want,key=sortkey):
            if basis=='daily_open':p=row.open;valid=np.isfinite(p) and p>0
            elif basis=='daily_close':p=row.close;valid=np.isfinite(p) and p>0
            elif basis.startswith('bar_close_'):
                b=bb.get(clock,{});p=b.get('close',np.nan);valid=np.isfinite(p) and p>0 and b.get('volume',0)>0
            else:
                # End-labelled bar beginning at clock, respecting afternoon session.
                end=c.b.minutes_after(clock,5);b=bb.get(end,{});p=b.get('open',np.nan);valid=np.isfinite(p) and p>0
            if not valid:
                missing.append(dict(date=day,clock=clock,basis=basis,reason='missing_or_invalid_completed_quote'));continue
            gid+=1;g=dict(grid_id=gid,date=day,clock=clock,basis=basis,price=float(p),timing='after_same_basis_orders; bar_close before following bar_open; gross dividend entitlement preopen; payment before15:00')
            GRID[(day,clock,basis)]=g;rows.append(g)
    save('common_grid.csv.gz',rows);save('grid_missing.csv',missing)
    js('grid_coverage.json',dict(days=len(d[d.date.ge(START)]),points=len(rows),days_with_minutes=sum(bool(bars.get(day)) for day in d.loc[d.date.ge(START),'date']),missing_points=len(missing),no_forward_fill=True))
    return GRID
def engine():
    source=inspect.getsource(c.simulate)
    (R/'inherited_account_runtime.py.txt').write_text(source)
    def sub(a,b):
        nonlocal source
        assert a in source,a[:90]
        source=source.replace(a,b)
    sub("    for i in range(start,len(d)):","""    gridcache={}\n    def gridmark(day,clock,basis,price):
        g=GRID.get((day,clock,basis))
        if g is None:return
        price=g['price'];eq,he=mark(day,price);res=reserve(day)
        key=(day,len(events))\n        if gridcache.get('key')!=key:\n            gridcache.update(key=key,values={v:sum(t['cash']+t['dividend'] for t in trades.values() if t['module']==v) for v in 'PNR'},positions={v:sum(t['direction'] for t in pending.values() if t['module']==v) for v in 'PNR'})\n        mods={v:gridcache['values'][v]+1000*price*gridcache['positions'][v] for v in 'PNR'}
        assert abs(sum(mods.values())-res-(eq-he))<1e-5
        stress.append(dict(grid_id=g['grid_id'],date=day,clock=clock,basis=basis,price=price,cash=cash,hold_cash=hc,shares=qty(),receivable=sum(v for _,v in recv),hold_receivable=sum(v for _,v in hr),tax_reserve=res,external=external,equity=eq,hold_equity=he,relative=eq-he,absolute=eq-initial-external,hold_absolute=he-initial-external,adjust=-res,**mods))
    for i in range(start,len(d)):""")
    sub("        if intraday:groups|={(c,'mark_close') for c in bars.get(day,{})}","""        groups|={(clock,basis) for (dt,clock,basis) in GRID if dt==day}
        groups|={(a['clock'],a['basis']) for t in newby[i] for a in t.get('exit_attempts',[])}""")
    sub("sorted(groups,key=lambda v:(v[0],0 if v[1].startswith('bar_close') else 1 if v[1]=='mark_close' else 2))","sorted(groups,key=sortkey)")
    sub("if t['module']=='P' and t['entry_i']==i]","if t['module']=='P' and t['entry_i']==i and not t.get('new_P_exit')]")
    sub("            news=[intent", """            for t in list(pending.values()):
                if t.get('new_P_exit') and t['entry_i']==i:
                    for at in t['exit_attempts']:
                        if (at['clock'],at['basis'])==(clock,basis):
                            exits.append(intent(t,'exit',at['price'],clock,basis,t.get('observation_clock') or '09:35'))
            news=[intent""")
    sub("            if not accepted:continue","            if not accepted:\n                gridmark(day,clock,basis,0)\n                continue")
    sub("            stress.append(dict(date=day,clock=clock,basis=basis,relative=eq-he,absolute=eq-initial-external,hold_absolute=he-initial-external))","            gridmark(day,clock,basis,price)")
    # Index the predeclared grid by date, preserving identical points for every account.
    sub("groups|={(clock,basis) for (dt,clock,basis) in GRID if dt==day}","groups|=GRID_DAYS.get(day,set())")
    ns=c.__dict__.copy();ns.update(GRID=GRID,GRID_DAYS={day:{(clock,basis) for dt,clock,basis in GRID if dt==day} for day in {k[0] for k in GRID}},sortkey=sortkey)
    exec(compile(source,'B27_shared_account_runtime','exec'),ns)
    (R/'shared_account_runtime.py.txt').write_text(source)
    return ns['simulate']
def read(folder,name,root=R):
    try:return pd.read_csv(root/f'{folder}/{name}.csv.gz')
    except pd.errors.EmptyDataError:return pd.DataFrame()
def aligned(current,parent,label):
    common=list(parent.columns)
    pd.testing.assert_frame_equal(current[common].reset_index(drop=True),parent.reset_index(drop=True),check_dtype=False,atol=1e-5,rtol=1e-10,obj=label)
def validate_parents(s):
    checks=[]
    for row in s[s.stock.eq(3000)&s.parent.fillna('').ne('')].itertuples():
        name=f'{row.id}_{row.stock}_{row.bp}';old=f'{row.parent}_{row.stock}_{row.bp}'
        for folder in ['accounts','orders','events','trades','signals','pairs','disposals','lots','funds']:
            a=read(folder,name);b=read(folder,old,OLD)
            if not len(a) and not len(b):continue
            if folder=='trades' and row.P=='Pclose' and 'variant' in b:b['variant']=b['variant'].replace({'P0935':'PUR'})
            aligned(a,b,folder+name)
        checks.append(dict(id=row.id,parent=row.parent,bp=row.bp,days=len(read('accounts',name)),status='PASS',scope='daily and all net orders/logical attribution/lots'))
    assert len(checks)==15
    save('parent_daily_alignment.csv',checks)
def extremes(g,col):
    arr=np.r_[0,g[col].to_numpy()];peak=np.maximum.accumulate(arr);j=int(np.argmax(peak-arr));prior=arr[:j+1];i=int(np.argmax(prior))
    def at(k):return 'initial0' if k==0 else str(g.date.iloc[k-1])+' '+str(g.clock.iloc[k-1])+' '+str(g.basis.iloc[k-1])
    return dict(value=float(peak[j]-arr[j]),peak=at(i),trough=at(j))
def run():
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in {**frozen['files'],**frozen['code']}.items():assert sha(p)==h,p
    d,m,bars,sched,plans=load();make_grid(d,bars,plans);sim=engine();tests()
    # Measure common resource before ranking, for all registered policies.
    need=[];K=3000
    for rule in registry():
        k=3000
        while True:
            met,_,_,_=sim(d,bars,sched,plans,rule,k,5)
            if met['inventory_rejected']==0 and met['inventory_exit_failed']==0:break
            k+=1000;assert k<=100000
        K=max(K,k);need.append(dict(id=rule['id'],diagnostic_stock=k,minimum_historical_old_shares=k-met['min_old_available']))
    save('resource_diagnostic.csv',need);js('resource_lock.json',dict(K=K,before_rankings=True))
    rows=[];peaks=[]
    for stock in sorted({3000,K}):
        for rule in registry():
            for bp in [5,11,20]:
                met,_,_,_=sim(d,bars,sched,plans,rule,stock,bp,True)
                name=f"{rule['id']}_{stock}_{bp}";g=read('stress',name)
                assert list(g.grid_id)==list(pd.read_csv(R/'common_grid.csv.gz').grid_id)
                for col in ['relative','absolute','hold_absolute']:
                    ex=extremes(g,col);peaks.append(dict(id=rule['id'],stock=stock,bp=bp,curve=col,**ex))
                met['intraday_relative_mdd']=c.ddmetric(g.relative);met['intraday_absolute_mdd']=c.ddmetric(g.absolute);met['intraday_hold_mdd']=c.ddmetric(g.hold_absolute);met['grid_points']=len(g)
                rows.append(met);print('CALCULATED',name,met['increment'],flush=True)
    s=save('account_summary.csv',rows);validate_parents(s)
    save('intraday_peaks.csv',peaks)
    analyze(s,d)
    for p,h in frozen['files'].items():assert sha(p)==h,p
    js('calculation_validation.json',dict(status='PASS',accounts=len(s),rules=17,K=K,parents=len(frozen['files']),all_newly_computed=True))
def tests():
    t=dict(entry_price=100.,entry_price_decimal='100',exit_price=103.,entry_i=0,tid='PUR_0',entry='2026-01-05',module='P',direction=1)
    def bar(v,vol=1):return dict(close=str(v),volume=str(vol),open=str(v),high='9999',low='0.01')
    assert pdecision(t,{'09:35':bar(999),'09:40':bar('101')},'PT1')['observation']=='09:40'
    assert pdecision(t,{'09:40':bar('100.999999')},'PT1')['observation'] is None
    assert pdecision(t,{'09:40':bar('101',0)},'PT1')['observation'] is None
    assert pdecision(t,{'09:40':bar('100.8'),'09:45':bar('99')},'PF105')['observation'] is None
    bb={'09:40':bar('101'),'09:45':bar('100.495')}
    assert pdecision(t,bb,'PF105')['observation']=='09:45'
    bb['09:45']=bar('100.495001');assert pdecision(t,bb,'PF105')['observation'] is None
    bb={'09:40':bar('101'),'09:45':bar('102'),'09:50':bar('101.49')}
    assert pdecision(t,bb,'PF105')['observation']=='09:50'
    assert pdecision(t,{'14:55':bar(102)},'PT1')['observation'] is None
    assert pplan(t,{'14:50':bar(101)},'PT1')['exit_attempts'][0]['clock']=='14:55'
    assert pplan(t,{'11:30':bar(101)},'PT1')['exit_attempts'][0]['clock']=='13:05'
    assert np.isnan(pplan(t,{'09:40':bar(101)},'PT1')['exit_attempts'][0]['price'])
    c.tests()
    global GRID
    oldgrid=GRID;dates=pd.to_datetime(['2025-12-31','2026-01-02','2026-01-05'])
    d=pd.DataFrame(dict(date=dates,open=[100.]*3,close=[100.]*3,limit_up=[110.]*3,limit_down=[90.]*3,volume=[100.]*3,dividend_today=[0.,1.,0.]))
    bars={dt:{k:dict(open=100.,close=100.,low=100.,high=100.,volume=100.) for k in CLOSES} for dt in dates}
    GRID={}
    for dt in dates:
        for cl,ba in [('09:25','daily_open'),('09:35','bar_open_0935'),('15:00','daily_close')]+[(k,'bar_close_'+k.replace(':','')) for k in CLOSES]:
            GRID[(dt,cl,ba)]=dict(grid_id=len(GRID)+1,price=100.)
    fn=engine();p=c.newplan('PUR',0,dates[0],100.,'09:35','bar_open_0935','09:25',0,'15:00',100.,'daily_close')
    bars[dates[0]]['09:40']['close']=101.;bars[dates[0]]['09:45']['volume']=0;bars[dates[0]]['09:50']['close']=99.
    pt=pplan(p,bars[dates[0]],'PT1')
    rule=dict(id='synthetic',P='PT1',N='-',R='-',policy='F',modules=1)
    met,a,tr,sg=fn(d,bars,{},dict(PT1=[pt]),rule,1000,5)
    assert tr.actual_exit_clock.iloc[0]=='09:50' and met['exit_failed']==1
    met,a,tr,sg=fn(d,bars,{},dict(PT1=[pt]),rule,0,5)
    assert tr.actual_exit_clock.iloc[0]=='09:25' and tr.actual_exit_i.iloc[0]==1
    met,a,tr,sg=fn(d.iloc[:1],bars,{},dict(PT1=[pt]),rule,0,5);assert met['pending']==1
    # Triggered exit stays latched after failed quote, and limit-down retry reaches next valid bar.
    bars[dates[0]]['09:45'].update(volume=100.,close=90.)
    pt=pplan(p,bars[dates[0]],'PT1');met,a,tr,sg=fn(d,bars,{},dict(PT1=[pt]),rule,1000,5)
    assert tr.actual_exit_clock.iloc[0]=='09:50'
    GRID=oldgrid
    js('synthetic_validation.json',dict(status='PASS',cases=['exact_profit_threshold','strict_below_not_trigger','ignore_preentry_bar','zero_volume_unknown','unarmed_pullback_ignored','exact_pullback_equal','strict_above_pullback_no_trigger','running_completed_close_peak','high_low_ignored','last_trigger1450_target1455','lunch_next_complete_bar','missing_target_keep_intent','failed_target_retry_latched','limit_down_retry','same_day_newshares_Tplus1_crossyear','terminal_pending','inherited_netting_FIFO_dividend_L1_flow_tests']))
METRICS=['increment','relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd','deposits','max_shares','win','worst','worst5','longest_loss','recovery_days','avg_profit','avg_loss']
def analyze(s,d):
    comparisons=[];adj=[];periods=[];con=[];dates=[];policy=[];exitbridge=[];corr=[];worst=[];pareto=[];oldbridge=[];opposite=[]
    for stock in sorted(s.stock.unique()):
        for bp in [5,11,20]:
            sub=s[s.stock.eq(stock)&s.bp.eq(bp)].set_index('id')
            curves={k:read('accounts',f'{k}_{stock}_{bp}') for k in sub.index}
            trades={k:read('trades',f'{k}_{stock}_{bp}') for k in sub.index}
            for t in trades.values():t['key']=t.module+'_'+t.entry.astype(str)
            for key,r in sub.iterrows():
                for ref in dict.fromkeys([BASE,'Pclose_N2_R1_L1']+([key[:-2]+'F'] if key.endswith('L1') else [])):
                    rr=sub.loc[ref];row=dict(id=key,reference=ref,stock=stock,bp=bp,**{v:r[v]-rr[v] for v in METRICS})
                    for v in ['reference_cash','slippage','fee','tax','terminal_reserve','dividend_relative','pending_mark']:row[v+'_change']=r[v]-rr[v]
                    bridge=row['reference_cash_change']-row['slippage_change']-row['fee_change']-row['tax_change']-row['terminal_reserve_change']+row['dividend_relative_change']+row['pending_mark_change']
                    assert abs(bridge-row['increment'])<1e-5
                    comparisons.append(row)
                a=curves[key];a.date=pd.to_datetime(a.date)
                day=a.relative.diff().fillna(a.relative.iloc[0])
                whole=a.absolute.diff().fillna(a.absolute.iloc[0])
                intr=read('stress',f'{key}_{stock}_{bp}');intr.date=pd.to_datetime(intr.date)
                for title,mask in [(str(y),a.date.dt.year.eq(y)) for y in range(2022,2027)]+[('2022-2023',a.date.dt.year.le(2023))]:
                    g=a[mask];ip=intr[intr.date.isin(g.date)]
                    periods.append(dict(id=key,stock=stock,bp=bp,period=title,increment=day[mask].sum(),absolute_profit=whole[mask].sum(),relative_mdd=c.ddmetric(np.cumsum(day[mask])),absolute_mdd=c.ddmetric(np.cumsum(whole[mask])),intraday_relative_mdd=c.ddmetric(ip.relative-(a.relative.iloc[g.index[0]-1] if g.index[0]>0 else 0)),intraday_absolute_mdd=c.ddmetric(ip.absolute-(a.absolute.iloc[g.index[0]-1] if g.index[0]>0 else 0))))
                delta=day-curves[BASE].relative.diff().fillna(curves[BASE].relative.iloc[0])
                con.append(dict(id=key,stock=stock,bp=bp,delta=delta.sum(),**{f'top{n}':delta.nlargest(n).sum() for n in [1,3,5]},**{f'without{n}':delta.sum()-delta.nlargest(n).sum() for n in [1,3,5]}))
                for ix in set(delta.nlargest(5).index)|set(delta.nsmallest(5).index):
                    dates.append(dict(id=key,stock=stock,bp=bp,date=a.date.loc[ix],change=delta.loc[ix]))
                if key.endswith('L1'):
                    ref=key[:-2]+'F';tt=trades[ref];kept=set(trades[key].key)
                    removed=tt[~tt.key.isin(kept)]
                    cost=sub.loc[key,'increment']-sub.loc[ref,'increment']
                    policy.append(dict(id=key,reference=ref,stock=stock,bp=bp,removed=len(removed),avoided_loss=-removed.realized.clip(upper=0).sum(),missed_profit=removed.realized.clip(lower=0).sum(),actual_change=cost,interaction=cost+removed.realized.sum()))
                if not r.anchor:
                    ref='Pclose_N2_R1_'+r.policy
                    old=trades[ref].set_index('key');cur=trades[key].set_index('key')
                    for tid in old.index.union(cur.index):
                        before=old.loc[tid] if tid in old.index else None;after=cur.loc[tid] if tid in cur.index else None
                        category='matched' if before is not None and after is not None else 'added' if before is None else 'removed'
                        val=(after.realized if after is not None else 0)-(before.realized if before is not None else 0)
                        exitbridge.append(dict(id=key,reference=ref,stock=stock,bp=bp,key=tid,module=tid[0],date=after.entry if after is not None else before.entry,category=category,old_exit=before.actual_exit_clock if before is not None else None,new_exit=after.actual_exit_clock if after is not None else None,delta=val,avoided_or_added_profit=max(0,val),missed_or_added_loss=max(0,-val)))
                if bp==5:
                    for v,w in [('P','N'),('P','R'),('N','R')]:corr.append(dict(id=key,stock=stock,module1=v,module2=w,correlation=a[v+'_pnl'].corr(a[w+'_pnl']),both_negative=int((a[v+'_pnl'].lt(0)&a[w+'_pnl'].lt(0)).sum())))
                    for ix in day.nsmallest(5).index:worst.append(dict(id=key,stock=stock,date=a.date.loc[ix],relative_day=day.loc[ix],absolute_day=whole.loc[ix],**{v:a.loc[ix,v+'_pnl'] for v in 'PNR'},adjust=a.loc[ix,'adjust_pnl']))
                axes=['relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd','deposits','max_shares']
                dominates=(sub.increment>=r.increment-1e-7)
                strict=(sub.increment>r.increment+1e-7)
                for v in axes:dominates&=sub[v]<=r[v]+1e-7;strict|=sub[v]<r[v]-1e-7
                pareto.append(dict(id=key,stock=stock,bp=bp,pareto=not bool((dominates&strict).any())))
            core=sub[~sub.anchor]
            for k,r in core.iterrows():
                for j,q in core.iterrows():
                    if k>=j:continue
                    changed=[v for v in ['P','N','policy'] if r[v]!=q[v]]
                    if len(changed)==1:adj.append(dict(id=k,reference=j,dimension=changed[0],stock=stock,bp=bp,**{v:r[v]-q[v] for v in METRICS}))
            for k in ANCHORS:
                old=c.read if hasattr(c,'read') else None
                oo=pd.read_csv(OLD/'account_summary.csv');o=oo[oo.id.eq(k)&oo.stock.eq(3000)&oo.bp.eq(bp)].iloc[0]
                oldbridge.append(dict(id=k,stock=stock,bp=bp,old_observed_relative=o.intraday_relative_mdd,new_common_relative=sub.loc[k,'intraday_relative_mdd'],old_observed_absolute=o.intraday_absolute_mdd,new_common_absolute=sub.loc[k,'intraday_absolute_mdd']))
    for name,v in [('comparisons.csv',comparisons),('adjacent_rules.csv',adj),('periods.csv',periods),('concentration.csv',con),('key_dates.csv',dates),('policy_opportunity_cost.csv',policy),('exit_opportunity_cost.csv',exitbridge),('daily_correlations.csv',corr),('worst_daily_contributions.csv',worst),('pareto.csv',pareto),('parent_common_grid_bridge.csv',oldbridge)]:save(name,v)
    main=s[s.stock.eq(3000)&s.bp.eq(5)].set_index('id');pf=pd.DataFrame(pareto);front=main.loc[pf[pf.stock.eq(3000)&pf.bp.eq(5)&pf.pareto].id]
    champ=main.sort_values(['increment','id'],ascending=[False,True]).index[0]
    b=main.loc[BASE];pool=front[(front.intraday_relative_mdd<b.intraday_relative_mdd-1e-7)&(front.intraday_absolute_mdd<b.intraday_absolute_mdd-1e-7)]
    risk=pool.sort_values('increment',ascending=False).index[0] if len(pool) else None
    simple=BASE
    js('focus.json',dict(profit=champ,risk=risk,simple=simple,rule='profit among fixed17 incl anchors; highest-profit Pareto member improving both intraday drawdowns vs specified baseline; unchanged baseline is simplicity reference, not automatically nondominated'))
    # Record negative module/year regions with independently charged reverse opportunity cash, no new account candidates.
    for r in s[s.stock.eq(3000)&s.bp.eq(5)&~s.anchor].itertuples():
        t=read('trades',r.id+'_3000_5');ev=read('events',r.id+'_3000_5');fills=ev[ev.reason.eq('filled')]
        ee=fills[fills.kind.eq('exit')].set_index('tid')
        t['year']=pd.to_datetime(t.entry).dt.year
        for (mod,year),g in t.groupby(['module','year']):
            if g.realized.mean()>=0:continue
            cash=[]
            for tr in g.itertuples():
                if tr.tid not in ee.index:continue
                x=ee.loc[tr.tid];dt=pd.Timestamp(tr.entry);xd=pd.Timestamp(tr.actual_exit)
                if tr.direction==1:
                    sell=1000*tr.entry_price*.9995;buy=1000*x.reference*1.0005
                    val=sell-buy-c.b.old.sf(sell,dt,True)-c.b.old.sf(buy,xd,False)-tr.dividend
                else:
                    buy=1000*tr.entry_price*1.0005;sell=1000*x.reference*.9995
                    val=sell-buy-c.b.old.sf(sell,xd,True)-c.b.old.sf(buy,dt,False)-tr.dividend
                cash.append(val)
            opposite.append(dict(id=r.id,module=mod,year=year,n=len(g),original=g.realized.sum(),reverse_opportunity_cash=sum(cash),status='diagnostic_only_not_FIFO_account_or_executable_short',overlap='same_dates_repeat_across_fixed_rules'))
    save('opposite_direction_regions.csv',opposite)
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:
        if sys.argv[-1]=='freeze':freeze()
        else:run()
    except Exception:
        R.mkdir(parents=True,exist_ok=True);js('failure_'+os.environ.get('GITHUB_RUN_ID','unknown')+'.json',dict(traceback=traceback.format_exc()));raise
