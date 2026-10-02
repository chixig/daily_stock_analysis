"""Final protected-file and report-number checks for B22."""
import os,json
from pathlib import Path
import pandas as pd
import foxconn_b22 as z
R=z.R
def run():
    protected={}
    for name in ['manifest.json','verification_manifest.json','details_manifest.json']:
        protected.update(json.loads((R/name).read_text())['files'])
    frozen=json.loads((R/'frozen_input_hashes.json').read_text())
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert z.b.sha(p)==h,p
    for name in ['calculation_validation.json','independent_validation.json','details_validation.json']:
        assert json.loads((R/name).read_text())['status']=='PASS'
    s=pd.read_csv(R/'comparison.csv');assert len(s)==168 and len(z.registry())==56
    a=pd.read_csv(R/'parent_baseline_alignment.csv');assert len(a)==6 and a.status.eq('PASS').all()
    v=pd.read_csv(R/'independent_accounts_verified.csv');assert len(v)==168 and v.status.eq('PASS').all()
    for folder in ['accounts','orders','trades','funds']:assert len(list((R/folder).glob('*')))==168
    report=(R/'REPORT.md').read_text().replace('\u2212','-');checks=json.loads((R/'report_checks.json').read_text())
    for key,cols in checks.items():
        row=s[s.id.eq(key)&s.bp.eq(5)].iloc[0]
        for col in cols:
            token=f'{float(row[col]):,.2f}';assert token in report,(key,col,token)
    for row in s[s.bp.eq(5)&s.group.eq('core')].itertuples():
        for value in [row.increment,row.trade_win]:assert f'{value:,.2f}' in report,(row.id,value)
    f=pd.read_csv(R/'features.csv');assert f[f.date.eq('2021-12-24')].position.iloc[0]==.7
    for p,h in {**protected,**frozen['files'],**frozen['code']}.items():assert z.b.sha(p)==h,p
    z.js('delivery_validation.json',dict(status='PASS',accounts=168,independently_checked=168,parent_alignments=6,protected_results=len(protected),parent_files=len(frozen['files']),report_sha256=z.b.sha(R/'REPORT.md'),new_candidates=0,scope='B22 only; submitted, no adoption, main merge, trade or other-thread message'))
    files={str(p):z.b.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['delivery_manifest.json','delivery.log']}
    for p in Path('scripts/research').glob('foxconn_b22*.py'):files[str(p)]=z.b.sha(p)
    for p in Path('.github/workflows').glob('foxconn-b22*.yml'):files[str(p)]=z.b.sha(p)
    z.js('delivery_manifest.json',dict(files=files));print((R/'delivery_validation.json').read_text(),flush=True)
if __name__=='__main__':
    assert os.environ.get('GITHUB_ACTIONS')=='true';run()
