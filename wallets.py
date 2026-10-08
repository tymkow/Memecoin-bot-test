"""Własny silnik rankingu portfeli (smart money) + selektywna analiza źródła finansowania.

DANE: bez płatnego API. Każde ocenienie tokena zapisuje ostatnie ~300 transakcji jego puli (GeckoTerminal) do tabeli
wallet_trades. Z tego liczymy statystyki portfeli. To dane CZĘŚCIOWE (tylko tokeny, które oceniliśmy, i tylko ostatnie
transakcje puli), więc ranking jest tak dobry, jak pokrycie - dlatego śledzimy skromny zbiór (domyślnie do 100 portfeli).

ADAPTERY: WalletDataProvider to miejsce na GMGN/Birdeye/Helius. Silnik nie zależy od żadnego z nich.
  * NullProvider    - domyślny, brak zewnętrznych danych
  * HeliusProvider  - klucz w zmiennej środowiskowej HELIUS_API_KEY (darmowy plan: /transfers i /history;
                      /funded-by wymaga planu płatnego, więc przy 403 źródło finansowania wyliczamy z /transfers).
                      NIEZWERYFIKOWANY na żywo - brak klucza przy pisaniu; kształt odpowiedzi /transfers z dokumentacji.
  * GMGN/Birdeye   - szkielety (NotImplementedError) - do podpięcia, gdy będzie klucz.
"""
from __future__ import annotations

import os
import statistics
import time
from dataclasses import dataclass, field

import requests

import features as feat
from analysis import Finding

WSOL = "So11111111111111111111111111111111111111112"


# ============================================================ ADAPTERY DANYCH O PORTFELACH

class WalletDataProvider:
    name = "base"
    available = False

    def funder_of(self, wallet: str) -> tuple[str | None, str]:
        """(adres_fundatora | None, źródło). Fundator = nadawca pierwszego przelewu SOL do portfela."""
        raise NotImplementedError


class NullProvider(WalletDataProvider):
    name = "none"

    def funder_of(self, wallet):
        return None, "none"


class HeliusProvider(WalletDataProvider):
    name = "helius"
    BASE = "https://api.helius.xyz"

    def __init__(self, api_key: str, timeout: int = 15):
        self.key, self.timeout = api_key, timeout
        self.available = bool(api_key)
        self._funded_by_paid_only = False       # po pierwszym 403 nie odpytujemy już /funded-by
        self.s = requests.Session()

    def _get(self, path, params=None):
        r = self.s.get(f"{self.BASE}{path}", params=params, headers={"X-Api-Key": self.key}, timeout=self.timeout)
        return r.status_code, (r.json() if r.status_code == 200 else None)

    def funder_of(self, wallet):
        if not self.available:
            return None, "none"
        try:
            if not self._funded_by_paid_only:
                code, data = self._get(f"/v1/wallet/{wallet}/funded-by")
                if code == 200 and isinstance(data, dict) and data.get("funder"):
                    return data["funder"], "helius_funded_by"
                if code == 403:                      # darmowy plan
                    self._funded_by_paid_only = True
                elif code in (404,):
                    return None, "helius_funded_by"      # portfel bez przychodzących przelewów SOL
            code, data = self._get(f"/v1/wallet/{wallet}/transfers", {"limit": 100})
            if code == 200:
                return self.first_incoming_sol(data), "helius_transfers"
        except (requests.RequestException, ValueError):
            pass
        return None, "error"

    @staticmethod
    def first_incoming_sol(data) -> str | None:
        """Najstarszy przychodzący przelew SOL w odpowiedzi /transfers (pola dobierane defensywnie)."""
        items = data.get("data") if isinstance(data, dict) else data
        best = None
        for t in items or []:
            if not isinstance(t, dict):
                continue
            direction = str(t.get("direction", "")).lower()
            mint = t.get("mint") or t.get("token") or ""
            native = mint in ("", WSOL, "SOL") or str(t.get("symbol", "")).upper() == "SOL"
            sender = t.get("counterparty") or t.get("from") or t.get("sender")
            ts = t.get("timestamp") or t.get("blockTime") or 0
            if direction in ("in", "incoming", "receive", "received") and native and sender:
                if best is None or ts < best[0]:
                    best = (ts, sender)
        return best[1] if best else None


class BirdeyeProvider(WalletDataProvider):
    name = "birdeye"

    def funder_of(self, wallet):
        raise NotImplementedError("adapter Birdeye - do podpięcia po zdobyciu klucza")


class GmgnProvider(WalletDataProvider):
    name = "gmgn"

    def funder_of(self, wallet):
        raise NotImplementedError("adapter GMGN - do podpięcia po zdobyciu klucza")


