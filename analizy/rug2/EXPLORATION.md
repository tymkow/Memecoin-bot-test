# Eksploracja rug2 - nowe źródła sygnału (07.10.2026 14:26)

Zbiór: migracje żywe w T = migracja + 30 min, wynik pozycji po kosztach: s0 (wyjście bota) i s6 (S6), etykieta (e)
pomocniczo. Podział czasowy 70/30. Każdy pomysł: lista reguł USTALONA Z GÓRY, najlepsza wybrana na eksploracji (N >= 30),
TEST liczony raz. Porównanie z baseline (wszystkie tokeny okna) i z oczekiwanym random_eligible (tokeny po twardych
filtrach bota w tym samym oknie - common.re_expected). Werdykt "działa" tylko, gdy na TEŚCIE reguła bije random_eligible
o >= 2 pp przy N >= 30, bije baseline, p losowego podzbioru < 0,10 i była lepsza od baseline na eksploracji.


Tokenów: **617** (eksploracja 431, TEST 186). Baseline: eksploracja -15.8%, TEST -15.7%; random_eligible oczekiwany TEST +7.4% (N 23). Wersja LOKALNA - bez nowych pobrań z Heliusa.


## Werdykty

| pomysł | pokrycie | werdykt | szczegóły (reguła z eksploracji -> TEST) |
|---|---|---|---|
| a) historia twórcy | 21% | NIEJASNE | S0: twórca bez historii w danych -> niejasne (vs random_eligible -21.9 pp, p 0.22); S6: poprzedni coin miał >= 10 SOL obrotu -> niejasne (N testu 29 < 30) |
| b) graf zasilania, hop 1 | 25% | NIE DZIAŁA | S0: źródła zasilały wcześniejsze tokeny (>= 1) -> nie działa (na teście nie bije baseline); S6: źródła zasilały wcześniejsze tokeny (>= 1) -> nie działa (na teście nie bije baseline) |
| b) graf zasilania, hop 2 | 6% | NIEJASNE (za małe pokrycie: przodek spoza hubów u 6% kupujących) | S0: źródła zasilały wcześniejsze tokeny (>= 1) -> nie działa (na teście nie bije baseline); S6: wspólny przodek do 2 hopów < 10% -> niejasne (vs random_eligible -14.6 pp, p 0.07) |
| b) graf zasilania, hop 3 | 5% | NIEJASNE (za małe pokrycie: przodek spoza hubów u 5% kupujących) | S0: źródła zasilały wcześniejsze tokeny (>= 1) -> nie działa (na teście nie bije baseline); S6: wspólny przodek do 3 hopów < 10% -> niejasne (vs random_eligible -14.6 pp, p 0.07) |
| c) zaufani twórcy | 0% | NIEJASNE (za małe pokrycie) |  |
| d) ślepy test wizualny | — | NIE DZIAŁA (NIE BIJE RANDOM_ELIGIBLE O >= 2 PP) | Ślepy test: 195 ocen |
| d2) wzorce wizualne (prosta / schodki / zygzak / V) | 10-22% | NIE DZIAŁA (dla bota) | prosta i schodki gorsze w obu połowach, ale filtry bota już je odsiewają; żaden filtr nie bije random_eligible |


### a) Historia twórcy (slop / dev)

Pokrycie: **21%** tokenów ma twórcę z >= 1 wcześniejszym startem w danych (zbieracz od 04.10, PumpPortal bota od 01.10 z nocnymi przerwami); >= 2 startów: 16%. Próg użytkownika: < 20% -> niejasne.

**Pojedyncze cechy:**

| cecha | pokrycie | AUC wynik>0 eksploracja | AUC TEST | Spearman z wynikiem eksploracja | Spearman TEST |
|---|---|---|---|---|---|
| dev_has_hist | 100% | 0.462 | 0.436 | -0.14 | -0.10 |
| dev_prev_n | 100% | 0.462 | 0.428 | -0.14 | -0.12 |
| dev_prev_mig_n | 100% | 0.460 | 0.443 | -0.11 | -0.14 |
| dev_prev_mig_rate | 21% | 0.435 | 0.393 | +0.03 | -0.15 |
| dev_gap_h | 21% | 0.394 | 0.729 | -0.11 | +0.31 |
| dev_prev_maxvol_sol | 21% | 0.532 | 0.365 | +0.18 | +0.04 |
| dev_launches_per_day | 100% | 0.461 | 0.428 | -0.14 | -0.12 |

