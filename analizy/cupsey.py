"""Kopiowanie 1:1 tradera "Cupsey" (portfel z listy MadeOnSol) - na jego historycznych transakcjach z okresu naszych
danych i z NASZYM opóźnieniem (8.10.2026).

    python -m analizy.cupsey fetch      # jego transakcje z MadeOnSol /kol/feed (darmowe, 100 na zapytanie) -> cache
    python -m analizy.cupsey report     # -> analizy/CUPSEY.md

Źródło transakcji: MadeOnSol /kol/feed?kol=<portfel> (Helius odpada: pod jego adresem ~6 tx/s cudzych transakcji
Raydium LaunchLab, w których jest tylko kontem pomocniczym - pełne pobranie ~180 tys. kredytów).
Kopia 1:1: każdy jego zakup = nasz zakup TĄ SAMĄ kwotą SOL po d sekundach, każda sprzedaż = sprzedaż tej samej części
naszej pozycji po d sekundach. Cena: krzywa pump.fun - rezerwy z naszego strumienia (stream.db) po ostatniej transakcji
z czasem <= t + d. Opłata krzywej z transakcji strumienia, + COST_TX SOL za każdą naszą transakcję (priority + napiwek).
Opóźnienia: 0 s (jego cena - nieosiągalne), 2 s (najlepszy copy bot), 5 s, 12 s (mediana wykrycia w naszym bocie),
20 s (pętla bota).
"""
from __future__ import annotations

import bisect
import collections
import json
import sqlite3
import sys
import time
from datetime import datetime

from analizy import common as C

W = "2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f"
CACHE = C.DATA / "analizy_cache.db"
WSOL = "So11111111111111111111111111111111111111112"
PROGRAMS = {
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "pump_curve",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "pumpswap",
    "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj": "raydium_launchlab",
    "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN": "meteora_dbc",
    "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG": "meteora_damm2",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "meteora_dlmm",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "raydium_cpmm",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "raydium_amm",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "jupiter",
}
VENUE_ORDER = ("pump_curve", "pumpswap", "raydium_launchlab", "meteora_dbc", "meteora_damm2", "meteora_dlmm",
               "raydium_cpmm", "raydium_amm")
SCHEMA = """
CREATE TABLE IF NOT EXISTS cs_feed(sig TEXT PRIMARY KEY, ts INTEGER, mint TEXT, action TEXT, sol REAL, tok REAL,
  mc_usd REAL, price_usd REAL, launchpad TEXT, age_min REAL, raw TEXT);
CREATE TABLE IF NOT EXISTS cs_tx(sig TEXT PRIMARY KEY, slot INTEGER, idx INTEGER, bt INTEGER, kind TEXT, mint TEXT,
  tok REAL, sol REAL, fee REAL, venue TEXT, pool TEXT, pool_tok REAL, pool_sol REAL);
CREATE TABLE IF NOT EXISTS cs_acc(mint TEXT PRIMARY KEY, acc TEXT, n INTEGER, credits INTEGER, ts REAL);
"""


