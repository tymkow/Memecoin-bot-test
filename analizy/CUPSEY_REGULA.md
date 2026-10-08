# Reguła wejścia Cupseya stosowana samodzielnie - 08.10.2026 11:14

Pytanie: czy wejścia, które Cupsey wybiera (start pump.fun z tłumem w pierwszych sekundach - CUPSEY_SYGNALY.md), zarabiają, gdy sami stosujemy regułę na WSZYSTKICH nowych tokenach - bez kopiowania go, po naszym opóźnieniu i kosztach. Metoda w nagłówku `analizy/cupsey_rule.py`.

- Dane: stream.db 04.10 10:23 - 07.10 19:32; tokeny z zapisanym utworzeniem i pełnymi 330 s po nim: **70039** (trening 54758, test 15281).
- Podział czasu: **06.10 20:33** (późniejszy z: 70% okna = 06.10 19:11, podział drzew Cupseya = 06.10 20:32 - progi z drzew nie widziały testu).
- Dziury w strumieniu (> 5 s bez transakcji): 1240, w tym 4 przerw > 30 min (29.2 h). Tokeny z migracją w ciągu 315 s od startu: 1127.
- Koszty: opłata pump.fun z transakcji (zwykle 1.25% w każdą stronę), poślizg krzywej, 0.0005 SOL za transakcję. Wynik = % stawki po wszystkim. d = 0 s to odniesienie nieosiągalne.

## 1. Baseline - wejście w KAŻDY nowy token w tym wieku (test, bez dziur, 0.25 SOL)

| wiek | wyjście | d = 0 s | d = 1 s | d = 2 s | d = 5 s |
|---|---|---|---|---|---|
| 5 s | jak on (5 s bez napływu) | N 12468: śr. -3.2%, med. -2.9%, wygr. 14% | N 12176: śr. -3.6%, med. -2.9%, wygr. 14% | N 11828: śr. -3.7%, med. -2.9%, wygr. 14% | N 11073: śr. -3.7%, med. -2.9%, wygr. 14% |
| 5 s | stały czas 15 s | N 11128: śr. -2.4%, med. -2.9%, wygr. 19% | N 11015: śr. -2.7%, med. -2.9%, wygr. 18% | N 10898: śr. -2.8%, med. -2.9%, wygr. 17% | N 10591: śr. -3.1%, med. -2.9%, wygr. 16% |
| 5 s | stały czas 60 s | N 8420: śr. -2.0%, med. -2.9%, wygr. 18% | N 8404: śr. -2.3%, med. -2.9%, wygr. 17% | N 8375: śr. -2.0%, med. -2.9%, wygr. 16% | N 8290: śr. -1.3%, med. -2.9%, wygr. 15% |
| 5 s | TP +30% / SL -20% | N 8723: śr. -3.0%, med. -4.2%, wygr. 28% | N 8517: śr. -3.6%, med. -4.2%, wygr. 26% | N 8337: śr. -3.7%, med. -3.9%, wygr. 25% | N 7840: śr. -4.1%, med. -3.7%, wygr. 22% |
| 10 s | jak on (5 s bez napływu) | N 11709: śr. -4.0%, med. -2.9%, wygr. 11% | N 11455: śr. -3.8%, med. -2.9%, wygr. 12% | N 11216: śr. -3.2%, med. -2.9%, wygr. 13% | N 10549: śr. -2.8%, med. -2.9%, wygr. 13% |
| 10 s | stały czas 15 s | N 10591: śr. -3.1%, med. -2.9%, wygr. 16% | N 10506: śr. -3.0%, med. -2.9%, wygr. 16% | N 10425: śr. -2.6%, med. -2.9%, wygr. 15% | N 10184: śr. -2.8%, med. -2.9%, wygr. 14% |
| 10 s | stały czas 60 s | N 8290: śr. -1.3%, med. -2.9%, wygr. 15% | N 8261: śr. -1.6%, med. -2.9%, wygr. 15% | N 8243: śr. -1.3%, med. -2.9%, wygr. 15% | N 8180: śr. -0.8%, med. -2.9%, wygr. 14% |
| 10 s | TP +30% / SL -20% | N 8063: śr. -4.2%, med. -3.5%, wygr. 24% | N 7911: śr. -4.1%, med. -3.4%, wygr. 23% | N 7802: śr. -3.6%, med. -3.3%, wygr. 23% | N 7441: śr. -2.4%, med. -3.1%, wygr. 21% |
| 15 s | jak on (5 s bez napływu) | N 11106: śr. -3.0%, med. -2.9%, wygr. 10% | N 10871: śr. -2.8%, med. -2.9%, wygr. 11% | N 10636: śr. -3.0%, med. -2.9%, wygr. 12% | N 10137: śr. -3.6%, med. -2.9%, wygr. 12% |
| 15 s | stały czas 15 s | N 10184: śr. -2.8%, med. -2.9%, wygr. 14% | N 10115: śr. -2.8%, med. -2.9%, wygr. 14% | N 10032: śr. -3.1%, med. -2.9%, wygr. 14% | N 9828: śr. -3.3%, med. -2.9%, wygr. 13% |
| 15 s | stały czas 60 s | N 8180: śr. -0.8%, med. -2.9%, wygr. 14% | N 8157: śr. -0.3%, med. -2.9%, wygr. 14% | N 8142: śr. -1.4%, med. -2.9%, wygr. 13% | N 8079: śr. -2.2%, med. -2.9%, wygr. 13% |
| 15 s | TP +30% / SL -20% | N 7595: śr. -3.0%, med. -3.0%, wygr. 23% | N 7480: śr. -2.5%, med. -3.0%, wygr. 22% | N 7354: śr. -2.6%, med. -3.0%, wygr. 21% | N 7122: śr. -3.1%, med. -3.0%, wygr. 19% |

