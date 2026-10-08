"""Kopiowanie zyskownych portfeli - test POZA PRÓBĄ (8.10.2026).

    python -m analizy.copy_oos        # -> analizy/KOPIA_OOS.md (tylko stream.db, krzywa pump.fun)

Poprzednio (KOL_Bot D / KOL_Bot E) kopia z opóźnieniem 0.4-20 s dawała +1.6..+3.6%/poz., ale portfele były wybrane
na tym samym oknie (błąd selekcji). Tu:
  1. EKSPLORACJA = pierwsze 70% czasu (po chwili pierwszego zakupu pozycji). Portfele z >= MIN_POS zamkniętymi
     pozycjami na krzywej, <= 20% zakupów w slocie utworzenia (insiderzy twórcy odpadają), mediana stawki >= 0.05 SOL,
     bez pozycji z tokenami spoza zakupu. Klony (podobny odcisk, >= 70% wspólnych godzin, <= 2% wspólnych tokenów) -
     z grupy bierzemy tylko pierwszy w rankingu.
  2. REGUŁY WYBORU (ustalone przed testem): R1 top 20 po sumie SOL; R2 top 20 po średnim wyniku na pozycję wśród
     portfeli zyskownych w obu połowach eksploracji; R3 = R2 + średnia bez 1% największych pozycji > 0;
     kontrola = 20 losowych portfeli spełniających warunki aktywności.
  3. TEST = ostatnie 30%: każda pozycja wybranego portfela otwarta w teście, skopiowana k slotów po każdej jego
     transakcji (k = 1, 5, 12, 25, 50 -> 0.4-20 s): fill = jego fill x (spot przed nim / spot po k slotach), krzywa ze
     strumienia; -0.4 pp na nasze koszty (2 x 0.0005 SOL przy 0.25 SOL). CI: bootstrap po pozycjach ORAZ po portfelach
     (pozycje jednego portfela nie są niezależne). Odporność: bez 1% największych, połowy testu.
  4. Do tego: czy wynik portfela na eksploracji przewiduje wynik na teście (korelacja rang Spearmana).
"""
from __future__ import annotations

import collections
import random
import statistics as S
import time

from analizy import common as C
from analizy import cupsey_ahead as A
from analizy import kol

MIN_POS = 50
TOP = 20
KS = (1, 5, 12, 25, 50)
OUR_COST = 0.004


def wallet_stats(t_cut: float):
    st = C.ro("stream.db")
    first_slot = dict(st.execute("SELECT mint_id, MIN(slot) FROM trades GROUP BY mint_id"))
    q = ("SELECT wallet_id, mint_id, SUM(CASE WHEN buy=1 THEN sol ELSE 0 END)/1e9, SUM(CASE WHEN buy=0 THEN sol ELSE 0 END)/1e9, "
         "SUM(CASE WHEN buy=1 THEN tok ELSE 0 END), SUM(CASE WHEN buy=0 THEN tok ELSE 0 END), "
         "MIN(CASE WHEN buy=1 THEN ts END), MIN(CASE WHEN buy=0 THEN ts END), MIN(CASE WHEN buy=1 THEN slot END) "
         "FROM trades GROUP BY wallet_id, mint_id")
    W = collections.defaultdict(list)
    ext = collections.Counter()
    for w, m, b, s, bt, stk, tb, ts_, sb in st.execute(q):
        if not tb or tb >= t_cut or b <= 0 or bt <= 0:
            continue
        if stk > 1.02 * bt:
            ext[w] += 1
            continue
        if stk >= 0.98 * bt and ts_:
            W[w].append({"m": m, "b": b, "s": s, "t": tb, "hold": ts_ - tb, "slot0": sb == first_slot.get(m)})
    addr = dict(st.execute("SELECT id, addr FROM wallets"))
    return W, ext, addr


