"""Trade denetimi düzeltmeleri, VERİ AŞAMALARI (Modal'de koşar; LLM yok, deterministik). Rapor/PDF aşaması: scripts/trade_audit_report.py (+ scripts/audit_fix_report.py).

  modal run modal_app.py --cmd "python scripts/audit_fix.py --stage causal --out /data/audit_fix/causal"
  Aşamalar: causal (0.1), mexc (0.3), null (1.2), cf (2.6), bench (2.5), surv (2.9); hepsi ev1_plus_new, sermaye 1 000, fee 10 + slip 2.
Ölçüm düzeltmesidir: strateji, parametre, eşik, ağırlık değişmez ve aranmaz. Çıktılar `reports/trade_audit_data/fix/` altına indirilir. Mühürlü dönem (≥ 2026-04-01) yüklenmez (`tape.load` mühür sınırını kodla zorlar)."""
import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402  (load, spec, utc, data_of, D, EXT, MAIN)

from nautilus_trader.backtest import BacktestEngineConfig as _BEC  # noqa: E402
from nautilus_trader.config import LoggerConfig  # noqa: E402

from kepler import audit  # noqa: E402
from kepler import ensemble as en  # noqa: E402
from kepler import evaluate as ev  # noqa: E402
from kepler import portfolio, referee, report, robust, tape  # noqa: E402

# Nautilus rc5 `BacktestEngineConfig(bypass_logging=True)` bayrağını yok sayıyor (INFO günlükleri hakem koşusunu saatlerce yavaşlatır). referee.py'ye DOKUNMADAN, bu işlemde motor yapılandırmasını
# günlüksüz kurarız; sonuç değişmez (taban koşu 790,5162 ile birebir doğrulanır, stage_base).
referee.BacktestEngineConfig = lambda **kw: _BEC(**{**kw, "logging": LoggerConfig(bypass_logging=True)})

CAP = 1000.0
PRESET = "ev1_plus_new"
ROOTS = [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)]


def params(preset: str = PRESET) -> en.Params:
    return en.Params(**en.PRESETS[preset])


def load_all(cap: float = CAP):
    E.load(E.EXT, ROOTS, cap=cap)
    return {s: d["kl"] for s, d in E.data_of(E.EXT).items()}


# ---------------------------------------------------------------- 0.1 nedensellik
def parts(kls: dict, p: en.Params, cap: float, mutant: str = "") -> dict:
    """Karar zincirinin ara serileri (günlük): uzman tahminleri, tahmin ölçeği m_d, toplam F, oynaklık, funding, rejim etiketi, hedef notional. `mutant` yalnızca POZİTİF KONTROL için:
    bilinçli gelecek sızıntısı ekler (test gerçekten yakalıyor mu?). '' = gerçek zincir."""
    close, _ = en.panel(kls)
    st = en.market_state(close, kls, p)
    if mutant == "sigma_future":  # σ'yı 5 gün ileriye kaydır (gelecek oynaklığı)
        st = dict(st, sigma=st["sigma"].shift(-5).ffill())
    es = en.experts(close, st, p)
    names, w = en.composition(p)
    raw = sum(wi * e.fillna(0.0) for wi, e in zip(w, es)).where(st["active"])
    ab = raw.abs()
    tot = pd.Series([math.fsum(r[~np.isnan(r)]) for r in ab.to_numpy()], index=ab.index)
    m = tot.cumsum() / st["active"].sum(axis=1).cumsum()
    if mutant == "m_fullsample":  # tahmin ölçeği tüm örneklem ortalamasıyla (genişleyen değil)
        m = pd.Series(tot.sum() / st["active"].to_numpy().sum(), index=ab.index)
        warm = st["active"].any(axis=1).cumsum() >= p.warm
        f = (raw.mul(0.5 / m.where(m > 0), axis=0)).clip(-1, 1).where(warm, 0.0).where(st["active"])
    else:
        f = en.combine(es, st, p)
    reg = robust.regime(close["BTCUSDT"])
    if mutant == "regime_future":  # rejim etiketi bir gün İLERİ (d+1 etiketi d'ye yazılır)
        reg = reg.shift(-1)
    n = portfolio.size(f, st, cap, p)
    out = dict(m=m, F=f, sigma=st["sigma"], phi=st["phi"], dvol=st["dvol"], tbr=st["tbr"], n=n)
    out.update({f"E_{nm}": e for nm, e in zip(names, es)})
    out["regime"] = reg.to_frame("regime")
    return {k: (v.to_frame(k) if isinstance(v, pd.Series) else v) for k, v in out.items()}


