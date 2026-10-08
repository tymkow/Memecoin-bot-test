# Raport analiz - Memecoin Bot (07.10.2026 12:19)

Zasady: podział czasowy 70% eksploracja / 30% TEST (wnioski tylko, gdy trzymają się na teście); N przy każdym
wyniku, N < 30 = "niewiarygodny"; zawsze porównanie z baseline = obecne reguły bota; logika bota nietknięta.
**Od 6.10 wieczorem także porównanie z random_eligible** (jedyna strategia dodatnia brutto): filtr, który go nie bije,
nie ma wartości. random_eligible = losowe 25% tokenów, które przeszły twarde filtry bota, więc jego OCZEKIWANY wynik na
danym zbiorze to średnia po tokenach tego zbioru z sygnałem safety_only (przeszły filtry), w tym samym oknie TESTU i tą
samą symulacją (porównanie 1:1). Faktyczne pozycje random_eligible są za nieliczne na okna testów (58 w 5 dni; w oknie
testu migracji 3) - ich wynik jest w notce pod tabelą zbiorczą. W zbiorze wejść bota każde wejście przeszło filtry, więc
tam oczekiwany random_eligible = baseline.
Wyniki wejść w stawkach (1 = cała stawka), po kosztach (wejście 1.5%, wyjście 4%, krach w świecy -> low).
Etykieta tokena (potrójna bariera od ceny wejścia, 6 h): -70% najpierw = rug, +50% najpierw = pump, żadne = nic.

**Poprawka 6.10 wieczorem - rozbieżność baseline (część 3: -8,0% TEST vs część 4: -12,2% TEST):** to samo wyjście
(SL -25%, TP 50/100/300 po 1/3, trailing 20%, time stop 4 h) i te same koszty (wejście 1,5%, wyjście 4%); oba symulatory
dają ten sam wynik na tych samych wejściach (różnica <= 0,4 pp na wejściu: część 4 brała TP po dokładnie 1/3, bot ma
0,33). Różnica wynikała z ZESTAWU wejść: część 3 brała tylko wejścia z >= 5 migawkami płynności (233 z 260) - 27
wykluczonych to szybko umierające tokeny (-32% na wejście, 78% rugów), więc jej baseline był zawyżony (przeżycie).
Teraz części 3, 4, 6 i 7 liczą na TYM SAMYM zestawie (`common.bot_entry_set`); w części 3 wejście bez danych
o płynności = brak poszerzenia stopa.


## Tabela zbiorcza: hipoteza -> eksploracja (train) -> TEST -> N -> vs random_eligible -> werdykt

Werdykt POTWIERDZONE = na teście lepsze od baseline, lepsze od oczekiwanego random_eligible (tokeny po filtrach bota z tego samego zbioru i okna), p losowego podzbioru < 0,10 i N >= 30 (filtry) albo CI różnicy w parach > 0 (warianty wyjścia). "p losowe" = szansa, że LOSOWY wybór tylu samych tokenów z testu da średnią co najmniej taką jak filtr.

