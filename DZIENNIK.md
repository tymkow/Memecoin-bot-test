# Memecoin Bot (Solana) - szkielet do paper tradingu

Bot sam znajduje świeże tokeny, sprawdza je pod kątem rug pulla, ocenia i **udaje** handel
(żadnych prawdziwych transakcji, żadnych kluczy/portfeli). Cały ruch idzie przez darmowe API bez rejestracji.

## Źródła danych
| Źródło | Do czego | Klucz |
|---|---|---|
| DexScreener | odkrywanie (profile, boosty), cena, płynność, wolumen, txns, wiek pary, social | brak |
| RugCheck.xyz | mint/freeze authority, LP lock, holderzy, insiderzy, flagi ryzyka, "rugged" | brak |
| Publiczny RPC Solany | zapas, gdy RugCheck nie odpowiada | brak |

## Uruchomienie
```
pip install requests
python test_offline.py                 # testy bez sieci
python bot.py analyze <MINT>           # pełna ocena jednego tokena (nic nie kupuje)
python bot.py once                     # jeden obieg
python bot.py run                      # pętla ciągła
python bot.py report                   # wyniki paper tradingu
python bot.py reset                    # nowy start z czystą bazą
```
Progi zmieniasz w `config.json` (np. `{"buy_threshold": 72, "position_pct": 0.03}`) - lista pól w `config.py`.

## Jak bot decyduje
1. **Odkrywanie** - najnowsze profile i boosty z DexScreenera (Solana), plus lista obserwowanych ("za młode", "za mało transakcji").
2. **Etap 1 (tani)** - testy rynkowe z danych DexScreenera. Twarde veto kończy sprawę bez dalszych zapytań.
3. **Etap 2** - wyszukiwanie klonów o tym samym symbolu + audyt RugCheck.
4. **Decyzja** - wynik 0-100 (kategorie: safety 45%, liquidity 20%, momentum 20%, social 10%, flow 5%) >= `buy_threshold`
   *i* brak veto => `BUY`. Veto tymczasowe (za młody, cienka płynność, spadek 5m) => `WATCH` (ponowna ocena do 90 min),
   veto stałe => `REJECT`, `rugged` => czarna lista.

### Testy (`analysis.py`)
**Rug/bezpieczeństwo:** flaga rugged, mint authority, freeze authority, podatek transferu, % zablokowanego LP w głównej puli,
koncentracja top1/top10 holderów (bez adresów puli), sieci insiderów/snajperów, saldo twórcy, liczba dostawców LP,
zmienne metadane, flagi danger/warn RugChecka, znormalizowany wynik RugChecka, zapasowy audyt z RPC.
**Płynność:** głębokość, mcap min/max, mcap/płynność, obrót 24h (wash trading), szacowany slippage dla naszej pozycji,
token kwotowany (SOL/USDC/USDT), znany DEX, krzywa pump.fun, wiek pary.
**Momentum:** spadający nóż (5m/1h), parabola (kupowanie szczytu), zdrowy trend 1h, zgodność 5m/1h, martwy kot,
presja kupna/sprzedaży, przyspieszenie/wygasanie wolumenu.
**Przepływ:** liczba transakcji, wolumen 1h, średnia wielkość transakcji, wash trading (idealne 50/50), wygasanie aktywności.
**Social:** strona/X/Telegram, grafika, płatne boosty, klony o tym samym symbolu (starsze/płynniejsze).

### Paper trading (`paper.py`)
Wejście z poślizgiem x*y=k + prowizja + priority fee; rozmiar = min(5% kapitału, 2% płynności puli, gotówka).
Wyjścia: stop loss -25%, częściowe TP (+50/+100/+300%), trailing 20% po pierwszym TP, time stop, ucieczka przy
spadku płynności o 40%, ponowny skan RugCheck co 10 min, token znika z API => zakładamy rug (wartość 0).
Limity: 5 pozycji, 40% ekspozycji, dzienny limit strat 10%, pauza po 4 stratach z rzędu.

### Dziennik (`data/bot.db`, SQLite)
`decisions` - każda decyzja z pełną listą testów (do strojenia progów i sprawdzania odrzuconych tokenów),
`positions`, `trades`, `equity`, `blacklist`.

## Pliki
`config.py` progi | `sources.py` klienci API | `analysis.py` testy i decyzja | `paper.py` symulator |
`storage.py` baza | `bot.py` pętla i CLI | `test_offline.py` testy

## Dodane w wersji 0.2
- **Jupiter (darmowe kwotowania, bez klucza):** przed kupnem bot pyta o kupno ORAZ sprzedaż tego samego tokena.
  Brak trasy sprzedaży = honeypot (czarna lista); koszt kupno+sprzedaż > 8% = veto; cena Jupitera vs DexScreener > 15% = veto.
  Fille w paper tradingu liczone z realnych kwotowań Jupitera (fallback: model x*y=k).
- **Szybszy nadzór:** pozycje sprawdzane co 10 s (`position_loop_seconds`), skan nowych co 45 s. Co 60 s próbne kwotowanie sprzedaży
  każdej pozycji: 3x brak trasy = spisanie na zero (`unsellable`), a wartość sprzedaży < 50% wartości z ceny = wyjście (`exit_gap`).
  To zastępuje websocket - łapie rug szybciej i na podstawie realnej głębokości, nie samej ceny.
- **GeckoTerminal (darmowe):** liczba holderów, gt_score, flaga honeypot, udział dewelopera, ranking trendów oraz analiza
  ostatnich 300 transakcji puli: dominacja 3 portfeli, wash-portfele, unikalni kupujący, przepływ netto, sprzedaże wielorybów,
  "smart money" (adresy z `smart_wallets` w config.json - wklej portfele, za którymi chcesz podążać).
- **Samouczenie się listy rugów:** gdy pozycja kończy jako rug (`liq_drain`, `no_data_rug`, `rug_recheck`, `unsellable`) albo token
  ma flagę rugged/honeypot, portfele twórcy/dewelopera trafiają do tabeli `bad_wallets`. Następny token tego twórcy = veto.
- **Token-2022:** permanentDelegate, nonTransferable, transferHook, domyślnie zamrożone konta.
- **Kalibracja:** bot sam dopisuje cenę i płynność każdej decyzji (także odrzuconych) po 1/6/24 h. `python bot.py calibrate`
  pokazuje, jak zachowały się kupione/pominięte/odrzucone tokeny, skuteczność każdego veto (%rug vs średni zwrot)
  i zwrot w zależności od progu `buy_threshold`. Trzeba zostawić bota na kilka dni, żeby było na czym liczyć.

## Wersja 0.3 - poprawki po pierwszych 4 h paper tradingu (12 pozycji, -7%)
Diagnoza z bazy: 9 z 12 wejść nastąpiło PO pompie +103..+219% w 1h (6 z 6 skończyło stratą, w tym rug ZYROX) albo w spadku
-12..-26%/h (3 z 3 strata). Jedyna duża wygrana (swarmdots +141%) weszła przy +28%/h. Zmiany:
- wzrost 1h: "zdrowy" tylko 5-40%, veto od +100% (było +400%); spadek 1h: veto od -10% (było -35%); sprzedający >65% transakcji = veto;
- wynik łączny nie może już kompensować słabego momentum: bramki `min_category_scores` (safety >= 70, momentum >= 55),
  wagi: momentum 35%, safety 15% (bezpieczeństwo jest przede wszystkim veto/bramką, nie punktami do kupna);
- wycena pozycji z Jupitera (cena wykonalna) zamiast ostatniej transakcji z DexScreenera: take-profity wyzwalały się na
  spike'ach, po których nie dało się sprzedać (poślizg wyjścia 11-32% wobec ceny z DexScreenera);
- błąd: token zablokowany limitem pozycji był logowany jako BUY przy każdym obiegu (37 duplikatów jednego tokena) i za każdym razem
  pełnie analizowany; teraz jeden wpis na okno cooldownu, `calibrate` liczy duplikaty raz;
- `python bot.py reset` archiwizuje starą bazę (bot_RRRRMMDD_GGMMSS.db) zamiast ją kasować.
UWAGA: progi wyciągnięto z 12 transakcji - to hipotezy dopasowane wstecz. Sprawdza je dopiero nowa porcja danych (`calibrate`).

## Wersja 0.4 - strategie jako moduły, zbiór danych, metryki (po przeglądzie specyfikacji od ChatGPT)
- **Strategie (`strategies.py`):** `hybrid`, `momentum_only`, `flow_only`, `safety_only` (grupa kontrolna: kupuje wszystko, co
  przejdzie twarde filtry) i `score_no_gates`. Każda ma własny wirtualny portfel ($1000), wszystkie widzą ten sam rynek
  i te same twarde filtry (veto blokuje każdą). `python bot.py report` porównuje je obok siebie. Nowa strategia = jedna
  funkcja `(verdict, cfg) -> bool` + wpis w `REGISTRY` i `Config.strategies`; nie trzeba ruszać reszty.
- **Zbiór danych:** każdy oceniony token (także odrzucony) zapisuje wektor ~60 cech liczbowych (`decisions.features`);
  tabela `snapshots` to szereg czasowy cen/wolumenów/transakcji obserwowanych tokenów co 60 s; `wallet_buys` to kto kupował.
- **Nowe cechy:** unikalni kupujący w oknach 30/60/180/300 s, przyspieszenie, udział nowych kupujących, stosunek
  kupno/sprzedaż (wolumen i liczba portfeli), skoordynowane zakupy w jednym bloku (wyjaśnialny sygnał, nie wyrok),
  top1/5/10/20, Gini, Nakamoto, zmiana ceny względem płynności.
- **Latencja wejścia:** po sygnale bot czeka `entry_latency_s` (8 s) i wypełnia po NOWYM kwotowaniu Jupitera; cena, która
  uciekła o więcej niż `max_slippage_pct`, to nieudana transakcja. Zapisywane: oczekiwany i faktyczny poślizg.
  Dane z pollingu mają rozdzielczość sekund, więc symulacji milisekundowych (0-5000 ms) NIE da się uczciwie zrobić.
- **Dodatkowe wyjścia (osobno włączane):** `dev_sell` (twórca sprzedał >=50% salda, domyślnie ON), `smart_money_sell`
  (po wpisaniu `smart_wallets`), `momentum_decay` (domyślnie OFF - hipoteza do przetestowania).
- **Metryki (`bot.py report`):** expectancy, mediana, profit factor, PnL bez najlepszej transakcji, max drawdown, śr. czas,
  koszty wykonania, kubełki płynności/mcap/wyniku, powody wyjścia.
- **Badania (`bot.py features`, `bot.py wallets`):** korelacja Spearmana cech z wynikiem z kontrolą "pierwsza vs druga połowa
  danych" oraz ranking portfeli kupujących. To NIE jest ML; wag nie wolno stroić na tych samych transakcjach, którymi oceniamy.
- Baza starego formatu jest migrowana automatycznie (nowe kolumny), `reset` archiwizuje.

## Wersja 0.5 - maszyna do zbierania i testowania danych (priorytet: jakość danych > złożoność strategii > ML)
- **Dwie osie zamiast jednego wyniku:** `Opportunity` (momentum, unikalni kupujący, presja kupna/sprzedaży, smart money,
  wolumen/płynność) i `Risk` (holderzy, deweloper, klastry, bundle, głębokość/pogarszanie płynności, autentyczność).
  Wejście = Opportunity >= 70 ORAZ Risk <= 20 ORAZ brak veto (+ bramka momentum >= 55). Skala 50 +/- 50*tanh(suma/60);
  progi to punkt startowy dobrany tak, by zachować dotychczasową selektywność - NIE są zoptymalizowane.
- **Wyjaśnialne odrzucenia:** każda decyzja zapisuje `explanation`, np. `Opportunity 84 | Risk 67 -> SKIP` + powody
  (za duże ryzyko: ... ryzyko - top1_holder: ...). Veto wypisane osobno (tymczasowe/trwałe).
- **Tryby:** `RESEARCH` (zbiera dane, zapisuje decyzje i sygnały, bez wirtualnych transakcji), `PAPER` (domyślny),
  `LIVE` (NIEZAIMPLEMENTOWANY - bot odmawia startu). Wybór: `python bot.py run --mode RESEARCH` lub `"mode"` w config.json.
- **PumpPortal (jedno połączenie WebSocket, darmowe, bez klucza):** `create` -> tabela `launches` (historia twórców, m.in.
  seryjni launcherzy), `migrate` (graduacja) -> token trafia do analizy, gdy DexScreener zaindeksuje parę. Strumienie
  transakcji per token są płatne w SOL - nie używamy.
- **Silnik rankingu portfeli (`wallets.py`) bez płatnego API:** każde ocenienie tokena zapisuje ~300 transakcji puli
  (`wallet_trades`). Z nich: win rate, ROI domkniętych pozycji, wynik kopiowania z opóźnieniem 20 s, czas trzymania, udział
  wczesnych wejść i tokenów o niskiej płynności, wykrywanie botów/market makerów. Do 100 najlepszych portfeli jest
  "śledzonych"; **konwergencja** (>=2 niezależnych śledzonych portfeli kupuje ten sam token w 15 min) to cecha i test okazji.
  Adaptery `WalletDataProvider`: Null (domyślny), Helius (`HELIUS_API_KEY`), szkielety GMGN/Birdeye.
- **Źródło finansowania - selektywnie:** drogie zapytania tylko, gdy w transakcjach jest podejrzany klaster (>=3 portfele
  kupujące w jednym bloku i >=20% wolumenu kupna w takich blokach); maks. 5 zapytań na token, wyniki w cache.
  UWAGA: endpoint Helius `/funded-by` wymaga płatnego planu; na darmowym bot wylicza fundatora z `/transfers`
  (niezweryfikowane na żywo - brak klucza).
