"""Sinyal teşhisi işçisi (reports/preregistration/signal_diagnostics.md): 9 uzmanın tahminleri → oynaklığa normalize ileri getiri; IC, kalibrasyon, sönme, fazlalık, koşullu analiz. Hakem yok.

  modal run modal_app.py --cmd "python scripts/signal_diag.py --stage panel --out /data/signal_diag"     # tahmin + ileri getiri panelleri (npz)
  modal run modal_app.py --cmd "python scripts/signal_diag.py --stage analyze --out /data/signal_diag"   # aile testleri, betimsel tablolar, deneme defteri
Tahmin: ensemble'ın kullandığı hâli (`en.REG[ad].forecast(close, st, Params())`, dinamik evrende `active & üyelik`). İleri getiri: karar günü d kapanışı → giriş = d+1 ilk saatlik barın AÇILIŞI,
çıkış = d+1+h ilk barın açılışı (hakem dolumu `next_open`); Y = ln(çıkış/giriş) / (σ_d √(h/365)), σ_d karar anındaki `market_state.sigma`. Mühür (≥ 2026-04-01) `tape.load` ile yüklenmez."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signal_diag_stats as sx  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import signals as sg  # noqa: E402

EXT9 = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
ROOTS = [("/data/pre2022", None, "2022-01-01"), ("/data", "2022-01-01", None)]
EXPERTS = ["trend", "xs_momentum", "carry", "bollinger", "lowvol", "nearhigh", "fundcrowd", "volrev", "orderflow"]
H_TIER = dict(trend=1, xs_momentum=1, carry=2, bollinger=2, lowvol=1, nearhigh=2, fundcrowd=2, volrev=2, orderflow=2)  # ön kayıt 0.1 tablosu (sonuçtan önce)
DEC_START, DEC_LAST = pd.Timestamp("2020-04-01", tz="UTC"), pd.Timestamp("2026-03-30", tz="UTC")  # karar tarihi aralığı; çıkış açılışı ≤ 2026-03-31 ayrıca kontrol edilir
DATA_END = pd.Timestamp("2026-03-31", tz="UTC")  # son kullanılabilir saatlik bar günü (mühür 2026-04-01)
PERIODS = {"2020-21": ("2020-04-01", "2021-12-31"), "2022-24": ("2022-01-01", "2024-12-31"), "2025+": ("2025-01-01", "2026-03-31")}
N_FAMILY = len(EXPERTS) * len(sx.HORIZONS) * 2
Z_CORR = float(norm.isf(0.05 / (2 * N_FAMILY)))


# ------------------------------------------------------------------ veri
def _load_safe(root: str, sym: str, lo, hi) -> dict:
    """`tape.load`; funding dosyası olmayan sembol (ICPUSDT pre2022) için funding boş (o dönemde funding hesaba girmez; ikincil hedefte hücre düşer)."""
    from kepler import tape
    try:
        return tape.load(root, sym, start=lo, end=hi)
    except Exception as e:  # noqa: BLE001
        if "fundingRate" not in str(e):
            raise
        import duckdb
        lo_, hi_ = pd.Timestamp(lo or "1970-01-01", tz="UTC"), pd.Timestamp(hi, tz="UTC") if hi else tape.SEAL_START
        if hi_ > tape.SEAL_START:
            raise ValueError("mühür sınırı aşılıyor")
        cut = tape._usable(root).get(sym)
        hi_ = min(hi_, pd.Timestamp(cut)) if cut else hi_
        out = {}
        for name, kind in tape.KINDS.items():
            p_ = Path(root) / "tape" / kind / f"{sym}.parquet"
            if name == "funding" and not p_.exists():
                out[name] = pd.DataFrame(dict(funding_interval_hours=pd.Series(dtype=float), last_funding_rate=pd.Series(dtype=float)), index=pd.DatetimeIndex([], tz="UTC", name="ts"))
                continue
            df = duckdb.execute(f"select * exclude (ts_unit) from read_parquet('{p_}') where ts >= ? and ts < ? order by ts", [lo_, hi_]).df()
            out[name] = df.set_index(pd.DatetimeIndex(df.pop("ts")).tz_convert("UTC"))
        return out


def with_funding_strict(kl: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    """`signals.with_funding` ile aynı, ama bar kapanışı T'de YALNIZCA ts < T olaylar bilinen sayılır (T damgalı olay hariç; ön kayıt 1.1 katı sürüm)."""
    f = (funding.last_funding_rate / funding.funding_interval_hours).sort_index()
    f.index = f.index.round("1min")
    f = f[~f.index.duplicated()]
    t = kl.index + pd.Timedelta("1h") - pd.Timedelta("1min")
    return kl.assign(fund_hr=f.reindex(f.index.union(t)).ffill().reindex(t).to_numpy())