**Reguły ustalone z góry - eksploracja (wynik obecnego wyjścia, po kosztach):**

| reguła | N wpuszczonych | śr. wpuszczone | śr. reszta |
|---|---|---|---|
| twórca bez historii w danych | 339 | -15.0% | -19.0% |
| twórca z historią (>= 1 start) | 92 | -19.0% | -15.0% |
| twórca, którego coin już zmigrował | 50 | -21.0% | -15.2% |
| bez seryjnych (< 5 startów) | 377 | -16.0% | -14.6% |
| bez szybkiego ponownego startu (odstęp >= 1 h albo brak) | 375 | -15.5% | -18.3% |
| poprzedni coin miał >= 10 SOL obrotu | 70 | -16.1% | -15.8% |

**TEST - tylko reguła najlepsza na eksploracji (obecne wyjście i S6 osobno):**

| reguła (wybrana na eksploracji) | eksploracja: reguła vs baseline | TEST: reguła vs baseline | random_eligible oczekiwany (TEST) | rug (e) reguła / baseline | werdykt |
|---|---|---|---|---|---|
| twórca bez historii w danych (obecne wyjście) | -15.0% vs -15.8% (N 339/431) | -14.5% vs -15.7% (N 148/186; p 0.22) | +7.4% (N 23 ⚠️ niewiarygodny); różnica -21.9 pp | 24% / 24% | niejasne (vs random_eligible -21.9 pp, p 0.22) |
| poprzedni coin miał >= 10 SOL obrotu (S6) | -14.1% vs -15.3% (N 70/431) | -19.9% vs -13.5% (N 29 ⚠️ niewiarygodny/186; p 0.83) | +6.3% (N 23 ⚠️ niewiarygodny); różnica -26.3 pp | 24% / 24% | niejasne (N testu 29 < 30) |

### b) Graf zasilania - hop 1

Łańcuch rozpoznany do hopu 1 (cache, bez nowych pobrań): **100%** pierwszych kupujących, ale przodka SPOZA hubów na hopie 1 ma tylko **25%** (56% pierwszych kupujących to portfele 'aktywne' >= 3000 tx - źródła nie da się ustalić). Huby: 2907.

**Pojedyncze cechy:**

| cecha | pokrycie | AUC wynik>0 eksploracja | AUC TEST | Spearman z wynikiem eksploracja | Spearman TEST |
|---|---|---|---|---|---|
| f1_shared | 99% | 0.636 | 0.581 | +0.09 | +0.01 |
| f1_creator_link | 99% | 0.612 | 0.588 | +0.09 | +0.02 |
| f1_src_prev_n | 100% | 0.496 | 0.403 | -0.01 | -0.14 |
| f1_src_prev_s0 | 21% | 0.607 | 0.510 | +0.05 | +0.00 |

**Reguły ustalone z góry - eksploracja (wynik obecnego wyjścia, po kosztach):**

| reguła | N wpuszczonych | śr. wpuszczone | śr. reszta |
|---|---|---|---|
| wspólny przodek do 1 hopów >= 10% kupujących | 230 | -17.7% | -13.7% |
| wspólny przodek do 1 hopów >= 25% | 166 | -18.4% | -14.2% |
| wspólny przodek do 1 hopów < 10% | 201 | -13.7% | -17.7% |
| powiązanie z twórcą do 1 hopów (> 0) | 384 | -16.0% | -14.6% |
| źródła zasilały wcześniejsze tokeny (>= 1) | 71 | -10.6% | -16.9% |
| wcześniejsze tokeny tych źródeł miały wynik > 0 | 10 ⚠️ niewiarygodny | -12.4% | -15.9% |

**TEST - tylko reguła najlepsza na eksploracji (obecne wyjście i S6 osobno):**

