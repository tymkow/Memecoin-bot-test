"""Dane do map sieci portfeli w panelu (8.10.2026): python -m analizy.mapy -> data/mapy.json (kilka minut, stream.db).

Mapy:
  * floty klonów - jeden bot na wielu portfelach (data/klony.json z analizy/clones.py); węzeł = portfel, kolor = grupa,
    wielkość = liczba pozycji, wynik w SOL w podpowiedzi;
  * grupy kupujące razem (analizy/cabal.py, cała próba): krawędź = para kupująca ten sam start w <= 2 s w >= 5 tokenach;
    bez "grupy" sieci snajperów (> 100 portfeli);
  * naśladowcy traderów: trader w środku, portfele kupujące <= 5 s po nim w >= 3 jego tokenach i >= 20x częściej niż
    losowo (jak kol_select.followers);
  * bundle startu: portfele kupujące w SLOCIE UTWORZENIA tokena (poza twórcą); krawędź = razem w slocie startu w
    >= 3 tokenach - pierścienie portfeli używanych przy wielu startach. Plus statystyki bundli vs migracja.
"""
from __future__ import annotations

import bisect
import collections
import json

from analizy import cabal as K
from analizy import common as C
from analizy import kol

TRADERS = {"Cupsey": "2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f",
           "Trader B": "PODAJ_ADRES_PORTFELA",
           "Bot D": "PODAJ_ADRES_PORTFELA",
           "Bot E": "PODAJ_ADRES_PORTFELA"}
MAX_GROUPS = 30
MAX_FOLLOWERS = 60


def short(a: str) -> str:
    return a[:4] + "…" + a[-4:]


def wallet_pnl(st, ids: list) -> dict:
    """{wallet_id: (pozycji zamkniętych na krzywej, SOL)}."""
    if not ids:
        return {}
    out = {}
    q = (f"SELECT wallet_id, SUM(CASE WHEN buy=1 THEN sol ELSE 0 END)/1e9, SUM(CASE WHEN buy=0 THEN sol ELSE 0 END)/1e9, "
         f"SUM(CASE WHEN buy=1 THEN tok ELSE 0 END), SUM(CASE WHEN buy=0 THEN tok ELSE 0 END) FROM trades "
         f"WHERE wallet_id IN ({','.join(map(str, ids))}) GROUP BY wallet_id, mint_id")
    for w, b, s, bt, stk in st.execute(q):
        if b > 0 and bt > 0 and 0.98 * bt <= stk <= 1.02 * bt:
            n, p = out.get(w, (0, 0.0))
            out[w] = (n + 1, p + s - b)
    return out


def fleets(st, addr2id, addr) -> dict:
    d = json.loads((C.DATA / "klony.json").read_text(encoding="utf-8"))
    groups = d["groups"][:15]
    ids = [addr2id[a] for g in groups for a in g if a in addr2id]
    pnl = wallet_pnl(st, ids)
    nodes, links = [], []
    for gi, g in enumerate(groups):
        ws = [addr2id[a] for a in g if a in addr2id]
        tot = sum(pnl.get(w, (0, 0))[1] for w in ws)
        for w in ws:
            n, p = pnl.get(w, (0, 0.0))
            nodes.append({"id": addr[w], "label": short(addr[w]), "g": gi, "n": n, "sol": round(p, 1),
                          "info": f"flota {gi + 1}: {len(ws)} portfeli, razem {tot:+.1f} SOL"})
        hub = ws[0] if ws else None
        for w in ws[1:]:
            links.append({"s": addr[hub], "t": addr[w], "w": 1})
    return {"nodes": nodes, "links": links,
            "about": "Każdy kolor to jeden bot rozbity na wiele portfeli: ten sam rytm, te same godziny, prawie zero wspólnych tokenów."}


def cabals(st, eb, created, addr) -> dict:
    mints = list(eb)
    groups, edges, n = K.find_groups(eb, mints, with_edges=True)
    size = collections.Counter(groups.values())
    keep = [g for g, s in size.most_common() if s <= 100][:MAX_GROUPS]
    kset = set(keep)
    nodes = [{"id": addr[w], "label": short(addr[w]), "g": keep.index(g), "n": n[w], "sol": None,
              "info": f"grupa {keep.index(g) + 1}: {size[g]} portfeli; {n[w]} startów kupionych w 300 s"}
             for w, g in groups.items() if g in kset]
    links = [{"s": addr[a], "t": addr[b], "w": c} for a, b, c in edges if groups.get(a) in kset and groups.get(a) == groups.get(b)]
    return {"nodes": nodes, "links": links, "stat": {"groups": len(size), "wallets": len(groups),
                                                     "sniper_net": max(size.values()) if size else 0},
            "about": "Portfele, które raz po raz kupują ten sam start w ciągu 2 s. Grubość linii = w ilu tokenach razem."}


