"""B23 state-conditioned existing buybacks; GitHub-only computation."""
import os,sys,json,hashlib,itertools,subprocess,traceback
from pathlib import Path
from decimal import Decimal
import numpy as np
import pandas as pd
import foxconn_b22 as z
q=z.q;y=z.y;x=z.x;b=z.b
R=Path('research/foxconn_t0_20261002_b23');PARENT='fa0a4da8fc7f64d3bded9f9d26c921fee01ebe95'
DIMS=['A_U','A_D','B_U','B_D'];AM=['AO','A1','AT'];BM=['BO','B05','B1'];BASE='R1122';ALT='R1111'
PARENT_ACTION={'AO':'H03','A1':'R121','AT':'H00','BO':'H03','B05':'W0022','B1':'W0122'}
LABEL={'AO':'预定次日开盘','A1':'涨1%触发否则14:50','AT':'固定14:50','BO':'预定次日开盘','B05':'低开0.5%否则跌0.5%/涨2%/11:00','B1':'低开0.5%否则跌1%/涨2%/11:00'}
def save(name,data):
    p=R/name;p.parent.mkdir(parents=True,exist_ok=True);f=data if isinstance(data,pd.DataFrame) else pd.DataFrame(data);f.to_csv(p,index=False);return f
def js(name,data):(R/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str))
def rid(vals):return 'R'+''.join(str(int(v)) for v in vals)
def registry():
    out=[]
    for v in itertools.product(range(3),repeat=4):
        aa=v[0]!=v[1];bb=v[2]!=v[3];group='both' if aa and bb else 'A_only' if aa else 'B_only' if bb else 'constant'
        out.append(dict(id=rid(v),group=group,**dict(zip(DIMS,v))))
    assert len(out)==81;return out
def freeze():
    if (R/'failure.json').exists():
        (R/'failures').mkdir(exist_ok=True);(R/'failure.json').rename(R/'failures'/('before_'+os.environ['GITHUB_RUN_ID']+'.json'))
    files=json.loads((z.R/'frozen_input_hashes.json').read_text())['files']
    for p,h in files.items():assert b.sha(p)==h,p
    for p in list(z.R.rglob('*'))+list(Path('scripts/research').glob('foxconn*.py')):
        if p.is_file() and 'b23' not in p.name:files[str(p)]=b.sha(p)
    subprocess.run(['git','diff','--exit-code',PARENT,'--',str(z.R),str(q.R),str(y.R),str(x.R),str(b.R),str(b.b17.R),str(b.b16.R),str(b.P)],check=True)
    js('registry.json',registry());save('registry.csv',registry());js('frozen_input_hashes.json',dict(parent=PARENT,files=files,registry_sha256=b.sha(R/'registry.json'),protocol_sha256=b.sha(R/'PROTOCOL.md'),code={str(p):b.sha(p) for p in Path('scripts/research').glob('foxconn_b23*.py')}))
def state_one(g,cref):
    one=g[g.clock.eq('14:50')];p50=float(one.close.iloc[0]) if len(one)==1 else np.nan
    reason='missing_P50' if len(one)==0 else 'duplicate_P50' if len(one)>1 else 'invalid_P50' if not np.isfinite(p50) or p50<=0 else 'invalid_Cref' if not np.isfinite(cref) or cref<=0 else 'ok'
    state=('U' if Decimal(str(p50))>=Decimal(str(cref)) else 'D') if reason=='ok' else 'X'
    return dict(p50=p50,cref=cref,state=state,reason=reason)
def states(d,m):
    days={day:g for day,g in m.groupby('date')};empty=m.iloc[:0]
    return pd.DataFrame([dict(date=r.date,**state_one(days.get(r.date,empty),r.preclose)) for r in d.itertuples()],index=d.index)
