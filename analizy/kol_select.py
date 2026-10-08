"""Czy trader ODRÓŻNIA trash od dobrych tokenów? Jego wybory vs równie gorące starty, które pominął (8.10.2026).

    python -m analizy.kol_select [nazwa]     # -> analizy/<NAZWA>_WYBOR.md (domyślnie Cupsey)

Dla każdego jego wejścia na krzywej pump.fun <= 60 s od startu (chwila T, cechy tylko sprzed jego slotu):
  grupa porównawcza = inne tokeny utworzone w ostatnich 2 min przed T, które w chwili T były w TOP 5 po kwocie zakupów
  z ostatnich 10 s (tak samo gorące jak jego wybór; on ich nie ruszał).
Wynik tokena od ceny w chwili T (krzywa pump.fun ze strumienia; po migracji - ostatnia cena krzywej + flaga migracji):
  max wzrost w 5 / 30 min, cena po 5 / 30 min, migracja w 30 min, "rug" = -70% od ceny w T zanim +100% (30 min),
  "pump" = +100% zanim -70%. To mierzy WYBÓR tokena, nie jego wykonanie (wejście/wyjście).
"""
from __future__ import annotations

import bisect
import sys
import time

from analizy import common as C
from analizy import cupsey as Q
from analizy import cupsey_signals as S

H5, H30 = 300, 1800
TOP = 5


def outcome(tp: S.Tape, slot: int, T: float, mig: float | None) -> dict | None:
    k = bisect.bisect_left(tp.slot, slot)
    if k == 0 or not tp.px[k - 1]:
        return None
    p0 = tp.px[k - 1]
    o = {"mig30": 1.0 if mig and T < mig <= T + H30 else 0.0}
    path = [(tp.ts[i], tp.px[i]) for i in range(k, len(tp.slot)) if tp.ts[i] <= T + H30 and tp.px[i]]
    for h, nm in ((H5, "5"), (H30, "30")):
        seg = [p for t, p in path if t <= T + h]
        o[f"max{nm}"] = max(seg + [p0]) / p0 - 1
        o[f"po{nm}"] = (seg[-1] if seg else p0) / p0 - 1
    lab = "nic"
    for t, p in path:
        if p >= 2 * p0:
            lab = "pump"
            break
        if p <= 0.3 * p0:
            lab = "rug"
            break
    if lab == "nic" and o["mig30"]:
        lab = "pump" if o["max30"] >= 1 else "nic"
    o["pump"], o["rug"] = float(lab == "pump"), float(lab == "rug")
    return o


