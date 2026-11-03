/* Purple premium review layout editor. Presentation only, no mask/quad/production API.
 * Existing engine DOM nodes and listeners are moved together, never cloned.
 * Editing is isolated from all production clicks, keyboard shortcuts and canvas drags.
 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const URL = '/api/ui-layout/review';
  const PINNED = {review: ['review-quick', 'review-approve'], petek: ['petek-approval']};
  const GROUPS = {
    review: [
      ['review-quick', 'Hızlı Onay'], ['review-alignment','Köşe Rehberi'],
      ['review-corners','4 Köşe Araçları'], ['review-source','Kaynak ve Yedek'],
      ['review-reports','Raporlar'], ['review-approve','Kritik İşlemler']
    ],
    petek: [
      ['petek-preview','Önizleme ve A/B'], ['petek-general','Ortak Araçlar'],
      ['petek-corners','4 Köşe'], ['petek-mask','Ahşap ve Maske'],
      ['petek-curves','Kavisler'], ['petek-approval','Kaydet / Onay / Revizyon']
    ]
  };
  const DEFAULT = () => ({
    schema: 1, widths: {left:290,right:330}, paneOrder:'photo-first',
    density:'normal', effect:'subtle',
    colors:{accent:'#7A4DFA',background:'#111827',panel:'#1D2638',border:'#384466',text:'#F4F6FF'},
    tabs:{review:['Tümü'],petek:['Tümü']},
    assignments:{review:{},petek:{}},
    order:{review:GROUPS.review.map(x=>x[0]),petek:GROUPS.petek.map(x=>x[0])}
  });
  const safeCopy = value => JSON.parse(JSON.stringify(value));
  let saved=DEFAULT(), current=safeCopy(saved), editing=false, mode='review';
  let history=[], future=[], activeTabs={review:'Tümü',petek:'Tümü'};
  let shell, button, handleLeft, handleRight, controls, notice;
  const groups={review:new Map(),petek:new Map()};
  const isPetek=()=> $('petekV477Editor')?.style.display!=='none';
  const currentMode=()=>isPetek()?'petek':'review';
  function node(tag, className, text){
    const el=document.createElement(tag);if(className)el.className=className;
    if(text!==undefined)el.textContent=text;
    return el;
  }
  function groupChildren(container, definition){
    if(!container) return;
    const elements=Array.from(container.children);
    const starts=container.id==='right-toolbar'?
      [elements.findIndex(el=>el.id==='v46QuickApproval'),elements.findIndex(el=>el.id==='v46-alignment-panel'),
       elements.findIndex(el=>el.matches('h3.tool-section-title')),
       elements.findIndex(el=>el.matches('details.v46-secondary-tools')),
       elements.findIndex(el=>el.id==='v46-reports'),
       elements.findIndex(el=>el.matches('h3.tool-section-title')&&el.textContent.includes('Kontrol ve Onay'))]
      :elements.map((el,i)=>el.tagName==='H3'?i:-1).filter(i=>i>=0);
    if(starts.length!==definition.length||starts.some((n,i)=>n<0||(i&&n<=starts[i-1]))) return;
    definition.forEach(([id,label],i)=>{
      const group=node('section','ui-review-card');group.dataset.reviewCard=id;
      const head=node('div','ui-card-edit-header');head.dataset.uiEditControl='1';
      const grip=node('button','ui-card-drag','↕ '+label);grip.type='button';grip.draggable=true;
      grip.title='Düzenleme modunda buradan tutup sürükleyin. Ok tuşlarıyla da sıralayın.';
      grip.dataset.uiEditControl='1';
      grip.addEventListener('dragstart',event=>{
        if(!editing){event.preventDefault();return;}
        event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',mode+':'+id);
      });
      grip.addEventListener('keydown',event=>{
        if(!editing||!['ArrowUp','ArrowDown'].includes(event.key))return;
        event.preventDefault();shiftCard(id,event.key==='ArrowUp'?-1:1);
      });
      group.addEventListener('dragover',event=>{if(editing){event.preventDefault();event.dataTransfer.dropEffect='move';}});
      group.addEventListener('drop',event=>{
        if(!editing)return;event.preventDefault();event.stopPropagation();
        const [origin,dragging]=String(event.dataTransfer.getData('text/plain')||'').split(':');
        if(origin!==mode||!groups[mode].has(dragging))return;
        const list=current.order[mode],old=list.indexOf(dragging),target=list.indexOf(id);
        if(old<0||target<0||old===target)return;
        checkpoint();list.splice(old,1);list.splice(target,0,dragging);apply();renderControls();
      });
      const selector=node('select','ui-card-tab-select');selector.dataset.uiEditControl='1';
      selector.setAttribute('aria-label',label+' sekmesini seç');
      selector.addEventListener('change',()=>{
        if(!editing)return;
        checkpoint();current.assignments[mode][id]=selector.value;apply();
      });
      head.append(grip,selector);group.append(head);
      elements.slice(starts[i],starts[i+1]||elements.length).forEach(el=>group.append(el));
      container.append(group);groups[mode].set(id,group);
    });
    container.classList.add('ui-review-card-container');
    const tabs=node('nav','ui-review-tabs');tabs.dataset.reviewTabs=container.id==='right-toolbar'?'review':'petek';
    tabs.setAttribute('aria-label','Araç sekmeleri');container.prepend(tabs);
  }
  function setupCards(){
    groupChildren($('right-toolbar'),GROUPS.review);
    groupChildren(document.querySelector('#petekV477Editor .petek-v477-tools'),GROUPS.petek);
  }
  function checkpoint(){history.push(safeCopy(current));if(history.length>32)history.shift();future=[];}
  function undo(){if(!history.length)return;future.push(safeCopy(current));current=history.pop();apply();renderControls();}
  function redo(){if(!future.length)return;history.push(safeCopy(current));current=future.pop();apply();renderControls();}
  function shiftCard(id,change){
    const items=current.order[mode],idx=items.indexOf(id),next=Math.max(0,Math.min(items.length-1,idx+change));
    if(idx===next)return;checkpoint();items.splice(idx,1);items.splice(next,0,id);apply();renderControls();
  }
  function cssColor(key){return current.colors[key];}
  function apply(){
    const r=document.documentElement.style;
    for(const key of ['accent','background','panel','border','text'])
      r.setProperty('--mor-'+key,cssColor(key));
    document.body.dataset.uiDensity=current.density;
    document.body.dataset.uiEffect=current.effect;
    $('sidebar')?.style.setProperty('width',current.widths.left+'px','important');
    $('right-toolbar')?.style.setProperty('width',current.widths.right+'px','important');
    document.querySelector('.petek-v477-tools')?.style.setProperty('width',current.widths.right+'px','important');
    const photo=document.querySelector('.petek-v477-stage');
    const tools=document.querySelector('.petek-v477-tools');
    if(photo&&tools){photo.style.order=current.paneOrder==='photo-first'?'1':'2';tools.style.order=current.paneOrder==='photo-first'?'2':'1';}
    for(const [which,cards] of Object.entries(groups)){
      const order=current.order[which],tabs=current.tabs[which];
      if(!tabs.includes(activeTabs[which]))activeTabs[which]='Tümü';
      for(const [id,element] of cards){
        element.style.order=String(order.indexOf(id));
        const assigned=current.assignments[which][id]||'Tümü';
        // Pinned save/approve and restore remain visible on every tab.
        const shouldShow=editing||activeTabs[which]===assigned||PINNED[which].includes(id);
        element.hidden=!shouldShow;
        const selector=element.querySelector('.ui-card-tab-select');
        if(selector){
          selector.replaceChildren();
          tabs.forEach(tab=>{
            const opt=document.createElement('option');opt.value=tab;opt.textContent=tab;selector.append(opt);
          });
          selector.value=assigned;
          selector.disabled=PINNED[which].includes(id);
        }
      }
      const nav=document.querySelector('[data-review-tabs="'+which+'"]');
      if(nav){
        nav.replaceChildren();
        tabs.forEach(tab=>{
          const b=node('button','ui-review-tab'+(activeTabs[which]===tab?' selected':''),tab);
          b.type='button';b.dataset.uiEditControl='1';
          b.addEventListener('click',()=>{activeTabs[which]=tab;apply();});nav.append(b);
        });
      }
    }
    updateHandles();
    window.dispatchEvent(new Event('resize')); // existing editor measures its own canvas.
  }
  function syncMode(){
    const chosen=currentMode();if(chosen===mode)return;
    mode=chosen;if(editing)renderControls();updateHandles();
  }
  function updateHandles(){
    if(!editing||!handleLeft||!handleRight)return;
    const side=$('sidebar');const target=mode==='petek'?
      document.querySelector('.petek-v477-tools'):$('right-toolbar');
    if(side){const rect=side.getBoundingClientRect();
      handleLeft.style.left=(rect.right-6)+'px';handleLeft.style.top=(rect.top+56)+'px';}
    if(target){const rect=target.getBoundingClientRect();
      handleRight.style.left=(rect.left-9)+'px';handleRight.style.top=(rect.top+56)+'px';}
  }
  function dragSize(handle,key,direction){
    handle.addEventListener('pointerdown',event=>{
      if(!editing)return;
      event.preventDefault();event.stopPropagation();checkpoint();
      const start=event.clientX,old=current.widths[key];
      handle.setPointerCapture(event.pointerId);
      const move=e=>{
        const next=old+(e.clientX-start)*direction;
        const min=key==='left'?205:245,max=key==='left'?480:530;
        current.widths[key]=Math.max(min,Math.min(max,Math.round(next)));
        apply();renderWidthLabels();
      };
      const finish=()=>{handle.removeEventListener('pointermove',move);
        handle.removeEventListener('pointerup',finish);handle.removeEventListener('pointercancel',finish);};
      handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',finish);
      handle.addEventListener('pointercancel',finish);
    });
  }
  function show(message,bad=false){
    if(!notice)return;notice.textContent=message;notice.style.color=bad?'#ffb9b9':'#b3ffdc';
  }
  function isDirty(){return JSON.stringify(current)!==JSON.stringify(saved);}
  function enter(){
    if(editing)return;
    editing=true;mode=currentMode();history=[];future=[];
    document.body.classList.add('ui-layout-editing');shell.hidden=false;
    button.textContent='Düzenleme Açık';apply();renderControls();
  }
  function cancel(){
    if(!editing)return;
    if(isDirty()&&!window.confirm('Kaydedilmemiş arayüz düzenini iptal et? Maskeler ve onaylar etkilenmez.'))return;
    current=safeCopy(saved);leave();
  }
  function leave(){
    editing=false;document.body.classList.remove('ui-layout-editing');
    shell.hidden=true;button.textContent='Arayüzü Düzenle';apply();
  }
  async function save(){
    try{
      const response=await fetch(URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(current)});
      const result=await response.json();
      if(!response.ok||!result.success)throw Error(result.code||'UI_SAVE_FAILED');
      saved=result.layout;current=safeCopy(saved);show('UI ayarları ayrı kullanıcı dosyasına kaydedildi.');leave();
    }catch(err){show('Kaydedilemedi: '+err.message,true);}
  }
  async function lastGood(){
    try{
      const r=await fetch(URL+'/previous',{cache:'no-store'});const x=await r.json();
      if(!r.ok||!x.success)throw Error(x.code||'Önceki güvenli düzen yok');
      checkpoint();current=x.layout;apply();renderControls();show('Önceki düzen önizlemede; kalıcı olması için Kaydet.');
    }catch(err){show(err.message,true);}
  }
  function input(label,child){
    const wrap=node('label','ui-layout-field');wrap.dataset.uiEditControl='1';
    wrap.append(node('span','',label),child);return wrap;
  }
  function action(label,callback){
    const b=node('button','ui-layout-action',label);b.type='button';b.dataset.uiEditControl='1';
    b.addEventListener('click',callback);return b;
  }
  function select(values,chosen,callback){
    const el=node('select','ui-layout-input');el.dataset.uiEditControl='1';
    for(const [value,title] of values){const opt=node('option','',title);opt.value=value;el.append(opt);}
    el.value=chosen;el.addEventListener('change',()=>callback(el.value));return el;
  }
  function renderWidthLabels(){
    for(const key of ['left','right']){
      const e=$('ui-layout-width-'+key);if(e)e.textContent=current.widths[key]+' px';
    }
  }
  function renderControls(){
    if(!shell)return;
    controls.replaceChildren();
    const heading=node('h2','','Arayüzü Düzenle — Şablon İnceleme');controls.append(heading);
    controls.append(node('p','ui-layout-sub','Yalnız görünüm: gerçek 4 köşe, maske, onay ve üretim kayıtlarına dokunulmaz. Panelin mor tutma kolunu sürükle.'));
    const toolbar=node('div','ui-layout-actions');
    toolbar.append(action('Kaydet',save),action('Vazgeç',cancel),action('↶ Geri Al',undo),action('↷ Yinele',redo));
    controls.append(toolbar);
    const title=node('h3','','Panel Boyutları');controls.append(title);
    ['left','right'].forEach(key=>{
      const range=node('input','ui-layout-input');range.type='range';range.min=key==='left'?'205':'245';
      range.max=key==='left'?'480':'530';range.step='5';range.value=String(current.widths[key]);
      range.dataset.uiEditControl='1';let started=false;
      range.addEventListener('pointerdown',()=>{checkpoint();started=true;});
      range.addEventListener('input',()=>{if(!started){checkpoint();started=true;}
        current.widths[key]=Number(range.value);apply();renderWidthLabels();});
      range.addEventListener('change',()=>{started=false;});
      const label=node('span','',' '+current.widths[key]+' px');label.id='ui-layout-width-'+key;
      const wrap=input(key==='left'?'Sol Liste':'Sağ Araçlar',range);wrap.append(label);controls.append(wrap);
    });
    controls.append(action('Fotoğraf / Sağ Araçların Yerini Değiştir',()=>{
      checkpoint();current.paneOrder=current.paneOrder==='photo-first'?'tools-first':'photo-first';apply();
    }));
    controls.append(node('h3','','Görünüm ve Renk'));
    for(const [field,name] of [['accent','Mor Vurgu'],['background','Ana Zemin'],['panel','Kart Yüzeyi'],
                                ['border','Kenarlık'],['text','Ana Yazı']]){
      const color=node('input','ui-layout-input');color.type='color';color.value=current.colors[field];
      color.dataset.uiEditControl='1';
      color.addEventListener('change',()=>{
        checkpoint();current.colors[field]=color.value.toUpperCase();apply();
      });controls.append(input(name,color));
    }
    controls.append(input('Yoğunluk',select([['compact','Kompakt'],['normal','Standart'],['spacious','Geniş']],current.density,v=>{
      checkpoint();current.density=v;apply();})));
    controls.append(input('Efekt',select([['off','Kapalı'],['subtle','Hafif'],['soft','Belirgin']],current.effect,v=>{
      checkpoint();current.effect=v;apply();})));
    controls.append(node('h3','','Sekmeler ve Kart Yerleşimi'));
    const tabs=current.tabs[mode];
    controls.append(input('Etkin ekran',select([['review','6 Kategori / 4 Köşe'],['petek','PETEK Maske']],mode,
      v=>{show(v===currentMode()?'Ekran seçildi':'Diğer ekranın sekmesini görmek için önce o kategoriye geç.');})));
    const active=select(tabs.map(t=>[t,t]),activeTabs[mode],v=>{activeTabs[mode]=v;apply();});
    controls.append(input('Sekme',active));
    const tabActions=node('div','ui-layout-actions');
    tabActions.append(action('Sekme Ekle',()=>{
      if(tabs.length>=8)return show('En fazla 8 sekme eklenebilir.',true);
      const name=window.prompt('Yeni sekme adı (1–30 karakter):');
      if(!name)return;const value=name.trim();
      if(!value||value.length>30||tabs.includes(value))return show('Sekme adı geçersiz/tekrar ediyor.',true);
      checkpoint();tabs.push(value);activeTabs[mode]=value;apply();renderControls();
    }));
    tabActions.append(action('Sekmeyi Adlandır',()=>{
      const old=activeTabs[mode];if(old==='Tümü')return show('Sistem sekmesi yeniden adlandırılamaz.',true);
      const name=window.prompt('Yeni sekme adı:',old);if(!name)return;
      const next=name.trim();if(!next||next.length>30||tabs.includes(next))return show('Geçersiz sekme adı.',true);
      checkpoint();tabs[tabs.indexOf(old)]=next;
      for(const [id,tab] of Object.entries(current.assignments[mode]))if(tab===old)current.assignments[mode][id]=next;
      activeTabs[mode]=next;apply();renderControls();
    }));
    tabActions.append(action('Sekmeyi Sil',()=>{
      const old=activeTabs[mode];if(old==='Tümü')return show('Sistem sekmesi silinemez.',true);
      if(!window.confirm('“'+old+'” sekmesi silinsin mi? Kartlar Tümü sekmesine taşınacak.'))return;
      checkpoint();current.tabs[mode]=tabs.filter(t=>t!==old);
      for(const [id,tab] of Object.entries(current.assignments[mode]))if(tab===old)current.assignments[mode][id]='Tümü';
      activeTabs[mode]='Tümü';apply();renderControls();
    }));
    controls.append(tabActions);
    controls.append(node('p','ui-layout-sub','Sağ paneldeki her kartı mor ↕ tutma kolundan sürükleyebilir veya ok tuşlarıyla sıralayabilirsin. Kartın sekmesini kart üstündeki listeden seç. Kaydet/Onay işlemleri daima görünür.'));
    const final=node('div','ui-layout-actions');
    final.append(action('Varsayılana Dön',()=>{checkpoint();current=DEFAULT();apply();renderControls();}));
    final.append(action('Son İyi Düzen',lastGood));controls.append(final);
    controls.append(notice);
  }
  function makeUI(){
    button=node('button','ui-layout-launcher','Arayüzü Düzenle');button.id='uiLayoutLaunch';
    button.dataset.uiEditControl='1';button.type='button';
    button.addEventListener('click',()=>editing?cancel():enter());
    shell=node('aside','ui-layout-shell');shell.id='uiLayoutShell';shell.hidden=true;
    shell.dataset.uiEditControl='1';shell.setAttribute('aria-label','Güvenli arayüz yerleşim düzenleyicisi');
    controls=node('div','ui-layout-controls');controls.dataset.uiEditControl='1';
    notice=node('div','ui-layout-notice');notice.setAttribute('role','status');
    shell.append(controls);
    handleLeft=node('div','ui-layout-resize-handle','⋮');handleRight=node('div','ui-layout-resize-handle','⋮');
    for(const handle of [handleLeft,handleRight]){handle.dataset.uiEditControl='1';handle.title='Panel genişliğini sürükle';}
    dragSize(handleLeft,'left',1);dragSize(handleRight,'right',-1);
    // The sidebar persists for all seven categories: no overlap with PETEK
    // close/approval buttons in the top toolbars.
    $('sidebar').prepend(button);
    document.body.append(shell,handleLeft,handleRight);
  }
  function blockEngineEvent(event){
    if(!editing)return;
    if(event.type==='keydown' && event.ctrlKey && !event.altKey){
      const k=event.key.toLowerCase();
      if(k==='z'){event.preventDefault();event.stopImmediatePropagation();undo();return;}
      if(k==='y'){event.preventDefault();event.stopImmediatePropagation();redo();return;}
    }
    if(event.type==='keydown'&&event.key==='Escape'){
      event.preventDefault();event.stopImmediatePropagation();cancel();return;
    }
    const target=event.target;
    if(target instanceof Element && target.closest('[data-ui-edit-control]'))return;
    if(['pointerdown','pointermove','mousedown','mousemove','touchstart','click','dblclick','keydown','keyup','wheel'].includes(event.type)){
      event.stopImmediatePropagation();event.preventDefault();
    }
  }
  async function init(){
    setupCards();makeUI();
    for(const type of ['pointerdown','pointermove','mousedown','mousemove','touchstart','click','dblclick','keydown','keyup','wheel'])
      window.addEventListener(type,blockEngineEvent,true);
    window.addEventListener('resize',updateHandles);
    new MutationObserver(syncMode).observe($('petekV477Editor'),{attributes:true,attributeFilter:['style']});
    try{
      const r=await fetch(URL,{cache:'no-store'});const obj=await r.json();
      if(r.ok&&obj.success&&obj.layout&&obj.layout.schema===1)saved=obj.layout;
    }catch(_ignored){/* Show factory layout without running a setup migration. */}
    current=safeCopy(saved);mode=currentMode();apply();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
