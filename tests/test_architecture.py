"""Mimari kuralları (ARCHITECTURE.md): katmanlar, yasak import'lar, boyut bütçesi, belge izin listesi. TEK KAYNAK burası; ARCHITECTURE.md bunu özetler, tersi değil.
Yalnızca stdlib: Modal'siz, pytest'siz koşar (`python3 tests/test_architecture.py`); Stop hook'u ve .githooks/pre-commit bunu çağırır.
Yeni modül ekleyince LAYERS'a yaz (test bunu zorlar). İstisna eklemek yerine sorunu çöz: ALLOW listesi yalnızca küçülür (bayatlarsa test kırılır)."""
import ast
import fnmatch
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "kepler"

# Alt katman üst katmanı import edemez (aynı katman serbest). Düşükten yükseğe.
LAYERS = [
    ("veri", ["data", "qc", "tape", "universe"]),
    ("temel", ["ledger", "report", "intents", "funding", "receipt", "stats", "capacity", "stress", "nested", "signals"]),
    ("risk", ["risk", "portfolio"]),
    ("durum", ["market_state", "state", "indicators"]),
    ("uzman", ["experts", "turtle"]),  # experts = kepler/experts/* (tek grup)
    ("kompozisyon", ["ensemble"]),
    ("hakem", ["referee", "audit", "robust", "screen", "evaluate"]),
]
RANK = {m: i for i, (_, mods) in enumerate(LAYERS) for m in mods}
LAYER_OF = {m: name for name, mods in LAYERS for m in mods}

# Uzman yalnızca TAHMİN verir: boyut/kaldıraç risk katmanında, sonuç yazımı hakem hattında.
EXPERT_FORBIDDEN = {"risk", "portfolio", "ledger", "referee", "audit", "robust", "screen", "evaluate", "ensemble"}
# Hakem, sinyalden habersiz kalır (sonucu etkileyecek hiçbir üretici bilgisi görmez).
JUDGE = {"referee", "audit", "ledger", "stats", "robust"}
JUDGE_FORBIDDEN = {"experts", "ensemble", "signals", "turtle", "indicators", "market_state", "state", "portfolio", "risk"}

# Bilinen ihlaller (importer, imported): YALNIZCA azalır. Bayat girdi testi kırar.
ALLOW = {
    ("experts", "ledger"): "zone_fade.py defter yazıyor (K1 rotate_book/yönetici dahil); WP1'de (experts/_interface) yönetici ayrılınca kalkar",
}

MAX_FILE_LINES = 300
MAX_TOTAL_LINES = 3000

# Git'te izlenen .md dosyaları için izin listesi (doc hell kapısı). Yeni belge türü açmak = bu listeyi bilerek değiştirmek.
ALLOWED_MD = [
    "AGENTS.md", "CLAUDE.md", "MISSION.md", "ARCHITECTURE.md", "BACKTEST.md", "TASKS.md", "README.md", "docs/factory.md",
    "reports/*", "factory/*", "books_text/*", "data_manifest/*", "state/*", ".pi/*", "tests/*",
    ".claude/rules/*", ".claude/skills/*", ".claude/agents/*",
]


def _group(mod: str) -> str | None:
    p = mod.split(".")
    return p[1] if p[0] == "kepler" and len(p) > 1 else None


def _modules() -> dict[str, pathlib.Path]:
    out = {}
    for f in sorted(PKG.rglob("*.py")):
        g = f.relative_to(PKG).parts[0].removesuffix(".py")
        if g != "__init__":
            out.setdefault(g, f)  # experts/* tek grup
    return out


def _edges() -> dict[tuple[str, str], list[str]]:
    """(importer grubu, imported grubu) -> ['dosya:satır', ...]; grup içi import sayılmaz."""
    e: dict[tuple[str, str], list[str]] = {}
    for f in sorted(PKG.rglob("*.py")):
        me = f.relative_to(PKG).parts[0].removesuffix(".py")
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(n, ast.ImportFrom) and n.module:
                mods = [n.module] if n.module != "kepler" else [f"kepler.{a.name}" for a in n.names]
            elif isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            for m in mods:
                g = _group(m)
                if g and g != me:
                    e.setdefault((me, g), []).append(f"{f.relative_to(ROOT)}:{n.lineno}")
    return e


