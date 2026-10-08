"""3. DYNAMICZNY STOP LOSS - poszerzenie SL w dół tylko pod warunkami.

Warunki (w chwili, gdy cena dotyka obecnego SL -25%):
  płynność stabilna: L_t / L_0 >= 0.9 * sqrt(P_t / P_0)
      (pula stałego iloczynu bez dodawania/wycofania LP: L_t/L_0 = sqrt(P_t/P_0); spadek płynności większy niż
       wynika z ceny = wycofanie płynności). L, P z migawek bota (co ~10 s). Brak migawki w 2 min = brak zgody.
  sweep, nie trend: w ciągu N=2 świec od dotknięcia cena zamyka się z powrotem nad poziomem -25% (czekanie kosztuje:
      bez powrotu wychodzimy po zamknięciu N-tej świecy, nie na poziomie stopa).
  dev nie sprzedaje: brak danych historycznych dla wszystkich wejść (bot widzi sprzedaż dev tylko w transakcjach
      GeckoTerminal; zapisuje tylko jako powód wyjścia) - do logowania na żywo, tu nietestowalne.
Warianty: B0 = obecny SL -25% (baseline), B1 = stały SL -40%, D1 = płynność -> SL -40%, D2 = sweep -> SL -40%,
D3 = płynność i sweep -> SL -40%, D4 = SL -40% + strażnik płynności (wyjście, gdy L_t/L_0 < 0.7 * sqrt(P_t/P_0)).
TP, trailing i time stop jak w bocie; koszty jak exit_research (wejście 1.5%, wyjście 4%, krach w świecy -> low).
"""
from __future__ import annotations

import bisect
import math

import exit_research as er
from analizy import common as C

WIDE = 0.40
N_CONFIRM = 2
VARIANTS = ("B0 SL-25% (baseline)", "B1 SL-40% stały", "D1 płynność->SL-40%", "D2 sweep->SL-40%",
            "D3 płynność+sweep->SL-40%", "D4 SL-40% + strażnik płynności")


def liq_ratio(snaps, t, p0, l0, mint=""):
    """Płynność / oczekiwana w puli stałego iloczynu (od 7.10 z wirtualną rezerwą SOL PumpSwap -
    common.liq_vs_expected) z ostatniej migawki do t (max 120 s wstecz); None = brak danych."""
    if not snaps or not l0 or not p0:
        return None
    i = bisect.bisect_right([s[0] for s in snaps], t) - 1
    if i < 0 or t - snaps[i][0] > 120 or not snaps[i][1] or not snaps[i][2]:
        return None
    return C.liq_vs_expected(l0, p0, snaps[i][2], snaps[i][1], mint)


def simulate(path, ref, ts0, variant: str, snaps=None, p0=None, l0=None, mint="") -> float:
    tp = er.tp_plan(C.CFG.take_profit_levels)
    trail = C.CFG.trailing_stop_pct / 100
    tstop = (C.CFG.time_stop_minutes, C.CFG.time_stop_min_move_pct / 100)
    tokens, left, proceeds, tp_i, peak = 1.0 / (ref * (1 + er.EC)), 1.0, 0.0, 0, ref
    lvl25 = ref * 0.75
    wide0 = variant.startswith(("B1", "D4"))
    stop = ref * (1 - WIDE) if wide0 else lvl25
    widened, pending = wide0, None

    def sell(px):
        return proceeds + left * tokens * px * (1 - er.XC) - 1

    for idx, (t, o, h, l, c, v) in enumerate(path):
        mins = (t - ts0) / 60
        if variant.startswith("D4"):
            lr = liq_ratio(snaps, t + 60, p0, l0, mint)
            if lr is not None and lr < 0.7:
                return sell(c)
        if pending is not None:                          # czekamy na powrót nad -25%
            if l <= ref * (1 - WIDE):
                return sell(l if (o > 0 and l / o < er.CRASH) else min(o, ref * (1 - WIDE)))
            if c > lvl25:
                pending, widened, stop = None, True, ref * (1 - WIDE)
                continue
            if idx >= pending:
                return sell(c)
            continue
        trail_lvl = peak * (1 - trail) if tp_i >= 1 else None
        lvl = max(x for x in (stop, trail_lvl) if x is not None)
        if l <= lvl:
            if not widened and lvl == stop and variant[:2] in ("D1", "D2", "D3"):
                liq_ok = (lr := liq_ratio(snaps, t + 60, p0, l0, mint)) is not None and lr >= 0.9
                if variant.startswith("D1") and liq_ok:
                    widened, stop = True, ref * (1 - WIDE)
                elif variant.startswith("D2") or (variant.startswith("D3") and liq_ok):
                    if c > lvl25:                         # powrót w tej samej świecy
                        widened, stop = True, ref * (1 - WIDE)
                    else:
                        pending = idx + N_CONFIRM - 1
                        if pending == idx:
                            return sell(c)
                        continue
                if widened:
                    if l <= stop:
                        return sell(l if (o > 0 and l / o < er.CRASH) else min(o, stop))
                else:
                    return sell(l if (o > 0 and l / o < er.CRASH) else min(o, lvl))
            else:
                return sell(l if (o > 0 and l / o < er.CRASH) else min(o, lvl))
        while tp_i < len(tp) and h >= ref * (1 + tp[tp_i][0]):
            px = max(o, ref * (1 + tp[tp_i][0]))
            frac = left if tp[tp_i][1] is None else min(tp[tp_i][1], left)
            proceeds += frac * tokens * px * (1 - er.XC)
            left -= frac
            tp_i += 1
            if left <= 1e-9:
                return proceeds - 1
        peak = max(peak, h)
        if tstop and tp_i == 0 and mins >= tstop[0] and c < ref * (1 + tstop[1]):
            return sell(c)
    return sell(path[-1][4] if path else ref)


