"""10. MODEL WYNIKU - zamiast P(rug) przewidujemy WYNIK pozycji po kosztach.

    python -m analizy.result_model report

Zbiór: migracje + 30 min (jak części 1, 9, 10), tokeny z policzonym składem pierwszych kupujących i bundlami.
Cel (klasyfikacja): y = 1, gdy wynik wejścia po kosztach (obecne wyjście bota) > 0 - regresja logistyczna.
Dla porównania regresja liniowa na samym wyniku (te same cechy).
Cechy - max 6, dobór WYŁĄCZNIE na eksploracji:
  4 stałe z części 1c: frac_insider, frac_shared_funder, young_insider_dump, frac_sniper;
  + do 2 z bundli i copy coinów, jeśli pojedyncza cecha ma na eksploracji AUC dla "wynik > 0" poza 0,45-0,55
    (kandydaci: bundle_start_pct, bundle_held_pct, b_shared, is_copy, copy_active, log numeru kopii, img_copy).
Cechy standaryzowane średnią i odchyleniem z eksploracji; brak wartości = średnia z eksploracji.
Filtr: wchodź, gdy score >= mediana score na eksploracji (połowa tokenów). TEST liczony raz, bez strojenia.
"""
from __future__ import annotations

import json
import math
import time

from analizy import common as C

FIXED = ["frac_insider", "frac_shared_funder", "young_insider_dump", "frac_sniper"]
CANDS = ["bundle_start_pct", "bundle_held_pct", "b_shared", "is_copy", "copy_active", "log_copy_n", "img_copy"]
MODEL_PATH = C.ROOT / "analizy" / "result_model.json"


def dataset() -> list[dict]:
    from analizy import bundles, copycoins, first_buyers
    ents, _, _, _ = first_buyers.build()
    sets = bundles.build()
    bundles.finish(sets)
    bmap = {e["mint"]: e for e in sets["mig"] if e["assessable"]}
    copycoins.classify(ents, copycoins.universe())
    out = []
    for e in ents:
        b = bmap.get(e["mint"])
        if not b or not e.get("copy_known"):
            continue
        for k in ("bundle_start_pct", "bundle_held_pct", "b_shared"):
            e[k] = b[k]
        e["log_copy_n"] = math.log(e["copy_n"])
        out.append(e)
    C.add_outcomes(out)
    for e in out:
        e["win"] = int(e["s0"] > 0)
    return out


def ols(X, y, ridge=1e-3):
    k = len(X[0]) + 1
    A = [[0.0] * k for _ in range(k)]
    v = [0.0] * k
    for xi, yi in zip(X, y):
        row = [1.0] + list(xi)
        for i in range(k):
            v[i] += row[i] * yi
            for j in range(k):
                A[i][j] += row[i] * row[j]
    for i in range(1, k):
        A[i][i] += ridge * len(X)
    m = [A[i] + [v[i]] for i in range(k)]
    for i in range(k):
        p = max(range(i, k), key=lambda r: abs(m[r][i]))
        m[i], m[p] = m[p], m[i]
        for r in range(k):
            if r != i and m[i][i]:
                f = m[r][i] / m[i][i]
                m[r] = [a - f * b for a, b in zip(m[r], m[i])]
    w = [m[i][k] / m[i][i] if m[i][i] else 0.0 for i in range(k)]
    return w[1:], w[0]


