# Trader Bot C (Bot C) - 08.10.2026 18:49

Wybrany losowo (ziarno 20261008) spośród portfeli bez X i spoza listy KOL MadeOnSol, z >= 100 zamkniętymi pozycjami na krzywej, zyskownych w obu połowach okna i NIE kupujących w slocie utworzenia tokena (insiderzy twórcy odrzuceni). Dane: tylko nasz strumień pump.fun (krzywa).

|  | N | suma SOL | śr. / mediana na poz. | wygrane | śr. stawka SOL |
|---|---|---|---|---|---|
| zamknięte na krzywej | 573 | +54.7 | +6.0% / +0.8% | 54% | 1.52 |
| 1. połowa | 306 | +36.7 | +7.5% / +1.3% | 57% | 1.56 |
| 2. połowa | 267 | +18.0 | +4.2% / +0.3% | 51% | 1.48 |

Pozycji otwartych na końcu / sprzedanych poza krzywą: 115; pominięte (sprzedał więcej tokenów, niż kupił na krzywej - przelew / inny portfel / dziura strumienia): 1. (śr. wynik na pozycję +6.0%)


# Na jakie sygnały wchodzi i wychodzi Bot C - 08.10.2026 18:49

Wejścia na krzywej pump.fun z pełnym zapisem rynku przed nimi: 675 (z 688 jego pozycji; reszta: PumpSwap / inne launchpady / brak w strumieniu). Kontrole: 3102 chwil tego samego tokena, 3375 innych tokenów w tej samej chwili. Podział czasu: 06.10 14:39.

## 1. Wejścia - cechy rynku tuż przed jego zakupem

