"""9. COPY COINY - token z tym samym tickerem lub nazwą (albo tą samą grafiką) co wcześniejszy token.

    python -m analizy.copycoins fetch [--rps 2]   # grafiki i program tokena: Helius DAS getAssetBatch (10 kredytów/1000)
    python -m analizy.copycoins report

METADANE - co jest w danych:
  * nazwa i ticker: TAK, za darmo - zbieracz (data/stream.db, tabela mints, od 04.10 10:23) i bot (data/bot.db, tabela
    launches z PumpPortal, od 01.10 20:23; oba z nocnymi przerwami, gdy komputer jest wyłączony);
  * grafika: NIE ma w danych - pobrana z Helius DAS (getAssetBatch: 10 kredytów za zapytanie do 1000 tokenów, czyli
    ~1 300 kredytów za wszystkie ~130 tys. startów). Adres IPFS zawiera CID = hash treści pliku, więc ten sam CID = ten
    sam plik graficzny (nie trzeba pobierać obrazków); grafiki z CDN Axiom mają w nazwie mint tokena, z którego
    skopiowano grafikę (funkcja "kopiuj token" w terminalu).
DEFINICJE (ustalone przed patrzeniem na wyniki):
  kopia = wcześniejszy token z tym samym znormalizowanym tickerem LUB nazwą (małe litery, tylko litery i cyfry - bez
          spacji, emoji i znaków) wystartowany w ciągu 60 h przed startem tokena. 60 h zamiast 7 dni: tyle historii mamy
          dla KAŻDEGO ocenianego tokena (dane od 01.10 20:23) - jedno okno dla wszystkich, żeby eksploracja i test były
          porównywalne. Nocne przerwy w danych gubią część oryginałów -> część kopii trafia do "oryginałów" (to zaciera
          różnice, nie tworzy fałszywych).
  (c) oryginał          - brak wcześniejszego tokena z tym tickerem/nazwą w oknie,
  (a) kopia AKTYWNEGO   - któryś wcześniejszy token w chwili startu kopii: zmigrował w ostatnich 24 h ALBO miał >= 10 SOL
                          obrotu na krzywej w ostatnich 24 h ALBO bot widział go z obrotem 24 h >= $50k (DexScreener),
  (b) kopia MARTWEGO    - pozostałe kopie.
  numer kopii = 1 + liczba wcześniejszych tokenów z tym tickerem/nazwą w oknie (1 = oryginał).
  ta sama grafika = ten sam CID/adres grafiki co wcześniejszy token w oknie (niezależnie od nazwy).
"""
from __future__ import annotations

import argparse
import bisect
import collections
import json
import re
import time

from analizy import common as C

LOOKBACK_H = 60
ACTIVE_SOL = 10.0
ACTIVE_VOL_USD = 50_000
DAY = 86400
ASSET_SCHEMA = """CREATE TABLE IF NOT EXISTS asset(mint TEXT PRIMARY KEY, program TEXT, image TEXT, image_key TEXT,
  image_ref TEXT, name TEXT, symbol TEXT, ts REAL);"""
_CID = re.compile(r"(Qm[1-9A-HJ-NP-Za-km-z]{44}|baf[a-z2-7]{50,})")
_MINT = re.compile(r"/([1-9A-HJ-NP-Za-km-z]{32,44})(?:\.[a-z]+)?(?:$|\?)")


def cache():
    from analizy.crash_gap import cache as cg_cache
    db = cg_cache()
    db.executescript(ASSET_SCHEMA)
    return db


def norm(s) -> str | None:
    if not s:
        return None
    n = "".join(ch for ch in str(s).lower() if ch.isalnum())
    return n or None


def image_key(url: str | None) -> tuple[str | None, str | None]:
    if not url:
        return None, None
    m = _CID.search(url)
    ref = _MINT.search(url.split("ipfs/")[-1] if "ipfs/" in url else url)
    ref_mint = ref.group(1) if ref and not _CID.fullmatch(ref.group(1)) else None
    return (m.group(1) if m else url.split("?")[0]), ref_mint


