# Kepler: ajan kuralları (Claude Code, Codex, Hermes ve diğerleri)

Oturum başında: `TASKS.md` devralma notunu oku. Fabrika çalışıyorsa `state/STATUS.md` ve açık kuyruğu oku;
büyük bir adımdan önce yeniden oku.

- Soru ve kurallar `MISSION.md`'de, sistem haritası `ARCHITECTURE.md`'de. Çelişkide onlar kazanır.
- Sonuç deftere yalnızca hakemden girer (`kepler/ledger.py`). Eleme sonucu sayılmaz.
- Hakem, denetim, risk ve mühür koduna yalnızca kullanıcı + güçlü model + bağımsız inceleme dokunur.
- Mühürlü dönem (son 6 ay) açılmaz, anahtar hiçbir yere girmez, `tools/seal_holdout.py` gerçek veriyle çalıştırılmaz.
- Yeni bileşen için gözlenmiş engel gerekir. Yeni spec/anayasa belgesi yazılmaz.
- Kendi kodumuz küçük kalır (MISSION kural 7 iki sayıyı da raporlar). Testleri elle koş; CI yok.
- Doğrulanmamış rakam "doğrulanmadı" diye yazılır. Kuyruğa yazmak için `factory/enqueue.py`.
