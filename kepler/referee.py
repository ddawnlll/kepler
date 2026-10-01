"""C2: hakem motor = NautilusTrader 2.0.0rc5 + ince yapıştırma (hedef→emir, likidasyon stopu, funding).

Sözleşme: target[t] = t barı (açılış zamanı t) KAPANDIĞINDA istenen işaretli notional (USDT); NaN = mevcut pozisyonu tut.
Miktar yalnızca hedef DEĞİŞTİĞİNDE dolum fiyatından yeniden hesaplanır (lot adımına aşağı yuvarlanır); aynı hedef sürdükçe işlem yok.
Dolum (varsayılan fill="next_open"): karar t barının kapanışında bilinir, SONRAKİ barın açılış fiyatından dolar (her bar motora iki parça gider:
(o,o,o,o) açılış tiki = karar anı, (o,h,l,c) = bar gövdesi; likidasyon stopu gövdede tetiklenir). fill="close" (eski, iyimser: karar barının
kapanışından) yalnızca testler içindir; `evaluate` reddeder. Son barın hedefi dolmaz. Likidasyondan sonra hesap ölü: yeni işlem yok (kalan marj likidasyon ücretiyle kaybedilir). Açık pozisyonun çıkış maliyeti (fee+slip) son kapanıştan
düşülür (close_out). Maliyet: taker fee + slippage
(bps, gidiş-dönüş; yan başına yarısı) Nautilus komisyonuna girer. Funding: T anındaki oran, T'den ÖNCE (T'de
yapılan dolumlardan önce) tutulan pozisyon x mark fiyat; işaret: oran>0 iken long öder. Likidasyon: Nautilus bar
verisinde likide etmiyor (tests/test_referee.py::test_nautilus_alone_does_not_liquidate); bu yüzden her pozisyon
değişiminde likidasyon fiyatında reduce-only STOP_MARKET konur (Nautilus bar içi H/L'de tetikler, tetik fiyatından doldurur).
Tetik MARK fiyatıyla: `mark` verilirse motora giden barların H/L'si mark H/L'sidir (O/C kline'dan; piyasa emirleri kapanıştan
dolar, etkilenmez). Nautilus'un MARK_PRICE tetikleyicisi bar/MarkPriceUpdate ile çalışmadı, bu yüzden bu yol seçildi.
"""
import math
from bisect import bisect_left
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

import numpy as np
import pandas as pd
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.execution import MakerTakerFeeModel
from nautilus_trader.model import (AccountType, AggregationSource, Bar, BarAggregation, BarSpecification, BarType,
                                   CryptoPerpetual, Currency, CurrencyType, InstrumentId, Money, OmsType, OrderSide,
                                   Price, PriceType, Quantity, Symbol, Venue)
from nautilus_trader.trading import Strategy

from kepler import tape

HOUR_NS = 3_600_000_000_000
USDT = Currency("USDT", 8, 0, "Tether", CurrencyType.CRYPTO)
BTC = Currency("BASE", 8, 0, "Base", CurrencyType.CRYPTO)
VENUE = Venue("BINANCE")


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
    native_liq: bool = False  # yalnızca test: Nautilus'un kendi liquidation_enabled'ı (bar verisinde işe yaramadığını belgeler)
    liq_fee_rate: float | None = None  # None -> mmr (kalan bakım marjı kaybedilir; gerçek Binance ücreti UNKNOWN); motorun taker fee'si bunun İÇİNDE sayılır (çifte sayım yok)
    fill: str = "next_open"  # "next_open" | "close" (yalnızca test/eski)
    close_out: bool = True  # açık pozisyonu son kapanıştan çıkış fee+slip ile değerle


def ns(index) -> list[int]:
    return [int(x) for x in pd.DatetimeIndex(index).as_unit("ns").asi8]


def _dp(s: str) -> int:
    return max(0, -Decimal(s).as_tuple().exponent)


def liq_price(q: Decimal, entry: float, wb: float, mmr: float) -> float | None:
    """Tek sembol, cross: özsermaye = WB + q(P-E) <= mmr*|q|*P. Likidasyon yok (None) ise kaldıraçsız/güvenli."""
    qf = float(q)
    p = (qf * entry - wb) / (qf * (1 - mmr)) if qf > 0 else (wb - qf * entry) / (-qf * (1 + mmr))
    return p if p > 0 else None


