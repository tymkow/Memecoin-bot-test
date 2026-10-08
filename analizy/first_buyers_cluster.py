"""1b. FIRST BUYERS - klasteryzacja (KMeans, DBSCAN) i porównanie z grupami regułowymi.

Wymaga numpy + scikit-learn (osobne środowisko badawcze, nie bot):  <mlenv>\\Scripts\\python analizy/first_buyers_cluster.py
Wejście: analizy/first_buyers_wallets.csv (z `python -m analizy.first_buyers report`). Model dopasowany WYŁĄCZNIE na
portfelach z tokenów eksploracji; tokeny testu tylko przypisane do klastrów. Liczba klastrów KMeans wybrana po
silhouette na eksploracji. Predykcja: udział portfeli z każdego klastra wśród pierwszych kupujących tokena -> rug/pump.
"""
import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import roc_auc_score, silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(HERE / "first_buyers_wallets.csv", encoding="utf-8")))


def num(x, default=0.0):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


FEAT = ["slot_rel", "buy_sol", "sold_5m", "same_slot", "shared_funder", "by_creator", "active", "age_h", "n_tx",
        "prior_n_tokens", "prior_win_rate", "prior_hold_med_s", "is_creator"]


def vec(r):
    return [math.log1p(max(num(r["slot_rel"]), 0)), math.log1p(num(r["buy_sol"])), num(r["sold_5m"]), num(r["same_slot"]),
            num(r["shared_funder"]), num(r["by_creator"]), num(r["active"]), math.log1p(max(num(r["age_h"], 1e4), 0)),
            math.log1p(num(r["n_tx"], 3000)), math.log1p(num(r["prior_n_tokens"])), num(r["prior_win_rate"], 0.5),
            math.log1p(num(r["prior_hold_med_s"], 600)), num(r["is_creator"])]


X = np.array([vec(r) for r in rows])
ex = np.array([r["split"] == "explore" for r in rows])
sc = StandardScaler().fit(X[ex])
Z = sc.transform(X)
out = ["## 1b. First buyers - klasteryzacja (KMeans / DBSCAN)\n",
       f"Portfeli (portfel x token): {len(rows)} (eksploracja {ex.sum()}, TEST {(~ex).sum()}); cech: {len(FEAT)}.\n"]
sil = {}
rng = np.random.default_rng(1)
idx = np.where(ex)[0]
sample = rng.choice(idx, size=min(3000, len(idx)), replace=False)
for k in range(2, 8):
    km = KMeans(n_clusters=k, n_init=10, random_state=1).fit(Z[ex])
    sil[k] = silhouette_score(Z[sample], km.predict(Z[sample]))
k = max(sil, key=sil.get)
km = KMeans(n_clusters=k, n_init=10, random_state=1).fit(Z[ex])
lab = km.predict(Z)
out.append("silhouette (eksploracja): " + ", ".join(f"k={a}: {b:.3f}" for a, b in sil.items()) + f" -> **k={k}**\n")
groups = ["insider", "sniper", "smart", "retail"]
tab = ["| klaster | N | " + " | ".join(groups) + " | śr. wiek (h) | sprzedał w 5 min | śr. zakup SOL |", "|" + "---|" * (6 + len(groups))]
for c in range(k):
    m = lab == c
    gc = Counter(r["group"] for r, mm in zip(rows, m) if mm)
    tot = m.sum()
    tab.append(f"| K{c} | {tot} | " + " | ".join(f"{gc[g] / tot:.0%}" for g in groups) +
               f" | {np.nanmedian([num(r['age_h'], np.nan) for r, mm in zip(rows, m) if mm]):.0f}"
               f" | {np.mean([num(r['sold_5m']) for r, mm in zip(rows, m) if mm]):.0%}"
               f" | {np.mean([num(r['buy_sol']) for r, mm in zip(rows, m) if mm]):.2f} |")
out.append("**Skład klastrów KMeans wg grup regułowych** (czy klasteryzacja odtwarza reguły?):\n")
out.append("\n".join(tab))

# DBSCAN: eps z wykresu k-odległości (90. percentyl odległości do 5. sąsiada) na eksploracji
nn = NearestNeighbors(n_neighbors=5).fit(Z[sample])
eps = float(np.percentile(nn.kneighbors(Z[sample])[0][:, -1], 90))
db = DBSCAN(eps=eps, min_samples=10).fit(Z[sample])
dl = Counter(db.labels_)
out.append(f"\nDBSCAN (eps={eps:.2f}, min 10, próbka {len(sample)} portfeli eksploracji): klastrów "
           f"{len([c for c in dl if c >= 0])}, szum {dl.get(-1, 0) / len(sample):.0%}, największy klaster "
           f"{max((v for c, v in dl.items() if c >= 0), default=0) / len(sample):.0%} - "
           f"{'dane tworzą jedną dużą chmurę (brak naturalnych grup)' if max((v for c, v in dl.items() if c >= 0), default=0) / len(sample) > 0.7 else 'są wyraźne skupiska'}.\n")

# predykcja: skład klastrów w tokenie -> rug / pump
tok = defaultdict(lambda: {"split": None, "label": None, "sim": None, "c": Counter(), "n": 0})
for r, c in zip(rows, lab):
    t = tok[r["mint"]]
    t["split"], t["label"], t["sim"] = r["split"], r["label"], num(r["sim"])
    t["c"][c] += 1
    t["n"] += 1
out.append("**Udział klastra wśród pierwszych kupujących -> wynik tokena (AUC; kierunek z eksploracji):**\n")
pt = ["| klaster | cel | AUC eksploracja | AUC TEST | trzyma się? |", "|---|---|---|---|---|"]
for c in range(k):
    for target in ("rug", "pump"):
        res = {}
        for sp in ("explore", "test"):
            ts = [t for t in tok.values() if t["split"] == sp]
            y = [t["label"] == target for t in ts]
            x = [t["c"][c] / t["n"] for t in ts]
            res[sp] = roc_auc_score(y, x) if 0 < sum(y) < len(y) else float("nan")
        flip = res["explore"] < 0.5
        a_ex = 1 - res["explore"] if flip else res["explore"]
        a_te = 1 - res["test"] if flip else res["test"]
        ok = a_ex >= 0.55 and a_te >= 0.55
        pt.append(f"| K{c} | {target} | {a_ex:.3f} | {a_te:.3f} | {'TAK' if ok else '—'} |")
out.append("\n".join(pt))
n_te = sum(1 for t in tok.values() if t["split"] == "test")
out.append(f"\nTokenów: eksploracja {sum(1 for t in tok.values() if t['split'] == 'explore')}, TEST {n_te}"
           f"{' ⚠️ niewiarygodny' if n_te < 30 else ''}.")
(HERE / "first_buyers_cluster.md").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
