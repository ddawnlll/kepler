"""C3 + C5 gerçek dev verisinde (Modal: python scripts/g1_real.py corr|xcheck --root /data --out /data/reports).

corr  : eleme (vectorbt) ile hakem arasında sıralama korelasyonu; deney defterine yazar.
xcheck: tek sembol (BTCUSDT), basit sinyal: hakem ile bağımsız elle hesap arasında işlem başına net fark.
Sinyaller burada yalnızca TEST FIXTURE'ıdır (G2 sinyali değil)."""
import argparse
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import ledger, qc, referee, screen, tape

SYM = "BTCUSDT"
# Muhasebe/sıralama karşılaştırması için büyük sermaye: yüksek devirli fixture sinyalleri 500 USD'lik hesabı fee ile bitirir
# (ilk denemede INITIAL_MARGIN_EXCEEDS_FREE_BALANCE ile reddedilen binlerce emir -> geçersiz koşu). Sermaye PnL'yi değiştirmez.
SPEC = referee.Spec(tick="0.1", step="0.001", min_notional=100.0, fee_rt_bps=10.0, slip_rt_bps=2.0, capital=1_000_000.0)


def mom(kl, n, sign=1.0, size=1000.0):
    return pd.Series(np.where(kl.close > kl.close.shift(n), sign * size, -sign * size), index=kl.index).where(kl.close.shift(n).notna())


def trend_long(kl, n, size=1000.0):
    return pd.Series(np.where(kl.close > kl.close.rolling(n).mean(), size, 0.0), index=kl.index).where(kl.close.rolling(n).mean().notna())


def grid(kl):
    g = {f"mom{n}": mom(kl, n) for n in (6, 12, 24, 48, 96, 168)}
    g |= {f"rev{n}": mom(kl, n, -1.0) for n in (6, 12, 24, 48, 96, 168)}
    g |= {f"trend{n}": trend_long(kl, n) for n in (24, 72, 168, 336)}
    return g


def data_hash(root):
    return ledger.sha([qc.sha256_file(Path(root) / "tape" / k / f"{SYM}.parquet") for k in ("klines", "markPriceKlines", "fundingRate")])


def corr(root, out):
    t = tape.load(root, SYM, start="2022-01-01")
    kl, fund, mark = t["klines"], t["funding"], t["mark"]
    led, dh = Path(out) / "ledger.jsonl", data_hash(root)
    g = grid(kl)
    scr = screen.screen(kl, g, SPEC.fee_rt_bps, led, slip_rt_bps=SPEC.slip_rt_bps, capital=1e5, hypothesis="G1 eleme-hakem uyumu (fixture ızgarası)", data_hash=dh)
    ref = {}
    for name in g:
        signal = lambda frame: grid(frame)[name]
        r = referee.evaluate(kl, signal, SPEC, led, hypothesis="G1 eleme-hakem uyumu (fixture ızgarası)",
                             config=dict(name=name), data_hash=dh, funding=fund, mark=mark)
        s = r["summary"]
        ref[name] = s["net_pnl"]
    df = pd.DataFrame({"screen": scr, "referee": pd.Series(ref)}).dropna()
    rho = df.screen.corr(df.referee, method="spearman")
    md = ["# Eleme (vectorbt) ↔ hakem (Nautilus) uyumu", "", f"Sembol {SYM}, {kl.index[0].date()} → {kl.index[-1].date()}, {len(g)} fixture konfigürasyonu, gidiş-dönüş fee {SPEC.fee_rt_bps} bps.",
          f"**Spearman sıralama korelasyonu: {rho:.3f}** (öneri eşiği ≥0,8 — doğrulanmadı, eşik konmadı; yalnızca raporlanır). Pearson: {df.screen.corr(df.referee):.3f}.",
          "Fark kaynakları: eleme lot/min-notional yuvarlamasını, funding'i ve likidasyonu içermez; hakem içerir.", "",
          "| config | eleme PnL | hakem net PnL |", "|---|---|---|"] + [f"| {k} | {r.screen:.2f} | {r.referee:.2f} |" for k, r in df.sort_values("referee").iterrows()]
    md += ["", "Geçersiz koşu evaluate() tarafından reddedilir; böyle bir koşuda ızgara durur, kısmi korelasyon raporlanmaz."]
    Path(out, "screen_vs_referee.md").write_text("\n".join(md))
    print(f"spearman={rho:.3f} n={len(df)}")


