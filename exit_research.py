"""Badanie wyjść: MAE/MFE wejść, "zabici zwycięzcy" i odtworzenie wariantów wyjść na archiwalnych świecach 1-min.

    python bot.py exits                 # wejścia, które bot naprawdę zrobił (pozycje)
    python bot.py exits --signals       # sygnały wszystkich strategii, także tylko-sygnałowych (więcej danych)
    python bot.py exits --horizon 6     # okno po wejściu w godzinach (max tyle, ile archiwizujemy: archive_after_h)

Skąd świece: bot sam archiwizuje 1-min świece dla każdego tokena z sygnałem (Config.archive_*).

Jak czytać (ważne):
  * MFE = najwyższy zysk po wejściu, MAE = najgłębszy spadek. "Zabici zwycięzcy" = wejścia, które najpierw dotknęły
    stopa, a potem i tak doszły do pierwszego take-profitu.
  * Odtworzenie wariantów to ILUSTRACJA, nie optymalizacja: na kilkudziesięciu wejściach różnice rzędu kilku punktów
    procentowych to szum, a wybranie "najlepszego" parametru z tej tabeli to dopasowanie do przeszłości.
    Decyzje podejmujemy na osobnych portfelach (np. safety_only vs safety_wide) i na danych z późniejszego okresu.
  * Ceny ze świec to ostatnie transakcje, nie gwarantowana cena sprzedaży. Koszty: wejście ~1.5%, wyjście ~4%
    (zmierzone w bocie); w świecy-krachu (low < 50% open) zakładamy sprzedaż przy dnie świecy, a gdy w jednej świecy
    padają i stop, i take-profit, liczymy najpierw stop (ostrożnie). Wyjścia po płynności (liq_drain, exit_gap) nie są
    odtwarzane - świece nie mają danych o płynności.
"""
from __future__ import annotations

import json
import statistics
import time

import indicators
from features import liq_bucket
from storage import Storage

EC, XC = 0.015, 0.04          # koszt wejścia / wyjścia (zmierzone w v0.6: poślizg wejścia ~1%, wyjścia ~4%)
CRASH = 0.5                   # świeca, w której low < 50% open = krach jednym zleceniem


def tp_plan(levels) -> list[tuple[float, float | None]]:
    """((50, .33), (100, .33), (300, .34)) z Config -> [(0.5, .33), (1.0, .33), (3.0, None)] (ostatni = reszta)."""
    out = [(lvl / 100, frac) for lvl, frac in levels]
    return [(l, f) for l, f in out[:-1]] + [(out[-1][0], None)] if out else []


def simulate(path, ref, ts0, stop=None, tp=((0.5, 1 / 3), (1.0, 1 / 3), (3.0, None)), trail=0.20,
             time_stop=(240, 0.10), short_ts=None, be_at=None):
    """Jedno wejście przez świece. path = [[ts,o,h,l,c,v], ...] PO świecy wejścia. Zwraca (zwrot, powód, minuty)."""
    tokens, left, proceeds, tp_i, peak = 1.0 / (ref * (1 + EC)), 1.0, 0.0, 0, ref
    for t, o, h, l, c, v in path:
        mins = (t - ts0) / 60
        trail_lvl = peak * (1 - trail) if tp_i >= 1 else None
        lvls = [x for x in (stop, trail_lvl) if x is not None]
        lvl = max(lvls) if lvls else None
        if lvl is not None and l <= lvl:
            fill = l if (o > 0 and l / o < CRASH) else min(o, lvl)
            proceeds += left * tokens * fill * (1 - XC)
            return proceeds - 1, ("trailing" if trail_lvl is not None and lvl == trail_lvl else "stop"), mins
        while tp_i < len(tp) and h >= ref * (1 + tp[tp_i][0]):
            px = max(o, ref * (1 + tp[tp_i][0]))
            frac = left if tp[tp_i][1] is None else min(tp[tp_i][1], left)
            proceeds += frac * tokens * px * (1 - XC)
            left -= frac
            tp_i += 1
            if left <= 1e-9:
                return proceeds - 1, "tp_all", mins
        peak = max(peak, h)
        if be_at is not None and stop is not None and h >= ref * (1 + be_at):
            stop = max(stop, ref)
        if short_ts and tp_i == 0 and mins >= short_ts[0] and c < ref * (1 + short_ts[1]):
            return proceeds + left * tokens * c * (1 - XC) - 1, "time_short", mins
        if time_stop and tp_i == 0 and mins >= time_stop[0] and c < ref * (1 + time_stop[1]):
            return proceeds + left * tokens * c * (1 - XC) - 1, "time_stop", mins
    last = path[-1][4] if path else ref
    return proceeds + left * tokens * last * (1 - XC) - 1, "koniec_okna", ((path[-1][0] - ts0) / 60 if path else 0)


