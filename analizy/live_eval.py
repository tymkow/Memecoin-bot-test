"""Ocena portfeli safety_fast / safety_bundle30 / safety_nocopy na żywo wg kryteriów ustalonych 7.10.2026 PRZED
wynikami (analizy/KRYTERIA_NA_ZYWO.md - ten plik je tylko liczy, nie zmienia).

    python -m analizy.live_eval
"""
from __future__ import annotations

import json
import random
import statistics
import time

from analizy import common as C

T0 = time.mktime((2026, 10, 7, 12, 16, 0, 0, 0, -1))
MIN_POS = 100
PAIR_S = 600
FILTERS = ("safety_bundle30", "safety_nocopy")


def ci(xs: list, n: int = 2000, seed: int = 1):
    if len(xs) < 2:
        return float("nan"), float("nan")
    r = random.Random(seed)
    ms = sorted(statistics.mean(r.choices(xs, k=len(xs))) for _ in range(n))
    return ms[int(n * 0.025)], ms[int(n * 0.975)]


def ci_diff(a: list, b: list, n: int = 2000, seed: int = 1):
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    r = random.Random(seed)
    ds = sorted(statistics.mean(r.choices(a, k=len(a))) - statistics.mean(r.choices(b, k=len(b))) for _ in range(n))
    return ds[int(n * 0.025)], ds[int(n * 0.975)]


def verdict(lo, hi, ok: bool) -> str:
    if not ok:
        return "za wcześnie (próg nie osiągnięty)"
    if lo > 0:
        return "**LEPSZY**"
    if hi < 0:
        return "**GORSZY**"
    return "nierozstrzygnięty"


def load():
    db = C.ro("bot.db")
    pos = [dict(r) for r in db.execute(
        "SELECT id, mint, strategy, opened_ts, closed_ts, cost_usd, realized_usd, exit_reason FROM positions "
        "WHERE status='closed' AND opened_ts >= ? AND COALESCE(exit_reason,'') NOT LIKE 'przerwa%'", (T0,))]
    for p in pos:
        p["ret"] = p["realized_usd"] / p["cost_usd"] - 1
    return db, pos


def filter_flags(db, p: dict, name: str):
    """Czy filtr dał sygnał przy decyzji, z której safety_only otworzył pozycję (None = brak danych o starcie)."""
    d = db.execute("SELECT d.id, d.features FROM decisions d JOIN signals s ON s.decision_id = d.id "
                   "WHERE d.mint=? AND s.strategy='safety_only' AND d.ts <= ? ORDER BY d.ts DESC LIMIT 1",
                   (p["mint"], p["opened_ts"] + 5)).fetchone()
    if not d:
        return None
    if name == "safety_bundle30":
        f = json.loads(d["features"] or "{}") or {}
        if f.get("bundle_start_pct") is None:
            return None
    return bool(db.execute("SELECT 1 FROM signals WHERE decision_id=? AND strategy=?", (d["id"], name)).fetchone())


