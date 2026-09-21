"""Keyboard, compact sheet, no-storage and empty collection acceptance."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def check(url,dest):
    dest.mkdir(parents=True,exist_ok=True);results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for width,height in [(1440,1000),(390,844)]:
            page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce')
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script("Storage.prototype.getItem=()=>{throw new Error('blocked')};Storage.prototype.setItem=()=>{throw new Error('blocked')}")
            page.route('**/api/guide',lambda r:r.fulfill(status=200,content_type='application/json',body='{"enabled":false}'))
            page.goto(url);page.wait_for_selector('body[data-city-ready="true"]')
            book=page.locator('.sheet-tabs [data-open="book"]' if width<900 else '.dock [data-open="book"]')
            book.click();page.locator('[data-book-filter="saved"]').click()
            assert page.locator('.card-grid button').count()==0
            assert page.get_by_text('아직 담은 명소가 없습니다.',exact=False).is_visible()
            page.locator('[data-open="landmarks"]').focus();page.keyboard.press('Enter')
            page.locator('[data-discovery-place="landmark-3"]').focus();page.keyboard.press('Enter')
            page.wait_for_function('()=>document.querySelector("#map").dataset.selected==="king-sejong"')
            assert page.get_by_text('위치 안내 · 외형 미확인',exact=True).is_visible()
            if width<900:
                assert abs(page.locator('#sheet').bounding_box()['height']-height*.4)<2
                page.locator('#sheet-handle').click();assert page.locator('#sheet').bounding_box()['height']>height*.5
                page.locator('#sheet-handle').click();assert abs(page.locator('#sheet').bounding_box()['height']-height*.4)<2
            page.locator('[data-collect="landmark-3"]').click()
            assert page.locator('[data-collect="landmark-3"]').inner_text()=='도감에서 빼기'
            assert page.locator('[data-collect="landmark-3"]').evaluate('(b)=>document.activeElement===b')
            page.keyboard.press('Escape')
            page.wait_for_function('()=>document.querySelector("#map").dataset.selected===""')
            assert page.locator('#map').evaluate('(b)=>document.activeElement===b')
            book.click();assert page.locator('.collection-head').inner_text().endswith('1/8')
            assert page.locator('.card-grid button').count()==1
            page.screenshot(path=str(dest/f'{width}_storage-blocked.png'))
            page.reload();page.wait_for_selector('body[data-city-ready="true"]');book.click()
            assert page.locator('.collection-head').inner_text().endswith('0/8')
            page.keyboard.press('Escape');page.locator('#fit').click()
            page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
            labels=page.locator('.discovery-marker:visible').evaluate_all('(bs)=>bs.map(b=>{const r=b.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}})')
            for i,a in enumerate(labels):
                for b in labels[i+1:]:assert not (a['left']<b['right'] and a['right']>b['left'] and a['top']<b['bottom'] and a['bottom']>b['top'])
            assert not errors,errors
            results.append({'viewport':[width,height],'keyboardSelection':True,'emptyFilter':True,'storageBlockedSessionOnly':True,'focusRestored':True,'sheetToggle':width<900,'fitLabelsNoOverlap':True,'errors':errors});page.close()
        browser.close()
    (dest/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8766/work/landmark-discovery-20260922/');p.add_argument('--dest',type=Path,default=Path('prototype2/work/landmark-discovery-20260922/accessibility'));a=p.parse_args();check(a.url,a.dest)
