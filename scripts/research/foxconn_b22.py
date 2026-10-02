"""B22 fixed entry filters; all market computation is GitHub-only."""
import os,sys,json,hashlib,subprocess,traceback
from pathlib import Path
from fractions import Fraction
import numpy as np
import pandas as pd
import foxconn_b21 as q
y=q.y;x=q.x;b=q.b
R=Path('research/foxconn_t0_20261002_b22')
PARENT='e64b733ad39e828c32034dce6d4f2cf7a8ae7b2a'
PREFIX=[c for c in x.ENDS if c<='14:50']
TARGETS={'T1':'Q1010','T05':'Q1000'}
def save(name,data):
    p=R/name;p.parent.mkdir(parents=True,exist_ok=True)
    z=data if isinstance(data,pd.DataFrame) else pd.DataFrame(data);z.to_csv(p,index=False);return z
def js(name,obj):(R/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str))
def registry():
    out=[]
    for target,parent in TARGETS.items():
        out.append(dict(id=target+'_ALL',group='core',target=target,parent=parent,scope='none',feature='none',side='all'))
        for feature in ['day','position','tail']:
            for scope in ['A','B','AB']:
                for side in ['ge','lt','avail']:
                    out.append(dict(id=f'{target}_{scope}_{feature}_{side}',group='availability' if side=='avail' else 'core',target=target,parent=parent,scope=scope,feature=feature,side=side))
    assert len(out)==56 and len({r['id'] for r in out})==56
    return out
def freeze():
    if (R/'failure.json').exists():
        (R/'failures').mkdir(exist_ok=True);(R/'failure.json').rename(R/'failures'/('before_'+os.environ['GITHUB_RUN_ID']+'.json'))
    files=json.loads((q.R/'frozen_input_hashes.json').read_text())['files']
    for p,h in files.items():assert b.sha(p)==h,p
    for p in list(q.R.rglob('*'))+list(Path('scripts/research').glob('foxconn*.py')):
        if p.is_file() and 'b22' not in p.name:files[str(p)]=b.sha(p)
    subprocess.run(['git','diff','--exit-code',PARENT,'--',str(q.R),str(y.R),str(x.R),str(b.R),str(b.b17.R),str(b.b16.R),str(b.P)],check=True)
    js('registry.json',registry());save('registry.csv',registry())
    js('frozen_input_hashes.json',dict(parent=PARENT,files=files,registry_sha256=b.sha(R/'registry.json'),protocol_sha256=b.sha(R/'PROTOCOL.md'),code={str(p):b.sha(p) for p in Path('scripts/research').glob('foxconn_b22*.py')}))
def feature_day(g,cref):
    g=g[g.clock.le('14:50')].copy();out={}
    def endpoint(clock):
        z=g[g.clock.eq(clock)]
        if len(z)!=1:return np.nan,'missing_'+clock if not len(z) else 'duplicate_'+clock
        p=float(z.close.iloc[0]);return (p,'ok') if np.isfinite(p) and p>0 else (np.nan,'invalid_'+clock)
    p50,r50=endpoint('14:50');p30,r30=endpoint('14:30')
    out.update(p50=p50,p30=p30,cref=cref,prefix_n=len(g),prefix_unique=g.clock.nunique(),h50=np.nan,l50=np.nan)
    out['day_reason']=r50 if r50!='ok' else 'invalid_cref' if not np.isfinite(cref) or cref<=0 else 'ok'
    out['day']=p50/cref-1 if out['day_reason']=='ok' else np.nan
    out['tail_reason']=r50 if r50!='ok' else r30
    out['tail']=p50/p30-1 if out['tail_reason']=='ok' else np.nan
    clocks=list(g.sort_values('clock').clock)
    a=g[['open','high','low','close']].to_numpy(float)
    if clocks!=PREFIX:reason='incomplete_or_duplicate_prefix'
    elif not np.isfinite(a).all() or not (a>0).all():reason='invalid_prefix_price'
    elif not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))).all():reason='invalid_prefix_ohlc'
    else:
        out['h50']=float(g.high.max());out['l50']=float(g.low.min());reason='ok' if out['h50']>out['l50'] else 'flat_range'
    out['position_reason']=reason;out['position']=float((Fraction(str(p50))-Fraction(str(out['l50'])))/(Fraction(str(out['h50']))-Fraction(str(out['l50'])))) if reason=='ok' else np.nan
    for name in ['day','tail','position']:out[name+'_available']=bool(np.isfinite(out[name]))
    out['day_margin']=p50-cref;out['tail_margin']=p50-p30;out['position_margin']=p50-(out['l50']+.7*(out['h50']-out['l50']))
    return out
