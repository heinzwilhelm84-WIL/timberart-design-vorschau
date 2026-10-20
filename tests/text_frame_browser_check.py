"""V3 user-visible layout/persistence contracts; isolated browser storage, no services."""
import functools,http.server,json,math,os,pathlib,shutil,threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
URL=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,touch in [(1440,1000,False),(820,1180,True),(390,844,True)]:
  ctx=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,is_mobile=touch)
  ctx.route('https://**/*',lambda r:r.abort())
  page=ctx.new_page();errors=[];posts=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method!='GET' else None)
  def ready():page.wait_for_function('() => studio.ready')
  def model():return page.evaluate('({...personal.current.textFrame})')
  def field(name,value):page.locator('#frame-'+name).fill(str(value));page.locator('#frame-'+name).press('Tab')
  def metrics(selector='.frame-v3-object'):
   return page.locator(selector).first.evaluate('''o=>{const t=o.querySelector('.frame-text'),v=o.querySelector('.frame-text-viewport'),s=getComputedStyle(t);return {width:o.offsetWidth,height:o.offsetHeight,innerWidth:v.clientWidth,innerHeight:v.clientHeight,fontSize:s.fontSize,lineHeight:s.lineHeight,align:s.textAlign,textHeight:t.scrollHeight,transform:o.style.transform,text:o.querySelector('.frame-text-content').textContent}}''')
  def activate_text():
   el=page.locator('#designSurface .frame-v3-object');el.scroll_into_view_if_needed();b=el.bounding_box()
   if touch:page.touchscreen.tap(b['x']+b['width']/2,b['y']+b['height']/2)
   else:page.mouse.click(b['x']+b['width']/2,b['y']+b['height']/2)
  page.goto(URL);ready();page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click()
  assert page.evaluate('personal.current.layoutVersion')==3
  assert page.evaluate("!('transform' in personal.current) && !('scale' in personal.current.textFrame)")
  assert page.locator('.scale-handle,#textScale').count()==0
  if width==1440:
   # A local test font substitutes for the unavailable Google font to exercise
   # asynchronous metric changes. This is not a test of Google Fonts delivery.
   font=pathlib.Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
   assert font.is_file(),'Local asynchronous font fixture is required'
   page.evaluate("() => {window.originalFontLoad=document.fonts.load.bind(document.fonts);window.fontResolvers=[];document.fonts.load=()=>new Promise(resolve=>fontResolvers.push(resolve))}")
   page.locator('#wishText').fill('Schrift lädt später: vollständiger Text und Rahmen bleiben erhalten.')
   before=model()
   page.evaluate('''async bytes => {const font=await new FontFace('Montserrat',new Uint8Array(bytes)).load();document.fonts.add(font);document.fonts.load=window.originalFontLoad;fontResolvers.forEach(resolve=>resolve([font]));}''',list(font.read_bytes()))
   page.wait_for_function("document.getElementById('fontStatus').textContent===''")
   assert model()==before
   assert page.evaluate('document.fonts.check(\'400 24px "Montserrat"\')')
  field('height',400);field('y',300);field('fontSize',24)
  page.locator('#wishText').fill('Automatische Umbrüche sollen sich mit der Rahmenbreite ändern. '*3)
  field('width',200);narrow=metrics();before=model()
  field('width',540);wide=metrics();assert wide['textHeight']<narrow['textHeight']
  assert model()['fontSize']==before['fontSize'] and model()['height']==before['height']
  old=model();field('fontSize',36);assert model()['width']==old['width'] and model()['height']==old['height']
  assert 8 <= float(metrics()['fontSize'].removesuffix('px')) <= 36 and 'scale' not in metrics()['transform']
  assert model()['fontSize']==36  # requested maximum remains independent
  old=model();field('width',0);assert model()==old
  assert float(page.locator('#frame-width').input_value())==old['width']
  assert 'wiederhergestellt' in page.locator('.frame-control-error').inner_text()
  # Actual Enter keys, including an empty and a final blank line; never store soft wraps.
  page.locator('#wishText').fill('Erste Zeile');page.locator('#wishText').press('End');page.locator('#wishText').press('Enter')
  page.locator('#wishText').press('Enter');page.locator('#wishText').press_sequentially('Letzte Zeile');page.locator('#wishText').press('Enter')
  raw='Erste Zeile\n\nLetzte Zeile\n';assert page.evaluate('personal.current.text')==raw
  field('fontSize',24);field('width',540);h=metrics()['textHeight']
  assert h>=4*float(metrics()['lineHeight'].removesuffix('px'))-2
  field('width',200);field('width',540);assert page.evaluate('personal.current.text')==raw
  for align in ['left','center','right']:
   page.locator('#frame-align').select_option(align);assert metrics()['align']==align and model()['align']==align
  # Long words wrap rather than expanding the frame.
  field('width',160);page.locator('#wishText').fill('ABCDEFGHIJKLMNOPQRSTUVWXYZ'*100)
  assert metrics()['innerWidth']==136 and metrics()['textHeight']>100
  assert page.locator('.frame-warning').is_visible()
  field('width',420);field('height',140);field('fontSize',32);field('y',480)
  page.locator('#wishText').fill('Für dich ♥\nVon Herzen')
  original=metrics();activate_text();assert page.locator('.rotate-handle').is_visible()
  assert metrics()==original  # Selection cannot change content width, border or wrapping.
  page.locator('#wishText').click();assert page.locator('.rotate-handle').is_hidden()
  field('rotation',31);assert model()['rotation']==31
  # Native mouse/touch drag retains dimensions and font; cancel restores exact geometry.
  page.evaluate("() => {const s=document.getElementById('designSurface');scrollTo({top:s.getBoundingClientRect().top+scrollY-230,behavior:'instant'})}")
  b=page.locator('#designSurface .frame-v3-object').bounding_box();start=(b['x']+b['width']/2,b['y']+b['height']/2);before=model()
  if touch:
   cdp=ctx.new_cdp_session(page);cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':start[0],'y':start[1],'id':1}]})
   cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':start[0]+15,'y':start[1]-15,'id':1}]})
   cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
  else:
   page.mouse.move(*start);page.mouse.down();page.mouse.move(start[0]+15,start[1]-15,steps=5);page.mouse.up()
  moved=model();assert moved['x']!=before['x'] and moved['y']!=before['y']
  assert all(moved[k]==before[k] for k in ['width','height','fontSize','rotation'])
  def drag(start,end,cancel=False):
   if touch:
    c=ctx.new_cdp_session(page)
    c.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':start[0],'y':start[1],'id':1}]})
    for n in range(1,6):c.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':start[0]+(end[0]-start[0])*n/5,'y':start[1]+(end[1]-start[1])*n/5,'id':1}]})
    c.send('Input.dispatchTouchEvent',{'type':'touchCancel' if cancel else 'touchEnd','touchPoints':[]});c.detach()
   else:
    page.mouse.move(*start);page.mouse.down();page.mouse.move(*end,steps=5)
    if cancel:page.keyboard.press('Escape')
    page.mouse.up()
  # Real rotation through the handle; only rotation may change.
  surface=page.locator('#designSurface').bounding_box();f=model()
  center=(surface['x']+surface['width']*f['x']/600,surface['y']+surface['height']*f['y']/600)
  handle=page.locator('.rotate-handle').bounding_box();start=(handle['x']+handle['width']/2,handle['y']+handle['height']/2)
  dx,dy=start[0]-center[0],start[1]-center[1];a=math.pi/4
  drag(start,(center[0]+dx*math.cos(a)-dy*math.sin(a),center[1]+dx*math.sin(a)+dy*math.cos(a)))
  assert abs(model()['rotation']-f['rotation']-45)<.6,(model(),f,surface,handle,center,start)
  assert all(model()[k]==f[k] for k in ['x','y','width','height','fontSize'])
  b=page.locator('#designSurface .frame-v3-object').bounding_box();start=(b['x']+b['width']/2,b['y']+b['height']/2);before=model()
  drag(start,(start[0]+12,start[1]-12),cancel=True);assert model()==before
  page.locator('#designSurface .frame-v3-object').focus();page.keyboard.press('ArrowLeft');assert model()['x']<moved['x']
  target=model();editor=metrics();page.locator('#saveDraft').click();page.wait_for_function('() => typeof mapWritesPending!=="undefined" && mapWritesPending===0 && !savingDraft')
  saved=page.evaluate('personal.drafts[0]');assert saved['textFrame']==target and saved['layoutVersion']==3 and 'transform' not in saved
  assert metrics()==editor
  stored=page.evaluate('localStorage.getItem(MAP_KEY)');assert json.loads(stored)['version']==2
  page.reload();ready();page.locator('[data-view="map"]').click();assert metrics()==editor
  assert page.evaluate('localStorage.getItem(MAP_KEY)')==stored
  page.locator('[data-duplicate]').click();page.wait_for_function('() => typeof mapWritesPending!=="undefined" && mapWritesPending===0 && !savingDraft');assert page.evaluate('personal.drafts[1].textFrame')==target
  for box in page.locator('[data-compare]').all():box.check()
  page.locator('#compareDrafts').click()
  assert metrics('.comparison-grid .frame-v3-object')==editor
  assert page.locator('.comparison-grid .transform-handle').count()==0
  page.locator('[data-compare-edit]').nth(1).click();field('width',350);assert page.evaluate('personal.drafts[0].textFrame')==target
  field('height',32);page.locator('#wishText').fill(('Langer Text ohne Zeichenlimit. '*30)+'\nNeue Zeile')
  assert page.locator('.frame-warning').is_visible()
  text=page.locator('#wishText').input_value();page.locator('#saveDraft').click();page.wait_for_function('() => typeof mapWritesPending!=="undefined" && mapWritesPending===0 && !savingDraft')
  assert page.evaluate('personal.drafts[1].text')==text
  assert page.locator('.draft-card').nth(1).locator('.frame-warning').is_visible()
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  # Mixed maps: opening/cancelling legacy v1/v2 must not migrate or rewrite storage.
  base=page.evaluate('personal.drafts[0]');base.pop('textFrame')
  v1=dict(base,id='v1',layoutVersion=1);v2=dict(base,id='v2',layoutVersion=2,transform={'x':.65,'y':.74,'scale':1.3,'rotation':23})
  v3=page.evaluate('personal.drafts[0]');mixed=json.dumps({'version':2,'epoch':'mixed','drafts':[v1,v2,v3]})
  page.evaluate('(raw)=>localStorage.setItem(MAP_KEY,raw)',mixed);page.reload();ready();page.locator('[data-view="map"]').click()
  for index,version in [(0,1),(1,2)]:
   page.locator('[data-edit]').nth(index).click()
   assert page.evaluate('personal.current.layoutVersion')==version and not page.evaluate('personal.dirty')
   assert page.evaluate('localStorage.getItem(MAP_KEY)')==mixed
   assert page.locator('.frame-controls').count()==0
   if version==2:
    legacy=page.locator('.design-text-object').evaluate("o=>({w:o.offsetWidth,inner:o.querySelector('.composition-text').clientWidth,font:getComputedStyle(o.querySelector('.composition-text')).fontSize})")
    assert legacy=={'w':420,'inner':392,'font':'40px'}
   page.locator('[data-view="map"]').click()
  assert page.evaluate('personal.drafts')==[v1,v2,v3]
  # Saving one legacy entry in a mixed map must preserve every v3 field and v1/v2.
  page.locator('[data-edit]').nth(1).click();page.locator('#wishText').fill('Legacy bleibt editierbar')
  page.locator('#saveDraft').click();page.wait_for_function('() => typeof mapWritesPending!=="undefined" && mapWritesPending===0 && !savingDraft')
  assert page.evaluate('personal.drafts[1].layoutVersion')==2
  assert page.evaluate('personal.drafts[1].transform')==v2['transform']
  assert page.evaluate('personal.drafts[2]')==v3 and page.evaluate('personal.drafts[0]')==v1
  # Corruption or unknown versions protect the complete raw map, including old drafts.
  for broken in [dict(v3,textFrame=dict(v3['textFrame'],width=None)),dict(v3,textFrame=dict(v3['textFrame'],align='justify')),dict(v3,transform={}),dict(v3,layoutVersion=99)]:
   bad=json.dumps({'version':2,'epoch':'bad','drafts':[v1,broken]})
   page.evaluate('(raw)=>localStorage.setItem(MAP_KEY,raw)',bad);page.reload();ready()
   assert page.evaluate('personal.blocked') and page.evaluate('localStorage.getItem(MAP_KEY)')==bad
  for version in [1,99]:
   bad=json.dumps({'version':version,'epoch':'unsupported','drafts':[v3]})
   page.evaluate('(raw)=>localStorage.setItem(MAP_KEY,raw)',bad);page.reload();ready()
   assert page.evaluate('personal.blocked') and page.evaluate('localStorage.getItem(MAP_KEY)')==bad
  assert not errors,errors;assert not posts,posts
  print(f'PASS {width}px: v3 independent dimensions/font; wrap/unwarp; Enter/blank lines; align; selection; mouse/touch move; editor/map/compare equality; roundtrip; duplicate isolation; overflow warnings; mixed v1/v2/v3; corrupt data protection; no JS errors/POSTs',flush=True)
  ctx.close()
 browser.close()
server.shutdown()
