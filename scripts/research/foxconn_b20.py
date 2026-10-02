"""B20 fixed combinations. All market processing is remote-only."""
import os,sys,json,inspect,hashlib,subprocess,traceback,itertools
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_b19 as x
b=x.b
R=Path('research/foxconn_t0_20261002_b20')
PARENT='6c82922dadaaf605766d56f31ae1d5715a321a8d'
KEYS=['H00','R121','H01','W0022','W0122','H03']
BASE='C00B'
def save(name,data):
    p=R/name;p.parent.mkdir(parents=True,exist_ok=True)
    frame=data if isinstance(data,pd.DataFrame) else pd.DataFrame(data)
    frame.to_csv(p,index=False);return frame
def js(name,obj):
    (R/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str))
def freeze():
    if (R/'failure.json').exists():
        (R/'failures').mkdir(exist_ok=True)
        (R/'failure.json').rename(R/'failures'/('before_'+os.environ['GITHUB_RUN_ID']+'.json'))
    folders=[x.R,b.R,b.b17.R,b.b16.R,b.P]
    raw=[b.old.P/'source/601138-full-5min-history.zip',b.r1.B13/'tdx_recovered_1m.csv',b.old.B2/'source/sse_index.csv']
    inherited=list(Path('scripts/research').glob('foxconn*.py'))
    inherited=[p for p in inherited if 'b20' not in p.name]
    subprocess.run(['git','diff','--exit-code',PARENT,'--']+[str(p) for p in folders+raw+inherited],check=True)
    paths=set(raw+inherited)
    for folder in folders:paths.update(p for p in folder.rglob('*') if p.is_file())
    js('frozen_input_hashes.json',dict(parent=PARENT,files={str(p):b.sha(p) for p in sorted(paths)},registry_sha256=b.sha(R/'registry.json'),code={str(p):b.sha(p) for p in Path('scripts/research').glob('foxconn_b20*.py')}))
def masks_from_features(f):
    def c(col,op,value):return getattr(f[col],op)(value).astype('boolean').where(f[col].notna(),pd.NA)
    a=c('S1_clv','ge',.8)&c('S1_vr','le',1)
    bb=c('S1_clv','ge',.7)&c('S1_r3','le',-4)
    env=f.S1_r20.ge(0).where(f.S1_r20.notna(),False)
    return dict(H00=a,R121=a&env,H01=bb,W0022=bb,W0122=bb,H03=bb)
def selection(rule,masks):
    ix=next(iter(masks.values())).index
    a=masks[rule['a']].fillna(False) if rule['a'] else pd.Series(False,index=ix)
    bb=masks[rule['b']].fillna(False) if rule['b'] else pd.Series(False,index=ix)
    category=pd.Series(np.select([a&bb,a,bb],['overlap','only_A','only_B'],default='neither'),index=ix)
    chosen=pd.Series('',index=ix,dtype=object)
    chosen.loc[a&~bb]=rule['a'];chosen.loc[bb&~a]=rule['b']
    if rule['policy'] in ['A','B']:chosen.loc[a&bb]=rule[rule['policy'].lower()]
    return chosen,category
def combined_paths(rule,masks,paths):
    chosen,category=selection(rule,masks)
    p=paths[rule['a'] or rule['b']].copy()
    for key in KEYS:
        ix=p.index[chosen.reindex(p.index).eq(key)]
        if len(ix):p.loc[ix,:]=paths[key].loc[ix,:]
    return chosen.ne(''),p,chosen,category
def description(rule):
    aa={'H00':'昨日收顶部20%且量不超此前20日均量；次日14:50买回','R121':'昨日收顶部20%、量不超此前20日均量且20日累计涨幅非负；次日涨1%触发/14:50截止'}
    bb={'H01':'昨日3日累计跌至少4%且收顶部30%；次日低开0.5%尽早买，否则跌0.5%/涨1%/10:30','W0022':'昨日3日累计跌至少4%且收顶部30%；次日低开0.5%尽早买，否则跌0.5%/涨2%/11:00','W0122':'昨日3日累计跌至少4%且收顶部30%；次日低开0.5%尽早买，否则跌1%/涨2%/11:00','H03':'昨日3日累计跌至少4%且收顶部30%；次日直接开盘买'}
    parts=[aa[rule['a']]] if rule['a'] else []
    if rule['b']:parts.append(bb[rule['b']])
    return '今日收盘卖1000股：'+'；或 '.join(parts)+('；重叠'+{'A':'第一类优先','B':'第二类优先','SKIP':'不卖'}[rule['policy']] if rule['group']=='combo' else '')
