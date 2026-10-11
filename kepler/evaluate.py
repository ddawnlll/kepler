"""G2 tek giriş: nedensellik denetimi -> hakem -> defter. Hakem sonucu deftere yalnızca buradan (denetimden geçerek) girer.

Sinyal birim pozisyon (+1/-1/0/NaN) döndürür; hedef = birim x notional. Gerçekçi koşul zorunlu: sonraki-bar dolum, slippage >= MIN_SLIP_RT_BPS,
açık pozisyon çıkış maliyeti. `window`: sinyal TAM seride hesaplanır (ısınma), hakem yalnızca pencerede koşar."""
import inspect
from dataclasses import asdict

import pandas as pd

from kepler import audit, ledger, receipt, referee, report, risk, tape

MIN_SLIP_RT_BPS = 1.0  # UNKNOWN: gerçek slippage ölçülmedi; majörlerde alt sınır varsayımı, duyarlılık ızgarası g2'de


def _realistic(specs):
    for sp in specs:
        if sp.fill != "next_open" or not sp.close_out or not sp.liq or sp.slip_rt_bps < MIN_SLIP_RT_BPS or sp.fee_rt_bps < 1.0 or sp.mmr <= 0:
            raise ValueError(f"gerçekçi olmayan Spec reddedildi (fill=next_open, close_out, liq, slip>={MIN_SLIP_RT_BPS}, fee>=1, mmr>0): {sp}")


def evaluate(signal, kl: pd.DataFrame, specs: list, ledger_path, hypothesis: str, data: str, funding=None, mark=None,
             notional: float = 1000.0, name: str = "", params: dict | None = None, window: tuple | None = None, size=None, kill_dd: float | None = None, symbol: str | None = None) -> list[dict]:
    """Her spec için {'res': hakem sonucu, 'row': defter satırı}. Denetim (nedensellik) sinyal başına bir kez koşar.
    size(kl, unit, capital) -> hedef notional serisi (risk motoru, örn. risk.vol_target); verilmezse sabit `notional`. kill_dd: equity düşüşü eşiği (risk.kill_switch)."""
    _realistic(specs)
    audit.assert_causal(signal, kl)
    unit = tape.check_target(kl, signal(kl).astype(float))
    if not unit.equals(signal(kl).astype(float)) or unit.abs().max() > 1:
        raise ValueError("sinyal belirlenimsiz ya da birim pozisyon |x|<=1 değil")
    utc = lambda x: pd.Timestamp(x).tz_localize("UTC") if pd.Timestamp(x).tzinfo is None else pd.Timestamp(x).tz_convert("UTC")  # noqa: E731
    lo, hi = (utc(window[0]), utc(window[1])) if window else (kl.index[0], kl.index[-1] + pd.Timedelta("1h"))
    keep = (kl.index >= lo) & (kl.index < hi)
    if not keep.any():
        raise ValueError("pencerede bar yok")
    unit = unit.ffill()  # NaN = tut: pencere başında tutulan pozisyon açık hedef olur (pencereler bağımsız koşar)
    sig_src = inspect.getsourcefile(signal)
    out = []
    for sp in specs:
        k, mk = kl[keep], None if mark is None else mark.loc[(mark.index >= lo) & (mark.index < hi)]
        tgt = (unit * notional if size is None else size(kl, unit, sp.capital))[keep]
        if size is not None and tgt.abs().max() > sp.capital * sp.leverage:
            raise ValueError("risk motoru kaldıraç tavanını aştı")
        res = referee.run(k, tgt, sp, funding, mk)
        tripped = None
        if kill_dd is not None:
            tgt, tripped = risk.kill_switch(tgt, risk.equity_curve(k, mk, funding, res, sp), kill_dd)
            res = referee.run(k, tgt, sp, funding, mk) if tripped is not None else res
        cfg = dict(name=name, params=params or {}, notional=notional, spec=asdict(sp), window=[str(lo), str(hi)], audit_causal=True, sized=size is not None, kill_dd=kill_dd, kill_at=str(tripped), **({"symbol": symbol} if symbol else {}))
        rc = receipt.make(cfg, {symbol or "SYM": dict(kl=kl, funding=funding, mark=mark)}, cut=(lo, hi), book=signal, extra_files=[sig_src] if sig_src else [])  # #12: tüm kod + config + kullanılan veri içeriği
        if why := ledger.invalid_reason(res["summary"]):
            ledger.record_attempt(ledger_path, "invalid", hypothesis, cfg, rc["code_hash"], data, reason=why, result=res["summary"], receipt=rc)
            raise ledger.InvalidRun(why)
        out.append(dict(res=res, row=ledger.record(ledger_path, "referee", hypothesis, cfg, rc["code_hash"], data, result=res["summary"], receipt=rc)))
    return out


