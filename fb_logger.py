"""Logowanie na żywo (6.10.2026): skład pierwszych kupujących przy każdej decyzji bota + sprzedaże insiderów w trakcie
trzymania pozycji. OSOBNY proces - bot o nim nie wie i nie czeka na niego (zero wpływu na handel); bot.db i stream.db
tylko do odczytu.

    python -u fb_logger.py            # pętla (start/restart: skill /restart-bota loger)
    python fb_logger.py --once        # jeden przebieg (test)
    python fb_logger.py --stats       # podsumowanie zapisanych danych

Zapis: data/fb_live.db
  token_fb      skład pierwszych kupujących tokena (firstbuyers.py - ta sama logika co w analizie), liczony RAZ na token
                w chwili PIERWSZEJ decyzji bota o nim (krzywa po migracji się nie zmienia); score_rug z analizy
                (analizy/fb_score_model.json - na teście AUC ~0.52, logujemy do sprawdzenia na żywo)
  decision_fb   każda decyzja bota -> token (żeby łączyć skład z decyzjami i wynikami portfeli)
  holding_sells sprzedaże w trakcie otwartej pozycji bota: insiderzy, wspólny zasilający, twórca, pierwsi kupujący
                oraz każda sprzedaż >= $100 (z adresem - do późniejszego sprawdzenia zasileń)
Point-in-time: transakcje krzywej, historia portfeli i wiek tylko sprzed chwili pierwszej decyzji.
Helius: zasilenia portfeli tylko dla tokenów z decyzją BUY/WATCH/SKIP (te, które bot mógł kupić), limit dzienny.
Sprzedaże: transakcje puli z GeckoTerminal (ostatnie 300) co ~90 s dla tokenów z otwartą pozycją; tx_from_address =
podpisujący (u routerów może to być pośrednik - flaga "insider" jest wtedy dolnym oszacowaniem).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
import traceback
from datetime import datetime
from pathlib import Path

import firstbuyers as F

BASE = Path(__file__).parent
DATA = BASE / "data"
OUT_DB = DATA / "fb_live.db"
MODEL = BASE / "analizy" / "fb_score_model.json"
HELIUS_DAILY_CAP = 15_000
TRADEABLE = ("BUY", "WATCH", "SKIP")
BIG_SELL_USD = 100.0
POLL_DECISIONS_S, POLL_SELLS_S, ROUTERS_REFRESH_S = 10, 90, 7200

SCHEMA = """
CREATE TABLE IF NOT EXISTS token_fb(mint TEXT PRIMARY KEY, decision_id INTEGER, ts_eval REAL, status TEXT,
  n_first INTEGER, frac_insider REAL, frac_smart REAL, frac_sniper REAL, frac_retail REAL, frac_shared_funder REAL,
  young_insider_dump REAL, funding_known REAL, score_rug REAL, has_hole INTEGER, funding_done INTEGER,
  features TEXT, wallets TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS decision_fb(decision_id INTEGER PRIMARY KEY, mint TEXT, ts REAL, decision TEXT);
CREATE TABLE IF NOT EXISTS holding_sells(tx TEXT PRIMARY KEY, mint TEXT, ts REAL, wallet TEXT, usd REAL,
  insider INTEGER, shared_funder INTEGER, creator INTEGER, first_buyer INTEGER, young_insider INTEGER, logged_ts REAL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


def log(msg: str):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def ro(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=60)
    c.row_factory = sqlite3.Row
    return c


class Logger:
    def __init__(self):
        import rug_funding as rf
        from config import Config
        from sources import GeckoTerminal
        self.out = sqlite3.connect(OUT_DB, timeout=60)
        self.out.execute("PRAGMA journal_mode=WAL")
        self.out.executescript(SCHEMA)
        self.bot = ro(DATA / "bot.db")
        self.stream = ro(DATA / "stream.db")
        self.cache = rf.wallet_db()                 # wspólny cache zasileń z analizami (data/rug_data.db)
        self.rf = rf
        self.helius = None
        cfg = Config()
        cfg.gecko_rpm = 6                           # bot zużywa 20 z ~30/min tego samego IP
        self.gecko = GeckoTerminal(cfg)
        self.model = json.loads(MODEL.read_text(encoding="utf-8")) if MODEL.exists() else None
        self.routers: set = set()
        self.routers_ts = 0.0
        self.last_sells = 0.0

    # ---------------------------------------------------------------- pomocnicze
    def meta(self, k, default=None):
        r = self.out.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    def set_meta(self, k, v):
        self.out.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v)))
        self.out.commit()

    def helius_budget(self) -> bool:
        return self.meta(f"helius:{time.strftime('%Y-%m-%d')}", 0) < HELIUS_DAILY_CAP

    def refresh_routers(self):
        if time.time() - self.routers_ts < ROUTERS_REFRESH_S:
            return
        ids = [r[0] for r in self.stream.execute(
            "SELECT id FROM mints WHERE created_ts IS NOT NULL ORDER BY created_ts DESC LIMIT 400")]
        tr: dict = {i: [] for i in ids}
        if ids:
            for r in self.stream.execute(f"SELECT mint_id, slot, ts, wallet_id, buy, sol, tok FROM trades WHERE "
                                         f"ts < 2000000000 AND mint_id IN ({','.join(map(str, ids))})"):
                tr[r[0]].append(tuple(r[1:]))
        self.routers = F.routers(tr, ids)
        self.routers_ts = time.time()
        log(f"routery: {len(self.routers)} (z {len(ids)} ostatnich tokenów)")

    def addr_map(self, ids) -> dict:
        ids = [i for i in ids if i is not None]
        out = {}
        for i in range(0, len(ids), 900):
            ch = ids[i:i + 900]
            out.update(dict(self.stream.execute(f"SELECT id, addr FROM wallets WHERE id IN ({','.join(map(str, ch))})")))
        return out

    def funding(self, addrs: list[str], resolve: bool) -> dict:
        info = {}
        for a in addrs:
            r = self.cache.execute("SELECT * FROM wallet_funding WHERE wallet=?", (a,)).fetchone()
            if r and r["status"] != "blad":
                info[a] = dict(r)
            elif resolve and self.helius_budget():
                if self.helius is None:
                    self.helius = self.rf.Helius(4)
                before = self.helius.calls
                res = self.rf.resolve(self.helius, a)
                self.cache.execute("INSERT OR REPLACE INTO wallet_funding VALUES(?,?,?,?,?,?)",
                                   (a, res["status"], res.get("funder"), res.get("first_ts"), res.get("sig_times"), time.time()))
                self.cache.commit()
                day = f"helius:{time.strftime('%Y-%m-%d')}"
                self.set_meta(day, self.meta(day, 0) + self.helius.calls - before)
                info[a] = {"wallet": a, **res}
        return info

    def hubs(self) -> set:
        return {r[0] for r in self.cache.execute(
            "SELECT funder FROM wallet_funding WHERE funder IS NOT NULL GROUP BY funder HAVING COUNT(*) >= ?", (F.HUB_MIN,))}

    def history(self, wids) -> dict:
        out: dict = {}
        if not wids:
            return out
        q = (f"SELECT wallet_id, MIN(CASE WHEN buy=1 THEN ts END), MIN(CASE WHEN buy=0 THEN ts END), MAX(ts), "
             f"SUM(CASE WHEN buy=1 THEN sol ELSE 0 END), SUM(CASE WHEN buy=0 THEN sol ELSE 0 END) FROM trades "
             f"WHERE ts < 2000000000 AND wallet_id IN ({','.join(map(str, wids))}) GROUP BY wallet_id, mint_id")
        for w, a, b, c, d, e in self.stream.execute(q):
            out.setdefault(w, []).append((a, b, c, d or 0, e or 0))
        return out

    # ---------------------------------------------------------------- skład pierwszych kupujących
    def evaluate(self, mint: str, decision_id: int, t: float, resolve: bool):
        import collector
        m = self.stream.execute("SELECT id, created_ts, created_slot, creator FROM mints WHERE mint=?", (mint,)).fetchone()
        if not m or m["created_ts"] is None or m["created_ts"] > t:
            self.out.execute("INSERT OR REPLACE INTO token_fb(mint, decision_id, ts_eval, status, ts) VALUES(?,?,?,?,?)",
                             (mint, decision_id, t, "brak_historii_krzywej", time.time()))
            self.out.commit()
            return
        self.refresh_routers()
        tr = [tuple(r) for r in self.stream.execute(
            "SELECT slot, ts, wallet_id, buy, sol, tok FROM trades WHERE mint_id=? AND ts <= ? ORDER BY slot", (m["id"], t))]
        ws = F.first_buyers(tr, self.routers)
        addr = self.addr_map(ws + [m["creator"]])
        info = self.funding([addr[w] for w in ws if w in addr] + ([addr[m["creator"]]] if m["creator"] in addr else []), resolve)
        rows = F.token_rows(tr, m["created_slot"], m["creator"], t, self.routers, addr.get, info, self.history(ws), self.hubs())
        comp = F.composition(rows)
        hole = int(bool(collector.data_holes(self.stream, m["created_ts"] - 60, t)))
        wallets = [{"addr": addr.get(r["wallet"]), "group": r["group"], "shared_funder": r["shared_funder"],
                    "by_creator": r["by_creator"], "is_creator": r["is_creator"], "young_insider_dump": r["young_insider_dump"],
                    "sold_5m": r["sold_5m"]} for r in rows]
        if m["creator"] in addr and not any(w["is_creator"] for w in wallets):
            wallets.append({"addr": addr[m["creator"]], "group": "creator", "shared_funder": 0, "by_creator": 0,
                            "is_creator": 1, "young_insider_dump": 0, "sold_5m": 0})
        self.out.execute(
            "INSERT OR REPLACE INTO token_fb VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mint, decision_id, t, "ok" if rows else "brak_kupujacych", comp.get("n_first"), comp.get("frac_insider"),
             comp.get("frac_smart"), comp.get("frac_sniper"), comp.get("frac_retail"), comp.get("frac_shared_funder"),
             comp.get("young_insider_dump"), comp.get("funding_known"), F.score(comp, self.model) if rows else None,
             hole, int(resolve), json.dumps({k: v for k, v in comp.items() if not isinstance(v, dict)}),
             json.dumps(wallets), time.time()))
        self.out.commit()

    def process_decisions(self) -> int:
        last = self.meta("last_decision_id", None)
        if last is None:                           # start: od bieżących decyzji (historia jest w analizach)
            last = (self.bot.execute("SELECT MAX(id) FROM decisions").fetchone()[0] or 0) - 50
        rows = self.bot.execute("SELECT id, ts, mint, decision FROM decisions WHERE id > ? ORDER BY id LIMIT 300",
                                (last,)).fetchall()
        for r in rows:
            self.out.execute("INSERT OR REPLACE INTO decision_fb VALUES(?,?,?,?)", (r["id"], r["ts"], r["mint"], r["decision"]))
            have = self.out.execute("SELECT ts_eval, funding_done, status FROM token_fb WHERE mint=?", (r["mint"],)).fetchone()
            tradeable = r["decision"] in TRADEABLE
            try:
                if not have:
                    self.evaluate(r["mint"], r["id"], r["ts"], tradeable)
                elif tradeable and not have[1] and have[2] == "ok":
                    self.evaluate(r["mint"], r["id"], have[0], True)        # dociągnij zasilenia, ta sama chwila t
            except Exception as e:                    # jeden token nie może zatrzymać logowania
                log(f"BŁĄD oceny {r['mint'][:8]}: {type(e).__name__}: {e}")
            last = r["id"]
        self.set_meta("last_decision_id", last)
        return len(rows)

    # ---------------------------------------------------------------- sprzedaże w trakcie pozycji
    def process_sells(self) -> int:
        if time.time() - self.last_sells < POLL_SELLS_S:
            return 0
        self.last_sells = time.time()
        opened = {}
        for r in self.bot.execute("SELECT mint, MIN(opened_ts) FROM positions WHERE status='open' GROUP BY mint"):
            opened[r[0]] = r[1]
        n = 0
        for mint, t0 in opened.items():
            pr = self.bot.execute("SELECT pair FROM decisions WHERE mint=? AND pair IS NOT NULL ORDER BY ts DESC LIMIT 1",
                                  (mint,)).fetchone()
            if not pr:
                continue
            fb = self.out.execute("SELECT wallets FROM token_fb WHERE mint=?", (mint,)).fetchone()
            ws = {w["addr"]: w for w in json.loads(fb[0] or "[]")} if fb and fb[0] else {}
            for tr in self.gecko.pool_trades(pr[0]):
                if tr.get("kind") != "sell":
                    continue
                try:
                    ts = datetime.fromisoformat(str(tr["block_timestamp"]).replace("Z", "+00:00")).timestamp()
                except (KeyError, ValueError):
                    continue
                if ts < t0:
                    continue
                a = tr.get("tx_from_address")
                usd = float(tr.get("volume_in_usd") or 0)
                w = ws.get(a)
                flags = (int(bool(w) and w["group"] == "insider"), int(bool(w) and bool(w["shared_funder"])),
                         int(bool(w) and bool(w["is_creator"])), int(bool(w)), int(bool(w) and bool(w["young_insider_dump"])))
                if any(flags) or usd >= BIG_SELL_USD:
                    cur = self.out.execute("INSERT OR IGNORE INTO holding_sells VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                           (tr.get("tx_hash"), mint, ts, a, usd, *flags, time.time()))
                    n += cur.rowcount
        self.out.commit()
        return n

    def images_loop(self):
        """7.10: cache grafik nowych tokenów (Helius DAS getAssetBatch, 10 kredytów / do 1000 tokenów) co 10 min -
        z niego portfel safety_nocopy (launchcheck.py) wie, czy grafika jest skopiowana. Osobny wątek: jedno zapytanie
        trwa do ~50 s. Pobiera tokeny z ostatnich 70 h (okno kopii 60 h), których jeszcze nie ma w cache."""
        import threading
        from analizy import copycoins as CC

        def loop():
            stream = ro(DATA / "stream.db")
            h = self.rf.Helius(2)
            while True:
                try:
                    db = CC.cache()
                    have = {r[0] for r in db.execute("SELECT mint FROM asset WHERE ts > ?", (time.time() - 80 * 3600,))}
                    todo = [r[0] for r in stream.execute("SELECT mint FROM mints WHERE created_ts > ?",
                                                         (time.time() - 70 * 3600,)) if r[0] not in have]
                    done = 0
                    for i in range(0, len(todo), 1000):
                        ch = todo[i:i + 1000]
                        r = h.call("getAssetBatch", {"ids": ch})
                        if r is None:
                            break
                        CC.store(db, ch, r)
                        done += len(ch)
                    if done:
                        log(f"grafiki: +{done} tokenów w cache ({(done + 999) // 1000 * 10} kredytów)")
                    db.close()
                except Exception:
                    log("BŁĄD grafik: " + traceback.format_exc().replace("\n", " | ")[-300:])
                time.sleep(600)

        threading.Thread(target=loop, daemon=True, name="grafiki").start()

    def run(self, once: bool = False):
        log(f"start loggera: model scoringu {'OK' if self.model else 'BRAK'}, limit Helius {HELIUS_DAILY_CAP}/dobę")
        if not once:
            self.images_loop()
        while True:
            try:
                nd = self.process_decisions()
                ns = self.process_sells()
                if nd or ns:
                    tot = self.out.execute("SELECT COUNT(*) FROM token_fb").fetchone()[0]
                    log(f"decyzji {nd}, sprzedaży w trakcie pozycji {ns} | tokenów ze składem: {tot}, "
                        f"Helius dziś {self.meta('helius:' + time.strftime('%Y-%m-%d'), 0)}")
            except sqlite3.Error as e:
                log(f"BŁĄD bazy ({e}) - ponowię")
            except Exception:
                log("BŁĄD: " + traceback.format_exc().replace("\n", " | ")[-400:])
            if once:
                return
            time.sleep(POLL_DECISIONS_S)


def stats():
    c = sqlite3.connect(OUT_DB)
    print("tokenów:", dict(c.execute("SELECT status, COUNT(*) FROM token_fb GROUP BY status").fetchall()))
    print("decyzji:", c.execute("SELECT COUNT(*) FROM decision_fb").fetchone()[0])
    print("sprzedaży w trakcie pozycji:", c.execute(
        "SELECT COUNT(*), SUM(insider), SUM(shared_funder), SUM(creator), SUM(first_buyer) FROM holding_sells").fetchone())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.stats:
        stats()
    else:
        Logger().run(once=a.once)


if __name__ == "__main__":
    main()
