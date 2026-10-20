"""Offline UI checks for stable category keys, empty folders and hostile names."""
import functools,http.server,json,os,pathlib,shutil,threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
URL=f'http://127.0.0.1:{server.server_port}'
catalog=json.loads((ROOT/'catalog.json').read_text());categories=json.loads((ROOT/'data/categories.json').read_text())
malicious='Neu "><img src=x onerror="window.injected=true">'
extra={'id':'drive-new-folder','key':'drive-new-folder','folderId':'new-folder','name':malicious,'displayName':malicious,'parentId':None}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width in [1440,820,390]:
  ctx=browser.new_context(viewport={'width':width,'height':1000},has_touch=width!=1440,is_mobile=width!=1440)
  ctx.route('https://**/*',lambda route:route.abort())
  ctx.route('**/data/categories.json',lambda r:r.fulfill(json={'version':1,'categories':categories['categories']+[extra]}))
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(URL);page.wait_for_function('() => studio.ready')
  assert page.locator('[data-category]').count()==len(categories['categories'])+1
  card=page.locator('[data-category="drive-new-folder"]');assert malicious in card.inner_text()
  card.click();assert page.locator('[data-design]').count()==0
  assert page.locator('#categorySelect').input_value()=='drive-new-folder'
  # Simulate a folder rename and later an image arriving: same category key/ID.
  renamed=dict(extra,name='Neu benannt',displayName='Neu benannt')
  ctx.route('**/data/categories.json',lambda r:r.fulfill(json={'version':1,'categories':categories['categories']+[renamed]}))
  entry=dict(catalog[0],id='new-image',name=malicious,category='drive-new-folder',categoryId='drive-new-folder')
  ctx.route('**/catalog.json',lambda r:r.fulfill(json=catalog+[entry]))
  page.reload();page.wait_for_function('() => studio.ready')
  page.locator('[data-category="drive-new-folder"]').click()
  assert page.locator('[data-design]').count()==1 and 'Neu benannt' in page.locator('h1').inner_text()
  page.locator('[data-design]').click();assert page.locator('#modalTitle').inner_text()==malicious
  page.evaluate('closeImageModal()')
  # Legacy renderer must escape imported names even when explicitly called.
  page.evaluate('(entry)=>{document.getElementById("content").innerHTML=renderDesignCard(entry)}',entry)
  assert not page.locator('img[src="x"]').count()
  page.locator('#content .design-card').click()
  assert page.locator('#modalTitle').inner_text()==malicious
  page.evaluate('closeImageModal()')
  assert not page.evaluate('Boolean(window.injected)')
  assert not errors,errors
  assert page.evaluate('FONTS.length')==30
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  ctx.close();print('PASS',width,'px: empty/new/renamed category, arriving image, stable key, escaped hostile labels and legacy renderer, 30 fonts')
 browser.close()
server.shutdown()
