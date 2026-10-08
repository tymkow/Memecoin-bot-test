# Trader Bot A2 (Bot A2) - 08.10.2026 18:54

Wybrany losowo (ziarno 20261008) spośród portfeli bez X i spoza listy KOL MadeOnSol, z >= 100 zamkniętymi pozycjami na krzywej, zyskownych w obu połowach okna i NIE kupujących w slocie utworzenia tokena (insiderzy twórcy odrzuceni). Dane: tylko nasz strumień pump.fun (krzywa).

|  | N | suma SOL | śr. / mediana na poz. | wygrane | śr. stawka SOL |
|---|---|---|---|---|---|
| zamknięte na krzywej | 1087 | +13.4 | +1.1% / -0.6% | 49% | 0.63 |
| 1. połowa | 722 | +17.0 | +2.0% / -1.2% | 48% | 0.64 |
| 2. połowa | 365 | -3.6 | -0.8% / -0.2% | 50% | 0.62 |

Pozycji otwartych na końcu / sprzedanych poza krzywą: 186; pominięte (sprzedał więcej tokenów, niż kupił na krzywej - przelew / inny portfel / dziura strumienia): 27. (śr. wynik na pozycję +1.1%)


# Na jakie sygnały wchodzi i wychodzi Bot A2 - 08.10.2026 18:54

Wejścia na krzywej pump.fun z pełnym zapisem rynku przed nimi: 1269 (z 1273 jego pozycji; reszta: PumpSwap / inne launchpady / brak w strumieniu). Kontrole: 5441 chwil tego samego tokena, 6325 innych tokenów w tej samej chwili. Podział czasu: 06.10 08:42.

## 1. Wejścia - cechy rynku tuż przed jego zakupem

