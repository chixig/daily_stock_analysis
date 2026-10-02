"""Independent saved-account and causal path verification for B21."""
import os,json,functools,traceback
from types import SimpleNamespace
import numpy as np
import pandas as pd
import foxconn_b21 as q
import foxconn_b20_verify as inherited_tests
x=q.x;y=q.y;b=q.b;R=q.R
def run():
    manifests=json.loads((R/'manifest.json').read_text())['files'];frozen=json.loads((R/'frozen_input_hashes.json').read_text())['files']
    for p,h in {**manifests,**frozen}.items():assert b.sha(p)==h,p
    d,f,masks,_,_,schedule=y.load();s=pd.read_csv(R/'comparison.csv');reg=q.registry();sp=q.specs();checked=[]
    src=(y.R/'independent_verifier_runtime.py.txt').read_text();scope=dict(b.b17.__dict__);scope['functools']=functools;exec(src,scope)
    (R/'independent_verifier_runtime.py.txt').write_text(src)
    for r in s.itertuples():
        z=pd.read_csv(R/f'accounts/{r.id}_{r.bp}.csv.gz',parse_dates=['date']);o=pd.read_csv(R/f'orders/{r.id}_{r.bp}.csv.gz',parse_dates=['date','entry']);t=q.read_trade(r.id,r.bp)
        scope['verify'](d,z,o,3000,r.bp/10000,0.,schedule)
        assert abs(z.relative.iloc[-1]-r.increment)<1e-5
        assert int(t.cash_increment.gt(0).sum())==r.trade_wins and t.exit_i.notna().sum()==r.completed
        assert not o[o.side.eq('SELL')].date.duplicated().any()
        need=max([1000*(1+sum((t.entry_i<v.entry_i)&(t.exit_i.isna()|t.exit_i.ge(v.entry_i)))) for v in t.itertuples()],default=0)
        assert need<=3000
        if r.bp!=5:
            ref=q.read_trade(r.id);cols=['entry_i','exit_i','buy_ref','buy_clock','path','selected_rule']
            pd.testing.assert_frame_equal(t[cols],ref[cols])
        checked.append(dict(id=r.id,bp=r.bp,days=len(z),orders=len(o),minimum_old_shares=need,status='PASS'))
        if len(checked)%12==0:print('VERIFIED',len(checked),flush=True)
    q.save('independent_accounts_verified.csv',checked)
    # Reuse unchanged complete parent tests for account edge cases, then test new choices.
    inherited_tests.synthetic_tests();new_clock_tests()
    scalar=0;cross=[]
    for rule in [r for r in reg if r['group']=='combo']:
        dec=pd.read_csv(R/f'decisions/{rule["id"]}.csv').fillna('')
        for i in d.index:
            aa=bool(masks['R121'].iloc[i]) if pd.notna(masks['R121'].iloc[i]) else False
            bb=bool(masks['H01'].iloc[i]) if pd.notna(masks['H01'].iloc[i]) else False
            want=rule['a'] if aa else rule['b'] if bb else ''
            assert dec.selected_rule.iloc[i]==want;scalar+=1
        t=q.read_trade(rule['id'])
        for tr in t.itertuples():
            assert tr.selected_rule==dec.selected_rule.iloc[tr.entry_i]
            pp=pd.read_csv(R/f'paths/{tr.selected_rule}.csv').set_index('entry_i').loc[tr.entry_i]
            assert (pd.isna(pp.exit_i) and pd.isna(tr.exit_i)) or (pp.exit_i==tr.exit_i and abs(pp.buy_ref-tr.buy_ref)<1e-8 and pp.buy_clock==tr.buy_clock)
            if pd.notna(tr.exit) and tr.entry.year!=tr.exit.year:cross.append(dict(id=rule['id'],entry=tr.entry,exit=tr.exit,attached_rule=tr.selected_rule))
    q.save('cross_year_bindings.csv',cross)
    # Actual paths truncated before 2024 must preserve every already completed fill.
    m=q.load_minutes();cut=d.index[d.date.lt('2024-01-01')][-1];original=b.first_buy;b.first_buy=x.first_buy;prefix=0
    try:
        for key,spec in sp.items():
            pp,_=b.build_paths(d.iloc[:cut+1],m[m.date.le(d.date.iloc[cut])],spec)
            full=pd.read_csv(R/f'paths/{key}.csv',parse_dates=['entry','exit']).set_index('entry_i',drop=False);ix=pp.index[pp.exit_i.notna()]
            pd.testing.assert_frame_equal(pp.loc[ix,['exit_i','buy_ref','buy_clock']],full.loc[ix,['exit_i','buy_ref','buy_clock']],check_dtype=False);prefix+=1
    finally:b.first_buy=original
    daily=lambda dd:pd.DataFrame({'S1_clv':((dd.close-dd.low)/(dd.high-dd.low).replace(0,np.nan)).shift(),'S1_vr':(dd.volume/dd.volume.shift().rolling(20).mean()).shift(),'S1_r3':(100*((dd.close/dd.preclose).cumprod()/(dd.close/dd.preclose).cumprod().shift(3)-1)).shift(),'S1_r20':(100*((dd.close/dd.preclose).cumprod()/(dd.close/dd.preclose).cumprod().shift(20)-1)).shift()})
    before=daily(d)
    for col in before:np.testing.assert_allclose(before[col],f[col],equal_nan=True,atol=1e-10)
    dd=d.copy();future=dd.date.ge('2024-01-01');dd.loc[future,['open','high','low','close','preclose','volume']]*=1.71
    mutated=y.masks_from_features(daily(dd))
    for col in ['R121','H01']:pd.testing.assert_series_equal(masks[col][~future],mutated[col][~future])
    days=b.lookup_days(m);mutations=0
    for key,spec in sp.items():
        pp=pd.read_csv(R/f'paths/{key}.csv',parse_dates=['entry','exit'])
        for tr in pp[pp.exit_i.eq(pp.entry_i+1)&pp.entry.ge('2024-01-01')].head(3).itertuples():
            rr=d.iloc[int(tr.exit_i)];bars={k:dict(v) for k,v in days.get(rr.date,{}).items()};fill,_,_=x.first_buy(tr.sell_ref,rr,bars,spec)
            if not fill:continue
            for clock,bar in bars.items():
                if clock>b.minutes_after(fill[0],5):
                    for col in ['open','close','high','low']:bar[col]*=1.71
            again,_,_=x.first_buy(tr.sell_ref,rr,bars,spec);assert fill==again;mutations+=1
    t=q.read_trade(q.BASE);z,o,tt,ff,met=x.account(d,t,3000,.0005,schedule,initialcash=200000.)
    assert abs(met['increment']-s[s.id.eq(q.BASE)&s.bp.eq(5)].iloc[0].increment)<1e-5
    for p,h in {**manifests,**frozen}.items():assert b.sha(p)==h,p
    q.js('independent_validation.json',dict(status='PASS',new_saved_accounts=len(checked),reused_account_results=0,scalar_decisions=scalar,prefix_actions=prefix,future_path_mutations=mutations,cross_year_cases=len(cross),parent_files=len(frozen),checks=['independent fees/FIFO/dividend/cash/shares on all saved accounts','six parent baselines x three costs aligned','all three costs same decisions','new low-gap cancellation cannot backfill opening','first completed close, 1pct/2pct/no-stop, deadline and lunch timing','inherited multi-pending/T+1/same-day/cross-year/missing/locked/unresolved cases','actual-path prefix removal and daily/post-fill future mutation','positive initial cash invariance','all fixed parent bytes and computed manifest unchanged']))
    report_tables(s)
    q.js('verification_manifest.json',dict(files={str(p):b.sha(p) for p in R.rglob('*') if p.is_file() and str(p) not in manifests and p.name not in ['manifest.json','verification_manifest.json','calculation.log','verification.log','failure.json']}))
    print('VERIFICATION COMPLETE',len(checked),flush=True)
