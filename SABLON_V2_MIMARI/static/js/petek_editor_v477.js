/* V4.7.7 PETEK native seventh category — same browser page, shared V3 registry.
 * Zero automatic approval. Existing approved mask is always read-only.
 * Full source pixels are authoritative, visual canvas uses fit-to-screen.
 */
(function () {
'use strict';
const $ = id => document.getElementById(id);
const category='06_Petek_Kapama';
const s={
  active:false,photo:null,name:'',uid:'',sha:'',status:'NEW',
  width:0,height:0,scale:1,quad:[],curves:{top:[],bottom:[]},
  img:null,mask:null,base:null,mode:'corners',painting:false,
  dragCorner:-1,dirty:false,needsCurveApply:false
};
const names={corners:'Dört köşe',wood:'Baskı ahşabını boya',protect:'Delik / yan yüzü koru',top:'Üst kavis',bottom:'Alt kavis'};
function notice(message,bad=false){
 const e=$('petekV477Status'); if(!e)return;
 e.textContent=String(message);e.style.color=bad?'#fca5a5':'#c6f6d5';
}
function photoUrl(name){return '/api/petek/photo/'+encodeURIComponent(name);}
function detailUrl(name,uid){return '/api/petek/detail/'+encodeURIComponent(name)+'?uid='+encodeURIComponent(uid);}
async function api(path,body){
 const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
 const data=await r.json();
 if(!r.ok||!data.success)throw Error(data.error||'PETEK_API_ERROR');
 return data;
}
function blank(){
 let c=document.createElement('canvas');c.width=s.width;c.height=s.height;
 c.getContext('2d',{willReadFrequently:true}).fillStyle='#000';
 c.getContext('2d').fillRect(0,0,c.width,c.height);return c;
}
function imageOf(url){return new Promise((resolve,reject)=>{
 let i=new Image();i.onload=()=>resolve(i);i.onerror=()=>reject(Error('PETEK_GORSEL_YUKLENEMEDI'));i.src=url;
});}
async function decodeCanvas(url){
 const image=await imageOf(url),c=blank();
 if(image.naturalWidth!==s.width||image.naturalHeight!==s.height)
    throw Error('MASKE_KAYNAK_BOYUTU_UYUSMUYOR');
 c.getContext('2d',{willReadFrequently:true}).drawImage(image,0,0);
 return c;
}
function maskUrl(canvas){
 // Canvas is RGBA, but PETEK registry requires single-channel grayscale.
 // Convert via a proper browser-produced 8-bit grayscale PNG by using RGB
 // equal channels; cv2 IMREAD_UNCHANGED would return 4 channels. Python API
 // explicitly accepts RGBA with RGB-equivalent pixels and alpha=255.
 return canvas.toDataURL('image/png');
}
function content(){return {name:s.name,uid:s.uid,source_sha:s.sha,quad:s.quad,
 mask:maskUrl(s.mask),curve_points:s.curves,base_mask:s.base?maskUrl(s.base):null,
 physical_aspect:Number($('petekV477Aspect').value)};}
function limited(){return s.status==='APPROVED';}
function editingAllowed(){
 if(limited()){notice('Onaylı PETEK maskesi kilitli. Mevcut 45 başarılı şablon korunur.',true);return false;}
 return true;
}
function fit(){
 const canvas=$('petekV477Canvas'),area=$('petekV477Drawing');
 if(!canvas||!s.img)return;
 const box=area.getBoundingClientRect();
 s.scale=Math.min(1,Math.max(0.05,Math.min((box.width-32)/s.width,(box.height-46)/s.height)));
 canvas.width=Math.max(1,Math.round(s.width*s.scale));
 canvas.height=Math.max(1,Math.round(s.height*s.scale));
 draw();
}
function draw(){
 const canvas=$('petekV477Canvas');if(!canvas||!s.img)return;
 let ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height,k=s.scale;
 ctx.clearRect(0,0,w,h);ctx.drawImage(s.img,0,0,w,h);
 if(s.mask){
    const tint=document.createElement('canvas');tint.width=w;tint.height=h;
    const t=tint.getContext('2d',{willReadFrequently:true});
    t.drawImage(s.mask,0,0,w,h);
    // The registry mask is opaque grayscale: black pixels have alpha=255 too.
    // source-in would wrongly tint the entire PETEK photo, including vents.
    // Convert the grayscale *value* to overlay coverage, at preview size only.
    const overlay=t.getImageData(0,0,w,h);
    for(let i=0;i<overlay.data.length;i+=4){
       const coverage=overlay.data[i];
       overlay.data[i]=45;overlay.data[i+1]=222;overlay.data[i+2]=116;
       overlay.data[i+3]=Math.round(coverage*0.60);
    }
    t.putImageData(overlay,0,0);
    ctx.drawImage(tint,0,0);
 }
 if(s.quad.length){
    ctx.lineWidth=2;ctx.strokeStyle='#ff5555';ctx.fillStyle='#ff4444';
    ctx.beginPath();s.quad.forEach((p,i)=>i?ctx.lineTo(p[0]*k,p[1]*k):ctx.moveTo(p[0]*k,p[1]*k));
    if(s.quad.length===4)ctx.closePath();ctx.stroke();
    s.quad.forEach((p,i)=>{
      ctx.beginPath();ctx.arc(p[0]*k,p[1]*k,5,0,Math.PI*2);ctx.fill();
      ctx.fillStyle='white';ctx.font='bold 12px Arial';ctx.fillText(String(i+1),p[0]*k+7,p[1]*k-7);
      ctx.fillStyle='#ff4444';
    });
 }
 for(const type of ['top','bottom']){
   const pts=s.curves[type];if(!pts.length)continue;
   ctx.strokeStyle=type==='top'?'#ffd447':'#33e0ff';ctx.fillStyle=ctx.strokeStyle;
   ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p[0]*k,p[1]*k):ctx.moveTo(p[0]*k,p[1]*k));ctx.stroke();
   for(const p of pts){ctx.beginPath();ctx.arc(p[0]*k,p[1]*k,4,0,7);ctx.fill();}
 }
}
function point(event){
 const r=$('petekV477Canvas').getBoundingClientRect();
 return [Math.max(0,Math.min(s.width-1,(event.clientX-r.left)*s.width/r.width)),
         Math.max(0,Math.min(s.height-1,(event.clientY-r.top)*s.height/r.height))];
}
function paintAt(event,first){
 const p=point(event),c=s.base||s.mask,ctx=c.getContext('2d',{willReadFrequently:true});
 ctx.lineCap='round';ctx.lineJoin='round';
 // Paint only within reviewed front face, even when brush touches its border.
 ctx.save();ctx.beginPath();
 s.quad.forEach((q,i)=>i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]));
 ctx.closePath();ctx.clip();
 const brush=Math.max(2,Number($('petekV477Brush').value)||20);
 ctx.lineWidth=brush;ctx.strokeStyle=s.mode==='wood'?'#ffffff':'#000000';
 if(first){ctx.beginPath();ctx.arc(p[0],p[1],brush/2,0,Math.PI*2);ctx.fillStyle=ctx.strokeStyle;ctx.fill();s.lastPoint=p;}
 else{ctx.beginPath();ctx.moveTo(...s.lastPoint);ctx.lineTo(...p);ctx.stroke();s.lastPoint=p;}
 ctx.restore();
 s.dirty=true;
 if(s.base){s.needsCurveApply=true;notice('Temel maske değişti. Kaydetmeden önce «Kavisleri Uygula» seç.');}
 draw();
}
function setMode(mode){
 if(!editingAllowed())return;
 if(!s.img){notice('Önce PETEK şablonu seç.',true);return;}
 if(mode==='corners'&&s.quad.length===4){
    if(!confirm('4 köşe yeniden işaretlenecek. Bu TASLAĞIN maskesi ve kavisleri sıfırlanacak. Onaylı kayıtlar değişmeyecek.'))return;
    s.quad=[];s.curves={top:[],bottom:[]};s.base=null;s.mask=blank();s.dirty=true;
 }
 s.mode=mode;
 $('petekV477Mode').textContent='Mod: '+names[mode];
 notice(mode==='corners'?'Köşeleri sol üst, sağ üst, sağ alt, sol alt sırasıyla işaretle.':
       mode==='wood'?'Yeşil boyanacak ön ahşabı boya. Dikey yarıklara ve zemine taşırma.':
       mode==='protect'?'Siyah koruma fırçası: delikler, gölgeler, üst/alt kavis ve yan yüz.':
       'Kavis uçları yan kenarlara ulaşmalı. Noktaları soldan sağa işaretle.');
 draw();
}
async function select(name,uid){
 try{
  const data=await api(detailUrl(name,uid));
  s.name=name;s.uid=data.uid;s.sha=data.source_sha;s.status=data.status;
  s.width=data.width;s.height=data.height;s.quad=data.quad||[];
  s.curves=data.curve_points||{top:[],bottom:[]};s.needsCurveApply=false;
  s.base=null;s.dirty=false;
  s.img=await imageOf(photoUrl(name));
  s.mask=data.mask?await decodeCanvas(data.mask):blank();
  s.base=data.base_mask?await decodeCanvas(data.base_mask):null;
  $('petekV477Aspect').value=String(data.physical_aspect);
  $('petekV477Name').textContent=name+' · '+data.status+' · '+s.uid;
  $('petekV477Approve').disabled=data.status==='APPROVED';
  $('petekV477Save').disabled=data.status==='APPROVED';
  $('petekV477Revision').disabled=data.status!=='APPROVED';
  $('petekV477Confirm').checked=false;
  $('petekV477Mode').textContent='Mod: '+names[s.mode];
  fit();
  notice(data.status==='APPROVED'?'Onaylı SHA-kilitli maske yüklendi. Yalnız görüntüle.':
        data.status==='DRAFT'?'Taslak maskeyi kontrol et, kavis ve yarıkları onayla.':
        'Yeni PETEK: dört köşeyi işaretle, otomatik taslak maske çıkar, sonra düzelt.');
 }catch(e){notice(e.message,true);}
}
async function reload(preferUid){
 try{
  const data=await api('/api/petek/templates');
  const selectEl=$('petekV477Select'),previous=selectEl.value;
  selectEl.replaceChildren();
  for(const item of data.items){
    const option=document.createElement('option');
    option.value=JSON.stringify([item.name,item.uid]);
    option.textContent=item.name+' · '+item.uid+' — '+item.status;
    selectEl.append(option);
  }
  const scanned=Number(data.scanned_photos||0);
  $('petekV477Count').textContent=data.items.length+' kayıt · '+scanned+' PETEK fotoğrafı';
  if(data.items.length){
    let preferred=preferUid
      ?Array.from(selectEl.options).find(o=>JSON.parse(o.value)[1]===preferUid)?.value
      :null;
    selectEl.value=preferred ||
      (Array.from(selectEl.options).some(x=>x.value===previous)
         ?previous:selectEl.options[0].value);
    if(!selectEl.value)selectEl.value=selectEl.options[0].value;
    const pair=JSON.parse(selectEl.value);
    await select(pair[0],pair[1]);
  }else{
    $('petekV477Name').textContent='PETEK kaydı görüntülenemedi.';
    const path=String(data.working_path||'2_SABLON_HAVUZU/Petek_Dolabi');
    const warning=(data.warnings||[]).map(w=>w.file+': '+w.error).slice(0,2).join(' | ');
    notice(scanned?('PETEK fotoğrafları bulundu ama kayıtlar yüklenemedi: '+warning+
                 ' · Okunan klasör: '+path):
                 ('Bu sunucunun okuduğu PETEK klasörü boş: '+path+
                 ' · Fotoğrafların bu klasörde olduğunu doğrula.'),true);
  }
 }catch(e){notice(e.message,true);}
}
async function autoMask(){
 if(!editingAllowed())return;
 if(s.quad.length!==4){notice('Önce dört köşe tamamlanmalı.',true);return;}
 if(!confirm('Yalnız açık TASLAK maske yeniden oluşturulacak. Mevcut taslak boyama sıfırlansın mı?'))return;
 try{
  const data=await api('/api/petek/auto-mask',{name:s.name,source_sha:s.sha,quad:s.quad});
  s.mask=await decodeCanvas(data.mask);s.base=null;s.curves={top:[],bottom:[]};
  s.needsCurveApply=false;s.dirty=true;draw();
  notice('Otomatik TASLAK oluşturuldu. Dikey delikler, kavisler ve yanları gözle kontrol et.');
 }catch(e){notice(e.message,true);}
}
async function applyCurves(){
 if(!editingAllowed())return;
 if(s.quad.length!==4){notice('Önce dört köşe tamamlanmalı.',true);return;}
 if(!s.curves.top.length&&!s.curves.bottom.length){
    notice('Önce üst/alt kavis noktalarını yerleştir.',true);return;
 }
 try{
  if(!s.base)s.base=s.mask;
  const data=await api('/api/petek/curve-preview',{
    name:s.name,source_sha:s.sha,quad:s.quad,base_mask:maskUrl(s.base),curve_points:s.curves
  });
  s.mask=await decodeCanvas(data.mask);s.needsCurveApply=false;s.dirty=true;draw();
  notice('Kavis maskesi görüntülendi; delik ve yer gölgelerini kontrol et.');
 }catch(e){notice(e.message,true);}
}
function undoCurve(){
 if(!editingAllowed())return;
 const arr=s.curves[s.mode];if(!Array.isArray(arr)||!arr.length)return;
 arr.pop();s.needsCurveApply=true;s.dirty=true;draw();
 notice('Son kavis noktası çıkarıldı. Kavisleri yeniden uygula.');
}
async function save(){
 if(!editingAllowed()||!s.img)return;
 if(s.quad.length!==4){notice('Dört köşe tamamlanmadan taslak kaydedilemez.',true);return;}
 if(s.needsCurveApply){notice('Kavis noktalarını/maskesini değiştirdin; önce Kavisleri Uygula.',true);return;}
 if(!confirm('Yalnız PETEK TASLAĞI kaydedilecek. Orijinal ve onaylı maskeler korunacak. Devam?'))return;
 try{
  const data=await api('/api/petek/save-draft',content());
  s.status=data.status;s.dirty=false;
  notice('PETEK taslağı kaydedildi. İncelemeyi tamamladıktan sonra ayrı onayla.');
  await reload();
 }catch(e){notice(e.message,true);}
}
async function approve(){
 if(!s.img||s.status!=='DRAFT'){notice('Önce TASLAK kaydet, sonra onayla.',true);return;}
 if(s.dirty||s.needsCurveApply){notice('Değişiklik var. Önce taslağı kaydet.',true);return;}
 const reviewer=$('petekV477Reviewer').value.trim();
 if(!reviewer){notice('Onaylayan kişinin adını gir.',true);return;}
 if(!$('petekV477Confirm').checked){
   notice('Dikey delikler, üst-alt kavis, yan yüzler ve zemini kontrol ettiğini işaretle.',true);return;
 }
 if(!confirm('Bu PETEK maskesini insan onaylı, SHA-kilitli üretim şablonu yapıyorsun. Onaylıyor musun?'))return;
 try{
  await api('/api/petek/approve',{name:s.name,uid:s.uid,source_sha:s.sha,confirmed_sha:s.sha,
    reviewer,confirm:'I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR'});
  await reload();notice('PETEK MASKESİ ONAYLANDI. Ortak 7 kategori üretiminde kullanılabilir.');
 }catch(e){notice(e.message,true);}
}
async function newRevision(){
 if(!s.img||s.status!=='APPROVED')return;
 if(!confirm('Onaylı PETEK maskesi kilitli kalacak. Aynı fotoğraf için yeni, BAĞIMSIZ _r2 TASLAĞI oluşturulsun mu?'))return;
 try{
    const data=await api('/api/petek/new-revision',{
        name:s.name,uid:s.uid,source_sha:s.sha,confirmed_sha:s.sha});
    await reload(data.uid);
    notice('Onaylı eski maske korunuyor. Yeni '+data.uid+' TASLAĞINI düzenleyebilirsin.');
 }catch(e){notice(e.message,true);}
}
function pointerDown(e){
 if(!s.img||!editingAllowed())return;
 e.preventDefault();const p=point(e);
 if(s.mode==='corners'){
   if(s.quad.length>=4)return;
   s.quad.push(p);s.dirty=true;draw();
   notice('Köşeler: '+s.quad.length+'/4'+(s.quad.length===4?' · Şimdi Taslak Maske oluştur.':''));
 }else if(s.mode==='wood'||s.mode==='protect'){
   if(s.quad.length!==4){notice('Önce dört köşe gerekir.',true);return;}
   s.painting=true;paintAt(e,true);
 }else if(s.mode==='top'||s.mode==='bottom'){
   if(s.quad.length!==4){notice('Önce dört köşe gerekir.',true);return;}
   s.curves[s.mode].push(p);s.needsCurveApply=true;s.dirty=true;
   draw();notice('Kavis noktası eklendi. Bitince «Kavisleri Uygula» seç.');
 }
}
function pointerMove(e){if(!s.painting)return;e.preventDefault();paintAt(e,false);}
function pointerUp(){s.painting=false;s.lastPoint=null;}
function start(){
 s.active=true;
 const normal=$('main'),pane=$('petekV477Editor');
 normal.style.display='none';pane.style.display='flex';
 $('petekV477Nav').classList.add('selected');
 reload();
}
function exit(){
 if(!s.active)return;
 if(s.dirty&&!confirm('Kaydedilmemiş PETEK taslağın var. Kaydetmeden çıkılsın mı?'))return;
 s.active=false;
 $('main').style.display='flex';$('petekV477Editor').style.display='none';
 $('petekV477Nav').classList.remove('selected');
}
function init(){
 const pane=$('petekV477Editor');if(!pane)return;
 $('petekV477Nav').addEventListener('click',start);
 $('petekV477Close').addEventListener('click',exit);
 $('petekV477Reload').addEventListener('click',reload);
 $('petekV477Select').addEventListener('change',e=>{
    const [name,uid]=JSON.parse(e.target.value);
    select(name,uid);
 });
 for(const b of document.querySelectorAll('[data-petek-mode]'))
   b.addEventListener('click',()=>setMode(b.dataset.petekMode));
 $('petekV477Auto').addEventListener('click',autoMask);
 $('petekV477CurveApply').addEventListener('click',applyCurves);
 $('petekV477CurveUndo').addEventListener('click',undoCurve);
 $('petekV477Save').addEventListener('click',save);
 $('petekV477Approve').addEventListener('click',approve);
 $('petekV477Revision').addEventListener('click',newRevision);
 $('petekV477Canvas').addEventListener('pointerdown',pointerDown);
 $('petekV477Canvas').addEventListener('pointermove',pointerMove);
 $('petekV477Canvas').addEventListener('pointerup',pointerUp);
 $('petekV477Canvas').addEventListener('pointercancel',pointerUp);
 document.querySelector('#categories').addEventListener('click',event=>{
   // Reclicking PETEK itself must not trigger discard/close/reopen.
   if(event.target.closest('#petekV477Nav'))return;
   if(!s.active)return;
   if(s.dirty&&!confirm('PETEK taslağında kaydedilmemiş değişiklikler var. Altı kategoriye dönüp bunları kaybetmek istiyor musun?')){
     event.preventDefault();event.stopPropagation();return;
   }
   s.active=false;$('main').style.display='flex';pane.style.display='none';
   $('petekV477Nav').classList.remove('selected');
 },true);
 window.addEventListener('resize',()=>{if(s.active)fit();});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
else init();
window.PetekV477={start,exit,reload};
})();
