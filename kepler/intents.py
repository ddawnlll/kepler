"""#11: niyet izi tablosu (hakem Adapter'ı satırları toplar; burada kapatılır ve özetlenir). Niyet → lot/tavan sonrası hedef → emir → dolum/red/bloke."""
import pandas as pd

COLS = ["sym", "ts", "target_notional", "px", "pos_qty", "want_qty", "delta_qty", "gap_notional", "status", "filled_qty", "reason"]
NOT_SENT = ["blocked_minimum", "noop_lot", "blocked_halt"]


def intent_row(k, t, tgt, px, pos, want, status) -> dict:
    """Niyet satırı. tgt = istenen işaretli notional (equity ölçekli), want = lot/tavan sonrası hedef miktar, gap = istenen − (gönderildiyse yuvarlanmış hedef, değilse fiilen tutulan pozisyon) notional; filled/reason dolum ve red sırasında güncellenir."""
    return dict(sym=k.removesuffix("-PERP"), ts=t, target_notional=float(tgt), px=float(px), pos_qty=float(pos), want_qty=float(want), delta_qty=float(want - pos),
                gap_notional=float(tgt) - float(want if status == "sent" else pos) * float(px), status=status, filled_qty=0.0, reason="")


def finalize(rows: list[dict]) -> tuple[pd.DataFrame, dict]:
    """Gönderildi ama hiç dolmadı ve red de yok → engine_unfilled (örn. fiyat hassasiyeti "Skipping fill": başarı sayılmaz); kısmi dolum → partial. Dönüş: (tablo, özet alanları)."""
    df = pd.DataFrame(rows, columns=COLS)
    sent = df.status == "sent"
    df.loc[sent & (df.filled_qty == 0), ["status", "reason"]] = ["engine_unfilled", "emir gönderildi, dolum ve red yok"]
    df.loc[sent & (df.filled_qty > 0) & ((df.filled_qty - df.delta_qty.abs()).abs() > 1e-9), "status"] = "partial"
    n = lambda st: int((df.status == st).sum())  # noqa: E731
    b = df[df.status.isin(NOT_SENT)]
    return df, dict(n_intents=len(df), n_blocked_minimum=n("blocked_minimum"), n_noop_lot=n("noop_lot"), n_blocked_halt=n("blocked_halt"), n_partial=n("partial"), n_engine_unfilled=n("engine_unfilled"),
                    blocked_notional=float((b.delta_qty.abs() * b.px).sum()), gap_notional_abs=float(df.gap_notional.abs().sum()))
