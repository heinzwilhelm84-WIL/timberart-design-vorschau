"""Real pointer resize/rotate/move on v3; local-only and isolated browser storage."""
import functools,http.server,math,os,pathlib,shutil,threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,touch in [(1440,1000,False),(820,1180,True),(390,844,True)]:
  if os.environ.get('TIMBERART_RESIZE_WIDTH') and width!=int(os.environ['TIMBERART_RESIZE_WIDTH']):continue
  ctx=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,is_mobile=touch)
  ctx.route('https://**/*',lambda r:r.abort());page=ctx.new_page();errors=[];posts=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:posts.append(r.url) if r.method!='GET' else None)
  page.goto(f'http://127.0.0.1:{server.server_port}');page.wait_for_function('() => studio.ready')
  page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click()
  def model():return page.evaluate('({...personal.current.textFrame})')
  def configure(**values):
   # Set via the same public input path; gestures themselves are native pointer input.
   for key,value in values.items():page.locator('#frame-'+key).fill(str(value));page.locator('#frame-'+key).press('Tab')
  def scroll():page.evaluate("() => {const s=document.getElementById('designSurface');scrollTo({top:s.getBoundingClientRect().top+scrollY-230,behavior:'instant'})}")
  def center(selector):
   b=page.locator(selector).bounding_box();return (b['x']+b['width']/2,b['y']+b['height']/2)
  def select():
   scroll();x,y=center('.frame-v3-object')
   if touch:page.touchscreen.tap(x,y)
   else:page.mouse.click(x,y)
  def drag(start,end,cancel=False,live=None):
   if touch:
    c=ctx.new_cdp_session(page);c.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':start[0],'y':start[1],'id':1}]})
    for n in range(1,6):c.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':start[0]+(end[0]-start[0])*n/5,'y':start[1]+(end[1]-start[1])*n/5,'id':1}]})
    if live:live()
    c.send('Input.dispatchTouchEvent',{'type':'touchCancel' if cancel else 'touchEnd','touchPoints':[]});c.detach()
   else:
    page.mouse.move(*start);page.mouse.down();page.mouse.move(*end,steps=5)
    if live:live()
    if cancel:page.keyboard.press('Escape')
    page.mouse.up()
  def anchor(f,sx,sy):
   a=math.radians(f['rotation']);return (f['x']-math.cos(a)*sx*f['width']/2+math.sin(a)*sy*f['height']/2,f['y']-math.sin(a)*sx*f['width']/2-math.cos(a)*sy*f['height']/2)
  def text_height():return page.locator('.frame-text').evaluate('e=>e.scrollHeight')
  handles={'nw':(-1,-1),'n':(0,-1),'ne':(1,-1),'e':(1,0),'se':(1,1),'s':(0,1),'sw':(-1,1),'w':(-1,0)}
  raw='Feine Linien und persönliche Wünsche bleiben erhalten. '*4+'\nFeste zweite Zeile\n'
  page.locator('#wishText').fill(raw);page.locator('#frame-align').select_option('right')
  for rotation in [0,31,90,-47]:
   for handle,(sx,sy) in handles.items():
    page.locator('#frame-align').select_option({0:'left',31:'center',90:'right',-47:'right'}[rotation])
    configure(x=300,y=300,width=240,height=160,fontSize=28,rotation=rotation);select()
    selector=f'[data-frame-handle="{handle}"]';start=center(selector)
    # Every handle centre must be reachable, even with rotated/small frames.
    hit=page.evaluate('p=>document.elementFromPoint(...p).closest("[data-frame-handle]")?.dataset.frameHandle',list(start));assert hit==handle,(width,rotation,handle,hit,start,page.evaluate('p=>document.elementFromPoint(...p).outerHTML',list(start)))
    before=model();surface=page.locator('#designSurface').bounding_box();scale=surface['width']/600;a=math.radians(rotation)
    dx=(math.cos(a)*sx*36-math.sin(a)*sy*24)*scale;dy=(math.sin(a)*sx*36+math.cos(a)*sy*24)*scale
    drag(start,(start[0]+dx,start[1]+dy));after=model()
    assert abs(after['width']-(before['width']+(36 if sx else 0)))<4,(width,rotation,handle,before,after)
    assert abs(after['height']-(before['height']+(24 if sy else 0)))<4,(width,rotation,handle,before,after)
    for k in ['fontSize','rotation','align','padding','lineHeight']:assert after[k]==before[k]
    assert all(abs(a-b)<1e-6 for a,b in zip(anchor(before,sx,sy),anchor(after,sx,sy)))
    assert page.locator('#wishText').input_value()==raw
    # Pull the same edge/corner back inwards; no hidden font-size coupling.
    start=center(selector);drag(start,(start[0]-dx,start[1]-dy));shrunk=model()
    assert abs(shrunk['width']-before['width'])<5 and abs(shrunk['height']-before['height'])<5
    assert shrunk['fontSize']==before['fontSize'] and shrunk['align']==before['align']
  page.locator('#frame-align').select_option('right')
  # Reflow occurs while the pointer is still down, and widening removes soft breaks.
  configure(x=300,y=300,width=210,height=300,fontSize=26,rotation=31);select();old_height=text_height()
  start=center('[data-frame-handle="e"]');surface=page.locator('#designSurface').bounding_box();scale=surface['width']/600;a=math.radians(31)
  def live():
   assert text_height()<old_height
   assert model()['fontSize']==26 and model()['align']=='right'
   assert page.locator('#wishText').input_value()==raw
  drag(start,(start[0]+math.cos(a)*240*scale,start[1]+math.sin(a)*240*scale),live=live)
  resized=model();configure(fontSize=34);assert model()['width']==resized['width'] and model()['height']==resized['height']
  # Rotation after resizing changes no dimensions or font; next resize uses new axes.
  select();before=model();b=page.locator('#designSurface').bounding_box();origin=(b['x']+before['x']/600*b['width'],b['y']+before['y']/600*b['height']);start=center('.rotate-handle');dx=start[0]-origin[0];dy=start[1]-origin[1];a=math.radians(35)
  drag(start,(origin[0]+dx*math.cos(a)-dy*math.sin(a),origin[1]+dx*math.sin(a)+dy*math.cos(a)))
  assert abs(model()['rotation']-before['rotation']-35)<1.5,(width,before,model())
  assert all(model()[k]==before[k] for k in ['width','height','fontSize','x','y'])
  start=center('[data-frame-handle="s"]');before=model();a=math.radians(before['rotation']);drag(start,(start[0]-math.sin(a)*20,start[1]+math.cos(a)*20));assert model()['height']>before['height'] and model()['fontSize']==34
  # Dragging + cancellation restores the entire snapshot (Escape / touchCancel).
  select();before=model();start=center('[data-frame-handle="nw"]');drag(start,(start[0]+20,start[1]+15),cancel=True);assert model()==before
  select();start=center('.frame-v3-object');before=model();drag(start,(start[0]+10,start[1]-10));assert model()['x']!=before['x'] and all(model()[k]==before[k] for k in ['width','height','fontSize','rotation'])
  # Tiny/edge frames keep nonoverlapping, visible mouse/touch controls and warn.
  for x,y,rotation in [(36,36,31),(564,564,-47),(300,300,90)]:
   configure(x=x,y=y,width=32,height=32,rotation=rotation);scroll()
   page.locator('.frame-v3-object').focus();page.keyboard.press('Enter')
   assert page.locator('.frame-warning').is_visible()
   for handle in handles:
    start=center(f'[data-frame-handle="{handle}"]');assert page.evaluate('p=>document.elementFromPoint(...p).closest("[data-frame-handle]")?.dataset.frameHandle',list(start))==handle,(width,x,y,handle)
  # Shrinking height visibly warns; growing again clears the warning, with full text.
  configure(x=300,y=300,width=300,height=200,rotation=0,fontSize=26)
  page.locator('#wishText').fill('Erste Zeile\nZweite Zeile');select()
  assert page.locator('.frame-warning').is_hidden()
  b=page.locator('#designSurface').bounding_box();scale=b['width']/600;start=center('[data-frame-handle="s"]')
  drag(start,(start[0],start[1]-150*scale));assert page.locator('.frame-warning').is_visible()
  start=center('[data-frame-handle="s"]');drag(start,(start[0],start[1]+150*scale));assert page.locator('.frame-warning').is_hidden()
  page.locator('#wishText').fill(raw);configure(fontSize=34)
  # Keyboard resize, saved geometry, reload and identical map/compare rendering.
  configure(x=300,y=300,width=300,height=180,rotation=31);select();page.locator('[data-frame-handle="e"]').focus();before=model();page.keyboard.press('ArrowRight');assert model()['width']>before['width'] and model()['fontSize']==before['fontSize']
  target=model();assert abs(float(page.locator('#frame-width').input_value())-target['width'])<=.051
  page.locator('#frame-width').focus();page.locator('#frame-width').press('Tab');assert model()==target
  page.locator('#saveDraft').click();page.wait_for_function('() => typeof mapWritesPending!=="undefined" && mapWritesPending===0 && !savingDraft');assert page.evaluate('personal.drafts[0].textFrame')==target
  page.reload();page.wait_for_function('() => studio.ready');page.locator('[data-view="map"]').click();assert page.evaluate('personal.drafts[0].textFrame')==target
  assert page.locator('.resize-handle,.frame-guide-lines').count()==0
  page.locator('[data-duplicate]').click();page.wait_for_function('() => typeof mapWritesPending!=="undefined" && mapWritesPending===0 && !savingDraft')
  for box in page.locator('[data-compare]').all():box.check()
  page.locator('#compareDrafts').click();assert page.locator('.resize-handle,.frame-guide-lines').count()==0
  for el in page.locator('.frame-v3-object').all():assert abs(el.evaluate('e=>parseFloat(e.style.width)')-target['width'])<.001
  page.locator('[data-compare-edit]').first.click();assert model()==target and page.locator('#wishText').input_value()==raw
  assert page.locator('.resize-handle:visible').count()==0
  select();assert page.locator('.resize-handle:visible').count()==8
  if os.environ.get('TIMBERART_FRAME_SCREENSHOTS'):page.screenshot(path=f'/tmp/timberart-frame-{width}.png')
  page.locator('#wishText').click();assert page.locator('.resize-handle:visible').count()==0
  assert not errors,errors;assert not posts,posts
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  print(f'PASS {width}px: 8 handles x 4 rotations; fixed anchors/font/alignment; live reflow; rotate-resize-move-font sequence; cancel; edge/tiny controls; keyboard; save/reopen/map/compare; selection; no POSTs/errors',flush=True)
  ctx.close()
 browser.close()
server.shutdown()
