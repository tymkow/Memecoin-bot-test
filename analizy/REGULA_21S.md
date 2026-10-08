# Reguła 21 s (z tradera Bot D) - 08.10.2026 19:01

Ocen tokenów: 99790 (eksploracja 71164, TEST 28626 od 06.10 13:38). Siatka: 36 reguł x 3 wieki x 2 wyjścia.

Reguł ze średnią > 0 na eksploracji (N >= 100): 0 z 216.

**Najlepsza na eksploracji:** wiek 30 s, portfele >= 60, kupujący w 10 s >= 10, zmiana ceny 2 min >= 0.0, wyjście stały 21 s (jak on) (eksploracja N 577, śr. -1.7%).

## TEST (liczony raz, bez dziur, 0.25 SOL)

| opóźnienie | reguła | baseline: każdy żywy token w wieku 30 s |
|---|---|---|
| 0 s | N 137: śr. -2.8% (CI -8.3..+2.5), med. -5.3%, wygr. 47% | N 3975: śr. -2.8% (CI -3.2..-2.2), med. -2.9%, wygr. 8% |
| 1 s | N 137: śr. -4.5% (CI -9.6..+0.2), med. -6.6%, wygr. 43% | N 3975: śr. -2.7% (CI -3.1..-2.2), med. -2.9%, wygr. 8% |
| 2 s | N 137: śr. -3.9% (CI -8.8..+0.7), med. -5.6%, wygr. 42% | N 3975: śr. -2.8% (CI -3.2..-2.4), med. -2.9%, wygr. 8% |
| 5 s | N 137: śr. -6.3% (CI -11.1..-1.7), med. -5.6%, wygr. 39% | N 3975: śr. -2.9% (CI -3.3..-2.5), med. -2.9%, wygr. 7% |
| 12 s | N 137: śr. -5.3% (CI -10.3..-0.7), med. -3.9%, wygr. 41% | N 3975: śr. -3.0% (CI -3.3..-2.6), med. -2.9%, wygr. 7% |

Z dziurami, d = 2 s: N 440: śr. -5.3% (CI -8.3..-2.1), med. -2.9%, wygr. 38%; migracja przed wyjściem: 3.

Werdykt (d = 2 s): **nie działa** (CI obejmuje 0 albo wynik <= 0).
