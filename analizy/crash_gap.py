"""0. LUKA PRZY KRACHU - czy szybszy odczyt ceny (stan puli przez Helius co 2/5/10 s) zmniejszyłby stratę przy krachu.

    python -m analizy.crash_gap plan             # ile pozycji i okien do pobrania
    python -m analizy.crash_gap fetch [--rps 4]  # SOL/USD (GeckoTerminal) + transakcje puli w oknach (Helius)
    python -m analizy.crash_gap report

JAK PAPER TRADING LICZY DZIŚ SPRZEDAŻ PRZY KRACHU (bot.py manage_positions + paper.py):
  * pętla pozycji: co position_loop_seconds = 10 s, ale w tym samym wątku co skan nowych tokenów (co 45 s), więc
    faktyczny odstęp bywa dłuższy (migawki co >= 60 s mają medianę 68,5 s -> pętla średnio co ~20 s);
  * w każdym obiegu cena z DexScreenera (pairs) - ta potrafi być opóźniona o dziesiątki sekund;
  * co exit_probe_seconds = 20 s kwotowanie Jupitera sprzedaży CAŁEJ pozycji = "cena wykonalna" (exec_price),
    od której liczone są SL i TP, jeśli ma <= 50 s; gdy wartość z kwotowania < 50% wartości z ceny DexScreenera
    -> wyjście "exit_gap";
  * sprzedaż: kwotowanie Jupitera z tej chwili (albo kwotowanie z próby <= 5 s), wpływy = kwotowanie x 0.99
    (poślizg "z życia") - $0.05 priority fee. Żadna transakcja nie jest wysyłana - fill = cena z kwotowania.
  Realna egzekucja byłaby GORSZA: od kwotowania do wylądowania transakcji mija ~1-3 s (podpis, wysłanie, blok),
  a w krachu cena w tym czasie dalej spada; transakcja z limitem poślizgu może się nie wykonać (ponowienie = kolejne
  sekundy); kwotowanie Jupitera opiera się na stanie puli sprzed chwili. Mierzymy to niżej na transakcjach puli.

SYMULACJA (pozycje bota, bez zamkniętych przy odtwarzaniu przerwy):
  * stan puli PumpSwap (rezerwy tokena i SOL) po każdej transakcji z oknach wokół minut, w których świeca (archiwum
    bota) zeszła do poziomu stopa; cena USD = rezerwy x SOL/USD (świece minutowe SOL/USDC z GeckoTerminala);
  * odczyt co P s (2/5/10/20) z losową fazą (10 faz), stan widziany z opóźnieniem 0.4 s (1 slot); gdy wartość
    sprzedaży całej reszty pozycji (stały iloczyn, prowizja puli 0.3%) <= poziom stopa -> sprzedaż; transakcja
    ląduje po D s (bazowo 1.5 s; też 0.5 i 3 s) po cenie z tamtej chwili; koszty jak w paper (x 0.99, - $0.05);
  * szybki odczyt DOKŁADAMY do obecnego bota: wyjście = wcześniejsze z (szybki stop, faktyczne wyjście). Dzięki temu
    widać obie strony: lepsza cena na krachach i nowe "fałszywe stopy" na krótkich knotach, których bot nie złapał.
  * nie symulujemy szybszego TP / trailingu (tylko stały stop) - efekt TP po stronie zysków pominięty.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import math
import sqlite3
import statistics
import time

from analizy import common as C

CACHE = C.DATA / "analizy_cache.db"
WSOL = "So11111111111111111111111111111111111111112"
SOL_USDC_POOL = "58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2"     # Raydium SOL/USDC
POOL_FEE = 0.003
READ_LAG = 0.4
POLLS = (2, 5, 10, 20)
DELAYS = (0.5, 1.5, 3.0)
BASE_DELAY = 1.5
PHASES = 10
CRASH_EXITS = ("stop_loss", "exit_gap", "liq_drain")
PRE_S, POST_S = 20, 70          # okno transakcji wokół minuty-kandydata: [m - 20 s, m + 70 s]
MARGIN = 1.03                   # świeca-kandydat: dołek <= poziom stopa x 1.03 (resztę rozstrzygają transakcje)
MAX_WIN = 8                     # max okien-kandydatów na pozycję (najwcześniejsze)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sol_usd(ts INTEGER PRIMARY KEY, c REAL);
CREATE TABLE IF NOT EXISTS pool_tx(pool TEXT, slot INTEGER, idx INTEGER, bt INTEGER, pre_tok REAL, pre_sol REAL,
  post_tok REAL, post_sol REAL, PRIMARY KEY(pool, slot, idx));
CREATE TABLE IF NOT EXISTS pool_win(pool TEXT, t0 INTEGER, t1 INTEGER, status TEXT, n INTEGER, credits INTEGER, ts REAL,
  PRIMARY KEY(pool, t0, t1));
"""


