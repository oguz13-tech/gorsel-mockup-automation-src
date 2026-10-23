# V4.2.2 — GitHub geçmişi, açık PR dal zinciri ve neden otomatik merge yok

**2026-10-23 doğrulama:** Aşağıdaki PR'lar GitHub üzerinden tek tek okundu; tamamı **open / draft / unmerged** olarak dönüyordu. Değişen dosya sayıları o andaki PR metadata'sıdır, final V4.2.2 ZIP ile eşit değildir. Bu tabloda verilenden başka bir PR merge edildi varsayılmamalıdır.

| PR | Konu | Head | Base | PR değişen dosya |
|---|---|---|---|---:|
| [#4](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/4) | EPIC-3 geometry + autonomous factory hardening | `feature/epic-3-geometry-accuracy` | `main` | 77 |
| [#9](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/9) | P0 DB read-only gate / preview / stage UI | `fix/p0-final-release-closure-20261017` | `audit/full-system-release-gate-20261017` | 26 |
| [#11](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/11) | PETEK fixed 13 procedural slots — DO NOT USE | `feature/petek-dolabi-procedural-slots-20261020` | `fix/p0-final-release-closure-20261017` | 6 |
| [#12](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/12) | NumberGuard V2 / proportional fill | `delivery/core-numbering-fill-20261020` | `fix/p0-final-release-closure-20261017` | 10 |
| [#13](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/13) | PETEK V3 masks and Windows candidate | `feature/petek-v3-source-preserving-factory-20261021` | `delivery/core-numbering-fill-20261020` | 22 |
| [#14](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/14) | Local PETEK preserve/checkpoint | `checkpoint/astra-petek-v3-local-20261021` | `delivery/core-numbering-fill-20261020` | 48 |
| [#26](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/26) | Windows package tests | `fix/final-15-package-tests-20261021` | `feature/petek-v3-source-preserving-factory-20261021` | 6 |
| [#27](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/27) | geometry-bound identity and receipt | `fix/final-18-no-loss-identity` | `fix/final-15-package-tests-20261021` | 7 |
| [#28](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/28) | PETEK brush solid coverage and quad clip | `fix/petek-solid-brush-coverage` | `fix/final-18-no-loss-identity` | 46 |
| [#37](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/37) | V4.0 docs-only planning handoff | `docs/v4-final-release-plan-20261022` | `fix/petek-solid-brush-coverage` | 2 |
| [#38](https://github.com/oguz13-tech/gorsel-mockup-automation-src/pull/38) | V4.2.2 source + full manifest + handoff | `handoff/v422-complete-20261023` | `main` | 281 |

## Yanlış sürümden devamı önleyen kurallar

1. `main` geçmişi 2026-10-23 başında 101 dosya gösteriyordu ve `MERKEZ/URETIM_V4` yoktu. **Güncel kaynak `handoff/v422-complete-20261023` dalıdır**, ancak kanonik Windows ZIP'in tüm 379 dosyasını public kaynakta arama; tam özel ZIP Library'de.
2. PR #37 V4.0 görev ve kabul dokümanlarını içerir; kaynak kodu final birleştirme PR'ı değildir. #38 daha yeni V4.2.2 kaynak aktarımıdır.
3. PR #11'ın sabit 13 PETEK delik algoritmasını bu projede asla üretime alma; gerçek fotoğraftaki delik sayısı değişir, onaylı maske/kavis korunur.
4. PR #4 EPIC-3, PR #9/#12/#13/#14 ve #26/#27/#28 geçmişi referans ve test regresyon kapsamıdır. **Bütün bu PR'ları sıra gözetmeden merge etmek yasak**; farklı base/head zincirleri vardır ve kod çatışması/gerileme yaratabilir. İhtiyaç varsa sadece belirli test/özellik ve commit diff doğrulanarak aktar.
5. GitHub #29–#35 ana iş kapsamı ve #36 orkestra; #15–#24 tarihî kabul talepleri kapanmış sayılmaz. Gerçek Windows kabulü olmadan issue kapama/PR merge/production GO yok.
6. Kota devri: `AGENTS.md` → `docs/WORK_HANDOFF_CURRENT.md` → `docs/NEXT_AGENT_TASK.md` → `docs/V422_GITHUB_RECONCILIATION.md` → `docs/RELEASE_ACCEPTANCE_MATRIX.md`. Kullanıcının Library ZIP'ini SHA ile doğrula.

## Dosya kimliği

**379 üye ZIP**: SHA256 `ad33e3219c5e2c6e1f6185a2b726730276eb9e2386abd6a78d49b97df566f7ee`. Güncel GitHub karşılaştırması: **330 exact match, 3 present-different, 46 not-published**. 46 dosyanın tamamı özel Library ZIP/CSV envanterinde bulunur. Bir agent bu farkı eksik geliştirmenin kanıtı olarak yorumlamamalı; eksik olanları geliştirmenin, çalıştırmanın ve yayınlamanın uygun olup olmadığını ayrı değerlendirmeli.
