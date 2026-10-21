"""Legacy/missing resources, transport timeout, CSP, SVG/PNG fidelity; all traffic local or intercepted."""
import functools,http.server,json,os,pathlib,shutil,threading,xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'catalog.json').read_text());MANIFEST=json.loads((ROOT/'data/motifs-manifest.json').read_text())
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}'
ENDPOINT='https://formspree.io/f/xzebgwlg'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for version,condition in [(1,'missing-manifest'),(2,'thumbnail'),(3,'missing-image'),(3,'missing-motif')]:
  ctx=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True)
  ctx.route('https://**/*',lambda r:r.abort());posts=[]
  ctx.route(ENDPOINT,lambda r:(posts.append(r.request.post_data_json),r.fulfill(body='{"ok":true}',content_type='application/json',headers={'access-control-allow-origin':'*'}))[1])
  if condition=='missing-manifest':ctx.route('**/data/motifs-manifest.json',lambda r:r.fulfill(status=503,body='Unavailable'))
  if condition=='thumbnail':
   data=json.loads(json.dumps(MANIFEST));data['motifs'][0]['source']['originalUrl']='https://drive.google.com/thumbnail?id='+CAT[0]['id']
   ctx.route('**/data/motifs-manifest.json',lambda r:r.fulfill(body=json.dumps(data),content_type='application/json'))
  if condition=='missing-image':ctx.route('**/assets/motifs/**/*.webp',lambda r:r.fulfill(status=404,body='Missing'))
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(URL);page.wait_for_function('() => studio.ready')
  base={'id':'legacy','motifId':'missing' if condition=='missing-motif' else CAT[0]['id'],'motifName':CAT[0]['name'],'category':CAT[0]['category'],'fontId':'pacifico','text':'Alt Ä ♥\n\nZeile < & >','layoutVersion':version,'createdAt':'test','updatedAt':'test'}
  if version==2:base['transform']={'x':.42,'y':.7,'scale':1.3,'rotation':-31}
  if version==3:base['textFrame']=page.evaluate('copyTextFrame()')
  stored=json.dumps({'version':2,'epoch':'fixture','drafts':[base]})
  page.evaluate('raw=>localStorage.setItem(MAP_KEY,raw)',stored);page.reload();page.wait_for_function('() => studio.ready')
  page.locator('[data-view="map"]').click();page.locator('.draft-card [data-inquiry]').click()
  page.wait_for_function('() => activeInquiry?.phase==="ready"')
  assert page.evaluate('activeInquiry.design.draft')==base
  if condition in ['missing-manifest','thumbnail','missing-motif']:
   assert page.evaluate('activeInquiry.design.motif.source.originalUrl') is None
  if condition in ['missing-image','missing-motif']:
   assert page.evaluate('activeInquiry.design.render.motifIncluded') is False
   assert 'Motiv' in page.locator('.inquiry-warnings').inner_text()
  with page.expect_download() as download:page.locator('.inquiry-downloads a').nth(1).click()
  svg=pathlib.Path(download.value.path()).read_text();assert ET.fromstring(svg).tag.endswith('svg')
  assert '<script' not in svg and 'http://drive' not in svg
  page.locator('#inquiryName').fill('Nur simulierter Test');page.locator('.inquiry-submit').click()
  page.wait_for_function('() => activeInquiry.phase==="sent"')
  assert json.loads(posts[0]['design_data'])['draft']==base
  assert page.evaluate('localStorage.getItem(MAP_KEY)')==stored
  page.locator('.inquiry-close').click();assert not errors,errors
  print(f'PASS v{version} {condition}: safe provenance, complete unchanged draft, parseable SVG and simulated send',flush=True)
  ctx.close()
 # Real timeout path without waiting thirty seconds, then no automatic retry.
 ctx=browser.new_context();ctx.route('https://**/*',lambda r:r.abort());pending=[]
 ctx.route(ENDPOINT,lambda r:pending.append(r));page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(URL);page.wait_for_function('() => studio.ready');page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.locator('[data-inquiry="motif"]').click();page.wait_for_function('() => activeInquiry?.phase==="ready"')
 page.locator('#inquiryName').fill('Timeout Test');page.clock.install();page.locator('.inquiry-submit').click()
 page.wait_for_function('() => activeInquiry.phase==="sending"');page.clock.fast_forward(31000)
 page.wait_for_function('() => activeInquiry.phase==="uncertain"');assert len(pending)==1
 page.clock.fast_forward(120000);assert len(pending)==1
 assert 'Keine sichere' in page.locator('.inquiry-status').inner_text()
 page.clock.resume();page.locator('.inquiry-close').click()
 # CSP allows only the intended receiver path; unrelated destinations remain blocked.
 page.evaluate("() => {window.blockedConnect=0;document.addEventListener('securitypolicyviolation',e=>{if(e.effectiveDirective==='connect-src')blockedConnect++})}")
 for url in ['https://formspree.io/f/not-allowed','https://example.invalid/']:
  assert page.evaluate('async url=>{try{await fetch(url);return false}catch(_){return true}}',url)
 page.wait_for_function('() => blockedConnect>=2')
 for route in pending:
  try:route.abort()
  except Exception:pass # client timeout may already have closed the intercepted request
 # Unsupported native-dialog browsers fail safely before asking for contact data.
 page.evaluate('HTMLDialogElement.prototype.showModal=undefined')
 page.locator('[data-inquiry="motif"]').click()
 assert 'unterstützt' in page.locator('#personalStatus').inner_text()
 assert page.locator('#designInquiry').count()==0
 assert not errors,errors;ctx.close()
 print('PASS timeout: exactly one intercepted attempt, no retry; CSP rejects other paths/hosts',flush=True)
 browser.close()
server.shutdown()
