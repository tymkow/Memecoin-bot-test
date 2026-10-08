"""Backtest modułu wykrywania rugów (etap 1). Uruchamiane przez: python rug_dataset.py build|report

build: dla każdej migracji z pobranymi świecami i chwil migracja +0/+2/+5/+15 min: cechy krzywej (rugguard) w chwili t,
       cechy ceny po migracji do chwili t, etykieta (RUG_SZYBKI / RUG_PO_POMPIE / OK) i wynik wejścia po regułach wyjścia
       bota (exit_research.simulate: SL -25% jak hybrid, SL -40% jak *_wide, SL -25% + time stop 5 min jak safety_ts5).
report: podział w CZASIE - pierwsze 60% migracji = trening (kierunek i próg każdej cechy), ostatnie 40% = TEST (liczony
       raz). Dla każdej cechy: AUC (trening / test), precyzja, czułość, ile OK i RUG_PO_POMPIE odrzuca, wynik wejść
       oflagowanych vs reszty. Potem liczba flag (k z treningu) i wpływ filtra na wynik, macierz pomyłek, przykłady.
"""
from __future__ import annotations

import json
import math
import statistics
import time

import collector
import exit_research
import rugguard
from rug_dataset import BOT_DB, OFFSETS_MIN, STREAM_DB, WINDOW_S, migrations, out_db, ro

# PUMP = TP1 bota (+50%): "pompa" ma znaczyć, że bot zdążył coś sprzedać. W propozycji z 5.10 było +30% z błędnym
# uzasadnieniem "+30% to TP1" - TP1 w config.take_profit_levels to +50%, więc próg poprawiony do intencji.
FAST_DROP, FAST_MIN, PUMP, LATE_DROP = 0.30, 30, 1.50, 0.20
POLICIES = {
    "SL25 (hybrid)": dict(stop_frac=0.25, time_stop=(240, 0.10)),
    "SL40 (wide)": dict(stop_frac=0.40, time_stop=(240, 0.10)),
    "SL25+ts5": dict(stop_frac=0.25, time_stop=(5, 0.0)),
}


# ------------------------------------------------------------------ etykiety i symulacja
def label(cands: list, t: float) -> dict | None:
    """Świece PumpSwap [ts,o,h,l,c,v] rosnąco; cena odniesienia = cena w chwili t (bez zaglądania w przyszłość)."""
    done = [c for c in cands if c[0] + 60 <= t]
    path = [c for c in cands if c[0] + 60 > t and c[0] <= t + WINDOW_S] if not done else \
           [c for c in cands if c[0] >= done[-1][0] + 60 and c[0] <= t + WINDOW_S]
    if not done and path:
        # chwila migracji: w tej samej minucie snajperzy kupują w bloku migracji (np. 150 SOL = cena x7.7) - po cenie
        # otwarcia nikt z opóźnieniem nie kupi; odniesieniem jest zamknięcie pierwszej minuty (5.10.2026)
        ref, path = path[0][4], path[1:]
    else:
        ref = done[-1][4] if done else None
    if not ref or not path:
        return None
    pumped, fast, late, t_pump = False, False, False, None
    for ts, o, h, l, c, v in path:
        mins = (ts - t) / 60
        if not pumped and mins <= FAST_MIN and l <= ref * FAST_DROP:      # najpierw dołek (pesymistycznie)
            fast = True
            break
        if h >= ref * PUMP and not pumped:
            pumped, t_pump = True, ts
        if pumped and l <= ref * LATE_DROP:
            late = True
            break
    hi = max(c[2] for c in path) / ref - 1
    lo = min(c[3] for c in path) / ref - 1
    ret30 = next((c[4] for c in reversed(path) if c[0] <= t + FAST_MIN * 60), path[0][4]) / ref - 1
    return {"label": "RUG_SZYBKI" if fast else ("RUG_PO_POMPIE" if late else "OK"), "fast_rug": int(fast),
            "mfe": hi, "mae": lo, "ret_30m": ret30, "ret_6h": path[-1][4] / ref - 1, "ref": ref}


