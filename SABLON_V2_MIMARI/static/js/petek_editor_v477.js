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
  fitScale:1,zoom:1,preview:null,previewMode:false,entries:[],spaceHeld:false,panning:false,undoStack:[],listHost:null,
  bulkMode:false,bulkSelected:new Set(),bulkActive:false,bulkStop:false,bulkRows:[],bulkReport:[],compactList:true
};
const names={corners:'Dört köşe',wood:'Baskı ahşabını boya',erasewood:'Ahşap boyasını sil',protect:'Delik / yan yüzü koru',top:'Üst kavis',bottom:'Alt kavis'};
const errorSolutions=[
  [/maske taslağı|baskı alanı|%0|0[.,]0%/i,'Dört köşe kaydedildiyse önce “2. Otomatik Maske Taslağı” oluştur, ardından gerçek tasarımla önizle. Kaydedilmiş maske yokken baskı alanını %0 diye yorumlama.','petekV477Auto'],
  [/onaylı.*kilit|kilitli/i,'“Onaylı Maskeyi Düzenle / Yeni Revizyon” yolunu kullan. Orijinal onaylı kayıt korunur; yeni revizyonu onayladıktan sonra etkinleştir.','petekV477Revision'],
  [/kaynak|sha|uid|kimlik/i,'Kaynak fotoğraf veya maskenin SHA değeri değişmiş olabilir. Listeyi yenile, güncel taslağı incele; eski kaydı zorla onaylama.',null],
  [/4k|esrgan|vulkan/i,'Seri Üretim > “4K Kurulumunu Kontrol Et” düğmesini kullan. 4K kapalı normal üretim sürdürülebilir.',null]
];
let lastErrorKey='',lastErrorTime=0;
function notice(message,bad=false){
 const e=$('petekV477Status'); if(!e)return;
 const raw=String(message);let recommendation=null;
 if(bad){for(const [pattern,advice,id] of errorSolutions){if(pattern.test(raw)){recommendation={advice,id};break;}}}
 e.textContent=raw+(recommendation?'\nNEDEN / ÇÖZÜM: '+recommendation.advice:'');
 e.style.color=bad?'#fca5a5':'#c6f6d5';
 // Only blocking, non-batch errors trigger the popup once. Per-file bulk
 // failures are aggregated in the report and must not stop the queue.
 if(!bad||s.bulkActive||!recommendation)return;
 const popup=$('petekV4101ErrorDialog');if(!popup||typeof popup.showModal!=='function')return;
 const key=raw;const now=Date.now();if(key===lastErrorKey&&now-lastErrorTime<1500)return;
 lastErrorKey=key;lastErrorTime=now;
 $('petekV4101ErrorText').textContent=raw;
 $('petekV4101ErrorAdvice').textContent=recommendation.advice;
 const button=$('petekV4101ErrorAction');button.hidden=!recommendation.id;
 button.onclick=()=>{popup.close();const item=$(recommendation.id);
   if(item){item.scrollIntoView({block:'center'});item.focus();}};
 if(!popup.open)popup.showModal();
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
 const list=visiblePetekItems(),idx=list.findIndex(x=>x.uid===s.uid&&x.name===s.name);
 // A just-saved/approved record can disappear under the active status filter.
 // Never interpret a filtered-out selection as 'jump to the first template'.
 if(idx<0){notice('Seçili PETEK bu filtrede gizli. Aynı görselde kalındı; gezinmek için ilgili durum filtresini aç.',true);return;}
 const target=list[idx+delta];if(!target)return;
 if(s.dirty&&!confirm('Kaydedilmemiş PETEK taslağını bırakıp sonraki şablona geçilsin mi?'))return;
 select(target.name,target.uid);
}
function bulkKey(item){return JSON.stringify([item.name,item.uid,item.source_sha]);}
function visiblePetekItems(){
 const q=$('petekV477Search').value.trim().toLocaleLowerCase('tr');
 return s.entries.filter(x=>(!q||x.name.toLocaleLowerCase('tr').includes(q)||x.uid.toLocaleLowerCase('tr').includes(q)) && (!window.V499StatusFilters || window.V499StatusFilters.allowed(petekState(x))));
}
function refreshBulkCount(){
 $('petekV484BulkCount').textContent=s.bulkSelected.size+' PETEK şablonu seçildi; toplu ONAY için tikleme gerekmez';
 const selectedCount=s.bulkSelected.size;
 $('petekV484BulkDetect').disabled=!selectedCount||s.bulkActive;
 $('petekV484BulkSave').disabled=!selectedCount||s.bulkActive;
 $('petekV498BulkApprove').disabled=s.bulkActive;
 $('petekV484BulkStop').disabled=!s.bulkActive;
 $('petekV484BulkMode').disabled=s.bulkActive;
}
function showBulkReport(){
 const full=s.bulkReport.join('\n');
 if(!full){notice('Önce PETEK toplu işlem çalıştır.',true);return;}
 if(navigator.clipboard?.writeText){
    navigator.clipboard.writeText(full).then(()=>notice('PETEK toplu işlem raporu kopyalandı.'),
      ()=>prompt('PETEK raporunu kopyala:',full));
 }else prompt('PETEK raporunu kopyala:',full);
}
function selectBulk(filter){
 if(s.bulkActive)return;
 const list=visiblePetekItems();
 if(filter==='clear')s.bulkSelected.clear();
 else for(const item of list){
   if(filter==='visible'||(filter==='new'&&item.status==='NEW')||
      (filter==='draft'&&item.status==='DRAFT')||
      (filter==='approved'&&item.status==='APPROVED'))s.bulkSelected.add(bulkKey(item));
 }
 listVisual();
}
async function runBulkPetek(save){
 if(s.bulkActive)return;
 const selected=s.entries.filter(item=>s.bulkSelected.has(bulkKey(item))&&
                       (save?item.status==='NEW':item.status!=='APPROVED'));
 const excluded=s.bulkSelected.size-selected.length;
 if(!selected.length){notice('İşlenecek PETEK yok. Taslak tarama: NEW/DRAFT; taslak kaydetme: yalnız NEW.',true);return;}
 if(s.dirty){notice('Açık PETEK üzerinde kaydedilmemiş değişiklikler var; önce kaydet veya geri al.',true);return;}
 if(save&&!confirm(selected.length+' YENİ PETEK için yalnız KÖŞE+MASKE TASLAĞI kaydedilecek. İnsan onayı VERİLMEYECEK. Eski onaylı maskeler korunacak. Devam?'))return;
 s.bulkActive=true;s.bulkStop=false;s.bulkRows=[];s.bulkReport=[
   'PETEK TOPLU '+(save?'YENİ TASLAK KAYDETME':'OTOMATİK 4 KÖŞE TESPİT')+
   ' | '+new Date().toLocaleString('tr-TR'),
   'Seçilen: '+selected.length+', işlem dışı onaylı/mevcut: '+excluded];
 const status=$('petekV484BulkStatus');
 let done=0,ok=0,fail=0;
 refreshBulkCount();
 try{
  // Eight per request: UI stays responsive and operator can STOP after a
  // complete chunk. Large 127-photo batches never fill browser with images.
  for(let i=0;i<selected.length;i+=8){
   if(s.bulkStop)break;
   const chunk=selected.slice(i,i+8).map(item=>({
      name:item.name,uid:item.uid,source_sha:item.source_sha}));
   status.textContent='PETEK Toplu '+(save?'taslak kaydı':'4 köşe tespiti')+
        '\nİşlenen: '+done+'/'+selected.length+' | Başarılı: '+ok+' | Kontrol: '+fail+
        '\nSekizli grup: '+(Math.floor(i/8)+1);
   const path=save?'/api/petek/bulk-save-new-drafts':'/api/petek/bulk-propose';
   try{
    const payload=await api(path,{items:chunk,...(save?{confirm:'CREATE_NEW_DRAFTS_ONLY_NO_APPROVAL'}:{})});
    for(const result of (save?payload.drafts:payload.proposals)||[]){
      ok++;s.bulkRows.push({...result,ok:true});
      s.bulkReport.push('OK | '+result.name+' | '+result.uid+
        ' | 4 köşe '+(result.method||'AUTO')+
        ' | kapsama '+result.coverage+' | '+(save?'DRAFT':'ÖNERİ, KAYDEDİLMEDİ'));
    }
    for(const problem of payload.failed||[]){
      fail++;s.bulkRows.push({...problem,ok:false});
      s.bulkReport.push('KONTROL | '+problem.name+' | '+problem.uid+' | '+problem.error);
    }
   }catch(error){
    for(const item of chunk){
      fail++;s.bulkRows.push({name:item.name,uid:item.uid,error:error.message,ok:false});
      s.bulkReport.push('KONTROL | '+item.name+' | '+item.uid+' | '+error.message);
    }
   }
   done+=chunk.length;
  }
  const final='PETEK Toplu işlem '+(s.bulkStop?'OPERATÖR DURDURDU':'BİTTİ')+
      ' · '+done+'/'+selected.length+' incelendi · '+ok+' başarılı · '+fail+' kontrol gerekiyor'+
      (excluded?' · '+excluded+' korunan/kapsam dışı':'')+
      '\n'+(save?'Oluşturulanlar DRAFT; insan onayı verilmedi.':'Yalnız öneri; hiçbir maske veya köşe kaydedilmedi.')+
      '\nİlk sorunlar: '+s.bulkRows.filter(x=>!x.ok).slice(0,6).map(x=>x.name+' — '+x.error).join(' | ');
  status.textContent=final;
  s.bulkReport.push(final);
  if(save){
    s.bulkSelected.clear();
    await reload(s.uid); // Source SHA and onay counts rechecked after writes.
  }else listVisual();
  notice(final,fail>0);
 }finally{
  s.bulkActive=false;
  refreshBulkCount();
 }
}
/* V4.10.1: The retired eight-at-a-time human review UI was removed.
 * One explicit global confirmation applies to every eligible visible DRAFT;
 * each individual mask/source is still independently validated by the server. */
