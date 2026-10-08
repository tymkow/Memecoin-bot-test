"""Panel z danymi projektu (8.10.2026): python panel.py -> data/panel.html (jedna strona, dane wbudowane).

Mapy sieci portfeli: najpierw python -m analizy.mapy (-> data/mapy.json, kilka minut). Liczby z baz (bot.db, stream.db, tylko odczyt) liczone na nowo przy każdym uruchomieniu; wyniki badań (werdykty,
traderzy, koszty Heliusa) przepisane z README / analizy/*.md - przy nowych badaniach dopisz je w RESEARCH / TRADERS.
"""
from __future__ import annotations

import collections
import json
import sqlite3
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
NEW_PORTFOLIOS = ("safety_fast", "safety_bundle30", "safety_nocopy", "random_fast_s6")
LIVE_T0 = time.mktime((2026, 10, 7, 12, 16, 0, 0, 0, -1))

RESEARCH = [  # (obszar, pytanie, wynik, werdykt: ok / niejasne / nie)
    ("Wyjście", "Szybki stop z odczytu puli co 2 s", "symulacja +2,1 pp/poz.; na żywo pary z safety_only +5,6 pp (21 par)", "ok"),
    ("Wyjście", "Wyjście S6 (1/3 @+20%, stop na wejściu)", "+1..+3 pp w danych; na żywo safety_s6 -4,4%/poz. (38)", "niejasne"),
    ("Wejście", "Bundle startu >= 30% podaży", "TEST -1,2% vs -12,7%, ale nie bije random_eligible", "niejasne"),
    ("Wejście", "Bez kopii aktywnego tokena", "TEST -8,7% vs -15,7%; na żywo odwrotnie (12 poz.)", "niejasne"),
    ("Wejście", "Model wyniku (6 cech)", "AUC 0,556 - brak przewagi", "nie"),
    ("Wybór tokenów", "Historia twórcy (pilot Helius)", "pokrycie 18%, grupy z historią gorsze", "nie"),
    ("Wybór tokenów", "Graf zasilania portfeli K = 1-3", "test gorszy od baseline", "nie"),
    ("Wybór tokenów", "Ślepy test wykresów (195 ocen)", "kupić -14,0% vs random_eligible -5,0%", "nie"),
    ("Arbitraż", "Kup na DEX A, sprzedaj na B", "438 kwotowań, 4 zyskowne po 0,1 SOL, żadne nie żyło 10 s", "nie"),
    ("Kopiowanie", "Cupsey 1:1 z opóźnieniem", "0 s -2,6%/poz.; 2-20 s -26..-30%/poz.", "nie"),
    ("Kopiowanie", "Szybciej niż Cupsey (k slotów przed nim)", "2 s przed nim +0,6%/poz., mediana -4,7%", "nie"),
    ("Reguły traderów", "Gorący start (reguła Cupseya)", "0 z 215 reguł > 0 na treningu", "nie"),
    ("Reguły traderów", "Przetrwał start (Bot C)", "test -17%/poz. vs baseline -7%", "nie"),
    ("Reguły traderów", "21 s na najgorętszym starcie (Bot D)", "-2,8% już przy d = 0", "nie"),
    ("Reguły traderów", "Ranking nr 1 w tej sekundzie", "-3,9% przy natychmiastowym wejściu", "nie"),
    ("Grupy", "Wejście za grupą portfeli (cabal)", "wybrane grupy -0,5..-2,1%, baseline -6%", "nie"),
    ("Kopiowanie", "Zyskowne portfele poza próbą", "0,4 s: -5,5%/poz.; one same +3,5%", "nie"),
    ("Kopiowanie", "Zgoda >= 2 zręcznych portfeli", "-5,5..-13,9% vs losowy token ~0..+2%", "nie"),
]
TRADERS = [  # (portfel, opis, pozycji, SOL, %/poz., skąd przewaga)
    ("Cupsey (X, 229 tys.)", "snajper startów ~10 s, wyjście ~14 s", 250, 38.1, -0.2, "sam porusza ceną: ~140 portfeli kupuje za nim"),
    ("Bot A + flota 5 portfeli", "bot: wyjście 16 s albo równo 300 s", 2184, -45.5, -7.2, "flota razem traci - zyskowne portfele to szczęśliwe kawałki"),
    ("Trader B", "kupuje dołek ~1,3 min po starcie", 125, 131.2, 38.6, "grupa: 46 portfeli za nim, 8 z 10 startów jednego twórcy"),
    ("Bot C", "bot: czeka 2-3 min, wyjście po 60 s", 573, 54.7, 6.0, "unika rugów czekaniem; reguła u nas -17%"),
    ("Bot D", "bot: najgorętszy start ~40 s, zawsze 21 s", 2843, 54.2, 3.8, "szybkość / ranking w slocie"),
    ("Bot E (+1 klon)", "bot: wejście 4 s po starcie, zawsze 2 s", 697, 38.4, 5.5, "arbitraż opóźnienia na fali otwarcia"),
]
COPY_DELAY = {  # wynik kopii (%/poz.) wg opóźnienia (s)
    "Cupsey 1:1": [(0, -2.6), (2, -29.5), (5, -27.7), (12, -26.0), (20, -27.7)],
    "Top 20 portfeli, poza próbą": [(0.4, -5.5), (2, -5.8), (4.8, -5.6), (10, -5.5), (20, -4.9)],
    "20 losowych portfeli, poza próbą": [(0.4, -7.5), (2, -7.8), (4.8, -6.8), (10, -7.2), (20, -6.9)],
}
HELIUS = [("Okna krachów, bundle, grafiki (6.10)", 70000), ("Wcześniejsze badania rugów / zasileń", 80000),
          ("Pilot historii twórców (rug2)", 1300), ("Cupsey: historia kont tokenów", 10600),
          ("Cupsey: okna pul PumpSwap", 60000)]


