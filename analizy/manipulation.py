"""5. WYKRYWANIE MANIPULACJI (obrona, nie strategia) - flagi z transakcji krzywej pump.fun sprzed chwili decyzji.

  F1 skoordynowane zakupy: >= 3 portfele (nie twórca, nie router) kupują w JEDNYM slocie w pierwszych 20 slotach
     ALBO >= 3 z 20 pierwszych kupujących ma wspólnego zasilającego (bez hubów; Helius)
  F2 wash trading: udział w wolumenie kupna (SOL) portfeli z >= 2 "kółkami" kup->sprzedaj->kup w tym tokenie
     >= górny tercyl eksploracji
  F3 wolumen bez nowych kupujących: ostatnie 10 min krzywej przed migracją (tylko krzywe >= 20 min) - wolumen >=
     górny tercyl eksploracji i udział kupna od portfeli NOWYCH dla tego tokena <= dolny tercyl eksploracji
  F4 dev/insider sprzedaje w trakcie pompy: twórca lub portfel zasilony przez twórcę/jego zasilającego sprzedaje
     >= 1% podaży w chwili, gdy cena > cena sprzed 5 min
Tokeny z dziurą w danych zbieracza w [utworzenie, t] pomijane (flagi wymagają pełnej historii).
Ocena: (A) migracje + 30 min - rug/pump i wynik wejścia; (B) PRAWDZIWE pozycje bota - czy omijanie flag poprawia $.
"""
from __future__ import annotations

import collections
import json

from analizy import common as C
import firstbuyers as FC
from analizy import first_buyers as FB

SUPPLY = 1e15


def flags_for(tr: list, created_slot: int, creator, t: float, mig_ts: float | None, routers: set, funders: dict,
              hubs: set, creator_links: set) -> dict:
    tr = [x for x in tr if x[1] <= t]
    f = {}
    # F1
    early = [x for x in tr if x[3] and x[0] - created_slot <= 20 and x[2] != creator and x[2] not in routers]
    by_slot = collections.defaultdict(set)
    for x in early:
        by_slot[x[0]].add(x[2])
    fbw = FC.first_buyers(tr, routers)
    fc = collections.Counter(funders.get(w) for w in fbw if funders.get(w) and funders.get(w) not in hubs)
    f["F1"] = int(max((len(s) for s in by_slot.values()), default=0) >= 3 or max(fc.values(), default=0) >= 3)
    # F2
    seq = collections.defaultdict(list)
    vol = collections.Counter()
    for x in tr:
        if x[2] in routers:
            continue
        seq[x[2]].append(x[3])
        if x[3]:
            vol[x[2]] += x[4]
    loops = {w for w, s in seq.items() if sum(1 for a, b, c in zip(s, s[1:], s[2:]) if a and not b and c) >= 2}
    tot = sum(vol.values()) or 1
    f["wash_share"] = sum(v for w, v in vol.items() if w in loops) / tot
    f["F2"] = int(f["wash_share"] >= 0.25)
    # F3 (surowe wartości; progi z eksploracji w report)
    end = mig_ts if mig_ts and mig_ts <= t else t
    if not tr or end - tr[0][1] < 1200:              # krzywa < 20 min: okno 10 min = cała krzywa, "nowi" = wszyscy
        f["vol10"], f["new_share10"] = None, None
        f["F2"] = f["F2"]
    win = [x for x in tr if end - 600 <= x[1] <= end and x[3] and x[2] not in routers] if f.get("vol10", 0) is not None else []
    before = {x[2] for x in tr if x[1] < end - 600}
    if "vol10" not in f:
        f["vol10"] = sum(x[4] for x in win) / 1e9
        f["new_share10"] = (sum(x[4] for x in win if x[2] not in before) / (sum(x[4] for x in win) or 1)) if win else None
    # F4
    px = [(x[1], x[5] and x[4] / x[5]) for x in tr]
    sold = 0.0
    for x in tr:
        if not x[3] and (x[2] == creator or funders.get(x[2]) in creator_links):
            p_now = x[4] / x[5] if x[5] else 0
            past = [p for ts, p in px if x[1] - 330 <= ts <= x[1] - 270 and p]
            if past and p_now > past[0]:
                sold += x[5]
    f["F4"] = int(sold >= 0.01 * SUPPLY)
    return f


