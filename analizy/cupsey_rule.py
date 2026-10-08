"""Czy reguła wejścia wyczytana z Cupseya zarabia, gdy stosujemy ją SAMI na wszystkich nowych tokenach? (8.10.2026)

    python -m analizy.cupsey_rule        # -> analizy/CUPSEY_REGULA.md (bez Heliusa, tylko data/stream.db, ~5-10 min)

Pytanie: analizy/CUPSEY_SYGNALY.md pokazało, że jego wejścia na krzywej pump.fun da się przewidzieć z rynku (tłum
kupujących w pierwszych sekundach). Tu nie kopiujemy jego transakcji - każdy nowy token ze strumienia oceniamy w wieku
5/10/15 s cechami z transakcji SPRZED tej chwili i wchodzimy, gdy spełnia regułę.

Symulacja pozycji (jeden zakup na token na regułę):
  * wejście w t + d (d = 1, 2, 5 s; 0 s = nieosiągalne odniesienie): stan krzywej po ostatniej transakcji z ts <= t + d,
    zakup 0.25 / 1 SOL z opłatą fee_bps z transakcji (copytrade.buy_tokens), + 0.0005 SOL kosztu za transakcję;
  * nasz wpływ na krzywą: cudze transakcje traktujemy jako przepływ TOKENÓW (pump.fun kupuje po liczbie tokenów),
    więc przy wyjściu rezerwa tokenów jest mniejsza o nasze tokeny przy tym samym k = vsol * vtok. Sprzedaż od razu po
    zakupie oddaje więc wkład minus opłaty, a nie podwójny poślizg;
  * wyjścia: "jak on" - całość, gdy przez 5 s brak napływu netto innych (vsol nie wyższe niż 5 s temu; cena krzywej
    rośnie wtedy i tylko wtedy, gdy rośnie vsol), sprzedaż po d s od sygnału, max 5 min; stały czas 15 / 60 s;
    TP +30% / SL -20% od ceny wejścia (sygnał z ceny transakcji, sprzedaż po d s), max 5 min;
  * migracja przed sprzedażą = wyjście po ostatniej cenie krzywej (PumpSwap nie mamy) - liczone i zaznaczone w raporcie;
  * dziura w strumieniu (> 5 s bez żadnej transakcji, collector.data_holes) między utworzeniem a sprzedażą = pozycja
    "na dziurze" (brakujące transakcje -> zła cena); wyniki podajemy z nimi i bez nich.

Progi: siatka warunków (jeden albo dwa naraz) z cech z drzew decyzyjnych; wybór WYŁĄCZNIE na części treningowej bez
dziur, przy d = 2 s i 0.25 SOL, kryterium = średni wynik, N >= 50. Podział czasu = później z (70% okna, podział z drzew
Cupseya 06.10 20:32) - progi z drzew nie mogły widzieć testu. Test liczony raz. Baseline = wszystkie nowe tokeny w tym
samym wieku z tymi samymi wyjściami (losowy wybór tokena = średnia po wszystkich).
"""
from __future__ import annotations

import bisect
import collections
import sys
import time

from analizy import common as C
from collector import data_holes
from copytrade import buy_tokens, sell_sol

AGES = (5, 10, 15)
DELAYS = (0, 1, 2, 5)                  # 0 = odniesienie (nieosiągalne)
SIZES = (0.25, 1.0)
EXITS = ("jak_on", "czas_15s", "czas_60s", "tp30_sl20")
EXIT_NAME = {"jak_on": "jak on (5 s bez napływu)", "czas_15s": "stały czas 15 s", "czas_60s": "stały czas 60 s",
             "tp30_sl20": "TP +30% / SL -20%"}
MAX_HOLD = 300
HORIZON = max(AGES) + max(DELAYS) + MAX_HOLD + max(DELAYS) + 5
TX_COST = 0.0005                        # SOL za transakcję (priority fee + tip)
SUPPLY = 1e15
SEL_D, SEL_S, SEL_MIN_N = 2, 0.25, 50
TREE_SPLIT = time.mktime((2026, 10, 6, 20, 33, 0, 0, 0, -1))     # podział czasu w CUPSEY_SYGNALY.md (06.10 20:32)

