"""Wykrywanie rugów przed wejściem - etap 1 (5.10.2026): cechy ze strumienia pump.fun (data/stream.db, zbieracz).

Każda cecha liczona POINT-IN-TIME: tylko z transakcji krzywej o czasie <= t (i historii twórcy sprzed t). Po migracji
strumień nie ma handlu PumpSwap, więc cechy krzywej są "zamrożone" na chwili migracji (posiadacze = salda z krzywej).

Notatki użytkownika -> cechy (pełna tabela w README, sekcja "Moduł wykrywania rugów"):
  bundle          bundle_wallets, bundle_pct, dev_initial_pct (kupna w slocie utworzenia +2)
  snajperzy       sniper_pct (pierwsze 20 slotów), sniper_sold_frac (ile już sprzedali), first_min_ret
  posiadacze      top1_pct, top10_pct, n_holders, n_over_3pct, hhi, creator_pct ("nikt > 3%" vs "czysto = scam")
  schodki         pullback_ratio, max_pullback, buy_size_cv, intertrade_cv, repeat_buy_share, same_slot_share
  świeże portfele fresh_buyer_share, fresh_top20_share, first_seen_cluster (proxy z pierwszego pojawienia w strumieniu)
  twórca          creator_prev_tokens, creator_prev_migrated, creator_mig_rate, creator_late_buy_pct, creator_sold_frac
  czas            curve_minutes (od utworzenia do migracji), mayhem
Etap 2 (później): klastry wspólnego źródła finansowania z RPC (bubble mapy, "funding time") - patrz README.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

SUPPLY_RAW = 1e15            # 1 mld tokenów pump.fun x 10^6 (decimals)
BUNDLE_SLOTS = 2
SNIPER_SLOTS = 20
FRESH_S = 600                # portfel "świeży": pierwszy raz w strumieniu <= 10 min przed pierwszym kupnem tego tokena


@dataclass
class RugAssessment:
    score: float                                  # 0-1 (etap 1: odsetek zapalonych flag)
    flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    features: dict = field(default_factory=dict)


def _cv(xs: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    m = statistics.mean(xs)
    return statistics.pstdev(xs) / m if m else None


def top_buyers(tr: list[tuple], n: int, exclude: set | None = None) -> list[int]:
    """Portfele, które kupiły najwięcej tokenów (brutto) - bez pośredników z ujemnym saldem w tym tokenie."""
    got: dict[int, float] = {}
    net: dict[int, float] = {}
    for x in tr:
        net[x[2]] = net.get(x[2], 0) + (x[5] if x[3] else -x[5])
        if x[3]:
            got[x[2]] = got.get(x[2], 0) + x[5]
    skip = {w for w, v in net.items() if v < -1e-3 * SUPPLY_RAW} | (exclude or set())
    return [w for w, _ in sorted(((w, v) for w, v in got.items() if w not in skip), key=lambda kv: -kv[1])[:n]]


def curve_features(trades: list[tuple], meta: dict, t: float, first_seen: dict[int, float],
                   creator_hist: dict | None = None) -> dict:
    """trades: [(slot, ts, wallet_id, buy, sol, tok, vsol, vtok)] tokena posortowane po slocie; meta: created_ts,
    created_slot, creator (wallet_id), mayhem, mig_ts (opcjonalnie); first_seen: wallet_id -> pierwszy ts w strumieniu
    (liczony ze strumienia sprzed t - patrz rug_backtest.first_seen_map); creator_hist: {prev_tokens, prev_migrated}."""
    tr = [x for x in trades if x[1] <= t]
    f: dict = {"n_trades": len(tr), "mayhem": int(bool(meta.get("mayhem")))}
    cs, creator = meta["created_slot"], meta.get("creator")
    if meta.get("mig_ts") and meta["mig_ts"] <= t:
        f["curve_minutes"] = (meta["mig_ts"] - meta["created_ts"]) / 60
    f["age_min"] = (t - meta["created_ts"]) / 60
    if not tr:
        return f
    buys = [x for x in tr if x[3]]

    # --- bundle i snajperzy (sloty od utworzenia) ---
    early = lambda n: [x for x in buys if x[0] - cs <= n and x[2] != creator]
    b = early(BUNDLE_SLOTS)
    f["bundle_wallets"] = len({x[2] for x in b})
    f["bundle_pct"] = sum(x[5] for x in b) / SUPPLY_RAW * 100
    f["dev_initial_pct"] = sum(x[5] for x in buys if x[2] == creator and x[0] - cs <= BUNDLE_SLOTS) / SUPPLY_RAW * 100
    sn = early(SNIPER_SLOTS)
    snw = {x[2] for x in sn}
    f["sniper_wallets"] = len(snw)
    f["sniper_pct"] = sum(x[5] for x in sn) / SUPPLY_RAW * 100
    sn_bought = sum(x[5] for x in tr if x[2] in snw and x[3])
    sn_sold = sum(x[5] for x in tr if x[2] in snw and not x[3])
    f["sniper_sold_frac"] = min(sn_sold / sn_bought, 1.0) if sn_bought else 0.0
    px = lambda x: x[6] / x[7] if x[7] else 0
    p0 = px(tr[0])
    first_min = [x for x in tr if x[1] <= meta["created_ts"] + 60]
    f["first_min_ret"] = (px(first_min[-1]) / p0 - 1) if first_min and p0 else 0.0

    # --- posiadacze (salda z krzywej w chwili t) ---
    bal: dict[int, float] = {}
    for x in tr:
        bal[x[2]] = bal.get(x[2], 0) + (x[5] if x[3] else -x[5])
    hold = sorted((v for v in bal.values() if v > SUPPLY_RAW * 1e-6), reverse=True)
    # handel przez routery/boty: TradeEvent zapisuje podpisującego (pośrednika), tokeny idą dalej przelewem, którego
    # strumień nie widzi -> salda z krzywej niemożliwe (suma > 85% podaży albo ujemne). 5.10: 71 z 338 tokenów.
    # Wtedy cechy posiadaczy = brak (None), a sama niespójność jest cechą.
    ok = sum(hold) <= 0.85 * SUPPLY_RAW and min(bal.values()) >= -1e-3 * SUPPLY_RAW
    f["balances_ok"] = int(ok)
    if ok:
        f["n_holders"] = len(hold)
        f["top1_pct"] = hold[0] / SUPPLY_RAW * 100 if hold else 0.0
        f["top10_pct"] = sum(hold[:10]) / SUPPLY_RAW * 100
        f["n_over_3pct"] = sum(v > 0.03 * SUPPLY_RAW for v in hold)
        tot = sum(hold)
        f["hhi"] = sum((v / tot) ** 2 for v in hold) if tot else 0.0
        f["creator_pct"] = max(bal.get(creator, 0), 0) / SUPPLY_RAW * 100 if creator is not None else 0.0
    else:
        for k in ("n_holders", "top1_pct", "top10_pct", "n_over_3pct", "hhi", "creator_pct"):
            f[k] = None

    # --- "schodki": kształt ceny i regularność przepływu ---
    prices = [px(x) for x in tr if px(x) > 0]
    up = dn = 0.0
    peak, max_dd = prices[0] if prices else 0, 0.0
    for a, c in zip(prices, prices[1:]):
        if c > a:
            up += c / a - 1
        else:
            dn += 1 - c / a
        peak = max(peak, c)
        max_dd = max(max_dd, 1 - c / peak if peak else 0)
    f["pullback_ratio"] = dn / up if up else 0.0
    f["max_pullback"] = max_dd
    f["buy_size_cv"] = _cv([x[4] for x in buys])
    f["intertrade_cv"] = _cv([b_[1] - a_[1] for a_, b_ in zip(tr, tr[1:])])
    seen, rep = set(), 0
    for x in buys:
        rep += x[2] in seen
        seen.add(x[2])
    f["repeat_buy_share"] = rep / len(buys) if buys else 0.0
    f["unique_buyers"] = len(seen)
    f["sell_share"] = 1 - len(buys) / len(tr)
    by_slot: dict[int, set] = {}
    for x in buys:
        by_slot.setdefault(x[0], set()).add(x[2])
    f["same_slot_share"] = sum(1 for x in buys if len(by_slot[x[0]]) >= 2) / len(buys) if buys else 0.0

    # --- świeże portfele (pierwsze pojawienie w strumieniu tuż przed kupnem) ---
    first_buy: dict[int, float] = {}
    for x in buys:
        first_buy.setdefault(x[2], x[1])
    fresh = [w for w, ts in first_buy.items() if ts - first_seen.get(w, ts) <= FRESH_S]
    f["fresh_buyer_share"] = len(fresh) / len(first_buy) if first_buy else 0.0
    top20 = top_buyers(tr, 20)          # kupujący (wiarygodne), nie salda (routery psują salda - patrz wyżej)
    f["fresh_top20_share"] = sum(w in set(fresh) for w in top20) / len(top20) if top20 else 0.0
    fs = sorted(first_seen.get(w, first_buy.get(w, t)) for w in top20)
    f["first_seen_cluster"] = max((sum(1 for y in fs if x <= y <= x + FRESH_S) for x in fs), default=0) / max(len(fs), 1)

    # --- twórca ---
    if creator is not None:
        mig = meta.get("mig_ts") or t
        late0 = meta["created_ts"] + 0.75 * (min(mig, t) - meta["created_ts"])
        f["creator_late_buy_pct"] = sum(x[5] for x in buys if x[2] == creator and x[1] >= late0) / SUPPLY_RAW * 100
        cb = sum(x[5] for x in buys if x[2] == creator)
        cs_ = sum(x[5] for x in tr if x[2] == creator and not x[3])
        f["creator_sold_frac"] = min(cs_ / cb, 1.0) if cb else 0.0
    if creator_hist is not None:
        f["creator_prev_tokens"] = creator_hist["prev_tokens"]
        f["creator_prev_migrated"] = creator_hist["prev_migrated"]
        f["creator_mig_rate"] = (creator_hist["prev_migrated"] / creator_hist["prev_tokens"]
                                 if creator_hist["prev_tokens"] else None)
    return f


def assess(features: dict, rules: list[tuple[str, str, float]]) -> RugAssessment:
    """Etap 1: reguły (cecha, '>'|'<', próg) dobrane na danych treningowych (rug_backtest). score = odsetek flag."""
    flags, reasons = [], []
    for name, op, thr in rules:
        v = features.get(name)
        if v is None:
            continue
        if (v > thr) if op == ">" else (v < thr):
            flags.append(name)
            reasons.append(f"{name} = {v:.3g} {op} {thr:.3g}")
    return RugAssessment(len(flags) / len(rules) if rules else 0.0, flags, reasons, features)
