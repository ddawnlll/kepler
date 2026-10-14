"""Acil durdurma. `engage` yeni işi kapatır (herkes, ajan dahil: durdurmak güvenli yöndedir); `--kill` çalışanları da sonlandırır.
`release` yalnızca insan: KEPLER_APPROVAL_KEY ile imzalı kayıt yazar ve durdurmayı kaldırır. Ajan imzasız kayıtla kaldıramaz.

  python -m factory.halt engage --by <ad> --reason "<neden>" [--kill]
  python -m factory.halt release --by <ad>
  python -m factory.halt status
"""
import argparse
import json
import sys
import time

from factory import auth, enqueue, runner

LOG = enqueue.ROOT / "state" / "halt_log.jsonl"


def _log(row: dict):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def engage(by: str, reason: str, kill: bool = False) -> list[str]:
    enqueue.HALT.parent.mkdir(parents=True, exist_ok=True)
    enqueue.HALT.write_text(json.dumps(dict(by=by, reason=reason, ts=time.time())))
    killed = runner.kill_running() if kill else []
    _log(dict(action="engage", by=by, reason=reason, kill=kill, killed=killed, ts=time.time()))
    return killed


def release(by: str):
    row = dict(action="release", by=by, ts=time.time())
    row["sig"] = auth.sign(row)  # anahtar yoksa PermissionError: kaldırma yalnızca anahtar sahibinde
    _log(row)
    enqueue.HALT.unlink(missing_ok=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("engage")
    e.add_argument("--by", required=True)
    e.add_argument("--reason", required=True)
    e.add_argument("--kill", action="store_true")
    r = sub.add_parser("release")
    r.add_argument("--by", required=True)
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "engage":
        print("durduruldu; sonlandırılan:", engage(a.by, a.reason, a.kill) or "yok")
    elif a.cmd == "release":
        try:
            release(a.by)
        except PermissionError as e:
            print(e, file=sys.stderr)
            return 1
        print("durdurma kaldırıldı")
    else:
        print("DURDURULDU" if enqueue.halted() else "çalışıyor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