| filtr / hipoteza | eksploracja: filtr vs baseline (N) | TEST: filtr vs baseline (N; p losowe) | random_eligible oczekiwany, TEST (N) | werdykt |
|---|---|---|---|---|
| luka przy krachu (część 0): szybki stop z odczytu puli co 2 s, transakcja po 1.5 s, dołożony do bota | +2.3 pp na pozycję (N 784) | +1.7 pp na pozycję (N 337) | na pozycjach random_eligible +1.6 pp (N 41) | symulacja: poprawa w obu połowach |
| luka przy krachu (część 0): szybki stop z odczytu puli co 5 s, transakcja po 1.5 s, dołożony do bota | +1.8 pp na pozycję (N 784) | +1.3 pp na pozycję (N 337) | na pozycjach random_eligible +1.1 pp (N 41) | symulacja: poprawa w obu połowach |
| luka przy krachu (część 0): szybki stop z odczytu puli co 10 s, transakcja po 1.5 s, dołożony do bota | +1.4 pp na pozycję (N 784) | +0.9 pp na pozycję (N 337) | na pozycjach random_eligible +1.0 pp (N 41) | symulacja: poprawa w obu połowach |
| pierwsi kupujący (część 1): wchodź, gdy snajperów >= 50% | -12.2% vs -15.9% (N 175/425) | -15.1% vs -15.9% (N 61/183; p 0.43) | +5.9% (N 24 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| scoring P(rug) z części 1c: wchodź, gdy score < mediana eksploracji | -13.5% vs -15.9% (N 116/425) | -10.7% vs -15.9% (N 48/183; p 0.18) | +5.9% (N 24 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| S6 zamiast obecnego wyjścia (część 4) - wejścia bota | -9.7% vs -10.7% (N 205) | -5.0% vs -6.1% (N 89; CI różnicy -2.6..+5.2 pp) | -6.1% (N 89) | kierunek OK, CI obejmuje 0 |
| S6 zamiast obecnego wyjścia (część 4) - migracje + 30 min | -15.3% vs -15.8% (N 431) | -13.5% vs -15.7% (N 186; CI różnicy -0.0..+4.5 pp) | +7.4% (N 23 ⚠️ niewiarygodny) | kierunek OK, CI obejmuje 0 |
| bundle (a) hipoteza: 20-30% opłacalne (obecne wyjście) | -15.1% vs -15.5% (N 41/361) | -6.9% vs -12.7% (N 16 ⚠️ niewiarygodny/156; p 0.27) | +9.2% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| bundle (a) hipoteza: unikaj >= 35% (obecne wyjście) | -16.8% vs -15.5% (N 255/361) | -15.5% vs -12.7% (N 129/156; p 0.95) | +9.2% (N 20 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| bundle (a) najlepszy przedział z eksploracji 30%+ (obecne wyjście) | -12.1% vs -15.5% (N 125/361) | -1.2% vs -12.7% (N 35/156; p 0.03) | +9.2% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| bundle (a) hipoteza: 20-30% opłacalne (S6) | -12.2% vs -14.6% (N 41/361) | -5.7% vs -10.8% (N 16 ⚠️ niewiarygodny/156; p 0.27) | +8.3% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| bundle (a) hipoteza: unikaj >= 35% (S6) | -15.8% vs -14.6% (N 255/361) | -13.3% vs -10.8% (N 129/156; p 0.95) | +8.3% (N 20 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| bundle (a) najlepszy przedział z eksploracji 30%+ (S6) | -11.8% vs -14.6% (N 125/361) | -0.4% vs -10.8% (N 35/156; p 0.03) | +8.3% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| bundle (b) hipoteza: 20-30% opłacalne (obecne wyjście) | — vs -16.6% (N 0/275) | +90.9% vs -13.0% (N 1 ⚠️ niewiarygodny/119; p 0.04) | +15.8% (N 10 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| bundle (b) hipoteza: unikaj >= 35% (obecne wyjście) | -16.5% vs -16.6% (N 274/275) | -13.4% vs -13.0% (N 118/119; p 0.90) | +15.8% (N 10 ⚠️ niewiarygodny) | NIE trzyma się na teście |
| bundle (b) najlepszy przedział z eksploracji 0-20% (obecne wyjście) | -16.5% vs -16.6% (N 274/275) | -14.3% vs -13.0% (N 117/119; p 0.97) | +15.8% (N 10 ⚠️ niewiarygodny) | NIE trzyma się na teście |
| bundle (b) hipoteza: 20-30% opłacalne (S6) | — vs -15.9% (N 0/275) | +81.6% vs -11.3% (N 1 ⚠️ niewiarygodny/119; p 0.04) | +13.2% (N 10 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| bundle (b) hipoteza: unikaj >= 35% (S6) | -15.9% vs -15.9% (N 274/275) | -11.4% vs -11.3% (N 118/119; p 0.66) | +13.2% (N 10 ⚠️ niewiarygodny) | NIE trzyma się na teście |
| bundle (b) najlepszy przedział z eksploracji 0-20% (S6) | -15.9% vs -15.9% (N 274/275) | -12.2% vs -11.3% (N 117/119; p 0.95) | +13.2% (N 10 ⚠️ niewiarygodny) | NIE trzyma się na teście |
| copy: nie kupuj kopii AKTYWNEGO (a) (obecne wyjście) | -13.7% vs -15.8% (N 199/431) | -8.7% vs -15.7% (N 86/186; p 0.02) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj kopii MARTWEGO (b) (obecne wyjście) | -16.5% vs -15.8% (N 316/431) | -18.5% vs -15.7% (N 130/186; p 0.90) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| copy: tylko oryginały (c) (obecne wyjście) | -13.2% vs -15.8% (N 84/431) | -7.4% vs -15.7% (N 30/186; p 0.13) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj tej samej grafiki (obecne wyjście) | -13.6% vs -15.8% (N 273/431) | -8.5% vs -15.7% (N 101/186; p 0.01) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj kopii AKTYWNEGO (a) (S6) | -13.4% vs -15.3% (N 199/431) | -7.3% vs -13.5% (N 86/186; p 0.02) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj kopii MARTWEGO (b) (S6) | -15.9% vs -15.3% (N 316/431) | -15.5% vs -13.5% (N 130/186; p 0.85) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| copy: tylko oryginały (c) (S6) | -13.0% vs -15.3% (N 84/431) | -4.3% vs -13.5% (N 30/186; p 0.08) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj tej samej grafiki (S6) | -13.1% vs -15.3% (N 273/431) | -7.8% vs -13.5% (N 101/186; p 0.02) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| model wyniku (logistyczna): score >= mediana eksploracji (obecne wyjście) | -16.2% vs -15.5% (N 179/357) | -15.9% vs -12.6% (N 103/154; p 0.90) | +9.2% (N 20 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| model wyniku (logistyczna): score >= mediana eksploracji (S6) | -16.9% vs -14.6% (N 179/357) | -15.3% vs -10.9% (N 103/154; p 0.97) | +8.3% (N 20 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| model wyniku (liniowa): score >= mediana eksploracji (obecne wyjście) | -11.2% vs -15.5% (N 179/357) | -9.9% vs -12.6% (N 67/154; p 0.26) | +9.2% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| model wyniku (liniowa): score >= mediana eksploracji (S6) | -10.8% vs -14.6% (N 179/357) | -6.9% vs -10.9% (N 67/154; p 0.14) | +8.3% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |

**Czym jest random_eligible:** losowe ~25% tokenów (hash mintu), które przeszły TE SAME twarde filtry co safety_only - ten sam rynek, losowy podzbiór. Jego oczekiwany wynik = wynik safety_only; różnica to przede wszystkim losowość małej próby:

| strategia | pozycji | netto na pozycję | 95% CI netto | brutto na pozycję |
|---|---|---|---|---|
| random_eligible | 62 | -2.6% | -14.7..+10.4% | +1.6% |
| safety_only | 219 | -11.9% | -17.5..-6.1% | -7.5% |


## 0. Luka przy krachu - szybszy odczyt ceny puli


**Jak paper trading liczy dziś cenę sprzedaży przy krachu** (bot.py `manage_positions`, paper.py `sell`):

| krok | jak jest | skutek przy krachu |
|---|---|---|
| pętla pozycji | co 10 s, ale w jednym wątku ze skanem nowych tokenów (co 45 s) - migawki pozycji (zapis co >= 60 s) mają medianę 68,5 s, czyli pętla średnio co ~20 s | spadek między obiegami widać dopiero w następnym obiegu |
| cena do stopów | kwotowanie Jupitera sprzedaży całej pozycji co 20 s ("cena wykonalna", ważna 50 s); bez niego cena z DexScreenera | DexScreener spóźnia się o dziesiątki sekund; kwotowanie co 20 s |
| exit_gap | kwotowanie < 50% wartości z ceny DexScreenera -> natychmiastowe wyjście | to są krachy głębsze niż 50% między dwoma kwotowaniami |
| cena sprzedaży | NOWE kwotowanie Jupitera (lub z próby <= 5 s) x 0,99 - $0,05 | fill = kwotowanie z chwili decyzji, bez wysyłania transakcji |

**Czy realna egzekucja byłaby gorsza? Tak.** Od kwotowania do wylądowania transakcji mija ~1-3 s (podpis, wysłanie,
blok), w krachu cena w tym czasie dalej spada; transakcja z limitem poślizgu może się nie wykonać (ponowienie = kolejne
sekundy); Jupiter kwotuje ze stanu puli sprzed chwili. Ile to kosztuje - wiersze "realna egzekucja" niżej (zmierzone
na transakcjach puli w sekundach po kwotowaniu paper).

Pozycje bota (bez odtworzeń przerwy): 1574; z odtworzoną ceną puli: **1121** (ok 1121, pula nie-PumpSwap / brak transakcji 421, bez świec 31, bez puli 1); w tym wyjścia krachowe (stop_loss / exit_gap / liq_drain): 882.

**Obecny mechanizm w liczbach (wyjścia krachowe):**

| miara | N | wartość |
|---|---|---|
| kalibracja: kwotowanie paper / wartość z puli w tej sekundzie (mediana, p25-p75) | 882 | 0.991 (0.988-0.994) |
| opóźnienie: od przebicia stopa w transakcjach puli do sprzedaży paper (mediana, p75, p90) | 810 | 12 s, 19 s, 23 s |
| cena sprzedaży paper względem poziomu stopa (średnio, mediana) | 882 | -17.0%, -7.6% |
| realna egzekucja: zmiana wartości sprzedaży 1 s po kwotowaniu (średnio, mediana) | 882 | -0.1%, +0.0% |
| realna egzekucja: zmiana wartości sprzedaży 2 s po kwotowaniu (średnio, mediana) | 882 | -0.2%, +0.0% |
| realna egzekucja: zmiana wartości sprzedaży 3 s po kwotowaniu (średnio, mediana) | 882 | -0.4%, +0.0% |

Jak to czytać: kwotowanie paper zgadza się ze stanem puli w tej samej sekundzie (kalibracja ~0,99 = prowizje), więc paper NIE zawyża ceny sprzedaży. "Luka przy krachu" z części 7 (4,6 pp na pozycję) jest liczona względem ceny z DexScreenera, która w krachu jest nieaktualna - to głównie spadek, który wydarzył się PRZED wykryciem (stop przebity średnio kilkanaście sekund wcześniej), a nie koszt samej sprzedaży. Realna transakcja byłaby gorsza tylko o dalszy spadek w 1-3 s po kwotowaniu (wiersze wyżej) plus ryzyko nieudanej transakcji przy limicie poślizgu (nie do zmierzenia na danych). Odzyskać da się tylko część przez szybsze wykrycie - symulacja niżej.


**Symulacja: szybki stop z odczytu puli dołożony do bota** (wszystkie 1121 pozycje z ceną puli; eksploracja 784, TEST 337; wynik w pp stawki na pozycję i w $ łącznie)

| odczyt puli | lądowanie tx | zbiór | N pozycji | zmiana na wyjściach krachowych (na pozycję) | nowe fałszywe stopy (pozycje bez krachu) | zmiana na pozycję (wszystkie) | $ łącznie |
|---|---|---|---|---|---|---|---|
| co 2 s | 0.5 s | wszystkie | 1121 | +3.9 pp (N 882) | 25 poz., śr. -34 pp, -419 $ | **+2.3 pp** | +1,277 |
| co 2 s | 1.5 s | wszystkie | 1121 | +3.6 pp (N 882) | 25 poz., śr. -33 pp, -409 $ | **+2.1 pp** | +1,180 |
| co 2 s | 1.5 s | eksploracja | 784 | +4.0 pp (N 615) | 21 poz., śr. -33 pp, -341 $ | **+2.3 pp** | +896 |
| co 2 s | 1.5 s | TEST | 337 | +2.6 pp (N 267) | 4 poz., śr. -34 pp, -68 $ | **+1.7 pp** | +284 |
| co 2 s | 3.0 s | wszystkie | 1121 | +3.2 pp (N 882) | 25 poz., śr. -31 pp, -386 $ | **+1.8 pp** | +1,015 |
| co 5 s | 0.5 s | wszystkie | 1121 | +3.0 pp (N 882) | 25 poz., śr. -24 pp, -301 $ | **+1.8 pp** | +1,000 |
| co 5 s | 1.5 s | wszystkie | 1121 | +2.7 pp (N 882) | 25 poz., śr. -24 pp, -294 $ | **+1.6 pp** | +916 |
| co 5 s | 1.5 s | eksploracja | 784 | +3.1 pp (N 615) | 21 poz., śr. -25 pp, -259 $ | **+1.8 pp** | +691 |
| co 5 s | 1.5 s | TEST | 337 | +2.0 pp (N 267) | 4 poz., śr. -18 pp, -35 $ | **+1.3 pp** | +225 |
| co 5 s | 3.0 s | wszystkie | 1121 | +2.5 pp (N 882) | 25 poz., śr. -23 pp, -287 $ | **+1.4 pp** | +799 |
| co 10 s | 1.5 s | wszystkie | 1121 | +2.1 pp (N 882) | 25 poz., śr. -19 pp, -241 $ | **+1.2 pp** | +682 |
| co 10 s | 1.5 s | eksploracja | 784 | +2.5 pp (N 615) | 21 poz., śr. -21 pp, -216 $ | **+1.4 pp** | +538 |
| co 10 s | 1.5 s | TEST | 337 | +1.3 pp (N 267) | 4 poz., śr. -12 pp, -24 $ | **+0.9 pp** | +144 |
| co 20 s | 1.5 s | wszystkie | 1121 | +1.3 pp (N 882) | 22 poz., śr. -16 pp, -171 $ | **+0.7 pp** | +397 |
| co 20 s | 1.5 s | eksploracja | 784 | +1.5 pp (N 615) | 20 poz., śr. -16 pp, -156 $ | **+0.8 pp** | +307 |
| co 20 s | 1.5 s | TEST | 337 | +0.8 pp (N 267) | 2 poz., śr. -15 pp, -15 $ | **+0.5 pp** | +90 |
| co 2 s, 2 odczyty z rzędu | 1.5 s | wszystkie | 1121 | +2.4 pp (N 882) | 13 poz., śr. -36 pp, -236 $ | **+1.4 pp** | +803 |
| co 2 s, 2 odczyty z rzędu | 1.5 s | eksploracja | 784 | +2.6 pp (N 615) | 12 poz., śr. -37 pp, -222 $ | **+1.5 pp** | +574 |
| co 2 s, 2 odczyty z rzędu | 1.5 s | TEST | 337 | +1.8 pp (N 267) | 1 poz., śr. -27 pp, -13 $ | **+1.4 pp** | +229 |
| co 5 s, 2 odczyty z rzędu | 1.5 s | wszystkie | 1121 | +1.4 pp (N 882) | 7 poz., śr. -53 pp, -184 $ | **+0.7 pp** | +413 |
| co 5 s, 2 odczyty z rzędu | 1.5 s | eksploracja | 784 | +1.7 pp (N 615) | 6 poz., śr. -57 pp, -171 $ | **+0.9 pp** | +346 |
| co 5 s, 2 odczyty z rzędu | 1.5 s | TEST | 337 | +0.6 pp (N 267) | 1 poz., śr. -26 pp, -13 $ | **+0.4 pp** | +66 |

**Według strategii (wynik $ faktyczny -> z szybkim stopem):**

| strategia | pozycji | $ faktycznie | $ odczyt co 2 s | $ co 5 s | $ co 10 s | śr. na pozycję (2 s) |
|---|---|---|---|---|---|---|
| safety_only | 152 | -2,146 | -1,876 | -1,945 | -1,989 | -24.8% |
| momentum_only | 141 | -2,139 | -1,874 | -1,933 | -1,980 | -26.9% |
| safety_wide | 130 | -2,064 | -1,948 | -1,969 | -1,994 | -30.1% |
| smart_money_only | 95 | -1,321 | -1,187 | -1,219 | -1,240 | -25.1% |
| hybrid | 113 | -1,233 | -1,112 | -1,140 | -1,164 | -20.0% |
| lowvol | 83 | -1,130 | -1,055 | -1,066 | -1,088 | -25.4% |
| lowvol_catastrophic | 73 | -1,085 | -1,071 | -1,073 | -1,074 | -29.3% |
| lowvol_wide | 75 | -1,026 | -1,046 | -1,010 | -1,010 | -27.9% |
| safety_ts5 | 79 | -1,004 | -953 | -966 | -982 | -24.1% |
| buyer_accel_only | 68 | -857 | -733 | -777 | -799 | -21.9% |
| random_eligible | 41 | -527 | -495 | -506 | -506 | -24.2% |
| strict | 30 | -511 | -515 | -524 | -536 | -34.3% |
| lowvol_ts10 | 39 | -364 | -363 | -363 | -364 | -18.6% |
| safety_s6 | 2 | -57 | -59 | -58 | -58 | -58.5% |

## 1. First buyers - segmentacja

Punkt decyzji: migracja + 30 min, token żyje. Tokenów: **608** (eksploracja 427, TEST 181); pierwszych kupujących (portfel x token): 7136; routerów wykluczonych: 151; hubów: 8. Definicje grup: firstbuyers.py (smart money od 6.10: >= 5 zamkniętych pozycji, >= 55% wygranych, mediana trzymania > 30 min, nie sprzedał w 5 min).

| grupa | N portfeli | udział | mediana wieku portfela (h) | sprzedał w 5 min | śr. zakup SOL |
|---|---|---|---|---|---|
| insider | 2458 | 34% | 31 | 50% | 11.08 |
| smart | 1 | 0% | nan | 0% | 0.98 |
| sniper | 3751 | 53% | 125 | 74% | 1.00 |
| retail | 926 | 13% | 311 | 47% | 1.93 |

**Smart money wg nowej definicji - ile portfeli przechodzi kolejne warunki:** >= 5 zamkniętych pozycji przed t: 4650 -> >= 55% wygranych: 1195 -> mediana trzymania > 30 min: 1 -> nie sprzedał w 5 min: **1**. Mediana trzymania (portfele z historią): 0.1 min; > 30 min ma 2% z nich - pierwsi kupujący na pump.fun prawie nie trzymają długo, więc grupa jest pusta (wynik, nie błąd).


**Baseline (wejście w każdy żywy token, wyjścia bota):**

| zbiór | N | rug | pump | nic | śr. wynik wejścia |
|---|---|---|---|---|---|
| eksploracja | 427 | 23% | 26% | 50% | -15.8% |
| TEST | 181 | 24% | 30% | 45% | -16.1% |

**Dominująca grupa wśród pierwszych kupujących -> wynik tokena:**

| dominuje | zbiór | N | rug | pump | śr. wynik |
|---|---|---|---|---|---|
| insider | eksploracja | 232 | 23% | 23% | -19.0% |
| insider | TEST | 106 | 26% | 34% | -18.0% |
| sniper | eksploracja | 182 | 24% | 30% | -11.9% |
| sniper | TEST | 69 | 20% | 26% | -13.6% |
| retail | eksploracja | 13 ⚠️ niewiarygodny | 23% | 31% | -14.5% |
| retail | TEST | 6 ⚠️ niewiarygodny | 33% | 17% | -11.7% |

**Pojedyncze cechy składu (AUC; kierunek ustalony na eksploracji):**

| cecha | cel | AUC eksploracja | AUC TEST (ten sam kierunek) | trzyma się? |
|---|---|---|---|---|
| frac_insider | rug | 0.514 | 0.494 | — |
| frac_insider | pump | 0.535 | 0.409 | — |
| frac_sniper | rug | 0.503 | 0.485 | — |
| frac_sniper | pump | 0.531 | 0.423 | — |
| frac_smart | rug | 0.502 | 0.500 | — |
| frac_smart | pump | 0.502 | 0.500 | — |
| frac_retail | rug | 0.539 | 0.470 | — |
| frac_retail | pump | 0.509 | 0.422 | — |
| vol_insider | rug | 0.526 | 0.490 | — |
| vol_insider | pump | 0.524 | 0.422 | — |
| vol_sniper | rug | 0.501 | 0.527 | — |
| vol_sniper | pump | 0.532 | 0.436 | — |
| vol_smart | rug | 0.502 | 0.500 | — |
| vol_smart | pump | 0.502 | 0.500 | — |
| vol_retail | rug | 0.549 | 0.478 | — |
| vol_retail | pump | 0.502 | 0.575 | — |
| age_med_h | rug | 0.507 | 0.421 | — |
| age_med_h | pump | 0.531 | 0.609 | — |
| frac_young | rug | 0.523 | 0.422 | — |
| frac_young | pump | 0.509 | 0.562 | — |
| frac_sold5m | rug | 0.532 | 0.445 | — |
| frac_sold5m | pump | 0.505 | 0.452 | — |
| frac_same_slot | rug | 0.547 | 0.566 | — |
| frac_same_slot | pump | 0.534 | 0.472 | — |
| frac_shared_funder | rug | 0.527 | 0.489 | — |
| frac_shared_funder | pump | 0.528 | 0.541 | — |
| frac_active | rug | 0.521 | 0.473 | — |
| frac_active | pump | 0.512 | 0.415 | — |
| young_insider_dump | rug | 0.507 | 0.463 | — |
| young_insider_dump | pump | 0.533 | 0.522 | — |

**Filtr "wchodź, gdy snajperów >= 50% pierwszych kupujących"** (reguła z 6.10, po zmianie definicji smart):

| zbiór | N baseline | baseline | N po filtrze | po filtrze | rug po filtrze |
|---|---|---|---|---|---|
| eksploracja | 427 | -15.8% | 176 | -12.3% | 24% |
| TEST | 181 | -16.1% | 60 | -14.9% | 22% |

**Połączenie z filtrami bota (werdykt bota: BUY/WATCH = przeszedł filtry):**

| zbiór | grupa | N | rug | śr. wynik |
|---|---|---|---|---|
| eksploracja | BUY/WATCH | 110 | 30% | -11.1% |
| eksploracja | BUY/WATCH + snajperzy >= 50% | 67 | 33% | -13.1% |
| eksploracja | REJECT/SKIP | 103 | 27% | -14.0% |
| eksploracja | nieoceniony | 214 | 18% | -19.1% |
| TEST | BUY/WATCH | 36 | 11% | +4.6% |
| TEST | BUY/WATCH + snajperzy >= 50% | 24 ⚠️ niewiarygodny | 12% | -2.1% |
| TEST | REJECT/SKIP | 69 | 32% | -21.5% |
| TEST | nieoceniony | 76 | 24% | -21.0% |

### 1c. Scoring wejścia - regresja logistyczna (4 cechy, cel = rug, trening tylko na eksploracji)

- model `rug`: współczynniki (cechy standaryzowane) frac_insider -0.28, frac_shared_funder -0.10, young_insider_dump +0.15, frac_sniper -0.29, wyraz wolny -1.19; **AUC eksploracja 0.543, TEST 0.446** (N test 181)
- model `pump`: współczynniki (cechy standaryzowane) frac_insider +0.02, frac_shared_funder +0.42, young_insider_dump -0.23, frac_sniper +0.22, wyraz wolny -1.06; **AUC eksploracja 0.595, TEST 0.491** (N test 181)

Filtr: wchodź tylko, gdy score_rug < 0.226 (mediana eksploracji). Wynik w $ przy stawce $50:

| zbiór | N baseline | baseline śr. | N wpuszczonych | wpuszczone śr. | $ wpuszczone | $ baseline (wszystkie) | N odrzuconych | odrzucone śr. | rug wpuszczone / odrzucone |
|---|---|---|---|---|---|---|---|---|---|
| eksploracja | 427 | -15.8% | 116 | -13.5% | -785 | -3381 | 311 | -16.7% | 20% / 25% |
| TEST | 181 | -16.1% | 48 | -10.7% | -256 | -1458 | 133 | -18.1% | 27% / 23% |

## 1b. First buyers - klasteryzacja (KMeans / DBSCAN)

Portfeli (portfel x token): 3731 (eksploracja 2490, TEST 1241); cech: 13.

silhouette (eksploracja): k=2: 0.270, k=3: 0.271, k=4: 0.281, k=5: 0.259, k=6: 0.264, k=7: 0.270 -> **k=4**

**Skład klastrów KMeans wg grup regułowych** (czy klasteryzacja odtwarza reguły?):

| klaster | N | insider | sniper | smart | retail | śr. wiek (h) | sprzedał w 5 min | śr. zakup SOL |
|---|---|---|---|---|---|---|---|---|---|
| K0 | 1145 | 41% | 19% | 0% | 40% | 170 | 53% | 3.50 |
| K1 | 2189 | 20% | 79% | 0% | 1% | 956 | 76% | 1.16 |
| K2 | 213 | 100% | 0% | 0% | 0% | 1 | 11% | 41.66 |
| K3 | 184 | 100% | 0% | 0% | 0% | 21 | 70% | 2.09 |

DBSCAN (eps=1.57, min 10, próbka 2490 portfeli eksploracji): klastrów 12, szum 11%, największy klaster 31% - są wyraźne skupiska.

**Udział klastra wśród pierwszych kupujących -> wynik tokena (AUC; kierunek z eksploracji):**

| klaster | cel | AUC eksploracja | AUC TEST | trzyma się? |
|---|---|---|---|---|
| K0 | rug | 0.554 | 0.456 | — |
| K0 | pump | 0.578 | 0.606 | TAK |
| K1 | rug | 0.507 | 0.569 | — |
| K1 | pump | 0.550 | 0.484 | — |
| K2 | rug | 0.501 | 0.479 | — |
| K2 | pump | 0.502 | 0.472 | — |
| K3 | rug | 0.556 | 0.575 | TAK |
| K3 | pump | 0.513 | 0.497 | — |

Tokenów: eksploracja 210, TEST 90.

## 2. Liquidity sweeps

Tokenów: 1197 (eksploracja 837, TEST 360), świece 1-min do 6 h po migracji.

**Siatka parametrów na EKSPLORACJI** (średni zwrot po 5 min po sygnale; baseline = każda 3. świeca):

| L | X | N | sweepów w dół | zwrot 5 min po | baseline 5 min | sweepów w górę | 5 min po (w górę) | wejście po sweepie (wyjścia bota) | wejście o losowej porze |
|---|---|---|---|---|---|---|---|---|---|
| 10 | 5% | 1 | 318 | -2.3% | -1.8% | 282 | -2.1% | -11.1% | -11.1% |
| 10 | 5% | 3 | 518 | -2.4% | -1.8% | 719 | -3.6% | -10.3% | -11.0% |
| 10 | 10% | 1 | 137 | -6.8% | -1.8% | 112 | -2.6% | -15.8% | -17.7% |
| 10 | 10% | 3 | 261 | -5.3% | -1.8% | 361 | -1.2% | -12.1% | -10.5% |
| 10 | 20% | 1 | 45 | -12.8% | -1.8% | 30 | +19.4% | -27.8% | -26.2% |
| 10 | 20% | 3 | 95 | -9.3% | -1.8% | 124 | +5.0% | -18.3% | -11.5% |
| 20 | 5% | 1 | 182 | -8.5% | -1.4% | 155 | +3.8% | -15.6% | -12.7% |
| 20 | 5% | 3 | 310 | -3.3% | -1.4% | 376 | -0.8% | -11.0% | -10.2% |
| 20 | 10% | 1 | 76 | -8.5% | -1.4% | 62 | +6.2% | -16.0% | -12.8% |
| 20 | 10% | 3 | 148 | -4.6% | -1.4% | 189 | +5.6% | -13.3% | -9.0% |
| 20 | 20% | 1 | 17 ⚠️ niewiarygodny | -21.2% | -1.4% | 14 | +5.1% | -36.3% | +7.4% |
| 20 | 20% | 3 | 41 | -12.9% | -1.4% | 57 | +8.9% | -25.6% | -10.9% |

**Wybrane na eksploracji:** L=10, X=10%, N=1. **TEST (liczony raz):**

| zbiór | zdarzenie | N | po 1 min | po 5 min | po 15 min | % dodatnich po 5 min |
|---|---|---|---|---|---|---|
| eksploracja | sweep w dół (powrót) | 137 | -2.0% | -6.8% | -16.9% | 36% |
| eksploracja | wybicie bez powrotu (trend) | 1705 | -6.6% | -8.0% | -10.4% | 36% |
| eksploracja | sweep w górę (fałszywe wybicie) | 112 | +0.5% | -2.6% | -1.1% | 40% |
| eksploracja | baseline: każda 3. świeca | 19026 | -0.7% | -1.8% | -3.7% | 53% |
| eksploracja | WEJŚCIE po sweepie w dół (wyjścia bota) | 134 |  |  |  | -15.8% (CI -22.3%..-9.1%) |
| eksploracja | WEJŚCIE o losowej porze (baseline) | 134 |  |  |  | -13.5% (CI -19.5%..-6.9%) |
| TEST | sweep w dół (powrót) | 44 | +6.7% | +0.1% | +9.3% | 50% |
| TEST | wybicie bez powrotu (trend) | 701 | -4.3% | -4.3% | -5.8% | 41% |
| TEST | sweep w górę (fałszywe wybicie) | 36 | -4.1% | -18.3% | -29.8% | 33% |
| TEST | baseline: każda 3. świeca | 7802 | -1.0% | -1.8% | -3.1% | 57% |
| TEST | WEJŚCIE po sweepie w dół (wyjścia bota) | 44 |  |  |  | -8.4% (CI -19.9%..+4.3%) |
| TEST | WEJŚCIE o losowej porze (baseline) | 44 |  |  |  | +5.8% (CI -7.2%..+20.7%) |

## 3. Dynamiczny stop loss

**Wejścia bota (ten sam zestaw co części 4, 6, 7; z pomiarami płynności 264)** - wejść 294 (eksploracja 205, TEST 89); rug = token spadł <= -80% w 6 h.

| wariant | zbiór | N | śr. wynik | suma (stawki) | max DD (stawki) | najgorsza | N rugów | śr. na rugach |
|---|---|---|---|---|---|---|---|---|
| B0 SL-25% (baseline) | eksploracja | 205 | -10.7% | -21.97 | 22.61 | -99% | 101 | -22.1% |
| B0 SL-25% (baseline) | TEST | 89 | -6.1% | -5.46 | 7.28 | -100% | 41 | -22.9% |
| B1 SL-40% stały | eksploracja | 205 | -15.3% | -31.41 | 32.31 | -99% | 101 | -33.6% |
| B1 SL-40% stały | TEST | 89 | -6.7% | -5.96 | 8.34 | -100% | 41 | -24.1% |
| D1 płynność->SL-40% | eksploracja | 205 | -14.9% | -30.60 | 31.50 | -99% | 101 | -32.9% |
| D1 płynność->SL-40% | TEST | 89 | -5.7% | -5.03 | 8.34 | -100% | 41 | -22.1% |
| D2 sweep->SL-40% | eksploracja | 205 | -14.9% | -30.48 | 31.38 | -99% | 101 | -33.5% |
| D2 sweep->SL-40% | TEST | 89 | -5.3% | -4.68 | 7.58 | -100% | 41 | -22.6% |
| D3 płynność+sweep->SL-40% | eksploracja | 205 | -14.5% | -29.66 | 30.56 | -99% | 101 | -32.8% |
| D3 płynność+sweep->SL-40% | TEST | 89 | -4.3% | -3.82 | 7.58 | -100% | 41 | -20.8% |
| D4 SL-40% + strażnik płynności | eksploracja | 205 | -15.3% | -31.41 | 32.31 | -99% | 101 | -33.6% |
| D4 SL-40% + strażnik płynności | TEST | 89 | -6.7% | -5.96 | 8.34 | -100% | 41 | -24.1% |

Najlepszy na eksploracji: **D3 płynność+sweep->SL-40%** (-14.5% vs baseline -10.7%). TEST: -4.3% vs baseline -6.1% -> żaden wariant nie bije baseline już na eksploracji. Na rugach w teście szerszy SL dał gorszy wynik niż -25% w 18/41 przypadków.

**Migracje + 30 min (bez danych o płynności: tylko B0/B1/D2)** - wejść 617 (eksploracja 431, TEST 186); rug = token spadł <= -80% w 6 h.

| wariant | zbiór | N | śr. wynik | suma (stawki) | max DD (stawki) | najgorsza | N rugów | śr. na rugach |
|---|---|---|---|---|---|---|---|---|
| B0 SL-25% (baseline) | eksploracja | 431 | -15.8% | -68.23 | 68.74 | -100% | 141 | -35.1% |
| B0 SL-25% (baseline) | TEST | 186 | -15.7% | -29.29 | 29.29 | -100% | 70 | -35.3% |
| B1 SL-40% stały | eksploracja | 431 | -17.5% | -75.35 | 76.20 | -100% | 141 | -38.2% |
| B1 SL-40% stały | TEST | 186 | -17.5% | -32.62 | 32.62 | -100% | 70 | -40.3% |
| D2 sweep->SL-40% | eksploracja | 431 | -17.5% | -75.57 | 76.41 | -100% | 141 | -37.8% |
| D2 sweep->SL-40% | TEST | 186 | -17.9% | -33.38 | 33.38 | -100% | 70 | -40.5% |

Najlepszy na eksploracji: **B1 SL-40% stały** (-17.5% vs baseline -15.8%). TEST: -17.5% vs baseline -15.7% -> żaden wariant nie bije baseline już na eksploracji. Na rugach w teście szerszy SL dał gorszy wynik niż -25% w 14/70 przypadków.

## 4. Częściowa realizacja zysku (scaling out)

**Wejścia bota (świece z archiwum)** - wejść 294 (eksploracja 205, TEST 89)

| schemat | zbiór | N | suma (stawki) | śr. | odch. std | max DD | % zyskownych |
|---|---|---|---|---|---|---|---|
| S0 obecny: 1/3 @+50%, 1/3 @+100%, reszta @+300%, trailing 20% | eksploracja | 205 | -21.97 | -10.7% | 0.39 | 22.61 | 28% |
| S0 obecny: 1/3 @+50%, 1/3 @+100%, reszta @+300%, trailing 20% | TEST | 89 | -5.46 | -6.1% | 0.42 | 7.28 | 38% |
| S1 25% @+20%, reszta trailing 20% | eksploracja | 205 | -16.86 | -8.2% | 0.41 | 17.54 | 38% |
| S1 25% @+20%, reszta trailing 20% | TEST | 89 | -4.35 | -4.9% | 0.37 | 5.28 | 46% |
| S2 50% @+20%, reszta trailing 20% | eksploracja | 205 | -18.74 | -9.1% | 0.33 | 19.15 | 45% |
| S2 50% @+20%, reszta trailing 20% | TEST | 89 | -5.39 | -6.1% | 0.33 | 6.15 | 57% |
| S3 50% @+30%, reszta break-even + trailing 25% | eksploracja | 205 | -19.61 | -9.6% | 0.35 | 20.03 | 39% |
| S3 50% @+30%, reszta break-even + trailing 25% | TEST | 89 | -8.90 | -10.0% | 0.34 | 9.32 | 44% |
| S4 25% @+20%, 25% @+50%, reszta trailing 20% | eksploracja | 205 | -18.20 | -8.9% | 0.35 | 18.75 | 38% |
| S4 25% @+20%, 25% @+50%, reszta trailing 20% | TEST | 89 | -4.59 | -5.2% | 0.35 | 5.44 | 46% |
| S5 50% @+50%, reszta trailing 20% | eksploracja | 205 | -20.67 | -10.1% | 0.42 | 21.36 | 28% |
| S5 50% @+50%, reszta trailing 20% | TEST | 89 | -5.66 | -6.4% | 0.41 | 7.32 | 38% |
| S6 33% @+20% + break-even, potem 1/3 @+100%, reszta @+300% | eksploracja | 205 | -19.85 | -9.7% | 0.31 | 20.31 | 44% |
| S6 33% @+20% + break-even, potem 1/3 @+100%, reszta @+300% | TEST | 89 | -4.43 | -5.0% | 0.35 | 5.37 | 57% |
| S7 100% @+20% (całość) | eksploracja | 205 | -22.50 | -11.0% | 0.25 | 22.77 | 46% |
| S7 100% @+20% (całość) | TEST | 89 | -7.48 | -8.4% | 0.29 | 7.88 | 57% |

Najlepszy na eksploracji: **S1** (+2.5 pp vs obecny). TEST: +1.2 pp (95% CI różnicy w parach -2.5..+5.3 pp) -> kierunek się zgadza, ale CI obejmuje 0.

**Migracje + 30 min (wszystkie żywe tokeny)** - wejść 617 (eksploracja 431, TEST 186)

| schemat | zbiór | N | suma (stawki) | śr. | odch. std | max DD | % zyskownych |
|---|---|---|---|---|---|---|---|
| S0 obecny: 1/3 @+50%, 1/3 @+100%, reszta @+300%, trailing 20% | eksploracja | 431 | -68.23 | -15.8% | 0.42 | 68.74 | 21% |
| S0 obecny: 1/3 @+50%, 1/3 @+100%, reszta @+300%, trailing 20% | TEST | 186 | -29.29 | -15.7% | 0.45 | 29.29 | 28% |
| S1 25% @+20%, reszta trailing 20% | eksploracja | 431 | -85.63 | -19.9% | 0.35 | 86.06 | 21% |
| S1 25% @+20%, reszta trailing 20% | TEST | 186 | -39.94 | -21.5% | 0.38 | 39.94 | 28% |
| S2 50% @+20%, reszta trailing 20% | eksploracja | 431 | -75.45 | -17.5% | 0.30 | 75.83 | 25% |
| S2 50% @+20%, reszta trailing 20% | TEST | 186 | -31.10 | -16.7% | 0.32 | 31.10 | 32% |
| S3 50% @+30%, reszta break-even + trailing 25% | eksploracja | 431 | -76.64 | -17.8% | 0.33 | 77.03 | 22% |
| S3 50% @+30%, reszta break-even + trailing 25% | TEST | 186 | -33.32 | -17.9% | 0.34 | 33.32 | 27% |
| S4 25% @+20%, 25% @+50%, reszta trailing 20% | eksploracja | 431 | -76.35 | -17.7% | 0.32 | 76.81 | 21% |
| S4 25% @+20%, 25% @+50%, reszta trailing 20% | TEST | 186 | -31.85 | -17.1% | 0.34 | 31.85 | 28% |
| S5 50% @+50%, reszta trailing 20% | eksploracja | 431 | -77.67 | -18.0% | 0.37 | 78.19 | 18% |
| S5 50% @+50%, reszta trailing 20% | TEST | 186 | -35.49 | -19.1% | 0.38 | 35.49 | 22% |
| S6 33% @+20% + break-even, potem 1/3 @+100%, reszta @+300% | eksploracja | 431 | -66.03 | -15.3% | 0.36 | 66.45 | 28% |
| S6 33% @+20% + break-even, potem 1/3 @+100%, reszta @+300% | TEST | 186 | -25.13 | -13.5% | 0.39 | 25.13 | 35% |
| S7 100% @+20% (całość) | eksploracja | 431 | -55.10 | -12.8% | 0.29 | 55.38 | 35% |
| S7 100% @+20% (całość) | TEST | 186 | -13.43 | -7.2% | 0.30 | 13.64 | 52% |

Najlepszy na eksploracji: **S7** (+3.0 pp vs obecny). TEST: +8.5 pp (95% CI różnicy w parach +3.2..+14.3 pp) -> TRZYMA SIĘ.

## 5. Wykrywanie manipulacji (obrona)

**(A) Migracje + 30 min, tokeny z pełną historią krzywej: 303** (eksploracja 217, TEST 86). Progi z eksploracji: F2 udział kółek >= 2%; F3 (tylko krzywe >= 20 min: 15 tokenów eksploracji) wolumen 10 min >= 142.4 SOL i nowi kupujący <= 64%.

| flaga | zbiór | N z flagą | rug z flagą | rug bez | wynik z flagą | wynik bez | baseline (wszystkie) | zysk z omijania |
|---|---|---|---|---|---|---|---|---|
| F1 | eksploracja | 105 | 22% | 20% | -15.0% | -18.1% | -16.6% | -1.5% |
| F1 | TEST | 24 ⚠️ niewiarygodny | 17% | 27% | -5.4% | -17.5% | -14.1% | -3.4% |
| F2 | eksploracja | 73 | 21% | 21% | -13.7% | -18.1% | -16.6% | -1.5% |
| F2 | TEST | 23 ⚠️ niewiarygodny | 35% | 21% | -19.2% | -12.3% | -14.1% | +1.9% |
| F3 | eksploracja | 2 ⚠️ niewiarygodny | 50% | 20% | -19.4% | -16.6% | -16.6% | +0.0% |
| F3 | TEST | 0 ⚠️ niewiarygodny | — | 24% | — | -14.1% | -14.1% | +0.0% |
| F4 | eksploracja | 2 ⚠️ niewiarygodny | 0% | 21% | -26.9% | -16.5% | -16.6% | +0.1% |
| F4 | TEST | 0 ⚠️ niewiarygodny | — | 24% | — | -14.1% | -14.1% | +0.0% |

**(B) PRAWDZIWE pozycje bota w tokenach z pełną historią krzywej: 13 wejść** (eksploracja 9, TEST 4).

| flaga | zbiór | wejść z flagą | pozycji | $ z flagą | $ baseline (wszystkie) | $ gdyby omijać flagę |
|---|---|---|---|---|---|---|
| F1 | eksploracja | 9 ⚠️ niewiarygodny | 57 | -998 | -998 | +0 |
| F1 | TEST | 4 ⚠️ niewiarygodny | 24 | -246 | -246 | +0 |
| F2 | eksploracja | 7 ⚠️ niewiarygodny | 45 | -593 | -998 | -405 |
| F2 | TEST | 4 ⚠️ niewiarygodny | 24 | -246 | -246 | +0 |
| F3 | eksploracja | 0 ⚠️ niewiarygodny | 0 | +0 | -998 | -998 |
| F3 | TEST | 0 ⚠️ niewiarygodny | 0 | +0 | -246 | -246 |
| F4 | eksploracja | 0 ⚠️ niewiarygodny | 0 | +0 | -998 | -998 |
| F4 | TEST | 0 ⚠️ niewiarygodny | 0 | +0 | -246 | -246 |

## 6. Definicje ruga

Wejścia bota ze świecami: **294** (eksploracja 205, TEST 89); z migawkami płynności po wejściu: 294; w danych map rugów (c2): 12.

**Ile rugów wg każdej definicji** (odsetek wejść; stabilność w czasie: eksploracja vs TEST):

| definicja | rugów | odsetek | eksploracja | TEST | pozycji bota | $ na tych pozycjach | śr. wynik pozycji |
|---|---|---|---|---|---|---|---|
| (a) wycofanie płynności | 1 | 0% | 0% | 1% | 4 | -61 | -30.4% |
| (a') płynność -50% | 61 | 21% | 21% | 19% | 295 | -5288 | -36.1% |
| (b1) -70% w 30 min | 69 | 23% | 25% | 20% | 344 | -7006 | -40.9% |
| (b2) -80% w 6 h | 142 | 48% | 49% | 46% | 719 | -9079 | -25.4% |
| (c1) dev_sell | 7 | 2% | 2% | 2% | 49 | -497 | -20.3% |
| (c2) top holder >= 3% | 1 | 0% | 0% | 0% | 5 | -75 | -30.1% |
| (d1) b1 lub a | 69 | 23% | 25% | 20% | 344 | -7006 | -40.9% |
| (d2) b2 i (a' lub c) | 63 | 21% | 22% | 19% | 301 | -5260 | -35.2% |
| (e) -70% zanim +50% (6 h) | 104 | 35% | 39% | 27% | 510 | -10561 | -41.6% |

**Pokrycie definicji** (ile % rugów z wiersza jest też rugiem wg kolumny):

| rug wg \ też wg | a | a_raw | b1 | b2 | c1 | c2 | d1 | d2 | e |
|---|---|---|---|---|---|---|---|---|---|
| (a) wycofanie płynności | 100% | 100% | 100% | 100% | 0% | 0% | 100% | 100% | 100% |
| (a') płynność -50% | 2% | 100% | 57% | 98% | 0% | 0% | 57% | 98% | 69% |
| (b1) -70% w 30 min | 1% | 51% | 100% | 93% | 1% | 0% | 100% | 52% | 78% |
| (b2) -80% w 6 h | 1% | 42% | 45% | 100% | 1% | 1% | 45% | 44% | 65% |
| (c1) dev_sell | 0% | 0% | 14% | 29% | 100% | 0% | 14% | 29% | 14% |
| (c2) top holder >= 3% | 0% | 0% | 0% | 100% | 0% | 100% | 0% | 100% | 0% |
| (d1) b1 lub a | 1% | 51% | 100% | 93% | 1% | 0% | 100% | 52% | 78% |
| (d2) b2 i (a' lub c) | 2% | 95% | 57% | 100% | 3% | 2% | 57% | 100% | 68% |
| (e) -70% zanim +50% (6 h) | 1% | 40% | 52% | 89% | 1% | 0% | 52% | 41% | 100% |

**Wynik strategii: $ na wejściach uznanych za rug vs pozostałe (cały okres)**

| strategia | pozycji | $ razem | $ na rugach b1 (N) | $ na rugach b2 (N) | $ na rugach e (N) | $ na rugach a' (N) |
|---|---|---|---|---|---|---|
| buyer_accel_only | 97 | -313 | -476 (30) | -613 (61) | -659 (36) | -199 (26) |
| hybrid | 146 | -658 | -669 (34) | -884 (70) | -864 (48) | -515 (35) |
| lowvol | 120 | -538 | -315 (12) | -311 (38) | -505 (29) | -331 (15) |
| lowvol_catastrophic | 118 | -631 | -415 (12) | -627 (36) | -970 (27) | -507 (13) |
| lowvol_ts10 | 63 | -268 | -67 (7) | -157 (17) | -195 (15) | -115 (9) |
| lowvol_wide | 118 | -526 | -389 (12) | -476 (36) | -774 (27) | -430 (13) |
| momentum_only | 199 | -1195 | -1014 (51) | -1283 (97) | -1322 (67) | -679 (38) |
| random_eligible | 61 | -67 | -244 (13) | -263 (28) | -415 (21) | -100 (8) |
| safety_only | 214 | -1232 | -1023 (53) | -1288 (100) | -1393 (71) | -711 (41) |
| safety_s6 | 13 | -34 | -47 (3) | -43 (7) | -72 (3) | -39 (4) |
| safety_ts5 | 119 | -719 | -491 (30) | -612 (58) | -632 (41) | -229 (24) |
| safety_wide | 198 | -1146 | -1116 (50) | -1335 (96) | -1638 (63) | -770 (37) |
| smart_money_only | 115 | -956 | -660 (34) | -863 (57) | -810 (47) | -459 (22) |
| strict | 46 | -331 | -80 (3) | -326 (18) | -311 (15) | -203 (10) |

## 7. Koszty: wynik brutto vs koszty

**(A) Symulacja: ten sam zestaw wejść co części 3/4/6, wyjście obecne (S0) i S6**

| zbiór | wyjście | N | brutto | netto | koszty razem | w tym wejście | w tym wyjście |
|---|---|---|---|---|---|---|---|
| wejścia bota | S0 | 294 | -4.1% | -9.3% | 5.2 pp | 1.4 pp | 3.8 pp |
| wejścia bota | S6 | 294 | -3.0% | -8.3% | 5.3 pp | 1.4 pp | 3.8 pp |
| migracje + 30 min | S0 | 617 | -11.0% | -15.8% | 4.8 pp | 1.3 pp | 3.5 pp |
| migracje + 30 min | S6 | 617 | -9.9% | -14.8% | 4.9 pp | 1.3 pp | 3.6 pp |

**(B) PRAWDZIWE pozycje bota: 1664** (eksploracja 1164, TEST 500) - średnio na pozycję, w pp stawki ($50):

| okres | N | brutto (pp) | priority fee | poślizg 'z życia' 1% | DEX + pula | luka przy krachu | koszty razem | netto (pp) |
|---|---|---|---|---|---|---|---|---|
| cały okres | 1664 | -5.8 | 0.2 | 1.9 | -1.7 | 4.6 | **5.0** | -10.9 |
| eksploracja | 1164 | -8.3 | 0.2 | 1.9 | -1.6 | 4.5 | **5.1** | -13.3 |
| TEST | 500 | -0.2 | 0.2 | 2.0 | -2.1 | 4.9 | **5.0** | -5.2 |

**Według strategii (cały okres, suma $):**

| strategia | pozycji | $ brutto | $ koszty zwykłe | $ luka przy krachu | $ netto |
|---|---|---|---|---|---|
| safety_only | 219 | -814 | -26 | 498 | -1286 |
| momentum_only | 203 | -745 | -7 | 497 | -1234 |
| safety_wide | 201 | -567 | -22 | 624 | -1170 |
| smart_money_only | 115 | -716 | -7 | 247 | -956 |
| hybrid | 150 | -469 | -6 | 262 | -725 |
| safety_ts5 | 124 | -550 | -80 | 255 | -725 |
| lowvol_catastrophic | 119 | -41 | 168 | 434 | -644 |
| lowvol | 123 | -190 | 177 | 214 | -581 |
| lowvol_wide | 119 | -56 | 163 | 320 | -539 |
| strict | 48 | -201 | 62 | 95 | -358 |
| buyer_accel_only | 98 | -225 | -114 | 224 | -335 |
| lowvol_ts10 | 66 | -232 | 73 | 0 | -305 |
| random_eligible | 62 | +48 | 13 | 118 | -83 |
| safety_s6 | 17 | -72 | -40 | 39 | -71 |

## 8. Bundlery (zakupy wielu portfeli w bloku startu)

Definicje (ustalone przed patrzeniem na wyniki):
  bundle      = zakupy z >= 2 RÓŻNYCH portfeli w tym samym slocie: w slocie utworzenia tokena albo w N = 3 kolejnych
                (krzywa pump.fun z data/stream.db, bez routerów). Portfel bundla = każdy kupujący w takim slocie (też twórca).
  (a) bundle_start_pct = % podaży kupiony w bundlach przy starcie (netto: minus sprzedaż tych portfeli w slotach 0..3,
                         bo zdarza się "flip" w bloku startu; max 100%).
  (b) bundle_held_pct  = % podaży, który portfele bundla NADAL mają w chwili decyzji bota: saldo ich kont tokena (ATA)
                         po ostatniej transakcji przed chwilą t (Helius: historia konta + saldo z transakcji). Przelew na
                         inny portfel liczy się jako "nie trzyma" (dolne oszacowanie trzymania przez grupę).
  wspólny zasilający = >= 2 portfele bundla zasilone przez ten sam portfel (bez hubów - giełd/serwisów zasilających
                       >= 15 portfeli na eksploracji) albo portfel bundla zasilony przez twórcę lub jego zasilającego.
  "dev sam" = w slocie utworzenia kupił tylko twórca (to NIE jest bundle wg definicji - osobna kategoria w tabelach).
Zbiory: migracje + 30 min (każdy żywy token, jak części 1-6) i wejścia bota w tokeny utworzone w czasie zbierania.
Wynik wejścia: wyjście bota (S0) i S6, koszty analiz; rug = etykieta (e): -70% przed +50% w 6 h; "max zysk" = MFE.
Progi filtrów wyłącznie z eksploracji (70% czasu), TEST liczony raz.


**Ile tokenów da się ocenić:** migracje + 30 min: 517 z 617 (reszta: dziura w danych zbieracza przy starcie); wejścia bota: 70 z 294 (pozostałe to tokeny sprzed startu zbieracza 04.10 10:23 albo spoza pump.fun). Saldo bundlerów w chwili decyzji znane dla 394 migracji i 34 wejść bota.

| zbiór | tokenów | z bundlem | mediana portfeli bundla | śr. % podaży w bundlu (gdy jest) | z tego slot 0 | wspólny zasilający | twórca w bundlu | dev sam kupił >= 40% w slocie 0 |
|---|---|---|---|---|---|---|---|---|
| migracje + 30 min | 517 | 52% | 8 | 40.0% | 90% | 43% | 78% | 37% |
| wejścia bota | 70 | 93% | 8 | 35.0% | 95% | 38% | 74% | 1% |

**(a) % podaży kupionej w bundlach przy starcie - migracje + 30 min** (N 517):

| kubełek | zbiór | N | śr. wynik (obecne wyjście) | śr. wynik (S6) | % rugów (e) | mediana max zysku 6 h |
|---|---|---|---|---|---|---|
| 0-10% | eksploracja | 175 | -17.9% | -16.7% | 24% | +13% |
| 0-10% | TEST | 97 | -18.5% | -16.3% | 25% | +20% |
|   w tym: dev sam kupił >= 40% w slocie 0 | eksploracja | 118 | -22.8% | -21.0% | 28% | +14% |
|   w tym: normalny start | eksploracja | 57 | -7.7% | -7.6% | 16% | +13% |
|   w tym: dev sam kupił >= 40% w slocie 0 | TEST | 71 | -16.8% | -16.3% | 20% | +24% |
|   w tym: normalny start | TEST | 26 ⚠️ niewiarygodny | -23.1% | -16.6% | 38% | +5% |
| 10-20% | eksploracja | 20 ⚠️ niewiarygodny | -17.1% | -18.6% | 40% | +25% |
| 10-20% | TEST | 8 ⚠️ niewiarygodny | -3.7% | +1.0% | 12% | +61% |
| 20-30% | eksploracja | 41 | -15.1% | -12.2% | 27% | +10% |
| 20-30% | TEST | 16 ⚠️ niewiarygodny | -6.9% | -5.7% | 12% | +28% |
| 30-40% | eksploracja | 29 ⚠️ niewiarygodny | -8.2% | -11.4% | 21% | +4% |
| 30-40% | TEST | 13 ⚠️ niewiarygodny | -9.8% | -6.4% | 15% | +29% |
| 40%+ | eksploracja | 96 | -13.3% | -12.0% | 20% | +4% |
| 40%+ | TEST | 22 ⚠️ niewiarygodny | +3.8% | +3.2% | 23% | +37% |
| **wszystkie (baseline)** | eksploracja | 361 | -15.5% | -14.6% | 24% | +10% |
| **wszystkie (baseline)** | TEST | 156 | -12.7% | -10.8% | 22% | +24% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | eksploracja | 45 | -9.4% | -7.2% | 42% | +76% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | TEST | 20 ⚠️ niewiarygodny | +9.2% | +8.3% | 15% | +111% |

Kształt zależności (wynik obecnego wyjścia ~ cecha):
- eksploracja (N 361): Spearman +0.03; parabola c = -0.16e-4, wierzchołek 63%; średnie kubełków (N >= 10): 0-10% -17.9%, 10-20% -17.1%, 20-30% -15.1%, 30-40% -8.2%, 40%+ -13.3% -> **brak związku**
- TEST (N 156): Spearman +0.15; parabola c = +0.08e-4, wierzchołek -187%; średnie kubełków (N >= 10): 0-10% -18.5%, 10-20% —, 20-30% -6.9%, 30-40% -9.8%, 40%+ +3.8% -> **wzrost**

**Kształt: eksploracja: brak związku, TEST: wzrost.**

| filtr / hipoteza | eksploracja: filtr vs baseline (N) | TEST: filtr vs baseline (N; p losowe) | random_eligible oczekiwany, TEST (N) | werdykt |
|---|---|---|---|---|
| bundle (a) hipoteza: 20-30% opłacalne (obecne wyjście) | -15.1% vs -15.5% (N 41/361) | -6.9% vs -12.7% (N 16 ⚠️ niewiarygodny/156; p 0.27) | +9.2% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| bundle (a) hipoteza: unikaj >= 35% (obecne wyjście) | -16.8% vs -15.5% (N 255/361) | -15.5% vs -12.7% (N 129/156; p 0.95) | +9.2% (N 20 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| bundle (a) najlepszy przedział z eksploracji 30%+ (obecne wyjście) | -12.1% vs -15.5% (N 125/361) | -1.2% vs -12.7% (N 35/156; p 0.03) | +9.2% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| bundle (a) hipoteza: 20-30% opłacalne (S6) | -12.2% vs -14.6% (N 41/361) | -5.7% vs -10.8% (N 16 ⚠️ niewiarygodny/156; p 0.27) | +8.3% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| bundle (a) hipoteza: unikaj >= 35% (S6) | -15.8% vs -14.6% (N 255/361) | -13.3% vs -10.8% (N 129/156; p 0.95) | +8.3% (N 20 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| bundle (a) najlepszy przedział z eksploracji 30%+ (S6) | -11.8% vs -14.6% (N 125/361) | -0.4% vs -10.8% (N 35/156; p 0.03) | +8.3% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |

**(a) % podaży kupionej w bundlach przy starcie - wejścia bota** (N 70):

| kubełek | zbiór | N | śr. wynik (obecne wyjście) | śr. wynik (S6) | % rugów (e) | mediana max zysku 6 h |
|---|---|---|---|---|---|---|
| 0-10% | eksploracja | 4 ⚠️ niewiarygodny | -16.7% | -11.4% | 25% | +612% |
| 0-10% | TEST | 5 ⚠️ niewiarygodny | -16.6% | -17.9% | 60% | +28% |
|   w tym: normalny start | eksploracja | 4 ⚠️ niewiarygodny | -16.7% | -11.4% | 25% | +612% |
|   w tym: dev sam kupił >= 40% w slocie 0 | TEST | 1 ⚠️ niewiarygodny | -99.6% | -99.6% | 100% | +16% |
|   w tym: normalny start | TEST | 4 ⚠️ niewiarygodny | +4.1% | +2.5% | 50% | +57% |
| 10-20% | eksploracja | 9 ⚠️ niewiarygodny | -3.7% | -7.3% | 33% | +117% |
| 10-20% | TEST | 4 ⚠️ niewiarygodny | +10.0% | +14.3% | 0% | +93% |
| 20-30% | eksploracja | 13 ⚠️ niewiarygodny | -14.9% | -17.2% | 54% | +65% |
| 20-30% | TEST | 3 ⚠️ niewiarygodny | +12.7% | +6.5% | 0% | +90% |
| 30-40% | eksploracja | 6 ⚠️ niewiarygodny | -7.0% | -7.3% | 17% | +148% |
| 30-40% | TEST | 5 ⚠️ niewiarygodny | +6.2% | +0.6% | 0% | +128% |
| 40%+ | eksploracja | 17 ⚠️ niewiarygodny | -16.8% | -16.0% | 59% | +17% |
| 40%+ | TEST | 4 ⚠️ niewiarygodny | +29.0% | +16.5% | 25% | +209% |
| **wszystkie (baseline)** | eksploracja | 49 | -12.7% | -13.3% | 45% | +55% |
| **wszystkie (baseline)** | TEST | 21 ⚠️ niewiarygodny | +6.8% | +2.7% | 19% | +100% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | eksploracja | 49 | -12.7% | -13.3% | 45% | +55% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | TEST | 21 ⚠️ niewiarygodny | +6.8% | +2.7% | 19% | +100% |

Kształt zależności (wynik obecnego wyjścia ~ cecha):
- eksploracja (N 49): Spearman -0.14; parabola c = +0.59e-4, wierzchołek 47%; średnie kubełków (N >= 10): 0-10% —, 10-20% —, 20-30% -14.9%, 30-40% —, 40%+ -16.8% -> **spadek (im więcej, tym gorzej)**
- TEST (N 21 ⚠️ niewiarygodny): Spearman +0.17; parabola c = -0.44e-4, wierzchołek 93%; średnie kubełków (N >= 10): 0-10% —, 10-20% —, 20-30% —, 30-40% —, 40%+ — -> **wzrost**

**Kształt: eksploracja: spadek (im więcej, tym gorzej), TEST: wzrost.**

**(b) % podaży, który bundlerzy NADAL trzymają w chwili decyzji - migracje + 30 min** (N 394):

| kubełek | zbiór | N | śr. wynik (obecne wyjście) | śr. wynik (S6) | % rugów (e) | mediana max zysku 6 h |
|---|---|---|---|---|---|---|
| 0-10% | eksploracja | 272 | -16.8% | -16.0% | 23% | +9% |
| 0-10% | TEST | 117 | -14.3% | -12.2% | 21% | +24% |
| 10-20% | eksploracja | 2 ⚠️ niewiarygodny | +16.4% | +2.2% | 0% | +63% |
| 10-20% | TEST | 0 | — | — | — | — |
| 20-30% | eksploracja | 0 | — | — | — | — |
| 20-30% | TEST | 1 ⚠️ niewiarygodny | +90.9% | +81.6% | 0% | +217% |
| 30-40% | eksploracja | 0 | — | — | — | — |
| 30-40% | TEST | 0 | — | — | — | — |
| 40%+ | eksploracja | 1 ⚠️ niewiarygodny | -29.1% | -29.1% | 0% | +133% |
| 40%+ | TEST | 1 ⚠️ niewiarygodny | +33.2% | +0.8% | 0% | +215% |
| **wszystkie (baseline)** | eksploracja | 275 | -16.6% | -15.9% | 23% | +9% |
| **wszystkie (baseline)** | TEST | 119 | -13.0% | -11.3% | 21% | +24% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | eksploracja | 20 ⚠️ niewiarygodny | -0.7% | -3.6% | 25% | +166% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | TEST | 10 ⚠️ niewiarygodny | +15.8% | +13.2% | 10% | +115% |

Kształt zależności (wynik obecnego wyjścia ~ cecha):
- eksploracja (N 275): Spearman +0.00; parabola c = -3.37e-4, wierzchołek 31%; średnie kubełków (N >= 10): 0-10% -16.8%, 10-20% —, 20-30% —, 30-40% —, 40%+ — -> **brak związku**
- TEST (N 119): Spearman +0.19; parabola c = -14.28e-4, wierzchołek 28%; średnie kubełków (N >= 10): 0-10% -14.3%, 10-20% —, 20-30% —, 30-40% —, 40%+ — -> **wzrost**

**Kształt: eksploracja: brak związku, TEST: wzrost.**

| filtr / hipoteza | eksploracja: filtr vs baseline (N) | TEST: filtr vs baseline (N; p losowe) | random_eligible oczekiwany, TEST (N) | werdykt |
|---|---|---|---|---|
| bundle (b) hipoteza: 20-30% opłacalne (obecne wyjście) | — vs -16.6% (N 0/275) | +90.9% vs -13.0% (N 1 ⚠️ niewiarygodny/119; p 0.04) | +15.8% (N 10 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| bundle (b) hipoteza: unikaj >= 35% (obecne wyjście) | -16.5% vs -16.6% (N 274/275) | -13.4% vs -13.0% (N 118/119; p 0.90) | +15.8% (N 10 ⚠️ niewiarygodny) | NIE trzyma się na teście |
| bundle (b) najlepszy przedział z eksploracji 0-20% (obecne wyjście) | -16.5% vs -16.6% (N 274/275) | -14.3% vs -13.0% (N 117/119; p 0.97) | +15.8% (N 10 ⚠️ niewiarygodny) | NIE trzyma się na teście |
| bundle (b) hipoteza: 20-30% opłacalne (S6) | — vs -15.9% (N 0/275) | +81.6% vs -11.3% (N 1 ⚠️ niewiarygodny/119; p 0.04) | +13.2% (N 10 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| bundle (b) hipoteza: unikaj >= 35% (S6) | -15.9% vs -15.9% (N 274/275) | -11.4% vs -11.3% (N 118/119; p 0.66) | +13.2% (N 10 ⚠️ niewiarygodny) | NIE trzyma się na teście |
| bundle (b) najlepszy przedział z eksploracji 0-20% (S6) | -15.9% vs -15.9% (N 274/275) | -12.2% vs -11.3% (N 117/119; p 0.95) | +13.2% (N 10 ⚠️ niewiarygodny) | NIE trzyma się na teście |

**(b) % podaży, który bundlerzy NADAL trzymają w chwili decyzji - wejścia bota** (N 34):

| kubełek | zbiór | N | śr. wynik (obecne wyjście) | śr. wynik (S6) | % rugów (e) | mediana max zysku 6 h |
|---|---|---|---|---|---|---|
| 0-10% | eksploracja | 22 ⚠️ niewiarygodny | +1.4% | -3.7% | 27% | +96% |
| 0-10% | TEST | 11 ⚠️ niewiarygodny | +8.9% | +4.7% | 27% | +128% |
| 10-20% | eksploracja | 1 ⚠️ niewiarygodny | -29.1% | -29.1% | 0% | +1% |
| 10-20% | TEST | 0 | — | — | — | — |
| 20-30% | eksploracja | 0 | — | — | — | — |
| 20-30% | TEST | 0 | — | — | — | — |
| 30-40% | eksploracja | 0 | — | — | — | — |
| 30-40% | TEST | 0 | — | — | — | — |
| 40%+ | eksploracja | 0 | — | — | — | — |
| 40%+ | TEST | 0 | — | — | — | — |
| **wszystkie (baseline)** | eksploracja | 23 ⚠️ niewiarygodny | +0.1% | -4.8% | 26% | +90% |
| **wszystkie (baseline)** | TEST | 11 ⚠️ niewiarygodny | +8.9% | +4.7% | 27% | +128% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | eksploracja | 23 ⚠️ niewiarygodny | +0.1% | -4.8% | 26% | +90% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | TEST | 11 ⚠️ niewiarygodny | +8.9% | +4.7% | 27% | +128% |

Kształt zależności (wynik obecnego wyjścia ~ cecha):
- eksploracja (N 23 ⚠️ niewiarygodny): Spearman -0.04; parabola c = -38.42e-4, wierzchołek 2%; średnie kubełków (N >= 10): 0-10% +1.4%, 10-20% —, 20-30% —, 30-40% —, 40%+ — -> **brak związku**
- TEST (N 11 ⚠️ niewiarygodny): Spearman +0.10; parabola c = -8464.99e-4, wierzchołek 1%; średnie kubełków (N >= 10): 0-10% +8.9%, 10-20% —, 20-30% —, 30-40% —, 40%+ — -> **brak związku**

**Kształt: brak związku.**

**Flaga wspólnego zasilającego w bundlu (migracje + 30 min):**

| grupa | zbiór | N | śr. wynik (obecne) | śr. wynik (S6) | % rugów |
|---|---|---|---|---|---|
| bundle >= 10%, wspólny zasilający | eksploracja | 88 | -12.0% | -14.6% | 25% |
| bundle >= 10%, bez wspólnego | eksploracja | 98 | -14.5% | -10.9% | 22% |
| bundle < 10% | eksploracja | 175 | -17.9% | -16.7% | 24% |
| bundle >= 10%, wspólny zasilający | TEST | 23 ⚠️ niewiarygodny | +9.2% | +6.1% | 22% |
| bundle >= 10%, bez wspólnego | TEST | 36 | -11.0% | -6.6% | 14% |
| bundle < 10% | TEST | 97 | -18.5% | -16.3% | 25% |

## 9. Copy coiny (kopie tickera / nazwy / grafiki)

METADANE - co jest w danych:
  * nazwa i ticker: TAK, za darmo - zbieracz (data/stream.db, tabela mints, od 04.10 10:23) i bot (data/bot.db, tabela
    launches z PumpPortal, od 01.10 20:23; oba z nocnymi przerwami, gdy komputer jest wyłączony);
  * grafika: NIE ma w danych - pobrana z Helius DAS (getAssetBatch: 10 kredytów za zapytanie do 1000 tokenów, czyli
    ~1 300 kredytów za wszystkie ~130 tys. startów). Adres IPFS zawiera CID = hash treści pliku, więc ten sam CID = ten
    sam plik graficzny (nie trzeba pobierać obrazków); grafiki z CDN Axiom mają w nazwie mint tokena, z którego
    skopiowano grafikę (funkcja "kopiuj token" w terminalu).
DEFINICJE (ustalone przed patrzeniem na wyniki):
  kopia = wcześniejszy token z tym samym znormalizowanym tickerem LUB nazwą (małe litery, tylko litery i cyfry - bez
          spacji, emoji i znaków) wystartowany w ciągu 60 h przed startem tokena. 60 h zamiast 7 dni: tyle historii mamy
          dla KAŻDEGO ocenianego tokena (dane od 01.10 20:23) - jedno okno dla wszystkich, żeby eksploracja i test były
          porównywalne. Nocne przerwy w danych gubią część oryginałów -> część kopii trafia do "oryginałów" (to zaciera
          różnice, nie tworzy fałszywych).
  (c) oryginał          - brak wcześniejszego tokena z tym tickerem/nazwą w oknie,
  (a) kopia AKTYWNEGO   - któryś wcześniejszy token w chwili startu kopii: zmigrował w ostatnich 24 h ALBO miał >= 10 SOL
                          obrotu na krzywej w ostatnich 24 h ALBO bot widział go z obrotem 24 h >= $50k (DexScreener),
  (b) kopia MARTWEGO    - pozostałe kopie.
  numer kopii = 1 + liczba wcześniejszych tokenów z tym tickerem/nazwą w oknie (1 = oryginał).
  ta sama grafika = ten sam CID/adres grafiki co wcześniejszy token w oknie (niezależnie od nazwy).


W danych: 149,212 startów z nazwą/tickerem (zbieracz + bot); grafika pobrana dla 146,075 (z adresem grafiki 145,045). Średnie pokrycie okna 60 h danymi o startach: migracje 54%, wejścia bota 55% (reszta = noce bez danych).

| zbiór | tokenów | oryginały (c) | kopie aktywnego (a) | kopie martwego (b) | mediana numeru kopii | ta sama grafika co wcześniejszy | grafika z CDN z mintem innego tokena |
|---|---|---|---|---|---|---|---|
| migracje + 30 min | 617 | 18% | 54% | 28% | 10 | 34% | 13% |
| wejścia bota (tokeny z pełnym oknem) | 110 | 25% | 34% | 42% | 7 | 16% | 13% |

**Oryginały vs kopie - migracje + 30 min** (N 617):

| kategoria | zbiór | N | śr. wynik (obecne wyjście) | śr. wynik (S6) | % rugów (e) | mediana max zysku 6 h |
|---|---|---|---|---|---|---|
| c oryginał | eksploracja | 84 | -13.2% | -13.0% | 17% | +4% |
| c oryginał | TEST | 30 | -7.4% | -4.3% | 17% | +37% |
| a kopia aktywnego | eksploracja | 232 | -17.7% | -17.0% | 25% | +13% |
| a kopia aktywnego | TEST | 100 | -21.8% | -18.8% | 27% | +24% |
| b kopia martwego | eksploracja | 115 | -14.0% | -13.6% | 23% | +11% |
| b kopia martwego | TEST | 56 | -9.4% | -8.9% | 21% | +10% |
| **wszystkie (baseline)** | eksploracja | 431 | -15.8% | -15.3% | 23% | +10% |
| **wszystkie (baseline)** | TEST | 186 | -15.7% | -13.5% | 24% | +22% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | eksploracja | 51 | -10.6% | -8.6% | 43% | +76% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | TEST | 23 ⚠️ niewiarygodny | +7.4% | +6.3% | 17% | +108% |

Odporność na dziury w danych: tylko tokeny z pełnymi danymi o startach w 6 h przed startem (kopia zwykle pojawia się w mediana < 1 h po poprzedniku) - N 346:

| kategoria | zbiór | N | śr. wynik (obecne wyjście) | % rugów |
|---|---|---|---|---|
| c oryginał | eksploracja | 45 | -13.9% | 18% |
| c oryginał | TEST | 13 ⚠️ niewiarygodny | -10.1% | 15% |
| a kopia aktywnego | eksploracja | 128 | -12.8% | 20% |
| a kopia aktywnego | TEST | 63 | -27.3% | 30% |
| b kopia martwego | eksploracja | 69 | -14.6% | 23% |
| b kopia martwego | TEST | 28 ⚠️ niewiarygodny | -8.1% | 18% |

**Numer kopii - migracje + 30 min:**

| numer kopii | zbiór | N | śr. wynik | % rugów |
|---|---|---|---|---|
| 1 (oryginał) | eksploracja | 84 | -13.2% | 17% |
| 1 (oryginał) | TEST | 30 | -7.4% | 17% |
| 2 | eksploracja | 35 | -13.1% | 14% |
| 2 | TEST | 24 ⚠️ niewiarygodny | -2.6% | 17% |
| 3 | eksploracja | 26 ⚠️ niewiarygodny | +11.6% | 15% |
| 3 | TEST | 14 ⚠️ niewiarygodny | -14.7% | 29% |
| 4-9 | eksploracja | 108 | -23.8% | 29% |
| 4-9 | TEST | 43 | -15.7% | 23% |
| 10+ | eksploracja | 178 | -16.8% | 26% |
| 10+ | TEST | 75 | -23.5% | 28% |

**Grafika - migracje + 30 min:**

| grupa | zbiór | N | śr. wynik | % rugów |
|---|---|---|---|---|
| ta sama grafika co wcześniejszy token | eksploracja | 128 | -21.1% | 27% |
| grafika z CDN z mintem innego tokena | eksploracja | 56 | -16.3% | 30% |
| grafika własna | eksploracja | 262 | -14.1% | 23% |
| ta sama grafika co wcześniejszy token | TEST | 74 | -26.9% | 28% |
| grafika z CDN z mintem innego tokena | TEST | 25 ⚠️ niewiarygodny | -15.0% | 4% |
| grafika własna | TEST | 96 | -8.8% | 23% |

**Filtry (hipoteza: kopie wypadają gorzej i warto ich nie kupować):**

| filtr / hipoteza | eksploracja: filtr vs baseline (N) | TEST: filtr vs baseline (N; p losowe) | random_eligible oczekiwany, TEST (N) | werdykt |
|---|---|---|---|---|
| copy: nie kupuj kopii AKTYWNEGO (a) (obecne wyjście) | -13.7% vs -15.8% (N 199/431) | -8.7% vs -15.7% (N 86/186; p 0.02) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj kopii MARTWEGO (b) (obecne wyjście) | -16.5% vs -15.8% (N 316/431) | -18.5% vs -15.7% (N 130/186; p 0.90) | +7.4% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| copy: tylko oryginały (c) (obecne wyjście) | -13.2% vs -15.8% (N 84/431) | -7.4% vs -15.7% (N 30/186; p 0.13) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj tej samej grafiki (obecne wyjście) | -13.6% vs -15.8% (N 273/431) | -8.5% vs -15.7% (N 101/186; p 0.01) | +7.4% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj kopii AKTYWNEGO (a) (S6) | -13.4% vs -15.3% (N 199/431) | -7.3% vs -13.5% (N 86/186; p 0.02) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj kopii MARTWEGO (b) (S6) | -15.9% vs -15.3% (N 316/431) | -15.5% vs -13.5% (N 130/186; p 0.85) | +6.3% (N 23 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| copy: tylko oryginały (c) (S6) | -13.0% vs -15.3% (N 84/431) | -4.3% vs -13.5% (N 30/186; p 0.08) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| copy: nie kupuj tej samej grafiki (S6) | -13.1% vs -15.3% (N 273/431) | -7.8% vs -13.5% (N 101/186; p 0.02) | +6.3% (N 23 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |

**Oryginały vs kopie - wejścia bota** (N 110):

| kategoria | zbiór | N | śr. wynik (obecne wyjście) | śr. wynik (S6) | % rugów (e) | mediana max zysku 6 h |
|---|---|---|---|---|---|---|
| c oryginał | eksploracja | 19 ⚠️ niewiarygodny | -4.8% | -1.2% | 32% | +86% |
| c oryginał | TEST | 8 ⚠️ niewiarygodny | +16.0% | +14.9% | 12% | +73% |
| a kopia aktywnego | eksploracja | 29 ⚠️ niewiarygodny | -15.8% | -17.9% | 52% | +22% |
| a kopia aktywnego | TEST | 8 ⚠️ niewiarygodny | -25.1% | -14.6% | 62% | +49% |
| b kopia martwego | eksploracja | 29 ⚠️ niewiarygodny | -10.5% | -14.1% | 48% | +59% |
| b kopia martwego | TEST | 17 ⚠️ niewiarygodny | +0.3% | -4.4% | 24% | +98% |
| **wszystkie (baseline)** | eksploracja | 77 | -11.1% | -12.4% | 45% | +52% |
| **wszystkie (baseline)** | TEST | 33 | -2.0% | -2.2% | 30% | +69% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | eksploracja | 77 | -11.1% | -12.4% | 45% | +52% |
| **random_eligible oczekiwany** (tokeny po filtrach bota) | TEST | 33 | -2.0% | -2.2% | 30% | +69% |

Odporność na dziury w danych: tylko tokeny z pełnymi danymi o startach w 6 h przed startem (kopia zwykle pojawia się w mediana < 1 h po poprzedniku) - N 72:

| kategoria | zbiór | N | śr. wynik (obecne wyjście) | % rugów |
|---|---|---|---|---|
| c oryginał | eksploracja | 13 ⚠️ niewiarygodny | -10.5% | 38% |
| c oryginał | TEST | 5 ⚠️ niewiarygodny | -1.1% | 20% |
| a kopia aktywnego | eksploracja | 17 ⚠️ niewiarygodny | -23.7% | 59% |
| a kopia aktywnego | TEST | 7 ⚠️ niewiarygodny | -24.5% | 57% |
| b kopia martwego | eksploracja | 20 ⚠️ niewiarygodny | -17.1% | 50% |
| b kopia martwego | TEST | 10 ⚠️ niewiarygodny | +3.8% | 30% |

**Numer kopii - wejścia bota:**

| numer kopii | zbiór | N | śr. wynik | % rugów |
|---|---|---|---|---|
| 1 (oryginał) | eksploracja | 19 ⚠️ niewiarygodny | -4.8% | 32% |
| 1 (oryginał) | TEST | 8 ⚠️ niewiarygodny | +16.0% | 12% |
| 2 | eksploracja | 8 ⚠️ niewiarygodny | +13.8% | 38% |
| 2 | TEST | 6 ⚠️ niewiarygodny | +19.5% | 17% |
| 3 | eksploracja | 6 ⚠️ niewiarygodny | -10.0% | 50% |
| 3 | TEST | 1 ⚠️ niewiarygodny | +24.4% | 0% |
| 4-9 | eksploracja | 24 ⚠️ niewiarygodny | -18.4% | 58% |
| 4-9 | TEST | 8 ⚠️ niewiarygodny | -17.3% | 25% |
| 10+ | eksploracja | 20 ⚠️ niewiarygodny | -18.5% | 45% |
| 10+ | TEST | 10 ⚠️ niewiarygodny | -19.8% | 60% |

**Grafika - wejścia bota:**

| grupa | zbiór | N | śr. wynik | % rugów |
|---|---|---|---|---|
| ta sama grafika co wcześniejszy token | eksploracja | 13 ⚠️ niewiarygodny | -21.2% | 46% |
| grafika z CDN z mintem innego tokena | eksploracja | 11 ⚠️ niewiarygodny | -10.0% | 45% |
| grafika własna | eksploracja | 56 | -9.6% | 46% |
| ta sama grafika co wcześniejszy token | TEST | 4 ⚠️ niewiarygodny | -38.7% | 75% |
| grafika z CDN z mintem innego tokena | TEST | 3 ⚠️ niewiarygodny | -0.8% | 33% |
| grafika własna | TEST | 23 ⚠️ niewiarygodny | +12.1% | 22% |

## 10. Model wyniku pozycji (zamiast P(rug))

Zbiór: migracje + 30 min (jak części 1, 9, 10), tokeny z policzonym składem pierwszych kupujących i bundlami.
Cel (klasyfikacja): y = 1, gdy wynik wejścia po kosztach (obecne wyjście bota) > 0 - regresja logistyczna.
Dla porównania regresja liniowa na samym wyniku (te same cechy).
Cechy - max 6, dobór WYŁĄCZNIE na eksploracji:
  4 stałe z części 1c: frac_insider, frac_shared_funder, young_insider_dump, frac_sniper;
  + do 2 z bundli i copy coinów, jeśli pojedyncza cecha ma na eksploracji AUC dla "wynik > 0" poza 0,45-0,55
    (kandydaci: bundle_start_pct, bundle_held_pct, b_shared, is_copy, copy_active, log numeru kopii, img_copy).
Cechy standaryzowane średnią i odchyleniem z eksploracji; brak wartości = średnia z eksploracji.
Filtr: wchodź, gdy score >= mediana score na eksploracji (połowa tokenów). TEST liczony raz, bez strojenia.


Tokenów: **511** (eksploracja 357, TEST 154); wynik > 0 na eksploracji: 22%, na teście 31%.

**Pojedyncze cechy - AUC dla "wynik > 0" (dobór na eksploracji; TEST tylko do wglądu):**

| cecha | N eksploracja | AUC eksploracja | AUC TEST | w modelu? |
|---|---|---|---|---|
| frac_insider | 357 | 0.557 | 0.602 | stała (część 1c) |
| frac_shared_funder | 357 | 0.520 | 0.515 | stała (część 1c) |
| young_insider_dump | 357 | 0.477 | 0.491 | stała (część 1c) |
| frac_sniper | 357 | 0.440 | 0.397 | stała (część 1c) |
| bundle_start_pct | 357 | 0.387 | 0.501 | kandydat |
| bundle_held_pct | 255 | 0.512 | 0.560 | — |
| b_shared | 357 | 0.475 | 0.564 | — |
| is_copy | 357 | 0.509 | 0.506 | — |
| copy_active | 357 | 0.492 | 0.516 | — |
| log_copy_n | 357 | 0.472 | 0.445 | — |
| img_copy | 357 | 0.487 | 0.450 | — |

Cechy modelu (5): frac_insider, frac_shared_funder, young_insider_dump, frac_sniper, bundle_start_pct.

**Modele (współczynniki na cechach standaryzowanych; AUC dla wynik > 0):**

| model | współczynniki | AUC eksploracja | AUC TEST |
|---|---|---|---|
| logistyczna P(wynik > 0) | frac_insider +0.19, frac_shared_funder +0.34, young_insider_dump +0.03, frac_sniper +0.06, bundle_start_pct -0.55 | 0.654 | **0.556** |
| liniowa: przewidywany wynik | frac_insider -0.04, frac_shared_funder +0.03, young_insider_dump -0.00, frac_sniper -0.00, bundle_start_pct +0.01 | 0.455 | **0.443** |

**Filtr z modelu (próg = mediana score na eksploracji):**

| filtr / hipoteza | eksploracja: filtr vs baseline (N) | TEST: filtr vs baseline (N; p losowe) | random_eligible oczekiwany, TEST (N) | werdykt |
|---|---|---|---|---|
| model wyniku (logistyczna): score >= mediana eksploracji (obecne wyjście) | -16.2% vs -15.5% (N 179/357) | -15.9% vs -12.6% (N 103/154; p 0.90) | +9.2% (N 20 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| model wyniku (logistyczna): score >= mediana eksploracji (S6) | -16.9% vs -14.6% (N 179/357) | -15.3% vs -10.9% (N 103/154; p 0.97) | +8.3% (N 20 ⚠️ niewiarygodny) | odrzucone już na eksploracji |
| model wyniku (liniowa): score >= mediana eksploracji (obecne wyjście) | -11.2% vs -15.5% (N 179/357) | -9.9% vs -12.6% (N 67/154; p 0.26) | +9.2% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |
| model wyniku (liniowa): score >= mediana eksploracji (S6) | -10.8% vs -14.6% (N 179/357) | -6.9% vs -10.9% (N 67/154; p 0.14) | +8.3% (N 20 ⚠️ niewiarygodny) | lepsze od baseline, ale NIE bije random_eligible -> bez wartości |

**W dolarach (stawka $50, model logistyczny, obecne wyjście):**

| zbiór | N wszystkich | $ wszystkie | N wpuszczonych | $ wpuszczone | śr. wpuszczone | % rugów wpuszczone / wszystkie |
|---|---|---|---|---|---|---|
| eksploracja | 357 | -2,771 | 179 | -1,451 | -16.2% | 26% / 24% |
| TEST | 154 | -969 | 103 | -817 | -15.9% | 25% / 22% |

## 11. Portfele na żywo - kryteria oceny ustalone 7.10.2026 12:20, PRZED pierwszą pozycją

Portfele uruchomione 7.10.2026 12:16 (każdy zmienia JEDNĄ rzecz względem safety_only, te same wejścia i wyjścia poza nią):

| portfel | zmiana | hipoteza |
|---|---|---|
| safety_fast | stop z odczytu ceny puli co 2 s w osobnym wątku (fastexit.py); reszta wyjść jak safety_only | mniejsza strata na stopach: symulacja +2,1 pp na pozycję (część 0) |
| safety_bundle30 | wejście tylko, gdy bundle startu >= 30% podaży (launchcheck.py) | lepszy wynik na wejście (część 8: TEST -1,2% vs -12,7%) |
| safety_nocopy | bez kopii AKTYWNEGO tokena i bez skopiowanej grafiki | lepszy wynik na wejście (część 9: TEST -8,7% vs -15,7%) |

**Zasady (nie zmieniamy ich po zobaczeniu wyników):**
1. Okno: od 7.10.2026 12:16. Liczą się pozycje ZAMKNIĘTE, bez odtworzeń przerwy (`przerwa_*`) i unieważnionych. Wynik pozycji
   = zrealizowane / koszt - 1 (netto, koszty paper). Zmiana reguł któregoś z tych portfeli = nowe okno i licznik od zera.
2. Ocena dopiero przy **>= 100 zamkniętych pozycjach** portfela (wcześniej raport pokazuje tylko stan, bez wniosków).
3. **safety_fast - porównanie w parach z safety_only**: para = ta sama moneta, wejście obu portfeli w odstępie <= 10 min.
   Miara = średnia różnica wyniku w parach (pp stawki) + 95% przedział ufności (bootstrap 2000 losowań par, ziarno 1).
   Werdykt LEPSZY, gdy dolna granica CI > 0; GORSZY, gdy górna < 0; inaczej NIEROZSTRZYGNIĘTY.
4. **safety_bundle30 i safety_nocopy - filtry**: w parach z safety_only te same wejścia mają te same wyjścia (różnica ~0),
   więc filtr mierzymy na pozycjach safety_only z tego samego okna: grupa PRZEPUSZCZONA (filtr dał sygnał przy tej samej
   decyzji) vs ODRZUCONA (brak sygnału; dla bundle30 osobno "brak danych o starcie"). Miara = różnica średnich
   (przepuszczone - odrzucone) + 95% CI (bootstrap niezależnych prób). Werdykt LEPSZY, gdy dolna granica CI > 0, obie
   grupy >= 30 i portfel filtra ma >= 100 pozycji. Pomocniczo: średnia portfela filtra vs safety_only w tym samym oknie.
5. **random_eligible**: przy każdym werdykcie średnia random_eligible w tym samym oknie (+ CI) i różnica do portfela;
   portfel, który nie bije random_eligible (CI różnicy obejmuje 0 albo < 0), opisujemy jako "nie lepszy od losowego".
6. Dodatkowo (bez wpływu na werdykt): suma $, max obsunięcie, % pozycji zamkniętych stopem; dla safety_fast liczba
   wyjść stop_fast i czas od ostatniego odczytu nad stopem (kv `fast_stop_events`).
Liczy to `python -m analizy.live_eval` (sekcja niżej, aktualizowana przy każdym `run_all`).


**Stan na 07.10.2026 12:20** (okno od 7.10 12:16): safety_only 0 pozycji, random_eligible 0.

| portfel | pozycji | śr. wynik | $ | miara główna (kryteria 3-4) | werdykt |
|---|---|---|---|---|---|
| safety_fast | 0 | — | +0 | pary z safety_only: 0, średnia różnica — (CI +nan..+nan pp) | za wcześnie (próg nie osiągnięty) |
| safety_bundle30 | 0 | — | +0 | safety_only przepuszczone — (N 0) vs odrzucone — (N 0), brak danych 0; różnica CI +nan..+nan pp | za wcześnie (próg nie osiągnięty) |
| safety_nocopy | 0 | — | +0 | safety_only przepuszczone — (N 0) vs odrzucone — (N 0), brak danych 0; różnica CI +nan..+nan pp | za wcześnie (próg nie osiągnięty) |

**Porównanie z random_eligible (kryterium 5):**

| portfel | śr. wynik | random_eligible | CI różnicy | ocena |
|---|---|---|---|---|
| safety_fast | — (N 0) | — (N 0) | +nan..+nan pp | za wcześnie |
| safety_bundle30 | — (N 0) | — (N 0) | +nan..+nan pp | za wcześnie |
| safety_nocopy | — (N 0) | — (N 0) | +nan..+nan pp | za wcześnie |