"""Explicit, audited research executables. The installed root-owned policy is an additional gate.

Never interpret incoming user-controlled module names or free-form command strings.
"""
RESEARCH_ENTRYPOINTS = frozenset({
    "scripts/ensemble.py",
    "scripts/carryxs_card.py",
    "scripts/g2.py",
    "experiments/erf01/atlas.py",
})
