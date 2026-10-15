"""Research is limited to an approved main commit, preregistered DEV protocol, fixed argv."""
import hashlib
import json
import re

from factory.merge_gate import git


def fingerprint(commit):
    files = git("ls-tree", "-r", "--name-only", commit).decode().splitlines()
    names = [n for n in files if n in {"pyproject.toml", "uv.lock"} or
             n.endswith(".py") and n.startswith(("kepler/", "scripts/", "experiments/"))]
    entries = [(name, hashlib.sha256(git("show", commit + ":" + name)).hexdigest()) for name in sorted(names)]
    return hashlib.sha256(json.dumps(entries, sort_keys=True, default=str).encode()).hexdigest()


def validate(payload, config):
    if set(payload) != {"kind", "commit", "script", "argv", "protocol", "protocol_commit", "protocol_sha", "data_hash", "period"} or payload["kind"] != "research":
        raise ValueError("araştırma istek şeması")
    if not config["research_enabled"]:
        raise PermissionError("araştırma provası tamamlanmadan research_enabled açılamaz")
    if payload["period"] != "DEV":
        raise PermissionError("yalnızca DEV dönemi araştırılabilir")
    commit = payload["commit"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("commit SHA")
    if commit != git("rev-parse", "refs/heads/main").decode().strip():
        raise PermissionError("araştırma yalnızca onaylanmış güncel main kodunda koşar")
    if payload["script"] not in config["research_scripts"]:
        raise PermissionError("izin verilmeyen araştırma betiği")
    protocol = payload["protocol"]
    if not isinstance(protocol, str) or not re.fullmatch(r"reports/[A-Za-z0-9_/-]+\.md", protocol) or ".." in protocol:
        raise ValueError("geçersiz ön kayıt yolu")
    if hashlib.sha256(git("show", commit + ":" + protocol)).hexdigest() != payload["protocol_sha"]:
        raise ValueError("ön kayıt hash uyuşmazlığı")
    prereg = payload["protocol_commit"]
    if not isinstance(prereg, str) or not re.fullmatch(r"[0-9a-f]{40}", prereg) or prereg == commit:
        raise ValueError("ön kayıt ayrı ve önceki commit'te olmalı")
    if git("merge-base", prereg, commit).decode().strip() != prereg:
        raise ValueError("ön kayıt commit'i koşudan önce gelmeli")
    if hashlib.sha256(git("show", prereg + ":" + protocol)).hexdigest() != payload["protocol_sha"]:
        raise ValueError("ön kayıt sonradan değiştirilmiş")
    if not re.fullmatch(r"[0-9a-f]{64}", payload["data_hash"]):
        raise ValueError("ön kayıtlı veri hash gerekli")
    argv = payload["argv"]
    if not isinstance(argv, list) or (not argv and payload["script"] != "experiments/erf01/atlas.py") or len(argv) > 24 or any(not isinstance(a, str) for a in argv):
        raise ValueError("geçersiz argv")
    # No --out/--root overrides, response files or free-form executable input.
    allowed = {"--stage", "--job", "--preset", "--expert", "--rot", "--b", "--null-from", "--null-to", "--only", "--syms", "--procs"}
    seen = set()
    for i in range(0, len(argv), 2):
        if i + 1 >= len(argv) or argv[i] not in allowed or argv[i] in seen or not re.fullmatch(r"[A-Za-z0-9_,.-]{1,128}", argv[i + 1]):
            raise ValueError("izin verilmeyen araştırma argümanı")
        seen.add(argv[i])
        if argv[i] in {"--b", "--null-from", "--null-to", "--procs"} and (not argv[i + 1].isdigit() or int(argv[i + 1]) > 1000):
            raise ValueError("sayısal araştırma sınırı")
    return {**payload, "code_hash": fingerprint(commit), "policy": config}
