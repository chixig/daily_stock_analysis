#!/usr/bin/env python3
"""Outcome-first case profiling and bounded interpretable fitting; GitHub only."""
import os,json,hashlib,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.tree import DecisionTreeClassifier,DecisionTreeRegressor,export_text
import foxconn_overnight_b08 as b8
import foxconn_overnight_b09 as b9
R=Path('research/foxconn_overnight_20260916_b10');P8=b9.P8

def save(n,x):
    t=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x);t.to_csv(R/n,index=False);return t

def make_features(d,m,ix):
    t,a=b8.tail_features(d,m,'14:50');path=b9.features(d,m);c=d.signal_close
    f=pd.DataFrame({'prev_r1':100*c.pct_change().shift(),'prev_r3':100*c.pct_change(3).shift(),'prev_r5':100*c.pct_change(5).shift(),'prev_r20':100*c.pct_change(20).shift(),
        'prev_bias20':100*(c/c.rolling(20).mean()-1).shift(),'prev_vol20':100*np.log(c).diff().rolling(20).std().shift(),
        'prev_intraday':100*(d.close/d.open-1).shift(),'prev_clv':((d.close-d.low)/(d.high-d.low).replace(0,np.nan)).shift(),
        'prev_volume_ratio':(d.volume/d.volume.shift().rolling(20).mean()).shift(),'prev_market1':100*ix.pct_change().shift(),'prev_market20':100*ix.pct_change(20).shift(),
        'prev_relative20':100*(c.pct_change(20)-ix.pct_change(20)).shift(),'today_gap':100*(d.open/d.preclose-1),
        'return1450':100*(a.p/d.preclose-1),'range1450':100*(a.h-a.l)/d.preclose,'clv1450':t.clv,'volume_ratio1450':t.vr,
        'morning_return':path.morning,'afternoon_return':path.afternoon,'tail_return':path['tail'],'tail_volume_ratio':path.vr,
        'breakout_distance':100*(path.p/path.prior_high-1),'breakdown_distance':100*(path.p/path.prior_low-1),
        'known_gapdays':(d.exit_date-d.date).dt.days.astype(float)})
    return f

def met(g,total_good=None):
    z=b8.brief(g)
    if not len(g):return {**z,'good_n':0,'good_pct':None,'bad_pct':None,'recall_pct':0 if total_good else None}
    good=int(g.net.ge(1).sum());z.update(good_n=good,good_pct=100*good/len(g),bad_pct=float(100*g.net.le(-1).mean()),recall_pct=100*good/total_good if total_good else None)
    return z

def profiles(d,f,mask,name):
    z=[]
    for col in f:
        valid=mask&f[col].notna();a=f.loc[valid&d.net.ge(1),col];b=f.loc[valid&d.net.lt(1),col];bad=f.loc[valid&d.net.le(-1),col]
        sd=f.loc[valid,col].std()
        if len(a)<2 or len(b)<2:continue
        z.append(dict(window=name,feature=col,good_n=len(a),other_n=len(b),good_median=a.median(),other_median=b.median(),bad_median=bad.median(),standardized_difference=(a.mean()-b.mean())/sd if sd else 0,good_vs_bad=(a.mean()-bad.mean())/sd if sd and len(bad) else None,p=mannwhitneyu(a,b,alternative='two-sided').pvalue))
    # BH q-values are descriptive; no independent confirmation or automatic feature selection.
    order=sorted(range(len(z)),key=lambda i:z[i]['p']);q=1
    for rank,i in reversed(list(enumerate(order,1))):q=min(q,z[i]['p']*len(z)/rank);z[i]['q_descriptive']=q
    return z

def leaf_paths(model,columns):
    out={}
    def go(i,path):
        if model.tree_.children_left[i]<0:out[i]=path or ['ALL'];return
        j=model.tree_.feature[i];v=model.tree_.threshold[i]
        go(model.tree_.children_left[i],path+[f'{columns[j]} <= {v:.9g}'])
        go(model.tree_.children_right[i],path+[f'{columns[j]} > {v:.9g}'])
    go(0,[]);return out

