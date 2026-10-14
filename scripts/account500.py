"""#16: EV1 ve carry_xs için $500 hesap uygulanabilirliği: YALNIZ offline dry replay (canlı API emri/anahtar yok, mühürlü dönem yok; pencere E.MAIN = 2020-04 -> 2026-04).
  python scripts/account500.py --stage rules                       # MEXC contract/detail halka açık GET -> reports/account500_data/mexc_rules.json (fetched_utc kayıtlı)
  modal run --detach modal_app.py --cmd "python scripts/account500.py --stage replay --system EV1 --scenario model_10+2 --out /data/account500"   # 2 sistem x 3 senaryo = 6 ayrı konteyner
ÖNCEDEN YAZILI ÖLÇÜTLER (koşudan önce; sonuca bakılarak değiştirilmez). Her sistem x ücret senaryosu için:
  C1 niyet: bloke (blocked_minimum + noop_lot) niyet oranı <= %5            C2 sonuç: |net(500, kurallı) - net(500, ince adım)| <= %5 x |net(ince adım)| ve |ΔSharpe| <= 0,10
  C3 bütünlük: n_rejected = n_engine_unfilled = n_liq = 0 ve PnL mutabakatı (`report.reconcile`) tutuyor
  C4 kural kaynağı: işlem gören TÜM semboller için MEXC kuralı alınmış ve eşleme birebir (BASEUSDT <-> BASE_USDT); eksik/eşlenmemiş sembol hedef notional payı raporlanır, > %0 ise UNKNOWN
  Kalıcı UNKNOWN (kanıtlanamaz): hesap ücreti/VIP/indirim, likidite/slippage, MEXC funding/marj/mmr kademesi ve fiyat davranışı (Binance replay'i bunları KANITLAMAZ), geçmiş dönemde güncel kuralların geçerliliği ve listeleme tarihi.
  Karar: herhangi C1-C3 FAIL ise FAIL; yoksa UNKNOWN (kalıcı UNKNOWN'lar yüzünden PASS verilmez; ücret doğrulanmadan PASS yok). Operasyonel uygunluk edge değildir.
Uygulanamaz hedefler kör minimuma yukarı yuvarlanmaz, risk bütçesi büyütülmez (hakem `min_notional=0`, gerçek minimum = minVol sözleşme)."""
import argparse
import json
import math
import sys
import time
import urllib.request
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

RULES = Path(__file__).resolve().parent.parent / "reports" / "account500_data" / "mexc_rules.json"
CAP = 500.0
SCENARIOS = {"model_10+2": (10.0, 2.0), "mexc_list_4+2": (4.0, 2.0), "stress_16+4": (16.0, 4.0)}  # (fee RT bps, slip RT bps): model varsayımı / API liste ücreti (hesap ücreti DEĞİL) / MISSION 16 bps + stres slip
FIELDS = ("symbol", "contractSize", "priceUnit", "volUnit", "minVol", "maxVol", "takerFeeRate", "makerFeeRate", "maintenanceMarginRate", "initialMarginRate", "maxLeverage", "state", "apiAllowed", "feeRateMode")


def fetch_rules(out: Path = RULES) -> dict:
    url = "https://contract.mexc.com/api/v1/contract/detail"
    raw = json.loads(urllib.request.urlopen(url, timeout=60).read())["data"]
    syms = {r["baseCoin"] + "USDT": {k: r.get(k) for k in FIELDS} for r in raw if r.get("quoteCoin") == "USDT"}
    doc = dict(source=url, fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), n_usdt=len(syms),
               note="Halka açık GET. Ücret alanları API liste değeri, kullanıcı hesap ücreti/VIP/indirim DEĞİL. Güncel kurallar geçmiş döneme uygulanır (listeleme tarihi/eski kurallar UNKNOWN). Binance->MEXC eşleme yalnız BASEUSDT=BASE_USDT adı (1000x vb. dönüşümler doğrulanmadı).",
               symbols=syms)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True))
    return doc


