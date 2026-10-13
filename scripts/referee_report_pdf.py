"""Günaydın raporu (PDF, Türkçe): yeni hakem motorunun doğrulama + performans özeti. Girdi: reports/vbt_referee/*.json|npz (Modal koşularının ham çıktıları). Gereksinim: matplotlib, reportlab.
  python scripts/referee_report_pdf.py   ->  reports/vbt_referee/gunaydin_raporu.pdf"""
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

D = Path(__file__).resolve().parents[1] / "reports" / "vbt_referee"
FD = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DV", os.path.join(FD, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(FD, "DejaVuSans-Bold.ttf")))
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 130})
C1, C2, C3, C4 = "#2a6fdb", "#e0782b", "#2f9e6f", "#8a4fd6"
H1 = ParagraphStyle("h1", fontName="DVB", fontSize=15, leading=19, spaceBefore=8, spaceAfter=6, textColor=colors.HexColor("#14325c"))
H2 = ParagraphStyle("h2", fontName="DVB", fontSize=11, leading=14, spaceBefore=6, spaceAfter=3)
B = ParagraphStyle("b", fontName="DV", fontSize=9, leading=12.5, spaceAfter=4)
SM = ParagraphStyle("sm", fontName="DV", fontSize=7.5, leading=10, textColor=colors.HexColor("#444444"))
val = json.loads((D / "validate.json").read_text())
cpu = json.loads((D / "bench_cpu.json").read_text())
gpu = {g: json.loads((D / f"gpu_{g}.json").read_text()) for g in ("T4", "A10G")}


def save(fig, name):
    p = D / f"_{name}.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def f_equiv():
    fig, ax = plt.subplots(2, 1, figsize=(7.2, 4.6), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.3]))
    z = np.load(D / "ev1_diff.npz")
    t = pd.to_datetime(z["ts"], unit="ns")
    ax[0].plot(t, z["cash_ref"], color=C2, lw=2.2, label="Eski hakem (Nautilus) — kümülatif nakit akışı")
    ax[0].plot(t, z["cash_new"], color=C1, lw=1.0, label="Yeni hakem (numba)")
    ax[0].set_ylabel("USDT")
    ax[0].legend(frameon=False, fontsize=8)
    ax[0].set_title("EV1, 6 yıl, 9 sembol, 5 305 dolum: iki motor üst üste biniyor", fontsize=10)
    ax[1].plot(t, (z["cash_new"] - z["cash_ref"]) * 1e6, color=C4, lw=1)
    ax[1].set_ylabel("fark (µUSDT)")
    return save(fig, "equiv")


def f_diff():
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.7))
    names = [v["preset"] for v in val]
    ax[0].bar(names, [max(v["max_abs_px_diff"], 1e-13) for v in val], color=C1)
    ax[0].set_yscale("log")
    ax[0].set_title("Maks. |fiyat farkı| (dolum başına)", fontsize=9)
    ax[0].tick_params(axis="x", labelsize=7)
    ax[1].bar(names, [abs(v["net_new"] - v["net_ref"]) for v in val], color=C3)
    ax[1].set_yscale("log")
    ax[1].set_title("|Net PnL farkı| (USDT)", fontsize=9)
    ax[1].tick_params(axis="x", labelsize=7)
    return save(fig, "diff")


def f_time():
    fig, ax = plt.subplots(figsize=(7.2, 2.7))
    cold = val[0]["t_first"]
    parts = [("Veri yükleme", val[0]["t_load"], C1), ("Kitap (sinyal)", val[0]["t_book"], C3), ("Hakem (soğuk: derleme dâhil)", cold, C2)]
    left = 0
    for n, v, c in parts:
        ax.barh(["Soğuk başlangıç"], [v], left=left, color=c, label=f"{n} {v:.1f} sn")
        left += v
    ax.text(left + 0.2, 0, f"{left:.1f} sn", va="center", fontsize=9)
    left = 0
    for n, v, c in [("Veri yükleme", val[0]["t_load"], C1), ("Kitap (sinyal)", val[0]["t_book"], C3), ("Hakem (sıcak)", val[0]["t_warm"], C2)]:
        ax.barh(["Sıcak (derleme önbellekte)"], [v], left=left, color=c)
        left += v
    ax.text(left + 0.2, 1, f"{left:.1f} sn", va="center", fontsize=9)
    ax.axvline(60, color="#c0392b", ls="--", lw=1)
    ax.text(59, 0.45, "hedef: 60 sn", ha="right", fontsize=8, color="#c0392b")
    ax.set_xlim(0, 65)
    ax.set_xlabel("saniye")
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=3)
    ax.set_title("Uçtan uca (EV1, 473 bin saatlik bar, 9 sembol)", fontsize=10)
    return save(fig, "time")