| cecha | on (mediana) | ten sam token (mediana) | ta sama chwila (mediana) | nowe w tym wieku (mediana) | AUC vs ten sam token | AUC 70% / 30% | AUC vs ta sama chwila | AUC 70% / 30% | AUC vs nowe w tym wieku | AUC 70% / 30% |
|---|---|---|---|---|---|---|---|---|---|---|
| wiek_min | 2.57 | 9.52 | 4.55 | 2.67 | 0.33 | 0.32 / 0.35 | 0.40 | 0.40 / 0.40 | 0.49 | 0.49 / 0.49 |
| od_szczytu | -0.147 | -0.347 | -0.223 | -0.0971 | 0.66 | 0.68 / 0.63 | 0.57 | 0.56 / 0.58 | 0.47 | 0.46 / 0.50 |
| nowy_szczyt | 0 | 0 | 0 | 0 | 0.54 | 0.55 / 0.54 | 0.48 | 0.48 / 0.48 | 0.43 | 0.43 / 0.44 |
| zmiana_10s | 0 | 0 | 0 | 0 | 0.56 | 0.56 / 0.55 | 0.58 | 0.58 / 0.58 | 0.57 | 0.56 / 0.58 |
| zmiana_30s | 0.0248 | 0 | -0.00117 | 0 | 0.58 | 0.58 / 0.59 | 0.63 | 0.62 / 0.64 | 0.61 | 0.61 / 0.63 |
| zmiana_60s | 0.0586 | 0 | -0.00156 | 0 | 0.62 | 0.62 / 0.60 | 0.65 | 0.65 / 0.65 | 0.64 | 0.64 / 0.63 |
| zmiana_300s | 0.0716 | 0 | -0.00118 | 0 | 0.59 | 0.62 / 0.54 | 0.62 | 0.64 / 0.58 | 0.63 | 0.65 / 0.58 |
| kupna_10s | 7 | 1 | 0 | 0 | 0.69 | 0.71 / 0.65 | 0.81 | 0.81 / 0.80 | 0.83 | 0.84 / 0.82 |
| sprzedaze_10s | 4 | 1 | 0 | 0 | 0.64 | 0.65 / 0.61 | 0.74 | 0.75 / 0.74 | 0.81 | 0.82 / 0.80 |
| kupujacy_10s | 6 | 1 | 0 | 0 | 0.70 | 0.71 / 0.65 | 0.82 | 0.82 / 0.82 | 0.84 | 0.85 / 0.83 |
| kupno_sol_10s | 2.81 | 0.0495 | 0 | 0 | 0.70 | 0.72 / 0.67 | 0.83 | 0.83 / 0.83 | 0.83 | 0.84 / 0.82 |
| netto_sol_10s | 0.716 | 0 | 0 | 0 | 0.61 | 0.61 / 0.60 | 0.64 | 0.64 / 0.63 | 0.60 | 0.61 / 0.59 |
| max_kupno_10s | 0.988 | 0.0489 | 0 | 0 | 0.70 | 0.71 / 0.67 | 0.83 | 0.83 / 0.82 | 0.82 | 0.83 / 0.82 |
| kol_kupna_10s | 0 | 0 | 0 | 0 | 0.51 | 0.51 / 0.51 | 0.51 | 0.51 / 0.52 | 0.51 | 0.51 / 0.52 |
| kupna_60s | 21 | 7 | 1 | 0 | 0.68 | 0.70 / 0.65 | 0.80 | 0.80 / 0.80 | 0.88 | 0.88 / 0.87 |
| sprzedaze_60s | 10 | 5 | 1 | 0 | 0.61 | 0.62 / 0.58 | 0.72 | 0.72 / 0.72 | 0.85 | 0.85 / 0.84 |
| kupujacy_60s | 20 | 6 | 1 | 0 | 0.69 | 0.71 / 0.65 | 0.83 | 0.83 / 0.83 | 0.89 | 0.89 / 0.89 |
| kupno_sol_60s | 11.9 | 2.45 | 0.0818 | 0 | 0.71 | 0.73 / 0.68 | 0.84 | 0.84 / 0.85 | 0.88 | 0.88 / 0.87 |
| netto_sol_60s | 3.77 | 0 | -0.000202 | 0 | 0.68 | 0.68 / 0.67 | 0.72 | 0.71 / 0.73 | 0.70 | 0.70 / 0.70 |
| max_kupno_60s | 1.98 | 0.988 | 0.0494 | 0 | 0.71 | 0.72 / 0.69 | 0.83 | 0.82 / 0.85 | 0.86 | 0.86 / 0.86 |
| kol_kupna_60s | 0 | 0 | 0 | 0 | 0.52 | 0.51 / 0.52 | 0.52 | 0.52 / 0.53 | 0.53 | 0.52 / 0.54 |
| kol_kupna_300s | 0 | 0 | 0 | 0 | 0.51 | 0.51 / 0.52 | 0.54 | 0.53 / 0.56 | 0.55 | 0.54 / 0.56 |
| portfele_razem | 70 | 132 | 18 | 3 | 0.39 | 0.39 / 0.40 | 0.68 | 0.67 / 0.68 | 0.93 | 0.93 / 0.93 |
| transakcje_razem | 142 | 328 | 62 | 9 | 0.38 | 0.37 / 0.39 | 0.61 | 0.61 / 0.61 | 0.88 | 0.88 / 0.87 |
| przyspieszenie | 1.64 | 1.09 | 0.424 | 2.81 | 0.59 | 0.61 / 0.57 | 0.67 | 0.67 / 0.67 | 0.51 | 0.51 / 0.51 |
| tworca_sprzedal | 0 | 0 | 0 | 0 | 0.47 | 0.47 / 0.48 | 0.49 | 0.49 / 0.47 | 0.39 | 0.40 / 0.37 |
| tworca_ma_pct | 0 | 0 | 0 | 0 | 0.53 | 0.54 / 0.52 | 0.57 | 0.57 / 0.54 | 0.53 | 0.55 / 0.49 |
| cisza_s | 1 | 2 | 8 | 81 | 0.32 | 0.31 / 0.34 | 0.21 | 0.20 / 0.21 | 0.10 | 0.10 / 0.10 |
| tworca_kupil_sol | 0.395 | 0.395 | 0 | 0.208 | 0.49 | 0.49 / 0.49 | 0.57 | 0.58 / 0.54 | 0.48 | 0.50 / 0.42 |
| kupujacy_1_slot | 3 | 3 | 1 | 1 | 0.51 | 0.51 / 0.51 | 0.67 | 0.67 / 0.66 | 0.68 | 0.68 / 0.67 |
| sol_1_slot | 3.28 | 3.13 | 0.495 | 0.602 | 0.50 | 0.51 / 0.50 | 0.66 | 0.66 / 0.66 | 0.68 | 0.68 / 0.67 |

**Najsilniejsze różnice** (|AUC - 0.5|, z kontrolą; kierunek musi się zgadzać w obu połowach czasu):

