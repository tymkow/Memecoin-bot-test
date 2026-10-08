"""Skąd powracający dumperzy mieli tokeny (6.10.2026)? Dla top-10 dumperów (po 3 rugi, najspokojniejsze pule):
transakcje puli od migracji do krachu (Helius), pierwsza transakcja, w której saldo tokena dumpera rośnie:
kupno z puli (spada saldo puli) albo przelew od innego właściciela. Tylko odczyt baz bota."""
import collections
import json
import sqlite3
import sys

BOT = r"."
sys.path.insert(0, BOT)
import rug_funding as rf  # noqa: E402

r = sqlite3.connect(f"file:{BOT}\\data\\rug_data.db?mode=ro", uri=True)
dump = r.execute("SELECT mint, wallet, sold_pct, crash_ts FROM dumpers").fetchall()
mig = {m: t for m, t in r.execute("SELECT mint, t FROM samples WHERE offset_min=0")}
pool = dict(r.execute("SELECT mint, pool FROM pools"))
ntx = dict(r.execute("SELECT mint, n_tx FROM dump_status"))
cnt = collections.Counter(w for _, w, _, _ in dump)
h = rf.Helius(8)


def deltas(tx, mint):
    d = collections.defaultdict(float)
    meta = (tx or {}).get("meta") or {}
    if meta.get("err"):
        return {}
    for side, sign in (("preTokenBalances", -1), ("postTokenBalances", 1)):
        for b in meta.get(side) or []:
            if b.get("mint") == mint and b.get("owner"):
                ui = b.get("uiTokenAmount") or {}
                d[b["owner"]] += sign * float(ui.get("amount") or 0) / 10 ** int(ui.get("decimals") or 6)
    return d


out = []
for w, n in cnt.most_common(10):
    rugs = sorted([(m, ct) for m, ww, _, ct in dump if ww == w and m in mig], key=lambda x: ntx.get(x[0], 9e9))[:3]
    for m, ct in rugs:
        p, t0 = pool[m], mig[m]
        sigs, before, pages = [], None, 0
        while pages < 20:
            opts = {"limit": 1000}
            if before:
                opts["before"] = before
            res = h.call("getSignaturesForAddress", [p, opts])
            pages += 1
            if not res:
                break
            sigs += [x for x in res if x.get("blockTime") and t0 - 60 <= x["blockTime"] <= ct + 60 and not x.get("err")]
            if len(res) < 1000 or (res[-1].get("blockTime") or 0) < t0 - 60:
                break
            before = res[-1]["signature"]
        found = None
        for i, x in enumerate(sorted(sigs, key=lambda x: x["blockTime"])[:200]):
            tx = h.call("getTransaction", [x["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
            d = deltas(tx, m)
            if d.get(w, 0) > 0:
                src = [o for o, v in d.items() if v < 0 and o != w]
                how = "kupno z puli" if p in src else (f"przelew od {src[0][:6]}.." if src else "inne (np. krzywa przez router)")
                found = (how, x["blockTime"] - t0, d[w] / 1e9 * 100)
                break
        out.append((w, n, m, found, len(sigs), pages))
        f = found
        print(f"{w[:8]}.. ({n} rugów) token {m[:6]}..: " + (f"{f[0]}, {f[1]:+.0f} s od migracji, {f[2]:.2f}% podaży" if f else
              f"nie znaleziono w {min(len(sigs), 200)} transakcjach puli od migracji do krachu"), flush=True)
print(f"kredytów: {h.calls}")
json.dump(out, open("dumper_source.json", "w"), default=str)
