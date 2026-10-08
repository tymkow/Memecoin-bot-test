"""6. DEFINICJE RUGA - kilka definicji na wejściach bota, ich pokrycie i wpływ na wyniki strategii.

  (a)  wycofanie płynności: min_t L_t / L_oczekiwana < 0.7   (płynność spadła o > 30% PONAD to, co wynika z ceny w puli
       stałego iloczynu - od 7.10 z wirtualną rezerwą SOL PumpSwap, common.liq_vs_expected; migawki bota)
  (a') surowy spadek płynności: min L_t / L_0 < 0.5
  (b1) cena -70% w 30 min od wejścia (szybki)       (b2) cena -80% w 6 h od wejścia (wolny)
  (c1) dev sprzedaje: któryś portfel wyszedł z powodem dev_sell (bot zobaczył sprzedaż twórcy)
  (c2) top holder: w minucie krachu jeden portfel sprzedał >= 3% podaży (mapy rugów; tylko tokeny z danych migracji)
  (d1) b1 lub a      (d2) b2 i (a' lub c1 lub c2)
  (e)  potrójna bariera: cena -70% ZANIM +50% (TP1 bota), w 6 h - rug, przed którym bot nie mógł nic zrealizować
"""
from __future__ import annotations

import collections
import math

from analizy import common as C


def defs_for(e: dict, dumpers: dict) -> dict:
    ref, path = e["ref"], e["path"]
    t0 = e["ts"]
    d = {}
    lr, lraw = [], []
    snaps = [s for s in e.get("snaps", []) if s[0] >= t0 - 30 and s[1] and s[2]]
    if snaps:
        p0, l0 = snaps[0][1], snaps[0][2]
        for _, p, l in snaps:
            r = C.liq_vs_expected(l0, p0, l, p, e["mint"])     # od 7.10 z wirtualną rezerwą SOL PumpSwap
            if r is not None:
                lr.append(r)
            lraw.append(l / l0)
    d["a"] = int(bool(lr) and min(lr) < 0.7)
    d["a_raw"] = int(bool(lraw) and min(lraw) < 0.5)
    d["b1"] = int(any(c[3] <= ref * 0.30 for c in path if c[0] <= t0 + 1800))
    d["b2"] = int(min(c[3] for c in path) <= ref * 0.20)
    d["c1"] = int(any(p["reason"] == "dev_sell" for p in e["pos"]))
    d["c2"] = int(max(dumpers.get(e["mint"], [0])) >= 3.0)
    d["d1"] = int(d["b1"] or d["a"])
    d["d2"] = int(d["b2"] and (d["a_raw"] or d["c1"] or d["c2"]))
    d["e"] = int(e.get("label") == "rug")            # potrójna bariera: -70% ZANIM +50% (TP1), 6 h
    d["has_liq"] = int(bool(snaps))
    return d


DEFS = ["a", "a_raw", "b1", "b2", "c1", "c2", "d1", "d2", "e"]
NAMES = {"a": "(a) wycofanie płynności", "a_raw": "(a') płynność -50%", "b1": "(b1) -70% w 30 min",
         "b2": "(b2) -80% w 6 h", "c1": "(c1) dev_sell", "c2": "(c2) top holder >= 3%", "d1": "(d1) b1 lub a",
         "d2": "(d2) b2 i (a' lub c)", "e": "(e) -70% zanim +50% (6 h)"}


def report() -> str:
    db = C.ro("rug_data.db")
    dumpers = collections.defaultdict(list)
    for m, pct in db.execute("SELECT mint, sold_pct FROM dumpers"):
        dumpers[m].append(pct)
    ents = C.bot_entry_set()
    for e in ents:
        e["d"] = defs_for(e, dumpers)
    ex, te = C.split_time(ents)
    out = ["## 6. Definicje ruga\n",
           f"Wejścia bota ze świecami: **{len(ents)}** (eksploracja {len(ex)}, TEST {len(te)}); z migawkami płynności po "
           f"wejściu: {sum(e['d']['has_liq'] for e in ents)}; w danych map rugów (c2): "
           f"{sum(1 for e in ents if e['mint'] in dumpers)}.\n"]
    rows = []
    for k in DEFS:
        n_ex, n_te = sum(e["d"][k] for e in ex), sum(e["d"][k] for e in te)
        pos = [p for e in ents if e["d"][k] for p in e["pos"]]
        rows.append([NAMES[k], f"{n_ex + n_te}", f"{(n_ex + n_te) / len(ents):.0%}", f"{n_ex / len(ex):.0%}",
                     f"{n_te / len(te):.0%}", f"{len(pos)}", f"{sum(p['pnl'] for p in pos):+.0f}",
                     C.pct(C.mean([p["ret"] for p in pos]))])
    out.append("**Ile rugów wg każdej definicji** (odsetek wejść; stabilność w czasie: eksploracja vs TEST):\n")
    out.append(C.table(["definicja", "rugów", "odsetek", "eksploracja", "TEST", "pozycji bota", "$ na tych pozycjach",
                        "śr. wynik pozycji"], rows))
    out.append("\n**Pokrycie definicji** (ile % rugów z wiersza jest też rugiem wg kolumny):\n")
    cov = []
    for a in DEFS:
        sa = {i for i, e in enumerate(ents) if e["d"][a]}
        cov.append([NAMES[a]] + [f"{len(sa & {i for i, e in enumerate(ents) if e['d'][b]}) / len(sa):.0%}" if sa else "—" for b in DEFS])
    out.append(C.table(["rug wg \\ też wg"] + [k for k in DEFS], cov))
    out.append("\n**Wynik strategii: $ na wejściach uznanych za rug vs pozostałe (cały okres)**\n")
    strats = sorted({p["s"] for e in ents for p in e["pos"]})
    srows = []
    for s in strats:
        allp = [p for e in ents for p in e["pos"] if p["s"] == s]
        row = [s, f"{len(allp)}", f"{sum(p['pnl'] for p in allp):+.0f}"]
        for k in ("b1", "b2", "e", "a_raw"):
            rp = [p for e in ents if e["d"][k] for p in e["pos"] if p["s"] == s]
            row.append(f"{sum(p['pnl'] for p in rp):+.0f} ({len(rp)})")
        srows.append(row)
    out.append(C.table(["strategia", "pozycji", "$ razem", "$ na rugach b1 (N)", "$ na rugach b2 (N)", "$ na rugach e (N)",
                        "$ na rugach a' (N)"], srows))
    return "\n".join(out)


if __name__ == "__main__":
    print(report())
