# Trader Bot D (Bot D) - 08.10.2026 18:59

Wybrany losowo (ziarno 20261008) spośród portfeli bez X i spoza listy KOL MadeOnSol, z >= 100 zamkniętymi pozycjami na krzywej, zyskownych w obu połowach okna i NIE kupujących w slocie utworzenia tokena (insiderzy twórcy odrzuceni). Dane: tylko nasz strumień pump.fun (krzywa).

|  | N | suma SOL | śr. / mediana na poz. | wygrane | śr. stawka SOL |
|---|---|---|---|---|---|
| zamknięte na krzywej | 2843 | +54.2 | +3.8% / -0.8% | 46% | 0.50 |
| 1. połowa | 1661 | +32.8 | +4.0% / -0.2% | 47% | 0.50 |
| 2. połowa | 1182 | +21.4 | +3.6% / -1.7% | 44% | 0.50 |

Pozycji otwartych na końcu / sprzedanych poza krzywą: 445; pominięte (sprzedał więcej tokenów, niż kupił na krzywej - przelew / inny portfel / dziura strumienia): 12. (śr. wynik na pozycję +3.8%)


# Na jakie sygnały wchodzi i wychodzi Bot D - 08.10.2026 19:00

Wejścia na krzywej pump.fun z pełnym zapisem rynku przed nimi: 3272 (z 3288 jego pozycji; reszta: PumpSwap / inne launchpady / brak w strumieniu). Kontrole: 13077 chwil tego samego tokena, 16335 innych tokenów w tej samej chwili. Podział czasu: 06.10 12:26.

## 1. Wejścia - cechy rynku tuż przed jego zakupem

