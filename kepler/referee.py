"""C2: hakem motor = NautilusTrader 2.0.0rc5 + ince yapıştırma (hedef→emir, likidasyon stopu, funding).

Sözleşme: target[t] = t barı (açılış zamanı t) KAPANDIĞINDA istenen işaretli notional (USDT); NaN = mevcut pozisyonu tut.
Miktar yalnızca hedef DEĞİŞTİĞİNDE dolum fiyatından yeniden hesaplanır (lot adımına aşağı yuvarlanır); aynı hedef sürdükçe işlem yok.
Dolum (varsayılan fill="next_open"): karar t barının kapanışında bilinir, SONRAKİ barın açılış fiyatından dolar (her bar motora iki parça gider:
(o,o,o,o) açılış tiki = karar anı, (o,h,l,c) = bar gövdesi; likidasyon stopu gövdede tetiklenir). fill="close" (eski, iyimser: karar barının
kapanışından) yalnızca testler içindir; `evaluate` reddeder. Son barın hedefi dolmaz. Likidasyondan sonra hesap ölü: yeni işlem yok (kalan marj likidasyon ücretiyle kaybedilir). Açık pozisyonun çıkış maliyeti (fee+slip) son kapanıştan
düşülür (close_out). Maliyet: taker fee + slippage
(bps, gidiş-dönüş; yan başına yarısı) Nautilus komisyonuna girer. Funding: T anındaki oran, T'den ÖNCE (T'de
yapılan dolumlardan önce) tutulan pozisyon x mark fiyat; işaret: oran>0 iken long öder. Funding SETTLEMENT ANINDA, tek kez uygulanır:
Adapter.cash (funding nakit akışı) equity()'ye ve likidasyon fiyatının cüzdan bakiyesine girer; sıra: (1) önceki barın gövdesindeki stop/likidasyon, (2) T'deki
funding (karardan önceki pozisyon), (3) koruyucu emirlerin yeni bakiyeyle yeniden kurulması (özsermaye bakım marjının altına inmişse reduce-only market ile
kapanır, likidasyon sayılır), (4) T'deki kararlar/dolumlar. Net PnL'de funding bir kez sayılır (Nautilus bakiyesi funding'i görmez; koşu sonunda cash eklenir). Likidasyon: Nautilus bar
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
from nautilus_trader.common import LoggerConfig
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
    delay: int = 0  # ek gecikme (bar): dolum karardan sonraki (1 + delay). mevcut barda; stres testi (K3)
    gross_cap: float | None = None  # toplam brüt notional tavanı (USDT); artıran emir kalan alana küçülür (portföy, §6.5)
    equity_scale: bool = False  # True: yeni/değişen hedef notional (ve gross_cap) x equity / capital, equity = bakiye + gerçekleşmemiş PnL, emir anında (BACKTEST §5.1)


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
    """Çok sembollü hedef→emir adaptörü. B[k] = dict(iid, bt, step, tick, tg {slot_ns: hedef notional}, st {slot_ns: stop seviyesi}); k = sembol adı."""
    def __new__(cls, *args):  # PyO3 Strategy.__new__ en çok 1 konumsal argüman kabul eder
        return super().__new__(cls)

    def __init__(self, B: dict, spec: Spec):
        super().__init__(None)
        self.B, self.spec, self.fills, self.rejected, self.split = B, spec, [], [], spec.fill == "next_open"
        self.q, self.last, self.px = {k: Decimal(0) for k in B}, dict.fromkeys(B, 0.0), {}  # q: fill olaylarından beslenen imzalı miktar
        self.stop, self.lvl, self.prot = dict.fromkeys(B, math.nan), {}, set()  # strateji stopu; (stop, LP) koruyucu seviyeler; koruyucu emir kimlikleri
        self.cash, self.cash_ref, self.mc, self.fund_i = 0.0, 0.0, {}, dict.fromkeys(B, 0)  # settlement'ta uygulanmış funding toplamı (USDT); cash_ref: son tam likidasyon-fiyatı taramasındaki cash; mc: sembol başına açık pozisyon başlangıç marjı (yalnız dolumda değişir); sembol başına bir sonraki işlenecek funding indeksi
        self.missed = self.fallback = 0
        self.halt, self.dead = {}, set()  # halt[k]: stop sonrası yön, hedef yönü değişene kadar yeniden giriş yok; dead: likide olan sembol, işlem yok

    def pos(self, k) -> Decimal:
        return self.q[k]  # fill olaylarından beslenen imzalı miktar (cache sorgusu yok)

    def equity(self) -> float:
        """Bakiye + uygulanmış funding + gerçekleşmemiş PnL (son görülen fiyatla). Likidasyon ücreti farkı ve çıkış maliyeti koşu sonunda eklenir, bu yüzden equity - capital hakem net'inden bu kalemler kadar farklıdır."""
        return float(self.cache.account_for_venue(VENUE).balance_total(USDT)) + self.cash + sum(float(self.pos(j)) * (self.px[j] - float(self.cache.positions_open(instrument_id=self.B[j]["iid"])[0].avg_px_open))
                                                                                  for j in self.B if self.pos(j) != 0 and self.px.get(j))

    def settle(self, k, te, pos):
        """k sembolünün zamanı <= te olan bekleyen funding olaylarını `pos` pozisyonu (karar öncesi) ve mark kapanışıyla BİR KEZ uygular. Sıfır olmayan tutar varsa koruyucu emirler yeni bakiyeyle yeniden kurulur."""
        ev, i, hit = self.B[k]["fund"], self.fund_i[k], False
        while i < len(ev) and ev[i][0] <= te:
            _, rate, c, fb = ev[i]
            i += 1
            if math.isnan(c):
                self.missed += 1  # mark da kline da yok: sessizce atlanmaz, özette sayılır
                continue
            self.fallback += fb
            self.cash += (amt := -float(pos) * c * rate)
            hit |= amt != 0
        self.fund_i[k] = i
        if hit:  # bakiye değişti: funding'i alan sembolün likidasyon seviyesi yeni bakiyeyle yeniden kurulur; seviye > %0,2 kaymadıysa dokunulmaz (O(olay x pozisyon) emir fırtınası olmasın)
            self._relevel(k)
            if abs(self.cash - self.cash_ref) > 0.002 * self.spec.capital:  # ortak cüzdan: diğer açık pozisyonlar yalnız cash belirgin kaydığında toplu taranır
                self.cash_ref = self.cash
                for j in [j for j, v in self.mc.items() if v and j != k]:
                    self._relevel(j)

    def _relevel(self, j):
        q, px = self.pos(j), self.px.get(j)
        if j in self.dead or q == 0 or not px:
            return
        lp, old = self._lp(j, q), self.lvl.get(j, (None, None))[1]
        if lp is None or old is None or abs(lp - old) > 0.002 * px:
            self.refresh(j, px)

    def on_start(self):
        for b in self.B.values():
            self.subscribe_bars(b["bt"])

    def on_bar(self, bar):
        k, t, c = bar.bar_type.instrument_id.symbol.value, bar.ts_event, float(bar.close)
        self.px[k] = c
        pos = self.q[k]
        if self.split and t % HOUR_NS:  # bar gövdesi (ts = kapanış-1ns): karar yok; funding anı T = kapanış (O(1): yalnızca sözlük okuma/yazma)
            self.settle(k, t + 1, pos)  # funding anı T = t+1: bu barın içindeki stop/likidasyonlar düşülmüş, T'deki kararlardan önceki pozisyon
            return
        b, px = self.B[k], Decimal(str(bar.close))
        self.settle(k, t, pos)  # açılış tiki (karar öncesi): gövdede uygulanmamış funding (boşluk) bu pozisyonla; gövdede işlenenler tekrar uygulanmaz
        if k in self.dead:
            return
        old, new = self.stop[k], b["st"].get(t, self.stop[k])
        self.stop[k] = new
        tgt, sent = b["tg"].get(t), False
        if tgt is not None and not math.isnan(tgt):
            d = (tgt > 0) - (tgt < 0)
            if self.halt.get(k) not in (None, d):
                del self.halt[k]  # ters ya da flat sinyal: stop kilidi açılır
            if k not in self.halt and tgt != self.last[k]:  # hedef değişmedikçe yeniden boyutlama yok (fiyat gürültüsü churn yapmasın)
                self.last[k] = tgt
                f = max(self.equity() / self.spec.capital, 0.0) if self.spec.equity_scale else 1.0
                want = (Decimal(str(abs(tgt) * f)) / px).quantize(b["step"], rounding=ROUND_DOWN) * d
                if self.spec.gross_cap and abs(want) > abs(pos):  # toplam brüt tavan: artıran emir kalan alana küçülür
                    room = self.spec.gross_cap * f - sum(abs(float(self.pos(j))) * self.px[j] for j in self.B if j != k and self.px.get(j))
                    want = max(min(abs(want), (Decimal(str(max(room, 0.0))) / px).quantize(b["step"], rounding=ROUND_DOWN)), abs(pos) if pos * d > 0 else 0) * d  # mevcut pozisyon küçülmez
                delta = want - pos
                reducing = want == 0 or (want * pos > 0 and abs(want) < abs(pos))
                if delta != 0 and (reducing or abs(delta) * px >= Decimal(str(self.spec.min_notional))):
                    self.submit_order(self.order_factory.market(b["iid"], OrderSide.BUY if delta > 0 else OrderSide.SELL, Quantity.from_str(format(abs(delta), "f"))))
                    sent = True
        if not sent and not (old == new or (math.isnan(old) and math.isnan(new))):  # emir gitmediyse yeni stop seviyesini bar açılışında kur
            self.refresh(k, c)

    def _lp(self, k, q):
        """k sembolünün likidasyon fiyatı: ortak cüzdan (bakiye + uygulanmış funding − DİĞER pozisyonların başlangıç marjı; self.mc), tek sembol cross formülü."""
        m = self.mc
        position = self.cache.positions_open(instrument_id=self.B[k]["iid"])[0]
        wb = float(self.cache.account_for_venue(VENUE).balance_total(USDT)) + self.cash - (sum(m.values()) - m.get(k, 0.0))
        return liq_price(q, float(position.avg_px_open), wb, self.spec.mmr) if self.spec.liq else None

    def refresh(self, k, px):
        """Sembol başına TEK koruyucu emir: stop ile likidasyon fiyatından fiyata YAKIN olanı (aynı tikte iki stop'un sırası belirsiz olmasın; yakın olan fiyat yolunda önce vurulur).
        Seviye px'in ötesindeyse (açılış gap'i) piyasa emriyle hemen kapanır (dolum açılış fiyatından)."""
        b, q = self.B[k], self.pos(k)
        self.cancel_all_orders(b["iid"])
        if q == 0 or k in self.dead:
            return
        lp = self._lp(k, q)
        q_ = lambda v: None if v is None or math.isnan(v) else float(Decimal(str(v)).quantize(b["tick"]))  # noqa: E731
        s, lp = q_(self.stop[k]), q_(lp)
        lvls = [v for v in (s, lp) if v is not None]
        if not lvls:
            return
        lvl = max(lvls) if q > 0 else min(lvls)
        self.lvl[k] = (s, lp)
        side, qty = (OrderSide.SELL if q > 0 else OrderSide.BUY), Quantity.from_str(format(abs(q), "f"))
        order = (self.order_factory.market(b["iid"], side, qty, reduce_only=True) if (px <= lvl if q > 0 else px >= lvl)
                 else self.order_factory.stop_market(b["iid"], side, qty, Price.from_str(f"{lvl:.{b['dp']}f}"), reduce_only=True))
        self.prot.add(str(order.client_order_id))
        self.submit_order(order)

    def on_order_filled(self, e):
        k, p = e.instrument_id.symbol.value, float(e.last_px)
        self.q[k] += Decimal(str(float(e.last_qty))).quantize(self.B[k]["step"]) * (1 if e.order_side == OrderSide.BUY else -1)
        prot, sell = str(e.client_order_id) in self.prot, e.order_side == OrderSide.SELL
        lp = self.lvl.get(k, (None, None))[1]
        liq = prot and lp is not None and (p <= lp if sell else p >= lp)  # koruyucu emir LP'de ya da ötesinde dolduysa likidasyon, değilse strateji stopu
        if liq:
            self.dead.add(k)
        elif prot:
            self.halt[k] = 1 if sell else -1
        self.fills.append(dict(sym=k, ts=e.ts_event, side=str(e.order_side), qty=float(e.last_qty), px=p, commission=float(e.commission), liq=liq, stop=prot and not liq))
        o = self.cache.order(e.client_order_id)
        if o is None or o.is_closed:  # kısmi dolumda (hacim sınırı) emir hâlâ açıksa yeni emir kurma: kalan miktar aynı emirle dolar
            self.refresh(k, p)

    def on_order_rejected(self, e):
        self.rejected.append(str(e))

    def on_order_denied(self, e):
        self.rejected.append(str(e))


