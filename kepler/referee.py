"""C2: hakem motor = numba olay döngüsü (kepler/referee_core.py) + vektörel hazırlık/muhasebe. NautilusTrader'ın yerini aldı (eski hakem: git 23ee215).

Sözleşme: target[t] = t barı (açılış zamanı t) KAPANDIĞINDA istenen işaretli notional (USDT); NaN = mevcut pozisyonu tut.
Miktar yalnızca hedef DEĞİŞTİĞİNDE dolum fiyatından yeniden hesaplanır (lot adımına aşağı yuvarlanır); aynı hedef sürdükçe işlem yok.
Dolum (varsayılan fill="next_open"): karar t barının kapanışında bilinir, SONRAKİ barın açılış fiyatından dolar (her bar iki olay:
açılış tiki = karar anı, gövde (o,h,l,c) = stop/likidasyon eşleşmesi). fill="close" (eski, iyimser: karar barının kapanışından) yalnızca testler içindir;
`evaluate` reddeder. Son barın hedefi dolmaz. Likidasyondan sonra hesap ölü: yeni işlem yok (kalan marj likidasyon ücretiyle kaybedilir). Açık pozisyonun
çıkış maliyeti (fee+slip) son kapanıştan düşülür (close_out). Maliyet: taker fee + slippage (bps, gidiş-dönüş; yan başına yarısı) komisyona girer.
Funding: T anındaki oran, T'den ÖNCE (T'de yapılan dolumlardan önce) tutulan pozisyon x mark fiyat; işaret: oran>0 iken long öder.
Likidasyon: her pozisyon değişiminde likidasyon fiyatında reduce-only STOP; tetik MARK H/L'siyle (mark yoksa kline); gap'te açılıştan, bar içinde seviyeden dolar.
Hacim sınırı (L1 bar yürütmesi): her tikin boyutu = bar hacmi/4 (lot adımına bölünmüş); piyasa/stop emri tik boyutu kadar tek fiyattan dolar, KALANI son dolum fiyatının 1 tick ötesinden
(alış +, satış -) dolar. Marj: artıran/çeviren emir, başlangıç marjı (|notional|/kaldıraç^2: Nautilus LeveragedMarginModel, margin_init=1/kaldıraç) - bakım marjı kilidini bakiyeden
aşıyorsa REDDEDİLİR (n_rejected; defter reddeden koşuyu kabul etmez); kitap fiyatı stop seviyesindeyse stop da reddedilir.
"""
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd

from kepler import referee_core as core
from kepler import tape

HOUR_NS = core.HOUR


@dataclass(frozen=True)
class Spec:
    tick: str = "0.1"
    step: str = "0.001"
    min_notional: float = 5.0
    fee_rt_bps: float = 10.0
    slip_rt_bps: float = 0.0
    leverage: int = 10
    mmr: float = 0.005  # bakım marjı oranı (sembole/kademeye göre değişir; UNKNOWN: gerçek kademe tablosu alınmadı)
    capital: float = 500.0
    liq: bool = True
    native_liq: bool = False  # yalnızca test uyumu: eski motorun kendi likidasyonu bar verisinde işe yaramıyordu; burada liq=False ile aynı (likidasyon yok)
    liq_fee_rate: float | None = None  # None -> mmr (kalan bakım marjı kaybedilir; gerçek Binance ücreti UNKNOWN); motorun taker fee'si bunun İÇİNDE sayılır (çifte sayım yok)
    fill: str = "next_open"  # "next_open" | "close" (yalnızca test/eski)
    close_out: bool = True  # açık pozisyonu son kapanıştan çıkış fee+slip ile değerle
    delay: int = 0  # ek gecikme (bar): dolum karardan sonraki (1 + delay). mevcut barda; stres testi (K3)
    gross_cap: float | None = None  # toplam brüt notional tavanı (USDT); artıran emir kalan alana küçülür (portföy, §6.5)
    equity_scale: bool = False  # True: yeni/değişen hedef notional (ve gross_cap) x equity / capital, equity = bakiye + gerçekleşmemiş PnL, emir anında (BACKTEST §5.1)


def ns(index) -> np.ndarray:
    return np.asarray(pd.DatetimeIndex(index).as_unit("ns").asi8, np.int64)


def _dp(s: str) -> int:
    return max(0, -Decimal(s).as_tuple().exponent)


