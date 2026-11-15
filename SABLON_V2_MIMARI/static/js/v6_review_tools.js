/* V6 Şablon İnceleme Panosu — eski (legacy) arayüzden taşınan özellikler.
 *
 * Legacy `index.html` + `main.js` ekranında olup V6 panosunda olmayan
 * kullanıcıya açık özellikler bu dosyada, aynı API uç noktaları ve aynı
 * güvenlik sözleşmesi (insan onayı, recovery bazlı geri alma, salt-okunur
 * raporlar) korunarak uygulanır.  Geometry/onay kurallarını gevşetmez;
 * onaylar V6'nın tek approve akışından geçer. */
'use strict';

const el = id => document.getElementById(id);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const waitMs = ms => new Promise(resolve => setTimeout(resolve, ms));
const GLASS_CATEGORIES = ['02_Cam_Tablo_Dikey', '02_Cam_Tablo_Yatay', '04_Cam_Dograma', '05_Ocak_Arkasi'];

const v6BulkState = { mode: false, selected: new Set(), running: false, stop: false };
const v6BatchState = {
  running: false, stopRequested: false, jobId: null, category: null,
  currentTemplate: null, inFlight: new Set(), compact: false, externalPause: false,
};
let v6HealthScanJobId = null;
let v6WorkspaceAuditJobId = null;
let v6HealthSnapshot = null;
let v6WorkspaceSnapshot = null;
let v6SourceViewMode = 'working';
let v6OverlayOn = false;
let v6ClipboardCorners = null;
let v6VisibleDraft = null;
let v6ReviewPaused = false;

/* ============================================================
 * Kopyalanabilir rapor + kullanıcı mesajı (legacy showCopyableReport)
 * ========================================================== */