class Adapter(Strategy):
    def __new__(cls, *args):  # PyO3 Strategy.__new__ en çok 1 konumsal argüman kabul eder
        return super().__new__(cls)

    def __init__(self, iid, spec: Spec, targets: dict[int, float]):
        super().__init__(None)
        self.iid, self.spec, self.targets = iid, spec, targets
        self.bt = BarType(iid, BarSpecification(1, BarAggregation.HOUR, PriceType.LAST), AggregationSource.EXTERNAL)
        self.step, self.tick = Decimal(spec.step), Decimal(spec.tick)
        self.before, self.fills, self.rejected, self.stops, self.last = {}, [], [], set(), 0.0
        self.split, self.dead = spec.fill == "next_open", False  # dead: likidasyondan sonra hesap sıfırlandı, işlem yok

    def pos(self) -> Decimal:
        return sum((Decimal(str(p.signed_qty)).quantize(self.step) for p in self.cache.positions_open()), Decimal(0))  # float gürültüsünü at

    def on_start(self):
        self.subscribe_bars(self.bt)

    def on_bar(self, bar):
        t, pos, px = bar.ts_event, self.pos(), Decimal(str(bar.close))
        if self.split and t % HOUR_NS:  # bar gövdesi (ts = kapanış-1ns): karar yok; funding anı T = kapanış
            self.before[t + 1] = pos  # funding için: bu barın içindeki likidasyonlar düşülmüş, T'deki kararlardan önceki pozisyon
            return
        self.before[t] = pos  # (karar öncesi; açılış tikinde de tutulur: boşluktan sonraki ilk bar için funding anı doğru pozisyonu görür)
        if self.dead:
            return
        tgt = self.targets.get(t)
        if tgt is None or math.isnan(tgt) or tgt == self.last:  # hedef değişmedikçe yeniden boyutlama yok (fiyat gürültüsü churn yapmasın)
            return
        self.last = tgt
        want = (Decimal(str(tgt)) / px).quantize(self.step, rounding=ROUND_DOWN) if tgt >= 0 else -(Decimal(str(-tgt)) / px).quantize(self.step, rounding=ROUND_DOWN)
        delta = want - pos
        reducing = want == 0 or (want * pos > 0 and abs(want) < abs(pos))
        if delta == 0 or (not reducing and abs(delta) * px < Decimal(str(self.spec.min_notional))):
            return
        self.submit_order(self.order_factory.market(self.iid, OrderSide.BUY if delta > 0 else OrderSide.SELL, Quantity.from_str(format(abs(delta), "f"))))

    def on_order_filled(self, e):
        liq = str(e.client_order_id) in self.stops
        self.dead |= liq
        self.fills.append(dict(ts=e.ts_event, side=str(e.order_side), qty=float(e.last_qty), px=float(e.last_px), commission=float(e.commission), liq=liq))
        self.cancel_all_orders(self.iid)
        pos = self.pos()
        if self.spec.liq and pos != 0 and not liq:
            position = self.cache.positions_open()[0]
            wb = float(self.portfolio.account(VENUE).balance_total(USDT))
            lp = liq_price(pos, float(position.avg_px_open), wb, self.spec.mmr)
            if lp is not None:
                stop_px = Price.from_str(str(Decimal(str(lp)).quantize(self.tick)))
                order = self.order_factory.stop_market(self.iid, OrderSide.SELL if pos > 0 else OrderSide.BUY, Quantity.from_str(format(abs(pos), "f")), stop_px, reduce_only=True)
                self.stops.add(str(order.client_order_id))
                self.submit_order(order)

    def on_order_rejected(self, e):
        self.rejected.append(str(e))

    def on_order_denied(self, e):
        self.rejected.append(str(e))


