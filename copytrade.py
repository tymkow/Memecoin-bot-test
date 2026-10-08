"""Copy trading na własnych danych (data/stream.db ze zbieracza collector.py): czy kopiowanie portfeli, które zarabiały
w przeszłości, zarabia w PRZYSZŁOŚCI - po naszym opóźnieniu i kosztach.

    python copytrade.py                         # ranking na pierwszych 60% danych, test na ostatnich 40%
    python copytrade.py --split 0.5 --top 30 --size 0.25 --min-closed 5

Kroki:
  1. Okres treningowy: wynik każdego portfela na krzywej pump.fun (pozycja = zakupy i sprzedaże jednego tokena,
     koszt średni, opłaty pump.fun z każdej transakcji). Odsiew: boty (mediana trzymania < 15 s albo > 300 tokenów),
     twórcy tokenów (pozycje we własnych tokenach), mniej niż --min-closed zamkniętych pozycji.
  2. Ranking: portfele z zyskiem i >= 50% wygranych, kolejność po zysku w SOL -> top N.
     Grupa kontrolna: N LOSOWYCH portfeli spełniających te same warunki aktywności (bez warunku zysku).
  3. Okres testowy: każdy PIERWSZY zakup tokena przez portfel z grupy = nasz zakup za --size SOL po opóźnieniu d
     (0 s = ich cena, nieosiągalne - punkt odniesienia; 3 s; 10 s; 30 s). Cena i poślizg z rezerw krzywej w chwili t+d,
     opłata pump.fun z transakcji, --prio SOL za każdą transakcję (priority fee + tip). Jeden zakup na token.
     Wyjście "lustro": gdy lider sprzeda pierwszy raz (też z opóźnieniem d); "zasady bota": SL -25%, TP 50/100/300%
     po 1/3, trailing 20% po TP1, time stop 240 min. Graduacja = wyjście po ostatniej cenie krzywej (handlu na
     PumpSwap jeszcze nie zbieramy), koniec danych = wycena otwartej pozycji.

Uwagi: kilka godzin danych to mało - liczy się kierunek i porównanie z grupą kontrolną, nie dokładna liczba.
Luki w danych (dziury > 5 s bez transakcji, collector.data_holes) oznaczają brakujące transakcje: część pozycji może być
policzona błędnie (5.10: po południu brakowało 20-43% transakcji na godzinę - publiczny RPC).
"""
from __future__ import annotations

import argparse
import bisect
import random
import sqlite3
import statistics
import time
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "stream.db"
DELAYS = (0, 3, 10, 30)
LAMPORTS = 1e9


# ------------------------------------------------------------------ matematyka krzywej pump.fun (stała iloczynu na rezerwach wirtualnych)
def buy_tokens(vsol: int, vtok: int, sol_in: float, fee_bps: int) -> float:
    """Ile tokenów (surowe jednostki) za sol_in lamportów RAZEM z opłatą (opłata doliczana do kwoty na krzywą)."""
    curve_in = sol_in / (1 + fee_bps / 1e4)
    return vtok - vsol * vtok / (vsol + curve_in)


def sell_sol(vsol: int, vtok: int, tokens: float, fee_bps: int) -> float:
    """Ile lamportów dostaniemy za tokens (po opłacie pump.fun)."""
    out = vsol - vsol * vtok / (vtok + tokens)
    return max(out, 0.0) * (1 - fee_bps / 1e4)


# ------------------------------------------------------------------ dane
def build_states(rows) -> dict:
    """mint -> (czasy, stany krzywej po każdej transakcji: (vsol, vtok, fee_bps)) - do wyceny w dowolnej chwili."""
    states: dict[int, tuple[list, list]] = defaultdict(lambda: ([], []))
    for r in rows:
        ts_list, st = states[r[2]]
        ts_list.append(r[1])
        st.append((r[7], r[8], r[9] or 125))
    return states


def load(db: sqlite3.Connection, hours: float | None = None):
    """Transakcje (całość albo ostatnie `hours` godzin - po tygodniu zbierania całość nie zmieści się w pamięci)."""
    t_from = (db.execute("SELECT MAX(ts) FROM trades").fetchone()[0] or 0) - hours * 3600 if hours else 0
    rows = db.execute("SELECT slot, ts, mint_id, wallet_id, buy, sol, tok, vsol, vtok, fee_bps FROM trades "
                      "WHERE ts >= ? ORDER BY slot, rowid", (t_from,)).fetchall()
    states = build_states(rows)
    complete ={m: ts for m, ts in db.execute("SELECT mint_id, MIN(ts) FROM events WHERE kind='complete' GROUP BY mint_id")}
    creators = {m: c for m, c in db.execute("SELECT id, creator FROM mints WHERE creator IS NOT NULL")}
    from collector import data_holes                # dziury w czasie bloku (tabela gaps do 5.10 była niepełna)
    holes = data_holes(db)
    gaps = (len(holes), sum(b - a for a, b in holes))
    return rows, states, complete, creators, gaps


