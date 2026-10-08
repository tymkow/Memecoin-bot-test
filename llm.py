"""Strategia "Gemini" (tylko sygnały): model językowy ocenia token, który przeszedł twarde filtry bezpieczeństwa.

    python llm.py               # jedno zapytanie próbne (sprawdza klucz i format odpowiedzi)

Klucz: zmienna środowiskowa GEMINI_API_KEY albo plik secrets.json (poza gitem). Bez klucza strategia po prostu milczy.

Zasady (wnioski z przeglądu LLM_trader / LazyTrader / ai-trading-agent-gemini, 4.10.2026):
  * odpowiedź tylko jako JSON wg schematu (responseSchema), sprawdzany w kodzie - zły format = brak sygnału;
  * BUY musi mieć warunek unieważnienia ("co by pokazało, że się mylę"), inaczej odrzucamy;
  * ŻADNEGO zastępczego sygnału z reguł, gdy model nie odpowie (mieszałoby to wyniki AI i reguł);
  * każde zapytanie i odpowiedź trafia do tabeli llm_decisions (audyt, koszt, opóźnienie);
  * model niczego nie kupuje: sygnały gemini / gemini_hc oceniamy jak każdą strategię tylko-sygnałową
    (exits --signals, entries, calibrate) na tle grup kontrolnych. Prawdopodobieństwo (v2: p_better) z każdej oceny (także SKIP)
    zapisujemy jako cechę gemini_p, więc można sprawdzić, czy model w ogóle przewiduje cokolwiek lepiej niż przypadek.
"""
from __future__ import annotations

import bisect
import collections
import json
import os
import time
from pathlib import Path

import requests

BASE = Path(__file__).parent
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT_VERSION = "v2"   # v1 (4.10 do 15:40): stawki bazowe w prompcie -> model powtarzał p=18-22% przy KAŻDYM tokenie

SYSTEM = """You are a quantitative analyst RANKING Solana memecoins for a PAPER-TRADING research bot.
Every token you see already passed the same hard rug filters, and the bot's portfolios usually buy it anyway.
Your job is NOT to decide whether memecoins are good in general (most lose money) - it is to separate this token
from the OTHER clean tokens the bot sees. For each number you get its percentile among recent clean tokens
(p50 = typical, p90 = higher than 90% of them), so compare relative to them.
Setup: position $50, round-trip costs ~5.5%, exits: stop-loss -25%, take-profit +50%/+100%/+300% (1/3 each),
trailing stop 20% after the first TP, time stop 4 h.
What this bot's data showed so far (weak evidence, use as hints, not rules):
- very high activity (transactions, 1-min ATR >= 20%, +30% spikes in 5 min, buyer acceleration >= 3x) did worse;
- price above VWAP with calmer trading did better; many clones of the symbol did NOT do worse.
p_better = your probability (5-95) that this token's result after the bot's exits beats the MEDIAN clean token.
50 means "looks typical". Use the whole range - you are scored on how well p_better RANKS tokens, so giving
everything the same number is useless. BUY only if p_better >= 65 and name a concrete invalidation;
otherwise SKIP. Write "reasoning" in Polish, max 2 short sentences, citing the percentiles you relied on."""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "decision": {"type": "STRING", "enum": ["BUY", "SKIP"]},
        "confidence": {"type": "INTEGER"},
        "p_better": {"type": "INTEGER"},
        "reasoning": {"type": "STRING"},
        "invalidation": {"type": "STRING"},
        "risk_flags": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["decision", "confidence", "p_better", "reasoning", "invalidation"],
}