def features(d,m):
    days={day:g for day,g in m.groupby('date')};empty=m.iloc[:0]
    return pd.DataFrame([dict(date=r.date,**feature_day(days.get(r.date,empty),r.preclose)) for r in d.itertuples()],index=d.index)
def origins(masks):
    aa=masks['R121'].fillna(False);bb=masks['H01'].fillna(False)
    return pd.Series(np.select([aa,bb],['A','B'],default=''),index=aa.index),pd.Series(np.select([aa&bb,aa,bb],['overlap','only_A','only_B'],default='neither'),index=aa.index)
def decide(rule,f,family):
    exists=family.ne('');app=exists&family.isin(['A','B'] if rule['scope']=='AB' else [rule['scope']]);known=pd.Series(True,index=f.index);passed=pd.Series(True,index=f.index)
    if rule['side']!='all':
        v=f[rule['feature']];known=v.notna();threshold=.7 if rule['feature']=='position' else 0.
        passed=known if rule['side']=='avail' else known&(v.ge(threshold) if rule['side']=='ge' else v.lt(threshold))
    allowed=exists&(~app|passed)
    reason=pd.Series(np.select([~exists,app&~known,app&known&~passed],['no_original_signal','feature_unavailable','market_rejected'],default='keep'),index=f.index)
    return allowed,app,known,reason
def label(r):
    state={'day':{'ge':'14:50相对当日昨收参考未下跌','lt':'14:50相对当日昨收参考已下跌'},'position':{'ge':'14:50仍在截至当时区间顶部30%','lt':'14:50不在截至当时区间顶部30%'},'tail':{'ge':'14:30至14:50未下跌','lt':'14:30至14:50下跌'}}
    condition='原样全做' if r['side']=='all' else f'仅要求{r["feature"]}可用' if r['side']=='avail' else state[r['feature']][r['side']]
    scope={'none':'无今日筛选','A':'仅筛第一类','B':'仅筛第二类','AB':'两类都筛'}[r['scope']]
    return f'昨日第一类顶部20%/量不超前20日均量/20日非负，或第二类3日累计跌至少4%/顶部30%；{scope}：{condition}；合格今日收盘卖1000；第一类涨1%/14:50，第二类低开0.5%否则跌{"1%" if r["target"]=="T1" else "0.5%"}/涨2%/11:00；先归第一类再筛，否决不回退'
def trade(key,bp=5):
    t=pd.read_csv(R/f'trades/{key}_{bp}.csv')
    for col in ['entry','exit']:t[col]=pd.to_datetime(t[col])
    return t
