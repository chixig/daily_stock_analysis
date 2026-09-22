#!/usr/bin/env python3
import os,json,re,io,hashlib,zipfile
from pathlib import Path
import requests,pandas as pd,numpy as np
from pypdf import PdfReader
from bs4 import BeautifulSoup
import foxconn_overnight_sell_b15_r1 as r1
assert os.environ.get('GITHUB_ACTIONS')=='true'
R=Path('research/foxconn_t0_20260922_b16');P=r1.P
logs=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def request(name,url,data=None):
 try:
  x=requests.post(url,data=data,timeout=20)if data is not None else requests.get(url,timeout=20)
  p=R/'sources'/name;p.write_bytes(x.content);logs.append(dict(path=str(p),url=url,status=x.status_code,sha256=sha(p),parameters=data))
  x.raise_for_status();return x
 except Exception as e:logs.append(dict(url=url,error=str(e)));return None
def extract(p):
 b=Path(p).read_bytes()
 if b.startswith(b'%PDF'):return '\n'.join(pg.extract_text()or''for pg in PdfReader(io.BytesIO(b)).pages)
 if str(p).endswith('.txt'):return b.decode('utf-8')
 try:s=b.decode('utf-8')
 except UnicodeDecodeError:s=b.decode('gb18030',errors='replace')
 return BeautifulSoup(s,'html.parser').get_text(' ',strip=True)
x=request('cninfo_stock_lookup.json','https://www.cninfo.com.cn/new/information/topSearch/query',{'keyWord':'601138','maxNum':'10'})
catalog=[]
if x is not None:
 try:
  entries=x.json();entries=entries if isinstance(entries,list) else entries.get('data',[])
  match=next(a for a in entries if a.get('code')=='601138')
  x=request('cninfo_query_with_orgid.json','https://www.cninfo.com.cn/new/hisAnnouncement/query',dict(pageNum='1',pageSize='30',column='sse',tabName='fulltext',stock='601138,'+match['orgId'],searchkey='权益分派实施公告',seDate='2019-01-01~2026-09-11',sortName='time',sortType='asc',isHLtitle='true'))
  if x is not None:catalog=x.json().get('announcements')or[]
 except Exception as e:logs.append(dict(stage='cninfo_lookup_parse',error=str(e)))
candidates=pd.read_csv(R/'dividend_source_candidates.csv');out=[]
for _,row in candidates.iterrows():
 c=row.to_dict();ex=c['ex_date'];p=None;level=None;url=None
 if c['prior_status']=='amount_and_ex_pay_table_matched':
  p=P/'primary_sources'/(ex+'.pdf');level='primary_reused';url=c['url']
 elif c.get('level')=='primary_new':p=Path(c['path']);level='primary_new';url=c['url']
 else:
  for a in catalog:
   if c['announcement'] in a.get('adjunctUrl','') and '权益分派实施公告'in re.sub('<[^>]+>','',a.get('announcementTitle','')):
    url='https://static.cninfo.com.cn/'+a['adjunctUrl']
    x=request(ex+'_official.pdf',url)
    if x is not None and x.content.startswith(b'%PDF'):p=R/'sources'/(ex+'_official.pdf');level='primary_new'
    break
  if p is None and pd.notna(c.get('path')):p=Path(c['path']);level=c.get('level');url=c.get('url')
  if p is None and ex=='2019-06-20':
   url='https://q.stock.sohu.com/cn/601138/bw_4.shtml';x=request(ex+'_sohu.html',url)
   if x is not None:p=R/'sources'/(ex+'_sohu.html');level='reliable_reprint'
 if p is None:c.update(source_status='unknown',payment_date=None,amount_verified=False)
 else:
  t=extract(p);clean=re.sub(r'\s+','',t);tp=R/'sources'/(ex+'_reviewed.txt');tp.write_text(t)
  ix=clean.find('现金红利发放日');tax=clean.find('扣税说明')
  c.update(path=str(p),text_path=str(tp),sha256=sha(p),url=url,level=level,source_status='review_pending',date_excerpt=clean[max(0,ix-150):ix+160],tax_excerpt=clean[tax:tax+1100]if tax>=0 else'',start_excerpt=clean[:1500],payment_date=None,amount_verified=False)
 out.append(c)
pd.DataFrame(out).to_csv(R/'dividend_review.csv',index=False)
(R/'source_supplement_log.json').write_text(json.dumps(logs,ensure_ascii=False,indent=2))
# Price preflight; no account results calculated. Same saved inputs only.
d=pd.read_csv(P/'daily_ledger.csv',parse_dates=['date','exit_date'])
with zipfile.ZipFile('research/foxconn_t0_20260913/source/601138-full-5min-history.zip')as z:
 names=z.namelist();m=pd.read_csv(z.open(next(n for n in names if n.endswith('601138_5min_all.csv'))))
m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M')
k=pd.read_csv(r1.B13/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);k['clock']=k.datetime.dt.strftime('%H:%M')
day=pd.Timestamp('2026-05-15');a=m[m.date.eq(day)].copy();b=k[k.date.eq(day)].copy().sort_values('clock');rr=d[d.date.eq(day)]
a.to_csv(R/'price_20260515_5m.csv',index=False);b.to_csv(R/'price_20260515_1m.csv',index=False);rr.to_csv(R/'price_20260515_daily.csv',index=False)
bb=b.copy();bb['block']=np.arange(len(bb))//5
agg=bb.groupby('block').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),clock=('clock','last'))
comp=a.set_index('clock')[['open','high','low','close']].join(agg.set_index('clock'),rsuffix='_1m')
comp.to_csv(R/'price_20260515_bar_compare.csv')
meta=dict(zip_names=names,columns5m=list(m.columns),columns1m=list(k.columns),five_min_first_last=[str(a.clock.min()),str(a.clock.max())],one_min_first_last=[str(b.clock.min()),str(b.clock.max())],datetime_timezone=str(k.datetime.dt.tz),daily=rr[['date','open','high','low','close','preclose','dividend_today']].to_dict('records'),adjustflags5m=a.adjustflag.unique().tolist()if'adjustflag'in a else None,bar_semantics=json.loads((P/'bar_semantics.json').read_text()))
(R/'price_preflight.json').write_text(json.dumps(meta,default=str,indent=2))
(R/'PREFLIGHT_REVIEW.md').write_text('# Evidence review before account calculation\n\n'+pd.DataFrame(out)[['ex_date','level','date_excerpt']].to_markdown(index=False)+'\n\n## 2026-05-15 first bars\n\n'+comp.head(8).to_markdown()+'\n\n## Metadata\n\n'+json.dumps(meta,default=str,ensure_ascii=False,indent=2))
print('PREFLIGHT_COMPLETE',flush=True)
