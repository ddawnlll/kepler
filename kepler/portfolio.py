"""Portföy düzeyinde risk motoru (EV1 §4): tahmin F -> hedef notional. Korelasyon farkındalıklı oynaklık hedefi (IDM), sembol/brüt tavanları, tampon (devir azaltma). Yol bağımlı, gün gün.
Uzmanlar yalnızca tahmin verir; büyüklük ve tavanlar burada. `kepler/risk.py` (sembol başına oynaklık hedefi + kill switch, korumalı çekirdek) ile birleştirilmesi
bağımsız incelemeli ayrı iştir (TASKS.md); bu dosya `ensemble.size`ın birebir taşınmış halidir. `p`: `ensemble.Params` benzeri (tau, risk, corr_days, sym_cap, gross_cap, buffer)."""
import numpy as np
import pandas as pd


def size(f: pd.DataFrame, st: dict, capital: float, p) -> pd.DataFrame:
    """Risk motoru: günlük hedef notional [gün x sembol] (aktif olmayan = 0). Yol bağımlı (tampon), gün gün."""
    syms, ret, sig, act = list(f.columns), st["ret"].to_numpy(), st["sigma"].to_numpy(), st["active"].to_numpy()
    fv, out, prev = f.to_numpy(), np.zeros(f.shape), np.zeros(len(syms))
    for d in range(len(f)):
        a = act[d] & ~np.isnan(fv[d])
        tgt, u = np.zeros(len(syms)), np.full(len(syms), np.inf)
        idx = np.flatnonzero(a)
        if len(idx):
            m, s, fa = len(idx), sig[d, idx], fv[d, idx]
            if p.risk:
                lo = max(0, d - p.corr_days + 1)
                rho = pd.DataFrame(ret[lo:d + 1, idx]).corr(min_periods=30).fillna(1.0).to_numpy().copy()  # örtüşmesi yetersiz çift: korelasyon 1 (muhafazakâr)
                np.fill_diagonal(rho, 1.0)
                w = np.full(m, 1.0 / m)
                idm = min(2.5, 1.0 / np.sqrt(w @ np.clip(rho, 0, None) @ w))
                unit = capital * p.tau * w * idm / s
                n = unit * fa
                v = np.sqrt(max(n @ (np.outer(s, s) * rho) @ n, 0.0)) / capital
                if v > p.tau:
                    n *= p.tau / v
            else:
                unit = np.full(m, capital / m)
                n = unit * fa
            n = np.clip(n, -p.sym_cap * capital, p.sym_cap * capital)
            g = np.abs(n).sum()
            if g > p.gross_cap * capital:
                n *= p.gross_cap * capital / g
            tgt[idx], u[idx] = n, unit
        move = np.abs(tgt - prev) > np.where(np.isinf(u), np.inf, p.buffer * np.where(np.isinf(u), 0.0, u))
        prev = np.where(~a, 0.0, np.where(move, tgt, prev))
        out[d] = prev
    return pd.DataFrame(out, index=f.index, columns=syms)
