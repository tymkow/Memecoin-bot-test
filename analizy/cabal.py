"""Grupy portfeli kupujących razem ("cabale") - wykrycie na eksploracji i test: czy wejście za grupą po naszym
opóźnieniu zarabia (8.10.2026).

    python -m analizy.cabal        # -> analizy/CABAL.md (tylko stream.db, bez Heliusa)

Tło: trader Trader B (analizy/KOL_trader_B.md) wybierał tokeny lepsze także po 30 min, a sekundy po nim kupowało 46
portfeli prawie tylko jego tokeny; kupował większość startów kilku twórców. Hipoteza: zorganizowane grupy portfeli
wiedzą, który start pójdzie - może da się wejść za nimi.

1. EKSPLORACJA (pierwsze 70% czasu, po chwili utworzenia tokena): pierwsze zakupy portfeli w ciągu 300 s od startu.
   Para portfeli = "razem", gdy kupiły ten sam token w odstępie <= 5 slotów (2 s). Krawędź, gdy razem w >= 5 tokenach
   i w >= 50% tokenów mniej aktywnego z nich. Portfele z < 5 albo > 1500 tokenami (wszystkożerne snajpery) pomijane.
   Grupa = spójna składowa z >= 3 portfelami.
2. SYGNAŁ: w tokenie kupuje M-ty (2 / 3) różny członek tej samej grupy w ciągu 30 s od pierwszego -> chwila T.
3. POZYCJA: wejście 0.25 SOL w T + d (d = 1, 2, 5, 12, 20 s), stan krzywej z ts <= T + d, opłata pump.fun z transakcji
   (copytrade.buy_tokens / sell_sol), 0.0005 SOL za transakcję. Wyjścia: (a) "za grupą" - gdy pierwszy członek grupy
   sprzeda, + d; (b) stały czas 60 s; (c) 300 s; (d) TP +30% / SL -20%; wszystkie max 300 s. Migracja przed wyjściem =
   ostatnia cena krzywej (zaznaczone). Pozycje nachodzące na dziurę strumienia - osobno.
4. WYBÓR grup i wariantu (M, wyjście) WYŁĄCZNIE na eksploracji przy d = 5 s; TEST (ostatnie 30%) liczony raz.
   Porównanie: baseline = wszystkie tokeny w tym samym wieku co sygnał (ten sam d i wyjście), oraz sygnały
   wszystkich grup (bez wyboru).
"""
from __future__ import annotations

import bisect
import collections
import time

from analizy import common as C
from collector import data_holes
from copytrade import buy_tokens, sell_sol

EARLY_S = 300
PAIR_SLOTS = 5
MIN_CO, MIN_SHARE = 5, 0.5
MIN_TOK, MAX_TOK = 5, 1500
MIN_GROUP = 3
SIG_WINDOW = 30
MS = (2, 3)
DELAYS = (1, 2, 5, 12, 20)
SEL_D = 5
EXITS = ("za_grupa", "czas_60s", "czas_300s", "tp30_sl20")
EXIT_NAME = {"za_grupa": "za grupą (1. sprzedaż członka)", "czas_60s": "stały 60 s", "czas_300s": "stały 300 s",
             "tp30_sl20": "TP +30% / SL -20%"}
MAX_HOLD = 300
SIZE, TX = 0.25, 0.0005


def early_buys():
    """{mint_id: [(slot, ts, wallet)]} pierwszych zakupów portfeli w ciągu EARLY_S od utworzenia + czasy utworzenia."""
    st = C.ro("stream.db")
    created = {r[0]: r[1] for r in st.execute("SELECT id, created_ts FROM mints WHERE created_ts IS NOT NULL")}
    out = collections.defaultdict(list)
    seen = set()
    cur = None
    for mid, slot, ts, w in st.execute(
            "SELECT t.mint_id, t.slot, t.ts, t.wallet_id FROM trades t JOIN mints m ON m.id = t.mint_id "
            "WHERE t.buy = 1 AND m.created_ts IS NOT NULL AND t.ts <= m.created_ts + ? ORDER BY t.mint_id, t.slot",
            (EARLY_S,)):
        if mid != cur:
            cur, seen = mid, set()
        if w in seen:
            continue
        seen.add(w)
        out[mid].append((slot, ts, w))
    return out, created