def cache() -> sqlite3.Connection:
    c = sqlite3.connect(CACHE, timeout=120)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


# ------------------------------------------------------------------ pozycje i okna
def positions() -> list[dict]:
    db = C.ro("bot.db")
    trades = collections.defaultdict(list)
    for r in db.execute("SELECT position_id, ts, side, qty, usd, reason FROM trades ORDER BY ts"):
        trades[r[0]].append(dict(r))
    pairs: dict = {}
    out = []
    for p in db.execute("SELECT * FROM positions WHERE status='closed' ORDER BY opened_ts"):
        reason = p["exit_reason"] or ""
        sells = [t for t in trades.get(p["id"], []) if t["side"] == "SELL"]
        if reason.startswith("przerwa") or not sells:
            continue                  # zamknięte przy odtwarzaniu przerwy ze świec (bot był wyłączony)
        key = (p["mint"], int(p["opened_ts"]) // 600)
        if key not in pairs:
            r = db.execute("SELECT pair FROM decisions WHERE mint=? AND pair IS NOT NULL ORDER BY ABS(ts-?) LIMIT 1",
                           (p["mint"], p["opened_ts"])).fetchone()
            pairs[key] = r[0] if r else None
        s = p["strategy"] or "hybrid"
        sl = C.CFG.strategy_exits.get(s, {}).get("stop_loss_pct", C.CFG.stop_loss_pct)
        out.append({"id": p["id"], "s": s, "mint": p["mint"], "pool": pairs[key], "t0": p["opened_ts"],
                    "t1": p["closed_ts"], "reason": reason, "entry": p["entry_price"], "qty0": p["qty_initial"],
                    "cost": p["cost_usd"], "pnl": p["realized_usd"] - p["cost_usd"], "sl": sl,
                    "L": p["entry_price"] * (1 - sl / 100), "sells": sells, "ts": p["opened_ts"]})
    return out


def merge(iv: list) -> list:
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def plan_windows(poss: list[dict]) -> dict:
    """Okna transakcji na pozycję (p['windows']) i scalone okna na pulę (do pobrania)."""
    db = C.ro("bot.db")
    per_pool = collections.defaultdict(list)
    for p in poss:
        p["windows"], p["has_candles"] = [], False
        if not p["pool"]:
            continue
        rows = db.execute("SELECT ts, l FROM candles WHERE pool=? AND ts BETWEEN ? AND ? ORDER BY ts",
                          (p["pool"], int(p["t0"] // 60 * 60), int(p["t1"]))).fetchall()
        p["has_candles"] = bool(rows)
        cand = [int(r[0]) for r in rows if r[1] and r[1] <= p["L"] * MARGIN][:MAX_WIN]
        iv = [[m - PRE_S, m + POST_S] for m in cand]
        if p["reason"] in CRASH_EXITS:                     # zawsze okno wokół faktycznej sprzedaży
            iv.append([int(p["t1"]) - 90, int(p["t1"]) + 15])
        iv = [[max(a, int(p["t0"]) - 5), b] for a, b in iv if a < p["t1"] + 15]
        p["windows"] = merge(iv)
        per_pool[p["pool"]] += [list(w) for w in p["windows"]]
    return {pool: merge(iv) for pool, iv in per_pool.items()}


# ------------------------------------------------------------------ pobieranie
def vault_state(tx: dict, pool: str, mint: str):
    meta = tx.get("meta") or {}

    def bal(side):
        tok = sol = None
        for b in meta.get(side) or []:
            if b.get("owner") != pool:
                continue
            ui = b.get("uiTokenAmount") or {}
            amt = float(ui.get("amount") or 0) / 10 ** int(ui.get("decimals") or 0)
            if b.get("mint") == WSOL:
                sol = amt
            elif b.get("mint") == mint:
                tok = amt
        return tok, sol

    pre, post = bal("preTokenBalances"), bal("postTokenBalances")
    if None in pre or None in post:
        return None
    return (*pre, *post)


def fetch_window(h, pool: str, mint: str, t0: int, t1: int):
    rows, token, credits, n = [], None, 0, 0
    while True:
        opts = {"transactionDetails": "full", "sortOrder": "asc", "limit": 1000,
                "filters": {"blockTime": {"gte": int(t0), "lte": int(t1)}, "status": "succeeded"}}
        if token:
            opts["paginationToken"] = token
        r = h.call("getTransactionsForAddress", [pool, opts])
        if r is None:
            return rows, credits, n, "blad"
        d = r.get("data") or []
        n += len(d)
        credits += max(10, math.ceil(len(d) / 100) * 10)
        for x in d:
            st = vault_state(x, pool, mint)
            if st and x.get("blockTime"):
                rows.append((pool, x["slot"], x.get("transactionIndex") or 0, x["blockTime"], *st))
        token = r.get("paginationToken")
        if not token or not d:
            return rows, credits, n, ("ok" if n == 0 or rows else "nie_pumpswap")


def fetch_sol(t_from: float, t_to: float):
    from sources import GeckoTerminal
    cfg = C.Config()
    cfg.gecko_rpm = 6
    g = GeckoTerminal(cfg)
    db = cache()
    before = int(t_to) + 120
    while before > t_from:
        cs = g.ohlcv(SOL_USDC_POOL, limit=1000, before=before)
        if not cs:
            print("SOL/USD: brak świec dla", time.strftime('%d.%m %H:%M', time.localtime(before)))
            break
        db.executemany("INSERT OR REPLACE INTO sol_usd VALUES(?,?)", [(int(c[0]), float(c[4])) for c in cs])
        db.commit()
        before = int(cs[0][0])
    n, a, b = db.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM sol_usd").fetchone()
    print(f"SOL/USD: {n} świec {time.strftime('%d.%m %H:%M', time.localtime(a))} - "
          f"{time.strftime('%d.%m %H:%M', time.localtime(b))}", flush=True)


def fetch(rps: float, reverse: bool = False):
    import rug_funding as rf
    poss = positions()
    pools = plan_windows(poss)
    if not reverse:
        fetch_sol(min(p["t0"] for p in poss) - 3600, max(p["t1"] for p in poss) + 600)
    mint_of = {p["pool"]: p["mint"] for p in poss if p["pool"]}
    db = cache()
    done = {(r[0], r[1], r[2]) for r in db.execute("SELECT pool, t0, t1 FROM pool_win WHERE status != 'blad'")}
    todo = [(pool, a, b) for pool, iv in pools.items() for a, b in iv if (pool, a, b) not in done]
    if reverse:                       # drugi proces od końca listy (zapytania Heliusa trwają do ~1 min)
        todo = todo[::-1]
    print(f"okien do pobrania: {len(todo)} (pul {len(pools)})", flush=True)
    h = rf.Helius(rps)
    credits = 0
    for i, (pool, a, b) in enumerate(todo, 1):
        if reverse and db.execute("SELECT 1 FROM pool_win WHERE pool=? AND t0=? AND t1=? AND status != 'blad'",
                                  (pool, a, b)).fetchone():
            break                     # spotkaliśmy pierwszy proces
        rows, cr, n, status = fetch_window(h, pool, mint_of[pool], a, b)
        credits += cr
        db.executemany("INSERT OR IGNORE INTO pool_tx VALUES(?,?,?,?,?,?,?,?)", rows)
        db.execute("INSERT OR REPLACE INTO pool_win VALUES(?,?,?,?,?,?,?)", (pool, a, b, status, n, cr, time.time()))
        db.commit()
        if i % 50 == 0 or i == len(todo):
            print(f"{time.strftime('%H:%M:%S')} {i}/{len(todo)} kredytów ~{credits} (zapytań {h.calls})", flush=True)


# ------------------------------------------------------------------ symulacja
def virtual_sol(rows: list) -> float | None:
    """Wirtualna rezerwa SOL puli PumpSwap: pula liczy wymianę tak, jakby w skarbcu było o V SOL więcej (stały iloczyn
    na (tokeny, SOL + V); sprawdzone 6.10: k na samych saldach spada przy każdej sprzedaży, a z V jest stałe; V ~17-18 SOL,
    stałe w oknie i między oknami tej samej puli). Z każdej wymiany: V = dSOL * (tok_przed + dTok) / dTok - SOL_przed."""
    vs = []
    for r in rows:
        dt, ds = r["post_tok"] - r["pre_tok"], r["pre_sol"] - r["post_sol"]
        if r["pre_tok"] > 0 and abs(dt) >= 1e-4 * r["pre_tok"] and dt * ds > 0:
            vs.append(ds * (r["pre_tok"] + dt) / dt - r["pre_sol"])
    return statistics.median(vs) if len(vs) >= 5 else None


class PoolPath:
    """Stan puli w czasie z pobranych okien: state(x) = EFEKTYWNE rezerwy (tokeny, SOL + V) w chwili x albo None."""

    def __init__(self, rows: list, wins: list):
        self.wins = sorted((a, b) for a, b in wins)
        rows = sorted(rows, key=lambda r: (r["slot"], r["idx"]))
        vw = {w: virtual_sol([r for r in rows if w[0] <= r["bt"] <= w[1]]) for w in self.wins}
        known = [v for v in vw.values() if v is not None]
        v_pool = statistics.median(known) if known else 17.5
        self.v = {w: (v if v is not None else v_pool) for w, v in vw.items()}
        first_slot: dict = {}
        self.t, self.post, self.pre = [], [], []
        for r in rows:
            fs = first_slot.setdefault(r["bt"], r["slot"])
            self.t.append(r["bt"] + min(0.4 * (r["slot"] - fs), 0.95))
            w = self.window_of(r["bt"])
            v = self.v.get(w, v_pool) if w else v_pool
            self.pre.append((r["pre_tok"], r["pre_sol"] + v))
            self.post.append((r["post_tok"], r["post_sol"] + v))

    def window_of(self, x: float):
        i = bisect.bisect_right(self.wins, (x, float("inf"))) - 1
        return self.wins[i] if i >= 0 and self.wins[i][0] <= x <= self.wins[i][1] else None

    def state(self, x: float):
        w = self.window_of(x)
        if not w:
            return None
        i = bisect.bisect_right(self.t, x) - 1
        if i >= 0 and self.t[i] >= w[0]:
            return self.post[i]
        j = bisect.bisect_left(self.t, w[0])                 # przed pierwszą transakcją okna: stan sprzed niej
        return self.pre[j] if j < len(self.t) and self.t[j] <= w[1] else None


def sol_price(sol: dict, keys: list, x: float) -> float | None:
    i = bisect.bisect_right(keys, x) - 1
    return sol[keys[i]] if i >= 0 and x - keys[i] <= 600 else None


def value_usd(st, qty: float, s: float) -> float:
    tok, sol = st
    q = qty * (1 - POOL_FEE)
    return sol * q / (tok + q) * s if tok > 0 and q > 0 else 0.0


def load_paths(poss: list[dict]) -> dict:
    db = cache()
    wins = collections.defaultdict(list)
    for r in db.execute("SELECT pool, t0, t1 FROM pool_win WHERE status='ok'"):
        wins[r[0]].append((r[1], r[2]))
    rows = collections.defaultdict(list)
    need = {p["pool"] for p in poss if p["pool"] in wins}
    for r in db.execute("SELECT * FROM pool_tx"):
        if r["pool"] in need:
            rows[r["pool"]].append(r)
    return {pool: PoolPath(rows[pool], wins[pool]) for pool in need}


def state_before(p: dict, x: float) -> tuple[float, float]:
    """(ilość tokenów w pozycji, zrealizowane $) tuż przed chwilą x - z faktycznych sprzedaży."""
    done = [s for s in p["sells"] if s["ts"] < x]
    return p["qty0"] - sum(s["qty"] for s in done), sum(s["usd"] for s in done)


def sim_position(p: dict, path: PoolPath, sol, keys, poll: float, delay: float, confirm: int = 1) -> tuple[float, int]:
    """Średni wynik $ pozycji (po fazach) z dołożonym szybkim stopem; drugi element = ile faz wyszło wcześniej.
    confirm = ile kolejnych odczytów musi być pod stopem (1 = od razu; 2 = odporność na jednorazowy knot)."""
    extra, pri = C.CFG.extra_slippage_pct / 100, C.CFG.priority_fee_usd
    res, early = [], 0
    for j in range(PHASES):
        phi = j * poll / PHASES
        out = None
        for a, b in p["windows"]:
            tau = phi + math.ceil((max(a, p["t0"]) - phi) / poll) * poll
            below = 0
            while tau <= b and out is None:
                if tau + delay >= p["t1"]:                    # faktyczne wyjście było wcześniej
                    break
                st = path.state(tau - READ_LAG)
                s = sol_price(sol, keys, tau)
                if st and s:
                    qty, realized = state_before(p, tau)
                    if qty > 1e-9 and value_usd(st, qty, s) / qty <= p["L"]:
                        below += 1
                        if below >= confirm:
                            st2 = path.state(tau + delay) or st
                            proceeds = max(value_usd(st2, qty, sol_price(sol, keys, tau + delay) or s) * (1 - extra) - pri, 0.0)
                            out = realized + proceeds - p["cost"]
                    else:
                        below = 0
                tau += poll
            if out is not None:
                break
        if out is None:
            out = p["pnl"]
        else:
            early += 1
        res.append(out)
    return statistics.mean(res), early


def crash_metrics(p: dict, path: PoolPath, sol, keys) -> dict | None:
    """Dla faktycznej sprzedaży krachowej: kalibracja (kwotowanie paper / wartość z puli), opóźnienie wykrycia
    (od ostatniego przebicia stopa w transakcjach do sprzedaży) i dalszy spadek 1/2/3 s po kwotowaniu."""
    last = p["sells"][-1]
    t1 = last["ts"]
    qty = last["qty"]
    s = sol_price(sol, keys, t1)
    st = path.state(t1)
    if not (s and st and qty > 0):
        return None
    v0 = value_usd(st, qty, s)
    quoted = (last["usd"] + C.CFG.priority_fee_usd) / (1 - C.CFG.extra_slippage_pct / 100)
    out = {"calib": quoted / v0 if v0 > 0 else None}
    for d in (1, 2, 3):
        st2 = path.state(t1 + d)
        out[f"fall_{d}s"] = value_usd(st2, qty, s) / v0 - 1 if st2 and v0 > 0 else None
    # ostatnie przebicie poziomu stopa (z góry w dół) przed sprzedażą, w oknie sprzedaży
    w = path.window_of(t1)
    cross = None
    if w:
        i1 = bisect.bisect_right(path.t, t1) - 1
        above = None
        for i in range(bisect.bisect_left(path.t, w[0]), i1 + 1):
            v = value_usd(path.post[i], qty, sol_price(sol, keys, path.t[i]) or s) / qty
            if v > p["L"]:
                above = True
            elif above:
                cross, above = path.t[i], False
        out["first_below_in_window"] = cross is None and value_usd(path.state(w[0]) or st, qty, s) / qty <= p["L"]
    out["delay_s"] = t1 - cross if cross else None
    out["overshoot"] = (last["usd"] / qty) / p["L"] - 1 if p["L"] > 0 else None
    return out


def report() -> str:
    poss = positions()
    plan_windows(poss)
    db = cache()
    sol = {r[0]: r[1] for r in db.execute("SELECT ts, c FROM sol_usd")}
    keys = sorted(sol)
    paths = load_paths(poss)
    ok = [p for p in poss if p["pool"] in paths]
    crash = [p for p in ok if p["reason"] in CRASH_EXITS]
    out = ["## 0. Luka przy krachu - szybszy odczyt ceny puli\n", HOW]
    cover = collections.Counter("bez puli" if not p["pool"] else ("bez świec" if not p["has_candles"] else
                                ("ok" if p["pool"] in paths else "pula nie-PumpSwap / brak transakcji")) for p in poss)
    out.append(f"Pozycje bota (bez odtworzeń przerwy): {len(poss)}; z odtworzoną ceną puli: **{len(ok)}** "
               f"({', '.join(f'{k} {v}' for k, v in cover.most_common())}); w tym wyjścia krachowe "
               f"(stop_loss / exit_gap / liq_drain): {len(crash)}.\n")
    # --- opis obecnego mechanizmu liczbami
    cm = [m for p in crash if (m := crash_metrics(p, paths[p["pool"]], sol, keys))]
    cal = sorted(m["calib"] for m in cm if m.get("calib"))
    dl = sorted(m["delay_s"] for m in cm if m.get("delay_s") is not None)
    ov = [m["overshoot"] for m in cm if m.get("overshoot") is not None]
    rows = [["kalibracja: kwotowanie paper / wartość z puli w tej sekundzie (mediana, p25-p75)",
             f"{len(cal)}{C.rel(len(cal))}", f"{cal[len(cal) // 2]:.3f} ({cal[len(cal) // 4]:.3f}-{cal[3 * len(cal) // 4]:.3f})" if cal else "—"],
            ["opóźnienie: od przebicia stopa w transakcjach puli do sprzedaży paper (mediana, p75, p90)",
             f"{len(dl)}{C.rel(len(dl))}", f"{dl[len(dl) // 2]:.0f} s, {dl[3 * len(dl) // 4]:.0f} s, {dl[int(len(dl) * .9)]:.0f} s" if dl else "—"],
            ["cena sprzedaży paper względem poziomu stopa (średnio, mediana)", f"{len(ov)}{C.rel(len(ov))}",
             f"{C.pct(C.mean(ov))}, {C.pct(C.median(ov))}"]]
    for d in (1, 2, 3):
        f = [m[f"fall_{d}s"] for m in cm if m.get(f"fall_{d}s") is not None]
        rows.append([f"realna egzekucja: zmiana wartości sprzedaży {d} s po kwotowaniu (średnio, mediana)",
                     f"{len(f)}{C.rel(len(f))}", f"{C.pct(C.mean(f))}, {C.pct(C.median(f))}"])
    out.append("**Obecny mechanizm w liczbach (wyjścia krachowe):**\n")
    out.append(C.table(["miara", "N", "wartość"], rows))
    out.append("\nJak to czytać: kwotowanie paper zgadza się ze stanem puli w tej samej sekundzie (kalibracja ~0,99 = prowizje), "
               "więc paper NIE zawyża ceny sprzedaży. \"Luka przy krachu\" z części 7 (4,6 pp na pozycję) jest liczona "
               "względem ceny z DexScreenera, która w krachu jest nieaktualna - to głównie spadek, który wydarzył się PRZED "
               "wykryciem (stop przebity średnio kilkanaście sekund wcześniej), a nie koszt samej sprzedaży. Realna "
               "transakcja byłaby gorsza tylko o dalszy spadek w 1-3 s po kwotowaniu (wiersze wyżej) plus ryzyko "
               "nieudanej transakcji przy limicie poślizgu (nie do zmierzenia na danych). Odzyskać da się tylko część "
               "przez szybsze wykrycie - symulacja niżej.\n")
    # --- symulacja
    ex, te = C.split_time(ok)
    exset = {p["id"] for p in ex}
    out.append(f"\n**Symulacja: szybki stop z odczytu puli dołożony do bota** (wszystkie {len(ok)} pozycje z ceną puli; "
               f"eksploracja {len(ex)}, TEST {len(te)}; wynik w pp stawki na pozycję i w $ łącznie)\n")
    rows = []
    res = {}
    variants = [(poll, delay, 1) for poll in POLLS for delay in DELAYS if delay == BASE_DELAY or poll in (2, 5)]
    variants += [(2, BASE_DELAY, 2), (5, BASE_DELAY, 2)]
    for poll, delay, conf in variants:
        d = {}
        for p in ok:
            d[p["id"]] = sim_position(p, paths[p["pool"]], sol, keys, poll, delay, conf)
        res[(poll, delay, conf)] = d
        for lbl, sel in (("wszystkie", ok), ("eksploracja", ex), ("TEST", te)):
            if lbl != "wszystkie" and delay != BASE_DELAY:
                continue
            ch = lambda p: (d[p["id"]][0] - p["pnl"]) / p["cost"]
            cr = [ch(p) for p in sel if p["reason"] in CRASH_EXITS]
            fs = [p for p in sel if p["reason"] not in CRASH_EXITS and d[p["id"]][1] > 0]
            rows.append([f"co {poll} s" + (f", {conf} odczyty z rzędu" if conf > 1 else ""), f"{delay:.1f} s", lbl,
                         f"{len(sel)}", f"{C.mean(cr) * 100:+.1f} pp (N {len(cr)})",
                         f"{len(fs)} poz., śr. {C.mean([ch(p) for p in fs]) * 100:+.0f} pp, "
                         f"{sum(d[p['id']][0] - p['pnl'] for p in fs):+,.0f} $" if fs else "0",
                         f"**{C.mean([ch(p) for p in sel]) * 100:+.1f} pp**",
                         f"{sum(d[p['id']][0] - p['pnl'] for p in sel):+,.0f}"])
    out.append(C.table(["odczyt puli", "lądowanie tx", "zbiór", "N pozycji", "zmiana na wyjściach krachowych (na pozycję)",
                        "nowe fałszywe stopy (pozycje bez krachu)", "zmiana na pozycję (wszystkie)", "$ łącznie"], rows))
    # --- po strategiach (odczyt 2 s i 5 s, lądowanie 1.5 s)
    out.append("\n**Według strategii (wynik $ faktyczny -> z szybkim stopem):**\n")
    st = collections.defaultdict(list)
    for p in ok:
        st[p["s"]].append(p)
    rows = []
    for s, ps in sorted(st.items(), key=lambda kv: sum(p["pnl"] for p in kv[1])):
        rows.append([s, f"{len(ps)}", f"{sum(p['pnl'] for p in ps):+,.0f}",
                     f"{sum(res[(2, BASE_DELAY, 1)][p['id']][0] for p in ps):+,.0f}",
                     f"{sum(res[(5, BASE_DELAY, 1)][p['id']][0] for p in ps):+,.0f}",
                     f"{sum(res[(10, BASE_DELAY, 1)][p['id']][0] for p in ps):+,.0f}",
                     f"{C.mean([res[(2, BASE_DELAY, 1)][p['id']][0] / p['cost'] for p in ps]) * 100:+.1f}%"])
    out.append(C.table(["strategia", "pozycji", "$ faktycznie", "$ odczyt co 2 s", "$ co 5 s", "$ co 10 s",
                        "śr. na pozycję (2 s)"], rows))
    rep = [p for p in ok if p["s"] == "random_eligible"]
    for poll in (2, 5, 10):
        d = res[(poll, BASE_DELAY, 1)]
        f = lambda sel: C.mean([(d[p["id"]][0] - p["pnl"]) / p["cost"] for p in sel])
        C.SUMMARY.append([f"luka przy krachu (część 0): szybki stop z odczytu puli co {poll} s, transakcja po "
                          f"{BASE_DELAY} s, dołożony do bota", f"{f(ex) * 100:+.1f} pp na pozycję (N {len(ex)})",
                          f"{f(te) * 100:+.1f} pp na pozycję (N {len(te)})",
                          f"na pozycjach random_eligible {f(rep) * 100:+.1f} pp (N {len(rep)})",
                          "symulacja: poprawa w obu połowach" if f(ex) > 0 and f(te) > 0 else "symulacja: brak stałej poprawy"])
    return "\n".join(out)


HOW = """
**Jak paper trading liczy dziś cenę sprzedaży przy krachu** (bot.py `manage_positions`, paper.py `sell`):

| krok | jak jest | skutek przy krachu |
|---|---|---|
| pętla pozycji | co 10 s, ale w jednym wątku ze skanem nowych tokenów (co 45 s) - migawki pozycji (zapis co >= 60 s) mają medianę 68,5 s, czyli pętla średnio co ~20 s | spadek między obiegami widać dopiero w następnym obiegu |
| cena do stopów | kwotowanie Jupitera sprzedaży całej pozycji co 20 s ("cena wykonalna", ważna 50 s); bez niego cena z DexScreenera | DexScreener spóźnia się o dziesiątki sekund; kwotowanie co 20 s |
| exit_gap | kwotowanie < 50% wartości z ceny DexScreenera -> natychmiastowe wyjście | to są krachy głębsze niż 50% między dwoma kwotowaniami |
| cena sprzedaży | NOWE kwotowanie Jupitera (lub z próby <= 5 s) x 0,99 - $0,05 | fill = kwotowanie z chwili decyzji, bez wysyłania transakcji |

**Czy realna egzekucja byłaby gorsza? Tak.** Od kwotowania do wylądowania transakcji mija ~1-3 s (podpis, wysłanie,
blok), w krachu cena w tym czasie dalej spada; transakcja z limitem poślizgu może się nie wykonać (ponowienie = kolejne
sekundy); Jupiter kwotuje ze stanu puli sprzed chwili. Ile to kosztuje - wiersze "realna egzekucja" niżej (zmierzone
na transakcjach puli w sekundach po kwotowaniu paper).
"""


def plan():
    poss = positions()
    pools = plan_windows(poss)
    n_iv = sum(len(v) for v in pools.values())
    secs = sum(b - a for v in pools.values() for a, b in v)
    with_w = [p for p in poss if p["windows"]]
    print(f"pozycji {len(poss)}, z pulą {sum(1 for p in poss if p['pool'])}, ze świecami "
          f"{sum(1 for p in poss if p['has_candles'])}, z oknami {len(with_w)} "
          f"(krachowe {sum(1 for p in with_w if p['reason'] in CRASH_EXITS)}, inne {sum(1 for p in with_w if p['reason'] not in CRASH_EXITS)})")
    print(f"pul {len(pools)}, okien scalonych {n_iv}, łącznie {secs / 60:.0f} min transakcji")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "fetch", "report"])
    ap.add_argument("--rps", type=float, default=4)
    ap.add_argument("--reverse", action="store_true")
    a = ap.parse_args()
    if a.cmd == "plan":
        plan()
    elif a.cmd == "fetch":
        fetch(a.rps, a.reverse)
    else:
        print(report())


if __name__ == "__main__":
    main()
