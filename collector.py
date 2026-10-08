"""Własny strumień danych pump.fun ("własny DexScreener"): każda transakcja na krzywej bondingowej pump.fun, nowe tokeny
i graduacje - prosto z blockchaina, przez DARMOWY websocket publicznego RPC Solany (logsSubscribe na programie pump.fun).

    python collector.py              # zbiera do data/stream.db; co minutę wpis w data/collector.log
    python collector.py --probe 20   # 20 s podglądu: dekodowanie zdarzeń i kontrola pól (bez zapisu)
    python collector.py --stats      # podsumowanie bazy (bez łączenia)

Ten sam zapis służy do obserwacji na żywo i do backtestów (np. copy trading: copytrade.py): po każdej transakcji mamy
portfel, kwoty, opłaty i stan krzywej (wirtualne rezerwy), a z nich dokładną cenę i poślizg dowolnego zlecenia.

Ograniczenia darmowego źródła (świadome):
  * publiczny RPC nie gwarantuje kompletności - zerwane połączenie = luka; zapisujemy ją w tabeli gaps, żeby analizy
    wiedziały, gdzie brakuje danych;
  * opóźnienie ~2 s od czasu bloku (zmierzone 4.10.2026: mediana 2.1 s);
  * handel PO graduacji (PumpSwap) nie jest jeszcze zbierany - token po graduacji znika z naszego strumienia.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import sqlite3
import statistics
import struct
import time
from pathlib import Path

import websockets

BASE = Path(__file__).parent
DB_PATH = BASE / "data" / "stream.db"
LOG_PATH = BASE / "data" / "collector.log"
RPC_WS = "wss://api.mainnet-beta.solana.com"
HOLE_S = 5.0     # tyle sekund (czas bloku) bez żadnej transakcji pump.fun = zgubione dane (normalnie ~30-50 transakcji/s)
PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
EVENTS = ("TradeEvent", "CreateEvent", "CompleteEvent", "CompletePumpAmmMigrationEvent")
DISC = {hashlib.sha256(f"event:{n}".encode()).digest()[:8]: n for n in EVENTS}
# krzywa pump.fun: 1 mld tokenów (6 miejsc), na krzywej sprzedaje się 793.1 mln; start wirtualnych rezerw tokena 1.073 mld
INITIAL_VTOK = 1_073_000_000 * 10 ** 6
CURVE_TOKENS = 793_100_000 * 10 ** 6
MAX_INT = 2 ** 63                 # SQLite INTEGER = 64 bity ze znakiem; u64 z łańcucha może być większy
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

SCHEMA = """
CREATE TABLE IF NOT EXISTS mints(id INTEGER PRIMARY KEY, mint TEXT UNIQUE, name TEXT, symbol TEXT, creator INTEGER,
                                 created_ts INTEGER, created_slot INTEGER);
CREATE TABLE IF NOT EXISTS wallets(id INTEGER PRIMARY KEY, addr TEXT UNIQUE);
-- jedna transakcja na krzywej: kwoty w lamportach / surowych jednostkach tokena; vsol/vtok = rezerwy PO transakcji;
-- fee_bps = łączna opłata (protokół + twórca) w punktach bazowych
CREATE TABLE IF NOT EXISTS trades(slot INTEGER, ts INTEGER, mint_id INTEGER, wallet_id INTEGER, buy INTEGER,
                                  sol INTEGER, tok INTEGER, vsol INTEGER, vtok INTEGER, fee_bps INTEGER);
CREATE INDEX IF NOT EXISTS ix_trades_ts ON trades(ts);
CREATE TABLE IF NOT EXISTS events(slot INTEGER, ts INTEGER, mint_id INTEGER, kind TEXT, wallet_id INTEGER);
CREATE TABLE IF NOT EXISTS gaps(start REAL, end REAL, reason TEXT);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