| reguła (wybrana na eksploracji) | eksploracja: reguła vs baseline | TEST: reguła vs baseline | random_eligible oczekiwany (TEST) | rug (e) reguła / baseline | werdykt |
|---|---|---|---|---|---|
| źródła zasilały wcześniejsze tokeny (>= 1) (obecne wyjście) | -10.6% vs -15.8% (N 71/431) | -21.3% vs -15.7% (N 57/186; p 0.87) | +7.4% (N 23 ⚠️ niewiarygodny); różnica -28.8 pp | 30% / 24% | nie działa (na teście nie bije baseline) |
| źródła zasilały wcześniejsze tokeny (>= 1) (S6) | -11.1% vs -15.3% (N 71/431) | -14.3% vs -13.5% (N 57/186; p 0.57) | +6.3% (N 23 ⚠️ niewiarygodny); różnica -20.6 pp | 30% / 24% | nie działa (na teście nie bije baseline) |

### b) Graf zasilania - hop 2

Łańcuch rozpoznany do hopu 2 (cache, bez nowych pobrań): **74%** pierwszych kupujących, ale przodka SPOZA hubów na hopie 2 ma tylko **6%** (56% pierwszych kupujących to portfele 'aktywne' >= 3000 tx - źródła nie da się ustalić). Huby: 2907. Hop 2 dodał nowe powiązania w 5 z 617 tokenów.

**Pojedyncze cechy:**

| cecha | pokrycie | AUC wynik>0 eksploracja | AUC TEST | Spearman z wynikiem eksploracja | Spearman TEST |
|---|---|---|---|---|---|
| f2_shared | 99% | 0.634 | 0.581 | +0.09 | +0.01 |
| f2_creator_link | 99% | 0.612 | 0.588 | +0.09 | +0.02 |
| f2_src_prev_n | 100% | 0.488 | 0.399 | -0.02 | -0.14 |
| f2_src_prev_s0 | 23% | 0.573 | 0.474 | -0.06 | -0.03 |

**Reguły ustalone z góry - eksploracja (wynik obecnego wyjścia, po kosztach):**

| reguła | N wpuszczonych | śr. wpuszczone | śr. reszta |
|---|---|---|---|
| wspólny przodek do 2 hopów >= 10% kupujących | 232 | -17.8% | -13.5% |
| wspólny przodek do 2 hopów >= 25% | 166 | -18.4% | -14.2% |
| wspólny przodek do 2 hopów < 10% | 199 | -13.5% | -17.8% |
| powiązanie z twórcą do 2 hopów (> 0) | 385 | -16.0% | -14.6% |
| źródła zasilały wcześniejsze tokeny (>= 1) | 82 | -11.7% | -16.8% |
| wcześniejsze tokeny tych źródeł miały wynik > 0 | 19 ⚠️ niewiarygodny | -15.6% | -15.8% |

**TEST - tylko reguła najlepsza na eksploracji (obecne wyjście i S6 osobno):**

| reguła (wybrana na eksploracji) | eksploracja: reguła vs baseline | TEST: reguła vs baseline | random_eligible oczekiwany (TEST) | rug (e) reguła / baseline | werdykt |
|---|---|---|---|---|---|
| źródła zasilały wcześniejsze tokeny (>= 1) (obecne wyjście) | -11.7% vs -15.8% (N 82/431) | -21.5% vs -15.7% (N 58/186; p 0.88) | +7.4% (N 23 ⚠️ niewiarygodny); różnica -28.9 pp | 31% / 24% | nie działa (na teście nie bije baseline) |
| wspólny przodek do 2 hopów < 10% (S6) | -11.2% vs -15.3% (N 199/431) | -8.3% vs -13.5% (N 80/186; p 0.07) | +6.3% (N 23 ⚠️ niewiarygodny); różnica -14.6 pp | 21% / 24% | niejasne (vs random_eligible -14.6 pp, p 0.07) |

### b) Graf zasilania - hop 3

Łańcuch rozpoznany do hopu 3 (cache, bez nowych pobrań): **72%** pierwszych kupujących, ale przodka SPOZA hubów na hopie 3 ma tylko **5%** (56% pierwszych kupujących to portfele 'aktywne' >= 3000 tx - źródła nie da się ustalić). Huby: 2907. Hop 3 dodał nowe powiązania w 0 z 617 tokenów.

