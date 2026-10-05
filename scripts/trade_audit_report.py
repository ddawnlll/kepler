"""Trade denetimi, RAPOR AŞAMASI: scripts/trade_audit.py çıktısından (trades.csv, daily.csv, hourly.csv, meta.json ...) istatistikleri hesaplar, grafikleri çizer ve PDF üretir.
LLM yok: her rakam bu betikte tanımlı bir formülden gelir (tekrarlanabilir). Gereksinim: pandas, numpy, matplotlib, reportlab; Nautilus çapraz kontrolü için nautilus_trader (yoksa o bölüm atlanır).

  python scripts/trade_audit_report.py <veri dizini> <PDF yolu>     (veri dizini = modal volume get ile indirilmiş /data/audit/<ad>)
Palet: dataviz referans paleti (validate_palette.js ile doğrulandı: 4 kategorik slot, açık yüzey); gelir/zarar = mavi/kırmızı ıraksak çift, nötr gri."""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from reportlab.lib import colors as rc  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

SRC, PDF = Path(sys.argv[1]), Path(sys.argv[2])
FIG = PDF.parent / (PDF.stem + "_figs")
FIG.mkdir(parents=True, exist_ok=True)
BLUE, ORANGE, AQUA, YELLOW, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948"
INK, INK2, MUTED, GRID, AXIS, SURF, MID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb", "#f0efec"
FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DV", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False, "font.size": 8.5, "axes.titlesize": 10,
                     "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False})
DIV = LinearSegmentedColormap.from_list("div", [RED, MID, BLUE])

meta = json.loads((SRC / "meta.json").read_text())
CAP = meta["cap"]
tr = pd.read_csv(SRC / "trades.csv", parse_dates=["opened", "closed", "decision_day"])
daily = pd.read_csv(SRC / "daily.csv", index_col=0, parse_dates=True)
fills = pd.read_csv(SRC / "fills.csv")
hourly = pd.read_csv(SRC / "hourly.csv", index_col=0, parse_dates=True) if (SRC / "hourly.csv").exists() else None
S = meta["summary"]
NAMES = meta["names"]
STRESS = {k: (pd.Timestamp(v[0], tz="UTC"), pd.Timestamp(v[1], tz="UTC")) for k, v in meta["stress"].items()}
YEARS = (daily.index[-1] - daily.index[0]).days / 365.25
usd = lambda x: f"{x:,.2f}".replace(",", " ")  # noqa: E731
pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
pct3 = lambda x: f"{100 * x:.3f}%"  # noqa: E731


def sharpe_of(pnl, cap=CAP):
    e = cap + pnl.cumsum()
    r = pnl / e.shift(1).fillna(cap)
    pk = e.cummax()
    return float(r.mean() / r.std(ddof=1) * np.sqrt(365)), float(((pk - e) / pk).max())


def save(fig, name):
    p = FIG / f"{name}.png"
    fig.savefig(p, dpi=170, bbox_inches="tight", facecolor=SURF)
    plt.close(fig)
    return p


# ---------------------------------------------------------------- istatistikler
eq = daily.equity
ret = daily.net / eq.shift(1).fillna(CAP)
peak = eq.cummax()
dd_usd, dd_pct = peak - eq, (peak - eq) / peak
under = eq < peak
runs = (under != under.shift()).cumsum()
uw_days = int(under.groupby(runs).sum().max())
dd_peak_date, dd_trough_date = eq[:dd_pct.idxmax()].idxmax(), dd_pct.idxmax()
rec = eq[dd_trough_date:][eq[dd_trough_date:] >= eq[dd_peak_date]]
sharpe, vol = ret.mean() / ret.std(ddof=1) * np.sqrt(365), ret.std(ddof=1) * np.sqrt(365)
sortino = ret.mean() / np.sqrt((np.minimum(ret, 0) ** 2).mean()) * np.sqrt(365)
net_total = float(daily.net.sum())
cagr = (eq.iloc[-1] / CAP) ** (1 / YEARS) - 1
calmar = cagr / dd_pct.max()
month = daily.net.resample("MS").sum()
month_eq0 = eq.shift(1).fillna(CAP).resample("MS").first()
month_pct = month / month_eq0
week = daily.net.resample("W").sum()
week_pct = week / eq.shift(1).fillna(CAP).resample("W").first()
tr["net_pct_eq"] = tr.net / tr.eq_at_open
tr["bps"] = tr.net / tr.avg_notional * 1e4
tr["ym"] = tr.opened.dt.to_period("M")
win, loss = tr[tr.net > 0], tr[tr.net < 0]
per_month = tr.groupby("ym").size().reindex(pd.period_range(tr.ym.min(), tr.ym.max(), freq="M"), fill_value=0)
tr["plan_risk_pct"] = tr.avg_notional * tr.sigma / np.sqrt(365) / tr.eq_at_open  # planlanan risk: notional x 1 günlük 1σ / equity
tr["mae_pct_eq"] = tr.mae_bps / 1e4 * tr.avg_notional / tr.eq_at_open
side_fee = (S["fee"] + S["slippage"]) / max(S["fee"] + S["slippage"], 1e-12)
traded = float((fills.qty * fills.px).sum())
lev = daily.gross_lev_mean

import itertools  # noqa: E402

mx_streak0 = max((len(list(g)) for k, g in itertools.groupby((tr.net < 0).tolist()) if k), default=0)
# kayıp nedeni sınıflandırması (kural tabanlı; öncelik sırası; tanımlar PDF ekinde)
STRESS_HIT = lambda r: any((r.opened <= b) and (r.closed >= a) for a, b in STRESS.values())  # noqa: E731
flip = tr.groupby("sym", group_keys=False).apply(lambda g: (g.opened.shift(-1) - g.closed).dt.total_seconds().div(3600).le(24) & (g.side.shift(-1) != g.side) & g.opened.shift(-1).notna())
tr["flip_close"] = flip.reindex(tr.index).fillna(False)


tr["sig_bps"] = tr.sigma / np.sqrt(365) * 1e4  # giriş günü 1 günlük σ (bps)
tr["mfe_s"], tr["mae_s"] = tr.mfe_bps / tr.sig_bps, tr.mae_bps / tr.sig_bps  # MFE/MAE'nin günlük σ cinsinden (oynaklığa göre ölçekli eşik: sabit bps trend sisteminde her trade'e uyar)


def cause(r):
    if r.net >= 0:
        return None
    if r.price_pnl >= 0:
        return "1. Maliyet / funding yedi (brüt fiyat PnL ≥ 0)"
    if STRESS_HIT(r):
        return "2. Şok penceresi (LUNA / FTX / 2021-05)"
    if r.mfe_s >= 2.0:
        return "3. Büyük kârı geri verdi (MFE ≥ 2σ)"
    if r.mfe_s >= 0.5:
        return "4. Orta kârı geri verdi (0,5σ ≤ MFE < 2σ)"
    if r.hours <= 72:
        return "5. Hiç lehe gitmedi, kısa (whipsaw, ≤ 72 saat)"
    return "6. Hiç lehe gitmedi, uzun (trend yanlış, > 72 saat)"


tr["cause"] = tr.apply(cause, axis=1)
win, loss = tr[tr.net > 0], tr[tr.net < 0]  # yeni sütunlarla (mfe_s, cause) yeniden
cause_tab = tr[tr.net < 0].groupby("cause").agg(n=("net", "size"), total=("net", "sum"), avg=("net", "mean"), hours=("hours", "median")).sort_index()
drive = tr[[f"c_{n}" for n in NAMES]].idxmax(axis=1).str[2:]
tr["driver"] = drive

# Nautilus çapraz kontrolü (bağımsız hesaplayıcılar; yoksa atlanır)
naut = None
try:
    from nautilus_trader import analysis as an

    npos = pd.read_csv(SRC / "nautilus_positions.csv")
    mine_nb = (tr.price_pnl - tr.commission).to_numpy()  # Nautilus realized: fiyat - komisyon (funding hakem tarafında, Nautilus dışında)
    rd = {int(t.value): float(v) for t, v in ret.items()}
    ours = dict(win_rate=float((mine_nb > 0).mean()), expectancy=float(mine_nb.mean()), avg_winner=float(mine_nb[mine_nb > 0].mean()), sharpe=float(sharpe), sortino=float(sortino), maxdd=float(dd_pct.max()), vol=float(vol))
    naut = dict(win_rate=float(an.WinRate().calculate_from_realized_pnls(npos.realized.to_numpy())), expectancy=float(an.Expectancy().calculate_from_realized_pnls(npos.realized.to_numpy())),
                avg_winner=float(an.AvgWinner().calculate_from_realized_pnls(npos.realized.to_numpy())), sharpe=float(an.SharpeRatio(365).calculate_from_returns(rd)),
                sortino=float(an.SortinoRatio(365).calculate_from_returns(rd)), maxdd=float(abs(an.MaxDrawdown().calculate_from_returns(rd))), vol=float(an.ReturnsVolatility(365).calculate_from_returns(rd)))
    n_naut = len(npos)
except Exception as e:  # noqa: BLE001
    ours, n_naut = None, None
    print("Nautilus çapraz kontrolü atlandı:", repr(e)[:120])

# ---------------------------------------------------------------- grafikler
figs = {}
fig, ax = plt.subplots(2, 1, figsize=(9, 4.0), sharex=True, gridspec_kw=dict(height_ratios=[2.2, 1]))
ax[0].plot(eq.index, eq, color=BLUE, lw=1.4)
ax[0].axhline(CAP, color=AXIS, lw=0.8)
ax[0].set_ylabel("Equity (USDT)")
ax[0].set_title("Equity ve drawdown")
ax[1].fill_between(dd_pct.index, -100 * dd_pct, 0, color=ORANGE, alpha=0.85, lw=0)
ax[1].set_ylabel("Drawdown (%)")
figs["equity"] = save(fig, "01_equity")

fig, ax = plt.subplots(figsize=(9, 3.2))
tab = month_pct.to_frame("r")
tab["y"], tab["m"] = tab.index.year, tab.index.month
hm = tab.pivot(index="y", columns="m", values="r") * 100
v = max(abs(np.nanmin(hm.values)), abs(np.nanmax(hm.values)))
im = ax.imshow(hm.values, cmap=DIV, vmin=-v, vmax=v, aspect="auto")
ax.set_xticks(range(12))
ax.set_xticklabels(["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"])
ax.set_yticks(range(len(hm.index)))
ax.set_yticklabels(hm.index)
ax.grid(False)
for i in range(hm.shape[0]):
    for j in range(hm.shape[1]):
        x = hm.values[i, j]
        if not np.isnan(x):
            ax.text(j, i, f"{x:.1f}", ha="center", va="center", fontsize=7.5, color=INK if abs(x) < 0.6 * v else "white")
ax.set_title("Aylık getiri (% başlangıç ayı equity'si)")
ax.set_xlim(-0.5, 11.5)
figs["monthly"] = save(fig, "02_monthly")

fig, ax = plt.subplots(1, 2, figsize=(9, 3), gridspec_kw=dict(width_ratios=[2.2, 1]))
ax[0].bar(per_month.index.to_timestamp(), per_month.values, width=22, color=BLUE)
ax[0].axhline(per_month.mean(), color=ORANGE, lw=1.2)
ax[0].text(per_month.index.to_timestamp()[-1], per_month.mean() + 0.8, f"ortalama {per_month.mean():.1f}/ay", color=INK2, fontsize=8, ha="right")
ax[0].set_title("Ayda açılan pozisyon sayısı")
by_year = tr.groupby(tr.opened.dt.year).size()
ax[1].bar(by_year.index.astype(str), by_year.values, color=BLUE, width=0.6)
for i, x in enumerate(by_year.values):
    ax[1].text(i, x, str(x), ha="center", va="bottom", fontsize=8, color=INK2)
ax[1].set_title("Yıla göre")
figs["count"] = save(fig, "03_count")

