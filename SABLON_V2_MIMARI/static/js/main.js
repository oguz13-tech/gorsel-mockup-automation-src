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
                details.onclick = () => alert(
                    "KRİTİK SORUNLAR:\n" + (data.sorunlar || []).join("\n") +
                    "\n\nUYARILAR:\n" + (data.uyarilar || []).join("\n") +
                    "\n\nÇÖZÜLENLER:\n" + (data.cozulenler || []).join("\n")
                );
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

    // =========================================================
    // FOREGROUND MASK EDITOR (Photoshop Object Selection & Brush)
    // =========================================================
    let editorTool = 'corner';

    let foregroundMask = {
        object_boxes: [],
        add_brush: [],
        subtract_brush: [],
        feather: 1.2,
        grabcut_iterations: 5
    };

    let maskDragStart = null;
    let maskDragCurrent = null;

    let brushRadius = 20;
    let brushDrawing = false;
    let lastBrushPoint = null;
    let hoverBrushPoint = null;

    let maskHistory = [];

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
    let isShowingOriginal = false; // Kullanici butona basili tutuyor mu
    let previewModeActive = false; // Aninda beyazlatma devrede mi
    
    let allTemplates = [];

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
            title.textContent = cat;
            const list = document.createElement('div');
            list.className = 'template-list';
            if (cat === currentCat) {
                list.style.display = 'block';
            }
            title.onclick = () => { list.style.display = list.style.display === 'block' ? 'none' : 'block'; };
            div.appendChild(title);
            for (const tmpl in ayarlar.kategoriler[cat].sablonlar) {
                const itemData = ayarlar.kategoriler[cat].sablonlar[tmpl];
                const item = document.createElement('div');
                item.className = 'template-item';
                
                const hasCorners = itemData.koseler && itemData.koseler.length === 4;
                const reviewStatus = String(
                    itemData._review_status || itemData.review_status || 'UNANALYZED'
                ).toUpperCase();
                if (reviewStatus === 'APPROVED') {
                    item.textContent = '✅ ' + tmpl;
                    item.title = 'İnsan onaylı ve üretime uygun profil.';
                } else if (reviewStatus === 'STALE_SOURCE_CHANGED' || reviewStatus === 'AMBIGUOUS_DUPLICATE') {
                    item.textContent = '⛔ ' + tmpl;
                    item.style.backgroundColor = 'rgba(220, 53, 69, 0.2)';
                    item.style.color = '#ff9999';
                    item.title = 'Onay artık güvenli değil; yeniden analiz/onay gerekli.';
                } else if (reviewStatus === 'REJECTED') {
                    item.textContent = '🚫 ' + tmpl;
                    item.title = 'İnsan incelemesinde reddedildi.';
                } else if (itemData.supheli) {
                    item.textContent = '⚠️ ' + tmpl;
                    item.style.backgroundColor = 'rgba(220, 53, 69, 0.2)';
                    item.style.color = '#ff9999';
                    item.title = 'Otomatik tespit şüpheli. İnsan kontrolü gerekli.';
                } else if (hasCorners) {
                    item.textContent = '📝 ' + tmpl;
                    item.title = '4 köşe var fakat henüz APPROVED değil.';
                } else {
                    item.textContent = '⏳ ' + tmpl;
                    item.title = 'Henüz incelenmedi.';
                }
                
                item.onclick = () => navigateToTemplate(cat, tmpl, item);
                list.appendChild(item);
                allTemplates.push({cat, tmpl, elem: item, list});
            }
            div.appendChild(list);
            catDiv.appendChild(div);
        }
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
        currentTmpl = tmpl;
        const data = ayarlar.kategoriler[cat].sablonlar[tmpl];
        
        // KULLANICI TALEBI: Varsayilan olarak her zaman perspektif ile acilsin
        if (data.tip !== 'perspektif') {
            data.tip = 'perspektif';
            if (!data.koseler && data.w && data.h) {
                data.koseler = [
                    [data.x, data.y],
                    [data.x + data.w, data.y],
                    [data.x + data.w, data.y + data.h],
                    [data.x, data.y + data.h]
                ];
            }
        }
        
        document.getElementById('current-file').textContent = cat + ' / ' + tmpl;
        document.getElementById('template-type').textContent = 'Tip: ' + data.tip;
        updateCounter();
        syncPhysicalOrientationControl(data);
        
        resetView();

        // Ön plan maske verilerini yükle (Object selection & brush formatı)
        if (data.on_plan && typeof data.on_plan === 'object' && !Array.isArray(data.on_plan)) {
            foregroundMask = JSON.parse(JSON.stringify(data.on_plan));
            if (!foregroundMask.object_boxes) foregroundMask.object_boxes = [];
            if (!foregroundMask.add_brush) foregroundMask.add_brush = [];
            if (!foregroundMask.subtract_brush) foregroundMask.subtract_brush = [];
            if (foregroundMask.feather === undefined) foregroundMask.feather = 1.2;
            if (foregroundMask.grabcut_iterations === undefined) foregroundMask.grabcut_iterations = 5;
        } else {
            foregroundMask = {
                object_boxes: [],
                add_brush: [],
                subtract_brush: [],
                feather: 1.2,
                grabcut_iterations: 5
            };
        }
        maskHistory = [];
        setEditorTool('corner');
        
        // RESET PREVIEW STATE
        isShowingOriginal = false;
        tempPreviewImg = null;
        let btnOrig = document.getElementById('btnToggleOriginal');
        if (btnOrig) {
            btnOrig.innerHTML = "👁️ Orijinal / Önizleme";
            btnOrig.style.background = "#9c27b0";
        }
        
        const img = new Image();
        img.onload = () => {
            currentImg = img;
            originalImgObj = img;
            previewModeActive = false;
            initPoints(data);
            draw();
        };
        img.onerror = () => {
            alert('HATA: "' + tmpl + '" görseli diskinizde (2_SABLON_HAVUZU veya YEDEK klasöründe) bulunamadı! Lütfen dosyanın klasörde gerçekten var olduğundan emin olun.');
            currentImg = null;
            draw();
        };
        img.src = '/image/' + encodeURIComponent(cat) + '/' + encodeURIComponent(tmpl);
    }
    
    function resetView() {
        userZoom = 1.65;
        offsetX = 0;
        offsetY = 0;
    }
    
    function initPoints(data) {
        pts = [];
        if (data.tip === 'perspektif' && data.koseler) {
            pts = data.koseler.map(p => ({x: p[0], y: p[1]}));
        } else {
            let x = data.x || 0;
            let y = data.y || 0;
            let w = data.w || 100;
            let h = data.h || 100;
            pts = [
                {x: x, y: y}, {x: x+w, y: y},
                {x: x+w, y: y+h}, {x: x, y: y+h}
            ];
        }
    }
    
    function toggleType() {
        if(!currentCat) return;
        const data = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
        if(data.tip === 'perspektif') {
            data.tip = 'duz';
            let minX = Math.min(...pts.map(p=>p.x)), maxX = Math.max(...pts.map(p=>p.x));
            let minY = Math.min(...pts.map(p=>p.y)), maxY = Math.max(...pts.map(p=>p.y));
            data.x = Math.round(minX); data.y = Math.round(minY);
            data.w = Math.round(maxX - minX); data.h = Math.round(maxY - minY);
            delete data.koseler;
        } else {
            data.tip = 'perspektif';
            data.koseler = pts.map(p => [Math.round(p.x), Math.round(p.y)]);
            delete data.x; delete data.y; delete data.w; delete data.h;
        }
        document.getElementById('template-type').textContent = 'Tip: ' + data.tip;
        initPoints(data);
        draw();
    }
    
    function updateDataFromPoints() {
        if (!currentCat || !currentTmpl) return;
        const data = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
        if (pts.length === 4) {
            data.koseler = pts.map(p => [Math.round(p.x), Math.round(p.y)]);
            
            // Update sidebar icon
            const currentItem = allTemplates.find(t => t.cat === currentCat && t.tmpl === currentTmpl);
            if (currentItem && currentItem.elem) {
                currentItem.elem.textContent = '✅ ' + currentTmpl;
            }
        }
        if (data.supheli) {
            delete data.supheli;
        }
        if (data.tip === 'perspektif') {
            data.koseler = pts.map(p => [Math.round(p.x), Math.round(p.y)]);
        } else {
            let minX = Math.min(...pts.map(p=>p.x)), maxX = Math.max(...pts.map(p=>p.x));
            let minY = Math.min(...pts.map(p=>p.y)), maxY = Math.max(...pts.map(p=>p.y));
            data.x = Math.round(minX); data.y = Math.round(minY);
            data.w = Math.round(maxX - minX); data.h = Math.round(maxY - minY);
            initPoints(data);
        }
    }

    // =========================================================
    // FOREGROUND MASK İŞLEMLERİ
    // =========================================================

    function cloneForegroundMask() {
        return JSON.parse(JSON.stringify(foregroundMask));
    }

    function pushMaskHistory() {
        maskHistory.push(cloneForegroundMask());
        if (maskHistory.length > 50) maskHistory.shift();
    }

    function undoMaskAction() {
        if (maskHistory.length === 0) return;
        foregroundMask = maskHistory.pop();
        saveCurrentTemplateData();
        draw();
    }

    function clearForegroundMask() {
        if (confirm("Bu şablon için tüm nesne seçimlerini ve fırça maskelerini temizlemek istiyor musunuz?")) {
            pushMaskHistory();
            foregroundMask = {
                object_boxes: [],
                add_brush: [],
                subtract_brush: [],
                feather: 1.2,
                grabcut_iterations: 5
            };
            saveCurrentTemplateData();
            draw();
        }
    }

    function setEditorTool(tool) {
        editorTool = tool;
        maskDragStart = null;
        maskDragCurrent = null;
        brushDrawing = false;
        draggingPoint = -1;

        const ids = {
            corner: 'btnCorner',
            object: 'btnObject',
            add: 'btnAdd',
            subtract: 'btnSubtract'
        };

        for (const key in ids) {
            const el = document.getElementById(ids[key]);
            if (!el) continue;
            if (key === tool) {
                el.style.outline = '3px solid #00aaff';
            } else {
                el.style.outline = '';
            }
        }

        updateCursor();
        draw();
    }

    function updateCursor() {
        if (!canvas) return;
        if (isPanning) {
            canvas.style.cursor = 'grabbing';
        } else if (editorTool === 'object') {
            canvas.style.cursor = 'crosshair';
        } else if (editorTool === 'add' || editorTool === 'subtract') {
            canvas.style.cursor = 'none';
        } else {
            canvas.style.cursor = 'default';
        }
    }

    function updateBrushSize(value) {
        brushRadius = parseInt(value);
        const el = document.getElementById('maskBrushValue');
        if (el) el.textContent = brushRadius;
        const slider = document.getElementById('maskBrushSize');
        if (slider) slider.value = brushRadius;
        draw();
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
            tmplObj.on_plan = cloneForegroundMask();
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

    // Standart koordinat - sınır kontrolü VAR (nesne seçme, fırça için)
    function eventToImagePoint(e) {
        if (!currentImg) return null;
        const finalScale = baseScale * userZoom;
        const imgDrawW = currentImg.width * finalScale;
        const imgDrawH = currentImg.height * finalScale;
        const startX = (canvas.width - imgDrawW) / 2 + offsetX;
        const startY = (canvas.height - imgDrawH) / 2 + offsetY;

        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const imgX = (mouseX - startX) / finalScale;
        const imgY = (mouseY - startY) / finalScale;

        if (imgX < 0 || imgY < 0 || imgX >= currentImg.width || imgY >= currentImg.height) {
            return null;
        }

        return {
            x: Math.round(imgX),
            y: Math.round(imgY)
        };
    }

    function addBrushPoint(p) {
        if (!p) return;
        if (lastBrushPoint) {
            const dx = p.x - lastBrushPoint.x;
            const dy = p.y - lastBrushPoint.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < Math.max(2, brushRadius * 0.25)) return;
        }

        const record = [
            Math.round(p.x),
            Math.round(p.y),
            Math.round(brushRadius)
        ];

        if (editorTool === 'add') {
            foregroundMask.add_brush.push(record);
        } else if (editorTool === 'subtract') {
            foregroundMask.subtract_brush.push(record);
        }
        lastBrushPoint = p;
    }

    // =========================================================
    // ÇİZİM MOTORU (CANVAS RENDER)
    // =========================================================

    function draw() {
        if (!currentImg) return;
        
        canvas.width = cont.clientWidth;
        canvas.height = cont.clientHeight;
        
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

        // 2. Foreground Editor Katmanları (Object Boxes & Brushes)
        drawForegroundEditor(startX, startY, finalScale);
        
        const objCount = foregroundMask.object_boxes.length;
        const brushCount = foregroundMask.add_brush.length + foregroundMask.subtract_brush.length;
        const toolNames = { corner: '🔴 4 KÖŞE', object: '✨ NESNE SEÇ', add: '➕ FIRÇAYLA EKLE', subtract: '➖ FIRÇAYLA ÇIKAR' };
        let infoStr = `Görsel: ${currentImg.width}x${currentImg.height} | Zoom: ${Math.round(userZoom*100)}% | Aktif Araç: <b>${toolNames[editorTool] || editorTool}</b>`;
        infoStr += ` | Nesne Kutuları: ${objCount} | Fırça Noktaları: ${brushCount}`;
        document.getElementById('info').innerHTML = infoStr;
    }

    function drawForegroundEditor(startX, startY, finalScale) {
        ctx.save();

        // 1. Kayıtlı Nesne Seçim Kutuları (GrabCut Boxes)
        for (let i = 0; i < foregroundMask.object_boxes.length; i++) {
            const box = foregroundMask.object_boxes[i];
            if (!box || box.length !== 4) continue;
            const [x1, y1, x2, y2] = box;
            const sx = startX + x1 * finalScale;
            const sy = startY + y1 * finalScale;
            const sw = (x2 - x1) * finalScale;
            const sh = (y2 - y1) * finalScale;

            ctx.fillStyle = 'rgba(0, 255, 80, 0.14)';
            ctx.fillRect(sx, sy, sw, sh);

            ctx.strokeStyle = '#00ff66';
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);
            ctx.strokeRect(sx, sy, sw, sh);

            // Badge
            ctx.fillStyle = '#00ff66';
            ctx.font = 'bold 12px sans-serif';
            ctx.fillText(`✨ Nesne #${i + 1}`, sx + 4, sy + 15);
        }
        ctx.setLineDash([]);

        // 2. Şu An Sürüklenen Nesne Kutusu
        if (maskDragStart && maskDragCurrent) {
            const x1 = Math.min(maskDragStart.x, maskDragCurrent.x);
            const y1 = Math.min(maskDragStart.y, maskDragCurrent.y);
            const x2 = Math.max(maskDragStart.x, maskDragCurrent.x);
            const y2 = Math.max(maskDragStart.y, maskDragCurrent.y);

            ctx.fillStyle = 'rgba(0, 255, 255, 0.18)';
            ctx.strokeStyle = '#00ffff';
            ctx.lineWidth = 2;

            const sx = startX + x1 * finalScale;
            const sy = startY + y1 * finalScale;
            const sw = (x2 - x1) * finalScale;
            const sh = (y2 - y1) * finalScale;

            ctx.fillRect(sx, sy, sw, sh);
            ctx.strokeRect(sx, sy, sw, sh);
        }

        // 3. ➕ Ekle Fırça Katmanı
        ctx.fillStyle = 'rgba(0, 255, 80, 0.32)';
        for (const stroke of foregroundMask.add_brush) {
            const [x, y, r] = stroke;
            ctx.beginPath();
            ctx.arc(startX + x * finalScale, startY + y * finalScale, r * finalScale, 0, Math.PI * 2);
            ctx.fill();
        }

        // 4. ➖ Çıkar Fırça Katmanı
        ctx.fillStyle = 'rgba(255, 40, 40, 0.32)';
        for (const stroke of foregroundMask.subtract_brush) {
            const [x, y, r] = stroke;
            ctx.beginPath();
            ctx.arc(startX + x * finalScale, startY + y * finalScale, r * finalScale, 0, Math.PI * 2);
            ctx.fill();
        }

        // 5. Fırça İmleci Önizlemesi (Brush Cursor)
        if ((editorTool === 'add' || editorTool === 'subtract') && hoverBrushPoint) {
            const hx = startX + hoverBrushPoint.x * finalScale;
            const hy = startY + hoverBrushPoint.y * finalScale;
            const hr = brushRadius * finalScale;

            ctx.beginPath();
            ctx.arc(hx, hy, hr, 0, Math.PI * 2);
            ctx.strokeStyle = (editorTool === 'add') ? '#00ff66' : '#ff3333';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Merkez artı işareti
            ctx.beginPath();
            ctx.moveTo(hx - 4, hy); ctx.lineTo(hx + 4, hy);
            ctx.moveTo(hx, hy - 4); ctx.lineTo(hx, hy + 4);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        ctx.restore();
    }

    // =========================================================
    // FARE VE İŞARETÇİ ETKİLEŞİMLERİ (POINTER EVENTS)
    // =========================================================

    canvas.addEventListener('contextmenu', e => e.preventDefault());

    window.addEventListener('keydown', e => {
        if (e.code === 'Space' && !isSpacePressed) {
            isSpacePressed = true;
            updateCursor();
        }
    });
    window.addEventListener('keyup', e => {
        if (e.code === 'Space') {
            isSpacePressed = false;
            updateCursor();
        }
    });

    canvas.addEventListener('pointerdown', function(e) {
        if (!currentImg) return;

        if (e.button === 2) {
            isPanning = true;
            panStartX = e.clientX - offsetX;
            panStartY = e.clientY - offsetY;
            updateCursor();
            return;
        }

        // Sol Tık
        if (e.button === 0) {
            // 1. Köşe Sürükleme Modu
            if (editorTool === 'corner') {
                // Köşe modu: sınır dışına taşan noktalar da yakalanabilsin
                const rawPos = eventToRawImagePoint(e);
                if (!rawPos) return;
                const finalScale = baseScale * userZoom;
                // Ekran piksel cinsinden 22px hit radius (zoom bağımsız)
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
                return;
            }

            // 2. Nesne Seç veya Fırça Modları
            e.preventDefault();
            e.stopImmediatePropagation();
            const p = eventToImagePoint(e);
            if (!p) return;

            try { canvas.setPointerCapture(e.pointerId); } catch (_) {}

            if (editorTool === 'object') {
                if (e.shiftKey) {
                    // Shift+Tık ile tıklanan kutuyu sil
                    for (let i = foregroundMask.object_boxes.length - 1; i >= 0; i--) {
                        const b = foregroundMask.object_boxes[i];
                        if (p.x >= b[0] && p.x <= b[2] && p.y >= b[1] && p.y <= b[3]) {
                            pushMaskHistory();
                            foregroundMask.object_boxes.splice(i, 1);
                            saveCurrentTemplateData();
                            draw();
                            return;
                        }
                    }
                }
                pushMaskHistory();
                maskDragStart = p;
                maskDragCurrent = p;
                draw();
                return;
            }

            if (editorTool === 'add' || editorTool === 'subtract') {
                pushMaskHistory();
                brushDrawing = true;
                lastBrushPoint = null;
                addBrushPoint(p);
                draw();
                return;
            }
        }
    }, true);

    canvas.addEventListener('pointermove', function(e) {
        if (!currentImg) return;

        // Pan devam ediyor mu?
        if (isPanning) {
            offsetX = e.clientX - panStartX;
            offsetY = e.clientY - panStartY;
            draw();
            return;
        }

        // Köşe sürükleniyor mu?
        if (editorTool === 'corner' && draggingPoint !== -1) {
            // Sınır kontrolsuz koordinat kullan - dışarıya taşabilsin
            const rawPos = eventToRawImagePoint(e);
            if (!rawPos) return;
            const data = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];

            if (data.tip === 'duz') {
                const cx = Math.round(Math.max(0, Math.min(rawPos.x, currentImg.width)));
                const cy = Math.round(Math.max(0, Math.min(rawPos.y, currentImg.height)));
                if (draggingPoint === 0) { pts[0].x = cx; pts[0].y = cy; pts[3].x = cx; pts[1].y = cy; }
                if (draggingPoint === 1) { pts[1].x = cx; pts[1].y = cy; pts[2].x = cx; pts[0].y = cy; }
                if (draggingPoint === 2) { pts[2].x = cx; pts[2].y = cy; pts[1].x = cx; pts[3].y = cy; }
                if (draggingPoint === 3) { pts[3].x = cx; pts[3].y = cy; pts[0].x = cx; pts[2].y = cy; }
            } else {
                // Perspektif: sınır yok, serbestce taşabilsin
                pts[draggingPoint].x = Math.round(rawPos.x);
                pts[draggingPoint].y = Math.round(rawPos.y);
            }
            updateDataFromPoints();
            draw();
            return;
        }

        const p = eventToImagePoint(e);
        hoverBrushPoint = p;

        if (editorTool === 'object' && maskDragStart) {
            e.preventDefault();
            e.stopImmediatePropagation();
            maskDragCurrent = p || maskDragCurrent;
            draw();
            return;
        }

        if ((editorTool === 'add' || editorTool === 'subtract') && brushDrawing && p) {
            e.preventDefault();
            e.stopImmediatePropagation();
            addBrushPoint(p);
            draw();
            return;
        }

        // Fırça önizleme imlecini çiz
        if (editorTool === 'add' || editorTool === 'subtract') {
            draw();
        }
    }, true);

    canvas.addEventListener('pointerup', function(e) {
        if (e.button === 2) {
            isPanning = false;
            updateCursor();
            return;
        }

        if (editorTool === 'corner') {
            draggingPoint = -1;
            return;
        }

        e.preventDefault();
        e.stopImmediatePropagation();

        if (editorTool === 'object' && maskDragStart && maskDragCurrent) {
            let x1 = Math.min(maskDragStart.x, maskDragCurrent.x);
            let y1 = Math.min(maskDragStart.y, maskDragCurrent.y);
            let x2 = Math.max(maskDragStart.x, maskDragCurrent.x);
            let y2 = Math.max(maskDragStart.y, maskDragCurrent.y);

            // Sadece tek tık yapılmışsa akıllı otomatik kutu oluştur
            if ((x2 - x1) < 8 && (y2 - y1) < 8) {
                const autoSize = Math.max(60, Math.round(Math.min(currentImg.width, currentImg.height) * 0.08));
                const cx = maskDragStart.x;
                const cy = maskDragStart.y;
                x1 = Math.max(0, cx - autoSize);
                y1 = Math.max(0, cy - autoSize);
                x2 = Math.min(currentImg.width - 1, cx + autoSize);
                y2 = Math.min(currentImg.height - 1, cy + autoSize);
            }

            foregroundMask.object_boxes.push([
                Math.round(x1),
                Math.round(y1),
                Math.round(x2),
                Math.round(y2)
            ]);

            maskDragStart = null;
            maskDragCurrent = null;
            saveCurrentTemplateData();
        }

        if (brushDrawing) {
            brushDrawing = false;
            lastBrushPoint = null;
            saveCurrentTemplateData();
        }

        try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
        draw();
    }, true);

    canvas.addEventListener('pointercancel', function(e) {
        maskDragStart = null;
        maskDragCurrent = null;
        brushDrawing = false;
        lastBrushPoint = null;
        isPanning = false;
        updateCursor();
        draw();
    }, true);

    canvas.addEventListener('pointerleave', function(e) {
        hoverBrushPoint = null;
        draw();
    });

    // Klavye Kısayolları (Ctrl+Z, C, V, Enter, Space, 1, 2, 3, 4, [, ], N, P)
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
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
            e.preventDefault();
            undoMaskAction();
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

            pushMaskHistory();
            const detectedBoxes = Array.isArray(data.boxes) ? data.boxes : [];
            // Preserve manual brush refinements. Replace only AI/object boxes so
            // re-running discovery cannot duplicate stale detections endlessly.
            foregroundMask.object_boxes = detectedBoxes.map(box => box.slice(0, 4));
            saveCurrentTemplateData();
            setEditorTool('object');
            draw();

            if (detectedBoxes.length === 0) {
                alert(
                    'AI baskının önünde güvenilir bir nesne bulmadı. ' +
                    'Gerekirse Nesne Seç / Maske Ekle araçlarıyla elle düzeltin.'
                );
            } else {
                const confidence = Number(data.confidence || 0);
                alert(
                    detectedBoxes.length + ' ön plan nesnesi bulundu. ' +
                    'Kutuları kontrol edin; gerekirse ekle/çıkar fırçasıyla düzeltin. ' +
                    'Güven: ' + confidence.toFixed(2)
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
            alert("Lutfen once listeden bir sablon secin!");
            return;
        }
        const btn = document.getElementById('btnAutoCorner');
        const origText = btn.innerHTML;
        btn.innerHTML = '⏳ Köşeler Algılanıyor...';
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
                alert('4 kose otomatik olarak basariyla tespit edildi! Koseleri kontrol edin, gerekirse ince ayar yapin.');
            } else {
                alert("Otomatik kose tespiti basarisiz: " + (res.error || "4 koselik bir alan bulunamadi. Lutfen elle ayarlayin."));
            }
        })
        .catch(err => {
            btn.innerHTML = origText;
            btn.disabled = false;
            alert("Sunucu baglanti hatasi: " + err);
        });
    }

    function instantWhiten() {
        if (!currentCat || !currentTmpl) return;
        updateDataFromPoints();
        saveCurrentTemplateData();
        fetch('/api/anlik_beyazlat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': currentCat,
                'X-Active-Template': currentTmpl
            },
            body: JSON.stringify(ayarlar)
        }).then(r => r.json()).then(res => {
            if(res.success) {
                const tempImg = new Image();
                tempImg.onload = () => {
                    currentImg = tempImg;
                    previewModeActive = true;
                    draw();
                };
                tempImg.src = '/preview/' + encodeURIComponent(currentCat) + '/' + encodeURIComponent(currentTmpl) + '?t=' + new Date().getTime();
            } else {
                alert("Beyazlatma başarısız: " + (res.error || 'Bilinmeyen hata'));
            }
        });
    }

    let tempPreviewImg = null;
    function toggleOriginalView() {
        if (!originalImgObj) return;
        
        isShowingOriginal = !isShowingOriginal;
        
        if (isShowingOriginal) {
            tempPreviewImg = currentImg; // Onizlemeyi sakla
            currentImg = originalImgObj; // Orijinale gec
            document.getElementById('btnToggleOriginal').innerHTML = "👁️ Önizlemeye Dön";
            document.getElementById('btnToggleOriginal').style.background = "#ff9800";
        } else {
            if (tempPreviewImg) {
                currentImg = tempPreviewImg; // Onizlemeye geri don
            }
            document.getElementById('btnToggleOriginal').innerHTML = "👁️ Orijinal / Önizleme";
            document.getElementById('btnToggleOriginal').style.background = "#9c27b0";
        }
        draw();
    }

    function restoreOriginal() {
        if (!currentCat || !currentTmpl) return;
        fetch('/api/orijinal_yukle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Active-Category': currentCat,
                'X-Active-Template': currentTmpl
            }
        }).then(r => r.json()).then(res => {
            if(res.success) {
                const tempImg = new Image();
                tempImg.onload = () => {
                    currentImg = tempImg;
                    originalImgObj = tempImg;
                    previewModeActive = false;
                    draw();
                };
                tempImg.src = '/image/' + encodeURIComponent(currentCat) + '/' + encodeURIComponent(currentTmpl) + '?t=' + new Date().getTime();
            } else {
                alert("Orijinal yükleme başarısız: " + (res.error || 'Bu görselin eski bir kopyası (orijinal yedek) bulunamadı.'));
            }
        });
    }

    function tumunuBeyazlat() {
        if (!confirm(`Tüm şablonlar (veya sadece bu kategori) arka planda kalıcı olarak beyazlatılacak. Sadece koordinatları belirlenmiş olanlar işlenecektir.\n\nSadece mevcut kategoriyi beyazlatmak istiyorsanız 'Tamam' deyin.\nTüm veritabanındaki şablonları beyazlatmak istiyorsanız 'İptal' diyerek tam beyazlatmayı seçin.`)) {
            if (!confirm("TÜM KATEGORİLERDEKİ ŞABLONLARI BEYAZLATMAK ÜZERESİNİZ. Onaylıyor musunuz?")) return;
            _triggerTumunuBeyazlat(null);
        } else {
            if (!currentCat) {
                alert("Lütfen önce bir kategori seçin!");
                return;
            }
            _triggerTumunuBeyazlat(currentCat);
        }
    }

    function _triggerTumunuBeyazlat(kategori) {
        alert("Beyazlatma işlemi arka planda başlatıldı! Sunucu ekranından (siyah ekran) takip edebilirsiniz.");
        fetch('/api/tumunu_beyazlat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ kategori: kategori })
        }).then(r => r.json()).then(res => {
            if (res.success) {
                alert("İşlem başarıyla tamamlandı! İşlenen dosya sayısı: " + res.islenen);
            } else {
                alert("Hata oluştu: " + res.error);
            }
        }).catch(err => {
            alert("Bağlantı hatası: " + err);
        });
    }

    function deleteTemplate() {
        if (!currentCat || !currentTmpl) return;
        if (!confirm('Bu şablonu çöpe atmak istediğinize emin misiniz? (Geri alabilirsiniz)')) return;
        
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
                    const listItems = document.querySelectorAll('.template-item');
                    let nextElem = null;
                    listItems.forEach(el => {
                        if (el.textContent === nextTmpl || el.textContent === '⚠️ ' + nextTmpl) {
                            nextElem = el;
                        }
                    });
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
                        alert("Şablon başarıyla geri getirildi: " + res.restored_tmpl);
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

    async function batchAutoDetect() {
        if (!currentCat) { alert("Lütfen önce listeden bir kategori seçin!"); return; }
        const templates = allTemplates.filter(t => t.cat === currentCat);
        if (templates.length === 0) return;
        
        // Henüz işlenmemiş olanları say (hızlandırmak için sadece boş olanları da yapabiliriz ama hepsi baştan taranacak)
        if (!confirm(`Bu kategorideki ${templates.length} şablon için otomatik algılama başlatılacak.\n\nİşlem biraz sürebilir, onaylıyor musunuz?`)) return;

        let successCount = 0;
        let failCount = 0;
        
        const btn = document.getElementById('btnBatchDetect');
        const origHtml = btn.innerHTML;
        btn.disabled = true;
        btn.style.background = '#6c757d';

        let bulkUpdates = [];

        for (let i = 0; i < templates.length; i++) {
            const t = templates[i];
            btn.innerHTML = `⏳ ${i+1} / ${templates.length} taranıyor...`;
            
            // Eğer zaten köşeleri varsa atla
            const tmplData = ayarlar.kategoriler[t.cat].sablonlar[t.tmpl];
            if (tmplData.koseler && tmplData.koseler.length === 4) {
                // Atla
                continue;
            }

            try {
                const res = await fetch('/api/auto_detect_corners', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Active-Category': t.cat,
                        'X-Active-Template': t.tmpl
                    },
                    body: JSON.stringify({ kategori: t.cat, sablon: t.tmpl })
                }).then(r => r.json());
                
                if (res.success && res.corners && res.corners.length === 4) {
                    tmplData.koseler = res.corners;
                    tmplData.tip = 'perspektif';
                    t.elem.textContent = '✅ ' + t.tmpl; // Update sidebar
                    successCount++;
                    bulkUpdates.push({ category: t.cat, filename: t.tmpl, data: tmplData });
                } else {
                    failCount++;
                }
            } catch(e) { failCount++; }
        }
        
        if (bulkUpdates.length > 0) {
            try {
                const saveRes = await fetch('/api/templates/bulk-save-geometry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ templates: bulkUpdates })
                }).then(r => r.json());
                if (!saveRes.success) {
                    console.error("Bulk save failed:", saveRes.error);
                    alert("Uyarı: Taranan şablonlar kaydedilirken hata oluştu: " + saveRes.error);
                }
            } catch(e) {
                console.error("Bulk save request failed:", e);
                alert("Uyarı: Toplu kayıt isteği başarısız oldu.");
            }
        }
        btn.disabled = false;
        btn.style.background = '#e83e8c';
        btn.innerHTML = origHtml;
        alert(`Toplu tarama tamamlandı!\n\nYeni algılanan: ${successCount}\nBulunamayan: ${failCount}`);
        
        // Ekrani guncelle
        if (currentCat && currentTmpl) {
            loadTemplate(currentCat, currentTmpl, allTemplates.find(x => x.cat===currentCat && x.tmpl===currentTmpl).elem);
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
        
        // Eger URL'de ?kaggle=1 varsa direkt olarak Kaggle Onay galerisini ac
        if (window.location.search.includes('kaggle=1')) {
            toggleKaggleView();
        }
    }, 500);

    // ==========================================
    // KAGGLE ONAY SISTEMI
    // ==========================================
    function toggleKaggleView() {
        const dashboard = document.getElementById('kaggle-dashboard');
        if (dashboard.style.display === 'none') {
            dashboard.style.display = 'flex';
            loadKaggleImages();
        } else {
            dashboard.style.display = 'none';
        }
    }

    function loadKaggleImages() {
        fetch('/api/kaggle/bekleyenler')
            .then(r => r.json())
            .then(data => {
                const grid = document.getElementById('kaggle-grid');
                grid.innerHTML = '';
                if(data.success && data.files.length > 0) {
                    data.files.forEach(file => {
                        grid.innerHTML += `
                            <div style="background:#2d2d2d; border-radius:8px; padding:10px; width:220px; display:flex; flex-direction:column; align-items:center;">
                                <img src="/image_kaggle/${file}?t=${new Date().getTime()}" style="max-width:100%; max-height:200px; object-fit:contain; border-radius:4px; margin-bottom:10px;">
                                <span style="color:#fff; font-size:12px; margin-bottom:10px; word-break:break-all;">${file}</span>
                                <div style="display:flex; width:100%; gap:5px;">
                                    <button onclick="approveKaggleImage('${file}')" style="flex:1; background:#28a745; padding:8px; font-weight:bold;">✅ Onayla</button>
                                    <button onclick="rejectKaggleImage('${file}')" style="flex:1; background:#dc3545; padding:8px; font-weight:bold;">❌ Reddet</button>
                                </div>
                            </div>
                        `;
                    });
                } else {
                    grid.innerHTML = '<div style="color:#aaa; font-style:italic; padding:20px;">Onay bekleyen Kaggle baskısı bulunmuyor.</div>';
                }
            })
            .catch(err => console.error(err));
    }

    function approveKaggleImage(filename) {
        fetch('/api/kaggle/onayla', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({filename: filename})
        }).then(r=>r.json()).then(data => {
            if(data.success) {
                loadKaggleImages();
            } else {
                alert("Hata: " + data.error);
            }
        });
    }

    function rejectKaggleImage(filename) {
        if(!confirm("Bu görseli tamamen silmek (çöpe atmak) istediğinize emin misiniz?")) return;
        fetch('/api/kaggle/reddet', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({filename: filename})
        }).then(r=>r.json()).then(data => {
            if(data.success) {
                loadKaggleImages();
            } else {
                alert("Hata: " + data.error);
            }
        });
    }

