# Trader Bot E (Bot E) - 08.10.2026 19:08

Wybrany losowo (ziarno 20261008) spośród portfeli bez X i spoza listy KOL MadeOnSol, z >= 100 zamkniętymi pozycjami na krzywej, zyskownych w obu połowach okna i NIE kupujących w slocie utworzenia tokena (insiderzy twórcy odrzuceni). Dane: tylko nasz strumień pump.fun (krzywa).

|  | N | suma SOL | śr. / mediana na poz. | wygrane | śr. stawka SOL |
|---|---|---|---|---|---|
| zamknięte na krzywej | 697 | +38.4 | +5.5% / +2.9% | 58% | 1.06 |
| 1. połowa | 479 | +30.1 | +6.1% / +3.2% | 60% | 1.09 |
| 2. połowa | 218 | +8.4 | +4.1% / +1.2% | 52% | 1.00 |

Pozycji otwartych na końcu / sprzedanych poza krzywą: 39; pominięte (sprzedał więcej tokenów, niż kupił na krzywej - przelew / inny portfel / dziura strumienia): 0. (śr. wynik na pozycję +5.5%)


# Na jakie sygnały wchodzi i wychodzi Bot E - 08.10.2026 19:08

Wejścia na krzywej pump.fun z pełnym zapisem rynku przed nimi: 732 (z 736 jego pozycji; reszta: PumpSwap / inne launchpady / brak w strumieniu). Kontrole: 3038 chwil tego samego tokena, 3660 innych tokenów w tej samej chwili. Podział czasu: 06.10 09:33.

## 1. Wejścia - cechy rynku tuż przed jego zakupem

