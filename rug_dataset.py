"""Zbiór danych do modułu wykrywania rugów (rugguard.py), etap 1: cechy ze strumienia zbieracza (bez kosztów).

    python rug_dataset.py fetch      # pule (DexScreener) i świece 1-min po migracji (GeckoTerminal) -> data/rug_data.db
    python rug_dataset.py build      # punkty decyzji + cechy POINT-IN-TIME + etykiety -> tabela samples
    python rug_dataset.py report     # progi pojedynczych cech, liczba flag, wpływ na P&L (rug_backtest)

Punkty decyzji: każda migracja z data/stream.db (token utworzony w czasie zbierania = pełna historia krzywej), chwile
migracja +0 / +2 / +5 / +15 min. Cechy wyłącznie z transakcji krzywej sprzed chwili t (rugguard.curve_features).
Etykiety (zaakceptowane 5.10.2026) liczone ze świec PumpSwap po chwili t, cena odniesienia = cena w chwili t:
  RUG_SZYBKI     cena <= 30% ceny z t w ciągu 30 min, ZANIM wzrosła o +50% (TP1 bota; w propozycji +30%, patrz README)
  RUG_PO_POMPIE  cena <= 20% ceny z t w ciągu 6 h, po wzroście o >= +50%
  OK             reszta.  Token martwy (brak świec >= 30 min po spadku) = spadek się liczy (nie "brak danych").
Surowe dane (świece) zapisywane lokalnie - przebiegi build/report nie odpytują sieci. Baza bota tylko do odczytu.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT_DB = DATA / "rug_data.db"
STREAM_DB = DATA / "stream.db"
BOT_DB = DATA / "bot.db"
WINDOW_S = 6 * 3600
OFFSETS_MIN = (0, 2, 5, 15)

SCHEMA = """
CREATE TABLE IF NOT EXISTS pools(mint TEXT PRIMARY KEY, mig_ts REAL, pool TEXT, dex TEXT, status TEXT, ts REAL, n INTEGER);
CREATE TABLE IF NOT EXISTS candles(pool TEXT, ts INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL, PRIMARY KEY(pool, ts));
CREATE TABLE IF NOT EXISTS samples(mint TEXT, t REAL, offset_min INTEGER, label TEXT, fast_rug INTEGER, mfe REAL, mae REAL,
  ret_30m REAL, ret_6h REAL, features TEXT, PRIMARY KEY(mint, offset_min));
"""


def ro(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def out_db() -> sqlite3.Connection:
    c = sqlite3.connect(OUT_DB, timeout=120)        # zapisy równoległe (świece, zasilający) - czekamy zamiast błędu
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def migrations(stream: sqlite3.Connection) -> list[sqlite3.Row]:
    """Migracje tokenów utworzonych w czasie zbierania (pełna historia krzywej)."""
    return stream.execute(
        "SELECT m.id mint_id, m.mint, m.created_ts, m.created_slot, m.creator, m.mayhem, MIN(e.ts) mig_ts, MIN(e.slot) mig_slot "
        "FROM events e JOIN mints m ON m.id = e.mint_id WHERE e.kind='migrate' AND m.created_ts IS NOT NULL "
        "GROUP BY m.id ORDER BY mig_ts").fetchall()


# ------------------------------------------------------------------ fetch
def fetch(rpm_gecko: int, limit: int | None):
    sys.path.insert(0, str(Path(__file__).parent))
    from config import Config
    from sources import DexScreener, GeckoTerminal
    cfg = Config()
    cfg.dexscreener_rpm, cfg.gecko_rpm = 30, rpm_gecko      # bot korzysta z tych samych limitów IP - jedziemy wolno
    dex, gecko = DexScreener(cfg), GeckoTerminal(cfg)
    db = out_db()
    migs = [m for m in migrations(ro(STREAM_DB)) if m["mig_ts"] < time.time() - WINDOW_S - 600]
    done = {r["mint"] for r in db.execute("SELECT mint FROM pools WHERE status IN ('ok','brak_swiec')")}
    todo = [m for m in migs if m["mint"] not in done][:limit]
    print(f"migracji z pełnym oknem 6 h: {len(migs)}, do pobrania: {len(todo)}", flush=True)
    for i in range(0, len(todo), 30):
        chunk = todo[i:i + 30]
        pairs = dex.pairs_for_tokens([m["mint"] for m in chunk])
        for m in chunk:
            ps = pairs.get(m["mint"]) or []
            p = next((x for x in ps if x.get("dexId") == "pumpswap"), None) or dex.best_pair(ps)
            if not p:
                # DexScreener ukrywa martwe tokeny (pairs: null) - bez tego zapasu zbiór miałby tylko ocalałych
                d = gecko._get(f"/tokens/{m['mint']}/pools") or {}
                gp = [x for x in d.get("data", []) if (((x.get("relationships") or {}).get("dex") or {}).get("data")
                                                       or {}).get("id") == "pumpswap"]
                if gp:
                    p = {"pairAddress": gp[0]["attributes"]["address"], "dexId": "pumpswap(gecko)"}
            if not p:
                db.execute("INSERT OR REPLACE INTO pools VALUES(?,?,?,?,?,?,?)",
                           (m["mint"], m["mig_ts"], None, None, "brak_pary", time.time(), 0))
                db.commit()
                continue
            pool = p["pairAddress"]
            cs = gecko.ohlcv(pool, limit=1000, before=int(m["mig_ts"] + WINDOW_S + 120))
            if cs is None:
                status, n = "blad", 0                                          # ponowimy przy następnym przebiegu
            else:
                cs = [c for c in cs if m["mig_ts"] - 600 <= c[0] <= m["mig_ts"] + WINDOW_S + 60]
                db.executemany("INSERT OR REPLACE INTO candles VALUES(?,?,?,?,?,?,?)",
                               [(pool, int(c[0]), *map(float, c[1:6])) for c in cs])
                status, n = ("ok" if cs else "brak_swiec"), len(cs)
            db.execute("INSERT OR REPLACE INTO pools VALUES(?,?,?,?,?,?,?)",
                       (m["mint"], m["mig_ts"], pool, p.get("dexId"), status, time.time(), n))
            db.commit()
        got = db.execute("SELECT status, COUNT(*) FROM pools GROUP BY status").fetchall()
        print(f"{time.strftime('%H:%M:%S')} {min(i + 30, len(todo))}/{len(todo)}  {dict((r[0], r[1]) for r in got)}",
              flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "build", "report"])
    ap.add_argument("--rpm", type=int, default=8, help="fetch: zapytań/min do GeckoTerminal (bot używa 20 z ~30)")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.rpm, a.limit)
    elif a.cmd == "build":
        import rug_backtest
        rug_backtest.build()
    else:
        import rug_backtest
        rug_backtest.report()


if __name__ == "__main__":
    main()
