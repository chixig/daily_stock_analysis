"""Independent B23 saved accounts, scalar selection and causal tests."""
import os,json,functools,traceback
from decimal import Decimal
from types import SimpleNamespace
import numpy as np
import pandas as pd
import foxconn_b23 as v
import foxconn_b21_verify as oldtests
R=v.R
def scalar_state(rows,cref):
    found=[r.close for r in rows.itertuples() if r.clock=='14:50']
    if len(found)!=1:return 'X'
    p=Decimal(str(found[0]));c=Decimal(str(cref))
    if not p.is_finite() or not c.is_finite() or p<=0 or c<=0:return 'X'
    return 'D' if p<c else 'U'
def scalar_choice(rule,family,state):
    if not family:return ''
    acts=v.AM if family=='A' else v.BM;a=acts[rule[family+'_U']];b=acts[rule[family+'_D']]
    return a if a==b or state=='U' else b if state=='D' else 'A1' if family=='A' else 'B1'
def synthetic():
    g=pd.DataFrame([dict(clock='14:50',close=11.99),dict(clock='14:55',close=99.)])
    assert v.state_one(g,11.99)['state']=='U' and v.state_one(g,12.0)['state']=='D'
    assert v.state_one(g.iloc[:0],12.)['state']=='X';assert v.state_one(pd.concat([g,g.iloc[:1]]),12.)['state']=='X'
    for c in [0.,np.nan,np.inf]:assert v.state_one(g,c)['state']=='X'
    st=pd.DataFrame(dict(state=['X','X','U','D','U']));family=pd.Series(['A','B','A','B',''])
    r=dict(A_U=0,A_D=2,B_U=0,B_D=1);got,fb,reason=v.choose(r,st,family)
    assert got.tolist()==['A1','B1','AO','B05',''] and fb.tolist()==[True,True,False,False,False]
    same=dict(A_U=2,A_D=2,B_U=1,B_D=1);assert v.choose(same,st,family)[0].tolist()==['AT','B05','AT','B05','']
    rr=SimpleNamespace(open=99.4,limit_down=90.,limit_up=110.);bars={c:dict(open=99.3,close=99.3) for c in v.x.ENDS}
    opened=v.x.first_buy(100.,rr,bars,dict(kind='open'))[0];gap=v.x.first_buy(100.,rr,bars,dict(kind='adaptive',gap=.005,tp=.005,stop=.02,deadline='11:00'))[0]
    assert opened[:2]==('09:25',99.4) and gap[:2]==('09:30',99.3)
    bars['14:50'].update(open=98.,close=97.);bars['14:55']['open']=96.
    assert v.x.first_buy(100.,rr,bars,dict(kind='adaptive',gap=None,tp=None,stop=None,deadline='14:50'))[0][:2]==('14:50',96.)
    oldtests.inherited_tests.synthetic_tests();oldtests.new_clock_tests()