def keys_of(tx: dict) -> list[str]:
    msg = tx["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
    la = (tx.get("meta") or {}).get("loadedAddresses") or {}
    return keys + la.get("writable", []) + la.get("readonly", [])


def parse_swap(tx: dict, wallet: str = W) -> dict | None:
    """Zakup/sprzedaż tokena przez portfel: zmiana tokena i SOL (natywny + WSOL) portfela, miejsce handlu i stan puli po
    transakcji (konto, które oddało/przyjęło tokeny, i jego WSOL). None = to nie swap tokena za SOL."""
    meta = tx.get("meta") or {}
    if meta.get("err"):
        return None
    try:
        keys = keys_of(tx)
        wi = keys.index(wallet)
    except (KeyError, TypeError, ValueError):
        return None
    sol = (meta["postBalances"][wi] - meta["preBalances"][wi]) / 1e9
    fee = (meta.get("fee") or 0) / 1e9 if wi == 0 else 0.0
    bal = collections.defaultdict(lambda: [0.0, 0.0])      # (owner, mint) -> [pre, post]
    for side, i in (("preTokenBalances", 0), ("postTokenBalances", 1)):
        for b in meta.get(side) or []:
            ui = b.get("uiTokenAmount") or {}
            bal[(b.get("owner"), b.get("mint"))][i] += float(ui.get("amount") or 0) / 10 ** int(ui.get("decimals") or 0)
    own = {m: v for (o, m), v in bal.items() if o == wallet}
    if WSOL in own:
        v = own.pop(WSOL)
        sol += v[1] - v[0]
    moved = [(m, v[1] - v[0]) for m, v in own.items() if abs(v[1] - v[0]) > 0]
    if len(moved) != 1:
        return None
    mint, dtok = moved[0]
    if dtok > 0 and sol < 0:
        kind = "buy"
    elif dtok < 0 and sol > 0:
        kind = "sell"
    else:
        return None
    progs = {PROGRAMS[k] for k in keys if k in PROGRAMS}
    venue = next((v for v in VENUE_ORDER if v in progs), "jupiter" if "jupiter" in progs else "inne")
    pool = ptok = psol = None
    cands = [(o, v) for (o, m), v in bal.items() if m == mint and o != wallet and (v[1] - v[0]) * dtok < 0]
    if cands:
        o, v = max(cands, key=lambda x: abs(x[1][1] - x[1][0]))
        pool, ptok = o, v[1]
        ws = bal.get((o, WSOL))
        psol = ws[1] if ws else None
    return {"kind": kind, "mint": mint, "tok": abs(dtok), "sol": sol, "fee": fee, "venue": venue, "pool": pool,
            "pool_tok": ptok, "pool_sol": psol}


def cache() -> sqlite3.Connection:
    c = sqlite3.connect(CACHE, timeout=120)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def window() -> tuple[int, int]:
    db = C.ro("stream.db")
    a, b = db.execute("SELECT MIN(ts), MAX(ts) FROM trades").fetchone()
    return int(a), int(b)


def iso(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(max_calls: int = 120):
    import madeonsol as M
    db = cache()
    t0, t1 = window()
    have = db.execute("SELECT MIN(ts) FROM cs_feed").fetchone()[0]
    before = iso(have) if have and have <= t1 + 60 else iso(t1 + 60)
    calls = 0
    while calls < max_calls:
        d = M.get("/kol/feed", {"kol": W, "limit": 100, "before": before})
        calls += 1
        if not d:
            print("brak odpowiedzi - przerwane (można wznowić)")
            break
        rows = d.get("trades") or []
        for x in rows:
            ts = datetime.fromisoformat(x["traded_at"].replace("Z", "+00:00")).timestamp()
            db.execute("INSERT OR REPLACE INTO cs_feed VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (x["tx_signature"], int(ts), x["token_mint"], x["action"], x.get("sol_amount"),
                        x.get("token_amount"), x.get("market_cap_usd_at_trade"), x.get("price_usd_at_trade"),
                        x.get("launchpad"), x.get("token_age_minutes"), json.dumps(x)))
        db.commit()
        oldest = min((r["traded_at"] for r in rows), default=None)
        print(f"{time.strftime('%H:%M:%S')} zapytanie {calls}: {len(rows)} transakcji, najstarsza {oldest}", flush=True)
        if not rows or not d.get("has_more") or not d.get("next_before"):
            break
        before = d["next_before"]
        if datetime.fromisoformat(before.replace("Z", "+00:00")).timestamp() < t0 - 3600:
            break
        time.sleep(1.0)
    n, a, b = db.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM cs_feed").fetchone()
    print(f"w cache {n} transakcji: {time.ctime(a)} - {time.ctime(b)}; zapytań {calls}")


def universe() -> list[str]:
    """Tokeny, którymi handlował w oknie: z feedu MadeOnSol + z naszego strumienia (krzywa pump.fun)."""
    t0, t1 = window()
    db = cache()
    ms = {r[0] for r in db.execute("SELECT DISTINCT mint FROM cs_feed WHERE ts BETWEEN ? AND ?", (t0, t1))}
    st = C.ro("stream.db")
    wid = st.execute("SELECT id FROM wallets WHERE addr=?", (W,)).fetchone()
    if wid:
        ms |= {r[0] for r in st.execute("SELECT DISTINCT m.mint FROM trades t JOIN mints m ON m.id = t.mint_id "
                                        "WHERE t.wallet_id=?", (wid[0],))}
    return sorted(ms)


def fetch_acc(rps: float = 3.0):
    """Pełna historia jego konta tokena (ATA, Token-2022 albo SPL) dla każdego tokena - tylko jego transakcje
    (adres portfela odpada: ~6 tx/s cudzego szumu). Koszt ~10 kredytów / 100 transakcji."""
    import rug_funding as rf
    from analizy import solana as SO
    h = rf.Helius(rps)
    db = cache()
    done = {r[0] for r in db.execute("SELECT mint FROM cs_acc")}
    todo = [m for m in universe() if m not in done]
    print(f"tokenów do pobrania: {len(todo)} (szacunek ~{len(todo) * 15} kredytów)", flush=True)
    credits = 0
    for i, m in enumerate(todo, 1):
        acc, n, cr = None, 0, 0
        for prog in (SO.TOKEN_2022, SO.TOKEN):
            a = SO.ata(W, m, prog)
            token, txs = None, []
            while True:
                opts = {"transactionDetails": "full", "sortOrder": "asc", "limit": 100,
                        "maxSupportedTransactionVersion": 1, "filters": {"status": "succeeded"}}
                if token:
                    opts["paginationToken"] = token
                r = h.call("getTransactionsForAddress", [a, opts])
                cr += 10
                if r is None:
                    break
                txs += r.get("data") or []
                token = r.get("paginationToken")
                if not token or not r.get("data"):
                    break
            if txs:
                acc, n = a, len(txs)
                for x in txs:
                    s = parse_swap(x)
                    if not s or s["mint"] != m:
                        continue
                    sig = (x.get("transaction") or {}).get("signatures", [None])[0]
                    db.execute("INSERT OR REPLACE INTO cs_tx VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (sig, x.get("slot"), x.get("transactionIndex") or 0, x.get("blockTime"), s["kind"], m,
                                s["tok"], s["sol"], s["fee"], s["venue"], s["pool"], s["pool_tok"], s["pool_sol"]))
                break
        credits += cr
        db.execute("INSERT OR REPLACE INTO cs_acc VALUES (?,?,?,?,?)", (m, acc, n, cr, time.time()))
        db.commit()
        if i % 25 == 0:
            print(f"{time.strftime('%H:%M:%S')} {i}/{len(todo)} kredyty ~{credits}", flush=True)
    print(f"koniec, kredyty ~{credits}", flush=True)


