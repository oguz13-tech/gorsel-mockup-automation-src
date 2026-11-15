/* V6 Şablon İnceleme Panosu — gerçek API'lere bağlı. */
'use strict';

const state = {
  idx: 0,
  filter: 'all',
  category: 'all',
  query: '',
  selCorner: 0,
  zoom: 1,
  preview: 'final',
  items: [],
  filtered: [],
  current: null,
  requestId: 0,
  petekError: null,
  hiddenStates: new Set(),
  panX: 0,
  panY: 0,
};

const imgEl = document.getElementById('shotImg');
const svg = document.getElementById('cornerSvg');
const stage = document.getElementById('stage');
const railList = document.getElementById('railList');
const railCnt = document.getElementById('railCnt');
const railSearch = document.getElementById('railSearch');
const categoryFilter = document.getElementById('categoryFilter');
const curName = document.getElementById('curName');
const curPill = document.getElementById('curPill');
const inspPill = document.getElementById('inspPill');
const ctxCounter = document.getElementById('ctx-counter');
const statusmsg = document.getElementById('statusmsg');
const zoomVal = document.getElementById('zoomVal');
const toastEl = document.getElementById('toast');
const shot = document.getElementById('shot');
const printSize = document.getElementById('printSize');
const cornerAngles = document.getElementById('cornerAngles');
const mismatchInfo = document.getElementById('mismatchInfo');
const statApproved = document.getElementById('statApproved');
const statDraft = document.getElementById('statDraft');
const statError = document.getElementById('statError');
const navReviewCnt = document.getElementById('navReviewCnt');
const placementModal = document.getElementById('placementModal');
const placementFile = document.getElementById('placementFile');
const placementMode = document.getElementById('placementMode');
const placementCanvas = document.getElementById('placementCanvas');
const placementNote = document.getElementById('placementNote');

window.toggleCard = function toggleCard(head) {
  const card = head.parentElement;
  card.classList.toggle('open');
  const b = card.querySelector('.card-b');
  if (b) b.classList.toggle('hide', !card.classList.contains('open'));
};

let toastTimer = null;
function toast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2200);
}

const DANGER_STATUSES = new Set(['STALE_SOURCE_CHANGED', 'AMBIGUOUS_DUPLICATE', 'INVALID', 'ERROR', 'FAILED']);

function statusClass(reviewStatus) {
  const s = String(reviewStatus || '').toUpperCase();
  if (s === 'APPROVED') return 'approved';
  if (s === 'REVIEW_REQUIRED' || s === 'DRAFT') return 'draft';
  if (DANGER_STATUSES.has(s)) return 'error';
  return 'new';
}

function statusLabel(reviewStatus) {
  const s = String(reviewStatus || '').toUpperCase();
  const map = {APPROVED: 'Onaylı', REVIEW_REQUIRED: 'Taslak', DRAFT: 'Taslak', NEW: 'Yeni', ERROR: 'Hatalı', FAILED: 'Hatalı', STALE_SOURCE_CHANGED: 'Kaynak Değişti', AMBIGUOUS_DUPLICATE: 'Duplicate', INVALID: 'Geçersiz'};
  return map[s] || 'Yeni';
}

function pillFor(reviewStatus) {
  const s = String(reviewStatus || '').toUpperCase();
  if (s === 'APPROVED') return 'approved';
  if (s === 'REVIEW_REQUIRED' || s === 'DRAFT') return 'draft';
  if (DANGER_STATUSES.has(s)) return 'error';
  return 'new';
}

function flatten(data) {
  const out = [];
  const cats = (data && data.kategoriler) || {};
  for (const [cat, catData] of Object.entries(cats)) {
    if (!catData || typeof catData !== 'object') continue;
    const temps = catData.sablonlar || {};
    for (const [filename, tmpl] of Object.entries(temps)) {
      if (!tmpl || typeof tmpl !== 'object') continue;
      // "Yüklenecekler" havuzundaki geçmiş/kayıp kayıtlar (fiziksel kaynak yok) listelenmez.
      if (cat === 'Yüklenecekler') {
        const sm = tmpl._source_map || {};
        if (!(sm.active || sm.backup)) continue;
      }
      // `/api/ayarlar` currently exposes the protected geometry as `koseler`,
      // while newer adapters may already normalize it to `corners`.  Accept
      // both names at this boundary so a catalog migration cannot blank the
      // review list.
      const raw = Array.isArray(tmpl.koseler)
        ? tmpl.koseler
        : (Array.isArray(tmpl.corners) ? tmpl.corners : []);
      if (raw.length !== 4) continue;
      const points = raw.map(p => [Number(p[0]), Number(p[1])]);
      if (points.some(p => !Number.isFinite(p[0]) || !Number.isFinite(p[1]))) continue;
      const review = String(tmpl._review_status || tmpl.review_status || 'NEW').toUpperCase();
      // Keep the API/storage name (`koseler`) for diagnostics, but expose the
      // normalized editor name (`corners`) to every UI action.  The V6
      // workbench previously only populated `koseler` and then attempted
      // `t.corners.map(...)` during the first selection, which made a valid
      // catalog look like a failed load (`undefined.map`).
      out.push({cat, filename, koseler: points, corners: points, review_status: review, raw: tmpl});
    }
  }
  return out;
}

function headerFor(cat, filename) {
  return {'X-Active-Category': cat, 'X-Active-Template': filename};
}

function imageUrl(preview, cat, filename, item) {
  if (item && item.petek) {
    // PETEK photos are served by the dedicated read-only PETEK endpoint as a
    // bounded display copy; the raw source bytes stay in the workspace.
    return '/api/petek/photo/' + encodeURIComponent(filename) + '?display=1&t=' + Date.now();
  }
  const base = preview === 'original' ? '/original-image/' : '/working-image/';
  return base + encodeURIComponent(cat) + '/' + encodeURIComponent(filename) + '?t=' + Date.now();
}

function updateImage() {
  if (!state.current) return;
  state.requestId += 1;
  const id = state.requestId;
  imgEl.src = imageUrl(state.preview, state.current.cat, state.current.filename, state.current);
  imgEl.onload = () => {
    if (id !== state.requestId) return;
    const iw = imgEl.naturalWidth || 896;
    const ih = imgEl.naturalHeight || 1200;
    svg.setAttribute('viewBox', `0 0 ${iw} ${ih}`);
    state.current.iw = iw;
    state.current.ih = ih;
    render();
  };
  imgEl.onerror = () => {
    if (id !== state.requestId) return;
    const t = state.current;
    const sourceMap = (t && t.raw && t.raw._source_map) || {};
    // Çalışma kopyası okunamazsa ham yedeği salt okunur aç (tek seviye fallback).
    if (t && !t.petek && state.preview !== 'original' && sourceMap.backup) {
      state.preview = 'original';
      if (typeof syncPreviewButtons === 'function') syncPreviewButtons();
      statusmsg.textContent = 'Çalışma görseli bulunamadı — ham yedek (salt okunur) gösteriliyor.';
      toast('👁️ Ham yedek gösteriliyor (salt okunur)');
      updateImage();
      return;
    }
    statusmsg.textContent = 'Görsel okunamadı: ' + state.current.filename;
  };
}

