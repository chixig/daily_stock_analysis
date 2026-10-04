from pathlib import Path
import json
from playwright.sync_api import sync_playwright
ROOT=Path('research/foxconn_kline_20261005');report=[]
images=Path('/tmp/foxconn_chart_qa');images.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for i,f in enumerate(sorted((ROOT/'delivery').glob('*.html'))):
        page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f.resolve().as_uri(),wait_until='load')
        page.wait_for_function('window.__chartReady === true',timeout=90000)
        assert page.locator('#date').input_value()=='2026-09-30'
        assert '2,019' in page.locator('#range').inner_text()
        page.screenshot(path=str(images/f'{i}_latest.png'),full_page=True)
        page.locator('#date').fill('2018-06-08');page.locator('#date').dispatch_event('change')
        assert page.locator('#status').inner_text().startswith('1 /')
        page.screenshot(path=str(images/f'{i}_listing.png'),full_page=True)
        page.locator('#next').click();assert page.locator('#date').input_value()=='2018-06-11'
        page.locator('#date').fill('2026-09-30');page.locator('#date').dispatch_event('change')
        page.locator('#span').select_option('20')
        page.locator('#chart').hover(position={'x':500,'y':200})
        assert page.locator('#tooltip').is_visible()
        with page.expect_download() as dl:page.locator('#csv').click()
        download=dl.value;dest=images/f'{i}_export.csv';download.save_as(dest)
        assert dest.read_text(encoding='utf-8-sig').splitlines()[0].startswith('datetime,')
        assert not errors,errors
        report.append({'file':f.name,'status':'PASS','tested':['offline_load','latest_date','listing_date','next_trading_day','20_day_view','hover_tooltip','csv_download'],'console_errors':errors})
        page.close()
    browser.close()
(ROOT/'audit/chart_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
