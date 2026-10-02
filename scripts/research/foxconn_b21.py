"""B21 finite exit optimization; all market computation runs on GitHub."""
import os,sys,json,hashlib,subprocess,traceback,zipfile,itertools
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_b20 as y
x=y.x;b=y.b
R=Path('research/foxconn_t0_20261002_b21')
PARENT='ad66e34c1035a7685f7b526a688f9ef36d4afd73'
BASE='Q1010';ALT='Q1000'
def save(name,data):
    p=R/name;p.parent.mkdir(parents=True,exist_ok=True)
    f=data if isinstance(data,pd.DataFrame) else pd.DataFrame(data);f.to_csv(p,index=False);return f
def js(name,obj):(R/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str))
def registry():return json.loads((R/'registry.json').read_text())
def specs():
    out={f'A{k}':dict(path=f'A{k}',kind='adaptive',gap=None,tp=None,stop=k/100 if k else None,deadline='14:50') for k in [1,2,0]}
    for g,t,d in itertools.product(range(2),repeat=3):
        key=f'B{g}{t}{d}';out[key]=dict(path=key,kind='adaptive',gap=None if g else .005,tp=.01 if t else .005,stop=.02,deadline='14:50' if d else '11:00')
    return out
def freeze():
    if (R/'failure.json').exists():
        (R/'failures').mkdir(exist_ok=True);(R/'failure.json').rename(R/'failures'/('before_'+os.environ['GITHUB_RUN_ID']+'.json'))
    files=json.loads((y.R/'frozen_input_hashes.json').read_text())['files']
    for p,h in files.items():assert b.sha(p)==h,p
    more=list(y.R.rglob('*'))+list(Path('scripts/research').glob('foxconn*.py'))
    for p in more:
        if p.is_file() and 'b21' not in p.name:files[str(p)]=b.sha(p)
    subprocess.run(['git','diff','--exit-code',PARENT,'--',str(y.R),str(x.R),str(b.R),str(b.b17.R),str(b.b16.R),str(b.P)],check=True)
    js('frozen_input_hashes.json',dict(parent=PARENT,files=files,registry_sha256=b.sha(R/'registry.json'),code={str(p):b.sha(p) for p in Path('scripts/research').glob('foxconn_b21*.py')}))
def load_minutes():
    with zipfile.ZipFile(b.old.P/'source/601138-full-5min-history.zip') as z:m=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith('601138_5min_all.csv'))))
    m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M')
    return m.sort_values(['date','clock'])
def configure(rule,masks,paths):
    aa=masks['R121'].fillna(False);bb=masks['H01'].fillna(False)
    selected=pd.Series('',index=aa.index,dtype=object);selected.loc[aa]=rule['a'];selected.loc[~aa&bb]=rule['b']
    category=pd.Series(np.select([aa&bb,aa,bb],['overlap','only_A','only_B'],default='neither'),index=aa.index)
    p=paths[rule['a']].copy();ix=p.index[selected.reindex(p.index).eq(rule['b'])];p.loc[ix]=paths[rule['b']].loc[ix]
    return selected.ne(''),p,selected,category
def label(rule):
    if rule['group']!='combo':
        return {'CTRL_OLD':'旧第一类顶部20%且量不放大/14:50；第二类3日累计跌4%且顶部30%/低开0.5%或跌0.5%涨1%10:30；重叠第二类优先','CTRL_OPEN':'新两卖出入口；第一类涨1%或14:50，第二类直接开盘买；重叠第一类优先','CTRL_W0':'仅第二类3日累计跌至少4%且顶部30%；低开0.5%最早09:30，否则跌0.5%或涨2%，11:00截止','CTRL_W1':'仅第二类3日累计跌至少4%且顶部30%；低开0.5%最早09:30，否则跌1%或涨2%，11:00截止'}[rule['id']]
    a='第一类'+(f'涨{rule["stop"]*100:g}%触发/14:50' if rule['stop'] is not None else '固定14:50，不提前上涨买')
    bb='第二类'+('低开0.5%最早09:30买，否则' if rule['gap'] else '低开也继续等，')+f'跌{rule["tp"]*100:g}%或涨2%触发/{rule["deadline"]}'
    return '昨日第一类顶部20%/量不超前20日均量/20日非负，或第二类3日累计跌至少4%/顶部30%，今日收盘卖1000；'+a+'；'+bb+'；重叠第一类优先'