def prefix_diff(a: dict, b: dict, upto: pd.Timestamp) -> dict:
    """İki `parts` çıktısının `upto`'dan ÖNCEKİ (kesilmiş veride tam gün) satırlarında fark: en büyük mutlak fark ve NaN deseni uyuşmazlığı. Kesilmiş (b) ve tam (a) aynı geçmişi vermeli."""
    out = {}
    for k in a:
        x = a[k][a[k].index < upto]
        y = b[k].reindex(index=x.index, columns=x.columns, fill_value=0.0 if k == "n" else np.nan)  # kesik veride henüz verisi olmayan sembol sütunu yok: tam serideki karşılığı 0 (n) / NaN
        if k == "regime":
            out[k] = dict(maxdiff=float((x.regime.fillna("na") != y.regime.fillna("na")).sum()), nan_mismatch=0)
            continue
        xv, yv = x.to_numpy(float), y.to_numpy(float)
        nan_mm = int((np.isnan(xv) != np.isnan(yv)).sum())
        both = ~np.isnan(xv) & ~np.isnan(yv)
        out[k] = dict(maxdiff=float(np.abs(xv[both] - yv[both]).max()) if both.any() else 0.0, nan_mismatch=nan_mm)
    return out


def cut_days(kls: dict, n_cuts: int, seed: int = 0) -> list:
    """Her ay için bir kesim günü (UTC 00:00; deterministik tohum): ilk 200 günlük ısınmadan sonra."""
    idx = pd.DatetimeIndex(sorted(set().union(*[d.index for d in kls.values()])))
    days = idx.normalize().unique()
    days = days[days >= days[0] + pd.Timedelta(days=200)]
    rng = np.random.default_rng(seed)
    months = pd.Series(days.tz_localize(None).to_period("M")).drop_duplicates()
    picks = [days[(pd.Series(days.tz_localize(None).to_period("M")) == m).to_numpy()][rng.integers(0, int(((pd.Series(days.tz_localize(None).to_period("M")) == m)).sum()))] for m in months]
    return sorted(picks)[:n_cuts] if n_cuts < len(picks) else sorted(picks)


_G: dict = {}


def _cut_job(a):
    day, mutant = a
    kls, p = _G["kls"], _G["p"]
    full = _G["full"][mutant]
    cut = {s: kl[kl.index < day] for s, kl in kls.items()}
    cut = {s: kl for s, kl in cut.items() if len(kl)}
    res = prefix_diff(full, parts(cut, p, CAP, mutant), day)
    bad = {k: v for k, v in res.items() if v["maxdiff"] > 1e-12 or v["nan_mismatch"]}
    return str(day.date()), res, bad, None


def stage_causal(out: Path, n_cuts: int, procs: int):
    t0 = time.time()
    kls = load_all()
    p = params()
    book = en.make_book(CAP, p)
    # (a) projenin kendi denetimi: ev1_plus_new kitabı için audit.check_causal_book (16 kesim noktası: veri bozma + kesme)
    bad_book = audit.check_causal_book(book, kls)
    print("check_causal_book kötü kesimler:", bad_book, f"({time.time() - t0:.0f}s)", flush=True)
    # (b) pozitif kontrol: bilinçli sızıntılı kitap bu denetimde yakalanıyor mu (denetimin gücü)
    _G.update(kls=kls, p=p, full={m: parts(kls, p, CAP, m) for m in ("", "m_fullsample", "sigma_future", "regime_future")})
    # (c) önek-değişmezlik: t gününe kadar kesilmiş veri vs tam veri; ara seriler ve hedef pozisyon aynı olmalı
    days = cut_days(kls, n_cuts)
    results = {}
    for mutant in ("", "m_fullsample", "sigma_future", "regime_future"):
        with ProcessPoolExecutor(procs) as ex:
            rows = list(ex.map(_cut_job, [(d, mutant) for d in days]))
        worst = {}
        for day, res, bad, last in rows:
            for k, v in res.items():
                w = worst.setdefault(k, dict(maxdiff=0.0, nan_mismatch=0, n_bad_cuts=0))
                w["maxdiff"] = max(w["maxdiff"], v["maxdiff"])
                w["nan_mismatch"] += v["nan_mismatch"]
                w["n_bad_cuts"] += int(k in bad)
        results[mutant or "real"] = dict(n_cuts=len(rows), worst=worst, bad_cut_days=[r[0] for r in rows if r[2]])
        print(mutant or "real", {k: (round(v["maxdiff"], 12), v["n_bad_cuts"]) for k, v in worst.items()}, f"({time.time() - t0:.0f}s)", flush=True)
    # (d) mutant kitaplarının audit.check_causal_book'ta yakalanması (denetim gücü)
    ctrl = {}
    for mutant in ("m_fullsample", "sigma_future"):
        def mbook(kl_, mutant=mutant):
            pr = parts(kl_, p, CAP, mutant)
            n_ = pr["n"]
            return {s: pd.DataFrame(dict(target=en.place(kl, n_[s]), stop=np.nan), index=kl.index) for s, kl in kl_.items()}
        ctrl[mutant] = audit.check_causal_book(mbook, kls, fracs=tuple(np.linspace(0.2, 0.9, 6)))
        print("check_causal_book mutant", mutant, ctrl[mutant], flush=True)
    out.mkdir(parents=True, exist_ok=True)
    (out / "causal.json").write_text(json.dumps(dict(check_causal_book_bad=bad_book, check_causal_book_fracs=16, prefix=results, mutant_check_causal_book=ctrl,
                                                      cut_days=[str(d.date()) for d in days], window=E.MAIN, preset=PRESET, cap=CAP, seconds=time.time() - t0), indent=1, default=str))
    print("tamam", f"{time.time() - t0:.0f}s")