def run(kl: pd.DataFrame, target: pd.Series, spec: Spec = Spec(), funding: pd.DataFrame | None = None, mark: pd.DataFrame | None = None) -> dict:
    """kl: ts(bar açılışı, UTC) indeksli open/high/low/close/volume. Dönüş: {'summary', 'fills', 'rejected'}."""
    if not (kl.index.is_monotonic_increasing and kl.index.is_unique):
        raise ValueError("kl indeksi artan ve tekil olmalı")
    if len(kl) == 0 or any(d % HOUR_NS for d in np.diff(ns(kl.index))) or ns(kl.index)[0] % HOUR_NS:
        raise ValueError("kl boş ya da saatlik hizalı değil")
    tape.check_target(kl, target)  # yanlış hizalı/tz'siz hedef sessizce sıfır işleme dönüşmesin
    if funding is not None and funding["last_funding_rate"].isna().any():
        raise ValueError("funding oranında NaN var (QC'den geçmemiş veri)")
    pp, sp = _dp(spec.tick), _dp(spec.step)
    iid = InstrumentId(Symbol("SYM-PERP"), VENUE)
    if spec.fill not in ("next_open", "close"):
        raise ValueError("fill next_open veya close olmalı")
    side_fee = (spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4
    inst = CryptoPerpetual(iid, Symbol("SYM"), BTC, USDT, USDT, False, pp, sp, Price.from_str(spec.tick), Quantity.from_str(spec.step), 0, 0,
                           margin_init=Decimal(1) / spec.leverage, margin_maint=Decimal(str(spec.mmr)), maker_fee=Decimal(str(side_fee)), taker_fee=Decimal(str(side_fee)))
    eng = BacktestEngine(BacktestEngineConfig(bypass_logging=True))
    eng.add_venue(VENUE, OmsType.NETTING, AccountType.MARGIN, [Money(spec.capital, USDT)], base_currency=USDT,
                  default_leverage=Decimal(spec.leverage), fee_model=MakerTakerFeeModel(), bar_execution=True,
                  liquidation_enabled=spec.native_liq)
    eng.add_instrument(inst)
    open_ns = ns(kl.index)
    close_ns = [t + HOUR_NS for t in open_ns]
    slots, tg = (open_ns if spec.fill == "next_open" else close_ns), {}
    for k, v in zip(close_ns, target.astype(float)):  # karar anı k (t barı kapanışı) -> ilk dolum anı (sonraki barın açılışı; boşlukta sonraki mevcut bar)
        i = bisect_left(slots, k)
        if i < len(slots) and not math.isnan(v):
            tg[slots[i]] = v
    strat = Adapter(iid, spec, tg)
    f = lambda v, d: Price.from_str(f"{v:.{d}f}")  # noqa: E731
    hi, lo = kl.high, kl.low
    if mark is not None and {"high", "low"} <= set(mark.columns):  # likidasyon stopu MARK fiyatının H/L'siyle tetiklenir (Binance); eksik mark barında kline H/L
        hi, lo = mark.high.reindex(kl.index).fillna(kl.high), mark.low.reindex(kl.index).fillna(kl.low)
    hi, lo = pd.concat([hi, kl.open, kl.close], axis=1).max(axis=1), pd.concat([lo, kl.open, kl.close], axis=1).min(axis=1)  # O/C [L,H] içinde kalsın
    bs = lambda o, h, l, c, v, t: Bar(strat.bt, f(o, pp), f(h, pp), f(l, pp), f(c, pp), Quantity.from_str(f"{v:.{sp}f}"), t, t)  # noqa: E731,E741
    rows = list(zip(kl.open, hi, lo, kl.close, kl.volume, open_ns, close_ns))
    eng.add_data([b for o, h, l, c, v, t0, t1 in rows for b in ((bs(o, o, o, o, v, t0), bs(o, h, l, c, v, t1 - 1)) if spec.fill == "next_open" else (bs(o, h, l, c, v, t1),))])
    eng.add_strategy(strat)
    eng.run()
    bal = float(eng.portfolio.account(VENUE).balance_total(USDT))
    open_pos = eng.cache.positions_open()
    unreal = sum(float(p.signed_qty) * (float(kl.close.iloc[-1]) - float(p.avg_px_open)) for p in open_pos)
    end_pos = float(strat.pos())  # dispose'dan önce (sonra cache boşalır)
    pr = eng.generate_positions_report()
    positions = pd.DataFrame({"opened": pr.ts_opened, "closed": pr.ts_closed, "realized": pr.realized_pnl.map(lambda m: float(str(m).split()[0]))}).reset_index(drop=True) if len(pr) else pd.DataFrame(columns=["opened", "closed", "realized"])
    eng.dispose()
    fills = pd.DataFrame(strat.fills, columns=["ts", "side", "qty", "px", "commission", "liq"]).astype({"qty": float, "px": float, "commission": float, "liq": bool})
    notional = (fills.qty * fills.px).sum()
    fee, slip = notional * spec.fee_rt_bps / 2 / 1e4, notional * spec.slip_rt_bps / 2 / 1e4
    lq = fills[fills.liq]
    liq_fee = float((lq.qty * lq.px).sum()) * max(0.0, (spec.mmr if spec.liq_fee_rate is None else spec.liq_fee_rate) - side_fee)  # motor taker fee'yi zaten kesti
    exit_cost = abs(end_pos) * float(kl.close.iloc[-1]) * side_fee if spec.close_out else 0.0
    fund, missed, fallback = 0.0, 0, 0
    if funding is not None and len(funding):
        mk = (mark if mark is not None else kl).close.astype(float)
        by_close = dict(zip([t + HOUR_NS for t in ns(mk.index)], mk))  # T'de biten barın mark kapanışı
        keys = sorted(strat.before)
        for ts, rate in zip(ns(pd.DatetimeIndex(funding.index).round("1min")), funding["last_funding_rate"].astype(float)):
            if not close_ns[0] <= ts <= close_ns[-1]:
                continue
            j = bisect_left(keys, ts)  # T'de bar yoksa (boşluk) pozisyon bir sonraki barın öncesidir: boşlukta dolum olmaz
            c = by_close.get(ts, math.nan)
            if math.isnan(c) and mark is not None:  # mark barı eksik (gerçek veri: BTC'de 3 boşluk): kline kapanışına düş, özette say
                c = float(kl.close.get(pd.Timestamp(ts, unit="ns", tz="UTC") - pd.Timedelta("1h"), math.nan))
                fallback += not math.isnan(c)
            if math.isnan(c) or j == len(keys):
                missed += 1  # mark da kline da yok: sessizce atlanmaz, özette sayılır
                continue
            fund += -float(strat.before[keys[j]]) * c * rate
    net = bal + unreal - spec.capital + fund - liq_fee - exit_cost
    return dict(summary=dict(net_pnl=net, gross_pnl=net + fee + slip + exit_cost - fund + liq_fee, fee=fee, slippage=slip, funding=fund, liq_fee=liq_fee, exit_cost=exit_cost,
                             n_fills=len(fills), n_liq=int(fills.liq.sum()), end_position=end_pos, engine_commission=float(fills.commission.sum()),
                             n_rejected=len(strat.rejected), funding_missed=missed, funding_mark_fallback=fallback),
                fills=fills, positions=positions, rejected=strat.rejected)
