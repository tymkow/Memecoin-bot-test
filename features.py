"""Cechy liczbowe tokena (do dziennika, analizy i porównywania strategii). Same funkcje czyste - łatwe do testowania.

Cechy trafiają do decisions.features jako JSON dla KAŻDEGO ocenionego tokena, także odrzuconego, żeby były
negatywne przykłady do badań. Brakująca cecha = brak klucza (nie zero), bo zero bywa prawdziwą wartością.
"""
from __future__ import annotations

import calendar
import time


def _f(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _ts(s: str | None) -> float | None:
    try:
        return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


LIQ_BUCKETS = [(5_000, "<5k"), (10_000, "5-10k"), (25_000, "10-25k"), (50_000, "25-50k"), (100_000, "50-100k")]


def liq_bucket(liq_usd: float) -> str:
    """Kubełek płynności do osobnych testów (nie ma jednego 'magicznego' progu)."""
    for edge, label in LIQ_BUCKETS:
        if liq_usd < edge:
            return label
    return "100k+"


# ------------------------------------------------------------------ transakcje puli (GeckoTerminal)

def trade_metrics(trades: list[dict]) -> dict:
    """Unikalni kupujący w oknach czasu, przyspieszenie, udział nowych kupujących, bloki z wieloma portfelami.

    Okna liczone wstecz od OSTATNIEJ transakcji w próbce. Gdy próbka (300 transakcji) obejmuje mniej niż okno,
    okno jest po prostu krótsze - span_s mówi, ile czasu faktycznie obejmują dane."""
    rows = []
    for t in trades:
        ts = _ts(t.get("block_timestamp"))
        w = t.get("tx_from_address")
        if ts is None or not w:
            continue
        rows.append((ts, w, t.get("kind"), _f(t.get("volume_in_usd")), t.get("block_number")))
    if len(rows) < 20:
        return {}
    rows.sort()
    now = rows[-1][0]
    out: dict = {"span_s": now - rows[0][0], "n_trades": len(rows)}

    def uniq(kind, lo, hi):   # unikalne portfele w (now-hi, now-lo]
        return {w for ts, w, k, _, _ in rows if k == kind and now - hi < ts <= now - lo}

    for win in (30, 60, 180, 300):
        out[f"ub_{win}s"] = len(uniq("buy", 0, win))
        out[f"us_{win}s"] = len(uniq("sell", 0, win))
    # przyspieszenie: tempo (kupujący/min) w ostatnich 60 s względem 2 minut wcześniej
    prior_rate = len(uniq("buy", 60, 180)) / 2
    out["buyer_accel"] = out["ub_60s"] / prior_rate if prior_rate else (float(out["ub_60s"]) if out["ub_60s"] else 0.0)
    # v0.9: to samo dla sprzedających - "kupujących przybywa, a sprzedający się nie śpieszą" to inny sygnał niż wzrost obu
    prior_sell = len(uniq("sell", 60, 180)) / 2
    out["seller_accel"] = out["us_60s"] / prior_sell if prior_sell else (float(out["us_60s"]) if out["us_60s"] else 0.0)
    recent, earlier = uniq("buy", 0, 180), {w for ts, w, k, _, _ in rows if k == "buy" and ts <= now - 180}
    out["new_buyer_ratio"] = len(recent - earlier) / len(recent) if recent else 0.0

    buy_v = sum(v for _, _, k, v, _ in rows if k == "buy")
    sell_v = sum(v for _, _, k, v, _ in rows if k != "buy")
    out["buy_vol"], out["sell_vol"] = buy_v, sell_v
    out["buy_sell_vol_ratio"] = buy_v / sell_v if sell_v else None
    out["buyer_seller_ratio"] = len({w for _, w, k, _, _ in rows if k == "buy"}) / max(
        len({w for _, w, k, _, _ in rows if k != "buy"}), 1)
    if buy_v + sell_v > 0:
        out["bsi"] = buy_v / (buy_v + sell_v)            # udział kupna w wolumenie: 0.5 = równowaga
        out["buy_count_share"] = sum(1 for r in rows if r[2] == "buy") / len(rows)
        # > 0: transakcji kupna jest dużo więcej niż kupującego wolumenu = drobne zakupy tłumu, duże sprzedaże.
        # Na AMM cena zależy tylko od salda przepływu, więc "absorpcja" kupna oznacza, że ktoś większy sprzedaje w tłum.
        out["flow_divergence"] = out["buy_count_share"] - out["bsi"]

    # skoordynowane zakupy: wiele różnych portfeli kupujących w TYM SAMYM bloku
    blocks: dict = {}
    for ts, w, k, v, b in rows:
        if k == "buy" and b is not None:
            blocks.setdefault(b, []).append((w, v))
    multi = [(len({w for w, _ in x}), sum(v for _, v in x)) for x in blocks.values() if len({w for w, _ in x}) >= 3]
    out["same_block_max_wallets"] = max((n for n, _ in multi), default=1 if blocks else 0)
    out["same_block_buy_share"] = sum(v for _, v in multi) / buy_v if buy_v else 0.0
    # portfele z podejrzanych bloków - kandydaci do (selektywnej, drogiej) analizy źródła finansowania
    out["coordinated_wallets"] = sorted({w for x in blocks.values() if len({w for w, _ in x}) >= 3 for w, _ in x})[:30]

    vol: dict = {}
    for _, w, _, v, _ in rows:
        vol[w] = vol.get(w, 0.0) + v
    tot = sum(vol.values()) or 1.0
    out["top3_wallet_share"] = sum(sorted(vol.values(), reverse=True)[:3]) / tot

    # pierwsi kupujący W OKNIE próbki (u młodych tokenów to bywają snajperzy/insiderzy): ilu już sprzedało?
    # Wysoki udział = ktoś wcześniejszy realizuje zyski na nowych kupujących (kandydat na sygnał zrzutu).
    first_buy: dict = {}
    last_sell: dict = {}
    for ts, w, k, _, _ in rows:
        if k == "buy":
            first_buy.setdefault(w, ts)
        else:
            last_sell[w] = ts
    early = sorted(first_buy, key=first_buy.get)[:20]
    if len(early) >= 5:
        out["early_buyers_sold_share"] = sum(1 for w in early if last_sell.get(w, 0) > first_buy[w]) / len(early)
    return out


# ------------------------------------------------------------------ rozkład posiadaczy (RugCheck)

def gini(values: list[float]) -> float:
    v = sorted(x for x in values if x >= 0)
    n, s = len(v), sum(v)
    if n < 2 or s == 0:
        return 0.0
    return sum((2 * i - n + 1) * x for i, x in enumerate(v)) / (n * s)


def holder_metrics(report: dict | None) -> dict:
    """top1/5/10/20, Gini i współczynnik Nakamoto liczone BEZ adresów pul płynności.

    RugCheck zwraca tylko największych posiadaczy (zwykle 20), więc Gini dotyczy tej czołówki, a Nakamoto
    bywa niedostępny (None), gdy czołówka nie sięga 50% podaży."""
    if not report:
        return {}
    pool = set()
    for m in report.get("markets") or []:
        for k in ("pubkey", "liquidityA", "liquidityB", "mintLP"):
            if m.get(k):
                pool.add(m[k])
    pcts = sorted((_f(h.get("pct")) for h in (report.get("topHolders") or [])
                   if h.get("address") not in pool and h.get("owner") not in pool), reverse=True)
    if not pcts:
        return {}
    out = {"top1": pcts[0], "top5": sum(pcts[:5]), "top10": sum(pcts[:10]), "top20": sum(pcts[:20]),
           "holder_gini": gini(pcts), "n_holders_listed": len(pcts)}
    cum, nak = 0.0, None
    for i, p in enumerate(pcts, 1):
        cum += p
        if cum >= 50:
            nak = i
            break
    out["nakamoto"] = nak
    supply = _f((report.get("token") or {}).get("supply"))
    if supply and report.get("creatorBalance") is not None:
        out["creator_pct"] = _f(report.get("creatorBalance")) / supply * 100
    out["insider_holders"] = sum(1 for h in report.get("topHolders") or [] if h.get("insider"))
    nets = report.get("insiderNetworks") or []
    out["insider_network_accounts"] = sum(_f(n.get("size")) for n in nets if isinstance(n, dict))
    if report.get("score_normalised") is not None:
        out["rugcheck_norm"] = _f(report.get("score_normalised"))
    return out


# ------------------------------------------------------------------ pełny wektor cech

def pair_features(pair: dict) -> dict:
    tx, vol, chg = pair.get("txns") or {}, pair.get("volume") or {}, pair.get("priceChange") or {}
    liq = _f((pair.get("liquidity") or {}).get("usd"))
    mcap = _f(pair.get("marketCap")) or _f(pair.get("fdv"))
    out = {"price": _f(pair.get("priceUsd")), "liq": liq, "mcap": mcap, "liq_bucket": liq_bucket(liq)}
    if pair.get("pairCreatedAt"):
        out["age_min"] = (time.time() * 1000 - pair["pairCreatedAt"]) / 60000
    for w in ("m5", "h1", "h6", "h24"):
        out[f"vol_{w}"] = _f(vol.get(w))
        out[f"ch_{w}"] = _f(chg.get(w))
        b, s = _f((tx.get(w) or {}).get("buys")), _f((tx.get(w) or {}).get("sells"))
        out[f"txns_{w}"] = b + s
        out[f"buy_ratio_{w}"] = b / (b + s) if b + s else None
    if liq:
        out["turnover_h24"] = out["vol_h24"] / liq
        out["vol_liq_h1"] = out["vol_h1"] / liq
        out["mcap_to_liq"] = mcap / liq if mcap else None
        out["ch_h1_per_liq_100k"] = out["ch_h1"] / (liq / 100_000)   # zmiana ceny względem płynności
    return {k: v for k, v in out.items() if v is not None}


def build(pair: dict, report: dict | None = None, trades: list[dict] | None = None, gecko: dict | None = None,
          extra: dict | None = None) -> dict:
    f = pair_features(pair)
    f.update(holder_metrics(report))
    f.update(trade_metrics(trades or []))
    if gecko:
        h = gecko.get("holders") or {}
        if h.get("count") is not None:
            f["holders_count"] = _f(h.get("count"))
        if gecko.get("gt_score") is not None:
            f["gt_score"] = _f(gecko.get("gt_score"))
        if gecko.get("developer_holding_percentage") is not None:
            f["dev_pct"] = _f(gecko.get("developer_holding_percentage"))
    f.update(extra or {})
    f.pop("coordinated_wallets", None)       # lista adresów to dane robocze, nie cecha
    # 6 cyfr znaczących zamiast miejsc po przecinku: ceny memecoinów bywają rzędu 1e-6 (round(.., 4) dawało 0.0)
    return {k: (float(f"{v:.6g}") if isinstance(v, float) else v) for k, v in f.items()}
