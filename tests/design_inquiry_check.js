/* Pure payload/provenance contracts. No network or customer persistence. */
const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function context(rows=[],fail=false){
 const calls=[];const c=vm.createContext({Blob,TextEncoder,FormData:class{constructor(f){this.values=f;}get(k){return this.values[k]||'';}},
  document:{addEventListener(){}},window:{addEventListener(){}},fetch:async url=>{calls.push(url);if(fail)throw Error();return{ok:true,json:async()=>({motifs:rows})};}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../design-export.js'),'utf8'),c);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../design-inquiry.js'),'utf8'),c);
 return {c,calls,run:code=>vm.runInContext(code,c)};
}
const plain=x=>JSON.parse(JSON.stringify(x));
test('original reference requires exact Drive original URL and matching identity',async()=>{
 const {run,calls}=context([{id:'motif',source:{provider:'google-drive',fileId:'motif',originalUrl:'https://drive.google.com/file/d/motif/view',originalFilename:'Original.png',access_token:'not-a-real-token'}}]);
 const r=plain(await run("inquirySource('motif')"));assert.equal(r.source.originalUrl,'https://drive.google.com/file/d/motif/view');assert.equal(r.source.originalFilename,'Original.png');assert.equal('access_token' in r.source,false);assert.deepEqual(calls,['./data/motifs-manifest.json']);
});
for(const [name,url,fileId,provider] of [
 ['thumbnail','https://drive.google.com/thumbnail?id=motif','motif','google-drive'],
 ['wrong identity','https://drive.google.com/file/d/motif/view','another','google-drive'],
 ['foreign host','https://example.invalid/file','motif','google-drive'],
 ['unknown provider','https://drive.google.com/file/d/motif/view','motif','unknown'],
 ['missing URL',undefined,'motif','google-drive']
])test(name+' never becomes an original link',async()=>{
 const {run}=context([{id:'motif',source:{provider,fileId,originalUrl:url}}]);const r=await run("inquirySource('motif')");assert.equal(r.source.originalUrl,null);
});
test('missing manifest or missing record does not invent a filename or original URL',async()=>{
 for(const fail of [true,false]){
  const {run}=context([],fail),r=await run("inquirySource('unknown')");assert.equal(r.source.originalUrl,null);assert.equal(r.source.originalFilename,undefined);
 }
});
test('source manifest is read only once after successful loading',async()=>{
 const {run,calls}=context([]);await run("inquirySource('one')");await run("inquirySource('two')");assert.equal(calls.length,1);
});
test('XML escape protects SVG from markup and invalid control characters',()=>{
 const {run}=context();assert.equal(run(`inquiryXML('<script>"&\u0000')`),'&lt;script&gt;&quot;&amp;�');
});
test('payload keeps full multiline text, maximum and all reconstruction fields',()=>{
 const {run,c}=context();const raw='ÄÖÜ ♥ <script>\n\n'+('lang '.repeat(10000))+'\n';
 const draft={layoutVersion:3,motifId:'motif',text:raw,fontId:'sample',textFrame:{x:313,y:282,width:222,height:101,fontSize:47.5,rotation:-47,align:'right',padding:12,lineHeight:1.3}};
 const design={draft,type:'personalisiert',font:{name:'Sample',id:'sample'},motif:{id:'motif',name:'Motif',category:'Cat',source:{originalUrl:null}}};
 c.fixture={design,form:{name:'  Test  ',email:'',phone:'',message:'Ä & \nBemerkung'}};
 const payload=plain(run('inquiryPayload(fixture)'));assert.equal(payload.name,'Test');assert.equal(payload.wish_text,raw);assert.equal(payload.max_font_size,47.5);assert.deepEqual(JSON.parse(payload.design_data).draft,draft);assert.equal(payload.original_file_url,'');assert.equal(payload.email,'');assert.equal(payload.message,'Ä & \nBemerkung');assert.equal(payload._subject,'Unverbindliche TimberArt-Designanfrage');
});
test('unpersonalised payload does not invent text, font or layout',()=>{
 const {run,c}=context();c.fixture={form:{name:'Test'},design:{draft:null,type:'motiv',motif:{id:'m',name:'M',category:'C',source:{}}}};
 const p=plain(run('inquiryPayload(fixture)'));assert.equal(p.wish_text,'');assert.equal(p.font_id,'');assert.equal(p.max_font_size,'');assert.equal(p.layout_version,'');
});