function updateContext() {
  if (!state.current) {
    curName.textContent = '—';
    curPill.textContent = '—';
    inspPill.textContent = '—';
    ctxCounter.textContent = '0 / 0 şablon';
    statApproved.textContent = '0';
    statDraft.textContent = '0';
    statError.textContent = '0';
    printSize.textContent = '— × —';
    cornerAngles.textContent = '—';
    return;
  }
  const t = state.current;
  curName.textContent = `${t.cat} · ${t.filename}`
    + (t.petek && t.uid && t.uid !== String(t.filename).replace(/\.[^.]+$/, '') ? ` · ${t.uid}` : '');
  const s = t.review_status;
  curPill.textContent = statusLabel(s);
  curPill.className = 'pill ' + pillFor(s);
  inspPill.textContent = statusLabel(s);
  inspPill.className = 'pill ' + pillFor(s);
  const filtered = state.filtered;
  const idx = filtered.indexOf(t);
  ctxCounter.textContent = (idx >= 0 ? idx + 1 : state.idx + 1) + ' / ' + filtered.length + ' şablon';
  printSize.textContent = `${t.iw || imgEl.naturalWidth || '?'} × ${t.ih || imgEl.naturalHeight || '?'}`;
  cornerAngles.textContent = (Array.isArray(t.corners) && t.corners.length === 4)
    ? 'Ölçülüyor…' : '—';
  if (window.V6Tools && V6Tools.updateAlignment) V6Tools.updateAlignment();
  const ok = countByStatus();
  statApproved.textContent = String(ok.APPROVED || 0);
  statDraft.textContent = String(ok.REVIEW_REQUIRED || ok.DRAFT || 0);
  statError.textContent = String(ok.ERROR || ok.FAILED || 0);
  navReviewCnt.textContent = String(state.items.length);
}

function countByStatus() {
  const acc = {};
  for (const t of state.items) {
    const s = t.review_status || 'NEW';
    const bucket = DANGER_STATUSES.has(s) ? 'ERROR' : s;
    acc[bucket] = (acc[bucket] || 0) + 1;
  }
  return acc;
}

const PETEK_CATEGORY = '06_Petek_Kapama';
const CATEGORY_LABELS = {
  '01_Wifi_Kutusu': '01 · Dekoratif Ahşap Wi-Fi Kutusu',
  '02_Cam_Tablo_Dikey': '02 · Temperli Cam Tablo Dikey',
  '02_Cam_Tablo_Yatay': '02 · Temperli Cam Tablo Yatay',
  '03_Ahsap_Tablo': '03 · Dekoratif Ahşap Tablo',
  '04_Cam_Dograma': '04 · Cam Doğrama Görsel Kaplama',
  '05_Ocak_Arkasi': '05 · Temperli Cam Ocak Arkası',
  '06_Petek_Kapama': '06 · Dekoratif Ahşap Petek Dolabı',
};
const CATEGORY_ORDER = [
  '01_Wifi_Kutusu', '02_Cam_Tablo_Dikey', '02_Cam_Tablo_Yatay',
  '03_Ahsap_Tablo', '04_Cam_Dograma', '05_Ocak_Arkasi', '06_Petek_Kapama',
];

// PETEK templates live in their own immutable V3 registry and are served by
// /api/petek/*, never by the six-category ayarlar catalog.  Adapt a sidebar
// row to the board shape here; the ayarlar rows keep flowing through flatten().
function petekItems(rawItems) {
  const out = [];
  for (const it of (Array.isArray(rawItems) ? rawItems : [])) {
    if (!it || typeof it !== 'object' || !it.name) continue;
    const status = String(it.status || 'NEW').toUpperCase();
    out.push({
      cat: PETEK_CATEGORY, filename: it.name, uid: it.uid || it.name,
      koseler: [], corners: [], review_status: status, petek: true, raw: it,
    });
  }
  return out;
}

function populateCategoryFilter() {
  if (!categoryFilter) return;
  const categories = [...new Set([...CATEGORY_ORDER, ...state.items.map(t => t.cat)])]
    .filter(cat => cat !== 'Yüklenecekler')
    .sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a);
    const bi = CATEGORY_ORDER.indexOf(b);
    return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi) || a.localeCompare(b, 'tr');
  });
  const counts = {};
  for (const t of state.items) counts[t.cat] = (counts[t.cat] || 0) + 1;
  categoryFilter.replaceChildren(new Option('Tüm kategoriler', 'all'));
  categories.forEach(cat => categoryFilter.add(new Option(`${CATEGORY_LABELS[cat] || cat} · ${counts[cat] || 0}`, cat)));
  categoryFilter.value = state.category;
}

function renderRail() {
  const q = state.query.toLowerCase();
  const f = state.filter;
  const cat = state.category;
  const filtered = state.items.filter(t => {
    const matchStatus = f === 'all' || t.review_status === f;
    const matchCategory = cat === 'all' || t.cat === cat;
    const matchQuery = !q || (t.cat + ' ' + t.filename).toLowerCase().includes(q);
    const matchHidden = state.hiddenStates.size === 0 || !state.hiddenStates.has(t.review_status);
    return matchStatus && matchCategory && matchQuery && matchHidden;
  });
  state.filtered = filtered;
  railCnt.textContent = filtered.length;
  if (!filtered.length) {
    railList.innerHTML = '<div style="padding:18px;color:var(--faint);font-size:11px;text-align:center;">Sonuç bulunamadı.</div>';
    return;
  }
  railList.innerHTML = filtered.map((t, i) => {
    const sameFile = state.current && state.current.cat === t.cat && state.current.filename === t.filename;
    // PETEK revisions share one photo name; two revisions must not both light up.
    const sameRev = !(t.petek && state.current && state.current.petek) || t.uid === state.current.uid;
    const isCur = sameFile && sameRev;
    const cls = isCur ? ((t.petek ? 'trow sel petek' : 'trow sel')) : (t.petek ? 'trow petek' : 'trow');
    const bulkOn = Boolean(window.V6Tools && V6Tools.bulkMode) && !t.petek;
    const bulkKey = (window.V6Tools && V6Tools.bulkKey)
      ? V6Tools.bulkKey(t.cat, t.filename)
      : (t.cat + '|' + t.filename);
    const bulkChecked = bulkOn && Boolean(window.V6Tools.isBulkSelected(bulkKey));
    if (bulkChecked) cls += ' bulk-selected';
    // Legacy sağlık/yaşam rozetleri (varsa): 🛑/⚠️ satır başı, D/H/Ç rozeti
    const raw = t.raw || {};
    const hInfo = window.V6Tools && V6Tools.healthInfo ? V6Tools.healthInfo(t.cat, t.filename) : null;
    const lInfo = window.V6Tools && V6Tools.lifecycleInfo ? V6Tools.lifecycleInfo(t.cat, t.filename) : null;
    const danger = DANGER_STATUSES.has(String(t.review_status || '').toUpperCase()) || raw.supheli;
    const healthCrit = hInfo && hInfo.severity === 'CRITICAL';
    const healthWarn = hInfo && hInfo.severity && hInfo.severity !== 'OK' && !healthCrit;
    if (healthCrit) cls += ' trow-crit';
    else if (healthWarn || danger) cls += ' trow-warn';
    const status = String(t.review_status || 'NEW').toUpperCase();
    const color = status === 'APPROVED' ? '#3FD98A' : (status === 'REVIEW_REQUIRED' || status === 'DRAFT' ? '#F0B84C' : (DANGER_STATUSES.has(status) ? '#EF6A73' : '#5AA9FF'));
    const bar = status === 'APPROVED' ? 92 : (status === 'ERROR' || status === 'FAILED' ? 0 : (status === 'NEW' ? 18 : 45));
    const num = String(i + 1).padStart(3, '0');
    // PETEK registry revisions carry a distinct uid for the same photo name;
    // show it inline so two revisions of one file stay distinguishable.
    const stem = String(t.filename).replace(/\.[^.]+$/, '');
    const label = t.petek && t.uid && t.uid !== stem ? `${t.filename} · ${t.uid}` : t.filename;
    const healthPrefix = healthCrit ? '🛑 ' : (healthWarn ? '⚠️ ' : (danger ? '⛔ ' : ''));
    const healthTitle = hInfo && hInfo.severity !== 'OK'
      ? 'Dosya Sağlığı: ' + (hInfo.label || hInfo.code || 'Kontrol gerekli') : '';
    const dangerTitle = danger ? 'Onay artık güvenli değil; yeniden analiz/onay gerekli.' : '';
    const rowTitle = [t.petek ? 'PETEK kaydı · ' + (t.uid || '') : '', healthTitle, dangerTitle].filter(Boolean).join('\n');
    const badge = lInfo
      ? `<span class="trow-badge" title="Dosya yaşam durumu: DB=${lInfo.db ? 'VAR' : 'YOK'}, Ham=${lInfo.backup ? 'VAR' : 'YOK'}, Çalışma=${lInfo.working ? 'VAR' : 'YOK'}">D${lInfo.db ? '✅' : '❌'} H${lInfo.backup ? '✅' : '❌'} Ç${lInfo.working ? '✅' : '❌'}</span>`
      : '';
    return `<button class="${cls}" data-i="${i}" data-bulk-key="${bulkKey}" title="${rowTitle}">
      ${bulkOn ? `<span class="trow-check${bulkChecked ? ' on' : ''}" data-bulk-check="${bulkKey}" title="Toplu işlem için seç"></span>` : ''}
      <div class="top"><span class="dot" style="background:${color}"></span><span class="code">${t.cat}</span>${badge}</div>
      <div class="name">${healthPrefix}${label}</div>
      <div class="bot"><span class="num">${num}</span><span class="mini-bar"><i style="width:${bar}%"></i></span><span class="num">${status}</span></div>
    </button>`;
  }).join('');
  railList.querySelectorAll('.trow').forEach(b => {
    b.addEventListener('click', () => selectIndex(Number(b.dataset.i)));
  });
}