| cecha | on (mediana) | ten sam token (mediana) | ta sama chwila (mediana) | nowe w tym wieku (mediana) | AUC vs ten sam token | AUC 70% / 30% | AUC vs ta sama chwila | AUC 70% / 30% | AUC vs nowe w tym wieku | AUC 70% / 30% |
|---|---|---|---|---|---|---|---|---|---|---|
| wiek_min | 0.0667 | 3.19 | 4.73 | 0.0667 | 0.03 | 0.03 / 0.04 | 0.06 | 0.06 / 0.06 | 0.48 | 0.48 / 0.49 |
| od_szczytu | -0.168 | -0.51 | -0.205 | 0 | 0.81 | 0.81 / 0.81 | 0.54 | 0.55 / 0.53 | 0.25 | 0.25 / 0.26 |
| nowy_szczyt | 0 | 0 | 0 | 1 | 0.54 | 0.55 / 0.53 | 0.43 | 0.44 / 0.41 | 0.27 | 0.27 / 0.26 |
| zmiana_10s | -0.0144 | 0 | 0 | 0 | 0.49 | 0.56 / 0.34 | 0.48 | 0.54 / 0.34 | 0.49 | 0.56 / 0.34 |
| zmiana_30s | -0.134 | 0 | -0.00139 | 0 | 0.46 | 0.53 / 0.34 | 0.45 | 0.52 / 0.33 | 0.44 | 0.52 / 0.30 |
| zmiana_60s | -0.115 | -0.000661 | -0.00162 | 0 | 0.46 | 0.54 / 0.32 | 0.44 | 0.51 / 0.30 | 0.43 | 0.51 / 0.25 |
| zmiana_300s | 2.42 | 0 | -0.000836 | 0 | 0.96 | 0.95 / 0.98 | 0.98 | 0.98 / 0.99 | 1.00 | 1.00 / nan |
| kupna_10s | 26 | 1 | 0 | 2 | 0.89 | 0.88 / 0.92 | 0.98 | 0.98 / 0.97 | 0.95 | 0.96 / 0.94 |
| sprzedaze_10s | 9 | 2 | 0 | 0 | 0.73 | 0.71 / 0.79 | 0.91 | 0.91 / 0.91 | 0.90 | 0.90 / 0.91 |
| kupujacy_10s | 24.5 | 1 | 0 | 2 | 0.90 | 0.89 / 0.92 | 0.98 | 0.98 / 0.98 | 0.96 | 0.96 / 0.95 |
| kupno_sol_10s | 21.6 | 0.0406 | 0 | 0.441 | 0.95 | 0.95 / 0.96 | 0.99 | 0.99 / 0.99 | 0.94 | 0.95 / 0.93 |
| netto_sol_10s | 10.9 | 0 | 0 | 0.206 | 0.84 | 0.85 / 0.81 | 0.85 | 0.87 / 0.82 | 0.80 | 0.82 / 0.76 |
| max_kupno_10s | 4 | 0.0352 | 0 | 0.382 | 0.94 | 0.94 / 0.95 | 0.98 | 0.99 / 0.98 | 0.90 | 0.90 / 0.89 |
| kol_kupna_10s | 0 | 0 | 0 | 0 | 0.53 | 0.53 / 0.54 | 0.54 | 0.54 / 0.55 | 0.54 | 0.54 / 0.55 |
| kupna_60s | 30 | 12 | 1 | 2 | 0.67 | 0.64 / 0.72 | 0.90 | 0.90 / 0.90 | 0.95 | 0.95 / 0.94 |
| sprzedaze_60s | 10 | 14 | 1 | 0 | 0.50 | 0.48 / 0.55 | 0.77 | 0.77 / 0.78 | 0.88 | 0.88 / 0.89 |
| kupujacy_60s | 28 | 11 | 1 | 2 | 0.68 | 0.66 / 0.74 | 0.93 | 0.93 / 0.93 | 0.95 | 0.96 / 0.95 |
| kupno_sol_60s | 27.6 | 4.44 | 0.0761 | 0.84 | 0.80 | 0.79 / 0.84 | 0.96 | 0.96 / 0.96 | 0.94 | 0.95 / 0.94 |
| netto_sol_60s | 13.5 | 0 | -0.000392 | 0.396 | 0.88 | 0.89 / 0.86 | 0.91 | 0.93 / 0.88 | 0.87 | 0.88 / 0.83 |
| max_kupno_60s | 4.94 | 1.04 | 0.0486 | 0.509 | 0.91 | 0.90 / 0.92 | 0.96 | 0.97 / 0.96 | 0.91 | 0.91 / 0.90 |
| kol_kupna_60s | 0 | 0 | 0 | 0 | 0.51 | 0.50 / 0.51 | 0.55 | 0.55 / 0.55 | 0.55 | 0.55 / 0.56 |
| kol_kupna_300s | 0 | 0 | 0 | 0 | 0.42 | 0.41 / 0.44 | 0.55 | 0.55 / 0.55 | 0.56 | 0.55 / 0.57 |
| portfele_razem | 29 | 129 | 17 | 2 | 0.16 | 0.15 / 0.17 | 0.59 | 0.59 / 0.59 | 0.95 | 0.95 / 0.95 |
| transakcje_razem | 40 | 307 | 58.5 | 4 | 0.12 | 0.12 / 0.14 | 0.47 | 0.47 / 0.47 | 0.93 | 0.93 / 0.93 |
| przyspieszenie | 6 | 0.766 | 0.545 | 6 | 0.92 | 0.92 / 0.92 | 0.86 | 0.87 / 0.85 | 0.49 | 0.49 / 0.48 |
| tworca_sprzedal | 0 | 1 | 0 | 0 | 0.41 | 0.40 / 0.43 | 0.56 | 0.57 / 0.52 | 0.60 | 0.62 / 0.56 |
| tworca_ma_pct | 0 | 0 | 0 | 0.247 | 0.67 | 0.69 / 0.63 | 0.63 | 0.65 / 0.57 | 0.49 | 0.53 / 0.42 |
| cisza_s | 0 | 2 | 8 | 2 | 0.19 | 0.20 / 0.17 | 0.07 | 0.06 / 0.08 | 0.06 | 0.06 / 0.08 |
| tworca_kupil_sol | 1.25 | 1.3 | 0 | 0.198 | 0.50 | 0.50 / 0.50 | 0.68 | 0.71 / 0.59 | 0.61 | 0.65 / 0.50 |
| kupujacy_1_slot | 5 | 5 | 1 | 1 | 0.49 | 0.49 / 0.50 | 0.82 | 0.82 / 0.81 | 0.83 | 0.83 / 0.83 |
| sol_1_slot | 10.3 | 10.4 | 0.489 | 0.683 | 0.49 | 0.49 / 0.51 | 0.85 | 0.86 / 0.82 | 0.86 | 0.87 / 0.84 |