## 2. Wybór progów na treningu (bez dziur, d = 2 s, 0.25 SOL, N >= 50)

Siatka: 215 reguł (jeden albo dwa warunki z: portfele_razem >= 4/8/15/25/40, kupno_sol_10s > 1/3/6/10/15, netto_sol_60s > 1/2.7/5/10, sol_1_slot > 1/3/6/9, kupujacy_10s >= 3/8/15/25). Najlepsza reguła dla każdego wieku i wyjścia; trening vs test (test liczony raz):

| wiek | wyjście | reguła | reguł > 0 na treningu | TRENING | TEST |
|---|---|---|---|---|---|
| 5 s | jak on (5 s bez napływu) | `portfele_razem >= 4 i kupno_sol_10s > 1` | 0 z 215 | N 13376: śr. -3.9%, med. -2.9%, wygr. 17% (baseline -3.9%) | N 3143: śr. -5.1%, med. -3.1%, wygr. 15% |
| 5 s | stały czas 15 s | `portfele_razem >= 40 i sol_1_slot > 9` **(główna)** | 0 z 215 | N 448: śr. -2.7%, med. -5.2%, wygr. 40% (baseline -3.8%) | N 89: śr. +0.2%, med. -3.1%, wygr. 45% |
| 5 s | stały czas 60 s | `portfele_razem >= 40 i netto_sol_60s > 10` | 0 z 215 | N 406: śr. -3.3%, med. -8.4%, wygr. 40% (baseline -5.6%) | N 80: śr. +2.4%, med. -11.1%, wygr. 45% |
| 5 s | TP +30% / SL -20% | `portfele_razem >= 40 i netto_sol_60s > 10` | 0 z 215 | N 562: śr. -3.2%, med. -11.3%, wygr. 43% (baseline -3.9%) | N 117: śr. +1.8%, med. +2.2%, wygr. 51% |
| 10 s | jak on (5 s bez napływu) | `kupno_sol_10s > 1` | 0 z 215 | N 22089: śr. -3.5%, med. -2.9%, wygr. 12% (baseline -3.5%) | N 4830: śr. -4.7%, med. -2.9%, wygr. 13% |
| 10 s | stały czas 15 s | `portfele_razem >= 40 i netto_sol_60s > 10` | 0 z 215 | N 1220: śr. -3.6%, med. -5.3%, wygr. 41% (baseline -3.5%) | N 260: śr. -3.4%, med. -4.1%, wygr. 42% |
| 10 s | stały czas 60 s | `portfele_razem >= 40 i netto_sol_60s > 10` | 0 z 215 | N 954: śr. -5.4%, med. -13.1%, wygr. 37% (baseline -5.4%) | N 193: śr. -3.6%, med. -10.6%, wygr. 39% |
| 10 s | TP +30% / SL -20% | `portfele_razem >= 40 i netto_sol_60s > 10` | 0 z 215 | N 1208: śr. -3.2%, med. -13.2%, wygr. 44% (baseline -3.8%) | N 268: śr. -3.4%, med. -10.2%, wygr. 45% |
| 15 s | jak on (5 s bez napływu) | `kupno_sol_10s > 1 i kupujacy_10s >= 3` | 0 z 215 | N 6923: śr. -3.1%, med. -4.1%, wygr. 23% (baseline -3.4%) | N 1492: śr. -5.3%, med. -4.7%, wygr. 23% |
| 15 s | stały czas 15 s | `kupno_sol_10s > 15 i kupujacy_10s >= 15` | 0 z 215 | N 1091: śr. -3.1%, med. -5.1%, wygr. 40% (baseline -3.4%) | N 212: śr. +1.0%, med. -3.7%, wygr. 44% |
| 15 s | stały czas 60 s | `portfele_razem >= 40 i kupno_sol_10s > 10` | 0 z 215 | N 1071: śr. -5.4%, med. -11.6%, wygr. 36% (baseline -5.0%) | N 196: śr. -5.7%, med. -15.4%, wygr. 38% |
| 15 s | TP +30% / SL -20% | `kupno_sol_10s > 15 i kupujacy_10s >= 15` | 0 z 215 | N 1054: śr. -4.3%, med. -15.9%, wygr. 40% (baseline -3.8%) | N 210: śr. -0.4%, med. -12.4%, wygr. 43% |

