/* V4.6 safe review tools. Bulk detection makes review-only, source-SHA-bound drafts.
   Never approves or mutates production geometry without an explicit per-template user action. */
'use strict';
let v46BulkRunning = false;
let v46BulkStop = false;
let v46VisibleDraft = null;

function v46InitQuickPanel() {
    const place = document.getElementById('v46QuickOptions');
    for (const id of ['physical-orientation-wrap','glassCornerWrap']) {
        const el = document.getElementById(id);
        if (el && place) place.appendChild(el);
    }
}

function v46AlignmentHelp() {
    const el = document.getElementById('v46-alignment-text');
    if (!el) return;
    if (!currentImg || !Array.isArray(pts) || pts.length !== 4 || !pts.every(p => Number.isFinite(p.x) && Number.isFinite(p.y))) {
        el.textContent = 'Şablonun dört köşesi ayarlandığında ölçüm burada görünür.';
        return;
    }
    // Canonical point order: TL, TR, BR, BL. Percentages refer to IMAGE dimensions;
    // not physical centimeter differences or rectified-plane measurements.
    const [tl,tr,br,bl] = pts;
    const w = Math.max(1, Number(currentImg.width));
    const h = Math.max(1, Number(currentImg.height));
    const measure = (a,b,dir) => {
        const dx=b.x-a.x, dy=b.y-a.y;
        const dev = dir==='H' ? dy : dx;
        const angle = dir==='H' ? Math.atan2(dy,dx)*180/Math.PI
            : Math.atan2(dx,dy)*180/Math.PI;
        const norm = 100*Math.abs(dev)/(dir==='H'?h:w);
        return {diff:Math.round(dev), angle, norm};
    };
    const top=measure(tl,tr,'H'), bottom=measure(bl,br,'H');
    const left=measure(tl,bl,'V'), right=measure(tr,br,'V');
    const tag=(m,side)=>`${side}: ${m.diff>0?'+':''}${m.diff} px · ${m.angle.toFixed(1)}°`;
    const maxDev = Math.max(top.norm,bottom.norm,left.norm,right.norm);
    const note = maxDev < 0.6 ? 'Düz çekim için hizalar yakın.'
        : 'Fark var; açılı / perspektifli çekimlerde normal olabilir. Yüzeyi gözle doğrulayın.';
    el.textContent = [tag(top,'Üst (sağ−sol ↓)'),tag(bottom,'Alt (sağ−sol ↓)'),
      tag(left,'Sol (alt−üst →)'),tag(right,'Sağ (alt−üst →)'),
      `Maksimum görüntü sapması: %${maxDev.toFixed(2)}. ${note}`].join(' | ');
    el.classList.toggle('v46-warning', maxDev>=1.0);
}

async function v46ShowDraft(category, template, token) {
    const bar = document.getElementById('v46-draft-alert');
    if (bar) {bar.style.display='none'; bar.textContent='';}
    v46VisibleDraft = null;
    if (!category || !template) return;
    try {
        const url='/api/v46/corner_draft?category='+encodeURIComponent(category)+'&template='+encodeURIComponent(template);
        const response=await fetch(url, {cache:'no-store'});
        const data=await response.json();
        if (token !== templateLoadToken || category !== currentCat || template !== currentTmpl) return;
        if (!response.ok || !data.success || !data.available || !Array.isArray(data.corners)) return;
        v46VisibleDraft = {category,template,corners:data.corners,source:data.source_sha256};
        if (bar) {
            bar.style.display='block';
            const line=document.createElement('div');
            line.textContent='🟡 Bu şablonda toplu analizden gelen ONAYSIZ dört köşe önerisi var.';
            const action=document.createElement('button');
            action.type='button';
            action.textContent='👁️ Taslağı Köşelere Uygula / İncele';
            action.onclick=v46ApplyCornerDraft;
            bar.replaceChildren(line,action);
        }
    } catch (err) { console.warn('V4.6 taslak kontrolü:',err); }
}

