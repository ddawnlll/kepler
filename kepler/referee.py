"""Nautilus hakem: evaluate() denetler ve deftere yazar; run() muhasebe testleri içindir."""
# Hedef bar kapanınca bilinir; next_open izleyen gözlenmiş barın açılışında boyutlar/dolar.
# Açılış yalnızca o fiyatı içeren bir barla oynatılır, H/L daha sonra gelir (gelecek fitile bakmaz).
# Funding T'deki dolumdan önceki pozisyona uygulanır; settlement sırası UNKNOWN bir kabuldür.
# Slippage fiyat etkisi yerine notional maliyeti olarak komisyona girer (gidiş-dönüş bps / 2).
# Likidasyon MARK H/L stopu; gerçek likidasyon ücret/kademe tablosu UNKNOWN.
import math
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

import pandas as pd
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.execution import FeeModel
from nautilus_trader.model import (AccountType, AggregationSource, Bar, BarAggregation, BarSpecification, BarType,
                                   CryptoPerpetual, Currency, CurrencyType, InstrumentId, Money, OmsType, OrderSide,
                                   Price, PriceType, Quantity, Symbol, Venue)
from nautilus_trader.trading import Strategy

from kepler import audit, ledger, tape

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
    slip_rt_bps: float | None = None  # zorunlu açık seçim; sıfır yalnız close muhasebe fixture'ında
    fill_mode: str = "next_open"  # close: eski bilinen-cevaplı fixture'lar; evaluate() kabul etmez
    leverage: int = 10
    mmr: float = 0.005  # bakım marjı oranı (sembole/kademeye göre değişir; UNKNOWN: gerçek kademe tablosu alınmadı)
    capital: float = 500.0
    liq: bool = True
    native_liq: bool = False  # yalnızca test: Nautilus'un kendi liquidation_enabled'ı (bar verisinde işe yaramadığını belgeler)
    liq_fee_rate: float | None = None  # None -> mmr (kalan bakım marjı kaybedilir; gerçek Binance ücreti UNKNOWN)


def ns(index) -> list[int]:
    return [int(x) for x in pd.DatetimeIndex(index).as_unit("ns").asi8]


