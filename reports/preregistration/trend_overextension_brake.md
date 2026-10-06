# Ön kayıt TASLAĞI 1/4: "Trend + aşırı uzama freni" (K8'e takılan uzmanların tek hipotezle değiştirilmesi)

**Durum: TASLAK, KOŞULMADI.** Kullanıcı onayı ve ayrı commit olmadan hiçbir kod yazılmaz/koşulmaz (MISSION kural 11). Onaylanınca bu dosya değişmez; değişiklik = yeni ön kayıt + yeni deneme. Bu taslak `reports/audit_fixes.md` / `reports/trade_audit_data/fix/analysis/analysis.json` bulgularından doğdu (yeni fikir, görevin kapsamı dışı: yalnızca taslak).

## Neden (gözlenmiş engel; MISSION kural 4)
Leave-one-out (`analysis.json → loo`, rapor Bölüm I.5 → 2.7): ev1_plus_new'de **carry, bollinger ve fundcrowd** çıkarılınca net ARTIYOR (+79,8 / +71,3 / +66,9 USDT); yalnızca **fundcrowd** çıkarılınca Sharpe da artıyor (+0,05). BACKTEST K8 ("bileşen çıkarılınca OOS Sharpe düşmeli, düşmüyorsa bileşen atılır") fundcrowd'u kesin, carry ve bollinger'ı net ölçütüyle işaretler. Üçü de tek başına NO_EDGE (`reports/edge_experts.md`). Doğrusal atıfta (2.1) bollinger −199 USDT, carry −69, fundcrowd −50 katkı veriyor. Trend ise net'in neredeyse tamamını taşıyor ve sonuçların ana riski trend dönüşleri (kâr geri verme: kaybeden trade'lerin %26'sı ≥ 2σ lehe gitmişti).
**Hipotez (tek):** "Aşırı uzamış trend sinyalinde (fiyat kısa EMA'dan oynaklık-ölçekli büyük sapmada) tahmini yarıya indiren bir fren, trend uzmanının Sharpe'ını artırır ve K8'e takılan üç uzmanın yerini, onların negatif katkısı olmadan tutar."

## Kural (tüm parametreler sabit; ayarlanmaz)
- Yeni uzman `trend_brake` (`experts/trend_brake.py`): E1 `trend` ile aynı F (L ∈ {7, 14, 28, 56}); uzama ölçüsü s = |ln(C_d / EMA_28(C)_d)| / (σ_günlük,d · √28), σ_günlük = `st["sigma"]`/√365. **s > 1,5 ve işaret(ln(C/EMA_28)) = işaret(F) ise F ← 0,5 · F**, değilse F aynı. Başka eşik/çarpan denenmez (1,5 ve 0,5 literatürde yaygın yuvarlak değerler; bu veride seçilmedi).
- Bileşim B (tek test edilen): `trend_brake` 0,6; `xs_momentum` 0,2; `lowvol` 0,1; `nearhigh` 0,1; `volrev` 0,1; `orderflow` 0,1. Çıkarılanlar: carry, bollinger, fundcrowd (K8'e takılanlar). Kontrol C: aynı bileşim, `trend` (frensiz) 0,6 (deftere girmez).
- Risk motoru, hakem, Spec, evren (ext-9), dönem, maliyet (fee 10 + slip 2), sermaye (1 000 ve 10 000) ve K-kartı `reports/ensemble_protocol.md` ile birebir.

## Başarı ve red ölçütü (koşudan ÖNCE)
- **BAŞARI**: B için K1 (brüt p ≤ 0,05/N; DSR ≥ 0,95; N bu denemeyle +1) ve K2–K9 geçer **ve** fren etkisi: sabit-sermaye Sharpe(B) − Sharpe(C) ≥ +0,15 **ve** 6 takvim yılından en az 4'ünde Sharpe(B) ≥ Sharpe(C) **ve** 2025+ Sharpe(B) > 0.
- **RED**: Sharpe(B) − Sharpe(C) < +0,05 ya da yıl sayısı < 3. Arası = "KANITSIZ" (ek kategori yok).
- Başarı bile ADAY'a götürmez: görülmüş veride ön kayıtlı testtir (BACKTEST §8.5); G3 yalnızca ADAY + kullanıcı komutuyla.

## Tahmin (koşudan önce; yargı)
Frenin Sharpe'ı +0,05…+0,15 arttırması beklenir; ama frenin kısmen sönmüş trend sonrası (2025+) etkisinin belirsiz olması ve LOO'nun ölçekleme etkileşimi nedeniyle RED ya da KANITSIZ en olası sonuç. Üç uzmanı çıkarmanın tek başına etkisi Kontrol C'nin yanında görülür.

## Denemeler
N + 1 (B, `evaluate_book` ile deftere; kümülatif sayı koşudan sonra defterden okunur). Kontrol C, K5/K8 komşuları ve null çekilişleri deftere girmez.

## Sınırlar
Evren hayatta kalma yanlılığı taşır (rapor 2.9: dinamik evrende Sharpe 1,86 → 0,82/1,04): B ayrıca aylık top-20 evrende (bilgi) koşulur, karar dışı. Frenin parametreleri ve çıkarılacak üç uzman bu denetimin (görülmüş) LOO sonucundan geldi: seçim yanlılığı var; bu yüzden zaman-dışı kanıt yalnızca ileri veri/mühürdür.