**Najsilniejsze różnice** (|AUC - 0.5|, z kontrolą; kierunek musi się zgadzać w obu połowach czasu):

| cecha | kontrola | AUC | 70% / 30% | stabilne |
|---|---|---|---|---|
| kupno_sol_10s | ta sama chwila | 0.99 | 0.99 / 0.99 | tak |
| max_kupno_10s | ta sama chwila | 0.98 | 0.99 / 0.98 | tak |
| kupujacy_10s | ta sama chwila | 0.98 | 0.98 / 0.98 | tak |
| zmiana_300s | ta sama chwila | 0.98 | 0.98 / 0.99 | tak |
| kupna_10s | ta sama chwila | 0.98 | 0.98 / 0.97 | tak |
| wiek_min | ten sam token | 0.03 | 0.03 / 0.04 | tak |
| max_kupno_60s | ta sama chwila | 0.96 | 0.97 / 0.96 | tak |
| kupno_sol_60s | ta sama chwila | 0.96 | 0.96 / 0.96 | tak |
| zmiana_300s | ten sam token | 0.96 | 0.95 / 0.98 | tak |
| kupujacy_10s | nowe w tym wieku | 0.96 | 0.96 / 0.95 | tak |
| kupujacy_60s | nowe w tym wieku | 0.95 | 0.96 / 0.95 | tak |
| kupna_10s | nowe w tym wieku | 0.95 | 0.96 / 0.94 | tak |
| portfele_razem | nowe w tym wieku | 0.95 | 0.95 / 0.95 | tak |
| kupno_sol_10s | ten sam token | 0.95 | 0.95 / 0.96 | tak |
| kupna_60s | nowe w tym wieku | 0.95 | 0.95 / 0.94 | tak |
| max_kupno_10s | ten sam token | 0.94 | 0.94 / 0.95 | tak |
| kupno_sol_60s | nowe w tym wieku | 0.94 | 0.95 / 0.94 | tak |
| wiek_min | ta sama chwila | 0.06 | 0.06 / 0.06 | tak |
| kupno_sol_10s | nowe w tym wieku | 0.94 | 0.95 / 0.93 | tak |
| cisza_s | nowe w tym wieku | 0.06 | 0.06 / 0.08 | tak |
| cisza_s | ta sama chwila | 0.07 | 0.06 / 0.08 | tak |
| kupujacy_60s | ta sama chwila | 0.93 | 0.93 / 0.93 | tak |

**Drzewo decyzyjne (który NOWY token: on vs tokeny odpalone w tej samej minucie, w tym samym wieku)**, głębokość 3, uczone na 70% czasu (N 4370), test na 30% (N 1773): AUC eksploracja 0.98, **test 0.96**.

```
|--- kupujacy_10s <= 7.50
|   |--- cisza_s <= 0.50
|   |   |--- class: 1
|   |--- cisza_s >  0.50
|   |   |--- kupno_sol_10s <= 6.88
|   |   |   |--- class: 0
|   |   |--- kupno_sol_10s >  6.88
|   |   |   |--- class: 0
|--- kupujacy_10s >  7.50
|   |--- cisza_s <= 1.50
|   |   |--- cisza_s <= 0.50
|   |   |   |--- class: 1
|   |   |--- cisza_s >  0.50
|   |   |   |--- class: 1
|   |--- cisza_s >  1.50
|   |   |--- class: 0
```


**Drzewo decyzyjne (który token: on vs inne tokeny w tej chwili)**, głębokość 3, uczone na 70% czasu (N 3066), test na 30% (N 1326): AUC eksploracja 0.99, **test 0.97**.