## 3. Główna reguła (najlepsza na treningu): `portfele_razem >= 40 i sol_1_slot > 9`, wiek 5 s, wyjście stały czas 15 s


**Stawka 0.25 SOL**

| opóźnienie | trening (wszystkie) | trening (bez dziur) | TEST (wszystkie) | TEST (bez dziur) | baseline TEST (bez dziur) |
|---|---|---|---|---|---|
| 0 s (odniesienie) | N 597: śr. -3.3%, med. -4.4%, wygr. 39%, -5.0 SOL | N 465: śr. -3.1%, med. -5.7%, wygr. 41%, -3.6 SOL | N 145: śr. -0.6%, med. -2.9%, wygr. 35%, -0.2 SOL | N 94: śr. +1.5%, med. -4.1%, wygr. 40%, +0.4 SOL | N 11128: śr. -2.4%, med. -2.9%, wygr. 19% |
| 1 s | N 597: śr. -3.3%, med. -4.1%, wygr. 38%, -4.9 SOL | N 458: śr. -2.9%, med. -5.9%, wygr. 41%, -3.3 SOL | N 145: śr. -0.5%, med. -2.9%, wygr. 42%, -0.2 SOL | N 90: śr. +0.5%, med. -3.2%, wygr. 47%, +0.1 SOL | N 11015: śr. -2.7%, med. -2.9%, wygr. 18% |
| 2 s | N 597: śr. -3.2%, med. -4.0%, wygr. 38%, -4.7 SOL | N 448: śr. -2.7%, med. -5.2%, wygr. 40%, -3.1 SOL | N 145: śr. -0.7%, med. -2.9%, wygr. 41%, -0.2 SOL | N 89: śr. +0.2%, med. -3.1%, wygr. 45%, +0.1 SOL | N 10898: śr. -2.8%, med. -2.9%, wygr. 17% |
| 5 s | N 597: śr. -2.6%, med. -2.9%, wygr. 36%, -3.8 SOL | N 426: śr. -2.1%, med. -4.8%, wygr. 39%, -2.2 SOL | N 145: śr. +0.7%, med. -2.9%, wygr. 37%, +0.3 SOL | N 88: śr. +1.4%, med. -3.1%, wygr. 42%, +0.3 SOL | N 10591: śr. -3.1%, med. -2.9%, wygr. 16% |

**Stawka 1 SOL**

