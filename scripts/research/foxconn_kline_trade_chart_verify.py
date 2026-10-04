"""Exercise reconstructed charts including their null candles in an actual browser."""
from pathlib import Path
import json
import pandas as pd
from playwright.sync_api import sync_playwright

ROOT=Path('research/foxconn_kline_repair_20261005/delivery')
def main():
    result=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for f in sorted(ROOT.glob('*.html')):
            page=browser.new_page(viewport={'width':1280,'height':900});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f.resolve().as_uri());page.wait_for_function('window.__chartReady === true')
            page.locator('#prev').click();page.locator('#next').click()
            page.locator('#span').select_option('20')
            page.locator('#chart').hover(position={'x':600,'y':220})
            assert page.locator('#tooltip').is_visible()
            page.locator('#span').select_option('1')
            null_checked=False
            if f.name.startswith('01_'):
                data=pd.read_csv(ROOT/'601138_1min_trades.csv');nulls=data[data.open.isna()]
                if len(nulls):
                    row=nulls.iloc[-1];day=str(row.datetime)[:10];page.locator('#date').fill(day);page.locator('#date').dispatch_event('change')
                    day_rows=data[data.datetime.str.startswith(day)].reset_index(drop=True);idx=int(day_rows[day_rows.datetime.eq(row.datetime)].index[0]);box=page.locator('#chart').bounding_box()
                    page.locator('#chart').hover(position={'x':66+(idx+.5)*(box['width']-90)/len(day_rows),'y':220})
                    assert '无成交' in page.locator('#tooltip').inner_text();null_checked=True
            with page.expect_download() as event:page.locator('#csv').click()
            assert event.value.suggested_filename.endswith('.csv')
            screenshot=Path('/tmp/foxconn_trade_chart_qa')/f.name.replace('.html','.png');screenshot.parent.mkdir(exist_ok=True);page.screenshot(path=str(screenshot))
            assert not errors,errors
            result.append({'chart':f.name,'status':'PASS','date_navigation':True,'multi_day_view':True,'tooltip':True,'csv_download':True,'null_minute_tooltip_checked':null_checked,'javascript_errors':errors})
            page.close()
        browser.close()
    (ROOT/'chart_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