| cecha | on (mediana) | ten sam token (mediana) | ta sama chwila (mediana) | nowe w tym wieku (mediana) | AUC vs ten sam token | AUC 70% / 30% | AUC vs ta sama chwila | AUC 70% / 30% | AUC vs nowe w tym wieku | AUC 70% / 30% |
|---|---|---|---|---|---|---|---|---|---|---|
| wiek_min | 2.88 | 4.47 | 4.43 | 2.97 | 0.47 | 0.46 / 0.51 | 0.46 | 0.46 / 0.48 | 0.49 | 0.49 / 0.50 |
| od_szczytu | -0.139 | -0.254 | -0.22 | -0.132 | 0.60 | 0.61 / 0.58 | 0.57 | 0.57 / 0.57 | 0.51 | 0.51 / 0.49 |
| nowy_szczyt | 0 | 0 | 0 | 0 | 0.51 | 0.53 / 0.48 | 0.46 | 0.47 / 0.43 | 0.43 | 0.44 / 0.39 |
| zmiana_10s | 0 | 0 | 0 | 0 | 0.53 | 0.53 / 0.53 | 0.55 | 0.54 / 0.56 | 0.52 | 0.52 / 0.52 |
| zmiana_30s | 0.0465 | 0 | -0.00212 | 0 | 0.63 | 0.63 / 0.62 | 0.69 | 0.68 / 0.72 | 0.68 | 0.67 / 0.69 |
| zmiana_60s | 0.122 | 0 | -0.00255 | 0 | 0.65 | 0.65 / 0.66 | 0.71 | 0.69 / 0.76 | 0.72 | 0.70 / 0.76 |
| zmiana_300s | 0.284 | 0.00351 | -0.00192 | 0 | 0.59 | 0.57 / 0.65 | 0.70 | 0.68 / 0.76 | 0.72 | 0.70 / 0.78 |
| kupna_10s | 3 | 3 | 0 | 0 | 0.48 | 0.47 / 0.50 | 0.75 | 0.73 / 0.78 | 0.83 | 0.82 / 0.86 |
| sprzedaze_10s | 3 | 3 | 0 | 0 | 0.48 | 0.46 / 0.51 | 0.72 | 0.71 / 0.75 | 0.81 | 0.80 / 0.85 |
| kupujacy_10s | 3 | 3 | 0 | 0 | 0.48 | 0.47 / 0.50 | 0.76 | 0.75 / 0.79 | 0.84 | 0.82 / 0.87 |
| kupno_sol_10s | 0.884 | 0.868 | 0 | 0 | 0.48 | 0.48 / 0.49 | 0.76 | 0.75 / 0.79 | 0.84 | 0.82 / 0.87 |
| netto_sol_10s | 0 | 0 | 0 | 0 | 0.49 | 0.50 / 0.47 | 0.53 | 0.54 / 0.52 | 0.52 | 0.53 / 0.51 |
| max_kupno_10s | 0.494 | 0.474 | 0 | 0 | 0.50 | 0.50 / 0.49 | 0.76 | 0.75 / 0.79 | 0.84 | 0.83 / 0.87 |
| kol_kupna_10s | 0 | 0 | 0 | 0 | 0.49 | 0.49 / 0.49 | 0.50 | 0.50 / 0.50 | 0.50 | 0.50 / 0.50 |
| kupna_60s | 20 | 15 | 1 | 0 | 0.55 | 0.53 / 0.58 | 0.82 | 0.81 / 0.84 | 0.89 | 0.88 / 0.90 |
| sprzedaze_60s | 13 | 12 | 2 | 0 | 0.51 | 0.50 / 0.55 | 0.76 | 0.75 / 0.79 | 0.85 | 0.84 / 0.87 |
| kupujacy_60s | 18 | 14 | 1 | 0 | 0.54 | 0.53 / 0.57 | 0.84 | 0.84 / 0.86 | 0.91 | 0.91 / 0.93 |
| kupno_sol_60s | 8.45 | 6.08 | 0.0781 | 0 | 0.55 | 0.54 / 0.58 | 0.84 | 0.83 / 0.86 | 0.90 | 0.90 / 0.92 |
| netto_sol_60s | 2.05 | 0.168 | -0.00099 | 0 | 0.57 | 0.57 / 0.57 | 0.70 | 0.69 / 0.71 | 0.71 | 0.71 / 0.72 |
| max_kupno_60s | 1.89 | 1.47 | 0.0494 | 0 | 0.57 | 0.57 / 0.59 | 0.84 | 0.83 / 0.86 | 0.90 | 0.89 / 0.92 |
| kol_kupna_60s | 0 | 0 | 0 | 0 | 0.50 | 0.50 / 0.51 | 0.52 | 0.52 / 0.53 | 0.53 | 0.52 / 0.54 |
| kol_kupna_300s | 0 | 0 | 0 | 0 | 0.51 | 0.50 / 0.51 | 0.55 | 0.54 / 0.56 | 0.56 | 0.55 / 0.57 |
| portfele_razem | 67 | 90 | 14 | 4 | 0.44 | 0.44 / 0.45 | 0.68 | 0.67 / 0.69 | 0.89 | 0.89 / 0.90 |
| transakcje_razem | 140 | 197 | 52 | 11 | 0.44 | 0.44 / 0.45 | 0.62 | 0.61 / 0.64 | 0.83 | 0.82 / 0.85 |
| przyspieszenie | 0.857 | 1.2 | 0.235 | 0 | 0.42 | 0.42 / 0.41 | 0.56 | 0.57 / 0.56 | 0.71 | 0.69 / 0.75 |
| tworca_sprzedal | 0 | 0 | 0 | 1 | 0.49 | 0.49 / 0.51 | 0.53 | 0.52 / 0.53 | 0.39 | 0.40 / 0.39 |
| tworca_ma_pct | 0 | 0 | 0 | 0 | 0.50 | 0.50 / 0.49 | 0.52 | 0.52 / 0.51 | 0.51 | 0.53 / 0.47 |
| cisza_s | 1 | 1 | 8 | 101 | 0.52 | 0.52 / 0.54 | 0.27 | 0.27 / 0.26 | 0.08 | 0.08 / 0.07 |
| tworca_kupil_sol | 0.248 | 0.287 | 0 | 0.218 | 0.49 | 0.49 / 0.49 | 0.56 | 0.56 / 0.56 | 0.46 | 0.48 / 0.44 |
| kupujacy_1_slot | 3 | 3 | 1 | 1 | 0.49 | 0.49 / 0.49 | 0.65 | 0.66 / 0.63 | 0.64 | 0.66 / 0.60 |
| sol_1_slot | 2.6 | 2.86 | 0.487 | 0.508 | 0.49 | 0.49 / 0.49 | 0.66 | 0.66 / 0.65 | 0.65 | 0.66 / 0.62 |

**Najsilniejsze różnice** (|AUC - 0.5|, z kontrolą; kierunek musi się zgadzać w obu połowach czasu):