def make_provider(cfg) -> WalletDataProvider:
    key = os.environ.get("HELIUS_API_KEY", "")
    if cfg.wallet_provider == "helius" and key:
        return HeliusProvider(key)
    return NullProvider()


# ============================================================ SELEKTYWNA ANALIZA WSPÓLNEGO FUNDATORA

def funding_check(cfg, provider: WalletDataProvider, store, coordinated_wallets: list[str],
                  same_block_share: float) -> tuple[list[Finding], dict]:
    """Drogie zapytania wykonujemy TYLKO dla podejrzanego klastra (>=3 portfele kupujące w jednym bloku i znaczny udział
    takich bloków w wolumenie). Zwraca (findings, info). Bez providera albo bez klastra: pusto."""
    if not (provider.available and len(coordinated_wallets) >= 3 and same_block_share >= cfg.funding_trigger_share):
        return [], {}
    funders: dict[str, list[str]] = {}
    lookups = 0
    for w in coordinated_wallets:
        cached = store.funding_get(w)
        if cached is None:
            if lookups >= cfg.funding_max_lookups:
                continue
            lookups += 1
            funder, src = provider.funder_of(w)
            if src != "error":
                store.funding_set(w, funder, src)
            cached = (funder, src)
        if cached[0]:
            funders.setdefault(cached[0], []).append(w)
    if not funders:
        return [], {"funding_lookups": lookups}
    funder, group = max(funders.items(), key=lambda kv: len(kv[1]))
    info = {"funding_lookups": lookups, "common_funder_wallets": len(group)}
    if len(group) >= 3:
        return [Finding("safety", "wspólny_fundator", points=-25,
                        detail=f"{len(group)} portfeli z podejrzanych bloków sfinansował ten sam adres {funder[:6]}...")], info
    return [], info


# ============================================================ SILNIK RANKINGU PORTFELI

@dataclass
class WalletStats:
    wallet: str
    tokens: int = 0
    closed: int = 0
    win_rate: float = 0.0
    mean_roi: float = 0.0
    copy_roi: float | None = None        # wynik "gdybyśmy kupili wallet_copy_latency_s po nim"
    total_pnl: float = 0.0
    median_hold_s: float = 0.0
    early_share: float = 0.0
    low_liq_share: float = 0.0
    is_bot: bool = False
    quality: float | None = None
    rois: list = field(default_factory=list)


