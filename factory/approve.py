"""İnsan onayı (B/C işleri): `python -m factory.approve <kimlik> approve|reject --by <ad>`.
Anahtar KEPLER_APPROVAL_KEY ortamından okunur. Onay için kimliğin tamamı yazılmalı (yanlış tuşa karşı).
Ajanın bu anahtara erişmemesi bir işletim sistemi sınırıdır (docs/factory.md §5); bu betik tek başına sınır değildir."""
import argparse
import sys

from factory import enqueue


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("id")
    ap.add_argument("decision", choices=["approve", "reject"])
    ap.add_argument("--by", required=True)
    a = ap.parse_args(argv)
    if input(f"{a.id} için {a.decision} onayı. Onaylamak için kimliği yazın: ").strip() != a.id:
        print("iptal")
        return 1
    row = enqueue.approve(a.id, "approved" if a.decision == "approve" else "rejected", a.by)
    print(f"{row['status']}: {a.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
