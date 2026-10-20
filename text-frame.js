/* Layout v3: design-space dimensions and font size, never an object scale. */
const FRAME_DEFAULT = Object.freeze({ x: 300, y: 480, width: 420, height: 140, fontSize: 40, rotation: 0, align: 'center', padding: 12, lineHeight: 1.3 });
const FRAME_LIMITS = Object.freeze({ x: [36, 564], y: [36, 564], width: [32, 1800], height: [32, 1800], fontSize: [8, 240], rotation: [-180, 180], padding: [0, 60], lineHeight: [1, 3] });
function validTextFrame(value) {
    return !!value && typeof value === 'object' && !Array.isArray(value) &&
        Object.keys(value).length === Object.keys(FRAME_DEFAULT).length &&
        Object.entries(FRAME_LIMITS).every(([key, [min, max]]) => typeof value[key] === 'number' && Number.isFinite(value[key]) && value[key] >= min && value[key] <= max) &&
        ['left', 'center', 'right'].includes(value.align) && value.width > value.padding * 2 && value.height > value.padding * 2;
}
function copyTextFrame(value = FRAME_DEFAULT) {
    if (!validTextFrame(value)) throw Error('Invalid text frame');
    return { ...value };
}
function frameBounds(f) {
    const a = f.rotation * Math.PI / 180;
    const halfX = Math.abs(Math.cos(a)) * f.width / 2 + Math.abs(Math.sin(a)) * f.height / 2;
    const halfY = Math.abs(Math.sin(a)) * f.width / 2 + Math.abs(Math.cos(a)) * f.height / 2;
    return { left: f.x - halfX, right: f.x + halfX, top: f.y - halfY, bottom: f.y + halfY };
}
const FRAME_HANDLES = Object.freeze({ nw:[-1,-1], ne:[1,-1], se:[1,1], sw:[-1,1] });
function frameResize(f, handle, dx, dy) {
    const [sx,sy] = FRAME_HANDLES[handle] || [];
    if (sx === undefined || !Number.isFinite(dx) || !Number.isFinite(dy)) throw Error('Invalid resize');
    const a=f.rotation*Math.PI/180, c=Math.cos(a), s=Math.sin(a);
    const min=Math.max(32,2*f.padding+1);
    const dw=sx ? Math.max(min,Math.min(1800,f.width+sx*(c*dx+s*dy)))-f.width : 0;
    const dh=sy ? Math.max(min,Math.min(1800,f.height+sy*(-s*dx+c*dy)))-f.height : 0;
    const cx=c*sx*dw/2-s*sy*dh/2, cy=s*sx*dw/2+c*sy*dh/2;
    // Limit the same resize delta, rather than shifting the fixed opposite anchor.
    let t=1;
    for (const [position,delta] of [[f.x,cx],[f.y,cy]]) {
        if(delta>0) t=Math.min(t,(564-position)/delta);
        if(delta<0) t=Math.min(t,(36-position)/delta);
    }
    t=Math.max(0,t);
    return copyTextFrame({...f,x:Math.max(36,Math.min(564,f.x+cx*t)),y:Math.max(36,Math.min(564,f.y+cy*t)),width:f.width+dw*t,height:f.height+dh*t});
}
function frameTools() {
    const names={nw:'oben links',ne:'oben rechts',se:'unten rechts',sw:'unten links'};
    return `<svg class="frame-guide-lines" viewBox="0 0 600 600" aria-hidden="true">${[...Object.keys(FRAME_HANDLES),'rotate'].map(key=>`<line data-frame-guide="${key}"/>`).join('')}</svg>` +
        Object.keys(FRAME_HANDLES).map(key=>`<button type="button" class="transform-handle resize-handle" hidden data-transform-action="resize" data-frame-handle="${key}" aria-label="Rahmen ${names[key]} ändern. Ziehen oder Pfeiltasten verwenden." title="Rahmen ${names[key]} ändern"></button>`).join('') +
        '<button type="button" class="transform-handle rotate-handle" hidden data-transform-action="rotate" aria-label="Text drehen. Ziehen oder Pfeiltasten verwenden.">↻</button>';
}
function framePlaceTools(surface,f) {
    if (!surface.clientWidth) return;
    // Keep 48px controls apart and inside the viewport; displaced grips get leaders.
    const a=f.rotation*Math.PI/180,c=Math.cos(a),s=Math.sin(a),unit=600/surface.clientWidth;
    const margin=28*unit,gap=52*unit,placed=[];
    const clamp=v=>Math.max(margin,Math.min(600-margin,v));
    const grid=[];
    for(let x=margin;x<=600-margin+.01;x+=gap) for(let y=margin;y<=600-margin+.01;y+=gap) grid.push({x,y});
    const tools=[...Object.entries(FRAME_HANDLES),['rotate',[0,-1]]];
    const desired=tools.map(([key,[sx,sy]])=>({key,sx,sy,x:f.x+c*sx*f.width/2-s*sy*(f.height/2+(key==='rotate'?60*unit:0)),y:f.y+s*sx*f.width/2+c*sy*(f.height/2+(key==='rotate'?60*unit:0))}));
    function layout(gridOnly) {
        placed.length=0;
        for(const d of desired) {
            const candidates=gridOnly?[...grid]:[{x:clamp(d.x),y:clamp(d.y)},...grid];
            candidates.sort((p,q)=>Math.hypot(p.x-d.x,p.y-d.y)-Math.hypot(q.x-d.x,q.y-d.y));
            const p=candidates.find(p=>placed.every(q=>Math.abs(p.x-q.x)>=gap-.01 || Math.abs(p.y-q.y)>=gap-.01));
            if(!p) return false;
            placed.push({...d,...p});
        }
        return true;
    }
    if(!layout(false)) layout(true);
    desired.forEach((d,i)=>{
        const p=placed[i] || {x:clamp(d.x),y:clamp(d.y)};
        const button=surface.querySelector(d.key==='rotate'?'.rotate-handle':`[data-frame-handle="${d.key}"]`);
        Object.assign(button.style,{left:`${p.x/6}%`,top:`${p.y/6}%`});
        if(d.key!=='rotate') {
            const angle=Math.atan2(d.sy,d.sx)*180/Math.PI+f.rotation;
            button.style.cursor=['ew-resize','nwse-resize','ns-resize','nesw-resize'][((Math.round(angle/45)%4)+4)%4];
        }
        const line=surface.querySelector(`[data-frame-guide="${d.key}"]`);
        for(const [key,value] of Object.entries({x1:d.x,y1:d.y,x2:p.x,y2:p.y})) line.setAttribute(key,value);
    });
}
function framePreview(d, full, editable) {
    const f = copyTextFrame(d.textFrame), motif = studio.catalog.find(m => m.id === d.motifId);
    return `<div class="composition transform-composition frame-v3 ${full ? 'composition-large' : ''}"><div class="design-surface ${editable ? 'design-editable' : ''}" data-frame="${studioEscape(JSON.stringify(f))}" ${editable ? 'id="designSurface" aria-label="Gestaltungsfläche für deinen Wunschtext"' : 'role="group" aria-label="Motiv mit gestaltetem Wunschtext"'}><div class="design-plane">${motif ? `${motifImageTag(motif, {className:'motif-image', detail:full, sizes:full ? '(max-width:760px) 70vw, 38vw' : '(max-width:760px) 70vw, 24vw'})}<span class="asset-warning" hidden>Motivbild nicht erreichbar. Die Auswahl bleibt gespeichert.</span>` : '<p class="asset-warning">Bitte ein Motiv auswählen.</p>'}<div class="design-text-object frame-v3-object" ${editable ? 'tabindex="0" data-transform-action="move" role="button" aria-pressed="false" aria-label="Text auswählen und verschieben. Pfeiltasten bewegen."' : ''}><div class="frame-text-viewport"><div class="composition-text frame-text" style="font-family:${studioEscape(personalFont(d.fontId).family)}"><span class="frame-text-content">${studioEscape(d.text || 'Dein Wunschtext')}</span></div></div></div></div>${editable ? frameTools() : ''}</div><p class="frame-warning" role="status" hidden></p></div>`;
}
function frameControls() {
    const fields = [['width','Rahmenbreite'],['height','Rahmenhöhe'],['fontSize','Schriftgrösse'],['x','Position horizontal'],['y','Position vertikal'],['rotation','Drehung (Grad)']];
    return `<fieldset class="frame-controls"><legend>Textrahmen</legend><p>Breite, Höhe und Schriftgrösse sind unabhängig. Werte beziehen sich auf die 600 × 600 grosse Vorschau, nicht auf Millimeter. Text auswählen, dann verschieben oder über die vier Eckgriffe den Rahmen ändern. ↻ dreht den Text. Bei kleinen Rahmen liegen die Griffe mit Verbindungslinien weiter aussen. Auch die Eingabefelder bleiben verfügbar.</p><div class="frame-fields">${fields.map(([key,label]) => `<label for="frame-${key}">${label}<input id="frame-${key}" data-frame-field="${key}" type="number" min="${FRAME_LIMITS[key][0]}" max="${FRAME_LIMITS[key][1]}" step="0.1" inputmode="decimal"></label>`).join('')}</div><label for="frame-align">Textausrichtung<select id="frame-align"><option value="left">Linksbündig</option><option value="center">Zentriert</option><option value="right">Rechtsbündig</option></select></label><p class="frame-control-error" role="status"></p></fieldset>`;
}
function frameSet(changes) {
    if (personal.current?.layoutVersion !== 3 || studio.view !== 'editor') return false;
    const next = { ...personal.current.textFrame, ...changes };
    if (!validTextFrame(next)) return false;
    personal.current.textFrame = next;
    personal.dirty = true;
    frameSync(document.getElementById('designSurface'));
    return true;
}
function frameBindControls() {
    document.querySelectorAll('[data-frame-field]').forEach(input => {
        const apply = () => {
            const ok = input.value !== '' && frameSet({ [input.dataset.frameField]: input.valueAsNumber });
            input.setAttribute('aria-invalid', String(!ok));
            document.querySelector('.frame-control-error').textContent = ok ? '' : 'Bitte einen gültigen Wert innerhalb des angezeigten Bereichs eingeben. Die letzte gültige Einstellung bleibt erhalten.';
            return ok;
        };
        input.addEventListener('input', apply);
        input.addEventListener('change', () => {
            if (!apply()) {
                input.value = personal.current.textFrame[input.dataset.frameField];
                input.setAttribute('aria-invalid', 'false');
                document.querySelector('.frame-control-error').textContent = 'Ungültige Eingabe verworfen. Die letzte gültige Einstellung wurde wiederhergestellt.';
            }
        });
    });
    document.getElementById('frame-align').addEventListener('change', event => frameSet({ align: event.target.value }));
}
function frameSync(surface) {
    if (!surface?.isConnected) return;
    const editable = surface.classList.contains('design-editable');
    const f = editable ? personal.current?.textFrame : JSON.parse(surface.dataset.frame);
    if (!validTextFrame(f)) return;
    const object = surface.querySelector('.frame-v3-object');
    Object.assign(object.style, { left: `${f.x}px`, top: `${f.y}px`, width: `${f.width}px`, height: `${f.height}px`, padding: `${f.padding}px`, transform: `translate(-50%,-50%) rotate(${f.rotation}deg)` });
    const text = object.querySelector('.frame-text');
    Object.assign(text.style, { fontSize: `${f.fontSize}px`, lineHeight: String(f.lineHeight), textAlign: f.align });
    surface.dataset.frame = JSON.stringify(f);
    if (editable) {
        // Keep controls readable after dragging; persist the unrounded frame geometry.
        document.querySelectorAll('[data-frame-field]').forEach(input => { if (document.activeElement !== input) input.value = Number(f[input.dataset.frameField].toFixed(1)); });
        document.getElementById('frame-align').value = f.align;
        framePlaceTools(surface,f);
    }
    frameCheck(surface, f);
}
function frameCheck(surface, f = JSON.parse(surface.dataset.frame)) {
    const viewport = surface.querySelector('.frame-text-viewport'), text = surface.querySelector('.frame-text');
    const overflow = text.scrollHeight > viewport.clientHeight + 1 || text.scrollWidth > viewport.clientWidth + 1;
    const b = frameBounds(f), outside = b.left < 0 || b.top < 0 || b.right > DESIGN_SIZE || b.bottom > DESIGN_SIZE;
    const warning = surface.parentElement.querySelector('.frame-warning');
    warning.hidden = !overflow && !outside;
    warning.textContent = [overflow ? 'Der Text passt nicht vollständig in den Rahmen. Rahmen vergrössern oder Schrift verkleinern.' : '', outside ? 'Der gedrehte Textrahmen ragt über die Gestaltungsfläche hinaus. Position oder Abmessungen prüfen.' : '', overflow || outside ? 'Der vollständige Wunschtext bleibt gespeichert. Keine Gravurfreigabe.' : ''].filter(Boolean).join(' ');
}
function frameRefreshChecks() {
    document.querySelectorAll('.frame-v3 .design-surface').forEach(surface => frameCheck(surface));
}
function frameUpdatePreview(d) {
    const surface = document.getElementById('designSurface');
    surface.querySelector('.frame-text-content').textContent = d.text || 'Dein Wunschtext';
    surface.querySelector('.frame-text').style.fontFamily = personalFont(d.fontId).family;
    frameSync(surface);
}
function frameBind(surface) {
    // Pointer deltas are transformed into frame-local axes; font size is never scaled.
    let gesture = null;
    const point = event => { const r = surface.getBoundingClientRect(); return { x: (event.clientX-r.left)/r.width*DESIGN_SIZE, y: (event.clientY-r.top)/r.height*DESIGN_SIZE }; };
    const finish = cancel => {
        if (!gesture) return;
        const previous = gesture; gesture = null;
        if (cancel && personal.current === previous.draft) { personal.current.textFrame = previous.frame; personal.dirty = previous.dirty; frameSync(surface); }
        if (surface.hasPointerCapture(previous.id)) surface.releasePointerCapture(previous.id);
    };
    surface.addEventListener('designresize', () => finish(true));
    surface.addEventListener('pointerdown', event => {
        const target = event.target.closest('[data-transform-action]');
        if (!target || !['move','rotate','resize'].includes(target.dataset.transformAction) || event.button !== 0 || event.isPrimary === false || gesture) return;
        event.preventDefault(); transformSelect(surface); target.focus({preventScroll:true});
        gesture = { id:event.pointerId, action:target.dataset.transformAction, handle:target.dataset.frameHandle, start:point(event), frame:copyTextFrame(personal.current.textFrame), draft:personal.current, dirty:personal.dirty };
        surface.setPointerCapture(event.pointerId);
    });
    surface.addEventListener('pointermove', event => {
        if (!gesture || event.pointerId !== gesture.id || personal.current !== gesture.draft) return;
        event.preventDefault(); const p=point(event), f=gesture.frame;
        if (gesture.action==='move') frameSet({ x:transformClamp(f.x+p.x-gesture.start.x,36,564), y:transformClamp(f.y+p.y-gesture.start.y,36,564) });
        else if(gesture.action==='resize') frameSet(frameResize(f,gesture.handle,p.x-gesture.start.x,p.y-gesture.start.y));
        else { const delta=Math.atan2(p.y-f.y,p.x-f.x)-Math.atan2(gesture.start.y-f.y,gesture.start.x-f.x); frameSet({rotation:((f.rotation+delta*180/Math.PI+180)%360+360)%360-180}); }
    });
    surface.addEventListener('pointerup', event => { if (event.pointerId===gesture?.id) finish(false); });
    surface.addEventListener('pointercancel', event => { if (event.pointerId===gesture?.id) finish(true); });
    surface.addEventListener('lostpointercapture', () => finish(true));
    surface.addEventListener('keydown', event => {
        if (event.key==='Escape') { event.preventDefault(); if(gesture) finish(true); else transformSelect(); return; }
        const action=event.target.closest('[data-transform-action]')?.dataset.transformAction;
        if (!action) return;
        if (event.key==='Enter' || event.key===' ') { event.preventDefault(); transformSelect(surface); return; }
        if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)) return;
        event.preventDefault(); const f=personal.current.textFrame, step=event.shiftKey?30:6;
        if(action==='move') frameSet({x:transformClamp(f.x+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0),36,564),y:transformClamp(f.y+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0),36,564)});
        else if(action==='resize') frameSet(frameResize(f,event.target.closest('[data-frame-handle]').dataset.frameHandle,event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0,event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0));
        else frameSet({rotation:((f.rotation+(['ArrowUp','ArrowRight'].includes(event.key)?1:-1)*(event.shiftKey?15:1)+180)%360+360)%360-180});
    });
}
