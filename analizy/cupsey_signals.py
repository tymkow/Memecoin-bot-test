"""Na jakie sygnały wchodzi i wychodzi Cupsey? (8.10.2026)

    <mlenv>/python -m analizy.cupsey_signals      # -> analizy/CUPSEY_SYGNALY.md (sklearn do drzewa decyzyjnego)

Jego transakcje: analizy/cupsey.py (historia jego kont tokenów, Helius). Rynek: nasz strumień pump.fun (stream.db -
każda transakcja na krzywej z rezerwami po niej), więc analizujemy wejścia NA KRZYWEJ (PumpSwap mamy tylko w oknach
+-15/25 s wokół jego transakcji). Cechy liczone wyłącznie z transakcji w slotach PRZED jego transakcją.

WEJŚCIA - dwie grupy kontrolne:
  * "kiedy" (ten sam token): losowe chwile życia tego samego tokena (transakcje innych), poza jego pozycjami +-60 s;
  * "który" (ta sama chwila): inne tokeny pump.fun z handlem w ostatnich 30 s przed jego wejściem, których nie ruszał.
  Dla cechy: mediana u niego vs w kontroli i AUC (0.5 = brak różnicy; > 0.5 = u niego wyżej). Stabilność: AUC osobno
  na pierwszych 70% i ostatnich 30% czasu; drzewo decyzyjne (głębokość 3) uczone na 70%, AUC na 30%.
WYJŚCIA: chwila każdej jego sprzedaży na krzywej vs losowe chwile w trakcie trzymania (transakcje innych, poza +-5 s
  od jego sprzedaży). Do tego rozkład wyniku i czasu przy pierwszej sprzedaży (stałe progi TP/SL?).
X / social: nie mamy osi czasu tweetów; jedyny ślad to źródło grafiki tokena (narzędzia do odpalania coinów z tweeta:
  j7tracker, uxento, obrazek prosto z pbs.twimg.com) - porównanie jego tokenów z kontrolą z tej samej chwili.
"""
from __future__ import annotations

import bisect
import collections
import json
import random
import time
import urllib.parse

from analizy import common as C
from analizy import cupsey as Q

RNG = random.Random(20261008)
N_CTRL = 5
SUPPLY = 1e15                 # podaż pump.fun w jednostkach surowych (1 mld tokenów x 1e6)
X_HOSTS = ("metadata.j7tracker.io", "edge.uxento.io", "pbs.twimg.com")


class Tape:
    """Transakcje krzywej jednego tokena (rosnąco po slocie): slot, ts, wallet, buy, sol (SOL), tok, price."""

    def __init__(self, st, mint_id: int):
        rows = st.execute("SELECT slot, ts, wallet_id, buy, sol, tok, vsol, vtok FROM trades WHERE mint_id=? "
                          "ORDER BY slot", (mint_id,)).fetchall()
        self.slot = [r[0] for r in rows]
        self.ts = [r[1] for r in rows]
        self.w = [r[2] for r in rows]
        self.buy = [r[3] for r in rows]
        self.sol = [r[4] / 1e9 for r in rows]
        self.tok = [float(r[5]) for r in rows]
        self.px = [float(r[6]) / float(r[7]) if r[7] else None for r in rows]


def price_at_ts(tp: Tape, k_end: int, t: float):
    """Cena po ostatniej transakcji z ts <= t spośród pierwszych k_end."""
    j = bisect.bisect_right(tp.ts, t, 0, k_end)
    return tp.px[j - 1] if j > 0 else None