- **Kubełki płynności:** dolna granica zbierania obniżona do $5k (mcap min $15k); wyniki raportowane osobno dla
  5-10k / 10-25k / 25-50k / 50-100k / 100k+ (`bot.py report`, `bot.py calibrate`) - bez zakładania z góry, że $10k ma sens.
- **Strategie:** domyślnie `hybrid`, `momentum_only`, `buyer_accel_only`, `smart_money_only` + dwie grupy kontrolne
  (`safety_only`, `random_eligible`). Wyłączanie = usuń z `"strategies"` w config.json. Tabela `signals` zapisuje, które
  strategie chciały kupić dany token, więc `bot.py calibrate` porównuje CENĘ tokenów z sygnałów każdej strategii z
  wszystkimi ocenianymi tokenami (bez wpływu naszych wyjść i kosztów) - to właściwa "grupa kontrolna".
- **Grupa kontrolna danych:** każdy oceniony token trafia do `decisions` z cechami i (po 1/6/24 h) wynikiem, także gdy
  został odrzucony; tokeny obserwowane dostają szereg czasowy w `snapshots`.
- Bez ML (zgodnie z założeniem). Raportowanie: expectancy, mediana, średnia, drawdown, profit factor, koszty (wynik
  przed/po kosztach), czas trzymania, wyniki wg kubełka płynności, per strategia.

## Wersja 0.6 - analiza techniczna jako cechy i strategie tylko-sygnałowe
Źródło pomysłu (ChatGPT) zweryfikowane: przywoływany bot "memecoin-freqtrade-bot" handluje na **Binance spot** płynnymi,
dużymi memecoinami (DOGE, SHIB, PEPE, BONK) na świecach 5 min, ma 2 gwiazdki i sam zastrzega "educational only"
bez deklaracji rentowności. Nie jest dowodem dla tokenów DEX tuż po graduacji - to inny reżim płynności.
- **`indicators.py`:** ze świec 1 min GeckoTerminal (+1 zapytanie na oceniany token, `use_ohlcv`) liczymy EMA9/21/50 i
  trend, RSI14, ATR14 (+ percentyl zmienności), VWAP (+ nachylenie), Bollinger 20/2 (szerokość, percentyl, squeeze),
  Donchian 20, MACD, z-score ceny i wolumenu, "efektywność wolumenu", wybicie/retest/nieudane wybicie.
  Wszystko trafia do `decisions.features` - **jako cechy, nie do punktacji**. Bieżąca, niezamknięta świeca jest pomijana.
- **Strategie tylko-sygnałowe** (`signal_strategies`, bez kapitału): `breakout_volume`, `breakout_retest`, `vwap_momentum`,
  `ema_trend_rsi`, `bollinger_breakout`, `vwap_reversion`. Wszystkie za tymi samymi twardymi filtrami; oceniane w
  `bot.py calibrate` po zwrocie ceny wskazanych tokenów vs grupy kontrolne. To tanie hipotezy, nie "strategie na zysk".
- Niewdrożone świadomie: stop/trailing oparty na ATR i wyjścia czasowe (zmieniają wyjścia WSZYSTKICH portfeli - do osobnej
  decyzji), RSI-dywergencja (wyjście), przełączanie reżimów zmienności (na razie tylko cecha `atr_percentile`).

## Wersja 0.7 - wybór tokenów vs wyjścia: eksperyment 2x2, MAE/MFE, archiwum świec
**Skąd zmiany (analiza 2.10.2026, 49 wejść z 30 tokenów, świece 1-min, odtworzenie zgodne z realnym wynikiem 43/46):**
- 49% wejść dochodziło do +50% w 6 h, ale 33/49 najpierw spadało do -25%. Zwycięzcy schodzili przed wzrostem w medianie
  do -26%, więc stop -25% wyrzucał połowę z nich ("zabici zwycięzcy": 13).
- Żaden z 12 wariantów wyjść nie dawał zysku na tych wejściach (od -5.5% do -11.7% na wejście), bo 27% wejść to rugi do -98%.
- Gdyby rugów nie było (wiedza z przyszłości), szeroki stop / brak stopa dawał +13% na wejście (PF 1.94), a -25% nadal tracił.
- ATR 1-min przy wejściu oddzielał rugi: >= 20% -> 8/15 rugów, < 20% -> 4/32 (to samo na ATR liczonym przez bota).
  Próg 20% wybrano PO obejrzeniu danych - to hipoteza, którą sprawdza dopiero przyszłość.

**Co dodano:**
- **Eksperyment 2x2 (osobne portfele, te same dane):** `safety_only` (wszystko czyste, stop -25%), `safety_wide`
  (stop -40%), `lowvol` (tylko ATR < 20%, stop -25%), `lowvol_wide` (ATR < 20%, stop -40%), `lowvol_catastrophic`
  (ATR < 20%, stop awaryjny -60%). Różnica safety_only/lowvol = efekt filtra, safety_only/safety_wide = efekt stopa.
  Parametry wyjść per strategia: `Config.strategy_exits` (literówka w nazwie parametru = błąd przy starcie).
- **MAE/MFE każdej pozycji** zapisywane na żywo (kolumny `mae_pct`, `mfe_pct`, `t_mae_min`, `t_mfe_min`), z tej samej
  ceny, po której działają stopy.
- **Archiwum świec:** dla każdego sygnału (także strategii tylko-sygnałowych) bot po 6 h pobiera świece 1-min
  (1 zapytanie GeckoTerminal, maks. 6 na 10 min) do tabeli `candles`.
- **`python bot.py exits`:** MFE wejść, MAE zwycięzców, "zabici zwycięzcy", odtworzenie 7 wariantów wyjść, podział wg ATR,
  źródła odkrycia i płynności, kontrola zgodności z realnym wynikiem. `--signals`: to samo dla sygnałów każdej strategii,
  także tylko-sygnałowych (dużo więcej danych niż z pozycji). To ilustracja - parametrów z tej tabeli NIE wybieramy.
- **Cechy wyboru tokenów:** `source` (graduation/profile/boost/top_boost - czy płatna promocja przyciąga zrzuty?),
  `early_buyers_sold_share` (ilu pierwszych kupujących w próbce już sprzedało). `bot.py calibrate` pokazuje wyniki wg
  źródła i wg ATR przy decyzji.
- **`mature_calm`** (tylko-sygnałowa, zamrożona): token >= 60 min życia, aktywność 5 min < 80 transakcji.
- **Przerwy w działaniu:** po >10 min przerwy (np. wyłączony komputer) otwarte pozycje są zamykane po kursie sprzed
  przerwy (`downtime_close`), zamiast wyceniać je po godzinach bez działających stopów.
- **`bot.py report`:** porównanie strategii we wspólnym oknie czasowym (nowe portfele startują później niż stare).
- Jednoczesne wyjście kilku portfeli z tego samego tokena korzysta z jednego kwotowania Jupitera (bez kolejki zapytań).

## Wersja 0.8 - reguły wykluczenia tokenów (test na przyszłych danych)
Z analizy 50 wejść (2.10.2026; bez reguł -$220, 13 rugów) - progi zamrożone, oceni je dopiero przyszłość:
| reguła: nie kupujemy, gdy… | wycięte | rugi | zyskowne | wynik reszty |
|---|---|---|---|---|
| cena pod VWAP (~100 min) | 26 | 9 | 5 | +$41 |
| >= 20% zakupów w blokach z >= 3 portfelami | 15 | 5 | 1 | -$6 |
| skok >= +30% w 5 min | 5 | 2 | 0 | -$112 |
| przyspieszenie kupujących >= 3x | 8 | 7 | 2 | -$142 |
| token młodszy niż 60 min | 15 | 7 | 3 | -$72 |
- **Tylko-sygnałowe** `skip_below_vwap`, `skip_block_buys`, `skip_spike_5m`, `skip_accel_3x`, `skip_young_60m`:
  safety_only bez jednego typu tokenów. `python bot.py exits --signals` pokazuje ich wynik z obecnymi wyjściami.
- **Portfel `strict`:** ATR < 20% + cena nad VWAP + < 20% zakupów w skoordynowanych blokach + bez skoku 5 min.
- **Porównania w kohortach** (`report`, `exits --signals`): każda grupa strategii porównywana od chwili, w której
  dołączyła, z tymi, które już działały - dodanie nowych strategii nie przesuwa okien wcześniejszych porównań.
  Moment dołączenia: `kv added:<strategia>` (stare strategie - z historii).
- `--since "RRRR-MM-DD GG:MM"` dla `exits` i `calibrate`: tylko dane od wskazanej chwili.
- Do obserwacji (bez zmian, żeby nie psuć działających porównań): punktacja daje bonus za rozproszonych holderów
  (top10 < 25%: +8), a 12 z 13 rugów miało top10 < 15% (bundlery rozkładają podaż na wiele portfeli); +10 pkt za
  przyspieszenie kupujących >= 1.5x obejmuje też skrajne >= 3x (7/8 rugów).

## Wersja 0.9 - uczciwe porównanie portfeli i badanie wejść (2.10.2026 wieczorem)
**Zasady portfeli (dla wszystkich strategii naraz):**
- **Stała stawka $50** (`position_usd`) zamiast 5% kapitału - portfele po stratach grały mniejszymi kwotami.
- **Bez dziennego limitu strat i pauzy po serii strat w PAPER** (`risk_limits_in_paper=False`; w LIVE działają zawsze).
  2.10 od 17:52 do 2:00 stały przez nie hybrid, momentum_only, smart_money_only i safety_only, a reszta handlowała.
- **Blokada ponownego wejścia 6 h** (`reentry_block_h`): po wyjściu z tokena ta sama strategia go nie kupuje.
  Ponowne wejścia po zyskownym wyjściu: 15 szt., 14 stratnych, razem -$213.
- **Do 15 pozycji, ekspozycja do 100%** (było 5 i 40% - portfele lowvol* zaczynały pomijać wejścia lowvol).
- `report` ma sekcję "od ostatniej zmiany zasad portfeli" (moment zmiany zapisuje się sam: `kv rules_since`);
  kohorty porównań grupują strategie dołączone w odstępie do 15 min (było 1 h - sklejało starty z 17:52 i 18:50).

**Badanie wejść (`python bot.py entries [--min-age 60] [--since ...]`)** - po wiadomości ChatGPT o strategiach wejścia:
- Większość listy już była w bocie: momentum, wybicie, retest, Bollinger squeeze, przyspieszenie kupujących, smart money,
  powrót do VWAP, wynik punktowy (= oś Opportunity), koszty i opóźnienie wejścia. Sentyment społecznościowy - brak
  darmowego API.
- **Bot ocenia token zwykle raz** (gdy pojawi się w nowościach DexScreenera), więc reguły minutowe prawie nigdy nie trafiały
  w moment oceny (breakout_volume: 1 sygnał w dobę). `entries` sprawdza je retro na archiwum świec "co minutę" przez
  2 h od pierwszego spojrzenia. Na 34-48 tokenach żadna reguła (wybicie, retest, kompresja, wolumen, momentum 5 min,
  sweep, powrót do średniej, wiele interwałów) nie dała wyniku na plus w obu połowach próby.
- **Rynek po pierwszym spojrzeniu bota mocno spada:** tokeny po twardych filtrach - mediana -30% po 1 h i -76% po 6 h
  (ceny DexScreenera). Najmocniej świeże (< 60 min): -51% po 1 h na 644 tokenach, także poza próbą. Po wyjściach
  (stop + take-profity) obraz jest niejednoznaczny: prawdziwe pozycje - świeże lepiej (-5,5% vs -16,1%), odtworzenie
  na świecach z poprawionym czasem sygnału - świeże gorzej (-16,9% vs -8,8%, 14 vs 18 tokenów). Dryf ceny to nie wynik
  strategii - portfela "tylko dojrzałe" nie dodano; regułę ocenia dalej `skip_young_60m`.
- **Poprawka zapisu sygnałów (2.10 23:05):** gdy token w ciągu 30 min przechodził z obserwacji (WATCH) do zakupu, bot
  nie zapisywał nowej oceny i sygnał trafiał do starej: z jej czasem, ceną i niepełnymi cechami (36% sygnałów; wejście
  w odtworzeniach średnio ~5 min za wcześnie). Teraz zmiana decyzji = nowy wpis. Stare sygnały naprawia
  `Storage.signals_timed` (czas = pierwsze wejście portfela w ten token; bez wejścia - pomijane), z którego korzystają
  `exits --signals`, `entries` i `calibrate`. Po poprawce odtworzenia są gorsze (np. safety_only -14% zamiast -9% na
  wejście) - wcześniejsze wejścia "w chwili obserwacji" łapały ruch, którego bot nie mógł złapać.
- Cechy aktywności (kupujący 60 s, transakcje, wolumen, ATR, nowi kupujący) to praktycznie jedna informacja
  (Spearman 0.7-0.93); strategie momentum/hybrid/buyer_accel/smart_money wskazują w 85-100% te same tokeny co momentum_only.
- **Nowe cechy (tylko do badań):** `seller_accel`, `bsi` (udział kupna w wolumenie), `buy_count_share`, `flow_divergence`
  (dużo drobnych zakupów przy dużych sprzedażach = dystrybucja), reżim rynku `mkt_breadth_h1` / `mkt_median_h1`
  (tokeny z bieżącego obiegu) i `sol_ch_h1/h6/h24` (SOL/USDC, co 5 min).

