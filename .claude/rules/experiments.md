---
paths:
  - scripts/**
  - reports/**
---
# Deney / rapor kuralları
- Bir deney = bir ön kayıt (`reports/<ad>_protocol.md`, koşudan önce commit) + bir işçi betiği. Var olan betiği genişlet, kopyalama; sonuç `reports/<ad>.md` + `reports/<ad>_data/`.
- Sonuçlanmış ön kayıt (`<ad>.md` var) değişmez; değişiklik = yeni ön kayıt + yeni deneme. Deneme sayısı N kümülatif sayaca ve TASKS.md'ye yazılır.
- Sonuç deftere yalnızca hakemden girer. Rakam sorgudan/defterden gelir; doğrulanmamış rakam "doğrulanmadı" yazılır, hafızadan sayı verilmez.
- Mühürlü dönem (son 6 ay) açılmaz. Yeni `.md` açma: izin listesi `tests/test_architecture.py` içinde.