# ------------------------------------------------------------------ wszechświat startów
def universe() -> dict[str, dict]:
    import rug_dataset as rd
    toks: dict[str, dict] = {}
    for mint, name, sym, cts, mid in rd.ro(rd.STREAM_DB).execute(
            "SELECT mint, name, symbol, created_ts, id FROM mints WHERE created_ts IS NOT NULL"):
        toks[mint] = {"mint": mint, "name": name, "sym": sym, "t": float(cts), "mint_id": mid}
    for mint, ts, sym, name in C.ro("bot.db").execute("SELECT mint, ts, symbol, name FROM launches"):
        if mint in toks:
            toks[mint]["t"] = min(toks[mint]["t"], ts)
        else:
            toks[mint] = {"mint": mint, "name": name, "sym": sym, "t": float(ts), "mint_id": None}
    for d in toks.values():
        d["nsym"], d["nname"] = norm(d["sym"]), norm(d["name"])
    return toks


def fetch(rps: float):
    import rug_funding as rf
    toks = universe()
    db = cache()
    have = {r[0] for r in db.execute("SELECT mint FROM asset")}
    todo = sorted(m for m in toks if m not in have)
    print(f"tokenów {len(toks)}, do pobrania grafik {len(todo)} (~{(len(todo) + 999) // 1000 * 10} kredytów)", flush=True)
    import threading
    from concurrent.futures import ThreadPoolExecutor
    local = threading.local()

    def get(ch):                    # jedno zapytanie (1000 tokenów) trwa ~50 s po stronie serwera - 4 naraz
        if not hasattr(local, "h"):
            local.h = rf.Helius(rps)
        return ch, local.h.call("getAssetBatch", {"ids": ch})

    chunks = [todo[i:i + 1000] for i in range(0, len(todo), 1000)]
    done = 0
    with ThreadPoolExecutor(4) as pool:
        results = pool.map(get, chunks)
        for ch, r in results:
            done += len(ch)
            if r is None:
                print(f"błąd zapytania ({len(ch)} tokenów) - uruchom ponownie, pobierze brakujące", flush=True)
                continue
            store(db, ch, r)
            print(f"{time.strftime('%H:%M:%S')} {done}/{len(todo)}", flush=True)


def store(db, ch: list, r: list) -> None:
    rows = []
    for m, a in zip(ch, r):
        a = a or {}
        content = a.get("content") or {}
        img = (content.get("links") or {}).get("image") or next((f.get("uri") for f in content.get("files") or []
                                                                  if f.get("uri")), None)
        key, ref = image_key(img)
        md = content.get("metadata") or {}
        rows.append((m, (a.get("token_info") or {}).get("token_program"), img, key, ref, md.get("name"),
                     md.get("symbol"), time.time()))
    db.executemany("INSERT OR REPLACE INTO asset VALUES(?,?,?,?,?,?,?,?)", rows)
    db.commit()


# ------------------------------------------------------------------ aktywność wcześniejszych tokenów
def activity(toks: dict, pred_mints: set) -> dict:
    """mint -> {'mig': czas migracji, 'vol': {godzina: SOL na krzywej}, 'dex': [(ts, vol_h24 $)]}"""
    import rug_dataset as rd
    out = {m: {"mig": None, "vol": collections.Counter(), "dex": []} for m in pred_mints}
    stream = rd.ro(rd.STREAM_DB)
    for mid, ts in stream.execute("SELECT m.mint, MIN(e.ts) FROM events e JOIN mints m ON m.id=e.mint_id "
                                  "WHERE e.kind='migrate' GROUP BY e.mint_id"):
        if mid in out:
            out[mid]["mig"] = ts
    for m, ts in C.ro("bot.db").execute("SELECT mint, ts FROM migrations"):
        if m in out and (out[m]["mig"] is None or ts < out[m]["mig"]):
            out[m]["mig"] = ts
    ids = {toks[m]["mint_id"]: m for m in pred_mints if toks.get(m, {}).get("mint_id")}
    lst = sorted(ids)
    for i in range(0, len(lst), 800):
        ch = lst[i:i + 800]
        q = (f"SELECT mint_id, ts / 3600, SUM(sol) FROM trades WHERE ts < 2000000000 AND mint_id IN "
             f"({','.join(map(str, ch))}) GROUP BY mint_id, ts / 3600")
        for mid, hr, sol in stream.execute(q):
            out[ids[mid]]["vol"][int(hr)] += (sol or 0) / 1e9
    pm = sorted(pred_mints)
    bot = C.ro("bot.db")
    for i in range(0, len(pm), 500):
        ch = pm[i:i + 500]
        for m, ts, f in bot.execute(f"SELECT mint, ts, features FROM decisions WHERE mint IN ({','.join('?' * len(ch))})", ch):
            try:
                v = (json.loads(f or "{}") or {}).get("vol_h24")
            except ValueError:
                v = None
            if v:
                out[m]["dex"].append((ts, float(v)))
    return out


