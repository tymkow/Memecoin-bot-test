# Kopiowanie 1:1 tradera Cupsey (2fg5QD...) - 08.10.2026 10:47

Okno naszych danych: 04.10 10:23 - 07.10 19:32 (81 h). Transakcje: historia jego kont tokenów z Heliusa (350 z 400 tokenów z feedu MadeOnSol i naszego strumienia, ~10590 kredytów). Feed MadeOnSol gubi większość sprzedaży (zwykle widzi 1 z kilku), więc wyniki tylko z Heliusa.

## 1. Jego wynik (pozycje zamknięte w oknie)

Pozycji: 327 (zamkniętych 250, otwartych na końcu okna 77). Miejsca handlu: {'pump_curve': 135, 'pumpswap': 72, 'pump_curve+pumpswap': 22, 'meteora_damm2': 9, 'meteora_dbc': 5, 'raydium_launchlab': 3, 'raydium_cpmm': 3, 'meteora_damm2+meteora_dbc': 1}.

|  | N | suma SOL | śr. na pozycję | wygrane | śr. koszt pozycji SOL |
|---|---|---|---|---|---|
| wszystkie zamknięte | 250 | +38.11 | -0.2% (mediana -13.7%, N 250) | 34% | 2.11 |
| pierwsza połowa czasu | 132 | +47.37 | -1.9% (mediana -13.5%, N 132) | 34% | 2.61 |
| druga połowa czasu | 118 | -9.26 | +1.7% (mediana -14.4%, N 118) | 35% | 1.55 |

## 2. Kopia 1:1 z opóźnieniem (pozycje, których wszystkie transakcje da się wycenić)

Wycenialne: 131 z 250 zamkniętych (krzywa pump.fun ze strumienia, PumpSwap z transakcji puli; inne miejsca - LaunchLab, Meteora, ... - bez cen). Wejście/wyjście tą samą kwotą SOL co on, po d sekundach.

| opóźnienie | N | suma SOL | 95% CI śr. SOL/poz. | śr. wynik na pozycję | wygrane | 1. / 2. połowa SOL |
|---|---|---|---|---|---|---|
| 0 s (jego cena) | 131 | +62.56 | -0.188..+1.625 | -2.6% (mediana -6.3%, N 131) | 41% | +61.46 / +1.10 |
| 2 s | 131 | -17.52 | -0.668..+0.758 | -29.5% (mediana -35.6%, N 131) | 14% | +5.95 / -23.47 |
| 5 s | 131 | -22.62 | -0.666..+0.602 | -27.7% (mediana -32.2%, N 131) | 14% | -1.92 / -20.70 |
| 12 s | 131 | -20.42 | -0.613..+0.592 | -26.0% (mediana -26.8%, N 131) | 16% | +2.06 / -22.48 |
| 20 s | 131 | -23.58 | -0.657..+0.585 | -27.7% (mediana -28.6%, N 131) | 14% | -0.03 / -23.55 |

Bez pozycji nachodzących na dziury w strumieniu (79 z 131): 0 s +1.86 SOL, 2 s -37.13 SOL, 5 s -37.05 SOL, 12 s -33.15 SOL, 20 s -32.15 SOL.

**Dlaczego:** zmiana ceny względem stanu tuż przed jego transakcją (mediana; zawiera jego własny wpływ):

|  | po 2 s | po 5 s | po 12 s | po 20 s |
|---|---|---|---|---|
| po jego KUPNIE (N 446) | +6.0% | +4.5% | +5.0% | +3.2% |
| po jego SPRZEDAŻY (N 199) | -11.1% | -11.8% | -8.1% | -13.7% |

Na krzywej w ciągu 2 s po jego kupnie inni robią mediana 3 zakupów (N 301). Ruch ceny w tym czasie to jego własny wpływ + ci, którzy wchodzą razem z nim - kopiujący zawsze kupuje drożej i sprzedaje taniej o ten ruch.

Koszt danych: Helius ~10590 kredytów (konta tokenów) + okna pul PumpSwap (gorące pule: setki-tysiące transakcji na sekundę okna, łącznie ~60 tys. kredytów - szacunek przed pobraniem był ~3 tys.).

## 3. Pokrycie z naszym botem (te same tokeny w oknie)

| grupa | N | jego wynik | wynik bota (śr. portfeli) | uwagi |
|---|---|---|---|---|
| jego pozycje w tokenach, które bot też kupił | 16 | -3.2% (mediana -5.4%, N 16 ⚠️ niewiarygodny) | -15.1% (mediana -29.0%, N 23 ⚠️ niewiarygodny) | wejść bota 23; miejsca: [('pumpswap', 11), ('pump_curve', 4), ('pump_curve+pumpswap', 1)] |
| jego pozycje, których bot nie wziął | 234 | -0.0% (mediana -14.5%, N 234) | - | bot w ogóle oceniał 54 z tych tokenów; miejsca: [('pump_curve', 131), ('pumpswap', 61), ('pump_curve+pumpswap', 21)] |
| wejścia bota w tokeny, których on nie ruszał | 151 | - | -13.7% (mediana -28.2%, N 151) | random_eligible z nich: -7.1% (mediana -27.2%, N 33) |

Wspólne tokeny - jego najbliższe wejście względem naszego (minuty, + = on później): -1471, -1234, -1045, -978, -123, -100, -80, -79, -75, -74, -73, -70, -54, -33, -31, -17, -17, -17, -16, -16, -1, +15, +53
