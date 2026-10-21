"""Dynamic catalog and failure contracts with local fixtures; never external services."""
import functools, http.server, json, os, pathlib, shutil, threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'catalog.json').read_text())
CATS=json.loads((ROOT/'data/categories.json').read_text())['categories']
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
URL=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 def context(width=1440,height=1000,touch=False):
  ctx=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,is_mobile=touch)
  ctx.route('https://**/*',lambda r:r.abort());page=ctx.new_page();errors=[];posts=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method!='GET' else None)
  return ctx,page,errors,posts
 for width,height,touch in [(1440,1000,False),(820,1180,True),(390,844,True)]:
  ctx,page,errors,posts=context(width,height,touch)
  page.goto(URL);page.wait_for_function('() => studio.ready')
  assert page.evaluate('studio.catalog')==CAT
  page.locator('[data-view="motifs"]').click()
  for cat in CATS:
   page.locator('#categorySelect').select_option(cat['key'])
   actual=page.locator('[data-design]').evaluate_all('es=>es.map(e=>e.dataset.design)')
   assert actual==[m['id'] for m in CAT if m['category']==cat['key']]
  page.locator('#categorySelect').select_option('all')
  # Search expectations come from the real catalog and runtime label normalization.
  term=CAT[-1]['name'].replace('_',' ').split()[0]
  expected=page.evaluate("q=>studio.catalog.filter(d=>(studioPrettyName(d.name)+' '+studioLabel(d.category)).toLocaleLowerCase('de').includes(q.toLocaleLowerCase('de'))).map(d=>d.id)",term)
  page.locator('#motifSearch').fill(term)
  assert page.locator('[data-design]').evaluate_all('es=>es.map(e=>e.dataset.design)')==expected
  page.locator('#motifSearch').fill('guaranteed-no-match-xy-981742')
  assert page.locator('[data-design]').count()==0 and page.locator('.empty-state').is_visible()
  page.locator('#motifSearch').fill('')
  page.evaluate("() => {Storage.prototype.originalSet=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new DOMException('Full','QuotaExceededError')}}")
  before=page.evaluate('JSON.stringify(favorites)');page.locator('[data-favorite]').first.click()
  assert page.evaluate('JSON.stringify(favorites)')==before,'Failed favorite write must not pretend success'
  assert 'nicht gespeichert' in page.locator('#personalStatus').inner_text().lower()
  page.evaluate('() => {Storage.prototype.setItem=Storage.prototype.originalSet}')
  page.locator('[data-favorite]').first.click();page.reload();page.wait_for_function('() => studio.ready')
  assert len(page.evaluate('favorites'))==1
  # Rapid navigation while the shared catalog promise is unresolved must render latest view only.
  page.evaluate("() => {window.finishCatalog=null;studio.loading=new Promise(resolve=>finishCatalog=resolve);studioNavigate('motifs');studioNavigate('map');studioNavigate('schriften');finishCatalog()}")
  assert page.locator('[data-font]').count()==page.evaluate('FONTS.length')
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  assert not errors,errors;assert not posts,posts
  print(f'PASS {width}px: every category, dynamic search/filter, empty result, favorite quota/reload, rapid navigation, no overflow/errors/POSTs',flush=True)
  ctx.close()
 # HTTP errors and structurally malformed JSON must not produce unhandled JS errors.
 for response in [(503,'unavailable'),(200,'{}'),(200,'[{"id":"bad"}]')]:
  ctx,page,errors,posts=context()
  ctx.route('**/catalog.json',lambda r:r.fulfill(status=response[0],body=response[1],content_type='application/json'))
  page.goto(URL);page.wait_for_function('() => studio.ready')
  assert page.get_by_text('Der Motivkatalog ist gerade nicht erreichbar.',exact=True).is_visible()
  page.locator('[data-view="motifs"]').click()
  assert page.get_by_text('Der Motivkatalog ist gerade nicht erreichbar.',exact=True).is_visible()
  assert page.locator('[data-design]').count()==0
  page.locator('[data-view="schriften"]').click();assert page.locator('[data-font]').count()==30
  assert not errors,errors;assert not posts,posts;ctx.close()
 print('PASS: unavailable/malformed catalog displays an explicit recoverable error; font atelier remains usable',flush=True)
 # Actual delayed HTTP catalog load followed by navigation.
 ctx,page,errors,posts=context();pending=[]
 ctx.route('**/catalog.json',lambda r:pending.append(r));page.goto(URL,wait_until='domcontentloaded')
 page.locator('[data-view="motifs"]').click();page.locator('[data-view="schriften"]').click()
 page.wait_for_function('() => studio.view==="schriften"');assert pending
 pending[0].fulfill(body=json.dumps(CAT),content_type='application/json');page.wait_for_function('() => studio.ready')
 assert page.locator('[data-font]').count()==30 and not errors
 ctx.close()
 # Empty category from configuration is selectable, not silently dropped.
 ctx,page,errors,posts=context()
 ctx.route('**/data/categories.json',lambda r:r.fulfill(body=json.dumps({'version':1,'categories':CATS+[{'id':'empty-test','key':'empty-test','name':'Leere Testkategorie'}]}),content_type='application/json'))
 page.goto(URL);page.wait_for_function('() => studio.ready');page.locator('[data-category="empty-test"]').click()
 assert page.locator('[data-design]').count()==0 and page.locator('.empty-state').is_visible()
 assert not errors and not posts;ctx.close()
 print('PASS: deferred HTTP catalog navigation and configured empty category',flush=True)
 browser.close()
server.shutdown()
