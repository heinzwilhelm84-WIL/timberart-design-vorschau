/* Local preview exports only. No production geometry, font outlines or Drive downloads. */
const inquiryClone = value => JSON.parse(JSON.stringify(value));
const inquiryXML = value => String(value).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/g, '\uFFFD').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
function inquiryBlobData(blob) {
    return new Promise((resolve,reject) => { const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('Local export failed'));reader.readAsDataURL(blob); });
}
function inquiryCanvasBlob(canvas) {
    return new Promise((resolve,reject) => canvas.toBlob(blob=>blob?resolve(blob):reject(Error('Local export failed')),'image/png'));
}
function inquiryLocalImage(url) {
    return new Promise((resolve,reject) => {const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('Local image unavailable'));img.src=url;});
}
function inquiryLines(text, root) {
    // Use real browser wrapping, including font fallback and preserved manual breaks.
    const walker=document.createTreeWalker(text,NodeFilter.SHOW_TEXT), rows=[], byTop=new Map();
    const origin=root.getBoundingClientRect();
    while (walker.nextNode()) {
        const node=walker.currentNode;
        const segments=typeof Intl.Segmenter==='function'?[...new Intl.Segmenter('de',{granularity:'grapheme'}).segment(node.data)].map(s=>s.segment):Array.from(node.data);
        let offset=0;
        for (const segment of segments) {
            const range=document.createRange();range.setStart(node,offset);offset+=segment.length;range.setEnd(node,offset);
            if (/^[\r\n]+$/.test(segment)) continue;
            const rect=range.getClientRects()[0];if(!rect)continue;
            const key=Math.round((rect.top-origin.top)*2);let row=byTop.get(key);
            if(!row){row={x:rect.left-origin.left,top:rect.top-origin.top,height:rect.height,text:''};rows.push(row);byTop.set(key,row);}
            row.text+=segment;
        }
    }
    return rows;
}
async function inquiryExport(design, motif, legacyLayout, options = {}) {
    const host=document.createElement('div');host.className='inquiry-export-host';host.setAttribute('aria-hidden','true');document.body.append(host);
    const warnings=[];
    try {
        let fontLoaded=false;
        if(design) {
            const font=personalFont(design.fontId);
            const loaded=await Promise.race([document.fonts.load(`400 24px "${font.name}"`).catch(()=>[]),new Promise(resolve=>setTimeout(()=>resolve([]),4000))]);
            fontLoaded=loaded.length>0;
            if(!fontLoaded) {
                if(options.pngOnly && design.text.trim())throw Error('Die gewählte Schrift ist noch nicht verfügbar. Bitte Internetverbindung prüfen, kurz warten und erneut versuchen.');
                warnings.push('Originalschrift nicht bestätigt; aktuelle Ersatzschrift in PNG möglich.');
            }
            host.innerHTML=personalPreview(design,legacyLayout?.full??true,false);
            if(options.pngOnly && !design.text)host.querySelector('.composition-text').textContent='';
            if(!host.querySelector('.design-surface')&&legacyLayout?.width){host.style.width=`${legacyLayout.width}px`;host.firstElementChild.style.width=`${legacyLayout.width}px`;}
        } else host.innerHTML='<div class="composition"><div class="design-surface"><div class="design-plane"></div></div></div>';
        const surface=host.querySelector('.design-surface');
        let root,object,text,frame=null,scale=1,rotation=0,cx=0,cy=0;
        if(surface) {
            Object.assign(surface.style,{width:'600px',height:'600px',maxWidth:'none',aspectRatio:'auto'});
            surface.querySelector('.design-plane').style.transform='none';root=surface;
            if(design?.layoutVersion===3) {frameSync(surface);frame=inquiryClone(design.textFrame);}
        } else root=host.querySelector('.composition');
        object=host.querySelector('.design-text-object');text=host.querySelector('.composition-text');
        if(object) {
            if(frame){cx=frame.x;cy=frame.y;rotation=frame.rotation;}
            else {const t=textTransform(design.transform);cx=t.x*600;cy=t.y*600;rotation=t.rotation;scale=t.scale;}
            // Measure unrotated local coordinates, then apply exactly one object transform.
            object.style.transform='none';object.style.left='0';object.style.top='0';
        }
        const width=Math.ceil(root.getBoundingClientRect().width),height=Math.ceil(root.getBoundingClientRect().height);
        const factor=options.pngOnly?2400/Math.max(width,height):2;
        const canvas=document.createElement('canvas');canvas.width=options.pngOnly?2400:Math.round(width*factor);canvas.height=options.pngOnly?2400:Math.round(height*factor);
        const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);
        ctx.scale(factor,factor);ctx.translate((canvas.width/factor-width)/2,(canvas.height/factor-height)/2);
        ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
        let imageURI='',imageBox=null,imageIncluded=false;
        if(motif) {
            try {
                const path=motifImageData(motif,{detail:true}).src;
                if(!/^\.\/assets\/motifs\/[A-Za-z0-9_/-]+\.webp$/.test(path))throw Error();
                const response=await fetch(path,{redirect:'error',credentials:'same-origin'});if(!response.ok)throw Error();
                const blob=await response.blob();if(blob.type!=='image/webp')throw Error();const img=await inquiryLocalImage(await inquiryBlobData(blob));
                if(!options.pngOnly) {
                    const raster=document.createElement('canvas');raster.width=img.naturalWidth;raster.height=img.naturalHeight;raster.getContext('2d').drawImage(img,0,0);
                    imageURI=await inquiryBlobData(await inquiryCanvasBlob(raster));
                }
                if(surface) imageBox=design?{x:72,y:30,width:456,height:390}:{x:30,y:30,width:540,height:540};
                else {const r=host.querySelector('img').getBoundingClientRect(),o=root.getBoundingClientRect();imageBox={x:r.left-o.left,y:r.top-o.top,width:r.width,height:r.height};}
                const ratio=Math.min(imageBox.width/img.naturalWidth,imageBox.height/img.naturalHeight);
                const w=img.naturalWidth*ratio,h=img.naturalHeight*ratio;
                ctx.drawImage(img,imageBox.x+(imageBox.width-w)/2,imageBox.y+(imageBox.height-h)/2,w,h);imageIncluded=true;
                if(options.pngOnly && (w*factor>img.naturalWidth+1 || h*factor>img.naturalHeight+1))warnings.push(`Motivquelle: ${img.naturalWidth} × ${img.naturalHeight} Pixel. Verwendet wird die grösste lokale Datei; 2400 Pixel Export erzeugen keine zusätzlichen Motivdetails.`);
            } catch (_) {
                if(options.pngOnly)throw Error('Das Motivbild konnte nicht geladen werden. Es wurde kein unvollständiges PNG erstellt.');
                warnings.push('Motivbild fehlt in der Exportvorschau.');
            }
        } else {
            if(options.pngOnly)throw Error('Bitte zuerst ein verfügbares Motiv wählen.');
            warnings.push('Motiv derzeit nicht im Katalog verfügbar.');
        }
        const svg=[`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><title>TimberArt Gestaltungsvorschau – keine Gravurvorlage</title><rect width="100%" height="100%" fill="white"/>`];
        if(imageURI)svg.push(`<image x="${imageBox.x}" y="${imageBox.y}" width="${imageBox.width}" height="${imageBox.height}" preserveAspectRatio="xMidYMid meet" href="${imageURI}"/>`);
        else if(!imageIncluded) {ctx.fillStyle='#792f15';ctx.font='16px sans-serif';ctx.fillText('Motivbild nicht verfügbar – Gestaltungsdaten beachten',24,60);svg.push('<text x="24" y="60" font-size="16">Motivbild nicht verfügbar</text>');}
        let rendered=null;
        if(text) {
            if(object){object.style.transform='none';object.style.left='0';object.style.top='0';}
            const style=getComputedStyle(text),size=parseFloat(style.fontSize),local=object||root;
            const runs=inquiryLines(text,local),ow=object?.offsetWidth||0,oh=object?.offsetHeight||0;
            const viewport=frame?host.querySelector('.frame-text-viewport'):text;
            if(text.scrollHeight>viewport.clientHeight+1 || text.scrollWidth>viewport.clientWidth+1) {
                if(options.pngOnly)throw Error('Der Text passt nicht vollständig in den Rahmen. Bitte Rahmen oder Schriftgrösse anpassen und erneut speichern.');
                warnings.push('Textvorschau hat Überlauf; vollständiger Wunschtext steht in den Gestaltungsdaten.');
            }
            if(frame) {const b=frameBounds(frame);if(b.left<0||b.top<0||b.right>600||b.bottom>600) {
                if(options.pngOnly)throw Error('Der Textrahmen ragt über die Gestaltungsfläche. Bitte verschieben oder verkleinern, damit nichts abgeschnitten wird.');
                warnings.push('Textrahmen ragt über die Gestaltungsfläche.');
            }}
            const transform=object?`translate(${cx} ${cy}) rotate(${rotation}) scale(${scale}) translate(${-ow/2} ${-oh/2})`:'';
            ctx.save();if(object){ctx.translate(cx,cy);ctx.rotate(rotation*Math.PI/180);ctx.scale(scale,scale);ctx.translate(-ow/2,-oh/2);}
            let clip='';
            if(frame) {ctx.beginPath();ctx.rect(frame.padding,frame.padding,frame.width-2*frame.padding,frame.height-2*frame.padding);ctx.clip();svg.push(`<defs><clipPath id="text-clip"><rect x="${frame.padding}" y="${frame.padding}" width="${frame.width-2*frame.padding}" height="${frame.height-2*frame.padding}"/></clipPath></defs>`);clip=' clip-path="url(#text-clip)"';}
            ctx.font=`${style.fontStyle} ${style.fontWeight} ${size}px ${style.fontFamily}`;ctx.fillStyle=style.color;ctx.textBaseline='alphabetic';
            svg.push(`<g transform="${transform}"><g${clip} fill="${inquiryXML(style.color)}" font-family="${inquiryXML(style.fontFamily)}" font-size="${size}" font-weight="${style.fontWeight}" xml:space="preserve">`);
            for(const row of runs) {
                const m=ctx.measureText(row.text||'M'),ascent=m.fontBoundingBoxAscent??size*.8,descent=m.fontBoundingBoxDescent??size*.2;
                row.y=row.top+(row.height-ascent-descent)/2+ascent;
                ctx.fillText(row.text,row.x,row.y);svg.push(`<text x="${row.x}" y="${row.y}">${inquiryXML(row.text)}</text>`);
            }
            svg.push('</g></g>');ctx.restore();
            rendered={effectiveFontSize:size,fontFamily:style.fontFamily,fontLoaded,lineHeight:style.lineHeight,runs,object:object?{x:cx,y:cy,width:ow,height:oh,rotation,scale}:null};
            if(!options.pngOnly)warnings.push('SVG referenziert Schriften, ohne Einbettung oder Umwandlung in Pfade. PNG hält die aktuell gezeichnete Vorschau fest.');
        }
        const render={width,height,rendered,motifIncluded:imageIncluded,warnings,productionReady:false};
        svg.push(`<metadata>${inquiryXML(JSON.stringify({design,render}))}</metadata></svg>`);
        const png=await inquiryCanvasBlob(canvas);
        return {svg:options.pngOnly?null:new Blob(svg,{type:'image/svg+xml;charset=utf-8'}),png,preview:options.pngOnly?null:await inquiryBlobData(png),render};
    } finally {
        host.querySelectorAll('.design-surface').forEach(s=>{if(mountedSurfaces.has(s)){surfaceObserver.unobserve(s);mountedSurfaces.delete(s);}});
        host.remove();
    }
}