| opóźnienie | trening (wszystkie) | trening (bez dziur) | TEST (wszystkie) | TEST (bez dziur) | baseline TEST (bez dziur) |
|---|---|---|---|---|---|
| 0 s (odniesienie) | N 597: śr. -3.0%, med. -4.1%, wygr. 39%, -17.6 SOL | N 465: śr. -2.7%, med. -5.4%, wygr. 42%, -12.5 SOL | N 145: śr. -0.3%, med. -2.6%, wygr. 35%, -0.4 SOL | N 94: śr. +1.9%, med. -3.8%, wygr. 40%, +1.8 SOL | N 11128: śr. -2.1%, med. -2.6%, wygr. 19% |
| 1 s | N 597: śr. -2.9%, med. -3.8%, wygr. 39%, -17.6 SOL | N 458: śr. -2.5%, med. -5.6%, wygr. 41%, -11.5 SOL | N 145: śr. -0.1%, med. -2.6%, wygr. 42%, -0.2 SOL | N 90: śr. +1.0%, med. -2.9%, wygr. 47%, +0.9 SOL | N 11015: śr. -2.4%, med. -2.6%, wygr. 18% |
| 2 s | N 597: śr. -2.8%, med. -3.7%, wygr. 38%, -16.7 SOL | N 448: śr. -2.4%, med. -4.9%, wygr. 40%, -10.6 SOL | N 145: śr. -0.3%, med. -2.6%, wygr. 41%, -0.4 SOL | N 89: śr. +0.6%, med. -2.8%, wygr. 46%, +0.6 SOL | N 10898: śr. -2.5%, med. -2.6%, wygr. 18% |
| 5 s | N 597: śr. -2.2%, med. -2.6%, wygr. 36%, -13.2 SOL | N 426: śr. -1.7%, med. -4.5%, wygr. 39%, -7.4 SOL | N 145: śr. +1.1%, med. -2.6%, wygr. 37%, +1.6 SOL | N 88: śr. +1.8%, med. -2.8%, wygr. 43%, +1.6 SOL | N 10591: śr. -2.8%, med. -2.6%, wygr. 17% |

Test, d = 2 s, 0.25 SOL, bez dziur: średnia +0.2%, 95% CI (bootstrap) -8.0% .. +9.1%; pozycji z migracją przed sprzedażą (wyjście po ostatniej cenie krzywej): 0; czas trzymania mediana 15 s.

5% najlepszych pozycji testu wnosi +5.6 pp do średniej +0.2%; bez nich średnia -5.6%.


## 4. Reguły dosłownie z drzew CUPSEY_SYGNALY.md (bez doboru), d = 2 s, bez dziur

