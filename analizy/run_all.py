"""Składa raport wszystkich analiz do analizy/RAPORT.md (część 1b - klasteryzacja - z pliku, bo wymaga scikit-learn).

    python -m analizy.run_all
"""
import time
from pathlib import Path

from analizy import common as C
from analizy import (bundles, copycoins, costs, crash_gap, dynamic_sl, first_buyers, live_eval, manipulation,
                     result_model, rug_definitions, scaling_out, sweeps)

HERE = Path(__file__).resolve().parent

INTRO = f"""# Raport analiz - Memecoin Bot ({time.strftime('%d.%m.%Y %H:%M')})

Zasady: podział czasowy 70% eksploracja / 30% TEST (wnioski tylko, gdy trzymają się na teście); N przy każdym
wyniku, N < {C.MIN_N} = "niewiarygodny"; zawsze porównanie z baseline = obecne reguły bota; logika bota nietknięta.
**Od 6.10 wieczorem także porównanie z random_eligible** (jedyna strategia dodatnia brutto): filtr, który go nie bije,
nie ma wartości. random_eligible = losowe 25% tokenów, które przeszły twarde filtry bota, więc jego OCZEKIWANY wynik na
danym zbiorze to średnia po tokenach tego zbioru z sygnałem safety_only (przeszły filtry), w tym samym oknie TESTU i tą
samą symulacją (porównanie 1:1). Faktyczne pozycje random_eligible są za nieliczne na okna testów (58 w 5 dni; w oknie
testu migracji 3) - ich wynik jest w notce pod tabelą zbiorczą. W zbiorze wejść bota każde wejście przeszło filtry, więc
tam oczekiwany random_eligible = baseline.
Wyniki wejść w stawkach (1 = cała stawka), po kosztach (wejście 1.5%, wyjście 4%, krach w świecy -> low).
Etykieta tokena (potrójna bariera od ceny wejścia, 6 h): -70% najpierw = rug, +50% najpierw = pump, żadne = nic.

**Poprawka 6.10 wieczorem - rozbieżność baseline (część 3: -8,0% TEST vs część 4: -12,2% TEST):** to samo wyjście
(SL -25%, TP 50/100/300 po 1/3, trailing 20%, time stop 4 h) i te same koszty (wejście 1,5%, wyjście 4%); oba symulatory
dają ten sam wynik na tych samych wejściach (różnica <= 0,4 pp na wejściu: część 4 brała TP po dokładnie 1/3, bot ma
0,33). Różnica wynikała z ZESTAWU wejść: część 3 brała tylko wejścia z >= 5 migawkami płynności (233 z 260) - 27
wykluczonych to szybko umierające tokeny (-32% na wejście, 78% rugów), więc jej baseline był zawyżony (przeżycie).
Teraz części 3, 4, 6 i 7 liczą na TYM SAMYM zestawie (`common.bot_entry_set`); w części 3 wejście bez danych
o płynności = brak poszerzenia stopa.
"""

PARTS = (("0", crash_gap), ("1", first_buyers), ("2", sweeps), ("3", dynamic_sl), ("4", scaling_out),
         ("5", manipulation), ("6", rug_definitions), ("7", costs), ("8", bundles), ("9", copycoins),
         ("10", result_model), ("11", live_eval))


def random_eligible_note() -> str:
    rows = costs.real_rows()
    out = []
    for s in ("random_eligible", "safety_only"):
        xs = [r for r in rows if r["s"] == s]
        net = [r["net"] / r["stake"] for r in xs]
        lo, hi = C.boot_ci(net)
        out.append([s, f"{len(xs)}", C.pct(C.mean(net)), f"{lo * 100:+.1f}..{hi * 100:+.1f}%",
                    C.pct(C.mean([r["gross"] / r["stake"] for r in xs]))])
    return ("\n**Czym jest random_eligible:** losowe ~25% tokenów (hash mintu), które przeszły TE SAME twarde filtry co "
            "safety_only - ten sam rynek, losowy podzbiór. Jego oczekiwany wynik = wynik safety_only; różnica to "
            "przede wszystkim losowość małej próby:\n\n" +
            C.table(["strategia", "pozycji", "netto na pozycję", "95% CI netto", "brutto na pozycję"], out) + "\n")


def main():
    C.SUMMARY.clear()
    parts = []
    for name, mod in PARTS:
        t0 = time.time()
        parts.append(mod.report())
        print(f"część {name}: {time.time() - t0:.0f} s", flush=True)
        if name == "1" and (HERE / "first_buyers_cluster.md").exists():
            parts.append((HERE / "first_buyers_cluster.md").read_text(encoding="utf-8"))
    summary = ["## Tabela zbiorcza: hipoteza -> eksploracja (train) -> TEST -> N -> vs random_eligible -> werdykt\n",
               "Werdykt POTWIERDZONE = na teście lepsze od baseline, lepsze od oczekiwanego random_eligible (tokeny po "
               "filtrach bota z tego samego zbioru i okna), p losowego podzbioru < 0,10 i N >= 30 (filtry) albo CI różnicy "
               "w parach > 0 (warianty wyjścia). \"p losowe\" = szansa, że LOSOWY wybór tylu samych tokenów z testu da "
               "średnią co najmniej taką jak filtr.\n",
               C.table(C.FILTER_HEAD, C.SUMMARY), random_eligible_note()]
    (HERE / "RAPORT.md").write_text("\n\n".join([INTRO, "\n".join(summary)] + parts), encoding="utf-8")
    print(f"zapisano {HERE / 'RAPORT.md'}")


if __name__ == "__main__":
    main()
