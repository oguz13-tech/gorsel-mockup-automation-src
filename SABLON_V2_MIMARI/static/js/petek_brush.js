/* Source-pixel binary coverage. Pure helpers shared by canvas and Node tests. */
(function(root) {
  'use strict';
  function inside(x,y,quad) {
    if(quad.length!==4)return false;
    let sign=0;
    for(let i=0;i<4;i++) {
      const a=quad[i], b=quad[(i+1)%4];
      const cross=(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]);
      if(Math.abs(cross)<1e-8)continue;
      const next=Math.sign(cross);if(sign && sign!==next)return false;sign=next;
    }
    return sign!==0;
  }
  function stroke(mask,w,h,quad,a,b,diameter,value) {
    if(quad.length!==4)throw Error('Önce dört köşeyi seçin');
    const r=diameter/2,dx=b[0]-a[0],dy=b[1]-a[1],len=dx*dx+dy*dy;
    for(let y=Math.max(0,Math.floor(Math.min(a[1],b[1])-r));y<=Math.min(h-1,Math.ceil(Math.max(a[1],b[1])+r));y++)
      for(let x=Math.max(0,Math.floor(Math.min(a[0],b[0])-r));x<=Math.min(w-1,Math.ceil(Math.max(a[0],b[0])+r));x++) {
        const t=len?Math.max(0,Math.min(1,((x-a[0])*dx+(y-a[1])*dy)/len)):0;
        if((x-a[0]-t*dx)**2+(y-a[1]-t*dy)**2<=r*r && inside(x,y,quad))mask[y*w+x]=value?255:0;
      }
    return mask;
  }
  function cursor(diameter,sourceWidth,screenWidth){return diameter*screenWidth/sourceWidth;}
  const api={inside,stroke,cursor};
  if(typeof module!=='undefined')module.exports=api;else root.PetekBrush=api;
})(typeof globalThis!=='undefined'?globalThis:this);
