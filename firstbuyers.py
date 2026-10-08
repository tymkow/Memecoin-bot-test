"""Skład pierwszych kupujących tokena (6.10.2026) - WSPÓLNA logika dla analizy (analizy/first_buyers.py) i logowania
na żywo (fb_logger.py), żeby to, co testujemy, było tym samym, co zapisujemy na żywo. Tylko dane sprzed chwili t.

Pierwsi kupujący = 20 pierwszych RÓŻNYCH portfeli kupujących na krzywej pump.fun (kolejność slotów), bez routerów
(ujemne saldo w >= 3 tokenach: TradeEvent zapisuje podpisującego, a tokeny idą dalej przelewem).
Grupy (kolejność ma znaczenie):
  insider = twórca | zasilony przez twórcę lub jego zasilającego | wspólny zasilający z innym pierwszym kupującym |
            kupno w slocie utworzenia (bundle)
  smart   = (od 6.10 wg użytkownika) >= 5 pozycji zamkniętych przed t, >= 55% wygranych, mediana trzymania > 30 min
            i NIE sprzedał tego tokena w 5 min od zakupu
  sniper  = kupno <= 3 sloty od utworzenia | portfel "aktywny" (>= 3000 transakcji) |
            (>= 30 wcześniejszych tokenów i mediana trzymania <= 120 s)
  retail  = reszta
Młody insider ze zrzutem (reguła zamiast klastra K3 z KMeans): insider, wiek portfela < 48 h, sprzedał w 5 min.
Wiek portfela tylko przy znanej PIERWSZEJ transakcji (u "aktywnych" Helius zwraca najnowsze 3000 - błąd z 6.10).
"""
from __future__ import annotations

import collections
import json
import math
import statistics

N_FIRST = 20
SUPPLY = 1e15
HUB_MIN = 15
YOUNG_H = 48
SMART_HOLD_S = 1800
GROUPS = ("insider", "smart", "sniper", "retail")
SCORE_FEATS = ("frac_insider", "frac_shared_funder", "young_insider_dump", "frac_sniper")


def routers(trades_by_mint: dict, mint_ids) -> set:
    neg = collections.Counter()
    for mid in mint_ids:
        net = collections.defaultdict(float)
        for x in trades_by_mint.get(mid, []):
            net[x[2]] += x[5] if x[3] else -x[5]
        for w, v in net.items():
            if v < -1e-3 * SUPPLY:
                neg[w] += 1
    return {w for w, n in neg.items() if n >= 3}


def first_buyers(tr: list, exclude: set, n: int = N_FIRST) -> list[int]:
    """tr: [(slot, ts, wallet_id, buy, sol, tok)] posortowane po slocie."""
    out = []
    for x in tr:
        if x[3] and x[2] not in exclude and x[2] not in out:
            out.append(x[2])
            if len(out) >= n:
                break
    return out


def prior_stats(hist: list, t: float) -> dict:
    """hist: [(first_buy_ts, first_sell_ts, last_ts, buy_sol, sell_sol)] - tylko pozycje w CAŁOŚCI sprzed t."""
    tokens = sum(1 for p in hist if p[0] is not None and p[0] < t)
    closed = [p for p in hist if p[2] < t and p[1] is not None and p[0] is not None]
    wins = [p[4] - p[3] > 0 for p in closed]
    holds = [p[1] - p[0] for p in closed if p[1] >= p[0]]
    return {"n_tokens": tokens, "n_closed": len(closed), "win_rate": statistics.mean(wins) if wins else None,
            "pnl_sol": sum(p[4] - p[3] for p in closed) / 1e9, "hold_med_s": statistics.median(holds) if holds else None}


