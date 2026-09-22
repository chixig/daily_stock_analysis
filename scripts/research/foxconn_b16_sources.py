#!/usr/bin/env python3
"""B16 evidence acquisition only; no account results computed."""
import os,json,re,hashlib,traceback,io
from pathlib import Path
import requests,pandas as pd
from pypdf import PdfReader
from bs4 import BeautifulSoup
R=Path('research/foxconn_t0_20260922_b16');P=Path('research/foxconn_overnight_sell_20260921_b15')
assert os.environ.get('GITHUB_ACTIONS')=='true'
(R/'sources').mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
logs=[]
def save_request(name,url,method='GET',data=None):
 try:
  rr=requests.request(method,url,data=data,timeout=25,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'})
  p=R/'sources'/name;p.write_bytes(rr.content)
  logs.append(dict(path=str(p),url=url,http=rr.status_code,sha256=sha(p),bytes=len(rr.content)))
  rr.raise_for_status();return rr
 except Exception as e:logs.append(dict(url=url,status='failed',error=str(e)));return None
def textof(p):
 b=Path(p).read_bytes()
 if b.startswith(b'%PDF'):
  return '\n'.join(x.extract_text() or '' for x in PdfReader(io.BytesIO(b)).pages),'pdf'
 s=b.decode('utf-8',errors='replace')
 if '公告日期' not in s:s=b.decode('gb18030',errors='replace')
 soup=BeautifulSoup(s,'html.parser');s=soup.get_text(' ',strip=True)
 return s,'html'
# Re-read existing sources first. HTTP200 impostor PDFs remain explicitly failed.
saved=[]
for p in list((P/'sources').glob('div*'))+list((P/'primary_sources').glob('20*.txt')):
 t,fmt=textof(p);clean=re.sub(r'\s+','',t)
 saved.append(dict(path=str(p),sha256=sha(p),format=fmt,has_issuer='富士康工业互联网股份有限公司'in clean,has_payment_heading='现金红利发放日'in clean,chars=len(t)))
pd.DataFrame(saved).to_csv(R/'saved_source_inspection.csv',index=False)
old=pd.read_csv(P/'primary_source_verification.csv');corp=pd.read_csv(P/'corporate_actions.csv')
# One official alternative catalogue query for all still-unverified events.
rr=save_request('cninfo_query.json','https://www.cninfo.com.cn/new/hisAnnouncement/query','POST',dict(pageNum='1',pageSize='30',column='sse',tabName='fulltext',stock='601138',searchkey='权益分派实施公告',secid='',plate='',category='',trade='',seDate='2019-01-01~2026-09-11',sortName='time',sortType='asc',isHLtitle='true'))
catalog=[]
if rr is not None:
 try:catalog=rr.json().get('announcements')or[]
 except Exception:pass
known={'2026-08-03':'https://static.cninfo.com.cn/finalpage/2026-07-24/1225438954.PDF'}
reprints={'2019-06-20':'https://pdf.dfcfw.com/pdf/H2_AN201906131334966769_1.pdf',
'2020-06-30':'https://q.stock.sohu.com/cn/601138/bw_6.shtml',
'2021-07-27':'https://www.jwview.com/jingwei/html/07-20/414603.shtml'}
rows=[]
for _,c in corp.iterrows():
 ex=c['date'];prior=old[old.ex_date.eq(ex)].iloc[0];chosen=None;level=None;url=None
 if prior.status=='amount_and_ex_pay_table_matched':
  chosen=P/'primary_sources'/f'{ex}.txt';level='primary_reused';url=prior.url
 else:
  for a in catalog:
   title=re.sub('<[^>]+>','',a.get('announcementTitle',''))
   if a.get('secCode')=='601138' and '权益分派实施公告'in title and c.announcement in a.get('adjunctUrl',''):
    known[ex]='https://static.cninfo.com.cn/'+a['adjunctUrl']
  if ex in known:
   rr=save_request(ex+'.pdf',known[ex])
   if rr is not None and rr.content.startswith(b'%PDF'):
    chosen=R/'sources'/(ex+'.pdf');level='primary_new';url=known[ex]
  if chosen is None:
   savedname={2022:'div2022_issuer_reprint.html',2023:'div2023_issuer_reprint.html',2024:'div2024_issuer_reprint.html'}.get(int(ex[:4]))
   if savedname:
    p=P/'sources'/savedname;t,fmt=textof(p);clean=re.sub(r'\s+','',t)
    if '现金红利发放日'in clean and '富士康工业互联网股份有限公司'in clean:
     chosen=p;level='issuer_announcement_reprint_reused';url=pd.read_csv(P/'sources.csv').set_index('id').loc[savedname[:-5],'url']
   elif ex in reprints:
    rr=save_request(ex+'_reprint'+('.pdf'if'.pdf'in reprints[ex]else'.html'),reprints[ex])
    if rr is not None:chosen=R/'sources'/(ex+'_reprint'+('.pdf'if'.pdf'in reprints[ex]else'.html'));level='reliable_reprint';url=reprints[ex]
 row=dict(ex_date=ex,amount_original=c.dividend_today,announcement=c.announcement,record_date=c.record_date,prior_status=prior.status,original_source=prior.url,source_status='unknown',payment_date=None,amount_verified=False,tradable_cash_clock='unknown; model after payment-day close')
 if chosen:
  t,fmt=textof(chosen);clean=re.sub(r'\s+','',t);out=R/'sources'/(ex+'_extracted.txt');out.write_text(t)
  year,month,day=map(int,ex.split('-'));compact=f'{year}/{month}/{day}'
  date_match=compact in clean or ex in clean
  amt=str(c.dividend_today);amount_match=amt in clean or str(c.dividend_today*10)in clean
  row.update(path=str(chosen),text_path=str(out),url=url,sha256=sha(chosen),level=level,format=fmt,source_status='candidate_text_requires_review',date_found=date_match,amount_string_found=amount_match)
  # Review compact relevant text; accepted only after explicit human-readable model review.
  i=clean.find('现金红利发放日');row['date_excerpt']=clean[max(0,i-80):i+220]
  j=clean.find('扣税说明');row['tax_excerpt']=clean[j:j+900]if j>=0 else ''
  row['start_excerpt']=clean[:1300]
 rows.append(row)
pd.DataFrame(rows).to_csv(R/'dividend_source_candidates.csv',index=False)
pd.DataFrame(logs).to_csv(R/'source_search_log.csv',index=False)
(R/'SOURCE_REVIEW.md').write_text('# B16 source candidates\n\n'+pd.DataFrame(rows).to_markdown(index=False))
print(pd.DataFrame(rows)[['ex_date','source_status','level','url','date_excerpt']].to_markdown(index=False),flush=True)
