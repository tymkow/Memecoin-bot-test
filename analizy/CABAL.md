# Grupy portfeli kupujących razem - 08.10.2026 18:25

Tokeny z pełnym oknem: 53458 (eksploracja 37420, TEST 16038 od 06.10 14:12). Wykryte grupy (eksploracja): 815, portfeli w grupach 5623; rozmiary: największe [2045, 36, 34, 30, 27, 27, 19, 19, 18, 16], mediana 4.

Sygnałów: eksploracja 52723, test 16653 (tokenów z sygnałem w teście: 4760 z 16038). Mediana wieku tokena przy sygnale: 4 s.

**Wybór na eksploracji (d = 5 s, bez dziur):** M = 2, wyjście za grupą (1. sprzedaż członka); grup z >= 5 sygnałami: 421, z nich ze średnią > 0: 114.

## Eksploracja - wszystkie sygnały grup (d = 5 s, bez dziur)

| sygnał | wyjście | wynik |
|---|---|---|
| M=2 | za grupą (1. sprzedaż członka) | N 13975: śr. -3.2% (CI -3.9..-2.5), med. -3.3%, wygr. 24% |
| M=2 | stały 60 s | N 13975: śr. -5.6% (CI -6.3..-4.9), med. -10.0%, wygr. 29% |
| M=2 | stały 300 s | N 13975: śr. -7.9% (CI -9.1..-6.6), med. -24.2%, wygr. 20% |
| M=2 | TP +30% / SL -20% | N 13975: śr. -5.4% (CI -5.9..-4.9), med. -13.0%, wygr. 31% |
| M=3 | za grupą (1. sprzedaż członka) | N 10492: śr. -3.9% (CI -4.6..-3.2), med. -3.0%, wygr. 22% |
| M=3 | stały 60 s | N 10492: śr. -6.3% (CI -7.1..-5.4), med. -11.8%, wygr. 28% |
| M=3 | stały 300 s | N 10492: śr. -9.1% (CI -10.6..-7.6), med. -26.4%, wygr. 18% |
| M=3 | TP +30% / SL -20% | N 10492: śr. -5.8% (CI -6.4..-5.2), med. -14.2%, wygr. 31% |

## TEST (liczony raz): M = 2, wyjście za grupą (1. sprzedaż członka), 0.25 SOL, bez dziur

| opóźnienie | wybrane grupy (114) | wszystkie grupy | baseline: każdy token w wieku 4 s |
|---|---|---|---|
| 1 s | N 395: śr. -2.1% (CI -6.5..+2.5), med. -8.7%, wygr. 33% | N 2536: śr. -4.8% (CI -6.1..-3.4), med. -4.8%, wygr. 25% | N 794: śr. -6.1% (CI -8.4..-3.6), med. -3.2%, wygr. 8% |
| 2 s | N 395: śr. -2.0% (CI -6.4..+2.7), med. -8.2%, wygr. 32% | N 2536: śr. -4.9% (CI -6.2..-3.6), med. -4.5%, wygr. 24% | N 794: śr. -6.4% (CI -8.5..-4.2), med. -3.2%, wygr. 9% |
| 5 s | N 395: śr. -1.1% (CI -5.6..+3.8), med. -6.9%, wygr. 32% | N 2535: śr. -4.4% (CI -5.8..-3.0), med. -3.2%, wygr. 23% | N 796: śr. -6.2% (CI -8.1..-4.1), med. -3.1%, wygr. 8% |
| 12 s | N 395: śr. -0.7% (CI -4.5..+3.6), med. -5.0%, wygr. 31% | N 2534: śr. -4.4% (CI -5.6..-3.2), med. -2.9%, wygr. 20% | N 801: śr. -6.0% (CI -7.9..-3.8), med. -3.0%, wygr. 7% |
| 20 s | N 395: śr. -0.5% (CI -4.6..+3.9), med. -4.0%, wygr. 32% | N 2534: śr. -4.0% (CI -5.2..-2.8), med. -2.9%, wygr. 19% | N 804: śr. -6.3% (CI -8.1..-4.4), med. -3.0%, wygr. 5% |

Test z dziurami włącznie, d = 5 s: wybrane grupy N 1244: śr. -4.8% (CI -7.6..-2.0), med. -9.1%, wygr. 28%; z migracją przed wyjściem: 25.

Werdykt dla wejścia za wybranymi grupami po 5 s: **nie działa** (CI obejmuje 0, wynik <= 0 albo N < 30).