**Pojedyncze cechy:**

| cecha | pokrycie | AUC wynik>0 eksploracja | AUC TEST | Spearman z wynikiem eksploracja | Spearman TEST |
|---|---|---|---|---|---|
| f3_shared | 99% | 0.634 | 0.581 | +0.09 | +0.01 |
| f3_creator_link | 99% | 0.612 | 0.588 | +0.09 | +0.02 |
| f3_src_prev_n | 100% | 0.486 | 0.399 | -0.03 | -0.14 |
| f3_src_prev_s0 | 23% | 0.574 | 0.474 | -0.01 | -0.03 |

**Reguły ustalone z góry - eksploracja (wynik obecnego wyjścia, po kosztach):**

| reguła | N wpuszczonych | śr. wpuszczone | śr. reszta |
|---|---|---|---|
| wspólny przodek do 3 hopów >= 10% kupujących | 232 | -17.8% | -13.5% |
| wspólny przodek do 3 hopów >= 25% | 166 | -18.4% | -14.2% |
| wspólny przodek do 3 hopów < 10% | 199 | -13.5% | -17.8% |
| powiązanie z twórcą do 3 hopów (> 0) | 385 | -16.0% | -14.6% |
| źródła zasilały wcześniejsze tokeny (>= 1) | 84 | -12.6% | -16.6% |
| wcześniejsze tokeny tych źródeł miały wynik > 0 | 20 ⚠️ niewiarygodny | -15.0% | -15.9% |

**TEST - tylko reguła najlepsza na eksploracji (obecne wyjście i S6 osobno):**

| reguła (wybrana na eksploracji) | eksploracja: reguła vs baseline | TEST: reguła vs baseline | random_eligible oczekiwany (TEST) | rug (e) reguła / baseline | werdykt |
|---|---|---|---|---|---|
| źródła zasilały wcześniejsze tokeny (>= 1) (obecne wyjście) | -12.6% vs -15.8% (N 84/431) | -21.5% vs -15.7% (N 58/186; p 0.88) | +7.4% (N 23 ⚠️ niewiarygodny); różnica -28.9 pp | 31% / 24% | nie działa (na teście nie bije baseline) |
| wspólny przodek do 3 hopów < 10% (S6) | -11.2% vs -15.3% (N 199/431) | -8.3% vs -13.5% (N 80/186; p 0.07) | +6.3% (N 23 ⚠️ niewiarygodny); różnica -14.6 pp | 21% / 24% | niejasne (vs random_eligible -14.6 pp, p 0.07) |

### c) Zaufani twórcy

Propozycje do analizy/rug2/trusted_devs.yaml (>= 2 tokeny w danych z wynikiem > 0): **1** twórców. Pokrycie cechy point-in-time (>= 2 sprawdzone tokeny przed T): 0.0% tokenów; >= 1: 0.3%. Lista ręczna jest pusta, dopóki jej nie uzupełnisz (propozycje używają wyników z przyszłości - tylko do ręcznej oceny, nie jako cecha).

**Pojedyncze cechy:**

| cecha | pokrycie | AUC wynik>0 eksploracja | AUC TEST | Spearman z wynikiem eksploracja | Spearman TEST |
|---|---|---|---|---|---|
| dev_proven_n | 100% | 0.505 | 0.496 | +0.08 | -0.04 |
| dev_prev_eval_n | 100% | 0.505 | 0.496 | +0.01 | -0.04 |
| dev_trusted | 100% | 0.500 | 0.500 | +nan | +nan |

**Reguły ustalone z góry - eksploracja (wynik obecnego wyjścia, po kosztach):**

| reguła | N wpuszczonych | śr. wpuszczone | śr. reszta |
|---|---|---|---|
| twórca sprawdzony w T (>= 2 wcześniejsze tokeny z wynikiem > 0) | 0 ⚠️ niewiarygodny | — | -15.8% |
| twórca z >= 1 wcześniejszym tokenem z wynikiem > 0 | 1 ⚠️ niewiarygodny | +62.7% | -16.0% |
| twórca z trusted_devs.yaml | 0 ⚠️ niewiarygodny | — | -15.8% |