# ---------------------------------------------------------------- 0.3 hedef borsa kuralları (MEXC) + yuvarlama
RULES_PATH = Path(__file__).resolve().parent.parent / "reports" / "trade_audit_data" / "fix" / "mexc_rules.json"
OHLC = ("open", "high", "low", "close")


def mexc_rules() -> dict:
    """reports/trade_audit_data/fix/mexc_rules.json: MEXC `contract/detail` çıktısından (fetched_utc kayıtlı) 9 sembolün kuralları."""
    return json.loads(RULES_PATH.read_text())["symbols"]


def contract_view(D: dict, rules: dict) -> dict:
    """Her sembolü MEXC SÖZLEŞME biriminde yeniden temsil eder: fiyat x contractSize (sözleşme başına USDT), miktar = sözleşme sayısı, lot adımı = volUnit sözleşme, tick = priceUnit x contractSize.
    Hakemin `quantize(step)` adımı yalnızca 10'un negatif/sıfır üslü adımlarını doğru yuvarlar (DOGE adımı 100 DOGE); sözleşme birimi bunu hakemi DEĞİŞTİRMEDEN aşar. notional = qty x px, funding = -pos x mark x oran
    ve PnL birimden bağımsızdır. Dönen fills'te qty sözleşme, px sözleşme fiyatıdır: baz birime dönüş qty x cs, px / cs."""
    out = {}
    for s, d in D.items():
        r = rules[s]
        cs = Decimal(str(r["contractSize"]))
        k = float(cs)
        kl = d["kl"].copy()
        for c in OHLC:
            kl[c] = kl[c] * k
        kl["volume"] = kl["volume"] / k
        mk = None if d.get("mark") is None else d["mark"].assign(**{c: d["mark"][c] * k for c in OHLC if c in d["mark"]})
        out[s] = dict(d, kl=kl, mark=mk, tick=format((Decimal(str(r["priceUnit"])) * cs).normalize(), "f"), step=format(Decimal(str(r["volUnit"])).normalize(), "f"), cs=k)  # normalize: "0.00100" gibi artık sıfırlı tik, hassasiyeti (5) tik (0,001) ile uyumsuz kılar ve Nautilus eşleştirme motoru uyuşmayan fiyattaki emri SESSİZCE doldurmaz (n_rejected sayılmaz)
    return out


def replay_orders(kl: pd.DataFrame, target: pd.Series, step: str, tick: str, min_notional: float = 0.0) -> pd.DataFrame:
    """Hakemin hedef→emir kuralının (referee.Adapter.on_bar) birebir yeniden oynatımı: her hedef DEĞİŞİMİ bir emir niyetidir; miktar = floor(|hedef| / px / adım) x yön, delta = want - mevcut,
    azaltma değilse ve |delta| x px < min_notional ya da delta = 0 ise emir GÖNDERİLMEZ (hakemde reddedilen sayılmaz: `n_rejected` bu yüzden 0 kalır). Dönüş: niyet başına satır
    (ts, tgt, px, ideal [= tgt/px - önceki gerçek poz], want, pos_before, delta, sent, reason). Doğrulama: gönderilen emirler = hakem dolumları (stage_mexc)."""
    stp, pp = Decimal(step), max(0, -Decimal(tick).as_tuple().exponent)
    idx, opn = kl.index, kl.open.to_numpy(float)
    dec = target.dropna()
    slot = idx.searchsorted(dec.index + pd.Timedelta("1h"))
    last, pos, rows = 0.0, Decimal(0), []
    for ts, tgt, i in zip(dec.index, dec.to_numpy(float), slot):
        if i >= len(idx) or tgt == last:
            continue
        last = tgt
        d = int(tgt > 0) - int(tgt < 0)
        px = Decimal(f"{opn[i]:.{pp}f}")
        want = (Decimal(str(abs(tgt))) / px).quantize(stp, rounding=ROUND_DOWN) * d
        delta = want - pos
        reducing = want == 0 or (want * pos > 0 and abs(want) < abs(pos))
        sent = delta != 0 and (reducing or abs(delta) * px >= Decimal(str(min_notional)))
        reason = "sent" if sent else ("delta_zero" if delta == 0 else "min_notional")
        rows.append(dict(ts=idx[i], tgt=tgt, px=float(px), ideal=tgt / float(px) - float(pos), want=float(want), pos_before=float(pos), delta=float(delta), sent=sent, reason=reason))
        if sent:
            pos = want
    return pd.DataFrame(rows, columns=["ts", "tgt", "px", "ideal", "want", "pos_before", "delta", "sent", "reason"])


