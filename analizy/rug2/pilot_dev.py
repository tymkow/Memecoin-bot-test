"""Pilot a): pełna historia 100 twórców z Heliusa (kryterium: analizy/rug2/PILOT_A.md, ustalone przed pobraniem).

    python -m analizy.rug2.pilot_dev fetch [--rps 3]
    python -m analizy.rug2.pilot_dev report
"""
from __future__ import annotations

import argparse
import base64
import json
import random
import time

from analizy import common as C
from analizy import solana as SOL

PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
WSOL = "So11111111111111111111111111111111111111112"
SEED, N_DEVS, MAX_TX = 20261007, 100, 500
SCHEMA = """CREATE TABLE IF NOT EXISTS dev_hist(creator TEXT PRIMARY KEY, status TEXT, n_tx INTEGER, launches TEXT,
  credits INTEGER, ts REAL);
CREATE TABLE IF NOT EXISTS curve_complete(mint TEXT PRIMARY KEY, complete INTEGER, ts REAL);"""


def cache():
    from analizy.crash_gap import cache as cg
    db = cg()
    db.executescript(SCHEMA)
    return db


def sample():
    from analizy.rug2.pit import dataset
    ents = dataset()
    devs = sorted({e["creator_addr"] for e in ents if e.get("creator_addr")})
    random.Random(SEED).shuffle(devs)
    chosen = set(devs[:N_DEVS])
    return ents, [e for e in ents if e.get("creator_addr") in chosen], chosen


def curve_pda(mint: str) -> str:
    return SOL.find_pda([b"bonding-curve", SOL.b58decode(mint)], PUMP)


def creates_in(tx: dict, creator: str) -> list[tuple]:
    """[(mint, blockTime)] coinów utworzonych w transakcji przez twórcę (podpisującego)."""
    meta = tx.get("meta") or {}
    logs = " ".join(meta.get("logMessages") or [])
    if "Instruction: Create" not in logs or PUMP not in logs:
        return []
    msg = (tx.get("transaction") or {}).get("message") or {}
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg.get("accountKeys") or []]
    if not keys or keys[0] != creator:
        return []
    owners = {(b.get("mint"), b.get("owner")) for b in meta.get("postTokenBalances") or []}
    out = []
    for m in {b.get("mint") for b in meta.get("postTokenBalances") or []} - {WSOL, None}:
        if (m, curve_pda(m)) in owners:
            out.append((m, tx.get("blockTime")))
    return out


