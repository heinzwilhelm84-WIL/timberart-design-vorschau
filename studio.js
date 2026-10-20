/* UI layer: font definitions and design UI are retained; preview catalog and test handlers live in index.html. */
const studio = { view: 'home', category: 'all', catalog: [], categories: [], ready: false, loading: null, query: '', request: 0, returnFocus: null };
const CATEGORY_STYLE = {
    'Alu-Kreditkarte': ['Alu-Kreditkarten', 'Kleine Karte. Grosse Botschaft.', '#f1e9f6'],
    'CAP-Design': ['Cap-Designs', 'Ein Statement für deinen Look.', '#e8eee5'],
    'Flachmann Motive': ['Flachmann-Motive', 'Für besondere Anstossmomente.', '#fae8df'],
    'Flaschenöffner-Aluminium-gross': ['Flaschenöffner · gross', 'Gute Laune zum Aufmachen.', '#e8eaf5'],
    'Flaschenöffner-Aluminium-klein': ['Flaschenöffner · klein', 'Kleine Begleiter, grosse Freude.', '#f8edce'],
    'Schmuck Design': ['Schmuck-Designs', 'Persönliches, das bleibt.', '#f7e7e9'],
    'Sternzeichen': ['Sternzeichen', 'So einzigartig wie du.', '#eee8f7'],
    'Tiere Strichoptik': ['Tiere in Strichoptik', 'Lieblingstiere mit Charakter.', '#e8efe9'],
    'Untersetzter ': ['Untersetzer', 'Ein Lieblingsplatz fürs Glas.', '#f5e9df']
};
function studioIcon(name) {
    const paths = { arrow:'<path d="M4 12h15m-6-6 6 6-6 6"/>', heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>', search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>', gift:'<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M5 12v9h14v-9M12 8v13"/><path d="M12 8H8a3 3 0 1 1 3-3Zm0 0h4a3 3 0 1 0-3-3Z"/>', spark:'<path d="m12 2 2.8 7.2L22 12l-7.2 2.8L12 22l-2.8-7.2L2 12l7.2-2.8Z"/>', check:'<path d="m5 12 4 4L19 6"/>', folder:'<path d="M3 7V5h6l2 3h10v12H3Z"/>', image:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1"/><path d="m3 17 5-5 4 4 4-7 5 8"/>' };
    return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.spark}</svg>`;
}
function studioEscape(value) { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function studioLabel(category) {
    const record = studio.categories.find(c => c.key === category);
    if (record && (record.displayName || record.name) !== category) return record.displayName || record.name;
    return CATEGORY_STYLE[category]?.[0] || category.trim();
}
async function studioLoadCategories() {
    try {
        const response = await fetch('./data/categories.json');
        if (!response.ok) throw Error();
        const data = await response.json();
        if (data.version !== 1 || !Array.isArray(data.categories) || !data.categories.every(c => typeof c.id === 'string' && typeof c.key === 'string' && typeof c.name === 'string' && (c.displayName == null || typeof c.displayName === 'string'))) throw Error();
        if (new Set(data.categories.map(c => c.id)).size !== data.categories.length || new Set(data.categories.map(c => c.key)).size !== data.categories.length) throw Error();
        studio.categories = data.categories;
    } catch (_) { studio.categories = []; }
}
function studioPrettyName(name) { return name.replace(/^\d+[_-]/, '').replace(/_/g, ' '); }
function studioNavigation() {
    document.getElementById('navContainer').innerHTML = [
        ['home','Entdecken'],['motifs','Motive'],['schriften','Schriftatelier'],['favorites',`${studioIcon('heart')} Favoriten <span class="nav-count">${favorites.length}</span>`],['map',`${studioIcon('folder')} Designmappe <span class="nav-count">${personal.drafts.length}</span>`],...(personal.current && personal.picking ? [['editor','Entwurf fortsetzen']] : [])
    ].map(([view,label]) => `<button type="button" class="nav-btn ${studio.view===view?'active':''}" data-view="${view}" ${studio.view===view?'aria-current="page"':''} onclick="studioNavigate('${view}')">${label}</button>`).join('');
}
async function initStudio() {
    // Keep the existing localStorage key and favorite IDs.
    try { loadFavorites(); } catch (e) { favorites = []; }
    if (!Array.isArray(favorites)) favorites = [];
    studioNavigation(); studioHome(); loadLogo();
    studio.loading = Promise.all([loadAllDesigns(), studioLoadCategories()]).then(() => {
        studio.catalog = [...allDesigns];
        allCategories = [...new Set([...studio.categories.map(c => c.key), ...studio.catalog.map(d => d.category)])].sort((a,b) => studioLabel(a).localeCompare(studioLabel(b), 'de'));
        studio.ready = true;
        if (studio.view==='home') studioHome();
        return studio.catalog;
    });
    await studio.loading;
}
function studioHome() {
    const groups = allCategories.map(cat => ({cat, designs:studio.catalog.filter(d=>d.category===cat)}));
    const hero = studio.catalog.find(d=>d.category==='Tiere Strichoptik') || studio.catalog[0];
    document.getElementById('content').innerHTML = `
        <section class="hero" aria-labelledby="welcomeTitle">
          <div><div class="eyebrow">TimberArt Design Studio</div>
            <h1 id="welcomeTitle">Gestalte dein<br>persönliches <em>Unikat.</em></h1>
            <p class="hero-description">Deine Idee. Dein Motiv. Deine Worte.<br>Kombiniere unsere Motive mit deinem Wunschtext und gestalte etwas, das zu dir passt.</p>
            <div class="hero-actions"><button class="action primary" onclick="studioNavigate('motifs')">Jetzt gestalten ${studioIcon('arrow')}</button><button class="action secondary" onclick="document.getElementById('categories').scrollIntoView({behavior:'smooth'})">Motive entdecken ${studioIcon('image')}</button></div>
            <div class="hero-footnote"><span>${studioIcon('check')} In Ruhe ausprobieren</span><span>${studioIcon('heart')} Ideen auf diesem Gerät speichern</span></div>
          </div>
          <div class="hero-art" aria-label="Inspiration aus dem TimberArt Motivkatalog">
            <div class="studio-example"><div class="example-heading"><span>${studioIcon('spark')} Raum für deine Ideen</span><span class="example-badge">Gestaltungsvorschau</span></div>
              <div class="example-sheet">${hero?motifImageTag(hero, {loading:"eager", sizes:"(max-width:760px) 80vw, 30vw"}):'<span class="example-placeholder">Dein Lieblingsmotiv</span>'}<p class="example-wish">für dich</p><span class="example-rule"></span><p class="example-note">Ein Motiv. Deine persönliche Note.</p></div>
              <div class="example-footer"><span>${studioIcon('image')} Motiv</span><span>+</span><span>${studioIcon('spark')} Wunschtext</span><span>=</span><strong>Dein Unikat</strong></div>
            </div><div class="idea-note">${studioIcon('heart')} So persönlich wie deine Idee.</div>
          </div>
        </section>
        <div class="studio-strip"><span>${studioIcon('image')} <strong>${studio.ready?studio.catalog.length:'…'} Motive</strong> zum Entdecken</span><span>${studioIcon('spark')} <strong>30 Schriften</strong> für deine Worte</span><span>${studioIcon('gift')} <strong>${studio.ready?groups.length:'…'} Kategorien</strong> voller Ideen</span></div>
        <section class="section-wrap" id="categories" aria-labelledby="categoriesTitle"><div class="section-heading"><div><div class="eyebrow">Was möchtest du gestalten?</div><h2 id="categoriesTitle">Was passt zu deiner Idee?</h2><p>Entdecke unsere Motivwelten und finde deinen Ausgangspunkt.</p></div><button class="text-link" onclick="studioNavigate('motifs')">Alle Motive ansehen ${studioIcon('arrow')}</button></div>
        ${groups.length?`<div class="category-grid">${groups.map(({cat,designs},i)=>`<article class="category-card"><button class="category-open" data-category="${studioEscape(cat)}"><div class="category-picture"><span class="category-number">MOTIVWELT ${String(i+1).padStart(2,'0')}</span>${designs.length ? motifImageTag(designs[0], {alt:studioLabel(cat)}) : studioIcon('image')}</div><div class="category-info"><div><h3>${studioEscape(studioLabel(cat))}</h3><p>${designs.length} Motive entdecken</p></div><span class="round-arrow">${studioIcon('arrow')}</span></div></button></article>`).join('')}</div>`:studio.ready?studioEmpty('Die Motive sind gerade nicht erreichbar.','Bitte prüfe die Verbindung und versuche es erneut.','Erneut laden',"location.reload()"):'<div class="loading" role="status"><span class="spinner"></span>Deine Geschenkideen werden geladen …</div>'}
        <div class="font-banner"><div class="type-art" aria-hidden="true">Aa</div><div><div class="eyebrow">Worte mit Persönlichkeit</div><h2>Dein Text. Dein Stil.</h2><p>Elegant, verspielt oder ganz klar: Finde deine Lieblingsschrift.</p></div><button class="action" onclick="studioNavigate('schriften')">Zum Schriftatelier ${studioIcon('arrow')}</button></div></section>`;
    document.querySelectorAll('.category-open').forEach(btn=>btn.addEventListener('click',()=>studioNavigate('motifs',btn.dataset.category)));
}
async function studioNavigate(view, category='all') {
    if (!personalLeave(view)) return;
    transformUnmount();
    personalNotice('');
    const request = ++studio.request;
    studio.view=view;studio.category=category;studio.query='';studioNavigation();
    if(view==='home') studioHome();
    else if(view==='schriften') studioFonts();
    else if(view==='editor' || view==='map') {
        if(studio.loading) await studio.loading;
        if(request!==studio.request) return;
        if(view==='editor') personalEditor(); else mapRender();
    }
    else {
        document.getElementById('content').innerHTML='<div class="loading" role="status"><span class="spinner"></span>Deine Motive werden geladen …</div>';
        if(studio.loading) await studio.loading;
        if(request!==studio.request) return;
        studioGallery();
    }
    window.scrollTo({top:0,behavior:'instant'});
    document.getElementById('content').focus({preventScroll:true});
}
function studioEmpty(title, description, action='Motive entdecken', handler="studioNavigate('motifs')") {
    return `<div class="empty-state">${studioIcon('heart')}<h2>${studioEscape(title)}</h2><p>${studioEscape(description)}</p><button class="action primary" onclick="${handler}">${action} ${studioIcon('arrow')}</button></div>`;
}
function studioGallery() {
    const fav=studio.view==='favorites';
    const title=fav?'Deine Lieblingsideen':studio.category==='all'?'Finde dein Lieblingsmotiv':studioLabel(studio.category);
    document.getElementById('content').innerHTML=`<section class="page-wrap"><div class="breadcrumb"><button onclick="studioNavigate('home')">Entdecken</button><span>/</span><span>${fav?'Favoriten':'Motive'}</span></div><div class="page-heading"><div><div class="eyebrow">${fav?'Zum Wiederfinden und Besprechen':'Dein Geschenk beginnt mit einer Idee'}</div><h1>${studioEscape(title)}</h1><p>${fav?'Hier sammelst du alles, was dir gefällt.':'Entdecken, gross ansehen und deine Favoriten merken.'}</p></div><span class="heading-count">${fav?favorites.length:studio.catalog.length} ${fav?'gemerkt':'Motive'}</span></div>
    <div class="gallery-toolbar"><label class="search-wrap">${studioIcon('search')}<span class="sr-only">Motive suchen</span><input id="motifSearch" type="search" placeholder="Welches Motiv suchst du?" autocomplete="off"></label><label><span class="sr-only">Kategorie auswählen</span><select id="categorySelect" class="category-select"><option value="all">Alle Kategorien</option>${allCategories.map(cat=>`<option value="${studioEscape(cat)}" ${cat===studio.category?'selected':''}>${studioEscape(studioLabel(cat))}</option>`).join('')}</select></label><span id="resultCount" class="result-count" role="status"></span></div><div id="motifResults"></div></section>`;
    document.getElementById('motifSearch').addEventListener('input',e=>{studio.query=e.target.value;studioResults();});
    document.getElementById('categorySelect').addEventListener('change',e=>{studio.category=e.target.value;studioResults();});
    studioResults();
}
function studioResults() {
    const query=studio.query.trim().toLocaleLowerCase('de');
    const list=studio.catalog.filter(d=>(studio.view!=='favorites'||favorites.includes(d.id))&&(studio.category==='all'||d.category===studio.category)&&(!query||`${studioPrettyName(d.name)} ${studioLabel(d.category)}`.toLocaleLowerCase('de').includes(query)));
    document.querySelector('.page-heading h1').textContent=studio.view==='favorites'?'Deine Lieblingsideen':studio.category==='all'?'Finde dein Lieblingsmotiv':studioLabel(studio.category);
    document.querySelector('.heading-count').textContent=`${list.length} ${studio.view==='favorites'?'gemerkt':list.length===1?'Motiv':'Motive'}`;
    document.getElementById('resultCount').textContent=`${list.length} ${list.length===1?'Motiv':'Motive'}`;
    document.getElementById('motifResults').innerHTML=list.length?`<div class="grid-5">${list.map(studioDesignCard).join('')}</div>`:studio.view==='favorites'&&!favorites.length?studioEmpty('Hier ist Platz für deine Lieblingsideen.','Tippe bei einem Motiv auf das Herz. Deine Favoriten bleiben auf diesem Gerät gespeichert.'):studioEmpty('Noch kein passendes Motiv dabei?','Versuche einen anderen Suchbegriff oder wähle eine andere Kategorie.','Alle Motive zeigen',"studioNavigate('motifs')");
    studioBindCards();
}
function studioDesignCard(d) {
    const selected=favorites.includes(d.id);
    return `<article class="design-card"><button class="favorite-btn" data-favorite="${studioEscape(d.id)}" aria-pressed="${selected}" aria-label="${selected?'Aus Favoriten entfernen':'Als Favorit merken'}: ${studioEscape(studioPrettyName(d.name))}">${studioIcon('heart')}</button><button class="design-open" data-design="${studioEscape(d.id)}" aria-label="${studioEscape(studioPrettyName(d.name))} gross ansehen">${motifImageTag(d)}<div class="info"><div class="name">${studioEscape(studioPrettyName(d.name))}</div><div class="description">${studioEscape(studioLabel(d.category))}</div></div></button></article>`;
}
function studioBindCards() {
    document.querySelectorAll('[data-design]').forEach(btn=>btn.addEventListener('click',()=>{const d=studio.catalog.find(d=>d.id===btn.dataset.design);studio.returnFocus=btn;openImageModal(d.id,d.name,d.category);studioPrepareDialog('imageModal');}));
    document.querySelectorAll('[data-favorite]').forEach(btn=>btn.addEventListener('click',e=>{
        toggleFavorite(e,btn.dataset.favorite);const pressed=favorites.includes(btn.dataset.favorite);btn.setAttribute('aria-pressed',String(pressed));btn.setAttribute('aria-label',`${pressed?'Aus Favoriten entfernen':'Als Favorit merken'}: ${btn.closest('article').querySelector('.name').textContent}`);studioNavigation();
        if(studio.view==='favorites'){const index=[...document.querySelectorAll('[data-favorite]')].indexOf(btn);studioResults();const remaining=document.querySelectorAll('[data-favorite]');(remaining[Math.min(index,remaining.length-1)]||document.getElementById('motifSearch')).focus();}
    }));
    document.querySelectorAll('.design-open img').forEach(img=>img.addEventListener('error',()=>{
        const fallback=document.createElement('span');fallback.className='image-fallback';fallback.innerHTML=`${studioIcon('image')}Vorschau gerade nicht verfügbar`;
        img.replaceWith(fallback);
    },{once:true}));
}
function studioFonts() {
    document.getElementById('content').innerHTML=`<section class="page-wrap"><div class="breadcrumb"><button onclick="studioNavigate('home')">Entdecken</button><span>/</span><span>Schriftatelier</span></div><div class="page-heading"><div><div class="eyebrow">Worte mit Persönlichkeit</div><h1>Welche Schrift passt zu dir?</h1><p>Wähle eine Schrift und probiere deinen eigenen Text in der grossen Vorschau aus.</p></div><span class="heading-count">${FONTS.length} Schriften</span></div><div class="grid-5">${FONTS.map((font,i)=>`<article class="font-card"><button class="font-open" data-font="${i}" aria-label="${studioEscape(font.name)} ausprobieren"><div class="preview" style="font-family:${studioEscape(font.family)}">${studioEscape(font.sample)}</div><div class="info"><div class="name">${studioEscape(font.name)}</div><div class="description">${studioEscape(font.desc)} · Schrift #${i+1}</div></div></button></article>`).join('')}</div></section>`;
    document.querySelectorAll('[data-font]').forEach(btn=>btn.addEventListener('click',()=>{studio.returnFocus=btn;openFontModal(Number(btn.dataset.font));studioPrepareDialog('modal');}));
}
function studioPrepareDialog(id) {
    const dialog=document.getElementById(id);dialog.querySelector('.modal-close').focus();
}
// Accessibility additions do not change the selection or submission handlers.
document.addEventListener('DOMContentLoaded',()=>{
    document.querySelectorAll('.modal').forEach(dialog=>{
        dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');
        const heading=dialog.querySelector('h2');if(heading){if(!heading.id)heading.id=dialog.id+'Heading';dialog.setAttribute('aria-labelledby',heading.id);}
        dialog.querySelector('.modal-close').setAttribute('aria-label','Vorschau schliessen');
        dialog.addEventListener('keydown',e=>{
            if(e.key!=='Tab')return;
            const focusable=[...dialog.querySelectorAll('button,input,textarea,a[href],select')].filter(el=>el.getClientRects().length);
            const first=focusable[0],last=focusable[focusable.length-1];
            if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
            else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
        });
    });
    document.querySelectorAll('.form-group').forEach((group,i)=>{const input=group.querySelector('input,textarea');if(input){input.id=input.id||'studioField'+i;group.querySelector('label').htmlFor=input.id;}});
    document.querySelector('label[for="customText"]')||document.querySelector('#customText').previousElementSibling.setAttribute('for','customText');
    const observer=new MutationObserver(records=>{for(const record of records){const modal=record.target;if(modal.classList.contains('active')){modal.querySelector('.modal-close').focus();}else if(studio.returnFocus?.isConnected){studio.returnFocus.focus();}}document.body.style.overflow=document.querySelector('.modal.active')?'hidden':'';});
    document.querySelectorAll('.modal').forEach(modal=>observer.observe(modal,{attributes:true,attributeFilter:['class']}));
});