def fp(ps):
    holds = [p["hold"] for p in ps]
    n = len(ps)
    return {"stawka": S.median(p["b"] for p in ps), "trzyma": max(S.median(holds), 1),
            "s14": sum(14 <= h <= 19 for h in holds) / n, "s60": sum(58 <= h <= 63 for h in holds) / n,
            "s300": sum(295 <= h <= 305 for h in holds) / n, "godz": {int(p["t"] // 3600) for p in ps},
            "tok": {p["m"] for p in ps}}


def clone(a, b):
    r = lambda x, y: max(x, y) / max(min(x, y), 1e-9)               # noqa: E731
    if r(a["stawka"], b["stawka"]) > 1.3 or r(a["trzyma"], b["trzyma"]) > 1.5:
        return False
    if any(abs(a[k] - b[k]) > 0.10 for k in ("s14", "s60", "s300")):
        return False
    h = len(a["godz"] & b["godz"]) / min(len(a["godz"]), len(b["godz"]))
    t = len(a["tok"] & b["tok"]) / min(len(a["tok"]), len(b["tok"]))
    return h >= 0.7 and t <= 0.02


def copy_ret(e, k, slp):
    tok = sol = 0.0
    for r in e["legs"]:
        p0 = slp.before(r, r["slot"])
        p1 = slp.before(r, r["slot"] + 1 + k)
        if not p0 or not p1:
            return None
        if r["kind"] == "buy":
            tok += r["tok"] * p0 / p1
            sol += r["sol"]
        elif r["tok"] > 0:
            q = tok * r["frac"]
            sol += r["sol"] * (q / r["tok"]) * p1 / p0
            tok -= q
    return sol / e["cost"] - OUR_COST


def boot_wallet(per_w: dict, n=2000, seed=1):
    ws = [w for w, xs in per_w.items() if xs]
    if len(ws) < 2:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    ms = []
    for _ in range(n):
        xs = [x for w in rng.choices(ws, k=len(ws)) for x in per_w[w]]
        ms.append(sum(xs) / len(xs))
    ms.sort()
    return ms[int(n * 0.025)], ms[int(n * 0.975)]


def spearman(a, b):
    ra = {x: i for i, x in enumerate(sorted(range(len(a)), key=lambda i: a[i]))}
    rb = {x: i for i, x in enumerate(sorted(range(len(b)), key=lambda i: b[i]))}
    n = len(a)
    return 1 - 6 * sum((ra[i] - rb[i]) ** 2 for i in range(n)) / (n * (n * n - 1)) if n > 2 else float("nan")


def report() -> str:
    t0, t1 = C.ro("stream.db").execute("SELECT MIN(ts), MAX(ts) FROM trades").fetchone()
    cut = t0 + (t1 - t0) * C.SPLIT
    mid_ex = t0 + (cut - t0) / 2
    W, ext, addr = wallet_stats(cut)
    elig = {}
    for w, ps in W.items():
        if len(ps) < MIN_POS or ext[w] > 0.05 * len(ps) or sum(p["slot0"] for p in ps) > 0.2 * len(ps):
            continue
        if S.median(p["b"] for p in ps) < 0.05:
            continue
        rets = sorted((p["s"] - p["b"]) / p["b"] for p in ps)
        elig[w] = {"n": len(ps), "sol": sum(p["s"] - p["b"] for p in ps), "mean": S.mean(rets),
                   "trim": S.mean(rets[:max(int(len(rets) * 0.99), 1)]),
                   "h1": sum(p["s"] - p["b"] for p in ps if p["t"] < mid_ex),
                   "h2": sum(p["s"] - p["b"] for p in ps if p["t"] >= mid_ex), "fp": fp(ps)}

    def pick(order, cond):
        sel = []
        for w in order:
            if not cond(elig[w]):
                continue
            if any(clone(elig[w]["fp"], elig[x]["fp"]) for x in sel):
                continue
            sel.append(w)
            if len(sel) == TOP:
                break
        return sel
    by_sol = sorted(elig, key=lambda w: -elig[w]["sol"])
    by_mean = sorted(elig, key=lambda w: -elig[w]["mean"])
    rules = {
        "R1 top 20 po sumie SOL": pick(by_sol, lambda s: s["sol"] > 0),
        "R2 top 20 po śr. wyniku, zysk w obu połowach": pick(by_mean, lambda s: s["h1"] > 0 and s["h2"] > 0 and s["n"] >= 100),
        "R3 = R2 + średnia bez 1% najlepszych > 0": pick(by_mean, lambda s: s["h1"] > 0 and s["h2"] > 0 and s["n"] >= 100
                                                         and s["trim"] > 0),
        "kontrola: 20 losowych aktywnych": random.Random(7).sample(sorted(elig), min(TOP, len(elig))),
    }
    slp = A.SlotPrices()
    mid_te = cut + (t1 - cut) / 2
    out = [f"# Kopiowanie zyskownych portfeli - test poza próbą ({time.strftime('%d.%m.%Y %H:%M')})\n",
           f"Eksploracja do {time.strftime('%d.%m %H:%M', time.localtime(cut))}, TEST potem "
           f"({(t1 - cut) / 3600:.0f} h). Portfeli spełniających warunki na eksploracji: {len(elig)}.\n"]
    corr_rows = []
    for name, sel in rules.items():
        per = {k: collections.defaultdict(list) for k in KS}
        halves = {k: ([], []) for k in KS}
        his = collections.defaultdict(list)
        for w in sel:
            eps, _ = kol.episodes_stream(addr[w])
            for e in eps:
                if e["t"] < cut or not e["closed"] or e["cost"] <= 0:
                    continue
                his[w].append(e["his_sol"] / e["cost"])
                for k in KS:
                    x = copy_ret(e, k, slp)
                    if x is not None:
                        per[k][w].append(x)
                        halves[k][e["t"] >= mid_te].append(x)
        rows = []
        allhis = [x for xs in his.values() for x in xs]
        for k in KS:
            xs = [x for v in per[k].values() for x in v]
            if not xs:
                continue
            lo, hi = C.boot_ci(xs)
            wl, wh = boot_wallet(per[k])
            srt = sorted(xs)
            rows.append([f"{k} ({k * 0.4:.1f} s)", len(xs), C.pct(C.mean(xs)), f"{lo * 100:+.1f}..{hi * 100:+.1f}",
                         f"{wl * 100:+.1f}..{wh * 100:+.1f}", C.pct(C.median(xs)),
                         C.pct(C.mean(srt[:int(len(srt) * 0.99)])),
                         f"{C.pct(C.mean(halves[k][0]))} / {C.pct(C.mean(halves[k][1]))}",
                         f"{sum(1 for v in per[k].values() if v and C.mean(v) > 0)}/{sum(1 for v in per[k].values() if v)}"])
        out += [f"\n## {name} ({len(sel)} portfeli; ich własny wynik w teście: "
                f"{C.pct(C.mean(allhis))} na {len(allhis)} poz.)\n",
                C.table(["opóźnienie (sloty)", "pozycji", "śr.", "CI po pozycjach", "CI po portfelach", "mediana",
                         "bez 1% najlepszych", "1. / 2. połowa testu", "portfeli > 0"], rows)]
        if name.startswith("R1"):
            for w in sel:
                if his[w]:
                    corr_rows.append((elig[w]["mean"], C.mean(his[w])))
    # trwałość: czy wynik z eksploracji przewiduje test (wszystkie kwalifikujące się, ich własny wynik)
    sample = sorted(elig, key=lambda w: -elig[w]["n"])[:300]
    a, b = [], []
    for w in sample:
        eps, _ = kol.episodes_stream(addr[w])
        xs = [e["his_sol"] / e["cost"] for e in eps if e["t"] >= cut and e["closed"] and e["cost"] > 0]
        if len(xs) >= 20:
            a.append(elig[w]["mean"])
            b.append(C.mean(xs))
    top_q = [y for x, y in sorted(zip(a, b), reverse=True)[:len(a) // 5]]
    bot_q = [y for x, y in sorted(zip(a, b))[:len(a) // 5]]
    out.append(f"\n## Trwałość umiejętności\n\n300 najaktywniejszych portfeli (>= 20 pozycji w teście: {len(a)}): korelacja "
               f"rang wyniku eksploracja -> test (ich własne transakcje) = {spearman(a, b):.2f}. Najlepsza piątka na "
               f"eksploracji ma w teście śr. {C.pct(C.mean(top_q))}, najgorsza piątka {C.pct(C.mean(bot_q))}.")
    return "\n".join(out)


def consensus(min_w: int = 2, window: int = 60) -> str:
    """Zgoda kilku zręcznych portfeli: token, który kupiło >= min_w różnych portfeli z R1 u R2 (wybranych na
    eksploracji) w ciągu window s -> nasze wejście po drugim zakupie + d. Wyjścia i koszty jak slow_rule.sim."""
    from analizy import cabal as K
    from analizy import slow_rule as R
    st = C.ro("stream.db")
    t0, t1 = st.execute("SELECT MIN(ts), MAX(ts) FROM trades").fetchone()
    cut = t0 + (t1 - t0) * C.SPLIT
    W, ext, addr = wallet_stats(cut)
    elig = [w for w, ps in W.items() if len(ps) >= MIN_POS and ext[w] <= 0.05 * len(ps)
            and sum(p["slot0"] for p in ps) <= 0.2 * len(ps) and S.median(p["b"] for p in ps) >= 0.05]
    sol = {w: sum(p["s"] - p["b"] for p in W[w]) for w in elig}
    skilled = set(sorted(elig, key=lambda w: -sol[w])[:100])
    mig = dict(st.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind IN ('complete','migrate') GROUP BY mint_id"))
    odd = {r[0] for r in st.execute("SELECT DISTINCT mint_id FROM trades WHERE vsol < 25e9")}
    q = f"SELECT mint_id, wallet_id, MIN(ts) FROM trades WHERE buy=1 AND ts >= ? AND wallet_id IN ({','.join(map(str, skilled))}) GROUP BY mint_id, wallet_id"
    first = collections.defaultdict(list)
    for m, w, t in st.execute(q, (cut,)):
        first[m].append(t)
    sig = []
    for m, ts in first.items():
        ts.sort()
        for i in range(min_w - 1, len(ts)):
            if ts[i] - ts[i - min_w + 1] <= window:
                sig.append((m, ts[i]))
                break
    rows = []
    res = {d: collections.defaultdict(list) for d in (2, 5, 20)}
    base = {d: collections.defaultdict(list) for d in (2, 5, 20)}
    rng = random.Random(3)
    allm = [r[0] for r in st.execute("SELECT id FROM mints WHERE created_ts >= ? AND created_ts <= ?", (cut, t1 - 400))]
    for m, T in sig:
        if m in odd or T > t1 - 400:
            continue
        tp = K.tape(st, m, T + 400)
        for d in res:
            for ex, (r, _) in R.sim(tp, T + d, mig.get(m)).items():
                if r is not None:
                    res[d][ex].append(r)
        # baseline: losowy token w tym samym wieku
        c = st.execute("SELECT created_ts FROM mints WHERE id=?", (m,)).fetchone()[0]
        age = T - c if c else 30
        for _ in range(2):
            b = rng.choice(allm)
            cb = st.execute("SELECT created_ts FROM mints WHERE id=?", (b,)).fetchone()[0]
            if b in odd or not cb:
                continue
            tpb = K.tape(st, b, cb + age + 400)
            if not tpb["ts"] or tpb["ts"][-1] < cb + age:
                continue
            for d in base:
                for ex, (r, _) in R.sim(tpb, cb + age + d, mig.get(b)).items():
                    if r is not None:
                        base[d][ex].append(r)
    for d in res:
        for ex in R.EXITS:
            xs, bs = res[d][ex], base[d][ex]
            lo, hi = C.boot_ci(xs) if len(xs) > 1 else (float("nan"),) * 2
            rows.append([f"{d} s", R.EXIT_NAME[ex], f"N {len(xs)}: śr. {C.pct(C.mean(xs))} (CI {lo * 100:+.1f}..{hi * 100:+.1f}), "
                         f"med. {C.pct(C.median(xs))}", f"N {len(bs)}: śr. {C.pct(C.mean(bs))}, med. {C.pct(C.median(bs))}"])
    return (f"\n## Zgoda zręcznych portfeli (top 100 po SOL na eksploracji; >= {min_w} kupiło ten sam token w {window} s)\n\n"
            f"Sygnałów w teście: {len(sig)}. Uwaga: bez filtra dziur strumienia.\n\n" +
            C.table(["opóźnienie", "wyjście", "zgoda", "baseline: losowy token w tym samym wieku"], rows))



if __name__ == "__main__":
    txt = report() + "\n" + consensus()
    (C.ROOT / "analizy" / "KOPIA_OOS.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
