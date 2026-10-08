"""Moduł wykrywania rugów - etap 2 (5.10.2026): klastry wspólnego źródła finansowania (Helius, zwykłe RPC).

    python rug_funding.py fetch [--rps 5]   # posiadacze w chwili migracji -> kto zasilił portfel (cache w rug_data.db)
    python rug_funding.py report            # cechy klastrów + cechy krzywej -> ten sam raport co etap 1

Notatki użytkownika: "bubble mapy / połączone portfele", "time linked funding", "wallets funding time", "fresh wallets".
Dla każdego tokena (punkt decyzji = migracja, tylko tokeny bez dziur w danych zbieracza) bierzemy 20 największych
KUPUJĄCYCH z krzywej przed chwilą t (bez pośredników - salda z krzywej psują routery, patrz holders_at). Dla każdego portfela: najstarsza transakcja (getSignaturesForAddress, do 3 stron
po 1000) i jej źródło SOL (getTransaction: konto o największym spadku salda = zasilający). Portfel z >= 3000 transakcji
= "aktywny" (zasilający nieznany, wiek >= najstarszej z pobranych). Pierwsza transakcja portfela, który handlował przed t,
jest sprzed t - cechy są point-in-time. Liczba transakcji przed t liczona z pobranych podpisów (ucięta przy 3000).
Huby (giełdy, serwisy botów: zasilają wiele portfeli) wyznaczane TYLKO z tokenów treningowych - nie tworzą klastrów.
Koszt: Helius Free, 1 kredyt za zapytanie (1 mln/mies.), limit 10 zapytań/s - jedziemy wolniej.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import requests

import rug_backtest as rb
import rugguard
from rug_dataset import STREAM_DB, out_db, ro

TOP_N = 20
MAX_PAGES = 3
HUB_MIN = 15                 # zasilający >= tylu różnych portfeli w danych treningowych = hub (giełda, serwis)
WINDOW_S = 600


class Helius:
    def __init__(self, rps: float):
        key = json.loads((Path(__file__).parent / "secrets.json").read_text(encoding="utf-8")).get("HELIUS_API_KEY")
        if not key:
            raise SystemExit("brak HELIUS_API_KEY w secrets.json")
        self.url = f"https://mainnet.helius-rpc.com/?api-key={key}"     # adres z kluczem nigdy nie trafia do logów
        self.s = requests.Session()
        self.gap, self.last, self.calls = 1 / rps, 0.0, 0

    def call(self, method: str, params: list):
        for attempt in range(4):
            wait = self.gap - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            try:
                r = self.s.post(self.url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=30)
            except requests.RequestException:
                time.sleep(2 * (attempt + 1))
                continue
            self.calls += 1
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code != 200:
                return None
            j = r.json()
            if "error" in j:
                return None
            return j.get("result")
        return None


def funder_of(tx: dict, wallet: str) -> str | None:
    """Konto, którego saldo SOL spadło najbardziej w pierwszej transakcji portfela (poza samym portfelem)."""
    try:
        msg = tx["transaction"]["message"]
        keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
        la = tx["meta"].get("loadedAddresses") or {}
        keys += la.get("writable", []) + la.get("readonly", [])
        pre, post = tx["meta"]["preBalances"], tx["meta"]["postBalances"]
    except (KeyError, TypeError):
        return None
    best, drop = None, 0
    for k, a, b in zip(keys, pre, post):
        if k != wallet and a - b > drop:
            best, drop = k, a - b
    return best


def resolve(h: Helius, wallet: str) -> dict:
    sigs, before, oldest = [], None, False
    for _ in range(MAX_PAGES):
        opts = {"limit": 1000}
        if before:
            opts["before"] = before
        r = h.call("getSignaturesForAddress", [wallet, opts])
        if r is None:
            return {"status": "blad"}
        sigs += r
        if len(r) < 1000:
            oldest = True
            break
        before = r[-1]["signature"]
    if not sigs:
        return {"status": "pusty"}
    times = [s.get("blockTime") for s in sigs if s.get("blockTime")]
    out = {"status": "ok" if oldest else "aktywny", "first_ts": min(times) if times else None,
           "sig_times": json.dumps(sorted(times)[:3000])}
    if oldest:
        tx = h.call("getTransaction", [sigs[-1]["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
        out["funder"] = funder_of(tx, wallet) if tx else None
    return out


# ------------------------------------------------------------------ posiadacze w chwili t (z sald krzywej)
def holders_at(rows: list, split: float = 0.6) -> dict:
    """mint -> (t, creator_addr, [(addr, % wolumenu kupna)...]) - top N KUPUJĄCYCH z krzywej przed t.
    Nie salda: przy handlu przez routery TradeEvent zapisuje pośrednika, a tokeny idą dalej przelewem (5.10: salda
    niemożliwe w 21% tokenów). Pośrednicy wyłączeni: ujemne saldo w tym tokenie albo w >= 3 tokenach treningowych."""
    stream = ro(STREAM_DB)
    mints = {r["mint"]: r for r in rows}
    meta = {m["mint"]: m for m in stream.execute("SELECT id, mint, creator FROM mints WHERE mint IN (%s)"
                                                  % ",".join("?" * len(mints)), list(mints))}
    ids = {m["id"]: m["mint"] for m in meta.values()}
    trs: dict[str, list] = {m: [] for m in mints}
    q = (f"SELECT mint_id, slot, ts, wallet_id, buy, sol, tok FROM trades WHERE ts < 2000000000 AND mint_id IN "
         f"({','.join(map(str, ids))}) ORDER BY slot")
    for mid, slot, ts, w, buy, sol, tok in stream.execute(q):
        m = ids[mid]
        if ts <= mints[m]["t"]:
            trs[m].append((slot, ts, w, buy, sol, tok))
    train = {r["mint"] for r in rows[:int(len(rows) * split)]}
    neg: dict[int, int] = {}
    for m in train:
        net: dict[int, float] = {}
        for x in trs[m]:
            net[x[2]] = net.get(x[2], 0) + (x[5] if x[3] else -x[5])
        for w, v in net.items():
            if v < -1e-3 * 1e15:
                neg[w] = neg.get(w, 0) + 1
    routers = {w for w, n in neg.items() if n >= 3}
    tops = {}
    for m, tr in trs.items():
        top = rugguard.top_buyers(tr, TOP_N, routers)
        got = {}
        for x in tr:
            if x[3]:
                got[x[2]] = got.get(x[2], 0) + x[5]
        total = sum(got.values()) or 1
        tops[m] = [(w, got[w] / total * 100) for w in top]      # % wolumenu kupna (brutto przekracza podaż - boty)
    need = {w for top in tops.values() for w, _ in top} | {m["creator"] for m in meta.values() if m["creator"] is not None}
    addr = {}
    for i in range(0, len(need), 900):
        chunk = list(need)[i:i + 900]
        addr.update(dict(stream.execute(f"SELECT id, addr FROM wallets WHERE id IN ({','.join(map(str, chunk))})")))
    return {m: (mints[m]["t"], addr.get(meta[m]["creator"]), [(addr[w], p) for w, p in tops[m]]) for m in mints}


def wallet_db():
    db = out_db()
    db.execute("CREATE TABLE IF NOT EXISTS wallet_funding(wallet TEXT PRIMARY KEY, status TEXT, funder TEXT, "
               "first_ts REAL, sig_times TEXT, ts REAL)")
    return db


def fetch(rps: float):
    rows = rb.load(0)
    hs = holders_at(rows)
    wallets = sorted({a for _, c, top in hs.values() for a, _ in top} | {c for _, c, _ in hs.values() if c})
    db = wallet_db()
    done = {r[0] for r in db.execute("SELECT wallet FROM wallet_funding WHERE status != 'blad'")}
    todo = [w for w in wallets if w not in done]
    print(f"tokenów {len(hs)}, portfeli {len(wallets)}, do sprawdzenia {len(todo)}, tempo {rps}/s", flush=True)
    h = Helius(rps)
    for i, w in enumerate(todo, 1):
        r = resolve(h, w)
        db.execute("INSERT OR REPLACE INTO wallet_funding VALUES(?,?,?,?,?,?)",
                   (w, r["status"], r.get("funder"), r.get("first_ts"), r.get("sig_times"), time.time()))
        if i % 100 == 0:
            db.commit()
            st = dict(db.execute("SELECT status, COUNT(*) FROM wallet_funding GROUP BY status").fetchall())
            print(f"{time.strftime('%H:%M:%S')} {i}/{len(todo)} zapytań Helius {h.calls} {st}", flush=True)
    db.commit()
    print(f"koniec; zapytań (kredytów) Helius: {h.calls}")


# ------------------------------------------------------------------ cechy i raport
FUND_FEATURES = ["clust_max_pct", "clust_sum_pct", "clust_wallets", "creator_linked_pct", "fund_time_cluster",
                 "young_1d_share", "low_tx_share", "wallet_age_med_h", "hub_funded_share", "unknown_share"]


def features(t: float, creator: str | None, top: list, info: dict, hubs: set) -> dict:
    hold = [(a, pct, info.get(a) or {}) for a, pct in top]
    known = [(a, pct, i) for a, pct, i in hold if i.get("status") in ("ok", "aktywny")]
    f: dict = {"unknown_share": 1 - len(known) / len(hold) if hold else 1.0}
    groups: dict[str, list] = {}
    for a, pct, i in known:
        fu = i.get("funder")
        if fu and fu not in hubs:
            groups.setdefault(fu, []).append((a, pct))
    creator_f = (info.get(creator) or {}).get("funder") if creator else None
    clusters = {fu: g for fu, g in groups.items() if len(g) >= 2}
    f["clust_max_pct"] = max((sum(p for _, p in g) for g in clusters.values()), default=0.0)
    f["clust_sum_pct"] = sum(p for g in clusters.values() for _, p in g)
    f["clust_wallets"] = sum(len(g) for g in clusters.values())
    linked = {fu for fu in (creator, creator_f) if fu and fu not in hubs}
    f["creator_linked_pct"] = sum(p for a, p, i in known if a != creator and (i.get("funder") in linked))
    firsts = sorted(i["first_ts"] for _, _, i in known if i.get("first_ts") and i["status"] == "ok")
    f["fund_time_cluster"] = (max(sum(1 for y in firsts if x <= y <= x + WINDOW_S) for x in firsts) / len(hold)
                              if firsts else 0.0)
    # wiek tylko przy znanej pierwszej transakcji ("aktywny" = najnowsze 3000 tx, najstarsza z nich nie jest pierwszą)
    ages = [(t - i["first_ts"]) / 3600 for _, _, i in known if i.get("first_ts") and i["status"] == "ok" and i["first_ts"] <= t]
    f["young_1d_share"] = sum(a < 24 for a in ages) / len(hold) if hold else 0.0
    f["wallet_age_med_h"] = statistics.median(ages) if ages else None
    ntx = [sum(1 for x in json.loads(i.get("sig_times") or "[]") if x < t) for _, _, i in known if i["status"] == "ok"]
    f["low_tx_share"] = sum(n < 20 for n in ntx) / len(hold) if hold else 0.0
    f["hub_funded_share"] = sum(1 for _, _, i in known if i.get("funder") in hubs) / len(hold) if hold else 0.0
    return f


def report(split: float = 0.6):
    rows = rb.load(0)
    hs = holders_at(rows)
    db = wallet_db()
    info = {r["wallet"]: dict(r) for r in db.execute("SELECT * FROM wallet_funding")}
    cut = int(len(rows) * split)
    train = {r["mint"] for r in rows[:cut]}
    cnt: dict[str, set] = {}
    for m in train:
        for a, _ in hs[m][2]:
            fu = (info.get(a) or {}).get("funder")
            if fu:
                cnt.setdefault(fu, set()).add(a)
    hubs = {fu for fu, ws in cnt.items() if len(ws) >= HUB_MIN}
    covered = 0
    for r in rows:
        t, creator, top = hs[r["mint"]]
        f = features(t, creator, top, info, hubs)
        covered += f["unknown_share"] < 0.5
        r["f"].update(f)
    print(f"etap 2: tokenów {len(rows)}, z rozpoznanymi źródłami >= połowy top-{TOP_N}: {covered}; "
          f"hubów (zasilają >= {HUB_MIN} portfeli w treningu): {len(hubs)}")
    rb.report(rows=rows, features=FUND_FEATURES + rb.FEATURES, bot=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "report"])
    ap.add_argument("--rps", type=float, default=5)
    a = ap.parse_args()
    fetch(a.rps) if a.cmd == "fetch" else report()


if __name__ == "__main__":
    main()
