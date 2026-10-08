# Memecoin Bot – badanie, czy na memecoinach Solany da się wygrać

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
