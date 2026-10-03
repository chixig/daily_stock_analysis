"""B25 final evidence and report; fixed accounts only, no new strategies."""
import os,json
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_b25 as c
R=c.R
def read(name):return pd.read_csv(R/name)
HEAD={'id':'核对编号','reference':'对照','P':'正T贡献','N':'隔夜买贡献','R':'隔夜卖贡献','increment':'净增量','relative_mdd':'收盘做T回撤','absolute_mdd':'收盘全账户回撤','intraday_relative_mdd':'离散盘中做T回撤','intraday_absolute_mdd':'离散盘中全账户回撤','deposits':'累计补款','max_shares':'最高持股','win':'逻辑胜率(%)','worst':'最大单笔损益','worst5':'最差五笔合计','longest_loss':'最长连亏','recovery_days':'最长收盘恢复天数','avg_profit':'盈利笔平均','avg_loss':'亏损笔平均','completed':'完成笔数','pending':'期末未完成','bp':'每边滑点bp','stock':'旧股','period':'年份/分期','delta':'净变化','top1':'最大一日贡献','top3':'最大三日贡献','top5':'最大五日贡献','without1':'其余日合计去一日','without3':'其余日合计去三日','without5':'其余日合计去五日','removed':'少做笔数','avoided_loss':'避免亏损','missed_profit':'错失盈利','actual_change':'实际账户变化','interaction':'其他交互','module':'模块','date':'日期','signals':'信号数','accepted':'已开笔数','policy_rejected':'政策拒绝','inventory_rejected':'库存拒绝','quote_unknown':'缺报价','untradeable':'不可成交','exit_failed':'失败退出次数','max_deposit':'最大单次补款','max_buy_cash':'最大真实买单总款','min_old_available':'最低可卖旧股','deposit_yuan_days':'补款留存元天','max_batch_days':'最长逻辑批次日数','relative_day':'当日做T损益','absolute_day':'当日全账户损益','adjust':'税准备调整','module1':'方向一','module2':'方向二','correlation':'日贡献相关性','both_negative':'同日俱亏天数','reference_cash_change':'参考价现金差','slippage_change':'滑点差','fee_change':'费用差','tax_change':'FIFO税差','terminal_reserve_change':'期末税准备差','dividend_relative_change':'股息权益差','pending_mark_change':'期末估值差','dimension':'变化维度'}
LABEL={'Pclose':'正T收盘卖','Pstop2':'正T完成收价跌2%后延迟卖','P1100':'正T11:00决定/11:05卖','N1000s2':'深跌2%触发/10:00截止','N1000none':'深跌无止损/10:00截止','N0935s2':'深跌2%触发/09:35截止','N0935none':'深跌无止损/09:35截止','F':'全参加','L1':'同向最多一笔','Pall':'四阶段正T','PUR':'上升震荡正T','N2':'深跌2%/10:00','N0':'深跌无止损/10:00','R1':'原隔夜卖回补','Rprofit':'状态切换买回锚点'}
def name(key):return '＋'.join(LABEL[v] for v in key.split('_'))
def table(f,cols=None,names=False):
    f=(f[cols] if cols else f).copy()
    if names and 'id' in f:f.insert(0,'具体动作',f.id.map(name))
    return f.rename(columns=HEAD).to_markdown(index=False,floatfmt='.2f')
