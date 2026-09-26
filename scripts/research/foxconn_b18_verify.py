#!/usr/bin/env python3
"""Fresh-process B18 output reconciliation and causal edge cases, GitHub only."""
import os,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import foxconn_b18 as b
R=b.R

def run():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    manifest=json.loads((R/'manifest.json').read_text())['files']
    for p,h in manifest.items():assert b.sha(p)==h,p
    checks=['all B18 calculation output hashes match']
    # Completion/no completion, response latency, gaps and future bar contents.
    r=pd.Series(dict(open=101.,limit_down=90.,limit_up=110.))
    target=dict(kind='target',tp=.005,stop=.01,branch='none',deadline='10:30')
    bars={'09:35':{'close':99.},'09:45':{'open':98.},'10:35':{'open':107.},'14:55':{'open':109.}}
    x,issues,why=b.first_buy(100.,r,bars,target);assert x[0]=='09:40' and x[1]==98. and why=='target_close'
    x,_,_=b.first_buy(100.,r,{**bars,'09:35':{'close':102.}},target);assert x[0]=='09:40' and x[1]==98.
    branch={**target,'branch':'both'};bb={**bars,'09:35':{'open':103.,'close':99.}}
    x,_,_=b.first_buy(100.,r,bb,branch);assert x[0]=='09:30' and x[1]==103.
    x,issues,_=b.first_buy(100.,r,{},target);assert x is None and len(issues)>0
    x,_,_=b.first_buy(100.,r,{'14:55':{'open':104.}},dict(kind='fixed',deadline='10:00'));assert x[0]=='14:50'
    x,_,_=b.first_buy(100.,r,{'14:55':{'open':110.}},dict(kind='fixed',deadline='10:00'));assert x is None
    # A future high/low/volume on the execution interval must not change the start price fill.
    noisy={k:{**v,'high':999.,'low':.01,'volume':0} for k,v in bars.items()}
    assert b.first_buy(100.,r,noisy,target)[0]==b.first_buy(100.,r,bars,target)[0]
    checks.append('synthetic gap/target/stop/latency/missing/deadline/limit/future-bar tests')
    grid=pd.read_csv(R/'all_experiments.csv');rules=pd.read_csv(R/'rules.csv')
    h=grid[(grid.period=='discovery')&grid.n.ge(40)].merge(rules[['rule','layer']],on='rule');selected=[]
    def add(df,col,n):
        for _,x in df.sort_values([col,'cash','rule','path'],ascending=[False,False,True,True]).head(n).iterrows():
            key=(x.rule,x.path)
            if key not in selected:selected.append(key)
    add(h[h.bp.eq(5)],'cash',2);add(h[h.bp.eq(5)&h.cash.gt(0)],'win',2);add(h[h.bp.eq(11)],'cash',2)
    for layer in ['daily','minute_unconfirmed']:add(h[h.bp.eq(5)&h.layer.eq(layer)],'cash',1)
    for key in [('S1_clv_ge_0p8','open'),('S0','open')]:
        if key not in selected:selected.append(key)
    frozen=pd.read_csv(R/'selected_before_later_account_review.csv');assert selected==list(zip(frozen.rule,frozen.path))
    checks.append('selected candidates reconstructed using discovery rows only')
    acc=pd.read_csv(R/'account_summary.csv');periods=pd.read_csv(R/'periods.csv');d=pd.read_csv(b.P/'daily_ledger.csv',parse_dates=['date','exit_date']);start=d.date.ge('2020-01-01');dates=d.loc[start,'date'].reset_index(drop=True);ds=d.loc[start].reset_index(drop=True)
    q=json.loads((R/'common_resources.json').read_text())['shares'];assert acc.stock.eq(q).all()
    summaries=[]
    for _,a in acc.iterrows():
        tag=f'{a.candidate}_{int(a.slip_bp)}';z=pd.read_csv(R/f'account_{tag}.csv',parse_dates=['date']);o=pd.read_csv(R/f'orders_{tag}.csv',parse_dates=['date']);t=pd.read_csv(R/f'trades_{tag}.csv',parse_dates=['entry','exit'])
        assert o.quantity.eq(1000).all();assert z.cash.min()>=-1e-6
        flow=(o.value*np.where(o.side.eq('SELL'),1,-1)-o.fee-o.tax).groupby(o.date).sum().reindex(dates,fill_value=0).to_numpy()
        qty=(o.quantity*np.where(o.side.eq('BUY'),1,-1)).groupby(o.date).sum().reindex(dates,fill_value=0).to_numpy()
        np.testing.assert_allclose(z.cash,z.external+np.cumsum(flow+z.payment.to_numpy()),atol=1e-5)
        np.testing.assert_array_equal(z.shares,q+np.cumsum(qty))
        np.testing.assert_allclose(z.hold_cash,z.external+z.hold_payment.cumsum(),atol=1e-5)
        np.testing.assert_allclose(z.relative,z.cash+z.receivable+z.shares*ds.close-z.tax_reserve-(z.hold_cash+z.hold_receivable+q*ds.close),atol=1e-5)
        done=t[t.exit_i.notna()];un=t[t.exit_i.isna()]
        marked=(un.sale_net-1000*d.close.iloc[-1]-un.missed_dividend).sum()
        assert abs(done.cash_increment.sum()+marked-z.tax_reserve.iloc[-1]-a.increment)<1e-5
        assert abs(a.trade_cash-done.cash_increment.sum())<1e-5
        assert abs(a.trade_win-100*done.cash_increment.gt(0).mean())<1e-6
        assert abs(a.relative_mdd-(z.relative-z.relative.cummax().clip(lower=0)).min())<1e-5
        for period in ['discovery','later','main']:
            sel=done.entry.lt('2024-01-01') if period=='discovery' else (done.entry.ge('2024-01-01') if period=='later' else np.ones(len(done),bool))
            pr=periods[(periods.candidate==a.candidate)&periods.bp.eq(a.slip_bp)&periods.period.eq(period)].iloc[0]
            assert abs(done.loc[sel,'cash_increment'].sum()-pr.cash)<1e-5
        summaries.append(dict(candidate=a.candidate,bp=a.slip_bp,checks='PASS'))
    checks.append(f'{len(acc)} accounts independently reconciled from persisted orders and daily balances')
    finepath=R/'fine_execution_comparison.csv'
    fine=pd.read_csv(finepath) if finepath.stat().st_size>2 else pd.DataFrame(columns=['candidate','covered','difference'])
    fine_summary=[]
    for k,g in fine.groupby('candidate'):
        hit=g[g.covered];fine_summary.append(dict(candidate=k,total=len(g),covered=len(hit),differences_ge_cent=int(hit.difference.abs().ge(.011).sum()),max_abs_difference=float(hit.difference.abs().max()) if len(hit) else None))
    b.save('fine_execution_summary.csv',fine_summary)
    result=dict(status='PASS',checks=checks,accounts=len(acc),verified_files=len(manifest),limitations='historical model verification only; not fills or independent OOS')
    b.js('final_validation.json',result);b.save('independent_account_checks.csv',summaries)
    b.js('verification_manifest.json',dict(files={str(p):b.sha(p) for p in [R/'final_validation.json',R/'independent_account_checks.csv',R/'fine_execution_summary.csv']}))
    print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':run()
