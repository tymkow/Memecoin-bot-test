# Reguła "przetrwał start" (z tradera Bot C) - 08.10.2026 18:51

Ocen tokenów: 35421 (eksploracja 25039, TEST 10382 od 06.10 11:54). Siatka: 36 reguł x 3 wieki x 3 wyjścia.

Reguł ze średnią > 0 na eksploracji (N >= 100): 0 z 324.

**Najlepsza na eksploracji:** wiek 90 s, portfele >= 100, kupujący w 10 s >= 5, zmiana ceny 2 min >= 0.2, wyjście stały 300 s (eksploracja N 379, śr. -1.8%).

## TEST (liczony raz, bez dziur, 0.25 SOL)

| opóźnienie | reguła | baseline: każdy żywy token w wieku 90 s |
|---|---|---|
| 2 s | N 107: śr. -16.6% (CI -30.2..-2.3), med. -42.0%, wygr. 28% | N 1398: śr. -6.9% (CI -8.8..-4.8), med. -3.8%, wygr. 11% |
| 5 s | N 107: śr. -17.1% (CI -29.9..-3.4), med. -40.8%, wygr. 31% | N 1398: śr. -7.0% (CI -8.8..-5.1), med. -3.7%, wygr. 11% |
| 12 s | N 107: śr. -13.0% (CI -26.4..+1.4), med. -36.4%, wygr. 34% | N 1398: śr. -6.4% (CI -8.2..-4.2), med. -3.5%, wygr. 11% |
| 20 s | N 107: śr. -14.0% (CI -27.1..+0.1), med. -36.8%, wygr. 31% | N 1398: śr. -6.1% (CI -8.0..-3.9), med. -3.4%, wygr. 11% |

Z dziurami, d = 5 s: N 295: śr. -14.7% (CI -21.8..-6.9), med. -32.7%, wygr. 33%; migracja przed wyjściem: 18.

Werdykt (d = 5 s): **nie działa** (CI obejmuje 0 albo wynik <= 0).