def metrics(xs: list, rug_flags: list) -> dict:
    rugs = [x for x, r in zip(xs, rug_flags) if r]
    return {"n": len(xs), "mean": C.mean(xs), "sum": sum(xs), "mdd": C.max_drawdown(xs), "worst": min(xs) if xs else None,
            "rug_n": len(rugs), "rug_mean": C.mean(rugs)}


def run(ents, with_liq: bool):
    res = {}
    for v in VARIANTS:
        if not with_liq and v[:2] in ("D1", "D3", "D4"):
            continue
        xs = [simulate(e["path"], e["ref"], e["path"][0][0], v, e.get("snaps"), e.get("p0"), e.get("l0"), e["mint"]) for e in ents]
        res[v] = (xs, metrics(xs, [e["rug6h"] for e in ents]))
    return res


def prep_bot():
    """Wszystkie wejścia bota (C.bot_entry_set - ten sam zestaw co części 4 i 6). Bez migawek płynności warunek
    płynności = brak danych -> brak poszerzenia (wariant zachowuje się jak baseline)."""
    ents = []
    for e in C.bot_entry_set():
        after = [s for s in e.get("snaps", []) if s[0] >= e["ts"] - 30 and s[1] and s[2]]
        e["p0"], e["l0"] = (after[0][1], after[0][2]) if after else (None, None)
        e["snaps"] = after
        e["rug6h"] = e["mae"] <= -0.80
        ents.append(e)
    return ents


def prep_mig():
    ents = C.migration_entries(30)
    for e in ents:
        e["rug6h"] = e["mae"] <= -0.80
    return ents


def section(title, ents, with_liq):
    ex, te = C.split_time(ents)
    out = [f"\n**{title}** - wejść {len(ents)} (eksploracja {len(ex)}, TEST {len(te)}); rug = token spadł <= -80% w 6 h.\n"]
    rex, rte = run(ex, with_liq), run(te, with_liq)
    rows = []
    for v in rex:
        for lbl, r in (("eksploracja", rex[v][1]), ("TEST", rte[v][1])):
            rows.append([v, lbl, f"{r['n']}{C.rel(r['n'])}", C.pct(r["mean"]), f"{r['sum']:+.2f}", f"{r['mdd']:.2f}",
                         C.pct(r["worst"], 0), f"{r['rug_n']}{C.rel(r['rug_n'])}", C.pct(r["rug_mean"])])
    out.append(C.table(["wariant", "zbiór", "N", "śr. wynik", "suma (stawki)", "max DD (stawki)", "najgorsza", "N rugów",
                        "śr. na rugach"], rows))
    best = max((v for v in rex if not v.startswith("B0")), key=lambda v: rex[v][1]["mean"])
    b0e, b0t = rex[VARIANTS[0]][1]["mean"], rte[VARIANTS[0]][1]["mean"]
    be, bt = rex[best][1]["mean"], rte[best][1]["mean"]
    worse = sum(1 for a, b, e in zip(rte[best][0], rte[VARIANTS[0]][0], te) if e["rug6h"] and a < b - 1e-9)
    nr = sum(1 for e in te if e["rug6h"])
    out.append(f"\nNajlepszy na eksploracji: **{best}** ({C.pct(be)} vs baseline {C.pct(b0e)}). TEST: {C.pct(bt)} vs baseline "
               f"{C.pct(b0t)} -> {'żaden wariant nie bije baseline już na eksploracji' if be <= b0e else ('TRZYMA SIĘ' if bt > b0t else 'NIE trzyma się')}. "
               f"Na rugach w teście szerszy SL dał "
               f"gorszy wynik niż -25% w {worse}/{nr} przypadków{C.rel(nr)}.")
    return "\n".join(out)


def report() -> str:
    bot = prep_bot()
    n_liq = sum(1 for e in bot if len(e["snaps"]) >= 5)
    return "\n".join(["## 3. Dynamiczny stop loss",
                      section(f"Wejścia bota (ten sam zestaw co części 4, 6, 7; z pomiarami płynności {n_liq})", bot, True),
                      section("Migracje + 30 min (bez danych o płynności: tylko B0/B1/D2)", prep_mig(), False)])


if __name__ == "__main__":
    print(report())