// --- YZ ONAY SISTEMI ---
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

async function batchAnalyze() {
    if(!currentCat) return alert("Kategori seçili değil!");
    if(batchAnalyzeRunning) return;

    const templates = Object.keys(
        ayarlar?.kategoriler?.[currentCat]?.sablonlar || {}
    );
    if(templates.length === 0) return alert("Bu kategoride analiz edilecek şablon bulunamadı.");

    if(!confirm(
        currentCat + " kategorisindeki " + templates.length +
        " şablon analiz edilecek. Onaylıyor musunuz?"
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

    const category = currentCat;
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
                currentItem.elem.textContent = '✅ ' + currentTmpl;
                currentItem.elem.title = 'İnsan onaylı ve üretime uygun profil.';
                currentItem.elem.style.backgroundColor = '';
                currentItem.elem.style.color = '';
            }
            alert("Geometri başarıyla onaylandı (APPROVED).");
        } else {
            alert("Hata: " + data.error);
        }
    } catch(e) {
        alert("Bağlantı hatası: " + e);
    }
}

async function rejectTemplate() {
    if(!currentCat || !currentTmpl) return;
    let uid = currentCat + "_" + currentTmpl;
    try {
        let res = await fetch('/api/templates/reject', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ template_uid: uid })
        });
        let data = await res.json();
        if(data.success) {
            const tmplObj = ayarlar.kategoriler[currentCat].sablonlar[currentTmpl];
            if (tmplObj) tmplObj._review_status = 'REJECTED';
            const currentItem = allTemplates.find(
                t => t.cat === currentCat && t.tmpl === currentTmpl
            );
            if (currentItem && currentItem.elem) {
                currentItem.elem.textContent = '🚫 ' + currentTmpl;
                currentItem.elem.title = 'İnsan incelemesinde reddedildi.';
            }
            alert("Geometri reddedildi (REJECTED).");
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