def verdict(m: dict) -> dict:
    """m: bir koşunun ölçümleri (aşağıdaki `metrics`). Ölçütler modül başlığında."""
    c = dict(
        C1_blocked_share=("PASS" if m["blocked_share"] <= 0.05 else "FAIL", m["blocked_share"]),
        C2_outcome=("PASS" if m["net_rel_diff"] <= 0.05 and m["abs_dsharpe"] <= 0.10 else "FAIL", dict(net_rel_diff=m["net_rel_diff"], abs_dsharpe=m["abs_dsharpe"])),
        C3_integrity=("PASS" if not (m["n_rejected"] or m["n_engine_unfilled"] or m["n_liq"]) and m["recon_ok"] else "FAIL", dict(n_rejected=m["n_rejected"], n_engine_unfilled=m["n_engine_unfilled"], n_liq=m["n_liq"], recon_ok=m["recon_ok"])),
        C4_rules_coverage=("PASS" if m["unmapped_target_share"] == 0 else "UNKNOWN", m["unmapped_target_share"]),
    )
    fail = [k for k, (v, _) in c.items() if v == "FAIL"]
    return dict(criteria=c, overall="FAIL" if fail else "UNKNOWN", failed=fail, permanent_unknown=["hesap ücreti/VIP/indirim", "likidite/slippage", "MEXC funding/marj/mmr kademesi", "geçmişte güncel kuralların geçerliliği"])


def metrics(res: dict, ref: dict, intents: pd.DataFrame, unmapped: float, rc: dict, cap: float = CAP) -> dict:
    s, r = res["summary"], ref["summary"]
    ni = max(len(intents), 1)
    sent = intents.status.isin(["sent", "partial"])
    ach = (intents.pos_qty + np.where(sent, np.sign(intents.delta_qty) * intents.filled_qty, 0)) * intents.px  # fiilen tutulan (işaretli) notional
    tgt = intents.target_notional.to_numpy()
    nz = np.abs(tgt) > 0
    dev = np.abs(tgt - ach)[nz] / np.abs(tgt)[nz] if nz.any() else np.array([0.0])
    f = res["fills"]
    return dict(n_intents=len(intents), by_status=intents.status.value_counts().to_dict(), blocked_share=float(intents.status.isin(["blocked_minimum", "noop_lot"]).sum() / ni),
                blocked_notional=float(s["blocked_notional"]), dev_median=float(np.median(dev)), dev_p90=float(np.quantile(dev, 0.9)), risk_dev_share=float(np.abs(tgt - ach).sum() / max(np.abs(tgt).sum(), 1e-12)),
                net=float(s["net_pnl"]), net_ref=float(r["net_pnl"]), net_rel_diff=float(abs(s["net_pnl"] - r["net_pnl"]) / max(abs(r["net_pnl"]), 1e-12)), abs_dsharpe=float(abs(res["sharpe"] - ref["sharpe"])),
                sharpe=float(res["sharpe"]), sharpe_ref=float(ref["sharpe"]), fee=float(s["fee"]), slippage=float(s["slippage"]), funding=float(s["funding"]), gross_pnl=float(s["gross_pnl"]),
                turnover_x_cap=float((f.qty * f.px).sum() / cap), n_fills=int(s["n_fills"]), n_rejected=int(s["n_rejected"]), n_engine_unfilled=int(s["n_engine_unfilled"]), n_liq=int(s["n_liq"]), funding_missed=int(s["funding_missed"]),
                recon_ok=bool(rc["ok"]), recon_diff=float(rc["diff"]), unmapped_target_share=float(unmapped), ideal_gross_mean=float(np.abs(tgt).mean()), achieved_gross_mean=float(np.abs(ach).mean()))


