import http.server,threading,functools,json,pathlib,os,shutil
from playwright.sync_api import sync_playwright
ROOT=str(pathlib.Path(__file__).resolve().parents[1])
EXPECTED=json.loads((pathlib.Path(ROOT)/'catalog.json').read_text())
EXPECTED_COUNT=len(EXPECTED)
EXPECTED_CATEGORIES=len({item['category'] for item in EXPECTED})
SCREENSHOTS=os.environ.get('TIMBERART_TEST_SCREENSHOTS')
if SCREENSHOTS:pathlib.Path(SCREENSHOTS).mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=ROOT))
threading.Thread(target=server.serve_forever,daemon=True).start()
url='http://127.0.0.1:'+str(server.server_port)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True)
 context=browser.new_context(viewport={'width':1440,'height':1000})
 page=context.new_page(); errors=[]; posts=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 context.on('request',lambda r:posts.append(r.url) if r.method!='GET' else None)
 context.route('https://**/*',lambda r:r.abort())
 def ready():page.wait_for_function('n => typeof studio !== "undefined" && studio.ready && studio.catalog.length===n',arg=EXPECTED_COUNT)
 def nav(view):page.locator('[data-view="'+view+'"]').click()
 def accept():page.once('dialog',lambda d:d.accept())
 def dismiss():page.once('dialog',lambda d:d.dismiss())
 def drafts():return page.evaluate('personal.drafts')
 page.goto(url);ready()
 assert page.evaluate('FONTS.length')==30
 assert page.evaluate('allCategories.length')==EXPECTED_CATEGORIES
 nav('motifs');assert page.locator('[data-design]').count()==EXPECTED_COUNT
 page.locator('#categorySelect').select_option(index=1)
 assert 0<page.locator('[data-design]').count()<EXPECTED_COUNT
 page.locator('#categorySelect').select_option('all')
 page.locator('#motifSearch').fill('Hirsch');assert page.locator('[data-design]').count()>0
 page.locator('#motifSearch').fill('')
 page.locator('[data-favorite]').first.click();assert page.evaluate('favorites.length')==1
 page.locator('[data-design]').first.click()
 page.get_by_role('button',name='Personalisieren',exact=True).click()
 assert page.locator('[data-personal-font]').count()==30
 long='Für dich ♥ ÄÖÜ '+('Ein langer Wunschtext. '*15)+'\nZweite Zeile\nDritte Zeile <img src=x onerror=alert(1)>'
 page.locator('#wishText').fill(long)
 assert 'vollständig gespeichert' in page.locator('#textAdvice').inner_text()
 assert page.locator('.composition-text').inner_text()==long
 for choice in page.locator('[data-personal-font]').all():
  choice.click();assert choice.get_attribute('aria-pressed')=='true'
 page.locator('[data-personal-font="pacifico"]').click()
 # Guard unsaved navigation.
 dismiss();nav('map');assert page.locator('#wishText').is_visible()
 # Pick a different motif without losing text/font.
 page.locator('#chooseMotif').click();page.locator('[data-design]').nth(2).click();page.get_by_role('button',name='Personalisieren',exact=True).click()
 assert page.locator('#wishText').input_value()==long
 assert page.locator('[data-personal-font="pacifico"]').get_attribute('aria-pressed')=='true'
 page.locator('#saveDraft').click();assert len(drafts())==1
 page.reload();ready();nav('map');assert len(drafts())==1 and drafts()[0]['text']==long
 page.locator('[data-duplicate]').click();assert len(drafts())==2
 page.locator('[data-edit]').nth(1).click();page.locator('#wishText').fill('Alles Gute, Anna!')
 page.locator('[data-personal-font="orbitron"]').click();page.locator('#saveDraft').click()
 assert len(drafts())==2 and drafts()[1]['fontId']=='orbitron'
 for box in page.locator('[data-compare]').all():box.check()
 page.locator('#compareDrafts').click();assert page.locator('.comparison-grid article').count()==2
 assert 'Alles Gute, Anna!' in page.locator('.comparison-grid').inner_text()
 # Three responsive layouts, comparison and editor.
 for width,height,label in [(1440,1000,'desktop'),(820,1180,'tablet'),(390,844,'phone')]:
  page.set_viewport_size({'width':width,'height':height})
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),label+' comparison overflow'
  assert page.locator('[data-view="map"]').is_visible()
  if SCREENSHOTS:page.screenshot(path=str(pathlib.Path(SCREENSHOTS)/(label+'-map.png')),full_page=True)
  page.locator('[data-edit]').first.click()
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),label+' editor overflow'
  assert page.locator('#saveDraft').bounding_box()['height']>=48
  if SCREENSHOTS:page.screenshot(path=str(pathlib.Path(SCREENSHOTS)/(label+'-editor.png')),full_page=True)
  nav('map');page.locator('#compareDrafts').click()
 print(f'PASS: {EXPECTED_COUNT} motifs / {EXPECTED_CATEGORIES} categories / 30 fonts; long multiline/XSS-safe text; motif change; save/reload/edit/duplicate/compare; 3 viewport layouts')
 # Delete cancelled and confirmed.
 dismiss();page.locator('[data-delete]').first.click();assert len(drafts())==2
 accept();page.locator('[data-delete]').first.click();assert len(drafts())==1
 # Storage failure must preserve draft, no fake success.
 page.locator('[data-edit]').click();page.locator('#wishText').fill('Nicht verlieren')
 page.evaluate("() => {window.originalSet=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new Error('quota')};}")
 page.locator('#saveDraft').click();assert 'Nicht gespeichert' in page.locator('#editorError').inner_text();assert page.locator('#wishText').input_value()=='Nicht verlieren'
 page.evaluate('() => {Storage.prototype.setItem=window.originalSet;}')
 page.locator('#saveDraft').click();assert drafts()[0]['text']=='Nicht verlieren'
 # Both legacy test order routes still send no data.
 nav('schriften');page.locator('[data-font="0"]').click();page.get_by_role('button',name='Diese Schrift auswählen').click()
 page.locator('#orderForm input[name="name"]').fill('Testkunde');page.locator('#orderForm button[type="submit"]').click()
 assert page.locator('#orderForm .preview-order-status').is_visible();page.evaluate('closeModal()')
 nav('motifs');page.locator('[data-design]').first.click();page.locator('#imageModal .btn-primary').click()
 page.locator('#designOrderForm input[name="name"]').fill('Testkunde');page.locator('#designOrderForm button[type="submit"]').click()
 assert page.locator('#designOrderForm .preview-order-status').is_visible();page.evaluate('closeDesignOrderForm()')
 # Reset cancel, reset accept, no unrelated storage deletion, persistent reset.
 page.evaluate("localStorage.setItem('unrelated','keep')")
 dismiss();page.get_by_role('button',name='Neue Beratung',exact=True).click();assert len(drafts())==1
 accept();page.get_by_role('button',name='Neue Beratung',exact=True).click()
 assert page.evaluate('personal.drafts.length===0 && favorites.length===0 && personal.current===null && selectedFont===null && selectedDesign===null')
 assert page.locator('#orderForm input[name="name"]').input_value()==''
 assert page.locator('#designOrderForm input[name="name"]').input_value()==''
 assert page.locator('#customText').input_value()==''
 assert page.evaluate("localStorage.getItem('unrelated')")=='keep'
 page.reload();ready();assert drafts()==[] and page.evaluate('favorites.length')==0
 print('PASS: delete confirmation; storage failure; both test orders; reset cancelled/confirmed; form privacy; reset survives reload; unrelated browser data retained')
 # Font-first path and validation.
 nav('schriften');page.locator('[data-font="2"]').click();page.locator('#customText').fill('Vom Schriftatelier')
 page.get_by_role('button',name='Mit Motiv kombinieren').click();assert page.locator('#wishText').input_value()=='Vom Schriftatelier'
 page.locator('#saveDraft').click();assert 'Motiv' in page.locator('#editorError').inner_text()
 page.locator('#chooseMotif').click();page.locator('[data-design]').first.click();page.get_by_role('button',name='Personalisieren',exact=True).click()
 page.locator('#wishText').fill('  ');page.locator('#saveDraft').click();assert 'Wunschtext' in page.locator('#editorError').inner_text()
 page.locator('#wishText').fill('Schriftweg');page.locator('#saveDraft').click();assert drafts()[0]['fontId']=='oswald'
 # A second tab resets the shared consultation.
 second=context.new_page();second.goto(url);second.wait_for_function('() => studio.ready')
 second.once('dialog',lambda d:d.accept())
 with page.expect_navigation(wait_until='domcontentloaded'):
  second.get_by_role('button',name='Neue Beratung',exact=True).click()
 ready();assert drafts()==[]
 assert not errors,errors
 assert not posts,posts
 print('PASS: font-first flow; required motif/text validation; cross-tab reset; zero JS errors; zero POST requests')
 # Corrupt browser data must not be silently overwritten.
 page.evaluate("localStorage.setItem(MAP_KEY, '{broken')")
 page.reload();ready();nav('map')
 assert 'nicht gelesen' in page.locator('#personalStatus').inner_text()
 assert page.evaluate('localStorage.getItem(MAP_KEY)')=='{broken'
 accept();page.get_by_role('button',name='Neue Beratung',exact=True).click();assert drafts()==[]
 print('PASS: corrupt saved data protected; explicit reset recovers storage')
 browser.close()
server.shutdown()