async function v46ApplyCornerDraft() {
    const d=v46VisibleDraft;
    if (!d || d.category!==currentCat || d.template!==currentTmpl) return;
    try {
        // Revalidate identity and source SHA at the time of acceptance.
        const url='/api/v46/corner_draft?category='+encodeURIComponent(d.category)+'&template='+encodeURIComponent(d.template);
        const response=await fetch(url,{cache:'no-store'});
        const fresh=await response.json();
        if (!response.ok || !fresh.available || fresh.source_sha256!==d.source ||
          !Array.isArray(fresh.corners) || fresh.corners.length!==4)
            return showMessage('Taslak artık geçerli değil. Önce tekrar algılayın.');
        if (!confirm('Bu taslağın dört köşeleri AÇIK şablona uygulanacak. Kaydederken/onaylarken insan kontrolü zorunlu.\n\nÖnceki onaylı geometri toplu taramada DEĞİŞTİRİLMEDİ.\n\nYeni köşeleri ekranda incelemek için devam edilsin mi?')) return;
        pts=fresh.corners.map(p=>({x:Number(p[0]),y:Number(p[1])}));
        updateDataFromPoints();
        draw();
        showMessage('Taslak köşeleri ekranda gösteriliyor. Kontrol edin. Doğruysa "Bu Şablonu Onayla"ya basın. Otomatik onay YAPILMADI.');
    } catch (err) {showMessage('Taslak kontrol hatası: '+String(err));}
}

function stopBulkCornerDetect() {
    v46BulkStop=true;
    const st=document.getElementById('bulkDetectStatus');
    if (st) st.textContent='⏹ Durdurma istendi; mevcut görsel tamamlanınca duracak.';
}

async function bulkDetectSelectedCorners() {
    if (v46BulkRunning) return;
    const selected=Array.from(bulkSelectedTemplates).map(parseBulkTemplateKey)
      .filter(([cat,tmpl])=>cat && tmpl && ayarlar?.kategoriler?.[cat]?.sablonlar?.[tmpl]);
    if (!selected.length) return showMessage('Önce soldan şablonları toplu seçin.');
    if (!confirm(`${selected.length} seçili şablon için sadece DÖRT KÖŞE ÖNERİSİ çıkarılacak.\n\nAPPROVED/onaylı köşeler, ana veritabanı, şablon ve ham yedek fotoğraflar DEĞİŞTİRİLMEYECEK.\n\nHer taslağı açıp tek tek kontrol ederek onaylayabilirsiniz. Devam?`)) return;
    const button=document.getElementById('bulkDetectButton');
    const stop=document.getElementById('bulkDetectStopButton');
    const status=document.getElementById('bulkDetectStatus');
    v46BulkRunning=true; v46BulkStop=false;
    if (button) {button.disabled=true;button.textContent='⏳ Köşe taslakları oluşturuluyor...';}
    if (stop) stop.style.display='block';
    let success=0, fail=0;
    const errs=[];
    try {
        for (let i=0;i<selected.length;i++) {
            if (v46BulkStop) break;
            const [cat,tmpl]=selected[i];
            if (status) status.textContent=`Analiz: ${i+1}/${selected.length} • Başarılı: ${success} • Kontrol: ${fail}\n${cat} / ${tmpl}`;
            if (typeof isBatchAnalyzingTemplate==='function' && isBatchAnalyzingTemplate(cat,tmpl)) {
                fail++; errs.push(`${cat}/${tmpl}: başka tarama tarafından işleniyor`);
                continue;
            }
            try {
                const response=await fetch('/api/auto_detect_corners', {
                    method:'POST', headers:{'Content-Type':'application/json','X-Active-Category':cat,'X-Active-Template':tmpl},
                    body:JSON.stringify({kategori:cat,sablon:tmpl,save_as_draft:true})
                });
                const result=await response.json();
                if (!response.ok || !result.success || !Array.isArray(result.corners) || result.corners.length!==4)
                    throw new Error(result.error||`HTTP ${response.status}`);
                success++;
            } catch (err) {fail++; errs.push(`${cat}/${tmpl}: ${String(err)}`);}
            // UI remains responsive during the batch; stop takes effect between templates.
            await new Promise(resolve=>setTimeout(resolve,0));
        }
        const summary=`TOPLU KÖŞE TASLAĞI (${v46BulkStop?'DURDURULDU':'TAMAMLANDI'})\nSeçilen: ${selected.length}\nTaslak oluşturulan: ${success}\nBaşarısız / kontrol: ${fail}\nOnaylanan: 0 (otomatik onay YOK)\n\nOnaylı köşeler / kaynak fotoğraflar korunur.\n\n${errs.slice(0,100).join('\n')}`;
        if (status) status.textContent=`${success} öneri hazır · ${fail} kontrol · ${v46BulkStop?'Durduruldu':'Tamamlandı'}`;
        showCopyableReport('V4.6 Seçili Köşe Algılama Raporu', summary);
        if (typeof v46ShowDraft==='function' && currentCat && currentTmpl)
            v46ShowDraft(currentCat,currentTmpl,templateLoadToken);
    } finally {
        v46BulkRunning=false;v46BulkStop=false;
        if (button) {button.disabled=bulkSelectedTemplates.size===0;button.textContent='🧭 Seçilenlerin 4 Köşesini Algıla (Taslak)';}
        if (stop) stop.style.display='none';
    }
}