function selectFirstVisible() {
  if (state.filtered.length) {
    selectIndex(0);
    return;
  }
  state.current = null;
  syncActionButtons();
  updateContext();
  renderInspector();
  if (imgEl) imgEl.removeAttribute('src');
  statusmsg.textContent = state.category === PETEK_CATEGORY
    ? 'PETEK kategorisinde kullanılabilir inceleme kaydı bulunamadı.'
    : 'Bu filtre için kullanılabilir şablon bulunamadı.';
}

async function selectIndex(i) {
  const max = state.filtered.length - 1;
  i = Math.max(0, Math.min(max, i));
  const t = state.filtered[i];
  if (!t) return;
  // Ham yedekten başlayan kayıtlar (kaynak değiştirilmiş/pasif) salt okunur ham ile açılır.
  const sourceMap = (t.raw && t.raw._source_map) || {};
  state.preview = (!t.petek && sourceMap.active === false && sourceMap.backup === true) ? 'original' : 'working';
  state.zoom = 1;
  state.panX = 0;
  state.panY = 0;
  zoomVal.textContent = '100%';
  if (typeof syncPreviewButtons === 'function') syncPreviewButtons();
  // Legacy davranış: açık şablonu sessizce kaydet; kaydedilemezse geçiş iptal edilir.
  if (state.current && !state.current.petek && window.V6Tools && V6Tools.saveAll) {
    try {
      const saved = await V6Tools.saveAll(true);
      if (!saved) {
        statusmsg.textContent = 'Mevcut şablon kaydedilemedi. Veri kaybını önlemek için geçiş iptal edildi.';
        toast('⚠️ Kaydetme başarısız — geçiş iptal edildi');
        return;
      }
    } catch (err) {
      statusmsg.textContent = 'Mevcut şablon kaydedilemedi: ' + err;
      return;
    }
  }
  state.idx = i;
  if (t.petek) {
    // PETEK köşeleri ayarlar kataloğunda değil; kayıt defterinden ayrıntıyla
    // gelir. O gelene kadar sahne görseli gösterir, köşe düzenlemesi olmaz.
    state.current = Object.assign({}, t, {corners: [], petek: true});
  } else {
    const sourceCorners = Array.isArray(t.corners) ? t.corners : t.koseler;
    if (!Array.isArray(sourceCorners) || sourceCorners.length !== 4) {
      statusmsg.textContent = 'Şablonun dört köşe verisi eksik veya geçersiz.';
      toast('⚠️ Bu şablon incelemeye uygun değil');
      return;
    }
    state.current = Object.assign({}, t, {corners: sourceCorners.map(p => p.slice())});
  }
  state.selCorner = 0;
  renderRail();
  updateContext();
  renderInspector();
  updateImage();
  syncActionButtons();
  if (state.current.petek) {
    loadPetekDetail(state.current);
  } else {
    statusmsg.textContent = 'Şablon açıldı · ' + t.filename;
  }
  if (window.V6Tools && V6Tools.onTemplateSelected) V6Tools.onTemplateSelected();
}

async function loadPetekDetail(t) {
  statusmsg.textContent = 'PETEK kaydı yükleniyor · ' + t.filename;
  try {
    const res = await fetch('/api/petek/detail/' + encodeURIComponent(t.filename)
      + '?uid=' + encodeURIComponent(t.uid || t.filename), {cache: 'no-store'});
    const d = await res.json();
    if (!res.ok || !d.success) throw new Error(d.error || ('HTTP ' + res.status));
    const quad = Array.isArray(d.quad) ? d.quad : [];
    const points = quad.length === 4 ? quad.map(p => [Number(p[0]), Number(p[1])]) : [];
    if (points.some(p => !Number.isFinite(p[0]) || !Number.isFinite(p[1]))) throw new Error('PETEK_QUAD_INVALID');
    if (!state.current || !state.current.petek
        || state.current.filename !== t.filename || state.current.uid !== t.uid) return;
    t.corners = points;
    t.iw = Number(d.width) || t.iw;
    t.ih = Number(d.height) || t.ih;
    t.petekDetail = {status: d.status, physical_aspect: d.physical_aspect, mask: Boolean(d.mask)};
    state.current.corners = points.slice();
    render();
    renderInspector();
    updateContext();
    const backup = t.raw && t.raw.backup_status;
    statusmsg.textContent = 'PETEK açıldı · ' + t.filename + ' · ' + (d.status || 'Yeni')
      + (points.length ? ' · 4 köşe' : ' · köşe tanımlı değil')
      + (backup ? ' · yedek: ' + backup : '');
  } catch (err) {
    if (!state.current || !state.current.petek
        || state.current.filename !== t.filename || state.current.uid !== t.uid) return;
    statusmsg.textContent = 'PETEK ayrıntısı yüklenemedi: ' + err.message;
    toast('⚠️ PETEK ayrıntısı okunamadı');
  }
}

