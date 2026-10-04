---
name: new-experiment
description: Yeni bir ön kayıtlı deney (protokol + betik + rapor) açma iş akışı. Mevcut sistemi/sinyali yeni bir koşuyla sınamadan önce kullan.
---
1. `reports/*_protocol.md` ve `scripts/` içinde benzer deney var mı bak; varsa onu genişlet.
2. Protokolü yaz ve KOŞUDAN ÖNCE commit'le: soru, kural, sabit parametreler, evren, dönem, ölçüt, N, "ne olursa ne kararı" (K kartı). Mühür dışı; görülmüş veri ise bunu açıkça yaz.
3. İşçi betiği: `scripts/<ad>.py` (Modal'de koşar) + gerekirse `scripts/<ad>_report.py`; çekirdeğe dokunma. Hakem ve defter dışında sonuç sayma.
4. Koş (`modal run modal_app.py --cmd "..."`), rapor `reports/<ad>.md`, tablolar `reports/<ad>_data/`. Doğrulanmamışı "doğrulanmadı" yaz.
5. TASKS.md `Aktif iş:` + N sayacı. Protokol artık değişmez.
