"""Moduły strategii wejścia. Strategia = funkcja (verdict, cfg, ctx) -> bool: "czy ten token kupić".

Wszystkie strategie dostają TEN SAM strumień tokenów i te same twarde filtry bezpieczeństwa (veto blokuje każdą), ale
każda ma własny wirtualny portfel (paper.Portfolio) oraz własne sygnały w tabeli signals. Dzięki temu hipotezy
porównujemy na jednym rynku w jednym czasie:

  hybrid            pełny system: Opportunity >= próg ORAZ Risk <= próg ORAZ brak veto (strategia "produkcyjna")
  momentum_only     tylko kategoria momentum >= próg
  buyer_accel_only  tylko przyspieszenie unikalnych kupujących (z transakcji puli)
  smart_money_only  tylko konwergencja >= N śledzonych portfeli (silnik rankingu portfeli, wallets.py)
  safety_only       GRUPA KONTROLNA 1: kupuje wszystko, co przejdzie twarde filtry
  random_eligible   GRUPA KONTROLNA 2: losowa ~1/4 tokenów, które przeszły twarde filtry (determinizm: hash mintu)
  flow_only, score_no_gates   dodatkowe warianty (domyślnie wyłączone)

  v0.7 - eksperyment 2x2 (wejście x wyjście), parametry wyjścia w Config.strategy_exits:
                      stop -25%        stop -40%       stop -60% (awaryjny)
    wszystkie czyste  safety_only      safety_wide
    ATR 1-min < 20%   lowvol           lowvol_wide     lowvol_catastrophic
  safety_only vs lowvol = efekt filtra; safety_only vs safety_wide = efekt stopa; lowvol_wide = oba naraz.

  v0.8 - reguły wykluczenia (z analizy 50 wejść, progi zamrożone 2.10.2026):
    strict            portfel: ATR < 20%, cena nad VWAP, < 20% zakupów w skoordynowanych blokach, bez skoku 5 min >= 30%
    skip_*            tylko-sygnałowe: safety_only minus JEDEN typ tokenów - pokazują, która reguła naprawdę coś daje

Dodanie strategii: napisz funkcję, dopisz do REGISTRY i do Config.strategies. Nie trzeba ruszać odkrywania, wykonania,
portfela ani bazy.
"""
from __future__ import annotations

import zlib
from typing import Callable


def _clean(v) -> bool:
    """Przeszedł wszystkie etapy bez veto (wyniki kategorii są pełne)."""
    return not v.vetoes and bool(v.category_scores)


def _feat(ctx) -> dict:
    return (ctx or {}).get("features") or {}


def hybrid(v, cfg, ctx=None) -> bool:
    return v.decision == "BUY"


def momentum_only(v, cfg, ctx=None) -> bool:
    return _clean(v) and v.category_scores.get("momentum", 0) >= cfg.strategy_thresholds.get("momentum_only", 70)


def flow_only(v, cfg, ctx=None) -> bool:
    return _clean(v) and v.category_scores.get("flow", 0) >= cfg.strategy_thresholds.get("flow_only", 80)


def buyer_accel_only(v, cfg, ctx=None) -> bool:
    f = _feat(ctx)
    return (_clean(v) and f.get("ub_60s", 0) >= cfg.strategy_thresholds.get("buyer_accel_min_buyers", 8)
            and f.get("buyer_accel", 0) >= cfg.strategy_thresholds.get("buyer_accel_min_ratio", 1.5))


def smart_money_only(v, cfg, ctx=None) -> bool:
    return _clean(v) and _feat(ctx).get("smart_wallets_n", 0) >= cfg.smart_min_wallets


def safety_only(v, cfg, ctx=None) -> bool:
    return _clean(v)


def safety_bundle30(v, cfg, ctx=None) -> bool:
    """7.10: safety_only tylko przy bundlu startu >= 30% podaży (analizy część 8; brak danych o starcie -> nie kupuje)."""
    b = ((ctx or {}).get("launch") or {}).get("bundle")
    return _clean(v) and b is not None and b["bundle_start_pct"] >= cfg.strategy_thresholds.get("bundle_min_pct", 30.0)


def safety_nocopy(v, cfg, ctx=None) -> bool:
    """7.10: safety_only bez kopii AKTYWNEGO tokena i bez skopiowanej grafiki (analizy część 9; brak danych -> kupuje)."""
    c = ((ctx or {}).get("launch") or {}).get("copy")
    return _clean(v) and not (c and (c["copy_cat"].startswith("a") or c["img_copy"] or c["img_ref"]))


