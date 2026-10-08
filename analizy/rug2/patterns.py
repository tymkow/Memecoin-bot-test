"""Wzorce wykresu, które użytkownik widzi jako "oczywisty rug" (7.10, po ślepym teście) - zamienione na liczby z ceny
DO chwili T (minutowe zamknięcia: krzywa ze zbieracza + świece po migracji) i sprawdzone na wyniku pozycji po kosztach.
Progi USTALONE Z OPISU, przed spojrzeniem na wyniki:
  prosta    log ceny ~ czas w oknie [migracja, T]: R^2 >= 0,85 i nachylenie > 0 ("prosta linia do góry")
  schodki   >= 4 minuty z +3% lub więcej, wielkość tych wzrostów podobna (CV < 0,5), żaden zjazd minutowy < -5%
  zygzak    wśród ruchów minutowych |r| > 1%: >= 60% zmian kierunku
  V         od szczytu spadek >= 40%, potem w T cena >= 1,5 x dołek ("mocno spadło, potem pompa = kolejny dump")
Każdy wzorzec jako filtr "NIE kupuj, gdy wzorzec" (hipoteza: to rugi) i odwrotnie; eksploracja 70% / TEST 30%.

    python -m analizy.rug2.patterns
"""
from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path

from analizy import common as C

HERE = Path(__file__).resolve().parent


def minute_closes(e: dict, stream) -> list[tuple]:
    """[(minuta od startu, cena USD)] - ostatnia cena w każdej minucie, tylko dane < T."""
    T, c0, out = e["ts"], e["created_ts"], {}
    for ts, vsol, vtok in stream.execute("SELECT ts, vsol, vtok FROM trades WHERE mint_id=? AND ts < ? AND ts < ? "
                                         "ORDER BY slot", (e["mint_id"], T, e["mig_ts"] + 1)):
        if vtok:
            out[int((ts - c0) // 60)] = float(vsol) / 1e9 / (float(vtok) / 1e6) * C.SOL_USD
    for t, o, h, l, cl, v in e["pre"]:
        if t + 60 <= T and t >= e["mig_ts"] - 60:
            out[int((t - c0) // 60)] = cl
    return sorted(out.items())


def features(series: list[tuple], mig_min: float) -> dict:
    post = [(m, p) for m, p in series if m >= mig_min - 1 and p > 0]
    f = {"straight": 0, "steps": 0, "zigzag": 0, "vshape": 0}
    if len(post) >= 8:
        xs, ys = [m for m, _ in post], [math.log(p) for _, p in post]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0
        ss = sum((y - my) ** 2 for y in ys)
        r2 = 1 - sum((y - (my + b * (x - mx))) ** 2 for x, y in zip(xs, ys)) / ss if ss else 0
        f["r2"], f["slope"] = r2, b
        f["straight"] = int(r2 >= 0.85 and b > 0)
        rets = [post[i][1] / post[i - 1][1] - 1 for i in range(1, len(post))]
        ups = [r for r in rets if r >= 0.03]
        f["steps"] = int(len(ups) >= 4 and statistics.pstdev(ups) / statistics.mean(ups) < 0.5 and min(rets) > -0.05)
        big = [r for r in rets if abs(r) > 0.01]
        flips = sum(1 for a, c in zip(big, big[1:]) if (a > 0) != (c > 0))
        f["zigzag"] = int(len(big) >= 6 and flips / (len(big) - 1) >= 0.6)
    prices = [p for _, p in series if p > 0]
    if len(prices) >= 5:
        i_pk = max(range(len(prices)), key=lambda i: prices[i])
        after = prices[i_pk:]
        lo = min(after)
        f["vshape"] = int(lo <= prices[i_pk] * 0.6 and prices[-1] >= lo * 1.5)
    return f


def main():
    import rug_dataset as rd
    stream = rd.ro(rd.STREAM_DB)
    ents = C.migration_entries(30)
    C.add_outcomes(ents)
    for e in ents:
        e.update(features(minute_closes(e, stream), (e["mig_ts"] - e["created_ts"]) / 60))
    ex, te = C.split_time(ents)
    ratings = {}
    p = HERE / "blind" / "oceny.csv"
    if p.exists():
        ratings = {r["mint"]: r["choice"] for r in csv.DictReader(open(p, encoding="utf-8"))}
    out = ["## Wzorce wykresu użytkownika (prosta / schodki / zygzak / V) - na wyniku po kosztach\n",
           (__doc__ or "").split("Progi", 1)[1].split("    python")[0].join(["Progi", ""]), ""]
    rows = []
    for k, name in (("straight", "prosta linia do góry"), ("steps", "schodki"), ("zigzag", "zygzak"),
                    ("vshape", "spadek, potem pompa (V)")):
        for lbl, s in (("eksploracja", ex), ("TEST", te)):
            y = [e for e in s if e[k]]
            n = [e for e in s if not e[k]]
            rows.append([name, lbl, f"{len(y)}{C.rel(len(y))} ({len(y) / len(s):.0%})", C.pct(C.mean([e['s0'] for e in y])),
                         C.pct(C.mean([e['s0'] for e in n])), C.pct(C.mean([e['s6'] for e in y])),
                         f"{C.mean([e['rug'] for e in y]):.0%} / {C.mean([e['rug'] for e in n]):.0%}" if y else "—"])
        rat = [ratings[e["mint"]] for e in ents if e[k] and e["mint"] in ratings]
        if rat:
            rows.append([name, "Twoje oceny", f"{len(rat)}", f"'nie kupić' {sum(r == 'nie' for r in rat) / len(rat):.0%}", "", "", ""])
    out.append(C.table(["wzorzec", "zbiór", "N z wzorcem (udział)", "wynik z wzorcem", "wynik bez wzorca", "S6 z wzorcem",
                        "rug (e) z / bez"], rows))
    out.append("\n**Filtry \"nie kupuj, gdy wzorzec\" (vs baseline i oczekiwany random_eligible na TEŚCIE):**\n")
    frows = []
    for k, name in (("straight", "prosta"), ("steps", "schodki"), ("zigzag", "zygzak"), ("vshape", "V")):
        for ycol in ("s0", "s6"):
            frows.append(C.filter_eval(f"wzorzec {name}: nie kupuj ({ycol.upper()})", ents, lambda e, k=k: not e[k], ycol))
            frows.append(C.filter_eval(f"wzorzec {name}: kupuj TYLKO z nim ({ycol.upper()})", ents, lambda e, k=k: bool(e[k]), ycol))
    out.append(C.table(C.FILTER_HEAD, frows))
    txt = "\n".join(out)
    (HERE / "PATTERNS.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
