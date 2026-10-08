"""Papierowy skaner arbitrażu między pulami DEX na Solanie (7.10.2026).

Pytanie: czy atomowy arbitraż "kup na DEX A, sprzedaj na DEX B w jednej transakcji" na memecoinach z naszej niszy
zostawia zysk po kosztach. ZERO transakcji i kluczy - tylko kwotowania. Flash loan na Solanie nie jest potrzebny do
pomiaru (atomowa transakcja i tak się wycofa przy stracie); jego koszt to parametr FLASH_FEE_BPS.

Obieg (osobny proces, bez wpływu na bota):
  1. wszechświat = tokeny, które bot oglądał w ostatnich 24 h z płynnością >= $10k (bot.db, tylko odczyt)
     + migracje pump.fun z ostatnich 6 h (stream.db, tylko odczyt);
  2. pule tokena z DexScreenera (token-pairs) - tylko pary token/SOL z płynnością >= $1k, bez zamkniętej krzywej pump.fun;
     program puli (-> etykieta DEX-u Jupitera) z publicznego RPC;
  3. przesiew: różnica cen między pulami wg DexScreenera; >= SCREEN_BPS albo losowo co SAMPLE_EVERY-ta para ->
     weryfikacja kwotowaniami Jupitera ograniczonymi do jednego DEX-u (onlyDirectRoutes): kup na A za X SOL, sprzedaj
     na B otrzymane tokeny; oba kierunki przy najmniejszej kwocie, większe kwoty dla zyskownego kierunku;
  4. zysk brutto = SOL z powrotem - X (fee pul i price impact są w kwotowaniu), netto = minus opłata sieci, priority
     fee, napiwek Jito (minimalny i "konkurencyjny" = połowa zysku), flash loan. Zyskowne -> ponowne kwotowanie po
     RECHECK_S (czy okazja w ogóle żyje dłużej niż chwilę).
     Ograniczenie: Jupiter wybiera NAJLEPSZĄ pulę danego DEX-u, nie konkretną - dwie pule tego samego DEX-u nie są
     rozdzielane (zapisane jako "ten sam DEX"), a różnica z DexScreenera na małej puli bywa tylko nieświeżą ceną.

Limity: Jupiter dzielimy z botem (bot <= 55/min) - tu najwyżej JUP_RPM, a po 429 pauza 10 min. DexScreener 20/min.

    python -u arb_scan.py run       # skaner (log data/arb_out.log przy starcie przez Start-Process)
    python arb_scan.py report       # podsumowanie -> analizy/ARBITRAZ.md
"""
from __future__ import annotations

import itertools
import json
import random
import sqlite3
import sys
import time
from pathlib import Path

import requests

from sources import RateLimiter

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
WSOL = "So11111111111111111111111111111111111111112"
DEX = "https://api.dexscreener.com/token-pairs/v1/solana/"
JUP = "https://lite-api.jup.ag/swap/v1/quote"
JUP_LABELS = "https://lite-api.jup.ag/swap/v1/program-id-to-label"
RPC = "https://api.mainnet-beta.solana.com"
UA = "memecoin-paper-bot/0.1 arb-scan"

DEX_RPM, JUP_RPM, RPC_RPM = 20, 6, 10
JUP_PAUSE_S = 600
UNIVERSE_H, UNIVERSE_LIQ, MIG_H = 24, 10_000, 6
POOL_MIN_LIQ = 1_000
TTL_MULTI_S, TTL_SINGLE_S = 180, 3600
SCREEN_BPS, SAMPLE_EVERY = 50, 10
SIZES_SOL = (0.1, 0.5, 2.0)
RECHECK_S = 10
SLIPPAGE_BPS = 50
# koszty transakcji arbitrażowej (SOL): opłata podstawowa 5000 lamportów, priority fee, minimalny napiwek Jito
BASE_FEE, PRIORITY_FEE, TIP_MIN = 5_000e-9, 10_000e-9, 1_000e-9
TIP_COMPETITIVE = 0.5        # boty arbitrażowe oddają walidatorom zwykle 50-90% zysku - przyjmujemy dolną granicę
FLASH_FEE_BPS = 0.0          # pożyczka flash na Solanie (np. Kamino / MarginFi) - pomijalna albo 0; parametr


