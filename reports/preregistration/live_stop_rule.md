# Ön kayıt TASLAĞI 4/4: Canlı durdurma kuralı (kayan Sharpe eşiği ve penceresi)

**Durum: TASLAK, KOŞULMADI.** Kullanıcı onayı + commit olmadan kural kodlanmaz. Bu bir strateji parametresi araması değildir: pencere ve eşik formülle (güç/yanlış-durdurma dengesi) önceden belirlenir, tarihsel tetik sayıları yalnızca betimseldir.

## Neden
Rapor (özet, sönme): sabit sermaye Sharpe'ı 2020–21'de 3,4 → 2022–24'te 1,6 → 2025+ 0,1; 2025+ için bootstrap %95 AA sıfırı içeriyor. Canlıda (H5) sistemin bozulduğunu *önceden* tanımlı bir kuralla yakalamak gerekir; ad hoc el müdahalesi seçim yanlılığı üretir. `risk.kill_switch` drawdown tabanlıdır; bir Sharpe tabanlı kural ayrı bir hipotezdir.
**Hipotez (tek):** "Kayan 365 günlük net Sharpe (sabit sermaye) ≤ −0,64 olursa durdur (pozisyonları kapat, yeniden başlatma insan onayı), gerçek Sharpe 1,0 iken yılda en çok %5 yanlış durdurma verir ve gerçek Sharpe ≤ −1 iken yakalama gücü ≥ %60'tır."

## Kural (formülle önceden)
- Eşik = SR_H1 − z(1−α) · √(365/pencere), SR_H1 = 1,0 (tüm dönem bootstrap %95 AA alt sınırına yakın; rapor 1,0'ın altını dışlamıyor), α = 0,05, iid-normal yaklaşımı. Pencere 365 gün (1 yıl): trend sisteminin tam döngüsü + SD(SR) ≈ 1,0.
- Aynı formülle diğer pencereler (`analysis.json → live_stop`, script `scripts/audit_fix_analysis.py::live_stop_power`): 180 gün için eşik −1,34 ve H0 gücü %17, 365 gün için −0,64 / %26 (gerçek Sharpe 0'da), 540 gün için −0,35 / %33. **Pencere güç/gecikme dengesiyle seçildi, tarihsel tetik sayısıyla değil**; 3 pencereye de bakıldı (kayıt: bu satır).
- Güç düşüktür: gerçek Sharpe 0 iken bir yıllık pencerede durdurma olasılığı ≈ %26 (güç_h0). Kural "bozulmayı erken yakalar" iddiası taşımaz; yalnızca ağır bozulmayı (Sharpe ≈ −1) geç ama kuralla yakalar. Alternatif/tamamlayıcı olarak mevcut drawdown kill switch'i (%30) kalır.

## Başarı ve red ölçütü (koşudan ÖNCE; ileri veri/canlı H5 için)
- Değerlendirme yalnızca ileri veride (dondurma tarihinden sonra); görülmüş veride sonuç "betimsel" etiketlidir (tarihsel tetik sayısı: 365 günlük pencerede 2 gün, ilk 2022-09-15; seçimde kullanılmadı).
- **BAŞARI**: ileri 24 ayda (a) yanlış durdurma yok iken (ardından ≥ 12 ay boyunca gerçek 365 günlük Sharpe > 0) tetik sayısı 0 **ya da** (b) tetik sonrası ilk 180 günde sistem net < 0 (durdurma doğru çıkar).
- **RED**: tetik sonrası ilk 180 günde sistem net > +%2 sermaye (yanlış durdurma) ve bu iki kez tekrarlanır; ya da kural hiç tetiklenmeden 12 ay üst üste kayan Sharpe < −0,64 (kural uygulanmadı/hatalı).
- Aralık = KANITSIZ.

## Denemeler
N + 1 (kural kodlandığında `evaluate`/ledger'a bir satır; canlı gözlem deftere girmez). Kuralın kendisi hakemde simüle edilecekse `risk.kill_switch` benzeri çıktıyla yapılır; `risk.py`'ye dokunmak bağımsız inceleme gerektirir (korumalı çekirdek).

## Sınırlar
iid-normal yaklaşımı otokorelasyonu ve kalın kuyrukları yok sayar (çarpıklık 0,67, fazla basıklık 13: gerçek SD daha büyük, yanlış durdurma oranı yaklaşıktır). Eşik SR_H1 varsayımına duyarlı.
