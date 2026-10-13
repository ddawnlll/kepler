#!/usr/bin/env python3
"""Yazma sınırı + mimari kapı. Korumalı yol listesinin TEK kaynağı burası (ARCHITECTURE.md, AGENTS.md buna atıf yapar).
  guard.py pretool   Claude Code PreToolUse (stdin JSON; exit 2 = engelle, stderr ajana geri bildirim)
  guard.py stop      Claude Code Stop: tests/test_architecture.py geçmeden tur bitmez
  guard.py staged    .githooks/pre-commit: staged dosyalar + mimari test (Claude Code dışı ajanlar için de geçerli)
Kilit: kullanıcı oturumu `KEPLER_CORE_UNLOCK=1` ile açar (ajanın alt süreç ortamı hook'u etkilemez). Bu bir ajan sözleşmesidir, güvenlik sınırı değil:
git hook'u atlanabilir; gerçek sınır dal koruması + insan incelemesi (AGENTS.md)."""
import fnmatch
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE = [
    "kepler/referee.py", "kepler/referee_core.py", "kepler/receipt.py", "kepler/intents.py", "kepler/positioning.py", "kepler/audit.py", "kepler/evaluate.py", "kepler/ledger.py", "kepler/risk.py", "kepler/stats.py", "kepler/robust.py", "kepler/state.py",
    "kepler/tape.py", "kepler/data.py", "kepler/qc.py", "kepler/universe.py", "modal_app.py", "tools/*", "factory/*.py", "factory/policy.yaml", "factory/agents/*",
    "BACKTEST.md", "AGENTS.md", "CLAUDE.md", "MISSION.md", "docs/*", ".claude/*", ".githooks/*",
]
NEVER_BY_AGENT = ["ledger/*", "registry/*", "hypotheses.jsonl", "artifacts/*", "state/*"]  # yalnızca script'ler yazar
ASK = ["tests/test_architecture.py"]  # LAYERS satırı eklemek serbest, kuralı gevşetmek kullanıcı onayı
EXISTING_TESTS = "tests/*"  # mevcut (izlenen) testler korumalı; yeni test dosyası serbest


def _git_tracked(rel: str) -> bool:
    return subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True).returncode == 0


def _allowed_md() -> list[str]:
    spec = importlib.util.spec_from_file_location("test_architecture", ROOT / "tests" / "test_architecture.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.ALLOWED_MD


def classify(rel: str, is_new: bool) -> tuple[str, str]:
    """('allow'|'ask'|'deny', neden)."""
    match = lambda pats: any(fnmatch.fnmatch(rel, g) for g in pats)  # noqa: E731
    unlocked = os.environ.get("KEPLER_CORE_UNLOCK") == "1"
    if match(NEVER_BY_AGENT):
        return "deny", f"{rel}: defter/kayıt/durum dosyalarına ajan yazmaz (yalnızca script'ler: factory/enqueue.py, hakem)."
    if rel.startswith("reports/") and rel.endswith("_protocol.md") and (ROOT / (rel[: -len("_protocol.md")] + ".md")).exists():
        return "deny", f"{rel}: sonuçlanmış ön kayıt değişmez. Değişiklik = yeni ön kayıt + yeni deneme (MISSION kural 11)."
    if rel.endswith(".md") and is_new and not match(_allowed_md()):
        return "deny", f"{rel}: yeni .md açma. İlgili mevcut belgeye yaz (AGENTS.md 'nereye ne konur'); izin listesi tests/test_architecture.py ALLOWED_MD."
    if match(ASK):
        return "ask", f"{rel}: mimari kuralların tek kaynağı. Yeni modül için LAYERS satırı eklemek serbest; kural gevşetme/ALLOW büyütme kullanıcı onayı ister."
    protected = match(CORE) or (match([EXISTING_TESTS]) and not is_new)
    if protected and not unlocked:
        return "deny", f"{rel}: korumalı çekirdek (AGENTS.md). Gerçekten gerekiyorsa dur ve kullanıcıya sor; kullanıcı oturumu KEPLER_CORE_UNLOCK=1 ile açar."
    return "allow", ""


def _arch_test() -> tuple[bool, str]:
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_architecture.py")], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def pretool() -> int:
    ev = json.load(sys.stdin)
    ti = ev.get("tool_input", {})
    path = ti.get("file_path") or ti.get("notebook_path")
    if not path:
        return 0
    p = pathlib.Path(path)
    p = p if p.is_absolute() else pathlib.Path(ev.get("cwd", ROOT)) / p
    try:
        rel = p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return 0  # repo dışı
    verdict, why = classify(rel, is_new=not p.exists())
    if verdict == "deny":
        print(why, file=sys.stderr)
        return 2
    if verdict == "ask":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": why}}))
    return 0


def stop() -> int:
    try:
        if json.load(sys.stdin).get("stop_hook_active"):
            return 0  # döngü koruması
    except ValueError:
        pass
    ok, out = _arch_test()
    if not ok:
        print("Mimari test kırmızı; düzeltmeden bitirme:\n" + out, file=sys.stderr)
        return 2
    return 0


def staged() -> int:
    out = subprocess.run(["git", "diff", "--cached", "--name-status", "--no-renames"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    bad = []
    for line in out:
        st, rel = line.split("\t", 1)
        verdict, why = classify(rel, is_new=(st == "A"))
        if verdict == "deny" and st != "D":
            bad.append(why)
        elif verdict == "ask":
            print(f"uyarı: {why}", file=sys.stderr)
    ok, text = _arch_test()
    if not ok:
        bad.append("mimari test kırmızı:\n" + text)
    if bad:
        print("commit engellendi:\n- " + "\n- ".join(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit({"pretool": pretool, "stop": stop, "staged": staged}[sys.argv[1]]())