def sharpe_fixed(daily_net: pd.Series, cap: float) -> float:
    r = daily_net / cap
    return float(r.mean() / r.std(ddof=1) * np.sqrt(365))


def run_rules(cap: float, rules_mode: str, p: en.Params, kls: dict, D: dict) -> dict:
    """Bir hakem koşusu: rules_mode 'unrounded' (mevcut sezgisel adım/tik: sermayeye bağlı, 1e-3 mertebesi) ya da 'mexc' (gerçek MEXC kuralları, sözleşme birimi). Hedefler aynı kitaptan (sermaye cap)."""
    out = en.make_book(cap, p)(kls)
    if rules_mode == "mexc":
        data, sp = contract_view(E.data_of(E.EXT, D), mexc_rules()), replace(E.spec(cap=cap), min_notional=0.0)
    else:
        data = {s: dict(D[s], step=format(Decimal(10) ** (math.floor(math.log10(0.25 * cap / D[s]["kl"].close.max())) - 3), "f")) for s in E.EXT}
        sp = E.spec(cap=cap)
    res, win, _ = ev.run_book(out, data, sp, *E.utc(E.MAIN))
    pnl = report.book_pnl(win, res, sp)
    dn = pnl.resample("1D").sum()
    fills = res["fills"]
    rep = {}
    if rules_mode == "mexc":
        rows = []
        for s in E.EXT:
            r = replay_orders(data[s]["kl"], out[s].target, data[s]["step"], data[s]["tick"], sp.min_notional)
            r.insert(0, "sym", s)
            rows.append(r)
        rep = pd.concat(rows)
        sent = rep[rep.sent]
        cs = {s: data[s]["cs"] for s in E.EXT}
        # doğrulama: oynatılan emirler = hakem dolumları (sembol başına sayı ve toplam miktar)
        fmatch = {s: (int((sent.sym == s).sum()), int((fills.sym == s).sum()), float(abs(sent[sent.sym == s].delta).sum() - fills[fills.sym == s].qty.sum())) for s in E.EXT}
        bad = {k: v for k, v in fmatch.items() if v[0] != v[1] or abs(v[2]) > 1e-6}
        if bad:  # oynatılan emirler hakem dolumlarıyla birebir eşit olmalı; değilse hakem emri sessizce doldurmamıştır (ör. tik uyuşmazlığı)
            raise AssertionError(f"MEXC koşusunda emir niyeti ile dolum uyuşmuyor: {bad}")
        fills = fills.assign(qty_base=fills.qty * fills.sym.map(cs), px_base=fills.px / fills.sym.map(cs))
    return dict(cap=cap, mode=rules_mode, summary={k: float(v) for k, v in res["summary"].items()}, sharpe_fixed=sharpe_fixed(dn, cap), daily=dn, fills=fills, replay=rep,
                replay_check=fmatch if rules_mode == "mexc" else None, hourly_net_sum=float(pnl.sum()))


_GJ: dict = {}


def _rules_job(a):
    return run_rules(a[0], a[1], _GJ["p"], _GJ["kls"], _GJ["D"])


def stage_mexc(out: Path, procs: int, caps=(1000.0, 2500.0, 5000.0, 10000.0, 25000.0)):
    t0 = time.time()
    kls = load_all()
    p = params()
    _GJ.update(p=p, kls=kls, D=dict(E.D))
    jobs = [(c, m) for c in caps for m in ("unrounded", "mexc")]
    with ProcessPoolExecutor(procs) as ex:
        res = list(ex.map(_rules_job, jobs))
    out.mkdir(parents=True, exist_ok=True)
    table = []
    for r in res:
        tag = f"{int(r['cap'])}_{r['mode']}"
        r["daily"].to_csv(out / f"daily_{tag}.csv", header=["net"])
        if r["mode"] == "mexc":
            r["replay"].to_csv(out / f"replay_{tag}.csv", index=False)
            r["fills"].to_csv(out / f"fills_{tag}.csv", index=False)
        table.append(dict(cap=r["cap"], mode=r["mode"], sharpe_fixed=r["sharpe_fixed"], hourly_net_sum=r["hourly_net_sum"], replay_check=r["replay_check"], **r["summary"]))
    (out / "mexc_runs.json").write_text(json.dumps(dict(runs=table, rules_file=str(RULES_PATH.name), window=E.MAIN, preset=PRESET, seconds=time.time() - t0), indent=1, default=str))
    print("tamam", f"{time.time() - t0:.0f}s")


