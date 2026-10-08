"""Cała konfiguracja bota w jednym miejscu.

Każdy próg ma komentarz, po co jest. Nadpisywanie bez ruszania kodu:
wpisz wybrane pola do config.json obok tego pliku, np. {"buy_threshold": 70}.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

BASE_DIR = Path(__file__).parent


@dataclass
class Config:
    # ---------- ogólne ----------
    # Tryb pracy: RESEARCH = tylko zbiera dane i zapisuje decyzje/sygnały (bez wirtualnych transakcji),
    # PAPER = jak wyżej + symulowane transakcje na żywych danych, LIVE = prawdziwe transakcje (NIEZAIMPLEMENTOWANE).
    mode: str = "PAPER"
    use_pumpportal: bool = True           # strumień PumpPortal: graduacje (odkrywanie) i starty (historia twórców)
    chain: str = "solana"
    loop_seconds: int = 45                # co ile sekund pełny obieg
    db_path: str = str(BASE_DIR / "data" / "bot.db")
    user_agent: str = "memecoin-paper-bot/0.1"

    # ---------- limity zapytań (darmowe API) ----------
    dexscreener_rpm: int = 200            # limit DexScreenera to 300 rpm dla pairs, 60 dla profili
    dexscreener_profiles_rpm: int = 40
    rugcheck_rpm: int = 30                # RugCheck nie publikuje limitu - trzymamy się nisko
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    rpc_rpm: int = 30
    use_rpc_fallback: bool = True         # gdy RugCheck padnie: mint/freeze authority z RPC

    # ---------- paper trading ----------
    start_balance_usd: float = 1000.0
    # v0.9: stała stawka na wejście. Przy stawce w % kapitału portfele po stratach grały mniejszymi kwotami, więc wyniki
    # w $ przestawały być porównywalne między strategiami. 0 = stawka position_pct * kapitał.
    position_usd: float = 50.0
    position_pct: float = 0.05            # ile kapitału na jedną pozycję (tylko gdy position_usd = 0)
    max_open_positions: int = 15          # v0.9: 5 -> 15 (przy 5 portfele lowvol* zaczynały pomijać wejścia lowvol)
    max_exposure_pct: float = 1.0         # v0.9: 0.40 -> 1.0 (15 x $50 = $750 - realnie ogranicza gotówka)
    max_position_pct_of_liq: float = 0.02  # pozycja <= 2% płynności puli (ogranicza slippage)
    swap_fee_pct: float = 0.30            # prowizja DEX-a na stronę
    priority_fee_usd: float = 0.05        # stały koszt tipa/priority fee na transakcję
    extra_slippage_pct: float = 1.0       # dodatkowy poślizg "z życia" (opóźnienie, MEV)

    # ---------- wyjścia ----------
    stop_loss_pct: float = 25.0           # twardy SL od ceny wejścia
    take_profit_levels: tuple = ((50.0, 0.33), (100.0, 0.33), (300.0, 0.34))
    #                              ^ (zysk % od wejścia, jaka część ORYGINALNEJ ilości sprzedać;
    #                                 ostatni poziom sprzedaje całą resztę)
    trailing_stop_pct: float = 20.0       # trailing od szczytu, aktywny po pierwszym TP
    # stop na cenie wejścia po pierwszym TP: sprzedaż reszty, gdy zysk spadnie do tylu % (None = wyłączone; tylko
    # portfele, które ustawią to w strategy_exits - 6.10: safety_s6)
    breakeven_after_tp1_pct: float | None = None
    time_stop_minutes: int = 240          # martwa pozycja zamykana po tylu minutach
    time_stop_min_move_pct: float = 10.0  # ...jeśli nie ruszyła się o tyle w górę
    liquidity_drain_exit_pct: float = 40.0  # płynność spadła o tyle od wejścia => ucieczka
    recheck_rug_every_min: int = 10       # ponowny skan rugcheck otwartych pozycji
    # --- dodatkowe niezależne wyjścia (każde można włączyć/wyłączyć osobno) ---
    exit_dev_sell: bool = True            # twórca sprzedał >= dev_sell_drop_pct swojego salda od wejścia
    dev_sell_drop_pct: float = 50.0
    exit_momentum_decay: bool = False     # WYŁĄCZONE: hipoteza do przetestowania (sprzedający dominują w 5 min)
    momentum_decay_max_pnl_pct: float = 20.0   # ...i pozycja nie jest już wyraźnie na plusie
    momentum_decay_min_txns: int = 20
    momentum_decay_buy_ratio: float = 0.35
    momentum_decay_ch5_pct: float = -5.0
    exit_smart_money_sell: bool = True    # działa tylko gdy wpiszesz smart_wallets: ktoś z nich sprzedaje = wychodzimy

    # ---------- latencja i realizm wejścia ----------
    entry_latency_s: float = 8.0          # opóźnienie od sygnału do transakcji; fill = NOWE kwotowanie po tym czasie
    # (0 = wyłączone). Cena, która ucieka > max_slippage_pct przed wykonaniem = nieudane wejście
    # UWAGA: dane z pollingu mają rozdzielczość sekund, nie milisekund - symulujemy opóźnienie w sekundach.

    # ---------- strategie (każda = osobny wirtualny portfel na tych samych danych; patrz strategies.py) ----------
    # Każdą strategię włączasz/wyłączasz usuwając ją z tej listy (dostępne: patrz strategies.REGISTRY).
    # 7.10.2026: smart_money_only WYŁĄCZONY (stał na $44, a smart money wg analizy praktycznie nie istnieje - 1 portfel
    # na 3731 pierwszych kupujących); jego historia zostaje w bazie.
    strategies: tuple = ("hybrid", "momentum_only", "buyer_accel_only", "safety_only",
                         "random_eligible",
                         # v0.7: eksperyment 2x2 "filtr zmienności x szerokość stopa" (+ wariant ze stopem awaryjnym)
                         "safety_wide", "lowvol", "lowvol_wide", "lowvol_catastrophic",
                         # v0.8: wszystkie reguły wykluczenia naraz (zob. strategies.strict)
                         "strict",
                         # 4.10.2026: szybki time stop (odtworzenie 160 wejść: straty na stopach -45..-75%, obie połowy)
                         "safety_ts5", "lowvol_ts10", "safety_s6",
                         # 7.10.2026: osobne portfele - każdy zmienia JEDNO względem safety_only (kryteria oceny ustalone
                         # z góry: analizy/KRYTERIA_NA_ZYWO.md): szybki stop z odczytu puli co 2 s (fastexit.py),
                         # tylko bundle startu >= 30%, bez kopii aktywnego tokena / skopiowanej grafiki (launchcheck.py)
                         "safety_fast", "safety_bundle30", "safety_nocopy",
                         # 7.10.2026 wieczorem: wejścia jak random_eligible (ten sam hash mintu), szybki stop z odczytu puli
                         # i wyjście S6 - jedyna strategia bliska zeru brutto + dwie zmiany wyjścia, które w danych pomagały
                         "random_fast_s6")
    fast_stop_portfolios: tuple = ("safety_fast", "random_fast_s6")
    fast_stop_poll_s: float = 2.0
    random_eligible_pct: int = 25         # random_eligible: losowo ~25% tokenów, które przeszły twarde filtry
    # Filtr zmienności (strategie lowvol*): ATR 1-min przy wejściu (w % ceny, liczony jak w indicators.py).
    # Hipoteza z danych 1-2.10.2026 (49 wejść): ATR >= 20% -> 8/15 rugów, < 20% -> 4/32. Próg ZAMROŻONY - ocenia go
    # dopiero przyszłość (te same dane posłużyły do jego znalezienia).
    lowvol_max_atr_pct: float = 20.0
    # Nadpisania parametrów wyjścia per strategia (reszta jak w sekcji "wyjścia"). Dzięki temu wejścia są identyczne,
    # a różni się tylko wyjście - np. safety_only vs safety_wide mierzy wyłącznie efekt szerokości stopa.
    # Skąd -40%: zwycięzcy (wejścia, które doszły do +50%) schodzili przed wzrostem w medianie do -26%, więc -25% wyrzucał
    # połowę z nich. -60% = tylko stop awaryjny (wariant najbliższy "bez stopa", ale z ochroną przed rugiem do zera).
    strategy_exits: dict = field(default_factory=lambda: {
        "safety_wide": {"stop_loss_pct": 40.0},
        "lowvol_wide": {"stop_loss_pct": 40.0},
        "lowvol_catastrophic": {"stop_loss_pct": 60.0},
        # wyjście, gdy po 5 min nie jesteśmy na plusie / po 10 min poniżej +5% (zastępuje time stop 4 h; działa przed TP1)
        "safety_ts5": {"time_stop_minutes": 5, "time_stop_min_move_pct": 0.0},
        "lowvol_ts10": {"time_stop_minutes": 10, "time_stop_min_move_pct": 5.0},
        # 6.10 (analizy/scaling_out.py, schemat S6): 1/3 przy +20%, potem stop na wejściu, dalej 1/3 @+100%, reszta @+300%,
        # trailing 20% po pierwszym TP; te same wejścia co safety_only - porównanie w parach mierzy tylko efekt wyjścia
        "safety_s6": {"take_profit_levels": ((20.0, 0.33), (100.0, 0.33), (300.0, 0.34)),
                      "breakeven_after_tp1_pct": 0.0},
        "random_fast_s6": {"take_profit_levels": ((20.0, 0.33), (100.0, 0.33), (300.0, 0.34)),
                           "breakeven_after_tp1_pct": 0.0},
    })
    # Strategie TYLKO-SYGNAŁOWE: bez portfela i kapitału, zapisują sygnały (tabela signals), a `bot.py calibrate`
    # porównuje zwrot ceny wskazanych tokenów z grupami kontrolnymi. Tanie hipotezy z analizy technicznej (świece 1 min).
    signal_strategies: tuple = ("breakout_volume", "breakout_retest", "vwap_momentum", "ema_trend_rsi",
                                "bollinger_breakout", "vwap_reversion", "mature_calm",
                                # v0.8: każda reguła wykluczenia osobno (safety_only bez jednego typu tokenów)
                                "skip_below_vwap", "skip_block_buys", "skip_spike_5m", "skip_accel_3x", "skip_young_60m")
    # Strategia Gemini (llm.py), tylko sygnały: model ocenia każdy token po twardych filtrach. "gemini" = decyzja BUY,
    # "gemini_hc" = BUY z pewnością >= gemini_hc_confidence. Bez klucza GEMINI_API_KEY nic nie robi. Darmowy plan Gemini
    # mieści się z zapasem (~80 czystych tokenów na dobę). Model przypięty na stałe (nie alias *-latest), żeby wyniki
    # nie zmieniały się po cichu; 2.5-flash-lite nie jest już dostępny dla nowych kont (4.10.2026). Modele "myślące"
    # (np. gemini-3.5-flash) zużywają limit odpowiedzi na myślenie i ucinają JSON - przed zmianą sprawdź `python llm.py`.
    gemini_enabled: bool = True
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_rpm: int = 10
    gemini_max_per_day: int = 400
    gemini_timeout_s: float = 20.0
    gemini_hc_confidence: int = 70
    llm_strategies: tuple = ("gemini", "gemini_hc")
    use_ohlcv: bool = True                # świece minutowe GeckoTerminal -> wskaźniki TA jako cechy (+1 zapytanie na token)
    strategy_thresholds: dict = field(default_factory=lambda: {
        "momentum_only": 70.0, "flow_only": 80.0, "buyer_accel_min_buyers": 8, "buyer_accel_min_ratio": 1.5,
        "breakout_volume_ratio": 2.0, "rsi_momentum_lo": 50.0, "rsi_momentum_hi": 70.0, "ema_trend_volume_ratio": 1.2,
        "bb_volume_z": 1.5, "vwap_reversion_dist": -0.05, "vwap_reversion_buy_ratio": 0.55,
        # mature_calm (zamrożone 2.10.2026): token >= 60 min życia i poza szczytem aktywności (txns 5 min < 80;
        # najwyższy kwartyl aktywności miał 37% upadków po 6 h)
        "mature_min_age": 60.0, "mature_max_txns_m5": 80.0,
        # v0.8 reguły wykluczenia (zamrożone 2.10.2026 na 50 wejściach - ocenia je dopiero przyszłość):
        "max_block_share": 0.2, "max_spike_5m": 30.0, "max_buyer_accel": 3.0, "min_age_strict": 60.0})
    snapshot_every_s: int = 60            # szereg czasowy obserwowanych tokenów (także odrzuconych)

    # ---------- archiwum świec i badanie wyjść (bot.py exits) ----------
    # Dla każdego tokena z sygnałem (także strategii tylko-sygnałowych) bot po archive_after_h pobiera świece 1-min
    # (1 zapytanie GeckoTerminal) - z nich liczymy MAE/MFE, "zabitych zwycięzców" i odtwarzamy warianty wyjść.
    archive_candles: bool = True
    archive_after_h: float = 6.0          # czekamy, aż minie okno, które chcemy analizować
    archive_every_min: int = 10
    archive_batch: int = 6                # maks. pobrań na jeden przebieg (oszczędnie z limitem GeckoTerminal)
    # Po przerwie w działaniu (wyłączony komputer) otwarte pozycje zamykamy po ostatnim znanym kursie, zamiast
    # wyceniać je po godzinach (stopy w przerwie nie działały, więc taki wynik byłby przypadkowy).
    downtime_close_min: int = 10

    # ---------- kontrola ryzyka ----------
    # v0.9: w PAPER dzienny limit strat i pauza po serii strat są WYŁĄCZONE: 2.10 od 17:52 do 2:00 stały przez nie
    # hybrid, momentum_only, smart_money_only i safety_only, a nowe strategie handlowały dalej - porównanie z grupą
    # kontrolną przestawało być uczciwe. W LIVE działają zawsze; risk_limits_in_paper=True włącza je też w PAPER.
    risk_limits_in_paper: bool = False
    daily_loss_limit_pct: float = 10.0    # po takim dziennym spadku kapitału stop z nowymi wejściami
    max_consecutive_losses: int = 4       # potem pauza
    pause_after_losses_min: int = 60
    # v0.9: po wyjściu z tokena ta sama strategia nie kupuje go ponownie przez tyle godzin (0 = bez blokady).
    # Dane 1-2.10: ponowne wejścia po ZYSKOWNYM wyjściu - 15 szt., 14 stratnych, razem -$213. Blokada po decyzji trwała
    # 30 min, a pozycja dłużej, więc bot wracał do tokena nawet minutę po sprzedaży.
    reentry_block_h: float = 6.0
    # v0.10 "tylko pierwsze spojrzenie": token wolno kupić tylko w ciągu tylu minut od PIERWSZEGO wejścia któregokolwiek
    # portfela w ten token (0 = wyłączone). Dane do 4.10: późne wejścia (mediana 1-2 h po pierwszym) były gorsze w 9 z 11
    # strategii, ~20% transakcji, razem -$1,174 (np. safety_only -32% vs -6%, momentum_only -28% vs -9%).
    first_look_window_min: float = 10.0

    # ---------- decyzja ----------
    # v0.5: decyzja z DWÓCH osi. Wejście = Opportunity >= opportunity_min ORAZ Risk <= risk_max ORAZ brak veto.
    # Skala: wynik = 50 +/- 50*tanh(suma_punktów / axis_scale). Progi to PUNKT STARTOWY dobrany tak, by w przybliżeniu
    # zachować dotychczasową selektywność (opportunity_min=70 ~ suma punktów okazji >= 29; risk_max=20 ~ suma
    # punktów "bezpieczeństwa" >= 42). Nie są zoptymalizowane - kalibrować po zebraniu danych (`bot.py calibrate`).
    axis_scale: float = 60.0
    opportunity_min: float = 70.0
    risk_max: float = 20.0
    buy_threshold: float = 68.0           # dawny wynik łączny - używa go tylko strategia score_no_gates i porównania
    weights: dict = field(default_factory=lambda: {
        "safety": 0.15,      # rugcheck/holderzy/autorytety/LP (tu działa głównie bramka, nie punkty)
        "liquidity": 0.20,   # głębokość, FDV/liq, obrót
        "momentum": 0.35,    # zmiany ceny, presja kupna - to decyduje, CZY kupować
        "social": 0.10,      # strony, X, telegram, imposterzy
        "flow": 0.20,        # liczba transakcji, wash trading, portfele
    })
    # Bramki: nawet wysoki wynik łączny nie kupuje, jeśli kategoria jest poniżej minimum.
    # (v0.2: bezpieczeństwo 100/100 "kompensowało" fatalne momentum i bot kupował spadające/przegrzane tokeny)
    min_category_scores: dict = field(default_factory=lambda: {"momentum": 55.0})
    min_buy_pressure_h1: float = 0.35     # odsetek transakcji kupna w 1h; niżej = wyprzedaż, veto do ponownej oceny
    reject_cooldown_min: int = 30         # jak długo nie analizować odrzuconego tokena
    watch_max_min: int = 90               # tyle czasu obserwujemy "za młode" tokeny

    # ---------- twarde veto: bezpieczeństwo (rug pull) ----------
    veto_mint_authority: bool = True      # dev może dodrukować tokeny
    veto_freeze_authority: bool = True    # dev może zamrozić Twój portfel
    veto_if_rugged_flag: bool = True
    max_transfer_fee_pct: float = 5.0     # token z podatkiem transferu
    max_top1_holder_pct: float = 20.0     # największy holder (bez puli LP)
    max_top10_holder_pct: float = 60.0
    max_creator_balance_pct: float = 15.0
    serial_launcher_24h: int = 5          # twórca z >=5 startami w 24 h (wg strumienia PumpPortal) = ryzyko
    serial_launcher_veto_24h: int = 20    # >=20 startów w 24 h = veto (farma tokenów)
    min_lp_locked_pct: float = 0.0        # <10% zablokowane to duża kara, nie veto (pump.fun palą LP)
    max_danger_risks: int = 2             # ile flag "danger" z rugcheck = veto
    max_rugcheck_norm_score: float = 70.0  # znormalizowany wynik ryzyka (0-100, więcej = gorzej)
    require_rugcheck: bool = True         # bez raportu rugcheck nie kupujemy

    # ---------- twarde veto: rynek ----------
    # v0.5: próg obniżony do 5k - to tylko DOLNA GRANICA zbierania danych. Czy kubełek 5-10k ma sens, pokażą osobne
    # wyniki w `bot.py report` / `calibrate` (kubełki: 5-10k, 10-25k, 25-50k, 50-100k, 100k+), nie nasze przeczucie.
    min_liquidity_usd: float = 5_000.0
    min_age_minutes: float = 15.0         # pierwsze minuty = snajperzy i boty
    max_age_hours: float = 72.0           # starsze nie są już "świeżym memem"
    min_txns_h1: int = 60
    min_volume_h1_usd: float = 5_000.0
    max_mcap_usd: float = 50_000_000.0
    min_mcap_usd: float = 15_000.0
    max_fdv_to_liq: float = 150.0         # FDV / płynność; wyżej = cienka pula pod dużą wyceną
    max_turnover_h24: float = 60.0        # wolumen24h / płynność; wyżej podejrzane na wash trading
    max_m5_drop_pct: float = -12.0        # spadający nóż
    max_h1_drop_pct: float = -10.0        # v0.2: -35 -> -10 (kupowane po -12/-22/-26% w 1h traciły)
    max_h1_pump_pct: float = 100.0        # v0.2: 400 -> 100 (6 z 6 wejść po +103..+219% w 1h skończyło stratą)
    max_h24_pump_pct: float = 1500.0
    max_slippage_pct: float = 4.0         # szacowany slippage naszej pozycji
    allowed_quote_symbols: tuple = ("SOL", "WSOL", "USDC", "USDT")
    allowed_dexes: tuple = ("raydium", "pumpswap", "meteora", "orca", "pumpfun")

    # ---------- Jupiter (darmowe API kwotowań): test honeypota i realne fille ----------
    use_jupiter: bool = True
    jupiter_url: str = "https://lite-api.jup.ag/swap/v1/quote"
    jupiter_rpm: int = 55
    jupiter_slippage_bps: int = 500
    require_jupiter: bool = False         # True = bez potwierdzonej trasy sprzedaży nie kupujemy
    max_roundtrip_loss_pct: float = 8.0   # kupno+sprzedaż od razu: strata > tyle = podatek/cienka pula/honeypot
    max_price_mismatch_pct: float = 15.0  # cena z Jupitera vs DexScreener (nieświeże dane / manipulacja)
    use_jupiter_fills: bool = True        # paper: fille z realnych kwotowań Jupitera zamiast modelu x*y=k

    # ---------- GeckoTerminal (darmowe): holderzy, gt_score, trendy, historia transakcji ----------
    use_gecko: bool = True
    gecko_rpm: int = 20                   # darmowy limit ~30/min
    min_holders: int = 100
    trades_top3_veto_pct: float = 70.0    # 3 portfele robią >70% wolumenu = boty / wash trading
    trades_top3_warn_pct: float = 50.0
    trades_wash_wallet_pct: float = 35.0
    whale_sell_pct_of_liq: float = 3.0    # pojedyncza sprzedaż > 3% płynności puli
    trending_refresh_min: int = 5
    smart_wallets: tuple = ()             # portfele, za którymi chcesz podążać (wklej adresy) - bonus gdy kupują
    # --- silnik rankingu portfeli (wallets.py): własne dane z transakcji pul, bez płatnego API ---
    wallet_track_max: int = 100           # ile najlepszych portfeli śledzimy (50-200 wg założeń)
    wallet_min_closed: int = 3            # minimum domkniętych pozycji, żeby w ogóle ocenić portfel
    wallet_min_quality: float = 65.0      # minimalna jakość (0-100), by trafić do śledzonych
    wallet_refresh_min: int = 30
    wallet_copy_latency_s: int = 20       # opóźnienie w symulacji "gdybyśmy kopiowali ten zakup"
    convergence_window_s: int = 900       # okno, w którym kilku śledzonych portfeli kupuje ten sam token
    smart_min_wallets: int = 2            # strategia smart_money_only: min. niezależnych portfeli
    # --- adapter płatnych/zewnętrznych danych o portfelach (opcjonalny) ---
    wallet_provider: str = "none"         # "none" | "helius" (klucz w zmiennej środowiskowej HELIUS_API_KEY)
    funding_trigger_share: float = 0.2    # analiza funderów tylko gdy >=20% wolumenu kupna to bloki z >=3 portfelami
    funding_max_lookups: int = 5          # maks. nowych zapytań o fundatora na jeden token
    bad_wallet_veto: bool = True          # twórca tokena z listy rugów = veto (lista uczy się sama)

    # ---------- szybki nadzór nad pozycjami ----------
    position_loop_seconds: int = 10       # sprawdzanie otwartych pozycji (skan nowych: loop_seconds)
    exit_probe_seconds: int = 20          # kwotowanie sprzedaży pozycji przez Jupiter = WYCENA pod stopy i TP
    exit_gap_pct: float = 50.0            # wartość sprzedaży wg Jupitera < 50% wartości z ceny => wyjście
    unsellable_probes: int = 3            # tyle razy z rzędu brak trasy sprzedaży => uznajemy za honeypot/rug

    # ---------- śledzenie wyników decyzji (kalibracja) ----------
    track_outcomes: bool = True
    outcome_horizons_h: tuple = (1, 6, 24)
    outcome_check_min: int = 15

    # ---------- listy ręczne ----------
    blacklist_mints: tuple = ()           # nigdy nie kupuj
    whitelist_mints: tuple = ()           # zawsze pomijaj veto rynku (NIE bezpieczeństwa)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        cfg = cls()
        p = path or BASE_DIR / "config.json"
        if p.exists():
            raw = json.loads(p.read_text(encoding="utf-8"))
            names = {f.name for f in fields(cls)}
            for k, v in raw.items():
                if k in names:
                    setattr(cfg, k, v)
                else:
                    print(f"[config] nieznane pole w config.json: {k}")
        Path(cfg.db_path).parent.mkdir(parents=True, exist_ok=True)
        return cfg
