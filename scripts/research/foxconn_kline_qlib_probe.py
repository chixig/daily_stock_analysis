"""Inspect official Qlib-linked minute archives for the requested stock only."""
import hashlib
import json
from pathlib import Path
from remotezip import RemoteZip

ROOT=Path('research/foxconn_kline_repair_20261005');RAW=ROOT/'raw/qlib';AUDIT=ROOT/'audit'
def main():
    RAW.mkdir(exist_ok=True);results=[]
    for ver in ['v2','v1']:
        u=f'https://github.com/SunsetWolf/qlib_dataset/releases/download/{ver}/qlib_data_cn_1min_latest.zip'
        item={'version':ver,'url':u}
        try:
            with RemoteZip(u,timeout=60) as z:
                files=z.infolist();hits=[x for x in files if '601138' in x.filename.lower() and not x.is_dir()]
                meta=[x for x in files if 'calendars/' in x.filename and x.filename.endswith('.txt')]
                item.update(member_count=len(files),matches=[x.filename for x in hits],calendar_files=[x.filename for x in meta])
                for f in hits+meta:
                    if f.file_size>50_000_000:raise ValueError('Probe member exceeds 50MB cap')
                    data=z.read(f);p=RAW/ver/f.filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
                    item.setdefault('saved',[]).append({'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        except Exception as e:item['error']=repr(e)
        results.append(item);(AUDIT/'qlib_acquisition.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(item,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