def net_profit(gross_sol: float, size_sol: float) -> tuple[float, float]:
    """(netto przy minimalnym napiwku, netto przy napiwku konkurencyjnym) dla zysku brutto z jednej transakcji."""
    fixed = BASE_FEE + PRIORITY_FEE + size_sol * FLASH_FEE_BPS / 1e4
    n_min = gross_sol - fixed - TIP_MIN
    n_comp = gross_sol - fixed - max(TIP_MIN, TIP_COMPETITIVE * gross_sol) if gross_sol > 0 else n_min
    return n_min, n_comp


def spread_bps(p_lo: float, p_hi: float) -> float:
    return (p_hi / p_lo - 1) * 1e4 if p_lo > 0 else 0.0


def eligible_pools(mint: str, pairs: list) -> list[dict]:
    """Pule token/SOL z płynnością >= POOL_MIN_LIQ, bez krzywej pump.fun (po migracji zamknięta, handlu brak)."""
    out = []
    for p in pairs or []:
        if (p.get("baseToken") or {}).get("address") != mint or (p.get("quoteToken") or {}).get("address") != WSOL:
            continue
        if p.get("dexId") == "pumpfun":
            continue
        liq = float((p.get("liquidity") or {}).get("usd") or 0)
        try:
            price = float(p.get("priceNative") or 0)
        except ValueError:
            price = 0.0
        if liq >= POOL_MIN_LIQ and price > 0 and p.get("pairAddress"):
            out.append({"pool": p["pairAddress"], "dex_id": p.get("dexId"), "labels": ",".join(p.get("labels") or []),
                        "liq": liq, "price": price})
    return out


SCHEMA = """
CREATE TABLE IF NOT EXISTS pools(pool TEXT PRIMARY KEY, mint TEXT, dex_id TEXT, ds_labels TEXT, program TEXT, label TEXT,
  liq_usd REAL, price REAL, seen_ts REAL);
CREATE TABLE IF NOT EXISTS checked(mint TEXT PRIMARY KEY, ts REAL, n_pools INTEGER);
CREATE TABLE IF NOT EXISTS screens(id INTEGER PRIMARY KEY, ts REAL, mint TEXT, pool_lo TEXT, pool_hi TEXT, label_lo TEXT,
  label_hi TEXT, spread_bps REAL, liq_min_usd REAL, verify INTEGER, why TEXT);
CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY, ts REAL, screen_id INTEGER, mint TEXT, buy_label TEXT,
  sell_label TEXT, size_sol REAL, tokens INTEGER, sol_back REAL, gross_sol REAL, net_min_sol REAL, net_comp_sol REAL,
  recheck_of INTEGER, status TEXT);
CREATE TABLE IF NOT EXISTS events(ts REAL, kind TEXT, info TEXT);
"""