def fit(d,f,mask,kind):
    model=(DecisionTreeClassifier if kind=='case_classifier' else DecisionTreeRegressor)(max_depth=2,min_samples_leaf=40,random_state=601138)
    train=d[mask];X=f.loc[mask];y=train.net.ge(1).astype(int) if kind=='case_classifier' else train.net
    model.fit(X,y);leaf=model.apply(X);paths=leaf_paths(model,list(f));rows=[];options=[]
    for node in sorted(set(leaf)):
        g=train.iloc[np.flatnonzero(leaf==node)];row=dict(node=int(node),rule=' AND '.join(paths[node]),**met(g,int(train.net.ge(1).sum())));rows.append(row)
        if kind=='case_classifier':
            if row['good_n']>=5:options.append((row['good_pct'],row['mean'],len(g),int(node)))
        else:options.append((row['mean'],row['good_pct'],len(g),int(node)))
    node=sorted(options,key=lambda x:(-x[0],-x[1],-x[2],x[3]))[0][3] if options else None
    chosen=next((x for x in rows if x['node']==node),None)
    economic=chosen is not None and chosen['mean']>0 and chosen['delete5']>0 and chosen['delete5_cash']>0
    return model,node,rows,economic

def run():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    R.mkdir(parents=True,exist_ok=True);inputs={}
    pm=json.loads((P8/'manifest.json').read_text());p=P8/'daily_ledger.csv';h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==pm['files'][str(p)];inputs[str(p)]=h
    pa=json.loads((P8/'audit.json').read_text())
    for p,h in pa['input_hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h;inputs[p]=h
    d=pd.read_csv(P8/'daily_ledger.csv',parse_dates=['date','exit_date']);assert len(d)==2007
    np.testing.assert_allclose(b8.pnl(d)[0],d.cash,atol=1e-8,equal_nan=True)
    with zipfile.ZipFile(b8.P/'source/601138-full-5min-history.zip') as z:m=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('601138_5min_all.csv'))))
    m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
    ix=d.date.map(pd.read_csv(b8.B2/'source/sse_index.csv',parse_dates=['date']).set_index('date').close)
    f=make_features(d,m,ix);assert len(f.columns)==24
    for cut in [900,1600]:
        mm=m.copy();mm['volume']=mm.volume.astype(float);s=(mm.date>d.date.iloc[cut])|((mm.date==d.date.iloc[cut])&mm.clock.gt('14:50'));mm.loc[s,['open','high','low','close','volume']]*=1.5
        dd=d.copy();dd['volume']=dd.volume.astype(float);dd.loc[cut:,['close','high','low','volume']]*=1.7
        # signal_close/close adjustment factor is held equal for the raw scaling test at the cutoff.
        dd.loc[cut:,'signal_close']*=1.7
        pd.testing.assert_series_equal(make_features(dd,mm,ix).iloc[cut],f.iloc[cut])
        pd.testing.assert_frame_equal(make_features(d.iloc[:cut+1],m[m.date<=d.date.iloc[cut]],ix.iloc[:cut+1]),f.iloc[:cut+1])
    full=d.next_open.notna();main=full&d.date.ge('2020-01-01');valid=f.notna().all(axis=1);eligible=main&valid
    assert abs(d.loc[main,'net'].mean()+.3291354026252871)<1e-10
    windows={'all':full,'main2020':main,'old2020_2023':main&d.date.dt.year.le(2023),'recent2024':main&d.date.dt.year.ge(2024)}
    windows.update({str(y):main&d.date.dt.year.eq(y) for y in range(2020,2027)})
    counts=[]
    for name,wm in windows.items():
        for threshold in [.5,1,2]:
            g=d[wm&d.net.ge(threshold)];counts.append(dict(window=name,threshold=threshold,total=int(wm.sum()),rate_pct=100*len(g)/wm.sum() if wm.sum() else None,model_valid_good=int((wm&d.net.ge(threshold)&valid).sum()),**met(g)))
    ct=save('case_counts.csv',counts)
    library=pd.concat([d[['date','exit_date','open','close','next_open','net','cash','gross','stage','dividend','exit0935close','exit0935open']],f],axis=1)
    library['model_valid']=valid;save('good_case_library.csv',library[main&d.net.ge(1)].sort_values('net',ascending=False));save('top20_return.csv',library[main].nlargest(20,'net'));save('top20_cash.csv',library[main].nlargest(20,'cash'));save('features.csv',pd.concat([d[['date']],f],axis=1))
    profile=[]
    for name in ['main2020','old2020_2023','recent2024']:profile+=profiles(d,f,windows[name],name)
    prof=save('factor_profiles.csv',profile)
    # Three nearest-volatility non-good controls in same calendar year and frozen stage.
    pairs=[]
    for i in d[main&d.net.ge(1)&f.prev_vol20.notna()].index:
        pool=d[main&d.net.lt(1)&d.date.dt.year.eq(d.loc[i,'date'].year)&d.stage.eq(d.loc[i,'stage'])&f.prev_vol20.notna()].index
        near=(f.loc[pool,'prev_vol20']-f.loc[i,'prev_vol20']).abs().sort_values(kind='stable').index[:3]
        for j in near:pairs.append(dict(case_index=int(i),control_index=int(j),case_date=d.loc[i,'date'],control_date=d.loc[j,'date'],stage=d.loc[i,'stage'],vol_distance=float(abs(f.loc[i,'prev_vol20']-f.loc[j,'prev_vol20']))))
    pair=save('matched_pairs.csv',pairs);matched=[]
    for col in f:
        a=f.loc[pair.case_index,col].to_numpy();b=f.loc[pair.control_index,col].to_numpy();ok=np.isfinite(a)&np.isfinite(b);sd=f.loc[main,col].std()
        matched.append(dict(feature=col,pairs=int(ok.sum()),cases=int(pair.loc[ok,'case_index'].nunique()),unique_controls=int(pair.loc[ok,'control_index'].nunique()),case_mean=float(a[ok].mean()),control_mean=float(b[ok].mean()),standardized_paired_difference=float((a[ok]-b[ok]).mean()/sd) if sd else 0))
    match=save('matched_factor_profiles.csv',matched)
    # All-data fits intentionally describe discovered cases; never call their performance OOS.
    leaves=[];discovery=[];stress=[];rules=[]
    for kind in ['case_classifier','return_regressor']:
        model,node,lr,eco=fit(d,f,eligible,kind)
        (R/(kind+'_fullfit.txt')).write_text(export_text(model,feature_names=list(f),decimals=6))
        leaves.extend([dict(model=kind,scope='ALL_DATA_IN_SAMPLE',**row) for row in lr])
        chosen=next((row for row in lr if row['node']==node),None)
        rules.append(dict(model=kind,scope='ALL_DATA_IN_SAMPLE',node=node,rule=chosen['rule'] if chosen else 'NONE',training_economic_gate=bool(eco)))
        selected=pd.Series(False,index=d.index)
        if node is not None:selected.loc[eligible]=model.apply(f.loc[eligible])==node
        for name in ['main2020','old2020_2023','recent2024']:
            g=d[windows[name]&selected];u=d[windows[name]&valid]
            discovery.append(dict(model=kind,window=name,**met(g,int(u.net.ge(1).sum())),**b8.boot(u,selected.loc[u.index])))
        g=d[selected].copy();g['model']=kind;save(kind+'_fullfit_trades.csv',g)
        for slip in [0,.001,.002]:stress.append(dict(model=kind,scope='ALL_DATA_IN_SAMPLE',kind='slip',value=slip,**met(b9.changes(g,slip=slip))))
        for col in ['exit0935close','exit0935open']:stress.append(dict(model=kind,scope='ALL_DATA_IN_SAMPLE',kind=col,value=0,excluded=int(g[col].isna().sum()),**met(b9.changes(g[g[col].notna()],exitcol=col))))
        # Show negative examples satisfying the very same fitted rule.
        save(kind+'_false_positive_cases.csv',library.loc[g.index[g.net<1]].sort_values('net').head(20))
    leaf=save('all_leaf_profiles.csv',leaves);disc=save('in_sample_rules.csv',rules);ds=save('in_sample_results.csv',discovery)
    # Rolling chronological fits; test outcomes never select thresholds or leaves.
    wf=[];fitlog=[];leaflog=[];preds=[];allmask={};ecomask={};fold_base=[]
    for kind in ['case_classifier','return_regressor']:
        selected=pd.Series(False,index=d.index);economic=pd.Series(False,index=d.index)
        for year in range(2022,2027):
            train=eligible&d.exit_date.lt(pd.Timestamp(year,1,1));test=eligible&d.date.dt.year.eq(year)
            assert not (train&test).any()
            assert d.loc[train,'exit_date'].max()<pd.Timestamp(year,1,1)
            model,node,lr,eco=fit(d,f,train,kind)
            # Refit a prefix alone; learned structure and chosen node must be identical.
            before=d.date.lt(pd.Timestamp(year,1,1));mm,nn,_,ee=fit(d[before],f[before],train[before],kind)
            np.testing.assert_array_equal(model.tree_.feature,mm.tree_.feature);np.testing.assert_allclose(model.tree_.threshold,mm.tree_.threshold);assert node==nn and eco==ee
            chosen=next((row for row in lr if row['node']==node),None)
            fitlog.append(dict(model=kind,year=year,train_n=int(train.sum()),last_exit=d.loc[train,'exit_date'].max(),chosen_node=node,rule=chosen['rule'] if chosen else 'NONE',economic=bool(eco),train_good_pct=chosen['good_pct'] if chosen else None,train_net_mean=chosen['mean'] if chosen else None))
            leaflog.extend([dict(model=kind,year=year,**row) for row in lr])
            h=pd.Series(False,index=d.index)
            if node is not None:h.loc[test]=model.apply(f.loc[test])==node
            selected|=h
            if eco:economic|=h
            g=d[h];totalgood=int(d.loc[test,'net'].ge(1).sum())
            wf.append(dict(model=kind,year=year,variant='diagnostic_best_leaf',rule=chosen['rule'] if chosen else 'NONE',**met(g,totalgood)))
            wf.append(dict(model=kind,year=year,variant='economic_gate',rule=chosen['rule'] if eco else 'NONE',**met(g if eco else g.iloc[:0],totalgood)))
            fold_base.append(dict(model=kind,year=year,**met(d[test])))
            for i in d[test].index:preds.append(dict(model=kind,date=d.loc[i,'date'],year=year,selected=bool(h.loc[i]),economic_selected=bool(h.loc[i] and eco),actual_net=d.loc[i,'net'],actual_cash=d.loc[i,'cash'],actual_good=bool(d.loc[i,'net']>=1)))
        allmask[kind]=selected;ecomask[kind]=economic
        for variant,mask in [('diagnostic_best_leaf',selected),('economic_gate',economic)]:
            for window,wm in [('combined2022',eligible&d.date.dt.year.ge(2022)),('old2022_2023',eligible&d.date.dt.year.between(2022,2023)),('recent2024',eligible&d.date.dt.year.ge(2024))]:
                u=d[wm];g=d[mask&wm];wf.append(dict(model=kind,year=window,variant=variant,rule='yearly_frozen',**met(g,int(u.net.ge(1).sum())),**b8.boot(u,mask.loc[u.index])))
            g=d[mask].copy();g['model']=kind;g['variant']=variant;save(kind+'_'+variant+'_wf_trades.csv',g)
            for slip in [0,.001,.002]:stress.append(dict(model=kind,scope=variant+'_WF',kind='slip',value=slip,**met(b9.changes(g,slip=slip))))
            for col in ['exit0935close','exit0935open']:stress.append(dict(model=kind,scope=variant+'_WF',kind=col,value=0,excluded=int(g[col].isna().sum()),**met(b9.changes(g[g[col].notna()],exitcol=col))))
    wft=save('walkforward_results.csv',wf);save('walkforward_rules.csv',fitlog);save('walkforward_leaves.csv',leaflog);save('walkforward_predictions.csv',preds);save('walkforward_baselines.csv',fold_base);save('stress.csv',stress)
    # Account and opposite-direction evidence only for the actual chronological selected dates.
    accounts=[];mir=[]
    for kind in allmask:
        for variant,mask in [('diagnostic',allmask[kind]),('economic',ecomask[kind])]:
            z,tr,ac=b8.account(d,mask);save(kind+'_'+variant+'_account.csv',z);accounts.append(dict(model=kind,variant=variant,**ac))
            for wn,wm in [('main2022',eligible&d.date.dt.year.ge(2022)),('recent2024',eligible&d.date.dt.year.ge(2024))]:
                g=d[mask&wm]
                if len(g) and g.net.mean()<0:mir.append(dict(model=kind,variant=variant,window=wn,**met(b9.changes(g,reverse=True))))
    save('accounts.csv',accounts);save('mirror_registry.csv',mir)
    audit=dict(data_end=str(d.date.max().date()),main_n=int(main.sum()),good_n=int((main&d.net.ge(1)).sum()),model_eligible=int(eligible.sum()),model_good=int((eligible&d.net.ge(1)).sum()),missing_model_good=int((main&d.net.ge(1)&~valid).sum()),features=list(f),input_hashes=inputs,model_contract='two families,depth2,minleaf40,seed601138;fullfit descriptive,annual2022-2026 causal thresholds;classifier selects highest good-rate leaf >=5 good cases,regressor highest mean;economic gate mean/delete5mean/delete5cash>0',matched_cases=int(pair.case_index.nunique()),matched_unique_controls=int(pair.control_index.nunique()),checks='parent cash/source hashes,feature mutation/prefix,training exit cutoff,prefix-identical fitted trees passed',limitations='Outcome-first full-data discovery is explicitly in-sample;historical walk-forward also uses previously viewed market history,not clean prospective OOS. Vendor dividends and execution proxy limitations inherited. No missing imputation;no new trading trigger adopted.')
    (R/'audit.json').write_text(json.dumps(audit,indent=2))
    reports=['# B10 Outcome-first discovery and interpretable fitting','## Good cases',ct[ct.threshold.eq(1)].to_markdown(index=False,floatfmt='.4f'),'## Full-data fitted rules (IN SAMPLE)',disc.to_markdown(index=False),'## Full-data fitted results (IN SAMPLE)',ds[['model','window','n','mean','cash','good_pct','recall_pct','bad_pct','delete5']].to_markdown(index=False,floatfmt='.4f'),'## Chronological rules',pd.DataFrame(fitlog).to_markdown(index=False,floatfmt='.5f'),'## Chronological results',wft[['model','year','variant','n','mean','cash','good_pct','recall_pct','bad_pct','delete5']].to_markdown(index=False,floatfmt='.4f'),'## Main factor descriptive comparisons',prof[prof.window.eq('main2020')].sort_values('standardized_difference',ascending=False).to_markdown(index=False,floatfmt='.4f'),'## Audit',json.dumps(audit,indent=2)]
    (R/'REPORT.md').write_text('\n\n'.join(reports))
    (R/'manifest.json').write_text(json.dumps(dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],spec_sha256=hashlib.sha256(Path('DOCS/FOXCONN_OVERNIGHT_B10.md').read_bytes()).hexdigest(),files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.iterdir() if p.is_file() and p.name!='manifest.json'}),indent=2));print(json.dumps(audit))
if __name__=='__main__':run()