def b58(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = _B58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s


def _string(d: bytes, o: int) -> tuple[str, int]:
    n = struct.unpack_from("<I", d, o)[0]
    return d[o + 4:o + 4 + n].decode("utf-8", "replace"), o + 4 + n


def parse(raw: bytes) -> dict | None:
    """Zdarzenie pump.fun z linii 'Program data: <base64>' -> słownik (albo None, gdy to nie nasze/uszkodzone)."""
    kind = DISC.get(raw[:8])
    try:
        if kind == "TradeEvent":
            o = 8
            mint = b58(raw[o:o + 32]); o += 32
            sol, tok = struct.unpack_from("<QQ", raw, o); o += 16
            buy = raw[o]; o += 1
            user = b58(raw[o:o + 32]); o += 32
            ts, vsol, vtok = struct.unpack_from("<qQQ", raw, o); o += 24
            fee_bps, mayhem = 0, None
            if len(raw) >= o + 16 + 32 + 16 + 32 + 16:       # real reserves, fee_recipient, fee_bps+fee, creator, creator fee
                o += 16 + 32
                fee_bps = struct.unpack_from("<Q", raw, o)[0]; o += 16 + 32
                fee_bps += struct.unpack_from("<Q", raw, o)[0]; o += 16
                # track_volume, 4 x u64, ix_name (string), mayhem_mode (wg IDL pump.fun, 34 pola)
                if len(raw) >= o + 1 + 32 + 4:
                    _, o2 = _string(raw, o + 1 + 32)
                    if len(raw) > o2:
                        mayhem = raw[o2]
            return {"kind": kind, "mint": mint, "sol": sol, "tok": tok, "buy": int(bool(buy)), "user": user, "ts": ts,
                    "vsol": vsol, "vtok": vtok, "fee_bps": fee_bps, "mayhem": mayhem}
        if kind == "CreateEvent":
            name, o = _string(raw, 8)
            symbol, o = _string(raw, o)
            _, o = _string(raw, o)                                  # uri
            mint = b58(raw[o:o + 32]); o += 64                      # mint, bonding_curve
            user = b58(raw[o:o + 32]); o += 32
            creator = b58(raw[o:o + 32]) if len(raw) >= o + 40 else user
            if len(raw) >= o + 40:
                o += 32
            ts = struct.unpack_from("<q", raw, o)[0] if len(raw) >= o + 8 else 0
            # po timestamp: 4 x u64 rezerw/podaży, token_program, is_mayhem_mode
            mayhem = raw[o + 8 + 32 + 32] if len(raw) > o + 8 + 32 + 32 else None
            return {"kind": kind, "mint": mint, "name": name[:64], "symbol": symbol[:32], "user": creator, "ts": ts,
                    "mayhem": mayhem}
        if kind == "CompleteEvent":                                 # graduacja: krzywa wypełniona
            user, mint = b58(raw[8:40]), b58(raw[40:72])
            ts = struct.unpack_from("<q", raw, 104)[0]
            return {"kind": kind, "mint": mint, "user": user, "ts": ts}
        if kind == "CompletePumpAmmMigrationEvent":                 # przeniesienie płynności do PumpSwap
            user, mint = b58(raw[8:40]), b58(raw[40:72])
            return {"kind": kind, "mint": mint, "user": user, "ts": 0}
    except (struct.error, IndexError, UnicodeDecodeError):
        return None
    return None


def pump_data(logs: list[str]):
    """Bajty z linii 'Program data:' wyemitowanych przez SAM pump.fun (śledzimy stos wywołań programów).
    Subskrypcja daje całe transakcje, w których pojawia się pump.fun, a zdarzenie Anchora "TradeEvent" ma ten sam
    dyskryminator w każdym programie: 4.10 Raydium LaunchLab (LanMV9...) wywołany w tej samej transakcji dał 3 śmieciowe
    transakcje z czasem rzędu 10^18, które zepsuły MAX(ts) (wykrywanie przerw, copytrade --hours, --stats)."""
    stack: list[str] = []
    for line in logs:
        if line.startswith("Program data: "):
            if stack and stack[-1] == PUMP:
                try:
                    yield base64.b64decode(line[14:])
                except ValueError:                    # uszkodzony base64 (binascii.Error)
                    pass
            continue
        p = line.split(" ", 3)
        if len(p) >= 3 and p[0] == "Program" and not p[1].endswith(":"):     # nie "Program log: invoke ..."
            if p[2] == "invoke":
                stack.append(p[1])
            elif p[2] in ("success", "failed:") and stack:
                stack.pop()


def progress(vtok: int) -> float:
    """Postęp krzywej 0..1 (1 = graduacja) z wirtualnych rezerw tokena po transakcji."""
    return min(max((INITIAL_VTOK - vtok) / CURVE_TOKENS, 0.0), 1.0)


class Store:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        if "mayhem" not in {r[1] for r in self.db.execute("PRAGMA table_info(mints)")}:
            self.db.execute("ALTER TABLE mints ADD COLUMN mayhem INTEGER")      # od 4.10: tokeny w trybie mayhem
        self.mayhem = {i for (i,) in self.db.execute("SELECT id FROM mints WHERE mayhem=1")}
        self.new_mayhem: set = set()
        self.mints = {m: i for i, m in self.db.execute("SELECT id, mint FROM mints")}
        self.wallets = {a: i for i, a in self.db.execute("SELECT id, addr FROM wallets")}
        self.next_mint = max(self.mints.values(), default=0) + 1
        self.next_wallet = max(self.wallets.values(), default=0) + 1
        self.new_mints: list = []
        self.new_wallets: list = []
        self.trades: list = []
        self.events: list = []
        self.creates: list = []
        self.bad = 0              # pominięte zdarzenia z liczbami poza zakresem
        self.last_ts = None       # najpóźniejszy czas BLOKU odebranej transakcji (wykrywanie dziur)
        self.holes: list = []

    def wid(self, addr: str) -> int:
        i = self.wallets.get(addr)
        if i is None:
            i = self.wallets[addr] = self.next_wallet
            self.next_wallet += 1
            self.new_wallets.append((i, addr))
        return i

    def mid(self, mint: str) -> int:
        i = self.mints.get(mint)
        if i is None:
            i = self.mints[mint] = self.next_mint
            self.next_mint += 1
            self.new_mints.append([i, mint, None, None, None, None, None])
        return i

    def add(self, ev: dict, slot: int, store_trades: bool = True):
        k = ev["kind"]
        if k == "TradeEvent":
            if not ev["vsol"] or not ev["vtok"]:     # rzadkie zdarzenia z zerową rezerwą (inny typ krzywej?) - bez ceny
                return
            if max(ev["sol"], ev["tok"], ev["vsol"], ev["vtok"]) >= MAX_INT:
                self.bad += 1                         # u64 poza zakresem SQLite (4.10 10:30 to zabiło zbieracza)
                if self.bad <= 3:
                    log(f"pominięto zdarzenie z liczbą poza zakresem: {ev}")
                return
            if not 0 <= ev["fee_bps"] <= 10_000:
                ev = dict(ev, fee_bps=0)              # nieznana opłata (analizy przyjmą wtedy 1,25%)
            self._mark_mayhem(ev)
            ts = ev["ts"]
            if ts and self.last_ts is not None and ts - self.last_ts > HOLE_S:
                self.holes.append((self.last_ts, ts))
            if ts:
                self.last_ts = ts if self.last_ts is None else max(self.last_ts, ts)
            if store_trades:
                self.trades.append((slot, ev["ts"], self.mid(ev["mint"]), self.wid(ev["user"]), ev["buy"], ev["sol"],
                                    ev["tok"], ev["vsol"], ev["vtok"], ev["fee_bps"]))
        elif k == "CreateEvent":
            self.creates.append((ev["mint"], ev["name"], ev["symbol"], self.wid(ev["user"]), ev["ts"], slot))
            self.mid(ev["mint"])
            self._mark_mayhem(ev)
        else:
            self.events.append((slot, ev["ts"] or int(time.time()), self.mid(ev["mint"]),
                                "complete" if k == "CompleteEvent" else "migrate", self.wid(ev["user"])))

    def _mark_mayhem(self, ev: dict):
        """Tryb mayhem pump.fun (osobny typ tokenów, część bez opłat) - ~30% transakcji 4.10; zaznaczamy token,
        żeby analizy (ranking portfeli, etapy) mogły go wydzielić."""
        if ev.get("mayhem") == 1:
            i = self.mid(ev["mint"])
            if i not in self.mayhem:
                self.mayhem.add(i)
                self.new_mayhem.add(i)

    def flush(self):
        db = self.db
        try:
            with db:
                if self.new_wallets:
                    db.executemany("INSERT OR IGNORE INTO wallets(id, addr) VALUES(?,?)", self.new_wallets)
                if self.new_mints:
                    db.executemany("INSERT OR IGNORE INTO mints(id, mint, name, symbol, creator, created_ts, "
                                   "created_slot) VALUES(?,?,?,?,?,?,?)", self.new_mints)
                for mint, name, symbol, creator, ts, slot in self.creates:
                    db.execute("UPDATE mints SET name=?, symbol=?, creator=?, created_ts=?, created_slot=? WHERE id=?",
                               (name, symbol, creator, ts, slot, self.mints[mint]))
                if self.new_mayhem:                    # po dodaniu nowych tokenów - inaczej UPDATE trafia w pustkę
                    db.executemany("UPDATE mints SET mayhem=1 WHERE id=?", [(i,) for i in self.new_mayhem])
                if self.trades:
                    db.executemany("INSERT INTO trades VALUES(?,?,?,?,?,?,?,?,?,?)", self.trades)
                if self.events:
                    db.executemany("INSERT INTO events VALUES(?,?,?,?,?)", self.events)
                if self.holes:
                    db.executemany("INSERT INTO gaps VALUES(?,?,?)",
                                   [(a, b, "dziura w danych (czas bloku)") for a, b in self.holes])
        except (sqlite3.Error, OverflowError, ValueError) as e:
            # błąd zapisu nie może zatrzymać zbierania: tracimy jedną paczkę (~2 s), nie resztę dnia
            log(f"BŁĄD zapisu paczki ({type(e).__name__}: {e}) - pominięto {len(self.trades)} transakcji")
            try:                                       # identyfikatory i tak muszą trafić do bazy (mapy w pamięci je mają)
                with db:
                    db.executemany("INSERT OR IGNORE INTO wallets(id, addr) VALUES(?,?)", self.new_wallets)
                    db.executemany("INSERT OR IGNORE INTO mints(id, mint, name, symbol, creator, created_ts, "
                                   "created_slot) VALUES(?,?,?,?,?,?,?)", self.new_mints)
            except sqlite3.Error:
                pass
        n = len(self.trades)
        self.new_wallets, self.new_mints, self.trades, self.events, self.creates = [], [], [], [], []
        self.new_mayhem, self.holes = set(), []
        return n

    def gap(self, start: float, end: float, reason: str):
        with self.db:
            self.db.execute("INSERT INTO gaps VALUES(?,?,?)", (start, end, reason))

    def meta(self, k: str, v):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v)))


