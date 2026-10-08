"""Klienci darmowych API: DexScreener (rynek), RugCheck (audyt tokena), publiczny RPC Solany.

Żadne z nich nie wymaga klucza. Każdy klient ma własny limiter i cache,
a błędy sieciowe zwracają None zamiast wywalać cały obieg.
"""
from __future__ import annotations

import threading
import time

import requests

DEX = "https://api.dexscreener.com"
RUGCHECK = "https://api.rugcheck.xyz/v1"


class RateLimiter:
    def __init__(self, rpm: int):
        self.interval = 60.0 / max(rpm, 1)
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self.interval


class Http:
    def __init__(self, rpm: int, user_agent: str):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = user_agent
        self.limiter = RateLimiter(rpm)

    def get(self, url, params=None, retries=2, timeout=15):
        for attempt in range(retries + 1):
            self.limiter.wait()
            try:
                r = self.s.get(url, params=params, timeout=timeout)
            except requests.RequestException:
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code != 200:
                return None
            try:
                return r.json()
            except ValueError:
                return None
        return None

    def get_status(self, url, params=None, headers=None, retries=2, timeout=15):
        """Jak get(), ale zwraca (kod_http, json|None); kod 0 = błąd sieci. Rozróżnia 'brak trasy' od awarii."""
        status = 0
        for attempt in range(retries + 1):
            self.limiter.wait()
            try:
                r = self.s.get(url, params=params, headers=headers, timeout=timeout)
            except requests.RequestException:
                status = 0
                time.sleep(1.5 * (attempt + 1))
                continue
            status = r.status_code
            if status == 429:
                time.sleep(6 * (attempt + 1))
                continue
            try:
                return status, r.json()
            except ValueError:
                return status, None
        return status, None

    def post(self, url, json_body, retries=1, timeout=15):
        for attempt in range(retries + 1):
            self.limiter.wait()
            try:
                r = self.s.post(url, json=json_body, timeout=timeout)
            except requests.RequestException:
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code != 200:
                return None
            try:
                return r.json()
            except ValueError:
                return None
        return None


class DexScreener:
    def __init__(self, cfg):
        self.cfg = cfg
        self.pairs_http = Http(cfg.dexscreener_rpm, cfg.user_agent)
        self.profiles_http = Http(cfg.dexscreener_profiles_rpm, cfg.user_agent)

    # --- odkrywanie tokenów ---
    def _profile_list(self, path) -> list[str]:
        data = self.profiles_http.get(f"{DEX}{path}")
        if not isinstance(data, list):
            return []
        return [d["tokenAddress"] for d in data
                if d.get("chainId") == self.cfg.chain and d.get("tokenAddress")]

    def latest_profiles(self) -> list[str]:
        """Świeżo założone profile tokenów (ktoś zapłacił za profil/zaktualizował info)."""
        return self._profile_list("/token-profiles/latest/v1")

    def latest_boosts(self) -> list[str]:
        return self._profile_list("/token-boosts/latest/v1")

    def top_boosts(self) -> list[str]:
        return self._profile_list("/token-boosts/top/v1")

    def search(self, query: str) -> list[dict]:
        data = self.pairs_http.get(f"{DEX}/latest/dex/search", params={"q": query})
        pairs = (data or {}).get("pairs") or []
        return [p for p in pairs if p.get("chainId") == self.cfg.chain]

    # --- dane rynkowe ---
    def pairs_for_tokens(self, mints: list[str]) -> dict[str, list[dict]]:
        """Do 30 adresów na zapytanie. Zwraca {mint: [pary...]} (tylko baseToken == mint)."""
        out: dict[str, list[dict]] = {}
        for i in range(0, len(mints), 30):
            chunk = mints[i:i + 30]
            data = self.pairs_http.get(f"{DEX}/tokens/v1/{self.cfg.chain}/{','.join(chunk)}")
            if data is None:  # starszy endpoint jako zapas
                data = (self.pairs_http.get(f"{DEX}/latest/dex/tokens/{','.join(chunk)}") or {}).get("pairs")
            for p in data or []:
                if p.get("chainId") != self.cfg.chain:
                    continue
                addr = (p.get("baseToken") or {}).get("address")
                if addr:
                    out.setdefault(addr, []).append(p)
        return out

    @staticmethod
    def best_pair(pairs: list[dict]) -> dict | None:
        """Najpłynniejsza para = 'prawdziwa' cena tokena."""
        if not pairs:
            return None
        return max(pairs, key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0))


