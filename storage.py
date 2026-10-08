"""SQLite: dziennik decyzji, pozycje, transakcje, krzywa kapitału, czarna lista, zbiór danych badawczych.

Dziennik decyzji zapisuje CAŁE findings i wektor cech dla każdego tokena (także odrzuconego) - to materiał do
strojenia progów i do analizy "co przewiduje wynik". Tabela snapshots to szereg czasowy obserwowanych tokenów.
"""
from __future__ import annotations

import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions(
  id INTEGER PRIMARY KEY, ts REAL, mint TEXT, symbol TEXT, decision TEXT, score REAL,
  categories TEXT, reasons TEXT, findings TEXT, price REAL, liq REAL, mcap REAL, age_min REAL, features TEXT);
CREATE INDEX IF NOT EXISTS ix_dec_mint ON decisions(mint);
CREATE TABLE IF NOT EXISTS positions(
  id INTEGER PRIMARY KEY, mint TEXT, symbol TEXT, status TEXT, opened_ts REAL, closed_ts REAL,
  entry_price REAL, qty_initial REAL, qty_left REAL, cost_usd REAL, realized_usd REAL DEFAULT 0,
  peak_price REAL, entry_liq REAL, tp_hit INTEGER DEFAULT 0, misses INTEGER DEFAULT 0,
  last_rugcheck_ts REAL, exit_reason TEXT, score REAL, entry_info TEXT,
  decimals INTEGER, last_probe_ts REAL DEFAULT 0, unsellable INTEGER DEFAULT 0, strategy TEXT DEFAULT 'hybrid');