def read_trade(key,bp=5):return pd.read_csv(R/f'trades/{key}_{bp}.csv',parse_dates=['entry','exit'])
def run():
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in frozen['files'].items():assert b.sha(p)==h,p
    assert b.sha(R/'registry.json')==frozen['registry_sha256']
    reg=registry();assert len(reg)==28
    d,f,masks,oldspecs,oldpaths,schedule=y.load();m=load_minutes();sp=specs();paths={};failed=[]
    original=b.first_buy;b.first_buy=x.first_buy
    try:
        for key,spec in sp.items():
            p,a=b.build_paths(d,m,spec);paths[key]=p;failed.append(a);save(f'paths/{key}.csv',p)
    finally:b.first_buy=original
    save('failed_and_missing_attempts.csv',pd.concat(failed,ignore_index=True))
    parentreg={a['id']:a for a in json.loads((y.R/'registry.json').read_text())}
    plans={};needs={};aliases=[];seen={};choices=[];configuration={}
    for rule in reg:
        key=rule['id']
        if rule['group']=='combo':mask,p,selected,category=configure(rule,masks,paths)
        else:mask,p,selected,category=y.combined_paths(parentreg[rule['parent']],masks,oldpaths)
        raw,need,_=x.plan(d,mask,p);t,_,reasons=x.plan(d,mask,p,capacity=3)
        t['selected_rule']=t.entry_i.map(selected);t['category']=t.entry_i.map(category)
        t['family']=np.where(t.selected_rule.str.startswith('A')|t.selected_rule.isin(['H00','R121']),'A','B')
        plans[key]=t;needs[key]=need;configuration[key]=(selected,category)
        identity={k:v for k,v in rule.items() if k not in ['id','group']};sig=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        aliases.append(dict(id=key,canonical=seen.setdefault(sig,key),identity_sha256=sig))
        chosen=pd.DataFrame(dict(date=d.date,selected_rule=selected,category=category));save(f'decisions/{key}.csv',chosen)
        save(f'participation/{key}.csv',reasons)
    save('path_aliases.csv',aliases);js('pre_account_validation.json',dict(registered=28,unique=len(seen),identity_dedup_before_accounts=True))
    rows=[]
    (R/'inherited_account_runtime.py.txt').write_text(x.source)
    for rule in reg:
        key=rule['id']
        for bp in [5,11,20]:
            z,o,t,ff,s=x.account(d,plans[key],3000,bp/10000,schedule);x.audit(d,z,o,t,s)
            done=t[t.exit_i.notna()];st=b.stats(done.cash_increment,done.net_pct)
            rows.append(dict(id=key,group=rule['group'],bp=bp,rule=label(rule),**s,**{'trade_'+k:v for k,v in st.items()},average_profit=done.loc[done.cash_increment.gt(0),'cash_increment'].mean(),average_loss=done.loc[done.cash_increment.lt(0),'cash_increment'].mean(),minimum_old_shares_unconstrained=needs[key],max_buy_cash=ff.buy_cost.max(),max_single_deposit=ff.deposit.max(),max_wait_calendar_days=(done.exit-done.entry).dt.days.max(),inventory_blocked=int(pd.read_csv(R/f'participation/{key}.csv').reason.eq('inventory_participation').sum())))
            for folder,data,ext in [('accounts',z,'.csv.gz'),('orders',o,'.csv.gz'),('trades',t,'.csv'),('funds',ff,'.csv.gz')]:save(f'{folder}/{key}_{bp}'+ext,data)
            print('ACCOUNT',key,bp,s['increment'],s['completed'],flush=True)
    s=save('account_summary.csv',rows);parent=pd.read_csv(y.R/'account_summary.csv');align=[]
    mapping={BASE:'C12A',ALT:'C11A',**{a['id']:a['parent'] for a in reg if a['group']!='combo'}}
    for key,old in mapping.items():
        for bp in [5,11,20]:
            aa=s[s.id.eq(key)&s.bp.eq(bp)].iloc[0];bb=parent[parent.id.eq(old)&parent.bp.eq(bp)].iloc[0]
            for col in ['increment','completed','trade_wins','trade_win','trade_worst','relative_mdd','terminal_tax_reserve','deposits']:assert abs(aa[col]-bb[col])<1e-5,(key,bp,col)
            align.append(dict(id=key,parent_id=old,bp=bp,status='PASS'))
    save('parent_baseline_alignment.csv',align)
    analyze(d,s,reg)
    replay_fine(d,sp|oldspecs)
    for p,h in frozen['files'].items():assert b.sha(p)==h,p
    js('calculation_validation.json',dict(status='PASS',accounts=len(s),parent_alignments=len(align),parent_files=len(frozen['files']),inventory_max=max(needs.values()),data_cutoff=str(d.date.max().date()),new_exit_specs=len(sp)))
    js('manifest.json',dict(files={str(p):b.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['manifest.json','calculation.log','verification.log','failure.json']}))
