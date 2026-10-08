# Memecoin Bot – badanie, czy na memecoinach Solany da się wygrać

> ⚠️ **Ostrzeżenie.** Każda strategia, którą tu sprawdziliśmy, wypadła **gorzej niż rzut monetą**. Rzut monetą
> o równą stawkę ma wartość oczekiwaną zero. Każdy nasz wariant – filtry, modele, ocena wykresów, kopiowanie traderów,
> reguły skutecznych botów – miał po kosztach wartość oczekiwaną **ujemną**, także w teście poza próbą.

**Krótko:** przez kilka tygodni budowaliśmy bota (tylko *paper trading*, bez prawdziwych pieniędzy) i sprawdzaliśmy na
danych z pump.fun każdy pomysł na przewagę: filtry tokenów, wyjścia, modele, ocenę wykresów okiem, kopiowanie znanych
traderów, grupy portfeli, arbitraż. **Żaden nie dał zwykłemu uczestnikowi przewagi po kosztach.** Zarabiają ci, którzy
są szybsi o ułamek sekundy, albo grupy z informacją z wnętrza. Jeśli myślisz o własnym bocie albo o kopiowaniu
„traderów z TikToka”, ten kod i te wyniki mogą oszczędzić Ci tygodnie.

*English summary: a paper-trading research bot for Solana memecoins (pump.fun). We tested 18+ ideas for an edge – token
filters, exits, ML models, human chart reading, copying famous traders, wallet clusters, cross-DEX arbitrage – with
time-split validation and out-of-sample tests. None gave a retail-speed participant a positive expectation after costs.
Profitable wallets exist and their skill persists, but it lives in the first slot (~0.4 s) or comes from inside
coordinated groups; copying them even 0.4 s later loses 5–8% per trade. Code and reports are in Polish.*

## Najważniejsze wyniki (dane 1–8.10.2026)

| pytanie | wynik |
|---|---|
| Czy jakiś portfel bota zarabia? | 18 portfeli, ~1900 pozycji, wszystkie na minusie; najmniej traci losowe wejście po twardych filtrach |
| Czy da się wybierać lepsze tokeny? | historia twórcy, graf zasilań portfeli, model ML (AUC 0,56), ślepa ocena 195 wykresów okiem – nic nie bije losowego wyboru |
| Arbitraż między DEX-ami? | 438 kwotowań: 4 zyskowne po 0,1 SOL, żadna okazja nie przetrwała 10 s; przy 0,5–2 SOL zawsze strata |
| Kopiowanie znanego tradera (Cupsey) | po 2 s opóźnienia **−26…−30% na pozycję**; za nim kupuje ~140 portfeli-naśladowców, więc to on porusza ceną |
| Kopiowanie zyskownych portfeli, test poza próbą | wybrane na 70% czasu, kopiowane na 30%: **−5,5% przy 0,4 s opóźnienia**, a one same dalej +3,5% |
| Odtworzenie reguł skutecznych botów | „gorący start”, „przetrwał start”, „21 s na nr 1”, ranking sekundowy – wszystkie −3…−17% na pozycję, także przy wejściu natychmiast |
| Wejście za grupą portfeli kupujących razem | lepiej niż losowo o ~4–5 pp, ale wciąż poniżej zera |
| „Top traderzy” z rankingów | część to jeden bot na wielu portfelach; cała flota razem traciła (−45 SOL), a „zyskowne” portfele były szczęśliwymi kawałkami |
| Jedyne, co pomaga | szybsze wyjście ze stratnej pozycji (szybki stop) – zmniejsza stratę, nie robi z gry zyskownej |

Szczegóły, liczebności i przedziały ufności: `analizy/*.md`, pełny dziennik prac: `DZIENNIK.md`.

## Dlaczego zwykły uczestnik przegrywa – jak ten rynek jest ułożony

Nie wykazaliśmy, że ktoś „ustawia” wyniki. Wykazaliśmy coś innego: sama budowa rynku sprawia, że pieniądze płyną od
wolnych i słabo poinformowanych do szybkich i dobrze poinformowanych. Każdy punkt poniżej wynika z danych w tym repo.

1. **Opłaty płacisz zawsze.** Krzywa pump.fun bierze ok. 1,25% przy kupnie i przy sprzedaży, do tego poślizg
   i priority fee. Losowe wejście i wyjście bez żadnego ruchu ceny to już ok. −3% na transakcji.
2. **Start jest rozdany, zanim go zobaczysz.** W 27% tokenów obce portfele kupują w tym samym slocie, w którym token
   powstaje (bundle). To ludzie twórcy – wchodzą po cenie, której nikt z zewnątrz nie dostanie.
3. **Wyścig wygrywa ten, kto jest szybszy o ułamek sekundy.** Najlepsze boty wchodzą 4 s po starcie i wychodzą po 2 s.
   Ich przewaga jest prawdziwa i trwała (wynik z pierwszych 70% czasu przewiduje wynik w teście), ale siedzi
   w pierwszym slocie: kopia wykonana 0,4 s później traci 5–8% na transakcji.
