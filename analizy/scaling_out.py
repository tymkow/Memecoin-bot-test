"""4. CZĘŚCIOWA REALIZACJA ZYSKU (scaling out) - schematy sprzedaży części pozycji vs obecne wyjście bota.

Schemat = lista (próg zysku, część pozycji) + trailing po pierwszej realizacji + ewentualny stop na break-even
(po osiągnięciu progu be_at stop przesuwa się na cenę wejścia). Wszędzie SL -25% i time stop 4 h jak w bocie.
Wyniki w stawkach (1 = cała stawka); max DD liczony po kolei w czasie; wybór schematu na eksploracji, TEST raz.
"""
from __future__ import annotations

import statistics

from analizy import common as C

FAR = 99.0   # "reszta pozycji bez TP" = próg nieosiągalny, zamyka trailing/stop/time stop
SCHEMES = {
    "S0 obecny: 1/3 @+50%, 1/3 @+100%, reszta @+300%, trailing 20%": dict(tp=C.er.tp_plan(C.CFG.take_profit_levels), trail=0.20),
    "S1 25% @+20%, reszta trailing 20%": dict(tp=[(0.2, 0.25), (FAR, None)], trail=0.20),
    "S2 50% @+20%, reszta trailing 20%": dict(tp=[(0.2, 0.5), (FAR, None)], trail=0.20),
    "S3 50% @+30%, reszta break-even + trailing 25%": dict(tp=[(0.3, 0.5), (FAR, None)], trail=0.25, be_at=0.3),
    "S4 25% @+20%, 25% @+50%, reszta trailing 20%": dict(tp=[(0.2, 0.25), (0.5, 0.25), (FAR, None)], trail=0.20),
    "S5 50% @+50%, reszta trailing 20%": dict(tp=[(0.5, 0.5), (FAR, None)], trail=0.20),
    "S6 33% @+20% + break-even, potem 1/3 @+100%, reszta @+300%": dict(tp=[(0.2, 0.33), (1.0, 0.33), (3.0, None)], trail=0.20, be_at=0.2),
    "S7 100% @+20% (całość)": dict(tp=[(0.2, None)], trail=0.20),
}


def run(ents, scheme):
    kw = SCHEMES[scheme]
    return [C.sim(e["path"], e["ref"], e["path"][0][0], stop_frac=0.25, tp=kw["tp"], trail=kw["trail"],
                  time_stop=(C.CFG.time_stop_minutes, C.CFG.time_stop_min_move_pct / 100), be_at=kw.get("be_at"))
            for e in ents]


def section(title, ents):
    ex, te = C.split_time(ents)
    out = [f"\n**{title}** - wejść {len(ents)} (eksploracja {len(ex)}, TEST {len(te)})\n"]
    rows, res = [], {}
    for s in SCHEMES:
        res[s] = (run(ex, s), run(te, s))
        for lbl, xs in (("eksploracja", res[s][0]), ("TEST", res[s][1])):
            rows.append([s, lbl, f"{len(xs)}{C.rel(len(xs))}", f"{sum(xs):+.2f}", C.pct(C.mean(xs)),
                         f"{statistics.pstdev(xs):.2f}" if len(xs) > 1 else "—", f"{C.max_drawdown(xs):.2f}",
                         f"{C.mean([x > 0 for x in xs]):.0%}"])
    out.append(C.table(["schemat", "zbiór", "N", "suma (stawki)", "śr.", "odch. std", "max DD", "% zyskownych"], rows))
    base = list(SCHEMES)[0]
    best = max((s for s in SCHEMES if s != base), key=lambda s: C.mean(res[s][0]))
    d_ex = C.mean(res[best][0]) - C.mean(res[base][0])
    d_te = C.mean(res[best][1]) - C.mean(res[base][1])
    diffs = [a - b for a, b in zip(res[best][1], res[base][1])]
    lo, hi = C.boot_ci(diffs)
    out.append(f"\nNajlepszy na eksploracji: **{best.split(' ')[0]}** (+{d_ex * 100:.1f} pp vs obecny). TEST: {d_te * 100:+.1f} pp "
               f"(95% CI różnicy w parach {lo * 100:+.1f}..{hi * 100:+.1f} pp) -> "
               f"{'TRZYMA SIĘ' if d_te > 0 and lo > 0 else ('kierunek się zgadza, ale CI obejmuje 0' if d_te > 0 else 'NIE trzyma się')}.")
    return "\n".join(out)


def report() -> str:
    bot = C.bot_entry_set()
    mig = C.migration_entries(30)
    C.add_outcomes(bot)
    C.add_outcomes(mig)
    C.variant_eval("S6 zamiast obecnego wyjścia (część 4) - wejścia bota", bot, "s6")
    C.variant_eval("S6 zamiast obecnego wyjścia (część 4) - migracje + 30 min", mig, "s6")
    return "\n".join(["## 4. Częściowa realizacja zysku (scaling out)",
                      section("Wejścia bota (świece z archiwum)", bot),
                      section("Migracje + 30 min (wszystkie żywe tokeny)", mig)])


if __name__ == "__main__":
    print(report())
