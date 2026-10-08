"""Ile jego wyboru tłumaczy rynek? Reguła "tłum na starcie" - trafność (precision) i pokrycie (recall) (8.10.2026).

    python -m analizy.cupsey_trigger    # -> analizy/CUPSEY_WYZWALACZ.md

Mianownik: tokeny pump.fun utworzone, gdy Cupsey był "przy komputerze" (+-5 min od dowolnej jego transakcji),
oglądane w wieku A sekund (cechy tylko z transakcji przed tą chwilą). Licznik: tokeny, w które wszedł w ciągu 60 s
od utworzenia. Pokrycie = ile JEGO wczesnych wejść spełniało regułę; trafność = ile tokenów spełniających regułę kupił.
"""
from __future__ import annotations

import bisect
import json
import time

from analizy import common as C
from analizy import cupsey as Q
from analizy import cupsey_signals as S

AGES = (5, 10, 15)
RULES = {
    "portfele >= 8": lambda f: f["portfele_razem"] >= 8,
    "portfele >= 15": lambda f: f["portfele_razem"] >= 15,
    "portfele >= 25": lambda f: f["portfele_razem"] >= 25,
    "portfele >= 15 i kupno 10 s > 3 SOL": lambda f: f["portfele_razem"] >= 15 and f["kupno_sol_10s"] > 3,
    "portfele >= 25 i kupno 10 s > 6 SOL": lambda f: f["portfele_razem"] >= 25 and f["kupno_sol_10s"] > 6,
    "slot startu > 3 SOL i portfele >= 15": lambda f: f["sol_1_slot"] > 3 and f["portfele_razem"] >= 15,
    "portfele >= 40": lambda f: f["portfele_razem"] >= 40,
}


