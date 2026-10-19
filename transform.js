/* One fixed design space keeps saved compositions consistent at every screen size. */
const DESIGN_SIZE = 600;
const TEXT_DEFAULT = Object.freeze({ x: 0.5, y: 0.8, scale: 1, rotation: 0 });
const transformClamp = (value, min, max) => Math.min(max, Math.max(min, value));
function textTransform(value = {}) {
    const number = (key, fallback) => typeof value?.[key] === 'number' && Number.isFinite(value[key]) ? value[key] : fallback;
    const rotation = number('rotation', 0);
    const round = n => Math.round(n * 100000) / 100000;
    return {
        x: round(transformClamp(number('x', TEXT_DEFAULT.x), 0.06, 0.94)),
        y: round(transformClamp(number('y', TEXT_DEFAULT.y), 0.06, 0.94)),
        scale: round(transformClamp(number('scale', 1), 0.25, 3)),
        rotation: round(((rotation + 180) % 360 + 360) % 360 - 180)
    };
}
function transformPreview(d, full, editable) {
    const motif = studio.catalog.find(m => m.id === d.motifId);
    const font = personalFont(d.fontId);
    const t = textTransform(d.transform);
    return `<div class="composition transform-composition ${full ? 'composition-large' : ''}"><div class="design-surface ${editable ? 'design-editable' : ''}" ${editable ? 'id="designSurface" aria-label="Gestaltungsfläche für deinen Wunschtext"' : 'role="group" aria-label="Motiv mit gestaltetem Wunschtext"'}><div class="design-plane">${motif ? `<img class="motif-image" src="${studioEscape(motif.url)}" alt="${studioEscape(studioPrettyName(motif.name))}" loading="lazy" draggable="false"><span class="asset-warning" hidden>Motivbild nicht erreichbar. Die Auswahl bleibt gespeichert.</span>` : '<p class="asset-warning">Bitte ein Motiv auswählen.</p>'}<div class="design-text-object" style="left:${t.x * DESIGN_SIZE}px;top:${t.y * DESIGN_SIZE}px;transform:translate(-50%,-50%) rotate(${t.rotation}deg) scale(${t.scale})" ${editable ? 'tabindex="0" data-transform-action="move" role="group" aria-label="Wunschtext verschieben. Pfeiltasten bewegen, Umschalt bewegt schneller." aria-describedby="transformHelp"' : ''}><div class="composition-text" style="font-family:${studioEscape(font.family)}">${studioEscape(d.text || 'Dein Wunschtext')}</div></div></div>${editable ? '<button type="button" class="transform-handle rotate-handle" data-transform-action="rotate" aria-label="Text drehen. Ziehen oder Pfeiltasten verwenden." title="Text drehen">↻</button><button type="button" class="transform-handle scale-handle" data-transform-action="scale" aria-label="Text skalieren. Ziehen oder Pfeiltasten verwenden." title="Text skalieren">⤢</button>' : ''}</div></div>`;
}
function transformControls() {
    return `<section class="transform-controls" aria-label="Textposition, Grösse und Drehung"><p id="transformHelp">Text mit Maus oder einem Finger ziehen. Mit ⤢ die Grösse ändern, mit ↻ drehen. Alternativ Regler oder Pfeiltasten verwenden.</p><div class="transform-positions"><label for="textX">Horizontal (%)<input type="number" id="textX" min="6" max="94" step="0.1" inputmode="decimal"></label><label for="textY">Vertikal (%)<input type="number" id="textY" min="6" max="94" step="0.1" inputmode="decimal"></label></div><label class="transform-range" for="textScale">Textgrösse <output id="scaleValue" for="textScale"></output><input type="range" id="textScale" min="25" max="300" step="1"></label><label class="transform-range" for="textRotation">Drehung <output id="rotationValue" for="textRotation"></output><input type="range" id="textRotation" min="-180" max="180" step="1"></label><button type="button" class="action" id="resetTransform">Position, Grösse und Drehung zurücksetzen</button><p id="transformAdvice" class="personal-help" role="status"></p></section>`;
}
const mountedSurfaces = new Set();
const surfaceObserver = new ResizeObserver(entries => {
    for (const entry of entries) transformFit(entry.target);
});
function transformFit(surface) {
    if (!surface.isConnected || !surface.clientWidth) return;
    if (surface.designWidth && surface.designWidth !== surface.clientWidth) surface.dispatchEvent(new Event('designresize'));
    surface.designWidth = surface.clientWidth;
    surface.querySelector('.design-plane').style.transform = `scale(${surface.clientWidth / DESIGN_SIZE})`;
    if (surface.classList.contains('design-editable')) transformSync();
}
function transformUnmount() {
    for (const surface of mountedSurfaces) surfaceObserver.unobserve(surface);
    mountedSurfaces.clear();
}
function transformMount() {
    for (const surface of mountedSurfaces) {
        if (!surface.isConnected) { surfaceObserver.unobserve(surface); mountedSurfaces.delete(surface); }
    }
    document.querySelectorAll('.design-surface').forEach(surface => {
        if (!mountedSurfaces.has(surface)) {
            mountedSurfaces.add(surface); surfaceObserver.observe(surface);
            if (surface.classList.contains('design-editable')) transformBind(surface);
        }
        transformFit(surface);
    });
}
function transformSet(value) {
    if (!personal.current || studio.view !== 'editor') return;
    personal.current.transform = textTransform(value);
    personal.current.layoutVersion = 2;
    personal.dirty = true;
    transformSync();
}
function transformSync() {
    const surface = document.getElementById('designSurface');
    if (!surface || !personal.current) return;
    const t = textTransform(personal.current.transform);
    const object = surface.querySelector('.design-text-object');
    object.style.left = `${t.x * DESIGN_SIZE}px`;
    object.style.top = `${t.y * DESIGN_SIZE}px`;
    object.style.transform = `translate(-50%,-50%) rotate(${t.rotation}deg) scale(${t.scale})`;
    const values = { textX: Math.round(t.x * 1000) / 10, textY: Math.round(t.y * 1000) / 10, textScale: Math.round(t.scale * 100), textRotation: Math.round(t.rotation) };
    for (const [id, value] of Object.entries(values)) {
        const input = document.getElementById(id);
        if (input && document.activeElement !== input) input.value = value;
    }
    document.getElementById('scaleValue').textContent = `${Math.round(t.scale * 100)} %`;
    document.getElementById('rotationValue').textContent = `${Math.round(t.rotation)}°`;
    const angle = t.rotation * Math.PI / 180;
    const cos = Math.cos(angle), sin = Math.sin(angle);
    const w = object.offsetWidth * t.scale / 2, h = object.offsetHeight * t.scale / 2;
    const margin = Math.min(100, 28 * DESIGN_SIZE / Math.max(1, surface.clientWidth));
    const placeHandle = (handle, dx, dy) => {
        const x = transformClamp(t.x * DESIGN_SIZE + dx * cos - dy * sin, margin, DESIGN_SIZE - margin);
        const y = transformClamp(t.y * DESIGN_SIZE + dx * sin + dy * cos, margin, DESIGN_SIZE - margin);
        handle.style.left = `${x / DESIGN_SIZE * 100}%`;
        handle.style.top = `${y / DESIGN_SIZE * 100}%`;
        return { x, y };
    };
    const scale = placeHandle(surface.querySelector('.scale-handle'), w, h);
    const rotateHandle = surface.querySelector('.rotate-handle');
    const rotate = placeHandle(rotateHandle, 0, -h - margin);
    if (Math.hypot(scale.x - rotate.x, scale.y - rotate.y) < margin * 1.9) {
        rotateHandle.style.left = `${(scale.x > DESIGN_SIZE / 2 ? margin : DESIGN_SIZE - margin) / DESIGN_SIZE * 100}%`;
    }
    const halfX = Math.abs(cos) * w + Math.abs(sin) * h;
    const halfY = Math.abs(sin) * w + Math.abs(cos) * h;
    const cropped = t.x * DESIGN_SIZE - halfX < 0 || t.x * DESIGN_SIZE + halfX > DESIGN_SIZE || t.y * DESIGN_SIZE - halfY < 0 || t.y * DESIGN_SIZE + halfY > DESIGN_SIZE;
    document.getElementById('transformAdvice').textContent = cropped ? 'Der Textrahmen ragt über die Fläche hinaus. Teile des Textes können in der Vorschau abgeschnitten sein. Verschiebe oder verkleinere den Text. Dein vollständiger Wunschtext bleibt gespeichert.' : 'Der Textmittelpunkt bleibt innerhalb der Fläche. Die Vorschau ist keine massstabsgetreue Gravurvorlage.';
}
function transformBind(surface) {
    let gesture = null;
    const point = event => {
        const rect = surface.getBoundingClientRect();
        return { x: (event.clientX - rect.left) / rect.width * DESIGN_SIZE, y: (event.clientY - rect.top) / rect.height * DESIGN_SIZE };
    };
    const finish = (cancel = false) => {
        if (!gesture) return;
        const last = gesture; gesture = null;
        surface.classList.remove('is-transforming');
        if (cancel && personal.current === last.draft) {
            personal.current.transform = last.transform;
            personal.dirty = last.dirty;
            transformSync();
        }
        if (surface.hasPointerCapture(last.id)) surface.releasePointerCapture(last.id);
    };
    surface.addEventListener('designresize', () => finish(true));
    surface.addEventListener('pointerdown', event => {
        const target = event.target.closest('[data-transform-action]');
        if (!target || event.button !== 0 || event.isPrimary === false || gesture || !personal.current) return;
        event.preventDefault();
        target.focus({ preventScroll: true });
        const start = point(event), transform = textTransform(personal.current.transform);
        gesture = { id: event.pointerId, action: target.dataset.transformAction, start, transform, dirty: personal.dirty, draft: personal.current };
        surface.setPointerCapture(event.pointerId);
        surface.classList.add('is-transforming');
    });
    surface.addEventListener('pointermove', event => {
        if (!gesture || event.pointerId !== gesture.id || personal.current !== gesture.draft) return;
        event.preventDefault();
        const now = point(event), t = gesture.transform, cx = t.x * DESIGN_SIZE, cy = t.y * DESIGN_SIZE;
        if (gesture.action === 'move') transformSet({ ...t, x: t.x + (now.x - gesture.start.x) / DESIGN_SIZE, y: t.y + (now.y - gesture.start.y) / DESIGN_SIZE });
        if (gesture.action === 'scale') {
            const distance = Math.hypot(gesture.start.x - cx, gesture.start.y - cy);
            transformSet({ ...t, scale: t.scale * Math.hypot(now.x - cx, now.y - cy) / Math.max(20, distance) });
        }
        if (gesture.action === 'rotate') {
            const delta = Math.atan2(now.y - cy, now.x - cx) - Math.atan2(gesture.start.y - cy, gesture.start.x - cx);
            transformSet({ ...t, rotation: t.rotation + delta * 180 / Math.PI });
        }
    });
    surface.addEventListener('pointerup', event => { if (gesture?.id === event.pointerId) finish(); });
    surface.addEventListener('pointercancel', event => { if (gesture?.id === event.pointerId) finish(true); });
    surface.addEventListener('lostpointercapture', () => finish(true));
    surface.addEventListener('keydown', event => {
        if (event.key === 'Escape' && gesture) { event.preventDefault(); finish(true); return; }
        const target = event.target.closest('[data-transform-action]');
        if (!target || !personal.current) return;
        const t = textTransform(personal.current.transform), step = event.shiftKey ? 5 : 1;
        const action = target.dataset.transformAction;
        const direction = ['ArrowRight', 'ArrowUp'].includes(event.key) ? 1 : ['ArrowLeft', 'ArrowDown'].includes(event.key) ? -1 : 0;
        if (!direction && event.key !== 'Home') return;
        event.preventDefault();
        if (event.key === 'Home') {
            transformSet({ ...t, ...(action === 'move' ? { x: TEXT_DEFAULT.x, y: TEXT_DEFAULT.y } : action === 'scale' ? { scale: 1 } : { rotation: 0 }) });
        } else if (action === 'move') {
            transformSet({ ...t, x: t.x + (event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0) / 100, y: t.y + (event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0) / 100 });
        } else if (action === 'scale') transformSet({ ...t, scale: t.scale + direction * step * 0.05 });
        else transformSet({ ...t, rotation: t.rotation + direction * (event.shiftKey ? 15 : 1) });
    });
}
function transformBindControls() {
    for (const [id, key, factor] of [['textX', 'x', 0.01], ['textY', 'y', 0.01], ['textScale', 'scale', 0.01], ['textRotation', 'rotation', 1]]) {
        const input = document.getElementById(id);
        input.addEventListener('input', () => {
            if (input.value === '' || !Number.isFinite(input.valueAsNumber)) return;
            transformSet({ ...personal.current.transform, [key]: input.valueAsNumber * factor });
        });
        input.addEventListener('change', () => {
            const t = textTransform(personal.current.transform);
            input.value = Math.round(t[key] / factor * 10) / 10;
        });
    }
    document.getElementById('resetTransform').onclick = () => transformSet(TEXT_DEFAULT);
}