def report(name: str = "Cupsey", episodes=None, wallet: str = Q.W) -> str:
    st = C.ro("stream.db")
    eps = episodes if episodes is not None else Q.episodes()
    ids = {r[1]: r[0] for r in st.execute("SELECT id, mint FROM mints")}
    info = {r[0]: {"created": r[1], "creator": r[2]} for r in st.execute("SELECT id, created_ts, creator FROM mints")}
    mig = dict(st.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind IN ('complete','migrate') GROUP BY mint_id"))
    his = {ids[e["mint"]] for e in eps if e["mint"] in ids}
    created = sorted((v["created"], k) for k, v in info.items() if v["created"])
    cts = [c for c, _ in created]
    tapes = {}

    def tape(m):
        if m not in tapes:
            tapes[m] = S.Tape(st, m)
        return tapes[m]

    pairs = []                   # (T, jego wynik, [wyniki pominiętych z top 5], jego miejsce)
    for e in eps:
        mid, leg = ids.get(e["mint"]), e["legs"][0]
        if not mid or leg["venue"] != "pump_curve" or not info[mid]["created"]:
            continue
        T = leg["bt"]
        if not 0 <= T - info[mid]["created"] <= 60:
            continue
        lo, hi = bisect.bisect_left(cts, T - 120), bisect.bisect_right(cts, T)
        ranked = []
        for _, m in created[lo:hi]:
            tp = tape(m)
            if not tp.slot:
                continue
            f = S.entry_feats(tp, leg["slot"], T, info[m], set(), None)
            if f:
                ranked.append((f["kupno_sol_10s"], m))
        ranked.sort(reverse=True)
        place = next((i + 1 for i, (_, m) in enumerate(ranked) if m == mid), None)
        mine = outcome(tape(mid), leg["slot"], T, mig.get(mid))
        others = [outcome(tape(m), leg["slot"], T, mig.get(m)) for _, m in ranked[:TOP] if m != mid and m not in his]
        others = [o for o in others if o]
        if mine and others:
            pairs.append((T, mine, others, place))
    pairs.sort(key=lambda x: x[0])
    mid_t = pairs[len(pairs) // 2][0] if pairs else 0
    keys = [("max5", "max wzrost 5 min"), ("max30", "max wzrost 30 min"), ("po5", "cena po 5 min"),
            ("po30", "cena po 30 min"), ("mig30", "migracja w 30 min"), ("pump", "pump (+100% przed -70%)"),
            ("rug", "rug (-70% przed +100%)")]
    rows = []
    for k, lab in keys:
        a = [p[1][k] for p in pairs]
        b = [o[k] for p in pairs for o in p[2]]
        a1 = [p[1][k] for p in pairs if p[0] < mid_t]
        b1 = [o[k] for p in pairs if p[0] < mid_t for o in p[2]]
        a2 = [p[1][k] for p in pairs if p[0] >= mid_t]
        b2 = [o[k] for p in pairs if p[0] >= mid_t for o in p[2]]
        fmt = (lambda xs: f"{C.mean(xs):.0%}") if k in ("mig30", "pump", "rug") else \
              (lambda xs: f"{C.pct(C.median(xs))} (śr. {C.pct(C.mean(xs))})")
        rows.append([lab, fmt(a), fmt(b), f"{C.auc(a, b):.2f}", f"{C.auc(a1, b1):.2f} / {C.auc(a2, b2):.2f}"])
    # wewnątrz-chwilowe porównanie: czy jego token wypadł lepiej niż średnia pominiętych z TEJ SAMEJ chwili
    wins = [p[1]["max30"] > C.median([o["max30"] for o in p[2]]) for p in pairs]
    out = [f"# Czy {name} odróżnia trash? Jego wybory vs pominięte równie gorące starty - {time.strftime('%d.%m.%Y %H:%M')}\n",
           f"Jego wejść <= 60 s od startu z porównaniem: {len(pairs)}{C.rel(len(pairs))}; pominiętych tokenów z top {TOP} "
           f"(po kwocie zakupów w 10 s, w tej samej chwili): {sum(len(p[2]) for p in pairs)}. Jego token był nr 1 w "
           f"{sum(p[3] == 1 for p in pairs) / max(len(pairs), 1):.0%} przypadków. Wynik liczony od ceny w chwili jego "
           f"wejścia (to ocena WYBORU, nie jego wykonania).\n",
           C.table(["wynik tokena od chwili T", "jego wybór", f"pominięte z top {TOP}", "AUC (> 0.5 = jego lepsze)",
                    "AUC 1. / 2. połowa"], rows),
           f"\nW tej samej chwili jego token miał większy max wzrost w 30 min niż mediana pominiętych w "
           f"{sum(wins) / max(len(wins), 1):.0%} przypadków (50% = rzut monetą; N {len(wins)})."]
    out.append(idle_top1(st, eps, ids, info, mig, created, cts, tape, his))
    out.append(followers(st, eps, ids, info, tape, wallet=wallet))
    return "\n".join(out)


def summ_out(os: list) -> list:
    return [len(os), C.pct(C.median([o["max5"] for o in os])), C.pct(C.median([o["max30"] for o in os])),
            C.pct(C.median([o["po30"] for o in os])), f"{C.mean([o['pump'] for o in os]):.0%}",
            f"{C.mean([o['rug'] for o in os]):.0%}", f"{C.mean([o['mig30'] for o in os]):.0%}"]


def idle_top1(st, eps, ids, info, mig, created, cts, tape, his, n: int = 250) -> str:
    """Kontrola "mechaniczna": nr 1 gorący start (<= 60 s, kwota zakupów 10 s) w losowych chwilach, gdy był aktywny
    (+-5 min od jego transakcji), ale NIE kupował (+-120 s bez jego transakcji)."""
    import random
    tx = sorted(r["bt"] for e in eps for r in e["legs"])
    rng = random.Random(5)
    res, tries = [], 0
    while len(res) < n and tries < 20 * n and tx:
        tries += 1
        T = rng.choice(tx) + rng.uniform(-300, 300)
        j = bisect.bisect_left(tx, T)
        if any(0 <= i < len(tx) and abs(tx[i] - T) <= 120 for i in (j - 1, j)):
            continue
        best = None
        for c, m in created[bisect.bisect_left(cts, T - 60):bisect.bisect_right(cts, T)]:
            if m in his:
                continue
            tp = tape(m)
            if not tp.slot:
                continue
            cut = S.cut_at(tp, T)
            f = S.entry_feats(tp, cut, T, info[m], set(), None)
            if f and f["kupno_sol_10s"] > 0 and (best is None or f["kupno_sol_10s"] > best[0]):
                best = (f["kupno_sol_10s"], m, cut)
        if best:
            o = outcome(tape(best[1]), best[2], T, mig.get(best[1]))
            if o:
                res.append(o)
    mine = []
    for e in eps:
        mid, leg = ids.get(e["mint"]), e["legs"][0]
        if mid and leg["venue"] == "pump_curve" and info[mid]["created"] and 0 <= leg["bt"] - info[mid]["created"] <= 60:
            o = outcome(tape(mid), leg["slot"], leg["bt"], mig.get(mid))
            if o:
                mine.append(o)
    return ("\n## Czy to tylko \"bierze nr 1\"? Nr 1 gorący start w chwilach, gdy był aktywny, ale nie kupował\n\n" +
            C.table(["", "N", "max 5 min (med.)", "max 30 min (med.)", "cena po 30 min (med.)", "pump", "rug",
                     "migracja 30 min"],
                    [["jego wybory", *summ_out(mine)], ["nr 1 gorący start bez niego", *summ_out(res)]]))


def followers(st, eps, ids, info, tape, min_hits: int = 3, min_lift: float = 20, wallet: str = Q.W) -> str:
    """Naśladowcy: portfele kupujące <= 5 s po nim w >= min_hits jego tokenach, dla których jego tokeny stanowią
    >= min_lift razy większy udział wczesnych zakupów (<= 90 s od startu) niż losowo. Ile SOL wnoszą po jego zakupie."""
    import collections
    me = (st.execute("SELECT id FROM wallets WHERE addr=?", (wallet,)).fetchone() or [None])[0]
    ent = {}
    for e in eps:
        mid, leg = ids.get(e["mint"]), e["legs"][0]
        if mid and leg["venue"] == "pump_curve" and info[mid]["created"] and 0 <= leg["bt"] - info[mid]["created"] <= 60:
            ent[mid] = leg
    after = collections.Counter()
    for mid, leg in ent.items():
        tp = tape(mid)
        k = bisect.bisect_right(tp.slot, leg["slot"])
        for w in {tp.w[i] for i in range(k, len(tp.slot)) if tp.ts[i] <= leg["bt"] + 5 and tp.buy[i] and tp.w[i] != me}:
            after[w] += 1
    cand = [w for w, c in after.items() if c >= min_hits]
    if not cand:
        return "\n(Naśladowców nie znaleziono.)"
    first = collections.defaultdict(set)
    for w, m, t in st.execute(f"SELECT wallet_id, mint_id, MIN(ts) FROM trades WHERE buy=1 AND wallet_id IN "
                              f"({','.join(map(str, cand))}) GROUP BY wallet_id, mint_id"):
        if info.get(m, {}).get("created") and t - info[m]["created"] <= 90:
            first[w].add(m)
    t0, t1 = Q.window()
    base = len(ent) / max(st.execute("SELECT COUNT(*) FROM mints WHERE created_ts BETWEEN ? AND ?", (t0, t1)).fetchone()[0], 1)
    lifts = [(len(first[w] & set(ent)) / len(first[w]) / base, len(first[w] & set(ent)), len(first[w]), w)
             for w in cand if first[w]]
    strong = {x[3] for x in lifts if x[0] >= min_lift}
    sh, tot = [], []
    for mid, leg in ent.items():
        tp = tape(mid)
        k = bisect.bisect_right(tp.slot, leg["slot"])
        idx = [i for i in range(k, len(tp.slot)) if tp.ts[i] <= leg["bt"] + 30 and tp.buy[i] and tp.w[i] != me]
        a = sum(tp.sol[i] for i in idx)
        tot.append(a)
        if a:
            sh.append(sum(tp.sol[i] for i in idx if tp.w[i] in strong) / a)
    top = sorted(lifts, reverse=True)[:5]
    return (f"\n## Naśladowcy (portfele, które kupują sekundy po nim i prawie tylko jego tokeny)\n\n"
            f"Portfeli kupujących <= 5 s po nim w >= {min_hits} jego tokenach: {len(cand)}; z nich {len(strong)} ma jego "
            f"tokeny >= {min_lift:.0f}x częściej wśród swoich wczesnych zakupów niż losowo (baza {base:.3%}). Najbardziej "
            f"wierni: " + "; ".join(f"{h} z {n} wczesnych zakupów to jego tokeny" for _, h, n, _ in top) +
            f". Po jego zakupie inni kupują w 30 s mediana {C.median(tot):.1f} SOL, z czego naśladowcy mediana "
            f"{C.median(sh):.0%} (średnio {C.mean(sh):.0%}). To mogą być boty kopiujące albo jego własne dodatkowe portfele.")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "Cupsey"
    txt = report(name)
    (C.ROOT / "analizy" / f"{name.upper()}_WYBOR.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
