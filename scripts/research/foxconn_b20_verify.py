"""New process verifies all B20 saved accounts and combination decisions."""
import os,json,inspect,functools,traceback
from types import SimpleNamespace
import numpy as np
import pandas as pd
import foxconn_b20 as y
x=y.x;b=y.b;R=y.R
def run():
    frozen=json.loads((R/'frozen_input_hashes.json').read_text());manifest=json.loads((R/'manifest.json').read_text())
    for p,h in {**frozen['files'],**manifest['files']}.items():assert b.sha(p)==h,p
    d,f,masks,specs,paths,schedule=y.load();summary=pd.read_csv(R/'account_summary.csv')
    reg=json.loads((R/'registry.json').read_text())
    # Separate scalar verifier has independent fee and FIFO definitions; only accelerate loops.
    src=inspect.getsource(b.b17.verify)
    src=src.replace(' def rate(a,b):',' @functools.lru_cache(maxsize=None)\n def rate(a,b):')
    src=src.replace("for (_,r),(_,zr) in zip(d[d.date.ge('2020-01-01')].iterrows(),z.iterrows()):","for r,zr in zip(d[d.date.ge('2020-01-01')].itertuples(index=False),z.itertuples(index=False)):")
    src=src.replace(' cash=initialcash;holdcash=initialcash;',' indices=dict(zip(d.date,d.index))\n cash=initialcash;holdcash=initialcash;').replace("i=int(d.index[d.date.eq(day)][0])","i=indices[day]")
    src=src.replace('for _,x in dayorders.iterrows():','for x in dayorders.itertuples(index=False):')
    scope=dict(b.b17.__dict__);scope['functools']=functools;exec(src,scope)
    (R/'independent_verifier_runtime.py.txt').write_text(src)
    checks=[]
    for a in summary.itertuples():
        tag=f'{a.id}_{a.bp}'
        z=pd.read_csv(R/f'accounts/{tag}.csv.gz',parse_dates=['date']);o=pd.read_csv(R/f'orders/{tag}.csv.gz',parse_dates=['date','entry']);t=pd.read_csv(R/f'trades/{tag}.csv',parse_dates=['entry','exit'])
        scope['verify'](d,z,o,3000,a.bp/10000,0.,schedule)
        assert abs(z.relative.iloc[-1]-a.increment)<1e-5
        assert (t.cash_increment>0).sum()==a.trade_wins and t.exit_i.notna().sum()==a.completed
        assert not o[o.side.eq('SELL')].date.duplicated().any()
        # Independent resource reconstruction accounts for T+1 bought-today inventory.
        need=max([1000*(1+sum((t.entry_i<tr.entry_i)&(t.exit_i.isna()|t.exit_i.ge(tr.entry_i)))) for tr in t.itertuples()],default=0)
        assert need<=3000 and a.minimum_old_shares_unconstrained==need
        if a.bp!=5:
            ref=pd.read_csv(R/f'trades/{a.id}_5.csv',parse_dates=['entry','exit'])
            cols=['entry_i','exit_i','buy_ref','buy_clock','selected_rule','path']
            pd.testing.assert_frame_equal(t[cols],ref[cols])
        checks.append(dict(id=a.id,bp=a.bp,days=len(z),orders=len(o),minimum_old_shares=need,status='PASS'))
        if len(checks)%10==0:print('INDEPENDENT',len(checks),flush=True)
    y.save('independent_accounts_verified.csv',checks)
    # Every date's selection checked with scalar truth-table logic independent of selection().
    decision_checks=0
    for rule in reg:
        chosen,category=y.selection(rule,masks)
        for i in d.index:
            aa=bool(masks[rule['a']].iloc[i]) if rule['a'] and pd.notna(masks[rule['a']].iloc[i]) else False
            bb=bool(masks[rule['b']].iloc[i]) if rule['b'] and pd.notna(masks[rule['b']].iloc[i]) else False
            want=''
            if aa and bb:want=rule['a'] if rule['policy']=='A' else rule['b'] if rule['policy']=='B' else ''
            elif aa:want=rule['a']
            elif bb:want=rule['b']
            assert chosen.iloc[i]==want;decision_checks+=1
        t=pd.read_csv(R/f'trades/{rule["id"]}_5.csv')
        for tr in t.itertuples():
            assert tr.selected_rule==chosen.iloc[tr.entry_i]
            p=paths[tr.selected_rule].loc[tr.entry_i]
            assert tr.path==p.path and tr.buy_clock==p.buy_clock and abs(tr.buy_ref-p.buy_ref)<1e-8
    synthetic_tests()
    # Rebuild only the daily features actually used, then mutate future daily quotations.
    def daily_features(dd):
        chain=(dd.close/dd.preclose).cumprod()
        return pd.DataFrame({'S1_clv':((dd.close-dd.low)/(dd.high-dd.low).replace(0,np.nan)).shift(),'S1_vr':(dd.volume/dd.volume.shift().rolling(20).mean()).shift(),'S1_r3':(100*(chain/chain.shift(3)-1)).shift(),'S1_r20':(100*(chain/chain.shift(20)-1)).shift()})
    before=daily_features(d)
    for col in before:np.testing.assert_allclose(before[col],f[col],equal_nan=True,atol=1e-10)
    cutoff=pd.Timestamp('2024-01-01');dd=d.copy();future=dd.date.ge(cutoff)
    dd.loc[future,['open','high','low','close','preclose','volume']]*=1.71
    after=daily_features(dd);mm=y.masks_from_features(after)
    for rule in reg:
        c,_=y.selection(rule,masks);c2,_=y.selection(rule,mm)
        pd.testing.assert_series_equal(c[~future],c2[~future])
    # Parent prefix/clock tests remain evidence; repeat six actions against synthetic future changes.
    nmut=0
    rr=SimpleNamespace(open=100.,limit_down=90.,limit_up=110.)
    for key,spec in specs.items():
        bars={clock:dict(open=100.,close=100.,high=102.,low=98.) for clock in x.ENDS}
        bars['09:35']['close']=103.
        fill,_,_=x.first_buy(100.,rr,bars,spec)
        assert fill
        for clock,bar in bars.items():
            if clock>b.minutes_after(fill[0],5):
                bar.update(open=105.,close=105.,high=109.,low=91.)
        again,_,_=x.first_buy(100.,rr,bars,spec);assert fill==again;nmut+=1
    # Changing cash cannot change plan or economic increment.
    t=pd.read_csv(R/f'trades/{y.BASE}_5.csv',parse_dates=['entry','exit'])
    z,o,tt,ff,s=x.account(d,t,3000,.0005,schedule,initialcash=200000.)
    expected=summary[summary.id.eq(y.BASE)&summary.bp.eq(5)].iloc[0]
    assert abs(s['increment']-expected.increment)<1e-5
    # Explicit full-path equivalence for registered aliases, if any.
    aliases=pd.read_csv(R/'path_aliases.csv')
    for a in aliases.itertuples():
        if a.id==a.canonical:continue
        for bp in [5,11,20]:
            aa=summary[summary.id.eq(a.id)&summary.bp.eq(bp)].iloc[0];cc=summary[summary.id.eq(a.canonical)&summary.bp.eq(bp)].iloc[0]
            assert abs(aa.increment-cc.increment)<1e-5
    for p,h in {**frozen['files'],**manifest['files']}.items():assert b.sha(p)==h,p
    y.js('independent_validation.json',dict(status='PASS',accounts=len(checks),decision_truth_table_cases=decision_checks,future_path_mutations=nmut,parent_files=len(frozen['files']),checks=['all 90 saved ledgers independently fee/FIFO/dividend/cash/share reconciled','full 30-rule scalar decision truth table','same-day one sale and T+1 resources','all three priorities; failed A filter preserves B','multiple pending and cross-year attached entry paths','5/11/20bp decisions unchanged','future daily and post-fill bars cannot change earlier decisions','positive initial cash invariance','parent 24 baseline accounts aligned','frozen input and output hashes unchanged']))
    y.js('verification_manifest.json',dict(files={str(p):b.sha(p) for p in sorted(R.rglob('*')) if p.is_file() and str(p) not in manifest['files'] and p.name not in ['manifest.json','calculation.log','verification.log','verification_manifest.json','failure.json']}))
    print('VERIFICATION COMPLETE',len(checks),flush=True)
