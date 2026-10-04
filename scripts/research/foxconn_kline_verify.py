"""Independent checks over the saved final files; no downloader/build helper imports."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path('research/foxconn_kline_20261005');C=ROOT/'canonical';R=ROOT/'raw';A=ROOT/'audit'


def main():
    one=pd.read_parquet(C/'601138_1min.parquet');five=pd.read_parquet(C/'601138_5min.parquet');snap=pd.read_parquet(C/'601138_intraday.parquet')
    expected=pd.read_csv(R/'old_5m/601138_daily_raw.csv')
    expected=expected[(expected.tradestatus.astype(int)==1)&(expected.date>='2018-06-08')&(expected.date<='2026-09-30')].date.tolist()
    td=pd.read_csv(R/'tdx_daily_fresh.csv.gz');assert sorted(td.datetime.str[:10].unique())==expected
    def times(frequency):
        return ([f'{m//60:02d}:{m%60:02d}' for m in range(570+frequency,691,frequency)] + [f'{m//60:02d}:{m%60:02d}' for m in range(780+frequency,901,frequency)])
    for df,frequency in [(one,1),(five,5),(snap,1)]:
        assert df.datetime.is_monotonic_increasing and not df.datetime.duplicated().any()
        assert df.symbol.eq('601138.SH').all()
        days=df.datetime.dt.strftime('%Y-%m-%d')
        assert sorted(days.unique())==expected
        for day,g in df.groupby(days):assert g.datetime.dt.strftime('%H:%M').tolist()==times(frequency),day
    assert len(one)==len(snap)==len(expected)*240
    assert len(five)==len(expected)*48
    cols=['open','high','low','close','volume','amount']
    for df in [one,five]:
        assert np.isfinite(df[cols]).all().all()
        assert (df[['open','high','low','close']]>0).all().all()
        assert (df[['volume','amount']]>=0).all().all()
        assert (df.high>=df[['open','close','low']].max(axis=1)).all()
        assert (df.low<=df[['open','close','high']].min(axis=1)).all()
    arr=one[cols].to_numpy().reshape(-1,5,6)
    rebuilt=np.column_stack([arr[:,0,0],arr[:,:,1].max(axis=1),arr[:,:,2].min(axis=1),arr[:,-1,3],arr[:,:,4].sum(axis=1),arr[:,:,5].sum(axis=1)])
    assert np.allclose(rebuilt,five[cols].to_numpy(),atol=.001,rtol=0)
    assert one.datetime.iloc[4::5].reset_index(drop=True).equals(five.datetime)
    # Every canonical price/volume must correspond to the chosen frozen source.
    hf=pd.read_parquet(R/'hf_601138.parquet').rename(columns={'timestamp':'datetime','turnover':'amount'})
    d=hf.datetime.dt.strftime('%Y-%m-%d');a=hf[hf.datetime.dt.strftime('%H:%M')=='09:30'].copy();a.index=d[a.index]
    hf=hf[hf.datetime.dt.strftime('%H:%M')!='09:30'].copy()
    first=hf.datetime.dt.strftime('%H:%M')=='09:31';keys=hf.loc[first,'datetime'].dt.strftime('%Y-%m-%d')
    hf.loc[first,'open']=a.loc[keys,'open'].to_numpy()
    hf.loc[first,'high']=np.maximum(hf.loc[first,'high'],a.loc[keys,'high'].to_numpy())
    hf.loc[first,'low']=np.minimum(hf.loc[first,'low'],a.loc[keys,'low'].to_numpy())
    for c in ['volume','amount']:hf.loc[first,c]=hf.loc[first,c].to_numpy()+a.loc[keys,c].to_numpy()
    b13=pd.read_csv(R/'b13_1m.csv',parse_dates=['datetime']);oldmain=pd.read_csv(R/'main_1m.csv',parse_dates=['datetime']);fresh=pd.read_csv(R/'tdx_1m_fresh.csv.gz',parse_dates=['datetime']).rename(columns={'vol':'volume'})
    for label,source in [('hf_0930_fold',hf),('b13_tdx',b13),('main_tdx',oldmain),('tdx_20261005',fresh)]:
        chosen=one[one.source==label]
        check=chosen.merge(source[['datetime',*cols]],on='datetime',suffixes=('_c','_s'))
        assert len(check)==len(chosen)
        for c in cols:
            expected_values=check[c+'_s'].round(0 if c=='volume' else 2)
            assert np.allclose(check[c+'_c'],expected_values,atol=.001,rtol=0),(label,c)
    sr=pd.concat([pd.read_csv(f) for f in sorted((R/'snapshot_full').glob('*.csv.gz'))]).sort_values(['trade_date','position']).reset_index(drop=True)
    assert len(sr)==len(snap)
    assert np.allclose(sr.price.round(2),snap.price,atol=1e-8,rtol=0)
    assert np.allclose((sr.vol*100).round(),snap.volume,atol=0,rtol=0)
    assert np.allclose(sr.avg_price.round(6),snap.provider_avg_price,atol=1e-8,rtol=0)
    assert (snap.source_time==(sr.hour.astype(str).str.zfill(2)+':'+sr.minute.astype(str).str.zfill(2))).all()
    q=pd.read_csv(C/'daily_quality.csv');cv=json.loads((C/'coverage.json').read_text())
    assert int(q.strict_eligible.sum())==cv['strict_eligible_days']
    assert int(one.source_conflict.sum())==cv['source_conflict_bars']
    assert int(snap.bar_close_conflict.sum())==cv['snapshot_bar_price_conflict_points']
    # Re-read CSV representations and compare with Parquet.
    for name,df in [('601138_1min',one),('601138_5min',five),('601138_intraday',snap)]:
        csv=pd.read_csv(C/f'{name}.csv.gz',parse_dates=['datetime'])
        pd.testing.assert_frame_equal(csv,df,check_dtype=False,atol=1e-6,rtol=0)
    hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in C.iterdir() if f.is_file()}
    report={'status':'PASS','rows_verified':{'one_minute':len(one),'five_minute':len(five),'intraday':len(snap)},'trading_days':len(expected),'checks':['two_daily_calendars','all_session_grids','uniqueness_and_sort','finite_positive_ohlc','ohlc_bounds','independent_5m_reshape','selected_source_all_rows','native_snapshot_all_rows','csv_parquet_roundtrip','quality_counts'],'scope':'Structural and source fidelity verification; disclosed source disagreements remain unresolved.','canonical_sha256':hashes}
    (A/'independent_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