# ---------------------------------------------------------------- risk motoru ara adımları (atıf 2.1 ve oynaklık ayrıştırması 2.8 için)
def size_parts(f: pd.DataFrame, st: dict, capital: float, p) -> dict:
    """`portfolio.size`ın BİREBİR kopyası, ara adımları da döndürür (üretim kodu değişmez; `stage` içinde çıktı `portfolio.size` ile eşitlik olarak doğrulanır).
    unit  = K τ w IDM / σ (tam tahmindeki, |F| = 1 pozisyon); n0 = unit F (ölçeklenmemiş); n1 = portföy oynaklık tavanı sonrası; n2 = sembol ve brüt tavanlar sonrası (= tampon öncesi hedef);
    out = tampon sonrası tutulan hedef (= `portfolio.size` çıktısı); v = portföy oynaklık tahmini (yıllık, sermayeye oranlı); idm."""
    syms, ret, sig, act = list(f.columns), st["ret"].to_numpy(), st["sigma"].to_numpy(), st["active"].to_numpy()
    fv, shp = f.to_numpy(), f.shape
    out = np.zeros(shp)
    unit_a, n0_a, n1_a, n2_a = (np.full(shp, np.nan) for _ in range(4))
    v_a, idm_a, prev = np.full(shp[0], np.nan), np.full(shp[0], np.nan), np.zeros(len(syms))
    for d in range(shp[0]):
        a = act[d] & ~np.isnan(fv[d])
        tgt, u = np.zeros(len(syms)), np.full(len(syms), np.inf)
        idx = np.flatnonzero(a)
        if len(idx):
            m, s, fa = len(idx), sig[d, idx], fv[d, idx]
            if p.risk:
                lo = max(0, d - p.corr_days + 1)
                rho = pd.DataFrame(ret[lo:d + 1, idx]).corr(min_periods=30).fillna(1.0).to_numpy().copy()
                np.fill_diagonal(rho, 1.0)
                w = np.full(m, 1.0 / m)
                idm = min(2.5, 1.0 / np.sqrt(w @ np.clip(rho, 0, None) @ w))
                unit = capital * p.tau * w * idm / s
                n = unit * fa
                v = np.sqrt(max(n @ (np.outer(s, s) * rho) @ n, 0.0)) / capital
                unit_a[d, idx], n0_a[d, idx], v_a[d], idm_a[d] = unit, n.copy(), v, idm
                if v > p.tau:
                    n *= p.tau / v
            else:
                unit = np.full(m, capital / m)
                n = unit * fa
                unit_a[d, idx], n0_a[d, idx] = unit, n.copy()
            n1_a[d, idx] = n
            n = np.clip(n, -p.sym_cap * capital, p.sym_cap * capital)
            g = np.abs(n).sum()
            if g > p.gross_cap * capital:
                n *= p.gross_cap * capital / g
            n2_a[d, idx] = n
            tgt[idx], u[idx] = n, unit
        move = np.abs(tgt - prev) > np.where(np.isinf(u), np.inf, p.buffer * np.where(np.isinf(u), 0.0, u))
        prev = np.where(~a, 0.0, np.where(move, tgt, prev))
        out[d] = prev
    df = lambda x: pd.DataFrame(x, index=f.index, columns=syms)  # noqa: E731
    return dict(unit=df(unit_a), n0=df(n0_a), n1=df(n1_a), n2=df(n2_a), out=df(out), v=pd.Series(v_a, index=f.index), idm=pd.Series(idm_a, index=f.index))


def panels(kls: dict, p: en.Params, cap: float) -> dict[str, pd.DataFrame]:
    """Günlük paneller ([gün x sembol]): uzman tahminleri (E_<ad>), toplam F, tahmin ölçeği m, σ, funding φ, risk motoru ara adımları, günlük açılış/kapanış, rejim. portfolio.size ile eşitlik doğrulanır."""
    close, _ = en.panel(kls)
    st = en.market_state(close, kls, p)
    es = en.experts(close, st, p)
    names, _w = en.composition(p)
    f = en.combine(es, st, p)
    sp_ = size_parts(f, st, cap, p)
    ref = portfolio.size(f, st, cap, p)
    if not np.array_equal(ref.to_numpy(), sp_["out"].to_numpy()):
        raise AssertionError("size_parts çıktısı portfolio.size ile birebir eşit değil")
    raw = sum(w * e.fillna(0.0) for w, e in zip(en.composition(p)[1], es)).where(st["active"])
    m = pd.Series([math.fsum(r[~np.isnan(r)]) for r in raw.abs().to_numpy()], index=raw.index).cumsum() / st["active"].sum(axis=1).cumsum()
    opn = pd.DataFrame({s: kl.open.resample("1D").first() for s, kl in kls.items()}).reindex(close.index)
    out = {"F": f, "sigma": st["sigma"], "phi": st["phi"], "active": st["active"].astype(float), "close": close, "open": opn, **{f"E_{n}": e for n, e in zip(names, es)},
           **{k: v for k, v in sp_.items() if isinstance(v, pd.DataFrame)}}
    out["m"] = pd.DataFrame({s: m for s in close.columns})
    out["v"] = pd.DataFrame({s: sp_["v"] for s in close.columns})
    out["idm"] = pd.DataFrame({s: sp_["idm"] for s in close.columns})
    reg = robust.regime(close["BTCUSDT"])
    out["regime"] = pd.DataFrame({s: reg for s in close.columns}).replace({"bull": 1.0, "range": 0.0, "bear": -1.0})
    return out