# cechy przekazywane modelowi (nazwa w features -> opis z jednostką); brakująca cecha = pomijamy
FEATURES = {
    "age_min": "pool age, minutes", "source": "how the bot found it (profile/boost/top_boost/graduation)",
    "liq": "liquidity USD", "mcap": "market cap USD", "ch_m5": "price change 5 min %", "ch_h1": "price change 1 h %",
    "ch_h6": "price change 6 h %", "ch_h24": "price change 24 h %", "txns_m5": "transactions 5 min",
    "txns_h1": "transactions 1 h", "vol_m5": "volume 5 min USD", "vol_h1": "volume 1 h USD",
    "buy_ratio_m5": "share of buys 5 min (count)", "buy_ratio_h1": "share of buys 1 h (count)",
    "holders_count": "holders", "top1": "largest holder % (ex-LP)", "top10": "top-10 holders %",
    "holder_gini": "holder Gini", "rugcheck_norm": "RugCheck risk score 0-100 (higher = riskier)",
    "creator_pct": "creator holds % of supply", "creator_launches_7d": "creator's other launches 7 d",
    "creator_graduated": "creator's launches that graduated", "ub_60s": "unique buyers last 60 s",
    "ub_300s": "unique buyers last 5 min", "buyer_accel": "buyer acceleration (last 60 s vs previous 2 min)",
    "seller_accel": "seller acceleration", "bsi": "buy share of volume (0.5 = balanced)",
    "flow_divergence": "buy-count share minus buy-volume share (>0 = small buys vs big sells)",
    "new_buyer_ratio": "share of new buyers", "same_block_buy_share": "share of buy volume in multi-wallet blocks (bundles)",
    "top3_wallet_share": "top-3 wallets share of volume", "early_buyers_sold_share": "early buyers who already sold",
    "smart_wallets_n": "tracked profitable wallets buying", "atr_pct": "1-min ATR % of price",
    "price_vs_vwap": "price vs ~100-min VWAP (fraction)", "rsi14": "RSI(14) on 1-min candles",
    "trend_bull": "EMA9>EMA21>EMA50 on 1-min (1 = yes)", "volume_ratio_1m": "last 1-min volume / 20-min average",
    "roundtrip_loss_pct": "buy+sell immediately loss %", "mkt_breadth_h1": "share of other new tokens up in 1 h",
    "mkt_median_h1": "median 1-h change of other new tokens %", "sol_ch_h1": "SOL price change 1 h %",
    "sol_ch_h24": "SOL price change 24 h %",
}


def api_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY")
    if not key and (BASE / "secrets.json").exists():
        key = json.loads((BASE / "secrets.json").read_text(encoding="utf-8")).get("GEMINI_API_KEY")
    return key or None


def reference(rows) -> dict:
    """Próbka odniesienia: cecha -> posortowane wartości z ostatnich czystych tokenów (json features z decisions)."""
    ref: dict = {}
    for (raw,) in rows:
        f = json.loads(raw or "{}")
        for k in FEATURES:
            v = f.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                ref.setdefault(k, []).append(float(v))
    return {k: sorted(v) for k, v in ref.items() if len(v) >= 20}


def build_prompt(symbol: str, features: dict, notes: list[str], ref: dict | None = None) -> str:
    """Wartości cech z percentylem wśród ostatnich czystych tokenów - model porównuje token z innymi, a nie
    ze średnią stratą rynku (v1 kotwiczył się na stawkach bazowych i dawał każdemu to samo)."""
    rows = {}
    for k, desc in FEATURES.items():
        v = features.get(k)
        if v is None:
            continue
        r = (ref or {}).get(k)
        if r and isinstance(v, (int, float)) and not isinstance(v, bool):
            rows[desc] = f"{v:.4g} (p{round(100 * bisect.bisect_left(r, float(v)) / len(r))})"
        else:
            rows[desc] = v
    n = max((len(r) for r in (ref or {}).values()), default=0)
    return (f"Token {symbol}. Snapshot at decision time (percentile among {n} recent clean tokens in brackets):\n"
            f"{json.dumps(rows, ensure_ascii=False, indent=0)}\n"
            f"Bot's rule-based notes (positive and negative findings):\n- " + "\n- ".join(notes or ["(none)"]))


def parse(text: str) -> dict:
    """Odpowiedź modelu -> słownik po walidacji (ValueError = odrzucamy, bez sygnału).
    Liczba p_better (v2) trafia do pola p_tp - ta sama kolumna w llm_decisions; wersję promptu niesie kolumna model."""
    d = json.loads(text)
    if d.get("decision") not in ("BUY", "SKIP"):
        raise ValueError(f"zła decyzja: {d.get('decision')!r}")
    if "p_better" in d:
        d["p_tp"] = d.pop("p_better")
    for k in ("confidence", "p_tp"):
        v = d.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= 100:
            raise ValueError(f"{k} poza 0-100: {v!r}")
        d[k] = int(round(v))
    d["reasoning"] = str(d.get("reasoning") or "")[:400]
    d["invalidation"] = str(d.get("invalidation") or "").strip()[:300]
    if d["decision"] == "BUY" and len(d["invalidation"]) < 5:
        raise ValueError("BUY bez warunku unieważnienia")
    d["risk_flags"] = [str(x)[:80] for x in (d.get("risk_flags") or [])][:5]
    return d