function syncActionButtons() {
  // PETEK onayı/maske işi kendi düzenleyicisindedir; V6 burada salt liste ve
  // önizlemdir. Butonları kapatmak, yanlışlıkla başka kata yazmayı önler.
  const petek = Boolean(state.current && state.current.petek);
  ['approveQuick', 'approveBtn', 'autoCornerBtn', 'autoBtn',
   'deleteTemplateBtn', 'restoreDeletedBtn'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.disabled = petek;
    el.title = petek ? 'PETEK onayı ayrı düzenleyicide yapılır' : '';
  });
}

function updateContextAfterDrag() {
  if (!state.current) return;
  const filtered = state.filtered;
  const idx = filtered.indexOf(state.current);
  ctxCounter.textContent = (idx >= 0 ? idx + 1 : state.idx + 1) + ' / ' + filtered.length + ' şablon';
}

function applyZoomTransform() {
  const t = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
  if (imgEl) imgEl.style.transform = t;
  svg.style.transform = t;
  const mask = document.getElementById('maskCanvas');
  if (mask) mask.style.transform = t;
}

function render() {
  if (!state.current) return;
  const iw = state.current.iw || 896;
  const ih = state.current.ih || 1200;
  const c = state.current.corners || [];
  const sel = state.selCorner;
  applyZoomTransform();
  let inner = `<rect x="0" y="0" width="${iw}" height="${ih}" fill="none" stroke="rgba(147,166,196,.10)" stroke-width="1"/>`;
  const hasQuad = c.length === 4;
  if (hasQuad) {
    const d = `M ${c[0][0]} ${c[0][1]} L ${c[1][0]} ${c[1][1]} L ${c[2][0]} ${c[2][1]} L ${c[3][0]} ${c[3][1]} Z`;
    inner += `<path class="conn" d="${d}" stroke-width="2"/>`;
    for (let i = 0; i < 4; i++) {
      const [x, y] = c[i];
      const hot = i === sel;
      inner += `<circle class="corner${hot ? ' hot' : ''}" cx="${x}" cy="${y}" r="${hot ? 13 : 10}" data-c="${i}"/>`;
      inner += `<g class="corner-tag" style="left:${(x / iw * 100).toFixed(2)}%;top:${(y / ih * 100).toFixed(2)}%;opacity:${hot ? 1 : 0}">K${i + 1}<small>${Math.round(x)}, ${Math.round(y)}</small></g>`;
    }
  }
  svg.innerHTML = inner;
  buildTags(iw, ih);
  svg.querySelectorAll('circle.corner').forEach(h => {
    h.addEventListener('pointerdown', ev => startDrag(+h.dataset.c, ev));
    h.addEventListener('click', () => { state.selCorner = +h.dataset.c; render(); });
  });
}

function buildTags(iw, ih) {
  document.querySelectorAll('.corner-tag').forEach(e => e.remove());
  if (!state.current) return;
  const corners = state.current.corners || [];
  if (corners.length !== 4) return;
  const cw = stage.clientWidth;
  const ch = stage.clientHeight;
  const sc = Math.min(cw / iw, ch / ih) * state.zoom;
  const left = (cw - iw * sc) / 2 + state.panX;
  const top = (ch - ih * sc) / 2 + state.panY;
  for (let i = 0; i < 4; i++) {
    const [x, y] = corners[i];
    const hot = i === state.selCorner;
    const el = document.createElement('div');
    el.className = 'corner-tag';
    el.style.left = (left + x * sc) + 'px';
    el.style.top = (top + y * sc) + 'px';
    el.style.opacity = hot ? '1' : '0';
    el.innerHTML = `K${i + 1}<small>${Math.round(x)}, ${Math.round(y)}</small>`;
    shot.appendChild(el);
  }
}

function clientToWorld(ev, svgEl) {
  const r = svgEl.getBoundingClientRect();
  const iw = state.current.iw || 896;
  const ih = state.current.ih || 1200;
  const x = (ev.clientX - r.left) / r.width * iw;
  const y = (ev.clientY - r.top) / r.height * ih;
  return [Math.round(x), Math.round(y)];
}

function startDrag(idx, ev) {
  if (state.current && state.current.petek) {
    toast('🔥 PETEK köşeleri bu panoda düzenlenmez');
    return;
  }
  ev.preventDefault();
  ev.stopPropagation();
  state.selCorner = idx;
  render();
  const move = e => {
    if (!state.current) return;
    const [x, y] = clientToWorld(e, svg);
    const iw = state.current.iw || 896;
    const ih = state.current.ih || 1200;
    state.current.corners[idx][0] = Math.max(0, Math.min(iw, x));
    state.current.corners[idx][1] = Math.max(0, Math.min(ih, y));
    render();
  };
  const up = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
    statusmsg.textContent = `Köşe ${idx + 1} güncellendi · ${Math.round(state.current.corners[idx][0])}, ${Math.round(state.current.corners[idx][1])}`;
    renderInspector();
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}

function renderInspector() {
  const body = document.getElementById('coBody');
  if (!body) return;
  if (!state.current) {
    body.innerHTML = '<div class="kv"><span class="k">Durum</span><span class="v">Şablon seçilmedi</span></div>';
    return;
  }
  if (state.current.petek) {
    const d = state.current.petekDetail || {};
    const raw = state.current.raw || {};
    body.innerHTML = `<div class="kv"><span class="k">Kayıt</span><span class="v">${state.current.uid || state.current.filename}</span></div>
      <div class="kv"><span class="k">Durum</span><span class="v">${d.status || state.current.review_status}</span></div>
      <div class="kv"><span class="k">Maske doğrulama</span><span class="v">${raw.mask_verified ? 'Doğrulandı' : 'Bekliyor'}</span></div>
      <div class="kv"><span class="k">Yedek</span><span class="v">${raw.backup_status || '—'}</span></div>
      <div class="kv"><span class="k">Köşe/maske yönetimi</span><span class="v" style="color:var(--amber)">PETEK düzenleyicisi</span></div>`;
    return;
  }
  body.innerHTML = state.current.corners.map(([x, y], i) => {
    const sel = i === state.selCorner ? ' sel' : '';
    return `<div class="co-row${sel}" data-c="${i}">
      <span class="n">${i + 1}</span>
      <div><div class="lbl">Köşe ${i + 1}</div><div class="val">X: ${Math.round(x)} · Y: ${Math.round(y)}</div></div>
      <button class="go" data-goto="${i}">→</button>
    </div>`;
  }).join('');
  body.querySelectorAll('.co-row').forEach(row => {
    row.addEventListener('click', e => {
      const goto = e.target.classList.contains('go');
      state.selCorner = Number(row.dataset.c);
      if (goto) toast('Köşe ' + (state.selCorner + 1) + ' seçildi');
      render();
      renderInspector();
    });
  });
}

