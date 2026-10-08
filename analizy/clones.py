"""Klony: jeden bot rozbity na wiele portfeli (8.10.2026). Odkryte przy Bot A i Bot A2 (te same godziny, ta sama
stawka i stopy czasowe, wejścia ~45 s od siebie, 0 wspólnych tokenów).

    python -m analizy.clones      # -> analizy/KLONY.md + data/klony.json (lista portfeli do losowania bez klonów)

Kandydaci: portfele ze strumienia z >= 100 zamkniętymi pozycjami na krzywej, które NIE kupują w slocie utworzenia
(<= 20% zakupów w slocie startu). Odcisk zachowania: mediana stawki, mediana trzymania, udział wyjść po 14-19 s,
58-63 s i 295-305 s, mediana wieku tokena przy wejściu, godziny aktywności. Para = klon, gdy: odcisk podobny (stawka
w granicach x1.3, trzymanie x1.5, wiek x1.5, udziały stopów czasowych +-10 pp), >= 70% wspólnych godzin aktywności
i wspólnych tokenów <= 2% mniejszego portfela (bot nie kupuje dwa razy tego samego). Grupa klonów = spójna składowa.
"""
from __future__ import annotations

import collections
import json
import statistics as S
import time

from analizy import common as C

MIN_POS = 100


def positions():
    st = C.ro("stream.db")
    created = dict(st.execute("SELECT id, created_ts FROM mints"))
    first_slot = {}
    out = collections.defaultdict(list)
    q = ("SELECT wallet_id, mint_id, SUM(CASE WHEN buy=1 THEN sol ELSE 0 END)/1e9, SUM(CASE WHEN buy=0 THEN sol ELSE 0 END)/1e9, "
         "SUM(CASE WHEN buy=1 THEN tok ELSE 0 END), SUM(CASE WHEN buy=0 THEN tok ELSE 0 END), "
         "MIN(CASE WHEN buy=1 THEN ts END), MIN(CASE WHEN buy=0 THEN ts END), MIN(CASE WHEN buy=1 THEN slot END) "
         "FROM trades GROUP BY wallet_id, mint_id")
    for w, m, b, s, bt, stk, tb, ts_, sb in st.execute(q):
        if b > 0 and bt > 0 and 0.98 * bt <= stk <= 1.02 * bt and tb and ts_:
            out[w].append((m, b, s, tb, ts_ - tb, sb))
    cand = {w: ps for w, ps in out.items() if len(ps) >= MIN_POS}
    ms = {m for ps in cand.values() for p in ps for m in [p[0]]}
    for m, s0 in st.execute("SELECT mint_id, MIN(slot) FROM trades GROUP BY mint_id"):
        if m in ms:
            first_slot[m] = s0
    addr = dict(st.execute("SELECT id, addr FROM wallets"))
    return cand, created, first_slot, addr


