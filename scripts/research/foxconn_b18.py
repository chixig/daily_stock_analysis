#!/usr/bin/env python3
"""Bounded B18 discovery and chronological historical replication, GitHub only."""
import os,sys,json,hashlib,zipfile,math,traceback,itertools
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_overnight_sell_b15 as old
import foxconn_overnight_sell_b15_r1 as r1
import foxconn_b16_accounts as b16
import foxconn_b17 as b17
R=Path('research/foxconn_t0_20260926_b18'); P=r1.P
CHECK=[]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
    z=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x); z.to_csv(R/n,index=False); return z
def js(n,x): (R/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def check(s): CHECK.append(s); print('PASS',s,flush=True)

def signals(d,m,ix):
    f1,f2,_=old.features(d,m,ix)
    chain=(d.close/d.preclose).cumprod()
    f1['r20']=(100*(chain/chain.shift(20)-1)).shift()
    f1['market20']=(100*(ix/ix.shift(20)-1)).shift()
    specs={'clv':[('le',.2),('le',.3),('ge',.7),('ge',.8),('ge',.9)],'r3':[('le',-6),('le',-4),('le',-2),('ge',2),('ge',4),('ge',6)],'r20':[('le',-10),('le',0),('ge',0),('ge',10)],'vr':[('le',.8),('le',1),('ge',1.2),('ge',1.5)],'relative':[('ge',0),('lt',0)],'market20':[('ge',0),('lt',0)],'gapdays':[('ge',3)]}
    masks={'S0':pd.Series(True,index=d.index,dtype='boolean')}; meta=[dict(rule='S0',family='none',layer='daily',description='无条件')]
    for layer,f in [('S1',f1),('S2',f2)]:
        for col,pars in specs.items():
            if layer=='S2':
                if col not in ['clv','r3','vr']: continue
                pars=[(fn,v) for fn,v in pars if not (col=='clv' and v==.9) and not (col=='vr' and v==1)]
            for fn,v in pars:
                key=f'{layer}_{col}_{fn}_{str(v).replace("-","m").replace(".","p")}'
                masks[key]=getattr(f[col],fn)(v).astype('boolean').where(f[col].notna(),pd.NA)
                meta.append(dict(rule=key,family=col,layer='daily' if layer=='S1' else 'minute_unconfirmed',description=f'{layer} {col} {fn} {v}'))
    singles=meta[1:].copy()
    anchors=['S1_clv_ge_0p8','S1_clv_le_0p2','S1_r3_le_m4','S2_clv_le_0p2','S2_r3_le_m4']; seen=set()
    for a in anchors:
        af=next(x['family'] for x in singles if x['rule']==a)
        for b in singles:
            if b['family']==af: continue
            pair=tuple(sorted([a,b['rule']]))
            if pair in seen: continue
            seen.add(pair); key='__AND__'.join(pair); masks[key]=masks[pair[0]]&masks[pair[1]]
            meta.append(dict(rule=key,family=af+'+'+b['family'],layer='minute_unconfirmed' if any(x.startswith('S2') for x in pair) else 'daily',description=' AND '.join(pair)))
    assert len(masks)<=220,len(masks)
    return masks,pd.DataFrame(meta),pd.concat([f1.add_prefix('S1_'),f2.add_prefix('S2_')],axis=1)

def path_specs():
    out=[dict(path='open',kind='open')]
    out += [dict(path='fixed_'+s.replace(':',''),kind='fixed',deadline=s) for s in ['09:40','10:00','10:30','14:50']]
    for tp,st in itertools.product([.005,.01],[.01,.02]):out.append(dict(path=f'target{tp*100:g}_stop{st*100:g}',kind='target',tp=tp,stop=st,branch='none',deadline='10:30'))
    for tp in [.005,.01]:out.append(dict(path=f'gap_both_target{tp*100:g}',kind='target',tp=tp,stop=.01,branch='both',deadline='10:30'))
    for branch in ['high','low']:out.append(dict(path=f'gap_{branch}_target0.5',kind='target',tp=.005,stop=.01,branch=branch,deadline='10:30'))
    assert len(out)==13
    return out

def minutes_after(clock,minutes):return (pd.Timestamp('2000-01-01 '+clock)+pd.Timedelta(minutes=minutes)).strftime('%H:%M')
def lookup_days(m): return {day:g.set_index('clock').to_dict('index') for day,g in m.groupby('date')}
def valid(p,r):return np.isfinite(p) and p>=r.limit_down-.005 and p<r.limit_up-.005

def first_buy(sell,r,bars,spec):
    """At-clock decision only. Full-day QC is deliberately absent."""
    issues=[]
    def at(clock):
        end=minutes_after(clock,5); bar=bars.get(end)
        # The bar open is the start timestamp. Do not require its FUTURE volume/high.
        p=float(bar['open']) if bar else np.nan
        if not np.isfinite(p): issues.append('missing_'+clock)
        return (clock,p,'fixed_or_trigger_next_interval') if valid(p,r) else None
    if spec['kind']=='open':
        return (('09:25',float(r.open),'daily_open') if valid(float(r.open),r) else None),issues,'planned_open'
    if spec['kind']=='fixed':
        x=at(spec['deadline'])
        if x:return x,issues,'fixed'
    else:
        gap=r.open/sell-1; branch=spec['branch']
        immediate=(branch in ['both','high'] and gap>=.01) or (branch in ['both','low'] and gap<=-.005)
        if immediate:
            x=at('09:30')
            if x:return x,issues,'observed_gap_then_continuous_open'
        for clock in ['09:35','09:40','09:45','09:50','09:55','10:00','10:05','10:10','10:15','10:20']:
            bar=bars.get(clock)
            if bar is None:issues.append('missing_observation_'+clock);continue
            p=float(bar['close'])
            if p<=sell*(1-spec['tp']) or p>=sell*(1+spec['stop']):
                reason='target_close' if p<=sell*(1-spec['tp']) else 'stop_close'
                x=at(minutes_after(clock,5))
                if x:return x,issues,reason
        x=at('10:30')
        if x:return x,issues,'deadline'
    # No planned next-day window may be silently discarded.
    x=at('14:50')
    if x:return x,issues,'emergency_1450'
    return None,issues,'next_open_forced_retry'

def build_paths(d,m,spec):
    days=lookup_days(m); rows=[]; attempts=[]
    for i,r in d.iloc[:-1].iterrows():
        j=i+1; nxt=d.iloc[j]; x,issues,reason=first_buy(r.close,nxt,days.get(nxt.date,{}),spec)
        for iss in issues:attempts.append(dict(entry_i=i,date=nxt.date,reason=iss,path=spec['path']))
        if x is None:
            attempts.append(dict(entry_i=i,date=nxt.date,reason=reason,path=spec['path']))
            j+=1
            while j<len(d):
                a=d.iloc[j]
                if valid(float(a.open),a):x=('09:25',float(a.open),'forced_open_retry');break
                attempts.append(dict(entry_i=i,date=a.date,reason='retry_upper_limit_or_unknown',path=spec['path']));j+=1
        done=x is not None
        end=j if done else len(d)-1
        div=1000*d.loc[i+1:end,'dividend_today'].sum()
        rows.append(dict(entry_i=i,entry=r.date,sell_ref=float(r.close),exit_i=j if done else np.nan,exit=d.date.iloc[j] if done else pd.NaT,buy_ref=x[1] if done else np.nan,buy_clock=x[0] if done else None,kind=x[2] if done else 'unresolved',trigger=reason,missing_windows=len(issues),delayed=bool(done and j>i+1),missed_dividend=div,terminal_mark=float(d.close.iloc[-1]),path=spec['path']))
    return pd.DataFrame(rows).set_index('entry_i',drop=False),pd.DataFrame(attempts)

def opportunity(d,t,bp):
    slip=bp/10000;z=t.copy();sv=1000*z.sell_ref*(1-slip)
    buy=z.buy_ref.fillna(z.terminal_mark);bv=1000*buy*(1+slip)
    buydate=z.exit.fillna(d.date.iloc[-1]); fees=old.fee(sv,z.entry,True)+old.fee(bv,buydate)
    z['cash']=sv-bv-fees-z.missed_dividend;z['net']=100*z.cash/(1000*z.sell_ref)
    z['sale_allowed']=(d.loc[z.index,'close']>d.loc[z.index,'limit_down']+.005)&d.loc[z.index,'volume'].gt(0)
    return z

def stats(x,returns=None):
    a=np.asarray(x,float); n=len(a)
    if not n:return dict(n=0,wins=0,win=np.nan,cash=0.,mean=np.nan,worst=np.nan,mdd=0.,top3=0.,bottom3=0.)
    equity=np.r_[0,np.cumsum(a)]; s=np.sort(a)
    return dict(n=n,wins=int((a>0).sum()),win=100*(a>0).mean(),cash=float(a.sum()),mean=float(a.mean()),worst=float(a.min()),mdd=float((equity-np.maximum.accumulate(equity)).min()),top3=float(s[-3:].sum()),bottom3=float(s[:3].sum()),mean_pct=float(np.mean(returns)) if returns is not None else np.nan)

def make_plan(d,mask,paths,capacity=None):
    pending=[];trades=[];needs=[];reasons=[]
    for i,r in d[d.date.ge('2020-01-01')].iterrows():
        bought=0
        for t in list(pending):
            if pd.notna(t['exit_i']) and int(t['exit_i'])==i:pending.remove(t);bought+=1
        s=mask.iloc[i]
        if pd.isna(s):reason='unknown_signal'
        elif not s:reason='no_signal'
        elif i==len(d)-1:reason='terminal_no_next_day'
        elif r.close<=r.limit_down+.005 or r.volume<=0:reason='blocked_sale'
        elif capacity is not None and len(pending)+bought>=capacity:reason='inventory_participation'
        else:
            t=paths.loc[i].to_dict();trades.append(t);pending.append(t);needs.append((len(pending)+bought)*1000);reason='sold_1000'
        reasons.append(dict(date=r.date,reason=reason))
    cols=['entry_i','entry','sell_ref','exit_i','exit','buy_ref','buy_clock','kind','trigger','missing_windows','delayed']
    return pd.DataFrame(trades,columns=cols),max(needs,default=1000),pd.DataFrame(reasons)

def bootstrap(entries,cash):
    x=pd.DataFrame({'month':pd.to_datetime(entries).dt.to_period('M'),'cash':np.asarray(cash)}).groupby('month').cash.sum().to_numpy()
    if not len(x):return [None,None]
    rng=np.random.default_rng(601138);v=x[rng.integers(0,len(x),(2000,len(x)))].sum(axis=1)
    return np.quantile(v,[.025,.975]).tolist()

def run():
    assert os.environ.get('GITHUB_ACTIONS')=='true','Market computation is remote-only'
    R.mkdir(parents=True,exist_ok=True)
    parents={}
    for folder in [P,P/'revision_r1',b16.R,Path('research/foxconn_t0_20260923_b17')]:parents.update(json.loads((folder/'manifest.json').read_text())['files'])
    for p,h in parents.items():assert sha(p)==h,p
    check(f'parent {len(parents)} hashes before')
    d=pd.read_csv(P/'daily_ledger.csv',parse_dates=['date','exit_date'])
    with zipfile.ZipFile(old.P/'source/601138-full-5min-history.zip') as z:m=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('601138_5min_all.csv'))))
    m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
    ixraw=pd.read_csv(old.B2/'source/sse_index.csv',parse_dates=['date']).set_index('date').close;ix=d.date.map(ixraw)
    masks,registry,f=signals(d,m,ix);save('rules.csv',registry);save('features.csv',pd.concat([d.date,f],axis=1));save('signals.csv',pd.DataFrame({'date':d.date,**masks}))
    basekey='S1_clv_ge_0p8';sig=pd.read_csv(P/'signals.csv');pd.testing.assert_series_equal(masks[basekey],sig.S1_F1.astype('boolean'),check_names=False)
    for cut in [500,1000,1600]:
        mm,_,ff=signals(d.iloc[:cut+1],m[m.date.le(d.date.iloc[cut])],ix.iloc[:cut+1]);pd.testing.assert_frame_equal(ff,f.iloc[:cut+1])
        for k in mm:pd.testing.assert_series_equal(mm[k],masks[k].iloc[:cut+1])
    dd=d.copy(); future=dd.date.ge('2024-01-01');dd.loc[future,['open','high','low','close','volume']]*=1.37
    mm,_,_=signals(dd,m,ix)
    for k in mm:pd.testing.assert_series_equal(mm[k][~future],masks[k][~future])
    check('baseline signal, prefix and future perturbation')
    specs=path_specs();save('exit_rules.csv',specs);paths={};opps={}; attempts=[]
    for spec in specs:
        name=spec['path']; t,a=build_paths(d,m,spec);paths[name]=t;attempts.append(a);save('paths_'+name+'.csv',t)
        opps[(name,5)]=opportunity(d,t,5);opps[(name,11)]=opportunity(d,t,11)
    save('failed_and_missing_attempts.csv',pd.concat(attempts,ignore_index=True))
    # Prefix of all completed paths is invariant when future rows/bars are removed.
    cut=1300
    for spec in specs:
        p,_=build_paths(d.iloc[:cut+1],m[m.date.le(d.date.iloc[cut])],spec);full=paths[spec['path']];ixc=p.index[p.exit_i.notna()]
        pd.testing.assert_frame_equal(p.loc[ixc,['exit_i','buy_ref','buy_clock']],full.loc[ixc,['exit_i','buy_ref','buy_clock']],check_dtype=False)
    check('all 13 execution paths prefix invariant; no QC gates')
    au=r1.audit(d,m);save('quality_annotations_only.csv',au)
    windows={'discovery':d.date.between('2020-01-01','2023-12-31'),'later':d.date.ge('2024-01-01'),'main':d.date.ge('2020-01-01')}
    windows.update({str(y):d.date.dt.year.eq(y) for y in range(2020,2027)})
    rows=[]
    for k,mask in masks.items():
        ids=mask.fillna(False)
        for spec in specs:
            name=spec['path']
            for bp in [5,11]:
                z=opps[(name,bp)];active=ids.reindex(z.index).fillna(False)&z.sale_allowed
                for period,w in windows.items():
                    g=z[active&w.reindex(z.index).fillna(False)]
                    if period=='discovery':g=g[g.exit.notna()&g.exit.le('2023-12-31')]
                    rows.append(dict(rule=k,path=name,bp=bp,period=period,**stats(g.cash,g.net),delayed=int(g.delayed.sum()),missing_windows=int(g.missing_windows.sum()),unfinished=int(g.exit_i.isna().sum()),unknown_signal=int((mask.isna()&w).sum())))
    grid=save('all_experiments.csv',rows);print('GRID',len(masks),len(grid),flush=True)
    discovery=grid[(grid.period=='discovery')&grid.n.ge(40)].merge(registry[['rule','layer']],on='rule')
    selected=[]
    def add(df,col,n,reason):
        for _,x in df.sort_values([col,'cash','rule','path'],ascending=[False,False,True,True]).head(n).iterrows():
            key=(x.rule,x.path)
            if key not in [(a['rule'],a['path']) for a in selected]:selected.append(dict(rule=x.rule,path=x.path,selection=reason))
    add(discovery[discovery.bp.eq(5)],'cash',2,'discovery_cash')
    add(discovery[discovery.bp.eq(5)&discovery.cash.gt(0)],'win',2,'discovery_win_positive_cash')
    add(discovery[discovery.bp.eq(11)],'cash',2,'discovery_stress_cash')
    for layer in ['daily','minute_unconfirmed']:add(discovery[discovery.bp.eq(5)&discovery.layer.eq(layer)],'cash',1,'discovery_layer_'+layer)
    assert len(selected)<=8
    selected+=[dict(rule=basekey,path='open',selection='baseline'),dict(rule='S0',path='open',selection='baseline')]
    selected=list({(x['rule'],x['path']):x for x in selected}.values())
    save('selected_before_later_account_review.csv',selected)
    # Selection predicates above never read later rows. Save diagnostic historical winners separately.
    winners=[]
    for period in ['discovery','later','main']:
        h=grid[(grid.period==period)&grid.bp.eq(5)&grid.n.ge(40)]
        for col in ['cash','win']:
            g=h if col=='cash' else h[h.cash.gt(0)]
            if len(g):winners.append(dict(category=col,**g.sort_values([col,'cash'],ascending=False).iloc[0].to_dict()))
    save('descriptive_grid_winners_NOT_validation.csv',winners)
    jobs=[]
    for a in selected:
        t,need,reasons=make_plan(d,masks[a['rule']],paths[a['path']]);jobs.append((a,t,need,reasons))
    a=dict(rule=basekey,path='open',selection='baseline_single_batch',policy='no_resell_buy_day')
    t,need,reasons=make_plan(d,masks[basekey],paths['open'],1);jobs.append((a,t,need,reasons))
    q=max([3000]+[x[2] for x in jobs]);js('common_resources.json',dict(shares=q,per_trade=1000,cash='externally supplemented, identical hold flows',maximum_required=max(x[2] for x in jobs)))
    events=json.loads((b16.R/'verified_events.json').read_text());schedule=b16.schedule_for(d,events,0)
    # Reproduce B17 exactly before relying on account machinery.
    _,_,op,post=r1.pipeline(d,m);tt,_,_,_=b17.plan(d,masks[basekey],op,post,'open',1)
    z,o,ledger,ff,summary=b17.account(d,tt,1000,.0005,schedule);b17.verify(d,z,o,1000,.0005,0.,schedule)
    assert summary['completed']==286 and abs(summary['increment']-11271.41)<.01,summary
    save('b17_bridge.csv',[summary]);check('B17 286 trades +11271.41 reproduced')
    acc=[];periods=[];qualities=[];paired=[];concentration=[];funding=[]
    for no,(a,t,need,reasons) in enumerate(jobs):
        key=f'C{no:02d}'; a={**a,'candidate':key,'minimum_old_shares':need};save('participation_'+key+'.csv',reasons)
        for bp in [5,11,20]:
            print('ACCOUNT',key,bp,a['rule'],a['path'],flush=True)
            z,o,tt,ff,s=b17.account(d,t,q,bp/10000,schedule);b17.verify(d,z,o,q,bp/10000,0.,schedule)
            tag=f'{key}_{bp}';save('account_'+tag+'.csv',z);save('orders_'+tag+'.csv',o);save('trades_'+tag+'.csv',tt);save('funds_'+tag+'.csv',ff)
            done=tt[tt.exit_i.notna()];met=stats(done.cash_increment,done.net_pct)
            acc.append(dict(**a,**s,**{('trade_'+k):v for k,v in met.items()},missing_windows=int(t.missing_windows.sum()),delayed=int(t.delayed.sum())))
            for name,w in windows.items():
                g=done[done.entry_i.astype(int).map(w).fillna(False)];ci=bootstrap(g.entry,g.cash_increment) if name in ['discovery','later','main'] else [None,None]
                periods.append(dict(candidate=key,bp=bp,period=name,**stats(g.cash_increment,g.net_pct),ci_low=ci[0],ci_high=ci[1]))
            if bp==5:
                # Same actual sales, each repurchase policy compared with open; not a second executable account.
                oo=opps[('open',5)].loc[t.entry_i.astype(int)];this=opps[(a['path'],5)].loc[t.entry_i.astype(int)]
                paired.append(dict(candidate=key,**stats(this.cash.to_numpy()-oo.cash.to_numpy()),note='paired opportunity cash before FIFO tax; same sale dates'))
                strict=au.set_index('date').strict
                good=done.entry.map(strict).fillna(False)&done.exit.map(strict).fillna(False)
                for label,g in [('both_days_strict',done[good]),('other_or_unknown',done[~good])]:qualities.append(dict(candidate=key,quality=label,**stats(g.cash_increment)))
                # Event concentration: groups of actual entries separated by at most 5 trading days.
                g=done.copy();g['event']=g.entry_i.diff().gt(5).cumsum();ev=g.groupby('event').agg(cash=('cash_increment','sum'),n=('entry_i','size'),start=('entry','min'),end=('entry','max'))
                save('events_'+key+'.csv',ev.reset_index());sv=ev.cash.sort_values()
                concentration.append(dict(candidate=key,events=len(ev),cash=sv.sum(),without_best_event=sv.sum()-sv.iloc[-1],without_worst_event=sv.sum()-sv.iloc[0],without_best3_trades=met['cash']-met['top3'],without_worst3_trades=met['cash']-met['bottom3']))
            funding.append(dict(candidate=key,bp=bp,deposits=s['deposits'],single_max=s['single_max'],single_p95=s['single_p95'],peak_requirement=s['peak_requirement'],longest_deficit_days=s['longest_relative_deficit_calendar_days'],minimum_old_shares=need))
    save('account_summary.csv',acc);save('periods.csv',periods);save('paired_exit_improvement.csv',paired);save('quality_strata.csv',qualities);save('concentration.csv',concentration);save('funding_summary.csv',funding)
    # Negative sell/open rule regions, independently costed opposite direction, no strategy switch.
    mirrors=[]
    for k,mask in masks.items():
        g=d[d.date.ge('2020-01-01')&d.exit_date.notna()&mask.fillna(False)]
        if len(g):
            a=old.ledger(g);b=old.ledger(g,reverse=True)
            if a.cash.sum()<0:mirrors.append(dict(rule=k,n=len(g),original_cash=a.cash.sum(),opposite_cash=b.cash.sum(),opposite_mean=b.net.mean(),note='nominal same dates only; not account or adopted strategy'))
    save('negative_region_mirrors.csv',mirrors)
    # Available one-minute corroboration of actually selected five-minute start prices.
    fine=pd.read_csv(r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);fine['clock']=fine.datetime.dt.strftime('%H:%M')
    flookup=fine.set_index(['date','clock']);evidence=[]
    for a in acc:
        if a['slip_bp']!=5:continue
        key=a['candidate'];o=pd.read_csv(R/f'orders_{key}_5.csv',parse_dates=['date'])
        for _,order in o[o.side.eq('BUY')&o.clock.ne('09:25')].iterrows():
            # 1m timestamps are bar ends; open at 09:40 is row ending 09:41.
            hit=(order.date,minutes_after(order.clock,1))
            fp=float(flookup.loc[hit,'open']) if hit in flookup.index else np.nan
            evidence.append(dict(candidate=key,date=order.date,clock=order.clock,five_ref=order.reference,one_ref=fp,difference=order.reference-fp if np.isfinite(fp) else np.nan,covered=np.isfinite(fp)))
    save('fine_execution_comparison.csv',evidence)
    for p,h in parents.items():assert sha(p)==h,p
    check('all parent hashes unchanged; all selected accounts scalar verified')
    js('validation.json',dict(status='PASS',checks=CHECK,rules=len(masks),paths=len(specs),grid_rows=len(grid),selected=len(jobs),accounts=len(acc),parent_files=len(parents),market_cutoff=str(d.date.max().date()),limitations=['already viewed historical later period','five-minute source discrepancies','no queue or actual execution proof','missing intraday windows retain fallback and flags']))
    js('manifest.json',dict(files={str(p):sha(p) for p in sorted(R.rglob('*')) if p.is_file() and p.name not in ['manifest.json','calculation.log']}))
    print('COMPLETE',json.dumps(dict(rules=len(masks),accounts=len(acc),q=q)),flush=True)
if __name__=='__main__':
    try:run()
    except Exception:
        R.mkdir(parents=True,exist_ok=True);js('failure.json',dict(traceback=traceback.format_exc(),checks=CHECK));raise
