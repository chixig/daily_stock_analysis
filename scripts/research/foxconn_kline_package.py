from pathlib import Path
import gzip,hashlib,json,zipfile,shutil
R=Path('research/foxconn_kline_20261005');D=R/'delivery';C=R/'canonical';A=R/'audit'
assert json.loads((A/'independent_verification.json').read_text())['status']=='PASS'
assert all(r['status']=='PASS' for r in json.loads((A/'chart_verification.json').read_text()))
for name in ['independent_verification.json','chart_verification.json']:shutil.copyfile(A/name,D/name)
files={p.name:p.read_bytes() for p in D.iterdir() if p.is_file() and p.suffix not in ['.zip'] and p.name not in ['SHA256SUMS.txt','package_manifest.json']}
for name in ['601138_1min','601138_5min','601138_intraday']:files[name+'.csv']=gzip.decompress((C/(name+'.csv.gz')).read_bytes())
files['daily_reference.csv']=(C/'daily_reference.csv').read_bytes()
files['opening_source_records.parquet']=(C/'opening_source_records.parquet').read_bytes()
files['HF_SOURCE_LICENSE.txt']=(R/'raw/hf_metadata/LICENSE').read_bytes()
sha={n:hashlib.sha256(v).hexdigest() for n,v in files.items()}
files['SHA256SUMS.txt']=('\n'.join(sha[n]+'  '+n for n in sorted(sha))+'\n').encode()
zipname='工业富联_上市以来_1分钟K线_5分钟K线_每日分时_截至20260930.zip'
with zipfile.ZipFile(D/zipname,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in sorted(files):
        info=zipfile.ZipInfo(name,date_time=(2026,10,5,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,files[name])
with zipfile.ZipFile(D/zipname) as z:
    assert z.testzip() is None
    for name,digest in sha.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
manifest={'archive':zipname,'archive_sha256':hashlib.sha256((D/zipname).read_bytes()).hexdigest(),'archive_bytes':(D/zipname).stat().st_size,'files':sha}
(D/'package_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(D/'SHA256SUMS.txt').write_text(manifest['archive_sha256']+'  '+zipname+'\n')
# Hash all acquired and canonical evidence; keep self hashes out of the inventory.
allhash={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(R/'SHA256.json').write_text(json.dumps(allhash,ensure_ascii=False,indent=2))
print(json.dumps(manifest,ensure_ascii=False,indent=2))
