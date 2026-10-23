window.onerror = function(msg, url, line, col, error) {
        showMessage("JS ERROR: " + msg + "\\nLine: " + line);
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

    function showMessage(message, title = 'Bilgi / Uyarı') {
        showCopyableReport(
            String(title || 'Bilgi / Uyarı'),
            String(message ?? '')
        );
    }

    function formatStagingCollisionWarning(collision) {
        const identity = collision?.identity_conflict || null;
        const number = collision?.number_conflict || null;
        const lines = [
            'STAGING GÜVENLİK UYARISI',
            'İşlem: ' + String(collision?.transaction_id || ''),
            'Zaman: ' + String(collision?.updated_at || ''),
            ''
        ];

        if (identity) {
            lines.push(
                identity.different_extension_present
                    ? '⛔ AYNI İSİM, FARKLI UZANTI'
                    : '⛔ AYNI İSİM / AYNI UZANTI'
            );
            lines.push(
                'Gelen: ' + String(identity.incoming_name || ''),
                'Kategori: ' + String(identity.category || ''),
                'Kimlik: ' + String(identity.identity || ''),
                'Gelen uzantı: ' +
                    String(identity.incoming_extension || 'YOK'),
                'Sistemdeki uzantılar: ' +
                    (identity.existing_extensions || []).join(', '),
                '',
                'Eşleşmeler:'
            );
            (identity.matches || []).forEach(row => {
                lines.push(
                    '• ' + String(row.location || '') +
                    ' — ' + String(row.name || '') +
                    (
                        row.path
                            ? ' [' + String(row.path) + ']'
                            : ''
                    )
                );
            });
        } else if (number) {
            lines.push(
                '⛔ NUMARA KİMLİĞİ ÇAKIŞMASI',
                'Gelen: ' + String(number.incoming_name || ''),
                'Kategori: ' + String(number.category || ''),
                'İstenen numara: ' +
                    String(number.requested_number ?? ''),
                'Gelen uzantı: ' +
                    String(number.incoming_extension || 'YOK'),
                'Önerilen yeni numara: ' +
                    String(number.suggested_number ?? '')
            );
        }

        lines.push(
            '',
            'SONUÇ:',
            'Yeni şablon oluşturulmadı.',
            'Gelen dosya silinmedi veya yeniden adlandırılmadı; staging klasöründe bırakıldı.'
        );
        if (!identity && !number && collision?.error) {
            lines.push('', 'Detay:', String(collision.error));
        }
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
            try {
                lastSeen = localStorage.getItem(storageKey) || '';
            } catch (err) {
                lastSeen = '';
            }
            if (lastSeen === id) return;

            try {
                localStorage.setItem(storageKey, id);
            } catch (err) {
                // Warning still remains visible even if localStorage is blocked.
            }

            showCopyableReport(
                '⛔ Staging İsim / Uzantı Çakışması',
                formatStagingCollisionWarning(collision)
            );
        } catch (err) {
            console.warn('Staging çakışma uyarısı okunamadı:', err);
        }
    }

    function startStagingCollisionPolling() {
        if (stagingCollisionPollTimer) return;
        pollLatestStagingCollision();
        stagingCollisionPollTimer = window.setInterval(
            pollLatestStagingCollision,
            2500
        );
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
                    const guidance = data.doctor_guidance || {};
                    const recommendations = Array.isArray(guidance.recommendations)
                        ? guidance.recommendations : [];
                    const guidanceText = recommendations.map(item =>
                        "[" + (item.code || "BİLGİ") + "] " + (item.title || "") + "\n" +
                        "Anlamı: " + (item.explanation || "") + "\n" +
                        "Güvenli adım: " + (item.action || "") + "\n" +
                        "Dayanak: " + (item.evidence || "")
                    ).join("\n\n");
                    const reportText =
                        "KRİTİK SORUNLAR:\n" + (data.sorunlar || []).join("\n") +
                        "\n\nUYARILAR (OTOMATİK ONARIM YAPILMAZ):\n" + (data.uyarilar || []).join("\n") +
                        "\n\nUYARILARIN AÇIKLAMASI VE GÜVENLİ ADIMLAR:\n" + (guidanceText || "Ek açıklama yok.") +
                        "\n\nDOKTORUN PYTHON ORTAMI:\n" + (guidance.interpreter || "Bilinmiyor") +
                        "\nPython sürümü: " + (guidance.python_version || "Bilinmiyor") +
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
    let templateHealthSnapshot = null;
    let workspaceConsistencySnapshot = null;
    let workspaceAuditJobId = null;
    let templateLoadToken = 0;
    
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
        } else if (sourceViewMode === 'preview') {
            el.innerHTML = '🟡 <b>SADECE BEYAZLATMA ÖNİZLEMESİ.</b> Çalışma, orijinal ve onay değişmedi.';
            el.style.borderColor = '#eab308';
        } else {
            el.innerHTML = '🟢 <b>Çalışma görseli gösteriliyor.</b> Sistem işlemlerinde kullanılan aktif kopya budur.';
            el.style.borderColor = '#2e7d32';
        }
    }

    function loadSourceImage(mode, onSuccess = null) {
        if (!currentCat || !currentTmpl) return;
        const requestCat = currentCat;
        const requestTmpl = currentTmpl;
        const requestToken = templateLoadToken;
        const img = new Image();
        img.onload = () => {
            if (
                requestToken !== templateLoadToken
                || requestCat !== currentCat
                || requestTmpl !== currentTmpl
            ) return;
            currentImg = img;
            originalImgObj = img;
            sourceViewMode = mode;
            updateSourceViewStatus();
            resetView();
            draw();
            if (typeof onSuccess === 'function') onSuccess();
        };
        img.onerror = () => {
            if (
                requestToken !== templateLoadToken
                || requestCat !== currentCat
                || requestTmpl !== currentTmpl
            ) return;
            const label = mode === 'original'
                ? 'Ham orijinal yedek'
                : 'Çalışma görseli';
            showMessage(
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

    async function showIsolatedWhitePreview() {
        if (!currentCat || !currentTmpl) {
            showMessage('Önce bir şablon seçin.');
            return;
        }
        const requestCat = currentCat;
        const requestTmpl = currentTmpl;
        try {
            const response = await fetch('/api/anlik_beyazlat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Active-Category': requestCat,
                    'X-Active-Template': requestTmpl
                },
                body: JSON.stringify({kategori: requestCat, sablon: requestTmpl})
            });
            const result = await response.json();
            if (!response.ok || !result.success || !result.preview_only) {
                showMessage('Beyazlatma önizlemesi başarısız: ' + (result.error || response.status));
                return;
            }
            const img = new Image();
            img.onload = () => {
                if (currentCat !== requestCat || currentTmpl !== requestTmpl) return;
                currentImg = img;
                originalImgObj = img;
                sourceViewMode = 'preview';
                updateSourceViewStatus();
                resetView();
                draw();
            };
            img.onerror = () => showMessage('Önizleme görseli yüklenemedi; çalışma dosyası değişmedi.');
            img.src = result.preview_url + '?t=' + Date.now();
        } catch (error) {
            showMessage('Beyazlatma sunucu hatası: ' + error);
        }
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
        const approveButton = document.getElementById('bulkApproveButton');
        if (approveButton) {
            approveButton.disabled = count === 0;
            approveButton.style.opacity = count === 0 ? '0.55' : '1';
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
            showMessage('Önce soldan bir kategori başlığına veya şablona tıklayın.');
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

    // Multi-approval MUST use the existing source-hash-bound human endpoint.
    // No new approve-by-filename shortcuts or implicit selection of unseen geometry.
    async function bulkApproveSelected() {
        const selected = Array.from(bulkSelectedTemplates).map(parseBulkTemplateKey)
            .filter(([cat, tmpl]) => cat && tmpl && ayarlar?.kategoriler?.[cat]?.sablonlar?.[tmpl]);
        if (!selected.length) return showMessage('Önce onaylanacak şablonları işaretleyin.');
        if (currentCat && currentTmpl) {
            if (!await saveAll(true)) {
                return showMessage('Açık şablon kaydedilemedi. Toplu onay durduruldu.');
            }
        }
        const approved = [], failed = [];
        // Fetch again: current editor state may have changed since checkbox selection.
        try {
            const fresh = await fetch('/api/ayarlar', {cache:'no-store'});
            if (!fresh.ok) throw new Error('Onay öncesi kayıtlar okunamadı.');
            ayarlar = await fresh.json();
        } catch (error) { return showMessage('Toplu onay: ' + error.message); }
        const candidates = selected.map(([cat, tmpl]) => {
            const data = ayarlar?.kategoriler?.[cat]?.sablonlar?.[tmpl];
            const quad = data?.koseler;
            const valid = Array.isArray(quad) && quad.length === 4 &&
              quad.every(p => Array.isArray(p) && p.length === 2 && p.every(n => Number.isFinite(Number(n))));
            let orientation = String(data?.physical_orientation || '').toUpperCase();
            if (cat === '04_Cam_Dograma' && !['H','V'].includes(orientation)) orientation = '';
            return {cat, tmpl, data, quad, valid, orientation};
        });
        const ready = candidates.filter(x => x.valid && !isBatchAnalyzingTemplate(x.cat, x.tmpl));
        for (const x of candidates) if (!ready.includes(x)) {
            failed.push(`${x.cat}/${x.tmpl}: ${!x.valid ? 'Kaydedilmiş 4 köşe yok' : 'Tarama sürüyor'}`);
        }
        if (!ready.length) return showMessage('Toplu onay için geçerli kayıtlı dört köşe bulunamadı.\n' + failed.join('\n'));
        if (!confirm(`${ready.length} şablon, her biri ayrı kontrol edilerek onaylanacak.\n${failed.length} şablon atlanacak.\nDevam edilsin mi?`)) return;
        const btn = document.getElementById('bulkApproveButton');
        if (btn) {btn.disabled=true; btn.textContent='⏳ Onaylanıyor...';}
        try {
            for (const x of ready) {
                try {
                    const response = await fetch('/api/templates/update_corners', {
                        method:'POST', headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({template_uid:x.cat+'_'+x.tmpl,category:x.cat,
                          template:x.tmpl,corners:x.quad,physical_orientation:x.orientation,
                          // Bulk approval cannot assert that uninspected foreground is safe.
                          // The source-hash-bound endpoint rejects stale identities.
                          bulk_approval:true, occlusion_reviewed:false})
                    });
                    const result = await response.json();
                    if (!response.ok || !result.success) throw new Error(result.error || `HTTP ${response.status}`);
                    approved.push(`${x.cat}/${x.tmpl}`);
                    bulkSelectedTemplates.delete(bulkTemplateKey(x.cat,x.tmpl));
                } catch (error) {failed.push(`${x.cat}/${x.tmpl}: ${error.message}`);}
            }
            const refreshed = await fetch('/api/ayarlar', {cache:'no-store'});
            if (!refreshed.ok) throw new Error('Liste yenilenemedi; sayfayı yenileyin.');
            ayarlar = await refreshed.json();
            renderSidebar();
            if (typeof refreshReviewSettingsAfterJob === 'function') await refreshReviewSettingsAfterJob();
            const current = allTemplates.find(x => x.cat === currentCat && x.tmpl === currentTmpl);
            if (current) loadTemplate(currentCat,currentTmpl,current.elem);
            const msg = `Toplu onay: ${approved.length} başarılı, ${failed.length} kontrol gerekiyor.` +
                (failed.length ? '\n\n' + failed.slice(0,30).join('\n') : '');
            showMessage(msg);
        } catch (error) {showMessage('Toplu onay listesi: '+error.message);}
        finally { if (btn) {btn.textContent='✅ Seçilenleri Toplu Onayla'; btn.disabled=bulkSelectedTemplates.size===0;} updateBulkSelectedCount();}
    }

    async function bulkDeleteSelected() {
        const selected = Array.from(bulkSelectedTemplates)
            .map(parseBulkTemplateKey)
            .filter(([cat, tmpl]) => (
                cat && tmpl
                && ayarlar?.kategoriler?.[cat]?.sablonlar?.[tmpl]
            ));

        if (selected.length === 0) {
            showMessage('Önce çöpe atılacak şablonları işaretleyin.');
            return;
        }

        const currentlyAnalyzed = selected.filter(([cat, tmpl]) =>
            isBatchAnalyzingTemplate(cat, tmpl)
        );
        const safeSelected = selected.filter(([cat, tmpl]) =>
            !isBatchAnalyzingTemplate(cat, tmpl)
        );

        if (safeSelected.length === 0) {
            showMessage(
                'Seçtiğiniz şablon şu anda toplu tarama tarafından işleniyor. ' +
                'Birkaç saniye sonra tekrar deneyin.'
            );
            return;
        }

        const scanNote = currentlyAnalyzed.length
            ? '\n\nNot: Şu anda taranan ' + currentlyAnalyzed.length +
              ' şablon bu işlemde atlanacak ve seçili kalacak.'
            : '';

        if (!confirm(
            safeSelected.length +
            ' şablon aktif kullanımdan çıkarılıp geri alınabilir çöp alanına taşınacak.' +
            scanNote +
            '\n\nDevam edilsin mi?'
        )) return;

        if (batchAnalyzeRunning) {
            batchAnalyzeExternalPause = true;
        }

        const button = document.getElementById('bulkDeleteButton');
        const countLabel = document.getElementById('bulkSelectedCount');
        const originalText = button ? button.textContent : '';

        if (button) {
            button.disabled = true;
            button.textContent = '⏳ Seçilenler çöpe taşınıyor...';
        }
        if (countLabel) {
            countLabel.textContent =
                safeSelected.length + ' şablon işleniyor...';
        }

        try {
            const response = await fetch('/api/sablon_sil_toplu', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    items: safeSelected.map(([category, template]) => ({
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

            showMessage(
                'Toplu işlem tamamlandı.\n' +
                Number(data.deleted_count || deleted.length) +
                ' şablon çöpe taşındı.' +
                (failed.length
                    ? '\n' + failed.length + ' şablon silinemedi.'
                    : '') +
                failedText +
                (currentlyAnalyzed.length
                    ? '\n\n' + currentlyAnalyzed.length +
                      ' şablon o anda tarandığı için atlandı; seçili bırakıldı.'
                    : '')
            );
            refreshTemplateHealth(false, false);
        } catch (err) {
            showMessage('Toplu silme başarısız: ' + err.message);
        } finally {
            batchAnalyzeExternalPause = false;
            if (button) {
                button.textContent =
                    originalText || '🗑️ Seçilenleri Çöpe At';
                button.disabled = bulkSelectedTemplates.size === 0;
            }
            updateBulkSelectedCount();
        }
    }

    function getTemplateHealth(cat, tmpl) {
        return (
            templateHealthSnapshot
            && templateHealthSnapshot.templates
            && templateHealthSnapshot.templates[cat]
            && templateHealthSnapshot.templates[cat][tmpl]
        ) || null;
    }

    function getWorkspaceTemplateState(cat, tmpl) {
        return (
            workspaceConsistencySnapshot
            && workspaceConsistencySnapshot.templates
            && workspaceConsistencySnapshot.templates[cat]
            && workspaceConsistencySnapshot.templates[cat][tmpl]
        ) || null;
    }

    function formatWorkspaceConsistencyReport(data) {
        const summary = data?.summary || {};
        const diff = data?.diff || {};
        const lines = [
            'KLASÖR / DOSYA TUTARLILIK RAPORU — READ ONLY',
            data?.saved_at
                ? 'Kayıt zamanı: ' + data.saved_at
                : (
                    data?.generated_at
                        ? 'Tarama zamanı: ' + data.generated_at
                        : ''
                ),
            'Runtime: ' + String(data?.runtime_root || ''),
            '',
            'GÜVENLİK:',
            '• Bu tarama kullanıcı görsellerini silmez, taşımaz, yeniden adlandırmaz veya değiştirmez.',
            '• Aktif eşitlik kuralı: DB ↔ Çalışma ↔ Ham/Orijinal kimliği 1:1 olmalıdır.',
            '• Staging, çöp ve recovery aktif eşitlik kümesine dahil değildir.',
            '',
            'ÖZET:',
            'Aktif DB: ' + Number(summary.active_db_total || 0),
            'Tam eşleşen aktif: ' +
                Number(summary.fully_matched_active_total || 0),
            'Aktif eşleşme sorunu: ' +
                Number(summary.active_mismatch_total || 0),
            'Aktif bütünlük bulgusu: ' +
                Number(summary.active_integrity_issue_count || 0),
            'Çalışma havuzu hijyen bulgusu: ' +
                Number(summary.working_hygiene_count || 0),
            'Duplicate kimlik bulgusu: ' +
                Number(summary.duplicate_hygiene_count || 0),
            'Ham arşiv envanter fazlası: ' +
                Number(summary.archive_inventory_count || 0),
            'Toplam kayıtlı bulgu: ' + Number(summary.issue_count || 0),
            'Kritik: ' + Number(summary.critical_count || 0),
            'Uyarı: ' + Number(summary.warning_count || 0),
            'Bilgi/envanter: ' + Number(summary.info_count || 0),
            'Kaggle görevli klasörü: ' +
                Number(summary.kaggle_folder_count || 0),
            'Mockup görevli klasörü: ' +
                Number(summary.mockup_folder_count || 0),
            'Tüm üst seviye klasör: ' +
                Number(summary.top_level_folder_count || 0),
            'Henüz sınıflandırılmamış üst klasör: ' +
                Number(summary.unclassified_top_level_count || 0),
            'Çöp dosyası: ' + Number(summary.trash_file_count || 0),
            'Recovery dosyası: ' +
                Number(summary.recovery_file_count || 0),
            ''
        ];

        if (diff.has_previous) {
            lines.push(
                'ÖNCEKİ RAPORA GÖRE:',
                'Önceki kayıt: ' + String(diff.previous_saved_at || ''),
                'Yeni sorun: ' + Number(diff.new_issue_count || 0),
                'Düzelen sorun: ' + Number(diff.resolved_issue_count || 0),
                'Devam eden sorun: ' +
                    Number(diff.unchanged_issue_count || 0),
                ''
            );
        } else {
            lines.push(
                'ÖNCEKİ RAPORA GÖRE:',
                'Bu ilk kayıtlı tutarlılık raporu.',
                ''
            );
        }

        lines.push('KATEGORİLER:');
        Object.keys(data?.categories || {}).sort().forEach(cat => {
            const row = data.categories[cat] || {};
            lines.push(
                '• ' + cat +
                ' | DB=' + Number(row.db_count || 0) +
                ' | Çalışma=' + Number(row.working_identity_count || 0) +
                ' | Ham=' + Number(row.backup_identity_count || 0) +
                ' | Staging=' + Number(row.staging_identity_count || 0) +
                ' | Tam=' + Number(row.fully_matched_active_count || 0) +
                ' | AktifSorun=' +
                    Number(row.active_integrity_issue_count || 0) +
                ' | ArşivEkstra=' +
                    Number(row.archive_inventory_count || 0) +
                ' | Hijyen=' +
                    (
                        Number(row.working_hygiene_count || 0) +
                        Number(row.duplicate_hygiene_count || 0)
                    )
            );
        });

        lines.push('', 'KLASÖR GÖREV / REFERANS AUDITİ:');
        (data?.folders || []).forEach(row => {
            const inv = row.inventory || {};
            lines.push(
                '• ' + row.folder +
                ' [' + row.role + ']' +
                ' | var=' + (row.exists ? 'EVET' : 'HAYIR') +
                ' | dosya=' + Number(inv.file_count || 0) +
                ' | görsel=' + Number(inv.image_count || 0) +
                ' | aktif-kod-ref=' +
                    Number(row.runtime_code_reference_count || 0) +
                ' | tüm-ref=' +
                    Number(row.code_reference_count || 0)
            );
            lines.push('  Görev: ' + String(row.expected_contract || ''));
            if ((row.runtime_code_reference_files || []).length) {
                lines.push(
                    '  Aktif kod örnekleri: ' +
                    row.runtime_code_reference_files.join(', ')
                );
            }
        });

        lines.push('', 'KAGGLE KLASÖRLERİ:');
        if ((data?.kaggle_folders || []).length) {
            data.kaggle_folders.forEach(row => {
                lines.push(
                    '• ' + row.folder +
                    ' [' + String(row.role || '') + ']' +
                    ' | dosya=' +
                    Number(row.inventory?.file_count || 0) +
                    ' | aktif-kod-ref=' +
                    Number(row.runtime_code_reference_count || 0)
                );
            });
        } else {
            lines.push('Bulunamadı.');
        }

        lines.push('', 'MOCKUP KLASÖRLERİ:');
        if ((data?.mockup_folders || []).length) {
            data.mockup_folders.forEach(row => {
                lines.push(
                    '• ' + row.folder +
                    ' [' + String(row.role || '') + ']' +
                    ' | dosya=' +
                    Number(row.inventory?.file_count || 0) +
                    ' | aktif-kod-ref=' +
                    Number(row.runtime_code_reference_count || 0)
                );
            });
        } else {
            lines.push('Bulunamadı.');
        }

        lines.push('', 'AKTİF BÜTÜNLÜK / HİJYEN / ENVANTER BULGULARI:');
        const issues = Array.isArray(data?.issues) ? data.issues : [];
        if (!issues.length) {
            lines.push('Yok.');
        } else {
            issues.forEach(item => {
                lines.push(
                    '[' + String(item.severity || 'INFO') +
                    ' / ' + String(item.scope || 'GENEL') + '] ' +
                    String(item.category || '-') + ' / ' +
                    String(item.identity || '-') + ' — ' +
                    String(item.label || item.code || '')
                );
                if (item.details) {
                    lines.push('  ' + String(item.details));
                }
            });
        }

        lines.push(
            '',
            'NOT: Bu rapor düzeltme yapmaz. Eşitleme işlemleri Grup 2’de ayrıca ve geri alınabilir olarak geliştirilecektir.'
        );
        return lines.join('\n');
    }

    function formatWorkspaceHistory(data) {
        const rows = Array.isArray(data?.history) ? data.history : [];
        const lines = [
            'KLASÖR TUTARLILIK RAPOR GEÇMİŞİ',
            ''
        ];
        if (!rows.length) {
            lines.push('Henüz kayıtlı rapor yok.');
            return lines.join('\n');
        }
        rows.forEach((row, index) => {
            lines.push(
                (index + 1) + '. ' +
                String(row.saved_at || row.generated_at || row.file || '') +
                ' | Aktif=' + Number(row.active_db_total || 0) +
                ' | Tam=' +
                    Number(row.fully_matched_active_total || 0) +
                ' | AktifSorun=' +
                    Number(row.active_integrity_issue_count || 0) +
                ' | Arşiv=' + Number(row.archive_inventory_count || 0) +
                ' | Hijyen=' +
                    (
                        Number(row.working_hygiene_count || 0) +
                        Number(row.duplicate_hygiene_count || 0)
                    ) +
                ' | Kaggle=' + Number(row.kaggle_folder_count || 0) +
                ' | Mockup=' + Number(row.mockup_folder_count || 0) +
                ' | Sınıfsız=' +
                    Number(row.unclassified_top_level_count || 0)
            );
        });
        return lines.join('\n');
    }

    function formatTemplateHealthHistory(data) {
        const rows = Array.isArray(data?.history) ? data.history : [];
        const lines = [
            'HAM DOSYA SAĞLIK RAPOR GEÇMİŞİ',
            ''
        ];