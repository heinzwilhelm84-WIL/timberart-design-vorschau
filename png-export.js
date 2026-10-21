/* Market-stand PNG only: no forms, customer data, mail or upload requests. */
let activePngExport=null;
function pngExportClose() {
    const state=activePngExport;if(!state)return;
    activePngExport=null;state.dialog.close();state.dialog.remove();
    // Safari may still be opening the download after the dialog is dismissed.
    if(state.url)setTimeout(()=>URL.revokeObjectURL(state.url),60000);
    if(state.returnFocus?.isConnected)state.returnFocus.focus();
}
async function pngExportOpen(design,motifId,button) {
    if(activePngExport)return;
    const draft=design?inquiryClone(design):null;
    if(draft && (![1,2,3].includes(draft.layoutVersion||1) || typeof draft.text!=='string' || !FONTS.some(f=>fontId(f)===draft.fontId) || (draft.layoutVersion===3&&!validTextFrame(draft.textFrame)))) {
        personalNotice('Die Gestaltungsdaten können nicht sicher gelesen werden. Dein Entwurf bleibt unverändert.');return;
    }
    const motif=studio.catalog.find(m=>m.id===(draft?.motifId||motifId));
    if(!motif){personalNotice('Bitte zuerst ein verfügbares Motiv auswählen. Dein Entwurf bleibt unverändert.');return;}
    const dialog=document.createElement('dialog');dialog.id='pngExport';dialog.className='png-dialog';
    dialog.setAttribute('aria-labelledby','pngExportTitle');
    dialog.innerHTML='<button type="button" class="action png-close" aria-label="PNG-Vorschau schliessen">✕</button><h2 id="pngExportTitle">Dein Design als PNG</h2><p class="png-status" role="status">PNG wird vorbereitet …</p><img class="png-preview" alt="Fertige PNG-Gestaltung" hidden><p class="png-warnings" role="status"></p><a class="action primary png-download" hidden download="timberart-design.png" target="_blank" rel="noopener">Design als PNG speichern</a><p>2400 × 2400 Pixel · weisser Hintergrund. In xTool Creative Space die gewünschte Grösse und Gravureinstellungen selbst festlegen; keine massstabsgetreue Produktionsvorlage.</p><p>iPad: Falls Safari die Bildansicht öffnet, über „Teilen → In Dateien sichern“ speichern. Die Vorschau bitte bis zum Speichern geöffnet lassen.</p>';
    if(typeof dialog.showModal!=='function'){personalNotice('Bitte für den PNG-Export einen aktuellen Browser verwenden.');return;}
    const reference=button?.closest('.draft-card')?.querySelector('.composition') || (draft?document.querySelector('#compositionPreview .composition'):null);
    const legacyLayout=reference?{full:reference.classList.contains('composition-large'),width:reference.getBoundingClientRect().width}:null;
    const state={dialog,url:null,returnFocus:button||document.activeElement};activePngExport=state;
    document.body.append(dialog);dialog.showModal();dialog.querySelector('.png-close').onclick=pngExportClose;
    dialog.addEventListener('cancel',event=>{event.preventDefault();pngExportClose();});
    dialog.addEventListener('keydown',event=>{if(event.key==='Escape')event.stopPropagation();});
    try {
        const result=await inquiryExport(draft,motif,legacyLayout,{pngOnly:true});
        const previewData=await inquiryBlobData(result.png);
        if(activePngExport!==state)return;
        state.url=URL.createObjectURL(result.png);
        const preview=dialog.querySelector('.png-preview');preview.src=previewData;preview.hidden=false;
        const link=dialog.querySelector('.png-download');link.href=state.url;link.hidden=false;
        // A genuine second tap on this ready Blob link retains Safari's user gesture.
        // Do not auto-click after asynchronous font/image loading or revoke on click.
        dialog.querySelector('.png-status').textContent='PNG bereit. Zum Speichern den Button antippen. Es wird nichts übermittelt.';
        dialog.querySelector('.png-warnings').textContent=result.render.warnings.join(' ');
    } catch(error) {
        if(activePngExport!==state)return;
        dialog.querySelector('.png-status').textContent=error.message||'PNG konnte nicht erstellt werden. Bitte schliessen und erneut versuchen.';
    }
}
document.addEventListener('click',event=>{
    const button=event.target.closest?.('[data-png-export]');if(!button)return;
    const value=button.dataset.pngExport;
    if(value==='motif')pngExportOpen(null,selectedDesign?.id,button);
    else if(value==='current')pngExportOpen(personal.current,undefined,button);
    else {const draft=personal.drafts.find(d=>d.id===value);if(draft)pngExportOpen(draft,undefined,button);}
});
