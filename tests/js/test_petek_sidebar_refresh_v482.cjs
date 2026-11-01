'use strict';
/* Regression for real six-category renderSidebar preserving PETEK live DOM. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const main=fs.readFileSync(path.resolve(__dirname,'../../SABLON_V2_MIMARI/static/js/main.js'),'utf8');
const petek=fs.readFileSync(path.resolve(__dirname,'../../SABLON_V2_MIMARI/static/js/petek_editor_v477.js'),'utf8');
function codeUnderTest(){
  // Run the ACTUAL DOM preservation blocks from renderSidebar, not a rewrite
  // of their logic: deliberately exclude unrelated category building.
  const before=main.match(/const petekSeventhCategory = document\.getElementById\('petekV477Nav'\);[\s\S]*?catDiv\.replaceChildren\(\);/);
  const after=main.match(/if \(petekSeventhCategory\) \{\s*catDiv\.appendChild\(petekSeventhCategory\);[\s\S]*?applyBulkSelectionUi\(\);/);
  assert.ok(before,'renderSidebar must preserve PETEK nodes before clearing categories');
  assert.ok(after,'renderSidebar must restore PETEK nodes after six category rebuild');
  return new Function('document','catDiv','applyBulkSelectionUi',before[0]+'\n'+after[0]);
}
class Node {
  constructor(id){this.id=id;this.parentElement=null;this.children=[];this.listeners=new Set();}
  appendChild(n){n.remove();n.parentElement=this;this.children.push(n);return n;}
  remove(){if(this.parentElement){const children=this.parentElement.children;
    const at=children.indexOf(this);if(at>=0)children.splice(at,1);this.parentElement=null;}}
  after(n){const parent=this.parentElement;assert.ok(parent);
    n.remove();const idx=parent.children.indexOf(this);parent.children.splice(idx+1,0,n);n.parentElement=parent;}
  contains(n){return this.children.includes(n)||this.children.some(c=>c.contains(n));}
  replaceChildren(){for(const child of this.children)child.parentElement=null;this.children=[];}
}
test('Refresh six categories while PETEK list is mounted, keep SAME node and listeners',()=>{
  const categories=new Node('categories'),nav=new Node('petekV477Nav'),list=new Node('petekV477ListPane');
  const eventHandler=()=>{};list.listeners.add(eventHandler);
  categories.appendChild(new Node('legacy'));categories.appendChild(nav);categories.appendChild(list);
  const doc={getElementById(id){for(const n of [nav,list]){if(n.id===id&&categories.contains(n))return n;}return null;}};
  let called=0;codeUnderTest()(doc,categories,()=>called++);
  assert.deepEqual(categories.children.map(n=>n.id),['petekV477Nav','petekV477ListPane']);
  assert.equal(list.parentElement,categories);
  assert.ok(list.listeners.has(eventHandler));
  assert.equal(called,1);
});
test('Refresh six categories when PETEK list is still in editor workspace',()=>{
  const categories=new Node('categories'),workspace=new Node('petekV477Workspace');
  const nav=new Node('petekV477Nav'),list=new Node('petekV477ListPane');
  categories.appendChild(nav);workspace.appendChild(list);
  const doc={getElementById(id){return id==='petekV477Nav'?nav:id==='petekV477ListPane'?list:null;}};
  codeUnderTest()(doc,categories,()=>{});
  assert.deepEqual(categories.children,[nav]);
  assert.equal(list.parentElement,workspace);
});
test('Missing category nav must preserve live PETEK list instead of deleting it',()=>{
  const categories=new Node('categories'),list=new Node('petekV477ListPane');
  categories.appendChild(list);
  const doc={getElementById(id){return id==='petekV477ListPane'&&categories.contains(list)?list:null;}};
  const old=console.error;console.error=()=>{};
  try{codeUnderTest()(doc,categories,()=>{});}finally{console.error=old;}
  assert.deepEqual(categories.children,[list]);
});
test('PETEK and main sidebar scripts are cache-busted together after bugfix',()=>{
 const html=fs.readFileSync(path.resolve(__dirname,'../../SABLON_V2_MIMARI/templates/index.html'),'utf8');
 for(const script of ['main.js','petek_editor_v477.js']){
   assert.ok(html.includes(script+'?v=488-legible'),script+' must have current cache key');
 }
 assert.ok(html.includes('petek_quad_drag_v481.js?v=482-sidebar'));
});
test('Editor caches detached host and guards missing list at start; no null classList crash',()=>{
  assert.match(petek,/listHost:\s*null/);
  assert.match(petek,/s\.listHost=\$\('petekV477ListPane'\)/);
  assert.match(petek,/const list=\$\('petekV477ListPane'\)\|\|s\.listHost/);
  assert.match(petek,/if\(!normal\|\|!pane\|\|!nav\|\|!list\)/);
  assert.match(petek,/list\?\.classList\.remove\('in-sidebar'\)/);
});
