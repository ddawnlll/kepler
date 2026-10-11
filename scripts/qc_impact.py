"""#18: veri QC bulgularının strateji sonuçlarına (carry_xs C1 geliştirme koşusu) ekonomik etkisi. Veriyi TEMİZLEMEZ; ölçer. Geliştirme verisi; mühürlü dönem yok.
  modal run modal_app.py --cmd "python scripts/qc_impact.py --out /data/qc_impact"
BAYRAKLAR (kepler/qc.py eşikleriyle aynı, bayrak = kanıt değil): gap (eksik saatlik bar sonrası ilk bar), mark_fallback (funding anında mark barı yok: kline kapanışına düşüldü), mark_last_div (|mark/last−1| > MARK_DIV),
fund_extreme (|oran| > FUND_MAX), fund_interval (aralık ≠ 8h): aralık 1/2/4/8 ve olay aralığı bildirilenle tutarlıysa 'legit_interval' (anomali DEĞİL), tutarsızsa UNKNOWN; jump (|saatlik getiri| > JUMP).
Meşru ekstrem vs hata: çözülemeyen alan UNKNOWN kalır (gerçek/hata ayrımı için bağımsız kaynak yok; hiçbir değer 'hatalı' ilan edilmez).
KESİŞİM: gerçek pozisyon (fill'lerden saatlik), emir (fill) ve settlement olaylarıyla; sayı değil ETKİ: etkilenen notional, fiyat/funding/maliyet/net katkısı, risk tepkisi (stop/likidasyon fill'leri).
ÖNCEDEN KAYITLI REPLAY POLİTİKALARI (koşudan önce, Sharpe artırmak için seçilmedi; hepsi aynı muhasebe yolunda `ev.run_book` + `report.reconcile`):
  P0 orijinal; P1 'funding_exclude_flagged': bayraklı (fund_extreme ∪ mark_fallback ∪ mark_last_div) settlement olaylarında funding 0 (muhafazakâr DEĞİL: gelir de çıkar; yalnız duyarlılık);
  P2 'funding_adverse_flagged': bayraklı olaylarda oran işareti pozisyon aleyhine çevrilmiş mutlak oran (|oran| x pozisyon ödemesi: ödeme muhafazakâr stres);
  P3 'mark_last_worst': mark/last ayrışan barlarda funding mark'ı olarak büyük olan (|pozisyon| maruziyeti artar) alınır.
Point-in-time: üyelik ve veri kesimi korunur (aynı `mem`/pencere); bayrak her olay için YALNIZ o olayın kendi verisinden (oran, o barın mark/last'ı, bar varlığı) hesaplanır: gelecekteki bilgiyle sembol/bar seçimi yok;
qc.divergence_cutoff (24 ardışık bar, gelecekten bakar) sembol dışlaması olarak UYGULANMAZ. Eski kart sonuçları (NO_EDGE) ve eski veri kimliği korunur; replay'ler ayrı receipt alır."""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import qc, receipt, report
from kepler.funding import schedule

HOUR = pd.Timedelta("1h")
POLICIES = ("P0_original", "P1_funding_exclude_flagged", "P2_funding_adverse_flagged", "P3_mark_last_worst")


def flags(kl: pd.DataFrame, mark: pd.DataFrame | None, funding: pd.DataFrame | None) -> dict:
    """Sembol başına bayraklar: bar bayrakları (ts indeksi) ve funding olay bayrakları (T)."""
    full = pd.date_range(kl.index[0], kl.index[-1], freq="1h")
    miss = full.difference(kl.index)
    after = pd.DatetimeIndex(sorted({kl.index[kl.index.searchsorted(t)] for t in miss if kl.index.searchsorted(t) < len(kl)}))
    ret = kl.close.pct_change().abs()
    out = dict(gap=after, jump=ret.index[ret > qc.JUMP])
    if mark is not None:
        m = mark.close.reindex(kl.index)
        out["mark_last_div"] = kl.index[((m / kl.close - 1).abs() > qc.MARK_DIV).to_numpy()]
    ev = pd.DataFrame(columns=["rate", "fund_extreme", "mark_fallback", "interval", "interval_consistent"])
    if funding is not None and len(funding):
        sched = schedule(kl, mark, funding)
        T = pd.to_datetime([e[0] for e in sched], unit="ns", utc=True)
        f = funding.copy()
        f.index = f.index.round("1min")
        iv = f["funding_interval_hours"].reindex(T).to_numpy() if "funding_interval_hours" in f else np.full(len(T), np.nan)
        gap_h = pd.Series(T, index=T).diff().dt.total_seconds().to_numpy() / 3600
        ev = pd.DataFrame(dict(rate=[e[1] for e in sched], fund_extreme=[abs(e[1]) > qc.FUND_MAX for e in sched], mark_fallback=[bool(e[3]) for e in sched], interval=iv,
                               interval_consistent=np.isclose(gap_h, iv, atol=0.02) | np.isnan(gap_h)), index=T)
    out["fund_events"] = ev
    return out