function affineTriangle(ctx, image, src, dst) {
  const [s0, s1, s2] = src;
  const [d0, d1, d2] = dst;
  const den = s0[0] * (s1[1] - s2[1]) + s1[0] * (s2[1] - s0[1]) + s2[0] * (s0[1] - s1[1]);
  if (!Number.isFinite(den) || Math.abs(den) < 0.001) return;
  const a = (d0[0] * (s1[1] - s2[1]) + d1[0] * (s2[1] - s0[1]) + d2[0] * (s0[1] - s1[1])) / den;
  const b = (d0[1] * (s1[1] - s2[1]) + d1[1] * (s2[1] - s0[1]) + d2[1] * (s0[1] - s1[1])) / den;
  const c = (d0[0] * (s2[0] - s1[0]) + d1[0] * (s0[0] - s2[0]) + d2[0] * (s1[0] - s0[0])) / den;
  const d = (d0[1] * (s2[0] - s1[0]) + d1[1] * (s0[0] - s2[0]) + d2[1] * (s1[0] - s0[0])) / den;
  const e = (d0[0] * (s0[0] * s2[1] - s2[0] * s0[1]) + d1[0] * (s1[0] * s0[1] - s0[0] * s1[1]) + d2[0] * (s2[0] * s1[1] - s1[0] * s2[1])) / den;
  const f = (d0[1] * (s0[0] * s2[1] - s2[0] * s0[1]) + d1[1] * (s1[0] * s0[1] - s0[0] * s1[1]) + d2[1] * (s2[0] * s1[1] - s1[0] * s2[1])) / den;
  ctx.save();
  ctx.beginPath(); ctx.moveTo(d0[0], d0[1]); ctx.lineTo(d1[0], d1[1]); ctx.lineTo(d2[0], d2[1]); ctx.closePath(); ctx.clip();
  ctx.transform(a, b, c, d, e, f);
  ctx.drawImage(image, 0, 0);
  ctx.restore();
}

function drawPlacementPreview(artwork) {
  if (!placementCanvas || !state.current || !artwork) return;
  const rect = placementCanvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(320, Math.round(rect.width * dpr));
  const height = Math.max(220, Math.round(rect.height * dpr));
  placementCanvas.width = width; placementCanvas.height = height;
  const ctx = placementCanvas.getContext('2d');
  ctx.clearRect(0, 0, width, height);
  const source = imgEl;
  const sw = source.naturalWidth || state.current.iw || 896;
  const sh = source.naturalHeight || state.current.ih || 1200;
  const scale = Math.min((width - 32) / sw, (height - 32) / sh);
  const ox = (width - sw * scale) / 2, oy = (height - sh * scale) / 2;
  if (source.complete && source.naturalWidth) ctx.drawImage(source, ox, oy, sw * scale, sh * scale);
  const corners = state.current.corners || [];
  if (corners.length !== 4) return;
  const dest = corners.map(([x, y]) => [ox + x * scale, oy + y * scale]);
  const mode = placementMode ? placementMode.value : 'cover';
  const minX = Math.min(...dest.map(p => p[0])), maxX = Math.max(...dest.map(p => p[0]));
  const minY = Math.min(...dest.map(p => p[1])), maxY = Math.max(...dest.map(p => p[1]));
  const physicalAspect = Number(state.current.raw && state.current.raw.physical_aspect);
  const targetRatio = Number.isFinite(physicalAspect) && physicalAspect > 0.12 && physicalAspect <= 12
    ? physicalAspect
    : Math.max(.1, (maxX - minX) / Math.max(1, maxY - minY));
  let image = artwork;
  if (mode === 'cover' || mode === 'contain') {
    const iw = artwork.naturalWidth, ih = artwork.naturalHeight, ratio = iw / ih;
    const canvas = document.createElement('canvas');
    let cw = iw, ch = ih, sx = 0, sy = 0;
    if (mode === 'cover' && ratio > targetRatio) { cw = Math.round(ih * targetRatio); sx = Math.round((iw - cw) / 2); }
    if (mode === 'cover' && ratio < targetRatio) { ch = Math.round(iw / targetRatio); sy = Math.round((ih - ch) / 2); }
    if (mode === 'contain' && ratio > targetRatio) { ch = Math.round(iw / targetRatio); sy = Math.round((ih - ch) / 2); }
    if (mode === 'contain' && ratio < targetRatio) { cw = Math.round(ih * targetRatio); sx = Math.round((iw - cw) / 2); }
    canvas.width = Math.max(1, cw); canvas.height = Math.max(1, ch);
    canvas.getContext('2d').drawImage(artwork, sx, sy, cw, ch, 0, 0, cw, ch);
    image = canvas;
  }
  const srcW = image.width || image.naturalWidth, srcH = image.height || image.naturalHeight;
  affineTriangle(ctx, image, [[0, 0], [srcW, 0], [srcW, srcH]], [dest[0], dest[1], dest[2]]);
  affineTriangle(ctx, image, [[0, 0], [srcW, srcH], [0, srcH]], [dest[0], dest[2], dest[3]]);
  ctx.save(); ctx.beginPath(); ctx.moveTo(...dest[0]); dest.slice(1).forEach(p => ctx.lineTo(...p)); ctx.closePath();
  ctx.strokeStyle = '#17D3A3'; ctx.lineWidth = Math.max(2, dpr * 2); ctx.setLineDash([8, 6]); ctx.stroke(); ctx.restore();
}

// Üretim motoruyla birebir giydirme: sunucu üretim renderini kullanır; yazma yok.
const placementState = { artwork: null, lastOut: null };

