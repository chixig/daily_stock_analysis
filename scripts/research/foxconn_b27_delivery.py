"""B27 final evidence and report; fixed accounts only, no new strategies."""
import os,json
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_b27 as c
R=c.R
def read(name):return pd.read_csv(R/name)
HEAD={'earlier':'提前笔数','matched':'匹配笔数','price_change':'退出参考价现金差','avoided_later_decline':'避免后续下跌','missed_later_rebound':'错失后续回升','logical_change':'逻辑利润差','cost_tax_attribution':'费用税及归属差','winning_day_pct':'盈利交易日比例(%)','curve':'曲线','peak':'峰时刻','trough':'谷时刻','drawdown':'回撤金额','hold_absolute':'持有底仓贡献','date_covered':'日期覆盖','quotes_compared':'报价核对数','auction_unknown':'竞价未认证','max_abs_difference':'最大绝对价差','n':'笔数','covered':'细决策覆盖','changed':'细决策变化','id':'核对编号','reference':'对照','P':'正T贡献','N':'隔夜买贡献','R':'隔夜卖贡献','increment':'净增量','relative_mdd':'收盘做T回撤','absolute_mdd':'收盘全账户回撤','intraday_relative_mdd':'离散盘中做T回撤','intraday_absolute_mdd':'离散盘中全账户回撤','deposits':'累计补款','max_shares':'最高持股','win':'逻辑胜率(%)','worst':'最大单笔损益','worst5':'最差五笔合计','longest_loss':'最长连亏','recovery_days':'最长收盘恢复天数','avg_profit':'盈利笔平均','avg_loss':'亏损笔平均','completed':'完成笔数','pending':'期末未完成','bp':'每边滑点bp','stock':'旧股','period':'年份/分期','delta':'净变化','top1':'最大一日贡献','top3':'最大三日贡献','top5':'最大五日贡献','without1':'其余日合计去一日','without3':'其余日合计去三日','without5':'其余日合计去五日','removed':'少做笔数','avoided_loss':'避免亏损','missed_profit':'错失盈利','actual_change':'实际账户变化','interaction':'其他交互','module':'模块','date':'日期','signals':'信号数','accepted':'已开笔数','policy_rejected':'政策拒绝','inventory_rejected':'库存拒绝','quote_unknown':'缺报价','untradeable':'不可成交','exit_failed':'失败退出次数','max_deposit':'最大单次补款','max_buy_cash':'最大真实买单总款','min_old_available':'最低可卖旧股','deposit_yuan_days':'补款留存元天','max_batch_days':'最长逻辑批次日数','relative_day':'当日做T损益','absolute_day':'当日全账户损益','adjust':'税准备调整','module1':'方向一','module2':'方向二','correlation':'日贡献相关性','both_negative':'同日俱亏天数','reference_cash_change':'参考价现金差','slippage_change':'滑点差','fee_change':'费用差','tax_change':'FIFO税差','terminal_reserve_change':'期末税准备差','dividend_relative_change':'股息权益差','pending_mark_change':'期末估值差','dimension':'变化维度'}
LABEL={'Pclose':'正T收盘卖','Pstop2':'正T完成收价跌2%后延迟卖','P1100':'正T11:00决定/11:05卖','N1000s2':'深跌2%触发/10:00截止','N1000none':'深跌无止损/10:00截止','N0935s2':'深跌2%触发/09:35截止','N0935none':'深跌无止损/09:35截止','F':'全参加','L1':'同向最多一笔','Pall':'四阶段正T','PUR':'上升震荡正T','N2':'深跌2%/10:00','N0':'深跌无止损/10:00','R1':'原隔夜卖回补','Rprofit':'状态切换买回锚点'}
LABEL.update(PT1='完成收价涨1%固定止盈',PT2='完成收价涨2%固定止盈',PF105='先涨1%再从收价峰回落0.5%',PF110='先涨1%再从收价峰回落1%',PF205='先涨2%再从收价峰回落0.5%',PF210='先涨2%再从收价峰回落1%')
def name(key):return '＋'.join(LABEL[v] for v in key.split('_'))
def table(f,cols=None,names=False):
    f=(f[cols] if cols else f).copy()
    if names and 'id' in f:f.insert(0,'具体动作',f.id.map(name))
    return f.rename(columns=HEAD).to_markdown(index=False,floatfmt='.2f')

