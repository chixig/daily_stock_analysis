"""Bounded report tables from saved B22 results, without new candidates."""
import os,json,subprocess,io
import pandas as pd
import foxconn_b22 as z
R=z.R
def run():
    protected={}
    for name in ['manifest.json','verification_manifest.json']:
        protected.update(json.loads((R/name).read_text())['files'])
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert z.b.sha(p)==h,p
    s=pd.read_csv(R/'comparison.csv');leaders=pd.read_csv(R/'leaders.csv');focus=list(dict.fromkeys(list(leaders.id)+['T1_ALL','T05_ALL','T05_A_day_lt']))
    blocks=['# B22最终结果便读表'];core=s[s.bp.eq(5)&s.group.eq('core')]
    def add(title,table):blocks.extend(['## '+title,table.to_markdown(index=False,floatfmt='.4f') if len(table) else '无记录'])
    add('核心全表',core[['id','completed','trade_wins','trade_win','increment','trade_mean_pct','average_profit','average_loss','trade_worst','relative_mdd']])
    add('排名',leaders)
    add('重点成本',s[s.id.isin(focus)][['id','bp','completed','trade_wins','trade_win','increment','trade_worst','relative_mdd']])
    for name,cols in [('periods',['id','period','n','cash','mean_pct']),('yearly_trades',['id','year','n','cash','mean_pct']),('annual_equity_changes',None),('family_groups',['id','family','n','wins','cash','mean_pct'])]:
        t=pd.read_csv(R/(name+'.csv'));t=t[t.id.isin(focus)&t.bp.eq(5)];add(name,t[cols] if cols else t)
    a=pd.read_csv(R/'attribution.csv');add('删单与税桥',a[a.id.isin(focus)&a.bp.eq(5)&a.baseline.eq('T1_ALL')])
    orig='a8e9335b4157908668df8bb4b1411c4e68c13b7d'
    old=pd.read_csv(io.StringIO(subprocess.check_output(['git','show',orig+':'+str(R/'comparison.csv')],text=True)))
    change=s.merge(old,on=['id','bp'],suffixes=('','_first'))
    change=change[(change.increment-change.increment_first).abs().gt(.00001)]
    add('等号修正影响',change[change.bp.eq(5)][['id','completed_first','completed','trade_wins_first','trade_wins','increment_first','increment']])
    z.save('exact_boundary_account_changes.csv',change[['id','bp','completed_first','completed','trade_wins_first','trade_wins','increment_first','increment']])
    f=pd.read_csv(R/'features.csv');fo=pd.read_csv(io.StringIO(subprocess.check_output(['git','show',orig+':'+str(R/'features.csv')],text=True)))
    changed=f.position.ge(.7)!=fo.position.ge(.7);fc=f.loc[changed,['date','p50','h50','l50','position']].copy();fc['original_position']=fo.loc[changed,'position'];add('精确边界日期',fc);z.save('exact_boundary_feature_changes.csv',fc)
    fs=pd.read_csv(R/'fine_feature_comparison.csv');base=z.trade('T1_ALL');fine=fs[fs.feature.eq('day')].set_index('entry_i');rules={r['id']:r for r in z.registry()};det=pd.read_csv(R/'attribution_trades.csv');coverage=[];keydates=[]
    for key in focus:
        r=rules[key];dec=pd.read_csv(R/f'decisions/{key}.csv').set_index(f.index);t=z.trade(key);kept=set(t.entry_i)
        for i in base.entry_i:
            applied=bool(dec.applied.iloc[i]);covered=bool(fine.loc[i,'day_qualified']);keep=i in kept;flip=False
            if covered and applied:
                ff=fs[(fs.entry_i.eq(i))&fs.feature.eq(r['feature'])].iloc[0];flip=bool(ff.flip or ff.availability_flip)
            coverage.append(dict(id=key,entry_i=i,kept=keep,applied=applied,covered=covered,signal_flip=flip))
        dd=det[det.id.eq(key)&det.baseline.eq('T1_ALL')]
        for side,table in [('gain',dd[dd.change.gt(.00001)].nlargest(3,'change')),('loss',dd[dd.change.lt(-.00001)].nsmallest(3,'change'))]:
            for row in table.itertuples():
                feature=r['feature'];ff=fs[(fs.entry_i.eq(row.entry_i))&fs.feature.eq(feature)]
                keydates.append(dict(id=key,side=side,entry=row.entry,status=row.status,change=row.change,covered=bool(fine.loc[row.entry_i,'day_qualified']),feature=feature,old_value=ff.old_value.iloc[0] if len(ff) else None,fine_value=ff.new_value.iloc[0] if len(ff) else None))
    cv=pd.DataFrame(coverage).groupby(['id','kept','applied']).agg(n=('entry_i','size'),covered=('covered','sum'),flips=('signal_flip','sum')).reset_index();z.save('selected_fine_coverage.csv',cv);add('重点新卖出信号覆盖',cv)
    kd=z.save('selected_key_dates.csv',keydates);add('主要贡献日期与覆盖',kd)
    add('资金资源',s[s.id.isin(focus)&s.bp.eq(5)][['id','deposits','peak_requirement','max_single_deposit','max_buy_cash','minimum_old_shares','pending','inventory_blocked','terminal_tax_reserve','max_wait_calendar_days','longest_relative_deficit_calendar_days']])
    regions=pd.read_csv(R/'opposite_direction_regions.csv');add('相反方向亏损区域线索',regions[regions.id.isin(focus)])
    real=[]
    for key in focus:
        t=z.trade(key);real.append(dict(id=key,cross_year=int((t.entry.dt.year!=t.exit.dt.year).sum()),new_sale_with_pending=int(sum(any((t.entry_i<v.entry_i)&(t.exit_i>v.entry_i)) for v in t.itertuples())),same_day_previous_buy_and_new_sale=int(sum(any((t.entry_i<v.entry_i)&(t.exit_i==v.entry_i)) for v in t.itertuples()))))
    add('真实执行覆盖计数',pd.DataFrame(real));z.save('real_execution_counts.csv',real)
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert z.b.sha(p)==h,p
    (R/'DETAILS.md').write_text('\n\n'.join(blocks)+'\n')
    z.js('details_validation.json',dict(status='PASS',protected_results=len(protected),parent_files=len(frozen['files']),new_accounts=0,new_candidates=0,precision_fix_changed_main_accounts=len(change[change.bp.eq(5)]),fine_coverage_purpose='sell signals, not buy fills; attribution uses T1_ALL reference'))
    z.js('details_manifest.json',dict(files={str(p):z.b.sha(p) for p in R.rglob('*') if p.is_file() and str(p) not in protected and p.name not in ['manifest.json','verification_manifest.json','details_manifest.json','calculation.log','verification.log','details.log']}))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true';run()