## Przegląd cudzych botów i strategia Gemini (4.10.2026)
Folder `inspiracje/` (poza gitem, tylko do czytania): pumpfun-bonkfun-bot (Chainstack), LLM_trader, LazyTrader,
ai-trading-agent-gemini. Kod sprawdzony pod kątem bezpieczeństwa (adresy, obsługa kluczy, skrypty instalacyjne) - czysty.
- **Dane zbieracza zweryfikowane:** każda instrukcja kupna/sprzedaży pump.fun ma TradeEvent w logach (1231 zdarzeń na
  1198 instrukcji, zero uciętych logów). 99,2% transakcji jest w SOL; tokeny w innych walutach (USDC itd.) mają
  sol=0 i zbieracz już je pomijał. Opłata 1,25% = 0,95% protokół + 0,30% twórca.
- **Cudze zdarzenia "TradeEvent" (naprawione 4.10 13:31):** dyskryminator Anchora zależy tylko od nazwy zdarzenia, a
  subskrypcja daje całe transakcje z pump.fun. Raydium LaunchLab (`LanMV9...`) w tej samej transakcji dał 3 śmieciowe
  rekordy (czas ~10^18) na 385 tys. - psuły MAX(ts): wykrywanie przerw przy restarcie, `copytrade --hours`, `--stats`.
  Zbieracz śledzi teraz stos wywołań programów i czyta tylko zdarzenia wyemitowane przez pump.fun; 3 rekordy usunięte.
- **Tryb mayhem:** ~30% transakcji to tokeny w trybie "mayhem" (część bez opłat). Zbieracz zaznacza je w
  `mints.mayhem`, żeby ranking portfeli i etapy mogły je wydzielić.
- **Strategia `gemini` / `gemini_hc` (llm.py, tylko sygnały):** model ocenia każdy token po twardych filtrach, PO
  wejściach portfeli (nie spowalnia handlu). Odpowiedź tylko jako JSON wg schematu; BUY wymaga warunku unieważnienia;
  brak odpowiedzi = brak sygnału (bez reguły zastępczej); każda ocena w tabeli `llm_decisions`; prawdopodobieństwo
  `p_tp` (+50% przed -25%) zapisywane jako cecha `gemini_p` także przy SKIP. Klucz: `GEMINI_API_KEY` w `secrets.json`.
  Prompt podaje modelowi zmierzone przez bota stawki bazowe (spadek po odkryciu, odsetek rugów), żeby był skalibrowany.
- **Model: `gemini-3.5-flash-lite`** (klucz dodany 4.10 o 12:52, start oceny 12:53). `gemini-2.5-flash-lite` zwraca
  404 dla nowych kont. Test 3 modeli tym samym promptem: 3.5-flash-lite i alias flash-lite-latest ~1 s, ~110 tokenów
  odpowiedzi, poprawny JSON; `gemini-3.5-flash` "myśli" domyślnie (479 tokenów) i ucina JSON przy limicie 500 ->
  odpowiedź `MAX_TOKENS` jest teraz odrzucana z czytelnym błędem. Alias *-latest odrzucony: zmieniałby model po cichu.
- **Prompt v2 (4.10 15:44):** v1 dawał przy 16 ocenach p = 18-22% i SKIP każdemu tokenowi (także SLOP/NET/DOREL,
  razem +$623) - kotwiczył się na podanych mu stawkach bazowych. v2: każda cecha z percentylem wśród ostatnich ~185
  czystych tokenów, pytanie o p_better = szansę, że token wypadnie lepiej niż mediana czystych tokenów (zapis w kolumnie
  p_tp, wersja w `llm_decisions.model` = "gemini-3.5-flash-lite/v2"). Próba na 8 tokenach: p 42-55 (już się różni),
  trafności jeszcze nie widać - ocena po ~100 ocenach (ranking p_better vs wynik po wyjściach).
- **Czego nie kopiujemy:** wykonania prawdziwych transakcji (wymaga klucza prywatnego portfela), "bias to action"
  z promptu LLM_trader (nasze dane mówią, że większość wejść traci), fałszywej historii i testu z podglądaniem
  przyszłości (LazyTrader), cichego zastępowania AI regułami (ai-trading-agent-gemini).

## Wersja 0.10 - tylko pierwsze spojrzenie (4.10.2026)
Token wolno kupić tylko w ciągu `first_look_window_min` (10) minut od pierwszego wejścia któregokolwiek portfela.
Późne wejścia (mediana 1-2 h po pierwszym - ponowne oceny po cooldownie) były gorsze w 9 z 11 strategii, ~20% transakcji,
razem -$1,174 (safety_only -32% vs -6%, momentum_only -28% vs -9%, buyer_accel_only -20% vs 0%). Najczęściej spóźniały
się strict (50% wejść), hybrid (36%) i lowvol* (~27%) - filtr zmienności przepuszcza token, gdy uspokoi się po wzroście.
Zmiana zasad dla wszystkich portfeli naraz (nowa epoka w `report`). Sygnały nadal zapisujemy bez tej reguły (badania).

## Własny strumień danych pump.fun i copy trading (4.10.2026)
Plan z 4.10 (kolejność: najpierw dane, potem symulator, filtry, a copy trading jako osobny moduł). Repozytorium git
od tej wersji (`data/`, bazy, logi i `config.json` poza repozytorium).
- **`collector.py` - "własny DexScreener" za darmo:** websocket publicznego RPC Solany (`logsSubscribe` na programie
  pump.fun), dekodowanie zdarzeń z logów (`TradeEvent`, `CreateEvent`, `CompleteEvent`, migracja). Każda transakcja
  na krzywej: portfel, kwoty, opłata (protokół + twórca, dziś 1,25%), rezerwy po transakcji = dokładna cena. Zapis do
  `data/stream.db` (osobna baza, tryb WAL), luki po zerwaniu połączenia w tabeli `gaps`, limit rozmiaru `--max-gb`.
  Zmierzone: ~35-38 transakcji/s, 20-26 nowych tokenów/min, opóźnienie 2-5 s od bloku, ~0,3 GB/dobę.
  Start: `Start-Process python -ArgumentList "-u","collector.py" -WindowStyle Hidden ...`; `python collector.py --stats`.
- **Czego nie ma:** handlu po graduacji (PumpSwap: ~490 wiadomości/s, ~1 GB/dobę - za dużo dla darmowego RPC przy
  obecnym podejściu). Pozycje w tokenach, które zgraduowały, wyceniamy po ostatniej cenie krzywej.
- **`copytrade.py` - copy trading na własnych danych:** ranking portfeli na starszej części danych (zysk po opłatach,
  >= 5 zamkniętych pozycji, bez botów i twórców), test na nowszej części, której ranking nie widział. Nasze wejście po
  opóźnieniu 0 s (ich cena - punkt odniesienia) / 3 / 10 / 30 s, cena i poślizg z rezerw krzywej, opłata pump.fun,
  priority fee. Dwa wyjścia: "lustro" (gdy lider sprzeda) i zasady bota. Grupa kontrolna: losowe aktywne portfele -
  jeśli top nie bije losowych, ranking nic nie daje.

## Czego świadomie nie ma
- **Historia deployera i bundlerów w pierwszych blokach** (poza samouczącą się listą rugów) - wymaga kluczowanego API (Helius/Birdeye).
- **Sentyment z X/Telegrama:** brak darmowego API. Zastępniki: holderzy, gt_score, trendy GeckoTerminal, linki social.
- **Opóźnienie danych** nie znika w paper tradingu; częściowo pokrywają je realne kwotowania Jupitera i `extra_slippage_pct`.
- **Wszystkie progi są nadal zgadywane** - do czasu, aż `calibrate` będzie miał dane. Szczególnie ostre może być veto
  przy sieciach insiderów (>= 40 kont) i limit round-trip 8%.
- Kolejność darmowych limitów: RugCheck ~30/min i GeckoTerminal ~20/min sprawiają, że pełny skan trwa ok. 1-2 minut.

## Anatomia rugów (4.10.2026, analiza jednorazowa - skrypty w scratchpadzie, nie w repo)
- **Cechy rugów w danych bota** (171 tokenów po graduacji, 53% rugów; 145 wejść bota, 47% rugów; AUC stabilne w obu
  połowach czasu): rugi to tokeny z dużym ruchem w chwili oceny (unikalni kupujący 60 s: mediana 54 vs 11, AUC 0.77;
  transakcje i wolumen 5 min, ATR 1-min), MŁODE (41 vs 91 min), z ROZPROSZONYMI posiadaczami (top10 15% vs 21%),
  z kupnami z wielu portfeli w jednym bloku (same_block_buy_share 0.18 vs 0.06) i flagą "skoordynowane_bloki"
  (83% rugów). Mniej rugów: boosty, insider_networks, smart_konwergencja (słabo).
- **Ryzyko ruga != wynik:** górna 1/3 aktywności (ub_60s) ma 67% rugów, ale najlepszy wynik po wyjściach (-2.5% vs
  -8.4%), bo te same tokeny najmocniej pompują. Jedyna cecha z wynikiem malejącym monotonicznie: same_block_buy_share
  (-3.3% / -9.3% / -13.5%) - to testuje sygnał skip_block_buys.
- **Sekundy przed rugiem na krzywej pump.fun** (zbieracz, 5.5 h, 1815 pierwszych pomp +50% w <= 30 s): 25% kończy się
  rugiem w 60 s. Pompy z rugiem: 2 posiadaczy zamiast 7, top1 59% vs 40%, twórca trzyma 50% vs 16%, w 10 s kupuje
  2 portfele za 0.4 SOL zamiast 7 za 8.4 SOL, 58% to tokeny mayhem (vs 23%). Rug robią portfele z pierwszych 20 kupujących
  (82%), twórca tylko w 7%. Reguły: mayhem -> 45% rugów, nie-mayhem + >= 7 posiadaczy + >= 5 kupujących w 10 s -> 8%.
  Okno 1 s niemierzalne (czas bloku ma rozdzielczość 1 s).
- **Hipotezy z 4.10 wieczorem (bez zmian w bocie):** (1) x = liczba cech "po rugowej stronie mediany" (0/1 albo
  pół punktu) przewiduje rug na krzywej lepiej niż suma płynna (AUC test 0.77 vs 0.71; x=0 -> 0% rugów na 302 pompach),
  wagi nic nie dają. ALE kupowanie tylko x=0 daje NAJGORSZY wynik (-10.3% vs -7.4% przy x 6-9): bez ruga token po
  prostu powoli spada. (2) "dużo różnych kupujących w trakcie pompy = sprzedaj": krach w 30 s najczęstszy przy 2-5
  kupujących w 10 s (35-37%), przy 20+ tylko 15-18%; reguła sprzedaży poprawia wynik (-8.2% -> -6.3%), ale tylko
  dlatego, że skraca trzymanie - zwykłe "sprzedaj po 10 s" daje -5.8%. Na krzywej każde wyjście zostaje na minusie
  (koszt obrotu ~3.3% + poślizg).
- **Profil tokenów, które zarobiły (4.10 wieczorem):** bot 145 wejść - ZYSK 39 (śr. +56%, wyjście trailingiem po MFE
  ~+59% w ~10 min, płynność rośnie 1.3x), RUG 54, RESZTA 52. Przy WEJŚCIU zyskowne wyglądają jak rugi (ok. 120 kupujących
  w 10 min, ub_60s 45 vs 50 u rugów i 8.5 u reszty); od rugów różni je mniej kupna w jednym bloku (0.07 vs 0.17)
  i mniejszy wolumen 6 h. Reguła "aktywne + blok < 0.10" niestabilna (1. poł -12.8%, 2. poł +4.4%, n=10/14).
  Krzywa pump.fun (3319 wejść przy 5 SOL): ZYSK 15%, RUG 19%; przy wejściu ZYSK nieodróżnialny (AUC <= 0.57);
  wspólne z rugami: twórca trzyma więcej, mayhem. Znane portfele (ranking pump.fun, KOL) prawie nigdy nie kupują przed nami.
- **Model ryzyk konkurujących na żywo (4.10, 10:23-16:27, 916 tys. punktów co 2 s, scratchpad ml_*.py + venv ze
  scikit-learn - poza repo):** etykiety trzech barier (+30% / -30% w 60 s), gradient boosting, podział w czasie
  trening/walidacja/TEST. "Będzie duży ruch" przewidywalne świetnie (AUC TEST 0.87 pompa, 0.93 zjazd), ale P(pompa)
  i P(zjazd) rosną RAZEM - strategia "kup gdy przewaga pompy, sprzedaj gdy przeważy zjazd" -13% na teście.
  Osobny model kierunku (meta-labeling, tylko punkty z ruchem): AUC TEST 0.60, w górnym kubełku 67.5% pomp; więcej
  kupna w ostatnich 30 s = częściej ZJAZD. Strategia ruch >= 0.5 i góra >= 0.8: TEST -6.7% (opóźnienie 2 s), -4.4% (1 s),
  -3.0% (0 s); losowe wejścia -10%, sam "ruch" -19%. Przed kosztami (~4% za obrót) blisko zera.
- **Jakość portfeli jako cecha (4.10 wieczorem):** historia portfela liczona tylko z pozycji zamkniętych PRZED chwilą
  decyzji (>= 3 zamknięte, zysk, >= 50% wygranych = "dobry"). Pokrycie: tylko w 31% chwil kupił portfel z historią
  (6 h danych). Kierunek: AUC 0.602 vs 0.603 bez tych cech - zero poprawy; kupno "dobrych" portfeli lekko zapowiada
  ZJAZD (AUC 0.46: na krzywej "dobre" = szybcy flipperzy, którzy zaraz sprzedają). Take-profit "na plusie >= 5% i ktoś
  kupuje -> sprzedaj": -5.7% (mediana +3.7%, 60% zyskownych) vs bariery -8.9% i TP +15% -6.7% - lekko lepszy, n~250.