def load_symbols(syms: list[str]) -> tuple[dict, dict, dict]:
    """({sym: kl + fund_hr}, {sym: kl + fund_hr (katı)}, {sym: funding olayları}); iki kök birleştirilir, sembol yalnızca bulunduğu kökten."""
    kls, kls_s, fund = {}, {}, {}
    for s in syms:
        parts = []
        for r, lo, hi in ROOTS:
            if (Path(r) / "tape" / "klines" / f"{s}.parquet").exists():
                part = _load_safe(r, s, lo, hi)
                if len(part["klines"]):
                    parts.append(part)
        if not parts:
            continue
        d = {k: pd.concat([p[k] for p in parts]).sort_index() for k in ("klines", "funding")}
        for k in d:
            d[k] = d[k][~d[k].index.duplicated()]
        cols = ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_quote_volume"]
        kls[s], kls_s[s], fund[s] = sg.with_funding(d["klines"][cols], d["funding"]), with_funding_strict(d["klines"][cols], d["funding"]), d["funding"]
    return kls, kls_s, fund


def members(top_n: int = 20) -> pd.DataFrame:
    """Aylık üyelik (month, sym), rank ≤ top_n (`audit_fix.members` ile aynı kural)."""
    from kepler import tape
    parts = [tape.membership(r)[lambda d: d["rank"] <= top_n] for r in ("/data/pre2022", "/data")]
    df = pd.concat(parts, ignore_index=True)
    return df[df.month >= "2020-03"].drop_duplicates(["month", "sym"])[["month", "sym"]]


def member_mask(index: pd.DatetimeIndex, columns, mem: pd.DataFrame) -> pd.DataFrame:
    mask = pd.DataFrame(False, index=index, columns=columns)
    mon = index.strftime("%Y-%m")
    for m, g in mem.groupby("month"):
        mask.loc[mon == m, [c for c in g.sym if c in mask.columns]] = True
    return mask


# ------------------------------------------------------------------ tahminler
def forecasts(kls: dict, mem: pd.DataFrame | None = None, p: en.Params | None = None) -> tuple[pd.DataFrame, dict, dict]:
    """(close, st, {uzman: F}) + 'ensemble' (ev1_plus_new birleşik F, referans). mem verilirse st['active'] üyelikle kesilir (dinamik evren)."""
    p = p or en.Params()
    close, _ = en.panel(kls)
    st = en.market_state(close, kls, p)
    if mem is not None:
        st = dict(st, active=st["active"] & member_mask(close.index, close.columns, mem))
    F = {n: en.REG[n].forecast(close, st, p) for n in EXPERTS}
    pe = en.Params(**en.PRESETS["ev1_plus_new"])
    F["ensemble"] = en.combine(tuple(F[n] for n in en.composition(pe)[0]), st, pe)
    return close, st, F


# ------------------------------------------------------------------ ileri getiri
def _ns(idx) -> np.ndarray:
    return pd.DatetimeIndex(idx).as_unit("ns").asi8


def _up(a: np.ndarray, k: int) -> np.ndarray:
    """a[t + k] (sondaki k satır NaN)."""
    out = np.full(a.shape, np.nan)
    out[:-k] = a[k:]
    return out


def _cumfund(f: pd.Series, ext: pd.DatetimeIndex) -> np.ndarray:
    """Günlük 00:00'a kadarki (dahil) funding oranları kümülatif toplamı; ilk olaydan önceki gün ve funding'i olmayan sembol NaN."""
    if not len(f):
        return np.full(len(ext), np.nan)
    f = f.sort_index()
    ts, cum = _ns(f.index.round("1min")), np.cumsum(f.to_numpy(float))
    pos = np.searchsorted(ts, _ns(ext), side="right")
    v = np.where(pos > 0, cum[np.maximum(pos - 1, 0)], 0.0)
    v[_ns(ext) < _ns(pd.DatetimeIndex([f.index[0].normalize()]))[0]] = np.nan
    return v


