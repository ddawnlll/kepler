"""Root-owned installation policy; never read policy from an agent commit."""
import json
from pathlib import Path

POLICY = Path("/etc/kepler/policy.json")


def load(path=POLICY):
    p = json.loads(Path(path).read_text())
    for key in ("workers_max", "max_attempts", "heartbeat_seconds", "lease_seconds", "timeout_seconds"):
        if type(p.get(key)) is not int or p[key] <= 0:
            raise ValueError(f"geçersiz politika: {key}")
    if p["workers_max"] != 1:
        raise ValueError("tek sandbox kullanıcısıyla workers_max=1 olmalı")
    if p["lease_seconds"] <= 3 * p["heartbeat_seconds"]:
        raise ValueError("lease heartbeat aralığından yeterince büyük olmalı")
    if p.get("budget_hard_action") != "warn":
        raise ValueError("MISSION bütçe davranışı warn olmalı")
    if not p.get("required_tests") or not p.get("checks_required_before_merge"):
        raise ValueError("merge kontrolleri zorunlu")
    if p.get("research_enabled") and not all(p.get(k) is True for k in ("dev_workspace_verified", "provider_limits_verified", "acceptance_verified")):
        raise ValueError("DEV izolasyonu, dış limitler ve kabul provası doğrulanmadan araştırma açılamaz")
    return p