- **Ablacja A/B/C/D wg planu ChatGPT (4.10 wieczorem, 1 mln punktów, 57 cech):** AUC kierunku TEST: A cena 0.595,
  B +przepływ 0.610, C +portfele 0.608, D +zysk posiadaczy/twórca 0.601 - AUC stoi. Ale zysk strategii EV
  (+15% przed -8%, koszt 4.5%) przy tych samych progach: A -17.5%, B -15.2%, C -6.6% (próg 0); walk-forward w 3 oknach:
  C lepszy od A zawsze, od B nie zawsze; wyniki okien od -2% do -20% (zależne od pory), plus tylko w jednej komórce
  (C, próg 0.02, ostatnie okno: +0.8%, n=89). Najlepsze pojedyncze cechy portfeli: forward edge kupujących
  (fe_buy30, AUC 0.547: kupują portfele, po których zwykle rośnie -> częściej w górę), kupno portfeli z ujemnym edge
  (0.444), niezrealizowany zysk top10 (0.46: duży zysk posiadaczy = podaż nad głową -> częściej w dół), twórca z wieloma
  wcześniejszymi tokenami (0.46). "Dobre" wg zamkniętego PnL działają odwrotnie (0.467). Flow efficiency pominięte:
  na krzywej cena zależy deterministycznie od rezerw i salda SOL.
- **Ranking okazji (pomysł ChatGPT, 4.10 17:40):** score = EV z modelu +15/-8, progi przedziałów z walidacji, wynik na
  TEŚCIE. Model C (z portfelami) jest MONOTONICZNY: top 1% -6.3%, 1-2% -9.1%, 2-5% -12.3%, 5-10% -13.0%, 10-20% -15.1%,
  30-50% -18.0%, dolne 50% -23.6% (A i B nie są monotoniczne na górze). Ale cała krzywa jest pod zerem; walk-forward
  top 2%: -9.9% / -14.7% / -7.7%. Reputacja portfeli w każdej chwili liczona wyłącznie z przeszłości (bez wycieku) -
  brakuje głębi historii, nie separacji. Do powtórzenia po 2-3 dniach zbierania (skrypty ml_*.py w scratchpadzie).
- **Diagnoza modelu C (4.10 ~18:00, dane do ~17:50, nowsze okno TEST):** top 1% przy 2 s spadł do -14.0% (wcześniej
  -6.3% na krótszych danych - wynik niestabilny). Opóźnienie: 0 s -8.3%, 1 s -10.7%, 2 s -14.0%, 5 s -10.9% (nawet 0 s
  mocno na minusie i brak monotoniczności -> to nie wykonanie zabija, sygnał za słaby). Czas trzymania 15-120 s bez
  znaczenia (-13..-15%). Rozkład top 1% dwumodalny: 42% transakcji < -15% (stop -8% przeskakiwany - cena na krzywej
  skacze jedną transakcją), 27% > +10%; MFE mediana 0%. Kształt ruchu 120 s: top 1% rusza się 3x częściej niż losowe
  punkty, ale "najpierw góra" vs "najpierw dół" ~ 36-44% vs 41-45% - model wybiera zmienność, nie kierunek.

## Wpisy na X jako sygnał (4.10.2026, rozpoznanie)
- Badania: tweety influencerów +1.83% w 1. dniu, potem -1% (dni 2-5), -6.5% (30 dni), -18.9% (90 dni) (Merkley i in.,
  180 influencerów, 36 tys. wpisów). MadeOnSol (1071 portfeli KOL, 757 tys. transakcji): ślepe kopiowanie KOL = ujemne EV,
  śr. win rate 42%, liczba obserwujących to najgorszy predyktor; wzór "kup - napisz - sprzedaj obserwującym" w minuty;
  kolejny KOL dokupuje medianowo po 12 s od pierwszego (szybciej niż jakikolwiek tweet).
- Nasze dane: wejścia z kompletem linków (strona + X + Telegram) -18.4% vs -9.1% reszta (n=31 vs 127) - linki nic nie znaczą.
- Dostęp: oficjalne X API pay-per-use $0.005 za odczyt; twitterapi.io $0.15 za 1000 wpisów ($0.1 na start). Lista 199 KOL
  z MadeOnSol ma handle X + adres portfela -> da się zmierzyć opóźnienie tweet vs zakup on-chain.

## Przerwy w działaniu: odtwarzanie ze świec zamiast downtime_close (4.10.2026 19:09)
- Do teraz pozycje otwarte w chwili wyłączenia komputera zamykano po kursie sprzed przerwy (`downtime_close`) - to ucinało
  transakcje w połowie (trailing i TP nie miały szans) i fałszowało wyniki.
- Teraz po przerwie (>= 10 min) bot pobiera świece 1-min z czasu przerwy (archiwum albo GeckoTerminal, porcjami po
  1000 minut) i przepuszcza je przez TE SAME reguły wyjścia (`Portfolio.manage`, parametry strategii), kolejność
  open -> low -> high -> close. Zamknięte w przerwie dostają powód `przerwa_<powód>` i czas ze świecy; niezamknięte
  zostają otwarte. Brak świec / cena niezgodna z ostatnim kursem -> unieważnienie (`status='void'`, gotówka wraca,
  transakcje usunięte, nie liczy się do wyników).
- `fix_downtime.py` przeliczył wstecz 41 starych `downtime_close` (kopia bazy: data/bot_przed_fix_downtime_*.db):
  było -$176, jest -$137 (8 trailingów +$274, 20 stopów -$374, 19 time stopów -$136 - w tym 9 pozycji z przerwy 19:09).
- Ograniczenie: świece nie widzą płynności, więc wyjście "liq_drain" w przerwie nie zadziała; rug bez transakcji
  (wycofanie LP) wyjdzie jako brak świec -> unieważnienie zamiast straty.
- Pierwsza noc (4/5.10, przerwa 537 min): 7 pozycji odtworzonych, 0 unieważnionych. GIFTCAT x3 -> `przerwa_stop_loss`
  o 22:10 (-66%, świeca 22:10 spadła z -27% do -66% i zamknęła się na -64% - realne), MFMBCoin x4 -> `przerwa_time_stop`.
- Poprawka (5.10.2026): MFMBCoin zamknął się o 03:01 zamiast o 01:14 (termin time stopu), bo cichy token nie miał świec
  między 01:00 a 03:01, a odtwarzanie sprawdzało reguły tylko przy świecach. Teraz minuty bez świecy dostają tick po
  cenie stojącej (brak transakcji = cena się nie zmienia na krzywej/AMM), także od ostatniej świecy do końca przerwy.
  Różnica dla tej nocy: ~$0,5 na pozycję - nie przeliczano wstecz.

## Portfele z szybkim time stopem (4.10.2026 19:20)
- Odtworzenie 160 wejść (świece 1-min): wyjście "po 5 min, jeśli nie na plusie" ścina straty na stopach o 59% (wynik
  -798 -> -672 $), "po 10 min, jeśli < +5%" o 45% (-683 $); obie połowy czasu lepsze. Filtr ATR < 20% + time stop 10 min:
  -75% strat na stopach. Stop -15% tylko -24%, stop na wejściu po +15% niestabilny (2. połowa gorsza).
- Nowe portfele (wejścia bez zmian, inne wyjście w strategy_exits): `safety_ts5` = safety_only + time stop 5 min / 0%,
  `lowvol_ts10` = lowvol + time stop 10 min / +5% (zastępuje 4 h; działa tylko przed TP1).
- `Storage.mark_rules`: dopisanie wyjść NOWEJ strategii nie resetuje okna "od ostatniej zmiany zasad" (dalej od 11:50).

## Dopłata gotówki i podział strat (5.10.2026 17:00)
- safety_only ($33), safety_wide ($39) i momentum_only ($37) nie miały gotówki na stawkę $50 i przestały wchodzić
  (safety_only to grupa kontrolna dla safety_ts5). `topup.py` dopłacił je do $1 000 (kopia: data/bot_przed_topup_*.db).
  Dopłaty są w kv `<strategia>:deposits` z czasem; raport pokazuje "dopłacono $X; bez dopłat $Y", a maxDD(equity)
  liczy z equity pomniejszonego o dopłaty. Wyniki w $ na transakcję się nie zmieniają (stała stawka).
- Testy: `_bot()` blokuje sieć do Gemini - wcześniej test z prawdziwym kluczem z secrets.json zużywał dzienny limit.
- Podział strat (wszystkie strategie, 762 transakcje na minusie, -$13 721; skrypt w scratchpadzie):
  rug (token <= -80% w 6 h od wejścia) 54% (-$7 351, w tym $2 419 kosztów - wyjście z wydrenowanej krzywej),
  słuszny stop 13%, fałszywy stop (potem >= +50%) 12%, brak świec 11%, stop i powrót do wejścia 6%, time stop 4%.
- "Bez rugów" (wyrocznia - wyrzucone pozycje w tokenach, które zrugowały; nie da się tego wiedzieć przy wejściu):
  razem -$171 zamiast -$5 326. Na plusie: hybrid +$267, random +$123, buyer_accel +$121, momentum +$51; rodzina lowvol
  dalej na minusie (-$128..-$183). Pozycje na rugach zamknięte z zyskiem: 80 szt. +$2 196 - filtr anty-rug zabrałby i je.

## Moduł wykrywania rugów - etap 1 (5.10.2026, rugguard.py + rug_dataset.py + rug_backtest.py)
Plan z promptu użytkownika (notatki rynkowe -> cechy on-chain -> backtest). Bot NIE używa jeszcze modułu (tryb badań).
- **Etykieta (zaakceptowana):** cena odniesienia = cena w chwili decyzji t. RUG_SZYBKI: <= 30% ceny w 30 min, zanim
  wzrosła o +30%; RUG_PO_POMPIE: <= 20% w 6 h po wzroście >= +30% (na takich bot często zarabia - filtr nie powinien ich
  odrzucać); OK - reszta. Martwy token = spadek się liczy. W chwili migracji odniesieniem jest zamknięcie pierwszej
  minuty: w bloku migracji snajperzy potrafią kupić ~150 SOL (cena x7.7), po cenie otwarcia nikt z opóźnieniem nie kupi.
- **Dane (za darmo):** punkty decyzji = migracje z data/stream.db (tylko tokeny utworzone w czasie zbierania = pełna
  historia krzywej, bez survivorship bias), chwile +0/+2/+5/+15 min. Świece PumpSwap z GeckoTerminal (8 zapytań/min, bot
  zużywa 20 z ~30), cache w data/rug_data.db. DexScreener NIE zwraca par martwych tokenów (pairs: null) - zapasem jest
  lista pul tokena z GeckoTerminal, inaczej zbiór miałby tylko ocalałych. Tokeny z luką w danych zbieracza pomijane.
- **Notatki -> cechy (rugguard.curve_features, point-in-time):** bundle (portfele i % podaży w slocie utworzenia +2,
  dev_initial_pct); snajperzy (% podaży w 20 slotach, ile już sprzedali, ruch 1. minuty); posiadacze z sald krzywej
  (top1/top10, liczba > 3%, HHI, twórca) - sprawdza "nikt > 3% = czysto" vs "czysto = scam"; schodki (pullback_ratio,
  max_pullback, CV rozmiaru kupna i odstępów, powtarzający się kupujący, kupna wielu portfeli w slocie); świeże portfele
  (proxy: pierwsze pojawienie w strumieniu <= 10 min przed kupnem; liczone tylko dla tokenów >= 3 h od startu strumienia);
  twórca (wcześniejsze tokeny i % migracji od 04.10, dokupowanie w ostatniej 1/4 krzywej, sprzedaż); czas krzywej, mayhem;
  po migracji: ruch ceny i wolumen od migracji do t (świece do t). Fałszywi KOL-e: bot liczy KOL-i tylko po kupnach,
  nie po etykietach terminali - pułapka go nie dotyczy.
- **Etap 2 (nie zrobione):** klastry wspólnego źródła SOL (bubble mapy, "funding time") z RPC - % podaży na klaster.
- **WYNIK etapu 1 (5.10 20:00, 598 migracji ze świecami, 341 bez dziur w danych - prawie tylko godziny 7-14):**
  w chwili migracji 74% tokenów kończy jako rug (RUG_SZYBKI 252 / RUG_PO_POMPIE 221 / OK 97 na +0 min); średnie
  wejście po regułach bota -20..-30%. Żadna z 33 cech krzywej nie przewiduje ruga: AUC trening 0.50-0.57, TEST
  0.44-0.57, kilka odwraca kierunek. Filtr "flag >= 2" (k z treningu) na TEŚCIE: średnio -20.2% vs -19.7% bez filtra
  (gorzej; mniejsza suma strat tylko przez mniej wejść), odrzuca 31 z 49 RUG_PO_POMPIE i tokeny z +136%.
  Na pozycjach bota (153, wejście zwykle godziny po migracji) progi nie przenoszą się - oflagowane wszystkie.
  "Nikt > 3%": tylko 13 tokenów, rug w obu klasach; top1 > 10% najgorszy wynik (-28%) - za mało danych na rozstrzygnięcie.
  Wniosek: notatki zmierzone na historii krzywej (bundle, snajperzy, posiadacze, schodki, świeże portfele, twórca)
  NIE odróżniają rugów po migracji. Niezbadane: klastry zasileń (etap 2, Helius) i zachowanie PO migracji.