fig, ax = plt.subplots(1, 2, figsize=(9, 3.1))
lim = np.nanpercentile(np.abs(tr.net), 99)
bins = np.linspace(-lim, lim, 41)
ax[0].hist(loss.net.clip(-lim, lim), bins=bins, color=RED, label=f"Kayıp ({len(loss)})")
ax[0].hist(win.net.clip(-lim, lim), bins=bins, color=BLUE, label=f"Kâr ({len(win)})")
ax[0].set_title("Trade net PnL dağılımı (USDT)")
ax[0].legend()
limb = np.nanpercentile(np.abs(tr.bps), 95)
bb = np.linspace(-limb, limb, 41)
ax[1].hist(tr.bps[tr.bps < 0].clip(-limb, limb), bins=bb, color=RED, label="Kayıp")
ax[1].hist(tr.bps[tr.bps >= 0].clip(-limb, limb), bins=bb, color=BLUE, label="Kâr")
ax[1].set_title("Net getiri (bps, notional'a göre; %95'e kırpıldı)")
ax[1].legend()
figs["hist"] = save(fig, "04_hist")

fig, ax = plt.subplots(2, 1, figsize=(9, 4.6), sharex=True, gridspec_kw=dict(height_ratios=[2, 1]))
ax[0].plot(lev.index, lev, color=BLUE, lw=0.9, label="Günlük ort. brüt kaldıraç")
ax[0].set_ylim(0, lev.max() * 1.35)
ax[0].plot(lev.rolling(60).mean().index, lev.rolling(60).mean(), color=ORANGE, lw=1.6, label="60 gün ortalaması")
ax[0].set_ylabel("Brüt notional / equity (x)")
ax[0].set_title("Kaldıraç ve açık sembol sayısı")
ax[0].legend(loc="upper left")
ax[1].plot(daily.index, daily.n_symbols_open, color=AQUA, lw=0.9)
ax[1].set_ylabel("Açık sembol")
figs["lev"] = save(fig, "05_leverage")

wf = [("Kazanan trade'lerin\nfiyat PnL", win.price_pnl.sum()), ("Kaybeden trade'lerin\nfiyat PnL", loss.price_pnl.sum()), ("Komisyon\n(fee+slip)", -tr.commission.sum()), ("Funding", tr.funding.sum()), ("Çıkış\nmaliyeti", -tr.exit_cost.sum())]
fig, ax = plt.subplots(figsize=(9, 3.4))
cum = 0.0
for i, (lab, x) in enumerate(wf):
    ax.bar(i, x, bottom=cum if x >= 0 else cum + x, color=BLUE if x >= 0 else RED, width=0.6, edgecolor=SURF, linewidth=2)
    ax.text(i, (cum + x if x >= 0 else cum) + (4 if x >= 0 else 4), f"{x:+.1f}", ha="center", va="bottom", fontsize=8, color=INK2)
    cum += x
ax.bar(len(wf), cum, color=INK2, width=0.6)
ax.text(len(wf), max(cum, 0) + 4, f"net {cum:+.1f}", ha="center", va="bottom", fontsize=8, color=INK)
ax.set_xticks(range(len(wf) + 1))
ax.set_xticklabels([w[0] for w in wf] + ["Net"], fontsize=7.5)
ax.set_title("Kâr/zarar şelalesi (USDT)")
figs["waterfall"] = save(fig, "06_waterfall")

fig, ax = plt.subplots(figsize=(9, 3.2))
ct = cause_tab.iloc[::-1]
ax.barh(range(len(ct)), ct.total, color=RED, height=0.62)
ax.set_yticks(range(len(ct)))
ax.set_yticklabels([c.replace(" (", "\n(") for c in ct.index], fontsize=7.2)
for i, (t, n) in enumerate(zip(ct.total, ct.n)):
    ax.text(t, i, f" {t:.1f} USDT · {n} trade", va="center", ha="right", fontsize=8, color=INK2)
ax.set_title("Kayıp nedenleri (toplam zarar, USDT)")
ax.grid(False)
ax.set_xlim(ct.total.min() * 1.9, 0)
figs["causes"] = save(fig, "07_causes")

fig, ax = plt.subplots(1, 4, figsize=(9.6, 3.0))
for a, (key, ttl) in zip(ax, (("side", "Yöne göre net PnL"), ("regime", "Giriş rejimine göre"), ("sym", "Sembole göre"), ("driver", "Sürücü uzmana göre"))):
    g = tr.groupby(key).net.sum().sort_values()
    a.barh([str(i).replace("USDT", "") for i in g.index], g.values, color=[BLUE if x >= 0 else RED for x in g.values], height=0.62)
    a.set_title(ttl, fontsize=8.5)
    a.axvline(0, color=AXIS, lw=0.8)
    a.grid(False)
fig.subplots_adjust(wspace=0.75)
figs["breakdown"] = save(fig, "08_breakdown")

fig, ax = plt.subplots(figsize=(9, 3.4))
ax.scatter(win.mfe_bps, win.gross_bps, s=9, color=BLUE, alpha=0.6, label="Net kârlı")
ax.scatter(loss.mfe_bps, loss.gross_bps, s=9, color=RED, alpha=0.6, label="Net zararlı")
mx = np.nanpercentile(tr.mfe_bps, 95)
ax.plot([0, mx], [0, mx], color=MUTED, lw=0.8, ls="--")
ax.text(mx * 0.62, mx * 0.7, "kâr tam realize\n(çıkış = zirve)", color=INK2, fontsize=7.5)
ax.set_xlim(0, mx)
ax.set_ylim(np.nanpercentile(tr.gross_bps, 1), mx)
ax.set_xlabel("En iyi lehe sapma (MFE, bps)")
ax.set_ylabel("Çıkıştaki brüt getiri (bps)")
ax.set_title("Kâr geri verme: MFE ve çıkış (eksenler MFE'nin %95'ine kırpıldı)")
ax.legend(loc="lower right")
figs["mfe"] = save(fig, "09_mfe")

cost_y = pd.DataFrame(dict(Komisyon=-tr.groupby(tr.closed.dt.year).commission.sum(), Funding=tr.groupby(tr.closed.dt.year).funding.sum()))
fig, ax = plt.subplots(figsize=(9, 2.9))
cost_y.plot.bar(ax=ax, stacked=True, color=[ORANGE, AQUA], width=0.6, edgecolor=SURF, linewidth=2)
ax.set_title("Yıllık maliyet kalemleri (USDT; negatif = maliyet)")
ax.grid(axis="x", visible=False)
ax.set_xlabel("")
ax.legend()
ax.axhline(0, color=AXIS, lw=0.8)
figs["costs"] = save(fig, "10_costs")

fig, ax = plt.subplots(figsize=(9, 2.8))
rs = ret.rolling(90).mean() / ret.rolling(90).std() * np.sqrt(365)
ax.plot(rs.index, rs, color=BLUE, lw=1.1)
ax.axhline(0, color=AXIS, lw=0.8)
ax.set_title("90 günlük kayan Sharpe")
figs["rollsharpe"] = save(fig, "11_rollsharpe")

worst = tr.nsmallest(4, "net")
if hourly is not None:
    fig, axs = plt.subplots(2, 2, figsize=(9, 5.2))
    for a, r in zip(axs.ravel(), worst.itertuples()):
        px = hourly[f"{r.sym}.close"][r.opened - pd.Timedelta("48h"): r.closed + pd.Timedelta("48h")]
        a.plot(px.index, px / px.iloc[0], color=INK2, lw=0.9)
        seg = hourly[f"{r.sym}.close"][r.opened: r.closed]
        a.plot(seg.index, seg / px.iloc[0], color=RED, lw=1.8)
        a.axvline(r.opened, color=BLUE, lw=0.9)
        a.axvline(r.closed, color=ORANGE, lw=0.9)
        a.set_title(f"{r.sym.replace('USDT', '')} {r.side} {r.opened:%Y-%m-%d} · net {r.net:.1f} USDT\nMFE {r.mfe_bps:.0f} / MAE {r.mae_bps:.0f} bps", fontsize=7.5)
        a.tick_params(labelsize=6.5)
    figs["worst"] = save(fig, "12_worst")

fig, ax = plt.subplots(1, 2, figsize=(9, 2.9))
ax[0].hist(tr.hours.clip(upper=tr.hours.quantile(0.98)) / 24, bins=40, color=BLUE)
ax[0].set_title("Tutma süresi (gün)")
ax[1].hist(tr.avg_notional.clip(upper=tr.avg_notional.quantile(0.98)), bins=40, color=BLUE)
ax[1].set_title("Ortalama trade büyüklüğü (USDT notional)")
figs["hold"] = save(fig, "13_hold")

# ---------------------------------------------------------------- ek analizler (drawdown, dağılım, sembol, maruziyet, kalibrasyon, karşı-olgusal)
SYMS = sorted({c.split(".")[0] for c in hourly.columns}) if hourly is not None else []
BTC_RET = daily.btc_close.pct_change()


def drawdown_table(e, top=10):
    pk, rows, start, trough, depth = e.iloc[0], [], e.index[0], e.index[0], 0.0
    for t, v in e.items():
        if v >= pk:  # yeni tepe: önceki drawdown (varsa) kapanır
            if depth > 0:
                rows.append(dict(peak=start, trough=trough, recovered=t, depth=depth, depth_usd=pk * depth))
            pk, start, trough, depth = v, t, t, 0.0
        else:
            d = (pk - v) / pk
            if d > depth:
                depth, trough = d, t
    if depth > 0:
        rows.append(dict(peak=start, trough=trough, recovered=pd.NaT, depth=depth, depth_usd=pk * depth))
    return pd.DataFrame(rows).sort_values("depth", ascending=False).head(top).reset_index(drop=True)


dd_tab = drawdown_table(eq)
r_ = ret.dropna()
ret_stats = dict(mean=r_.mean(), std=r_.std(ddof=1), skew=float(r_.skew()), kurt=float(r_.kurt()), var95=float(np.percentile(r_, 5)), var99=float(np.percentile(r_, 1)), cvar95=float(r_[r_ <= np.percentile(r_, 5)].mean()),
                 best=float(r_.max()), worst=float(r_.min()), pos=float((r_ > 0).mean()), ac1=float(r_.autocorr(1)), ac5=float(r_.autocorr(5)))
wd_mean = r_.groupby(r_.index.dayofweek).mean() * 1e4
beta_df = pd.concat([ret, BTC_RET], axis=1, keys=["r", "b"]).dropna()
beta = float(np.cov(beta_df.r, beta_df.b)[0, 1] / beta_df.b.var())
alpha_ann = float((beta_df.r.mean() - beta * beta_df.b.mean()) * 365)
r2 = float(np.corrcoef(beta_df.r, beta_df.b)[0, 1] ** 2)
roll_beta = beta_df.r.rolling(180).cov(beta_df.b) / beta_df.b.rolling(180).var()

fig, ax = plt.subplots(2, 1, figsize=(9, 4.4), sharex=True, gridspec_kw=dict(height_ratios=[1.4, 1]))
ax[0].fill_between(dd_pct.index, -100 * dd_pct, 0, color=ORANGE, alpha=0.9, lw=0)
for i, r in dd_tab.head(3).iterrows():
    ax[0].annotate(f"#{i + 1}  -{100 * r.depth:.1f}%", (r.trough, -100 * r.depth), xytext=(4, -10), textcoords="offset points", fontsize=7.5, color=INK2)
ax[0].set_ylabel("Drawdown (%)")
ax[0].set_title("Su altı grafiği ve en derin 3 drawdown")
ax[1].plot(roll_beta.index, roll_beta, color=BLUE, lw=1.2)
ax[1].axhline(0, color=AXIS, lw=0.8)
ax[1].set_ylabel("180 gün BTC beta")
figs["underwater"] = save(fig, "14_underwater")

