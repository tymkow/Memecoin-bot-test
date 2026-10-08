# Kopiowanie zyskownych portfeli - test poza próbą (08.10.2026 19:15)

Eksploracja do 06.10 19:11, TEST potem (24 h). Portfeli spełniających warunki na eksploracji: 1154.


## R1 top 20 po sumie SOL (20 portfeli; ich własny wynik w teście: +3.5% na 2524 poz.)

| opóźnienie (sloty) | pozycji | śr. | CI po pozycjach | CI po portfelach | mediana | bez 1% najlepszych | 1. / 2. połowa testu | portfeli > 0 |
|---|---|---|---|---|---|---|---|---|
| 1 (0.4 s) | 2483 | -5.5% | -6.8..-4.2 | -15.3..-1.5 | -9.3% | -7.3% | -7.4% / -5.1% | 7/18 |
| 5 (2.0 s) | 2483 | -5.8% | -7.0..-4.5 | -14.7..-1.9 | -9.1% | -7.5% | -7.4% / -5.4% | 5/18 |
| 12 (4.8 s) | 2483 | -5.6% | -6.8..-4.3 | -14.6..-1.7 | -8.0% | -7.2% | -6.8% / -5.3% | 6/18 |
| 25 (10.0 s) | 2483 | -5.5% | -6.7..-4.3 | -14.0..-1.9 | -7.6% | -7.0% | -5.8% / -5.4% | 1/18 |
| 50 (20.0 s) | 2483 | -4.9% | -6.0..-3.7 | -14.0..-1.1 | -6.6% | -6.5% | -5.7% / -4.7% | 4/18 |

## R2 top 20 po śr. wyniku, zysk w obu połowach (20 portfeli; ich własny wynik w teście: +3.2% na 1184 poz.)

| opóźnienie (sloty) | pozycji | śr. | CI po pozycjach | CI po portfelach | mediana | bez 1% najlepszych | 1. / 2. połowa testu | portfeli > 0 |
|---|---|---|---|---|---|---|---|---|
| 1 (0.4 s) | 1059 | -7.6% | -10.1..-5.1 | -10.8..-3.1 | -12.1% | -10.2% | -4.8% / -8.7% | 6/16 |
| 5 (2.0 s) | 1059 | -6.2% | -8.8..-3.3 | -9.1..-1.7 | -10.5% | -9.1% | -5.2% / -6.6% | 6/16 |
| 12 (4.8 s) | 1059 | -6.7% | -9.3..-3.9 | -9.5..-3.1 | -9.6% | -9.8% | -8.2% / -6.1% | 5/16 |
| 25 (10.0 s) | 1059 | -4.4% | -7.3..-0.8 | -8.3..+0.8 | -8.0% | -8.0% | -7.3% / -3.2% | 2/16 |
| 50 (20.0 s) | 1059 | -4.9% | -7.6..-2.1 | -9.4..+2.4 | -7.4% | -8.4% | -9.2% / -3.2% | 3/16 |

## R3 = R2 + średnia bez 1% najlepszych > 0 (20 portfeli; ich własny wynik w teście: +3.2% na 1184 poz.)

| opóźnienie (sloty) | pozycji | śr. | CI po pozycjach | CI po portfelach | mediana | bez 1% najlepszych | 1. / 2. połowa testu | portfeli > 0 |
|---|---|---|---|---|---|---|---|---|
| 1 (0.4 s) | 1059 | -7.6% | -10.1..-5.1 | -10.8..-3.1 | -12.1% | -10.2% | -4.8% / -8.7% | 6/16 |
| 5 (2.0 s) | 1059 | -6.2% | -8.8..-3.3 | -9.1..-1.7 | -10.5% | -9.1% | -5.2% / -6.6% | 6/16 |
| 12 (4.8 s) | 1059 | -6.7% | -9.3..-3.9 | -9.5..-3.1 | -9.6% | -9.8% | -8.2% / -6.1% | 5/16 |
| 25 (10.0 s) | 1059 | -4.4% | -7.3..-0.8 | -8.3..+0.8 | -8.0% | -8.0% | -7.3% / -3.2% | 2/16 |
| 50 (20.0 s) | 1059 | -4.9% | -7.6..-2.1 | -9.4..+2.4 | -7.4% | -8.4% | -9.2% / -3.2% | 3/16 |