function placementIsPetek() { return Boolean(state.current && state.current.petek); }

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function placementServerPreview(t, dataUrl, placement) {
  if (t.petek) {
    const resp = await fetch('/api/petek/detail/' + encodeURIComponent(t.filename)
      + '?uid=' + encodeURIComponent(t.uid || t.filename), { cache: 'no-store' });
    const detail = await resp.json();
    if (!resp.ok || !detail.success) throw new Error(detail.error || 'PETEK_DETAY_YOK');
    const payload = {
      name: t.filename, uid: detail.uid, source_sha: detail.source_sha,
      quad: detail.quad, mask: detail.mask,
      curve_points: detail.curve_points || { top: [], bottom: [] },
      base_mask: detail.base_mask || null,
      physical_aspect: Number(detail.physical_aspect),
      artwork_png: dataUrl,
      fifteen_slot_ab: false, fifteen_slot_strength: 'orta', preview_slot_mode: 'orta',
      realism_profile: 'belirgin', material_effect: true, pink_cleanup: false,
    };
    const r2 = await fetch('/api/petek/preview-artwork', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const d2 = await r2.json();
    if (!r2.ok || !d2.success || !d2.preview) throw new Error(d2.error || 'PETEK_ONIZLEME_YOK');
    return d2.preview;
  }
  const form = new FormData();
  form.append('file', placementState.artwork.file, placementState.artwork.file.name);
  form.append('placement', placement || 'cover');
  const r2 = await fetch('/api/templates/placement-preview', {
    method: 'POST',
    headers: headerFor(t.cat, t.filename),
    body: form,
  });
  const d2 = await r2.json();
  if (!r2.ok || !d2.success || !d2.preview) throw new Error(d2.error || ('HTTP ' + r2.status));
  return d2.preview;
}

function drawServerPreview(dataUrl) {
  const img = new Image();
  img.onload = () => {
    if (!placementCanvas) return;
    const rect = placementCanvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    placementCanvas.width = Math.max(320, Math.round(rect.width * dpr));
    placementCanvas.height = Math.max(220, Math.round(rect.height * dpr));
    const ctx = placementCanvas.getContext('2d');
    ctx.clearRect(0, 0, placementCanvas.width, placementCanvas.height);
    const scale = Math.min(placementCanvas.width / img.width, placementCanvas.height / img.height);
    const w = img.width * scale, h = img.height * scale;
    ctx.drawImage(img, (placementCanvas.width - w) / 2, (placementCanvas.height - h) / 2, w, h);
    placementNote.textContent = '⚙️ Üretim motoruyla birebir — hiçbir dosya/onay değişmedi.';
  };
  img.src = dataUrl;
}

async function runPlacementPreview() {
  const t = state.current;
  if (!t || !placementState.artwork) return;
  placementNote.textContent = '⚙️ Üretim motoruyla yerleştiriliyor…';
  try {
    const out = await placementServerPreview(t, placementState.artwork.dataUrl,
      placementMode ? placementMode.value : 'cover');
    placementState.lastOut = out;
    drawServerPreview(out);
  } catch (err) {
    placementState.lastOut = null;
    placementNote.textContent = 'Üretim önizlemesi başarısız (' + (err && err.message ? err.message : err)
      + ') — istemci warp gösteriliyor; üretimden farklı olabilir.';
    drawPlacementPreview(placementState.artwork.image);
  }
}

function openPlacementPreview() {
  if (!state.current) { toast('Önce bir şablon seçin'); return; }
  placementModal.hidden = false;
  placementState.artwork = null;
  placementState.lastOut = null;
  if (placementMode) {
    placementMode.value = 'cover';
    placementMode.disabled = placementIsPetek();
    placementMode.title = placementIsPetek() ? 'PETEK üretiminde yerleşim hep Tam Doldur' : '';
  }
  placementNote.textContent = 'Önizleme için bir PNG, JPG veya WEBP seçin. Sonuç üretim motoruyla birebir çıkar.';
  if (placementFile) placementFile.value = '';
  requestAnimationFrame(() => placementCanvas && drawPlacementPreview(null));
}

if (placementFile) placementFile.addEventListener('change', async () => {
  const file = placementFile.files && placementFile.files[0];
  if (!file) return;
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    placementNote.textContent = 'PNG, JPG veya WEBP seçin.';
    return;
  }
  if (file.size > 8 * 1024 * 1024) {
    placementNote.textContent = 'Tasarım 8 MB altında olmalı.';
    return;
  }
  placementNote.textContent = 'Tasarım okunuyor…';
  try {
    const dataUrl = await fileToDataUrl(file);
    const image = new Image();
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = reject;
      image.src = dataUrl;
    });
    placementState.artwork = { file, name: file.name, dataUrl, image };
    if (placementMode) {
      placementMode.disabled = placementIsPetek();
      placementMode.title = placementIsPetek() ? 'PETEK üretiminde yerleşim hep Tam Doldur' : '';
    }
    await runPlacementPreview();
  } catch (_) {
    placementNote.textContent = 'Tasarım okunamadı. PNG, JPG veya WEBP seçin.';
  }
});
if (placementMode) placementMode.addEventListener('change', () => {
  if (placementState.artwork) runPlacementPreview();
  else drawPlacementPreview(null);
});
if (placementCanvas) window.addEventListener('resize', () => {
  if (placementState.artwork && placementState.lastOut) drawServerPreview(placementState.lastOut);
  else drawPlacementPreview(placementState.artwork && placementState.artwork.image);
});
if (document.getElementById('placementClose')) document.getElementById('placementClose').addEventListener('click', () => { placementModal.hidden = true; });
if (placementModal) placementModal.addEventListener('click', e => { if (e.target === placementModal) placementModal.hidden = true; });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && placementModal && !placementModal.hidden) placementModal.hidden = true; });

function load() {
  railList.innerHTML = '<div style="padding:18px;color:var(--faint);font-size:11px;text-align:center;">Yükleniyor…</div>';
  // PETEK is served by its own immutable V3 registry through /api/petek/*, not
  // by the six-category catalog.  Merge it read-only so the 06 list and its
  // statuses show up without fabricating ayarlar.db rows or PETEK approvals.
  const ayarlar = fetch('/api/ayarlar', {cache: 'no-store'})
    .then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  const petek = fetch('/api/petek/templates', {cache: 'no-store'})
    .then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(d => ({items: Array.isArray(d.items) ? d.items : []}))
    .catch(err => ({error: String((err && err.message) || err)}));
  // The PETEK scan takes seconds, so the six-category catalog renders first and
  // the PETEK rows are appended when that promise settles.
  const showCatalog = data => {
    state.items = flatten(data);
    if (state.petekItems) state.items = state.items.concat(state.petekItems);
    populateCategoryFilter();
    renderRail();
    if (state.items.length) {
      selectFirstVisible();
    } else {
      state.current = null;
      updateContext();
      statusmsg.textContent = 'Kullanılabilir dört köşeli şablon bulunamadı.';
      railList.innerHTML = '<div style="padding:18px;color:var(--amber);font-size:11px;text-align:center;">Kullanılabilir şablon bulunamadı.<br><small>Kaynak fotoğrafı ve dört köşe doğrulamasını kontrol edin.</small></div>';
    }
  };

  ayarlar.then(data => {
    showCatalog(data);
    return petek;
  }).then(petekData => {
    if (petekData.error) {
      state.petekError = petekData.error;
      toast('⚠️ PETEK listesi yüklenemedi');
      statusmsg.textContent = 'PETEK listesi yüklenemedi: ' + petekData.error;
      return;
    }
    state.petekItems = petekItems(petekData.items);
    // Rebuild so a retry cannot duplicate PETEK rows.
    state.items = state.items.filter(t => !t.petek).concat(state.petekItems);
    populateCategoryFilter();
    renderRail();
    updateContext();
    if (!state.current && state.items.length) selectFirstVisible();
  })
    .catch(err => {
      statusmsg.textContent = 'Şablonlar yüklenemedi: ' + err.message;
      railList.replaceChildren();
      const panel = document.createElement('div');
      panel.style.cssText = 'padding:18px;color:var(--red);font-size:11px;text-align:center;line-height:1.45;';
      const title = document.createElement('strong');
      title.textContent = 'Şablonlar yüklenemedi';
      const detail = document.createElement('div');
      detail.style.cssText = 'margin-top:6px;color:var(--faint);word-break:break-word;';
      detail.textContent = String(err && err.message || 'Bilinmeyen veri erişim hatası');
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.textContent = 'Tekrar Dene';
      retry.style.cssText = 'margin-top:10px;padding:7px 10px;background:var(--accent);color:#06120f;border:0;border-radius:4px;font-weight:700;cursor:pointer;';
      retry.addEventListener('click', load);
      panel.append(title, detail, retry);
      railList.appendChild(panel);
    });
}