def run():
    iv=json.loads((R/'independent_validation.json').read_text());assert iv['status']=='PASS'
    sealed=json.loads((R/'result_sha256.json').read_text())
    for p,h in sealed['files'].items():assert c.sha(p)==h,p
    s=read('account_summary.csv');main=s[s.stock.eq(3000)&s.bp.eq(5)].set_index('id');base=main.loc[c.BASE]
    focus=json.loads((R/'focus.json').read_text())
    front=read('pareto.csv');front=front[front.stock.eq(3000)&front.bp.eq(5)&front.pareto].id
    # Simplicity considers number of new exit definitions/changed module versions plus participation cap.
    ranked=[]
    for k in front:
        rr=main.loc[k]
        complexity=(int(rr.P!='Pclose')+int(rr.N!='N1000s2')+int(rr.policy!='F')) if not rr.anchor else (2 if k=='Pall_N2_R1_F' else 3)
        ranked.append((complexity,-rr.increment,k))
    focus['simple']=sorted(ranked)[0][2]
    highlights=list(dict.fromkeys([focus['profit']]+([focus['risk']] if focus['risk'] else [])+[focus['simple']]))
    focus['highlights']=highlights;focus['highest_win']=main.sort_values(['win','increment'],ascending=False).index[0]
    keys=list(dict.fromkeys([c.BASE,'Pclose_N1000s2_L1']+highlights))
    evidence_keys=list(dict.fromkeys(keys+['Pstop2_N1000s2_F','P1100_N1000s2_F','Pclose_N0935s2_F','Pclose_N0935none_F']))
    c.js('delivery_focus.json',focus)
    # Common-entry reference-price attribution, actual logical allocation and accepted-set effects separate.
    attr=[];riskparts=[]
    for key in main.index:
        if main.loc[key,'anchor']:continue
        ref='Pclose_N1000s2_'+main.loc[key,'policy']
        at=c.read('trades',key+'_3000_5');bt=c.read('trades',ref+'_3000_5')
        ae=c.read('events',key+'_3000_5');be=c.read('events',ref+'_3000_5')
        ax=ae[ae.kind.eq('exit')&ae.reason.eq('filled')].set_index('tid');bx=be[be.kind.eq('exit')&be.reason.eq('filled')].set_index('tid')
        at['key']=at.module+'_'+at.entry;bt['key']=bt.module+'_'+bt.entry;at=at.set_index('key');bt=bt.set_index('key')
        for tid in at.index.intersection(bt.index):
            a=at.loc[tid];b=bt.loc[tid]
            if a.tid not in ax.index or b.tid not in bx.index:continue
            er=ax.loc[a.tid];br=bx.loc[b.tid]
            px=1000*a.direction*(er.reference-br.reference)
            actual=a.realized-b.realized
            earlier=(str(a.actual_exit)+' '+str(a.actual_exit_clock))<(str(b.actual_exit)+' '+str(b.actual_exit_clock))
            attr.append(dict(id=key,reference=ref,key=tid,module=a.module,date=a.entry,earlier=earlier,old_exit=str(b.actual_exit)+' '+str(b.actual_exit_clock),new_exit=str(a.actual_exit)+' '+str(a.actual_exit_clock),exit_price_cash_change=px,avoided_later_decline=max(px,0) if earlier else 0,missed_later_rebound=max(-px,0) if earlier else 0,logical_change=actual,cost_tax_attribution=actual-px))
    c.save('matched_exit_price_attribution.csv',attr)
    agg=pd.DataFrame(attr).groupby(['id','module']).agg(matched=('key','size'),earlier=('earlier','sum'),price_change=('exit_price_cash_change','sum'),avoided_later_decline=('avoided_later_decline','sum'),missed_later_rebound=('missed_later_rebound','sum'),logical_change=('logical_change','sum'),cost_tax_attribution=('cost_tax_attribution','sum')).reset_index()
    c.save('matched_exit_price_summary.csv',agg)
    for key in evidence_keys:
        g=c.read('stress',key+'_3000_5')
        for curve in ['relative','absolute']:
            vals=np.r_[0,g[curve].values];dd=np.maximum.accumulate(vals)-vals;j=int(np.argmax(dd));i=int(np.argmax(vals[:j+1]))
            a=g.iloc[i-1] if i else None;b=g.iloc[j-1] if j else None
            row=dict(id=key,curve=curve,peak='initial0' if not i else str(a.date)+' '+a.clock+' '+a.basis,trough='initial0' if not j else str(b.date)+' '+b.clock+' '+b.basis,drawdown=float(dd[j]))
            for col in ['P','N','R','adjust','hold_absolute']:row[col]=(a[col] if i else 0)-(b[col] if j else 0)
            assert abs(sum(row[v] for v in ['P','N','R','adjust'])+(row['hold_absolute'] if curve=='absolute' else 0)-dd[j])<1e-5
            riskparts.append(row)
    c.save('intraday_risk_attribution.csv',riskparts)
    # Fine-source evidence. No replacement prices and no enlargement of candidate set.
    d,_,_,_,plans=c.load();p=c.c
    raw=pd.read_csv(p.b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);raw['clock']=raw.datetime.dt.strftime('%H:%M')
    expected=[p.b.minutes_after(st,k) for st in p.z.x.STARTS for k in range(1,6)]
    fine={}
    for dt,g in raw.groupby('date'):
        rr=d[d.date.eq(dt)]
        if len(rr)!=1:continue
        rr=rr.iloc[0];g=g.sort_values('clock')
        if list(g.clock)!=expected:continue
        if max(abs(g.open.iloc[0]-rr.open),abs(g.close.iloc[-1]-rr.close),abs(g.high.max()-rr.high),abs(g.low.min()-rr.low))>=.011:continue
        if not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))&(g.volume>=0)).all():continue
        fine[dt]=g.set_index('clock')
    fq=[];fdec=[]
    for key in main.index:
        ev=c.read('events',key+'_3000_5')
        for e in ev[ev.reason.eq('filled')].itertuples():
            dt=pd.Timestamp(e.date);g=fine.get(dt);px=np.nan
            if g is not None:
                if e.basis.startswith('bar_open_'):
                    clock=p.b.minutes_after(e.clock,1)
                    if clock in g.index:px=g.loc[clock,'open']
                elif e.basis.startswith('bar_close_') or e.basis=='daily_close':
                    if e.clock in g.index:px=g.loc[e.clock,'close']
            fq.append(dict(id=key,module=e.module,kind=e.kind,date=e.date,clock=e.clock,basis=e.basis,date_covered=g is not None,quote_compared=np.isfinite(px),auction_unknown=e.basis in ['daily_open','daily_close'],difference=px-e.reference))
    for mode in ['Pstop2','P1100']:
        for t in plans[mode]:
            dt=pd.Timestamp(t['entry']);g=fine.get(dt);newobs=None
            if g is not None:
                fb={k:dict(close=g.loc[k,'close'],volume=g.loc[[p.b.minutes_after(k,-j) for j in range(5)],'volume'].sum()) for k in c.CLOSES}
                newobs=c.pdecision(t,fb,mode)[0]
            fdec.append(dict(module=mode,date=t['entry'],old_observation=t['observation_clock'],fine_observation=newobs,covered=g is not None,changed=g is not None and newobs!=t['observation_clock']))
    ndec=[];days=d.to_dict('records')
    finebars={}
    for dt,g in fine.items():
        fg=[]
        for k in c.CLOSES:
            part=g.loc[[p.b.minutes_after(k,-j) for j in range(4,-1,-1)]]
            fg.append(dict(clock=k,open=float(part.open.iloc[0]),high=float(part.high.max()),low=float(part.low.min()),close=float(part.close.iloc[-1]),volume=float(part.volume.sum())))
        finebars[dt]=fg
    for mode,stop in [('N0935s2',.02),('N0935none',None)]:
        for t in plans[mode]:
            entry=pd.Timestamp(t['entry']);obs=pd.Timestamp(t.get('observation_date',t['entry']))
            needed=d.loc[(d.date>entry)&(d.date<=obs),'date']
            covered=entry in fine and len(needed)>0 and all(dt in fine for dt in needed)
            xx={}
            if covered:xx=p.n11.morning_exit(t['entry_price'],days,finebars,t['entry_i']+1,'09:35',stop)
            changed=covered and (xx.get('clock')!=t.get('observation_clock') or xx.get('actual_exit')!=obs or xx.get('reason')!=t.get('trigger'))
            ndec.append(dict(module=mode,date=t['entry'],decision_date=str(obs.date()),old_observation=t.get('observation_clock'),fine_observation=xx.get('clock'),covered=covered,changed=changed))
    c.save('fine_N_decision_checks.csv',ndec)
    c.save('fine_quote_checks.csv',fq);c.save('fine_P_decision_checks.csv',fdec)
    qf=pd.DataFrame(fq);summary=qf.groupby(['id','module','kind']).agg(n=('date','size'),date_covered=('date_covered','sum'),quotes_compared=('quote_compared','sum'),auction_unknown=('auction_unknown','sum'),max_abs_difference=('difference',lambda x:x.abs().max())).reset_index();c.save('fine_quote_summary.csv',summary)
    kd=read('key_dates.csv');wk=read('worst_daily_contributions.csv');target=[]
    for key in evidence_keys:
        vals=set(pd.to_datetime(kd[kd.id.eq(key)&kd.bp.eq(5)].date))|set(pd.to_datetime(wk[wk.id.eq(key)].date))
        pairs=c.read('pairs',key+'_3000_5')
        if len(pairs):vals|=set(pd.to_datetime(pairs.date))
        for dt in vals:target.append(dict(id=key,date=dt,fine_available=dt in fine))
    c.save('focus_date_coverage.csv',target)
    # Direct edge cases complement the main new-engine and inherited shared-account tests.
    t=dict(entry_price=100.,exit_price=100.,tid='x',entry='2026-01-05')
    bar=lambda x,v=100:dict(open=x,high=x,low=x,close=x,volume=v)
    assert c.pplan(t,{'11:30':bar(98)},'Pstop2')['exit_attempts'][0]['clock']=='13:05'
    assert c.pplan(t,{'14:55':bar(1)},'Pstop2')['exit_attempts'][0]['clock']=='15:00'
    assert c.pdecision(t,{'09:40':bar(98.0000001)},'Pstop2')[0] is None
    c.js('delivery_validation.json',dict(status='PASS',accounts=len(s),fine_days=len(fine),new_candidates=0,tests=['lunch_first_next_complete_bar','post1450_cannot_trigger','strict_above2pct_no_trigger','all_sealed_result_hashes','matched_price_vs_allocated_profit_bridge','peak_trough_module_and_baseline_bridge']))
    cols=['id','increment','relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd','deposits','max_shares']
    best=main.loc[focus['profit']];cap=main.loc['Pclose_N1000s2_L1'];risk=main.loc[focus['risk']] if focus['risk'] else None
    comp=read('comparisons.csv');per=read('periods.csv');costleaders=pd.concat([g.sort_values(['increment','id'],ascending=[False,True]).head(1) for _,g in s[s.stock.eq(3000)].groupby('bp')]);c.save('cost_leaders.csv',costleaders)
    core=main[~main.anchor].sort_values('increment',ascending=False);newbest=core.iloc[0]
    pnames=['Pclose_N1000s2_F','Pstop2_N1000s2_F','P1100_N1000s2_F']
    nnames=['Pclose_N1000s2_F','Pclose_N1000none_F','Pclose_N0935s2_F','Pclose_N0935none_F']
    txt=['# B25买入方向退出与组合盘中回撤研究报告',
    '【事实】状态submitted，待统筹审核。固定行情截至2026-09-11，2022年首个交易日起统一3000研究旧股、初始现金0、每笔1000且必要补款；主成本每边0.05%滑点另加费用及FIFO股息税。净增量相对同资源同流量持有，不是年收益或实际持仓收益。所有金额单位元。',
    f'**【模型事实】原重点基线净增量{base.increment:,.2f}；收盘做T/全账户回撤{base.relative_mdd:,.2f}/{base.absolute_mdd:,.2f}；本轮统一网格离散盘中做T/全账户回撤{base.intraday_relative_mdd:,.2f}/{base.intraday_absolute_mdd:,.2f}；累计补款{base.deposits:,.2f}、最高持股{int(base.max_shares)}。**',
    f'**固定27条规则中利润最多：{name(focus["profit"])}，净{best.increment:,.2f}；24条买入退出主矩阵利润最多为{name(newbest.name)}，净{newbest.increment:,.2f}。** 两者分别明确，三锚点没有成为可新增的优化维度。',
    (f'**降低两种盘中回撤的非支配取舍：{name(focus["risk"])}。** 相对重点基线多/少赚{risk.increment-base.increment:,.2f}；收盘两回撤变化{risk.relative_mdd-base.relative_mdd:,.2f}/{risk.absolute_mdd-base.absolute_mdd:,.2f}；离散盘中两回撤变化{risk.intraday_relative_mdd-base.intraday_relative_mdd:,.2f}/{risk.intraday_absolute_mdd-base.intraday_absolute_mdd:,.2f}；补款{risk.deposits:,.2f}。负的回撤变化表示改善。' if risk is not None else '**未找到同时降低重点基线两种盘中回撤的非支配方案；不强造“更稳”赢家。**'),
    '【研究判断】本轮新增提前退出未形成值得替换重点基线的组合。正T完成收价跌2%后卖，显著少赚而全账户盘中回撤不降；正T11:00后卖虽降低做T盘中回撤，却使全账户盘中回撤变大。深跌买提前到09:35截止也没有同时降低两种盘中回撤。保留原上升/震荡正T收盘卖＋原深跌2%/10:00退出＋原隔夜卖回补全参加作研究基线；这是本轮有限候选的否定结果，不证明所有提前退出都无效。',
    '## 一、利润与四种回撤的直接取舍',
    table(main.loc[keys].reset_index(),cols,True),
    '比较中始终保留原重点基线及原L1；最多三个非重复突出取舍见delivery_focus.json。非支配同时考虑利润、四种回撤、补款和最高股数，没有自设利润代价阈值或加权总分。简单取舍以改动退出定义和参与限制较少者优先，不能凭简单名称保证风险更低。',
    table(main.loc[evidence_keys].reset_index(),['id','completed','win','avg_profit','avg_loss','worst','worst5','longest_loss','recovery_days','winning_day_pct']),
    f'最高逻辑胜率另看“{name(focus["highest_win"])}”：{main.loc[focus["highest_win"],"win"]:.2f}%，净{main.loc[focus["highest_win"],"increment"]:,.2f}、最大单笔{main.loc[focus["highest_win"],"worst"]:,.2f}。单笔盈亏受共享订单成本分配影响，完整账利润优先；高胜率不等于更值得采用。',
    '## 二、提前退出是否优于限制参与',
    table(main.loc[pnames].reset_index(),cols,True),
    table(main.loc[nnames].reset_index(),cols,True),
    table(main[~main.anchor].reset_index(),cols+['policy'],True),
    f'只改正T跌2%提前退出：相对基线净变化{main.loc["Pstop2_N1000s2_F","increment"]-base.increment:,.2f}，做T盘中回撤变化{main.loc["Pstop2_N1000s2_F","intraday_relative_mdd"]-base.intraday_relative_mdd:,.2f}，全账户盘中回撤变化{main.loc["Pstop2_N1000s2_F","intraday_absolute_mdd"]-base.intraday_absolute_mdd:,.2f}。只改正T11:00后退出：相应变化{main.loc["P1100_N1000s2_F","increment"]-base.increment:,.2f}、{main.loc["P1100_N1000s2_F","intraday_relative_mdd"]-base.intraday_relative_mdd:,.2f}、{main.loc["P1100_N1000s2_F","intraday_absolute_mdd"]-base.intraday_absolute_mdd:,.2f}。',
    f'只改深跌含2%触发的截止为09:35：少赚{base.increment-main.loc["Pclose_N0935s2_F","increment"]:,.2f}；收盘做T回撤少{base.relative_mdd-main.loc["Pclose_N0935s2_F","relative_mdd"]:,.2f}，但盘中做T回撤基本相同，全账户盘中回撤多{main.loc["Pclose_N0935s2_F","intraday_absolute_mdd"]-base.intraday_absolute_mdd:,.2f}。改09:35且无止损则少赚{base.increment-main.loc["Pclose_N0935none_F","increment"]:,.2f}，全账户盘中回撤只少{base.intraday_absolute_mdd-main.loc["Pclose_N0935none_F","intraday_absolute_mdd"]:,.2f}，做T盘中回撤不变。',
    '以上主矩阵完整列出24条，不只挑赢家。相邻规则完整证据在adjacent_rules.csv，每次只改变P退出、N退出或F/L1一个维度；与原退出L1对照及相同退出F的差异在comparisons.csv。改变两种退出后的组合不能把两个单项改善直接相加。',
    table(read('policy_opportunity_cost.csv')[lambda x:x.stock.eq(3000)&x.bp.eq(5)]),
    '避损与错失盈利取各规则对应F账户被删逻辑批次，其余交互保留；同向名额与真实净额共同重算。政策从不阻止退出，失败不释放名额。',
    '## 三、早卖少亏与错失反弹从哪里来',
    '以下归因、年份、成本及覆盖表同时保留未获选的单项提前退出，以解释失败；这些诊断对照不是新增最终推荐。',
    table(agg[agg.id.isin(evidence_keys)]),
    'matched_exit_price_attribution.csv逐笔用同入场日期/方向比较真实退出参考价；正的早卖价差是避免后续下跌，负值是错失随后较好价格。不是根据事后走势选择退出。实际逻辑利润变化减价差，保留费用/税与分摊交互；新增/拒绝的参与差另在exit_opportunity_cost.csv，不能只把匹配交易差额说成总账改变。',
    table(comp[comp.stock.eq(3000)&comp.bp.eq(5)&comp.id.isin(evidence_keys)&comp.reference.eq(c.BASE)],['id','increment','reference_cash_change','slippage_change','fee_change','tax_change','terminal_reserve_change','dividend_relative_change','pending_mark_change']),
    '桥接恒等式：净变化=参考价现金差−滑点差−费用差−FIFO税差−期末准备差＋权益差＋期末未完成估值差。配对减少也可能增加费用或补款，不以早卖必然省钱作前提。',
    '## 四、盘中亏损来源与共同观察网格',
    table(pd.DataFrame(riskparts)),
    '每行在该曲线自己的峰/谷之间分解。正值贡献回撤、负值抵消回撤；做T回撤等于P/N/R/税准备变化合计，全账户还加同流量持有底仓损益变化。不同曲线峰谷不必同日，不能混加不同峰谷损失。',
    table(read('daily_correlations.csv')[lambda x:x.id.isin(evidence_keys)]),
    table(read('worst_daily_contributions.csv')[lambda x:x.id.isin(evidence_keys)]),
    table(read('B24_grid_bridge.csv')),
    '本轮所有账户采用同一组grid_id，包含无交易日及早卖后的全部观察点，按同刻同报价交易后的状态估值；完成bar收价在随后bar开价之前。日线开/收与分钟报价语义不同，均保留来源，不用高低价拼未知走势。覆盖见grid_coverage.json及grid_missing.csv；缺口不前填，日终账不删日。本轮重估锚点与旧B24离散口径桥单列，不能直接跨口径比较。离散最大回撤不是连续最大浮亏或真实成交上限。',
    json.dumps(json.loads((R/'grid_coverage.json').read_text()),ensure_ascii=False),
    '## 五、年份、成本和集中性',
    table(s[s.stock.eq(3000)&s.id.isin(evidence_keys)],['id','bp']+cols[1:],True),
    table(per[per.stock.eq(3000)&per.bp.eq(5)&per.id.isin(evidence_keys)]),
    table(costleaders,cols+['bp'],True),
    table(read('concentration.csv')[lambda x:x.stock.eq(3000)&x.bp.eq(5)&x.id.isin(evidence_keys)]),
    '集中性以相对重点基线的每日贡献诊断，去最大1/3/5日后的其余合计不是删交易后重跑。所有规则各年和2022—2023/2024/2025/2026及三成本完整保存，不按每年事后冠军切换；同历史已反复查看，不称样本外。',
    '## 六、资源和细数据未知',
    table(main.loc[evidence_keys].reset_index(),['id','signals','accepted','completed','pending','policy_rejected','inventory_rejected','quote_unknown','untradeable','exit_failed','deposits','max_deposit','max_buy_cash','max_shares','min_old_available','max_batch_days','deposit_yuan_days']),
    json.dumps(json.loads((R/'resource_lock.json').read_text()),ensure_ascii=False),
    '补款不是全部本金，3000旧股底仓价值另在账中；卖出回款留存可用于买回。真实残余净卖检查旧股，内部配对不变税龄、不生成可卖股。所有资源候选公平，K测量先于利润排名。',
    table(summary[summary.id.isin(evidence_keys)]),
    table(pd.DataFrame(fdec).groupby('module').agg(n=('date','size'),covered=('covered','sum'),changed=('changed','sum')).reset_index()),
    table(pd.DataFrame(ndec).groupby('module').agg(n=('date','size'),covered=('covered','sum'),changed=('changed','sum')).reset_index()),
    '合格细数据仅使用继承93日，报价差、触发变化与未覆盖分开，未替换有利价格。入口/退出quote覆盖不自动等于竞价认证；N早退仍继承B11/B12低价触发及延迟代理，覆盖只说明相应字段可核对。关键增益/损失、共同大亏及净额日期见focus_date_coverage.csv。未覆盖区间、分钟内先后与竞价队列仍未知。',
    '## 七、完整规则和验证边界',
    'P仅上升/震荡：上升阶段昨日收盘在振幅下方40%以内（严格<40%）且今日较昨收参考低开至少1%；震荡阶段截至昨日连跌至少3日，昨日量/含昨日20日均量<0.80。阶段沿用冻结滞后算法，每日一阶段，09:35开始区间开价买1000。P收盘原退出；P止损为买入后09:40至14:50完成5分钟收价≤原始买价×0.98首次触发，再下一个完整bar收价卖；P定时11:00决定、通常11:05卖。目标缺失/无量/不可卖继续后续完整bar至14:55，再日线收盘，仍失败次日合规开盘；不重复退出，不用当天新股外卖。',
    'N前一交易日20日累计收益≤−16.1565018%，今日收盘买1000。四种为10:00/09:35截止分别配父2%触发或无止损，原B12下一完整bar收价延迟退出，通常10:05/09:40。N2沿用父跳空/低价/已知权益触发，与新增P按完成收价跌2%不同，2%均非保证亏损上限。新N只改截止，不继承无关特征完整性删单。',
    'R固定原两入口与买回：A昨日顶部20%、量≤昨日之前20日均量且20日累计涨幅≥0，否则B昨日3日累计跌至少4%且顶部30%。收盘卖1000，A优先；A次日涨1%否则14:50，B低开至少0.5%观察后最早09:30，否则跌1%/涨2%及11:00截止。完整延迟及失败恢复继承。三锚点另含原P四阶段或R利润版，只作冻结比较，不与主矩阵混称新退出创新。',
    'F全部有效机会；L1加股P/N最多一笔、减股R另最多一笔未完成逻辑批次。退出优先，失败保留名额；新开按已知先后、同刻P/N/R。只有同刻同报价且事先已知意图配对，残余外单才改现金/股数/FIFO并收费。持有账同流量，外部补款从账户损益剔除。',
    f'【验证事实】{iv["accounts"]}账户全部独立逐日及共同网格重放；每账户{iv["intraday_points_per_account"]}盘中观察点，合计{iv["total_intraday_points"]}点。21组旧规则三成本逐日、实际净单/逻辑归属/股票批次对齐；父哈希保护、逐笔新路径因果检查、新账户前缀及合成边界通过。独立是第二份程序从真实净订单重建，不是独立行情认证。',
    '【观点】仅在固定候选历史中比较利润代价与四种回撤。新增时间/2%参数来自事前研究设计，不是已证实规律。若可靠成交、成本、权益或后续历史使优势消失，应针对受影响结论复核；不新增未经用户授权的硬收益/风险门槛，也不自动采用、交易或开启B26。',
    '[固定账户证据](https://github.com/chixig/daily_stock_analysis/tree/'+os.environ['GITHUB_SHA']+'/research/foxconn_t0_20261003_b25)，最终交付提交/运行/失败修正与独立SHA见本地执行交接。']
    (R/'DELIVERY.md').write_text('---\nid: foxconn-t0-b25-report\ntitle: B25买入方向退出与组合盘中回撤研究报告\ntype: project\nstatus: submitted\ngraph: false\ndirection_id: foxconn-t0\ncontent_id: foxconn-t0-20261003-b25\ncreated: 2026-10-03\nupdated: 2026-10-03\nneed_review: true\n---\n\n'+'\n\n'.join(txt)+'\n')
    for path,h in sealed['files'].items():assert c.sha(path)==h,path
    c.js('delivery_sha256.json',dict(code_sha=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],files={str(p):c.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['delivery_sha256.json','calculation.log','verification.log','delivery.log']}))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    run()
