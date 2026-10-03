"""B26 fixed exit experiment. All computation confined to GitHub Actions."""
import os,sys,json,hashlib,inspect,itertools,copy,subprocess,traceback
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
import numpy as np
import pandas as pd
import foxconn_b24 as c
R=Path('research/foxconn_t0_20261003_b26')
OLD=Path('research/foxconn_t0_20261003_b25')
PARENT='efb5e16ed8445f777a31c2ea493671474afdb0b9'
START=c.START
z=c.z
sha=c.sha
c.R=R
save=c.save
js=c.js
BASE='P0935_N2_R1_F'
ANCHORS=['Pall_N2_R1_F','Pall_N0_Rprofit_F','PUR_N0_Rprofit_F']
CLOSES=[v.strftime('%H:%M') for a,b in [('09:35','11:30'),('13:05','15:00')] for v in pd.date_range('2000-01-01 '+a,'2000-01-01 '+b,freq='5min')]
GRID={}
MODES=['P0935','P0945','P1005','PO0940','PO1000','PL0940','PL1000']
def registry():
    out=[]
    for p,pol in itertools.product(MODES,['F','L1']):
        out.append(dict(id=p+'_N2_R1_'+pol,P=p,N='N2',R='R1',policy=pol,anchor=False,parent='Pclose_N1000s2_'+pol if p=='P0935' else '',modules=3))
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
        if 'b26' not in p.name:files[str(p)]=sha(p)
    for p,h in old['files'].items():assert sha(p)==h,p
    subprocess.run(['git','diff','--exit-code',PARENT,'--',str(OLD)],check=True)
    reg=registry()
    if (R/'registry.json').exists():assert json.loads((R/'registry.json').read_text())==reg
    js('registry.json',reg);save('registry.csv',reg)
    js('frozen_input_hashes.json',dict(parent=PARENT,files=files,code={str(p):sha(p) for p in Path('scripts/research').glob('foxconn_b26*.py')},protocol=sha(R/'PROTOCOL.md'),task=sha(R/'TASK.md'),registry=sha(R/'registry.json')))
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
def features(bb,op,mode):
    target='09:35' if mode=='P0935' else '09:45' if mode in ['P0945','PO0940','PL0940'] else '10:05'
    obs='09:40' if target=='09:45' else '10:00' if target=='10:05' else '09:25'
    prev='09:35' if obs=='09:40' else '09:55'
    f=dict(mode=mode,observation=obs,target=target,O=str(op),C_t='',L_t='',V_t='',C_prev='',L_prev='',V_prev='',condition='not_required',confirm_reason='not_required')
    if not mode.startswith(('PO','PL')):return f
    a=bb.get(obs,{});b=bb.get(prev,{})
    f.update(C_t=str(a.get('close','')),L_t=str(a.get('low','')),V_t=str(a.get('volume','')))
    if mode.startswith('PL'):f.update(C_prev=str(b.get('close','')),L_prev=str(b.get('low','')),V_prev=str(b.get('volume','')))
    required=['C_t','V_t','O'] if mode.startswith('PO') else ['C_t','L_t','V_t','C_prev','L_prev','V_prev']
    if any(decimal_value(f[k]) is None for k in required):
        f.update(condition='unknown',confirm_reason='confirmation_data_unknown');return f
    good=Decimal(f['C_t'])>=Decimal(f['O']) if mode.startswith('PO') else Decimal(f['C_t'])>Decimal(f['C_prev']) and Decimal(f['L_t'])>=Decimal(f['L_prev'])
    f.update(condition='pass' if good else 'fail',confirm_reason='confirmed' if good else 'confirmation_false')
    return f
