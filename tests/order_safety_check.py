import http.server,threading,functools,os,shutil,pathlib
from playwright.sync_api import sync_playwright
ROOT=str(pathlib.Path(__file__).resolve().parents[1])
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=ROOT));threading.Thread(target=server.serve_forever,daemon=True).start()
url='http://127.0.0.1:'+str(server.server_port)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width in [1440,820,390]:
  context=browser.new_context(viewport={'width':width,'height':1000})
  page=context.new_page();requests=[];errors=[]
  page.on('request',lambda r:requests.append((r.method,r.url,r.post_data or '')))
  page.on('pageerror',lambda e:errors.append(str(e)))
  context.route('https://**/*',lambda route:route.abort())
  page.goto(url,wait_until='networkidle');page.wait_for_function('() => studio.ready')
  page.evaluate('''() => {
    window.orderCalls=[];window.orderViolations=[];
    const originalFetch=window.fetch;
    window.fetch=(...args)=>{orderCalls.push('fetch');return originalFetch(...args)};
    const originalSend=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send=function(...args){orderCalls.push('xhr');return originalSend.apply(this,args)};
    navigator.sendBeacon=(...args)=>{orderCalls.push('beacon');return false};
    document.addEventListener('securitypolicyviolation',e=>orderViolations.push(e.effectiveDirective));
  }''')
  # Fill all fields, not only the required name; submit both visible UI paths twice.
  page.locator('[data-view="schriften"]').click();page.locator('[data-font="0"]').click()
  page.locator('#customText').fill('ORDER_SAFETY_SENTINEL');page.get_by_role('button',name='Diese Schrift auswählen').click()
  for field in ['name','email','phone','message']:
   value='safety@example.invalid' if field=='email' else 'ORDER_SAFETY_SENTINEL'
   page.locator('#orderForm [name="'+field+'"]').fill(value)
  start=len(requests)
  page.locator('#orderForm button[type="submit"]').click();page.locator('#orderForm button[type="submit"]').click()
  assert 'keine Daten versendet' in page.locator('#orderForm .preview-order-status').inner_text()
  assert requests[start:]==[]
  page.evaluate('closeModal()')
  page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.locator('#imageModal .btn-primary').click()
  for field in ['name','email','phone','message']:
   value='safety@example.invalid' if field=='email' else 'ORDER_SAFETY_SENTINEL'
   page.locator('#designOrderForm [name="'+field+'"]').fill(value)
  start=len(requests)
  page.locator('#designOrderForm button[type="submit"]').click();page.locator('#designOrderForm button[type="submit"]').click()
  assert 'keine Daten versendet' in page.locator('#designOrderForm .preview-order-status').inner_text()
  assert requests[start:]==[]
  assert page.evaluate('orderCalls')==[]
  # Native submit bypasses JS submit handlers; CSP must still prohibit any request.
  start=len(requests)
  for index,formid in enumerate(['orderForm','designOrderForm'],1):
   page.evaluate("id => HTMLFormElement.prototype.submit.call(document.getElementById(id))",formid)
   page.wait_for_function("count => orderViolations.filter(d=>d==='form-action').length>=count",arg=index,timeout=5000)
  assert requests[start:]==[]
  assert not any('ORDER_SAFETY_SENTINEL' in u+b or 'safety@example.invalid' in u+b for _,u,b in requests)
  assert not errors,errors
  context.close()
  print('PASS',width,'px: both filled forms; repeat submit; zero form requests; zero fetch/XHR/beacon; native submit blocked by CSP')
 # With scripts disabled, page.evaluate(function) cannot reliably invoke page code.
 # Click the actual original native form controls in an isolated no-script fixture.
 import re
 source=(pathlib.Path(ROOT)/'index.html').read_text()
 csp=re.search(r'<meta http-equiv="Content-Security-Policy"[^>]+>',source).group()
 forms=re.findall(r'<form\b.*?</form>',source,re.S)
 assert len(forms)==2 and "form-action 'none'" in csp
 context=browser.new_context(java_script_enabled=False)
 context.route('https://**/*',lambda route:route.abort())
 context.route('**/native-test.html',lambda r:r.fulfill(body='<html><head>'+csp+'</head><body>'+''.join(forms)+'</body></html>',content_type='text/html'))
 for formid in ['orderForm','designOrderForm']:
  page=context.new_page();requests=[]
  page.on('request',lambda r:requests.append((r.method,r.url,r.post_data or '')))
  page.goto(url+'/native-test.html');initial=len(requests)
  page.locator('#'+formid+' [name="name"]').fill('ORDER_SAFETY_SENTINEL')
  page.locator('#'+formid+' [name="email"]').fill('safety@example.invalid')
  page.locator('#'+formid+' button[type="submit"]').click(no_wait_after=True)
  page.wait_for_timeout(250)
  assert requests[initial:]==[]
  assert page.url==url+'/native-test.html'
  page.close()  # Chromium leaves a blocked native navigation pending; isolate the next form.
 print('PASS: actual native clicks on both original forms blocked by original CSP with JavaScript disabled')
 context.close();browser.close()
server.shutdown()
