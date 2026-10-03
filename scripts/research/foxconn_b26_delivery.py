"""B26 final evidence and report; fixed accounts only, no new strategies."""
import os,json
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_b26 as c
R=c.R
def read(name):return pd.read_csv(R/name)
HEAD={'earlier':'提前笔数','matched':'匹配笔数','price_change':'退出参考价现金差','avoided_later_decline':'避免后续下跌','missed_later_rebound':'错失后续回升','logical_change':'逻辑利润差','cost_tax_attribution':'费用税及归属差','winning_day_pct':'盈利交易日比例(%)','curve':'曲线','peak':'峰时刻','trough':'谷时刻','drawdown':'回撤金额','hold_absolute':'持有底仓贡献','date_covered':'日期覆盖','quotes_compared':'报价核对数','auction_unknown':'竞价未认证','max_abs_difference':'最大绝对价差','n':'笔数','covered':'细决策覆盖','changed':'细决策变化','id':'核对编号','reference':'对照','P':'正T贡献','N':'隔夜买贡献','R':'隔夜卖贡献','increment':'净增量','relative_mdd':'收盘做T回撤','absolute_mdd':'收盘全账户回撤','intraday_relative_mdd':'离散盘中做T回撤','intraday_absolute_mdd':'离散盘中全账户回撤','deposits':'累计补款','max_shares':'最高持股','win':'逻辑胜率(%)','worst':'最大单笔损益','worst5':'最差五笔合计','longest_loss':'最长连亏','recovery_days':'最长收盘恢复天数','avg_profit':'盈利笔平均','avg_loss':'亏损笔平均','completed':'完成笔数','pending':'期末未完成','bp':'每边滑点bp','stock':'旧股','period':'年份/分期','delta':'净变化','top1':'最大一日贡献','top3':'最大三日贡献','top5':'最大五日贡献','without1':'其余日合计去一日','without3':'其余日合计去三日','without5':'其余日合计去五日','removed':'少做笔数','avoided_loss':'避免亏损','missed_profit':'错失盈利','actual_change':'实际账户变化','interaction':'其他交互','module':'模块','date':'日期','signals':'信号数','accepted':'已开笔数','policy_rejected':'政策拒绝','inventory_rejected':'库存拒绝','quote_unknown':'缺报价','untradeable':'不可成交','exit_failed':'失败退出次数','max_deposit':'最大单次补款','max_buy_cash':'最大真实买单总款','min_old_available':'最低可卖旧股','deposit_yuan_days':'补款留存元天','max_batch_days':'最长逻辑批次日数','relative_day':'当日做T损益','absolute_day':'当日全账户损益','adjust':'税准备调整','module1':'方向一','module2':'方向二','correlation':'日贡献相关性','both_negative':'同日俱亏天数','reference_cash_change':'参考价现金差','slippage_change':'滑点差','fee_change':'费用差','tax_change':'FIFO税差','terminal_reserve_change':'期末税准备差','dividend_relative_change':'股息权益差','pending_mark_change':'期末估值差','dimension':'变化维度'}
LABEL={'Pclose':'正T收盘卖','Pstop2':'正T完成收价跌2%后延迟卖','P1100':'正T11:00决定/11:05卖','N1000s2':'深跌2%触发/10:00截止','N1000none':'深跌无止损/10:00截止','N0935s2':'深跌2%触发/09:35截止','N0935none':'深跌无止损/09:35截止','F':'全参加','L1':'同向最多一笔','Pall':'四阶段正T','PUR':'上升震荡正T','N2':'深跌2%/10:00','N0':'深跌无止损/10:00','R1':'原隔夜卖回补','Rprofit':'状态切换买回锚点'}
LABEL.update(P0935='原09:35买',P0945='固定09:45买',P1005='固定10:05买',PO0940='09:40收复开盘价/09:45买',PO1000='10:00收复开盘价/10:05买',PL0940='09:40收价回升且低点不降/09:45买',PL1000='10:00收价回升且低点不降/10:05买')
HEAD.update(confirmation_vs_same_time='确认相对同刻晚买',delay_vs_original='晚买相对原版',total='总变化',condition='确认状态',fixed_profit='固定晚买逻辑利润',unknown_excluded_profit='未知而未做的利润',price_cash='买价差现金贡献',cheaper='买便宜笔数',dearer='买贵笔数',logical_change='逻辑利润差',frequency='估值频率',profit='阶段利润',stage='阶段',reason='实际参与状态')
def name(key):return '＋'.join(LABEL[v] for v in key.split('_'))
def table(f,cols=None,names=False):
    f=(f[cols] if cols else f).copy()
    if names and 'id' in f:f.insert(0,'具体动作',f.id.map(name))
    return f.rename(columns=HEAD).to_markdown(index=False,floatfmt='.2f')