def write_panels(pn: dict, path: Path):
    wide = pd.concat({k: v for k, v in pn.items()}, axis=1)
    wide.columns = [f"{a}.{b}" for a, b in wide.columns]
    wide.to_parquet(path, compression="zstd")


# ---------------------------------------------------------------- 1.1 deneme sayısı (defterden)
def stage_trials(out: Path):
    """Modal Volume'daki (/data) ve repodaki (/repo/ledger) tüm defter dosyalarını sayar: satır, kaynak (referee/screen), SHA256. Aynı SHA256 iki konumda ise bir kez sayılır.
    Kategori: smoke (`*_smoke` dizinleri: boru hattı denemesi, seçimde kullanılmaz), repo (repoda izlenen), modal_only (yalnızca Volume'da). Kural: MISSION 2 'her deneme deftere yazılır'."""
    import hashlib
    rows = []
    for loc, root in (("repo", Path("/repo/ledger")), ("volume", Path("/data"))):
        for f in sorted(root.rglob("*.jsonl")):
            rel = f.relative_to(root).as_posix()
            if loc == "volume" and (rel.startswith("audit_fix/") or rel.startswith("audit/")):
                continue
            recs = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
            rows.append(dict(loc=loc, path=rel, n=len(recs), sha=hashlib.sha256(f.read_bytes()).hexdigest(), sources={k: sum(1 for r in recs if r.get("source") == k) for k in ("referee", "screen")},
                             smoke="smoke" in rel))
    df = pd.DataFrame(rows)
    repo_sha = set(df[df["loc"] == "repo"].sha)
    vol = df[df["loc"] == "volume"].assign(in_repo=lambda d: d.sha.isin(repo_sha))
    summary = dict(repo_rows=int(df[df["loc"] == "repo"].n.sum()), repo_files=int((df["loc"] == "repo").sum()), volume_rows=int(vol.n.sum()), volume_files=len(vol),
                   volume_rows_identical_to_repo=int(vol[vol.in_repo].n.sum()), volume_only_rows=int(vol[~vol.in_repo].n.sum()), volume_only_nonsmoke_rows=int(vol[(~vol.in_repo) & (~vol.smoke)].n.sum()),
                   volume_only_smoke_rows=int(vol[(~vol.in_repo) & vol.smoke].n.sum()))
    out.mkdir(parents=True, exist_ok=True)
    (out / "trials.json").write_text(json.dumps(dict(summary=summary, files=rows), indent=1))
    print(json.dumps(summary, indent=1))


# ---------------------------------------------------------------- 1.2 rotasyon null'u (ensemble.rotate: tüm semboller aynı dairesel kaydırma)
def _null_job(i):
    p, sp = _GJ["p"], E.spec(cap=CAP)
    if i < 0:  # gerçek (kaydırmasız) koşu, aynı kod yolu
        u = None
    else:
        u = float(np.random.default_rng([0, i]).uniform(0.05, 0.95))  # K1 ile aynı tohumlar (reports/ensemble_protocol.md)
    res, win, _ = E.run(p, sp, u=u)
    pnl = report.book_pnl(win, res, sp)
    dn = pnl.resample("1D").sum()
    s = res["summary"]
    return dict(i=i, u=u, net=float(s["net_pnl"]), gross=float(s["gross_pnl"]), fee=float(s["fee"]), slip=float(s["slippage"]), funding=float(s["funding"]), n_fills=int(s["n_fills"]),
                sharpe_fixed=sharpe_fixed(dn, CAP), net_hourly=float(pnl.sum()))


def stage_null(out: Path, b_from: int, b_to: int, procs: int):
    t0 = time.time()
    kls = load_all()
    _GJ.update(p=params(), kls=kls, D=dict(E.D))
    idx = ([-1] if b_from == 0 else []) + list(range(b_from, b_to))
    with ProcessPoolExecutor(procs) as ex:
        rows = list(ex.map(_null_job, idx))
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / f"null_{b_from}_{b_to}.csv", index=False)
    print("tamam", len(rows), f"{time.time() - t0:.0f}s")


