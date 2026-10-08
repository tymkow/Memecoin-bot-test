"""Ranking "nr 1 w tej sekundzie" - czy wejście w start, który właśnie został najgorętszy, zarabia (8.10.2026).

    python -m analizy.top1        # -> analizy/NR1.md (tylko stream.db)

Trader Bot D (KOL_bot_D.md) wchodzi ~40 s po starcie w start nr 1 po napływie i trzyma dokładnie 21 s, zarabia
~+3.8%/poz.; odtworzenie progami cech dawało -2.8% przy d = 0 (REGULA_21S.md). Tu sam ranking:
  * co sekundę: tokeny w wieku AGE_LO..AGE_HI s, kwota zakupów (SOL) z ostatnich 10 s z transakcji do końca tej
    sekundy; nr 1 = największa kwota (>= MIN_SOL); sygnał, gdy token STAJE SIĘ nr 1 (sekundę wcześniej nie był);
  * wejście 0.25 SOL po d s od końca sekundy sygnału (d = 0 = natychmiast, jak najszybszy bot; 1, 2, 5 s), wyjście po
    21 s (jak on) / 60 s; koszty jak slow_rule.py (opłata krzywej z transakcji, 0.0005 SOL / transakcję);
  * wybór progu (wiek, MIN_SOL, kupujący w 10 s) WYŁĄCZNIE na 70% czasu przy d = 0, test raz;
  * porównanie z jego faktycznymi wejściami: ile jego wejść pokrywa się z naszymi sygnałami (ten sam token, <= 5 s).
"""
from __future__ import annotations

import bisect
import collections
import itertools
import time

from analizy import common as C
from analizy import kol
from collector import data_holes
from copytrade import buy_tokens, sell_sol

TRADER = "PODAJ_ADRES_PORTFELA"
SPAN = 160
DELAYS = (0, 1, 2, 5)
HOLDS = (21, 60)
GRID = {"age": ((10, 60), (20, 90), (30, 120)), "min_sol": (3, 6, 10), "min_b10": (5, 10, 16)}
SIZE, TX = 0.25, 0.0005


def load():
    st = C.ro("stream.db")
    created = dict(st.execute("SELECT id, created_ts FROM mints WHERE created_ts IS NOT NULL"))
    odd = {r[0] for r in st.execute("SELECT DISTINCT mint_id FROM trades WHERE vsol < 25e9")}
    T = collections.defaultdict(lambda: {k: [] for k in ("ts", "w", "buy", "sol", "vs", "vt", "fee")})
    for mid, ts, w, buy, sol, vsol, vtok, fee in st.execute(
            "SELECT t.mint_id, t.ts, t.wallet_id, t.buy, t.sol, t.vsol, t.vtok, t.fee_bps FROM trades t JOIN mints m "
            "ON m.id = t.mint_id WHERE m.created_ts IS NOT NULL AND t.ts <= m.created_ts + ? ORDER BY t.mint_id, t.slot",
            (SPAN,)):
        if mid in odd or not vtok:
            continue
        tp = T[mid]
        tp["ts"].append(ts)
        tp["w"].append(w)
        tp["buy"].append(buy)
        tp["sol"].append(sol / 1e9 if buy else 0.0)
        tp["vs"].append(float(vsol))
        tp["vt"].append(float(vtok))
        tp["fee"].append(fee or 125)
    for tp in T.values():
        acc, s = [], 0.0
        for x in tp["sol"]:
            s += x
            acc.append(s)
        tp["cum"] = acc
    holes = data_holes(st)
    t1 = st.execute("SELECT MAX(ts) FROM trades").fetchone()[0]
    return T, created, holes, t1, st


def _unused_buy10(tp, t):
    """Kwota zakupów i liczba kupujących w (t-10, t] (transakcje z ts <= t)."""
    k = bisect.bisect_right(tp["ts"], t)
    a = bisect.bisect_right(tp["ts"], t - 10)
    if k <= a:
        return 0.0, 0
    s = tp["cum"][k - 1] - (tp["cum"][a - 1] if a else 0.0)
    return s, len({tp["w"][i] for i in range(a, k) if tp["buy"][i]})


def pnl(tp, te, hold):
    ts, vs, vt, fee = tp["ts"], tp["vs"], tp["vt"], tp["fee"]
    i0 = bisect.bisect_right(ts, te) - 1
    ie = bisect.bisect_right(ts, te + hold) - 1
    if i0 < 0 or ts[-1] < te + hold - 5 and ie == len(ts) - 1 and ts[-1] < te:
        return None
    tok = buy_tokens(vs[i0], vt[i0], SIZE * 1e9, fee[i0])
    k = vs[ie] * vt[ie]
    vt_r = vt[ie] - tok
    if vt_r <= 0:
        return None
    return (sell_sol(k / vt_r, vt_r, tok, fee[ie]) / 1e9 - 2 * TX - SIZE) / SIZE


