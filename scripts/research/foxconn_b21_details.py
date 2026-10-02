"""Read-only decision summaries from frozen B21 research outputs."""
import os,json
import numpy as np
import pandas as pd
import foxconn_b21 as q
R=q.R
def run():
    protected={}
    for name in ['manifest.json','verification_manifest.json']:
        protected.update(json.loads((R/name).read_text())['files'])
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())['files']
    for p,h in {**protected,**frozen}.items():assert q.b.sha(p)==h,p
    s=pd.read_csv(R/'comparison.csv');leaders=pd.read_csv(R/'leaders.csv');main=s[s.bp.eq(5)].set_index('id');reg={r['id']:r for r in q.registry()}
    top=list(dict.fromkeys(leaders.id));focus=list(dict.fromkeys(top+[q.BASE,q.ALT,'Q2010','Q0010','Q1110','Q1100','Q1111','CTRL_OPEN','CTRL_OLD','CTRL_W0','CTRL_W1']))
    det=pd.read_csv(R/'attribution_trades.csv');edge=pd.read_csv(R/'single_action_edges.csv');fine=pd.read_csv(R/'fine_paired_attribution.csv');replay=pd.read_csv(R/'fine_path_replay.csv')
    d,_,_,oldspecs,_,_=q.y.load();changes=[];low=[];support=[]
    replay=extend_replay(d,q.specs()|oldspecs,replay,set(focus)-set(replay.id))
    q.save('diagnostic_fine_replay.csv',replay)
    new=replay[['id','entry','path_replayed','price_difference']].rename(columns={'path_replayed':'new_path_supported','price_difference':'new_price_difference'})
    old=replay[['id','entry','path_replayed','price_difference']].rename(columns={'id':'baseline','path_replayed':'old_path_supported','price_difference':'old_price_difference'})
    fine=det[det.id.isin(focus)].merge(new,on=['id','entry'],how='left').merge(old,on=['baseline','entry'],how='left')
    fine['both_supported']=fine.new_path_supported.fillna(False)&fine.old_path_supported.fillna(False)
    q.save('diagnostic_paired_fine.csv',fine)
    for key in focus:
        t=q.read_trade(key)
        for tr in t.itertuples():
            if tr.family!='B':continue
            gap=d.open.iloc[int(tr.entry_i)+1]/tr.sell_ref-1
            low.append(dict(id=key,entry=tr.entry,gap=gap,low_open=gap<=-.005,trigger=tr.trigger,clock=tr.buy_clock,buy_price=tr.buy_ref,cash=tr.cash_increment,net_pct=tr.net_pct))
        for baseline in [q.BASE,q.ALT]:
            ff=fine[fine.id.eq(key)&fine.baseline.eq(baseline)].copy()
            if not len(ff):continue
            ff['changed']=ff.change.abs().gt(.00001)
            for family in ['A','B']:
                v=ff[ff.family.eq(family)&ff.changed]
                support.append(dict(id=key,baseline=baseline,family=family,changed=len(v),both_supported=int(v.both_supported.sum()),new_supported=int(v.new_path_supported.sum()),old_supported=int(v.old_path_supported.sum()),positive_supported=int((v.both_supported&v.change.gt(0)).sum()),negative_supported=int((v.both_supported&v.change.lt(0)).sum()),supported_change=v.loc[v.both_supported,'change'].sum(),unsupported_change=v.loc[~v.both_supported,'change'].sum()))
    low=pd.DataFrame(low);q.save('low_open_trades.csv',low)
    low_summary=low.groupby(['id','low_open']).agg(n=('cash','size'),wins=('cash',lambda v:(v>0).sum()),cash=('cash','sum'),mean_net_pct=('net_pct','mean')).reset_index();q.save('low_open_subgroups.csv',low_summary)
    q.save('fine_changed_coverage.csv',support)
    neighbor_summary=[]
    for dim,g in edge[edge.bp.eq(5)].groupby('dimension'):
        # Direction labels prevent interpreting the reverse edge as a new comparison.
        for (a,b),sub in g.groupby([g.from_id.map(lambda k:str(reg[k][dim])),g.to_id.map(lambda k:str(reg[k][dim]))]):
            neighbor_summary.append(dict(dimension=dim,from_value=a,to_value=b,pairs=len(sub),better=int(sub.net_change.gt(.00001).sum()),worse=int(sub.net_change.lt(-.00001).sum()),equal=int(sub.net_change.abs().le(.00001).sum()),min_change=sub.net_change.min(),max_change=sub.net_change.max()))
    q.save('neighbor_summary.csv',neighbor_summary)
    pairs=[(q.BASE,'Q2010'),(q.BASE,'Q0010'),(q.BASE,'Q1110'),(q.ALT,'Q1100'),(q.BASE,'Q1011'),(q.ALT,'Q1001'),('Q1110','Q1111')]
    pairrows=[];pairsummary=[];ri=replay.set_index(['id','entry'])
    for before,after in pairs:
        tt=q.read_trade(after).set_index('entry_i');rr=q.read_trade(before).set_index('entry_i');delta=tt.cash_increment-rr.cash_increment
        edge_row=edge[edge.from_id.eq(before)&edge.to_id.eq(after)&edge.bp.eq(5)].iloc[0].to_dict();pairsummary.append(edge_row)
        changed=(tt.buy_clock!=rr.buy_clock)|(tt.buy_ref-rr.buy_ref).abs().gt(.00001)
        for i in tt.index[changed]:
            a=tt.loc[i];b=rr.loc[i];date=a.entry.strftime('%Y-%m-%d');ar=ri.loc[(after,date)];br=ri.loc[(before,date)]
            pairrows.append(dict(before=before,after=after,entry=date,exit=a.exit,family=a.family,new_trigger=a.trigger,old_trigger=b.trigger,new_clock=a.buy_clock,old_clock=b.buy_clock,new_price=a.buy_ref,old_price=b.buy_ref,new_net=a.cash_increment,old_net=b.cash_increment,change=delta.loc[i],loss_to_win=bool(a.cash_increment>0 and b.cash_increment<=0),win_to_loss=bool(a.cash_increment<=0 and b.cash_increment>0),new_supported=bool(ar.path_replayed),old_supported=bool(br.path_replayed),both_supported=bool(ar.path_replayed and br.path_replayed),new_price_difference=ar.price_difference,old_price_difference=br.price_difference))
    q.save('action_pair_summary.csv',pairsummary);q.save('action_pair_dates.csv',pairrows)
    blocks=['# B21决策细表','仅整理冻结结果，不新增候选，不改会计或排名。']
    def add(title,f):blocks.extend(['## '+title,f.to_markdown(index=False,floatfmt='.6f') if len(f) else '无记录'])
    cols=['id','bp','completed','trade_wins','trade_win','increment','delta_'+q.BASE,'delta_'+q.ALT,'average_profit','average_loss','trade_worst','relative_mdd','pending','terminal_tax_reserve','trade_mean_net_pct']
    cols=[c for c in cols if c in s]
    add('重点账户',s[s.id.isin(focus)][cols]);add('排名',leaders)
    for name in ['periods','yearly_trades','annual_equity_changes','family_groups','attribution','family_interactions']:
        f=pd.read_csv(R/(name+'.csv'));add(name,f[f.id.isin(focus)&f.bp.eq(5)])
    add('集中度',pd.read_csv(R/'concentration.csv'));add('低开子组',low_summary);add('邻近动作整体',pd.DataFrame(neighbor_summary))
    add('领先规则邻居',edge[edge.from_id.isin(top)&edge.bp.eq(5)])
    add('改变交易的细路径覆盖',pd.DataFrame(support))
    fs=replay.groupby(['id','family']).agg(n=('entry','size'),replayed=('path_replayed','sum'),clock_match=('clock_match','sum'),trigger_match=('trigger_match','sum'),min_price_difference=('price_difference','min'),max_price_difference=('price_difference','max')).reset_index();q.save('fine_replay_summary.csv',fs);add('细路径一致性',fs)
    keys=pd.read_csv(R/'key_gain_loss_dates.csv')
    keys=keys.merge(fine[['id','baseline','entry','both_supported','new_price_difference','old_price_difference']],on=['id','baseline','entry'],how='left');q.save('key_dates_with_coverage.csv',keys)
    add('关键正反例',keys[keys.id.isin(top)&keys.baseline.eq(q.BASE)])
    add('单动作问题汇总',pd.DataFrame(pairsummary))
    pp=pd.DataFrame(pairrows);examples=[]
    for _,g in pp.groupby(['before','after']):
        examples.extend(g.sort_values('change').head(3).to_dict('records'));examples.extend(g.sort_values('change',ascending=False).head(3).to_dict('records'))
    q.save('action_pair_examples.csv',examples);add('单动作正反例',pd.DataFrame(examples))
    add('资源',s[s.id.isin(focus)&s.bp.eq(5)][['id','deposits','peak_requirement','max_single_deposit','max_buy_cash','single_max','minimum_old_shares_unconstrained','inventory_blocked','max_wait_calendar_days','longest_relative_deficit_calendar_days','deposit_yuan_days']])
    neg=pd.read_csv(R/'opposite_direction_regions.csv');add('反向诊断',neg[neg.id.isin(focus)])
    (R/'DECISION_DETAILS.md').write_text('\n\n'.join(blocks)+'\n')
    q.js('decision_details.json',dict(focus=focus,main=s[s.bp.eq(5)].to_dict('records'),leaders=leaders.to_dict('records'),neighbor=neighbor_summary,changed_coverage=support,replay=fs.to_dict('records')))
    for p,h in {**protected,**frozen}.items():assert q.b.sha(p)==h,p
    q.js('details_validation.json',dict(status='PASS',protected_results=len(protected),parent_files=len(frozen),new_candidates=0,full_accounts_unchanged=True))
    q.js('details_manifest.json',dict(files={str(p):q.b.sha(p) for p in R.rglob('*') if p.is_file() and str(p) not in protected and p.name not in ['manifest.json','verification_manifest.json','details_manifest.json','calculation.log','verification.log','details.log','failure.json']}))