class Scanner:
    def __init__(self, db_path: Path = DATA / "arb.db"):
        self.db = sqlite3.connect(db_path, timeout=60)
        self.db.executescript(SCHEMA)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.dex_lim, self.jup_lim, self.rpc_lim = RateLimiter(DEX_RPM), RateLimiter(JUP_RPM), RateLimiter(RPC_RPM)
        self.jup_paused_until = 0.0
        self.labels: dict[str, str] = {}
        self.rng = random.Random(20261007)

    def log(self, kind: str, info: str):
        print(f"{time.strftime('%H:%M:%S')} {kind}: {info}", flush=True)
        self.db.execute("INSERT INTO events VALUES (?,?,?)", (time.time(), kind, info))
        self.db.commit()

    # --- źródła ---
    def universe(self) -> list[str]:
        now = time.time()
        bot = sqlite3.connect(f"file:{DATA / 'bot.db'}?mode=ro", uri=True, timeout=30)
        mints = [r[0] for r in bot.execute(
            "SELECT mint, MAX(ts) t FROM decisions WHERE ts > ? AND liq >= ? GROUP BY mint ORDER BY t DESC",
            (now - UNIVERSE_H * 3600, UNIVERSE_LIQ))]
        bot.close()
        st = sqlite3.connect(f"file:{DATA / 'stream.db'}?mode=ro", uri=True, timeout=30)
        mig = [r[0] for r in st.execute(
            "SELECT m.mint FROM events e JOIN mints m ON m.id = e.mint_id WHERE e.kind='migrate' AND e.ts > ? "
            "ORDER BY e.ts DESC", (now - MIG_H * 3600,))]
        st.close()
        return list(dict.fromkeys(mig + mints))

    def pairs(self, mint: str):
        self.dex_lim.wait()
        try:
            r = self.s.get(DEX + mint, timeout=20)
        except requests.RequestException:
            return None
        if r.status_code == 429:
            self.log("dexscreener_429", mint)
            time.sleep(30)
            return None
        return r.json() if r.status_code == 200 else None

    def resolve_labels(self, pools: list[str]):
        todo = [p for p in pools if not self.db.execute("SELECT 1 FROM pools WHERE pool=? AND label IS NOT NULL",
                                                         (p,)).fetchone()]
        if not todo:
            return
        if not self.labels:
            self.jup_lim.wait()
            self.labels = self.s.get(JUP_LABELS, timeout=20).json()
        self.rpc_lim.wait()
        try:
            res = self.s.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
                                         "params": [todo, {"encoding": "base64", "dataSlice": {"offset": 0, "length": 0}}]},
                              timeout=20).json()["result"]["value"]
        except (requests.RequestException, KeyError, TypeError, ValueError):
            return
        for pool, acc in zip(todo, res):
            if acc:
                owner = acc.get("owner")
                self.db.execute("UPDATE pools SET program=?, label=? WHERE pool=?",
                                (owner, self.labels.get(owner, "?" + owner[:6]), pool))
        self.db.commit()

    def quote(self, in_mint: str, out_mint: str, amount: int, label: str):
        """(stan, outAmount): 'ok' | 'noroute' | 'error' | 'paused'."""
        if time.time() < self.jup_paused_until:
            return "paused", 0
        self.jup_lim.wait()
        try:
            r = self.s.get(JUP, params={"inputMint": in_mint, "outputMint": out_mint, "amount": str(int(amount)),
                                        "slippageBps": SLIPPAGE_BPS, "dexes": label, "onlyDirectRoutes": "true"},
                           timeout=20)
        except requests.RequestException:
            return "error", 0
        if r.status_code == 429:
            self.jup_paused_until = time.time() + JUP_PAUSE_S
            self.log("jupiter_429", f"pauza {JUP_PAUSE_S} s (bot ma pierwszeństwo)")
            return "paused", 0
        if r.status_code in (400, 404):
            return "noroute", 0
        try:
            d = r.json()
            return ("ok", int(d["outAmount"])) if r.status_code == 200 and d.get("outAmount") else ("error", 0)
        except (ValueError, KeyError, TypeError):
            return "error", 0

    # --- pomiar ---
    def round_trip(self, mint: str, buy_label: str, sell_label: str, size: float, screen_id: int,
                   recheck_of: int | None = None) -> tuple[int | None, float | None]:
        st, tok = self.quote(WSOL, mint, int(size * 1e9), buy_label)
        back, gross, nm, nc = None, None, None, None
        if st == "ok":
            st, lam = self.quote(mint, WSOL, tok, sell_label)
            if st == "ok":
                back = lam / 1e9
                gross = back - size
                nm, nc = net_profit(gross, size)
        if st == "paused":
            return None, None
        cur = self.db.execute("INSERT INTO quotes(ts, screen_id, mint, buy_label, sell_label, size_sol, tokens, sol_back, "
                              "gross_sol, net_min_sol, net_comp_sol, recheck_of, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (time.time(), screen_id, mint, buy_label, sell_label, size, tok or None, back, gross, nm, nc,
                               recheck_of, st))
        self.db.commit()
        return cur.lastrowid, nm

    def verify(self, mint: str, a: dict, b: dict, screen_id: int):
        best = None
        for lo, hi in ((a, b), (b, a)):
            qid, nm = self.round_trip(mint, lo["label"], hi["label"], SIZES_SOL[0], screen_id)
            if qid is None:
                return
            if nm is not None and nm > 0:
                best = (lo, hi, SIZES_SOL[0], qid, nm)
                for size in SIZES_SOL[1:]:
                    q2, n2 = self.round_trip(mint, lo["label"], hi["label"], size, screen_id)
                    if q2 is not None and n2 is not None and n2 > best[4]:
                        best = (lo, hi, size, q2, n2)
        if best:
            lo, hi, size, qid, nm = best
            self.log("okazja", f"{mint[:8]} {lo['label']} -> {hi['label']} {size} SOL netto {nm:+.5f} SOL; "
                               f"ponowne kwotowanie za {RECHECK_S} s")
            time.sleep(RECHECK_S)
            self.round_trip(mint, lo["label"], hi["label"], size, screen_id, recheck_of=qid)

    def check_mint(self, mint: str):
        pairs = self.pairs(mint)
        if pairs is None:
            return
        now = time.time()
        pools = eligible_pools(mint, pairs)
        for p in pools:
            self.db.execute("INSERT INTO pools(pool, mint, dex_id, ds_labels, liq_usd, price, seen_ts) VALUES (?,?,?,?,?,?,?) "
                            "ON CONFLICT(pool) DO UPDATE SET liq_usd=excluded.liq_usd, price=excluded.price, "
                            "seen_ts=excluded.seen_ts", (p["pool"], mint, p["dex_id"], p["labels"], p["liq"], p["price"], now))
        self.db.execute("INSERT OR REPLACE INTO checked VALUES (?,?,?)", (mint, now, len(pools)))
        self.db.commit()
        if len(pools) < 2:
            return
        self.resolve_labels([p["pool"] for p in pools])
        for p in pools:
            p["label"] = (self.db.execute("SELECT label FROM pools WHERE pool=?", (p["pool"],)).fetchone() or [None])[0]
        rows = []
        for a, b in itertools.combinations(pools, 2):
            lo, hi = (a, b) if a["price"] <= b["price"] else (b, a)
            sp = spread_bps(lo["price"], hi["price"])
            if not lo["label"] or not hi["label"] or lo["label"].startswith("?") or hi["label"].startswith("?"):
                why = "DEX nieobsługiwany przez Jupitera"
            elif lo["label"] == hi["label"]:
                why = "ten sam DEX (kwotowanie nie rozdzieli pul)"
            else:
                why = None
            rows.append([lo, hi, sp, why])
        # kwotowania są drogie (limit dzielony z botem): weryfikujemy najwyżej JEDNĄ parę na token - największą różnicę
        ok = sorted((r for r in rows if r[3] is None), key=lambda r: -r[2])
        pick = None
        if ok:
            pick = ok[0]
            if pick[2] >= SCREEN_BPS:
                pick[3] = "różnica >= próg"
            elif self.rng.randrange(SAMPLE_EVERY) == 0:
                pick[3] = "próbka losowa (kontrola przesiewu)"
            else:
                pick = None
        for r in rows:
            if r[3] is None:
                r[3] = "poniżej progu" if r[2] < SCREEN_BPS else "różnica >= próg, nie najlepsza para"
        for lo, hi, sp, why in rows:
            ver = int(pick is not None and lo is pick[0] and hi is pick[1])
            cur = self.db.execute("INSERT INTO screens(ts, mint, pool_lo, pool_hi, label_lo, label_hi, spread_bps, "
                                  "liq_min_usd, verify, why) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                  (now, mint, lo["pool"], hi["pool"], lo["label"], hi["label"], sp,
                                   min(lo["liq"], hi["liq"]), ver, why))
            self.db.commit()
            if ver:
                sid = cur.lastrowid
        if pick is not None:
            self.verify(mint, pick[0], pick[1], sid)

    def due(self, mint: str, now: float) -> bool:
        r = self.db.execute("SELECT ts, n_pools FROM checked WHERE mint=?", (mint,)).fetchone()
        if not r:
            return True
        return now - r[0] >= (TTL_MULTI_S if r[1] >= 2 else TTL_SINGLE_S)

    def run(self):
        self.log("start", f"DexScreener {DEX_RPM}/min, Jupiter {JUP_RPM}/min, próg {SCREEN_BPS} bps, kwoty {SIZES_SOL} SOL")
        last_stats = time.time()
        while True:
            try:
                uni = self.universe()
                now = time.time()
                todo = [m for m in uni if self.due(m, now)]
                for mint in todo[:60]:
                    self.check_mint(mint)
                if time.time() - last_stats >= 600:
                    last_stats = time.time()
                    multi = self.db.execute("SELECT COUNT(*) FROM checked WHERE n_pools >= 2").fetchone()[0]
                    allm = self.db.execute("SELECT COUNT(*) FROM checked").fetchone()[0]
                    q = self.db.execute("SELECT COUNT(*), SUM(net_min_sol > 0) FROM quotes WHERE status='ok'").fetchone()
                    self.log("stan", f"wszechświat {len(uni)}, sprawdzonych {allm}, z >= 2 pulami {multi}, "
                                     f"kwotowań {q[0]}, zyskownych (min. koszty) {q[1] or 0}")
                if not todo:
                    time.sleep(20)
            except Exception as e:  # skaner pomiarowy - błąd jednego obiegu nie może go zabić
                self.log("błąd", repr(e)[:300])
                time.sleep(30)


