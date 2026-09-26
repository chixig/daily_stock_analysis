#!/usr/bin/env python3
"""Clearly labelled, bounded post-hoc champions; no rewrite of frozen discovery."""
import os,json,traceback
import pandas as pd,numpy as np
import foxconn_b18 as b
R=b.R

def run():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    original=json.loads((R/'manifest.json').read_text())['files']
    for p,h in original.items():assert b.sha(p)==h,p
    d=pd.read_csv(b.P/'daily_ledger.csv',parse_dates=['date','exit_date']);signals=pd.read_csv(R/'signals.csv')
    champions=pd.read_csv(R/'descriptive_grid_winners_NOT_validation.csv');champions=champions[(champions.period=='main')&champions.bp.eq(5)]
    grid=pd.read_csv(R/'all_experiments.csv');common=json.loads((R/'common_resources.json').read_text());q=common['shares']
    jobs=[]
    for _,a in champions.iterrows():jobs.append(dict(rule=a.rule,path=a.path,category=a.category,status='posthoc_full_history_discovery_NOT_OOS'))
    jobs += [{**a,'path':'open','category':a['category']+'_open_control'} for a in jobs.copy()]
    rows=[];periods=[];funds=[];quality=[];concentration=[];fine_out=[];paired=[];bridge=[];fine_replay=[]
    events=json.loads((b.b16.R/'verified_events.json').read_text());schedule=b.b16.schedule_for(d,events,0)
    au=pd.read_csv(R/'quality_annotations_only.csv',parse_dates=['date']).set_index('date').strict
    fine=pd.read_csv(b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);fine['clock']=fine.datetime.dt.strftime('%H:%M');fl=fine.set_index(['date','clock'])
    fine_days={};ds=d.set_index('date')
    for day,g in fine.groupby('date'):
        g=g.sort_values('clock').copy()
        if day not in ds.index or len(g)!=240:continue
        rr=ds.loc[day]
        if max(abs(g.open.iloc[0]-rr.open),abs(g.close.iloc[-1]-rr.close),abs(g.high.max()-rr.high),abs(g.low.min()-rr.low))>=.011:continue
        g['block']=np.arange(240)//5
        agg=g.groupby('block').agg(open=('open','first'),close=('close','last'),high=('high','max'),low=('low','min'),volume=('volume','sum'),clock=('clock','last'))
        fine_days[day]=agg.set_index('clock').to_dict('index')
    specmap={x['path']:x for x in b.path_specs()}
    for no,a in enumerate(jobs):
        key=f'H{no:02d}';path=pd.read_csv(R/f'paths_{a["path"]}.csv',parse_dates=['entry','exit']).set_index('entry_i',drop=False)
        mask=signals[a['rule']].astype('boolean');t,need,reasons=b.make_plan(d,mask,path);assert need<=q
        b.save('posthoc_participation_'+key+'.csv',reasons)
        for bp in [5,11,20]:
            z,o,tt,ff,s=b.b17.account(d,t,q,bp/10000,schedule);b.b17.verify(d,z,o,q,bp/10000,0.,schedule)
            tag=f'{key}_{bp}';b.save('posthoc_account_'+tag+'.csv',z);b.save('posthoc_orders_'+tag+'.csv',o);b.save('posthoc_trades_'+tag+'.csv',tt);b.save('posthoc_funds_'+tag+'.csv',ff)
            done=tt[tt.exit_i.notna()];met=b.stats(done.cash_increment,done.net_pct)
            rows.append(dict(candidate=key,**a,**s,**{'trade_'+k:v for k,v in met.items()},minimum_old_shares=need,missing_windows=int(t.missing_windows.sum()),delayed=int(t.delayed.sum())))
            windows={'discovery':done.entry.lt('2024-01-01'),'later':done.entry.ge('2024-01-01'),'main':pd.Series(True,index=done.index)};windows.update({str(y):done.entry.dt.year.eq(y) for y in range(2020,2027)})
            for period,sel in windows.items():
                g=done[sel];ci=b.bootstrap(g.entry,g.cash_increment) if period in ['main','discovery','later'] else [None,None]
                periods.append(dict(candidate=key,bp=bp,period=period,**b.stats(g.cash_increment,g.net_pct),ci_low=ci[0],ci_high=ci[1]))
            funds.append(dict(candidate=key,bp=bp,deposits=s['deposits'],single_max=s['single_max'],single_p95=s['single_p95'],peak_requirement=s['peak_requirement'],longest_deficit_days=s['longest_relative_deficit_calendar_days'],minimum_old_shares=need))
            if bp==5:
                strict=done.entry.map(au).fillna(False)&done.exit.map(au).fillna(False)
                for label,g in [('both_days_strict',done[strict]),('other_or_unknown',done[~strict])]:quality.append(dict(candidate=key,quality=label,**b.stats(g.cash_increment)))
                ev=done.copy();ev['event']=ev.entry_i.diff().gt(5).cumsum();ev=ev.groupby('event').agg(cash=('cash_increment','sum'),n=('entry_i','size'),start=('entry','min'),end=('entry','max'));b.save('posthoc_events_'+key+'.csv',ev.reset_index());sv=ev.cash.sort_values()
                concentration.append(dict(candidate=key,events=len(ev),cash=met['cash'],without_best_event=met['cash']-sv.iloc[-1],without_worst_event=met['cash']-sv.iloc[0],without_best3_trades=met['cash']-met['top3'],without_worst3_trades=met['cash']-met['bottom3']))
                for _,order in o[o.side.eq('BUY')&o.clock.ne('09:25')].iterrows():
                    hit=(order.date,b.minutes_after(order.clock,1));fp=float(fl.loc[hit,'open']) if hit in fl.index else np.nan
                    fine_out.append(dict(candidate=key,date=order.date,clock=order.clock,five_ref=order.reference,one_ref=fp,difference=order.reference-fp if np.isfinite(fp) else np.nan,covered=np.isfinite(fp)))
                op_path=pd.read_csv(R/'paths_open.csv',parse_dates=['entry','exit']).set_index('entry_i',drop=False)
                oo=b.opportunity(d,op_path,5).loc[t.entry_i.astype(int)];this=b.opportunity(d,path,5).loc[t.entry_i.astype(int)]
                paired.append(dict(candidate=key,**b.stats(this.cash.to_numpy()-oo.cash.to_numpy()),scope='same actual sale dates, independent opportunities before FIFO tax'))
                # Replay the ORIGINAL five-minute decision cadence using qualified one-minute-aggregated bars.
                for _,tr in t.iterrows():
                    ni=int(tr.entry_i)+1;rr=d.iloc[ni]
                    if rr.date not in fine_days:continue
                    fill,issues,reason=b.first_buy(tr.sell_ref,rr,fine_days[rr.date],specmap[a['path']])
                    alternative=np.nan;extra=np.nan
                    if fill:
                        bv=1000*fill[1]*1.0005;sv=1000*tr.sell_ref*.9995
                        alternative=sv-b.old.sf(sv,tr.entry,True)-bv-b.old.sf(bv,rr.date)-1000*rr.dividend_today
                        extra=alternative-float(this.loc[int(tr.entry_i),'cash'])
                    fine_replay.append(dict(candidate=key,entry=tr.entry,expected_exit=rr.date,old_exit=tr.exit,old_clock=tr.buy_clock,new_clock=fill[0] if fill else None,old_price=tr.buy_ref,new_price=fill[1] if fill else np.nan,new_trigger=reason,old_cash=float(this.loc[int(tr.entry_i),'cash']),new_cash=alternative,change=extra,note='same decision cadence, qualified 1m aggregated; paired opportunities, not whole history account'))
                # Constant-holding nominal baseline versus FIFO account bridge.
                bridge.append(dict(candidate=key,nominal_cash=this.cash.sum(),trade_cash=done.cash_increment.sum(),missed_dividend=done.missed_dividend.sum(),fifo_tax=done.dividend_tax.sum(),terminal_reserve=s['terminal_tax_reserve'],account_increment=s['increment']))
            print('POSTHOC',key,bp,s['increment'],flush=True)
    b.save('posthoc_fine_path_replay.csv',fine_replay);b.save('posthoc_account_summary.csv',rows);b.save('posthoc_periods.csv',periods);b.save('posthoc_funding_summary.csv',funds);b.save('posthoc_quality_strata.csv',quality);b.save('posthoc_concentration.csv',concentration);b.save('posthoc_fine_execution.csv',fine_out);b.save('posthoc_paired_exit.csv',paired);b.save('posthoc_nominal_account_bridge.csv',bridge)
    # Nearby pre-existing variants; descriptive only, no new masks or parameter search.
    wanted=[]
    for rule in grid.rule.unique():
        if ('S1_clv_ge_0p8' in rule and '__AND__S1_vr_' in rule) or ('S1_r3_le_m4' in rule and 'S1_clv_ge_' in rule):wanted.append(rule)
    neigh=grid[grid.rule.isin(wanted)&grid.bp.eq(5)&grid.period.isin(['discovery','later','main'])];b.save('posthoc_existing_neighborhood.csv',neigh)
    # Compact key neighborhood: original exit for each family and the open benchmark.
    key_neigh=neigh[((neigh.rule.str.contains('vr_'))&neigh.path.isin(['open','fixed_1000','fixed_1030','fixed_1450']))|((~neigh.rule.str.contains('vr_'))&neigh.path.isin(['open','gap_low_target0.5']))]
    b.save('posthoc_key_neighborhood.csv',key_neigh)
    for p,h in original.items():assert b.sha(p)==h,p
    b.js('posthoc_validation.json',dict(status='PASS',accounts=len(rows),original_files_unchanged=len(original),selection='after full historical grid viewed; not OOS',checks=['all orders scalar independently verified using inherited b17.verify','common 3000 shares and fixed 1000 per order','no modification of original discovery shortlist','original output manifest unchanged']))
    b.js('posthoc_manifest.json',dict(files={str(p):b.sha(p) for p in sorted(R.glob('posthoc_*')) if p.is_file() and p.name not in ['posthoc_manifest.json','posthoc_calculation.log']}))
if __name__=='__main__':run()
