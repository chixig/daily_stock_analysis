#!/usr/bin/env python3
"""B18 final independent reconciliation and reader-facing remote report."""
import os,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import foxconn_b18 as b
R=b.R

def money(x):return f'{x:+,.2f}'
def plain(x):return f'{x:,.2f}'
def pct(x):return f'{x:.2f}%'
def run():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    checked={}
    for f in ['manifest.json','verification_manifest.json','posthoc_manifest.json']:
        for p,h in json.loads((R/f).read_text())['files'].items():assert b.sha(p)==h,p;checked[p]=h
    ca=pd.read_csv(R/'account_summary.csv');ha=pd.read_csv(R/'posthoc_account_summary.csv');a=pd.concat([ca,ha],ignore_index=True)
    periods=pd.concat([pd.read_csv(R/'periods.csv'),pd.read_csv(R/'posthoc_periods.csv')],ignore_index=True)
    quality=pd.concat([pd.read_csv(R/'quality_strata.csv'),pd.read_csv(R/'posthoc_quality_strata.csv')],ignore_index=True)
    conc=pd.concat([pd.read_csv(R/'concentration.csv'),pd.read_csv(R/'posthoc_concentration.csv')],ignore_index=True)
    funding=pd.concat([pd.read_csv(R/'funding_summary.csv'),pd.read_csv(R/'posthoc_funding_summary.csv')],ignore_index=True)
    d=pd.read_csv(b.P/'daily_ledger.csv',parse_dates=['date','exit_date']);ds=d[d.date.ge('2020-01-01')].reset_index(drop=True);q=3000;checks=[]
    for _,x in ha.iterrows():
        tag=f'{x.candidate}_{int(x.slip_bp)}';z=pd.read_csv(R/f'posthoc_account_{tag}.csv',parse_dates=['date']);o=pd.read_csv(R/f'posthoc_orders_{tag}.csv',parse_dates=['date']);t=pd.read_csv(R/f'posthoc_trades_{tag}.csv',parse_dates=['entry','exit'])
        assert o.quantity.eq(1000).all() and z.cash.min()>-1e-6
        flow=(o.value*np.where(o.side.eq('SELL'),1,-1)-o.fee-o.tax).groupby(o.date).sum().reindex(ds.date,fill_value=0).to_numpy()
        qty=(o.quantity*np.where(o.side.eq('BUY'),1,-1)).groupby(o.date).sum().reindex(ds.date,fill_value=0).to_numpy()
        np.testing.assert_allclose(z.cash,z.external+np.cumsum(flow+z.payment.to_numpy()),atol=1e-5)
        np.testing.assert_array_equal(z.shares,q+np.cumsum(qty))
        np.testing.assert_allclose(z.hold_cash,z.external+z.hold_payment.cumsum(),atol=1e-5)
        np.testing.assert_allclose(z.relative,z.cash+z.receivable+z.shares*ds.close-z.tax_reserve-z.hold_cash-z.hold_receivable-q*ds.close,atol=1e-5)
        assert t.exit_i.notna().all()
        assert abs(t.cash_increment.sum()-z.tax_reserve.iloc[-1]-x.increment)<1e-5
        assert abs(x.trade_win-t.cash_increment.gt(0).mean()*100)<1e-6
        assert abs(x.relative_mdd-(z.relative-z.relative.cummax().clip(lower=0)).min())<1e-5
        for per,sel in [('discovery',t.entry.lt('2024-01-01')),('later',t.entry.ge('2024-01-01'))]:
            p=periods[(periods.candidate==x.candidate)&periods.bp.eq(x.slip_bp)&periods.period.eq(per)].iloc[0]
            assert abs(t.loc[sel,'cash_increment'].sum()-p.cash)<1e-5
        checks.append(dict(candidate=x.candidate,bp=x.slip_bp,status='PASS'))
    b.save('final_posthoc_independent_checks.csv',checks)
    # All raw experiment, old/new baseline and posthoc values remain separate.
    selected=a[a.slip_bp.eq(5)].set_index('candidate');base=selected.loc['C08'];allbase=selected.loc['C06']
    names={'H00':'强收盘＋量不放大，次日14:50买回','H01':'三日跌≥4%但强收盘，低开先回补／限时回补','H02':'强收盘＋量不放大，次日开盘买回','H03':'三日跌≥4%但强收盘，次日开盘买回','C00':'截至14:50三日涨≥6%，次日14:50买回','C01':'前日三日跌≥2%＋当日弱收盘，次日09:40','C02':'当日弱收盘＋三日跌≥4%，低开先回补','C03':'前日三日跌≥2%＋当日弱收盘，低开先回补','C04':'前日三日跌≥2%＋当日弱收盘，1%目标/1%止损','C05':'前日顶部10%强收盘，0.5%目标/2%止损','C06':'旧S1_F1：所有信号都参与，次日开盘回补','C07':'无条件每日收盘卖，次日开盘回补','C08':'旧S1_F1：单批周转，回补当日不再卖'}
    best=selected.increment.idxmax();bestwin=selected.trade_win.idxmax()
    core=['H00','H01','H03','C08','C06','C00','C07']
    main=[]
    for key in core:
        x=selected.loc[key];main.append({'方案':key+' '+names[key],'次数':int(x.completed),'盈利次数/胜率':f'{int(x.trade_wins)}/{pct(x.trade_win)}','累计净增量元':money(x.increment),'平均每次元':money(x.increment/x.completed),'比旧单批多赚元':money(x.increment-base.increment),'最大单次亏损元':money(x.trade_worst),'最大相对回撤元':money(x.relative_mdd)})
    b.save('reader_core_comparison.csv',main)
    def getp(key,period,bp=5):return periods[(periods.candidate==key)&periods.bp.eq(bp)&periods.period.eq(period)].iloc[0]
    def geta(key,bp):return a[(a.candidate==key)&a.slip_bp.eq(bp)].iloc[0]
    split=[]
    for key in ['H00','H01','H03','C08','C06','C00','C02']:
        early=getp(key,'discovery');late=getp(key,'later');split.append({'方案':key,'2020—2023次数':int(early.n),'前段逐笔净增量元':money(early.cash),'2024后次数':int(late.n),'后段逐笔净增量元':money(late.cash),'后段胜率':pct(late.win),'11bp全段账户元':money(geta(key,11).increment),'20bp全段账户元':money(geta(key,20).increment)})
    yearly=[]
    for key in ['H00','H01','H03','C08']:
        row={'方案':key}
        for y in range(2020,2027):row[str(y)]=money(getp(key,str(y)).cash)
        yearly.append(row)
    hm=selected.loc['H00'];hw=selected.loc['H01'];c0=selected.loc['C00'];h0open=selected.loc['H02'];h1open=selected.loc['H03']
    fine=pd.read_csv(R/'posthoc_fine_path_replay.csv');fs=[]
    for key in ['H00','H01']:
        g=fine[fine.candidate.eq(key)];v=g[g.new_cash.notna()]
        fs.append({'方案':key,'已完成交易':int(selected.loc[key].completed),'有细数据复核':len(g),'成功重放':len(v),'时点变化数':int((v.old_clock!=v.new_clock).sum()),'累计价差修正元':money(v.change.sum()),'最大单笔修正绝对元':plain(v.change.abs().max()) if len(v) else '未知'})
    b.save('reader_fine_replay_summary.csv',fs)
    neigh=pd.read_csv(R/'posthoc_key_neighborhood.csv');nh=[]
    for rule,path in [('S1_clv_ge_0p8__AND__S1_vr_le_0p8','fixed_1450'),('S1_clv_ge_0p8__AND__S1_vr_le_1','fixed_1450'),('S1_clv_ge_0p8__AND__S1_vr_le_1','fixed_1030'),('S1_clv_ge_0p7__AND__S1_r3_le_m4','gap_low_target0.5'),('S1_clv_ge_0p8__AND__S1_r3_le_m4','gap_low_target0.5'),('S1_clv_ge_0p9__AND__S1_r3_le_m4','gap_low_target0.5')]:
        z=neigh[neigh.rule.eq(rule)&neigh.path.eq(path)]
        if len(z):
            row={'条件/回补':rule+' / '+path}
            for per in ['discovery','later','main']:
                zz=z[z.period==per].iloc[0];row[per]=f'{int(zz.n)}笔 / {money(zz.cash)}元 / {pct(zz.win)}'
            nh.append(row)
    full=[]
    for key,x in selected.iterrows():full.append({'方案':key+' '+names[key],'N':int(x.completed),'胜率':pct(x.trade_win),'账户净增量元':money(x.increment),'11bp元':money(geta(key,11).increment),'身份':'全历史事后线索/对照' if key.startswith('H') else ('旧基准' if key in ['C06','C07','C08'] else '前段选出')})
    res=[]
    for key in ['H00','H01','H03','C08','C00']:
        x=funding[funding.candidate.eq(key)&funding.bp.eq(5)].iloc[0]
        res.append({'方案':key,'最低旧仓需求股':int(x.minimum_old_shares),'累计资金支持元':plain(x.deposits),'单笔额外买回资金最大元':plain(x.single_max),'最长相对现金不足天数':int(x.longest_deficit_days)})
    tails=[]
    for key in ['H00','H01','H03','C08','C00']:
        x=conc[conc.candidate.eq(key)].iloc[0];tails.append({'方案':key,'交易事件簇':int(x.events),'删最大盈利事件后元':money(x.without_best_event),'删最大亏损事件后元':money(x.without_worst_event),'删最好3笔后元':money(x.without_best3_trades),'删最差3笔后元':money(x.without_worst3_trades)})
    url='https://github.com/chixig/daily_stock_analysis/blob/'+os.environ['GITHUB_SHA']+'/research/foxconn_t0_20260926_b18/'
    def link(label,file):return f'[{label}]({url+file})'
    text=f'''# B18更优卖出与回补研究报告

**交付状态：submitted，待统筹审核。研究日2026-09-26，行情截至2026-09-11。** 本文“事实”指固定历史数据和所述成交/成本模型下可复核的计算结果；不是实盘成交或收益。判断与下一步建议标为观点；未经证实的原因标为推测。

**结论：找到两条比旧单批方案历史表现更好的新线索，但尚未证明它们能稳定取代旧方案。** 166个卖出条件×13条回补路径共2,158个组合，按前段预选的6条新组合均未在完整比较中稳健超过旧单批方案。另将全历史收益和胜率冠军单独标为“事后发现”，补齐账户与成本复核：H00净增量{money(hm.increment)}元，胜率{pct(hm.trade_win)}；H01净增量{money(hw.increment)}元，胜率{pct(hw.trade_win)}。同资源旧单批方案为{money(base.increment)}元、{pct(base.trade_win)}。

观点：**收益优先候选是H00，胜率优先候选是H01；综合执行简洁和较小历史回撤，我更倾向先复核H03（H01同条件、次日开盘直接买回）。三者都不是已验证正式策略。** H00前段表现较差，H01样本少且为全历史筛选；不能把后段表现好反写成“当年已经选中了它”。

## 一、用同样资源比较，究竟多赚多少

全表统一期初3000股旧仓、每次交易1000股、资金足额，持有对照收到相同本金流；只报告相对持有的做T增量，底仓自然上涨收益不混入。主成本每边5bp（0.05%）滑点，另计历史税费及FIFO股息税，期末税准备也扣除。研究主窗卖出日2020-01-02至2026-09-10，末回补/估值日2026-09-11。

{pd.DataFrame(main).to_markdown(index=False)}

不做T：增量0元、交易0次、做T增量回撤0元；胜率不适用。表内{best}是完成完整账户核算的13条路径中主成本净增量最高者，{bestwin}是胜率最高者。2,158个网格组合先完成独立机会账，再对选定候选补齐上述完整账户，因此不声称穷尽所有组合的最终账户名次或全局最优。

网格冠军比较事前设定至少40笔；更小样本也保存并在邻域表列出，但不拿9笔之类的小样本高胜率充当同等级冠军。H01相对H00提高胜率{hw.trade_win-hm.trade_win:.2f}个百分点，但少赚{plain(hm.increment-hw.increment)}元、少交易{int(hm.completed-hw.completed)}次。是否更合适取决于对累计收益、出手机会与单次亏损的取舍，未编造综合评分。

旧B17“1000股总底仓”286笔净增量11,271.41元已原样复现；主表旧单批在统一3000股账户为{money(base.increment)}元。两者股票批次与FIFO股息税不同，不能直接搬旧数字进相同资源表。单批仅是参与政策（回补当天不再卖），并非本次默认用户只有1000股。

## 二、两条新线索怎样执行

**H00：前一交易日收盘位于当日价格区间顶部20%，且成交量不超过此前20日平均量；符合时今日收盘卖1000股，次日14:50买回。** CLV=(收盘−最低)/(最高−最低)≥0.8；量比≤1。两条件只用卖出日前一交易日数据。不是当日15:00才看完收盘后回填收盘卖单。14:50使用从14:50开始的五分钟区间开价作代理，不使用该区间后来的低点。若无法回补，按应急及强制开盘重试处理。

**H01：前一交易日三日累计跌至少4%，但当天收盘已位于日内区间顶部30%；今日收盘卖1000股。** 次日09:25开盘价相对卖价低至少0.5%，09:30连续竞价开始时回补；否则按完成五分钟bar收价观察：价格较卖价跌0.5%触发回补、涨1%触发止损回补，额外等待一个五分钟间隔后成交，最晚10:30强制回补。观察到低开后不能追溯成交在09:25。实际执行价可以超过止损线，1%不是最大亏损承诺。

事实：H00换成相同条件开盘回补，账户仅{money(h0open.increment)}元；延至14:50的账户差额为{money(hm.increment-h0open.increment)}元。H01换成相同条件开盘回补为{money(h1open.increment)}元，所列限时回补差额为{money(hw.increment-h1open.increment)}元。它们说明本轮收益不能只归功于卖出筛选；仍需注意回补方式会影响税、后续参与及失败路径。两条完整账户对照均保留在底稿。

观点：H03的取舍更容易解释：H01复杂回补比直接开盘只多赚{plain(hw.increment-h1open.increment)}元，却把历史最大单次亏损从{plain(abs(h1open.trade_worst))}元扩大到{plain(abs(hw.trade_worst))}元、最大相对回撤从{plain(abs(h1open.relative_mdd))}元扩大到{plain(abs(hw.relative_mdd))}元；胜率确实提高{hw.trade_win-h1open.trade_win:.2f}个百分点。若优先简单执行和历史尾部，H03值得优先复核；若优先胜率，可保留H01。这是明示偏好取舍，不是综合分数。

推测：H00可能捕捉“强收盘但成交未放大”的次日回落；H01可能捕捉下跌后日内收回的短暂修复。这里只是机制假说，结果不证明市场必然按此运行。

## 三、前后时期和成本能不能撑住

{pd.DataFrame(split).to_markdown(index=False)}

前/后段按卖出日期归属，表中是已完成逐笔净额；少数方案期末还有65或130元股息税准备，因此逐笔加总不一定等于账户净增量。主表及成本列已扣期末税准备。用于发现期选举的交易另要求2023年底前已经回补，避免跨年标签泄漏；展示前段可以包含年末卖出、翌年回补的归属交易。H00/H01均在观察全历史后发现，不能称此表通过独立样本外验证。

{pd.DataFrame(yearly).to_markdown(index=False)}

2026是不完整年度。年表仅用于检查收益集中，不要求每年盈利。主样本内最好、前段最好、后段最好是不同问题。前段选择出的C00虽然全段尚有{money(c0.increment)}元，其最大相对回撤{money(c0.relative_mdd)}元、最大单次亏损{money(c0.trade_worst)}元；不因胜率略过50%便优先于风险较小的旧单批。

事实：原先发现期胜率最高的C02在独立机会账前段52笔胜率65.38%、净额+495.93元，加入FIFO账户后前段变为−119.07元，全段账户−3,542.12元。**提高胜率并不自动提高利润；手续费和较大亏损可以吃掉多数小赢。**

事实：H00量比阈值从≤1改为≤0.8，主窗机会净额由24,295.32元降到2,547.29元，敏感性较强；不能把“越缩量越好”当规律。H01把强收盘从顶部30%缩到顶部20%/10%，样本降到26/9笔，机会账仍正，但小样本胜率不可与41笔直接当同等级证据。

附近参数并非都一样：下表只复用原网格已有结果，不追加调参，均为独立机会账（未含路径依赖FIFO税），不能混进主表账户数。

{pd.DataFrame(nh).to_markdown(index=False)}

## 四、尾部、数据与执行限制

{pd.DataFrame(tails).to_markdown(index=False)}

本表基于已完成逐笔净额做删减诊断；H01/H03尚有130元期末税准备，删减后也未重建账户和后续税收路径，因此不是新的可执行账户收益。删赢家/输家只是对称集中度诊断，不能删掉后作为正式策略。事件簇以实际卖出相隔不超过5个交易日连接；连续日规则可能连成一个大簇，因此不能把簇数量当独立样本量。回撤为逐日收盘相对持有的增量回撤，未宣称逐笔盘中最深回撤。分期月区块区间在底稿保留；反复搜索后不能用普通区间声称已取得统计显著优势。

{pd.DataFrame(fs).to_markdown(index=False)}

细数据复核只覆盖现有合格一分钟日期，并按原五分钟决策节奏重新聚合和重放，不擅自把策略改成一分钟。未覆盖部分未知；H01四笔细数据重放全部属于低开后09:30回补，尚未覆盖其等待触发/止损分支。价格相符不证明排队或1000股必然成交。H00/H01卖出条件只用日线，避开S2日内条件的已知质量缺口；其回补仍依赖分钟价格。普通五分钟全天价格/量对账有异常，事后QC仅作分层，不倒过来取消当时应卖的交易。原预选C05有一笔可比买价相差约0.16元，保留反证。

没有把极值当成交价；固定时间和完成bar触发均有明确动作时点。计划10:30/14:50到期，失败后逐日可成交开盘强制恢复；延期和未完成估值不删除。主账户未因现金不足缩量或停做。实际竞价排队、报价接收延迟和部分成交仍未认证。

## 五、资金和旧仓需要多少

{pd.DataFrame(res).to_markdown(index=False)}

累计资金支持指零初始现金、盈余留在账户、股息按旧核验时点到账、必要时补入后的总额，非亏损额、非建议投入额度；补钱同时进入持有对照，未算成利润。单笔缺口可高于累计额，因为较早利润/股息可用于后续买回。所有方案实际比较都使用3000股；最低旧仓需求只是历史资源测算，不代表用户持仓或建议买入。

## 六、结论与下一步

观点：本轮没有支持“早期选出一个稳定冠军、随后持续战胜旧方案”。它支持更具体的研究进展：H00提供较高累计收益线索，H01提供较高胜率且较小历史单次亏损线索；两者相同条件的回补对照已算清，盈利与失败路径都纳入。

更合理的处理是保留H00及H01/H03这一组待复核候选，优先复核执行简单、历史回撤较小的H03，并将H00作为收益优先比较对象；旧单批保留比较地位，不把这次全历史筛选当成正式采用依据。若继续，先锁定上述精确规则，用已具备的2018—2019较早历史及逐年只用当时历史选择的测试检查可迁移性，并优先核对这两条需要的固定时点/触发价格；不要求等待未来半年，也不继续扩大无边界网格。早期历史也曾被旧研究查看，仍需如实标注历史复核身份。

H00若优势在较早历史和相邻时点消失、或者扣真实可支持成本后不再改善，应降级；H01若附近阈值高度跳变、收益集中于少数事件或细数据重放改变止损/回补，应降级。实际费率/成交条件未知时不把5bp当真实滑点。上述为研究建议，未授权交易或自动采用。

## 附录：范围、复用和全部候选

V1事前范围实际生成166条件、13回补、43,160条按费用/时期拆分的汇总（并非43,160个独立策略）。2020—2023按收益/胜率/成本预选6条新组合，加3个基准，27账户。V1.1看到全历史结果后只补两个冠军及相同条件开盘对照，12账户；共13条完整路径、39个成本账户。不改原发现名单，不把事后冠军升级为时间检验成功。

{pd.DataFrame(full).to_markdown(index=False)}

所有条件只使用卖前可得信息；S1/S2时间定义、缺失值、费用、权益、失败回补、库存/资金分账与前缀测试详见协议。费用沿用旧核验模型：每腿佣金成交额0.0001354且最低5元，历史印花税/过户费，FIFO股息税和期末准备。官方规则页面本次只读核验：[上交所2026交易规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)、[股息红利差别化税政策](https://www.csrc.gov.cn/csrc/c100028/c1001875/content.shtml)。历史基准、费用原始来源及九次权益公告保留父批次。

### 验证和证据

- 主运行36248777017成功；独立复核36248993685成功；有限补充运行36249118079成功；最终交付独立核验由本程序运行，证据见delivery_validation.json。
- V1的1,171项父证据哈希前后不变；原286笔+11,271.41元复现。主27账户独立逐日现金/库存/对照核算通过，选择名单可只用发现期重建。
- 补充12账户完成原会计标量复核，本最终程序又从保存订单独立重建现金、数量、对照权益、分期和胜率；原主manifest未改。合成测试覆盖观察低开后成交、目标/止损、额外五分钟延迟、缺窗、最晚时点和涨停。
- 全部行情、计算和逐笔底稿只在GitHub；本地保存协议、报告和链接。未合main、未实际交易。研究工作流成功不代表仓库其他无关工作流全部成功。

证据固定于最终文档生成程序启动提交（不使用漂移分支）：{link('主账户汇总','account_summary.csv')}、{link('补充冠军账户','posthoc_account_summary.csv')}、{link('全部网格','all_experiments.csv')}、{link('前段选择名单','selected_before_later_account_review.csv')}、{link('主分期','periods.csv')}、{link('冠军分期','posthoc_periods.csv')}、{link('分钟路径重放','posthoc_fine_path_replay.csv')}、{link('原协议','protocol.md')}、{link('事后有限扩展理由','posthoc_protocol_v1_1.md')}、{link('主独立核验','final_validation.json')}、{link('主manifest','manifest.json')}、{link('补充manifest','posthoc_manifest.json')}。
'''
    (R/'REPORT.md').write_text(text)
    b.js('delivery_validation.json',dict(status='PASS',original_and_posthoc_files_verified=len(checked),new_independent_accounts=len(checks),total_cost_accounts=len(a),complete_paths=len(selected),net_best=best,win_best=bestwin,market_cutoff='2026-09-11',source_commit=os.environ['GITHUB_SHA']))
    b.js('delivery_manifest.json',dict(files={str(p):b.sha(p) for p in [R/'REPORT.md',R/'reader_core_comparison.csv',R/'reader_fine_replay_summary.csv',R/'delivery_validation.json',R/'final_posthoc_independent_checks.csv']}))
    print(json.dumps(json.loads((R/'delivery_validation.json').read_text()),ensure_ascii=False),flush=True)
if __name__=='__main__':run()
