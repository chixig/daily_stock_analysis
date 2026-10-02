"""Bounded B23 report evidence and delivery integrity checks on GitHub."""
import os,json,sys
import pandas as pd
import foxconn_b23 as v
R=v.R
def protect():
    assert json.loads((R/'independent_validation.json').read_text())['status']=='PASS'
    counts={}
    for name in ['frozen_input_hashes.json','manifest.json','verification_manifest.json']:
        obj=json.loads((R/name).read_text());files=obj['files'];counts[name]=len(files)
        for p,h in files.items():assert v.b.sha(p)==h,p
    return counts
def details():
    counts=protect();s=pd.read_csv(R/'comparison.csv');leaders=pd.read_csv(R/'leaders.csv');best=json.loads((R/'best_constant.json').read_text())['5']
    picks=leaders[leaders.bp.eq(5)&leaders['rank'].eq(1)].id.tolist();focus=list(dict.fromkeys(picks+[v.BASE,v.ALT,best]));blocks=['# B23交付证据便读摘录','固定历史模型；不改变81规则或243账户；不构成未来或实盘认证。']
    def add(title,g):blocks.extend(['## '+title,g.to_markdown(index=False,floatfmt='.4f') if len(g) else '无记录'])
    def read(name):return pd.read_csv(R/(name+'.csv'))
    def selected(name):
        a=read(name);return a[a.id.isin(focus)&a.bp.eq(5)] if 'bp' in a else a[a.id.isin(focus)]
    meta=dict(protected=counts,picks=picks,focus=focus,all_completed=sorted(s.completed.unique().tolist()),all_pending=sorted(s.pending.unique().tolist()),all_inventory_blocked=sorted(s.inventory_blocked.unique().tolist()),all_old_shares=sorted(s.minimum_old_shares_unconstrained.unique().tolist()),state_counts=read('state_counts').to_dict('records'),fine=json.loads((R/'fine_quality.json').read_text()),independent=json.loads((R/'independent_validation.json').read_text()))
    blocks+=['## 核验总览','```json\n'+json.dumps(meta,ensure_ascii=False,indent=2)+'\n```']
    add('主成本九恒定',s[s.bp.eq(5)&s.group.eq('constant')][['id','rule','completed','trade_wins','trade_win','increment','average_profit','average_loss','trade_worst','relative_mdd']])
    add('全部81主成本简表',s[s.bp.eq(5)][['id','group','trade_wins','trade_win','increment','delta_best_constant','trade_worst','relative_mdd']])
    add('重点三成本',s[s.id.isin(focus)][['id','bp','completed','trade_wins','trade_win','increment','delta_'+v.BASE,'delta_'+v.ALT,'delta_best_constant','trade_mean_pct','average_profit','average_loss','trade_worst','relative_mdd']])
    for name,cols in [('periods',['id','period','n','cash','mean_pct']),('yearly_trades',['id','year','n','cash','mean_pct']),('annual_equity_changes',None),('state_account_groups',['id','family','state','n','wins','cash','mean_pct']),('attribution',None),('constant_family_interactions',None)]:
        a=selected(name);add(name,a[cols] if cols else a)
    for name in ['state_action_summary','state_pair_summary']:
        a=read(name);add(name,a[a.bp.eq(5)])
    add('concentration',selected('concentration'));add('fine_coverage_summary',selected('fine_coverage_summary'));add('fine_covered_uncovered_contributions',selected('fine_covered_uncovered_contributions'))
    a=read('single_position_edges');add('重点单位置变更',a[a.from_id.isin(picks)&a.bp.eq(5)])
    a=selected('key_gain_loss_dates');f=read('fine_paired_attribution');a=a.merge(f[['id','baseline','entry_i','sell_state_covered','both_paths_supported','new_open_proxy','old_open_proxy']],on=['id','baseline','entry_i'],how='left');a=a.groupby(['id','baseline','side'],sort=False).head(5)
    add('关键收益及损失日期',a[['id','baseline','entry','family','state','side','old_rule','new_rule','old_clock','new_clock','old_price','new_price','change','sell_state_covered','both_paths_supported','new_open_proxy','old_open_proxy']])
    f=read('fine_buy_paths');f=f[f.id.isin(focus)&f.path_replayed];f=f.assign(abs_price_difference=f.price_difference.abs()).sort_values('abs_price_difference',ascending=False);add('细分钟价差最大记录',f[['id','entry','action','old_clock','fine_clock','old_price','fine_price','price_difference','clock_match','trigger_match']].head(15))
    add('重点资源',s[s.id.isin(focus)&s.bp.eq(5)][['id','deposits','peak_requirement','max_single_deposit','max_buy_cash','single_max','minimum_old_shares_unconstrained','inventory_blocked','max_wait_calendar_days','longest_relative_deficit_calendar_days','deposit_yuan_days','terminal_tax_reserve']])
    add('重点负区域独立反向扣费线索',selected('opposite_direction_regions'))
    protection=protect();assert protection==counts
    (R/'DETAILS.md').write_text('\n\n'.join(blocks)+'\n');v.js('details_validation.json',dict(status='PASS',protected=counts,picks=picks,focus=focus,details_sha256=v.b.sha(R/'DETAILS.md'),code_sha256=v.b.sha('scripts/research/foxconn_b23_delivery.py')))
def delivery():
    counts=protect();detail=json.loads((R/'details_validation.json').read_text());assert detail['details_sha256']==v.b.sha(R/'DETAILS.md')
    report=(R/'REPORT.md').read_text();s=pd.read_csv(R/'comparison.csv');leads=pd.read_csv(R/'leaders.csv');picks=list(dict.fromkeys(leads[leads.bp.eq(5)&leads['rank'].eq(1)].id.tolist()+[v.BASE,v.ALT]));checks=[]
    for key in picks:
        row=s[s.id.eq(key)&s.bp.eq(5)].iloc[0]
        for col in ['increment','trade_win','trade_worst','relative_mdd']:
            value=abs(row[col]) if col in ['trade_worst','relative_mdd'] else row[col];shown=f'{value:,.2f}';assert shown in report,(key,col,shown);checks.append(dict(id=key,field=col,value=float(row[col]),shown=shown))
    for folder in ['accounts','orders','trades','funds']:assert len(list((R/folder).glob('*')))==243
    assert len(json.loads((R/'registry.json').read_text()))==81
    assert all(pd.read_csv(R/'parent_baseline_alignment.csv').status.eq('PASS'))
    assert 'status: submitted' in report and '2026-09-11' in report
    v.js('report_checks.json',dict(status='PASS',checks=checks))
    v.js('delivery_validation.json',dict(status='PASS',protected=counts,report_sha256=v.b.sha(R/'REPORT.md'),registry_sha256=v.b.sha(R/'registry.json'),protocol_sha256=v.b.sha(R/'PROTOCOL.md'),accounts=243,rules=81,parent_alignments=6,report_numeric_checks=len(checks),data_cutoff='2026-09-11',run=os.environ['GITHUB_RUN_ID']))
    excluded={'delivery_manifest.json','calculation.log','verification.log','failure.json'}
    files={str(p):v.b.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in excluded}
    for p in ['scripts/research/foxconn_b23.py','scripts/research/foxconn_b23_verify.py','scripts/research/foxconn_b23_delivery.py','.github/workflows/foxconn-b23.yml','.github/workflows/foxconn-b23-delivery.yml']:files[p]=v.b.sha(p)
    v.js('delivery_manifest.json',dict(files=files))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    details() if sys.argv[1]=='details' else delivery()