def path_metrics(path, ref, ts0, stop_frac, tp1):
    """MFE/MAE, czas do MFE, co pierwsze (stop czy TP1), czy 'zabity zwycięzca', wynik na końcu okna."""
    i_mfe = max(range(len(path)), key=lambda i: path[i][2])
    first = None
    for x in path:
        dn, up = x[3] <= ref * (1 - stop_frac), x[2] >= ref * (1 + tp1)
        if dn or up:
            first = "oba" if dn and up else ("stop" if dn else "tp1")
            break
    hit = [i for i, x in enumerate(path) if x[2] >= ref * (1 + tp1)]
    return {
        "mfe": path[i_mfe][2] / ref - 1,
        "t_mfe": (path[i_mfe][0] - ts0) / 60,
        "mae": min(x[3] for x in path) / ref - 1,
        "mae_before_tp1": (min([x[3] for x in path[:hit[0]]] or [ref]) / ref - 1) if hit else None,
        "first": first,
        "killed_winner": first == "stop" and bool(hit),
        "final": path[-1][4] / ref - 1,
    }


def policies(cfg) -> dict:
    """Stała, krótka lista wariantów (świadomie BEZ siatki parametrów - patrz docstring)."""
    tp = tp_plan(cfg.take_profit_levels)
    trail = cfg.trailing_stop_pct / 100
    ts = (cfg.time_stop_minutes, cfg.time_stop_min_move_pct / 100)

    def base(**kw):
        d = dict(tp=tp, trail=trail, time_stop=ts)
        d.update(kw)
        return d

    def atr_stop(e, mult):
        a = e.get("atr_pct")
        return e["ref"] * max(1 - mult * a / 100, 0.4) if a else e["ref"] * (1 - cfg.stop_loss_pct / 100)

    return {
        f"obecne: SL -{cfg.stop_loss_pct:.0f}%": lambda e: base(stop=e["ref"] * (1 - cfg.stop_loss_pct / 100)),
        "SL -15%": lambda e: base(stop=e["ref"] * 0.85),
        "SL -40%": lambda e: base(stop=e["ref"] * 0.60),
        "SL awaryjny -60%": lambda e: base(stop=e["ref"] * 0.40),
        "bez SL (TP + trailing + time stop)": lambda e: base(stop=None),
        "SL 3x ATR(1 min)": lambda e: base(stop=atr_stop(e, 3)),
        f"SL -{cfg.stop_loss_pct:.0f}% + time stop 10 min (<+5%)":
            lambda e: base(stop=e["ref"] * (1 - cfg.stop_loss_pct / 100), short_ts=(10, 0.05)),
    }


def _build(store: Storage, mint: str, ts: float, horizon_min: int, atr_pct=None):
    """Świece wokół wejścia -> słownik wejścia albo None (brak archiwum / niezgodna cena)."""
    pool = store.pool_for(mint, ts)
    if not pool:
        return None
    cs = store.candles_between(pool, ts - 100 * 60, ts + horizon_min * 60)
    pre = [x for x in cs if x[0] <= ts]
    if not pre:
        return None
    refc = pre[-1]
    path = [x for x in cs if refc[0] < x[0] <= ts + horizon_min * 60]
    if not path or refc[4] <= 0:
        return None
    if atr_pct is None:
        atr_pct = indicators.compute(pre[-100:], now=ts).get("atr_pct")
    return {"mint": mint, "ts": ts, "ref": refc[4], "path": path, "atr_pct": atr_pct,
            "span": (path[-1][0] - ts) / 60}