def sim_all(cands: list, t: float, latency_s: int = 10) -> dict:
    """Wejście po opóźnieniu: otwarcie pierwszej świecy zaczynającej się po t+latency (świeca 1-min, więc realnie
    10-70 s), wyjście regułami bota; zwroty netto (koszty z exit_research: EC/XC)."""
    path = [c for c in cands if t + latency_s <= c[0] <= t + WINDOW_S]
    if not path:
        return {}
    ref = path[0][1]
    out = {}
    for name, p in POLICIES.items():
        r, why, _ = exit_research.simulate(path, ref, path[0][0], stop=ref * (1 - p["stop_frac"]),
                                           time_stop=p["time_stop"])
        out[name] = r
    return out


def first_seen_map(stream) -> dict[int, float]:
    return dict(stream.execute("SELECT wallet_id, MIN(ts) FROM trades WHERE ts < 2000000000 GROUP BY wallet_id"))


def gap_overlap(gaps, a: float, b: float) -> bool:
    return any(g0 < b and g1 > a for g0, g1 in gaps)


def build():
    t0 = time.time()
    stream, db = ro(STREAM_DB), out_db()
    migs = migrations(stream)
    pools = {r["mint"]: r["pool"] for r in db.execute("SELECT mint, pool FROM pools WHERE status='ok'")}
    migs = [m for m in migs if m["mint"] in pools]
    ids = [m["mint_id"] for m in migs]
    print(f"migracji ze świecami: {len(migs)}; wczytuję transakcje krzywej...", flush=True)
    trades: dict[int, list] = {i: [] for i in ids}
    q = (f"SELECT mint_id, slot, ts, wallet_id, buy, sol, tok, vsol, vtok FROM trades WHERE ts < 2000000000 AND "
         f"mint_id IN ({','.join(map(str, ids))}) ORDER BY slot")
    for r in stream.execute(q):
        trades[r[0]].append(tuple(r[1:]))
    fs = first_seen_map(stream)
    stream_start = stream.execute("SELECT MIN(ts) FROM trades WHERE ts < 2000000000").fetchone()[0]
    gaps = collector.data_holes(stream)          # dziury w czasie bloku (tabela gaps do 5.10 niepełna)
    by_creator: dict[int, list] = {}
    for r in stream.execute("SELECT id, creator, created_ts FROM mints WHERE creator IS NOT NULL AND created_ts IS NOT NULL"):
        by_creator.setdefault(r["creator"], []).append((r["created_ts"], r["id"]))
    mig_ts = dict(stream.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind='migrate' GROUP BY mint_id"))
    print(f"wczytano w {time.time() - t0:.0f} s; liczę próbki...", flush=True)
    n = 0
    for m in migs:
        cands = [list(r) for r in db.execute("SELECT ts,o,h,l,c,v FROM candles WHERE pool=? ORDER BY ts", (pools[m["mint"]],))]
        meta = {"created_ts": m["created_ts"], "created_slot": m["created_slot"], "creator": m["creator"],
                "mayhem": m["mayhem"], "mig_ts": m["mig_ts"]}
        for off in OFFSETS_MIN:
            t = m["mig_ts"] + off * 60
            lab = label(cands, t)
            if lab is None:
                continue
            hist = None
            if m["creator"] is not None:
                prev = [i for ts, i in by_creator.get(m["creator"], []) if ts < m["created_ts"]]
                hist = {"prev_tokens": len(prev), "prev_migrated": sum(1 for i in prev if mig_ts.get(i, 1e18) < t)}
            f = rugguard.curve_features(trades[m["mint_id"]], meta, t, fs, hist)
            since = [c for c in cands if m["mig_ts"] - 60 <= c[0] and c[0] + 60 <= t]
            f["post_ret"] = (since[-1][4] / since[0][1] - 1) if since and since[0][1] else 0.0
            f["post_vol_usd"] = sum(c[5] for c in since)
            f["stream_age_h"] = (m["created_ts"] - stream_start) / 3600
            f["gap"] = int(gap_overlap(gaps, m["created_ts"] - 60, t))
            f["sim"] = sim_all(cands, t)
            db.execute("INSERT OR REPLACE INTO samples VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (m["mint"], t, off, lab["label"], lab["fast_rug"], lab["mfe"], lab["mae"], lab["ret_30m"],
                        lab["ret_6h"], json.dumps(f)))
            n += 1
    db.commit()
    print(f"próbek: {n} w {time.time() - t0:.0f} s")
    for r in db.execute("SELECT offset_min, label, COUNT(*) FROM samples GROUP BY 1, 2 ORDER BY 1, 2"):
        print(f"  +{r[0]:>2} min  {r[1]:<14} {r[2]}")