def new_clock_tests():
    rr=SimpleNamespace(open=99.4,limit_down=90.,limit_up=110.)
    bars={c:dict(open=100.,close=100.,high=106.,low=95.) for c in x.ENDS};bars['09:35'].update(open=99.3,close=99.3);bars['09:45']['open']=99.2
    s=dict(kind='adaptive',gap=None,tp=.005,stop=.02,deadline='11:00')
    fill,_,reason=x.first_buy(100.,rr,bars,s);assert fill[:2]==('09:40',99.2) and reason=='target_close'
    fill,_,_=x.first_buy(100.,rr,bars,{**s,'gap':.005});assert fill[:2]==('09:30',99.3)
    rr.open=100.;bars={c:dict(open=100.,close=100.) for c in x.ENDS};bars['09:35']['close']=101.5;bars['09:40']['close']=102.5
    a=dict(kind='adaptive',gap=None,tp=None,stop=.01,deadline='14:50')
    assert x.first_buy(100.,rr,bars,a)[0][0]=='09:40'
    assert x.first_buy(100.,rr,bars,{**a,'stop':.02})[0][0]=='09:45'
    assert x.first_buy(100.,rr,bars,{**a,'stop':None})[0][0]=='14:50'
    for deadline,observation in [('11:00','10:55'),('14:50','14:45')]:
        bars={c:dict(open=100.,close=100.) for c in x.ENDS};bars[observation]['close']=103.
        fill,_,reason=x.first_buy(100.,rr,bars,{**s,'deadline':deadline});assert fill[0]==deadline and reason=='deadline'
    for clock,want in [('11:25','13:00'),('11:30','13:05')]:
        bars={c:dict(open=100.,close=100.) for c in x.ENDS};bars[clock]['close']=103.
        assert x.first_buy(100.,rr,bars,{**s,'deadline':'14:50'})[0][0]==want
    bars={c:dict(open=100.,close=100.,high=105.,low=95.) for c in x.ENDS}
    assert x.first_buy(100.,rr,bars,s)[2]=='deadline'
    assert x.first_buy(100.,rr,{},s)[0] is None