def log(msg: str):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


async def run(max_gb: float, url: str = RPC_WS, path: Path = DB_PATH):
    st = Store(path)
    # indeksy dla fb_logger.py i analiz (6.10): tworzone TYLKO tutaj, przy starcie zbieracza, zanim zacznie pisać -
    # utworzenie indeksu na żywej bazie (np. z --stats) zablokowałoby zapisy i zgubiło transakcje
    have = {r[0] for r in st.db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    for name, col in (("ix_trades_wallet", "wallet_id"), ("ix_trades_mint", "mint_id")):
        if name not in have:
            log(f"tworzę indeks {name} (jednorazowo, może potrwać kilka minut)")
            with st.db:
                st.db.execute(f"CREATE INDEX IF NOT EXISTS {name} ON trades({col})")
    last_msg = st.db.execute("SELECT MAX(ts) FROM trades").fetchone()[0]
    if last_msg and time.time() - last_msg > 5:
        st.gap(last_msg, time.time(), "przerwa w działaniu zbieracza")
    st.meta("started", time.time())
    reconnects, backoff = 0, 2.0
    counts = {"trade": 0, "create": 0, "complete": 0, "migrate": 0}
    lags: list[float] = []
    t_stat, t_flush = time.time(), time.time()
    full = False
    while True:
        try:
            async with websockets.connect(url, max_size=2 ** 24, ping_interval=20, ping_timeout=30) as ws:
                await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                                          "params": [{"mentions": [PUMP]}, {"commitment": "confirmed"}]}))
                await asyncio.wait_for(ws.recv(), timeout=15)
                # luki po zerwaniu zapisuje Store.add w CZASIE BLOKU (dziura między transakcjami > HOLE_S). Do 5.10
                # liczono je w czasie odbioru: przy opóźnieniu 30 s zerwanie gubiło 30 s transakcji, a luka miała 2 s
                backoff = 2.0
                log(f"połączono z {url} (reconnectów: {reconnects})")
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                    now = time.time()
                    res = (msg.get("params") or {}).get("result") or {}
                    v, slot = res.get("value") or {}, (res.get("context") or {}).get("slot", 0)
                    if v.get("err"):
                        continue
                    for raw in pump_data(v.get("logs") or []):
                        ev = parse(raw)
                        if not ev:
                            continue
                        st.add(ev, slot, store_trades=not full)
                        k = {"TradeEvent": "trade", "CreateEvent": "create", "CompleteEvent": "complete"}.get(ev["kind"], "migrate")
                        counts[k] += 1
                        if k == "trade" and ev["ts"]:
                            lags.append(now - ev["ts"])
                    if now - t_flush >= 2:
                        st.flush()
                        t_flush = now
                    if now - t_stat >= 60:
                        size_gb = sum(os.path.getsize(p) for p in (path, Path(str(path) + "-wal")) if p.exists()) / 1e9
                        if size_gb > max_gb and not full:
                            full = True
                            log(f"UWAGA: baza ma {size_gb:.1f} GB > limit {max_gb} GB - przestaję zapisywać transakcje "
                                f"(nowe tokeny i graduacje dalej)")
                        lag = statistics.median(lags) if lags else float("nan")
                        log(f"minuta: transakcji {counts['trade']}, nowych tokenów {counts['create']}, graduacji "
                            f"{counts['complete']}, opóźnienie mediana {lag:.1f} s | portfeli {len(st.wallets)}, tokenów "
                            f"{len(st.mints)}, baza {size_gb:.2f} GB, reconnecty {reconnects}")
                        st.meta("last_stats", {"ts": now, **counts, "lag": lag, "reconnects": reconnects})
                        counts = {k: 0 for k in counts}
                        lags, t_stat = [], now
        except Exception as e:      # zerwane połączenie ALBO nieprzewidziany błąd: zapisz, odczekaj, połącz ponownie
            st.flush()
            reconnects += 1
            expected = isinstance(e, (websockets.WebSocketException, asyncio.TimeoutError, OSError, json.JSONDecodeError))
            log(f"{'rozłączono' if expected else 'BŁĄD'} ({type(e).__name__}: {str(e)[:160]}) - ponowna próba za "
                f"{backoff:.0f} s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


async def probe(seconds: int, url: str = RPC_WS):
    """Podgląd bez zapisu: czy pola się dekodują i są spójne (opłata ~ 1%, cena z rezerw = cena transakcji)."""
    seen: dict = {}
    checks = []
    async with websockets.connect(url, max_size=2 ** 24) as ws:
        await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                                  "params": [{"mentions": [PUMP]}, {"commitment": "confirmed"}]}))
        await ws.recv()
        t0 = time.time()
        lags: list[float] = []
        while time.time() - t0 < seconds:
            msg = json.loads(await ws.recv())
            v = ((msg.get("params") or {}).get("result") or {}).get("value") or {}
            if v.get("err"):
                continue
            for raw in pump_data(v.get("logs") or []):
                ev = parse(raw)
                if ev:
                    if ev["kind"] == "TradeEvent" and ev["ts"]:
                        lags.append(time.time() - ev["ts"])
                    seen.setdefault(ev["kind"], ev)
                    if ev["kind"] == "TradeEvent" and (not ev["vsol"] or not ev["vtok"]):
                        seen.setdefault("TradeEvent_bez_rezerw", dict(ev, len=len(raw)))
                    elif ev["kind"] == "TradeEvent" and ev["tok"]:
                        fill = ev["sol"] / ev["tok"]                 # cena tej transakcji (lamport / jednostka)
                        spot = ev["vsol"] / ev["vtok"]               # cena z rezerw po transakcji
                        checks.append((ev["fee_bps"], fill / spot))
    print(json.dumps(seen, indent=1, ensure_ascii=False)[:2000])
    if lags:
        print(f"\n{url}: transakcji {len(lags)} w {seconds} s ({len(lags) / seconds:.1f}/s), opóźnienie od bloku: "
              f"mediana {statistics.median(lags):.1f} s, p90 {sorted(lags)[int(len(lags) * 0.9)]:.1f} s")
    if checks:
        fees = [c[0] for c in checks]
        ratio = sorted(c[1] for c in checks)
        print(f"\ntransakcji: {len(checks)}; opłata (bps) mediana {statistics.median(fees)}, min {min(fees)}, max {max(fees)}")
        print(f"cena transakcji / cena z rezerw po niej: mediana {ratio[len(ratio) // 2]:.3f} (blisko 1 = pola się zgadzają)")


