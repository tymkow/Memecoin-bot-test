"""Wskaźniki analizy technicznej liczone z świec 1-minutowych (GeckoTerminal OHLCV) - WYŁĄCZNIE jako cechy do badań.

Zasada: każdy klasyczny wskaźnik trafia do dziennika cech, nawet gdy żadna strategia z niego nie korzysta. Dzięki temu po
zebraniu danych da się sprawdzić, czy np. "RSI 60-70 + przyspieszenie kupujących" daje coś ponad samo przyspieszenie
kupujących, zamiast wrzucać 15 wskaźników do jednego wzoru. Wskaźniki nie biorą udziału w punktacji Opportunity/Risk.

Świece: lista [ts, open, high, low, close, volume_usd] rosnąco po czasie (najnowsza ostatnia).
Okno to ~100 minut, więc "EMA50" to 50 minut, nie dni - dla memecoinów tak ma być, ale to nie jest klasyczny interwał.
"""
from __future__ import annotations

import math
import statistics
import time


def ema(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    k = 2 / (n + 1)
    e = sum(values[:n]) / n
    for v in values[n:]:
        e = v * k + e * (1 - k)
    return e


def ema_series(values: list[float], n: int) -> list[float]:
    if len(values) < n:
        return []
    k = 2 / (n + 1)
    e = sum(values[:n]) / n
    out = [e]
    for v in values[n:]:
        e = v * k + e * (1 - k)
        out.append(e)
    return out


def rsi(closes: list[float], n: int = 14) -> float | None:
    """RSI Wildera."""
    if len(closes) < n + 1:
        return None
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    ag, al = sum(gains[:n]) / n, sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):
        ag, al = (ag * (n - 1) + g) / n, (al * (n - 1) + l) / n
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return 100 - 100 / (1 + ag / al)


def true_ranges(c: list[list[float]]) -> list[float]:
    return [max(c[i][2] - c[i][3], abs(c[i][2] - c[i - 1][4]), abs(c[i][3] - c[i - 1][4])) for i in range(1, len(c))]


def atr_series(c: list[list[float]], n: int = 14) -> list[float]:
    tr = true_ranges(c)
    if len(tr) < n:
        return []
    a = sum(tr[:n]) / n
    out = [a]
    for t in tr[n:]:
        a = (a * (n - 1) + t) / n
        out.append(a)
    return out


def _percentile_rank(series: list[float], value: float) -> float:
    return sum(1 for x in series if x <= value) / len(series) if series else 0.5