def positions(fills: pd.DataFrame, sym: str, index: pd.DatetimeIndex) -> pd.Series:
    """Bar sonu pozisyon (hourly_pnl ile aynı kural: gövde fill'i kendi barında)."""
    f = fills[fills.sym == sym]
    bar = pd.DatetimeIndex(pd.to_datetime(f.ts, unit="ns", utc=True)).floor("1h")
    sg = pd.Series(np.where(f.side == "BUY", f.qty, -f.qty), index=bar)
    return sg.groupby(level=0).sum().reindex(index, fill_value=0.0).cumsum()


def impact(data: dict, res: dict, spec) -> dict:
    """Bayrak türü başına gerçek etki. Fiyat bileşeni: bayraklı barın PnL'i (saatlik fiyat yolu, funding/maliyet hariç); funding: bayraklı settlement tutarı (hakemle aynı formül); maliyet: o bardaki fill komisyonu."""
    z = spec.__class__(**{**spec.__dict__, "fee_rt_bps": 0.0, "slip_rt_bps": 0.0})
    rows: dict[str, dict] = {}
    tot = dict(price=0.0, funding=0.0)
    unknown_interval = 0
    for s, d in data.items():
        kl, mark, fund = d["kl"], d.get("mark"), d.get("funding")
        fl = flags(kl, mark, fund)
        f = res["fills"][res["fills"].sym == s]
        pos = positions(res["fills"], s, kl.index)
        zf = f.assign(commission=0.0, liq=False)
        price = report.hourly_pnl(kl, mark, None, zf, z)
        cost = pd.Series(0.0, index=kl.index)
        fb = pd.DatetimeIndex(pd.to_datetime(f.ts, unit="ns", utc=True)).floor("1h")
        cost = pd.Series(f.commission.to_numpy(), index=fb).groupby(level=0).sum().reindex(kl.index, fill_value=0.0)
        risk = pd.Series((f.liq | f.stop).to_numpy().astype(int), index=fb).groupby(level=0).sum().reindex(kl.index, fill_value=0)
        tot["price"] += float(price.sum())
        for kind in ("gap", "jump", "mark_last_div"):
            ix = fl.get(kind, pd.DatetimeIndex([]))
            r = rows.setdefault(kind, dict(n_flags=0, n_with_position=0, notional_sum=0.0, notional_max=0.0, price=0.0, funding=0.0, cost=0.0, n_risk_fills=0))
            r["n_flags"] += len(ix)
            held = pos.reindex(ix).abs() > 0
            r["n_with_position"] += int(held.sum())
            nt = (pos.reindex(ix).abs() * kl.close.reindex(ix))[held]
            r["notional_sum"] += float(nt.sum())
            r["notional_max"] = max(r["notional_max"], float(nt.max()) if len(nt) else 0.0)
            r["price"] += float(price.reindex(ix).sum())
            r["cost"] += float(cost.reindex(ix).sum())
            r["n_risk_fills"] += int(risk.reindex(ix).sum())
        ev = fl["fund_events"]
        for T_, row in ev.iterrows():
            b = T_ - HOUR
            p_ = float(pos.get(b, np.nan)) if b in pos.index else float(pos.shift(1).iloc[min(kl.index.searchsorted(T_), len(pos) - 1)])
            c = float(mark.close.get(b, np.nan)) if mark is not None else float(kl.close.get(b, np.nan))
            c = float(kl.close.get(b, np.nan)) if np.isnan(c) else c
            amt = 0.0 if np.isnan(c) else -p_ * c * row.rate
            tot["funding"] += amt
            kinds = [k for k in ("fund_extreme", "mark_fallback") if row[k]]
            if not row.interval_consistent:
                kinds.append("fund_interval_inconsistent")
                unknown_interval += 1
            elif not np.isnan(row.interval) and row.interval != 8:
                kinds.append("fund_interval_legit_nonstd")
            for k in kinds:
                r = rows.setdefault(k, dict(n_flags=0, n_with_position=0, notional_sum=0.0, notional_max=0.0, price=0.0, funding=0.0, cost=0.0, n_risk_fills=0))
                r["n_flags"] += 1
                if abs(p_) > 0:
                    r["n_with_position"] += 1
                    nt = abs(p_) * (0.0 if np.isnan(c) else c)
                    r["notional_sum"] += nt
                    r["notional_max"] = max(r["notional_max"], nt)
                r["funding"] += amt
    for r in rows.values():
        r["net"] = r["price"] + r["funding"] - r["cost"]  # cost = o bardaki fill komisyonu (pozitif tutar)
    return dict(kinds=rows, totals=tot, unknown_interval_events=unknown_interval)


