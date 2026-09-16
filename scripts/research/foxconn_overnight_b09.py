#!/usr/bin/env python3
"""B09 frozen intraday-path hypotheses, close-to-next-open remains primary."""
import os,json,hashlib,zipfile
from pathlib import Path
import pandas as pd
import numpy as np
import foxconn_overnight_b08 as b8
R=Path('research/foxconn_overnight_20260916_b09');P8=Path('research/foxconn_overnight_20260916_b08')

def save(n,x):
    z=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x);z.to_csv(R/n,index=False);return z

def features(d,m,cutoff='14:50'):
    # Data calendar is reindexed before any historical rolling calculation.
    def align(s):return pd.Series(d.date.map(s).to_numpy(),index=d.index,dtype=float)
    def px(clock,col='close'):return align(m[m.clock.eq(clock)].set_index('date')[col])
    n=46 if cutoff=='14:50' else 45
    t=m[m.clock.le(cutoff)];count=align(t.groupby('date').size());valid=count.eq(n)
    past=m[m.clock.le('14:00')];late=m[m.clock.gt('14:00')&m.clock.le(cutoff)]
    p=px(cutoff);p1400=px('14:00');p1130=px('11:30');o=px('09:35','open')
    v=align(late.groupby('date').volume.sum())
    f=pd.DataFrame({'p':p,'tail':100*(p/p1400-1),'morning':100*(p1130/o-1),'afternoon':100*(p/p1130-1),'prior_high':align(past.groupby('date').high.max()),'prior_low':align(past.groupby('date').low.min()),'tail_volume':v})
    f.loc[~valid,:]=np.nan
    f['vr']=f.tail_volume/f.tail_volume.shift().rolling(20).mean()
    return f

def masks(f):
    def pred(test,cols):return test.astype('boolean').where(f[cols].notna().all(axis=1),pd.NA)
    return {'L1_tail_up':pred(f['tail']>0,['tail']),'L2_tail_down':pred(f['tail']<0,['tail']),
        'L3_afternoon_recovery':pred((f.morning<0)&(f.afternoon>0),['morning','afternoon']),
        'L4_afternoon_reversal':pred((f.morning>0)&(f.afternoon<0),['morning','afternoon']),
        'L5_breakout':pred(f.p>f.prior_high,['p','prior_high']),
        'L6_breakdown':pred(f.p<f.prior_low,['p','prior_low']),
        'L7_tail_up_volume':pred((f['tail']>0)&(f.vr>=1.5),['tail','vr']),
        'L8_tail_down_volume':pred((f['tail']<0)&(f.vr>=1.5),['tail','vr'])}

def changes(g,slip=.0005,exitcol='next_open',early=False,reverse=False):
    z=g.copy()
    if early:z['close']=z.early_entry
    z['cash'],z['net'],z['fee']=b8.pnl(z,slip=slip,exitcol=exitcol,reverse=reverse)
    z['gross']=100*((z.close-z[exitcol]-z.dividend*.8)/z.close if reverse else (z[exitcol]+z.dividend*.8)/z.close-1)
    return z

def gates(g):
    s=b8.brief(g)
    if len(g)<60:return False
    early=g[g.date.dt.year.le(2023)];recent=g[g.date.dt.year.ge(2024)]
    ci=b8.boot(g,pd.Series(True,index=g.index))
    return bool(len(early)>=20 and len(recent)>=20 and early.net.mean()>0 and recent.net.mean()>0 and s['mean']>0 and s['delete5']>0 and s['delete5_cash']>0 and (g.groupby(g.date.dt.year).net.mean()>0).sum()>=3 and ci['ci_low']>0 and changes(g,slip=.001).net.mean()>0)