- **Błąd sald (5.10 wieczorem):** TradeEvent zapisuje podpisującego - przy handlu przez routery/boty tokeny idą dalej
  przelewem, którego strumień nie widzi. Salda z krzywej były niemożliwe w 71 z 338 tokenów (suma > 85% podaży albo
  ujemne). Cechy posiadaczy liczone teraz tylko przy spójnych saldach (balances_ok), inaczej brak. Wniosek etapu 1 bez
  zmian (AUC test 0.44-0.47 dla cech posiadaczy). Spójnych tokenów z największym posiadaczem <= 3% jest 1 na 218 -
  "nikt > 3%" kontra "czysto = scam" nie do rozstrzygnięcia na tych danych.
- **ETAP 2 - klastry zasileń (rug_funding.py, Helius Free, 4 689 kredytów):** 20 największych KUPUJĄCYCH z krzywej
  przed migracją (bez pośredników; udział w wolumenie kupna - brutto kupna przekraczają podaż przez boty wolumenowe),
  dla każdego najstarsza transakcja i jej źródło SOL. 1840 portfeli: 1112 rozpoznanych, 687 "aktywnych" (>= 3000
  transakcji - boty, źródło nieznane). Huby (>= 15 zasilonych portfeli w treningu): 3. Klastry wspólnego źródła
  (bez hubów) w 11 z 137 tokenów testu - rzadkie i bez związku z rugiem (AUC test 0.48); czas zasilenia 0.50, świeże
  portfele < 24 h 0.45, mało transakcji 0.45, wiek portfela 0.46, powiązane z twórcą 0.50. Filtr z liczby flag
  (k z treningu = 4): TEST -19.4% vs -19.7% bez filtra - szum. Wniosek: zasilenia 1 krokiem (bez śledzenia łańcucha
  portfeli przez kilka przeskoków) też nie odróżniają rugów po migracji.
- **MAPY RUGÓW (rug_map.py, 5.10 22:55, łańcuch zasileń przeskoki 1-2 z 4; ~41 tys. kredytów Helius):**
  473 rugi -> minuta krachu z 423 (44 pule zbyt ruchliwe, 6 bez krachu), dumperzy (>= 0.3% podaży sprzedane w oknie
  krachu, właściciele z sald tokenów) w 216 rugach, 1459 par, 1267 portfeli. Ten sam portfel zrzucał w wielu rugach:
  89 portfeli w >= 2, jeden w 13 (śr. 5.5% podaży); 48% rugów (chronologicznie) ma dumpera znanego z wcześniejszego.
  ALE: tylko 3% dumperów było wśród top-20 kupujących z krzywej tego tokena - zrzucający to nie widoczni kupujący
  (tokeny docierają do nich przelewem albo kupują po migracji), więc przed migracją ich nie widać. Predykcja przy
  migracji (tylko rugi sprzed t): znany dumper wśród kupujących/twórca -> TEST rug 75% vs 79% bez (AUC 0.47); rodzina
  przez wspólnego przodka: bez stopu na aktywnych łączy przez huby/giełdy (5tzFki.. w 42 rugach) - AUC 0.52;
  twórca powiązany 0.545 (n=48, wynik gorszy -28.9% vs -22.4%) - słabe, do sprawdzenia na pełnym łańcuchu.
  Następny krok (pomysł użytkownika rozwinięty): skąd dumperzy mieli TOKENY (przelewy tokena przed krachem) -
  połączy ich z kupującymi z krzywej / twórcą. Wznowienie śledzenia: `python rug_map.py trace` (pomija sprawdzone).
- **MAPY RUGÓW - wynik końcowy (6.10 rano, łańcuch 4 przeskoki, razem ~52 tys. kredytów Helius):** predykcja przy
  migracji bez zmian - znany dumper / rodzina (wspólny przodek) / powiązany twórca: AUC TEST 0.46-0.50 (wcześniejsze
  0.545 dla twórcy znikło przy pełnych danych). Rodziny "bez stopu" łączą 73% rugów, ale przez giełdy (5tzFki.. 47 rugów).
  **Kim są powracający dumperzy (dumper_source.py, top-10 portfeli x 3 rugi, 4 777 kredytów):** nie
  handlowali na krzywej; w 12/12 znalezionych przypadków KUPILI Z PULI PumpSwap w pierwszych sekundach po migracji
  (-22..+24 s; ujemne = opóźnienie zapisu migracji), żadnego przelewu od operatora. To boty-snajperzy migracji, które
  sprzedają przy krachu - często SAME go powodują - a nie operatorzy rugów. 17% wszystkich dumperów kupowało dany
  token na krzywej. Ruch ceny i wolumen od migracji do t (+2/+5 min) też nie przewidują krachu (AUC TEST 0.48-0.53).
- **"Migration dump" (notatka użytkownika) jest częsty, ale nie wyróżnia:** 114 z 341 migracji (33%) to krzywa wykupiona
  w bloku utworzenia (<= 1 s), w 94 jeden portfel >= 70% podaży. Rug 84% vs 82% przy pozostałych migracjach; wynik
  wejścia raz gorszy, raz lepszy (trening -33.6% vs -27.3%, TEST -14.7% vs -22.2%). Każda świeża migracja to strefa zrzutu
  (~80% rugów) - zgodnie z tym bot i tak nie kupuje tokenów młodszych niż 15 min.
- **Poprawka etykiety (5.10 wieczorem):** próg "pompy" +30% -> +50%. Uzasadnienie w propozycji ("+30% to TP1") było
  błędne - TP1 bota to +50% (config.take_profit_levels); intencja "bot zdążył coś sprzedać" wymaga +50%.

## Dziury w danych zbieracza (5.10.2026 19:00)
- Publiczny RPC (api.mainnet-beta.solana.com) po południu i wieczorem (ok. 14-22) opóźnia strumień (mediana 10-57 s
  zamiast ~2 s) i zrywa połączenie co 1-3 min (ConnectionClosed 1002, 158 razy 5.10). Rano dane prawie pełne.
- **Błąd:** luki zapisywano w czasie ODBIORU (> 5 s od ostatniej wiadomości). Przy opóźnieniu 30 s zerwanie gubi ~30 s
  transakcji, a luka w czasie odbioru ma 2-3 s - poniżej progu, więc tabela gaps nie widziała większości strat.
  Pomiar z samych transakcji (odstępy > 5 s bez żadnej transakcji w czasie bloku): 4.10 14-22 h brak 9-38% każdej
  godziny, 5.10 15-19 h brak 9-43%. Tylko 251 z 760 migracji ma dane bez dziur (wszystkie z godzin 7-14).
- **Poprawka:** zbieracz zapisuje dziury w CZASIE BLOKU (Store.add, HOLE_S = 5 s); `collector.data_holes()` liczy je
  wstecz z samych transakcji i to jest źródło prawdy dla analiz (rug_backtest wyklucza tokeny z dziurą, copytrade
  pokazuje prawdziwą sumę); `collector.py --stats` pokazuje dziury. Wnioski z danych popołudniowych (copytrade, analizy
  krzywej z 4.10) mogą być obciążone brakującymi transakcjami.
