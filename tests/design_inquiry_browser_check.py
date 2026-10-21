"""Only intercepted Formspree requests; never contacts the actual endpoint."""
import functools,http.server,json,os,pathlib,shutil,threading,time
from playwright.sync_api import sync_playwright
from PIL import Image
import xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'catalog.json').read_text())
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}'
ENDPOINT='https://formspree.io/f/xzebgwlg'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,touch in [(1440,1000,False),(820,1180,True),(390,844,True)]:
  ctx=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,is_mobile=touch)
  ctx.route('https://**/*',lambda r:r.abort());requests=[];pending=[];reply={'mode':'ok'}
  def formspree(route):
   if route.request.method=='OPTIONS':route.fulfill(status=204,headers={'access-control-allow-origin':'*','access-control-allow-headers':'content-type','access-control-allow-methods':'POST'});return
   requests.append(route.request.post_data_json)
   mode=reply['mode']
   if mode=='hold':pending.append(route);return
   if mode=='network':route.abort();return
   route.fulfill(status=422 if mode=='422' else 429 if mode=='429' else 500 if mode=='500' else 200,content_type='application/json',headers={'access-control-allow-origin':'*'},body=json.dumps({'ok':True} if mode=='ok' else {}))
  ctx.route(ENDPOINT,formspree)
  page=ctx.new_page();errors=[];posts=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
  page.goto(URL);page.wait_for_function('() => studio.ready')
  def open_motif():
   page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.locator('[data-inquiry="motif"]').click()
  def ready():page.wait_for_function('() => activeInquiry?.phase==="ready"')
  def close():page.locator('.inquiry-close').click();page.wait_for_selector('#designInquiry',state='detached')
  def contact(name='Testkunde Ä & < >',email=''):
   page.locator('#inquiryName').fill(name);page.locator('#inquiryEmail').fill(email)
  def submit():page.locator('.inquiry-submit').click()
  open_motif();ready();assert requests==[]
  assert page.locator('.inquiry-dialog').evaluate('e=>e.scrollWidth<=e.clientWidth')
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  assert page.locator('.inquiry-preview').is_visible()
  assert page.locator('.inquiry-downloads a').count()==3
  submit();assert requests==[] # required name
  contact('   ');submit();assert requests==[]
  contact(email='bad');submit();assert requests==[]
  contact();reply['mode']='hold';submit()
  page.wait_for_function('() => activeInquiry.phase==="sending"')
  page.evaluate('document.getElementById("designInquiryForm").dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}))')
  page.keyboard.press('Escape');assert page.locator('#designInquiry').is_visible()
  assert len(requests)==1
  pending.pop().fulfill(status=200,content_type='application/json',headers={'access-control-allow-origin':'*'},body='{"ok":true}')
  page.wait_for_function('() => activeInquiry.phase==="sent"')
  assert 'erfolgreich' in page.locator('.inquiry-status').inner_text()
  first=requests[0];assert first['name']=='Testkunde Ä & < >' and first['email']==''
  d=json.loads(first['design_data']);assert d['type']=='motiv' and d['motif']['id']==CAT[0]['id']
  assert first['original_file_url'].startswith('https://drive.google.com/file/d/') and '/thumbnail' not in first['original_file_url']
  assert first['original_filename'] and d['motif']['source']['accessStatus']
  assert not d['previewFilesSent'] and not d['productionReady']
  assert 'name' not in page.evaluate('localStorage.getItem(MAP_KEY)||""')
  assert page.locator('#inquiryName').input_value()==''
  close()
  # Same design/contact again in this page session must not be re-sent.
  page.locator('[data-inquiry="motif"]').click();ready();contact();submit()
  page.wait_for_function('() => activeInquiry.phase==="sent"');assert len(requests)==1
  assert 'nicht erneut' in page.locator('.inquiry-status').inner_text();close()
  page.evaluate('closeImageModal()')
  page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click()
  raw=('Grüsse ♥ <script>& " \n\nLange manuelle Zeile '+('SehrlangesWort'*50)+'\n')*2
  page.locator('#wishText').fill(raw)
  for k,v in [('width',320),('height',220),('fontSize',49),('rotation',45),('x',300),('y',300)]:
   page.locator('#frame-'+k).fill(str(v));page.locator('#frame-'+k).press('Tab')
  page.locator('#frame-align').select_option('right');frame=page.evaluate('personal.current.textFrame')
  snapshot=page.evaluate('JSON.stringify({current:personal.current,dirty:personal.dirty,drafts:personal.drafts,raw:localStorage.getItem(MAP_KEY)})')
  page.locator('[data-inquiry="current"]').click();ready()
  assert page.evaluate('JSON.stringify({current:personal.current,dirty:personal.dirty,drafts:personal.drafts,raw:localStorage.getItem(MAP_KEY)})')==snapshot
  assert page.evaluate('activeInquiry.design.draft.textFrame')==frame
  assert page.evaluate('activeInquiry.design.draft.text')==raw
  assert page.evaluate('activeInquiry.design.render.rendered.effectiveFontSize')<=49
  # Parse self-contained SVG image and preserved line runs; no executable user markup.
  with page.expect_download() as download:page.locator('.inquiry-downloads a').nth(1).click()
  assert download.value.suggested_filename=='timberart-vorschau.svg'
  svg=pathlib.Path(download.value.path()).read_text();ET.fromstring(svg)
  assert '<script>' not in svg and 'data:image/png;base64,' in svg and '<text ' in svg
  with page.expect_download() as download:page.locator('.inquiry-downloads a').nth(0).click()
  with Image.open(download.value.path()) as png:
   assert png.format=='PNG' and png.size==(1200,1200)
  with page.expect_download() as download:page.locator('.inquiry-downloads a').nth(2).click()
  exported=json.loads(pathlib.Path(download.value.path()).read_text())
  assert exported['draft']['text']==raw and exported['draft']['textFrame']==frame
  contact('Personalisierter Test','reply@example.invalid');page.locator('#inquiryPhone').fill('+41 00 000 00 00');page.locator('#inquiryMessage').fill('Bemerkung\nÄÖÜ & < >')
  reply['mode']='ok';submit();page.wait_for_function('() => activeInquiry.phase==="sent"')
  sent=requests[-1];assert sent['wish_text']==raw and sent['max_font_size']==49
  assert json.loads(sent['design_data'])['draft']['textFrame']==frame
  assert sent['font_id'] and sent['font_name'] and sent['message']=='Bemerkung\nÄÖÜ & < >'
  assert page.evaluate('JSON.stringify({current:personal.current,dirty:personal.dirty,drafts:personal.drafts,raw:localStorage.getItem(MAP_KEY)})')==snapshot
  close()
  # Save original draft after inquiry; sending from map must not write it again.
  page.locator('#saveDraft').click();page.wait_for_selector('[data-edit]')
  stored=page.evaluate('localStorage.getItem(MAP_KEY)')
  page.locator('.draft-card [data-inquiry]').click();ready();contact('Map Test')
  reply['mode']='422';submit();page.wait_for_function('() => activeInquiry.phase==="ready"')
  assert 'abgelehnt' in page.locator('.inquiry-status').inner_text()
  assert page.locator('#inquiryName').input_value()=='Map Test'
  reply['mode']='network';submit();page.wait_for_function('() => activeInquiry.phase==="uncertain"')
  n=len(requests);page.evaluate('document.getElementById("designInquiryForm").dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}))');assert len(requests)==n
  # Closing/reopening must not turn an unknown receipt into an ordinary new send.
  close();page.locator('.draft-card [data-inquiry]').click();ready();contact('Map Test');submit()
  page.wait_for_function('() => activeInquiry.phase==="uncertain"');assert len(requests)==n
  reply['mode']='ok';page.locator('.inquiry-retry').click();page.wait_for_function('() => activeInquiry.phase==="sent"')
  assert requests[-1]['name']=='Map Test' and requests[-1]['request_id']==requests[-2]['request_id']
  assert page.evaluate('localStorage.getItem(MAP_KEY)')==stored;close()
  # Unknown JSON success and HTTP 5xx never claim success.
  for mode in ['empty','500','429']:
   page.locator('.draft-card [data-inquiry]').click();ready();contact('Failure '+mode);reply['mode']=mode;submit()
   page.wait_for_function('() => activeInquiry.phase!=="sending"')
   assert page.evaluate('activeInquiry.phase')==('ready' if mode=='429' else 'uncertain')
   assert 'erfolgreich' not in page.locator('.inquiry-status').inner_text();close()
  assert page.evaluate('localStorage.getItem(MAP_KEY)')==stored
  assert posts and all(u==ENDPOINT for u in posts)
  assert not errors,errors
  print(f'PASS {width}px: plain/personal/map inquiries; full long multiline data; PNG/SVG/JSON downloads; validation; duplicate and pending protection; confirmed-only success; HTTP/network/unknown errors; unchanged drafts; no other POSTs',flush=True)
  ctx.close()
 browser.close()
server.shutdown()
