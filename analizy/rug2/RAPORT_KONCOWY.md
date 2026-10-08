# rug2 - raport końcowy (7.10.2026)

**Pytanie:** czy NOWE źródła sygnału poprawiają wynik pozycji po kosztach przy wyborze tokenów (nie "czy rug").
**Zasady:** chwila T = migracja + 30 min, cechy tylko z danych sprzed T (testy pytest: analizy/rug2/tests), wynik po
kosztach z symulatora bota (obecne wyjście; S6 jako drugi wariant), etykieta (e) pomocniczo, podział czasowy 70/30,
N przy każdym wyniku, porównanie z baseline i z random_eligible. Kryterium odpuszczenia (użytkownika): żaden pomysł nie daje
na teście >= 2 pp ponad random_eligible przy N >= 30 -> wybór tokenów w tej niszy nie ma przewagi z tych danych.
**Dane:** 617 migracji żywych w T (04-06.10; eksploracja 431, TEST 186). Baseline: -15,8% / -15,7%; random_eligible
oczekiwany (tokeny po filtrach bota): -5,0% w całej puli (N 74), +7,4% w oknie testu (N 23 - niewiarygodny).
**Koszt:** Helius 1 293 kredyty (tylko pilot a); reszta lokalnie z cache.

## Werdykty

| pomysł | co sprawdziliśmy | najważniejszy wynik | werdykt |
|---|---|---|---|
| a) historia twórcy (lokalnie) | liczba wcześniejszych startów, odstępy, migracje i obrót poprzednich coinów (do T) | pokrycie 21%; twórcy z historią minimalnie gorsi w obu połowach (AUC 0,46 / 0,44); najlepsza reguła na teście +1,2 pp vs baseline, p 0,22 | niejasne -> nie działa |
| a) pilot Helius (100 twórców) | pełna historia transakcji twórcy (do 500 tx), starty pump.fun, flaga migracji krzywej | pełna historia podnosi pokrycie tylko z 14% do 18% (twórcy używają nowych portfeli); bez historii -14,1% (N 76), z historią -18..-32% (N 7-12) | **nie działa** (kryterium z PILOT_A.md) |
| b) graf zasilania K = 1 | wspólny zasilający pierwszych kupujących / z twórcą, czy źródła zasilały wcześniejsze tokeny i ich wyniki (okno 6 h zamknięte przed T) | najlepsza reguła z eksploracji (-10,6% vs -15,8%) na teście gorsza od baseline (-21,3% vs -15,7%, N 57) | **nie działa** |
| b) K = 2, 3 | to samo do 3 hopów, bez propagacji przez huby | przodek spoza hubów tylko u 6% / 5% kupujących; hop 2 dodał powiązania w 5/617 tokenów, hop 3 w 0 - sygnał nie rośnie z hopami (56% pierwszych kupujących to boty >= 3000 tx bez ustalonego źródła) | niejasne - za małe pokrycie |
| c) zaufani twórcy | trusted_devs.yaml (ręczna lista) + "sprawdzony w T" (>= 2 wcześniejsze tokeny z wynikiem > 0) | 1 propozycja z danych; pokrycie cechy point-in-time 0% | niejasne - za małe pokrycie |
| d) ślepy test wizualny | 195 ocen wykresów od startu do T (bez nazwy), "kupić / nie" | kupić -14,0% (N 35) vs nie -14,9% vs random_eligible -5,0%; "kupić" częściej rugują (AUC 0,58-0,66) | **nie działa** |
| d2) wzorce wykresu użytkownika | prosta linia w górę, schodki, zygzak, spadek-potem-pompa jako cechy (progi z opisu) | prosta i schodki gorsze w obu połowach (rug 40% vs 20%), ale filtry bota już ich nie przepuszczają (2/51, 0/23); zygzak odwrotnie (lepszy) | nie działa dla bota |

## Wniosek

**Żaden pomysł nie spełnił kryterium (>= 2 pp ponad random_eligible na teście przy N >= 30). Wybór tokenów w tej niszy
nie ma przewagi z tych danych** - ani z nowych źródeł (historia twórcy, graf zasilania, zaufani twórcy, oko człowieka,
wzorce wykresu), ani z wcześniej sprawdzonych (skład pierwszych kupujących, smart money, cechy krzywej, Gemini, modele
logistyczne: AUC 0,52-0,57; bundle >= 30% i kopie aktywnego tokena bijały baseline, ale nie random_eligible).
Jedyny powtarzalny "filtr wyboru" w danych to **twarde filtry bota** (tokeny po nich: -9..-11% vs -16% wszystkich na
eksploracji) - i one już działają we wszystkich portfelach; nowe cechy dublują to, co filtry już odsiewają.

Zastrzeżenia: dane z ~3 dni (z nocnymi przerwami), punkt odniesienia random_eligible w oknie testu ma N 23; "brak przewagi"
dotyczy tych źródeł i tej skali danych, nie wszystkich możliwych.

## Co z tego wynika dla projektu
- Dalsza praca nad WYBOREM tokenów z tych źródeł - zamknięta (moduł rug2 zostaje jako narzędzie, bez rozwijania cech).
- Wynik zależy od WYJŚCIA i kosztów: S6 i szybki stop poprawiały wynik w danych (część 4: +1..+3 pp; część 0: +2,1 pp
  na pozycję) - testowane na żywo (safety_s6, safety_fast) wg KRYTERIA_NA_ZYWO.md.
- Propozycja: portfel **random_fast_s6** (wejścia random_eligible + szybki stop + S6) - kryteria oceny zapisane w
  KRYTERIA_NA_ZYWO.md przed wdrożeniem; wdrożenie po zgodzie użytkownika.