# ------------------------------------------------------------------ raport
def auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank, i, rs = 1, 0, 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        r = (rank + rank + (j - i) - 1) / 2
        rs += r * sum(1 for k in range(i, j) if allv[k][1])
        rank += j - i
        i = j
    return (rs - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else float("nan")


FEATURES = ["bundle_wallets", "bundle_pct", "dev_initial_pct", "sniper_wallets", "sniper_pct", "sniper_sold_frac",
            "first_min_ret", "n_holders", "top1_pct", "top10_pct", "n_over_3pct", "hhi", "creator_pct",
            "pullback_ratio", "max_pullback", "buy_size_cv", "intertrade_cv", "repeat_buy_share", "unique_buyers",
            "sell_share", "same_slot_share", "fresh_buyer_share", "fresh_top20_share", "first_seen_cluster",
            "creator_late_buy_pct", "creator_sold_frac", "creator_prev_tokens", "creator_prev_migrated",
            "creator_mig_rate", "curve_minutes", "mayhem", "n_trades", "post_ret", "post_vol_usd"]
FRESH = {"fresh_buyer_share", "fresh_top20_share", "first_seen_cluster", "creator_prev_tokens",
         "creator_prev_migrated", "creator_mig_rate"}       # zależne od długości historii strumienia


def load(offset: int):
    db = out_db()
    rows = []
    for r in db.execute("SELECT * FROM samples WHERE offset_min=? ORDER BY t", (offset,)):
        f = json.loads(r["features"])
        if f.get("gap"):
            continue
        rows.append({"mint": r["mint"], "t": r["t"], "label": r["label"], "y": r["fast_rug"], "f": f,
                     "sim": f.get("sim") or {}, "mfe": r["mfe"], "mae": r["mae"]})
    return rows


def choose(train: list, name: str):
    """Kierunek z AUC na treningu; próg = tercyl treningu po 'rugowej' stronie (flaga ~1/3 tokenów)."""
    vals = [(r["f"].get(name), r["y"]) for r in train if r["f"].get(name) is not None
            and not (name in FRESH and r["f"]["stream_age_h"] < 3)]
    if len(vals) < 30:
        return None
    a = auc([v for v, y in vals if y], [v for v, y in vals if not y])
    if a is None:
        return None
    xs = sorted(v for v, _ in vals)
    if a >= 0.5:
        return name, ">", xs[int(len(xs) * 2 / 3)], a
    return name, "<", xs[int(len(xs) / 3)], a


def flagged(r, rule) -> bool | None:
    name, op, thr = rule[:3]
    v = r["f"].get(name)
    if v is None or (name in FRESH and r["f"]["stream_age_h"] < 3):
        return None
    return v > thr if op == ">" else v < thr


def stats(rows, flag_fn, pol="SL25 (hybrid)"):
    fl = [r for r in rows if flag_fn(r) is True]
    ok = [r for r in rows if flag_fn(r) is False]
    rugs = [r for r in rows if r["y"] and flag_fn(r) is not None]
    goods = [r for r in rows if r["label"] == "OK" and flag_fn(r) is not None]
    late = [r for r in rows if r["label"] == "RUG_PO_POMPIE" and flag_fn(r) is not None]
    return {
        "n_flag": len(fl), "n": len(fl) + len(ok),
        "prec": _mean([r["y"] for r in fl]), "base": _mean([r["y"] for r in fl + ok]),
        "recall": sum(r["y"] for r in fl) / len(rugs) if rugs else float("nan"),
        "ok_rej": sum(r["label"] == "OK" for r in fl) / len(goods) if goods else float("nan"),
        "late_rej": sum(r["label"] == "RUG_PO_POMPIE" for r in fl) / len(late) if late else float("nan"),
        "ret_flag": _mean([r["sim"].get(pol) for r in fl]), "ret_rest": _mean([r["sim"].get(pol) for r in ok]),
    }


def report(offset: int = 0, split: float = 0.6, rows: list | None = None, features: list | None = None,
           bot: bool = True):
    """rows/features: inny zestaw (np. rug_funding dokłada cechy klastrów); bot=False pomija pozycje bota."""
    rows = load(offset) if rows is None else rows
    if len(rows) < 100:
        print(f"za mało próbek ({len(rows)}) - najpierw: python rug_dataset.py fetch && python rug_dataset.py build")
        return
    cut = int(len(rows) * split)
    train, test = rows[:cut], rows[cut:]
    fmt = lambda ts: time.strftime("%d.%m %H:%M", time.localtime(ts))
    print(f"punkt decyzji: migracja +{offset} min | próbek {len(rows)} (bez tokenów z luką w danych)")
    print(f"trening {fmt(train[0]['t'])} - {fmt(train[-1]['t'])} (n={len(train)}), "
          f"TEST {fmt(test[0]['t'])} - {fmt(test[-1]['t'])} (n={len(test)})")
    for part, rs in (("trening", train), ("TEST", test)):
        c = {k: sum(r["label"] == k for r in rs) for k in ("RUG_SZYBKI", "RUG_PO_POMPIE", "OK")}
        sims = {p: _mean([r["sim"].get(p) for r in rs]) for p in POLICIES}
        print(f"  {part:<8} etykiety {c} | śr. wynik wejścia: " + ", ".join(f"{p} {v:+.1%}" for p, v in sims.items()))

    print("\n== 1) każda cecha osobno: kierunek i próg z TRENINGU, liczby na TEŚCIE (flaga = 'rugowa' 1/3) ==")
    print(f"  {'cecha':<22}{'kier.':>6}{'próg':>10}{'AUC tr':>8}{'AUC test':>9}{'flaga':>7}{'precyzja':>9}{'baza':>6}"
          f"{'czułość':>8}{'OK odrz.':>9}{'pompa odrz.':>12}{'wynik flag':>11}{'reszta':>8}")
    rules = []
    for name in (features or FEATURES):
        rule = choose(train, name)
        if not rule:
            continue
        vals = [(r["f"].get(name), r["y"]) for r in test if flagged(r, rule) is not None]
        a_te = auc([v for v, y in vals if y], [v for v, y in vals if not y])
        a_te = a_te if rule[1] == ">" else (1 - a_te if a_te is not None else None)
        a_tr = rule[3] if rule[1] == ">" else 1 - rule[3]
        s = stats(test, lambda r: flagged(r, rule))
        rules.append((*rule, a_tr, a_te, s))
        print(f"  {name:<22}{rule[1]:>6}{rule[2]:>10.3g}{a_tr:>8.3f}{(a_te or float('nan')):>9.3f}"
              f"{s['n_flag']:>7}{s['prec']:>9.0%}{s['base']:>6.0%}{s['recall']:>8.0%}{s['ok_rej']:>9.0%}"
              f"{s['late_rej']:>12.0%}{s['ret_flag']:>+11.1%}{s['ret_rest']:>+8.1%}")

    # sprzeczność "nikt > 3% = czysto" vs "czysta zakładka może być scamem"
    print("\n== 2) 'nikt > 3%' vs 'czysto = scam' (cały okres, posiadacze liczeni na portfelach) ==")
    for lbl, fn in (("top1 <= 3% (czysto)", lambda r: (r["f"].get("top1_pct") or 99) <= 3),
                    ("top1 3-10%", lambda r: 3 < (r["f"].get("top1_pct") or 99) <= 10),
                    ("top1 > 10%", lambda r: (r["f"].get("top1_pct") or 0) > 10)):
        rs = [r for r in rows if fn(r)]
        if rs:
            print(f"  {lbl:<22} n={len(rs):>4}  RUG_SZYBKI {_mean([r['y'] for r in rs]):>4.0%}  "
                  f"RUG_PO_POMPIE {_mean([r['label'] == 'RUG_PO_POMPIE' for r in rs]):>4.0%}  "
                  f"wynik SL25 {_mean([r['sim'].get('SL25 (hybrid)') for r in rs]):+.1%}")

    # liczba flag: cechy, które na treningu mają AUC >= 0.55 (wybór bez patrzenia na test)
    good = [r for r in rules if r[4] >= 0.55]
    print(f"\n== 3) liczba flag z {len(good)} cech o AUC trening >= 0.55: "
          + ", ".join(f"{r[0]}{r[1]}{r[2]:.3g}" for r in good))
    cnt = lambda r: sum(1 for g in good if flagged(r, g) is True)
    ks = sorted({cnt(r) for r in train})
    print(f"  {'k (flagi >=)':<14}{'trening: rugi':>14}{'n':>6}{'wynik SL25':>11} | {'TEST: rugi':>11}{'n':>6}"
          + "".join(f"{p:>16}" for p in POLICIES))
    for k in ks:
        tr = [r for r in train if cnt(r) >= k]
        te = [r for r in test if cnt(r) >= k]
        print(f"  {k:<14}{_mean([r['y'] for r in tr]):>14.0%}{len(tr):>6}{_mean([r['sim'].get('SL25 (hybrid)') for r in tr]):>+11.1%} | "
              f"{_mean([r['y'] for r in te]):>11.0%}{len(te):>6}"
              + "".join(f"{_mean([r['sim'].get(p) for r in te]):>+16.1%}" for p in POLICIES))
    # próg k z treningu: najlepszy wynik SL25 pozostałych (bez flagi >= k) przy >= 30% próbek zostających
    best = None
    for k in ks[1:]:
        keep = [r for r in train if cnt(r) < k]
        if len(keep) >= 0.3 * len(train):
            v = _mean([r["sim"].get("SL25 (hybrid)") for r in keep])
            if best is None or v > best[1]:
                best = (k, v)
    if not best:
        return
    k = best[0]
    print(f"\n== 4) FILTR: odrzuć, gdy flag >= {k} (k wybrane na treningu). TEST, te same wejścia ==")
    keep, drop = [r for r in test if cnt(r) < k], [r for r in test if cnt(r) >= k]
    for p in POLICIES:
        a = [r["sim"].get(p) for r in test if r["sim"].get(p) is not None]
        b = [r["sim"].get(p) for r in keep if r["sim"].get(p) is not None]
        print(f"  {p:<16} bez filtra: n={len(a):>4} śr. {_mean(a):+.2%} suma {sum(a):+.2f} stawki | "
              f"z filtrem: n={len(b):>4} śr. {_mean(b):+.2%} suma {sum(b):+.2f} stawki")
    tp = sum(r["y"] for r in drop); fp = len(drop) - tp
    fn = sum(r["y"] for r in keep); tn = len(keep) - fn
    print(f"  macierz pomyłek (RUG_SZYBKI):  odrzucone rug {tp}, odrzucone nie-rug {fp}, przepuszczone rug {fn}, "
          f"przepuszczone nie-rug {tn}")
    print(f"  odrzucone RUG_PO_POMPIE: {sum(r['label'] == 'RUG_PO_POMPIE' for r in drop)} z "
          f"{sum(r['label'] == 'RUG_PO_POMPIE' for r in test)}")
    print("  fałszywe alarmy (odrzucone, a zarobiłyby najwięcej):")
    for r in sorted([r for r in drop if not r["y"]], key=lambda r: -(r["sim"].get("SL25 (hybrid)") or -9))[:5]:
        print(f"    {r['mint']}  {r['label']:<14} wynik {r['sim'].get('SL25 (hybrid)', 0):+.0%}  MFE {r['mfe']:+.0%}  flagi {cnt(r)}")
    print("  przepuszczone rugi (najgorsze):")
    for r in sorted([r for r in keep if r["y"]], key=lambda r: r["sim"].get("SL25 (hybrid)") or 0)[:5]:
        print(f"    {r['mint']}  wynik {r['sim'].get('SL25 (hybrid)', 0):+.0%}  MAE {r['mae']:+.0%}  flagi {cnt(r)}")
    if bot:
        bot_positions(good, k)


def bot_positions(good: list, k: int):
    """Prawdziwe pozycje bota w tokenach z pełną historią krzywej w strumieniu: cechy w chwili otwarcia pozycji
    (point-in-time), wynik w $ z filtrem i bez, osobno dla strategii."""
    stream, bot = ro(STREAM_DB), ro(BOT_DB)
    mints = {r["mint"]: r for r in stream.execute(
        "SELECT id, mint, created_ts, created_slot, creator, mayhem FROM mints WHERE created_ts IS NOT NULL")}
    pos = [p for p in bot.execute("SELECT mint, strategy, opened_ts, realized_usd - cost_usd pnl FROM positions "
                                  "WHERE status='closed'") if p["mint"] in mints and mints[p["mint"]]["created_ts"] < p["opened_ts"]]
    if not pos:
        print("\n== 5) pozycje bota: brak pozycji w tokenach z pełną historią krzywej ==")
        return
    ids = sorted({mints[p["mint"]]["id"] for p in pos})
    trades: dict[int, list] = {i: [] for i in ids}
    for r in stream.execute(f"SELECT mint_id, slot, ts, wallet_id, buy, sol, tok, vsol, vtok FROM trades "
                            f"WHERE ts < 2000000000 AND mint_id IN ({','.join(map(str, ids))}) ORDER BY slot"):
        trades[r[0]].append(tuple(r[1:]))
    fs = first_seen_map(stream)
    stream_start = stream.execute("SELECT MIN(ts) FROM trades WHERE ts < 2000000000").fetchone()[0]
    gaps = collector.data_holes(stream)          # dziury w czasie bloku (tabela gaps do 5.10 niepełna)
    mig_ts = dict(stream.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind='migrate' GROUP BY mint_id"))
    by_creator: dict[int, list] = {}
    for r in stream.execute("SELECT id, creator, created_ts FROM mints WHERE creator IS NOT NULL AND created_ts IS NOT NULL"):
        by_creator.setdefault(r["creator"], []).append((r["created_ts"], r["id"]))
    res: dict[str, list] = {}
    for p in pos:
        m = mints[p["mint"]]
        t = p["opened_ts"]
        if gap_overlap(gaps, m["created_ts"] - 60, min(t, mig_ts.get(m["id"], t))):
            continue
        meta = {"created_ts": m["created_ts"], "created_slot": m["created_slot"], "creator": m["creator"],
                "mayhem": m["mayhem"], "mig_ts": mig_ts.get(m["id"])}
        prev = [i for ts, i in by_creator.get(m["creator"], []) if ts < m["created_ts"]]
        f = rugguard.curve_features(trades[m["id"]], meta, t, fs,
                                    {"prev_tokens": len(prev), "prev_migrated": sum(1 for i in prev if mig_ts.get(i, 1e18) < t)})
        f["stream_age_h"] = (m["created_ts"] - stream_start) / 3600
        r = {"f": f}
        n_fl = sum(1 for g in good if flagged(r, g) is True)
        res.setdefault(p["strategy"] or "hybrid", []).append((n_fl >= k, p["pnl"]))
    print(f"\n== 5) PRAWDZIWE pozycje bota w tokenach z pełną historią krzywej (filtr: flag >= {k}) ==")
    print(f"  {'strategia':<20}{'n':>4}{'wynik':>10}{'odrzucone':>10}{'ich wynik':>10}{'z filtrem':>11}")
    tot = [0, 0.0, 0, 0.0]
    for s, xs in sorted(res.items()):
        a = sum(v for _, v in xs); d = [v for fl, v in xs if fl]
        print(f"  {s:<20}{len(xs):>4}{a:>+10.2f}{len(d):>10}{sum(d):>+10.2f}{a - sum(d):>+11.2f}")
        tot = [tot[0] + len(xs), tot[1] + a, tot[2] + len(d), tot[3] + sum(d)]
    print(f"  {'RAZEM':<20}{tot[0]:>4}{tot[1]:>+10.2f}{tot[2]:>10}{tot[3]:>+10.2f}{tot[1] - tot[3]:>+11.2f}")