| cecha | on (mediana) | ten sam token (mediana) | ta sama chwila (mediana) | nowe w tym wieku (mediana) | AUC vs ten sam token | AUC 70% / 30% | AUC vs ta sama chwila | AUC 70% / 30% | AUC vs nowe w tym wieku | AUC 70% / 30% |
|---|---|---|---|---|---|---|---|---|---|---|
| wiek_min | 0.65 | 5.43 | 3.45 | 0.667 | 0.23 | 0.22 / 0.25 | 0.29 | 0.29 / 0.28 | 0.50 | 0.50 / 0.50 |
| od_szczytu | -0.258 | -0.395 | -0.184 | -0.0737 | 0.60 | 0.62 / 0.55 | 0.45 | 0.45 / 0.44 | 0.34 | 0.35 / 0.33 |
| nowy_szczyt | 0 | 0 | 0 | 0 | 0.51 | 0.51 / 0.49 | 0.40 | 0.41 / 0.39 | 0.35 | 0.36 / 0.33 |
| zmiana_10s | -0.0613 | 0 | 0 | 0 | 0.44 | 0.44 / 0.45 | 0.45 | 0.44 / 0.46 | 0.44 | 0.44 / 0.45 |
| zmiana_30s | -0.0169 | 0 | -0.00142 | 0 | 0.49 | 0.48 / 0.50 | 0.51 | 0.51 / 0.52 | 0.50 | 0.50 / 0.50 |
| zmiana_60s | 0.063 | 0 | -0.00222 | 0 | 0.53 | 0.52 / 0.55 | 0.56 | 0.55 / 0.58 | 0.54 | 0.54 / 0.56 |
| zmiana_300s | 0.345 | 0 | -0.0013 | 0 | 0.63 | 0.63 / 0.62 | 0.66 | 0.66 / 0.65 | 0.67 | 0.67 / 0.67 |
| kupna_10s | 17 | 2 | 0 | 0 | 0.80 | 0.81 / 0.78 | 0.95 | 0.95 / 0.95 | 0.93 | 0.93 / 0.92 |
| sprzedaze_10s | 12 | 2 | 0 | 0 | 0.78 | 0.79 / 0.77 | 0.94 | 0.95 / 0.93 | 0.94 | 0.94 / 0.93 |
| kupujacy_10s | 16 | 2 | 0 | 0 | 0.80 | 0.81 / 0.79 | 0.96 | 0.96 / 0.96 | 0.94 | 0.94 / 0.94 |
| kupno_sol_10s | 9.36 | 0.348 | 0 | 0 | 0.82 | 0.83 / 0.81 | 0.96 | 0.96 / 0.96 | 0.92 | 0.92 / 0.92 |
| netto_sol_10s | 2.08 | 0 | 0 | 0 | 0.55 | 0.56 / 0.54 | 0.58 | 0.58 / 0.57 | 0.56 | 0.56 / 0.54 |
| max_kupno_10s | 2 | 0.204 | 0 | 0 | 0.81 | 0.81 / 0.80 | 0.95 | 0.95 / 0.95 | 0.90 | 0.90 / 0.90 |
| kol_kupna_10s | 0 | 0 | 0 | 0 | 0.52 | 0.52 / 0.52 | 0.53 | 0.53 / 0.53 | 0.53 | 0.53 / 0.53 |
| kupna_60s | 42 | 15 | 1 | 1 | 0.70 | 0.71 / 0.69 | 0.92 | 0.93 / 0.91 | 0.94 | 0.95 / 0.93 |
| sprzedaze_60s | 27 | 14 | 1 | 0 | 0.65 | 0.65 / 0.65 | 0.89 | 0.89 / 0.88 | 0.93 | 0.93 / 0.93 |
| kupujacy_60s | 37 | 13 | 1 | 1 | 0.71 | 0.72 / 0.70 | 0.95 | 0.95 / 0.94 | 0.96 | 0.96 / 0.95 |
| kupno_sol_60s | 23.7 | 5.56 | 0.061 | 0.0902 | 0.77 | 0.77 / 0.75 | 0.96 | 0.96 / 0.95 | 0.95 | 0.96 / 0.94 |
| netto_sol_60s | 5.2 | 0 | -1.37e-06 | 6e-09 | 0.64 | 0.64 / 0.63 | 0.72 | 0.72 / 0.71 | 0.70 | 0.71 / 0.68 |
| max_kupno_60s | 3.01 | 1.28 | 0.0399 | 0.0594 | 0.80 | 0.80 / 0.78 | 0.94 | 0.95 / 0.94 | 0.92 | 0.92 / 0.91 |
| kol_kupna_60s | 0 | 0 | 0 | 0 | 0.53 | 0.52 / 0.53 | 0.55 | 0.55 / 0.56 | 0.55 | 0.55 / 0.56 |
| kol_kupna_300s | 0 | 0 | 0 | 0 | 0.50 | 0.51 / 0.50 | 0.58 | 0.58 / 0.59 | 0.59 | 0.58 / 0.60 |
| portfele_razem | 66 | 142 | 12 | 3 | 0.37 | 0.36 / 0.37 | 0.73 | 0.74 / 0.71 | 0.94 | 0.94 / 0.93 |
| transakcje_razem | 119 | 343 | 44 | 8 | 0.35 | 0.34 / 0.36 | 0.65 | 0.66 / 0.64 | 0.90 | 0.90 / 0.90 |
| przyspieszenie | 2.78 | 1.02 | 0.273 | 5.45 | 0.72 | 0.73 / 0.70 | 0.74 | 0.75 / 0.72 | 0.51 | 0.50 / 0.52 |
| tworca_sprzedal | 0 | 0 | 0 | 0 | 0.47 | 0.47 / 0.49 | 0.56 | 0.57 / 0.54 | 0.48 | 0.50 / 0.46 |
| tworca_ma_pct | 0 | 0 | 0 | 0 | 0.53 | 0.54 / 0.51 | 0.53 | 0.56 / 0.49 | 0.46 | 0.49 / 0.40 |
| cisza_s | 0 | 1 | 8 | 14 | 0.25 | 0.24 / 0.27 | 0.08 | 0.07 / 0.09 | 0.04 | 0.04 / 0.04 |
| tworca_kupil_sol | 0.57 | 0.593 | 0 | 0.198 | 0.50 | 0.50 / 0.50 | 0.63 | 0.66 / 0.57 | 0.53 | 0.57 / 0.44 |
| kupujacy_1_slot | 4 | 4 | 1 | 1 | 0.49 | 0.49 / 0.50 | 0.77 | 0.79 / 0.75 | 0.77 | 0.79 / 0.73 |
| sol_1_slot | 7.89 | 7.82 | 0.282 | 0.495 | 0.50 | 0.50 / 0.51 | 0.81 | 0.82 / 0.77 | 0.79 | 0.81 / 0.75 |

**Najsilniejsze różnice** (|AUC - 0.5|, z kontrolą; kierunek musi się zgadzać w obu połowach czasu):