def is_active(a: dict, t: float) -> bool:
    if a["mig"] is not None and t - DAY <= a["mig"] < t:
        return True
    h1 = int(t // 3600)
    if sum(a["vol"].get(h, 0.0) for h in range(h1 - 24, h1)) >= ACTIVE_SOL:
        return True
    return any(t - DAY <= ts < t and v >= ACTIVE_VOL_USD for ts, v in a["dex"])


# ------------------------------------------------------------------ klasyfikacja zbiorów
def classify(ents: list[dict], toks: dict) -> None:
    by_sym, by_name, by_img = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    db = cache()
    img = {r[0]: (r[1], r[2]) for r in db.execute("SELECT mint, image_key, image_ref FROM asset")}
    for d in toks.values():
        if d["nsym"]:
            by_sym[d["nsym"]].append((d["t"], d["mint"]))
        if d["nname"]:
            by_name[d["nname"]].append((d["t"], d["mint"]))
        k = (img.get(d["mint"]) or (None, None))[0]
        if k:
            by_img[k].append((d["t"], d["mint"]))
    for idx in (by_sym, by_name, by_img):
        for v in idx.values():
            v.sort()
    lb = LOOKBACK_H * 3600

    def window(lst, t):
        return lst[bisect.bisect_left(lst, (t - lb, "")):bisect.bisect_left(lst, (t, ""))]

    preds_all = set()
    for e in ents:
        d = toks.get(e["mint"])
        e["copy_known"] = d is not None
        if not d:
            continue
        t = d["t"]
        pr = {m for _, m in window(by_sym.get(d["nsym"], []), t) if m != e["mint"]} | \
             {m for _, m in window(by_name.get(d["nname"], []), t) if m != e["mint"]}
        k, ref = img.get(e["mint"], (None, None))
        e["img_known"] = k is not None
        e["img_preds"] = {m for _, m in window(by_img.get(k, []), t) if m != e["mint"]} if k else set()
        e["img_ref"] = ref if ref and ref != e["mint"] else None
        e["preds"], e["created_t"] = pr, t
        preds_all |= pr
    act = activity(toks, preds_all)
    cnt = collections.Counter(int(d["t"] // 600) for d in toks.values())
    for e in ents:
        if not e.get("copy_known"):
            continue
        b1 = int(e["created_t"] // 600)              # pokrycie danymi 6 h przed startem (>= 30 startów / 10 min)
        e["cov6"] = sum(1 for b in range(b1 - 36, b1) if cnt.get(b, 0) >= 30) / 36
        pr = e["preds"]
        e["copy_n"] = 1 + len(pr)
        e["copy_active"] = int(any(is_active(act[m], e["created_t"]) for m in pr))
        e["copy_cat"] = "c oryginał" if not pr else ("a kopia aktywnego" if e["copy_active"] else "b kopia martwego")
        e["is_copy"] = int(bool(pr))
        e["img_copy"] = int(bool(e["img_preds"]))


def nbucket(n: int) -> str:
    return "1 (oryginał)" if n == 1 else ("2" if n == 2 else ("3" if n == 3 else ("4-9" if n < 10 else "10+")))


def coverage(toks: dict, ents: list[dict]) -> float:
    """Średni odsetek 10-min przedziałów okna 60 h, w których mamy dane o startach (>= 30 startów)."""
    cnt = collections.Counter(int(d["t"] // 600) for d in toks.values())
    covs = []
    for e in ents:
        if e.get("copy_known"):
            b1 = int(e["created_t"] // 600)
            bs = range(b1 - LOOKBACK_H * 6, b1)
            covs.append(sum(1 for b in bs if cnt.get(b, 0) >= 30) / len(bs))
    return C.mean(covs)


def report() -> str:
    toks = universe()
    mig = C.migration_entries(30)
    bot = [e for e in C.bot_entry_set()]
    classify(mig + bot, toks)
    C.add_outcomes(mig + bot)
    t_min = min(d["t"] for d in toks.values())
    bot = [e for e in bot if e.get("copy_known") and e["created_t"] >= t_min + LOOKBACK_H * 3600]
    mig = [e for e in mig if e.get("copy_known")]
    db = cache()
    n_img = db.execute("SELECT COUNT(*), SUM(image_key IS NOT NULL) FROM asset").fetchone()
    out = ["## 9. Copy coiny (kopie tickera / nazwy / grafiki)\n", "METADANE" + (__doc__ or "").split("METADANE", 1)[1],
           f"\nW danych: {len(toks):,} startów z nazwą/tickerem (zbieracz + bot); grafika pobrana dla {n_img[0]:,} "
           f"(z adresem grafiki {n_img[1] or 0:,}). Średnie pokrycie okna 60 h danymi o startach: migracje "
           f"{coverage(toks, mig):.0%}, wejścia bota {coverage(toks, bot):.0%} (reszta = noce bez danych).\n"]
    rows = []
    for lbl, s in (("migracje + 30 min", mig), ("wejścia bota (tokeny z pełnym oknem)", bot)):
        if not s:
            continue
        cats = collections.Counter(e["copy_cat"] for e in s)
        rows.append([lbl, f"{len(s)}", f"{cats['c oryginał'] / len(s):.0%}", f"{cats['a kopia aktywnego'] / len(s):.0%}",
                     f"{cats['b kopia martwego'] / len(s):.0%}", f"{C.median([e['copy_n'] for e in s if e['is_copy']]):.0f}",
                     f"{C.mean([e['img_copy'] for e in s if e.get('img_known')]):.0%}",
                     f"{C.mean([bool(e['img_ref']) for e in s if e.get('img_known')]):.0%}"])
    out.append(C.table(["zbiór", "tokenów", "oryginały (c)", "kopie aktywnego (a)", "kopie martwego (b)",
                        "mediana numeru kopii", "ta sama grafika co wcześniejszy", "grafika z CDN z mintem innego tokena"], rows))
    for lbl0, s in (("migracje + 30 min", mig), ("wejścia bota", bot)):
        if len(s) < 20:
            continue
        ex, te = C.split_time(s)
        rows = []
        for cat in ("c oryginał", "a kopia aktywnego", "b kopia martwego"):
            for lbl, ss0 in (("eksploracja", ex), ("TEST", te)):
                ss = [e for e in ss0 if e["copy_cat"] == cat]
                rows.append([cat, lbl, f"{len(ss)}{C.rel(len(ss))}", C.pct(C.mean([e['s0'] for e in ss])),
                             C.pct(C.mean([e['s6'] for e in ss])), f"{C.mean([e['rug'] for e in ss]):.0%}" if ss else "—",
                             C.pct(C.median([e['mfe'] for e in ss]), 0)])
        rows += C.ref_rows(ex, te)
        out.append(f"\n**Oryginały vs kopie - {lbl0}** (N {len(s)}):\n")
        out.append(C.table(["kategoria", "zbiór", "N", "śr. wynik (obecne wyjście)", "śr. wynik (S6)", "% rugów (e)",
                            "mediana max zysku 6 h"], rows))
        full = [e for e in s if e.get("cov6", 0) >= 0.9]
        if len(full) >= 30:
            fx, ft = C.split_time(full)
            rows = []
            for cat in ("c oryginał", "a kopia aktywnego", "b kopia martwego"):
                for lbl, ss0 in (("eksploracja", fx), ("TEST", ft)):
                    ss = [e for e in ss0 if e["copy_cat"] == cat]
                    rows.append([cat, lbl, f"{len(ss)}{C.rel(len(ss))}", C.pct(C.mean([e['s0'] for e in ss])),
                                 f"{C.mean([e['rug'] for e in ss]):.0%}" if ss else "—"])
            out.append(f"\nOdporność na dziury w danych: tylko tokeny z pełnymi danymi o startach w 6 h przed startem "
                       f"(kopia zwykle pojawia się w mediana < 1 h po poprzedniku) - N {len(full)}:\n")
            out.append(C.table(["kategoria", "zbiór", "N", "śr. wynik (obecne wyjście)", "% rugów"], rows))
        rows = []
        for nb in ("1 (oryginał)", "2", "3", "4-9", "10+"):
            for lbl, ss0 in (("eksploracja", ex), ("TEST", te)):
                ss = [e for e in ss0 if nbucket(e["copy_n"]) == nb]
                if ss:
                    rows.append([nb, lbl, f"{len(ss)}{C.rel(len(ss))}", C.pct(C.mean([e['s0'] for e in ss])),
                                 f"{C.mean([e['rug'] for e in ss]):.0%}"])
        out.append(f"\n**Numer kopii - {lbl0}:**\n")
        out.append(C.table(["numer kopii", "zbiór", "N", "śr. wynik", "% rugów"], rows))
        rows = []
        for lbl, ss0 in (("eksploracja", ex), ("TEST", te)):
            for name, cond in (("ta sama grafika co wcześniejszy token", lambda e: e.get("img_copy")),
                               ("grafika z CDN z mintem innego tokena", lambda e: bool(e.get("img_ref"))),
                               ("grafika własna", lambda e: e.get("img_known") and not e.get("img_copy") and not e.get("img_ref"))):
                ss = [e for e in ss0 if cond(e)]
                if ss:
                    rows.append([name, lbl, f"{len(ss)}{C.rel(len(ss))}", C.pct(C.mean([e['s0'] for e in ss])),
                                 f"{C.mean([e['rug'] for e in ss]):.0%}"])
        out.append(f"\n**Grafika - {lbl0}:**\n")
        out.append(C.table(["grupa", "zbiór", "N", "śr. wynik", "% rugów"], rows))
        if lbl0.startswith("migracje"):
            rows = []
            for ycol, yname in (("s0", "obecne wyjście"), ("s6", "S6")):
                rows.append(C.filter_eval(f"copy: nie kupuj kopii AKTYWNEGO (a) ({yname})", s,
                                          lambda e: e["copy_cat"] != "a kopia aktywnego", ycol))
                rows.append(C.filter_eval(f"copy: nie kupuj kopii MARTWEGO (b) ({yname})", s,
                                          lambda e: e["copy_cat"] != "b kopia martwego", ycol))
                rows.append(C.filter_eval(f"copy: tylko oryginały (c) ({yname})", s,
                                          lambda e: e["copy_cat"] == "c oryginał", ycol))
                rows.append(C.filter_eval(f"copy: nie kupuj tej samej grafiki ({yname})", s,
                                          lambda e: not e.get("img_copy") and not e.get("img_ref"), ycol))
            out.append("\n**Filtry (hipoteza: kopie wypadają gorzej i warto ich nie kupować):**\n")
            out.append(C.table(C.FILTER_HEAD, rows))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "report"])
    ap.add_argument("--rps", type=float, default=2)
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.rps)
    else:
        print(report())


if __name__ == "__main__":
    main()