def run(kl: pd.DataFrame, target: pd.Series, spec: Spec = Spec(), funding: pd.DataFrame | None = None, mark: pd.DataFrame | None = None, stop: pd.Series | None = None) -> dict:
    """Tek sembol = run_portfolio'nun tek sembollü hali. kl: ts(bar açılışı, UTC) indeksli open/high/low/close/volume. Dönüş: {'summary', 'fills', 'rejected'}."""
    return run_portfolio({"SYM": dict(kl=kl, target=target, funding=funding, mark=mark, stop=stop)}, spec)


def run_portfolio(data: dict[str, dict], spec: Spec = Spec()) -> dict:
    """Tek Nautilus motoru, tek USDT hesap, ortak marj. data[sym] = dict(kl, target, funding=None, mark=None, stop=None, tick=None, step=None).
    stop[t] = t kapanışında bilinen koruyucu stop fiyatı (NaN = stop yok), t+1 açılışından itibaren geçerli. Sembol başına likidasyon (cross-margin likidasyonu yok)."""
    if spec.fill not in ("next_open", "close"):
        raise ValueError("fill next_open veya close olmalı")
    side_fee = (spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4
    eng = BacktestEngine(BacktestEngineConfig(bypass_logging=True, logging=LoggerConfig(bypass_logging=True)))
    eng.add_venue(VENUE, OmsType.NETTING, AccountType.MARGIN, [Money(spec.capital, USDT)], base_currency=USDT,
                  default_leverage=Decimal(spec.leverage), fee_model=MakerTakerFeeModel(), bar_execution=True, liquidation_enabled=spec.native_liq)
    B, bars_, f = {}, [], lambda v, d: Price.from_str(f"{v:.{d}f}")  # noqa: E731
    for sym, d in data.items():
        kl, target, funding = d["kl"], d["target"], d.get("funding")
        if not (kl.index.is_monotonic_increasing and kl.index.is_unique):
            raise ValueError("kl indeksi artan ve tekil olmalı")
        if len(kl) == 0 or any(x % HOUR_NS for x in np.diff(ns(kl.index))) or ns(kl.index)[0] % HOUR_NS:
            raise ValueError("kl boş ya da saatlik hizalı değil")
        tape.check_target(kl, target)  # yanlış hizalı/tz'siz hedef sessizce sıfır işleme dönüşmesin
        if funding is not None and funding["last_funding_rate"].isna().any():
            raise ValueError("funding oranında NaN var (QC'den geçmemiş veri)")
        tick, step = d.get("tick") or spec.tick, d.get("step") or spec.step
        pp, sp = _dp(tick), _dp(step)
        iid = InstrumentId(Symbol(f"{sym}-PERP"), VENUE)
        eng.add_instrument(CryptoPerpetual(iid, Symbol(sym), BTC, USDT, USDT, False, pp, sp, Price.from_str(tick), Quantity.from_str(step), 0, 0, margin_init=Decimal(1) / spec.leverage,
                                           margin_maint=Decimal(str(spec.mmr)), maker_fee=Decimal(str(side_fee)), taker_fee=Decimal(str(side_fee))))
        open_ns = ns(kl.index)
        close_ns = [t + HOUR_NS for t in open_ns]
        slots = open_ns if spec.fill == "next_open" else close_ns
        tg, st = {}, {}
        for k_, v, sv in zip(close_ns, target.astype(float), (d.get("stop") if d.get("stop") is not None else pd.Series(math.nan, index=kl.index)).astype(float)):  # karar anı k_ -> ilk dolum anı (sonraki barın açılışı; boşlukta sonraki mevcut bar)
            i = bisect_left(slots, k_) + spec.delay
            if i < len(slots):
                st[slots[i]] = sv
                if not math.isnan(v):
                    tg[slots[i]] = v
        bt = BarType(iid, BarSpecification(1, BarAggregation.HOUR, PriceType.LAST), AggregationSource.EXTERNAL)
        mark = d.get("mark")
        fund = []
        if funding is not None and len(funding):
            mk = (mark if mark is not None else kl).close.astype(float)
            by_close = dict(zip([t + HOUR_NS for t in ns(mk.index)], mk))  # T'de biten barın mark kapanışı
            for ts, rate in zip(ns(pd.DatetimeIndex(funding.index).round("1min")), funding["last_funding_rate"].astype(float)):
                if not close_ns[0] <= ts <= close_ns[-1]:
                    continue
                c, fb = by_close.get(ts, math.nan), 0
                if math.isnan(c) and mark is not None:  # mark barı eksik (gerçek veri: BTC'de 3 boşluk): kline kapanışına düş, özette say
                    c = float(kl.close.get(pd.Timestamp(ts, unit="ns", tz="UTC") - pd.Timedelta("1h"), math.nan))
                    fb = int(not math.isnan(c))
                fund.append((ts, rate, c, fb))
            fund.sort(key=lambda e: e[0])
        B[sym + "-PERP"] = dict(iid=iid, bt=bt, step=Decimal(step), tick=Decimal(tick), dp=pp, tg=tg, st=st, fund=fund)
        hi, lo = kl.high, kl.low
        if mark is not None and {"high", "low"} <= set(mark.columns):  # likidasyon stopu MARK fiyatının H/L'siyle tetiklenir (Binance); eksik mark barında kline H/L
            hi, lo = mark.high.reindex(kl.index).fillna(kl.high), mark.low.reindex(kl.index).fillna(kl.low)
        hi, lo = pd.concat([hi, kl.open, kl.close], axis=1).max(axis=1), pd.concat([lo, kl.open, kl.close], axis=1).min(axis=1)  # O/C [L,H] içinde kalsın
        bs = lambda o, h, l, c, v, t: Bar(bt, f(o, pp), f(h, pp), f(l, pp), f(c, pp), Quantity.from_str(f"{v:.{sp}f}"), t, t)  # noqa: E731,E741
        eng.add_data([b for o, h, l, c, v, t0, t1 in zip(kl.open, hi, lo, kl.close, kl.volume, open_ns, close_ns)
                      for b in ((bs(o, o, o, o, v, t0), bs(o, h, l, c, v, t1 - 1)) if spec.fill == "next_open" else (bs(o, h, l, c, v, t1),))])
    strat = Adapter(B, spec)
    eng.add_strategy(strat)
    eng.run()
    bal = float(eng.portfolio.account(VENUE).balance_total(USDT))
    unreal, end_pos = 0.0, {}
    for sym, d in data.items():
        k = sym + "-PERP"
        unreal += sum(float(p.signed_qty) * (float(d["kl"].close.iloc[-1]) - float(p.avg_px_open)) for p in eng.cache.positions_open(instrument_id=B[k]["iid"]))
        end_pos[sym] = float(strat.pos(k))  # dispose'dan önce (sonra cache boşalır)
    pr = eng.generate_positions_report()
    positions = pd.DataFrame({"opened": pr.ts_opened, "closed": pr.ts_closed, "realized": pr.realized_pnl.map(lambda m: float(str(m).split()[0]))}).reset_index(drop=True) if len(pr) else pd.DataFrame(columns=["opened", "closed", "realized"])
    eng.dispose()
    fills = pd.DataFrame(strat.fills, columns=["sym", "ts", "side", "qty", "px", "commission", "liq", "stop"]).astype({"qty": float, "px": float, "commission": float, "liq": bool, "stop": bool})
    fills["sym"] = fills.sym.str.removesuffix("-PERP")
    notional = (fills.qty * fills.px).sum()
    fee, slip = notional * spec.fee_rt_bps / 2 / 1e4, notional * spec.slip_rt_bps / 2 / 1e4
    lq = fills[fills.liq]
    liq_fee = float((lq.qty * lq.px).sum()) * max(0.0, (spec.mmr if spec.liq_fee_rate is None else spec.liq_fee_rate) - side_fee)  # motor taker fee'yi zaten kesti
    exit_cost = sum(abs(end_pos[s]) * float(d["kl"].close.iloc[-1]) * side_fee for s, d in data.items()) if spec.close_out else 0.0
    fund, missed, fallback = strat.cash, strat.missed + sum(len(B[k]['fund']) - strat.fund_i[k] for k in B), strat.fallback  # funding settlement anında uygulandı (Adapter.settle); bakiye Nautilus'ta değil, burada eklenir
    net = bal + unreal - spec.capital + fund - liq_fee - exit_cost
    return dict(summary=dict(net_pnl=net, gross_pnl=net + fee + slip + exit_cost - fund + liq_fee, fee=fee, slippage=slip, funding=fund, liq_fee=liq_fee, exit_cost=exit_cost,
                             n_fills=len(fills), n_liq=int(fills.liq.sum()), n_stop=int(fills.stop.sum()), end_position=next(iter(end_pos.values())) if len(end_pos) == 1 else sum(abs(v) for v in end_pos.values()),
                             engine_commission=float(fills.commission.sum()), n_rejected=len(strat.rejected), funding_missed=missed, funding_mark_fallback=fallback),
                fills=fills, positions=positions, rejected=strat.rejected)
