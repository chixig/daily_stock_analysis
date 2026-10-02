"""Validate final report against immutable B20 accounts and preserve delivery hashes."""
import os,json,hashlib,subprocess
from pathlib import Path
import pandas as pd
import foxconn_b20 as y
R=y.R;b=y.b
assert os.environ.get('GITHUB_ACTIONS')=='true'
protected={}
for name in ['manifest.json','verification_manifest.json','details_manifest.json']:
    for p,h in json.loads((R/name).read_text())['files'].items():
        if p in protected:assert protected[p]==h
        protected[p]=h
for p,h in protected.items():assert b.sha(p)==h,p
frozen=json.loads((R/'frozen_input_hashes.json').read_text())
for p,h in frozen['files'].items():assert b.sha(p)==h,p
s=pd.read_csv(R/'comparison.csv');report=(R/'REPORT.md').read_text()
for key in ['C12A','C11A','C00B','W0022']:
    row=s[s.id.eq(key)&s.bp.eq(5)].iloc[0]
    for col in ['increment','trade_win','trade_worst','relative_mdd']:
        expected=f'{abs(row[col]):,.2f}'
        assert expected in report,(key,col,expected)
assert 'status: submitted' in report and '2026年9月11日' in report
assert len(s)==90 and len(json.loads((R/'registry.json').read_text()))==30
assert json.loads((R/'independent_validation.json').read_text())['accounts']==90
actual={}
for folder in ['accounts','orders','trades','funds']:
    actual[folder]=len(list((R/folder).glob('*')));assert actual[folder]==90
assert all(s.pending.eq(0)) and all(s.inventory_blocked.eq(0))
version=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
y.js('delivery_validation.json',dict(status='PASS',head=version,report_sha256=b.sha(R/'REPORT.md'),protected_result_files=len(protected),parent_files=len(frozen['files']),account_files=actual,reported_metrics_match=True,report_status='submitted',main_merged=False,trades_executed=False))
files={str(p):b.sha(p) for p in R.rglob('*') if p.is_file() and p.name not in ['delivery_manifest.json','delivery.log']}
files.update({str(p):b.sha(p) for p in Path('scripts/research').glob('foxconn_b20*.py')})
y.js('delivery_manifest.json',dict(files=files))
print('DELIVERY PASS',b.sha(R/'REPORT.md'),len(files),flush=True)
