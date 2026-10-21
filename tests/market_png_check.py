"""Focused, entirely local checks. External requests are blocked; no real submissions."""
import functools, http.server, io, json, os, pathlib, shutil, threading
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
URL = f'http://127.0.0.1:{server.server_port}'
FONT = list(pathlib.Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf').read_bytes())
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'), headless=True)
    for width, height, touch in [(1440, 1000, False), (820, 1180, True), (390, 844, True)]:
        context = browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch, is_mobile=touch)
        context.route('https://**/*', lambda r: r.abort())
        page = context.new_page(); errors = []; posts = []; image_requests = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: posts.append(r.url) if r.method != 'GET' else None)
        page.on('request', lambda r: image_requests.append(r.url) if '/assets/motifs/' in r.url else None)
        page.goto(URL); page.wait_for_function('() => studio.ready')
        # Deterministic stand-in font tests geometry, not the fidelity of Google fonts.
        page.evaluate("async bytes => {const font=await new FontFace('Montserrat',new Uint8Array(bytes)).load();document.fonts.add(font);personalFontsChanged()}", FONT)
        assert page.locator('form').count() == 0
        assert page.locator('[data-inquiry]').count() == 0
        assert page.evaluate('typeof inquirySubmit') == 'undefined'
        def ready():
            page.wait_for_selector('#pngExport .png-download:not([hidden])')
            assert page.locator('#pngExport a').count() == 1
            page.wait_for_function('() => document.querySelector(".png-preview").naturalWidth===2400')
            assert page.locator('#pngExport form').count() == 0
            assert page.locator('#pngExport').evaluate('e=>e.scrollWidth<=e.clientWidth')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        def download_png():
            with page.expect_download() as download:
                (page.locator('.png-download').tap() if touch else page.locator('.png-download').click())
            assert download.value.suggested_filename == 'timberart-design.png'
            data = pathlib.Path(download.value.path()).read_bytes()
            image = Image.open(io.BytesIO(data)); image.load()
            assert image.format == 'PNG' and image.size == (2400, 2400)
            assert image.convert('RGBA').getextrema()[3] == (255, 255)
            assert image.convert('RGB').getpixel((0, 0)) == (255, 255, 255)
            return image
        page.locator('[data-view="motifs"]').click()
        page.locator('[data-favorite]').first.click(); assert page.evaluate('favorites.length') == 1
        page.locator('[data-design]').first.click()
        page.locator('[data-png-export="motif"]').click(); ready()
        plain = download_png()
        assert ImageChops.difference(plain.convert('RGB'), Image.new('RGB', plain.size, 'white')).getbbox()
        page.locator('.png-close').click()
        page.get_by_role('button', name='Personalisieren', exact=True).click()
        for key, value in [('x',300),('y',480),('width',480),('height',160),('fontSize',42),('rotation',0)]:
            page.locator('#frame-'+key).fill(str(value)); page.locator('#frame-'+key).press('Tab')
        page.locator('#wishText').fill('Für dich ♥\nAnna & Ben')
        page.locator('#frame-align').select_option('right')
        snapshot = page.evaluate('JSON.stringify({current:personal.current,dirty:personal.dirty,drafts:personal.drafts,map:localStorage.getItem(MAP_KEY),favorites})')
        image_requests.clear()
        page.locator('[data-png-export="current"]').click(); ready(); composed = download_png()
        assert page.evaluate('JSON.stringify({current:personal.current,dirty:personal.dirty,drafts:personal.drafts,map:localStorage.getItem(MAP_KEY),favorites})') == snapshot
        chosen = page.evaluate('motifImageData(studio.catalog.find(m=>m.id===personal.current.motifId),{detail:true}).src')
        assert any(url.endswith(chosen.removeprefix('./')) for url in image_requests)
        # Text occupies the expected lower area; no empty or motif-only personal export.
        crop = composed.convert('RGB').crop((0,1680,2400,2400))
        assert ImageChops.difference(crop, Image.new('RGB', crop.size, 'white')).getbbox()
        page.locator('.png-close').click()
        # Actual editor vs PNG text position/alignment, drawn independently at 4x.
        page.evaluate("""() => {const s=document.getElementById('designSurface'),w=s.closest('.composition');document.body.append(w);
            w.style.cssText='position:fixed;left:0;top:0;width:600px;height:600px;max-width:none;padding:0!important;margin:0;border:0;border-radius:0;z-index:10000';
            s.style.cssText='width:600px;height:600px;max-width:none;position:relative;margin:0;border:0;border-radius:0';transformFit(s);transformSelect();
            scrollTo({top:0,left:0,behavior:'instant'}); }""")
        # Mobile viewport cannot show 600px; capture at a temporary fixed desktop viewport.
        page.set_viewport_size({'width':800,'height':800})
        page.evaluate('() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
        ref = Image.open(io.BytesIO(page.screenshot(clip={'x':0,'y':0,'width':600,'height':600}, animations='disabled'))).convert('RGB').resize((2400,2400),Image.Resampling.LANCZOS)
        difference = ImageChops.difference(ref.crop((0,1680,2400,2400)), composed.convert('RGB').crop((0,1680,2400,2400)))
        mean = sum(ImageStat.Stat(difference).mean)/3
        assert mean < 5, ('Text position differs from editor', width, mean)
        page.evaluate("document.body.lastElementChild.remove()")
        page.set_viewport_size({'width':width,'height':height})
        # Re-render after the isolated reference screenshot, then test rotation and map.
        page.evaluate('personalEditor()')
        page.locator('#frame-y').fill('320');page.locator('#frame-y').press('Tab')
        page.locator('#frame-rotation').fill('45');page.locator('#frame-rotation').press('Tab')
        page.locator('[data-png-export="current"]').click();ready();download_png();page.locator('.png-close').click()
        page.locator('#saveDraft').click();page.wait_for_selector('[data-edit]')
        stored = page.evaluate('localStorage.getItem(MAP_KEY)')
        page.locator('.draft-card [data-png-export]').click();ready();download_png()
        assert page.evaluate('localStorage.getItem(MAP_KEY)') == stored
        page.locator('.png-close').click()
        # Legacy drafts are read/exported without migration or writing local storage.
        for version in [1,2]:
            data=page.evaluate('inquiryClone(personal.drafts[0])');data['layoutVersion']=version;data.pop('textFrame',None)
            if version==2:data['transform']={'x':.5,'y':.75,'scale':1,'rotation':-15}
            page.evaluate('d=>{personal.drafts=[d];mapRender()}',data)
            page.locator('.draft-card [data-png-export]').click();ready();download_png();page.locator('.png-close').click()
            assert page.evaluate('localStorage.getItem(MAP_KEY)') == stored
        # No silent fallback export when original font or motif is missing.
        page.locator('.draft-card [data-edit]').click()
        page.evaluate("document.fonts.clear()")
        page.locator('[data-png-export="current"]').click()
        page.wait_for_function('() => document.querySelector(".png-status").textContent.includes("Schrift")')
        assert not page.locator('.png-download').is_visible();page.locator('.png-close').click()
        page.evaluate("async bytes=>{document.fonts.add(await new FontFace('Montserrat',new Uint8Array(bytes)).load())}",FONT)
        context.route('**/assets/motifs/**/*.webp', lambda r: r.fulfill(status=404, body='missing'))
        page.locator('[data-png-export="current"]').click()
        page.wait_for_function('() => document.querySelector(".png-status").textContent.includes("Motivbild")')
        assert not page.locator('.png-download').is_visible();page.locator('.png-close').click()
        # Confirmed consultation reset still works after removing the old form nodes.
        page.once('dialog',lambda d:d.accept());page.locator('.consultation-reset').click()
        page.wait_for_function('() => personal.current===null && personal.drafts.length===0 && favorites.length===0')
        assert not errors, errors
        assert not posts, posts
        print(f'PASS {width}px {"touch emulation" if touch else "mouse"}: motif/editor/map PNG 2400², opaque white, detail source, text pixel check {mean:.3f}/255, rotation, v1/v2, unchanged storage, missing assets blocked, reset; zero POSTs',flush=True)
        context.close()
    browser.close()
server.shutdown()