**TEST - tylko reguła najlepsza na eksploracji (obecne wyjście i S6 osobno):**

brak reguły z N >= 30 na eksploracji

### d) Ślepy test wizualny

Strona `python -m analizy.rug2.blind.server` (wykres od startu do T, bez nazwy i dalszego przebiegu), odpowiedzi w analizy/rug2/blind/oceny.csv.

**Ślepy test: 195 ocen.** Wyniki pozycji po kosztach (obecne wyjście / S6), etykiety pomocniczo.

| grupa | N | wynik (obecne wyjście) | S6 | rug (e) | pump |
|---|---|---|---|---|---|
| kupić (wszystkie) | 35 | -14.0% (CI -24.1..-3.3%) | -12.2% | 34% | 40% |
|   kupić - pewny | 5 ⚠️ niewiarygodny | -18.3% (CI -29.1..+3.2%) | -20.2% | 20% | 40% |
|   kupić - niepewny | 11 ⚠️ niewiarygodny | -11.1% (CI -29.1..+7.8%) | -11.8% | 18% | 45% |
|   kupić - pewność nieznana (pierwsze 120) | 19 ⚠️ niewiarygodny | -14.6% (CI -28.3..+0.2%) | -10.3% | 47% | 37% |
| nie kupić | 160 | -14.9% (CI -21.3..-8.6%) | -15.5% | 18% | 26% |
| cała pula | 617 | -15.8% | -14.8% | 23% | 28% |
| random_eligible (pula) | 74 | -5.0% | -4.0% | 35% | 54% |

'kupić' - random_eligible: CI -22.1..+4.6 pp. AUC 'kupić' jako wskaźnik ruga: 0.576 (> 0,5 = wybierane wykresy częściej rugują).

**Werdykt d): nie działa (nie bije random_eligible o >= 2 pp).**


### d2) Wzorce wykresu użytkownika (prosta / schodki / zygzak / V) - na wyniku po kosztach

Progi USTALONE Z OPISU, przed spojrzeniem na wyniki:
  prosta    log ceny ~ czas w oknie [migracja, T]: R^2 >= 0,85 i nachylenie > 0 ("prosta linia do góry")
  schodki   >= 4 minuty z +3% lub więcej, wielkość tych wzrostów podobna (CV < 0,5), żaden zjazd minutowy < -5%
  zygzak    wśród ruchów minutowych |r| > 1%: >= 60% zmian kierunku
  V         od szczytu spadek >= 40%, potem w T cena >= 1,5 x dołek ("mocno spadło, potem pompa = kolejny dump")
Każdy wzorzec jako filtr "NIE kupuj, gdy wzorzec" (hipoteza: to rugi) i odwrotnie; eksploracja 70% / TEST 30%.



| wzorzec | zbiór | N z wzorcem (udział) | wynik z wzorcem | wynik bez wzorca | S6 z wzorcem | rug (e) z / bez |
|---|---|---|---|---|---|---|
| prosta linia do góry | eksploracja | 75 (17%) | -33.4% | -12.1% | -31.5% | 40% / 20% |
| prosta linia do góry | TEST | 40 (22%) | -16.8% | -15.5% | -18.2% | 22% / 24% |
| prosta linia do góry | Twoje oceny | 36 | 'nie kupić' 100% |  |  |  |
| schodki | eksploracja | 45 (10%) | -40.2% | -13.0% | -40.6% | 40% / 21% |
| schodki | TEST | 30 (16%) | -25.1% | -13.9% | -25.9% | 27% / 23% |
| schodki | Twoje oceny | 18 | 'nie kupić' 100% |  |  |  |
| zygzak | eksploracja | 52 (12%) | -11.9% | -16.4% | -12.4% | 25% / 23% |
| zygzak | TEST | 19 ⚠️ niewiarygodny (10%) | +0.3% | -17.6% | +6.4% | 32% / 23% |
| zygzak | Twoje oceny | 21 | 'nie kupić' 81% |  |  |  |
| spadek, potem pompa (V) | eksploracja | 52 (12%) | -17.6% | -15.6% | -14.6% | 42% / 21% |
| spadek, potem pompa (V) | TEST | 24 ⚠️ niewiarygodny (13%) | -26.9% | -14.1% | -19.6% | 33% / 22% |
| spadek, potem pompa (V) | Twoje oceny | 24 | 'nie kupić' 50% |  |  |  |