class RugCheck:
    def __init__(self, cfg):
        self.http = Http(cfg.rugcheck_rpm, cfg.user_agent)

    def report(self, mint: str) -> dict | None:
        """Pełny raport (holderzy, markety, LP, ryzyka). None = brak danych."""
        data = self.http.get(f"{RUGCHECK}/tokens/{mint}/report")
        return data if isinstance(data, dict) else None


USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
GECKO = "https://api.geckoterminal.com/api/v2/networks/solana"
GECKO_HEADERS = {"Accept": "application/json;version=20230302"}


class Jupiter:
    """Darmowe kwotowania Jupitera (bez klucza). Służą do: testu honeypota, realnych fillów, kontroli wyjścia."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.http = Http(cfg.jupiter_rpm, cfg.user_agent)

    def quote(self, in_mint: str, out_mint: str, amount_raw: int):
        """Zwraca (stan, dane): 'ok' | 'noroute' | 'error'."""
        status, data = self.http.get_status(self.cfg.jupiter_url, params={
            "inputMint": in_mint, "outputMint": out_mint, "amount": str(int(amount_raw)),
            "slippageBps": self.cfg.jupiter_slippage_bps})
        if status == 200 and isinstance(data, dict) and data.get("outAmount"):
            return "ok", data
        if status in (400, 404):  # np. COULD_NOT_FIND_ANY_ROUTE / TOKEN_NOT_TRADABLE
            return "noroute", data
        return "error", None

    def buy_usdc(self, mint: str, usd: float):
        return self.quote(USDC, mint, int(usd * 1e6))

    def sell_usdc(self, mint: str, qty_raw: int):
        return self.quote(mint, USDC, qty_raw)


class GeckoTerminal:
    """Darmowe API GeckoTerminala (~30 zapytań/min): holderzy, gt_score, trendy, transakcje puli."""

    def __init__(self, cfg):
        self.http = Http(cfg.gecko_rpm, cfg.user_agent)

    def _get(self, path):
        status, data = self.http.get_status(f"{GECKO}{path}", headers=GECKO_HEADERS)
        return data if status == 200 and isinstance(data, dict) else None

    def token_info(self, mint: str) -> dict | None:
        d = self._get(f"/tokens/{mint}/info")
        return ((d or {}).get("data") or {}).get("attributes")

    def pool_trades(self, pool: str) -> list[dict]:
        d = self._get(f"/pools/{pool}/trades")
        return [x["attributes"] for x in (d or {}).get("data", []) if "attributes" in x]

    def ohlcv(self, pool: str, limit: int = 100, aggregate: int = 1, before: int | None = None) -> list[list[float]] | None:
        """Świece minutowe puli: [ts, open, high, low, close, volume_usd], rosnąco po czasie (do 1000 świec).
        before = znacznik czasu (s) - świece sprzed tej chwili (archiwum). None = błąd zapytania, [] = brak świec."""
        q = f"/pools/{pool}/ohlcv/minute?aggregate={aggregate}&limit={limit}&currency=usd"
        if before:
            q += f"&before_timestamp={int(before)}"
        d = self._get(q)
        if d is None:
            return None
        rows = (((d or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
        return sorted((r for r in rows if isinstance(r, list) and len(r) >= 6), key=lambda r: r[0])

    def trending(self, duration="1h") -> list[str]:
        """Adresy tokenów z listy 'trending' (kolejność = ranking)."""
        d = self._get(f"/trending_pools?duration={duration}")
        out = []
        for p in (d or {}).get("data", []):
            tid = (((p.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id", "")
            if tid.startswith("solana_"):
                out.append(tid[len("solana_"):])
        return out


class SolanaRPC:
    """Zapas dla RugCheck: autorytety mintu i koncentracja holderów prosto z łańcucha."""

    def __init__(self, cfg):
        self.url = cfg.rpc_url
        self.http = Http(cfg.rpc_rpm, cfg.user_agent)

    def _call(self, method, params):
        data = self.http.post(self.url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        return (data or {}).get("result")

    def mint_info(self, mint: str) -> dict | None:
        res = self._call("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        try:
            return res["value"]["data"]["parsed"]["info"]
        except (TypeError, KeyError):
            return None

    def largest_holders(self, mint: str) -> list[dict] | None:
        res = self._call("getTokenLargestAccounts", [mint])
        return (res or {}).get("value")

    def supply(self, mint: str) -> float | None:
        res = self._call("getTokenSupply", [mint])
        try:
            return float(res["value"]["uiAmount"])
        except (TypeError, KeyError):
            return None