def choose(rule,st,family):
    selected=pd.Series('',index=family.index,dtype=object);fallback=pd.Series(False,index=family.index);reason=pd.Series('no_original_signal',index=family.index)
    for fam,acts,default in [('A',AM,'A1'),('B',BM,'B1')]:
        mask=family.eq(fam);u=acts[rule[fam+'_U']];dd=acts[rule[fam+'_D']]
        for state,action in [('U',u),('D',dd)]:
            ix=mask&st.state.eq(state);selected.loc[ix]=action;reason.loc[ix]='known_state'
        ix=mask&st.state.eq('X');selected.loc[ix]=u if u==dd else default;fallback.loc[ix]=u!=dd;reason.loc[ix]='unknown_common_action' if u==dd else 'unknown_fallback'
    return selected,fallback,reason
def label(rule):return '；'.join(k.replace('_U','未跌').replace('_D','已跌')+'：'+LABEL[(AM if k[0]=='A' else BM)[rule[k]]] for k in DIMS)
def trade(key,bp=5):
    t=pd.read_csv(R/f'trades/{key}_{bp}.csv')
    for k in ['entry','exit']:t[k]=pd.to_datetime(t[k])
    return t
def load():
    d,f,masks,specs,oldpaths,schedule=y.load();paths={k:oldpaths[v].copy() for k,v in PARENT_ACTION.items()};sp={k:specs[v] for k,v in PARENT_ACTION.items()};return d,masks,paths,sp,schedule
def fullbridge(d,new,old,nrow,orow):
    v=q.bridge(new,old,d);v['terminal_reserve']=orow.terminal_tax_reserve-nrow.terminal_tax_reserve;v['net_change']=nrow.increment-orow.increment
    assert abs(v['net_change']-sum(v[k] for k in ['buy_price_and_fee','fifo_tax','missed_dividend','participation','pending_mark','terminal_reserve']))<1e-5
    return v