| reguła | wiek | wyjście | trening 0.25 SOL | TEST 0.25 SOL | TEST 1 SOL |
|---|---|---|---|---|---|
| drzewo 'nowe w tym wieku': portfele_razem >= 8 albo (netto_sol_60s > 2.66 i tworca_ma_pct <= 4.49) | 5 s | jak on (5 s bez napływu) | N 9103: śr. -4.3%, med. -3.8%, wygr. 21% | N 2225: śr. -5.4%, med. -4.1%, wygr. 18%, -29.9 SOL | N 2225: śr. -5.1%, med. -3.8%, wygr. 18%, -112.5 SOL |
|  | 5 s | stały czas 15 s | N 8543: śr. -4.4%, med. -4.6%, wygr. 25% | N 2024: śr. -6.4%, med. -5.6%, wygr. 23%, -32.4 SOL | N 2024: śr. -6.1%, med. -5.4%, wygr. 24%, -123.2 SOL |
|  | 5 s | stały czas 60 s | N 6692: śr. -7.1%, med. -11.8%, wygr. 21% | N 1524: śr. -8.7%, med. -14.6%, wygr. 20%, -33.0 SOL | N 1524: śr. -8.3%, med. -14.4%, wygr. 20%, -126.0 SOL |
|  | 5 s | TP +30% / SL -20% | N 6983: śr. -6.3%, med. -16.6%, wygr. 29% | N 1729: śr. -7.8%, med. -19.0%, wygr. 27%, -33.5 SOL | N 1729: śr. -7.4%, med. -18.9%, wygr. 28%, -127.6 SOL |
|  | 10 s | jak on (5 s bez napływu) | N 9348: śr. -4.2%, med. -3.1%, wygr. 18% | N 2211: śr. -5.4%, med. -3.2%, wygr. 17%, -29.9 SOL | N 2211: śr. -5.1%, med. -2.9%, wygr. 17%, -112.7 SOL |
|  | 10 s | stały czas 15 s | N 8828: śr. -4.4%, med. -3.6%, wygr. 23% | N 2057: śr. -6.1%, med. -4.0%, wygr. 22%, -31.5 SOL | N 2057: śr. -5.8%, med. -3.7%, wygr. 22%, -119.7 SOL |
|  | 10 s | stały czas 60 s | N 7124: śr. -7.8%, med. -8.7%, wygr. 20% | N 1582: śr. -8.4%, med. -9.6%, wygr. 20%, -33.3 SOL | N 1582: śr. -8.1%, med. -9.3%, wygr. 20%, -127.8 SOL |
|  | 10 s | TP +30% / SL -20% | N 6915: śr. -6.7%, med. -15.1%, wygr. 28% | N 1646: śr. -7.4%, med. -17.0%, wygr. 25%, -30.3 SOL | N 1646: śr. -6.9%, med. -16.8%, wygr. 26%, -114.2 SOL |
|  | 15 s | jak on (5 s bez napływu) | N 9374: śr. -3.7%, med. -2.9%, wygr. 17% | N 2133: śr. -4.5%, med. -2.9%, wygr. 16%, -24.0 SOL | N 2133: śr. -4.1%, med. -2.6%, wygr. 17%, -87.8 SOL |
|  | 15 s | stały czas 15 s | N 8914: śr. -4.2%, med. -3.4%, wygr. 22% | N 2001: śr. -5.2%, med. -3.3%, wygr. 20%, -25.9 SOL | N 2001: śr. -4.9%, med. -3.0%, wygr. 20%, -97.2 SOL |
|  | 15 s | stały czas 60 s | N 7330: śr. -7.4%, med. -6.9%, wygr. 20% | N 1614: śr. -7.7%, med. -6.5%, wygr. 20%, -30.9 SOL | N 1614: śr. -7.3%, med. -6.3%, wygr. 20%, -117.5 SOL |
|  | 15 s | TP +30% / SL -20% | N 6805: śr. -6.5%, med. -13.5%, wygr. 26% | N 1546: śr. -5.9%, med. -13.7%, wygr. 25%, -22.9 SOL | N 1546: śr. -5.5%, med. -13.5%, wygr. 25%, -84.3 SOL |
| oba drzewa razem: portfele_razem >= 8 i kupno_sol_10s > 3 | 5 s | jak on (5 s bez napływu) | N 7060: śr. -4.6%, med. -4.4%, wygr. 23% | N 1826: śr. -4.9%, med. -4.3%, wygr. 20%, -22.6 SOL | N 1826: śr. -4.6%, med. -4.0%, wygr. 21%, -84.3 SOL |
|  | 5 s | stały czas 15 s | N 6631: śr. -4.8%, med. -5.0%, wygr. 27% | N 1672: śr. -5.8%, med. -5.5%, wygr. 25%, -24.2 SOL | N 1672: śr. -5.5%, med. -5.2%, wygr. 26%, -91.3 SOL |
|  | 5 s | stały czas 60 s | N 5182: śr. -7.8%, med. -12.1%, wygr. 23% | N 1274: śr. -8.4%, med. -13.5%, wygr. 22%, -26.9 SOL | N 1274: śr. -8.1%, med. -13.3%, wygr. 22%, -102.6 SOL |
|  | 5 s | TP +30% / SL -20% | N 5579: śr. -6.4%, med. -16.4%, wygr. 32% | N 1466: śr. -6.6%, med. -18.2%, wygr. 30%, -24.2 SOL | N 1466: śr. -6.2%, med. -18.0%, wygr. 30%, -91.1 SOL |
|  | 10 s | jak on (5 s bez napływu) | N 7970: śr. -4.3%, med. -3.4%, wygr. 19% | N 1935: śr. -5.0%, med. -3.4%, wygr. 18%, -24.4 SOL | N 1935: śr. -4.7%, med. -3.1%, wygr. 19%, -91.5 SOL |
|  | 10 s | stały czas 15 s | N 7527: śr. -4.6%, med. -3.9%, wygr. 25% | N 1803: śr. -5.5%, med. -4.1%, wygr. 23%, -24.8 SOL | N 1803: śr. -5.2%, med. -3.8%, wygr. 24%, -93.4 SOL |
|  | 10 s | stały czas 60 s | N 6079: śr. -7.7%, med. -8.9%, wygr. 22% | N 1404: śr. -7.8%, med. -9.0%, wygr. 21%, -27.3 SOL | N 1404: śr. -7.4%, med. -8.8%, wygr. 21%, -104.3 SOL |
|  | 10 s | TP +30% / SL -20% | N 5993: śr. -6.6%, med. -15.0%, wygr. 29% | N 1473: śr. -6.5%, med. -15.9%, wygr. 27%, -24.1 SOL | N 1473: śr. -6.1%, med. -15.8%, wygr. 27%, -89.8 SOL |
|  | 15 s | jak on (5 s bez napływu) | N 4184: śr. -3.8%, med. -4.8%, wygr. 27% | N 930: śr. -4.2%, med. -5.1%, wygr. 26%, -9.8 SOL | N 930: śr. -3.9%, med. -4.8%, wygr. 27%, -36.3 SOL |
|  | 15 s | stały czas 15 s | N 4003: śr. -4.5%, med. -5.8%, wygr. 32% | N 873: śr. -4.4%, med. -5.9%, wygr. 30%, -9.6 SOL | N 873: śr. -4.1%, med. -5.6%, wygr. 31%, -35.5 SOL |
|  | 15 s | stały czas 60 s | N 3297: śr. -8.4%, med. -14.9%, wygr. 28% | N 720: śr. -8.6%, med. -14.2%, wygr. 26%, -15.4 SOL | N 720: śr. -8.2%, med. -14.0%, wygr. 27%, -59.0 SOL |
|  | 15 s | TP +30% / SL -20% | N 3556: śr. -6.5%, med. -19.0%, wygr. 33% | N 785: śr. -3.8%, med. -18.7%, wygr. 31%, -7.4 SOL | N 785: śr. -3.2%, med. -18.5%, wygr. 31%, -25.1 SOL |
| profil Cupseya (mediany): portfele_razem >= 8 i kupno_sol_10s > 3 i sol_1_slot > 3 | 5 s | jak on (5 s bez napływu) | N 5963: śr. -4.9%, med. -4.5%, wygr. 24% | N 1615: śr. -4.9%, med. -4.5%, wygr. 21%, -19.9 SOL | N 1615: śr. -4.6%, med. -4.2%, wygr. 22%, -74.4 SOL |
|  | 5 s | stały czas 15 s | N 5610: śr. -5.3%, med. -5.1%, wygr. 28% | N 1485: śr. -5.8%, med. -5.7%, wygr. 26%, -21.6 SOL | N 1485: śr. -5.5%, med. -5.4%, wygr. 27%, -81.5 SOL |
|  | 5 s | stały czas 60 s | N 4387: śr. -8.8%, med. -13.6%, wygr. 24% | N 1135: śr. -8.8%, med. -14.8%, wygr. 23%, -25.0 SOL | N 1135: śr. -8.4%, med. -14.6%, wygr. 23%, -95.8 SOL |
|  | 5 s | TP +30% / SL -20% | N 4849: śr. -6.9%, med. -17.3%, wygr. 32% | N 1324: śr. -6.9%, med. -18.7%, wygr. 30%, -22.7 SOL | N 1324: śr. -6.5%, med. -18.5%, wygr. 30%, -85.7 SOL |
|  | 10 s | jak on (5 s bez napływu) | N 6480: śr. -4.7%, med. -3.6%, wygr. 20% | N 1683: śr. -5.1%, med. -3.6%, wygr. 19%, -21.4 SOL | N 1683: śr. -4.8%, med. -3.3%, wygr. 20%, -80.5 SOL |
|  | 10 s | stały czas 15 s | N 6113: śr. -4.9%, med. -4.0%, wygr. 26% | N 1569: śr. -5.6%, med. -4.2%, wygr. 24%, -21.9 SOL | N 1569: śr. -5.3%, med. -3.9%, wygr. 25%, -82.6 SOL |
|  | 10 s | stały czas 60 s | N 4935: śr. -8.4%, med. -9.4%, wygr. 22% | N 1228: śr. -8.1%, med. -9.9%, wygr. 21%, -24.9 SOL | N 1228: śr. -7.8%, med. -9.7%, wygr. 22%, -95.3 SOL |
|  | 10 s | TP +30% / SL -20% | N 4997: śr. -7.2%, med. -15.8%, wygr. 29% | N 1304: śr. -6.9%, med. -16.6%, wygr. 27%, -22.4 SOL | N 1304: śr. -6.4%, med. -16.4%, wygr. 27%, -83.6 SOL |
|  | 15 s | jak on (5 s bez napływu) | N 3556: śr. -4.0%, med. -5.0%, wygr. 28% | N 852: śr. -3.9%, med. -4.8%, wygr. 26%, -8.2 SOL | N 852: śr. -3.5%, med. -4.5%, wygr. 27%, -30.1 SOL |
|  | 15 s | stały czas 15 s | N 3400: śr. -4.8%, med. -5.9%, wygr. 33% | N 803: śr. -4.0%, med. -5.6%, wygr. 31%, -8.0 SOL | N 803: śr. -3.7%, med. -5.4%, wygr. 32%, -29.4 SOL |
|  | 15 s | stały czas 60 s | N 2792: śr. -8.6%, med. -15.6%, wygr. 28% | N 667: śr. -8.4%, med. -14.6%, wygr. 27%, -13.9 SOL | N 667: śr. -8.0%, med. -14.4%, wygr. 27%, -53.2 SOL |
|  | 15 s | TP +30% / SL -20% | N 3042: śr. -6.8%, med. -19.0%, wygr. 33% | N 725: śr. -3.4%, med. -18.7%, wygr. 32%, -6.2 SOL | N 725: śr. -2.9%, med. -18.5%, wygr. 32%, -20.7 SOL |

