"""İnsan onayı anahtarı: yalnızca ortam değişkeninden okunur (repoda, dosyada, kuyrukta ve sohbette tutulmaz).
Anahtar yoksa imza üretilemez ve doğrulanamaz: onay ve durdurmanın kaldırılması reddedilir."""
import hashlib
import hmac
import json
import os

KEY_ENV = "KEPLER_APPROVAL_KEY"


def key() -> bytes:
    k = os.environ.get(KEY_ENV, "")
    if len(k) < 32:
        raise PermissionError(f"{KEY_ENV} (en az 32 karakter) ortamda yok: onay/kaldırma yapılamaz")
    return k.encode()


def _mac(row: dict) -> str:
    body = json.dumps({k: v for k, v in row.items() if k != "sig"}, sort_keys=True, ensure_ascii=False)
    return hmac.new(key(), body.encode(), hashlib.sha256).hexdigest()


def sign(row: dict) -> str:
    return _mac(row)


def verify(row: dict) -> bool:
    try:
        return hmac.compare_digest(str(row.get("sig", "")), _mac(row))
    except PermissionError:
        return False
