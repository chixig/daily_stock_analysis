"""B20 decision-focused tables, derived remotely from already verified accounts."""
import os,json
import numpy as np
import pandas as pd
import foxconn_b20 as y
R=y.R;b=y.b
assert os.environ.get('GITHUB_ACTIONS')=='true'
protected={}
for name in ['manifest.json','verification_manifest.json']:
    protected.update(json.loads((R/name).read_text())['files'])
for p,h in protected.items():assert b.sha(p)==h,p
s=pd.read_csv(R/'comparison.csv');reg=json.loads((R/'registry.json').read_text())
periods=pd.read_csv(R/'periods.csv');yearly=pd.read_csv(R/'yearly_trades.csv');equity=pd.read_csv(R/'annual_equity_changes.csv')
det=pd.read_csv(R/'attribution_trades.csv',parse_dates=['entry']);fine=pd.read_csv(R/'leader_fine_coverage.csv',parse_dates=['entry'])
parent_fine=pd.read_csv(y.x.R/'fine_path_replay.csv',parse_dates=['entry']).set_index(['id','entry'])
keys=['C00B','C12A','C11A','W0022'];blocks=['# B20决策补充表（模型事实）']
def add(title,f):blocks.extend(['## '+title,f.to_markdown(index=False,floatfmt='.4f') if len(f) else '无记录'])
add('四个选择三档成本',s[s.id.isin(keys)][['id','bp','completed','trade_wins','trade_win','increment','delta_baseline','average_profit','average_loss','trade_worst','relative_mdd','terminal_tax_reserve','pending','deposits','max_buy_cash','single_max','max_single_deposit','minimum_old_shares_unconstrained']])
add('同期间分段',periods[periods.id.isin(keys)&periods.bp.eq(5)])
add('逐年损益',yearly[yearly.id.isin(keys)&yearly.bp.eq(5)])
add('连续账户年末权益',equity[equity.id.isin(keys)&equity.bp.eq(5)])
groups=pd.read_csv(R/'participation_groups.csv')
add('参与分组',groups[groups.id.isin(keys)&groups.bp.eq(5)])
top=list(dict.fromkeys(pd.read_csv(R/'leaders.csv').id))
summ=[];changed=[];pairs=[];overlap=[];tails=[]
for key in top:
    dd=det[det.id.eq(key)&det.bp.eq(5)]
    actual=pd.read_csv(R/f'trades/{key}_5.csv',parse_dates=['entry','exit']).set_index('entry')
    baseline=pd.read_csv(R/'trades/C00B_5.csv',parse_dates=['entry','exit']).set_index('entry')
    for (cat,effect),g in dd.groupby(['category','effect']):summ.append(dict(id=key,category=cat,effect=effect,n=len(g),new_net=g.new_net.sum(),old_net=g.old_net.sum(),change=g.change.sum()))
    for effect,g in dd.groupby('effect'):
        shared=g[g.entry.isin(actual.index)&g.entry.isin(baseline.index)]
        changed_fill=sum(actual.loc[date,'buy_clock']!=baseline.loc[date,'buy_clock'] or abs(actual.loc[date,'buy_ref']-baseline.loc[date,'buy_ref'])>1e-8 or actual.loc[date,'exit']!=baseline.loc[date,'exit'] for date in shared.entry)
        changed.append(dict(id=key,effect=effect,n=len(g),different_realized_fill=changed_fill,changed_price_or_amount=int(g.change.abs().gt(.00001).sum()),positive_change=g.change.clip(lower=0).sum(),negative_change=g.change.clip(upper=0).sum(),change=g.change.sum()))
    for sign,g in [('positive',dd[dd.change.gt(.00001)].sort_values('change',ascending=False)),('negative',dd[dd.change.lt(-.00001)].sort_values('change'))]:
        for rank,tr in enumerate(g.head(8).itertuples(),1):
            ff=fine[fine.id.eq(key)&fine.entry.eq(tr.entry)]
            old_index=(tr.baseline_rule,tr.entry)
            baseline_covered=bool(parent_fine.loc[old_index,'covered']) if old_index in parent_fine.index else None
            new_covered=bool(ff.covered.iloc[0]) if len(ff) else None
            pairs.append(dict(id=key,sign=sign,rank=rank,entry=tr.entry,effect=tr.effect,category=tr.category,selected_rule=tr.selected_rule,new_trigger=tr.new_trigger,old_trigger=tr.old_trigger,change=tr.change,new_fine_covered=new_covered,baseline_fine_covered=baseline_covered,new_net=tr.new_net,old_net=tr.old_net))
    pos=dd.change.sort_values(ascending=False)
    net=s[s.id.eq(key)&s.bp.eq(5)].iloc[0].delta_baseline
    tails.append(dict(id=key,delta_baseline=net,largest_date_improvement=pos.iloc[0],top3_improvements=pos.head(3).sum(),delta_without_top1=net-pos.head(1).sum(),delta_without_top3=net-pos.head(3).sum(),delta_without_top5=net-pos.head(5).sum(),note='descriptive removal of attribution, not rerun account or a tradable selection'))
    if key.startswith('C'):
        t=pd.read_csv(R/f'trades/{key}_5.csv',parse_dates=['entry','exit'])
        for tr in t[t.category.eq('overlap')].itertuples():
            a=next(r for r in reg if r['id']==key);otherkey=key[:-1]+('B' if key.endswith('A') else 'A')
            other=pd.read_csv(R/f'trades/{otherkey}_5.csv',parse_dates=['entry','exit']);opp=other[other.entry.eq(tr.entry)].iloc[0]
            ff=fine[fine.id.eq(key)&fine.entry.eq(tr.entry)]
            overlap.append(dict(id=key,entry=tr.entry,selected_rule=tr.selected_rule,trigger=tr.trigger,clock=tr.buy_clock,cash=tr.cash_increment,opposite_priority=otherkey,other_rule=opp.selected_rule,other_trigger=opp.trigger,other_clock=opp.buy_clock,other_cash=opp.cash_increment,change=tr.cash_increment-opp.cash_increment,fine_covered=bool(ff.covered.iloc[0]) if len(ff) else False))