def position_entries(store: Storage, horizon_min: int, strategy: str | None = None) -> tuple[list, int]:
    """Wejścia z pozycji (pozycje różnych strategii w ten sam token w ciągu 10 min = jedno wejście)."""
    q = ("SELECT * FROM positions WHERE status!='void'" + (" AND COALESCE(strategy,'hybrid')=?" if strategy else "")
         + " ORDER BY opened_ts")                         # 'void' = unieważnione po przerwie bez danych
    pos = store.db.execute(q, (strategy,) if strategy else ()).fetchall()
    groups: list[dict] = []
    for p in pos:
        for g in groups:
            if g["mint"] == p["mint"] and abs(g["ts"] - p["opened_ts"]) < 600:
                g["pos"].append(p)
                break
        else:
            groups.append({"mint": p["mint"], "ts": p["opened_ts"], "sym": p["symbol"], "pos": [p]})
    out, missing = [], 0
    for g in groups:
        infos = [json.loads(p["entry_info"] or "{}") for p in g["pos"]]
        feats = [i.get("features") or {} for i in infos]
        atrs = [f["atr_pct"] for f in feats if f.get("atr_pct") is not None]
        e = _build(store, g["mint"], g["ts"], horizon_min, statistics.mean(atrs) if atrs else None)
        if e is None:
            missing += 1
            continue
        eff = statistics.mean(p["entry_price"] for p in g["pos"])
        if not 0.5 < eff / e["ref"] < 2:          # zła pula / odwrócona cena - pomijamy zamiast liczyć bzdury
            missing += 1
            continue
        closed = [p for p in g["pos"] if p["status"] == "closed"]
        e.update({"sym": g["sym"], "strategies": sorted({p["strategy"] or "hybrid" for p in g["pos"]}),
                  "actual": statistics.mean(p["realized_usd"] / p["cost_usd"] - 1 for p in closed) if closed else None,
                  "source": next((f.get("source") for f in feats if f.get("source")), None),
                  "liq": statistics.mean(p["entry_liq"] or 0 for p in g["pos"])})
        out.append(e)
    return out, missing


def signal_entries(store: Storage, horizon_min: int, latency_s: int = 60) -> tuple[dict, int]:
    """Pierwszy sygnał każdej strategii dla każdego tokena -> wejście (z opóźnieniem latency_s po sygnale).
    Czas sygnału ze store.signals_timed (poprawka dla sygnałów przypiętych do starej oceny WATCH sprzed v0.9)."""
    out: dict[str, list] = {}
    seen, missing = set(), 0
    for r in store.signals_timed():
        if (r["strategy"], r["mint"]) in seen:
            continue
        seen.add((r["strategy"], r["mint"]))
        f = json.loads(r["features"] or "{}")
        # cechy poprawionego wiersza są z oceny WATCH - ATR liczymy wtedy ze świec w chwili prawdziwego sygnału
        e = _build(store, r["mint"], r["ts"] + latency_s, horizon_min, None if r["fixed"] else f.get("atr_pct"))
        if e is None:
            missing += 1
            continue
        e.update({"source": f.get("source"), "liq": r["liq"] or 0, "sym": r["mint"][:6]})
        out.setdefault(r["strategy"], []).append(e)
    return out, missing + store.skipped


# ------------------------------------------------------------------ raport

def _pf(rets):
    pos_, neg = sum(x for x in rets if x > 0), -sum(x for x in rets if x < 0)
    return pos_ / neg if neg else float("inf")


def _policy_table(cfg, entries, title):
    print(f"\n{title} (n={len(entries)}, rugów <=-80% na końcu okna: {sum(e['m']['final'] <= -0.8 for e in entries)})")
    if not entries:
        print("  brak danych")
        return
    print(f"  {'wariant':<42}{'śr.':>7}{'med.':>7}{'suma $50':>10}{'zysk.':>8}{'PF':>6}")
    for name, mk in policies(cfg).items():
        rets = [simulate(e["path"], e["ref"], e["ts"], **mk(e))[0] for e in entries]
        print(f"  {name:<42}{statistics.mean(rets):>+7.1%}{statistics.median(rets):>+7.1%}{sum(rets) * 50:>+10.0f}"
              f"{sum(x > 0 for x in rets):>4}/{len(rets):<3}{_pf(rets):>6.2f}")


