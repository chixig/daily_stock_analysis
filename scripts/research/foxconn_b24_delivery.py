"""B24 bounded delivery, legacy bridges, and fine-date audit; no new candidates."""
import os,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_b24 as c
R=c.R
HEAD={'id':'核对编号','increment':'净增量(元)','relative_mdd':'做T回撤(元)','absolute_mdd':'全账户回撤(元)','hold_mdd':'持有回撤(元)','completed':'完成笔数','win':'逻辑胜率(%)','worst':'最大单笔损益(元)','worst5':'最差5笔合计(元)','deposits':'累计补款(元)','max_shares':'最高持股','bp':'每边滑点bp','stock':'初始旧股','policy_rejected':'政策拒绝数','longest_loss':'最长连亏笔数','recovery_days':'最长回撤恢复天数','reference':'对照','removed':'少做笔数','avoided_loss':'避免亏损(元)','missed_profit':'错失盈利(元)','actual_increment_change':'真实净增量变化(元)','remaining_interaction':'剩余交互变化(元)','period':'时期','absolute_profit':'全账户损益(元)','top1':'最大1日贡献','top3':'最大3日贡献','top5':'最大5日贡献','without1':'其余日合计(去1日)','without3':'其余日合计(去3日)','without5':'其余日合计(去5日)','delta':'相对主对照增量','date':'日期','module':'模块','kind':'动作','signals':'信号数','accepted':'已开笔数','pending':'未完成笔数','untradeable':'报价不可成交','quote_unknown':'报价未知','inventory_rejected':'旧股不足拒绝','exit_failed':'退出失败次数','max_deposit':'最大单次补款','max_buy_cash':'最大真实买单总款','max_batch_days':'最长批次日数','min_old_available':'最低可卖旧股','deposit_yuan_days':'补款留存元天','n':'笔数','step':'口径步骤','value':'金额(元)','correlation':'相关系数','both_loss_days':'同日俱亏天数','all_days':'全部交易日数','first':'方向一','second':'方向二','avg_profit':'盈利笔平均(元)','avg_loss':'亏损笔平均(元)','winning_day_pct':'盈利交易日占比(%)','behind_days':'最长落后持有天数','buy_cash_total':'累计真实买入总款(元)'}
HEAD.update({'reference_cash_change':'参考价现金变化','slippage_change':'滑点变化','fee_change':'费用变化','tax_change':'FIFO税变化','reserve_change':'期末税准备变化','dividend_change':'权益差变化','pending_mark_change':'未完成估值变化','relative_day':'当日做T损益','absolute_day':'当日全账户损益','P':'正T贡献','N':'隔夜买贡献','R':'隔夜卖贡献','adjust':'税准备调整','combo':'版本组合','minimum_initial_old_shares':'历史最低旧股需要','diagnostic_stock':'诊断旧股数','observed_5m_relative_mdd':'离散观察做T回撤','observed_5m_absolute_mdd':'离散观察全账户回撤','date_covered':'细数据日期覆盖','quote_compared':'已比报价数','auction_unknown':'竞价未认证数','max_abs_price_difference':'最大绝对价差','state_flips':'状态翻转数','coverage':'覆盖说明'})
def table(df,cols=None):
    return (df[cols] if cols else df).rename(columns=HEAD).to_markdown(index=False,floatfmt='.2f')