def run():
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in {**frozen['files'],**frozen['code']}.items():assert b.sha(p)==h,p
    assert b.sha(R/'registry.json')==frozen['registry_sha256'];reg=registry();d,masks,paths,sp,schedule=load();m=q.load_minutes();st=states(d,m);family,category=z.origins(masks)
    save('states.csv',st.assign(family=family,category=category));original=family.ne('')&d.date.ge('2020-01-01');assert not st.loc[original,'state'].eq('X').any()
    save('state_counts.csv',st[original].assign(family=family).groupby(['family','state']).size().rename('signals').reset_index())
    js('action_sources.json',{k:dict(parent_rule=v,source_path=str(x.R/f'paths/{sp[k]["path"]}.csv'),sha256=b.sha(x.R/f'paths/{sp[k]["path"]}.csv'),spec=sp[k]) for k,v in PARENT_ACTION.items()})
    plans={};needs={};aliases=[];seen={}
    for rule in reg:
        key=rule['id'];selected,fallback,reason=choose(rule,st,family);p=paths['A1'].copy()
        for action,pp in paths.items():
            ix=p.index[selected.reindex(p.index).eq(action)];p.loc[ix,:]=pp.loc[ix,:]
        _,need,_=x.plan(d,family.ne(''),p);t,_,part=x.plan(d,family.ne(''),p,capacity=3)
        t['selected_rule']=t.entry_i.map(selected);t['family']=t.entry_i.map(family);t['state']=t.entry_i.map(st.state);t['category']=t.entry_i.map(category);plans[key]=t;needs[key]=need
        save(f'decisions/{key}.csv',st.assign(family=family,category=category,selected_rule=selected,fallback=fallback,choice_reason=reason));save(f'participation/{key}.csv',part)
        sig=hashlib.sha256(p.loc[p.index[family.reindex(p.index).ne('')]].to_csv(index=False).encode()).hexdigest();aliases.append(dict(id=key,canonical=seen.setdefault(sig,key),decision_path_sha256=sig,reused=False))
    save('path_aliases.csv',aliases);js('pre_account_validation.json',dict(registered=81,groups=pd.Series([r['group'] for r in reg]).value_counts().to_dict(),unique_paths=len(seen),new_accounts=243,reused_accounts=0))
    rows=[];(R/'inherited_account_runtime.py.txt').write_text(x.source)
    for rule in reg:
        for bp in [5,11,20]:
            key=rule['id'];a,o,t,ff,met=x.account(d,plans[key],3000,bp/10000,schedule);x.audit(d,a,o,t,met);done=t[t.exit_i.notna()];stat=b.stats(done.cash_increment,done.net_pct)
            rows.append(dict(**rule,bp=bp,rule=label(rule),**met,**{'trade_'+k:v for k,v in stat.items()},average_profit=done.loc[done.cash_increment.gt(0),'cash_increment'].mean(),average_loss=done.loc[done.cash_increment.lt(0),'cash_increment'].mean(),minimum_old_shares_unconstrained=needs[key],max_buy_cash=ff.buy_cost.max(),max_single_deposit=ff.deposit.max(),max_wait_calendar_days=(pd.to_datetime(done.exit)-pd.to_datetime(done.entry)).dt.days.max(),inventory_blocked=int(pd.read_csv(R/f'participation/{key}.csv').reason.eq('inventory_participation').sum())))
            for folder,data,ext in [('accounts',a,'.csv.gz'),('orders',o,'.csv.gz'),('trades',t,'.csv'),('funds',ff,'.csv.gz')]:save(f'{folder}/{key}_{bp}'+ext,data)
            print('ACCOUNT',key,bp,met['increment'],met['completed'],flush=True)
    s=save('account_summary.csv',rows);parent=pd.read_csv(z.R/'comparison.csv');aligned=[]
    for key,old in [(BASE,'T1_ALL'),(ALT,'T05_ALL')]:
        for bp in [5,11,20]:
            a=s[s.id.eq(key)&s.bp.eq(bp)].iloc[0];c=parent[parent.id.eq(old)&parent.bp.eq(bp)].iloc[0]
            for col in ['increment','completed','trade_wins','trade_win','trade_worst','relative_mdd','terminal_tax_reserve','deposits']:assert abs(a[col]-c[col])<1e-5
            aligned.append(dict(id=key,parent=old,bp=bp,status='PASS'))
    save('parent_baseline_alignment.csv',aligned);analyze(d,s,reg);mechanisms(d,st,family,paths);fine(d,st,family,sp)
    for p,h in {**frozen['files'],**frozen['code']}.items():assert b.sha(p)==h,p
    js('calculation_validation.json',dict(status='PASS',accounts=243,parent_alignments=6,parent_files=len(frozen['files']),original_signals=int(original.sum()),unknown_original_states=int(st.loc[original,'state'].eq('X').sum()),data_cutoff=str(d.date.max().date()),new_accounts=243,reused=0))
    excluded=['manifest.json','calculation.log','verification.log','failure.json','verification_manifest.json','independent_accounts_verified.csv','independent_validation.json','independent_verifier_runtime.py.txt','REVIEW_DATA.md','test_evidence.json']
    js('manifest.json',dict(files={str(p):b.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in excluded}))
