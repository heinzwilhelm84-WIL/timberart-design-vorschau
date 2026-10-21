/* Explicit, non-binding inquiries only. Legacy order forms remain disabled. */
const INQUIRY_ENDPOINT='https://formspree.io/f/xzebgwlg';
let activeInquiry=null, inquiryManifest=null;
const inquiryUncertain=new Map();
const inquiryReceipts=new Map(); // Session-memory hashes only; no customer data persisted.
async function inquirySource(motifId) {
    if(!inquiryManifest) inquiryManifest=fetch('./data/motifs-manifest.json',{redirect:'error'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{if(!Array.isArray(data.motifs))throw Error();return data.motifs;}).catch(()=>{inquiryManifest=null;return [];});
    const rows=await inquiryManifest, entry=rows.find(m=>m.id===motifId);
    const fields=['provider','fileId','originalFilename','mimeType','size','md5Checksum','modifiedTime','version','rootFolderId','folderIds'];
    const trusted=entry?.source?.provider==='google-drive'&&entry.source.fileId===motifId;
    const source=Object.fromEntries(fields.filter(key=>trusted&&entry.source[key]!=null).map(key=>[key,inquiryClone(entry.source[key])]));
    const original=entry?.source?.originalUrl;
    source.originalUrl=source.provider==='google-drive'&&source.fileId===motifId&&original===`https://drive.google.com/file/d/${motifId}/view`?original:null;
    source.accessStatus=source.originalUrl?'Gespeicherter Originalverweis; Zugriff nicht geprüft, eventuell Google-Anmeldung erforderlich.':'Kein verifizierter Originalverweis im lokalen Manifest verfügbar.';
    return {source,sourceFingerprint:entry?.sourceFingerprint||null,originalFingerprint:entry?.originalFingerprint||null};
}
function inquiryClose() {
    const state=activeInquiry;if(!state)return;
    if(state.phase==='sending'){state.status.textContent='Übermittlung läuft. Bitte Ergebnis abwarten; nicht erneut senden.';return;}
    activeInquiry=null;state.form.reset();state.dialog.close();state.dialog.remove();
    state.urls.forEach(url=>URL.revokeObjectURL(url));
    if(state.returnFocus?.isConnected)state.returnFocus.focus();
}
function inquiryDownload(state,blob,label,filename) {
    const url=URL.createObjectURL(blob);state.urls.push(url);
    const a=document.createElement('a');a.href=url;a.download=filename;a.className='action';a.textContent=label;
    state.dialog.querySelector('.inquiry-downloads').append(a);
}
async function inquiryOpen(design,motifId,sourceButton) {
    if(activeInquiry)return;
    const draft=design?inquiryClone(design):null;
    if(draft) {
        if(![1,2,3].includes(draft.layoutVersion||1)||typeof draft.text!=='string'||!FONTS.some(f=>fontId(f)===draft.fontId)) {personalNotice('Die Gestaltungsdaten können nicht sicher gelesen werden. Es wurde nichts versendet.');return;}
        if(draft.layoutVersion===3&&!validTextFrame(draft.textFrame)){personalNotice('Ungültiger Textrahmen. Es wurde nichts versendet.');return;}
    }
    const id=draft?.motifId||motifId, motif=studio.catalog.find(m=>m.id===id);
    if(!id||(!draft&&!motif)){personalNotice('Bitte zuerst ein verfügbares Motiv wählen.');return;}
    const dialog=document.createElement('dialog');
    if(typeof dialog.showModal!=='function'){personalNotice('Dieser Browser unterstützt den Anfrage-Dialog nicht. Bitte einen aktuellen Browser verwenden. Es wurde nichts versendet.');return;}
    dialog.className='inquiry-dialog';dialog.id='designInquiry';dialog.setAttribute('aria-labelledby','inquiryTitle');
    dialog.innerHTML=`<button type="button" class="action inquiry-close" aria-label="Designanfrage schliessen">✕</button><h2 id="inquiryTitle">Design an TimberArt senden</h2><p>Unverbindliche Designanfrage – keine Bestellung, kein Kaufvertrag und keine Zahlung.</p><p class="inquiry-description"></p><img class="inquiry-preview" alt="Vorschau der erfassten Gestaltung" hidden><p class="inquiry-warnings" role="status"></p><div class="inquiry-downloads inquiry-actions"></div><p>SVG und PNG bleiben lokale Downloads und werden nicht als Anhang versendet. SVG-Schriften sind nicht eingebettet; die Dateien sind keine freigegebenen Gravurvorlagen.</p><form id="designInquiryForm"><fieldset class="inquiry-customer"><legend>Deine Kontaktangaben</legend><label for="inquiryName">Name (Pflichtfeld)<input id="inquiryName" name="name" autocomplete="name" required></label><label for="inquiryEmail">E-Mail (freiwillig)<input id="inquiryEmail" name="email" type="email" autocomplete="email" aria-describedby="inquiryEmailHelp"></label><p id="inquiryEmailHelp">Für eine gewünschte Rückmeldung bitte E-Mail oder Telefonnummer angeben.</p><label for="inquiryPhone">Telefonnummer (freiwillig)<input id="inquiryPhone" name="phone" type="tel" autocomplete="tel"></label><label for="inquiryMessage">Bemerkungen (freiwillig)<textarea id="inquiryMessage" name="message"></textarea></label><p>Erst beim bewussten Senden werden diese Angaben und die erfassten Gestaltungsdaten über Formspree an TimberArt übermittelt. Sie werden nicht in der Designmappe gespeichert. Deine gespeicherten Entwürfe bleiben unverändert.</p></fieldset><p class="inquiry-status" role="status" aria-live="polite">Gestaltung wird lokal vorbereitet …</p><button type="submit" class="action primary inquiry-submit" disabled>Design an TimberArt senden</button><button type="button" class="action inquiry-retry" hidden>Trotz unklarem Status erneut senden</button></form>`;
    const reference=(sourceButton||document.activeElement)?.closest('.draft-card')?.querySelector('.composition') || (draft?document.querySelector('#compositionPreview .composition'):null);
    const legacyLayout=reference?{full:reference.classList.contains('composition-large'),width:reference.getBoundingClientRect().width}:null;
    const state={dialog,form:dialog.querySelector('form'),status:dialog.querySelector('.inquiry-status'),phase:'preparing',urls:[],returnFocus:sourceButton||document.activeElement,draft};
    activeInquiry=state;document.body.append(dialog);dialog.showModal();dialog.querySelector('.inquiry-close').onclick=inquiryClose;
    dialog.addEventListener('keydown',event=>{if(event.key==='Escape')event.stopPropagation();});
    dialog.addEventListener('cancel',event=>{event.preventDefault();inquiryClose();});
    state.form.addEventListener('submit',event=>{event.preventDefault();inquirySubmit(state);});
    dialog.querySelector('.inquiry-retry').onclick=()=>{if(state.phase==='uncertain'){state.retryConfirmed=true;state.dialog.querySelector('.inquiry-customer').disabled=false;state.phase='ready';inquirySubmit(state);}};
    const name=motif?.name||draft?.motifName||'Gespeichertes Motiv';
    dialog.querySelector('.inquiry-description').textContent=`${name} · ${studioLabel(motif?.category||draft?.category||'')} · ${draft?'personalisierte Gestaltung':'unverändertes Motiv'}`;
    try {
        const provenance=await inquirySource(id);if(activeInquiry!==state)return;
        const exported=await inquiryExport(draft,motif,legacyLayout);if(activeInquiry!==state)return;
        state.design={schemaVersion:1,type:draft?'personalisiert':'motiv',motif:{id,name,category:motif?.category||draft?.category||'',categoryId:motif?.categoryId||null,previewVariants:inquiryClone(motif?.images||[]),...provenance},draft,font:draft?{id:draft.fontId,name:personalFont(draft.fontId).name,family:personalFont(draft.fontId).family}:null,render:exported.render,previewFilesSent:false,productionReady:false};
        const img=dialog.querySelector('.inquiry-preview');img.src=exported.preview;img.hidden=false;
        dialog.querySelector('.inquiry-warnings').textContent=[provenance.source.accessStatus,...exported.render.warnings].join(' ');
        inquiryDownload(state,exported.png,'PNG-Vorschau herunterladen','timberart-vorschau.png');
        inquiryDownload(state,exported.svg,'SVG-Vorschau herunterladen','timberart-vorschau.svg');
        inquiryDownload(state,new Blob([JSON.stringify(state.design,null,2)],{type:'application/json'}),'Gestaltungsdaten herunterladen','timberart-gestaltung.json');
        state.phase='ready';state.status.textContent='Gestaltung erfasst. Bitte Kontaktangaben prüfen und bewusst senden.';dialog.querySelector('.inquiry-submit').disabled=false;
    } catch (_) {
        if(activeInquiry!==state)return;
        state.phase='failed';state.status.textContent='Gestaltung konnte nicht vollständig vorbereitet werden. Es wurde nichts versendet. Bitte schliessen und erneut öffnen; dein Entwurf bleibt erhalten.';
    }
}
function inquiryPayload(state) {
    const form=new FormData(state.form), design=state.design, d=design.draft;
    return {name:String(form.get('name')||'').trim(),email:String(form.get('email')||'').trim(),phone:String(form.get('phone')||'').trim(),message:String(form.get('message')||''),
        _subject:'Unverbindliche TimberArt-Designanfrage',request_type:'unverbindliche_designanfrage',design_type:design.type,
        motif_name:design.motif.name,motif_id:design.motif.id,category:design.motif.category,
        original_file_url:design.motif.source.originalUrl||'',original_filename:design.motif.source.originalFilename||'',source_information:JSON.stringify(design.motif,null,2),
        wish_text:d?.text||'',font_name:design.font?.name||'',font_id:design.font?.id||'',layout_version:d?.layoutVersion|| (d?1:''),max_font_size:d?.textFrame?.fontSize??'',
        design_data:JSON.stringify(design,null,2),preview_note:'PNG/SVG nur lokal zum Download; keine Dateianhänge. Keine Gravurfreigabe.'};
}
async function inquirySubmit(state) {
    if(activeInquiry!==state||state.phase!=='ready')return;
    if(!state.form.reportValidity())return;
    const payload=inquiryPayload(state);
    if(!payload.name){state.status.textContent='Bitte deinen Namen eingeben.';return;}
    state.phase='sending';state.dialog.querySelector('.inquiry-submit').disabled=true;state.dialog.querySelector('.inquiry-retry').hidden=true;
    state.status.tabIndex=-1;state.status.focus();
    state.dialog.querySelector('.inquiry-customer').disabled=true;state.status.textContent='Designanfrage wird übermittelt … Bitte warten.';
    let timer,attempted=false;
    try {
        const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(payload)));
        const key=Array.from(new Uint8Array(hash),v=>v.toString(16).padStart(2,'0')).join('');
        if(inquiryReceipts.has(key)){state.phase='sent';state.form.reset();state.status.textContent='Diese identische Anfrage wurde in dieser Sitzung bereits bestätigt. Es wurde nicht erneut gesendet.';return;}
        if(state.payloadKey!==key){state.payloadKey=key;state.requestId=inquiryUncertain.get(key)||crypto.randomUUID();}
        if(inquiryUncertain.has(key)&&!state.retryConfirmed){
            state.phase='uncertain';state.status.textContent='Für diese identische Anfrage fehlt bereits eine sichere Bestätigung. Bitte zuerst bei TimberArt nachfragen; es wurde nicht erneut gesendet.';
            state.dialog.querySelector('.inquiry-retry').hidden=false;return;
        }
        state.retryConfirmed=false;
        const controller=new AbortController();timer=setTimeout(()=>controller.abort(),30000);
        attempted=true;
        const response=await fetch(INQUIRY_ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({...payload,request_id:state.requestId}),credentials:'omit',redirect:'error',referrerPolicy:'no-referrer',signal:controller.signal});
        let data;try{data=await response.json();}catch(_){data=null;}
        if(response.ok&&data?.ok===true) {
            inquiryUncertain.delete(key);inquiryReceipts.set(key,true);state.phase='sent';state.form.reset();state.status.textContent='Deine unverbindliche Designanfrage wurde erfolgreich an Formspree übermittelt. Das ist keine Bestellung. Eine Zustellung im Gmail-Postfach kann die App nicht bestätigen.';
        } else if([400,401,403,404,405,413,422,429].includes(response.status)) {
            state.phase='ready';state.status.textContent=response.status===429?'Formspree hat die Anfrage abgelehnt: zu viele Anfragen. Bitte später erneut versuchen.':response.status===413?'Die Anfrage ist für Formspree zu gross. Bitte Gestaltungsdaten lokal herunterladen und TimberArt kontaktieren.':'Formspree hat die Anfrage nicht bestätigt und mit einem Fehler abgelehnt. Bitte Angaben prüfen oder später erneut versuchen.';
        } else throw Error('Unconfirmed');
    } catch (_) {
        if(!attempted){state.phase='failed';state.status.textContent='Der Browser konnte die Anfrage nicht sicher vorbereiten. Es wurde nichts versendet. Bitte schliessen und einen aktuellen Browser mit HTTPS verwenden.';return;}
        inquiryUncertain.set(state.payloadKey,state.requestId);
        state.phase='uncertain';state.status.textContent='Keine sichere Übermittlungsbestätigung erhalten. Die Anfrage könnte bereits angekommen sein. Bitte zuerst bei TimberArt nachfragen; es wird nicht automatisch erneut gesendet.';
        state.dialog.querySelector('.inquiry-retry').hidden=false;
    } finally {
        clearTimeout(timer);
        if(state.phase==='ready'){state.dialog.querySelector('.inquiry-submit').disabled=false;state.dialog.querySelector('.inquiry-customer').disabled=false;}
    }
}
document.addEventListener('click',event=>{
    const button=event.target.closest?.('[data-inquiry]');if(!button)return;
    if(button.dataset.inquiry==='motif')inquiryOpen(null,selectedDesign?.id,button);
    else if(button.dataset.inquiry==='current')inquiryOpen(personal.current,undefined,button);
    else {const d=personal.drafts.find(d=>d.id===button.dataset.inquiry);if(d)inquiryOpen(d,undefined,button);}
});
window.addEventListener('beforeunload',event=>{if(activeInquiry?.phase==='sending'){event.preventDefault();event.returnValue='';}});

// A disabled submit button can move focus to body. Shield underlying legacy modals
// from Escape even in that case; the native dialog cancel handler remains active.
document.addEventListener('keydown',event=>{if(activeInquiry&&event.key==='Escape')event.stopPropagation();},true);
