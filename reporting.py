"""Metryki wyników paper tradingu: `python bot.py report`.

Pokazuje każdą strategię osobno (ten sam rynek, te same dane), z metrykami odpornymi na "jedną szczęśliwą transakcję":
expectancy, mediana, profit factor, PnL bez najlepszej transakcji, max drawdown, koszty wykonania.
Przy małej liczbie transakcji (< 30) każdy wniosek jest hipotezą, nie wynikiem.
"""
from __future__ import annotations

import json
import statistics
import time

from features import liq_bucket
from storage import Storage

MIN_TRADES = 30


def _pnl(r) -> float:
    return r["realized_usd"] - r["cost_usd"]


def metrics(rows: list) -> dict:
    """rows = zamknięte pozycje (sqlite Row) jednej strategii, w kolejności zamykania."""
    pnl = [_pnl(r) for r in rows]
    if not pnl:
        return {"n": 0}
    wins, losses = [p for p in pnl if p > 0], [p for p in pnl if p <= 0]
    rets = [_pnl(r) / r["cost_usd"] for r in rows if r["cost_usd"]]
    peak = cum = dd = 0.0
    for p in pnl:                     # drawdown na skumulowanym PnL zamkniętych transakcji
        cum += p
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    holds = [(r["closed_ts"] - r["opened_ts"]) / 60 for r in rows if r["closed_ts"]]
    return {
        "n": len(pnl), "win_rate": len(wins) / len(pnl), "total": sum(pnl),
        "expectancy": statistics.mean(pnl), "median": statistics.median(pnl),
        "profit_factor": (sum(wins) / -sum(losses)) if losses and sum(losses) < 0 else None,
        "without_best": sum(pnl) - max(pnl), "max_dd": dd,
        "avg_hold_min": statistics.mean(holds) if holds else 0.0,
        "sharpe_like": (statistics.mean(rets) / statistics.pstdev(rets)) if len(rets) > 2 and statistics.pstdev(rets) > 0 else None,
    }


def _fmt(m: dict) -> str:
    if not m.get("n"):
        return "brak zamkniętych pozycji"
    pf = f"{m['profit_factor']:.2f}" if m["profit_factor"] is not None else "-"
    sh = f"{m['sharpe_like']:.2f}" if m["sharpe_like"] is not None else "-"
    return (f"n={m['n']:<3} win {m['win_rate']:4.0%}  expectancy ${m['expectancy']:+7.2f}  mediana ${m['median']:+7.2f}  "
            f"PF {pf:>5}  suma ${m['total']:+8.2f}  bez najlepszej ${m['without_best']:+8.2f}  "
            f"maxDD ${m['max_dd']:6.2f}  śr.czas {m['avg_hold_min']:5.0f} min  sharpe~ {sh}")


def cohorts(starts: dict, gap_s: float = 900) -> list[tuple[float, list[str]]]:
    """Grupuje strategie wg momentu dołączenia. Zwraca [(start kohorty, strategie istniejące od tej chwili), ...].
    Każda kolejna kohorta = porównanie wszystkich strategii, które już działały, od chwili dołączenia nowych -
    dzięki temu dodanie strategii nie zmienia okna porównania wcześniejszych. gap_s: strategie dołączone w odstępie
    do 15 min to jedna kohorta (przy 1 h sklejały się starty z 17:52 i 18:50 - okno strict zaczynało się za wcześnie)."""
    known = sorted((t, n) for n, t in starts.items() if t is not None)
    out: list[tuple[float, list[str]]] = []
    for t, n in known:
        if not out or t - out[-1][0] > gap_s:
            out.append((t, list(out[-1][1]) if out else []))   # nowa kohorta = wcześniejsze strategie + nowe
        out[-1][1].append(n)
    return out


def _bucket(value, edges: list[float], labels: list[str]) -> str:
    for e, lab in zip(edges, labels):
        if value < e:
            return lab
    return labels[-1]


