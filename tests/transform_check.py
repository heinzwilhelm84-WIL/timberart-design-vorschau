"""Real mouse/touch browser regression checks; no external service or orders used."""
import functools,http.server,math,os,pathlib,shutil,threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
SCREENSHOTS=os.environ.get('TIMBERART_TEST_SCREENSHOTS')
if SCREENSHOTS:pathlib.Path(SCREENSHOTS).mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
URL='http://127.0.0.1:'+str(server.server_port)

def close(a,b,tolerance=0.0001):assert abs(a-b)<tolerance,(a,b)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,mode in [(1440,1000,'mouse'),(820,1180,'touch'),(390,844,'touch')]:
  context=browser.new_context(viewport={'width':width,'height':height},has_touch=mode=='touch',is_mobile=mode=='touch')
  page=context.new_page();errors=[];outbound=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  context.on('request',lambda r:outbound.append(r.url) if r.method!='GET' else None)
  context.route('https://**/*',lambda route:route.abort())
  cdp=context.new_cdp_session(page)
  def ready():page.wait_for_function('() => typeof studio!=="undefined" && studio.ready')
  def model():return page.evaluate('({...personal.current.transform})')
  def stage():return page.locator('#designSurface').bounding_box()
  def position_stage():
   page.evaluate("() => {let el=document.getElementById('designSurface');window.scrollTo({top:el.getBoundingClientRect().top+scrollY-230,behavior:'instant'})}")
  def xy(selector):
   box=page.locator(selector).bounding_box();return (box['x']+box['width']/2,box['y']+box['height']/2)
  def drag(start,end,cancel=False):
   scroll=page.evaluate('scrollY')
   if mode=='mouse':
    page.mouse.move(*start);page.mouse.down()
    page.mouse.move(*end,steps=8)
    if cancel:page.keyboard.press('Escape')
    page.mouse.up()
   else:
    def send(kind,pt=None):
     cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[] if pt is None else [{'x':pt[0],'y':pt[1],'id':1,'radiusX':4,'radiusY':4,'force':1}]})
    send('touchStart',start)
    for i in range(1,9):send('touchMove',(start[0]+(end[0]-start[0])*i/8,start[1]+(end[1]-start[1])*i/8))
    send('touchCancel' if cancel else 'touchEnd')
   close(page.evaluate('scrollY'),scroll,1)
  def reset():
   page.locator('.design-text-object').focus();page.locator('#resetTransform').click();position_stage()
  def display_matches(selector,t):
   page.wait_for_function("""({selector,t}) => {const el=document.querySelector(selector);if(!el)return false;const s=el.getBoundingClientRect(),o=el.querySelector('.design-text-object').getBoundingClientRect();return Math.abs((o.x+o.width/2-s.x)/s.width-t.x)<.005 && Math.abs((o.y+o.height/2-s.y)/s.height-t.y)<.005}""",arg={'selector':selector,'t':t})
   measured=page.locator(selector).evaluate("el => {const s=el.getBoundingClientRect(),o=el.querySelector('.design-text-object').getBoundingClientRect();return {x:(o.x+o.width/2-s.x)/s.width,y:(o.y+o.height/2-s.y)/s.height}}")
   close(measured['x'],t['x'],0.005);close(measured['y'],t['y'],0.005)
  page.goto(URL);ready();page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click()
  page.locator('#wishText').fill('Für Anna\nVon Herzen');position_stage()
  initial=model();s=stage();start=xy('.design-text-object');drag(start,(start[0]+25,start[1]-30))
  moved=model();close(moved['x'],initial['x']+25/s['width']);close(moved['y'],initial['y']-30/s['height'])
  assert page.evaluate('personal.dirty')
  # Scaling by its direct manipulation handle, not by calling app helpers.
  reset();s=stage();center=(s['x']+s['width']*model()['x'],s['y']+s['height']*model()['y'])
  start=xy('.scale-handle');end=(center[0]+(start[0]-center[0])*1.18,center[1]+(start[1]-center[1])*1.18)
  drag(start,end);close(model()['scale'],1.18,0.015)
  # Rotation handle: rotate the pointer vector 45 degrees.
  reset();s=stage();center=(s['x']+s['width']*model()['x'],s['y']+s['height']*model()['y'])
  start=xy('.rotate-handle');dx,dy=start[0]-center[0],start[1]-center[1];angle=math.pi/4
  end=(center[0]+dx*math.cos(angle)-dy*math.sin(angle),center[1]+dx*math.sin(angle)+dy*math.cos(angle))
  drag(start,end);close(model()['rotation'],45,0.5)
  # Pointer cancellation/escape restores the previous transform.
  before=model();start=xy('.design-text-object');drag(start,(start[0]+20,start[1]-15),cancel=True);assert model()==before
  # Handles remain finger-sized, including at the smallest screen width.
  for handle in ['.rotate-handle','.scale-handle']:
   box=page.locator(handle).bounding_box();assert box['width']>=48 and box['height']>=48
  # Keep the text center inside even after dragging far beyond the stage.
  reset();start=xy('.design-text-object');drag(start,(5,5));bounded=model();assert .06<=bounded['x']<=.94 and .06<=bounded['y']<=.94
  s=stage();box=page.locator('.design-text-object').bounding_box()
  assert box['x']+box['width']>s['x'] and box['x']<s['x']+s['width'] and box['y']+box['height']>s['y'] and box['y']<s['y']+s['height']
  assert page.locator('#transformAdvice').inner_text()
  # Extreme values clamp safely and rotated/scaled text keeps its center on the surface.
  page.locator('#textX').fill('-999');page.locator('#textX').press('Tab');close(model()['x'],.06)
  page.locator('#textY').fill('999');page.locator('#textY').press('Tab');close(model()['y'],.94)
  page.locator('#textScale').fill('300');page.locator('#textRotation').fill('180');close(model()['scale'],3);close(model()['rotation'],-180)
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  reset();page.locator('#textScale').fill('25');close(model()['scale'],.25)
  # Exact controls, keyboard access and their limits.
  page.locator('#textX').fill('43.2');page.locator('#textX').press('Tab')
  page.locator('#textY').fill('67.8');page.locator('#textY').press('Tab')
  page.locator('#textScale').fill('145');page.locator('#textRotation').fill('-32')
  target=model();close(target['x'],.432);close(target['y'],.678);close(target['scale'],1.45);close(target['rotation'],-32)
  page.locator('.design-text-object').focus();page.keyboard.press('ArrowRight');close(model()['x'],.442)
  page.locator('.rotate-handle').focus();page.keyboard.press('ArrowUp');close(model()['rotation'],-31)
  page.locator('.scale-handle').focus();page.keyboard.press('ArrowUp');close(model()['scale'],1.5)
  target=model()
  page.locator('[data-personal-font="pacifico"]').click();assert model()==target
  page.locator('#wishText').fill('Für Anna\nVon Herzen!');assert model()==target
  page.locator('#chooseMotif').click();page.locator('[data-design]').nth(2).click();page.get_by_role('button',name='Personalisieren',exact=True).click();assert model()==target
  # All four values must survive save, reload, editing and duplication.
  page.locator('#saveDraft').click();display_matches('.draft-card .design-surface',target)
  saved=page.evaluate('personal.drafts[0]');assert saved['layoutVersion']==2 and saved['transform']==target
  page.reload();ready();page.locator('[data-view="map"]').click();page.locator('[data-edit]').click();assert model()==target;display_matches('#designSurface',target)
  if mode=='mouse':
   position_stage();start=xy('.design-text-object');page.mouse.move(*start);page.mouse.down();page.mouse.move(start[0]+12,start[1]-8,steps=3)
   assert model()!=target
   page.set_viewport_size({'width':390,'height':1000})
   page.wait_for_function('t => JSON.stringify(personal.current.transform)===JSON.stringify(t)',arg=target)
   page.mouse.up();page.set_viewport_size({'width':width,'height':height})
  # A viewport change must not mutate the transform or change relative geometry.
  page.set_viewport_size({'width':390 if width>390 else 1440,'height':1000});display_matches('#designSurface',target);assert model()==target
  page.set_viewport_size({'width':width,'height':height});display_matches('#designSurface',target)
  page.locator('[data-view="map"]').click();page.locator('[data-duplicate]').click()
  assert page.evaluate('personal.drafts[1].transform')==target
  page.locator('[data-edit]').nth(1).click();page.locator('.design-text-object').focus();page.locator('#textRotation').fill('72')
  assert page.evaluate('personal.drafts[0].transform.rotation')==target['rotation']
  page.locator('#saveDraft').click();assert page.evaluate('personal.drafts[1].transform.rotation')==72
  for box in page.locator('[data-compare]').all():box.check()
  page.locator('#compareDrafts').click();assert page.locator('.comparison-grid .design-surface').count()==2
  display_matches('.comparison-grid article:first-child .design-surface',target)
  assert page.locator('.comparison-grid .transform-handle').count()==0
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  if SCREENSHOTS:page.screenshot(path=str(pathlib.Path(SCREENSHOTS)/f'transform-{width}-{mode}.png'),full_page=True)
  # Read old saved designs without silently altering them, then explicitly upgrade.
  page.evaluate("() => {const d={...personal.drafts[0],layoutVersion:1};delete d.transform;localStorage.setItem(MAP_KEY,JSON.stringify({version:1,epoch:'legacy-test',drafts:[d]}))}")
  page.reload();ready();page.locator('[data-view="map"]').click()
  assert page.locator('.draft-card .design-surface').count()==0
  page.locator('[data-edit]').click();assert model()=={'x':.5,'y':.8,'scale':1,'rotation':0}
  assert 'ältere Entwurf' in page.locator('#personalStatus').inner_text()
  assert page.evaluate('JSON.parse(localStorage.getItem(MAP_KEY)).drafts[0].layoutVersion')==1
  page.locator('#saveDraft').click();assert page.evaluate('personal.drafts[0].id')==saved['id']
  assert page.evaluate('personal.drafts[0].layoutVersion')==2
  # Corrupt transforms cannot overwrite stored data or generate invalid CSS.
  page.evaluate("() => {const d={...personal.drafts[0],transform:{x:null,y:.5,scale:1,rotation:0}};localStorage.setItem(MAP_KEY,JSON.stringify({version:1,epoch:'invalid-test',drafts:[d]}))}")
  page.reload();ready();page.locator('[data-view="map"]').click();assert page.evaluate('personal.blocked')
  page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Neue Beratung',exact=True).click()
  assert page.evaluate('personal.drafts.length===0 && personal.current===null')
  assert not errors,errors
  assert not outbound,outbound
  print(f'PASS {width}px {mode}: real drag/scale/rotate; cancel; bounds; 48px handles; keyboard; exact controls; persistence; responsive geometry; duplicate independence; comparison; legacy migration; invalid data; reset; zero JS errors/POSTs',flush=True)
  context.close()
 browser.close()
server.shutdown()
