import os,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_t0_audit as old
assert os.environ.get("GITHUB_ACTIONS")=="true"
root=Path("research/foxconn_t0_20260913_hindsight_check")
root.mkdir(parents=True,exist_ok=True)
p=Path("research/foxconn_t0_20260913/results/daily_features_and_cashflows.csv")
q=Path("research/foxconn_t0_20260913_b03/results/hindsight_drawdown_attribution.csv")
m1=json.loads(Path("research/foxconn_t0_20260913/manifest.json").read_text())
m3=json.loads(Path("research/foxconn_t0_20260913_b03/manifest.json").read_text())
assert hashlib.sha256(p.read_bytes()).hexdigest()==m1["sha256"][str(p)]
assert hashlib.sha256(q.read_bytes()).hexdigest()==m3["files"][str(q)]
d=pd.read_csv(p,parse_dates=["date"]);periods=pd.read_csv(q,parse_dates=["peak","trough"])
old.tests()
rows=[];ledger=[]
for _,e in periods.iterrows():
    g=d[d.date.gt(e.peak)&d.date.le(e.trough)].copy()
    assert len(g)==e.n
    net=old.cashflow(g.open,g.close,g.date)
    np.testing.assert_allclose(net,g.rt_cash,rtol=1e-9,atol=1e-6)
    gross=1000*(g.open-g.close)
    grosspct=100*(1-g.close/g.open)
    met=old.metrics(g)
    rows.append(dict(peak=e.peak.date(),trough=e.trough.date(),n=len(g),
        stock_decline_pct=e.decline_pct,linked_intraday_pct=e.intraday_pct,
        gross_RT_mean_pct=float(grosspct.mean()),net_RT_mean_pct=met["mean_pct"],
        gross_RT_cash=float(gross.sum()),net_RT_cash=met["cash"],
        cost_and_slippage_cash=float((gross-net).sum()),win_pct=met["win_pct"],
        profitable_days=int(net.gt(0).sum()),losing_days=int(net.lt(0).sum()),
        D_days=int(g.stage.eq("D").sum()),nonD_days=int(g.stage.ne("D").sum()),
        D_net_RT_cash=float(g.loc[g.stage.eq("D"),"rt_cash"].sum()),
        nonD_net_RT_cash=float(g.loc[g.stage.ne("D"),"rt_cash"].sum()),
        oracle_only_winners_cash=float(net[net>0].sum()),oracle_note="future-dependent selection, not strategy",
        period_note="prior batch ex-post running-peak to trough interval; endpoints not known in real time"))
    for _,r in g.iterrows():ledger.append(dict(peak=e.peak.date(),trough=e.trough.date(),date=r.date.date(),stage=r.stage,open=r.open,close=r.close,net_RT_cash=r.rt_cash,net_RT_pct=r.rt_pct))
out=pd.DataFrame(rows)
out.to_csv(root/"period_results.csv",index=False)
pd.DataFrame(ledger).to_csv(root/"trades.csv",index=False)
summary=dict(intervals=len(out),positive_net_cash_intervals=int(out.net_RT_cash.gt(0).sum()),
    positive_net_mean_intervals=int(out.net_RT_mean_pct.gt(0).sum()),
    cash_and_mean_both_positive=int((out.net_RT_cash.gt(0)&out.net_RT_mean_pct.gt(0)).sum()),
    every_interval_contains_net_profitable_days=bool(out.profitable_days.gt(0).all()),
    boundary="Existence of hindsight profitable intervals is separate from their causal detectability. Stock decline alone does not imply daily open-close RT net profit.")
(root/"summary.json").write_text(json.dumps(summary,indent=2))
report="# Hindsight decline intervals: literal open-sell close-buy audit\n\n"+json.dumps(summary,indent=2)+"\n\n"+old.md_table(out.drop(columns=["oracle_note","period_note"]))+"\n\nThese intervals were selected by realized drawdowns in batch03, not by a new return search. Fixed 1000 old shares, same price/cost scenario. Net cash is incremental T cash, not portfolio return. Oracle selection only describes ex-post opportunities. No live strategy, new stage formula or overnight strategy is introduced.\n"
(root/"REPORT.md").write_text(report)
(root/"manifest.json").write_text(json.dumps(dict(code_sha=os.environ["GITHUB_SHA"],run_id=os.environ["GITHUB_RUN_ID"],input_hashes={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [p,q]},files={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in root.iterdir() if x.name!="manifest.json"}),indent=2))
print(report)
