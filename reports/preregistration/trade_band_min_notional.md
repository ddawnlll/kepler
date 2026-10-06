# Ön kayıt TASLAĞI 3/4: İşlem bandı / asgari hedef notional

**Durum: TASLAK, KOŞULMADI. KOŞULLU:** görev "yalnızca 2.2'deki bps sonucu destekliyorsa" dedi. 2.2 sonucu (rapor Bölüm I.5 → 2.2, `analysis.json → size_vol_f`): en küçük boyut üçlüğünün notional-ağırlıklı getirisi 1,8 bps/gün (%95 AA −9,7 … 13,4), en küçük |F| üçlüğü −6,2 bps/gün (−18,4 … 5,8); ikisi de sıfırdan ayrışmıyor ve bu üçlüklerin net'i −23 / +5 USDT (toplamın %3'ü). **Destek zayıf: ekonomik değil operasyonel.** Taslak bu nedenle ekonomik hipotez olarak değil, uygulanabilirlik hipotezi olarak yazıldı; kullanıcı gerekçeyi yetersiz bulursa silinir. Onay ve commit olmadan koşulmaz.

## Neden (gözlenmiş engel)
MEXC kuralıyla (min 1 sözleşme, `reports/trade_audit_data/fix/mexc_rules.json`) $1 000'da emir niyetlerinin %17'si gönderilemiyor (ETH %59, DOGE %47, SOL %35) ve ön kayıtlı yakınsama ölçütünü geçen asgari sermaye $2 500 (rapor I.3). Hedef notional'ı 1 sözleşmenin altında kalan pozisyonlar zaten açılamıyor; bunları açıkça kapatmak (bant) takibi sadeleştirebilir.
**Hipotez (tek):** "Hedef notional'ı max(1 sözleşme MEXC değeri, sabit alt sınır) altında kalan pozisyonları 0'a yuvarlayan açık bir işlem bandı, $1 000'da MEXC-kuralı koşusunun yuvarlamasız hedefe takip hatasını azaltır ve net Sharpe'ı en fazla 0,10 düşürür."

## Kural (sabit)
- Karar anı hedef notional |n_i| < B_i ise n_i ← 0; B_i = 2 · (sembolün 1 sözleşme USDT değeri, karar anı fiyatı) (iki kat güvenlik payı; başka katsayı denenmez). Bant yalnızca açılış/artırmayı engeller, azaltma serbest (referee kuralıyla aynı).
- Sermaye 1 000; Spec ve MEXC kuralları `scripts/audit_fix.py::contract_view` ile; yuvarlamasız referans = bantsız yuvarlamasız koşu.

## Ölçüt (koşudan ÖNCE)
- **BAŞARI**: (a) gönderilemeyen emir niyeti payı ≤ %5 **ve** (b) günlük PnL takip hatası RMSE'si (yuvarlamasız koşuya göre) bantsız MEXC koşusundakinin ≤ %70'i **ve** (c) Sharpe(bantlı) ≥ Sharpe(bantsız MEXC) − 0,10.
- **RED**: (a) veya (b) sağlanmaz ya da (c) bozulur.

## Tahmin
$1 000'da yakınsama yine zor (hedefler sistematik olarak küçük); bant gönderilemeyenleri "açık sıfır"a çevirir ama ETH/DOGE/SOL'u fiilen portföyden çıkarır. En olası sonuç: (a) sağlanır, (b) kısmen, (c) tolerans içinde. Asıl çözüm daha büyük sermayedir (≥ $2 500).

## Denemeler
N + 1 (bantlı koşu, `evaluate_book`/ledger); referans koşular deftere girmez.