def followers(st, created, addr2id, addr) -> dict:
    nodes, links = [], []
    base_n = st.execute("SELECT COUNT(*) FROM mints").fetchone()[0]
    for ti, (name, a) in enumerate(TRADERS.items()):
        me = addr2id.get(a)
        if me is None:
            continue
        eps, _ = kol.episodes_stream(a)
        ent = {}
        for e in eps:
            mid = st.execute("SELECT id FROM mints WHERE mint=?", (e["mint"],)).fetchone()
            if mid and created.get(mid[0]) and 0 <= e["t"] - created[mid[0]] <= 600:
                ent[mid[0]] = e["legs"][0]
        after = collections.Counter()
        for mid, leg in ent.items():
            ws = {r[0] for r in st.execute("SELECT DISTINCT wallet_id FROM trades WHERE mint_id=? AND buy=1 AND slot > ? "
                                           "AND ts <= ? AND wallet_id != ?", (mid, leg["slot"], leg["bt"] + 5, me))}
            for w in ws:
                after[w] += 1
        cand = [w for w, c in after.items() if c >= 3]
        if not cand:
            continue
        first = collections.defaultdict(set)
        for w, m, t in st.execute(f"SELECT wallet_id, mint_id, MIN(ts) FROM trades WHERE buy=1 AND wallet_id IN "
                                  f"({','.join(map(str, cand))}) GROUP BY wallet_id, mint_id"):
            if created.get(m) and t - created[m] <= 600:
                first[w].add(m)
        base = len(ent) / base_n
        fol = sorted(((after[w], len(first[w] & set(ent)) / len(first[w]) / base, w) for w in cand if first[w]
                      and len(first[w] & set(ent)) / len(first[w]) / base >= 20), reverse=True)[:MAX_FOLLOWERS]
        center = f"T:{name}"
        nodes.append({"id": center, "label": name, "g": ti, "n": len(ent), "sol": None, "center": True,
                      "info": f"{name}: {len(ent)} wejść w pierwszych 10 min; {len(fol)} naśladowców na mapie"})
        for hits, lift, w in fol:
            nid = f"{name}:{addr[w]}"
            nodes.append({"id": nid, "label": short(addr[w]), "g": ti, "n": hits, "sol": None,
                          "info": f"kupił <= 5 s po {name} w {hits} jego tokenach; {lift:.0f}x częściej niż losowo"})
            links.append({"s": center, "t": nid, "w": hits})
    return {"nodes": nodes, "links": links,
            "about": "W środku trader, wokół portfele, które kupują sekundy po nim i prawie tylko jego tokeny (boty kopiujące albo jego własne portfele)."}


def bundles(st, created, addr) -> dict:
    first_slot = dict(st.execute("SELECT mint_id, MIN(slot) FROM trades GROUP BY mint_id"))
    creator = dict(st.execute("SELECT id, creator FROM mints"))
    mig = {r[0] for r in st.execute("SELECT DISTINCT mint_id FROM events WHERE kind='migrate'")}
    in_slot = collections.defaultdict(set)
    sol0 = collections.Counter()
    for m, slot, w, sol in st.execute("SELECT mint_id, slot, wallet_id, sol FROM trades WHERE buy=1"):
        if slot == first_slot.get(m) and w != creator.get(m):
            in_slot[m].add(w)
            sol0[m] += sol / 1e9
    toks = [m for m in first_slot if created.get(m)]
    bucket = collections.defaultdict(lambda: [0, 0])
    for m in toks:
        k = len(in_slot.get(m, ()))
        b = "0" if k == 0 else "1" if k == 1 else "2-3" if k <= 3 else "4-7" if k <= 7 else "8+"
        bucket[b][0] += 1
        bucket[b][1] += m in mig
    pair = collections.Counter()
    seen = collections.Counter()
    for m, ws in in_slot.items():
        ws = sorted(ws)
        for w in ws:
            seen[w] += 1
        if len(ws) > 30:
            continue
        for i in range(len(ws)):
            for j in range(i + 1, len(ws)):
                pair[(ws[i], ws[j])] += 1
    strong = [(a, b, c) for (a, b), c in pair.items() if c >= 3]
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, _ in strong:
        parent[find(a)] = find(b)
    comp = collections.defaultdict(list)
    for w in parent:
        comp[find(w)].append(w)
    rings = sorted(comp.values(), key=len, reverse=True)
    rings = [r for r in rings if len(r) <= 80][:MAX_GROUPS]
    gid = {w: i for i, r in enumerate(rings) for w in r}
    nodes = [{"id": addr[w], "label": short(addr[w]), "g": gid[w], "n": seen[w], "sol": None,
              "info": f"pierścień {gid[w] + 1}: {len(rings[gid[w]])} portfeli; w slocie startu {seen[w]} tokenów"}
             for w in gid]
    links = [{"s": addr[a], "t": addr[b], "w": c} for a, b, c in strong if a in gid and b in gid]
    order = ["0", "1", "2-3", "4-7", "8+"]
    stats = [{"k": b, "n": bucket[b][0], "mig": round(bucket[b][1] / bucket[b][0] * 100, 2) if bucket[b][0] else None}
             for b in order]
    return {"nodes": nodes, "links": links, "stats": stats,
            "share": round(sum(1 for m in toks if len(in_slot.get(m, ())) >= 2) / max(len(toks), 1) * 100, 1),
            "about": "Portfele kupujące w tym samym slocie, w którym powstaje token (bundle twórcy). Linia = razem w slocie startu w >= 3 tokenach."}


def build():
    st = C.ro("stream.db")
    addr = dict(st.execute("SELECT id, addr FROM wallets"))
    addr2id = {v: k for k, v in addr.items()}
    eb, created = K.early_buys()
    out = {"floty": fleets(st, addr2id, addr), "grupy": cabals(st, eb, created, addr),
           "nasladowcy": followers(st, created, addr2id, addr), "bundle": bundles(st, created, addr)}
    (C.DATA / "mapy.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return {k: (len(v["nodes"]), len(v["links"])) for k, v in out.items()}


if __name__ == "__main__":
    print(build())