y.save('decision_attribution_groups.csv',summ);y.save('decision_changes.csv',changed);y.save('key_gain_loss_dates.csv',pairs);y.save('overlap_priority_dates.csv',overlap);y.save('improvement_concentration.csv',tails)
add('保留/删去/改路径',pd.DataFrame(changed)[lambda f:f.id.isin(keys)])
add('按参与分类的差额',pd.DataFrame(summ)[lambda f:f.id.isin(keys)])
add('收益增量集中度',pd.DataFrame(tails))
add('核心四个重叠日期',pd.DataFrame(overlap)[lambda f:f.id.isin(['C12A','C11A'])])
add('主要增益与反例日期',pd.DataFrame(pairs)[lambda f:f.id.isin(['C12A','C11A'])])
coverage=fine.groupby(['id','trigger']).agg(n=('entry','size'),covered=('covered','sum'),increment_to_base=('change','sum'),replay_cash_change=('cash_change','sum')).reset_index()
y.save('fine_coverage_summary.csv',coverage);add('细分钟覆盖',coverage)
benefit=fine[fine.change.gt(.00001)].groupby(['id','trigger']).agg(positive_dates=('entry','size'),covered=('covered','sum'),positive_change=('change','sum')).reset_index()
y.save('fine_positive_gain_summary.csv',benefit);add('实际正增益日期覆盖',benefit)
costleaders=[];dominance=[]
for bp in [5,11,20]:
    pool=s[s.bp.eq(bp)];base=pool[pool.id.eq('C00B')].iloc[0]
    for objective,col in [('profit','increment'),('win','trade_win')]:
        g=pool[pool.completed.ge(40)].sort_values([col,'id'],ascending=[False,True]);best=g[col].iloc[0]
        for t in g[g[col].eq(best)].itertuples():costleaders.append(dict(bp=bp,objective=objective,id=t.id,net=t.increment,win=t.trade_win))
    for t in pool.itertuples():
        if t.increment>base.increment and t.trade_win>base.trade_win and t.trade_worst>base.trade_worst and t.relative_mdd>base.relative_mdd:dominance.append(dict(bp=bp,id=t.id,delta=t.delta_baseline,win=t.trade_win,worst=t.trade_worst,mdd=t.relative_mdd))
y.save('cost_leaders.csv',costleaders);y.save('strict_improvements.csv',dominance)
add('成本改变冠军',pd.DataFrame(costleaders));add('四指标同时严格改善',pd.DataFrame(dominance))
add('每笔期限与资金占用',s[s.id.isin(keys)&s.bp.eq(5)][['id','max_wait_calendar_days','longest_relative_deficit_calendar_days','deposit_yuan_days','deposits','peak_requirement','max_single_deposit','max_buy_cash','single_max']])
for p,h in protected.items():assert b.sha(p)==h,p
(R/'DECISION_DATA.md').write_text('\n\n'.join(blocks)+'\n')
y.js('details_validation.json',dict(status='PASS',protected_files=len(protected),new_optimization_candidates=0,scope='derived descriptions only; no new accounts or changed parameters'))
y.js('details_manifest.json',dict(files={str(p):b.sha(p) for p in R.iterdir() if p.is_file() and str(p) not in protected and p.name not in ['manifest.json','verification_manifest.json','details_manifest.json','details.log','verification.log','calculation.log']}))
