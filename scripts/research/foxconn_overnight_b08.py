#!/usr/bin/env python3
"""Predeclared overnight study. All market computation is restricted to GitHub Actions."""
import os,json,hashlib,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_t0_audit as old
R=Path('research/foxconn_overnight_20260916_b08')
P=Path('research/foxconn_t0_20260913')
B2=Path('research/foxconn_t0_20260913_b02')
DIV={'2019-06-20':.129,'2020-06-30':.2,'2021-07-27':.25,'2022-08-05':.5,'2023-07-28':.55,'2024-08-15':.58,'2025-07-31':.64,'2026-01-16':.33,'2026-08-03':.65}
SOURCE='https://money.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/601138.phtml'
def save(n,x):
    t=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)
    t.to_csv(R/n,index=False);return t

def fees(value,date,sell=False,current=False):
    trans=np.where(pd.to_datetime(date)<pd.Timestamp('2022-04-29'),.00002,.00001) if not current else .00001
    stamp=np.where(pd.to_datetime(date)<pd.Timestamp('2023-08-28'),.001,.0005) if not current else .0005
    return np.maximum(value*.0001354,5)+value*trans+(value*stamp if sell else 0)

def pnl(d,slip=.0005,q=1000,exitcol='next_open',tax=.2,current=False,reverse=False):
    if reverse:
        sv=q*d.close*(1-slip);bv=q*d[exitcol]*(1+slip)
        cost=fees(sv,d.date,True,current)+fees(bv,d.exit_date,False,current)
        cash=sv-bv-cost-q*d.dividend*(1-tax)
        return cash,100*cash/(q*d.close),cost
    bv=q*d.close*(1+slip);sv=q*d[exitcol]*(1-slip)
    bc=fees(bv,d.date,False,current);cost=bc+fees(sv,d.exit_date,True,current)
    cash=sv-bv-cost+q*d.dividend*(1-tax)
    return cash,100*cash/(bv+bc),cost

def brief(g):
    if not len(g):return {'n':0}
    x=g.net.to_numpy();cash=g.cash.to_numpy();cum=np.r_[0,cash.cumsum()]
    loses=x<=0;run=best=0
    for v in loses:run=run+1 if v else 0;best=max(best,run)
    pf=lambda z:float(z[z>0].sum()/-z[z<0].sum()) if (z<0).any() else None
    return dict(n=len(g),mean=float(x.mean()),median=float(np.median(x)),win=float(100*(x>0).mean()),cash=float(cash.sum()),pf=pf(x),pf_cash=pf(cash),worst=float(x.min()),tail5=float(np.sort(x)[:max(1,int(np.ceil(len(x)*.05)))].mean()),mdd_cash=float((cum-np.maximum.accumulate(cum)).min()),max_loss_run=best,months=int(g.date.dt.to_period('M').nunique()),years=int(g.date.dt.year.nunique()),clusters=int(g.ordinal.diff().gt(5).sum()+1),fee=float(g.fee.sum()),gross=float(g.gross.mean()),delete1=float(np.sort(x)[:-1].mean()) if len(x)>1 else None,delete5=float(np.sort(x)[:-5].mean()) if len(x)>5 else None,delete10=float(np.sort(x)[:-10].mean()) if len(x)>10 else None,delete5_cash=float(np.sort(cash)[:-5].sum()) if len(x)>5 else None)

def boot(g,mask):
    if mask.sum()<2:return dict(ci_low=np.nan,ci_high=np.nan,increment=np.nan,inc_low=np.nan,inc_high=np.nan,p_mean=1.,p_inc=1.)
    z=pd.DataFrame({'m':g.date.dt.to_period('M'),'s':g.net.where(mask,0),'n':mask.astype(int),'all':g.net,'count':1}).groupby('m')[['s','n','all','count']].sum().to_numpy()
    rng=np.random.default_rng(601138);tot=z[rng.integers(0,len(z),(2000,len(z)))].sum(axis=1);tot=tot[tot[:,1]>0]
    means=tot[:,0]/tot[:,1];inc=means-tot[:,2]/tot[:,3]
    obs=float(g.loc[mask,'net'].mean());delta=obs-float(g.net.mean())
    ci=np.quantile(means,[.025,.975]);di=np.quantile(inc,[.025,.975])
    return dict(ci_low=ci[0],ci_high=ci[1],increment=delta,inc_low=di[0],inc_high=di[1],p_mean=(1+np.sum(means-obs>=obs))/(len(means)+1),p_inc=(1+np.sum(inc-delta>=delta))/(len(inc)+1))