def ro(name):
    c = sqlite3.connect(f"file:{DATA / name}?mode=ro", uri=True, timeout=60)
    return c


def portfolios():
    db = ro("bot.db")
    rows = db.execute("SELECT strategy, opened_ts, closed_ts, cost_usd, realized_usd, exit_reason FROM positions "
                      "WHERE status='closed' ORDER BY closed_ts").fetchall()
    by = collections.defaultdict(list)
    for s, o, c, cost, real, ex in rows:
        by[s or "hybrid"].append((o, c, cost, real, ex or ""))
    out = []
    for s, ps in by.items():
        pnl = [r - c for _, _, c, r, _ in ps]
        rets = [r / c - 1 for _, _, c, r, _ in ps if c]
        gain, loss = sum(x for x in pnl if x > 0), -sum(x for x in pnl if x < 0)
        cum, series = 0.0, []
        for (o, c, cost, r, _), x in zip(ps, pnl):
            cum += x
            series.append([round(c), round(cum, 1)])
        step = max(len(series) // 150, 1)
        series = series[::step] + ([series[-1]] if series and series[-1] not in series[::step] else [])
        out.append({"name": s, "n": len(ps), "pnl": round(sum(pnl), 1), "avg": round(statistics.mean(rets) * 100, 2),
                    "win": round(sum(x > 0 for x in pnl) / len(pnl) * 100), "pf": round(gain / loss, 2) if loss else None,
                    "start": round(min(o for o, *_ in ps)), "series": series,
                    "stops": round(sum("stop" in e for *_, e in ps) / len(ps) * 100)})
    open_n = db.execute("SELECT COUNT(*) FROM positions WHERE status='open'").fetchone()[0]
    dec = db.execute("SELECT COUNT(*), COUNT(DISTINCT mint), MIN(ts), MAX(ts) FROM decisions").fetchone()
    live = []
    for s in NEW_PORTFOLIOS + ("safety_only", "random_eligible"):
        ps = [p for p in by.get(s, []) if p[0] >= LIVE_T0 and not p[4].startswith("przerwa")]
        rets = [r / c - 1 for _, _, c, r, _ in ps if c]
        live.append({"name": s, "n": len(ps), "avg": round(statistics.mean(rets) * 100, 1) if rets else None,
                     "pnl": round(sum(r - c for _, _, c, r, _ in ps), 1)})
    ev = db.execute("SELECT v FROM kv WHERE k='fast_stop_events'").fetchone()
    ev = json.loads(ev[0]) if ev else []
    ds = [e["since_last_above_s"] for e in ev if e.get("since_last_above_s") is not None]
    return sorted(out, key=lambda p: -p["pnl"]), open_n, dec, live, {"n": len(ev), "median_s": statistics.median(ds) if ds else None}


def market():
    st = ro("stream.db")
    t0, t1 = st.execute("SELECT MIN(ts), MAX(ts) FROM trades").fetchone()
    tr = dict(st.execute("SELECT CAST(ts/3600 AS INT), COUNT(*) FROM trades GROUP BY 1"))
    mi = dict(st.execute("SELECT CAST(created_ts/3600 AS INT), COUNT(*) FROM mints WHERE created_ts BETWEEN ? AND ? GROUP BY 1",
                         (t0, t1)))
    mg = dict(st.execute("SELECT CAST(ts/3600 AS INT), COUNT(*) FROM events WHERE kind='migrate' GROUP BY 1"))
    hours = list(range(int(t0 // 3600), int(t1 // 3600) + 1))
    gaps = st.execute("SELECT COUNT(*), COALESCE(SUM(end-start), 0) FROM gaps").fetchone()
    tot = {"trades": sum(tr.values()), "mints": sum(mi.values()), "migr": sum(mg.values()),
           "wallets": st.execute("SELECT COUNT(*) FROM wallets").fetchone()[0], "t0": t0, "t1": t1,
           "gaps": gaps[0], "gap_h": round(gaps[1] / 3600, 1)}
    return {"hours": [h * 3600 for h in hours], "trades": [tr.get(h, 0) for h in hours],
            "mints": [mi.get(h, 0) for h in hours], "migr": [mg.get(h, 0) for h in hours]}, tot


def build() -> Path:
    pf, open_n, dec, live, fast = portfolios()
    mk, tot = market()
    data = {"generated": time.strftime("%d.%m.%Y %H:%M"), "portfolios": pf, "open": open_n,
            "decisions": {"n": dec[0], "tokens": dec[1], "t0": dec[2], "t1": dec[3]}, "live": live, "fast": fast,
            "market": mk, "tot": tot, "research": RESEARCH, "traders": TRADERS, "copy": COPY_DELAY, "helius": HELIUS,
            "maps": json.loads((DATA / "mapy.json").read_text(encoding="utf-8")) if (DATA / "mapy.json").exists() else None,
            "arb": {"quotes": 438, "gross_pos": 4, "alive10s": 0, "sol": 0.0044, "med01": -1.09, "med05": -4.24, "med2": -5.12}}
    tpl = (ROOT / "panel_template.html").read_text(encoding="utf-8")
    out = DATA / "panel.html"
    out.write_text(tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build())