def independent(kl, target, funding, mark, spec):
    """Nautilus'tan bağımsız elle hesap: ortalama maliyet muhasebesi, döngüde, Decimal. Dönüş: işlemler + toplam funding."""
    tick_fee = Decimal(str(spec.fee_rt_bps + spec.slip_rt_bps)) / 2 / 10000
    step = Decimal(spec.step)
    pos, avg, last = Decimal(0), Decimal(0), 0.0
    trades, cur, fund = [], None, 0.0
    events = sorted((t.round("1min"), float(r)) for t, r in funding["last_funding_rate"].items())
    mk = {t + pd.Timedelta("1h"): float(c) for t, c in mark.close.items()}  # T'de biten barın mark kapanışı
    kc = {t + pd.Timedelta("1h"): float(c) for t, c in kl.close.items()}
    first, j, missed = kl.index[0] + pd.Timedelta("1h"), 0, 0
    for i, t in enumerate([*kl.index, kl.index[-1] + pd.Timedelta("1h")]):
        terminal = i == len(kl)
        fill_ts = t + pd.Timedelta(1, unit="ns")
        px = Decimal(str(kl.close.iloc[-1] if terminal else kl.open.iloc[i]))
        while j < len(events) and events[j][0] <= t:  # settlement, aynı andaki açılış dolumundan önce
            T, rate = events[j]
            j += 1
            if T < first:
                continue
            m = mk.get(T, np.nan)
            if np.isnan(m):  # mark barı eksik: kline kapanışına düş (hakemle aynı kural)
                m = kc.get(T, np.nan)
            if np.isnan(m):
                missed += 1
                continue
            f = -float(pos) * m * rate  # T öncesi (bu barın kararlarından önceki) pozisyon: long öder (oran>0)
            fund += f
            if cur is not None:
                cur["funding"] += f
        tg = np.nan if i == 0 or terminal else target.iloc[i - 1]  # son kararın sonraki barı yok; dolmaz
        if np.isnan(tg) or tg == last:
            continue
        last = tg
        q = (Decimal(str(abs(tg))) / px).quantize(step, rounding=ROUND_DOWN) * (1 if tg >= 0 else -1)
        d = q - pos
        reducing = q == 0 or (q * pos > 0 and abs(q) < abs(pos))
        if d == 0 or (not reducing and abs(d) * px < Decimal(str(spec.min_notional))):
            continue
        fee = abs(d) * px * tick_fee
        sgn = 1 if d > 0 else -1
        c = min(abs(d), abs(pos)) if pos * d < 0 else Decimal(0)  # mevcut pozisyonu kapatan kısım
        o = abs(d) - c  # yeni pozisyon açan / artıran kısım (çevirmede c ve o birlikte)
        if c > 0:
            cur["net"] += float((px - avg) * c * (1 if pos > 0 else -1) - fee * c / abs(d))  # komisyon miktarla orantılı bölünür
            pos += sgn * c
            if pos == 0:
                cur["closed"] = fill_ts
                trades.append(cur)
                cur, avg = None, Decimal(0)
        if o > 0:
            if pos == 0:
                cur, avg = dict(opened=fill_ts, closed=pd.NaT, net=0.0, funding=0.0), px
            else:
                avg = (avg * abs(pos) + px * o) / (abs(pos) + o)
            cur["net"] -= float(fee * o / abs(d))
            pos += sgn * o
    if cur is not None:
        cur["net"] += float((Decimal(str(kl.close.iloc[-1])) - avg) * pos - abs(pos) * Decimal(str(kl.close.iloc[-1])) * tick_fee)
    return trades, fund, cur, missed


