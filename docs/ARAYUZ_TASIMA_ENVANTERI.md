# ARAYÜZ TAŞIMA ENVANTERİ — Görsel Üretim Merkezi

**Tarih:** 2026-11-15 · **Dal:** `harness/github-sync-20261114` · **Bağlı görev:** GitHub Issue #82 (12 iş paketi) · **Üst envanter:** bu belge

## Durum tanımları

| Durum | Anlamı |
|---|---|
| **TAM** | Kod taşındı + test geçti + Windows kullanıcı kabulü alındı. |
| **KISMİ** | Hedef V6/Graphite yüzeyinde karşılığı var; tam kabul yok. |
| **EKSİK** | Henüz taşınmadı. |
| **BOZUK** | Bilinen hata/regresyon; ayrı bölümde izlenir. |
| **TEST BEKLİYOR** | Kod/karşılık var; test kanıtı bekliyor. |

> Kural: Windows kullanıcı kabulü (#82/01) kanıtlanmadan hiçbir madde **TAM** işaretlenmez. Bu nedenle TAM sayısı şimdilik 0’dır; maddeler mevcut durumlarına göre sınıflandırıldı.

## 714 referansı hakkında

Talimatta istenen “714 maddelik arayüz taşıma envanteri” diskte hiçbir dosyada bulunamadı (issue #82, `docs/`, tüm metin dosyaları, `%LOCALAPPDATA%\GorselMockup` tarandı; “714” yalnızca ilgisiz sayılarda görüldü). Sayı zorlanmadı; envanter kaynak koddan otomatik üretildi. **Gerçek madde sayısı:** 816

## Özet

| Durum | Adet |
|---|---|
| TAM | 0 |
| KISMİ | 76 |
| EKSİK | 652 |
| BOZUK | 0 |
| TEST BEKLİYOR | 88 |
| **TOPLAM** | **816** |

## Kaynak bazında özet

| Dosya | Madde | KISMİ | EKSİK | TEST BEKLİYOR |
|---|---|---|---|---|
| `MERKEZ/merkez.py` | 29 | 3 | 26 | 0 |
| `MERKEZ/ui_layout_v498.py` | 23 | 2 | 21 | 0 |
| `MERKEZ/help_v42.py` | 10 | 1 | 9 | 0 |
| `MERKEZ/bakim_merkezi_v472.py` | 25 | 0 | 25 | 0 |
| `MERKEZ/premium_dashboard_v489.py` | 11 | 1 | 10 | 0 |
| `MERKEZ/personal_hub_v493.py` | 40 | 5 | 35 | 0 |
| `MERKEZ/upload_center_v500.py` | 18 | 0 | 18 | 0 |
| `MERKEZ/graphite_ui_components.py` | 13 | 0 | 0 | 13 |
| `MERKEZ/PETEK_V3/gui.py` | 95 | 5 | 90 | 0 |
| `MERKEZ/GUNLUK/run.py` | 17 | 0 | 17 | 0 |
| `MERKEZ/URETIM_V4/gui_v4.py` | 188 | 7 | 181 | 0 |
| `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 76 | 8 | 68 | 0 |
| `MERKEZ/URETIM_V4/ui_table_v1.py` | 6 | 0 | 6 | 0 |
| `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 29 | 2 | 27 | 0 |
| `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 28 | 1 | 27 | 0 |
| `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 12 | 1 | 11 | 0 |
| `MERKEZ/magaza_profilleri_v1.py` | 33 | 6 | 27 | 0 |
| `MERKEZ/tasarim_yonetimi_v1.py` | 18 | 3 | 15 | 0 |
| `MERKEZ/dark_theme_v42.py` | 1 | 0 | 1 | 0 |
| `SABLON_V2_MIMARI/app.py` | 52 | 31 | 21 | 0 |
| `SABLON_V2_MIMARI/tools_runner.py` | 17 | 0 | 17 | 0 |
| `SABLON_V2_MIMARI/templates/v6_review.html` | 75 | 0 | 0 | 75 |

## Bilinen BOZUK modüller

| Modül / test | Durum | Not |
|---|---|---|
| `TESTLER/test_v40_unified_seven_category.py` | BOZUK | PETEK render 42 yerine 2 (değişiklik öncesinden beri kırık) |
| 2 arayüz testi (`petek_overlay_enabled` sahte pencere) | BOZUK | Sahte pencerede öznitelik eksik; kod değişikliğinden önce de kırık |
| `tests/test_p0_legacy_full_inventory_guards.py` | EKSİK ALTYAPI | `99_SISTEM_MOTORLARI_VE_KODLAR` yok → dosya okunamıyor |

## Tam envanter (816 madde)

| # | Dosya | Satır | Öğe | Etiket | Durum |
|---|---|---|---|---|---|
| 1 | `MERKEZ/merkez.py` | 135 | Tk widget |  | EKSİK |
| 2 | `MERKEZ/merkez.py` | 136 | Tk widget |  | EKSİK |
| 3 | `MERKEZ/merkez.py` | 137 | Tk widget |  | EKSİK |
| 4 | `MERKEZ/merkez.py` | 140 | Tk widget |  | EKSİK |
| 5 | `MERKEZ/merkez.py` | 150 | Tk widget |  | EKSİK |
| 6 | `MERKEZ/merkez.py` | 154 | Tk widget |  | EKSİK |
| 7 | `MERKEZ/merkez.py` | 155 | Tk widget |  | EKSİK |
| 8 | `MERKEZ/merkez.py` | 158 | Tk widget |  | EKSİK |
| 9 | `MERKEZ/merkez.py` | 161 | Tk widget |  | EKSİK |
| 10 | `MERKEZ/merkez.py` | 167 | Tk widget |  | EKSİK |
| 11 | `MERKEZ/merkez.py` | 169 | Tk widget | GÃ¶rsel Ãœretim Merkezi | KISMİ |
| 12 | `MERKEZ/merkez.py` | 170 | Tk widget |  | EKSİK |
| 13 | `MERKEZ/merkez.py` | 172 | Tk widget |  | EKSİK |
| 14 | `MERKEZ/merkez.py` | 178 | Tk widget |  | EKSİK |
| 15 | `MERKEZ/merkez.py` | 180 | Tk widget |  | EKSİK |
| 16 | `MERKEZ/merkez.py` | 182 | Tk widget | DeÄŸiÅŸtir | KISMİ |
| 17 | `MERKEZ/merkez.py` | 184 | Tk widget | KlasÃ¶rÃ¼ AÃ§ | EKSİK |
| 18 | `MERKEZ/merkez.py` | 193 | Tk widget |  | EKSİK |
| 19 | `MERKEZ/merkez.py` | 204 | Tk widget |  | EKSİK |
| 20 | `MERKEZ/merkez.py` | 208 | Tk widget |  | EKSİK |
| 21 | `MERKEZ/merkez.py` | 211 | Tk widget | â»  PROGRAMI GÃœVENLE KAPAT | EKSİK |
| 22 | `MERKEZ/merkez.py` | 214 | Tk widget | â–¶ DiÄŸer AraÃ§lar ve Kurtarma | KISMİ |
| 23 | `MERKEZ/merkez.py` | 217 | Tk widget |  | EKSİK |
| 24 | `MERKEZ/merkez.py` | 239 | Tk widget |  | EKSİK |
| 25 | `MERKEZ/merkez.py` | 240 | Tk widget |  | EKSİK |
| 26 | `MERKEZ/merkez.py` | 251 | Tk widget |  | EKSİK |
| 27 | `MERKEZ/merkez.py` | 1163 | Tk widget |  | EKSİK |
| 28 | `MERKEZ/merkez.py` | 1168 | Tk widget | Seri Ã¼retim hazÄ±rlanÄ±yorâ€¦ | EKSİK |
| 29 | `MERKEZ/merkez.py` | 1170 | Tk widget |  | EKSİK |
| 30 | `MERKEZ/ui_layout_v498.py` | 133 | Tk widget |  | EKSİK |
| 31 | `MERKEZ/ui_layout_v498.py` | 147 | Tk widget |  | EKSİK |
| 32 | `MERKEZ/ui_layout_v498.py` | 149 | Tk widget |  | EKSİK |
| 33 | `MERKEZ/ui_layout_v498.py` | 151 | Tk widget |  | EKSİK |
| 34 | `MERKEZ/ui_layout_v498.py` | 152 | Tk widget |  | EKSİK |
| 35 | `MERKEZ/ui_layout_v498.py` | 153 | Tk widget | Sekmeler | EKSİK |
| 36 | `MERKEZ/ui_layout_v498.py` | 154 | Tk widget |  | EKSİK |
| 37 | `MERKEZ/ui_layout_v498.py` | 160 | Tk widget |  | EKSİK |
| 38 | `MERKEZ/ui_layout_v498.py` | 161 | Tk widget |  | EKSİK |
| 39 | `MERKEZ/ui_layout_v498.py` | 162 | Tk widget | Kartlar â€” sÃ¼rÃ¼kleyip sÄ±ralayÄ±n | EKSİK |
| 40 | `MERKEZ/ui_layout_v498.py` | 163 | Tk widget |  | EKSİK |
| 41 | `MERKEZ/ui_layout_v498.py` | 169 | Tk widget |  | EKSİK |
| 42 | `MERKEZ/ui_layout_v498.py` | 170 | Tk widget | SeÃ§ili kartÄ± sekmeye taÅŸÄ±: | EKSİK |
| 43 | `MERKEZ/ui_layout_v498.py` | 172 | Tk widget |  | EKSİK |
| 44 | `MERKEZ/ui_layout_v498.py` | 174 | Tk widget | TaÅŸÄ± | KISMİ |
| 45 | `MERKEZ/ui_layout_v498.py` | 175 | Tk widget |  | EKSİK |
| 46 | `MERKEZ/ui_layout_v498.py` | 176 | Tk widget | ğŸ¨ Vurgu Rengi SeÃ§ | EKSİK |
| 47 | `MERKEZ/ui_layout_v498.py` | 178 | Tk widget |  | EKSİK |
| 48 | `MERKEZ/ui_layout_v498.py` | 180 | Tk widget | ğŸ¨ | KISMİ |
| 49 | `MERKEZ/ui_layout_v498.py` | 182 | Tk widget | Efekt: | EKSİK |
| 50 | `MERKEZ/ui_layout_v498.py` | 184 | Tk widget |  | EKSİK |
| 51 | `MERKEZ/ui_layout_v498.py` | 187 | Tk widget |  | EKSİK |
| 52 | `MERKEZ/ui_layout_v498.py` | 189 | Tk widget |  | EKSİK |
| 53 | `MERKEZ/help_v42.py` | 55 | Tk widget |  | EKSİK |
| 54 | `MERKEZ/help_v42.py` | 67 | Tk widget |  | EKSİK |
| 55 | `MERKEZ/help_v42.py` | 72 | Tk widget |  | EKSİK |
| 56 | `MERKEZ/help_v42.py` | 79 | Tk widget |  | EKSİK |
| 57 | `MERKEZ/help_v42.py` | 81 | Tk widget |  | EKSİK |
| 58 | `MERKEZ/help_v42.py` | 84 | Tk widget | Kapat | KISMİ |
| 59 | `MERKEZ/help_v42.py` | 166 | Tk widget |  | EKSİK |
| 60 | `MERKEZ/help_v42.py` | 172 | Tk widget |  | EKSİK |
| 61 | `MERKEZ/help_v42.py` | 99 | HTML kontrol |  | EKSİK |
| 62 | `MERKEZ/help_v42.py` | 119 | HTML kontrol |  | EKSİK |
| 63 | `MERKEZ/bakim_merkezi_v472.py` | 42 | Tk widget |  | EKSİK |
| 64 | `MERKEZ/bakim_merkezi_v472.py` | 43 | Tk widget |  | EKSİK |
| 65 | `MERKEZ/bakim_merkezi_v472.py` | 44 | Tk widget |  | EKSİK |
| 66 | `MERKEZ/bakim_merkezi_v472.py` | 48 | Tk widget |  | EKSİK |
| 67 | `MERKEZ/bakim_merkezi_v472.py` | 54 | Tk widget |  | EKSİK |
| 68 | `MERKEZ/bakim_merkezi_v472.py` | 56 | Tk widget |  | EKSİK |
| 69 | `MERKEZ/bakim_merkezi_v472.py` | 65 | Tk widget |  | EKSİK |
| 70 | `MERKEZ/bakim_merkezi_v472.py` | 66 | Tk widget |  | EKSİK |
| 71 | `MERKEZ/bakim_merkezi_v472.py` | 69 | Tk widget |  | EKSİK |
| 72 | `MERKEZ/bakim_merkezi_v472.py` | 71 | Tk widget |  | EKSİK |
| 73 | `MERKEZ/bakim_merkezi_v472.py` | 74 | Tk widget |  | EKSİK |
| 74 | `MERKEZ/bakim_merkezi_v472.py` | 78 | Tk widget |  | EKSİK |
| 75 | `MERKEZ/bakim_merkezi_v472.py` | 79 | Tk widget |  | EKSİK |
| 76 | `MERKEZ/bakim_merkezi_v472.py` | 81 | Tk widget |  | EKSİK |
| 77 | `MERKEZ/bakim_merkezi_v472.py` | 84 | Tk widget |  | EKSİK |
| 78 | `MERKEZ/bakim_merkezi_v472.py` | 85 | Tk widget |  | EKSİK |
| 79 | `MERKEZ/bakim_merkezi_v472.py` | 87 | Tk widget |  | EKSİK |
| 80 | `MERKEZ/bakim_merkezi_v472.py` | 90 | Tk widget |  | EKSİK |
| 81 | `MERKEZ/bakim_merkezi_v472.py` | 91 | Tk widget |  | EKSİK |
| 82 | `MERKEZ/bakim_merkezi_v472.py` | 93 | Tk widget |  | EKSİK |
| 83 | `MERKEZ/bakim_merkezi_v472.py` | 96 | Tk widget |  | EKSİK |
| 84 | `MERKEZ/bakim_merkezi_v472.py` | 99 | Tk widget |  | EKSİK |
| 85 | `MERKEZ/bakim_merkezi_v472.py` | 102 | Tk widget |  | EKSİK |
| 86 | `MERKEZ/bakim_merkezi_v472.py` | 103 | Tk widget |  | EKSİK |
| 87 | `MERKEZ/bakim_merkezi_v472.py` | 107 | Tk widget |  | EKSİK |
| 88 | `MERKEZ/premium_dashboard_v489.py` | 31 | Tk widget |  | EKSİK |
| 89 | `MERKEZ/premium_dashboard_v489.py` | 35 | Tk widget |  | EKSİK |
| 90 | `MERKEZ/premium_dashboard_v489.py` | 41 | Tk widget |  | EKSİK |
| 91 | `MERKEZ/premium_dashboard_v489.py` | 131 | Tk widget |  | EKSİK |
| 92 | `MERKEZ/premium_dashboard_v489.py` | 190 | Tk widget |  | EKSİK |
| 93 | `MERKEZ/premium_dashboard_v489.py` | 191 | Tk widget |  | EKSİK |
| 94 | `MERKEZ/premium_dashboard_v489.py` | 289 | Tk widget |  | EKSİK |
| 95 | `MERKEZ/premium_dashboard_v489.py` | 319 | Tk widget |  | EKSİK |
| 96 | `MERKEZ/premium_dashboard_v489.py` | 330 | Tk widget | â–¶ DiÄŸer AraÃ§lar ve Kurtarma | KISMİ |
| 97 | `MERKEZ/premium_dashboard_v489.py` | 333 | Tk widget |  | EKSİK |
| 98 | `MERKEZ/premium_dashboard_v489.py` | 350 | Tk widget |  | EKSİK |
| 99 | `MERKEZ/personal_hub_v493.py` | 313 | Tk widget |  | EKSİK |
| 100 | `MERKEZ/personal_hub_v493.py` | 320 | Tk widget |  | EKSİK |
| 101 | `MERKEZ/personal_hub_v493.py` | 321 | Tk widget | Yapmam Gereken Testler | EKSİK |
| 102 | `MERKEZ/personal_hub_v493.py` | 322 | Tk widget |  | EKSİK |
| 103 | `MERKEZ/personal_hub_v493.py` | 324 | Tk widget |  | EKSİK |
| 104 | `MERKEZ/personal_hub_v493.py` | 326 | Tk widget |  | EKSİK |
| 105 | `MERKEZ/personal_hub_v493.py` | 327 | Tk widget |  | EKSİK |
| 106 | `MERKEZ/personal_hub_v493.py` | 328 | Tk widget |  | EKSİK |
| 107 | `MERKEZ/personal_hub_v493.py` | 336 | Tk widget |  | EKSİK |
| 108 | `MERKEZ/personal_hub_v493.py` | 337 | Tk widget |  | EKSİK |
| 109 | `MERKEZ/personal_hub_v493.py` | 342 | Tk widget | SonuÃ§ / notun (kalÄ±cÄ± kaydedilir): | EKSİK |
| 110 | `MERKEZ/personal_hub_v493.py` | 347 | Tk widget |  | EKSİK |
| 111 | `MERKEZ/personal_hub_v493.py` | 383 | Tk widget | Tamamlananlar / ArÅŸiv | EKSİK |
| 112 | `MERKEZ/personal_hub_v493.py` | 384 | Tk widget | Test Raporu OluÅŸtur + Kopyala | EKSİK |
| 113 | `MERKEZ/personal_hub_v493.py` | 385 | Tk widget |  | EKSİK |
| 114 | `MERKEZ/personal_hub_v493.py` | 386 | Tk widget | Notu Kaydet | EKSİK |
| 115 | `MERKEZ/personal_hub_v493.py` | 387 | Tk widget | Beklet | EKSİK |
| 116 | `MERKEZ/personal_hub_v493.py` | 388 | Tk widget | Sorun Var | KISMİ |
| 117 | `MERKEZ/personal_hub_v493.py` | 389 | Tk widget | Bekleyen Yap | EKSİK |
| 118 | `MERKEZ/personal_hub_v493.py` | 390 | Tk widget | Test Ettim, Onayla ve KaldÄ±r | EKSİK |
| 119 | `MERKEZ/personal_hub_v493.py` | 398 | Tk widget |  | EKSİK |
| 120 | `MERKEZ/personal_hub_v493.py` | 400 | Tk widget |  | EKSİK |
| 121 | `MERKEZ/personal_hub_v493.py` | 401 | Tk widget |  | EKSİK |
| 122 | `MERKEZ/personal_hub_v493.py` | 403 | Tk widget |  | EKSİK |
| 123 | `MERKEZ/personal_hub_v493.py` | 404 | Tk widget |  | EKSİK |
| 124 | `MERKEZ/personal_hub_v493.py` | 410 | Tk widget |  | EKSİK |
| 125 | `MERKEZ/personal_hub_v493.py` | 411 | Tk widget | BaÅŸlÄ±k | KISMİ |
| 126 | `MERKEZ/personal_hub_v493.py` | 412 | Tk widget |  | EKSİK |
| 127 | `MERKEZ/personal_hub_v493.py` | 413 | Tk widget | Not / gÃ¶rev detaylarÄ± | EKSİK |
| 128 | `MERKEZ/personal_hub_v493.py` | 417 | Tk widget |  | EKSİK |
| 129 | `MERKEZ/personal_hub_v493.py` | 450 | Tk widget | Yeni | KISMİ |
| 130 | `MERKEZ/personal_hub_v493.py` | 451 | Tk widget | Kaydet | KISMİ |
| 131 | `MERKEZ/personal_hub_v493.py` | 452 | Tk widget | YapÄ±ldÄ± / Geri Al | EKSİK |
| 132 | `MERKEZ/personal_hub_v493.py` | 453 | Tk widget | Sil | KISMİ |
| 133 | `MERKEZ/personal_hub_v493.py` | 494 | Tk widget |  | EKSİK |
| 134 | `MERKEZ/personal_hub_v493.py` | 495 | Tk widget | Ã–zellik / AraÃ§ Ara | EKSİK |
| 135 | `MERKEZ/personal_hub_v493.py` | 496 | Tk widget |  | EKSİK |
| 136 | `MERKEZ/personal_hub_v493.py` | 497 | Tk widget |  | EKSİK |
| 137 | `MERKEZ/personal_hub_v493.py` | 498 | Tk widget |  | EKSİK |
| 138 | `MERKEZ/personal_hub_v493.py` | 519 | Tk widget | SeÃ§ili AracÄ± AÃ§ | EKSİK |
| 139 | `MERKEZ/upload_center_v500.py` | 43 | Tk widget |  | EKSİK |
| 140 | `MERKEZ/upload_center_v500.py` | 49 | Tk widget |  | EKSİK |
| 141 | `MERKEZ/upload_center_v500.py` | 95 | Tk widget |  | EKSİK |
| 142 | `MERKEZ/upload_center_v500.py` | 104 | Tk widget |  | EKSİK |
| 143 | `MERKEZ/upload_center_v500.py` | 107 | Tk widget |  | EKSİK |
| 144 | `MERKEZ/upload_center_v500.py` | 115 | Tk widget |  | EKSİK |
| 145 | `MERKEZ/upload_center_v500.py` | 120 | Tk widget |  | EKSİK |
| 146 | `MERKEZ/upload_center_v500.py` | 126 | Tk widget |  | EKSİK |
| 147 | `MERKEZ/upload_center_v500.py` | 132 | Tk widget |  | EKSİK |
| 148 | `MERKEZ/upload_center_v500.py` | 139 | Tk widget |  | EKSİK |
| 149 | `MERKEZ/upload_center_v500.py` | 144 | Tk widget |  | EKSİK |
| 150 | `MERKEZ/upload_center_v500.py` | 148 | Tk widget |  | EKSİK |
| 151 | `MERKEZ/upload_center_v500.py` | 154 | Tk widget |  | EKSİK |
| 152 | `MERKEZ/upload_center_v500.py` | 165 | Tk widget |  | EKSİK |
| 153 | `MERKEZ/upload_center_v500.py` | 171 | Tk widget |  | EKSİK |
| 154 | `MERKEZ/upload_center_v500.py` | 176 | Tk widget |  | EKSİK |
| 155 | `MERKEZ/upload_center_v500.py` | 178 | Tk widget |  | EKSİK |
| 156 | `MERKEZ/upload_center_v500.py` | 186 | Tk widget |  | EKSİK |
| 157 | `MERKEZ/graphite_ui_components.py` | 30 | Tk widget |  | TEST BEKLİYOR |
| 158 | `MERKEZ/graphite_ui_components.py` | 31 | Tk widget |  | TEST BEKLİYOR |
| 159 | `MERKEZ/graphite_ui_components.py` | 33 | Tk widget |  | TEST BEKLİYOR |
| 160 | `MERKEZ/graphite_ui_components.py` | 35 | Tk widget |  | TEST BEKLİYOR |
| 161 | `MERKEZ/graphite_ui_components.py` | 38 | Tk widget |  | TEST BEKLİYOR |
| 162 | `MERKEZ/graphite_ui_components.py` | 41 | Tk widget |  | TEST BEKLİYOR |
| 163 | `MERKEZ/graphite_ui_components.py` | 43 | Tk widget |  | TEST BEKLİYOR |
| 164 | `MERKEZ/graphite_ui_components.py` | 46 | Tk widget |  | TEST BEKLİYOR |
| 165 | `MERKEZ/graphite_ui_components.py` | 57 | Tk widget |  | TEST BEKLİYOR |
| 166 | `MERKEZ/graphite_ui_components.py` | 71 | Tk widget |  | TEST BEKLİYOR |
| 167 | `MERKEZ/graphite_ui_components.py` | 76 | Tk widget |  | TEST BEKLİYOR |
| 168 | `MERKEZ/graphite_ui_components.py` | 79 | Tk widget |  | TEST BEKLİYOR |
| 169 | `MERKEZ/graphite_ui_components.py` | 82 | Tk widget |  | TEST BEKLİYOR |
| 170 | `MERKEZ/PETEK_V3/gui.py` | 59 | Tk widget |  | EKSİK |
| 171 | `MERKEZ/PETEK_V3/gui.py` | 75 | Tk widget |  | EKSİK |
| 172 | `MERKEZ/PETEK_V3/gui.py` | 80 | Tk widget |  | EKSİK |
| 173 | `MERKEZ/PETEK_V3/gui.py` | 83 | Tk widget |  | EKSİK |
| 174 | `MERKEZ/PETEK_V3/gui.py` | 85 | Tk widget |  | EKSİK |
| 175 | `MERKEZ/PETEK_V3/gui.py` | 90 | Tk widget |  | EKSİK |
| 176 | `MERKEZ/PETEK_V3/gui.py` | 107 | Tk widget |  | EKSİK |
| 177 | `MERKEZ/PETEK_V3/gui.py` | 112 | Tk widget |  | EKSİK |
| 178 | `MERKEZ/PETEK_V3/gui.py` | 114 | Tk widget | PETEK: Mockup HazÄ±rlama | EKSİK |
| 179 | `MERKEZ/PETEK_V3/gui.py` | 115 | Tk widget | 1. PETEK Mockup FotoÄŸrafÄ±nÄ± SeÃ§ | EKSİK |
| 180 | `MERKEZ/PETEK_V3/gui.py` | 118 | Tk widget |  | EKSİK |
| 181 | `MERKEZ/PETEK_V3/gui.py` | 119 | Tk widget | Mockup AdÄ± / NumarasÄ± | EKSİK |
| 182 | `MERKEZ/PETEK_V3/gui.py` | 120 | Tk widget |  | EKSİK |
| 183 | `MERKEZ/PETEK_V3/gui.py` | 122 | Tk widget | PETEK Ã–n YÃ¼zÃ¼ En / Boy OranÄ± | EKSİK |
| 184 | `MERKEZ/PETEK_V3/gui.py` | 123 | Tk widget |  | EKSİK |
| 185 | `MERKEZ/PETEK_V3/gui.py` | 128 | Tk widget |  | EKSİK |
| 186 | `MERKEZ/PETEK_V3/gui.py` | 130 | Tk widget |  | EKSİK |
| 187 | `MERKEZ/PETEK_V3/gui.py` | 132 | Tk widget |  | EKSİK |
| 188 | `MERKEZ/PETEK_V3/gui.py` | 138 | Tk widget |  | EKSİK |
| 189 | `MERKEZ/PETEK_V3/gui.py` | 139 | Tk widget | FÄ±rÃ§a Ã§apÄ± (kaynak piksel) | EKSİK |
| 190 | `MERKEZ/PETEK_V3/gui.py` | 141 | Tk widget |  | EKSİK |
| 191 | `MERKEZ/PETEK_V3/gui.py` | 142 | Tk widget |  | EKSİK |
| 192 | `MERKEZ/PETEK_V3/gui.py` | 143 | Tk widget | 23 px | EKSİK |
| 193 | `MERKEZ/PETEK_V3/gui.py` | 145 | Tk widget |  | EKSİK |
| 194 | `MERKEZ/PETEK_V3/gui.py` | 147 | Tk widget | Ortam IÅŸÄ±ÄŸÄ± (fotoÄŸraftan) | EKSİK |
| 195 | `MERKEZ/PETEK_V3/gui.py` | 149 | Tk widget |  | EKSİK |
| 196 | `MERKEZ/PETEK_V3/gui.py` | 150 | Tk widget |  | EKSİK |
| 197 | `MERKEZ/PETEK_V3/gui.py` | 152 | Tk widget | KÃ¶ÅŸeleri Yeniden SeÃ§ | EKSİK |
| 198 | `MERKEZ/PETEK_V3/gui.py` | 153 | Tk widget | DÃ¶rtgen DÄ±ÅŸÄ±ndaki Turuncuyu Temizle | EKSİK |
| 199 | `MERKEZ/PETEK_V3/gui.py` | 155 | Tk widget |  | EKSİK |
| 200 | `MERKEZ/PETEK_V3/gui.py` | 157 | Tk widget |  | EKSİK |
| 201 | `MERKEZ/PETEK_V3/gui.py` | 159 | Tk widget |  | EKSİK |
| 202 | `MERKEZ/PETEK_V3/gui.py` | 162 | Tk widget |  | EKSİK |
| 203 | `MERKEZ/PETEK_V3/gui.py` | 164 | Tk widget | Geri Al (Ctrl+Z) | KISMİ |
| 204 | `MERKEZ/PETEK_V3/gui.py` | 166 | Tk widget | Test deseniyle kontrol (tanÄ±lama) | EKSİK |
| 205 | `MERKEZ/PETEK_V3/gui.py` | 167 | Tk widget |  | EKSİK |
| 206 | `MERKEZ/PETEK_V3/gui.py` | 169 | Tk widget |  | EKSİK |
| 207 | `MERKEZ/PETEK_V3/gui.py` | 171 | Tk widget | 3. GERÃ‡EK BaskÄ± TasarÄ±mÄ±yla Ã–nizle | EKSİK |
| 208 | `MERKEZ/PETEK_V3/gui.py` | 173 | Tk widget |  | EKSİK |
| 209 | `MERKEZ/PETEK_V3/gui.py` | 174 | Tk widget | 4. DÃ¼zenlediÄŸim Maskeyi TASLAK Kaydet | EKSİK |
| 210 | `MERKEZ/PETEK_V3/gui.py` | 177 | Tk widget | Ä°nceleyen kiÅŸi | KISMİ |
| 211 | `MERKEZ/PETEK_V3/gui.py` | 178 | Tk widget |  | EKSİK |
| 212 | `MERKEZ/PETEK_V3/gui.py` | 180 | Tk widget |  | EKSİK |
| 213 | `MERKEZ/PETEK_V3/gui.py` | 181 | Tk widget |  | EKSİK |
| 214 | `MERKEZ/PETEK_V3/gui.py` | 184 | Tk widget |  | EKSİK |
| 215 | `MERKEZ/PETEK_V3/gui.py` | 185 | Tk widget |  | EKSİK |
| 216 | `MERKEZ/PETEK_V3/gui.py` | 221 | Tk widget |  | EKSİK |
| 217 | `MERKEZ/PETEK_V3/gui.py` | 222 | Tk widget | SÄ±ÄŸdÄ±r | KISMİ |
| 218 | `MERKEZ/PETEK_V3/gui.py` | 223 | Tk widget | 100% | KISMİ |
| 219 | `MERKEZ/PETEK_V3/gui.py` | 224 | Tk widget | âˆ’ | KISMİ |
| 220 | `MERKEZ/PETEK_V3/gui.py` | 225 | Tk widget |  | EKSİK |
| 221 | `MERKEZ/PETEK_V3/gui.py` | 886 | Tk widget |  | EKSİK |
| 222 | `MERKEZ/PETEK_V3/gui.py` | 895 | Tk widget |  | EKSİK |
| 223 | `MERKEZ/PETEK_V3/gui.py` | 902 | Tk widget |  | EKSİK |
| 224 | `MERKEZ/PETEK_V3/gui.py` | 930 | Tk widget |  | EKSİK |
| 225 | `MERKEZ/PETEK_V3/gui.py` | 933 | Tk widget |  | EKSİK |
| 226 | `MERKEZ/PETEK_V3/gui.py` | 935 | Tk widget |  | EKSİK |
| 227 | `MERKEZ/PETEK_V3/gui.py` | 936 | Tk widget |  | EKSİK |
| 228 | `MERKEZ/PETEK_V3/gui.py` | 937 | Tk widget |  | EKSİK |
| 229 | `MERKEZ/PETEK_V3/gui.py` | 938 | Tk widget |  | EKSİK |
| 230 | `MERKEZ/PETEK_V3/gui.py` | 1019 | Tk widget |  | EKSİK |
| 231 | `MERKEZ/PETEK_V3/gui.py` | 1021 | Tk widget |  | EKSİK |
| 232 | `MERKEZ/PETEK_V3/gui.py` | 1022 | Tk widget |  | EKSİK |
| 233 | `MERKEZ/PETEK_V3/gui.py` | 1023 | Tk widget |  | EKSİK |
| 234 | `MERKEZ/PETEK_V3/gui.py` | 1024 | Tk widget |  | EKSİK |
| 235 | `MERKEZ/PETEK_V3/gui.py` | 1025 | Tk widget |  | EKSİK |
| 236 | `MERKEZ/PETEK_V3/gui.py` | 1027 | Tk widget |  | EKSİK |
| 237 | `MERKEZ/PETEK_V3/gui.py` | 1033 | Tk widget |  | EKSİK |
| 238 | `MERKEZ/PETEK_V3/gui.py` | 1034 | Tk widget |  | EKSİK |
| 239 | `MERKEZ/PETEK_V3/gui.py` | 1036 | Tk widget |  | EKSİK |
| 240 | `MERKEZ/PETEK_V3/gui.py` | 1038 | Tk widget |  | EKSİK |
| 241 | `MERKEZ/PETEK_V3/gui.py` | 1039 | Tk widget | 2. DESEN / BASKI TASARIMLARI KLASÃ–RÃœ | EKSİK |
| 242 | `MERKEZ/PETEK_V3/gui.py` | 1040 | Tk widget |  | EKSİK |
| 243 | `MERKEZ/PETEK_V3/gui.py` | 1042 | Tk widget |  | EKSİK |
| 244 | `MERKEZ/PETEK_V3/gui.py` | 1043 | Tk widget | MaÄŸaza grubu: | EKSİK |
| 245 | `MERKEZ/PETEK_V3/gui.py` | 1044 | Tk widget |  | EKSİK |
| 246 | `MERKEZ/PETEK_V3/gui.py` | 1045 | Tk widget | Bu turda en fazla Ã§Ä±ktÄ±: | EKSİK |
| 247 | `MERKEZ/PETEK_V3/gui.py` | 1046 | Tk widget |  | EKSİK |
| 248 | `MERKEZ/PETEK_V3/gui.py` | 1047 | Tk widget |  | EKSİK |
| 249 | `MERKEZ/PETEK_V3/gui.py` | 1048 | Tk widget | TasarÄ±m yerleÅŸimi: | EKSİK |
| 250 | `MERKEZ/PETEK_V3/gui.py` | 1050 | Tk widget |  | EKSİK |
| 251 | `MERKEZ/PETEK_V3/gui.py` | 1054 | Tk widget |  | EKSİK |
| 252 | `MERKEZ/PETEK_V3/gui.py` | 1055 | Tk widget |  | EKSİK |
| 253 | `MERKEZ/PETEK_V3/gui.py` | 1056 | Tk widget |  | EKSİK |
| 254 | `MERKEZ/PETEK_V3/gui.py` | 1057 | Tk widget | â–¶ Seri GÃ¶rsel Ãœretimini BaÅŸlat | EKSİK |
| 255 | `MERKEZ/PETEK_V3/gui.py` | 1059 | Tk widget | â–  GÃ¼venli durdur | EKSİK |
| 256 | `MERKEZ/PETEK_V3/gui.py` | 1060 | Tk widget | Ã‡Ä±ktÄ± klasÃ¶rÃ¼ | EKSİK |
| 257 | `MERKEZ/PETEK_V3/gui.py` | 1061 | Tk widget |  | EKSİK |
| 258 | `MERKEZ/PETEK_V3/gui.py` | 1064 | Tk widget |  | EKSİK |
| 259 | `MERKEZ/PETEK_V3/gui.py` | 1067 | Tk widget |  | EKSİK |
| 260 | `MERKEZ/PETEK_V3/gui.py` | 198 | HTML kontrol |  | EKSİK |
| 261 | `MERKEZ/PETEK_V3/gui.py` | 202 | HTML kontrol |  | EKSİK |
| 262 | `MERKEZ/PETEK_V3/gui.py` | 203 | HTML kontrol |  | EKSİK |
| 263 | `MERKEZ/PETEK_V3/gui.py` | 205 | HTML kontrol |  | EKSİK |
| 264 | `MERKEZ/PETEK_V3/gui.py` | 207 | HTML kontrol |  | EKSİK |
| 265 | `MERKEZ/GUNLUK/run.py` | 27 | Tk widget |  | EKSİK |
| 266 | `MERKEZ/GUNLUK/run.py` | 28 | Tk widget | TasarÄ±m klasÃ¶rÃ¼nden mockup Ã¼ret | EKSİK |
| 267 | `MERKEZ/GUNLUK/run.py` | 29 | Tk widget |  | EKSİK |
| 268 | `MERKEZ/GUNLUK/run.py` | 30 | Tk widget |  | EKSİK |
| 269 | `MERKEZ/GUNLUK/run.py` | 31 | Tk widget |  | EKSİK |
| 270 | `MERKEZ/GUNLUK/run.py` | 32 | Tk widget |  | EKSİK |
| 271 | `MERKEZ/GUNLUK/run.py` | 36 | Tk widget | KlasÃ¶r seÃ§ | EKSİK |
| 272 | `MERKEZ/GUNLUK/run.py` | 37 | Tk widget |  | EKSİK |
| 273 | `MERKEZ/GUNLUK/run.py` | 41 | Tk widget |  | EKSİK |
| 274 | `MERKEZ/GUNLUK/run.py` | 43 | Tk widget |  | EKSİK |
| 275 | `MERKEZ/GUNLUK/run.py` | 44 | Tk widget |  | EKSİK |
| 276 | `MERKEZ/GUNLUK/run.py` | 45 | Tk widget |  | EKSİK |
| 277 | `MERKEZ/GUNLUK/run.py` | 72 | Tk widget | Ãœretimi baÅŸlat | EKSİK |
| 278 | `MERKEZ/GUNLUK/run.py` | 73 | Tk widget | Mevcut iÅŸten sonra durdur | EKSİK |
| 279 | `MERKEZ/GUNLUK/run.py` | 74 | Tk widget | SonuÃ§larÄ± aÃ§ | EKSİK |
| 280 | `MERKEZ/GUNLUK/run.py` | 75 | Tk widget | Rapor klasÃ¶rÃ¼ | EKSİK |
| 281 | `MERKEZ/GUNLUK/run.py` | 76 | Tk widget |  | EKSİK |
| 282 | `MERKEZ/URETIM_V4/gui_v4.py` | 82 | Tk widget |  | EKSİK |
| 283 | `MERKEZ/URETIM_V4/gui_v4.py` | 125 | Tk widget |  | EKSİK |
| 284 | `MERKEZ/URETIM_V4/gui_v4.py` | 128 | Tk widget | â–¶  ÃœRETÄ°ME BAÅLA | EKSİK |
| 285 | `MERKEZ/URETIM_V4/gui_v4.py` | 135 | Tk widget |  | EKSİK |
| 286 | `MERKEZ/URETIM_V4/gui_v4.py` | 137 | Tk widget |  | EKSİK |
| 287 | `MERKEZ/URETIM_V4/gui_v4.py` | 139 | Tk widget |  | EKSİK |
| 288 | `MERKEZ/URETIM_V4/gui_v4.py` | 141 | Tk widget |  | EKSİK |
| 289 | `MERKEZ/URETIM_V4/gui_v4.py` | 152 | Tk widget |  | EKSİK |
| 290 | `MERKEZ/URETIM_V4/gui_v4.py` | 155 | Tk widget |  | EKSİK |
| 291 | `MERKEZ/URETIM_V4/gui_v4.py` | 157 | Tk widget |  | EKSİK |
| 292 | `MERKEZ/URETIM_V4/gui_v4.py` | 159 | Tk widget |  | EKSİK |
| 293 | `MERKEZ/URETIM_V4/gui_v4.py` | 161 | Tk widget |  | EKSİK |
| 294 | `MERKEZ/URETIM_V4/gui_v4.py` | 165 | Tk widget |  | EKSİK |
| 295 | `MERKEZ/URETIM_V4/gui_v4.py` | 167 | Tk widget |  | EKSİK |
| 296 | `MERKEZ/URETIM_V4/gui_v4.py` | 169 | Tk widget |  | EKSİK |
| 297 | `MERKEZ/URETIM_V4/gui_v4.py` | 170 | Tk widget |  | EKSİK |
| 298 | `MERKEZ/URETIM_V4/gui_v4.py` | 171 | Tk widget |  | EKSİK |
| 299 | `MERKEZ/URETIM_V4/gui_v4.py` | 174 | Tk widget |  | EKSİK |
| 300 | `MERKEZ/URETIM_V4/gui_v4.py` | 175 | Tk widget |  | EKSİK |
| 301 | `MERKEZ/URETIM_V4/gui_v4.py` | 176 | Tk widget |  | EKSİK |
| 302 | `MERKEZ/URETIM_V4/gui_v4.py` | 177 | Tk widget |  | EKSİK |
| 303 | `MERKEZ/URETIM_V4/gui_v4.py` | 180 | Tk widget |  | EKSİK |
| 304 | `MERKEZ/URETIM_V4/gui_v4.py` | 181 | Tk widget |  | EKSİK |
| 305 | `MERKEZ/URETIM_V4/gui_v4.py` | 182 | Tk widget |  | EKSİK |
| 306 | `MERKEZ/URETIM_V4/gui_v4.py` | 183 | Tk widget |  | EKSİK |
| 307 | `MERKEZ/URETIM_V4/gui_v4.py` | 184 | Tk widget |  | EKSİK |
| 308 | `MERKEZ/URETIM_V4/gui_v4.py` | 187 | Tk widget |  | EKSİK |
| 309 | `MERKEZ/URETIM_V4/gui_v4.py` | 188 | Tk widget |  | EKSİK |
| 310 | `MERKEZ/URETIM_V4/gui_v4.py` | 189 | Tk widget |  | EKSİK |
| 311 | `MERKEZ/URETIM_V4/gui_v4.py` | 190 | Tk widget |  | EKSİK |
| 312 | `MERKEZ/URETIM_V4/gui_v4.py` | 193 | Tk widget |  | EKSİK |
| 313 | `MERKEZ/URETIM_V4/gui_v4.py` | 194 | Tk widget |  | EKSİK |
| 314 | `MERKEZ/URETIM_V4/gui_v4.py` | 195 | Tk widget |  | EKSİK |
| 315 | `MERKEZ/URETIM_V4/gui_v4.py` | 196 | Tk widget |  | EKSİK |
| 316 | `MERKEZ/URETIM_V4/gui_v4.py` | 197 | Tk widget |  | EKSİK |
| 317 | `MERKEZ/URETIM_V4/gui_v4.py` | 199 | Tk widget | â˜ Linke Ã§evir + Excelâ€™e yaz | EKSİK |
| 318 | `MERKEZ/URETIM_V4/gui_v4.py` | 202 | Tk widget | MaÄŸaza Trendyol Excelâ€™i | EKSİK |
| 319 | `MERKEZ/URETIM_V4/gui_v4.py` | 204 | Tk widget | Ã‡Ä±ktÄ± klasÃ¶rÃ¼ | EKSİK |
| 320 | `MERKEZ/URETIM_V4/gui_v4.py` | 206 | Tk widget | Son Excelâ€™i aÃ§ | EKSİK |
| 321 | `MERKEZ/URETIM_V4/gui_v4.py` | 219 | Tk widget |  | EKSİK |
| 322 | `MERKEZ/URETIM_V4/gui_v4.py` | 221 | Tk widget |  | EKSİK |
| 323 | `MERKEZ/URETIM_V4/gui_v4.py` | 222 | Tk widget |  | EKSİK |
| 324 | `MERKEZ/URETIM_V4/gui_v4.py` | 226 | Tk widget |  | EKSİK |
| 325 | `MERKEZ/URETIM_V4/gui_v4.py` | 272 | Tk widget |  | EKSİK |
| 326 | `MERKEZ/URETIM_V4/gui_v4.py` | 274 | Tk widget |  | EKSİK |
| 327 | `MERKEZ/URETIM_V4/gui_v4.py` | 279 | Tk widget |  | EKSİK |
| 328 | `MERKEZ/URETIM_V4/gui_v4.py` | 293 | Tk widget |  | EKSİK |
| 329 | `MERKEZ/URETIM_V4/gui_v4.py` | 295 | Tk widget |  | EKSİK |
| 330 | `MERKEZ/URETIM_V4/gui_v4.py` | 297 | Tk widget |  | EKSİK |
| 331 | `MERKEZ/URETIM_V4/gui_v4.py` | 299 | Tk widget |  | EKSİK |
| 332 | `MERKEZ/URETIM_V4/gui_v4.py` | 301 | Tk widget | GeliÅŸmiÅŸ AraÃ§lar | EKSİK |
| 333 | `MERKEZ/URETIM_V4/gui_v4.py` | 309 | Tk widget |  | EKSİK |
| 334 | `MERKEZ/URETIM_V4/gui_v4.py` | 311 | Tk widget |  | EKSİK |
| 335 | `MERKEZ/URETIM_V4/gui_v4.py` | 316 | Tk widget |  | EKSİK |
| 336 | `MERKEZ/URETIM_V4/gui_v4.py` | 318 | Tk widget |  | EKSİK |
| 337 | `MERKEZ/URETIM_V4/gui_v4.py` | 325 | Tk widget |  | EKSİK |
| 338 | `MERKEZ/URETIM_V4/gui_v4.py` | 328 | Tk widget | Kaynak fotoÄŸraf Ã¶nizlemesi | EKSİK |
| 339 | `MERKEZ/URETIM_V4/gui_v4.py` | 331 | Tk widget |  | EKSİK |
| 340 | `MERKEZ/URETIM_V4/gui_v4.py` | 341 | Tk widget |  | EKSİK |
| 341 | `MERKEZ/URETIM_V4/gui_v4.py` | 343 | Tk widget | Kategori: | KISMİ |
| 342 | `MERKEZ/URETIM_V4/gui_v4.py` | 346 | Tk widget |  | EKSİK |
| 343 | `MERKEZ/URETIM_V4/gui_v4.py` | 349 | Tk widget | Åablon ara: | EKSİK |
| 344 | `MERKEZ/URETIM_V4/gui_v4.py` | 351 | Tk widget |  | EKSİK |
| 345 | `MERKEZ/URETIM_V4/gui_v4.py` | 352 | Tk widget | SÄ±rala: | EKSİK |
| 346 | `MERKEZ/URETIM_V4/gui_v4.py` | 354 | Tk widget |  | EKSİK |
| 347 | `MERKEZ/URETIM_V4/gui_v4.py` | 364 | Tk widget |  | EKSİK |
| 348 | `MERKEZ/URETIM_V4/gui_v4.py` | 370 | Tk widget |  | EKSİK |
| 349 | `MERKEZ/URETIM_V4/gui_v4.py` | 372 | Tk widget | SeÃ§im iÅŸlemleri: | EKSİK |
| 350 | `MERKEZ/URETIM_V4/gui_v4.py` | 373 | Tk widget | TÃ¼m onaylÄ±larÄ± seÃ§ | EKSİK |
| 351 | `MERKEZ/URETIM_V4/gui_v4.py` | 383 | Tk widget |  | EKSİK |
| 352 | `MERKEZ/URETIM_V4/gui_v4.py` | 386 | Tk widget |  | EKSİK |
| 353 | `MERKEZ/URETIM_V4/gui_v4.py` | 388 | Tk widget | Nedenleri GÃ¶r | EKSİK |
| 354 | `MERKEZ/URETIM_V4/gui_v4.py` | 402 | Tk widget |  | EKSİK |
| 355 | `MERKEZ/URETIM_V4/gui_v4.py` | 415 | Tk widget |  | EKSİK |
| 356 | `MERKEZ/URETIM_V4/gui_v4.py` | 422 | Tk widget | 02  BASKI TASARIMLARINI SEÃ‡ | EKSİK |
| 357 | `MERKEZ/URETIM_V4/gui_v4.py` | 424 | Tk widget |  | EKSİK |
| 358 | `MERKEZ/URETIM_V4/gui_v4.py` | 429 | Tk widget |  | EKSİK |
| 359 | `MERKEZ/URETIM_V4/gui_v4.py` | 430 | Tk widget |  | EKSİK |
| 360 | `MERKEZ/URETIM_V4/gui_v4.py` | 444 | Tk widget |  | EKSİK |
| 361 | `MERKEZ/URETIM_V4/gui_v4.py` | 458 | Tk widget | 03  MAÄAZA SEÃ‡ | EKSİK |
| 362 | `MERKEZ/URETIM_V4/gui_v4.py` | 460 | Tk widget |  | EKSİK |
| 363 | `MERKEZ/URETIM_V4/gui_v4.py` | 462 | Tk widget |  | EKSİK |
| 364 | `MERKEZ/URETIM_V4/gui_v4.py` | 470 | Tk widget |  | EKSİK |
| 365 | `MERKEZ/URETIM_V4/gui_v4.py` | 472 | Tk widget | MaÄŸaza grubu: | EKSİK |
| 366 | `MERKEZ/URETIM_V4/gui_v4.py` | 474 | Tk widget |  | EKSİK |
| 367 | `MERKEZ/URETIM_V4/gui_v4.py` | 484 | Tk widget |  | EKSİK |
| 368 | `MERKEZ/URETIM_V4/gui_v4.py` | 486 | Tk widget | MaÄŸazalar (Ctrl ile Ã§oklu seÃ§): | EKSİK |
| 369 | `MERKEZ/URETIM_V4/gui_v4.py` | 487 | Tk widget |  | EKSİK |
| 370 | `MERKEZ/URETIM_V4/gui_v4.py` | 495 | Tk widget |  | EKSİK |
| 371 | `MERKEZ/URETIM_V4/gui_v4.py` | 497 | Tk widget | MaÄŸaza YÃ¶netimi | EKSİK |
| 372 | `MERKEZ/URETIM_V4/gui_v4.py` | 506 | Tk widget | MaÄŸaza listesini yenile | EKSİK |
| 373 | `MERKEZ/URETIM_V4/gui_v4.py` | 515 | Tk widget |  | EKSİK |
| 374 | `MERKEZ/URETIM_V4/gui_v4.py` | 517 | Tk widget | MaÄŸaza kapsamÄ±: | EKSİK |
| 375 | `MERKEZ/URETIM_V4/gui_v4.py` | 518 | Tk widget | MaÄŸazaya atananlarÄ± Ã¼retime seÃ§ | EKSİK |
| 376 | `MERKEZ/URETIM_V4/gui_v4.py` | 531 | Tk widget |  | EKSİK |
| 377 | `MERKEZ/URETIM_V4/gui_v4.py` | 540 | Tk widget | 04  ÃœRETÄ°M AYARLARI | EKSİK |
| 378 | `MERKEZ/URETIM_V4/gui_v4.py` | 542 | Tk widget |  | EKSİK |
| 379 | `MERKEZ/URETIM_V4/gui_v4.py` | 544 | Tk widget | TasarÄ±m YerleÅŸimi: | EKSİK |
| 380 | `MERKEZ/URETIM_V4/gui_v4.py` | 546 | Tk widget |  | EKSİK |
| 381 | `MERKEZ/URETIM_V4/gui_v4.py` | 564 | Tk widget |  | EKSİK |
| 382 | `MERKEZ/URETIM_V4/gui_v4.py` | 566 | Tk widget | Ãœretim modeli: | EKSİK |
| 383 | `MERKEZ/URETIM_V4/gui_v4.py` | 567 | Tk widget |  | EKSİK |
| 384 | `MERKEZ/URETIM_V4/gui_v4.py` | 589 | Tk widget |  | EKSİK |
| 385 | `MERKEZ/URETIM_V4/gui_v4.py` | 596 | Tk widget |  | EKSİK |
| 386 | `MERKEZ/URETIM_V4/gui_v4.py` | 598 | Tk widget |  | EKSİK |
| 387 | `MERKEZ/URETIM_V4/gui_v4.py` | 602 | Tk widget | 4K Kurulumunu Kontrol Et | EKSİK |
| 388 | `MERKEZ/URETIM_V4/gui_v4.py` | 605 | Tk widget |  | EKSİK |
| 389 | `MERKEZ/URETIM_V4/gui_v4.py` | 626 | Tk widget |  | EKSİK |
| 390 | `MERKEZ/URETIM_V4/gui_v4.py` | 628 | Tk widget |  | EKSİK |
| 391 | `MERKEZ/URETIM_V4/gui_v4.py` | 630 | Tk widget | HazÄ±r katman Ã¶n kontrolÃ¼ | EKSİK |
| 392 | `MERKEZ/URETIM_V4/gui_v4.py` | 632 | Tk widget | HazÄ±r GÃ¶rsel YÃ¼kle Overlay Uygula | EKSİK |
| 393 | `MERKEZ/URETIM_V4/gui_v4.py` | 644 | Tk widget |  | EKSİK |
| 394 | `MERKEZ/URETIM_V4/gui_v4.py` | 659 | Tk widget |  | EKSİK |
| 395 | `MERKEZ/URETIM_V4/gui_v4.py` | 661 | Tk widget |  | EKSİK |
| 396 | `MERKEZ/URETIM_V4/gui_v4.py` | 677 | Tk widget |  | EKSİK |
| 397 | `MERKEZ/URETIM_V4/gui_v4.py` | 680 | Tk widget |  | EKSİK |
| 398 | `MERKEZ/URETIM_V4/gui_v4.py` | 684 | Tk widget | SaÄŸlayÄ±cÄ±: | EKSİK |
| 399 | `MERKEZ/URETIM_V4/gui_v4.py` | 685 | Tk widget |  | EKSİK |
| 400 | `MERKEZ/URETIM_V4/gui_v4.py` | 687 | Tk widget | ImageKit Private Key: | EKSİK |
| 401 | `MERKEZ/URETIM_V4/gui_v4.py` | 688 | Tk widget |  | EKSİK |
| 402 | `MERKEZ/URETIM_V4/gui_v4.py` | 690 | Tk widget |  | EKSİK |
| 403 | `MERKEZ/URETIM_V4/gui_v4.py` | 693 | Tk widget | MaÄŸaza BazlÄ± Trendyol Excel OluÅŸtur | EKSİK |
| 404 | `MERKEZ/URETIM_V4/gui_v4.py` | 694 | Tk widget | Trendyol Ã§Ä±ktÄ± klasÃ¶rÃ¼ | EKSİK |
| 405 | `MERKEZ/URETIM_V4/gui_v4.py` | 695 | Tk widget | Son Trendyol Excelâ€™i aÃ§ | EKSİK |
| 406 | `MERKEZ/URETIM_V4/gui_v4.py` | 696 | Tk widget |  | EKSİK |
| 407 | `MERKEZ/URETIM_V4/gui_v4.py` | 698 | Tk widget |  | EKSİK |
| 408 | `MERKEZ/URETIM_V4/gui_v4.py` | 714 | Tk widget |  | EKSİK |
| 409 | `MERKEZ/URETIM_V4/gui_v4.py` | 717 | Tk widget |  | EKSİK |
| 410 | `MERKEZ/URETIM_V4/gui_v4.py` | 723 | Tk widget |  | EKSİK |
| 411 | `MERKEZ/URETIM_V4/gui_v4.py` | 725 | Tk widget |  | EKSİK |
| 412 | `MERKEZ/URETIM_V4/gui_v4.py` | 794 | Tk widget | Ã‡alÄ±ÅŸma Panelleri: | EKSİK |
| 413 | `MERKEZ/URETIM_V4/gui_v4.py` | 797 | Tk widget |  | EKSİK |
| 414 | `MERKEZ/URETIM_V4/gui_v4.py` | 800 | Tk widget | âœ¥ ArayÃ¼zÃ¼ DÃ¼zenle | EKSİK |
| 415 | `MERKEZ/URETIM_V4/gui_v4.py` | 883 | Tk widget |  | EKSİK |
| 416 | `MERKEZ/URETIM_V4/gui_v4.py` | 888 | Tk widget |  | EKSİK |
| 417 | `MERKEZ/URETIM_V4/gui_v4.py` | 890 | Tk widget | GeliÅŸmiÅŸ AraÃ§lar | EKSİK |
| 418 | `MERKEZ/URETIM_V4/gui_v4.py` | 891 | Tk widget |  | EKSİK |
| 419 | `MERKEZ/URETIM_V4/gui_v4.py` | 895 | Tk widget |  | EKSİK |
| 420 | `MERKEZ/URETIM_V4/gui_v4.py` | 900 | Tk widget |  | EKSİK |
| 421 | `MERKEZ/URETIM_V4/gui_v4.py` | 902 | Tk widget |  | EKSİK |
| 422 | `MERKEZ/URETIM_V4/gui_v4.py` | 964 | Tk widget | GÃ¼neÅŸ / gerÃ§ekÃ§ilik profili | EKSİK |
| 423 | `MERKEZ/URETIM_V4/gui_v4.py` | 966 | Tk widget |  | EKSİK |
| 424 | `MERKEZ/URETIM_V4/gui_v4.py` | 969 | Tk widget |  | EKSİK |
| 425 | `MERKEZ/URETIM_V4/gui_v4.py` | 978 | Tk widget | PETEK gerÃ§ek yarÄ±k gÃ¶lgesi | EKSİK |
| 426 | `MERKEZ/URETIM_V4/gui_v4.py` | 980 | Tk widget |  | EKSİK |
| 427 | `MERKEZ/URETIM_V4/gui_v4.py` | 984 | Tk widget | PETEK doÄŸallÄ±k profili | EKSİK |
| 428 | `MERKEZ/URETIM_V4/gui_v4.py` | 986 | Tk widget |  | EKSİK |
| 429 | `MERKEZ/URETIM_V4/gui_v4.py` | 990 | Tk widget | PETEK pembe temizlik | EKSİK |
| 430 | `MERKEZ/URETIM_V4/gui_v4.py` | 993 | Tk widget |  | EKSİK |
| 431 | `MERKEZ/URETIM_V4/gui_v4.py` | 1002 | Tk widget | Kapat | KISMİ |
| 432 | `MERKEZ/URETIM_V4/gui_v4.py` | 1007 | Tk widget |  | EKSİK |
| 433 | `MERKEZ/URETIM_V4/gui_v4.py` | 1010 | Tk widget |  | EKSİK |
| 434 | `MERKEZ/URETIM_V4/gui_v4.py` | 1012 | Tk widget | 4K modelini seÃ§in | EKSİK |
| 435 | `MERKEZ/URETIM_V4/gui_v4.py` | 1013 | Tk widget |  | EKSİK |
| 436 | `MERKEZ/URETIM_V4/gui_v4.py` | 1020 | Tk widget | Kapat | KISMİ |
| 437 | `MERKEZ/URETIM_V4/gui_v4.py` | 1121 | Tk widget |  | EKSİK |
| 438 | `MERKEZ/URETIM_V4/gui_v4.py` | 1124 | Tk widget |  | EKSİK |
| 439 | `MERKEZ/URETIM_V4/gui_v4.py` | 1130 | Tk widget |  | EKSİK |
| 440 | `MERKEZ/URETIM_V4/gui_v4.py` | 1134 | Tk widget | Raporu Kopyala | KISMİ |
| 441 | `MERKEZ/URETIM_V4/gui_v4.py` | 1135 | Tk widget | Bu MaÄŸazanÄ±n MockuplarÄ±nÄ± GÃ¶ster | EKSİK |
| 442 | `MERKEZ/URETIM_V4/gui_v4.py` | 1137 | Tk widget | Kapat | KISMİ |
| 443 | `MERKEZ/URETIM_V4/gui_v4.py` | 1202 | Tk widget |  | EKSİK |
| 444 | `MERKEZ/URETIM_V4/gui_v4.py` | 1206 | Tk widget |  | EKSİK |
| 445 | `MERKEZ/URETIM_V4/gui_v4.py` | 1208 | Tk widget | Ãœretim gÃ¼venli biÃ§imde engellendi | EKSİK |
| 446 | `MERKEZ/URETIM_V4/gui_v4.py` | 1214 | Tk widget |  | EKSİK |
| 447 | `MERKEZ/URETIM_V4/gui_v4.py` | 1219 | Tk widget | MaÄŸazaya AtananlarÄ± Ãœretime SeÃ§ | EKSİK |
| 448 | `MERKEZ/URETIM_V4/gui_v4.py` | 1221 | Tk widget | Bu MaÄŸazanÄ±n MockuplarÄ±nÄ± GÃ¶ster | EKSİK |
| 449 | `MERKEZ/URETIM_V4/gui_v4.py` | 1223 | Tk widget | DetaylÄ± Salt Okunur Rapor | EKSİK |
| 450 | `MERKEZ/URETIM_V4/gui_v4.py` | 1232 | Tk widget | Bu MockupÄ± MaÄŸazaya Ataâ€¦ | EKSİK |
| 451 | `MERKEZ/URETIM_V4/gui_v4.py` | 1236 | Tk widget | Kapat | KISMİ |
| 452 | `MERKEZ/URETIM_V4/gui_v4.py` | 1631 | Tk widget |  | EKSİK |
| 453 | `MERKEZ/URETIM_V4/gui_v4.py` | 1637 | Tk widget |  | EKSİK |
| 454 | `MERKEZ/URETIM_V4/gui_v4.py` | 1639 | Tk widget |  | EKSİK |
| 455 | `MERKEZ/URETIM_V4/gui_v4.py` | 1641 | Tk widget |  | EKSİK |
| 456 | `MERKEZ/URETIM_V4/gui_v4.py` | 1679 | Tk widget | Kapat | KISMİ |
| 457 | `MERKEZ/URETIM_V4/gui_v4.py` | 2358 | Tk widget |  | EKSİK |
| 458 | `MERKEZ/URETIM_V4/gui_v4.py` | 2368 | Tk widget |  | EKSİK |
| 459 | `MERKEZ/URETIM_V4/gui_v4.py` | 2370 | Tk widget |  | EKSİK |
| 460 | `MERKEZ/URETIM_V4/gui_v4.py` | 2371 | Tk widget |  | EKSİK |
| 461 | `MERKEZ/URETIM_V4/gui_v4.py` | 2372 | Tk widget |  | EKSİK |
| 462 | `MERKEZ/URETIM_V4/gui_v4.py` | 2373 | Tk widget |  | EKSİK |
| 463 | `MERKEZ/URETIM_V4/gui_v4.py` | 2384 | Tk widget |  | EKSİK |
| 464 | `MERKEZ/URETIM_V4/gui_v4.py` | 2388 | Tk widget |  | EKSİK |
| 465 | `MERKEZ/URETIM_V4/gui_v4.py` | 2400 | Tk widget |  | EKSİK |
| 466 | `MERKEZ/URETIM_V4/gui_v4.py` | 268 | HTML kontrol |  | EKSİK |
| 467 | `MERKEZ/URETIM_V4/gui_v4.py` | 270 | HTML kontrol |  | EKSİK |
| 468 | `MERKEZ/URETIM_V4/gui_v4.py` | 2938 | HTML kontrol |  | EKSİK |
| 469 | `MERKEZ/URETIM_V4/gui_v4.py` | 2939 | HTML kontrol |  | EKSİK |
| 470 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 39 | Tk widget |  | EKSİK |
| 471 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 60 | Tk widget |  | EKSİK |
| 472 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 62 | Tk widget | MAÄAZAâ€“MOCKUP EÅLEÅTÄ°RME MERKEZÄ° | EKSİK |
| 473 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 64 | Tk widget |  | EKSİK |
| 474 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 66 | Tk widget |  | EKSİK |
| 475 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 69 | Tk widget | 1  MAÄAZA VE KATEGORÄ° | EKSİK |
| 476 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 71 | Tk widget |  | EKSİK |
| 477 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 73 | Tk widget | MaÄŸaza: | EKSİK |
| 478 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 75 | Tk widget |  | EKSİK |
| 479 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 78 | Tk widget | Yeni maÄŸaza adÄ±: | EKSİK |
| 480 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 80 | Tk widget |  | EKSİK |
| 481 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 81 | Tk widget | KÄ±sa kod: | EKSİK |
| 482 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 83 | Tk widget |  | EKSİK |
| 483 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 84 | Tk widget | MaÄŸaza OluÅŸtur | EKSİK |
| 484 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 85 | Tk widget | Kategori: | KISMİ |
| 485 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 87 | Tk widget |  | EKSİK |
| 486 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 91 | Tk widget | Listeyi Yenile | KISMİ |
| 487 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 93 | Tk widget |  | EKSİK |
| 488 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 97 | Tk widget |  | EKSİK |
| 489 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 100 | Tk widget |  | EKSİK |
| 490 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 102 | Tk widget |  | EKSİK |
| 491 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 104 | Tk widget | Ara: | KISMİ |
| 492 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 106 | Tk widget |  | EKSİK |
| 493 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 108 | Tk widget |  | EKSİK |
| 494 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 110 | Tk widget | Sayfadaki UygunlarÄ± SeÃ§ | EKSİK |
| 495 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 111 | Tk widget | Kategorideki TÃ¼m UygunlarÄ± SeÃ§ | EKSİK |
| 496 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 112 | Tk widget | SeÃ§imi Temizle | KISMİ |
| 497 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 114 | Tk widget |  | EKSİK |
| 498 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 115 | Tk widget |  | EKSİK |
| 499 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 117 | Tk widget | â—€ Ã–nceki | KISMİ |
| 500 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 119 | Tk widget |  | EKSİK |
| 501 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 120 | Tk widget | Sonraki â–¶ | KISMİ |
| 502 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 121 | Tk widget |  | EKSİK |
| 503 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 139 | Tk widget |  | EKSİK |
| 504 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 149 | Tk widget |  | EKSİK |
| 505 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 153 | Tk widget |  | EKSİK |
| 506 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 155 | Tk widget |  | EKSİK |
| 507 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 157 | Tk widget |  | EKSİK |
| 508 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 169 | Tk widget |  | EKSİK |
| 509 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 175 | Tk widget |  | EKSİK |
| 510 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 177 | Tk widget |  | EKSİK |
| 511 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 179 | Tk widget | TÃ¼m AtamalarÄ± SeÃ§ | EKSİK |
| 512 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 181 | Tk widget | Bu Kategoriyi SeÃ§ | EKSİK |
| 513 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 183 | Tk widget | SeÃ§imi Temizle | KISMİ |
| 514 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 185 | Tk widget | SEÃ‡Ä°LÄ° ATAMALARI TOPLU KALDIR | EKSİK |
| 515 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 187 | Tk widget |  | EKSİK |
| 516 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 190 | Tk widget |  | EKSİK |
| 517 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 193 | Tk widget |  | EKSİK |
| 518 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 195 | Tk widget |  | EKSİK |
| 519 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 198 | Tk widget |  | EKSİK |
| 520 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 199 | Tk widget |  | EKSİK |
| 521 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 201 | Tk widget | Kapat | KISMİ |
| 522 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 202 | Tk widget | âœ“ SOLDAN SEÃ‡Ä°LENLERÄ° MAÄAZAYA ATA | EKSİK |
| 523 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 508 | Tk widget |  | EKSİK |
| 524 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 514 | Tk widget |  | EKSİK |
| 525 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 516 | Tk widget |  | EKSİK |
| 526 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 517 | Tk widget |  | EKSİK |
| 527 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 519 | Tk widget |  | EKSİK |
| 528 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 521 | Tk widget |  | EKSİK |
| 529 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 523 | Tk widget |  | EKSİK |
| 530 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 525 | Tk widget |  | EKSİK |
| 531 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 528 | Tk widget |  | EKSİK |
| 532 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 540 | Tk widget |  | EKSİK |
| 533 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 542 | Tk widget | VazgeÃ§ | EKSİK |
| 534 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 543 | Tk widget |  | EKSİK |
| 535 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 580 | Tk widget |  | EKSİK |
| 536 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 586 | Tk widget |  | EKSİK |
| 537 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 588 | Tk widget |  | EKSİK |
| 538 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 589 | Tk widget |  | EKSİK |
| 539 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 591 | Tk widget |  | EKSİK |
| 540 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 594 | Tk widget |  | EKSİK |
| 541 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 596 | Tk widget |  | EKSİK |
| 542 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 599 | Tk widget |  | EKSİK |
| 543 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 611 | Tk widget |  | EKSİK |
| 544 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 613 | Tk widget | VazgeÃ§ | EKSİK |
| 545 | `MERKEZ/URETIM_V4/store_assignment_ui_v410.py` | 614 | Tk widget |  | EKSİK |
| 546 | `MERKEZ/URETIM_V4/ui_table_v1.py` | 30 | Tk widget |  | EKSİK |
| 547 | `MERKEZ/URETIM_V4/ui_table_v1.py` | 202 | Tk widget |  | EKSİK |
| 548 | `MERKEZ/URETIM_V4/ui_table_v1.py` | 210 | Tk widget |  | EKSİK |
| 549 | `MERKEZ/URETIM_V4/ui_table_v1.py` | 273 | Tk widget |  | EKSİK |
| 550 | `MERKEZ/URETIM_V4/ui_table_v1.py` | 56 | HTML kontrol |  | EKSİK |
| 551 | `MERKEZ/URETIM_V4/ui_table_v1.py` | 102 | HTML kontrol |  | EKSİK |
| 552 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 36 | Tk widget |  | EKSİK |
| 553 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 38 | Tk widget |  | EKSİK |
| 554 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 41 | Tk widget | Slot ve Overlay AyarlarÄ±â€¦ | EKSİK |
| 555 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 42 | Tk widget | Ãœretim Ã–ncesi Kontrol | EKSİK |
| 556 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 43 | Tk widget | Ãœretim GeÃ§miÅŸi | EKSİK |
| 557 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 133 | Tk widget |  | EKSİK |
| 558 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 138 | Tk widget |  | EKSİK |
| 559 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 140 | Tk widget |  | EKSİK |
| 560 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 142 | Tk widget |  | EKSİK |
| 561 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 159 | Tk widget |  | EKSİK |
| 562 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 162 | Tk widget |  | EKSİK |
| 563 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 167 | Tk widget |  | EKSİK |
| 564 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 169 | Tk widget |  | EKSİK |
| 565 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 172 | Tk widget |  | EKSİK |
| 566 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 173 | Tk widget |  | EKSİK |
| 567 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 179 | Tk widget |  | EKSİK |
| 568 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 204 | Tk widget |  | EKSİK |
| 569 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 206 | Tk widget |  | EKSİK |
| 570 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 207 | Tk widget |  | EKSİK |
| 571 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 210 | Tk widget |  | EKSİK |
| 572 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 217 | Tk widget | Ã–zel dosyaâ€¦ | EKSİK |
| 573 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 218 | Tk widget | VarsayÄ±lan | EKSİK |
| 574 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 246 | Tk widget |  | EKSİK |
| 575 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 248 | Tk widget | Kaydet | KISMİ |
| 576 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 249 | Tk widget | VazgeÃ§ | EKSİK |
| 577 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 258 | Tk widget |  | EKSİK |
| 578 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 263 | Tk widget |  | EKSİK |
| 579 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 268 | Tk widget |  | EKSİK |
| 580 | `MERKEZ/URETIM_V4/four_mockup_ui_v1.py` | 288 | Tk widget | Yenile | KISMİ |
| 581 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 345 | Tk widget |  | EKSİK |
| 582 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 352 | Tk widget |  | EKSİK |
| 583 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 357 | Tk widget |  | EKSİK |
| 584 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 366 | Tk widget | âŸ³ Yenile | KISMİ |
| 585 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 369 | Tk widget | Sistem SaÄŸlÄ±ÄŸÄ± | EKSİK |
| 586 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 374 | Tk widget |  | EKSİK |
| 587 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 376 | Tk widget | KayÄ±tlar yÃ¼kleniyorâ€¦ | EKSİK |
| 588 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 380 | Tk widget | â–¶  YarÄ±m KalanÄ± Devam Ettir | EKSİK |
| 589 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 383 | Tk widget | ğŸ›   Kesinti Kurtarma Denetimi | EKSİK |
| 590 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 389 | Tk widget |  | EKSİK |
| 591 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 393 | Tk widget | Son Ãœretimler | EKSİK |
| 592 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 399 | Tk widget |  | EKSİK |
| 593 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 409 | Tk widget |  | EKSİK |
| 594 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 417 | Tk widget |  | EKSİK |
| 595 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 420 | Tk widget |  | EKSİK |
| 596 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 421 | Tk widget |  | EKSİK |
| 597 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 429 | Tk widget | Hata Nedenleri (en sÄ±k) | EKSİK |
| 598 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 433 | Tk widget |  | EKSİK |
| 599 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 452 | Tk widget |  | EKSİK |
| 600 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 455 | Tk widget |  | EKSİK |
| 601 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 459 | Tk widget |  | EKSİK |
| 602 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 468 | Tk widget |  | EKSİK |
| 603 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 475 | Tk widget |  | EKSİK |
| 604 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 481 | Tk widget | Ã–nizleme iÃ§in bir satÄ±r seÃ§in | EKSİK |
| 605 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 484 | Tk widget |  | EKSİK |
| 606 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 488 | Tk widget | ğŸ“‚  Ã‡Ä±ktÄ± KlasÃ¶rÃ¼nÃ¼ AÃ§ | EKSİK |
| 607 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 502 | Tk widget |  | EKSİK |
| 608 | `MERKEZ/URETIM_V4/uretim_kayitlari_v1.py` | 504 | Tk widget |  | EKSİK |
| 609 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 71 | Tk widget |  | EKSİK |
| 610 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 79 | Tk widget |  | EKSİK |
| 611 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 81 | Tk widget | âŸ³ Yenile | KISMİ |
| 612 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 86 | Tk widget |  | EKSİK |
| 613 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 93 | Tk widget |  | EKSİK |
| 614 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 100 | Tk widget |  | EKSİK |
| 615 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 136 | Tk widget |  | EKSİK |
| 616 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 140 | Tk widget |  | EKSİK |
| 617 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 143 | Tk widget |  | EKSİK |
| 618 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 157 | Tk widget |  | EKSİK |
| 619 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 162 | Tk widget |  | EKSİK |
| 620 | `MERKEZ/URETIM_V4/raporlar_tarama_v1.py` | 165 | Tk widget |  | EKSİK |
| 621 | `MERKEZ/magaza_profilleri_v1.py` | 219 | Tk widget |  | EKSİK |
| 622 | `MERKEZ/magaza_profilleri_v1.py` | 226 | Tk widget |  | EKSİK |
| 623 | `MERKEZ/magaza_profilleri_v1.py` | 231 | Tk widget |  | EKSİK |
| 624 | `MERKEZ/magaza_profilleri_v1.py` | 240 | Tk widget | âŸ³ Yenile | KISMİ |
| 625 | `MERKEZ/magaza_profilleri_v1.py` | 243 | Tk widget | DoÄŸrula | KISMİ |
| 626 | `MERKEZ/magaza_profilleri_v1.py` | 248 | Tk widget |  | EKSİK |
| 627 | `MERKEZ/magaza_profilleri_v1.py` | 252 | Tk widget |  | EKSİK |
| 628 | `MERKEZ/magaza_profilleri_v1.py` | 256 | Tk widget | MAÄAZALAR | EKSİK |
| 629 | `MERKEZ/magaza_profilleri_v1.py` | 259 | Tk widget |  | EKSİK |
| 630 | `MERKEZ/magaza_profilleri_v1.py` | 266 | Tk widget |  | EKSİK |
| 631 | `MERKEZ/magaza_profilleri_v1.py` | 273 | Tk widget | ï¼‹ MaÄŸaza Ekle | EKSİK |
| 632 | `MERKEZ/magaza_profilleri_v1.py` | 277 | Tk widget |  | EKSİK |
| 633 | `MERKEZ/magaza_profilleri_v1.py` | 282 | Tk widget | KayÄ±tlÄ± Ayarlar | KISMİ |
| 634 | `MERKEZ/magaza_profilleri_v1.py` | 286 | Tk widget | MaÄŸaza kimliÄŸi: | EKSİK |
| 635 | `MERKEZ/magaza_profilleri_v1.py` | 289 | Tk widget |  | EKSİK |
| 636 | `MERKEZ/magaza_profilleri_v1.py` | 291 | Tk widget | KÄ±sa kod: | EKSİK |
| 637 | `MERKEZ/magaza_profilleri_v1.py` | 294 | Tk widget |  | EKSİK |
| 638 | `MERKEZ/magaza_profilleri_v1.py` | 298 | Tk widget | Kaydet | KISMİ |
| 639 | `MERKEZ/magaza_profilleri_v1.py` | 302 | Tk widget |  | EKSİK |
| 640 | `MERKEZ/magaza_profilleri_v1.py` | 306 | Tk widget | AtanmÄ±ÅŸ Åablon Havuzu (salt okunur) | EKSİK |
| 641 | `MERKEZ/magaza_profilleri_v1.py` | 313 | Tk widget |  | EKSİK |
| 642 | `MERKEZ/magaza_profilleri_v1.py` | 320 | Tk widget |  | EKSİK |
| 643 | `MERKEZ/magaza_profilleri_v1.py` | 333 | Tk widget |  | EKSİK |
| 644 | `MERKEZ/magaza_profilleri_v1.py` | 336 | Tk widget | Havuz yalnÄ±z | KISMİ |
| 645 | `MERKEZ/magaza_profilleri_v1.py` | 339 | Tk widget |  | EKSİK |
| 646 | `MERKEZ/magaza_profilleri_v1.py` | 505 | Tk widget |  | EKSİK |
| 647 | `MERKEZ/magaza_profilleri_v1.py` | 511 | Tk widget |  | EKSİK |
| 648 | `MERKEZ/magaza_profilleri_v1.py` | 514 | Tk widget |  | EKSİK |
| 649 | `MERKEZ/magaza_profilleri_v1.py` | 519 | Tk widget |  | EKSİK |
| 650 | `MERKEZ/magaza_profilleri_v1.py` | 522 | Tk widget |  | EKSİK |
| 651 | `MERKEZ/magaza_profilleri_v1.py` | 527 | Tk widget |  | EKSİK |
| 652 | `MERKEZ/magaza_profilleri_v1.py` | 543 | Tk widget | VazgeÃ§ | EKSİK |
| 653 | `MERKEZ/magaza_profilleri_v1.py` | 545 | Tk widget | OluÅŸtur | KISMİ |
| 654 | `MERKEZ/tasarim_yonetimi_v1.py` | 178 | Tk widget |  | EKSİK |
| 655 | `MERKEZ/tasarim_yonetimi_v1.py` | 185 | Tk widget |  | EKSİK |
| 656 | `MERKEZ/tasarim_yonetimi_v1.py` | 190 | Tk widget |  | EKSİK |
| 657 | `MERKEZ/tasarim_yonetimi_v1.py` | 199 | Tk widget | âŸ³ Yenile | KISMİ |
| 658 | `MERKEZ/tasarim_yonetimi_v1.py` | 202 | Tk widget | KlasÃ¶rÃ¼ AÃ§ | EKSİK |
| 659 | `MERKEZ/tasarim_yonetimi_v1.py` | 205 | Tk widget | Numara Denetimi | EKSİK |
| 660 | `MERKEZ/tasarim_yonetimi_v1.py` | 209 | Tk widget |  | EKSİK |
| 661 | `MERKEZ/tasarim_yonetimi_v1.py` | 211 | Tk widget | Ara: | KISMİ |
| 662 | `MERKEZ/tasarim_yonetimi_v1.py` | 213 | Tk widget |  | EKSİK |
| 663 | `MERKEZ/tasarim_yonetimi_v1.py` | 218 | Tk widget |  | EKSİK |
| 664 | `MERKEZ/tasarim_yonetimi_v1.py` | 223 | Tk widget |  | EKSİK |
| 665 | `MERKEZ/tasarim_yonetimi_v1.py` | 227 | Tk widget |  | EKSİK |
| 666 | `MERKEZ/tasarim_yonetimi_v1.py` | 232 | Tk widget |  | EKSİK |
| 667 | `MERKEZ/tasarim_yonetimi_v1.py` | 240 | Tk widget |  | EKSİK |
| 668 | `MERKEZ/tasarim_yonetimi_v1.py` | 250 | Tk widget |  | EKSİK |
| 669 | `MERKEZ/tasarim_yonetimi_v1.py` | 252 | Tk widget | Ã–NÄ°ZLEME | KISMİ |
| 670 | `MERKEZ/tasarim_yonetimi_v1.py` | 254 | Tk widget | Bir tasarÄ±m seÃ§in. | EKSİK |
| 671 | `MERKEZ/tasarim_yonetimi_v1.py` | 257 | Tk widget |  | EKSİK |
| 672 | `MERKEZ/dark_theme_v42.py` | 55 | Tk widget |  | EKSİK |
| 673 | `SABLON_V2_MIMARI/app.py` | 177 | Flask route | /api/session/csrf | EKSİK |
| 674 | `SABLON_V2_MIMARI/app.py` | 181 | Flask route | /api/center_identity | EKSİK |
| 675 | `SABLON_V2_MIMARI/app.py` | 374 | Flask route |  | EKSİK |
| 676 | `SABLON_V2_MIMARI/app.py` | 387 | Flask route | /favicon.ico | EKSİK |
| 677 | `SABLON_V2_MIMARI/app.py` | 401 | Flask route | /legacy-review | KISMİ |
| 678 | `SABLON_V2_MIMARI/app.py` | 412 | Flask route | /tools | KISMİ |
| 679 | `SABLON_V2_MIMARI/app.py` | 417 | Flask route | /review/v6 | KISMİ |
| 680 | `SABLON_V2_MIMARI/app.py` | 481 | Flask route | /api/inspection-package/start | KISMİ |
| 681 | `SABLON_V2_MIMARI/app.py` | 517 | Flask route | /api/inspection-package/status/<job_id> | EKSİK |
| 682 | `SABLON_V2_MIMARI/app.py` | 665 | Flask route | /api/github-sync/info | KISMİ |
| 683 | `SABLON_V2_MIMARI/app.py` | 670 | Flask route | /api/github-sync/transfer | KISMİ |
| 684 | `SABLON_V2_MIMARI/app.py` | 717 | Flask route | /api/github-sync/status/<job_id> | EKSİK |
| 685 | `SABLON_V2_MIMARI/app.py` | 757 | Flask route | /api/tools/status/<launch_id> | EKSİK |
| 686 | `SABLON_V2_MIMARI/app.py` | 765 | Flask route | /api/tools/launch/<tool_name> | EKSİK |
| 687 | `SABLON_V2_MIMARI/app.py` | 798 | Flask route | /api/ayarlar | KISMİ |
| 688 | `SABLON_V2_MIMARI/app.py` | 857 | Flask route | /api/tekil_sablon_kaydet | KISMİ |
| 689 | `SABLON_V2_MIMARI/app.py` | 876 | Flask route | /api/templates/bulk-save-geometry | EKSİK |
| 690 | `SABLON_V2_MIMARI/app.py` | 917 | Flask route | /api/anlik_beyazlat | KISMİ |
| 691 | `SABLON_V2_MIMARI/app.py` | 968 | Flask route | /api/templates/placement-preview | KISMİ |
| 692 | `SABLON_V2_MIMARI/app.py` | 1048 | Flask route | /preview/<category>/<template> | EKSİK |
| 693 | `SABLON_V2_MIMARI/app.py` | 1065 | Flask route | /api/orijinal_yukle | KISMİ |
| 694 | `SABLON_V2_MIMARI/app.py` | 1193 | Flask route | /api/lifecycle/center | KISMİ |
| 695 | `SABLON_V2_MIMARI/app.py` | 1212 | Flask route | /api/staging/latest-collision | KISMİ |
| 696 | `SABLON_V2_MIMARI/app.py` | 1272 | Flask route | /api/lifecycle/resolve-duplicate | KISMİ |
| 697 | `SABLON_V2_MIMARI/app.py` | 1323 | Flask route | /api/lifecycle/archive-working-orphan | KISMİ |
| 698 | `SABLON_V2_MIMARI/app.py` | 1369 | Flask route | /api/lifecycle/retire-db-orphan | KISMİ |
| 699 | `SABLON_V2_MIMARI/app.py` | 1415 | Flask route | /api/lifecycle/undo | KISMİ |
| 700 | `SABLON_V2_MIMARI/app.py` | 1440 | Flask route | /api/templates/replace-original | KISMİ |
| 701 | `SABLON_V2_MIMARI/app.py` | 1580 | Flask route | /api/v46/corner_draft | KISMİ |
| 702 | `SABLON_V2_MIMARI/app.py` | 1612 | Flask route | /api/auto_detect_corners | KISMİ |
| 703 | `SABLON_V2_MIMARI/app.py` | 1987 | Flask route | /api/sablon_sil | KISMİ |
| 704 | `SABLON_V2_MIMARI/app.py` | 2017 | Flask route | /api/sablon_sil_toplu | KISMİ |
| 705 | `SABLON_V2_MIMARI/app.py` | 2079 | Flask route | /api/sablon_sil_geri_al | KISMİ |
| 706 | `SABLON_V2_MIMARI/app.py` | 2447 | Flask route | /working-image/<cat>/<tmpl> | EKSİK |
| 707 | `SABLON_V2_MIMARI/app.py` | 2462 | Flask route | /original-image/<cat>/<tmpl> | EKSİK |
| 708 | `SABLON_V2_MIMARI/app.py` | 2475 | Flask route | /image/<cat>/<tmpl> | EKSİK |
| 709 | `SABLON_V2_MIMARI/app.py` | 2821 | Flask route | /api/templates/foreground_detect | EKSİK |
| 710 | `SABLON_V2_MIMARI/app.py` | 2925 | Flask route | /api/templates/analyze | EKSİK |
| 711 | `SABLON_V2_MIMARI/app.py` | 2971 | Flask route | /api/templates/approve | EKSİK |
| 712 | `SABLON_V2_MIMARI/app.py` | 3314 | Flask route | /api/templates/batch_analyze | EKSİK |
| 713 | `SABLON_V2_MIMARI/app.py` | 3361 | Flask route | /api/templates/update_corners | KISMİ |
| 714 | `SABLON_V2_MIMARI/app.py` | 4364 | Flask route | /api/jobs | KISMİ |
| 715 | `SABLON_V2_MIMARI/app.py` | 4455 | Flask route | /api/jobs/<job_id> | EKSİK |
| 716 | `SABLON_V2_MIMARI/app.py` | 4469 | Flask route | /api/jobs/<job_id>/stop | EKSİK |
| 717 | `SABLON_V2_MIMARI/app.py` | 4489 | Flask route | /api/analysis-cache/stats | EKSİK |
| 718 | `SABLON_V2_MIMARI/app.py` | 4498 | Flask route | /api/template-health | KISMİ |
| 719 | `SABLON_V2_MIMARI/app.py` | 4531 | Flask route | /api/template-health/last | KISMİ |
| 720 | `SABLON_V2_MIMARI/app.py` | 4552 | Flask route | /api/template-health/history | KISMİ |
| 721 | `SABLON_V2_MIMARI/app.py` | 4567 | Flask route | /api/workspace-consistency/last | KISMİ |
| 722 | `SABLON_V2_MIMARI/app.py` | 4586 | Flask route | /api/workspace-consistency/history | KISMİ |
| 723 | `SABLON_V2_MIMARI/app.py` | 4604 | Flask route | /api/saglik_durumu | KISMİ |
| 724 | `SABLON_V2_MIMARI/app.py` | 4647 | Flask route | /<path:filename> | EKSİK |
| 725 | `SABLON_V2_MIMARI/tools_runner.py` | 408 | Tk widget |  | EKSİK |
| 726 | `SABLON_V2_MIMARI/tools_runner.py` | 419 | Tk widget |  | EKSİK |
| 727 | `SABLON_V2_MIMARI/tools_runner.py` | 421 | Tk widget | Åablon kategorisini seÃ§in: | EKSİK |
| 728 | `SABLON_V2_MIMARI/tools_runner.py` | 424 | Tk widget |  | EKSİK |
| 729 | `SABLON_V2_MIMARI/tools_runner.py` | 427 | Tk widget |  | EKSİK |
| 730 | `SABLON_V2_MIMARI/tools_runner.py` | 428 | Tk widget |  | EKSİK |
| 731 | `SABLON_V2_MIMARI/tools_runner.py` | 430 | Tk widget |  | EKSİK |
| 732 | `SABLON_V2_MIMARI/tools_runner.py` | 432 | Tk widget | Devam Et | EKSİK |
| 733 | `SABLON_V2_MIMARI/tools_runner.py` | 434 | Tk widget | VazgeÃ§ | EKSİK |
| 734 | `SABLON_V2_MIMARI/tools_runner.py` | 1326 | Tk widget |  | EKSİK |
| 735 | `SABLON_V2_MIMARI/tools_runner.py` | 1335 | Tk widget |  | EKSİK |
| 736 | `SABLON_V2_MIMARI/tools_runner.py` | 1342 | Tk widget |  | EKSİK |
| 737 | `SABLON_V2_MIMARI/tools_runner.py` | 1350 | Tk widget |  | EKSİK |
| 738 | `SABLON_V2_MIMARI/tools_runner.py` | 1769 | Tk widget |  | EKSİK |
| 739 | `SABLON_V2_MIMARI/tools_runner.py` | 1773 | Tk widget | KlasÃ¶r taranÄ±yor... | EKSİK |
| 740 | `SABLON_V2_MIMARI/tools_runner.py` | 1775 | Tk widget |  | EKSİK |
| 741 | `SABLON_V2_MIMARI/tools_runner.py` | 1777 | Tk widget |  | EKSİK |
| 742 | `SABLON_V2_MIMARI/templates/v6_review.html` | 30 | V6 kontrol |  | TEST BEKLİYOR |
| 743 | `SABLON_V2_MIMARI/templates/v6_review.html` | 31 | V6 kontrol |  | TEST BEKLİYOR |
| 744 | `SABLON_V2_MIMARI/templates/v6_review.html` | 32 | V6 kontrol |  | TEST BEKLİYOR |
| 745 | `SABLON_V2_MIMARI/templates/v6_review.html` | 33 | V6 kontrol |  | TEST BEKLİYOR |
| 746 | `SABLON_V2_MIMARI/templates/v6_review.html` | 34 | V6 kontrol |  | TEST BEKLİYOR |
| 747 | `SABLON_V2_MIMARI/templates/v6_review.html` | 35 | V6 kontrol |  | TEST BEKLİYOR |
| 748 | `SABLON_V2_MIMARI/templates/v6_review.html` | 40 | V6 kontrol | YardÄ±m | TEST BEKLİYOR |
| 749 | `SABLON_V2_MIMARI/templates/v6_review.html` | 41 | V6 kontrol | Ayarlar | TEST BEKLİYOR |
| 750 | `SABLON_V2_MIMARI/templates/v6_review.html` | 48 | V6 kontrol | prevBtn | TEST BEKLİYOR |
| 751 | `SABLON_V2_MIMARI/templates/v6_review.html` | 53 | V6 kontrol | nextBtn | TEST BEKLİYOR |
| 752 | `SABLON_V2_MIMARI/templates/v6_review.html` | 59 | V6 kontrol | zoomOut | TEST BEKLİYOR |
| 753 | `SABLON_V2_MIMARI/templates/v6_review.html` | 61 | V6 kontrol | zoomIn | TEST BEKLİYOR |
| 754 | `SABLON_V2_MIMARI/templates/v6_review.html` | 62 | V6 kontrol | zoomFit | TEST BEKLİYOR |
| 755 | `SABLON_V2_MIMARI/templates/v6_review.html` | 65 | V6 kontrol |  | TEST BEKLİYOR |
| 756 | `SABLON_V2_MIMARI/templates/v6_review.html` | 66 | V6 kontrol |  | TEST BEKLİYOR |
| 757 | `SABLON_V2_MIMARI/templates/v6_review.html` | 67 | V6 kontrol |  | TEST BEKLİYOR |
| 758 | `SABLON_V2_MIMARI/templates/v6_review.html` | 69 | V6 kontrol | autoBtn | TEST BEKLİYOR |
| 759 | `SABLON_V2_MIMARI/templates/v6_review.html` | 76 | V6 kontrol | railToggle | TEST BEKLİYOR |
| 760 | `SABLON_V2_MIMARI/templates/v6_review.html` | 80 | V6 kontrol | railSearch | TEST BEKLİYOR |
| 761 | `SABLON_V2_MIMARI/templates/v6_review.html` | 82 | V6 kontrol | categoryFilter | TEST BEKLİYOR |
| 762 | `SABLON_V2_MIMARI/templates/v6_review.html` | 89 | V6 kontrol | v6BulkModeButton | TEST BEKLİYOR |
| 763 | `SABLON_V2_MIMARI/templates/v6_review.html` | 93 | V6 kontrol | v6BulkSelectCategory | TEST BEKLİYOR |
| 764 | `SABLON_V2_MIMARI/templates/v6_review.html` | 94 | V6 kontrol | v6BulkClearSelection | TEST BEKLİYOR |
| 765 | `SABLON_V2_MIMARI/templates/v6_review.html` | 98 | V6 kontrol | v6BulkSelectPending | TEST BEKLİYOR |
| 766 | `SABLON_V2_MIMARI/templates/v6_review.html` | 99 | V6 kontrol | v6BulkSelectApproved | TEST BEKLİYOR |
| 767 | `SABLON_V2_MIMARI/templates/v6_review.html` | 101 | V6 kontrol | v6BulkDetectButton | TEST BEKLİYOR |
| 768 | `SABLON_V2_MIMARI/templates/v6_review.html` | 103 | V6 kontrol | v6BulkDetectStopButton | TEST BEKLİYOR |
| 769 | `SABLON_V2_MIMARI/templates/v6_review.html` | 104 | V6 kontrol | v6BulkApproveButton | TEST BEKLİYOR |
| 770 | `SABLON_V2_MIMARI/templates/v6_review.html` | 106 | V6 kontrol | v6BulkDeleteButton | TEST BEKLİYOR |
| 771 | `SABLON_V2_MIMARI/templates/v6_review.html` | 113 | V6 kontrol |  | TEST BEKLİYOR |
| 772 | `SABLON_V2_MIMARI/templates/v6_review.html` | 114 | V6 kontrol |  | TEST BEKLİYOR |
| 773 | `SABLON_V2_MIMARI/templates/v6_review.html` | 115 | V6 kontrol |  | TEST BEKLİYOR |
| 774 | `SABLON_V2_MIMARI/templates/v6_review.html` | 116 | V6 kontrol |  | TEST BEKLİYOR |
| 775 | `SABLON_V2_MIMARI/templates/v6_review.html` | 143 | V6 kontrol | btnCorner | TEST BEKLİYOR |
| 776 | `SABLON_V2_MIMARI/templates/v6_review.html` | 144 | V6 kontrol | autoCornerBtn | TEST BEKLİYOR |
| 777 | `SABLON_V2_MIMARI/templates/v6_review.html` | 145 | V6 kontrol | v6BatchAnalyzeButton | TEST BEKLİYOR |
| 778 | `SABLON_V2_MIMARI/templates/v6_review.html` | 146 | V6 kontrol | placeBtn | TEST BEKLİYOR |
| 779 | `SABLON_V2_MIMARI/templates/v6_review.html` | 147 | V6 kontrol | approveQuick | TEST BEKLİYOR |
| 780 | `SABLON_V2_MIMARI/templates/v6_review.html` | 157 | V6 kontrol | inspectorToggle | TEST BEKLİYOR |
| 781 | `SABLON_V2_MIMARI/templates/v6_review.html` | 164 | V6 kontrol | approveBtn | TEST BEKLİYOR |
| 782 | `SABLON_V2_MIMARI/templates/v6_review.html` | 194 | V6 kontrol | physicalOrientationSelect | TEST BEKLİYOR |
| 783 | `SABLON_V2_MIMARI/templates/v6_review.html` | 203 | V6 kontrol | glassCornerRadiusApproval | TEST BEKLİYOR |
| 784 | `SABLON_V2_MIMARI/templates/v6_review.html` | 220 | V6 kontrol |  | TEST BEKLİYOR |
| 785 | `SABLON_V2_MIMARI/templates/v6_review.html` | 221 | V6 kontrol |  | TEST BEKLİYOR |
| 786 | `SABLON_V2_MIMARI/templates/v6_review.html` | 222 | V6 kontrol |  | TEST BEKLİYOR |
| 787 | `SABLON_V2_MIMARI/templates/v6_review.html` | 225 | V6 kontrol | v6WhitePreviewBtn | TEST BEKLİYOR |
| 788 | `SABLON_V2_MIMARI/templates/v6_review.html` | 229 | V6 kontrol | restoreOriginalBtn | TEST BEKLİYOR |
| 789 | `SABLON_V2_MIMARI/templates/v6_review.html` | 230 | V6 kontrol | refreshWorkingBtn | TEST BEKLİYOR |
| 790 | `SABLON_V2_MIMARI/templates/v6_review.html` | 231 | V6 kontrol | v6RestoreWorkingBtn | TEST BEKLİYOR |
| 791 | `SABLON_V2_MIMARI/templates/v6_review.html` | 232 | V6 kontrol | v6ChooseReplacementBtn | TEST BEKLİYOR |
| 792 | `SABLON_V2_MIMARI/templates/v6_review.html` | 233 | V6 kontrol | replaceOriginalFileInput | TEST BEKLİYOR |
| 793 | `SABLON_V2_MIMARI/templates/v6_review.html` | 244 | V6 kontrol | templateHealthScanButton | TEST BEKLİYOR |
| 794 | `SABLON_V2_MIMARI/templates/v6_review.html` | 246 | V6 kontrol | lastTemplateHealthReportButton | TEST BEKLİYOR |
| 795 | `SABLON_V2_MIMARI/templates/v6_review.html` | 247 | V6 kontrol | templateHealthHistoryButton | TEST BEKLİYOR |
| 796 | `SABLON_V2_MIMARI/templates/v6_review.html` | 248 | V6 kontrol | workspaceConsistencyScanButton | TEST BEKLİYOR |
| 797 | `SABLON_V2_MIMARI/templates/v6_review.html` | 250 | V6 kontrol | lastWorkspaceConsistencyReportButton | TEST BEKLİYOR |
| 798 | `SABLON_V2_MIMARI/templates/v6_review.html` | 251 | V6 kontrol | workspaceConsistencyHistoryButton | TEST BEKLİYOR |
| 799 | `SABLON_V2_MIMARI/templates/v6_review.html` | 252 | V6 kontrol | v6BulkAlignmentButton | TEST BEKLİYOR |
| 800 | `SABLON_V2_MIMARI/templates/v6_review.html` | 258 | V6 kontrol | deleteTemplateBtn | TEST BEKLİYOR |
| 801 | `SABLON_V2_MIMARI/templates/v6_review.html` | 259 | V6 kontrol | restoreDeletedBtn | TEST BEKLİYOR |
| 802 | `SABLON_V2_MIMARI/templates/v6_review.html` | 264 | V6 kontrol |  | TEST BEKLİYOR |
| 803 | `SABLON_V2_MIMARI/templates/v6_review.html` | 265 | V6 kontrol |  | TEST BEKLİYOR |
| 804 | `SABLON_V2_MIMARI/templates/v6_review.html` | 269 | V6 kontrol | v6ReconciliationBtn | TEST BEKLİYOR |
| 805 | `SABLON_V2_MIMARI/templates/v6_review.html` | 270 | V6 kontrol | v6ResolveDuplicatesBtn | TEST BEKLİYOR |
| 806 | `SABLON_V2_MIMARI/templates/v6_review.html` | 271 | V6 kontrol | v6RecoveryCenterBtn | TEST BEKLİYOR |
| 807 | `SABLON_V2_MIMARI/templates/v6_review.html` | 272 | V6 kontrol | v6UndoLifecycleBtn | TEST BEKLİYOR |
| 808 | `SABLON_V2_MIMARI/templates/v6_review.html` | 273 | V6 kontrol | v6CanvasBgBtn | TEST BEKLİYOR |
| 809 | `SABLON_V2_MIMARI/templates/v6_review.html` | 274 | V6 kontrol | v6OverlayToggleBtn | TEST BEKLİYOR |
| 810 | `SABLON_V2_MIMARI/templates/v6_review.html` | 282 | V6 kontrol | dockApproveBtn | TEST BEKLİYOR |
| 811 | `SABLON_V2_MIMARI/templates/v6_review.html` | 283 | V6 kontrol | dockPauseBtn | TEST BEKLİYOR |
| 812 | `SABLON_V2_MIMARI/templates/v6_review.html` | 284 | V6 kontrol | dockHealthBtn | TEST BEKLİYOR |
| 813 | `SABLON_V2_MIMARI/templates/v6_review.html` | 285 | V6 kontrol | dockSaveBtn | TEST BEKLİYOR |
| 814 | `SABLON_V2_MIMARI/templates/v6_review.html` | 300 | V6 kontrol | placementClose | TEST BEKLİYOR |
| 815 | `SABLON_V2_MIMARI/templates/v6_review.html` | 303 | V6 kontrol | placementFile | TEST BEKLİYOR |
| 816 | `SABLON_V2_MIMARI/templates/v6_review.html` | 304 | V6 kontrol | placementMode | TEST BEKLİYOR |

---
*Bu belge `tmp_gen_inventory.py` tarafından üretildi; kaynak koddaki her satır tek tek sayılır. Durumlar otomatik ön-sınıflandırmadır; Windows kabulüyle insan onayı gerektirir.*