**Filtry "nie kupuj, gdy wzorzec" (vs baseline i oczekiwany random_eligible na TEŚCIE):**

| filtr / hipoteza | eksploracja: filtr vs baseline (N) | TEST: filtr vs baseline (N; p losowe) | random_eligible oczekiwany, TEST (N) | werdykt |
|---|---|---|---|---|
| wzorzec prosta: nie kupuj (S0) | -12.1% vs -15.8% (N 356/431) | -15.5% vs -15.7% (N 146/186; p 0.43) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec prosta: kupuj TYLKO z nim (S0) | -33.4% vs -15.8% (N 75/431) | -16.8% vs -15.7% (N 40/186; p 0.56) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec prosta: nie kupuj (S6) | -11.9% vs -15.3% (N 356/431) | -12.2% vs -13.5% (N 146/186; p 0.19) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec prosta: kupuj TYLKO z nim (S6) | -31.5% vs -15.3% (N 75/431) | -18.2% vs -13.5% (N 40/186; p 0.80) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec schodki: nie kupuj (S0) | -13.0% vs -15.8% (N 386/431) | -13.9% vs -15.7% (N 156/186; p 0.11) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec schodki: kupuj TYLKO z nim (S0) | -40.2% vs -15.8% (N 45/431) | -25.1% vs -15.7% (N 30/186; p 0.89) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec schodki: nie kupuj (S6) | -12.4% vs -15.3% (N 386/431) | -11.1% vs -13.5% (N 156/186; p 0.03) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec schodki: kupuj TYLKO z nim (S6) | -40.6% vs -15.3% (N 45/431) | -25.9% vs -13.5% (N 30/186; p 0.96) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec zygzak: nie kupuj (S0) | -16.4% vs -15.8% (N 379/431) | -17.6% vs -15.7% (N 167/186; p 0.95) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec zygzak: kupuj TYLKO z nim (S0) | -11.9% vs -15.8% (N 52/431) | +0.3% vs -15.7% (N 19 ⚠️ niewiarygodny/186; p 0.05) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec zygzak: nie kupuj (S6) | -15.7% vs -15.3% (N 379/431) | -15.8% vs -13.5% (N 167/186; p 0.99) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec zygzak: kupuj TYLKO z nim (S6) | -12.4% vs -15.3% (N 52/431) | +6.4% vs -13.5% (N 19 ⚠️ niewiarygodny/186; p 0.01) | +6.3% (N 23 ⚠️ niewiarygodny) | kierunek OK, niepewne (N 19, p 0.01) |
| wzorzec V: nie kupuj (S0) | -15.6% vs -15.8% (N 379/431) | -14.1% vs -15.7% (N 162/186; p 0.09) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| wzorzec V: kupuj TYLKO z nim (S0) | -17.6% vs -15.8% (N 52/431) | -26.9% vs -15.7% (N 24 ⚠️ niewiarygodny/186; p 0.90) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec V: nie kupuj (S6) | -15.4% vs -15.3% (N 379/431) | -12.6% vs -13.5% (N 162/186; p 0.21) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| wzorzec V: kupuj TYLKO z nim (S6) | -14.6% vs -15.3% (N 52/431) | -19.6% vs -13.5% (N 24 ⚠️ niewiarygodny/186; p 0.78) | +6.3% (N 23 ⚠️ niewiarygodny) | NIE trzyma się na teście |

Wniosek: 'prosta' i 'schodki' są gorsze w obu połowach (rug 40% vs 20%), ale twarde filtry bota już ich nie przepuszczają (wśród tokenów po filtrach: 2/51 na eksploracji, 0/23 na teście) - dla bota bez wartości dodanej. 'Zygzak' wychodzi odwrotnie niż intuicja (lepszy), 'V' słabo i niestabilnie.
