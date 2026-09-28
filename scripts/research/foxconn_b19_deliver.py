#!/usr/bin/env python3
"""Assemble submitted report from verified account summaries; no new strategy search."""
import os,json,subprocess
from pathlib import Path
import numpy as np,pandas as pd
import foxconn_b19 as b
from foxconn_b19_finalize import desc
R=b.R

def table(df):return df.to_markdown(index=False,floatfmt='.2f').replace('nan','—')
def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true'
 protected={}
 for name in ['manifest.json','verification_manifest.json']:protected.update(json.loads((R/name).read_text())['files'])
 for p,h in protected.items():assert b.b.sha(p)==h,p
 s=pd.concat([pd.read_csv(R/'account_summary.csv'),pd.read_csv(R/'supplemental_account_summary.csv')],ignore_index=True)
 reg={x['id']:x for x in b.registry()};main=s[(s.group=='main')&s.bp.eq(5)].set_index('id');resources=[]
 for a in s.itertuples():
  p=R/f'trades/{a.group}/{a.id}_{int(a.bp)}.csv'
  if not p.exists():continue
  t=pd.read_csv(p);need=max([0]+[1000*int((t.entry_i.le(i)&(t.exit_i.isna()|t.exit_i.ge(i))).sum()) for i in t.entry_i])
  assert need<=3000
  if a.group=='main':assert need==a.minimum_old_shares,(a.id,need,a.minimum_old_shares)
  resources.append(dict(id=a.id,group=a.group,bp=a.bp,minimum_shares_actual=need,prior_summary_value=a.minimum_old_shares,meaning='minimum sellable inventory on actual order dates; accounts still use 3000'))
 b.save('resource_requirements.csv',resources);rr=pd.DataFrame(resources)
 # Rows of the report are sourced directly from already independently verified accounts.
 keys=['H00','H01','H03','R121','R112','W0122','W0022'];front=[]
 labels={'H00':'原H00：14:50回补','H01':'原H01：低开/0.5%目标/1%上涨/10:30','H03':'H03：同H01信号、开盘回补','R121':'收益线收益最佳：20日非负/14:50/1%上涨','R112':'收益线胜率最佳：20日非负/13:30/2%上涨','W0122':'H01收益最佳：低开0.5%/目标1%/涨2%/11:00','W0022':'H01胜率最佳：低开0.5%/目标0.5%/涨2%/11:00'}
 def row(key,a,label,delta):return {'方案':key+' '+label,'次数':int(a.completed),'盈利次数/胜率':f'{int(a.trade_wins)}/{a.trade_win:.2f}%' if a.completed else '0/不定义','累计净增量':a.increment,'比对应基准多赚':delta,'平均每次':a.trade_mean,'最大单亏':max(0,-a.trade_worst) if np.isfinite(a.trade_worst) else np.nan,'收盘相对回撤':-a.relative_mdd}
 for key in keys:
  a=main.loc[key];front.append(row(key,a,labels[key],a.increment-main.loc[reg[key]['line'],'increment']))
 for key,label in [('A_H00_profit','按年选收益'),('A_H00_win','按年选胜率'),('A_H01_profit','H01两条年选轨道合并')]:
  a=s[(s.group=='annual')&s.id.eq(key)&s.bp.eq(5)].iloc[0];basekey=key.split('_')[1];base=s[(s.group=='annual_baseline')&s.id.eq(basekey)&s.bp.eq(5)].iloc[0]
  front.append(row(key,a,label,a.increment-base.increment))
 values={'FRONT_TABLE':table(pd.DataFrame(front))}
 cost=s[s.group.eq('main')&s.id.isin(keys)][['id','bp','increment','trade_win']].copy();cost['baseline']=cost.id.map(lambda k:reg[k]['line'])
 cost['delta']=cost.apply(lambda a:a.increment-s[(s.group=='main')&s.id.eq(a.baseline)&s.bp.eq(a.bp)].iloc[0].increment,axis=1)
 cost=cost.drop(columns='baseline').sort_values(['id','bp']).rename(columns={'id':'方案','bp':'每边滑点bp','increment':'账户净增量','trade_win':'胜率%','delta':'较对应原方案增量'})
 annualcost=s[s.group.eq('annual')&s.id.isin(['A_H00_profit','A_H00_win'])][['id','bp','increment','trade_win']].copy();annualcost['delta']=annualcost.apply(lambda a:a.increment-s[(s.group=='annual_baseline')&s.id.eq('H00')&s.bp.eq(a.bp)].iloc[0].increment,axis=1)
 annualcost=annualcost.rename(columns={'id':'方案','bp':'每边滑点bp','increment':'账户净增量','trade_win':'胜率%','delta':'较对应原方案增量'})
 values['COST_TABLE']=table(cost)+'\n\n年选H00成本对照（与2024起固定H00比较）：\n\n'+table(annualcost)
 p=pd.read_csv(R/'periods.csv');p=p[p.group.eq('main')&p.bp.eq(5)&p.id.isin(keys)][['id','period','n','cash','mean_pct']].rename(columns={'id':'方案','period':'入场时段','n':'笔数','cash':'完成交易净额','mean_pct':'每笔标准化均值%'})
 values['PERIOD_TABLE']=table(p)
 n=pd.read_csv(R/'adjacent_actions.csv');n=n[n.center.isin(['R121','R112','W0122','W0022'])][['center','neighbor','dimension','increment','trade_win','trade_worst']];n['trade_worst']=-n.trade_worst
 n=n.rename(columns={'center':'中心方案','neighbor':'相邻方案','dimension':'改变维度','increment':'账户净增量','trade_win':'胜率%','trade_worst':'最大单亏'});values['NEIGHBOR_TABLE']=table(n)
 a=pd.read_csv(R/'annual_selection.csv');out=[]
 for z in a[a.line.eq('H00')].itertuples():out.append({'主线/轨道':z.line+'/'+z.objective,'执行年':z.test_year,'训练截止':z.cutoff,'选中规则':z.id if z.id=='NONE' else z.id+' '+desc(reg[z.id]),'训练笔数':z.training_n,'训练净额':z.training_net})
 out.append({'主线/轨道':'H01/收益与胜率','执行年':'2024/2025/2026','训练截止':'各上一年最后交易日','选中规则':'NONE（各次均不足40笔）','训练笔数':'17/27/35','训练净额':'不进入同等级选择'})
 # Check the displayed H01 history counts against every candidate's training accounts.
 train=pd.read_csv(R/'training_all_candidates.csv');assert list(train[train.line.eq('H01')].groupby('test_year').completed.first().astype(int))==[17,27,35]
 values['SELECTION_TABLE']=table(pd.DataFrame(out))
 e=s[s.group.eq('early')&s.id.isin(keys)][['id','completed','increment','trade_win','delayed']].rename(columns={'id':'方案','completed':'完成笔数','increment':'净增量','trade_win':'胜率%','delayed':'延后开盘恢复笔数'});values['EARLY_TABLE']=table(e)
 c=s[s.group.eq('combo')][['id','bp','completed','trade_wins','trade_win','increment','trade_worst','relative_mdd']].copy();c['trade_worst']=-c.trade_worst;c['relative_mdd']=-c.relative_mdd
 c=c.rename(columns={'id':'固定组合','bp':'每边滑点bp','completed':'次数','trade_wins':'盈利次数','trade_win':'胜率%','increment':'净增量','trade_worst':'最大单亏','relative_mdd':'相对回撤'});values['COMBO_TABLE']=table(c)
 capital=s[s.bp.eq(5)&((s.group.eq('main')&s.id.isin(keys))|s.group.eq('combo')|(s.group.eq('annual')&s.id.isin(['A_H00_profit','A_H00_win'])))][['id','group','bp','deposits','single_max','longest_relative_deficit_calendar_days']].merge(rr[['id','group','bp','minimum_shares_actual']],on=['id','group','bp']).drop(columns=['group','bp'])
 capital=capital.rename(columns={'id':'方案','deposits':'累计外部补入元','single_max':'单笔最大资金缺口元','longest_relative_deficit_calendar_days':'最长相对现金缺口日历天','minimum_shares_actual':'历史最低可卖股数'});values['CAPITAL_TABLE']=table(capital)
 content=(R/'REPORT_TEMPLATE.md').read_text()
 for k,v in values.items():assert content.count('{{'+k+'}}')==1;content=content.replace('{{'+k+'}}',v)
 assert '{{' not in content
 content=content.replace('足額','足额')
 note='账户旧摘要中年选/组合/部分阈值复核的 `minimum_old_shares` 用3000股比较资源作为默认值；本报告资金表已按逐笔入场、未回补及当日回补不可卖的约束重算，最终最低库存以 `resource_requirements.csv` 为准。该元数据修正不改变任何3000股账户交易、税或收益。'
 content=content.replace('累计外部补入是本模型',note+'\n\n累计外部补入是本模型')
 (R/'REPORT.md').write_text(content)
 (R/'DELIVERY_NOTES.md').write_text('# B19交付说明\n\n状态 submitted。主结果与独立复核固定在 cd8861e3f330e7e2bf3a3e8eedba8390e695068d；本次只整理报告、衍生库存元数据与哈希，没有新增策略搜索或改动收益。\n\n'+note+'\n\n全量明细来源：main manifest、verification manifest；749账户计算（740主批＋9同测试时段基准），其中344保存底稿账户独立复核；405训练账户内部守恒检查。\n')
 for p,h in protected.items():assert b.b.sha(p)==h,p
 newfiles=[R/'REPORT.md',R/'REPORT_TEMPLATE.md',R/'DELIVERY_NOTES.md',R/'resource_requirements.csv']
 js=dict(status='PASS',report_sha256=b.b.sha(R/'REPORT.md'),protected_files=len(protected),resource_rows=len(resources),checks=['report tables derived from verified summaries','main fixed-rule minimum inventory unchanged','all saved accounts actual minimum inventory recalculated <=3000','all protected outputs unchanged','no new parameter search'],code_commit=os.environ['GITHUB_SHA'],run_url=f'https://github.com/chixig/daily_stock_analysis/actions/runs/{os.environ["GITHUB_RUN_ID"]}')
 b.js('delivery_validation.json',js);newfiles.append(R/'delivery_validation.json')
 b.js('delivery_manifest.json',dict(files={str(p):b.b.sha(p) for p in newfiles},code={str(p):b.b.sha(p) for p in [Path(__file__),Path('scripts/research/foxconn_b19.py'),Path('scripts/research/foxconn_b19_finalize.py')]}))
 print(json.dumps(js,ensure_ascii=False),flush=True)
if __name__=='__main__':run()
