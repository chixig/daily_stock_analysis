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
# Use only the publisher's publicly supplied extraction code. No login, CAPTCHA handling, or transfer.
s=requests.Session();u='https://pan.baidu.com/s/1W2TMPTHLWblKy1gBwMCIEQ';attempt={'public_share_url':u,'password_source':'https://github.com/aitech17/A_history','file_downloaded':False}
try:
 page=s.get(u,timeout=25);shareid=re.search(r'shareid[\"\s]*:[\"\s]*(\d+)',page.text);uk=re.search(r'share_uk[\"\s]*:[\"\s]*(\d+)',page.text)
 if not shareid or not uk:attempt['status']='public_share_identifiers_not_found'
 else:
  shareid=shareid.group(1);uk=uk.group(1)
  r=s.post('https://pan.baidu.com/share/verify',params={'shareid':shareid,'uk':uk,'web':1,'clienttype':0},data={'pwd':'i4ru','vcode':'','vcode_str':''},headers={'Referer':u},timeout=25)
  attempt['verify_http_status']=r.status_code
  try:v=r.json();attempt['verify_result']={k:v[k] for k in ['errno','err_msg','show_msg'] if k in v}
  except ValueError:v={};attempt['status']='verification_did_not_return_json'
  if v.get('errno')==0:
   r=s.get('https://pan.baidu.com/share/list',params={'shareid':shareid,'uk':uk,'root':1,'page':1,'num':100,'order':'name','desc':0,'web':1},headers={'Referer':u},timeout=25);v=r.json();attempt['list_errno']=v.get('errno');attempt['root_files']=[{k:a.get(k) for k in ['server_filename','path','isdir','size','fs_id']} for a in v.get('list',[])]
except Exception as e:attempt['error']=repr(e)
(O/'baidu_public_share_attempt.json').write_text(json.dumps(attempt,ensure_ascii=False,indent=2));print(json.dumps(attempt,ensure_ascii=False,indent=2))
if attempt.get('list_errno')==0:
 queue=[(a['path'],0) for a in attempt.get('root_files',[]) if str(a.get('isdir'))=='1'];seen=set();lists=[]
 while queue and len(lists)<20:
  path,depth=queue.pop(0)
  if path in seen:continue
  seen.add(path)
  try:
   r=s.get('https://pan.baidu.com/share/list',params={'shareid':shareid,'uk':uk,'dir':path,'page':1,'num':100,'order':'name','desc':0,'web':1},headers={'Referer':u},timeout=20);a=r.json();files=[{k:v.get(k) for k in ['server_filename','path','isdir','size','fs_id']} for v in a.get('list',[])]
   lists.append({'path':path,'depth':depth,'errno':a.get('errno'),'has_more':a.get('has_more'),'files':files})
   for v in files:
    if str(v.get('isdir'))=='1' and depth<3:
     name=v.get('server_filename','');years=re.findall(r'20\d{2}',name)
     if not years or any(2018<=int(y)<=2026 for y in years):queue.append((v['path'],depth+1))
  except Exception as e:lists.append({'path':path,'error':repr(e)})
 (O/'baidu_public_inventory.json').write_text(json.dumps({'folders':lists,'remaining_folders':queue,'downloaded_data_files':0},ensure_ascii=False,indent=2));print(json.dumps({'baidu_folders_inspected':len(lists),'remaining':len(queue)}))
# Read the archive's small published documentation before attempting any large download.
if attempt.get('list_errno')==0:
 from urllib.parse import unquote
 result={'requested_file':'data documentation text','data_files_downloaded':0}
 try:
  html=s.get(u,timeout=25).text
  sig=re.search(r'[\"\']sign[\"\']\s*:\s*[\"\']([^\"\']+)',html);ts=re.search(r'[\"\']timestamp[\"\']\s*:\s*[\"\']?(\d+)',html)
  result['page_has_sign']=bool(sig);result['page_has_timestamp']=bool(ts);result['page_title']=re.findall(r'<title[^>]*>(.*?)</title>',html,re.S)[:1]
  sign_value=sig.group(1) if sig else None;stamp_value=ts.group(1) if ts else None
  if not (sign_value and stamp_value):
   r=s.get('https://pan.baidu.com/share/tplconfig',params={'surl':'1W2TMPTHLWblKy1gBwMCIEQ','shareid':shareid,'uk':uk,'fields':'sign,timestamp','channel':'chunlei','web':1,'app_id':250528,'clienttype':0},headers={'Referer':u},timeout=25)
   a=r.json();result['tplconfig_http_status']=r.status_code;result['tplconfig_errno']=a.get('errno');d=a.get('data') or {};sign_value=d.get('sign');stamp_value=d.get('timestamp');result['tplconfig_has_parameters']=bool(sign_value and stamp_value)
  if sign_value and stamp_value:
   files=[f for row in lists for f in row.get('files',[])];target=[f for f in files if f.get('server_filename','').endswith('.txt')]
   if target:
    t=target[0];r=s.post('https://pan.baidu.com/api/sharedownload',params={'sign':sign_value,'timestamp':stamp_value,'web':1,'clienttype':0,'app_id':250528,'channel':'chunlei'},data={'encrypt':0,'extra':json.dumps({'sekey':unquote(s.cookies.get('BDCLND',''))}),'uk':uk,'primaryid':shareid,'product':'share','fid_list':json.dumps([int(t['fs_id'])])},headers={'Referer':u},timeout=25)
    v=r.json();result['download_api_errno']=v.get('errno');result['download_api_message']=v.get('err_msg',v.get('show_msg'))
    if v.get('errno')==0 and v.get('list'):
     url=v['list'][0].get('dlink')
     if url:
      r=s.get(url,timeout=30,stream=True);result['document_http_status']=r.status_code
      if r.status_code==200:
       data=b''
       for part in r.iter_content(8192):
        data+=part
        if len(data)>1048576:raise RuntimeError('document larger than expected; stopped')
       (O/'baidu_archive_documentation.txt').write_bytes(data);result['document_bytes']=len(data);result['document_sha256']=hashlib.sha256(data).hexdigest()
  else:result['status']='standard_download_parameters_not_exposed_to_anonymous_share_view'
 except Exception as e:result['error']=repr(e)
 (O/'baidu_document_access.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
