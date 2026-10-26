/* Source-pixel measurements; viewport only affects label placement. */
(function(root){
'use strict';
function labels(points, view) {
    const edges=[[0,1,0],[1,2,90],[3,2,0],[0,3,90]], result=[];
    for(const [a,b,target] of edges){
        const p=points[a],q=points[b];
        if(!p||!q||![p.x,p.y,q.x,q.y].every(Number.isFinite))continue;
        if(Math.hypot(q.x-p.x,q.y-p.y)<1e-6)continue;
        let delta=Math.atan2(q.y-p.y,q.x-p.x)*180/Math.PI-target;
        delta=((delta+90)%180+180)%180-90;
        const magnitude=Math.abs(delta),symbol=magnitude<=.5?'✓ DÜZ':magnitude<=2?'≈':'EĞİK';
        result.push({delta,text:`${symbol} ${delta>=0?'+':''}${delta.toFixed(1)}°`,
            color:magnitude<=.5?'#86efac':magnitude<=2?'#fde047':'#fca5a5',
            x:view.x+(p.x+q.x)/2*view.scale,y:view.y+(p.y+q.y)/2*view.scale-16});
    }
    return result;
}
function paint(ctx,points,view){
    ctx.save();ctx.font='bold 12px sans-serif';ctx.textAlign='left';ctx.textBaseline='middle';ctx.setLineDash([]);
    for(const item of labels(points,view)){
        const w=Math.min(ctx.measureText(item.text).width+12,ctx.canvas.width);
        const x=Math.max(0,Math.min(ctx.canvas.width-w,item.x-w/2));
        const y=Math.max(11,Math.min(ctx.canvas.height-11,item.y));
        ctx.fillStyle='rgba(15,23,42,.92)';ctx.fillRect(x,y-11,w,22);
        ctx.fillStyle=item.color;ctx.fillText(item.text,x+6,y,Math.max(1,w-12));
    }
    ctx.restore();
}
const api={labels,paint};root.EdgeAnglesV46=api;
if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