# ------------------------------------------------------------------ pozycje (epizody) Cupseya
DELAYS = (0, 2, 5, 12, 20)
DUST = 0.01                    # reszta < 1% kupionych tokenów = pozycja zamknięta


def episodes() -> list[dict]:
    """Jego pozycje w oknie naszych danych: od zakupu przy zerowym stanie do sprzedaży (prawie) wszystkiego.
    Pozycje zaczęte przed oknem (pierwsza transakcja = sprzedaż) i niezamknięte do końca okna - pomijane/oznaczone."""
    t0, t1 = window()
    db = cache()
    rows = [dict(r) for r in db.execute("SELECT * FROM cs_tx WHERE bt BETWEEN ? AND ? ORDER BY slot, idx", (t0, t1))]
    by = collections.defaultdict(list)
    for r in rows:
        by[r["mint"]].append(r)
    out = []
    for mint, rs in by.items():
        cur, hold, bought = None, 0.0, 0.0
        for r in rs:
            if r["kind"] == "buy":
                if cur is None:
                    cur, hold, bought = {"mint": mint, "legs": [], "t": r["bt"]}, 0.0, 0.0
                hold += r["tok"]
                bought += r["tok"]
                r["frac"] = None
            else:
                if cur is None:
                    continue                                  # sprzedaż tokenów kupionych przed oknem
                r["frac"] = min(1.0, r["tok"] / hold) if hold > 0 else 1.0
                hold -= r["tok"]
            cur["legs"].append(r)
            if r["kind"] == "sell" and hold <= DUST * bought:
                cur.update(closed=True, t_end=r["bt"])
                out.append(cur)
                cur = None
        if cur is not None:
            cur.update(closed=False, t_end=t1)
            out.append(cur)
    for e in out:
        e["his_sol"] = sum(r["sol"] for r in e["legs"])
        e["cost"] = -sum(r["sol"] for r in e["legs"] if r["kind"] == "buy")
        e["venues"] = sorted({r["venue"] for r in e["legs"]})
    return sorted(out, key=lambda e: e["t"])