/* V4.9.9 single-confirm bulk approval. Backend rechecks every source, UID and mask.
 * Any internal eight-record chunks are invisible to the operator; no checkbox
 * or repeated prompt. Failed items stay DRAFT, approved originals stay locked. */
async function beginBulkPetekApproval(){
 if(s.bulkActive)return;
 if(s.dirty){notice('Kaydedilmemiş PETEK düzenlemesi var. Önce kaydet veya geri al.',true);return;}
 const drafts=visiblePetekItems().filter(x=>x.status==='DRAFT'&&x.mask_verified);
 const rejected=visiblePetekItems().filter(x=>x.status==='DRAFT'&&!x.mask_verified).length;
 if(!drafts.length){notice('Onaylanabilecek doğrulanmış PETEK TASLAĞI bulunamadı. Önce Otomatik Maske Taslağı oluştur ve kaydet.',true);return;}
 const reviewer=($('petekV477Reviewer')?.value||'Can').trim();
 if(!reviewer){notice('İnceleyen kişinin adını gir.',true);return;}
 if(!confirm(drafts.length+' PETEK TASLAĞININ TÜMÜ SUNUCUDA AYRI AYRI DENETLENECEK.\n\n'+
   'Kaynak fotoğraf, maske SHA, dört köşe ve baskı alanı doğru olanlar ONAYLANACAK; hatalılar TASLAK kalacak.\n'+
   'Onaylı eski maskeler ve orijinal dosyalar değişmeyecek.\n\n'+
   'Her dosyaya tik atmanız gerekmiyor. Toplu onayı BAŞLATMAK istiyor musunuz?'))return;
 s.bulkActive=true;s.bulkStop=false;s.bulkRows=[];
 s.bulkReport=['PETEK TEK ONAYLI TOPLU TASLAK KİLİTLEME | '+new Date().toLocaleString('tr-TR'),
   'Başlangıç taslak sayısı: '+drafts.length+' | Maskesi doğrulanmamış: '+rejected];
 refreshBulkCount();
 let processed=0,ok=0,failed=0;
 try{
   for(let offset=0;offset<drafts.length;offset+=8){
     if(s.bulkStop)break;
     const chunk=drafts.slice(offset,offset+8).map(item=>({name:item.name,
       uid:item.uid,source_sha:item.source_sha}));
     $('petekV484BulkStatus').textContent='PETEK toplu onay işleniyor...\n'+
       processed+'/'+drafts.length+' kontrol edildi · '+ok+' onaylandı · '+failed+' hata';
     try{
       const result=await api('/api/petek/bulk-approve-confirmed',{items:chunk,reviewer,
         confirm:'I_APPROVE_ALL_VALID_PETEK_DRAFTS_IN_THIS_SELECTION'});
       for(const approved of result.approved||[]){ok++;s.bulkReport.push('ONAYLI | '+approved.name+' | '+approved.uid);}
       for(const problem of result.failed||[]){failed++;s.bulkReport.push('HATALI/TASLAK KALDI | '+problem.name+' | '+problem.error);}
     }catch(error){for(const item of chunk){failed++;s.bulkReport.push(
       'HATALI/TASLAK KALDI | '+item.name+' | '+error.message);}}
     processed+=chunk.length;
     $('petekV484BulkStatus').textContent='PETEK TOPLU ONAY\n'+processed+'/'+drafts.length+
       ' kontrol edildi · '+ok+' onaylandı · '+failed+' sorun';
     await new Promise(resolve=>setTimeout(resolve,0));
   }
   if(s.bulkStop)s.bulkReport.push('İPTAL EDİLDİ | kalan '+(drafts.length-processed)+' taslak korunur');
   $('petekV484BulkStatus').textContent='SONUÇ: '+ok+' onaylandı; '+failed+' hata; '+
       (drafts.length-processed)+' işlem yapılmadı. Detay için Raporu Kopyala.';
   notice(ok+' PETEK taslağı onaylandı; '+failed+' kontrol gerekli. Hatalı kayıtlar taslak kaldı.',failed>0);
 }finally{s.bulkActive=false;s.bulkStop=false;await reload(s.uid);refreshBulkCount();}
}
function petekState(item){
 if(item.status==='REVIEW_REQUIRED'||item.backup_status==='UNSAFE'||item.backup_status==='DIFFERENT'||(item.approved&&!item.mask_verified))return 'ERROR';
 if(item.status==='APPROVED'&&item.approved&&item.mask_verified)return 'APPROVED';
 if(item.status==='DRAFT')return 'DRAFT';
 return 'NEW';
}
function petekHealth(item){
 // Never claim approval from badge colour alone: both SHA-bound mask and
 // registry human approval are necessary.
 if(item.status==='REVIEW_REQUIRED'||item.backup_status==='UNSAFE'||
    item.backup_status==='DIFFERENT'||(item.approved&&!item.mask_verified))return 'error';
 if(item.status==='APPROVED'&&item.approved&&item.mask_verified)return 'approved';
 return 'pending';
}
function listVisual(){
 const panel=$('petekV477List')||s.listHost?.querySelector('#petekV477List');
 if(!panel){notice('PETEK şablon listesi bulunamadı: HTML ve JS sürümlerini eşitle.',true);return;}
 panel.replaceChildren();
 panel.classList.toggle('petek-v498-compact',s.compactList);
 const summaries=s.entries.reduce((acc,item)=>{
   acc[item.status]=(acc[item.status]||0)+1;
   if(item.backup_status!=='MATCH')acc.backup++;
   if(item.status==='REVIEW_REQUIRED')acc.problem++;
   return acc;
 },{NEW:0,DRAFT:0,APPROVED:0,REVIEW_REQUIRED:0,backup:0,problem:0});
 $('petekV484Summary').textContent='✅ '+summaries.APPROVED+
   ' onaylı · 📝 '+summaries.DRAFT+' taslak · '+summaries.NEW+
   ' yeni · ⚠️ '+summaries.REVIEW_REQUIRED+' kayıt sorunu · 🗄️ '+summaries.backup+' ham kontrol';
 for(const item of visiblePetekItems()){
   const wrap=document.createElement('div');
   wrap.className='petek-v484-item-wrap petek-status-'+petekHealth(item)+' v499-status-'+petekState(item).toLowerCase();
   wrap.setAttribute('aria-label',item.name+' — '+(petekHealth(item)==='approved'?'Onaylı':petekHealth(item)==='error'?'Ciddi sorun, kontrol gerekli':'İnceleme bekliyor'));
   const line=document.createElement('div');
   line.className='petek-v484-line';
   const key=bulkKey(item);
   if(s.bulkMode){
     const input=document.createElement('input');input.type='checkbox';input.className='petek-v484-check';
     input.checked=s.bulkSelected.has(key);
     input.setAttribute('aria-label','Toplu PETEK seç: '+item.name);
     input.addEventListener('change',()=>{if(s.bulkActive){input.checked=!input.checked;return;}
       if(input.checked)s.bulkSelected.add(key);else s.bulkSelected.delete(key);
       refreshBulkCount();
     });
     line.append(input);
   }
   const thumbnail=document.createElement('img');
   thumbnail.className='petek-v484-thumb';thumbnail.loading='lazy';
   thumbnail.decoding='async';thumbnail.alt=item.name+' küçük önizleme';
   thumbnail.width=52;thumbnail.height=52;
   thumbnail.src='/api/petek/thumbnail/'+encodeURIComponent(item.name);
   thumbnail.addEventListener('error',()=>{thumbnail.alt='Önizleme açılamadı';thumbnail.classList.add('petek-v484-thumb-error');});
   line.append(thumbnail);
   const button=document.createElement('button');button.type='button';button.className='petek-v477-list-item petek-v484-name';
   button.setAttribute('role','option');
   button.setAttribute('aria-selected',String(s.uid===item.uid&&s.name===item.name));
   // Keep the real filename and immutable UID unchanged; only shorten
   // extremely long generated names visually. Full name remains in tooltip.
   const shortName=item.name.length>43?
      item.name.slice(0,25)+'…'+item.name.slice(-13):item.name;
   const readableState=item.status==='APPROVED'?'ONAYLI':
      item.status==='DRAFT'?'TASLAK':item.status==='NEW'?'YENİ':'KONTROL GEREK';
   button.textContent=shortName+' — '+readableState;
   button.title=item.name+' · '+item.uid+' · '+item.status;
   if(s.name===item.name&&s.uid===item.uid)button.classList.add('selected');
   button.addEventListener('click',()=>{
     if(s.bulkActive){notice('PETEK toplu tarama sürüyor; bitince şablon değiştir.',true);return;}
     if(s.name===item.name&&s.uid===item.uid)return;
     if(s.dirty&&!confirm('Kaydedilmemiş değişiklikleri bırakarak farklı PETEK şablonu açılsın mı?'))return;
     select(item.name,item.uid);
   });
   line.append(button);
   const pictos=document.createElement('span');pictos.className='petek-v484-pictos';
   pictos.textContent='📁'+(item.working_ok?'✅':'⚠️')+
      ' 🗄️'+(item.backup_status==='MATCH'?'✅':'⚠️')+
      ' 🎭'+(item.mask_verified?'✅':'📝')+
      ' ✅'+(item.approved?'✅':'–');
   pictos.title='Çalışma: '+(item.working_ok?'OK':'KONTROL')+
      ' / Ham: '+String(item.backup_status||'BİLİNMİYOR')+
      ' / Maske: '+(item.mask_verified?'doğrulandı':'yeni/taslak veya kontrol')+
      ' / Onay: '+(item.approved?'insan onaylı':'yok');
   // Each row has an immutable filename label and a separately sized checkbox.
   // Do not let global input{width:100%} consume the entire row.
   wrap.append(line,pictos);
   if(s.bulkSelected.has(key))wrap.classList.add('petek-v484-selected');
   if(petekHealth(item)==='error')wrap.classList.add('petek-v484-warning');
   panel.append(wrap);
 }
 refreshBulkCount();
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
       mode==='erasewood'?'Ahşap Boyasını Sil: Yeşil maske alanını siyaha geri döndürür; fotoğraf piksellerine dokunmaz. Ctrl+Z ile geri al.':
       mode==='protect'?'Siyah koruma fırçası: delikler, gölgeler, üst/alt kavis ve yan yüz.':
       'Kavis uçları yan kenarlara ulaşmalı. Noktaları soldan sağa işaretle.');
 draw();
}
async function select(name,uid){
 try{
  const data=await api(detailUrl(name,uid));
  s.name=name;s.uid=data.uid;s.sha=data.source_sha;s.status=data.status;
  // The visible list click and hidden native selection MUST have one UID.
  // Otherwise the next reload or arrow navigation silently jumps elsewhere.
  const nativeSelect=$('petekV477Select');
  if(nativeSelect){
    const matching=Array.from(nativeSelect.options).find(opt=>{
      try{const pair=JSON.parse(opt.value);return pair[0]===name&&pair[1]===data.uid;}
      catch(_ignored){return false;}
    });
    if(matching)nativeSelect.value=matching.value;
  }
  s.revisesUid=data.revises_uid||null;s.baseUid=data.base_uid||null;
  s.isCurrent=data.is_current!==false;
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
  $('petekV477Revision').disabled=data.status!=='APPROVED'||!s.isCurrent;
  $('petekV499Restore').disabled=!(data.status==='APPROVED'&&data.revises_uid&&s.isCurrent);
  $('petekV499Activate').disabled=!(data.status==='APPROVED'&&data.revises_uid&&!s.isCurrent);
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
async function previewArtwork(isFifteen=false){
 if(!s.img||s.quad.length!==4||!s.mask){
   const msg='Önizleme için önce dört köşe ve baskı maskesi gerekli.\nÇözüm: 4 köşe → 2. Otomatik Maske Taslağı → Gerçek Tasarımla Önizle.';
   notice(msg,true);alert(msg);return;
 }
 // After automatic quad proposal a blank black canvas exists, but no actual
 // printable mask has been generated. Avoid misleading "0.0% bad mask" error.
 const context=s.mask.getContext('2d',{willReadFrequently:true});
 const rgba=context.getImageData(0,0,s.mask.width,s.mask.height).data;
 let printable=false;
 for(let i=0;i<rgba.length;i+=4*48){if(rgba[i]>96){printable=true;break;}}
 if(!printable){
   const msg='DÖRT KÖŞE BULUNDU, ancak OTOMATİK MASKE TASLAĞI henüz oluşturulmadı.\n\n'
       +'Çözüm: Sağ panelde 2. Otomatik Maske Taslağı düğmesine bas. '
       +'Sonra yeşil baskı alanını, 15 yarığı ve üst-alt kavisi kontrol ederek önizlemeyi yeniden aç.';
   notice(msg,true);alert(msg);return;
 }

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
    ...content(),artwork_png:c.toDataURL('image/png'),
    fifteen_slot_ab:!!isFifteen,
    fifteen_slot_strength:isFifteen?$('petekV493Strength').value:'orta',
    pink_cleanup:isFifteen?!!$('petekV493Pink').checked:false});
  if(s.name!==before.name||s.uid!==before.uid||s.sha!==before.sha){
   notice('Şablon değişti; farklı fotoğrafın önizlemesi gösterilmedi.',true);return;
  }
  const previewBefore=await imageOf(data.preview);
  if(isFifteen){
    if(!data.after||data.slot_qa?.count!==15)throw Error('Tam 15 ızgara önizlemesi üretilemedi.');
    const previewAfter=await imageOf(data.after);
    s.previewBefore=previewBefore;s.previewAfter=previewAfter;
    s.preview=previewAfter;
    $('petekV493Before').disabled=false;$('petekV493After').disabled=false;
    const qa=data.slot_qa;
    const gaps=qa.spacings_rectified_900||[];
    const spacing=gaps.length?' • Kaynakta ölçülen 14 aralık: '+
      Math.min(...gaps).toFixed(1)+'–'+Math.max(...gaps).toFixed(1)+' px (perspektifi düzeltilmiş)':'';
    const source=qa.alignment==='SOURCE_PHOTO_15'?'orijinal fotoğraftan ölçüldü':
      qa.alignment==='EXISTING_MASK_15'?'onaylı maske geometrisinden ölçüldü':'kaynak geometrisi kontrol edildi';
    $('petekV493Result').textContent='15 / 15 gerçek yarık '+source+spacing+
      ' • Değişen piksel: '+qa.changed_pixels+
      ' • Dört kenar / ızgara temizliği: '+data.pink_qa.status+
      ' · Kalan yüksek doygunluklu pembe: '+(data.pink_qa.remaining_pixels||0)+
      '. ÖNCE / SONRA ile kontrol et; kaynak veya onaylı maske değişmedi.';
  }else{
    s.previewBefore=null;s.previewAfter=null;s.preview=previewBefore;
    $('petekV493Before').disabled=true;$('petekV493After').disabled=true;
  }
  s.previewMode=true;draw();
  const residual=Number(data.mask_qa?.protected_magenta_pixels||0);
  notice((isFifteen?'15 IZGARA A/B ÖNİZLEMESİ — ':'GERÇEK BASKI ÖNİZLEMESİ — ')+ 'PETEK V3 motoru. '+
     (residual?'Maskenin DIŞINDA '+residual+' pembe kaynak pikseli korunuyor: tasarım öncesi maskeyi incele. ':'Magenta kenarlarda pembe geçiş karışımı kapalı. ')+
     'Önizleme kaydedilmedi. 3:4 üretim tuvali ve seçili üretim efektleri son çıktıyı değiştirebilir.',
     residual>30||!!(data.pink_qa&&data.pink_qa.remaining_pixels>0));
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
// Update only the current draft's UI record. Save-draft keeps the same UID;
// a complete pool reload can change selection, scroll position and focus.
function applyDraftInPlace(name,uid,maskSha){
 const pane=$('petekV477List');const oldScroll=pane?pane.scrollTop:0;
 for(const item of s.entries){
   if(item.name===name&&item.uid===uid){
     item.status='DRAFT';item.approved=false;item.mask_verified=true;
     if(maskSha)item.mask_sha=maskSha;
   }
 }
 const options=$('petekV477Select');
 if(options){for(const opt of options.options){
   try{const pair=JSON.parse(opt.value);
     if(pair[0]===name&&pair[1]===uid)opt.textContent=name+' · '+uid+' — DRAFT';
   }catch(_ignored){}
 }}
 if(s.name===name&&s.uid===uid){
   s.status='DRAFT';s.dirty=false;
   // Deliberately do not change s.name, s.uid, image canvas, focus or zoom.
   $('petekV477Name').textContent=name+' · DRAFT · '+uid;
 }
 listVisual();if(pane)pane.scrollTop=oldScroll;
}
async function save(){
 if(!editingAllowed()||!s.img)return;
 if(s.quad.length!==4){notice('Dört köşe tamamlanmadan taslak kaydedilemez.',true);return;}
 if(s.needsCurveApply){notice('Kavis noktalarını/maskesini değiştirdin; önce Kavisleri Uygula.',true);return;}
 if(!confirm('Yalnız PETEK TASLAĞI kaydedilecek. Orijinal ve onaylı maskeler korunacak. Devam?'))return;
 const identity={name:s.name,uid:s.uid,sha:s.sha};
 try{
  const data=await api('/api/petek/save-draft',content());
  if(data.uid!==identity.uid||data.status!=='DRAFT')throw Error('PETEK_TASLAK_UID_STATUS_UYUSMUYOR_YENILE');
  applyDraftInPlace(identity.name,identity.uid,data.mask_sha);
  notice('PETEK taslağı kaydedildi. Aynı görselde kalındı; son insan onayı ayrıca verilebilir.');
 }catch(e){notice(e.message,true);}
}
// V4.10.2: The HTTP approval itself is authoritative. Never follow a
// successful approval by an eager /api/petek/templates scan of the entire
// 100+ photo pool and a full-resolution /detail + /photo reload.
function applyApprovedInPlace(name,uid,maskSha){
 const current=s.name===name&&s.uid===uid;
 for(const item of s.entries){
   if(item.name===name&&item.uid===uid){
     item.status='APPROVED';item.approved=true;item.mask_verified=true;
     if(maskSha)item.mask_sha=maskSha;
   }
 }
 const options=$('petekV477Select');
 if(options){for(const opt of options.options){
    try{const pair=JSON.parse(opt.value);
      if(pair[0]===name&&pair[1]===uid)opt.textContent=name+' · '+uid+' — APPROVED';
    }catch(_ignored){}
 }}
 if(current){
   s.status='APPROVED';s.dirty=false;s.isCurrent=true;
   $('petekV477Name').textContent=name+' · APPROVED · '+uid;
   $('petekV477AutoCorners').disabled=true;
   $('petekV477Approve').disabled=true;
   $('petekV477Save').disabled=true;
   $('petekV477Revision').disabled=false;
   $('petekV499Restore').disabled=!s.revisesUid;
   $('petekV499Activate').disabled=true;
 }
 // DOM-only refresh. The explicit "Listeyi Yenile" control still performs a
 // full authoritative SHA/mask verification when the user requests it.
 const pane=$('petekV477List');const oldScroll=pane?pane.scrollTop:0;
 listVisual();if(pane)pane.scrollTop=oldScroll;
}
async function approve(){
 if(!s.img||s.status!=='DRAFT'){notice('Önce TASLAK kaydet, sonra onayla.',true);return;}
 if(s.dirty||s.needsCurveApply){notice('Değişiklik var. Önce taslağı kaydet.',true);return;}
 const reviewer=$('petekV477Reviewer').value.trim();
 if(!reviewer){notice('Onaylayan kişinin adını gir.',true);return;}
 if(!$('petekV477Confirm').checked){
   notice('Dikey delikler, üst-alt kavis, yan yüzler ve zemini kontrol ettiğini işaretle.',true);return;
 }
 if(!confirm(s.revisesUid
   ? 'DÜZENLENMİŞ MASKENİN KAYDINI ONAYLA VE GÜNCEL YAP: eski onaylı maske dosyası korunacak; sonraki üretimlerde yeni maske kullanılacak. Devam?'
   : 'Bu PETEK maskesini insan onaylı, SHA-kilitli üretim şablonu yapıyorsun. Onaylıyor musun?'))return;
 const identity={name:s.name,uid:s.uid,sha:s.sha};
 const approveButton=$('petekV477Approve');
 approveButton.disabled=true;
 const started=performance.now();
 notice('Maske güvenle onaylanıyor... SHA, kaynak ve maske denetimi yapılıyor.');
 try{
  const result=await api('/api/petek/approve',{name:identity.name,uid:identity.uid,
    source_sha:identity.sha,confirmed_sha:identity.sha,
    reviewer,confirm:'I_VISUALLY_CHECKED_VENTS_ARCHES_FLOOR',
    activate_revision:!!s.revisesUid,
    activate_confirm:s.revisesUid?'ACTIVATE_REVISED_PETEK_AND_KEEP_OLD':null});
  applyApprovedInPlace(identity.name,identity.uid,result.mask_sha);
  const seconds=((performance.now()-started)/1000).toFixed(1);
  notice((s.revisesUid
    ? 'YENİ ONAYLI MASKE GÜNCEL SÜRÜM OLDU. Eski sürüm korunuyor.'
    : 'PETEK MASKESİ ONAYLANDI. Üretimde kullanılabilir.')+
    ' · Onay '+seconds+' saniyede tamamlandı. Liste yeniden taranmadı.');
 }catch(e){
  if(s.name===identity.name&&s.uid===identity.uid&&s.status==='DRAFT')approveButton.disabled=false;
  notice('Maske onaylanamadı: '+e.message,true);
 }
}
async function newRevision(){
 if(!s.img||s.status!=='APPROVED')return;
 if(!confirm('Onaylı maskeyi yeniden düzenlemek için bu fotoğrafın güvenli, bağımsız bir TASLAK revizyonu açılacak. Mevcut onaylı maske ve önceki üretimler değişmeyecek. Devam?'))return;
 try{
    const data=await api('/api/petek/new-revision',{
        name:s.name,uid:s.uid,source_sha:s.sha,confirmed_sha:s.sha});
    await reload(data.uid);
    notice('DÜZENLEME MODU AÇILDI: '+data.uid+' TASLAĞI. 4 köşeleri sürükleyebilir, maskeyi değiştirebilirsin. Kaydet ve ardından insan onayı ver. Eski etkin onaylı kayıt değişmedi.');
 }catch(e){notice(e.message,true);}
}
async function restorePreviousApproved(){
 if(!s.isCurrent||!s.revisesUid||!s.baseUid){notice('Bu şablonun etkin onaylı revizyonu yok.',true);return;}
 if(!confirm('ÖNCEKİ ONAYLI MASKEYE DÖN: bu revizyonun yerine eski onaylı maskeyi gelecek üretimler için etkinleştireceğiz. İki sürüm de silinmeyecek. Onaylıyor musun?'))return;
 try{
  const data=await api('/api/petek/restore-approved-revision',{
    name:s.name,uid:s.revisesUid,base_uid:s.baseUid,source_sha:s.sha,
    confirm:'RESTORE_PREVIOUS_APPROVED_PETEK'});
  await reload(data.active_uid);notice('Önceki PETEK onaylı maske yeniden etkin. Diğer sürümler korunuyor.');
 }catch(e){notice('Geri dönüş yapılamadı: '+e.message,true);}
}
async function activateApprovedRevision(){
 if(s.status!=='APPROVED'||!s.revisesUid||s.isCurrent)return;
 if(!confirm('Bu onaylı maskeyi, önceki onaylı maskeyi silmeden GELECEK ÜRETİMLER İÇİN GÜNCEL yapalım mı?'))return;
 try{
  await api('/api/petek/activate-approved-revision',{
    name:s.name,uid:s.uid,source_sha:s.sha,previous_uid:s.revisesUid,
    confirm:'ACTIVATE_REVISED_PETEK_AND_KEEP_OLD'});
  await reload(s.uid);notice('Yeni onaylı PETEK revizyonu etkinleştirildi.');
 }catch(e){notice('Etkinleştirilemedi: '+e.message,true);}
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
 }else if(s.mode==='wood'||s.mode==='protect'||s.mode==='erasewood'){
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
 const list=$('petekV477ListPane')||s.listHost,workspace=$('petekV477Workspace');
 if(list&&workspace&&list.parentElement!==workspace)workspace.prepend(list);
 list?.classList.remove('in-sidebar');
}
function start(){
 const normal=$('main'),pane=$('petekV477Editor'),nav=$('petekV477Nav');
 // Category refresh can detach a live PETEK list. Retain the original DOM
 // element (including listeners and controls); never recreate it from HTML.
 const list=$('petekV477ListPane')||s.listHost;
 if(!normal||!pane||!nav||!list){
    notice('PETEK arayüzü eksik veya eski sürüm dosyaları karışmış. Güncel paketi açıp sayfayı Ctrl+Shift+R ile yenile.',true);
    return;
 }
 s.listHost=list;s.active=true;
 normal.style.display='none';pane.style.display='flex';
 nav.classList.add('selected');
 nav.after(list);
 list.classList.add('in-sidebar');
 reload();
}
function exit(){
 if(!s.active)return;
 if(s.bulkActive){notice('PETEK toplu tarama sürüyor. Önce taramayı durdur.',true);return;}
 if(s.dirty&&!confirm('Kaydedilmemiş PETEK taslağın var. Kaydetmeden çıkılsın mı?'))return;
 s.active=false;
 restoreListHost();
 $('main').style.display='flex';$('petekV477Editor').style.display='none';
 $('petekV477Nav')?.classList.remove('selected');
}
function init(){
 const pane=$('petekV477Editor');if(!pane)return;
 s.listHost=$('petekV477ListPane');
 $('petekV477Nav').addEventListener('click',start);
 $('petekV477Close').addEventListener('click',exit);
 $('petekV477Reload').addEventListener('click',()=>{
   if(s.dirty&&!confirm('Kaydedilmemiş PETEK değişiklikleri atılsın ve liste yenilensin mi?'))return;
   reload();
 });
 $('petekV477Search').addEventListener('input',listVisual);
 document.addEventListener('v499:status-filter',()=>{if(s.active)listVisual();});
 $('petekV484BulkMode').addEventListener('click',()=>{
   if(s.bulkActive)return;
   s.bulkMode=!s.bulkMode;
   $('petekV484BulkPanel').hidden=!s.bulkMode;
   $('petekV484BulkMode').textContent=s.bulkMode?'✅ PETEK Toplu Seçim Açık':'☑️ PETEK Toplu Seçim';
   if(!s.bulkMode)s.bulkSelected.clear();
   listVisual();
 });
 for(const [id,filter] of [['petekV484BulkAll','visible'],['petekV484BulkNew','new'],
   ['petekV484BulkDraft','draft'],['petekV484BulkApproved','approved'],
   ['petekV484BulkClear','clear']]){
   $(id).addEventListener('click',()=>selectBulk(filter));
 }
 $('petekV484BulkDetect').addEventListener('click',()=>runBulkPetek(false));
 $('petekV484BulkSave').addEventListener('click',()=>runBulkPetek(true));
 $('petekV498BulkApprove').addEventListener('click',beginBulkPetekApproval);
 /* Obsolete per-template review dialog disabled: single confirmation lives in PETEK bulk panel. */
 $('petekV498ListView').addEventListener('click',()=>{s.compactList=!s.compactList;
    $('petekV498ListView').textContent=s.compactList?'☷ Kompakt liste: Açık':'▧ Fotoğraflı liste: Açık';listVisual();});
 $('petekV484BulkStop').addEventListener('click',()=>{s.bulkStop=true;
   $('petekV484BulkStatus').textContent='Durdurma istendi. İçinde bulunulan sekizli grup bitecek.';});
 $('petekV484BulkReport').addEventListener('click',showBulkReport);
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
 document.addEventListener('keydown',e=>{
   if(!s.active || ['INPUT','TEXTAREA','SELECT','BUTTON'].includes(e.target.tagName) || e.target.isContentEditable) return;
   if(['ArrowRight','ArrowLeft'].includes(e.key)){
     if(s.bulkActive||s.dirty){notice('Önce açık maske değişikliklerini kaydet veya bırak; ondan sonra şablon değiştir.',true);e.preventDefault();e.stopImmediatePropagation();return;}
     e.preventDefault();e.stopImmediatePropagation();chooseRelative(e.key==='ArrowRight'?1:-1);return;
   }
   if(e.code==='Space')s.spaceHeld=true;
 },true);
 document.addEventListener('keyup',e=>{if(e.code==='Space')s.spaceHeld=false;});
 $('petekV477Preview').addEventListener('click',()=>previewArtwork(false));
 $('petekV493Preview').addEventListener('click',()=>previewArtwork(true));
 $('petekV493Before').addEventListener('click',()=>{
   if(s.previewBefore){s.preview=s.previewBefore;s.previewMode=true;draw();notice('PETEK 15 ızgara — ÖNCE (orijinal maske + baskı)');}
 });
 $('petekV493After').addEventListener('click',()=>{
   if(s.previewAfter){s.preview=s.previewAfter;s.previewMode=true;draw();notice('PETEK 15 ızgara — SONRA (geometri katmanı)');}
 });
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
 $('petekV499Restore').addEventListener('click',restorePreviousApproved);
 $('petekV499Activate').addEventListener('click',activateApprovedRevision);
 $('petekV477Canvas').addEventListener('pointerdown',pointerDown);
 $('petekV477Canvas').addEventListener('pointermove',pointerMove);
 $('petekV477Canvas').addEventListener('pointerup',pointerUp);
 $('petekV477Canvas').addEventListener('pointercancel',pointerUp);
 $('petekV477Canvas').addEventListener('lostpointercapture',pointerUp);
 document.querySelector('#categories').addEventListener('click',event=>{
   // Reclicking PETEK itself must not trigger discard/close/reopen.
   if(event.target.closest('#petekV477Nav')||event.target.closest('#petekV477ListPane'))return;
   if(!s.active)return;
   if(s.bulkActive){notice('PETEK toplu tarama sürüyor. Önce durdur.',true);
      event.preventDefault();event.stopPropagation();return;}
   if(s.dirty&&!confirm('PETEK taslağında kaydedilmemiş değişiklikler var. Altı kategoriye dönüp bunları kaybetmek istiyor musun?')){
     event.preventDefault();event.stopPropagation();return;
   }
   s.active=false;restoreListHost();$('main').style.display='flex';pane.style.display='none';
   $('petekV477Nav')?.classList.remove('selected');
 },true);
 window.addEventListener('resize',()=>{if(s.active)fit();});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
else init();
window.PetekV477={start,exit,reload,isActive:()=>s.active,isDirty:()=>s.dirty};
})();