| cecha | kontrola | AUC | 70% / 30% | stabilne |
|---|---|---|---|---|
| cisza_s | nowe w tym wieku | 0.08 | 0.08 / 0.07 | tak |
| kupujacy_60s | nowe w tym wieku | 0.91 | 0.91 / 0.93 | tak |
| kupno_sol_60s | nowe w tym wieku | 0.90 | 0.90 / 0.92 | tak |
| max_kupno_60s | nowe w tym wieku | 0.90 | 0.89 / 0.92 | tak |
| portfele_razem | nowe w tym wieku | 0.89 | 0.89 / 0.90 | tak |
| kupna_60s | nowe w tym wieku | 0.89 | 0.88 / 0.90 | tak |
| sprzedaze_60s | nowe w tym wieku | 0.85 | 0.84 / 0.87 | tak |
| kupujacy_60s | ta sama chwila | 0.84 | 0.84 / 0.86 | tak |
| kupno_sol_60s | ta sama chwila | 0.84 | 0.83 / 0.86 | tak |
| max_kupno_10s | nowe w tym wieku | 0.84 | 0.83 / 0.87 | tak |
| kupno_sol_10s | nowe w tym wieku | 0.84 | 0.82 / 0.87 | tak |
| kupujacy_10s | nowe w tym wieku | 0.84 | 0.82 / 0.87 | tak |
| max_kupno_60s | ta sama chwila | 0.84 | 0.83 / 0.86 | tak |
| transakcje_razem | nowe w tym wieku | 0.83 | 0.82 / 0.85 | tak |
| kupna_10s | nowe w tym wieku | 0.83 | 0.82 / 0.86 | tak |
| kupna_60s | ta sama chwila | 0.82 | 0.81 / 0.84 | tak |
| sprzedaze_10s | nowe w tym wieku | 0.81 | 0.80 / 0.85 | tak |
| max_kupno_10s | ta sama chwila | 0.76 | 0.75 / 0.79 | tak |
| kupno_sol_10s | ta sama chwila | 0.76 | 0.75 / 0.79 | tak |
| kupujacy_10s | ta sama chwila | 0.76 | 0.75 / 0.79 | tak |
| sprzedaze_60s | ta sama chwila | 0.76 | 0.75 / 0.79 | tak |
| kupna_10s | ta sama chwila | 0.75 | 0.73 / 0.78 | tak |

**Drzewo decyzyjne (który NOWY token: on vs tokeny odpalone w tej samej minucie, w tym samym wieku)**, głębokość 3, uczone na 70% czasu (N 3522), test na 30% (N 1206): AUC eksploracja 0.95, **test 0.95**.

```
|--- max_kupno_60s <= 0.61
|   |--- portfele_razem <= 36.50
|   |   |--- zmiana_30s <= 0.00
|   |   |   |--- class: 0
|   |   |--- zmiana_30s >  0.00
|   |   |   |--- class: 1
|   |--- portfele_razem >  36.50
|   |   |--- cisza_s <= 194.00
|   |   |   |--- class: 1
|   |   |--- cisza_s >  194.00
|   |   |   |--- class: 0
|--- max_kupno_60s >  0.61
|   |--- wiek_min <= 1.34
|   |   |--- netto_sol_60s <= 1.31
|   |   |   |--- class: 0
|   |   |--- netto_sol_60s >  1.31
|   |   |   |--- class: 1
|   |--- wiek_min >  1.34
|   |   |--- zmiana_60s <= -0.49
|   |   |   |--- class: 1
|   |   |--- zmiana_60s >  -0.49
|   |   |   |--- class: 1
```


**Drzewo decyzyjne (który token: on vs inne tokeny w tej chwili)**, głębokość 3, uczone na 70% czasu (N 2826), test na 30% (N 1224): AUC eksploracja 0.88, **test 0.88**.

```
|--- max_kupno_60s <= 0.61
|   |--- cisza_s <= 32.00
|   |   |--- zmiana_30s <= 0.00
|   |   |   |--- class: 0
|   |   |--- zmiana_30s >  0.00
|   |   |   |--- class: 0
|   |--- cisza_s >  32.00
|   |   |--- class: 1
|--- max_kupno_60s >  0.61
|   |--- kupujacy_60s <= 5.50
|   |   |--- od_szczytu <= -0.00
|   |   |   |--- class: 0
|   |   |--- od_szczytu >  -0.00
|   |   |   |--- class: 1
|   |--- kupujacy_60s >  5.50
|   |   |--- zmiana_30s <= -0.20
|   |   |   |--- class: 0
|   |   |--- zmiana_30s >  -0.20
|   |   |   |--- class: 1
```


