"""Cechy startu tokena dla portfeli safety_bundle30 i safety_nocopy (7.10.2026) - ta sama logika co analizy
(analizy/bundles.py część 8, analizy/copycoins.py część 9). Tylko dane sprzed chwili decyzji, bazy tylko do odczytu.

bundle: zakupy z >= 2 różnych portfeli w tym samym slocie, w slocie utworzenia albo w N = 3 kolejnych (krzywa pump.fun,
        data/stream.db, bez routerów), % podaży netto (minus sprzedaż tych portfeli w slotach 0..3, max 100%).
        Brak tokena w zbieraczu albo dziura w danych przy starcie -> None (filtr nie kupuje).
kopia:  wcześniejszy token (60 h) z tym samym znormalizowanym tickerem lub nazwą; "aktywny" = w 24 h przed startem kopii
        zmigrował / >= 10 SOL obrotu na krzywej / bot widział obrót 24 h >= $50k. Grafika: ten sam klucz (CID IPFS
        albo adres) co wcześniejszy token w 60 h albo adres CDN z mintem innego tokena (cache grafik: tabela asset
        w data/analizy_cache.db, odświeża fb_logger). Token spoza danych -> None (filtr kopii go nie wyklucza).
"""
from __future__ import annotations

import bisect
import collections
import json
import sqlite3
import time
from pathlib import Path

import firstbuyers as F

N_SLOTS = 3
LOOKBACK_S = 60 * 3600
DAY = 86400
ACTIVE_SOL = 10.0
ACTIVE_VOL_USD = 50_000
ROUTERS_REFRESH_S = 7200


def norm(s) -> str | None:
    if not s:
        return None
    n = "".join(ch for ch in str(s).lower() if ch.isalnum())
    return n or None


def bundle_from_trades(tr: list, created_slot: int, creator, rts: set) -> dict:
    """tr: [(slot, ts, wallet, buy, sol, tok)]."""
    by_slot: dict = collections.defaultdict(lambda: collections.defaultdict(float))
    for slot, ts, w, buy, sol, tok in tr:
        rel = slot - created_slot
        if buy and 0 <= rel <= N_SLOTS and w not in rts:
            by_slot[rel][w] += tok
    bslots = {k: ws for k, ws in by_slot.items() if len(ws) >= 2}
    wallets = sorted({w for ws in bslots.values() for w in ws})
    s0 = by_slot.get(0, {})
    sold = sum(tok for slot, ts, w, buy, sol, tok in tr if not buy and 0 <= slot - created_slot <= N_SLOTS and w in wallets)
    gross = sum(v for ws in bslots.values() for v in ws.values())
    return {"b_wallets": wallets, "b_n": len(wallets),
            "bundle_start_pct": min(max(gross - sold, 0.0) / F.SUPPLY * 100, 100.0),
            "b_slot0_pct": sum(bslots.get(0, {}).values()) / F.SUPPLY * 100,
            "dev_alone_pct": (sum(s0.values()) / F.SUPPLY * 100) if len(s0) == 1 and creator in s0 else 0.0,
            "creator_in_bundle": int(creator in wallets)}


def _ro(path: Path):
    if not path.exists():
        return None
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