function showCopyableReport(title, text) {
  let overlay = el('copyable-report-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'copyable-report-overlay';
    overlay.className = 'copyable-report-overlay';
    overlay.innerHTML = `
      <div class="copyable-report-dialog" role="dialog" aria-modal="true" aria-labelledby="copyable-report-title">
        <div class="copyable-report-header">
          <div id="copyable-report-title" class="copyable-report-title"></div>
          <button type="button" class="copyable-report-close" aria-label="Kapat">×</button>
        </div>
        <textarea class="copyable-report-text" readonly spellcheck="false"></textarea>
        <div class="copyable-report-actions">
          <span class="copyable-report-status" aria-live="polite"></span>
          <button type="button" class="copyable-report-copy">📋 Tümünü Kopyala</button>
          <button type="button" class="copyable-report-ok">Tamam</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const closeReport = () => { overlay.style.display = 'none'; };
    overlay.querySelector('.copyable-report-close').onclick = closeReport;
    overlay.querySelector('.copyable-report-ok').onclick = closeReport;
    overlay.addEventListener('click', ev => { if (ev.target === overlay) closeReport(); });
    document.addEventListener('keydown', ev => {
      if (ev.key === 'Escape' && overlay.style.display !== 'none') closeReport();
    });
    overlay.querySelector('.copyable-report-copy').onclick = async () => {
      const area = overlay.querySelector('.copyable-report-text');
      const status = overlay.querySelector('.copyable-report-status');
      let copied = false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(area.value);
          copied = true;
        }
      } catch (_) { copied = false; }
      if (!copied) {
        area.focus(); area.select();
        try { copied = document.execCommand('copy'); } catch (_) { copied = false; }
        area.setSelectionRange(0, 0);
      }
      status.textContent = copied ? '✅ Metin panoya kopyalandı.' : 'Metni seçip Ctrl+C ile kopyalayabilirsiniz.';
    };
  }
  overlay.querySelector('.copyable-report-title').textContent = title;
  const area = overlay.querySelector('.copyable-report-text');
  area.value = String(text || '');
  area.scrollTop = 0;
  area.setSelectionRange(0, 0);
  overlay.querySelector('.copyable-report-status').textContent =
    'Metni fareyle seçebilir veya Ctrl+A / Ctrl+C kullanabilirsiniz.';
  overlay.style.display = 'flex';
}

function adviceForWebError(message, title) {
  const value = (String(title || '') + ' ' + String(message || '')).toLocaleLowerCase('tr');
  if (/baskı alanı|maske taslağı|0[.,]0%/.test(value))
    return ['Maske taslağı henüz oluşturulmamış veya geçersiz olabilir.',
            'Dört köşeleri kontrol et, otomatik taslak oluştur, sonra gerçek tasarımla önizle.'];
  if (/onaylı.*kilit|approved.*locked/.test(value))
    return ['Kayıt onaylı olduğundan kaynak maske korunuyor.',
            'Onaylı kaynağı yeniden düzenleme için güvenli revizyon açın; eski sürümü yedekli tutarak değişiklikleri insan onayıyla etkinleştirin.'];
  if (/8080|8090|port.*kullanım/.test(value))
    return ['İnceleme sunucusu veya port başka bir işlemce kullanılıyor olabilir.',
            'Önce kayıtları sakla; uygulamadaki güvenli sunucu durdurma aracını kullan. Rastgele süreç sonlandırma.'];
  if (/kaynak.*değiş|sha|kimlik.*uyuş/.test(value))
    return ['Fotoğraf/maske kimliği değişmiş; eski taslak kullanılamaz.',
            'Listeyi yenileyip güncel kaynağı incele; eski onayı zorla kullanma.'];
  if (/hata|failed|error|başarısız|oluşturulamadı/.test(value))
    return ['İşlem tamamlanmadı; ilgili kayıt veya uygulama adımı geçersiz olabilir.',
            'İşlem günlüğünü kopyala, aynı dosyayı yeniden dene; sorun sürerse Test Merkezi > Sorun Var olarak kaydet.'];
  return null;
}

function showMessage(message, title = 'Bilgi / Uyarı') {
  const original = String(message ?? '');
  const help = adviceForWebError(original, title);
  const full = help ? original + '\n\nNEDEN: ' + help[0] + '\n\nNE YAPMALIYIM? ' + help[1] : original;
  showCopyableReport(String(title || 'Bilgi / Uyarı'), full);
}

function showHelp() {
  showCopyableReport('Kısayollar Ve Yardım', [
    'KISAYOLLAR',
    '← / P        : Önceki şablon',
    '→ / N        : Sonraki şablon',
    'A            : Açık şablonu onayla',
    'Enter        : Köşeleri yeniden algıla',
    'C            : Köşeleri kopyala',
    'V            : Köşeleri yapıştır',
    'Tekerlek     : Sahneyi yakınlaştır / uzaklaştır',
    'Ctrl+Tekerlek: Üzerindeki yan paneli genişlet / daralt',
    '',
    'FARE',
    'Köşe noktaları sürükleme : Baskı alanını elle ayarla',
    'Sol liste + filtreler    : Kategoriye / duruma göre daraltma',
    'Toplu Seçim              : Çoklu şablonla toplu işlem',
    '',
    'ONAY GÜVENLİĞİ',
    '4 köşe + kaynak + insan onayı olmadan şablon üretimde kullanılmaz.',
    'Cam Doğrama onayında fiziksel yön (H/V) zorunludur.',
    'Onaysız, köşesiz veya kaynağı değişmiş şablonlar toplu onayda otomatik atlanır.',
  ].join('\n'));
}

/* ============================================================
 * API performans ölçümü (#perf-metric) — legacy fetch wrapper
 * ========================================================== */
if (!window.fetch.__gorselPerfWrapped) {
  const originalFetch = window.fetch;
  const perfState = window.__gorselPerfState || (window.__gorselPerfState = {
    count: 0, slow: 0, samples: [], lastPath: '', lastMs: 0,
  });
  const wrappedFetch = async function (...args) {
    const url = args[0];
    if (typeof url === 'string' && url.startsWith('/api/')) {
      const startTime = performance.now();
      try {
        const response = await originalFetch.apply(this, args);
        const durationMs = performance.now() - startTime;
        perfState.count += 1;
        perfState.lastPath = url;
        perfState.lastMs = Math.round(durationMs);
        perfState.slow += durationMs >= 2000 ? 1 : 0;
        perfState.samples.push(durationMs);
        if (perfState.samples.length > 30) perfState.samples.shift();
        const ordered = perfState.samples.slice().sort((a, b) => a - b);
        const p95 = ordered[Math.max(0, Math.ceil(ordered.length * .95) - 1)] || durationMs;
        const perfMetric = el('perf-metric');
        if (perfMetric) {
          perfMetric.style.display = 'inline-block';
          const sec = (durationMs / 1000).toFixed(2);
          perfMetric.style.color = durationMs < 500 ? '#3FD98A' : durationMs < 2000 ? '#F0B84C' : '#EF6A73';
          perfMetric.textContent = `${durationMs < 500 ? '⚡' : durationMs < 2000 ? '⏱️' : '🐢'} ${sec}s`;
          perfMetric.title = `${url} · son ${Math.round(durationMs)} ms · p95 ${Math.round(p95)} ms · ${perfState.count} istek`;
          clearTimeout(window.perfTimeout);
          window.perfTimeout = setTimeout(() => { perfMetric.style.display = 'none'; }, 4000);
        }
        return response;
      } catch (error) {
        perfState.lastPath = url;
        perfState.lastMs = Math.round(performance.now() - startTime);
        console.error('Fetch hatası:', error);
        throw error;
      }
    }
    return originalFetch.apply(this, args);
  };
  wrappedFetch.__gorselPerfWrapped = true;
  window.fetch = wrappedFetch;
}

/* ============================================================
 * Staging çakışma uyarısı (2.5 sn periyot, legacy ile aynı)
 * ========================================================== */
function formatStagingCollisionWarning(collision) {
  const identity = collision?.identity_conflict || null;
  const number = collision?.number_conflict || null;
  const lines = [
    'STAGING GÜVENLİK UYARISI',
    'İşlem: ' + String(collision?.transaction_id || ''),
    'Zaman: ' + String(collision?.updated_at || ''),
    '',
  ];
  if (identity) {
    lines.push(identity.different_extension_present ? '⛔ AYNI İSİM, FARKLI UZANTI' : '⛔ AYNI İSİM / AYNI UZANTI');
    lines.push(
      'Gelen: ' + String(identity.incoming_name || ''),
      'Kategori: ' + String(identity.category || ''),
      'Kimlik: ' + String(identity.identity || ''),
      'Gelen uzantı: ' + String(identity.incoming_extension || 'YOK'),
      'Sistemdeki uzantılar: ' + (identity.existing_extensions || []).join(', '),
      '',
      'Eşleşmeler:');
    (identity.matches || []).forEach(row => {
      lines.push('• ' + String(row.location || '') + ' — ' + String(row.name || '') + (row.path ? ' [' + String(row.path) + ']' : ''));
    });
  } else if (number) {
    lines.push(
      '⛔ NUMARA KİMLİĞİ ÇAKIŞMASI',
      'Gelen: ' + String(number.incoming_name || ''),
      'Kategori: ' + String(number.category || ''),
      'İstenen numara: ' + String(number.requested_number ?? ''),
      'Gelen uzantı: ' + String(number.incoming_extension || 'YOK'),
      'Önerilen yeni numara: ' + String(number.suggested_number ?? ''));
  }
  lines.push('', 'SONUÇ:', 'Yeni şablon oluşturulmadı.', 'Gelen dosya silinmedi veya yeniden adlandırılmadı; staging klasöründe bırakıldı.');
  if (!identity && !number && collision?.error) lines.push('', 'Detay:', String(collision.error));
  return lines.join('\n');
}

let stagingCollisionPollTimer = null;
async function pollLatestStagingCollision() {
  try {
    const response = await fetch('/api/staging/latest-collision');
    const data = await response.json();
    if (!response.ok || !data.success || !data.collision) return;
    const collision = data.collision;
    const id = String(collision.transaction_id || '');
    if (!id) return;
    const storageKey = 'jarvis-last-staging-collision-id';
    let lastSeen = '';
    try { lastSeen = localStorage.getItem(storageKey) || ''; } catch (_) { lastSeen = ''; }
    if (lastSeen === id) return;
    try { localStorage.setItem(storageKey, id); } catch (_) { /* uyarı görünür kalır */ }
    showCopyableReport('⛔ Staging İsim / Uzantı Çakışması', formatStagingCollisionWarning(collision));
  } catch (err) {
    console.warn('Staging çakışma uyarısı okunamadı:', err);
  }
}
function startStagingCollisionPolling() {
  if (stagingCollisionPollTimer) return;
  pollLatestStagingCollision();
  stagingCollisionPollTimer = window.setInterval(pollLatestStagingCollision, 2500);
}

/* ============================================================
 * Sistem sağlık bannerı (/api/saglik_durumu) — legacy banner
 * ========================================================== */
function showHealthBanner() {
  fetch('/api/saglik_durumu')
    .then(res => res.json())
    .then(data => {
      const errorCount = Number(data.sorun_sayisi || 0);
      const warningCount = Number(data.uyari_sayisi || 0);
      const solvedCount = Number(data.cozulen_sayisi || 0);
      if (!(errorCount > 0 || warningCount > 0 || solvedCount > 0)) return;
      const banner = document.createElement('div');
      banner.className = 'graphite-safety-banner';
      banner.style.cssText = 'padding:10px;text-align:center;font-weight:bold;position:relative;z-index:5;';
      if (errorCount > 0) {
        banner.style.backgroundColor = '#EF6A73'; banner.style.color = 'white';
        banner.textContent = '⛔ ÜRETİM GÜVENLİĞİ: ' + errorCount + ' kritik sorun bulundu.';
      } else if (warningCount > 0) {
        banner.style.backgroundColor = '#F0B84C'; banner.style.color = 'black';
        banner.textContent = '⚠️ FACTORY DOCTOR: ' + warningCount + ' geliştirme/sağlık uyarısı var.';
      } else {
        banner.style.backgroundColor = '#3FD98A'; banner.style.color = 'black';
        banner.textContent = '✅ SİSTEM ' + solvedCount + ' adet sorunu otomatik olarak çözdü.';
      }
      const details = document.createElement('button');
      details.innerText = 'Detaylar';
      details.style.marginLeft = '15px';
      details.onclick = () => {
        const guidance = data.doctor_guidance || {};
        const recommendations = Array.isArray(guidance.recommendations) ? guidance.recommendations : [];
        const guidanceText = recommendations.map(item =>
          '[' + (item.code || 'BİLGİ') + '] ' + (item.title || '') + '\n' +
          'Anlamı: ' + (item.explanation || '') + '\n' +
          'Güvenli adım: ' + (item.action || '') + '\n' +
          'Dayanak: ' + (item.evidence || '')
        ).join('\n\n');
        showCopyableReport('Factory Doctor Detayları',
          'KRİTİK SORUNLAR:\n' + (data.sorunlar || []).join('\n') +
          '\n\nUYARILAR (OTOMATİK ONARIM YAPILMAZ):\n' + (data.uyarilar || []).join('\n') +
          '\n\nUYARILARIN AÇIKLAMASI VE GÜVENLİ ADIMLAR:\n' + (guidanceText || 'Ek açıklama yok.') +
          '\n\nDOKTORUN PYTHON ORTAMI:\n' + (guidance.interpreter || 'Bilinmiyor') +
          '\nPython sürümü: ' + (guidance.python_version || 'Bilinmiyor') +
          '\n\nÇÖZÜLENLER:\n' + (data.cozulenler || []).join('\n'));
      };
      banner.appendChild(details);
      const mainDiv = el('main');
      if (mainDiv) mainDiv.insertBefore(banner, mainDiv.firstChild);
    })
    .catch(err => console.log('Sağlık kontrolü alınamadı', err));
}

/* ============================================================
 * Toplu seçim (bulk) — legacy bulk selection panel
 * ========================================================== */
// DOM attribute'larında NUL karakteri tarayıcı tarafından bozulduğu için
// legacy \u0000 anahtarı yerine URL-kodlu anahtar kullanılır.
function bulkTemplateKey(cat, tmpl) { return encodeURIComponent(cat) + '%7C' + encodeURIComponent(tmpl); }
function parseBulkTemplateKey(key) {
  const parts = String(key).split('%7C');
  if (parts.length !== 2) return ['', ''];
  try { return [decodeURIComponent(parts[0]), decodeURIComponent(parts[1])]; }
  catch (_) { return ['', '']; }
}

function isBulkSelected(key) { return v6BulkState.selected.has(key); }

function selectedBulkEntries() {
  return Array.from(v6BulkState.selected).map(parseBulkTemplateKey)
    .filter(([cat, tmpl]) => cat && tmpl)
    .map(([cat, tmpl]) => ({ cat, tmpl, item: state.items.find(t => !t.petek && t.cat === cat && t.filename === tmpl) || null }));
}

function updateBulkSelectedCount() {
  const count = v6BulkState.selected.size;
  const label = el('v6BulkSelectedCount');
  if (label) label.textContent = count + ' şablon seçildi';
  for (const id of ['v6BulkDeleteButton', 'v6BulkApproveButton', 'v6BulkDetectButton']) {
    const btn = el(id);
    if (btn) { btn.disabled = count === 0; btn.style.opacity = count === 0 ? '0.55' : '1'; }
  }
}

function applyBulkSelectionUi() {
  const panel = el('v6BulkSelectionActions');
  const btn = el('v6BulkModeButton');
  if (panel) panel.hidden = !v6BulkState.mode;
  if (btn) {
    btn.classList.toggle('active', v6BulkState.mode);
    btn.textContent = v6BulkState.mode ? '✅ Toplu Seçim Açık' : '☑️ Toplu Seçim';
  }
  updateBulkSelectedCount();
  renderRail();
}

function toggleBulkSelectionMode() {
  v6BulkState.mode = !v6BulkState.mode;
  if (!v6BulkState.mode) v6BulkState.selected.clear();
  applyBulkSelectionUi();
}

function clearBulkSelection() {
  v6BulkState.selected.clear();
  updateBulkSelectedCount();
  renderRail();
}

function selectAllInCurrentCategory() {
  const target = (state.category && state.category !== 'all')
    ? state.category
    : (state.current ? state.current.cat : null);
  if (!target) { showMessage('Önce bir kategori seçin ya da soldan bir şablon açın.'); return; }
  state.items.forEach(t => {
    if (!t.petek && t.cat === target) v6BulkState.selected.add(bulkTemplateKey(t.cat, t.filename));
  });
  updateBulkSelectedCount();
  renderRail();
}

function v6SelectByReviewStatus(approved) {
  if (!v6BulkState.mode) v6BulkState.mode = true;
  state.items.forEach(t => {
    if (t.petek) return;
    const ok = String(t.review_status || '').toUpperCase() === 'APPROVED';
    if (ok === approved) v6BulkState.selected.add(bulkTemplateKey(t.cat, t.filename));
  });
  applyBulkSelectionUi();
}

function v6BulkAlignmentReport() {
  const selected = Array.from(v6BulkState.selected).map(parseBulkTemplateKey);
  if (!selected.length) return showMessage('Önce rapor için şablonları seçin.');
  const lines = [
    'V6 TOPLU 4 KÖŞE HİZALAMA RAPORU — SALT OKUNUR',
    'Perspektifli görsellerde açı farkı normaldir; cm değildir.',
    '',
    '',
  ];
  let missing = 0;
  for (const [cat, tmpl] of selected) {
    const item = state.items.find(t => t.cat === cat && t.filename === tmpl);
    const quad = item && Array.isArray(item.koseler) ? item.koseler : null;
    if (!Array.isArray(quad) || quad.length !== 4) { missing++; lines.push(`${cat}/${tmpl}: KÖŞE YOK`); continue; }
    try {
      const [tl, tr, br, bl] = quad.map(p => ({ x: Number(p[0]), y: Number(p[1]) }));
      const all = [tl, tr, br, bl];
      if (!all.every(p => Number.isFinite(p.x) && Number.isFinite(p.y))) throw Error('Geçersiz');
      const angle = (a, b) => Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
      lines.push(`${cat}/${tmpl}: Üst Δy=${tr.y - tl.y}px, Alt Δy=${br.y - bl.y}px, Sol Δx=${bl.x - tl.x}px, Sağ Δx=${br.x - tr.x}px; Üst açı=${angle(tl, tr).toFixed(1)}° Alt açı=${angle(bl, br).toFixed(1)}°`);
    } catch (_) { missing++; lines.push(`${cat}/${tmpl}: Geçersiz köşeler`); }
  }
  lines.splice(3, 0, `Seçili ${selected.length} · Köşesiz/hatalı ${missing}`);
  showCopyableReport('Seçili 4 Köşe Doğrultu Raporu', lines.join('\n'));
}

async function bulkDetectSelectedCorners() {
  if (v6BulkState.running) return;
  const selected = selectedBulkEntries().filter(x => x.item);
  if (!selected.length) return showMessage('Önce soldan (PETEK olmayan) şablonları toplu seçin.');
  if (!confirm(`${selected.length} seçili şablon için sadece DÖRT KÖŞE ÖNERİSİ çıkarılacak.\n\nAPPROVED/onaylı köşeler, ana veritabanı, şablon ve ham yedek fotoğraflar DEĞİŞTİRİLMEYECEK.\n\nHer taslağı açıp tek tek kontrol ederek onaylayabilirsiniz. Devam?`)) return;
  const button = el('v6BulkDetectButton');
  const stop = el('v6BulkDetectStopButton');
  const status = el('v6BulkDetectStatus');
  v6BulkState.running = true; v6BulkState.stop = false;
  if (button) { button.disabled = true; button.textContent = '⏳ Köşe taslakları oluşturuluyor...'; }
  if (stop) stop.hidden = false;
  let success = 0, fail = 0;
  const errs = [];
  try {
    for (let i = 0; i < selected.length; i++) {
      if (v6BulkState.stop) break;
      const { cat, tmpl } = selected[i];
      if (status) status.textContent = `Analiz: ${i + 1}/${selected.length} • Başarılı: ${success} • Kontrol: ${fail}\n${cat} / ${tmpl}`;
      if (isBatchAnalyzingTemplate(cat, tmpl)) { fail++; errs.push(`${cat}/${tmpl}: başka tarama tarafından işleniyor`); continue; }
      try {
        const response = await fetch('/api/auto_detect_corners', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Active-Category': cat, 'X-Active-Template': tmpl },
          body: JSON.stringify({ kategori: cat, sablon: tmpl, save_as_draft: true }),
        });
        const result = await response.json();
        if (!response.ok || !result.success || !Array.isArray(result.corners) || result.corners.length !== 4)
          throw new Error(result.error || `HTTP ${response.status}`);
        success++;
      } catch (err) { fail++; errs.push(`${cat}/${tmpl}: ${String(err)}`); }
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    const summary = `TOPLU KÖŞE TASLAĞI (${v6BulkState.stop ? 'DURDURULDU' : 'TAMAMLANDI'})\nSeçilen: ${selected.length}\nTaslak oluşturulan: ${success}\nBaşarısız / kontrol: ${fail}\nOnaylanan: 0 (otomatik onay YOK)\n\nOnaylı köşeler / kaynak fotoğraflar korunur.\n\n${errs.slice(0, 100).join('\n')}`;
    if (status) status.textContent = `${success} öneri hazır · ${fail} kontrol · ${v6BulkState.stop ? 'Durduruldu' : 'Tamamlandı'}`;
    showCopyableReport('V6 Seçili Köşe Algılama Raporu', summary);
    checkDraft();
  } finally {
    v6BulkState.running = false; v6BulkState.stop = false;
    if (button) { button.disabled = v6BulkState.selected.size === 0; button.textContent = '🧭 Seçilenlerin 4 Köşesini Algıla (Taslak)'; }
    if (stop) stop.hidden = true;
  }
}

function stopBulkCornerDetect() {
  v6BulkState.stop = true;
  const st = el('v6BulkDetectStatus');
  if (st) st.textContent = '⏹ Durdurma istendi; mevcut görsel tamamlanınca duracak.';
}

async function bulkApproveSelected() {
  const selected = selectedBulkEntries().filter(x => x.item);
  if (!selected.length) return showMessage('Önce onaylanacak (PETEK olmayan) şablonları işaretleyin.');
  if (state.current && !state.current.petek) {
    if (!await v6SaveAll(true)) return showMessage('Açık şablon kaydedilemedi. Toplu onay durduruldu.');
  }
  const approved = [], failed = [];
  let fresh;
  try {
    const res = await fetch('/api/ayarlar', { cache: 'no-store' });
    if (!res.ok) throw new Error('Onay öncesi kayıtlar okunamadı.');
    fresh = await res.json();
  } catch (error) { return showMessage('Toplu onay: ' + error.message); }
  const candidates = selected.map(({ cat, tmpl }) => {
    const data = fresh?.kategoriler?.[cat]?.sablonlar?.[tmpl];
    const quad = data?.koseler;
    const valid = Array.isArray(quad) && quad.length === 4 &&
      quad.every(p => Array.isArray(p) && p.length === 2 && p.every(n => Number.isFinite(Number(n))));
    let orientation = String(data?.physical_orientation || '').toUpperCase();
    if (cat === '04_Cam_Dograma' && !['H', 'V'].includes(orientation)) orientation = '';
    return { cat, tmpl, valid, orientation };
  });
  const ready = candidates.filter(x => x.valid && !isBatchAnalyzingTemplate(x.cat, x.tmpl));
  for (const x of candidates) if (!ready.includes(x)) {
    failed.push(`${x.cat}/${x.tmpl}: ${!x.valid ? 'Kaydedilmiş 4 köşe yok' : 'Tarama sürüyor'}`);
  }
  if (!ready.length) return showMessage('Toplu onay için geçerli kayıtlı dört köşe bulunamadı.\n' + failed.join('\n'));
  if (!confirm(`${ready.length} şablon, her biri ayrı kontrol edilerek onaylanacak.\n${failed.length} şablon atlanacak.\nDevam edilsin mi?`)) return;
  const btn = el('v6BulkApproveButton');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Onaylanıyor...'; }
  try {
    for (const x of ready) {
      try {
        const data = fresh?.kategoriler?.[x.cat]?.sablonlar?.[x.tmpl];
        const response = await fetch('/api/templates/update_corners', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            template_uid: x.cat + '_' + x.tmpl, category: x.cat, template: x.tmpl,
            corners: (data?.koseler || []).map(p => [Number(p[0]), Number(p[1])]),
            physical_orientation: x.orientation,
            bulk_approval: true, occlusion_reviewed: false,
          }),
        });
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.error || `HTTP ${response.status}`);
        approved.push(`${x.cat}/${x.tmpl}`);
        v6BulkState.selected.delete(bulkTemplateKey(x.cat, x.tmpl));
      } catch (error) { failed.push(`${x.cat}/${x.tmpl}: ${error.message}`); }
    }
    await refreshAfterJob();
    const msg = `Toplu onay: ${approved.length} başarılı, ${failed.length} kontrol gerekiyor.` +
      (failed.length ? '\n\n' + failed.slice(0, 30).join('\n') : '');
    showMessage(msg);
  } catch (error) { showMessage('Toplu onay listesi: ' + error.message); }
  finally {
    if (btn) { btn.textContent = '✅ Seçilenleri Toplu Onayla'; btn.disabled = v6BulkState.selected.size === 0; }
    updateBulkSelectedCount();
  }
}

async function bulkDeleteSelected() {
  const selected = selectedBulkEntries().filter(x => x.item);
  if (!selected.length) return showMessage('Önce çöpe atılacak (PETEK olmayan) şablonları işaretleyin.');
  const currentlyAnalyzed = selected.filter(x => isBatchAnalyzingTemplate(x.cat, x.tmpl));
  const safeSelected = selected.filter(x => !isBatchAnalyzingTemplate(x.cat, x.tmpl));
  if (!safeSelected.length) {
    return showMessage('Seçtiğiniz şablon şu anda toplu tarama tarafından işleniyor.\nBirkaç saniye sonra tekrar deneyin.');
  }
  const scanNote = currentlyAnalyzed.length
    ? '\n\nNot: Şu anda taranan ' + currentlyAnalyzed.length + ' şablon bu işlemde atlanacak ve seçili kalacak.'
    : '';
  if (!confirm(safeSelected.length + ' şablon aktif kullanımdan çıkarılıp geri alınabilir çöp alanına taşınacak.' + scanNote + '\n\nDevam edilsin mi?')) return;
  if (v6BatchState.running) v6BatchState.externalPause = true;
  const button = el('v6BulkDeleteButton');
  const originalText = button ? button.textContent : '';
  if (button) { button.disabled = true; button.textContent = '⏳ Seçilenler çöpe taşınıyor...'; }
  const countLabel = el('v6BulkSelectedCount');
  if (countLabel) countLabel.textContent = safeSelected.length + ' şablon işleniyor...';
  try {
    const response = await fetch('/api/sablon_sil_toplu', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: safeSelected.map(({ cat, tmpl }) => ({ category: cat, template: tmpl })) }),
    });
    const data = await response.json();
    const deleted = Array.isArray(data.deleted) ? data.deleted : [];
    const failed = Array.isArray(data.failed) ? data.failed : [];
    for (const item of deleted) v6BulkState.selected.delete(bulkTemplateKey(item.category, item.template));
    await refreshAfterJob();
    // Açık şablon silindiyse seçimi sıfırla
    if (state.current && !state.current.petek
        && !state.items.some(t => t.cat === state.current.cat && t.filename === state.current.filename)) {
      state.current = null;
      const img = el('shotImg'); if (img) img.removeAttribute('src');
    }
    const failedText = failed.length
      ? '\n\nSilinemeyenler:\n' + failed.slice(0, 10).map(item => ((item.category ? item.category + ' / ' : '') + (item.template || 'Bilinmeyen') + ': ' + (item.error || 'Bilinmeyen hata'))).join('\n')
      : '';
    showMessage(
      'Toplu işlem tamamlandı.\n' + Number(data.deleted_count || deleted.length) + ' şablon çöpe taşındı.' +
      (failed.length ? '\n' + failed.length + ' şablon silinemedi.' : '') + failedText +
      (currentlyAnalyzed.length ? '\n\n' + currentlyAnalyzed.length + ' şablon o anda tarandığı için atlandı; seçili bırakıldı.' : ''));
    refreshTemplateHealth(false, false);
  } catch (err) { showMessage('Toplu silme başarısız: ' + err.message); }
  finally {
    v6BatchState.externalPause = false;
    if (button) { button.textContent = originalText || '🗑️ Seçilenleri Çöpe At'; button.disabled = v6BulkState.selected.size === 0; }
    updateBulkSelectedCount();
  }
}

/* ============================================================
 * Toplu köşe taraması (BATCH_CORNER_SCAN) — legacy batchAnalyze
 * ========================================================== */
function isBatchAnalyzingTemplate(cat, tmpl) {
  if (!v6BatchState.running || v6BatchState.category !== cat) return false;
  const key = bulkTemplateKey(cat, tmpl);
  return v6BatchState.inFlight.has(key) || v6BatchState.currentTemplate === tmpl;
}

function blockIfCurrentBatchTemplate(cat, tmpl, actionLabel) {
  if (!isBatchAnalyzingTemplate(cat, tmpl)) return false;
  showMessage('(' + (actionLabel || 'Bu işlem') + ') şu anda mümkün değil çünkü bu şablon hızlı toplu tarama paketinde işleniyor.\n\nBirkaç saniye sonra tekrar deneyin. Diğer şablonlarda çalışmaya devam edebilirsiniz.');
  return true;
}

function ensureBatchAnalyzeProgressModal() {
  let overlay = el('batchAnalyzeProgressOverlay');
  if (overlay) return overlay;
  overlay = document.createElement('div');
  overlay.id = 'batchAnalyzeProgressOverlay';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.72);display:none;align-items:center;justify-content:center;z-index:10000;';
  overlay.innerHTML = `
    <div id="batchAnalyzePanel" style="width:min(560px,92vw);background:#131C2B;border:1px solid #22304A;border-radius:12px;padding:22px;box-shadow:0 18px 60px rgba(0,0,0,.45);color:#fff;font-family:Arial,sans-serif;">
      <div id="batchAnalyzeTitle" style="font-size:20px;font-weight:700;margin-bottom:8px;">Şablonlar analiz ediliyor</div>
      <div id="batchAnalyzeSummary" style="font-size:14px;color:#ddd;margin-bottom:14px;">Hazırlanıyor...</div>
      <div style="height:18px;background:#182238;border-radius:999px;overflow:hidden;border:1px solid #22304A;">
        <div id="batchAnalyzeBar" style="height:100%;width:0%;background:#17D3A3;transition:width .18s ease;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;gap:12px;margin-top:8px;font-size:13px;color:#ddd;">
        <span id="batchAnalyzeCount">0 / 0</span>
        <span id="batchAnalyzePercent">%0</span>
      </div>
      <div id="batchAnalyzeCurrent" style="margin-top:14px;padding:10px;background:#0F1622;border-radius:7px;font-size:13px;word-break:break-word;color:#eee;">Bekleniyor...</div>
      <div id="batchAnalyzeErrors" style="display:none;margin-top:12px;padding:10px;background:#2E161A;border-radius:7px;font-size:12px;max-height:120px;overflow:auto;"></div>
      <div id="batchAnalyzeRunActions" style="display:flex;gap:8px;margin-top:14px;">
        <button id="batchAnalyzeBackground" type="button" style="flex:1;padding:10px;border:0;border-radius:7px;background:#2F6FED;color:white;font-weight:700;cursor:pointer;">↘ Arka Planda Sürdür</button>
        <button id="batchAnalyzeStop" type="button" style="flex:1;padding:10px;border:0;border-radius:7px;background:#A94442;color:white;font-weight:700;cursor:pointer;">⏹ Taramayı Durdur</button>
      </div>
      <button id="batchAnalyzeClose" type="button" style="display:none;width:100%;margin-top:14px;padding:11px;border:0;border-radius:7px;background:#17D3A3;color:#04140E;font-weight:700;cursor:pointer;">Tamam</button>
    </div>`;
  document.body.appendChild(overlay);
  el('batchAnalyzeBackground').addEventListener('click', () => setBatchAnalyzeCompact(!v6BatchState.compact));
  el('batchAnalyzeStop').addEventListener('click', async () => {
    if (!v6BatchState.running || v6BatchState.stopRequested) return;
    v6BatchState.stopRequested = true;
    const stopButton = el('batchAnalyzeStop');
    if (stopButton) { stopButton.disabled = true; stopButton.textContent = '⏳ Mevcut küçük paket bitsin, sonra duracak'; stopButton.style.opacity = '0.65'; }
    el('batchAnalyzeSummary').textContent = 'Durdurma istendi. İşlenen küçük paket tamamlanınca tarama duracak...';
    if (v6BatchState.jobId) {
      try { await fetch('/api/jobs/' + encodeURIComponent(v6BatchState.jobId) + '/stop', { method: 'POST' }); }
      catch (err) { console.warn('Kalıcı job durdurma isteği gönderilemedi:', err); }
    }
  });
  el('batchAnalyzeClose').addEventListener('click', () => { overlay.style.display = 'none'; });
  return overlay;
}

function setBatchAnalyzeCompact(compact) {
  const overlay = ensureBatchAnalyzeProgressModal();
  const panel = el('batchAnalyzePanel');
  const toggle = el('batchAnalyzeBackground');
  v6BatchState.compact = Boolean(compact);
  if (v6BatchState.compact) {
    overlay.style.background = 'transparent'; overlay.style.pointerEvents = 'none'; overlay.style.alignItems = 'flex-end'; overlay.style.justifyContent = 'flex-end'; overlay.style.padding = '18px';
    if (panel) { panel.style.width = 'min(410px, calc(100vw - 36px))'; panel.style.padding = '14px'; panel.style.pointerEvents = 'auto'; }
    if (toggle) toggle.textContent = '↗ Büyüt';
  } else {
    overlay.style.background = 'rgba(0,0,0,.72)'; overlay.style.pointerEvents = 'auto'; overlay.style.alignItems = 'center'; overlay.style.justifyContent = 'center'; overlay.style.padding = '0';
    if (panel) { panel.style.width = 'min(560px,92vw)'; panel.style.padding = '22px'; panel.style.pointerEvents = 'auto'; }
    if (toggle) toggle.textContent = '↘ Arka Planda Sürdür';
  }
}

function updateBatchAnalyzeProgress(done, total, currentText, statusText) {
  const overlay = ensureBatchAnalyzeProgressModal();
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  el('batchAnalyzeBar').style.width = percent + '%';
  el('batchAnalyzeCount').textContent = done + ' / ' + total;
  el('batchAnalyzePercent').textContent = '%' + percent;
  el('batchAnalyzeSummary').textContent = statusText || 'Analiz devam ediyor...';
  el('batchAnalyzeCurrent').textContent = currentText ? 'İşlenen: ' + currentText : 'Hazırlanıyor...';
  overlay.style.display = 'flex';
}

function finishBatchAnalyzeProgress(total, processedCount, successCount, approvedProtectedCount, failureCount, skippedCount, failures, stopped) {
  const overlay = ensureBatchAnalyzeProgressModal();
  const percent = total > 0 ? Math.round((processedCount / total) * 100) : 0;
  el('batchAnalyzeBar').style.width = percent + '%';
  el('batchAnalyzeCount').textContent = processedCount + ' / ' + total;
  el('batchAnalyzePercent').textContent = '%' + percent;
  el('batchAnalyzeTitle').textContent = stopped ? '⏹ Tarama durduruldu' : (failureCount === 0 ? '✅ Analiz tamamlandı' : '⚠️ Analiz tamamlandı');
  el('batchAnalyzeSummary').textContent = processedCount + ' dosya işlendi • ' + successCount + ' analiz edildi • ' + approvedProtectedCount + ' onaylı korundu • ' + skippedCount + ' atlandı • ' + failureCount + ' hatalı';
  el('batchAnalyzeCurrent').textContent = stopped
    ? 'O ana kadar tamamlanan analizler kaydedildi. Kalan şablonlar taranmadı.'
    : (failureCount === 0 ? 'Kategori taraması tamamlandı. 4 köşe kalite algoritması değiştirilmedi.' : 'Tarama tamamlandı; bazı dosyalar ayrıca kontrol edilmeli.');
  const errorBox = el('batchAnalyzeErrors');
  if (failureCount > 0) { errorBox.style.display = 'block'; errorBox.textContent = (failures || []).slice(0, 8).join('\n'); }
  else { errorBox.style.display = 'none'; errorBox.textContent = ''; }
  const runActions = el('batchAnalyzeRunActions');
  if (runActions) runActions.style.display = 'none';
  el('batchAnalyzeClose').style.display = 'block';
  overlay.style.display = 'flex';
}

function chooseBatchAnalyzeCategory() {
  const categories = [...new Set(state.items.filter(t => !t.petek).map(t => t.cat))];
  if (!categories.length) { showMessage('Yeniden taranacak kategori bulunamadı.'); return Promise.resolve(null); }
  return new Promise(resolve => {
    el('batch-category-chooser')?.remove();
    const overlay = document.createElement('div');
    overlay.id = 'batch-category-chooser';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:21000;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(0,0,0,.72);';
    const dialog = document.createElement('div');
    dialog.style.cssText = 'width:min(560px,94vw);background:#131C2B;color:#E9EFF9;border:1px solid #555;border-radius:12px;padding:20px;box-shadow:0 18px 60px rgba(0,0,0,.45);';
    const title = document.createElement('div');
    title.textContent = 'Hangi kategoriyi yeniden taramak istiyorsunuz?';
    title.style.cssText = 'font-size:18px;font-weight:700;margin-bottom:8px;';
    const note = document.createElement('div');
    note.innerHTML = 'Yalnızca seçtiğiniz kategorinin otomatik 4 köşe tespiti yeniden çalıştırılır. <b>Kalite algoritması değiştirilmez.</b> Kaynağı değişmemiş insan onaylı <b>APPROVED</b> şablonlar ağır analizden atlanır ve aynen korunur. Onaysız şablonlar mevcut motorla analiz edilir. <b>Arka Planda Sürdür</b> ile diğer şablonlarda çalışabilirsiniz.';
    note.style.cssText = 'font-size:12px;line-height:1.5;color:#93A6C4;margin-bottom:14px;';
    const select = document.createElement('select');
    select.style.cssText = 'width:100%;padding:11px;border-radius:7px;background:#0F1622;color:#fff;border:1px solid #666;font-size:14px;box-sizing:border-box;';
    categories.forEach(cat => {
      const count = state.items.filter(t => t.cat === cat && !t.petek).length;
      const option = document.createElement('option');
      option.value = cat;
      option.textContent = (typeof CATEGORY_LABELS !== 'undefined' && CATEGORY_LABELS[cat]) ? `${CATEGORY_LABELS[cat]} — ${count} şablon` : `${cat} — ${count} şablon`;
      if (state.current && cat === state.current.cat) option.selected = true;
      select.appendChild(option);
    });
    const actions = document.createElement('div');
    actions.style.cssText = 'display:flex;justify-content:flex-end;gap:10px;margin-top:16px;';
    const cancel = document.createElement('button');
    cancel.type = 'button'; cancel.textContent = 'İptal';
    cancel.style.cssText = 'padding:10px 16px;background:#22304A;color:white;border:0;border-radius:7px;cursor:pointer;';
    const confirmButton = document.createElement('button');
    confirmButton.type = 'button'; confirmButton.textContent = '⚡ Bu Kategoriyi Hızlı Tara';
    confirmButton.style.cssText = 'padding:10px 16px;background:#2F6FED;color:white;border:0;border-radius:7px;font-weight:700;cursor:pointer;';
    const finish = value => { overlay.remove(); resolve(value); };
    cancel.onclick = () => finish(null);
    confirmButton.onclick = () => finish(select.value || null);
    overlay.onclick = ev => { if (ev.target === overlay) finish(null); };
    actions.append(cancel, confirmButton);
    dialog.append(title, note, select, actions);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
    setTimeout(() => select.focus(), 0);
  });
}

async function refreshAfterJob() {
  try {
    const response = await fetch('/api/ayarlar', { cache: 'no-store' });
    if (!response.ok) return;
    const fresh = await response.json();
    const petekRows = state.items.filter(t => t.petek);
    state.items = flatten(fresh).concat(petekRows);
    populateCategoryFilter();
    renderRail();
    updateContext();
  } catch (err) {
    console.warn('İş sonrası şablon listesi yenilenemedi:', err);
  }
}

async function monitorBatchAnalyzeJob(jobId, category, totalHint, resumed = false) {
  v6BatchState.running = true;
  v6BatchState.jobId = jobId;
  v6BatchState.category = category;
  v6BatchState.currentTemplate = null;
  v6BatchState.inFlight.clear();
  const button = el('v6BatchAnalyzeButton');
  if (button) { button.disabled = true; button.style.opacity = '0.55'; button.style.cursor = 'wait'; }
  ensureBatchAnalyzeProgressModal();
  if (resumed) setBatchAnalyzeCompact(true);
  el('batchAnalyzeTitle').textContent = resumed ? '↻ Kalıcı tarama devam ediyor' : '⚡ Hızlı kalite-korumalı tarama';
  el('batchAnalyzeClose').style.display = 'none';
  const runActions = el('batchAnalyzeRunActions');
  if (runActions) runActions.style.display = 'flex';
  const stopButton = el('batchAnalyzeStop');
  if (stopButton) { stopButton.disabled = false; stopButton.textContent = '⏹ Taramayı Durdur'; stopButton.style.opacity = '1'; }
  try {
    while (true) {
      const response = await fetch('/api/jobs/' + encodeURIComponent(jobId));
      const data = await response.json();
      if (!response.ok || !data.success || !data.job) throw new Error(data.error || ('HTTP ' + response.status));
      const job = data.job;
      const current = Number(job.progress_current || 0);
      const total = Number(job.progress_total || totalHint || 0);
      updateBatchAnalyzeProgress(current, total, '', job.progress_message || (job.status === 'PENDING' ? 'Kalıcı iş kuyruğunda bekliyor...' : 'Analiz devam ediyor...'));
      const status = String(job.status || '').toUpperCase();
      if (status === 'SUCCEEDED' || status === 'FAILED' || status === 'CANCELLED') {
        const result = job.result || {};
        const stopped = status === 'CANCELLED';
        const failureCount = Number(result.failed_count || 0) + Number(result.source_changed_count || 0);
        const skippedCount = Number(result.missing_count || 0) + Number(result.busy_count || 0);
        if (status === 'FAILED') {
          finishBatchAnalyzeProgress(total, current, Number(result.analyzed_count || 0), Number(result.approved_preserved_count || 0), Math.max(1, failureCount), skippedCount, [job.error_text || 'Kalıcı tarama başarısız.'], false);
        } else {
          finishBatchAnalyzeProgress(total, current, Number(result.analyzed_count || 0), Number(result.approved_preserved_count || 0), failureCount, skippedCount, [], stopped);
          const cacheHits = Number(result.cache_hit_count || 0);
          if (!stopped && cacheHits > 0) {
            el('batchAnalyzeCurrent').textContent += ' • ' + cacheHits + ' şablon SHA256 + analyzer sürüm cache’inden geldi.';
          }
        }
        await refreshAfterJob();
        return job;
      }
      await waitMs(450);
    }
  } catch (err) {
    finishBatchAnalyzeProgress(Number(totalHint || 0), 0, 0, 0, 1, 0, [String(err)], false);
    return null;
  } finally {
    v6BatchState.running = false;
    v6BatchState.stopRequested = false;
    v6BatchState.category = null;
    v6BatchState.currentTemplate = null;
    v6BatchState.inFlight.clear();
    v6BatchState.externalPause = false;
    v6BatchState.jobId = null;
    if (button) { button.disabled = false; button.style.opacity = '1'; button.style.cursor = 'pointer'; }
  }
}

/* ============================================================
 * Ham dosya sağlık taraması + klasör tutarlılığı — legacy raporlar
 * ========================================================== */
function formatTemplateHealthReport(data) {
  const summary = data?.summary || {};
  const lines = [
    'HAM / ÇALIŞMA DOSYASI SAĞLIK TARAMASI',
    data?.saved_at ? 'Kayıt zamanı: ' + data.saved_at : (data?.generated_at ? 'Tarama zamanı: ' + data.generated_at : ''),
    data?.saved_report ? 'Bu rapor son manuel tam taramanın kalıcı kaydıdır.' : '',
    '',
    'Toplam kayıt: ' + Number(summary.total_records || 0),
    'Sağlam: ' + Number(summary.ok || 0),
    'Uyarı / insan kontrolü: ' + Number(summary.warning || 0),
    'Kritik: ' + Number(summary.critical || 0),
    'DB kaydı olmayan çalışma dosyası: ' + Number(summary.filesystem_only_working || 0),
    'DB kaydı olmayan ham yedek: ' + Number(summary.filesystem_only_backup || 0),
    '',
    'NOT: Siyah/beyaz veya çok düz görüntüler otomatik bozuk sayılmaz; ' +
      'yalnız insan kontrolüne işaretlenir. Hiçbir dosya otomatik silinmez.',
    '',
    'SORUNLU / KONTROL EDİLECEK KAYITLAR:'
  ];
  let issueCount = 0;
  const templates = data?.templates || {};
  Object.keys(templates).sort().forEach(cat => {
    Object.keys(templates[cat] || {}).sort().forEach(tmpl => {
      const info = templates[cat][tmpl];
      if (!info || info.severity === 'OK') return;
      issueCount += 1;
      lines.push('[' + info.severity + '] ' + cat + ' / ' + tmpl + ' — ' + (info.label || info.code || 'Kontrol gerekli'));
      (info.details || []).forEach(detail => { lines.push('  • ' + detail); });
    });
  });
  if (issueCount === 0) lines.push('Yok.');
  const diff = data?.diff || {};
  lines.push('', 'ÖNCEKİ SAĞLIK RAPORUNA GÖRE:');
  if (diff.has_previous) {
    lines.push(
      'Önceki kayıt: ' + String(diff.previous_saved_at || ''),
      'Yeni sorun: ' + Number(diff.new_issue_count || 0),
      'Düzelen sorun: ' + Number(diff.resolved_issue_count || 0),
      'Devam eden sorun: ' + Number(diff.unchanged_issue_count || 0));
  } else {
    lines.push('Bu ilk kayıtlı sağlık raporu.');
  }
  const extraWorking = data?.filesystem_only_working || [];
  const extraBackup = data?.filesystem_only_backup || [];
  lines.push('', 'DB KAYDI OLMAYAN ÇALIŞMA DOSYALARI:');
  if (extraWorking.length) extraWorking.forEach(item => { lines.push('  • ' + item.category + ' / ' + item.filename); });
  else lines.push('Yok.');
  lines.push('', 'DB KAYDI OLMAYAN HAM YEDEKLER:');
  if (extraBackup.length) extraBackup.forEach(item => { lines.push('  • ' + item.category + ' / ' + item.filename); });
  else lines.push('Yok.');
  return lines.join('\n');
}

function formatTemplateHealthHistory(data) {
  const rows = Array.isArray(data?.history) ? data.history : [];
  const lines = ['HAM DOSYA SAĞLIK RAPOR GEÇMİŞİ', ''];
  if (!rows.length) { lines.push('Henüz kayıtlı sağlık raporu yok.'); return lines.join('\n'); }
  rows.forEach((row, index) => {
    const diff = row.diff || {};
    lines.push(
      (index + 1) + '. ' + String(row.saved_at || row.file || '') +
      ' | Toplam=' + Number(row.total_records || 0) +
      ' | Sağlam=' + Number(row.ok || 0) +
      ' | Uyarı=' + Number(row.warning || 0) +
      ' | Kritik=' + Number(row.critical || 0) +
      (diff.has_previous ? ' | Yeni=' + Number(diff.new_issue_count || 0) + ' | Düzelen=' + Number(diff.resolved_issue_count || 0) : ''));
  });
  return lines.join('\n');
}

async function monitorHealthScanJob(jobId, showReport = true) {
  v6HealthScanJobId = jobId;
  const button = el('templateHealthScanButton');
  const originalText = button ? button.textContent : '';
  if (button) { button.disabled = true; button.textContent = '⏳ Ham dosyalar kontrol ediliyor...'; }
  try {
    while (true) {
      const response = await fetch('/api/jobs/' + encodeURIComponent(jobId));
      const data = await response.json();
      if (!response.ok || !data.success || !data.job) throw new Error(data.error || ('HTTP ' + response.status));
      const job = data.job;
      const status = String(job.status || '').toUpperCase();
      if (button && job.progress_message) button.textContent = '⏳ ' + job.progress_message;
      if (status === 'SUCCEEDED' || status === 'FAILED' || status === 'CANCELLED') {
        if (status !== 'SUCCEEDED') {
          throw new Error(job.error_text || (status === 'CANCELLED' ? 'Sağlık taraması durduruldu.' : 'Sağlık taraması başarısız.'));
        }
        const savedResponse = await fetch('/api/template-health/last');
        const saved = await savedResponse.json();
        if (!savedResponse.ok || !saved.success) throw new Error(saved.error || 'Kaydedilen sağlık raporu okunamadı.');
        v6HealthSnapshot = saved;
        if (showReport) showCopyableReport(saved.saved_report ? 'Ham Dosya Sağlık Taraması — Kaydedildi' : 'Ham Dosya Sağlık Taraması', formatTemplateHealthReport(saved));
        return saved;
      }
      await waitMs(450);
    }
  } finally {
    v6HealthScanJobId = null;
    if (button) { button.disabled = false; button.textContent = originalText || '🩺 Ham Dosya Sağlık Taraması'; }
  }
}

async function runTemplateHealthScan() {
  if (v6HealthScanJobId) return;
  try {
    const response = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_type: 'RAW_HEALTH_SCAN', payload: {} }),
    });
    const data = await response.json();
    if (!response.ok || !data.success || !data.job) throw new Error(data.error || ('HTTP ' + response.status));
    await monitorHealthScanJob(data.job.id, true);
  } catch (err) {
    showMessage('Ham dosya sağlık taraması başarısız: ' + err.message);
  }
}

async function openLastTemplateHealthReport() {
  const button = el('lastTemplateHealthReportButton');
  const originalText = button ? button.textContent : '';
  if (button) { button.disabled = true; button.textContent = '⏳ Son rapor açılıyor...'; }
  try {
    const response = await fetch('/api/template-health/last');
    const data = await response.json();
    if (!response.ok || !data.success) {
      if (data.code === 'NO_SAVED_HEALTH_REPORT') {
        showMessage('Henüz kaydedilmiş Ham Dosya Sağlık Raporu yok.\n\nÖnce “Ham Dosya Sağlık Taraması” butonuna basın.\nTamamlanan bu manuel tarama bundan sonra kalıcı olarak saklanır.');
        return;
      }
      throw new Error(data.error || ('HTTP ' + response.status));
    }
    showCopyableReport('Son Ham Dosya Sağlık Raporu' + (data.saved_at ? ' — ' + data.saved_at : ''), formatTemplateHealthReport(data));
  } catch (err) {
    showMessage('Son sağlık raporu açılamadı: ' + err.message);
  } finally {
    if (button) { button.disabled = false; button.textContent = originalText || '📄 Son Sağlık Raporunu Aç'; }
  }
}

async function openTemplateHealthHistory() {
  try {
    const response = await fetch('/api/template-health/history?limit=30');
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || ('HTTP ' + response.status));
    showCopyableReport('Ham Dosya Sağlık Rapor Geçmişi', formatTemplateHealthHistory(data));
  } catch (err) {
    showMessage('Sağlık rapor geçmişi açılamadı: ' + err.message);
  }
}

function formatWorkspaceConsistencyReport(data) {
  const summary = data?.summary || {};
  const diff = data?.diff || {};
  const lines = [
    'KLASÖR / DOSYA TUTARLILIK RAPORU — READ ONLY',
    data?.saved_at ? 'Kayıt zamanı: ' + data.saved_at : (data?.generated_at ? 'Tarama zamanı: ' + data.generated_at : ''),
    'Runtime: ' + String(data?.runtime_root || ''),
    '',
    'GÜVENLİK:',
    '• Bu tarama kullanıcı görsellerini silmez, taşımaz, yeniden adlandırmaz veya değiştirmez.',
    '• Aktif eşitlik kuralı: DB ↔ Çalışma ↔ Ham/Orijinal kimliği 1:1 olmalıdır.',
    '• Staging, çöp ve recovery aktif eşitlik kümesine dahil değildir.',
    '',
    'ÖZET:',
    'Aktif DB: ' + Number(summary.active_db_total || 0),
    'Tam eşleşen aktif: ' + Number(summary.fully_matched_active_total || 0),
    'Aktif eşleşme sorunu: ' + Number(summary.active_mismatch_total || 0),
    'Aktif bütünlük bulgusu: ' + Number(summary.active_integrity_issue_count || 0),
    'Çalışma havuzu hijyen bulgusu: ' + Number(summary.working_hygiene_count || 0),
    'Duplicate kimlik bulgusu: ' + Number(summary.duplicate_hygiene_count || 0),
    'Ham arşiv envanter fazlası: ' + Number(summary.archive_inventory_count || 0),
    'Toplam kayıtlı bulgu: ' + Number(summary.issue_count || 0),
    'Kritik: ' + Number(summary.critical_count || 0),
    'Uyarı: ' + Number(summary.warning_count || 0),
    'Bilgi/envanter: ' + Number(summary.info_count || 0),
    'Kaggle görevli klasörü: ' + Number(summary.kaggle_folder_count || 0),
    'Mockup görevli klasörü: ' + Number(summary.mockup_folder_count || 0),
    'Tüm üst seviye klasör: ' + Number(summary.top_level_folder_count || 0),
    'Henüz sınıflandırılmamış üst klasör: ' + Number(summary.unclassified_top_level_count || 0),
    'Çöp dosyası: ' + Number(summary.trash_file_count || 0),
    'Recovery dosyası: ' + Number(summary.recovery_file_count || 0),
    '',
  ];
  if (diff.has_previous) {
    lines.push('ÖNCEKİ RAPORA GÖRE:', 'Önceki kayıt: ' + String(diff.previous_saved_at || ''), 'Yeni sorun: ' + Number(diff.new_issue_count || 0), 'Düzelen sorun: ' + Number(diff.resolved_issue_count || 0), 'Devam eden sorun: ' + Number(diff.unchanged_issue_count || 0), '');
  } else {
    lines.push('ÖNCEKİ RAPORA GÖRE:', 'Bu ilk kayıtlı tutarlılık raporu.', '');
  }
  lines.push('KATEGORİLER:');
  Object.keys(data?.categories || {}).sort().forEach(cat => {
    const row = data.categories[cat] || {};
    lines.push('• ' + cat + ' | DB=' + Number(row.db_count || 0) + ' | Çalışma=' + Number(row.working_identity_count || 0) + ' | Ham=' + Number(row.backup_identity_count || 0) + ' | Staging=' + Number(row.staging_identity_count || 0) + ' | Tam=' + Number(row.fully_matched_active_count || 0) + ' | AktifSorun=' + Number(row.active_integrity_issue_count || 0) + ' | ArşivEkstra=' + Number(row.archive_inventory_count || 0) + ' | Hijyen=' + (Number(row.working_hygiene_count || 0) + Number(row.duplicate_hygiene_count || 0)));
  });
  lines.push('', 'KLASÖR GÖREV / REFERANS AUDİTİ:');
  (data?.folders || []).forEach(row => {
    const inv = row.inventory || {};
    lines.push('• ' + row.folder + ' [' + row.role + ']' + ' | var=' + (row.exists ? 'EVET' : 'HAYIR') + ' | dosya=' + Number(inv.file_count || 0) + ' | görsel=' + Number(inv.image_count || 0) + ' | aktif-kod-ref=' + Number(row.runtime_code_reference_count || 0) + ' | tüm-ref=' + Number(row.code_reference_count || 0));
    lines.push('  Görev: ' + String(row.expected_contract || ''));
    if ((row.runtime_code_reference_files || []).length) lines.push('  Aktif kod örnekleri: ' + row.runtime_code_reference_files.join(', '));
  });
  lines.push('', 'KAGGLE KLASÖRLERİ:');
  if ((data?.kaggle_folders || []).length) data.kaggle_folders.forEach(row => { lines.push('• ' + row.folder + ' [' + String(row.role || '') + ']' + ' | dosya=' + Number(row.inventory?.file_count || 0) + ' | aktif-kod-ref=' + Number(row.runtime_code_reference_count || 0)); });
  else lines.push('Bulunamadı.');
  lines.push('', 'MOCKUP KLASÖRLERİ:');
  if ((data?.mockup_folders || []).length) data.mockup_folders.forEach(row => { lines.push('• ' + row.folder + ' [' + String(row.role || '') + ']' + ' | dosya=' + Number(row.inventory?.file_count || 0) + ' | aktif-kod-ref=' + Number(row.runtime_code_reference_count || 0)); });
  else lines.push('Bulunamadı.');
  lines.push('', 'AKTİF BÜTÜNLÜK / HİJYEN / ENVANTER BULGULARI:');
  const issues = Array.isArray(data?.issues) ? data.issues : [];
  if (!issues.length) lines.push('Yok.');
  else issues.forEach(item => {
    lines.push('[' + String(item.severity || 'INFO') + ' / ' + String(item.scope || 'GENEL') + '] ' + String(item.category || '-') + ' / ' + String(item.identity || '-') + ' — ' + String(item.label || item.code || ''));
    if (item.details) lines.push('  ' + String(item.details));
  });
  lines.push('', 'NOT: Bu rapor düzeltme yapmaz. Eşitleme işlemleri ayrıca ve geri alınabilir olarak yapılır.');
  return lines.join('\n');
}

function formatWorkspaceHistory(data) {
  const rows = Array.isArray(data?.history) ? data.history : [];
  const lines = ['KLASÖR TUTARLILIK RAPOR GEÇMİŞİ', ''];
  if (!rows.length) { lines.push('Henüz kayıtlı rapor yok.'); return lines.join('\n'); }
  rows.forEach((row, index) => {
    lines.push((index + 1) + '. ' + String(row.saved_at || row.generated_at || row.file || '') + ' | Aktif=' + Number(row.active_db_total || 0) + ' | Tam=' + Number(row.fully_matched_active_total || 0) + ' | AktifSorun=' + Number(row.active_integrity_issue_count || 0) + ' | Arşiv=' + Number(row.archive_inventory_count || 0) + ' | Hijyen=' + (Number(row.working_hygiene_count || 0) + Number(row.duplicate_hygiene_count || 0)) + ' | Kaggle=' + Number(row.kaggle_folder_count || 0) + ' | Mockup=' + Number(row.mockup_folder_count || 0) + ' | Sınıfsız=' + Number(row.unclassified_top_level_count || 0));
  });
  return lines.join('\n');
}

async function loadLastWorkspaceConsistency(render = true) {
  try {
    const response = await fetch('/api/workspace-consistency/last');
    const data = await response.json();
    if (!response.ok || !data.success) {
      if (data.code === 'NO_SAVED_WORKSPACE_REPORT') return null;
      throw new Error(data.error || ('HTTP ' + response.status));
    }
    v6WorkspaceSnapshot = data;
    if (render) refreshRailDots();
    return data;
  } catch (err) {
    console.warn('Son klasör tutarlılık raporu yüklenemedi:', err);
    return null;
  }
}

function getTemplateHealth(cat, tmpl) {
  return (v6HealthSnapshot && v6HealthSnapshot.templates && v6HealthSnapshot.templates[cat] && v6HealthSnapshot.templates[cat][tmpl]) || null;
}

function getWorkspaceTemplateState(cat, tmpl) {
  return (v6WorkspaceSnapshot && v6WorkspaceSnapshot.templates && v6WorkspaceSnapshot.templates[cat] && v6WorkspaceSnapshot.templates[cat][tmpl]) || null;
}

function refreshRailDots() {
  // Sağlık/tutarlılık anlık görüntüsü güncellendiğinde satır rozetlerini tazele.
  try { renderRail(); } catch (_) { /* rail henüz hazır değil */ }
}

function ensureWorkspaceAuditProgress() {
  let card = el('workspace-audit-progress');
  if (card) return card;
  card = document.createElement('div');
  card.id = 'workspace-audit-progress';
  card.style.cssText = ['position:fixed', 'right:18px', 'bottom:18px', 'z-index:22000', 'width:min(430px,calc(100vw - 36px))', 'background:#131C2B', 'color:#fff', 'border:1px solid #555', 'border-radius:10px', 'padding:14px', 'box-shadow:0 12px 40px rgba(0,0,0,.45)', 'display:none'].join(';');
  card.innerHTML = `
    <div style="font-weight:700;margin-bottom:8px;">🧭 Klasör Tutarlılık Taraması</div>
    <div id="workspace-audit-message" style="font-size:12px;color:#ddd;margin-bottom:8px;">Hazırlanıyor...</div>
    <div style="height:14px;background:#182238;border-radius:999px;overflow:hidden;">
      <div id="workspace-audit-bar" style="height:100%;width:0%;background:#17D3A3;transition:width .2s ease;"></div>
    </div>
    <div id="workspace-audit-count" style="font-size:11px;color:#bbb;margin-top:6px;">0 / 8</div>
    <div style="display:flex;gap:8px;margin-top:10px;">
      <button type="button" id="workspace-audit-stop" style="flex:1;padding:8px;background:#A94442;color:white;border:0;border-radius:6px;cursor:pointer;">⏹ Durdur</button>
      <button type="button" id="workspace-audit-hide" style="flex:1;padding:8px;background:#182238;color:white;border:0;border-radius:6px;cursor:pointer;">↘ Gizle</button>
    </div>`;
  document.body.appendChild(card);
  card.querySelector('#workspace-audit-hide').onclick = () => { card.style.display = 'none'; };
  card.querySelector('#workspace-audit-stop').onclick = async () => {
    if (!v6WorkspaceAuditJobId) return;
    const stop = card.querySelector('#workspace-audit-stop');
    stop.disabled = true;
    stop.textContent = '⏳ Durduruluyor...';
    try { await fetch('/api/jobs/' + encodeURIComponent(v6WorkspaceAuditJobId) + '/stop', { method: 'POST' }); }
    catch (err) { console.warn('Audit stop isteği gönderilemedi:', err); }
  };
  return card;
}

function updateWorkspaceAuditProgress(job) {
  const card = ensureWorkspaceAuditProgress();
  const current = Number(job?.progress_current || 0);
  const total = Math.max(1, Number(job?.progress_total || 8));
  const percent = Math.max(0, Math.min(100, Math.round((current / total) * 100)));
  card.querySelector('#workspace-audit-bar').style.width = percent + '%';
  card.querySelector('#workspace-audit-count').textContent = current + ' / ' + total + ' — %' + percent;
  card.querySelector('#workspace-audit-message').textContent = job?.progress_message || 'Read-only tarama devam ediyor...';
  card.style.display = 'block';
}

async function monitorWorkspaceAuditJob(jobId, showReport = true) {
  v6WorkspaceAuditJobId = jobId;
  const button = el('workspaceConsistencyScanButton');
  const originalText = button ? button.textContent : '';
  if (button) { button.disabled = true; button.textContent = '⏳ Tutarlılık taranıyor...'; }
  try {
    while (true) {
      const response = await fetch('/api/jobs/' + encodeURIComponent(jobId));
      const data = await response.json();
      if (!response.ok || !data.success || !data.job) throw new Error(data.error || ('HTTP ' + response.status));
      const job = data.job;
      updateWorkspaceAuditProgress(job);
      const status = String(job.status || '').toUpperCase();
      if (status === 'SUCCEEDED' || status === 'FAILED' || status === 'CANCELLED') {
        const card = ensureWorkspaceAuditProgress();
        const stop = card.querySelector('#workspace-audit-stop');
        if (stop) {
          stop.disabled = true;
          stop.textContent = status === 'SUCCEEDED' ? '✅ Tamamlandı' : (status === 'CANCELLED' ? '⏹ Durduruldu' : '⛔ Hata');
        }
        if (status !== 'SUCCEEDED') throw new Error(job.error_text || (status === 'CANCELLED' ? 'Tutarlılık taraması durduruldu.' : 'Tutarlılık taraması başarısız.'));
        const saved = await loadLastWorkspaceConsistency(false);
        if (!saved) throw new Error('Kaydedilmiş tutarlılık raporu okunamadı.');
        v6WorkspaceSnapshot = saved;
        if (showReport) showCopyableReport('Klasör Tutarlılık Raporu — READ ONLY', formatWorkspaceConsistencyReport(saved));
        return saved;
      }
      await waitMs(400);
    }
  } finally {
    v6WorkspaceAuditJobId = null;
    if (button) { button.disabled = false; button.textContent = originalText || '🧭 Klasör Tutarlılık Taraması'; }
  }
}

async function runWorkspaceConsistencyScan() {
  if (v6WorkspaceAuditJobId) { ensureWorkspaceAuditProgress().style.display = 'block'; return; }
  const ok = confirm(
    'Klasör Tutarlılık Doktoru yalnızca okuyacak.\n\n' +
    'DB, çalışma, ham yedek, staging, çöp, recovery, Kaggle ve Mockup ' +
    'klasörleri denetlenecek.\n\n' +
    'Hiçbir görsel silinmeyecek, taşınmayacak, yeniden adlandırılmayacak ' +
    'veya değiştirilmeyecek. Yalnız rapor kaydı oluşturulacak.\n\n' +
    'Tarama başlatılsın mı?');
  if (!ok) return;
  try {
    const response = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_type: 'WORKSPACE_CONSISTENCY_SCAN', payload: {} }),
    });
    const data = await response.json();
    if (!response.ok || !data.success || !data.job) throw new Error(data.error || ('HTTP ' + response.status));
    await monitorWorkspaceAuditJob(data.job.id, true);
  } catch (err) {
    showMessage('Klasör Tutarlılık Taraması başarısız: ' + err.message);
  }
}

async function openLastWorkspaceConsistencyReport() {
  const data = await loadLastWorkspaceConsistency(false);
  if (!data) {
    showMessage('Henüz kayıtlı Klasör Tutarlılık Raporu yok. Önce “Klasör Tutarlılık Taraması” çalıştırın.');
    return;
  }
  showCopyableReport('Son Klasör Tutarlılık Raporu' + (data.saved_at ? ' — ' + data.saved_at : ''), formatWorkspaceConsistencyReport(data));
}

async function openWorkspaceConsistencyHistory() {
  try {
    const response = await fetch('/api/workspace-consistency/history?limit=30');
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || ('HTTP ' + response.status));
    showCopyableReport('Klasör Tutarlılık Rapor Geçmişi', formatWorkspaceHistory(data));
  } catch (err) {
    showMessage('Tutarlılık rapor geçmişi açılamadı: ' + err.message);
  }
}

async function refreshTemplateHealth(deep = false, showReport = false, persist = false) {
  try {
    const response = await fetch('/api/template-health?deep=' + (deep ? '1' : '0') + '&save=' + (persist ? '1' : '0'));
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || ('HTTP ' + response.status));
    v6HealthSnapshot = data;
    if (showReport) showCopyableReport(data.saved_report ? 'Ham Dosya Sağlık Taraması — Kaydedildi' : 'Ham Dosya Sağlık Taraması', formatTemplateHealthReport(data));
    return data;
  } catch (err) {
    if (showReport) showMessage('Ham dosya sağlık taraması başarısız: ' + err.message);
    return null;
  }
}

/* ============================================================
 * Lifecycle / Güvenli Eşitleme Merkezi — legacy reconciliation
 * ========================================================== */
function formatLifecycleFileEvidence(item) {
  const dims = (item?.width && item?.height ? String(item.width) + 'x' + String(item.height) : 'boyut-okunamadı');
  const alpha = item?.has_alpha
    ? ('alpha=' + String(item.alpha_min ?? '?') + '..' + String(item.alpha_max ?? '?'))
    : 'alpha=YOK';
  return [
    String(item?.name || ''),
    'bytes=' + Number(item?.size_bytes || 0),
    'piksel=' + dims,
    'kanal=' + String(item?.channels ?? '?'),
    alpha,
    'SHA256=' + String(item?.sha256 || ''),
    'PIXEL_SHA256=' + String(item?.decoded_pixel_sha256 || 'OKUNAMADI'),
    'mtime=' + String(item?.modified_at || '')
  ].join(' | ');
}

function formatLifecycleCenter(data, focus = 'all') {
  const summary = data?.summary || {};
  const lines = [
    'GÜVENLİ EŞİTLEME / TRASH / RECOVERY MERKEZİ',
    'Tarama: ' + String(data?.generated_at || ''),
    'Runtime: ' + String(data?.runtime_root || ''),
    '',
    'GÜVENLİK POLİTİKASI:',
    '• Kalıcı otomatik silme: KAPALI',
    '• Duplicate çözümü: silmek yerine recovery alanına taşı',
    '• Çalışma yetimi: yalnız kullanıcı onayıyla recovery alanına taşı',
    '• Ham dosya değişimi: eski ham + eski çalışma bytes recovery kaydında korunur',
    '',
    'ÖZET:',
    'Duplicate kimlik: ' + Number(summary.duplicate_identity_count || 0),
    'Güvenli önerisi olan duplicate: ' + Number(summary.safe_duplicate_count || 0),
    'Elle seçim gerektiren duplicate: ' + Number(summary.manual_duplicate_count || 0),
    'Çalışma yetimi: ' + Number(summary.working_orphan_count || 0),
    'Aktif ama dosyası eksik kayıt: ' + Number(summary.active_missing_count || 0),
    'Geri alınabilir çöp kaydı: ' + Number(summary.trash_record_count || 0),
    'Lifecycle recovery operasyonu: ' + Number(summary.lifecycle_recovery_count || 0),
    '.processing recovery dosyası: ' + Number(summary.processing_recovery_count || 0),
    'Staging transaction kaydı: ' + Number(summary.staging_transaction_count || 0),
    'İnsan incelemesi isteyen staging transaction: ' + Number(summary.staging_recovery_required_count || 0),
    '',
  ];
  if (focus !== 'recovery') {
    lines.push('DUPLICATE KİMLİKLER:');
    const duplicates = Array.isArray(data?.duplicates) ? data.duplicates : [];
    if (!duplicates.length) lines.push('Yok.');
    else duplicates.forEach(row => {
      lines.push('• [' + String(row.area || '') + '] ' + String(row.category || '') + ' / ' + String(row.identity || ''));
      lines.push('  Dosyalar:');
      (row.files || []).forEach(item => { lines.push('    - ' + formatLifecycleFileEvidence(item)); });
      lines.push('  Byte olarak aynı: ' + (row.byte_equivalent ? 'EVET' : 'HAYIR'));
      lines.push('  Decode edilmiş piksel olarak aynı: ' + (row.pixel_equivalent ? 'EVET' : 'HAYIR'));
      lines.push('  Aktif DB dosyası: ' + String(row.active_template || 'YOK'));
      lines.push('  Güvenli koruma önerisi: ' + String(row.recommended_keep || 'ELLE SEÇİM GEREKİYOR'));
      if (row.manual_choice_reason) lines.push('  İnceleme nedeni: ' + String(row.manual_choice_reason));
    });
    lines.push('', 'ÇALIŞMA HAVUZU YETİMLERİ:');
    const workingOrphans = Array.isArray(data?.working_orphans) ? data.working_orphans : [];
    if (!workingOrphans.length) lines.push('Yok.');
    else workingOrphans.forEach(row => {
      lines.push('• ' + row.category + ' / ' + row.identity);
      (row.files || []).forEach(item => { lines.push('    - ' + formatLifecycleFileEvidence(item)); });
    });
    lines.push('', 'AKTİF DB AMA DOSYA EKSİK:');
    const activeMissing = Array.isArray(data?.active_missing) ? data.active_missing : [];
    if (!activeMissing.length) lines.push('Yok.');
    else activeMissing.forEach(row => {
      lines.push('• ' + row.category + ' / ' + row.template + ' | çalışma=' + (row.working_exists ? 'VAR' : 'YOK') + ' | ham=' + (row.backup_exists ? 'VAR' : 'YOK') + ' | öneri=' + String(row.recommended_action || ''));
    });
  }
  lines.push('', 'SON ÇÖP KAYITLARI:');
  const trash = Array.isArray(data?.trash_records) ? data.trash_records : [];
  if (!trash.length) lines.push('Yok.');
  else trash.slice(0, 20).forEach(row => {
    lines.push('• ' + String(row.created_at || '') + ' — ' + String(row.category || '') + ' / ' + String(row.template || '') + (row.source_was_missing ? ' [DOSYA ZATEN EKSİKTİ]' : ''));
  });
  lines.push('', 'SON LIFECYCLE RECOVERY OPERASYONLARI:');
  const recovery = Array.isArray(data?.lifecycle_recovery) ? data.lifecycle_recovery : [];
  if (!recovery.length) lines.push('Yok.');
  else recovery.slice(0, 20).forEach(row => {
    lines.push('• ' + String(row.created_at || '') + ' | ' + String(row.kind || '') + ' | ' + String(row.state || '') + ' | ' + String(row.category || '') + ' / ' + String(row.identity || row.template || '') + ' | geri alınabilir=' + (row.undo_supported ? 'EVET' : 'HAYIR') + ' | taşınan=' + Number(row.moved_count || 0) + ' | id=' + String(row.operation_id || ''));
  });
  lines.push('', '.PROCESSING RECOVERY:');
  const processing = Array.isArray(data?.processing_recovery) ? data.processing_recovery : [];
  if (!processing.length) lines.push('Yok.');
  else processing.slice(0, 20).forEach(row => { lines.push('• ' + String(row.relative_path || '') + ' | bytes=' + Number(row.size_bytes || 0)); });
  lines.push('', 'STAGING TRANSACTION JOURNALLARI:');
  const txns = Array.isArray(data?.staging_transactions) ? data.staging_transactions : [];
  if (!txns.length) lines.push('Yok.');
  else txns.slice(0, 30).forEach(row => {
    lines.push('• ' + String(row.updated_at || row.created_at || '') + ' | ' + String(row.state || '') + ' | ' + String(row.category || '') + ' / ' + String(row.canonical_name || '-') + ' | id=' + String(row.transaction_id || ''));
    if (row.error) lines.push('  Hata: ' + String(row.error));
  });
  lines.push('', 'NOT: Bu merkez kendi kendine toplu düzeltme yapmaz. Riskli aksiyonlar ayrıca kullanıcı onayı ister.');
  return lines.join('\n');
}

async function fetchLifecycleCenter() {
  const response = await fetch('/api/lifecycle/center?limit=100');
  const data = await response.json();
  if (!response.ok || !data.success) throw new Error(data.error || ('HTTP ' + response.status));
  return data;
}

async function openLifecycleCenter(focus = 'all') {
  try {
    const data = await fetchLifecycleCenter();
    showCopyableReport(focus === 'recovery' ? 'Trash / Recovery Merkezi' : 'Güvenli Eşitleme Merkezi', formatLifecycleCenter(data, focus));
  } catch (err) {
    showMessage('Lifecycle merkezi açılamadı: ' + err.message, 'Lifecycle Merkezi Hatası');
  }
}

function closeReconciliationCenter() {
  const overlay = el('reconciliation-center-overlay');
  if (overlay) overlay.style.display = 'none';
}

function reconciliationButton(label, handler, danger = false) {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = label;
  button.style.cssText = 'padding:8px 10px;border:0;border-radius:5px;cursor:pointer;font-weight:bold;margin-left:6px;background:' + (danger ? '#A94442' : '#2F6FED') + ';color:white;';
  button.onclick = handler;
  return button;
}

function reconciliationRow(title, details, severity = 'normal') {
  const row = document.createElement('div');
  row.className = 'reconciliation-row';
  const border = severity === 'critical' ? '#A94442' : (severity === 'warning' ? '#C88A2D' : '#22304A');
  row.style.cssText = 'border:1px solid ' + border + ';border-radius:7px;padding:10px;margin:8px 0;background:#0F1622;';
  const head = document.createElement('div');
  head.style.cssText = 'font-weight:bold;color:#fff;margin-bottom:5px;word-break:break-word;';
  head.textContent = title;
  row.appendChild(head);
  const info = document.createElement('div');
  info.style.cssText = 'white-space:pre-wrap;color:#93A6C4;font-size:12px;line-height:1.45;word-break:break-word;';
  info.textContent = details;
  row.appendChild(info);
  const actions = document.createElement('div');
  actions.className = 'reconciliation-actions';
  actions.style.cssText = 'display:flex;justify-content:flex-end;gap:4px;flex-wrap:wrap;margin-top:8px;';
  row.appendChild(actions);
  return { row, actions };
}

async function refreshSettingsAfterReconciliation() {
  await refreshAfterJob();
  refreshTemplateHealth(false, false);
  await loadLastWorkspaceConsistency(false);
}

async function reconciliationPost(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });
  const data = await response.json();
  if (!response.ok || !data.success) throw new Error(data.error || ('HTTP ' + response.status));
  return data;
}

async function restoreWorkingFromBackupRow(row) {
  const category = String(row.category || '');
  const template = String(row.template || '');
  if (!confirm('Çalışma kopyası ham/orijinal yedekten geri oluşturulacak.\n\n' + category + ' / ' + template + '\n\nBu işlem ham yedeki değiştirmez. Önceki onay yeniden kontrol gerektirebilir. Devam edilsin mi?')) return false;
  const response = await fetch('/api/orijinal_yukle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Active-Category': category, 'X-Active-Template': template },
  });
  const data = await response.json();
  if (!response.ok || !data.success) throw new Error(data.error || ('HTTP ' + response.status));
  showCopyableReport('Çalışma Kopyası Geri Yüklendi', [
    'Şablon: ' + category + ' / ' + template,
    'Ham kaynak: ' + String(data.backup_source_absolute || ''),
    'Çalışma hedef: ' + String(data.destination_absolute || ''),
    'SHA256: ' + String(data.destination_after_sha256 || ''),
    'PNG byte-exact: ' + (data.png_byte_exact_restore ? 'EVET' : 'HAYIR'),
    'Onay yeniden kontrol gerekli: EVET'
  ].join('\n'));
  return true;
}

function goToReconciliationTemplate(category, template) {
  closeReconciliationCenter();
  refreshSettingsAfterReconciliation().then(() => {
    const index = state.items.findIndex(t => t.cat === category && t.filename === template);
    if (index < 0) {
      showMessage('Şablon aktif listede bulunamadı: ' + category + ' / ' + template, 'Şablona Git');
      return;
    }
    selectIndex(index);
  });
}

async function runReconciliationAction(action, row) {
  try {
    if (action === 'DUPLICATE') {
      const movedNames = (row.files || []).map(item => item.name).filter(name => name !== row.recommended_keep);
      if (!confirm('Duplicate varyant KALICI SİLİNMEYECEK.\n\n' + row.category + ' / ' + row.identity + '\nAlan: ' + row.area + '\nKorunacak: ' + row.recommended_keep + '\nRecovery’ye taşınacak: ' + movedNames.join(', ') + '\n\nDevam edilsin mi?')) return;
      const data = await reconciliationPost('/api/lifecycle/resolve-duplicate', {
        area: row.area, category: row.category, identity: row.identity,
        keep_filename: row.recommended_keep, template: row.active_template || row.recommended_keep,
      });
      showCopyableReport('Duplicate Güvenle Ayrıldı', [
        'Operasyon: ' + String(data.operation?.operation_id || ''),
        'Kategori: ' + row.category, 'Kimlik: ' + row.identity, 'Korunan: ' + row.recommended_keep, 'Recovery’ye taşınan:',
        ...(data.operation?.moved || []).map(item => '• ' + item.name + ' | SHA256=' + item.sha256)
      ].join('\n'));
    } else if (action === 'WORKING_ORPHAN') {
      if (!confirm('Bu dosyanın aktif DB kaydı yok.\n\n' + row.category + ' / ' + row.identity + '\n\nDosya KALICI SİLİNMEYECEK; lifecycle recovery alanına taşınacak. Devam edilsin mi?')) return;
      const data = await reconciliationPost('/api/lifecycle/archive-working-orphan', { category: row.category, identity: row.identity });
      showCopyableReport('Çalışma Yetimi Recovery’ye Alındı', [
        'Operasyon: ' + String(data.operation?.operation_id || ''),
        'Kategori: ' + row.category, 'Kimlik: ' + row.identity, 'Taşınan:',
        ...(data.operation?.moved || []).map(item => '• ' + item.name + ' | SHA256=' + item.sha256)
      ].join('\n'));
    } else if (action === 'RETIRE_DB_ORPHAN') {
      if (!confirm('Bu aktif DB kaydının ne çalışma ne de ham dosyası var.\n\n' + row.category + ' / ' + row.template + '\n\nDB kaydı aktif listeden çıkarılıp geri alınabilir çöp metası oluşturulacak. Kalıcı numara geçmişi korunacak.\n\nDevam edilsin mi?')) return;
      const data = await reconciliationPost('/api/lifecycle/retire-db-orphan', { category: row.category, template: row.template });
      showCopyableReport('DB Yetimi Güvenle Retire Edildi', [
        'Kategori: ' + row.category, 'Şablon: ' + row.template, 'Çöp kaydı: ' + String(data.trash_record || ''),
        'Kaynak zaten eksikti: ' + (data.source_was_missing ? 'EVET' : 'HAYIR'), 'Numara geçmişi: KORUNDU', 'Geri alınabilir: EVET'
      ].join('\n'));
    } else if (action === 'RESTORE_WORKING') {
      await restoreWorkingFromBackupRow(row);
    } else {
      throw new Error('Bilinmeyen reconciliation aksiyonu.');
    }
    await refreshSettingsAfterReconciliation();
    await openActionableReconciliationCenter();
  } catch (err) {
    showMessage('Güvenli eşitleme işlemi başarısız: ' + err.message, 'Güvenli Eşitleme Hatası');
  }
}

async function openActionableReconciliationCenter() {
  try {
    const data = await fetchLifecycleCenter();
    let overlay = el('reconciliation-center-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'reconciliation-center-overlay';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:100000;display:none;align-items:center;justify-content:center;padding:20px;';
      overlay.innerHTML =
        '<div id="reconciliation-center-dialog" style="width:min(1050px,96vw);max-height:90vh;overflow:auto;background:#131C2B;border:1px solid #22304A;border-radius:10px;padding:16px;color:white;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;position:sticky;top:0;background:#131C2B;padding-bottom:10px;z-index:2;">' +
        '<div><div style="font-size:18px;font-weight:bold;">🧭 Güvenli Eşitleme Merkezi</div>' +
        '<div id="reconciliation-summary" style="font-size:12px;color:#93A6C4;margin-top:3px;"></div></div>' +
        '<div style="display:flex;gap:6px;">' +
        '<button type="button" id="reconciliation-copy-report" style="padding:8px;">📋 Raporu Aç</button>' +
        '<button type="button" id="reconciliation-close" style="padding:8px;">Kapat</button>' +
        '</div></div><div id="reconciliation-content"></div></div>';
      document.body.appendChild(overlay);
      overlay.querySelector('#reconciliation-close').onclick = closeReconciliationCenter;
      overlay.addEventListener('click', ev => { if (ev.target === overlay) closeReconciliationCenter(); });
    }
    const summary = data.summary || {};
    overlay.querySelector('#reconciliation-summary').textContent =
      'Duplicate=' + Number(summary.duplicate_identity_count || 0) +
      ' | Çalışma yetimi=' + Number(summary.working_orphan_count || 0) +
      ' | Aktif dosya eksiği=' + Number(summary.active_missing_count || 0) +
      ' | Kalıcı otomatik silme=KAPALI';
    overlay.querySelector('#reconciliation-copy-report').onclick = () => showCopyableReport('Güvenli Eşitleme Merkezi — Tam Rapor', formatLifecycleCenter(data, 'all'));
    const content = overlay.querySelector('#reconciliation-content');
    content.innerHTML = '';
    const intro = document.createElement('div');
    intro.style.cssText = 'padding:9px;border-radius:6px;background:#0F1622;color:#93A6C4;font-size:12px;line-height:1.5;margin-bottom:10px;';
    intro.textContent = 'Her sorun tek tek çözülür. “Hepsini düzelt” yoktur. Dosya taşıyan işlemler kalıcı silme yapmaz; recovery kaydı oluşturur.';
    content.appendChild(intro);
    const addSection = title => {
      const h = document.createElement('h3');
      h.textContent = title;
      h.style.cssText = 'margin:15px 0 6px;color:#E9EFF9;font-size:14px;';
      content.appendChild(h);
    };
    addSection('1) Duplicate Kimlikler');
    const duplicates = data.duplicates || [];
    if (!duplicates.length) {
      const empty = document.createElement('div');
      empty.textContent = '✅ Duplicate kimlik yok.'; empty.style.color = '#7BE3A8';
      content.appendChild(empty);
    }
    duplicates.forEach(row => {
      const files = (row.files || []).map(item => formatLifecycleFileEvidence(item)).join('\n');
      const item = reconciliationRow('[' + row.area + '] ' + row.category + ' / ' + row.identity,
        'Dosyalar:\n' + files + '\nAktif DB dosyası: ' + String(row.active_template || 'YOK') +
        '\nByte olarak aynı: ' + (row.byte_equivalent ? 'EVET' : 'HAYIR') +
        '\nPiksel olarak aynı: ' + (row.pixel_equivalent ? 'EVET' : 'HAYIR') +
        '\nKoruma önerisi: ' + String(row.recommended_keep || 'GÜVENLİ OTOMATİK SEÇİM YOK') +
        (row.manual_choice_reason ? '\nİnceleme nedeni: ' + String(row.manual_choice_reason) : ''),
        row.safe_recommendation ? 'warning' : 'critical');
      if (row.safe_recommendation && row.recommended_keep) {
        item.actions.appendChild(reconciliationButton('Recovery’ye Ayır', () => runReconciliationAction('DUPLICATE', row)));
      } else {
        const note = document.createElement('span');
        note.textContent = '⛔ Otomatik seçim yapılmadı; dosyalara dokunulmayacak.';
        note.style.cssText = 'color:#fca5a5;font-size:12px;';
        item.actions.appendChild(note);
      }
      content.appendChild(item.row);
    });
    addSection('2) DB Dışı Çalışma Dosyaları');
    const orphans = data.working_orphans || [];
    if (!orphans.length) {
      const empty = document.createElement('div');
      empty.textContent = '✅ Çalışma yetimi yok.'; empty.style.color = '#7BE3A8';
      content.appendChild(empty);
    }
    orphans.forEach(row => {
      const item = reconciliationRow(row.category + ' / ' + row.identity,
        'Aktif DB kaydı yok.\nDosyalar:\n' + (row.files || []).map(file => formatLifecycleFileEvidence(file)).join('\n'), 'warning');
      item.actions.appendChild(reconciliationButton('Recovery’ye Al', () => runReconciliationAction('WORKING_ORPHAN', row)));
      content.appendChild(item.row);
    });
    addSection('3) Aktif DB / Dosya Eksikleri');
    const missing = data.active_missing || [];
    if (!missing.length) {
      const empty = document.createElement('div');
      empty.textContent = '✅ Aktif DB kayıtlarında dosya eksiği yok.'; empty.style.color = '#7BE3A8';
      content.appendChild(empty);
    }
    missing.forEach(row => {
      const item = reconciliationRow(row.category + ' / ' + row.template,
        'Çalışma: ' + (row.working_exists ? 'VAR' : 'YOK') + '\nHam: ' + (row.backup_exists ? 'VAR' : 'YOK') + '\nÖneri: ' + String(row.recommended_action || ''), 'critical');
      if (row.recommended_action === 'RETIRE_DB_ORPHAN') {
        item.actions.appendChild(reconciliationButton('DB Yetimini Retire Et', () => runReconciliationAction('RETIRE_DB_ORPHAN', row), true));
      } else if (row.recommended_action === 'RESTORE_WORKING_FROM_BACKUP') {
        item.actions.appendChild(reconciliationButton('Hamdan Çalışmayı Geri Yükle', () => runReconciliationAction('RESTORE_WORKING', row)));
      } else if (row.recommended_action === 'REPLACE_ORIGINAL_REQUIRED') {
        item.actions.appendChild(reconciliationButton('Şablona Git / Yeni Ham Seç', () => goToReconciliationTemplate(row.category, row.template)));
      }
      content.appendChild(item.row);
    });
    overlay.style.display = 'flex';
  } catch (err) {
    showMessage('Güvenli Eşitleme Merkezi açılamadı: ' + err.message, 'Güvenli Eşitleme Hatası');
  }
}

async function resolveCurrentTemplateDuplicates() {
  const t = state.current;
  if (!t || t.petek) { showMessage('Önce soldan bir şablon seçin.'); return; }
  if (blockIfCurrentBatchTemplate(t.cat, t.filename, 'Duplicate çözme')) return;
  try {
    const center = await fetchLifecycleCenter();
    const identity = t.filename.replace(/\.[^.]+$/, '').toLowerCase();
    const rows = (center.duplicates || []).filter(row => row.category === t.cat && String(row.identity || '').toLowerCase() === identity);
    if (!rows.length) { showMessage('Bu aktif şablon için duplicate kimlik bulunmadı.', 'Duplicate Kontrolü'); return; }
    const safeRows = rows.filter(row => row.safe_recommendation && row.recommended_keep);
    const manualRows = rows.filter(row => !row.safe_recommendation);
    if (!safeRows.length) { showCopyableReport('Duplicate — Elle İnceleme Gerekli', formatLifecycleCenter(center, 'all')); return; }
    const planText = safeRows.map(row => '[' + row.area + '] ' + row.category + ' / ' + row.identity + '\nKorunacak: ' + row.recommended_keep + '\nRecovery’ye taşınacak: ' + (row.files || []).map(item => item.name).filter(name => name !== row.recommended_keep).join(', ')).join('\n\n');
    if (!confirm('Duplicate dosyalar KALICI SİLİNMEYECEK.\n\n' + planText + '\n\nDiğer varyantlar recovery alanına taşınsın mı?')) return;
    const results = [];
    for (const row of safeRows) {
      const response = await fetch('/api/lifecycle/resolve-duplicate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ area: row.area, category: row.category, identity: row.identity, keep_filename: row.recommended_keep, template: t.filename }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error('[' + row.area + '] ' + (data.error || ('HTTP ' + response.status)));
      results.push(data.operation);
    }
    showCopyableReport('Duplicate Çözümü Tamamlandı',
      results.map(op => 'Operasyon: ' + String(op.operation_id || '') + '\nAlan: ' + String(op.area || '') + '\nKorunan: ' + String(op.keep_filename || '') + '\nRecovery’ye taşınan: ' + (op.moved || []).map(item => item.name).join(', ')).join('\n\n') +
      (manualRows.length ? '\n\nNot: ' + manualRows.length + ' duplicate kümesi güvenli otomatik seçim yapılamadığı için dokunulmadan bırakıldı.' : ''));
    refreshTemplateHealth(false, false);
    await loadLastWorkspaceConsistency(false);
  } catch (err) {
    showMessage('Duplicate çözümü başarısız: ' + err.message, 'Duplicate Çözüm Hatası');
  }
}

async function undoLastLifecycleOperation() {
  if (!confirm('Son geri alınabilir duplicate/yetim arşiv işlemi eski yerine taşınacak.\n\nHedefte aynı isimde dosya varsa sistem geri almayı engelleyecek.\n\nDevam edilsin mi?')) return;
  try {
    const response = await fetch('/api/lifecycle/undo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || ('HTTP ' + response.status));
    const op = data.operation || {};
    showCopyableReport('Lifecycle İşlemi Geri Alındı', [
      'Operasyon: ' + String(op.operation_id || ''),
      'Tür: ' + String(op.kind || ''),
      'Durum: ' + String(op.state || ''),
      'Geri gelen dosyalar:',
      ...(op.restored || []).map(item => '• ' + item.absolute_path)
    ].join('\n'));
    refreshTemplateHealth(false, false);
    await loadLastWorkspaceConsistency(false);
  } catch (err) {
    showMessage('Lifecycle geri alma başarısız: ' + err.message, 'Recovery Hatası');
  }
}

/* ============================================================
 * Kaynak görsel görünümü + dosya değiştiren ham işlemler
 * ========================================================== */
function updateSourceViewStatus() {
  const box = el('sourceViewStatus');
  if (!box) return;
  const mode = v6SourceViewMode;
  if (mode === 'original' || state.preview === 'original') {
    box.innerHTML = '🟣 <b>HAM ORİJİNAL önizleniyor.</b> Bu sadece görüntülemedir; dosya değişmedi.';
    box.style.borderColor = '#8A7CF0';
  } else if (mode === 'preview') {
    box.innerHTML = '🟡 <b>SADECE BEYAZLATMA ÖNİZLEMESİ.</b> Çalışma, orijinal ve onay değişmedi.';
    box.style.borderColor = '#F0B84C';
  } else {
    box.innerHTML = '🟢 <b>Çalışma görseli gösteriliyor.</b> Sistem işlemlerinde kullanılan aktif kopya budur.';
    box.style.borderColor = '#0E8F6E';
  }
}

async function showIsolatedWhitePreview() {
  const t = state.current;
  if (!t || t.petek) { showMessage('Önce soldan bir şablon seçin.'); return; }
  try {
    const response = await fetch('/api/anlik_beyazlat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Active-Category': t.cat, 'X-Active-Template': t.filename },
      body: JSON.stringify({ kategori: t.cat, sablon: t.filename }),
    });
    const result = await response.json();
    if (!response.ok || !result.success || !result.preview_only) {
      showMessage('Beyazlatma önizlemesi başarısız: ' + (result.error || response.status));
      return;
    }
    if (imgEl) imgEl.src = result.preview_url + '?t=' + Date.now();
    v6SourceViewMode = 'preview';
    updateSourceViewStatus();
    statusmsg.textContent = 'Beyazlatma önizlemesi (kaydetmez)';
    toast('🖼️ Beyazlatma önizlemesi — dosya değişmedi');
  } catch (error) {
    showMessage('Beyazlatma sunucu hatası: ' + error);
  }
}

async function restoreWorkingFromBackup() {
  const t = state.current;
  if (!t || t.petek) return;
  if (blockIfCurrentBatchTemplate(t.cat, t.filename, 'Ham orijinali geri yükleme')) return;
  if (!confirm('Bu işlem sadece görüntüleme değildir.\n\nKorunmuş ham orijinal, aktif çalışma kopyasının yerine yazılacak. Mevcut onay/geometri kaydı yeniden kontrol gerektirebilir.\n\nDevam edilsin mi?')) return;
  try {
    const response = await fetch('/api/orijinal_yukle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Active-Category': t.cat, 'X-Active-Template': t.filename },
    });
    const res = await response.json();
    if (!res.success) {
      showMessage('Ham orijinal yükleme başarısız: ' + (res.error || 'Bu görselin korunmuş ham yedeği bulunamadı.'));
      return;
    }
    state.preview = 'working';
    syncPreviewButtons();
    updateImage();
    v6SourceViewMode = 'working';
    updateSourceViewStatus();
    // Yeniden yüklenen kaynak yeni bir kimliktir; yerel onay geçersiz sayılır.
    if (t.raw) {
      t.raw._review_status = 'STALE_SOURCE_CHANGED';
      t.raw._manually_verified = false;
      delete t.raw.on_plan;
      delete t.raw.on_plan_source_sha256;
    }
    await refreshAfterJob();
    refreshTemplateHealth(false, false);
    const info =
      (res.recreated_missing_working ? '\nEksik çalışma görseli yedekten yeniden oluşturuldu.' : '\nMevcut çalışma görseli ham yedekten geri yüklendi.') +
      '\n\nKaynak: ' + (res.backup_source_absolute || ((res.source_root || '2_SABLON_HAVUZU_ORIJINAL_YEDEK') + '/' + (res.backup_source_file || t.filename))) +
      '\nHedef: ' + (res.destination_absolute || ((res.destination_root || '2_SABLON_HAVUZU') + '/' + (res.destination_file || t.filename))) +
      '\nPNG birebir kopya doğrulaması: ' + (res.png_byte_exact_restore ? 'EVET' : 'HAYIR / DÖNÜŞTÜRÜLDÜ');
    showMessage('Ham orijinal çalışma kopyasına geri yüklendi.' + info + '\n\nDört köşeyi kontrol edin; gerekirse düzeltin ve “Şablonu Onayla”ya basın.');
  } catch (err) {
    showMessage('Orijinal yükleme bağlantı hatası: ' + err.message);
  }
}

function chooseReplacementOriginal() {
  const t = state.current;
  if (!t || t.petek) { showMessage('Önce soldan bir şablon seçin.'); return; }
  if (blockIfCurrentBatchTemplate(t.cat, t.filename, 'Ham dosyayı yenisiyle değiştirme')) return;
  const input = el('replaceOriginalFileInput');
  if (!input) { showMessage('Yeni ham dosya seçici bulunamadı.'); return; }
  input.value = '';
  input.click();
}

async function replaceOriginalSelectedFile(input) {
  const file = input?.files?.[0];
  if (!file || !state.current || state.current.petek) return;
  const requestCat = state.current.cat;
  const requestTmpl = state.current.filename;
  const ok = confirm(
    'HAM DOSYA DEĞİŞECEK.\n\n' + requestCat + ' / ' + requestTmpl + '\nYeni dosya: ' + file.name + '\n\n' +
    'Eski ham ve eski çalışma kopyaları kalıcı silinmeyecek; Recovery operasyonuna taşınacak. ' +
    'Yeni kaynak sonrası önceki onay STALE_SOURCE_CHANGED olacak ve yeniden kontrol gerekecek.\n\nDevam edilsin mi?');
  if (!ok) { input.value = ''; return; }
  const formData = new FormData();
  formData.append('file', file, file.name);
  try {
    const response = await fetch('/api/templates/replace-original', {
      method: 'POST',
      headers: { 'X-Active-Category': requestCat, 'X-Active-Template': requestTmpl },
      body: formData,
    });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.error || ('HTTP ' + response.status));
    showCopyableReport('Ham Dosya Güvenle Değiştirildi', [
      'Şablon: ' + requestCat + ' / ' + requestTmpl,
      'Yeni ham: ' + String(data.backup_source_absolute || ''),
      'Yeni çalışma: ' + String(data.working_absolute || ''),
      'Ham SHA256: ' + String(data.backup_sha256 || ''),
      'Çalışma SHA256: ' + String(data.working_sha256 || ''),
      'Recovery operasyonu: ' + String(data.operation_id || ''),
      'Recovery’ye alınan eski dosya: ' + Number(data.previous_bytes_archived || 0),
      'STALE yapılan profil: ' + Number(data.profiles_marked_stale || 0),
      'Yeni review durumu: ' + String(data.review_status || '')
    ].join('\n'));
    await refreshSettingsAfterReconciliation();
    if (state.current && state.current.cat === requestCat && state.current.filename === requestTmpl) updateImage();
  } catch (err) {
    showMessage('Ham dosya değiştirilemedi: ' + err.message, 'Ham Dosya Değiştirme Hatası');
  } finally {
    input.value = '';
  }
}

/* ============================================================
 * Kaydet (onaysız) — legacy saveAll
 * ========================================================== */
async function v6SaveAll(silent = false) {
  const t = state.current;
  if (!t) return true;
  if (t.petek) {
    if (!silent) showMessage('PETEK kayıtları ayrı düzenleyicide kaydedilir.');
    return true;
  }
  if (blockIfCurrentBatchTemplate(t.cat, t.filename, 'Bu şablonu kaydetme')) return false;
  const data = JSON.parse(JSON.stringify(t.raw || {}));
  data.tip = 'perspektif';
  data.koseler = t.corners.map(p => [Math.round(p[0]), Math.round(p[1])]);
  delete data.x; delete data.y; delete data.w; delete data.h;
  const orientSel = el('physicalOrientationSelect');
  if (t.cat === '04_Cam_Dograma' && orientSel) {
    const v = String(orientSel.value || '').toUpperCase();
    if (v === 'H' || v === 'V') data.physical_orientation = v;
    else delete data.physical_orientation;
  }
  const glassSel = el('glassCornerRadiusApproval');
  if (glassSel && GLASS_CATEGORIES.includes(t.cat)) data.glass_corner_radius = Number(glassSel.value || 0);
  try {
    const response = await fetch('/api/tekil_sablon_kaydet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kategori: t.cat, sablon: t.filename, data }),
    });
    const res = await response.json();
    if (!res.success) {
      if (!silent) showMessage('Kaydetme hatası: ' + (res.error || 'Bilinmeyen hata'));
      return false;
    }
    t.raw = data;
    if (!silent) { statusmsg.textContent = 'Kaydedildi · ' + t.filename; toast('▣ Değişiklikler kaydedildi'); }
    return true;
  } catch (err) {
    if (!silent) showMessage('Kaydetme hatası: ' + err);
    return false;
  }
}

/* ============================================================
 * Ürün/baskı seçenekleri + köşe doğrultu ölçümü
 * ========================================================== */
function syncProductOptionsControl() {
  const t = state.current;
  const mixed = Boolean(t && !t.petek && t.cat === '04_Cam_Dograma');
  const glass = Boolean(t && !t.petek && GLASS_CATEGORIES.includes(t.cat));
  const orientWrap = el('physical-orientation-wrap');
  const orientSel = el('physicalOrientationSelect');
  const orientVal = el('physicalOrientationValue');
  if (orientWrap) {
    orientWrap.hidden = !mixed;
    if (mixed && orientSel) {
      const value = String((t.raw && t.raw.physical_orientation) || '').toUpperCase();
      const approved = String(t.review_status || '').toUpperCase() === 'APPROVED';
      orientSel.value = (value === 'H' || value === 'V') ? value : ((!approved) ? 'H' : '');
      if (!approved && !['H', 'V'].includes(value) && t.raw) t.raw.physical_orientation = 'H';
      if (orientVal) orientVal.textContent = orientSel.value === 'H' ? 'Yatay' : (orientSel.value === 'V' ? 'Dikey' : 'H (öneri)');
    }
  }
  const glassWrap = el('glassCornerWrap');
  const glassSel = el('glassCornerRadiusApproval');
  if (glassWrap) {
    glassWrap.hidden = !glass;
    if (glass && glassSel) {
      const saved = Number((t.raw && (t.raw.glass_corner_radius ?? 0.008)));
      glassSel.value = saved === 0 ? '0' : saved === 0.015 ? '0.015' : '0.008';
    }
  }
  const empty = el('v6OptionsEmpty');
  if (empty) empty.hidden = Boolean(mixed || glass);
}

function updateAlignment() {
  const t = state.current;
  const mismatchInfo = el('mismatchInfo');
  if (!t || t.petek) { cornerAngles.textContent = '—'; return; }
  const c = t.corners;
  if (!Array.isArray(c) || c.length !== 4) { cornerAngles.textContent = '—'; return; }
  const w = Math.max(1, Number(t.iw || imgEl.naturalWidth || 1));
  const h = Math.max(1, Number(t.ih || imgEl.naturalHeight || 1));
  const [tl, tr, br, bl] = c.map(p => ({ x: Number(p[0]), y: Number(p[1]) }));
  const measure = (a, b, dir) => {
    const dx = b.x - a.x, dy = b.y - a.y;
    const dev = dir === 'H' ? dy : dx;
    const angle = dir === 'H' ? Math.atan2(dy, dx) * 180 / Math.PI : Math.atan2(dx, dy) * 180 / Math.PI;
    const norm = 100 * Math.abs(dev) / (dir === 'H' ? h : w);
    return { dev, angle, norm };
  };
  const top = measure(tl, tr, 'H'), bottom = measure(bl, br, 'H');
  const left = measure(tl, bl, 'V'), right = measure(tr, br, 'V');
  const fmt = (m, side) => `${side}: ${m.dev > 0 ? '+' : ''}${Math.round(m.dev)}px ${m.angle.toFixed(1)}°`;
  const maxDev = Math.max(top.norm, bottom.norm, left.norm, right.norm);
  cornerAngles.style.whiteSpace = 'pre-line';
  cornerAngles.textContent = fmt(top, 'Üst') + '  ' + fmt(bottom, 'Alt') + '\n' + fmt(left, 'Sol') + '  ' + fmt(right, 'Sağ');
  cornerAngles.classList.toggle('v6-warning', maxDev >= 1.0);
  if (mismatchInfo) {
    mismatchInfo.textContent = maxDev < 0.6 ? 'Yok' : (maxDev < 1.0 ? 'Hafif — gözle doğrulayın' : 'Yüksek — köşeleri kontrol edin');
    mismatchInfo.style.color = maxDev < 0.6 ? 'var(--green)' : (maxDev < 1.0 ? 'var(--amber)' : 'var(--red)');
  }
}

/* ============================================================
 * Baskı alanı kaplaması + kenar eğim etiketleri (maskCanvas)
 * ========================================================== */
function paintStage() {
  const canvas = el('maskCanvas');
  const shot = el('shot');
  if (!canvas || !shot) return;
  const cw = shot.clientWidth, ch = shot.clientHeight;
  if (cw < 4 || ch < 4) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(cw * dpr);
  canvas.height = Math.round(ch * dpr);
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cw, ch);
  const t = state.current;
  if (!t) return;
  const iw = t.iw || imgEl.naturalWidth || 896;
  const ih = t.ih || imgEl.naturalHeight || 1200;
  const sc = Math.min(cw / iw, ch / ih) * (state.zoom || 1);
  const left = (cw - iw * sc) / 2 + (state.panX || 0), top = (ch - ih * sc) / 2 + (state.panY || 0);
  const c = t.corners;
  const hasQuad = Array.isArray(c) && c.length === 4;
  const pt = p => [left + Number(p[0]) * sc, top + Number(p[1]) * sc];
  if (hasQuad && v6OverlayOn) {
    ctx.beginPath();
    ctx.moveTo(...pt(c[0])); ctx.lineTo(...pt(c[1])); ctx.lineTo(...pt(c[2])); ctx.lineTo(...pt(c[3]));
    ctx.closePath();
    ctx.fillStyle = 'rgba(23,211,163,.20)';
    ctx.fill();
    ctx.strokeStyle = '#17D3A3';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  // Kayıtlı otomatik ön plan kanıtı (on_plan.object_boxes) — salt okunur yeşil çizgi.
  const plan = t.raw && t.raw.on_plan;
  if (plan && typeof plan === 'object' && Array.isArray(plan.object_boxes) && plan.object_boxes.length) {
    ctx.save();
    ctx.strokeStyle = 'rgba(63,217,138,.85)';
    ctx.setLineDash([4, 3]);
    ctx.lineWidth = 1.5;
    for (const box of plan.object_boxes) {
      if (!Array.isArray(box) || box.length < 4) continue;
      const [x0, y0, x1, y1] = box.map(Number);
      if (![x0, y0, x1, y1].every(Number.isFinite)) continue;
      ctx.strokeRect(left + x0 * sc, top + y0 * sc, Math.max(2, (x1 - x0) * sc), Math.max(2, (y1 - y0) * sc));
    }
    ctx.restore();
  }
  if (hasQuad && v6Tools.showEdgeLabels) {
    const edges = [[0, 1, 0], [1, 2, 90], [3, 2, 0], [0, 3, 90]];
    ctx.save();
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    for (const [a, b, target] of edges) {
      const p = c[a], q = c[b];
      let delta = Math.atan2(q[1] - p[1], q[0] - p[0]) * 180 / Math.PI - target;
      delta = ((delta + 90) % 180 + 180) % 180 - 90;
      const magnitude = Math.abs(delta);
      const symbol = magnitude <= 0.5 ? '✓ DÜZ' : magnitude <= 2 ? '≈' : 'EĞİK';
      const text = `${symbol} ${delta >= 0 ? '+' : ''}${delta.toFixed(1)}°`;
      const color = magnitude <= 0.5 ? '#86efac' : magnitude <= 2 ? '#fde047' : '#fca5a5';
      const [x1, y1] = pt(p), [x2, y2] = pt(q);
      const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - 18;
      const w = Math.min(ctx.measureText(text).width + 12, canvas.width);
      const x = clamp(mx - w / 2, 0, cw - w);
      const y = clamp(my, 11, ch - 11);
      ctx.fillStyle = 'rgba(15,23,42,.92)';
      ctx.fillRect(x, y - 11, w, 22);
      ctx.fillStyle = color;
      ctx.fillText(text, x + 6, y, Math.max(1, w - 12));
    }
    ctx.restore();
  }
}

const v6Tools = window.V6Tools = {};
v6Tools.showEdgeLabels = true;

/* ============================================================
 * Köşe kopyala / yapıştır (C / V)
 * ========================================================== */
function copyCorners() {
  const t = state.current;
  if (!t || !Array.isArray(t.corners) || t.corners.length !== 4) { toast('⚠️ Kopyalanacak 4 köşe yok'); return; }
  v6ClipboardCorners = t.corners.map(p => p.slice());
  toast('📋 Köşeler kopyalandı');
}

function pasteCorners() {
  if (!v6ClipboardCorners) { toast('⚠️ Önce C ile köşe kopyalayın'); return; }
  const t = state.current;
  if (!t) return;
  if (t.petek) { toast('🔥 PETEK köşeleri bu panoda düzenlenmez'); return; }
  t.corners = v6ClipboardCorners.map(p => p.slice());
  render();
  renderInspector();
  // Legacy davranış: yapıştırmadan sonra sessiz otomatik kayıt
  v6SaveAll(true);
  statusmsg.textContent = 'Köşeler yapıştırıldı ve kaydedildi';
  toast('📋 Köşeler yapıştırıldı ve kaydedildi');
}

/* ============================================================
 * Köşeleri elle ayarla odağı — legacy focusCornerEditing
 * ========================================================== */
function focusCornerEditing() {
  const t = state.current;
  const stage = el('stage');
  if (!t) { showMessage('Önce soldan bir şablon seçin.'); return; }
  if (t.petek) { toast('🔥 PETEK köşeleri bu panoda düzenlenmez'); return; }
  if (stage) {
    stage.classList.add('v6-focus');
    window.setTimeout(() => stage.classList.remove('v6-focus'), 1600);
  }
  state.selCorner = 0;
  render();
  renderInspector();
  statusmsg.textContent = 'Köşe 1 seçildi — kırmızı noktaları gerçek baskı alanının dört köşesine sürükleyin.';
  toast('✋ Köşe 1 seçildi — sürükleyerek ayarlayın');
}

/* ============================================================
 * Baskı alanı kaplaması + önizleme arka planı
 * ========================================================== */
function toggleReviewOverlay() {
  v6OverlayOn = !v6OverlayOn;
  paintStage();
  toast(v6OverlayOn ? '🟢 Baskı alanı kaplaması açık' : 'Baskı alanı kaplaması kapalı');
}

const v6BgModes = ['#080C14', '#ffffff', '#39ff14'];
let v6BgMode = 0;
function toggleCanvasBg() {
  v6BgMode = (v6BgMode + 1) % v6BgModes.length;
  const stage = el('stage');
  if (stage) stage.style.background = v6BgModes[v6BgMode];
  toast(['Koyu arka plan', 'Beyaz arka plan', 'Yeşil arka plan'][v6BgMode]);
}

/* ============================================================
 * Taslak uyarı çubuğu (toplu analizden gelen onaysız öneri)
 * ========================================================== */
function hideDraftAlert() {
  const bar = el('v6DraftAlert');
  if (bar) { bar.hidden = true; bar.replaceChildren(); }
}

async function checkDraft() {
  hideDraftAlert();
  const t = state.current;
  if (!t || t.petek) return;
  const bar = el('v6DraftAlert');
  if (!bar) return;
  try {
    const url = '/api/v46/corner_draft?category=' + encodeURIComponent(t.cat) + '&template=' + encodeURIComponent(t.filename);
    const response = await fetch(url, { cache: 'no-store' });
    const data = await response.json();
    if (!state.current || state.current !== t) return;
    if (!response.ok || !data.success || !data.available || !Array.isArray(data.corners)) return;
    v6VisibleDraft = { cat: t.cat, filename: t.filename, corners: data.corners, source: data.source_sha256 };
    bar.hidden = false;
    const line = document.createElement('div');
    line.textContent = '🟡 Bu şablonda toplu analizden gelen ONAYSIZ dört köşe önerisi var.';
    const action = document.createElement('button');
    action.type = 'button';
    action.textContent = '👁️ Taslağı Köşelere Uygula / İncele';
    action.onclick = applyDraftCorners;
    bar.replaceChildren(line, action);
  } catch (err) {
    console.warn('V6 taslak kontrolü:', err);
  }
}

async function applyDraftCorners() {
  const d = v6VisibleDraft;
  const t = state.current;
  if (!d || !t || t.petek || d.cat !== t.cat || d.filename !== t.filename) return;
  try {
    const url = '/api/v46/corner_draft?category=' + encodeURIComponent(d.cat) + '&template=' + encodeURIComponent(d.filename);
    const response = await fetch(url, { cache: 'no-store' });
    const fresh = await response.json();
    if (!response.ok || !fresh.available || fresh.source_sha256 !== d.source || !Array.isArray(fresh.corners) || fresh.corners.length !== 4) {
      showMessage('Taslak artık geçerli değil. Önce tekrar algılayın.');
      return;
    }
    if (!confirm('Bu taslağın dört köşeleri AÇIK şablona uygulanacak. Kaydederken/onaylarken insan kontrolü zorunlu.\n\nÖnceki onaylı geometri toplu taramada DEĞİŞTİRİLMEDİ.\n\nYeni köşeleri ekranda incelemek için devam edilsin mi?')) return;
    t.corners = fresh.corners.map(p => [Number(p[0]), Number(p[1])]);
    render();
    renderInspector();
    hideDraftAlert();
    showMessage('Taslak köşeleri ekranda gösteriliyor. Kontrol edin. Doğruysa “Şablonu Onayla”ya basın. Otomatik onay YAPILMADI.');
  } catch (err) {
    showMessage('Taslak kontrol hatası: ' + String(err));
  }
}

function onTemplateSelected() {
  const t = state.current;
  // Görsel önizleme her yeni seçimde çalışma görseline döner (legacy davranışı)
  if (t && !t.petek && state.preview === 'preview') {
    state.preview = 'working';
    syncPreviewButtons();
    updateImage();
  }
  if (t && !t.petek) v6SourceViewMode = (state.preview === 'original') ? 'original' : 'working';
  syncProductOptionsControl();
  updateSourceViewStatus();
  if (t && !t.petek) checkDraft();
  else hideDraftAlert();
  paintStage();
  // PETEK açıksa dok butonları pasif
  const petek = Boolean(t && t.petek);
  for (const id of ['dockApproveBtn', 'dockSaveBtn', 'dockHealthBtn']) {
    const btn = el(id);
    if (btn) btn.disabled = petek;
  }
}

/* ============================================================
 * render() sarmalayıcı — her köşe değişiminde kaplamayı tazele
 * ========================================================== */
const _origRender = window.render;
if (typeof _origRender === 'function') {
  const wrapped = function () { _origRender(); paintStage(); };
  window.render = wrapped;
}

/* ============================================================
 * Kalıcı job'lara yeniden bağlanma — legacy resumePersistentJobs
 * ========================================================== */
async function resumePersistentJobs() {
  try {
    const response = await fetch('/api/jobs?active=1&limit=20');
    const data = await response.json();
    if (!response.ok || !data.success) return;
    const jobs = Array.isArray(data.jobs) ? data.jobs : [];
    const batchJob = jobs.find(job => String(job.job_type || '').toUpperCase() === 'BATCH_CORNER_SCAN');
    if (batchJob && !v6BatchState.running) {
      const category = String(batchJob.payload?.category || '');
      const total = Number(batchJob.progress_total || batchJob.payload?.templates?.length || 0);
      monitorBatchAnalyzeJob(batchJob.id, category, total, true);
    }
    const healthJob = jobs.find(job => String(job.job_type || '').toUpperCase() === 'RAW_HEALTH_SCAN');
    if (healthJob && !v6HealthScanJobId) {
      monitorHealthScanJob(healthJob.id, false).catch(err => console.warn('Aktif sağlık job takibi başarısız:', err));
    }
    const workspaceJob = jobs.find(job => String(job.job_type || '').toUpperCase() === 'WORKSPACE_CONSISTENCY_SCAN');
    if (workspaceJob && !v6WorkspaceAuditJobId) {
      monitorWorkspaceAuditJob(workspaceJob.id, false).catch(err => console.warn('Aktif klasör audit job takibi başarısız:', err));
    }
  } catch (err) {
    console.warn('Kalıcı işler yeniden bağlanamadı:', err);
  }
}

/* ============================================================
 * Canlı kayıt yenileme — legacy 1.5 sn fingerprint yoklaması
 * ========================================================== */
let v6RegistryFingerprint = '';
let v6RegistryTimer = null;
function startRegistryFingerprintPoll() {
  if (v6RegistryTimer) return;
  v6RegistryTimer = window.setInterval(async () => {
    if (document.hidden || v6BulkState.mode) return;
    try {
      const response = await fetch('/api/ayarlar', { cache: 'no-store' });
      if (!response.ok) return;
      const fresh = await response.json();
      const fingerprint = JSON.stringify(fresh?.kategoriler || {});
      if (!v6RegistryFingerprint) {
        v6RegistryFingerprint = fingerprint;
        return;
      }
      if (fingerprint !== v6RegistryFingerprint) {
        v6RegistryFingerprint = fingerprint;
        const petekRows = state.items.filter(t => t.petek);
        state.items = flatten(fresh).concat(petekRows);
        populateCategoryFilter();
        renderRail();
        updateContext();
        refreshTemplateHealth(false, false);
      }
    } catch (error) {
      console.debug('Şablon inceleme canlı yenileme bekliyor:', error);
    }
  }, 1500);
}

/* ============================================================
 * Dock + panel daraltma + Ctrl+tekerlek panel ölçeği + filtreler
 * ========================================================== */
function bindDock() {
  const approve = el('dockApproveBtn');
  if (approve) approve.addEventListener('click', () => approveTemplate());
  const pause = el('dockPauseBtn');
  if (pause) pause.addEventListener('click', () => {
    v6ReviewPaused = !v6ReviewPaused;
    el('graphiteActionDock')?.classList.toggle('is-paused', v6ReviewPaused);
    const status = el('graphiteActionStatus');
    if (status) status.textContent = v6ReviewPaused ? 'İnceleme beklemeye alındı.' : 'İnceleme devam ediyor.';
  });
  const health = el('dockHealthBtn');
  if (health) health.addEventListener('click', () => runTemplateHealthScan());
  const save = el('dockSaveBtn');
  if (save) save.addEventListener('click', () => v6SaveAll(false));
}

function ensureExpandButtons() {
  if (!el('v6RailExpand')) {
    const btn = document.createElement('button');
    btn.id = 'v6RailExpand';
    btn.className = 'v6-expand-btn v6-expand-rail';
    btn.type = 'button';
    btn.textContent = '»';
    btn.title = 'Şablon listesini göster';
    btn.addEventListener('click', () => setPaneCollapsed('rail', false));
    document.body.appendChild(btn);
  }
  if (!el('v6InspectorExpand')) {
    const btn = document.createElement('button');
    btn.id = 'v6InspectorExpand';
    btn.className = 'v6-expand-btn v6-expand-inspector';
    btn.type = 'button';
    btn.textContent = '«';
    btn.title = 'Kontrol panelini göster';
    btn.addEventListener('click', () => setPaneCollapsed('inspector', false));
    document.body.appendChild(btn);
  }
}

function setPaneCollapsed(which, collapsed, persist = true) {
  ensureExpandButtons();
  const pane = el(which === 'rail' ? 'rail' : 'inspector');
  const resizer = document.querySelector(which === 'rail' ? '.rail-resizer' : '.inspector-resizer');
  const expand = el(which === 'rail' ? 'v6RailExpand' : 'v6InspectorExpand');
  if (pane) pane.classList.toggle('v6-collapsed', collapsed);
  if (resizer) resizer.style.display = collapsed ? 'none' : '';
  if (expand) expand.style.display = collapsed ? 'flex' : 'none';
  const toggle = el(which === 'rail' ? 'railToggle' : 'inspectorToggle');
  if (toggle) toggle.textContent = collapsed ? (which === 'rail' ? '»' : '«') : (which === 'rail' ? '◀' : '▶');
  if (persist) {
    try { localStorage.setItem(which === 'rail' ? 'v6.rail.collapsed' : 'v6.inspector.collapsed', collapsed ? '1' : '0'); } catch (_) {}
  }
  window.dispatchEvent(new Event('resize'));
  window.requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  render();
}

function bindPanelControls() {
  el('railToggle')?.addEventListener('click', () => setPaneCollapsed('rail', !el('rail')?.classList.contains('v6-collapsed')));
  el('inspectorToggle')?.addEventListener('click', () => setPaneCollapsed('inspector', !el('inspector')?.classList.contains('v6-collapsed')));
  // Ctrl + tekerlek: yan paneli genişlet / daralt (legacy panel zoom karşılığı)
  const limits = { rail: [210, 440], inspector: [260, 520] };
  for (const which of ['rail', 'inspector']) {
    const pane = el(which);
    if (!pane) continue;
    pane.addEventListener('wheel', e => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      const [lo, hi] = limits[which];
      const delta = e.deltaY < 0 ? 16 : -16;
      pane.style.width = clamp(pane.getBoundingClientRect().width + delta, lo, hi) + 'px';
      try { localStorage.setItem('v6.' + which + '.width', pane.style.width.replace('px', '')); } catch (_) {}
      render();
    }, { passive: false });
  }
}

function bindStatusCheckboxFilter() {
  const panel = el('v499StatusPanel');
  if (!panel) return;
  panel.querySelectorAll('input[data-v499-state]').forEach(input => {
    input.addEventListener('change', () => {
      const next = new Set();
      panel.querySelectorAll('input[data-v499-state]').forEach(box => {
        if (!box.checked) next.add(box.dataset.v499State);
      });
      state.hiddenStates = next;
      renderRail();
      const cnt = el('railCnt');
      if (cnt) cnt.textContent = String(state.filtered.length);
    });
  });
}

function bindBulkControls() {
  el('v6BulkModeButton')?.addEventListener('click', toggleBulkSelectionMode);
  el('v6BulkSelectCategory')?.addEventListener('click', selectAllInCurrentCategory);
  el('v6BulkClearSelection')?.addEventListener('click', clearBulkSelection);
  el('v6BulkSelectPending')?.addEventListener('click', () => v6SelectByReviewStatus(false));
  el('v6BulkSelectApproved')?.addEventListener('click', () => v6SelectByReviewStatus(true));
  el('v6BulkDetectButton')?.addEventListener('click', bulkDetectSelectedCorners);
  el('v6BulkDetectStopButton')?.addEventListener('click', stopBulkCornerDetect);
  el('v6BulkApproveButton')?.addEventListener('click', bulkApproveSelected);
  el('v6BulkDeleteButton')?.addEventListener('click', bulkDeleteSelected);
  el('v6BatchAnalyzeButton')?.addEventListener('click', batchAnalyze);
  // Satır içi toplu seçim kutucuğu — satır tıklamasını yut
  railList.addEventListener('click', e => {
    const chk = e.target.closest('.trow-check');
    if (!chk) return;
    e.stopPropagation();
    e.preventDefault();
    const key = chk.getAttribute('data-bulk-check');
    if (v6BulkState.selected.has(key)) v6BulkState.selected.delete(key);
    else v6BulkState.selected.add(key);
    const row = chk.closest('.trow');
    const on = v6BulkState.selected.has(key);
    chk.classList.toggle('on', on);
    if (row) row.classList.toggle('bulk-selected', on);
    updateBulkSelectedCount();
  }, true);
}

function bindReportButtons() {
  el('templateHealthScanButton')?.addEventListener('click', runTemplateHealthScan);
  el('lastTemplateHealthReportButton')?.addEventListener('click', openLastTemplateHealthReport);
  el('templateHealthHistoryButton')?.addEventListener('click', openTemplateHealthHistory);
  el('workspaceConsistencyScanButton')?.addEventListener('click', runWorkspaceConsistencyScan);
  el('lastWorkspaceConsistencyReportButton')?.addEventListener('click', openLastWorkspaceConsistencyReport);
  el('workspaceConsistencyHistoryButton')?.addEventListener('click', openWorkspaceConsistencyHistory);
  el('v6BulkAlignmentButton')?.addEventListener('click', v6BulkAlignmentReport);
  el('v6ReconciliationBtn')?.addEventListener('click', openActionableReconciliationCenter);
  el('v6ResolveDuplicatesBtn')?.addEventListener('click', resolveCurrentTemplateDuplicates);
  el('v6RecoveryCenterBtn')?.addEventListener('click', () => openLifecycleCenter('recovery'));
  el('v6UndoLifecycleBtn')?.addEventListener('click', undoLastLifecycleOperation);
  el('v6CanvasBgBtn')?.addEventListener('click', toggleCanvasBg);
  el('v6OverlayToggleBtn')?.addEventListener('click', toggleReviewOverlay);
}

function bindSourceButtons() {
  el('v6WhitePreviewBtn')?.addEventListener('click', showIsolatedWhitePreview);
  el('v6RestoreWorkingBtn')?.addEventListener('click', restoreWorkingFromBackup);
  el('v6ChooseReplacementBtn')?.addEventListener('click', chooseReplacementOriginal);
  el('replaceOriginalFileInput')?.addEventListener('change', e => replaceOriginalSelectedFile(e.target));
  // Görünüm düğmeleri kaynak durum kutusunu da günceller
  el('restoreOriginalBtn')?.addEventListener('click', () => { v6SourceViewMode = 'original'; updateSourceViewStatus(); });
  el('refreshWorkingBtn')?.addEventListener('click', () => { v6SourceViewMode = 'working'; updateSourceViewStatus(); });
  const orientSel = el('physicalOrientationSelect');
  if (orientSel) orientSel.addEventListener('change', () => {
    const v = String(orientSel.value || '').toUpperCase();
    const t = state.current;
    if (t && t.raw) {
      if (v === 'H' || v === 'V') t.raw.physical_orientation = v;
      else delete t.raw.physical_orientation;
    }
    const orientVal = el('physicalOrientationValue');
    if (orientVal) orientVal.textContent = v === 'H' ? 'Yatay' : (v === 'V' ? 'Dikey' : 'Seçin…');
  });
  const glassSel = el('glassCornerRadiusApproval');
  if (glassSel) glassSel.addEventListener('change', () => {
    const t = state.current;
    if (t && t.raw) t.raw.glass_corner_radius = Number(glassSel.value || 0);
  });
}

function bindUI() {
  bindDock();
  bindPanelControls();
  bindStatusCheckboxFilter();
  bindBulkControls();
  bindReportButtons();
  bindSourceButtons();
  el('btnCorner')?.addEventListener('click', focusCornerEditing);
}

/* ============================================================
 * Global JS hata yakalayıcı (legacy window.onerror karşılığı)
 * ========================================================== */
window.addEventListener('error', event => {
  try {
    showMessage('JS ERROR: ' + String(event.message || 'bilinmeyen hata') +
      '\nKaynak: ' + String(event.filename || '?') +
      '\nSatır: ' + String(event.lineno || '?') + ':' + String(event.colno || '?'));
  } catch (_) { /* raporlama ikincil bir hata üretmesin */ }
});
window.addEventListener('unhandledrejection', event => {
  try {
    showMessage('Beklenmeyen promise hatası:\n' + String((event.reason && (event.reason.message || event.reason)) || 'bilinmeyen hata'));
  } catch (_) {}
});

/* ============================================================
 * Başlatma
 * ========================================================== */
bindUI();
showHealthBanner();
startStagingCollisionPolling();
refreshTemplateHealth(false, false);
loadLastWorkspaceConsistency(false);
resumePersistentJobs();
startRegistryFingerprintPoll();
updateSourceViewStatus();
function restorePaneCollapse() {
  let rail = false, insp = false;
  try {
    rail = localStorage.getItem('v6.rail.collapsed') === '1';
    insp = localStorage.getItem('v6.inspector.collapsed') === '1';
    // Kalıcı pane genişlikleri (ctrl+tekerlek / sürükleyerek ayarlanan)
    for (const which of ['rail', 'inspector']) {
      const raw = localStorage.getItem('v6.' + which + '.width');
      const width = Number(raw);
      if (raw && Number.isFinite(width) && width > 0) {
        const limits = which === 'rail' ? [210, 440] : [260, 520];
        const pane = el(which);
        if (pane) pane.style.width = clamp(width, limits[0], limits[1]) + 'px';
      }
    }
  } catch (_) {}
  if (rail) setPaneCollapsed('rail', true, false);
  if (insp) setPaneCollapsed('inspector', true, false);
}
restorePaneCollapse();

Object.defineProperty(v6Tools, 'bulkMode', { get: () => v6BulkState.mode, enumerable: true });
Object.assign(v6Tools, {
  refreshAfterJob,
  healthInfo: getTemplateHealth,
  lifecycleInfo: getWorkspaceTemplateState,
  focusCornerEditing,
  bulkKey: bulkTemplateKey,
  isBulkSelected,
  isBatchAnalyzingTemplate,
  blockIfCurrentBatchTemplate,
  updateAlignment,
  onTemplateSelected,
  copyCorners,
  pasteCorners,
  paintStage,
  paintOverlay: paintStage,
  toggleReviewOverlay,
  toggleCanvasBg,
  showHelp,
  checkDraft,
  saveAll: v6SaveAll,
});