def compute(candles: list[list[float]], now: float | None = None) -> dict:
    """Pełen zestaw cech technicznych. Brakujące wskaźniki (za mało świec) po prostu nie występują w wyniku.

    Bieżąca, jeszcze niezamknięta świeca jest pomijana (jej wolumen jest cząstkowy i fałszował z-score/ratio wolumenu)."""
    c = [x for x in candles if len(x) >= 6 and x[4] and x[4] > 0]
    c.sort(key=lambda x: x[0])
    if c and c[-1][0] + 60 > (time.time() if now is None else now):
        c = c[:-1]
    if len(c) < 15:
        return {}
    closes = [x[4] for x in c]
    vols = [x[5] for x in c]
    last = closes[-1]
    out: dict = {"ta_candles": len(c)}

    for n in (9, 21, 50):
        e = ema(closes, n)
        if e:
            out[f"ema{n}"] = e
            out[f"price_vs_ema{n}"] = (last - e) / e
    if all(k in out for k in ("ema9", "ema21", "ema50")):
        out["trend_bull"] = int(out["ema9"] > out["ema21"] > out["ema50"])
    r = rsi(closes, 14)
    if r is not None:
        out["rsi14"] = r
    atrs = atr_series(c, 14)
    if atrs:
        out["atr14"] = atrs[-1]
        out["atr_pct"] = atrs[-1] / last * 100
        out["atr_percentile"] = _percentile_rank(atrs, atrs[-1])        # reżim zmienności: 0 = spokojnie, 1 = najbardziej wzburzony

    # VWAP okna (cena typowa ważona wolumenem) i jego nachylenie (połowa okna vs druga połowa)
    typ = [(x[2] + x[3] + x[4]) / 3 for x in c]
    tv = sum(vols)
    if tv > 0:
        vwap = sum(t * v for t, v in zip(typ, vols)) / tv
        out["vwap"] = vwap
        out["price_vs_vwap"] = (last - vwap) / vwap
        h = len(c) // 2
        v1, v2 = sum(vols[:h]), sum(vols[h:])
        if v1 > 0 and v2 > 0:
            vw1 = sum(t * v for t, v in zip(typ[:h], vols[:h])) / v1
            vw2 = sum(t * v for t, v in zip(typ[h:], vols[h:])) / v2
            out["vwap_slope"] = (vw2 - vw1) / vw1

    # Bollinger (20, 2) i squeeze
    if len(closes) >= 20:
        def bands(i):
            w = closes[i - 20:i]
            m, s = statistics.mean(w), statistics.pstdev(w)
            return m + 2 * s, m - 2 * s, (4 * s / m if m else 0.0)
        up, lo, bw = bands(len(closes))
        out.update({"bb_upper": up, "bb_lower": lo, "bb_bandwidth": bw,
                    "bb_pos": (last - lo) / (up - lo) if up > lo else 0.5})
        bws = [bands(i)[2] for i in range(20, len(closes) + 1)]
        out["bb_bandwidth_percentile"] = _percentile_rank(bws, bw)
        recent_low_bw = min(bws[-10:]) if len(bws) >= 10 else bw
        out["bb_squeeze_break"] = int(last > up and _percentile_rank(bws, recent_low_bw) <= 0.25)

    # Donchian 20 i wybicie (porównujemy z 20 poprzednimi świecami, bez bieżącej)
    if len(c) >= 21:
        prev = c[-21:-1]
        dh, dl = max(x[2] for x in prev), min(x[3] for x in prev)
        out.update({"donchian_high_20": dh, "donchian_low_20": dl, "donchian_dist": (last - dh) / dh})
        out["donchian_break"] = int(last > dh)
        # wybicie w którejś z ostatnich 10 świec + retest: powrót do starego oporu bez zejścia pod niego
        for back in range(10, 0, -1):          # od najstarszej: PIERWSZE wybicie serii wyznacza opór, który retestujemy
            i = len(c) - 1 - back
            if i < 21:
                break
            old_high = max(x[2] for x in c[i - 20:i])
            if closes[i] > old_high:
                after = c[i + 1:]
                held = all(x[3] >= old_high * 0.97 for x in after)
                out["breakout_age"] = back
                out["retest_ok"] = int(held and last > old_high and any(x[3] <= old_high * 1.03 for x in after))
                vol_hot = max(vols[i:]) > 1.5 * statistics.mean(vols[max(0, i - 20):i] or [0])
                out["failed_breakout"] = int(last < old_high and vol_hot)
                break

    # wolumen: z-score ostatniej świecy względem 20 poprzednich, przyspieszenie i "efektywność" ceny
    if len(vols) >= 21:
        w = vols[-21:-1]
        m, s = statistics.mean(w), statistics.pstdev(w)
        out["volume_zscore"] = (vols[-1] - m) / s if s else 0.0
        out["volume_ratio_1m"] = vols[-1] / m if m else 0.0
        if len(vols) >= 10:
            v5, v5p = sum(vols[-5:]), sum(vols[-10:-5])
            out["volume_trend_5m"] = (v5 / v5p - 1) if v5p else 0.0
            ret5 = abs(closes[-1] / closes[-6] - 1)
            ratio = (v5 / (m * 5)) if m else 0.0
            out["vol_efficiency"] = ret5 / ratio if ratio else 0.0     # mały ruch ceny przy dużym wolumenie = niska efektywność
    if len(closes) >= 20:
        w = closes[-20:]
        s = statistics.pstdev(w)
        out["price_zscore"] = (last - statistics.mean(w)) / s if s else 0.0

    # MACD (12, 26, 9) - histogram jako cecha
    e12, e26 = ema_series(closes, 12), ema_series(closes, 26)
    if e26:
        macd = [a - b for a, b in zip(e12[-len(e26):], e26)]
        sig = ema_series(macd, 9)
        if sig:
            out["macd_hist"] = (macd[-1] - sig[-1]) / last
    # 6 cyfr znaczących (ceny memecoinów bywają rzędu 1e-6, więc zaokrąglenie do miejsc po przecinku by je wyzerowało)
    return {k: (float(f"{v:.6g}") if isinstance(v, float) else v) for k, v in out.items() if v is not None and not (
        isinstance(v, float) and (math.isnan(v) or math.isinf(v)))}