def snapshots(T, created):
    """{sekunda: [(zakupy SOL 10 s, kupujący 10 s, wiek, token)]} dla tokenów w wieku 10..120 s - raz dla wszystkich
    wariantów (okno przesuwne po transakcjach tokena)."""
    snap = collections.defaultdict(list)
    for m, tp in T.items():
        c = created[m]
        ts, w, buy, sol = tp["ts"], tp["w"], tp["buy"], tp["sol"]
        a = k = 0
        cnt = collections.Counter()
        s = 0.0
        for sec in range(int(c) + 10, int(c) + 121):
            while k < len(ts) and ts[k] <= sec:
                if buy[k]:
                    cnt[w[k]] += 1
                    s += sol[k]
                k += 1
            while a < k and ts[a] <= sec - 10:
                if buy[a]:
                    cnt[w[a]] -= 1
                    if not cnt[w[a]]:
                        del cnt[w[a]]
                    s -= sol[a]
                a += 1
            if s > 0.5:
                snap[sec].append((s, len(cnt), sec - c, m))
    return snap


def signals(snap, t0, t1, age, min_sol, min_b10):
    lo, hi = age
    out, prev = [], None
    for sec in range(int(t0), int(t1)):
        best = None
        for s, n, a, m in snap.get(sec, ()):
            if lo <= a <= hi and s >= min_sol and n >= min_b10 and (best is None or s > best[0]):
                best = (s, m)
        cur = best[1] if best else None
        if cur is not None and cur != prev:
            out.append((sec, cur))
        prev = cur
    return out


def summ(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "-"
    lo, hi = C.boot_ci(xs)
    return (f"N {len(xs)}{C.rel(len(xs))}: śr. {C.pct(C.mean(xs))} (CI {lo * 100:+.1f}..{hi * 100:+.1f}), "
            f"med. {C.pct(C.median(xs))}, wygr. {sum(x > 0 for x in xs) / len(xs):.0%}")


def report() -> str:
    T, created, holes, t1, st = load()
    ha, hb = [a for a, _ in holes], [b for _, b in holes]
    t0 = min(created[m] for m in T)
    cut = t0 + (t1 - SPAN - t0) * C.SPLIT

    def clean(sec):
        j = bisect.bisect_left(hb, sec - 60)
        return not (j < len(ha) and ha[j] < sec + 90)

    snap = snapshots(T, created)
    best = None
    for age, ms, mb in itertools.product(GRID["age"], GRID["min_sol"], GRID["min_b10"]):
        sig = [(s, m) for s, m in signals(snap, t0, cut, age, ms, mb) if clean(s)]
        xs = [pnl(T[m], s, 21) for s, m in sig]
        xs = [x for x in xs if x is not None]
        if len(xs) >= 100 and (best is None or C.mean(xs) > best[0]):
            best = (C.mean(xs), age, ms, mb, len(xs))
    out = [f"# Ranking \"nr 1 w tej sekundzie\" - {time.strftime('%d.%m.%Y %H:%M')}\n",
           f"Podział: eksploracja do {time.strftime('%d.%m %H:%M', time.localtime(cut))}, potem TEST. Siatka "
           f"{len(GRID['age']) * len(GRID['min_sol']) * len(GRID['min_b10'])} wariantów, wybór przy d = 0 i wyjściu 21 s.\n"]
    if not best:
        return "\n".join(out + ["Brak wariantu z N >= 100."])
    _, age, ms, mb, n = best
    out.append(f"**Najlepszy na eksploracji:** wiek {age[0]}-{age[1]} s, zakupy w 10 s >= {ms} SOL, kupujący w 10 s >= {mb} "
               f"(N {n}, śr. {C.pct(best[0])}).\n")
    sig_te = [(s, m) for s, m in signals(snap, cut, t1 - SPAN, age, ms, mb) if clean(s)]
    rows = []
    for d in DELAYS:
        rows.append([f"{d} s"] + [summ([pnl(T[m], s + d, h) for s, m in sig_te]) for h in HOLDS])
    out += ["## TEST (liczony raz, bez dziur, 0.25 SOL)\n",
            C.table(["opóźnienie od końca sekundy sygnału", "wyjście po 21 s (jak on)", "wyjście po 60 s"], rows)]
    # jego faktyczne wejścia vs nasze sygnały
    eps, _ = kol.episodes_stream(TRADER)
    ids = dict(st.execute("SELECT mint, id FROM mints"))
    his = [(e["t"], ids.get(e["mint"])) for e in eps if e["t"] >= cut]
    sig_all = collections.defaultdict(list)
    for s, m in sig_te:
        sig_all[m].append(s)
    hit = sum(1 for t, m in his if any(abs(t - s) <= 5 for s in sig_all.get(m, [])))
    his_res = [e["his_sol"] / e["cost"] for e in eps if e["t"] >= cut and e["closed"] and e["cost"] > 0]
    out.append(f"\nJego wejścia w okresie testu: {len(his)}, z nich pokrywa się z naszym sygnałem (ten sam token, <= 5 s): "
               f"{hit} ({hit / max(len(his), 1):.0%}); naszych sygnałów: {len(sig_te)}. Jego wynik w tym okresie: "
               f"{summ(his_res)}.")
    return "\n".join(out)


if __name__ == "__main__":
    txt = report()
    (C.ROOT / "analizy" / "NR1.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