def f_sweep():
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    lab = ["Hakem tam hat\n(DataFrame dâhil)\n4 iş parçacığı", "Yalnız çekirdek\nCPU 1 çekirdek", "Yalnız çekirdek\nCPU 8 iş parçacığı", "Yalnız çekirdek\nGPU T4", "Yalnız çekirdek\nGPU A10G"]
    v = [cpu["t_sweep_threads4_s"] / cpu["n_scenarios"], np.mean([gpu["T4"]["cpu_1core_s_per_scenario"], gpu["A10G"]["cpu_1core_s_per_scenario"]]), np.mean([gpu["T4"]["cpu_8thread_s_per_scenario"], gpu["A10G"]["cpu_8thread_s_per_scenario"]]), gpu["T4"]["gpu_s_per_scenario"], gpu["A10G"]["gpu_s_per_scenario"]]
    bars = ax.bar(lab, v, color=[C4, C2, C2, C1, C3])
    ax.set_yscale("log")
    ax.set_ylabel("saniye / senaryo (log)")
    for b_, x in zip(bars, v):
        ax.text(b_.get_x() + b_.get_width() / 2, x * 1.15, f"{x * 1000:.1f} ms", ha="center", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    ax.set_title("Senaryo taraması (fee × slip ızgarası, aynı 462 bin bar)", fontsize=10)
    return save(fig, "sweep")


def tbl(rows, widths, head=True):
    t = Table(rows, colWidths=widths, repeatRows=1)
    st = [("FONT", (0, 0), (-1, -1), "DV", 7.8), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bbbbbb")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if head:
        st += [("FONT", (0, 0), (-1, 0), "DVB", 7.8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef8"))]
    t.setStyle(TableStyle(st))
    return t


def P(s, st=B):
    return Paragraph(s, st)


def main():
    gb = gpu["A10G"]
    E_ = [P("Günaydın — Hakem motoru değişimi raporu", ParagraphStyle("t", parent=H1, fontSize=19, leading=24)),
          P("Kepler: NautilusTrader hakemi → numba tabanlı yüksek hızlı hakem. 13 Ekim 2026 sabahı için özet; her rakam Modal koşularının ham çıktılarından (reports/vbt_referee/) geliyor.", SM), Spacer(1, 4),
          P("1. Sonuç özeti", H1),
          P(f"<b>Yeni hakem varsayılan oldu ve Nautilus artık çalıştırılmıyor.</b> Gerçek veride (EV1, ev1_plus_new, all9_equal; 6 yıl, 9 sembol, 462 bin saatlik bar) eski hakemin <b>{sum(v['n_ref'] for v in val):,}</b> dolumunun hepsi "
            f"satır satır eşleşti (maks. fiyat farkı {max(v['max_abs_px_diff'] for v in val):.0e}, maks. net PnL farkı {max(abs(v['net_new'] - v['net_ref']) for v in val):.1e} USDT). Tam uçtan uca süre: soğuk başlangıç ≈ <b>{val[0]['t_load'] + val[0]['t_book'] + val[0]['t_first']:.0f} sn</b> "
            f"(numba derlemesi dâhil), sıcak ≈ <b>{val[0]['t_load'] + val[0]['t_book'] + val[0]['t_warm']:.1f} sn</b>; hedef 60 sn'nin çok altında. Hakem koşusunun kendisi ≈ {val[0]['t_warm']:.1f} sn."),
          P(f"<b>GPU:</b> tek koşuda gereksiz (CPU 0,6 sn). Ancak senaryo taramalarında (fee/slip/gecikme ızgaraları) çekirdek verimi A10G'de {gb['gpu_s_per_scenario'] * 1000:.1f} ms/senaryo; 8 iş parçacıklı CPU'ya göre "
            f"<b>{gb['speedup_vs_8threads']:.0f}×</b>, tek çekirdeğe göre {gb['speedup_vs_1core']:.0f}×. <b>Ama tam hatta kazanç yok</b> (T4, 128 senaryo, funding+özet dâhil: GPU 149 ms vs CPU 168 ms/senaryo = 1,1×): darboğaz CPU'daki özet/funding son işlemi. GPU yolu bağlı (device='gpu', özetler CPU ile aynı, net farkı ≤1,6e-6 USDT) ama 'auto' CPU'dur."),
          tbl([["Ölçüt", "Sonuç"], ["Gerçek veri dolum eşleşmesi", "5 305 / 5 041 / 4 949 satır, hepsi eşleşti"], ["Net PnL farkı (3 ön ayar)", "≤ 2,7e-7 USDT (Nautilus'un 8 basamaklı para yuvarlaması düzeyi)"],
               ["Tam test paketi (Modal, Python 3.12)", "343 geçti, 6 atlandı*, 33 seçilmedi**"], ["Altın sabit sayılar (eski hakemden)", "28 dolum, net −2340,724875: birebir"], ["Soğuk / sıcak uçtan uca", f"{val[0]['t_load'] + val[0]['t_book'] + val[0]['t_first']:.0f} sn / {val[0]['t_load'] + val[0]['t_book'] + val[0]['t_warm']:.1f} sn"]], [75 * mm, 100 * mm]),
          P("* 6 test 'nautilus_trader yoksa atla' kuralıyla atlanıyordu; bu kural kaldırıldı ve testler artık koşuyor (yerelde geçti). ** tests/test_indicators.py TradingView fixture'ı repoda yok (önceden de kırmızıydı, bu işle ilgisiz).", SM),
          P("2. Doğrulama: eski hakemin gerçek çıktılarıyla", H1), Image(f_equiv(), 170 * mm, 170 * mm * 4.6 / 7.2 * 0.95), Image(f_diff(), 170 * mm, 170 * mm * 2.7 / 7.2),
          P("Referans: <font name='DV'>reports/trade_audit_data/&lt;ön ayar&gt;/fills.csv</font> (Nautilus'un ürettiği dolumlar). Karşılaştırma anahtarı: sembol + zaman damgası + yön + miktar; fiyat ve komisyon ayrıca kıyaslandı. Nautilus bu oturumda hiç çalıştırılmadı."),
          tbl([["Ön ayar", "Dolum", "Eşleşen", "Maks |Δfiyat|", "Maks |Δkomisyon|", "Net (yeni)", "Net (eski)"]] + [[v["preset"], v["n_ref"], v["rows_matched"], f"{v['max_abs_px_diff']:.1e}", f"{v['max_abs_comm_diff']:.1e}", f"{v['net_new']:.6f}", f"{v['net_ref']:.6f}"] for v in val], [30 * mm, 15 * mm, 17 * mm, 25 * mm, 28 * mm, 30 * mm, 30 * mm]),
          PageBreak(), P("3. Bağımsız muhasebe ve test kanıtları", H1),
          P("• <b>Elle hesaplı testler</b> (long/short, flip, lot, min notional, funding sınırları, likidasyon, mark tetiği, stop, gap, portföy, brüt tavan, equity ölçekleme): tests/test_referee.py, test_stops.py, test_liq_mark.py, test_portfolio.py, test_realistic.py, test_review_fixes.py — hepsi değiştirilmeden geçti."),
          P("• <b>Altın sabit sayılar</b> (eski hakemden alınmış 28 dolumlu fixture, 10x likidasyon): ilk denemede 23 dolum çıkmıştı; fark, Nautilus'un L1 bar yürütmesindeki hacim kuralıydı (aşağıda). Kural kaynak koddan okunup uygulandıktan sonra sayılar birebir tuttu."),
          P("• <b>Yeni bağımsız testler</b> (tests/test_referee_engine.py, 13 test): (i) net = dolumlardan nakit akışı + son pozisyon − komisyon + funding − likidasyon ücreti − çıkış maliyeti kimliği, 6 rastgele senaryoda; (ii) funding'in motordan bağımsız yeniden hesabı (T öncesi dolumlar × mark × oran); "
            "(iii) saatlik PnL yeniden kurulumu (report.hourly_pnl) toplamı; (iv) <b>vectorbt</b> Portfolio.from_orders'a motorun dolumları verilip PnL'in ayrı muhasebeyle örtüşmesi; (v) hacim-kuralı, marj reddi ve iş parçacığı güvenliği/belirlenimlilik testleri."),
          P("• <b>Mimari kapı</b> (tests/test_architecture.py) yeşil: yeni modül referee_core hakem katmanına eklendi; dosyalar ≤ 300 satır."),
          P("4. Performans", H1), Image(f_time(), 165 * mm, 165 * mm * 2.7 / 7.2), Image(f_sweep(), 165 * mm, 165 * mm * 3.0 / 7.2),
          P(f"Aşama dökümü (Modal CPU, 462 bin bar): girdi hazırlığı ≈ {cpu['t_prep_inputs_s'] * 1000:.0f} ms, çekirdek ≈ 0,5–0,6 sn (olay başına ≈ 0,6 µs), özet/DataFrame ≈ 0,1 sn. 64 senaryo: seri {cpu['t_sweep_serial_s']:.0f} sn → hazırlık önbellekli seri {cpu['t_sweep_prepared_serial_s']:.0f} sn → 4 iş parçacığı {cpu['t_sweep_threads4_s']:.1f} sn "
            f"({cpu['n_scenarios'] / cpu['t_sweep_threads4_s']:.1f} senaryo/sn). Çekirdek <font name='DV'>nogil</font> olduğu için iş parçacıkları gerçekten paralel koşar (referee.run_many). Nautilus'un süre referansı bu oturumda <b>ölçülmedi</b> (çalıştırma yasağı); repo notları günlük açıkken koşuların saatler sürdüğünü söylüyor."),
          tbl([["GPU", "ms / senaryo", "CPU 1 çekirdek", "CPU 8 iş parçacığı", "Hız (1 çekirdek)", "Hız (8 iş p.)", "Bakiye farkı"]] + [[k, f"{g['gpu_s_per_scenario'] * 1000:.1f}", f"{g['cpu_1core_s_per_scenario'] * 1000:.0f} ms", f"{g['cpu_8thread_s_per_scenario'] * 1000:.0f} ms", f"{g['speedup_vs_1core']:.0f}×", f"{g['speedup_vs_8threads']:.1f}×", f"{g['max_abs_balance_diff_vs_cpu']:.0e}"] for k, g in gpu.items()], [20 * mm, 24 * mm, 26 * mm, 30 * mm, 26 * mm, 24 * mm, 24 * mm]),
          P("GPU yolu: referee_core.py'nin AYNI kaynak metni numba.cuda cihaz fonksiyonlarına derlenir (kod kopyası yok); iş parçacığı başına bir senaryo, 512'lik gruplar. Derleme + ısınma ≈ 11 sn tek seferlik. Küçük gruplarda (64 senaryo) kazanç ≈ 2×'e düşüyor: GPU yalnızca yüzlerce senaryolu taramada anlamlı.", SM),
          PageBreak(), P("5. Eski motordan taşınan (ve belgede eksik olan) kurallar", H1),
          P("Nautilus çalıştırılmadığı için kurallar 2.0.0rc5 <b>kaynak kodunun okunmasıyla</b> çıkarıldı ve altın fixture ile gerçek veriyle sınandı:"),
          P("• Bar → O,H,L,C tikleri; tik yalnızca son tik fiyatından farklıysa işlenir. Tik boyutu = bar hacmi/4 (lot adımına inip 4'e bölünür). L1 kitap = son tikin (fiyat, boyut).<br/>"
            "• Piyasa ve stop emri kitap boyutu kadar tek fiyattan dolar; <b>kalan miktar son dolum fiyatının 1 tick ötesinden</b> (alış +, satış −) dolar. Stop tetik fiyatından, gap'te (açılış tiki) piyasadan dolar.<br/>"
            "• <b>BACKTEST.md §6.3 'hakem hacme bağlı dolum yapmaz' diyordu; bu yanlıştı</b> — hakem hacim sınırlıydı (§6.6'da düzeltildi). Gerçek EV1 verisinde etkisi sıfır (hiçbir dolum bölünmedi), ama düşük hacimli sembollerde/küçük barlarda anlamlı.<br/>"
            "• Marj: başlangıç marjı = notional / kaldıraç × margin_init (=1/kaldıraç), serbest bakiye (bakiye − bakım marjı kilidi) aşılırsa emir reddedilir (n_rejected → defter koşuyu kabul etmez). Kitap fiyatı stop seviyesindeyse stop reddedilir.<br/>"
            "• Komisyon 8 basamağa yuvarlanır; flip'te komisyon kapanan/açılan miktarla orantılı bölünür; pozisyon raporu (positions) aynı tanım."),
          P("6. Kalan boşluklar ve dürüst notlar", H1),
          P("• <b>Doğrulanmayan/yaklaşık:</b> bekleyen emirlerin kilitlediği başlangıç marjı serbest bakiyeden düşülmüyor (yalnızca bakiye ≈ notional/100 mertebesine inince fark eder); bar fiyatları tick'e yuvarlama beraberlik (tie) durumlarında Decimal ile bit-düzeyi aynı olmayabilir; lot miktarı tavanı (floor) için göreli 1e-15 tolerans kullanılıyor (rastgele testlerde sapma görülmedi).<br/>"
            "• Nautilus'un 'tick katı olmayan fiyatta sessiz dolum atlama' davranışı taşınmadı (yeni motor bar fiyatından doldurur); audit_fix betiğindeki 'emir niyeti = dolum' doğrulaması bu yüzden artık gereksiz ama zararsız.<br/>"
            "• GPU yolu üretim hattına bağlı değil: funding ve özet GPU çıktısından üretilmiyor; yalnızca çekirdek verimi ölçüldü. Geniş taramalar için bağlanması yarım günlük iş.<br/>"
            "• Soğuk başlangıçtaki ≈ 10–15 sn numba derlemesi önbelleğe alınamadı (Modal'de kaynak dosya zaman damgası her koşuda değişiyor); imaja derleme adımı eklenerek kalkabilir.<br/>"
            "• Nautilus süre referansı ve yeni motorun EV1 dışı (ör. zone_fade, turtle) gerçek veri koşularında Nautilus eşleştirmesi bu oturumda yok; bu yollar yalnızca birim testlerle (geçti) doğrulandı.<br/>"
            "• Bağımlılık: pyproject'ten nautilus_trader kaldırıldı, uv.lock güncellendi (Modal imajı daha küçük/hızlı kurulur)."),
          P("7. Değişen dosyalar", H1),
          P("<b>Yeni:</b> kepler/referee_core.py, tests/test_referee_engine.py, scripts/referee_validate.py, referee_bench.py, referee_gpu_dump.py, referee_gpu_bench.py, referee_report_pdf.py, reports/vbt_referee/*.<br/>"
            "<b>Değişen:</b> kepler/referee.py (yeniden yazıldı; API aynı: Spec, run, run_portfolio, + prepare, run_many), kepler/tape.py (yorum), pyproject.toml, uv.lock, tests/test_architecture.py (LAYERS satırı), tests/test_env.py, tests/test_signal_diag.py, test_signal_phase2.py, test_zone_fade.py (nautilus importorskip kaldırıldı), scripts/audit_fix.py (Nautilus günlük sarmalayıcısı kaldırıldı), BACKTEST.md (§6.6), MISSION.md, ARCHITECTURE.md, docs/factory.md."),
          ]
    doc = SimpleDocTemplate(str(D / "gunaydin_raporu.pdf"), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title="Kepler hakem motoru değişimi — günaydın raporu")
    doc.build(E_)
    for f in D.glob("_*.png"):
        f.unlink()
    print("yazıldı", D / "gunaydin_raporu.pdf")


if __name__ == "__main__":
    main()
