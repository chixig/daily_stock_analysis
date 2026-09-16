#!/usr/bin/env python3
"""Frozen B11: causal loss avoidance and next-morning stop/deadline exits."""
import os,json,hashlib,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
import foxconn_overnight_b08 as b8
import foxconn_overnight_b09 as b9
import foxconn_overnight_b10 as b10
R=Path('research/foxconn_overnight_20260916_b11');P10=Path('research/foxconn_overnight_20260916_b10')
def save(n,x):
    z=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x);z.to_csv(R/n,index=False);return z

def metrics(g):
    z=b8.brief(g)
    if len(g):
        a=np.sort(g.net.to_numpy());z.update(bad_n=int(g.net.le(-1).sum()),good_n=int(g.net.ge(1).sum()),delete_worst5=float(a[5:].mean()) if len(a)>5 else None,delete_both5=float(a[5:-5].mean()) if len(a)>10 else None)
    return z

def riskfit(d,f,mask):
    g=d[mask];model=DecisionTreeClassifier(max_depth=2,min_samples_leaf=40,random_state=601138);model.fit(f.loc[mask],g.net.le(-1).astype(int));ids=model.apply(f.loc[mask]);paths=b10.leaf_paths(model,list(f));rows=[]
    for node in sorted(set(ids)):
        x=g.iloc[np.flatnonzero(ids==node)];rows.append(dict(node=int(node),rule=' AND '.join(paths[node]),bad_rate=float(x.net.le(-1).mean()),**metrics(x)))
    best=sorted(rows,key=lambda a:(-a['bad_rate'],a['mean'],-a['n'],a['node']))[0]
    enabled=best['bad_rate']>g.net.le(-1).mean() and best['mean']<0
    return model,best,enabled,rows

# Bars are labelled by end time. A limit-down/open or zero-volume interval cannot guarantee a sale.
# Pending liquidation is carried to the next observed bar/day with an open above the lower limit.
def morning_exit(entry,days,bars,start,deadline,stop,worst=False):
    threshold=entry*(1.0005)*(1-stop) if stop else None
    pending=False;delayed=False;div=0.;first_reason=None
    for j in range(start,len(days)):
        day=days[j];div+=float(day['dividend_today']);lower=round(float(day['preclose'])*.9+1e-8,2)
        tradeable=day['volume']>0 and day['open']>lower+.005
        gap=threshold is not None and day['open']+div*.8<=threshold
        if j==start and (deadline=='09:30' or gap):pending=True;first_reason='opening_gap_stop' if gap else 'opening_exit'
        if pending and tradeable:return dict(price=float(day['open']),actual_exit=day['date'],clock='09:30',reason=first_reason,delayed=delayed,dividend=div)
        if pending:delayed=True
        bs=bars.get(day['date'])
        if bs is None:return dict(price=np.nan,reason='missing_minute_path',delayed=delayed)
        for b in bs:
            lower_open=b['volume']>0 and b['open']>lower+.005
            if pending:
                if lower_open:return dict(price=float(b['open']),actual_exit=day['date'],clock=(pd.Timestamp('2000-01-01 '+b['clock'])-pd.Timedelta(minutes=5)).strftime('%H:%M'),reason=first_reason,delayed=True,dividend=div)
                continue
            line=threshold-div*.8 if threshold else None
            triggered=line is not None and b['low']<=line
            due=b['clock']>=deadline
            if not triggered and not due:continue
            reason='bar_gap_stop' if triggered and b['open']<=line else ('intrabar_stop' if triggered else 'deadline')
            if b['volume']<=0 or (triggered and min(line,b['open'])<=lower+.005) or (not triggered and b['close']<=lower+.005):
                pending=True;delayed=True;first_reason=reason;continue
            price=(b['open'] if b['open']<=line else (b['low'] if worst else line)) if triggered else b['close']
            return dict(price=float(price),actual_exit=day['date'],clock=b['clock'],reason=reason,delayed=delayed,dividend=div)
        if not pending:pending=True;delayed=True;first_reason='deadline_pending'
    return dict(price=np.nan,reason='unresolved_end',delayed=delayed)