def run():
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in frozen['files'].items():assert b.sha(p)==h,p
    assert frozen['registry_sha256']==b.sha(R/'registry.json')
    reg=registry();d,oldf,masks,oldspecs,oldpaths,schedule=y.load();m=q.load_minutes();f=features(d,m);family,category=origins(masks)
    save('features.csv',f);save('original_family.csv',pd.DataFrame(dict(date=d.date,family=family,category=category)))
    assert len(PREFIX)==46 and PREFIX[0]=='09:35' and PREFIX[-1]=='14:50'
    demo_dates=[d.date[d.date.ge('2020-01-01')].iloc[0],d.date.iloc[-1]]
    examples=m[m.date.isin(demo_dates)&m.clock.isin(['09:35','14:30','14:50','14:55'])].copy();examples['interval_start']=examples.clock.map(lambda c:b.minutes_after(c,-5));examples['used_by_P50']=examples.clock.eq('14:50');save('timestamp_examples.csv',examples)
    overlap=[]
    for name in ['day','position','tail']:
        for fam in ['A','B','AB']:
            sel=family.isin(['A','B'] if fam=='AB' else [fam])&d.date.ge('2020-01-01');g=f[sel]
            overlap.append(dict(feature=name,family=fam,original_signals=len(g),available=g[name].notna().sum(),unknown=g[name].isna().sum(),near_one_tick=(g[name+'_margin'].abs()<=.01000001).sum()))
    save('feature_availability.csv',overlap)
    save('unknown_feature_dates.csv',pd.concat([f[f[name].isna()&family.ne('')&d.date.ge('2020-01-01')].assign(feature=name,family=family,reason=f[name+'_reason']) for name in ['day','position','tail']],ignore_index=True))
    common=f.position.notna()&oldf.S2_clv.notna();save('b18_overlap.csv',[dict(feature='position',b18='S2_clv_ge_0p7 already studied',common_days=common.sum(),maximum_difference=(f.loc[common,'position']-oldf.loc[common,'S2_clv']).abs().max(),same_observed_information=True,changed_availability='B22 per-feature endpoints, exact prefix clocks and OHLC; no volume gate',new_claim='filter accepted two-family complete account, not new factor')])
    parentreg={r['id']:r for r in json.loads((y.R/'registry.json').read_text())};paths={};selected={}
    for target,pid in [('T1','C12A'),('T05','C11A')]:
        _,paths[target],selected[target],_=y.combined_paths(parentreg[pid],masks,oldpaths)
    plans={};needs={};alias=[];seen={}
    for r in reg:
        key=r['id'];allow,app,known,reason=decide(r,f,family);t,need,participation=x.plan(d,allow,paths[r['target']],capacity=3)
        t['selected_rule']=t.entry_i.map(selected[r['target']]);t['family']=t.entry_i.map(family);t['category']=t.entry_i.map(category);plans[key]=t;needs[key]=need
        save(f'decisions/{key}.csv',pd.DataFrame(dict(date=d.date,family=family,category=category,applied=app,known=known,signal=allow,reason=reason)))
        save(f'participation/{key}.csv',participation)
        sig=hashlib.sha256(pd.DataFrame(dict(date=d.date,chosen=selected[r['target']].where(allow,''))).to_csv(index=False).encode()).hexdigest()
        alias.append(dict(id=key,canonical=seen.setdefault(sig,key),decision_path_sha256=sig,account_reused=False))
    save('path_aliases.csv',alias);js('pre_account_validation.json',dict(registered=56,core=38,availability=18,unique_decision_paths=len(seen),actual_new_accounts=168,reused_accounts=0))
    (R/'inherited_account_runtime.py.txt').write_text(x.source);rows=[]
    for r in reg:
        key=r['id']
        for bp in [5,11,20]:
            z,o,t,ff,met=x.account(d,plans[key],3000,bp/10000,schedule);x.audit(d,z,o,t,met);done=t[t.exit_i.notna()];st=b.stats(done.cash_increment,done.net_pct)
            rows.append(dict(**r,bp=bp,rule=label(r),**met,**{'trade_'+k:v for k,v in st.items()},average_profit=done.loc[done.cash_increment.gt(0),'cash_increment'].mean(),average_loss=done.loc[done.cash_increment.lt(0),'cash_increment'].mean(),minimum_old_shares=needs[key],max_buy_cash=ff.buy_cost.max(),max_single_deposit=ff.deposit.max(),max_wait_calendar_days=(pd.to_datetime(done.exit)-pd.to_datetime(done.entry)).dt.days.max(),inventory_blocked=int(pd.read_csv(R/f'participation/{key}.csv').reason.eq('inventory_participation').sum())))
            for folder,data,ext in [('accounts',z,'.csv.gz'),('orders',o,'.csv.gz'),('trades',t,'.csv'),('funds',ff,'.csv.gz')]:save(f'{folder}/{key}_{bp}'+ext,data)
            print('ACCOUNT',key,bp,met['increment'],met['completed'],flush=True)
    s=save('account_summary.csv',rows);parent=pd.read_csv(q.R/'comparison.csv');aligned=[]
    for target,pid in TARGETS.items():
        for bp in [5,11,20]:
            now=s[s.id.eq(target+'_ALL')&s.bp.eq(bp)].iloc[0];old=parent[parent.id.eq(pid)&parent.bp.eq(bp)].iloc[0]
            for col in ['increment','completed','trade_wins','trade_win','trade_worst','relative_mdd','terminal_tax_reserve','deposits']:assert abs(now[col]-old[col])<1e-5,(target,bp,col)
            aligned.append(dict(id=target+'_ALL',parent=pid,bp=bp,status='PASS'))
    save('parent_baseline_alignment.csv',aligned);analyze(d,s,reg);fine_signals(d,f,family,category,reg)
    for p,h in frozen['files'].items():assert b.sha(p)==h,p
    js('calculation_validation.json',dict(status='PASS',accounts=168,parent_alignments=6,parent_files=len(frozen['files']),data_cutoff=str(d.date.max().date()),core=38,availability=18,new_accounts=168,reused_accounts=0))
    js('manifest.json',dict(files={str(p):b.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['manifest.json','calculation.log','verification.log','failure.json','verification_manifest.json','independent_accounts_verified.csv','independent_validation.json','independent_verifier_runtime.py.txt','REVIEW_DATA.md']}))