4. **Kupując za kimś, jesteś jego płynnością wyjścia.** Gdy kilka zręcznych portfeli kupi ten sam token, wejście 2–20 s
   po nich daje −6…−14%, a losowy token w tym samym wieku ok. 0%. Po zakupie znanego tradera cena rośnie w 2 s o ~6%,
   po jego sprzedaży spada o ~11% – kopiujący kupuje drożej i sprzedaje taniej.
5. **„Guru” sam porusza ceną.** Za znanym traderem z X (229 tys. obserwujących) kupuje sekundy po nim ~140 portfeli,
   które kupują prawie wyłącznie jego tokeny. Skok po jego wejściu w dużej części robi on sam i jego naśladowcy;
   po 30 minutach jego tokeny są tak samo w dół jak inne.
6. **Rankingi „top traderów” kłamią przez przeżywalność.** Część zyskownych portfeli to kawałki jednego bota rozbitego na
   wiele adresów. Jedna taka flota razem traciła 45 SOL, a w rankingu widać tylko jej szczęśliwe portfele.
7. **Ok. 80% świeżych migracji kończy się rugiem**, niezależnie od cech, które da się zobaczyć z zewnątrz.

## Zasady, których się trzymaliśmy

- **Tylko paper trading.** Bot nie ma trybu z prawdziwymi pieniędzmi i nie obsługuje kluczy portfeli.
- Każdy wniosek na **podziale czasowym** (70% eksploracja / 30% test, test liczony raz), N przy każdym wyniku,
  porównanie z baseline i z losowym wejściem.
- Koszty jak w rzeczywistości: opłaty pump.fun (1,25% w każdą stronę), poślizg krzywej, priority fee.
- Wpisywaliśmy też porażki – większość pomysłów to porażki i to jest główny wynik.

## Ograniczenia

- Dane z kilku dni (z nocnymi przerwami), jeden launchpad (pump.fun), darmowy RPC z dziurami w strumieniu.
- Symulacja, nie prawdziwe transakcje – prawdziwe wykonanie byłoby raczej gorsze.
- „Brak przewagi” dotyczy sprawdzonych źródeł i tej skali danych, nie wszystkich możliwych.
- Adresy prywatnych portfeli zastąpione etykietami (Bot A, Trader B…). Opisy zachowań portfeli to wzorce statystyczne,
  nie zarzuty wobec kogokolwiek.
- **To nie jest porada inwestycyjna.**

## Co w takim razie zarabia – i pod jakim warunkiem

W danych są portfele, które zarabiają w sposób powtarzalny. Każdy z nich spełnia warunek, którego zwykły uczestnik nie
spełnia. Liczby to średni wynik na transakcję w naszym oknie danych; koszty infrastruktury to ceny z cenników
dostawców z października 2026, do sprawdzenia przed wydaniem czegokolwiek.

| kto zarabia | ile (z naszych danych) | warunek | koszt wejścia |
|---|---|---|---|
| **Platforma, walidatorzy, dostawcy infrastruktury** | opłata od każdej transakcji, wygrywają niezależnie od wyniku graczy | być kasynem, a nie graczem | – |
| **Boty opóźnienia** (wejście w pierwszych sekundach startu, wyjście po 2–21 s) | +3,8…+5,5% na transakcję, setki transakcji dziennie | być w **tym samym slocie** co fala zakupów: strumień transakcji gRPC/Geyser, serwer blisko walidatorów, napiwki Jito, dobrze dobrany ranking startów | ok. $500–3000 miesięcznie (gRPC $49–999, dedykowany węzeł $1500–2500) + napiwki 0,001–0,1 SOL za transakcję. Uwaga: wiele takich botów przegrywa – jedna flota straciła 45 SOL |
| **Grupy z informacją z wnętrza** (wiedzą, który start „pójdzie”) | jeden taki portfel: +38% na pozycję | być w grupie, która odpala tokeny albo zna twórców | dostęp, nie pieniądze. To obszar manipulacji rynkiem – **nie polecamy i nie opisujemy, jak to robić** |
| **Influencerzy** | zarabiają na tym, że obserwujący kupują po nich | mieć tłum naśladowców, którzy dają płynność wyjścia | zasięg; zarabiają kosztem własnych obserwujących |

Wniosek: przy szybkości zwykłego człowieka albo zwykłego bota (sekundy, nie milisekundy) nie znaleźliśmy żadnej
strategii z dodatnim wynikiem. Jedyne, co poprawia wynik, to szybsze wyjście ze stratnej pozycji – zmniejsza stratę,
ale nie zamienia gry w zyskowną.

## Jak uruchomić

Python 3.10+, `pip install -r requirements.txt`. Klucze (darmowe plany) w `secrets.json` – wzór w
`secrets.example.json`; Helius i MadeOnSol są potrzebne tylko do części analiz.

```bash
python -u collector.py          # strumień pump.fun przez darmowy RPC -> data/stream.db
python -u bot.py run            # paper bot (wiele portfeli strategii) -> data/bot.db
python bot.py report            # wyniki portfeli
python -m analizy.run_all       # główne analizy -> analizy/RAPORT.md
python test_offline.py          # testy bez sieci
```

Dane (`data/`) nie są w repozytorium – zbierasz własne. Moduły w `analizy/` mają w nagłówku opis metody i polecenie.