def data_holes(db, t0: float | None = None, t1: float | None = None, min_s: float = HOLE_S) -> list[tuple[float, float]]:
    """Dziury w danych liczone z SAMYCH transakcji (czas bloku): odstępy > min_s bez żadnej transakcji. Źródło prawdy
    dla analiz - tabela gaps do 5.10.2026 zapisywała luki w czasie odbioru i pomijała większość strat (patrz README)."""
    q, args = "SELECT DISTINCT ts FROM trades WHERE ts < 2000000000", []
    if t0 is not None:
        q, args = q + " AND ts >= ?", args + [t0]
    if t1 is not None:
        q, args = q + " AND ts <= ?", args + [t1]
    ts = [r[0] for r in db.execute(q + " ORDER BY ts", args)]
    return [(a, b) for a, b in zip(ts, ts[1:]) if b - a > min_s]


def stats():
    st = Store()
    db = st.db
    n, t0, t1 = db.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM trades").fetchone()
    print(f"transakcji: {n:,}  od {time.strftime('%d.%m %H:%M', time.localtime(t0 or 0))} do "
          f"{time.strftime('%d.%m %H:%M', time.localtime(t1 or 0))}")
    print(f"tokenów: {len(st.mints):,} (z datą startu: {db.execute('SELECT COUNT(*) FROM mints WHERE created_ts IS NOT NULL').fetchone()[0]:,})"
          f", portfeli: {len(st.wallets):,}")
    print("zdarzenia:", dict(db.execute("SELECT kind, COUNT(*) FROM events GROUP BY kind").fetchall()))
    holes = data_holes(db)
    big = [h for h in holes if h[1] - h[0] > 1800]
    small = [h for h in holes if h[1] - h[0] <= 1800]
    print(f"dziury w danych (czas bloku, > {HOLE_S:.0f} s bez transakcji): przerwy > 30 min: {len(big)} "
          f"({sum(b - a for a, b in big) / 3600:.1f} h), krótkie: {len(small)} ({sum(b - a for a, b in small) / 60:.0f} min)")
    by_day: dict = {}
    for a, b in small:
        k = time.strftime("%d.%m", time.localtime(a))
        by_day[k] = by_day.get(k, 0) + (b - a)
    if by_day:
        print("  krótkie dziury wg dnia: " + ", ".join(f"{k} {v / 60:.0f} min" for k, v in by_day.items()))
    print(f"rozmiar: {DB_PATH.stat().st_size / 1e9:.2f} GB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", type=int, help="podgląd przez tyle sekund, bez zapisu")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--max-gb", type=float, default=8.0, help="limit rozmiaru bazy (potem bez zapisu transakcji)")
    ap.add_argument("--url", default=RPC_WS, help="websocket RPC Solany (domyślnie publiczny mainnet-beta)")
    ap.add_argument("--db", type=Path, default=DB_PATH, help="baza (np. osobna do porównania serwerów RPC)")
    a = ap.parse_args()
    if a.db != DB_PATH:                 # instancja testowa: własny log, żeby nie mieszać z głównym zbieraczem
        global LOG_PATH
        LOG_PATH = a.db.with_suffix(".log")
    if a.stats:
        stats()
    elif a.probe:
        asyncio.run(probe(a.probe, a.url))
    else:
        log(f"start zbieracza: {a.db} (limit {a.max_gb} GB, {a.url})")
        try:
            asyncio.run(run(a.max_gb, a.url, a.db))
        except KeyboardInterrupt:
            log("zatrzymano")


if __name__ == "__main__":
    main()