class CurvePath:
    """Cena krzywej pump.fun ze strumienia: spot = vsol / vtok po ostatniej transakcji z czasem <= x."""

    def __init__(self):
        self.st = C.ro("stream.db")
        self.ids = {r[1]: r[0] for r in self.st.execute("SELECT id, mint FROM mints")}
        self.cache = {}
        self.holes = [(a, b) for a, b in self.st.execute("SELECT start, end FROM gaps")]

    def path(self, mint: str):
        if mint not in self.cache:
            i = self.ids.get(mint)
            rows = [] if i is None else self.st.execute(
                "SELECT ts, vsol, vtok FROM trades WHERE mint_id=? ORDER BY slot", (i,)).fetchall()
            mig = None if i is None else self.st.execute(
                "SELECT MIN(ts) FROM events WHERE mint_id=? AND kind IN ('complete','migrate')", (i,)).fetchone()[0]
            self.cache[mint] = ([r[0] for r in rows], [float(r[1]) / float(r[2]) if r[2] else None for r in rows], mig)
        return self.cache[mint]

    def spot(self, mint: str, x: float, strict: bool = False):
        ts, px, mig = self.path(mint)
        if mig is not None and x >= mig:
            return None
        k = bisect.bisect_left(ts, x) if strict else bisect.bisect_right(ts, x)
        return px[k - 1] if k > 0 else None


class SwapPath:
    """Cena puli PumpSwap z transakcji puli (crash_gap.pool_tx): spot = (SOL + V) / tokeny."""

    def __init__(self):
        from analizy import crash_gap as CG
        self.db = CG.cache()
        self.cache = {}

    def path(self, pool: str):
        if pool not in self.cache:
            rows = self.db.execute("SELECT slot, idx, bt, pre_tok, pre_sol, post_tok, post_sol FROM pool_tx WHERE pool=? "
                                   "ORDER BY slot, idx", (pool,)).fetchall()
            spot = lambda tok, sol: (sol + C.V_PUMPSWAP) / tok if tok else None   # noqa: E731
            self.cache[pool] = ([r[2] for r in rows], [spot(r[5], r[6]) for r in rows],
                                {(r[0], r[1]): spot(r[3], r[4]) for r in rows})
        return self.cache[pool]

    def spot(self, pool: str, x: float):
        ts, px, _ = self.path(pool)
        k = bisect.bisect_right(ts, x)
        return px[k - 1] if k > 0 else None

    def spot_before(self, pool: str, slot: int, idx: int):
        """Stan puli tuż przed JEGO transakcją (pre-saldo z tej samej transakcji w pool_tx)."""
        return self.path(pool)[2].get((slot, idx))


def leg_spot(r: dict, x: float, before: bool, cp: CurvePath, sp: SwapPath):
    if r["venue"] == "pump_curve":
        return cp.spot(r["mint"], x, before)
    if r["venue"] == "pumpswap" and r["pool"]:
        return sp.spot_before(r["pool"], r["slot"], r["idx"]) if before else sp.spot(r["pool"], x)
    return None


def copy_episode(e: dict, d: float, cp: CurvePath, sp: SwapPath):
    """Nasz wynik (SOL) przy kopii 1:1 z opóźnieniem d. Fill = jego fill x (spot przed jego transakcją / spot w t + d):
    przy d = 0 dokładnie jego wynik; dla d > 0 cena przesunięta o ruch rynku (z jego własnym wpływem włącznie).
    None = nie da się wycenić (miejsce bez danych cen, migracja w trakcie, brak stanu puli)."""
    tokens, sol = 0.0, 0.0
    for r in e["legs"]:
        p0 = leg_spot(r, r["bt"], True, cp, sp)
        p1 = leg_spot(r, r["bt"] + d, False, cp, sp) if d > 0 else p0
        if not p0 or not p1:
            return None
        if r["kind"] == "buy":
            tokens += r["tok"] * p0 / p1
            sol += r["sol"]
        else:
            if r["tok"] <= 0:
                continue
            q = tokens * r["frac"]
            sol += r["sol"] * (q / r["tok"]) * p1 / p0
            tokens -= q
    return sol