def load():
    d=pd.read_csv(b.P/'daily_ledger.csv',parse_dates=['date','exit_date'])
    f=pd.read_csv(b.R/'features.csv');masks=masks_from_features(f)
    specs={a['id']:a for a in x.registry() if a['id'] in KEYS}
    paths={k:pd.read_csv(x.R/f'paths/{specs[k]["path"]}.csv',parse_dates=['entry','exit']).set_index('entry_i',drop=False) for k in KEYS}
    schedule=b.b16.schedule_for(d,json.loads((b.b16.R/'verified_events.json').read_text()),0)
    return d,f,masks,specs,paths,schedule
def run():
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in frozen['files'].items():assert b.sha(p)==h,p
    assert frozen['registry_sha256']==b.sha(R/'registry.json')
    reg=json.loads((R/'registry.json').read_text());assert len(reg)==30
    d,f,masks,specs,paths,schedule=load()
    (R/'inherited_account_runtime.py.txt').write_text(x.source)
    rows=[];plans={};configs={};aliases=[];seen={};needs={}
    for rule in reg:
        key=rule['id'];mask,p,chosen,category=combined_paths(rule,masks,paths);configs[key]=(chosen,category)
        # Hash the full prescribed path identities before accounting, never profits.
        signature=hashlib.sha256(pd.DataFrame({'date':d.date,'chosen':chosen.map(lambda k:specs[k]['path'] if k else '')}).to_csv(index=False).encode()).hexdigest()
        canonical=seen.setdefault(signature,key);aliases.append(dict(id=key,canonical=canonical,decision_path_sha256=signature))
        unlimited,need,_=x.plan(d,mask,p)
        t,_,reasons=x.plan(d,mask,p,capacity=3)
        t['selected_rule']=t.entry_i.map(chosen);t['category']=t.entry_i.map(category)
        assert not t.entry_i.duplicated().any()
        needs[key]=need;plans[key]=t
        save(f'participation/{key}.csv',reasons.assign(selected_rule=chosen.reindex(d.index[d.date.ge('2020-01-01')]).to_numpy(),category=category.reindex(d.index[d.date.ge('2020-01-01')]).to_numpy()))
    save('path_aliases.csv',aliases)
    js('pre_account_registry_validation.json',dict(registered=30,combinations=24,unique_paths=len(seen),computed_before_account=True))
    # Account construction remains the inherited full ledger, including tax reserves.
    for rule in reg:
        key=rule['id'];t=plans[key]
        for bp in [5,11,20]:
            z,o,tt,ff,s=x.account(d,t,3000,bp/10000,schedule);x.audit(d,z,o,tt,s)
            done=tt[tt.exit_i.notna()];stats=b.stats(done.cash_increment,done.net_pct)
            row=dict(id=key,group=rule['group'],bp=bp,rule=description(rule),**s,**{'trade_'+k:v for k,v in stats.items()},average_profit=done.loc[done.cash_increment.gt(0),'cash_increment'].mean(),average_loss=done.loc[done.cash_increment.lt(0),'cash_increment'].mean(),minimum_old_shares_unconstrained=needs[key],max_buy_cash=float(ff.buy_cost.max()),max_single_deposit=float(ff.deposit.max()),max_wait_calendar_days=int((done.exit-done.entry).dt.days.max()),inventory_blocked=int(pd.read_csv(R/f'participation/{key}.csv').reason.eq('inventory_participation').sum()))
            rows.append(row)
            for folder,data,ext in [('accounts',z,'.csv.gz'),('orders',o,'.csv.gz'),('trades',tt,'.csv'),('funds',ff,'.csv.gz')]:save(f'{folder}/{key}_{bp}'+ext,data)
            print('ACCOUNT',key,bp,s['increment'],len(done),flush=True)
    summary=save('account_summary.csv',rows)
    parent=pd.read_csv(x.R/'account_summary.csv');aligned=[]
    for rule in KEYS+['C00B','C03B']:
        old_id=rule if rule in KEYS else ('COMBO_H01' if rule=='C00B' else 'COMBO_H03')
        for bp in [5,11,20]:
            old=parent[parent.id.eq(old_id)&parent.bp.eq(bp)&parent.group.eq('main' if rule in KEYS else 'combo')].iloc[0]
            now=summary[summary.id.eq(rule)&summary.bp.eq(bp)].iloc[0]
            for col in ['increment','completed','trade_wins','trade_win','trade_worst','relative_mdd','terminal_tax_reserve','deposits']:
                assert abs(now[col]-old[col])<1e-5,(rule,bp,col,now[col],old[col])
            aligned.append(dict(id=rule,bp=bp,parent_id=old_id,status='PASS'))
    save('parent_baseline_alignment.csv',aligned)
    analyze(d,summary,reg,configs,specs)
    for p,h in frozen['files'].items():assert b.sha(p)==h,p
    js('calculation_validation.json',dict(status='PASS',accounts=len(rows),parent_alignments=len(aligned),parent_files=len(frozen['files']),data_cutoff=str(d.date.max().date()),inventory_max=max(needs.values()),aliases=len(reg)-len(seen)))
    js('manifest.json',dict(files={str(p):b.sha(p) for p in sorted(R.rglob('*')) if p.is_file() and p.name not in ['manifest.json','calculation.log','verification.log','failure.json']}))
