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
        const img = new Image();
        img.onload = () => {
            if (
                requestCat !== currentCat
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
                requestCat !== currentCat
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
        if (!rows.length) {
            lines.push('Henüz kayıtlı sağlık raporu yok.');
            return lines.join('\n');
        }
        rows.forEach((row, index) => {
            const diff = row.diff || {};
            lines.push(
                (index + 1) + '. ' + String(row.saved_at || row.file || '') +
                ' | Toplam=' + Number(row.total_records || 0) +
                ' | Sağlam=' + Number(row.ok || 0) +
                ' | Uyarı=' + Number(row.warning || 0) +
                ' | Kritik=' + Number(row.critical || 0) +
                (
                    diff.has_previous
                        ? ' | Yeni=' + Number(diff.new_issue_count || 0) +
                          ' | Düzelen=' +
                            Number(diff.resolved_issue_count || 0)
                        : ''
                )
            );
        });
        return lines.join('\n');
    }

    function ensureWorkspaceAuditProgress() {
        let card = document.getElementById('workspace-audit-progress');
        if (card) return card;

        card = document.createElement('div');
        card.id = 'workspace-audit-progress';
        card.style.cssText = [
            'position:fixed',
            'right:18px',
            'bottom:18px',
            'z-index:22000',
            'width:min(430px,calc(100vw - 36px))',
            'background:#202124',
            'color:#fff',
            'border:1px solid #555',
            'border-radius:10px',
            'padding:14px',
            'box-shadow:0 12px 40px rgba(0,0,0,.45)',
            'display:none'
        ].join(';');
        card.innerHTML = `
            <div style="font-weight:700;margin-bottom:8px;">🧭 Klasör Tutarlılık Taraması</div>
            <div id="workspace-audit-message" style="font-size:12px;color:#ddd;margin-bottom:8px;">Hazırlanıyor...</div>
            <div style="height:14px;background:#3b3b3b;border-radius:999px;overflow:hidden;">
                <div id="workspace-audit-bar" style="height:100%;width:0%;background:#16a34a;transition:width .2s ease;"></div>
            </div>
            <div id="workspace-audit-count" style="font-size:11px;color:#bbb;margin-top:6px;">0 / 8</div>
            <div style="display:flex;gap:8px;margin-top:10px;">
                <button type="button" id="workspace-audit-stop" style="flex:1;padding:8px;background:#b02a37;color:white;border:0;border-radius:6px;cursor:pointer;">⏹ Durdur</button>
                <button type="button" id="workspace-audit-hide" style="flex:1;padding:8px;background:#374151;color:white;border:0;border-radius:6px;cursor:pointer;">↘ Gizle</button>
            </div>
        `;
        document.body.appendChild(card);

        card.querySelector('#workspace-audit-hide').onclick = () => {
            card.style.display = 'none';
        };
        card.querySelector('#workspace-audit-stop').onclick = async () => {
            if (!workspaceAuditJobId) return;
            const stop = card.querySelector('#workspace-audit-stop');
            stop.disabled = true;
            stop.textContent = '⏳ Durduruluyor...';
            try {
                await fetch(
                    '/api/jobs/' +
                    encodeURIComponent(workspaceAuditJobId) +
                    '/stop',
                    {method: 'POST'}
                );
            } catch (err) {
                console.warn('Audit stop isteği gönderilemedi:', err);
            }
        };
        return card;
    }

    function updateWorkspaceAuditProgress(job) {
        const card = ensureWorkspaceAuditProgress();
        const current = Number(job?.progress_current || 0);
        const total = Math.max(1, Number(job?.progress_total || 8));
        const percent = Math.max(
            0,
            Math.min(100, Math.round((current / total) * 100))
        );
        card.querySelector('#workspace-audit-bar').style.width =
            percent + '%';
        card.querySelector('#workspace-audit-count').textContent =
            current + ' / ' + total + ' — %' + percent;
        card.querySelector('#workspace-audit-message').textContent =
            job?.progress_message || 'Read-only tarama devam ediyor...';
        card.style.display = 'block';
    }

    function formatTemplateHealthReport(data) {
        const summary = data?.summary || {};
        const lines = [
            'HAM / ÇALIŞMA DOSYASI SAĞLIK TARAMASI',
            data?.saved_at
                ? 'Kayıt zamanı: ' + data.saved_at
                : (
                    data?.generated_at
                        ? 'Tarama zamanı: ' + data.generated_at
                        : ''
                ),
            data?.saved_report
                ? 'Bu rapor son manuel tam taramanın kalıcı kaydıdır.'
                : '',
            '',
            'Toplam kayıt: ' + Number(summary.total_records || 0),
            'Sağlam: ' + Number(summary.ok || 0),
            'Uyarı / insan kontrolü: ' + Number(summary.warning || 0),
            'Kritik: ' + Number(summary.critical || 0),
            'DB kaydı olmayan çalışma dosyası: ' +
                Number(summary.filesystem_only_working || 0),
            'DB kaydı olmayan ham yedek: ' +
                Number(summary.filesystem_only_backup || 0),
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
                lines.push(
                    '[' + info.severity + '] ' +
                    cat + ' / ' + tmpl + ' — ' +
                    (info.label || info.code || 'Kontrol gerekli')
                );
                (info.details || []).forEach(detail => {
                    lines.push('  • ' + detail);
                });
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
                'Devam eden sorun: ' +
                    Number(diff.unchanged_issue_count || 0)
            );
        } else {
            lines.push('Bu ilk kayıtlı sağlık raporu.');
        }

        const extraWorking = data?.filesystem_only_working || [];
        const extraBackup = data?.filesystem_only_backup || [];

        lines.push('', 'DB KAYDI OLMAYAN ÇALIŞMA DOSYALARI:');
        if (extraWorking.length) {
            extraWorking.forEach(item => {
                lines.push('  • ' + item.category + ' / ' + item.filename);
            });
        } else {
            lines.push('Yok.');
        }

        lines.push('', 'DB KAYDI OLMAYAN HAM YEDEKLER:');
        if (extraBackup.length) {
            extraBackup.forEach(item => {
                lines.push('  • ' + item.category + ' / ' + item.filename);
            });
        } else {
            lines.push('Yok.');
        }

        return lines.join('\n');
    }

    async function refreshTemplateHealth(
        deep = false,
        showReport = false,
        persist = false
    ) {
        try {
            const response = await fetch(
                '/api/template-health?deep=' + (deep ? '1' : '0') +
                '&save=' + (persist ? '1' : '0')
            );
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || ('HTTP ' + response.status));
            }
            templateHealthSnapshot = data;
            if (ayarlar) renderSidebar();
            if (showReport) {
                showCopyableReport(
                    data.saved_report
                        ? 'Ham Dosya Sağlık Taraması — Kaydedildi'
                        : 'Ham Dosya Sağlık Taraması',
                    formatTemplateHealthReport(data)
                );
            }
            return data;
        } catch (err) {
            if (showReport) {
                showMessage('Ham dosya sağlık taraması başarısız: ' + err.message);
            }
            return null;
        }
    }

    async function monitorHealthScanJob(jobId, showReport = true) {
        healthScanJobId = jobId;
        const button = document.getElementById('templateHealthScanButton');
        const originalText = button ? button.textContent : '';
        if (button) {
            button.disabled = true;
            button.textContent = '⏳ Ham dosyalar kontrol ediliyor...';
        }

        try {
            while (true) {
                const response = await fetch(
                    '/api/jobs/' + encodeURIComponent(jobId)
                );
                const data = await response.json();
                if (!response.ok || !data.success || !data.job) {
                    throw new Error(
                        data.error || ('HTTP ' + response.status)
                    );
                }

                const job = data.job;
                const status = String(job.status || '').toUpperCase();
                if (button && job.progress_message) {
                    button.textContent =
                        '⏳ ' + job.progress_message;
                }

                if (
                    status === 'SUCCEEDED'
                    || status === 'FAILED'
                    || status === 'CANCELLED'
                ) {
                    if (status !== 'SUCCEEDED') {
                        throw new Error(
                            job.error_text ||
                            (
                                status === 'CANCELLED'
                                    ? 'Sağlık taraması durduruldu.'
                                    : 'Sağlık taraması başarısız.'
                            )
                        );
                    }

                    const savedResponse = await fetch(
                        '/api/template-health/last'
                    );
                    const saved = await savedResponse.json();
                    if (
                        !savedResponse.ok
                        || !saved.success
                    ) {
                        throw new Error(
                            saved.error ||
                            'Kaydedilen sağlık raporu okunamadı.'
                        );
                    }
                    templateHealthSnapshot = saved;
                    if (ayarlar) renderSidebar();
                    if (showReport) {
                        showCopyableReport(
                            'Ham Dosya Sağlık Taraması — Kaydedildi',
                            formatTemplateHealthReport(saved)
                        );
                    }
                    return saved;
                }

                await waitMs(450);
            }
        } finally {
            healthScanJobId = null;
            if (button) {
                button.disabled = false;
                button.textContent =
                    originalText || '🩺 Ham Dosya Sağlık Taraması';
            }
        }
    }

    async function runTemplateHealthScan() {
        if (healthScanJobId) {
            return;
        }
        try {
            const response = await fetch('/api/jobs', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    job_type: 'RAW_HEALTH_SCAN',
                    payload: {}
                })
            });
            const data = await response.json();
            if (!response.ok || !data.success || !data.job) {
                throw new Error(
                    data.error || ('HTTP ' + response.status)
                );
            }
            await monitorHealthScanJob(
                data.job.id,
                true
            );
        } catch (err) {
            showMessage(
                'Ham dosya sağlık taraması başarısız: ' +
                err.message
            );
        }
    }


    async function openLastTemplateHealthReport() {
        const button = document.getElementById(
            'lastTemplateHealthReportButton'
        );
        const originalText = button ? button.textContent : '';
        if (button) {
            button.disabled = true;
            button.textContent = '⏳ Son rapor açılıyor...';
        }

        try {
            const response = await fetch('/api/template-health/last');
            const data = await response.json();
            if (!response.ok || !data.success) {
                if (data.code === 'NO_SAVED_HEALTH_REPORT') {
                    showMessage(
                        'Henüz kaydedilmiş Ham Dosya Sağlık Raporu yok.\n\n' +
                        'Önce “Ham Dosya Sağlık Taraması” butonuna basın. ' +
                        'Tamamlanan rapor bundan sonra burada kalıcı olarak saklanır.'
                    );
                    return;
                }
                throw new Error(
                    data.error || ('HTTP ' + response.status)
                );
            }

            showCopyableReport(
                'Son Ham Dosya Sağlık Raporu' +
                    (data.saved_at ? ' — ' + data.saved_at : ''),
                formatTemplateHealthReport(data)
            );
        } catch (err) {
            showMessage(
                'Son sağlık raporu açılamadı: ' +
                err.message
            );
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent =
                    originalText || '📄 Son Sağlık Raporunu Aç';
            }
        }
    }

    async function loadLastWorkspaceConsistency(render = true) {
        try {
            const response = await fetch('/api/workspace-consistency/last');
            const data = await response.json();
            if (!response.ok || !data.success) {
                if (data.code === 'NO_SAVED_WORKSPACE_REPORT') return null;
                throw new Error(data.error || ('HTTP ' + response.status));
            }
            workspaceConsistencySnapshot = data;
            if (render && ayarlar) renderSidebar();
            return data;
        } catch (err) {
            console.warn('Son klasör tutarlılık raporu yüklenemedi:', err);
            return null;
        }
    }

    async function monitorWorkspaceAuditJob(jobId, showReport = true) {
        workspaceAuditJobId = jobId;
        const button = document.getElementById(
            'workspaceConsistencyScanButton'
        );
        const originalText = button ? button.textContent : '';
        if (button) {
            button.disabled = true;
            button.textContent = '⏳ Tutarlılık taranıyor...';
        }

        try {
            while (true) {
                const response = await fetch(
                    '/api/jobs/' + encodeURIComponent(jobId)
                );
                const data = await response.json();
                if (!response.ok || !data.success || !data.job) {
                    throw new Error(
                        data.error || ('HTTP ' + response.status)
                    );
                }
                const job = data.job;
                updateWorkspaceAuditProgress(job);
                const status = String(job.status || '').toUpperCase();

                if (
                    status === 'SUCCEEDED'
                    || status === 'FAILED'
                    || status === 'CANCELLED'
                ) {
                    const card = ensureWorkspaceAuditProgress();
                    const stop = card.querySelector('#workspace-audit-stop');
                    if (stop) {
                        stop.disabled = true;
                        stop.textContent =
                            status === 'SUCCEEDED'
                                ? '✅ Tamamlandı'
                                : (
                                    status === 'CANCELLED'
                                        ? '⏹ Durduruldu'
                                        : '⛔ Hata'
                                );
                    }

                    if (status !== 'SUCCEEDED') {
                        throw new Error(
                            job.error_text ||
                            (
                                status === 'CANCELLED'
                                    ? 'Tutarlılık taraması durduruldu.'
                                    : 'Tutarlılık taraması başarısız.'
                            )
                        );
                    }

                    const saved = await loadLastWorkspaceConsistency(false);
                    if (!saved) {
                        throw new Error(
                            'Kaydedilmiş tutarlılık raporu okunamadı.'
                        );
                    }
                    workspaceConsistencySnapshot = saved;
                    if (ayarlar) renderSidebar();
                    if (showReport) {
                        showCopyableReport(
                            'Klasör Tutarlılık Raporu — READ ONLY',
                            formatWorkspaceConsistencyReport(saved)
                        );
                    }
                    return saved;
                }
                await waitMs(400);
            }
        } finally {
            workspaceAuditJobId = null;
            if (button) {
                button.disabled = false;
                button.textContent =
                    originalText || '🧭 Klasör Tutarlılık Taraması';
            }
        }
    }

    async function runWorkspaceConsistencyScan() {
        if (workspaceAuditJobId) {
            ensureWorkspaceAuditProgress().style.display = 'block';
            return;
        }

        const ok = confirm(
            'Klasör Tutarlılık Doktoru yalnızca okuyacak.\n\n' +
            'DB, çalışma, ham yedek, staging, çöp, recovery, Kaggle ve Mockup ' +
            'klasörleri denetlenecek.\n\n' +
            'Hiçbir görsel silinmeyecek, taşınmayacak, yeniden adlandırılmayacak ' +
            'veya değiştirilmeyecek. Yalnız rapor kaydı oluşturulacak.\n\n' +
            'Tarama başlatılsın mı?'
        );
        if (!ok) return;

        try {
            const response = await fetch('/api/jobs', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    job_type: 'WORKSPACE_CONSISTENCY_SCAN',
                    payload: {}
                })
            });
            const data = await response.json();
            if (!response.ok || !data.success || !data.job) {
                throw new Error(
                    data.error || ('HTTP ' + response.status)
                );
            }
            await monitorWorkspaceAuditJob(data.job.id, true);
        } catch (err) {
            showMessage(
                'Klasör Tutarlılık Taraması başarısız: ' +
                err.message
            );
        }
    }

    async function openLastWorkspaceConsistencyReport() {
        const data = await loadLastWorkspaceConsistency(false);
        if (!data) {
            showMessage(
                'Henüz kayıtlı Klasör Tutarlılık Raporu yok. ' +
                'Önce “Klasör Tutarlılık Taraması” çalıştırın.'
            );
            return;
        }
        showCopyableReport(
            'Son Klasör Tutarlılık Raporu' +
                (data.saved_at ? ' — ' + data.saved_at : ''),
            formatWorkspaceConsistencyReport(data)
        );
    }

    async function openWorkspaceConsistencyHistory() {
        try {
            const response = await fetch(
                '/api/workspace-consistency/history?limit=30'
            );
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(
                    data.error || ('HTTP ' + response.status)
                );
            }
            showCopyableReport(
                'Klasör Tutarlılık Rapor Geçmişi',
                formatWorkspaceHistory(data)
            );
        } catch (err) {
            showMessage(
                'Tutarlılık rapor geçmişi açılamadı: ' +
                err.message
            );
        }
    }

    async function openTemplateHealthHistory() {
        try {
            const response = await fetch(
                '/api/template-health/history?limit=30'
            );
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(
                    data.error || ('HTTP ' + response.status)
                );
            }
            showCopyableReport(
                'Ham Dosya Sağlık Rapor Geçmişi',
                formatTemplateHealthHistory(data)
            );
        } catch (err) {
            showMessage(
                'Sağlık rapor geçmişi açılamadı: ' +
                err.message
            );
        }
    }

    async function resumePersistentJobs() {
        try {
            const response = await fetch('/api/jobs?active=1&limit=20');
            const data = await response.json();
            if (!response.ok || !data.success) return;

            const jobs = Array.isArray(data.jobs) ? data.jobs : [];
            const batchJob = jobs.find(
                job => String(job.job_type || '').toUpperCase() ===
                    'BATCH_CORNER_SCAN'
            );
            if (batchJob && !batchAnalyzeRunning) {
                const category = String(
                    batchJob.payload?.category || ''
                );
                const total = Number(
                    batchJob.progress_total ||
                    batchJob.payload?.templates?.length ||
                    0
                );
                monitorBatchAnalyzeJob(
                    batchJob.id,
                    category,
                    total,
                    true
                );
            }

            const healthJob = jobs.find(
                job => String(job.job_type || '').toUpperCase() ===
                    'RAW_HEALTH_SCAN'
            );
            if (healthJob && !healthScanJobId) {
                monitorHealthScanJob(
                    healthJob.id,
                    false
                ).catch(err => {
                    console.warn(
                        'Aktif sağlık job takibi başarısız:',
                        err
                    );
                });
            }

            const workspaceJob = jobs.find(
                job => String(job.job_type || '').toUpperCase() ===
                    'WORKSPACE_CONSISTENCY_SCAN'
            );
            if (workspaceJob && !workspaceAuditJobId) {
                monitorWorkspaceAuditJob(
                    workspaceJob.id,
                    false
                ).catch(err => {
                    console.warn(
                        'Aktif klasör audit job takibi başarısız:',
                        err
                    );
                });
            }
        } catch (err) {
            console.warn('Kalıcı işler yeniden bağlanamadı:', err);
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
            refreshTemplateHealth(false, false);
            loadLastWorkspaceConsistency(true);
            resumePersistentJobs();
            startStagingCollisionPolling();
        })
        .catch(err => showMessage("FETCH ERROR: " + err.message));
    
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
            const categoryHealth =
                templateHealthSnapshot?.categories?.[cat] || null;
            const healthIssueCount = Number(
                categoryHealth?.issue_count || 0
            );
            const auditCategory =
                workspaceConsistencySnapshot?.categories?.[cat] || null;
            const auditIssueCount = Number(
                auditCategory?.active_integrity_issue_count || 0
            );
            const auditArchiveCount = Number(
                auditCategory?.archive_inventory_count || 0
            );
            const auditHygieneCount =
                Number(auditCategory?.working_hygiene_count || 0) +
                Number(auditCategory?.duplicate_hygiene_count || 0);
            const matchedCount = Number(
                auditCategory?.fully_matched_active_count || 0
            );
            const stagingCount = Number(
                auditCategory?.staging_identity_count || 0
            );
            const visibleIssueCount = auditCategory
                ? auditIssueCount
                : healthIssueCount;

            title.textContent =
                cat + ' (' + templateCount + ')' +
                (auditCategory
                    ? '  ✅' + matchedCount +
                      (visibleIssueCount > 0
                          ? ' ⚠️' + visibleIssueCount
                          : '') +
                      (stagingCount > 0
                          ? ' 📥' + stagingCount
                          : '')
                    : (
                        visibleIssueCount > 0
                            ? '  ⚠️ ' + visibleIssueCount
                            : ''
                    ));

            const auditTime =
                workspaceConsistencySnapshot?.saved_at || '';
            title.title = auditCategory
                ? (
                    "Son tutarlılık audit'i" +
                    (auditTime ? ' (' + auditTime + ')' : '') +
                    ': DB=' + Number(auditCategory.db_count || 0) +
                    ', Çalışma=' +
                        Number(auditCategory.working_identity_count || 0) +
                    ', Ham=' +
                        Number(auditCategory.backup_identity_count || 0) +
                    ', Tam eşleşen=' + matchedCount +
                    ', Aktif bütünlük sorunu=' + auditIssueCount +
                    ', Arşiv ekstra=' + auditArchiveCount +
                    ', Hijyen=' + auditHygieneCount +
                    ', Staging=' + stagingCount
                )
                : (
                    visibleIssueCount > 0
                        ? visibleIssueCount +
                          ' dosya sağlığı uyarısı var.'
                        : 'Henüz klasör tutarlılık audit sonucu yok.'
                );
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
                if (cat === currentCat && tmpl === currentTmpl) {
                    item.classList.add('active');
                }

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

                const healthInfo = getTemplateHealth(cat, tmpl);
                if (healthInfo && healthInfo.severity !== 'OK') {
                    const healthPrefix = healthInfo.severity === 'CRITICAL'
                        ? '🛑 '
                        : '⚠️ ';
                    label.textContent =
                        healthPrefix +
                        (healthInfo.label || 'Dosya kontrolü') +
                        ' · ' +
                        label.textContent;

                    const previousTitle = item.title
                        ? item.title + '\n'
                        : '';
                    item.title =
                        previousTitle +
                        'Dosya Sağlığı: ' +
                        (healthInfo.label || healthInfo.code || 'Kontrol gerekli');

                    if (healthInfo.severity === 'CRITICAL') {
                        item.style.backgroundColor = 'rgba(220,53,69,0.35)';
                        item.style.color = '#ffb3b3';
                    } else if (!item.style.backgroundColor) {
                        item.style.backgroundColor = 'rgba(255,193,7,0.18)';
                        item.style.color = '#ffe08a';
                    }
                }

                const lifecycle = getWorkspaceTemplateState(
                    cat,
                    tmpl
                );
                if (lifecycle) {
                    const lifecycleBadge = document.createElement('span');
                    lifecycleBadge.style.cssText =
                        'margin-left:6px;font-size:10px;white-space:nowrap;opacity:.92;';
                    lifecycleBadge.textContent =
                        'D' + (lifecycle.db ? '✅' : '❌') +
                        ' H' + (lifecycle.backup ? '✅' : '❌') +
                        ' Ç' + (lifecycle.working ? '✅' : '❌');
                    lifecycleBadge.title =
                        'Dosya yaşam durumu: DB=' +
                        (lifecycle.db ? 'VAR' : 'YOK') +
                        ', Ham=' +
                        (lifecycle.backup ? 'VAR' : 'YOK') +
                        ', Çalışma=' +
                        (lifecycle.working ? 'VAR' : 'YOK') +
                        (
                            lifecycle.staging
                                ? ', Staging=VAR'
                                : ', Staging=YOK'
                        );
                    item.appendChild(checkbox);
                    item.appendChild(label);
                    item.appendChild(lifecycleBadge);
                } else {
                    item.appendChild(checkbox);
                    item.appendChild(label);
                }

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
                showMessage('Mevcut şablon kaydedilemedi. Veri kaybını önlemek için geçiş iptal edildi.');
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
        const loadToken = ++templateLoadToken;
        document.querySelectorAll('.template-item').forEach(el => el.classList.remove('active'));
        if(elem) elem.classList.add('active');
        
        currentCat = cat;
        bulkTargetCategory = cat;
        currentTmpl = tmpl;
        currentImg = null;
        originalImgObj = null;
        pts = [];
        draggingPoint = -1;
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
            if (
                loadToken !== templateLoadToken
                || cat !== currentCat
                || tmpl !== currentTmpl
            ) return;
            currentImg = img;
            originalImgObj = img;
            sourceViewMode = 'working';
            updateSourceViewStatus();
            initPoints(data);
            draw();
        };
        img.onerror = () => {
            if (
                loadToken !== templateLoadToken
                || cat !== currentCat
                || tmpl !== currentTmpl
            ) return;
            currentImg = null;
            originalImgObj = null;
            pts = [];
            sourceViewMode = 'working';
            updateSourceViewStatus();
            showMessage(
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
            showMessage("Lütfen önce bir şablon seçin.");
            return;
        }
        if (!pts || pts.length !== 4) {
            showMessage("AI ön plan analizi için önce 4 baskı köşesini doğrulayın.");
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
                showMessage('Baskının önünde korunması gereken güvenilir bir nesne bulunmadı.');
            } else {
                const confidence = Number(data.confidence || 0);
                showMessage(
                    detectedBoxes.length + ' ön plan nesnesi otomatik bulundu. ' +
                    'Yeşil kutuları gözle kontrol edin. Güven: ' +
                    confidence.toFixed(2)
                );
            }
        } catch (err) {
            showMessage('AI ön plan analizi kullanılamadı: ' + err.message);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        }
    }

    function autoDetectCorners() {
        if (!currentCat || !currentTmpl) {
            showMessage("Önce soldaki listeden bir şablon seçin.");
            return;
        }
        if (blockIfCurrentBatchTemplate(
            currentCat,
            currentTmpl,
            'Köşeleri yeniden algılama'
        )) return;
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

                showMessage(
                    'Yeni köşe önerisi hazır.\n\n' +
                    'Algılanan zemin: ' + modeLabel +
                    (modeConfidence > 0
                        ? ' (güven: %' + Math.round(modeConfidence * 100) + ')'
                        : '') +
                    '\n\nKırmızı noktaları kontrol edin; doğruysa “Bu Şablonu Onayla”ya basın.'
                );
            } else {
                showMessage("Köşeler otomatik bulunamadı: " + (res.error || "Kırmızı noktaları “Köşeleri Elle Ayarla” ile yerleştirin."));
            }
        })
        .catch(err => {
            btn.innerHTML = origText;
            btn.disabled = false;
            showMessage("Sunucu baglanti hatasi: " + err);
        });
    }

    function restoreOriginal() {
        if (!currentCat || !currentTmpl) return;
        if (blockIfCurrentBatchTemplate(
            currentCat,
            currentTmpl,
            'Ham orijinali geri yükleme'
        )) return;
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
                    refreshTemplateHealth(false, false);
                    const sourceInfo =
                        '\n\nKaynak: ' +
                        (res.backup_source_absolute ||
                            (
                                (res.source_root || '2_SABLON_HAVUZU_ORIJINAL_YEDEK') +
                                '/' +
                                (res.backup_source_file || currentTmpl)
                            )) +
                        '\nHedef: ' +
                        (res.destination_absolute ||
                            (
                                (res.destination_root || '2_SABLON_HAVUZU') +
                                '/' +
                                (res.destination_file || currentTmpl)
                            )) +
                        '\nPNG birebir kopya doğrulaması: ' +
                        (res.png_byte_exact_restore ? 'EVET' : 'HAYIR / DÖNÜŞTÜRÜLDÜ');

                    showMessage(
                        'Ham orijinal çalışma kopyasına geri yüklendi.' +
                        sourceInfo +
                        '\n\nDört köşeyi kontrol edin; gerekirse çok küçük bir düzeltme yapın ve ' +
                        '“Bu Şablonu Onayla”ya basın. Sistem onayı yeni görsele bağlayacak.'
                    );
                });
            } else {
                showMessage(
                    "Orijinal yükleme başarısız: " +
                    (res.error || 'Bu görselin korunmuş ham yedeği bulunamadı.')
                );
            }
        }).catch(err => {
            showMessage('Orijinal yükleme bağlantı hatası: ' + err.message);
        });
    }

    function formatLifecycleFileEvidence(item) {
        const dims = (
            item?.width && item?.height
                ? String(item.width) + 'x' + String(item.height)
                : 'boyut-okunamadı'
        );
        const alpha = item?.has_alpha
            ? (
                'alpha=' +
                String(item.alpha_min ?? '?') +
                '..' +
                String(item.alpha_max ?? '?')
            )
            : 'alpha=YOK';
        return [
            String(item?.name || ''),
            'bytes=' + Number(item?.size_bytes || 0),
            'piksel=' + dims,
            'kanal=' + String(item?.channels ?? '?'),
            alpha,
            'SHA256=' + String(item?.sha256 || ''),
            'PIXEL_SHA256=' +
                String(item?.decoded_pixel_sha256 || 'OKUNAMADI'),
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
            'İnsan incelemesi isteyen staging transaction: ' +
                Number(summary.staging_recovery_required_count || 0),
            ''
        ];

        if (focus !== 'recovery') {
            lines.push('DUPLICATE KİMLİKLER:');
            const duplicates = Array.isArray(data?.duplicates)
                ? data.duplicates
                : [];
            if (!duplicates.length) {
                lines.push('Yok.');
            } else {
                duplicates.forEach(row => {
                    lines.push(
                        '• [' + String(row.area || '') + '] ' +
                        String(row.category || '') + ' / ' +
                        String(row.identity || '')
                    );
                    lines.push('  Dosyalar:');
                    (row.files || []).forEach(item => {
                        lines.push(
                            '    - ' + formatLifecycleFileEvidence(item)
                        );
                    });
                    lines.push(
                        '  Byte olarak aynı: ' +
                        (row.byte_equivalent ? 'EVET' : 'HAYIR')
                    );
                    lines.push(
                        '  Decode edilmiş piksel olarak aynı: ' +
                        (row.pixel_equivalent ? 'EVET' : 'HAYIR')
                    );
                    lines.push(
                        '  Aktif DB dosyası: ' +
                        String(row.active_template || 'YOK')
                    );
                    lines.push(
                        '  Güvenli koruma önerisi: ' +
                        String(row.recommended_keep || 'ELLE SEÇİM GEREKİYOR')
                    );
                    if (row.manual_choice_reason) {
                        lines.push(
                            '  İnceleme nedeni: ' +
                            String(row.manual_choice_reason)
                        );
                    }
                });
            }

            lines.push('', 'ÇALIŞMA HAVUZU YETİMLERİ:');
            const workingOrphans = Array.isArray(data?.working_orphans)
                ? data.working_orphans
                : [];
            if (!workingOrphans.length) {
                lines.push('Yok.');
            } else {
                workingOrphans.forEach(row => {
                    lines.push(
                        '• ' + row.category + ' / ' + row.identity
                    );
                    (row.files || []).forEach(item => {
                        lines.push(
                            '    - ' + formatLifecycleFileEvidence(item)
                        );
                    });
                });
            }

            lines.push('', 'AKTİF DB AMA DOSYA EKSİK:');
            const activeMissing = Array.isArray(data?.active_missing)
                ? data.active_missing
                : [];
            if (!activeMissing.length) {
                lines.push('Yok.');
            } else {
                activeMissing.forEach(row => {
                    lines.push(
                        '• ' + row.category + ' / ' + row.template +
                        ' | çalışma=' + (row.working_exists ? 'VAR' : 'YOK') +
                        ' | ham=' + (row.backup_exists ? 'VAR' : 'YOK') +
                        ' | öneri=' + String(row.recommended_action || '')
                    );
                });
            }
        }

        lines.push('', 'SON ÇÖP KAYITLARI:');
        const trash = Array.isArray(data?.trash_records)
            ? data.trash_records
            : [];
        if (!trash.length) {
            lines.push('Yok.');
        } else {
            trash.slice(0, 20).forEach(row => {
                lines.push(
                    '• ' + String(row.created_at || '') + ' — ' +
                    String(row.category || '') + ' / ' +
                    String(row.template || '') +
                    (row.source_was_missing ? ' [DOSYA ZATEN EKSİKTİ]' : '')
                );
            });
        }

        lines.push('', 'SON LIFECYCLE RECOVERY OPERASYONLARI:');
        const recovery = Array.isArray(data?.lifecycle_recovery)
            ? data.lifecycle_recovery
            : [];
        if (!recovery.length) {
            lines.push('Yok.');
        } else {
            recovery.slice(0, 20).forEach(row => {
                lines.push(
                    '• ' + String(row.created_at || '') +
                    ' | ' + String(row.kind || '') +
                    ' | ' + String(row.state || '') +
                    ' | ' + String(row.category || '') +
                    ' / ' + String(row.identity || row.template || '') +
                    ' | geri alınabilir=' +
                    (row.undo_supported ? 'EVET' : 'HAYIR') +
                    ' | taşınan=' + Number(row.moved_count || 0) +
                    ' | id=' + String(row.operation_id || '')
                );
            });
        }

        lines.push('', '.PROCESSING RECOVERY:');
        const processing = Array.isArray(data?.processing_recovery)
            ? data.processing_recovery
            : [];
        if (!processing.length) {
            lines.push('Yok.');
        } else {
            processing.slice(0, 20).forEach(row => {
                lines.push(
                    '• ' + String(row.relative_path || '') +
                    ' | bytes=' + Number(row.size_bytes || 0)
                );
            });
        }

        lines.push('', 'STAGING TRANSACTION JOURNALLARI:');
        const txns = Array.isArray(data?.staging_transactions)
            ? data.staging_transactions
            : [];
        if (!txns.length) {
            lines.push('Yok.');
        } else {
            txns.slice(0, 30).forEach(row => {
                lines.push(
                    '• ' + String(row.updated_at || row.created_at || '') +
                    ' | ' + String(row.state || '') +
                    ' | ' + String(row.category || '') +
                    ' / ' + String(row.canonical_name || '-') +
                    ' | id=' + String(row.transaction_id || '')
                );
                if (row.error) {
                    lines.push('  Hata: ' + String(row.error));
                }
            });
        }

        lines.push(
            '',
            'NOT: Bu merkez kendi kendine toplu düzeltme yapmaz. Riskli aksiyonlar ayrıca kullanıcı onayı ister.'
        );
        return lines.join('\n');
    }

    async function fetchLifecycleCenter() {
        const response = await fetch('/api/lifecycle/center?limit=100');
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(
                data.error || ('HTTP ' + response.status)
            );
        }
        return data;
    }

    async function openLifecycleCenter(focus = 'all') {
        try {
            const data = await fetchLifecycleCenter();
            showCopyableReport(
                focus === 'recovery'
                    ? 'Trash / Recovery Merkezi'
                    : 'Güvenli Eşitleme Merkezi',
                formatLifecycleCenter(data, focus)
            );
        } catch (err) {
            showMessage(
                'Lifecycle merkezi açılamadı: ' + err.message,
                'Lifecycle Merkezi Hatası'
            );
        }
    }

    function closeReconciliationCenter() {
        const overlay = document.getElementById(
            'reconciliation-center-overlay'
        );
        if (overlay) overlay.style.display = 'none';
    }

    function reconciliationButton(label, handler, danger = false) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = label;
        button.style.cssText =
            'padding:8px 10px;border:0;border-radius:5px;cursor:pointer;' +
            'font-weight:bold;margin-left:6px;' +
            'background:' + (danger ? '#b91c1c' : '#2563eb') + ';color:white;';
        button.onclick = handler;
        return button;
    }

    function reconciliationRow(title, details, severity = 'normal') {
        const row = document.createElement('div');
        row.className = 'reconciliation-row';
        const border = severity === 'critical'
            ? '#dc2626'
            : (severity === 'warning' ? '#d97706' : '#475569');
        row.style.cssText =
            'border:1px solid ' + border + ';border-radius:7px;' +
            'padding:10px;margin:8px 0;background:#171717;';

        const head = document.createElement('div');
        head.style.cssText =
            'font-weight:bold;color:#fff;margin-bottom:5px;word-break:break-word;';
        head.textContent = title;
        row.appendChild(head);

        const info = document.createElement('div');
        info.style.cssText =
            'white-space:pre-wrap;color:#d1d5db;font-size:12px;' +
            'line-height:1.45;word-break:break-word;';
        info.textContent = details;
        row.appendChild(info);

        const actions = document.createElement('div');
        actions.className = 'reconciliation-actions';
        actions.style.cssText =
            'display:flex;justify-content:flex-end;gap:4px;' +
            'flex-wrap:wrap;margin-top:8px;';
        row.appendChild(actions);
        return {row, actions};
    }

    async function refreshSettingsAfterReconciliation() {
        const response = await fetch('/api/ayarlar');
        if (!response.ok) {
            throw new Error('Ayarlar yeniden yüklenemedi: HTTP ' + response.status);
        }
        ayarlar = await response.json();
        renderSidebar();
        refreshTemplateHealth(false, false);
        loadLastWorkspaceConsistency(true);
    }

    async function reconciliationPost(url, payload) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload || {})
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(
                data.error || ('HTTP ' + response.status)
            );
        }
        return data;
    }

    async function restoreWorkingFromBackupRow(row) {
        const category = String(row.category || '');
        const template = String(row.template || '');
        if (!confirm(
            'Çalışma kopyası ham/orijinal yedekten geri oluşturulacak.\n\n' +
            category + ' / ' + template + '\n\n' +
            'Bu işlem ham yedeği değiştirmez. Önceki onay yeniden kontrol ' +
            'gerektirebilir. Devam edilsin mi?'
        )) return false;

        const response = await fetch('/api/orijinal_yukle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': category,
                'X-Active-Template': template
            }
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(
                data.error || ('HTTP ' + response.status)
            );
        }
        showCopyableReport(
            'Çalışma Kopyası Geri Yüklendi',
            [
                'Şablon: ' + category + ' / ' + template,
                'Ham kaynak: ' + String(data.backup_source_absolute || ''),
                'Çalışma hedefi: ' + String(data.destination_absolute || ''),
                'SHA256: ' + String(data.destination_after_sha256 || ''),
                'PNG byte-exact: ' +
                    (data.png_byte_exact_restore ? 'EVET' : 'HAYIR'),
                'Onay yeniden kontrol gerekli: EVET'
            ].join('\n')
        );
        return true;
    }

    async function goToReconciliationTemplate(category, template) {
        closeReconciliationCenter();
        await refreshSettingsAfterReconciliation();
        const target = allTemplates.find(
            item => item.cat === category && item.tmpl === template
        );
        if (!target) {
            showMessage(
                'Şablon aktif listede bulunamadı: ' +
                category + ' / ' + template,
                'Şablona Git'
            );
            return;
        }
        if (target.list) target.list.style.display = 'block';
        await navigateToTemplate(
            target.cat,
            target.tmpl,
            target.elem
        );
    }

    async function runReconciliationAction(action, row) {
        try {
            if (action === 'DUPLICATE') {
                const movedNames = (row.files || [])
                    .map(item => item.name)
                    .filter(name => name !== row.recommended_keep);
                if (!confirm(
                    'Duplicate varyant KALICI SİLİNMEYECEK.\n\n' +
                    row.category + ' / ' + row.identity + '\n' +
                    'Alan: ' + row.area + '\n' +
                    'Korunacak: ' + row.recommended_keep + '\n' +
                    'Recovery’ye taşınacak: ' + movedNames.join(', ') +
                    '\n\nDevam edilsin mi?'
                )) return;

                const data = await reconciliationPost(
                    '/api/lifecycle/resolve-duplicate',
                    {
                        area: row.area,
                        category: row.category,
                        identity: row.identity,
                        keep_filename: row.recommended_keep,
                        template: row.active_template || row.recommended_keep
                    }
                );
                showCopyableReport(
                    'Duplicate Güvenle Ayrıldı',
                    [
                        'Operasyon: ' +
                            String(data.operation?.operation_id || ''),
                        'Kategori: ' + row.category,
                        'Kimlik: ' + row.identity,
                        'Korunan: ' + row.recommended_keep,
                        'Recovery’ye taşınan:',
                        ...(data.operation?.moved || []).map(
                            item => '• ' + item.name +
                                ' | SHA256=' + item.sha256
                        )
                    ].join('\n')
                );
            } else if (action === 'WORKING_ORPHAN') {
                if (!confirm(
                    'Bu dosyanın aktif DB kaydı yok.\n\n' +
                    row.category + ' / ' + row.identity + '\n\n' +
                    'Dosya KALICI SİLİNMEYECEK; lifecycle recovery alanına ' +
                    'taşınacak. Devam edilsin mi?'
                )) return;

                const data = await reconciliationPost(
                    '/api/lifecycle/archive-working-orphan',
                    {
                        category: row.category,
                        identity: row.identity
                    }
                );
                showCopyableReport(
                    'Çalışma Yetimi Recovery’ye Alındı',
                    [
                        'Operasyon: ' +
                            String(data.operation?.operation_id || ''),
                        'Kategori: ' + row.category,
                        'Kimlik: ' + row.identity,
                        'Taşınan:',
                        ...(data.operation?.moved || []).map(
                            item => '• ' + item.name +
                                ' | SHA256=' + item.sha256
                        )
                    ].join('\n')
                );
            } else if (action === 'RETIRE_DB_ORPHAN') {
                if (!confirm(
                    'Bu aktif DB kaydının ne çalışma ne de ham dosyası var.\n\n' +
                    row.category + ' / ' + row.template + '\n\n' +
                    'DB kaydı aktif listeden çıkarılıp geri alınabilir çöp ' +
                    'metası oluşturulacak. Kalıcı numara geçmişi korunacak.\n\n' +
                    'Devam edilsin mi?'
                )) return;

                const data = await reconciliationPost(
                    '/api/lifecycle/retire-db-orphan',
                    {
                        category: row.category,
                        template: row.template
                    }
                );
                showCopyableReport(
                    'DB Yetimi Güvenle Retire Edildi',
                    [
                        'Kategori: ' + row.category,
                        'Şablon: ' + row.template,
                        'Çöp kaydı: ' + String(data.trash_record || ''),
                        'Kaynak zaten eksikti: ' +
                            (data.source_was_missing ? 'EVET' : 'HAYIR'),
                        'Numara geçmişi: KORUNDU',
                        'Geri alınabilir: EVET'
                    ].join('\n')
                );
            } else if (action === 'RESTORE_WORKING') {
                await restoreWorkingFromBackupRow(row);
            } else {
                throw new Error('Bilinmeyen reconciliation aksiyonu.');
            }

            await refreshSettingsAfterReconciliation();
            await openActionableReconciliationCenter();
        } catch (err) {
            showMessage(
                'Güvenli eşitleme işlemi başarısız: ' + err.message,
                'Güvenli Eşitleme Hatası'
            );
        }
    }

    async function openActionableReconciliationCenter() {
        try {
            const data = await fetchLifecycleCenter();
            let overlay = document.getElementById(
                'reconciliation-center-overlay'
            );
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.id = 'reconciliation-center-overlay';
                overlay.style.cssText =
                    'position:fixed;inset:0;background:rgba(0,0,0,.78);' +
                    'z-index:100000;display:none;align-items:center;' +
                    'justify-content:center;padding:20px;';
                overlay.innerHTML =
                    '<div id="reconciliation-center-dialog" ' +
                    'style="width:min(1050px,96vw);max-height:90vh;' +
                    'overflow:auto;background:#111827;border:1px solid #475569;' +
                    'border-radius:10px;padding:16px;color:white;">' +
                    '<div style="display:flex;justify-content:space-between;' +
                    'align-items:center;gap:10px;position:sticky;top:0;' +
                    'background:#111827;padding-bottom:10px;z-index:2;">' +
                    '<div><div style="font-size:18px;font-weight:bold;">' +
                    '🧭 Güvenli Eşitleme Merkezi</div>' +
                    '<div id="reconciliation-summary" ' +
                    'style="font-size:12px;color:#cbd5e1;margin-top:3px;"></div>' +
                    '</div>' +
                    '<div style="display:flex;gap:6px;">' +
                    '<button type="button" id="reconciliation-copy-report" ' +
                    'style="padding:8px;">📋 Raporu Aç</button>' +
                    '<button type="button" id="reconciliation-close" ' +
                    'style="padding:8px;">Kapat</button>' +
                    '</div></div>' +
                    '<div id="reconciliation-content"></div>' +
                    '</div>';
                document.body.appendChild(overlay);
                overlay.querySelector(
                    '#reconciliation-close'
                ).onclick = closeReconciliationCenter;
                overlay.addEventListener('click', event => {
                    if (event.target === overlay) {
                        closeReconciliationCenter();
                    }
                });
            }

            const summary = data.summary || {};
            overlay.querySelector(
                '#reconciliation-summary'
            ).textContent =
                'Duplicate=' +
                Number(summary.duplicate_identity_count || 0) +
                ' | Çalışma yetimi=' +
                Number(summary.working_orphan_count || 0) +
                ' | Aktif dosya eksiği=' +
                Number(summary.active_missing_count || 0) +
                ' | Kalıcı otomatik silme=KAPALI';

            overlay.querySelector(
                '#reconciliation-copy-report'
            ).onclick = () => showCopyableReport(
                'Güvenli Eşitleme Merkezi — Tam Rapor',
                formatLifecycleCenter(data, 'all')
            );

            const content = overlay.querySelector(
                '#reconciliation-content'
            );
            content.innerHTML = '';

            const intro = document.createElement('div');
            intro.style.cssText =
                'padding:9px;border-radius:6px;background:#0f172a;' +
                'color:#cbd5e1;font-size:12px;line-height:1.5;margin-bottom:10px;';
            intro.textContent =
                'Her sorun tek tek çözülür. “Hepsini düzelt” yoktur. ' +
                'Dosya taşıyan işlemler kalıcı silme yapmaz; recovery kaydı oluşturur.';
            content.appendChild(intro);

            const addSection = title => {
                const h = document.createElement('h3');
                h.textContent = title;
                h.style.cssText =
                    'margin:15px 0 6px;color:#e2e8f0;font-size:14px;';
                content.appendChild(h);
            };

            addSection('1) Duplicate Kimlikler');
            const duplicates = data.duplicates || [];
            if (!duplicates.length) {
                const empty = document.createElement('div');
                empty.textContent = '✅ Duplicate kimlik yok.';
                empty.style.color = '#86efac';
                content.appendChild(empty);
            }
            duplicates.forEach(row => {
                const files = (row.files || [])
                    .map(item => formatLifecycleFileEvidence(item))
                    .join('\n');
                const item = reconciliationRow(
                    '[' + row.area + '] ' +
                        row.category + ' / ' + row.identity,
                    'Dosyalar:\n' + files +
                    '\nAktif DB dosyası: ' +
                        String(row.active_template || 'YOK') +
                    '\nByte olarak aynı: ' +
                        (row.byte_equivalent ? 'EVET' : 'HAYIR') +
                    '\nPiksel olarak aynı: ' +
                        (row.pixel_equivalent ? 'EVET' : 'HAYIR') +
                    '\nKoruma önerisi: ' +
                        String(
                            row.recommended_keep ||
                            'GÜVENLİ OTOMATİK SEÇİM YOK'
                        ) +
                    (
                        row.manual_choice_reason
                            ? '\nİnceleme nedeni: ' +
                              String(row.manual_choice_reason)
                            : ''
                    ),
                    row.safe_recommendation ? 'warning' : 'critical'
                );
                if (
                    row.safe_recommendation
                    && row.recommended_keep
                ) {
                    item.actions.appendChild(
                        reconciliationButton(
                            'Recovery’ye Ayır',
                            () => runReconciliationAction(
                                'DUPLICATE',
                                row
                            )
                        )
                    );
                } else {
                    const note = document.createElement('span');
                    note.textContent =
                        '⛔ Otomatik seçim yapılmadı; dosyalara dokunulmayacak.';
                    note.style.cssText =
                        'color:#fca5a5;font-size:12px;';
                    item.actions.appendChild(note);
                }
                content.appendChild(item.row);
            });

            addSection('2) DB Dışı Çalışma Dosyaları');
            const orphans = data.working_orphans || [];
            if (!orphans.length) {
                const empty = document.createElement('div');
                empty.textContent = '✅ Çalışma yetimi yok.';
                empty.style.color = '#86efac';
                content.appendChild(empty);
            }
            orphans.forEach(row => {
                const item = reconciliationRow(
                    row.category + ' / ' + row.identity,
                    'Aktif DB kaydı yok.\nDosyalar:\n' +
                        (row.files || []).map(
                            file => formatLifecycleFileEvidence(file)
                        ).join('\n'),
                    'warning'
                );
                item.actions.appendChild(
                    reconciliationButton(
                        'Recovery’ye Al',
                        () => runReconciliationAction(
                            'WORKING_ORPHAN',
                            row
                        )
                    )
                );
                content.appendChild(item.row);
            });

            addSection('3) Aktif DB / Dosya Eksikleri');
            const missing = data.active_missing || [];
            if (!missing.length) {
                const empty = document.createElement('div');
                empty.textContent = '✅ Aktif DB kayıtlarında dosya eksiği yok.';
                empty.style.color = '#86efac';
                content.appendChild(empty);
            }
            missing.forEach(row => {
                const item = reconciliationRow(
                    row.category + ' / ' + row.template,
                    'Çalışma: ' +
                        (row.working_exists ? 'VAR' : 'YOK') +
                    '\nHam: ' +
                        (row.backup_exists ? 'VAR' : 'YOK') +
                    '\nÖneri: ' +
                        String(row.recommended_action || ''),
                    'critical'
                );

                if (row.recommended_action === 'RETIRE_DB_ORPHAN') {
                    item.actions.appendChild(
                        reconciliationButton(
                            'DB Yetimini Retire Et',
                            () => runReconciliationAction(
                                'RETIRE_DB_ORPHAN',
                                row
                            ),
                            true
                        )
                    );
                } else if (
                    row.recommended_action ===
                    'RESTORE_WORKING_FROM_BACKUP'
                ) {
                    item.actions.appendChild(
                        reconciliationButton(
                            'Hamdan Çalışmayı Geri Yükle',
                            () => runReconciliationAction(
                                'RESTORE_WORKING',
                                row
                            )
                        )
                    );
                } else if (
                    row.recommended_action ===
                    'REPLACE_ORIGINAL_REQUIRED'
                ) {
                    item.actions.appendChild(
                        reconciliationButton(
                            'Şablona Git / Yeni Ham Seç',
                            () => goToReconciliationTemplate(
                                row.category,
                                row.template
                            )
                        )
                    );
                }
                content.appendChild(item.row);
            });

            overlay.style.display = 'flex';
        } catch (err) {
            showMessage(
                'Güvenli Eşitleme Merkezi açılamadı: ' +
                    err.message,
                'Güvenli Eşitleme Hatası'
            );
        }
    }

    function chooseReplacementOriginal() {
        if (!currentCat || !currentTmpl) {
            showMessage('Önce soldan bir şablon seçin.');
            return;
        }
        if (blockIfCurrentBatchTemplate(
            currentCat,
            currentTmpl,
            'Ham dosyayı yenisiyle değiştirme'
        )) return;

        const input = document.getElementById(
            'replaceOriginalFileInput'
        );
        if (!input) {
            showMessage('Yeni ham dosya seçici bulunamadı.');
            return;
        }
        input.value = '';
        input.click();
    }

    async function replaceOriginalSelectedFile(input) {
        const file = input?.files?.[0];
        if (!file || !currentCat || !currentTmpl) return;

        const requestCat = currentCat;
        const requestTmpl = currentTmpl;
        const ok = confirm(
            'HAM DOSYA DEĞİŞECEK.\n\n' +
            requestCat + ' / ' + requestTmpl + '\n' +
            'Yeni dosya: ' + file.name + '\n\n' +
            'Eski ham ve eski çalışma kopyaları kalıcı silinmeyecek; ' +
            'Recovery operasyonuna taşınacak. Yeni kaynak sonrası önceki onay ' +
            'STALE_SOURCE_CHANGED olacak ve yeniden kontrol gerekecek.\n\n' +
            'Devam edilsin mi?'
        );
        if (!ok) {
            input.value = '';
            return;
        }

        const formData = new FormData();
        formData.append('file', file, file.name);

        try {
            const response = await fetch(
                '/api/templates/replace-original',
                {
                    method: 'POST',
                    headers: {
                        'X-Active-Category': requestCat,
                        'X-Active-Template': requestTmpl
                    },
                    body: formData
                }
            );
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(
                    data.error || ('HTTP ' + response.status)
                );
            }

            showCopyableReport(
                'Ham Dosya Güvenle Değiştirildi',
                [
                    'Şablon: ' + requestCat + ' / ' + requestTmpl,
                    'Yeni ham: ' + String(data.backup_source_absolute || ''),
                    'Yeni çalışma: ' + String(data.working_absolute || ''),
                    'Ham SHA256: ' + String(data.backup_sha256 || ''),
                    'Çalışma SHA256: ' + String(data.working_sha256 || ''),
                    'Recovery operasyonu: ' + String(data.operation_id || ''),
                    'Recovery’ye alınan eski dosya: ' +
                        Number(data.previous_bytes_archived || 0),
                    'STALE yapılan profil: ' +
                        Number(data.profiles_marked_stale || 0),
                    'Yeni review durumu: ' +
                        String(data.review_status || '')
                ].join('\n')
            );

            const settingsResponse = await fetch('/api/ayarlar');
            ayarlar = await settingsResponse.json();
            renderSidebar();
            refreshTemplateHealth(false, false);
            loadLastWorkspaceConsistency(true);

            if (
                requestCat === currentCat
                && requestTmpl === currentTmpl
            ) {
                const row = allTemplates.find(
                    item => (
                        item.cat === requestCat
                        && item.tmpl === requestTmpl
                    )
                );
                loadTemplate(
                    requestCat,
                    requestTmpl,
                    row?.elem || null
                );
            }
        } catch (err) {
            showMessage(
                'Ham dosya değiştirilemedi: ' + err.message,
                'Ham Dosya Değiştirme Hatası'
            );
        } finally {
            input.value = '';
        }
    }

    async function resolveCurrentTemplateDuplicates() {
        if (!currentCat || !currentTmpl) {
            showMessage('Önce soldan bir şablon seçin.');
            return;
        }
        if (blockIfCurrentBatchTemplate(
            currentCat,
            currentTmpl,
            'Duplicate çözme'
        )) return;

        try {
            const center = await fetchLifecycleCenter();
            const identity = currentTmpl
                .replace(/\.[^.]+$/, '')
                .toLowerCase();

            const rows = (center.duplicates || []).filter(row => (
                row.category === currentCat
                && String(row.identity || '').toLowerCase() === identity
            ));

            if (!rows.length) {
                showMessage(
                    'Bu aktif şablon için duplicate kimlik bulunmadı.',
                    'Duplicate Kontrolü'
                );
                return;
            }

            const safeRows = rows.filter(
                row => row.safe_recommendation && row.recommended_keep
            );
            const manualRows = rows.filter(
                row => !row.safe_recommendation
            );

            if (!safeRows.length) {
                showCopyableReport(
                    'Duplicate — Elle İnceleme Gerekli',
                    formatLifecycleCenter(center, 'all')
                );
                return;
            }

            const planText = safeRows.map(row => (
                '[' + row.area + '] ' +
                row.category + ' / ' + row.identity +
                '\nKorunacak: ' + row.recommended_keep +
                '\nRecovery’ye taşınacak: ' +
                (row.files || [])
                    .map(item => item.name)
                    .filter(name => name !== row.recommended_keep)
                    .join(', ')
            )).join('\n\n');

            if (!confirm(
                'Duplicate dosyalar KALICI SİLİNMEYECEK.\n\n' +
                planText +
                '\n\nDiğer varyantlar recovery alanına taşınsın mı?'
            )) return;

            const results = [];
            for (const row of safeRows) {
                const response = await fetch(
                    '/api/lifecycle/resolve-duplicate',
                    {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            area: row.area,
                            category: row.category,
                            identity: row.identity,
                            keep_filename: row.recommended_keep,
                            template: currentTmpl
                        })
                    }
                );
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(
                        '[' + row.area + '] ' +
                        (data.error || ('HTTP ' + response.status))
                    );
                }
                results.push(data.operation);
            }

            showCopyableReport(
                'Duplicate Çözümü Tamamlandı',
                results.map(op => (
                    'Operasyon: ' + String(op.operation_id || '') +
                    '\nAlan: ' + String(op.area || '') +
                    '\nKorunan: ' + String(op.keep_filename || '') +
                    '\nRecovery’ye taşınan: ' +
                    (op.moved || []).map(item => item.name).join(', ')
                )).join('\n\n') +
                (
                    manualRows.length
                        ? '\n\nNot: ' + manualRows.length +
                          ' duplicate kümesi güvenli otomatik seçim yapılamadığı için dokunulmadan bırakıldı.'
                        : ''
                )
            );

            refreshTemplateHealth(false, false);
            loadLastWorkspaceConsistency(true);
        } catch (err) {
            showMessage(
                'Duplicate çözümü başarısız: ' + err.message,
                'Duplicate Çözüm Hatası'
            );
        }
    }

    async function undoLastLifecycleOperation() {
        if (!confirm(
            'Son geri alınabilir duplicate/yetim arşiv işlemi eski yerine taşınacak.\n\n' +
            'Hedefte aynı isimde dosya varsa sistem geri almayı engelleyecek.\n\n' +
            'Devam edilsin mi?'
        )) return;

        try {
            const response = await fetch('/api/lifecycle/undo', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(
                    data.error || ('HTTP ' + response.status)
                );
            }
            const op = data.operation || {};
            showCopyableReport(
                'Lifecycle İşlemi Geri Alındı',
                [
                    'Operasyon: ' + String(op.operation_id || ''),
                    'Tür: ' + String(op.kind || ''),
                    'Durum: ' + String(op.state || ''),
                    'Geri gelen dosyalar:',
                    ...(op.restored || []).map(
                        item => '• ' + item.absolute_path
                    )
                ].join('\n')
            );
            refreshTemplateHealth(false, false);
            loadLastWorkspaceConsistency(true);
        } catch (err) {
            showMessage(
                'Lifecycle geri alma başarısız: ' + err.message,
                'Recovery Hatası'
            );
        }
    }

    function deleteTemplate() {
        if (!currentCat || !currentTmpl) return;
        if (blockIfCurrentBatchTemplate(
            currentCat,
            currentTmpl,
            'Şablonu silme'
        )) return;
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
                refreshTemplateHealth(false, false);
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
                showMessage("Silme başarısız: " + (res.error || 'Bilinmeyen hata'));
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
                        refreshTemplateHealth(false, false);
                        if (res.restored_as_orphan) {
                            showMessage(
                                'Yetim kayıt geri getirildi: ' +
                                res.restored_tmpl +
                                '\n\nBu kaydın çalışma görseli silinmeden önce de yoktu; ' +
                                'sistem olmayan bir çalışma görseli üretmedi.' +
                                (res.backup_restored
                                    ? '\nHam/orijinal yedek geri getirildi.'
                                    : '\nHam/orijinal yedek de bulunmuyordu.')
                            );
                        } else {
                            showMessage(
                                'Şablon geri getirildi: ' +
                                res.restored_tmpl
                            );
                        }
                    });
            } else {
                showMessage("Geri alma başarısız: " + (res.error || 'Çöpte dosya yok.'));
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
        if (blockIfCurrentBatchTemplate(
            saveCat,
            saveTmpl,
            'Bu şablonu kaydetme'
        )) return false;

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
                    showMessage('Kaydetme hatası: ' + (res.error || 'Bilinmeyen hata'));
                }
                return false;
            }

            // Sadece manuel kaydetmede AKTİF çalışma görselini yenile.
            // Legacy /image rotası ham yedeği öncelediği için burada kullanılmaz.
            if (saveCat && saveTmpl && !silent) {
                const tempImg = new Image();
                tempImg.onload = () => {
                    if (saveCat === currentCat && saveTmpl === currentTmpl) {
                        currentImg = tempImg;
                        originalImgObj = tempImg;
                        sourceViewMode = 'working';
                        updateSourceViewStatus();
                        draw();
                    }
                };
                tempImg.src =
                    '/working-image/' +
                    encodeURIComponent(saveCat) + '/' +
                    encodeURIComponent(saveTmpl) +
                    '?t=' + Date.now();
            }
            if (!silent) {
                showMessage('Değişiklikler aktif şablon veritabanına başarıyla kaydedildi.');
            }
            return true;
        } catch (err) {
            if (!silent) showMessage('Kaydetme hatası: ' + err);
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
let batchAnalyzeStopRequested = false;
let batchAnalyzeCurrentCategory = null;
let batchAnalyzeCurrentTemplate = null;
let batchAnalyzeCompact = false;
let batchAnalyzeExternalPause = false;
let batchAnalyzeInFlightTemplates = new Set();
let batchAnalyzeJobId = null;
let healthScanJobId = null;

function isBatchAnalyzingTemplate(category, template) {
    if (!batchAnalyzeRunning || batchAnalyzeCurrentCategory !== category) {
        return false;
    }
    const key = bulkTemplateKey(category, template);
    return (
        batchAnalyzeInFlightTemplates.has(key)
        || batchAnalyzeCurrentTemplate === template
    );
}

function blockIfCurrentBatchTemplate(category, template, actionLabel) {
    if (!isBatchAnalyzingTemplate(category, template)) return false;
    showMessage(
        (actionLabel || 'Bu işlem') +
        ' şu anda mümkün değil çünkü bu şablon hızlı toplu tarama paketinde işleniyor.\n\n' +
        'Birkaç saniye sonra tekrar deneyin. Diğer şablonlarda çalışmaya devam edebilirsiniz.'
    );
    return true;
}

function setBatchAnalyzeCompact(compact) {
    const overlay = ensureBatchAnalyzeProgressModal();
    const panel = document.getElementById('batchAnalyzePanel');
    const toggle = document.getElementById('batchAnalyzeBackground');

    batchAnalyzeCompact = Boolean(compact);

    if (batchAnalyzeCompact) {
        overlay.style.background = 'transparent';
        overlay.style.pointerEvents = 'none';
        overlay.style.alignItems = 'flex-end';
        overlay.style.justifyContent = 'flex-end';
        overlay.style.padding = '18px';
        if (panel) {
            panel.style.width = 'min(410px, calc(100vw - 36px))';
            panel.style.padding = '14px';
            panel.style.pointerEvents = 'auto';
        }
        if (toggle) toggle.textContent = '↗ Büyüt';
    } else {
        overlay.style.background = 'rgba(0,0,0,.72)';
        overlay.style.pointerEvents = 'auto';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.padding = '0';
        if (panel) {
            panel.style.width = 'min(560px,92vw)';
            panel.style.padding = '22px';
            panel.style.pointerEvents = 'auto';
        }
        if (toggle) toggle.textContent = '↘ Arka Planda Sürdür';
    }
}

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
        <div id="batchAnalyzePanel" style="width:min(560px,92vw);background:#202020;border:1px solid #555;border-radius:12px;padding:22px;box-shadow:0 18px 60px rgba(0,0,0,.45);color:#fff;font-family:Arial,sans-serif;">
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
            <div id="batchAnalyzeRunActions" style="display:flex;gap:8px;margin-top:14px;">
                <button id="batchAnalyzeBackground" type="button" style="flex:1;padding:10px;border:0;border-radius:7px;background:#0d6efd;color:white;font-weight:700;cursor:pointer;">↘ Arka Planda Sürdür</button>
                <button id="batchAnalyzeStop" type="button" style="flex:1;padding:10px;border:0;border-radius:7px;background:#b02a37;color:white;font-weight:700;cursor:pointer;">⏹ Taramayı Durdur</button>
            </div>
            <button id="batchAnalyzeClose" type="button" style="display:none;width:100%;margin-top:14px;padding:11px;border:0;border-radius:7px;background:#28a745;color:white;font-weight:700;cursor:pointer;">Tamam</button>
        </div>
    `;

    document.body.appendChild(overlay);

    document.getElementById('batchAnalyzeBackground').addEventListener('click', () => {
        setBatchAnalyzeCompact(!batchAnalyzeCompact);
    });
    document.getElementById('batchAnalyzeStop').addEventListener('click', async () => {
        if (!batchAnalyzeRunning || batchAnalyzeStopRequested) return;
        batchAnalyzeStopRequested = true;
        const stopButton = document.getElementById('batchAnalyzeStop');
        if (stopButton) {
            stopButton.disabled = true;
            stopButton.textContent = '⏳ Mevcut küçük paket bitsin, sonra duracak';
            stopButton.style.opacity = '0.65';
        }
        document.getElementById('batchAnalyzeSummary').textContent =
            'Durdurma istendi. İşlenen küçük paket tamamlanınca tarama duracak...';

        if (batchAnalyzeJobId) {
            try {
                await fetch(
                    '/api/jobs/' + encodeURIComponent(batchAnalyzeJobId) + '/stop',
                    {method: 'POST'}
                );
            } catch (err) {
                console.warn('Kalıcı job durdurma isteği gönderilemedi:', err);
            }
        }
    });
    document.getElementById('batchAnalyzeClose').addEventListener('click', () => {
        overlay.style.display = 'none';
    });
    return overlay;
}

function updateBatchAnalyzeProgress(done, total, currentText, statusText) {
    const overlay = ensureBatchAnalyzeProgressModal();
    const percent = total > 0 ? Math.round((done / total) * 100) : 0;
    document.getElementById('batchAnalyzeBar').style.width = percent + '%';
    document.getElementById('batchAnalyzeCount').textContent = done + ' / ' + total;
    document.getElementById('batchAnalyzePercent').textContent = '%' + percent;
    document.getElementById('batchAnalyzeSummary').textContent =
        statusText || 'Analiz devam ediyor...';
    document.getElementById('batchAnalyzeCurrent').textContent = currentText
        ? 'İşlenen: ' + currentText
        : 'Hazırlanıyor...';
    overlay.style.display = 'flex';
}

function finishBatchAnalyzeProgress(
    total,
    processedCount,
    successCount,
    approvedProtectedCount,
    failureCount,
    skippedCount,
    failures,
    stopped
) {
    const overlay = ensureBatchAnalyzeProgressModal();
    const percent = total > 0
        ? Math.round((processedCount / total) * 100)
        : 0;

    document.getElementById('batchAnalyzeBar').style.width = percent + '%';
    document.getElementById('batchAnalyzeCount').textContent =
        processedCount + ' / ' + total;
    document.getElementById('batchAnalyzePercent').textContent = '%' + percent;
    document.getElementById('batchAnalyzeTitle').textContent = stopped
        ? '⏹ Tarama durduruldu'
        : (failureCount === 0 ? '✅ Analiz tamamlandı' : '⚠️ Analiz tamamlandı');

    document.getElementById('batchAnalyzeSummary').textContent =
        processedCount + ' dosya işlendi • ' +
        successCount + ' analiz edildi • ' +
        approvedProtectedCount + ' onaylı korundu • ' +
        skippedCount + ' atlandı • ' +
        failureCount + ' hatalı';

    document.getElementById('batchAnalyzeCurrent').textContent = stopped
        ? 'O ana kadar tamamlanan analizler kaydedildi. Kalan şablonlar taranmadı.'
        : (
            failureCount === 0
                ? 'Kategori taraması tamamlandı. 4 köşe kalite algoritması değiştirilmedi.'
                : 'Tarama tamamlandı; bazı dosyalar ayrıca kontrol edilmeli.'
        );

    const errorBox = document.getElementById('batchAnalyzeErrors');
    if (failureCount > 0) {
        errorBox.style.display = 'block';
        errorBox.textContent = failures.slice(0, 8).join('\n');
    } else {
        errorBox.style.display = 'none';
        errorBox.textContent = '';
    }

    const runActions = document.getElementById('batchAnalyzeRunActions');
    if (runActions) runActions.style.display = 'none';
    document.getElementById('batchAnalyzeClose').style.display = 'block';
    overlay.style.display = 'flex';
}

function chooseBatchAnalyzeCategory() {
    const categories = Object.keys(ayarlar?.kategoriler || {});
    if (categories.length === 0) {
        showMessage('Yeniden taranacak kategori bulunamadı.');
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
            '<b>Kalite algoritması değiştirilmez.</b> Kaynağı değişmemiş insan onaylı ' +
            '<b>APPROVED</b> şablonlar ağır analizden atlanır ve aynen korunur. ' +
            'Onaysız şablonlar mevcut motorla analiz edilir. ' +
            '<b>Arka Planda Sürdür</b> ile diğer şablonlarda çalışabilirsiniz.';
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
        confirmButton.textContent = '⚡ Bu Kategoriyi Hızlı Tara';
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

function waitMs(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function refreshReviewSettingsAfterJob() {
    try {
        const response = await fetch('/api/ayarlar');
        if (!response.ok) return;
        ayarlar = await response.json();
        renderSidebar();
    } catch (err) {
        console.warn('Job sonrası şablon listesi yenilenemedi:', err);
    }
}

async function monitorBatchAnalyzeJob(jobId, category, totalHint, resumed = false) {
    batchAnalyzeRunning = true;
    batchAnalyzeJobId = jobId;
    batchAnalyzeCurrentCategory = category;
    batchAnalyzeCurrentTemplate = null;
    batchAnalyzeInFlightTemplates.clear();

    const button = document.getElementById('batchAnalyzeButton');
    if (button) {
        button.disabled = true;
        button.style.opacity = '0.55';
        button.style.cursor = 'wait';
    }

    ensureBatchAnalyzeProgressModal();
    if (resumed) {
        setBatchAnalyzeCompact(true);
    }
    document.getElementById('batchAnalyzeTitle').textContent =
        resumed
            ? '↻ Kalıcı tarama devam ediyor'
            : '⚡ Hızlı kalite-korumalı tarama';
    document.getElementById('batchAnalyzeClose').style.display = 'none';
    const runActions = document.getElementById('batchAnalyzeRunActions');
    if (runActions) runActions.style.display = 'flex';
    const stopButton = document.getElementById('batchAnalyzeStop');
    if (stopButton) {
        stopButton.disabled = false;
        stopButton.textContent = '⏹ Taramayı Durdur';
        stopButton.style.opacity = '1';
    }

    try {
        while (true) {
            const response = await fetch(
                '/api/jobs/' + encodeURIComponent(jobId)
            );
            const data = await response.json();
            if (!response.ok || !data.success || !data.job) {
                throw new Error(
                    data.error || ('HTTP ' + response.status)
                );
            }

            const job = data.job;
            const current = Number(job.progress_current || 0);
            const total = Number(
                job.progress_total || totalHint || 0
            );
            updateBatchAnalyzeProgress(
                current,
                total,
                '',
                job.progress_message ||
                    (
                        job.status === 'PENDING'
                            ? 'Kalıcı iş kuyruğunda bekliyor...'
                            : 'Analiz devam ediyor...'
                    )
            );

            const status = String(job.status || '').toUpperCase();
            if (
                status === 'SUCCEEDED'
                || status === 'FAILED'
                || status === 'CANCELLED'
            ) {
                const result = job.result || {};
                const stopped = status === 'CANCELLED';
                const failureCount =
                    Number(result.failed_count || 0) +
                    Number(result.source_changed_count || 0);
                const skippedCount =
                    Number(result.missing_count || 0) +
                    Number(result.busy_count || 0);

                if (status === 'FAILED') {
                    finishBatchAnalyzeProgress(
                        total,
                        current,
                        Number(result.analyzed_count || 0),
                        Number(result.approved_preserved_count || 0),
                        Math.max(1, failureCount),
                        skippedCount,
                        [job.error_text || 'Kalıcı tarama başarısız.'],
                        false
                    );
                } else {
                    finishBatchAnalyzeProgress(
                        total,
                        current,
                        Number(result.analyzed_count || 0),
                        Number(result.approved_preserved_count || 0),
                        failureCount,
                        skippedCount,
                        [],
                        stopped
                    );
                    const cacheHits = Number(
                        result.cache_hit_count || 0
                    );
                    if (!stopped && cacheHits > 0) {
                        document.getElementById(
                            'batchAnalyzeCurrent'
                        ).textContent +=
                            ' • ' + cacheHits +
                            ' şablon SHA256 + analyzer sürüm cache’inden geldi.';
                    }
                }
                await refreshReviewSettingsAfterJob();
                return job;
            }

            await waitMs(450);
        }
    } catch (err) {
        finishBatchAnalyzeProgress(
            Number(totalHint || 0),
            0,
            0,
            0,
            1,
            0,
            [String(err)],
            false
        );
        return null;
    } finally {
        batchAnalyzeRunning = false;
        batchAnalyzeStopRequested = false;
        batchAnalyzeCurrentCategory = null;
        batchAnalyzeCurrentTemplate = null;
        batchAnalyzeInFlightTemplates.clear();
        batchAnalyzeExternalPause = false;
        batchAnalyzeJobId = null;
        if (button) {
            button.disabled = false;
            button.style.opacity = '1';
            button.style.cursor = 'pointer';
        }
    }
}

async function batchAnalyze() {
    if(batchAnalyzeRunning) return;

    const category = await chooseBatchAnalyzeCategory();
    if(!category) return;

    const templates = Object.keys(
        ayarlar?.kategoriler?.[category]?.sablonlar || {}
    );
    if(templates.length === 0) {
        return showMessage("Seçtiğiniz kategoride analiz edilecek şablon bulunamadı.");
    }

    if(!confirm(
        category + " kategorisindeki " + templates.length +
        " şablon kalıcı iş kuyruğuna alınacak.\n\n" +
        "4 köşe kalite algoritması DEĞİŞMEDİ. Kaynağı değişmemiş insan onaylı " +
        "APPROVED şablonlar korunur; aynı SHA256 + analyzer sürümü daha önce " +
        "hesaplandıysa sonuç cache’den kullanılır.\n\n" +
        "Sayfayı yenileseniz bile iş kaybolmaz; uygulama yeniden açılırsa " +
        "kaldığı ilerleme noktasından devam eder.\n\nDevam edilsin mi?"
    )) return;

    batchAnalyzeStopRequested = false;
    try {
        const response = await fetch('/api/jobs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                job_type: 'BATCH_CORNER_SCAN',
                payload: {
                    category,
                    templates
                }
            })
        });
        const data = await response.json();
        if (!response.ok || !data.success || !data.job) {
            throw new Error(data.error || ('HTTP ' + response.status));
        }

        await monitorBatchAnalyzeJob(
            data.job.id,
            category,
            templates.length,
            Boolean(data.reused_active_job)
        );
    } catch (err) {
        showMessage('Kalıcı kategori taraması başlatılamadı: ' + err.message);
    }
}


async function approveTemplate() {
    if(!currentCat || !currentTmpl) return;
    if (blockIfCurrentBatchTemplate(
        currentCat,
        currentTmpl,
        'Şablonu onaylama'
    )) return;
    let uid = currentCat + "_" + currentTmpl;
    // Use the global pts array from the canvas editor
    if (!pts || pts.length !== 4) return showMessage("Geçerli 4 köşe yok!");
    // Convert {x,y} objects to [[x,y],...] canonical format for DB/profile
    let canonicalCorners = pts.map(p => [p.x, p.y]);
    let physicalOrientation = '';
    if (currentCat === '04_Cam_Dograma') {
        const orientationSelect = document.getElementById('physicalOrientationSelect');
        physicalOrientation = String(
            orientationSelect ? orientationSelect.value : ''
        ).toUpperCase();
        if (physicalOrientation !== 'H' && physicalOrientation !== 'V') {
            return showMessage("Cam Doğrama için onaydan önce fiziksel yönü Yatay (H) veya Dikey (V) seçin.");
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
            showMessage("Şablon onaylandı. Artık üretimde kullanılabilir.");
        } else {
            showMessage("Hata: " + data.error);
        }
    } catch(e) {
        showMessage("Bağlantı hatası: " + e);
    }
}

let showReviewOverlay = false;
function toggleReviewOverlay() {
    showReviewOverlay = !showReviewOverlay;
    draw(); // Redraw canvas with or without overlay
}