def run():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    R.mkdir(parents=True,exist_ok=True);inputs={};parent=json.loads((P8/'manifest.json').read_text())
    for name in ['daily_ledger.csv','results.csv']:
        p=P8/name;h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==parent['files'][str(p)];inputs[str(p)]=h
    oldaudit=json.loads((P8/'audit.json').read_text())
    for p,h in oldaudit['input_hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h;inputs[p]=h
    d=pd.read_csv(P8/'daily_ledger.csv',parse_dates=['date','exit_date'])
    assert len(d)==2007 and d.date.max()==pd.Timestamp('2026-09-11')
    np.testing.assert_allclose(b8.pnl(d)[0],d.cash,atol=1e-8,equal_nan=True)
    b8.old.tests()
    with zipfile.ZipFile(b8.P/'source/601138-full-5min-history.zip') as z:m=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('601138_5min_all.csv'))))
    m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
    assert not m.duplicated(['date','clock']).any()
    f=features(d,m);r=masks(f);lag=masks(features(d,m,'14:45'))
    for cut in [900,1600]:
        mm=m.copy();mm['volume']=mm.volume.astype(float)
        select=(mm.date>d.date.iloc[cut])|((mm.date==d.date.iloc[cut])&mm.clock.gt('14:50'))
        mm.loc[select,['open','high','low','close','volume']]*=1.3
        pd.testing.assert_frame_equal(features(d,mm).iloc[:cut+1],f.iloc[:cut+1])
        pd.testing.assert_frame_equal(features(d.iloc[:cut+1],m[m.date<=d.date.iloc[cut]]),f.iloc[:cut+1])
        # Daily final prices are deliberately irrelevant to the intraday-path input.
        dd=d.copy();dd.loc[cut:,['close','high','low','open']]*=2
        pd.testing.assert_series_equal(features(dd,m).iloc[cut],f.iloc[cut])
    d['p1450']=f.p
    d['early_entry']=d.date.map(m[m.clock.eq('14:55')].set_index('date').open)
    full=d.next_open.notna();main=full&d.date.ge('2020-01-01')
    assert abs(d.loc[main,'net'].mean()-(-.3291354026252871))<1e-10
    wins={'main2020':main,'old2020_2023':main&d.date.dt.year.le(2023),'recent2024':full&d.date.dt.year.ge(2024),'all':full}
    wins.update({str(y):full&d.date.dt.year.eq(y) for y in range(2018,2027)})
    allm={'ON0_common':f.p.notna().astype('boolean'),**r}
    results=[];coverage=[];stress=[];path=[];mirrors=[];trades=[];overlaps=[];stage=[]
    for name,mask in allm.items():
        hit=mask.fillna(False).astype(bool);known=mask.notna() if name!='ON0_common' else f.p.notna()
        for win,wm in wins.items():
            u=d[wm&known];h=hit.loc[u.index];g=u[h]
            ci=b8.boot(u,h) if win in ['main2020','old2020_2023','recent2024'] else {}
            results.append(dict(id=name,window=win,**b8.brief(g),**ci))
            coverage.append(dict(id=name,window=win,total=int(wm.sum()),known=int((wm&known).sum()),unknown=int((wm&~known).sum()),hit=len(g),not_hit=int((~h).sum()),universe_mean=float(u.net.mean()) if len(u) else None,nonhit_mean=float(u.loc[~h,'net'].mean()) if (~h).any() else None))
            assert len(g)+int((~h).sum())+int((wm&~known).sum())==int(wm.sum())
            if win in ['main2020','old2020_2023','recent2024']:
                x=g[g.p1450.notna()]
                late=np.log(x.close/x.p1450);night=np.log((x.next_open+x.dividend*.8)/x.close)
                np.testing.assert_allclose(late+night,np.log((x.next_open+x.dividend*.8)/x.p1450),atol=1e-12)
                path.append(dict(id=name,window=win,n=len(x),late_log_mean=float(100*late.mean()),overnight_log_mean=float(100*night.mean()),combined_log_mean=float(100*(late+night).mean()),late_price_mean=float((100*(x.close/x.p1450-1)).mean())))
                for slip in [0,.001,.002]:stress.append(dict(id=name,window=win,kind='slip',value=10000*slip,**b8.brief(changes(g,slip=slip))))
                for col in ['exit0935close','exit0935open']:
                    x=g[g[col].notna()];stress.append(dict(id=name,window=win,kind=col,value=0,excluded=len(g)-len(x),matched_primary=float(x.net.mean()) if len(x) else None,**b8.brief(changes(x,exitcol=col))))
                x=g[g.early_entry.notna()]
                stress.append(dict(id=name,window=win,kind='early_entry_DIAGNOSTIC',value=1450,excluded=len(g)-len(x),matched_primary=float(x.net.mean()) if len(x) else None,**b8.brief(changes(x,early=True))))
                stress.append(dict(id=name,window=win,kind='no_dividend',value=0,**b8.brief(g[~g.event])))
                if len(g) and g.net.mean()<0:mirrors.append(dict(id=name,window=win,**b8.brief(changes(g,reverse=True))))
            if win=='main2020':
                for ph in ['U','R','D','C','UNKNOWN']:stage.append(dict(id=name,stage=ph,**b8.brief(g[g.stage==ph])))
        z=d[main&hit].copy();z['id']=name;trades.append(z)
        if name in lag:stress.append(dict(id=name,window='main2020',kind='signal1445',value=1445,**b8.brief(d[main&lag[name].fillna(False)])))
    for a in r:
        for b in r:
            if a<b:overlaps.append(dict(a=a,b=b,shared=int((main&r[a].fillna(False)&r[b].fillna(False)).sum())))
    stats=save('results.csv',results);st=save('stress.csv',stress);save('coverage.csv',coverage);save('path_attribution.csv',path);save('mirror_registry.csv',mirrors);save('overlap.csv',overlaps);save('stage_descriptive.csv',stage);save('trades.csv',pd.concat(trades));save('features.csv',pd.concat([d[['date']],f],axis=1));save('signals.csv',pd.DataFrame({'date':d.date,**r}))
    # Adjust all 8 mean + 8 incremental tests together. No result-dependent extra combinations.
    rows=stats[stats.window.eq('main2020')&stats.id.ne('ON0_common')];tests=[]
    for _,row in rows.iterrows():
        for col in ['p_mean','p_inc']:tests.append((row.id,col,row[col]))
    tests.sort(key=lambda x:x[2]);adj={};prev=0
    for i,(name,col,p) in enumerate(tests):prev=max(prev,min(1,p*(len(tests)-i)));adj[name,col]=prev
    gs=[]
    for name,mask in r.items():
        g=d[main&mask.fillna(False)];row=rows[rows.id.eq(name)].iloc[0]
        delays=st[st.id.eq(name)&st.window.eq('main2020')&st.kind.str.startswith('exit0935')]
        passed=gates(g) and adj[name,'p_mean']<.05 and adj[name,'p_inc']<.05 and row.inc_low>0 and delays['mean'].gt(0).all()
        gs.append(dict(id=name,passed=bool(passed),holm_mean=adj[name,'p_mean'],holm_increment=adj[name,'p_inc'],execution_certified=False))
    gate=save('gates.csv',gs)
    # Retrospective annual selector uses only trades with exit BEFORE training cutoff.
    wf=[];train=[]
    for year in range(2022,2027):
        options=[]
        for name,mask in r.items():
            g=d[main&d.exit_date.lt(pd.Timestamp(year,1,1))&mask.fillna(False)];b=b8.brief(g)
            passed=len(g)>=60 and b.get('delete5',-1)>0 and b.get('delete5_cash',-1)>0 and (g.groupby(g.date.dt.year).net.mean()>0).sum()>=3
            train.append(dict(year=year,id=name,eligible=bool(passed),last_exit=g.exit_date.max(),**b))
            if passed:options.append((b['delete5'],len(g),name))
        chosen=sorted(options,key=lambda x:(-x[0],-x[1],x[2]))[0][2] if options else 'NONE'
        hit=r[chosen].fillna(False) if chosen!='NONE' else pd.Series(False,index=d.index)
        wf.append(dict(year=year,id=chosen,**b8.brief(d[main&d.date.dt.year.eq(year)&hit])))
    save('walkforward.csv',wf);save('walkforward_training.csv',train)
    # Matched predecessor tests isolate whether new path information improves on old broad conditions.
    oldfeatures=pd.read_csv(P8/'features.csv');prior=json.loads((P8/'manifest.json').read_text())
    assert hashlib.sha256((P8/'features.csv').read_bytes()).hexdigest()==prior['files'][str(P8/'features.csv')]
    inputs[str(P8/'features.csv')]=prior['files'][str(P8/'features.csv')]
    assert pd.to_datetime(oldfeatures.date).equals(d.date)
    common=main&f.p.notna()
    diagnostics=[]
    for label,mask in [('B08_strong',oldfeatures.ON2_clv.ge(.8)),('B08_weak',oldfeatures.ON2_clv.le(.2))]:diagnostics.append(dict(id=label,**b8.brief(d[common&mask])))
    save('old_conditions_common.csv',diagnostics)
    # Fixed1000 account scenarios kept separate from unlimited-opportunity cash sums.
    accounts=[]
    for name,mask in r.items():
        z,tr,summary=b8.account(d,mask.fillna(False));save('account_'+name+'.csv',z);save('account_trades_'+name+'.csv',tr);accounts.append(dict(id=name,**summary))
    save('accounts.csv',accounts)
    audit=dict(data_end=str(d.date.max().date()),minute_days=int(m.date.nunique()),signal_dates=int(f.p.notna().sum()),valid_tail_volume=int(f.vr.notna().sum()),input_hashes=inputs,rule_count=len(r),passed=gate.loc[gate.passed,'id'].tolist(),checks='B08 cash reproduction,source hashes,future-minute/daily-close mutation,prefix,coverage partition,log path identity,temporal training cutoff passed',limitations='Same previously explored history,not clean OOS. No auction queue certification,dividend vendor/settlement limitations inherited. Early-entry diagnostic is a different strategy,not automatic replacement. Frozen stages descriptive only.')
    (R/'audit.json').write_text(json.dumps(audit,indent=2))
    report=['# B09 Intraday paths and overnight follow-through','All signals at14:50; primary buy close,sell next open. No adaptive threshold tuning.',stats[stats.window.isin(['main2020','old2020_2023','recent2024'])][['id','window','n','mean','win','cash','delete5','ci_low','ci_high','increment']].to_markdown(index=False,floatfmt='.4f'),'## Path decomposition',pd.DataFrame(path).to_markdown(index=False,floatfmt='.4f'),'## Gates',gate.to_markdown(index=False),'## Annual selection',pd.DataFrame(wf).to_markdown(index=False),'## Audit',json.dumps(audit,indent=2)]
    (R/'REPORT.md').write_text('\n\n'.join(report))
    manifest=dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],spec_sha256=hashlib.sha256(Path('DOCS/FOXCONN_OVERNIGHT_B09.md').read_bytes()).hexdigest(),files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.iterdir() if p.is_file() and p.name!='manifest.json'})
    (R/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(audit))
if __name__=='__main__':run()