def bridge(d,t,ref,new_s,old_s):
    v=q.bridge(t,ref,d);v['terminal_reserve']=old_s.terminal_tax_reserve-new_s.terminal_tax_reserve
    delta=new_s.increment-old_s.increment
    assert abs(delta-sum(v[k] for k in ['buy_price_and_fee','fifo_tax','missed_dividend','participation','pending_mark','terminal_reserve']))<1e-5
    a=t.set_index('entry_i');bb=ref.set_index('entry_i');removed=bb.loc[bb.index.difference(a.index)]
    v.update(net_change=delta,avoided_losses=int(removed.cash_increment.lt(0).sum()),forgone_wins=int(removed.cash_increment.gt(0).sum()),avoided_loss_cash=-removed.loc[removed.cash_increment.lt(0),'cash_increment'].sum(),forgone_win_cash=removed.loc[removed.cash_increment.gt(0),'cash_increment'].sum())
    return v
def analyze(d,s,reg):
    by={(r.id,r.bp):r for r in s.itertuples()};tr={(r.id,r.bp):trade(r.id,r.bp) for r in s.itertuples()};records=[];detail=[];period=[];annual=[];equity=[];groups=[];avail=[];mirrors=[]
    for baseline in ['T1_ALL','T05_ALL']:s['delta_'+baseline]=s.apply(lambda row:row.increment-by[baseline,row.bp].increment,axis=1)
    save('comparison.csv',s)
    for row in s.itertuples():
        t=tr[row.id,row.bp];done=t[t.exit_i.notna()]
        for name,sel in [('2020-2023',done.entry.lt('2024-01-01'))]+[(str(yr),done.entry.dt.year.eq(yr)) for yr in range(2024,2027)]:
            g=done[sel];period.append(dict(id=row.id,bp=row.bp,period=name,**b.stats(g.cash_increment,g.net_pct)))
            if row.bp==5 and len(g) and g.cash_increment.sum()<0:
                buy=1000*g.sell_ref*1.0005;sell=1000*g.buy_ref*.9995;cash=sell-buy-b.old.fee(buy,g.entry,False)-b.old.fee(sell,g.exit,True)
                mirrors.append(dict(id=row.id,period=name,n=len(g),normal_cash=g.cash_increment.sum(),reverse_price_cost_cash=cash.sum(),reverse_mean_pct=(100*cash/(1000*g.sell_ref)).mean(),missed_dividend=g.missed_dividend.sum(),status='independent opposite costs; reverse FIFO account unverified'))
        for yr in range(2020,2027):
            g=done[done.entry.dt.year.eq(yr)];annual.append(dict(id=row.id,bp=row.bp,year=yr,**b.stats(g.cash_increment,g.net_pct)))
        z=pd.read_csv(R/f'accounts/{row.id}_{row.bp}.csv.gz',parse_dates=['date']);prior=0.
        for yr,g in z.groupby(z.date.dt.year):
            end=g.relative.iloc[-1];equity.append(dict(id=row.id,bp=row.bp,year=yr,equity_change=end-prior,year_end_relative=end,tax_reserve=g.tax_reserve.iloc[-1],missing=3000-g.shares.iloc[-1]));prior=end
        for family in ['A','B','overlap']:
            g=done[done.category.eq('overlap') if family=='overlap' else done.family.eq(family)];groups.append(dict(id=row.id,bp=row.bp,family=family,**b.stats(g.cash_increment,g.net_pct)))
        refs=['T1_ALL','T05_ALL'];availability=f'{row.target}_{row.scope}_{row.feature}_avail' if row.side in ['ge','lt'] else row.target+'_ALL'
        if row.side in ['ge','lt']:refs.append(availability)
        for refkey in list(dict.fromkeys(refs)):
            ref=tr[refkey,row.bp];v=bridge(d,t,ref,row,by[refkey,row.bp]);records.append(dict(id=row.id,bp=row.bp,baseline=refkey,**v))
            if row.bp==5:
                tt=t.set_index('entry_i');rr=ref.set_index('entry_i');dec=pd.read_csv(R/f'decisions/{row.id}.csv')
                for i in tt.index.union(rr.index):
                    a=tt.loc[i] if i in tt.index else None;c=rr.loc[i] if i in rr.index else None
                    detail.append(dict(id=row.id,baseline=refkey,entry=d.date.iloc[i],entry_i=i,status='retained' if a is not None and c is not None else 'added' if a is not None else 'removed',family=a.family if a is not None else c.family,category=a.category if a is not None else c.category,reason=dec.reason.iloc[i],new_net=a.cash_increment if a is not None else 0.,old_net=c.cash_increment if c is not None else 0.,change=(a.cash_increment if a is not None else 0.)-(c.cash_increment if c is not None else 0.)))
        if row.side in ['ge','lt']:
            base=by[row.target+'_ALL',row.bp];av=by[availability,row.bp]
            avail.append(dict(id=row.id,bp=row.bp,baseline=base.id,availability=availability,availability_delta=av.increment-base.increment,market_delta=row.increment-av.increment,total_delta=row.increment-base.increment))
    for name,data in [('periods.csv',period),('yearly_trades.csv',annual),('annual_equity_changes.csv',equity),('family_groups.csv',groups),('attribution.csv',records),('attribution_trades.csv',detail),('availability_bridge.csv',avail),('opposite_direction_regions.csv',mirrors)]:save(name,data)
    leaders=[]
    for bp in [5,11,20]:
        pool=s[s.bp.eq(bp)&s.group.eq('core')]
        for objective,col in [('profit','increment'),('win','trade_win')]:
            eligible=pool if objective=='profit' else pool[pool.completed.ge(40)]
            pick=eligible.sort_values([col]+(['increment'] if col!='increment' else [])+['id'],ascending=[False]+([False] if col!='increment' else [])+[True]).head(3)
            for rank,r in enumerate(pick.itertuples(),1):leaders.append(dict(bp=bp,objective=objective,rank=rank,id=r.id,n=r.completed,win=r.trade_win,increment=r.increment))
    save('leaders.csv',leaders);top=set(r['id'] for r in leaders);det=pd.DataFrame(detail);tails=[];keydates=[]
    for key in sorted(top):
        for ref in ['T1_ALL','T05_ALL']:
            dd=det[det.id.eq(key)&det.baseline.eq(ref)];values=dd.change.sort_values(ascending=False);delta=by[key,5].increment-by[ref,5].increment
            tails.append(dict(id=key,baseline=ref,delta=delta,top1=values.head(1).sum(),top3=values.head(3).sum(),top5=values.head(5).sum(),without1=delta-values.head(1).sum(),without3=delta-values.head(3).sum(),without5=delta-values.head(5).sum()))
            for sign,g in [('positive',dd[dd.change.gt(.00001)].sort_values('change',ascending=False)),('negative',dd[dd.change.lt(-.00001)].sort_values('change'))]:keydates.extend(g.head(8).assign(sign=sign).to_dict('records'))
    save('concentration.csv',tails);save('key_gain_loss_dates.csv',keydates)