def bridge(t,ref,d):
    t=t.set_index('entry_i');ref=ref.set_index('entry_i');both=t.index.intersection(ref.index);added=t.index.difference(ref.index);removed=ref.index.difference(t.index)
    mark=lambda tt:sum(v.sale_net-1000*d.close.iloc[-1]-v.missed_dividend for v in tt[tt.exit_i.isna()].itertuples())
    changed=(t.loc[both,'buy_clock']!=ref.loc[both,'buy_clock'])|((t.loc[both,'buy_ref']-ref.loc[both,'buy_ref']).abs()>1e-8)|(t.loc[both,'exit']!=ref.loc[both,'exit'])
    return dict(shared=len(both),added=len(added),removed=len(removed),changed_fills=int(changed.sum()),buy_price_and_fee=float((ref.loc[both,'buy_cost']-t.loc[both,'buy_cost']).sum()),fifo_tax=float((ref.loc[both,'dividend_tax']-t.loc[both,'dividend_tax']).sum()),missed_dividend=float((ref.loc[both,'missed_dividend']-t.loc[both,'missed_dividend']).sum()),participation=float(t.loc[added,'cash_increment'].sum()-ref.loc[removed,'cash_increment'].sum()),pending_mark=mark(t)-mark(ref),loss_to_win=int(((t.loc[both,'cash_increment']>0)&(ref.loc[both,'cash_increment']<=0)).sum()),win_to_loss=int(((t.loc[both,'cash_increment']<=0)&(ref.loc[both,'cash_increment']>0)).sum()))
