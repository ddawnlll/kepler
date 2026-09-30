import hashlib
import io
import os
import zipfile

import pytest
import requests

from kepler import data

K = "data/futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2024-01.zip"


def make_zip(text="open_time,open\n1,2\n") -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("x.csv", text)
    return b.getvalue()


class FakeNet:
    """Sahte ağ: anahtar -> [ilk yanıt, sonraki yanıtlar]; .CHECKSUM her zaman doğru içeriğin hash'i."""

    def __init__(self, bodies):
        self.bodies, self.calls = list(bodies), 0

    def __call__(self, url, **kw):
        r = requests.Response()
        r.status_code = 200
        if url.endswith(".CHECKSUM"):
            r._content = (hashlib.sha256(make_zip()).hexdigest() + "  f.zip\n").encode()
        else:
            self.calls += 1
            r._content = self.bodies.pop(0) if len(self.bodies) > 1 else self.bodies[0]
        return r


def test_fetch_ok_and_idempotent(tmp_path, monkeypatch):
    net = FakeNet([make_zip()])
    monkeypatch.setattr(data, "_get", net)
    p = data.fetch(K, tmp_path)
    assert p.read_bytes() == make_zip() and net.calls == 1
    data.fetch(K, tmp_path)  # ikinci çağrı: doğrulanmış dosya var, yeniden indirmez
    assert net.calls == 1


def test_bad_checksum_rejected_and_redownloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(data.time, "sleep", lambda s: None)
    net = FakeNet([b"BOZUK", make_zip()])  # ilk indirme bozuk, ikinci doğru
    monkeypatch.setattr(data, "_get", net)
    p = data.fetch(K, tmp_path)
    assert p.read_bytes() == make_zip() and net.calls == 2
    assert not list(p.parent.glob("*.part"))  # bozuk içerik diske hiç yazılmadı


def test_always_bad_checksum_raises_and_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(data.time, "sleep", lambda s: None)
    monkeypatch.setattr(data, "_get", FakeNet([b"BOZUK"]))
    with pytest.raises(data.ChecksumError):
        data.fetch(K, tmp_path, retries=3)
    assert not (tmp_path / "raw" / K).exists()


def test_corrupt_local_file_is_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "_get", FakeNet([make_zip()]))
    dst = tmp_path / "raw" / K
    dst.parent.mkdir(parents=True)
    dst.write_bytes(b"yarim")
    assert data.fetch(K, tmp_path).read_bytes() == make_zip()


def test_sealed_period_is_never_fetched(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ağa çıkılmamalıydı")

    monkeypatch.setattr(data, "_get", boom)
    sealed = K.replace("2024-01", "2026-04")
    with pytest.raises(data.SealedError):
        data.fetch(sealed, tmp_path)
    assert data.key("klines", "BTCUSDT", "2026-04").endswith("2026-04.zip")


@pytest.mark.skipif(not os.getenv("KEPLER_NET"), reason="ağ testi: KEPLER_NET=1 (Modal)")
def test_real_small_end_to_end(tmp_path):
    """Gerçek arşiv: 1 sembol, 2 ay; klines + mark + funding; liste, indirme, sha256, okuma."""
    assert "BTCUSDT" in data.symbols()
    ms = data.months("klines", "BTCUSDT")
    assert ms[0] <= "2020-01" and ms[-1] == data.DEV_END  # mühürlü aylar listede yok
    for kind in ("klines", "markPriceKlines", "fundingRate"):
        p = data.fetch(data.key(kind, "BTCUSDT", "2024-01"), tmp_path)
        df = data.read_zip_csv(p)
        assert len(df) > 20
        assert (tmp_path / "raw" / (data.key(kind, "BTCUSDT", "2024-01") + ".sha256")).exists()
    assert set(df.columns) == {"calc_time", "funding_interval_hours", "last_funding_rate"}
    # mark ve klines aynı dosya adı, ayrı dizin
    assert data.key("klines", "BTCUSDT", "2024-01") != data.key("markPriceKlines", "BTCUSDT", "2024-01")