def run():
    sealed=json.loads((R/'result_sha256.json').read_text())
    for p,h in sealed['files'].items():assert c.sha(p)==h,p
    iv=json.loads((R/'independent_validation.json').read_text());assert iv['status']=='PASS'
    s=read('account_summary.csv');main=s.query('stock==3000 and bp==5').set_index('id');base=main.loc[c.BASE]
    d,_,_,_,plans=c.load();p=c.c
    # Bounded diagnostic data, never changes source or any account.
    raw=pd.read_csv(p.b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);raw['clock']=raw.datetime.dt.strftime('%H:%M')
    expected=[p.b.minutes_after(st,k) for st in p.z.x.STARTS for k in range(1,6)];fine={}
    for dt,g in raw.groupby('date'):
        rr=d[d.date.eq(dt)]
        if len(rr)!=1:continue
        rr=rr.iloc[0];g=g.sort_values('clock')
        if list(g.clock)!=expected:continue
        if max(abs(g.open.iloc[0]-rr.open),abs(g.close.iloc[-1]-rr.close),abs(g.high.max()-rr.high),abs(g.low.min()-rr.low))>=.011:continue
        if not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))&(g.volume>=0)).all():continue
        fine[dt]=g.set_index('clock')
    from decimal import Decimal
    fd=[];fq=[];rd=pd.read_csv(R/'exit_decisions.csv',keep_default_na=False)
    for mode in c.SPECS:
        for t in plans[mode]:
            dt=pd.Timestamp(t['entry']);g=fine.get(dt);dec={};cent={}
            if g is not None:
                fb={k:dict(close=str(g.loc[k,'close']),volume=str(g.loc[[p.b.minutes_after(k,-j) for j in range(5)],'volume'].sum())) for k in c.CLOSES}
                dec=c.pdecision(t,fb,mode)
                cents={k:dict(close=str(Decimal(v['close']).quantize(Decimal('0.01'))),volume=v['volume']) for k,v in fb.items()}
                cent=c.pdecision(t,cents,mode)
            old=rd[(rd['mode']==mode)&(rd.date==t['entry'])].iloc[0]
            fd.append(dict(mode=mode,date=t['entry'],covered=g is not None,original_observation=old.observation,fine_observation=dec.get('observation') or '',cent_observation=cent.get('observation') or '',original_armed=old.armed,fine_armed=dec.get('armed') or '',cent_armed=cent.get('armed') or '',trigger_changed=g is not None and old.observation!=(dec.get('observation') or ''),armed_changed=g is not None and old.armed!=(dec.get('armed') or ''),cent_trigger_changed=g is not None and old.observation!=(cent.get('observation') or ''),cent_armed_changed=g is not None and old.armed!=(cent.get('armed') or '')))
    for key in main.index:
        ev=c.read('events',key+'_3000_5')
        for e in ev[ev.reason.eq('filled')].itertuples():
            g=fine.get(pd.Timestamp(e.date));px=np.nan
            if g is not None:
                if e.basis.startswith('bar_open_'):
                    cl=p.b.minutes_after(e.clock,1)
                    if cl in g.index:px=g.loc[cl,'open']
                elif e.basis.startswith('bar_close_') or e.basis=='daily_close':
                    if e.clock in g.index:px=g.loc[e.clock,'close']
            fq.append(dict(id=key,module=e.module,kind=e.kind,date=e.date,clock=e.clock,basis=e.basis,date_covered=g is not None,quote_compared=np.isfinite(px),auction_unknown=e.basis in ['daily_open','daily_close'],difference=px-e.reference))
    ff=c.save('fine_decision_checks.csv',fd);qq=c.save('fine_quote_checks.csv',fq)
    c.save('fine_decision_summary.csv',ff.groupby('mode').agg(raw_signals=('date','size'),covered=('covered','sum'),trigger_changed=('trigger_changed','sum'),armed_changed=('armed_changed','sum'),cent_trigger_changed=('cent_trigger_changed','sum'),cent_armed_changed=('cent_armed_changed','sum')).reset_index())
    c.save('fine_quote_summary.csv',qq.groupby(['id','module','kind']).agg(n=('date','size'),date_covered=('date_covered','sum'),quotes_compared=('quote_compared','sum'),auction_unknown=('auction_unknown','sum'),max_abs_difference=('difference',lambda x:x.abs().max())).reset_index())
    attr=[];risk=[];pairs=[];stages=[];counts=[];states=[]
    for stock in sorted(s.stock.unique()):
      for bp in [5,11,20]:
        sub=s[s.stock.eq(stock)&s.bp.eq(bp)].set_index('id')
        for key,r in sub.iterrows():
            for folder in ['accounts','stress']:
                g=c.read(folder,f'{key}_{stock}_{bp}')
                for curve in ['relative','absolute']:
                    vals=np.r_[0,g[curve].values];dd=np.maximum.accumulate(vals)-vals;j=int(np.argmax(dd));i=int(np.argmax(vals[:j+1]))
                    a=g.iloc[i-1] if i else None;b=g.iloc[j-1] if j else None
                    def at(row,k):return 'initial0' if not k else str(row.date)+(' '+row.clock+' '+row.basis if folder=='stress' else ' close')
                    rr=dict(id=key,stock=stock,bp=bp,frequency='intraday' if folder=='stress' else 'close',curve=curve,peak=at(a,i),trough=at(b,j),drawdown=dd[j])
                    for col in ['P','N','R','adjust','hold_absolute']:rr[col]=(a[col] if i else 0)-(b[col] if j else 0)
                    assert abs(sum(rr[v] for v in ['P','N','R','adjust'])+(rr['hold_absolute'] if curve=='absolute' else 0)-dd[j])<1e-5
                    risk.append(rr)
            if r.anchor:continue
            ref='Pclose_N2_R1_'+r.policy
            at_=c.read('trades',f'{key}_{stock}_{bp}');bt=c.read('trades',f'{ref}_{stock}_{bp}')
            ae=c.read('events',f'{key}_{stock}_{bp}');be=c.read('events',f'{ref}_{stock}_{bp}')
            ax=ae[ae.kind.eq('exit')&ae.reason.eq('filled')].set_index('tid');bx=be[be.kind.eq('exit')&be.reason.eq('filled')].set_index('tid')
            at_['key']=at_.module+'_'+at_.entry;bt['key']=bt.module+'_'+bt.entry
            at_=at_.set_index('key');bt=bt.set_index('key')
            for tid in at_.index.intersection(bt.index):
                a=at_.loc[tid];b=bt.loc[tid]
                if a.tid not in ax.index or b.tid not in bx.index:continue
                er=ax.loc[a.tid];br=bx.loc[b.tid];price=1000*a.direction*(er.reference-br.reference)
                earlier=(str(a.actual_exit)+' '+a.actual_exit_clock)<(str(b.actual_exit)+' '+b.actual_exit_clock)
                attr.append(dict(id=key,reference=ref,stock=stock,bp=bp,module=a.module,date=a.entry,earlier=earlier,old_exit=str(b.actual_exit)+' '+b.actual_exit_clock,new_exit=str(a.actual_exit)+' '+a.actual_exit_clock,exit_price_change=price,avoided_giveback=max(price,0) if earlier else 0,missed_upside=max(-price,0) if earlier else 0,logical_change=a.realized-b.realized,allocation_cost_difference=a.realized-b.realized-price))
            for stage,gg in at_[at_.module.eq('P')].groupby('stage'):
                stages.append(dict(id=key,stock=stock,bp=bp,stage=stage,n=len(gg),profit=gg.realized.sum(),win=100*gg.realized.gt(0).mean(),worst=gg.realized.min()))
            for t in at_[at_.module.eq('P')].itertuples():
                dec=rd[(rd['mode']==r.P)&(rd.date==t.entry)].iloc[0]
                states.append(dict(id=key,stock=stock,bp=bp,date=t.entry,armed=bool(dec.armed),triggered=bool(dec.observation),reason=dec.reason,unknown_observations=dec.unknown,realized=t.realized,exit_clock=t.actual_exit_clock))
            refs=[ref]
            if r.P.startswith('PF'):refs.append(('PT1' if r.P[2]=='1' else 'PT2')+'_N2_R1_'+r.policy)
            if r.policy=='L1':refs.append(key[:-2]+'F')
            for rf in dict.fromkeys(refs):
                z=sub.loc[rf];row=dict(id=key,reference=rf,stock=stock,bp=bp,**{k:r[k]-z[k] for k in c.METRICS})
                for k in ['reference_cash','slippage','fee','tax','terminal_reserve','dividend_relative','pending_mark']:row[k+'_change']=r[k]-z[k]
                assert abs(row['increment']-(row['reference_cash_change']-row['slippage_change']-row['fee_change']-row['tax_change']-row['terminal_reserve_change']+row['dividend_relative_change']+row['pending_mark_change']))<1e-5
                pairs.append(row)
    c.save('matched_exit_attribution.csv',attr);aa=pd.DataFrame(attr)
    c.save('matched_exit_summary.csv',aa.groupby(['id','stock','bp','module']).agg(n=('date','size'),earlier=('earlier','sum'),price_change=('exit_price_change','sum'),avoided_giveback=('avoided_giveback','sum'),missed_upside=('missed_upside','sum'),logical_change=('logical_change','sum'),allocation_cost_difference=('allocation_cost_difference','sum')).reset_index())
    c.save('risk_attribution.csv',risk);c.save('target_follow_comparisons.csv',pairs);c.save('stage_diagnostics.csv',stages)
    st=c.save('executed_P_states.csv',states)
    c.save('executed_P_state_summary.csv',st.groupby(['id','stock','bp','armed','triggered','reason']).agg(n=('date','size'),logical_profit=('realized','sum'),unknown_observations=('unknown_observations','sum')).reset_index())
    # Full parent common-grid bridge. B24 published5m and event-only histories stay distinct.
    old=pd.read_csv(c.OLD/'account_summary.csv');bridge=[]
    for r in s[s.stock.eq(3000)&s.parent.fillna('').ne('')].itertuples():
        o=old[old.id.eq(r.parent)&old.stock.eq(3000)&old.bp.eq(r.bp)].iloc[0]
        bridge.append(dict(id=r.id,parent=r.parent,bp=r.bp,profit_change=r.increment-o.increment,old_D=o.intraday_relative_mdd,new_D=r.intraday_relative_mdd,old_X=o.intraday_absolute_mdd,new_X=r.intraday_absolute_mdd))
    c.save('all_parent_common_grid_bridge.csv',bridge)
    for name_ in ['B24_published_grid_bridge_inherited.csv','B24_event_only_bridge_inherited.csv']:c.save(name_,pd.read_csv(c.OLD/name_))
    # Key dates, all main rules including rejected and changed execution opportunities.
    kd=read('key_dates.csv');dates=[]
    for key in main.index:
        val=set(kd[kd.id.eq(key)&kd.bp.eq(5)].date)
        ev=c.read('events',key+'_3000_5');val|=set(ev[ev.reason.ne('filled')].date)
        if key in set(aa.id):val|=set(aa[aa.id.eq(key)&aa.bp.eq(5)&aa.earlier].date)
        for dt in val:dates.append(dict(id=key,date=dt,fine_available=pd.Timestamp(dt) in fine))
    c.save('focus_date_coverage.csv',dates)
    for path,h in sealed['files'].items():assert c.sha(path)==h,path
    c.js('delivery_validation.json',dict(status='PASS',accounts=len(s),fine_days=len(fine),new_candidates=0,all_sealed_results_unchanged=True,feature_validation=json.loads((R/'independent_feature_validation.json').read_text()),tests=['fixed_and_following_exit_total_account_bridge','all_cost_profit_attribution','all_four_risk_module_hold_bridge','fine_raw_and_cent_diagnostic_only','all15_parent_common_grid_bridge']))
    # Findings added after reading fixed result metadata, never used to change registry.
    commentary="**【研究判断】本轮没有找到比原收盘退出更赚钱的新方案；原重点收益基线继续保留。同时新增一个有明确代价的风险候选：正T完成收价涨2%后，下一完整bar收价退出。** 它不是收益升级，也不是全账户风险全面下降；用户选择提高收益，因此不自动用它替换原版。四种跟随退出在本轮核心指标下均被更简单的2%固定盈利退出支配，不采用跟随版。\n\n【主成本模型事实】原基线净80,189.30元，收盘做T/全账户回撤3,673.14/71,389.70，盘中4,904.39/78,289.70，必要补款37,259.66。涨2%退出净79,398.00元，少791.30；收盘两回撤3,673.14/73,677.08，盘中4,242.04/80,577.08，补款35,134.30。它减少做T盘中回撤662.35元、必要补款2,125.36元，最大单亏2,263.98降到1,900.54；但两种全账户回撤都增加2,287.38元。逻辑胜率59.79%→62.37%，两版均194批完成，不靠少参加信号提高胜率。\n\n涨1%固定退出净70,713.71元，少9,475.59，虽胜率63.92%为本轮最高，却切掉更多收益。四种跟随（先涨1%/回落0.5%、先涨1%/回落1%、先涨2%/回落0.5%、先涨2%/回落1%）净69,345.39/74,389.88/73,920.35/74,869.51元，均比原版少，亦均低于固定2%版。跟随止盈“给上涨留空间”的假设没有转化为更高全期收益，须看匹配退出的回吐/继续上涨归因，而不能凭机制听起来合理推荐。\n\n【成本边界】2%版在5/11/20bp分别比原版少791.30/826.78/880.00元；主/中成本做T盘中回撤减少662.35/349.35元，20bp则与原版同为5,334.10元。三档全账户盘中回撤均更大，补款均较少。不能将主成本的局部风险改善概括成各成本全面改善。2%版叠加L1在主成本再少1,070.69元、四回撤不变、补款增加，不默认叠加。\n\n【集中性反证】2%版相对原版全期−791.30元，其中最佳改善日+3,755.69元，其余日合计−4,546.99元；前三/前五改善日分别+7,980.85/+10,318.17，其余更负。其2022年度自身增量−1,013.67元。它仅是当前历史下的有限风险取舍，未证明跨期稳定。旧全表利润冠军仍为82,561.48元的旧锚点，不算本轮创新。"
    profit=main.sort_values('increment',ascending=False).index[0];core=main[~main.anchor];corebest=core.sort_values('increment',ascending=False).index[0]
    pf=read('pareto.csv');front=main.loc[pf.query('stock==3000 and bp==5 and pareto').id]
    highwin=main.sort_values(['win','increment'],ascending=False).index[0]
    # Display original and global profit leader, then a distinct best core only when superior.
    highlights=list(dict.fromkeys([profit,c.BASE,'PT2_N2_R1_F']))
    assert all(k in front.index for k in highlights)
    c.js('delivery_focus.json',dict(profit=profit,corebest=corebest,highest_win=highwin,highlights=highlights,all_Pareto=list(front.index),risk_candidate='PT2_N2_R1_F',rule='old global profit and baseline plus fixed2pct limited risk/funding tradeoff; all3 Pareto; not profit upgrade or automatic adoption'))
    metrics=['id','increment','relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd','deposits','max_shares']
    def selected(f):return f.query('stock==3000 and bp==5') if 'stock' in f and 'bp' in f else f
    decision_sum=rd.assign(triggered=rd.observation.ne(''),armed_flag=rd.armed.ne('')).groupby('mode').agg(raw_signals=('date','size'),triggered=('triggered','sum'),armed=('armed_flag','sum'),unknown=('unknown',lambda x:pd.to_numeric(x).sum())).reset_index();c.save('raw_decision_summary.csv',decision_sum)
    txt=['# B27正T盈利退出与跟随止盈研究报告',
      '【事实】用户选择提高收益、研究新交易机制并比较风险代价；本轮执行前冻结七P退出×F/L1加三锚点17规则、三成本51账户。行情仍2022年首交易日至2026-09-11，3000研究旧股、初始现金0、每笔1000且足额补款。主成本每边5bp滑点另加日期费用/FIFO股息税及准备。金额元，累计相对同流量持有的模型净增量，非年收益、真实持仓或实盘结果。状态submitted／待统筹审核。',
      commentary,
      '## 1. 核心比较及明确动作',
      'P原上升/震荡信号及09:35开价买不变。固定盈利版在完成收价≥入场参考价×1.01/1.02时触发。跟随版先达到上述幅度才激活，之后只更新已完成收价最高值H；当前收价≤H×0.995/0.99触发。回落为相对H的比例，不是减0.5/1个百分点，不用高低价拼路径。只观察09:40—14:50有效完成收价和正量；触发后下一完整bar收价卖。未触发原收盘卖，失败意图锁定并持续重试，T+1旧股合法性不变。涨幅是参考价变化，不保证净盈利。',
      'N2深跌买原2%/10:00截止，R1隔夜卖原两类买回完整固定。F只保留原机会不加跨方向限额，L1限制P/N未平最多一笔、R另最多一笔。同刻不同报价不能配对，不出售当天新股；缺资金按足额补款，不缩量。',
      table(core.reset_index(),metrics,True),
      '## 2. 触发、激活与退出后涨跌',
      table(decision_sum),
      '原始57条P意图含不可成交日期；上表不是57笔已成交。原始缺观察及已执行状态分开，未触发不宣称全路径已知。下表为主成本真实已开P批次。',
      table(selected(read('executed_P_state_summary.csv'))),
      table(selected(read('matched_exit_summary.csv'))),
      '避免回吐/错失上涨是同一原入场日期、新退出参考价相对原实际退出参考价的现金归因；只在确实提前完成者计这两个方向。实际逻辑利润差含费用税和内部配对归属，总账户桥另列；不是事后按结果选日。收益比较含N/R交互，不将三模块独立利润相加。',
      '## 3. 跟随退出相对固定止盈、L1边际',
      table(selected(read('target_follow_comparisons.csv')),['id','reference','increment','relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd','deposits','win','worst']),
      table(selected(read('policy_opportunity_cost.csv')),names=True),
      '跟随与相同激活幅度的固定止盈作对照，避免把“比某止盈版好”说成“比原收盘好”。L1效果逐版全账计算，失败未退出仍占名额，不预设叠加风控有利。',
      '## 4. 胜率、尾部、资金和取舍',
      table(s.query('stock==3000 and bp==5'),['id','completed','pending','win','winning_day_pct','avg_profit','avg_loss','worst','worst5','longest_loss','recovery_days'],True),
      table(s.query('stock==3000 and bp==5'),['id','deposits','max_deposit','max_buy_cash','max_shares','min_old_available','deposit_yuan_days','max_batch_days'],True),
      '补款留存元天是必要外部流入至期末的加权留存；旧股初始价值不在补款里，最大真实买单含已有现金，均不是个人账户资金授权。统一K先于排名确定，不因利润排序改底仓。',
      table(main.loc[highlights].reset_index(),metrics,True),
      '最高逻辑胜率单列：',
      table(main.loc[[highwin]].reset_index(),['id','increment','win','worst','worst5','intraday_relative_mdd','intraday_absolute_mdd'],True),
      '全部非支配取舍与所有指标见pareto/account_summary，不构造权重总分、不要求四回撤必须同降、不把小幅下降称稳健。',
      '## 5. 三成本、各年与集中性',
      table(s[s.stock.eq(3000)],['id','bp','increment','relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd','deposits','win','worst'],True),
      table(read('periods.csv').query('stock==3000'),['id','bp','period','increment','relative_mdd','absolute_mdd','intraday_relative_mdd','intraday_absolute_mdd']),
      table(read('concentration.csv').query('stock==3000')),
      table(selected(read('stage_diagnostics.csv'))),
      '2022—2023及各年收益/风险保留。前1/3/5日与其余日只是集中性诊断，不删大赢家或动态追随当年冠军；U/R仅分组解释，不拼新策略。全部相邻规则对照adjacent_rules.csv，负区域反向诊断opposite_direction_regions.csv按同日期重新扣费，不直接把净收益取负，也不授权卖空。',
      '## 6. 四种峰谷及底仓贡献',
      table(selected(read('risk_attribution.csv'))),
      '贡献为同一峰谷段峰减谷，正值加大回撤，负值抵消。全账户还加同段底仓贡献；不能称它为独立持有全历史最大回撤。每条完整曲线分别求峰谷，不相加不同策略最大回撤。',
      table(read('all_parent_common_grid_bridge.csv')),
      '旧15账日线与净单相同，新旧盘中都用本轮共同网格；如指标变动须归为观察点变化，不称经济改进。B24已发布5分钟/实际交易事件桥分别继承，不混用。',
      '## 7. 细分钟和独立验证',
      table(read('fine_decision_summary.csv')),
      table(ff[ff.trigger_changed|ff.armed_changed]),
      table(read('fine_quote_summary.csv')),
      f'93日父合格细数据，本批实际通过质量筛选{len(fine)}日。原始细数与分位诊断并列，只帮助识别数值表示/行情口径差异；不替换主价/信号。激活、触发、报价覆盖不同，关键日期见focus_date_coverage.csv，未覆盖及竞价不认证。',
      f'独立重建{iv["accounts"]}账户，每账户{iv["intraday_points_per_account"]}个共同格点，共{iv["total_intraday_points"]}点；{iv["prefixes"]}前缀通过。独立Fraction从原始CSV另算激活、峰值、首触发和未知数，独立检查实际P退出时刻/参考价（锁定K的历史无库存退出阻塞）。现金/FIFO税/权益/同流量持有/每日与公共点权益/四回撤另重建。',
      '共同网格包含无交易、退出后以及待履约状态，完成收价先于随后开价，同报价成交后估值，缺口不未来填充；离散网格不是连续盘中最大亏损。合成测试不等于历史成交，独立程序不是第二行情商，多轮历史筛选不是样本外。',
      '## 8. 经济差额与永久证据',
      table(selected(read('target_follow_comparisons.csv')),['id','reference','increment','reference_cash_change','slippage_change','fee_change','tax_change','terminal_reserve_change','dividend_relative_change','pending_mark_change']),
      '净增量变化=参考价现金差−滑点差−费用差−FIFO税差−期末准备差＋股息相对差＋未完成估值差；全部对照断言通过。可靠成交、成本、公司行为或新历史改变优势时复核对应取舍，不凭本轮宣布全局最优。',
      '全部TASK/PROTOCOL/注册/输入代码SHA、原始及逐笔决策、账户净单/逻辑/FIFO/权益、共同曲线、成本/时期/集中性/风险/独立验证及manifest永久留指定GitHub。最终固定提交、运行及错误修订见本地执行交接。原阶段整理和B24—B26材料不改；不合main、不派发、不交易/监控或自动B28。'
    ]
    (R/'DELIVERY.md').write_text('\n\n'.join(txt)+'\n')
    c.js('delivery_sha256.json',dict(code_sha=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],files={str(p):c.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['delivery_sha256.json','calculation.log','verification.log','delivery.log']}))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    try:run()
    except Exception:
        import traceback
        c.js('delivery_failure_'+os.environ['GITHUB_RUN_ID']+'.json',dict(traceback=traceback.format_exc()));raise