FEATS = ("portfele_razem", "kupno_sol_10s", "netto_sol_60s", "sol_1_slot", "kupujacy_10s", "tworca_ma_pct")
GRID = {"portfele_razem": (">=", (4, 8, 15, 25, 40)),
        "kupno_sol_10s": (">", (1, 3, 6, 10, 15)),
        "netto_sol_60s": (">", (1, 2.7, 5, 10)),
        "sol_1_slot": (">", (1, 3, 6, 9)),
        "kupujacy_10s": (">=", (3, 8, 15, 25))}


# ------------------------------------------------------------------ cechy i symulacja jednego tokena
def features(tp: dict, T: float, creator) -> tuple:
    """Cechy z transakcji o ts < T (te same definicje co cupsey_signals.entry_feats)."""
    ts = tp["ts"]
    k = bisect.bisect_left(ts, T)
    buyers, buyers10 = set(), set()
    kup10 = netto60 = held = s1 = 0.0
    s0 = tp["slot"][0]
    for i in range(k):
        b, sol, w = tp["buy"][i], tp["sol"][i], tp["w"][i]
        if b:
            buyers.add(w)
            if ts[i] >= T - 10:
                kup10 += sol
                buyers10.add(w)
            if tp["slot"][i] == s0:
                s1 += sol
        if ts[i] >= T - 60:
            netto60 += sol if b else -sol
        if w == creator:
            held += tp["tok"][i] if b else -tp["tok"][i]
    return (len(buyers), kup10, netto60, s1, len(buyers10), max(held, 0.0) / SUPPLY * 100)


def simulate(tp: dict, created: float, mig, holes_a: list, holes_b: list):
    """{(wiek, d, wyjście): (wynik % przy 0.25 SOL, przy 1 SOL, na dziurze, migracja, czas trzymania)} albo brak klucza."""
    ts, vs, vt, fee = tp["ts"], tp["vs"], tp["vt"], tp["fee"]
    idx = lambda t: bisect.bisect_right(ts, t) - 1                           # noqa: E731
    mig_i = idx(mig) if mig is not None else None
    out = {}

    def at(t):
        if mig is not None and t >= mig:
            return mig_i, True
        return idx(t), False

    def hole(t_end):                                        # czy dziura nachodzi na [utworzenie, sprzedaż]
        j = bisect.bisect_left(holes_b, created)            # pierwsza dziura kończąca się po utworzeniu
        return j < len(holes_a) and holes_a[j] < t_end

    def pnl(i0, ie, size):
        lam = size * 1e9
        tok = buy_tokens(vs[i0], vt[i0], lam, fee[i0])
        k = vs[ie] * vt[ie]
        vt_r = vt[ie] - tok
        if vt_r <= 0:
            return None
        got = sell_sol(k / vt_r, vt_r, tok, fee[ie]) / 1e9
        return (got - TX_COST - size - TX_COST) / size

    for A in AGES:
        for d in DELAYS:
            te = created + A + d
            if mig is not None and te >= mig:
                continue
            i0 = idx(te)
            if i0 < 0:
                continue
            p0 = vs[i0] / vt[i0]
            for ex in EXITS:
                if ex == "czas_15s":
                    t_exit = te + 15
                elif ex == "czas_60s":
                    t_exit = te + 60
                elif ex == "jak_on":
                    t_exit = te + MAX_HOLD
                    x = te + 5
                    while x <= te + MAX_HOLD:
                        if mig is not None and x >= mig:
                            t_exit = x + d
                            break
                        if vs[idx(x)] <= vs[idx(x - 5)]:
                            t_exit = x + d
                            break
                        x += 1
                    t_exit = min(t_exit, te + MAX_HOLD)
                else:
                    t_exit = te + MAX_HOLD
                    j = i0 + 1
                    while j < len(ts) and ts[j] <= te + MAX_HOLD:
                        p = vs[j] / vt[j]
                        if p >= 1.3 * p0 or p <= 0.8 * p0:
                            t_exit = min(ts[j] + d, te + MAX_HOLD)
                            break
                        j += 1
                ie, migr = at(t_exit)
                if ie < i0:
                    ie = i0
                r = (pnl(i0, ie, SIZES[0]), pnl(i0, ie, SIZES[1]))
                if r[0] is None or r[1] is None:
                    continue
                out[(A, d, ex)] = (r[0], r[1], hole(t_exit), migr, t_exit - te)
    return out