def tests():
    dt=pd.Timestamp('2026-01-01')
    def day(o=100):return dict(date=dt,open=o,volume=1000,preclose=100,dividend_today=0)
    def bar(o,h,l,c):return dict(clock='09:35',open=o,high=h,low=l,close=c,volume=100)
    x=morning_exit(100,[day(94)],{dt:[bar(94,96,93,95)]},0,'10:00',.01);assert x['price']==94 and x['reason']=='opening_gap_stop'
    x=morning_exit(100,[day()],{dt:[bar(100,101,98,100)]},0,'09:35',.01);assert abs(x['price']-99.0495)<1e-8
    assert morning_exit(100,[day()],{dt:[bar(100,101,98,100)]},0,'09:35',.01,True)['price']==98
    assert morning_exit(100,[day()],{dt:[bar(100,101,98,100)]},0,'09:35',None)['price']==100
    d2=day(92);d2['date']=dt+pd.Timedelta(days=1);d2['preclose']=90
    x=morning_exit(100,[day(90),d2],{dt:[bar(90,90,90,90)]},0,'09:35',.01);assert x['price']==92 and x['delayed']
    # A future bar cannot alter an earlier stop.
    b=[bar(100,101,98,100)];a=morning_exit(100,[day()],{dt:b},0,'10:00',.01);b.append(dict(clock='09:40',open=200,high=300,low=1,close=250,volume=100));assert morning_exit(100,[day()],{dt:b},0,'10:00',.01)==a