def copy_episode_safe(e, d, cp, sp):
    try:
        return copy_episode(e, d, cp, sp)
    except (TypeError, ZeroDivisionError):
        return None


def fetch_pools(rps: float = 3.0, pre: int = 15, post: int = 25):
    """Transakcje pul PumpSwap w oknach [t - pre, t + post] wokół jego transakcji (do stanu puli w t + d)."""
    import rug_funding as rf
    from analizy import crash_gap as CG
    db = CG.cache()
    per = collections.defaultdict(list)
    mint_of = {}
    for e in episodes():
        for r in e["legs"]:
            if r["venue"] == "pumpswap" and r["pool"]:
                per[r["pool"]].append([r["bt"] - pre, r["bt"] + post])
                mint_of[r["pool"]] = r["mint"]
    have = {(r[0], r[1], r[2]) for r in db.execute("SELECT pool, t0, t1 FROM pool_win")}
    jobs = [(p, a, b) for p, iv in per.items() for a, b in CG.merge(iv) if (p, a, b) not in have]
    print(f"okien do pobrania: {len(jobs)} (pul {len(per)}), szacunek ~{len(jobs) * 12} kredytów", flush=True)
    h = rf.Helius(rps)
    credits = 0
    for i, (p, a, b) in enumerate(jobs, 1):
        rows, cr, n, status = CG.fetch_window(h, p, mint_of[p], a, b)
        credits += cr
        db.executemany("INSERT OR IGNORE INTO pool_tx VALUES (?,?,?,?,?,?,?,?)", rows)
        db.execute("INSERT OR REPLACE INTO pool_win VALUES (?,?,?,?,?,?,?)", (p, a, b, status, n, cr, time.time()))
        db.commit()
        if i % 50 == 0:
            print(f"{time.strftime('%H:%M:%S')} {i}/{len(jobs)} kredyty ~{credits}", flush=True)
    print(f"koniec, kredyty ~{credits}", flush=True)


# ------------------------------------------------------------------ pozycje bota
def bot_entries(t0: float, t1: float) -> list[dict]:
    """Wejścia bota w oknie (pozycje różnych portfeli w ten sam token w 10 min = jedno wejście), bez odtworzeń przerwy."""
    db = C.ro("bot.db")
    rows = [dict(r) for r in db.execute(
        "SELECT mint, strategy, opened_ts, closed_ts, cost_usd, realized_usd, exit_reason FROM positions "
        "WHERE status='closed' AND opened_ts BETWEEN ? AND ? AND COALESCE(exit_reason,'') NOT LIKE 'przerwa%' "
        "ORDER BY opened_ts", (t0, t1))]
    ents = []
    for r in rows:
        r["ret"] = r["realized_usd"] / r["cost_usd"] - 1
        e = next((x for x in ents if x["mint"] == r["mint"] and r["opened_ts"] - x["t"] <= 600), None)
        if e is None:
            ents.append({"mint": r["mint"], "t": r["opened_ts"], "pos": [r]})
        else:
            e["pos"].append(r)
    for e in ents:
        e["ret"] = C.mean([p["ret"] for p in e["pos"]])
        e["usd"] = sum(p["realized_usd"] - p["cost_usd"] for p in e["pos"])
        e["re"] = next((p["ret"] for p in e["pos"] if p["strategy"] == "random_eligible"), None)
    return ents


def summ(xs: list) -> str:
    xs = [x for x in xs if x is not None]
    if not xs:
        return "-"
    return f"{C.pct(C.mean(xs))} (mediana {C.pct(C.median(xs))}, N {len(xs)}{C.rel(len(xs))})"