async function saveCorners() {
  if (!state.current) return;
  if (state.current.petek) {
    statusmsg.textContent = 'PETEK onayı ayrı düzenleyicide yapılır · /legacy-review?surface=petek';
    toast('🔥 PETEK onayı kendi düzenleyicisinde yapılır');
    return;
  }
  const t = state.current;
  let physicalOrientation = String((t.raw && t.raw.physical_orientation) || '').toUpperCase();
  if (t.cat === '04_Cam_Dograma') {
    const orient = document.getElementById('physicalOrientationSelect');
    physicalOrientation = orient ? String(orient.value || '').toUpperCase() : '';
    if (physicalOrientation !== 'H' && physicalOrientation !== 'V') {
      statusmsg.textContent = 'Cam Doğrama için onaydan önce fiziksel yönü Yatay (H) veya Dikey (V) seçin.';
      toast('⚠️ Cam Doğrama yönü seçin');
      return;
    }
  }
  const glassSelect = document.getElementById('glassCornerRadiusApproval');
  const rawPlan = (t.raw && t.raw.on_plan) || null;
  const onPlan = (rawPlan && typeof rawPlan === 'object' && Array.isArray(rawPlan.object_boxes) && rawPlan.object_boxes.length)
    ? {
        object_boxes: rawPlan.object_boxes.map(box => Array.isArray(box) ? box.slice(0, 4) : []),
        feather: Number(rawPlan.feather || 1.2) || 1.2,
        grabcut_iterations: Number(rawPlan.grabcut_iterations || 5) || 5,
      }
    : null;
  const body = {
    template_uid: t.cat + '_' + t.filename,
    category: t.cat,
    template: t.filename,
    corners: t.corners,
    physical_orientation: physicalOrientation,
    glass_corner_radius: glassSelect ? Number(glassSelect.value || 0) : 0,
    on_plan: onPlan,
    occlusion_reviewed: true,
  };
  const res = await fetch('/api/templates/update_corners', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const result = await res.json();
  if (!res.ok || !result.success) {
    throw new Error(result.error || ('HTTP ' + res.status));
  }
  t.review_status = 'APPROVED';
  state.current.review_status = 'APPROVED';
  statusmsg.textContent = 'Onaylandı · ' + t.filename;
  toast('✅ ' + t.filename + ' üretimde kullanılabilir');
  renderRail();
  updateContext();
  renderInspector();
  // Legacy: onay sonrası kayıt listesi ve aynı şablon görünümü tamamen yenilenir.
  if (window.V6Tools && V6Tools.refreshAfterJob) V6Tools.refreshAfterJob();
}

async function approveTemplate() {
  try {
    await saveCorners();
  } catch (err) {
    statusmsg.textContent = 'Onay başarısız: ' + err.message;
    toast('❌ ' + err.message);
  }
}

async function autoDetect() {
  if (!state.current) return;
  if (state.current.petek) {
    statusmsg.textContent = 'PETEK köşe algılama ayrı düzenleyicide yapılır · /legacy-review?surface=petek';
    toast('🔥 PETEK köşe algılama kendi düzenleyicisinde yapılır');
    return;
  }
  const t = state.current;
  statusmsg.textContent = 'Köşeler analiz ediliyor…';
  const res = await fetch('/api/auto_detect_corners', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headerFor(t.cat, t.filename),
    },
    body: JSON.stringify({save_as_draft: true}),
  });
  const result = await res.json();
  if (!res.ok || !result.success) {
    statusmsg.textContent = 'Otomatik algılama başarısız: ' + (result.error || ('HTTP ' + res.status));
    toast('❌ ' + (result.error || 'Otomatik algılama başarısız'));
    return;
  }
  if (Array.isArray(result.corners) && result.corners.length === 4) {
    state.current.corners = result.corners.map(p => [Number(p[0]), Number(p[1])]);
    render();
    renderInspector();
    statusmsg.textContent = 'Köşeler otomatik algılandı · onay bekliyor';
    toast('🧭 4 köşe taslak olarak önerildi');
  } else {
    statusmsg.textContent = 'Köşeler önerilemedi; elle ayarlayın.';
  }
}

async function deleteTemplate() {
  if (!state.current) return;
  if (window.V6Tools && V6Tools.blockIfCurrentBatchTemplate &&
      V6Tools.blockIfCurrentBatchTemplate(state.current.cat, state.current.filename, 'Şablonu silme')) return;
  if (state.current.petek) {
    statusmsg.textContent = 'PETEK kayıtları bu panodan silinmez · /legacy-review?surface=petek';
    toast('🔥 PETEK kayıtları kendi düzenleyicisinde yönetilir');
    return;
  }
  if (!confirm('Şablonu çöp kutusuna taşımak istiyor musunuz?')) return;
  const t = state.current;
  statusmsg.textContent = 'Şablon çöp kutusuna taşınıyor…';
  const res = await fetch('/api/sablon_sil', {
    method: 'POST',
    headers: headerFor(t.cat, t.filename),
  });
  const result = await res.json();
  if (!res.ok || !result.success) {
    statusmsg.textContent = 'Silinemedi: ' + (result.error || ('HTTP ' + res.status));
    toast('❌ ' + (result.error || 'Silme başarısız'));
    return;
  }
  statusmsg.textContent = 'Çöpe atıldı · ' + t.filename;
  toast('🗑️ ' + t.filename + ' çöpe atıldı');
  await load();
}

