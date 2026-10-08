"""Szybki stop z odczytu puli (portfel safety_fast, 7.10.2026) - OSOBNY wątek, niezależny od skanu nowych tokenów.

Co period sekund (domyślnie 2 s) jedno zapytanie getMultipleAccounts (commitment "processed", darmowy RPC Solany,
zapas: Helius) o salda skarbców pul PumpSwap otwartych pozycji portfeli z Config.fast_stop_portfolios. Wartość
sprzedaży całej reszty pozycji = stały iloczyn na (tokeny, SOL + V) z prowizją puli 0,3%, V = wirtualna rezerwa SOL
z konta puli (offset 245; analizy/crash_gap.py: bez niej wycena o 10-24% za niska), x SOL/USD (kwotowanie Jupitera
co 60 s) x 0,991 (kalibracja: kwotowanie Jupitera / wartość z puli w krachach). Gdy cena <= cena wejścia x (1 - SL):
sprzedaż przez zwykły paper.sell (fill = kwotowanie Jupitera z tej chwili, jak w każdym portfelu), powód "stop_fast".
Wątek robi TYLKO stop - TP, trailing, time stop i audyty zostają w głównej pętli (efekt = sam szybki stop).
Tokeny spoza PumpSwap (nie da się odczytać puli) - zwykły stop głównej pętli.
"""
from __future__ import annotations

import base64
import collections
import json
import statistics
import struct
import threading
import time
from pathlib import Path

import requests

PUMPSWAP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
POOL_FEE = 0.003
CALIB = 0.991
V_OFFSET = 245
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + out


def decode_pool(raw: bytes) -> dict | None:
    """Konto puli PumpSwap: mint bazowy, mint kwotowany, skarbce i wirtualna rezerwa SOL (lamporty -> SOL)."""
    if len(raw) < V_OFFSET + 8:
        return None
    k = [b58(raw[o:o + 32]) for o in (43, 75, 139, 171)]
    return {"base_mint": k[0], "quote_mint": k[1], "base_vault": k[2], "quote_vault": k[3],
            "v_sol": struct.unpack_from("<Q", raw, V_OFFSET)[0] / 1e9}


def sell_value_sol(tok: float, sol: float, v_sol: float, qty: float) -> float:
    q = qty * (1 - POOL_FEE)
    return (sol + v_sol) * q / (tok + q) if tok > 0 and q > 0 else 0.0


