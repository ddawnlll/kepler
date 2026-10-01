"""G2 tek giriş: nedensellik denetimi -> hakem -> defter. Hakem sonucu deftere yalnızca buradan (denetimden geçerek) girer.

Sinyal birim pozisyon (+1/-1/0/NaN) döndürür; hedef = birim x notional. Gerçekçi koşul zorunlu: sonraki-bar dolum, slippage >= MIN_SLIP_RT_BPS,
açık pozisyon çıkış maliyeti. `window`: sinyal TAM seride hesaplanır (ısınma), hakem yalnızca pencerede koşar."""
import inspect
from dataclasses import asdict

import pandas as pd

from kepler import audit, ledger, referee, tape

MIN_SLIP_RT_BPS = 1.0  # UNKNOWN: gerçek slippage ölçülmedi; majörlerde alt sınır varsayımı, duyarlılık ızgarası g2'de


def evaluate(signal, kl: pd.DataFrame, specs: list, ledger_path, hypothesis: str, data: str, funding=None, mark=None,
             notional: float = 1000.0, name: str = "", params: dict | None = None, window: tuple | None = None) -> list[dict]:
    """Her spec için {'res': hakem sonucu, 'row': defter satırı}. Denetim (nedensellik) sinyal başına bir kez koşar."""
    for sp in specs:
        if sp.fill != "next_open" or not sp.close_out or not sp.liq or sp.slip_rt_bps < MIN_SLIP_RT_BPS or sp.fee_rt_bps < 1.0 or sp.mmr <= 0:
            raise ValueError(f"gerçekçi olmayan Spec reddedildi (fill=next_open, close_out, liq, slip>={MIN_SLIP_RT_BPS}, fee>=1, mmr>0): {sp}")
    audit.assert_causal(signal, kl)
    unit = tape.check_target(kl, signal(kl).astype(float))
    if not unit.equals(signal(kl).astype(float)) or unit.abs().max() > 1:
        raise ValueError("sinyal belirlenimsiz ya da birim pozisyon |x|<=1 değil")
    utc = lambda x: pd.Timestamp(x).tz_localize("UTC") if pd.Timestamp(x).tzinfo is None else pd.Timestamp(x).tz_convert("UTC")  # noqa: E731
    lo, hi = (utc(window[0]), utc(window[1])) if window else (kl.index[0], kl.index[-1] + pd.Timedelta("1h"))
    keep = (kl.index >= lo) & (kl.index < hi)
    if not keep.any():
        raise ValueError("pencerede bar yok")
    unit = unit.ffill()  # NaN = tut: pencere başında tutulan pozisyon açık hedef olur (pencereler bağımsız koşar)
    code = ledger.code_hash(referee.__file__, __file__, audit.__file__, ledger.__file__, tape.__file__, inspect.getsourcefile(signal))
    out = []
    for sp in specs:
        res = referee.run(kl[keep], (unit * notional)[keep], sp, funding, None if mark is None else mark.loc[(mark.index >= lo) & (mark.index < hi)])
        cfg = dict(name=name, params=params or {}, notional=notional, spec=asdict(sp), window=[str(lo), str(hi)], audit_causal=True)
        out.append(dict(res=res, row=ledger.record(ledger_path, "referee", hypothesis, cfg, code, data, result=res["summary"])))
    return out
