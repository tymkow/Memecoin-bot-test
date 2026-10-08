"""Ta sama analiza co dla Cupseya (sygnały wejścia/wyjścia, czy odróżnia trash, naśladowcy) dla DOWOLNEGO portfela -
z samego naszego strumienia pump.fun (stream.db), bez Heliusa (8.10.2026).

    <mlenv>/python -m analizy.kol <adres> [nazwa]     # -> analizy/KOL_<nazwa>.md

Pozycje portfela: jego transakcje na krzywej pump.fun ze strumienia (sprzedaż po migracji na PumpSwap jest poza
strumieniem - takie pozycje zostają "otwarte" i nie wchodzą do wyniku). Dziury strumienia gubią część transakcji.
"""
from __future__ import annotations

import collections
import sys
import time

from analizy import common as C
from analizy import cupsey as Q
from analizy import cupsey_signals as S
from analizy import kol_select as K


def episodes_stream(addr: str) -> list[dict]:
    st = C.ro("stream.db")
    wid = (st.execute("SELECT id FROM wallets WHERE addr=?", (addr,)).fetchone() or [None])[0]
    if wid is None:
        return []
    mints = dict(st.execute("SELECT id, mint FROM mints"))
    rows = st.execute("SELECT slot, ts, mint_id, buy, sol, tok FROM trades WHERE wallet_id=? ORDER BY slot", (wid,)).fetchall()
    by = collections.defaultdict(list)
    for slot, ts, m, buy, sol, tok in rows:
        by[m].append({"slot": slot, "idx": 0, "bt": ts, "kind": "buy" if buy else "sell", "mint": mints[m],
                      "tok": float(tok), "sol": (-1 if buy else 1) * sol / 1e9, "venue": "pump_curve", "pool": None})
    t1 = st.execute("SELECT MAX(ts) FROM trades").fetchone()[0]
    out = []
    for m, rs in by.items():
        cur, hold, bought = None, 0.0, 0.0
        for r in rs:
            if r["kind"] == "buy":
                if cur is None:
                    cur, hold, bought = {"mint": r["mint"], "legs": [], "t": r["bt"]}, 0.0, 0.0
                hold += r["tok"]
                bought += r["tok"]
                r["frac"] = None
            else:
                if cur is None:
                    continue
                r["frac"] = min(1.0, r["tok"] / hold) if hold > 0 else 1.0
                hold -= r["tok"]
            cur["legs"].append(r)
            if r["kind"] == "sell" and hold <= Q.DUST * bought:
                cur.update(closed=True, t_end=r["bt"])
                out.append(cur)
                cur = None
        if cur is not None:
            cur.update(closed=False, t_end=t1)
            out.append(cur)
    for e in out:                      # sprzedał więcej, niż kupił na krzywej = tokeny spoza zakupu (przelew, inny
        b = sum(r["tok"] for r in e["legs"] if r["kind"] == "buy")      # portfel, dziura strumienia) - nie liczymy
        e["external"] = sum(r["tok"] for r in e["legs"] if r["kind"] == "sell") > 1.02 * b
        e["his_sol"] = sum(r["sol"] for r in e["legs"])
        e["cost"] = -sum(r["sol"] for r in e["legs"] if r["kind"] == "buy")
        e["venues"] = ["pump_curve"]
    return sorted([e for e in out if not e["external"]], key=lambda e: e["t"]), sum(e["external"] for e in out)


def run(addr: str, name: str) -> str:
    eps, n_ext = episodes_stream(addr)
    closed = [e for e in eps if e["closed"]]
    t0, t1 = Q.window()
    mid = (t0 + t1) / 2
    rets = [e["his_sol"] / e["cost"] for e in closed if e["cost"] > 0]
    head = [f"# Trader {name} ({addr}) - {time.strftime('%d.%m.%Y %H:%M')}\n",
            "Wybrany losowo (ziarno 20261008) spośród portfeli bez X i spoza listy KOL MadeOnSol, z >= 100 zamkniętymi "
            "pozycjami na krzywej, zyskownych w obu połowach okna i NIE kupujących w slocie utworzenia tokena (insiderzy "
            "twórcy odrzuceni). Dane: tylko nasz strumień pump.fun (krzywa).\n",
            C.table(["", "N", "suma SOL", "śr. / mediana na poz.", "wygrane", "śr. stawka SOL"],
                    [[lab, len(g), f"{sum(e['his_sol'] for e in g):+.1f}",
                      f"{C.pct(C.mean([e['his_sol'] / e['cost'] for e in g]))} / {C.pct(C.median([e['his_sol'] / e['cost'] for e in g]))}",
                      f"{sum(e['his_sol'] > 0 for e in g) / max(len(g), 1):.0%}", f"{C.mean([e['cost'] for e in g]):.2f}"]
                     for lab, g in (("zamknięte na krzywej", closed), ("1. połowa", [e for e in closed if e["t"] < mid]),
                                    ("2. połowa", [e for e in closed if e["t"] >= mid]))]),
            f"\nPozycji otwartych na końcu / sprzedanych poza krzywą: {len(eps) - len(closed)}; pominięte (sprzedał więcej tokenów, niż kupił na krzywej - przelew / inny portfel / dziura strumienia): {n_ext}. "
            f"(śr. wynik na pozycję {C.pct(C.mean(rets))})\n"]
    sig = S.report(name, addr, eps)
    sel = K.report(name, eps, addr)
    return "\n".join(head) + "\n\n" + sig + "\n\n" + sel


if __name__ == "__main__":
    addr = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else addr[:6]
    txt = run(addr, name)
    (C.ROOT / "analizy" / f"KOL_{name}.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