def load():
    d,m,bars,sched,plans=c.load()
    raw,opens=raw_inputs();features_rows=[];causal=[]
    originals=copy.deepcopy(plans['PUR'])
    for mode in MODES:
        out=[]
        for t in originals:
            dt=pd.Timestamp(t['entry']);bb=raw.get(dt,{});f=features(bb,opens.get(dt,''),mode)
            nt=copy.deepcopy(t);nt['variant']=mode
            if mode!='P0935':
                nt.update(entry_clock=f['target'],entry_basis='bar_open_'+f['target'].replace(':',''),entry_price=float(bars.get(dt,{}).get(c.b.minutes_after(f['target'],5),{}).get('open',np.nan)),known=f['observation'] if mode.startswith(('PO','PL')) else t['known'])
            nt.update(confirmation=f['condition'],confirmation_reason=f['confirm_reason'])
            if f['condition'] in ['fail','unknown']:nt['entry_block_reason']=f['confirm_reason']
            out.append(nt)
            q=f['target'];price=nt['entry_price'];row=d.loc[t['entry_i']]
            features_rows.append(dict(**f,tid=t['tid'],date=t['entry'],entry_i=t['entry_i'],stage=t['stage'],original_signal=True,original_price=t['entry_price'],entry_price=price,quote_state='quote_unknown' if not np.isfinite(price) or price<=0 else 'untradeable' if not c.valid(price,row,1) else 'quote_proxy_valid',intended_buy=f['condition'] not in ['fail','unknown']))
            trunc={k:v for k,v in bb.items() if k<=f['observation']}
            assert features(trunc,opens.get(dt,''),mode)==f
            future={k:({**v,'open':'9999','close':'0.01','high':'9999','low':'0.001','volume':'0'} if k>f['observation'] else v) for k,v in bb.items()}
            assert features(future,opens.get(dt,''),mode)==f
            # Entry quote can be observed at interval start; future volume/high/low/close never gates it.
            end=c.b.minutes_after(q,5);alter=copy.deepcopy(bb)
            if end in alter:alter[end].update(volume='0',high='9999',low='0.001',close='0.01')
            assert alter.get(end,{}).get('open')==bb.get(end,{}).get('open')
            causal.append(dict(mode=mode,tid=t['tid'],date=t['entry'],observation=f['observation'],status='PASS',entry_future_volume_not_used=True))
        plans[mode]=out
    # Only registered plans feed the common grid; the legacy load includes additional frozen aliases.
    used={v[k] for v in registry() for k in ['P','N','R']}
    plans={k:v for k,v in plans.items() if k in used}
    save('confirmation_features.csv',features_rows);save('path_causality.csv',causal)
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
    sub("                if reason:\n                    why[o['tid']]=reason","                if o['kind']=='entry' and o['plan'].get('entry_block_reason'):reason=o['plan']['entry_block_reason']\n                if reason:\n                    why[o['tid']]=reason")
    # Index the predeclared grid by date, preserving identical points for every account.
    sub("groups|={(clock,basis) for (dt,clock,basis) in GRID if dt==day}","groups|=GRID_DAYS.get(day,set())")
    ns=c.__dict__.copy();ns.update(GRID=GRID,GRID_DAYS={day:{(clock,basis) for dt,clock,basis in GRID if dt==day} for day in {k[0] for k in GRID}},sortkey=sortkey)
    exec(compile(source,'B26_shared_account_runtime','exec'),ns)
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
            if 'variant' in a and folder=='trades' and row.P=='P0935':a['variant']=a['variant'].replace({'P0935':'PUR'})
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
    entry_analysis(s,d)
    for p,h in frozen['files'].items():assert sha(p)==h,p
    js('calculation_validation.json',dict(status='PASS',accounts=len(s),rules=17,K=K,parents=len(frozen['files']),all_newly_computed=True))
