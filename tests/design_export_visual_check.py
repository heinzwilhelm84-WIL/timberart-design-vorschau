"""Pixel comparison of locally rendered PNG against the actual editor, not original artwork."""
import functools,http.server,os,pathlib,shutil,threading
from PIL import Image,ImageChops,ImageStat
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=pathlib.Path(os.environ.get('TIMBERART_INQUIRY_SCREENSHOTS','/tmp/timberart-inquiry-visual'));OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start();URL=f'http://127.0.0.1:{server.server_port}'
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 for loaded in [False,True]:
  c=b.new_context(viewport={'width':1440,'height':1100},device_scale_factor=2);c.route('https://**/*',lambda r:r.abort())
  page=c.new_page();errors=[];posts=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
  page.goto(URL);page.wait_for_function('() => studio.ready');page.locator('[data-view="motifs"]').click();page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click()
  if loaded:
   font=pathlib.Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
   page.evaluate("async bytes=>{const f=await new FontFace('Montserrat',new Uint8Array(bytes)).load();document.fonts.add(f);personalFontsChanged()}",list(font.read_bytes()))
  for k,v in [('x',300),('y',500),('width',480),('height',145),('rotation',0),('fontSize',42)]:
   page.locator('#frame-'+k).fill(str(v));page.locator('#frame-'+k).press('Tab')
  page.locator('#wishText').fill('Für dich ♥\nAnna & Ben')
  # Keep the actual editor node/styles, but remove surrounding sticky/overflow UI
  # from the capture so only the 600-unit design surface is compared.
  page.evaluate("""() => {
   const s=document.getElementById('designSurface'),wrap=s.closest('.composition');document.body.append(wrap);
   Object.assign(wrap.style,{position:'fixed',left:'0',top:'0',width:'600px',height:'600px',padding:'0',margin:'0',border:'0',borderRadius:'0',zIndex:'10000'});
   wrap.style.setProperty('padding','0','important');
   Object.assign(s.style,{width:'600px',height:'600px',position:'relative',margin:'0',border:'0',borderRadius:'0'});transformFit(s);transformSelect();
  }""")
  page.wait_for_function('() => document.querySelector(".motif-image").complete')
  page.evaluate("() => scrollTo({top:0,left:0,behavior:'instant'})")
  page.evaluate('() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
  assert page.locator('#designSurface').evaluate('s=>{const r=s.getBoundingClientRect();return r.x===0&&r.y===0&&r.width===600&&r.height===600}')
  actual=OUT/f'editor-{loaded}.png';page.screenshot(path=str(actual),clip={'x':0,'y':0,'width':600,'height':600},animations='disabled')
  effective=page.evaluate('getComputedStyle(document.querySelector("#designSurface .frame-text")).fontSize')
  page.locator('[data-inquiry="current"]').click();page.wait_for_function('() => activeInquiry?.phase==="ready"')
  assert page.evaluate('activeInquiry.design.render.rendered.effectiveFontSize')==float(effective.removesuffix('px'))
  with page.expect_download() as download:page.locator('.inquiry-downloads a').first.click()
  exported=OUT/f'export-{loaded}.png';download.value.save_as(str(exported))
  # Exclude motif resampling differences: compare just the text below its layout box.
  with Image.open(actual) as a,Image.open(exported) as e:
   assert a.size==e.size==(1200,1200)
   crop=(0,840,1200,1200)
   difference=ImageChops.difference(a.convert('RGB').crop(crop),e.convert('RGB').crop(crop))
   mean=sum(ImageStat.Stat(difference).mean)/3
   assert mean<5,('PNG text placement differs from actual editor',loaded,mean)
  assert not errors and not posts
  print(f'PASS PNG {"loaded local font" if loaded else "fallback font"}: actual editor/effective size; text-region mean absolute RGB error={mean:.4f}/255; no POST',flush=True)
  page.locator('#designInquiry').screenshot(path=str(OUT/f'inquiry-{loaded}.png'))
  c.close()
 b.close()
server.shutdown()
