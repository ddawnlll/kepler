"""Point-in-time contracts for publication- and vintage-aware macro data.

These primitives select only explicitly available source vintages. They do not
retrieve data, infer missing releases, or forward-fill unreleased observations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
import re
from typing import Iterable

from kepler.intelligence.validation import utc


@dataclass(frozen=True)
class MacroVintage:
    """One source-provided value version and when that exact version was usable."""

    series: str
    observation_period_end: date
    value: float
    unit: str
    source: str
    source_sha256: str
    vintage_id: str
    publication_at: datetime
    vintage_at: datetime
    available_at: datetime

    def __post_init__(self):
        if not self.series or not self.unit or not self.source or not self.vintage_id:
            raise ValueError("macro series, unit, source and vintage_id are required")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.source_sha256):
            raise ValueError("source_sha256 must be a 64-character SHA256 hex digest")
        if isinstance(self.observation_period_end, datetime) or not isinstance(self.observation_period_end, date):
            raise TypeError("observation_period_end must be a date")
        value = float(self.value)
        if not math.isfinite(value):
            raise ValueError("macro value must be finite")
        publication = utc(self.publication_at)
        vintage = utc(self.vintage_at)
        available = utc(self.available_at)
        if vintage < publication:
            raise ValueError("vintage_at cannot precede publication_at")
        if available < publication or available < vintage:
            raise ValueError("available_at cannot precede publication or vintage time")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "source_sha256", self.source_sha256.lower())
        object.__setattr__(self, "publication_at", publication)
        object.__setattr__(self, "vintage_at", vintage)
        object.__setattr__(self, "available_at", available)


def asof_macro_vintages(
    records: Iterable[MacroVintage], prediction_at: datetime,
) -> tuple[MacroVintage, ...]:
    """Select the latest available version of each observation as of ``t``.

    Records with a future availability timestamp do not participate in either
    value selection or validation. In particular, a later revision cannot
    replace the first release before that revision was actually available.
    Units must be stable within each visible series; conversion belongs in a
    separately sourced, training-fitted transformation.
    """
    cutoff = utc(prediction_at)
    visible = []
    for record in records:
        if not isinstance(record, MacroVintage):
            raise TypeError("records must contain MacroVintage values")
        if record.available_at <= cutoff:
            visible.append(record)
    units: dict[str, set[str]] = {}
    grouped: dict[tuple[str, date], list[MacroVintage]] = {}
    for record in visible:
        units.setdefault(record.series, set()).add(record.unit)
        grouped.setdefault((record.series, record.observation_period_end), []).append(record)
    changed = {series: sorted(values) for series, values in units.items() if len(values) > 1}
    if changed:
        raise ValueError(f"visible macro vintages have inconsistent units: {changed}")

    selected = []
    for key, versions in grouped.items():
        # Availability gates which versions can participate. Among visible
        # versions, the source vintage timestamp determines revision order;
        # a late-ingested old vintage must not overwrite a newer visible one.
        newest_vintage = max(record.vintage_at for record in versions)
        latest = [record for record in versions if record.vintage_at == newest_vintage]
        signatures = {(record.value, record.unit, record.source, record.source_sha256, record.vintage_id,
                       record.publication_at, record.available_at) for record in latest}
        if len(signatures) > 1:
            raise ValueError(f"ambiguous macro vintage at the same as-of time: {key}")
        selected.append(sorted(latest, key=lambda record: (record.source, record.vintage_id))[0])
    return tuple(sorted(selected, key=lambda record: (record.series, record.observation_period_end)))
