"""C3: vectorbt ELEME. Yalnızca hızlı filtre: sonuç sayılmaz, deftere `score` olarak girer (result yazamaz).

Hakemle aynı sözleşme ve dolum kuralı: hedef değişince kapanış fiyatından hedef notional'a ayarla (targetvalue).
Yaklaşımlar (hakemden fark): lot/min-notional yuvarlaması, funding ve likidasyon YOK.
"""
import pandas as pd
import vectorbt as vbt

from kepler import ledger


def actions(target: pd.Series) -> pd.Series:
    """Hakemdeki kural: NaN = tut; hedef yalnızca önceki (tutulan) değerden farklıysa emir. Diğer barlar NaN."""
    held = target.ffill().fillna(0.0)
    return held.where(held != held.shift(fill_value=0.0))


def screen(kl: pd.DataFrame, targets: dict[str, pd.Series], fee_rt_bps: float, slip_rt_bps: float = 0.0, capital: float = 500.0,
           ledger_path=None, hypothesis: str = "", data_hash: str = "") -> pd.Series:
    """Her konfigürasyon için net PnL (USDT) tahmini. ledger_path verilirse her konfigürasyon deftere (eleme olarak) yazılır."""
    size = pd.DataFrame({k: actions(v) for k, v in targets.items()})
    close = pd.DataFrame({k: kl.close for k in size})
    pf = vbt.Portfolio.from_orders(close, size=size, size_type="targetvalue", direction="both", fees=(fee_rt_bps + slip_rt_bps) / 2 / 1e4,
                                   init_cash=capital, freq="1h")
    score = pf.final_value() - capital
    if ledger_path is not None:
        code = ledger.code_hash(__file__)
        for name, s in score.items():
            ledger.record(ledger_path, "screen", hypothesis, dict(name=name, fee_rt_bps=fee_rt_bps, slip_rt_bps=slip_rt_bps, capital=capital),
                          code, data_hash, score=float(s))
    return score