def fine_signals(d,f,family,category,reg):
    raw=pd.read_csv(b.r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);raw['clock']=raw.datetime.dt.strftime('%H:%M');expected=[b.minutes_after(start,k) for start in x.STARTS for k in range(1,6)];ds=d.set_index('date');days={};rawdays={}
    for day,g in raw.groupby('date'):
        g=g.sort_values('clock').copy()
        if day not in ds.index or list(g.clock)!=expected:continue
        rr=ds.loc[day]
        if max(abs(g.open.iloc[0]-rr.open),abs(g.close.iloc[-1]-rr.close),abs(g.high.max()-rr.high),abs(g.low.min()-rr.low))>=.011:continue
        if not ((g.high>=g[['open','close','low']].max(axis=1))&(g.low<=g[['open','close','high']].min(axis=1))&(g.volume>=0)).all():continue
        g['block']=np.arange(240)//5
        agg=lambda h:h.groupby('block').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),clock=('clock','last')).reset_index(drop=True)
        rawdays[day]=agg(g);g[['open','high','low','close']]=g[['open','high','low','close']].round(2);days[day]=agg(g)
    rows=[];base=trade('T1_ALL').set_index('entry_i');records=[];flip=[];top=set(pd.read_csv(R/'leaders.csv').id)
    rules={r['id']:r for r in reg};ffeat=f.copy()
    for i,tr in base.iterrows():
        available=tr.entry in days;ff=feature_day(days[tr.entry],d.preclose.iloc[i]) if available else None;rf=feature_day(rawdays[tr.entry],d.preclose.iloc[i]) if available else None
        if available:
            for col,v in ff.items():ffeat.loc[i,col]=v
        for name in ['day','position','tail']:
            old=f.loc[i,name];new=ff[name] if ff else np.nan;threshold=.7 if name=='position' else 0.;known=pd.notna(old);nk=pd.notna(new)
            row=dict(entry=tr.entry,entry_i=i,family=tr.family,category=tr.category,feature=name,day_qualified=available,old_value=old,new_value=new,raw_fine_value=rf[name] if rf else np.nan,old_available=known,new_available=nk,old_ge=bool(known and old>=threshold),new_ge=bool(nk and new>=threshold),raw_ge=bool(rf is not None and np.isfinite(rf[name]) and rf[name]>=threshold),flip=bool(known and nk and (old>=threshold)!=(new>=threshold)),availability_flip=bool(available and known!=nk),old_margin=f.loc[i,name+'_margin'],new_margin=ff[name+'_margin'] if ff else np.nan,old_p30=f.p30.iloc[i],new_p30=ff['p30'] if ff else np.nan,old_p50=f.p50.iloc[i],new_p50=ff['p50'] if ff else np.nan,old_h50=f.h50.iloc[i],new_h50=ff['h50'] if ff else np.nan,old_l50=f.l50.iloc[i],new_l50=ff['l50'] if ff else np.nan,original_net=tr.cash_increment)
            rows.append(row)
    fs=save('fine_feature_comparison.csv',rows);save('boundary_and_flip_dates.csv',fs[fs.old_margin.abs().le(.01000001)|fs.new_margin.abs().le(.01000001)|fs.flip|fs.availability_flip])
    for key in sorted(top):
        r=rules[key];olddec=pd.read_csv(R/f'decisions/{key}.csv');newdec=decide(r,ffeat,family)[0];t=trade(key).set_index('entry_i')
        for i,tr in base.iterrows():
            covered=tr.entry in days;applied=bool(olddec.applied.iloc[i]);kept=i in t.index;changed=bool(covered and newdec.iloc[i]!=olddec.signal.iloc[i]);one=dict(id=key,entry=tr.entry,entry_i=i,family=tr.family,category=tr.category,kept=kept,applied=applied,covered=covered,old_decision=bool(olddec.signal.iloc[i]),fine_decision=bool(newdec.iloc[i]) if covered else None,signal_flip=changed,reason=olddec.reason.iloc[i],baseline_net=tr.cash_increment,attribution=(t.cash_increment.loc[i] if kept else 0.)-tr.cash_increment)
            records.append(one)
            if changed:flip.append(one)
    rr=save('fine_candidate_decisions.csv',records);save('fine_candidate_flips.csv',pd.DataFrame(flip,columns=rr.columns))
    summary=rr.groupby(['id','kept','applied']).agg(n=('entry','size'),covered=('covered','sum'),signal_flips=('signal_flip','sum'),attribution=('attribution','sum')).reset_index();save('fine_coverage_summary.csv',summary)
    js('fine_quality.json',dict(qualified_days=len(days),price_tick=.01,observed_base_sell_days=int(fs[fs.feature.eq('day')].day_qualified.sum()),purpose='new sell-day prefix signals, kept and removed original dates; no main replacement',uncovered='unknown'))
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true';R.mkdir(parents=True,exist_ok=True)
    try:freeze() if sys.argv[1]=='freeze' else run()
    except Exception:
        js('failure.json',dict(run=os.environ.get('GITHUB_RUN_ID'),traceback=traceback.format_exc()));raise
