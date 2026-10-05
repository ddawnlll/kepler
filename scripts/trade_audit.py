"""Trade denetimi, VERİ AŞAMASI (Modal'de koşar; LLM yok, tamamen deterministik): varsayılan Ensemble (EV1) bileşimini hakemden geçirir ve işlem-seviyesinde ham tabloları yazar.
Rapor/PDF aşaması ayrı: scripts/trade_audit_report.py (yerelde, matplotlib + reportlab).

  modal run modal_app.py --cmd "python scripts/trade_audit.py --cap 1000 --out /data/audit/ev1_1000"   (--preset ad, --window 2021-11-01:2022-02-01 duman testi)

Çıktı (--out): trades.csv (pozisyon dönemi = sembolde sıfırdan sıfıra; MAE/MFE, maliyet kalemleri, uzman katkıları), fills.csv, hourly.csv (sembol başına saatlik pozisyon + PnL bileşenleri),
daily.csv (equity, PnL, kaldıraç, maruziyet), regimes.csv, nautilus_positions.csv (Nautilus'un kendi pozisyon raporu), meta.json (hakem özeti, mutabakat).
Tanımlar: net = fiyat PnL - komisyon(fee+slip) + funding - çıkış maliyeti; saatlik PnL `report.hourly_pnl` ile aynı kural, toplamı hakem net'ine eşit (mutabakat meta.json'da)."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402  (load, spec, utc, data_of, D, EXT, MAIN, STRESS)

from kepler import ensemble as en  # noqa: E402
from kepler import evaluate as ev  # noqa: E402
from kepler import report, robust  # noqa: E402


def components(kl: pd.DataFrame, mark, funding, fl: pd.DataFrame, sp) -> pd.DataFrame:
    """Saatlik: pos (bar sonu), net (hourly_pnl), funding, commission, exit, price = net - funding + commission + exit. Aynı kural `report.hourly_pnl` (toplam net'e eşit)."""
    base = report.hourly_pnl(kl, mark, None, fl, sp)  # fiyat - komisyon - çıkış (funding'siz); funding aşağıda hakemle aynı kuralla (mark NaN/eksik -> kline kapanışı)
    bar = pd.DatetimeIndex(pd.to_datetime(fl.ts, unit="ns", utc=True)).floor("1h")
    by_bar = lambda v: pd.Series(np.asarray(v, float), index=bar).groupby(level=0).sum().reindex(kl.index, fill_value=0.0)  # noqa: E731
    signed = np.where(fl.side == "BUY", fl.qty, -fl.qty)
    pos = by_bar(signed).cumsum()
    liq = fl.qty * fl.px * fl.liq * max(0.0, (sp.mmr if sp.liq_fee_rate is None else sp.liq_fee_rate) - (sp.fee_rt_bps + sp.slip_rt_bps) / 2 / 1e4)
    comm = by_bar(fl.commission) + by_bar(liq)
    fund = pd.Series(0.0, index=kl.index)
    if funding is not None and len(funding):
        rate = funding.last_funding_rate.copy()
        rate.index = rate.index.round("1min")
        mk = (mark.close.reindex(kl.index) if mark is not None else kl.close).fillna(kl.close)  # report.hourly_pnl yalnızca eksik anahtarda düşer, NaN değerde düşmez: hakem ikisinde de düşer
        for T, r in rate.items():
            b = T - pd.Timedelta("1h")
            if b in pos.index:
                fund[b] += -pos[b] * mk[b] * r
    ex = pd.Series(0.0, index=kl.index)
    ex.iloc[-1] = abs(pos.iloc[-1]) * kl.close.iloc[-1] * (sp.fee_rt_bps + sp.slip_rt_bps) / 2 / 1e4
    net = base + fund
    return pd.DataFrame(dict(pos=pos, net=net, funding=fund, commission=comm, exit=ex, price=base + comm + ex, close=kl.close, high=kl.high, low=kl.low))


def episodes(sym: str, fl: pd.DataFrame, h: pd.DataFrame, eq: pd.Series) -> list[dict]:
    """Pozisyon dönemleri: sembolde sıfırdan sıfıra (işaret değişimi = kapanış + yeni açılış)."""
    rows, pos, cur = [], 0.0, None
    sgn = lambda x: 0 if abs(x) < 1e-12 else (1 if x > 0 else -1)  # noqa: E731

    def close(ts, open_end=False):
        nonlocal cur
        o, c = pd.Timestamp(cur["t0"], unit="ns", tz="UTC"), pd.Timestamp(ts, unit="ns", tz="UTC")
        ob, cb = o.floor("1h"), c.floor("1h")
        w = h[(h.index >= ob) & (h.index <= cb)]
        held = h[(h.index >= ob) & (h.index < cb)]  # pozisyonun bar başında açık olduğu barlar (funding/risk)
        ent = cur["vwap_in"]
        side = cur["side"]
        px_ext = (w.low.min(), w.high.max()) if len(w) else (ent, ent)
        mae = side * ((px_ext[0] if side > 0 else px_ext[1]) / ent - 1) * 1e4  # aleyhe en kötü sapma (bps)
        mfe = side * ((px_ext[1] if side > 0 else px_ext[0]) / ent - 1) * 1e4  # lehe en iyi sapma (bps)
        notional_t = (held.pos.abs() * held.close) if len(held) else pd.Series([cur["max_notional"]])
        fund = float(held.funding.sum()) if len(held) else 0.0
        price_pnl = cur["cash"]  # dönem sıfıra döndüğü için nakit akışı = fiyat PnL
        exit_cost = float(w.exit.sum()) if open_end else 0.0
        if open_end:
            price_pnl += cur["pos"] * h.close.iloc[-1]
        rows.append(dict(sym=sym, opened=o, closed=c, side="long" if side > 0 else "short", hours=(c - o).total_seconds() / 3600, n_fills=cur["n"], vwap_in=ent, vwap_out=cur["vwap_out"],
                         max_notional=cur["max_notional"], avg_notional=float(notional_t.mean()), eq_at_open=float(eq.asof(ob)) if len(eq) else np.nan, price_pnl=price_pnl, commission=cur["comm"],
                         funding=fund, exit_cost=exit_cost, net=price_pnl - cur["comm"] + fund - exit_cost, mae_bps=mae, mfe_bps=mfe, gross_bps=side * (cur["vwap_out"] / ent - 1) * 1e4 if cur["vwap_out"] else np.nan,
                         open_at_end=open_end, liq=cur["liq"]))
        cur = None

    for r in fl.itertuples():
        d = r.qty if r.side == "BUY" else -r.qty
        if cur is not None and cur["side"] * d < 0 and abs(d) > abs(pos) + 1e-12:  # çevirme: kalan kadarı kapatır, fazlası yeni dönem
            rem = abs(pos)
            cur["cash"] += -np.sign(d) * rem * r.px
            cur["comm"] += r.commission * rem / abs(d)
            cur["out_q"], cur["out_v"] = cur["out_q"] + rem, cur["out_v"] + rem * r.px
            cur["vwap_out"] = cur["out_v"] / cur["out_q"]
            cur["n"] += 1
            cur["liq"] |= bool(r.liq)
            close(r.ts)
            d, pos = d - np.sign(d) * rem, 0.0
            frac = abs(d) / (abs(d) + rem)
            comm_new = r.commission * frac
        else:
            comm_new = r.commission
        if cur is None and abs(d) > 1e-12:
            cur = dict(t0=r.ts, side=sgn(d), pos=0.0, cash=0.0, comm=0.0, n=0, in_q=0.0, in_v=0.0, out_q=0.0, out_v=0.0, vwap_in=r.px, vwap_out=None, max_notional=0.0, liq=False)
        if cur is None:
            continue
        cur["cash"] += -d * r.px
        cur["comm"] += comm_new
        cur["n"] += 1
        cur["liq"] |= bool(r.liq)
        if d * cur["side"] > 0:  # büyüt
            cur["in_q"], cur["in_v"] = cur["in_q"] + abs(d), cur["in_v"] + abs(d) * r.px
            cur["vwap_in"] = cur["in_v"] / cur["in_q"]
        else:  # azalt
            cur["out_q"], cur["out_v"] = cur["out_q"] + abs(d), cur["out_v"] + abs(d) * r.px
            cur["vwap_out"] = cur["out_v"] / cur["out_q"]
        pos += d
        cur["pos"] = pos
        cur["max_notional"] = max(cur["max_notional"], abs(pos) * r.px)
        if abs(pos) < 1e-12:
            pos = 0.0
            close(r.ts)
    if cur is not None:  # veri sonunda açık dönem: son kapanıştan değerlenir
        close(int(h.index[-1].value) + 3_600_000_000_000, open_end=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cap", type=float, default=1000.0)
    ap.add_argument("--preset", default="ev1", choices=list(en.PRESETS))
    ap.add_argument("--window", default=None, help="a:b duman testi (varsayılan 2020-04-01:2026-04-01)")
    a = ap.parse_args()
    window = tuple(a.window.split(":")) if a.window else E.MAIN
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    E.load(E.EXT, [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)], cap=a.cap)
    p = en.Params(**en.PRESETS[a.preset])
    data, sp = E.data_of(E.EXT), E.spec(cap=a.cap)
    kls = {s: d["kl"] for s, d in data.items()}
    out = en.make_book(a.cap, p)(kls)
    res, win, _ = ev.run_book(out, data, sp, *E.utc(window))
    fills = res["fills"].sort_values("ts").reset_index(drop=True)
    comp = {s: components(win[s]["kl"], win[s].get("mark"), win[s].get("funding"), fills[fills.sym == s], sp) for s in win}
    net_h = pd.concat([c.net for c in comp.values()], axis=1).fillna(0.0).sum(axis=1).sort_index()
    eq_h = a.cap + net_h.cumsum()
    recon = float(net_h.sum() - res["summary"]["net_pnl"])
    names, w = en.composition(p)
    close_d, _ = en.panel(kls)
    st = en.market_state(close_d, kls, p)
    es = dict(zip(names, en.experts(close_d, st, p)))
    f_tot = en.combine(tuple(es.values()), st, p)
    reg = robust.regime(close_d["BTCUSDT"])
    rows = []
    for s in win:
        rows += episodes(s, fills[fills.sym == s], comp[s], eq_h)
    tr = pd.DataFrame(rows).sort_values("opened").reset_index(drop=True)
    day = (tr.opened - pd.Timedelta("1h")).dt.normalize()  # karar günü (23:00 barı kapanışı; dolum ertesi gün açılışı)
    tr["decision_day"] = day
    tr["regime"] = reg.reindex(day).to_numpy()
    tr["sigma"] = [st["sigma"].at[d, s] if d in st["sigma"].index else np.nan for d, s in zip(day, tr.sym)]
    tr["f_total"] = [f_tot.at[d, s] if d in f_tot.index else np.nan for d, s in zip(day, tr.sym)]
    sd = tr.side.map({"long": 1, "short": -1})
    for n, wt in zip(names, w):
        tr[f"c_{n}"] = [sg * wt * (es[n].at[d, s] if d in es[n].index and pd.notna(es[n].at[d, s]) else 0.0) for sg, d, s in zip(sd, day, tr.sym)]  # yön-hizalı katkı (+ = bu uzman pozisyonu destekledi)
    tr.to_csv(out_dir / "trades.csv", index=False)
    fills.to_csv(out_dir / "fills.csv", index=False)
    hourly = pd.concat({s: c[["pos", "close", "high", "low", "net", "funding", "commission", "exit", "price"]] for s, c in comp.items()}, axis=1)
    hourly.columns = [f"{s}.{k}" for s, k in hourly.columns]
    hourly.to_csv(out_dir / "hourly.csv")
    gross_h = sum((c.pos.abs() * c.close) for c in comp.values())
    net_exp_h = sum((c.pos * c.close) for c in comp.values())
    d = pd.DataFrame(dict(equity=eq_h.resample("1D").last(), net=net_h.resample("1D").sum(), gross_lev_mean=(gross_h / eq_h).resample("1D").mean(), gross_lev_max=(gross_h / eq_h).resample("1D").max(),
                          gross_notional=gross_h.resample("1D").mean(), net_exposure=net_exp_h.resample("1D").mean(), n_symbols_open=sum((c.pos.abs() > 1e-12).astype(int) for c in comp.values()).resample("1D").mean()))
    d["regime"] = reg.reindex(d.index).to_numpy()
    d["btc_close"] = close_d["BTCUSDT"].reindex(d.index).to_numpy()
    d.to_csv(out_dir / "daily.csv")
    pd.DataFrame(dict(regime=reg)).to_csv(out_dir / "regimes.csv")
    res["positions"].to_csv(out_dir / "nautilus_positions.csv", index=False)
    meta = dict(cap=a.cap, preset=a.preset, names=names, weights=w, window=window, summary=res["summary"], recon_hourly_vs_referee=recon, n_episodes=len(tr), rejected=len(res["rejected"]), stress=E.STRESS)
    (out_dir / "meta.json").write_text(json.dumps(meta, default=str, indent=1))
    print("tamam:", len(tr), "dönem,", len(fills), "dolum; mutabakat farkı", recon, "; net", res["summary"]["net_pnl"], "; dönemler toplamı", float(tr.net.sum()), flush=True)


if __name__ == "__main__":
    main()
