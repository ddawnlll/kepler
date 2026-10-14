"""Birleştirme kapısı: `python -m factory.gate <taban_dal> [--tests]`.
Reddeder: (1) kilit kapalıyken korumalı yol değişmişse; (2) mimari test kırmızıysa; (3) --tests ile pytest kırmızıysa.
Kilit açıkken korumalı değişiklikler `insan incelemesi` olarak listelenir (çıkış kodu 0, birleştirme kararı insanda).
Sınır: test ajan kodunu ayrı kullanıcı/sandbox'ta koşmaz; bu kapı yalnızca kontrolü ve kararı toplar (docs/factory.md §5)."""
import argparse
import importlib.util
import subprocess
import sys

from factory import enqueue

ROOT = enqueue.ROOT


def _guard():
    spec = importlib.util.spec_from_file_location("kepler_guard_gate", ROOT / ".claude" / "hooks" / "guard.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def changed(base: str) -> list[tuple[str, str]]:
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", f"{base}...HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [tuple(line.split("\t", 1)) for line in out.splitlines() if line]


def check(base: str, tests: bool = False) -> tuple[list[str], list[str]]:
    """(sorunlar, insan_incelemesi). Sorun varsa birleştirme reddedilir."""
    g = _guard()
    problems, review = [], []
    for st, rel in changed(base):
        verdict, why = g.classify(rel, is_new=(st == "A"))
        if verdict == "deny":
            problems.append(why)
        elif verdict == "ask" or g._protected_path(rel):
            review.append(f"{st} {rel}" + (f" ({why})" if why else ""))
    ok, text = g._arch_test()
    if not ok:
        problems.append("mimari test kırmızı:\n" + text)
    if tests:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            problems.append("pytest kırmızı:\n" + r.stdout[-1500:])
    return problems, review


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("base")
    ap.add_argument("--tests", action="store_true")
    a = ap.parse_args(argv)
    problems, review = check(a.base, a.tests)
    for r in review:
        print(f"insan incelemesi: {r}")
    for p in problems:
        print(f"REDDEDİLDİ: {p}")
    print("KAPI: " + ("kırmızı" if problems else "yeşil"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