def entry_feats(tp: Tape, slot: int, T: float, info: dict, kol: set, me: int) -> dict | None:
    k = bisect.bisect_left(tp.slot, slot)          # transakcje w slotach < slot
    if k == 0 or tp.px[k - 1] is None:
        return None
    p = tp.px[k - 1]
    f = {"wiek_min": (T - info["created"]) / 60 if info["created"] else None,
         "krzywa_sol": None}
    f["krzywa_sol"] = None
    hist = [x for x in tp.px[:k] if x]
    f["od_szczytu"] = p / max(hist) - 1
    f["nowy_szczyt"] = 1.0 if p >= max(hist) * 0.98 else 0.0
    for s in (10, 30, 60, 300):
        p0 = price_at_ts(tp, k, T - s)
        f[f"zmiana_{s}s"] = p / p0 - 1 if p0 else None
    for s in (10, 60):
        a = bisect.bisect_left(tp.ts, T - s, 0, k)
        idx = range(a, k)
        f[f"kupna_{s}s"] = sum(tp.buy[i] for i in idx)
        f[f"sprzedaze_{s}s"] = sum(1 - tp.buy[i] for i in idx)
        f[f"kupujacy_{s}s"] = len({tp.w[i] for i in idx if tp.buy[i]})
        f[f"kupno_sol_{s}s"] = sum(tp.sol[i] for i in idx if tp.buy[i])
        f[f"netto_sol_{s}s"] = sum(tp.sol[i] * (1 if tp.buy[i] else -1) for i in idx)
        f[f"max_kupno_{s}s"] = max([tp.sol[i] for i in idx if tp.buy[i]] or [0.0])
        f[f"kol_kupna_{s}s"] = sum(1 for i in idx if tp.buy[i] and tp.w[i] in kol and tp.w[i] != me)
    a = bisect.bisect_left(tp.ts, T - 300, 0, k)
    f["kol_kupna_300s"] = sum(1 for i in range(a, k) if tp.buy[i] and tp.w[i] in kol and tp.w[i] != me)
    f["portfele_razem"] = len({tp.w[i] for i in range(k) if tp.buy[i]})
    f["transakcje_razem"] = k
    f["przyspieszenie"] = f["kupna_10s"] / (f["kupna_60s"] / 6) if f["kupna_60s"] else None
    cr = info["creator"]
    held = sum(tp.tok[i] * (1 if tp.buy[i] else -1) for i in range(k) if tp.w[i] == cr)
    f["tworca_sprzedal"] = 1.0 if any(tp.w[i] == cr and not tp.buy[i] for i in range(k)) else 0.0
    f["tworca_ma_pct"] = max(held, 0) / SUPPLY * 100
    f["cisza_s"] = T - tp.ts[k - 1]
    f["tworca_kupil_sol"] = sum(tp.sol[i] for i in range(k) if tp.w[i] == cr and tp.buy[i])
    s0 = tp.slot[0]
    f["kupujacy_1_slot"] = len({tp.w[i] for i in range(k) if tp.slot[i] == s0 and tp.buy[i]})
    f["sol_1_slot"] = sum(tp.sol[i] for i in range(k) if tp.slot[i] == s0 and tp.buy[i])
    return f


def cut_at(tp: Tape, t: float) -> int:
    """Slot-odcięcie dla chwili t (pierwsza transakcja z ts >= t; po końcu zapisu - za ostatnią)."""
    j = bisect.bisect_left(tp.ts, t)
    return tp.slot[j] if j < len(tp.slot) else tp.slot[-1] + 1