def rules(f,clow=.2,chigh=.8,r=4,vl=.8,vh=1.5):
    vals={'F1':('clv',lambda x:x>=chigh),'F2':('clv',lambda x:x<=clow),'F3':('r3',lambda x:x<=-r),'F4':('r3',lambda x:x>=r),'F5':('vr',lambda x:x<=vl),'F6':('vr',lambda x:x>=vh),'F7':('relative',lambda x:x>0),'F8':('gapdays',lambda x:x>=3)}
    return {k:fn(f[c]).astype('boolean').where(f[c].notna(),pd.NA) for k,(c,fn) in vals.items()}

def prior_features(d,ix):
    f=pd.DataFrame({'clv':(d.close-d.low)/(d.high-d.low).replace(0,np.nan),'r3':100*d.signal_close.pct_change(3),'vr':d.volume/d.volume.shift().rolling(20).mean(),'relative':d.signal_close.pct_change()-ix.pct_change()}).shift()
    f['gapdays']=(d.exit_date-d.date).dt.days.astype(float)
    return f

def tail_features(d,m,clock):
    t=m[m.clock.le(clock)]
    a=t.groupby('date').agg(p=('close','last'),h=('high','max'),l=('low','min'),v=('volume','sum'),bars=('clock','size'))
    # Reindex to the daily calendar before rolling: missing days must not become earlier observations.
    a=a.reindex(pd.DatetimeIndex(d.date));a.index=d.index
    expected=46 if clock=='14:50' else 45
    a.loc[a.bars.ne(expected),['p','h','l','v']]=np.nan
    f=pd.DataFrame({'clv':(a.p-a.l)/(a.h-a.l).replace(0,np.nan),'r3':100*(a.p*(d.signal_close/d.close)/d.signal_close.shift(3)-1),'vr':a.v/a.v.shift().rolling(20).mean(),'relative':np.nan,'gapdays':(d.exit_date-d.date).dt.days.astype(float)})
    return f,a

def checks(d,ix,m,f1,f2):
    old.tests()
    for cut in [900,1600]:
        a=d.copy();a['volume']=a.volume.astype(float);a.loc[cut:,'volume']*=1.8
        a.loc[cut:,['open','close','high','low','signal_close']]*=1.3
        pd.testing.assert_series_equal(prior_features(a,ix).iloc[cut],f1.iloc[cut])
        pd.testing.assert_frame_equal(prior_features(d.iloc[:cut+1],ix.iloc[:cut+1]),f1.iloc[:cut+1])
        # Mutating future bars must not alter current or previous tail features.
        mm=m.copy();mm.loc[(mm.date>d.date.iloc[cut])|((mm.date==d.date.iloc[cut])&mm.clock.gt('14:50')),['open','close','high','low','volume']]*=2
        ff,_=tail_features(d,mm,'14:50');pd.testing.assert_frame_equal(ff.iloc[:cut+1],f2.iloc[:cut+1])
        ff,_=tail_features(d.iloc[:cut+1],m[m.date<=d.date.iloc[cut]],'14:50');pd.testing.assert_frame_equal(ff,f2.iloc[:cut+1])
    good=d.next_open.notna()
    np.testing.assert_allclose((d.next_open/d.close*d.next_close/d.next_open)[good],(d.next_close/d.close)[good])
    assert fees(1000,pd.Timestamp('2026-01-01'))==5.01
    assert fees(1000,pd.Timestamp('2023-08-25'),True)>fees(1000,pd.Timestamp('2023-08-28'),True)
    # Zero-return hypothetical round-trip costs cannot generate profit.
    toy=d.iloc[:2].copy();toy['next_open']=toy.close;toy['dividend']=0
    assert (pnl(toy)[0]<0).all()
    assert (pnl(d)[0]+pnl(d,reverse=True)[0]).dropna().lt(0).all()