def tests():
    bb={'09:35':dict(close='100',low='99',volume='1'),'09:40':dict(close='100',low='99',volume='1')}
    assert features(bb,'100','PO0940')['condition']=='pass'
    assert features(bb,'100','PL0940')['condition']=='fail'
    bb['09:40']['close']='100.01'
    assert features(bb,'100','PL0940')['condition']=='pass'
    bb['09:40']['low']='98.99'
    assert features(bb,'100','PL0940')['condition']=='fail'
    bb['09:40']['close']='99.99'
    assert features(bb,'100','PO0940')['condition']=='fail'
    assert features({'09:40':bb['09:40']},'100','PL0940')['condition']=='unknown'
    assert features({'09:40':dict(close='100',volume='1')},'100','PO0940')['condition']=='pass'
    assert features({},'100','PO0940')['condition']=='unknown'
    bb['09:40']['volume']='0';assert features(bb,'100','PO0940')['condition']=='unknown'
    c.tests()
    global GRID
    oldgrid=GRID
    dates=pd.to_datetime(['2025-12-31','2026-01-02','2026-01-05'])
    d=pd.DataFrame(dict(date=dates,open=[100.]*3,close=[100.]*3,limit_up=[110.]*3,limit_down=[90.]*3,volume=[100.]*3,dividend_today=[0.,1.,0.]))
    bars={dt:{k:dict(open=100.,close=100.,low=100.,high=100.,volume=100.) for k in CLOSES} for dt in dates}
    GRID={}
    for dt in dates:
        for cl,ba in [('09:25','daily_open'),('09:35','bar_open_0935'),('09:45','bar_open_0945'),('10:05','bar_open_1005'),('10:05','bar_close_1005'),('15:00','daily_close')]:
            GRID[(dt,cl,ba)]=dict(grid_id=len(GRID)+1,price=100.)
    fn=engine();rule=dict(id='synthetic',P='P0945',N='N2',R='-',policy='L1',modules=2)
    p=c.newplan('PUR',1,dates[1],100.,'09:45','bar_open_0945','09:40',1,'15:00',100.,'daily_close')
    n=c.newplan('N2',0,dates[0],100.,'15:00','daily_close','previous_close',1,'09:40',100.,'bar_close_0940')
    plans=dict(P0945=[p],N2=[n])
    met,a,t,ss=fn(d,bars,{dates[1]:1},plans,rule,3000,5)
    assert ss[ss.module.eq('P')].reason.iloc[0]=='accepted'
    bars[dates[1]]['09:40']['volume']=0
    met,a,t,ss=fn(d,bars,{dates[1]:1},plans,rule,3000,5)
    assert ss[ss.module.eq('P')].reason.iloc[0]=='policy_rejected'
    bars[dates[1]]['09:50']['volume']=0
    solo=dict(rule,N='-',policy='F')
    met,a,t,ss=fn(d,bars,{dates[1]:1},plans,solo,3000,5);assert met['completed']==1
    pp=dict(p,entry_price=np.nan)
    assert fn(d,bars,{},dict(P0945=[pp]),solo,3000,5)[3].reason.iloc[0]=='quote_unknown'
    for price in [110.,111.]:
        assert fn(d,bars,{},dict(P0945=[dict(p,entry_price=price)]),solo,3000,5)[3].reason.iloc[0]=='untradeable'
    for reason in ['confirmation_false','confirmation_data_unknown']:
        assert fn(d,bars,{},dict(P0945=[dict(pp,entry_block_reason=reason)]),solo,3000,5)[3].reason.iloc[0]==reason
    met,a,t,ss=fn(d,bars,{dates[1]:1},plans,solo,0,5)
    assert met['exit_failed']==1 and t.actual_exit_clock.iloc[0]=='09:25'
    dd=d.copy();dd.loc[1,'close']=90
    met,a,t,ss=fn(dd,bars,{},plans,solo,3000,5);assert met['exit_failed']==1 and t.actual_exit_i.iloc[0]==2
    met,a,t,ss=fn(dd.iloc[:2],bars,{},plans,solo,3000,5);assert met['pending']==1
    # Same clock different price bases: N close first releases slot; P open is a separate order.
    pp=dict(p,entry_clock='10:05',entry_basis='bar_open_1005',entry_price=101.)
    nn=dict(n,exit_clock='10:05',exit_basis='bar_close_1005')
    met,a,t,ss=fn(d,bars,{},dict(P0945=[pp],N2=[nn]),rule,3000,5)
    assert ss[ss.module.eq('P')].reason.iloc[0]=='accepted' and met['internal_pairs']==0
    GRID=oldgrid
    js('synthetic_validation.json',dict(status='PASS',cases=['C_equals_open_pass','C_equals_prev_fail','L_equals_prev_pass','one_cent_edges','missing_prev_unknown_only_for_two_bar_rule','missing_current_unknown','zero_observation_volume_unknown','target_missing_quote','target_future_volume_not_gate','limit_up_no_buy','successful_observation_failed_execution','confirmation_reason_precedes_execution_and_policy','L1_prior_exit_release','L1_failed_exit_keeps_slot','different_basis_no_net','new_shares_Tplus1_cross_year','close_failure_recovery','terminal_pending','inherited_dividend_FIFO_flow_tests']))
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
                for ref in dict.fromkeys([BASE,'P0935_N2_R1_'+r.policy]+([key[:-2]+'F'] if key.endswith('L1') else [])+([('P0945' if r.P.endswith('0940') else 'P1005')+'_N2_R1_'+r.policy] if r.P.startswith(('PO','PL')) else [])):
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
                    ref='P0935_N2_R1_'+r.policy
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
    for name,v in [('comparisons.csv',comparisons),('adjacent_rules.csv',adj),('periods.csv',periods),('concentration.csv',con),('key_dates.csv',dates),('policy_opportunity_cost.csv',policy),('exit_opportunity_cost.csv',exitbridge),('daily_correlations.csv',corr),('worst_daily_contributions.csv',worst),('pareto.csv',pareto),('B26_common_grid_bridge.csv',oldbridge)]:save(name,v)
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