## 5. Główna reguła (portfele_razem >= 40 i sol_1_slot > 9, wiek 5 s) z każdym wyjściem - TEST bez dziur, 0.25 SOL

| wyjście | d = 0 s | d = 1 s | d = 2 s | d = 5 s |
|---|---|---|---|---|
| jak on (5 s bez napływu) | N 110: śr. +0.3%, med. -7.4%, wygr. 30% | N 103: śr. -0.5%, med. -7.1%, wygr. 36% | N 99: śr. -0.6%, med. -7.8%, wygr. 33% | N 88: śr. -4.1%, med. -8.2%, wygr. 32% |
| stały czas 15 s | N 94: śr. +1.5%, med. -4.1%, wygr. 40% | N 90: śr. +0.5%, med. -3.2%, wygr. 47% | N 89: śr. +0.2%, med. -3.1%, wygr. 45% | N 88: śr. +1.4%, med. -3.1%, wygr. 42% |
| stały czas 60 s | N 64: śr. +6.2%, med. +0.1%, wygr. 50% | N 64: śr. +5.9%, med. -5.1%, wygr. 47% | N 64: śr. +4.0%, med. -10.8%, wygr. 45% | N 62: śr. +5.8%, med. -6.8%, wygr. 44% |
| TP +30% / SL -20% | N 110: śr. -2.0%, med. -15.4%, wygr. 40% | N 101: śr. -0.2%, med. -7.7%, wygr. 45% | N 94: śr. +3.2%, med. +2.8%, wygr. 52% | N 79: śr. +2.7%, med. -0.2%, wygr. 49% |