class Fees(FeeModel):
    def __new__(cls, spec):
        return super().__new__(cls)

    def __init__(self, spec):
        self.spec = spec

    def get_commission(self, order, fill_quantity, fill_px, instrument):
        rate = (self.spec.mmr if self.spec.liq_fee_rate is None else self.spec.liq_fee_rate) if order.is_reduce_only else self.spec.fee_rt_bps / 2 / 1e4
        return Money(float(fill_quantity) * float(fill_px) * (rate + self.spec.slip_rt_bps / 2 / 1e4), USDT)


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
        self.fills, self.rejected, self.stops, self.last = [], [], set(), 0.0

    def pos(self) -> Decimal:
        return sum((Decimal(str(p.signed_qty)).quantize(self.step) for p in self.cache.positions_open()), Decimal(0))  # float gürültüsünü at

    def on_start(self):
        self.subscribe_bars(self.bt)

    def on_bar(self, bar):
        t, pos, px = bar.ts_event, self.pos(), Decimal(str(bar.close))
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
    tape.check_target(kl, target)  # yanlış hizalı/tz'siz hedef sessizce sıfır işleme dönüşmesin
    if spec.fill_mode not in ("next_open", "close") or spec.slip_rt_bps is None or not math.isfinite(spec.slip_rt_bps) or spec.slip_rt_bps < 0:
        raise ValueError("fill_mode geçerli ve slippage açıkça verilmiş, sonlu, negatif olmayan bps olmalı")
    if spec.fill_mode == "next_open" and spec.slip_rt_bps == 0:
        raise ValueError("next_open pozitif slippage gerektirir")
    if funding is not None and funding["last_funding_rate"].isna().any():
        raise ValueError("funding oranında NaN var (QC'den geçmemiş veri)")
    pp, sp = (max(0, -Decimal(s).as_tuple().exponent) for s in (spec.tick, spec.step))
    iid = InstrumentId(Symbol("SYM-PERP"), VENUE)
    side_fee = (spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4
    inst = CryptoPerpetual(iid, Symbol("SYM"), BTC, USDT, USDT, False, pp, sp, Price.from_str(spec.tick), Quantity.from_str(spec.step), 0, 0,
                           margin_init=Decimal(1) / spec.leverage, margin_maint=Decimal(str(spec.mmr)), maker_fee=Decimal(str(side_fee)), taker_fee=Decimal(str(side_fee)))
    eng = BacktestEngine(BacktestEngineConfig(bypass_logging=True))
    eng.add_venue(VENUE, OmsType.NETTING, AccountType.MARGIN, [Money(spec.capital, USDT)], base_currency=USDT,
                  default_leverage=Decimal(spec.leverage), fee_model=Fees(spec), bar_execution=True,
                  liquidation_enabled=spec.native_liq)
    eng.add_instrument(inst)
    next_open = spec.fill_mode == "next_open"
    times, values = (ns(kl.index[1:]), target.iloc[:-1]) if next_open else (ns(kl.index), target)
    strat = Adapter(iid, spec, dict(zip([t + (1 if next_open else HOUR_NS) for t in times], values.astype(float))))
    close_ns = [t + HOUR_NS for t in ns(kl.index)]
    f = lambda v, d: Price.from_str(f"{v:.{d}f}")  # noqa: E731
    hi, lo = kl.high, kl.low
    if mark is not None and {"high", "low"} <= set(mark.columns):  # likidasyon stopu MARK fiyatının H/L'siyle tetiklenir (Binance); eksik mark barında kline H/L
        hi, lo = mark.high.reindex(kl.index).fillna(kl.high), mark.low.reindex(kl.index).fillna(kl.low)
    hi, lo = pd.concat([hi, kl.open, kl.close], axis=1).max(axis=1), pd.concat([lo, kl.open, kl.close], axis=1).min(axis=1)  # O/C [L,H] içinde kalsın
    bars = []
    for o, h, l, c, v, t in zip(kl.open, hi, lo, kl.close, kl.volume, close_ns):
        if next_open:
            opening = t - HOUR_NS + 1  # önceki bar kapanışı ve funding'den 1 ns sonra
            # Sabit sentetik derinlik: OHLC modunda hacim/slippage fiyat modeli yok; maliyet açık bps ile kesilir.
            bars.append(Bar(strat.bt, f(o, pp), f(o, pp), f(o, pp), f(o, pp), Quantity.from_str(f"{1e9:.{sp}f}"), opening, opening))
        bars.append(Bar(strat.bt, f(o, pp), f(h, pp), f(l, pp), f(c, pp), Quantity.from_str(f"{v:.{sp}f}"), t, t))
    eng.add_data(bars)
    eng.add_strategy(strat)
    eng.run()
    bal = float(eng.portfolio.account(VENUE).balance_total(USDT))
    open_pos = eng.cache.positions_open()
    unreal = sum(float(p.signed_qty) * (float(kl.close.iloc[-1]) - float(p.avg_px_open)) for p in open_pos)
    end_pos = float(strat.pos())  # dispose'dan önce (sonra cache boşalır)
    pr = eng.generate_positions_report()
    positions = pd.DataFrame({"opened": pd.to_datetime(pr.ts_opened, utc=True), "closed": pd.to_datetime(pr.ts_closed, utc=True), "realized": pr.realized_pnl.map(lambda m: float(str(m).split()[0]))}).reset_index(drop=True) if len(pr) else pd.DataFrame(columns=["opened", "closed", "realized"])
    eng.dispose()
    fills = pd.DataFrame(strat.fills, columns=["ts", "side", "qty", "px", "commission", "liq"]).astype({"qty": float, "px": float, "commission": float, "liq": bool})
    notional = (fills.qty * fills.px).sum()
    exit_notional = abs(end_pos) * float(kl.close.iloc[-1])
    exit_cost = exit_notional * side_fee  # açık pozisyonu son kapanıştan tasfiye etmenin fee+slippage karşılığı
    lq = fills[fills.liq]
    fee, slip = (notional + exit_notional - (lq.qty * lq.px).sum()) * spec.fee_rt_bps / 2 / 1e4, (notional + exit_notional) * spec.slip_rt_bps / 2 / 1e4
    liq_fee = float((lq.qty * lq.px).sum()) * (spec.mmr if spec.liq_fee_rate is None else spec.liq_fee_rate)
    fund, missed, fallback = 0.0, 0, 0
    if funding is not None and len(funding):
        mk = (mark if mark is not None else kl).close.astype(float)
        by_close = dict(zip([t + HOUR_NS for t in ns(mk.index)], mk))  # T'de biten barın mark kapanışı
        held = fills.qty.where(fills.side == "BUY", -fills.qty).cumsum()
        for ts, rate in zip(ns(pd.DatetimeIndex(funding.index).round("1min")), funding["last_funding_rate"].astype(float)):
            if not close_ns[0] <= ts <= close_ns[-1]:
                continue
            before = held[(fills.ts < ts) | ((fills.ts == ts) & fills.liq)]  # intrabar stop T'den önce; T dolumu settlement'tan sonra
            c = by_close.get(ts, math.nan)
            if math.isnan(c) and mark is not None:  # mark barı eksik (gerçek veri: BTC'de 3 boşluk): kline kapanışına düş, özette say
                c = float(kl.close.get(pd.Timestamp(ts, unit="ns", tz="UTC") - pd.Timedelta("1h"), math.nan))
                fallback += not math.isnan(c)
            if math.isnan(c):
                missed += 1  # mark da kline da yok: sessizce atlanmaz, özette sayılır
                continue
            fund += -float(before.iloc[-1] if len(before) else 0.0) * c * rate
    net = bal + unreal - spec.capital + fund - exit_cost
    return dict(summary=dict(net_pnl=net, gross_pnl=net + fee + slip - fund + liq_fee, fee=fee, slippage=slip, funding=fund, liq_fee=liq_fee,
                             n_fills=len(fills), n_liq=int(fills.liq.sum()), end_position=end_pos, engine_commission=float(fills.commission.sum()),
                             exit_cost=exit_cost, n_rejected=len(strat.rejected), funding_missed=missed, funding_mark_fallback=fallback),
                fills=fills, positions=positions, rejected=strat.rejected)


def evaluate(kl, signal, spec: Spec, ledger_path, hypothesis="", config=None, data_hash="", funding=None, mark=None):
    """G2 için tek giriş: sözleşme + nedensellik → gerçekçi hakem → geçerli sonuç deftere."""
    if spec.fill_mode != "next_open":
        raise ValueError("evaluate yalnız next_open kabul eder")
    target = tape.check_target(kl, signal(kl))
    audit.assert_causal(signal, kl)
    res = run(kl, target, spec, funding=funding, mark=mark)
    cfg = {**(config or {}), **spec.__dict__, "target_sha": ledger.sha(target.tolist())}
    code = ledger.code_hash(__file__, audit.__file__, tape.__file__, ledger.__file__, signal.__code__.co_filename)
    ledger.record(ledger_path, "referee", hypothesis, cfg, code, data_hash, result=res["summary"], _token=ledger._REFEREE_TOKEN)
    return res