| cecha | kontrola | AUC | 70% / 30% | stabilne |
|---|---|---|---|---|
| kupujacy_60s | nowe w tym wieku | 0.96 | 0.96 / 0.95 | tak |
| kupno_sol_60s | ta sama chwila | 0.96 | 0.96 / 0.95 | tak |
| kupujacy_10s | ta sama chwila | 0.96 | 0.96 / 0.96 | tak |
| kupno_sol_10s | ta sama chwila | 0.96 | 0.96 / 0.96 | tak |
| cisza_s | nowe w tym wieku | 0.04 | 0.04 / 0.04 | tak |
| kupna_10s | ta sama chwila | 0.95 | 0.95 / 0.95 | tak |
| kupno_sol_60s | nowe w tym wieku | 0.95 | 0.96 / 0.94 | tak |
| max_kupno_10s | ta sama chwila | 0.95 | 0.95 / 0.95 | tak |
| kupujacy_60s | ta sama chwila | 0.95 | 0.95 / 0.94 | tak |
| max_kupno_60s | ta sama chwila | 0.94 | 0.95 / 0.94 | tak |
| kupna_60s | nowe w tym wieku | 0.94 | 0.95 / 0.93 | tak |
| sprzedaze_10s | ta sama chwila | 0.94 | 0.95 / 0.93 | tak |
| kupujacy_10s | nowe w tym wieku | 0.94 | 0.94 / 0.94 | tak |
| portfele_razem | nowe w tym wieku | 0.94 | 0.94 / 0.93 | tak |
| sprzedaze_10s | nowe w tym wieku | 0.94 | 0.94 / 0.93 | tak |
| sprzedaze_60s | nowe w tym wieku | 0.93 | 0.93 / 0.93 | tak |
| kupna_10s | nowe w tym wieku | 0.93 | 0.93 / 0.92 | tak |
| cisza_s | ta sama chwila | 0.08 | 0.07 / 0.09 | tak |
| kupno_sol_10s | nowe w tym wieku | 0.92 | 0.92 / 0.92 | tak |
| kupna_60s | ta sama chwila | 0.92 | 0.93 / 0.91 | tak |
| max_kupno_60s | nowe w tym wieku | 0.92 | 0.92 / 0.91 | tak |
| max_kupno_10s | nowe w tym wieku | 0.90 | 0.90 / 0.90 | tak |

**Drzewo decyzyjne (który NOWY token: on vs tokeny odpalone w tej samej minucie, w tym samym wieku)**, głębokość 3, uczone na 70% czasu (N 19469), test na 30% (N 6835): AUC eksploracja 0.98, **test 0.97**.

```
|--- kupno_sol_60s <= 4.79
|   |--- cisza_s <= 0.50
|   |   |--- class: 1
|   |--- cisza_s >  0.50
|   |   |--- sol_1_slot <= 0.00
|   |   |   |--- class: 1
|   |   |--- sol_1_slot >  0.00
|   |   |   |--- class: 0
|--- kupno_sol_60s >  4.79
|   |--- cisza_s <= 1.50
|   |   |--- cisza_s <= 0.50
|   |   |   |--- class: 1
|   |   |--- cisza_s >  0.50
|   |   |   |--- class: 1
|   |--- cisza_s >  1.50
|   |   |--- netto_sol_60s <= 2.16
|   |   |   |--- class: 0
|   |   |--- netto_sol_60s >  2.16
|   |   |   |--- class: 1
```


**Drzewo decyzyjne (który token: on vs inne tokeny w tej chwili)**, głębokość 3, uczone na 70% czasu (N 13754), test na 30% (N 5853): AUC eksploracja 0.97, **test 0.96**.

```
|--- kupno_sol_60s <= 4.79
|   |--- netto_sol_10s <= -4.05
|   |   |--- max_kupno_60s <= 0.00
|   |   |   |--- class: 1
|   |   |--- max_kupno_60s >  0.00
|   |   |   |--- class: 1
|   |--- netto_sol_10s >  -4.05
|   |   |--- kupno_sol_10s <= 2.60
|   |   |   |--- class: 0
|   |   |--- kupno_sol_10s >  2.60
|   |   |   |--- class: 1
|--- kupno_sol_60s >  4.79
|   |--- cisza_s <= 2.50
|   |   |--- kupujacy_10s <= 6.50
|   |   |   |--- class: 1
|   |   |--- kupujacy_10s >  6.50
|   |   |   |--- class: 1
|   |--- cisza_s >  2.50
|   |   |--- kupno_sol_10s <= 5.39
|   |   |   |--- class: 0
|   |   |--- kupno_sol_10s >  5.39
|   |   |   |--- class: 1
```