def report() -> str:
    from analizy.first_buyers import fit_logreg
    data = dataset()
    ex, te = C.split_time(data)
    out = ["## 10. Model wyniku pozycji (zamiast P(rug))\n", "Zbiór" + (__doc__ or "").split("Zbiór", 1)[1],
           f"\nTokenów: **{len(data)}** (eksploracja {len(ex)}, TEST {len(te)}); wynik > 0 na eksploracji: "
           f"{C.mean([e['win'] for e in ex]):.0%}, na teście {C.mean([e['win'] for e in te]):.0%}.\n"]
    # dobór cech z bundli / copy coinów - tylko eksploracja
    rows, picked = [], []
    for f in FIXED + CANDS:
        pos = [e[f] for e in ex if e["win"] and e.get(f) is not None]
        neg = [e[f] for e in ex if not e["win"] and e.get(f) is not None]
        a = C.auc(pos, neg)
        pos_t = [e[f] for e in te if e["win"] and e.get(f) is not None]
        neg_t = [e[f] for e in te if not e["win"] and e.get(f) is not None]
        a_t = C.auc(pos_t, neg_t)
        use = f in FIXED or (abs(a - 0.5) >= 0.05)
        rows.append([f, f"{len(pos) + len(neg)}", f"{a:.3f}", f"{a_t:.3f}",
                     "stała (część 1c)" if f in FIXED else ("kandydat" if use else "—")])
        if f in CANDS and use:
            picked.append((abs(a - 0.5), f))
    extra = [f for _, f in sorted(picked, reverse=True)[:2]]
    feats = FIXED + extra
    out.append("**Pojedyncze cechy - AUC dla \"wynik > 0\" (dobór na eksploracji; TEST tylko do wglądu):**\n")
    out.append(C.table(["cecha", "N eksploracja", "AUC eksploracja", "AUC TEST", "w modelu?"], rows))
    out.append(f"\nCechy modelu ({len(feats)}): {', '.join(feats)}.\n")
    mean = {f: C.mean([e[f] for e in ex if e.get(f) is not None]) for f in feats}
    std = {f: (C.mean([(e[f] - mean[f]) ** 2 for e in ex if e.get(f) is not None]) ** 0.5) or 1.0 for f in feats}
    z = lambda e: [((e[f] if e.get(f) is not None else mean[f]) - mean[f]) / std[f] for f in feats]
    w, b = fit_logreg([z(e) for e in ex], [e["win"] for e in ex])
    wl, bl = ols([z(e) for e in ex], [e["s0"] for e in ex])
    for e in data:
        zz = z(e)
        e["p_win"] = 1 / (1 + math.exp(-(b + sum(a * c for a, c in zip(w, zz)))))
        e["pred"] = bl + sum(a * c for a, c in zip(wl, zz))
    MODEL_PATH.write_text(json.dumps({"target": "wynik po kosztach > 0 (obecne wyjście)", "features": feats,
                                      "coef": dict(zip(feats, w)), "intercept": b, "mean": mean, "std": std,
                                      "trained_on": f"{len(ex)} tokenów eksploracji, {time.strftime('%d.%m.%Y')}"},
                                     indent=1), encoding="utf-8")
    rows = []
    for name, key, ok in (("logistyczna P(wynik > 0)", "p_win", lambda e: e["win"]),
                          ("liniowa: przewidywany wynik", "pred", lambda e: e["win"])):
        a_ex = C.auc([e[key] for e in ex if ok(e)], [e[key] for e in ex if not ok(e)])
        a_te = C.auc([e[key] for e in te if ok(e)], [e[key] for e in te if not ok(e)])
        rows.append([name, ", ".join(f"{f} {c:+.2f}" for f, c in zip(feats, w if key == "p_win" else wl)),
                     f"{a_ex:.3f}", f"**{a_te:.3f}**"])
    out.append("**Modele (współczynniki na cechach standaryzowanych; AUC dla wynik > 0):**\n")
    out.append(C.table(["model", "współczynniki", "AUC eksploracja", "AUC TEST"], rows))
    rows = []
    for key, nm in (("p_win", "logistyczna"), ("pred", "liniowa")):
        thr = sorted(e[key] for e in ex)[len(ex) // 2]
        for ycol, yname in (("s0", "obecne wyjście"), ("s6", "S6")):
            rows.append(C.filter_eval(f"model wyniku ({nm}): score >= mediana eksploracji ({yname})", data,
                                      lambda e, key=key, thr=thr: e[key] >= thr, ycol))
    out.append("\n**Filtr z modelu (próg = mediana score na eksploracji):**\n")
    out.append(C.table(C.FILTER_HEAD, rows))
    thr = sorted(e["p_win"] for e in ex)[len(ex) // 2]
    rows = []
    for lbl, s in (("eksploracja", ex), ("TEST", te)):
        keep = [e for e in s if e["p_win"] >= thr]
        rows.append([lbl, f"{len(s)}", f"{sum(e['s0'] for e in s) * 50:+,.0f}", f"{len(keep)}{C.rel(len(keep))}",
                     f"{sum(e['s0'] for e in keep) * 50:+,.0f}", C.pct(C.mean([e['s0'] for e in keep])),
                     f"{C.mean([e['rug'] for e in keep]):.0%} / {C.mean([e['rug'] for e in s]):.0%}"])
    out.append("\n**W dolarach (stawka $50, model logistyczny, obecne wyjście):**\n")
    out.append(C.table(["zbiór", "N wszystkich", "$ wszystkie", "N wpuszczonych", "$ wpuszczone", "śr. wpuszczone",
                        "% rugów wpuszczone / wszystkie"], rows))
    return "\n".join(out)


if __name__ == "__main__":
    print(report())