def random_eligible(v, cfg, ctx=None) -> bool:
    mint = (ctx or {}).get("mint", "")
    return _clean(v) and (zlib.crc32(mint.encode()) % 100) < cfg.random_eligible_pct


def score_no_gates(v, cfg, ctx=None) -> bool:
    return _clean(v) and v.score >= cfg.buy_threshold


# ---- hipotezy z analizy technicznej (świece 1 min z GeckoTerminal); wszystkie za tymi samymi twardymi filtrami ----
# Brak cechy (za mało świec) = brak sygnału. To są HIPOTEZY - dopiero `bot.py calibrate` pokaże, czy cokolwiek wnoszą.

def _th(cfg, key, default):
    return cfg.strategy_thresholds.get(key, default)


def breakout_volume(v, cfg, ctx=None) -> bool:
    """Wybicie 20-świecowego maksimum + wolumen > 2x średniej + cena nad VWAP + trend EMA9>21>50."""
    f = _feat(ctx)
    return (_clean(v) and f.get("donchian_break") == 1 and f.get("volume_ratio_1m", 0) >= _th(cfg, "breakout_volume_ratio", 2.0)
            and f.get("price_vs_vwap", -1) > 0 and f.get("trend_bull") == 1)


def breakout_retest(v, cfg, ctx=None) -> bool:
    """Wybicie, cofnięcie do starego oporu i utrzymanie nad nim (nie gonimy pierwszej świecy)."""
    f = _feat(ctx)
    return _clean(v) and f.get("retest_ok") == 1 and f.get("trend_bull") == 1 and f.get("failed_breakout", 0) == 0


def vwap_momentum(v, cfg, ctx=None) -> bool:
    f = _feat(ctx)
    return (_clean(v) and f.get("price_vs_vwap", -1) > 0 and f.get("vwap_slope", -1) > 0
            and f.get("volume_trend_5m", -1) > 0)


def ema_trend_rsi(v, cfg, ctx=None) -> bool:
    """Trend (EMA9>21>50) + RSI w strefie momentum (nie 'wyprzedane' i nie ekstremum) + rosnący wolumen."""
    f = _feat(ctx)
    return (_clean(v) and f.get("trend_bull") == 1
            and _th(cfg, "rsi_momentum_lo", 50) <= f.get("rsi14", -1) <= _th(cfg, "rsi_momentum_hi", 70)
            and f.get("volume_ratio_1m", 0) >= _th(cfg, "ema_trend_volume_ratio", 1.2))


def bollinger_breakout(v, cfg, ctx=None) -> bool:
    """Ekspansja zmienności po ścieśnieniu pasm: wybicie górnej wstęgi + skok wolumenu."""
    f = _feat(ctx)
    return _clean(v) and f.get("bb_squeeze_break") == 1 and f.get("volume_zscore", 0) >= _th(cfg, "bb_volume_z", 1.5)


def vwap_reversion(v, cfg, ctx=None) -> bool:
    """Powrót do średniej: cena wyraźnie pod VWAP, ale kupujący wracają (presja kupna 5 min > 1 h)."""
    f = _feat(ctx)
    return (_clean(v) and f.get("price_vs_vwap", 0) <= _th(cfg, "vwap_reversion_dist", -0.05)
            and f.get("buy_ratio_m5", 0) >= _th(cfg, "vwap_reversion_buy_ratio", 0.55)
            and f.get("buy_ratio_m5", 0) > f.get("buy_ratio_h1", 1))


# ---- v0.7: filtr zmienności (eksperyment 2x2 z szerokością stopa) i hipoteza "dojrzały, spokojny" ----

def lowvol(v, cfg, ctx=None) -> bool:
    """Jak safety_only (wszystko, co przeszło twarde filtry), ale tylko gdy ATR 1-min < lowvol_max_atr_pct.
    Brak ATR (brak świec) = brak sygnału - filtr ma działać na tej samej liczbie, którą widzi badanie."""
    atr = _feat(ctx).get("atr_pct")
    return _clean(v) and atr is not None and atr < cfg.lowvol_max_atr_pct


def mature_calm(v, cfg, ctx=None) -> bool:
    f = _feat(ctx)
    return (_clean(v) and f.get("age_min", 0) >= _th(cfg, "mature_min_age", 60)
            and f.get("txns_m5", 1e9) < _th(cfg, "mature_max_txns_m5", 80))