class GeminiAdvisor:
    def __init__(self, cfg, store, key: str | None = None):
        self.cfg, self.store = cfg, store
        self.key = key if key is not None else api_key()
        self.enabled = bool(cfg.gemini_enabled and self.key)
        self.calls: collections.deque = collections.deque()
        self.s = requests.Session()

    def _budget_ok(self) -> tuple[bool, str]:
        now = time.time()
        while self.calls and now - self.calls[0] > 60:
            self.calls.popleft()
        if len(self.calls) >= self.cfg.gemini_rpm:
            return False, "limit na minutę"
        day = time.strftime("%Y-%m-%d")
        if self.store.kv_get(f"gemini_calls:{day}", 0) >= self.cfg.gemini_max_per_day:
            return False, "limit dzienny"
        return True, ""

    def ask(self, prompt: str) -> tuple[dict | None, dict]:
        """Jedno zapytanie. Zwraca (odpowiedź po walidacji albo None, meta: latency, tokeny, błąd, surowy tekst)."""
        meta: dict = {"model": f"{self.cfg.gemini_model}/{PROMPT_VERSION}", "error": None, "raw": None, "latency": None,
                      "tokens_in": None, "tokens_out": None}
        ok, why = self._budget_ok()
        if not ok:
            meta["error"] = why
            return None, meta
        self.calls.append(time.time())
        day = time.strftime("%Y-%m-%d")
        self.store.kv_set(f"gemini_calls:{day}", self.store.kv_get(f"gemini_calls:{day}", 0) + 1)
        body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 500, "responseMimeType": "application/json",
                                     "responseSchema": SCHEMA}}
        t0 = time.time()
        try:
            # klucz w nagłówku, nie w adresie - adresy trafiają do logów i komunikatów błędów
            r = self.s.post(URL.format(model=self.cfg.gemini_model), json=body, timeout=self.cfg.gemini_timeout_s,
                            headers={"x-goog-api-key": self.key, "Content-Type": "application/json"})
        except requests.RequestException as e:
            meta.update(error=f"sieć: {type(e).__name__}", latency=time.time() - t0)
            return None, meta
        meta["latency"] = round(time.time() - t0, 2)
        if r.status_code != 200:
            meta["error"] = f"HTTP {r.status_code}: {r.text[:200]}"
            return None, meta
        j = r.json()
        usage = j.get("usageMetadata") or {}
        # tokeny "myślenia" są płatne i liczą się do limitu odpowiedzi jak zwykłe - doliczamy je do tokens_out
        meta.update(tokens_in=usage.get("promptTokenCount"),
                    tokens_out=(usage.get("candidatesTokenCount") or 0) + (usage.get("thoughtsTokenCount") or 0))
        try:
            cand = j["candidates"][0]
            text = cand["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            meta["error"] = f"pusta odpowiedź: {json.dumps(j)[:200]}"
            return None, meta
        if cand.get("finishReason") == "MAX_TOKENS":
            meta.update(error="ucięta odpowiedź (MAX_TOKENS) - model myślący? zmień gemini_model", raw=text[:2000])
            return None, meta
        meta["raw"] = text[:2000]
        try:
            return parse(text), meta
        except (ValueError, json.JSONDecodeError) as e:
            meta["error"] = f"odrzucona: {e}"
            return None, meta


def _test():
    from config import Config
    from storage import Storage
    import tempfile
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    adv = GeminiAdvisor(cfg, st)
    if not adv.key:
        print("Brak klucza: ustaw GEMINI_API_KEY albo dopisz go do secrets.json")
        return
    feats = {"age_min": 95, "source": "profile", "liq": 42000, "mcap": 310000, "ch_m5": 4.2, "ch_h1": 18,
             "txns_m5": 60, "buy_ratio_m5": 0.58, "atr_pct": 9.5, "price_vs_vwap": 0.04, "rsi14": 61, "top10": 22}
    res, meta = adv.ask(build_prompt("TEST", feats, ["social: strona + X", "lp_locked: LP spalone w 100%"]))
    print("odpowiedź:", json.dumps(res, ensure_ascii=False))
    print("meta:", {k: v for k, v in meta.items() if k != "raw"})


if __name__ == "__main__":
    _test()
