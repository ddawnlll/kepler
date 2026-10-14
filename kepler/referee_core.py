"""Hakem çekirdeği (numba): referee.py'nin olay döngüsü. Sözleşme ve anlamlar referee.py başlığında; burada yalnızca durum makinesi.
Olay sırası (zaman, sembol sırası): next_open modunda her bar iki olay (A = açılış parçası (o,o,o,o): eşleşme -> karar; B = gövde (o,h,l,c) t+1sa-1ns: eşleşme),
close modunda gövde T-1ns, karar T; funding T'de dolum/karardan önce. Eşleşme = Nautilus L1 bar yürütmesinin kaynak koddan okunmuş kuralları: bar -> O,H,L,C tikleri,
tik boyutu = hacim/4 (BarTickSizes), piyasa/stop emri tik boyutuyla sınırlı dolar, kalan miktar son dolum fiyatının 1 tick ötesinden dolar, stop tetik fiyatından (gap'te piyasadan) dolar.
Miktarlar tam sayı lot (U[k,0] = 10^sp, U[k,1] = 10^pp, U[k,2] = tick artışı, U[k,3] = adım/lot), fiyatlar gerçek tick katına yuvarlanmış float. Nautilus çalıştırılmaz."""
import numpy as np
from numba import njit

# F sütunları (float): ortalama giriş, strateji stopu, son hedef, bekleyen koruyucu seviye, son LP, son tik fiyatı, döngü realize
AVG, STOP, LAST, ORD, LP, PX, CYC, TLAST, BP = range(9)  # TLAST: motorun son tik fiyatı; BP: L1 kitap fiyatı
# I sütunları (int): lot, stop kilidi (±1), ölü, döngü açılış ts
LOT, HALT, DEAD, COPEN, BS = range(5)  # COPEN: açık döngünün PI satırı; BS: L1 kitap boyutu (lot)
# P: yan ücret, kaldıraç, mmr, liq, min_notional, sermaye, equity_scale, gross_cap (0 = yok), mod, likidasyon ücret oranı
FEE, LEV, MMR, LIQ, MINN, CAP, EQS, GCAP, MODE, LQF = range(10)
HOUR = 3_600_000_000_000
KIND_OPEN, KIND_BODY, KIND_CLOSE, KIND_FUND = 0, 1, 2, 3


@njit(cache=True, nogil=True)
def _lots(num, px, usc, step):
    """floor(num / px / adım): Decimal ROUND_DOWN karşılığı (göreli 1e-15 tolerans: tam bölünen yuvarlak sayılar float'ta 1 ulp altına düşmesin)."""
    return np.int64(np.floor(num / px * usc / step * (1.0 + 1e-15))) * np.int64(step)


@njit(cache=True, nogil=True)
def _book(k, d, px, ts, prot, F, I, G, N, U, P, FI, FF, PI, PF):
    """Dolumu muhasebeleştir (bakiye, ortalama giriş, pozisyon döngüsü, kayıt) + on_order_filled sınıflaması (likidasyon / stop kilidi)."""
    sell = d < 0
    ad, p = abs(d), I[k, LOT]
    q = ad / U[k, 0]
    comm = np.round(q * px * P[FEE], 8)
    lp = F[k, LP]
    liq = prot and (not np.isnan(lp)) and (px <= lp if sell else px >= lp)
    if liq:
        I[k, DEAD] = 1
    elif prot:
        I[k, HALT] = 1 if sell else -1
    c = min(ad, abs(p)) if p != 0 and p * d < 0 else 0
    if c > 0:  # azaltma / kapama / çevirme: realize PnL, komisyon miktarla orantılı bölünür
        pnl = np.round((1.0 if p > 0 else -1.0) * (px - F[k, AVG]) * c / U[k, 0], 8)
        G[0] += pnl
        F[k, CYC] += pnl - comm * c / ad
        if c == abs(p):  # döngü kapanır
            PI[I[k, COPEN], 1], PF[I[k, COPEN]] = ts, F[k, CYC]
    o = ad - c
    if o > 0:
        if p == 0 or c == abs(p):  # yeni döngü (çevirmede ortalama = dolum fiyatı)
            F[k, AVG], F[k, CYC] = px, -comm * o / ad
            PI[N[1], 0], PI[N[1], 1], PI[N[1], 2] = ts, 0, k
            I[k, COPEN] = N[1]
            N[1] += 1
        else:
            F[k, AVG] = (F[k, AVG] * abs(p) + px * o) / (abs(p) + o)
            F[k, CYC] -= comm
    G[0] -= comm
    if liq:
        extra = q * px * max(0.0, P[LQF] - P[FEE])
        G[0] -= extra
        G[2] += extra
    I[k, LOT] = p + d
    n = N[0]
    FI[n, 0], FI[n, 1], FI[n, 2], FI[n, 3] = k, ts, -1 if sell else 1, (1 if liq else 0) | (2 if (prot and not liq) else 0)
    FF[n, 0], FF[n, 1], FF[n, 2] = q, px, comm
    N[0] += 1


