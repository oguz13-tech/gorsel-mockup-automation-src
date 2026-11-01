'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const geometry=require('../../SABLON_V2_MIMARI/static/js/petek_quad_drag_v481.js');
const quad=[[120,60],[450,74],[445,315],[112,310]];
test('Auto quad manually adjusted: drag only selected nearest handle',()=>{
 assert.equal(geometry.check(quad,640,400),true);
 assert.equal(geometry.closest(quad,[122,62],.55),0);
 assert.equal(geometry.closest(quad,[450,76],1.8),1);
 assert.equal(geometry.closest(quad,[300,200],.55),-1);
 const updated=geometry.moved(quad,0,[128,66],640,400);
 assert.ok(updated);
 assert.deepEqual(updated[0],[128,66]);
 assert.deepEqual(updated[1],quad[1]);
 assert.deepEqual(quad[0],[120,60], 'Approved/source geometry passed into helper remains unchanged');
});
test('Reject crossings, flipped quad and collapsed/folded panel',()=>{
 assert.equal(geometry.moved(quad,0,[400,340],640,400),null);
 assert.equal(geometry.moved(quad,1,[0,0],640,400),null);
 assert.equal(geometry.moved(quad,0,[450,74],640,400),null);
});
test('Reject malformed image bounds and nonfinite candidate',()=>{
 assert.equal(geometry.check(quad,0,400),false);
 assert.equal(geometry.moved(quad,1,[NaN,2],640,400),null);
 assert.equal(geometry.moved([],0,[100,100],640,400),null);
 assert.equal(geometry.closest(quad,[120,60],0),-1);
});
test('Zoom changes only hit tolerance in display pixel units',()=>{
 assert.equal(geometry.closest(quad,[140,60],.5),0);
 assert.equal(geometry.closest(quad,[140,60],2),-1);
});