def analyze(d,s,reg):
    by={(r.id,r.bp):r for r in s.itertuples()};tr={(r.id,r.bp):trade(r.id,r.bp) for r in s.itertuples()};best={}
    for bp in [5,11,20]:best[bp]=s[s.bp.eq(bp)&s.group.eq('constant')].sort_values(['increment','id'],ascending=[False,True]).iloc[0].id
    for base in [BASE,ALT]:s['delta_'+base]=s.apply(lambda r:r.increment-by[base,r.bp].increment,axis=1)
    s['best_constant']=s.bp.map(best);s['delta_best_constant']=s.apply(lambda r:r.increment-by[best[r.bp],r.bp].increment,axis=1);save('comparison.csv',s);js('best_constant.json',best)
    period=[];annual=[];equity=[];groups=[];attr=[];details=[];mirrors=[]
    for row in s.itertuples():
        t=tr[row.id,row.bp];done=t[t.exit_i.notna()]
        for name,sel in [('2020-2023',done.entry.lt('2024-01-01'))]+[(str(yr),done.entry.dt.year.eq(yr)) for yr in range(2024,2027)]:
            g=done[sel];period.append(dict(id=row.id,bp=row.bp,period=name,**b.stats(g.cash_increment,g.net_pct)))
            if row.bp==5 and len(g) and g.cash_increment.sum()<0:
                buy=1000*g.sell_ref*1.0005;sell=1000*g.buy_ref*.9995;cash=sell-buy-b.old.fee(buy,g.entry,False)-b.old.fee(sell,g.exit,True);mirrors.append(dict(id=row.id,period=name,n=len(g),normal_cash=g.cash_increment.sum(),reverse_price_cost_cash=cash.sum(),reverse_mean_pct=(100*cash/(1000*g.sell_ref)).mean(),dividend_entitlement=g.missed_dividend.sum(),status='independent reverse costs; reverse FIFO and entitlement account unverified'))
        for yr in range(2020,2027):
            g=done[done.entry.dt.year.eq(yr)];annual.append(dict(id=row.id,bp=row.bp,year=yr,**b.stats(g.cash_increment,g.net_pct)))
        a=pd.read_csv(R/f'accounts/{row.id}_{row.bp}.csv.gz',parse_dates=['date']);prior=0.
        for yr,g in a.groupby(a.date.dt.year):
            end=g.relative.iloc[-1];equity.append(dict(id=row.id,bp=row.bp,year=yr,equity_change=end-prior,year_end_relative=end,tax_reserve=g.tax_reserve.iloc[-1],missing=3000-g.shares.iloc[-1]));prior=end
        for fam,state in itertools.product(['A','B'],['U','D','X']):
            g=done[done.family.eq(fam)&done.state.eq(state)];groups.append(dict(id=row.id,bp=row.bp,family=fam,state=state,**b.stats(g.cash_increment,g.net_pct)))
        for refkey in list(dict.fromkeys([BASE,ALT,best[row.bp]])):
            ref=tr[refkey,row.bp];v=fullbridge(d,t,ref,row,by[refkey,row.bp]);attr.append(dict(id=row.id,bp=row.bp,baseline=refkey,**v))
            if row.bp==5:
                aa=t.set_index('entry_i');bb=ref.set_index('entry_i')
                for i in aa.index.union(bb.index):
                    nn=aa.loc[i] if i in aa.index else None;oo=bb.loc[i] if i in bb.index else None
                    details.append(dict(id=row.id,baseline=refkey,entry=d.date.iloc[i],entry_i=i,family=nn.family if nn is not None else oo.family,state=nn.state if nn is not None else oo.state,status='retained' if nn is not None and oo is not None else 'added' if nn is not None else 'removed',new_rule=nn.selected_rule if nn is not None else '',old_rule=oo.selected_rule if oo is not None else '',new_clock=nn.buy_clock if nn is not None else '',old_clock=oo.buy_clock if oo is not None else '',new_price=nn.buy_ref if nn is not None else np.nan,old_price=oo.buy_ref if oo is not None else np.nan,new_exit=nn.exit if nn is not None else None,old_exit=oo.exit if oo is not None else None,new_net=nn.cash_increment if nn is not None else 0.,old_net=oo.cash_increment if oo is not None else 0.,change=(nn.cash_increment if nn is not None else 0.)-(oo.cash_increment if oo is not None else 0.)))
    for name,data in [('periods.csv',period),('yearly_trades.csv',annual),('annual_equity_changes.csv',equity),('state_account_groups.csv',groups),('attribution.csv',attr),('attribution_trades.csv',details),('opposite_direction_regions.csv',mirrors)]:save(name,data)
    edges=[];corners=[]
    for rule in reg:
        vals=[rule[k] for k in DIMS]
        for j,dim in enumerate(DIMS):
            for value in range(3):
                if value==vals[j]:continue
                vv=vals.copy();vv[j]=value;dest=rid(vv)
                for bp in [5,11,20]:edges.append(dict(from_id=rule['id'],to_id=dest,dimension=dim,bp=bp,**fullbridge(d,tr[dest,bp],tr[rule['id'],bp],by[dest,bp],by[rule['id'],bp])))
        for aa,bb in itertools.product(sorted(set(vals[:2])),sorted(set(vals[2:]))):
            constant=rid([aa,aa,bb,bb]);aonly=rid(vals[:2]+[bb,bb]);bonly=rid([aa,aa]+vals[2:])
            for bp in [5,11,20]:
                f=lambda key:by[key,bp].increment
                corners.append(dict(id=rule['id'],bp=bp,constant=constant,a_only=aonly,b_only=bonly,constant_net=f(constant),a_only_net=f(aonly),b_only_net=f(bonly),full_net=f(rule['id']),joint_delta=f(rule['id'])-f(constant),interaction=f(rule['id'])-f(aonly)-f(bonly)+f(constant)))
    save('single_position_edges.csv',edges);save('constant_family_interactions.csv',corners)
    leaders=[]
    for bp in [5,11,20]:
        for objective,col in [('profit','increment'),('win','trade_win'),('small_loss','trade_worst')]:
            pool=s[s.bp.eq(bp)];pool=pool if objective=='profit' else pool[pool.completed.ge(40)]
            cols=[col]+(['increment'] if col!='increment' else [])+['id'];pick=pool.sort_values(cols,ascending=[False]*(len(cols)-1)+[True]).head(3)
            for rank,r in enumerate(pick.itertuples(),1):leaders.append(dict(bp=bp,objective=objective,rank=rank,id=r.id,n=r.completed,win=r.trade_win,increment=r.increment,delta_best_constant=r.delta_best_constant))
    save('leaders.csv',leaders);top=set(a['id'] for a in leaders)|{BASE,ALT}|set(best.values());js('focus.json',sorted(top));det=pd.DataFrame(details);tails=[];keydates=[]
    for key in sorted(top):
        for ref in list(dict.fromkeys([BASE,ALT,best[5]])):
            dd=det[det.id.eq(key)&det.baseline.eq(ref)];v=dd.change.sort_values(ascending=False);net=by[key,5].increment-by[ref,5].increment
            tails.append(dict(id=key,baseline=ref,delta=net,top1=v.head(1).sum(),top3=v.head(3).sum(),top5=v.head(5).sum(),without1=net-v.head(1).sum(),without3=net-v.head(3).sum(),without5=net-v.head(5).sum()))
            for side,g in [('positive',dd[dd.change.gt(.00001)].sort_values('change',ascending=False)),('negative',dd[dd.change.lt(-.00001)].sort_values('change'))]:keydates.extend(g.head(8).assign(side=side).to_dict('records'))
    save('concentration.csv',tails);save('key_gain_loss_dates.csv',keydates)
