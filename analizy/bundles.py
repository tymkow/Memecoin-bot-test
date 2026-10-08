"""8. BUNDLERY - zakupy wielu portfeli w bloku startu tokena i to, ile z tego nadal trzymają w chwili decyzji.

    python -m analizy.bundles fetch [--rps 3]   # zasilający portfeli bundli + ich saldo tokena w chwili decyzji (Helius)
    python -m analizy.bundles report

Definicje (ustalone przed patrzeniem na wyniki):
  bundle      = zakupy z >= 2 RÓŻNYCH portfeli w tym samym slocie: w slocie utworzenia tokena albo w N = 3 kolejnych
                (krzywa pump.fun z data/stream.db, bez routerów). Portfel bundla = każdy kupujący w takim slocie (też twórca).
  (a) bundle_start_pct = % podaży kupiony w bundlach przy starcie (netto: minus sprzedaż tych portfeli w slotach 0..3,
                         bo zdarza się "flip" w bloku startu; max 100%).
  (b) bundle_held_pct  = % podaży, który portfele bundla NADAL mają w chwili decyzji bota: saldo ich kont tokena (ATA)
                         po ostatniej transakcji przed chwilą t (Helius: historia konta + saldo z transakcji). Przelew na
                         inny portfel liczy się jako "nie trzyma" (dolne oszacowanie trzymania przez grupę).
  wspólny zasilający = >= 2 portfele bundla zasilone przez ten sam portfel (bez hubów - giełd/serwisów zasilających
                       >= 15 portfeli na eksploracji) albo portfel bundla zasilony przez twórcę lub jego zasilającego.
  "dev sam" = w slocie utworzenia kupił tylko twórca (to NIE jest bundle wg definicji - osobna kategoria w tabelach).
Zbiory: migracje + 30 min (każdy żywy token, jak części 1-6) i wejścia bota w tokeny utworzone w czasie zbierania.
Wynik wejścia: wyjście bota (S0) i S6, koszty analiz; rug = etykieta (e): -70% przed +50% w 6 h; "max zysk" = MFE.
Progi filtrów wyłącznie z eksploracji (70% czasu), TEST liczony raz.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import time

import firstbuyers as F
from analizy import common as C
from analizy import solana as SOL

N_SLOTS = 3
BUCKETS = ((0, 10), (10, 20), (20, 30), (30, 40), (40, 101))
HOLD_SCHEMA = """CREATE TABLE IF NOT EXISTS hold(mint TEXT, wallet TEXT, t INTEGER, status TEXT, amount REAL, n_sigs INTEGER,
  ts REAL, PRIMARY KEY(mint, wallet, t));
