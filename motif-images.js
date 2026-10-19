/* Runtime image sources are local only. Drive provenance belongs to the import manifest. */
const MOTIF_PLACEHOLDER = './assets/motifs/unavailable.svg';
function motifEscape(value) {
    return String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}
function motifRecord(value) {
    if (value && typeof value === 'object') return value;
    const catalog = typeof studio !== 'undefined' ? studio.catalog : allDesigns;
    return catalog.find(motif => motif.id === value) || null;
}
function motifImageData(value, options = {}) {
    const motif = motifRecord(value);
    const local = url => typeof url === 'string' && /^\.\/assets\/motifs\/[A-Za-z0-9_/-]+\.webp$/.test(url);
    const variants = (motif?.images || []).filter(image => local(image.url) && Number.isFinite(image.width) && image.width > 0 && Number.isFinite(image.height) && image.height > 0).sort((a, b) => a.edge - b.edge);
    const chosen = options.detail ? variants.at(-1) : variants[0];
    const url = chosen?.url || (local(options.detail ? motif?.detailUrl : motif?.url) ? (options.detail ? motif.detailUrl : motif.url) : MOTIF_PLACEHOLDER);
    const byWidth = new Map(variants.map(image => [image.width, image]));
    return { src: url, srcset: [...byWidth.values()].sort((a, b) => a.width - b.width).map(image => `${image.url} ${image.width}w`).join(', '),
        sizes: options.sizes || '(max-width:760px) 42vw, (min-width:1500px) 22vw, 28vw',
        width: chosen?.width, height: chosen?.height, id: motif?.id || '',
        alt: options.alt || (motif ? motif.name.replace(/^\d+[_-]/, '').replace(/_/g, ' ') : 'Motiv nicht verfügbar') };
}
function motifImageTag(value, options = {}) {
    const data = motifImageData(value, options);
    return `<img src="${motifEscape(data.src)}"${data.srcset ? ` srcset="${motifEscape(data.srcset)}" sizes="${motifEscape(data.sizes)}"` : ''}${data.width ? ` width="${data.width}" height="${data.height}"` : ''} data-motif-id="${motifEscape(data.id)}" alt="${motifEscape(data.alt)}" loading="${options.loading === 'eager' ? 'eager' : 'lazy'}" decoding="async" draggable="false"${options.className ? ` class="${motifEscape(options.className)}"` : ''}${options.style ? ` style="${motifEscape(options.style)}"` : ''}>`;
}
function setMotifImage(element, value, options = {}) {
    const data = motifImageData(value, options);
    delete element.dataset.motifFallback;
    element.hidden = false;
    element.dataset.motifId = data.id;
    element.alt = data.alt;
    if (data.width) { element.width = data.width; element.height = data.height; }
    if (data.srcset) { element.sizes = data.sizes; element.srcset = data.srcset; }
    else { element.removeAttribute('sizes'); element.removeAttribute('srcset'); }
    element.src = data.src;
}
function motifDetailUrl(value) { return motifImageData(value, {detail:true}).src; }
document.addEventListener('error', event => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement) || !img.hasAttribute('data-motif-id') || img.dataset.motifFallback) return;
    img.dataset.motifFallback = 'true';
    img.removeAttribute('srcset'); img.removeAttribute('sizes');
    img.alt = 'Motivbild momentan nicht verfügbar';
    img.src = MOTIF_PLACEHOLDER;
}, true);
