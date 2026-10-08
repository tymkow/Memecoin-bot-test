"""Kalibracja progów na zebranych danych: `python bot.py calibrate [--horizon 6]`.

Bot zapisuje każdą decyzję (także odrzucone tokeny) razem z ceną, a po 1/6/24 h dopisuje pomiar ceny i płynności
(tabela outcomes). Tu porównujemy: co się stało z tokenami, które bot kupił / pominął / odrzucił z danego powodu.

Jak czytać:
  * veto z wysokim %rug i ujemną średnią - działa, trzymaj,
  * veto z dodatnią średnią i niskim %rug - zbyt ostre, tnie dobre tokeny (poluzuj próg),
  * próg buy_threshold: patrz tabela "wynik >= X" - wybierz najniższy próg, od którego średnia jest dodatnia.
Uwaga: to zwrot z wyceny (mark-to-market) bez kosztów wejścia/wyjścia i bez naszych stopów - to wskaźnik jakości
selekcji, nie symulacja zysku. Przy n < 30 wnioski są słabe.
"""
from __future__ import annotations

import json
import re
import statistics

from features import liq_bucket
from storage import Storage

VETO_RE = re.compile(r"^\[[^\]]+\] (.+?) \(VETO\):")


def _stats(rets: list[float], rugs: list[bool]) -> str:
    n = len(rets)
    if not n:
        return "brak danych"
    return (f"n={n:<4} śr {statistics.mean(rets):+7.1%}  mediana {statistics.median(rets):+7.1%}  "
            f">+50%: {sum(r > 0.5 for r in rets) / n:4.0%}  rug: {sum(rugs) / n:4.0%}")


def load(st: Storage, horizon: int, since: float | None = None):
    rows = st.db.execute(
        "SELECT d.id, d.mint, d.decision, d.score, d.findings, d.price, d.liq, d.opportunity, d.risk, d.features, "
        "o.price AS p1, o.liq AS l1 "
        "FROM decisions d JOIN outcomes o ON o.decision_id = d.id AND o.horizon_h = ? WHERE d.price > 0 AND d.ts >= ? "
        "ORDER BY d.ts", (horizon, since or 0)
    ).fetchall()
    out = []
    seen = set()
    for r in rows:
        key = (r["mint"], r["decision"])      # duplikaty tej samej decyzji o tym samym tokenie liczymy raz
        if key in seen:
            continue
        seen.add(key)
        ret = (r["p1"] / r["price"] - 1) if r["p1"] and r["p1"] > 0 else -1.0
        dead = bool(r["p1"] in (None, 0) or ret < -0.8
                    or (r["liq"] and r["l1"] is not None and r["l1"] < 0.2 * r["liq"]))
        vetoes = []
        for s in json.loads(r["findings"] or "[]"):
            m = VETO_RE.match(s)
            if m:
                vetoes.append(m.group(1))
        f = json.loads(r["features"] or "{}")
        out.append({"decision": r["decision"], "score": r["score"], "vetoes": vetoes, "ret": ret, "dead": dead,
                    "opp": r["opportunity"], "risk": r["risk"], "bucket": liq_bucket(r["liq"] or 0),
                    "source": f.get("source"), "atr": f.get("atr_pct")})
    return out


