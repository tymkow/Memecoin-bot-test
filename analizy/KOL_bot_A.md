# Trader Bot A (Bot A) - 08.10.2026 18:13

Wybrany losowo (ziarno 20261008) spośród portfeli bez X i spoza listy KOL MadeOnSol, z >= 100 zamkniętymi pozycjami na krzywej, zyskownych w obu połowach okna i NIE kupujących w slocie utworzenia tokena (insiderzy twórcy odrzuceni). Dane: tylko nasz strumień pump.fun (krzywa).

|  | N | suma SOL | śr. / mediana na poz. | wygrane | śr. stawka SOL |
|---|---|---|---|---|---|
| zamknięte na krzywej | 1078 | +9.9 | +1.0% / -1.5% | 47% | 0.66 |
| 1. połowa | 714 | +7.9 | +1.2% / -1.8% | 47% | 0.68 |
| 2. połowa | 364 | +2.0 | +0.6% / -1.1% | 47% | 0.63 |

Pozycji otwartych na końcu / sprzedanych poza krzywą: 210; pominięte (sprzedał więcej tokenów, niż kupił na krzywej - przelew / inny portfel / dziura strumienia): 23. (śr. wynik na pozycję +1.0%)


# Na jakie sygnały wchodzi i wychodzi Bot A - 08.10.2026 18:13

Wejścia na krzywej pump.fun z pełnym zapisem rynku przed nimi: 1283 (z 1288 jego pozycji; reszta: PumpSwap / inne launchpady / brak w strumieniu). Kontrole: 5506 chwil tego samego tokena, 6395 innych tokenów w tej samej chwili. Podział czasu: 06.10 09:29.

## 1. Wejścia - cechy rynku tuż przed jego zakupem