| cecha | kontrola | AUC | 70% / 30% | stabilne |
|---|---|---|---|---|
| portfele_razem | nowe w tym wieku | 0.93 | 0.93 / 0.93 | tak |
| cisza_s | nowe w tym wieku | 0.10 | 0.10 / 0.10 | tak |
| kupujacy_60s | nowe w tym wieku | 0.89 | 0.89 / 0.89 | tak |
| kupno_sol_60s | nowe w tym wieku | 0.88 | 0.88 / 0.87 | tak |
| transakcje_razem | nowe w tym wieku | 0.88 | 0.88 / 0.87 | tak |
| kupna_60s | nowe w tym wieku | 0.88 | 0.88 / 0.87 | tak |
| max_kupno_60s | nowe w tym wieku | 0.86 | 0.86 / 0.86 | tak |
| sprzedaze_60s | nowe w tym wieku | 0.85 | 0.85 / 0.84 | tak |
| kupno_sol_60s | ta sama chwila | 0.84 | 0.84 / 0.85 | tak |
| kupujacy_10s | nowe w tym wieku | 0.84 | 0.85 / 0.83 | tak |
| kupna_10s | nowe w tym wieku | 0.83 | 0.84 / 0.82 | tak |
| kupno_sol_10s | nowe w tym wieku | 0.83 | 0.84 / 0.82 | tak |
| max_kupno_60s | ta sama chwila | 0.83 | 0.82 / 0.85 | tak |
| kupujacy_60s | ta sama chwila | 0.83 | 0.83 / 0.83 | tak |
| kupno_sol_10s | ta sama chwila | 0.83 | 0.83 / 0.83 | tak |
| max_kupno_10s | ta sama chwila | 0.83 | 0.83 / 0.82 | tak |
| max_kupno_10s | nowe w tym wieku | 0.82 | 0.83 / 0.82 | tak |
| kupujacy_10s | ta sama chwila | 0.82 | 0.82 / 0.82 | tak |
| sprzedaze_10s | nowe w tym wieku | 0.81 | 0.82 / 0.80 | tak |
| kupna_10s | ta sama chwila | 0.81 | 0.81 / 0.80 | tak |
| kupna_60s | ta sama chwila | 0.80 | 0.80 / 0.80 | tak |
| cisza_s | ta sama chwila | 0.21 | 0.20 / 0.21 | tak |

**Drzewo decyzyjne (który NOWY token: on vs tokeny odpalone w tej samej minucie, w tym samym wieku)**, głębokość 3, uczone na 70% czasu (N 7373), test na 30% (N 2819): AUC eksploracja 0.96, **test 0.94**.

```
|--- portfele_razem <= 11.50
|   |--- sol_1_slot <= 0.00
|   |   |--- class: 1
|   |--- sol_1_slot >  0.00
|   |   |--- netto_sol_10s <= 1.43
|   |   |   |--- class: 0
|   |   |--- netto_sol_10s >  1.43
|   |   |   |--- class: 0
|--- portfele_razem >  11.50
|   |--- cisza_s <= 12.50
|   |   |--- od_szczytu <= -0.87
|   |   |   |--- class: 0
|   |   |--- od_szczytu >  -0.87
|   |   |   |--- class: 1
|   |--- cisza_s >  12.50
|   |   |--- tworca_sprzedal <= 0.50
|   |   |   |--- class: 1
|   |   |--- tworca_sprzedal >  0.50
|   |   |   |--- class: 0
```


**Drzewo decyzyjne (który token: on vs inne tokeny w tej chwili)**, głębokość 3, uczone na 70% czasu (N 5313), test na 30% (N 2281): AUC eksploracja 0.90, **test 0.90**.

```
|--- kupno_sol_10s <= 0.28
|   |--- cisza_s <= 31.00
|   |   |--- kupno_sol_60s <= 1.66
|   |   |   |--- class: 0
|   |   |--- kupno_sol_60s >  1.66
|   |   |   |--- class: 0
|   |--- cisza_s >  31.00
|   |   |--- tworca_kupil_sol <= 0.07
|   |   |   |--- class: 1
|   |   |--- tworca_kupil_sol >  0.07
|   |   |   |--- class: 1
|--- kupno_sol_10s >  0.28
|   |--- portfele_razem <= 9.50
|   |   |--- netto_sol_10s <= 0.50
|   |   |   |--- class: 0
|   |   |--- netto_sol_10s >  0.50
|   |   |   |--- class: 0
|   |--- portfele_razem >  9.50
|   |   |--- cisza_s <= 2.50
|   |   |   |--- class: 1
|   |   |--- cisza_s >  2.50
|   |   |   |--- class: 1
```


