/* Local-only personalisation. No order or customer data leaves this browser. */
const MAP_KEY = 'timberart-designmappe-v1';
const personal = { drafts: [], current: null, dirty: false, picking: false, compare: [], blocked: false, epoch: '', message: '', storageVersion: 1 };
const fontId = font => font.name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
const personalFont = id => FONTS.find(font => fontId(font) === id) || FONTS[0];
function parseMap(raw) {
    const data = JSON.parse(raw);
    if (![1, 2].includes(data?.version) || !Array.isArray(data.drafts) || typeof data.epoch !== 'string') throw Error('Invalid map');
    const ids = new Set();
    for (const d of data.drafts) {
        if (!d || typeof d.id !== 'string' || ids.has(d.id) || typeof d.motifId !== 'string' || typeof d.text !== 'string' || !FONTS.some(f => fontId(f) === d.fontId) || typeof d.createdAt !== 'string' || typeof d.updatedAt !== 'string') throw Error('Invalid draft');
        if (d.layoutVersion != null && ![1, 2, 3].includes(d.layoutVersion)) throw Error('Invalid layout');
        if (d.layoutVersion === 3 && (data.version !== 2 || !validTextFrame(d.textFrame) || 'transform' in d)) throw Error('Invalid frame');
        if (d.layoutVersion === 2) {
            if (!d.transform || !['x', 'y', 'scale', 'rotation'].every(key => typeof d.transform[key] === 'number' && Number.isFinite(d.transform[key]))) throw Error('Invalid transform');
            d.transform = textTransform(d.transform);
        }
        ids.add(d.id);
    }
    return data;
}
function mapAdopt(data, raw) {
    personal.drafts = data.drafts;
    personal.epoch = data.epoch;
    personal.storageVersion = data.version;
    personal.lastRaw = raw;
    personal.blocked = false;
    personal.message = '';
}
function mapRead() {
    let raw;
    try {
        raw = localStorage.getItem(MAP_KEY);
        if (!raw) { personal.epoch = crypto.randomUUID(); personal.lastRaw = raw; return; }
        mapAdopt(parseMap(raw), raw);
    } catch (_) {
        personal.lastRaw = raw;
        personal.blocked = true;
        personal.message = 'Die lokale Designmappe kann nicht gelesen werden. Vorhandene Daten werden nicht überschrieben. Starte bei Bedarf nach Bestätigung eine neue Beratung.';
    }
}
let mapWritesPending = 0;
let resetPending = false;
async function mapSnapshotKey(raw) {
    const bytes = new TextEncoder().encode(JSON.stringify({raw}));
    return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(n => n.toString(16).padStart(2,'0')).join('');
}
async function mapGuardDatabase() {
    return new Promise((resolve,reject) => {
        let blocked = false;
        const request = indexedDB.open('timberart-map-write-guards',1);
        request.onupgradeneeded = () => request.result.createObjectStore('usedSnapshots');
        request.onsuccess = () => { if (blocked) request.result.close(); else resolve(request.result); };
        request.onerror = () => reject(request.error);
        request.onblocked = () => { blocked = true; reject(Error('Storage blocked')); };
    });
}
async function mapSnapshotUsed(raw) {
    const key = await mapSnapshotKey(raw), db = await mapGuardDatabase();
    try {
        return await new Promise((resolve,reject) => {
            const request = db.transaction('usedSnapshots').objectStore('usedSnapshots').get(key);
            request.onsuccess = () => resolve(request.result === true);
            request.onerror = () => reject(request.error);
        });
    } finally { db.close(); }
}
async function mapGuardedWrite(operation, expected) {
    // Some engines can expose a stale localStorage cache even after a lock grant.
    // Atomically consume each base snapshot once, using only an opaque SHA-256 key.
    const key = await mapSnapshotKey(expected), db = await mapGuardDatabase();
    try {
        return await new Promise((resolve,reject) => {
            const transaction = db.transaction('usedSnapshots','readwrite');
            const store = transaction.objectStore('usedSnapshots');
            const abort = () => { try { transaction.abort(); } catch (_) { /* already aborted by the browser */ } };
            let result = false, failure, writtenRaw, before, favoritesBefore;
            const read = store.get(key);
            read.onsuccess = () => {
                if (read.result) { failure = Error('Snapshot already replaced'); abort(); return; }
                before = {drafts:personal.drafts,epoch:personal.epoch,lastRaw:personal.lastRaw,storageVersion:personal.storageVersion,blocked:personal.blocked,message:personal.message};
                try {
                    favoritesBefore = localStorage.getItem('timberart-favorites');
                    result = operation();
                    if (!result) { abort(); return; }
                    writtenRaw = personal.lastRaw;
                    if (writtenRaw !== expected) store.add(true,key);
                } catch (error) { failure = error; abort(); }
            };
            transaction.oncomplete = () => resolve(result);
            transaction.onabort = () => {
                // Roll back our mirror if the guard transaction could not commit.
                if (writtenRaw !== undefined) {
                    try {
                        if (localStorage.getItem(MAP_KEY) === writtenRaw) {
                            if (expected == null) localStorage.removeItem(MAP_KEY); else localStorage.setItem(MAP_KEY,expected);
                            if (favoritesBefore !== null && localStorage.getItem('timberart-favorites') === null) localStorage.setItem('timberart-favorites',favoritesBefore);
                            Object.assign(personal,before);
                        }
                    } catch (_) { /* preserve the editor and report failure; never claim success */ }
                }
                if (failure || transaction.error) reject(failure || transaction.error); else resolve(false);
            };
        });
    } finally { db.close(); }
}
async function mapLocked(operation) {
    const expected = personal.lastRaw;
    if (!navigator.locks?.request || !globalThis.indexedDB || !crypto.subtle) {
        personalNotice('Nicht gespeichert: Dieser Browser unterstützt keine sichere Mehrfenster-Speicherung. Bitte einen aktuellen Browser über HTTPS verwenden. Dein Entwurf bleibt geöffnet.');
        return false;
    }
    mapWritesPending++;
    try { return await navigator.locks.request(MAP_KEY, () => mapGuardedWrite(operation,expected)); }
    catch (_) { personalNotice('Nicht gespeichert: Der Browserspeicher ist gesperrt oder wurde in einem anderen Fenster verändert. Dein aktueller Entwurf bleibt geöffnet.'); return false; }
    finally { mapWritesPending--; }
}
async function mapWrite(drafts) {
    if (resetPending) { personalNotice('Neue Beratung wird bereits vorbereitet. Bitte warten; es wurde nichts zusätzlich gespeichert.'); return false; }
    const expected = personal.lastRaw;
    return mapLocked(() => {
        if (personal.blocked) { personalNotice(personal.message); return false; }
        // Capture the base BEFORE waiting for the lock, not after another tab's update.
        if (localStorage.getItem(MAP_KEY) !== expected) throw Error('changed');
        const version = drafts.some(d => d.layoutVersion === 3) ? 2 : personal.storageVersion;
        const value = JSON.stringify({ version, epoch: personal.epoch, drafts });
        localStorage.setItem(MAP_KEY, value);
        personal.lastRaw = value;
        personal.drafts = drafts;
        personal.storageVersion = version;
        return true;
    });
}
let consultationReloading = false;
function reloadConsultation() {
    if (!consultationReloading) { consultationReloading = true; personal.dirty = false; location.reload(); }
    return 'reset';
}
function mapReconcile(event) {
    if (consultationReloading) return 'reset';
    try {
        const raw = localStorage.getItem(MAP_KEY);
        if (raw === personal.lastRaw) return 'same';
        if (raw === null) {
            // Explicit browser-storage clearing is also a privacy boundary.
            return reloadConsultation();
        }
        const data = parseMap(raw);
        let resetEvent = false;
        if (event?.key === MAP_KEY && event.newValue) {
            try { const snapshot = parseMap(event.newValue); resetEvent = snapshot.reset === true && snapshot.epoch === data.epoch; } catch (_) { /* validate the current value, not an obsolete event */ }
        }
        if (data.epoch !== personal.epoch && (personal.lastRaw !== null || data.reset === true || resetEvent || data.drafts.length === 0)) {
            return reloadConsultation();
        }
        if (personal.current) {
            personalNotice('Die Designmappe wurde in einem anderen Fenster geändert. Dein aktueller Entwurf bleibt erhalten. Speichern ist bis zur Klärung gesperrt. Nach bewusstem Verlassen des Entwurfs wird der neue Stand geladen.');
            return 'conflict';
        }
        mapAdopt(data, raw);
        return 'adopted';
    } catch (_) {
        personal.blocked = true;
        personal.message = 'Die geänderte Designmappe kann nicht gelesen werden. Dein aktueller Entwurf bleibt erhalten; vorhandene Daten werden nicht überschrieben.';
        personalNotice(personal.message);
        return 'invalid';
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
    mapReconcile();
    return true;
}
function personalStart(motifId, seed) {
    if (personal.current && !personal.picking && personal.dirty && !confirm('Aktuellen ungespeicherten Entwurf verwerfen?')) return;
    const current = personal.picking && personal.current ? personal.current : { id: null, text: seed?.text || '', fontId: seed?.fontId || fontId(FONTS[0]), layoutVersion: 3, textFrame: copyTextFrame() };
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
function personalMissingMotif(d) {
    return `<p class="asset-warning" role="status">${d.motifId ? 'Das gespeicherte Motiv ist derzeit nicht im Katalog verfügbar. Text, Motivzuordnung und Einstellungen bleiben erhalten. Bitte Katalogverbindung prüfen oder bewusst ein anderes Motiv wählen.' : 'Bitte ein Motiv auswählen.'}</p>`;
}
function personalPreview(d, full = false, editable = false) {
    if (d.layoutVersion === 3) return framePreview(d, full, editable);
    if (d.layoutVersion === 2) return transformPreview(d, full, editable);
    const motif = studio.catalog.find(m => m.id === d.motifId);
    const font = personalFont(d.fontId);
    return `<div class="composition ${full ? 'composition-large' : ''}">${motif ? `${motifImageTag(motif, {detail:full, sizes:full ? "(max-width:760px) 75vw, 40vw" : "(max-width:760px) 75vw, 28vw"})}<span class="asset-warning" hidden>Motivbild nicht erreichbar. Die Auswahl bleibt gespeichert.</span>` : personalMissingMotif(d)}<div class="composition-text" tabindex="0" role="region" aria-label="Wunschtextvorschau, bei langen Texten scrollbar" style="font-family:${studioEscape(font.family)}">${studioEscape(d.text || 'Dein Wunschtext')}</div></div>`;
}
function personalImages() {
    transformMount();
    document.querySelectorAll('.composition img').forEach(img => img.addEventListener('error', () => { img.hidden = true; img.nextElementSibling.hidden = false; }, { once: true }));
}
function personalEditor() {
    if (!personal.current) { personal.current = { id: null, motifId: '', text: '', fontId: fontId(FONTS[0]), layoutVersion: 3, textFrame: copyTextFrame() }; }
    if (personal.current.layoutVersion === 2) personal.current.transform = textTransform(personal.current.transform);
    personal.picking = false;
    studioNavigation();
    const d = personal.current;
    const motif = studio.catalog.find(m => m.id === d.motifId);
    document.getElementById('content').innerHTML = `<section class="page-wrap personal-page"><div class="eyebrow">Dein persönlicher Entwurf</div><h1>Mach es zu deinem Geschenk.</h1><ol class="personal-steps"><li>1 · Motiv wählen</li><li>2 · Text & Schrift</li><li>3 · In der Mappe speichern</li></ol><div class="personal-layout"><div><div id="compositionPreview">${personalPreview(d, true, true)}</div>${d.layoutVersion === 2 ? transformControls() : ''}<p class="personal-caption">Gestaltungsvorschau · keine massstabsgetreue Gravurvorlage</p><p id="fontStatus" role="status"></p></div><div class="personal-controls"><h2>Deine Gestaltung</h2><p>${motif ? studioEscape(studioPrettyName(motif.name)) + ' · ' + studioEscape(studioLabel(motif.category)) : 'Noch kein Motiv ausgewählt'}</p><button class="action" id="chooseMotif">${motif ? 'Motiv wechseln' : 'Motiv auswählen'}</button><label for="wishText">Dein Wunschtext</label><textarea id="wishText" rows="4" aria-describedby="textAdvice" placeholder="Zum Beispiel: Für dich, von Herzen"></textarea><p id="textAdvice" class="personal-help" role="status"></p>${d.layoutVersion === 3 ? frameControls() : ''}<h3>Deine Schrift</h3><div id="fontChoices" class="font-choices" role="group" aria-label="Schrift auswählen">${FONTS.map(f => `<button class="font-choice" data-personal-font="${fontId(f)}" aria-pressed="${fontId(f) === d.fontId}"><strong>${studioEscape(f.name)}</strong><span style="font-family:${studioEscape(f.family)}"></span></button>`).join('')}</div><button class="action primary" id="saveDraft">${d.id ? 'Änderungen speichern' : 'In Designmappe speichern'}</button><button type="button" class="action" data-inquiry="current">Design an TimberArt senden</button><button class="action" id="cancelDraft">Abbrechen</button><p id="editorError" role="alert"></p></div></div></section>`;
    document.getElementById('wishText').value = d.text;
    document.getElementById('wishText').addEventListener('input', e => { d.text = e.target.value; personal.dirty = true; personalUpdate(); });
    document.getElementById('chooseMotif').onclick = personalPick;
    document.getElementById('saveDraft').onclick = personalSave;
    document.getElementById('cancelDraft').onclick = () => studioNavigate('map');
    document.querySelectorAll('[data-personal-font]').forEach(btn => btn.onclick = () => { d.fontId = btn.dataset.personalFont; personal.dirty = true; personalUpdate(); });
    if (d.layoutVersion === 3) frameBindControls();
    else if (d.layoutVersion === 2) transformBindControls();
    personalUpdate();
    if (d.layoutVersion !== 3) personalNotice('Älterer Entwurf: Das bisherige Layout bleibt erhalten. Es findet keine Umstellung auf das neue Rahmenmodell statt.');
}
let fontRequest = 0;
function personalUpdate() {
    const d = personal.current;
    const font = personalFont(d.fontId);
    if (d.layoutVersion === 3 && document.querySelector('#compositionPreview .frame-v3')) frameUpdatePreview(d);
    else document.getElementById('compositionPreview').innerHTML = personalPreview(d, true, true);
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
        if (request === fontRequest && status.isConnected) { status.textContent = loaded.length ? '' : 'Originalschrift gerade nicht verfügbar. Eine Ersatzschrift wird angezeigt.'; transformSync(); }
    }).catch(() => { clearTimeout(timer); if (request === fontRequest && status.isConnected) { status.textContent = 'Originalschrift nicht geladen. Eine Ersatzschrift wird angezeigt.'; frameRefreshChecks(); } });
}
let savingDraft = false;
async function personalSave() {
    if (savingDraft) { personalNotice('Speichern läuft bereits. Dein Entwurf bleibt geöffnet.'); return; }
    const d = personal.current;
    const error = document.getElementById('editorError');
    if (!studio.catalog.some(m => m.id === d.motifId)) { error.textContent = 'Bitte wähle zuerst ein Motiv aus.'; return; }
    if (!d.text.trim()) { error.textContent = 'Bitte gib deinen Wunschtext ein.'; document.getElementById('wishText').focus(); return; }
    const motif = studio.catalog.find(m => m.id === d.motifId);
    const now = new Date().toISOString();
    const existing = personal.drafts.find(item => item.id === d.id);
    const layout = d.layoutVersion === 3 ? { layoutVersion: 3, textFrame: copyTextFrame(d.textFrame) } : d.layoutVersion === 2 ? { layoutVersion: 2, transform: textTransform(d.transform) } : { layoutVersion: d.layoutVersion || 1 };
    const saved = { id: d.id || crypto.randomUUID(), motifId: d.motifId, motifName: motif.name, category: motif.category, text: d.text, fontId: d.fontId, ...layout, createdAt: existing?.createdAt || now, updatedAt: now };
    const list = existing ? personal.drafts.map(item => item.id === d.id ? saved : item) : [...personal.drafts, saved];
    const snapshot = JSON.stringify(d);
    savingDraft = true;
    personalNotice('Speichern läuft … Dein aktueller Entwurf bleibt geöffnet.');
    let ok;
    try { ok = await mapWrite(list); } finally { savingDraft = false; }
    if (!ok) {
        const reason = document.getElementById('personalStatus').textContent;
        if (error.isConnected) error.textContent = reason.startsWith('Nicht gespeichert:') ? reason : `Nicht gespeichert: ${reason}`;
        return;
    }
    if (personal.current !== d) return;
    if (JSON.stringify(d) !== snapshot) {
        d.id = saved.id;
        personalNotice('Der Stand beim Klick wurde gespeichert. Deine neueren Änderungen bleiben geöffnet und sind noch nicht gespeichert.');
        return;
    }
    personal.current = null; personal.dirty = false; personal.picking = false;
    studioNavigate('map'); personalNotice('Entwurf auf diesem Gerät gespeichert. Du kannst weitere Entwürfe hinzufügen.');
}
function mapEdit(id) {
    const d = personal.drafts.find(item => item.id === id);
    if (!d) return;
    personal.current = { ...d, ...(d.transform ? { transform: { ...d.transform } } : {}), ...(d.textFrame ? { textFrame: copyTextFrame(d.textFrame) } : {}) }; personal.dirty = false; personal.picking = false;
    studioNavigate('editor');
}
async function mapDuplicate(id) {
    const d = personal.drafts.find(item => item.id === id);
    if (!d) return;
    const now = new Date().toISOString();
    if (await mapWrite([...personal.drafts, { ...d, ...(d.transform ? { transform: { ...d.transform } } : {}), ...(d.textFrame ? { textFrame: copyTextFrame(d.textFrame) } : {}), id: crypto.randomUUID(), createdAt: now, updatedAt: now }])) { if(studio.view === 'map') mapRender(); studioNavigation(); personalNotice('Entwurf dupliziert. Über „Bearbeiten“ kannst du die Variante anpassen.'); }
}
async function mapDelete(id) {
    if (!confirm('Diesen Entwurf aus der Designmappe löschen?')) return;
    if (await mapWrite(personal.drafts.filter(d => d.id !== id))) { personal.compare = personal.compare.filter(value => value !== id); if(studio.view === 'map') mapRender(); studioNavigation(); personalNotice('Entwurf gelöscht.'); }
}
function mapRender() {
    personal.compare = personal.compare.filter(id => personal.drafts.some(d => d.id === id));
    document.getElementById('content').innerHTML = `<section class="page-wrap personal-page"><div class="eyebrow">Deine Ideen an einem Ort</div><div class="page-heading"><div><h1>Deine Designmappe</h1><p>Nur auf diesem Gerät gespeichert. Bitte vor dem nächsten Kunden eine neue Beratung starten.</p></div><span class="heading-count">${personal.drafts.length} Entwürfe</span></div><div class="map-toolbar"><button class="action primary" onclick="personalStart('')">Weiteren Entwurf gestalten</button><button class="action" id="compareDrafts" ${personal.compare.length !== 2 ? 'disabled' : ''}>Zwei Entwürfe vergleichen (${personal.compare.length}/2)</button></div><p id="mapFontStatus" role="status"></p><div id="comparison"></div>${personal.drafts.length ? `<div class="map-grid">${personal.drafts.map(d => `<article class="draft-card">${personalPreview(d)}<div class="draft-info"><h2>${studioEscape(studioPrettyName(d.motifName || studio.catalog.find(m => m.id === d.motifId)?.name || 'Motiv'))}</h2><p>${studioEscape(personalFont(d.fontId).name)} · ${studioEscape(studioLabel(d.category || ''))}</p><label class="compare-choice"><input type="checkbox" data-compare="${studioEscape(d.id)}" ${personal.compare.includes(d.id) ? 'checked' : ''}> Zum Vergleich auswählen</label><div class="draft-actions"><button class="action" data-edit="${studioEscape(d.id)}">Bearbeiten</button><button class="action" data-duplicate="${studioEscape(d.id)}">Duplizieren</button><button type="button" class="action" data-inquiry="${studioEscape(d.id)}">Design an TimberArt senden</button><button class="action danger" data-delete="${studioEscape(d.id)}">Löschen</button></div></div></article>`).join('')}</div>` : '<div class="empty-state"><h2>Hier beginnt deine Sammlung.</h2><p>Wähle ein Motiv, ergänze deinen Text und speichere deinen ersten Entwurf.</p></div>'}</section>`;
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
    if (!el || !fonts.length) return;
    el.textContent = 'Schriften werden geprüft …';
    const states = new Map(fonts.map(font => [font.name, 'pending']));
    let timedOut = false;
    const update = () => {
        if (!el.isConnected) return;
        const missing = [...states].filter(([,state]) => state === 'missing').map(([name]) => name);
        const pending = [...states.values()].includes('pending');
        el.textContent = [missing.length ? `Originalschriften gerade nicht verfügbar: ${missing.join(', ')}. Die Vorschau zeigt Ersatzschriften; deine Schriftauswahl bleibt gespeichert.` : '', pending ? (timedOut ? 'Schriften laden noch. Bis dahin werden Ersatzschriften angezeigt.' : 'Schriften werden geprüft …') : ''].filter(Boolean).join(' ');
        frameRefreshChecks();
    };
    const timer = setTimeout(() => { timedOut = true; update(); }, 4000);
    const requests = fonts.map(font => document.fonts.load(`400 24px "${font.name}"`).then(loaded => {
        states.set(font.name, loaded.length ? 'loaded' : 'missing'); update();
    }, () => { states.set(font.name, 'missing'); update(); }));
    Promise.all(requests).then(() => clearTimeout(timer));
}
// A later retry/CSS font load may not be the same promise as our first request.
function personalFontsChanged() {
    frameRefreshChecks();
    if (studio.view === 'editor' && personal.current) {
        const status = document.getElementById('fontStatus');
        const request = fontRequest, font = personalFont(personal.current.fontId);
        document.fonts.load(`400 24px "${font.name}"`).then(loaded => {
            if (status?.isConnected && request === fontRequest) status.textContent = loaded.length ? '' : 'Originalschrift gerade nicht verfügbar. Eine Ersatzschrift wird angezeigt.';
            frameRefreshChecks();
        }, () => { if (status?.isConnected && request === fontRequest) status.textContent = 'Originalschrift nicht geladen. Eine Ersatzschrift wird angezeigt.'; frameRefreshChecks(); });
    }
    if (studio.view === 'map') mapFontStatus();
}
document.fonts.addEventListener('loadingdone', personalFontsChanged);
document.fonts.addEventListener('loadingerror', personalFontsChanged);
function mapCompare() {
    const list = personal.compare.map(id => personal.drafts.find(d => d.id === id)).filter(Boolean);
    if (list.length !== 2) return;
    const el = document.getElementById('comparison');
    el.innerHTML = `<section class="comparison-panel" aria-label="Entwürfe vergleichen"><h2>Zwei Ideen im Vergleich</h2><div class="comparison-grid">${list.map((d, i) => `<article><h3>Variante ${i + 1} · ${studioEscape(personalFont(d.fontId).name)}</h3>${personalPreview(d, true)}<p>${studioEscape(studioPrettyName(d.motifName || 'Motiv'))}</p><button class="action" data-compare-edit="${studioEscape(d.id)}">Variante ${i + 1} bearbeiten</button></article>`).join('')}</div><button class="action" id="closeComparison">Vergleich schliessen</button></section>`;
    el.querySelectorAll('[data-compare-edit]').forEach(btn => btn.onclick = () => mapEdit(btn.dataset.compareEdit));
    document.getElementById('closeComparison').onclick = () => el.replaceChildren();
    personalImages(); el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
async function newConsultation() {
    if (resetPending || mapWritesPending) { personalNotice('Ein Speichervorgang läuft noch. Bitte danach die neue Beratung starten.'); return; }
    if (!confirm('Neue Beratung starten? Alle Entwürfe, Favoriten, Wunschtexte, Testformulardaten und die aktuelle Auswahl werden auf diesem Gerät gelöscht. Das kann nicht rückgängig gemacht werden.')) return;
    const expected = personal.lastRaw;
    let reset;
    resetPending = true;
    try { reset = await mapLocked(() => {
        let oldMap;
        try {
            oldMap = localStorage.getItem(MAP_KEY);
            if (oldMap !== expected) throw Error('changed');
            const value = JSON.stringify({ version: 1, epoch: crypto.randomUUID(), drafts: [], reset: true });
            localStorage.setItem(MAP_KEY, value);
            try { localStorage.removeItem('timberart-favorites'); } catch (error) {
                if (oldMap === null) localStorage.removeItem(MAP_KEY); else localStorage.setItem(MAP_KEY, oldMap);
                throw error;
            }
            personal.lastRaw = value; personal.epoch = JSON.parse(value).epoch; personal.storageVersion = 1;
        } catch (_) { personalNotice('Zurücksetzen nicht möglich: Der Browserspeicher ist gesperrt. Bitte lade den aktuellen Stand neu und verwende das Gerät erst nach erfolgreichem Zurücksetzen für den nächsten Kunden.'); return; }
        return true;
    }); } finally { resetPending = false; }
    if (!reset) return;
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
window.addEventListener('beforeunload', event => { if (personal.dirty) { event.preventDefault(); event.returnValue = ''; } });
window.addEventListener('storage', async event => {
    if (event.storageArea !== localStorage || (event.key !== MAP_KEY && event.key !== 'timberart-favorites' && event.key !== null)) return;
    // Do not clear another tab for a reset whose guard transaction later aborts.
    if (event.key === MAP_KEY && event.newValue) {
        let snapshot;
        try { snapshot = parseMap(event.newValue); } catch (_) { /* reconciliation reports invalid data */ }
        if (snapshot?.reset === true) {
            try {
                const committed = await navigator.locks.request(MAP_KEY, {mode:'shared'}, () => mapSnapshotUsed(event.oldValue));
                if (!committed) return;
            } catch (_) { personalNotice('Beratungsreset nicht bestätigt. Dein aktueller Entwurf bleibt geöffnet.'); return; }
        }
    }
    const result = event.key === 'timberart-favorites' ? 'same' : mapReconcile(event);
    if (result === 'reset') return;
    try { loadFavorites(); } catch (_) { favorites = []; }
    if (!Array.isArray(favorites) || !favorites.every(id => typeof id === 'string')) favorites = [];
    studioNavigation();
    if (studio.view === 'motifs' || studio.view === 'favorites') studioResults();
    if (result === 'adopted' && studio.view === 'map') mapRender();
});
