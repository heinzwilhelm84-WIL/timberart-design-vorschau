"""Pointer/touch selection lifecycle, clean previews and preserved geometry."""
import functools,http.server,os,pathlib,shutil,threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
URL='http://127.0.0.1:'+str(server.server_port)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,mode in [(1440,1000,'mouse'),(820,1180,'touch'),(390,844,'touch')]:
  context=browser.new_context(viewport={'width':width,'height':height},has_touch=mode=='touch',is_mobile=mode=='touch')
  context.route('https://**/*',lambda route:route.abort())
  page=context.new_page();errors=[];posts=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  context.on('request',lambda r:posts.append(r.url) if r.method!='GET' else None)
  def ready():page.wait_for_function('() => typeof studio!=="undefined" && studio.ready')
  def model():return page.evaluate('({...personal.current.transform})')
  def position_stage():page.evaluate("() => {const s=document.getElementById('designSurface');window.scrollTo({top:s.getBoundingClientRect().top+scrollY-230,behavior:'instant'})}")
  def activate(selector):
   locator=page.locator(selector);locator.scroll_into_view_if_needed();box=locator.bounding_box()
   x,y=box['x']+box['width']/2,box['y']+box['height']/2
   if mode=='mouse':page.mouse.click(x,y)
   else:page.touchscreen.tap(x,y)
  def text_tap():position_stage();activate('.design-text-object')
  def background_tap():
   position_stage();box=page.locator('#designSurface').bounding_box();x,y=box['x']+box['width']*.04,box['y']+box['height']*.15
   if mode=='mouse':page.mouse.click(x,y)
   else:page.touchscreen.tap(x,y)
  def selected(expected):
   page.wait_for_function('want => document.getElementById("designSurface").classList.contains("text-is-selected")===want',arg=expected)
   assert page.locator('.transform-handle:visible').count()==(2 if expected else 0)
   assert page.locator('#transformControls').is_visible()==expected
   assert page.locator('.design-text-object').get_attribute('aria-pressed')==str(expected).lower()
   background=page.locator('#designSurface').evaluate('el=>getComputedStyle(el).backgroundImage')
   border=page.locator('.design-text-object').evaluate('el=>getComputedStyle(el).borderTopColor')
   assert (background!='none')==expected
   assert (border!='rgba(0, 0, 0, 0)')==expected
  page.goto(URL);ready();page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click()
  page.locator('#wishText').fill('Für Anna\nVon Herzen');selected(False)
  initial=model()
  for _ in range(3):
   text_tap();selected(True);background_tap();selected(False);assert model()==initial
  # An outside field/button must receive the very first tap despite toolbar collapse.
  text_tap();selected(True);activate('#wishText');page.locator('#wishText').fill('Erster Tap funktioniert');selected(False)
  assert page.evaluate('personal.current.text')=='Erster Tap funktioniert'
  text_tap();selected(True);activate('[data-personal-font="pacifico"]');selected(False)
  assert page.evaluate('personal.current.fontId')=='pacifico'
  text_tap();activate('#textX');page.locator('#textX').fill('53');page.locator('#textX').press('Tab');selected(True)
  page.locator('#textScale').fill('125');page.locator('#textRotation').fill('-24');selected(True)
  # Drag with real input, and keep selection after releasing a captured pointer.
  position_stage();box=page.locator('.design-text-object').bounding_box();start=(box['x']+box['width']/2,box['y']+box['height']/2);end=(start[0]-15,start[1]-15)
  before=model()
  if mode=='mouse':
   page.mouse.move(*start);page.mouse.down();page.mouse.move(*end,steps=5);page.mouse.up()
  else:
   cdp=context.new_cdp_session(page)
   cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':start[0],'y':start[1],'id':1}]})
   for n in range(1,6):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':start[0]+(end[0]-start[0])*n/5,'y':start[1]+(end[1]-start[1])*n/5,'id':1}]})
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
  selected(True);assert model()!=before
  transformed=model();background_tap();selected(False);assert model()==transformed
  # A keyboard user can explicitly select and dismiss without changing data.
  page.locator('.design-text-object').focus();selected(True);page.keyboard.press('Enter');selected(True)
  page.keyboard.press('Escape');selected(False);assert model()==transformed
  page.locator('#saveDraft').click()
  assert page.locator('.design-editable,.transform-handle,.transform-controls,.text-is-selected').count()==0
  saved=page.evaluate('personal.drafts[0]');assert saved['transform']==transformed
  assert 'selected' not in saved and 'selection' not in saved
  page.reload();ready();page.locator('[data-view="map"]').click();page.locator('[data-edit]').click();selected(False)
  raw=page.evaluate('localStorage.getItem(MAP_KEY)');assert not page.evaluate('personal.dirty')
  text_tap();selected(True);background_tap();selected(False)
  assert not page.evaluate('personal.dirty') and model()==transformed
  assert page.evaluate('localStorage.getItem(MAP_KEY)')==raw
  # Preview cards and the comparison never expose editing tools, even on tap/focus.
  page.locator('[data-view="map"]').click();page.locator('[data-duplicate]').click()
  activate('.draft-card:first-child .design-text-object')
  assert page.locator('.text-is-selected,.transform-handle,.transform-controls,.design-editable').count()==0
  for box in page.locator('[data-compare]').all():box.check()
  page.locator('#compareDrafts').click();activate('.comparison-grid article:first-child .design-text-object')
  assert page.locator('.text-is-selected,.transform-handle,.transform-controls,.design-editable').count()==0
  assert page.evaluate('personal.drafts[0].transform')==transformed
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  # Explicitly editing a compared draft starts with a clean preview until selected.
  page.locator('[data-compare-edit]').first.click();selected(False);text_tap();selected(True)
  page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Neue Beratung',exact=True).click()
  assert page.evaluate('activeTextSurface===null && personal.current===null && personal.drafts.length===0')
  assert not errors,errors
  assert not posts,posts
  print(f'PASS {width}px {mode}: select/deselect/reselect; first-tap inputs/buttons; tool use; pointer-capture drag; keyboard; no geometry/dirty/storage changes from selection; clean cards/comparison; persistence; reset; no JS errors/POSTs',flush=True)
  context.close()
 browser.close()
server.shutdown()