def entry_analysis(s,d):
    feat=pd.read_csv(R/'confirmation_features.csv',keep_default_na=False)
    diag=[]; bridges=[]; filtered=[]; matched=[]; daily=[]; stage=[]; availability=[]; ris=[]
    for stock in sorted(s.stock.unique()):
      for bp in [5,11,20]:
        sub=s[s.stock.eq(stock)&s.bp.eq(bp)].set_index('id')
        for key,r in sub[~sub.anchor].iterrows():
            name=f'{key}_{stock}_{bp}'
            sig=read('signals',name);sig=sig[sig.module.eq('P')]
            f=feat[feat['mode'].eq(r.P)].copy()
            joined=f.merge(sig[['tid','reason']],on='tid',validate='one_to_one')
            assert len(joined)==len(f)
            joined['id']=key;joined['stock']=stock;joined['bp']=bp
            diag.extend(joined.to_dict('records'))
            ref='P0935_N2_R1_'+r.policy
            fixed=('P0945' if r.P.endswith('0940') else 'P1005')+'_N2_R1_'+r.policy if r.P.startswith(('PO','PL')) else key
            x=r.increment-sub.loc[ref,'increment'];fil=r.increment-sub.loc[fixed,'increment'];tim=sub.loc[fixed,'increment']-sub.loc[ref,'increment']
            assert abs(x-fil-tim)<1e-6
            bridges.append(dict(id=key,stock=stock,bp=bp,original=ref,fixed=fixed,total=x,confirmation_vs_same_time=fil,delay_vs_original=tim))
            current=read('trades',name);current=current[current.module.eq('P')].set_index('entry')
            old=read('trades',f'{ref}_{stock}_{bp}');old=old[old.module.eq('P')].set_index('entry')
            for dt in current.index.union(old.index):
                a=current.loc[dt] if dt in current.index else None;b=old.loc[dt] if dt in old.index else None
                both=a is not None and b is not None
                matched.append(dict(id=key,stock=stock,bp=bp,date=dt,reference=ref,category='matched' if both else 'added' if a is not None else 'removed',old_price=b.entry_price if b is not None else None,new_price=a.entry_price if a is not None else None,buy_price_cash_change=1000*(b.entry_price-a.entry_price) if both else 0,logical_change=(a.realized if a is not None and pd.notna(a.realized) else 0)-(b.realized if b is not None and pd.notna(b.realized) else 0)))
            if r.P.startswith(('PO','PL')):
                # Same-time fixed F allocation: condition false and unknown are separate diagnoses.
                fref=('P0945' if r.P.endswith('0940') else 'P1005')+'_N2_R1_F'
                ft=read('trades',f'{fref}_{stock}_{bp}');ft=ft[ft.module.eq('P')].set_index('entry')
                for rr in f.itertuples():
                    if rr.date not in ft.index:continue
                    tr=ft.loc[rr.date]
                    filtered.append(dict(id=key,stock=stock,bp=bp,reference=fref,date=rr.date,stage=rr.stage,condition=rr.condition,confirm_reason=rr.confirm_reason,fixed_logical_profit=tr.realized,avoided_loss=max(0,-tr.realized) if rr.condition=='fail' else 0,missed_profit=max(0,tr.realized) if rr.condition=='fail' else 0,unknown_excluded_profit=tr.realized if rr.condition=='unknown' else 0))
            refs=list(dict.fromkeys([ref,fixed,key[:-2]+'F' if key.endswith('L1') else key]))
            aa=read('accounts',name)
            for rf in refs:
                if rf==key:continue
                bb=read('accounts',f'{rf}_{stock}_{bp}')
                delta=(aa.relative-bb.relative).diff().fillna(aa.relative.iloc[0]-bb.relative.iloc[0])
                for ix in aa.index:
                    daily.append(dict(id=key,reference=rf,stock=stock,bp=bp,date=aa.date.iloc[ix],change=delta.iloc[ix],P=aa.P_pnl.iloc[ix]-bb.P_pnl.iloc[ix],N=aa.N_pnl.iloc[ix]-bb.N_pnl.iloc[ix],R=aa.R_pnl.iloc[ix]-bb.R_pnl.iloc[ix],adjust=aa.adjust_pnl.iloc[ix]-bb.adjust_pnl.iloc[ix]))
            for label,gg in current.groupby('stage'):
                stage.append(dict(id=key,stock=stock,bp=bp,stage=label,n=len(gg),profit=gg.realized.sum(),win=100*gg.realized.gt(0).mean(),worst=gg.realized.min(),note='descriptive_group_not_recombined_strategy'))
            basefeat=feat[feat['mode'].eq('P0935')].set_index('tid')
            for rr in f.itertuples():
                before=basefeat.loc[rr.tid]
                availability.append(dict(id=key,stock=stock,bp=bp,date=rr.date,original_quote=before.quote_state,new_quote=rr.quote_state,changed=before.quote_state!=rr.quote_state,condition=rr.condition))
        # Attribute every registered account's four peak/trough intervals.
        for key,r in sub.iterrows():
            for folder,curves in [('stress',['relative','absolute']),('accounts',['relative','absolute'])]:
                g=read(folder,f'{key}_{stock}_{bp}')
                for curve in curves:
                    vals=np.r_[0,g[curve].values];dds=np.maximum.accumulate(vals)-vals;j=int(np.argmax(dds));i=int(np.argmax(vals[:j+1]))
                    a=g.iloc[i-1] if i else None;b=g.iloc[j-1] if j else None
                    def label(row,k):
                        return 'initial0' if not k else str(row.date)+(' '+str(row.clock)+' '+str(row.basis) if folder=='stress' else ' close')
                    rr=dict(id=key,stock=stock,bp=bp,frequency='intraday' if folder=='stress' else 'close',curve=curve,peak=label(a,i),trough=label(b,j),drawdown=dds[j])
                    for col in ['P','N','R','adjust','hold_absolute']:rr[col]=(a[col] if i else 0)-(b[col] if j else 0)
                    assert abs(sum(rr[v] for v in ['P','N','R','adjust'])+(rr['hold_absolute'] if curve=='absolute' else 0)-dds[j])<1e-5
                    ris.append(rr)
    save('signal_decisions.csv',diag);save('confirmation_delay_bridge.csv',bridges);save('filtered_fixed_F_trades.csv',filtered);save('matched_entry_prices.csv',matched);save('daily_comparison.csv.gz',daily);save('stage_diagnostics.csv',stage);save('quote_availability_changes.csv',availability);save('risk_attribution.csv',ris)
    ff=pd.DataFrame(filtered)
    save('confirmation_opportunity_summary.csv',ff.groupby(['id','stock','bp','condition']).agg(n=('date','size'),fixed_profit=('fixed_logical_profit','sum'),avoided_loss=('avoided_loss','sum'),missed_profit=('missed_profit','sum'),unknown_excluded_profit=('unknown_excluded_profit','sum')).reset_index())
    mm=pd.DataFrame(matched);matchedonly=mm[mm.category.eq('matched')]
    save('matched_price_summary.csv',matchedonly.groupby(['id','stock','bp']).agg(n=('date','size'),price_cash=('buy_price_cash_change','sum'),cheaper=('buy_price_cash_change',lambda x:x.gt(0).sum()),dearer=('buy_price_cash_change',lambda x:x.lt(0).sum()),max_benefit=('buy_price_cash_change','max'),max_cost=('buy_price_cash_change','min'),logical_change=('logical_change','sum')).reset_index())
    dd=pd.DataFrame(daily);rows=[]
    for (key,ref,stock,bp),gg in dd.groupby(['id','reference','stock','bp']):
        x=gg.change
        rows.append(dict(id=key,reference=ref,stock=stock,bp=bp,delta=x.sum(),**{f'top{n}':x.nlargest(n).sum() for n in [1,3,5]},**{f'without{n}':x.sum()-x.nlargest(n).sum() for n in [1,3,5]}))
    save('all_comparison_concentration.csv',rows)

if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:
        if sys.argv[-1]=='freeze':freeze()
        else:run()
    except Exception:
        R.mkdir(parents=True,exist_ok=True);js('failure_'+os.environ.get('GITHUB_RUN_ID','unknown')+'.json',dict(traceback=traceback.format_exc()));raise