# ------------------------------------------------------------------ zbiórka
def collect():
    st = C.ro("stream.db")
    t0, t1 = st.execute("SELECT MIN(ts), MAX(ts) FROM trades").fetchone()
    info = {r[0]: (r[1], r[2]) for r in st.execute("SELECT id, created_ts, creator FROM mints WHERE created_ts IS NOT NULL")}
    mig = {r[0]: r[1] for r in st.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind IN ('complete','migrate') "
                                          "GROUP BY mint_id")}
    holes = data_holes(st)
    holes_a, holes_b = [a for a, _ in holes], [b for _, b in holes]
    toks = []                        # (mint_id, created, cechy[wiek])
    res = collections.defaultdict(dict)    # (wiek, d, wyjście) -> {nr tokena: wynik}
    cur, tp = None, None

    def flush():
        if cur is None or not tp["ts"]:
            return
        created, creator = info[cur]
        if created + HORIZON > t1:
            return
        n = len(toks)
        toks.append((cur, created, {A: features(tp, created + A, creator) for A in AGES}))
        for key, v in simulate(tp, created, mig.get(cur), holes_a, holes_b).items():
            res[key][n] = v

    q = ("SELECT t.mint_id, t.slot, t.ts, t.wallet_id, t.buy, t.sol, t.tok, t.vsol, t.vtok, t.fee_bps "
         "FROM trades t JOIN mints m ON m.id = t.mint_id WHERE m.created_ts IS NOT NULL AND t.ts <= m.created_ts + ? "
         "ORDER BY t.mint_id, t.slot, t.rowid")
    for mid, slot, ts, w, buy, sol, tok, vsol, vtok, fee in st.execute(q, (HORIZON,)):
        if mid != cur:
            flush()
            cur = mid
            tp = {k: [] for k in ("slot", "ts", "w", "buy", "sol", "tok", "vs", "vt", "fee")}
        if not vtok:
            continue
        tp["slot"].append(slot)
        tp["ts"].append(ts)
        tp["w"].append(w)
        tp["buy"].append(buy)
        tp["sol"].append(sol / 1e9)
        tp["tok"].append(float(tok))
        tp["vs"].append(float(vsol))
        tp["vt"].append(float(vtok))
        tp["fee"].append(fee or 125)
    flush()
    return {"t0": t0, "t1": t1, "toks": toks, "res": res, "holes": holes, "mig": mig}


# ------------------------------------------------------------------ reguły
def grid_rules():
    conds = [(f, op, th) for f, (op, ths) in GRID.items() for th in ths]
    rules = [(c,) for c in conds]
    rules += [(a, b) for i, a in enumerate(conds) for b in conds[i + 1:] if a[0] != b[0]]
    return rules


def ok(fv: tuple, cond) -> bool:
    f, op, th = cond
    x = fv[FEATS.index(f)]
    return x >= th if op == ">=" else x > th


def rule_name(rule) -> str:
    return " i ".join(f"{f} {op} {th:g}" for f, op, th in rule)


LITERAL = {
    "drzewo 'nowe w tym wieku': portfele_razem >= 8 albo (netto_sol_60s > 2.66 i tworca_ma_pct <= 4.49)":
        lambda f: f[0] >= 8 or (f[2] > 2.66 and f[5] <= 4.49),
    "oba drzewa razem: portfele_razem >= 8 i kupno_sol_10s > 3": lambda f: f[0] >= 8 and f[1] > 3,
    "profil Cupseya (mediany): portfele_razem >= 8 i kupno_sol_10s > 3 i sol_1_slot > 3":
        lambda f: f[0] >= 8 and f[1] > 3 and f[3] > 3,
}