**Drzewo decyzyjne (kiedy: on vs inne chwile tego tokena)**, głębokość 3, uczone na 70% czasu (N 11893), test na 30% (N 4456): AUC eksploracja 0.87, **test 0.84**.

```
|--- kupno_sol_10s <= 0.98
|   |--- netto_sol_10s <= -2.84
|   |   |--- portfele_razem <= 58.50
|   |   |   |--- class: 1
|   |   |--- portfele_razem >  58.50
|   |   |   |--- class: 0
|   |--- netto_sol_10s >  -2.84
|   |   |--- wiek_min <= 1.00
|   |   |   |--- class: 1
|   |   |--- wiek_min >  1.00
|   |   |   |--- class: 0
|--- kupno_sol_10s >  0.98
|   |--- wiek_min <= 1.56
|   |   |--- wiek_min <= 0.08
|   |   |   |--- class: 0
|   |   |--- wiek_min >  0.08
|   |   |   |--- class: 1
|   |--- wiek_min >  1.56
|   |   |--- netto_sol_10s <= -5.29
|   |   |   |--- class: 1
|   |   |--- netto_sol_10s >  -5.29
|   |   |   |--- class: 0
```


## 2. Ślad X / social - źródło grafiki tokena (narzędzie, którym go odpalono)

| źródło | jego tokeny (N 3272) | inne tokeny w tej chwili (N 16335) | nowe w tym wieku (N 23032) |
|---|---|---|---|
| pump.fun (strona) | 39% | 53% | 76% |
| brak | 5% | 28% | 1% |
| inne | 24% | 9% | 9% |
| Axiom | 20% | 5% | 8% |
| z X (tweet -> coin) | 12% | 4% | 6% |

## 3. Wyjścia - chwila jego sprzedaży vs inne chwile w trakcie trzymania

| cecha | on (mediana) | w trakcie (mediana) | AUC vs w trakcie | AUC 70% / 30% |
|---|---|---|---|---|
| wynik_od_wejscia | -0.023 | 0.0032 | 0.46 | 0.46 / 0.45 |
| od_szczytu_pozycji | -0.124 | -0.0654 | 0.35 | 0.35 / 0.35 |
| trzyma_s | 21 | 7 | 0.98 | 0.99 / 0.97 |
| zmiana_5s | -2.84e-08 | -0.00953 | 0.52 | 0.52 / 0.52 |
| zmiana_10s | -0.0121 | -0.0244 | 0.52 | 0.52 / 0.52 |
| zmiana_30s | -0.0656 | -0.00958 | 0.47 | 0.47 / 0.46 |
| sprzedaze_10s | 7 | 14 | 0.30 | 0.30 / 0.30 |
| kupna_10s | 7 | 18 | 0.29 | 0.29 / 0.28 |
| sprzedaz_sol_10s | 2.78 | 8.67 | 0.24 | 0.24 / 0.24 |
| max_sprzedaz_10s | 1.02 | 2.04 | 0.24 | 0.24 / 0.25 |
| netto_sol_10s | -0.296 | -0.333 | 0.50 | 0.50 / 0.50 |
| kol_sprzedaze_60s | 0 | 0 | 0.50 | 0.50 / 0.50 |
| tworca_sprzedal_w_trakcie | 0 | 0 | 0.51 | 0.51 / 0.51 |

**Drzewo decyzyjne (wyjście: jego sprzedaż vs trzymanie)**, głębokość 3, uczone na 70% czasu (N 12053), test na 30% (N 4341): AUC eksploracja 1.00, **test 1.00**.

```
|--- trzyma_s <= 16.50
|   |--- wynik_od_wejscia <= 0.87
|   |   |--- wynik_od_wejscia <= 0.34
|   |   |   |--- class: 0
|   |   |--- wynik_od_wejscia >  0.34
|   |   |   |--- class: 0
|   |--- wynik_od_wejscia >  0.87
|   |   |--- trzyma_s <= 12.50
|   |   |   |--- class: 0
|   |   |--- trzyma_s >  12.50
|   |   |   |--- class: 0
|--- trzyma_s >  16.50
|   |--- trzyma_s <= 25.50
|   |   |--- max_sprzedaz_10s <= 3.78
|   |   |   |--- class: 1
|   |   |--- max_sprzedaz_10s >  3.78
|   |   |   |--- class: 1
|   |--- trzyma_s >  25.50
|   |   |--- trzyma_s <= 73.00
|   |   |   |--- class: 0
|   |   |--- trzyma_s >  73.00
|   |   |   |--- class: 1
```


