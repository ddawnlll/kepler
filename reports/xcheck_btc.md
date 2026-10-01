# Gerçek veri çapraz kontrolü (BTCUSDT, mom24 fixture, 1000 USDT notional)

Hakem işlem (pozisyon) sayısı 3773, bağımsız hesap 3773, eşleşen 3773; eşleşmeyen 0.
**İşlem başına |net fark|: maks 0.002070 USDT, ort 0.000025** (net = brüt − fee; funding hariç).
|fark|>1e-6 olan 120 işlemin 119'i çevirme dolumunda açılmış; tüm işlemlerde işaretli toplam fark -0.015408 USDT.
Funding toplamı: hakem -37.707683, bağımsız -37.707683, fark 0.00e+00 USDT; eksik funding olayı hakem 0, bağımsız 0.
Hakem toplam net -4069.6842; fills 3773, likidasyon 0, reddedilen emir 0.

Açıklama (varsayım, doğrulanmadı): fark neredeyse yalnızca çevirme (flip) dolumlarında; çevirmede komisyon iki pozisyona bölünür. Bağımsız hesap miktarla orantılı böler; Nautilus'un bölüşümü bundan ≤0,002 USDT/işlem sapıyor (muhtemelen farklı yuvarlama/ağırlık). Toplam komisyon iki tarafta aynı; fark yalnızca iki komşu pozisyon arasındaki paylaşımda.
Sermaye bu karşılaştırma için 1.000.000 USDT (500 USD'lik hesap bu yüksek devirli fixture ile iflas eder: ilk denemede INITIAL_MARGIN_EXCEEDS_FREE_BALANCE ile binlerce emir reddedildi). Sermaye PnL'yi değiştirmez.