```
|--- kupno_sol_10s <= 5.30
|   |--- kupujacy_10s <= 5.50
|   |   |--- netto_sol_10s <= -3.68
|   |   |   |--- class: 0
|   |   |--- netto_sol_10s >  -3.68
|   |   |   |--- class: 0
|   |--- kupujacy_10s >  5.50
|   |   |--- zmiana_10s <= 0.00
|   |   |   |--- class: 1
|   |   |--- zmiana_10s >  0.00
|   |   |   |--- class: 0
|--- kupno_sol_10s >  5.30
|   |--- zmiana_30s <= 0.02
|   |   |--- zmiana_30s <= -0.06
|   |   |   |--- class: 1
|   |   |--- zmiana_30s >  -0.06
|   |   |   |--- class: 1
|   |--- zmiana_30s >  0.02
|   |   |--- kupno_sol_10s <= 10.81
|   |   |   |--- class: 0
|   |   |--- kupno_sol_10s >  10.81
|   |   |   |--- class: 1
```


**Drzewo decyzyjne (kiedy: on vs inne chwile tego tokena)**, głębokość 3, uczone na 70% czasu (N 2673), test na 30% (N 1097): AUC eksploracja 0.98, **test 0.97**.

```
|--- wiek_min <= 0.97
|   |--- sol_1_slot <= 0.99
|   |   |--- class: 1
|   |--- sol_1_slot >  0.99
|   |   |--- tworca_ma_pct <= 17.62
|   |   |   |--- class: 1
|   |   |--- tworca_ma_pct >  17.62
|   |   |   |--- class: 1
|--- wiek_min >  0.97
|   |--- kupno_sol_10s <= 9.14
|   |   |--- portfele_razem <= 13.50
|   |   |   |--- class: 1
|   |   |--- portfele_razem >  13.50
|   |   |   |--- class: 0
|   |--- kupno_sol_10s >  9.14
|   |   |--- portfele_razem <= 217.00
|   |   |   |--- class: 1
|   |   |--- portfele_razem >  217.00
|   |   |   |--- class: 0
```


## 2. Ślad X / social - źródło grafiki tokena (narzędzie, którym go odpalono)

| źródło | jego tokeny (N 732) | inne tokeny w tej chwili (N 3660) | nowe w tym wieku (N 5411) |
|---|---|---|---|
| pump.fun (strona) | 31% | 54% | 74% |
| inne | 25% | 11% | 10% |
| brak | 3% | 24% | 1% |
| Axiom | 24% | 6% | 9% |
| z X (tweet -> coin) | 17% | 5% | 5% |

## 3. Wyjścia - chwila jego sprzedaży vs inne chwile w trakcie trzymania

| cecha | on (mediana) | w trakcie (mediana) | AUC vs w trakcie | AUC 70% / 30% |
|---|---|---|---|---|
| wynik_od_wejscia | 0.0324 | -0.128 | 0.83 | 0.85 / nan |
| od_szczytu_pozycji | -0.0797 | -0.15 | 0.75 | 0.76 / nan |
| trzyma_s | 2 | 68 | 0.00 | 0.00 / nan |
| zmiana_5s | 0.0226 | -0.0256 | 0.64 | 0.65 / nan |
| zmiana_10s | 0.0028 | -0.128 | 0.66 | 0.69 / nan |
| zmiana_30s | -0.0437 | -0.00957 | 0.51 | 0.56 / nan |
| sprzedaze_10s | 18 | 16 | 0.61 | 0.61 / nan |
| kupna_10s | 41.5 | 10 | 0.96 | 0.96 / nan |
| sprzedaz_sol_10s | 19.7 | 10.1 | 0.86 | 0.85 / nan |
| max_sprzedaz_10s | 3.91 | 1.51 | 0.97 | 0.97 / nan |
| netto_sol_10s | 9.56 | -3.69 | 0.88 | 0.88 / nan |
| kol_sprzedaze_60s | 0 | 0 | 0.52 | 0.52 / nan |
| tworca_sprzedal_w_trakcie | 0 | 1 | 0.15 | 0.16 / nan |

**Drzewo decyzyjne (wyjście: jego sprzedaż vs trzymanie)**, głębokość 3, uczone na 70% czasu (N 495), test na 30% (N 204): AUC eksploracja 0.99, **test nan**.

```
|--- max_sprzedaz_10s <= 1.74
|   |--- od_szczytu_pozycji <= -0.04
|   |   |--- class: 0
|   |--- od_szczytu_pozycji >  -0.04
|   |   |--- class: 1
|--- max_sprzedaz_10s >  1.74
|   |--- class: 1
```


