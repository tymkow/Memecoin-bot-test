"""Wspólne narzędzia analiz (6.10.2026). Zasady użytkownika (obowiązkowe):
- podział CZASOWY: pierwsze 70% = eksploracja (tu dobieramy progi/warianty), ostatnie 30% = TEST (liczony raz);
  wniosek przyjmujemy tylko, jeśli trzyma się na teście;
- przy każdym wyniku N; N < 30 -> "niewiarygodny";
- zawsze porównanie z baseline = obecne reguły bota bez zmian;
- logika live bota nietknięta; bazy tylko do odczytu.

Zbiory:
  bot_entries()        wejścia bota (pozycje różnych portfeli w ten sam token w 10 min = jedno wejście) + świece
                       z archiwum + migawki ceny/płynności + faktyczne wyniki pozycji
  migration_entries()  migracje z data/rug_data.db (świece PumpSwap 6 h) - wejście X min po migracji, jeśli token
                       żyje (handel w ostatnich 5 min); baseline = wejście w KAŻDY żywy token z wyjściami bota
Etykieta wyniku tokena (potrójna bariera): od ceny wejścia, w 6 h: najpierw -70% -> "rug", najpierw +50% -> "pump",
żadne -> "nic". W tej samej świecy liczymy dołek przed szczytem (pesymistycznie, jak exit_research).
"""
from __future__ import annotations

import bisect
import math
import json
import random
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import exit_research as er  # noqa: E402
from config import Config  # noqa: E402

DATA = ROOT / "data"
CFG = Config()
SPLIT = 0.7
MIN_N = 30
H6 = 6 * 3600
UP, DOWN = 0.50, -0.70          # potrójna bariera


# ------------------------------------------------------------------ bazy (tylko odczyt)
def ro(name: str) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{DATA / name}?mode=ro", uri=True, timeout=120)   # zapisy w tle (Helius) blokują chwilowo
    c.row_factory = sqlite3.Row
    return c


# ------------------------------------------------------------------ statystyka i raport
def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else float("nan")


def median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else float("nan")


def rel(n: int) -> str:
    return "" if n >= MIN_N else " ⚠️ niewiarygodny"


