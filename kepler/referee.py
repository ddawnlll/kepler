"""C2: hakem motor = numba olay döngüsü (kepler/referee_core.py) + vektörel hazırlık/muhasebe. NautilusTrader'ın yerini aldı (eski hakem: git 23ee215).

Sözleşme: target[t] = t barı (açılış zamanı t) KAPANDIĞINDA istenen işaretli notional (USDT); NaN = mevcut pozisyonu tut.
Miktar yalnızca hedef DEĞİŞTİĞİNDE dolum fiyatından yeniden hesaplanır (lot adımına aşağı yuvarlanır); aynı hedef sürdükçe işlem yok.
Dolum (varsayılan fill="next_open"): karar t barının kapanışında bilinir, SONRAKİ barın açılış fiyatından dolar (her bar iki olay:
açılış tiki = karar anı, gövde (o,h,l,c) = stop/likidasyon eşleşmesi). fill="close" (eski, iyimser: karar barının kapanışından) yalnızca testler içindir;
`evaluate` reddeder. Son barın hedefi dolmaz. Likidasyondan sonra hesap ölü: yeni işlem yok (kalan marj likidasyon ücretiyle kaybedilir). Açık pozisyonun
çıkış maliyeti (fee+slip) son kapanıştan düşülür (close_out). Maliyet: taker fee + slippage (bps, gidiş-dönüş; yan başına yarısı) komisyona girer.
Funding: T anındaki oran, T'den ÖNCE (T'de yapılan dolumlardan önce) tutulan pozisyon x mark fiyat; işaret: oran>0 iken long öder. SETTLEMENT ANINDA, çekirdekte bakiyeye bir kez işlenir (#10):
equity, equity_scale, marj kilidi ve likidasyon fiyatı aynı akışı görür; sıra: gövde eşleşmesi (stop/likidasyon) -> funding -> koruyucu emirlerin yeni bakiyeyle yeniden kurulması (özsermaye bakım marjının altındaysa reduce-only piyasa kapama = likidasyon) -> karar/dolum.
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
from kepler.intents import finalize, from_kernel, summarize_kernel
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
    if funding is not None and not np.isfinite(funding["last_funding_rate"].to_numpy(float)).all():
        raise ValueError("funding oranında NaN/Inf var (QC'den geçmemiş veri)")
    tick, step = (getattr(spec, k) if d.get(k) is None else d[k] for k in ("tick", "step"))
    if not all(np.isfinite(float(x)) and float(x) > 0 for x in (tick, step)):
        raise ValueError("tick/step sonlu ve pozitif olmalı")
    pp, sp = _dp(tick), _dp(step)
    mark = d.get("mark")
    hi, lo = kl.high, kl.low
    if mark is not None and {"high", "low"} <= set(mark.columns):  # likidasyon stopu MARK fiyatının H/L'siyle tetiklenir (Binance); eksik mark barında kline H/L
        hi, lo = mark.high.reindex(kl.index).fillna(kl.high), mark.low.reindex(kl.index).fillna(kl.low)
    o, c = kl.open.to_numpy(float), kl.close.to_numpy(float)
    h, l = np.fmax.reduce([hi.to_numpy(float), o, c]), np.fmin.reduce([lo.to_numpy(float), o, c])  # noqa: E741  O/C [L,H] içinde kalsın
    q = lambda a: np.rint(a * 10.0**pp / (float(tick) * 10.0**pp)) * (float(tick) * 10.0**pp) / 10.0**pp  # noqa: E731  tick ondalığına yuvarla (Price.from_str karşılığı)
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
    if stop is not None:
        tape.check_target(kl, stop)
    tg = target.astype(float).to_numpy()
    st = stop.astype(float).to_numpy() if stop is not None else np.full(len(kl), np.nan)
    return dict(t0=t0, o=o, h=h, l=l, c=c, tg=tg, st=st, sz=sz, u=(1.0 / float(step), 1.0 / float(tick), float(tick)))


def _fund_inputs(kl, mark, funding, fallback=None):
    """Funding olaylarının pozisyondan bağımsız kısmı (bir kez): T (1 dk yuvarlı), oran, mark kapanışı (yoksa kline kapanışı), kaçan/kline'a düşen sayıları. Aralık dışı olaylar atlanır."""
    if funding is None or not len(funding):
        return None
    ts, rate, t0 = ns(pd.DatetimeIndex(funding.index).round("1min")), funding["last_funding_rate"].to_numpy(float), ns(kl.index)
    ok = (t0[0] + HOUR_NS <= ts) & (ts <= t0[-1] + HOUR_NS)
    ts, rate = ts[ok], rate[ok]
    fallback = kl if fallback is None else fallback
    src = mark if mark is not None else fallback
    if len(src):
        order = np.argsort(ns(src.index), kind="stable")
        mk_close, mk_val = (ns(src.index) + HOUR_NS)[order], src.close.to_numpy(float)[order]
        i = np.searchsorted(mk_close, ts, side="right") - 1  # yinelenen anahtarda sonuncusu (dict semantiği)
        hit = (i >= 0) & (mk_close[np.maximum(i, 0)] == ts)
        c = np.where(hit, mk_val[np.maximum(i, 0)], np.nan)
    else:
        c = np.full(len(ts), np.nan)
    fallback_count = 0
    if mark is not None:  # mark barı yok: kline kapanışına düş (sayılır)
        miss = np.isnan(c)
        fb_t = ns(fallback.index)
        j = np.searchsorted(fb_t, ts - HOUR_NS)
        kh = (j < len(fb_t)) & (fb_t[np.minimum(j, len(fb_t) - 1)] == ts - HOUR_NS)
        c2 = np.where(kh, fallback.close.to_numpy(float)[np.minimum(j, len(fb_t) - 1)], np.nan)
        c, fallback_count = np.where(miss, c2, c), int((miss & ~np.isnan(c2)).sum())
    if np.isinf(c).any() or (c <= 0).any():
        raise ValueError("funding mark/kline fiyatı sonlu ve pozitif olmalı (eksik NaN ayrı sayılır)")
    return dict(ts=ts, rate=rate, c=c, fallback=fallback_count)


