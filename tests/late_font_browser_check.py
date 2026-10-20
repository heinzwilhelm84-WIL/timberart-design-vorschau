"""Controlled local font metrics after the real four-second UI timeout."""
import functools,http.server,os,pathlib,shutil,threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
FONT=pathlib.Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
assert FONT.is_file(),'Local test font is required'
FONT_BYTES=list(FONT.read_bytes())
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,touch in [(1440,1000,False),(820,1180,True),(390,844,True)]:
  for view in ['editor','map']:
   for grows in [True,False]:
    ctx=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,is_mobile=touch);ctx.route('https://**/*',lambda r:r.abort());page=ctx.new_page();errors=[];posts=[]
    page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method!='GET' else None)
    page.goto(URL);page.wait_for_function('() => studio.ready');page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click()
    text=('iiiiiiiiii '*10 if grows else 'WWWWWWWWWW '*5)+'\n'
    page.locator('#wishText').fill(text)
    def field(k,v):page.locator('#frame-'+k).fill(str(v));page.locator('#frame-'+k).press('Tab')
    field('width',300);field('height',500);field('fontSize',30);field('y',300)
    page.evaluate('''async bytes=>{const f=await new FontFace('ReviewProbe',new Uint8Array(bytes)).load();document.fonts.add(f)}''',FONT_BYTES)
    heights=page.locator('.frame-text').evaluate("e=>{const normal=e.scrollHeight,old=e.style.fontFamily;e.style.fontFamily='ReviewProbe';const loaded=e.scrollHeight;e.style.fontFamily=old;return {normal,loaded}}")
    assert (heights['loaded']>heights['normal'])==grows,heights
    h=(heights['normal']+heights['loaded'])/2+24;assert h<576,heights;field('height',h)
    if view=='map':
     page.locator('#saveDraft').click();page.wait_for_selector('.draft-card');page.locator('[data-duplicate]').click();page.wait_for_function('() => personal.drafts.length===2')
     for box in page.locator('[data-compare]').all():box.check()
     page.locator('#compareDrafts').click()
    before=page.evaluate('JSON.stringify({drafts:personal.drafts,current:personal.current,raw:localStorage.getItem(MAP_KEY)})')
    page.evaluate("() => {window.realLoad=document.fonts.load.bind(document.fonts);window.resolvers=[];document.fonts.load=()=>new Promise(resolve=>resolvers.push(resolve));}")
    page.evaluate('personalUpdate()' if view=='editor' else 'mapFontStatus()')
    status='fontStatus' if view=='editor' else 'mapFontStatus'
    page.wait_for_function('id => /lädt noch|laden noch/.test(document.getElementById(id).textContent)',arg=status,timeout=9000)
    assert page.locator('.frame-warning').count()==(1 if view=='editor' else 4)
    assert all(w.is_visible()==(not grows) for w in page.locator('.frame-warning').all())
    page.evaluate('''async bytes=>{const f=await new FontFace('Montserrat',new Uint8Array(bytes)).load();document.fonts.add(f);document.fonts.load=window.realLoad;resolvers.forEach(resolve=>resolve([f]));}''',FONT_BYTES)
    page.wait_for_function('expected => [...document.querySelectorAll(".frame-v3")].every(e=>{const t=e.querySelector(".frame-text"),v=e.querySelector(".frame-text-viewport"),w=e.querySelector(".frame-warning");return (t.scrollHeight>v.clientHeight+1)===expected && !w.hidden===expected})',arg=grows)
    page.wait_for_function('id => document.getElementById(id).textContent===""',arg=status)
    assert page.evaluate('JSON.stringify({drafts:personal.drafts,current:personal.current,raw:localStorage.getItem(MAP_KEY)})')==before
    # Late callbacks from an old editor/map must not recreate it after navigation.
    if view=='editor':page.once('dialog',lambda d:d.accept())
    page.locator('[data-view="home"]').click();page.evaluate("document.fonts.dispatchEvent(new Event('loadingdone'))")
    assert page.evaluate('studio.view')=='home'
    assert not errors,errors;assert not posts,posts
    print(f'PASS {width}px {view} {"overflow appears" if grows else "overflow clears"}: >4s font promise; all visible previews/status refreshed; exact model/storage unchanged; closed view ignored',flush=True);ctx.close()
 # Recovery after an initial failed/absent font, via a CSP-allowed URL fulfilled only from local fixture bytes.
 ctx=browser.new_context();ctx.route('https://**/*',lambda r:r.abort());page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 ctx.route('https://fonts.gstatic.com/timberart-local-fixture.ttf',lambda r:r.fulfill(body=FONT.read_bytes(),content_type='font/ttf',headers={'access-control-allow-origin':'*'}))
 page.goto(URL);page.wait_for_function('() => studio.ready');page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click();page.locator('#wishText').fill('Späterer Schriftversuch')
 page.wait_for_function('() => /nicht verfügbar|nicht geladen/.test(document.getElementById("fontStatus").textContent)')
 page.evaluate("async()=>{window.fontEvents=0;document.fonts.addEventListener('loadingdone',()=>fontEvents++);const f=new FontFace('Montserrat','url(https://fonts.gstatic.com/timberart-local-fixture.ttf)');document.fonts.add(f);await f.load()}")
 page.wait_for_function('() => fontEvents>0 && document.getElementById("fontStatus").textContent===""')
 assert not errors,errors;ctx.close()
 print('PASS: real FontFaceSet loadingdone after initially absent font updates editor status',flush=True)
 browser.close()
server.shutdown()