fig, ax = plt.subplots(1, 3, figsize=(9.6, 3.0), gridspec_kw=dict(width_ratios=[1.6, 1, 1.3]))
bins_ = np.linspace(np.percentile(r_, 0.5) * 100, np.percentile(r_, 99.5) * 100, 40)
ax[0].hist(r_ * 100, bins=bins_, color=BLUE, density=True)
xs = np.linspace(bins_[0], bins_[-1], 200)
ax[0].plot(xs, np.exp(-0.5 * ((xs - r_.mean() * 100) / (r_.std() * 100)) ** 2) / (r_.std() * 100 * np.sqrt(2 * np.pi)), color=ORANGE, lw=1.4, label="normal")
ax[0].set_title("Günlük getiri (%)")
ax[0].legend()
ax[1].bar(["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"], wd_mean.values, color=[BLUE if x >= 0 else RED for x in wd_mean.values])
ax[1].set_title("Haftanın günü (ort. bps)")
ax[1].tick_params(axis="x", labelsize=6)
rolling_vol = ret.rolling(90).std() * np.sqrt(365)
ax[2].plot(rolling_vol.index, 100 * rolling_vol, color=BLUE, lw=1.1)
ax[2].set_title("90 gün oynaklık (% yıllık)")
figs["retdist"] = save(fig, "15_retdist")

if hourly is not None:
    H_ = {s: hourly[[f"{s}.{k}" for k in ("pos", "close", "high", "low", "net", "funding", "commission")]].set_axis(["pos", "close", "high", "low", "net", "funding", "commission"], axis=1) for s in SYMS}
    expo = {s: (H_[s].pos * H_[s].close) for s in SYMS}
    eq_h = (CAP + sum(H_[s].net for s in SYMS).cumsum())
    long_e = sum(e.clip(lower=0) for e in expo.values()) / eq_h
    short_e = sum(e.clip(upper=0) for e in expo.values()) / eq_h
    n_long = sum((H_[s].pos > 1e-12).astype(int) for s in SYMS)
    n_short = sum((H_[s].pos < -1e-12).astype(int) for s in SYMS)
    d_ = lambda x: x.resample("1D").mean()  # noqa: E731
    fig, ax = plt.subplots(2, 1, figsize=(9, 4.8), sharex=True)
    ax[0].plot(d_(long_e).index, d_(long_e), color=BLUE, lw=1.0, label="Long / equity")
    ax[0].plot(d_(short_e).index, -d_(short_e), color=ORANGE, lw=1.0, label="Short / equity (mutlak)")
    ax[0].plot(d_(long_e + short_e).index, d_(long_e + short_e), color=INK2, lw=1.0, ls="--", label="Net")
    ax[0].axhline(0, color=AXIS, lw=0.8)
    ax[0].set_title("Long, short ve net maruziyet (equity'ye oran)")
    ax[0].legend(ncol=3, loc="upper left")
    ax[0].set_ylim(top=max(d_(long_e).max(), d_(short_e).abs().max()) * 1.35)
    ax[1].fill_between(d_(n_long).index, d_(n_long), color=BLUE, alpha=0.9, lw=0, label="Long sembol sayısı")
    ax[1].fill_between(d_(n_short).index, -d_(n_short), color=ORANGE, alpha=0.9, lw=0, label="Short sembol sayısı")
    ax[1].legend(ncol=2, loc="lower left")
    ax[1].set_ylabel("Sembol")
    figs["longshort"] = save(fig, "16_longshort")

    fig, axs = plt.subplots(3, 3, figsize=(9, 6.2), sharex=True)
    for a, s in zip(axs.ravel(), SYMS):
        c = H_[s].net.resample("1D").sum().cumsum()
        a.plot(c.index, c, color=BLUE, lw=1.1)
        a.axhline(0, color=AXIS, lw=0.7)
        a.set_title(f"{s.replace('USDT', '')}  {c.iloc[-1]:+.1f} USDT", fontsize=8.5)
        a.tick_params(labelsize=6.5)
    fig.suptitle("Sembol bazında kümülatif net PnL (USDT)", x=0.07, ha="left", fontsize=10, fontweight="bold")
    figs["sym_cum"] = save(fig, "17_sym_cum")

    fig, axs = plt.subplots(3, 3, figsize=(9, 6.2), sharex=True)
    for a, s in zip(axs.ravel(), SYMS):
        e = d_(expo[s])
        a.fill_between(e.index, e.clip(lower=0), color=BLUE, lw=0)
        a.fill_between(e.index, e.clip(upper=0), color=ORANGE, lw=0)
        a.axhline(0, color=AXIS, lw=0.7)
        a.set_title(s.replace("USDT", ""), fontsize=8.5)
        a.tick_params(labelsize=6.5)
    fig.suptitle("Sembol bazında pozisyon (USDT notional; mavi long, turuncu short)", x=0.07, ha="left", fontsize=10, fontweight="bold")
    figs["sym_expo"] = save(fig, "18_sym_expo")

    sy = pd.DataFrame({s: H_[s].net.resample("YS").sum() for s in SYMS})
    sy.index = sy.index.year
    cm = pd.DataFrame({s: H_[s].net.resample("1D").sum() for s in SYMS}).corr()
    fig, ax = plt.subplots(1, 2, figsize=(9.4, 3.4), gridspec_kw=dict(width_ratios=[1.2, 1]))
    v1 = np.abs(sy.values).max()
    ax[0].imshow(sy.values, cmap=DIV, vmin=-v1, vmax=v1, aspect="auto")
    ax[0].set_xticks(range(len(SYMS)))
    ax[0].set_xticklabels([s.replace("USDT", "") for s in SYMS], fontsize=7)
    ax[0].set_yticks(range(len(sy)))
    ax[0].set_yticklabels(sy.index)
    for i in range(sy.shape[0]):
        for j in range(sy.shape[1]):
            ax[0].text(j, i, f"{sy.values[i, j]:.0f}", ha="center", va="center", fontsize=7, color=INK if abs(sy.values[i, j]) < 0.6 * v1 else "white")
    ax[0].grid(False)
    ax[0].set_title("Sembol × yıl net PnL (USDT)")
    ax[1].imshow(cm.values, cmap=DIV, vmin=-1, vmax=1, aspect="auto")
    ax[1].set_xticks(range(len(SYMS)))
    ax[1].set_xticklabels([s.replace("USDT", "") for s in SYMS], fontsize=6.5, rotation=90)
    ax[1].set_yticks(range(len(SYMS)))
    ax[1].set_yticklabels([s.replace("USDT", "") for s in SYMS], fontsize=6.5)
    ax[1].grid(False)
    ax[1].set_title("Günlük PnL korelasyonu")
    figs["sym_heat"] = save(fig, "19_sym_heat")

# sinyal kalibrasyonu: giriş anındaki koşullara göre trade sonucu
tr["absf"] = tr.f_total.abs()
cc = [f"c_{n}" for n in NAMES]
tr["n_aligned"] = (tr[cc] > 0).sum(axis=1)
tr["wd"] = (tr.opened - pd.Timedelta("1h")).dt.dayofweek
tr["size_pct"] = tr.avg_notional / tr.eq_at_open
cal_defs = [("absf", "|F| çeyreklik"), ("n_aligned", "Aynı yönde uzman"), ("sig_bps", "Oynaklık üçlüğü"), ("size_pct", "Büyüklük üçlüğü")]
fig, axs = plt.subplots(1, 4, figsize=(9.6, 3.0))
cal_tabs = {}
for a, (col, ttl) in zip(axs, cal_defs):
    x = tr.dropna(subset=[col, "bps"]).copy()
    if col == "n_aligned":
        x["g"] = x[col].astype(int).astype(str)
    else:
        q = 4 if col == "absf" else 3
        x["g"] = pd.qcut(x[col], q, labels=[f"{i + 1}" for i in range(q)], duplicates="drop").astype(str)
    g = x.groupby("g").agg(n=("net", "size"), med=("net", "median"), win=("net", lambda v: (v > 0).mean()), net=("net", "sum"), avg=("net", "mean"))
    cal_tabs[col] = g
    a.bar(g.index, g.avg, color=[BLUE if v >= 0 else RED for v in g.avg], width=0.6)
    for i, (n_, v) in enumerate(zip(g.n, g.avg)):
        a.text(i, v, f"n={n_}", ha="center", va="bottom" if v >= 0 else "top", fontsize=6.5, color=INK2)
    a.set_title(ttl, fontsize=7.5)
    a.axhline(0, color=AXIS, lw=0.8)
    a.tick_params(labelsize=7)
fig.suptitle("Trade başına ortalama net PnL (USDT) giriş koşuluna göre (kırpma yok)", x=0.05, ha="left", fontsize=9.5, fontweight="bold", y=1.04)
figs["calib"] = save(fig, "20_calib")

# MFE/MAE zamanlaması ve dağılımı (saatlik yoldan)
if hourly is not None:
    frac_peak, retained = [], []
    for r in tr.itertuples():
        ob, cb = r.opened.floor("1h"), r.closed.floor("1h")
        w = H_[r.sym].loc[ob:cb - pd.Timedelta("1h")]
        if len(w) < 2:
            frac_peak.append(np.nan)
            retained.append(np.nan)
            continue
        ext = w.high if r.side == "long" else -w.low
        frac_peak.append((ext.idxmax() - ob) / max(cb - ob, pd.Timedelta("1h")))
        retained.append(r.gross_bps / r.mfe_bps if r.mfe_bps > 0 else np.nan)
    tr["peak_frac"], tr["retained"] = frac_peak, retained
    win, loss = tr[tr.net > 0], tr[tr.net < 0]
    fig, ax = plt.subplots(1, 3, figsize=(9.6, 2.5))
    ax[0].hist(win.peak_frac.dropna(), bins=20, range=(0, 1), color=BLUE, alpha=0.9, label="Kâr", density=True)
    ax[0].hist(loss.peak_frac.dropna(), bins=20, range=(0, 1), color=RED, alpha=0.6, label="Zarar", density=True)
    ax[0].set_title("Zirve konumu (0 giriş, 1 çıkış)", fontsize=8)
    ax[0].legend()
    lo_, hi_ = -6, 12
    ax[1].hist(win.mfe_s.clip(0, hi_), bins=30, color=BLUE, alpha=0.9, label="Kâr")
    ax[1].hist(loss.mfe_s.clip(0, hi_), bins=30, color=RED, alpha=0.6, label="Zarar")
    ax[1].set_title("MFE (σ; 12σ'da kırpıldı)", fontsize=8)
    ax[1].legend()
    ax[2].hist(win.mae_s.clip(lo_, 0), bins=30, color=BLUE, alpha=0.9, label="Kâr")
    ax[2].hist(loss.mae_s.clip(lo_, 0), bins=30, color=RED, alpha=0.6, label="Zarar")
    ax[2].set_title("MAE (σ; -6σ'da kırpıldı)", fontsize=8)
    ax[2].legend()
    figs["timing"] = save(fig, "21_timing")

    # karşı-olgusal çıkış kuralları (ölçüm; strateji değil): saatlik GERÇEK pozisyon profiliyle. Trade'in saatlik fiyat PnL'i c_h = pos_{h-1} x (close_h - close_{h-1}) (ilk bar: pos x (close - giriş VWAP)).
    for i_, r_ in tr[tr.gross_bps.isna()].iterrows():  # veri sonunda açık kalan trade: son kapanıştan değerle
        tr.at[i_, "gross_bps"] = (1 if r_.side == "long" else -1) * (H_[r_.sym].close.iloc[-1] / r_.vwap_in - 1) * 1e4
    HF = {s_: H_[s_][["pos", "close", "high", "low"]].ffill() for s_ in SYMS}  # sembol verisinde boşluk (SOL/XRP'de saatlik eksik): son değerle doldur
    ARR = {s_: dict(idx=HF[s_].index, pos=HF[s_].pos.to_numpy(), close=HF[s_].close.to_numpy(), high=HF[s_].high.to_numpy(), low=HF[s_].low.to_numpy()) for s_ in SYMS}

    def path(r):
        a = ARR[r.sym]
        ob, cb = a["idx"].searchsorted(r.opened.floor("1h")), a["idx"].searchsorted(r.closed.floor("1h"))
        h = np.arange(ob, max(cb, ob + 1))  # pozisyonun tutulduğu barlar [ob, cb)
        pos_in = np.r_[a["pos"][ob], a["pos"][h[1:] - 1]] if len(h) else np.array([])  # bar boyunca tutulan pozisyon
        entry0 = a["close"][ob - 1] if ob > 0 else r.vwap_in  # ilk dolum fiyatı ~ önceki bar kapanışı (VWAP değil: kademeli eklemelerde VWAP ilk fiyattan çok uzak olabilir)
        prev = np.r_[entry0, a["close"][h[:-1]]] if len(h) else np.array([])
        return h, pos_in, prev, a, entry0

    def cf_exit(r, k, trailing, cache):
        h, pos_in, prev, a, entry0 = cache
        c_h = pos_in * (a["close"][h] - prev)  # saatlik fiyat PnL (gerçek profil)
        base = float(c_h.sum())
        d = k * r.sig_bps / 1e4
        if not np.isfinite(d) or len(h) == 0:
            return base, base, False
        sd = 1 if r.side == "long" else -1
        ref = entry0
        for n_, (hi, lo) in enumerate(zip(a["high"][h], a["low"][h])):
            stop = ref * (1 - d) if sd > 0 else ref * (1 + d)
            if (sd > 0 and lo <= stop) or (sd < 0 and hi >= stop):
                return base, float(c_h[:n_].sum() + pos_in[n_] * (stop - prev[n_])), True
            if trailing:
                ref = max(ref, hi) if sd > 0 else min(ref, lo)
        return base, base, False

    caches = [path(r) for r in tr.itertuples()]
    base_total = float(sum(float((pi * (a["close"][h] - pv)).sum()) for h, pi, pv, a, _ in caches))
    cf_rows = []
    for trailing in (True, False):
        for k in (1.0, 1.5, 2.0, 3.0, 4.0, 6.0):
            res_ = [cf_exit(r, k, trailing, c) for r, c in zip(tr.itertuples(), caches)]
            b_, c_, hit = (np.array([x[i] for x in res_]) for i in range(3))
            dl = c_ - b_
            cf_rows.append(dict(rule="İzleyen stop" if trailing else "Sabit stop (girişten)", k=k, delta=float(dl.sum()), hit=float(hit.mean()), helped=int(((dl > 1e-9) & hit).sum()), hurt=int(((dl < -1e-9) & hit).sum()),
                                helped_usd=float(dl[dl > 1e-9].sum()), hurt_usd=float(dl[dl < -1e-9].sum()), cf_total=float(c_.sum())))
    cf = pd.DataFrame(cf_rows)
    fig, ax = plt.subplots(figsize=(9, 2.4))
    for rule, col in (("İzleyen stop", BLUE), ("Sabit stop (girişten)", ORANGE)):
        z = cf[cf.rule == rule]
        ax.plot(z.k, z.delta, color=col, lw=1.8, marker="o", ms=4, label=rule)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_xlabel("Stop mesafesi (günlük σ cinsinden)")
    ax.set_ylabel("Brüt fiyat PnL değişimi (USDT)")
    ax.set_title("Karşı-olgusal: bu stop kuralı trade başına uygulansaydı (yeniden giriş yok)")
    ax.legend()
    figs["cf"] = save(fig, "22_cf")

