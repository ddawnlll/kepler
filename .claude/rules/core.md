---
paths:
  - kepler/referee.py
  - kepler/audit.py
  - kepler/evaluate.py
  - kepler/ledger.py
  - kepler/risk.py
  - kepler/stats.py
  - kepler/robust.py
  - kepler/state.py
  - kepler/tape.py
  - kepler/data.py
  - kepler/qc.py
  - kepler/universe.py
  - tools/**
---
# Korumalı çekirdek
Hakem, denetim, risk, state, veri ve mühür koduna yalnızca kullanıcı + güçlü model + bağımsız inceleme dokunur (AGENTS.md). `guard.py` yazmayı reddediyorsa kullanıcı oturumu `KEPLER_CORE_UNLOCK=1` ile açmamıştır: dur, ne istediğini ve nedenini yaz, kullanıcıya sor.
Mühürlü dönem (son 6 ay) açılmaz; `tools/seal_holdout.py` gerçek veriyle çalıştırılmaz.