- `--url` i `--db`: porównanie serwerów RPC na osobnej bazie bez ruszania głównego zbieracza. PublicNode
  (wss://solana-rpc.publicnode.com, bez klucza) w teście 30 s: 56,5 transakcji/s przy opóźnieniu stałym ~10,6 s,
  główny zbieracz w tej samej chwili ~38/s.
- **Test 10 min równolegle (19:20-19:30):** liczby transakcji podobne (mainnet 22 033, PublicNode 21 894), ale wspólnych
  tylko 14 145. Mainnet gubi CAŁE SEKUNDY przy zerwaniach (5 dziur, 151 s - wykrywalne), w połączonych sekundach ma
  ~99% transakcji. PublicNode nie zrywa, ale pomija CAŁE BLOKI: 394 z 1135 slotów (35%) - braki rozsiane, niewykrywalne
  jako dziury. Dla badań to gorsze, więc zbieracz został na mainnet-beta (restart 19:32 z poprawionym kodem).
  Przepustowość łącza wykluczona (Ethernet 1 Gb/s, opóźnienie mainnetu bez zmian przy drugim połączeniu). Na przyszłość:
  Helius (darmowy plan, konto użytkownika) albo dwa źródła z łączeniem.

## Opóźnienie wyjść na stopie (5.10.2026, scratchpad stop_delay.py)
- Bot sprawdza pozycje co 10 s (DexScreener + kwotowanie Jupitera), obieg skanu ~50 s (p90 ~60 s) - stabilnie od 1.10.
- 229 wyjść na stopie ze świecami: od początku minuty, w której świeca przebiła poziom stopa, do wyjścia mediana ~50 s
  (każdy dzień 48-60 s). Wyjście średnio **-16.9% PONIŻEJ poziomu stopa** (stop -25% = realnie ~-37% od wejścia);
  zamknięcie minuty przebicia dałoby -11.6%, dołek tej minuty -18..-23%. 5.10 (-15.6%) nie gorszy niż inne dni -
  zły wynik dnia to rynek (tylko 9% pozycji doszło do +50% wobec 21% 4.10 i 38% 3.10), nie opóźnienia ani dziury
  w danych (bot nie używa danych zbieracza - ma PumpPortal, DexScreener, GeckoTerminal, Jupiter).

## Wiek przy wejściu i "random lepszy od filtrów" (6.10.2026, pomysły ChatGPT; scratchpad age_entry.py)
- Wcześniejsze "30-60 min -6% vs 1-3 h -21%" było liczone na POZYCJACH (token w 8 portfelach = 8 obserwacji) i z różnymi
  wyjściami. Na WEJŚCIACH (270, to samo wyjście SL25 symulowane na świecach): 30-60 min -11.2% (n=34, 95% CI -24..+2%)
  vs 60-180 min -14.5% (n=80, CI -22..-6%) - przedziały się nakładają. Poza próbą (po 07:40) za mało wejść.
  `age_min` bota to wiek PULI (od migracji), nie tokena.
- **Test w parach na 598 migracjach (ten sam token kupiony 15/30/45/60/90/120/180 min po migracji, wyjścia bota):**
  każdy wiek -8..-16% na wejście; różnice w parach 30 vs 60/90/180 min: +0.8..+2.2 pp (CI ok. +-7 pp) - wiek NIE ma
  znaczenia. Poprawa średnich z wiekiem bez par to przeżywalność (martwe tokeny wypadają).
- "Random lepszy od filtrów": wejścia z udziałem random_eligible -5.5% (n=49, CI -17..+6%) vs reszta -13.0% (n=201,
  CI -18..-7%) - nakładają się; random w 47/49 kupił TEN SAM token co inne strategie (losuje z tej samej puli), więc jego
  lepszy wynik to głównie szczęście doboru, nie dowód, że filtry wybierają gorzej. Typowe wejście (mediana) traci ~29%
  przy SL -25% w każdym przedziale wieku; wynik robi garstka dużych wygranych.
- smart_money_only: bez dopłaty (zgodnie z ChatGPT) - z $44 nie handluje, kod i sygnały zostają.

## Moduł analizy/ - 6 analiz wg planu użytkownika (6.10.2026, raport: analizy/RAPORT.md)
Katalog nazywa się analizy/, nie analysis/: pakiet analysis/ przesłaniał moduł reguł bota analysis.py (bot by się nie uruchomił - wykryte przez testy, poprawione przed restartem).
Zasady: podział czasowy 70/30 (eksploracja/TEST), N przy każdym wyniku (< 30 = niewiarygodny), baseline = obecne
reguły bota, logika bota nietknięta. `python -m analizy.run_all` (klasteryzacja: analizy/first_buyers_cluster.py w mlenv).
- **1. First buyers** (300 tokenów, 3731 portfeli; Helius +2 278 kredytów): grupy regułowe insider 35% / sniper 52% /
  smart 1% / retail 12%. Tokeny z przewagą snajperów lepsze niż z przewagą insiderów (eksploracja -11.4% vs -18.3%,
  TEST -15.7% vs -21.4%); filtr "pomiń, gdy snajperów < 50%" +3.4 pp / TEST +2.5 pp (N=45). Udział pierwszych
  kupujących ze wspólnym zasilającym -> rug: AUC 0.556 / TEST 0.574. KMeans k=4: klaster K3 "młodzi insiderzy, zrzut
  w 5 min" -> rug (0.556/0.575), K0 "mieszani, średnie zakupy" -> pump (0.578/0.606). Połączenie z filtrami bota:
  bez poprawy na teście (N=28, niewiarygodne). Błąd poprawiony: wiek portfeli "aktywnych" (>= 3000 tx) był ujemny/
  zaniżony (Helius daje najnowsze 3000) - też w rug_funding; wnioski bez zmian.
- **2. Sweeps** (570 tokenów): sweep w dół z powrotem - na teście się odwraca (N=28). Wybicie bez powrotu: dalszy
  spadek 15 min -2.4..-3.0 pp vs baseline w obu zbiorach (CI obejmuje 0).
- **3. Dynamiczny SL**: żaden wariant nie bije SL -25% (ani eksploracja, ani TEST); szerszy SL pogłębia straty na
  rugach (-19% -> -28% / -36% -> -53%). Płynność w pulach idzie jak sqrt(ceny) - strażnik LP nigdy nie zadziałał:
  rugi = wyprzedaż, nie wycofanie płynności.
- **4. Scaling out**: S6 (1/3 przy +20% + stop na wejściu, dalej TP bota) lepszy w 4/4 porównaniach (bot +1.1/+1.5 pp,
  migracje +0.4/+2.8 pp - TEST migracji CI +0.2..+5.7), niższe odch. std i max DD wszędzie. Kandydat na nowy portfel.
- **5. Manipulacje**: F1 skoordynowane zakupy i F2 "kółka" = tokeny aktywne, wynik LEPSZY (omijanie kosztuje ~2 pp
  w obu zbiorach); F3/F4 rzadkie. Pozycje bota z pełną historią krzywej: 13 - niewiarygodne.
- **6. Definicje ruga** (258 wejść bota): (b2) -80% w 6 h 47%, (e) -70% ZANIM +50% 36% (stabilne 37/36%), (b1) 24%,
  (a) LP 11%, dev_sell 2%. Etykieta do dalszych analiz: (e). Bez rugów (e) strategie: eksploracja +$1 568, TEST -$683 -
  rugi to główna strata w obu okresach (-$5 014 / -$3 328), ale ich unikanie samo nie wystarcza.

## 6.10 wieczorem: portfel safety_s6, logger na żywo, poprawki analiz
- **Portfel `safety_s6`** (osobny, bez filtra pierwszych kupujących): wejścia safety_only, wyjście S6 = 1/3 przy +20%,
  potem stop na cenie wejścia (`breakeven_after_tp1_pct`, nowa opcja paper.py - domyślnie wyłączona, inne portfele bez
  zmian), dalej 1/3 @+100%, reszta @+300%, trailing 20%. Okno "od zmiany zasad" bez resetu (nowy portfel = nowe klucze).
- **`fb_logger.py`** (osobny proces, data/fb_live.db): przy KAŻDEJ decyzji bota skład pierwszych kupujących (liczony raz
  na token na chwilę pierwszej decyzji: firstbuyers.py - ta sama logika co analiza), score_rug; w trakcie otwartej pozycji
  sprzedaże insiderów / wspólnego zasilającego / twórcy / pierwszych kupujących i każda sprzedaż >= $100 (GeckoTerminal,
  co 90 s). Helius tylko dla decyzji BUY/WATCH/SKIP, limit 15 tys. kredytów/dobę. Ok. 2/3 ocenianych tokenów nie ma
  historii krzywej w zbieraczu (starsze lub spoza pump.fun). Zbieracz przy następnym starcie tworzy indeksy trades
  (wallet_id, mint_id) - kilka minut, restart.ps1 czeka do 600 s.
- **Rozbieżność baseline (część 3 -8,0% vs część 4 -12,2% TEST):** te same wyjścia i koszty, inny ZESTAW wejść - część 3
  brała wejścia z >= 5 migawkami płynności; 27 wykluczonych to szybko umierające tokeny (-32%, 78% rugów) = przeżycie.
  Teraz wspólny zestaw `common.bot_entry_set` (260 wejść): baseline -9,3% / TEST -11,5% w obu częściach.
- **Koszty (część 7):** symulacja 5,2 pp na wejście (wejście 1,4 + wyjście 3,8); prawdziwe pozycje 5,4 pp: priority
  0,2, poślizg "z życia" 1,9, DEX+pula -1,3 (kwotowanie lepsze niż cena odniesienia), luka przy krachu 4,6 - największy
  koszt to sprzedaż w spadającą cenę, nie opłaty. Brutto -6,8% -> netto -12,2%; random_eligible jedyny na plusie
  brutto (+$59).
- **Smart money wg definicji użytkownika** (>= 5 zamkniętych, >= 55% wygranych, mediana trzymania > 30 min, bez
  sprzedaży w 5 min): 1 portfel na 3731 - mediana trzymania pierwszych kupujących to ~12 s, > 30 min ma 2%.
- **Scoring logistyczny** (4 cechy, cel rug, trening na eksploracji): AUC 0,569 -> TEST 0,523; filtr "niski score"
  pogarsza wynik w $ w obu zbiorach (wybiera tokeny bez ruchu). Model zapisany (analizy/fb_score_model.json) - logger
  liczy go na żywo do sprawdzenia na nowych danych.

## 6.10 noc: luka przy krachu, bundlery, copy coiny, model wyniku (analizy/ części 0, 8-10)
Nowa zasada: każdy filtr vs baseline ORAZ vs random_eligible (oczekiwany = tokeny z sygnałem safety_only w tym samym
zbiorze i oknie testu, `common.re_expected`; faktycznych pozycji random_eligible za mało). Tabela zbiorcza na początku
analizy/RAPORT.md. Bot bez zmian.
- **0. Luka przy krachu** (crash_gap.py; Helius getTransactionsForAddress, ~60 tys. kredytów, 1 119 pozycji): kwotowanie
  paper = stan puli (kalibracja 0,991), wykrycie stopa średnio 12 s po przebiciu, sprzedaż średnio -17% pod stopem;
  realna transakcja 1-3 s później gorsza tylko o 0,1-0,4%. Szybki stop z odczytu puli: co 2 s +2,1 pp na pozycję
  (eksploracja +2,3 / TEST +1,7), co 5 s +1,6, co 10 s +1,2; potwierdzanie 2 odczytami gorsze.
- **Pule PumpSwap mają wirtualną rezerwę SOL** (~17-18 SOL): cena = (SOL w skarbcu + V) / tokeny; bez V wycena o 10-24%
  za niska (`crash_gap.virtual_sol`, test). Transakcje v1: getTransaction wymaga `maxSupportedTransactionVersion: 1`.
- **Końcowe liczby (7.10 rano, 617 migracji + 30 min: eksploracja 431 / TEST 186; świece rug_data.db 1 279 pul).**
  Oczekiwany random_eligible na migracjach w oknie TESTU: +6..+16% przy N 10-24 (niewiarygodny) - żaden filtr go nie
  bije, ale ten punkt odniesienia jest za mały na wniosek; na eksploracji tokeny po filtrach bota -9..-11% vs -16% wszystkich.
- **8. Bundlery** (bundles.py; 517 ocenialnych): 52% migracji ma bundle (>= 2 portfele w slotach 0-3), w 37% dev sam kupił
  >= 40% w slocie startu. Kształt: NIE odwrócone U i NIE spadek - eksploracja brak związku (Spearman +0,03), TEST wzrost
  (+0,15); najgorszy kubełek 0-10% w obu połowach (-17,9% / -18,5%), 40%+ -13,3% / +3,8%. Hipotezy "20-30% opłacalne"
  (ujemne w obu połowach) i "unikaj >= 35%" (odrzucona na eksploracji) się nie potwierdzają. Przedział z eksploracji
  ">= 30%": TEST -1,2% vs -12,7% (N 35, p 0,03; S6 -0,4% vs -10,8%) - bije baseline, nie bije random_eligible (N 20).
  (b) W chwili decyzji bundlerzy prawie zawsze już sprzedali (272/275 i 117/119 tokenów w kubełku 0-10%) - nietestowalne.
- **9. Copy coiny** (copycoins.py; nazwy/tickery za darmo z danych, grafiki Helius DAS ~1 400 kredytów; 617 migracji:
  oryginały 18%, kopie aktywnego 54%, kopie martwego 28%, mediana numeru kopii 10): kopie AKTYWNEGO gorsze w obu
  połowach (-17,7% / -21,8% vs baseline -15,8% / -15,7%); filtr "nie kupuj ich": TEST -8,7% vs -15,7% (N 86, p 0,02).
  Kopie MARTWEGO nie gorsze (-14,0% / -9,4%) - filtr odrzucony na eksploracji. Ta sama grafika co wcześniejszy token
  gorsza w obu połowach (-21,1% / -24,4% vs własna -14,1% / -8,9%). Pokrycie okna 60 h danymi ~54% (noce).
- **10. Model wyniku** (result_model.py, cel wynik > 0, 5 cech - z bundli/copy weszła tylko bundle_start_pct): logistyczna
  AUC 0,654 -> TEST 0,556, filtr gorszy od baseline już na eksploracji; liniowa AUC 0,44 (odwrotnie). Brak przewagi.
- Model loggera (analizy/fb_score_model.json) zamrożony z 6.10 - ponowne przebiegi zapisują fb_score_model_latest.json.

## 7.10: trzy nowe portfele, smart_money_only wyłączony, poprawka V w analizach płynności
- **safety_fast** (fastexit.py): osobny wątek co 2 s czyta jednym getMultipleAccounts (darmowy RPC, commitment
  processed, zapas Helius) skarbce pul PumpSwap pozycji i sprzedaje TYLKO na stopie (`stop_fast`); TP/trailing/time
  stop/audyty jak safety_only w głównej pętli. Cena z (SOL + V) / tokeny, V z konta puli (offset 245, ~17,58 SOL),
  x SOL/USD (Jupiter co 60 s) x 0,991. Pomiar 2 min: cykl 2,01 s, zapytanie 46 ms (p90 118 ms), stan 0 slotów za
  czubkiem -> wykrycie <= ~2,1 s (średnio ~1 s) vs mediana 12 s w głównej pętli. Wspólne połączenie SQLite
  (check_same_thread=False) + `Bot.fast_lock` przy kupnie/wyjściach; Portfolio.open_value iteruje po kopii.
- **safety_bundle30** / **safety_nocopy** (launchcheck.py - ta sama logika co analizy 8 i 9): wejścia safety_only tylko
  przy bundlu startu >= 30% (brak danych -> nie kupuje) / bez kopii aktywnego tokena i skopiowanej grafiki (brak danych
  -> kupuje). Cechy startu zapisywane w decisions.features (bundle_start_pct, copy_cat, img_copy...). Cache grafik
  odświeża fb_logger co 10 min (DAS, ~70 kredytów/cykl). bundle30 kupi rzadziej - tylko tokeny z historią krzywej.
- **smart_money_only wyłączony** (stał na $44; smart money wg analizy prawie nie istnieje).
- **Kryteria oceny na żywo ustalone PRZED wynikami**: analizy/KRYTERIA_NA_ZYWO.md (para z safety_only, >= 100 pozycji,
  bootstrap CI, random_eligible), liczy `python -m analizy.live_eval` (część 11 raportu).
- **Poprawka V w analizach płynności** (common.liq_vs_expected): oczekiwana płynność w puli PumpSwap to
  (L_0 + V) sqrt(P_t/P_0) - V, nie L_0 sqrt(P_t/P_0). Definicja ruga (a) "wycofanie płynności": 31 wejść (11%) -> 1 (0%)
  - wcześniejsze "wycofania LP" były artefaktem; rug = wyprzedaż. Dynamiczny SL (część 3): dalej żaden wariant nie bije
  SL -25% (poprawiony też tekst werdyktu - D3 dostawał "TRZYMA SIĘ", choć na eksploracji był gorszy). Baseline, S6,
  koszty, luka przy krachu i etykieta (e) bez zmian (świece Gecko / transakcje paper nie zależą od V).

## 7.10: rug2 - nowe źródła sygnału przy wyborze tokenów (analizy/rug2/, raport RAPORT_KONCOWY.md)
- Sprawdzone (cechy tylko sprzed T, testy pytest braku lookahead): a) historia twórcy - lokalnie pokrycie 21%, pilot Helius
  (100 twórców, 1 293 kredyty) podnosi je tylko do 18% (twórcy na nowych portfelach); b) graf zasilania do 3 hopów - hop 1
  nie trzyma się na teście, hopy 2-3 bez pokrycia (56% pierwszych kupujących to boty >= 3000 tx); c) zaufani twórcy
  (trusted_devs.yaml) - pokrycie 0%; d) ślepy test wykresów (strona `analizy/rug2/blind/server.py`, 195 ocen) - "kupić"
  nie lepsze, częściej rugi; d2) wzorce użytkownika (prosta, schodki - gorsze, ale filtry bota już je odsiewają).
- **Wniosek wg kryterium użytkownika: wybór tokenów w tej niszy nie ma przewagi z tych danych** - żaden pomysł nie dał na
  teście >= 2 pp ponad random_eligible przy N >= 30. Dalsza praca: wyjścia i koszty (S6, szybki stop - test na żywo).
- Propozycja portfela random_fast_s6 (wejścia random_eligible + szybki stop + S6): kryteria w KRYTERIA_NA_ZYWO.md zapisane
  przed wdrożeniem; zmiana czeka na zgodę.

## 8.10: panel danych (panel.py + panel_template.html -> data/panel.html)
- `python panel.py` liczy na nowo wyniki portfeli, testy na żywo i aktywność pump.fun z baz (tylko odczyt) i wstawia je do
  szablonu; werdykty badań, traderzy i koszty Heliusa są wpisane w panel.py (RESEARCH / TRADERS / HELIUS) - przy nowych
  badaniach dopisz je tam. Opublikowany jako artefakt: https://claude.ai/artifact/KbPV6PqwhpLF3gCgffUhef
- Mapy portfeli (8.10, analizy/mapy.py -> data/mapy.json, zakładka "Mapy portfeli"): floty klonów (15 flot, 120 portfeli),
  grupy kupujące razem (1076 grup / 7016 portfeli w całych danych; sieć snajperów 2097 portfeli pominięta; na mapie 30
  grup), naśladowcy Cupsey / Trader B / Bot D / Bot E, pierścienie bundla startu (portfele razem w slocie utworzenia
  w >= 3 tokenach). Bundle: 27% tokenów ma >= 2 obce portfele w slocie startu; migracja: 0 obcych 2.4%, 1: 0.4%,
  2-3: 1.0%, 4-7: 4.3%, 8+: 7.3% (więcej portfeli w bundlu = częściej migruje, ale to nie wynik pozycji).

## 8.10: kopiowanie zyskownych portfeli POZA PRÓBĄ (analizy/copy_oos.py -> analizy/KOPIA_OOS.md)
- Wybór portfeli na 70% czasu (1154 kwalifikujących się, klony odsiane), kopia ich pozycji w ostatnich 30% (24 h),
  k slotów po każdej ich transakcji. R1 top 20 po SOL: -5.5% przy 0.4 s, -4.9% przy 20 s (CI po portfelach < 0);
  R2/R3 (zysk w obu połowach): -7.6..-4.4%; kontrola 20 losowych: -7.5..-6.8%. Wybrani portfele SAME dalej zarabiają
  w teście (+3.2..+3.5%/poz.), ale już 1 slot (0.4 s) opóźnienia zabiera ~9-11 pp - przewaga siedzi w pierwszym slocie.