@njit(cache=True, nogil=True)
def _refresh(k, pxc, ts, F, I, G, N, U, P, RJ, defer=False):
    """Sembol başına TEK koruyucu emir: stop ile LP'den fiyata yakın olan. Dönüş True = seviye pxc'nin ötesinde, hemen piyasa emriyle kapatılmalı.
    Kitap fiyatı zaten seviyedeyse motor stopu reddeder (reject_stop_orders): sayılır, koruma kurulmaz."""
    F[k, ORD] = np.nan
    q = I[k, LOT]
    if q == 0 or I[k, DEAD] == 1:
        return False
    qf, sc = q / U[k, 0], U[k, 1]
    wb = G[0]
    for j in range(I.shape[0]):
        if j != k and I[j, LOT] != 0:
            wb -= abs(I[j, LOT]) / U[j, 0] * F[j, AVG] / P[LEV]
    lp = np.nan
    if P[LIQ] == 1.0:
        lp = (qf * F[k, AVG] - wb) / (qf * (1 - P[MMR])) if qf > 0 else (wb - qf * F[k, AVG]) / (-qf * (1 + P[MMR]))
        lp = np.rint(np.rint(lp / U[k, 2]) * U[k, 2] * sc) / sc if lp > 0 else np.nan
    s = np.rint(np.rint(F[k, STOP] / U[k, 2]) * U[k, 2] * sc) / sc if not np.isnan(F[k, STOP]) else np.nan
    if np.isnan(s) and np.isnan(lp):
        return False
    lvl = lp if np.isnan(s) else (s if np.isnan(lp) else (max(s, lp) if q > 0 else min(s, lp)))
    F[k, LP] = lp
    if defer:  # settlement: yeni koruma bir sonraki piyasa tikinde eşleşir, bayat kitaptan dolum yapılmaz
        F[k, ORD] = lvl
        return False
    if (pxc <= lvl) if q > 0 else (pxc >= lvl):
        return True
    if (F[k, BP] <= lvl) if q > 0 else (F[k, BP] >= lvl):
        RJ[N[2], 0], RJ[N[2], 1], RJ[N[2], 2] = k, ts, 0
        N[2] += 1
        return False
    F[k, ORD] = lvl
    return False


