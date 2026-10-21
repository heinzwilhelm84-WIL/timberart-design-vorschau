"""Responsive visual-theme checks; local data and screenshots only, no external requests."""
import functools, http.server, json, os, pathlib, shutil, threading
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT/'catalog.json').read_text())
CATEGORIES = {c['key'] for c in json.loads((ROOT/'data/categories.json').read_text())['categories']} | {m['category'] for m in CATALOG}
SCREENSHOTS = os.environ.get('TIMBERART_REDESIGN_SCREENSHOTS')
if SCREENSHOTS:
 pathlib.Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self, *args): pass
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
with sync_playwright() as p:
 browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'), headless=True)
 for width, height, touch in [(1440, 1000, False), (820, 1180, True), (390, 844, True)]:
  ctx = browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch, is_mobile=touch)
  ctx.route('https://**/*', lambda r: r.abort())
  page = ctx.new_page(); errors = []; posts = []
  page.on('pageerror', lambda e: errors.append(str(e)))
  page.on('request', lambda r: posts.append(r.url) if r.method != 'GET' else None)
  page.goto(f'http://127.0.0.1:{server.server_port}'); page.wait_for_function('() => studio.ready')
  def no_overflow(): assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
  def nav(view): page.locator(f'[data-view="{view}"]').click()
  def shot(name):
   if SCREENSHOTS:
    page.eval_on_selector_all('#content img', "els => els.forEach(i => i.loading = 'eager')")
    page.wait_for_function('() => [...document.querySelectorAll("#content img")].every(i => i.complete && i.naturalWidth > 0)')
    page.evaluate("async () => {await Promise.all([...document.querySelectorAll('#content img')].map(i => i.decode())); await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));}")
    page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    page.screenshot(path=str(pathlib.Path(SCREENSHOTS) / f'{name}-{width}.png'), full_page=True, animations='disabled')
  assert page.locator('#welcomeTitle').inner_text().replace('\n', ' ') == 'Gestalte dein persönliches Unikat.'
  assert page.locator('[data-category]').count() == len(CATEGORIES)
  assert page.evaluate('studio.catalog') == CATALOG and page.evaluate('FONTS.length') == 30
  assert page.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgb(246, 242, 234)'
  assert page.locator('.brand-logo,.footer-logo').count() == 2
  page.wait_for_function('() => [...document.querySelectorAll(".brand-logo,.footer-logo")].every(i => i.complete && i.naturalWidth > 0)')
  for logo in page.locator('.brand-logo,.footer-logo').all():
   assert logo.get_attribute('src') == './assets/brand/timberart-logo.png'
   assert logo.evaluate('e => getComputedStyle(e).filter') == 'none'
  assert page.locator('.preview-banner').is_visible()
  no_overflow(); shot('startseite')
  for nav_button in page.locator('.studio-header button').all():
   assert nav_button.bounding_box()['height'] >= 48
  page.get_by_role('button', name='Jetzt gestalten', exact=False).click()
  assert page.locator('[data-design]').count() == len(CATALOG)
  page.locator('#motifSearch').fill('Hirsch'); assert page.locator('[data-design]').count() > 0
  page.locator('#motifSearch').fill(''); page.locator('[data-favorite]').first.click()
  nav('favorites'); assert page.locator('[data-design]').count() == 1
  no_overflow()
  page.locator('[data-design]').first.click(); page.get_by_role('button', name='Personalisieren', exact=True).click()
  page.locator('#wishText').fill('Für dich\nvon Herzen')
  for key, value in [('y', '410'), ('width', '360'), ('height', '155'), ('fontSize', '34')]:
   field = page.locator('#frame-' + key); field.fill(value); field.press('Tab')
  assert page.locator('#designSurface').evaluate('e => getComputedStyle(e).backgroundColor') == 'rgb(255, 255, 255)'
  assert page.locator('.composition').evaluate('e => getComputedStyle(e).backgroundColor') == 'rgb(255, 255, 255)'
  assert page.locator('.resize-handle').count() == 4
  assert page.locator('.rotate-handle').count() == 1
  assert page.locator('#saveDraft').bounding_box()['height'] >= 48
  assert page.locator('[data-personal-font]').count() == 30
  no_overflow(); shot('editor')
  page.locator('.frame-v3-object').focus(); page.keyboard.press('Enter')
  assert page.locator('.resize-handle:visible').count() == 4
  assert page.locator('.frame-v3-object').evaluate('e => getComputedStyle(e).outlineStyle') == 'dashed'
  no_overflow(); shot('editor-auswahl')
  saved = page.evaluate('JSON.stringify(personal.current.textFrame)')
  page.locator('#saveDraft').click(); page.wait_for_selector('[data-edit]')
  assert page.evaluate('JSON.stringify(personal.drafts[0].textFrame)') == saved
  page.locator('[data-duplicate]').click(); page.wait_for_function('() => personal.drafts.length === 2')
  for box in page.locator('[data-compare]').all(): box.check()
  page.locator('#compareDrafts').click()
  assert page.locator('.comparison-grid .resize-handle').count() == 0
  no_overflow(); shot('designmappe')
  page.reload(); page.wait_for_function('() => studio.ready'); nav('map')
  page.locator('[data-edit]').first.click()
  assert page.evaluate('JSON.stringify(personal.current.textFrame)') == saved
  nav('schriften'); assert page.locator('[data-font]').count() == 30
  assert page.locator('.font-card .preview').first.evaluate('e => getComputedStyle(e).backgroundColor') == 'rgb(255, 255, 255)'
  no_overflow()
  assert not page.locator('a[href*="checkout"],a[href*="login"],form[action]').count()
  assert not errors, errors
  assert not posts, posts
  print(f'PASS {width}px: original local logo; cream/bronze theme; {len(CATEGORIES)} categories; direct design entry; search/favorites; white previews; four grips; save/reopen/map/compare; 30 fonts; touch targets; no overflow/errors/POSTs', flush=True)
  ctx.close()
 browser.close()
server.shutdown()