def report() -> str:
    db, pos = load()
    by = {}
    for p in pos:
        by.setdefault(p["strategy"] or "hybrid", []).append(p)
    so, re_ = by.get("safety_only", []), by.get("random_eligible", [])
    out = [open(C.ROOT / "analizy" / "KRYTERIA_NA_ZYWO.md", encoding="utf-8").read(),
           f"\n**Stan na {time.strftime('%d.%m.%Y %H:%M')}** (okno od 7.10 12:16): safety_only {len(so)} pozycji, "
           f"random_eligible {len(re_)}.\n"]
    rows = []
    fast = by.get("safety_fast", [])
    pairs = []
    for p in fast:
        m = [q for q in so if q["mint"] == p["mint"] and abs(q["opened_ts"] - p["opened_ts"]) <= PAIR_S]
        if m:
            pairs.append(p["ret"] - m[0]["ret"])
    lo, hi = ci(pairs)
    rows.append(["safety_fast", f"{len(fast)}", C.pct(C.mean([p['ret'] for p in fast])), f"{sum(p['realized_usd'] - p['cost_usd'] for p in fast):+.0f}",
                 f"pary z safety_only: {len(pairs)}, średnia różnica {C.pct(C.mean(pairs))} (CI {lo * 100:+.1f}..{hi * 100:+.1f} pp)",
                 verdict(lo, hi, len(fast) >= MIN_POS)])
    for name in FILTERS:
        own = by.get(name, [])
        flags = [(p, filter_flags(db, p, name)) for p in so]
        kept = [p["ret"] for p, f in flags if f is True]
        drop = [p["ret"] for p, f in flags if f is False]
        unk = sum(1 for _, f in flags if f is None)
        lo, hi = ci_diff(kept, drop)
        rows.append([name, f"{len(own)}", C.pct(C.mean([p['ret'] for p in own])), f"{sum(p['realized_usd'] - p['cost_usd'] for p in own):+.0f}",
                     f"safety_only przepuszczone {C.pct(C.mean(kept))} (N {len(kept)}) vs odrzucone {C.pct(C.mean(drop))} "
                     f"(N {len(drop)}), brak danych {unk}; różnica CI {lo * 100:+.1f}..{hi * 100:+.1f} pp",
                     verdict(lo, hi, len(own) >= MIN_POS and len(kept) >= C.MIN_N and len(drop) >= C.MIN_N)])
    out.append(C.table(["portfel", "pozycji", "śr. wynik", "$", "miara główna (kryteria 3-4)", "werdykt"], rows))
    rf = by.get("random_fast_s6", [])
    if rf:
        t0 = min(p["opened_ts"] for p in rf)
        rel = [p for p in re_ if p["opened_ts"] >= t0 - PAIR_S]
        pr = []
        for p in rf:
            q = [x for x in rel if x["mint"] == p["mint"] and abs(x["opened_ts"] - p["opened_ts"]) <= PAIR_S]
            if q:
                pr.append(p["ret"] - q[0]["ret"])
        lo, hi = ci(pr)
        la, ha = ci([p["ret"] for p in rf])
        out.append(f"\n**random_fast_s6** (kryteria niżej w pliku): pozycji {len(rf)}, średnio {C.pct(C.mean([p['ret'] for p in rf]))} "
                   f"(CI {la * 100:+.1f}..{ha * 100:+.1f}%); pary z random_eligible {len(pr)}, różnica {C.pct(C.mean(pr))} "
                   f"(CI {lo * 100:+.1f}..{hi * 100:+.1f} pp) -> {verdict(lo, hi, len(pr) >= MIN_POS)}.")
    rows = []
    for name in ("safety_fast",) + FILTERS:
        own = [p["ret"] for p in by.get(name, [])]
        lo, hi = ci_diff(own, [p["ret"] for p in re_])
        rows.append([name, f"{C.pct(C.mean(own))} (N {len(own)})", f"{C.pct(C.mean([p['ret'] for p in re_]))} (N {len(re_)})",
                     f"{lo * 100:+.1f}..{hi * 100:+.1f} pp",
                     "za wcześnie" if len(own) < MIN_POS else
                     ("lepszy od random_eligible" if lo > 0 else "nie lepszy od losowego")])
    out.append("\n**Porównanie z random_eligible (kryterium 5):**\n")
    out.append(C.table(["portfel", "śr. wynik", "random_eligible", "CI różnicy", "ocena"], rows))
    evs = [e for e in (C.ro("bot.db").execute("SELECT v FROM kv WHERE k='fast_stop_events'").fetchone() or ["[]"])]
    ev = json.loads(evs[0]) if evs else []
    if ev:
        ds = [e["since_last_above_s"] for e in ev if e.get("since_last_above_s") is not None]
        out.append(f"\nSzybki stop: {len(ev)} wyjść stop_fast; od ostatniego odczytu nad stopem do sprzedaży mediana "
                   f"{C.median(ds):.1f} s (N {len(ds)}).")
    return "\n".join(out)


if __name__ == "__main__":
    print(report())