## kontrola: 20 losowych aktywnych (20 portfeli; ich własny wynik w teście: +3.1% na 1064 poz.)

| opóźnienie (sloty) | pozycji | śr. | CI po pozycjach | CI po portfelach | mediana | bez 1% najlepszych | 1. / 2. połowa testu | portfeli > 0 |
|---|---|---|---|---|---|---|---|---|
| 1 (0.4 s) | 1005 | -7.5% | -9.7..-5.2 | -14.5..-0.6 | -12.1% | -9.5% | -9.4% / -6.7% | 4/18 |
| 5 (2.0 s) | 1005 | -7.8% | -10.1..-5.6 | -14.7..-2.0 | -11.6% | -9.9% | -9.2% / -7.2% | 3/18 |
| 12 (4.8 s) | 1005 | -6.8% | -9.0..-4.4 | -13.8..-1.5 | -9.8% | -9.0% | -7.0% / -6.7% | 4/18 |
| 25 (10.0 s) | 1005 | -7.2% | -9.2..-5.2 | -12.4..-2.6 | -9.0% | -9.2% | -7.6% / -7.1% | 4/18 |
| 50 (20.0 s) | 1005 | -6.9% | -8.7..-4.9 | -12.3..-2.3 | -7.9% | -8.8% | -7.8% / -6.5% | 4/18 |

## Trwałość umiejętności

300 najaktywniejszych portfeli (>= 20 pozycji w teście: 224): korelacja rang wyniku eksploracja -> test (ich własne transakcje) = 0.41. Najlepsza piątka na eksploracji ma w teście śr. +3.2%, najgorsza piątka -4.9%.

## Zgoda zręcznych portfeli (top 100 po SOL na eksploracji; >= 2 kupiło ten sam token w 60 s)

Sygnałów w teście: 1872. Uwaga: bez filtra dziur strumienia.

| opóźnienie | wyjście | zgoda | baseline: losowy token w tym samym wieku |
|---|---|---|---|
| 2 s | stały 60 s (jak on) | N 1859: śr. -6.6% (CI -8.6..-4.6), med. -11.4% | N 1457: śr. +2.4%, med. -2.9% |
| 2 s | stały 300 s | N 1859: śr. -13.9% (CI -16.8..-10.8), med. -27.9% | N 1457: śr. +2.1%, med. -4.3% |
| 2 s | TP +30% / SL -20% | N 1859: śr. -5.7% (CI -7.1..-4.2), med. -18.7% | N 1457: śr. +0.2%, med. -3.5% |
| 5 s | stały 60 s (jak on) | N 1859: śr. -6.3% (CI -8.2..-4.4), med. -9.9% | N 1458: śr. +2.4%, med. -2.9% |
| 5 s | stały 300 s | N 1859: śr. -13.2% (CI -16.0..-10.2), med. -26.3% | N 1458: śr. +1.2%, med. -3.7% |
| 5 s | TP +30% / SL -20% | N 1859: śr. -5.5% (CI -7.1..-4.1), med. -17.5% | N 1458: śr. +0.7%, med. -3.3% |
| 20 s | stały 60 s (jak on) | N 1858: śr. -5.6% (CI -7.3..-3.6), med. -6.2% | N 1471: śr. +0.8%, med. -2.9% |
| 20 s | stały 300 s | N 1858: śr. -11.9% (CI -14.4..-9.2), med. -18.7% | N 1471: śr. +1.1%, med. -3.0% |
| 20 s | TP +30% / SL -20% | N 1858: śr. -6.3% (CI -7.7..-4.9), med. -13.5% | N 1471: śr. -0.2%, med. -3.0% |