def fwd_panels(kls: dict, funding: dict, index: pd.DatetimeIndex, sigma: pd.DataFrame, horizons=sx.HORIZONS, data_end: pd.Timestamp = DATA_END) -> dict:
    """{h: dict(Y, Ytot, term)} [index x sembol] numpy. Giriş = d+1 günü ilk saatlik bar AÇILIŞI, çıkış = d+1+h günü; veri çıkıştan önce bitmişse (delist/kesim) çıkış = son barın kapanışı (term=True);
    çıkış günü data_end'den sonraysa NaN. Ytot: funding dahil (long öder): ödeme (t₀, t₁] olayları, t₀ = giriş açılışı (00:00; dolumdaki damgalı olayı yeni pozisyon ödemez)."""
    cols = list(sigma.columns)
    ext = pd.date_range(index[0], index[-1] + pd.Timedelta(days=max(horizons) + 3), freq="1D", tz="UTC")
    O = np.stack([kls[s].open.resample("1D").first().reindex(ext).to_numpy(float) for s in cols], axis=1)
    last_ns = np.array([_ns(pd.DatetimeIndex([kls[s].index[-1].normalize()]))[0] for s in cols])
    last_px = np.array([float(kls[s].close.iloc[-1]) for s in cols])
    CF = np.stack([_cumfund(funding[s].last_funding_rate, ext) for s in cols], axis=1)
    sig = sigma.reindex(ext).to_numpy(float)
    ext_ns, end_ns = _ns(ext), _ns(pd.DatetimeIndex([data_end]))[0]
    entry, rows = _up(O, 1), ext.get_indexer(index)
    out = {}
    for h in horizons:
        ex = _up(O, 1 + h)
        exit_ns = (ext_ns + (1 + h) * 86_400_000_000_000)[:, None]
        gone = np.isnan(ex) & (exit_ns > last_ns[None, :]) & (exit_ns <= end_ns)
        ok = exit_ns <= end_ns
        with np.errstate(divide="ignore", invalid="ignore"):
            R = np.where(ok, np.log(np.where(gone, last_px[None, :], ex) / entry), np.nan)
            scale = sig * np.sqrt(h / 365.0)
            fsum = _up(CF, 1 + h) - _up(CF, 1)
            out[h] = dict(Y=(R / scale)[rows], Ytot=((R - fsum) / scale)[rows], term=(gone & ok)[rows])
    return out


# ------------------------------------------------------------------ panel
def build_panel(kls: dict, funding: dict, kls_s: dict, mem: pd.DataFrame | None) -> dict:
    close, st, F = forecasts(kls, mem)
    idx = close.index[(close.index >= DEC_START) & (close.index <= DEC_LAST)]
    cols = list(close.columns)
    fw = fwd_panels(kls, funding, idx, st["sigma"])
    act = st["active"].reindex(idx)
    Fs = {}
    if kls_s is not None:  # katı funding: yalnızca φ'ye bağlı iki uzman yeniden hesaplanır
        _, st_s, F_s = forecasts(kls_s, mem)
        Fs = {n: F_s[n].reindex(idx) for n in ("carry", "fundcrowd")}
    from kepler import robust  # geç import: hakem zinciri (nautilus) yalnızca rejim etiketi için
    reg = robust.regime(close["BTCUSDT"]).reindex(idx)
    return dict(index=idx, columns=cols, act=act.to_numpy(bool), F={k: v.reindex(idx)[cols].to_numpy(float) for k, v in F.items()}, Fstrict={k: v[cols].to_numpy(float) for k, v in Fs.items()},
                Y={h: v["Y"] for h, v in fw.items()}, Ytot={h: v["Ytot"] for h, v in fw.items()}, term={h: v["term"] for h, v in fw.items()}, regime=reg.fillna("na").to_numpy(str), sigma=st["sigma"].reindex(idx)[cols].to_numpy(float))


