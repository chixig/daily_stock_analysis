from pathlib import Path
import pandas as pd,json,requests,hashlib,re
B=Path('research/foxconn_kline_20261005');R=Path('research/foxconn_kline_repair_20261005');O=R/'provenance_r3';O.mkdir(exist_ok=True)
x=pd.read_csv(B/'audit/canonical_source_price_conflicts.csv.gz');x.datetime=pd.to_datetime(x.datetime)
pairs=[]
for key,g in x.groupby(['source_selected','source_other']):
 pairs.append({'selected':key[0],'other':key[1],'rows':len(g),'unique_minutes':int(g.datetime.nunique()),'dates':sorted(g.datetime.dt.strftime('%Y-%m-%d').unique().tolist())})
u=x[['datetime']].drop_duplicates().sort_values('datetime');u['date']=u.datetime.dt.strftime('%Y-%m-%d')
byday=[]
for day,g in x.groupby(x.datetime.dt.strftime('%Y-%m-%d')):
 byday.append({'date':day,'minutes':int(g.datetime.nunique()),'pairs':sorted(set(g.source_selected+' vs '+g.source_other))})
q=pd.read_csv(B/'delivery/daily_quality.csv');bad=q[~q.daily_ohl_match]
report={'distinct_conflict_minutes':int(x.datetime.nunique()),'comparison_rows':len(x),'pairs':pairs,'by_day':byday,'early_mismatch_days':len(bad),'early_by_source':bad.source.value_counts().to_dict(),'early_by_year':bad.date.str[:4].value_counts().to_dict()}
(O/'conflict_source_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));x.to_csv(O/'all_conflicting_versions.csv',index=False)
y=pd.read_csv(R/'public_r2/supplemental_delivery/2026_1min_closing_assignment_candidate.csv');y=y[y.datetime.str.startswith('2026-07-15')].copy();assert len(y)==240
for f in ['open','high','low','close','volume','amount']:y=y.rename(columns={f:'current_'+f});y['ths_'+f]=''
y['ths_adjustment']='';y['ths_time_label']='';y['ths_app_version']='';y['evidence_file']='';y.to_csv(O/'20260715_ths_comparison_template.csv',index=False)
z=pd.read_csv(R/'public_r2/2026-07-15_snapshot_trade_cumulative.csv.gz');report['snapshot_diagnostic_columns']=list(z.columns)
(O/'conflict_source_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
sources=[('ifind_faq','https://ftwc.51ifind.com/gwstatic/static/ds_web/quantapi-web/help-center/faq.html'),('neigezhu_provenance','https://huggingface.co/datasets/neigezhu/china-a-share-1min-ohlcv/raw/ba589a11534825044fe5a6b84838f50ba8d8d188/metadata/source_provenance.json'),('phields_schema','https://huggingface.co/datasets/phields/a-share-l2-trades/raw/2f4c13ee70cabf3f8b831acf7e1686481a762eaa/metadata/schema.json'),('baidu_public_share','https://pan.baidu.com/s/1W2TMPTHLWblKy1gBwMCIEQ?pwd=i4ru'),('phields_SHA_inventory','https://huggingface.co/api/datasets/phields/SHA/revision/6d0abf9fc6949a0906828faca690f56031d09549')]
res=[]
for name,url in sources:
 a={'name':name,'url':url}
 try:
  r=requests.get(url,timeout=25);a.update(http_status=r.status_code,bytes=len(r.content),sha256=hashlib.sha256(r.content).hexdigest());(O/(name+'.txt')).write_bytes(r.content)
  if 'html' in r.headers.get('Content-Type',''):a['title']=re.findall(r'<title[^>]*>(.*?)</title>',r.text,re.S)[:1]
 except Exception as e:a['error']=repr(e)
 res.append(a)
(O/'source_documents.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps(res,ensure_ascii=False,indent=2))