**Drzewo decyzyjne (kiedy: on vs inne chwile tego tokena)**, głębokość 3, uczone na 70% czasu (N 2659), test na 30% (N 1118): AUC eksploracja 0.73, **test 0.66**.

```
|--- zmiana_30s <= 0.00
|   |--- od_szczytu <= -0.23
|   |   |--- kupno_sol_60s <= 2.00
|   |   |   |--- class: 0
|   |   |--- kupno_sol_60s >  2.00
|   |   |   |--- class: 0
|   |--- od_szczytu >  -0.23
|   |   |--- wiek_min <= 0.23
|   |   |   |--- class: 0
|   |   |--- wiek_min >  0.23
|   |   |   |--- class: 1
|--- zmiana_30s >  0.00
|   |--- kupno_sol_60s <= 37.83
|   |   |--- wiek_min <= 2.55
|   |   |   |--- class: 1
|   |   |--- wiek_min >  2.55
|   |   |   |--- class: 1
|   |--- kupno_sol_60s >  37.83
|   |   |--- sol_1_slot <= 3.74
|   |   |   |--- class: 0
|   |   |--- sol_1_slot >  3.74
|   |   |   |--- class: 0
```


## 2. Ślad X / social - źródło grafiki tokena (narzędzie, którym go odpalono)

| źródło | jego tokeny (N 675) | inne tokeny w tej chwili (N 3375) | nowe w tym wieku (N 4053) |
|---|---|---|---|
| pump.fun (strona) | 53% | 52% | 75% |
| brak | 16% | 26% | 1% |
| inne | 15% | 11% | 9% |
| Axiom | 9% | 7% | 9% |
| z X (tweet -> coin) | 7% | 5% | 6% |

## 3. Wyjścia - chwila jego sprzedaży vs inne chwile w trakcie trzymania

| cecha | on (mediana) | w trakcie (mediana) | AUC vs w trakcie | AUC 70% / 30% |
|---|---|---|---|---|
| wynik_od_wejscia | 0.135 | 0.112 | 0.55 | 0.55 / 0.54 |
| od_szczytu_pozycji | -0.0468 | -0.0234 | 0.41 | 0.42 / 0.39 |
| trzyma_s | 51 | 12 | 0.81 | 0.80 / 0.84 |
| zmiana_5s | 0 | 0.00676 | 0.46 | 0.45 / 0.47 |
| zmiana_10s | 0 | 0.0367 | 0.44 | 0.43 / 0.46 |
| zmiana_30s | 0.0462 | 0.117 | 0.43 | 0.43 / 0.43 |
| sprzedaze_10s | 3 | 4 | 0.48 | 0.48 / 0.46 |
| kupna_10s | 4 | 5 | 0.45 | 0.45 / 0.47 |
| sprzedaz_sol_10s | 1.05 | 1.28 | 0.46 | 0.47 / 0.45 |
| max_sprzedaz_10s | 0.554 | 0.68 | 0.47 | 0.47 / 0.45 |
| netto_sol_10s | 0.0116 | 0.0982 | 0.51 | 0.51 / 0.52 |
| kol_sprzedaze_60s | 0 | 0 | 0.50 | 0.50 / 0.51 |
| tworca_sprzedal_w_trakcie | 0 | 0 | 0.51 | 0.51 / 0.51 |

**Drzewo decyzyjne (wyjście: jego sprzedaż vs trzymanie)**, głębokość 3, uczone na 70% czasu (N 2233), test na 30% (N 855): AUC eksploracja 0.88, **test 0.90**.

```
|--- trzyma_s <= 11.50
|   |--- wynik_od_wejscia <= 0.50
|   |   |--- zmiana_10s <= -0.09
|   |   |   |--- class: 0
|   |   |--- zmiana_10s >  -0.09
|   |   |   |--- class: 0
|   |--- wynik_od_wejscia >  0.50
|   |   |--- class: 1
|--- trzyma_s >  11.50
|   |--- trzyma_s <= 55.50
|   |   |--- netto_sol_10s <= 4.21
|   |   |   |--- class: 0
|   |   |--- netto_sol_10s >  4.21
|   |   |   |--- class: 1
|   |--- trzyma_s >  55.50
|   |   |--- trzyma_s <= 67.50
|   |   |   |--- class: 1
|   |   |--- trzyma_s >  67.50
|   |   |   |--- class: 1
```