async function restoreDeleted() {
  if (state.current && state.current.petek) {
    statusmsg.textContent = 'PETEK geri alma ayrı düzenleyicide yapılır · /legacy-review?surface=petek';
    toast('🔥 PETEK geri alma kendi düzenleyicisinde yapılır');
    return;
  }
  statusmsg.textContent = 'Son silinen geri alınıyor…';
  const res = await fetch('/api/sablon_sil_geri_al', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
  const result = await res.json();
  if (!res.ok || !result.success) {
    statusmsg.textContent = 'Geri alma başarısız: ' + (result.error || ('HTTP ' + res.status));
    toast('❌ ' + (result.error || 'Geri alma başarısız'));
    return;
  }
  statusmsg.textContent = 'Geri alındı';
  toast('♻️ Son silinen geri alındı');
  await load();
}

// Eski ekranın kaydırma (pan) davranışı: Space + sürükle ya da sağ/orta düğme + sürükle
let spaceDown = false;
let panDrag = null;
function applyPanCursor() {
  const st = document.getElementById('stage');
  if (!st) return;
  st.classList.toggle('pan-ready', spaceDown && !panDrag);
  st.classList.toggle('panning', Boolean(panDrag));
}
(function bindPan() {
  const st = document.getElementById('stage');
  if (!st) return;
  st.addEventListener('pointerdown', e => {
    if (!state.current) return;
    const isPan = e.button === 1 || e.button === 2 || (spaceDown && e.button === 0);
    if (!isPan) return;
    if (e.target.closest && e.target.closest('.corner')) return;
    e.preventDefault();
    panDrag = { startX: e.clientX, startY: e.clientY, baseX: state.panX, baseY: state.panY };
    applyPanCursor();
    const move = ev => {
      if (!panDrag) return;
      state.panX = panDrag.baseX + ev.clientX - panDrag.startX;
      state.panY = panDrag.baseY + ev.clientY - panDrag.startY;
      applyZoomTransform();
      render();
    };
    const up = () => {
      panDrag = null;
      applyPanCursor();
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  });
  document.addEventListener('keyup', e => {
    if (e.key === ' ') { spaceDown = false; applyPanCursor(); }
  });
})();

// Events
document.getElementById('prevBtn').addEventListener('click', () => {
  const i = (state.idx - 1 + state.filtered.length) % (state.filtered.length || 1);
  selectIndex(i);
});
document.getElementById('nextBtn').addEventListener('click', () => {
  const i = (state.idx + 1) % (state.filtered.length || 1);
  selectIndex(i);
});
document.getElementById('approveQuick').addEventListener('click', approveTemplate);
document.getElementById('approveBtn').addEventListener('click', approveTemplate);
document.getElementById('autoCornerBtn').addEventListener('click', autoDetect);
document.getElementById('autoBtn').addEventListener('click', autoDetect);
document.getElementById('deleteTemplateBtn').addEventListener('click', deleteTemplate);
document.getElementById('restoreDeletedBtn').addEventListener('click', restoreDeleted);
document.getElementById('restoreOriginalBtn').addEventListener('click', () => {
  if (!state.current) return;
  state.preview = 'original';
  syncPreviewButtons();
  updateImage();
  statusmsg.textContent = 'Ham orijinal görünümü (salt okunur)';
});
document.getElementById('refreshWorkingBtn').addEventListener('click', () => {
  if (!state.current) return;
  state.preview = 'working';
  syncPreviewButtons();
  updateImage();
  statusmsg.textContent = 'Çalışma görseli görünümü';
});

function syncPreviewButtons() {
  document.querySelectorAll('#previewSeg button, #inspector .segmented button').forEach(b => {
    b.classList.toggle('active', b.dataset.p === state.preview);
  });
}

document.querySelectorAll('#previewSeg button, #inspector .segmented button').forEach(b => {
  b.addEventListener('click', () => {
    state.preview = b.dataset.p;
    syncPreviewButtons();
    updateImage();
  });
});

document.getElementById('zoomOut').addEventListener('click', () => {
  state.zoom = Math.max(0.4, state.zoom - 0.1);
  zoomVal.textContent = Math.round(state.zoom * 100) + '%';
  render();
});
document.getElementById('zoomIn').addEventListener('click', () => {
  state.zoom = Math.min(3, state.zoom + 0.1);
  zoomVal.textContent = Math.round(state.zoom * 100) + '%';
  render();
});
document.getElementById('zoomFit').addEventListener('click', () => {
  state.zoom = 1;
  state.panX = 0;
  state.panY = 0;
  zoomVal.textContent = '100%';
  render();
});
document.getElementById('placeBtn').addEventListener('click', openPlacementPreview);

railSearch.addEventListener('input', () => {
  state.query = railSearch.value;
  renderRail();
  selectFirstVisible();
});
if (categoryFilter) categoryFilter.addEventListener('change', () => {
  state.category = categoryFilter.value || 'all';
  renderRail();
  selectFirstVisible();
});
document.querySelectorAll('#railFilters .fchip').forEach(chip => {
  chip.addEventListener('click', () => {
    state.filter = chip.dataset.f;
    document.querySelectorAll('#railFilters .fchip').forEach(c => c.classList.toggle('on', c === chip));
    renderRail();
    selectFirstVisible();
  });
});
document.getElementById('helpBtn').addEventListener('click', () => {
  if (window.V6Tools && V6Tools.showHelp) { V6Tools.showHelp(); return; }
  alert('Kısayol: ←/→ şablon değiştir, A onayla.');
});
document.getElementById('settingsBtn').addEventListener('click', () => {
  window.location.href = '/tools';
});
document.querySelectorAll('[data-action="reports"]').forEach(b => b.addEventListener('click', () => {
  window.location.href = '/tools';
}));
document.querySelectorAll('[data-action="tools"]').forEach(b => b.addEventListener('click', () => {
  window.location.href = '/tools';
}));
document.querySelectorAll('#topnav [data-nav]').forEach(b => {
  b.addEventListener('click', () => {
    const dest = b.dataset.nav;
    if (dest === 'review') {
      window.location.href = '/';
      return;
    }
    if (dest === 'reports') {
      window.location.href = '/tools';
      return;
    }
    if (dest === 'petek') {
      window.location.href = '/legacy-review?surface=petek';
      return;
    }
    // Production, upload, and store workspaces are native Tk workspaces in
    // the desktop shell.  A direct browser visit must explain the boundary
    // instead of silently reopening the review page or an unrelated tool.
    statusmsg.textContent = 'Bu çalışma alanı Graphite masaüstü kabuğundan açılır.';
    toast('Graphite masaüstü kabuğunda açın');
  });
});

function bindPaneResizers() {
  const rail = document.getElementById('rail');
  const inspector = document.getElementById('inspector');
  document.querySelectorAll('.pane-resizer').forEach(handle => {
    const pane = handle.dataset.pane === 'rail' ? rail : inspector;
    if (!pane) return;
    let startX = 0, startWidth = 0, dragging = false;
    const limits = handle.dataset.pane === 'rail' ? [210, 440] : [260, 520];
    const move = e => {
      if (!dragging) return;
      const delta = e.clientX - startX;
      const next = handle.dataset.pane === 'rail' ? startWidth + delta : startWidth - delta;
      pane.style.width = `${Math.max(limits[0], Math.min(limits[1], next))}px`;
      render();
    };
    const stop = () => {
      dragging = false;
      handle.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      try {
        localStorage.setItem('v6.' + handle.dataset.pane + '.width', String(Math.round(pane.getBoundingClientRect().width)));
      } catch (_) { /* depolama kapalıysa sessiz */ }
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
    };
    handle.addEventListener('pointerdown', e => {
      dragging = true; startX = e.clientX; startWidth = pane.getBoundingClientRect().width;
      handle.classList.add('dragging'); document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none';
      window.addEventListener('pointermove', move); window.addEventListener('pointerup', stop);
    });
    handle.addEventListener('keydown', e => {
      if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      e.preventDefault();
      const sign = (handle.dataset.pane === 'rail' ? 1 : -1) * (e.key === 'ArrowRight' ? 1 : -1);
      const next = pane.getBoundingClientRect().width + sign * 16;
      pane.style.width = `${Math.max(limits[0], Math.min(limits[1], next))}px`;
      render();
    });
  });
}
bindPaneResizers();

document.addEventListener('keydown', e => {
  const target = e.target;
  const tag = String((target && target.tagName) || '').toLowerCase();
  if (e.altKey || e.metaKey || e.ctrlKey) return;
  if (tag === 'input' || tag === 'select' || tag === 'textarea' || tag === 'button' || (target && target.isContentEditable)) return;
  if (e.key === ' ') { e.preventDefault(); spaceDown = true; applyPanCursor(); return; }
  if (e.key === 'ArrowLeft' || e.key === 'p' || e.key === 'P') selectIndex(Math.max(0, state.idx - 1));
  if (e.key === 'ArrowRight' || e.key === 'n' || e.key === 'N') selectIndex(Math.min(state.filtered.length - 1, state.idx + 1));
  if (e.key === 'a' || e.key === 'A') approveTemplate();
  if (e.key === 'Enter') autoDetect();
  if (e.key === 'c' || e.key === 'C') { if (window.V6Tools && V6Tools.copyCorners) V6Tools.copyCorners(); }
  if (e.key === 'v' || e.key === 'V') { if (window.V6Tools && V6Tools.pasteCorners) V6Tools.pasteCorners(); }
});

window.addEventListener('resize', () => render());
shot.addEventListener('dblclick', () => {
  if (!state.current) return;
  state.zoom = 1;
  state.panX = 0;
  state.panY = 0;
  zoomVal.textContent = '100%';
  render();
});
shot.addEventListener('contextmenu', e => e.preventDefault());
shot.addEventListener('wheel', e => {
  if (!state.current) return;
  e.preventDefault();
  const delta = e.deltaY < 0 ? 0.1 : -0.1;
  state.zoom = Math.max(0.4, Math.min(3, Math.round((state.zoom + delta) * 10) / 10));
  zoomVal.textContent = Math.round(state.zoom * 100) + '%';
  render();
  if (window.V6Tools && V6Tools.paintOverlay) V6Tools.paintOverlay();
}, {passive: false});
load();