def save_panel(P: dict, path: Path):
    flat = dict(index=_ns(P["index"]), columns=np.array(P["columns"]), act=P["act"], regime=P["regime"], sigma=P["sigma"])
    for k in ("F", "Fstrict"):
        flat.update({f"{k}__{n}": v for n, v in P[k].items()})
    for k in ("Y", "Ytot", "term"):
        flat.update({f"{k}__{h}": v for h, v in P[k].items()})
    np.savez_compressed(path, **flat)


def load_panel(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    g = lambda pre, cast=lambda x: x: {k.split("__", 1)[1]: cast(z[k]) for k in z.files if k.startswith(pre + "__")}  # noqa: E731
    return dict(index=pd.DatetimeIndex(z["index"], tz="UTC"), columns=list(z["columns"]), act=z["act"], regime=z["regime"], sigma=z["sigma"], F=g("F"), Fstrict=g("Fstrict"),
                Y={int(h): v for h, v in g("Y").items()}, Ytot={int(h): v for h, v in g("Ytot").items()}, term={int(h): v for h, v in g("term").items()})


def stage_panel(out: Path, top_n: int = 20):
    t0 = time.time()
    mem = members(top_n)
    syms = sorted(mem.sym.unique())
    kls, kls_s, fund = load_symbols(syms)
    syms = [s for s in syms if s in kls]
    out.mkdir(parents=True, exist_ok=True)
    P = build_panel(kls, fund, kls_s, mem)
    save_panel(P, out / "panel_dyn20.npz")
    print("dinamik panel", len(P["columns"]), "sembol", P["act"].sum(), "hücre", f"{time.time() - t0:.0f}s", flush=True)
    k9, k9s, f9 = {s: kls[s] for s in EXT9}, {s: kls_s[s] for s in EXT9}, {s: fund[s] for s in EXT9}
    P9 = build_panel(k9, f9, k9s, None)
    save_panel(P9, out / "panel_ext9.npz")
    print("karşılaştırma paneli", P9["act"].sum(), "hücre", f"{time.time() - t0:.0f}s")
    (out / "panel_meta.json").write_text(json.dumps(dict(n_symbols=len(syms), symbols=syms, n_cells=int(P["act"].sum()), seconds=time.time() - t0,
                                                         data_end=str(DATA_END), seal_start="2026-04-01"), indent=1))


# ------------------------------------------------------------------ analiz
def cell_ic(F, Y, kind: str, C, mask=None, min_n=sx.MIN_N_TS, min_cells=8):
    if kind == "ts":
        return sx.ic_ts(F, Y, C, mask, min_n)
    est, boots, _ = sx.ic_xs(F, Y, C, mask, min_cells)
    return est, boots


def period_masks(index: pd.DatetimeIndex) -> dict:
    return {k: ((index >= pd.Timestamp(a, tz="UTC")) & (index <= pd.Timestamp(b, tz="UTC"))) for k, (a, b) in PERIODS.items()}


def analyze(P: dict, B: int = 2000, seed: int = 0, P9: dict | None = None, verbose: bool = True) -> dict:
    index, act = P["index"], P["act"]
    T, S = act.shape
    rows = []  # deneme defteri (her test/ölçüm bir satır)

    def reg(kind, exp, spec, res):
        rows.append(dict(kind=kind, expert=exp, spec=spec, result=res))
    Cs = {L: sx.block_counts(T, B, L, seed) for L in sorted({max(20, 2 * h) for h in sx.HORIZONS})}
    Fm = {n: np.where(act, P["F"][n], np.nan) for n in EXPERTS + ["ensemble"]}
    # ---- aile: 9 uzman x 6 ufuk x 2 tür
    fam = {}
    for n in EXPERTS:
        for h in sx.HORIZONS:
            C = Cs[max(20, 2 * h)]
            for kind in ("ts", "xs"):
                est, boots = cell_ic(Fm[n], P["Y"][h], kind, C)
                r = sx.summarize(est, boots, Z_CORR)
                fam[(n, kind, h)] = r
        if verbose:
            print("aile", n, flush=True)
    keys = list(fam)
    praw = np.array([fam[k]["p"] for k in keys])
    padj, q = sx.holm(np.where(np.isfinite(praw), praw, 1.0)), sx.bh(np.where(np.isfinite(praw), praw, 1.0))
    for k, a, b in zip(keys, padj, q):
        fam[k].update(p_holm=float(a), q_bh=float(b))
        reg("family", k[0], dict(ic=k[1], h=k[2], target="Y_price", family=N_FAMILY), fam[k])
    # ---- uzman kararları
    pm = period_masks(index)
    per_ic, cards = {}, {}
    for n in EXPERTS:
        cells = {k: v for k, v in fam.items() if k[0] == n and np.isfinite(v["z"])}
        pos = {k: v for k, v in cells.items() if v["ic"] > 0}
        best = max(pos, key=lambda k: pos[k]["z"]) if pos else None
        worst = min(cells, key=lambda k: cells[k]["z"]) if cells else None
        card = dict(best=None if best is None else dict(type=best[1], h=best[2], **fam[best]), worst=None if worst is None else dict(type=worst[1], h=worst[2], **fam[worst]))
        if best is not None:
            _, kind, h = best
            sub = {}
            for pn, m in pm.items():
                est, boots = cell_ic(Fm[n], P["Y"][h], kind, Cs[max(20, 2 * h)], mask=m[:, None] & np.ones((1, S), bool), min_n=60)
                sub[pn] = sx.summarize(est, boots)
                reg("criterion_period", n, dict(ic=kind, h=h, period=pn), sub[pn])
            card["periods"] = sub
            card["n_pos_periods"] = int(sum(v["ic"] > 0 for v in sub.values()))
        card["ic_pass"] = bool(best is not None and fam[best]["p_holm"] <= 0.05 and card.get("n_pos_periods", 0) >= 2)
        card["neg_sig"] = bool(worst is not None and fam[worst]["ic"] < 0 and fam[worst]["p_holm"] <= 0.05)
        cards[n] = card
    out = dict(family={f"{k[0]}|{k[1]}|{k[2]}": v for k, v in fam.items()}, cards=cards, n_cells=int(act.sum()), n_family=N_FAMILY, z_corr=Z_CORR)
    # ---- betimsel: kalibrasyon, sönme, koşullu, fazlalık, ters işaret, duyarlılık
    valid_cell = act
    A = {n: np.nan_to_num(Fm[n]) for n in EXPERTS}
    corr = sx.cell_spearman(A, valid_cell)
    corr_x = sx.daily_xs_corr(A, valid_cell)
    cl = sx.cluster(corr, 0.5)
    out.update(corr=corr.round(4).to_dict(), corr_xs=corr_x.round(4).to_dict(), clusters=cl)
    sgn = {n: np.sign(np.nan_to_num(Fm[n])) for n in EXPERTS}
    desc = {}
    for n in EXPERTS:
        d = {}
        card = cards[n]
        a_ = np.abs(Fm[n][act])
        d["fire_rate"], d["mean_absF"], d["n_cells"] = float((a_ > 0).mean()), float(a_.mean()), int(act.sum())
        if card["best"] is not None:
            kind, h = card["best"]["type"], card["best"]["h"]
            C = Cs[max(20, 2 * h)]
            Y, F = P["Y"][h], Fm[n]
            ok = np.isfinite(F) & np.isfinite(Y)
            bid, nb = sx.buckets(F, ok, 5)
            cal = sx.bucket_means(np.where(ok, Y, 0.0), bid, max(nb, 1), C) if nb else None
            absF = np.where(ok & (F != 0), np.abs(F), np.nan)
            ok2 = np.isfinite(absF)
            bid2, nb2 = sx.buckets(absF, ok2, 5)
            mag = sx.bucket_means(np.where(ok2, np.sign(F) * Y, 0.0), bid2, max(nb2, 1), C) if nb2 else None
            d["calibration"], d["magnitude"] = cal, mag
            reg("descriptive", n, dict(what="calibration_F", h=h), cal or {})
            reg("descriptive", n, dict(what="calibration_absF", h=h), mag or {})
            yr = {}
            for yv in range(2020, 2027):
                m = (index.year == yv)[:, None] & np.ones((1, S), bool)
                est, boots = cell_ic(F, Y, kind, C, mask=m, min_n=60)
                yr[str(yv)] = sx.summarize(est, boots)
                reg("descriptive", n, dict(what="year", year=yv, ic=kind, h=h), yr[str(yv)])
            d["years"] = yr
            reg_ic = {}
            for rg in ("bull", "bear", "range"):
                m = (P["regime"] == rg)[:, None] & np.ones((1, S), bool)
                est, boots = cell_ic(F, Y, kind, C, mask=m, min_n=60, min_cells=5)
                reg_ic[rg] = dict(n_days=int((P["regime"] == rg).sum()), **sx.summarize(est, boots))
                reg("descriptive", n, dict(what="regime", regime=rg, ic=kind, h=h), reg_ic[rg])
            d["regime"] = reg_ic
            others = [o for o in EXPERTS if o != n]
            agree = sum((sgn[o] == sgn[n]) & (sgn[n] != 0) for o in others)
            ag = {}
            for lab, m in (("<=2", agree <= 2), ("3-4", (agree >= 3) & (agree <= 4)), (">=5", agree >= 5)):
                est, boots = cell_ic(F, Y, kind, C, mask=m & (sgn[n] != 0), min_n=60, min_cells=5)
                ag[lab] = dict(n_cells=int((m & (sgn[n] != 0) & ok).sum()), **sx.summarize(est, boots))
                reg("descriptive", n, dict(what="agreement", bucket=lab, ic=kind, h=h), ag[lab])
            d["agreement"] = ag
            tot = sx.summarize(*cell_ic(F, P["Ytot"][h], kind, C))
            reg("descriptive", n, dict(what="total_return_target", ic=kind, h=h), tot)
            d["total_return"] = tot
            nt = ~P["term"][h]
            ex = sx.summarize(*cell_ic(F, np.where(nt, Y, np.nan), kind, C))
            reg("descriptive", n, dict(what="exclude_terminal", ic=kind, h=h), ex)
            d["exclude_terminal"] = ex
            d["terminal_share"] = float(P["term"][h][ok].mean()) if ok.any() else float("nan")
        # ters işaret / kopya
        r_oth = {o: float(corr.loc[n, o]) for o in EXPERTS if o != n}
        mx = max(r_oth, key=lambda o: abs(r_oth[o]))
        d["max_corr_other"] = dict(expert=mx, rho=r_oth[mx])
        d["copy"] = bool(abs(r_oth[mx]) >= 0.5)
        if card["worst"] is not None and cards[n]["neg_sig"] and n != "trend":
            _, kind, h = (n, card["worst"]["type"], card["worst"]["h"])
            rk = lambda a: pd.DataFrame(np.where(act, a, np.nan)).rank().to_numpy()  # noqa: E731
            x, t_ = rk(Fm[n]), rk(Fm["trend"])
            v = np.isfinite(x) & np.isfinite(t_)
            beta = np.sum((x[v] - x[v].mean()) * (t_[v] - t_[v].mean())) / np.sum((t_[v] - t_[v].mean()) ** 2)
            resid = np.where(v, (x - x[v].mean()) - beta * (t_ - t_[v].mean()), np.nan)
            est, boots = cell_ic(-resid, P["Y"][h], kind, Cs[max(20, 2 * h)])
            d["flip_orth_trend"] = dict(h=h, type=kind, **sx.summarize(est, boots))
            reg("descriptive", n, dict(what="flip_orth_trend", h=h, ic=kind), d["flip_orth_trend"])
        desc[n] = d
    out["desc"] = desc
    # ---- karar
    cluster_pass = {}
    for n in EXPERTS:
        c, d = cards[n], desc[n]
        if c["ic_pass"]:
            dec = "TUT" if H_TIER[n] >= 1 else "YENİDEN KUR"
        elif c["neg_sig"]:
            dec = "AT" if d["copy"] else "YENİDEN KUR"
        else:
            dec = "YENİDEN KUR" if H_TIER[n] == 2 else "AT"
        c["decision"], c["H"] = dec, H_TIER[n]
        cluster_pass.setdefault(cl[n], []).append(n if c["ic_pass"] else None)
    out["n_clusters"] = len(set(cl.values()))
    out["n_clusters_with_ic_pass"] = sum(1 for v in cluster_pass.values() if any(v))
    # ---- ensemble referansı (aile dışı) ve funding duyarlılığı (katı)
    refrows = {}
    for kind in ("ts", "xs"):
        for h in sx.HORIZONS:
            est, boots = cell_ic(Fm["ensemble"], P["Y"][h], kind, Cs[max(20, 2 * h)])
            refrows[f"{kind}|{h}"] = sx.summarize(est, boots)
            reg("descriptive", "ensemble", dict(what="reference", ic=kind, h=h), refrows[f"{kind}|{h}"])
    out["ensemble_ref"] = refrows
    strict = {}
    for n in P["Fstrict"]:
        Fs_ = np.where(act, P["Fstrict"][n], np.nan)
        for kind in ("ts", "xs"):
            for h in sx.HORIZONS:
                est = cell_ic(Fs_, P["Y"][h], kind, None)[0]
                strict[f"{n}|{kind}|{h}"] = dict(strict=est, inclusive=fam[(n, kind, h)]["ic"])
    out["funding_strict"] = strict
    if P9 is not None:  # karşılaştırma evreni (yalnızca nokta IC; p/karar yok)
        a9 = P9["act"]
        cmp_ = {}
        for n in EXPERTS:
            for kind in ("ts", "xs"):
                for h in sx.HORIZONS:
                    cmp_[f"{n}|{kind}|{h}"] = cell_ic(np.where(a9, P9["F"][n], np.nan), P9["Y"][h], kind, None, min_cells=5)[0]
        out["ext9"] = cmp_
    out["n_trials"] = dict(family=sum(r["kind"] == "family" for r in rows), criterion_period=sum(r["kind"] == "criterion_period" for r in rows), descriptive=sum(r["kind"] == "descriptive" for r in rows), total=len(rows))
    return dict(result=out, ledger=rows)


def clean(o):
    """JSON'a güvenli: numpy → python, NaN/inf → None (JSONL sorgulanabilir kalsın)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def write_ledger(rows: list, path: Path, base_n: int, code_hash: str, data_hash: str):
    """Araştırma defteri: append-only JSONL, satır başına bir test/ölçüm. `ledger.record` hakem dışı kaynağı reddeder (ve `ledger/*` ajan tarafından yazılmaz): aynı alanlar, source='diagnostic'.
    trial = bu işteki sıra; global sayaç = base_n + trial."""
    path.parent.mkdir(parents=True, exist_ok=True)
    t = time.time()
    with path.open("a") as f:
        for i, r in enumerate(rows, 1):
            cfg = clean(dict(kind=r["kind"], expert=r["expert"], spec=r["spec"]))
            row = dict(trial=i, global_trial=base_n + i, time=t, source="diagnostic", hypothesis="reports/preregistration/signal_diagnostics.md", config=cfg,
                       config_hash=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(), code_hash=code_hash, data_hash=data_hash, result=clean(r["result"]), score=None)
            f.write(json.dumps(row, allow_nan=False) + "\n")


def stage_analyze(out: Path, B: int):
    t0 = time.time()
    P, P9 = load_panel(out / "panel_dyn20.npz"), load_panel(out / "panel_ext9.npz")
    res = analyze(P, B=B, P9=P9)
    ch = hashlib.sha256((Path(__file__).read_text() + Path(sx.__file__).read_text()).encode()).hexdigest()
    dh = hashlib.sha256((out / "panel_dyn20.npz").read_bytes()).hexdigest()
    (out / "ledger_signal_diag.jsonl").unlink(missing_ok=True)
    write_ledger(res["ledger"], out / "ledger_signal_diag.jsonl", 4775, ch, dh)
    res["result"].update(code_hash=ch, data_hash=dh, seconds=time.time() - t0, B=B)
    (out / "results.json").write_text(json.dumps(clean(res["result"]), indent=1, allow_nan=False))
    print("tamam", res["result"]["n_trials"], f"{time.time() - t0:.0f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["panel", "analyze"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--b", type=int, default=2000)
    a = ap.parse_args()
    {"panel": lambda: stage_panel(Path(a.out)), "analyze": lambda: stage_analyze(Path(a.out), a.b)}[a.stage]()


if __name__ == "__main__":
    main()
