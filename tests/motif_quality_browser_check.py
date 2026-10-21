"""Seven named motifs: mapping, proportions and real browser rendering, no Drive."""
import functools,http.server,json,os,pathlib,re,shutil,threading
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
NAMES=['03_Jagd_Revier_Beispiel','04_Jagd_Revier_Leer','09_Metallbau_Beispiel','10_Metallbau_Leer','05_Werkstatt_Beispiel','06_Werkstatt_Leer','Bergkette-Churfürsten']
CAT=json.loads((ROOT/'catalog.json').read_text())
MANIFEST=json.loads((ROOT/'data/motifs-manifest.json').read_text())['motifs']
BASE=json.loads((ROOT/'data/motifs-baseline.json').read_text())['motifs']
CATEGORIES=json.loads((ROOT/'data/categories.json').read_text())['categories']
selected=[]
for name in NAMES:
 records=[m for m in MANIFEST if m['name']==name];assert len(records)==1,name
 m=records[0];selected.append(m)
 assert len([d for d in CAT if d['id']==m['id'] and d['name']==name and d['category']==m['category']])==1
 assert m['category'] in {c['key'] for c in CATEGORIES}
 baseline=next((d for d in BASE if d['id']==m['id']),None)
 if baseline:assert baseline['category']==m['category']
 if name=='Bergkette-Churfürsten':
  assert next(c for c in CATEGORIES if c['id']==m['categoryId'])['name']=='Bergmotive'
 for edge,meta in m['variants'].items():
  reference=Image.new('1',(m['previewSource']['width'],m['previewSource']['height']))
  reference.thumbnail((int(edge),int(edge)),Image.Resampling.LANCZOS)
  with Image.open(ROOT/meta['path']) as im:
   assert im.size==reference.size, (name,edge,im.size,reference.size)
 print('PASS stored source proportions/category mapping:',name,flush=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for width,height,touch in [(1440,1000,False),(820,1180,True),(390,844,True)]:
  ctx=browser.new_context(viewport={'width':width,'height':height},has_touch=touch,is_mobile=touch)
  ctx.route('https://**/*',lambda r:r.abort());page=ctx.new_page();errors=[];posts=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method!='GET' else None)
  page.goto(URL);page.wait_for_function('() => studio.ready')
  for m in selected:
   page.locator('[data-view="motifs"]').click()
   query=re.sub(r'^\d+[_-]','',m['name']).replace('_',' ')
   page.locator('#motifSearch').fill(query);page.locator('[data-design="'+m['id']+'"]').click()
   page.wait_for_function('() => {const i=document.getElementById("modalImage");return i.complete&&i.naturalWidth>0}')
   page.get_by_role('button',name='Personalisieren',exact=True).click()
   page.wait_for_function('() => {const i=document.querySelector(".motif-image");return i.complete&&i.naturalWidth>0}')
   assert page.locator('.motif-image').evaluate('i=>getComputedStyle(i).objectFit')=='contain'
   assert page.evaluate('personal.current.motifId')==m['id']
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   if os.environ.get('TIMBERART_QA_SCREENSHOTS'):
    folder=pathlib.Path(os.environ['TIMBERART_QA_SCREENSHOTS']);folder.mkdir(parents=True,exist_ok=True)
    page.locator('#designSurface').screenshot(path=str(folder/f'{m["name"]}-{width}.png'))
   page.once('dialog',lambda d:d.accept());page.locator('[data-view="motifs"]').click()
  assert not errors and not posts
  print(f'PASS {width}px: seven named motifs load in large preview and editor, object-fit contain, correct IDs and no overflow/errors/POSTs',flush=True)
  ctx.close()
 browser.close()
server.shutdown()