def run_one(name, out, data, rules, fee, slip, E, AF, ev, report, cap=CAP):
    """out = {sym: DataFrame[target, stop]} (cap=500 kitabı). Kurallı koşu (MEXC sözleşme birimi, min_notional=0) ve aynı hedeflerle ince-adım referansı (yuvarlamasız)."""
    syms = [s for s in out if s in rules]
    gross = {s: float(out[s].target.abs().mean()) for s in out}
    unmapped = sum(v for s, v in gross.items() if s not in rules) / max(sum(gross.values()), 1e-12)
    sp = replace(E.spec(fee, slip, cap=cap), min_notional=0.0)
    d = AF.contract_view({s: data[s] for s in syms}, rules)
    res, win, _ = ev.run_book({s: out[s] for s in syms}, d, sp, *E.utc(E.MAIN))
    rc = report.reconcile(win, res, sp)
    dn = report.book_pnl(win, res, sp).resample("1D").sum()
    ref_d = {s: dict(data[s], step=format(Decimal(10) ** (math.floor(math.log10(0.25 * cap / data[s]["kl"].close.max())) - 3), "f")) for s in syms}
    rres, rwin, _ = ev.run_book({s: out[s] for s in syms}, ref_d, sp, *E.utc(E.MAIN))
    rdn = report.book_pnl(rwin, rres, sp).resample("1D").sum()
    sh = lambda x: float((x / cap).mean() / (x / cap).std(ddof=1) * math.sqrt(365))  # noqa: E731
    res["sharpe"], rres["sharpe"] = sh(dn), sh(rdn)
    m = metrics(res, rres, res["intents"], unmapped, rc, cap)
    sym_tab = res["intents"].assign(abs_gap=lambda x: x.gap_notional.abs(), abs_tgt=lambda x: x.target_notional.abs()).groupby("sym").agg(n=("ts", "size"), mean_abs_target=("abs_tgt", "mean"), mean_abs_gap=("abs_gap", "mean"), blocked=("status", lambda x: int(x.isin(["blocked_minimum", "noop_lot"]).sum())))
    return dict(system=name, fee_rt=fee, slip_rt=slip, symbols_traded=syms, symbols_unmapped=sorted(set(out) - set(rules)), metrics=m, verdict=verdict(m), per_symbol=sym_tab.reset_index().to_dict("records")), res


def stage_replay(out_dir: str, system: str, scen: str):
    """Tek (sistem, ücret senaryosu) koşusu; her biri ayrı konteynerde (modal run --detach), çıktı <out>/<system>__<scen>.json."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import audit_fix as AF  # noqa: E402
    import ensemble as E  # noqa: E402
    import signal_diag as sd  # noqa: E402
    import signal_phase2 as P2  # noqa: E402

    from kepler import ensemble as en  # noqa: E402
    from kepler import evaluate as ev  # noqa: E402
    from kepler import report  # noqa: E402
    t0 = time.time()
    doc = json.loads(RULES.read_text())
    if system == "EV1":
        kls = AF.load_all(CAP)  # EV1 evreni: 9 sembol, pencere E.MAIN (mühürlü dönem yüklenmez)
        out, data = en.make_book(CAP, AF.params())(kls), E.data_of(E.EXT)
    else:
        mem = sd.members(20)
        syms = sorted(mem.sym.unique())
        AF.load_dynamic(syms, cap=CAP)
        syms = [s for s in syms if s in E.D]
        kls = {s: E.D[s]["kl"] for s in syms}
        out, data = P2.make_book(en.Params(names=("carry_xs",), weights=(1.0,)), mem, False, CAP)(kls), E.data_of(syms)
    fee, slip = SCENARIOS[scen]
    r, res = run_one(system, out, data, doc["symbols"], fee, slip, E, AF, ev, report)
    from kepler import receipt
    used = ev.book_window(out, data, *E.utc(E.MAIN))
    r["receipt"] = receipt.make(dict(system=system, scenario=scen, capital=CAP, rules=doc, window=E.MAIN), used, cut=E.utc(E.MAIN), extra_files=[__file__])
    r = dict(r, scenario=scen, rules_fetched_utc=doc["fetched_utc"], rules_source=doc["source"], window=E.MAIN, capital=CAP, seconds=time.time() - t0)
    o = Path(out_dir)
    o.mkdir(parents=True, exist_ok=True)
    (o / f"{system}__{scen}.json").write_text(json.dumps(r, indent=1, default=str, allow_nan=False))
    print(system, scen, r["verdict"]["overall"], r["verdict"]["failed"], f"{r['seconds']:.0f}s", json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in r["metrics"].items() if k in ("blocked_share", "net", "net_ref", "sharpe", "sharpe_ref", "unmapped_target_share", "dev_median")}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["rules", "replay"])
    ap.add_argument("--out", default="/data/account500")
    ap.add_argument("--system", choices=["EV1", "carry_xs"])
    ap.add_argument("--scenario", choices=list(SCENARIOS))
    a = ap.parse_args()
    if a.stage == "rules":
        d = fetch_rules()
        print(d["fetched_utc"], d["n_usdt"], "USDT sözleşmesi")
    else:
        stage_replay(a.out, a.system, a.scenario)