def find_groups(eb: dict, mints: list, with_edges: bool = False):
    """{wallet: id grupy} z tokenów eksploracji (z with_edges: także [(a, b, razem)] krawędzi grupy - do mapy)."""
    n = collections.Counter(w for m in mints for _, _, w in eb[m])
    ok = {w for w, c in n.items() if MIN_TOK <= c <= MAX_TOK}
    pair = collections.Counter()
    for m in mints:
        lst = [(s, w) for s, _, w in eb[m] if w in ok]
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                if lst[j][0] - lst[i][0] > PAIR_SLOTS:
                    break
                a, b = lst[i][1], lst[j][1]
                if a != b:
                    pair[(a, b) if a < b else (b, a)] += 1
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    edges = []
    for (a, b), c in pair.items():
        if c >= MIN_CO and c >= MIN_SHARE * min(n[a], n[b]):
            parent[find(a)] = find(b)
            edges.append((a, b, c))
    comp = collections.defaultdict(list)
    for w in parent:
        comp[find(w)].append(w)
    groups = {}
    for gi, ws in enumerate(sorted((v for v in comp.values() if len(v) >= MIN_GROUP), key=len, reverse=True)):
        for w in ws:
            groups[w] = gi
    return (groups, edges, n) if with_edges else groups


def signals(eb: dict, groups: dict, mints: list) -> list:
    """[(mint, grupa, M, T)] - chwila, gdy M-ty członek grupy kupił w ciągu SIG_WINDOW od pierwszego."""
    out = []
    for m in mints:
        by = collections.defaultdict(list)
        for s, t, w in eb[m]:
            if w in groups:
                by[groups[w]].append(t)
        for g, ts in by.items():
            ts.sort()
            for M in MS:
                if len(ts) >= M and ts[M - 1] - ts[0] <= SIG_WINDOW:
                    out.append((m, g, M, ts[M - 1]))
    return out


def tape(st, mid: int, t_end: float) -> dict:
    tp = {k: [] for k in ("ts", "w", "buy", "vs", "vt", "fee")}
    for ts, w, buy, vsol, vtok, fee in st.execute(
            "SELECT ts, wallet_id, buy, vsol, vtok, fee_bps FROM trades WHERE mint_id=? AND ts <= ? ORDER BY slot",
            (mid, t_end)):
        if not vtok:
            continue
        tp["ts"].append(ts)
        tp["w"].append(w)
        tp["buy"].append(buy)
        tp["vs"].append(float(vsol))
        tp["vt"].append(float(vtok))
        tp["fee"].append(fee or 125)
    return tp


def simulate(tp: dict, T: float, mig, members: set) -> dict:
    """{(d, wyjście): (wynik % stawki, migracja)}."""
    ts, vs, vt, fee = tp["ts"], tp["vs"], tp["vt"], tp["fee"]
    idx = lambda t: bisect.bisect_right(ts, t) - 1                  # noqa: E731
    out = {}

    def pnl(i0, ie):
        tok = buy_tokens(vs[i0], vt[i0], SIZE * 1e9, fee[i0])
        k = vs[ie] * vt[ie]
        vt_r = vt[ie] - tok
        if vt_r <= 0:
            return None
        return (sell_sol(k / vt_r, vt_r, tok, fee[ie]) / 1e9 - 2 * TX - SIZE) / SIZE

    first_sell = next((ts[i] for i in range(len(ts)) if ts[i] > T - SIG_WINDOW and not tp["buy"][i]
                       and tp["w"][i] in members), None)
    for d in DELAYS:
        te = T + d
        if mig is not None and te >= mig:
            continue
        i0 = idx(te)
        if i0 < 0:
            continue
        p0 = vs[i0] / vt[i0]
        for ex in EXITS:
            if ex == "czas_60s":
                tx = te + 60
            elif ex == "czas_300s":
                tx = te + MAX_HOLD
            elif ex == "za_grupa":
                tx = min(max(first_sell + d, te) if first_sell else te + MAX_HOLD, te + MAX_HOLD)
            else:
                tx = te + MAX_HOLD
                for j in range(i0 + 1, len(ts)):
                    if ts[j] > te + MAX_HOLD:
                        break
                    p = vs[j] / vt[j]
                    if p >= 1.3 * p0 or p <= 0.8 * p0:
                        tx = min(ts[j] + d, te + MAX_HOLD)
                        break
            migr = mig is not None and tx >= mig
            ie = idx(mig if migr else tx)
            r = pnl(i0, max(ie, i0))
            if r is not None:
                out[(d, ex)] = (r, migr)
    return out