def run():
    frozen=json.loads((R/'frozen_input_hashes.json').read_text());protected=json.loads((R/'manifest.json').read_text())['files']
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert v.b.sha(p)==h,p
    d,masks,paths,sp,schedule=v.load();m=v.q.load_minutes();st=pd.read_csv(R/'states.csv',parse_dates=['date']).fillna({'family':'','category':''});reg=v.registry();s=pd.read_csv(R/'comparison.csv')
    days={day:g for day,g in m.groupby('date')};empty=m.iloc[:0];independent=[scalar_state(days.get(r.date,empty),r.preclose) for r in d.itertuples()];assert independent==st.state.tolist()
    families=[]
    for i in d.index:
        a=masks['R121'].iloc[i];bb=masks['H01'].iloc[i];families.append('A' if pd.notna(a) and a else 'B' if pd.notna(bb) and bb else '')
    assert families==st.family.tolist();families=pd.Series(families,index=d.index);decisions=0;selections={};expected_entries={}
    for r in reg:
        dec=pd.read_csv(R/f'decisions/{r["id"]}.csv').fillna({'selected_rule':'','family':''});want=[scalar_choice(r,families.iloc[i],independent[i]) for i in d.index]
        assert want==dec.selected_rule.tolist() and dec.family.tolist()==families.tolist();decisions+=len(want);selections[r['id']]=want
        pending=[];entries=[]
        for i,row in d[d.date.ge('2020-01-01')].iterrows():
            bought=sum(pd.notna(k) and int(k)==i for k in pending);pending=[k for k in pending if pd.isna(k) or int(k)!=i]
            if not want[i] or i==len(d)-1 or row.close<=row.limit_down+.005 or row.volume<=0 or len(pending)+bought>=3:continue
            entries.append(i);pending.append(paths[want[i]].loc[i,'exit_i'])
        expected_entries[r['id']]=entries
        for state in ['U','D','X']:
            if r['group']=='constant':assert v.choose(r,st.assign(state=state),families)[0].tolist()==want
    src=(v.q.R/'independent_verifier_runtime.py.txt').read_text();scope=dict(v.b.b17.__dict__);scope['functools']=functools;exec(src,scope);(R/'independent_verifier_runtime.py.txt').write_text(src);checks=[];cross=0;pending_cases=0
    for row in s.itertuples():
        a=pd.read_csv(R/f'accounts/{row.id}_{row.bp}.csv.gz',parse_dates=['date']);o=pd.read_csv(R/f'orders/{row.id}_{row.bp}.csv.gz',parse_dates=['date','entry']);t=v.trade(row.id,row.bp)
        scope['verify'](d,a,o,3000,row.bp/10000,0.,schedule)
        assert abs(a.relative.iloc[-1]-row.increment)<1e-5 and int(t.cash_increment.gt(0).sum())==row.trade_wins
        assert t.entry_i.tolist()==expected_entries[row.id];assert not o[o.side.eq('SELL')].date.duplicated().any()
        for tr in t.itertuples():
            action=selections[row.id][tr.entry_i];assert tr.selected_rule==action and tr.state==independent[tr.entry_i];p=paths[action].loc[tr.entry_i]
            for col in ['buy_ref','exit_i']:
                aa=getattr(tr,col);bb=p[col];assert (pd.isna(aa) and pd.isna(bb)) or abs(aa-bb)<1e-8,(row.id,col)
            for col in ['buy_clock','kind','trigger','path']:assert getattr(tr,col)==p[col]
        need=max([1000*(1+sum((t.entry_i<tr.entry_i)&(t.exit_i.isna()|t.exit_i.ge(tr.entry_i)))) for tr in t.itertuples()],default=1000);assert need<=3000
        if row.bp!=5:pd.testing.assert_frame_equal(t[['entry_i','exit_i','buy_ref','buy_clock','selected_rule','state']],v.trade(row.id)[['entry_i','exit_i','buy_ref','buy_clock','selected_rule','state']])
        if row.bp==5:
            cross+=int((t.entry.dt.year!=t.exit.dt.year).sum());pending_cases+=sum(any((t.entry_i<tr.entry_i)&(t.exit_i>tr.entry_i)) for tr in t.itertuples())
        checks.append(dict(id=row.id,bp=row.bp,days=len(a),orders=len(o),minimum_actual_old_shares=need,status='PASS'))
        if len(checks)%27==0:print('INDEPENDENT',len(checks),flush=True)
    v.save('independent_accounts_verified.csv',checks)
    after=m.copy();after.loc[after.clock.gt('14:50'),['open','high','low','close']]*=1.71;dd=d.copy();dd[['open','high','low','close','volume']]*=1.37
    mutated=v.states(dd,after);prefix=v.states(d,m[m.clock.le('14:50')]);assert mutated.state.tolist()==independent and prefix.state.tolist()==independent
    for r in reg:
        assert v.choose(r,mutated,families)[0].tolist()==selections[r['id']];assert v.choose(r,prefix,families)[0].tolist()==selections[r['id']]
    future_cases=0
    for cutoff in ['2021-01-01','2024-01-01','2026-01-01']:
        dd=d.copy();mm=m.copy();mask=dd.date.ge(cutoff);dd.loc[mask,['open','high','low','close','preclose','volume']]*=1.51;mm.loc[mm.date.ge(cutoff),['open','high','low','close']]*=1.51
        new=v.states(dd,mm)
        for r in reg:
            got=v.choose(r,new,families)[0];assert got[~mask].tolist()==pd.Series(selections[r['id']])[~mask].tolist();future_cases+=1
    synthetic();t=v.trade(v.BASE);_,_,_,_,meta=v.x.account(d,t,3000,.0005,schedule,initialcash=200000.);assert abs(meta['increment']-s[s.id.eq(v.BASE)&s.bp.eq(5)].iloc[0].increment)<1e-5
    edges=pd.read_csv(R/'single_position_edges.csv');assert len(edges)==81*4*2*3;summary=s.set_index(['id','bp'])
    for r in edges.itertuples():assert abs(r.net_change-(summary.loc[(r.to_id,r.bp),'increment']-summary.loc[(r.from_id,r.bp),'increment']))<1e-6
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert v.b.sha(p)==h,p
    v.js('independent_validation.json',dict(status='PASS',new_saved_accounts=243,reused_accounts=0,scalar_state_days=len(d),scalar_decisions=decisions,independent_participation_rules=81,constant_state_invariance=9,post1450_mutation_rules=81,prefix_truncation_rules=81,future_date_mutations=future_cases,main_cross_year_cases=cross,main_new_sale_with_pending_cases=int(pending_cases),parent_files=len(frozen['files']),checks=['independent saved ledgers fee/FIFO/cash/shares/dividends','scalar Decimal states and scalar choice for all rules','independent constrained participation and locked source paths','missing/duplicate/equality fallback, no silent sale filter','planned open versus observed low-gap open','inherited T+1/lunch/delay/locked/missing/multiple/cross-year/unresolved','late data and future days cannot change prior choices','full edge and parent account reconciliation']))
    tables(s);v.js('verification_manifest.json',dict(files={str(p):v.b.sha(p) for p in R.rglob('*') if p.is_file() and str(p) not in protected and p.name not in ['manifest.json','verification_manifest.json','calculation.log','verification.log','failure.json']}))