def exit_feats(tp: Tape, slot: int, T: float, p_entry: float, t_entry: float, info: dict, kol: set, me: int):
    k = bisect.bisect_left(tp.slot, slot)
    if k == 0 or not tp.px[k - 1] or not p_entry:
        return None
    p = tp.px[k - 1]
    e = bisect.bisect_left(tp.ts, t_entry, 0, k)
    peak = max([x for x in tp.px[e:k] if x] or [p])
    f = {"wynik_od_wejscia": p / p_entry - 1, "od_szczytu_pozycji": p / peak - 1, "trzyma_s": T - t_entry}
    for s in (5, 10, 30):
        p0 = price_at_ts(tp, k, T - s)
        f[f"zmiana_{s}s"] = p / p0 - 1 if p0 else None
    a = bisect.bisect_left(tp.ts, T - 10, 0, k)
    idx = [i for i in range(a, k) if tp.w[i] != me]
    f["sprzedaze_10s"] = sum(1 - tp.buy[i] for i in idx)
    f["kupna_10s"] = sum(tp.buy[i] for i in idx)
    f["sprzedaz_sol_10s"] = sum(tp.sol[i] for i in idx if not tp.buy[i])
    f["max_sprzedaz_10s"] = max([tp.sol[i] for i in idx if not tp.buy[i]] or [0.0])
    f["netto_sol_10s"] = sum(tp.sol[i] * (1 if tp.buy[i] else -1) for i in idx)
    a60 = bisect.bisect_left(tp.ts, T - 60, 0, k)
    f["kol_sprzedaze_60s"] = sum(1 for i in range(a60, k) if not tp.buy[i] and tp.w[i] in kol and tp.w[i] != me)
    f["tworca_sprzedal_w_trakcie"] = 1.0 if any(tp.w[i] == info["creator"] and not tp.buy[i] for i in range(e, k)) else 0.0
    return f


def auc_row(name, a, b):
    xa = [x for x in a if x is not None]
    xb = [x for x in b if x is not None]
    return C.auc(xa, xb) if xa and xb else float("nan")


def feat_table(groups: dict, names: list, ref: str, split_t: float) -> tuple[str, list]:
    """Tabela: mediana w każdej grupie + AUC (ref vs kontrola) na całości, eksploracji i teście."""
    out, ranked = [], []
    ctrls = [g for g in groups if g != ref]
    head = ["cecha", f"{ref} (mediana)"] + [f"{g} (mediana)" for g in ctrls]
    for g in ctrls:
        head += [f"AUC vs {g}", "AUC 70% / 30%"]
    rows = []
    for n in names:
        r = [n, f"{C.median([f[n] for f, _ in groups[ref]]):.3g}"]
        r += [f"{C.median([f[n] for f, _ in groups[g]]):.3g}" for g in ctrls]
        for g in ctrls:
            a = [f[n] for f, t in groups[ref]]
            b = [f[n] for f, t in groups[g]]
            ea = [f[n] for f, t in groups[ref] if t < split_t]
            eb = [f[n] for f, t in groups[g] if t < split_t]
            ta = [f[n] for f, t in groups[ref] if t >= split_t]
            tb = [f[n] for f, t in groups[g] if t >= split_t]
            A, Ae, At = auc_row(n, a, b), auc_row(n, ea, eb), auc_row(n, ta, tb)
            r += [f"{A:.2f}", f"{Ae:.2f} / {At:.2f}"]
            ranked.append((abs(A - 0.5), n, g, A, Ae, At))
        rows.append(r)
    out.append(C.table(head, rows))
    return "\n".join(out), ranked


def tree_eval(pos: list, neg: list, names: list, split_t: float, label: str) -> str:
    try:
        import numpy as np
        from sklearn.metrics import roc_auc_score
        from sklearn.tree import DecisionTreeClassifier, export_text
    except ImportError:
        return f"\n({label}: brak sklearn - uruchom pod scratchpad/mlenv)\n"

    def mat(gs):
        return np.array([[(f[n] if f[n] is not None else np.nan) for n in names] for f, _ in gs], dtype=float)

    tr = [(x, 1) for x in pos if x[1] < split_t] + [(x, 0) for x in neg if x[1] < split_t]
    te = [(x, 1) for x in pos if x[1] >= split_t] + [(x, 0) for x in neg if x[1] >= split_t]
    Xtr, ytr = mat([x for x, _ in tr]), np.array([y for _, y in tr])
    Xte, yte = mat([x for x, _ in te]), np.array([y for _, y in te])
    med = np.nanmedian(Xtr, axis=0)
    Xtr = np.where(np.isnan(Xtr), med, Xtr)
    Xte = np.where(np.isnan(Xte), med, Xte)
    m = DecisionTreeClassifier(max_depth=3, min_samples_leaf=15, class_weight="balanced", random_state=1).fit(Xtr, ytr)
    a_tr = roc_auc_score(ytr, m.predict_proba(Xtr)[:, 1])
    a_te = roc_auc_score(yte, m.predict_proba(Xte)[:, 1]) if len(set(yte)) > 1 else float("nan")
    return (f"\n**Drzewo decyzyjne ({label})**, głębokość 3, uczone na 70% czasu (N {len(tr)}), test na 30% (N {len(te)}): "
            f"AUC eksploracja {a_tr:.2f}, **test {a_te:.2f}**.\n\n```\n{export_text(m, feature_names=names)}```\n")