function v46SelectByReviewStatus(approved) {
    if (!bulkSelectionMode) {bulkSelectionMode=true;}
    for (const row of allTemplates) {
        const data=ayarlar?.kategoriler?.[row.cat]?.sablonlar?.[row.tmpl];
        const ok=String(data?._review_status||data?.review_status||'').toUpperCase()==='APPROVED';
        if (ok===approved) bulkSelectedTemplates.add(bulkTemplateKey(row.cat,row.tmpl));
    }
    applyBulkSelectionUi();
}

function v46BulkAlignmentReport() {
    const selected=Array.from(bulkSelectedTemplates).map(parseBulkTemplateKey);
    if (!selected.length) return showMessage('Önce rapor için şablonları seçin.');
    const lines=['V4.6 TOPLU 4 KÖŞE HİZALAMA RAPORU — SALT OKUNUR',
        'Perspektifli görsellerde açı farkı normaldir; cm değildir.','',''];
    let missing=0;
    for (const [cat,tmpl] of selected) {
        const quad=ayarlar?.kategoriler?.[cat]?.sablonlar?.[tmpl]?.koseler;
        if (!Array.isArray(quad)||quad.length!==4) {
            missing++; lines.push(`${cat}/${tmpl}: KÖŞE YOK`);continue;
        }
        try {
            const [tl,tr,br,bl]=quad.map(p=>({x:Number(p[0]),y:Number(p[1])}));
            const all=[tl,tr,br,bl];
            if (!all.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y))) throw Error('Geçersiz');
            const angle=(a,b)=>Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI;
            lines.push(`${cat}/${tmpl}: Üst Δy=${tr.y-tl.y}px, Alt Δy=${br.y-bl.y}px, Sol Δx=${bl.x-tl.x}px, Sağ Δx=${br.x-tr.x}px; Üst açı=${angle(tl,tr).toFixed(1)}° Alt açı=${angle(bl,br).toFixed(1)}°`);
        } catch (err) {missing++; lines.push(`${cat}/${tmpl}: Geçersiz köşeler`);}
    }
    lines.splice(3,0,`Seçili ${selected.length} · Köşesiz/hatalı ${missing}`);
    showCopyableReport('Seçili 4 Köşe Doğrultu Raporu',lines.join('\n'));
}

v46InitQuickPanel();