def analyze(d,summary,reg,configs,specs):
    byid={a['id']:a for a in reg};main=summary[summary.bp.eq(5)].set_index('id')
    periods=[];yearly=[];equity=[];attributions=[];detail=[];groups=[];adj=[];leaders=[]
    for scope,pool in [('combo',main[main.group.eq('combo')]),('all',main)]:
        for objective,col in [('profit','increment'),('win','trade_win')]:
            eligible=pool if objective=='profit' else pool[pool.completed.ge(40)]
            ranking=eligible.reset_index().sort_values([col]+(['increment'] if col!='increment' else [])+['id'],ascending=[False]+([False] if col!='increment' else [])+[True]).head(3)
            for rank,row in enumerate(ranking.itertuples(),1):leaders.append(dict(scope=scope,objective=objective,rank=rank,id=row.id))
    save('leaders.csv',leaders)
    for bp in [5,11,20]:
        ref=pd.read_csv(R/f'trades/{BASE}_{bp}.csv',parse_dates=['entry','exit']).set_index('entry_i')
        base=summary[summary.id.eq(BASE)&summary.bp.eq(bp)].iloc[0]
        for rule in reg:
            key=rule['id'];t=pd.read_csv(R/f'trades/{key}_{bp}.csv',parse_dates=['entry','exit']).set_index('entry_i')
            z=pd.read_csv(R/f'accounts/{key}_{bp}.csv.gz',parse_dates=['date'])
            row=summary[summary.id.eq(key)&summary.bp.eq(bp)].iloc[0];done=t[t.exit_i.notna()]
            for period,sel in [('2020-2023',done.entry.lt('2024-01-01'))]+[(str(y),done.entry.dt.year.eq(y)) for y in range(2024,2027)]:
                g=done[sel];periods.append(dict(id=key,bp=bp,period=period,**b.stats(g.cash_increment,g.net_pct)))
            for y in range(2020,2027):
                g=done[done.entry.dt.year.eq(y)];yearly.append(dict(id=key,bp=bp,year=y,**b.stats(g.cash_increment,g.net_pct)))
            previous=0.
            for y,g in z.groupby(z.date.dt.year):
                end=g.relative.iloc[-1];equity.append(dict(id=key,bp=bp,year=y,equity_change=end-previous,year_end_relative=end,year_end_tax_reserve=g.tax_reserve.iloc[-1],year_end_missing=3000-g.shares.iloc[-1]));previous=end
            both=t.index.intersection(ref.index);added=t.index.difference(ref.index);removed=ref.index.difference(t.index)
            price=(ref.loc[both,'buy_cost']-t.loc[both,'buy_cost']).sum()
            tax=(ref.loc[both,'dividend_tax']-t.loc[both,'dividend_tax']).sum()
            missed=(ref.loc[both,'missed_dividend']-t.loc[both,'missed_dividend']).sum()
            participation=t.loc[added,'cash_increment'].sum()-ref.loc[removed,'cash_increment'].sum()
            reserve=base.terminal_tax_reserve-row.terminal_tax_reserve
            pending=lambda tt:sum(v.sale_net-1000*d.close.iloc[-1]-v.missed_dividend for v in tt[tt.exit_i.isna()].itertuples())
            mark=pending(t)-pending(ref)
            delta=row.increment-base.increment
            assert abs(delta-price-tax-missed-participation-reserve-mark)<1e-5,(key,bp,'attribution')
            attributions.append(dict(id=key,bp=bp,net_change=delta,shared=len(both),added=len(added),removed=len(removed),same_date_buy_and_fee=price,fifo_tax=tax,missed_dividend=missed,participation=participation,terminal_reserve=reserve,pending_mark=mark))
            for i in t.index.union(ref.index):
                new=t.loc[i] if i in t.index else None;old=ref.loc[i] if i in ref.index else None
                effect=('added' if old is None else 'removed' if new is None else 'changed_path' if new.path!=old.path else 'same_path')
                detail.append(dict(id=key,bp=bp,entry_i=i,entry=d.date.iloc[i],effect=effect,category=configs[key][1].iloc[i],selected_rule=new.selected_rule if new is not None else '',baseline_rule=old.selected_rule if old is not None else '',new_trigger=new.trigger if new is not None else '',old_trigger=old.trigger if old is not None else '',new_net=new.cash_increment if new is not None else 0.,old_net=old.cash_increment if old is not None else 0.,change=(new.cash_increment if new is not None else 0.)-(old.cash_increment if old is not None else 0.)))
            for cat in ['only_A','only_B','overlap']:
                g=done[done.category.eq(cat)];groups.append(dict(id=key,bp=bp,category=cat,**b.stats(g.cash_increment,g.net_pct)))
    save('periods.csv',periods);save('yearly_trades.csv',yearly);save('annual_equity_changes.csv',equity)
    save('attribution.csv',attributions);det=save('attribution_trades.csv',detail);save('participation_groups.csv',groups)
    for a in reg:
        if a['group']!='combo':continue
        for c in reg:
            if c['group']!='combo':continue
            fields=[k for k in ['a','b','policy'] if a[k]!=c[k]]
            if len(fields)==1:adj.append(dict(center=a['id'],neighbor=c['id'],changed=fields[0],increment=main.loc[c['id'],'increment'],win=main.loc[c['id'],'trade_win'],delta=main.loc[c['id'],'increment']-main.loc[a['id'],'increment'],worst=main.loc[c['id'],'trade_worst'],mdd=main.loc[c['id'],'relative_mdd']))
    save('adjacent_combinations.csv',adj)
    fine=pd.read_csv(x.R/'fine_path_replay.csv',parse_dates=['entry']).set_index(['id','entry'])
    top=list(dict.fromkeys(a['id'] for a in leaders));coverage=[]
    for key in top:
        t=pd.read_csv(R/f'trades/{key}_5.csv',parse_dates=['entry','exit'])
        di=det[det.id.eq(key)&det.bp.eq(5)].set_index('entry_i')
        for tr in t.itertuples():
            ix=(tr.selected_rule,tr.entry);assert ix in fine.index,ix
            fr=fine.loc[ix];dv=di.loc[tr.entry_i]
            coverage.append(dict(id=key,entry=tr.entry,selected_rule=tr.selected_rule,category=tr.category,trigger=tr.trigger,buy_clock=tr.buy_clock,buy_ref=tr.buy_ref,net=tr.cash_increment,change=dv.change,effect=dv.effect,covered=fr.covered,new_trigger=fr.get('new_trigger'),new_clock=fr.get('new_clock'),new_price=fr.get('new_price'),cash_change=fr.get('cash_change')))
    save('leader_fine_coverage.csv',coverage)
    # Negative historical regions: independently cost both sides on exactly the same dates.
    mirrors=[]
    for key in main.index:
        t=pd.read_csv(R/f'trades/{key}_5.csv',parse_dates=['entry','exit'])
        for period,sel in [('2020-2023',t.entry.lt('2024-01-01'))]+[(str(y),t.entry.dt.year.eq(y)) for y in range(2024,2027)]:
            g=t[sel&t.exit_i.notna()]
            if len(g)==0 or g.cash_increment.sum()>=0:continue
            buy=1000*g.sell_ref*1.0005;sell=1000*g.buy_ref*.9995
            reverse=sell-buy-b.old.fee(buy,g.entry,False)-b.old.fee(sell,g.exit,True)
            # Reverse buys retain dividend entitlement across ex-date; keep gross entitlement
            # separately to avoid claiming the full reverse FIFO tax account was constructed.
            normal=1000*g.sell_ref*.9995-1000*g.buy_ref*1.0005-b.old.fee(1000*g.sell_ref*.9995,g.entry,True)-b.old.fee(1000*g.buy_ref*1.0005,g.exit,False)
            mirrors.append(dict(id=key,period=period,n=len(g),account_episode_cash=g.cash_increment.sum(),normal_price_cost_cash=normal.sum(),reverse_price_cost_cash=reverse.sum(),reverse_price_cost_pct=(100*reverse/(1000*g.sell_ref)).mean(),dividend_entitlement=g.missed_dividend.sum(),status='same dates and clocks; independently costed nominal candidate, dividend FIFO and reverse continuous account unverified'))
    save('opposite_direction_regions.csv',mirrors)
    comp=summary.copy();comp['delta_baseline']=comp.apply(lambda row:row.increment-summary[summary.id.eq(BASE)&summary.bp.eq(row.bp)].iloc[0].increment,axis=1)
    save('comparison.csv',comp)
    blocks=['# B20完整计算表','模型事实：2020年至2026-09-11，3000股旧仓、每笔1000股、足额资金；非未来收益。']
    sections=[('全部主成本规则',comp[comp.bp.eq(5)][['id','rule','completed','trade_wins','trade_win','increment','delta_baseline','average_profit','average_loss','trade_worst','relative_mdd','pending']]),('前列规则',pd.DataFrame(leaders)),('三档成本',comp[['id','bp','completed','trade_win','increment','delta_baseline','trade_worst','relative_mdd']]),('资源',comp[comp.bp.eq(5)][['id','deposits','peak_requirement','max_single_deposit','max_buy_cash','single_max','minimum_old_shares_unconstrained','inventory_blocked','max_wait_calendar_days','longest_relative_deficit_calendar_days','deposit_yuan_days']]),('前列分期',pd.DataFrame(periods).query('bp==5')[lambda f:f.id.isin(top)]),('前列归因',pd.DataFrame(attributions).query('bp==5')[lambda f:f.id.isin(top)]),('前列相邻',pd.DataFrame(adj)[lambda f:f.center.isin(top)])]
    for title,frame in sections:blocks+=['## '+title,frame.to_markdown(index=False,floatfmt='.4f')]
    (R/'REVIEW_DATA.md').write_text('\n\n'.join(blocks)+'\n')
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true','Market computations stay on GitHub'
    try:
        R.mkdir(parents=True,exist_ok=True)
        if sys.argv[1]=='freeze':freeze()
        else:run()
    except Exception:
        js('failure.json',dict(run=os.environ.get('GITHUB_RUN_ID'),traceback=traceback.format_exc()));raise