class FastMonitor(threading.Thread):
    def __init__(self, bot, names: tuple, period: float = 2.0, log=print):
        super().__init__(daemon=True, name="szybki-stop")
        self.bot, self.names, self.period, self.log = bot, names, period, log
        self.pfs = [bot.portfolios[n] for n in names if n in bot.portfolios]
        self.lock = bot.fast_lock
        self.s = requests.Session()
        self.pools: dict = {}                  # mint -> dane puli albo None (nie da się czytać szybko)
        self.sol_usd, self.sol_ts = None, 0.0
        self.owned: set = set()                # minty, którymi zarządza szybki stop
        self.stats = collections.deque(maxlen=900)   # (okres cyklu s, czas zapytania s, źródło)
        self.last_above: dict = {}             # (portfel, mint) -> ostatni odczyt NAD stopem
        self.fallbacks = 0
        self._stats_ts = time.time()
        key = None
        try:
            key = json.loads((Path(__file__).parent / "secrets.json").read_text(encoding="utf-8")).get("HELIUS_API_KEY")
        except (OSError, ValueError):
            pass
        self.helius = f"https://mainnet.helius-rpc.com/?api-key={key}" if key else None   # adres z kluczem nie trafia do logów

    # ------------------------------------------------------------ RPC
    def rpc(self, payload):
        for url in (PUBLIC_RPC, self.helius):
            if not url:
                continue
            try:
                r = self.s.post(url, json=payload, timeout=4)
                if r.status_code == 200:
                    if url != PUBLIC_RPC:
                        self.fallbacks += 1
                    return r.json(), ("public" if url == PUBLIC_RPC else "helius")
            except requests.RequestException:
                pass
        return None, None

    def resolve(self, mint: str):
        row = self.bot.store.db.execute("SELECT pair FROM decisions WHERE mint=? AND pair IS NOT NULL ORDER BY id DESC "
                                        "LIMIT 1", (mint,)).fetchone()
        if not row:
            return None
        j, _ = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo", "params": [row[0], {"encoding": "base64"}]})
        v = ((j or {}).get("result") or {}).get("value")
        if not v or v.get("owner") != PUMPSWAP:
            return None
        d = decode_pool(base64.b64decode(v["data"][0]))
        if not d or {d["base_mint"], d["quote_mint"]} != {mint, WSOL}:
            return None
        d["reversed"] = d["base_mint"] == WSOL
        d["pool"] = row[0]
        return d

    def refresh_sol(self):
        if time.time() - self.sol_ts < 60 and self.sol_usd:
            return
        try:
            r = self.s.get(self.bot.cfg.jupiter_url, params={"inputMint": WSOL, "outputMint": USDC, "amount": 10 ** 9,
                                                             "slippageBps": 50}, timeout=5).json()
            self.sol_usd, self.sol_ts = int(r["outAmount"]) / 1e6, time.time()
        except (requests.RequestException, ValueError, KeyError):
            pass

    # ------------------------------------------------------------ pętla
    def run(self):
        self.log(f"szybki stop: wątek startuje ({', '.join(self.names)}, co {self.period:.0f} s)")
        last = time.time()
        while True:
            t0 = time.time()
            try:
                src, dt = self.step()
                if src:
                    self.stats.append((t0 - last, dt, src))
                last = t0
                if time.time() - self._stats_ts > 600:
                    self._stats_ts = time.time()
                    self.log("szybki stop: " + self.summary())
            except Exception as e:                       # wątek nie może umrzeć po jednym złym odczycie
                self.log(f"szybki stop: BŁĄD {type(e).__name__}: {e}")
            time.sleep(max(0.0, self.period - (time.time() - t0)))

    def summary(self) -> str:
        st = list(self.stats)
        if not st:
            return f"brak pozycji do pilnowania (pul: {sum(1 for v in self.pools.values() if v)})"
        per = sorted(x[0] for x in st)
        lat = sorted(x[1] for x in st)
        return (f"{len(self.owned)} pozycji z odczytem puli; cykl mediana {statistics.median(per):.2f} s (p90 "
                f"{per[int(len(per) * .9)]:.2f}), zapytanie mediana {statistics.median(lat) * 1000:.0f} ms (p90 "
                f"{lat[int(len(lat) * .9)] * 1000:.0f} ms), zapas Helius {self.fallbacks}x")

    def step(self):
        held = [(pf, pos) for pf in self.pfs for pos in list(pf.positions.values())]
        for pf, pos in held:
            if pos.mint not in self.pools:
                self.pools[pos.mint] = self.resolve(pos.mint)
                d = self.pools[pos.mint]
                self.log(f"szybki stop: {pos.symbol} " + (f"pula PumpSwap, V={d['v_sol']:.2f} SOL" if d else
                                                         "pula nie-PumpSwap - zwykły stop głównej pętli"))
        live = [(pf, pos, self.pools[pos.mint]) for pf, pos in held if self.pools.get(pos.mint)]
        self.owned = {pos.mint for _, pos, _ in live}
        if not live:
            return None, 0.0
        self.refresh_sol()
        if not self.sol_usd:
            return None, 0.0
        accs = list(dict.fromkeys(a for _, _, d in live for a in (d["base_vault"], d["quote_vault"])))
        t = time.time()
        j, src = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
                           "params": [accs, {"encoding": "jsonParsed", "commitment": "processed"}]})
        dt = time.time() - t
        vals = ((j or {}).get("result") or {}).get("value")
        if not vals:
            return None, dt
        bal = {}
        for a, v in zip(accs, vals):
            try:
                bal[a] = float(v["data"]["parsed"]["info"]["tokenAmount"]["uiAmountString"])
            except (TypeError, KeyError, ValueError):
                pass
        now = time.time()
        for pf, pos, d in live:
            tok_v, sol_v = (d["quote_vault"], d["base_vault"]) if d["reversed"] else (d["base_vault"], d["quote_vault"])
            if tok_v not in bal or sol_v not in bal or pos.qty_left <= 0:
                continue
            price = sell_value_sol(bal[tok_v], bal[sol_v], d["v_sol"], pos.qty_left) * self.sol_usd * CALIB / pos.qty_left
            stop = pos.entry_price * (1 - pf.p("stop_loss_pct") / 100)
            key = (pf.name, pos.mint)
            if price > stop:
                self.last_above[key] = now
                continue
            with self.lock:
                if pos.mint not in pf.positions or pos.qty_left <= 0:
                    continue
                pf.sell(pos, pos.qty_left, price, 0.0, "stop_fast")
            prev = self.last_above.pop(key, None)
            ev = {"ts": now, "mint": pos.mint, "portfolio": pf.name, "price": price, "stop": stop,
                  "since_last_above_s": round(now - prev, 2) if prev else None, "rpc_s": round(dt, 3), "src": src}
            evs = self.bot.store.kv_get("fast_stop_events", [])
            self.bot.store.kv_set("fast_stop_events", (evs + [ev])[-500:])
            self.log(f"POZYCJA [{pf.name}] {pos.symbol}: stop_fast (cena puli {price / pos.entry_price - 1:+.1%} od wejścia, "
                     f"ostatni odczyt nad stopem {ev['since_last_above_s']} s wcześniej, zapytanie {dt * 1000:.0f} ms)")
        return src, dt
