import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import null_merge as NM  # noqa: E402


def U(i):
    return 0.05 + i / 1000


def shard(d, lo, hi, **over):
    part = {str(i): dict(net=float(i), u=U(i)) for i in range(lo, hi)}
    part.update(over)
    (Path(d) / f"null_{lo}_{hi}.json").write_text(json.dumps(part))


def full(d, b=10, chunk=4):
    for lo, hi in NM.spans(b, chunk):
        shard(d, lo, hi)


def test_worker_exit_code_propagates_despite_traceback_text():
    py = sys.executable
    assert NM.run_worker([py, "-c", "import sys; print('Traceback: synthetic failure'); sys.exit(23)"]) == 23  # grep'li pipeline bunu 0 yapıyordu
    assert NM.run_worker([py, "-c", "print('Error: only a log line')"]) == 0  # farklı log başarısızlık sayılmaz


def test_merge_ok_and_expected_range(tmp_path):
    full(tmp_path)
    m = NM.merge(tmp_path, 10, 4, expect_u=U)
    assert m["n"] == 10 and list(m["results"]) == [str(i) for i in range(10)]


def test_missing_shard_fails(tmp_path):
    full(tmp_path)
    (tmp_path / "null_4_8.json").unlink()
    with pytest.raises(NM.MergeError, match="eksik shard"):
        NM.merge(tmp_path, 10, 4)


def test_truncated_output_fails(tmp_path):
    full(tmp_path)
    p = tmp_path / "null_0_4.json"
    p.write_text(p.read_text()[:-5])
    with pytest.raises(NM.MergeError, match="bozuk"):
        NM.merge(tmp_path, 10, 4)


def test_missing_seed_inside_shard_fails(tmp_path):
    full(tmp_path)
    p = tmp_path / "null_0_4.json"
    d = json.loads(p.read_text()); d.pop("2"); p.write_text(json.dumps(d))
    with pytest.raises(NM.MergeError, match="tohum kümesi"):
        NM.merge(tmp_path, 10, 4)


def test_wrong_u_and_schema_and_stray(tmp_path):
    full(tmp_path)
    with pytest.raises(NM.MergeError, match="u tohumla"):
        NM.merge(tmp_path, 10, 4, expect_u=lambda i: 0.5)
    shard(tmp_path, 0, 4, **{"1": dict(net=1.0)})
    with pytest.raises(NM.MergeError, match="şema"):
        NM.merge(tmp_path, 10, 4)
    full(tmp_path); shard(tmp_path, 8, 12)
    with pytest.raises(NM.MergeError, match="beklenmeyen"):
        NM.merge(tmp_path, 10, 4)


def test_retry_idempotent_and_overlap_is_error(tmp_path):
    full(tmp_path)
    a = NM.merge(tmp_path, 10, 4)["content_sha"]
    shard(tmp_path, 0, 4)  # aynı içerikle retry
    assert NM.merge(tmp_path, 10, 4)["content_sha"] == a
    shard(tmp_path, 2, 6)  # çakışan aralık (çelişkili olabilir): sessizce seçilmez
    with pytest.raises(NM.MergeError, match="beklenmeyen"):
        NM.merge(tmp_path, 10, 4)


def test_merge_key_format_for_carryxs_shards(tmp_path):
    """carryxs_card.py çıktısı "null_<i>" anahtarlıdır (kayıt: summary + u)."""
    for lo, hi in NM.spans(6, 3):
        (tmp_path / f"null_{lo}_{hi}.json").write_text(json.dumps({f"null_{i}": dict(summary=dict(net_pnl=1.0), u=U(i)) for i in range(lo, hi)}))
    m = NM.merge(tmp_path, 6, 3, expect_u=U, key="null_{}")
    assert list(m["results"]) == [f"null_{i}" for i in range(6)]
    with pytest.raises(NM.MergeError, match="tohum kümesi"):
        NM.merge(tmp_path, 6, 3)  # yanlış anahtar biçimi sessizce kabul edilmez


def test_worker_identity_and_run_manifest_must_match(tmp_path, monkeypatch):
    full(tmp_path)
    manifest = dict(run_id="fresh", script="ensemble", b=10)
    monkeypatch.setenv("KEPLER_NULL_MANIFEST", json.dumps(manifest))
    for lo, hi in NM.spans(10, 4):
        NM.publish_identity(tmp_path / f"null_{lo}_{hi}.json", "a" * 64)
    assert NM.merge(tmp_path, 10, 4, run_manifest=manifest)["economic_id"] == "a" * 64
    with pytest.raises(NM.MergeError, match="run manifest mismatch"):
        NM.merge(tmp_path, 10, 4, run_manifest=dict(manifest, run_id="stale"))
    NM.publish_identity(tmp_path / "null_4_8.json", "b" * 64)
    with pytest.raises(NM.MergeError, match="identity mismatch"):
        NM.merge(tmp_path, 10, 4, run_manifest=manifest)
    (tmp_path / "null_4_8.manifest.json").unlink()
    with pytest.raises(NM.MergeError, match="missing"):
        NM.merge(tmp_path, 10, 4, run_manifest=manifest)


@pytest.mark.parametrize("bad", [float("inf"), float("nan")])
def test_nested_nonfinite_metrics_fail(tmp_path, bad):
    full(tmp_path)
    shard(tmp_path, 0, 4, **{"1": dict(u=U(1), summary=dict(net_pnl=bad))})
    with pytest.raises(NM.MergeError, match="NaN/Inf"):
        NM.merge(tmp_path, 10, 4)


def test_production_economic_metrics_cannot_be_missing_or_invalid():
    valid = dict(net_pnl=1., funding=-.01, n_fills=3., n_rejected=0, n_engine_unfilled=0, funding_missed=0)
    NM.validate_economics(valid)
    for bad in (dict(valid, n_rejected=1), dict(valid, n_engine_unfilled=1), dict(valid, funding_missed=1), dict(valid, net_pnl="1"), dict(valid, n_fills=-1)):
        with pytest.raises(NM.MergeError):
            NM.validate_economics(bad)
