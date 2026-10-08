"""Dane "do chwili T" (point-in-time) dla nowych źródeł sygnału (rug2, 7.10.2026). Każda funkcja cech dostaje T i nie
może użyć niczego późniejszego - pilnują tego testy (analizy/rug2/tests). Bazy tylko do odczytu, bez Heliusa
(wersja lokalna: cache wallet_funding z wcześniejszych analiz).

Zbiór: migracje żywe w T = migracja + 30 min (common.migration_entries) - wynik pozycji po kosztach: s0 (wyjście bota),
s6 (S6); etykieta (e) tylko pomocniczo.
"""
from __future__ import annotations

import bisect
import collections
import statistics

from analizy import common as C

DAY = 86400.0


# ------------------------------------------------------------------ zbiór
def dataset() -> list[dict]:
    """Migracje + 30 min z wynikiem, twórcą (adres) i pierwszymi kupującymi (adresy) - jak część 1 (first_buyers.setup)."""
    from analizy import first_buyers as FB
    entries, explore, trades, rt, fb, addr = FB.setup()
    C.add_outcomes(entries)
    for e in entries:
        e["T"] = e["ts"]
        e["creator_addr"] = addr.get(e["creator"])
        e["fb_addrs"] = [addr[w] for w in fb.get(e["mint_id"], []) if w in addr]
        e["curve"] = [x for x in trades.get(e["mint_id"], []) if x[1] <= e["T"]]     # (slot, ts, wallet, buy, sol, tok)
    return entries


# ------------------------------------------------------------------ a) historia twórcy
class LaunchIndex:
    """Wszystkie starty z danych: zbieracz (od 04.10 10:23) + PumpPortal bota (od 01.10 20:23, nocne przerwy)."""

    def __init__(self, launches: list[tuple], migrations: dict, curve_vol: dict):
        # launches: (creator_addr, ts, mint); migrations: mint -> ts migracji; curve_vol: mint -> [(ts, sol)] posortowane
        self.by_dev: dict = collections.defaultdict(list)
        seen = {}
        for dev, ts, mint in launches:
            if dev and (mint not in seen or ts < seen[mint][1]):
                seen[mint] = (dev, ts)
        for mint, (dev, ts) in seen.items():
            self.by_dev[dev].append((ts, mint))
        for v in self.by_dev.values():
            v.sort()
        self.mig = migrations
        self.vol = curve_vol
        self.first_ts = min((ts for _, ts in seen.values()), default=0.0)

    @classmethod
    def load(cls) -> "LaunchIndex":
        import rug_dataset as rd
        s = rd.ro(rd.STREAM_DB)
        b = C.ro("bot.db")
        cr_ids = {r[0] for r in s.execute("SELECT DISTINCT creator FROM mints WHERE creator IS NOT NULL")}
        addr = {}
        lst = list(cr_ids)
        for i in range(0, len(lst), 900):
            ch = lst[i:i + 900]
            addr.update(dict(s.execute(f"SELECT id, addr FROM wallets WHERE id IN ({','.join(map(str, ch))})")))
        launches = [(addr.get(r[0]), float(r[1]), r[2]) for r in
                    s.execute("SELECT creator, created_ts, mint FROM mints WHERE created_ts IS NOT NULL")]
        launches += [(r[0], float(r[1]), r[2]) for r in b.execute("SELECT creator, ts, mint FROM launches")]
        mig = {}
        for m, ts in s.execute("SELECT m.mint, MIN(e.ts) FROM events e JOIN mints m ON m.id=e.mint_id "
                               "WHERE e.kind='migrate' GROUP BY e.mint_id"):
            mig[m] = ts
        for m, ts in b.execute("SELECT mint, ts FROM migrations"):
            mig[m] = min(ts, mig.get(m, ts))
        vol: dict = collections.defaultdict(list)
        for m, ts, sol in s.execute("SELECT m.mint, t.ts / 60 * 60, SUM(t.sol) FROM trades t JOIN mints m ON m.id=t.mint_id "
                                    "WHERE t.ts < 2000000000 GROUP BY t.mint_id, t.ts / 60"):
            vol[m].append((ts, (sol or 0) / 1e9))
        return cls(launches, mig, dict(vol))

    def prev_launches(self, dev: str, created_ts: float) -> list[tuple]:
        lst = self.by_dev.get(dev, [])
        return lst[:bisect.bisect_left(lst, (created_ts - 1, ""))]

    def features(self, dev: str | None, created_ts: float, T: float) -> dict:
        """Cechy twórcy w chwili T: tylko starty PRZED utworzeniem tokena i to, co o nich było wiadomo do T."""
        prev = self.prev_launches(dev, created_ts) if dev else []
        mig = [m for _, m in prev if self.mig.get(m) is not None and self.mig[m] < T]
        vols = []
        for ts, m in prev:
            v = self.vol.get(m, [])
            vols.append(sum(x for t, x in v[:bisect.bisect_left(v, (T, -1.0))]))
        hist_days = max((created_ts - self.first_ts) / DAY, 1e-9)
        return {"dev_prev_n": len(prev), "dev_has_hist": int(bool(prev)), "dev_prev_mig_n": len(mig),
                "dev_prev_mig_rate": len(mig) / len(prev) if prev else None,
                "dev_gap_h": (created_ts - prev[-1][0]) / 3600 if prev else None,
                "dev_prev_maxvol_sol": max(vols) if vols else None,
                "dev_prev_medvol_sol": statistics.median(vols) if vols else None,
                "dev_launches_per_day": len(prev) / hist_days}