def extend_replay(d,specs,replay,keys):
    raw=pd.read_csv(q.b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);raw['clock']=raw.datetime.dt.strftime('%H:%M');ds=d.set_index('date');days={}
    expected=[q.b.minutes_after(start,k) for start in q.x.STARTS for k in range(1,6)]
    for day,g in raw.groupby('date'):
        g=g.sort_values('clock').copy()
        if day not in ds.index or list(g.clock)!=expected:continue
        rr=ds.loc[day]
        if max(abs(g.open.iloc[0]-rr.open),abs(g.close.iloc[-1]-rr.close),abs(g.high.max()-rr.high),abs(g.low.min()-rr.low))>=.011:continue
        if not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))&(g.volume>=0)).all():continue
        g['block']=np.arange(240)//5;days[day]=g.groupby('block').agg(open=('open','first'),close=('close','last'),clock=('clock','last')).set_index('clock').to_dict('index')
    assert len(days)==json.loads((R/'fine_quality.json').read_text())['qualified_days']
    records=[]
    for key in sorted(keys):
        for tr in q.read_trade(key).itertuples():
            rr=d.iloc[int(tr.entry_i)+1];available=rr.date in days;fill=None;reason=None
            if available:fill,_,reason=q.x.first_buy(tr.sell_ref,rr,days[rr.date],specs[tr.selected_rule])
            supported=bool(available and fill is not None and tr.exit==rr.date)
            records.append(dict(id=key,entry=tr.entry.strftime('%Y-%m-%d'),entry_i=tr.entry_i,family=tr.family,selected_rule=tr.selected_rule,trigger=tr.trigger,old_clock=tr.buy_clock,old_price=tr.buy_ref,day_available=available,path_replayed=supported,new_clock=fill[0] if fill else None,new_price=fill[1] if fill else np.nan,new_trigger=reason,clock_match=bool(supported and fill[0]==tr.buy_clock),trigger_match=bool(supported and reason==tr.trigger),price_difference=fill[1]-tr.buy_ref if supported else np.nan))
    return pd.concat([replay,pd.DataFrame(records)],ignore_index=True)
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true';run()
