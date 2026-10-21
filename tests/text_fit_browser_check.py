"""Measured v3 auto-fit: maximum is persisted, effective size is always derived."""
import functools,http.server,json,os,pathlib,shutil,threading
from playwright.sync_api import sync_playwright, Error, TimeoutError
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,touch in [(1440,1000,False),(820,1180,True),(390,844,True)]:
  ctx=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,is_mobile=touch)
  ctx.route('https://**/*',lambda r:r.abort());page=ctx.new_page();errors=[];posts=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method!='GET' else None)
  page.goto(URL);page.wait_for_function('() => studio.ready');page.locator('[data-view="motifs"]').click()
  page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click()
  def frame():return page.evaluate('({...personal.current.textFrame})')
  def configure(**values):
   for k,v in values.items():
    page.locator('#frame-'+k).fill(str(v));page.locator('#frame-'+k).press('Tab')
  def measure(selector='.design-surface'):
   return page.locator(selector).first.evaluate('''s=>{const t=s.querySelector('.frame-text'),v=s.querySelector('.frame-text-viewport');return {size:parseFloat(t.style.fontSize),width:v.clientWidth,height:v.clientHeight,tw:t.scrollWidth,th:t.scrollHeight,align:getComputedStyle(t).textAlign,text:t.textContent,warning:!s.parentElement.querySelector('.frame-warning').hidden}}''')
  def fits(m):return m['tw']<=m['width'] and m['th']<=m['height']
  configure(x=300,y=300,width=400,height=200,fontSize=48,rotation=0)
  page.locator('#wishText').fill('Text zum Löschen');page.locator('#wishText').fill('')
  assert page.evaluate('personal.current.text')==''
  assert 'Dein Wunschtext' in measure()['text']
  raw='Für Anna ♥\n\nGrüsse & schöne Wünsche!\n';page.locator('#wishText').fill(raw)
  initial=measure();assert fits(initial) and initial['size']<=48
  geometry=frame();configure(width=180,height=100);small=measure()
  assert 8<=small['size']<initial['size'] and fits(small),small
  assert frame()['fontSize']==48 and page.locator('.frame-fit-status').is_visible()
  configure(width=540,height=450);large=measure();assert large['size']==48 and fits(large)
  assert page.locator('#wishText').input_value()==raw and frame()['rotation']==0
  assert page.locator('.frame-fit-status').is_hidden()
  fixed=frame();configure(fontSize=120);assert all(frame()[k]==fixed[k] for k in ['x','y','width','height','rotation'])
  configure(width=190,height=130,fontSize=48)
  for align in ['left','center','right']:
   page.locator('#frame-align').select_option(align)
   for angle in [0,45,90,-47]:
    configure(rotation=angle);m=measure();assert fits(m) and m['align']==align
    assert frame()['fontSize']==48 and page.locator('#wishText').input_value()==raw
  for choice in page.locator('[data-personal-font]').all():
   choice.click();m=measure();assert 8<=m['size']<=48 and (fits(m) or m['warning'])
  # Soft wraps are never serialized; a long word also fits or produces a visible minimum warning.
  page.locator('#wishText').fill('Übergrössenträger'*50)
  assert fits(measure()) or measure()['warning']
  configure(width=32,height=32)
  assert measure()['size']==8 and measure()['warning'] and not fits(measure())
  assert 'kleinsten Schriftgrösse' in page.locator('.frame-warning').inner_text()
  # Actual controls retain requested font geometry and selection does not affect fit.
  configure(width=190,height=130,rotation=45);page.locator('#wishText').fill(raw)
  before=frame();m=measure();page.locator('.frame-v3-object').focus();page.keyboard.press('Enter')
  assert measure()==m and page.locator('.resize-handle:visible').count()==4
  page.locator('[data-frame-handle="se"]').focus();page.keyboard.press('ArrowRight')
  assert frame()['fontSize']==before['fontSize'] and frame()['width']!=before['width']
  before=frame();page.keyboard.press('Escape');assert frame()==before
  # Save/reload/map/compare must derive identical size/content with zero geometry changes.
  target=frame();expected=measure()
  if os.environ.get('TIMBERART_QA_SCREENSHOTS'):
   dest=pathlib.Path(os.environ['TIMBERART_QA_SCREENSHOTS']);dest.mkdir(parents=True,exist_ok=True)
   page.locator('#compositionPreview').screenshot(path=str(dest/f'auto-fit-editor-{width}.png'))
  page.locator('#saveDraft').click();page.wait_for_selector('[data-edit]')
  assert measure()==expected
  raw_storage=page.evaluate('localStorage.getItem(MAP_KEY)')
  assert page.evaluate('personal.drafts[0].textFrame')==target
  assert 'effectiveFontSize' not in raw_storage and 'scale' not in json.dumps(target)
  page.reload();page.wait_for_function('() => studio.ready');page.locator('[data-view="map"]').click()
  assert measure()==expected and page.evaluate('localStorage.getItem(MAP_KEY)')==raw_storage
  page.locator('[data-duplicate]').click();page.wait_for_function('() => personal.drafts.length===2')
  for box in page.locator('[data-compare]').all():box.check()
  page.locator('#compareDrafts').click();assert measure('.comparison-grid .design-surface')==expected
  assert page.locator('.comparison-grid .transform-handle').count()==0
  if os.environ.get('TIMBERART_QA_SCREENSHOTS'):
   page.locator('.comparison-panel').screenshot(path=str(dest/f'auto-fit-vergleich-{width}.png'))
  page.locator('[data-compare-edit]').first.click();assert frame()==target and measure()==expected
  # Landscape re-layout derives the same design-space geometry/effective size.
  page.set_viewport_size({'width':height,'height':width})
  page.wait_for_function('() => document.querySelector(".design-surface").clientWidth===document.querySelector(".design-surface").designWidth')
  assert frame()==target and measure()==expected
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  if page.evaluate('personal.dirty'):page.once('dialog',lambda d:d.accept())
  page.locator('[data-view="map"]').click()
  # Missing catalog motif never deletes or rewrites legacy or v3 data.
  base=page.evaluate('personal.drafts[0]');versions=[]
  for version in [1,2,3]:
   d=dict(base,id=f'missing-{version}',layoutVersion=version,motifId='not-in-catalog')
   if version<3:d.pop('textFrame',None)
   if version==2:d['transform']={'x':.5,'y':.6,'scale':1,'rotation':0}
   versions.append(d)
  stored=json.dumps({'version':2,'epoch':'missing-fixture','drafts':versions})
  page.evaluate('raw=>localStorage.setItem(MAP_KEY,raw)',stored);page.reload();page.wait_for_function('() => studio.ready')
  page.locator('[data-view="map"]').click()
  assert page.locator('.draft-card .asset-warning').count()==3
  assert all('gespeicherte Motiv' in w.inner_text() for w in page.locator('.draft-card .asset-warning').all())
  for index in range(3):
   page.locator('[data-edit]').nth(index).click();assert page.evaluate('personal.current.motifId')=='not-in-catalog'
   assert page.evaluate('localStorage.getItem(MAP_KEY)')==stored
   page.locator('#saveDraft').click();assert page.locator('#editorError').is_visible()
   page.locator('[data-view="map"]').click()
  assert page.evaluate('localStorage.getItem(MAP_KEY)')==stored
  # Real beforeunload cancellation: Chromium/Playwright may leave the reload
  # waiter pending even though the dialog was dismissed. Check actual page state.
  page.locator('[data-edit]').nth(2).click();page.locator('#wishText').fill('Ungespeichert behalten ♥')
  target=page.evaluate('JSON.stringify(personal.current)')
  page.evaluate('window.reloadGuardMarker=true');dialogs=[]
  def cancel_reload(dialog):dialogs.append(dialog.type);dialog.dismiss()
  page.once('dialog',cancel_reload)
  try:page.reload(timeout=3000)
  except Error as error:assert isinstance(error,TimeoutError) or 'ERR_ABORTED' in str(error),str(error)
  assert dialogs==['beforeunload']
  assert page.evaluate('window.reloadGuardMarker')
  assert page.evaluate('JSON.stringify(personal.current)')==target
  assert page.evaluate('localStorage.getItem(MAP_KEY)')==stored
  assert not errors,errors;assert not posts,posts
  print(f'PASS {width}px: auto shrink/grow; manual maximum/geometry; all fonts; Enter/soft wrap; all alignments/rotations; minimum warning; save/reload/map/compare; landscape; missing motif v1/v2/v3 retained; no errors/POSTs',flush=True)
  ctx.close()
 browser.close()
server.shutdown()
