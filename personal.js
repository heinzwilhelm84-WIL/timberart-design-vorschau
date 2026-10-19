/* Local-only personalisation. No order or customer data leaves this browser. */
const MAP_KEY = 'timberart-designmappe-v1';
const personal = { drafts: [], current: null, dirty: false, picking: false, compare: [], blocked: false, epoch: '', message: '' };
const fontId = font => font.name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
const personalFont = id => FONTS.find(font => fontId(font) === id) || FONTS[0];
function mapRead() {
    try {
        const raw = localStorage.getItem(MAP_KEY);
        if (!raw) { personal.epoch = crypto.randomUUID(); return; }
        const data = JSON.parse(raw);
        if (data.version !== 1 || !Array.isArray(data.drafts) || typeof data.epoch !== 'string') throw Error();
        const ids = new Set();
        for (const d of data.drafts) {
            if (!d || typeof d.id !== 'string' || ids.has(d.id) || typeof d.motifId !== 'string' || typeof d.text !== 'string' || !FONTS.some(f => fontId(f) === d.fontId) || typeof d.createdAt !== 'string' || typeof d.updatedAt !== 'string') throw Error();
            ids.add(d.id);
        }
        personal.drafts = data.drafts;
        personal.epoch = data.epoch;
    } catch (_) {
        personal.blocked = true;
        personal.message = 'Die lokale Designmappe kann nicht gelesen werden. Vorhandene Daten werden nicht überschrieben. Starte bei Bedarf nach Bestätigung eine neue Beratung.';
    }
}
function mapWrite(drafts) {
    if (personal.blocked) { personalNotice(personal.message); return false; }
    try {
        // Read before write so an older open tab cannot silently overwrite another consultation.
        const raw = localStorage.getItem(MAP_KEY);
        if (raw !== personal.lastRaw) throw Error('changed');
        const value = JSON.stringify({ version: 1, epoch: personal.epoch, drafts });
        localStorage.setItem(MAP_KEY, value);
        personal.lastRaw = value;
        personal.drafts = drafts;
        return true;
    } catch (_) {
        personalNotice('Nicht gespeichert: Der Browserspeicher ist voll, gesperrt oder wurde in einem anderen Fenster verändert. Dein aktueller Entwurf bleibt geöffnet.');
        return false;
    }
}
function personalNotice(text) {
    const el = document.getElementById('personalStatus');
    el.textContent = text;
}
function personalLeave(view) {
    if (!personal.current || view === 'editor') return true;
    if (personal.picking && ['motifs', 'favorites'].includes(view)) return true;
    if (personal.dirty && !confirm('Ungespeicherte Änderungen verwerfen und diesen Bereich verlassen?')) return false;
    personal.current = null; personal.dirty = false; personal.picking = false;
    return true;
}
function personalStart(motifId, seed) {
    if (personal.current && !personal.picking && personal.dirty && !confirm('Aktuellen ungespeicherten Entwurf verwerfen?')) return;
    const current = personal.picking && personal.current ? personal.current : { id: null, text: seed?.text || '', fontId: seed?.fontId || fontId(FONTS[0]) };
    personal.current = { ...current, motifId: motifId || '' };
    personal.picking = false;
    personal.dirty = true;
    closeImageModal(); closeModal();
    studioNavigate('editor');
}
function personalFromFont() {
    if (!selectedFont) return;
    personalStart('', { text: document.getElementById('customText').value, fontId: fontId(selectedFont) });
}
function personalPick() {
    personal.picking = true;
    studioNavigate('motifs');
    personalNotice('Wähle ein Motiv, öffne es und tippe auf „Personalisieren“. Dein Text und deine Schrift bleiben erhalten.');
}
function personalPreview(d, full = false) {
    const motif = studio.catalog.find(m => m.id === d.motifId);
    const font = personalFont(d.fontId);
    return `<div class="composition ${full ? 'composition-large' : ''}">${motif ? `<img src="${studioEscape(motif.url)}" alt="${studioEscape(studioPrettyName(motif.name))}" loading="lazy"><span class="asset-warning" hidden>Motivbild nicht erreichbar. Die Auswahl bleibt gespeichert.</span>` : '<p class="asset-warning">Bitte ein Motiv auswählen.</p>'}<div class="composition-text" tabindex="0" role="region" aria-label="Wunschtextvorschau, bei langen Texten scrollbar" style="font-family:${studioEscape(font.family)}">${studioEscape(d.text || 'Dein Wunschtext')}</div></div>`;
}
function personalImages() {
    document.querySelectorAll('.composition img').forEach(img => img.addEventListener('error', () => { img.hidden = true; img.nextElementSibling.hidden = false; }, { once: true }));
}
function personalEditor() {
    if (!personal.current) { personal.current = { id: null, motifId: '', text: '', fontId: fontId(FONTS[0]) }; }
    personal.picking = false;
    studioNavigation();
    const d = personal.current;
    const motif = studio.catalog.find(m => m.id === d.motifId);
    document.getElementById('content').innerHTML = `<section class="page-wrap personal-page"><div class="eyebrow">Dein persönlicher Entwurf</div><h1>Mach es zu deinem Geschenk.</h1><ol class="personal-steps"><li>1 · Motiv wählen</li><li>2 · Text & Schrift</li><li>3 · In der Mappe speichern</li></ol><div class="personal-layout"><div><div id="compositionPreview">${personalPreview(d, true)}</div><p class="personal-caption">Gestaltungsvorschau · keine massstabsgetreue Gravurvorlage</p><p id="fontStatus" role="status"></p></div><div class="personal-controls"><h2>Deine Gestaltung</h2><p>${motif ? studioEscape(studioPrettyName(motif.name)) + ' · ' + studioEscape(studioLabel(motif.category)) : 'Noch kein Motiv ausgewählt'}</p><button class="action" id="chooseMotif">${motif ? 'Motiv wechseln' : 'Motiv auswählen'}</button><label for="wishText">Dein Wunschtext</label><textarea id="wishText" rows="4" aria-describedby="textAdvice" placeholder="Zum Beispiel: Für dich, von Herzen"></textarea><p id="textAdvice" class="personal-help" role="status"></p><h3>Deine Schrift</h3><div id="fontChoices" class="font-choices" role="group" aria-label="Schrift auswählen">${FONTS.map(f => `<button class="font-choice" data-personal-font="${fontId(f)}" aria-pressed="${fontId(f) === d.fontId}"><strong>${studioEscape(f.name)}</strong><span style="font-family:${studioEscape(f.family)}"></span></button>`).join('')}</div><button class="action primary" id="saveDraft">${d.id ? 'Änderungen speichern' : 'In Designmappe speichern'}</button><button class="action" id="cancelDraft">Abbrechen</button><p id="editorError" role="alert"></p></div></div></section>`;
    document.getElementById('wishText').value = d.text;
    document.getElementById('wishText').addEventListener('input', e => { d.text = e.target.value; personal.dirty = true; personalUpdate(); });
    document.getElementById('chooseMotif').onclick = personalPick;
    document.getElementById('saveDraft').onclick = personalSave;
    document.getElementById('cancelDraft').onclick = () => studioNavigate('map');
    document.querySelectorAll('[data-personal-font]').forEach(btn => btn.onclick = () => { d.fontId = btn.dataset.personalFont; personal.dirty = true; personalUpdate(); });
    personalUpdate();
}
let fontRequest = 0;
function personalUpdate() {
    const d = personal.current;
    const font = personalFont(d.fontId);
    document.getElementById('compositionPreview').innerHTML = personalPreview(d, true);
    personalImages();
    const count = Array.from(d.text).length;
    document.getElementById('textAdvice').textContent = `${count} Zeichen · ${count > 80 || d.text.split('\n').length > 2 ? 'Bei längeren Texten oder vielen Zeilen kann die Schrift auf dem fertigen Produkt zu klein werden. Prüfe die Lesbarkeit gemeinsam mit uns. Dein Text wird vollständig gespeichert.' : 'Zeilenumbrüche sind möglich. Bitte prüfe Schreibweise und Lesbarkeit.'}`;
    document.querySelectorAll('[data-personal-font]').forEach(btn => {
        btn.setAttribute('aria-pressed', String(btn.dataset.personalFont === d.fontId));
        btn.querySelector('span').textContent = d.text || 'Dein Wunschtext';
    });
    const status = document.getElementById('fontStatus');
    status.textContent = 'Schrift wird geprüft …';
    const request = ++fontRequest;
    const timer = setTimeout(() => {
        if (request === fontRequest && status.isConnected) status.textContent = 'Schrift lädt noch. Bis dahin wird eine Ersatzschrift angezeigt.';
    }, 4000);
    document.fonts.load(`400 24px "${font.name}"`).then(loaded => {
        clearTimeout(timer);
        if (request === fontRequest && status.isConnected) status.textContent = loaded.length ? '' : 'Originalschrift gerade nicht verfügbar. Eine Ersatzschrift wird angezeigt.';
    }).catch(() => { clearTimeout(timer); if (request === fontRequest && status.isConnected) status.textContent = 'Originalschrift nicht geladen. Eine Ersatzschrift wird angezeigt.'; });
}
function personalSave() {
    const d = personal.current;
    const error = document.getElementById('editorError');
    if (!studio.catalog.some(m => m.id === d.motifId)) { error.textContent = 'Bitte wähle zuerst ein Motiv aus.'; return; }
    if (!d.text.trim()) { error.textContent = 'Bitte gib deinen Wunschtext ein.'; document.getElementById('wishText').focus(); return; }
    const motif = studio.catalog.find(m => m.id === d.motifId);
    const now = new Date().toISOString();
    const existing = personal.drafts.find(item => item.id === d.id);
    const saved = { id: d.id || crypto.randomUUID(), motifId: d.motifId, motifName: motif.name, category: motif.category, text: d.text, fontId: d.fontId, layoutVersion: 1, createdAt: existing?.createdAt || now, updatedAt: now };
    const list = existing ? personal.drafts.map(item => item.id === d.id ? saved : item) : [...personal.drafts, saved];
    if (!mapWrite(list)) { error.textContent = document.getElementById('personalStatus').textContent; return; }
    personal.current = null; personal.dirty = false; personal.picking = false;
    studioNavigate('map'); personalNotice('Entwurf auf diesem Gerät gespeichert. Du kannst weitere Entwürfe hinzufügen.');
}
function mapEdit(id) {
    const d = personal.drafts.find(item => item.id === id);
    if (!d) return;
    personal.current = { ...d }; personal.dirty = false; personal.picking = false;
    studioNavigate('editor');
}
function mapDuplicate(id) {
    const d = personal.drafts.find(item => item.id === id);
    if (!d) return;
    const now = new Date().toISOString();
    if (mapWrite([...personal.drafts, { ...d, id: crypto.randomUUID(), createdAt: now, updatedAt: now }])) { mapRender(); studioNavigation(); personalNotice('Entwurf dupliziert. Über „Bearbeiten“ kannst du die Variante anpassen.'); }
}
function mapDelete(id) {
    if (!confirm('Diesen Entwurf aus der Designmappe löschen?')) return;
    if (mapWrite(personal.drafts.filter(d => d.id !== id))) { personal.compare = personal.compare.filter(value => value !== id); mapRender(); studioNavigation(); personalNotice('Entwurf gelöscht.'); }
}
function mapRender() {
    personal.compare = personal.compare.filter(id => personal.drafts.some(d => d.id === id));
    document.getElementById('content').innerHTML = `<section class="page-wrap personal-page"><div class="eyebrow">Deine Ideen an einem Ort</div><div class="page-heading"><div><h1>Deine Designmappe</h1><p>Nur auf diesem Gerät gespeichert. Bitte vor dem nächsten Kunden eine neue Beratung starten.</p></div><span class="heading-count">${personal.drafts.length} Entwürfe</span></div><div class="map-toolbar"><button class="action primary" onclick="personalStart('')">Weiteren Entwurf gestalten</button><button class="action" id="compareDrafts" ${personal.compare.length !== 2 ? 'disabled' : ''}>Zwei Entwürfe vergleichen (${personal.compare.length}/2)</button></div><p id="mapFontStatus" role="status"></p><div id="comparison"></div>${personal.drafts.length ? `<div class="map-grid">${personal.drafts.map(d => `<article class="draft-card">${personalPreview(d)}<div class="draft-info"><h2>${studioEscape(studioPrettyName(d.motifName || studio.catalog.find(m => m.id === d.motifId)?.name || 'Motiv'))}</h2><p>${studioEscape(personalFont(d.fontId).name)} · ${studioEscape(studioLabel(d.category || ''))}</p><label class="compare-choice"><input type="checkbox" data-compare="${studioEscape(d.id)}" ${personal.compare.includes(d.id) ? 'checked' : ''}> Zum Vergleich auswählen</label><div class="draft-actions"><button class="action" data-edit="${studioEscape(d.id)}">Bearbeiten</button><button class="action" data-duplicate="${studioEscape(d.id)}">Duplizieren</button><button class="action danger" data-delete="${studioEscape(d.id)}">Löschen</button></div></div></article>`).join('')}</div>` : '<div class="empty-state"><h2>Hier beginnt deine Sammlung.</h2><p>Wähle ein Motiv, ergänze deinen Text und speichere deinen ersten Entwurf.</p></div>'}</section>`;
    for (const [attr, handler] of [['edit', mapEdit], ['duplicate', mapDuplicate], ['delete', mapDelete]]) document.querySelectorAll(`[data-${attr}]`).forEach(btn => btn.onclick = () => handler(btn.dataset[attr]));
    document.querySelectorAll('[data-compare]').forEach(box => box.onchange = () => {
        if (box.checked && personal.compare.length === 2) { box.checked = false; personalNotice('Bitte zuerst einen Entwurf abwählen. Du kannst zwei Entwürfe gleichzeitig vergleichen.'); return; }
        personal.compare = box.checked ? [...personal.compare, box.dataset.compare] : personal.compare.filter(id => id !== box.dataset.compare);
        const btn = document.getElementById('compareDrafts'); btn.disabled = personal.compare.length !== 2; btn.textContent = `Zwei Entwürfe vergleichen (${personal.compare.length}/2)`;
        document.getElementById('comparison').replaceChildren();
    });
    document.getElementById('compareDrafts').onclick = mapCompare;
    personalImages();
    mapFontStatus();
    if (personal.blocked) personalNotice(personal.message);
}
function mapFontStatus() {
    const el = document.getElementById('mapFontStatus');
    const fonts = [...new Set(personal.drafts.map(d => d.fontId))].map(personalFont);
    if (!fonts.length) return;
    el.textContent = 'Schriften werden geprüft …';
    Promise.all(fonts.map(font => Promise.race([
        document.fonts.load(`400 24px "${font.name}"`).then(loaded => loaded.length ? null : font.name).catch(() => font.name),
        new Promise(resolve => setTimeout(() => resolve(font.name), 4000))
    ]))).then(missing => {
        if (!el.isConnected) return;
        const names = missing.filter(Boolean);
        el.textContent = names.length ? `Originalschriften gerade nicht verfügbar: ${names.join(', ')}. Die Vorschau zeigt Ersatzschriften; deine Schriftauswahl bleibt gespeichert.` : '';
    });
}
function mapCompare() {
    const list = personal.compare.map(id => personal.drafts.find(d => d.id === id)).filter(Boolean);
    if (list.length !== 2) return;
    const el = document.getElementById('comparison');
    el.innerHTML = `<section class="comparison-panel" aria-label="Entwürfe vergleichen"><h2>Zwei Ideen im Vergleich</h2><div class="comparison-grid">${list.map((d, i) => `<article><h3>Variante ${i + 1} · ${studioEscape(personalFont(d.fontId).name)}</h3>${personalPreview(d, true)}<p>${studioEscape(studioPrettyName(d.motifName || 'Motiv'))}</p><button class="action" data-compare-edit="${studioEscape(d.id)}">Variante ${i + 1} bearbeiten</button></article>`).join('')}</div><button class="action" id="closeComparison">Vergleich schliessen</button></section>`;
    el.querySelectorAll('[data-compare-edit]').forEach(btn => btn.onclick = () => mapEdit(btn.dataset.compareEdit));
    document.getElementById('closeComparison').onclick = () => el.replaceChildren();
    personalImages(); el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function newConsultation() {
    if (!confirm('Neue Beratung starten? Alle Entwürfe, Favoriten, Wunschtexte, Testformulardaten und die aktuelle Auswahl werden auf diesem Gerät gelöscht. Das kann nicht rückgängig gemacht werden.')) return;
    let oldMap;
    try {
        oldMap = localStorage.getItem(MAP_KEY);
        const value = JSON.stringify({ version: 1, epoch: crypto.randomUUID(), drafts: [] });
        localStorage.setItem(MAP_KEY, value);
        try { localStorage.removeItem('timberart-favorites'); } catch (error) {
            if (oldMap === null) localStorage.removeItem(MAP_KEY); else localStorage.setItem(MAP_KEY, oldMap);
            throw error;
        }
        personal.lastRaw = value; personal.epoch = JSON.parse(value).epoch;
    } catch (_) { personalNotice('Zurücksetzen nicht möglich: Der Browserspeicher ist gesperrt. Bitte verwende das Gerät erst nach erfolgreichem Zurücksetzen für den nächsten Kunden.'); return; }
    personal.drafts = []; personal.current = null; personal.dirty = false; personal.picking = false; personal.compare = []; personal.blocked = false;
    favorites = []; selectedFont = null; selectedDesign = null; studio.returnFocus = null;
    document.querySelectorAll('.modal.active').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('form').forEach(form => form.reset());
    document.querySelectorAll('.preview-order-status').forEach(el => el.remove());
    document.getElementById('customText').value = '';
    for (const id of ['livePreview', 'alphabetPreview', 'selectedFontName', 'selection-summary', 'modalTitle', 'modalCategory', 'designName', 'designCat']) document.getElementById(id).replaceChildren();
    document.getElementById('modalImage').removeAttribute('src'); document.getElementById('designLink').removeAttribute('href');
    studioNavigate('home'); personalNotice('Neue Beratung gestartet. Alle vorherigen Kundenauswahlen wurden zurückgesetzt.');
}
mapRead();
try { personal.lastRaw = localStorage.getItem(MAP_KEY); } catch (_) { personal.lastRaw = null; }
window.addEventListener('beforeunload', event => { if (personal.dirty) { event.preventDefault(); event.returnValue = ''; } });
window.addEventListener('storage', event => {
    if (event.key !== MAP_KEY && event.key !== 'timberart-favorites' && event.key !== null) return;
    // Another tab may have started a new consultation: never retain the old customer's visible state.
    personal.dirty = false; location.reload();
});
