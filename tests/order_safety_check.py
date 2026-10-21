"""Market stand: no order/inquiry UI, and native submissions remain blocked by CSP."""
import functools,http.server,os,pathlib,re,shutil,threading
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 context=browser.new_context();context.route('https://**/*',lambda r:r.abort())
 page=context.new_page();posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
 page.goto(url);page.wait_for_function('() => studio.ready')
 assert page.locator('form,[data-inquiry]').count()==0
 assert page.evaluate('typeof inquirySubmit')=='undefined'
 for view in ['motifs','schriften','map']:
  page.locator(f'[data-view="{view}"]').click()
  assert page.get_by_role('button',name=re.compile('Design an TimberArt senden|Testbestellung')).count()==0
 assert not posts
 context.close()
 # A synthetic form proves the retained CSP guard even without JavaScript.
 source=(ROOT/'index.html').read_text();csp=re.search(r'<meta http-equiv="Content-Security-Policy"[^>]+>',source).group()
 assert "connect-src 'self';" in csp and "form-action 'none'" in csp
 context=browser.new_context(java_script_enabled=False)
 context.route('https://**/*',lambda r:r.abort())
 context.route('**/native-test.html',lambda r:r.fulfill(content_type='text/html',body='<html><head>'+csp+'</head><body><form method="post" action="/forbidden"><input name="name" value="LOCAL_TEST"><button>Submit</button></form></body></html>'))
 page=context.new_page();page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
 page.goto(url+'/native-test.html');page.get_by_role('button').click(no_wait_after=True);page.wait_for_timeout(250)
 assert not posts
 context.close();browser.close()
server.shutdown()
print('PASS: no order/inquiry forms or buttons; no loaded sender; native submission blocked without JS; zero POSTs')