@njit(cache=True, nogil=True)
def _exec(k, d, px, ts, prot, F, I, G, N, U, P, FI, FF, PI, PF, RJ):
    """Piyasa/stop emri: ilk dolum min(kitap boyutu, miktar) @ px, kalan son dolum fiyatının 1 tick ötesinden (L1 hacim tükendi). Ardından koruyucu emri yenile;
    seviye fiyatın ötesindeyse reduce-only piyasa kapama (kitap fiyatından). Kitap yoksa emir reddedilir ('No market')."""
    while True:
        if np.isnan(F[k, BP]):
            RJ[N[2], 0], RJ[N[2], 1], RJ[N[2], 2] = k, ts, d
            N[2] += 1
            return
        sg, ad = (1 if d > 0 else -1), abs(d)
        q1 = min(I[k, BS], ad)
        _book(k, sg * q1, px, ts, prot, F, I, G, N, U, P, FI, FF, PI, PF)
        last = px
        if ad > q1:
            last = px + sg * U[k, 2]
            _book(k, sg * (ad - q1), last, ts, prot, F, I, G, N, U, P, FI, FF, PI, PF)
        if not _refresh(k, last, ts, F, I, G, N, U, P, RJ):
            return
        d, prot, px = -I[k, LOT], True, F[k, BP]


@njit(cache=True, nogil=True)
def _tick(k, price, size, at_market, ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ):
    """Bir bar tiki: kitabı güncelle (tik boyutu 0 ise tamamen atla), bekleyen koruyucu stopu tetik kontrolüyle eşleştir. Tetik: stop satış fiyat <= seviye, alış >= seviye."""
    if size == 0:
        return
    F[k, BP], I[k, BS] = price, size
    lvl, q = F[k, ORD], I[k, LOT]
    if not np.isnan(lvl) and q != 0 and ((price <= lvl) if q > 0 else (price >= lvl)):
        F[k, ORD] = np.nan
        _exec(k, -q, price if at_market else lvl, ts, True, F, I, G, N, U, P, FI, FF, PI, PF, RJ)


@njit(cache=True, nogil=True)
def _bar(k, o, h, l, c, sz, ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ):  # noqa: E741
    """Nautilus process_trade_ticks_from_bar: O (son fiyattan farklıysa; boşluk/piyasadan), H (> son), L (< son), C (!= son); sıra O,H,L,C."""
    last = F[k, TLAST]
    crossed = not np.isnan(F[k, ORD]) and ((o <= F[k, ORD]) if I[k, LOT] > 0 else (o >= F[k, ORD]))
    if np.isnan(last) or o != last or crossed:
        _tick(k, o, sz[0], True, ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ)
        last = o
    if h > last:
        _tick(k, h, sz[1], False, ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ)
        last = h
    if l < last:
        _tick(k, l, sz[2], False, ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ)
        last = l
    if c != last:
        _tick(k, c, sz[3], False, ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ)
        last = c
    F[k, TLAST] = last