def summ(xs: list) -> str:
    if not xs:
        return "-"
    lo, hi = C.boot_ci(xs)
    return (f"N {len(xs)}{C.rel(len(xs))}: śr. {C.pct(C.mean(xs))} (CI {lo * 100:+.1f}..{hi * 100:+.1f}), "
            f"med. {C.pct(C.median(xs))}, wygr. {sum(x > 0 for x in xs) / len(xs):.0%}")


def report() -> str:
    st = C.ro("stream.db")
    eb, created = early_buys()
    t0, t1 = st.execute("SELECT MIN(ts), MAX(ts) FROM trades").fetchone()
    mig = dict(st.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind IN ('complete','migrate') GROUP BY mint_id"))
    holes = data_holes(st)
    ha, hb = [a for a, _ in holes], [b for _, b in holes]
    # tokeny z nietypową krzywą (wirtualna rezerwa SOL < 25 SOL; standard ~30) - 0.25 SOL zmienia cenę wielokrotnie,
    # pojedyncze "wyniki" +100 000% - osobna populacja, wykluczona (948 tokenów, 8.10)
    odd = {r[0] for r in st.execute("SELECT DISTINCT mint_id FROM trades WHERE vsol < 25e9")}
    mints = sorted((m for m in eb if created[m] + EARLY_S + MAX_HOLD + 30 <= t1 and m not in odd), key=lambda m: created[m])
    cut = created[mints[int(len(mints) * C.SPLIT)]]
    ex_m = [m for m in mints if created[m] < cut]
    te_m = [m for m in mints if created[m] >= cut]
    groups = find_groups(eb, ex_m)
    gsize = collections.Counter(groups.values())
    members = collections.defaultdict(set)
    for w, g in groups.items():
        members[g].add(w)

    def hole(c, t_end):
        j = bisect.bisect_left(hb, c)
        return j < len(ha) and ha[j] < t_end

    def run(sigs):
        res = []
        for m, g, M, T in sigs:
            r = simulate(tape(st, m, T + 2 * MAX_HOLD + 30), T, mig.get(m), members[g])
            res.append({"m": m, "g": g, "M": M, "T": T, "r": r, "hole": hole(created[m], T + MAX_HOLD + 30)})
        return res

    s_ex = run(signals(eb, groups, ex_m))
    s_te = run(signals(eb, groups, te_m))
    # baseline: wszystkie tokeny w tym samym wieku co sygnał (mediana wieku sygnałów)
    ages = sorted(x["T"] - created[x["m"]] for x in s_ex)
    age = ages[len(ages) // 2] if ages else 10
    base_te = run([(m, -1, 0, created[m] + age) for m in te_m[::max(len(te_m) // 3000, 1)]])
    # wybór na eksploracji (d = SEL_D, bez dziur): wariant (M, wyjście) i grupy ze średnią > 0 przy N >= 5
    best = None
    for M in MS:
        for ex in EXITS:
            xs = [x["r"][(SEL_D, ex)][0] for x in s_ex if x["M"] == M and not x["hole"] and (SEL_D, ex) in x["r"]]
            if len(xs) >= 30 and (best is None or C.mean(xs) > best[2]):
                best = (M, ex, C.mean(xs), len(xs))
    out = [f"# Grupy portfeli kupujących razem - {time.strftime('%d.%m.%Y %H:%M')}\n",
           f"Tokeny z pełnym oknem: {len(mints)} (eksploracja {len(ex_m)}, TEST {len(te_m)} od "
           f"{time.strftime('%d.%m %H:%M', time.localtime(cut))}). Wykryte grupy (eksploracja): {len(gsize)}, portfeli "
           f"w grupach {len(groups)}; rozmiary: największe {sorted(gsize.values(), reverse=True)[:10]}, mediana "
           f"{C.median(list(gsize.values())) if gsize else 0}.\n",
           f"Sygnałów: eksploracja {len(s_ex)}, test {len(s_te)} (tokenów z sygnałem w teście: "
           f"{len({x['m'] for x in s_te})} z {len(te_m)}). Mediana wieku tokena przy sygnale: {age:.0f} s.\n"]
    if not best:
        out.append("Za mało sygnałów na eksploracji (N < 30) - brak wniosku.")
        return "\n".join(out)
    M, ex, _, _ = best
    gstat = collections.defaultdict(list)
    for x in s_ex:
        if x["M"] == M and not x["hole"] and (SEL_D, ex) in x["r"]:
            gstat[x["g"]].append(x["r"][(SEL_D, ex)][0])
    good = {g for g, xs in gstat.items() if len(xs) >= 5 and C.mean(xs) > 0}
    out.append(f"**Wybór na eksploracji (d = {SEL_D} s, bez dziur):** M = {M}, wyjście {EXIT_NAME[ex]}; grup z >= 5 "
               f"sygnałami: {sum(1 for xs in gstat.values() if len(xs) >= 5)}, z nich ze średnią > 0: {len(good)}.\n")
    # tabela: wszystkie warianty na eksploracji (informacyjnie)
    rows = []
    for Mx in MS:
        for e in EXITS:
            rows.append([f"M={Mx}", EXIT_NAME[e], summ([x["r"][(SEL_D, e)][0] for x in s_ex
                                                       if x["M"] == Mx and not x["hole"] and (SEL_D, e) in x["r"]])])
    out += ["## Eksploracja - wszystkie sygnały grup (d = 5 s, bez dziur)\n", C.table(["sygnał", "wyjście", "wynik"], rows)]
    # TEST
    rows = []
    for d in DELAYS:
        sel = [x["r"][(d, ex)][0] for x in s_te if x["M"] == M and x["g"] in good and not x["hole"] and (d, ex) in x["r"]]
        allg = [x["r"][(d, ex)][0] for x in s_te if x["M"] == M and not x["hole"] and (d, ex) in x["r"]]
        base = [x["r"][(d, ex)][0] for x in base_te if not x["hole"] and (d, ex) in x["r"]]
        rows.append([f"{d} s", summ(sel), summ(allg), summ(base)])
    out += [f"\n## TEST (liczony raz): M = {M}, wyjście {EXIT_NAME[ex]}, 0.25 SOL, bez dziur\n",
            C.table(["opóźnienie", f"wybrane grupy ({len(good)})", "wszystkie grupy", f"baseline: każdy token w wieku {age:.0f} s"],
                    rows)]
    sel5 = [x for x in s_te if x["M"] == M and x["g"] in good and (SEL_D, ex) in x["r"]]
    out.append(f"\nTest z dziurami włącznie, d = {SEL_D} s: wybrane grupy {summ([x['r'][(SEL_D, ex)][0] for x in sel5])}; "
               f"z migracją przed wyjściem: {sum(x['r'][(SEL_D, ex)][1] for x in sel5)}.")
    lo = None
    xs = [x["r"][(SEL_D, ex)][0] for x in s_te if x["M"] == M and x["g"] in good and not x["hole"] and (SEL_D, ex) in x["r"]]
    if len(xs) >= 2:
        lo, hi = C.boot_ci(xs)
    verdict = ("**DZIAŁA** (dolna granica CI > 0 przy N >= 30)" if lo is not None and lo > 0 and len(xs) >= C.MIN_N
               else "**nie działa** (CI obejmuje 0, wynik <= 0 albo N < 30)")
    out.append(f"\nWerdykt dla wejścia za wybranymi grupami po {SEL_D} s: {verdict}.")
    return "\n".join(out)


if __name__ == "__main__":
    txt = report()
    (C.ROOT / "analizy" / "CABAL.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