def report() -> str:
    t0, t1 = window()
    eps = episodes()
    cp, sp = CurvePath(), SwapPath()
    db = cache()
    n_acc = db.execute("SELECT COUNT(*), SUM(acc IS NOT NULL), SUM(credits) FROM cs_acc").fetchone()
    for e in eps:
        e["ret"] = e["his_sol"] / e["cost"] if e["cost"] > 0 else None
        e["copy"] = {d: copy_episode_safe(e, d, cp, sp) for d in DELAYS}
        e["hole"] = any(a <= e["t_end"] and b >= e["t"] for a, b in cp.holes)
    closed = [e for e in eps if e["closed"]]
    out = [f"# Kopiowanie 1:1 tradera Cupsey ({W[:6]}...) - {time.strftime('%d.%m.%Y %H:%M')}\n",
           f"Okno naszych danych: {time.strftime('%d.%m %H:%M', time.localtime(t0))} - "
           f"{time.strftime('%d.%m %H:%M', time.localtime(t1))} ({(t1 - t0) / 3600:.0f} h). Transakcje: historia jego kont "
           f"tokenów z Heliusa ({n_acc[1]} z {n_acc[0]} tokenów z feedu MadeOnSol i naszego strumienia, ~{n_acc[2]} "
           f"kredytów). Feed MadeOnSol gubi większość sprzedaży (zwykle widzi 1 z kilku), więc wyniki tylko z Heliusa.\n"]
    # 1. jego wynik
    vc = collections.Counter("+".join(e["venues"]) for e in closed)
    out += ["## 1. Jego wynik (pozycje zamknięte w oknie)\n",
            f"Pozycji: {len(eps)} (zamkniętych {len(closed)}, otwartych na końcu okna {len(eps) - len(closed)}). "
            f"Miejsca handlu: {dict(vc.most_common(8))}.\n",
            C.table(["", "N", "suma SOL", "śr. na pozycję", "wygrane", "śr. koszt pozycji SOL"],
                    [[nm, len(g), f"{sum(e['his_sol'] for e in g):+.2f}", summ([e['ret'] for e in g]),
                      f"{sum(e['his_sol'] > 0 for e in g) / max(len(g), 1):.0%}", f"{C.mean([e['cost'] for e in g]):.2f}"]
                     for nm, g in (("wszystkie zamknięte", closed),
                                   ("pierwsza połowa czasu", [e for e in closed if e["t"] < (t0 + t1) / 2]),
                                   ("druga połowa czasu", [e for e in closed if e["t"] >= (t0 + t1) / 2]))])]
    # 2. kopia z opóźnieniem
    pr = [e for e in closed if all(e["copy"][d] is not None for d in DELAYS)]
    rows = []
    for d in DELAYS:
        xs = [e["copy"][d] for e in pr]
        rets = [x / e["cost"] for x, e in zip(xs, pr)]
        h1 = [e["copy"][d] for e in pr if e["t"] < (t0 + t1) / 2]
        h2 = [e["copy"][d] for e in pr if e["t"] >= (t0 + t1) / 2]
        lo, hi = C.boot_ci(xs) if len(xs) > 1 else (float("nan"), float("nan"))
        rows.append([f"{d} s" + (" (jego cena)" if d == 0 else ""), len(xs), f"{sum(xs):+.2f}",
                     f"{lo:+.3f}..{hi:+.3f}", summ(rets), f"{sum(x > 0 for x in xs) / max(len(xs), 1):.0%}",
                     f"{sum(h1):+.2f} / {sum(h2):+.2f}"])
    nh = [e for e in pr if not e["hole"]]
    out += ["\n## 2. Kopia 1:1 z opóźnieniem (pozycje, których wszystkie transakcje da się wycenić)\n",
            f"Wycenialne: {len(pr)} z {len(closed)} zamkniętych (krzywa pump.fun ze strumienia, PumpSwap z transakcji puli; "
            f"inne miejsca - LaunchLab, Meteora, ... - bez cen). Wejście/wyjście tą samą kwotą SOL co on, po d sekundach.\n",
            C.table(["opóźnienie", "N", "suma SOL", "95% CI śr. SOL/poz.", "śr. wynik na pozycję", "wygrane",
                     "1. / 2. połowa SOL"], rows),
            f"\nBez pozycji nachodzących na dziury w strumieniu ({len(nh)} z {len(pr)}): "
            + ", ".join(f"{d} s {sum(e['copy'][d] for e in nh):+.2f} SOL" for d in DELAYS) + "."]
    # 2b. dlaczego: ruch ceny po jego transakcjach
    mv = {k: {d: [] for d in DELAYS[1:]} for k in ("buy", "sell")}
    for e in closed:
        for r in e["legs"]:
            p0 = leg_spot(r, r["bt"], True, cp, sp)
            if not p0:
                continue
            for d in DELAYS[1:]:
                p1 = leg_spot(r, r["bt"] + d, False, cp, sp)
                if p1:
                    mv[r["kind"]][d].append(p1 / p0 - 1)
    st = C.ro("stream.db")
    crowd = []
    for e in closed:
        for r in e["legs"]:
            i = cp.ids.get(r["mint"])
            if r["venue"] == "pump_curve" and r["kind"] == "buy" and i:
                crowd.append(st.execute("SELECT COUNT(*) FROM trades WHERE mint_id=? AND buy=1 AND ts BETWEEN ? AND ? "
                                        "AND wallet_id NOT IN (SELECT id FROM wallets WHERE addr=?)",
                                        (i, r["bt"], r["bt"] + 2, W)).fetchone()[0])
    out += ["\n**Dlaczego:** zmiana ceny względem stanu tuż przed jego transakcją (mediana; zawiera jego własny wpływ):\n",
            C.table(["", *[f"po {d} s" for d in DELAYS[1:]]],
                    [[f"po jego KUPNIE (N {len(mv['buy'][2])})", *[C.pct(C.median(mv['buy'][d])) for d in DELAYS[1:]]],
                     [f"po jego SPRZEDAŻY (N {len(mv['sell'][2])})", *[C.pct(C.median(mv['sell'][d])) for d in DELAYS[1:]]]]),
            f"\nNa krzywej w ciągu 2 s po jego kupnie inni robią mediana {C.median(crowd):.0f} zakupów (N {len(crowd)}). "
            f"Ruch ceny w tym czasie to jego własny wpływ + ci, którzy wchodzą razem z nim - kopiujący zawsze kupuje "
            f"drożej i sprzedaje taniej o ten ruch.",
            f"\nKoszt danych: Helius ~{n_acc[2]} kredytów (konta tokenów) + okna pul PumpSwap (gorące pule: setki-tysiące "
            f"transakcji na sekundę okna, łącznie ~60 tys. kredytów - szacunek przed pobraniem był ~3 tys.)."]
    # 3. pokrycie z botem
    be = bot_entries(t0, t1)
    his_m = {e["mint"] for e in eps}
    bot_m = {e["mint"] for e in be}
    seen = C.ro("bot.db")
    both = [e for e in closed if e["mint"] in bot_m]
    only_his = [e for e in closed if e["mint"] not in bot_m]
    only_bot = [b for b in be if b["mint"] not in his_m]
    common_b = [b for b in be if b["mint"] in his_m]
    dt = []
    for b in common_b:
        hs = [e["t"] for e in eps if e["mint"] == b["mint"]]
        dt.append(min(hs, key=lambda x: abs(x - b["t"])) - b["t"])
    n_seen = sum(1 for e in only_his if seen.execute("SELECT 1 FROM decisions WHERE mint=? LIMIT 1", (e["mint"],)).fetchone())
    ve = lambda g: collections.Counter("+".join(e["venues"]) for e in g).most_common(3)   # noqa: E731
    out += ["\n## 3. Pokrycie z naszym botem (te same tokeny w oknie)\n",
            C.table(["grupa", "N", "jego wynik", "wynik bota (śr. portfeli)", "uwagi"], [
                ["jego pozycje w tokenach, które bot też kupił", len(both), summ([e["ret"] for e in both]),
                 summ([b["ret"] for b in common_b]), f"wejść bota {len(common_b)}; miejsca: {ve(both)}"],
                ["jego pozycje, których bot nie wziął", len(only_his), summ([e["ret"] for e in only_his]), "-",
                 f"bot w ogóle oceniał {n_seen} z tych tokenów; miejsca: {ve(only_his)}"],
                ["wejścia bota w tokeny, których on nie ruszał", len(only_bot), "-", summ([b["ret"] for b in only_bot]),
                 f"random_eligible z nich: {summ([b['re'] for b in only_bot if b['re'] is not None])}"],
            ]),
            f"\nWspólne tokeny - jego najbliższe wejście względem naszego (minuty, + = on później): "
            + (", ".join(f"{x / 60:+.0f}" for x in sorted(dt)[:40]) if dt else "brak")]
    return "\n".join(out)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "fetch":
        fetch()
    elif cmd == "fetch_acc":
        fetch_acc()
    elif cmd == "pools":
        fetch_pools()
    elif cmd == "report":
        txt = report()
        (C.ROOT / "analizy" / "CUPSEY.md").write_text(txt + "\n", encoding="utf-8")
        print(txt)