| cecha | on (mediana) | ten sam token (mediana) | ta sama chwila (mediana) | nowe w tym wieku (mediana) | AUC vs ten sam token | AUC 70% / 30% | AUC vs ta sama chwila | AUC 70% / 30% | AUC vs nowe w tym wieku | AUC 70% / 30% |
|---|---|---|---|---|---|---|---|---|---|---|
| wiek_min | 2.47 | 7.5 | 4.97 | 2.57 | 0.34 | 0.34 / 0.34 | 0.38 | 0.39 / 0.37 | 0.50 | 0.50 / 0.49 |
| od_szczytu | -0.154 | -0.356 | -0.222 | -0.083 | 0.66 | 0.66 / 0.68 | 0.56 | 0.56 / 0.58 | 0.44 | 0.43 / 0.47 |
| nowy_szczyt | 0 | 0 | 0 | 0 | 0.54 | 0.54 / 0.55 | 0.47 | 0.46 / 0.48 | 0.41 | 0.41 / 0.41 |
| zmiana_10s | 0 | 0 | 0 | 0 | 0.55 | 0.54 / 0.56 | 0.56 | 0.56 / 0.57 | 0.55 | 0.55 / 0.56 |
| zmiana_30s | 0.00725 | 0 | -0.00198 | 0 | 0.59 | 0.58 / 0.60 | 0.62 | 0.62 / 0.62 | 0.59 | 0.59 / 0.59 |
| zmiana_60s | 0.0439 | 0 | -0.00279 | 0 | 0.62 | 0.62 / 0.61 | 0.65 | 0.67 / 0.62 | 0.63 | 0.64 / 0.61 |
| zmiana_300s | 0.11 | 0 | -0.00191 | 0 | 0.60 | 0.58 / 0.64 | 0.64 | 0.64 / 0.63 | 0.65 | 0.65 / 0.65 |
| kupna_10s | 6 | 1 | 0 | 0 | 0.67 | 0.67 / 0.69 | 0.79 | 0.78 / 0.80 | 0.80 | 0.80 / 0.81 |
| sprzedaze_10s | 3 | 1 | 0 | 0 | 0.61 | 0.60 / 0.62 | 0.73 | 0.73 / 0.73 | 0.79 | 0.79 / 0.79 |
| kupujacy_10s | 5 | 1 | 0 | 0 | 0.68 | 0.67 / 0.70 | 0.80 | 0.79 / 0.81 | 0.81 | 0.81 / 0.82 |
| kupno_sol_10s | 2.21 | 0.0667 | 0 | 0 | 0.68 | 0.67 / 0.70 | 0.81 | 0.80 / 0.82 | 0.80 | 0.80 / 0.80 |
| netto_sol_10s | 0.465 | 0 | 0 | 0 | 0.61 | 0.60 / 0.62 | 0.63 | 0.63 / 0.63 | 0.58 | 0.59 / 0.58 |
| max_kupno_10s | 0.988 | 0.049 | 0 | 0 | 0.67 | 0.67 / 0.70 | 0.80 | 0.80 / 0.81 | 0.79 | 0.79 / 0.80 |
| kol_kupna_10s | 0 | 0 | 0 | 0 | 0.51 | 0.51 / 0.51 | 0.51 | 0.51 / 0.51 | 0.51 | 0.51 / 0.51 |
| kupna_60s | 19 | 8 | 1 | 0 | 0.65 | 0.65 / 0.66 | 0.79 | 0.79 / 0.79 | 0.87 | 0.87 / 0.87 |
| sprzedaze_60s | 8 | 6 | 1 | 0 | 0.57 | 0.57 / 0.58 | 0.71 | 0.71 / 0.70 | 0.85 | 0.85 / 0.84 |
| kupujacy_60s | 18 | 7 | 1 | 0 | 0.66 | 0.66 / 0.67 | 0.82 | 0.82 / 0.83 | 0.88 | 0.88 / 0.89 |
| kupno_sol_60s | 10.5 | 2.94 | 0.0795 | 0 | 0.69 | 0.68 / 0.69 | 0.83 | 0.83 / 0.83 | 0.86 | 0.86 / 0.86 |
| netto_sol_60s | 3.63 | 0 | -0.0013 | 0 | 0.67 | 0.68 / 0.66 | 0.71 | 0.72 / 0.67 | 0.68 | 0.69 / 0.64 |
| max_kupno_60s | 1.97 | 0.988 | 0.0427 | 0 | 0.69 | 0.69 / 0.69 | 0.82 | 0.82 / 0.82 | 0.84 | 0.84 / 0.84 |
| kol_kupna_60s | 0 | 0 | 0 | 0 | 0.51 | 0.51 / 0.52 | 0.52 | 0.51 / 0.53 | 0.52 | 0.52 / 0.53 |
| kol_kupna_300s | 0 | 0 | 0 | 0 | 0.50 | 0.51 / 0.50 | 0.53 | 0.53 / 0.53 | 0.54 | 0.53 / 0.54 |
| portfele_razem | 64 | 122 | 19 | 3 | 0.39 | 0.39 / 0.38 | 0.66 | 0.66 / 0.66 | 0.92 | 0.92 / 0.92 |
| transakcje_razem | 120 | 294 | 65 | 9 | 0.37 | 0.38 / 0.37 | 0.59 | 0.60 / 0.59 | 0.87 | 0.87 / 0.86 |
| przyspieszenie | 1.63 | 1 | 0.442 | 5.33 | 0.60 | 0.59 / 0.62 | 0.66 | 0.66 / 0.65 | 0.47 | 0.48 / 0.43 |
| tworca_sprzedal | 0 | 0 | 0 | 0 | 0.47 | 0.46 / 0.48 | 0.46 | 0.46 / 0.48 | 0.38 | 0.38 / 0.38 |
| tworca_ma_pct | 0 | 0 | 0 | 0 | 0.54 | 0.55 / 0.53 | 0.59 | 0.60 / 0.56 | 0.55 | 0.56 / 0.51 |
| cisza_s | 1 | 2 | 8 | 70 | 0.34 | 0.35 / 0.33 | 0.23 | 0.23 / 0.22 | 0.12 | 0.12 / 0.13 |
| tworca_kupil_sol | 0.282 | 0.282 | 0.000988 | 0.205 | 0.50 | 0.50 / 0.50 | 0.57 | 0.57 / 0.56 | 0.48 | 0.49 / 0.45 |
| kupujacy_1_slot | 3 | 3 | 1 | 1 | 0.51 | 0.51 / 0.50 | 0.66 | 0.65 / 0.67 | 0.66 | 0.65 / 0.67 |
| sol_1_slot | 3.48 | 3.46 | 0.494 | 0.672 | 0.50 | 0.51 / 0.50 | 0.67 | 0.67 / 0.65 | 0.67 | 0.67 / 0.66 |

**Najsilniejsze różnice** (|AUC - 0.5|, z kontrolą; kierunek musi się zgadzać w obu połowach czasu):

