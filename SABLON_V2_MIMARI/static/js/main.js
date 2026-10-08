window.onerror = function(msg, url, line, col, error) {
        alert("JS ERROR: " + msg + "\\nLine: " + line);
        return false;
    };
    
    // GLOBAL PERFORMANS OLCUM (FETCH WRAPPER)
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        const url = args[0];
        if (typeof url === 'string' && url.startsWith('/api/')) {
            const startTime = performance.now();
            try {
                const response = await originalFetch.apply(this, args);
                const endTime = performance.now();
                const durationMs = endTime - startTime;
                
                let perfMetric = document.getElementById("perf-metric");
                if (perfMetric) {
                    perfMetric.style.display = "inline-block";
                    let sec = (durationMs / 1000).toFixed(2);
                    
                    if (durationMs < 500) {
                        perfMetric.style.color = "#44ff44";
                        perfMetric.innerText = `⚡ ${sec}s`;
                    } else if (durationMs < 2000) {
                        perfMetric.style.color = "#ffdd44";
                        perfMetric.innerText = `⏱️ ${sec}s`;
                    } else {
                        perfMetric.style.color = "#ff4444";
                        perfMetric.innerText = `🐢 ${sec}s`;
                    }
                    
                    // 3 saniye sonra gizle (eger yeni istek gelmezse)
                    clearTimeout(window.perfTimeout);
                    window.perfTimeout = setTimeout(() => {
                        perfMetric.style.display = "none";
                    }, 4000);
                }
                return response;
            } catch (error) {
                console.error("Fetch hatasi:", error);
                throw error;
            }
        }
        return originalFetch.apply(this, args);
    };

    function showCopyableReport(title, text) {
        let overlay = document.getElementById('copyable-report-overlay');
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
                </div>
            `;
            document.body.appendChild(overlay);

            const closeReport = () => {
                overlay.style.display = 'none';
            };
            overlay.querySelector('.copyable-report-close').onclick = closeReport;
            overlay.querySelector('.copyable-report-ok').onclick = closeReport;
            overlay.addEventListener('click', event => {
                if (event.target === overlay) closeReport();
            });
            document.addEventListener('keydown', event => {
                if (event.key === 'Escape' && overlay.style.display !== 'none') {
                    closeReport();
                }
            });

            overlay.querySelector('.copyable-report-copy').onclick = async () => {
                const area = overlay.querySelector('.copyable-report-text');
                const status = overlay.querySelector('.copyable-report-status');
                const reportText = area.value;
                let copied = false;

                try {
                    if (navigator.clipboard && window.isSecureContext) {
                        await navigator.clipboard.writeText(reportText);
                        copied = true;
                    }
                } catch (err) {
                    copied = false;
                }

                if (!copied) {
                    area.focus();
                    area.select();
                    try {
                        copied = document.execCommand('copy');
                    } catch (err) {
                        copied = false;
                    }
                    area.setSelectionRange(0, 0);
                }

                status.textContent = copied
                    ? '✅ Metin panoya kopyalandı.'
                    : 'Metni seçip Ctrl+C ile kopyalayabilirsiniz.';
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

    // SISTEM SAĞLIK KONTROLÜ
    fetch('/api/saglik_durumu')
        .then(res => res.json())
        .then(data => {
            const errorCount = Number(data.sorun_sayisi || 0);
            const warningCount = Number(data.uyari_sayisi || 0);
            const solvedCount = Number(data.cozulen_sayisi || 0);
            if(errorCount > 0 || warningCount > 0 || solvedCount > 0) {
                let banner = document.createElement("div");
                banner.style.padding = "10px";
                banner.style.textAlign = "center";
                banner.style.fontWeight = "bold";
                banner.style.zIndex = "10000";
                banner.style.position = "relative";
                
                if(errorCount > 0) {
                    banner.style.backgroundColor = "#ff4444";
                    banner.style.color = "white";
                    banner.textContent = "⛔ ÜRETİM GÜVENLİĞİ: " + errorCount + " kritik sorun bulundu.";
                } else if(warningCount > 0) {
                    banner.style.backgroundColor = "#ffbf47";
                    banner.style.color = "black";
                    banner.textContent = "⚠️ FACTORY DOCTOR: " + warningCount + " geliştirme/sağlık uyarısı var.";
                } else {
                    banner.style.backgroundColor = "#44ff44";
                    banner.style.color = "black";
                    banner.textContent = "✅ SİSTEM " + solvedCount + " adet sorunu otomatik olarak çözdü.";
                }
                
                let details = document.createElement("button");
                details.innerText = "Detaylar";
                details.style.marginLeft = "15px";
                details.onclick = () => {
                    const reportText =
                        "KRİTİK SORUNLAR:\n" + (data.sorunlar || []).join("\n") +
                        "\n\nUYARILAR:\n" + (data.uyarilar || []).join("\n") +
                        "\n\nÇÖZÜLENLER:\n" + (data.cozulenler || []).join("\n");
                    showCopyableReport("Factory Doctor Detayları", reportText);
                };
                banner.appendChild(details);
                
                let mainDiv = document.getElementById("main");
                if (mainDiv) {
                    mainDiv.insertBefore(banner, mainDiv.firstChild);
                } else {
                    document.body.insertBefore(banner, document.body.firstChild);
                }
            }
        }).catch(err => console.log("Sağlık kontrolü alınamadı", err));


    let ayarlar = null;
    let currentCat = null;
    let currentTmpl = null;
    let currentImg = null;
    
    // Zoom & Pan vars
    let baseScale = 1;
    let userZoom = 1.65; // User requested 165% zoom by default
    let offsetX = 0;
    let offsetY = 0;
    
    let pts = []; 
    let clipboardPts = null; // For copy/paste
    let draggingPoint = -1;
    let isPanning = false;
    let isSpacePressed = false;
    let panStartX = 0;
    let panStartY = 0;

    // Automatic foreground evidence only; manual mask/brush tools removed.
    let foregroundMask = {
        object_boxes: [],
        feather: 1.2,
        grabcut_iterations: 5
    };

    const canvas = document.getElementById('c');
    const ctx = canvas.getContext('2d');
    const cont = document.getElementById('canvas-container');
    
    let bgMode = 0; // 0: dark, 1: white, 2: green
    const bgColors = [
        "#111 url('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAMUlEQVQ4T2NkYGAQYcAP3uCTZhw1gGGYhAGBZIA/ENFMo/5BAv4wMBw1gGGYhAGBCgIAVqU12f71J0EAAAAASUVORK5CYII=') repeat",
        "#ffffff",
        "#39ff14"
    ];

    function toggleCanvasBg() {
        bgMode = (bgMode + 1) % bgColors.length;
        document.getElementById('canvas-container').style.background = bgColors[bgMode];
    }
    
    let originalImgObj = null; // Ham orjinal gorseli hafizada tutar
    let sourceViewMode = 'working';

    function updateSourceViewStatus() {
        const el = document.getElementById('source-view-status');
        if (!el) return;
        if (sourceViewMode === 'original') {
            el.innerHTML = '🟣 <b>HAM ORİJİNAL önizleniyor.</b> Bu sadece görüntülemedir; dosya değişmedi.';
            el.style.borderColor = '#8b5cf6';
        } else {
            el.innerHTML = '🟢 <b>Çalışma görseli gösteriliyor.</b> Sistem işlemlerinde kullanılan aktif kopya budur.';
            el.style.borderColor = '#2e7d32';
        }
    }

    function loadSourceImage(mode, onSuccess = null) {
        if (!currentCat || !currentTmpl) return;
        const img = new Image();
        img.onload = () => {
            currentImg = img;
            originalImgObj = img;
            sourceViewMode = mode;
            updateSourceViewStatus();
            resetView();
            draw();
            if (typeof onSuccess === 'function') onSuccess();
        };
        img.onerror = () => {
            const label = mode === 'original'
                ? 'Ham orijinal yedek'
                : 'Çalışma görseli';
            alert(
                label + ' bulunamadı veya okunamadı. Dosya üzerinde hiçbir değişiklik yapılmadı.'
            );
        };
        const route = mode === 'original'
            ? '/original-image/'
            : '/working-image/';
        img.src =
            route +
            encodeURIComponent(currentCat) + '/' +
            encodeURIComponent(currentTmpl) +
            '?t=' + new Date().getTime();
    }

    function showOriginalPreview() {
        loadSourceImage('original');
    }

    function showWorkingPreview() {
        loadSourceImage('working');
    }

    
    let allTemplates = [];
    let bulkSelectionMode = false;
    let bulkTargetCategory = null;
    const bulkSelectedTemplates = new Set();

    function bulkTemplateKey(cat, tmpl) {
        return String(cat) + "\u0000" + String(tmpl);
    }

    function parseBulkTemplateKey(key) {
        const idx = String(key).indexOf("\u0000");
        if (idx < 0) return ["", ""];
        return [key.slice(0, idx), key.slice(idx + 1)];
    }

    function updateBulkSelectedCount() {
        const count = bulkSelectedTemplates.size;
        const label = document.getElementById('bulkSelectedCount');
        if (label) {
            label.textContent = count + ' şablon seçildi';
        }
        const deleteButton = document.getElementById('bulkDeleteButton');
        if (deleteButton) {
            deleteButton.disabled = count === 0;
            deleteButton.style.opacity = count === 0 ? '0.55' : '1';
        }
    }

    function applyBulkSelectionUi() {
        const actionPanel = document.getElementById('bulkSelectionActions');
        const modeButton = document.getElementById('bulkModeButton');

        if (actionPanel) {
            actionPanel.style.display = bulkSelectionMode ? 'block' : 'none';
        }
        if (modeButton) {
            modeButton.classList.toggle('active', bulkSelectionMode);
            modeButton.textContent = bulkSelectionMode
                ? '✅ Toplu Seçim Açık'
                : '☑️ Toplu Seçim';
        }

        allTemplates.forEach(entry => {
            const item = entry.elem;
            if (!item) return;

            let checkbox = item.querySelector('.template-select-checkbox');
            if (!checkbox) {
                checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'template-select-checkbox';
                checkbox.title = 'Bu şablonu toplu işlem için seç';
                checkbox.onclick = event => event.stopPropagation();
                checkbox.onchange = event => {
                    event.stopPropagation();
                    const key = bulkTemplateKey(entry.cat, entry.tmpl);
                    if (checkbox.checked) bulkSelectedTemplates.add(key);
                    else bulkSelectedTemplates.delete(key);
                    updateBulkSelectedCount();
                };
                item.prepend(checkbox);
            }

            checkbox.style.display = bulkSelectionMode ? 'inline-block' : 'none';
            checkbox.checked = bulkSelectedTemplates.has(
                bulkTemplateKey(entry.cat, entry.tmpl)
            );
            item.classList.toggle(
                'bulk-selected',
                bulkSelectionMode && checkbox.checked
            );
        });

        updateBulkSelectedCount();
    }

    function toggleBulkSelectionMode() {
        bulkSelectionMode = !bulkSelectionMode;
        if (!bulkSelectionMode) {
            bulkSelectedTemplates.clear();
        }
        applyBulkSelectionUi();
    }

    function clearBulkSelection() {
        bulkSelectedTemplates.clear();
        applyBulkSelectionUi();
    }

    function selectAllInCurrentCategory() {
        const targetCategory = bulkTargetCategory || currentCat;
        if (!targetCategory) {
            alert('Önce soldan bir kategori başlığına veya şablona tıklayın.');
            return;
        }
        allTemplates
            .filter(entry => entry.cat === targetCategory)
            .forEach(entry => {
                bulkSelectedTemplates.add(
                    bulkTemplateKey(entry.cat, entry.tmpl)
                );
            });
        applyBulkSelectionUi();
    }

    async function bulkDeleteSelected() {
        const selected = Array.from(bulkSelectedTemplates)
            .map(parseBulkTemplateKey)
            .filter(([cat, tmpl]) => (
                cat && tmpl
                && ayarlar?.kategoriler?.[cat]?.sablonlar?.[tmpl]
            ));

        if (selected.length === 0) {
            alert('Önce çöpe atılacak şablonları işaretleyin.');
            return;
        }

        if (!confirm(
            selected.length +
            ' şablon aktif kullanımdan çıkarılıp geri alınabilir çöp alanına taşınacak. Devam edilsin mi?'
        )) return;

        const button = document.getElementById('bulkDeleteButton');
        const countLabel = document.getElementById('bulkSelectedCount');
        const originalText = button ? button.textContent : '';

        if (button) {
            button.disabled = true;
            button.textContent = '⏳ Seçilenler çöpe taşınıyor...';
        }
        if (countLabel) {
            countLabel.textContent =
                selected.length + ' şablon işleniyor...';
        }

        try {
            const response = await fetch('/api/sablon_sil_toplu', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    items: selected.map(([category, template]) => ({
                        category,
                        template
                    }))
                })
            });
            const data = await response.json();

            const deleted = Array.isArray(data.deleted) ? data.deleted : [];
            const failed = Array.isArray(data.failed) ? data.failed : [];

            for (const item of deleted) {
                bulkSelectedTemplates.delete(
                    bulkTemplateKey(item.category, item.template)
                );
            }

            const refresh = await fetch('/api/ayarlar');
            if (!refresh.ok) {
                throw new Error('Şablon listesi yenilenemedi.');
            }
            ayarlar = await refresh.json();

            if (
                currentCat
                && currentTmpl
                && !ayarlar?.kategoriler?.[currentCat]?.sablonlar?.[currentTmpl]
            ) {
                currentTmpl = null;
                currentImg = null;
                originalImgObj = null;
                pts = [];
                draw();
            }

            renderSidebar();

            const failedText = failed.length
                ? '\n\nSilinemeyenler:\n' +
                  failed.slice(0, 10).map(item =>
                      (item.category ? item.category + ' / ' : '') +
                      (item.template || 'Bilinmeyen') +
                      ': ' + (item.error || 'Bilinmeyen hata')
                  ).join('\n')
                : '';

            alert(
                'Toplu işlem tamamlandı.\n' +
                Number(data.deleted_count || deleted.length) +
                ' şablon çöpe taşındı.' +
                (failed.length
                    ? '\n' + failed.length + ' şablon silinemedi.'
                    : '') +
                failedText
            );
        } catch (err) {
            alert('Toplu silme başarısız: ' + err.message);
        } finally {
            if (button) {
                button.textContent =
                    originalText || '🗑️ Seçilenleri Çöpe At';
                button.disabled = bulkSelectedTemplates.size === 0;
            }
            updateBulkSelectedCount();
        }
    }

    // Load config
    fetch('/api/ayarlar')
        .then(r => {
            if (!r.ok) throw new Error('HTTP error ' + r.status);
            return r.json();
        })
        .then(data => {
            ayarlar = data;
            renderSidebar();
        })
        .catch(err => alert("FETCH ERROR: " + err.message));
    
    function renderSidebar() {
        const catDiv = document.getElementById('categories');
        catDiv.innerHTML = '';
        allTemplates = [];
        for (const cat in ayarlar.kategoriler) {
            const div = document.createElement('div');
            div.className = 'category';
            const title = document.createElement('div');
            title.className = 'category-title';
            const templateCount = Object.keys(
                ayarlar?.kategoriler?.[cat]?.sablonlar || {}
            ).length;
            title.textContent = cat + ' (' + templateCount + ')';
            const list = document.createElement('div');
            list.className = 'template-list';
            if (cat === currentCat) {
                list.style.display = 'block';
            }
            title.onclick = () => {
                bulkTargetCategory = cat;
                list.style.display = list.style.display === 'block' ? 'none' : 'block';
            };
            div.appendChild(title);
            for (const tmpl in ayarlar.kategoriler[cat].sablonlar) {
                const itemData = ayarlar.kategoriler[cat].sablonlar[tmpl];
                const item = document.createElement('div');
                item.className = 'template-item';
                item.dataset.category = cat;
                item.dataset.template = tmpl;

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'template-select-checkbox';
                checkbox.style.display = bulkSelectionMode ? 'inline-block' : 'none';
                checkbox.title = 'Bu şablonu toplu işlem için seç';
                checkbox.onclick = event => event.stopPropagation();
                checkbox.onchange = event => {
                    event.stopPropagation();
                    const key = bulkTemplateKey(cat, tmpl);
                    if (checkbox.checked) bulkSelectedTemplates.add(key);
                    else bulkSelectedTemplates.delete(key);
                    item.classList.toggle('bulk-selected', checkbox.checked);
                    updateBulkSelectedCount();
                };
                checkbox.checked = bulkSelectedTemplates.has(
                    bulkTemplateKey(cat, tmpl)
                );

                const label = document.createElement('span');
                label.className = 'template-item-label';

                const hasCorners = (
                    itemData.koseler
                    && itemData.koseler.length === 4
                );
                const reviewStatus = String(
                    itemData._review_status
                    || itemData.review_status
                    || 'UNANALYZED'
                ).toUpperCase();

                if (reviewStatus === 'APPROVED') {
                    label.textContent = '✅ ' + tmpl;
                    item.title = 'İnsan onaylı ve üretime uygun profil.';
                } else if (
                    reviewStatus === 'STALE_SOURCE_CHANGED'
                    || reviewStatus === 'AMBIGUOUS_DUPLICATE'
                ) {
                    label.textContent = '⛔ ' + tmpl;
                    item.style.backgroundColor = 'rgba(220,53,69,0.2)';
                    item.style.color = '#ff9999';
                    item.title = 'Onay artık güvenli değil; yeniden analiz/onay gerekli.';
                } else if (itemData.supheli) {
                    label.textContent = '⚠️ ' + tmpl;
                    item.style.backgroundColor = 'rgba(220,53,69,0.2)';
                    item.style.color = '#ff9999';
                    item.title = 'Otomatik tespit şüpheli. İnsan kontrolü gerekli.';
                } else if (hasCorners) {
                    label.textContent = '📝 ' + tmpl;
                    item.title = '4 köşe var fakat henüz onaylanmadı.';
                } else {
                    label.textContent = '⏳ ' + tmpl;
                    item.title = 'Henüz incelenmedi.';
                }

                item.appendChild(checkbox);
                item.appendChild(label);

                item.onclick = () => {
                    if (bulkSelectionMode) {
                        checkbox.checked = !checkbox.checked;
                        checkbox.dispatchEvent(
                            new Event('change', {bubbles: false})
                        );
                        return;
                    }
                    navigateToTemplate(cat, tmpl, item);
                };

                list.appendChild(item);
                allTemplates.push({cat, tmpl, elem: item, list});
            }
            div.appendChild(list);
            catDiv.appendChild(div);
        }
        applyBulkSelectionUi();
    }

    async function navigateToTemplate(cat, tmpl, elem) {
        if (cat === currentCat && tmpl === currentTmpl) {
            loadTemplate(cat, tmpl, elem);
            return;
        }
        if (currentCat && currentTmpl) {
            const saved = await saveAll(true);
            if (!saved) {
                alert('Mevcut şablon kaydedilemedi. Veri kaybını önlemek için geçiş iptal edildi.');
                return;
            }
        }
        loadTemplate(cat, tmpl, elem);
    }

    async function nextTemplate() {
        if (allTemplates.length === 0) return;
        let idx = allTemplates.findIndex(t => t.cat === currentCat && t.tmpl === currentTmpl);
        if (idx === -1 || idx === allTemplates.length - 1) idx = 0;
        else idx++;
        const target = allTemplates[idx];
        if (target.list) target.list.style.display = 'block';
        await navigateToTemplate(target.cat, target.tmpl, target.elem);
    }

    async function prevTemplate() {
        if (allTemplates.length === 0) return;
        let idx = allTemplates.findIndex(t => t.cat === currentCat && t.tmpl === currentTmpl);
        if (idx <= 0) idx = allTemplates.length - 1;
        else idx--;
        const target = allTemplates[idx];
        if (target.list) target.list.style.display = 'block';
        await navigateToTemplate(target.cat, target.tmpl, target.elem);
    }

    function updateCounter() {
        let idx = allTemplates.findIndex(t => t.cat === currentCat && t.tmpl === currentTmpl);
        const el = document.getElementById('tmpl-counter');
        if (el) {
            el.textContent = idx !== -1 ? `[${idx + 1} / ${allTemplates.length}]` : '';
        }
    }
    
    function loadTemplate(cat, tmpl, elem) {
        document.querySelectorAll('.template-item').forEach(el => el.classList.remove('active'));
        if(elem) elem.classList.add('active');
        
        currentCat = cat;
        bulkTargetCategory = cat;
        currentTmpl = tmpl;
        const data = ayarlar.kategoriler[cat].sablonlar[tmpl];
        
        // Every template is permanently perspective geometry.
        data.tip = 'perspektif';
        delete data.x; delete data.y; delete data.w; delete data.h;

        document.getElementById('current-file').textContent = cat + ' / ' + tmpl;
        updateCounter();
        syncPhysicalOrientationControl(data);
        resetView();

        const savedPlan = (
            data.on_plan
            && typeof data.on_plan === 'object'
            && !Array.isArray(data.on_plan)
        ) ? data.on_plan : {};
        foregroundMask = {
            object_boxes: Array.isArray(savedPlan.object_boxes)
                ? savedPlan.object_boxes.map(box => box.slice(0, 4))
                : [],
            feather: Number(savedPlan.feather || 1.2),
            grabcut_iterations: Number(savedPlan.grabcut_iterations || 5)
        };

        const img = new Image();
        img.onload = () => {
            currentImg = img;
            originalImgObj = img;
            sourceViewMode = 'working';
            updateSourceViewStatus();
            initPoints(data);
            draw();
        };
        img.onerror = () => {
            sourceViewMode = 'working';
            updateSourceViewStatus();
            alert(
                'HATA: "' + tmpl + '" çalışma görseli 2_SABLON_HAVUZU içinde bulunamadı veya okunamadı. ' +
                'Ham yedeği kontrol etmek için “Ham Orijinali Göster” butonunu kullanabilirsiniz.'
            );
            currentImg = null;
            draw();
        };
        img.src =
            '/working-image/' +
            encodeURIComponent(cat) + '/' +
            encodeURIComponent(tmpl) +
            '?t=' + new Date().getTime();
    }
    
    function resetView() {
        userZoom = 1.65;
        offsetX = 0;
        offsetY = 0;
    }
    
    function initPoints(data) {
        pts = [];
        if (Array.isArray(data.koseler) && data.koseler.length === 4) {
            pts = data.koseler.map(p => ({x: Number(p[0]), y: Number(p[1])}));
            return;
        }
        if (!currentImg) return;
        const mx = Math.round(currentImg.width * 0.15);
        const my = Math.round(currentImg.height * 0.15);
        pts = [
            {x: mx, y: my},
            {x: currentImg.width - mx, y: my},
            {x: currentImg.width - mx, y: currentImg.height - my},
            {x: mx, y: currentImg.height - my}
        ];
    }

    function updateDataFromPoints() {
        if (!currentCat || !currentTmpl || pts.length !== 4) return;
        const data = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
        data.tip = 'perspektif';
        data.koseler = pts.map(p => [Math.round(p.x), Math.round(p.y)]);
        delete data.x; delete data.y; delete data.w; delete data.h;
        if (data.supheli) delete data.supheli;
    }

    // =========================================================
    // OTOMATİK ÖN PLAN VERİSİ
    // =========================================================
    function cloneForegroundMask() {
        const boxes = Array.isArray(foregroundMask.object_boxes)
            ? foregroundMask.object_boxes.map(box => box.slice(0, 4))
            : [];
        if (boxes.length === 0) return null;
        return {
            object_boxes: boxes,
            feather: Number(foregroundMask.feather || 1.2),
            grabcut_iterations: Number(foregroundMask.grabcut_iterations || 5)
        };
    }

    function focusCornerEditing() {
        const container = document.getElementById('canvas-container');
        if (container) container.focus();
        const info = document.getElementById('info');
        if (info) {
            info.textContent = 'Kırmızı köşe noktalarını sürükleyerek baskı alanını ayarlayın.';
        }
    }

    function updateCursor() {
        if (!canvas) return;
        canvas.style.cursor = isPanning ? 'grabbing' : 'default';
    }

    function savePhysicalOrientationSelection() {
        if (!currentCat || !currentTmpl || !ayarlar || !ayarlar.kategoriler[currentCat]) return;
        const select = document.getElementById('physicalOrientationSelect');
        const tmplObj = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
        if (!select || !tmplObj) return;
        const value = String(select.value || '').toUpperCase();
        if (value === 'H' || value === 'V') {
            tmplObj.physical_orientation = value;
        } else {
            delete tmplObj.physical_orientation;
        }
    }

    function syncPhysicalOrientationControl(data) {
        const wrap = document.getElementById('physical-orientation-wrap');
        const select = document.getElementById('physicalOrientationSelect');
        if (!wrap || !select) return;
        const mixed = currentCat === '04_Cam_Dograma';
        wrap.style.display = mixed ? 'block' : 'none';
        const value = String((data && data.physical_orientation) || '').toUpperCase();
        select.value = (value === 'H' || value === 'V') ? value : '';
    }

    function saveCurrentTemplateData() {
        if (currentCat && currentTmpl && ayarlar && ayarlar.kategoriler[currentCat]) {
            const tmplObj = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
            const autoPlan = cloneForegroundMask();
            if (autoPlan) tmplObj.on_plan = autoPlan;
            else delete tmplObj.on_plan;
            if (currentCat === '04_Cam_Dograma') {
                savePhysicalOrientationSelection();
            }
        }
    }

    // Tam koordinat dönüştürme - sınır kontrolü YOK (köşe noktası dışarıda olabilir)
    function eventToRawImagePoint(e) {
        if (!currentImg) return null;
        const finalScale = baseScale * userZoom;
        const imgDrawW = currentImg.width * finalScale;
        const imgDrawH = currentImg.height * finalScale;
        const startX = (canvas.width - imgDrawW) / 2 + offsetX;
        const startY = (canvas.height - imgDrawH) / 2 + offsetY;
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        return {
            x: (mouseX - startX) / finalScale,
            y: (mouseY - startY) / finalScale
        };
    }

    // =========================================================
    // ÇİZİM MOTORU (CANVAS RENDER)    // =========================================================
    // ÇİZİM MOTORU (CANVAS RENDER)
    // =========================================================

    function draw() {
        canvas.width = cont.clientWidth;
        canvas.height = cont.clientHeight;
        if (!currentImg) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const info = document.getElementById('info');
            if (info) info.textContent = 'Soldaki listeden bir şablon seçin.';
            const currentFile = document.getElementById('current-file');
            if (currentFile) currentFile.textContent = 'Görsel Seçin';
            return;
        }
        const padding = 40;
        const scaleX = (canvas.width - padding) / currentImg.width;
        const scaleY = (canvas.height - padding) / currentImg.height;
        baseScale = Math.min(scaleX, scaleY, 1);
        
        const finalScale = baseScale * userZoom;
        const imgDrawW = currentImg.width * finalScale;
        const imgDrawH = currentImg.height * finalScale;
        
        const startX = (canvas.width - imgDrawW) / 2 + offsetX;
        const startY = (canvas.height - imgDrawH) / 2 + offsetY;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.imageSmoothingEnabled = true;
        ctx.drawImage(currentImg, startX, startY, imgDrawW, imgDrawH);
        
        // 1. Baskı Yüzeyi Poligonu (Kırmızı)
        if (pts.length === 4) {
            ctx.beginPath();
            ctx.moveTo(startX + pts[0].x * finalScale, startY + pts[0].y * finalScale);
            for(let i=1; i<4; i++) ctx.lineTo(startX + pts[i].x * finalScale, startY + pts[i].y * finalScale);
            ctx.closePath();
            
            ctx.fillStyle = 'rgba(255, 0, 0, 0.0)'; // Tamamen seffaf (Gorseli engellememesi icin)
            ctx.fill();
            ctx.strokeStyle = '#ff3333';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Perspektif 3x3 Kılavuz Grid Çizgileri
            const gridSteps = 3;
            ctx.setLineDash([5, 4]);
            for (let step = 1; step < gridSteps; step++) {
                const t = step / gridSteps;
                // Dikey perspektif çizgileri (üstten alta)
                const topX = pts[0].x + (pts[1].x - pts[0].x) * t;
                const topY = pts[0].y + (pts[1].y - pts[0].y) * t;
                const botX = pts[3].x + (pts[2].x - pts[3].x) * t;
                const botY = pts[3].y + (pts[2].y - pts[3].y) * t;
                
                ctx.beginPath();
                ctx.moveTo(startX + topX * finalScale, startY + topY * finalScale);
                ctx.lineTo(startX + botX * finalScale, startY + botY * finalScale);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
                ctx.lineWidth = 1;
                ctx.stroke();

                // Yatay perspektif çizgileri (soldan sağa)
                const leftX = pts[0].x + (pts[3].x - pts[0].x) * t;
                const leftY = pts[0].y + (pts[3].y - pts[0].y) * t;
                const rightX = pts[1].x + (pts[2].x - pts[1].x) * t;
                const rightY = pts[1].y + (pts[2].y - pts[1].y) * t;
                
                ctx.beginPath();
                ctx.moveTo(startX + leftX * finalScale, startY + leftY * finalScale);
                ctx.lineTo(startX + rightX * finalScale, startY + rightY * finalScale);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
                ctx.lineWidth = 1;
                ctx.stroke();
            }
            ctx.setLineDash([]);
            
            // Köşe Noktaları ve Numaralandırma (1: Sol Üst, 2: Sağ Üst, 3: Sağ Alt, 4: Sol Alt)
            const cornerColors = ['#00e5ff', '#ffeb3b', '#ff4081', '#76ff03'];
            const cornerLabels = ['1: Sol Üst', '2: Sağ Üst', '3: Sağ Alt', '4: Sol Alt'];
            for(let i=0; i<4; i++) {
                const px = startX + pts[i].x * finalScale;
                const py = startY + pts[i].y * finalScale;
                
                ctx.beginPath();
                ctx.arc(px, py, 7, 0, Math.PI*2);
                ctx.fillStyle = cornerColors[i];
                ctx.fill();
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 2;
                ctx.stroke();

                // Numara Etiketi
                ctx.fillStyle = '#000';
                ctx.font = 'bold 10px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText((i + 1).toString(), px, py);

                // Köşe Adı
                ctx.fillStyle = cornerColors[i];
                ctx.font = 'bold 11px sans-serif';
                ctx.textAlign = (i === 1 || i === 2) ? 'left' : 'right';
                ctx.textBaseline = 'middle';
                const offX = (i === 1 || i === 2) ? 12 : -12;
                ctx.fillText(cornerLabels[i], px + offX, py);
            }
        }

        // CALIBRATION OVERLAY (Review Mode — controlled by showReviewOverlay)
        if (typeof showReviewOverlay !== 'undefined' && showReviewOverlay && pts.length === 4) {
            ctx.save();
            ctx.fillStyle = 'rgba(0, 255, 0, 0.25)';
            ctx.beginPath();
            ctx.moveTo(startX + pts[0].x * finalScale, startY + pts[0].y * finalScale);
            for(let i=1; i<4; i++) {
                ctx.lineTo(startX + pts[i].x * finalScale, startY + pts[i].y * finalScale);
            }
            ctx.closePath();
            ctx.fill();
            ctx.strokeStyle = '#00ff00';
            ctx.lineWidth = 3;
            ctx.stroke();
            ctx.restore();
        }

        drawAutomaticForegroundBoxes(startX, startY, finalScale);

        const info = document.getElementById('info');
        if (info) {
            const count = Array.isArray(foregroundMask.object_boxes)
                ? foregroundMask.object_boxes.length : 0;
            info.innerHTML =
                `Görsel: ${currentImg.width}x${currentImg.height} | Zoom: ${Math.round(userZoom*100)}% | Perspektif 4 köşe` +
                (count > 0 ? ` | Otomatik korunan nesne: ${count}` : '');
        }
    }

    function drawAutomaticForegroundBoxes(startX, startY, finalScale) {
        if (!Array.isArray(foregroundMask.object_boxes)) return;
        ctx.save();
        ctx.setLineDash([6, 4]);
        for (const box of foregroundMask.object_boxes) {
            if (!Array.isArray(box) || box.length !== 4) continue;
            const [x1, y1, x2, y2] = box;
            const sx = startX + x1 * finalScale;
            const sy = startY + y1 * finalScale;
            const sw = (x2 - x1) * finalScale;
            const sh = (y2 - y1) * finalScale;
            ctx.fillStyle = 'rgba(0,255,80,0.12)';
            ctx.fillRect(sx, sy, sw, sh);
            ctx.strokeStyle = '#00ff66';
            ctx.lineWidth = 2;
            ctx.strokeRect(sx, sy, sw, sh);
        }
        ctx.restore();
    }

    // =========================================================
    // FARE VE İŞARETÇİ ETKİLEŞİMLERİ (POINTER EVENTS)    // =========================================================
    // FARE VE İŞARETÇİ ETKİLEŞİMLERİ (POINTER EVENTS)
    // =========================================================

    canvas.addEventListener('contextmenu', e => e.preventDefault());

    canvas.addEventListener('pointerdown', function(e) {
        if (!currentImg) return;
        if (e.button === 2) {
            isPanning = true;
            panStartX = e.clientX - offsetX;
            panStartY = e.clientY - offsetY;
            updateCursor();
            return;
        }
        if (e.button !== 0 || pts.length !== 4) return;

        const rawPos = eventToRawImagePoint(e);
        if (!rawPos) return;
        const finalScale = baseScale * userZoom;
        let minDist = 22 / finalScale;
        draggingPoint = -1;
        for (let i = 0; i < 4; i++) {
            const dx = pts[i].x - rawPos.x;
            const dy = pts[i].y - rawPos.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < minDist) {
                minDist = dist;
                draggingPoint = i;
            }
        }
        if (draggingPoint !== -1) {
            try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
        }
    }, true);

    canvas.addEventListener('pointermove', function(e) {
        if (!currentImg) return;
        if (isPanning) {
            offsetX = e.clientX - panStartX;
            offsetY = e.clientY - panStartY;
            draw();
            return;
        }
        if (draggingPoint !== -1) {
            const rawPos = eventToRawImagePoint(e);
            if (!rawPos) return;
            pts[draggingPoint].x = Math.round(rawPos.x);
            pts[draggingPoint].y = Math.round(rawPos.y);
            updateDataFromPoints();
            draw();
        }
    }, true);

    canvas.addEventListener('pointerup', function(e) {
        if (e.button === 2) {
            isPanning = false;
            updateCursor();
            return;
        }
        draggingPoint = -1;
        try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
    }, true);

    canvas.addEventListener('pointercancel', function() {
        draggingPoint = -1;
        isPanning = false;
        updateCursor();
    }, true);

    // Klavye Kısayolları    // Klavye Kısayolları (C, V, Enter, Space, N, P)
    window.addEventListener('keydown', (e) => {
        if (e.target && e.target.tagName === 'INPUT') return;
        
        if (e.key === ' ' && !isSpacePressed) {
            e.preventDefault();
            isSpacePressed = true;
            if (!isPanning) {
                isPanning = true;
                panStartX = 0; // We will update this on pointermove if needed, but usually pointerdown starts it
                document.body.style.cursor = 'grab';
            }

        } else if (e.key.toLowerCase() === 'c' && pts.length === 4) {
            clipboardPts = JSON.parse(JSON.stringify(pts));
        } else if (e.key.toLowerCase() === 'v' && clipboardPts) {
            pts = JSON.parse(JSON.stringify(clipboardPts));
            updateDataFromPoints();
            saveAll(true); // Auto-save after paste
            draw();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            autoDetectCorners();
        } else if (e.key.toLowerCase() === 'n' || e.key === 'ArrowRight') {
            e.preventDefault();
            nextTemplate();
        } else if (e.key.toLowerCase() === 'p' || e.key === 'ArrowLeft') {
            e.preventDefault();
            prevTemplate();
        }
    });

    window.addEventListener('keyup', (e) => {
        if (e.key === ' ') {
            isSpacePressed = false;
            isPanning = false;
            updateCursor();
        }
    });

    // Zooming
    canvas.onwheel = (e) => {
        if (!currentImg) return;
        e.preventDefault();
        
        const zoomIntensity = 0.1;
        const wheel = e.deltaY < 0 ? 1 : -1;
        const zoomFactor = Math.exp(wheel * zoomIntensity);
        
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        
        const dx = mouseX - centerX;
        const dy = mouseY - centerY;
        
        const newZoom = userZoom * zoomFactor;
        
        offsetX = offsetX * zoomFactor - dx * (zoomFactor - 1);
        offsetY = offsetY * zoomFactor - dy * (zoomFactor - 1);
        
        userZoom = newZoom;
        draw();
    };
    
    // Double click to reset
    canvas.ondblclick = () => {
        resetView();
        draw();
    };
    
    window.onresize = draw;

    async function autoDetectForeground() {
        if (!currentCat || !currentTmpl || !currentImg) {
            alert("Lütfen önce bir şablon seçin.");
            return;
        }
        if (!pts || pts.length !== 4) {
            alert("AI ön plan analizi için önce 4 baskı köşesini doğrulayın.");
            return;
        }

        const btn = document.getElementById('btnAutoForeground');
        const originalText = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '⏳ AI Ön Plan Arıyor...';
        }

        try {
            const response = await fetch('/api/templates/foreground_detect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    category: currentCat,
                    template: currentTmpl,
                    corners: pts.map(p => [p.x, p.y])
                })
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'AI ön plan analizi başarısız.');
            }

            const detectedBoxes = Array.isArray(data.boxes) ? data.boxes : [];
            foregroundMask.object_boxes = detectedBoxes.map(
                box => box.slice(0, 4)
            );
            saveCurrentTemplateData();
            draw();

            if (detectedBoxes.length === 0) {
                alert('Baskının önünde korunması gereken güvenilir bir nesne bulunmadı.');
            } else {
                const confidence = Number(data.confidence || 0);
                alert(
                    detectedBoxes.length + ' ön plan nesnesi otomatik bulundu. ' +
                    'Yeşil kutuları gözle kontrol edin. Güven: ' +
                    confidence.toFixed(2)
                );
            }
        } catch (err) {
            alert('AI ön plan analizi kullanılamadı: ' + err.message);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        }
    }

    function autoDetectCorners() {
        if (!currentCat || !currentTmpl) {
            alert("Önce soldaki listeden bir şablon seçin.");
            return;
        }
        const btn = document.getElementById('btnAutoCorner');
        const origText = btn.innerHTML;
        btn.innerHTML = '⏳ Köşeler yeniden algılanıyor...';
        btn.disabled = true;

        fetch('/api/auto_detect_corners', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': currentCat,
                'X-Active-Template': currentTmpl
            },
            body: JSON.stringify({
                kategori: currentCat,
                sablon: currentTmpl
            })
        })
        .then(r => r.json())
        .then(res => {
            btn.innerHTML = origText;
            btn.disabled = false;
            if (res.success && res.corners && res.corners.length === 4) {
                pts = res.corners.map(p => ({x: p[0], y: p[1]}));
                updateDataFromPoints();
                draw();

                const modeLabels = {
                    BLACK: 'Siyah yüzey',
                    WHITE: 'Beyaz yüzey',
                    TRANSPARENT_GLASS: 'Şeffaf / saydam yüzey',
                    DESIGNED_TEXTURED: 'Desenli / tasarımlı yüzey',
                    UNKNOWN: 'Belirsiz yüzey'
                };
                const detectedMode = String(res.surface_mode || 'UNKNOWN');
                const modeLabel = modeLabels[detectedMode] || detectedMode;
                const modeConfidence = Number(res.surface_mode_confidence || 0);

                alert(
                    'Yeni köşe önerisi hazır.\n\n' +
                    'Algılanan zemin: ' + modeLabel +
                    (modeConfidence > 0
                        ? ' (güven: %' + Math.round(modeConfidence * 100) + ')'
                        : '') +
                    '\n\nKırmızı noktaları kontrol edin; doğruysa “Bu Şablonu Onayla”ya basın.'
                );
            } else {
                alert("Köşeler otomatik bulunamadı: " + (res.error || "Kırmızı noktaları “Köşeleri Elle Ayarla” ile yerleştirin."));
            }
        })
        .catch(err => {
            btn.innerHTML = origText;
            btn.disabled = false;
            alert("Sunucu baglanti hatasi: " + err);
        });
    }

    function restoreOriginal() {
        if (!currentCat || !currentTmpl) return;
        if (!confirm(
            'Bu işlem sadece görüntüleme değildir.\n\n' +
            'Korunmuş ham orijinal, aktif çalışma kopyasının yerine yazılacak. ' +
            'Mevcut onay/geometri kaydı yeniden kontrol gerektirebilir.\n\n' +
            'Devam edilsin mi?'
        )) return;

        fetch('/api/orijinal_yukle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': currentCat,
                'X-Active-Template': currentTmpl
            }
        }).then(r => r.json()).then(res => {
            if(res.success) {
                // A restored source is a new source identity. Never carry
                // foreground/mask evidence from the previous pixels.
                foregroundMask = {
                    object_boxes: [],
                    feather: 1.2,
                    grabcut_iterations: 5
                };
                const tmplObj = ayarlar?.kategoriler?.[currentCat]?.sablonlar?.[currentTmpl];
                if (tmplObj) {
                    delete tmplObj.on_plan;
                    delete tmplObj.on_plan_source_sha256;
                    tmplObj._review_status = 'STALE_SOURCE_CHANGED';
                    tmplObj._manually_verified = false;
                }

                loadSourceImage('working', () => {
                    alert(
                        'Ham orijinal çalışma kopyasına geri yüklendi. ' +
                        'Dört köşeyi kontrol edin; gerekirse çok küçük bir düzeltme yapın ve ' +
                        '“Bu Şablonu Onayla”ya basın. Sistem onayı yeni görsele bağlayacak.'
                    );
                });
            } else {
                alert(
                    "Orijinal yükleme başarısız: " +
                    (res.error || 'Bu görselin korunmuş ham yedeği bulunamadı.')
                );
            }
        }).catch(err => {
            alert('Orijinal yükleme bağlantı hatası: ' + err.message);
        });
    }

    function deleteTemplate() {
        if (!currentCat || !currentTmpl) return;
        if (!confirm('Bu şablon kullanımdan çıkarılacak ve geri alınabilir çöp alanına taşınacak. Devam edilsin mi?')) return;
        
        fetch('/api/sablon_sil', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': currentCat,
                'X-Active-Template': currentTmpl
            }
        }).then(r => r.json()).then(res => {
            if(res.success) {
                // Remove from ayarlar and UI
                delete ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
                renderSidebar();
                // Load next template
                const keys = Object.keys(ayarlar.kategoriler[currentCat].sablonlar);
                if (keys.length > 0) {
                    const nextTmpl = keys[0];
                    const nextElem = Array.from(
                        document.querySelectorAll('.template-item')
                    ).find(el => (
                        el.dataset.category === currentCat
                        && el.dataset.template === nextTmpl
                    )) || null;
                    loadTemplate(currentCat, nextTmpl, nextElem);
                } else {
                    currentTmpl = null;
                    currentImg = null;
                    draw();
                }
            } else {
                alert("Silme başarısız: " + (res.error || 'Bilinmeyen hata'));
            }
        });
    }

    function undoDelete() {
        fetch('/api/sablon_sil_geri_al', {
            method: 'POST'
        }).then(r => r.json()).then(res => {
            if(res.success) {
                // Reload ayarlar and UI
                fetch('/api/ayarlar')
                    .then(r => r.json())
                    .then(data => {
                        ayarlar = data;
                        renderSidebar();
                        alert("Şablon geri getirildi: " + res.restored_tmpl);
                    });
            } else {
                alert("Geri alma başarısız: " + (res.error || 'Çöpte dosya yok.'));
            }
        });
    }

    async function saveAll(silent = false) {
        if (currentCat && currentTmpl) {
            updateDataFromPoints();
            saveCurrentTemplateData();
        }
        const saveCat = currentCat;
        const saveTmpl = currentTmpl;
        if (!saveCat || !saveTmpl) return true;

        // Freeze the payload at click/navigation time so later UI changes can
        // never mutate an already in-flight save request.
        const currentData = JSON.parse(JSON.stringify(
            ayarlar.kategoriler[saveCat].sablonlar[saveTmpl]
        ));

        try {
            const response = await fetch('/api/tekil_sablon_kaydet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "kategori": saveCat,
                    "sablon": saveTmpl,
                    "data": currentData
                })
            });
            const res = await response.json();
            if (!res.success) {
                if (!silent) {
                    alert('Kaydetme hatası: ' + (res.error || 'Bilinmeyen hata'));
                }
                return false;
            }

            // Sadece manuel kaydetmede görseli yenile.
            if (saveCat && saveTmpl && !silent) {
                const stem = saveTmpl.replace(/\.[^.]+$/, '');
                const tempImg = new Image();
                tempImg.onload = () => {
                    if (saveCat === currentCat && saveTmpl === currentTmpl) {
                        currentImg = tempImg;
                        draw();
                    }
                };
                tempImg.src = '/image/' + encodeURIComponent(saveCat) + '/' +
                    encodeURIComponent(stem + '.png') + '?t=' + Date.now();
            }
            if (!silent) {
                alert('Değişiklikler aktif şablon veritabanına başarıyla kaydedildi.');
            }
            return true;
        } catch (err) {
            if (!silent) alert('Kaydetme hatası: ' + err);
            return false;
        }
    }

    // --- PANELLERI BOYUTLANDIRMA (RESIZER) ---
    function setupResizer(resizerId, panelId, isLeft) {
        const resizer = document.getElementById(resizerId);
        const panel = document.getElementById(panelId);
        if (!resizer || !panel) return;
        let startX, startWidth;

        resizer.addEventListener('mousedown', function(e) {
            startX = e.clientX;
            const style = window.getComputedStyle(panel);
            startWidth = parseInt(style.width, 10);
            document.documentElement.addEventListener('mousemove', doDrag, false);
            document.documentElement.addEventListener('mouseup', stopDrag, false);
            resizer.classList.add('active');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none'; // Secimi engelle
        });

        function doDrag(e) {
            let newWidth = isLeft ? startWidth + (e.clientX - startX) : startWidth - (e.clientX - startX);
            if (newWidth > 150 && newWidth < 800) {
                panel.style.width = newWidth + 'px';
                // Surekli guncellemek yerine ufak bir cizim tetikle (kasmamasi icin)
                draw();
            }
        }

        function stopDrag() {
            document.documentElement.removeEventListener('mousemove', doDrag, false);
            document.documentElement.removeEventListener('mouseup', stopDrag, false);
            resizer.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            // Son boyutlandirmadan sonra canvas'i tam ortaya oturt
            setTimeout(() => {
                resetView();
                draw();
            }, 50);
        }
    }
    
    // Sayfa yuklendikten kisa sure sonra aktif et
    setTimeout(() => {
        setupResizer('resizer-left', 'sidebar', true);
        setupResizer('resizer-right', 'right-toolbar', false);
        
    }, 500);

// --- TOPLU ANALIZ / ONAY SISTEMI ---
let batchAnalyzeRunning = false;

function ensureBatchAnalyzeProgressModal() {
    let overlay = document.getElementById('batchAnalyzeProgressOverlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'batchAnalyzeProgressOverlay';
    overlay.style.cssText = [
        'position:fixed',
        'inset:0',
        'background:rgba(0,0,0,.72)',
        'display:none',
        'align-items:center',
        'justify-content:center',
        'z-index:10000'
    ].join(';');

    overlay.innerHTML = `
        <div style="width:min(560px,92vw);background:#202020;border:1px solid #555;border-radius:12px;padding:22px;box-shadow:0 18px 60px rgba(0,0,0,.45);color:#fff;font-family:Arial,sans-serif;">
            <div id="batchAnalyzeTitle" style="font-size:20px;font-weight:700;margin-bottom:8px;">Şablonlar analiz ediliyor</div>
            <div id="batchAnalyzeSummary" style="font-size:14px;color:#ddd;margin-bottom:14px;">Hazırlanıyor...</div>
            <div style="height:18px;background:#3a3a3a;border-radius:999px;overflow:hidden;border:1px solid #555;">
                <div id="batchAnalyzeBar" style="height:100%;width:0%;background:#28a745;transition:width .18s ease;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;gap:12px;margin-top:8px;font-size:13px;color:#ddd;">
                <span id="batchAnalyzeCount">0 / 0</span>
                <span id="batchAnalyzePercent">%0</span>
            </div>
            <div id="batchAnalyzeCurrent" style="margin-top:14px;padding:10px;background:#151515;border-radius:7px;font-size:13px;word-break:break-word;color:#eee;">Bekleniyor...</div>
            <div id="batchAnalyzeErrors" style="display:none;margin-top:12px;padding:10px;background:#3a2020;border-radius:7px;font-size:12px;max-height:120px;overflow:auto;"></div>
            <button id="batchAnalyzeClose" type="button" style="display:none;width:100%;margin-top:16px;padding:11px;border:0;border-radius:7px;background:#28a745;color:white;font-weight:700;cursor:pointer;">Tamam</button>
        </div>
    `;

    document.body.appendChild(overlay);
    document.getElementById('batchAnalyzeClose').addEventListener('click', () => {
        overlay.style.display = 'none';
    });
    return overlay;
}

function updateBatchAnalyzeProgress(done, total, filename, statusText) {
    const overlay = ensureBatchAnalyzeProgressModal();
    const percent = total > 0 ? Math.round((done / total) * 100) : 0;
    document.getElementById('batchAnalyzeBar').style.width = percent + '%';
    document.getElementById('batchAnalyzeCount').textContent = done + ' / ' + total;
    document.getElementById('batchAnalyzePercent').textContent = '%' + percent;
    document.getElementById('batchAnalyzeSummary').textContent = statusText || 'Analiz devam ediyor...';
    document.getElementById('batchAnalyzeCurrent').textContent = filename
        ? 'İşlenen dosya: ' + filename
        : 'Hazırlanıyor...';
    overlay.style.display = 'flex';
}

function finishBatchAnalyzeProgress(total, successCount, failureCount, failures) {
    const overlay = ensureBatchAnalyzeProgressModal();
    document.getElementById('batchAnalyzeBar').style.width = '100%';
    document.getElementById('batchAnalyzeCount').textContent = total + ' / ' + total;
    document.getElementById('batchAnalyzePercent').textContent = '%100';
    document.getElementById('batchAnalyzeTitle').textContent =
        failureCount === 0 ? '✅ Analiz tamamlandı' : '⚠️ Analiz tamamlandı';
    document.getElementById('batchAnalyzeSummary').textContent =
        total + ' dosya işlendi • ' + successCount + ' başarılı • ' + failureCount + ' hatalı';
    document.getElementById('batchAnalyzeCurrent').textContent =
        failureCount === 0
            ? 'Klasör taraması başarıyla tamamlandı.'
            : 'Tarama tamamlandı; bazı dosyalar ayrıca kontrol edilmeli.';

    const errorBox = document.getElementById('batchAnalyzeErrors');
    if (failureCount > 0) {
        errorBox.style.display = 'block';
        errorBox.textContent = failures.slice(0, 8).join('\n');
    } else {
        errorBox.style.display = 'none';
        errorBox.textContent = '';
    }

    document.getElementById('batchAnalyzeClose').style.display = 'block';
    overlay.style.display = 'flex';
}

function chooseBatchAnalyzeCategory() {
    const categories = Object.keys(ayarlar?.kategoriler || {});
    if (categories.length === 0) {
        alert('Yeniden taranacak kategori bulunamadı.');
        return Promise.resolve(null);
    }

    return new Promise(resolve => {
        let overlay = document.getElementById('batch-category-chooser');
        if (overlay) overlay.remove();

        overlay = document.createElement('div');
        overlay.id = 'batch-category-chooser';
        overlay.style.cssText = [
            'position:fixed',
            'inset:0',
            'z-index:21000',
            'display:flex',
            'align-items:center',
            'justify-content:center',
            'padding:24px',
            'background:rgba(0,0,0,.72)'
        ].join(';');

        const dialog = document.createElement('div');
        dialog.style.cssText = [
            'width:min(560px,94vw)',
            'background:#202124',
            'color:#f1f3f4',
            'border:1px solid #555',
            'border-radius:12px',
            'padding:20px',
            'box-shadow:0 18px 60px rgba(0,0,0,.45)'
        ].join(';');

        const title = document.createElement('div');
        title.textContent = 'Hangi kategoriyi yeniden taramak istiyorsunuz?';
        title.style.cssText = 'font-size:18px;font-weight:700;margin-bottom:8px;';

        const note = document.createElement('div');
        note.innerHTML =
            'Yalnızca seçtiğiniz kategorinin otomatik 4 köşe tespiti yeniden çalıştırılır. ' +
            'Ham/orijinal görseller değişmez. Daha önce insan olarak onayladığınız ' +
            '<b>APPROVED</b> manuel geometri korunur.';
        note.style.cssText =
            'font-size:12px;line-height:1.5;color:#c7c7c7;margin-bottom:14px;';

        const select = document.createElement('select');
        select.style.cssText =
            'width:100%;padding:11px;border-radius:7px;background:#111315;color:#fff;' +
            'border:1px solid #666;font-size:14px;box-sizing:border-box;';

        categories.forEach(cat => {
            const option = document.createElement('option');
            const count = Object.keys(
                ayarlar?.kategoriler?.[cat]?.sablonlar || {}
            ).length;
            option.value = cat;
            option.textContent = cat + ' — ' + count + ' şablon';
            if (cat === currentCat) option.selected = true;
            select.appendChild(option);
        });

        const actions = document.createElement('div');
        actions.style.cssText =
            'display:flex;justify-content:flex-end;gap:10px;margin-top:16px;';

        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.textContent = 'İptal';
        cancel.style.cssText =
            'padding:10px 16px;background:#555;color:white;border:0;border-radius:7px;cursor:pointer;';

        const confirmButton = document.createElement('button');
        confirmButton.type = 'button';
        confirmButton.textContent = '🔍 Bu Kategoriyi Tara';
        confirmButton.style.cssText =
            'padding:10px 16px;background:#0d6efd;color:white;border:0;border-radius:7px;' +
            'font-weight:700;cursor:pointer;';

        const finish = value => {
            overlay.remove();
            resolve(value);
        };

        cancel.onclick = () => finish(null);
        confirmButton.onclick = () => finish(select.value || null);
        overlay.onclick = event => {
            if (event.target === overlay) finish(null);
        };

        actions.appendChild(cancel);
        actions.appendChild(confirmButton);
        dialog.appendChild(title);
        dialog.appendChild(note);
        dialog.appendChild(select);
        dialog.appendChild(actions);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        setTimeout(() => select.focus(), 0);
    });
}

async function batchAnalyze() {
    if(batchAnalyzeRunning) return;

    const category = await chooseBatchAnalyzeCategory();
    if(!category) return;

    const templates = Object.keys(
        ayarlar?.kategoriler?.[category]?.sablonlar || {}
    );
    if(templates.length === 0) {
        return alert("Seçtiğiniz kategoride analiz edilecek şablon bulunamadı.");
    }

    if(!confirm(
        category + " kategorisindeki " + templates.length +
        " şablonun otomatik 4 köşe tespiti yeniden çalıştırılacak.\n\n" +
        "Ham/orijinal görseller değişmez. Daha önce insan olarak onayladığınız " +
        "APPROVED manuel geometri korunur.\n\nDevam edilsin mi?"
    )) return;

    batchAnalyzeRunning = true;
    const button = document.getElementById('batchAnalyzeButton');
    if (button) {
        button.disabled = true;
        button.style.opacity = '0.55';
        button.style.cursor = 'wait';
    }

    const overlay = ensureBatchAnalyzeProgressModal();
    document.getElementById('batchAnalyzeTitle').textContent = 'Şablonlar analiz ediliyor';
    document.getElementById('batchAnalyzeClose').style.display = 'none';
    document.getElementById('batchAnalyzeErrors').style.display = 'none';

    let successCount = 0;
    let failureCount = 0;
    const failures = [];

    try {
        updateBatchAnalyzeProgress(0, templates.length, '', 'Tarama başlatılıyor...');

        for (let i = 0; i < templates.length; i++) {
            const tmpl = templates[i];
            updateBatchAnalyzeProgress(
                i,
                templates.length,
                tmpl,
                'Analiz ediliyor...'
            );

            try {
                const res = await fetch('/api/templates/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Active-Category': category,
                        'X-Active-Template': tmpl
                    },
                    body: JSON.stringify({})
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    successCount += 1;
                } else {
                    failureCount += 1;
                    failures.push(
                        tmpl + ': ' + (data.error || ('HTTP ' + res.status))
                    );
                }
            } catch (err) {
                failureCount += 1;
                failures.push(tmpl + ': ' + String(err));
            }

            updateBatchAnalyzeProgress(
                i + 1,
                templates.length,
                tmpl,
                'İlerleme: ' + (i + 1) + ' / ' + templates.length
            );
        }

        finishBatchAnalyzeProgress(
            templates.length,
            successCount,
            failureCount,
            failures
        );
    } finally {
        batchAnalyzeRunning = false;
        if (button) {
            button.disabled = false;
            button.style.opacity = '1';
            button.style.cursor = 'pointer';
        }
    }
}

async function approveTemplate() {
    if(!currentCat || !currentTmpl) return;
    let uid = currentCat + "_" + currentTmpl;
    // Use the global pts array from the canvas editor
    if (!pts || pts.length !== 4) return alert("Geçerli 4 köşe yok!");
    // Convert {x,y} objects to [[x,y],...] canonical format for DB/profile
    let canonicalCorners = pts.map(p => [p.x, p.y]);
    let physicalOrientation = '';
    if (currentCat === '04_Cam_Dograma') {
        const orientationSelect = document.getElementById('physicalOrientationSelect');
        physicalOrientation = String(
            orientationSelect ? orientationSelect.value : ''
        ).toUpperCase();
        if (physicalOrientation !== 'H' && physicalOrientation !== 'V') {
            return alert("Cam Doğrama için onaydan önce fiziksel yönü Yatay (H) veya Dikey (V) seçin.");
        }
    }
    
    try {
        let res = await fetch('/api/templates/update_corners', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                template_uid: uid,
                category: currentCat,
                template: currentTmpl,
                corners: canonicalCorners,
                physical_orientation: physicalOrientation,
                on_plan: cloneForegroundMask(),
                occlusion_reviewed: true
            })
        });
        let data = await res.json();
        if(data.success) {
            const tmplObj = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
            if (tmplObj) {
                tmplObj._review_status = 'APPROVED';
                tmplObj._manually_verified = true;
                if (data.orientation === 'H' || data.orientation === 'V') {
                    tmplObj.physical_orientation = data.orientation;
                    syncPhysicalOrientationControl(tmplObj);
                }
            }
            const currentItem = allTemplates.find(
                t => t.cat === currentCat && t.tmpl === currentTmpl
            );
            if (currentItem && currentItem.elem) {
                const label = currentItem.elem.querySelector('.template-item-label');
                if (label) label.textContent = '✅ ' + currentTmpl;
                currentItem.elem.title = 'İnsan onaylı ve üretime uygun profil.';
                currentItem.elem.style.backgroundColor = '';
                currentItem.elem.style.color = '';
            }
            alert("Şablon onaylandı. Artık üretimde kullanılabilir.");
        } else {
            alert("Hata: " + data.error);
        }
    } catch(e) {
        alert("Bağlantı hatası: " + e);
    }
}

let showReviewOverlay = false;
function toggleReviewOverlay() {
    showReviewOverlay = !showReviewOverlay;
    draw(); // Redraw canvas with or without overlay
}


