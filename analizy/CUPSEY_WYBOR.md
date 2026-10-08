# Czy Cupsey odróżnia trash? Jego wybory vs pominięte równie gorące starty - 08.10.2026 17:59

Jego wejść <= 60 s od startu z porównaniem: 84; pominiętych tokenów z top 5 (po kwocie zakupów w 10 s, w tej samej chwili): 330. Jego token był nr 1 w 55% przypadków. Wynik liczony od ceny w chwili jego wejścia (to ocena WYBORU, nie jego wykonania).

| wynik tokena od chwili T | jego wybór | pominięte z top 5 | AUC (> 0.5 = jego lepsze) | AUC 1. / 2. połowa |
|---|---|---|---|---|
| max wzrost 5 min | +105.1% (śr. +143.5%) | +5.7% (śr. +34.7%) | 0.86 | 0.86 / 0.86 |
| max wzrost 30 min | +112.9% (śr. +156.3%) | +6.5% (śr. +45.3%) | 0.84 | 0.85 / 0.84 |
| cena po 5 min | -10.4% (śr. +39.8%) | -24.8% (śr. -19.9%) | 0.61 | 0.64 / 0.59 |
| cena po 30 min | -38.9% (śr. +25.3%) | -30.3% (śr. -23.4%) | 0.52 | 0.56 / 0.47 |
| migracja w 30 min | 18% | 2% | 0.58 | 0.62 / 0.53 |
| pump (+100% przed -70%) | 56% | 12% | 0.72 | 0.76 / 0.68 |
| rug (-70% przed +100%) | 6% | 15% | 0.46 | 0.44 / 0.47 |

W tej samej chwili jego token miał większy max wzrost w 30 min niż mediana pominiętych w 95% przypadków (50% = rzut monetą; N 84).

## Czy to tylko "bierze nr 1"? Nr 1 gorący start w chwilach, gdy był aktywny, ale nie kupował

|  | N | max 5 min (med.) | max 30 min (med.) | cena po 30 min (med.) | pump | rug | migracja 30 min |
|---|---|---|---|---|---|---|---|
| jego wybory | 84 | +105.1% | +112.9% | -38.9% | 56% | 6% | 18% |
| nr 1 gorący start bez niego | 250 | +8.7% | +9.8% | -36.4% | 17% | 11% | 5% |

## Naśladowcy (portfele, które kupują sekundy po nim i prawie tylko jego tokeny)

Portfeli kupujących <= 5 s po nim w >= 3 jego tokenach: 187; z nich 140 ma jego tokeny >= 20x częściej wśród swoich wczesnych zakupów niż losowo (baza 0.110%). Najbardziej wierni: 7 z 7 wczesnych zakupów to jego tokeny; 5 z 5 wczesnych zakupów to jego tokeny; 20 z 21 wczesnych zakupów to jego tokeny; 74 z 78 wczesnych zakupów to jego tokeny; 74 z 79 wczesnych zakupów to jego tokeny. Po jego zakupie inni kupują w 30 s mediana 27.7 SOL, z czego naśladowcy mediana 22% (średnio 24%). To mogą być boty kopiujące albo jego własne dodatkowe portfele.
