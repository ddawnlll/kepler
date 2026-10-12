"""#19: parçalı (fan-out) koşu = seri referans (tohum bazında net, dolum, günlük PnL); başarısız worker ve retry davranışı."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

SC = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SC))
import null_merge as NM  # noqa: E402

FIX = str(SC / "null_parity_fixture.py")
B, CHUNK = 6, 2


def worker(out, lo, hi, *extra):
    return NM.run_worker([sys.executable, FIX, "--null-from", str(lo), "--null-to", str(hi), "--out", str(out), *extra])


def u_of(i):
    return float(np.random.default_rng([0, i]).uniform(0.05, 0.95))


@pytest.fixture(scope="module")
def serial(tmp_path_factory):
    d = tmp_path_factory.mktemp("serial")
    assert worker(d, 0, B) == 0
    return json.loads((d / f"null_0_{B}.json").read_text())


def test_sharded_equals_serial_per_seed(tmp_path, serial):
    for lo, hi in NM.spans(B, CHUNK):
        assert worker(tmp_path, lo, hi) == 0
    m = NM.merge(tmp_path, B, CHUNK, expect_u=u_of)
    assert m["n"] == B
    for i in range(B):
        a, b = serial[str(i)], m["results"][str(i)]
        assert a["net"] == b["net"] and a["n_fills"] == b["n_fills"] and a["daily"] == b["daily"] and a["u"] == b["u"], i  # birebir (aynı süreçsel hesap)
    assert len({serial[str(i)]["net"] for i in range(B)}) > 1  # fixture tohuma duyarlı: parity anlamlı


def test_failed_worker_fails_job_and_no_card(tmp_path):
    rc = worker(tmp_path, 0, CHUNK, "--fail-with", "23")
    assert rc == 23  # grep'li pipeline bunu 0 yapıyordu
    with pytest.raises(NM.MergeError, match="eksik shard"):
        NM.merge(tmp_path, B, CHUNK)  # başarısız shard başarı kartı üretemez


def test_retry_overwrites_same_shard_idempotently(tmp_path, serial):
    for lo, hi in NM.spans(B, CHUNK):
        assert worker(tmp_path, lo, hi) == 0
    a = NM.merge(tmp_path, B, CHUNK)["content_sha"]
    assert worker(tmp_path, 2, 4) == 0  # retry
    assert NM.merge(tmp_path, B, CHUNK)["content_sha"] == a
    p = tmp_path / "null_2_4.json"
    d = json.loads(p.read_text())
    d["2"]["net"] += 1.0  # çelişkili içerik: mevcut sözleşme tohum/şema kontrolünü geçer ama hash değişir -> sessizce aynı sayılmaz
    p.write_text(json.dumps(d))
    assert NM.merge(tmp_path, B, CHUNK)["content_sha"] != a
