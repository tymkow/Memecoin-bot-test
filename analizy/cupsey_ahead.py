"""Co gdybyśmy byli SZYBSI od Cupseya: te same transakcje, ale k slotów (0.4 s) PRZED nim (8.10.2026).

    python -m analizy.cupsey_ahead      # -> analizy/CUPSEY_PRZED.md

Górna granica "wchodzimy jego regułami szybciej": zakładamy, że wiemy, co on zrobi, i robimy to k slotów wcześniej.
Fill = jego fill x (spot tuż przed jego transakcją / spot tuż przed slotem s - k): przy k = 0 dokładnie jego wynik.
Warianty: wejście i wyjście przed nim; tylko wejście przed nim (wyjście razem z nim); tylko wyjście przed nim.
Pozycja, w której nie da się wejść wcześniej (token jeszcze nie istniał / brak stanu ceny), jest pomijana i liczona osobno.
Ceny: krzywa pump.fun ze strumienia (stream.db), PumpSwap z transakcji puli (okna -15..+25 s wokół jego transakcji).
"""
from __future__ import annotations

import bisect
import time

from analizy import common as C
from analizy import cupsey as Q

KS = (1, 3, 5, 12)            # sloty przed nim: 0.4 s, ~1.2 s, ~2 s, ~5 s


class SlotPrices:
    def __init__(self):
        self.st = C.ro("stream.db")
        self.ids = {r[1]: r[0] for r in self.st.execute("SELECT id, mint FROM mints")}
        self.pool = Q.SwapPath().db
        self.cache = {}

    def series(self, key: tuple):
        if key not in self.cache:
            kind, x = key
            if kind == "curve":
                i = self.ids.get(x)
                rows = [] if i is None else self.st.execute(
                    "SELECT slot, vsol, vtok FROM trades WHERE mint_id=? ORDER BY slot", (i,)).fetchall()
                self.cache[key] = ([r[0] for r in rows], [float(r[1]) / float(r[2]) if r[2] else None for r in rows])
            else:
                rows = self.pool.execute("SELECT slot, post_tok, post_sol FROM pool_tx WHERE pool=? ORDER BY slot, idx",
                                         (x,)).fetchall()
                self.cache[key] = ([r[0] for r in rows],
                                   [(r[2] + C.V_PUMPSWAP) / r[1] if r[1] else None for r in rows])
        return self.cache[key]

    def before(self, r: dict, slot: int):
        """Spot po ostatniej transakcji w slocie < slot (dla miejsca handlu tej transakcji)."""
        if r["venue"] == "pump_curve":
            key = ("curve", r["mint"])
        elif r["venue"] == "pumpswap" and r["pool"]:
            key = ("pool", r["pool"])
        else:
            return None
        sl, px = self.series(key)
        j = bisect.bisect_left(sl, slot)
        if j == 0:
            return None
        if key[0] == "pool" and sl[0] > slot - 40:      # okno puli zaczyna się 15 s przed nim - dalej nie sięgamy
            return None
        return px[j - 1]


def ahead(e: dict, kb: int, ks: int, sp: SlotPrices):
    tokens, sol = 0.0, 0.0
    for r in e["legs"]:
        k = kb if r["kind"] == "buy" else ks
        p0 = sp.before(r, r["slot"])
        p1 = sp.before(r, r["slot"] - k) if k else p0
        if not p0 or not p1:
            return None
        if r["kind"] == "buy":
            tokens += r["tok"] * p0 / p1
            sol += r["sol"]
        elif r["tok"] > 0:
            q = tokens * r["frac"]
            sol += r["sol"] * (q / r["tok"]) * p1 / p0
            tokens -= q
    return sol


def report() -> str:
    t0, t1 = Q.window()
    eps = [e for e in Q.episodes() if e["closed"]]
    sp = SlotPrices()
    for e in eps:
        e["cost"] = -sum(r["sol"] for r in e["legs"] if r["kind"] == "buy")
    base = [e for e in eps if ahead(e, 0, 0, sp) is not None]
    out = [f"# Szybciej niż Cupsey - te same transakcje k slotów przed nim ({time.strftime('%d.%m.%Y %H:%M')})\n",
           f"Zamkniętych pozycji z cenami (krzywa pump.fun / PumpSwap): {len(base)} z {len(eps)}. Górna granica: zakłada, "
           f"że wiemy, co on zrobi. 1 slot = 0,4 s.\n"]
    rows = []
    mid = (t0 + t1) / 2
    for label, f in (("jego wynik (k = 0)", lambda k: (0, 0)),
                     ("wejście i wyjście przed nim", lambda k: (k, k)),
                     ("tylko wejście przed nim, wyjście razem z nim", lambda k: (k, 0)),
                     ("tylko wyjście przed nim, wejście razem z nim", lambda k: (0, k))):
        for k in (KS if label != "jego wynik (k = 0)" else (0,)):
            kb, ks = f(k)
            vals = [(e, ahead(e, kb, ks, sp)) for e in base]
            ok = [(e, v) for e, v in vals if v is not None]
            xs = [v for _, v in ok]
            rets = [v / e["cost"] for e, v in ok if e["cost"] > 0]
            h1 = sum(v for e, v in ok if e["t"] < mid)
            h2 = sum(v for e, v in ok if e["t"] >= mid)
            lo, hi = C.boot_ci(xs)
            rows.append([label, f"{k} ({k * 0.4:.1f} s)" if k else "-", f"{len(ok)} (bez wejścia {len(vals) - len(ok)})",
                         f"{sum(xs):+.1f}", f"{lo:+.3f}..{hi:+.3f}", f"{C.pct(C.mean(rets))} / {C.pct(C.median(rets))}",
                         f"{sum(v > 0 for v in xs) / max(len(xs), 1):.0%}", f"{h1:+.1f} / {h2:+.1f}"])
    out.append(C.table(["wariant", "slotów przed nim", "N", "suma SOL", "95% CI śr. SOL/poz.", "śr. / mediana na poz.",
                        "wygrane", "1. / 2. połowa SOL"], rows))
    return "\n".join(out)


if __name__ == "__main__":
    txt = report()
    (C.ROOT / "analizy" / "CUPSEY_PRZED.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