def analyze(d,s,reg):
    s=s.copy()
    for baseline in [BASE,ALT]:s['delta_'+baseline]=s.apply(lambda row:row.increment-s[s.id.eq(baseline)&s.bp.eq(row.bp)].iloc[0].increment,axis=1)
    save('comparison.csv',s);periods=[];annual=[];equity=[];groups=[];attr=[];details=[];edges=[];interactions=[]
    by={(r.id,r.bp):r for r in s.itertuples()};trades={(r.id,r.bp):read_trade(r.id,r.bp) for r in s.itertuples()}
    for row in s.itertuples():
        t=trades[row.id,row.bp];done=t[t.exit_i.notna()]
        for period,sel in [('2020-2023',done.entry.lt('2024-01-01'))]+[(str(yr),done.entry.dt.year.eq(yr)) for yr in range(2024,2027)]:
            g=done[sel];periods.append(dict(id=row.id,bp=row.bp,period=period,**b.stats(g.cash_increment,g.net_pct)))
        for yr in range(2020,2027):
            g=done[done.entry.dt.year.eq(yr)];annual.append(dict(id=row.id,bp=row.bp,year=yr,**b.stats(g.cash_increment,g.net_pct)))
        z=pd.read_csv(R/f'accounts/{row.id}_{row.bp}.csv.gz',parse_dates=['date']);prior=0.
        for yr,g in z.groupby(z.date.dt.year):
            end=g.relative.iloc[-1];equity.append(dict(id=row.id,bp=row.bp,year=yr,equity_change=end-prior,year_end_relative=end,tax_reserve=g.tax_reserve.iloc[-1],missing=3000-g.shares.iloc[-1]));prior=end
        for family in ['A','B']:
            g=done[done.family.eq(family)];groups.append(dict(id=row.id,bp=row.bp,family=family,**b.stats(g.cash_increment,g.net_pct)))
        for baseline in [BASE,ALT]:
            ref=trades[baseline,row.bp];a=bridge(t,ref,d);a['terminal_reserve']=by[baseline,row.bp].terminal_tax_reserve-row.terminal_tax_reserve
            delta=row.increment-by[baseline,row.bp].increment
            assert abs(delta-sum(a[k] for k in ['buy_price_and_fee','fifo_tax','missed_dividend','participation','pending_mark','terminal_reserve']))<1e-5
            attr.append(dict(id=row.id,bp=row.bp,baseline=baseline,net_change=delta,**a))
            if row.bp==5:
                tt=t.set_index('entry_i');rr=ref.set_index('entry_i')
                for i in tt.index.union(rr.index):
                    nn=tt.loc[i] if i in tt.index else None;oo=rr.loc[i] if i in rr.index else None
                    details.append(dict(id=row.id,baseline=baseline,entry=d.date.iloc[i],entry_i=i,family=nn.family if nn is not None else oo.family,selected_rule=nn.selected_rule if nn is not None else '',old_rule=oo.selected_rule if oo is not None else '',new_trigger=nn.trigger if nn is not None else '',old_trigger=oo.trigger if oo is not None else '',new_exit=nn.exit if nn is not None else None,old_exit=oo.exit if oo is not None else None,new_clock=nn.buy_clock if nn is not None else '',old_clock=oo.buy_clock if oo is not None else '',new_price=nn.buy_ref if nn is not None else np.nan,old_price=oo.buy_ref if oo is not None else np.nan,new_net=nn.cash_increment if nn is not None else 0.,old_net=oo.cash_increment if oo is not None else 0.,change=(nn.cash_increment if nn is not None else 0.)-(oo.cash_increment if oo is not None else 0.),loss_to_win=bool(nn is not None and oo is not None and nn.cash_increment>0 and oo.cash_increment<=0),win_to_loss=bool(nn is not None and oo is not None and nn.cash_increment<=0 and oo.cash_increment>0)))
    grid=[a for a in reg if a['group']=='combo']
    for aa in grid:
        for bb in grid:
            dims=[k for k in ['stop','gap','tp','deadline'] if aa[k]!=bb[k]]
            if len(dims)!=1:continue
            for bp in [5,11,20]:
                bridge_data=bridge(trades[bb['id'],bp],trades[aa['id'],bp],d)
                edges.append(dict(from_id=aa['id'],to_id=bb['id'],dimension=dims[0],bp=bp,net_change=by[bb['id'],bp].increment-by[aa['id'],bp].increment,**bridge_data))
    # Interactions across two changed dimensions are grid corner differences, not new candidates.
    for rule in grid:
        for baseline in [BASE,ALT]:
            br=next(a for a in grid if a['id']==baseline)
            aonly=next(a for a in grid if a['a']==rule['a'] and a['b']==br['b'])
            bonly=next(a for a in grid if a['a']==br['a'] and a['b']==rule['b'])
            for bp in [5,11,20]:interactions.append(dict(id=rule['id'],baseline=baseline,bp=bp,a_only_delta=by[aonly['id'],bp].increment-by[baseline,bp].increment,b_only_delta=by[bonly['id'],bp].increment-by[baseline,bp].increment,joint_delta=by[rule['id'],bp].increment-by[baseline,bp].increment,interaction=by[rule['id'],bp].increment-by[aonly['id'],bp].increment-by[bonly['id'],bp].increment+by[baseline,bp].increment))
    for name,data in [('periods.csv',periods),('yearly_trades.csv',annual),('annual_equity_changes.csv',equity),('family_groups.csv',groups),('attribution.csv',attr),('attribution_trades.csv',details),('single_action_edges.csv',edges),('family_interactions.csv',interactions)]:save(name,data)
    leaders=[]
    for bp in [5,11,20]:
        for scope in ['combo','all']:
            pool=s[s.bp.eq(bp)&(s.group.eq('combo') if scope=='combo' else True)]
            for objective,col in [('profit','increment'),('win','trade_win')]:
                eligible=pool if objective=='profit' else pool[pool.completed.ge(40)]
                pick=eligible.sort_values([col]+(['increment'] if col!='increment' else [])+['id'],ascending=[False]+([False] if col!='increment' else [])+[True]).head(3)
                for rank,r in enumerate(pick.itertuples(),1):leaders.append(dict(bp=bp,scope=scope,objective=objective,rank=rank,id=r.id,net=r.increment,win=r.trade_win))
    save('leaders.csv',leaders)
    top=set(a['id'] for a in leaders);det=pd.DataFrame(details);tails=[];keys=[]
    for key in sorted(top):
        for baseline in [BASE,ALT]:
            dd=det[det.id.eq(key)&det.baseline.eq(baseline)];vals=dd.change.sort_values(ascending=False);net=by[key,5].increment-by[baseline,5].increment
            tails.append(dict(id=key,baseline=baseline,delta=net,top1=vals.head(1).sum(),top3=vals.head(3).sum(),top5=vals.head(5).sum(),without1=net-vals.head(1).sum(),without3=net-vals.head(3).sum(),without5=net-vals.head(5).sum()))
            for sign,g in [('positive',dd[dd.change.gt(.00001)].sort_values('change',ascending=False)),('negative',dd[dd.change.lt(-.00001)].sort_values('change'))]:
                keys.extend(g.head(8).assign(sign=sign).to_dict('records'))
    save('concentration.csv',tails);save('key_gain_loss_dates.csv',keys)
    mirrors=[]
    for key in [a['id'] for a in reg]:
        t=trades[key,5]
        for name,sel in [('2020-2023',t.entry.lt('2024-01-01'))]+[(str(yr),t.entry.dt.year.eq(yr)) for yr in range(2024,2027)]:
            g=t[sel&t.exit_i.notna()]
            if not len(g) or g.cash_increment.sum()>=0:continue
            buy=1000*g.sell_ref*1.0005;sell=1000*g.buy_ref*.9995;cash=sell-buy-b.old.fee(buy,g.entry,False)-b.old.fee(sell,g.exit,True)
            mirrors.append(dict(id=key,period=name,n=len(g),normal_episode_cash=g.cash_increment.sum(),reverse_price_cost_cash=cash.sum(),reverse_price_cost_pct=(100*cash/(1000*g.sell_ref)).mean(),dividend_entitlement=g.missed_dividend.sum(),status='same dates/clocks independently costed; reverse FIFO/dividend account unverified'))
    save('opposite_direction_regions.csv',mirrors)
