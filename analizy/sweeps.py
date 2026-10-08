"""2. LIQUIDITY SWEEPS na świecach 1-min (PumpSwap, 570 migracji, 6 h po migracji).

Definicja (parametry L, X, N konfigurowalne):
  sweep w dół w świecy i:  low_i < min(low_{i-L..i-1}) * (1 - X)        (wybicie pod lokalne minimum o X%)
                           i w ciągu N świec (i..i+N-1) close_j > min(low_{i-L..i-1})   (szybki powrót)
                           -> sygnał w chwili zamknięcia świecy j (bez zaglądania w przyszłość)
  nieudany sweep (trend):  wybicie bez powrotu w N świecach -> zdarzenie po zamknięciu świecy i+N-1
  sweep w górę (fałszywe wybicie): high_i > max(high_{i-L..i-1}) * (1 + X) i powrót close_j < max w N świecach
Świece są tylko w minutach z transakcjami ("N świec" = N minut z handlem). Pomijamy 2 pierwsze minuty po migracji.
Zwrot po k min: close pierwszej świecy z ts >= sygnał + k*60 (brak świecy = cena stoi = ostatni close).
Baseline: zwroty z KAŻDEJ świecy tych samych tokenów (bezwarunkowo) oraz wejście o losowej porze w ten sam token.
"""
from __future__ import annotations

import bisect
import random

from analizy import common as C

GRID = [(L, X, N) for L in (10, 20) for X in (0.05, 0.10, 0.20) for N in (1, 3)]
HORIZONS = (1, 5, 15)


def events(cs: list, L: int, X: float, N: int, mig_ts: float):
    """-> lista (rodzaj, indeks świecy sygnału) dla 'down', 'down_fail', 'up'."""
    out = []
    i = L
    while i < len(cs):
        if cs[i][0] < mig_ts + 120:
            i += 1
            continue
        lo_prev = min(c[3] for c in cs[i - L:i])
        hi_prev = max(c[2] for c in cs[i - L:i])
        if cs[i][3] < lo_prev * (1 - X):
            j = next((k for k in range(i, min(i + N, len(cs))) if cs[k][4] > lo_prev), None)
            if j is not None:
                out.append(("down", j))
                i = j + 1
            else:
                out.append(("down_fail", min(i + N - 1, len(cs) - 1)))
                i += N
            continue
        if cs[i][2] > hi_prev * (1 + X):
            j = next((k for k in range(i, min(i + N, len(cs))) if cs[k][4] < hi_prev), None)
            if j is not None:
                out.append(("up", j))
                i = j + 1
                continue
        i += 1
    return out


def fwd(cs: list, ts_list: list, j: int, k: int) -> float:
    t = cs[j][0] + 60 + k * 60
    p0 = cs[j][4]
    idx = bisect.bisect_left(ts_list, t)
    p = cs[idx][4] if idx < len(cs) else cs[-1][4]
    return p / p0 - 1 if p0 else 0.0


def collect(ents: list, L, X, N, rnd: random.Random):
    ev = {"down": [], "down_fail": [], "up": [], "baseline": []}
    entry = {"sweep_down": [], "losowa_pora": []}
    for e in ents:
        cs = e["candles"]
        tsl = [c[0] for c in cs]
        for kind, j in events(cs, L, X, N, e["mig_ts"]):
            ev[kind].append(tuple(fwd(cs, tsl, j, k) for k in HORIZONS))
            if kind == "down":
                path = [c for c in cs[j + 1:] if c[0] <= e["mig_ts"] + C.H6]
                if path:
                    entry["sweep_down"].append(C.sim(path, cs[j][4], cs[j][0] + 60))
                    r = rnd.randrange(L, len(cs) - 1)
                    rp = [c for c in cs[r + 1:] if c[0] <= e["mig_ts"] + C.H6]
                    if rp and cs[r][0] >= e["mig_ts"] + 120:
                        entry["losowa_pora"].append(C.sim(rp, cs[r][4], cs[r][0] + 60))
        for j in range(L, len(cs) - 1, 3):
            if cs[j][0] >= e["mig_ts"] + 120:
                ev["baseline"].append(tuple(fwd(cs, tsl, j, k) for k in HORIZONS))
    return ev, entry


def report() -> str:
    ents = C.migration_tokens()
    ex, te = C.split_time(ents)
    out = ["## 2. Liquidity sweeps\n",
           f"Tokenów: {len(ents)} (eksploracja {len(ex)}, TEST {len(te)}), świece 1-min do 6 h po migracji.\n",
           "**Siatka parametrów na EKSPLORACJI** (średni zwrot po 5 min po sygnale; baseline = każda 3. świeca):\n"]
    rows, best = [], None
    for L, X, N in GRID:
        ev, entry = collect(ex, L, X, N, random.Random(1))
        b5 = C.mean([r[1] for r in ev["baseline"]])
        d5 = C.mean([r[1] for r in ev["down"]])
        rows.append([L, f"{X:.0%}", N, f"{len(ev['down'])}{C.rel(len(ev['down']))}", C.pct(d5), C.pct(b5),
                     f"{len(ev['up'])}", C.pct(C.mean([r[1] for r in ev['up']])),
                     C.pct(C.mean(entry["sweep_down"])), C.pct(C.mean(entry["losowa_pora"]))])
        if len(ev["down"]) >= 30 and (best is None or C.mean(entry["sweep_down"]) - C.mean(entry["losowa_pora"]) > best[0]):
            best = (C.mean(entry["sweep_down"]) - C.mean(entry["losowa_pora"]), L, X, N)
    out.append(C.table(["L", "X", "N", "sweepów w dół", "zwrot 5 min po", "baseline 5 min", "sweepów w górę",
                        "5 min po (w górę)", "wejście po sweepie (wyjścia bota)", "wejście o losowej porze"], rows))
    if best:
        _, L, X, N = best
        out.append(f"\n**Wybrane na eksploracji:** L={L}, X={X:.0%}, N={N}. **TEST (liczony raz):**\n")
        rt = []
        for lbl, s in (("eksploracja", ex), ("TEST", te)):
            ev, entry = collect(s, L, X, N, random.Random(2))
            for kind, name in (("down", "sweep w dół (powrót)"), ("down_fail", "wybicie bez powrotu (trend)"),
                               ("up", "sweep w górę (fałszywe wybicie)"), ("baseline", "baseline: każda 3. świeca")):
                xs = ev[kind]
                rt.append([lbl, name, f"{len(xs)}{C.rel(len(xs))}"] +
                          [C.pct(C.mean([r[i] for r in xs])) for i in range(3)] +
                          [f"{C.mean([r[1] > 0 for r in xs]):.0%}"])
            for kind, name in (("sweep_down", "WEJŚCIE po sweepie w dół (wyjścia bota)"), ("losowa_pora", "WEJŚCIE o losowej porze (baseline)")):
                xs = entry[kind]
                lo, hi = C.boot_ci(xs)
                rt.append([lbl, name, f"{len(xs)}{C.rel(len(xs))}", "", "", "", f"{C.pct(C.mean(xs))} (CI {C.pct(lo)}..{C.pct(hi)})"])
        out.append(C.table(["zbiór", "zdarzenie", "N", "po 1 min", "po 5 min", "po 15 min", "% dodatnich po 5 min"], rt))
    return "\n".join(out)


if __name__ == "__main__":
    print(report())
