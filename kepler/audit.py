"""C4: güven denetimi — nedensellik ve determinizm. G2 boru hattının her yeni sinyal için ÇAĞIRMASI gereken kapı
(şu an yalnızca testlerden çağrılıyor; ledger.record'a bağlı DEĞİL — G2'de tek `evaluate()` girişine bağlanacak)."""
import numpy as np
import pandas as pd

from kepler import ledger


def check_causal_book(fn, data: dict[str, pd.DataFrame], fracs=tuple(np.linspace(0.1, 0.95, 16)), seed: int = 0) -> list[int]:
    """fn({sym: kl}) -> {sym: Series | DataFrame}. Ortak zaman çizgisinin k. barından sonra TÜM sembollerin verisi bozulur (panel / kesitsel sinyaller ve Turtle kitabı dahil) ve veri k'da
    kesilir; k öncesi kararlar (stop seviyeleri dahil) değişmemeli. Değişen kesim noktaları; boş liste = nedensel."""
    rng, base, bad, ts = np.random.default_rng(seed), fn(data), [], sorted(set().union(*[d.index for d in data.values()]))
    for f in fracs:
        k = int(len(ts) * f)
        alt, cut = {}, {}
        for s, kl in data.items():
            m = kl.index >= ts[k]
            alt[s] = kl.astype(float)  # tamsayı sütunlar (hacim) float gürültüyü kabul etsin
            for col in ("open", "high", "low", "close", "volume"):
                alt[s].loc[m, col] = kl.loc[m, col].to_numpy() * rng.uniform(0.5, 1.5, int(m.sum()))
            if (~m).any():
                cut[s] = kl[~m]
        pert, trunc = fn(alt), fn(cut)
        same = lambda a, b: a[a.index < ts[k]].equals(b[b.index < ts[k]])  # noqa: E731  (NaN'lar eşit sayılır)
        if not all(same(base[s], pert[s]) and same(base[s], trunc[s].reindex(base[s].index)) for s in cut):
            bad.append(k)
    return bad


def check_causal(signal, kl: pd.DataFrame, fracs=tuple(np.linspace(0.1, 0.95, 16)), seed: int = 0) -> list[int]:
    """Tek sembol: k'dan sonraki barlar bozulunca (ve k'da kesilince) [:k] kararları değişen kesim noktaları. Boş liste = nedensel."""
    return check_causal_book(lambda d: {"x": signal(d["x"])}, {"x": kl}, fracs, seed)


def assert_causal(signal, kl: pd.DataFrame) -> None:
    bad = check_causal(signal, kl)
    if bad:  # assert değil: python -O ile atlanamaz
        raise AssertionError(f"sinyal geleceğe bakıyor: geçmiş kararlar kesim noktalarında değişti {bad}")


def assert_causal_book(fn, data: dict[str, pd.DataFrame]) -> None:
    bad = check_causal_book(fn, data)
    if bad:
        raise AssertionError(f"kitap/panel sinyali geleceğe bakıyor: geçmiş kararlar kesim noktalarında değişti {bad}")


def result_hash(res: dict) -> str:
    """Aynı girdi -> aynı hash (determinizm): dolumlar + özet (9 basamak)."""
    f = res["fills"].round(9).to_dict("records")
    s = {k: round(float(v), 9) for k, v in res["summary"].items()}
    return ledger.sha([f, s])