| cecha | kontrola | AUC | 70% / 30% | stabilne |
|---|---|---|---|---|
| portfele_razem | nowe w tym wieku | 0.92 | 0.92 / 0.92 | tak |
| kupujacy_60s | nowe w tym wieku | 0.88 | 0.88 / 0.89 | tak |
| cisza_s | nowe w tym wieku | 0.12 | 0.12 / 0.13 | tak |
| transakcje_razem | nowe w tym wieku | 0.87 | 0.87 / 0.86 | tak |
| kupna_60s | nowe w tym wieku | 0.87 | 0.87 / 0.87 | tak |
| kupno_sol_60s | nowe w tym wieku | 0.86 | 0.86 / 0.86 | tak |
| sprzedaze_60s | nowe w tym wieku | 0.85 | 0.85 / 0.84 | tak |
| max_kupno_60s | nowe w tym wieku | 0.84 | 0.84 / 0.84 | tak |
| kupno_sol_60s | ta sama chwila | 0.83 | 0.83 / 0.83 | tak |
| kupujacy_60s | ta sama chwila | 0.82 | 0.82 / 0.83 | tak |
| max_kupno_60s | ta sama chwila | 0.82 | 0.82 / 0.82 | tak |
| kupujacy_10s | nowe w tym wieku | 0.81 | 0.81 / 0.82 | tak |
| kupno_sol_10s | ta sama chwila | 0.81 | 0.80 / 0.82 | tak |
| max_kupno_10s | ta sama chwila | 0.80 | 0.80 / 0.81 | tak |
| kupna_10s | nowe w tym wieku | 0.80 | 0.80 / 0.81 | tak |
| kupno_sol_10s | nowe w tym wieku | 0.80 | 0.80 / 0.80 | tak |
| kupujacy_10s | ta sama chwila | 0.80 | 0.79 / 0.81 | tak |
| kupna_60s | ta sama chwila | 0.79 | 0.79 / 0.79 | tak |
| max_kupno_10s | nowe w tym wieku | 0.79 | 0.79 / 0.80 | tak |
| sprzedaze_10s | nowe w tym wieku | 0.79 | 0.79 / 0.79 | tak |
| kupna_10s | ta sama chwila | 0.79 | 0.78 / 0.80 | tak |
| cisza_s | ta sama chwila | 0.23 | 0.23 / 0.22 | tak |

**Drzewo decyzyjne (który NOWY token: on vs tokeny odpalone w tej samej minucie, w tym samym wieku)**, głębokość 3, uczone na 70% czasu (N 6929), test na 30% (N 2668): AUC eksploracja 0.96, **test 0.95**.

```
|--- portfele_razem <= 12.50
|   |--- sol_1_slot <= 0.00
|   |   |--- class: 1
|   |--- sol_1_slot >  0.00
|   |   |--- zmiana_60s <= 0.07
|   |   |   |--- class: 0
|   |   |--- zmiana_60s >  0.07
|   |   |   |--- class: 1
|--- portfele_razem >  12.50
|   |--- cisza_s <= 42.50
|   |   |--- cisza_s <= 0.50
|   |   |   |--- class: 1
|   |   |--- cisza_s >  0.50
|   |   |   |--- class: 1
|   |--- cisza_s >  42.50
|   |   |--- tworca_sprzedal <= 0.50
|   |   |   |--- class: 1
|   |   |--- tworca_sprzedal >  0.50
|   |   |   |--- class: 0
```


**Drzewo decyzyjne (który token: on vs inne tokeny w tej chwili)**, głębokość 3, uczone na 70% czasu (N 5378), test na 30% (N 2300): AUC eksploracja 0.90, **test 0.87**.

```
|--- kupno_sol_60s <= 2.88
|   |--- cisza_s <= 30.50
|   |   |--- max_kupno_10s <= 0.14
|   |   |   |--- class: 0
|   |   |--- max_kupno_10s >  0.14
|   |   |   |--- class: 0
|   |--- cisza_s >  30.50
|   |   |--- class: 1
|--- kupno_sol_60s >  2.88
|   |--- cisza_s <= 1.50
|   |   |--- od_szczytu <= -0.81
|   |   |   |--- class: 0
|   |   |--- od_szczytu >  -0.81
|   |   |   |--- class: 1
|   |--- cisza_s >  1.50
|   |   |--- portfele_razem <= 11.50
|   |   |   |--- class: 0
|   |   |--- portfele_razem >  11.50
|   |   |   |--- class: 1
```


