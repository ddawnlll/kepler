"""C6/rapor: hakem sonucundan işlem-seviyesinde, açıklanabilir çıktı. Saatlik PnL yeniden kurulumu (kill switch ve Sharpe/DSR için) + işlem tablosu."""
import numpy as np
import pandas as pd


def hourly_pnl(kl: pd.DataFrame, mark: pd.DataFrame | None, funding: pd.DataFrame | None, fills: pd.DataFrame, spec) -> pd.Series:
    """Saatlik net PnL (fiyat + funding - komisyon, son barda çıkış maliyeti); toplamı hakem net_pnl'ine eşit olmalı (likidasyonsuz koşuda)."""
    t = pd.to_datetime(fills.ts, unit="ns", utc=True)
    signed = pd.Series(np.where(fills.side == "BUY", fills.qty, -fills.qty), index=t).groupby(level=0).sum()
    pos = signed.reindex(kl.index, fill_value=0.0).cumsum()
    nxt = kl.open.shift(-1).fillna(kl.close.iloc[-1])
    pnl = pos * (nxt - kl.open) - pd.Series(fills.commission.to_numpy(), index=t).groupby(level=0).sum().reindex(kl.index, fill_value=0.0)
    if funding is not None and len(funding):
        rate = funding.last_funding_rate.copy()
        rate.index = rate.index.round("1min")
        mk = (mark.close if mark is not None else kl.close)
        for T, r in rate.items():
            b = T - pd.Timedelta("1h")
            if b in pos.index:
                pnl[b] += -pos[b] * mk.get(b, kl.close[b]) * r  # T öncesi tutulan pozisyon x mark kapanışı (hakemle aynı kural)
    pnl.iloc[-1] -= abs(pos.iloc[-1]) * kl.close.iloc[-1] * (spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4
    return pnl


def trades(fills: pd.DataFrame) -> pd.DataFrame:
    """Her kapanış/azaltma olayı başına bir satır (kısmi azaltmalar ayrı satır): açılış, kapanış, yön, notional, tutma süresi (saat), brüt bps (fee'siz fiyat getirisi). Çevirmeler iki işlem sayılır."""
    rows, pos, cost, qty_open, t0 = [], 0.0, 0.0, 0.0, None
    for r in fills.itertuples():
        d = r.qty if r.side == "BUY" else -r.qty
        while abs(d) > 1e-12:
            if pos == 0 or pos * d > 0:  # aç / büyüt
                cost, qty_open = (cost * abs(pos) + r.px * abs(d)) / (abs(pos) + abs(d)), qty_open + abs(d)
                t0, pos, d = (t0 if pos else r.ts), pos + d, 0.0
            else:  # azalt / kapat
                c = min(abs(d), abs(pos))
                side = 1 if pos > 0 else -1
                rows.append(dict(opened=pd.Timestamp(t0, unit="ns", tz="UTC"), closed=pd.Timestamp(r.ts, unit="ns", tz="UTC"), side="long" if side > 0 else "short",
                                 notional=cost * c, hours=(r.ts - t0) / 3.6e12, gross_bps=side * (r.px / cost - 1) * 1e4, pnl=side * (r.px - cost) * c))
                pos, d = pos - side * c, d - np.sign(d) * c
                if abs(pos) < 1e-12:
                    pos, cost, qty_open, t0 = 0.0, 0.0, 0.0, None
    return pd.DataFrame(rows, columns=["opened", "closed", "side", "notional", "hours", "gross_bps", "pnl"])


def markdown(name: str, res: dict) -> str:
    s, t = res["summary"], trades(res["fills"])
    w = t[t.pnl > 0]
    lines = [f"### {name}", f"net {s['net_pnl']:.2f} · brüt {s['gross_pnl']:.2f} · fee {s['fee']:.2f} · slippage {s['slippage']:.2f} · funding {s['funding']:.2f} · çıkış {s['exit_cost']:.2f} · likidasyon {s['n_liq']}",
             f"işlem {len(t)} · kazanan %{100 * len(w) / max(len(t), 1):.0f} · ort. brüt {t.gross_bps.mean() if len(t) else 0:.0f} bps · ort. tutma {t.hours.mean() if len(t) else 0:.0f} sa",
             "| açılış | kapanış | yön | brüt bps | PnL |", "|---|---|---|---|---|"]
    return "\n".join(lines + [f"| {r.opened:%Y-%m-%d %H} | {r.closed:%Y-%m-%d %H} | {r.side} | {r.gross_bps:.0f} | {r.pnl:.2f} |" for r in t.itertuples()])
