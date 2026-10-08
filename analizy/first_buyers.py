"""1. FIRST BUYERS - segmentacja pierwszych kupujących, predykcja wyniku tokena, scoring (regresja logistyczna).

    python -m analizy.first_buyers fetch      # brakujące portfele -> Helius (źródło zasilenia, wiek, liczba transakcji)
    python -m analizy.first_buyers report     # grupy, predykcja, połączenie z filtrami bota, scoring
    (klasteryzacja: analizy/first_buyers_cluster.py w środowisku z numpy/scikit-learn)

Punkt decyzji t = migracja + 30 min (bot nie kupuje tokenów młodszych niż 15 min). Definicje grup i cech: firstbuyers.py
(ta sama logika co w logowaniu na żywo, fb_logger.py). Etykieta: potrójna bariera +50% / -70% w 6 h.
Scoring (punkt 4 użytkownika): regresja logistyczna na 4 cechach (udział insiderów, udział ze wspólnym zasilającym,
udział młodych insiderów ze zrzutem, udział snajperów), cel = rug; trenowana WYŁĄCZNIE na eksploracji; próg filtra =
mediana score na eksploracji (połowa tokenów); TEST liczony raz. Model -> analizy/fb_score_model.json (dla loggera).
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import time

import firstbuyers as F
from analizy import common as C

MODEL_PATH = C.ROOT / "analizy" / "fb_score_model.json"


def curve_trades(entries: list[dict]) -> dict[int, list]:
    import rug_dataset as rd
    stream = rd.ro(rd.STREAM_DB)
    ids = [e["mint_id"] for e in entries]
    out: dict[int, list] = {i: [] for i in ids}
    q = (f"SELECT mint_id, slot, ts, wallet_id, buy, sol, tok FROM trades WHERE ts < 2000000000 AND mint_id IN "
         f"({','.join(map(str, ids))}) ORDER BY slot")
    for r in stream.execute(q):
        out[r[0]].append(tuple(r[1:]))
    return out


def setup(pending: bool = False):
    import rug_dataset as rd
    if pending:                       # migracje bez świec (pobierają się) - chwila decyzji znana bez nich
        from analizy.bundles import pending_migrations
        entries = sorted(pending_migrations(), key=lambda e: e["ts"])
    else:
        entries = C.migration_entries(30)
    explore, _ = C.split_time(entries)
    trades = curve_trades(entries)
    rt = F.routers(trades, {e["mint_id"] for e in explore})
    fb = {e["mint_id"]: F.first_buyers([x for x in trades[e["mint_id"]] if x[1] <= e["ts"]], rt) for e in entries}
    stream = rd.ro(rd.STREAM_DB)
    need = {w for ws in fb.values() for w in ws} | {e["creator"] for e in entries if e["creator"] is not None}
    addr = {}
    lst = list(need)
    for i in range(0, len(lst), 900):
        ch = lst[i:i + 900]
        addr.update(dict(stream.execute(f"SELECT id, addr FROM wallets WHERE id IN ({','.join(map(str, ch))})")))
    return entries, explore, trades, rt, fb, addr


def fetch(rps: float, pending: bool = False):
    import rug_funding as rf
    entries, explore, trades, rt, fb, addr = setup(pending)
    db = rf.wallet_db()
    have = {r[0] for r in db.execute("SELECT wallet FROM wallet_funding WHERE status != 'blad'")}
    todo = sorted({addr[w] for ws in fb.values() for w in ws if addr.get(w) not in have} |
                  {addr[e["creator"]] for e in entries if e["creator"] in addr and addr[e["creator"]] not in have})
    print(f"wejść {len(entries)}, routerów {len(rt)}, do sprawdzenia {len(todo)} portfeli", flush=True)
    h = rf.Helius(rps)
    for i, w in enumerate(todo, 1):
        r = rf.resolve(h, w)
        db.execute("INSERT OR REPLACE INTO wallet_funding VALUES(?,?,?,?,?,?)",
                   (w, r["status"], r.get("funder"), r.get("first_ts"), r.get("sig_times"), time.time()))
        db.commit()       # od razu: rug_data.db piszą też inne procesy (świece) - długa transakcja je blokowała
        if i % 200 == 0:
            print(f"{time.strftime('%H:%M:%S')} {i}/{len(todo)} kredytów {h.calls}", flush=True)
    db.commit()
    print(f"koniec, kredytów {h.calls}")


def wallet_history(wallet_ids: set) -> dict[int, list]:
    import rug_dataset as rd
    stream = rd.ro(rd.STREAM_DB)
    out: dict[int, list] = collections.defaultdict(list)
    lst = list(wallet_ids)
    for i in range(0, len(lst), 400):
        ch = lst[i:i + 400]
        q = (f"SELECT wallet_id, MIN(CASE WHEN buy=1 THEN ts END), MIN(CASE WHEN buy=0 THEN ts END), MAX(ts), "
             f"SUM(CASE WHEN buy=1 THEN sol ELSE 0 END), SUM(CASE WHEN buy=0 THEN sol ELSE 0 END) FROM trades "
             f"WHERE ts < 2000000000 AND wallet_id IN ({','.join(map(str, ch))}) GROUP BY wallet_id, mint_id")
        for w, a, b, c, d, e in stream.execute(q):
            out[w].append((a, b, c, d or 0, e or 0))
    return out


def hubs_from(explore, fb, addr, info) -> set:
    cnt = collections.defaultdict(set)
    for e in explore:
        for w in fb[e["mint_id"]]:
            f = (info.get(addr.get(w)) or {}).get("funder")
            if f:
                cnt[f].add(w)
    return {f for f, s in cnt.items() if len(s) >= F.HUB_MIN}


def build():
    """Wejścia z cechami składu pierwszych kupujących + wiersze portfeli (wspólne dla raportu i klasteryzacji)."""
    import rug_funding as rf
    entries, explore, trades, rt, fb, addr = setup()
    info = {r["wallet"]: dict(r) for r in rf.wallet_db().execute("SELECT * FROM wallet_funding")}
    hubs = hubs_from(explore, fb, addr, info)
    hist = wallet_history({w for ws in fb.values() for w in ws})
    ex_ids = {e["mint_id"] for e in explore}
    rows = []
    for e in entries:
        tr = trades[e["mint_id"]]
        wr = F.token_rows(tr, e["created_slot"], e["creator"], e["ts"], rt, addr.get, info, hist, hubs)
        for r in wr:
            r.update(mint=e["mint"], ts=e["ts"])
        rows += wr
        e.update(F.composition(wr))
        e["sim"] = C.sim(e["path"], e["ref"], e["path"][0][0])
        e["explore"] = e["mint_id"] in ex_ids
    ents = [e for e in entries if e.get("n_first")]
    return ents, rows, rt, hubs


# ------------------------------------------------------------------ regresja logistyczna (czysty Python)
def fit_logreg(X: list[list[float]], y: list[int], l2: float = 0.01, lr: float = 0.2, iters: int = 3000):
    n, k = len(X), len(X[0])
    w, b = [0.0] * k, 0.0
    for _ in range(iters):
        gw, gb = [0.0] * k, 0.0
        for xi, yi in zip(X, y):
            p = 1 / (1 + math.exp(-(b + sum(a * c for a, c in zip(w, xi)))))
            d = p - yi
            gb += d
            for j in range(k):
                gw[j] += d * xi[j]
        b -= lr * gb / n
        w = [wj - lr * (gj / n + l2 * wj) for wj, gj in zip(w, gw)]
    return w, b


def scoring_section(ents: list[dict]) -> str:
    ex = [e for e in ents if e["explore"]]
    te = [e for e in ents if not e["explore"]]
    feats = list(F.SCORE_FEATS)
    mean = {f: sum(e[f] for e in ex) / len(ex) for f in feats}
    std = {f: (sum((e[f] - mean[f]) ** 2 for e in ex) / len(ex)) ** 0.5 or 1.0 for f in feats}
    z = lambda e: [(e[f] - mean[f]) / std[f] for f in feats]
    out = ["\n### 1c. Scoring wejścia - regresja logistyczna (4 cechy, cel = rug, trening tylko na eksploracji)\n"]
    models = {}
    for target in ("rug", "pump"):
        w, b = fit_logreg([z(e) for e in ex], [int(e["label"] == target) for e in ex])
        model = {"target": target, "intercept": b, "coef": dict(zip(feats, w)), "mean": mean, "std": std,
                 "trained_on": f"{len(ex)} tokenów eksploracji (migracja + 30 min), {time.strftime('%d.%m.%Y')}"}
        models[target] = model
        for e in ents:
            e[f"score_{target}"] = F.score(e, model)
        a_ex = C.auc([e[f"score_{target}"] for e in ex if e["label"] == target], [e[f"score_{target}"] for e in ex if e["label"] != target])
        a_te = C.auc([e[f"score_{target}"] for e in te if e["label"] == target], [e[f"score_{target}"] for e in te if e["label"] != target])
        out.append(f"- model `{target}`: współczynniki (cechy standaryzowane) " +
                   ", ".join(f"{f} {model['coef'][f]:+.2f}" for f in feats) +
                   f", wyraz wolny {b:+.2f}; **AUC eksploracja {a_ex:.3f}, TEST {a_te:.3f}** (N test {len(te)}{C.rel(len(te))})")
    # model loggera na żywo (fb_logger.py) zostaje ZAMROŻONY z 6.10 - ponowny przebieg raportu zapisuje obok, żeby
    # ocena na żywo dotyczyła jednego modelu (7.10: próbny run_all nadpisał go modelem z innych danych)
    (MODEL_PATH if not MODEL_PATH.exists() else MODEL_PATH.with_name("fb_score_model_latest.json")).write_text(
        json.dumps(models["rug"], indent=1), encoding="utf-8")
    thr = sorted(e["score_rug"] for e in ex)[len(ex) // 2]
    C.filter_eval("scoring P(rug) z części 1c: wchodź, gdy score < mediana eksploracji", ents,
                  lambda e: e["score_rug"] < thr, "sim")
    rows = []
    for lbl, s in (("eksploracja", ex), ("TEST", te)):
        keep = [e for e in s if e["score_rug"] < thr]
        drop = [e for e in s if e["score_rug"] >= thr]
        rows.append([lbl, f"{len(s)}", C.pct(C.mean([e['sim'] for e in s])), f"{len(keep)}{C.rel(len(keep))}",
                     C.pct(C.mean([e['sim'] for e in keep])), f"{sum(e['sim'] for e in keep) * 50:+.0f}",
                     f"{sum(e['sim'] for e in s) * 50:+.0f}", f"{len(drop)}", C.pct(C.mean([e['sim'] for e in drop])),
                     f"{C.mean([e['label'] == 'rug' for e in keep]):.0%} / {C.mean([e['label'] == 'rug' for e in drop]):.0%}"])
    out.append(f"\nFiltr: wchodź tylko, gdy score_rug < {thr:.3f} (mediana eksploracji). Wynik w $ przy stawce $50:\n")
    out.append(C.table(["zbiór", "N baseline", "baseline śr.", "N wpuszczonych", "wpuszczone śr.", "$ wpuszczone",
                        "$ baseline (wszystkie)", "N odrzuconych", "odrzucone śr.", "rug wpuszczone / odrzucone"], rows))
    return "\n".join(out)


def bot_verdicts(mints: list[str]) -> dict[str, str]:
    db = C.ro("bot.db")
    out = {}
    for m in mints:
        ds = {r[0] for r in db.execute("SELECT decision FROM decisions WHERE mint=?", (m,))}
        out[m] = "BUY/WATCH" if ds & {"BUY", "WATCH"} else ("REJECT/SKIP" if ds else "nieoceniony")
    return out


FEATS = ["frac_insider", "frac_sniper", "frac_smart", "frac_retail", "vol_insider", "vol_sniper", "vol_smart",
         "vol_retail", "age_med_h", "frac_young", "frac_sold5m", "frac_same_slot", "frac_shared_funder", "frac_active",
         "young_insider_dump"]


def report() -> str:
    ents, rows, rt, hubs = build()
    ex = [e for e in ents if e["explore"]]
    te = [e for e in ents if not e["explore"]]
    lab = {e["mint"]: e for e in ents}
    with open(C.ROOT / "analizy" / "first_buyers_wallets.csv", "w", newline="", encoding="utf-8") as fh:
        keys = list(rows[0].keys()) + ["split", "label", "sim"]
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            if r["mint"] in lab:
                e = lab[r["mint"]]
                w.writerow({**r, "label": e["label"], "sim": e["sim"], "split": "explore" if e["explore"] else "test"})
    out = ["## 1. First buyers - segmentacja\n",
           f"Punkt decyzji: migracja + 30 min, token żyje. Tokenów: **{len(ents)}** (eksploracja {len(ex)}, TEST {len(te)}); "
           f"pierwszych kupujących (portfel x token): {len(rows)}; routerów wykluczonych: {len(rt)}; hubów: {len(hubs)}. "
           f"Definicje grup: firstbuyers.py (smart money od 6.10: >= 5 zamkniętych pozycji, >= 55% wygranych, mediana "
           f"trzymania > 30 min, nie sprzedał w 5 min).\n"]
    gc = collections.Counter(r["group"] for r in rows)
    out.append(C.table(["grupa", "N portfeli", "udział", "mediana wieku portfela (h)", "sprzedał w 5 min", "śr. zakup SOL"],
                       [[g, gc[g], f"{gc[g] / len(rows):.0%}", f"{C.median([r['age_h'] for r in rows if r['group'] == g]):.0f}",
                         f"{C.mean([r['sold_5m'] for r in rows if r['group'] == g]):.0%}",
                         f"{C.mean([r['buy_sol'] for r in rows if r['group'] == g]):.2f}"] for g in F.GROUPS]))
    c1 = [r for r in rows if (r["prior_n_closed"] or 0) >= 5]
    c2 = [r for r in c1 if (r["prior_win_rate"] or 0) >= 0.55]
    c3 = [r for r in c2 if (r["prior_hold_med_s"] or 0) > F.SMART_HOLD_S]
    c4 = [r for r in c3 if not r["sold_5m"]]
    holds = sorted(r["prior_hold_med_s"] for r in c1 if r["prior_hold_med_s"] is not None)
    out.append(f"\n**Smart money wg nowej definicji - ile portfeli przechodzi kolejne warunki:** >= 5 zamkniętych pozycji "
               f"przed t: {len(c1)} -> >= 55% wygranych: {len(c2)} -> mediana trzymania > 30 min: {len(c3)} -> nie sprzedał "
               f"w 5 min: **{len(c4)}**. Mediana trzymania (portfele z historią): "
               f"{(holds[len(holds) // 2] / 60 if holds else float('nan')):.1f} min; > 30 min ma "
               f"{sum(h > F.SMART_HOLD_S for h in holds) / max(len(holds), 1):.0%} z nich - pierwsi kupujący na pump.fun "
               f"prawie nie trzymają długo, więc grupa jest pusta (wynik, nie błąd).\n")
    out.append("\n**Baseline (wejście w każdy żywy token, wyjścia bota):**\n")
    out.append(C.table(["zbiór", "N", "rug", "pump", "nic", "śr. wynik wejścia"],
                       [[k, len(s), f"{C.mean([e['label'] == 'rug' for e in s]):.0%}", f"{C.mean([e['label'] == 'pump' for e in s]):.0%}",
                         f"{C.mean([e['label'] == 'nic' for e in s]):.0%}", C.pct(C.mean([e['sim'] for e in s]))]
                        for k, s in (("eksploracja", ex), ("TEST", te))]))
    out.append("\n**Dominująca grupa wśród pierwszych kupujących -> wynik tokena:**\n")
    rt_ = []
    for g in F.GROUPS:
        for lbl, s in (("eksploracja", ex), ("TEST", te)):
            ss = [e for e in s if e["dominant"] == g]
            if ss:
                rt_.append([g, lbl, f"{len(ss)}{C.rel(len(ss))}", f"{C.mean([e['label'] == 'rug' for e in ss]):.0%}",
                            f"{C.mean([e['label'] == 'pump' for e in ss]):.0%}", C.pct(C.mean([e['sim'] for e in ss]))])
    out.append(C.table(["dominuje", "zbiór", "N", "rug", "pump", "śr. wynik"], rt_))
    out.append("\n**Pojedyncze cechy składu (AUC; kierunek ustalony na eksploracji):**\n")
    rf_ = []
    for f in FEATS:
        for target in ("rug", "pump"):
            a_ex = C.auc([e[f] for e in ex if e["label"] == target and e.get(f) is not None],
                         [e[f] for e in ex if e["label"] != target and e.get(f) is not None])
            a_te = C.auc([e[f] for e in te if e["label"] == target and e.get(f) is not None],
                         [e[f] for e in te if e["label"] != target and e.get(f) is not None])
            flip = a_ex < 0.5
            a_te2 = 1 - a_te if flip else a_te
            ok = abs(a_ex - 0.5) >= 0.05 and a_te2 >= 0.55
            rf_.append([f, target, f"{max(a_ex, 1 - a_ex):.3f}", f"{a_te2:.3f}", "potwierdzone" if ok else "—"])
    out.append(C.table(["cecha", "cel", "AUC eksploracja", "AUC TEST (ten sam kierunek)", "trzyma się?"], rf_))
    # filtr "przewaga snajperów" (zdefiniowany 6.10 na eksploracji, teraz z nową definicją smart)
    rr = []
    for lbl, s in (("eksploracja", ex), ("TEST", te)):
        keep = [e for e in s if e["frac_sniper"] >= 0.5]
        rr.append([lbl, f"{len(s)}", C.pct(C.mean([e['sim'] for e in s])), f"{len(keep)}{C.rel(len(keep))}",
                   C.pct(C.mean([e['sim'] for e in keep])), f"{C.mean([e['label'] == 'rug' for e in keep]):.0%}"])
    C.filter_eval("pierwsi kupujący (część 1): wchodź, gdy snajperów >= 50%", ents, lambda e: e["frac_sniper"] >= 0.5, "sim")
    out.append("\n**Filtr \"wchodź, gdy snajperów >= 50% pierwszych kupujących\"** (reguła z 6.10, po zmianie definicji smart):\n")
    out.append(C.table(["zbiór", "N baseline", "baseline", "N po filtrze", "po filtrze", "rug po filtrze"], rr))
    vd = bot_verdicts([e["mint"] for e in ents])
    out.append("\n**Połączenie z filtrami bota (werdykt bota: BUY/WATCH = przeszedł filtry):**\n")
    rc = []
    for lbl, s in (("eksploracja", ex), ("TEST", te)):
        for v in ("BUY/WATCH", "REJECT/SKIP", "nieoceniony"):
            ss = [e for e in s if vd[e["mint"]] == v]
            if ss:
                rc.append([lbl, v, f"{len(ss)}{C.rel(len(ss))}", f"{C.mean([e['label'] == 'rug' for e in ss]):.0%}",
                           C.pct(C.mean([e['sim'] for e in ss]))])
                if v == "BUY/WATCH":
                    k2 = [e for e in ss if e["frac_sniper"] >= 0.5]
                    rc.append([lbl, v + " + snajperzy >= 50%", f"{len(k2)}{C.rel(len(k2))}",
                               f"{C.mean([e['label'] == 'rug' for e in k2]):.0%}", C.pct(C.mean([e['sim'] for e in k2]))])
    out.append(C.table(["zbiór", "grupa", "N", "rug", "śr. wynik"], rc))
    out.append(scoring_section(ents))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "report"])
    ap.add_argument("--rps", type=float, default=8)
    ap.add_argument("--pending", action="store_true")
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.rps, a.pending)
    else:
        print(report())


if __name__ == "__main__":
    main()
