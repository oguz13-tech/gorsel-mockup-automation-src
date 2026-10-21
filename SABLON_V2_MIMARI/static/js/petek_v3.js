"use strict";
/* PETEK V3 review surface. All painting occurs in an offscreen grayscale mask.
   The source image and existing approved corners are never written by JS. */
(() => {
  const token = document.body.dataset.token;
  const $ = id => document.getElementById(id);
  const preview = $("source"), overlay = $("paint");
  const painter = document.createElement("canvas");
  const oc = overlay.getContext("2d", {willReadFrequently:false});
  const mc = painter.getContext("2d", {willReadFrequently:true});
  const state = {name:"", mode:"corners", corners:[], drawing:false, dirty:false};
  let animationPending = false;

  function notice(message, error=false) {
    $("notice").textContent = String(message);
    $("notice").style.color = error ? "#ffb5b5" : "#b2f1d2";
  }

  async function api(url, method="GET", body=null, multipart=false) {
    const headers = {"X-Petek-Token":token};
    if (body && !multipart) headers["Content-Type"]="application/json";
    const result = await fetch(url, {method, headers,
      body: body && !multipart ? JSON.stringify(body) : body, cache:"no-store"});
    if (!result.ok) {
      let error="HTTP "+result.status;
      try { const payload=await result.json(); error=payload.error||error; } catch (_) {}
      throw new Error(error);
    }
    return result.json();
  }

  function dimensions() {
    return [preview.naturalWidth || 0, preview.naturalHeight || 0];
  }

  function initCanvas() {
    const [w,h]=dimensions();
    painter.width=overlay.width=w;
    painter.height=overlay.height=h;
    mc.fillStyle="#000";
    mc.fillRect(0,0,w,h);
    state.dirty=false;
    schedulePaint();
  }

  function imageToMask(url) {
    return new Promise((resolve,reject)=>{
      const pic=new Image();
      pic.onload=()=>{mc.clearRect(0,0,painter.width,painter.height);
                       mc.drawImage(pic,0,0,painter.width,painter.height);
                       state.dirty=false;schedulePaint();resolve();};
      pic.onerror=()=>reject(new Error("MASK_IMAGE_UNREADABLE"));
      pic.src=url;
    });
  }

  function schedulePaint() {
    if(animationPending) return;
    animationPending=true;
    requestAnimationFrame(()=>{
      animationPending=false;
      const [w,h]=dimensions();
      if(!w || !h) return;
      oc.clearRect(0,0,w,h);
      const data=mc.getImageData(0,0,w,h).data;
      const out=oc.createImageData(w,h);
      const pixels=out.data;
      for(let i=0;i<data.length;i+=4) {
        const level=data[i]; // grayscale PNG
        if(level>0){
          pixels[i]=250;pixels[i+1]=151;pixels[i+2]=62;
          pixels[i+3]=Math.round(level*0.46);
        }
      }
      oc.putImageData(out,0,0);
      if(state.corners.length) {
        oc.strokeStyle="#ff4c64";oc.lineWidth=Math.max(2,w/800);
        oc.fillStyle="#ff4c64";
        oc.beginPath();
        state.corners.forEach(([x,y],j)=>{
          if(j===0)oc.moveTo(x,y);else oc.lineTo(x,y);
          oc.beginPath();oc.arc(x,y,Math.max(4,w/170),0,2*Math.PI);
          oc.fill();oc.beginPath();
        });
        if(state.corners.length===4){
          oc.beginPath();
          state.corners.forEach(([x,y],j)=>j?oc.lineTo(x,y):oc.moveTo(x,y));
          oc.closePath();oc.stroke();
        }
      }
    });
  }

  function cursorPoint(event) {
    const rect=overlay.getBoundingClientRect();
    const [w,h]=dimensions();
    return [
      Math.max(0,Math.min(w-1,(event.clientX-rect.left)*w/rect.width)),
      Math.max(0,Math.min(h-1,(event.clientY-rect.top)*h/rect.height)),
    ];
  }

  function paintBrush(point) {
    const radius=Number($("brush").value)/2;
    mc.fillStyle=state.mode==="wood"?"#fff":"#000";
    mc.beginPath();mc.arc(point[0],point[1],radius,0,Math.PI*2);mc.fill();
    state.dirty=true;schedulePaint();
  }

  overlay.addEventListener("pointerdown",ev=>{
    if(!dimensions()[0])return;
    const point=cursorPoint(ev);
    if(state.mode==="corners"){
      if(state.corners.length===4)state.corners=[];
      state.corners.push(point.map(v=>Math.round(v)));
      notice("Köşe "+state.corners.length+"/4 seçildi.");
      schedulePaint();
      return;
    }
    state.drawing=true;
    overlay.setPointerCapture(ev.pointerId);
    paintBrush(point);
  });
  overlay.addEventListener("pointermove",ev=>{
    if(state.drawing)paintBrush(cursorPoint(ev));
  });
  overlay.addEventListener("pointerup",()=>{state.drawing=false;});
  overlay.addEventListener("pointercancel",()=>{state.drawing=false;});
  ["corners","wood","protect"].forEach(id=>{
    $(id).addEventListener("click",()=>{state.mode=id;notice(
      id==="corners"?"Dört köşe tıklayın (TL/TR/BR/BL).":
      id==="wood"?"Beyaz = baskı yapılabilir ahşap":"Siyah = orijinal korunacak detay"
    );});
  });

  async function loadMask() {
    const response=await fetch("/petek-v3/api/mask/"+encodeURIComponent(state.name)+
       "?uid="+encodeURIComponent($("uid").value),{cache:"no-store"});
    if(!response.ok){
      notice("Bu görsel için maske yok; 4 köşe ile yeni taslak oluşturun.");
      return;
    }
    const url=URL.createObjectURL(await response.blob());
    try { await imageToMask(url); notice("Kayıtlı maske yüklendi. Kaynağı kontrol edin."); }
    finally {URL.revokeObjectURL(url);}
  }

  async function load() {
    try {
      state.name=$("template").value;
      if(!state.name)throw new Error("Önce PETEK şablonu seçin");
      $("uid").value=state.name.replace(/\.[^.]+$/,"").replace(/[^A-Za-z0-9_-]/g,"_");
      await new Promise((resolve,reject)=>{
        preview.onload=resolve;preview.onerror=()=>reject(new Error("Görsel yüklenemiyor"));
        preview.src="/petek-v3/api/original/"+encodeURIComponent(state.name);
      });
      initCanvas();
      const legacy=await api("/petek-v3/api/legacy-quad/"+encodeURIComponent(state.name));
      state.corners=Array.isArray(legacy.quad)?legacy.quad:[];
      schedulePaint();
      $("meta").textContent="Kaynak: "+dimensions().join("×")+
          " piksel; onaylı dört köşe: "+(state.corners.length===4?"var":"yok");
      await loadMask();
    } catch(err){notice(err.message,true);}
  }

  async function draft() {
    try {
      if(state.corners.length!==4)throw new Error("4 köşe işaretlenmemiş");
      const data=await api("/petek-v3/api/draft","POST",{
        name:state.name,uid:$("uid").value,
        quad:state.corners,physical_aspect:Number($("aspect").value)
      });
      await loadMask();
      notice("TASLAK üretildi. Otomatik maske ONAYLI değildir. Delik, kavis, gölgeleri kontrol edip gerekirse fırçayla düzeltin. "+
        JSON.stringify(data.profile.analysis));
    } catch(err){notice(err.message,true);}
  }

  async function save() {
    try {
      if(!state.name)throw new Error("Şablon seçilmedi");
      const blob=await new Promise(resolve=>painter.toBlob(resolve,"image/png"));
      if(!blob)throw new Error("MASK_PNG_FAILED");
      const form=new FormData();
      form.append("uid",$("uid").value);
      form.append("mask",blob,"mask.png");
      const data=await api("/petek-v3/api/mask/"+
          encodeURIComponent(state.name),"POST",form,true);
      state.dirty=false;
      notice("Maske yeni SHA altında taslak olarak kaydedildi. "+
        data.profile.mask_sha256.slice(0,16));
    } catch(err){notice(err.message,true);}
  }

  async function approve() {
    try {
      if(state.dirty)throw new Error("Kaydedilmemiş maske fırça değişikliği var");
      if(!$("checked").checked)throw new Error("Görsel inceleme kutusunu işaretleyin");
      const data=await api("/petek-v3/api/approve/"+
        encodeURIComponent(state.name),"POST",{
          uid:$("uid").value,reviewer:$("reviewer").value,
          confirmation:"I_REVIEWED_PETEK_MASK",
        });
      notice("KAYNAK SHA'SINA BAĞLI İNSAN ONAYI TAMAMLANDI: "+
        data.source_sha256.slice(0,16));
    } catch(err){notice(err.message,true);}
  }

  async function start() {
    try {
      const data=await api("/petek-v3/api/templates");
      const select=$("template");
      select.replaceChildren();
      for(const name of data.templates){
        const option=document.createElement("option");
        option.value=name;option.textContent=name;select.append(option);
      }
      if(data.templates.length)await load();
      else notice("06_Petek_Dolabi kaynak klasöründe henüz görsel yok.");
    }catch(err){notice(err.message,true);}
  }
  $("load").addEventListener("click",load);
  $("draft").addEventListener("click",draft);
  $("save").addEventListener("click",save);
  $("approve").addEventListener("click",approve);
  start();
})();
