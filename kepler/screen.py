"""vectorbt eleme: sonraki-bar açılışı + çıkış maliyeti; lot/min-notional/funding/likidasyon yok."""
import pandas as pd
import vectorbt as vbt

from kepler import ledger


def actions(target: pd.Series) -> pd.Series:
    """Hakemdeki kural: NaN = tut; hedef yalnızca önceki (tutulan) değerden farklıysa emir. Diğer barlar NaN."""
    held = target.ffill().fillna(0.0)
    return held.where(held != held.shift(fill_value=0.0))


def screen(kl: pd.DataFrame, targets: dict[str, pd.Series], fee_rt_bps: float, ledger_path, slip_rt_bps: float | None = None, capital: float = 500.0,
           hypothesis: str = "", data_hash: str = "") -> pd.Series:
    """Her konfigürasyon için net PnL (USDT) tahmini. Her konfigürasyon deftere (eleme olarak) yazılır: defter zorunlu (deneme sayacı)."""
    if slip_rt_bps is None or not 0 < slip_rt_bps < float("inf"):
        raise ValueError("eleme pozitif slippage gerektirir")
    size = pd.DataFrame({k: actions(v).shift(1) for k, v in targets.items()})
    close = pd.DataFrame({k: kl.close for k in size})
    pf = vbt.Portfolio.from_orders(close, price=kl.open.to_numpy()[:, None], val_price=kl.open.to_numpy()[:, None], size=size, size_type="targetvalue", direction="both", fees=(fee_rt_bps + slip_rt_bps) / 2 / 1e4,
                                   init_cash=capital, freq="1h")
    score = pf.final_value() - capital - pf.assets().iloc[-1].abs() * kl.close.iloc[-1] * (fee_rt_bps + slip_rt_bps) / 2 / 1e4
    code = ledger.code_hash(__file__)
    for name, s in score.items():
        cfg = dict(name=name, fee_rt_bps=fee_rt_bps, slip_rt_bps=slip_rt_bps, capital=capital, target_sha=ledger.sha(targets[name].round(6).tolist()))
        ledger.record(ledger_path, "screen", hypothesis, cfg, code, data_hash, score=float(s))
    return score