def mechanisms(d,st,family,paths):
    rows=[];pairs=[];summaries=[];ix=d.index[family.ne('')&d.date.ge('2020-01-01')&(d.index<len(d)-1)]
    for fam,acts in [('A',AM),('B',BM)]:
        sel=ix[family.loc[ix].eq(fam)]
        for bp in [5,11,20]:
            costs={key:b.opportunity(d,paths[key].loc[sel],bp) for key in acts}
            for key in acts:
                for i,r in costs[key].iterrows():rows.append(dict(family=fam,state=st.state.iloc[i],action=key,bp=bp,entry=r.entry,entry_i=i,exit=r.exit,clock=r.buy_clock,price=r.buy_ref,trigger=r.trigger,sale_allowed=r.sale_allowed,cash_price_fees_dividend=r.cash,net_pct=r.net,missing=r.missing_windows,delayed=r.delayed))
            for aa,bb in itertools.permutations(acts,2):
                for i in sel:
                    a=costs[aa].loc[i];c=costs[bb].loc[i];pairs.append(dict(family=fam,state=st.state.iloc[i],bp=bp,entry=d.date.iloc[i],entry_i=i,from_action=aa,to_action=bb,old_exit=a.exit,new_exit=c.exit,old_clock=a.buy_clock,new_clock=c.buy_clock,old_price=a.buy_ref,new_price=c.buy_ref,old_cash=a.cash,new_cash=c.cash,change=c.cash-a.cash,loss_to_win=bool(a.cash<=0<c.cash),win_to_loss=bool(c.cash<=0<a.cash),sale_allowed=bool(a.sale_allowed)))
    rr=save('state_action_price_costs.csv',rows);pp=save('state_action_pairs.csv',pairs)
    for keys,g in rr[rr.sale_allowed].groupby(['family','state','action','bp']):summaries.append(dict(zip(['family','state','action','bp'],keys),**b.stats(g.cash_price_fees_dividend,g.net_pct)))
    save('state_action_summary.csv',summaries);save('state_pair_summary.csv',pp[pp.sale_allowed].groupby(['family','state','from_action','to_action','bp']).agg(n=('entry','size'),change=('change','sum'),loss_to_win=('loss_to_win','sum'),win_to_loss=('win_to_loss','sum')).reset_index())
