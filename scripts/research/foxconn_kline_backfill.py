"""Acquire and inspect frozen 601138 OHLC sources. Never infer OHLC from snapshots."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import sys
import time
import zipfile
import pandas as pd
import requests

OUT = Path('research/foxconn_kline_20261005')
RAW = OUT / 'raw'
AUDIT = OUT / 'audit'
HF_REV = 'ba589a11534825044fe5a6b84838f50ba8d8d188'
HF = f'https://huggingface.co/datasets/neigezhu/china-a-share-1min-ohlcv/resolve/{HF_REV}/'
MAIN = 'e428977626fa6575dc8f4a5b0693c11e93f9a4c2'
B27 = 'fc832bce87c5963349bd9df9766fbf60089c385d'
REPO = 'chixig/daily_stock_analysis'
MANIFEST = []


def download(url, destination, expected=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with requests.get(url, timeout=(20, 90), stream=True) as response:
                response.raise_for_status()
                with destination.open('wb') as f:
                    for chunk in response.iter_content(1024 * 1024):
                        f.write(chunk)
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            if expected and digest != expected:
                raise ValueError(f'SHA256 mismatch: {destination.name}')
            MANIFEST.append({'url': url, 'path': str(destination), 'sha256': digest,
                             'bytes': destination.stat().st_size})
            print('Downloaded', destination, destination.stat().st_size, flush=True)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def inspect_frame(frame, name, timestamp):
    x = frame.copy()
    x['datetime'] = pd.to_datetime(x[timestamp], errors='raise')
    x = x.sort_values('datetime')
    fields = ['open', 'high', 'low', 'close']
    for field in fields:
        x[field] = pd.to_numeric(x[field], errors='raise')
    invalid = (x[fields].isna().any(axis=1) | (x[fields] <= 0).any(axis=1)
               | (x['high'] + 1e-5 < x[['open', 'close', 'low']].max(axis=1))
               | (x['low'] - 1e-5 > x[['open', 'close', 'high']].min(axis=1)))
    x['day'] = x['datetime'].dt.strftime('%Y-%m-%d')
    x['hhmm'] = x['datetime'].dt.strftime('%H:%M')
    daily = x.groupby('day').agg(rows=('datetime', 'size'), first=('hhmm', 'min'),
                               last=('hhmm', 'max'), open=('open', 'first'),
                               high=('high', 'max'), low=('low', 'min'), close=('close', 'last'))
    daily.to_csv(AUDIT / f'{name}_daily.csv')
    x.groupby('hhmm').size().to_csv(AUDIT / f'{name}_time_labels.csv', header=['rows'])
    summary = {'name': name, 'rows': len(x), 'days': len(daily),
               'first': str(x['datetime'].min()), 'last': str(x['datetime'].max()),
               'columns': list(frame.columns), 'duplicate_timestamps': int(x['datetime'].duplicated().sum()),
               'invalid_ohlc': int(invalid.sum()),
               'daily_count_distribution': daily['rows'].value_counts().to_dict()}
    x.head(5).to_csv(AUDIT / f'{name}_first_sample.csv', index=False)
    x.tail(5).to_csv(AUDIT / f'{name}_last_sample.csv', index=False)
    x[invalid].to_csv(AUDIT / f'{name}_invalid_ohlc.csv', index=False)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return x, summary


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    download(HF + 'data/stock_1m/SH/601138.parquet', RAW / 'hf_601138.parquet',
             '5bfaf612539495debbe441049112793ee455e33d8588f0d732e8cd9708675a43')
    for name in ['README.md', 'LICENSE', 'metadata/source_provenance.json',
                 'metadata/coverage_by_instrument.csv', 'metadata/missing_intervals.csv']:
        download(HF + name, RAW / 'hf_metadata' / name)
    base = f'https://raw.githubusercontent.com/{REPO}/'
    download(base + MAIN + '/data/601138_intraday/pytdxdata_1min/kline_yearly/601138_1m_kline_2026.csv', RAW / 'main_1m.csv')
    download(base + B27 + '/research/foxconn_overnight_20260917_b13/tdx_recovered_1m.csv', RAW / 'b13_1m.csv')
    download(base + MAIN + '/data/601138_intraday/pytdxdata_1min/daily_trade_calendar.csv', RAW / 'old_calendar.csv')
    # GitHub artifact remains a separate source, never silently replaced by a new query.
    artifact = subprocess.run(['gh', 'api', f'repos/{REPO}/actions/artifacts/11243418261/zip'],
                              check=True, stdout=subprocess.PIPE).stdout
    with zipfile.ZipFile(io.BytesIO(artifact)) as archive:
        for item in archive.infolist():
            leaf = Path(item.filename).name
            if leaf in ['601138_5min_all.csv', '601138_daily_raw.csv', 'qc_daily.csv', 'coverage.json']:
                p = RAW / 'old_5m' / leaf
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(archive.read(item))
    MANIFEST.append({'source': 'GitHub Actions artifact', 'artifact_id': 11243418261,
                     'run_id': 37044085482, 'zip_sha256': hashlib.sha256(artifact).hexdigest()})
    sources = {}
    summaries = []
    for name, frame, column in [
        ('hf', pd.read_parquet(RAW / 'hf_601138.parquet'), 'timestamp'),
        ('main', pd.read_csv(RAW / 'main_1m.csv'), 'datetime'),
        ('b13', pd.read_csv(RAW / 'b13_1m.csv'), 'datetime'),
        ('old5m', pd.read_csv(RAW / 'old_5m/601138_5min_all.csv'), 'datetime'),
    ]:
        sources[name], summary = inspect_frame(frame, name, column)
        summaries.append(summary)
    hf, old = sources['hf'], sources['b13']
    # Test alignment hypotheses explicitly; do not shift timestamps automatically.
    alignments = []
    for offset in [-1, 0, 1]:
        left = hf[['datetime', 'open', 'high', 'low', 'close']].copy()
        left['datetime'] += pd.Timedelta(minutes=offset)
        pair = left.merge(old[['datetime', 'open', 'high', 'low', 'close']], on='datetime', suffixes=('_hf', '_old'))
        diffs = pd.DataFrame({c: (pair[c + '_hf'] - pair[c + '_old']).abs() for c in ['open', 'high', 'low', 'close']})
        alignments.append({'hf_time_shift_minutes': offset, 'matched_rows': len(pair),
                           'all_ohlc_within_0_005': int((diffs <= 0.005).all(axis=1).sum()),
                           'median_diffs': diffs.median().to_dict(), 'max_diffs': diffs.max().to_dict()})
        if offset == 0:
            pair.loc[(diffs > 0.005).any(axis=1)].to_csv(AUDIT / 'hf_b13_conflicts_unshifted.csv.gz', index=False)
    result = {'status': 'ACQUIRED_PENDING_SEMANTIC_VALIDATION', 'target_start': '2018-06-08',
              'target_end': '2026-09-30', 'sources': summaries, 'alignment_hypotheses': alignments,
              'warning': 'No merged dataset is certified by this acquisition step. No snapshots used.'}
    (AUDIT / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    (AUDIT / 'source_manifest.json').write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=2))
    hashes = {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in OUT.rglob('*') if p.is_file() and p.name != 'SHA256.json'}
    (OUT / 'SHA256.json').write_text(json.dumps(hashes, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