def run(cfg):
    st = Storage(cfg.db_path)
    closed = st.db.execute("SELECT * FROM positions WHERE status='closed' ORDER BY closed_ts").fetchall()
    opened = st.db.execute("SELECT strategy, COUNT(*) c FROM positions WHERE status='open' GROUP BY strategy").fetchall()
    open_by = {r["strategy"] or "hybrid": r["c"] for r in opened}
    strategies = sorted({(r["strategy"] or "hybrid") for r in closed} | set(open_by) | set(cfg.strategies))

    print(f"zamknięte pozycje: {len(closed)}, otwarte: {sum(open_by.values())}, "
          f"nieudane wejścia (cena uciekła): {st.kv_get('failed_entries', 0)}")
    print(f"\n== strategie (ten sam rynek; wniosek wolno wyciągać od {MIN_TRADES} transakcji na strategię) ==")
    for name in strategies:
        rows = [r for r in closed if (r["strategy"] or "hybrid") == name]
        eq = st.db.execute("SELECT equity FROM equity WHERE strategy=? ORDER BY ts DESC LIMIT 1", (name,)).fetchone()
        deps = st.kv_get(("" if name == "hybrid" else f"{name}:") + "deposits", [])   # dopłaty (topup.py)
        eqs = [r["equity"] - sum(d for t, d in deps if t <= r["ts"])
               for r in st.db.execute("SELECT ts, equity FROM equity WHERE strategy=? ORDER BY ts", (name,))]
        peak, dd = 0.0, 0.0
        for e in eqs:
            peak = max(peak, e)
            dd = max(dd, (peak - e) / peak * 100 if peak else 0)
        tag = "" if len(rows) >= MIN_TRADES else "  [za mało danych]"
        dep = (f"  (dopłacono ${sum(d for _, d in deps):,.0f}; bez dopłat "
               f"${eq['equity'] - sum(d for _, d in deps):,.2f})" if deps and eq else "")
        print(f"\n{name}  kapitał ${eq['equity']:,.2f}{dep}  otwarte {open_by.get(name, 0)}  maxDD(equity) {dd:.1f}%{tag}" if eq
              else f"\n{name}{tag}")
        print("  " + _fmt(metrics(rows)))

    if not closed:
        return

    # strategie dodane później mają krótszą historię - porównujemy je w kohortach: od chwili dołączenia każdej grupy,
    # wszystkie strategie, które wtedy już działały (dodanie nowej strategii nie zmienia okien wcześniejszych porównań)
    for start, members in cohorts({n: st.strategy_started(n) for n in strategies})[1:]:
        print(f"\n== porównanie we WSPÓLNYM oknie od {time.strftime('%d.%m %H:%M', time.localtime(start))} "
              f"(pozycje otwarte od dołączenia tej grupy strategii) ==")
        for name in members:
            rows = [r for r in closed if (r["strategy"] or "hybrid") == name and r["opened_ts"] >= start]
            print(f"  {name:<20} " + _fmt(metrics(rows)))

    # zmiana zasad portfeli (stawka, limity, wyjścia) zmienia warunki gry WSZYSTKIM strategiom naraz
    since = st.kv_get("rules_since")
    if since and any(r["opened_ts"] >= since for r in closed):
        print(f"\n== od ostatniej zmiany zasad portfeli ({time.strftime('%d.%m %H:%M', time.localtime(since))}; "
              f"te same zasady dla wszystkich) ==")
        for name in strategies:
            rows = [r for r in closed if (r["strategy"] or "hybrid") == name and r["opened_ts"] >= since]
            print(f"  {name:<20} " + _fmt(metrics(rows)))

    # koszty wykonania: ile zjadły prowizje, poślizg i priority fee (fee_usd w trades = koszt względem ceny referencyjnej)
    print("\n== koszty wykonania (suma, USD) i poślizg ==")
    for name in strategies:
        r = st.db.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(t.fee_usd),0) fee, COALESCE(AVG(CASE WHEN t.side='BUY' THEN t.slippage_pct END),0) buy_slip,"
            " COALESCE(AVG(CASE WHEN t.side='SELL' AND t.reason NOT IN ('unsellable','no_data_rug') THEN t.slippage_pct END),0) sell_slip "
            "FROM trades t JOIN positions p ON p.id=t.position_id WHERE COALESCE(p.strategy,'hybrid')=?", (name,)).fetchone()
        if r["n"]:
            gross = sum(_pnl(x) for x in closed if (x["strategy"] or "hybrid") == name) + r["fee"]
            print(f"  {name:<15} koszty ${r['fee']:8.2f}  śr. poślizg wejścia {r['buy_slip']:5.1f}%  wyjścia {r['sell_slip']:5.1f}%  "
                  f"(PnL przed kosztami ${gross:+.2f})")

    # opóźnienie wejścia: jak uciekała cena między sygnałem a transakcją
    moves = []
    for r in closed:
        info = json.loads(r["entry_info"] or "{}")
        if "price_move_pct" in info:
            moves.append(info["price_move_pct"])
    if moves:
        print(f"\n== latencja wejścia ({len(moves)} pozycji) ==\n  średnio {statistics.mean(moves):+.2f}% mniej tokenów po opóźnieniu "
              f"(mediana {statistics.median(moves):+.2f}%, max {max(moves):+.2f}%)")

    print("\n== powody wyjścia (wszystkie strategie) ==")
    by: dict = {}
    for r in closed:
        by.setdefault(r["exit_reason"], []).append(_pnl(r))
    for reason, ps in sorted(by.items(), key=lambda kv: sum(kv[1])):
        print(f"  {reason:<16} {len(ps):>3} szt.  suma ${sum(ps):+9.2f}  śr. ${statistics.mean(ps):+7.2f}")

    order = ["<5k", "5-10k", "10-25k", "25-50k", "50-100k", "100k+"]
    print("\n== kubełki płynności przy wejściu - osobno dla każdej strategii (zysk netto po kosztach) ==")
    for name in strategies:
        rows = [r for r in closed if (r["strategy"] or "hybrid") == name]
        if not rows:
            continue
        print(f"  {name}")
        by_liq: dict = {}
        for r in rows:
            by_liq.setdefault(liq_bucket(r["entry_liq"] or 0), []).append(_pnl(r))
        for b in order:
            if b in by_liq:
                pnl = by_liq[b]
                print(f"    {b:<8} n={len(pnl):<3} śr. ${statistics.mean(pnl):+7.2f}  mediana ${statistics.median(pnl):+7.2f}  suma ${sum(pnl):+8.2f}")

    print("\n== kubełki mcap i Opportunity przy wejściu (wszystkie strategie) ==")
    groups: dict = {"mcap": {}, "Opportunity": {}}
    for r in closed:
        info = json.loads(r["entry_info"] or "{}")
        f = info.get("features") or {}
        if f.get("mcap"):
            groups["mcap"].setdefault(_bucket(f["mcap"], [50e3, 150e3, 500e3], ["<50k", "50-150k", "150-500k", ">500k"]), []).append(r)
        if info.get("opportunity") is not None:
            groups["Opportunity"].setdefault(_bucket(info["opportunity"], [75, 85], ["<75", "75-85", ">=85"]), []).append(r)
    for g, buckets in groups.items():
        for b, rows in sorted(buckets.items()):
            pnl = [_pnl(r) for r in rows]
            print(f"  {g:<12} {b:<9} n={len(rows):<3} śr. ${statistics.mean(pnl):+7.2f}  mediana ${statistics.median(pnl):+7.2f}  suma ${sum(pnl):+8.2f}")

    print("\nDecyzje:", dict(st.db.execute("SELECT decision, COUNT(*) FROM decisions GROUP BY decision").fetchall()),
          "| snapshotów:", st.db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],
          "| lista rugów:", st.db.execute("SELECT COUNT(*) FROM bad_wallets").fetchone()[0])
    g = st.db.execute("SELECT COUNT(*), SUM(decision='BUY'), SUM(error IS NOT NULL), AVG(latency), "
                      "SUM(tokens_in), SUM(tokens_out) FROM llm_decisions").fetchone()
    if g[0]:
        print(f"Gemini: ocen {g[0]}, BUY {g[1] or 0}, błędów/odrzuconych odpowiedzi {g[2] or 0}, śr. czas odpowiedzi "
              f"{g[3] or 0:.1f} s, tokeny {g[4] or 0:,} wej. / {g[5] or 0:,} wyj.")
    print("Zbiór danych: transakcje portfeli:", st.db.execute("SELECT COUNT(*) FROM wallet_trades").fetchone()[0],
          "(portfeli", st.db.execute("SELECT COUNT(DISTINCT wallet) FROM wallet_trades").fetchone()[0], ")",
          "| starty PumpPortal:", st.db.execute("SELECT COUNT(*) FROM launches").fetchone()[0],
          "| graduacje:", st.db.execute("SELECT COUNT(*) FROM migrations").fetchone()[0],
          "| sygnały strategii:", st.db.execute("SELECT COUNT(*) FROM signals").fetchone()[0])