CREATE TABLE IF NOT EXISTS bad_wallets(wallet TEXT PRIMARY KEY, mint TEXT, reason TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS outcomes(
  decision_id INTEGER, horizon_h INTEGER, ts REAL, price REAL, liq REAL,
  PRIMARY KEY(decision_id, horizon_h));
CREATE TABLE IF NOT EXISTS trades(
  id INTEGER PRIMARY KEY, position_id INTEGER, ts REAL, side TEXT, price REAL, qty REAL,
  usd REAL, fee_usd REAL, slippage_pct REAL, reason TEXT);
CREATE TABLE IF NOT EXISTS equity(ts REAL, equity REAL, cash REAL, open_value REAL, strategy TEXT DEFAULT 'hybrid');
CREATE TABLE IF NOT EXISTS blacklist(mint TEXT PRIMARY KEY, reason TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS snapshots(
  ts REAL, mint TEXT, price REAL, mcap REAL, liq REAL, vol_m5 REAL, vol_h1 REAL,
  buys_m5 INTEGER, sells_m5 INTEGER, buys_h1 INTEGER, sells_h1 INTEGER, ch_m5 REAL, ch_h1 REAL, held INTEGER);
CREATE INDEX IF NOT EXISTS ix_snap_mint_ts ON snapshots(mint, ts);
CREATE TABLE IF NOT EXISTS wallet_buys(
  wallet TEXT, mint TEXT, ts REAL, usd REAL, price REAL, PRIMARY KEY(wallet, mint));
CREATE TABLE IF NOT EXISTS signals(decision_id INTEGER, strategy TEXT, PRIMARY KEY(decision_id, strategy));
CREATE TABLE IF NOT EXISTS launches(
  mint TEXT PRIMARY KEY, ts REAL, creator TEXT, symbol TEXT, name TEXT, initial_buy_sol REAL, mcap_sol REAL);
CREATE INDEX IF NOT EXISTS ix_launch_creator ON launches(creator, ts);
CREATE TABLE IF NOT EXISTS migrations(mint TEXT PRIMARY KEY, ts REAL, pool TEXT);
CREATE TABLE IF NOT EXISTS wallet_trades(
  tx TEXT PRIMARY KEY, wallet TEXT, mint TEXT, ts REAL, side TEXT, usd REAL, token_amount REAL, price REAL);
CREATE INDEX IF NOT EXISTS ix_wt_wallet ON wallet_trades(wallet, mint);
CREATE INDEX IF NOT EXISTS ix_wt_mint_ts ON wallet_trades(mint, ts);
CREATE TABLE IF NOT EXISTS funding_cache(wallet TEXT PRIMARY KEY, funder TEXT, ts REAL, source TEXT);
CREATE TABLE IF NOT EXISTS candles(pool TEXT, ts INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL, PRIMARY KEY(pool, ts));
CREATE TABLE IF NOT EXISTS llm_decisions(
  decision_id INTEGER, ts REAL, mint TEXT, model TEXT, decision TEXT, confidence INTEGER, p_tp INTEGER, reasoning TEXT,
  invalidation TEXT, flags TEXT, latency REAL, tokens_in INTEGER, tokens_out INTEGER, error TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS candle_jobs(
  decision_id INTEGER PRIMARY KEY, mint TEXT, pool TEXT, entry_ts REAL, status TEXT, ts REAL, n INTEGER, attempts INTEGER);
"""

# kolumny dodane po v0.2 - dopisywane do istniejących baz (nie wymaga resetu)
MIGRATIONS = [
    ("decisions", "features", "TEXT"),
    ("positions", "strategy", "TEXT DEFAULT 'hybrid'"),
    ("equity", "strategy", "TEXT DEFAULT 'hybrid'"),
    ("decisions", "opportunity", "REAL"),
    ("decisions", "risk", "REAL"),
    ("decisions", "explanation", "TEXT"),
    ("decisions", "pair", "TEXT"),                  # v0.7: adres puli (do archiwum świec)
    ("positions", "mae_pct", "REAL"),               # v0.7: najgłębszy spadek w trakcie trzymania (% od wejścia)
    ("positions", "mfe_pct", "REAL"),               # v0.7: najwyższy zysk w trakcie trzymania
    ("positions", "t_mae_min", "REAL"),
    ("positions", "t_mfe_min", "REAL"),
]


class Storage:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False)   # 7.10: wątek szybkiego stopu (fastexit.py) pisze tym samym połączeniem
        self.db.row_factory = sqlite3.Row
        self.skipped = 0          # signals_timed: ile sygnałów pominięto w ostatnim wywołaniu (czas nieznany)
        self.db.executescript(SCHEMA)
        for table, col, ddl in MIGRATIONS:
            have = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
            if col not in have:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        self.db.commit()

    # ---- kv ----
    def kv_get(self, k, default=None):
        r = self.db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return json.loads(r["v"]) if r else default

    def kv_set(self, k, v):
        self.db.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (k, json.dumps(v)))
        self.db.commit()

    # ---- decyzje ----
    def log_decision(self, mint, symbol, verdict, pair, features=None):
        liq = ((pair or {}).get("liquidity") or {}).get("usd")
        ts_created = (pair or {}).get("pairCreatedAt")
        cur = self.db.execute(
            "INSERT INTO decisions(ts,mint,symbol,decision,score,categories,reasons,findings,price,liq,mcap,age_min,"
            "features,opportunity,risk,explanation,pair) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), mint, symbol, verdict.decision, round(verdict.score, 2),
             json.dumps({k: round(v, 1) for k, v in verdict.category_scores.items()}),
             verdict.reasons(), json.dumps([str(f) for f in verdict.findings], ensure_ascii=False),
             float((pair or {}).get("priceUsd") or 0), liq,
             (pair or {}).get("marketCap") or (pair or {}).get("fdv"),
             (time.time() * 1000 - ts_created) / 60000 if ts_created else None,
             json.dumps(features) if features else None,
             round(verdict.opportunity, 1), round(verdict.risk, 1), verdict.explain(), (pair or {}).get("pairAddress")))
        self.db.commit()
        return cur.lastrowid

    def signals_timed(self, strategy: str | None = None) -> list[dict]:
        """Sygnały z chwilą, w której NAPRAWDĘ padły (rosnąco po czasie) - dla badań na świecach i wynikach.

        Do v0.9 sygnał tokena, który w ciągu 30 min przeszedł z obserwacji (WATCH) lub odrzucenia do zakupu, przypinał się
        do starej oceny: jej czasu, ceny i cech. Dla takich wierszy (fixed=True) czas = pierwsze wejście dowolnego
        portfela w ten token w ciągu 31 min po tej ocenie, cena = ostatni snapshot przed nim (cechy zostają z oceny WATCH -
        są niepełne). Bez wejścia czasu nie znamy - wiersz pomijamy (`skipped` w ostatnim wywołaniu)."""
        q = ("SELECT s.strategy, d.id, d.mint, d.symbol, d.ts, d.decision, d.price, d.liq, d.age_min, d.features "
             "FROM signals s JOIN decisions d ON d.id=s.decision_id" + (" WHERE s.strategy=?" if strategy else ""))
        out, self.skipped = [], 0
        entry_cache: dict = {}
        for r in self.db.execute(q, (strategy,) if strategy else ()).fetchall():
            row = {k: r[k] for k in r.keys()}
            row.update(fixed=False, ts_decision=r["ts"])
            if r["decision"] in ("WATCH", "REJECT"):
                if r["id"] not in entry_cache:
                    entry_cache[r["id"]] = self.db.execute(
                        "SELECT MIN(opened_ts) FROM positions WHERE mint=? AND opened_ts BETWEEN ? AND ?",
                        (r["mint"], r["ts"], r["ts"] + 31 * 60)).fetchone()[0]
                opened = entry_cache[r["id"]]
                if opened is None:
                    self.skipped += 1
                    continue
                snap = self.last_snapshot(r["mint"], before_ts=opened)
                row.update(ts=opened - 10, fixed=True,       # wejście ~8 s po sygnale (latencja kwotowania)
                           price=snap["price"] if snap and opened - snap["ts"] <= 300 else None)
            out.append(row)
        return sorted(out, key=lambda x: x["ts"])

    def log_llm(self, decision_id, mint, res: dict | None, meta: dict):
        """Każda ocena modelu (także odrzucona i błąd) - audyt, koszt i opóźnienie."""
        r = res or {}
        self.db.execute("INSERT INTO llm_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (decision_id, time.time(), mint, meta.get("model"), r.get("decision"), r.get("confidence"),
                         r.get("p_tp"), r.get("reasoning"), r.get("invalidation"),
                         json.dumps(r.get("risk_flags") or [], ensure_ascii=False), meta.get("latency"),
                         meta.get("tokens_in"), meta.get("tokens_out"), meta.get("error"), meta.get("raw")))
        if res:                                     # do badań cech: p_tp i pewność jak każda inna cecha decyzji
            row = self.db.execute("SELECT features FROM decisions WHERE id=?", (decision_id,)).fetchone()
            if row is not None:
                f = json.loads(row["features"] or "{}")
                f.update({"gemini_p": res["p_tp"], "gemini_conf": res["confidence"],
                          "gemini_buy": int(res["decision"] == "BUY")})
                self.db.execute("UPDATE decisions SET features=? WHERE id=?", (json.dumps(f), decision_id))
        self.db.commit()

    def log_signal(self, decision_id, strategy):
        """Strategia chciała kupić ten token (niezależnie od tego, czy portfel miał miejsce) - do porównań strategii."""
        self.db.execute("INSERT OR IGNORE INTO signals VALUES(?,?)", (decision_id, strategy))

    # ---- strumień PumpPortal: starty i graduacje ----
    def log_launch(self, mint, creator, symbol, name, initial_buy_sol, mcap_sol):
        self.db.execute("INSERT OR IGNORE INTO launches VALUES(?,?,?,?,?,?,?)",
                        (mint, time.time(), creator, symbol, name, initial_buy_sol, mcap_sol))

    def log_migration(self, mint, pool):
        self.db.execute("INSERT OR IGNORE INTO migrations VALUES(?,?,?)", (mint, time.time(), pool))

    def creator_history(self, creator, exclude_mint="", days=7):
        """Ile tokenów ten twórca wypuścił w naszych danych i ile z nich się wygraduowało."""
        since = time.time() - days * 86400
        r = self.db.execute(
            "SELECT COUNT(*) n, SUM(CASE WHEN m.mint IS NOT NULL THEN 1 ELSE 0 END) grad, "
            "SUM(CASE WHEN l.ts > ? THEN 1 ELSE 0 END) last24 FROM launches l LEFT JOIN migrations m ON m.mint=l.mint "
            "WHERE l.creator=? AND l.mint<>? AND l.ts>?", (time.time() - 86400, creator, exclude_mint, since)).fetchone()
        return {"launches": r["n"] or 0, "graduated": r["grad"] or 0, "launches_24h": r["last24"] or 0}

    # ---- transakcje portfeli (silnik rankingu portfeli) ----
    def log_wallet_trades(self, rows):
        """rows = [(tx, wallet, mint, ts, side, usd, token_amount, price)]; duplikaty (ten sam tx) ignorowane."""
        self.db.executemany("INSERT OR IGNORE INTO wallet_trades VALUES(?,?,?,?,?,?,?,?)", rows)
        self.db.commit()

    def funding_get(self, wallet):
        r = self.db.execute("SELECT funder, ts, source FROM funding_cache WHERE wallet=?", (wallet,)).fetchone()
        return (r["funder"], r["source"]) if r else None

    def funding_set(self, wallet, funder, source):
        self.db.execute("INSERT OR REPLACE INTO funding_cache VALUES(?,?,?,?)", (wallet, funder, time.time(), source))
        self.db.commit()

    # ---- szereg czasowy obserwowanych tokenów (także odrzuconych) ----
    def log_snapshot(self, mint, pair, held=False):
        tx = pair.get("txns") or {}
        vol = pair.get("volume") or {}
        chg = pair.get("priceChange") or {}
        self.db.execute(
            "INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), mint, float(pair.get("priceUsd") or 0),
             pair.get("marketCap") or pair.get("fdv"), (pair.get("liquidity") or {}).get("usd"),
             vol.get("m5"), vol.get("h1"),
             (tx.get("m5") or {}).get("buys"), (tx.get("m5") or {}).get("sells"),
             (tx.get("h1") or {}).get("buys"), (tx.get("h1") or {}).get("sells"),
             chg.get("m5"), chg.get("h1"), int(held)))

    def log_wallet_buys(self, mint, buys):
        """buys = [(wallet, ts, usd, price)] - kto kupował token (do empirycznej oceny portfeli)."""
        self.db.executemany("INSERT OR IGNORE INTO wallet_buys VALUES(?,?,?,?,?)",
                            [(w, mint, ts, usd, px) for w, ts, usd, px in buys])
        self.db.commit()

    # ---- czarna lista ----
    def blacklist(self, mint, reason):
        self.db.execute("INSERT OR REPLACE INTO blacklist VALUES(?,?,?)", (mint, reason, time.time()))
        self.db.commit()

    def blacklisted(self) -> set[str]:
        return {r["mint"] for r in self.db.execute("SELECT mint FROM blacklist")}

    # ---- portfele z rugów (samouczenie) ----
    def add_bad_wallets(self, wallets, mint, reason):
        for w in wallets:
            if w:
                self.db.execute("INSERT OR IGNORE INTO bad_wallets VALUES(?,?,?,?)", (w, mint, reason, time.time()))
        self.db.commit()

    def bad_wallets(self) -> set[str]:
        return {r["wallet"] for r in self.db.execute("SELECT wallet FROM bad_wallets")}

    # ---- wyniki decyzji po czasie (kalibracja) ----
    def pending_outcomes(self, horizons, limit=120):
        """Decyzje z ceną, dla których minął horyzont, a nie ma jeszcze pomiaru."""
        rows = []
        now = time.time()
        for h in horizons:
            rows += self.db.execute(
                "SELECT d.id, d.mint, ?1 AS h FROM decisions d WHERE d.price > 0 AND d.ts <= ?2 - ?1 * 3600 "
                "AND NOT EXISTS (SELECT 1 FROM outcomes o WHERE o.decision_id=d.id AND o.horizon_h=?1) "
                "ORDER BY d.ts LIMIT ?3", (h, now, limit)).fetchall()
        return rows

    def save_outcome(self, decision_id, horizon, price, liq):
        self.db.execute("INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?,?)",
                        (decision_id, horizon, time.time(), price, liq))

    # ---- equity ----
    def log_equity(self, equity, cash, open_value, strategy="hybrid"):
        self.db.execute("INSERT INTO equity VALUES(?,?,?,?,?)", (time.time(), equity, cash, open_value, strategy))
        self.db.commit()

    # ---- kiedy strategia dołączyła (porównania tylko na wspólnym okresie) ----
    def strategy_started(self, name: str) -> float | None:
        v = self.kv_get(f"added:{name}")
        if v:
            return v
        r = self.db.execute("SELECT MIN(ts) FROM equity WHERE strategy=?", (name,)).fetchone()
        if r and r[0]:
            return r[0]
        r = self.db.execute("SELECT MIN(d.ts) FROM signals s JOIN decisions d ON d.id=s.decision_id WHERE s.strategy=?",
                            (name,)).fetchone()
        return r[0] if r and r[0] else None

    def register_strategies(self, names) -> None:
        """Zapamiętuje moment dołączenia każdej strategii (stare: z historii, nowe: teraz)."""
        for n in names:
            if self.kv_get(f"added:{n}") is None:
                self.kv_set(f"added:{n}", self.strategy_started(n) or time.time())

    def mark_rules(self, rules: dict) -> bool:
        """Zapamiętuje zasady portfeli; przy zmianie zapisuje moment zmiany (rules_since). True = zasady się zmieniły."""
        rules = json.loads(json.dumps(rules))          # krotki -> listy, żeby porównanie z kv było stabilne
        old = self.kv_get("rules")
        if old == rules:
            return False
        self.kv_set("rules", rules)
        # nowy portfel z własnymi wyjściami (tylko DOPISANE klucze strategy_exits) nie zmienia zasad pozostałych
        # portfeli - okno porównania "od ostatniej zmiany zasad" zostaje (4.10.2026: safety_ts5 / lowvol_ts10)
        if old and {k: v for k, v in old.items() if k != "strategy_exits"} ==                 {k: v for k, v in rules.items() if k != "strategy_exits"}:
            oe, ne = old.get("strategy_exits") or {}, rules.get("strategy_exits") or {}
            if all(ne.get(k) == v for k, v in oe.items()):
                return False
        self.kv_set("rules_since", time.time())
        return True

    def last_activity_ts(self) -> float | None:
        """Kiedy bot ostatnio coś zapisał (krzywa kapitału jest logowana co obieg) - do wykrywania przerw."""
        r = self.db.execute("SELECT MAX(ts) FROM equity").fetchone()
        return r[0] if r and r[0] else None

    def last_snapshot(self, mint: str, before_ts: float | None = None):
        q = "SELECT price, liq, ts FROM snapshots WHERE mint=? AND price>0"
        args: tuple = (mint,)
        if before_ts:
            q += " AND ts<=?"
            args = (mint, before_ts)
        return self.db.execute(q + " ORDER BY ts DESC LIMIT 1", args).fetchone()

    # ---- archiwum świec (badanie wyjść) ----
    def save_candles(self, pool: str, rows) -> int:
        """rows = [[ts, o, h, l, c, v], ...] ze świec GeckoTerminal; duplikaty (ta sama minuta) ignorowane."""
        data = [(pool, int(r[0]), r[1], r[2], r[3], r[4], r[5]) for r in rows if isinstance(r, (list, tuple)) and len(r) >= 6]
        self.db.executemany("INSERT OR IGNORE INTO candles VALUES(?,?,?,?,?,?,?)", data)
        self.db.commit()
        return len(data)

    def candles_between(self, pool: str, t0: float, t1: float) -> list[list[float]]:
        return [[r["ts"], r["o"], r["h"], r["l"], r["c"], r["v"]] for r in self.db.execute(
            "SELECT ts,o,h,l,c,v FROM candles WHERE pool=? AND ts BETWEEN ? AND ? ORDER BY ts", (pool, int(t0), int(t1)))]

    def candles_cover(self, pool: str, t0: float, t1: float) -> bool:
        """Czy archiwum ma świece obejmujące przedział (z marginesem 10 min na brak transakcji)."""
        r = self.db.execute("SELECT MIN(ts), MAX(ts) FROM candles WHERE pool=? AND ts BETWEEN ? AND ?",
                            (pool, int(t0) - 3600, int(t1) + 3600)).fetchone()
        return bool(r and r[0] is not None and r[0] <= t0 + 600 and r[1] >= t1 - 600)

    def pending_candle_jobs(self, after_h: float, limit: int, max_attempts: int = 3):
        """Decyzje z sygnałem jakiejkolwiek strategii, starsze niż after_h, bez archiwum świec."""
        return self.db.execute(
            "SELECT DISTINCT d.id, d.mint, d.ts, d.pair FROM signals s JOIN decisions d ON d.id=s.decision_id "
            "LEFT JOIN candle_jobs j ON j.decision_id=d.id "
            "WHERE d.ts <= ? AND (j.decision_id IS NULL OR (j.status='error' AND j.attempts < ?)) "
            "ORDER BY d.ts LIMIT ?", (time.time() - after_h * 3600, max_attempts, limit)).fetchall()

    def save_candle_job(self, decision_id, mint, pool, entry_ts, status, n):
        prev = self.db.execute("SELECT attempts FROM candle_jobs WHERE decision_id=?", (decision_id,)).fetchone()
        attempts = (prev["attempts"] or 0) + 1 if prev else 1
        self.db.execute("INSERT OR REPLACE INTO candle_jobs VALUES(?,?,?,?,?,?,?,?)",
                        (decision_id, mint, pool, entry_ts, status, time.time(), n, attempts))
        self.db.commit()

    def pool_for(self, mint: str, before_ts: float | None = None) -> str | None:
        """Adres puli tokena: z decyzji (od v0.7 zapisywany) albo z archiwum świec."""
        q = "SELECT pair FROM decisions WHERE mint=? AND pair IS NOT NULL"
        args: tuple = (mint,)
        if before_ts:
            q += " ORDER BY ABS(ts-?) LIMIT 1"
            args = (mint, before_ts)
        else:
            q += " ORDER BY ts DESC LIMIT 1"
        r = self.db.execute(q, args).fetchone()
        if r:
            return r["pair"]
        r = self.db.execute("SELECT pool FROM candle_jobs WHERE mint=? AND pool IS NOT NULL ORDER BY ts DESC LIMIT 1",
                            (mint,)).fetchone()
        return r["pool"] if r else None