def run_book(out: dict, data: dict[str, dict], spec, lo, hi, kill_dd: float | None = None):
    """Hesaplanmış kitabı ({sym: DataFrame[target, stop]}) [lo, hi) penceresinde portföy hakemiyle koşar (denetimsiz, deftersiz; sağlamlık koşuları için). Pencere başında tutulan
    pozisyon açık hedef olur. Kill switch: portföy equity'si kill_dd düşünce tüm hedefler 0. (hakem sonucu, pencere verisi, tetik zamanı)"""
    keep = {s: (d["kl"].index >= lo) & (d["kl"].index < hi) for s, d in data.items()}
    win = {s: dict(d, kl=d["kl"][keep[s]], target=out[s].target.ffill().fillna(0.0)[keep[s]], stop=out[s].stop[keep[s]],
                   mark=None if d.get("mark") is None else d["mark"].loc[(d["mark"].index >= lo) & (d["mark"].index < hi)]) for s, d in data.items() if keep[s].any()}
    res, tripped = referee.run_portfolio(win, spec), None
    if kill_dd is not None:
        eq = spec.capital + report.book_pnl(win, res, spec).cumsum()
        _, tripped = risk.kill_switch(pd.Series(0.0, index=eq.index), eq, kill_dd)
        if tripped is not None:
            for d in win.values():
                d["target"], d["stop"] = d["target"].where(d["target"].index < tripped, 0.0), d["stop"].where(d["stop"].index < tripped)
            res = referee.run_portfolio(win, spec)
    return res, win, tripped


def evaluate_book(book, data: dict[str, dict], specs: list, ledger_path, hypothesis: str, data_hash: str, name: str = "", params: dict | None = None, window: tuple | None = None, kill_dd: float | None = None) -> list[dict]:
    """Portföy (Motor v2): data[sym] = dict(kl, funding, mark[, tick, step]); book({sym: kl}) -> {sym: DataFrame[target, stop]} (örn. turtle.turtle_book). Sıra: gerçekçi Spec ->
    tüm panel bozularak nedensellik denetimi -> belirlenimlilik -> portföy hakemi (`run_book`; ortak sermaye; Spec.gross_cap; isteğe bağlı kill switch) -> defter.
    Kitap tam seride hesaplanır (ısınma); hakem yalnızca pencerede koşar. Dönüş satırı: res, row, win (pencere verisi: report.book_pnl için)."""
    _realistic(specs)
    kls = {s: d["kl"] for s, d in data.items()}
    audit.assert_causal_book(book, kls)
    out = book(kls)
    if not all(out[s].equals(book(kls)[s]) for s in out):
        raise ValueError("kitap belirlenimsiz")
    utc = lambda x: pd.Timestamp(x).tz_localize("UTC") if pd.Timestamp(x).tzinfo is None else pd.Timestamp(x).tz_convert("UTC")  # noqa: E731
    lo, hi = (utc(window[0]), utc(window[1])) if window else (min(k.index[0] for k in kls.values()), max(k.index[-1] for k in kls.values()) + pd.Timedelta("1h"))
    extra = [x for x in [inspect.getsourcefile(book)] if x]
    rows = []
    for sp in specs:
        cfg0 = dict(name=name, params=params or {}, spec=asdict(sp), window=[str(lo), str(hi)], audit_causal=True, book=True, kill_dd=kill_dd)
        try:
            res, win, tripped = run_book(out, data, sp, lo, hi, kill_dd)
        except Exception as e:  # çöken koşu araştırma izinden kaybolmasın (receipt tam girdiyi kapsar; pencere dilimi yok)
            ledger.record_attempt(ledger_path, "failed", hypothesis, cfg0, "", data_hash, reason=f"{type(e).__name__}: {e}"[:300], receipt=receipt.make(cfg0, data, cut=(lo, hi), book=book, extra_files=extra))
            raise
        mut = report.reconcile(win, res, sp)  # saatlik yeniden kurulum toplamı = hakem net'i (önceden tanımlı tolerans); ayrışırsa sessiz geçmez
        res["summary"]["recon_diff"] = mut["diff"]
        cfg = dict(cfg0, symbols=sorted(win), kill_at=str(tripped))
        rc = receipt.make(cfg, win, cut=(lo, hi), book=book, extra_files=extra)  # win = hakemin gerçekten tükettiği pencere verisi
        why = ledger.invalid_reason(res["summary"]) or (None if mut["ok"] else f"PnL mutabakatı tutmadı: fark {mut['diff']:.6f} > tolerans {mut['tol']:.6f} USDT")
        if why:  # geçersiz: performans istatistiğine girmez, araştırma geçmişinde `invalid` olarak korunur
            ledger.record_attempt(ledger_path, "invalid", hypothesis, cfg, rc["code_hash"], data_hash, reason=why, result=res["summary"], receipt=rc)
            raise ledger.InvalidRun(why)
        rows.append(dict(res=res, win=win, row=ledger.record(ledger_path, "referee", hypothesis, cfg, rc["code_hash"], data_hash, result=res["summary"], receipt=rc)))
    return rows
