"""Trusted diff gate plus human-only, compare-and-swap main update. No agent code runs here."""
import fnmatch
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

REPO = "/srv/kepler.git"


def git(*args):
    return subprocess.check_output(["/usr/bin/git", "--git-dir", REPO, *args],
                                   env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
                                        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})


def protected_patterns():
    # Source is the installed trusted tree, NEVER the candidate's hook module.
    source = Path(__file__).resolve().parents[1] / ".claude/hooks/guard.py"
    spec = importlib.util.spec_from_file_location("installed_guard", source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CORE + mod.NEVER_BY_AGENT + mod.ASK + ["pyproject.toml", "uv.lock", ".github/*", "factory/*"]


def check(commit, base):
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[0-9a-f]{40}", base):
        raise ValueError("tam commit SHA gerekli")
    if git("merge-base", commit, base).decode().strip() != base:
        raise ValueError("aday güncel main üzerinden gelmeli; önce rebase gerekli")
    tracked_tests = set(git("ls-tree", "-r", "--name-only", base, "tests").decode().splitlines())
    patterns = protected_patterns()
    raw = git("diff", "--raw", "-z", "--no-renames", base, commit).split(b"\0")
    changed = []
    for i in range(0, len(raw) - 1, 2):
        header = raw[i].decode()
        path = raw[i + 1].decode("utf-8", "strict")
        modes = header.split()[:2]
        if any(m in {":120000", "120000", ":160000", "160000"} for m in modes):
            raise PermissionError("symlink/submodule değişikliği reddedildi")
        if path in tracked_tests or any(fnmatch.fnmatch(path, p) for p in patterns):
            raise PermissionError(f"korumalı yol: {path}")
        if not (path.startswith("kepler/experts/") or path.startswith("scripts/") or path.startswith("tests/test_") or path.startswith("reports/")):
            raise PermissionError(f"ajan yazma alanı dışında: {path}")
        if path.endswith("_protocol.md"):
            result = path.removesuffix("_protocol.md") + ".md"
            if git("ls-tree", "--name-only", base, result).strip():
                raise PermissionError("sonuçlanmış ön kayıt değişmez")
        changed.append(path)
    if not changed:
        raise ValueError("boş değişiklik")
    return changed


def merge(con, identity, policy, uid):
    from factory import store
    job = con.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
    if not job or job["state"] != "done" or job["exit_code"] != 0:
        raise PermissionError("başarılı sandbox kontrolü gerekli")
    payload = json.loads(job["payload"])
    if payload["kind"] != "check" or payload.get("policy") != policy:
        raise PermissionError("güncel politika ile tüm kontroller gerekli")
    base = git("rev-parse", "refs/heads/main").decode().strip()
    if base != payload["base"]:
        raise PermissionError("main değişti; tekrar kontrol gerekli")
    approval = con.execute("SELECT value FROM meta WHERE key=?", ("review:" + identity,)).fetchone()
    expected = {"commit": payload["commit"], "base": base, "uid": uid, "policy": hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()}
    if not approval or json.loads(approval[0]) != expected:
        raise PermissionError("aynı diff/main/politika için insanın ayrı review çağrısı gerekli")
    git("update-ref", "refs/heads/main", payload["commit"], base)
    store.event(con, "merged", {"id": identity, "commit": payload["commit"], "uid": uid})
    store.notify(con, "merged:" + identity, f"İnsan onayıyla main güncellendi: {payload['commit']}")
    return {"commit": payload["commit"]}


def review(con, identity, policy, uid):
    job = con.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
    if not job or job["state"] != "done" or job["exit_code"] != 0:
        raise PermissionError("başarılı sandbox kontrolü gerekli")
    payload = json.loads(job["payload"])
    if payload.get("kind") != "check" or payload.get("policy") != policy:
        raise PermissionError("güncel politika ve değişiklik kontrolü gerekli")
    base = git("rev-parse", "refs/heads/main").decode().strip()
    if base != payload["base"]:
        raise PermissionError("main değişti; kontrolü tekrar çalıştır")
    changed = check(payload["commit"], base)
    patch = subprocess.check_output(["/usr/bin/git", "--git-dir", REPO, "-c", "core.pager=cat", "-c", "core.quotePath=true",
                                     "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--binary", base, payload["commit"]],
                                    env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
    if len(patch) > 512 * 1024:
        raise ValueError("diff 512 KiB sınırını aşıyor; insan terminalinde parça parça incelenmeli")
    text = patch.decode("utf-8", "replace")
    secret = re.compile(r"(?i)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]?[^\s'\"]{20,})")
    if secret.search(text):
        raise PermissionError("gizli bilgi sezgisel taramada bulundu; insan güvenlik incelemesi gerekli")
    policy_hash = hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()
    expected = {"commit": payload["commit"], "base": base, "uid": uid, "policy": policy_hash}
    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", ("review:" + identity, json.dumps(expected, sort_keys=True)))
    return {"id": identity, "base": base, "commit": payload["commit"], "files": changed, "diff": text,
            "review_key": hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest(),
            "notice": "Bu insan diff incelemesidir; kontrol komutları bu oturumda çalıştırılmadı. Review yalnız aynı kullanıcı, main ve politika için geçerlidir."}