# ---------------------------------------------------------------- PDF
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="DVB", fontSize=14, textColor=rc.HexColor(INK), spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="DVB", fontSize=10.5, textColor=rc.HexColor(INK), spaceBefore=8, spaceAfter=4)
B = ParagraphStyle("B", parent=ss["BodyText"], fontName="DV", fontSize=8.6, leading=12, textColor=rc.HexColor(INK))
SM = ParagraphStyle("SM", parent=B, fontSize=7.4, leading=10, textColor=rc.HexColor(INK2))
TT = ParagraphStyle("TT", parent=ss["Title"], fontName="DVB", fontSize=19, alignment=0, spaceAfter=4)
CELL = ParagraphStyle("CELL", parent=B, fontSize=7.6, leading=9.4)


def tbl(rows, widths=None, head=True, align_right_from=1):
    data = [[Paragraph(str(c), CELL) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.3, rc.HexColor(GRID)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if head:
        st += [("BACKGROUND", (0, 0), (-1, 0), rc.HexColor(MID))]
    t.setStyle(TableStyle(st))
    return t


def img(key, w=178 * mm):
    p = figs[key]
    from PIL import Image as PI

    iw, ih = PI.open(p).size
    return Image(str(p), width=w, height=w * ih / iw)


E_ = []
E_ += [Paragraph(f"Trade denetim raporu: Ensemble ({meta['preset']}), başlangıç bakiyesi {CAP:,.0f} USDT".replace(",", " "), TT),
       Paragraph(f"Dönem {daily.index[0]:%Y-%m-%d} → {daily.index[-1]:%Y-%m-%d} ({YEARS:.1f} yıl), 9 sembol (USDT-M perp), saatlik tarihsel tape, fee 10 + slip 2 bps gidiş-dönüş, kaldıraç limiti 10×. "
                 f"Bileşim: {', '.join(f'{n} {w:g}' for n, w in zip(meta['names'], meta['weights']))}. Bu rapor <b>script tabanlıdır</b> (scripts/trade_audit.py + trade_audit_report.py); LLM rakam üretmez. "
                 "Sonuçlar görülmüş veride; geleceği kanıtlamaz.", B), Spacer(1, 4)]
E_ += [Paragraph("Özet", H1)]
sm = [["Ölçü", "Değer", "Ölçü", "Değer"],
      ["Net PnL", f"{usd(net_total)} USDT ({pct(net_total / CAP)})", "Yıllık getiri (CAGR)", pct(cagr)],
      ["Yıllık oynaklık", pct(vol), "Sharpe / Sortino / Calmar", f"{sharpe:.2f} / {sortino:.2f} / {calmar:.2f}"],
      ["Maks drawdown", f"{usd(dd_usd.max())} USDT (tepe equity'nin {pct(dd_pct.max())}, başlangıç sermayesinin {pct(dd_usd.max() / CAP)})", "Suda geçen en uzun süre", f"{uw_days} gün"],
      ["Trade (pozisyon dönemi)", f"{len(tr)}  ({len(win)} kâr / {len(loss)} zarar)", "Dolum (emir yürütme)", f"{int(S['n_fills'])}"],
      ["Ayda trade (ort. / medyan / maks)", f"{per_month.mean():.1f} / {per_month.median():.0f} / {per_month.max()}", "Haftalık / aylık pozitif oran", f"{pct((week > 0).mean())} / {pct((month > 0).mean())}"],
      ["Likidasyon / reddedilen emir", f"{int(S['n_liq'])} / {meta['rejected']}", "Mutabakat farkı (saatlik − hakem)", f"{meta['recon_hourly_vs_referee']:.2e} USDT"]]
long_, short_ = tr[tr.side == "long"], tr[tr.side == "short"]
bull_short = tr[(tr.regime == "bull") & (tr.side == "short")]
big_gb = tr[(tr.net < 0) & (tr.mfe_s >= 2)]
finds = [f"<b>Profil.</b> Kazanma oranı {pct((tr.net > 0).mean())}, payoff {win.net.mean() / abs(loss.net.mean()):.1f}× (ort. kazanç {win.net.mean():.2f}, ort. kayıp {loss.net.mean():.2f} USDT); medyan trade {tr.net.median():.2f} USDT, beklenti {tr.net.mean():.2f} USDT/trade. En kötü ardışık kayıp serisi {mx_streak0} trade.",
         f"<b>Yön asimetrisi.</b> Long {len(long_)} trade net {long_.net.sum():+.1f} USDT; short {len(short_)} trade net {short_.net.sum():+.1f} USDT. Bull rejiminde short'lar {len(bull_short)} trade ile {bull_short.net.sum():+.1f} USDT.",
         f"<b>Paranın kazanıldığı yer uzun trade'ler.</b> 30 günden uzun {int((tr.hours > 720).sum())} trade net {tr[tr.hours > 720].net.sum():+.1f} USDT; 7 günden kısa {int((tr.hours <= 168).sum())} trade net {tr[tr.hours <= 168].net.sum():+.1f} USDT.",
         f"<b>Kâr geri verme ve sürekli pozisyon.</b> Kaybeden {len(loss)} trade'in {len(big_gb)}'i çıkmadan önce 2 günlük σ'dan fazla lehe gitmişti (toplam zararları {big_gb.net.sum():.1f} USDT). Trade'lerin %{100 * tr.flip_close.mean():.0f}'i doğrudan long↔short çevirme: sistem sürekli pozisyonda (aynı anda ort. {daily.n_symbols_open.mean():.1f}/9 sembol), stop ve izleyen çıkış yok.",
         f"<b>Maliyetler küçük.</b> Fee+slip brüt PnL'in {pct((S['fee'] + S['slippage']) / S['gross_pnl'])}'i, funding (net) {pct(-S['funding'] / S['gross_pnl'])}'i; ikisi birlikte {pct((S['fee'] + S['slippage'] - S['funding']) / S['gross_pnl'])}.",
         f"<b>Piyasa-nötre yakın, ama son dönem zayıf.</b> BTC beta'sı {beta:.2f} (R² {r2:.2f}). 2025-2026 net {daily.net[daily.index >= '2025-01-01'].sum():+.1f} USDT; en derin drawdown ({pct(dd_tab.depth.iloc[0])}) {dd_tab.peak.iloc[0]:%Y-%m-%d}'den beri {'sürüyor' if pd.isna(dd_tab.recovered.iloc[0]) else 'toparlandı'}.",
         f"<b>Fiyat stopu kârı götürüyor.</b> Trade bazında saatlik yola uygulanan {len(cf)} stop kuralının {int((cf.delta > 0).sum())}'i brüt fiyat PnL'i artırdı (en iyisi {cf.delta.max():+.0f} USDT, en kötüsü {cf.delta.min():+.0f} USDT; yeniden giriş ve maliyet etkisi yok). Kazanç, derin geri çekilmelere rağmen süren az sayıdaki trend trade'inden geliyor.",
         f"<b>Kaldıraç düşük.</b> Ortalama brüt kaldıraç {lev.mean():.2f}× (maks günlük ortalama {lev.max():.2f}×), limit 10×; ort. trade {tr.avg_notional.mean():.0f} USDT ({pct((tr.avg_notional / tr.eq_at_open).mean())} equity)."]
E_ += [tbl(sm, [48 * mm, 44 * mm, 46 * mm, 40 * mm]), Paragraph("Öne çıkan bulgular (otomatik üretildi)", H2)] + [Paragraph("• " + f, B) for f in finds] + [Spacer(1, 6), img("equity")]
E_ += [KeepTogether([Paragraph("Tanımlar ve sınırlar", H2),
       Paragraph("<b>Trade</b> = bir sembolde pozisyonun sıfırdan sıfıra (ya da yön değişimine) kadar süren dönemi; Nautilus pozisyon sayımıyla aynı (bkz. Bölüm 8). EV1 sürekli yeniden dengelendiği için bir trade içinde birden çok "
                 "kısmi dolum olabilir; <b>dolum</b> ayrı sayılır. <b>Net</b> = fiyat PnL − komisyon (fee+slip) + funding − çıkış maliyeti. <b>Kaldıraç</b> = brüt notional / equity. <b>Planlanan risk</b> = notional × 1 günlük 1σ / equity "
                 "(EV1'de stop yok). <b>Sharpe/Sortino</b> = günlük getirinin (PnL / önceki gün equity) ortalaması ÷ standart sapması, √365 ile yıllıklaştırılmış; getiri equity'ye normalleştirildiği için sabit sermayeli hesaptan biraz farklıdır. <b>MAE/MFE</b> = trade süresince saatlik en kötü/en iyi fiyat sapması (giriş VWAP'ına göre). <b>Kayıp nedeni</b> kural tabanlı etikettir (Ek A), kanıt değildir. "
                 "Veri saatlik bar: bar içi sıralama bilinmez; slippage varsayımdır; gerçek borsa lot/min-notional kuralları doğrulanmadı. "
                 "Mutabakat: trade tablosu saatlik PnL toplamına eşit; hakem net'inden 0,034 USDT (%0,004) farklı, bilinen küçük `report.hourly_pnl` muhasebe farkı, kaynağı tam çözülmedi.", SM)])]

E_ += [PageBreak(), Paragraph("1. Zaman içinde PnL", H1), img("monthly"), Spacer(1, 4)]
yr = daily.net.groupby(daily.index.year).sum()
yrp = yr / eq.groupby(eq.index.year).first().shift(0).clip(lower=1)
rows = [["Yıl", "Net PnL (USDT)", "Getiri (% yıl başı equity)", "En iyi ay (%)", "En kötü ay (%)", "Pozitif ay"]]
for y in yr.index:
    mm_ = month_pct[month_pct.index.year == y]
    e0 = eq[eq.index.year == y].iloc[0] - daily.net[daily.index.year == y].iloc[0]
    rows.append([y, usd(yr[y]), pct(yr[y] / e0), f"{100 * mm_.max():.1f}", f"{100 * mm_.min():.1f}", f"{int((mm_ > 0).sum())}/{len(mm_)}"])
E_ += [tbl(rows, [18 * mm, 32 * mm, 40 * mm, 28 * mm, 28 * mm, 28 * mm]), Spacer(1, 4)]
wk = [["Haftalık", "Değer", "Aylık", "Değer"],
      ["Ortalama (USDT / % equity)", f"{week.mean():.2f} / {pct(week_pct.mean())}", "Ortalama (USDT / % equity)", f"{month.mean():.2f} / {pct(month_pct.mean())}"],
      ["En iyi / en kötü hafta (USDT)", f"{week.max():.2f} / {week.min():.2f}", "En iyi / en kötü ay (USDT)", f"{month.max():.2f} / {month.min():.2f}"],
      ["En iyi / en kötü hafta (%)", f"{pct(week_pct.max())} / {pct(week_pct.min())}", "En iyi / en kötü ay (%)", f"{pct(month_pct.max())} / {pct(month_pct.min())}"],
      ["Pozitif hafta oranı", pct((week > 0).mean()), "Pozitif ay oranı", pct((month > 0).mean())]]
E_ += [tbl(wk, [48 * mm, 42 * mm, 48 * mm, 40 * mm]), Spacer(1, 4), img("rollsharpe", 170 * mm)]

E_ += [PageBreak(), Paragraph("1b. Drawdown, getiri dağılımı ve piyasa duyarlılığı", H1), img("underwater")]
rows = [["#", "Tepe", "Dip", "Toparlanma", "Derinlik", "USDT", "Dibe (gün)", "Toplam (gün)"]]
for i, r in dd_tab.iterrows():
    end = r.recovered if pd.notna(r.recovered) else daily.index[-1]
    rows.append([i + 1, f"{r.peak:%Y-%m-%d}", f"{r.trough:%Y-%m-%d}", f"{r.recovered:%Y-%m-%d}" if pd.notna(r.recovered) else "devam", pct(r.depth), f"{r.depth_usd:.1f}", (r.trough - r.peak).days, f"{(end - r.peak).days}{'+' if pd.isna(r.recovered) else ''}"])
E_ += [tbl(rows, [8 * mm, 24 * mm, 24 * mm, 26 * mm, 22 * mm, 20 * mm, 24 * mm, 26 * mm]), Spacer(1, 6), img("retdist")]
rs_ = [["Getiri dağılımı (günlük)", "Değer", "Piyasa duyarlılığı", "Değer"],
       ["Ortalama / oynaklık (bps)", f"{1e4 * ret_stats['mean']:.1f} / {1e4 * ret_stats['std']:.1f}", "BTC beta (günlük getiri)", f"{beta:.3f}"],
       ["Çarpıklık / fazla basıklık", f"{ret_stats['skew']:.2f} / {ret_stats['kurt']:.1f}", "Alfa (yıllık, beta'dan arınmış)", pct(alpha_ann)],
       ["VaR %95 / %99 (günlük, equity)", f"{pct(ret_stats['var95'])} / {pct(ret_stats['var99'])}", "BTC ile R²", f"{r2:.3f}"],
       ["CVaR %95 (en kötü %5 günün ort.)", pct(ret_stats["cvar95"]), "Net maruziyet ort. mutlak / equity", f"{(daily.net_exposure.abs() / eq).mean():.3f}×"],
       ["En iyi / en kötü gün", f"{pct(ret_stats['best'])} / {pct(ret_stats['worst'])}", "Pozitif gün oranı", pct(ret_stats["pos"])],
       ["Otokorelasyon lag-1 / lag-5", f"{ret_stats['ac1']:.3f} / {ret_stats['ac5']:.3f}", "Haftalık / aylık pozitif", f"{pct((week > 0).mean())} / {pct((month > 0).mean())}"]]
E_ += [Spacer(1, 4), tbl(rs_, [52 * mm, 36 * mm, 52 * mm, 34 * mm]), Spacer(1, 3),
       Paragraph(f"Çarpıklık {ret_stats['skew']:.2f} ve fazla basıklık {ret_stats['kurt']:.1f}: kuyruklar normalden belirgin ağır (trend takibinin tipik pozitif çarpıklık/büyük kâr günleri profili). BTC beta'sı {beta:.2f}, R² {r2:.2f}: getiri BTC yönünden büyük ölçüde bağımsız, alfa tahmini yıllık {pct(alpha_ann)} (örneklem içi).", SM)]
yrs = []
for y in sorted(set(daily.index.year)):
    dy, ey, ty = daily[daily.index.year == y], eq[eq.index.year == y], tr[tr.opened.dt.year == y]
    ry = ret[ret.index.year == y]
    e0 = ey.iloc[0] - dy.net.iloc[0]
    pk = pd.concat([pd.Series([e0]), ey]).cummax()
    ddy = ((pk.iloc[1:].to_numpy() - ey.to_numpy()) / pk.iloc[1:].to_numpy()).max()
    yrs.append([y, f"{dy.net.sum():.1f}", pct(dy.net.sum() / e0), f"{ry.mean() / ry.std(ddof=1) * np.sqrt(365):.2f}" if ry.std() > 0 else "-", pct(ddy), len(ty), pct((ty.net > 0).mean()), f"{ty[ty.side == 'long'].net.sum():.1f}", f"{ty[ty.side == 'short'].net.sum():.1f}", f"{dy.gross_lev_mean.mean():.2f}×"])
E_ += [Paragraph("Yıl yıl özet", H2), tbl([["Yıl", "Net", "Getiri", "Sharpe", "Maks DD", "Trade", "Kazanma", "Long net", "Short net", "Ort. kaldıraç"]] + yrs, [14 * mm, 18 * mm, 18 * mm, 16 * mm, 18 * mm, 15 * mm, 18 * mm, 20 * mm, 20 * mm, 22 * mm])]

E_ += [PageBreak(), Paragraph("2. Trade istatistikleri", H1), img("count")]
pf = win.net.sum() / abs(loss.net.sum())
mx_streak = mx_streak0
ts_ = [["Ölçü", "Değer", "Ölçü", "Değer"],
       ["Toplam trade / ayda ortalama", f"{len(tr)} / {per_month.mean():.1f}", "Kazanma oranı", pct((tr.net > 0).mean())],
       ["Ort. PnL / trade (USDT)", f"{tr.net.mean():.3f}", "Ort. PnL / trade (% equity)", f"{pct(tr.net_pct_eq.mean())}"],
       ["Medyan PnL / trade (USDT)", f"{tr.net.median():.3f}", "Ort. net getiri (bps notional)", f"{tr.bps.mean():.1f}"],
       ["Ort. kazanç / ort. kayıp (USDT)", f"{win.net.mean():.2f} / {loss.net.mean():.2f}", "Payoff (kazanç/kayıp)", f"{win.net.mean() / abs(loss.net.mean()):.2f}"],
       ["Profit factor", f"{pf:.2f}", "Beklenti (USDT/trade)", f"{tr.net.mean():.3f}"],
       ["En iyi / en kötü trade (USDT)", f"{tr.net.max():.2f} / {tr.net.min():.2f}", "En uzun ardışık kayıp serisi", f"{mx_streak} trade"],
       ["Long / short trade", f"{(tr.side == 'long').sum()} / {(tr.side == 'short').sum()}", "Long / short net PnL (USDT)", f"{tr[tr.side == 'long'].net.sum():.1f} / {tr[tr.side == 'short'].net.sum():.1f}"],
       ["Tutma süresi medyan / p90 (gün)", f"{tr.hours.median() / 24:.1f} / {tr.hours.quantile(0.9) / 24:.1f}", "Trade başına dolum (ort.)", f"{tr.n_fills.mean():.1f}"]]
E_ += [tbl(ts_, [52 * mm, 36 * mm, 50 * mm, 36 * mm]), Spacer(1, 4), img("hist"), img("hold")]
bs = tr.groupby("sym").agg(n=("net", "size"), net=("net", "sum"), win=("net", lambda x: (x > 0).mean()), avg=("net", "mean"), notional=("avg_notional", "mean"), hours=("hours", "median")).sort_values("net")
rows = [["Sembol", "Trade", "Net PnL", "Kazanma", "Ort. PnL", "Ort. notional", "Medyan süre (gün)"]] + [[i.replace("USDT", ""), r.n, f"{r.net:.2f}", pct(r.win), f"{r.avg:.3f}", f"{r.notional:.1f}", f"{r.hours / 24:.1f}"] for i, r in bs.iterrows()]
E_ += [Paragraph("Sembole göre", H2), tbl(rows, [20 * mm, 18 * mm, 26 * mm, 24 * mm, 26 * mm, 28 * mm, 32 * mm])]
top = pd.concat([tr.nlargest(10, "net").assign(k="En iyi"), tr.nsmallest(10, "net").assign(k="En kötü")])
rows = [["", "Sem.", "Açılış", "Yön", "Gün", "Notional", "Fiyat PnL", "Kom.", "Fund.", "Net", "MFE / MAE bps"]] + [[r.k, r.sym.replace("USDT", ""), f"{r.opened:%Y-%m-%d}", r.side, f"{r.hours / 24:.1f}", f"{r.avg_notional:.0f}", f"{r.price_pnl:.2f}",
                                                                                                                      f"{r.commission:.2f}", f"{r.funding:.2f}", f"{r.net:.2f}", f"{r.mfe_bps:.0f}/{r.mae_bps:.0f}"] for r in top.itertuples()]
E_ += [Paragraph("En iyi ve en kötü 10 trade", H2), tbl(rows, [15 * mm, 12 * mm, 20 * mm, 12 * mm, 11 * mm, 16 * mm, 17 * mm, 13 * mm, 13 * mm, 14 * mm, 31 * mm])]

E_ += [PageBreak(), Paragraph("3. Büyüklük ve kaldıraç", H1), img("lev")]
sz = [["Ölçü", "Değer", "Ölçü", "Değer"],
      ["Ort. trade büyüklüğü (USDT notional)", f"{tr.avg_notional.mean():.1f}", "Ort. trade büyüklüğü (% equity)", pct((tr.avg_notional / tr.eq_at_open).mean())],
      ["Medyan / maks trade (USDT)", f"{tr.avg_notional.median():.1f} / {tr.max_notional.max():.1f}", "Maks tek pozisyon (% equity)", pct((tr.max_notional / tr.eq_at_open).max())],
      ["Brüt kaldıraç ort. / medyan", f"{lev.mean():.3f}× / {lev.median():.3f}×", "Brüt kaldıraç p95 / maks (günlük ort.)", f"{lev.quantile(0.95):.3f}× / {lev.max():.3f}×"],
      ["Gün içi maks brüt kaldıraç", f"{daily.gross_lev_max.max():.3f}×", "Kullanılan marj (brüt/10, ort.)", pct(lev.mean() / 10)],
      ["Net maruziyet / equity (ort. mutlak)", f"{(daily.net_exposure.abs() / eq).mean():.3f}×", "Aynı anda açık sembol (ort.)", f"{daily.n_symbols_open.mean():.1f} / 9"],
      ["Yıllık devir (toplam işlem hacmi / ort. equity / yıl)", f"{traded / eq.mean() / YEARS:.1f}×", "Hakem kaldıraç limiti", "10×"]]
E_ += [tbl(sz, [60 * mm, 32 * mm, 50 * mm, 32 * mm]), Spacer(1, 4),
       Paragraph(f"Sistem sermayeyi ağırlıkla kullanmıyor: ortalama brüt kaldıraç {lev.mean():.2f}×, hakem limiti 10×. Likidasyona uzaklık çok geniş (brüt kaldıraç ≈ {lev.max():.2f}×); asıl kısıt drawdown bütçesidir. "
                 "Not: hedef notional'lar küçük (medyan trade ≈ " + f"{tr.avg_notional.median():.0f} USDT); gerçek borsa minimum notional/lot kuralları bu bakiyede BTC/ETH için engel olabilir (doğrulanmadı).", SM)]
if "longshort" in figs:
    gross_hr = sum(expo[s].abs() for s in SYMS) / eq_h
    hr_net = sum(H_[s].net for s in SYMS)
    lv = [["Saatlik kaldıraç ve ani kayıp", "Değer", "Ölçü", "Değer"],
          ["Brüt kaldıraç ort. / p95 / p99 / maks (saatlik)", f"{gross_hr.mean():.3f} / {gross_hr.quantile(0.95):.3f} / {gross_hr.quantile(0.99):.3f} / {gross_hr.max():.3f}×", "En kötü saat / gün / hafta (% equity)", f"{pct((hr_net / eq_h.shift(1)).min())} / {pct(ret.min())} / {pct(week_pct.min())}"],
          ["Tüm pozisyonlar aynı yönde olsaydı sermayeyi silecek fiyat hareketi (1 / maks brüt)", pct(1 / gross_hr.max()), "Long / short ort. maruziyet (equity)", f"{long_e.mean():.3f}× / {abs(short_e.mean()):.3f}×"],
          ["Aynı anda long / short sembol (ort.)", f"{n_long.mean():.1f} / {n_short.mean():.1f}", "Net long sembol sayısı > 0 olan gün oranı", pct(((n_long - n_short) > 0).resample("1D").mean().gt(0.5).mean())]]
    E_ += [Spacer(1, 6), img("longshort"), tbl(lv, [66 * mm, 40 * mm, 40 * mm, 34 * mm])]
E_ += [Paragraph("4. Trade başına risk", H1)]
rk = [["Ölçü", "Ortalama", "Medyan", "p95", "Maks"],
      ["Planlanan risk (notional × 1g σ / equity)", pct3(tr.plan_risk_pct.mean()), pct3(tr.plan_risk_pct.median()), pct3(tr.plan_risk_pct.quantile(0.95)), pct3(tr.plan_risk_pct.max())],
      ["Gerçekleşen en kötü sapma, MAE (% equity)", pct3(tr.mae_pct_eq.mean()), pct3(tr.mae_pct_eq.median()), pct3(tr.mae_pct_eq.quantile(0.05)), pct3(tr.mae_pct_eq.min())],
      ["Gerçekleşen net PnL (% equity)", pct3(tr.net_pct_eq.mean()), pct3(tr.net_pct_eq.median()), pct3(tr.net_pct_eq.quantile(0.05)), pct3(tr.net_pct_eq.min())],
      ["MAE (bps, giriş VWAP'ına göre)", f"{tr.mae_bps.mean():.0f}", f"{tr.mae_bps.median():.0f}", f"{tr.mae_bps.quantile(0.05):.0f}", f"{tr.mae_bps.min():.0f}"]]
E_ += [tbl(rk, [70 * mm, 26 * mm, 26 * mm, 26 * mm, 26 * mm]), Spacer(1, 3),
       Paragraph(f"Gerçekleşen portföy oynaklığı yıllık {pct(vol)}; hedef τ = %20 tam tahminde, tampon ve tahmin ölçeği (ortalama |F| = 0,5) yüzünden gerçekleşen bunun yaklaşık yarısı. "
                 "MAE, trade ortalama notional'ı ile % equity'ye çevrilmiştir (yaklaşık). Stop olmadığından 'trade başına risk' bir üst sınır değil, gözlenen/planlanan dağılımdır; sapmanın kuyruğu örneklemde gözlenenin ötesinde olabilir.", SM)]

E_ += [Paragraph("5. Maliyet", H1), img("costs", 160 * mm)]
cs = [["Kalem", "Toplam (USDT)", "Trade başına", "Brüt PnL'in %'si"],
      ["Fee", usd(S["fee"]), f"{S['fee'] / len(tr):.3f}", pct(S["fee"] / max(S["gross_pnl"], 1e-9))], ["Slippage (varsayım)", usd(S["slippage"]), f"{S['slippage'] / len(tr):.3f}", pct(S["slippage"] / max(S["gross_pnl"], 1e-9))],
      ["Funding (net)", usd(S["funding"]), f"{S['funding'] / len(tr):.3f}", pct(S["funding"] / max(S["gross_pnl"], 1e-9))], ["Çıkış maliyeti", usd(S["exit_cost"]), "-", "-"],
      ["Brüt PnL → Net PnL", f"{usd(S['gross_pnl'])} → {usd(S['net_pnl'])}", "", ""]]
E_ += [tbl(cs, [50 * mm, 48 * mm, 40 * mm, 40 * mm])]
fl_day = pd.to_datetime(fills.ts, unit="ns", utc=True).dt.floor("1D")
traded_d = (fills.qty * fills.px).groupby(fl_day).sum().reindex(daily.index, fill_value=0.0)
base_rt = 12.0  # hakem koşusu: fee 10 + slip 2 (gidiş-dönüş bps)
sens = [("Maker 4 + slip 0", 4, 0), ("Maker 4 + slip 2", 4, 2), ("BNB indirimli taker 9 + slip 2", 9, 2), ("Taker 10 + slip 0", 10, 0), ("Taker 10 + slip 2 (hakem koşusu)", 10, 2), ("Taker 10 + slip 6", 10, 6), ("Taker 16 + slip 2 (MEXC taker)", 16, 2), ("Taker 16 + slip 6", 16, 6)]
rows = [["Senaryo (gidiş-dönüş bps)", "Net (USDT)", "Getiri", "Sharpe", "Maks DD", "Brüt PnL'in %'si maliyet"]]
for lab, f_, sl_ in sens:
    alt = daily.net + traded_d * (base_rt - (f_ + sl_)) / 2e4  # komisyon notional ile doğrusal
    sh_, dd_ = sharpe_of(alt)
    rows.append([lab, f"{alt.sum():.1f}", pct(alt.sum() / CAP), f"{sh_:.2f}", pct(dd_), pct(((f_ + sl_) / 2e4 * traded_d.sum()) / S["gross_pnl"])])
be = 2e4 * (S["gross_pnl"] + S["funding"] - S["exit_cost"]) / traded_d.sum()
E_ += [Spacer(1, 4), Paragraph("Maliyet duyarlılığı (aynı dolumlar, komisyon notional ile doğrusal yeniden hesaplandı)", H2), tbl(rows, [62 * mm, 24 * mm, 20 * mm, 20 * mm, 22 * mm, 34 * mm]),
       Paragraph(f"Toplam işlem hacmi {traded_d.sum():,.0f} USDT ({traded_d.sum() / eq.mean() / YEARS:.1f}× ort. equity / yıl). Funding ve dolum kararları sabit tutuldu; fee/slip değişince karar değişmediği varsayılır (kuralda maliyete duyarlı bir adım yok). "
                 f"Net'i sıfırlayan toplam maliyet ≈ {be:.0f} bps gidiş-dönüş (funding dahil, çıkış maliyeti düşülmüş).".replace(",", " "), SM)]

bysym = tr.groupby("sym").agg(price=("price_pnl", "sum"), comm=("commission", "sum"), fund=("funding", "sum"), net=("net", "sum"))
byside = tr.groupby("side").agg(price=("price_pnl", "sum"), comm=("commission", "sum"), fund=("funding", "sum"), net=("net", "sum"))
rows = [["Grup", "Fiyat PnL", "Komisyon (fee+slip)", "Funding", "Net"]] + [[i.replace("USDT", ""), f"{r.price:.1f}", f"{-r.comm:.1f}", f"{r.fund:.1f}", f"{r.net:.1f}"] for i, r in pd.concat([bysym, byside]).iterrows()]
E_ += [Spacer(1, 4), Paragraph("Sembol ve yöne göre maliyet kalemleri (USDT)", H2), tbl(rows, [36 * mm, 34 * mm, 42 * mm, 34 * mm, 30 * mm])]
E_ += [Spacer(1, 8), Paragraph("6. Kayıp denetimi: paranın nerede kaybedildiği", H1), img("waterfall"),
       Paragraph(f"Kaybeden {len(loss)} trade'in toplamı {loss.net.sum():.1f} USDT; kazanan {len(win)} trade {win.net.sum():.1f} USDT. En kötü %5 trade ({max(1, int(len(tr) * 0.05))} adet) toplam zararın "
                 f"%{100 * tr.nsmallest(max(1, int(len(tr) * 0.05)), 'net').net.sum() / loss.net.sum():.0f}'ini oluşturuyor (kuyruk yoğunluğu).", B), img("causes")]
rows = [["Kayıp nedeni (etiket)", "Trade", "Toplam zarar (USDT)", "Zararın %'si", "Ort. zarar", "Medyan süre (gün)"]] + [[c, int(r.n), f"{r.total:.1f}", pct(r.total / loss.net.sum()), f"{r.avg:.3f}", f"{r.hours / 24:.1f}"] for c, r in cause_tab.iterrows()]
E_ += [tbl(rows, [64 * mm, 14 * mm, 28 * mm, 26 * mm, 20 * mm, 24 * mm]), Spacer(1, 4)]
E_ += [KeepTogether([Paragraph("Kırılımlar", H2), img("breakdown")])]
sr = tr.groupby(["regime", "side"]).agg(n=("net", "size"), net=("net", "sum"), win=("net", lambda x: (x > 0).mean()), avgw=("net", lambda x: x[x > 0].mean()), avgl=("net", lambda x: x[x < 0].mean()))
rows = [["Giriş rejimi", "Yön", "Trade", "Net PnL", "Kazanma", "Ort. kazanç", "Ort. kayıp"]] + [[i[0], i[1], int(r.n), f"{r.net:.1f}", pct(r.win), f"{r.avgw:.2f}", f"{r.avgl:.2f}"] for i, r in sr.iterrows()]
E_ += [Spacer(1, 4), tbl(rows, [32 * mm, 20 * mm, 20 * mm, 26 * mm, 24 * mm, 26 * mm, 26 * mm])]
E_ += [Spacer(1, 4)]
dr = tr.groupby("driver").agg(n=("net", "size"), net=("net", "sum"), win=("net", lambda x: (x > 0).mean()), loss=("net", lambda x: x[x < 0].sum()))
rows = [["Sürücü uzman (giriş günü en büyük yön-hizalı katkı)", "Trade", "Net PnL", "Kazanma", "Toplam zarar"]] + [[i, int(r.n), f"{r.net:.1f}", pct(r.win), f"{r.loss:.1f}"] for i, r in dr.iterrows()]
E_ += [tbl(rows, [80 * mm, 18 * mm, 24 * mm, 26 * mm, 26 * mm]), Spacer(1, 3),
       Paragraph("Uzman atfı yaklaşıktır: pozisyonu en çok destekleyen uzman 'sürücü' sayılır; etkileşim artığı (üç uzmanın birleşimi) ayrıca ölçülmedi.", SM)]
hb = [(">0 gün", tr.hours <= 24 * 7, "≤ 7 gün"), ("", (tr.hours > 24 * 7) & (tr.hours <= 24 * 30), "7-30 gün"), ("", tr.hours > 24 * 30, "> 30 gün")]
rows = [["Tutma süresi", "Trade", "Net PnL", "Kazanma", "Ort. net (USDT)"]] + [[lab, int(m.sum()), f"{tr[m].net.sum():.1f}", pct((tr[m].net > 0).mean()), f"{tr[m].net.mean():.3f}"] for _, m, lab in hb]
E_ += [Spacer(1, 4), tbl(rows, [50 * mm, 22 * mm, 30 * mm, 28 * mm, 34 * mm])]
dn = daily.net
stress_rows = [["Şok penceresi", "Net PnL (USDT)", "En kötü gün (USDT)"]] + [[k, f"{dn[a:b].sum():.2f}", f"{dn[a:b].min():.2f}"] for k, (a, b) in STRESS.items()]
wd = dn.nsmallest(5)
E_ += [Paragraph("En kötü 5 gün ve şok pencereleri", H2), tbl([["Tarih", "Net PnL (USDT)", "% equity"]] + [[f"{d:%Y-%m-%d}", f"{v:.2f}", pct(v / eq.shift(1).fillna(CAP)[d])] for d, v in wd.items()], [40 * mm, 40 * mm, 30 * mm]), Spacer(1, 4), tbl(stress_rows, [60 * mm, 40 * mm, 40 * mm])]
E_ += [Spacer(1, 8), Paragraph("7. Kâr geri verme ve en kötü trade'ler", H1), img("mfe")]
gv2, gv05 = loss[loss.mfe_s >= 2], loss[loss.mfe_s >= 0.5]
fl = loss[loss.flip_close]
E_ += [Paragraph(f"Kaybeden {len(loss)} trade'in {len(gv05)}'i (%{100 * len(gv05) / len(loss):.0f}) çıkıştan önce en az 0,5σ, {len(gv2)}'i (%{100 * len(gv2) / len(loss):.0f}) en az 2σ lehe gitmişti (σ = giriş günü 1 günlük oynaklık). "
                 f"Tüm trade'lerde medyan MFE {tr.mfe_s.median():.2f}σ, medyan MAE {tr.mae_s.median():.2f}σ. Trade'lerin %{100 * tr.flip_close.mean():.0f}'i doğrudan çevirmeyle (long↔short, aynı anda ters yönde yeni trade) kapanıyor; yani sistem neredeyse hiç nakitte beklemiyor (aynı anda ort. {daily.n_symbols_open.mean():.1f}/9 sembol açık) ve çıkış = ters yönde giriş. Stop ve izleyen çıkış olmadığı için kâr ancak sinyal dönünce realize oluyor.", B)]
if "worst" in figs:
    E_ += [img("worst")]

E_ += [PageBreak(), Paragraph("8. Sinyal kalibrasyonu: güçlü tahmin daha iyi trade mi?", H1), img("calib")]
rows = [["Giriş koşulu", "Grup", "Trade", "Kazanma", "Ort. net (USDT)", "Medyan net (USDT)", "Toplam net"]]
labels = {"absf": "|F| çeyreklik (1 = en zayıf)", "n_aligned": "Aynı yönde uzman sayısı", "sig_bps": "Oynaklık üçlüğü (1 = en düşük)", "size_pct": "Büyüklük üçlüğü (1 = en küçük)"}
for col, g in cal_tabs.items():
    for gi, r in g.iterrows():
        rows.append([labels[col], gi, int(r.n), pct(r.win), f"{r.avg:.3f}", f"{r.med:.3f}", f"{r.net:.1f}"])
E_ += [tbl(rows, [54 * mm, 14 * mm, 16 * mm, 22 * mm, 28 * mm, 30 * mm, 24 * mm])]
gq = cal_tabs["absf"]
gs_ = cal_tabs["size_pct"]
E_ += [Spacer(1, 3), Paragraph(f"Trade başına ortalama net PnL, |F| çeyreklerinde {gq.avg.iloc[0]:.2f} → {gq.avg.iloc[1]:.2f} → {gq.avg.iloc[2]:.2f} → {gq.avg.iloc[3]:.2f} USDT: tek yönlü bir artış yok, yalnızca en güçlü çeyrek belirgin yüksek. "
                                f"Büyüklük üçlüklerinde {gs_.avg.iloc[0]:.2f} / {gs_.avg.iloc[1]:.2f} / {gs_.avg.iloc[2]:.2f} USDT: en küçük iki üçlük zararda, en büyük üçlük toplam net'in {100 * gs_.net.iloc[-1] / tr.net.sum():.0f}%'ini üretiyor "
                                "(büyüklük = tahmin / oynaklık; yani yüksek inançlı, düşük oynaklıklı trade'ler kazandırıyor, küçük trade'ler maliyeti ve gürültüyü taşıyor). Küçük gruplarda gürültü yüksektir; kanıt değil.", SM)]
wdt = tr.groupby("wd").agg(n=("net", "size"), net=("net", "sum"), win=("net", lambda v: (v > 0).mean()), bps=("bps", lambda v: v.clip(v.quantile(0.02), v.quantile(0.98)).mean()))
E_ += [Paragraph("Giriş günü (haftanın günü)", H2), tbl([["Gün", "Trade", "Net PnL", "Kazanma", "Ort. bps"]] + [[["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"][i], int(r.n), f"{r.net:.1f}", pct(r.win), f"{r.bps:.0f}"] for i, r in wdt.iterrows()], [26 * mm, 22 * mm, 28 * mm, 26 * mm, 26 * mm])]

E_ += [PageBreak(), Paragraph("9. Sembol derin incelemesi", H1), img("sym_cum", 150 * mm), img("sym_expo", 150 * mm), img("sym_heat")]
sc = []
for s_ in SYMS:
    t_ = tr[tr.sym == s_]
    cum = H_[s_].net.resample("1D").sum().cumsum()
    sdd = ((cum + CAP).cummax() - (cum + CAP)).max()
    sc.append([s_.replace("USDT", ""), len(t_), f"{t_.net.sum():.1f}", f"{t_[t_.side == 'long'].net.sum():.1f}", f"{t_[t_.side == 'short'].net.sum():.1f}", pct((t_.net > 0).mean()), f"{t_.net.mean():.3f}", f"{t_.hours.median() / 24:.1f}", f"{t_.avg_notional.mean():.1f}", f"{sdd:.1f}"])
E_ += [tbl([["Sembol", "Trade", "Net", "Long net", "Short net", "Kazanma", "Ort. PnL", "Medyan gün", "Ort. notional", "Maks sembol DD (USDT)"]] + sc, [16 * mm, 14 * mm, 17 * mm, 19 * mm, 19 * mm, 18 * mm, 17 * mm, 20 * mm, 20 * mm, 26 * mm])]

E_ += [PageBreak(), Paragraph("10. MAE/MFE zamanlaması ve karşı-olgusal çıkış kuralları", H1), img("timing")]
q_ = lambda x: f"{x.quantile(0.25):.1f} / {x.median():.1f} / {x.quantile(0.75):.1f}"  # noqa: E731
rows = [["Ölçü (25% / medyan / 75%)", "Kâr eden trade", "Zarar eden trade"],
        ["MFE (σ cinsinden)", q_(win.mfe_s), q_(loss.mfe_s)], ["MAE (σ cinsinden)", q_(win.mae_s), q_(loss.mae_s)],
        ["Zirvenin trade süresindeki yeri (0-1)", q_(win.peak_frac.dropna()), q_(loss.peak_frac.dropna())],
        ["Kârın ne kadarı realize edildi (çıkış / MFE)", q_(win.retained.dropna()), q_(loss.retained.dropna())]]
E_ += [tbl(rows, [70 * mm, 50 * mm, 50 * mm]), Spacer(1, 5), img("cf")]
rows = [["Kural", "Mesafe (σ)", "Stop tetiklenen trade", "Lehine (trade / USDT)", "Aleyhine (trade / USDT)", "Net değişim (USDT)", "Toplam brüt fiyat PnL"]] + [[r.rule, f"{r.k:g}", pct(r.hit), f"{r.helped} / {r.helped_usd:+.1f}", f"{r.hurt} / {r.hurt_usd:+.1f}", f"{r.delta:+.1f}", f"{r.cf_total:.1f}"] for r in cf.itertuples()]
bestcf = cf.sort_values("delta", ascending=False).iloc[0]
worstcf = cf.sort_values("delta").iloc[0]
E_ += [tbl(rows, [36 * mm, 17 * mm, 26 * mm, 30 * mm, 30 * mm, 24 * mm, 25 * mm]), Spacer(1, 3),
       Paragraph(f"<b>Okuma:</b> denenen {len(cf)} stop kuralının {int((cf.delta > 0).sum())}'i toplam brüt fiyat PnL'i artırdı. En az zararlı: {bestcf.rule} {bestcf.k:g}σ ({bestcf.delta:+.1f} USDT, tetiklenen trade'lerin %{100 * bestcf.hit:.0f}'i); "
                 f"en zararlı: {worstcf.rule} {worstcf.k:g}σ ({worstcf.delta:+.1f} USDT). Dar stoplar (≤ 3σ) kârı büyük ölçüde keser: kazancı trend süren az sayıdaki büyük trade'ler taşıyor ve o trade'ler yol boyunca stop mesafesinden daha derin geri çekiliyor. "
                 "Geniş 'felaket' stopu (≥ 6σ) maliyeti küçük tutuyor; tek başına bir kuyruk riski sigortası olarak değerlendirilebilir, ama bu yalnızca bir ölçümdür.", B),
       Paragraph(f"Referans: saatlik gerçek pozisyon profilinden yeniden kurulan brüt fiyat PnL toplamı {base_total:.1f} USDT; hakemin brüt fiyat PnL'i {tr.price_pnl.sum():.1f} USDT (aradaki fark saatlik yeniden kurulumun yaklaşıklığıdır). "
                 "<b>Bu bir ölçümdür, strateji testi değil:</b> stop, trade'in kendi saatlik yüksek/düşük yoluna uygulanır; stop seviyesinde dolum varsayılır (gap yok, iyimser); stop sonrası yeniden giriş yok; boyutlama ve portföy etkileşimi yeniden hesaplanmaz; "
                 "aynı saatte hem stop hem yeni zirve olursa önce stop kontrol edilir (kötümser). Tümü görülmüş veride; bir kural önermek için yeterli değildir.", SM)]

import os  # noqa: E402

ROOT_ = Path(__file__).resolve().parents[1]


def dir_summary(d):
    m_ = json.loads((Path(d) / "meta.json").read_text())
    t_ = pd.read_csv(Path(d) / "trades.csv", parse_dates=["opened", "closed"])
    dd_ = pd.read_csv(Path(d) / "daily.csv", index_col=0, parse_dates=True)
    sh, mdd = sharpe_of(dd_.net, m_["cap"])
    w_, l_ = t_[t_.net > 0], t_[t_.net < 0]
    e_ = dd_.equity
    return dict(name=m_["preset"], net=float(dd_.net.sum()), cagr=float((e_.iloc[-1] / m_["cap"]) ** (365.25 / (dd_.index[-1] - dd_.index[0]).days) - 1), sharpe=sh, maxdd=mdd, n=len(t_), win=float((t_.net > 0).mean()),
                payoff=float(w_.net.mean() / abs(l_.net.mean())), pf=float(w_.net.sum() / abs(l_.net.sum())), lev=float(dd_.gross_lev_mean.mean()), longn=float(t_[t_.side == "long"].net.sum()), shortn=float(t_[t_.side == "short"].net.sum()),
                recent=float(dd_.net[dd_.index >= "2025-01-01"].sum()), nmem=len(m_["names"]))


E_ += [CondPageBreak(120 * mm), Paragraph("9b. Bileşim ve uzmanlar", H1)]
sh_all = tr[cc].abs().div(tr[cc].abs().sum(axis=1).replace(0, np.nan), axis=0).mean()
drv = tr.groupby("driver").agg(n=("net", "size"), net=("net", "sum"), win=("net", lambda v: (v > 0).mean()))
rows = [["Uzman", "Ağırlık", "Ağırlık payı", "Ort. |katkı| payı", "Sürücü olduğu trade", "Sürücü net PnL", "Sürücü kazanma"]]
for n_, w_ in zip(NAMES, meta["weights"]):
    dr_ = drv.loc[n_] if n_ in drv.index else None
    rows.append([n_, f"{w_:.3g}", pct(abs(w_) / sum(abs(x) for x in meta["weights"])), pct(sh_all[f"c_{n_}"]), int(dr_.n) if dr_ is not None else 0, f"{dr_.net:.1f}" if dr_ is not None else "-", pct(dr_.win) if dr_ is not None else "-"])
E_ += [Paragraph(f"Bileşim: {meta['preset']} ({len(NAMES)} uzman). 'Sürücü' = giriş gününde pozisyon yönünü en çok destekleyen uzman; 'katkı payı' = |ağırlık × tahmin|'in uzmanlar arasındaki payı (trade ortalaması). Atıf yaklaşıktır, etkileşim artığı ölçülmedi.", SM), tbl(rows, [32 * mm, 18 * mm, 24 * mm, 28 * mm, 30 * mm, 26 * mm, 26 * mm]), Spacer(1, 6)]
# tek başına uzman sonuçları (reports/edge_experts_data: ön kayıtlı aile testi, $10 000, tam K-kartı)
solo = []
for n_ in NAMES:
    f_ = ROOT_ / "reports" / "edge_experts_data" / n_ / "summary.json"
    if f_.exists():
        j_ = json.loads(f_.read_text())
        solo.append([n_, j_["decision"], pct(j_["net"] / 10000), f"{j_['sharpe']:.2f}", pct(j_["maxdd"]), f"{j_['p_gross']:.4f}", f"{j_['dsr']:.3f}", ",".join(k for k, v in j_["passed"].items() if not v) or "-", f"{j_['m2_corr_ev1']:.2f}"])
if solo:
    E_ += [Paragraph("Uzmanlar tek başına (reports/edge_experts.md, $10 000, 2020-04 → 2026-04, tam K1-K9 kartı)", H2),
           tbl([["Uzman", "Karar", "Getiri", "Sharpe", "Maks DD", "K1 p (brüt)", "DSR", "Kalan kartlar", "EV1 kor."]] + solo, [28 * mm, 18 * mm, 16 * mm, 16 * mm, 16 * mm, 20 * mm, 14 * mm, 34 * mm, 16 * mm]), Spacer(1, 6)]
# leave-one-out marjinal katkı (SRC/loo/<uzman>/daily.json: bileşimden o uzman çıkarılıp hakemle yeniden koşuldu)
loo_dir = SRC / "loo"
if loo_dir.exists():
    sh0, dd0 = sharpe_of(daily.net)
    rows = [["Bileşimden çıkarılan", "Net (USDT)", "Δ net", "Sharpe", "Δ Sharpe", "Maks DD", "Δ DD (puan)"]]
    for n_ in NAMES:
        f_ = loo_dir / n_ / "daily.json"
        if not f_.exists():
            continue
        j_ = json.loads(f_.read_text())
        pn = pd.Series(j_["daily"])
        pn.index = pd.to_datetime(pn.index, utc=True)
        sh_, dd_ = sharpe_of(pn.sort_index())
        rows.append([n_, f"{pn.sum():.1f}", f"{pn.sum() - daily.net.sum():+.1f}", f"{sh_:.2f}", f"{sh_ - sh0:+.2f}", pct(dd_), f"{100 * (dd_ - dd0):+.1f}"])
    rows.insert(1, ["(hiçbiri: tam bileşim)", f"{daily.net.sum():.1f}", "-", f"{sh0:.2f}", "-", pct(dd0), "-"])
    E_ += [Paragraph("Marjinal katkı: her uzman bileşimden çıkarılıp yeniden koşuldu (leave-one-out; aynı hakem, aynı veri)", H2), tbl(rows, [46 * mm, 24 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 24 * mm]),
           Paragraph("Δ net/Sharpe pozitifse uzman çıkarılınca sonuç iyileşti (uzmanın katkısı negatif), negatifse kötüleşti. Ağırlık yeniden normalleştirilmez ama `combine` tahmin ölçeği (ortalama |F| = 0,5) otomatik uyum sağlar. Görülmüş veride, tek koşu.", SM), Spacer(1, 6)]
# bileşimler arası karşılaştırma (komut satırında verilen ek veri dizinleri)
cmp_dirs = [d for d in sys.argv[3:] if (Path(d) / "meta.json").exists() and Path(d).resolve() != SRC.resolve()]
if cmp_dirs:
    ss_ = [dir_summary(SRC)] + [dir_summary(d) for d in cmp_dirs]
    r1 = [["Bileşim", "Üye", "Net (USDT)", "CAGR", "Sharpe", "Maks DD", "2025+ net"]] + [[x["name"], x["nmem"], f"{x['net']:.1f}", pct(x["cagr"]), f"{x['sharpe']:.2f}", pct(x["maxdd"]), f"{x['recent']:.1f}"] for x in ss_]
    r2 = [["Bileşim", "Trade", "Kazanma", "Payoff", "Profit factor", "Ort. kaldıraç", "Long net", "Short net"]] + [[x["name"], x["n"], pct(x["win"]), f"{x['payoff']:.1f}", f"{x['pf']:.2f}", f"{x['lev']:.2f}×", f"{x['longn']:.1f}", f"{x['shortn']:.1f}"] for x in ss_]
    E_ += [KeepTogether([Paragraph("Bileşim karşılaştırması (aynı hakem, $1 000)", H2), tbl(r1, [38 * mm, 14 * mm, 26 * mm, 22 * mm, 20 * mm, 24 * mm, 26 * mm]), Spacer(1, 4),
                         tbl(r2, [38 * mm, 18 * mm, 22 * mm, 18 * mm, 24 * mm, 24 * mm, 20 * mm, 20 * mm])])]

E_ += [CondPageBreak(90 * mm), Paragraph("11. Nautilus çapraz kontrolü ve veri bütünlüğü", H1)]
if naut is not None:
    rows = [["Ölçü", "Bu rapor (pandas)", "Nautilus hesaplayıcısı", "Not"],
            ["Pozisyon sayısı", len(tr), n_naut, "aynı trade tanımı"], ["Kazanma oranı (fiyat−komisyon)", pct(ours["win_rate"]), pct(naut["win_rate"]), "Nautilus pozisyon raporu"],
            ["Beklenti (USDT/trade)", f"{ours['expectancy']:.4f}", f"{naut['expectancy']:.4f}", ""], ["Ort. kazanç (USDT)", f"{ours['avg_winner']:.4f}", f"{naut['avg_winner']:.4f}", ""],
            ["Sharpe (günlük getiri)", f"{ours['sharpe']:.3f}", f"{naut['sharpe']:.3f}", "yıllıklaştırma 365"], ["Sortino", f"{ours['sortino']:.3f}", f"{naut['sortino']:.3f}", ""],
            ["Maks drawdown", pct(ours["maxdd"]), pct(naut["maxdd"]), "equity vs bileşik getiri"], ["Yıllık oynaklık", pct(ours["vol"]), pct(naut["vol"]), ""]]
    E_ += [tbl(rows, [52 * mm, 38 * mm, 42 * mm, 46 * mm]), Spacer(1, 3),
           Paragraph("Nautilus'un kendi PnL'i funding içermez (funding hakemde Nautilus dışında muhasebeleşir), bu yüzden kazanma/beklenti karşılaştırması fiyat−komisyon tabanında yapıldı. Sharpe/Sortino/DD/oynaklık aynı günlük getiri serisi üzerinde iki bağımsız uygulamayla hesaplandı.", SM)]
else:
    E_ += [Paragraph("Nautilus çapraz kontrolü bu ortamda koşulamadı (nautilus_trader yok).", B)]
E_ += [Spacer(1, 4), tbl([["Kontrol", "Sonuç"], ["Saatlik PnL bileşimi vs hakem net'i", f"fark {meta['recon_hourly_vs_referee']:.2e} USDT"], ["Pozisyon dönemleri net toplamı vs hakem net'i", f"fark {tr.net.sum() - S['net_pnl']:.2e} USDT"],
                      ["Reddedilen emir / likidasyon / eksik funding", f"{meta['rejected']} / {int(S['n_liq'])} / {int(S['funding_missed'])}"],
                      ["Nedensellik denetimi", ("EV1 için evaluate_book'ta geçti (ledger/ensemble); bu koşu run_book ile (denetimsiz) tekrarlandı" if meta["preset"] == "ev1" else "Bu bileşim için evaluate_book denetimi bu raporda koşulmadı (run_book). Uzman bazında nedensellik/gelecek-bozma testleri tests/test_edge_experts.py'de; bileşim düzeyinde audit.check_causal_book çalıştırılmadı (doğrulanmadı).")]], [70 * mm, 100 * mm])]
E_ += [PageBreak(), Paragraph("Ek A. Kayıp nedeni kuralları (kural tabanlı, öncelik sırasıyla)", H1),
       Paragraph("Yalnızca net &lt; 0 olan trade'ler sınıflanır; ilk uyan kural geçerlidir. (1) <b>Maliyet / funding yedi</b>: brüt fiyat PnL ≥ 0 ama komisyon+funding ile net &lt; 0. "
                 "(2) <b>Şok penceresi</b>: trade LUNA (2022-05-05→05-16), FTX (2022-11-06→11-15) ya da 2021-05-17→05-24 ile örtüşüyor. (3) <b>Büyük kârı geri verdi</b>: MFE ≥ 2σ. (4) <b>Orta kârı geri verdi</b>: 0,5σ ≤ MFE &lt; 2σ. "
                 "(5) <b>Hiç lehe gitmedi, kısa</b>: MFE &lt; 0,5σ ve süre ≤ 72 saat. (6) <b>Hiç lehe gitmedi, uzun</b>: MFE &lt; 0,5σ ve süre &gt; 72 saat. σ = giriş gününün günlük oynaklığı (σ_yıllık/√365); "
                 "eşikler (0,5σ, 2σ, 72 saat) bu rapor için bir kez seçildi, ayarlanmadı; farklı eşikler dağılımı değiştirir. İlk sürümde sabit 50 bps eşiği kullanılmıştı ve zararın %91'i tek kategoriye düşüyordu (medyan 7 gün tutulan bir "
                 "trend sisteminde her trade 50 bps'i aşar), bu yüzden oynaklığa göre ölçeklendi. Etiketler nedensellik iddiası değildir.", B),
       Paragraph("Ek B. Dosyalar ve yeniden üretim", H2),
       Paragraph("Veri: <font name='DV'>modal run modal_app.py --cmd \"python scripts/trade_audit.py --cap 1000 --out /data/audit/ev1_1000\"</font>; Rapor: <font name='DV'>python scripts/trade_audit_report.py &lt;indirilen dizin&gt; reports/trade_audit.pdf</font>. "
                 "Ham tablolar: trades.csv, daily.csv, fills.csv, meta.json (reports/trade_audit_data/).", B)]


def footer(c, d):
    c.saveState()
    c.setFont("DV", 7)
    c.setFillColor(rc.HexColor(MUTED))
    c.drawString(15 * mm, 8 * mm, f"Kepler trade denetimi · {meta['preset']} · {CAP:,.0f} USDT".replace(",", " "))
    c.drawRightString(195 * mm, 8 * mm, f"Sayfa {d.page}")
    c.restoreState()


SimpleDocTemplate(str(PDF), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm, title="Kepler trade denetim raporu", author="Kepler").build(E_, onFirstPage=footer, onLaterPages=footer)
print("PDF:", PDF, "| sayfa için figürler:", len(figs))