def xcheck(root, out):
    t = tape.load(root, SYM, start="2022-01-01")
    kl, fund, mark = t["klines"], t["funding"], t["mark"]
    tg = mom(kl, 24)
    r = referee.evaluate(kl, lambda frame: mom(frame, 24), SPEC, Path(out) / "xcheck_ledger.jsonl",
                         hypothesis="G1 xcheck fixture", data_hash=data_hash(root), funding=fund, mark=mark)
    trades, ifund, cur, imissed = independent(kl, tg, fund, mark, SPEC)
    if cur is not None:  # açık kalan son döngü
        trades.append(cur)
    ref = r["positions"].copy()
    ind = pd.DataFrame(trades)
    # Nautilus ts_closed 1 ns simülasyon ofsetini keser; işlem kimliği saniyede tekildir.
    for frame in (ref, ind):
        frame["closed"] = pd.to_datetime(frame.closed, utc=True).dt.floor("s")
    m = ref.merge(ind, on=["opened", "closed"], how="outer", suffixes=("_ref", "_ind"), indicator=True, validate="one_to_one")
    both = m[m._merge == "both"]
    closed = both[both.closed.notna()]  # açık son döngü toplam net kontrolüne DAHİL, realized karşılaştırmasına girmez
    diff = (closed.realized - closed.net).abs()
    s = r["summary"]
    total = sum(x["net"] for x in trades) + ifund
    assert (m._merge == "both").all() and abs(s["net_pnl"] - total) < 0.01, "xcheck eşleşme/toplam net farkı"
    flip = closed.opened.dt.floor("s").isin(set(ref.closed.dropna()))
    big = diff > 1e-6
    md = ["# Gerçek veri çapraz kontrolü (BTCUSDT, mom24 fixture, 1000 USDT notional)", "",
          f"Hakem işlem (pozisyon) sayısı {len(ref)}, bağımsız hesap {len(ind)}, eşleşen {len(both)}; eşleşmeyen {int((m._merge != 'both').sum())}.",
          f"**Kapalı işlem başına |net fark|: maks {diff.max():.6f} USDT, ort {diff.mean():.6f}** (net = brüt − fee − slippage; funding hariç).",
          f"|fark|>1e-6 olan {int(big.sum())} işlemin {int((big & flip).sum())}'i çevirme dolumunda açılmış; kapalı işlemlerde işaretli toplam fark {(closed.realized - closed.net).sum():.6f} USDT.",
          f"Funding toplamı: hakem {s['funding']:.6f}, bağımsız {ifund:.6f}, fark {s['funding'] - ifund:.2e} USDT; eksik funding olayı hakem {s['funding_missed']}, bağımsız {imissed}.",
          f"Hakem toplam net {s['net_pnl']:.4f}, bağımsız {total:.4f} (açık son döngü ve çıkış maliyeti dahil); fills {s['n_fills']}, likidasyon {s['n_liq']}, reddedilen emir {len(r['rejected'])}.", "",
          "Açıklama (varsayım, doğrulanmadı): fark neredeyse yalnızca çevirme (flip) dolumlarında; çevirmede komisyon iki pozisyona bölünür. Bağımsız hesap miktarla orantılı böler; "
          "Nautilus'un bölüşümü bundan ≤0,002 USDT/işlem sapıyor (muhtemelen farklı yuvarlama/ağırlık). Toplam komisyon iki tarafta aynı; fark yalnızca iki komşu pozisyon arasındaki paylaşımda.",
          "Sermaye bu karşılaştırma için 1.000.000 USDT: 500 USD'lik hesap bu yüksek devirli fixture ile fee'den iflas eder (ilk denemede INITIAL_MARGIN_EXCEEDS_FREE_BALANCE ile binlerce emir reddedildi). Sermaye PnL'yi değiştirmez."]
    Path(out, "xcheck_btc.md").write_text("\n".join(md))
    print(md[2], md[3], md[4], sep="\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["corr", "xcheck"])
    ap.add_argument("--root", default="/data")
    ap.add_argument("--out", default="/data/reports")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    {"corr": corr, "xcheck": xcheck}[a.cmd](a.root, a.out)