# ---------------------------------------------------------------- 2.5 benchmark'lar ve 2.6 karşı-olgusallar (post-hoc, betimsel)
def _daily_of(pnl: pd.Series) -> pd.Series:
    return pnl.resample("1D").sum()


def stage_bench(out: Path):
    from kepler import signals as sg
    t0 = time.time()
    kls = load_all()
    data = E.data_of(E.EXT)
    sp = E.spec(cap=CAP)
    notional = CAP / len(E.EXT)
    res_all = {}
    # (a) tek lookback'li basit TSMOM: tsmom(365, aylık) (reports/book_signals.md'de veriye bakmadan sabit), birim ±1 x notional, aynı hakem/Spec
    book = {s: pd.DataFrame(dict(target=sg.tsmom(365)(kls[s]) * notional, stop=np.nan), index=kls[s].index) for s in E.EXT}
    r, win, _ = ev.run_book(book, data, sp, *E.utc(E.MAIN))
    res_all["tsmom365"] = (r, report.book_pnl(win, r, sp))
    # (b) eşit notional long al-tut (K2 ile aynı), (c) BTC al-tut (sermaye kadar notional)
    sp_nc = replace(sp, gross_cap=None)
    res_all["ew_long"] = robust.buy_hold(data, sp_nc, CAP / len(E.EXT), E.MAIN)
    res_all["btc_hold"] = robust.buy_hold({"BTCUSDT": data["BTCUSDT"]}, sp_nc, CAP, E.MAIN)
    out.mkdir(parents=True, exist_ok=True)
    summ = {}
    for k, (r, pnl) in res_all.items():
        dn = _daily_of(pnl)
        dn.to_csv(out / f"daily_{k}.csv", header=["net"])
        summ[k] = dict({a: float(b) for a, b in r["summary"].items()}, sharpe_fixed=sharpe_fixed(dn, CAP), net_hourly=float(pnl.sum()))
    # alt sepeti: 8 alt'ın (BTC hariç) eşit ağırlıklı günlük fiyat getirisi (fiyat; maliyetsiz)
    close = pd.DataFrame({s: kls[s].close.resample("1D").last() for s in E.EXT})
    rets = close.pct_change()
    rets.to_csv(out / "daily_price_returns.csv")
    (out / "bench.json").write_text(json.dumps(dict(summary=summ, window=E.MAIN, notional_per_symbol=notional, seconds=time.time() - t0), indent=1, default=str))
    print("tamam", f"{time.time() - t0:.0f}s")


def stage_cf(out: Path):
    t0 = time.time()
    kls = load_all()
    data = E.data_of(E.EXT)
    sp = E.spec(cap=CAP)
    p = params()
    book = en.make_book(CAP, p)(kls)
    variants = {
        "long_only": {s: b.assign(target=b.target.clip(lower=0.0)) for s, b in book.items()},
        "short_x0.5": {s: b.assign(target=b.target.where(~(b.target < 0), b.target * 0.5)) for s, b in book.items()},
    }
    out.mkdir(parents=True, exist_ok=True)
    summ = {}
    for k, bk in variants.items():
        res, win, _ = ev.run_book(bk, data, sp, *E.utc(E.MAIN))
        pnl = report.book_pnl(win, res, sp)
        dn = _daily_of(pnl)
        dn.to_csv(out / f"daily_{k}.csv", header=["net"])
        res["fills"].to_csv(out / f"fills_{k}.csv", index=False)
        summ[k] = dict({a: float(b) for a, b in res["summary"].items()}, sharpe_fixed=sharpe_fixed(dn, CAP), net_hourly=float(pnl.sum()))
    (out / "cf.json").write_text(json.dumps(dict(summary=summ, window=E.MAIN, seconds=time.time() - t0), indent=1, default=str))
    print("tamam", f"{time.time() - t0:.0f}s")


# ---------------------------------------------------------------- 2.9 hayatta kalma yanlılığı: tarihsel likit evren (delist olanlar dahil)
def load_dynamic(syms: list, cap: float = CAP):
    """E.load ile aynı kural (kline + funding birleştirme, sezgisel tick/step), ama sembol yalnızca bulunduğu kökten(lerden) yüklenir (delist/geç listelenen semboller her iki kökte olmayabilir)."""
    from kepler import signals as sg
    for s in syms:
        parts = []
        for r, lo, hi in ROOTS:
            if (Path(r) / "tape" / "klines" / f"{s}.parquet").exists():
                part = tape.load(r, s, start=lo, end=hi)
                if len(part["klines"]):
                    parts.append(part)
        if not parts:
            continue
        d = {k: pd.concat([p_[k] for p_ in parts]).sort_index() for k in ("klines", "mark", "funding")}
        for k in d:
            d[k] = d[k][~d[k].index.duplicated()]
        kl = sg.with_funding(d["klines"][["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_quote_volume"]], d["funding"])
        q = Decimal(10) ** (math.floor(math.log10(kl.close.min())) - 5)
        st = Decimal(10) ** (math.floor(math.log10(0.25 * cap / kl.close.max())) - 3)
        E.D[s] = dict(kl=kl, funding=d["funding"], mark=d["mark"], tick=format(q, "f"), step=format(st, "f"))