**Pierwsza sprzedaż** (N 580): wynik od wejścia (cena) kwartyle -10.5%, +0.2%, +10.8%, +25.0%, +46.0%; czas trzymania kwartyle 13 s, 16 s, 51 s, 60 s, 61 s; sprzedana część mediana 100%.

Rozkład wyniku przy pierwszej sprzedaży (przedziały po 10 pp; skupienie = stały próg TP/SL):

| przedział | N |  |
|---|---|---|
| -50..-40% | 2 | ## |
| -40..-30% | 8 | ######## |
| -30..-20% | 16 | ################ |
| -20..-10% | 33 | ################################# |
| -10..+0% | 84 | #################################################################################### |
| +0..+10% | 138 | ########################################################################################################################################## |
| +10..+20% | 119 | ####################################################################################################################### |
| +20..+30% | 61 | ############################################################# |
| +30..+40% | 37 | ##################################### |
| +40..+50% | 35 | ################################### |
| +50..+60% | 17 | ################# |
| +60..+70% | 14 | ############## |
| +70..+80% | 9 | ######### |
| +80..+90% | 3 | ### |
| +90..+100% | 1 | # |
| +100..+110% | 3 | ### |

# Czy Bot C odróżnia trash? Jego wybory vs pominięte równie gorące starty - 08.10.2026 18:49

Jego wejść <= 60 s od startu z porównaniem: 88; pominiętych tokenów z top 5 (po kwocie zakupów w 10 s, w tej samej chwili): 378. Jego token był nr 1 w 10% przypadków. Wynik liczony od ceny w chwili jego wejścia (to ocena WYBORU, nie jego wykonania).

| wynik tokena od chwili T | jego wybór | pominięte z top 5 | AUC (> 0.5 = jego lepsze) | AUC 1. / 2. połowa |
|---|---|---|---|---|
| max wzrost 5 min | +23.6% (śr. +50.0%) | +9.5% (śr. +46.2%) | 0.65 | 0.63 / 0.67 |
| max wzrost 30 min | +25.6% (śr. +59.3%) | +9.8% (śr. +56.2%) | 0.64 | 0.64 / 0.65 |
| cena po 5 min | -14.6% (śr. -4.1%) | -19.0% (śr. -12.9%) | 0.58 | 0.55 / 0.61 |
| cena po 30 min | -19.3% (śr. -13.2%) | -26.1% (śr. -13.0%) | 0.57 | 0.56 / 0.58 |
| migracja w 30 min | 1% | 6% | 0.48 | 0.48 / 0.47 |
| pump (+100% przed -70%) | 14% | 14% | 0.50 | 0.48 / 0.52 |
| rug (-70% przed +100%) | 1% | 14% | 0.43 | 0.41 / 0.46 |

W tej samej chwili jego token miał większy max wzrost w 30 min niż mediana pominiętych w 68% przypadków (50% = rzut monetą; N 88).

## Czy to tylko "bierze nr 1"? Nr 1 gorący start w chwilach, gdy był aktywny, ale nie kupował

|  | N | max 5 min (med.) | max 30 min (med.) | cena po 30 min (med.) | pump | rug | migracja 30 min |
|---|---|---|---|---|---|---|---|
| jego wybory | 88 | +23.6% | +25.6% | -19.3% | 14% | 1% | 1% |
| nr 1 gorący start bez niego | 250 | +13.6% | +15.1% | -38.1% | 14% | 14% | 3% |

## Naśladowcy (portfele, które kupują sekundy po nim i prawie tylko jego tokeny)

Portfeli kupujących <= 5 s po nim w >= 3 jego tokenach: 28; z nich 20 ma jego tokeny >= 20x częściej wśród swoich wczesnych zakupów niż losowo (baza 0.106%). Najbardziej wierni: 11 z 20 wczesnych zakupów to jego tokeny; 5 z 14 wczesnych zakupów to jego tokeny; 11 z 36 wczesnych zakupów to jego tokeny; 13 z 99 wczesnych zakupów to jego tokeny; 6 z 49 wczesnych zakupów to jego tokeny. Po jego zakupie inni kupują w 30 s mediana 3.4 SOL, z czego naśladowcy mediana 15% (średnio 24%). To mogą być boty kopiujące albo jego własne dodatkowe portfele.