class WalletEngine:
    def __init__(self, cfg, store):
        self.cfg, self.store = cfg, store
        self.stats: dict[str, WalletStats] = {}
        self.tracked: dict[str, float] = {}        # wallet -> quality (0-100)
        self._refreshed = 0.0

    # ---- zapis transakcji puli ----
    def ingest(self, mint: str, trades: list[dict]) -> int:
        rows = []
        for t in trades:
            ts, w, tx = feat._ts(t.get("block_timestamp")), t.get("tx_from_address"), t.get("tx_hash")
            if not (ts and w and tx):
                continue
            buy = t.get("kind") == "buy"
            amount = feat._f(t.get("to_token_amount" if buy else "from_token_amount"))
            price = feat._f(t.get("price_to_in_usd" if buy else "price_from_in_usd"))
            if amount > 0 and price > 0:
                rows.append((tx, w, mint, ts, "buy" if buy else "sell", feat._f(t.get("volume_in_usd")), amount, price))
        if rows:
            self.store.log_wallet_trades(rows)
        return len(rows)

    # ---- statystyki i jakość ----
    def refresh(self, force: bool = False):
        if not force and time.time() - self._refreshed < self.cfg.wallet_refresh_min * 60:
            return
        self._refreshed = time.time()
        since = time.time() - 14 * 86400
        db = self.store.db
        created = {}     # mint -> przybliżony czas utworzenia pary i płynność (z pierwszej decyzji)
        for r in db.execute("SELECT mint, MIN(ts) ts, age_min, liq FROM decisions WHERE age_min IS NOT NULL GROUP BY mint"):
            created[r["mint"]] = (r["ts"] - r["age_min"] * 60, r["liq"] or 0)
        price_series: dict[str, list] = {}
        legs: dict[tuple, dict] = {}
        for r in db.execute("SELECT wallet, mint, ts, side, usd, token_amount, price FROM wallet_trades "
                            "WHERE ts>? ORDER BY ts", (since,)):
            price_series.setdefault(r["mint"], []).append((r["ts"], r["price"]))
            leg = legs.setdefault((r["wallet"], r["mint"]), {"buys": [], "sells": []})
            leg["buys" if r["side"] == "buy" else "sells"].append((r["ts"], r["usd"], r["token_amount"], r["price"]))

        per_wallet: dict[str, list] = {}
        for (w, mint), leg in legs.items():
            per_wallet.setdefault(w, []).append((mint, leg))
        stats: dict[str, WalletStats] = {}
        for w, items in per_wallet.items():
            st = WalletStats(w, tokens=len(items))
            holds, early, lowliq, copies, pnl_total = [], 0, 0, [], 0.0
            for mint, leg in items:
                created_ts, liq = created.get(mint, (None, None))
                first_buy = min((b[0] for b in leg["buys"]), default=None)
                if created_ts and first_buy is not None and first_buy - created_ts <= 3600:
                    early += 1
                if liq and liq < 10_000:
                    lowliq += 1
                bought, sold = sum(b[2] for b in leg["buys"]), sum(s[2] for s in leg["sells"])
                spent, got = sum(b[1] for b in leg["buys"]), sum(s[1] for s in leg["sells"])
                if bought > 0 and sold >= 0.8 * bought and spent >= 5:    # pozycja domknięta w oknie
                    st.closed += 1
                    roi = got / spent - 1
                    st.rois.append(roi)
                    pnl_total += got - spent
                    holds.append(max(max(s[0] for s in leg["sells"]) - first_buy, 0))
                    # symulacja kopiowania z opóźnieniem: cena tokena po L s od zakupu portfela
                    sell_px = got / sold if sold else 0
                    later = [p for ts, p in price_series.get(mint, []) if ts >= first_buy + self.cfg.wallet_copy_latency_s]
                    if later and sell_px > 0:
                        copies.append(sell_px / later[0] - 1)
            n_trades = sum(len(l["buys"]) + len(l["sells"]) for _, l in items)
            st.median_hold_s = statistics.median(holds) if holds else 0.0
            st.early_share = early / st.tokens
            st.low_liq_share = lowliq / st.tokens
            st.total_pnl = pnl_total
            if st.closed:
                st.win_rate = sum(r > 0 for r in st.rois) / st.closed
                st.mean_roi = statistics.mean(st.rois)
            st.copy_roi = statistics.mean(copies) if copies else None
            # bot/market-maker: ultrakrótkie trzymanie albo ogromna liczba transakcji na jednym tokenie
            st.is_bot = (st.closed >= 5 and st.median_hold_s < 20) or (n_trades / max(st.tokens, 1) >= 40)
            st.quality = self._quality(st)
            stats[w] = st
        self.stats = stats
        ranked = sorted((s for s in stats.values() if s.quality is not None and not s.is_bot
                         and s.quality >= self.cfg.wallet_min_quality), key=lambda s: -s.quality)
        self.tracked = {s.wallet: s.quality for s in ranked[: self.cfg.wallet_track_max]}
        for w in self.cfg.smart_wallets:               # ręczne portfele zawsze śledzone
            self.tracked.setdefault(w, 70.0)

    def _quality(self, s: WalletStats) -> float | None:
        """Heurystyczna jakość 0-100. Brak oceny (None), gdy za mało domkniętych pozycji."""
        if s.closed < self.cfg.wallet_min_closed:
            return None
        score = 50.0
        score += max(-0.5, min(0.5, s.win_rate - 0.5)) * 60                 # skuteczność (+-30)
        edge = s.copy_roi if s.copy_roi is not None else s.mean_roi * 0.5     # wynik po opóźnieniu ważniejszy niż teoretyczny
        score += max(-25.0, min(25.0, edge * 50))                            # (+-25)
        score += s.early_share * 10 - s.low_liq_share * 10
        if s.is_bot:
            score -= 30
        return max(0.0, min(100.0, score))

    # ---- konwergencja: kilku niezależnych dobrych portfeli kupuje ten sam token ----
    def convergence(self, trades: list[dict]) -> dict:
        if not self.tracked:
            return {}
        stamped = [(feat._ts(t.get("block_timestamp")), t) for t in trades]
        stamped = [(ts, t) for ts, t in stamped if ts]
        if not stamped:
            return {}
        now = max(ts for ts, _ in stamped)              # okno liczone wstecz od ostatniej transakcji w próbce
        hit = {t.get("tx_from_address") for ts, t in stamped if t.get("kind") == "buy"
               and t.get("tx_from_address") in self.tracked and now - ts <= self.cfg.convergence_window_s}
        return {"smart_wallets_n": len(hit), "smart_quality_sum": round(sum(self.tracked[w] for w in hit) / 100, 3),
                "smart_wallets": sorted(hit)}