def fine(d,st,family,sp):
    raw=pd.read_csv(b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);raw['clock']=raw.datetime.dt.strftime('%H:%M');ds=d.set_index('date');days={};state_days={};expected=[b.minutes_after(start,k) for start in x.STARTS for k in range(1,6)]
    for day,g in raw.groupby('date'):
        g=g.sort_values('clock').copy()
        if day not in ds.index or list(g.clock)!=expected:continue
        r=ds.loc[day]
        if max(abs(g.open.iloc[0]-r.open),abs(g.close.iloc[-1]-r.close),abs(g.high.max()-r.high),abs(g.low.min()-r.low))>=.011:continue
        if not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))&(g.volume>=0)).all():continue
        g['block']=np.arange(240)//5;ag=g.groupby('block').agg(open=('open','first'),close=('close','last'),clock=('clock','last'))
        days[day]=ag.set_index('clock').to_dict('index');state_days[day]=ag.assign(close=ag.close.round(2))
    states_rows=[];actual=set(trade(BASE).entry_i);signal_ix=d.index[family.ne('')&d.date.ge('2020-01-01')]
    for i in signal_ix:
        date=d.date.iloc[i];available=date in state_days;v=state_one(state_days[date],d.preclose.iloc[i]) if available else None
        states_rows.append(dict(entry=date,entry_i=i,family=family.iloc[i],baseline_traded=i in actual,covered=available,old_state=st.state.iloc[i],fine_state=v['state'] if v else None,old_p50=st.p50.iloc[i],fine_p50=v['p50'] if v else np.nan,flip=bool(available and st.state.iloc[i]!=v['state'])))
    ss=save('fine_sell_states.csv',states_rows).set_index('entry_i');top=json.loads((R/'focus.json').read_text());replay=[]
    for key in top:
        for tr in trade(key).itertuples():
            rr=d.iloc[int(tr.entry_i)+1];spec=sp[tr.selected_rule];covered=rr.date in days;planned=spec['kind']=='open';fill=reason=None
            if covered:fill,issues,reason=x.first_buy(tr.sell_ref,rr,days[rr.date],spec)
            supported=bool(covered and not planned and fill is not None and tr.exit==rr.date)
            replay.append(dict(id=key,entry=tr.entry,entry_i=tr.entry_i,action=tr.selected_rule,family=tr.family,state=tr.state,sell_state_covered=bool(ss.loc[tr.entry_i,'covered']),sell_state_flip=bool(ss.loc[tr.entry_i,'flip']),next_day_covered=covered,planned_open_proxy=planned,path_replayed=supported,old_exit=tr.exit,old_clock=tr.buy_clock,old_price=tr.buy_ref,fine_clock=fill[0] if fill else None,fine_price=fill[1] if fill else np.nan,old_trigger=tr.trigger,fine_trigger=reason,clock_match=bool(supported and fill[0]==tr.buy_clock),trigger_match=bool(supported and reason==tr.trigger),price_difference=fill[1]-tr.buy_ref if supported else np.nan,auction_proxy_matches_daily=bool(planned and tr.exit==rr.date and tr.buy_clock=='09:25' and abs(tr.buy_ref-rr.open)<1e-8),first_minute_open_difference=(days[rr.date]['09:35']['open']-tr.buy_ref) if covered and planned else np.nan))
    ff=save('fine_buy_paths.csv',replay);idx=ff.set_index(['id','entry_i']);det=pd.read_csv(R/'attribution_trades.csv');joined=[]
    for r in det[det.id.isin(top)].itertuples():
        nn=idx.loc[(r.id,r.entry_i)] if (r.id,r.entry_i) in idx.index else None;oo=idx.loc[(r.baseline,r.entry_i)] if (r.baseline,r.entry_i) in idx.index else None
        changed=r.new_clock!=r.old_clock or abs(r.new_price-r.old_price)>1e-8 or r.new_exit!=r.old_exit
        joined.append(dict(id=r.id,baseline=r.baseline,entry=r.entry,entry_i=r.entry_i,family=r.family,state=r.state,change=r.change,changed_fill=changed,sell_state_covered=bool(ss.loc[r.entry_i,'covered']),sell_state_flip=bool(ss.loc[r.entry_i,'flip']),new_path_supported=bool(nn is not None and nn.path_replayed),old_path_supported=bool(oo is not None and oo.path_replayed),both_paths_supported=bool(nn is not None and oo is not None and nn.path_replayed and oo.path_replayed),new_open_proxy=bool(nn is not None and nn.planned_open_proxy),old_open_proxy=bool(oo is not None and oo.planned_open_proxy),new_price_difference=nn.price_difference if nn is not None else np.nan,old_price_difference=oo.price_difference if oo is not None else np.nan))
    paired=save('fine_paired_attribution.csv',joined);save('fine_coverage_summary.csv',ff.groupby('id').agg(n=('entry','size'),sell_state_covered=('sell_state_covered','sum'),sell_state_flips=('sell_state_flip','sum'),next_day_covered=('next_day_covered','sum'),intraday_paths_replayed=('path_replayed','sum'),open_proxy_cases=('planned_open_proxy','sum'),clock_matches=('clock_match','sum'),trigger_matches=('trigger_match','sum')).reset_index())
    save('fine_covered_uncovered_contributions.csv',paired.groupby(['id','baseline','changed_fill','sell_state_covered','both_paths_supported']).agg(n=('entry','size'),change=('change','sum')).reset_index())
    js('fine_quality.json',dict(qualified_days=len(days),baseline_sell_days=int(ss[ss.baseline_traded].covered.sum()),signal_days=int(ss.covered.sum()),sell_state_flips=int(ss.flip.sum()),auction='daily open proxy only; not counted as minute-replayed execution',uncovered='unknown',paths='first next-day paths only; delayed recovery not certified by this replay'))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true';R.mkdir(parents=True,exist_ok=True)
    try:freeze() if sys.argv[1]=='freeze' else run()
    except Exception:js('failure.json',dict(run=os.environ.get('GITHUB_RUN_ID'),traceback=traceback.format_exc()));raise