def replay_fine(d,all_specs):
    raw=pd.read_csv(b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);raw['clock']=raw.datetime.dt.strftime('%H:%M');ds=d.set_index('date');days={}
    expected=[b.minutes_after(start,k) for start in x.STARTS for k in range(1,6)]
    for day,g in raw.groupby('date'):
        g=g.sort_values('clock').copy()
        if day not in ds.index or list(g.clock)!=expected:continue
        rr=ds.loc[day]
        if max(abs(g.open.iloc[0]-rr.open),abs(g.close.iloc[-1]-rr.close),abs(g.high.max()-rr.high),abs(g.low.min()-rr.low))>=.011:continue
        if not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))&(g.volume>=0)).all():continue
        g['block']=np.arange(240)//5;days[day]=g.groupby('block').agg(open=('open','first'),close=('close','last'),clock=('clock','last')).set_index('clock').to_dict('index')
    top=set(pd.read_csv(R/'leaders.csv').id)|{BASE,ALT};records=[]
    for key in sorted(top):
        for tr in read_trade(key).itertuples():
            rr=d.iloc[int(tr.entry_i)+1];spec=all_specs[tr.selected_rule]
            available=rr.date in days;fill=None;reason=None
            if available:fill,issues,reason=x.first_buy(tr.sell_ref,rr,days[rr.date],spec)
            supported=bool(available and fill is not None and tr.exit==rr.date)
            records.append(dict(id=key,entry=tr.entry,entry_i=tr.entry_i,family=tr.family,selected_rule=tr.selected_rule,trigger=tr.trigger,old_clock=tr.buy_clock,old_price=tr.buy_ref,day_available=available,path_replayed=supported,new_clock=fill[0] if fill else None,new_price=fill[1] if fill else np.nan,new_trigger=reason,clock_match=bool(supported and fill[0]==tr.buy_clock),trigger_match=bool(supported and reason==tr.trigger),price_difference=fill[1]-tr.buy_ref if supported else np.nan))
    replay=save('fine_path_replay.csv',records);details=pd.read_csv(R/'attribution_trades.csv',parse_dates=['entry']);joined=[]
    replay.entry=pd.to_datetime(replay.entry);idx=replay.set_index(['id','entry'])
    for v in details[details.id.isin(top)].itertuples():
        new=idx.loc[(v.id,v.entry)] if (v.id,v.entry) in idx.index else None;old=idx.loc[(v.baseline,v.entry)] if (v.baseline,v.entry) in idx.index else None
        joined.append(dict(id=v.id,baseline=v.baseline,entry=v.entry,family=v.family,change=v.change,new_rule=v.selected_rule,old_rule=v.old_rule,new_trigger=v.new_trigger,old_trigger=v.old_trigger,new_path_supported=bool(new is not None and new.path_replayed),old_path_supported=bool(old is not None and old.path_replayed),both_supported=bool(new is not None and old is not None and new.path_replayed and old.path_replayed),new_price_difference=new.price_difference if new is not None else np.nan,old_price_difference=old.price_difference if old is not None else np.nan))
    save('fine_paired_attribution.csv',joined);js('fine_quality.json',dict(qualified_days=len(days),cadence='five minute completed-close; new and old paths each recalculated',uncovered_status='unknown'))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    R.mkdir(parents=True,exist_ok=True)
    try:
        if sys.argv[1]=='freeze':freeze()
        else:run()
    except Exception:
        js('failure.json',dict(run=os.environ.get('GITHUB_RUN_ID'),traceback=traceback.format_exc()));raise