def state_at(states, mint: int, t: float):
    """Stan krzywej po ostatniej transakcji z czasem <= t (None, gdy tokena jeszcze nie było w danych)."""
    ts_list, st = states[mint]
    i = bisect.bisect_right(ts_list, t) - 1
    return (st[i], i) if i >= 0 else (None, -1)


# ------------------------------------------------------------------ 1. wyniki portfeli
def wallet_positions(rows, t0: float, t1: float, creators: dict) -> dict:
    """Zamknięte pozycje portfeli otwarte i zamknięte w [t0, t1): {portfel: [(mint, otwarcie, zamknięcie, koszt, przychód)]}.
    Sprzedaże tokenów kupionych przed oknem pomijamy (nieznany koszt). Pozycje twórców we własnych tokenach - pomijamy."""
    open_: dict = {}
    closed: dict = defaultdict(list)
    for slot, ts, mint, w, buy, sol, tok, vsol, vtok, fee in rows:
        if ts < t0 or ts >= t1 or creators.get(mint) == w:
            continue
        fee = fee or 125
        key = (w, mint)
        p = open_.get(key)
        if buy:
            if p is None:
                p = open_[key] = {"t": ts, "tok": 0.0, "cost": 0.0, "max": 0.0, "proc": 0.0, "cost_sold": 0.0}
            p["tok"] += tok
            p["cost"] += sol * (1 + fee / 1e4)
            p["max"] = max(p["max"], p["tok"])
        elif p is not None and p["tok"] > 0:
            q = min(tok, p["tok"])
            part = p["cost"] * q / p["tok"]
            p["proc"] += sol * (1 - fee / 1e4) * q / tok
            p["cost_sold"] += part
            p["cost"] -= part
            p["tok"] -= q
            if p["tok"] <= 0.01 * p["max"]:
                closed[w].append((mint, p["t"], ts, p["cost_sold"] + p["cost"], p["proc"]))
                del open_[key]
    return closed


def wallet_stats(closed: dict) -> dict:
    out = {}
    for w, ps in closed.items():
        pnl = [proc - cost for _, _, _, cost, proc in ps]
        holds = [t2 - t1 for _, t1, t2, _, _ in ps]
        out[w] = {"n": len(ps), "pnl": sum(pnl) / LAMPORTS, "win": sum(x > 0 for x in pnl) / len(ps),
                  "roi": statistics.mean((proc / cost - 1) if cost else 0 for _, _, _, cost, proc in ps),
                  "hold": statistics.median(holds), "tokens": len({m for m, *_ in ps})}
    return out


def eligible(stats: dict, min_closed: int, min_hold: float = 60) -> list:
    """Aktywne portfele, które da się kopiować: mediana trzymania >= min_hold s (szybszych nie dogonimy z naszym
    opóźnieniem 2-5 s strumienia + decyzja + wysłanie), <= 300 tokenów w oknie (więcej = bot)."""
    return [w for w, s in stats.items() if s["n"] >= min_closed and s["hold"] >= max(min_hold, 15) and s["tokens"] <= 300]


# ------------------------------------------------------------------ 3. symulacja kopiowania
def leader_signals(rows, leaders: set, t0: float, t1: float, creators: dict) -> list:
    """Pierwszy zakup tokena przez lidera w oknie testowym: (czas, mint, lider, ich koszt, ich tokeny, czas ich 1. sprzedaży)."""
    seen, sig, first_sell = set(), [], {}
    for slot, ts, mint, w, buy, sol, tok, vsol, vtok, fee in rows:
        if w not in leaders or ts < t0 or ts >= t1 or creators.get(mint) == w:
            continue
        key = (w, mint)
        if buy and key not in seen:
            seen.add(key)
            sig.append([ts, mint, w, sol * (1 + (fee or 125) / 1e4), tok, None])
        elif not buy and key in seen and key not in first_sell:
            first_sell[key] = ts
    for s in sig:
        s[5] = first_sell.get((s[2], s[1]))
    return sorted(sig)