def run():
    assert os.environ.get('GITHUB_ACTIONS')=='true';tests();R.mkdir(parents=True,exist_ok=True)
    inputs={};pm=json.loads((P10/'manifest.json').read_text())
    for name in ['features.csv','walkforward_predictions.csv']:
        p=P10/name;h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==pm['files'][str(p)];inputs[str(p)]=h
    for p,h in json.loads((P10/'audit.json').read_text())['input_hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h;inputs[p]=h
    d=pd.read_csv(b9.P8/'daily_ledger.csv',parse_dates=['date','exit_date']);f=pd.read_csv(P10/'features.csv').drop(columns='date');assert len(d)==len(f)==2007
    np.testing.assert_allclose(b8.pnl(d)[0],d.cash,atol=1e-8,equal_nan=True)
    valid=f.notna().all(axis=1)&d.next_open.notna()&d.date.ge('2020-01-01');main=valid&d.date.dt.year.ge(2022)
    masks={'ON0':valid,'A':valid&f.prev_vol20.gt(2.56433344)&f.prev_r1.le(-5.06116557),'B':valid&f.prev_r20.gt(-16.1565018)&f.tail_volume_ratio.le(.432379827),'C':valid&f.prev_r20.le(-16.1565018)}
    pred=pd.read_csv(P10/'walkforward_predictions.csv',parse_dates=['date']);pred=pred[pred.model.eq('return_regressor')];masks['WF_ENTRY']=d.date.isin(pred.loc[pred.selected,'date'])&valid
    blocked=d.close.ge(d.preclose*1.099)|d.volume.le(0)
    for k in masks:masks[k]&=~blocked
    windows={'main2022':main,'early2022_2023':main&d.date.dt.year.le(2023),'recent2024':main&d.date.dt.year.ge(2024)}
    windows.update({str(y):main&d.date.dt.year.eq(y) for y in range(2022,2027)})
    # Route 1: only previous years' realized losses select each year's exclusion leaf.
    exclude=pd.Series(False,index=d.index);logs=[];leaves=[]
    for year in range(2022,2027):
        tr=valid&~blocked&d.exit_date.lt(pd.Timestamp(year,1,1));te=main&d.date.dt.year.eq(year)
        model,best,enabled,rows=riskfit(d,f,tr);assert d.loc[tr,'exit_date'].max()<pd.Timestamp(year,1,1)
        pre=d.date.lt(pd.Timestamp(year,1,1));mm,bb,ee,_=riskfit(d[pre],f[pre],tr[pre]);np.testing.assert_array_equal(model.tree_.feature,mm.tree_.feature);np.testing.assert_allclose(model.tree_.threshold,mm.tree_.threshold);assert bb['node']==best['node'] and ee==enabled
        if enabled:exclude.loc[te]=model.apply(f.loc[te])==best['node']
        logs.append(dict(year=year,enabled=bool(enabled),train_n=int(tr.sum()),last_training_exit=d.loc[tr,'exit_date'].max(),**best));leaves.extend([dict(year=year,**row) for row in rows])
    save('risk_rules.csv',logs);save('risk_leaves.csv',leaves);save('risk_signals.csv',pd.DataFrame({'date':d.date,'excluded':exclude}))
    risk=[];rtr=[];mir=[]
    for name,mask in masks.items():
        for wn,wm in windows.items():
            base=d[mask&wm];removed=d[mask&wm&exclude];kept=d[mask&wm&~exclude]
            for variant,g in [('base',base),('removed',removed),('kept',kept)]:risk.append(dict(entry=name,window=wn,variant=variant,base_n=len(base),**metrics(g)))
            if wn in ['main2022','recent2024']:
                assert len(kept)+len(removed)==len(base);assert abs(kept.cash.sum()+removed.cash.sum()-base.cash.sum())<1e-7
                if len(kept) and kept.net.mean()<0:mir.append(dict(route='risk',entry=name,window=wn,**metrics(b9.changes(kept,reverse=True))))
        g=d[mask&main].copy();g['entry']=name;g['risk_excluded']=exclude.loc[g.index];rtr.append(g)
    riskdf=save('risk_results.csv',risk);save('risk_trades.csv',pd.concat(rtr))
    with zipfile.ZipFile(b8.P/'source/601138-full-5min-history.zip') as z:m=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('601138_5min_all.csv'))))
    m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock']);assert not m.duplicated(['date','clock']).any()
    expected=list(pd.date_range('2000-01-01 09:35','2000-01-01 11:30',freq='5min').strftime('%H:%M'))+list(pd.date_range('2000-01-01 13:05','2000-01-01 15:00',freq='5min').strftime('%H:%M'))
    bars={date:x.to_dict('records') for date,x in m.groupby('date') if x.clock.tolist()==expected};days=d.to_dict('records')
    # Route2 is evaluated independently; no risk-filter/stop Cartesian search.
    modes=[('OPEN','09:30',None,False)]+[(f'{tm.replace(":","")}_S{int(st*100) if st else 0}',tm,st,False) for tm in ['09:35','10:00'] for st in [None,.01,.02]]
    modes +=[(f'{tm.replace(":","")}_S{int(st*100)}_WORSTBAR',tm,st,True) for tm in ['09:35','10:00'] for st in [.01,.02]]
    priced={};exit_audit=[]
    for label,tm,st,worst in modes:
        rows=[]
        for i in d[main&~blocked].index:
            x=morning_exit(d.loc[i,'close'],days,bars,i+1,tm,st,worst);rows.append(dict(index=int(i),**x))
        ex=pd.DataFrame(rows).set_index('index');g=d.loc[ex.index].copy();g['model_exit']=ex.price;g['reason']=ex.reason;g['delayed']=ex.delayed;g['exit_clock']=ex.get('clock');g['actual_exit']=pd.to_datetime(ex.get('actual_exit'));g['dividend']=ex.get('dividend');g['exit_date']=g.actual_exit
        g['cash'],g['net'],g['fee']=b8.pnl(g,exitcol='model_exit');g['gross']=100*((g.model_exit+g.dividend*.8)/g.close-1)
        priced[label]=g
        exit_audit.append(dict(exit=label,candidates=len(g),resolved=int(g.net.notna().sum()),missing=int(g.net.isna().sum()),delayed=int(g.delayed.sum())))
    save('exit_coverage.csv',exit_audit)
    # Reporting diagnostics only: intervals, examples and delayed fills; no selection or threshold change.
    examples=[];intervals=[]
    for label in ['OPEN','1000_S0','1000_S1','1000_S2','1000_S2_WORSTBAR']:
        g=priced[label]
        for name in ['C','WF_ENTRY']:
            mask=masks[name].loc[g.index]&g.net.notna()
            x=g[mask].copy();x['entry']=name;x['exit_model']=label
            for tail,part in [('best',x.nlargest(5,'net')),('worst',x.nsmallest(5,'net'))]:
                part=part.copy();part['tail']=tail;examples.append(part)
            for wn in ['main2022','recent2024']:
                u=g[mask&windows[wn].loc[g.index]].copy();base=priced['OPEN'].loc[u.index];no=priced['1000_S0'].loc[u.index]
                for comparison,v in [('absolute',u.net),('vs_open',u.net-base.net),('vs_1000_no_stop',u.net-no.net)]:
                    z=u.copy();z['net']=v;ci=b8.boot(z,pd.Series(True,index=z.index));intervals.append(dict(entry=name,exit=label,window=wn,comparison=comparison,n=len(z),mean=float(v.mean()),ci_low=ci['ci_low'],ci_high=ci['ci_high']))
    save('selected_case_examples.csv',pd.concat(examples)[['entry','exit_model','tail','date','close','next_open','model_exit','actual_exit','exit_clock','net','cash','reason','delayed']])
    save('descriptive_intervals.csv',intervals)
    z=priced['OPEN'][priced['OPEN'].delayed].copy();save('delayed_exit_cases.csv',z[['date','close','next_open','model_exit','actual_exit','exit_clock','net','cash','reason']])

    stoprows=[];stoptr=[];stress=[]
    for name,mask in masks.items():
        for label,tm,st,worst in modes:
            g=priced[label];common=g.net.notna()&priced['OPEN'].net.notna()
            for wn,wm in windows.items():
                want=mask.loc[g.index]&wm.loc[g.index];pick=want&common;x=g[pick];base=priced['OPEN'][pick];orig=d.loc[x.index]
                z=dict(entry=name,exit=label,window=wn,eligible=int(want.sum()),excluded=int((want&~common).sum()),paired_open_mean=float(base.net.mean()),paired_open_cash=float(base.cash.sum()),delta_mean=float((x.net-base.net).mean()),delta_cash=float((x.cash-base.cash).sum()),opening_stops=int(x.reason.eq('opening_gap_stop').sum()),bar_stops=int(x.reason.isin(['bar_gap_stop','intrabar_stop']).sum()),delayed=int(x.delayed.sum()),saved_losses=int((base.net.lt(0)&x.net.ge(0)).sum()),spoiled_winners=int((base.net.gt(0)&x.net.le(0)).sum()),**metrics(x))
                if st:
                    no=priced[tm.replace(':','')+'_S0'].loc[x.index];same=no.net.notna();z.update(no_stop_common=int(same.sum()),stop_vs_no_stop_mean=float((x.net[same]-no.net[same]).mean()),stop_vs_no_stop_cash=float((x.cash[same]-no.cash[same]).sum()))
                stoprows.append(z)
                if wn=='main2022' and not worst:
                    for slip in [.001,.002]:stress.append(dict(entry=name,exit=label,slip=slip,**metrics(b9.changes(x,slip=slip,exitcol='model_exit'))))
                if wn in ['main2022','recent2024'] and label=='OPEN' and len(x) and x.net.mean()<0:mir.append(dict(route='exit',entry=name,window=wn,**metrics(b9.changes(x,reverse=True,exitcol='model_exit'))))
            x=g[mask.loc[g.index]&common].copy();x['entry']=name;x['exit_model']=label;stoptr.append(x)
    sr=save('exit_results.csv',stoprows);save('exit_trades.csv',pd.concat(stoptr));save('exit_stress.csv',stress);save('mirror_registry.csv',mir)
    # Baseline engine must agree with official-open cash whenever no execution delay occurs.
    op=priced['OPEN'];ok=op.net.notna()&~op.delayed;np.testing.assert_allclose(op.loc[ok,'cash'],d.loc[op.index[ok],'cash'],atol=1e-8)
    # Worst intrabar fills cannot improve on their matched standard stop, including fees.
    for label,_,_,worst in modes:
        if worst:
            a=priced[label];b=priced[label.replace('_WORSTBAR','')];ok=a.net.notna()&b.net.notna();assert (a.loc[ok,'net']<=b.loc[ok,'net']+1e-10).all()
    audit=dict(data_end=str(d.date.max().date()),risk_model='loss<=-1%,depth2,minleaf40,yearly train completed previous years;highest-loss-rate negative-mean leaf excluded',entry_sets='ON0,A,B,C fixed B10 hindsight candidates;WF_ENTRY=B10 chronological regressor selector;all exclude entry-limit proxy',stop_contract='price drawdown from slipped entry before fees;credit20%-tax dividend receivable;gap fill open,bar cross threshold,slip/fees extra;worstbar diagnostic;deadline09:35/10:00;stop1/2%;no TP',input_hashes=inputs,full_minute_days=len(bars),checks='source hashes,B08 cash,prefix risk fit,train cutoff,partition cash,synthetic gap/bar/deadline/locked sale/future-bar tests,open baseline equality,worst-fill dominance passed',limitations='A/B/C entry thresholds discovered using full history;all historical data previously viewed. No prospective OOS. Five-minute range executions and limit proxies not queue-certified. Opportunity ledger only,delayed-exit overlapping trades not a capital-feasible portfolio. Missing paths disclosed,not assumed successful. Symmetric trims diagnostic,not hard selection gates.')
    (R/'audit.json').write_text(json.dumps(audit,indent=2))
    cols=['entry','window','variant','n','mean','cash','good_n','bad_n','delete5','delete_worst5','delete_both5']
    cols2=['entry','exit','window','n','mean','cash','delta_mean','stop_vs_no_stop_mean','opening_stops','bar_stops','saved_losses','spoiled_winners','delete5','delete_worst5']
    parts=['# B11 两条路线：事前避亏与次晨止损','固定参数，删赢家/删输家对称诊断，不作单独否决。A/B/C仍属事后入场候选，不能把后续年度退出检查称为全策略独立验证。','## 风险规则',pd.DataFrame(logs)[['year','rule','bad_rate','mean','n']].to_markdown(index=False),'## 路线1',riskdf[riskdf.window.isin(['main2022','early2022_2023','recent2024'])][cols].to_markdown(index=False,floatfmt='.4f'),'## 路线2',sr[sr.window.isin(['main2022','early2022_2023','recent2024'])&~sr.exit.str.contains('WORST')][cols2].to_markdown(index=False,floatfmt='.4f'),'## 审计',json.dumps(audit,indent=2)]
    (R/'REPORT.md').write_text('\n\n'.join(parts));(R/'manifest.json').write_text(json.dumps(dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],spec_sha256=hashlib.sha256(Path('DOCS/FOXCONN_OVERNIGHT_B11.md').read_bytes()).hexdigest(),files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.iterdir() if p.is_file() and p.name!='manifest.json'}),indent=2));print(json.dumps(audit))
if __name__=='__main__':run()
