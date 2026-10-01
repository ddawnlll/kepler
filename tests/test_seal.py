import io
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from tools import open_holdout, seal_holdout


def keypair():
    k = rsa.generate_private_key(65537, 3072)
    priv = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    pub = k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, pub


@pytest.fixture
def synth(tmp_path):
    d = tmp_path / "synthetic_holdout"
    (d / "klines").mkdir(parents=True)
    (d / "klines" / "SYNTH.parquet").write_bytes(bytes(range(256)) * 400)
    (d / "note.txt").write_text("sentetik mühür verisi")
    return d


def test_roundtrip_bit_exact(synth, tmp_path):
    priv, pub = keypair()
    blob = seal_holdout.seal(synth, pub)
    assert synth.name.encode() not in blob and b"sentetik" not in blob  # düz metin sızmıyor
    out = tmp_path / "opened"
    with tarfile.open(fileobj=io.BytesIO(open_holdout.unseal(blob, priv))) as t:
        t.extractall(out, filter="data")
    for f in synth.rglob("*"):
        if f.is_file():
            assert (out / f.relative_to(synth)).read_bytes() == f.read_bytes()


def test_wrong_private_key_cannot_open(synth):
    _, pub = keypair()
    other_priv, _ = keypair()
    with pytest.raises(ValueError):
        open_holdout.unseal(seal_holdout.seal(synth, pub), other_priv)


def test_tampered_ciphertext_rejected(synth):
    priv, pub = keypair()
    blob = bytearray(seal_holdout.seal(synth, pub))
    blob[-5] ^= 1
    with pytest.raises(InvalidTag):
        open_holdout.unseal(bytes(blob), priv)


def test_weak_rsa_key_rejected(synth):
    k = rsa.generate_private_key(65537, 2048)
    pub = k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    with pytest.raises(ValueError, match="3072"):
        seal_holdout.seal(synth, pub)


def test_seal_tool_has_no_private_key_path():
    src = Path(seal_holdout.__file__).read_text()
    assert "load_pem_private_key" not in src and "--privkey" not in src


def test_cli_end_to_end(synth, tmp_path):
    priv, pub = keypair()
    (tmp_path / "pub.pem").write_bytes(pub)
    (tmp_path / "priv.pem").write_bytes(priv)
    root = Path(seal_holdout.__file__).parent.parent
    run = lambda *a: subprocess.run([sys.executable, *a], cwd=root, check=True, capture_output=True)
    run("tools/seal_holdout.py", "--data", str(synth), "--pubkey", str(tmp_path / "pub.pem"), "--out", str(tmp_path / "h.sealed"))
    run("tools/open_holdout.py", "--sealed", str(tmp_path / "h.sealed"), "--privkey", str(tmp_path / "priv.pem"), "--out", str(tmp_path / "o"))
    assert (tmp_path / "o" / "note.txt").read_text() == "sentetik mühür verisi"