class LaunchCheck:
    def __init__(self, data_dir: Path):
        self.data = Path(data_dir)
        self.stream = _ro(self.data / "stream.db")
        self.bot = _ro(self.data / "bot.db")
        self.routers: set = set()
        self.routers_ts = 0.0
        self.toks: dict = {}                               # mint -> (t, nsym, nname, mint_id)
        self.by_sym: dict = collections.defaultdict(list)
        self.by_name: dict = collections.defaultdict(list)
        self.by_img: dict = collections.defaultdict(list)
        self.img: dict = {}                                # mint -> (klucz grafiki, mint z adresu CDN)
        self.last_mint_id = 0
        self.last_launch_ts = 0.0
        self.last_asset_ts = 0.0

    # ------------------------------------------------------------ bundle
    def refresh_routers(self):
        if not self.stream or time.time() - self.routers_ts < ROUTERS_REFRESH_S:
            return
        ids = [r[0] for r in self.stream.execute(
            "SELECT id FROM mints WHERE created_ts IS NOT NULL ORDER BY created_ts DESC LIMIT 400")]
        tr: dict = {i: [] for i in ids}
        if ids:
            for r in self.stream.execute(f"SELECT mint_id, slot, ts, wallet_id, buy, sol, tok FROM trades WHERE "
                                         f"ts < 2000000000 AND mint_id IN ({','.join(map(str, ids))})"):
                tr[r[0]].append(tuple(r[1:]))
        self.routers = F.routers(tr, ids)
        self.routers_ts = time.time()

    def bundle(self, mint: str) -> dict | None:
        if not self.stream:
            return None
        m = self.stream.execute("SELECT id, created_ts, created_slot, creator FROM mints WHERE mint=? AND "
                                "created_ts IS NOT NULL", (mint,)).fetchone()
        if not m:
            return None
        ts = [r[0] for r in self.stream.execute("SELECT DISTINCT ts FROM trades WHERE ts BETWEEN ? AND ? ORDER BY ts",
                                                 (m["created_ts"] - 15, m["created_ts"] + 15))]
        if not ts or any(b - a > 5 for a, b in zip([m["created_ts"] - 10] + ts, ts + [m["created_ts"] + 10])):
            return None                                     # dziura w danych zbieracza przy starcie
        self.refresh_routers()
        tr = [tuple(r) for r in self.stream.execute(
            "SELECT slot, ts, wallet_id, buy, sol, tok FROM trades WHERE mint_id=? AND slot <= ? ORDER BY slot",
            (m["id"], m["created_slot"] + N_SLOTS))]
        d = bundle_from_trades(tr, m["created_slot"], m["creator"], self.routers)
        d.pop("b_wallets")
        return d

    # ------------------------------------------------------------ kopie
    def _add(self, mint, t, sym, name, mid=None):
        old = self.toks.get(mint)
        if old and old[0] <= t:
            return
        d = (t, norm(sym), norm(name), mid if mid is not None else (old[3] if old else None))
        self.toks[mint] = d
        if d[1]:
            bisect.insort(self.by_sym[d[1]], (t, mint))
        if d[2]:
            bisect.insort(self.by_name[d[2]], (t, mint))

    def refresh_names(self):
        n0 = (self.last_mint_id, self.last_launch_ts, self.last_asset_ts)
        if self.stream:
            for r in self.stream.execute("SELECT id, mint, name, symbol, created_ts FROM mints WHERE id > ? AND "
                                         "created_ts IS NOT NULL ORDER BY id", (self.last_mint_id,)):
                self._add(r["mint"], float(r["created_ts"]), r["symbol"], r["name"], r["id"])
                self.last_mint_id = r["id"]
        if self.bot:
            for r in self.bot.execute("SELECT mint, ts, symbol, name FROM launches WHERE ts > ? ORDER BY ts",
                                      (self.last_launch_ts,)):
                self._add(r["mint"], float(r["ts"]), r["symbol"], r["name"])
                self.last_launch_ts = r["ts"]
        cache = _ro(self.data / "analizy_cache.db")
        if cache:
            try:
                for r in cache.execute("SELECT mint, image_key, image_ref, ts FROM asset WHERE ts > ? ORDER BY ts",
                                       (self.last_asset_ts,)):
                    self.img[r["mint"]] = (r["image_key"], r["image_ref"])
                    self.last_asset_ts = r["ts"]
            except sqlite3.Error:
                pass
            cache.close()
        changed = n0 != (self.last_mint_id, self.last_launch_ts, self.last_asset_ts)
        if not changed:
            return
        self.by_img = collections.defaultdict(list)
        for m, (k, _) in self.img.items():
            if k and m in self.toks:
                self.by_img[k].append((self.toks[m][0], m))
        for v in self.by_img.values():
            v.sort()

    def _active(self, mint: str, t: float) -> bool:
        d = self.toks.get(mint)
        if self.stream and d and d[3] is not None:
            r = self.stream.execute("SELECT MIN(ts) FROM events WHERE mint_id=? AND kind='migrate'", (d[3],)).fetchone()
            if r and r[0] and t - DAY <= r[0] < t:
                return True
            v = self.stream.execute("SELECT SUM(sol) FROM trades WHERE mint_id=? AND ts BETWEEN ? AND ?",
                                    (d[3], t - DAY, t)).fetchone()[0]
            if (v or 0) / 1e9 >= ACTIVE_SOL:
                return True
        if self.bot:
            r = self.bot.execute("SELECT ts FROM migrations WHERE mint=?", (mint,)).fetchone()
            if r and t - DAY <= r[0] < t:
                return True
            for (f,) in self.bot.execute("SELECT features FROM decisions WHERE mint=? AND ts BETWEEN ? AND ?",
                                         (mint, t - DAY, t)):
                try:
                    if float((json.loads(f or "{}") or {}).get("vol_h24") or 0) >= ACTIVE_VOL_USD:
                        return True
                except (ValueError, TypeError):
                    pass
        return False

    def copy(self, mint: str) -> dict | None:
        self.refresh_names()
        d = self.toks.get(mint)
        if not d:
            return None
        t = d[0]

        def window(lst):
            return lst[bisect.bisect_left(lst, (t - LOOKBACK_S, "")):bisect.bisect_left(lst, (t, ""))]

        preds = {m for _, m in window(self.by_sym.get(d[1], []))} | {m for _, m in window(self.by_name.get(d[2], []))}
        preds.discard(mint)
        active = any(self._active(m, t) for m in sorted(preds, key=lambda m: -self.toks[m][0])[:200])
        key, ref = self.img.get(mint, (None, None))
        img_preds = {m for _, m in window(self.by_img.get(key, []))} - {mint} if key else set()
        return {"copy_n": 1 + len(preds), "copy_active": int(active),
                "copy_cat": "c oryginał" if not preds else ("a kopia aktywnego" if active else "b kopia martwego"),
                "img_known": int(key is not None), "img_copy": int(bool(img_preds)),
                "img_ref": int(bool(ref and ref != mint))}

    def check(self, mint: str) -> dict:
        out = {}
        try:
            out["bundle"] = self.bundle(mint)
        except sqlite3.Error:
            out["bundle"] = None
        try:
            out["copy"] = self.copy(mint)
        except sqlite3.Error:
            out["copy"] = None
        return out