# ---- v0.8: reguły wykluczenia z analizy 50 wejść (2.10.2026), progi ZAMROŻONE ----
# Każda reguła osobno jako strategia tylko-sygnałowa (= safety_only bez jednego typu tokenów), plus portfel `strict`
# łączący najmocniejsze. Brak cechy = brak sygnału (reguła ma działać tylko tam, gdzie da się ją sprawdzić).

def _has(f: dict, *keys) -> bool:
    return all(isinstance(f.get(k), (int, float)) for k in keys)


def skip_below_vwap(v, cfg, ctx=None) -> bool:
    """Bez wejść, gdy cena jest pod VWAP z ostatnich ~100 min (ktoś już rozprowadza token)."""
    f = _feat(ctx)
    return _clean(v) and _has(f, "price_vs_vwap") and f["price_vs_vwap"] >= 0


def skip_block_buys(v, cfg, ctx=None) -> bool:
    """Bez wejść, gdy >= 20% wolumenu kupna to bloki z >= 3 portfelami naraz (bundle / boty)."""
    f = _feat(ctx)
    return _clean(v) and _has(f, "same_block_buy_share") and f["same_block_buy_share"] < _th(cfg, "max_block_share", 0.2)


def skip_spike_5m(v, cfg, ctx=None) -> bool:
    """Bez wejść po pionowym skoku ceny w 5 min (>= +30%)."""
    f = _feat(ctx)
    return _clean(v) and _has(f, "ch_m5") and f["ch_m5"] < _th(cfg, "max_spike_5m", 30)


def skip_accel_3x(v, cfg, ctx=None) -> bool:
    """Bez wejść przy skrajnym przyspieszeniu nowych kupujących (>= 3x) - 7 z 8 takich wejść było rugami."""
    f = _feat(ctx)
    return _clean(v) and _has(f, "buyer_accel") and f["buyer_accel"] < _th(cfg, "max_buyer_accel", 3)


def skip_young_60m(v, cfg, ctx=None) -> bool:
    """Bez tokenów młodszych niż 60 min (obecne twarde minimum to 15 min)."""
    f = _feat(ctx)
    return _clean(v) and _has(f, "age_min") and f["age_min"] >= _th(cfg, "min_age_strict", 60)


def strict(v, cfg, ctx=None) -> bool:
    """Portfel: ATR < 20% ORAZ cena nad VWAP ORAZ mniej niż 20% zakupów w skoordynowanych blokach ORAZ bez skoku 5 min."""
    return (lowvol(v, cfg, ctx) and skip_below_vwap(v, cfg, ctx) and skip_block_buys(v, cfg, ctx)
            and skip_spike_5m(v, cfg, ctx))


REGISTRY: dict[str, Callable] = {
    "strict": strict,
    "skip_below_vwap": skip_below_vwap,
    "skip_block_buys": skip_block_buys,
    "skip_spike_5m": skip_spike_5m,
    "skip_accel_3x": skip_accel_3x,
    "skip_young_60m": skip_young_60m,
    # te same wejścia co safety_only / lowvol, inne wyjście (Config.strategy_exits) - porównanie czystego efektu stopa
    "safety_wide": safety_only,
    "lowvol": lowvol,
    "lowvol_wide": lowvol,
    "lowvol_catastrophic": lowvol,
    "safety_ts5": safety_only,           # 4.10: te same wejścia, szybki time stop (Config.strategy_exits)
    "lowvol_ts10": lowvol,
    "safety_s6": safety_only,            # 6.10: te same wejścia, wyjście S6 (1/3 @+20% + stop na wejściu)
    "mature_calm": mature_calm,
    "breakout_volume": breakout_volume,
    "breakout_retest": breakout_retest,
    "vwap_momentum": vwap_momentum,
    "ema_trend_rsi": ema_trend_rsi,
    "bollinger_breakout": bollinger_breakout,
    "vwap_reversion": vwap_reversion,
    "hybrid": hybrid,
    "momentum_only": momentum_only,
    "flow_only": flow_only,
    "buyer_accel_only": buyer_accel_only,
    "smart_money_only": smart_money_only,
    "safety_only": safety_only,
    "random_eligible": random_eligible,
    "safety_fast": safety_only,
    "random_fast_s6": random_eligible,
    "safety_bundle30": safety_bundle30,
    "safety_nocopy": safety_nocopy,
    "score_no_gates": score_no_gates,
}


def wants(name: str, verdict, cfg, ctx=None) -> bool:
    fn = REGISTRY.get(name)
    return bool(fn and fn(verdict, cfg, ctx))
