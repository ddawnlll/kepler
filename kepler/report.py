"""C6/rapor: hakem sonucundan işlem-seviyesinde, açıklanabilir çıktı. Saatlik PnL yeniden kurulumu (kill switch ve Sharpe/DSR için) + işlem tablosu."""
import numpy as np
import pandas as pd


def hourly_pnl(kl: pd.DataFrame, mark: pd.DataFrame | None, funding: pd.DataFrame | None, fills: pd.DataFrame, spec, fallback=None) -> pd.Series:
    """Saatlik net PnL (fiyat + funding - komisyon - likidasyon ücreti, son barda çıkış maliyeti); toplamı hakem net_pnl'ine eşit. Gövde barı dolumları (stop, likidasyon: ts = t+1h-1ns)
    kendi barlarına yazılır: bar PnL'i = önceki pozisyon x (sonraki açılış - açılış) + sum(Δ x (sonraki açılış - dolum fiyatı)) - komisyon."""
    raw_ts = pd.DatetimeIndex(pd.to_datetime(fills.ts, unit="ns", utc=True))
    bar = raw_ts.floor("1h").where(raw_ts.floor("1h") <= kl.index[-1], kl.index[-1])
    rate = funding.last_funding_rate.copy() if funding is not None else pd.Series(dtype=float)
    if len(rate):
        rate.index = rate.index.round("1min")
        rate = rate[(rate.index >= kl.index[0] + pd.Timedelta("1h")) & (rate.index <= kl.index[-1] + pd.Timedelta("1h"))]
    # Keep gap-time and terminal settlement fills; the latter posts in the last real bar.
    fund_bars = rate.index - pd.Timedelta("1h") if len(rate) else pd.DatetimeIndex([], tz=kl.index.tz)
    ix = kl.index.union(bar.unique()).union(fund_bars.unique()).sort_values()
    opened = kl.open.reindex(ix).fillna(kl.close.reindex(ix, method="ffill"))
    nxt = opened.shift(-1).fillna(kl.close.iloc[-1])
    signed = np.where(fills.side == "BUY", fills.qty, -fills.qty)
    by_bar = lambda v: pd.Series(np.asarray(v, float), index=bar).groupby(level=0).sum().reindex(ix, fill_value=0.0)
    pos = by_bar(signed).cumsum()
    side_fee = (spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4
    liq = fills.qty * fills.px * fills.liq * max(0.0, (spec.mmr if spec.liq_fee_rate is None else spec.liq_fee_rate) - side_fee)
    pnl = pos.shift(1, fill_value=0.0) * (nxt - opened) + by_bar(signed * (nxt.reindex(bar).to_numpy() - fills.px.to_numpy())) - by_bar(fills.commission) - by_bar(liq)
    order = np.argsort(raw_ts.asi8, kind="stable")
    ft, fq = raw_ts.asi8[order], np.cumsum(signed[order])
    fallback = kl if fallback is None else fallback
    for T, r in rate.items():
        b = T - pd.Timedelta("1h")
        c = (mark.close if mark is not None else fallback.close).get(b, np.nan)
        if np.isnan(c) and mark is not None:
            c = fallback.close.get(b, np.nan)
        if np.isnan(c):
            continue
        # Timestamp-T liquidation and entries happen AFTER timestamp-T funding.
        j = np.searchsorted(ft, T.value, side="left") - 1
        pnl[b] -= (fq[j] if j >= 0 else 0.0) * c * r
    if spec.close_out:
        pnl.iloc[-1] -= abs(pos.iloc[-1]) * kl.close.iloc[-1] * side_fee

    return pnl


def book_pnl(data: dict, res: dict, spec) -> pd.Series:
    """Portföy saatlik net PnL: sembol başına hourly_pnl'nin toplamı (data[sym] = kl, funding, mark içeren dict'ler; res = run_portfolio çıktısı)."""
    parts = [hourly_pnl(d["kl"], d.get("mark"), d.get("funding"), res["fills"][res["fills"].sym == s], spec, d.get("funding_fallback_kl")) for s, d in data.items()]
    return pd.concat(parts, axis=1).fillna(0.0).sum(axis=1).sort_index()


def reconcile(data: dict, res: dict, spec, abs_tol: float = 0.01, rel_tol: float = 1e-7) -> dict:
    """Günlük/saatlik yeniden kurulum toplamı ile hakem net_pnl'i arasında mutabakat (#11). Önceden tanımlı tolerans: abs_tol + rel_tol x işlem hacmi (USDT).
    Dönüş: dict(recon_sum, net_pnl, diff, tol, ok). Muhasebe yolları ayrışırsa ok=False (sessiz geçmez)."""
    total = float(book_pnl(data, res, spec).sum())
    f = res["fills"]
    tol = abs_tol + rel_tol * float((f.qty * f.px).sum())
    diff = total - float(res["summary"]["net_pnl"])
    return dict(recon_sum=total, net_pnl=float(res["summary"]["net_pnl"]), diff=diff, tol=tol, ok=abs(diff) <= tol)


def trades(fills: pd.DataFrame, close_px: float | None = None, close_ts: int | None = None) -> pd.DataFrame:
    """Her kapanış/azaltma olayı başına bir satır (kısmi azaltmalar ayrı satır): açılış, kapanış, yön, notional, tutma süresi (saat), brüt bps (fee'siz fiyat getirisi). Çevirmeler iki işlem sayılır.
    close_px/close_ts (ns) verilirse sonda açık kalan bacak o fiyattan kapatılmış sayılır (değerleme satırı; toplam PnL hakem net'iyle uzlaşsın diye)."""
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
    if close_px is not None and abs(pos) > 1e-12:
        side, c = (1 if pos > 0 else -1), abs(pos)
        rows.append(dict(opened=pd.Timestamp(t0, unit="ns", tz="UTC"), closed=pd.Timestamp(close_ts, unit="ns", tz="UTC"), side="long" if side > 0 else "short", notional=cost * c, hours=(close_ts - t0) / 3.6e12,
                         gross_bps=side * (close_px / cost - 1) * 1e4, pnl=side * (close_px - cost) * c))
    return pd.DataFrame(rows, columns=["opened", "closed", "side", "notional", "hours", "gross_bps", "pnl"])


def markdown(name: str, res: dict) -> str:
    s, t = res["summary"], trades(res["fills"])
    w = t[t.pnl > 0]
    lines = [f"### {name}", f"net {s['net_pnl']:.2f} · brüt {s['gross_pnl']:.2f} · fee {s['fee']:.2f} · slippage {s['slippage']:.2f} · funding {s['funding']:.2f} · çıkış {s['exit_cost']:.2f} · likidasyon {s['n_liq']}",
             f"işlem {len(t)} · kazanan %{100 * len(w) / max(len(t), 1):.0f} · ort. brüt {t.gross_bps.mean() if len(t) else 0:.0f} bps · ort. tutma {t.hours.mean() if len(t) else 0:.0f} sa",
             "| açılış | kapanış | yön | brüt bps | PnL |", "|---|---|---|---|---|"]
    return "\n".join(lines + [f"| {r.opened:%Y-%m-%d %H} | {r.closed:%Y-%m-%d %H} | {r.side} | {r.gross_bps:.0f} | {r.pnl:.2f} |" for r in t.itertuples()])
