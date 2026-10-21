const {test}=require('node:test');const assert=require('node:assert/strict');
const b=require('../../SABLON_V2_MIMARI/static/js/petek_brush.js');
const quad=[[10,10],[90,10],[90,90],[10,90]];
test('continuous white stroke has solid interior despite sparse pointer events',()=>{
 const m=new Uint8Array(10000);b.stroke(m,100,100,quad,[15,50],[85,50],18,255);
 for(let x=15;x<=85;x++)assert.equal(m[50*100+x],255);
 assert.ok([...m].every(v=>v===0||v===255));
});
test('brush cannot cross quad even with center outside',()=>{
 const m=new Uint8Array(10000);b.stroke(m,100,100,quad,[0,0],[99,99],42,255);
 for(let y=0;y<100;y++)for(let x=0;x<100;x++)if(!b.inside(x,y,quad))assert.equal(m[y*100+x],0);
});
test('cursor diameter follows source-to-screen zoom and size immediately',()=>{
 assert.equal(b.cursor(18,1000,500),9);assert.equal(b.cursor(42,1000,500),21);assert.equal(b.cursor(42,1000,2000),84);
});