def _fund_arrays(fx):
    """Global sorted settlement clock; same-time events keep one shared position snapshot."""
    parts = [(np.zeros(0, np.int64), np.zeros(0), np.zeros(0)) if f is None else (f["ts"], f["c"], f["rate"]) for f in fx]
    FT, FC, FR = (np.concatenate([p[i] for p in parts]) for i in range(3))
    FK = np.repeat(np.arange(len(fx), dtype=np.int64), [len(p[0]) for p in parts])
    order = np.argsort(FT, kind="stable")
    return dict(FK=FK[order], FT=FT[order].astype(np.int64), FC=FC[order], FR=FR[order])


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
        ev_t, ev_b, ev_k, ev_kind = T0 + HOUR_NS, bar, sym, np.full(len(bar), core.KIND_CLOSE, np.int8)
    else:
        ev_t, ev_b, ev_k = np.r_[T0, T0 + HOUR_NS - 1], np.r_[bar, bar], np.r_[sym, sym]
        ev_kind = np.r_[np.zeros(len(bar), np.int8), np.ones(len(bar), np.int8)]
    fx = [_fund_inputs(d["kl"], d.get("mark"), d.get("funding"), d.get("funding_fallback_kl")) for d in data.values()]
    o_ = np.lexsort((ev_k, ev_t))  # zaman, sonra sembol sırası (eski motor: veri ekleme sırası)
    return dict(syms=syms, prep=prep, n=n, off=off, T0=T0, O=O, H=H, L=L, C=C, SZ=SZ, U=np.array([p["u"] for p in prep]), close_mode=close_mode, tg=cat("tg"), st=cat("st"),
                ev_k=ev_k[o_].astype(np.int64), ev_b=ev_b[o_].astype(np.int64), ev_kind=ev_kind[o_], fx=fx, **_fund_arrays(fx), key=(spec.fill, spec.tick, spec.step))