- Umiejętność jest trwała: korelacja rang wyniku eksploracja -> test 0.41 (224 portfele); top 20% +3.2%, dół -4.9%.
- Wcześniejsze +1.6..+3.6% przy kopii Bot D / Bot E to był błąd selekcji (wybór na tym samym oknie).
- Zgoda zręcznych (>= 2 z top 100 kupiło ten sam token w 60 s): wejście po 2-20 s daje -5.5..-13.9% vs losowy token w
  tym wieku ~0..+2% - spóźniony kupujący za szybkimi portfelami jest ich płynnością wyjścia.

## 8.10: ranking "nr 1 w tej sekundzie" (top1.py -> NR1.md), koszt szybkości, trader Bot E (KOL_bot_E.md)
- Nr 1: co sekundę start (wiek 10-120 s) z największą kwotą zakupów w 10 s; sygnał, gdy staje się nr 1. 0 z 27 wariantów
  > 0 na eksploracji; TEST -3.9% przy d = 0 (natychmiast), -2.6..-3.9% przy 1-5 s. Pokrywa tylko 5% wejść Bot D -
  jego wybór to nie prosty ranking. Jego własny wynik w oknie testu: +1.2% (CI -0.9..+3.6) - też nieistotny.
- Bot E (klon: Bot E2): 697 pozycji, +38.4 SOL, +5.5%/poz. (mediana +2.9%), 58% wygranych; wchodzi 4 s po starcie
  (21.6 SOL zakupów w 10 s, cena już +242%), trzyma ZAWSZE 2 s - arbitraż opóźnienia na fali otwarcia.
- Kopia na poziomie slotów (jego transakcje wykonane k slotów po nim, -0.4 pp na nasze koszty): Bot E 1 slot +0.8%
  (CI -1.5..+3.5), 2 s +0.3%, 4.8-20 s +2.8..+3.6% (CI > 0); Bot D 0.4-20 s +1.6..+2.3% (CI > 0, obie połowy > 0).
  ALE: bez 1% największych pozycji ~0%, a traderzy wybrani na CAŁYM oknie (błąd selekcji) - wymaga testu poza próbą
  (wybór na 70%, kopia na 30%).
- Koszt szybkości (ceny z sieci 10.2026, niezweryfikowane): Helius Business z LaserStream gRPC $499/mies. (Professional
  $999), Chainstack Yellowstone gRPC od $49/mies., QuickNode gRPC od $499/mies., dedykowany węzeł $1.5-2.5 tys./mies.,
  napiwki Jito ~0.001-0.01 SOL na transakcję (w gorączce startu 0.01-0.1). Bot ma tryb tylko PAPER.

## 8.10: klony botów (analizy/clones.py -> KLONY.md, data/klony.json) i trader Bot D (KOL_bot_D.md, rule21.py -> REGULA_21S.md)
- Klony: 1125 portfeli z >= 100 pozycjami (bez insiderów slotu startu); para = klon, gdy podobny odcisk (stawka,
  trzymanie, udział stopów czasowych 14-19 / 58-63 / 295-305 s, wiek tokena), >= 70% wspólnych godzin i <= 2% wspólnych
  tokenów. 71 grup klonów (265 portfeli), 860 portfeli bez klona. Grupa 17 = Bot A + Bot A2 + Bot A3 + 2 inne: RAZEM
  -45.5 SOL (-7.2%/poz.) - "zyskowne portfele" tej floty to szczęśliwe kawałki przegrywającego bota (błąd przeżywalności).
  Trader B ma klona (Trader B2); Bot C bez klona. Losowanie dalej: 1 przedstawiciel grupy + portfele bez klona, top 30 po SOL.
- Bot D (bez klona, wylosowany z top 30): 2843 pozycje, +54.2 SOL, +3.8%/poz. (mediana -0.8%), obie połowy na plus
  (+32.8 / +21.4). Automat: trzyma ZAWSZE 21 s, 0.5 SOL, wchodzi ~40 s po starcie w najgorętszy start (nr 1 w 52%,
  AUC wejścia 0.97, 16 kupujących w 10 s). Wybór: max 5 min +17% vs +6%, rug 5% vs 13%, po 30 min bez różnicy.
- Jego reguła odtworzona (wiek 30/45/60 s, progi tłumu, wyjście 21 s / 60 s): 0 z 216 wariantów > 0 na eksploracji;
  test -2.8% już przy d = 0 (= opłaty pump.fun w obie strony), -4..-6% przy d = 1-12 s. Jego brutto ~+6.7% bierze się
  z czegoś, czego nasze cechy nie łapią (ranking chwili / wejście w tym samym slocie co fala).

## 8.10: czwarty trader bez X - Bot A2... (KOL_bot_A2.md) = ten sam bot co Bot A
- 1087 pozycji na krzywej, +13.4 SOL, +1.1%/poz. (mediana -0.6%); 1. połowa +17.0, 2. połowa -3.6 SOL.
- Identyczny profil jak Bot A: stawka ~0.63 SOL, wejście ~2.6 min po starcie w gorący start (AUC 0.94), wyjście po
  16-18 s albo dokładnie po 300 s, wybór: max 5 min +43% vs +11%, rug 5% vs 14%, cena po 30 min gorsza (-37% vs -31%).
- Oba portfele aktywne w tych samych 51 godzinach, ~1270 pozycji każdy, wejścia średnio 45 s od siebie, a WSPÓLNYCH
  tokenów 0 - jeden operator dzieli starty między portfele (żeby nie kupować dwa razy tego samego). Zysk "top traderów"
  bez X bywa więc jednym botem rozbitym na wiele portfeli.

## 8.10: trzeci trader bez X - Bot C... (KOL_bot_C.md) + reguła "przetrwał start" (slow_rule.py, REGULA_PRZETRWAL.md)
- Bot C: 573 zamknięte pozycje na krzywej, +54.7 SOL, +6.0%/poz. (mediana +0.8%), 54% wygranych, obie połowy na plus
  (+36.7 / +18.0). Bot: wyjście dokładnie po 60-61 s (stop czasowy 1 min) albo po 13-16 s; wejście ~2-3 min po starcie
  w żywy start z szeroką bazą (67 portfeli vs 4 u nowych w tym wieku, AUC 0.89), ślad X brak, naśladowców mało (15%).
- Wybór vs pominięte gorące starty (88 wejść <= 60 s): rug 1% vs 14%, cena po 30 min -19% vs -26% (AUC 0.57, obie
  połowy), max 5 min +24% vs +10%. Rugów unika, bo CZEKA: kupuje starty, które przetrwały ~2 min, z 2x większą liczbą
  posiadaczy - nie ma tu ukrytej informacji.
- Reguła stosowana samodzielnie (wiek 90/120/180 s, progi portfeli / kupujących w 10 s / zmiany ceny, wyjście 60 s /
  300 s / TP-SL): 0 z 324 wariantów > 0 na eksploracji; najlepszy na teście -17%/poz. (CI -30..-3) vs baseline -7%.
  Nie działa - jego +6% to wykonanie (wyjście po 60 s na szczycie mikro-fali), nie wybór, który da się powtórzyć.

## 8.10: grupy portfeli kupujących razem - wejście za nimi (analizy/cabal.py -> analizy/CABAL.md)
- Wykrycie na eksploracji (70% czasu): pary portfeli kupujące ten sam start w <= 2 s, razem w >= 5 tokenach i >= 50%
  tokenów mniej aktywnego; składowe >= 3 portfeli. 815 grup (5623 portfele; jedna "grupa" 2045 portfeli = sieć
  snajperów, reszta mediana 4). Sygnał = 2. (3.) członek grupy kupił w 30 s; 30% startów w teście ma sygnał.
- Wybór na eksploracji (d = 5 s): M = 2, wyjście "za grupą" (gdy 1. członek sprzeda), 114 grup ze średnią > 0.
- TEST (raz, bez dziur): wybrane grupy -0.5..-2.1%/poz. (CI obejmuje 0, mediana -4..-9%) przy d = 1-20 s; wszystkie
  grupy -4.0..-4.9%; baseline (każdy token w tym wieku) -6%. Lepiej od baseline o ~4-5 pp, ale nie na plusie; z dziurami
  -4.8% (CI -7.6..-2.0). Werdykt: NIE DZIAŁA jako strategia.
- Pułapka: ~950 tokenów ma krzywą z wirtualną rezerwą SOL < 25 (standard ~30) - 0.25 SOL zmienia tam cenę wielokrotnie
  i dawało "wyniki" +100 000%; wykluczone. Przy innych analizach krzywej sprawdzać vsol na wejściu.

## 8.10: drugi trader bez X - Trader B... (analizy/KOL_trader_B.md) + poprawka kol.py
- Poprawka: pozycje, w których portfel sprzedał więcej tokenów, niż kupił na krzywej (tokeny z przelewu / innego
  portfela / dziury strumienia), są pomijane - u Trader B dawały absurdalne +19 768% / +22 005%. Bot A po poprawce:
  1078 poz., +9.9 SOL, +1.0%/poz. (mediana -1.5%).
- Trader B: 125 zamkniętych pozycji, +131 SOL, +38.6%/poz. (mediana +17%), 82% wygranych, obie połowy na plus
  (+95.6 / +35.5). Wchodzi ~1.3 min po starcie w gorący start PO SPADKU (od szczytu -35%, cena od startu -21%),
  start z tweeta 16% vs 4-5% kontroli, nietypowe narzędzia startu (padre, uxento, googleapis) 36% vs 9-10%.
- Wybór vs pominięte gorące starty: max 5 min +97% vs +11%, cena po 5 min 0% vs -27%, po 30 min -20% vs -37%
  (AUC 0.64, stabilne w obu połowach), rug 2% vs 17% - jedyny z trzech, którego tokeny są lepsze także po 30 min.
- Ale: 46 portfeli kupuje sekundy po nim prawie tylko jego tokeny (27 z 27, 29 z 30) i wnosi ~30% SOL po jego
  zakupie; kupił 8 z 10 startów twórcy #3377 i 7 z 9 twórcy #15609; 8 pozycji z tokenami spoza zakupu. Wygląda na
  zorganizowaną grupę powiązaną z częścią twórców (cabal), nie na czytanie publicznych sygnałów. Z powtarzających się
  twórców 36 SOL, z pozostałych 95 SOL.

## 8.10: trader bez X - Bot A... (analizy/kol.py -> analizy/KOL_bot_A.md)
- Wybór: portfele ze strumienia z >= 30 zamkniętymi pozycjami, zyskowne w obu połowach, spoza listy KOL z X; z top 15
  odrzucone 4 "insiderskie" (kupują w slocie utworzenia w 89-100%); losowanie (ziarno 20261008) z 6 pozostałych z >= 100
  pozycjami. Analiza tylko ze strumienia (krzywa), bez Heliusa; moduły cupsey_signals / kol_select przyjmują portfel.
- Wynik na krzywej: 1101 zamkniętych pozycji, +18 SOL, +2.2%/poz. (mediana -1.2%), 48% wygranych, obie połowy na plus
  (+13.8 / +4.2). Mała, ale stała przewaga (wstępny ranking +98.5 SOL liczył sumy na token, nie pozycje).
- To BOT: 1. sprzedaż dokładnie po 300 s w ~21% pozycji (stop czasowy 5 min), druga fala po 15-17 s; sprzedaje, gdy
  handel zamiera (kupna w 10 s: 2 vs 8 w trakcie trzymania). Drzewo wyjścia AUC test 0.83.
- Wejście jak u Cupseya: gorący start (64 portfele vs 3 u nowych tokenów w tym samym wieku, AUC 0.92), ale później
  (mediana 2.5 min po starcie) i mniejsza stawka (0.66 SOL). Ślad X brak (7% vs 6%).
- Wybór vs pominięte gorące starty: max wzrost 5 min +38% vs +9% (AUC 0.69, stabilne), rug 5% vs 13%, ale cena po 5 i
  30 min GORSZA (-31% vs -21%, -39% vs -29%) - wybiera tokeny o największym krótkim skoku, nie trwale lepsze.
  Naśladowców prawie brak (7% SOL po nim) - tu skok to raczej jego wybór, nie jego wpływ.

## 8.10: czy Cupsey odróżnia trash? (analizy/kol_select.py -> analizy/CUPSEY_WYBOR.md)
- Jego wybory (84 wejścia <= 60 s od startu) vs pominięte tokeny z top 5 najgorętszych startów w tej samej chwili, wynik
  od ceny w chwili jego wejścia: max wzrost 5 min mediana +105% vs +6%, pump (+100% przed -70%) 56% vs 12% (AUC 0.72,
  stabilne w obu połowach), ALE cena po 30 min -39% vs -30% (AUC 0.52) - krótki skok, potem tak samo w dół.
- Nr 1 gorący start w chwilach, gdy był aktywny i nie kupował: max 5 min +9%, pump 17% - to nie "mechaniczne nr 1".
- Naśladowcy: 140 portfeli kupuje <= 5 s po nim i prawie tylko jego tokeny (np. 74 z 78 wczesnych zakupów); wnoszą
  ~22-24% SOL kupionego w 30 s po nim. Skok po jego wejściu jest więc w dużej części WYWOŁANY przez niego (boty
  kopiujące / jego dodatkowe portfele / alerty KOL), a nie tylko wykryty. Trwałej przewagi tokenów (30 min) brak.
