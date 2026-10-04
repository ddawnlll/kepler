---
name: new-expert
description: Ensemble'a yeni bir sürekli tahmin uzmanı (ör. Bollinger z-skor, hacim z-skoru) ekleme iş akışı. Yeni uzman fikri geldiğinde kullan.
---
Sıra değişmez; her adımın kanıtı çıktıda gösterilir.
1. **Gözlenmiş engel:** AGENTS.md "yeni bileşen için gözlenmiş engel gerekir". Hangi mevcut sonuç/teşhis bu uzmanı gerektiriyor? Yazamıyorsan dur, kullanıcıya sor.
2. **Ön kayıt:** `reports/<ad>_protocol.md` (hipotez, sabit parametreler, evren, dönem, ölçüt/K eşikleri, N). Koşudan önce commit. Şablon olarak `reports/ensemble_protocol.md` biçimini izle; yeni belge türü açma.
3. **Girdi:** gereken seri `market_state.py`/`state.py`/`indicators.py`'de var mı? Varsa kullan, yoksa oraya ekle (korumalı dosyaysa kullanıcıya sor).
4. **Uzman:** `kepler/experts/<ad>.py` içinde `forecast(close, st, p)`; [-1, 1], aktif değilse NaN. Boyut/kaldıraç yazma. `LAYERS` zaten `experts` grubunu kapsar.
5. **Test:** `tests/test_<ad>.py` elle hesaplı beklenen değerlerle + gelecek-bozma. `python3 tests/test_architecture.py` ve ilgili testler yeşil olmadan ilerleme.
6. **Kompozisyon:** ensemble'a ekleme ayrı ön kayıtlı karardır (ağırlık). Önce uzmanı tek başına hakemden geçir (`evaluate`), sonucu `reports/<ad>.md`'ye yaz.
7. **Kapanış:** TASKS.md `Aktif iş:` satırı, BACKTEST.md değişiklik günlüğü, N sayacı. ARCHITECTURE.md değişmişse aynı commit'te.