def account(d,mask,q=1000):
    # Conservative single-position account: reject limit-up buy, defer limit-down open sale.
    start=d.loc[d.date.ge('2020-01-01')].index[0];capital=q*d.loc[start,'close']*1.1
    cash=capital;held=0;entry=None;costbasis=0;rows=[];tr=[];skips=0
    for i in range(start,len(d)):
        r=d.loc[i]
        if held:
            cash+=held*r.dividend_today*.8 # ex-date receivable valued as cash scenario, not confirmed settlement
            if r.open>r.preclose*.901 and r.volume>0:
                v=held*r.open*.9995;fee=fees(v,r.date,True);cash+=v-fee
                tr.append(dict(entry=entry,exit=r.date,net=cash-costbasis,quantity=held))
                held=0
        open_equity=cash+held*r.open
        if bool(mask.iloc[i]) and not held and i<len(d)-1:
            v=q*r.close*1.0005;fee=fees(v,r.date)
            if r.close>=r.preclose*1.099 or r.volume<=0 or cash<v+fee:skips+=1
            else:costbasis=cash;cash-=v+fee;held=q;entry=r.date
        assert cash>=-1e-7 and held in [0,q]
        rows.append(dict(date=r.date,cash=cash,shares=held,open_equity=open_equity,equity=cash+held*r.close))
    z=pd.DataFrame(rows);eq=np.r_[capital,z[['open_equity','equity']].to_numpy().ravel()];dd=eq/np.maximum.accumulate(eq)-1
    return z,tr,dict(initial=capital,final=float(eq[-1]),return_pct=float(100*(eq[-1]/capital-1)),mdd_pct=float(100*dd.min()),skipped=skips,completed=len(tr),open_shares=held)