def _inputs(pr: dict, spec: Spec):
    """Senaryoya özgü girdiler: kaydırılmış hedef/stop (karar j -> yuva j + 1 + delay; close modunda j + delay) ve parametre vektörü."""
    off, sh = pr["off"], spec.delay if pr["close_mode"] else 1 + spec.delay
    TG, ST = pr["tg"].copy(), pr["st"].copy()
    for k in range(len(pr["syms"])):
        sl = slice(off[k], off[k + 1])
        TG[sl], ST[sl] = _shift(pr["tg"][sl], sh), _shift(pr["st"][sl], sh)
    P = np.array([(spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4, spec.leverage, spec.mmr, float(spec.liq and not spec.native_liq), spec.min_notional, spec.capital, float(spec.equity_scale), spec.gross_cap or 0.0, float(pr["close_mode"])])
    return TG, ST, P


def _kernel_cpu(pr: dict, TG, ST, P):
    nb = len(pr["T0"])
    cap = max(4096, nb // 16)  # tipik dolum sayısı bar sayısının ~%1'i; taşarsa iki katına çıkarıp yeniden koş (senaryo başına ~110 MB yerine ~5 MB tampon)
    while True:
        FI, FF, PI, PF, RJ = np.zeros((cap, 4), np.int64), np.zeros((cap, 3)), np.zeros((cap, 3), np.int64), np.zeros(cap), np.zeros((cap, 3), np.int64)
        IT, IF = np.zeros((cap, 3), np.int64), np.zeros((cap, 5))
        F, I, G, N = core.simulate(pr["ev_k"], pr["ev_b"], pr["ev_kind"], pr["T0"], pr["O"], pr["H"], pr["L"], pr["C"], pr["SZ"], TG, ST, pr["U"], P, cap, pr["FK"], pr["FT"], pr["FC"], pr["FR"], FI, FF, PI, PF, RJ, IT, IF)
        if N[0] >= 0:
            return dict(F=F, I=I, G=G, N=N, FI=FI, FF=FF, PI=PI, PF=PF, RJ=RJ, IT=IT, IF=IF)
        cap *= 2


def run_portfolio(data: dict[str, dict], spec: Spec = Spec(), prepared: dict | None = None) -> dict:
    """Tek USDT hesap, ortak marj. data[sym] = dict(kl, target, funding=None, mark=None, stop=None, tick=None, step=None).
    stop[t] = t kapanışında bilinen koruyucu stop fiyatı (NaN = stop yok), t+1 açılışından itibaren geçerli. Sembol başına likidasyon (cross-margin likidasyonu yok)."""
    pr = prepared if prepared is not None and prepared["key"] == (spec.fill, spec.tick, spec.step) else prepare(data, spec)
    return _finish(pr, data, spec, _kernel_cpu(pr, *_inputs(pr, spec)))


def _finish(pr: dict, data: dict, spec: Spec, raw: dict, full: bool = True) -> dict:
    """Çekirdek çıktısından özet + (full ise) fills/positions tabloları. Funding çekirdekte settlement anında işlendi (G[1] toplam, N[3] kaçan). full=False: DataFrame üretilmez (tarama)."""
    syms, prep, off, U, close_mode = pr["syms"], pr["prep"], pr["off"], pr["U"], pr["close_mode"]
    F, I, G, N, FI, FF, PI, PF, RJ, IT, IF = (raw[k] for k in ("F", "I", "G", "N", "FI", "FF", "PI", "PF", "RJ", "IT", "IF"))
    side_fee, (nf, npos, nrej), PF = (spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4, (int(N[0]), int(N[1]), int(N[2])), PF.copy()
    for k in range(len(syms)):
        if I[k, core.LOT] != 0:
            PF[I[k, core.COPEN]] = F[k, core.CYC]  # açık döngü: o ana kadarki realize (komisyon dahil)
    fi, ff = FI[:nf], FF[:nf]
    liq, stp = (fi[:, 3] & 1) > 0, (fi[:, 3] & 2) > 0
    notional = float((ff[:, 0] * ff[:, 1]).sum())
    fee, slip = notional * spec.fee_rt_bps / 2 / 1e4, notional * spec.slip_rt_bps / 2 / 1e4
    liq_fee = float((ff[liq, 0] * ff[liq, 1]).sum()) * max(0.0, (spec.mmr if spec.liq_fee_rate is None else spec.liq_fee_rate) - side_fee)  # motor taker fee'yi zaten kesti
    last = [float(d["kl"].close.iloc[-1]) for d in data.values()]
    end_pos = {s: I[k, core.LOT] / U[k, 0] for k, s in enumerate(syms)}
    unreal = sum(end_pos[s] * (last[k] - F[k, core.AVG]) for k, s in enumerate(syms) if I[k, core.LOT] != 0)
    exit_cost = sum(abs(end_pos[s]) * last[k] * side_fee for k, s in enumerate(syms)) if spec.close_out else 0.0
    fund, missed, fallback = float(G[1]), int(N[3]), sum(f["fallback"] for f in pr["fx"] if f is not None)  # funding çekirdekte settlement anında işlendi (G[0] bakiyesine dahil; burada tekrar eklenmez)
    net = float(G[0]) + unreal - spec.capital - liq_fee - exit_cost
    rejected = [f"OrderRejected(sym={syms[r[0]]} ts={r[1]} qty={r[2] / U[r[0], 0]}: {'stop kitap fiyatında' if r[2] == 0 else 'marj/piyasa yok'})" for r in RJ[:nrej]]
    summary = dict(net_pnl=net, gross_pnl=net + fee + slip + exit_cost - fund + liq_fee, fee=fee, slippage=slip, funding=fund, liq_fee=liq_fee, exit_cost=exit_cost, n_fills=nf, n_liq=int(liq.sum()), n_stop=int(stp.sum()),
                   end_position=next(iter(end_pos.values())) if len(end_pos) == 1 else sum(abs(v) for v in end_pos.values()), engine_commission=float(ff[:, 2].sum()), n_rejected=len(rejected),
                   funding_missed=missed, funding_mark_fallback=fallback)
    it, iv = IT[: int(N[4])], IF[: int(N[4])]
    intents, isum = finalize(from_kernel(syms, it, iv)) if full else (None, summarize_kernel(it, iv))
    summary.update(isum)  # niyet izi (#11): n_intents, n_blocked_minimum, n_noop_lot, n_blocked_halt, n_partial, n_engine_unfilled, blocked_notional, gap_notional_abs
    if not full:
        return dict(summary=summary, rejected=rejected)
    fills = pd.DataFrame(dict(sym=np.array(syms, dtype=object)[fi[:, 0]], ts=fi[:, 1], side=np.where(fi[:, 2] > 0, "BUY", "SELL"), qty=ff[:, 0], px=ff[:, 1], commission=ff[:, 2], liq=liq, stop=stp))
    pi = PI[:npos]
    return dict(summary=summary, fills=fills, rejected=rejected, intents=intents, positions=pd.DataFrame(dict(opened=pd.to_datetime(pi[:, 0], utc=True), closed=pd.to_datetime(np.where(pi[:, 1] > 0, pi[:, 1], np.iinfo(np.int64).min), utc=True), realized=PF[:npos])))


def run_many(data: dict[str, dict], specs: list[Spec], workers: int = 4, full: bool = True, kernel=None) -> list[dict]:
    """Aynı veri, çok senaryo; hazırlık bir kez, çekirdek nogil olduğundan iş parçacıklarıyla paralel. full=False: yalnızca özet + reddedilenler (fills/positions DataFrame'i yok; tarama için).
    kernel: eski GPU çağrılarını açıkça reddetmek için korunan uyumluluk parametresi; yalnız Numba CPU desteklenir."""
    from concurrent.futures import ThreadPoolExecutor
    if kernel is not None:
        raise NotImplementedError("GPU yolu emekliye ayrıldı: funding/niyet eşdeğerliği doğrulanmadı. Numba CPU kullanın.")
    if not specs:
        return []
    if workers < 1:
        raise ValueError("workers >= 1 required")
    pr = prepare(data, specs[0])
    if not all((sp.fill, sp.tick, sp.step) == pr["key"] for sp in specs):
        raise ValueError("tüm senaryolar aynı fill/tick/step paylaşmalı")
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(lambda sp: _run_cpu(pr, data, sp, full), specs))


def _run_cpu(pr: dict, data: dict, sp: Spec, full: bool) -> dict:
    return _finish(pr, data, sp, _kernel_cpu(pr, *_inputs(pr, sp)), full)