def token_rows(tr: list, created_slot: int, creator, t: float, rts: set, addr_of, info: dict, hist: dict,
               hubs: set) -> list[dict]:
    """Cechy i grupa każdego z pierwszych kupujących tokena w chwili t. addr_of: wallet_id -> adres;
    info: adres -> wiersz wallet_funding (status, funder, first_ts, sig_times); hist: wallet_id -> pozycje."""
    tr = [x for x in tr if x[1] <= t]
    ws = first_buyers(tr, rts)
    cfund = (info.get(addr_of(creator)) or {}).get("funder") if creator is not None else None
    linked = {x for x in (addr_of(creator) if creator is not None else None, cfund) if x and x not in hubs}
    funders = {w: (info.get(addr_of(w)) or {}).get("funder") for w in ws}
    fcount = collections.Counter(f for f in funders.values() if f and f not in hubs)
    first_slot: dict = {}
    for x in tr:
        if x[3] and x[2] in ws and x[2] not in first_slot:
            first_slot[x[2]] = x[0]
    slot_users = collections.Counter(first_slot.values())
    rows = []
    for w in ws:
        mine = [x for x in tr if x[2] == w]
        buys = [x for x in mine if x[3]]
        fb_ts = buys[0][1] if buys else None
        bought = sum(x[5] for x in buys)
        sold5 = sum(x[5] for x in mine if not x[3] and fb_ts is not None and x[1] <= fb_ts + 300)
        i = info.get(addr_of(w)) or {}
        st = i.get("status")
        age = (t - i["first_ts"]) / 3600 if st == "ok" and i.get("first_ts") and i["first_ts"] <= t else None
        ntx = (sum(1 for s in json.loads(i.get("sig_times") or "[]") if s < t) if st == "ok"
               else (3000 if st == "aktywny" else None))
        ps = prior_stats(hist.get(w, []), t)
        r = {"wallet": w, "is_creator": int(w == creator), "slot_rel": first_slot.get(w, created_slot) - created_slot,
             "buy_sol": sum(x[4] for x in buys) / 1e9, "sold_5m": int(bought > 0 and sold5 >= 0.5 * bought),
             "same_slot": int(slot_users[first_slot.get(w)] >= 2),
             "shared_funder": int(bool(funders[w]) and fcount.get(funders[w], 0) >= 2),
             "by_creator": int(bool(funders[w]) and funders[w] in linked), "active": int(st == "aktywny"),
             "funding_known": int(st in ("ok", "aktywny")), "age_h": age, "n_tx": ntx,
             **{f"prior_{k}": v for k, v in ps.items()}}
        r["group"] = classify(r)
        r["young_insider_dump"] = int(r["group"] == "insider" and age is not None and age < YOUNG_H and r["sold_5m"])
        rows.append(r)
    return rows


def classify(r: dict) -> str:
    if r["is_creator"] or r["by_creator"] or r["shared_funder"] or (r["slot_rel"] <= 0 and not r["is_creator"]):
        return "insider"
    if ((r["prior_n_closed"] or 0) >= 5 and (r["prior_win_rate"] or 0) >= 0.55
            and (r["prior_hold_med_s"] or 0) > SMART_HOLD_S and not r["sold_5m"]):
        return "smart"
    if r["slot_rel"] <= 3 or r["active"] or ((r["prior_n_tokens"] or 0) >= 30 and (r["prior_hold_med_s"] or 1e9) <= 120):
        return "sniper"
    return "retail"


def composition(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"n_first": 0}
    vol = sum(r["buy_sol"] for r in rows) or 1
    f = {f"frac_{g}": sum(r["group"] == g for r in rows) / n for g in GROUPS}
    f.update({f"vol_{g}": sum(r["buy_sol"] for r in rows if r["group"] == g) / vol for g in GROUPS})
    ages = [r["age_h"] for r in rows if r["age_h"] is not None]
    f.update(n_first=n, age_med_h=statistics.median(ages) if ages else None,
             frac_young=sum(a < 24 for a in ages) / n, frac_sold5m=sum(r["sold_5m"] for r in rows) / n,
             frac_same_slot=sum(r["same_slot"] for r in rows) / n,
             frac_shared_funder=sum(r["shared_funder"] for r in rows) / n,
             frac_active=sum(r["active"] for r in rows) / n,
             young_insider_dump=sum(r["young_insider_dump"] for r in rows) / n,
             funding_known=sum(r["funding_known"] for r in rows) / n,
             dominant=max(GROUPS, key=lambda g: (f[f"frac_{g}"], -GROUPS.index(g))))
    return f


def score(feats: dict, model: dict | None) -> float | None:
    """Regresja logistyczna z analizy (współczynniki na cechach standaryzowanych średnią/odch. z eksploracji)."""
    if not model:
        return None
    z = model["intercept"]
    for k, w in model["coef"].items():
        v = feats.get(k)
        if v is None:
            return None
        z += w * (v - model["mean"][k]) / (model["std"][k] or 1)
    return 1 / (1 + math.exp(-z))
