"""Independent B22 saved-ledger, prefix-feature and selection checks."""
import os,json,functools,traceback
import numpy as np
import pandas as pd
import foxconn_b22 as z
import foxconn_b21_verify as oldtests
R=z.R
def scalar_features(g,cref):
    rows=[r for r in g.itertuples() if r.clock<='14:50'];lookup={}
    for r in rows:lookup.setdefault(r.clock,[]).append(r)
    def endpoint(c):
        a=lookup.get(c,[])
        return float(a[0].close) if len(a)==1 and np.isfinite(a[0].close) and a[0].close>0 else np.nan
    p50=endpoint('14:50');p30=endpoint('14:30');day=p50/cref-1 if np.isfinite(cref) and cref>0 else np.nan;tail=p50/p30-1
    good=len(rows)==46 and sorted(lookup)==z.PREFIX and all(len(a)==1 for a in lookup.values())
    if good:
        good=all(all(np.isfinite(v) and v>0 for v in [r.open,r.high,r.low,r.close]) and r.high>=max(r.open,r.close,r.low) and r.low<=min(r.open,r.close,r.high) for r in rows)
    if good:
        hi=max(r.high for r in rows);lo=min(r.low for r in rows);position=(p50-lo)/(hi-lo) if hi>lo else np.nan
    else:position=np.nan
    return dict(day=day,position=position,tail=tail)
def clock_and_selection_tests():
    g=pd.DataFrame([dict(clock=c,open=100.,high=110.,low=100.,close=100.,volume=0.) for c in z.x.ENDS]);g.loc[g.clock.eq('14:50'),'close']=107.
    f=z.feature_day(g,107.);assert f['day']==0 and f['position']==.7 and f['day_available'] and f['position_available']
    r=dict(scope='AB',feature='position',side='ge');fam=pd.Series(['A']);ff=pd.DataFrame([f]);assert z.decide(r,ff,fam)[0].iloc[0]
    assert not z.decide({**r,'side':'lt'},ff,fam)[0].iloc[0]
    for name in ['day','tail']:
        equal=ff.copy();equal[name]=0.;assert z.decide(dict(scope='AB',feature=name,side='ge'),equal,fam)[0].iloc[0];assert not z.decide(dict(scope='AB',feature=name,side='lt'),equal,fam)[0].iloc[0]
    missing=g[~g.clock.eq('10:00')];a=z.feature_day(missing,107.);assert a['day_available'] and a['tail_available'] and not a['position_available']
    missing=g[~g.clock.eq('14:30')];a=z.feature_day(missing,107.);assert a['day_available'] and not a['tail_available'] and not a['position_available']
    missing=g[~g.clock.eq('14:50')];a=z.feature_day(missing,107.);assert not any(a[k+'_available'] for k in ['day','tail','position'])
    dup=pd.concat([g,g[g.clock.eq('14:50')]]);assert not z.feature_day(dup,107.)['day_available']
    flat=g.copy();flat[['open','high','low','close']]=100.;a=z.feature_day(flat,100.);assert a['day']==0 and a['tail']==0 and not a['position_available']
    assert not z.feature_day(g,0.)['day_available'] and z.feature_day(g,0.)['tail_available']
    future=g.copy();future.loc[future.clock.gt('14:50'),['open','high','low','close']]*=1.9
    for name in ['day','tail','position']:assert z.feature_day(future,107.)[name]==f[name]
    masks={'R121':pd.Series([True,False,False],dtype='boolean'),'H01':pd.Series([True,True,False],dtype='boolean')};families,categories=z.origins(masks);assert families.tolist()==['A','B','']
    ff=pd.DataFrame(dict(day=[-1.,np.nan,0.]));r=dict(scope='A',feature='day',side='ge');allow,app,known,reason=z.decide(r,ff,families)
    assert allow.tolist()==[False,True,False] and families.tolist()==['A','B',''] and reason.iloc[0]=='market_rejected'
    ff.day=[np.nan,0.,0.];allow,_,_,reason=z.decide(r,ff,families);assert not allow.iloc[0] and reason.iloc[0]=='feature_unavailable' and allow.iloc[1]
    assert not z.decide({**r,'side':'avail'},ff,families)[0].iloc[0]
    oldtests.inherited_tests.synthetic_tests();oldtests.new_clock_tests()
