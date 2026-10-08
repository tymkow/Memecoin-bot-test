"""Podział po etapach krzywej pump.fun (krok 4 planu z 4.10): czy któryś etap daje przewagę na samym rynku, bez strategii.
Dane: data/stream.db ze zbieracza collector.py.

    python stages.py [--size 0.25] [--delay 3]

Etap = postęp krzywej (0% = start tokena, 100% = graduacja): "nowe" < 30%, "środek" 30-70%, "final stretch" >= 70%.
Dla każdego tokena bierzemy chwilę, w której PIERWSZY raz wszedł w etap (widzimy przejście z niższego etapu, a dla
"nowych" - token powstał, gdy zbieracz działał), i liczymy zakup za --size SOL po --delay s: wartość po 5 / 30 / 120 min
(sprzedaż całości po cenie z rezerw krzywej, po opłatach i priority fee). Graduacja przed horyzontem = wycena po ostatniej
cenie krzywej (handlu po graduacji nie zbieramy). Wynik to "przeciętny token w tym etapie" - punkt odniesienia dla
każdej strategii na pump.fun: strategia ma sens dopiero, gdy bije swój etap.
"""
from __future__ import annotations

import argparse
import sqlite3
import statistics
import time

import copytrade as ct
from collector import CURVE_TOKENS, INITIAL_VTOK

HORIZONS = (5, 30, 120)
STAGES = (("nowe (<30%)", 0.0, 0.3), ("środek (30-70%)", 0.3, 0.7), ("final stretch (>=70%)", 0.7, 1.01))


def prog(vtok: int) -> float:
    return (INITIAL_VTOK - vtok) / CURVE_TOKENS


def entries(states: dict, created: dict) -> dict:
    """{etap: [(mint, czas wejścia w etap)]} - tylko przejścia, które widzieliśmy."""
    out = {name: [] for name, _, _ in STAGES}
    for mint, (ts_list, sts) in states.items():
        prev = None
        for t, (vsol, vtok, fee) in zip(ts_list, sts):
            p = prog(vtok)
            for name, lo, hi in STAGES:
                if lo <= p < hi and not any(m == mint for m, _ in out[name][-1:]):
                    seen_cross = (prev is not None and prev < lo) if lo > 0 else (mint in created and t - created[mint] < 120)
                    if seen_cross:
                        out[name].append((mint, t))
            prev = p
    return out


def run(size: float = 0.25, delay: int = 3, prio: float = 0.001, hours: float | None = None):
    db = sqlite3.connect(f"file:{ct.DB_PATH}?mode=ro", uri=True)
    rows, states, complete, creators, gaps = ct.load(db, hours)
    if len(rows) < 1000:
        print("Za mało danych - zbieracz musi popracować.")
        return
    created = {m: t for m, t in db.execute("SELECT id, created_ts FROM mints WHERE created_ts IS NOT NULL")}
    t_end = rows[-1][1]
    print(f"dane: {len(rows):,} transakcji, {(t_end - rows[0][1]) / 3600:.1f} h; tokenów powstałych w tym czasie: "
          f"{len(created):,}, graduacji: {len(complete)}; zakup {size} SOL po {delay} s, wycena po opłatach\n")
    size_l, prio_l = size * ct.LAMPORTS, prio * ct.LAMPORTS
    print(f"{'etap':<24}{'tokenów':>8}{'zgraduowało':>13}" + "".join(f"{f'+{h} min: med.':>16}{'śr.':>8}{'n':>6}" for h in HORIZONS)
          + f"{'<=-80% po 2 h':>15}")
    for name, items in entries(states, created).items():
        res = {h: [] for h in HORIZONS}
        grad = 0
        for mint, t in items:
            t_in = t + delay
            done = complete.get(mint)
            if done is not None and done <= t_in:
                continue
            st, _ = ct.state_at(states, mint, t_in)
            tokens = ct.buy_tokens(st[0], st[1], size_l - prio_l, st[2])
            grad += done is not None
            for h in HORIZONS:
                t_h = t_in + h * 60
                if done is not None and done <= t_h:
                    t_h = done                                  # zgraduował: wycena po ostatniej cenie krzywej
                elif t_h > t_end:
                    continue                                    # jeszcze nie minął horyzont
                s, _ = ct.state_at(states, mint, t_h)
                res[h].append((ct.sell_sol(s[0], s[1], tokens, s[2]) - prio_l) / size_l - 1)
        line = f"{name:<24}{len(items):>8}{(grad / len(items) if items else 0):>12.1%}"
        for h in HORIZONS:
            r = res[h]
            line += (f"{statistics.median(r):>+16.1%}{statistics.mean(r):>+8.1%}{len(r):>6}" if r else f"{'-':>16}{'-':>8}{0:>6}")
        r2 = res[HORIZONS[-1]]
        line += f"{(sum(x <= -0.8 for x in r2) / len(r2) if r2 else 0):>15.0%}"
        print(line)
    print("\n(śr. ciągną pojedyncze wystrzały, mediana pokazuje typowy token; to rynek bez żadnej strategii)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=float, default=0.25)
    ap.add_argument("--delay", type=int, default=3)
    ap.add_argument("--hours", type=float, help="tylko ostatnie tyle godzin danych")
    a = ap.parse_args()
    run(a.size, a.delay, hours=a.hours)


if __name__ == "__main__":
    main()