**Drzewo decyzyjne (kiedy: on vs inne chwile tego tokena)**, głębokość 3, uczone na 70% czasu (N 4808), test na 30% (N 1981): AUC eksploracja 0.74, **test 0.71**.

```
|--- netto_sol_60s <= 3.56
|   |--- od_szczytu <= -0.41
|   |   |--- kupno_sol_60s <= 0.14
|   |   |   |--- class: 0
|   |   |--- kupno_sol_60s >  0.14
|   |   |   |--- class: 0
|   |--- od_szczytu >  -0.41
|   |   |--- kupno_sol_60s <= 2.91
|   |   |   |--- class: 0
|   |   |--- kupno_sol_60s >  2.91
|   |   |   |--- class: 1
|--- netto_sol_60s >  3.56
|   |--- transakcje_razem <= 316.50
|   |   |--- transakcje_razem <= 14.50
|   |   |   |--- class: 0
|   |   |--- transakcje_razem >  14.50
|   |   |   |--- class: 1
|   |--- transakcje_razem >  316.50
|   |   |--- od_szczytu <= -0.02
|   |   |   |--- class: 0
|   |   |--- od_szczytu >  -0.02
|   |   |   |--- class: 0
```


## 2. Ślad X / social - źródło grafiki tokena (narzędzie, którym go odpalono)

| źródło | jego tokeny (N 1283) | inne tokeny w tej chwili (N 6395) | nowe w tym wieku (N 8314) |
|---|---|---|---|
| pump.fun (strona) | 52% | 53% | 76% |
| inne | 23% | 11% | 9% |
| brak | 9% | 24% | 1% |
| Axiom | 9% | 7% | 8% |
| z X (tweet -> coin) | 7% | 5% | 5% |

## 3. Wyjścia - chwila jego sprzedaży vs inne chwile w trakcie trzymania

| cecha | on (mediana) | w trakcie (mediana) | AUC vs w trakcie | AUC 70% / 30% |
|---|---|---|---|---|
| wynik_od_wejscia | 0.101 | 0.1 | 0.50 | 0.50 / 0.50 |
| od_szczytu_pozycji | -0.128 | -0.0633 | 0.37 | 0.36 / 0.39 |
| trzyma_s | 63 | 12 | 0.78 | 0.78 / 0.78 |
| zmiana_5s | 0 | 0 | 0.47 | 0.47 / 0.47 |
| zmiana_10s | 0 | 0.00553 | 0.44 | 0.43 / 0.46 |
| zmiana_30s | 0 | 0.0773 | 0.44 | 0.43 / 0.45 |
| sprzedaze_10s | 2 | 5 | 0.37 | 0.37 / 0.36 |
| kupna_10s | 2 | 8 | 0.32 | 0.32 / 0.32 |
| sprzedaz_sol_10s | 0.515 | 2.38 | 0.35 | 0.35 / 0.34 |
| max_sprzedaz_10s | 0.364 | 1.05 | 0.35 | 0.35 / 0.35 |
| netto_sol_10s | 0 | 0.653 | 0.41 | 0.40 / 0.44 |
| kol_sprzedaze_60s | 0 | 0 | 0.50 | 0.50 / 0.50 |
| tworca_sprzedal_w_trakcie | 0 | 0 | 0.51 | 0.51 / 0.51 |

**Drzewo decyzyjne (wyjście: jego sprzedaż vs trzymanie)**, głębokość 3, uczone na 70% czasu (N 4773), test na 30% (N 1854): AUC eksploracja 0.86, **test 0.84**.

```
|--- trzyma_s <= 14.50
|   |--- wynik_od_wejscia <= 1.21
|   |   |--- netto_sol_10s <= 32.73
|   |   |   |--- class: 0
|   |   |--- netto_sol_10s >  32.73
|   |   |   |--- class: 0
|   |--- wynik_od_wejscia >  1.21
|   |   |--- class: 0
|--- trzyma_s >  14.50
|   |--- trzyma_s <= 296.50
|   |   |--- trzyma_s <= 22.50
|   |   |   |--- class: 1
|   |   |--- trzyma_s >  22.50
|   |   |   |--- class: 1
|   |--- trzyma_s >  296.50
|   |   |--- trzyma_s <= 310.50
|   |   |   |--- class: 1
|   |   |--- trzyma_s >  310.50
|   |   |   |--- class: 1
```


