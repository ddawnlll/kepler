"""#11: niyet izi tablosu. Çekirdek (referee_core._decide) her hedef değişimini (IT/IF dizileri) kaydeder; burada tabloya çevrilir ve özetlenir: niyet → lot/tavan sonrası hedef → emir → dolum/red/bloke."""
import numpy as np
import pandas as pd

COLS = ["sym", "ts", "target_notional", "px", "pos_qty", "want_qty", "delta_qty", "gap_notional", "status", "filled_qty", "reason"]
STATUS = np.array(["", "sent", "noop_lot", "blocked_minimum", "blocked_halt", "rejected"], dtype=object)  # çekirdek durum kodları
NOT_SENT = ["blocked_minimum", "noop_lot", "blocked_halt"]


def from_kernel(syms: list, IT: np.ndarray, IF: np.ndarray) -> pd.DataFrame:
    """IT = (sembol, ts, durum kodu), IF = (hedef notional [equity ölçekli], fiyat, mevcut miktar, lot sonrası hedef miktar, dolan miktar). gap = istenen − (gönderildiyse yuvarlanmış hedef, değilse fiilen tutulan) notional."""
    st = STATUS[IT[:, 2]]
    held = np.where(st == "sent", IF[:, 3], IF[:, 2])
    return pd.DataFrame(dict(sym=np.array(syms, dtype=object)[IT[:, 0]], ts=IT[:, 1], target_notional=IF[:, 0], px=IF[:, 1], pos_qty=IF[:, 2], want_qty=IF[:, 3], delta_qty=IF[:, 3] - IF[:, 2],
                             gap_notional=IF[:, 0] - held * IF[:, 1], status=st, filled_qty=IF[:, 4], reason=np.where(st == "rejected", "marj/piyasa yok", ""))).astype({"status": object})[COLS]


def finalize(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Gönderildi ama hiç dolmadı ve red de yok → engine_unfilled (başarı sayılmaz); kısmi dolum → partial. Dönüş: (tablo, özet alanları)."""
    sent = df.status == "sent"
    df.loc[sent & (df.filled_qty == 0), ["status", "reason"]] = ["engine_unfilled", "emir gönderildi, dolum ve red yok"]
    df.loc[sent & (df.filled_qty > 0) & ((df.filled_qty - df.delta_qty.abs()).abs() > 1e-9), "status"] = "partial"
    n = lambda st: int((df.status == st).sum())  # noqa: E731
    b = df[df.status.isin(NOT_SENT)]
    return df, dict(n_intents=len(df), n_blocked_minimum=n("blocked_minimum"), n_noop_lot=n("noop_lot"), n_blocked_halt=n("blocked_halt"), n_partial=n("partial"), n_engine_unfilled=n("engine_unfilled"),
                    blocked_notional=float((b.delta_qty.abs() * b.px).sum()), gap_notional_abs=float(df.gap_notional.abs().sum()))
