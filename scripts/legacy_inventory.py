"""Read-only historical-ledger migration: immutable file/row digests and honest provenance labels.
Never rewrites old rows or reconstructs unknown experiment identities or statistical families.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def inventory(root):
    root = Path(root)
    files, rows, statuses = {}, [], Counter()
    for p in sorted(root.rglob("*.jsonl")):
        body = p.read_bytes()
        relative = str(p.relative_to(root))
        files[relative] = hashlib.sha256(body).hexdigest()
        for line, raw in enumerate(body.splitlines(), 1):
            if not raw.strip():
                continue
            r = json.loads(raw)
            label = "receipt_present_not_verified" if r.get("receipt") else "legacy_partial_provenance"
            statuses[label] += 1
            digest = hashlib.sha256(raw).hexdigest()
            legacy_id = hashlib.sha256(f"{relative}:{line}:{digest}".encode()).hexdigest()
            rows.append(dict(file=relative, line=line, row_sha256=digest, legacy_id=legacy_id, provenance_status=label))
    return dict(schema=1, scope="repository_snapshot_only", file_sha256=files, rows=rows, n_rows=len(rows),
                provenance_counts=dict(statuses), statistical_hypothesis_count=None,
                note="Row uniqueness is not statistical independence. Modal-only records and unrecorded searches are not reconstructed.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="ledger")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    doc = inventory(a.root)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, allow_nan=False))
    tmp.replace(out)
    print(json.dumps({k: v for k, v in doc.items() if k not in ("rows", "file_sha256")}, indent=1))


if __name__ == "__main__":
    main()