def simulate(sig, states, complete: dict, delay: int, size_sol: float, prio_sol: float, mode: str, t_end: float):
    """Jedna pozycja (sygnał lidera) -> (zwrot, powód wyjścia) albo None, gdy nie dało się wejść."""
    t_lead, mint, _, their_cost, their_tok, t_sell = sig
    size, prio = size_sol * LAMPORTS, prio_sol * LAMPORTS
    t_done = complete.get(mint)
    t_in = t_lead + delay
    if t_done is not None and t_done <= t_in:
        return None                                              # token już zgraduował - na krzywej nie kupimy
    if delay == 0:                                               # ich cena (punkt odniesienia)
        tokens = their_tok * (size - prio) / their_cost
        st, i = state_at(states, mint, t_lead)
    else:
        st, i = state_at(states, mint, t_in)
        if st is None:
            return None
        tokens = buy_tokens(st[0], st[1], size - prio, st[2])
    ts_list, sts = states[mint]

    def exit_at(t):
        s, _ = state_at(states, mint, t)
        return sell_sol(s[0], s[1], tokens, s[2]) - prio

    end = min(x for x in (t_done, t_end) if x is not None)
    if mode == "lustro":
        if t_sell is not None and t_sell + delay < end:
            return exit_at(t_sell + delay) / size - 1, "lider sprzedał"
        return exit_at(end) / size - 1, ("graduacja" if t_done is not None and t_done <= t_end else "koniec danych")
    # zasady bota: SL -25%, TP +50/+100/+300 (po 1/3), trailing 20% po TP1, time stop 240 min (< +10%)
    left, proceeds, tp_i, peak = tokens, 0.0, 0, 0.0
    levels = (0.5, 1.0, 3.0)
    for j in range(max(i, 0) + 1, len(ts_list)):
        t = ts_list[j]
        if t >= end:
            break
        s = sts[j]
        # cena WYKONALNA na token (sprzedaż reszty pozycji po tym stanie) względem naszej ceny wejścia
        ratio = sell_sol(s[0], s[1], left, s[2]) / left * tokens / size - 1
        peak = max(peak, ratio)
        if tp_i == 0 and ratio <= -0.25:
            return (proceeds + exit_at(t + delay)) / size - 1, "stop"
        if tp_i < 3 and ratio >= levels[tp_i]:
            part = left if tp_i == 2 else tokens / 3
            sp, _ = state_at(states, mint, t + delay)
            proceeds += sell_sol(sp[0], sp[1], part, sp[2]) - prio
            left -= part
            tp_i += 1
            if left <= 0:
                return proceeds / size - 1, "tp3"
            continue
        if tp_i >= 1 and ratio <= peak - 0.2 * (1 + peak):
            sp, _ = state_at(states, mint, t + delay)
            return (proceeds + sell_sol(sp[0], sp[1], left, sp[2]) - prio) / size - 1, "trailing"
        if tp_i == 0 and t - t_in >= 240 * 60 and ratio < 0.10:
            return (proceeds + exit_at(t + delay)) / size - 1, "time stop"
    s, _ = state_at(states, mint, end)
    return (proceeds + sell_sol(s[0], s[1], left, s[2]) - prio) / size - 1, \
        ("graduacja" if t_done is not None and t_done <= t_end else "koniec danych")


def _fmt(rets: list) -> str:
    if not rets:
        return "brak"
    p, n = sum(x for x in rets if x > 0), -sum(x for x in rets if x < 0)
    pf = f"{p / n:.2f}" if n else "inf"
    return (f"n={len(rets):<4} śr. {statistics.mean(rets):+7.1%}  med. {statistics.median(rets):+7.1%}  "
            f"zysk. {sum(x > 0 for x in rets) / len(rets):4.0%}  PF {pf:>5}")