def apply_policy(data: dict, res0: dict, policy: str) -> dict:
    """Politikaya göre funding/mark verisini dönüştürür (aynı sembol/pencere; point-in-time: olay başına yalnız kendi verisi)."""
    if policy == "P0_original":
        return data
    out = {}
    for s, d in data.items():
        fund, mark, kl = d.get("funding"), d.get("mark"), d["kl"]
        if fund is None or not len(fund):
            out[s] = d
            continue
        fl = flags(kl, mark, fund)
        ev = fl["fund_events"]
        f = fund.copy()
        f.index = f.index.round("1min")
        bad_T = set(ev.index[ev.fund_extreme | ev.mark_fallback])
        div = set(fl.get("mark_last_div", []))
        if policy == "P1_funding_exclude_flagged":
            bad_T |= {T for T in ev.index if (T - HOUR) in div}
            f.loc[f.index.isin(bad_T), "last_funding_rate"] = 0.0
            out[s] = dict(d, funding=f.set_axis(fund.index))
        elif policy == "P2_funding_adverse_flagged":
            bad_T |= {T for T in ev.index if (T - HOUR) in div}
            pos = positions(res0["fills"], s, kl.index)
            for T in f.index[f.index.isin(bad_T)]:
                p_ = float(pos.get(T - HOUR, 0.0))
                if p_ != 0:  # pozisyon aleyhine: long öder (+oran), short öder (−oran)
                    f.loc[T, "last_funding_rate"] = abs(f.loc[T, "last_funding_rate"]) * (1.0 if p_ > 0 else -1.0)
            out[s] = dict(d, funding=f.set_axis(fund.index))
        elif policy == "P3_mark_last_worst":
            m = mark.copy()
            worse = np.maximum(m.close, kl.close.reindex(m.index))
            m.loc[m.index.isin(div), "close"] = worse[m.index.isin(div)]
            out[s] = dict(d, mark=m)
        else:
            raise ValueError(policy)
    return out


def stage_all(out_dir: str, part: str):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import audit_fix as AF  # noqa: E402
    import ensemble as E  # noqa: E402
    import signal_diag as sd  # noqa: E402
    import signal_phase2 as P2  # noqa: E402

    from kepler import ensemble as en  # noqa: E402
    from kepler import evaluate as ev  # noqa: E402
    cap = P2.CAPR
    mem = sd.members(20)
    syms = sorted(mem.sym.unique())
    E.D.clear()
    AF.load_dynamic(syms, cap=cap)
    syms = [s for s in syms if s in E.D]
    data, kls = E.data_of(syms), {s: E.D[s]["kl"] for s in syms}
    out = P2.make_book(en.Params(names=("carry_xs",), weights=(1.0,)), mem, False, cap)(kls)
    sp = E.spec(cap=cap)
    cut = E.utc(E.MAIN)
    rcp = receipt.make(dict(policy="qc_impact", window=E.MAIN, spec=sp.__dict__), data, cut=cut, extra_files=[__file__])
    files = {f"{r}:{s}": {k: (qc.sha256_file(p_) if (p_ := Path(r) / "tape" / kk / f"{s}.parquet").exists() else None) for k, kk in (("klines", "klines"), ("mark", "markPriceKlines"), ("funding", "fundingRate"))}
             for s in syms for r, _, _ in AF.ROOTS if (Path(r) / "tape" / "klines" / f"{s}.parquet").exists()}  # eksik tür = None (kök başına)
    t0 = time.time()
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    base = dict(receipt=dict(economic_id=rcp["economic_id"], data_manifest_id=rcp["data"]["id"], provenance=rcp["provenance"], cut=rcp["data"]["cut"], symbols=rcp["data"]["symbols"]), tape_file_sha256=files, window=E.MAIN)

    def replay(pol, res0=None):
        d = data if pol == "P0_original" else apply_policy(data, res0, pol)
        r, w, _ = ev.run_book(out, d, sp, *cut)
        rc = report.reconcile(w, r, sp)
        dn = report.book_pnl(w, r, sp).resample("1D").sum()
        return r, w, dict(net=float(r["summary"]["net_pnl"]), funding=float(r["summary"]["funding"]), sharpe=float((dn / cap).mean() / (dn / cap).std(ddof=1) * np.sqrt(365)), n_liq=int(r["summary"]["n_liq"]), recon_ok=bool(rc["ok"]),
                          recon_diff=float(rc["diff"]), funding_mark_fallback=int(r["summary"]["funding_mark_fallback"]), funding_missed=int(r["summary"]["funding_missed"]), n_rejected=int(r["summary"]["n_rejected"]), seconds=time.time() - t0)
    if part == "P0_original":  # etki tablosu + orijinal replay (yalnız bu parça bayrak x pozisyon kesişimini üretir)
        r0, w0, rep = replay(part)
        doc = dict(base, part=part, replay=rep, impact=impact(w0, r0, sp), original_net=float(r0["summary"]["net_pnl"]))
    else:
        res0 = replay("P0_original")[0] if part == "P2_funding_adverse_flagged" else None  # P2 pozisyon yönünü orijinal fill'lerden alır
        doc = dict(base, part=part, replay=replay(part, res0)[2])
    doc["seconds"] = time.time() - t0
    (Path(out_dir) / f"{part}.json").write_text(json.dumps(doc, indent=1, default=str, allow_nan=False))
    print(part, "tamam", f"{doc['seconds']:.0f}s", json.dumps(doc["replay"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/data/qc_impact")
    ap.add_argument("--part", required=True, choices=POLICIES)  # her politika ayrı konteynerde (modal run --detach); çıktı <out>/<part>.json
    a = ap.parse_args()
    stage_all(a.out, a.part)