CREATE TABLE IF NOT EXISTS mint_program(mint TEXT PRIMARY KEY, program TEXT);"""


def cache():
    from analizy.crash_gap import cache as cg_cache
    db = cg_cache()
    db.executescript(HOLD_SCHEMA)
    return db


# ------------------------------------------------------------------ zbiory i bundle z krzywej
def stream_info(mints: list[str]) -> dict:
    import rug_dataset as rd
    s = rd.ro(rd.STREAM_DB)
    out = {}
    for i in range(0, len(mints), 500):
        ch = mints[i:i + 500]
        q = (f"SELECT id, mint, created_ts, created_slot, creator FROM mints WHERE created_ts IS NOT NULL AND mint IN "
             f"({','.join('?' * len(ch))})")
        for r in s.execute(q, ch):
            out[r[1]] = {"mint_id": r[0], "created_ts": r[2], "created_slot": r[3], "creator": r[4]}
    return out


def pending_migrations() -> list[dict]:
    """Migracje, dla których świece jeszcze się pobierają: chwila decyzji (migracja + 30 min) jest znana bez świec,
    więc zasilających i salda można pobrać równolegle (wspólne z first_buyers.fetch --pending)."""
    import rug_dataset as rd
    have = {r[0] for r in C.ro("rug_data.db").execute("SELECT mint FROM pools WHERE status IN ('ok', 'brak_swiec')")}
    return [{"mint": m["mint"], "mint_id": m["mint_id"], "created_ts": m["created_ts"], "created_slot": m["created_slot"],
             "creator": m["creator"], "ts": m["mig_ts"] + 1800} for m in rd.migrations(rd.ro(rd.STREAM_DB))
            if m["mint"] not in have and m["mig_ts"] + 1800 < time.time()]


def entry_sets(pending: bool = False) -> dict[str, list[dict]]:
    if pending:
        return {"mig": pending_migrations(), "bot": [], "bot_all": []}
    mig = C.migration_entries(30)
    bot = C.bot_entry_set()
    info = stream_info([e["mint"] for e in bot])
    bot2 = []
    for e in bot:
        if e["mint"] in info and info[e["mint"]]["created_ts"] <= e["ts"]:
            e.update(info[e["mint"]])
            bot2.append(e)
    return {"mig": mig, "bot": bot2, "bot_all": bot}


def curve(ids: list[int]) -> dict[int, list]:
    import rug_dataset as rd
    s = rd.ro(rd.STREAM_DB)
    out: dict[int, list] = {i: [] for i in ids}
    for i in range(0, len(ids), 800):
        ch = ids[i:i + 800]
        q = (f"SELECT mint_id, slot, ts, wallet_id, buy, sol, tok FROM trades WHERE ts < 2000000000 AND mint_id IN "
             f"({','.join(map(str, ch))}) ORDER BY slot")
        for r in s.execute(q):
            out[r[0]].append(tuple(r[1:]))
    return out


def detect(tr: list, created_slot: int, creator, rts: set) -> dict:
    import launchcheck
    return launchcheck.bundle_from_trades(tr, created_slot, creator, rts)     # ta sama logika co portfel safety_bundle30


def holes_ok(holes: list, t: float) -> bool:
    return not C.holes_overlap(holes, t - 10, t + 10)


def build(pending: bool = False) -> dict:
    """Zbiory z cechami bundli (bez sald - te z cache po fetch)."""
    import collector
    import rug_dataset as rd
    sets = entry_sets(pending)
    stream = rd.ro(rd.STREAM_DB)
    holes = sorted(collector.data_holes(stream))
    ids = sorted({e["mint_id"] for k in ("mig", "bot") for e in sets[k]})
    trades = curve(ids)
    mig_ex, _ = C.split_time(sets["mig"])
    rts = F.routers(trades, {e["mint_id"] for e in mig_ex})
    addr: dict = {}
    for k in ("mig", "bot"):
        for e in sets[k]:
            e["assessable"] = holes_ok(holes, e["created_ts"])
            e.update(detect(trades[e["mint_id"]], e["created_slot"], e["creator"], rts))
    need = sorted({w for k in ("mig", "bot") for e in sets[k] for w in e["b_wallets"]} |
                  {e["creator"] for k in ("mig", "bot") for e in sets[k] if e["creator"] is not None})
    for i in range(0, len(need), 900):
        ch = need[i:i + 900]
        addr.update(dict(stream.execute(f"SELECT id, addr FROM wallets WHERE id IN ({','.join(map(str, ch))})")))
    sets["addr"], sets["routers"] = addr, rts
    return sets


# ------------------------------------------------------------------ Helius: zasilający i saldo w chwili t
def token_programs(h, mints: list[str], db) -> dict:
    have = dict(db.execute("SELECT mint, program FROM mint_program").fetchall())
    todo = [m for m in mints if m not in have]
    for i in range(0, len(todo), 100):
        ch = todo[i:i + 100]
        r = h.call("getMultipleAccounts", [ch, {"encoding": "base64", "dataSlice": {"offset": 0, "length": 0}}])
        for m, acc in zip(ch, (r or {}).get("value") or []):
            if acc and acc.get("owner"):
                have[m] = acc["owner"]
                db.execute("INSERT OR REPLACE INTO mint_program VALUES(?,?)", (m, acc["owner"]))
        db.commit()
    return have


def tx_keys(tx: dict) -> list[str]:
    msg = (tx.get("transaction") or {}).get("message") or {}
    la = (tx.get("meta") or {}).get("loadedAddresses") or {}
    return [k["pubkey"] if isinstance(k, dict) else k for k in msg.get("accountKeys") or []] + \
        la.get("writable", []) + la.get("readonly", [])


def acc_balance_at(h, acc: str, owner: str, mint: str, t: float):
    """(saldo konta tokena w chwili t, status, liczba podpisów): saldo po ostatniej udanej transakcji konta przed t."""
    before, n = None, 0
    for _ in range(3):
        opts = {"limit": 1000}
        if before:
            opts["before"] = before
        r = h.call("getSignaturesForAddress", [acc, opts])
        if r is None:
            return None, "blad", n
        n += len(r)
        cand = [x for x in r if x.get("blockTime") and x["blockTime"] <= t and not x.get("err")]
        if cand:
            tx = h.call("getTransaction", [cand[0]["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1}])
            if not tx:
                return None, "blad", n
            keys = tx_keys(tx)
            amt = 0.0
            for b in (tx.get("meta") or {}).get("postTokenBalances") or []:
                i = b.get("accountIndex")
                if b.get("mint") == mint and i is not None and i < len(keys) and keys[i] == acc:
                    ui = b.get("uiTokenAmount") or {}
                    amt += float(ui.get("amount") or 0) / 10 ** int(ui.get("decimals") or 6)
            return amt, "ok", n
        if len(r) < 1000:
            return (0.0, "po_t", n) if r else (None, "brak_konta", n)
        before = r[-1]["signature"]
    return None, "za_duzo", n


def other_accounts(h, owner: str, mint: str, created_slot: int) -> list[str]:
    """Konta tokena portfela, które NIE są ATA (narzędzia do bundli kupują na losowe konta): otwarte z
    getTokenAccountsByOwner, a zamknięte - z transakcji kupna w slotach startu (historia portfela, do 3 stron)."""
    r = h.call("getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "base64",
                                                                   "dataSlice": {"offset": 0, "length": 0}}])
    accs = [x["pubkey"] for x in (r or {}).get("value") or []]
    if accs:
        return accs
    before = None
    for _ in range(3):
        opts = {"limit": 1000}
        if before:
            opts["before"] = before
        sigs = h.call("getSignaturesForAddress", [owner, opts])
        if not sigs:
            break
        near = [x for x in sigs if x.get("slot") is not None and created_slot <= x["slot"] <= created_slot + N_SLOTS
                and not x.get("err")]
        for x in near[:3]:
            tx = h.call("getTransaction", [x["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1}])
            keys = tx_keys(tx or {})
            for b in ((tx or {}).get("meta") or {}).get("postTokenBalances") or []:
                i = b.get("accountIndex")
                if b.get("mint") == mint and b.get("owner") == owner and i is not None and i < len(keys):
                    accs.append(keys[i])
        if accs or len(sigs) < 1000 or (sigs[-1].get("slot") or 0) < created_slot:
            break
        before = sigs[-1]["signature"]
    return sorted(set(accs))


def balance_at(h, owner: str, mint: str, program: str, t: float, created_slot: int):
    """(saldo portfela w tokenach w chwili t, status, liczba podpisów): najpierw konto ATA, potem inne konta tokena."""
    amt, st, n = acc_balance_at(h, SOL.ata(owner, mint, program), owner, mint, t)
    if st != "brak_konta":
        return amt, st, n
    accs = other_accounts(h, owner, mint, created_slot)
    if not accs:
        return None, "brak_konta", n
    tot = 0.0
    for a in accs:
        x, s2, n2 = acc_balance_at(h, a, owner, mint, t)
        n += n2
        if x is None and s2 != "brak_konta":
            return None, s2, n
        tot += x or 0.0
    return tot, "ok_inne_konto", n


def fetch(rps: float, pending: bool = False):
    import rug_funding as rf
    sets = build(pending)
    addr = sets["addr"]
    h = rf.Helius(rps)
    # 1) zasilający portfeli bundli i twórców (ta sama tabela co pierwsi kupujący)
    wdb = rf.wallet_db()
    wdb.execute("PRAGMA busy_timeout=60000")
    have = {r[0] for r in wdb.execute("SELECT wallet FROM wallet_funding WHERE status != 'blad'")}
    ents = [e for k in ("mig", "bot") for e in sets[k] if e["assessable"]]
    todo = sorted({addr[w] for e in ents for w in e["b_wallets"] if w in addr and addr[w] not in have} |
                  {addr[e["creator"]] for e in ents if e["b_n"] and e["creator"] in addr and addr[e["creator"]] not in have})
    print(f"tokenów do oceny {len(ents)}, z bundlem {sum(1 for e in ents if e['b_n'])}; zasilających do sprawdzenia "
          f"{len(todo)}", flush=True)
    for i, w in enumerate(todo, 1):
        r = rf.resolve(h, w)
        wdb.execute("INSERT OR REPLACE INTO wallet_funding VALUES(?,?,?,?,?,?)",
                    (w, r["status"], r.get("funder"), r.get("first_ts"), r.get("sig_times"), time.time()))
        wdb.commit()      # od razu: długa transakcja blokowała zapis świec do rug_data.db
        if i % 100 == 0:
            print(f"{time.strftime('%H:%M:%S')} zasilający {i}/{len(todo)} zapytań {h.calls}", flush=True)
    wdb.commit()
    # 2) saldo portfeli bundla w chwili decyzji
    db = cache()
    progs = token_programs(h, sorted({e["mint"] for e in ents if e["b_n"]}), db)
    done = {(r[0], r[1], r[2]) for r in db.execute("SELECT mint, wallet, t FROM hold WHERE status NOT IN ('blad', 'brak_konta')")}
    jobs = sorted({(e["mint"], addr[w], int(e["ts"])) for e in ents for w in e["b_wallets"] if w in addr} - done)
    slot_of = {e["mint"]: e["created_slot"] for e in ents}
    print(f"sald do odczytu: {len(jobs)}", flush=True)
    for i, (m, w, t) in enumerate(jobs, 1):
        amt, status, n = balance_at(h, w, m, progs.get(m, SOL.TOKEN), t, slot_of[m])
        db.execute("INSERT OR REPLACE INTO hold VALUES(?,?,?,?,?,?,?)", (m, w, t, status, amt, n, time.time()))
        db.commit()
        if i % 100 == 0 or i == len(jobs):
            print(f"{time.strftime('%H:%M:%S')} salda {i}/{len(jobs)} zapytań {h.calls}", flush=True)
    db.commit()
    print(f"koniec, zapytań Helius {h.calls}")


# ------------------------------------------------------------------ cechy końcowe
def finish(sets: dict) -> None:
    import rug_funding as rf
    addr = sets["addr"]
    info = {r["wallet"]: dict(r) for r in rf.wallet_db().execute("SELECT * FROM wallet_funding")}
    db = cache()
    hold = {(r[0], r[1], r[2]): (r[3], r[4]) for r in db.execute("SELECT mint, wallet, t, status, amount FROM hold")}
    mig_ex, _ = C.split_time(sets["mig"])
    cnt = collections.defaultdict(set)
    for e in mig_ex:
        for w in e["b_wallets"]:
            f = (info.get(addr.get(w)) or {}).get("funder")
            if f:
                cnt[f].add(w)
    hubs = {f for f, s in cnt.items() if len(s) >= F.HUB_MIN}
    sets["hubs"] = hubs
    for k in ("mig", "bot"):
        for e in sets[k]:
            fund = {w: (info.get(addr.get(w)) or {}).get("funder") for w in e["b_wallets"]}
            fc = collections.Counter(f for f in fund.values() if f and f not in hubs)
            cr = addr.get(e["creator"]) if e["creator"] is not None else None
            crf = (info.get(cr) or {}).get("funder") if cr else None
            linked = {x for x in (cr, crf) if x and x not in hubs}
            e["b_shared"] = int(any(n >= 2 for n in fc.values()) or any(f in linked for f in fund.values() if f))
            e["b_funding_known"] = (sum(1 for w in e["b_wallets"] if (info.get(addr.get(w)) or {}).get("status") in ("ok", "aktywny"))
                                    / len(e["b_wallets"]) if e["b_wallets"] else None)
            vals = [hold.get((e["mint"], addr.get(w), int(e["ts"]))) for w in e["b_wallets"]]
            known = [v[1] for v in vals if v and v[0] in ("ok", "po_t", "ok_inne_konto")]
            e["bundle_held_pct"] = (0.0 if not e["b_wallets"] else
                                    (sum(known) / 1e9 * 100 if len(known) == len(vals) else None))
        C.add_outcomes(sets[k])


# ------------------------------------------------------------------ raport
def bucket(x: float):
    for lo, hi in BUCKETS:
        if lo <= x < hi:
            return f"{lo}-{hi}%" if hi <= 100 else f"{lo}%+"
    return None


def blabel(lo, hi):
    return f"{lo}-{hi}%" if hi <= 100 else f"{lo}%+"


def bucket_table(ents: list[dict], key: str, split_dev: bool = False) -> tuple[str, dict]:
    ex, te = C.split_time(ents)
    rows, stats = [], {}
    for lo, hi in BUCKETS:
        for lbl, s in (("eksploracja", ex), ("TEST", te)):
            ss = [e for e in s if e.get(key) is not None and lo <= e[key] < hi]
            stats[(blabel(lo, hi), lbl)] = ss
            if not ss:
                rows.append([blabel(lo, hi), lbl, "0", "—", "—", "—", "—"])
                continue
            rows.append([blabel(lo, hi), lbl, f"{len(ss)}{C.rel(len(ss))}", C.pct(C.mean([e['s0'] for e in ss])),
                         C.pct(C.mean([e['s6'] for e in ss])), f"{C.mean([e['rug'] for e in ss]):.0%}",
                         C.pct(C.median([e['mfe'] for e in ss]), 0)])
        if split_dev and lo == 0:
            for lbl, s in (("eksploracja", ex), ("TEST", te)):
                for name, cond in (("  w tym: dev sam kupił >= 40% w slocie 0", lambda e: e["dev_alone_pct"] >= 40),
                                   ("  w tym: normalny start", lambda e: e["dev_alone_pct"] < 40)):
                    ss = [e for e in s if e.get(key) is not None and e[key] < hi and cond(e)]
                    if ss:
                        rows.append([name, lbl, f"{len(ss)}{C.rel(len(ss))}", C.pct(C.mean([e['s0'] for e in ss])),
                                     C.pct(C.mean([e['s6'] for e in ss])), f"{C.mean([e['rug'] for e in ss]):.0%}",
                                     C.pct(C.median([e['mfe'] for e in ss]), 0)])
    rows += C.ref_rows([e for e in ex if e.get(key) is not None], [e for e in te if e.get(key) is not None])
    return C.table(["kubełek", "zbiór", "N", "śr. wynik (obecne wyjście)", "śr. wynik (S6)", "% rugów (e)",
                    "mediana max zysku 6 h"], rows), stats


def quad_fit(xs, ys):
    """y = a + b x + c x^2 (najmniejsze kwadraty, x w %); zwraca (a, b, c, wierzchołek)."""
    n = len(xs)
    if n < 5:
        return None
    sx = [sum(x ** k for x in xs) for k in range(5)]
    sy = [sum(y * x ** k for x, y in zip(xs, ys)) for k in range(3)]
    m = [[sx[i + j] for j in range(3)] + [sy[i]] for i in range(3)]
    for i in range(3):
        p = max(range(i, 3), key=lambda r: abs(m[r][i]))
        m[i], m[p] = m[p], m[i]
        if abs(m[i][i]) < 1e-12:
            return None
        for r in range(3):
            if r != i:
                f = m[r][i] / m[i][i]
                m[r] = [a - f * b for a, b in zip(m[r], m[i])]
    a, b, c = (m[i][3] / m[i][i] for i in range(3))
    return a, b, c, (-b / (2 * c) if c else None)


def spearman(xs, ys) -> float:
    def ranks(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    if len(xs) < 3:
        return float("nan")
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def shape(ents: list[dict], key: str, ycol: str = "s0") -> tuple[str, str]:
    """Kształt zależności wynik ~ cecha: kubełki + Spearman + parabola, osobno eksploracja i TEST."""
    ex, te = C.split_time([e for e in ents if e.get(key) is not None])
    out, verdicts = [], []
    for lbl, s in (("eksploracja", ex), ("TEST", te)):
        xs, ys = [e[key] for e in s], [e[ycol] for e in s]
        q = quad_fit(xs, ys)
        rho = spearman(xs, ys)
        means = []
        for lo, hi in BUCKETS:
            v = [e[ycol] for e in s if lo <= e[key] < hi]
            means.append(C.mean(v) if len(v) >= 10 else None)
        ok = [m for m in means if m is not None]
        inner = means[1:4]
        inv_u = (q is not None and q[2] < 0 and q[3] is not None and 10 <= q[3] <= 40 and
                 any(m is not None for m in inner) and len(ok) >= 3 and
                 max((m for m in inner if m is not None), default=-9) > max(means[0] or -9, means[-1] or -9))
        lin_down = rho < -0.1 and not inv_u
        v = "odwrócone U" if inv_u else ("spadek (im więcej, tym gorzej)" if lin_down else
                                         ("wzrost" if rho > 0.1 else "brak związku"))
        verdicts.append(v)
        out.append(f"- {lbl} (N {len(s)}{C.rel(len(s))}): Spearman {rho:+.2f}; parabola " +
                   (f"c = {q[2] * 1e4:+.2f}e-4, wierzchołek {q[3]:.0f}%" if q and q[3] is not None else "—") +
                   "; średnie kubełków (N >= 10): " + ", ".join(f"{blabel(lo, hi)} {C.pct(m)}" if m is not None else
                                                                 f"{blabel(lo, hi)} —" for (lo, hi), m in zip(BUCKETS, means)) +
                   f" -> **{v}**")
    return "\n".join(out), (verdicts[0] if verdicts[0] == verdicts[1] else f"eksploracja: {verdicts[0]}, TEST: {verdicts[1]}")


def best_range(ex: list[dict], key: str, ycol: str) -> tuple[float, float] | None:
    """Najlepszy ciągły przedział kubełków na EKSPLORACJI (min. 30 wejść) - jedyny dobór progu."""
    best = None
    for i in range(len(BUCKETS)):
        for j in range(i, len(BUCKETS)):
            lo, hi = BUCKETS[i][0], BUCKETS[j][1]
            v = [e[ycol] for e in ex if lo <= e[key] < hi]
            if len(v) >= C.MIN_N and len(v) < len(ex) and (best is None or C.mean(v) > best[0]):
                best = (C.mean(v), lo, hi)
    return (best[1], best[2]) if best else None


def report() -> str:
    sets = build()
    finish(sets)
    out = ["## 8. Bundlery (zakupy wielu portfeli w bloku startu)\n", "Definicje" + (__doc__ or "").split("Definicje", 1)[1]]
    mig, bot = sets["mig"], sets["bot"]
    ma = [e for e in mig if e["assessable"]]
    ba = [e for e in bot if e["assessable"]]
    out.append(f"\n**Ile tokenów da się ocenić:** migracje + 30 min: {len(ma)} z {len(mig)} (reszta: dziura w danych zbieracza "
               f"przy starcie); wejścia bota: {len(ba)} z {len(sets['bot_all'])} (pozostałe to tokeny sprzed startu zbieracza "
               f"04.10 10:23 albo spoza pump.fun). Saldo bundlerów w chwili decyzji znane dla "
               f"{sum(1 for e in ma if e['bundle_held_pct'] is not None)} migracji i {sum(1 for e in ba if e['bundle_held_pct'] is not None)} wejść bota.\n")
    rows = []
    for lbl, s in (("migracje + 30 min", ma), ("wejścia bota", ba)):
        if not s:
            continue
        wb = [e for e in s if e["b_n"]]
        rows.append([lbl, f"{len(s)}", f"{len(wb) / len(s):.0%}", f"{C.median([e['b_n'] for e in wb]) if wb else 0:.0f}",
                     f"{C.mean([e['bundle_start_pct'] for e in wb]):.1f}%" if wb else "—",
                     f"{C.mean([e['b_slot0_pct'] / e['bundle_start_pct'] for e in wb if e['bundle_start_pct'] > 0]):.0%}" if wb else "—",
                     f"{C.mean([e['b_shared'] for e in wb]):.0%}" if wb else "—",
                     f"{C.mean([e['creator_in_bundle'] for e in wb]):.0%}" if wb else "—",
                     f"{C.mean([e['dev_alone_pct'] >= 40 for e in s]):.0%}"])
    out.append(C.table(["zbiór", "tokenów", "z bundlem", "mediana portfeli bundla", "śr. % podaży w bundlu (gdy jest)",
                        "z tego slot 0", "wspólny zasilający", "twórca w bundlu", "dev sam kupił >= 40% w slocie 0"], rows))
    for key, title in (("bundle_start_pct", "(a) % podaży kupionej w bundlach przy starcie"),
                       ("bundle_held_pct", "(b) % podaży, który bundlerzy NADAL trzymają w chwili decyzji")):
        for lbl, s in (("migracje + 30 min", ma), ("wejścia bota", ba)):
            s = [e for e in s if e.get(key) is not None]
            if len(s) < 20:
                out.append(f"\n**{title} - {lbl}:** za mało tokenów ({len(s)}).\n")
                continue
            tbl, _ = bucket_table(s, key, split_dev=(key == "bundle_start_pct"))
            out.append(f"\n**{title} - {lbl}** (N {len(s)}):\n")
            out.append(tbl)
            txt, verdict = shape(s, key)
            out.append("\nKształt zależności (wynik obecnego wyjścia ~ cecha):\n" + txt)
            out.append(f"\n**Kształt: {verdict}.**")
            if lbl.startswith("migracje"):
                ex, _ = C.split_time(s)
                rows = []
                tag = "bundle " + title.split(" ")[0]
                for ycol, yname in (("s0", "obecne wyjście"), ("s6", "S6")):
                    for (lo, hi), nm in (((20, 30), "hipoteza: 20-30% opłacalne"), ((0, 35), "hipoteza: unikaj >= 35%")):
                        rows.append(C.filter_eval(f"{tag} {nm} ({yname})", s,
                                                  lambda e, lo=lo, hi=hi, key=key: lo <= e[key] < hi, ycol))
                    rng = best_range(ex, key, ycol)
                    if rng:
                        rows.append(C.filter_eval(f"{tag} najlepszy przedział z eksploracji {blabel(*rng)} ({yname})", s,
                                                  lambda e, rng=rng, key=key: rng[0] <= e[key] < rng[1], ycol))
                out.append("\n" + C.table(C.FILTER_HEAD, rows))
    # wspólny zasilający w bundlu
    rows = []
    for lbl, s in (("eksploracja", C.split_time(ma)[0]), ("TEST", C.split_time(ma)[1])):
        for name, cond in (("bundle >= 10%, wspólny zasilający", lambda e: e["bundle_start_pct"] >= 10 and e["b_shared"]),
                           ("bundle >= 10%, bez wspólnego", lambda e: e["bundle_start_pct"] >= 10 and not e["b_shared"]),
                           ("bundle < 10%", lambda e: e["bundle_start_pct"] < 10)):
            ss = [e for e in s if cond(e)]
            if ss:
                rows.append([name, lbl, f"{len(ss)}{C.rel(len(ss))}", C.pct(C.mean([e['s0'] for e in ss])),
                             C.pct(C.mean([e['s6'] for e in ss])), f"{C.mean([e['rug'] for e in ss]):.0%}"])
    out.append("\n**Flaga wspólnego zasilającego w bundlu (migracje + 30 min):**\n")
    out.append(C.table(["grupa", "zbiór", "N", "śr. wynik (obecne)", "śr. wynik (S6)", "% rugów"], rows))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "report"])
    ap.add_argument("--rps", type=float, default=3)
    ap.add_argument("--pending", action="store_true", help="fetch: migracje bez świec (jeszcze się pobierają)")
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.rps, a.pending)
    else:
        print(report())


if __name__ == "__main__":
    main()