def report() -> str:
    db = sqlite3.connect(f"file:{DATA / 'arb.db'}?mode=ro", uri=True)
    t0, t1 = db.execute("SELECT MIN(ts), MAX(ts) FROM events").fetchone()
    hours = (t1 - t0) / 3600 if t0 else 0
    n_checked = db.execute("SELECT COUNT(*) FROM checked").fetchone()[0]
    n_multi = db.execute("SELECT COUNT(*) FROM checked WHERE n_pools >= 2").fetchone()[0]
    out = [f"# Arbitraż między pulami DEX (paper) - stan {time.strftime('%d.%m.%Y %H:%M')}\n",
           f"Pomiar: {hours:.1f} h pracy skanera. Tokenów sprawdzonych {n_checked}, z >= 2 pulami token/SOL "
           f"(płynność >= ${POOL_MIN_LIQ}): {n_multi} ({n_multi / max(n_checked, 1):.0%}).\n",
           "## Przesiew (różnica cen wg DexScreenera)\n", "| powód | par | mediana różnicy bps | p90 bps |", "|---|---|---|---|"]
    for why, in db.execute("SELECT DISTINCT why FROM screens"):
        xs = sorted(r[0] for r in db.execute("SELECT spread_bps FROM screens WHERE why=?", (why,)))
        out.append(f"| {why} | {len(xs)} | {xs[len(xs) // 2]:.0f} | {xs[int(len(xs) * 0.9)]:.0f} |")
    out += ["\n## Weryfikacja kwotowaniami Jupitera (pierwsze kwotowanie, bez ponownych)\n",
            "| kwota SOL | kwotowań | brutto > 0 | netto > 0 (min. koszty) | netto > 0 (napiwek 50%) | mediana brutto % | "
            "max netto SOL |", "|---|---|---|---|---|---|---|"]
    for size in SIZES_SOL:
        rows = db.execute("SELECT gross_sol, net_min_sol, net_comp_sol FROM quotes WHERE status='ok' AND recheck_of IS NULL "
                          "AND size_sol=?", (size,)).fetchall()
        if not rows:
            continue
        g = sorted(r[0] / size for r in rows)
        out.append(f"| {size} | {len(rows)} | {sum(r[0] > 0 for r in rows)} | {sum(r[1] > 0 for r in rows)} | "
                   f"{sum(r[2] > 0 for r in rows)} | {g[len(g) // 2] * 100:+.2f}% | {max(r[1] for r in rows):+.5f} |")
    st = db.execute("SELECT status, COUNT(*) FROM quotes GROUP BY status").fetchall()
    out.append(f"\nStatusy kwotowań: {dict(st)} (noroute = Jupiter nie ma bezpośredniej trasy przez ten DEX).")
    rc = db.execute("SELECT q.net_min_sol, r.net_min_sol FROM quotes r JOIN quotes q ON q.id = r.recheck_of "
                    "WHERE r.status='ok'").fetchall()
    if rc:
        alive = sum(1 for a, b in rc if b is not None and b > 0)
        out.append(f"\nPonowne kwotowanie po {RECHECK_S} s: {len(rc)} okazji, nadal zyskownych {alive}.")
    days = max(hours / 24, 1e-9)
    tot = db.execute("SELECT COALESCE(SUM(net_min_sol), 0), COUNT(*) FROM quotes WHERE status='ok' AND net_min_sol > 0 "
                     "AND recheck_of IS NULL").fetchone()
    out.append(f"\n**Górna granica zysku** (każda okazja wzięta przez nas, bez konkurencji, min. koszty): "
               f"{tot[0]:.4f} SOL z {tot[1]} okazji = {tot[0] / days:.4f} SOL/dobę. Konkurencyjne boty (Jito, ms) "
               f"zabierają większość z nich - realnie mniej.")
    rej = db.execute("SELECT kind, COUNT(*) FROM events WHERE kind LIKE '%429%' GROUP BY kind").fetchall()
    if rej:
        out.append(f"\nOdmowy limitów: {dict(rej)}.")
    return "\n".join(out)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        Scanner().run()
    elif cmd == "report":
        txt = report()
        (ROOT / "analizy" / "ARBITRAZ.md").write_text(txt + "\n", encoding="utf-8")
        print(txt)
    else:
        print(__doc__)
