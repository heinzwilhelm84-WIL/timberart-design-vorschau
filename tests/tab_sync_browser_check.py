"""Real cross-tab events and shared-lock contention; isolated local-only storage."""
import functools,http.server,os,pathlib,shutil,threading,json
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,touch in [(1440,1000,False),(820,1180,True),(390,844,True)]:
  ctx=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,is_mobile=touch);ctx.route('https://**/*',lambda r:r.abort());errors=[];posts=[]
  ctx.on('page',lambda pg:pg.on('pageerror',lambda e:errors.append(str(e))))
  ctx.on('request',lambda r:posts.append(r.url) if r.method!='GET' else None)
  a=ctx.new_page();b=ctx.new_page()
  def ready(pg):pg.wait_for_function('() => typeof studio!=="undefined" && studio.ready')
  def open_app(pg):pg.goto(URL);ready(pg)
  def start(pg,text):
   pg.locator('[data-view="motifs"]').click();pg.locator('[data-design]').first.click();pg.get_by_role('button',name='Personalisieren',exact=True).click();pg.locator('#wishText').fill(text)
  def saved(pg,count):pg.wait_for_function('n => personal.drafts.length===n && studio.view==="map"',arg=count)
  def marker(pg):pg.evaluate('window.noReloadMarker=true')
  def intact(pg,text):assert pg.evaluate('window.noReloadMarker') and pg.locator('#wishText').input_value()==text
  raw='Nicht verlieren ♥\n\nManueller Umbruch\n'
  # Initially empty shared storage: favoriting must neither reload nor mutate geometry.
  open_app(a);open_app(b);start(a,raw);marker(a);initial=a.evaluate('JSON.stringify(personal.current)')
  b.locator('[data-view="motifs"]').click();b.locator('[data-favorite]').first.click()
  a.wait_for_function('() => favorites.length===1');intact(a,raw);assert a.evaluate('JSON.stringify(personal.current)')==initial
  a.locator('#saveDraft').click();saved(a,1);b.wait_for_function('() => personal.drafts.length===1')
  # Both tabs edit the same base. A remote save must not clobber A's dirty editor.
  a.locator('[data-edit]').click();a.locator('#wishText').fill(raw);marker(a)
  b.locator('[data-view="map"]').click();b.locator('[data-edit]').click();b.locator('#wishText').fill('Stand aus Tab B');b.locator('#saveDraft').click();saved(b,1)
  a.wait_for_function('() => document.getElementById("personalStatus").textContent.includes("anderen Fenster")')
  current=a.evaluate('JSON.stringify(personal.current)');stored=a.evaluate('localStorage.getItem(MAP_KEY)')
  a.locator('#saveDraft').click();a.wait_for_function('() => document.getElementById("editorError").textContent.includes("Nicht gespeichert")');intact(a,raw)
  assert a.evaluate('JSON.stringify(personal.current)')==current and a.evaluate('localStorage.getItem(MAP_KEY)')==stored
  # Declining the discard prompt preserves data; confirmed discard adopts the latest map.
  a.once('dialog',lambda d:d.dismiss());a.locator('[data-view="map"]').click();intact(a,raw)
  a.once('dialog',lambda d:d.accept());a.locator('[data-view="map"]').click();assert a.evaluate('personal.drafts[0].text')=='Stand aus Tab B'
  assert a.evaluate('window.noReloadMarker')
  # Simultaneous saves are serialized. Hold the shared lock to queue both operations.
  a.locator('[data-edit]').click();a.locator('#wishText').fill('A gleichzeitig')
  b.locator('[data-edit]').click();b.locator('#wishText').fill('B gleichzeitig')
  a.evaluate("() => {window.lockHeld=false;navigator.locks.request(MAP_KEY,()=>{window.lockHeld=true;return new Promise(resolve=>window.releaseLock=resolve)})}")
  a.wait_for_function('() => window.lockHeld');a.locator('#saveDraft').click();a.wait_for_function('() => savingDraft');b.locator('#saveDraft').click();b.wait_for_function('() => savingDraft')
  assert a.evaluate('personal.lastRaw')==b.evaluate('personal.lastRaw')
  a.evaluate('window.releaseLock()');saved(a,1)
  b.wait_for_function('() => mapWritesPending===0 && !savingDraft')
  assert b.evaluate('studio.view')=='editor',b.evaluate('({view:studio.view,current:personal.current,drafts:personal.drafts})')
  assert 'Nicht gespeichert' in b.locator('#editorError').inner_text(),b.locator('#editorError').inner_text()
  assert b.locator('#wishText').input_value()=='B gleichzeitig'
  assert json.loads(b.evaluate('localStorage.getItem(MAP_KEY)'))['drafts'][0]['text']=='A gleichzeitig'
  # Typing while a save is queued must survive; next save updates the same draft ID.
  a.locator('[data-edit]').click();a.locator('#wishText').fill('Schnappschuss')
  a.evaluate("() => {window.lockHeld=false;navigator.locks.request(MAP_KEY,()=>{window.lockHeld=true;return new Promise(resolve=>window.releaseLock=resolve)})}");a.wait_for_function('() => lockHeld')
  a.locator('#saveDraft').click();a.locator('#wishText').fill('Weitergetippt');a.evaluate('releaseLock()')
  a.wait_for_function('() => document.getElementById("personalStatus").textContent.includes("neueren Änderungen")');assert a.locator('#wishText').input_value()=='Weitergetippt'
  assert json.loads(a.evaluate('localStorage.getItem(MAP_KEY)'))['drafts'][0]['text']=='Schnappschuss'
  a.locator('#saveDraft').click();saved(a,1)
  # Confirmed reset clears dirty work in the other tab and navigates it once.
  b.once('dialog',lambda d:d.accept());b.locator('[data-view="map"]').click()
  b.once('dialog',lambda d:d.accept())
  with a.expect_navigation(wait_until='domcontentloaded'):b.get_by_role('button',name='Neue Beratung',exact=True).click()
  ready(a);assert a.evaluate('personal.current===null && personal.drafts.length===0 && favorites.length===0')
  # A malformed remote map preserves the editor and raw storage; no silent rewrite.
  start(a,raw);marker(a);b.evaluate("localStorage.setItem(MAP_KEY,'{broken')")
  a.wait_for_function('() => personal.blocked');intact(a,raw);a.locator('#saveDraft').click()
  assert a.evaluate('localStorage.getItem(MAP_KEY)')=='{broken';intact(a,raw)
  # A missing shared-lock API must fail closed, not silently fall back to unsafe writes.
  ctx2=browser.new_context();ctx2.on('page',lambda pg:pg.on('pageerror',lambda e:errors.append(str(e))));ctx2.route('https://**/*',lambda r:r.abort());q=ctx2.new_page();open_app(q);start(q,'Ohne Sperre')
  q.evaluate("() => {window.realLocks=navigator.locks;Object.defineProperty(navigator,'locks',{value:undefined,configurable:true})}");q.locator('#saveDraft').click()
  assert q.locator('#wishText').input_value()=='Ohne Sperre' and q.evaluate('localStorage.getItem(MAP_KEY)') is None
  assert 'Mehrfenster' in q.locator('#editorError').inner_text()
  # Abort the atomic guard after the mirror write: roll back and keep the editor.
  q.evaluate("() => {Object.defineProperty(navigator,'locks',{value:realLocks,configurable:true});window.realAdd=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(){this.transaction.abort();throw Error('simulated guard failure')}}")
  q.locator('#saveDraft').click();q.wait_for_function('() => !savingDraft && mapWritesPending===0')
  assert q.evaluate('localStorage.getItem(MAP_KEY)') is None and q.locator('#wishText').input_value()=='Ohne Sperre'
  q.evaluate('() => {IDBObjectStore.prototype.add=realAdd;}');q.locator('#saveDraft').click();saved(q,1)
  q.locator('[data-edit]').click();q.locator('#wishText').fill('Reset darf bei Fehler nichts verlieren')
  q.evaluate("localStorage.setItem('timberart-favorites','[\"fixture\"]')")
  observer=ctx2.new_page();open_app(observer);observer.locator('[data-view="map"]').click();observer.locator('[data-edit]').click();observer.locator('#wishText').fill('Auch anderer Tab bleibt erhalten');marker(observer)
  observer.evaluate("() => {window.storageEvents=0;addEventListener('storage',()=>storageEvents++)}")
  before_reset=q.evaluate('localStorage.getItem(MAP_KEY)')
  q.evaluate("() => {IDBObjectStore.prototype.add=function(){this.transaction.abort();throw Error('simulated reset failure')}}")
  observer.evaluate("() => {window.resetLockHeld=false;navigator.locks.request(MAP_KEY,()=>{resetLockHeld=true;return new Promise(resolve=>window.releaseResetLock=resolve)})}");observer.wait_for_function('() => resetLockHeld')
  q.once('dialog',lambda d:d.accept());q.get_by_role('button',name='Neue Beratung',exact=True).click();q.wait_for_function('() => resetPending && mapWritesPending===1')
  q.locator('#saveDraft').click();q.wait_for_function('() => !savingDraft')
  assert q.evaluate('mapWritesPending')==1 and q.evaluate('localStorage.getItem(MAP_KEY)')==before_reset
  observer.evaluate('releaseResetLock()');q.wait_for_function('() => mapWritesPending===0 && !resetPending')
  assert q.locator('#wishText').input_value()=='Reset darf bei Fehler nichts verlieren'
  assert q.evaluate('localStorage.getItem(MAP_KEY)')==before_reset
  assert q.evaluate("localStorage.getItem('timberart-favorites')")=='["fixture"]'
  observer.wait_for_function('() => storageEvents>=4');observer.wait_for_timeout(150);intact(observer,'Auch anderer Tab bleibt erhalten')
  ctx2.close()
  # Existing V1/V2 drafts retain their model through cross-tab changes as well.
  for version in [1,2]:
   legacy=browser.new_context();legacy.on('page',lambda pg:pg.on('pageerror',lambda e:errors.append(str(e))));legacy.route('https://**/*',lambda r:r.abort())
   la=legacy.new_page();lb=legacy.new_page();open_app(la);open_app(lb);start(la,raw)
   la.evaluate("version => {personal.current.layoutVersion=version;delete personal.current.textFrame;if(version===2)personal.current.transform=textTransform();personalEditor()}",version)
   la.locator('#wishText').fill(raw);old=la.evaluate('JSON.stringify(personal.current)');marker(la)
   lb.locator('[data-view="motifs"]').click();lb.locator('[data-favorite]').first.click();la.wait_for_function('() => favorites.length===1')
   assert la.evaluate('JSON.stringify(personal.current)')==old;intact(la,raw)
   la.locator('#saveDraft').click();saved(la,1);lb.wait_for_function('() => personal.drafts.length===1')
   la.locator('[data-edit]').click();la.locator('#wishText').fill('Legacy ungespeichert')
   lb.locator('[data-view="map"]').click();lb.locator('[data-duplicate]').click();lb.wait_for_function('() => personal.drafts.length===2')
   la.wait_for_function('() => document.getElementById("personalStatus").textContent.includes("anderen Fenster")');intact(la,'Legacy ungespeichert')
   assert la.evaluate('personal.current.layoutVersion')==version
   la.locator('#saveDraft').click();la.wait_for_function('() => !savingDraft && mapWritesPending===0')
   assert 'Nicht gespeichert' in la.locator('#editorError').inner_text()
   assert all(d['layoutVersion']==version for d in la.evaluate('JSON.parse(localStorage.getItem(MAP_KEY)).drafts'))
   legacy.close()
  assert not errors,errors;assert not posts,posts
  print(f'PASS {width}px: favorite/no reload; conflicting maps preserved; reject stale save; discard/adopt; serialized simultaneous saves; typing during queued save; confirmed reset; malformed map; missing lock fails closed; no errors/POSTs',flush=True)
  ctx.close()
 # Repeated contention on the same base, independent of renderer timing.
 stress=browser.new_context();stress.route('https://**/*',lambda r:r.abort());x=stress.new_page();y=stress.new_page();open_app(x);open_app(y)
 seed=x.evaluate("() => ({version:2,epoch:'stress-consultation',drafts:[{id:'stress',motifId:studio.catalog[0].id,fontId:fontId(FONTS[0]),text:'base',layoutVersion:3,textFrame:copyTextFrame(),createdAt:'test',updatedAt:'test'}]})")
 for cycle in range(30):
  for pg in [x,y]:pg.evaluate('personal.current=null')
  seed['drafts'][0]['text']='base '+str(cycle)
  raw_seed=json.dumps(seed,separators=(',',':'))
  x.evaluate('raw => {localStorage.setItem(MAP_KEY,raw);mapAdopt(parseMap(raw),raw)}',raw_seed)
  y.wait_for_function('raw => personal.lastRaw===raw',arg=raw_seed)
  if cycle==0:assert x.evaluate('async () => await mapWrite(personal.drafts)')  # no-op must not consume the base
  for pg in [x,y]:pg.evaluate("personal.current={text:'protected'}")
  x.evaluate("() => {window.held=false;navigator.locks.request(MAP_KEY,()=>{held=true;return new Promise(resolve=>window.unlock=resolve)})}");x.wait_for_function('() => held')
  for pg,text in [(x,'writer A'),(y,'writer B')]:
   pg.evaluate("text => {window.result=undefined;mapWrite(personal.drafts.map(d=>({...d,text}))).then(ok=>window.result=ok)}",text)
   pg.wait_for_function('() => mapWritesPending===1')
  x.evaluate('unlock()')
  for pg in [x,y]:pg.wait_for_function('() => window.result!==undefined')
  outcomes=[x.evaluate('result'),y.evaluate('result')]
  assert outcomes.count(True)==1,(cycle,outcomes)
  winner='writer A' if outcomes[0] else 'writer B'
  assert x.evaluate('JSON.parse(localStorage.getItem(MAP_KEY)).drafts[0].text')==winner
 metadata=x.evaluate("""async()=>{const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('timberart-map-write-guards',1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});try{return await new Promise((resolve,reject)=>{const s=db.transaction('usedSnapshots').objectStore('usedSnapshots'),k=s.getAllKeys(),v=s.getAll();v.onsuccess=()=>resolve({keys:k.result,values:v.result});v.onerror=()=>reject(v.error)})}finally{db.close()}}""")
 assert len(metadata['keys'])==30 and all(len(k)==64 and all(c in '0123456789abcdef' for c in k) for k in metadata['keys'])
 assert all(v is True for v in metadata['values'])
 stress.close();print('PASS: 30 repeated simultaneous-write races; exactly one commit per shared base; no-op safe; guard contains only opaque hashes/booleans',flush=True)
 browser.close()
server.shutdown()