def run():
    frozen=json.loads((R/'frozen_input_hashes.json').read_text());protected=json.loads((R/'manifest.json').read_text())['files']
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert z.b.sha(p)==h,p
    d,_,masks,_,_,schedule=z.y.load();m=z.q.load_minutes();f=pd.read_csv(R/'features.csv',parse_dates=['date']);family,category=z.origins(masks);reg=z.registry();s=pd.read_csv(R/'comparison.csv');checks=[]
    src=(z.q.R/'independent_verifier_runtime.py.txt').read_text();scope=dict(z.b.b17.__dict__);scope['functools']=functools;exec(src,scope);(R/'independent_verifier_runtime.py.txt').write_text(src)
    for row in s.itertuples():
        a=pd.read_csv(R/f'accounts/{row.id}_{row.bp}.csv.gz',parse_dates=['date']);o=pd.read_csv(R/f'orders/{row.id}_{row.bp}.csv.gz',parse_dates=['date','entry']);t=z.trade(row.id,row.bp)
        scope['verify'](d,a,o,3000,row.bp/10000,0.,schedule)
        assert abs(a.relative.iloc[-1]-row.increment)<1e-5 and int(t.cash_increment.gt(0).sum())==row.trade_wins
        assert not o[o.side.eq('SELL')].date.duplicated().any()
        base=z.trade(row.target+'_ALL',row.bp).set_index('entry_i');assert set(t.entry_i)<=set(base.index)
        if len(t):
            cols=['entry_i','exit_i','buy_ref','buy_clock','path','selected_rule','family'];pd.testing.assert_frame_equal(t[cols].reset_index(drop=True),base.loc[t.entry_i].reset_index()[cols],check_dtype=False)
        need=max([1000*(1+sum((t.entry_i<v.entry_i)&(t.exit_i.isna()|t.exit_i.ge(v.entry_i)))) for v in t.itertuples()],default=1000);assert need<=3000 and need==row.minimum_old_shares
        if row.bp!=5:
            tt=z.trade(row.id);pd.testing.assert_frame_equal(t[['entry_i','exit_i','buy_ref','buy_clock','selected_rule']],tt[['entry_i','exit_i','buy_ref','buy_clock','selected_rule']])
        checks.append(dict(id=row.id,bp=row.bp,days=len(a),orders=len(o),minimum_old_shares=need,status='PASS'))
        if len(checks)%24==0:print('INDEPENDENT',len(checks),flush=True)
    z.save('independent_accounts_verified.csv',checks)
    days={day:g for day,g in m.groupby('date')};empty=m.iloc[:0];scalar=pd.DataFrame([scalar_features(days.get(r.date,empty),r.preclose) for r in d.itertuples()])
    for col in ['day','tail','position']:np.testing.assert_allclose(scalar[col],f[col],atol=1e-12,equal_nan=True)
    decisions=0
    for r in reg:
        got=pd.read_csv(R/f'decisions/{r["id"]}.csv').fillna('');allowed=[]
        for i in d.index:
            fam=family.iloc[i];app=bool(fam and (r['scope']=='AB' or fam==r['scope']))
            if not fam:want=False
            elif not app or r['side']=='all':want=True
            else:
                v=scalar.loc[i,r['feature']];k=np.isfinite(v);threshold=.7 if r['feature']=='position' else 0.
                want=k if r['side']=='avail' else k and (v>=threshold if r['side']=='ge' else v<threshold)
            assert bool(got.signal.iloc[i])==want and got.family.iloc[i]==fam;allowed.append(want);decisions+=1
        t=z.trade(r['id']);assert all(allowed[int(i)] for i in t.entry_i)
    # These mutations may alter later execution prices, but not the 14:50 decision.
    after=m.copy();after.loc[after.clock.gt('14:50'),['open','high','low','close']]*=1.73
    dd=d.copy();dd[['open','high','low','close','volume']]*=1.37
    mutated=z.features(dd,after);prefix=z.features(d,m[m.clock.le('14:50')])
    for col in ['day','tail','position']:
        np.testing.assert_allclose(mutated[col],f[col],atol=1e-12,equal_nan=True);np.testing.assert_allclose(prefix[col],f[col],atol=1e-12,equal_nan=True)
    for r in reg:
        original=z.decide(r,f,family)[0];pd.testing.assert_series_equal(original,z.decide(r,mutated,family)[0]);pd.testing.assert_series_equal(original,z.decide(r,prefix,family)[0])
    for target in z.TARGETS:
        for feature in ['day','tail','position']:
            for family_scope in ['A','B','AB']:
                rr=[next(r for r in reg if r['id']==f'{target}_{family_scope}_{feature}_{side}') for side in ['ge','lt','avail']]
                ge,lt,av=[z.decide(r,f,family)[0] for r in rr];app=z.decide(rr[0],f,family)[1]
                assert not (ge& lt&app).any();pd.testing.assert_series_equal((ge|lt)&app,av&app)
    ab=pd.read_csv(R/'availability_bridge.csv');np.testing.assert_allclose(ab.availability_delta+ab.market_delta,ab.total_delta,atol=1e-8)
    clock_and_selection_tests()
    t=z.trade('T1_ALL');_,_,_,_,met=z.x.account(d,t,3000,.0005,schedule,initialcash=200000.);assert abs(met['increment']-s[s.id.eq('T1_ALL')&s.bp.eq(5)].iloc[0].increment)<1e-5
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert z.b.sha(p)==h,p
    z.js('independent_validation.json',dict(status='PASS',new_saved_accounts=168,reused_account_results=0,scalar_feature_days=len(d),scalar_rule_decisions=decisions,post1450_mutation_rules=56,prefix_truncation_rules=56,parent_files=len(frozen['files']),checks=['independent saved-account fee/FIFO/dividend/cash/shares','fixed retained buy paths and no added dates','causal scalar endpoint and 46-bar prefix features','endpoint/equality/flat/duplicate/missing boundaries','original-family rejection without fallback','availability and market bridge','late quotes and final daily OHLCV cannot change 1450 features','inherited multiple pending, cross-year, T+1, lunch, missing, locked and unresolved tests']))
    tables(s)
    z.js('verification_manifest.json',dict(files={str(p):z.b.sha(p) for p in R.rglob('*') if p.is_file() and str(p) not in protected and p.name not in ['manifest.json','verification_manifest.json','calculation.log','verification.log','failure.json']}))
