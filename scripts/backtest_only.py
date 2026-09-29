#!/usr/bin/env python
"""Kepler train-free modern backtest (default path).

Train YOK: model, smoke run'undaki donuk params.pkl'dan yüklenir.
Bu script sadece predict + backtest + metrik üretir.
M0 arşivi (scripts/smoke_qlib.sh) salt-okunur kalır; yeni işler buradan yürür.

Kullanım:
    ./scripts/backtest_only.sh [CONFIG] [MODEL_PKL] [OUT_DIR]
"""

import argparse
import os
import pickle
import sys

import pandas as pd
import yaml

import qlib
from qlib.contrib.eva.alpha import calc_ic
from qlib.contrib.evaluate import risk_analysis
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP
from qlib.backtest import backtest as normal_backtest


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    ap = argparse.ArgumentParser(description="Kepler train-free modern backtest")
    ap.add_argument("--config", default="configs/backtest_modern.yaml")
    ap.add_argument(
        "--model",
        default="mlruns/461983874136587276/0414105956094a979bdd0f1a8a008066/artifacts/params.pkl",
        help="Donuk model (smoke run params.pkl). Refit yapılmaz.",
    )
    ap.add_argument("--out", default="reports/backtest_modern")
    args = ap.parse_args()

    if not os.path.exists(args.model):
        sys.exit(f"Donuk model bulunamadı: {args.model}\nÖnce ./scripts/smoke_qlib.sh koşmalı.")

    cfg = load_yaml(args.config)

    # 1. Qlib init (sadece data provider)
    init_cfg = cfg["qlib_init"]
    qlib.init(
        provider_uri=os.path.expanduser(init_cfg["provider_uri"]),
        region=init_cfg.get("region", "cn"),
    )

    # 2. Dataset: AYNI handler + AYNI fit penceresi, sadece test modern
    dataset_cfg = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": dict(cfg["data_handler_config"]),
            },
            "segments": dict(cfg["segments"]),
        },
    }
    from qlib.utils import init_instance_by_config

    dataset = init_instance_by_config(dataset_cfg, accept_types=DatasetH)

    # 3. Donuk model yükle — fit YOK
    with open(args.model, "rb") as f:
        model = pickle.load(f)
    if getattr(model, "model", None) is None:
        sys.exit("Model dosyası eğitilmiş ağırlık içermiyor (model.model is None).")

    # 4. Predict (test segmenti)
    pred = model.predict(dataset, segment="test")
    if isinstance(pred, pd.Series):
        pred = pred.to_frame("score")

    # 5. Backtest (strategy + executor, train yok)
    strategy_cfg = dict(cfg["strategy"])
    strategy_cfg["kwargs"] = dict(strategy_cfg["kwargs"])
    strategy_cfg["kwargs"]["signal"] = pred
    executor_cfg = cfg["executor"]
    bt_cfg = dict(cfg["backtest"])

    portfolio_metric_dict, _ = normal_backtest(
        executor=executor_cfg, strategy=strategy_cfg, **bt_cfg
    )
    freq = "1day" if "1day" in portfolio_metric_dict else next(iter(portfolio_metric_dict))
    report_normal, _ = portfolio_metric_dict[freq]

    # 6. Metrikler: portföy riski + sinyal IC
    excess_nc = report_normal["return"] - report_normal["bench"]
    excess_wc = report_normal["return"] - report_normal["bench"] - report_normal["cost"]
    port_frames = {
        "excess_return_without_cost": risk_analysis(excess_nc, freq=freq),
        "excess_return_with_cost": risk_analysis(excess_wc, freq=freq),
    }
    port = {k: df["risk"].to_dict() for k, df in port_frames.items()}

    try:
        raw_label = dataset.prepare("test", col_set="label", data_key=DataHandlerLP.DK_R)
    except TypeError:
        raw_label = dataset.prepare("test", col_set="label")
    ic, ric = calc_ic(pred.iloc[:, 0], raw_label.iloc[:, 0])
    sig = {
        "IC": float(ic.mean()),
        "ICIR": float(ic.mean() / ic.std()),
        "Rank IC": float(ric.mean()),
        "Rank ICIR": float(ric.mean() / ric.std()),
    }

    metrics = {
        "window": {"start": str(bt_cfg["start_time"]), "end": str(bt_cfg["end_time"])},
        "freq": freq,
        "n_bars": int(len(report_normal)),
        "model": args.model,
        "refit": False,
        "signal": sig,
        "portfolio": {k: {m: float(v) for m, v in d.items()} for k, d in port.items()},    }

    os.makedirs(args.out, exist_ok=True)
    pred.to_pickle(os.path.join(args.out, "pred_modern.pkl"))
    report_normal.to_pickle(os.path.join(args.out, f"report_normal_{freq}.pkl"))
    pd.concat(port_frames).to_pickle(os.path.join(args.out, f"port_analysis_{freq}.pkl"))
    with open(os.path.join(args.out, "metrics.yaml"), "w") as f:
        yaml.safe_dump(metrics, f, sort_keys=False)

    w = metrics["portfolio"]["excess_return_with_cost"]
    print(f"[{freq} {metrics['window']['start']} -> {metrics['window']['end']}] n={metrics['n_bars']} refit=False")
    print(f"IC={sig['IC']:.4f} (ICIR {sig['ICIR']:.4f}) | Rank IC={sig['Rank IC']:.4f} (ICIR {sig['Rank ICIR']:.4f})")
    print(f"with_cost: ann={w['annualized_return']:.6f} IR={w['information_ratio']:.6f} DD={w['max_drawdown']:.6f}")
    print(f"yazdı: {args.out}/metrics.yaml")


if __name__ == "__main__":
    main()