def run(split: float = 0.6, top: int = 30, size: float = 0.25, min_closed: int = 5, prio: float = 0.001, seed: int = 7,
        min_hold: float = 60, hours: float | None = None):
    if not DB_PATH.exists():
        print("Brak data/stream.db - uruchom najpierw: python collector.py")
        return
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows, states, complete, creators, gaps = load(db, hours)
    if len(rows) < 1000:
        print(f"Za mało danych ({len(rows)} transakcji) - zbieracz musi popracować kilka godzin.")
        return
    t0, t1 = rows[0][1], rows[-1][1]
    ts_split = t0 + split * (t1 - t0)
    fmt_t = lambda t: time.strftime("%d.%m %H:%M", time.localtime(t))
    print(f"dane: {len(rows):,} transakcji, {fmt_t(t0)} - {fmt_t(t1)} ({(t1 - t0) / 3600:.1f} h); luki: {gaps[0]} "
          f"({gaps[1] / 60:.0f} min)")
    print(f"trening: {fmt_t(t0)} - {fmt_t(ts_split)} | test: {fmt_t(ts_split)} - {fmt_t(t1)} | stawka {size} SOL, "
          f"priority fee {prio} SOL na transakcję, opłata pump.fun z transakcji")

    closed = wallet_positions(rows, t0, ts_split, creators)
    stats = wallet_stats(closed)
    pool = eligible(stats, min_closed, min_hold)
    winners = sorted((w for w in pool if stats[w]["pnl"] > 0 and stats[w]["win"] >= 0.5), key=lambda w: -stats[w]["pnl"])
    leaders = winners[:top]
    rnd = random.Random(seed)
    control = rnd.sample(pool, min(len(leaders) or top, len(pool))) if pool else []
    print(f"\n== 1-2) trening: portfeli z zamkniętymi pozycjami {len(stats):,}, do kopiowania (>= {min_closed} pozycji, "
          f"mediana trzymania >= {min_hold:.0f} s, nie boty) {len(pool):,}, z zyskiem i >= 50% wygranych {len(winners):,}"
          f" -> top {len(leaders)} ==")
    if not leaders:
        print("Brak kandydatów na liderów - za mało danych w okresie treningowym.")
        return
    for w in leaders[:10]:
        s = stats[w]
        print(f"  portfel #{w:<8} pozycji {s['n']:>3}  zysk {s['pnl']:+7.2f} SOL  wygranych {s['win']:4.0%}  "
              f"śr. ROI {s['roi']:+6.1%}  mediana trzymania {s['hold'] / 60:5.1f} min")

    # czy wyniki portfeli się utrzymują (sami liderzy, ich własne ceny, okres testowy)
    test_closed = wallet_positions(rows, ts_split, t1 + 1, creators)
    tstats = wallet_stats(test_closed)

    def own(group):
        ps = [proc / cost - 1 for w in group for _, _, _, cost, proc in test_closed.get(w, []) if cost]
        return ps

    # grupa 3: znani traderzy z rankingów MadeOnSol (historia spoza naszych danych), jeśli są w naszym strumieniu
    kol = []
    try:
        import madeonsol
        ids = {a: i for i, a in db.execute("SELECT id, addr FROM wallets")}
        kol = [ids[a] for a in madeonsol.kol_leaders(min_hold / 60) if a in ids]
    except Exception as e:                                     # brak klucza/cache nie może psuć reszty analizy
        print(f"(MadeOnSol pominięty: {e})")

    print(f"\n== czy portfele zarabiają dalej (ich WŁASNE wyniki w okresie testowym, po ich cenach) ==")
    print(f"  top {len(leaders):<3} z treningu      {_fmt(own(leaders))}")
    print(f"  losowe aktywne ({len(control)})      {_fmt(own(control))}")
    print(f"  KOL MadeOnSol ({len(kol)})       {_fmt(own(kol))}")

    print(f"\n== 3) kopiowanie w okresie testowym (jeden zakup na token, stawka {size} SOL) ==")
    for label, group in (("top z treningu", leaders), ("losowe aktywne", control), ("KOL MadeOnSol", kol)):
        if not group:
            print(f"\n  {label}: brak portfeli w danych")
            continue
        sig = leader_signals(rows, set(group), ts_split, t1 + 1, creators)
        once, seen = [], set()
        for s in sig:
            if s[1] not in seen:
                seen.add(s[1])
                once.append(s)
        print(f"\n  {label}: sygnałów (pierwszy zakup tokena) {len(sig)}, różnych tokenów {len(once)}")
        for mode in ("lustro", "zasady bota"):
            for d in DELAYS:
                res = [simulate(s, states, complete, d, size, prio, mode, t1) for s in once]
                ok = [r for r in res if r]
                rets = [r[0] for r in ok]
                tag = "ich cena" if d == 0 else f"+{d} s"
                why = defaultdict(int)
                for _, reason in ok:
                    why[reason] += 1
                print(f"    {mode:<12}{tag:<10}{_fmt(rets)}  suma {sum(rets) * size:+7.2f} SOL"
                      + (f"  | wyjścia: {dict(why)}" if d == 10 else ""))
    print("\n(liczy się porównanie top vs losowe i spadek wyniku z opóźnieniem; kilka godzin danych to dopiero sygnał, nie dowód)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", type=float, default=0.6, help="jaka część danych to trening (reszta = test)")
    ap.add_argument("--top", type=int, default=30, help="ilu najlepszych portfeli kopiujemy")
    ap.add_argument("--size", type=float, default=0.25, help="stawka na wejście w SOL")
    ap.add_argument("--min-closed", type=int, default=5, help="min. zamkniętych pozycji portfela w treningu")
    ap.add_argument("--prio", type=float, default=0.001, help="priority fee + tip na transakcję (SOL)")
    ap.add_argument("--min-hold", type=float, default=60, help="min. mediana trzymania lidera w s (szybszych nie dogonimy)")
    ap.add_argument("--hours", type=float, help="tylko ostatnie tyle godzin danych (domyślnie wszystko)")
    a = ap.parse_args()
    run(a.split, a.top, a.size, a.min_closed, a.prio, min_hold=a.min_hold, hours=a.hours)


if __name__ == "__main__":
    main()