## 6. Kontrola: tokeny, które kupił Cupsey (na krzywej), z NASZYM wejściem w wieku 5/10/15 s, d = 2 s, 0.25 SOL, bez dziur

Jego tokenów z pełnym zapisem startu: 96. Wchodzimy w stałym wieku niezależnie od niego; to NIE jest strategia (wybór tokenów zna jego przyszły zakup) - tylko test, czy jego tokeny różnią się od tych, które łapie reguła.

| wiek | wyjście | wszystkie jego (całe okno) | my PRZED jego zakupem | my PO jego zakupie |
|---|---|---|---|---|
| 5 s | jak on (5 s bez napływu) | N 73: śr. +19.3%, med. -0.3%, wygr. 49% | N 43: śr. +37.5%, med. +14.1%, wygr. 56% | N 30: śr. -6.8%, med. -8.9%, wygr. 40% |
| 5 s | stały czas 15 s | N 60: śr. +26.8%, med. +9.7%, wygr. 58% | N 35: śr. +46.8%, med. +28.1%, wygr. 74% | N 25 ⚠️ niewiarygodny: śr. -1.3%, med. -8.1%, wygr. 36% |
| 5 s | stały czas 60 s | N 39: śr. +68.1%, med. +32.4%, wygr. 56% | N 24 ⚠️ niewiarygodny: śr. +112.6%, med. +88.5%, wygr. 71% | N 15 ⚠️ niewiarygodny: śr. -3.2%, med. -45.9%, wygr. 33% |
| 5 s | TP +30% / SL -20% | N 72: śr. +25.4%, med. +23.1%, wygr. 68% | N 44: śr. +43.7%, med. +39.1%, wygr. 84% | N 28 ⚠️ niewiarygodny: śr. -3.3%, med. -13.0%, wygr. 43% |
| 10 s | jak on (5 s bez napływu) | N 61: śr. +13.4%, med. -1.6%, wygr. 48% | N 26 ⚠️ niewiarygodny: śr. +35.7%, med. +4.9%, wygr. 58% | N 35: śr. -3.1%, med. -9.1%, wygr. 40% |
| 10 s | stały czas 15 s | N 55: śr. +11.6%, med. -4.8%, wygr. 45% | N 25 ⚠️ niewiarygodny: śr. +37.6%, med. +4.0%, wygr. 60% | N 30: śr. -10.0%, med. -11.5%, wygr. 33% |
| 10 s | stały czas 60 s | N 37: śr. +47.4%, med. +10.4%, wygr. 54% | N 20 ⚠️ niewiarygodny: śr. +101.4%, med. +55.8%, wygr. 70% | N 17 ⚠️ niewiarygodny: śr. -16.2%, med. -30.7%, wygr. 35% |
| 10 s | TP +30% / SL -20% | N 60: śr. +9.3%, med. +7.9%, wygr. 55% | N 26 ⚠️ niewiarygodny: śr. +33.0%, med. +25.4%, wygr. 77% | N 34: śr. -8.8%, med. -19.3%, wygr. 38% |
| 15 s | jak on (5 s bez napływu) | N 56: śr. +12.9%, med. -3.0%, wygr. 46% | N 22 ⚠️ niewiarygodny: śr. +36.1%, med. +6.2%, wygr. 64% | N 34: śr. -2.1%, med. -7.6%, wygr. 35% |
| 15 s | stały czas 15 s | N 51: śr. +19.1%, med. +1.7%, wygr. 55% | N 22 ⚠️ niewiarygodny: śr. +44.0%, med. +18.0%, wygr. 68% | N 29 ⚠️ niewiarygodny: śr. +0.2%, med. -5.7%, wygr. 45% |
| 15 s | stały czas 60 s | N 36: śr. +47.3%, med. +8.0%, wygr. 58% | N 18 ⚠️ niewiarygodny: śr. +100.2%, med. +65.7%, wygr. 78% | N 18 ⚠️ niewiarygodny: śr. -5.6%, med. -14.5%, wygr. 39% |
| 15 s | TP +30% / SL -20% | N 52: śr. +12.4%, med. +4.3%, wygr. 54% | N 22 ⚠️ niewiarygodny: śr. +35.9%, med. +28.3%, wygr. 77% | N 30: śr. -4.8%, med. -17.3%, wygr. 37% |

