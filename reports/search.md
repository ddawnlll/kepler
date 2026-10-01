G2 sonrası geniş arama (88 yapılandırma, 6 aile, 9 sembol): **doğrulama döneminde ADAY yok**; pozitif "backtest" yalnızca arama döneminde (seçim yanlılıklı) ve piyasa yönünden ayrışmıyor. Mühür açılmadı, G3 yok. Protokol veriye bakmadan sabitlendi: `reports/search_protocol.md`.

## Ne yapıldı
- 88 yapılandırma (Donchian 30, EMA 24, tsmom 21, kesitsel momentum 6 / funding carry 3 / ters yönlü 4; kesitsel olanlar dolar-nötr), arama dönemi 2022-01→2025-01 (hakem + vectorbt eleme, fee 10 + slip 2 bps), aile başına arama-neti en yüksek yapılandırma doğrulama dönemi 2025-01→2026-04'te **bir kez** (fee 4/9/10/11/16 + slip 6; B=300 ortak-ofset rotasyon null'ı). Dev içi bölme: mühür dokunulmadı.
- Defter: `ledger/search/` (1908 satır: 792 hakem + 792 eleme + 324 doğrulama) + `ledger/g2/` (767) = 2675 satır; bağımsız yapılandırma ≈ 100 (G2'nin 12'si + 88; birkaçı örtüşür).
- **Eleme–hakem uyumu (G2'nin ilk adımı):** Spearman **0,871** (n=88, p≈3e-28), aile içi: donchian 0,94, ema 0,89, tsmom 0,97, xs_mom 0,71, xs_rev 0,60 (öneri eşiği ≥0,8, doğrulanmadı; genel eşiği geçiyor, kesitsel ailelerde geçmiyor; G1'in n=16 ölçümünden güçlü kanıt).

## Sonuçlar (tam tablo: `reports/search_data/tables.md`)
- Arama döneminde 80/88 yapılandırma net > 0 (ortalama +5,4k USDT / 9 sembol × 1000 notional × 3 yıl): trend/momentum aileleri 2022 ayı + 2023–24 boğa dalgasında kazandı; ters yönlü (xs_rev) net negatif (−8k…−9k: devir çok yüksek, brüt −25 bps/RT). Aile-içi en iyi yıllık Sharpe 0,5–1,8; seçim yanlılığından arındırılmış DSR (N=88) ≤0,77 (xs_mom 7 gün), diğerleri ≤0,5.
- **Doğrulama (tek atış):** donchian don_80_20 net +1166 (fee 10; brüt p=0,32), ema_10_100 +1722 (p=0,40), tsmom_14_1 +78 (fee 16'da −238; p=0,38), xs_carry −128, xs_mom −649, xs_rev −191. **Hiçbiri** p ≤ 0,05/6 değil (en düşük p=0,146); Bonferroni p ≥ 0,88; DSR(N=88) ≤ 0,11. Protokol kriteri (p≤0,0083 ve fee 10 + fee 16'da net>0): **ADAY yok**.
- Yorum: pozitif doğrulama netleri (donchian/ema) piyasa yönünün (2025'te) null'ın rotasyon dağılımından ayırt edilememesi anlamına geliyor; kesitsel dolar-nötr aileler (beta'dan arınmış) doğrulamada negatif. Yani arama-döneminin "pozitif backtest"i büyük ölçüde yön (beta) + seçimdir.

## Dürüstlük notu
Bu noktadan sonra aynı veriyle yeni aile denemek doğrulama dönemini yeniden kullanmak olur (her yeni deneme deneme sayısını ve yanlılığı artırır); "pozitif sonuç çıkana kadar ara" mekanik olarak yanlış pozitif üretir. Bu yüzden arama burada durduruldu; pozitif bir sonuç **üretilmedi**. Yeni veri (G3 dışında) ya da bağımsız, önceden sabitlenmiş yeni bir hipotez olmadan devam anlamsız.

## Sınırlar
Evren/dönem/slippage/funding-settlement/sembol kuralları için G2 raporundaki UNKNOWN'lar geçerli. Doğrulama 15 ay: gücü düşük (küçük etkileri ayırt edemez). DSR günlük PnL üzerinden. Risk motoru (`kepler/risk.py`) gerçek veride duman testinden geçti (vol hedefleme + kill switch çalışıyor; SOL turtle'da kill switch 2023-09'da tetiklendi ve toparlanmayı kaçırdı), ama aday olmadığından "sabit boyut"la bilimsel karşılaştırma yapılmadı (ARCHITECTURE: G3 sonrası).
