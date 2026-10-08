"""Reguła "przetrwał start" wyczytana z tradera Bot C (analizy/KOL_bot_C.md): kupuje tokeny ~2-3 min po starcie,
z szeroką bazą posiadaczy i trwającym handlem, trzyma ~60 s; jego tokeny rzadko rugują (1% vs 14%). Czy stosowana przez
nas na WSZYSTKICH startach zarabia po opóźnieniu i kosztach? (8.10.2026)

    python -m analizy.slow_rule        # -> analizy/REGULA_PRZETRWAL.md (tylko stream.db)

Ocena tokena w wieku A (90 / 120 / 180 s), cechy tylko z transakcji przed chwilą A: portfele = różni kupujący od startu,
kup10 = kupujący w ostatnich 10 s, zm = zmiana ceny od wieku A-120 s, cisza = s od ostatniej transakcji. Wejście
0.25 SOL w A + d (d = 2, 5, 12, 20 s), wyjście: stały czas 60 s (jak on) / 300 s / TP +30% SL -20% (max 300 s);
koszty jak w cabal.py (opłata krzywej z transakcji, 0.0005 SOL za transakcję), migracja = ostatnia cena krzywej.
Siatka progów wybierana WYŁĄCZNIE na pierwszych 70% (d = 5 s, bez dziur, N >= 100), test liczony raz; baseline =
wszystkie tokeny żywe w wieku A (handel w ostatnich 30 s). Tokeny z nietypową krzywą (vsol < 25 SOL) wykluczone.
"""
from __future__ import annotations

import bisect
import collections
import itertools
import time

from analizy import common as C
from collector import data_holes
from copytrade import buy_tokens, sell_sol

AGES = (90, 120, 180)
DELAYS = (2, 5, 12, 20)
SEL_D = 5
EXITS = ("czas_60s", "czas_300s", "tp30_sl20")
EXIT_NAME = {"czas_60s": "stały 60 s (jak on)", "czas_300s": "stały 300 s", "tp30_sl20": "TP +30% / SL -20%"}
MAX_HOLD = 300
HORIZON = max(AGES) + max(DELAYS) + MAX_HOLD + 30
SIZE, TX = 0.25, 0.0005
GRID = {"portfele": (20, 40, 60, 100), "kup10": (1, 3, 5), "zm": (None, 0.0, 0.2)}


def feats(tp, T):
    ts = tp["ts"]
    k = bisect.bisect_left(ts, T)
    if k == 0:
        return None
    buyers = {tp["w"][i] for i in range(k) if tp["buy"][i]}
    b10 = {tp["w"][i] for i in range(bisect.bisect_left(ts, T - 10), k) if tp["buy"][i]}
    j = bisect.bisect_right(ts, T - 120) - 1
    p = tp["vs"][k - 1] / tp["vt"][k - 1]
    p0 = tp["vs"][j] / tp["vt"][j] if j >= 0 else tp["vs"][0] / tp["vt"][0]
    return {"portfele": len(buyers), "kup10": len(b10), "zm": p / p0 - 1, "cisza": T - ts[k - 1]}


def sim(tp, te, mig):
    ts, vs, vt, fee = tp["ts"], tp["vs"], tp["vt"], tp["fee"]
    idx = lambda t: bisect.bisect_right(ts, t) - 1                 # noqa: E731
    if mig is not None and te >= mig:
        return {}
    i0 = idx(te)
    if i0 < 0:
        return {}
    p0 = vs[i0] / vt[i0]
    out = {}

    def pnl(ie):
        tok = buy_tokens(vs[i0], vt[i0], SIZE * 1e9, fee[i0])
        k = vs[ie] * vt[ie]
        vt_r = vt[ie] - tok
        return None if vt_r <= 0 else (sell_sol(k / vt_r, vt_r, tok, fee[ie]) / 1e9 - 2 * TX - SIZE) / SIZE
    for ex in EXITS:
        if ex.startswith("czas_"):
            tx = te + int(ex[5:-1])
        else:
            tx = te + MAX_HOLD
            for j in range(i0 + 1, len(ts)):
                if ts[j] > te + MAX_HOLD:
                    break
                if vs[j] / vt[j] >= 1.3 * p0 or vs[j] / vt[j] <= 0.8 * p0:
                    tx = ts[j]
                    break
        out[ex] = tx
    return {ex: (pnl(max(idx(min(tx, mig) if mig else tx), i0)), mig is not None and tx >= mig) for ex, tx in out.items()}