def tables(s):
    focus=json.loads((R/'focus.json').read_text());blocks=['# B23结果便读表','全部数字为固定历史模型，非未来或竞价成交认证。']
    def add(title,g):blocks.extend(['## '+title,g.to_markdown(index=False,floatfmt='.4f') if len(g) else '无记录'])
    add('全部81主成本',s[s.bp.eq(5)][['id','group','rule','completed','trade_wins','trade_win','increment','delta_'+v.BASE,'delta_'+v.ALT,'best_constant','delta_best_constant','average_profit','average_loss','trade_worst','relative_mdd','pending']])
    add('排名',pd.read_csv(R/'leaders.csv'));add('九恒定三成本',s[s.group.eq('constant')][['id','bp','rule','completed','trade_win','increment','trade_worst','relative_mdd']])
    add('重点三成本',s[s.id.isin(focus)][['id','bp','completed','trade_wins','trade_win','increment','delta_'+v.BASE,'delta_'+v.ALT,'delta_best_constant','trade_mean_pct','trade_worst','relative_mdd']])
    for file,cols in [('periods',['id','bp','period','n','cash','mean_pct']),('yearly_trades',['id','bp','year','n','cash','mean_pct']),('annual_equity_changes',None),('state_account_groups',['id','bp','family','state','n','wins','cash','mean_pct']),('attribution',None),('constant_family_interactions',None)]:
        t=pd.read_csv(R/(file+'.csv'));t=t[t.id.isin(focus)&t.bp.eq(5)];add(file,t[cols] if cols else t)
    for file in ['state_counts','state_action_summary','state_pair_summary','concentration','fine_coverage_summary','fine_covered_uncovered_contributions']:
        t=pd.read_csv(R/(file+'.csv'));add(file,t[t.bp.eq(5)] if 'bp' in t else t)
    add('重点资源',s[s.id.isin(focus)&s.bp.eq(5)][['id','deposits','peak_requirement','max_single_deposit','max_buy_cash','single_max','minimum_old_shares_unconstrained','inventory_blocked','max_wait_calendar_days','longest_relative_deficit_calendar_days','deposit_yuan_days']])
    (R/'REVIEW_DATA.md').write_text('\n\n'.join(blocks)+'\n')
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:run()
    except Exception:v.js('failure.json',dict(stage='independent_verification',run=os.environ.get('GITHUB_RUN_ID'),traceback=traceback.format_exc()));raise