def _shift(a: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    if k < len(a):
        out[k:] = a[: len(a) - k]
    return out


def _prep(sym: str, d: dict, spec: Spec):
    """Sembol verisini çekirdek dizilerine çevir: kline (+ mark H/L), tick yuvarlama, karar -> yuva kaydırma (bisect_left(yuvalar, kapanış) + delay = j + 1 + delay)."""
    kl, target, funding = d["kl"], d["target"], d.get("funding")
    if not (kl.index.is_monotonic_increasing and kl.index.is_unique):
        raise ValueError("kl indeksi artan ve tekil olmalı")
    t0 = ns(kl.index)
    if len(kl) == 0 or (np.diff(t0) % HOUR_NS).any() or t0[0] % HOUR_NS:
        raise ValueError("kl boş ya da saatlik hizalı değil")
    tape.check_target(kl, target)  # yanlış hizalı/tz'siz hedef sessizce sıfır işleme dönüşmesin
    if funding is not None and funding["last_funding_rate"].isna().any():
        raise ValueError("funding oranında NaN var (QC'den geçmemiş veri)")
    tick, step = d.get("tick") or spec.tick, d.get("step") or spec.step
    if not all(np.isfinite(float(x)) and float(x) > 0 for x in (tick, step)):
        raise ValueError("tick ve step pozitif ve sonlu olmalı")
    pp, sp = _dp(tick), _dp(step)
    mark = d.get("mark")
    hi, lo = kl.high, kl.low
    if mark is not None and {"high", "low"} <= set(mark.columns):  # likidasyon stopu MARK fiyatının H/L'siyle tetiklenir (Binance); eksik mark barında kline H/L
        hi, lo = mark.high.reindex(kl.index).fillna(kl.high), mark.low.reindex(kl.index).fillna(kl.low)
    o, c = kl.open.to_numpy(float), kl.close.to_numpy(float)
    h, l = np.fmax.reduce([hi.to_numpy(float), o, c]), np.fmin.reduce([lo.to_numpy(float), o, c])  # noqa: E741  O/C [L,H] içinde kalsın
    q = lambda a: np.round(np.rint(a / float(tick)) * float(tick), pp)  # noqa: E731  gerçek tick katı
    o, h, l, c = q(o), q(h), q(l), q(c)  # noqa: E741
    if not all(np.isfinite(a).all() and (a > 0).all() for a in (o, h, l, c)):
        raise ValueError(f"{sym}: kline OHLC'de NaN/sonsuz/pozitif olmayan fiyat (QC'den geçmemiş veri)")
    vol = kl.volume.to_numpy(float)
    if not (np.isfinite(vol).all() and (vol >= 0).all()):
        raise ValueError(f"{sym}: hacimde NaN/sonsuz/negatif değer (QC'den geçmemiş veri)")
    inc, incs = max(int(round(float(step) * 10.0**sp)), 1), np.rint(vol * 10.0**sp).astype(np.int64)  # BarTickSizes: hacim lot adımının katına inip 4 tike bölünür
    incs //= inc
    path = incs // 4
    sz = np.zeros((len(kl), 4), np.int64)
    big = incs >= 4
    sz[big] = np.c_[path, path, path, incs - 3 * path][big]
    sz[incs == 1, 3], sz[incs == 2, 1], sz[incs == 2, 2], sz[incs == 3, :3] = 1, 1, 1, 1
    stop = d.get("stop")
    tg = target.astype(float).to_numpy()
    st = stop.astype(float).to_numpy() if stop is not None else np.full(len(kl), np.nan)
    return dict(t0=t0, o=o, h=h, l=l, c=c, tg=tg, st=st, sz=sz * inc, u=(10.0**sp, 10.0**pp, float(tick), inc))


def _fund_inputs(kl, mark, funding):
    """Funding olaylarının pozisyondan bağımsız kısmı (bir kez): T (1 dk yuvarlı), oran, mark kapanışı (yoksa kline kapanışı), kaçan/kline'a düşen sayıları. Aralık dışı olaylar atlanır."""
    if funding is None or not len(funding):
        return None
    ts, rate, t0 = ns(pd.DatetimeIndex(funding.index).round("1min")), funding["last_funding_rate"].to_numpy(float), ns(kl.index)
    ok = (t0[0] + HOUR_NS <= ts) & (ts <= t0[-1] + HOUR_NS)
    ts, rate = ts[ok], rate[ok]
    src = mark if mark is not None else kl
    order = np.argsort(ns(src.index), kind="stable")
    mk_close, mk_val = (ns(src.index) + HOUR_NS)[order], src.close.to_numpy(float)[order]
    i = np.searchsorted(mk_close, ts, side="right") - 1  # yinelenen anahtarda sonuncusu (dict semantiği)
    hit = (i >= 0) & (mk_close[np.maximum(i, 0)] == ts)
    c, fallback = np.where(hit, mk_val[np.maximum(i, 0)], np.nan), 0
    if mark is not None:  # mark barı yok: kline kapanışına düş (sayılır)
        miss = np.isnan(c)
        j = np.searchsorted(t0, ts - HOUR_NS)
        kh = (j < len(t0)) & (t0[np.minimum(j, len(t0) - 1)] == ts - HOUR_NS)
        c2 = np.where(kh, kl.close.to_numpy(float)[np.minimum(j, len(t0) - 1)], np.nan)
        c, fallback = np.where(miss, c2, c), int((miss & ~np.isnan(c2)).sum())
    return dict(ts=ts, rate=rate, c=c, fallback=fallback)


def _funding(fx, keys, vals):
    """T'den ÖNCE tutulan pozisyon (keys[j] >= T ilk anahtar) x mark kapanışı x oran. (toplam, kaçan, kline'a düşen)."""
    if fx is None:
        return 0.0, 0, 0
    jk = np.searchsorted(keys, fx["ts"], side="left")
    bad = np.isnan(fx["c"]) | (jk == len(keys))
    return float(np.sum(np.where(bad, 0.0, -vals[np.minimum(jk, len(keys) - 1)] * np.where(bad, 0.0, fx["c"]) * fx["rate"]))), int(bad.sum()), fx["fallback"]


def run(kl: pd.DataFrame, target: pd.Series, spec: Spec = Spec(), funding: pd.DataFrame | None = None, mark: pd.DataFrame | None = None, stop: pd.Series | None = None) -> dict:
    """Tek sembol = run_portfolio'nun tek sembollü hali. kl: ts(bar açılışı, UTC) indeksli open/high/low/close/volume. Dönüş: {'summary', 'fills', 'rejected'}."""
    return run_portfolio({"SYM": dict(kl=kl, target=target, funding=funding, mark=mark, stop=stop)}, spec)


def prepare(data: dict[str, dict], spec: Spec = Spec()) -> dict:
    """Koşudan bağımsız hazırlık (doğrulama, tick yuvarlama, hacim -> tik boyutu, olay sırası). Aynı veriyle çok senaryo (fee/slip/gecikme ızgarası) için bir kez hesaplanıp `prepared=` ile verilir."""
    if spec.fill not in ("next_open", "close"):
        raise ValueError("fill next_open veya close olmalı")
    syms, prep = list(data), [_prep(s, d, spec) for s, d in data.items()]
    n = np.array([len(p["t0"]) for p in prep])
    off = np.r_[0, np.cumsum(n)]
    cat = lambda key: np.concatenate([p[key] for p in prep])  # noqa: E731
    T0, O, H, L, C, SZ = (cat(k) for k in ("t0", "o", "h", "l", "c", "sz"))
    close_mode = spec.fill == "close"
    bar, sym = np.arange(off[-1]), np.repeat(np.arange(len(syms)), n)
    if close_mode:
        ev_t, ev_b, ev_k = np.r_[T0 + HOUR_NS - 1, T0 + HOUR_NS], np.r_[bar, bar], np.r_[sym, sym]
        ev_kind = np.r_[np.full(len(bar), core.KIND_BODY, np.int8), np.full(len(bar), core.KIND_CLOSE, np.int8)]
    else:
        ev_t, ev_b, ev_k = np.r_[T0, T0 + HOUR_NS - 1], np.r_[bar, bar], np.r_[sym, sym]
        ev_kind = np.r_[np.zeros(len(bar), np.int8), np.ones(len(bar), np.int8)]
    fx = [_fund_inputs(d["kl"], d.get("mark"), d.get("funding")) for d in data.values()]
    FT = np.concatenate([x["ts"] for x in fx if x is not None]) if any(x is not None for x in fx) else np.empty(0, np.int64)
    FV = np.concatenate([np.nan_to_num(x["c"], nan=0.0) * x["rate"] for x in fx if x is not None]) if len(FT) else np.empty(0)
    fk = np.concatenate([np.full(len(x["ts"]), k, np.int64) for k, x in enumerate(fx) if x is not None]) if len(FT) else np.empty(0, np.int64)
    ev_t, ev_b, ev_k, ev_kind = np.r_[ev_t, FT], np.r_[ev_b, np.arange(len(FT))], np.r_[ev_k, fk], np.r_[ev_kind, np.full(len(FT), core.KIND_FUND, np.int8)]
    o_ = np.lexsort((ev_k, ev_kind != core.KIND_FUND, ev_t))  # T'de tüm funding, ardından dolum/karar; sembol sırası sabit
    return dict(syms=syms, prep=prep, n=n, off=off, T0=T0, O=O, H=H, L=L, C=C, SZ=SZ, U=np.array([p["u"] for p in prep]), close_mode=close_mode, tg=cat("tg"), st=cat("st"),
                ev_k=ev_k[o_].astype(np.int64), ev_b=ev_b[o_].astype(np.int64), ev_kind=ev_kind[o_], fx=fx, FT=FT, FV=FV, key=(spec.fill, spec.tick, spec.step))


def _inputs(pr: dict, spec: Spec):
    """Senaryoya özgü girdiler: kaydırılmış hedef/stop (karar j -> yuva j + 1 + delay; close modunda j + delay) ve parametre vektörü."""
    off, sh = pr["off"], spec.delay if pr["close_mode"] else 1 + spec.delay
    TG, ST = pr["tg"].copy(), pr["st"].copy()
    for k in range(len(pr["syms"])):
        sl = slice(off[k], off[k + 1])
        TG[sl], ST[sl] = _shift(pr["tg"][sl], sh), _shift(pr["st"][sl], sh)
    P = np.array([(spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4, spec.leverage, spec.mmr, float(spec.liq and not spec.native_liq), spec.min_notional, spec.capital, float(spec.equity_scale), spec.gross_cap or 0.0, float(pr["close_mode"]), spec.mmr if spec.liq_fee_rate is None else spec.liq_fee_rate])
    return TG, ST, P


def _kernel_cpu(pr: dict, TG, ST, P):
    nb = len(pr["T0"])
    cap = max(4096, nb // 16)  # tipik dolum sayısı bar sayısının ~%1'i; taşarsa iki katına çıkarıp yeniden koş (senaryo başına ~110 MB yerine ~5 MB tampon)
    while True:
        FI, FF, PI, PF, RJ = np.zeros((cap, 4), np.int64), np.zeros((cap, 3)), np.zeros((cap, 3), np.int64), np.zeros(cap), np.zeros((cap, 3), np.int64)
        PRE, END = np.zeros(nb, np.int64), np.zeros(nb, np.int64)
        F, I, G, N = core.simulate(pr["ev_k"], pr["ev_b"], pr["ev_kind"], pr["T0"], pr["O"], pr["H"], pr["L"], pr["C"], pr["SZ"], TG, ST, pr["U"], P, cap, FI, FF, PI, PF, RJ, PRE, END, pr["FT"], pr["FV"])
        if N[0] >= 0:
            return dict(F=F, I=I, G=G, N=N, FI=FI, FF=FF, PI=PI, PF=PF, RJ=RJ, PRE=PRE, END=END)
        cap *= 2


def run_portfolio(data: dict[str, dict], spec: Spec = Spec(), prepared: dict | None = None) -> dict:
    """Tek USDT hesap, ortak marj. data[sym] = dict(kl, target, funding=None, mark=None, stop=None, tick=None, step=None).
    stop[t] = t kapanışında bilinen koruyucu stop fiyatı (NaN = stop yok), t+1 açılışından itibaren geçerli. Sembol başına likidasyon (cross-margin likidasyonu yok)."""
    pr = prepared if prepared is not None and prepared["key"] == (spec.fill, spec.tick, spec.step) else prepare(data, spec)
    return _finish(pr, data, spec, _kernel_cpu(pr, *_inputs(pr, spec)))


def _finish(pr: dict, data: dict, spec: Spec, raw: dict, full: bool = True) -> dict:
    """Çekirdek nakdinden özet + (full ise) fills/positions; PRE/END yalnız funding veri eksikliği sayaçları için. full=False: DataFrame üretilmez (tarama)."""
    syms, prep, off, U, close_mode = pr["syms"], pr["prep"], pr["off"], pr["U"], pr["close_mode"]
    F, I, G, N, FI, FF, PI, PF, RJ, PRE, END = (raw[k] for k in ("F", "I", "G", "N", "FI", "FF", "PI", "PF", "RJ", "PRE", "END"))
    side_fee, (nf, npos, nrej), PF = (spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4, (int(N[0]), int(N[1]), int(N[2])), PF.copy()
    for k in range(len(syms)):
        if I[k, core.LOT] != 0:
            PF[I[k, core.COPEN]] = F[k, core.CYC]  # açık döngü: o ana kadarki realize (komisyon dahil)
    fi, ff = FI[:nf], FF[:nf]
    liq, stp = (fi[:, 3] & 1) > 0, (fi[:, 3] & 2) > 0
    notional = float((ff[:, 0] * ff[:, 1]).sum())
    fee, slip = notional * spec.fee_rt_bps / 2 / 1e4, notional * spec.slip_rt_bps / 2 / 1e4
    last = [float(d["kl"].close.iloc[-1]) for d in data.values()]
    end_pos = {s: I[k, core.LOT] / U[k, 0] for k, s in enumerate(syms)}
    unreal = sum(end_pos[s] * (last[k] - F[k, core.AVG]) for k, s in enumerate(syms) if I[k, core.LOT] != 0)
    exit_cost = sum(abs(end_pos[s]) * last[k] * side_fee for k, s in enumerate(syms)) if spec.close_out else 0.0
    missed, fallback = 0, 0
    for k, (s, d) in enumerate(data.items()):
        sl, kl = slice(off[k], off[k + 1]), d["kl"]
        pre, end, t0 = PRE[sl] / U[k, 0], END[sl] / U[k, 0], prep[k]["t0"]
        if close_mode:
            keys, vals = t0 + HOUR_NS, pre
        else:  # gövde sonu anahtarı = kapanış; açılış anahtarı yalnızca bir önceki barın kapanışına eşit değilse (ilk bar, boşluk sonrası) eklenir (setdefault semantiği)
            new = np.r_[True, t0[1:] != t0[:-1] + HOUR_NS]
            keys, vals = np.r_[t0 + HOUR_NS, t0[new]], np.r_[end, pre[new]]
        srt = np.argsort(keys, kind="stable")
        _, m, fb = _funding(pr["fx"][k], keys[srt], vals[srt])
        missed, fallback = missed + m, fallback + fb
    fund, liq_fee = float(G[1]), float(G[2])
    net = float(G[0]) + unreal - spec.capital - exit_cost
    rejected = [f"OrderRejected(sym={syms[r[0]]} ts={r[1]} qty={r[2] / U[r[0], 0]}: {'stop kitap fiyatında' if r[2] == 0 else 'marj/piyasa yok'})" for r in RJ[:nrej]]
    summary = dict(net_pnl=net, gross_pnl=net + fee + slip + exit_cost - fund + liq_fee, fee=fee, slippage=slip, funding=fund, liq_fee=liq_fee, exit_cost=exit_cost, n_fills=nf, n_liq=int(liq.sum()), n_stop=int(stp.sum()),
                   end_position=next(iter(end_pos.values())) if len(end_pos) == 1 else sum(abs(v) for v in end_pos.values()), engine_commission=float(ff[:, 2].sum()), n_rejected=len(rejected),
                   funding_missed=missed, funding_mark_fallback=fallback)
    if not full:
        return dict(summary=summary, rejected=rejected)
    fills = pd.DataFrame(dict(sym=np.array(syms, dtype=object)[fi[:, 0]], ts=fi[:, 1], side=np.where(fi[:, 2] > 0, "BUY", "SELL"), qty=ff[:, 0], px=ff[:, 1], commission=ff[:, 2], liq=liq, stop=stp))
    pi = PI[:npos]
    return dict(summary=summary, fills=fills, rejected=rejected, positions=pd.DataFrame(dict(opened=pd.to_datetime(pi[:, 0], utc=True), closed=pd.to_datetime(np.where(pi[:, 1] > 0, pi[:, 1], np.iinfo(np.int64).min), utc=True), realized=PF[:npos])))


def run_many(data: dict[str, dict], specs: list[Spec], workers: int = 4, full: bool = True, kernel=None) -> list[dict]:
    """Aynı veri, çok senaryo; hazırlık bir kez, çekirdek nogil olduğundan iş parçacıklarıyla paralel. full=False: yalnızca özet + reddedilenler (fills/positions DataFrame'i yok; tarama için).
    kernel: isteğe bağlı GPU çekirdeği `simulate_many(pr, inputs) -> ham çıktılar|None` (scripts/referee_gpu.py; tam hatta kazanç ~1,1x ve ~4x pahalı olduğundan varsayılan CPU)."""
    from concurrent.futures import ThreadPoolExecutor
    pr = prepare(data, specs[0])
    assert all((sp.fill, sp.tick, sp.step) == pr["key"] for sp in specs), "tüm senaryolar aynı fill/tick/step'i paylaşmalı"
    raws = kernel(pr, [_inputs(pr, sp) for sp in specs]) if kernel else [None] * len(specs)
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(lambda a: _finish(pr, data, a[0], a[1], full) if a[1] is not None else _run_cpu(pr, data, a[0], full), zip(specs, raws)))


def _run_cpu(pr: dict, data: dict, sp: Spec, full: bool) -> dict:
    return _finish(pr, data, sp, _kernel_cpu(pr, *_inputs(pr, sp)), full)