def read(n):return pd.read_csv(R/n)
def run():
    iv=json.loads((R/'independent_validation.json').read_text());assert iv['status']=='PASS'
    sealed=json.loads((R/'result_sha256.json').read_text())
    for path,h in sealed['files'].items():assert c.sha(path)==h,path
    s=read('account_summary.csv');main=s[s.stock.eq(3000)&s.bp.eq(5)].set_index('id')
    assert len(s)==396
    focus=json.loads((R/'focus.json').read_text())['3000']
    champion=main.loc[focus['profit']]
    frontier=read('pareto.csv');frontier=frontier[(frontier.stock==3000)&frontier.bp.eq(5)&frontier.pareto]
    riskpool=main.loc[main.index.intersection(frontier.id)]
    riskpool=riskpool[(riskpool.relative_mdd<champion.relative_mdd-1e-7)&(riskpool.absolute_mdd<champion.absolute_mdd-1e-7)]
    risk=riskpool.reset_index().sort_values(['increment','modules','id'],ascending=[False,True,True]).iloc[0].id if len(riskpool) else None
    focus['risk']=risk;focus['focus']=list(dict.fromkeys([c.BASE,focus['profit']]+([risk] if risk else [])+[focus['simple']]))
    c.js('delivery_focus.json',dict(**focus,selection='profit maximum; highest-profit nondominated alternative lowering BOTH drawdowns versus that profit champion; simplest nondominated alternative; no extra candidates'))
    keys=list(dict.fromkeys(focus['focus']+['Pall_N2_R1_L1','Pall_N2_R1_L2']))
    d,m,bars,sched,plans=c.load()
    sampled=read('sampled_intraday_stress.csv').to_dict('records')
    for key in focus['focus']:
        if key in {v['id'] for v in sampled}:continue
        rule=next(v for v in c.registry() if v['id']==key)
        met,aa,_,_=c.simulate(d,bars,sched,plans,rule,3000,5,False,True)
        expected=read('accounts/'+key+'_3000_5.csv.gz')
        for col in ['relative','absolute','shares','cash']:np.testing.assert_allclose(aa[col],expected[col],atol=1e-5)
        sampled.append(dict(id=key,stock=3000,bp=5,observed_5m_relative_mdd=met['event_relative_mdd'],observed_5m_absolute_mdd=met['event_absolute_mdd'],coverage='available 5m close plus event prices, not unknown intrabar max'))
    c.save('delivery_sampled_intraday_stress.csv',sampled)
    # Strengthen the 12 R-only parent bridges from terminal equality to every common daily ledger field.
    rd,rm,rpaths,rsp,rsched=c.z.load();rst=c.z.states(rd,m);family,_=c.z.z.origins(rm)
    c.z.x.ns['ACCOUNT_START']=c.START
    parent_daily=[]
    for module,parent_id in c.RM.items():
        original=next(v for v in c.z.registry() if v['id']==parent_id)
        actions,_,_=c.z.choose(original,rst,family);pp=rpaths['A1'].copy()
        for act,fp in rpaths.items():
            inds=pp.index[actions.reindex(pp.index).eq(act)];pp.loc[inds,:]=fp.loc[inds,:]
        plan,_,_=c.z.x.plan(rd,family.ne(''),pp,start=c.START,capacity=3)
        for bp in [5,11,20]:
            aa,_,_,_,_=c.z.x.account(rd,plan,3000,bp/10000,rsched)
            target=read('accounts/'+module+'_F_3000_'+str(bp)+'.csv.gz')
            assert list(pd.to_datetime(target.date))==list(aa.date)
            cols=['cash','hold_cash','shares','receivable','hold_receivable','tax_reserve','fee','tax','payment','hold_payment','deposit','external','equity','hold_equity','relative']
            np.testing.assert_allclose(target[cols],aa[cols],rtol=0,atol=1e-5)
            parent_daily.append(dict(module=module,bp=bp,days=len(aa),fields=len(cols),status='PASS'))
    c.save('R_daily_parent_validation.csv',parent_daily)
    # Reproduce B03 matched delayed comparison exactly, using old ex-post QC ONLY for legacy bridge.
    old=pd.read_csv(c.b.old.P/'results/daily_features_and_cashflows.csv',parse_dates=['date'])
    ix=old.date.map(pd.read_csv(c.b.old.B2/'source/sse_index.csv',parse_dates=['date']).set_index('date').close)
    masks,_=c.pmasks(old,ix)
    mg=m.groupby('date').agg(open=('open','first'),close=('close','last'))
    quality=(old.date.map(mg.open)-old.open).abs().le(.01)&(old.date.map(mg.close)-old.close).abs().le(.01)
    later=old.date.map(m[m.clock.eq('09:40')].set_index('date').open).where(quality)
    legacy=pd.read_csv('research/foxconn_t0_20260913_b03/results/matched_execution_comparison.csv')
    want=legacy[legacy.name.eq('PT_PT_matrix')].iloc[0]
    sel=masks['Pall']&old.date.ge('2024-01-02')&later.notna()
    cash=c.pt.cashflow(later[sel],old.close[sel],old.date[sel],'PT')
    assert int(sel.sum())==want.n and abs(cash.sum()-want.delayed_cash)<1e-6
    bridge=[dict(module='Pall',step='B03旧2024窗同日期理想开盘',n=want.n,value=want.open_cash),dict(module='Pall',step='B03旧2024窗同日期09:35',n=want.n,value=want.delayed_cash)]
    for mod in ['Pall','PUR']:
        sig=masks[mod]&old.date.ge('2022-01-01')
        direct=c.pt.cashflow(old.open[sig],old.close[sig],old.date[sig],'PT')
        bridge.append(dict(module=mod,step='统一2022窗旧开盘费用机会口径',n=int(sig.sum()),value=direct.sum()))
        t=read('trades/'+mod+'_F_3000_5.csv.gz');ev=read('events/'+mod+'_F_3000_5.csv.gz');matched=t[t.actual_exit_i.eq(t.entry_i)]
        ent=pd.to_datetime(matched.entry);buy=1000*matched.entry_price*1.0005
        exitref=ev[(ev.kind=='exit')&(ev.reason=='filled')].set_index('tid').reference
        sell=1000*matched.tid.map(exitref)*.9995
        oldcash=sell-buy-np.maximum(sell*.0001354,5)-np.maximum(buy*.0001354,5)-(sell+buy)*.00001-sell*np.where(ent<pd.Timestamp('2023-08-28'),.001,.0005)
        current=sell-buy-c.b.old.fee(sell,ent,True)-c.b.old.fee(buy,ent)
        bridge.extend([dict(module=mod,step='新已执行且当日完成日期09:35/旧费用',n=len(matched),value=oldcash.sum()),dict(module=mod,step='相同日期09:35/历史日期费用',n=len(matched),value=current.sum()),dict(module=mod,step='连续账户含延期/FIFO/权益准备',n=int(main.loc[mod+'_F','completed']),value=main.loc[mod+'_F','increment'])])
    nold=pd.read_csv(c.n11.R/'exit_trades.csv');nlat=pd.read_csv('research/foxconn_overnight_20260917_b12/latency_trades.csv')
    extras=[]
    oldfeat=pd.read_csv(c.n11.P10/'features.csv')
    oldledger=pd.read_csv(c.n11.b9.P8/'daily_ledger.csv',parse_dates=['date'])
    for mod,mode in [('N0','1000_S0'),('N2','1000_S2')]:
        for label,src in [('B11原价及固定20%股息税机会口径',nold),('B12下一bar收价及原费用机会口径',nlat[nlat.latency.eq('next_bar_close')])]:
            g=src[src.entry.eq('C')&src.exit_model.eq(mode)];bridge.append(dict(module=mod,step=label,n=len(g),value=g.cash.sum()))
        tt=read('trades/'+mod+'_F_3000_5.csv.gz')
        prior_dates=set(pd.to_datetime(nold.loc[nold.entry.eq('C')&nold.exit_model.eq(mode),'date']))
        shared=pd.to_datetime(tt.entry).isin(prior_dates)
        for label,pick in [('原61笔日期按新FIFO归属',shared),('新增完整信号日期按新FIFO归属',~shared)]:
            part=tt[pick];bridge.append(dict(module=mod,step=label,n=len(part),value=(part.cash+part.dividend).sum()))
        for t in tt[~shared].itertuples():
            dt=pd.Timestamp(t.entry);ii=int(oldledger.index[oldledger.date.eq(dt)][0]);oldrow=oldledger.iloc[ii]
            missing=list(oldfeat.columns[oldfeat.iloc[ii].isna()])
            extras.append(dict(module=mod,date=t.entry,old_missing_features=';'.join(missing),old_limit_proxy=bool(oldrow.close>=oldrow.preclose*1.099 or oldrow.volume<=0),old_next_open_missing=bool(pd.isna(oldrow.next_open)),logical_profit=t.cash+t.dividend,actual_exit=t.actual_exit))
        bridge.append(dict(module=mod,step='期末税准备从逻辑合计扣除',n=0,value=-main.loc[mod+'_F','terminal_reserve']))
        bridge.append(dict(module=mod,step='统一FIFO连续账户',n=int(main.loc[mod+'_F','completed']),value=main.loc[mod+'_F','increment']))
        assert abs((tt.cash+tt.dividend).sum()-main.loc[mod+'_F','terminal_reserve']-main.loc[mod+'_F','increment'])<1e-5
    c.save('legacy_N_membership_bridge.csv',extras)
    c.save('legacy_adjustment_bridge.csv',bridge)
    c.save('N_decision_prefix_evidence.csv',[dict(module=mod,tid=t['tid'],entry=t['entry'],observation_clock=t.get('observation_clock'),delayed_execution_clock=t.get('exit_clock'),status='PASS_asserted_in_load') for mod in ['N0','N2'] for t in plans[mod] if pd.notna(t.get('parent_price'))])
    # Qualified 1m coverage: actual entry/exit quotes and relevant R state, no source substitution.
    raw=pd.read_csv(c.b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);raw['clock']=raw.datetime.dt.strftime('%H:%M')
    expected=[c.b.minutes_after(st,k) for st in c.z.x.STARTS for k in range(1,6)]
    fine={}
    for day,g in raw.groupby('date'):
        rr=d[d.date.eq(day)]
        if len(rr)!=1:continue
        rr=rr.iloc[0];g=g.sort_values('clock')
        if list(g.clock)!=expected:continue
        if max(abs(g.open.iloc[0]-rr.open),abs(g.close.iloc[-1]-rr.close),abs(g.high.max()-rr.high),abs(g.low.min()-rr.low))>=.011:continue
        if not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))&(g.volume>=0)).all():continue
        fine[day]=g.set_index('clock')
    quote=[]
    for key in keys:
        ev=read('events/'+key+'_3000_5.csv.gz');tr=read('trades/'+key+'_3000_5.csv.gz').set_index('tid')
        for e in ev[ev.reason.eq('filled')].itertuples():
            dt=pd.Timestamp(e.date);g=fine.get(dt);p=np.nan
            if g is not None:
                if e.basis.startswith('bar_open_'):
                    nxt=c.b.minutes_after(e.clock,1)
                    if nxt in g.index:p=float(g.loc[nxt,'open'])
                elif e.basis.startswith('bar_close_') or e.basis=='daily_close':
                    if e.clock in g.index:p=float(g.loc[e.clock,'close'])
            state_old=state_fine=None
            if e.kind=='entry' and e.module=='R' and g is not None:
                cref=float(d.loc[d.date.eq(dt),'preclose'].iloc[0])
                state_old=tr.loc[e.tid,'state'];state_fine='U' if g.loc['14:50','close']>=cref else 'D'
            quote.append(dict(id=key,date=dt,tid=e.tid,module=e.module,kind=e.kind,clock=e.clock,basis=e.basis,original_price=e.reference,fine_price=p,difference=p-e.reference,date_covered=g is not None,quote_compared=np.isfinite(p),auction_uncertified=e.basis in ['daily_open','daily_close'],old_state=state_old,fine_state=state_fine,state_flip=state_old is not None and state_old!=state_fine))
    fq=c.save('focus_fine_quote_checks.csv',quote)
    keydays=read('key_dates.csv');worst=read('worst_daily_contributions.csv')
    pairs=read('pairs/'+c.BASE+'_3000_5.csv.gz');events=read('events/'+c.BASE+'_3000_5.csv.gz')
    dates=[]
    for label,vals in [('increment_gain_loss',keydays[keydays.id.isin(keys)&keydays.bp.eq(5)&keydays.stock.eq(3000)].date),('common_worst',worst[worst.id.isin(keys)].date),('internal_netting',pairs.date),('failed_exit',events[events.reason.ne('filled')].date)]:
        for dt in sorted(set(pd.to_datetime(vals))):dates.append(dict(reason=label,date=dt,fine_available=dt in fine))
    c.save('focus_date_coverage.csv',dates)
    c.save('focus_fine_quote_summary.csv',fq.groupby(['id','module','kind']).agg(n=('tid','size'),date_covered=('date_covered','sum'),quote_compared=('quote_compared','sum'),auction_unknown=('auction_uncertified','sum'),max_abs_price_difference=('difference',lambda v:v.abs().max()),state_flips=('state_flip','sum')).reset_index())
    # Additional boundary tests on real simulation interface, not merely mirrored assertions.
    dt=pd.date_range('2026-01-05',periods=4)
    tiny=pd.DataFrame(dict(date=dt,open=[100]*4,close=[100]*4,limit_up=[110]*4,limit_down=[90]*4,volume=[100]*4,dividend_today=[0]*4))
    rule=dict(id='test',P='Pall',N='N2',R='-',policy='L1',combo='test',modules=2)
    pp={'Pall':[c.newplan('Pall',0,dt[0],100,'09:35','bar_open_0935','09:25',0,'15:00',100,'daily_close')],'N2':[c.newplan('N2',0,dt[0],100,'15:00','daily_close','previous_close',1,'10:05',100,'bar_close_1005')]}
    met,a,t,ss=c.simulate(tiny,{dt[1]:{'10:05':dict(volume=100)}},{},pp,rule,1000,5)
    assert met['completed']==2 and met['internal_pairs']==1 # exit releases L1 before N new
    alt=tiny.copy();alt.loc[0,'close']=90
    pp2={'Pall':[dict(pp['Pall'][0],exit_price=90)],'N2':[dict(pp['N2'][0],entry_price=90)]}
    met,a,t,ss=c.simulate(alt,{dt[1]:{'10:05':dict(volume=100)}},{},pp2,rule,1000,5)
    assert ss[ss.module.eq('N')].reason.iloc[0]=='policy_rejected' and met['exit_failed']==1
    # Same timestamp distinct quotation bases must not net.
    rule=dict(rule,R='R1',P='-',policy='F')
    pp3={'N2':[c.newplan('N2',0,dt[0],100,'15:00','daily_close','previous_close',1,'09:35',100,'bar_close_0935')],
         'R1':[c.newplan('R1',0,dt[0],100,'15:00','daily_close','14:50',1,'09:35',100,'bar_open_0935')]}
    met,_,_,_=c.simulate(tiny,{dt[1]:{'09:35':dict(volume=100)}},{},pp3,rule,1000,5)
    assert met['internal_pairs']==1 and met['external_orders']==2
    pending_rule=dict(rule,P='-',R='-',N='N2')
    pending_plans={'N2':[c.newplan('N2',3,dt[3],100,'15:00','daily_close','previous_close')]}
    met,a,t,ss=c.simulate(tiny,{}, {},pending_plans,pending_rule,1000,5)
    assert met['pending']==1 and met['completed']==0 and met['increment']<0 and a.shares.iloc[-1]==2000
    cross=tiny.copy();cross.date=pd.to_datetime(['2025-12-30','2025-12-31','2026-01-02','2026-01-05'])
    cross_plan={'N2':[c.newplan('N2',1,cross.date.iloc[1],100,'15:00','daily_close','previous_close',2,'09:25',100,'daily_open')]}
    met,aa,tt,_=c.simulate(cross,{}, {},cross_plan,pending_rule,1000,5)
    assert met['completed']==1 and tt.actual_exit.iloc[0]=='2026-01-02' and aa.external.iloc[-1]>0
    falling=tiny.copy();falling.loc[3,'close']=90
    pf={'N2':[c.newplan('N2',3,dt[3],90,'15:00','daily_close','previous_close')]}
    met,aa,_,_=c.simulate(falling,{}, {},pf,pending_rule,1000,5)
    assert abs(aa.hold_absolute.iloc[-1]+10000)<1e-6 and met['absolute_mdd']>10000 and aa.external.iloc[-1]>0
    c.js('delivery_boundary_validation.json',dict(status='PASS',cases=['same_close_L1_exit_then_new','failed_exit_does_not_release_L1','same_time_different_bases_not_netted','B03_original_matched_delay_exact','terminal_unclosed_batch_marked','cross_year_Tplus1','cash_injection_does_not_erase_account_drawdown']))
    # Human-facing report, explicit direct answers, full rules and evidence links.
    cols=['increment','relative_mdd','absolute_mdd','completed','win','worst','deposits','max_shares']
    base=main.loc[c.BASE];best=main.loc[focus['profit']];l1=main.loc['Pall_N2_R1_L1']
    costleaders=pd.concat([g.sort_values(['increment','id'],ascending=[False,True]).head(1) for _,g in s[s.stock.eq(3000)].groupby('bp')])
    c.save('delivery_cost_leaders.csv',costleaders)
    yearly=read('periods.csv')
    label={'Pall':'正T四阶段','PUR':'正T仅上升/震荡','N0':'深跌隔夜买无止损','N2':'深跌隔夜买2%触发','R1':'隔夜卖原买回','R05':'隔夜卖B等跌0.5%','Rsmall':'隔夜卖未跌预定开盘','Rprofit':'隔夜卖未跌等尾盘','F':'全参加','L1':'同向最多一笔','L2':'同向最多两笔'}
    def name(key):return '＋'.join(label[v] for v in key.split('_'))
    def named(df):
        df=df.copy()
        if 'id' in df:df.insert(0,'具体组合',df.id.map(name))
        return df.rename(columns=HEAD)
    selected=list(dict.fromkeys([c.BASE,focus['profit']]+([focus['risk']] if focus['risk'] else [])+[focus['simple']]))
    text=['# B24多方向同时参与与收益回撤组合研究报告',
    '状态：submitted／待统筹审核。direction_id：foxconn-t0；content_id：foxconn-t0-20261002-b24。行情截至2026-09-11，共同窗口2022年首个交易日至2026-09-11；所有人民币数值为历史模型事实，非用户持仓或真实收益。',
    f'**【模型事实】指定全机会主对照累计多赚{base.increment:,.2f}元；做T相对持有最大收盘回撤{base.relative_mdd:,.2f}元，整个账户剔除补款后的最大收盘回撤{base.absolute_mdd:,.2f}元。** 同资源一直持有的全账户回撤为{base.hold_mdd:,.2f}元。统一3000股研究旧仓、每笔1000股，累计必要补款{base.deposits:,.2f}元，最高实际持股{int(base.max_shares)}股。两种回撤均从共同起点0计算。',
    f'**【模型事实】本固定矩阵利润最多的是“{name(best.name)}”：{best.increment:,.2f}元，比指定主对照多{best.increment-base.increment:,.2f}元。** 相对回撤{best.relative_mdd:,.2f}元、全账户回撤{best.absolute_mdd:,.2f}元、累计补款{best.deposits:,.2f}元。全参加是主对照，并未被预先裁定为最佳。',
    f'仅在原主对照上限制同向最多一笔：净增量{l1.increment:,.2f}元，比全参加变化{l1.increment-base.increment:,.2f}元；相对回撤降低{base.relative_mdd-l1.relative_mdd:,.2f}元，全账户回撤降低{base.absolute_mdd-l1.absolute_mdd:,.2f}元；累计补款下降{base.deposits-l1.deposits:,.2f}元至{l1.deposits:,.2f}元。少做{int(l1.policy_rejected)}个信号。这是原版本内的限制效果，不混入退出版本改动。',
    '## 一、收益与风险取舍',
    named(s[s.stock.eq(3000)&s.bp.eq(5)&s.id.isin(selected)][['id']+cols]).to_markdown(index=False,floatfmt='.2f'),
    (f'风险取舍“{name(focus["risk"])}”相对利润冠军少赚{best.increment-main.loc[focus["risk"],"increment"]:,.2f}元，做T回撤减少{best.relative_mdd-main.loc[focus["risk"],"relative_mdd"]:,.2f}元，全账户回撤减少{best.absolute_mdd-main.loc[focus["risk"],"absolute_mdd"]:,.2f}元；累计补款{main.loc[focus["risk"],"deposits"]:,.2f}元。' if focus['risk'] else '本轮未找到同时改善利润冠军两种回撤的非支配方案。'),
    f'较少方向的取舍“{name(focus["simple"])}”比利润冠军少赚{best.increment-main.loc[focus["simple"],"increment"]:,.2f}元；做T回撤更低不代表底仓整体更安全，其全账户回撤为{main.loc[focus["simple"],"absolute_mdd"]:,.2f}元，补款{main.loc[focus["simple"],"deposits"]:,.2f}元。',
    '【观点】并列利润最多、相对利润冠军同时降低两种回撤且在非支配集合中利润最高、较少方向的简单取舍；完全重复者只展示一次。非支配判断同时考虑利润、两种回撤、补款和最高持股，不构造唯一总分。复杂度只用于简单取舍，不作为收益认证。',
    '## 二、三个方向一起参加究竟多赚多少']
    family=['Pall_F','N2_F','R1_F','Pall_N2_F','Pall_R1_F','N2_R1_F',c.BASE]
    text+=[named(main.loc[family].reset_index()[['id']+cols]).to_markdown(index=False,floatfmt='.2f')]
    removal=[]
    for mod,key in [('正T','N2_R1_F'),('深跌隔夜买','Pall_R1_F'),('隔夜卖回补','Pall_N2_F')]:
        r=main.loc[key];removal.append(dict(新增方向=mod,新增利润=base.increment-r.increment,额外补款=base.deposits-r.deposits,相对回撤变化=base.relative_mdd-r.relative_mdd,全账户回撤变化=base.absolute_mdd-r.absolute_mdd))
    text +=[table(pd.DataFrame(removal)),'上述均从共同起点重算全账户；正值的回撤变化表示增加该方向后回撤变大。没有减旧机会利润或使用2020旧金额作分母。']
    comp=read('comparisons.csv');inter=comp[(comp.stock==3000)&(comp.bp==5)&comp.reference.eq('sum_same_window_single_accounts')&comp.id.isin(keys)]
    text+=['## 三、限制参与与已有退出办法',named(main.loc[['Pall_N2_R1_F','Pall_N2_R1_L1','Pall_N2_R1_L2']].reset_index()[['id']+cols+['policy_rejected','worst5','longest_loss','recovery_days']]).to_markdown(index=False,floatfmt='.2f')]
    pol=read('policy_opportunity_cost.csv');text+=[table(pol[(pol.stock==3000)&pol.bp.eq(5)&pol.id.isin(['Pall_N2_R1_L1','Pall_N2_R1_L2'])]),'避免亏损和错失盈利用全参加账户对应逻辑批次计算，剩余差额保留为净额、税、延期等相互影响，不能把删单金额当成精确账户增益。']
    neighbors=['Pall_N0_R1_F','Pall_N2_R05_F','Pall_N2_Rsmall_F','Pall_N2_Rprofit_F','PUR_N2_R1_F']
    text +=[named(main.loc[neighbors].reset_index()[['id']+cols]).to_markdown(index=False,floatfmt='.2f'),'上表每行相对原主对照只换一个模块版本。完整132规则之间只变一个维度的相邻对照保存在adjacent_rules.csv，包含各参与政策，未按结果增加组合。',
    '## 四、组合省费、税和共同亏损',
    table(inter,['id','increment','reference_cash_change','slippage_change','fee_change','tax_change','reserve_change','dividend_change','pending_mark_change']),
    table(main.loc[selected].reset_index(),['id','avg_profit','avg_loss','winning_day_pct','behind_days']),
    '盈利交易日比例以共同窗口所有交易日为分母，包括无交易日；平均赚亏仅针对完成逻辑批次，与包含未完成估值和权益准备的账户日损益不是同一口径。',
    '上方组合交互表是组合减去同窗口、同资源、同政策各单方向账户之和的交互差。恒等式：净变化＝参考价现金变化−滑点变化−费用变化−FIFO税变化−期末准备变化＋权益差变化＋未完成持股市值变化。费用为负表示省费；F下主要反映内部净额及税的交互，L1还包括共享名额改变参与，不能全称为净额省费。',
    table(read('daily_correlations.csv')),
    table(worst[worst.id.eq(c.BASE)].head(5)),
    '每日贡献包括无交易日和未完成批次的估值，税准备单列adjust；相关性只帮助解释，同日风险最终由完整账户验证。亏损分摊随内部配对方式变化，组合总账不随归属名称变化。',
    '## 五、年份、成本与增益集中',
    named(s[s.stock.eq(3000)&s.id.isin(selected)][['id','bp']+cols]).to_markdown(index=False,floatfmt='.2f'),
    table(read('periods.csv')[lambda f:f.stock.eq(3000)&f.id.isin(selected)&f.bp.eq(5)]),
    named(costleaders[['id','bp']+cols]).to_markdown(index=False,floatfmt='.2f'),
    ('【模型事实】三档成本下的利润冠军相同；这只是固定历史内的成本稳健性，不是未来保证。' if costleaders.id.nunique()==1 else '【模型事实】三档成本下的利润冠军并不完全一致，不能称某一方案对成本变化始终最优。'),
    table(yearly[yearly.stock.eq(3000)&yearly.id.isin(selected)&yearly.bp.eq(5)&yearly.increment.lt(0)]),
    '上表单列取舍方案的负增量年份/分期，空表表示该口径没有负段；不是每年必盈要求。各方案全部年份和三成本均保留在periods.csv；不按当年事后冠军切换。三成本为每边0.05%/0.11%/0.20%滑点另加费用、税，N固定主成本触发路径后改变成本。',
    table(read('concentration.csv')[lambda f:f.stock.eq(3000)&f.bp.eq(5)&f.reference.eq(c.BASE)&f.id.isin(selected)]),
    '前1/3/5日为“相对主对照每日增量”的最大正贡献，without是集中性诊断，不是删赢家策略。负年份、集中性与已反复检视同历史的事实限制未来推断。',
    '## 六、资源、覆盖与未解决问题',
    table(main.loc[keys].reset_index(),['id','signals','accepted','completed','pending','policy_rejected','untradeable','quote_unknown','inventory_rejected','exit_failed','deposits','max_deposit','max_buy_cash','buy_cash_total','max_batch_days','max_shares','min_old_available','deposit_yuan_days']),
    '补款与最大买单不同：卖出回款可用于后续买入；最大买单为真实外部净买订单总款。累计补款保留到期末，deposit_yuan_days反映该资金留在账户的时间积，max_batch_days为最长逻辑持有/待回补日数。足额现金没有缩量、删单；退出失败继续记风险。',
    table(read('resource_diagnostic.csv')),
    '3000股主资源没有库存受阻，K保持3000，不增开资源网格。最低历史旧股数量由冻结F事件流真实可卖旧股低点推得；不是建议仓位或未来保证。',
    table(read('delivery_sampled_intraday_stress.csv')),
    '离散5分钟收价及事件报价观察到的压力另列；未观察到的区间内路径和竞价排队仍未知。收盘全账户回撤不是盘中最大浮亏，离散路径也不称连续盘中最大值。',
    table(read('focus_fine_quote_summary.csv')),
    '细数据仅用于核对，没有替换为更有利价格。日期覆盖、报价比对、触发路径认证是三回事；收盘/开盘竞价代理仍未获成交保证。重点增益损失、共同大亏、净额和失败退出日期逐日覆盖见focus_date_coverage.csv；父R触发细路径见B23，父N双侧细路径仅9/61，不把覆盖日自动升级为真实可成交。',
    '## 七、规则、旧结果桥与验证',
    '本报告“前日/昨日”均指上一交易日，累计N日指N个交易日；P量比均值包含昨日，R量均值排除昨日，不能互换。',
    'P全：冻结上升U、震荡R、下降D、修复C四阶段，每天只选一个阶段。U/D前日收盘在当天最高最低区间下方40%以内（严格<40%），且今日较昨收参考preclose低开至少1%；R截至昨日连跌≥3日且前日成交量/截至前日20日均量<0.8；C前日个股阴线、上证下跌且今日低开。P主仅U/R。09:25知道开盘条件后，09:35开始区间开价买1000，收盘卖1000可卖旧股；09:35缺价/不可买不新开，卖失败延续至后续合规开盘。',
    'N无/N2：前日20日累计收益≤−16.1565018%，今日收盘买1000；次日10:00截止，无止损或原2%止损触发。观察完成后按B12下一bar收价成交代理，通常10:05；2%不是净亏损上限。止损参考使用原主成本及当时已知权益调整，不用未来实际FIFO卖出税。',
    'R：A为昨日顶部20%、量≤昨日之前20日均量且20日累计涨幅≥0；否则B为昨日3日累计跌至少4%且顶部30%。今日收盘卖1000，重叠A优先，每天模块新卖最多1000。原版A次日涨1%触发否则14:50；B低开0.5%后最早09:30，否则跌1%/涨2%触发，11:00截止。近邻仅B等待改跌0.5%。小亏版：卖出日14:50未跌时A预定次日开盘、B等跌0.5%，已跌A仍涨1%/14:50、B等跌1%；利润版仅将A未跌改次日固定14:50。未跌为14:50完成价≥当日preclose。盘中触发额外完整间隔、截止优先、失败恢复均继承B23。',
    'F全参加；L1/L2同向最多一/两笔未完成逻辑批次，加股P/N与减股R分别计数，不净抵消。退出优先，失败不释放名额；新开按信号可知先后、完全同刻P/N/R。只有同刻同报价且此前确定的反向意图内部配对，真实残余成交才改变FIFO与T+1或承担费用税费。',
    table(pd.DataFrame(bridge)),
    table(pd.DataFrame(extras)),
    'N本轮63笔与旧61笔的差异明确列在上表。旧研究的全特征完整性、次日价格和近涨停代理参与筛选；本轮只按任务书冻结的前日20日收益条件形成意图，再用统一报价/涨跌停/T+1判断能否执行，不继承无关特征缺失过滤。该变化与FIFO口径桥分别保存，不能把新增日期冒充原61笔；原61笔父路径/费用精确复现仍通过。表内逻辑损益含该笔真实分配的费用税和权益，期末准备另扣。',
    '旧P的71笔同日期09:35压力已精确复现；旧2024窗口、旧费用、旧全日质量筛选只用于核对，未把未来全日质量筛选带入本轮09:35入场。本轮2022窗、完整账户、限价失败和FIFO不同，数值差异明确桥接，旧报告与SHA不改。',
    f'独立重放{iv["accounts"]}个账户的每日现金、股票、FIFO税龄/股息税、应收与付款、持有对照、补款剔除权益与回撤通过；原R四版三成本共12组在2022新起点对齐父账；3个共享账户截断重放通过。边界测试包含同刻三方向、同向名额、T+1、失败退出、同刻不同报价不配对及现金流恒等式。',
    '首轮完成396个账后在JSON整数键序列化失败；同时修正内部配对批次费用与真实外部剩余成交不一致的归属问题，FIFO税现在逐段关联实际卖出批次。所有账户总利润、两种回撤和资金需求与修正前逐项保持一致，旧单笔胜率/损益统计已被新版本替代，见allocation_revision_bridge.csv。后续去除N加载器对未来整天完整性的依赖并加入逐笔截断检验，全部8模块历史路径字节不变。中途取消的慢速验账未算通过，最后全396账户重新独立验账。修正及影响范围保存在IMPLEMENTATION_CORRECTIONS.md，首轮快照和失败未删除。最终结论只使用独立核验通过的修订结果。',
    '固定账户证据：[B24远端目录](https://github.com/chixig/daily_stock_analysis/tree/'+os.environ['GITHUB_SHA']+'/research/foxconn_t0_20261002_b24)；父账户与动作：[B23固定证据](https://github.com/chixig/daily_stock_analysis/tree/'+c.PARENT+'/research/foxconn_t0_20261002_b23)。全部396摘要、逐日账、相邻规则与哈希均保留，独立验证及最终提交见本地《B24执行交接与验证》。',
    '【观点】结论是固定132条组合规则、三成本共396个策略账户的历史比较中的收益/风险取舍，不是独立样本外、实盘认证或绝对最优。若可靠成交价、退出延迟、费用、公司行为或未来共同亏损使净增量/回撤优势消失，应复核该取舍；不设未经用户授权的收益或回撤硬门槛。不自动采用、交易、监控或开启下一批。']
    header='---\nid: foxconn-t0-b24-report\ntitle: B24多方向同时参与与收益回撤组合研究报告\ntype: project\nstatus: submitted\ngraph: false\ndirection_id: foxconn-t0\ncontent_id: foxconn-t0-20261002-b24\ncreated: 2026-10-02\nupdated: 2026-10-03\nconfidence: medium\nneed_review: true\n---\n\n'
    (R/'DELIVERY.md').write_text(header+'\n\n'.join(text)+'\n')
    for path,h in sealed['files'].items():assert c.sha(path)==h,path
    c.js('delivery_validation.json',dict(status='PASS',accounts=len(s),legacy_matched_P=int(want.n),fine_days=len(fine),new_rules=0,source_manifest_verified=True))
    c.js('delivery_sha256.json',dict(code_sha=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],files={str(p):c.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['delivery_sha256.json','delivery.log','calculation.log','verification.log']}))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    run()