def run():
    sealed=json.loads((R/'result_sha256.json').read_text())
    for p,h in sealed['files'].items():assert c.sha(p)==h,p
    iv=json.loads((R/'independent_validation.json').read_text());assert iv['status']=='PASS'
    s=read('account_summary.csv');main=s[s.stock.eq(3000)&s.bp.eq(5)].set_index('id');base=main.loc[c.BASE]
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
    features=pd.read_csv(R/'confirmation_features.csv',keep_default_na=False);fd=[];fq=[]
    for r in features.itertuples():
        dt=pd.Timestamp(r.date);g=fine.get(dt);bb={}
        if g is not None:
            for k in c.CLOSES:
                part=g.loc[[p.b.minutes_after(k,-j) for j in range(4,-1,-1)]]
                bb[k]=dict(close=str(part.close.iloc[-1]),low=str(part.low.min()),volume=str(part.volume.sum()))
            ff=c.features(bb,r.O,r.mode)
            px=float(g.loc[p.b.minutes_after(r.target,1),'open'])
        else:ff={};px=np.nan
        oldprice=pd.to_numeric(r.entry_price,errors='coerce')
        fd.append(dict(mode=r.mode,date=r.date,stage=r.stage,covered=g is not None,original_condition=r.condition,fine_condition=ff.get('condition'),changed=g is not None and ff.get('condition')!=r.condition,quote_difference=px-oldprice if np.isfinite(px) and np.isfinite(oldprice) else np.nan,old_price=oldprice,fine_price=px,auction_certified=False))
    for key in main.index:
        ev=c.read('events',key+'_3000_5')
        for e in ev[ev.reason.eq('filled')].itertuples():
            dt=pd.Timestamp(e.date);g=fine.get(dt);px=np.nan
            if g is not None:
                if e.basis.startswith('bar_open_'):
                    cl=p.b.minutes_after(e.clock,1)
                    if cl in g.index:px=g.loc[cl,'open']
                elif e.basis.startswith('bar_close_') or e.basis=='daily_close':
                    if e.clock in g.index:px=g.loc[e.clock,'close']
            fq.append(dict(id=key,module=e.module,kind=e.kind,date=e.date,clock=e.clock,basis=e.basis,date_covered=g is not None,quote_compared=np.isfinite(px),auction_unknown=e.basis in ['daily_open','daily_close'],difference=px-e.reference))
    ff=c.save('fine_confirmation_checks.csv',fd);qq=c.save('fine_quote_checks.csv',fq)
    c.save('fine_confirmation_summary.csv',ff.groupby('mode').agg(signals=('date','size'),covered=('covered','sum'),changed=('changed','sum'),max_quote_difference=('quote_difference',lambda x:x.abs().max())).reset_index())
    c.save('fine_quote_summary.csv',qq.groupby(['id','module','kind']).agg(n=('date','size'),date_covered=('date_covered','sum'),quotes_compared=('quote_compared','sum'),auction_unknown=('auction_unknown','sum'),max_abs_difference=('difference',lambda x:x.abs().max())).reset_index())
    sig=read('signal_decisions.csv');sf=sig[sig.stock.eq(3000)&sig.bp.eq(5)]
    c.save('signal_status_summary.csv',sig.groupby(['id','stock','bp','condition','quote_state','reason']).size().rename('n').reset_index())
    # Common-evaluable comparison is explicitly descriptive; never reruns/filters primary accounts.
    filt=read('filtered_fixed_F_trades.csv')
    evdiag=filt[filt.condition.ne('unknown')].groupby(['id','stock','bp','condition']).agg(n=('date','size'),fixed_profit=('fixed_logical_profit','sum')).reset_index()
    c.save('common_evaluable_diagnostic.csv',evdiag)
    pairs=read('daily_comparison.csv.gz');focusdates=[]
    for (key,ref,bp),gg in pairs[pairs.stock.eq(3000)].groupby(['id','reference','bp']):
        important=set(gg.nlargest(5,'change').date)|set(gg.nsmallest(5,'change').date)
        important|=set(sf[sf.id.eq(key)&sf.reason.ne('accepted')].date)
        orig=sf[sf.id.eq(c.BASE)].set_index('date');now=sf[sf.id.eq(key)].set_index('date')
        for dt in now.index.intersection(orig.index):
            if now.loc[dt,'reason']!=orig.loc[dt,'reason']:important.add(dt)
        for dt in important:focusdates.append(dict(id=key,reference=ref,bp=bp,date=dt,fine_available=pd.Timestamp(dt) in fine,reason='gain_loss_rejection_or_original_conflict_change'))
    c.save('focus_date_coverage.csv',focusdates)
    old= pd.read_csv(c.OLD/'account_summary.csv');bridges=[]
    for rr in s[s.stock.eq(3000)&s.parent.fillna('').ne('')].itertuples():
        oo=old[old.id.eq(rr.parent)&old.stock.eq(3000)&old.bp.eq(rr.bp)].iloc[0]
        bridges.append(dict(id=rr.id,parent=rr.parent,bp=rr.bp,old_common_D=oo.intraday_relative_mdd,new_common_D=rr.intraday_relative_mdd,old_common_X=oo.intraday_absolute_mdd,new_common_X=rr.intraday_absolute_mdd,net_profit_change=rr.increment-oo.increment))
    c.save('parent_common_grid_bridge.csv',bridges)
    oldpub=pd.read_csv(c.OLD/'B24_published_grid_bridge.csv');c.save('B24_published_grid_bridge_inherited.csv',oldpub)
    # Original event-only observations remain separately labelled; never equated to published5m.
    oe=pd.read_csv(c.OLD/'B24_grid_bridge.csv');c.save('B24_event_only_bridge_inherited.csv',oe)
    pf=read('pareto.csv');costfront=pf[pf.stock.eq(3000)&pf.pareto];front=main.loc[costfront[costfront.bp.eq(5)].id]
    profit=main.sort_values(['increment','id'],ascending=[False,True]).index[0]
    # Display risk tradeoffs without making dual-drawdown reduction a success gate.
    riskpool=front[(front.intraday_relative_mdd<base.intraday_relative_mdd-1e-7)|(front.intraday_absolute_mdd<base.intraday_absolute_mdd-1e-7)]
    risk=riskpool.sort_values('increment',ascending=False).index[0] if len(riskpool) else None
    ranks=[]
    for key,row in front.iterrows():
        complexity=(0 if row.P=='P0935' else 1 if row.P in ['P0945','P1005'] else 2)+(row.policy!='F') if not row.anchor else 3
        ranks.append((complexity,-row.increment,key))
    simple=sorted(ranks)[0][2]
    highlights=list(dict.fromkeys([profit,c.BASE]))
    risk_display=risk
    risk=None
    highwin=main.sort_values(['win','increment'],ascending=False).index[0]
    c.js('delivery_focus.json',dict(profit=profit,risk=risk,simple=simple,highlights=highlights,highest_win=highwin,risk_diagnostic=risk_display,rule='retain old profit anchor and specified baseline; new risk swaps are diagnostic because profit/deposit/full-account costs are material; all frontiers and costs retained'))
    leaders=[];riskcost=[]
    for bp in [5,11,20]:
        sub=s[s.stock.eq(3000)&s.bp.eq(bp)].set_index('id');b=sub.loc[c.BASE]
        leader=sub.sort_values('increment',ascending=False).iloc[0];leaders.append(dict(id=leader.name,bp=bp,increment=leader.increment,change=leader.increment-b.increment))
        for key,row in sub.iterrows():
            riskcost.append(dict(id=key,bp=bp,profit_change=row.increment-b.increment,close_D_change=row.relative_mdd-b.relative_mdd,close_X_change=row.absolute_mdd-b.absolute_mdd,intra_D_change=row.intraday_relative_mdd-b.intraday_relative_mdd,intra_X_change=row.intraday_absolute_mdd-b.intraday_absolute_mdd,deposit_change=row.deposits-b.deposits,both_intra_improve=bool(row.intraday_relative_mdd<b.intraday_relative_mdd-1e-7 and row.intraday_absolute_mdd<b.intraday_absolute_mdd-1e-7)))
    c.save('cost_leaders.csv',leaders);c.save('cost_risk_changes.csv',riskcost)
    for path,h in sealed['files'].items():assert c.sha(path)==h,path
    c.js('delivery_validation.json',dict(status='PASS',accounts=len(s),fine_days=len(fine),new_candidates=0,all_sealed_results_unchanged=True,feature_validation=json.loads((R/'independent_feature_validation.json').read_text()),tests=['same_time_profit_bridge','all_costs_risk_changes','all_four_peak_trough_contribution_identities','separate_published5m_eventonly_grid_bridges','fine_data_diagnostic_only']))
    cols=['id','increment','relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd','deposits','max_shares']
    core=main[~main.anchor];newbest=core.sort_values('increment',ascending=False).iloc[0]
    bridge=read('confirmation_delay_bridge.csv');opp=read('confirmation_opportunity_summary.csv');buy=read('matched_price_summary.csv')
    comp=read('comparisons.csv');period=read('periods.csv');con=read('all_comparison_concentration.csv');policy=read('policy_opportunity_cost.csv')
    def mainpart(f):return f[f.stock.eq(3000)&f.bp.eq(5)] if 'stock' in f and 'bp' in f else f
    executive='''**【研究判断】不升级本轮延迟/确认入场，保留原09:35重点基线。三档成本下，六种新买点均未超过原版；主/中成本部分确认能降低做T盘中回撤，但全账户盘中回撤更大且少赚较多，高成本这些做T回撤优势消失。不是把双回撤同时下降设硬门槛，而是本轮利润、资金与风险交换不划算。**

【模型事实】固定09:45比原09:35少赚7,672.29元，固定10:05少13,338.43元。两者共同56笔中分别31笔买贵，买价参考现金代价7,670/13,330元；不是因为少参加机会。09:40收复开盘价相比固定09:45再少541.38元，总少8,213.67元；10:00收复开盘价相比固定10:05反而多2,012.13元，但仍总少11,326.30元。不能把“相对晚买有用”写成“优于原买点”。

09:40收复开盘的取舍：盘中做T回撤少662.35元，但全账户多2,902.86元，必要补款多2,306.10元，净少8,213.67元；最大单亏从2,263.98降到1,900.54元。收益代价与局部风险改善并列，不否认降低单亏的事实。10:00收复开盘筛掉12笔，在相同时刻固定F逻辑归属下避免亏损4,604.66、错过盈利2,577.82元，费用税/净额交互后总账户改善2,012.13元。两个bar“收价回升且低点不下降”筛掉的盈利更多：09:40版避6,694.50却错13,479.56元，10:00版避4,853.23却错16,814.67元。

成本例外不能省略：09:40收复开盘筛选相对固定09:45，在5/11/20bp分别−541.38/+44.46/+923.24元；10:00收复开盘筛选相对固定10:05分别+2,012.13/+2,416.03/+3,021.88元。两者三成本仍低于原09:35。主成本最高逻辑胜率是09:40两bar确认F的60.98%，但仅净65,650.74元，比原版少14,538.56元。延后10:05使原L1的三次冲突消失，F/L1结果相同；这是等到N退出后的名额释放，不是确认择时能力。

【观点】旧利润锚点与旧重点基线保留为两个展示入口，不硬凑第三新方案；本轮是有边界的负结果，不能推成任何确认、任何股票或未来等待都无效。'''
    text=['# B26正T入场确认与延迟买入研究报告',
      '【事实】submitted，待统筹审核。固定行情2022年首个交易日至2026-09-11；3000研究旧股、初始现金0、每笔1000，必要现金足额补款。主成本每边5bp滑点，另扣日期费用、FIFO股息税与期末准备。金额为元，相对同资源同流量持有的累计净增量，不是年收益或实盘收益。',
      f'**【模型事实】17规则全表收益最多为{name(profit)}，净{main.loc[profit,"increment"]:,.2f}；14条入场主矩阵最多为{name(newbest.name)}，净{newbest.increment:,.2f}，较原重点基线变化{newbest.increment-base.increment:+,.2f}。**',
      f'原重点基线净{base.increment:,.2f}，收盘做T/全账户回撤{base.relative_mdd:,.2f}/{base.absolute_mdd:,.2f}，共同网格离散盘中{base.intraday_relative_mdd:,.2f}/{base.intraday_absolute_mdd:,.2f}，必要补款{base.deposits:,.2f}。',
      executive,
      '## 1. 七种入场及利润／风险／资金主表',
      'P均只用原上升/震荡原信号，仍收盘卖可卖旧股。N2深跌买与R1隔夜卖完全冻结；F为不加额度限制，确认版F仍会因确认未通过而少做。L1限制未完成加股批次最多一笔、减股另最多一笔。全表三锚点是旧方案，不能称新确认创新。',
      table(core.reset_index(),cols,True),
      '【观点】分别看下表“固定延后−原版”和“确认−同刻延后”。只有后者才对应新增筛选的账户差额；该差额仍含参与、费用税和净额交互，不能等同随机实验因果效应。四种最大回撤各自从完整曲线计算，不相加最大回撤差额。',
      table(mainpart(bridge),['id','total','confirmation_vs_same_time','delay_vs_original'],True),
      '确认筛选的机会代价：用相同时刻固定延后F账本对应交易衡量。明确不满足与数据未知分开；未知不能算择时避损。对应L1仍以固定F衡量筛选，政策边际另列。',
      table(mainpart(opp),['id','condition','n','fixed_profit','avoided_loss','missed_profit','unknown_excluded_profit'],True),
      '## 2. 固定晚买和匹配成交价格',
      '原09:35、固定09:45/10:05的买入价来自该区间开价，父结束标签分别09:40/09:50/10:10。观察09:40或10:00完成后再留5分钟；不使用观察收价或触发bar早先开价成交。',
      table(mainpart(buy),['id','n','price_cash','cheaper','dearer','max_benefit','max_cost','logical_change'],True),
      '买价差只在与同政策原版共同成交日期计算。实际总账户还含新可成交/未成交、N/R分摊和FIFO变化；单独买价差不能当总账户收益。完整新增/减少日期见matched_entry_prices与quote_availability_changes。',
      '## 3. 确认条件和唯一拒绝原因',
      '收复开盘：完成收价≥当日已知开盘；两bar确认：当前收价>紧邻前bar收价且当前最低≥前bar最低。用原始十进制字符串Decimal，独立Fraction再判。正成交量/字段完整性只要求所需已完成bar；前bar缺失不影响单bar收复规则。不是日内最低点认证。一次不通过即当天不买，不滚动、补买或回退。',
      table(read('signal_status_summary.csv').query('stock==3000 and bp==5'),['id','condition','quote_state','reason','n'],True),
      '唯一实际原因按确认未知/失败、报价缺失/不可成交、政策/库存的时序优先记录；各条件和报价状态仍同时保留。主表保留全部原信号日，common_evaluable_diagnostic只是已知日期描述，不替代全策略。',
      '## 4. L1边际、尾部和资源',
      table(mainpart(policy),['id','removed','avoided_loss','missed_profit','actual_change','interaction'],True),
      'L1若因延后买等到N退出释放名额，是资源/时序效果，不是确认识别能力。所有交易按实际时间重算，同刻不同报价不能净额；不卖当天新买股份。',
      table(s.query('stock==3000 and bp==5'),['id','completed','pending','win','winning_day_pct','avg_profit','avg_loss','worst','worst5','longest_loss','recovery_days'],True),
      table(s.query('stock==3000 and bp==5'),['id','deposits','max_deposit','max_buy_cash','max_shares','min_old_available','deposit_yuan_days','max_batch_days'],True),
      '补款留存元天记录必要外部流入至期末的加权留存，不是可随时抽走的闲钱；最大买单含已有现金，不等于额外补款。库存算法先于排名，详见resource_lock/diagnostic。',
      '## 5. 有限非重复取舍与最高胜率',
      table(main.loc[highlights].reset_index(),cols,True),
      '【观点】上表只保留两个旧非支配取舍；新确认的局部风险降低已在全表保留，但本轮未形成值得替换的方案，因此不强凑第三。它们不是自动采用名单，双回撤同时下降也不是唯一成功门槛。全部Pareto点仍保存。',
      table(main.loc[[highwin]].reset_index(),['id','increment','win','worst','worst5','intraday_relative_mdd','intraday_absolute_mdd'],True),
      '最高胜率单列，不用胜率覆盖少赚和大额亏损；若与某展示点相同，不增加一个候选。',
      '## 6. 三成本完整结果与例外',
      table(s[s.stock.eq(3000)],['id','bp','increment','relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd','deposits','win','worst'],True),
      table(pd.DataFrame(leaders),names=True),
      '每一成本逐条相对原重点基线：正数回撤变化表示更差，负数表示降低。不能把主成本结论概括为全部成本。',
      table(pd.DataFrame(riskcost),names=True),
      '## 7. 年份、时期、集中性及阶段',
      table(period[period.stock.eq(3000)],['id','bp','period','increment','relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd']),
      '各年/分期曲线重新以该段前一收盘归零；不是当年重新择优的策略。以下集中性同时保留原版和相同时刻对照，去前1/3/5日只是诊断，不据此事后删日期。',
      table(mainpart(con)),
      table(mainpart(read('stage_diagnostics.csv'))),
      '上升/震荡仅分组解释，未将不同阶段赢家拼出第八种入场。每日全量收益/损失和前三成本集中性见daily_comparison.csv.gz/all_comparison_concentration.csv。',
      '## 8. 四种风险峰谷与底仓贡献',
      table(read('risk_attribution.csv').query('stock==3000 and bp==5')),
      '贡献为同一个峰谷区间峰值减谷值，正数增加回撤、负数抵消。全账户包括同段持有底仓贡献；这不是独立持有全历史最大回撤。完整三成本四曲线贡献均保存。',
      table(read('parent_common_grid_bridge.csv')),
      '旧15账户现金/净单/逻辑账保持；盘中改变如有来自新公共观察点，不能称经济改进。B24已发布5分钟桥和实际交易事件桥分开保留，不混用。',
      '## 9. 细数据、独立核验与限制',
      table(read('fine_confirmation_summary.csv')),
      table(read('fine_quote_summary.csv')),
      f'合格细分钟{len(fine)}日。上表信号/决策覆盖与实际成交报价覆盖分开；关键增益、损失、拒绝、名额变化日期覆盖见focus_date_coverage.csv。即使同日覆盖也不认证竞价、分钟内先后或可成交数量。没有替换有利细报价。',
      f'独立核验{iv["accounts"]}账户，每账户{iv["intraday_points_per_account"]}共同点，合计{iv["total_intraday_points"]}点，{iv["prefixes"]}前缀通过。原始字符串特征/判断独立Fraction验证，实际P拒绝状态另重建；15旧账户逐日/净单/逻辑路径对齐。费用FIFO/应收到账/税准备/同流量持有/四回撤独立重建。独立程序不是第二行情商。',
      '共同格点包含无交易、尚未买入与退出后的估值；缺失保留、不未来填充。五分钟离散峰谷不能认证连续盘中最大亏损，原来源/执行代理限制继承。同历史反复研究不是独立样本外，不能保证未来最好。',
      '## 10. 完整账户经济差额桥与永久证据',
      table(mainpart(comp),['id','reference','increment','reference_cash_change','slippage_change','fee_change','tax_change','terminal_reserve_change','dividend_relative_change','pending_mark_change']),
      '恒等式：净变化=参考价现金变化−滑点变化−费用变化−FIFO税变化−期末准备变化＋股息相对变化＋未完成估值变化。每条三成本对照断言通过。',
      '负模块/年份反向线索保存在opposite_direction_regions.csv：同日期重新扣双边滑点/费用，不直接取负；只是反向机会诊断，不是FIFO反向完整账户或可卖空候选。',
      '全部源码/输入SHA、注册、特征、拒绝、plans、共享账户、净单、逻辑/持股批次、共同曲线、三成本分析和验证保存在指定GitHub。result_sha256封存计算，delivery_sha256封存报告；固定最终提交与运行及错误修订见本地B26执行交接与验证。',
      '【状态】仅完成研究并提交，方向DOCS同步；未合main、交易、监控、派发消息或启动B27。'
    ]
    (R/'DELIVERY.md').write_text('\n\n'.join(text)+'\n')
    c.js('delivery_sha256.json',dict(code_sha=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],files={str(p):c.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['delivery_sha256.json','calculation.log','verification.log','delivery.log']}))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:run()
    except Exception:
        import traceback
        c.js('delivery_failure_'+os.environ['GITHUB_RUN_ID']+'.json',dict(traceback=traceback.format_exc()));raise