**Pierwsza sprzedaż** (N 1139): wynik od wejścia (cena) kwartyle -31.5%, -8.6%, +8.2%, +30.7%, +65.2%; czas trzymania kwartyle 16 s, 19 s, 49 s, 300 s, 300 s; sprzedana część mediana 100%.

Rozkład wyniku przy pierwszej sprzedaży (przedziały po 10 pp; skupienie = stały próg TP/SL):

| przedział | N |  |
|---|---|---|
| -50..-40% | 68 | #################################################################### |
| -40..-30% | 54 | ###################################################### |
| -30..-20% | 62 | ############################################################## |
| -20..-10% | 77 | ############################################################################# |
| -10..+0% | 135 | ####################################################################################################################################### |
| +0..+10% | 200 | ######################################################################################################################################################################################################## |
| +10..+20% | 148 | #################################################################################################################################################### |
| +20..+30% | 105 | ######################################################################################################### |
| +30..+40% | 71 | ####################################################################### |
| +40..+50% | 56 | ######################################################## |
| +50..+60% | 37 | ##################################### |
| +60..+70% | 35 | ################################### |
| +70..+80% | 26 | ########################## |
| +80..+90% | 16 | ################ |
| +90..+100% | 11 | ########### |
| +100..+110% | 38 | ###################################### |

# Czy Bot A odróżnia trash? Jego wybory vs pominięte równie gorące starty - 08.10.2026 18:13

Jego wejść <= 60 s od startu z porównaniem: 382; pominiętych tokenów z top 5 (po kwocie zakupów w 10 s, w tej samej chwili): 1507. Jego token był nr 1 w 44% przypadków. Wynik liczony od ceny w chwili jego wejścia (to ocena WYBORU, nie jego wykonania).

| wynik tokena od chwili T | jego wybór | pominięte z top 5 | AUC (> 0.5 = jego lepsze) | AUC 1. / 2. połowa |
|---|---|---|---|---|
| max wzrost 5 min | +37.2% (śr. +69.5%) | +9.2% (śr. +49.0%) | 0.69 | 0.67 / 0.71 |
| max wzrost 30 min | +41.0% (śr. +93.0%) | +9.9% (śr. +57.6%) | 0.69 | 0.68 / 0.70 |
| cena po 5 min | -32.0% (śr. -1.2%) | -20.8% (śr. -8.2%) | 0.49 | 0.50 / 0.48 |
| cena po 30 min | -38.9% (śr. -1.3%) | -28.2% (śr. -10.1%) | 0.46 | 0.48 / 0.43 |
| migracja w 30 min | 6% | 4% | 0.51 | 0.50 / 0.51 |
| pump (+100% przed -70%) | 25% | 15% | 0.55 | 0.55 / 0.55 |
| rug (-70% przed +100%) | 4% | 13% | 0.46 | 0.45 / 0.46 |

W tej samej chwili jego token miał większy max wzrost w 30 min niż mediana pominiętych w 70% przypadków (50% = rzut monetą; N 382).

## Czy to tylko "bierze nr 1"? Nr 1 gorący start w chwilach, gdy był aktywny, ale nie kupował

|  | N | max 5 min (med.) | max 30 min (med.) | cena po 30 min (med.) | pump | rug | migracja 30 min |
|---|---|---|---|---|---|---|---|
| jego wybory | 382 | +37.2% | +41.0% | -38.9% | 25% | 4% | 6% |
| nr 1 gorący start bez niego | 151 | +1.1% | +1.3% | -36.6% | 13% | 8% | 6% |

## Naśladowcy (portfele, które kupują sekundy po nim i prawie tylko jego tokeny)

Portfeli kupujących <= 5 s po nim w >= 3 jego tokenach: 300; z nich 103 ma jego tokeny >= 20x częściej wśród swoich wczesnych zakupów niż losowo (baza 0.395%). Najbardziej wierni: 4 z 5 wczesnych zakupów to jego tokeny; 4 z 14 wczesnych zakupów to jego tokeny; 177 z 717 wczesnych zakupów to jego tokeny; 5 z 22 wczesnych zakupów to jego tokeny; 4 z 18 wczesnych zakupów to jego tokeny. Po jego zakupie inni kupują w 30 s mediana 9.7 SOL, z czego naśladowcy mediana 7% (średnio 12%). To mogą być boty kopiujące albo jego własne dodatkowe portfele.
