const test=require('node:test'),assert=require('node:assert/strict');
const {labels,paint}=require('../../SABLON_V2_MIMARI/static/js/edge_angles_v46.js');
const view={x:0,y:0,scale:1};
test('two source corners immediately show upper-line angle without mutation',()=>{
 const p=[{x:10,y:20},{x:110,y:20}],before=JSON.stringify(p);
 assert.equal(labels(p,view).length,1);assert.equal(labels(p,view)[0].delta,0);
 assert.match(labels(p,view)[0].text,/DÜZ/);assert.equal(JSON.stringify(p),before);
});
test('drag angles and thresholds independent of pan and zoom',()=>{
 for(const [degrees,word] of [[.3,'DÜZ'],[1,'≈'],[3,'EĞİK']]){
  const p=[{x:0,y:0},{x:100,y:100*Math.tan(degrees*Math.PI/180)}];
  const a=labels(p,view)[0],b=labels(p,{x:80,y:-40,scale:4})[0];
  assert.ok(Math.abs(a.delta-degrees)<1e-8);assert.equal(a.delta,b.delta);assert.match(a.text,new RegExp(word));
 }
});
test('all four edges measured; vertical edges compare to ninety',()=>{
 const p=[{x:0,y:0},{x:100,y:0},{x:100,y:80},{x:0,y:80}];
 assert.deepEqual(labels(p,view).map(x=>x.delta),[0,0,0,0]);
});
test('labels remain in canvas during pan and resize; degenerate points ignored',()=>{
 assert.equal(labels([{x:0,y:0},{x:0,y:0}],view).length,0);
 for(const width of [90,800]){
  const boxes=[],ctx={canvas:{width,height:120},save(){},restore(){},setLineDash(){},measureText(){return {width:100}},fillText(){},fillRect(x,y,w,h){boxes.push([x,y,w,h])}};
  paint(ctx,[{x:0,y:0},{x:100,y:0}],{x:2000,y:-300,scale:3});
  assert.ok(boxes.every(([x,y,w,h])=>x>=0&&y>=0&&x+w<=width&&y+h<=120));
 }
});
