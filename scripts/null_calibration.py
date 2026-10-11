"""#15: rotasyon null'u ve IC bootstrap kalibrasyonu (yalnız sentetik; geliştirme verisi bile yüklenmez, Modal gerekmez, mühür yok).
  python scripts/null_calibration.py --out reports/signal_diagnostics_data/null_calibration.json [--reps 200]
ESTIMAND / VARSAYIMLAR (BACKTEST.md §9 'Rotasyon null'u'): K1 rotasyon null'u "koşullu zamanlama" sorar: SABİT bir sinyal serisinin (uzman, evren, ağırlıklar, aktiflik maskesi donmuş) zamanlaması şans mı?
Koşulladığı seçimler: uzman/bileşim, evren, parametreler, aktiflik maskesi. Varsayımlar: sinyal serisinin dairesel kayması kendi zaman yapısını (otokorelasyon, tutma süresi) korur ve
fiyat getirisi ile bağımsızdır (sıfır-edge altında değiştirilebilirlik); kayma, takvim/funding/aktiflik etkilerini bozar (aşağıda ölçülür). Seçim prosedürünü (en iyiyi seçme) KAPSAMAZ: `selection_null` ayrı kalibre eder.
NEGATİF KONTROLLER (önceden seçildi, en iyi sonuç sonradan seçilmez; hepsi raporlanır): NEGATIVE_CONTROLS."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signal_diag_stats as sx  # noqa: E402

NEGATIVE_CONTROLS = (
    "rotation_common_offset: tüm semboller aynı k ile dairesel kaydırılır (mevcut K1, birincil)",
    "rotation_independent_offset: her sembol kendi k'siyle (kesit yapısı bozulur; maruziyeti eşleyen alternatif)",
    "time_shuffle_blocks: sinyal blokları (ort. 20 gün) karıştırılır (tutma süresi korunur, zaman yapısı bozulur)",
)


def exposure_diag(f: np.ndarray, act: np.ndarray, k: int | None = None) -> dict:
    """[T,S] tahmin ve aktiflik maskesi için maruziyet/işlem özeti. k verilirse (sıfır dolu) seri k gün kaydırılıp mevcut maske uygulanır (null'un gerçekte kullandığı dönüşüm)."""
    x = np.where(act, np.nan_to_num(f), 0.0)
    if k is not None:
        x = np.where(act, np.roll(x, k, axis=0), 0.0)
    nz, chg = x != 0, np.abs(np.diff(x, axis=0, prepend=0.0)) > 1e-12
    runs = [len(r) for s in range(x.shape[1]) for r in np.split(np.arange(len(x)), np.flatnonzero(np.diff(nz[:, s].astype(int))) + 1) if nz[r[0], s]]
    return dict(active_cells=int(act.sum()), active_nonzero_cells=int(nz.sum()), gross_mean=float(np.abs(x).sum(1).mean()), net_mean=float(x.sum(1).mean()),
                n_changes=int(chg.sum()), mean_hold_days=float(np.mean(runs)) if runs else 0.0, dow_gross=[float(np.abs(x)[i::7].sum(1).mean()) if len(x) > i else 0.0 for i in range(7)])


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return float(c - h), float(c + h)


def ic_ts_rerank(F: np.ndarray, Y: np.ndarray, idx: np.ndarray, min_n: int = 10) -> np.ndarray:
    """REFERANS: replika İÇİNDE yeniden sıra alınan sembol-başına Spearman, n_s ağırlıklı havuz (tanıma birebir uyan, yavaş estimator). idx: [B,T] örneklenen tarihler."""
    S, out = F.shape[1], np.empty(len(idx))
    for b, ix in enumerate(idx):
        num = den = 0.0
        for s in range(S):
            f, y = F[ix, s], Y[ix, s]
            v = np.isfinite(f) & np.isfinite(y)
            if v.sum() < min_n:
                continue
            r = np.corrcoef(rankdata(f[v]), rankdata(y[v]))[0, 1]
            if np.isfinite(r):
                num, den = num + v.sum() * r, den + v.sum()
        out[b] = num / den if den else np.nan
    return out


def zero_edge_panel(rng, T: int, S: int, h: int, phi: float):
    """Sıfır-edge: AR(1) tahmin (kalıcı), bağımsız getiri; etiket = ileri h-gün toplam getiri (ÖRTÜŞEN)."""
    F = np.zeros((T + h, S))
    for t in range(1, T + h):
        F[t] = phi * F[t - 1] + np.sqrt(1 - phi**2) * rng.normal(size=S)
    r = rng.normal(size=(T + h, S))
    c = np.cumsum(r, 0)
    Y = c[h:T + h] - c[:T]
    return F[:T], Y


def estimator_check(seed=0, T=300, S=6, h=10, phi=0.9, B=300, mean_block=20.0) -> dict:
    """Aynı replika indeksleri üzerinde sabit-sıra (mevcut) ve replika-içi yeniden-sıra estimator'ı: değerler ve SE."""
    rng = np.random.default_rng(seed)
    F, Y = zero_edge_panel(rng, T, S, h, phi)
    idx = sx.block_idx(T, B, mean_block, seed=1)
    C = np.zeros((B, T))
    np.add.at(C, (np.repeat(np.arange(B), T), idx.ravel()), 1.0)
    est, fixed = sx.ic_ts(F, Y, C, min_n=10)
    rer = ic_ts_rerank(F, Y, idx)
    return dict(point=est, se_fixed=float(np.nanstd(fixed, ddof=1)), se_rerank=float(np.nanstd(rer, ddof=1)), corr_replicas=float(np.corrcoef(fixed, rer)[0, 1]), max_abs_diff=float(np.nanmax(np.abs(fixed - rer))),
                mean_diff=float(np.nanmean(fixed - rer)))


def fp_rate(T, S, h, phi, mean_block, reps, B, rerank=False, seed=0) -> dict:
    """Sıfır-edge süreçte iki yönlü p<0,05 oranı (nominal 0,05), Wilson %95 AA."""
    hits = 0
    for r in range(reps):
        rng = np.random.default_rng([seed, r])
        F, Y = zero_edge_panel(rng, T, S, h, phi)
        idx = sx.block_idx(T, B, mean_block, seed=10_000 + r)
        if rerank:
            est = sx.ic_ts(F, Y, None, min_n=10)[0]
            boots = ic_ts_rerank(F, Y, idx)
        else:
            C = np.zeros((B, T))
            np.add.at(C, (np.repeat(np.arange(B), T), idx.ravel()), 1.0)
            est, boots = sx.ic_ts(F, Y, C, min_n=10)
        hits += bool(sx.summarize(est, boots)["p"] < 0.05)
    lo, hi = _wilson(hits, reps)
    return dict(T=T, S=S, h=h, phi=phi, mean_block=mean_block, reps=reps, B=B, estimator="rerank" if rerank else "fixed_rank", fp=hits / reps, lo=lo, hi=hi)


def selection_null(reps=100, K=9, T=500, S=8, B=100, seed=0) -> dict:
    """Sıfır-edge K uzmandan en yüksek IC-TS'liyi seçme: (a) koşullu rotasyon p'si (yalnız seçilen uzman) (b) prosedür-düzeyi p (tüm uzmanlar aynı k ile kaydırılır, her kaydırmada yeniden max). Yanlış-pozitif oranları."""
    ca = pr = 0
    for r in range(reps):
        rng = np.random.default_rng([seed, r])
        Y = np.cumsum(rng.normal(size=(T + 1, S)), 0)
        Y = Y[1:] - Y[:-1]
        Fs = [rng.normal(size=(T, S)) for _ in range(K)]
        ics = [sx.ic_ts(F, Y, None, min_n=10)[0] for F in Fs]
        best = int(np.argmax(ics))
        ks = np.random.default_rng([seed, r, 1]).integers(int(0.05 * T), int(0.95 * T), B)
        null_one = [sx.ic_ts(np.roll(Fs[best], k, 0), Y, None, min_n=10)[0] for k in ks]
        null_max = [max(sx.ic_ts(np.roll(F, k, 0), Y, None, min_n=10)[0] for F in Fs) for k in ks[: B // 4]]
        ca += (1 + sum(n >= ics[best] for n in null_one)) / (B + 1) < 0.05
        pr += (1 + sum(n >= ics[best] for n in null_max)) / (len(null_max) + 1) < 0.05
    return dict(reps=reps, K=K, conditional_fp=ca / reps, conditional_ci=_wilson(int(ca), reps), procedure_fp=pr / reps, procedure_ci=_wilson(int(pr), reps), nominal=0.05)


def main(out: str, reps: int):
    res = dict(negative_controls=NEGATIVE_CONTROLS, estimator_check=[estimator_check(seed=s) for s in range(3)], fp_fixed=[], fp_rerank=[])
    for h, mb in [(1, 20), (10, 5), (10, 20), (40, 20), (40, 5), (40, 80)]:  # ufuk x blok uzunluğu duyarlılığı
        res["fp_fixed"].append(fp_rate(300, 6, h, 0.9, mb, reps, 200))
    for h, mb in [(10, 20), (40, 20)]:
        res["fp_rerank"].append(fp_rate(300, 6, h, 0.9, mb, max(40, reps // 4), 100, rerank=True))
    res["selection_null"] = selection_null()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1, allow_nan=False))
    print(json.dumps({k: v for k, v in res.items() if k != "negative_controls"}, indent=1)[:4000])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/signal_diagnostics_data/null_calibration.json")
    ap.add_argument("--reps", type=int, default=200)
    a = ap.parse_args()
    main(a.out, a.reps)