def tables(s):
    leaders=pd.read_csv(R/'leaders.csv');focus=list(dict.fromkeys(list(leaders.id)+['T1_ALL','T05_ALL']));blocks=['# B22冻结结果审阅表','模型事实：2020年至2026-09-11；3000股研究旧仓，每笔1000，资金足额。非独立OOS或真实成交认证。']
    def add(title,g):blocks.extend(['## '+title,g.to_markdown(index=False,floatfmt='.4f') if len(g) else '无记录'])
    cols=['id','rule','completed','trade_wins','trade_win','increment','delta_T1_ALL','delta_T05_ALL','average_profit','average_loss','trade_worst','relative_mdd','pending']
    add('38核心主表',s[s.bp.eq(5)&s.group.eq('core')][cols]);add('18可用性对照',s[s.bp.eq(5)&s.group.eq('availability')][cols]);add('排名',leaders)
    add('重点三成本',s[s.id.isin(focus)][['id','bp','completed','trade_win','increment','delta_T1_ALL','delta_T05_ALL','trade_mean_pct','trade_worst','relative_mdd']])
    for file in ['periods','yearly_trades','annual_equity_changes','family_groups','availability_bridge','attribution']:
        a=pd.read_csv(R/(file+'.csv'));add(file,a[a.id.isin(focus)&a.bp.eq(5)])
    for file in ['feature_availability','b18_overlap','concentration','fine_coverage_summary','boundary_and_flip_dates']:add(file,pd.read_csv(R/(file+'.csv')))
    add('资源',s[s.id.isin(focus)&s.bp.eq(5)][['id','deposits','peak_requirement','max_single_deposit','max_buy_cash','single_max','minimum_old_shares','inventory_blocked','max_wait_calendar_days','longest_relative_deficit_calendar_days','deposit_yuan_days']])
    (R/'REVIEW_DATA.md').write_text('\n\n'.join(blocks)+'\n')
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:run()
    except Exception:
        z.js('failure.json',dict(stage='independent_verification',run=os.environ.get('GITHUB_RUN_ID'),traceback=traceback.format_exc()));raise
