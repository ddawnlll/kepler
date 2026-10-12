"""D: books/*.txt -> books_text/ (kopya) + QUALITY.md. Kaynaklar PDF değil, hazır metin (sayfa bilgisi yok).
Not: books/ yerel ve git dışı; books_text/ repoya girer (repo özel kalmalı — telif). stdlib ile yerelde çalışır (ağır değil)."""
import re
import shutil
from pathlib import Path

SRC, DST = Path("books"), Path("books_text")
DST.mkdir(exist_ok=True)
rows = []
for p in sorted(SRC.glob("*.txt")):
    raw = p.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    n = len(text)
    lines = text.splitlines()
    empty = sum(1 for l in lines if not l.strip()) / max(1, len(lines))
    bad = (text.count("�") + len(re.findall(r"[\x00-\x08\x0b\x0e-\x1f]", text))) / max(1, n)
    alpha = sum(c.isalpha() for c in text) / max(1, n)
    flags = [f for f, c in (("KISA(<20k karakter)", n < 20_000), ("BOZUK(>0.5% geçersiz karakter)", bad > 0.005),
                            ("DÜŞÜK_HARF(<60% harf; OCR/tablo?)", alpha < 0.60), ("BOŞ_SATIR(>60%)", empty > 0.60)) if c]
    shutil.copyfile(p, DST / p.name)
    rows.append((p.name, n, len(text.split()), len(lines), empty, bad, alpha, ",".join(flags) or "-"))
md = ["# Kitap metni kalite notu", "", f"{len(rows)} kitap (books/*.txt). Kaynaklar zaten düz metin: PDF değil, sayfa sayısı yok → sayfa yerine satır/karakter ölçüleri.",
      "`books/_parts/` kitapların parçalı kopyaları (yinelenen içerik) — atlandı. `books/Moneyball`, `books/The`: 0 bayt, atlandı.",
      "OCR gerektiren taranmış PDF yok (PDF hiç yok). Bayraklı kitaplar elle bakılmalı.", "",
      "| dosya | karakter | kelime | satır | boş satır | geçersiz kr. | harf oranı | bayrak |", "|---|---|---|---|---|---|---|---|"]
md += [f"| {a[:70]} | {b} | {c} | {d} | {e:.2f} | {f:.4f} | {g:.2f} | {h} |" for a, b, c, d, e, f, g, h in rows]
(DST / "QUALITY.md").write_text("\n".join(md))
print(len(rows), "kitap;", sum(1 for r in rows if r[-1] != "-"), "bayraklı")