def test_every_module_has_a_layer():
    missing = sorted(set(_modules()) - set(RANK))
    assert not missing, f"katmanı olmayan modül(ler): {missing}. tests/test_architecture.py LAYERS'a ekle (ve ARCHITECTURE.md katman özetini güncelle)."
    assert not (set(RANK) - set(_modules())), f"LAYERS'ta olup dosyası olmayan: {sorted(set(RANK) - set(_modules()))}"


def test_no_upward_imports():
    bad = {k: v for k, v in _edges().items() if k[1] in RANK and k[0] in RANK and RANK[k[1]] > RANK[k[0]]}
    assert not bad, "üst katmanı import eden alt katman: " + "; ".join(f"{a}({LAYER_OF[a]}) -> {b}({LAYER_OF[b]}) @ {w[0]}" for (a, b), w in bad.items())


def test_expert_forbidden_imports():
    bad = {k: v for k, v in _edges().items() if k[0] == "experts" and k[1] in EXPERT_FORBIDDEN and k not in ALLOW}
    assert not bad, "uzman boyutlama/hakem/defter import edemez (uzman yalnızca tahmin verir): " + "; ".join(f"{b} @ {w[0]}" for (_, b), w in bad.items())


def test_judge_is_signal_blind():
    bad = {k: v for k, v in _edges().items() if k[0] in JUDGE and k[1] in JUDGE_FORBIDDEN and k not in ALLOW}
    assert not bad, "hakem hattı üretici koda bakamaz: " + "; ".join(f"{a} -> {b} @ {w[0]}" for (a, b), w in bad.items())


def test_allow_list_has_no_stale_entries():
    stale = [k for k in ALLOW if k not in _edges()]
    assert not stale, f"ALLOW'daki ihlal artık yok, girdiyi sil (liste yalnızca küçülür): {stale}"


def test_package_does_not_import_outer_dirs():
    for f in PKG.rglob("*.py"):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [n.module] if isinstance(n, ast.ImportFrom) and n.module else [a.name for a in n.names] if isinstance(n, ast.Import) else []
            for m in names:
                assert m.split(".")[0] not in {"scripts", "factory", "tools", "tests"}, f"{f.relative_to(ROOT)}:{n.lineno}: kepler/ dışarıdaki '{m}' kodunu import edemez (akış tek yönlü)"


def test_size_budget():
    sizes = {f: len(f.read_text(encoding="utf-8").splitlines()) for f in PKG.rglob("*.py")}
    big = {str(f.relative_to(ROOT)): n for f, n in sizes.items() if n > MAX_FILE_LINES}
    assert not big, f"dosya başına {MAX_FILE_LINES} satır tavanı aşıldı (böl, uzmanı ayrı dosyaya al): {big}"
    assert sum(sizes.values()) <= MAX_TOTAL_LINES, f"kepler/ toplam {sum(sizes.values())} satır > {MAX_TOTAL_LINES}: AGENTS.md 'kendi kodumuz küçük kalır'. Önce var olanı sadeleştir."


def test_markdown_allowlist():
    try:
        tracked = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return  # git yoksa atla
    extra = [t for t in tracked if not any(fnmatch.fnmatch(t, g) for g in ALLOWED_MD)]
    assert not extra, f"izin listesinde olmayan yeni .md: {extra}. Yeni belge açma; ilgili mevcut belgeye yaz (AGENTS.md 'nereye ne konur'). Gerçekten gerekiyorsa ALLOWED_MD'yi bilerek değiştir."


if __name__ == "__main__":
    import sys

    fails = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)):
        try:
            fn()
            print(f"ok    {name}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL  {name}: {e}", file=sys.stderr)
    sys.exit(1 if fails else 0)
