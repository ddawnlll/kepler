---
paths:
  - kepler/experts/**
  - kepler/ensemble.py
  - kepler/market_state.py
  - kepler/portfolio.py
---
# Uzman / ensemble kuralları (kısa; ayrıntı ARCHITECTURE.md "Katmanlar")
- Uzman = `forecast(close, st, p) -> DataFrame` ([gün x sembol], [-1, 1], aktif olmayan NaN). Boyut, kaldıraç, tavan, defter yazımı uzmanda olmaz (test zorlar).
- Oynaklık, korelasyon, funding, ATR gibi girdiyi uzmanda yeniden hesaplama: `market_state.py`/`state.py`'de var mı bak, yoksa oraya ekle.
- Nedensellik: gün `d` kararı yalnızca `d` dahil veriyi görür. Şüphede gelecek-bozma testi yaz (`tests/test_ensemble.py`, `audit.check_causal_book`).
- Parametre/ağırlık/eşik koşudan ÖNCE `reports/<ad>_protocol.md`'de sabitlenir; sonuca bakıp ayarlanmaz. Değişiklik = yeni ön kayıt + yeni deneme (N).
- Test: beklenen değer elle hesaplanır (formül + sayı); çıktıyı kendisiyle karşılaştırma. Refactor'da eski/yeni çıktı birebir eşit olmalı.
- Ensemble ana sistemdir: uzman eklemek/ağırlık değiştirmek `ensemble_protocol.md`'yi değil yeni bir protokolü gerektirir.
