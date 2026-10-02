"""Protect research bytes and check the submitted report against saved metrics."""
import os,json
from pathlib import Path
import pandas as pd
import foxconn_b21 as q
R=q.R
def run():
    protected={}
    for name in ['manifest.json','verification_manifest.json','details_manifest.json']:
        protected.update(json.loads((R/name).read_text())['files'])
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert q.b.sha(p)==h,p
    for name in ['calculation_validation.json','independent_validation.json','details_validation.json']:
        assert json.loads((R/name).read_text())['status']=='PASS'
    s=pd.read_csv(R/'comparison.csv');assert len(s)==84 and len(q.registry())==28
    a=pd.read_csv(R/'parent_baseline_alignment.csv');assert len(a)==18 and a.status.eq('PASS').all()
    verified=pd.read_csv(R/'independent_accounts_verified.csv');assert len(verified)==84 and verified.status.eq('PASS').all()
    for folder in ['accounts','orders','trades','funds']:assert len(list((R/folder).glob('*')))==84,folder
    report=(R/'REPORT.md').read_text();checks=json.loads((R/'report_checks.json').read_text())
    for key,cols in checks.items():
        row=s[s.id.eq(key)&s.bp.eq(5)].iloc[0]
        for col in cols:
            value=float(row[col]);token=f'{value:,.2f}'
            assert token in report,(key,col,token)
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert q.b.sha(p)==h,p
    q.js('delivery_validation.json',dict(status='PASS',accounts=84,independently_checked=84,parent_alignments=18,protected_results=len(protected),parent_files=len(frozen['files']),report_sha256=q.b.sha(R/'REPORT.md'),new_candidates=0,scope='B21 only; no main merge, trade or other-thread message'))
    files={str(p):q.b.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['delivery_manifest.json','delivery.log']}
    for p in Path('scripts/research').glob('foxconn_b21*.py'):files[str(p)]=q.b.sha(p)
    for p in Path('.github/workflows').glob('foxconn-b21*.yml'):files[str(p)]=q.b.sha(p)
    q.js('delivery_manifest.json',dict(files=files))
    print(json.dumps(json.loads((R/'delivery_validation.json').read_text()),ensure_ascii=False),flush=True)
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true';run()