def synthetic_tests():
    masks={k:pd.Series([True,False,True,False],dtype='boolean') for k in y.KEYS}
    masks['H01']=pd.Series([True,True,False,False],dtype='boolean')
    masks['R121']=pd.Series([False,False,True,False],dtype='boolean')
    for policy,want in [('A',['H00','H01','H00','']),('B',['H01','H01','H00','']),('SKIP',['','H01','H00',''])]:
        got,_=y.selection(dict(a='H00',b='H01',policy=policy),masks);assert got.tolist()==want
    got,_=y.selection(dict(a='R121',b='H01',policy='SKIP'),masks);assert got.tolist()==['H01','H01','R121','']
    dates=pd.to_datetime(['2023-12-28','2023-12-29','2024-01-02','2024-01-03','2024-01-04'])
    d=pd.DataFrame(dict(date=dates,open=[100.]*5,high=[101.]*5,low=[99.]*5,close=[100.]*5,limit_down=[90.]*5,limit_up=[110.]*5,volume=[100.]*5,dividend_today=[0.]*5))
    p=pd.DataFrame([dict(entry_i=i,entry=dates[i],sell_ref=100.,exit_i=3,exit=dates[3],buy_ref=101.,buy_clock='09:30',kind='test',trigger='deadline',missing_windows=0,delayed=True,path='attached_'+str(i)) for i in range(4)]).set_index('entry_i',drop=False)
    mask=pd.Series([True]*5,dtype='boolean');t,need,reasons=x.plan(d,mask,p,capacity=3)
    assert list(t.entry_i)==[0,1,2] and need==3000
    assert reasons.iloc[3].reason=='inventory_participation'
    assert t.path.tolist()==['attached_0','attached_1','attached_2']
    z,o,tt,ff,s=x.account(d,t,3000,.0005,{})
    x.audit(d,z,o,tt,s);b.b17.verify(d,z,o,3000,.0005,0.,{})
    assert s['completed']==3 and s['deposits']>0
    # With one batch bought today, a different old lot permits a new sale.
    p2=p.copy();p2.loc[0,['exit_i','exit','path']]=[1,dates[1],'original_entry_rule']
    t2,need2,_=x.plan(d,pd.Series([True,True,False,False,False]),p2,capacity=3)
    assert list(t2.entry_i)==[0,1] and need2==2000 and t2.iloc[0].path=='original_entry_rule'
    rr=SimpleNamespace(open=99.,limit_down=90.,limit_up=110.)
    bars={c:dict(open=100.,close=100.,high=105.,low=95.) for c in x.ENDS}
    bars['09:35']['open']=99.2;spec=dict(kind='adaptive',gap=.005,tp=.005,stop=.01,deadline='10:30')
    fill,_,_=x.first_buy(100.,rr,bars,spec);assert fill[:2]==('09:30',99.2)
    rr.open=100.;bars['09:35']['close']=99.;bars['09:45']['open']=98.8
    fill,_,why=x.first_buy(100.,rr,bars,spec);assert fill[:2]==('09:40',98.8) and why=='target_close'
    bars['09:35']['close']=102.;fill,_,why=x.first_buy(100.,rr,bars,spec);assert fill[0]=='09:40' and why=='stop_close'
    assert x.delayed_start('11:25')=='13:00' and x.delayed_start('11:30')=='13:05'
    bars={c:dict(open=100.,close=100.,high=105.,low=95.) for c in x.ENDS};bars['10:25']['close']=102.
    fill,_,why=x.first_buy(100.,rr,bars,spec);assert fill[0]=='10:30' and why=='deadline'
    bars.pop('10:35');fill,_,why=x.first_buy(100.,rr,bars,spec);assert fill[0]=='14:50' and why=='emergency_1450'
    fill,_,why=x.first_buy(100.,rr,{},spec);assert fill is None
    sd=d.copy();sd.loc[2,'open']=110.;orig=b.first_buy;b.first_buy=x.first_buy
    sp=dict(kind='adaptive',gap=None,tp=None,stop=None,deadline='13:30',path='missing_test')
    pp,_=b.build_paths(sd,pd.DataFrame(columns=['date','clock','open','close']),sp)
    assert pp.loc[0,'exit_i']==3
    pending,_=b.build_paths(sd.iloc[:3],pd.DataFrame(columns=['date','clock','open','close']),sp)
    b.first_buy=orig;t=pending.loc[[0]].reset_index(drop=True)
    z,o,tt,ff,s=x.account(sd.iloc[:3],t,3000,.0005,{})
    assert s['pending']==1 and s['terminal_missing']==1000
    assert abs(s['increment']-(tt.sale_net.iloc[0]-1000*sd.close.iloc[2]))<1e-6
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:run()
    except Exception:
        y.js('failure.json',dict(run=os.environ.get('GITHUB_RUN_ID'),stage='independent_verification',traceback=traceback.format_exc()));raise
