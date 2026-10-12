"""#10: funding settlement düzeltmesinin mevcut geliştirme kartlarındaki risk/PnL etkisi (yalnız ölçüm; strateji değişmez; mühürlü dönem yok).
  modal run --detach modal_app.py --cmd "python scripts/funding_impact.py --cap 1000 --out /data/funding_impact"
EV1 (ev1_plus_new, 9 sembol, fee 10 + slip 2) 'unrounded' koşusu YENİ hakemle yeniden koşulur ve saklı eski-hakem çıktısıyla (reports/trade_audit_data/fix/mexc/mexc_runs.json) karşılaştırılır:
net, funding, fill sayısı, likidasyon. Beklenti (önceden yazılı): funding'in marja yansıması yalnız marj/likidasyon yolunu etkiler; likidasyon yoksa net ve funding aynı kalır."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
STORED = Path(__file__).resolve().parent.parent / "reports" / "trade_audit_data" / "fix" / "mexc" / "mexc_runs.json"


def main(cap: float, out: str):
    import audit_fix as AF  # noqa: E402
    import ensemble as E  # noqa: E402
    kls = AF.load_all()
    r = AF.run_rules(cap, "unrounded", AF.params(), kls, dict(E.D))
    s = r["summary"]
    old = next(x for x in json.loads(STORED.read_text())["runs"] if x["cap"] == cap and x["mode"] == "unrounded")
    keys = ("net_pnl", "funding", "n_fills", "n_liq", "liq_fee", "fee", "slippage")
    doc = dict(cap=cap, new={k: float(s[k]) for k in keys}, old={k: float(old[k]) for k in keys}, sharpe_new=r["sharpe_fixed"], sharpe_old=float(old["sharpe_fixed"]))
    doc["delta"] = {k: doc["new"][k] - doc["old"][k] for k in keys}
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / f"cap{int(cap)}.json").write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=float, required=True)
    ap.add_argument("--out", default="/data/funding_impact")
    a = ap.parse_args()
    main(a.cap, a.out)
