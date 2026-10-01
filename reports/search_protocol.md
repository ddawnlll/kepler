# Arama protokolü (G2 sonrası; sonuçlara bakmadan sabitlendi)

Amaç: G2'de kitap sinyalleri NO_EDGE verdi. Aynı altyapıyla ailelerden oluşan geniş bir ızgarayı **dürüst sayımla** ara; "pozitif sonuç" yalnızca doğrulama döneminde ve çoklu-test düzeltmesinden sonra sayılır.

**Dönemler (dev içi, mühür DEĞİL):** arama dönemi 2022-01-01 → 2025-01-01 (ilk 12 ay bazı sinyallerde ısınma); doğrulama dönemi 2025-01-01 → 2026-04-01. Aile başına yalnızca arama-dönemi sonucuyla **tek** yapılandırma seçilir, doğrulamada bir kez koşulur. Mühürlü dönem (≥2026-04-01) açılmaz, G3 yok.

**Aileler (hepsi günlük karar, birim ±1 notional, evren = genişletilmiş-9, sembol başına bağımsız koşu; portföy = toplam):**
| aile | ızgara (sabit) |
|---|---|
| `donchian` | giriş {10,20,30,40,55,80,100,120} × çıkış {5,10,20,30,40}, çıkış < giriş (30) |
| `ema` | hızlı {5,10,20,30,50} × yavaş {50,100,150,200,350}, hızlı < yavaş; işaret(EMA_h − EMA_y) (24) |
| `tsmom` | formasyon {7,14,30,60,90,180,365} gün × yeniden dengeleme {1,7,30} gün (21) |
| `xs_mom` | kesitsel momentum, dolar-nötr (üst üçte bir long, alt üçte bir short): formasyon {7,14,30,60,90,180} gün, haftalık dengeleme (6) |
| `xs_carry` | kesitsel funding carry, dolar-nötr (en düşük funding long, en yüksek short): ortalama {7,14,30} gün, haftalık dengeleme (3) |
| `xs_rev` | kesitsel kısa vadeli ters yönlü, dolar-nötr: formasyon {1,2,3,5} gün, günlük dengeleme (4) |
Toplam N = 88 yapılandırma; hepsi deftere yazılır (hakem satırı: arama dönemi; seçilenler: + doğrulama), eleme (vectorbt) satırları da deneme sayacına girer.

**Maliyet:** fee 10 bps gidiş-dönüş + slippage 2 bps (arama); doğrulamada fee 4/9/10/11/16 + slippage 6.
**Seçim kuralı:** aile başına arama dönemi net PnL (fee 10) en yüksek yapılandırma.
**Doğrulama kriteri (ADAY):** (i) doğrulama brüt PnL'si ortak-ofset rotasyon null'ında (B=300) tek yönlü p ≤ 0,05/6 (aile sayısına Bonferroni) **ve** (ii) doğrulama neti fee 10'da > 0 **ve** (iii) fee 16'da da > 0. DSR (N=88 deneme) ayrıca raporlanır. Kriter sonuçlara göre değiştirilmez.
**Eleme–hakem uyumu:** aynı ızgara eleme ve hakemle koşulur; Spearman raporlanır (G1'in n=16 ölçümü zayıftı).