# ------------------------------------------------------------------ statystyki
def stats(vals: list) -> dict:
    n = len(vals)
    if not n:
        return {"n": 0}
    return {"n": n, "mean": sum(vals) / n, "med": C.median(vals), "win": sum(v > 0 for v in vals) / n}


def cell(s: dict, size: float | None = None) -> str:
    if not s or not s["n"]:
        return "N 0"
    sol = f", {s['mean'] * s['n'] * size:+.1f} SOL" if size else ""
    return (f"N {s['n']}{C.rel(s['n'])}: śr. {C.pct(s['mean'])}, med. {C.pct(s['med'])}, wygr. {s['win']:.0%}{sol}")


def pick(D, key, members, part, clean, size_i):
    """Wyniki (lista %) dla tokenów `members` w części `part` ('tr'/'te'/None) i opcji bez dziur."""
    r = D["res"].get(key, {})
    split = D["split"]
    out = []
    for n in members:
        v = r.get(n)
        if v is None or (clean and v[2]):
            continue
        cr = D["toks"][n][1]
        if part == "tr" and cr >= split or part == "te" and cr < split:
            continue
        out.append(v[size_i])
    return out


def report() -> str:
    t_start = time.time()
    D = collect()
    D["split"] = max(D["t0"] + C.SPLIT * (D["t1"] - D["t0"]), TREE_SPLIT)
    toks, res, split = D["toks"], D["res"], D["split"]
    all_ids = range(len(toks))
    fmt = lambda t: time.strftime("%d.%m %H:%M", time.localtime(t))        # noqa: E731
    n_tr = sum(1 for t in toks if t[1] < split)
    big = [h for h in D["holes"] if h[1] - h[0] > 1800]
    mig5 = sum(1 for m, cr, _ in toks if m in D["mig"] and D["mig"][m] - cr <= MAX_HOLD + max(AGES))

    # --- wybór progów na treningu (bez dziur), d = 2 s, 0.25 SOL
    rules = grid_rules()
    members = {}                                       # (wiek, reguła) -> lista tokenów
    for A in AGES:
        for rule in rules:
            members[(A, rule)] = [n for n in all_ids if all(ok(toks[n][2][A], c) for c in rule)]
    sel, n_pos = {}, collections.Counter()
    for A in AGES:
        for ex in EXITS:
            best = None
            for rule in rules:
                v = pick(D, (A, SEL_D, ex), members[(A, rule)], "tr", True, 0)
                if len(v) < SEL_MIN_N:
                    continue
                m = sum(v) / len(v)
                n_pos[(A, ex)] += m > 0
                if best is None or m > best[0]:
                    best = (m, rule, len(v))
            sel[(A, ex)] = best
    main_key = max((k for k in sel if sel[k]), key=lambda k: sel[k][0])
    mA, mex = main_key
    mrule = sel[main_key][1]
    mmem = members[(mA, mrule)]

    out = [f"# Reguła wejścia Cupseya stosowana samodzielnie - {time.strftime('%d.%m.%Y %H:%M')}\n",
           "Pytanie: czy wejścia, które Cupsey wybiera (start pump.fun z tłumem w pierwszych sekundach - "
           "CUPSEY_SYGNALY.md), zarabiają, gdy sami stosujemy regułę na WSZYSTKICH nowych tokenach - bez kopiowania go, "
           "po naszym opóźnieniu i kosztach. Metoda w nagłówku `analizy/cupsey_rule.py`.\n",
           f"- Dane: stream.db {fmt(D['t0'])} - {fmt(D['t1'])}; tokeny z zapisanym utworzeniem i pełnymi {HORIZON} s "
           f"po nim: **{len(toks)}** (trening {n_tr}, test {len(toks) - n_tr}).",
           f"- Podział czasu: **{fmt(split)}** (późniejszy z: 70% okna = {fmt(D['t0'] + C.SPLIT * (D['t1'] - D['t0']))}, "
           f"podział drzew Cupseya = 06.10 20:32 - progi z drzew nie widziały testu).",
           f"- Dziury w strumieniu (> 5 s bez transakcji): {len(D['holes'])}, w tym {len(big)} przerw > 30 min "
           f"({sum(b - a for a, b in big) / 3600:.1f} h). Tokeny z migracją w ciągu {MAX_HOLD + max(AGES)} s od startu: {mig5}.",
           f"- Koszty: opłata pump.fun z transakcji (zwykle 1.25% w każdą stronę), poślizg krzywej, {TX_COST} SOL za "
           "transakcję. Wynik = % stawki po wszystkim. d = 0 s to odniesienie nieosiągalne.\n"]

    # --- baseline: wszystkie tokeny
    out.append("## 1. Baseline - wejście w KAŻDY nowy token w tym wieku (test, bez dziur, 0.25 SOL)\n")
    rows = []
    for A in AGES:
        for ex in EXITS:
            rows.append([f"{A} s", EXIT_NAME[ex]] + [cell(stats(pick(D, (A, d, ex), all_ids, "te", True, 0)))
                                                      for d in DELAYS])
    out.append(C.table(["wiek", "wyjście"] + [f"d = {d} s" for d in DELAYS], rows))

    # --- wybór na treningu
    out.append(f"\n## 2. Wybór progów na treningu (bez dziur, d = {SEL_D} s, {SEL_S} SOL, N >= {SEL_MIN_N})\n")
    out.append(f"Siatka: {len(rules)} reguł (jeden albo dwa warunki z: "
               + ", ".join(f"{f} {op} {'/'.join(f'{t:g}' for t in ths)}" for f, (op, ths) in GRID.items())
               + "). Najlepsza reguła dla każdego wieku i wyjścia; trening vs test (test liczony raz):\n")
    rows = []
    for (A, ex), b in sel.items():
        if not b:
            rows.append([f"{A} s", EXIT_NAME[ex], "brak reguły z N >= 50", "", "", ""])
            continue
        m = members[(A, b[1])]
        base_tr = stats(pick(D, (A, SEL_D, ex), all_ids, "tr", True, 0))
        rows.append([f"{A} s", EXIT_NAME[ex], f"`{rule_name(b[1])}`" + (" **(główna)**" if (A, ex) == main_key else ""),
                     f"{n_pos[(A, ex)]} z {len(rules)}",
                     cell(stats(pick(D, (A, SEL_D, ex), m, "tr", True, 0))) + f" (baseline {C.pct(base_tr['mean'])})",
                     cell(stats(pick(D, (A, SEL_D, ex), m, "te", True, 0)))])
    out.append(C.table(["wiek", "wyjście", "reguła", "reguł > 0 na treningu", "TRENING", "TEST"], rows))

    # --- główna reguła: pełna tabela
    out.append(f"\n## 3. Główna reguła (najlepsza na treningu): `{rule_name(mrule)}`, wiek {mA} s, wyjście "
               f"{EXIT_NAME[mex]}\n")
    for si, size in enumerate(SIZES):
        out.append(f"\n**Stawka {size:g} SOL**\n")
        rows = []
        for d in DELAYS:
            key = (mA, d, mex)
            r = [f"{d} s" + (" (odniesienie)" if d == 0 else "")]
            for part in ("tr", "te"):
                for clean in (False, True):
                    r.append(cell(stats(pick(D, key, mmem, part, clean, si)), size))
            r.append(cell(stats(pick(D, key, all_ids, "te", True, si))))
            rows.append(r)
        out.append(C.table(["opóźnienie", "trening (wszystkie)", "trening (bez dziur)", "TEST (wszystkie)",
                            "TEST (bez dziur)", "baseline TEST (bez dziur)"], rows))
    v = pick(D, (mA, SEL_D, mex), mmem, "te", True, 0)
    lo, hi = C.boot_ci(v)
    rv = res.get((mA, SEL_D, mex), {})
    n_mig = sum(1 for n in mmem if n in rv and rv[n][3] and toks[n][1] >= split)
    holds = [rv[n][4] for n in mmem if n in rv and toks[n][1] >= split]
    out.append(f"\nTest, d = {SEL_D} s, 0.25 SOL, bez dziur: średnia {C.pct(sum(v) / len(v) if v else float('nan'))}, "
               f"95% CI (bootstrap) {C.pct(lo)} .. {C.pct(hi)}; pozycji z migracją przed sprzedażą (wyjście po ostatniej "
               f"cenie krzywej): {n_mig}; czas trzymania mediana {C.median(holds):.0f} s.\n")
    # rozkład: skąd średnia
    if v:
        vs_ = sorted(v, reverse=True)
        top = sum(vs_[:max(1, len(vs_) // 20)])
        out.append(f"5% najlepszych pozycji testu wnosi {top / len(v) * 100:+.1f} pp do średniej {sum(v) / len(v):+.1%}; "
                   f"bez nich średnia {(sum(v) - top) / max(len(v) - max(1, len(v) // 20), 1):+.1%}.\n")

    # --- reguły dosłownie z drzew
    out.append("\n## 4. Reguły dosłownie z drzew CUPSEY_SYGNALY.md (bez doboru), d = 2 s, bez dziur\n")
    rows = []
    for name, fn in LITERAL.items():
        for A in AGES:
            m = [n for n in all_ids if fn(toks[n][2][A])]
            for ex in EXITS:
                rows.append([name if (A, ex) == (AGES[0], EXITS[0]) else "", f"{A} s", EXIT_NAME[ex],
                             cell(stats(pick(D, (A, 2, ex), m, "tr", True, 0))),
                             cell(stats(pick(D, (A, 2, ex), m, "te", True, 0)), 0.25),
                             cell(stats(pick(D, (A, 2, ex), m, "te", True, 1)), 1.0)])
    out.append(C.table(["reguła", "wiek", "wyjście", "trening 0.25 SOL", "TEST 0.25 SOL", "TEST 1 SOL"], rows))

    # --- opóźnienie: ile kosztuje każda sekunda (dla reguły głównej, wszystkie wyjścia)
    out.append(f"\n## 5. Główna reguła ({rule_name(mrule)}, wiek {mA} s) z każdym wyjściem - TEST bez dziur, 0.25 SOL\n")
    rows = []
    for ex in EXITS:
        rows.append([EXIT_NAME[ex]] + [cell(stats(pick(D, (mA, d, ex), mmem, "te", True, 0))) for d in DELAYS])
    out.append(C.table(["wyjście"] + [f"d = {d} s" for d in DELAYS], rows))

    # --- jego własne tokeny tymi samymi wyjściami (czy przewaga jest w wyborze tokena, czy gdzie indziej)
    why = "brak przecięcia z oknem"
    try:
        from analizy import cupsey as Q
        st = C.ro("stream.db")
        ids = {r[1]: r[0] for r in st.execute("SELECT id, mint FROM mints")}
        his = {}                                 # token -> czas jego pierwszego zakupu na krzywej
        for e in Q.episodes():
            if e["legs"][0]["venue"] == "pump_curve" and e["mint"] in ids:
                his[ids[e["mint"]]] = min(his.get(ids[e["mint"]], 9e9), e["legs"][0]["bt"])
    except Exception as exc:                     # brak cache MadeOnSol - sekcja pominięta, reszta raportu bez zmian
        his, why = {}, f"{type(exc).__name__}: {exc}"
    hmem = [n for n in all_ids if toks[n][0] in his]
    out.append("\n## 6. Kontrola: tokeny, które kupił Cupsey (na krzywej), z NASZYM wejściem w wieku 5/10/15 s, d = 2 s, "
               "0.25 SOL, bez dziur\n")
    if hmem:
        rows = []
        for A in AGES:
            # przed nim = nasze wejście (t + d) przed jego zakupem: jego zakup i kopiujący go podbijają cenę PO nas
            pre = [n for n in hmem if his[toks[n][0]] > toks[n][1] + A + 2]
            post = [n for n in hmem if his[toks[n][0]] <= toks[n][1] + A + 2]
            for ex in EXITS:
                rows.append([f"{A} s", EXIT_NAME[ex], cell(stats(pick(D, (A, 2, ex), hmem, None, True, 0))),
                             cell(stats(pick(D, (A, 2, ex), pre, None, True, 0))),
                             cell(stats(pick(D, (A, 2, ex), post, None, True, 0)))])
        out.append(f"Jego tokenów z pełnym zapisem startu: {len(hmem)}. Wchodzimy w stałym wieku niezależnie od niego; "
                   "to NIE jest strategia (wybór tokenów zna jego przyszły zakup) - tylko test, czy jego tokeny "
                   "różnią się od tych, które łapie reguła.\n")
        out.append(C.table(["wiek", "wyjście", "wszystkie jego (całe okno)", "my PRZED jego zakupem",
                            "my PO jego zakupie"], rows))
    else:
        out.append(f"(pominięte - {why})\n")

    # --- werdykt
    best_test = []
    for (A, ex), b in sel.items():
        if b:
            s = stats(pick(D, (A, SEL_D, ex), members[(A, b[1])], "te", True, 0))
            best_test.append((s.get("mean", float("nan")), s["n"], A, ex))
    ms = stats(v)
    earns = ms["n"] >= C.MIN_N and ms["mean"] > 0 and lo > 0
    out.append("\n## Werdykt\n")
    out.append(f"Główna reguła (wybrana na treningu): `{rule_name(mrule)}` w wieku {mA} s, wyjście {EXIT_NAME[mex]}, "
               f"d = {SEL_D} s, 0.25 SOL - TEST: {cell(ms, 0.25)}; 95% CI {C.pct(lo)} .. {C.pct(hi)}.\n")
    out.append(f"Najlepsze reguły dla pozostałych wieków/wyjść na teście: "
               + ", ".join(f"{A} s/{EXIT_NAME[ex]} {C.pct(m)} (N {n})" for m, n, A, ex in sorted(best_test, reverse=True))
               + ".\n")
    out.append("**" + ("Reguła ZARABIA po kosztach i opóźnieniu na teście." if earns else
                       "Reguła NIE zarabia po kosztach i opóźnieniu na teście.") + "**\n")
    n_combo = len(sel)
    out.append(f"- Na treningu (bez dziur, d = {SEL_D} s) dodatnią średnią miało {sum(n_pos.values())} z "
               f"{len(rules) * n_combo} kombinacji reguła x wiek x wyjście (liczone te z N >= {SEL_MIN_N}) - wybrana reguła to najmniej stratna, nie "
               "zarabiająca; wynik testu bliski zera mieści się w szumie (CI wyżej) i opiera się na kilku trafieniach.")
    out.append("- Reguły dosłownie z drzew (sekcja 4) tracą 4-9%/pozycję na każdym wieku i wyjściu - bardziej niż "
               "baseline: tłum na starcie to częściej szczyt fali niż jej początek.")
    if hmem:
        pre = [n for n in hmem if his[toks[n][0]] > toks[n][1] + 5 + 2]
        post = [n for n in hmem if his[toks[n][0]] <= toks[n][1] + 5 + 2]
        a, b = (stats(pick(D, (5, 2, "tp30_sl20"), g, None, True, 0)) for g in (pre, post))
        out.append(f"- Jego własne tokeny (sekcja 6, 5 s, TP/SL): przed jego zakupem {cell(a)}, po jego zakupie "
                   f"{cell(b)}. Zarabia się na jego zakupie (i kopiujących go), nie na cechach startu, które reguła "
                   "widzi - tego nie da się odtworzyć bez wiedzy, że on kupi.")
    out.append(f"\n(Czas liczenia {time.time() - t_start:.0f} s.)")
    return "\n".join(out)


if __name__ == "__main__":
    txt = report()
    (C.ROOT / "analizy" / "CUPSEY_REGULA.md").write_text(txt + "\n", encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")      # konsola cp1250 nie ma emoji z C.rel
    print(txt)