## Werdykt

Główna reguła (wybrana na treningu): `portfele_razem >= 40 i sol_1_slot > 9` w wieku 5 s, wyjście stały czas 15 s, d = 2 s, 0.25 SOL - TEST: N 89: śr. +0.2%, med. -3.1%, wygr. 45%, +0.1 SOL; 95% CI -8.0% .. +9.1%.

Najlepsze reguły dla pozostałych wieków/wyjść na teście: 5 s/stały czas 60 s +2.4% (N 80), 5 s/TP +30% / SL -20% +1.8% (N 117), 15 s/stały czas 15 s +1.0% (N 212), 5 s/stały czas 15 s +0.2% (N 89), 15 s/TP +30% / SL -20% -0.4% (N 210), 10 s/stały czas 15 s -3.4% (N 260), 10 s/TP +30% / SL -20% -3.4% (N 268), 10 s/stały czas 60 s -3.6% (N 193), 10 s/jak on (5 s bez napływu) -4.7% (N 4830), 5 s/jak on (5 s bez napływu) -5.1% (N 3143), 15 s/jak on (5 s bez napływu) -5.3% (N 1492), 15 s/stały czas 60 s -5.7% (N 196).

**Reguła NIE zarabia po kosztach i opóźnieniu na teście.**

- Na treningu (bez dziur, d = 2 s) dodatnią średnią miało 0 z 2580 kombinacji reguła x wiek x wyjście (liczone te z N >= 50) - wybrana reguła to najmniej stratna, nie zarabiająca; wynik testu bliski zera mieści się w szumie (CI wyżej) i opiera się na kilku trafieniach.
- Reguły dosłownie z drzew (sekcja 4) tracą 4-9%/pozycję na każdym wieku i wyjściu - bardziej niż baseline: tłum na starcie to częściej szczyt fali niż jej początek.
- Jego własne tokeny (sekcja 6, 5 s, TP/SL): przed jego zakupem N 44: śr. +43.7%, med. +39.1%, wygr. 84%, po jego zakupie N 28 ⚠️ niewiarygodny: śr. -3.3%, med. -13.0%, wygr. 43%. Zarabia się na jego zakupie (i kopiujących go), nie na cechach startu, które reguła widzi - tego nie da się odtworzyć bez wiedzy, że on kupi.

(Czas liczenia 73 s.)