@njit(cache=True, nogil=True)
def _decide(k, tg, st, px, ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ):
    """Strateji.on_bar karar bölümü: stop seviyesi güncelle, hedef -> emir (lot yuvarlama, gross_cap, equity_scale, min notional, marj kontrolü)."""
    K = I.shape[0]
    F[k, PX] = px
    if I[k, DEAD] == 1:
        return
    old, new = F[k, STOP], st  # eksik yuva = NaN (ilk yuvalarda önceki stop zaten NaN)
    F[k, STOP] = new
    sent = False
    if not np.isnan(tg):
        d = 1 if tg > 0 else (-1 if tg < 0 else 0)
        if I[k, HALT] != 0 and I[k, HALT] != d:
            I[k, HALT] = 0
        if I[k, HALT] == 0 and tg != F[k, LAST]:
            F[k, LAST] = tg
            f = 1.0
            if P[EQS] == 1.0:
                eq = G[0]
                for j in range(K):
                    if I[j, LOT] != 0 and F[j, PX] != 0.0:
                        eq += I[j, LOT] / U[j, 0] * (F[j, PX] - F[j, AVG])
                f = max(eq / P[CAP], 0.0)
            pos = I[k, LOT]
            want = _lots(abs(tg) * f, px, U[k, 0], U[k, 3])
            if P[GCAP] > 0 and want > abs(pos):
                room = P[GCAP] * f
                for j in range(K):
                    if j != k and F[j, PX] != 0.0:
                        room -= abs(I[j, LOT]) / U[j, 0] * F[j, PX]
                want = max(min(want, _lots(max(room, 0.0), px, U[k, 0], U[k, 3])), abs(pos) if pos * d > 0 else 0)
            want *= d
            delta = want - pos
            reducing = want == 0 or (want * pos > 0 and abs(want) < abs(pos))
            if delta != 0 and (reducing or abs(delta) / U[k, 0] * px >= P[MINN] * (1 - 1e-12)):
                sent = True
                lock = 0.0  # Nautilus marj hesabı: emir başlangıç marjı = notional/kaldıraç x margin_init(=1/kaldıraç); açık pozisyonlar bakım marjı (notional/kaldıraç x mmr) kilitler
                for j in range(K):
                    if I[j, LOT] != 0:
                        lock += abs(I[j, LOT]) / U[j, 0] * F[j, PX] / P[LEV] * P[MMR]
                if not reducing and abs(delta) / U[k, 0] * px / P[LEV] / P[LEV] > G[0] - lock + 1e-9:  # INITIAL_MARGIN_EXCEEDS_FREE_BALANCE: emir reddedilir, hedef 'denendi' sayılır
                    RJ[N[2], 0], RJ[N[2], 1], RJ[N[2], 2] = k, ts, delta
                    N[2] += 1
                else:
                    _exec(k, delta, F[k, BP], ts, False, F, I, G, N, U, P, FI, FF, PI, PF, RJ)
    if not sent and not (old == new or (np.isnan(old) and np.isnan(new))):
        if _refresh(k, px, ts, F, I, G, N, U, P, RJ):
            _exec(k, -I[k, LOT], F[k, BP], ts, True, F, I, G, N, U, P, FI, FF, PI, PF, RJ)


@njit(cache=True, nogil=True)
def simulate(ev_k, ev_b, ev_kind, T0, O, H, L, C, SZ, TG, ST, U, P, cap_fills, FI, FF, PI, PF, RJ, PRE, END, FT, FV):  # noqa: E741
    """Tüm olayları sırayla koştur. Dönüş: (F, I, G, N). PRE[b] = karar anındaki (eşleşme sonrası) lot, END[b] = gövde sonu lot (funding için)."""
    K = U.shape[0]
    F, I = np.zeros((K, 9)), np.zeros((K, 5), np.int64)
    F[:, STOP], F[:, ORD], F[:, LP], F[:, TLAST], F[:, BP] = np.nan, np.nan, np.nan, np.nan, np.nan
    G, N = np.array([P[CAP], 0.0, 0.0]), np.zeros(3, np.int64)  # nakit, funding, ek likidasyon ücreti
    for e in range(ev_k.shape[0]):
        if N[0] + 8 >= cap_fills or N[2] + 8 >= RJ.shape[0]:
            N[0] = -1
            return F, I, G, N
        k, b, kind = ev_k[e], ev_b[e], ev_kind[e]
        if kind == KIND_FUND:
            cash = -I[k, LOT] / U[k, 0] * FV[b]
            G[0] += cash
            G[1] += cash
            if cash != 0.0:
                for j in range(K):
                    _refresh(j, F[j, PX], FT[b], F, I, G, N, U, P, RJ, True)
        elif kind == KIND_OPEN:
            ts = T0[b]
            _bar(k, O[b], O[b], O[b], O[b], SZ[b], ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ)
            PRE[b] = I[k, LOT]
            _decide(k, TG[b], ST[b], O[b], ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ)
        elif kind == KIND_BODY:
            ts = T0[b] + HOUR - 1
            _bar(k, O[b], H[b], L[b], C[b], SZ[b], ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ)
            F[k, PX] = C[b]
            END[b] = I[k, LOT]
        else:
            ts = T0[b] + HOUR
            PRE[b] = I[k, LOT]
            _decide(k, TG[b], ST[b], C[b], ts, F, I, G, N, U, P, FI, FF, PI, PF, RJ)
    return F, I, G, N
