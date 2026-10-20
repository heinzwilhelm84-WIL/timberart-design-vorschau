/* Pure-model contracts; no browser, packages or network required. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../text-frame.js'),'utf8'),context);
const model = vm.runInContext('({validTextFrame,copyTextFrame,frameBounds,frameResize,FRAME_HANDLES})',context);
const plain = value => JSON.parse(JSON.stringify(value));
test('default frame has one explicit source of font size and no scale',()=>{
 const f=model.copyTextFrame();assert.equal(f.width,420);assert.equal(f.fontSize,40);assert.equal('scale' in f,false);assert.ok(model.validTextFrame(f));
});
test('width, height and font size are independent',()=>{
 const f=model.copyTextFrame();const resized=model.copyTextFrame({...f,width:220,height:300});assert.equal(resized.fontSize,f.fontSize);
 const enlarged=model.copyTextFrame({...f,fontSize:80});assert.equal(enlarged.width,f.width);assert.equal(enlarged.height,f.height);
});
test('invalid, nonfinite, unknown and dual-scaling fields are rejected',()=>{
 const f=model.copyTextFrame();
 for(const bad of [null,[],{...f,scale:2},{...f,width:NaN},{...f,height:Infinity},{...f,fontSize:0},{...f,x:null},{...f,align:'justify'},{...f,width:32,padding:20}]) assert.equal(model.validTextFrame(bad),false);
 assert.throws(()=>model.copyTextFrame({...f,height:-5}));
});
test('all three alignments and fractional values survive exact roundtrip',()=>{
 for(const align of ['left','center','right']) {const f={...model.copyTextFrame(),align,width:387.4,fontSize:32.5,rotation:-31.2};assert.deepEqual(plain(model.copyTextFrame(JSON.parse(JSON.stringify(f)))),plain(f));}
});
test('copied frames are independent for edit and duplicate',()=>{
 const a=model.copyTextFrame(),b=model.copyTextFrame(a);b.width=220;assert.equal(a.width,420);
});
test('rotation bounds retain size and detect out-of-surface corners',()=>{
 const f={...model.copyTextFrame(),x:300,y:300,width:400,height:100,rotation:90};const b=model.frameBounds(f);
 assert.ok(Math.abs(b.right-b.left-100)<1e-8);assert.ok(Math.abs(b.bottom-b.top-400)<1e-8);
 assert.ok(model.frameBounds({...f,y:564}).bottom>600);assert.equal(f.width,400);
});

function anchor(f,sx,sy) {const a=f.rotation*Math.PI/180;return {x:f.x-Math.cos(a)*sx*f.width/2+Math.sin(a)*sy*f.height/2,y:f.y-Math.sin(a)*sx*f.width/2-Math.cos(a)*sy*f.height/2};}
function near(a,b) {assert.ok(Math.abs(a-b)<1e-8,`${a} != ${b}`);}
test('all eight handles retain opposite anchor at all rotations; no font scaling',()=>{
 for(const rotation of [0,31,90,-47,179]) for(const [handle,[sx,sy]] of Object.entries(model.FRAME_HANDLES)) {
  const f={...model.copyTextFrame(),x:300,y:300,width:240,height:160,rotation,align:'right'},before=anchor(f,sx,sy);
  const r=model.frameResize(f,handle,23,-17),after=anchor(r,sx,sy);
  near(before.x,after.x);near(before.y,after.y);
  for(const k of ['fontSize','rotation','align','padding','lineHeight']) assert.equal(r[k],f[k]);
  if(!sx) assert.equal(r.width,f.width);if(!sy) assert.equal(r.height,f.height);
  assert.ok(model.validTextFrame(r));assert.deepEqual(plain(f),plain({...model.copyTextFrame(),x:300,y:300,width:240,height:160,rotation,align:'right'}));
 }
});
test('rotated frame uses local width/height axes',()=>{
 const f={...model.copyTextFrame(),x:300,y:300,rotation:90};
 const w=model.frameResize(f,'e',0,50);near(w.width,f.width+50);near(w.height,f.height);near(w.x,f.x);near(w.y,f.y+25);
 const h=model.frameResize(f,'s',-40,0);near(h.height,f.height+40);near(h.width,f.width);near(h.x,f.x-20);
});
test('all resize limits preserve validity and opposite anchors',()=>{
 for(const rotation of [0,31,90,-47]) for(const [handle,[sx,sy]] of Object.entries(model.FRAME_HANDLES)) for(const x of [36,300,564]) for(const y of [36,300,564]) for(const delta of [-10000,10000]) {
  const f={...model.copyTextFrame(),x,y,rotation,padding:30},r=model.frameResize(f,handle,delta,-delta);
  assert.ok(model.validTextFrame(r));const a=anchor(f,sx,sy),b=anchor(r,sx,sy);near(a.x,b.x);near(a.y,b.y);
 }
});
test('repeat same pointer delta is deterministic and reversing restores frame',()=>{
 const f={...model.copyTextFrame(),x:300,y:300,rotation:31};
 const a=model.frameResize(f,'se',40,30),b=model.frameResize(f,'se',40,30);
 assert.deepEqual(plain(a),plain(b));const back=model.frameResize(a,'se',-40,-30);
 for(const key of ['x','y','width','height']) near(back[key],f[key]);
});
test('resize roundtrip retains every frame property, not another scale',()=>{
 const f=model.frameResize({...model.copyTextFrame(),align:'left',fontSize:37.5,rotation:-27},'nw',15,10);
 assert.deepEqual(plain(model.copyTextFrame(JSON.parse(JSON.stringify(f)))),plain(f));assert.equal('scale' in f,false);
});
test('invalid resize handles and nonfinite deltas are rejected',()=>{
 const f=model.copyTextFrame();for(const args of [['bad',1,1],['e',NaN,1],['e',1,Infinity]]) assert.throws(()=>model.frameResize(f,...args));
});