def auc(pos, neg) -> float:
    if not pos or not neg:
        return float("nan")
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank, i, rs = 1, 0, 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        rs += (rank + rank + (j - i) - 1) / 2 * sum(1 for k in range(i, j) if allv[k][1])
        rank += j - i
        i = j
    return (rs - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def boot_ci(xs, n=2000, seed=1):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return float("nan"), float("nan")
    r = random.Random(seed)
    ms = sorted(statistics.mean(r.choices(xs, k=len(xs))) for _ in range(n))
    return ms[int(n * 0.025)], ms[int(n * 0.975)]


def max_drawdown(rets) -> float:
    """Największy spadek skumulowanego wyniku (w stawkach) przy wejściach w kolejności czasu."""
    peak = cum = dd = 0.0
    for r in rets:
        cum += r
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return dd


def split_time(items: list, key: str = "ts", frac: float = SPLIT):
    items = sorted(items, key=lambda x: x[key])
    cut = int(len(items) * frac)
    return items[:cut], items[cut:]


def pct(x, d=1):
    return "—" if x is None or x != x else f"{x * 100:+.{d}f}%"


def table(headers: list, rows: list) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# ------------------------------------------------------------------ wyjścia
def bot_exits(stop=0.25, **over) -> dict:
    """Obecne reguły wyjścia bota (config): SL, TP 50/100/300 po 1/3, trailing 20% po TP1, time stop 240 min."""
    d = dict(stop_frac=stop, tp=er.tp_plan(CFG.take_profit_levels), trail=CFG.trailing_stop_pct / 100,
             time_stop=(CFG.time_stop_minutes, CFG.time_stop_min_move_pct / 100), be_at=None)
    d.update(over)
    return d


def bot_entry_set() -> list[dict]:
    """JEDEN zestaw wejść bota dla części 3, 4 i 6 (6.10: część 3 brała tylko wejścia z >= 5 migawkami płynności -
    27 wykluczonych wejść to szybko umierające tokeny: -32% i 78% rugów, więc jej baseline był zawyżony o ~4 pp)."""
    return [e for e in bot_entries() if "path" in e]


class no_costs:
    """Symulacja BRUTTO: wyłącza koszty exit_research (wejście EC, wyjście XC) na czas bloku `with`."""
    def __init__(self, entry=True, exit_=True):
        self.entry, self.exit_ = entry, exit_

    def __enter__(self):
        self.saved = (er.EC, er.XC)
        er.EC = 0.0 if self.entry else er.EC
        er.XC = 0.0 if self.exit_ else er.XC

    def __exit__(self, *a):
        er.EC, er.XC = self.saved


def sim(path, ref, ts0, stop_frac=0.25, tp=None, trail=0.20, time_stop=(240, 0.10), be_at=None) -> float:
    return er.simulate(path, ref, ts0, stop=ref * (1 - stop_frac) if stop_frac is not None else None,
                       tp=tp if tp is not None else er.tp_plan(CFG.take_profit_levels), trail=trail,
                       time_stop=time_stop, be_at=be_at)[0]


def outcome3(path, ref) -> tuple[str, float, float]:
    """(etykieta, MFE, MAE) - potrójna bariera +50% / -70% w ścieżce."""
    for c in path:
        if c[3] <= ref * (1 + DOWN):
            lab = "rug"
            break
        if c[2] >= ref * (1 + UP):
            lab = "pump"
            break
    else:
        lab = "nic"
    return lab, max(c[2] for c in path) / ref - 1, min(c[3] for c in path) / ref - 1


# ------------------------------------------------------------------ zbiór: wejścia bota
def bot_entries(with_snaps: bool = True) -> list[dict]:
    db = ro("bot.db")
    fees = dict(db.execute("SELECT position_id, SUM(fee_usd) FROM trades GROUP BY position_id").fetchall())
    groups: list[dict] = []
    for p in db.execute("SELECT * FROM positions WHERE status='closed' ORDER BY opened_ts"):
        for g in groups:
            if g["mint"] == p["mint"] and abs(g["ts"] - p["opened_ts"]) < 600:
                g["pos"].append(p)
                break
        else:
            groups.append({"mint": p["mint"], "ts": p["opened_ts"], "sym": p["symbol"], "pos": [p]})
    out = []
    for g in groups:
        p0 = g["pos"][0]
        info = json.loads(p0["entry_info"] or "{}")
        pr = db.execute("SELECT pair FROM decisions WHERE mint=? AND pair IS NOT NULL ORDER BY ABS(ts-?) LIMIT 1",
                        (g["mint"], g["ts"])).fetchone()
        e = {"mint": g["mint"], "ts": g["ts"], "sym": g["sym"], "features": info.get("features") or {},
             "entry_liq": p0["entry_liq"], "entry_price": statistics.mean(p["entry_price"] for p in g["pos"]),
             "pos": [{"s": p["strategy"] or "hybrid", "pnl": p["realized_usd"] - p["cost_usd"],
                      "ret": p["realized_usd"] / p["cost_usd"] - 1, "fee": fees.get(p["id"], 0.0),
                      "reason": (p["exit_reason"] or "").replace("przerwa_", ""), "closed": p["closed_ts"],
                      "mae": p["mae_pct"], "mfe": p["mfe_pct"]} for p in g["pos"]]}
        if pr:
            cs = [list(c) for c in db.execute("SELECT ts,o,h,l,c,v FROM candles WHERE pool=? AND ts BETWEEN ? AND ? "
                                              "ORDER BY ts", (pr["pair"], int(g["ts"]) - 6000, int(g["ts"]) + H6))]
            pre = [c for c in cs if c[0] + 60 <= g["ts"]]
            path = [c for c in cs if c[0] + 60 > g["ts"]]
            if pre and path and 0.5 < e["entry_price"] / pre[-1][4] < 2:
                e.update(ref=pre[-1][4], path=path, pre=pre)
                e["label"], e["mfe"], e["mae"] = outcome3(path, pre[-1][4])
        if with_snaps:
            e["snaps"] = [tuple(r) for r in db.execute(
                "SELECT ts, price, liq FROM snapshots WHERE mint=? AND ts BETWEEN ? AND ? ORDER BY ts",
                (g["mint"], g["ts"] - 3600, g["ts"] + H6))]
        out.append(e)
    return out


# ------------------------------------------------------------------ zbiór: migracje
def migration_entries(offset_min: int = 30) -> list[dict]:
    import rug_dataset as rd
    db = ro("rug_data.db")
    stream = rd.ro(rd.STREAM_DB)
    migs = {m["mint"]: m for m in rd.migrations(stream)}
    out = []
    for m, pool in db.execute("SELECT mint, pool FROM pools WHERE status='ok'"):
        mg = migs.get(m)
        if not mg:
            continue
        cs = [list(c) for c in db.execute("SELECT ts,o,h,l,c,v FROM candles WHERE pool=? ORDER BY ts", (pool,))]
        t = mg["mig_ts"] + offset_min * 60
        alive = [c for c in cs if t - 300 <= c[0] <= t - 60]
        path = [c for c in cs if t + 10 <= c[0] <= mg["mig_ts"] + H6]
        if not alive or not path or path[0][1] <= 0:
            continue
        ref = path[0][1]
        lab, mfe, mae = outcome3(path, ref)
        out.append({"mint": m, "ts": t, "mig_ts": mg["mig_ts"], "created_ts": mg["created_ts"], "mint_id": mg["mint_id"],
                    "created_slot": mg["created_slot"], "creator": mg["creator"], "mayhem": mg["mayhem"],
                    "ref": ref, "path": path, "pre": [c for c in cs if c[0] + 60 <= t], "label": lab, "mfe": mfe,
                    "mae": mae, "pool": pool})
    return sorted(out, key=lambda e: e["ts"])


def migration_tokens() -> list[dict]:
    """Wszystkie migracje ze świecami (bez punktu wejścia): mint, mig_ts, pool, świece - do badań na całych ścieżkach."""
    import rug_dataset as rd
    db = ro("rug_data.db")
    migs = {m["mint"]: m for m in rd.migrations(rd.ro(rd.STREAM_DB))}
    out = []
    for m, pool in db.execute("SELECT mint, pool FROM pools WHERE status='ok'"):
        if m in migs:
            cs = [list(c) for c in db.execute("SELECT ts,o,h,l,c,v FROM candles WHERE pool=? ORDER BY ts", (pool,))]
            if len(cs) >= 5:
                out.append({"mint": m, "mig_ts": migs[m]["mig_ts"], "ts": migs[m]["mig_ts"], "pool": pool, "candles": cs})
    return sorted(out, key=lambda e: e["ts"])


def holes_overlap(holes: list, a: float, b: float) -> bool:
    i = bisect.bisect_left(holes, (a, a))
    for j in (i - 1, i):
        if 0 <= j < len(holes) and holes[j][0] < b and holes[j][1] > a:
            return True
    return any(h0 < b and h1 > a for h0, h1 in holes[max(0, i - 3):i + 3])


# ------------------------------------------------------------------ porównanie z random_eligible (zasada od 6.10)
_RE: dict = {}


def random_eligible_ref(t0: float, t1: float) -> dict:
    """random_eligible w oknie czasu [t0, t1): (1) FAKTYCZNE pozycje - wynik netto i brutto na pozycję (koszty bota),
    (2) SYMULACJA na jego wejściach - te same świece, wyjście i koszty co filtry w analizach (porównywalne 1:1)."""
    if "rows" not in _RE:
        from analizy import costs
        _RE["rows"] = [r for r in costs.real_rows() if r["s"] == "random_eligible"]
        _RE["ents"] = [e for e in bot_entry_set() if any(p["s"] == "random_eligible" for p in e["pos"])]
    live = [r for r in _RE["rows"] if t0 <= r["ts"] < t1]
    sims = [sim(e["path"], e["ref"], e["path"][0][0]) for e in _RE["ents"] if t0 <= e["ts"] < t1]
    return {"n_live": len(live), "net": mean([r["net"] / r["stake"] for r in live]),
            "gross": mean([r["gross"] / r["stake"] for r in live]), "n_sim": len(sims), "sim": mean(sims)}


def split_windows(ents: list[dict]):
    """Okna czasu eksploracji i TESTU danego zbioru (do porównania z random_eligible w tym samym okresie)."""
    ex, te = split_time(ents)
    return (ex[0]["ts"], te[0]["ts"]), (te[0]["ts"], te[-1]["ts"] + 1)


def re_cell(r: dict) -> str:
    return (f"sym. {pct(r['sim'])} (N {r['n_sim']}{rel(r['n_sim'])}); faktycznie netto {pct(r['net'])}, "
            f"brutto {pct(r['gross'])} (N {r['n_live']})")


def perm_p(keep: list, allv: list, n: int = 4000, seed: int = 7) -> float:
    """P(losowy podzbiór tej samej wielkości ma średnią >= filtr) - czy filtr bije LOSOWY wybór z tego samego zbioru."""
    keep = [x for x in keep if x is not None]
    allv = [x for x in allv if x is not None]
    if not keep or len(keep) >= len(allv):
        return float("nan")
    r = random.Random(seed)
    m = statistics.mean(keep)
    return sum(statistics.mean(r.sample(allv, len(keep))) >= m for _ in range(n)) / n


S6 = dict(tp=[(0.2, 0.33), (1.0, 0.33), (3.0, None)], trail=0.20, be_at=0.2)
SUMMARY: list = []      # tabela zbiorcza: hipoteza -> train -> test -> N -> vs random_eligible -> werdykt


def add_outcomes(ents: list[dict]) -> None:
    """Wynik wejścia po kosztach: obecne wyjście bota (s0) i S6, etykieta rug (e) - -70% przed +50% w 6 h."""
    for e in ents:
        if "s0" not in e:
            e["s0"] = sim(e["path"], e["ref"], e["path"][0][0])
            e["s6"] = sim(e["path"], e["ref"], e["path"][0][0], **S6)
            e["rug"] = int(e["label"] == "rug")


_ELIG: set = set()


def eligible_mints() -> set:
    """Tokeny, które przeszły twarde filtry bota (sygnał safety_only) = uniwersum, z którego random_eligible losuje 25%."""
    if not _ELIG:
        _ELIG.update(r[0] for r in ro("bot.db").execute(
            "SELECT DISTINCT d.mint FROM signals s JOIN decisions d ON d.id = s.decision_id WHERE s.strategy='safety_only'"))
    return _ELIG


def re_expected(te: list[dict], ycol: str) -> tuple[float, int]:
    """Oczekiwany wynik random_eligible na TYM zbiorze i w TYM oknie: średnia po tokenach, które przeszły filtry bota
    (losowe 25% z nich ma tę samą wartość oczekiwaną). W wejściach bota = wszystkie wejścia (każde przeszło filtry)."""
    el = eligible_mints()
    v = [e[ycol] for e in te if e["mint"] in el]
    return mean(v), len(v)


def filter_eval(name: str, ents: list[dict], keep, ycol: str = "s0") -> list:
    """Filtr (zdefiniowany na eksploracji) vs baseline i vs random_eligible w tym samym oknie TESTU. Werdykt:
    POTWIERDZONE tylko, gdy na teście bije baseline, bije oczekiwany random_eligible (tokeny po filtrach bota z tego
    samego zbioru i okna, ta sama symulacja), p losowego podzbioru < 0.10 i N >= 30."""
    ex, te = split_time(ents)
    k_ex, k_te = [e for e in ex if keep(e)], [e for e in te if keep(e)]
    m = lambda s: mean([e[ycol] for e in s])
    p = perm_p([e[ycol] for e in k_te], [e[ycol] for e in te])
    re_m, re_n = re_expected(te, ycol)
    beat_base, beat_re = m(k_te) > m(te), m(k_te) > re_m
    if not m(k_ex) > m(ex):
        verdict = "odrzucone już na eksploracji"
    elif beat_base and beat_re and p < 0.10 and len(k_te) >= MIN_N:
        verdict = "**POTWIERDZONE**"
    elif beat_base and beat_re:
        verdict = f"kierunek OK, niepewne (N {len(k_te)}, p {p:.2f})"
    elif beat_base:
        verdict = "lepsze od baseline, ale NIE bije random_eligible -> bez wartości"
    else:
        verdict = "NIE trzyma się na teście"
    row = [name, f"{pct(m(k_ex))} vs {pct(m(ex))} (N {len(k_ex)}/{len(ex)})",
           f"{pct(m(k_te))} vs {pct(m(te))} (N {len(k_te)}{rel(len(k_te))}/{len(te)}; p {p:.2f})",
           f"{pct(re_m)} (N {re_n}{rel(re_n)})", verdict]
    SUMMARY.append(row)
    return row


FILTER_HEAD = ["filtr / hipoteza", "eksploracja: filtr vs baseline (N)", "TEST: filtr vs baseline (N; p losowe)",
               "random_eligible oczekiwany, TEST (N)", "werdykt"]


def variant_eval(name: str, ents: list[dict], new_col: str, base_col: str = "s0") -> list:
    """Wariant wyjścia na TYCH SAMYCH wejściach (np. S6 vs obecne) - różnica w parach + porównanie z random_eligible."""
    ex, te = split_time(ents)
    m = lambda s, c: mean([e[c] for e in s])
    lo, hi = boot_ci([e[new_col] - e[base_col] for e in te])
    better_ex, better_te = m(ex, new_col) > m(ex, base_col), m(te, new_col) > m(te, base_col)
    re_m, re_n = re_expected(te, base_col)
    beat_re = m(te, new_col) > re_m
    if not better_ex:
        verdict = "odrzucone już na eksploracji"
    elif better_te and lo > 0 and beat_re:
        verdict = "**POTWIERDZONE**"
    elif better_te and lo > 0:
        verdict = "lepsze od baseline (CI > 0), ale NIE bije random_eligible"
    elif better_te:
        verdict = "kierunek OK, CI obejmuje 0"
    else:
        verdict = "NIE trzyma się na teście"
    row = [name, f"{pct(m(ex, new_col))} vs {pct(m(ex, base_col))} (N {len(ex)})",
           f"{pct(m(te, new_col))} vs {pct(m(te, base_col))} (N {len(te)}{rel(len(te))}; CI różnicy "
           f"{lo * 100:+.1f}..{hi * 100:+.1f} pp)", f"{pct(re_m)} (N {re_n}{rel(re_n)})", verdict]
    SUMMARY.append(row)
    return row


def ref_rows(ex: list[dict], te: list[dict]) -> list[list]:
    """Wiersze odniesienia do tabel kubełków: baseline (wszystkie) i oczekiwany random_eligible (po filtrach bota)."""
    el = eligible_mints()
    rows = []
    for name, cond in (("**wszystkie (baseline)**", lambda e: True),
                       ("**random_eligible oczekiwany** (tokeny po filtrach bota)", lambda e: e["mint"] in el)):
        for lbl, s0 in (("eksploracja", ex), ("TEST", te)):
            s = [e for e in s0 if cond(e)]
            rows.append([name, lbl, f"{len(s)}{rel(len(s))}", pct(mean([e['s0'] for e in s])), pct(mean([e['s6'] for e in s])),
                         f"{mean([e['rug'] for e in s]):.0%}" if s else "—", pct(median([e['mfe'] for e in s]), 0)])
    return rows


V_PUMPSWAP = 17.58      # wirtualna rezerwa SOL pul PumpSwap (pole konta puli, offset 245; 7.10.2026)
SOL_USD = 120.0         # SOL/USD 1-7.10 (119-122) - do przeliczenia płynności z USD na SOL


def liq_vs_expected(l0: float, p0: float, l: float, p: float, mint: str) -> float | None:
    """Płynność (DexScreener, USD) względem OCZEKIWANEJ w puli stałego iloczynu bez dodawania/wycofania LP.
    Pule PumpSwap (tokeny *pump) liczą z wirtualną rezerwą SOL V: płynność = (2 SOL + V) x SOL/USD, a (SOL + V) rośnie
    jak sqrt(ceny), więc oczekiwana L_t = (L_0 + V) sqrt(P_t/P_0) - V (w SOL). Bez V (inne DEX-y): L_0 sqrt(P_t/P_0).
    Do 7.10 analizy liczyły bez V - przy spadku ceny "nadmierny" spadek płynności był sztuczny (fałszywe wycofania LP)."""
    if not (l0 and p0 and l and p):
        return None
    v = V_PUMPSWAP if mint.endswith("pump") else 0.0
    exp = (l0 / SOL_USD + v) * math.sqrt(p / p0) - v
    return (l / SOL_USD) / exp if exp > 0 else None