# ------------------------------------------------------------------ b) graf zasilania
class FundingGraph:
    """Kto zasilił portfel pierwszym przelewem (cache wallet_funding: rug_funding.resolve). Hub = portfel 'aktywny'
    (>= 3000 transakcji: giełdy, serwisy) albo zasilający >= HUB_MIN różnych portfeli w danych EKSPLORACJI -
    przez hub nie propagujemy (inaczej wszystko łączy się przez Binance)."""

    HUB_MIN = 15

    def __init__(self, rows: dict, hubs: set):
        self.rows, self.hubs = rows, hubs        # rows: wallet -> (status, funder, first_ts)

    @classmethod
    def load(cls, explore_wallets: set | None = None) -> "FundingGraph":
        import rug_funding as rf
        rows = {r[0]: (r[1], r[2], r[3]) for r in rf.wallet_db().execute(
            "SELECT wallet, status, funder, first_ts FROM wallet_funding")}
        cnt = collections.defaultdict(set)
        for w, (st, f, ft) in rows.items():
            if f and (explore_wallets is None or w in explore_wallets):
                cnt[f].add(w)
        hubs = {f for f, ws in cnt.items() if len(ws) >= cls.HUB_MIN} | {w for w, r in rows.items() if r[0] == "aktywny"}
        return cls(rows, hubs)

    def funder(self, w: str, T: float):
        """Zasilający portfela, jeśli znany i zasilenie (pierwsza transakcja portfela) było przed T."""
        r = self.rows.get(w)
        if not r or r[0] != "ok" or not r[1] or r[2] is None or r[2] > T:
            return None
        return r[1]

    def ancestors(self, w: str, K: int, T: float) -> list:
        """[hop1, hop2, ...] do K; None = nieznany/hub (dalej nie idziemy)."""
        out, cur = [], w
        for _ in range(K):
            f = self.funder(cur, T) if cur else None
            if f is None or f in self.hubs:
                out.append(None)
                cur = None
            else:
                out.append(f)
                cur = f
        return out

    def chain_known(self, w: str, k: int, T: float) -> bool:
        """Czy łańcuch do hopu k jest rozpoznany: każdy krok ma wpis w cache albo kończy się na hubie / portfelu
        bez zasilającego (wtedy wiadomo, że dalej nic nie ma)."""
        cur = w
        for _ in range(k):
            r = self.rows.get(cur)
            if r is None:
                return False
            if r[0] != "ok" or not r[1] or r[1] in self.hubs or (r[2] is not None and r[2] > T):
                return True
            cur = r[1]
        return True
