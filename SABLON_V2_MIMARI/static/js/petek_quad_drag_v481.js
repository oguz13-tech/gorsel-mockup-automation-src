/* Pure PETEK four-corner draft adjustment. No files, masks or approvals. */
(function (root) {
  'use strict';
  function check(quad,width,height) {
    if(!Array.isArray(quad)||quad.length!==4||!Number.isFinite(width)||!Number.isFinite(height)||width<64||height<64)return false;
    const points=quad.map(p=>Array.isArray(p)&&p.length===2?p.map(Number):[NaN,NaN]);
    if(points.some(p=>p.some(v=>!Number.isFinite(v)))||
       points.some(p=>p[0]<0||p[1]<0||p[0]>width-1||p[1]>height-1))return false;
    const edges=points.map((p,i)=>[points[(i+1)%4][0]-p[0],points[(i+1)%4][1]-p[1]]);
    const lengths=edges.map(e=>Math.hypot(e[0],e[1]));
    if(Math.min(...lengths)<15)return false;
    const turns=edges.map((e,i)=>e[0]*edges[(i+1)%4][1]-e[1]*edges[(i+1)%4][0]);
    if(turns.some(t=>t<=1e-3))return false;
    const area=points.reduce((sum,p,i)=>sum+p[0]*points[(i+1)%4][1]-p[1]*points[(i+1)%4][0],0)/2;
    return area>=width*height*.018;
  }
  function closest(quad,point,scale,threshold=21) {
    if(!Array.isArray(quad)||!Array.isArray(point)||!Number.isFinite(scale)||scale<=0)return -1;
    let best=-1,min=threshold*threshold;
    quad.forEach((p,i)=>{const dist=((p[0]-point[0])*scale)**2+((p[1]-point[1])*scale)**2;
      if(dist<=min){min=dist;best=i;}
    });
    return best;
  }
  function moved(quad,index,point,width,height) {
    if(!Array.isArray(quad)||quad.length!==4||index<0||index>3||
       !Array.isArray(point)||point.length!==2||!point.every(Number.isFinite))return null;
    const next=quad.map(p=>p.slice());
    next[index]=[Math.max(0,Math.min(width-1,point[0])),Math.max(0,Math.min(height-1,point[1]))];
    return check(next,width,height)?next:null;
  }
  const api=Object.freeze({check,closest,moved});
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.PetekQuadDragV481=api;
})(typeof window!=='undefined'?window:globalThis);
