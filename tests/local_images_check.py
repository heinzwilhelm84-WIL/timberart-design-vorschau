"""Load every local image under a Pages-style subpath; preserve old customer drafts."""
import functools,http.server,json,os,pathlib,shutil,threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'catalog.json').read_text());BASE=json.loads((ROOT/'data/motifs-baseline.json').read_text())['motifs']
assert [{k:d[k] for k in ['id','name','category']} for d in CAT[:len(BASE)]]==BASE
assert len(CAT)==412 and len({d['category'] for d in CAT})==9
PATHS=[v['url'] for d in CAT for v in d['images']]
assert len(PATHS)==824 and len(set(PATHS))==824
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
 def translate_path(self,path):
  # Exercise real relative links from /timberart-design-vorschau/, not site root.
  self.path=path.removeprefix('/timberart-design-vorschau')
  return super().translate_path(self.path)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
URL=f'http://127.0.0.1:{server.server_port}/timberart-design-vorschau/'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,touch in [(1440,1000,False),(820,1180,True),(390,844,True)]:
  context=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,is_mobile=touch,device_scale_factor=2 if touch else 1)
  context.route('https://**/*',lambda r:r.abort())
  page=context.new_page();errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append((r.method,r.url)))
  page.goto(URL);page.wait_for_function('() => studio.ready')
  assert page.evaluate('FONTS.length')==30
  if width==1440:
   result=page.evaluate('''async paths => {
    let next=0,loaded=0;const failures=[];
    await Promise.all(Array.from({length:6},async()=>{while(next<paths.length){const path=paths[next++];try{
     const response=await fetch(path);if(!response.ok||!response.headers.get('content-type').includes('image/webp'))throw Error('HTTP/MIME');
     const image=new Image();image.src=path;await image.decode();if(!image.naturalWidth)throw Error('decode');loaded++;
    }catch(error){failures.push(path+': '+error.message)}}}));return {loaded,failures};
   }''',PATHS)
   assert result=={'loaded':824,'failures':[]},result
   print('PASS: all 824 WebP files HTTP 200, image/webp and Chromium decode under project subpath')
  # Restore stored IDs and both legacy and transformed designs without migration/reset.
  now='2026-10-19T12:00:00.000Z'
  common={'motifId':CAT[0]['id'],'motifName':CAT[0]['name'],'category':CAT[0]['category'],'text':'Für Anna ♥','fontId':'pacifico','createdAt':now,'updatedAt':now}
  drafts=[dict(common,id='legacy',layoutVersion=1),dict(common,id='positioned',layoutVersion=2,transform={'x':.65,'y':.74,'scale':1.3,'rotation':23})]
  stored=json.dumps({'version':1,'epoch':'existing-customer','drafts':drafts},ensure_ascii=False)
  page.evaluate('''({map,id})=>{localStorage.setItem('timberart-designmappe-v1',map);localStorage.setItem('timberart-favorites',JSON.stringify([id]));}''',{'map':stored,'id':CAT[0]['id']})
  page.reload();page.wait_for_function('() => studio.ready')
  assert page.evaluate('personal.drafts')==drafts
  assert page.evaluate("localStorage.getItem(MAP_KEY)")==stored
  assert page.evaluate('favorites')==[CAT[0]['id']]
  def loaded(selector):
   page.eval_on_selector_all(selector,"els=>els.forEach(el=>el.loading='eager')")
   page.wait_for_function('''selector=>{const imgs=[...document.querySelectorAll(selector)];return imgs.length>0&&imgs.every(i=>i.complete&&i.naturalWidth>0&&i.currentSrc.includes('/timberart-design-vorschau/assets/motifs/')&&i.currentSrc.endsWith('.webp'))}''',arg=selector,timeout=30000)
  loaded('.hero img[data-motif-id]' if page.locator('.hero img[data-motif-id]').count() else '#content img[data-motif-id]')
  page.locator('[data-view="motifs"]').click();assert page.locator('[data-design]').count()==412
  loaded('[data-design] img')
  page.locator('[data-design]').first.click();loaded('#modalImage')
  page.locator('#imageModal .btn-primary').click()
  page.locator('#designOrderModal').wait_for(state='visible')
  assert page.locator('#designLink').get_attribute('href')==CAT[0]['detailUrl']
  page.evaluate('closeDesignOrderForm();closeImageModal()')
  page.locator('[data-view="map"]').click();loaded('.draft-card img')
  for box in page.locator('[data-compare]').all():box.check()
  page.locator('#compareDrafts').click();loaded('.comparison-grid img')
  assert page.locator('.comparison-grid .transform-handle').count()==0
  page.locator('[data-edit]').nth(1).click();loaded('.motif-image')
  assert page.evaluate('personal.current.transform')==drafts[1]['transform']
  assert page.locator('.scale-handle').is_hidden()
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  if os.environ.get('TIMBERART_TEST_SCREENSHOTS'):
   dest=pathlib.Path(os.environ['TIMBERART_TEST_SCREENSHOTS']);dest.mkdir(parents=True,exist_ok=True)
   page.screenshot(path=str(dest/f'local-images-{width}.png'),full_page=True)
  assert page.evaluate("localStorage.getItem(MAP_KEY)")==stored
  assert not errors,errors
  assert not [u for _,u in requests if 'drive.google.com' in u or 'googleusercontent.com' in u or 'accounts.google.com' in u]
  assert all(method=='GET' for method,_ in requests)
  # Simulate a missing source and require a local-only fallback, not a Google retry.
  page.route('**/assets/motifs/**/*.webp',lambda r:r.fulfill(status=404,body='Missing'))
  page.evaluate("() => {const img=document.querySelector('.motif-image');img.removeAttribute('srcset');img.src='./assets/motifs/nonexistent/missing.webp';}")
  page.wait_for_function("() => document.querySelector('.motif-image').dataset.motifFallback==='true'")
  assert page.locator('.motif-image').get_attribute('src')=='./assets/motifs/unavailable.svg'
  assert page.evaluate('personal.current.motifId')==CAT[0]['id']
  print(f'PASS {width}px {"touch" if touch else "mouse"}: local home/gallery/modal/editor/map/compare, unchanged old drafts/favorites/transforms, no overflow, no Drive/account requests, safe 404 fallback')
  context.close()
 browser.close()
server.shutdown()
