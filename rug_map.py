"""Mapy rugów (5.10.2026, pomysł użytkownika): KTO zrzucił token przy rugu, skąd miał pieniądze (łańcuch zasileń przez
pośredników) i czy ci sami ludzie / te same "rodziny" portfeli wracają w kolejnych tokenach.

    python rug_map.py dumpers [--rps 8]   # sprzedający w minucie krachu każdego ruga (transakcje puli PumpSwap, Helius)
    python rug_map.py trace [--rps 8]     # łańcuch zasileń do HOPS przeskoków: dumperzy, top kupujący, twórcy
    python rug_map.py all [--rps 8]       # dumpers + trace
    python rug_map.py report              # powtarzalność + test predykcji przy migracji (point-in-time)

Dumperzy: minuta krachu = pierwsza świeca po migracji, w której cena spadła do progu etykiety (RUG_SZYBKI 30% w 30 min,
RUG_PO_POMPIE 20% po pompie). Transakcje puli z okna [krach-2 min, krach+3 min] (getSignaturesForAddress puli wstecz od
dziś, getTransaction): sprzedający = WŁAŚCICIELE kont tokena, których saldo spadło (salda tokenów pokazują prawdziwego
właściciela, nie router, w odróżnieniu od TradeEvent na krzywej). Liczymy tych, którzy sprzedali >= 0.3% podaży.
Łańcuch zasileń: portfel -> kto go zasilił pierwszym przelewem -> kto zasilił tamtego ... (do HOPS); stop na portfelu
"aktywnym" (>= 3000 transakcji: giełdy, serwisy botów, ale też możliwe "główne" portfele oszustów - raport liczy oba
warianty). Predykcja: dla tokenu w chwili migracji t liczymy powiązania jego top kupujących i twórcy WYŁĄCZNIE z rugami,
których krach nastąpił przed t.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import time

import rug_backtest as rb
import rug_funding as rf
from rug_dataset import out_db

HOPS = 4
MIN_SOLD_PCT = 0.3          # % podaży sprzedany w oknie krachu, żeby uznać za dumpera
MAX_SIG_PAGES = 15
MAX_TX = 60


def db_():
    db = rf.wallet_db()
    db.execute("CREATE TABLE IF NOT EXISTS dump_status(mint TEXT PRIMARY KEY, label TEXT, crash_ts REAL, status TEXT, "
               "pages INTEGER, n_tx INTEGER, ts REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS dumpers(mint TEXT, wallet TEXT, sold_pct REAL, crash_ts REAL, "
               "PRIMARY KEY(mint, wallet))")
    return db


def all_samples() -> list[dict]:
    """Próbki z chwili migracji (+0) - także tokeny z dziurą w danych zbieracza (do map i powiązań wystarczą)."""
    db = out_db()
    out = []
    for r in db.execute("SELECT * FROM samples WHERE offset_min=0 ORDER BY t"):
        f = json.loads(r["features"])
        out.append({"mint": r["mint"], "t": r["t"], "label": r["label"], "y": r["fast_rug"], "f": f,
                    "sim": f.get("sim") or {}, "gap": f.get("gap", 0), "rug_any": r["label"] != "OK"})
    return out


def crash_time(db, mint: str, t: float, label: str) -> float | None:
    pool = db.execute("SELECT pool FROM pools WHERE mint=?", (mint,)).fetchone()
    if not pool or not pool[0]:
        return None
    cs = [list(c) for c in db.execute("SELECT ts,o,h,l,c,v FROM candles WHERE pool=? AND ts >= ? ORDER BY ts", (pool[0], int(t) - 60))]
    lab = rb.label(cs, t)
    if not lab:
        return None
    ref = lab["ref"]
    lvl = ref * (rb.FAST_DROP if label == "RUG_SZYBKI" else rb.LATE_DROP)
    pumped = label != "RUG_SZYBKI"
    seen_pump = False
    for c in cs:
        if c[0] <= t:          # minuta migracji: dołek to cena z krzywej przed kupnem snajperów, nie krach
            continue
        if pumped and c[2] >= ref * rb.PUMP:
            seen_pump = True
        if c[3] <= lvl and (seen_pump or not pumped):
            return float(c[0])
    return None


def sellers_in(tx: dict, mint: str, pool: str) -> dict[str, float]:
    """Właściciel -> tokeny sprzedane (spadek salda konta tokena) w jednej transakcji."""
    meta = (tx or {}).get("meta") or {}
    if meta.get("err"):
        return {}
    delta: dict[str, float] = collections.defaultdict(float)
    for side, sign in (("preTokenBalances", -1), ("postTokenBalances", 1)):
        for b in meta.get(side) or []:
            if b.get("mint") != mint or not b.get("owner"):
                continue
            ui = b.get("uiTokenAmount") or {}
            amt = float(ui.get("amount") or 0) / 10 ** int(ui.get("decimals") or 6)
            delta[b["owner"]] += sign * amt
    return {o: -d for o, d in delta.items() if d < 0 and o != pool}


def dumpers(rps: float):
    db = db_()
    h = rf.Helius(rps)
    done = {r[0] for r in db.execute("SELECT mint FROM dump_status WHERE status != 'blad'")}
    todo = [s for s in all_samples() if s["rug_any"] and s["mint"] not in done]
    print(f"rugów do zmapowania: {len(todo)}", flush=True)
    for i, s in enumerate(todo, 1):
        m = s["mint"]
        pool = db.execute("SELECT pool FROM pools WHERE mint=?", (m,)).fetchone()[0]
        ct = crash_time(db, m, s["t"], s["label"])
        status, pages, sigs = "ok", 0, []
        if ct is None:
            status = "brak_krachu"
        else:
            w0, w1 = ct - 120, ct + 180
            before = None
            while pages < MAX_SIG_PAGES:
                opts = {"limit": 1000}
                if before:
                    opts["before"] = before
                r = h.call("getSignaturesForAddress", [pool, opts])
                pages += 1
                if r is None:
                    status = "blad"
                    break
                sigs += [x for x in r if x.get("blockTime") and w0 <= x["blockTime"] <= w1 and not x.get("err")]
                if len(r) < 1000 or (r[-1].get("blockTime") or 0) < w0:
                    break
                before = r[-1]["signature"]
            else:
                status = "za_duzo"
        sold: dict[str, float] = collections.defaultdict(float)
        # najpierw minuta krachu, potem coraz dalej od niej (w ruchliwych pulach okno ma ponad 1000 transakcji)
        for x in sorted(sigs, key=lambda x: 0 if ct <= x["blockTime"] < ct + 60 else abs(x["blockTime"] - ct - 30))[:MAX_TX]:
            tx = h.call("getTransaction", [x["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
            for o, a in sellers_in(tx, m, pool).items():
                sold[o] += a
        for o, a in sold.items():
            pct = a / 1e9 * 100
            if pct >= MIN_SOLD_PCT:
                db.execute("INSERT OR REPLACE INTO dumpers VALUES(?,?,?,?)", (m, o, pct, ct))
        db.execute("INSERT OR REPLACE INTO dump_status VALUES(?,?,?,?,?,?,?)",
                   (m, s["label"], ct, status, pages, len(sigs), time.time()))
        db.commit()
        if i % 25 == 0:
            st = dict(db.execute("SELECT status, COUNT(*) FROM dump_status GROUP BY status").fetchall())
            n = db.execute("SELECT COUNT(*) FROM dumpers").fetchone()[0]
            print(f"{time.strftime('%H:%M:%S')} {i}/{len(todo)} {st} dumperów {n} kredytów {h.calls}", flush=True)
    print(f"dumpers: koniec, kredytów {h.calls}", flush=True)


def tops_all(samples: list[dict]) -> dict:
    return rf.holders_at(samples)            # top kupujący z krzywej + twórca (również tokeny z dziurą)


def trace(rps: float):
    db = db_()
    samples = all_samples()
    tops = tops_all(samples)
    seeds = {w for _, c, top in tops.values() for w in ([c] if c else []) + [a for a, _ in top]}
    seeds |= {r[0] for r in db.execute("SELECT wallet FROM dumpers")}
    h = rf.Helius(rps)
    info = {r["wallet"]: dict(r) for r in db.execute("SELECT * FROM wallet_funding")}
    frontier = set(seeds)
    for hop in range(HOPS):
        todo = [w for w in frontier if w not in info or info[w]["status"] == "blad"]
        print(f"przeskok {hop + 1}: portfeli {len(frontier)}, do sprawdzenia {len(todo)}", flush=True)
        for i, w in enumerate(todo, 1):
            r = rf.resolve(h, w)
            row = (w, r["status"], r.get("funder"), r.get("first_ts"), r.get("sig_times"), time.time())
            db.execute("INSERT OR REPLACE INTO wallet_funding VALUES(?,?,?,?,?,?)", row)
            info[w] = dict(zip(("wallet", "status", "funder", "first_ts", "sig_times", "ts"), row))
            if i % 200 == 0:
                db.commit()
                print(f"  {time.strftime('%H:%M:%S')} {i}/{len(todo)} kredytów {h.calls}", flush=True)
        db.commit()
        frontier = {info[w]["funder"] for w in frontier if info.get(w) and info[w].get("funder")
                    and info[w]["status"] == "ok"}
        if not frontier:
            break
    print(f"trace: koniec, kredytów {h.calls}", flush=True)


# ------------------------------------------------------------------ raport
def ancestors(w: str, info: dict, stop_active: bool) -> list[str]:
    """[portfel, zasilający, jego zasilający, ...] do HOPS; stop na portfelu aktywnym (wariant) albo nieznanym."""
    out, cur = [w], w
    for _ in range(HOPS):
        i = info.get(cur)
        if not i or not i.get("funder") or i["status"] != "ok":
            break
        nxt = i["funder"]
        j = info.get(nxt)
        if stop_active and (not j or j["status"] != "ok"):
            break                                  # zasilający "aktywny"/nieznany = giełda, serwis... - nie łączymy
        out.append(nxt)
        cur = nxt
    return out


def report(split: float = 0.6):
    db = db_()
    samples = all_samples()
    info = {r["wallet"]: dict(r) for r in db.execute("SELECT * FROM wallet_funding")}
    dump = collections.defaultdict(list)
    for m, w, pct, ct in db.execute("SELECT mint, wallet, sold_pct, crash_ts FROM dumpers"):
        dump[m].append((w, pct, ct))
    st = dict(db.execute("SELECT status, COUNT(*) FROM dump_status GROUP BY status").fetchall())
    rugs = sorted(((m, ws[0][2]) for m, ws in dump.items()), key=lambda x: x[1])
    print(f"rugi z mapą: statusy {st}; rugów z dumperami: {len(rugs)}, dumperów (token, portfel): "
          f"{sum(len(v) for v in dump.values())}, śr. na rug {statistics.mean(len(v) for v in dump.values()):.1f}")
    tops = tops_all(samples)

    # --- 1) powtarzalność: czy dumperzy / ich rodziny wracają w kolejnych rugach ---
    for stop_active in (True, False):
        seen_w: set = set()
        seen_anc: collections.Counter = collections.Counter()
        direct = family = 0
        for m, ct in rugs:
            ws = [w for w, _, _ in dump[m]]
            anc = {a for w in ws for a in ancestors(w, info, stop_active)}
            direct += any(w in seen_w for w in ws)
            family += any(a in seen_anc for a in anc)
            seen_w |= set(ws)
            seen_anc.update(anc)
        print(f"\n== 1) powtarzalność ({'stop na portfelach aktywnych' if stop_active else 'BEZ stopu na aktywnych'}) ==")
        print(f"  rugów, w których dumper był już dumperem we WCZEŚNIEJSZYM rugu: {direct}/{len(rugs)} ({direct / max(len(rugs), 1):.0%})")
        print(f"  rugów powiązanych rodziną (wspólny przodek <= {HOPS} przeskoki z wcześniejszym rugiem): "
              f"{family}/{len(rugs)} ({family / max(len(rugs), 1):.0%})")
        common = [(a, n) for a, n in seen_anc.most_common(8) if n >= 3]
        if common:
            print("  najczęstsze portfele/przodkowie w rugach (liczba rugów):",
                  ", ".join(f"{a[:6]}..({n}, {info.get(a, {}).get('status', '?')})" for a, n in common))

    # skąd dumperzy: czy kupowali na krzywej / są twórcą
    on_curve = creator = tot = 0
    for m, ws in dump.items():
        if m not in tops:
            continue
        t, c, top = tops[m]
        topw = {a for a, _ in top}
        for w, _, _ in ws:
            tot += 1
            on_curve += w in topw
            creator += w == c
    print(f"\n  dumperzy wśród top-{rf.TOP_N} kupujących z krzywej tego tokena: {on_curve}/{tot} ({on_curve / max(tot, 1):.0%}), "
          f"twórca: {creator}")

    # --- 2) predykcja przy migracji: powiązania z rugami, które wydarzyły się PRZED t ---
    cut = int(len(samples) * split)
    for stop_active in (True, False):
        print(f"\n== 2) predykcja przy migracji ({'stop na aktywnych' if stop_active else 'bez stopu'}); "
              f"trening = pierwsze {split:.0%} czasu, TEST = reszta ==")
        anc_cache: dict = {}

        def anc(w):
            if w not in anc_cache:
                anc_cache[w] = ancestors(w, info, stop_active)
            return anc_cache[w]
        events = sorted(((ct, w, m) for m, ws in dump.items() for w, _, ct in ws), key=lambda x: x[0])
        rows = []
        for s in samples:
            t, c, top = tops.get(s["mint"], (s["t"], None, []))
            past = [(w, m) for ct, w, m in events if ct < t and m != s["mint"]]
            past_w = {w for w, _ in past}
            past_anc = {a for w, _ in past for a in anc(w)}
            mine = ([c] if c else []) + [a for a, _ in top]
            f = {"rugger_direct": sum(w in past_w for w in mine),
                 "rugger_family": sum(any(a in past_anc for a in anc(w)) for w in mine),
                 "creator_rugger": int(bool(c) and any(a in past_anc for a in anc(c))),
                 "n_past_rugs": len({m for _, m in past})}
            rows.append(dict(s, f2=f))
        for part, rs in (("trening", rows[:cut]), ("TEST", rows[cut:])):
            print(f"  {part}: tokenów {len(rs)}, rug (szybki lub po pompie) {sum(r['rug_any'] for r in rs) / len(rs):.0%}, "
                  f"średnio wcześniejszych rugów w bazie {statistics.mean(r['f2']['n_past_rugs'] for r in rs):.0f}")
            for k in ("rugger_direct", "rugger_family", "creator_rugger"):
                pos = [r for r in rs if r["f2"][k] > 0]
                neg = [r for r in rs if r["f2"][k] == 0]
                if not pos:
                    print(f"    {k:<15} nikt nie ma powiązania")
                    continue
                aa = rb.auc([r["f2"][k] for r in rs if r["rug_any"]], [r["f2"][k] for r in rs if not r["rug_any"]])
                print(f"    {k:<15} z powiązaniem n={len(pos):>3}: rug {sum(r['rug_any'] for r in pos) / len(pos):.0%}, szybki "
                      f"{sum(r['y'] for r in pos) / len(pos):.0%}, wynik SL25 {rb._mean([r['sim'].get('SL25 (hybrid)') for r in pos]):+.1%} | "
                      f"bez n={len(neg):>3}: rug {sum(r['rug_any'] for r in neg) / max(len(neg), 1):.0%}, wynik "
                      f"{rb._mean([r['sim'].get('SL25 (hybrid)') for r in neg]):+.1%} | AUC {aa:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["dumpers", "trace", "all", "report"])
    ap.add_argument("--rps", type=float, default=8)
    a = ap.parse_args()
    if a.cmd in ("dumpers", "all"):
        dumpers(a.rps)
    if a.cmd in ("trace", "all"):
        trace(a.rps)
    if a.cmd == "report":
        report()


if __name__ == "__main__":
    main()