def context():
    import collector
    import rug_dataset as rd
    import rug_funding as rf
    entries, explore, trades, rt, fb, addr = FB.setup()
    stream = rd.ro(rd.STREAM_DB)
    holes = collector.data_holes(stream)
    info = {r["wallet"]: dict(r) for r in rf.wallet_db().execute("SELECT * FROM wallet_funding")}
    cnt = collections.defaultdict(set)
    for e in explore:
        for w in fb[e["mint_id"]]:
            fu = (info.get(addr.get(w)) or {}).get("funder")
            if fu:
                cnt[fu].add(w)
    hubs = {fu for fu, s in cnt.items() if len(s) >= FC.HUB_MIN}
    return entries, explore, trades, rt, addr, info, hubs, holes, stream


def funder_map(tr, addr_of, info):
    return {x[2]: (info.get(addr_of(x[2])) or {}).get("funder") for x in tr}


def report() -> str:
    entries, explore, trades, rt, addr, info, hubs, holes, stream = context()
    ex_ids = {e["mint_id"] for e in explore}
    rows = []
    for e in entries:
        if C.holes_overlap(holes, e["created_ts"] - 60, e["mig_ts"]):
            continue
        tr = trades[e["mint_id"]]
        fm = funder_map(tr, addr.get, info)
        cr = addr.get(e["creator"])
        links = {x for x in (cr, (info.get(cr) or {}).get("funder")) if x and x not in hubs}
        f = flags_for(tr, e["created_slot"], e["creator"], e["ts"], e["mig_ts"], rt, fm, hubs, links)
        f.update(sim=C.sim(e["path"], e["ref"], e["path"][0][0]), label=e["label"], ex=e["mint_id"] in ex_ids, ts=e["ts"])
        rows.append(f)
    exr = [r for r in rows if r["ex"]]
    v10 = sorted(r["vol10"] for r in exr if r["vol10"] is not None)
    ns = sorted(r["new_share10"] for r in exr if r["new_share10"] is not None)
    ws = sorted(r["wash_share"] for r in exr)
    hi_v, lo_n, hi_w = v10[int(len(v10) * 2 / 3)], ns[int(len(ns) / 3)], max(ws[int(len(ws) * 2 / 3)], 1e-9)
    f3 = lambda r: int(r["vol10"] is not None and r["vol10"] >= hi_v and r["new_share10"] is not None and r["new_share10"] <= lo_n)
    for r in rows:
        r["F3"] = f3(r)
        r["F2"] = int(r["wash_share"] >= hi_w)
    out = ["## 5. Wykrywanie manipulacji (obrona)\n",
           f"**(A) Migracje + 30 min, tokeny z pełną historią krzywej: {len(rows)}** (eksploracja {len(exr)}, TEST "
           f"{len(rows) - len(exr)}). Progi z eksploracji: F2 udział kółek >= {hi_w:.0%}; F3 (tylko krzywe >= 20 min: "
           f"{len(v10)} tokenów eksploracji) wolumen 10 min >= {hi_v:.1f} SOL i nowi kupujący <= {lo_n:.0%}.\n"]
    tab = []
    for fl in ("F1", "F2", "F3", "F4"):
        for lbl, rs in (("eksploracja", exr), ("TEST", [r for r in rows if not r["ex"]])):
            a = [r for r in rs if r[fl]]
            b = [r for r in rs if not r[fl]]
            tab.append([fl, lbl, f"{len(a)}{C.rel(len(a))}", f"{C.mean([r['label'] == 'rug' for r in a]):.0%}" if a else "—",
                        f"{C.mean([r['label'] == 'rug' for r in b]):.0%}", C.pct(C.mean([r['sim'] for r in a])),
                        C.pct(C.mean([r['sim'] for r in b])), C.pct(C.mean([r['sim'] for r in rs])),
                        C.pct(C.mean([r['sim'] for r in b]) - C.mean([r['sim'] for r in rs]))])
    out.append(C.table(["flaga", "zbiór", "N z flagą", "rug z flagą", "rug bez", "wynik z flagą", "wynik bez",
                        "baseline (wszystkie)", "zysk z omijania"], tab))

    # (B) prawdziwe pozycje bota w tokenach z historią krzywej
    mints = {m["mint"]: m for m in stream.execute("SELECT id, mint, created_ts, created_slot, creator FROM mints WHERE created_ts IS NOT NULL")}
    mig = dict(stream.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind='migrate' GROUP BY mint_id"))
    be = [e for e in C.bot_entries(with_snaps=False) if e["mint"] in mints and mints[e["mint"]]["created_ts"] < e["ts"]]
    ids = sorted({mints[e["mint"]]["id"] for e in be})
    trb = {i: [] for i in ids}
    if ids:
        for r in stream.execute(f"SELECT mint_id, slot, ts, wallet_id, buy, sol, tok FROM trades WHERE ts < 2000000000 AND "
                                f"mint_id IN ({','.join(map(str, ids))}) ORDER BY slot"):
            trb[r[0]].append(tuple(r[1:]))
    need = {x[2] for i in ids for x in trb[i]}
    addr2 = dict(addr)
    lst = [w for w in need if w not in addr2]
    for i in range(0, len(lst), 900):
        ch = lst[i:i + 900]
        addr2.update(dict(stream.execute(f"SELECT id, addr FROM wallets WHERE id IN ({','.join(map(str, ch))})")))
    brow = []
    for e in be:
        m = mints[e["mint"]]
        if C.holes_overlap(holes, m["created_ts"] - 60, e["ts"]):
            continue
        tr = trb[m["id"]]
        fm = funder_map(tr, addr2.get, info)
        cr = addr2.get(m["creator"])
        links = {x for x in (cr, (info.get(cr) or {}).get("funder")) if x and x not in hubs}
        f = flags_for(tr, m["created_slot"], m["creator"], e["ts"], mig.get(m["id"]), rt, fm, hubs, links)
        f["F3"] = f3(f)
        f["F2"] = int(f["wash_share"] >= hi_w)
        f["pnl"] = sum(p["pnl"] for p in e["pos"])
        f["n_pos"] = len(e["pos"])
        f["ts"] = e["ts"]
        brow.append(f)
    bex, bte = C.split_time(brow)
    out.append(f"\n**(B) PRAWDZIWE pozycje bota w tokenach z pełną historią krzywej: {len(brow)} wejść** "
               f"(eksploracja {len(bex)}, TEST {len(bte)}).\n")
    tb = []
    for fl in ("F1", "F2", "F3", "F4"):
        for lbl, rs in (("eksploracja", bex), ("TEST", bte)):
            a = [r for r in rs if r[fl]]
            tb.append([fl, lbl, f"{len(a)}{C.rel(len(a))}", f"{sum(r['n_pos'] for r in a)}",
                       f"{sum(r['pnl'] for r in a):+.0f}", f"{sum(r['pnl'] for r in rs):+.0f}",
                       f"{sum(r['pnl'] for r in rs) - sum(r['pnl'] for r in a):+.0f}"])
    out.append(C.table(["flaga", "zbiór", "wejść z flagą", "pozycji", "$ z flagą", "$ baseline (wszystkie)",
                        "$ gdyby omijać flagę"], tb))
    return "\n".join(out)


if __name__ == "__main__":
    print(report())