def _overview(cfg, entries):
    n = len(entries)
    stop = cfg.stop_loss_pct / 100
    tp1 = cfg.take_profit_levels[0][0] / 100
    print(f"\n== MFE: czy wejścia w ogóle dawały szansę (okno do {max(e['span'] for e in entries):.0f} min) ==")
    for th in (0.1, 0.25, 0.5, 1.0):
        k = sum(e["m"]["mfe"] >= th for e in entries)
        print(f"  MFE >= +{th:.0%}: {k}/{n} ({k / n:.0%})")
    first = {k: sum(e["m"]["first"] == k for e in entries) for k in ("tp1", "stop", "oba")}
    print(f"  co pierwsze: +{tp1:.0%} -> {first['tp1']}, -{stop:.0%} -> {first['stop']}, oba w jednej minucie -> "
          f"{first['oba']}, żadne -> {n - sum(first.values())}")
    print(f"  koniec okna <= -80% (rug/zrzut): {sum(e['m']['final'] <= -0.8 for e in entries)}/{n}")
    wins = sorted(e["m"]["mae_before_tp1"] for e in entries if e["m"]["mae_before_tp1"] is not None)
    if wins:
        print(f"\n== MAE zwycięzców: jak głęboko schodziły wejścia, które doszły do +{tp1:.0%}, ZANIM doszły (n={len(wins)}) ==")
        k = len(wins) - 1
        print(f"  mediana {statistics.median(wins):+.0%}; 75% zwycięzców nie spadło głębiej niż {wins[int(.25 * k)]:+.0%}, "
              f"90% - niż {wins[int(.10 * k)]:+.0%}  (stop płytszy niż te poziomy wyrzuca odpowiednią część zwycięzców)")
        deeper = sum(w <= -stop for w in wins)
        print(f"  głębiej niż obecny stop -{stop:.0%}: {deeper}/{len(wins)} zwycięzców  ->  'zabitych zwycięzców': "
              f"{sum(e['m']['killed_winner'] for e in entries)}")


def _signal_table(cfg, groups: dict, starts: dict, title: str):
    print(f"\n{title}")
    print(f"  {'strategia':<20}{'od':>12}{'n':>4}{'rugi':>6}{'MFE>=+50%':>11}{'zabici':>8}{'obecne śr.':>12}{'PF':>6}"
          f"{'bez SL śr.':>12}{'PF':>6}")
    pol = policies(cfg)
    cur, nosl = list(pol.values())[0], pol["bez SL (TP + trailing + time stop)"]
    for name, es in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if not es:
            continue
        r1 = [simulate(e["path"], e["ref"], e["ts"], **cur(e))[0] for e in es]
        r2 = [simulate(e["path"], e["ref"], e["ts"], **nosl(e))[0] for e in es]
        od = time.strftime("%d.%m %H:%M", time.localtime(starts[name])) if starts.get(name) else "?"
        print(f"  {name:<20}{od:>12}{len(es):>4}{sum(e['m']['final'] <= -0.8 for e in es):>6}"
              f"{sum(e['m']['mfe'] >= 0.5 for e in es):>11}{sum(e['m']['killed_winner'] for e in es):>8}"
              f"{statistics.mean(r1):>+12.1%}{_pf(r1):>6.2f}{statistics.mean(r2):>+12.1%}{_pf(r2):>6.2f}")