**Drzewo decyzyjne (kiedy: on vs inne chwile tego tokena)**, głębokość 3, uczone na 70% czasu (N 4693), test na 30% (N 2017): AUC eksploracja 0.77, **test 0.71**.

```
|--- kupno_sol_60s <= 7.93
|   |--- od_szczytu <= -0.34
|   |   |--- kupno_sol_10s <= 0.45
|   |   |   |--- class: 0
|   |   |--- kupno_sol_10s >  0.45
|   |   |   |--- class: 0
|   |--- od_szczytu >  -0.34
|   |   |--- portfele_razem <= 11.50
|   |   |   |--- class: 0
|   |   |--- portfele_razem >  11.50
|   |   |   |--- class: 1
|--- kupno_sol_60s >  7.93
|   |--- transakcje_razem <= 388.00
|   |   |--- portfele_razem <= 8.50
|   |   |   |--- class: 0
|   |   |--- portfele_razem >  8.50
|   |   |   |--- class: 1
|   |--- transakcje_razem >  388.00
|   |   |--- wiek_min <= 7.39
|   |   |   |--- class: 1
|   |   |--- wiek_min >  7.39
|   |   |   |--- class: 0
```


## 2. Ślad X / social - źródło grafiki tokena (narzędzie, którym go odpalono)

| źródło | jego tokeny (N 1269) | inne tokeny w tej chwili (N 6325) | nowe w tym wieku (N 8923) |
|---|---|---|---|
| pump.fun (strona) | 55% | 52% | 75% |
| inne | 22% | 11% | 11% |
| brak | 7% | 24% | 1% |
| Axiom | 10% | 7% | 8% |
| z X (tweet -> coin) | 6% | 5% | 6% |

## 3. Wyjścia - chwila jego sprzedaży vs inne chwile w trakcie trzymania

| cecha | on (mediana) | w trakcie (mediana) | AUC vs w trakcie | AUC 70% / 30% |
|---|---|---|---|---|
| wynik_od_wejscia | 0.0841 | 0.0922 | 0.49 | 0.48 / 0.50 |
| od_szczytu_pozycji | -0.122 | -0.0646 | 0.38 | 0.38 / 0.39 |
| trzyma_s | 56 | 10 | 0.78 | 0.78 / 0.78 |
| zmiana_5s | 0 | 0 | 0.47 | 0.47 / 0.47 |
| zmiana_10s | 0 | 0.0135 | 0.44 | 0.45 / 0.43 |
| zmiana_30s | 0.00359 | 0.0767 | 0.45 | 0.45 / 0.45 |
| sprzedaze_10s | 2 | 5 | 0.36 | 0.36 / 0.35 |
| kupna_10s | 3 | 9 | 0.32 | 0.32 / 0.31 |
| sprzedaz_sol_10s | 0.621 | 2.68 | 0.34 | 0.34 / 0.32 |
| max_sprzedaz_10s | 0.397 | 1.14 | 0.33 | 0.34 / 0.32 |
| netto_sol_10s | 0 | 0.804 | 0.42 | 0.42 / 0.42 |
| kol_sprzedaze_60s | 0 | 0 | 0.50 | 0.50 / 0.50 |
| tworca_sprzedal_w_trakcie | 0 | 0 | 0.51 | 0.51 / 0.51 |

**Drzewo decyzyjne (wyjście: jego sprzedaż vs trzymanie)**, głębokość 3, uczone na 70% czasu (N 4694), test na 30% (N 1904): AUC eksploracja 0.87, **test 0.87**.

```
|--- trzyma_s <= 14.50
|   |--- netto_sol_10s <= 23.08
|   |   |--- max_sprzedaz_10s <= 6.41
|   |   |   |--- class: 0
|   |   |--- max_sprzedaz_10s >  6.41
|   |   |   |--- class: 0
|   |--- netto_sol_10s >  23.08
|   |   |--- zmiana_5s <= 0.36
|   |   |   |--- class: 0
|   |   |--- zmiana_5s >  0.36
|   |   |   |--- class: 1
|--- trzyma_s >  14.50
|   |--- trzyma_s <= 296.50
|   |   |--- trzyma_s <= 19.50
|   |   |   |--- class: 1
|   |   |--- trzyma_s >  19.50
|   |   |   |--- class: 1
|   |--- trzyma_s >  296.50
|   |   |--- trzyma_s <= 302.00
|   |   |   |--- class: 1
|   |   |--- trzyma_s >  302.00
|   |   |   |--- class: 1
```


