"""C4: güven denetimi — nedensellik ve determinizm. G2 boru hattının her yeni sinyal için ÇAĞIRMASI gereken kapı
(şu an yalnızca testlerden çağrılıyor; ledger.record'a bağlı DEĞİL — G2'de tek `evaluate()` girişine bağlanacak)."""
import numpy as np
import pandas as pd

from kepler import ledger


def check_causal(signal, kl: pd.DataFrame, fracs=tuple(np.linspace(0.1, 0.95, 16)), seed: int = 0) -> list[int]:
    """k'dan sonraki barlar bozulunca (ve k'da kesilince) [:k] kararları değişen kesim noktaları. Boş liste = nedensel."""
    rng, base, bad = np.random.default_rng(seed), signal(kl), []
    for f in fracs:
        k = int(len(kl) * f)
        alt = kl.copy()
        for col in ("open", "high", "low", "close", "volume"):
            alt.iloc[k:, alt.columns.get_loc(col)] = kl[col].iloc[k:].to_numpy() * rng.uniform(0.5, 1.5, len(kl) - k)
        same = lambda a, b: a.iloc[:k].equals(b.iloc[:k])  # noqa: E731  (NaN'lar eşit sayılır)
        if not same(base, signal(alt)) or not same(base, signal(kl.iloc[:k]).reindex(kl.index)):
            bad.append(k)
    return bad


def assert_causal(signal, kl: pd.DataFrame) -> None:
    bad = check_causal(signal, kl)
    if bad:  # assert değil: python -O ile atlanamaz
        raise AssertionError(f"sinyal geleceğe bakıyor: geçmiş kararlar kesim noktalarında değişti {bad}")


def result_hash(res: dict) -> str:
    """Aynı girdi -> aynı hash (determinizm): dolumlar + özet (9 basamak)."""
    f = res["fills"].round(9).to_dict("records")
    s = {k: round(float(v), 9) for k, v in res["summary"].items()}
    return ledger.sha([f, s])