def members(top_n: int) -> pd.DataFrame:
    """Aylık üyelik (month, sym): iki kökün `universe.parquet`ı (ay M üyeleri = M-1 hacim sıralaması, nedensel; delist olanlar dahil; stable/emtia dışlı) rank ≤ top_n; kullanılamaz kesim kuralı `tape.membership`."""
    parts = [tape.membership(r)[lambda d: d["rank"] <= top_n] for r in ("/data/pre2022", "/data")]
    df = pd.concat(parts, ignore_index=True)
    df = df[df.month >= "2020-03"]  # pencere 2020-04-01'den başlar (üyelik 2020-02'den var; 2020-03 ısınma için)
    return df.drop_duplicates(["month", "sym"])[["month", "sym"]]


def stage_surv(out: Path, top_n: int, procs: int = 1):
    t0 = time.time()
    mem = members(top_n)
    syms = sorted(mem.sym.unique())
    E.D.clear()
    load_dynamic(syms)
    syms = [s for s in syms if s in E.D]
    kls = {s: E.D[s]["kl"] for s in syms}
    orig = en.market_state

    def ms(close, kl_, p):
        st = orig(close, kl_, p)
        mask = pd.DataFrame(False, index=close.index, columns=close.columns)
        mon = close.index.strftime("%Y-%m")
        for m, g in mem.groupby("month"):
            mask.loc[mon == m, [c for c in g.sym if c in mask.columns]] = True
        return dict(st, active=st["active"] & mask)

    en.market_state = ms
    p = params()
    book = en.make_book(CAP, p)(kls)
    sp = E.spec(cap=CAP)
    res, win, _ = ev.run_book(book, E.data_of(syms), sp, *E.utc(E.MAIN))
    pnl = report.book_pnl(win, res, sp)
    dn = pnl.resample("1D").sum()
    per_sym = {s: float(report.hourly_pnl(win[s]["kl"], win[s].get("mark"), win[s].get("funding"), res["fills"][res["fills"].sym == s], sp).sum()) for s in win}
    n_active = {}
    close, _x = en.panel(kls)
    act = ms(close, kls, p)["active"]
    for y in range(2020, 2027):
        a = act[act.index.year == y]
        if len(a):
            n_active[y] = dict(mean=float(a.sum(axis=1).mean()), distinct=int((a.any(axis=0)).sum()))
    out.mkdir(parents=True, exist_ok=True)
    tag = f"top{top_n}"
    dn.to_csv(out / f"daily_{tag}.csv", header=["net"])
    (out / f"surv_{tag}.json").write_text(json.dumps(dict(top_n=top_n, n_symbols_loaded=len(syms), symbols=syms, summary={k: float(v) for k, v in res["summary"].items()}, sharpe_fixed=sharpe_fixed(dn, CAP), per_symbol_net=per_sym,
                                                          n_active_by_year=n_active, net_hourly=float(pnl.sum()), window=E.MAIN, delisted_in_universe=sorted(s for s in syms if s in ("LUNAUSDT", "FTTUSDT", "EOSUSDT", "GALUSDT", "MATICUSDT", "RNDRUSDT", "TOMOUSDT", "LUNA2USDT")),
                                                          seconds=time.time() - t0), indent=1, default=str))
    print("tamam", tag, f"{time.time() - t0:.0f}s", "net", res["summary"]["net_pnl"], "rejected", res["summary"]["n_rejected"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["causal", "mexc", "trials", "null", "bench", "cf", "surv"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-cuts", type=int, default=72)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--top-n", type=int, default=9)
    ap.add_argument("--b-from", type=int, default=0)
    ap.add_argument("--b-to", type=int, default=300)
    a = ap.parse_args()
    {"causal": lambda: stage_causal(Path(a.out), a.n_cuts, a.procs), "mexc": lambda: stage_mexc(Path(a.out), a.procs), "trials": lambda: stage_trials(Path(a.out)), "null": lambda: stage_null(Path(a.out), a.b_from, a.b_to, a.procs), "bench": lambda: stage_bench(Path(a.out)), "cf": lambda: stage_cf(Path(a.out)), "surv": lambda: stage_surv(Path(a.out), a.top_n)}[a.stage]()


if __name__ == "__main__":
    main()