def run(cfg, horizon_h: float = 6, signals: bool = False, since: float | None = None):
    st = Storage(cfg.db_path)
    horizon_min = int(min(horizon_h, cfg.archive_after_h) * 60)
    stop, tp1 = cfg.stop_loss_pct / 100, cfg.take_profit_levels[0][0] / 100
    n_c = st.db.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
    jobs = dict(st.db.execute("SELECT status, COUNT(*) FROM candle_jobs GROUP BY status").fetchall())
    print(f"archiwum: {n_c} świec, zadania: {jobs or 'brak'}  (świece pobierane {cfg.archive_after_h:.0f} h po sygnale)")
    if since:
        print(f"tylko wejścia/sygnały od {time.strftime('%d.%m %H:%M', time.localtime(since))}")

    if signals:
        groups, missing = signal_entries(st, horizon_min)
        if since:
            groups = {k: [e for e in v if e["ts"] >= since] for k, v in groups.items()}
        print(f"sygnały z archiwum świec: {sum(len(v) for v in groups.values())} (bez świec: {missing})")
        if not any(groups.values()):
            print("Brak danych - archiwum zapełnia się samo, gdy minie archive_after_h od sygnałów.")
            return
        for es in groups.values():
            for e in es:
                e["m"] = path_metrics(e["path"], e["ref"], e["ts"], stop, tp1)
        starts = {n: st.strategy_started(n) for n in groups}
        _signal_table(cfg, groups, starts, "== sygnały strategii: wynik po obecnych wyjściach vs bez stopa "
                                           "(wejście 60 s po sygnale; cały okres - strategie z różnych okresów!) ==")
        # uczciwe porównanie: od dołączenia każdej grupy strategii, tylko strategie, które wtedy już działały
        from reporting import cohorts
        for start, members in cohorts(starts)[1:]:
            sub = {n: [e for e in groups.get(n, []) if e["ts"] >= start] for n in members}
            if any(sub.values()):
                _signal_table(cfg, sub, starts, f"== wspólne okno od {time.strftime('%d.%m %H:%M', time.localtime(start))} "
                                                f"(tylko sygnały od tej chwili) ==")
        print("\n  (strategia ma sens, jeśli bije grupy kontrolne safety_only / random_eligible na DANYCH Z PRZYSZŁOŚCI)")
        return

    entries, missing = position_entries(st, horizon_min)
    if since:
        entries = [e for e in entries if e["ts"] >= since]
    print(f"wejścia (pozycje zgrupowane po tokenie i czasie): {len(entries)}, bez świec w archiwum: {missing}")
    if not entries:
        print("Brak danych - archiwum zapełnia się samo, gdy minie archive_after_h od wejść.")
        return
    for e in entries:
        e["m"] = path_metrics(e["path"], e["ref"], e["ts"], stop, tp1)
    _overview(cfg, entries)
    _policy_table(cfg, entries, "== odtworzenie wariantów wyjść na tych samych wejściach ==")

    thr = cfg.lowvol_max_atr_pct
    _policy_table(cfg, [e for e in entries if e["atr_pct"] is not None and e["atr_pct"] < thr],
                  f"== podzbiór: ATR 1-min < {thr:.0f}% (filtr strategii lowvol*) ==")
    _policy_table(cfg, [e for e in entries if e["atr_pct"] is not None and e["atr_pct"] >= thr],
                  f"== podzbiór: ATR 1-min >= {thr:.0f}% ==")

    print("\n== źródło odkrycia i kubełek płynności (obecne wyjścia) ==")
    cur = list(policies(cfg).values())[0]
    for key, fn in (("źródło", lambda e: e.get("source") or "nieznane"), ("płynność", lambda e: liq_bucket(e.get("liq") or 0))):
        groups: dict = {}
        for e in entries:
            groups.setdefault(fn(e), []).append(simulate(e["path"], e["ref"], e["ts"], **cur(e))[0])
        for g, rets in sorted(groups.items()):
            print(f"  {key:<9}{g:<12} n={len(rets):<3} śr {statistics.mean(rets):+6.1%}  med {statistics.median(rets):+6.1%}")

    pairs = [(simulate(e["path"], e["ref"], e["ts"], **cur(e))[0], e["actual"]) for e in entries if e["actual"] is not None]
    if pairs:
        agree = sum((a > 0) == (b > 0) for a, b in pairs)
        print(f"\nkontrola wiarygodności: odtworzenie obecnych wyjść vs realny wynik bota - zgodny znak {agree}/{len(pairs)}, "
              f"suma ${sum(a for a, _ in pairs) * 50:+.0f} vs ${sum(b for _, b in pairs) * 50:+.0f} (na 1 pozycję z wejścia)")

    live = st.db.execute("SELECT COALESCE(strategy,'hybrid') s, mae_pct, mfe_pct, realized_usd, cost_usd FROM positions "
                         "WHERE status='closed' AND mfe_pct IS NOT NULL").fetchall()
    if live:
        print("\n== MAE/MFE zapisane na żywo przez bota (cena, po której działają stopy) ==")
        by: dict = {}
        for r in live:
            by.setdefault(r["s"], []).append(r)
        for s, rs in sorted(by.items()):
            win_mae = [r["mae_pct"] for r in rs if r["realized_usd"] > r["cost_usd"]]
            print(f"  {s:<20} n={len(rs):<3} MFE med {statistics.median(r['mfe_pct'] for r in rs):+5.0f}%  "
                  f"MAE med {statistics.median(r['mae_pct'] for r in rs):+5.0f}%  "
                  f"MAE zwycięzców med {(statistics.median(win_mae) if win_mae else float('nan')):+5.0f}%")
    print("\nPamiętaj: to ilustracja na danych historycznych, nie wybór parametru (patrz nagłówek exit_research.py).")