def report_tables(s):
    leaders=pd.read_csv(R/'leaders.csv');top=list(dict.fromkeys(leaders.id));focus=list(dict.fromkeys([q.BASE,q.ALT]+top))
    blocks=['# B21完整结果审阅表','模型事实：2020年至2026-09-11，3000股旧仓、每笔1000、足额资金，非未来收益或真实成交认证。']
    def add(title,f):blocks.extend(['## '+title,f.to_markdown(index=False,floatfmt='.4f') if len(f) else '无记录'])
    add('全部主成本完整条件',s[s.bp.eq(5)][['id','rule','completed','trade_wins','trade_win','increment','delta_'+q.BASE,'delta_'+q.ALT,'average_profit','average_loss','trade_worst','relative_mdd','pending']])
    add('前列',leaders)
    add('重点三档成本',s[s.id.isin(focus)][['id','bp','completed','trade_win','increment','delta_'+q.BASE,'delta_'+q.ALT,'trade_worst','relative_mdd']])
    for title,file,cols in [('分期','periods.csv',None),('逐年','yearly_trades.csv',None),('年末账户权益','annual_equity_changes.csv',None),('第一类第二类','family_groups.csv',None),('账户桥接','attribution.csv',None),('组合交互','family_interactions.csv',None)]:
        f=pd.read_csv(R/file);add(title,f[f.id.isin(focus)&f.bp.eq(5)])
    edge=pd.read_csv(R/'single_action_edges.csv');add('领先规则单动作替换',edge[edge.from_id.isin(top)&edge.bp.eq(5)])
    add('增益集中度',pd.read_csv(R/'concentration.csv'))
    fine=pd.read_csv(R/'fine_paired_attribution.csv')
    fs=fine.groupby(['id','baseline','family']).agg(n=('entry','size'),both_supported=('both_supported','sum'),new_supported=('new_path_supported','sum'),old_supported=('old_path_supported','sum'),net_change=('change','sum')).reset_index()
    q.save('fine_coverage_summary.csv',fs);add('新旧路径成对覆盖',fs)
    add('重点资源',s[s.id.isin(focus)&s.bp.eq(5)][['id','deposits','peak_requirement','max_single_deposit','max_buy_cash','single_max','minimum_old_shares_unconstrained','inventory_blocked','max_wait_calendar_days','longest_relative_deficit_calendar_days','deposit_yuan_days']])
    (R/'REVIEW_DATA.md').write_text('\n\n'.join(blocks)+'\n')
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:run()
    except Exception:
        q.js('failure.json',dict(run=os.environ.get('GITHUB_RUN_ID'),stage='independent_verification',traceback=traceback.format_exc()));raise
