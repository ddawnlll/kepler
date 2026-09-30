"""Mühürlü dosyayı açar. YALNIZCA kullanıcı çalıştırır (G3); özel anahtar yalnızca komut satırında verilir.

  python tools/open_holdout.py --sealed holdout.sealed --privkey private.pem --out DIR
"""
import argparse
import io
import struct
import tarfile
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"KEPLERSEAL1"


def unseal(blob: bytes, privkey_pem: bytes) -> bytes:
    if not blob.startswith(MAGIC):
        raise ValueError("mühürlü dosya değil")
    n = struct.unpack(">I", blob[len(MAGIC): len(MAGIC) + 4])[0]
    i = len(MAGIC) + 4
    priv = serialization.load_pem_private_key(privkey_pem, password=None)
    if not isinstance(priv, rsa.RSAPrivateKey):
        raise ValueError("RSA özel anahtarı bekleniyor")
    key = priv.decrypt(blob[i: i + n], padding.OAEP(padding.MGF1(hashes.SHA256()), hashes.SHA256(), None))
    return AESGCM(key).decrypt(blob[i + n: i + n + 12], blob[i + n + 12:], MAGIC)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sealed", type=Path, required=True)
    ap.add_argument("--privkey", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    tar = unseal(a.sealed.read_bytes(), a.privkey.read_bytes())
    a.out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(a.out, filter="data")
    print(f"{a.out} içine açıldı")