def collect():
    st = C.ro("stream.db")
    t1 = st.execute("SELECT MAX(ts) FROM trades").fetchone()[0]
    info = dict(st.execute("SELECT id, created_ts FROM mints WHERE created_ts IS NOT NULL"))
    mig = dict(st.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind IN ('complete','migrate') GROUP BY mint_id"))
    odd = {r[0] for r in st.execute("SELECT DISTINCT mint_id FROM trades WHERE vsol < 25e9")}
    holes = data_holes(st)
    ha, hb = [a for a, _ in holes], [b for _, b in holes]
    rows = []
    cur, tp = None, None

    def flush():
        if cur is None or cur in odd or not tp["ts"] or info[cur] + HORIZON > t1:
            return
        c = info[cur]
        for A in AGES:
            T = c + A
            f = feats(tp, T)
            if not f or f["cisza"] > 30:
                continue
            j = bisect.bisect_left(hb, c)
            hole = j < len(ha) and ha[j] < T + MAX_HOLD + 30
            r = {d: sim(tp, T + d, mig.get(cur)) for d in DELAYS}
            rows.append({"m": cur, "c": c, "A": A, "f": f, "r": r, "hole": hole})

    for mid, ts, w, buy, vsol, vtok, fee in st.execute(
            "SELECT t.mint_id, t.ts, t.wallet_id, t.buy, t.vsol, t.vtok, t.fee_bps FROM trades t JOIN mints m ON "
            "m.id = t.mint_id WHERE m.created_ts IS NOT NULL AND t.ts <= m.created_ts + ? ORDER BY t.mint_id, t.slot",
            (HORIZON,)):
        if mid != cur:
            flush()
            cur, tp = mid, {k: [] for k in ("ts", "w", "buy", "vs", "vt", "fee")}
        if not vtok:
            continue
        for k, v in (("ts", ts), ("w", w), ("buy", buy), ("vs", float(vsol)), ("vt", float(vtok)), ("fee", fee or 125)):
            tp[k].append(v)
    flush()
    return rows


def ok(f, rule):
    p, k, z = rule
    return f["portfele"] >= p and f["kup10"] >= k and (z is None or f["zm"] >= z)


def summ(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "-"
    lo, hi = C.boot_ci(xs)
    return (f"N {len(xs)}{C.rel(len(xs))}: śr. {C.pct(C.mean(xs))} (CI {lo * 100:+.1f}..{hi * 100:+.1f}), "
            f"med. {C.pct(C.median(xs))}, wygr. {sum(x > 0 for x in xs) / len(xs):.0%}")


def report() -> str:
    rows = collect()
    cs = sorted({r["c"] for r in rows})
    cut = cs[int(len(cs) * C.SPLIT)]
    ex = [r for r in rows if r["c"] < cut]
    te = [r for r in rows if r["c"] >= cut]
    rules = list(itertools.product(GRID["portfele"], GRID["kup10"], GRID["zm"]))
    best = None
    for A in AGES:
        for e in EXITS:
            for rule in rules:
                xs = [r["r"][SEL_D][e][0] for r in ex if r["A"] == A and not r["hole"] and ok(r["f"], rule)
                      and e in r["r"][SEL_D] and r["r"][SEL_D][e][0] is not None]
                if len(xs) >= 100 and (best is None or C.mean(xs) > best[0]):
                    best = (C.mean(xs), A, e, rule, len(xs))
    out = [f"# Reguła \"przetrwał start\" (z tradera Bot C) - {time.strftime('%d.%m.%Y %H:%M')}\n",
           f"Ocen tokenów: {len(rows)} (eksploracja {len(ex)}, TEST {len(te)} od {time.strftime('%d.%m %H:%M', time.localtime(cut))}). "
           f"Siatka: {len(rules)} reguł x {len(AGES)} wieki x {len(EXITS)} wyjścia.\n"]
    pos = sum(1 for A in AGES for e in EXITS for rule in rules
              if (lambda xs: len(xs) >= 100 and C.mean(xs) > 0)([r["r"][SEL_D][e][0] for r in ex if r["A"] == A
                  and not r["hole"] and ok(r["f"], rule) and r["r"][SEL_D].get(e) and r["r"][SEL_D][e][0] is not None]))
    out.append(f"Reguł ze średnią > 0 na eksploracji (N >= 100): {pos} z {len(rules) * len(AGES) * len(EXITS)}.\n")
    if not best:
        return "\n".join(out + ["Brak reguły z N >= 100."])
    _, A, e, rule, n = best
    out.append(f"**Najlepsza na eksploracji:** wiek {A} s, portfele >= {rule[0]}, kupujący w 10 s >= {rule[1]}, "
               f"zmiana ceny 2 min >= {rule[2] if rule[2] is not None else '-'}, wyjście {EXIT_NAME[e]} "
               f"(eksploracja N {n}, śr. {C.pct(best[0])}).\n")
    tab = []
    for d in DELAYS:
        sel = [r["r"][d][e][0] for r in te if r["A"] == A and not r["hole"] and ok(r["f"], rule) and r["r"][d].get(e)]
        base = [r["r"][d][e][0] for r in te if r["A"] == A and not r["hole"] and r["r"][d].get(e)]
        tab.append([f"{d} s", summ(sel), summ(base)])
    out += ["## TEST (liczony raz, bez dziur, 0.25 SOL)\n",
            C.table(["opóźnienie", "reguła", f"baseline: każdy żywy token w wieku {A} s"], tab)]
    sel = [r for r in te if r["A"] == A and ok(r["f"], rule) and r["r"][SEL_D].get(e)]
    out.append(f"\nZ dziurami, d = {SEL_D} s: {summ([r['r'][SEL_D][e][0] for r in sel])}; migracja przed wyjściem: "
               f"{sum(1 for r in sel if r['r'][SEL_D][e][1])}.")
    xs = [r["r"][SEL_D][e][0] for r in te if r["A"] == A and not r["hole"] and ok(r["f"], rule) and r["r"][SEL_D].get(e)]
    xs = [x for x in xs if x is not None]
    lo = C.boot_ci(xs)[0] if len(xs) > 1 else None
    out.append(f"\nWerdykt (d = {SEL_D} s): " + ("**DZIAŁA** (dolna granica CI > 0, N >= 30)" if lo and lo > 0 and len(xs) >= 30
                                               else "**nie działa** (CI obejmuje 0 albo wynik <= 0)") + ".")
    return "\n".join(out)


if __name__ == "__main__":
    txt = report()
    (C.ROOT / "analizy" / "REGULA_PRZETRWAL.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