**Pierwsza sprzedaż** (N 694): wynik od wejścia (cena) kwartyle -20.0%, -7.0%, +3.2%, +14.2%, +30.9%; czas trzymania kwartyle 2 s, 2 s, 2 s, 2 s, 3 s; sprzedana część mediana 100%.

Rozkład wyniku przy pierwszej sprzedaży (przedziały po 10 pp; skupienie = stały próg TP/SL):

| przedział | N |  |
|---|---|---|
| -50..-40% | 14 | ############## |
| -40..-30% | 23 | ####################### |
| -30..-20% | 33 | ################################# |
| -20..-10% | 72 | ######################################################################## |
| -10..+0% | 147 | ################################################################################################################################################### |
| +0..+10% | 171 | ########################################################################################################################################################################### |
| +10..+20% | 104 | ######################################################################################################## |
| +20..+30% | 55 | ####################################################### |
| +30..+40% | 31 | ############################### |
| +40..+50% | 24 | ######################## |
| +50..+60% | 9 | ######### |
| +60..+70% | 3 | ### |
| +70..+80% | 3 | ### |
| +80..+90% | 1 | # |
| +90..+100% | 1 | # |
| +100..+110% | 3 | ### |

# Czy Bot E odróżnia trash? Jego wybory vs pominięte równie gorące starty - 08.10.2026 19:08

Jego wejść <= 60 s od startu z porównaniem: 641; pominiętych tokenów z top 5 (po kwocie zakupów w 10 s, w tej samej chwili): 2439. Jego token był nr 1 w 66% przypadków. Wynik liczony od ceny w chwili jego wejścia (to ocena WYBORU, nie jego wykonania).

| wynik tokena od chwili T | jego wybór | pominięte z top 5 | AUC (> 0.5 = jego lepsze) | AUC 1. / 2. połowa |
|---|---|---|---|---|
| max wzrost 5 min | +31.3% (śr. +67.0%) | +8.0% (śr. +48.9%) | 0.66 | 0.66 / 0.67 |
| max wzrost 30 min | +33.6% (śr. +77.8%) | +8.7% (śr. +59.7%) | 0.65 | 0.65 / 0.66 |
| cena po 5 min | -35.5% (śr. -7.6%) | -19.5% (śr. -8.5%) | 0.44 | 0.47 / 0.41 |
| cena po 30 min | -43.7% (śr. -13.1%) | -27.8% (śr. -11.0%) | 0.41 | 0.44 / 0.38 |
| migracja w 30 min | 6% | 4% | 0.51 | 0.51 / 0.51 |
| pump (+100% przed -70%) | 23% | 15% | 0.54 | 0.54 / 0.54 |
| rug (-70% przed +100%) | 10% | 12% | 0.49 | 0.47 / 0.51 |

W tej samej chwili jego token miał większy max wzrost w 30 min niż mediana pominiętych w 65% przypadków (50% = rzut monetą; N 641).

## Czy to tylko "bierze nr 1"? Nr 1 gorący start w chwilach, gdy był aktywny, ale nie kupował

|  | N | max 5 min (med.) | max 30 min (med.) | cena po 30 min (med.) | pump | rug | migracja 30 min |
|---|---|---|---|---|---|---|---|
| jego wybory | 641 | +31.3% | +33.6% | -43.7% | 23% | 10% | 6% |
| nr 1 gorący start bez niego | 250 | +7.2% | +7.9% | -33.3% | 14% | 8% | 3% |

## Naśladowcy (portfele, które kupują sekundy po nim i prawie tylko jego tokeny)

Portfeli kupujących <= 5 s po nim w >= 3 jego tokenach: 823; z nich 515 ma jego tokeny >= 20x częściej wśród swoich wczesnych zakupów niż losowo (baza 0.648%). Najbardziej wierni: 66 z 66 wczesnych zakupów to jego tokeny; 4 z 4 wczesnych zakupów to jego tokeny; 5 z 7 wczesnych zakupów to jego tokeny; 4 z 6 wczesnych zakupów to jego tokeny; 5 z 8 wczesnych zakupów to jego tokeny. Po jego zakupie inni kupują w 30 s mediana 17.3 SOL, z czego naśladowcy mediana 24% (średnio 27%). To mogą być boty kopiujące albo jego własne dodatkowe portfele.
