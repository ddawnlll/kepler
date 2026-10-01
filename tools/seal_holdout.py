"""Mühürlü dönem verisini yalnızca GENEL anahtarla şifreler. Özel anahtar bu araçta hiç yoktur.

  python tools/seal_holdout.py --data DIR --pubkey public.pem --out holdout.sealed

Anahtar çifti kullanıcı makinesinde üretilir (özel anahtar ajanın ortamına/dosyasına girmez):
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out private.pem
  openssl pkey -in private.pem -pubout -out public.pem
Biçim: MAGIC | uint32 sarılı-anahtar uzunluğu | RSA-OAEP(SHA256) ile sarılmış AES-256 anahtarı | nonce(12) | AES-GCM(tar).
"""
import argparse
import hashlib
import io
import os
import struct
import tarfile
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"KEPLERSEAL1"


def seal(data_dir: Path, pubkey_pem: bytes) -> bytes:
    pub = serialization.load_pem_public_key(pubkey_pem)
    if not isinstance(pub, rsa.RSAPublicKey):
        raise ValueError("RSA genel anahtarı bekleniyor")
    if pub.key_size < 3072:
        raise ValueError("RSA anahtarı en az 3072 bit olmalı")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        tar.add(data_dir, arcname=".")
    key, nonce = AESGCM.generate_key(256), os.urandom(12)
    wrapped = pub.encrypt(key, padding.OAEP(padding.MGF1(hashes.SHA256()), hashes.SHA256(), None))
    return MAGIC + struct.pack(">I", len(wrapped)) + wrapped + nonce + AESGCM(key).encrypt(nonce, buf.getvalue(), MAGIC)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--pubkey", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    blob = seal(a.data, a.pubkey.read_bytes())
    a.out.write_bytes(blob)
    print(f"{a.out} yazıldı; sha256={hashlib.sha256(blob).hexdigest()}")
