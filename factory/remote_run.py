"""Trusted main-only Modal entry: unique output directory and durable completion receipt."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from kepler import ledger
from factory.entrypoints import RESEARCH_ENTRYPOINTS


def run(token, script, argv):
    if not re.fullmatch(r"[0-9a-f]{32}", token) or script not in RESEARCH_ENTRYPOINTS:
        raise ValueError("geçersiz koşu")
    spool = Path("/data/ledger-spool") / token
    if spool.exists():
        raise ValueError("aynı koşu kimliği tekrar yürütülemez; önce insan mutabakatı")
    spool.mkdir(parents=True)
    env = {**os.environ, "KEPLER_RUN_ID": token, "KEPLER_LEDGER_SPOOL": str(spool)}
    rc = subprocess.run([sys.executable, script, *argv, "--out", "/data/factory/" + token], env=env).returncode
    receipt = {"token": token, "exit_code": rc, "code_hash": ledger.code_hash(),
               "events": len(list(spool.glob("*/event.json")))}
    temp = spool / "receipt.pending"
    temp.write_text(json.dumps(receipt, allow_nan=False) + "\n")
    temp.replace(spool / "receipt.json")
    return rc


if __name__ == "__main__":
    args = json.loads(sys.argv[1])
    raise SystemExit(run(args["token"], args["script"], args["argv"]))