def report() -> str:
    st = C.ro("stream.db")
    eps = Q.episodes()
    ids = {r[1]: r[0] for r in st.execute("SELECT id, mint FROM mints")}
    info = {r[0]: {"created": r[1], "creator": r[2]} for r in st.execute("SELECT id, created_ts, creator FROM mints")}
    me = (st.execute("SELECT id FROM wallets WHERE addr=?", (Q.W,)).fetchone() or [None])[0]
    tx = sorted(r["bt"] for e in eps for r in e["legs"])
    early = {}
    for e in eps:
        mid = ids.get(e["mint"])
        if mid and info[mid]["created"] and e["legs"][0]["venue"] == "pump_curve":
            age = e["legs"][0]["bt"] - info[mid]["created"]
            if 0 <= age <= 60:
                early[mid] = min(early.get(mid, 1e9), age)
    t0, t1 = Q.window()
    online = lambda t: bool(tx) and abs(tx[min(bisect.bisect_left(tx, t), len(tx) - 1)] - t) <= 300 or \
        (bisect.bisect_left(tx, t) > 0 and abs(tx[bisect.bisect_left(tx, t) - 1] - t) <= 300)   # noqa: E731
    pool = [(v["created"], k) for k, v in info.items() if v["created"] and t0 + 60 <= v["created"] <= t1 - 60
            and online(v["created"])]
    hours = len({int(c // 3600) for c, _ in pool})
    rows_all = {A: [] for A in AGES}
    for c, mid in pool:
        tp = S.Tape(st, mid)
        if not tp.slot:
            continue
        for A in AGES:
            f = S.entry_feats(tp, S.cut_at(tp, c + A), c + A, info[mid], set(), me)
            if f:
                bought = mid in early and early[mid] >= A - 2      # wszedł nie wcześniej niż ~ten wiek
                rows_all[A].append((f, mid in early, bought))
    out = [f"# Ile jego wyboru tłumaczy rynek - {time.strftime('%d.%m.%Y %H:%M')}\n",
           f"Tokeny pump.fun utworzone, gdy był aktywny (+-5 min od jego transakcji): {len(pool)} w {hours} godzinach "
           f"aktywności. Wszedł w ciągu 60 s od utworzenia w {len(early)} z nich "
           f"({len(early) / max(len(pool), 1):.2%}, ~{len(early) / max(hours, 1):.1f}/h).\n"]
    for A in AGES:
        rs = rows_all[A]
        his = [x for x in rs if x[1]]
        tab = []
        for name, rule in RULES.items():
            hit = [x for x in rs if rule(x[0])]
            tp_ = sum(1 for x in hit if x[1])
            tab.append([name, len(hit), f"{len(hit) / max(hours, 1):.1f}", tp_,
                        f"{tp_ / max(len(hit), 1):.0%}", f"{sum(1 for x in his if rule(x[0])) / max(len(his), 1):.0%}"])
        out += [f"\n## Wiek {A} s (tokenów z danymi {len(rs)}, w tym jego {len(his)})\n",
                C.table(["reguła", "tokenów spełnia", "na godzinę", "z tego jego", "trafność (kupił)",
                         "pokrycie (jego wejścia spełniały)"], tab)]
    return "\n".join(out)


if __name__ == "__main__" and "--poza" not in __import__("sys").argv:
    txt = report()
    (C.ROOT / "analizy" / "CUPSEY_WYZWALACZ.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)


def beyond_market(A: int = 10, min_wallets: int = 15) -> str:
    """Wśród tokenów spełniających warunek rynkowy (tłum) - czym różnią się te, które kupił, od pozostałych?"""
    import collections
    st = C.ro("stream.db")
    eps = Q.episodes()
    ids = {r[1]: r[0] for r in st.execute("SELECT id, mint FROM mints")}
    mint_of = {v: k for k, v in ids.items()}
    info = {r[0]: {"created": r[1], "creator": r[2]} for r in st.execute("SELECT id, created_ts, creator FROM mints")}
    me = (st.execute("SELECT id FROM wallets WHERE addr=?", (Q.W,)).fetchone() or [None])[0]
    tx = sorted(r["bt"] for e in eps for r in e["legs"])
    his = {ids[e["mint"]] for e in eps if e["mint"] in ids}
    t0, t1 = Q.window()

    def online(t):
        j = bisect.bisect_left(tx, t)
        return any(0 <= i < len(tx) and abs(tx[i] - t) <= 300 for i in (j - 1, j))
    by_creator = collections.defaultdict(list)
    for k, v in info.items():
        if v["created"]:
            by_creator[v["creator"]].append(v["created"])
    migrated = {r[0] for r in st.execute("SELECT DISTINCT mint_id FROM events WHERE kind='migrate'")}
    mig_ts = dict(st.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind='migrate' GROUP BY mint_id").fetchall())
    asset = Q.cache()
    rows = []
    for mid, v in info.items():
        c = v["created"]
        if not c or not (t0 + 60 <= c <= t1 - 60) or not online(c):
            continue
        tp = S.Tape(st, mid)
        if not tp.slot:
            continue
        f = S.entry_feats(tp, S.cut_at(tp, c + A), c + A, v, set(), me)
        if not f or f["portfele_razem"] < min_wallets:
            continue
        prev = [x for x in by_creator[v["creator"]] if x < c]
        prev_m = [k for k, w in info.items() if w["creator"] == v["creator"] and w["created"] and w["created"] < c
                  and k in migrated and mig_ts[k] < c] if prev else []
        a = asset.execute("SELECT image, name, symbol FROM asset WHERE mint=?", (mint_of[mid],)).fetchone()
        rows.append({"his": mid in his, "src": S.host_cat(a[0] if a else None), "prev": len(prev),
                     "prev_mig": len(prev_m), "name_len": len((a[1] if a else "") or ""),
                     "sym_upper": 1.0 if a and a[2] and a[2].isupper() else 0.0, "f": f})
    yes = [r for r in rows if r["his"]]
    no = [r for r in rows if not r["his"]]
    out = [f"\n## Poza rynkiem: tokeny z tłumem (portfele >= {min_wallets} w wieku {A} s) - kupione przez niego vs pominięte\n",
           f"Kupione {len(yes)}, pominięte {len(no)}.\n"]
    srcs = sorted({r["src"] for r in rows})
    out.append(C.table(["źródło grafiki (narzędzie startu)", "kupione", "pominięte"],
                       [[s, f"{sum(r['src'] == s for r in yes) / max(len(yes), 1):.0%}",
                         f"{sum(r['src'] == s for r in no) / max(len(no), 1):.0%}"] for s in srcs]))
    feats = [("twórca: wcześniejsze starty", lambda r: r["prev"]),
             ("twórca: wcześniejsze zmigrowane", lambda r: r["prev_mig"]),
             ("długość nazwy", lambda r: r["name_len"]),
             ("portfele w wieku A", lambda r: r["f"]["portfele_razem"]),
             ("kupno SOL 10 s", lambda r: r["f"]["kupno_sol_10s"]),
             ("SOL w slocie startu", lambda r: r["f"]["sol_1_slot"]),
             ("twórca kupił SOL", lambda r: r["f"]["tworca_kupil_sol"]),
             ("zmiana ceny od startu", lambda r: r["f"]["zmiana_300s"])]
    out.append("\n" + C.table(["cecha", "kupione (mediana)", "pominięte (mediana)", "AUC"],
                              [[n, f"{C.median([g(r) for r in yes]):.3g}", f"{C.median([g(r) for r in no]):.3g}",
                                f"{C.auc([g(r) for r in yes], [g(r) for r in no]):.2f}"] for n, g in feats]))
    return "\n".join(out)


if __name__ == "__main__" and "--poza" in __import__("sys").argv:
    txt = beyond_market()
    with open(C.ROOT / "analizy" / "CUPSEY_WYZWALACZ.md", "a", encoding="utf-8") as fh:
        fh.write(txt + "\n")
    print(txt)