def fetch(rps: float):
    import rug_funding as rf
    ents, smp, devs = sample()
    db = cache()
    have = {r[0] for r in db.execute("SELECT creator FROM dev_hist WHERE status != 'blad'")}
    wf = {r[0]: r[1] for r in rf.wallet_db().execute("SELECT wallet, status FROM wallet_funding")}
    last = {}
    for e in smp:
        last[e["creator_addr"]] = max(last.get(e["creator_addr"], 0), e["created_ts"])
    h = rf.Helius(rps)
    credits = 0
    todo = sorted(d for d in devs if d not in have)
    print(f"twórców do pobrania: {len(todo)}", flush=True)
    for i, d in enumerate(todo, 1):
        if wf.get(d) == "aktywny":
            db.execute("INSERT OR REPLACE INTO dev_hist VALUES(?,?,?,?,?,?)", (d, "aktywny", None, "[]", 0, time.time()))
            db.commit()
            continue
        r = h.call("getTransactionsForAddress", [d, {"transactionDetails": "full", "sortOrder": "desc", "limit": MAX_TX,
                                                     "filters": {"blockTime": {"lte": int(last[d])}, "status": "succeeded"}}])
        if r is None:
            db.execute("INSERT OR REPLACE INTO dev_hist VALUES(?,?,?,?,?,?)", (d, "blad", None, "[]", 0, time.time()))
            db.commit()
            continue
        txs = r.get("data") or []
        cr = max(10, -(-len(txs) // 100) * 10)
        credits += cr
        launches = sorted({x for tx in txs for x in creates_in(tx, d)}, key=lambda x: x[1] or 0)
        status = "ok" if len(txs) < MAX_TX else "ucięte"
        db.execute("INSERT OR REPLACE INTO dev_hist VALUES(?,?,?,?,?,?)",
                   (d, status, len(txs), json.dumps(launches), cr, time.time()))
        db.commit()
        if i % 10 == 0:
            print(f"{time.strftime('%H:%M:%S')} {i}/{len(todo)} kredytów ~{credits}", flush=True)
    # flaga complete krzywych wcześniejszych coinów
    mints = sorted({m for (l,) in db.execute("SELECT launches FROM dev_hist") for m, _ in json.loads(l)}
                   - {r[0] for r in db.execute("SELECT mint FROM curve_complete")})
    for j in range(0, len(mints), 100):
        ch = mints[j:j + 100]
        r = h.call("getMultipleAccounts", [[curve_pda(m) for m in ch], {"encoding": "base64"}])
        credits += 1
        for m, acc in zip(ch, (r or {}).get("value") or []):
            comp = None
            if acc and acc.get("data"):
                raw = base64.b64decode(acc["data"][0])
                comp = raw[48] if len(raw) > 48 else None
            db.execute("INSERT OR REPLACE INTO curve_complete VALUES(?,?,?)", (m, comp, time.time()))
        db.commit()
    print(f"koniec: kredytów ~{credits}, zapytań {h.calls}")


def report() -> str:
    from analizy.rug2.pit import LaunchIndex
    ents, smp, devs = sample()
    C.add_outcomes(smp)
    db = cache()
    hist = {r[0]: (r[1], json.loads(r[3]), r[4]) for r in db.execute("SELECT * FROM dev_hist")}
    comp = dict(db.execute("SELECT mint, complete FROM curve_complete").fetchall())
    idx = LaunchIndex.load()
    for e in smp:
        st, launches, _ = hist.get(e["creator_addr"], ("brak", [], 0))
        prev = [(m, t) for m, t in launches if t and t < e["created_ts"] - 1 and m != e["mint"]]
        e["h_status"] = st
        e["h_prev"] = len(prev)
        mig = 0
        for m, t in prev:
            if t <= e["T"] - 86400 and comp.get(m):
                mig += 1
            elif idx.mig.get(m) is not None and idx.mig[m] < e["T"]:
                mig += 1
        e["h_mig"] = mig
        e["local_hist"] = int(bool(idx.prev_launches(e["creator_addr"], e["created_ts"])))
        e["grp"] = ("aktywny (seryjny, bez pobrania)" if st == "aktywny" else
                    ("H1: historia, >= 1 zmigrował" if prev and mig else
                     ("H2: historia, żaden nie zmigrował" if prev else "bez historii")))
    known = [e for e in smp if e["h_status"] in ("ok", "ucięte")]
    re_m, re_n = C.re_expected(ents, "s0") if False else (None, None)
    C.add_outcomes(ents)
    el = C.eligible_mints()
    re_ = [e for e in ents if e["mint"] in el]
    re_m = C.mean([e["s0"] for e in re_])
    out = [f"## Pilot a) - pełna historia twórcy ({time.strftime('%d.%m.%Y %H:%M')})\n",
           f"Próbka: {len(devs)} twórców, {len(smp)} tokenów. Kredyty Helius: ~{sum(v[2] for v in hist.values()) + 1}. "
           f"Pobranie: ok {sum(1 for e in smp if e['h_status'] == 'ok')}, ucięte do {MAX_TX} tx "
           f"{sum(1 for e in smp if e['h_status'] == 'ucięte')}, aktywni {sum(1 for e in smp if e['h_status'] == 'aktywny')}.\n",
           f"**Pokrycie historii:** wg Heliusa {C.mean([e['h_prev'] > 0 for e in known]):.0%} tokenów (z pobraną historią) ma "
           f"twórcę z >= 1 wcześniejszym startem; lokalnie (te same tokeny) {C.mean([e['local_hist'] for e in known]):.0%}.\n"]
    rows = []
    for g in ("bez historii", "H2: historia, żaden nie zmigrował", "H1: historia, >= 1 zmigrował", "aktywny (seryjny, bez pobrania)"):
        s = [e for e in smp if e["grp"] == g]
        rows.append([g, f"{len(s)}{C.rel(len(s))}", C.pct(C.mean([e['s0'] for e in s])), C.pct(C.mean([e['s6'] for e in s])),
                     f"{C.mean([e['rug'] for e in s]):.0%}" if s else "—",
                     ("**DZIAŁA**" if len(s) >= C.MIN_N and C.mean([e['s0'] for e in s]) >= re_m + 0.02 else
                      ("N < 30" if len(s) < C.MIN_N else "poniżej progu"))])
    out.append(C.table(["grupa", "N", "wynik (obecne wyjście)", "S6", "rug (e)", "vs próg random_eligible + 2 pp"], rows))
    ok = any(r[-1] == "**DZIAŁA**" for r in rows)
    out.append(f"\nPróg: random_eligible (cała pula, N {len(re_)}) {C.pct(re_m)} + 2 pp = {C.pct(re_m + 0.02)}. "
               f"Wszystkie tokeny próbki: {C.pct(C.mean([e['s0'] for e in smp]))}.\n\n**Werdykt pilota a): "
               f"{'działa' if ok else 'nie działa'}.**")
    txt = "\n".join(out)
    with open(C.ROOT / "analizy" / "rug2" / "PILOT_A.md", "a", encoding="utf-8") as fh:
        fh.write("\n\n" + txt + "\n")
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "report"])
    ap.add_argument("--rps", type=float, default=3)
    a = ap.parse_args()
    print(fetch(a.rps) if a.cmd == "fetch" else report())


if __name__ == "__main__":
    main()
