# Kepler: ajan kuralları (Claude Code, Codex, Hermes ve diğerleri)

Oturum başında: `TASKS.md` devralma notunu oku. Fabrika çalışıyorsa `state/STATUS.md` ve açık kuyruğu oku;
büyük bir adımdan önce yeniden oku.

## Nasıl çalıştırılır (tek doğru kaynak; başka yerde tekrarlama)
- Proje kodu Modal'de koşar (`modal_app.py`). Kalıcı veri: Modal Volume `kepler-data` → konteynerde `/data`
  (Parquet tape, `universe.parquet`); ham veri git'te yok.
- Testler: `modal run modal_app.py --cmd "pytest -q"`. Tek dosya: `--cmd "pytest -q tests/test_referee.py"`.
  Gerçek ağ testi: `--cmd "KEPLER_NET=1 pytest -q tests/test_data.py"`.
- Gerçek veriyle betikler: `--cmd "python scripts/g1_real.py corr"` ve `xcheck`; veri/QC:
  `--cmd "python -m kepler.qc --root /data --out /data/manifest"`.
- Modal erişimi: `pip install modal`, sonra `MODAL_TOKEN_ID` ve `MODAL_TOKEN_SECRET` ortam değişkenleri
  (veya `modal token set`). Token repoya, dosyaya, commit'e ve sohbete yazılmaz.
- Python 3.12 + `uv` (`uv.lock` kilitli). Yalnızca stdlib'e dayanan testler (ör. `tests/test_enqueue.py`)
  Modal'siz de koşar; Nautilus/vectorbt testleri Modal'de doğrulanmıştır.
- Kod değiştirince ilgili testleri koş; sonucu rapora yaz (yeşil/kırmızı/atlandı).

## Kurallar
- Backtest, sinyal, risk, hakem, değerlendirme ya da rapor işinden önce `BACKTEST.md`'yi oku (tasarım, sözleşmeler, başarı kartı, test senaryoları).
- Soru ve kurallar `MISSION.md`'de, sistem haritası `ARCHITECTURE.md`'de. Çelişkide onlar kazanır.
- Sonuç deftere yalnızca hakemden girer (`kepler/ledger.py`). Eleme sonucu sayılmaz.
- Hakem, denetim, risk ve mühür koduna yalnızca kullanıcı + güçlü model + bağımsız inceleme dokunur.
- Mühürlü dönem (son 6 ay) açılmaz, anahtar hiçbir yere girmez, `tools/seal_holdout.py` gerçek veriyle çalıştırılmaz.
- Yeni bileşen için gözlenmiş engel gerekir. Yeni spec/anayasa belgesi yazılmaz (tek istisna `BACKTEST.md`; tasarım değişikliği oraya yazılır).
- Kendi kodumuz küçük kalır (MISSION kural 7 iki sayıyı da raporlar). Testleri elle koş; CI yok.
- Doğrulanmamış rakam "doğrulanmadı" diye yazılır. Kuyruğa yazmak için `factory/enqueue.py`.
