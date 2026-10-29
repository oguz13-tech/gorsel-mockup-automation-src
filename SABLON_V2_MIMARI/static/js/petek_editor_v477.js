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
  dragCorner:-1,dragChanged:false,dirty:false,needsCurveApply:false,
  fitScale:1,zoom:1,preview:null,previewMode:false,entries:[],spaceHeld:false,panning:false,undoStack:[]
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
 if(limited()){notice('Onaylı PETEK maskesi kilitli. Eski üretilmiş görseller ve onaylar korunur.',true);return false;}
 return true;
}
function snapshot(){
 if(!s.img||!s.mask||s.status==='APPROVED')return;
 const frame={name:s.name,uid:s.uid,quad:JSON.parse(JSON.stringify(s.quad)),
   curves:JSON.parse(JSON.stringify(s.curves)),mask:maskUrl(s.mask),
   base:s.base?maskUrl(s.base):null,needsCurveApply:s.needsCurveApply};
 s.undoStack.push(frame);if(s.undoStack.length>6)s.undoStack.shift();
}
async function undoLast(){
 if(!editingAllowed()||!s.undoStack.length){notice('Geri alınabilecek yerel değişiklik yok.',true);return;}
 const frame=s.undoStack.pop();
 if(frame.name!==s.name||frame.uid!==s.uid){notice('Bu geri alma başka şablona ait.',true);return;}
 try{
  s.quad=frame.quad;s.curves=frame.curves;
  s.mask=await decodeCanvas(frame.mask);s.base=frame.base?await decodeCanvas(frame.base):null;
  s.needsCurveApply=frame.needsCurveApply;s.dirty=true;s.preview=null;s.previewMode=false;
  draw();notice('Son PETEK işlemi geri alındı (yalnız bellekte; onaylı maske korunuyor).');
 }catch(e){notice('Geri alma başarısız: '+e.message,true);}
}
function fit(){
 const canvas=$('petekV477Canvas'),area=$('petekV477Drawing');
 if(!canvas||!s.img)return;
 const box=area.getBoundingClientRect();
 s.fitScale=Math.min(1,Math.max(0.025,Math.min((box.width-32)/s.width,(box.height-46)/s.height)));
 s.scale=s.fitScale*s.zoom;
 canvas.width=Math.max(1,Math.round(s.width*s.scale));
 canvas.height=Math.max(1,Math.round(s.height*s.scale));
 $('petekV477ZoomLabel').textContent=Math.round(s.zoom*100)+'%';
 $('petekV477Zoom').value=String(Math.round(s.zoom*100));
 draw();
}
function setZoom(value){
 s.zoom=Math.max(.4,Math.min(5,Math.round(Number(value)*10)/10));
 fit();
}
function chooseRelative(delta){
 const list=s.entries,idx=list.findIndex(x=>x.uid===s.uid&&x.name===s.name);
 const target=list[idx+delta];if(!target)return;
 if(s.dirty&&!confirm('Kaydedilmemiş PETEK taslağını bırakıp sonraki şablona geçilsin mi?'))return;
 select(target.name,target.uid);
}
function listVisual(){
 const panel=$('petekV477List');panel.replaceChildren();
 const word=$('petekV477Search').value.trim().toLocaleLowerCase('tr');
 for(const item of s.entries){
  if(word&&!item.name.toLocaleLowerCase('tr').includes(word)&&!item.uid.toLocaleLowerCase('tr').includes(word))continue;
  const b=document.createElement('button');b.type='button';b.className='petek-v477-list-item';
  b.setAttribute('role','option');b.setAttribute('aria-selected',String(s.uid===item.uid&&s.name===item.name));
  b.textContent=item.name+' — '+item.status;
  b.title=item.name+' · '+item.uid+' · '+item.status;
  if(s.name===item.name&&s.uid===item.uid)b.classList.add('selected');
  b.addEventListener('click',()=>{
   if(s.name===item.name&&s.uid===item.uid)return;
   if(s.dirty&&!confirm('Kaydedilmemiş değişiklikleri bırakarak farklı PETEK şablonu açılsın mı?'))return;
   select(item.name,item.uid);
  });
  panel.append(b);
 }
}
function draw(){
 const canvas=$('petekV477Canvas');if(!canvas||!s.img)return;
 let ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height,k=s.scale;
 ctx.clearRect(0,0,w,h);ctx.drawImage(s.previewMode&&s.preview?s.preview:s.img,0,0,w,h);
 if(s.previewMode&&s.preview)return;
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
 if(first)snapshot();
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
function resetCorners(){
 if(!editingAllowed()||!s.img)return;
 if(!confirm('PETEK TASLAĞINDAKİ 4 köşe, maske ve kavisler temizlenecek. Önceki kayıtlı/onaylı maskeler korunur. Baştan seçilsin mi?'))return;
 snapshot();s.quad=[];s.curves={top:[],bottom:[]};s.base=null;s.mask=blank();
 s.previewMode=false;s.preview=null;s.dirty=true;s.needsCurveApply=false;
 s.mode='corners';$('petekV477Mode').textContent='Mod: '+names[s.mode];
 draw();notice('4 köşeyi sol üstten başlayıp yeniden işaretle. Ctrl+Z ile geri alabilirsin.');
}
function setMode(mode){
 if(!editingAllowed())return;
 if(!s.img){notice('Önce PETEK şablonu seç.',true);return;}
 // Switching to corner mode must NEVER discard an auto-detected quad.
 // Drag a red handle; use explicit Reset only when starting from scratch.
 s.mode=mode;
 $('petekV477Mode').textContent='Mod: '+names[mode];
 notice(mode==='corners'?(s.quad.length===4?'Dört köşe hazır. Kırmızı noktayı fareyle sürükle; zoom + Ctrl+Z kullanılabilir.':'Köşeleri sol üst, sağ üst, sağ alt, sol alt sırasıyla işaretle.'):
       mode==='wood'?'Yeşil boyanacak ön ahşabı boya. Dikey yarıklara ve zemine taşırma.':
       mode==='protect'?'Siyah koruma fırçası: delikler, gölgeler, üst/alt kavis ve yan yüz.':
       'Kavis uçları yan kenarlara ulaşmalı. Noktaları soldan sağa işaretle.');
 draw();
}
async function select(name,uid){
 try{
  const data=await api(detailUrl(name,uid));
  s.name=name;s.uid=data.uid;s.sha=data.source_sha;s.status=data.status;
  s.preview=null;s.previewMode=false;s.zoom=1;s.undoStack=[];
  s.width=data.width;s.height=data.height;s.quad=data.quad||[];
  s.curves=data.curve_points||{top:[],bottom:[]};s.needsCurveApply=false;
  s.base=null;s.dirty=false;
  s.img=await imageOf(photoUrl(name));
  s.mask=data.mask?await decodeCanvas(data.mask):blank();
  s.base=data.base_mask?await decodeCanvas(data.base_mask):null;
  $('petekV477Aspect').value=String(data.physical_aspect);
  $('petekV477Name').textContent=name+' · '+data.status+' · '+s.uid;
  $('petekV477AutoCorners').disabled=data.status==='APPROVED';
  $('petekV477Approve').disabled=data.status==='APPROVED';
  $('petekV477Save').disabled=data.status==='APPROVED';
  $('petekV477Revision').disabled=data.status!=='APPROVED';
  $('petekV477Confirm').checked=true;
  $('petekV477Reviewer').value='Can';
  listVisual();
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
  s.entries=data.items;
  selectEl.replaceChildren();
  for(const item of data.items){
    const option=document.createElement('option');
    option.value=JSON.stringify([item.name,item.uid]);
    option.textContent=item.name+' · '+item.uid+' — '+item.status;
    selectEl.append(option);
  }
  const scanned=Number(data.scanned_photos||0);
  const verified=Number(data.matched_approved_records||0);
  const historic=Number(data.registry_approved_total||0);
  const unmatched=Number(data.unmatched_approved_records||0);
  $('petekV477Count').textContent=data.items.length+' kayıt · '+scanned+' fotoğraf · '+
     verified+' eşleşen onaylı maske · '+historic+' eski onay kaydı'+
     (unmatched?' ('+unmatched+' fotoğrafla SHA eşleşmesi yok)':'');
  listVisual();
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
async function previewArtwork(){
 if(!s.img||s.quad.length!==4||!s.mask){notice('Önce dört köşe ve baskı maskesi gerekli.',true);return;}
 if(s.needsCurveApply){notice('Önce kavis maskesini güncelle.',true);return;}
 const file=$('petekV477Artwork').files[0];
 if(!file){notice('Önizleme için PNG, JPG veya WEBP tasarım dosyası seç.',true);return;}
 if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>8_000_000){
   notice('8 MB altında PNG/JPG/WEBP tasarım seç.',true);return;
 }
 const before={name:s.name,uid:s.uid,sha:s.sha};
 const btn=$('petekV477Preview');btn.disabled=true;
 try{
  const object=URL.createObjectURL(file);
  let design;
  try{design=await imageOf(object);}finally{URL.revokeObjectURL(object);}
  if(design.naturalWidth<100||design.naturalHeight<100)throw Error('Baskı tasarımı çok küçük.');
  const largest=1600,ratio=Math.min(1,largest/Math.max(design.naturalWidth,design.naturalHeight));
  const c=document.createElement('canvas');c.width=Math.round(design.naturalWidth*ratio);c.height=Math.round(design.naturalHeight*ratio);
  c.getContext('2d').drawImage(design,0,0,c.width,c.height);
  const data=await api('/api/petek/preview-artwork',{
    ...content(),artwork_png:c.toDataURL('image/png')});
  if(s.name!==before.name||s.uid!==before.uid||s.sha!==before.sha){
   notice('Şablon değişti; farklı fotoğrafın önizlemesi gösterilmedi.',true);return;
  }
  s.preview=await imageOf(data.preview);s.previewMode=true;draw();
  notice('GERÇEK BASKI ÖNİZLEMESİ — aynı PETEK V3 üretim motoruyla, fotoğrafa KAYDEDİLMEDİ. Görüntüyü yakınlaştırabilirsin.');
 }catch(e){notice('Baskı önizlemesi oluşturulamadı: '+e.message,true);}
 finally{btn.disabled=false;}
}
function backToOriginal(){s.previewMode=false;draw();notice('Orijinal fotoğraf ve maske görünümü.');}
async function resetUncommitted(){
 if(!s.img)return;
 if(!confirm('Yalnız kaydedilmemiş PETEK düzenlemeleri atılacak; kaydedilmiş onaylı maskeler değişmez. Devam?'))return;
 await select(s.name,s.uid);
}
async function autoCorners(){
 if(!editingAllowed()||!s.img)return;
 if((s.dirty||s.quad.length===4||s.curves.top.length||s.curves.bottom.length)&&
    !confirm('Bu PETEK TASLAĞINDAKİ kaydedilmemiş köşeler, maske ve kavisler sıfırlanarak magenta dört köşe önerisi yüklenecek. Onaylı kayıtlar değişmez. Devam?'))return;
 const expectedName=s.name,expectedSha=s.sha,expectedUid=s.uid;
 const button=$('petekV477AutoCorners');button.disabled=true;
 try{
  const data=await api('/api/petek/auto-corners',{
    name:expectedName,uid:expectedUid,source_sha:expectedSha});
  if(s.name!==expectedName||s.sha!==expectedSha||s.uid!==expectedUid||s.status==='APPROVED'){
    notice('Başka şablon açıldı; eski otomatik köşe sonucu uygulanmadı.',true);return;
  }
  snapshot();s.quad=data.quad;s.previewMode=false;s.preview=null;s.mask=blank();s.base=null;s.curves={top:[],bottom:[]};
  s.needsCurveApply=false;s.dirty=true;s.mode='corners';
  $('petekV477Mode').textContent='Mod: '+names[s.mode];
  draw();
  notice('MAGENTA 4 KÖŞE TASLAĞI ('+data.method+', kapsam '+Math.round(100*data.coverage)+
         '%) kırmızı olarak gösterildi. Köşeleri tek tek kontrol et; ardından Otomatik Maske Taslağı. Kaydedilmedi.');
 }catch(e){notice('MAGENTA KÖŞE ÖNERİSİ YOK: '+e.message+' · 4 köşeyi elle seç.',true);}
 finally{button.disabled=false;}
}
async function autoMask(){
 if(!editingAllowed())return;
 if(s.quad.length!==4){notice('Önce dört köşe tamamlanmalı.',true);return;}
 if(!confirm('Yalnız açık TASLAK maske yeniden oluşturulacak. Mevcut taslak boyama sıfırlansın mı?'))return;
 try{
  const data=await api('/api/petek/auto-mask',{name:s.name,source_sha:s.sha,quad:s.quad});
  snapshot();s.mask=await decodeCanvas(data.mask);s.previewMode=false;s.preview=null;s.base=null;s.curves={top:[],bottom:[]};
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
  snapshot();s.mask=await decodeCanvas(data.mask);s.needsCurveApply=false;s.dirty=true;draw();
  notice('Kavis maskesi görüntülendi; delik ve yer gölgelerini kontrol et.');
 }catch(e){notice(e.message,true);}
}
function undoCurve(){
 if(!editingAllowed())return;
 const arr=s.curves[s.mode];if(!Array.isArray(arr)||!arr.length)return;
 snapshot();arr.pop();s.needsCurveApply=true;s.dirty=true;draw();
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
 if(!s.img)return;
 if(e.button===1||e.button===2||s.spaceHeld){
   e.preventDefault();s.panning=true;s.panStart=[e.clientX,e.clientY];
   s.scrollStart=[$('petekV477Drawing').scrollLeft,$('petekV477Drawing').scrollTop];return;
 }
 if(s.previewMode){notice('Önizlemeyi kapatarak maskeyi düzenle.',true);return;}
 if(!editingAllowed())return;
 e.preventDefault();const p=point(e);
 if(s.mode==='corners'){
   if(s.quad.length===4){
     const idx=window.PetekQuadDragV481.closest(s.quad,p,s.scale);
     if(idx<0){notice('Kırmızı köşe noktasını tutup sürükle veya yakınlaştır. Dört köşe korunuyor.',true);return;}
     s.dragCorner=idx;s.dragChanged=false;
     try{$('petekV477Canvas').setPointerCapture(e.pointerId);}catch(_ignored){}
     notice('Köşe '+(idx+1)+' seçildi; hassas düzeltme için sürükle.');
     return;
   }
   snapshot();s.quad.push(p);s.dirty=true;draw();
   notice('Köşeler: '+s.quad.length+'/4'+(s.quad.length===4?' · Noktaları şimdi sürükleyerek düzeltebilirsin.':''));
 }else if(s.mode==='wood'||s.mode==='protect'){
   if(s.quad.length!==4){notice('Önce dört köşe gerekir.',true);return;}
   s.painting=true;paintAt(e,true);
 }else if(s.mode==='top'||s.mode==='bottom'){
   if(s.quad.length!==4){notice('Önce dört köşe gerekir.',true);return;}
   snapshot();s.curves[s.mode].push(p);s.needsCurveApply=true;s.dirty=true;
   draw();notice('Kavis noktası eklendi. Bitince «Kavisleri Uygula» seç.');
 }
}
function pointerMove(e){
 if(s.panning){e.preventDefault();const area=$('petekV477Drawing');
   area.scrollLeft=s.scrollStart[0]-(e.clientX-s.panStart[0]);
   area.scrollTop=s.scrollStart[1]-(e.clientY-s.panStart[1]);return;
 }
 if(s.dragCorner>=0){
   e.preventDefault();
   if(s.status==='APPROVED')return;
   const candidate=window.PetekQuadDragV481.moved(s.quad,s.dragCorner,point(e),s.width,s.height);
   if(!candidate){notice('Köşe taşınmadı: dört köşe dışbükey ve fotoğraf sınırları içinde kalmalı.',true);return;}
   const idx=s.dragCorner;
   if(Math.hypot(candidate[idx][0]-s.quad[idx][0],candidate[idx][1]-s.quad[idx][1])<.2)return;
   if(!s.dragChanged){
     snapshot();
     // The existing draft mask belongs to the OLD quad. Never reuse a mask
     // after a geometry edit; request a fresh preview before approval.
     s.mask=blank();s.base=null;s.curves={top:[],bottom:[]};s.needsCurveApply=false;
     s.preview=null;s.previewMode=false;s.dragChanged=true;
   }
   s.quad=candidate;s.dirty=true;draw();
   notice('Köşe '+(idx+1)+' elle düzeltildi. Maske/kavis taslağı temizlendi; Otomatik Maske Taslağı ile yenile. Ctrl+Z geri alır.');
   return;
 }
 if(!s.painting)return;e.preventDefault();paintAt(e,false);
}
function pointerUp(e){
 if(s.dragCorner>=0&&e){try{$('petekV477Canvas').releasePointerCapture(e.pointerId);}catch(_ignored){}}
 s.dragCorner=-1;s.dragChanged=false;s.panning=false;s.painting=false;s.lastPoint=null;
}
function restoreListHost(){
 const list=$('petekV477ListPane'),workspace=$('petekV477Workspace');
 if(list&&workspace&&list.parentElement!==workspace)workspace.prepend(list);
 list?.classList.remove('in-sidebar');
}
function start(){
 s.active=true;
 const normal=$('main'),pane=$('petekV477Editor');
 normal.style.display='none';pane.style.display='flex';
 $('petekV477Nav').classList.add('selected');
 const list=$('petekV477ListPane');
 $('petekV477Nav').after(list);
 list.classList.add('in-sidebar');
 reload();
}
function exit(){
 if(!s.active)return;
 if(s.dirty&&!confirm('Kaydedilmemiş PETEK taslağın var. Kaydetmeden çıkılsın mı?'))return;
 s.active=false;
 restoreListHost();
 $('main').style.display='flex';$('petekV477Editor').style.display='none';
 $('petekV477Nav').classList.remove('selected');
}
function init(){
 const pane=$('petekV477Editor');if(!pane)return;
 $('petekV477Nav').addEventListener('click',start);
 $('petekV477Close').addEventListener('click',exit);
 $('petekV477Reload').addEventListener('click',()=>{
   if(s.dirty&&!confirm('Kaydedilmemiş PETEK değişiklikleri atılsın ve liste yenilensin mi?'))return;
   reload();
 });
 $('petekV477Search').addEventListener('input',listVisual);
 $('petekV477Prev').addEventListener('click',()=>chooseRelative(-1));
 $('petekV477Next').addEventListener('click',()=>chooseRelative(1));
 $('petekV477ZoomIn').addEventListener('click',()=>setZoom(s.zoom+.2));
 $('petekV477ZoomOut').addEventListener('click',()=>setZoom(s.zoom-.2));
 $('petekV477ZoomFit').addEventListener('click',()=>setZoom(1));
 $('petekV477Zoom').addEventListener('input',e=>setZoom(Number(e.target.value)/100));
 $('petekV477Drawing').addEventListener('wheel',e=>{
   if(!s.active||!s.img)return;e.preventDefault();setZoom(s.zoom+(e.deltaY<0?.2:-.2));
 },{passive:false});
 $('petekV477Canvas').addEventListener('contextmenu',e=>e.preventDefault());
 document.addEventListener('keydown',e=>{if(e.code==='Space'&&!['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))s.spaceHeld=true;});
 document.addEventListener('keyup',e=>{if(e.code==='Space')s.spaceHeld=false;});
 $('petekV477Preview').addEventListener('click',previewArtwork);
 $('petekV477Original').addEventListener('click',backToOriginal);
 $('petekV477Reset').addEventListener('click',resetUncommitted);
 $('petekV477ResetCorners').addEventListener('click',resetCorners);
 $('petekV477Undo').addEventListener('click',undoLast);
 document.addEventListener('keydown',e=>{
   if(!s.active||!e.ctrlKey||e.key.toLowerCase()!=='z')return;
   if(['INPUT','TEXTAREA'].includes(e.target.tagName))return;
   e.preventDefault();undoLast();
 });
 $('petekV477Select').addEventListener('change',e=>{
    const [name,uid]=JSON.parse(e.target.value);
    select(name,uid);
 });
 for(const b of document.querySelectorAll('[data-petek-mode]'))
   b.addEventListener('click',()=>setMode(b.dataset.petekMode));
 $('petekV477AutoCorners').addEventListener('click',autoCorners);
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
 $('petekV477Canvas').addEventListener('lostpointercapture',pointerUp);
 document.querySelector('#categories').addEventListener('click',event=>{
   // Reclicking PETEK itself must not trigger discard/close/reopen.
   if(event.target.closest('#petekV477Nav')||event.target.closest('#petekV477ListPane'))return;
   if(!s.active)return;
   if(s.dirty&&!confirm('PETEK taslağında kaydedilmemiş değişiklikler var. Altı kategoriye dönüp bunları kaybetmek istiyor musun?')){
     event.preventDefault();event.stopPropagation();return;
   }
   s.active=false;restoreListHost();$('main').style.display='flex';pane.style.display='none';
   $('petekV477Nav').classList.remove('selected');
 },true);
 window.addEventListener('resize',()=>{if(s.active)fit();});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
else init();
window.PetekV477={start,exit,reload};
})();