def host_cat(url: str | None) -> str:
    h = urllib.parse.urlparse(url or "").netloc
    if h in X_HOSTS:
        return "z X (tweet -> coin)"
    if "axiom" in h:
        return "Axiom"
    if h in ("ipfs.io", "pump.mypinata.cloud"):
        return "pump.fun (strona)"
    return "inne" if h else "brak"


def report(name: str = "Cupsey", wallet: str = Q.W, eps: list | None = None) -> str:
    st = C.ro("stream.db")
    ids = {r[1]: r[0] for r in st.execute("SELECT id, mint FROM mints")}
    info = {r[0]: {"created": r[1], "creator": r[2]} for r in st.execute("SELECT id, created_ts, creator FROM mints")}
    me = (st.execute("SELECT id FROM wallets WHERE addr=?", (wallet,)).fetchone() or [None])[0]
    wl = json.loads((C.DATA / "madeonsol" / "wallets.json").read_text(encoding="utf-8"))["data"]
    wl = wl if isinstance(wl, list) else (wl.get("wallets") or wl.get("data") or [])
    addrs = [x.get("wallet_address") for x in wl]
    kol = {r[0] for r in st.execute(f"SELECT id FROM wallets WHERE addr IN ({','.join('?' * len(addrs))})", addrs)}
    eps = eps if eps is not None else Q.episodes()
    his_mints = {e["mint"] for e in eps}
    tapes = {}

    def tape(mid):
        if mid not in tapes:
            tapes[mid] = Tape(st, mid)
        return tapes[mid]

    t0, t1 = Q.window()
    ent = [e for e in eps if e["legs"][0]["venue"] == "pump_curve" and e["mint"] in ids]
    ent.sort(key=lambda e: e["t"])
    split_t = ent[int(len(ent) * C.SPLIT)]["t"] if ent else t1
    G = {"on": [], "ten sam token": [], "ta sama chwila": [], "nowe w tym wieku": []}
    hcat = {"on": [], "ta sama chwila": [], "nowe w tym wieku": []}
    created = sorted((v["created"], k) for k, v in info.items() if v["created"])
    cr_ts = [c for c, _ in created]
    asset = Q.cache()
    img = lambda m: (asset.execute("SELECT image FROM asset WHERE mint=?", (m,)).fetchone() or [None])[0]  # noqa: E731
    for e in ent:
        mid = ids[e["mint"]]
        tp = tape(mid)
        leg = e["legs"][0]
        f = entry_feats(tp, leg["slot"], leg["bt"], info[mid], kol, me)
        if not f:
            continue
        G["on"].append((f, leg["bt"]))
        hcat["on"].append(host_cat(img(e["mint"])))
        # kontrola "kiedy": transakcje innych w tym samym tokenie, poza jego pozycjami +-60 s
        busy = [(x["t"] - 60, x["t_end"] + 60) for x in eps if x["mint"] == e["mint"]]
        cand = [i for i in range(1, len(tp.slot)) if not any(a <= tp.ts[i] <= b for a, b in busy) and tp.w[i] != me]
        for i in RNG.sample(cand, min(N_CTRL, len(cand))):
            g = entry_feats(tp, tp.slot[i], tp.ts[i], info[mid], kol, me)
            if g:
                G["ten sam token"].append((g, leg["bt"]))
        # kontrola "który": inne aktywne tokeny w tej samej chwili
        act = [r[0] for r in st.execute("SELECT DISTINCT mint_id FROM trades WHERE ts BETWEEN ? AND ?",
                                        (leg["bt"] - 30, leg["bt"] - 1))]
        mint_of = {v: k for k, v in ids.items()} if not hasattr(report, "_inv") else report._inv
        report._inv = mint_of
        act = [m for m in act if mint_of.get(m) not in his_mints]
        for m in RNG.sample(act, min(N_CTRL, len(act))):
            g = entry_feats(tape(m), leg["slot"], leg["bt"], info[m], kol, me)
            if g:
                G["ta sama chwila"].append((g, leg["bt"]))
                hcat["ta sama chwila"].append(host_cat(img(mint_of[m])))
        # kontrola "nowe w tym wieku": tokeny odpalone +-60 s od jego tokena, oglądane w TYM SAMYM wieku co jego wejście
        c0 = info[mid]["created"]
        if c0:
            age = leg["bt"] - c0
            lo, hi = bisect.bisect_left(cr_ts, c0 - 60), bisect.bisect_right(cr_ts, c0 + 60)
            near = [m for _, m in created[lo:hi] if m != mid and mint_of.get(m) not in his_mints]
            for m in RNG.sample(near, min(2 * N_CTRL, len(near))):
                tpm = tape(m)
                if not tpm.slot:
                    continue
                Tm = info[m]["created"] + age
                g = entry_feats(tpm, cut_at(tpm, Tm), Tm, info[m], kol, me)
                if g:
                    G["nowe w tym wieku"].append((g, leg["bt"]))
                    hcat["nowe w tym wieku"].append(host_cat(img(mint_of[m])))
    names = [n for n in G["on"][0][0] if n != "krzywa_sol"]
    out = [f"# Na jakie sygnały wchodzi i wychodzi {name} - {time.strftime('%d.%m.%Y %H:%M')}\n",
           f"Wejścia na krzywej pump.fun z pełnym zapisem rynku przed nimi: {len(G['on'])} (z {len(eps)} jego pozycji; "
           f"reszta: PumpSwap / inne launchpady / brak w strumieniu). Kontrole: {len(G['ten sam token'])} chwil "
           f"tego samego tokena, {len(G['ta sama chwila'])} innych tokenów w tej samej chwili. Podział czasu: "
           f"{time.strftime('%d.%m %H:%M', time.localtime(split_t))}.\n",
           "## 1. Wejścia - cechy rynku tuż przed jego zakupem\n"]
    txt, ranked = feat_table(G, names, "on", split_t)
    out.append(txt)
    top = sorted([r for r in ranked if r[4] == r[4] and r[5] == r[5]], key=lambda r: -r[0])
    out.append("\n**Najsilniejsze różnice** (|AUC - 0.5|, z kontrolą; kierunek musi się zgadzać w obu połowach czasu):\n")
    rows = []
    for d, n, g, A, Ae, At in [r for r in top if r[1] != "wiek_min" or r[2] != "nowe w tym wieku"][:22]:
        same = (Ae - 0.5) * (At - 0.5) > 0
        rows.append([n, g, f"{A:.2f}", f"{Ae:.2f} / {At:.2f}", "tak" if same else "**NIE**"])
    out.append(C.table(["cecha", "kontrola", "AUC", "70% / 30%", "stabilne"], rows))
    out.append(tree_eval(G["on"], G["nowe w tym wieku"], names, split_t,
                         "który NOWY token: on vs tokeny odpalone w tej samej minucie, w tym samym wieku"))
    out.append(tree_eval(G["on"], G["ta sama chwila"], names, split_t, "który token: on vs inne tokeny w tej chwili"))
    out.append(tree_eval(G["on"], G["ten sam token"], names, split_t, "kiedy: on vs inne chwile tego tokena"))
    # social / X
    ca, cb, cc = (collections.Counter(hcat[g]) for g in ("on", "ta sama chwila", "nowe w tym wieku"))
    na, nb, nc = (max(len(hcat[g]), 1) for g in ("on", "ta sama chwila", "nowe w tym wieku"))
    out += ["\n## 2. Ślad X / social - źródło grafiki tokena (narzędzie, którym go odpalono)\n",
            C.table(["źródło", f"jego tokeny (N {len(hcat['on'])})", f"inne tokeny w tej chwili (N {len(hcat['ta sama chwila'])})",
                     f"nowe w tym wieku (N {len(hcat['nowe w tym wieku'])})"],
                    [[k, f"{ca[k] / na:.0%}", f"{cb[k] / nb:.0%}", f"{cc[k] / nc:.0%}"]
                     for k in sorted(set(ca) | set(cb) | set(cc), key=lambda k: -(ca[k] + cb[k] + cc[k]))])]
    # 3. wyjścia
    X = {"on": [], "w trakcie": []}
    first = []
    for e in ent:
        mid = ids[e["mint"]]
        tp = tape(mid)
        leg = e["legs"][0]
        k = bisect.bisect_left(tp.slot, leg["slot"])
        p_entry = tp.px[k - 1] if k > 0 else None
        sells = [r for r in e["legs"] if r["kind"] == "sell" and r["venue"] == "pump_curve"]
        for j, r in enumerate(sells):
            f = exit_feats(tp, r["slot"], r["bt"], p_entry, leg["bt"], info[mid], kol, me)
            if f:
                X["on"].append((f, r["bt"]))
                if j == 0:
                    first.append((f["wynik_od_wejscia"], f["trzyma_s"], r["frac"]))
        if sells:
            a, b = leg["bt"], sells[-1]["bt"]
            cand = [i for i in range(len(tp.slot)) if a < tp.ts[i] < b and tp.w[i] != me
                    and not any(abs(tp.ts[i] - s["bt"]) <= 5 for s in sells)]
            for i in RNG.sample(cand, min(N_CTRL, len(cand))):
                g = exit_feats(tp, tp.slot[i], tp.ts[i], p_entry, leg["bt"], info[mid], kol, me)
                if g:
                    X["w trakcie"].append((g, tp.ts[i]))
    out.append("\n## 3. Wyjścia - chwila jego sprzedaży vs inne chwile w trakcie trzymania\n")
    if X["on"] and X["w trakcie"]:
        txt, ranked_x = feat_table(X, list(X["on"][0][0]), "on", split_t)
        out.append(txt)
        out.append(tree_eval(X["on"], X["w trakcie"], list(X["on"][0][0]), split_t, "wyjście: jego sprzedaż vs trzymanie"))
    if first:
        rs = sorted(x[0] for x in first)
        hs = sorted(x[1] for x in first)
        q = lambda xs, p: xs[min(int(len(xs) * p), len(xs) - 1)]  # noqa: E731
        bins = collections.Counter(min(max(int((x * 100) // 10) * 10, -50), 100) for x in rs)
        out += [f"\n**Pierwsza sprzedaż** (N {len(first)}): wynik od wejścia (cena) kwartyle "
                f"{', '.join(C.pct(q(rs, p)) for p in (0.1, 0.25, 0.5, 0.75, 0.9))}; czas trzymania kwartyle "
                f"{', '.join(f'{q(hs, p):.0f} s' for p in (0.1, 0.25, 0.5, 0.75, 0.9))}; sprzedana część mediana "
                f"{C.median([x[2] for x in first]):.0%}.\n",
                "Rozkład wyniku przy pierwszej sprzedaży (przedziały po 10 pp; skupienie = stały próg TP/SL):\n",
                C.table(["przedział", "N", ""], [[f"{k:+d}..{k + 10:+d}%", bins[k], "#" * bins[k]] for k in sorted(bins)])]
    return "\n".join(out)


if __name__ == "__main__":
    txt = report()
    (C.ROOT / "analizy" / "CUPSEY_SYGNALY.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