def fingerprint(ps, created, first_slot):
    holds = [p[4] for p in ps]
    n = len(ps)
    return {"n": n, "stawka": S.median(p[1] for p in ps), "trzyma": S.median(holds),
            "s14_19": sum(14 <= h <= 19 for h in holds) / n, "s58_63": sum(58 <= h <= 63 for h in holds) / n,
            "s295_305": sum(295 <= h <= 305 for h in holds) / n,
            "wiek": S.median(p[3] - created[p[0]] for p in ps if created.get(p[0])) if any(created.get(p[0]) for p in ps) else None,
            "slot0": sum(p[5] == first_slot.get(p[0]) for p in ps) / n,
            "wynik": sum(p[2] - p[1] for p in ps), "na_poz": S.mean((p[2] - p[1]) / p[1] for p in ps),
            "godziny": {int(p[3] // 3600) for p in ps}, "tokeny": {p[0] for p in ps}}


def close(a, b, k):
    x, y = a[k], b[k]
    return x and y and max(x, y) / min(x, y)


def similar(a, b):
    return (close(a, b, "stawka") <= 1.3 and close(a, b, "trzyma") <= 1.5 and (close(a, b, "wiek") or 9) <= 1.5
            and all(abs(a[k] - b[k]) <= 0.10 for k in ("s14_19", "s58_63", "s295_305")))


def report():
    cand, created, first_slot, addr = positions()
    fp = {w: fingerprint(ps, created, first_slot) for w, ps in cand.items()}
    fp = {w: f for w, f in fp.items() if f["slot0"] <= 0.2}
    ws = sorted(fp)
    parent = {w: w for w in ws}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    pairs = 0
    for i, a in enumerate(ws):
        for b in ws[i + 1:]:
            A, B = fp[a], fp[b]
            if not similar(A, B):
                continue
            hours = len(A["godziny"] & B["godziny"]) / min(len(A["godziny"]), len(B["godziny"]))
            common = len(A["tokeny"] & B["tokeny"]) / min(len(A["tokeny"]), len(B["tokeny"]))
            if hours >= 0.7 and common <= 0.02:
                parent[find(a)] = find(b)
                pairs += 1
    comp = collections.defaultdict(list)
    for w in ws:
        comp[find(w)].append(w)
    groups = sorted((g for g in comp.values() if len(g) >= 2), key=len, reverse=True)
    solo = [g[0] for g in comp.values() if len(g) == 1]
    out = [f"# Klony - jeden bot na wielu portfelach ({time.strftime('%d.%m.%Y %H:%M')})\n",
           f"Kandydaci (>= {MIN_POS} zamkniętych pozycji na krzywej, <= 20% zakupów w slocie startu): {len(fp)}. "
           f"Par klonów: {pairs}; grup klonów: {len(groups)} (portfeli w nich {sum(len(g) for g in groups)}); "
           f"portfeli bez klona: {len(solo)}.\n"]
    rows = []
    for gi, g in enumerate(groups[:25], 1):
        F = [fp[w] for w in g]
        rows.append([gi, len(g), sum(f["n"] for f in F), f"{sum(f['wynik'] for f in F):+.1f}",
                     C.pct(S.mean(f["na_poz"] for f in F)), f"{S.median(f['stawka'] for f in F):.2f}",
                     f"{S.median(f['trzyma'] for f in F):.0f} s",
                     f"{S.mean(f['s14_19'] for f in F):.0%} / {S.mean(f['s58_63'] for f in F):.0%} / {S.mean(f['s295_305'] for f in F):.0%}",
                     f"{S.median(f['wiek'] for f in F if f['wiek'] is not None) / 60:.1f} min",
                     ", ".join(addr[w][:6] for w in g[:6]) + (" ..." if len(g) > 6 else "")])
    out.append(C.table(["grupa", "portfeli", "pozycji", "suma SOL", "śr. na poz.", "stawka SOL", "trzymanie (med.)",
                        "wyjścia 14-19 s / 58-63 s / 295-305 s", "wiek tokena", "portfele"], rows))
    known = {"Bot A", "Bot A2", "Trader B", "Bot C"}
    for gi, g in enumerate(groups, 1):
        hit = [addr[w][:6] for w in g if addr[w][:6] in known]
        if hit:
            out.append(f"\nAnalizowane wcześniej w grupie {gi}: {', '.join(hit)}.")
    # do losowania: jeden przedstawiciel z grupy (najwięcej pozycji) + portfele bez klona; zyskowne w obu połowach
    reps = [max(g, key=lambda w: fp[w]["n"]) for g in groups] + solo
    json.dump({"groups": [[addr[w] for w in g] for g in groups],
               "reps": [{"addr": addr[w], "n": fp[w]["n"], "wynik": fp[w]["wynik"], "na_poz": fp[w]["na_poz"],
                         "grupa": next((i + 1 for i, g in enumerate(groups) if w in g), None)} for w in reps]},
              open(C.DATA / "klony.json", "w", encoding="utf-8"))
    return "\n".join(out)


if __name__ == "__main__":
    txt = report()
    (C.ROOT / "analizy" / "KLONY.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
