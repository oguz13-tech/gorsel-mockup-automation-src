# VNext MOR — V4.10.2 Kaynak ve Güvenli Eylem Envanteri

**Başlangıç:** `GORSEL_V4102_WINDOWS.zip` SHA256 `eac3eb95f1735541a4bb5b05b556f66de31a8ac1bf2eef02a50e852e6961db88`, GitHub release dalı; F07 kodu korunarak ayrı aday.

## UI modül haritası

| Katman | Gerçek yol | Görev |
|---|---|---|
| Tk ana merkez | `MERKEZ/merkez.py, MERKEZ/premium_dashboard_v489.py` | Ana merkez, kısayollar, sekmeler |
| Tk Seri Üretim | `MERKEZ/URETIM_V4/gui_v4.py` | Mağaza, şablon, 4K, Excel, kuyruk |
| Tk mağaza ataması | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | Mevcut atamalar, F07 toplu kaldırma |
| Tk düzen görünümü | `MERKEZ/ui_layout_v498.py` | Ana ve üretim UI-only ayarlar |
| Web Şablon İnceleme | `SABLON_V2_MIMARI/templates/index.html` | 6 kategori, 4 köşe, yan panel |
| Web PETEK | `SABLON_V2_MIMARI/static/js/petek_editor_v477.js` | 7. kategori; maske ve SHA koruması |
| Web MOR düzenleyici | `SABLON_V2_MIMARI/static/js/review_layout_vnext.js` | UI-only kart/sekmeler, kapatma, renkler |
| Web UI-only backend | `SABLON_V2_MIMARI/core/review_layout_vnext.py` | LOCALAPPDATA/ GorselMockup/UI_VNEXT JSON |
| Mask/SHA backend — değiştirilmedi | `SABLON_V2_MIMARI/core/petek_web_v477.py` | Onay ve revizyon iş mantığı |

## Web mevcut `onclick` callback adları — statik tarama
**35 çağrı adı** (varlığı işlevini tek başına kanıtlamaz):

`approveTemplate`, `autoDetectCorners`, `batchAnalyze`, `bulkApproveSelected`, `bulkDeleteSelected`, `bulkDetectSelectedCorners`, `chooseReplacementOriginal`, `clearBulkSelection`, `deleteTemplate`, `focusCornerEditing`, `nextTemplate`, `openActionableReconciliationCenter`, `openLastTemplateHealthReport`, `openLastWorkspaceConsistencyReport`, `openLifecycleCenter`, `openTemplateHealthHistory`, `openWorkspaceConsistencyHistory`, `prevTemplate`, `resolveCurrentTemplateDuplicates`, `restoreOriginal`, `runTemplateHealthScan`, `runWorkspaceConsistencyScan`, `saveAll`, `selectAllInCurrentCategory`, `showIsolatedWhitePreview`, `showOriginalPreview`, `showWorkingPreview`, `stopBulkCornerDetect`, `toggleBulkSelectionMode`, `toggleCanvasBg`, `toggleReviewOverlay`, `undoDelete`, `undoLastLifecycleOperation`, `v46BulkAlignmentReport`, `v46SelectByReviewStatus`

## Flask deklarasyonları — statik tarama
**43 route** tespit edildi. Blueprint `petek_web`, `review_layout_bp` ayrıca kaydolur.

`/api/session/csrf`, `/api/center_identity`, `/`, `/tools`, `/api/tools/status/<launch_id>`, `/api/tools/launch/<tool_name>`, `/api/ayarlar`, `/api/tekil_sablon_kaydet`, `/api/templates/bulk-save-geometry`, `/api/anlik_beyazlat`, `/preview/<category>/<template>`, `/api/orijinal_yukle`, `/api/lifecycle/center`, `/api/staging/latest-collision`, `/api/lifecycle/resolve-duplicate`, `/api/lifecycle/archive-working-orphan`, `/api/lifecycle/retire-db-orphan`, `/api/lifecycle/undo`, `/api/templates/replace-original`, `/api/v46/corner_draft`, `/api/auto_detect_corners`, `/api/sablon_sil`, `/api/sablon_sil_toplu`, `/api/sablon_sil_geri_al`, `/working-image/<cat>/<tmpl>`, `/original-image/<cat>/<tmpl>`, `/image/<cat>/<tmpl>`, `/api/templates/foreground_detect`, `/api/templates/analyze`, `/api/templates/approve`, `/api/templates/batch_analyze`, `/api/templates/update_corners`, `/api/jobs`, `/api/jobs/<job_id>`, `/api/jobs/<job_id>/stop`, `/api/analysis-cache/stats`, `/api/template-health`, `/api/template-health/last`, `/api/template-health/history`, `/api/workspace-consistency/last`, `/api/workspace-consistency/history`, `/api/saglik_durumu`, `/<path:filename>`

## Veri izole etme ve risk sınırı
- Mor UI kodu gerçek çalışma klasörünü değiştirmez, yeni ayarlar `%LOCALAPPDATA%\GorselMockup\UI_VNEXT\review_layout.json` altında tutulur.
- Eski V4.10.2 kaynak ZIP ayrı saklanır; `2_SABLON_HAVUZU_ORIJINAL_YEDEK/`, PETEK registry, DB, görseller ve numara mezarlığı UI motorundan değiştirilmez.
- Flask UI JSON endpoint mevcut V4.7 loopback+CSRF middleware içinden geçer.
- Flask HTTP/port ve gerçek Windows/GPU/Excel/PETEK UAT yapılmadı: WINDOWS_NOT_VERIFIED.
- Önceden atanmış mağaza mockup kaldırma yalnız eşleştirme katmanında; orijinal görsel/maske silme işlemi yok.