- Wniosek: z danych on-chain nie da się oddzielić "umie wybrać" od "jego zakup sam pompuje" u tradera z tłumem
  naśladowców; czystszy test = trader bez naśladowców (sprawdzić ich udział tą samą funkcją followers()).
- MadeOnSol /kol/wallets: pełna lista 1155 portfeli w data/madeonsol/wallets_all.json; "slidrrz" na niej nie ma.

## 8.10: co wyzwala wejście Cupseya (analizy/cupsey_trigger.py -> analizy/CUPSEY_WYZWALACZ.md)
- Warunek konieczny = tłum na starcie: 86-96% jego wczesnych wejść miało >= 8-15 różnych kupujących w 10-15 s, ale
  taki warunek spełnia ~100-180 startów/h, a on kupuje ~2.6/h (trafność 1-4%) - sam tłum to za mało.
- Rozstrzyga RANKING: w chwili jego zakupu jego token był nr 1 po kwocie zakupów z ostatnich 10 s wśród tokenów
  z ostatnich 2 min (mediana 47) w 55%, top 3 w 81%, top 5 w 92%. Kupuje najgorętszy start chwili.
- Wśród gorących startów kupione vs pominięte: większy tłum (54 vs 29 portfeli, 51 vs 23 SOL w 10 s, AUC 0.74-0.79);
  start z X 14% vs 14%, Axiom 26% vs 18%, historia twórcy AUC 0.52-0.54 - poza rynkiem nic go nie wyróżnia.
- Reguła stosowana samodzielnie nie zarabia (analizy/CUPSEY_REGULA.md: 0 z 215 reguł > 0 na treningu).

## 8.10: szybciej niż Cupsey (analizy/cupsey_ahead.py -> analizy/CUPSEY_PRZED.md)
- Górna granica "jego reguły, ale szybciej": jego transakcje wykonane k slotów PRZED nim (jakbyśmy wiedzieli, co zrobi),
  119 wycenialnych pozycji. Jego wynik -2.8%/poz. (mediana -6.1%); przed nim o 0.4 s: -1.8%, 2 s: +0.6% (mediana -4.7%),
  5 s: +0.4% (mediana -8.8%, 17 pozycji bez możliwości wejścia - tokenu jeszcze nie było). CI zawsze obejmuje 0, suma
  SOL z kilku dużych trafień w 1. połowie. Asymetria: spóźnienie 2 s = -27 pp, wyprzedzenie 2 s = +3 pp - ruch robi
  ON i ci, którzy idą za nim; przed nim cena prawie stoi. Bycie szybszym nie daje przewagi, bo jego pozycje same
  w medianie tracą.

## 8.10: na jakie sygnały wchodzi Cupsey (analizy/cupsey_signals.py -> analizy/CUPSEY_SYGNALY.md)
- 116-119 jego wejść na krzywej pump.fun (pełny zapis rynku ze strumienia, cechy tylko ze slotów przed jego zakupem),
  3 kontrole: inne chwile tego tokena, inne tokeny w tej chwili, tokeny odpalone w tej samej minucie oglądane w tym
  samym wieku. Drzewa (głęb. 3) uczone na 70% czasu: AUC test 0.87 / 0.92 / 0.87 - wejścia są przewidywalne.
- Wzorzec: snajper startów - 31% wejść <= 5 s od utworzenia, 66% <= 15 s, 84% <= 60 s. Wybiera starty z tłumem:
  do jego wejścia ~41 różnych kupujących (inne nowe tokeny w tym wieku: 2), 14 SOL zakupów w 10 s (0.1), w slocie
  utworzenia 4 kupujących i ~9 SOL (bundle/start z rozmachem; inne: 1 i 0.5 SOL). Kupuje, gdy fala trwa (cisza 1 s).
- Nie widać: podążania za innymi KOL-ami z listy MadeOnSol (kupna KOL przed nim ~0, AUC 0.53-0.58), sprzedaży twórcy.
- Ślad X: tokeny odpalone narzędziami z tweeta (j7tracker, uxento, obrazek z pbs.twimg.com) 13% jego vs 6% kontroli,
  Axiom 28% vs 11% - nadreprezentowane, ale mniejszość; osi czasu tweetów nie mamy.
- Wyjście słabiej przewidywalne (AUC test 0.65): sprzedaje całość (mediana 100%) zwykle po 3-70 s (mediana 14 s), gdy
  fala słabnie - w chwili sprzedaży cena od 5-10 s stoi, napływ netto 0, mniej kupujących niż w trakcie trzymania;
  brak jednego progu TP/SL (wynik ceny przy 1. sprzedaży rozlany od -3% do +100%).

## 8.10: kopiowanie 1:1 tradera Cupsey (analizy/cupsey.py -> analizy/CUPSEY.md)
- Wynik 7.10 skanera arbitrażu (3,5 h): 438 kwotowań, 4 zyskowne przy 0.1 SOL (razem 0.0044 SOL), żadna nie żyła 10 s,
  przy 0.5/2 SOL zawsze strata -> nie działa, skaner wyłączony.
- Cupsey (2fg5QD1e..., scalper z MadeOnSol): transakcje z historii JEGO KONT TOKENÓW (Helius gTFA na ATA Token-2022) -
  adres portfela odpada (~6 tx/s cudzych transakcji LaunchLab, w których jest tylko kontem), a feed MadeOnSol /kol/feed
  gubi większość sprzedaży (portfel ma dziś 0 tokenów, feed widzi 1 sprzedaż z kilku).
- Okno 4.10 10:23 - 7.10 19:32: 250 zamkniętych pozycji, +38 SOL, średnio -0.2% na pozycję (mediana -13.7%, 34% wygranych);
  1. połowa +47 SOL, 2. połowa -9 SOL - wynik z kilku dużych trafień.
- Kopia 1:1 (te same kwoty, fill = jego fill x spot przed nim / spot w t + d; krzywa ze strumienia, PumpSwap z transakcji
  puli), 131 wycenialnych pozycji: 0 s +62.6 SOL (-2.6%/poz.), 2 s -17.5 SOL (-29.5%), 5 s -22.6, 12 s -20.4, 20 s -23.6
  (-26..-28%/poz., 14-16% wygranych); bez pozycji na dziurach strumienia 2-20 s: -32..-37 SOL. Już 2 s opóźnienia
  zjada wszystko: po jego kupnie cena +6% w 2 s, po sprzedaży -11% (jego wpływ + wchodzący/wychodzący razem z nim).
- Pokrycie z botem: tylko 16 jego pozycji w tokenach, które bot też kupił (on zwykle 15-120 min wcześniej, na krzywej);
  234 jego pozycji bot nie wziął (oceniał 54 z tych tokenów); 151 wejść bota w tokeny, których on nie ruszał.
- Koszt: Helius ~10.6 tys. (konta tokenów) + ~60 tys. (okna pul PumpSwap; szacunek był ~3 tys. - gorące pule mają
  setki transakcji na slot). Przed kolejnym pobieraniem okien pul: najpierw policz transakcje (tryb signatures).

## 8.10: reguła wejścia Cupseya stosowana samodzielnie (analizy/cupsey_rule.py -> analizy/CUPSEY_REGULA.md)
- Pytanie: skoro jego wejścia da się przewidzieć z rynku (CUPSEY_SYGNALY.md), czy SAMA reguła (bez kopiowania go)
  zarabia na wszystkich nowych tokenach pump.fun? Liczone lokalnie ze stream.db (bez Heliusa), ~75 s.
- 70 039 tokenów z pełnymi 330 s po starcie. Ocena w wieku 5/10/15 s cechami z transakcji przed tą chwilą, wejście po
  d = 1/2/5 s (stan krzywej w t + d), 0.25 i 1 SOL z opłatą i poślizgiem, 0.0005 SOL za transakcję. Nasz wpływ na
  krzywą: cudze transakcje jako przepływ tokenów (sprzedaż od razu po zakupie oddaje wkład minus opłaty). Wyjścia:
  "jak on" (5 s bez napływu netto, max 5 min), 15/60 s, TP +30%/SL -20%; migracja = ostatnia cena krzywej.
- Podział czasu 06.10 20:33 (później z: 70% okna i podział drzew Cupseya - progi z drzew nie widziały testu). Progi
  z siatki 215 reguł (1-2 warunki) wybierane na treningu bez dziur, d = 2 s, 0.25 SOL, N >= 50.
- **Wynik: reguła NIE zarabia.** Na treningu 0 z 2580 kombinacji reguła x wiek x wyjście miało dodatnią średnią.
  Najlepsza z treningu (portfele_razem >= 40 i sol_1_slot > 9, 5 s, 15 s): test N 89, +0.2%/poz., mediana -3.1%,
  95% CI -8..+9% - szum oparty na kilku trafieniach (bez 5% najlepszych -5.6%). Reguły dosłownie z drzew
  (portfele >= 8, kupno_sol_10s > 3 itd.): -4..-9%/poz. na każdym wieku/wyjściu (N 670-2230 na teście), gorzej niż
  baseline "każdy nowy token" (-1..-4%, głównie opłaty). Wyjście "jak on" przy najlepszych progach: -5%/poz. na każdym wieku.
- Kontrola na JEGO tokenach (nasze wejście w stałym wieku, wiedza z przyszłości - nie strategia): przed jego zakupem
  +44%/poz. (N 44, 5 s, TP/SL), po jego zakupie -3% (N 28). Zysk robi jego własny zakup i kopiujący go, a nie cechy
  startu - tłum w pierwszych sekundach sam z siebie częściej jest szczytem niż początkiem fali. Kierunek zamknięty,
  chyba że pojawi się źródło sygnału sprzed jego zakupu (X/social - CUPSEY_SYGNALY.md, sekcja 2).
- Uwaga: 39% pozycji głównej reguły na teście nachodzi na dziury strumienia (wszystkich tokenów testu: ~29%) - wyniki
  podane z nimi i bez nich, kierunek ten sam.

## 7.10: papierowy skaner arbitrażu między pulami DEX (arb_scan.py)
- Pytanie użytkownika: czy atomowy arbitraż "kup na DEX A, sprzedaj na B" (z flash loanem) zarabia na memecoinach.
  Wersja na Solanie, ZERO transakcji i kluczy - tylko kwotowania Jupitera ograniczone do jednego DEX-u.
- Rozpoznanie przed budową (DexScreener token-pairs): z 60 najświeższych migracji ok. 8% ma drugą PRAWDZIWĄ pulę
  (Meteora); druga "pula" pumpfun to zamknięta krzywa (płynność 0). Z 150 losowych migracji starszych niż 6 h: 149 martwych
  (< $10k płynności), żadna nie ma 2 pul >= $1k. Powierzchnia arbitrażu w niszy bota jest bliska zeru.
- Skaner: wszechświat = migracje z 6 h + tokeny, które bot oglądał w 24 h z płynnością >= $10k; przesiew różnicą cen
  z DexScreenera (>= 50 bps albo próbka losowa 1/10), weryfikacja kwotowaniem w obie strony (0.1 SOL, większe kwoty
  przy zysku), koszty: opłata sieci + priority fee + napiwek Jito (minimalny i 50% zysku), ponowne kwotowanie po 10 s.
- Kontrola na WIF (12 pul): DexScreener pokazywał do 7% różnicy na małej puli, kwotowanie tam i z powrotem dało -0.12%
  i -0.50% - różnice z DexScreenera to w dużej mierze nieświeże ceny.
- Ograniczenia: Jupiter wybiera najlepszą pulę DEX-u (nie konkretną), więc dwie pule jednego DEX-u nie są rozdzielane;
  nie mierzymy konkurencji (boty Jito w ms) - wynik to GÓRNA granica.

## Gemini na ślepo: rugi i fałszywe stopy (5.10.2026, gemini_eval.py)
- Test A (chwila wejścia): 101 wejść w tokeny, które w 6 h spadły do <= 20% ceny, + 101 zwykłych (losowo), pomieszane.
  Test B (chwila stopa): 232 wyjścia na stopie, z tego 51 fałszywych (cena wróciła do >= +50% nad wejście w 6 h).
  Model widzi tylko dane z tamtej chwili (87 cech z percentylami liczonymi z decyzji SPRZED, ustalenia reguł, migawki
  ceny/płynności, świece 1-min), bez adresu i etykiety. Raport porównuje z prostymi regułami (np. sama cena teraz vs
  wejście) - część stopów to krach -95%, gdzie "nie odbije" jest oczywiste.
- **WYNIK (396 z 434 odpowiedzi; o 21:00 dzienny limit Google - 429):**
  A: AUC Gemini 0.549 - prawie losowo; proste cechy lepsze: ATR 1-min 0.730, unikalni kupujący 60 s 0.722,
  same_block_buy_share 0.625 (rugi = duża aktywność, ale "ryzyko ruga != wynik"). Gemini mówi RUG w 74% przypadków
  (precyzja 56% przy bazie 51%), kalibracja płaska; odrzucone przez niego -$7.61 vs przepuszczone -$6.32 na wejście.
  B: AUC 0.596 - tyle co trywialna "cena teraz vs wejście" (0.588); werdykt HOLD 0 razy na 212 (p zawsze <= 40), więc
  jako decyzja nigdy nie uchyliłby stopa. Obserwacja do sprawdzenia na nowych danych (kierunek nie był ustalony
  z góry): krótki czas do stopa = częściej fałszywy stop (AUC 0.655 odwrotnie).
  Uwaga: test zużył dzienny limit klucza - strategia gemini w bocie dostaje 429 do resetu limitu (~9:00 czasu PL).