def run(cfg, horizon: int = 6, since: float | None = None):
    st = Storage(cfg.db_path)
    data = load(st, horizon, since)
    total = st.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    print(f"decyzji w bazie: {total}, z pomiarem po {horizon} h: {len(data)}")
    if len(data) < 10:
        print("Za mało pomiarów - zostaw bota włączonego (`python bot.py run`), pomiary dopisują się same.")
        return

    print(f"\n== wynik po {horizon} h wg decyzji ==")
    for dec in ("BUY", "SKIP", "REJECT", "WATCH"):
        rows = [d for d in data if d["decision"] == dec]
        print(f"  {dec:<7} {_stats([d['ret'] for d in rows], [d['dead'] for d in rows])}")

    print("\n== veto: co dokładnie odrzuca (im wyższy %rug i niższa średnia, tym lepiej działa) ==")
    names = sorted({v for d in data for v in d["vetoes"]})
    table = []
    for name in names:
        rows = [d for d in data if name in d["vetoes"]]
        table.append((name, rows))
    for name, rows in sorted(table, key=lambda t: -len(t[1])):
        print(f"  {name:<24} {_stats([d['ret'] for d in rows], [d['dead'] for d in rows])}")

    clean = [d for d in data if not d["vetoes"]]
    print("\n== osie decyzji: tokeny bez veto wg Opportunity (od X) i Risk (do Y) ==")
    for t in range(50, 100, 10):
        rows = [d for d in clean if d["opp"] is not None and d["opp"] >= t]
        if rows:
            print(f"  Opportunity >= {t:<3} {_stats([d['ret'] for d in rows], [d['dead'] for d in rows])}")
    for t in range(10, 70, 10):
        rows = [d for d in clean if d["risk"] is not None and d["risk"] <= t]
        if rows:
            print(f"  Risk        <= {t:<3} {_stats([d['ret'] for d in rows], [d['dead'] for d in rows])}")
    print(f"  (obecne progi: Opportunity >= {cfg.opportunity_min:.0f}, Risk <= {cfg.risk_max:.0f})")

    print("\n== kubełki płynności (tokeny bez veto) - czy dolne kubełki w ogóle mają sens ==")
    for b in ("5-10k", "10-25k", "25-50k", "50-100k", "100k+"):
        rows = [d for d in clean if d["bucket"] == b]
        print(f"  {b:<8} {_stats([d['ret'] for d in rows], [d['dead'] for d in rows])}")

    # v0.7: hipotezy wyboru tokenów - zmienność przy decyzji (filtr lowvol*) i źródło odkrycia
    print(f"\n== zmienność przy decyzji: ATR 1-min (tokeny bez veto; filtr lowvol* = < {cfg.lowvol_max_atr_pct:.0f}%) ==")
    for lo, hi in ((0, 10), (10, 15), (15, 20), (20, 30), (30, 1e9)):
        rows = [d for d in clean if d["atr"] is not None and lo <= d["atr"] < hi]
        label = f"{lo}-{hi:.0f}%" if hi < 1e9 else f">={lo}%"
        print(f"  {label:<8} {_stats([d['ret'] for d in rows], [d['dead'] for d in rows])}")
    print("\n== źródło odkrycia (wszystkie oceniane / bez veto) ==")
    for src in sorted({d["source"] or "nieznane" for d in data}):
        rows = [d for d in data if (d["source"] or "nieznane") == src]
        crows = [d for d in rows if not d["vetoes"]]
        print(f"  {src:<11} wszystkie: {_stats([d['ret'] for d in rows], [d['dead'] for d in rows])}")
        print(f"  {'':<11} bez veto:  {_stats([d['ret'] for d in crows], [d['dead'] for d in crows])}")

    print(f"\n== sygnały strategii: wynik CENY po {horizon} h (bez naszych wyjść i kosztów) vs wszystkie oceniane tokeny ==")
    print(f"  {'wszystkie bez veto':<18} {_stats([d['ret'] for d in clean], [d['dead'] for d in clean])}")
    for name, rows in signal_samples(st, horizon, since).items():
        print(f"  {name:<18} {_stats([d['ret'] for d in rows], [d['dead'] for d in rows])}")
    print("  (strategia ma sens, jeśli jej tokeny biją 'wszystkie bez veto' i grupy kontrolne safety_only/random_eligible)")


def signal_samples(st: Storage, horizon: int, since: float | None = None) -> dict:
    """Pierwszy sygnał strategii na token -> zmiana ceny po `horizon` h. Czas i cena sygnału ze st.signals_timed
    (sygnały sprzed v0.9 przypięte do oceny WATCH: cena z chwili prawdziwego sygnału; pomiar końcowy zostaje z oceny,
    więc ich horyzont bywa krótszy o kilka-kilkanaście minut)."""
    outcomes = {r["decision_id"]: (r["price"], r["liq"]) for r in
                st.db.execute("SELECT decision_id, price, liq FROM outcomes WHERE horizon_h=?", (horizon,))}
    out: dict = {}
    seen = set()
    for r in st.signals_timed():
        if (since and r["ts"] < since) or not r["price"] or r["price"] <= 0 or r["id"] not in outcomes:
            continue
        if (r["strategy"], r["mint"]) in seen:
            continue
        seen.add((r["strategy"], r["mint"]))
        p1, l1 = outcomes[r["id"]]
        ret = (p1 / r["price"] - 1) if p1 and p1 > 0 else -1.0
        dead = bool(p1 in (None, 0) or ret < -0.8 or (r["liq"] and l1 is not None and l1 < 0.2 * r["liq"]))
        out.setdefault(r["strategy"], []).append({"ret": ret, "dead": dead})
    return out