**Pierwsza sprzedaż** (N 2884): wynik od wejścia (cena) kwartyle -27.9%, -14.3%, -2.3%, +12.5%, +36.2%; czas trzymania kwartyle 21 s, 21 s, 21 s, 21 s, 21 s; sprzedana część mediana 100%.

Rozkład wyniku przy pierwszej sprzedaży (przedziały po 10 pp; skupienie = stały próg TP/SL):

| przedział | N |  |
|---|---|---|
| -50..-40% | 122 | ########################################################################################################################## |
| -40..-30% | 128 | ################################################################################################################################ |
| -30..-20% | 244 | #################################################################################################################################################################################################################################################### |
| -20..-10% | 489 | ######################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################### |
| -10..+0% | 618 | ########################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################## |
| +0..+10% | 484 | #################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################### |
| +10..+20% | 290 | ################################################################################################################################################################################################################################################################################################## |
| +20..+30% | 151 | ####################################################################################################################################################### |
| +30..+40% | 109 | ############################################################################################################# |
| +40..+50% | 58 | ########################################################## |
| +50..+60% | 50 | ################################################## |
| +60..+70% | 36 | #################################### |
| +70..+80% | 24 | ######################## |
| +80..+90% | 15 | ############### |
| +90..+100% | 18 | ################## |
| +100..+110% | 48 | ################################################ |

# Czy Bot D odróżnia trash? Jego wybory vs pominięte równie gorące starty - 08.10.2026 19:00

Jego wejść <= 60 s od startu z porównaniem: 1558; pominiętych tokenów z top 5 (po kwocie zakupów w 10 s, w tej samej chwili): 5250. Jego token był nr 1 w 52% przypadków. Wynik liczony od ceny w chwili jego wejścia (to ocena WYBORU, nie jego wykonania).

| wynik tokena od chwili T | jego wybór | pominięte z top 5 | AUC (> 0.5 = jego lepsze) | AUC 1. / 2. połowa |
|---|---|---|---|---|
| max wzrost 5 min | +17.2% (śr. +56.2%) | +5.7% (śr. +50.2%) | 0.60 | 0.58 / 0.61 |
| max wzrost 30 min | +18.6% (śr. +70.8%) | +6.3% (śr. +56.8%) | 0.60 | 0.59 / 0.62 |
| cena po 5 min | -21.4% (śr. -0.6%) | -19.7% (śr. -11.6%) | 0.53 | 0.55 / 0.52 |
| cena po 30 min | -28.2% (śr. -5.7%) | -26.2% (śr. -14.6%) | 0.50 | 0.52 / 0.48 |
| migracja w 30 min | 5% | 3% | 0.51 | 0.51 / 0.50 |
| pump (+100% przed -70%) | 19% | 13% | 0.53 | 0.53 / 0.53 |
| rug (-70% przed +100%) | 5% | 13% | 0.46 | 0.46 / 0.46 |

W tej samej chwili jego token miał większy max wzrost w 30 min niż mediana pominiętych w 58% przypadków (50% = rzut monetą; N 1558).

## Czy to tylko "bierze nr 1"? Nr 1 gorący start w chwilach, gdy był aktywny, ale nie kupował

|  | N | max 5 min (med.) | max 30 min (med.) | cena po 30 min (med.) | pump | rug | migracja 30 min |
|---|---|---|---|---|---|---|---|
| jego wybory | 1559 | +17.1% | +18.5% | -28.2% | 19% | 5% | 5% |
| nr 1 gorący start bez niego | 40 | +1.6% | +1.6% | -34.3% | 18% | 8% | 8% |

## Naśladowcy (portfele, które kupują sekundy po nim i prawie tylko jego tokeny)

Portfeli kupujących <= 5 s po nim w >= 3 jego tokenach: 1112; z nich 313 ma jego tokeny >= 20x częściej wśród swoich wczesnych zakupów niż losowo (baza 1.770%). Najbardziej wierni: 4 z 4 wczesnych zakupów to jego tokeny; 5 z 6 wczesnych zakupów to jego tokeny; 7 z 9 wczesnych zakupów to jego tokeny; 17 z 22 wczesnych zakupów to jego tokeny; 17 z 22 wczesnych zakupów to jego tokeny. Po jego zakupie inni kupują w 30 s mediana 6.8 SOL, z czego naśladowcy mediana 3% (średnio 9%). To mogą być boty kopiujące albo jego własne dodatkowe portfele.
