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

### random_fast_s6 - kryteria ustalone 7.10.2026 ~14:40, PRZED wdrożeniem i pierwszą pozycją

Portfel: wejścia jak random_eligible (ten sam hash mintu - te same tokeny), szybki stop z odczytu puli co 2 s
(fastexit.py) i wyjście S6 (1/3 przy +20%, stop na wejściu, dalej 1/3 @+100%, reszta @+300%, trailing 20%).
1. Okno: od pierwszej pozycji portfela. Pozycje zamknięte, bez `przerwa_*` i unieważnionych; wynik = zrealizowane / koszt - 1.
2. **Miara główna - pary z random_eligible**: ta sama moneta, wejścia w odstępie <= 10 min. Średnia różnica wyniku w parach
   + 95% CI (bootstrap 2000, ziarno 1). Ocena przy **>= 100 parach**: LEPSZY, gdy dolna granica CI > 0; GORSZY, gdy górna < 0;
   inaczej nierozstrzygnięty. (random_eligible otwiera ~10-15 pozycji na dobę pracy bota -> ok. 8-10 dni ciągłej pracy.)
3. **Wynik bezwzględny**: średni wynik portfela z 95% CI. "Na plusie po kosztach" tylko, gdy dolna granica CI > 0 - dopiero
   wtedy wracamy do tematu wielkości pozycji (Kelly itp.).
4. Portfel zmienia DWIE rzeczy naraz, więc rozbicie efektu bierzemy z istniejących par (informacyjnie, bez wpływu na werdykt):
   safety_s6 vs safety_only = efekt S6, safety_fast vs safety_only = efekt szybkiego stopu.
5. Reguł portfela nie zmieniamy w trakcie (zmiana = nowe okno). Wcześniejsza ocena niż przy 100 parach - tylko stan, bez wniosków.
