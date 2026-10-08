# Pilot a) - pełna historia twórcy z Heliusa (kryterium ustalone 7.10.2026 PRZED pobraniem)

**Próbka:** 100 losowych twórców (ziarno 20261007) spośród 589 twórców 617 migracji zbioru rug2 (T = migracja + 30 min).

**Pobranie (szacunek 2,5-4,5 tys. kredytów):** dla każdego twórcy `getTransactionsForAddress` (pełne transakcje,
10 kredytów / 100) - najwyżej 500 ostatnich transakcji sprzed startu tokena; twórcy "aktywni" (>= 3000 transakcji, 10 ze
100) bez pobierania - oznaczeni jako seryjni. Start coina = transakcja z instrukcją Create programu pump.fun, w której
konto krzywej (PDA "bonding-curve") trzyma podaż nowego mintu. Czy wcześniejszy coin zmigrował: flaga `complete` konta
krzywej (`getMultipleAccounts`, 1 kredyt / 100) - tylko dla coinów utworzonych >= 24 h przed T (stan teraz = stan w T;
młodsze: z danych lokalnych, inaczej "nieznany").

**Kryterium (jedno, z góry):** tokeny, których twórca MA historię (>= 1 wcześniejszy start w pełnej historii), dzielimy na
(H1) >= 1 wcześniejszy coin zmigrował i (H2) żaden nie zmigrował. Pomysł **działa**, jeśli któraś z grup H1 / H2 / "bez
historii" przy N >= 30 ma średni wynik pozycji po kosztach (obecne wyjście) >= oczekiwany random_eligible + 2 pp, gdzie
random_eligible = średnia tokenów po filtrach bota w CAŁEJ puli 617 migracji (-5,0%, N 74) - czyli >= -3,0%.
W przeciwnym razie werdykt **nie działa** (także gdy żadna grupa nie ma N >= 30). S6 i etykieta (e) tylko pomocniczo.
Dodatkowo raportujemy pokrycie: ile tokenów ma twórcę z historią wg Heliusa vs lokalnie (21%).


## Pilot a) - pełna historia twórcy (07.10.2026 14:33)

Próbka: 100 twórców, 105 tokenów. Kredyty Helius: ~1291. Pobranie: ok 86, ucięte do 500 tx 7, aktywni 12.

**Pokrycie historii:** wg Heliusa 18% tokenów (z pobraną historią) ma twórcę z >= 1 wcześniejszym startem; lokalnie (te same tokeny) 14%.

| grupa | N | wynik (obecne wyjście) | S6 | rug (e) | vs próg random_eligible + 2 pp |
|---|---|---|---|---|---|
| bez historii | 76 | -14.1% | -14.2% | 20% | poniżej progu |
| H2: historia, żaden nie zmigrował | 7 ⚠️ niewiarygodny | -18.2% | -16.1% | 14% | N < 30 |
| H1: historia, >= 1 zmigrował | 10 ⚠️ niewiarygodny | -31.5% | -20.6% | 40% | N < 30 |
| aktywny (seryjny, bez pobrania) | 12 ⚠️ niewiarygodny | -24.6% | -22.1% | 25% | N < 30 |

Próg: random_eligible (cała pula, N 74) -5.0% + 2 pp = -3.0%. Wszystkie tokeny próbki: -17.2%.

**Werdykt pilota a): nie działa.**