**Pierwsza sprzedaż** (N 1136): wynik od wejścia (cena) kwartyle -35.9%, -12.2%, +7.9%, +28.9%, +61.1%; czas trzymania kwartyle 16 s, 18 s, 46 s, 300 s, 300 s; sprzedana część mediana 100%.

Rozkład wyniku przy pierwszej sprzedaży (przedziały po 10 pp; skupienie = stały próg TP/SL):

| przedział | N |  |
|---|---|---|
| -50..-40% | 102 | ###################################################################################################### |
| -40..-30% | 44 | ############################################ |
| -30..-20% | 76 | ############################################################################ |
| -20..-10% | 81 | ################################################################################# |
| -10..+0% | 126 | ############################################################################################################################## |
| +0..+10% | 179 | ################################################################################################################################################################################### |
| +10..+20% | 157 | ############################################################################################################################################################# |
| +20..+30% | 98 | ################################################################################################## |
| +30..+40% | 76 | ############################################################################ |
| +40..+50% | 45 | ############################################# |
| +50..+60% | 34 | ################################## |
| +60..+70% | 32 | ################################ |
| +70..+80% | 19 | ################### |
| +80..+90% | 12 | ############ |
| +90..+100% | 8 | ######## |
| +100..+110% | 47 | ############################################### |

# Czy Bot A2 odróżnia trash? Jego wybory vs pominięte równie gorące starty - 08.10.2026 18:54

Jego wejść <= 60 s od startu z porównaniem: 354; pominiętych tokenów z top 5 (po kwocie zakupów w 10 s, w tej samej chwili): 1396. Jego token był nr 1 w 38% przypadków. Wynik liczony od ceny w chwili jego wejścia (to ocena WYBORU, nie jego wykonania).

| wynik tokena od chwili T | jego wybór | pominięte z top 5 | AUC (> 0.5 = jego lepsze) | AUC 1. / 2. połowa |
|---|---|---|---|---|
| max wzrost 5 min | +43.1% (śr. +92.4%) | +11.1% (śr. +44.6%) | 0.70 | 0.68 / 0.71 |
| max wzrost 30 min | +48.2% (śr. +119.9%) | +12.3% (śr. +50.2%) | 0.70 | 0.69 / 0.71 |
| cena po 5 min | -27.7% (śr. +8.4%) | -22.1% (śr. -16.3%) | 0.53 | 0.51 / 0.54 |
| cena po 30 min | -37.4% (śr. +4.5%) | -30.8% (śr. -22.1%) | 0.48 | 0.47 / 0.50 |
| migracja w 30 min | 5% | 4% | 0.51 | 0.50 / 0.51 |
| pump (+100% przed -70%) | 31% | 15% | 0.58 | 0.56 / 0.59 |
| rug (-70% przed +100%) | 5% | 14% | 0.46 | 0.46 / 0.45 |

W tej samej chwili jego token miał większy max wzrost w 30 min niż mediana pominiętych w 74% przypadków (50% = rzut monetą; N 354).

## Czy to tylko "bierze nr 1"? Nr 1 gorący start w chwilach, gdy był aktywny, ale nie kupował

|  | N | max 5 min (med.) | max 30 min (med.) | cena po 30 min (med.) | pump | rug | migracja 30 min |
|---|---|---|---|---|---|---|---|
| jego wybory | 354 | +43.1% | +48.2% | -37.4% | 31% | 5% | 5% |
| nr 1 gorący start bez niego | 177 | +17.3% | +21.8% | -38.2% | 24% | 12% | 7% |

## Naśladowcy (portfele, które kupują sekundy po nim i prawie tylko jego tokeny)

Portfeli kupujących <= 5 s po nim w >= 3 jego tokenach: 260; z nich 100 ma jego tokeny >= 20x częściej wśród swoich wczesnych zakupów niż losowo (baza 0.356%). Najbardziej wierni: 4 z 16 wczesnych zakupów to jego tokeny; 152 z 735 wczesnych zakupów to jego tokeny; 6 z 33 wczesnych zakupów to jego tokeny; 22 z 129 wczesnych zakupów to jego tokeny; 4 z 24 wczesnych zakupów to jego tokeny. Po jego zakupie inni kupują w 30 s mediana 10.5 SOL, z czego naśladowcy mediana 12% (średnio 17%). To mogą być boty kopiujące albo jego własne dodatkowe portfele.