def run():
    assert os.environ.get('GITHUB_ACTIONS')=='true','No local market computation'
    R.mkdir(parents=True,exist_ok=True);inputs={}
    for root,names,key in [(P,['results/daily_features_and_cashflows.csv','source/601138-full-5min-history.zip'],'sha256'),(B2,['source/sse_index.csv'],'files')]:
        manifest=json.loads((root/'manifest.json').read_text())
        for n in names:
            p=root/n;h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==manifest[key][str(p)];inputs[str(p)]=h
    d=pd.read_csv(P/'results/daily_features_and_cashflows.csv',parse_dates=['date']).sort_values('date').reset_index(drop=True)
    assert len(d)==2007 and str(d.date.max().date())=='2026-09-11' and not d.date.duplicated().any()
    d['exit_date']=d.date.shift(-1);d['next_open']=d.open.shift(-1);d['next_close']=d.close.shift(-1)
    d['dividend_today']=d.date.dt.strftime('%Y-%m-%d').map(DIV).fillna(0);d['dividend']=d.dividend_today.shift(-1).fillna(0)
    assert set(d.loc[d.action_ratio.sub(1).abs().gt(.0001),'date'].dt.strftime('%Y-%m-%d'))==set(DIV)
    cal=pd.read_csv('data/601138_intraday/pytdxdata_1min/daily_trade_calendar.csv',parse_dates=['date']).date
    assert set(cal)==set(d.date),'Calendar disagreement; do not skip suspended dates'
    events=d[d.dividend_today.gt(0)][['date','preclose','dividend_today']].copy();events['previous_close']=d.close.shift().loc[events.index];events['reference_difference']=events.previous_close-events.preclose;events['vendor_dividend_gap']=events.reference_difference-events.dividend_today
    save('corporate_actions.csv',events)
    with zipfile.ZipFile(P/'source/601138-full-5min-history.zip') as z:m=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('601138_5min_all.csv'))))
    m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
    assert not m.duplicated(['date','clock']).any()
    ma=m.groupby('date').agg(first=('open','first'),last=('close','last'),h=('high','max'),l=('low','min'),bars=('clock','size'),v=('volume','sum'))
    good=(d.date.map(ma['first'])-d.open).abs().le(.011)&(d.date.map(ma['last'])-d.close).abs().le(.011)&d.date.map(ma.bars).eq(48)
    # Use completed 09:30-09:35 bar close and next bar open as two indicative delayed exits.
    for name,clock,field in [('exit0935close','09:35','close'),('exit0935open','09:40','open')]:
        px=d.date.map(m[m.clock.eq(clock)].set_index('date')[field]).where(good);d[name]=px.shift(-1)
    ix=d.date.map(pd.read_csv(B2/'source/sse_index.csv',parse_dates=['date']).set_index('date').close)
    f1=prior_features(d,ix);f2,tail=tail_features(d,m,'14:50');lag,_=tail_features(d,m,'14:45')
    checks(d,ix,m,f1,f2)
    features=pd.concat([d[['date']],f1.add_prefix('ON1_'),f2.add_prefix('ON2_')],axis=1);save('features.csv',features)
    # Tail quality flags are for audit/execution comparisons only; do not drop rows by future close mismatch in signal construction.
    save('minute_audit.csv',pd.DataFrame({'date':d.date,'good_full_day':good,'tail_bars':tail.bars,'tail_price':tail.p,'daily_close':d.close,'exit0935close':d.exit0935close,'exit0935open':d.exit0935open}))
    d['cash'],d['net'],d['fee']=pnl(d);d['gross']=100*((d.next_open+d.dividend*.8)/d.close-1)
    d['price_only']=100*(d.next_open/d.close-1);d['event']=d.dividend.gt(0)
    d['calendar_days']=(d.exit_date-d.date).dt.days.astype(float)
    masks={'ON0':pd.Series(True,index=d.index,dtype='boolean')}
    for ver,f in [('ON1',f1),('ON2',f2)]:
        for k,v in rules(f).items():
            if ver=='ON2' and k=='F8':continue # alias of ON1_F8
            masks[ver+'_'+k]=v
    full=d.next_open.notna()&d.close.gt(0)&d.next_open.gt(0)
    wins={'all':full,'main2020':full&d.date.ge('2020-01-01'),'old2020_2023':full&d.date.between('2020-01-01','2023-12-31'),'recent2024':full&d.date.ge('2024-01-01')}
    wins.update({str(y):full&d.date.dt.year.eq(y) for y in range(2018,2027)})
    results=[];coverage=[];mirror=[];stress=[];alltr=[]
    for name,mask in masks.items():
        valid=mask.notna();hit=mask.fillna(False).astype(bool)
        for win,wm in wins.items():
            universe=wm&valid;g=d[universe];selected=hit[universe]
            met=brief(g[selected]);ci=boot(g,selected) if win in ['main2020','recent2024','old2020_2023'] else {}
            row=dict(id=name,window=win,**met,**ci);results.append(row)
            coverage.append(dict(id=name,window=win,universe=int(wm.sum()),unknown=int((wm&~valid).sum()),hit=int((wm&hit).sum()),not_hit=int((universe&~hit).sum()),base_mean=float(g.net.mean()) if len(g) else None,nonhit_mean=float(g.loc[~selected,'net'].mean()) if (~selected).any() else None))
            assert int((universe&hit).sum()+(universe&~hit).sum()+(wm&~valid).sum())==int(wm.sum())
            if len(g[selected]) and met['mean']<0:
                x=g[selected].copy();x['cash'],x['net'],x['fee']=pnl(x,reverse=True);mirror.append(dict(id=name,window=win,**brief(x)))
        chosen=d[full&hit].copy();chosen['id']=name;alltr.append(chosen)
        for slip in [0,.0005,.001,.002]:
            for win in ['main2020','old2020_2023','recent2024']:
                g=d[wins[win]&hit].copy();g['cash'],g['net'],g['fee']=pnl(g,slip=slip);stress.append(dict(id=name,window=win,kind='slip',value=slip*10000,**brief(g)))
        for exitcol in ['exit0935close','exit0935open']:
            for win in ['main2020','old2020_2023','recent2024']:
                g=d[wins[win]&hit&d[exitcol].notna()].copy();base=brief(g);g['cash'],g['net'],g['fee']=pnl(g,exitcol=exitcol)
                stress.append(dict(id=name,window=win,kind=exitcol,value=0,matched_base_mean=base.get('mean'),matched_base_cash=base.get('cash'),excluded=int((wins[win]&hit&d[exitcol].isna()).sum()),**brief(g)))
        for kind,vals in [('dividend_tax',[0,.1,.2]),('shares',[100,500,1000]),('current_fees',[1])]:
            for v in vals:
                g=d[wins['main2020']&hit].copy();kw={'tax':v} if kind=='dividend_tax' else {'q':v} if kind=='shares' else {'current':True}
                g['cash'],g['net'],g['fee']=pnl(g,**kw);stress.append(dict(id=name,window='main2020',kind=kind,value=v,**brief(g)))
        for subset in ['event','non_event']:
            g=d[wins['main2020']&hit&(d.event if subset=='event' else ~d.event)];stress.append(dict(id=name,window='main2020',kind=subset,value=0,**brief(g)))
    stats=save('results.csv',results);save('coverage.csv',coverage);st=save('stress.csv',stress);save('mirror_registry.csv',mirror)
    save('trades.csv',pd.concat(alltr));save('daily_ledger.csv',d)
    # All primary mean and increment tests belong to ONE family; no cherry-picked unadjusted p-values.
    primary=stats[(stats.window=='main2020')&stats.id.ne('ON0')].copy();tests=[]
    for _,row in primary.iterrows():
        for col in ['p_mean','p_inc']:tests.append((row.id,col,float(row[col]) if pd.notna(row[col]) else 1.))
    tests.sort(key=lambda x:x[2]);last=0;adj={}
    for i,(name,col,p) in enumerate(tests):last=max(last,min(1,p*(len(tests)-i)));adj[(name,col)]=last
    gates=[]
    for _,r in primary.iterrows():
        name=r.id;oldr=stats[(stats.id==name)&stats.window.eq('old2020_2023')].iloc[0];newr=stats[(stats.id==name)&stats.window.eq('recent2024')].iloc[0]
        yr=stats[(stats.id==name)&stats.window.str.fullmatch('[0-9]{4}')&stats.window.ge('2020')]
        dbl=st[(st.id==name)&st.window.eq('main2020')&st.kind.eq('slip')&st.value.eq(10)].iloc[0]
        delayed=st[(st.id==name)&st.window.eq('main2020')&st.kind.str.startswith('exit0935')]
        ok=bool(r.n>=60 and oldr.n>=20 and newr.n>=20 and (yr['mean']>0).sum()>=3 and oldr['mean']>0 and newr['mean']>0 and r['mean']>0 and r.delete5>0 and r.delete5_cash>0 and dbl['mean']>0 and (delayed['mean']>0).all() and r.ci_low>0 and r.inc_low>0 and adj[(name,'p_mean')]<.05 and adj[(name,'p_inc')]<.05)
        gates.append(dict(id=name,n=r.n,mean=r['mean'],old_mean=oldr['mean'],recent_mean=newr['mean'],holm_mean=adj[(name,'p_mean')],holm_increment=adj[(name,'p_inc')],historical_numeric_pass=ok,execution_certified=False,status='historical_candidate_pending_execution' if ok else 'not_passed_or_observation'))
    gate=save('candidate_gates.csv',gates)
    # Frozen neighboring thresholds and 14:45 latency input: diagnostics only, never replace defaults.
    neigh=[]
    for ver,f in [('ON1',f1),('ON2',f2)]:
        variants=[('clow',v) for v in [.15,.25]]+[('chigh',v) for v in [.75,.85]]+[('r',v) for v in [3,5]]+[('vl',v) for v in [.7,.9]]+[('vh',v) for v in [1.3,1.7]]
        target={'clow':['F2'],'chigh':['F1'],'r':['F3','F4'],'vl':['F5'],'vh':['F6']}
        for param,val in variants:
            rr=rules(f,**{param:val})
            for k in target[param]:neigh.append(dict(id=ver+'_'+k,param=param,value=val,**brief(d[wins['main2020']&rr[k].fillna(False)])))
    for k,v in rules(lag).items():neigh.append(dict(id='ON2_'+k,param='asof',value='14:45',**brief(d[wins['main2020']&v.fillna(False)])))
    save('neighbors_and_latency.csv',neigh)
    # Full rolling 12-month baselines, frozen-stage descriptive cells and leave-year-out evidence.
    desc=[]
    for name,mask in masks.items():
        hit=mask.fillna(False)
        for stage in ['U','R','D','C','UNKNOWN']:desc.append(dict(id=name,kind='stage',value=stage,**brief(d[wins['main2020']&hit&d.stage.eq(stage)])))
        for y in range(2020,2027):desc.append(dict(id=name,kind='exclude_year',value=str(y),**brief(d[wins['main2020']&hit&d.date.dt.year.ne(y)])))
    save('descriptive_cells.csv',desc)
    rolls=[]
    for end in pd.date_range('2021-01-01','2026-09-01',freq='MS'):
        start=end-pd.DateOffset(years=1)
        for name,mask in masks.items():rolls.append(dict(id=name,start=start,end_exclusive=end,**brief(d[d.date.ge(start)&d.date.lt(end)&mask.fillna(False)])))
    save('rolling12.csv',rolls)
    # Retrospective expanding selection: modest predeclared training gates, full gates remain separate above.
    selections=[];trainlogs=[];wfmask=pd.Series(False,index=d.index)
    for year in range(2022,2027):
        options=[]
        for name,mask in masks.items():
            if name=='ON0':continue
            g=d[d.date.ge('2020-01-01')&d.exit_date.lt(pd.Timestamp(year,1,1))&mask.fillna(False)];b=brief(g)
            pos=(g.groupby(g.date.dt.year).net.mean()>0).sum()
            passed=len(g)>=60 and b.get('delete5',-1)>0 and b.get('delete5_cash',-1)>0 and pos>=3
            trainlogs.append(dict(year=year,id=name,passed=passed,last_exit=g.exit_date.max(),**b))
            if passed:options.append((b['delete5'],len(g),name))
        selected=sorted(options,key=lambda z:(-z[0],-z[1],z[2]))[0][2] if options else 'NONE'
        sm=(d.date.dt.year.eq(year)&masks[selected].fillna(False)&full) if selected!='NONE' else pd.Series(False,index=d.index)
        wfmask|=sm;selections.append(dict(year=year,id=selected,**brief(d[sm])))
    save('walkforward.csv',selections);save('walkforward_training.csv',trainlogs);save('walkforward_trades.csv',d[wfmask])
    ac=[]
    for name,mask in masks.items():
        z,tr,summary=account(d,mask.fillna(False));z['id']=name;save('account_'+name+'.csv',z);save('account_trades_'+name+'.csv',tr);ac.append(dict(id=name,**summary))
    save('accounts.csv',ac)
    audit=dict(data_start=str(d.date.min().date()),data_end=str(d.date.max().date()),daily_rows=len(d),completed_labels=int(full.sum()),minute_days=int(m.date.nunique()),tail_valid=int(f2.clv.notna().sum()),minute_good_days=int(good.sum()),corporate_events=len(events),input_hashes=inputs,dividend_source=SOURCE,dividend_verification='Vendor implementation table, nine dates match action flags; primary announcements and cash settlement not independently certified',cost='date-varying stamp and transfer, assumed commission,20% dividend-tax scenario',feature_checks='prior current/future mutation,tail future-bar mutation,prefix,fee floors,cash direction,calendar and decomposition passed',limits='OHLC price proxies, not auction queue certification. ON2_F7 unavailable without intraday index. No clean OOS. Account credits dividend receivable on ex-date; open/close sampled drawdown, not tick worst drawdown.',numeric_candidates=gate.loc[gate.historical_numeric_pass,'id'].tolist(),execution_certified=False)
    (R/'audit.json').write_text(json.dumps(audit,indent=2))
    cols=['id','window','n','mean','win','cash','delete5','ci_low','ci_high','increment']
    report=['# B08 overnight research','Frozen inputs through 2026-09-11; all results exploratory historical, 20% dividend tax scenario.','## Main/old/recent',stats[stats.window.isin(['main2020','old2020_2023','recent2024'])][cols].to_markdown(index=False,floatfmt='.4f'),'## Gates',gate.to_markdown(index=False),'## Annual selection',pd.DataFrame(selections).to_markdown(index=False),'## Audit',json.dumps(audit,indent=2)]
    (R/'REPORT.md').write_text('\n\n'.join(report))
    manifest=dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.iterdir() if p.is_file() and p.name!='manifest.json'})
    (R/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(audit))
if __name__=='__main__':run()
