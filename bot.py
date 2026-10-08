"""Bot do paper-tradingu memecoinów na Solanie.

Użycie:
    python bot.py run [--mode RESEARCH|PAPER]   # pętla ciągła (Ctrl+C kończy); RESEARCH = tylko dane i sygnały
    python bot.py once               # jeden obieg i koniec
    python bot.py analyze <MINT>     # pełny raport oceny jednego tokena (nic nie kupuje)
    python bot.py report             # metryki wyników: porównanie strategii, koszty, kubełki płynności/mcap
    python bot.py calibrate          # co by było gdyby: skuteczność progów i veto na zebranych danych
    python bot.py features           # które cechy korelują z wynikiem po 6 h (korelacja Spearmana)
    python bot.py wallets            # portfele, za którymi warto podążać (empiryczny wynik ich zakupów)
    python bot.py exits [--signals]  # MAE/MFE wejść, "zabici zwycięzcy", odtworzenie wariantów wyjść na świecach
    python bot.py entries [--min-age 60]  # czy moment wejścia ma znaczenie: zwroty po 1-60 min, reguły TA co minutę (retro)
    python bot.py reset              # archiwizuje bazę i zaczyna z czystą
"""
from __future__ import annotations

import argparse
import collections
import statistics
import sys
import threading
import time
from pathlib import Path

import analysis
import fastexit
import features as feat
import indicators
import launchcheck
import llm
import strategies
from config import Config
from paper import Portfolio, Position
from sources import DexScreener, GeckoTerminal, Jupiter, RugCheck, SolanaRPC
from storage import Storage
from stream import PumpStream
from wallets import WalletEngine, funding_check, make_provider

MODES = ("RESEARCH", "PAPER", "LIVE")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RUG_EXITS = {"liq_drain", "no_data_rug", "rug_recheck", "unsellable"}
WSOL = "So11111111111111111111111111111111111111112"
# zasady portfeli: zmiana któregokolwiek = nowa "epoka" (report porównuje strategie także od ostatniej zmiany)
RULE_KEYS = ("position_usd", "position_pct", "max_open_positions", "max_exposure_pct", "risk_limits_in_paper",
             "daily_loss_limit_pct", "max_consecutive_losses", "reentry_block_h", "stop_loss_pct", "take_profit_levels",
             "trailing_stop_pct", "time_stop_minutes", "time_stop_min_move_pct", "strategy_exits", "first_look_window_min")


def log(msg: str):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


class Bot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        cfg.mode = cfg.mode.upper()
        if cfg.mode not in MODES:
            raise SystemExit(f"nieznany tryb '{cfg.mode}' (dozwolone: {', '.join(MODES)})")
        if cfg.mode == "LIVE":
            raise SystemExit("Tryb LIVE (prawdziwe transakcje) nie jest zaimplementowany - świadomie: wymaga portfela, "
                             "zarządzania kluczami i osobnej decyzji. Używaj PAPER albo RESEARCH.")
        unknown = [n for n in cfg.strategies if n not in strategies.REGISTRY]
        if unknown:
            log(f"UWAGA: nieznane strategie w config (pomijam): {unknown}; dostępne: {sorted(strategies.REGISTRY)}")
        self.store = Storage(cfg.db_path)
        self.portfolios: dict[str, Portfolio] = {n: Portfolio(cfg, self.store, n, cfg.strategy_exits.get(n))
                                                 for n in cfg.strategies if n in strategies.REGISTRY}
        if not self.portfolios:
            raise SystemExit("Brak włączonych strategii (Config.strategies).")
        self.llm = llm.GeminiAdvisor(cfg, self.store)
        self.llm_ref, self.llm_ref_ts = {}, 0.0   # próbka odniesienia do percentyli w prompcie Gemini
        self.llm_seen: dict[str, float] = {}     # mint -> kiedy ostatnio pytaliśmy model (bez powtórek w oknie cooldownu)
        # strategie modelu rejestrujemy dopiero z kluczem - inaczej okno porównań zaczęłoby się, zanim padł 1. sygnał
        self.store.register_strategies(list(cfg.strategies) + list(cfg.signal_strategies)
                                       + (list(cfg.llm_strategies) if self.llm.enabled else []))
        self.store.mark_rules({k: getattr(cfg, k) for k in RULE_KEYS})
        self.pf = self.portfolios.get("hybrid") or next(iter(self.portfolios.values()))
        self.engine = WalletEngine(cfg, self.store)
        self.provider = make_provider(cfg)
        self.stream = PumpStream() if cfg.use_pumpportal else None
        self.last_decision_id: dict[str, int] = {}
        self.dex, self.rug, self.rpc = DexScreener(cfg), RugCheck(cfg), SolanaRPC(cfg)
        self.jup, self.gecko = Jupiter(cfg), GeckoTerminal(cfg)
        self.blacklist = self.store.blacklisted() | set(cfg.blacklist_mints)
        self.bad_wallets = self.store.bad_wallets()
        self.cooldown: dict[str, float] = {}     # mint -> do kiedy nie analizować
        self.watch: dict[str, float] = {}        # mint -> kiedy zaczęliśmy obserwować
        self.trending: list[str] = []
        self._trending_ts = 0.0
        self._outcomes_ts = 0.0
        self.prices: dict[str, float] = {}       # ostatnie znane ceny (wycena kapitału)
        self.exec_marks: dict[str, tuple] = {}   # mint -> (czas, cena wykonalna wg Jupitera)
        self.last_probe: dict[str, float] = {}   # mint -> kiedy ostatnio kwotowaliśmy sprzedaż
        self.unsell: dict[str, int] = {}         # mint -> ile kolejnych kwotowań bez trasy sprzedaży
        self.last_audit: dict[str, float] = {}
        self.last_smart: dict[str, float] = {}
        self.snap_ts: dict[str, float] = {}      # mint -> kiedy ostatni snapshot
        self.logged_at: dict[str, float] = {}    # mint -> kiedy ostatnio zapisaliśmy decyzję (bez duplikatów)
        self.logged_dec: dict[str, str] = {}     # mint -> jaka to była decyzja (zmiana decyzji = nowy wpis)
        self.source: dict[str, str] = {}         # mint -> skąd go odkryliśmy (graduation/profile/boost/top_boost)
        self._sellq: dict[str, tuple] = {}       # mint -> (czas, ilość, USD) ostatniego kwotowania sprzedaży
        self._archive_ts = 0.0
        self.market: dict = {}                   # reżim rynku (cechy do badań): nastrój nowych memecoinów, trend SOL
        self._sol_ts = 0.0
        self.loop_no = 0
        self.fast_lock = threading.RLock()       # 7.10: wątek szybkiego stopu (fastexit.py) vs główna pętla
        self.fast_names = tuple(n for n in getattr(cfg, "fast_stop_portfolios", ()) if n in self.portfolios)
        self.launch = launchcheck.LaunchCheck(Path(cfg.db_path).resolve().parent)   # bundle / kopie (safety_bundle30, safety_nocopy)
        if cfg.use_jupiter and cfg.use_jupiter_fills:
            for p in self.portfolios.values():
                p.sell_quoter = self.quote_sell

    # ------------------------------------------------------------ Jupiter
    def quote_sell(self, pos: Position, qty: float):
        """Realna wartość sprzedaży (USD) wg Jupitera albo None (wtedy działa model z paper.py).

        Gdy kilka portfeli wychodzi z tego samego tokena w tej samej chwili (ten sam stop w kilku strategiach),
        używamy jednego świeżego (<= 5 s) kwotowania przeliczonego proporcjonalnie, zamiast pytać Jupitera N razy -
        kolejne zapytania czekałyby na limit i wyjścia ostatnich portfeli byłyby sztucznie spóźnione."""
        if pos.decimals is None:
            return None
        now = time.time()
        c = self._sellq.get(pos.mint)
        if c and now - c[0] <= 5 and c[1] > 0 and 0.5 <= qty / c[1] <= 2:
            return c[2] * qty / c[1]
        state, d = self.jup.sell_usdc(pos.mint, int(qty * 10 ** pos.decimals))
        if state != "ok":
            return None
        value = float(d["outAmount"]) / 1e6
        self._sellq[pos.mint] = (now, qty, value)
        return value

    def fill_quote(self, mint: str, size: float, ctx: dict):
        """Wejście z symulowaną latencją: po entry_latency_s pytamy Jupitera o NOWE kwotowanie i po nim wypełniamy.
        Zwraca (ilość_tokenów | None, info). None = transakcja by się nie udała (cena uciekła ponad max_slippage_pct)."""
        cfg = self.cfg
        base = ctx.get("buy_qty")
        info = {"expected_slip_pct": round(analysis.est_slippage_pct(size, ctx.get("liq", 0)), 2)}
        if not (cfg.use_jupiter and cfg.entry_latency_s > 0 and base):
            return base, info
        time.sleep(cfg.entry_latency_s)
        state, d = self.jup.buy_usdc(mint, size)
        info["latency_s"] = cfg.entry_latency_s
        if state != "ok":
            info["failed"] = "brak kwotowania po opóźnieniu"
            return None, info
        qty = float(d["outAmount"]) / 10 ** ctx["decimals"]
        move = (1 - qty / base) * 100          # >0 = po opóźnieniu dostajemy mniej tokenów niż w chwili sygnału
        info.update({"signal_qty": base, "fill_qty": qty, "price_move_pct": round(move, 2)})
        if move > cfg.max_slippage_pct:
            info["failed"] = f"cena uciekła o {move:.1f}% w {cfg.entry_latency_s:.0f} s"
            return None, info
        return qty, info

    # ------------------------------------------------------------ odkrywanie
    def tag_source(self, mints, source: str):
        """Zapamiętuje PIERWSZE źródło, z którego token do nas trafił (cecha 'source' do badań)."""
        for m in mints:
            self.source.setdefault(m, source)
        if len(self.source) > 50_000:            # ograniczenie pamięci: zostaw nowszą połowę
            for k in list(self.source)[:25_000]:
                del self.source[k]

    def discover(self) -> list[str]:
        held = {m for p in self.portfolios.values() for m in list(p.positions)}
        profiles, boosts = self.dex.latest_profiles(), self.dex.latest_boosts()
        self.tag_source(profiles, "profile")
        self.tag_source(boosts, "boost")
        mints = list(dict.fromkeys(profiles + boosts))
        if self.loop_no % 10 == 1:                # rzadziej: najczęściej boostowane
            top = self.dex.top_boosts()
            self.tag_source(top, "top_boost")
            mints += top
        now = time.time()
        self.watch = {m: t for m, t in self.watch.items() if now - t < self.cfg.watch_max_min * 60}
        mints += list(self.watch)
        return [m for m in dict.fromkeys(mints)
                if m not in self.blacklist and m not in held and self.cooldown.get(m, 0) <= now]

    def refresh_trending(self):
        if self.cfg.use_gecko and time.time() - self._trending_ts > self.cfg.trending_refresh_min * 60:
            self._trending_ts = time.time()
            self.trending = self.gecko.trending("1h") or self.trending

    def update_market(self, best: dict):
        """Reżim rynku jako CECHY (nie wpływają na decyzje - najpierw dane, potem ewentualny filtr):
        mkt_* = jak radzą sobie tokeny z bieżącego obiegu (udział rosnących w 1 h, mediana zmiany 1 h),
        sol_* = trend SOL (najpłynniejsza para SOL/USDC, odświeżana co 5 min)."""
        chs = [float((p.get("priceChange") or {}).get("h1") or 0) for p in best.values() if p]
        if len(chs) >= 10:
            self.market.update({"mkt_breadth_h1": sum(c > 0 for c in chs) / len(chs),
                                "mkt_median_h1": statistics.median(chs), "mkt_n": len(chs)})
        if time.time() - self._sol_ts >= 300:
            self._sol_ts = time.time()
            stable = [p for p in self.dex.pairs_for_tokens([WSOL]).get(WSOL, [])
                      if (p.get("quoteToken") or {}).get("symbol") in ("USDC", "USDT")]
            p = self.dex.best_pair(stable)
            if p:
                ch = p.get("priceChange") or {}
                self.market.update({f"sol_ch_{w}": float(ch.get(w) or 0) for w in ("h1", "h6", "h24")})

    def snapshot(self, mint: str, pair: dict, held=False):
        if time.time() - self.snap_ts.get(mint, 0) >= self.cfg.snapshot_every_s:
            self.snap_ts[mint] = time.time()
            self.store.log_snapshot(mint, pair, held)

    # ------------------------------------------------------------ audyt bezpieczeństwa
    def audit(self, mint: str):
        """RugCheck (+ RPC jako zapas) + lista rugów. Zwraca (findings, ctx z twórcą, decimals i raportem)."""
        report = self.rug.report(mint)
        rpc = None
        ctx: dict = {"wallets": [], "decimals": None, "report": report, "creator_balance_pct": None}
        if report:
            ctx["wallets"] = [report.get("creator")]
            ctx["decimals"] = (report.get("token") or {}).get("decimals")
            ctx["creator_balance_pct"] = feat.holder_metrics(report).get("creator_pct")
        elif self.cfg.use_rpc_fallback:
            rpc = {"mint": self.rpc.mint_info(mint), "holders": self.rpc.largest_holders(mint),
                   "supply": self.rpc.supply(mint)}
            if not rpc["mint"]:
                rpc = None
            else:
                ctx["decimals"] = rpc["mint"].get("decimals")
        f = analysis.rug_checks(self.cfg, report, rpc)
        f += analysis.creator_checks(self.cfg, ctx["wallets"], self.bad_wallets)
        return f, ctx

    # ------------------------------------------------------------ ocena jednego tokena
    def evaluate(self, mint: str, pair: dict, prices: dict, full=False):
        """Zwraca (Verdict, ctx). Etapy od najtańszego; veto kończy ocenę (full=True ocenia wszystko - dla `analyze`).
        ctx['features'] = wektor cech liczbowych (do dziennika i badań) - zapisywany także dla odrzuconych."""
        cfg = self.cfg
        liq = float((pair.get("liquidity") or {}).get("usd") or 0)
        size = self.pf.entry_size(prices, liq) or cfg.start_balance_usd * cfg.position_pct
        ctx: dict = {"size": size, "liq": liq, "wallets": [], "decimals": None, "buy_qty": None,
                     "report": None, "creator_balance_pct": None}
        data: dict = {"trades": None, "gecko": None, "extra": dict(self.market)}
        if self.source.get(mint):
            data["extra"]["source"] = self.source[mint]

        def finish(findings):
            ctx["features"] = feat.build(pair, ctx.get("report"), data["trades"], data["gecko"], data["extra"])
            return analysis.decide(cfg, findings, mint), ctx

        def stop(f):
            return any(x.veto for x in f) and not full

        # etap 1: dane DexScreenera
        findings = analysis.market_checks(cfg, pair, size)
        if stop(findings):
            return finish(findings)

        # etap 2: klony o tym samym symbolu + audyt RugCheck + lista rugów
        sym = (pair.get("baseToken") or {}).get("symbol", "")
        findings = analysis.market_checks(cfg, pair, size, self.dex.search(sym) if sym else None)
        sf, actx = self.audit(mint)
        ctx.update(actx)
        findings += sf
        creator = next((w for w in ctx["wallets"] if w), None)
        if creator:        # historia twórcy z własnego strumienia PumpPortal
            hist = self.store.creator_history(creator, exclude_mint=mint)
            findings += analysis.creator_history_checks(cfg, hist)
            data["extra"].update({"creator_launches_7d": hist["launches"], "creator_launches_24h": hist["launches_24h"],
                                  "creator_graduated": hist["graduated"]})
        if stop(findings):
            return finish(findings)

        # etap 3: Jupiter - czy da się sprzedać i ile kosztuje przejście w obie strony
        if cfg.use_jupiter:
            price = float(pair.get("priceUsd") or 0)
            buy = self.jup.buy_usdc(mint, size)
            sell = self.jup.sell_usdc(mint, int(buy[1]["outAmount"])) if buy[0] == "ok" else None
            findings += analysis.honeypot_checks(cfg, buy, sell, size, price, ctx["decimals"])
            if buy[0] == "ok" and ctx["decimals"] is not None:
                ctx["buy_qty"] = float(buy[1]["outAmount"]) / 10 ** ctx["decimals"]
                if sell and sell[0] == "ok":
                    data["extra"]["roundtrip_loss_pct"] = (1 - float(sell[1]["outAmount"]) / 1e6 / size) * 100
            data["extra"]["expected_slip_pct"] = analysis.est_slippage_pct(size, liq)
            if stop(findings):
                return finish(findings)

        # etap 4: GeckoTerminal - holderzy, trendy, historia transakcji puli
        if cfg.use_gecko:
            info = self.gecko.token_info(mint)
            data["gecko"] = info
            rank = self.trending.index(mint) if mint in self.trending else None
            findings += analysis.gecko_checks(cfg, info, rank)
            if rank is not None:
                data["extra"]["trending_rank"] = rank
            if info and info.get("developer_address"):
                ctx["wallets"].append(info["developer_address"])
                findings += analysis.creator_checks(cfg, [info["developer_address"]], self.bad_wallets)
            if pair.get("pairAddress"):
                trades = self.gecko.pool_trades(pair["pairAddress"])
                data["trades"] = trades
                findings += analysis.trade_checks(cfg, trades, liq)
                self.engine.ingest(mint, trades)                    # dane do rankingu portfeli
                conv = self.engine.convergence(trades)              # smart money: konwergencja śledzonych portfeli
                ctx["conv"] = conv
                data["extra"].update({k: v for k, v in conv.items() if k != "smart_wallets"})
                findings += analysis.smart_checks(cfg, conv)
                # selektywnie: źródło finansowania sprawdzamy dopiero, gdy trafi się podejrzany klaster z jednego bloku
                tm = feat.trade_metrics(trades)
                ff, finfo = funding_check(cfg, self.provider, self.store, tm.get("coordinated_wallets", []),
                                          tm.get("same_block_buy_share", 0.0))
                findings += ff
                data["extra"].update(finfo)
                if cfg.use_ohlcv:       # wskaźniki TA tylko jako cechy do badań (nie wchodzą do punktacji)
                    data["extra"].update(indicators.compute(self.gecko.ohlcv(pair["pairAddress"]) or []))
        return finish(findings)

    # ------------------------------------------------------------ nadzór nad pozycjami (szybka pętla)
    def mark_rug(self, mint: str, wallets, reason: str):
        wallets = [w for w in wallets if w]
        if wallets:
            self.store.add_bad_wallets(wallets, mint, reason)
            self.bad_wallets |= set(wallets)
            log(f"lista rugów: +{len(wallets)} portfel(e) ({reason})")

    def manage_positions(self):
        cfg = self.cfg
        held: dict[str, list] = {}
        for pf in self.portfolios.values():
            for mint, pos in list(pf.positions.items()):
                held.setdefault(mint, []).append((pf, pos))
        if not held:
            return
        best = {m: self.dex.best_pair(ps) for m, ps in self.dex.pairs_for_tokens(list(held)).items()}
        now = time.time()
        for mint, plist in held.items():
            pair = best.get(mint)
            if pair:
                self.prices[mint] = float(pair.get("priceUsd") or 0)
                self.snapshot(mint, pair, held=True)
            sym = plist[0][1].symbol

            def close_all(reason, writeoff=False):
                for pf, pos in plist:
                    with self.fast_lock:
                        if pos.mint in pf.positions:
                            (pf.write_off(pos, reason) if writeoff else pf.force_exit(pos, pair, reason))

            # 1) kwotowanie sprzedaży (jedno na token, największa pozycja): honeypot, rozjazd ceny, WYCENA WYKONALNA
            decimals = plist[0][1].decimals
            if cfg.use_jupiter and decimals is not None and now - self.last_probe.get(mint, 0) >= cfg.exit_probe_seconds:
                self.last_probe[mint] = now
                qty = max(pos.qty_left for _, pos in plist)
                state, d = self.jup.sell_usdc(mint, int(qty * 10 ** decimals))
                if state == "noroute":
                    self.unsell[mint] = self.unsell.get(mint, 0) + 1
                    self.exec_marks.pop(mint, None)
                    if self.unsell[mint] >= cfg.unsellable_probes:
                        log(f"POZYCJA {sym}: brak trasy sprzedaży {self.unsell[mint]}x - spisuję na zero")
                        wallets = plist[0][1].info.get("wallets", [])
                        close_all("unsellable", writeoff=True)
                        self.mark_rug(mint, wallets, "unsellable")
                        continue
                elif state == "ok":
                    self.unsell[mint] = 0
                    value = float(d["outAmount"]) / 1e6
                    self.exec_marks[mint] = (now, value / qty)
                    self._sellq[mint] = (now, qty, value)       # ewentualne wyjścia w tej chwili użyją tego kwotowania
                    ref = qty * float((pair or {}).get("priceUsd") or 0)
                    if ref > 5 and value < ref * (1 - cfg.exit_gap_pct / 100):
                        log(f"POZYCJA {sym}: realna wartość sprzedaży ${value:.0f} << ${ref:.0f} z ceny - wychodzę")
                        close_all("exit_gap")
                        continue
            ts, px = self.exec_marks.get(mint, (0.0, None))
            exec_price = px if now - ts <= cfg.exit_probe_seconds * 2.5 else None

            # 2) reguły wyjścia każdego portfela (SL / TP / trailing / momentum / time stop / drenaż płynności)
            for pf, pos in plist:
                with self.fast_lock:                   # szybki stop mógł już zamknąć pozycję
                    if pos.mint not in pf.positions:
                        continue
                    reason = pf.manage(pos, pair, exec_price=exec_price)
                if reason:
                    log(f"POZYCJA [{pf.name}] {sym}: {reason}")
                    if reason in RUG_EXITS:
                        self.mark_rug(mint, pos.info.get("wallets", []), reason)
            plist = [(pf, pos) for pf, pos in plist if mint in pf.positions]
            if not plist:
                continue

            # 3) smart money sprzedaje (tylko gdy skonfigurowano smart_wallets)
            if cfg.exit_smart_money_sell and cfg.smart_wallets and pair and pair.get("pairAddress") \
                    and now - self.last_smart.get(mint, 0) >= cfg.exit_probe_seconds * 3:
                self.last_smart[mint] = now
                opened = min(pos.opened_ts for _, pos in plist)
                sold = [t for t in self.gecko.pool_trades(pair["pairAddress"])
                        if t.get("kind") == "sell" and t.get("tx_from_address") in cfg.smart_wallets
                        and (feat._ts(t.get("block_timestamp")) or 0) > opened]
                if sold:
                    log(f"POZYCJA {sym}: obserwowany portfel sprzedaje - wychodzę")
                    close_all("smart_money_sell")
                    continue

            # 4) cykliczny ponowny audyt: nowe veto bezpieczeństwa albo sprzedaż deweloperskiego salda
            if now - self.last_audit.get(mint, 0) > cfg.recheck_rug_every_min * 60:
                self.last_audit[mint] = now
                findings, actx = self.audit(mint)
                bad = [f for f in findings if f.veto and not f.retry]
                wallets = plist[0][1].info.get("wallets", [])
                if bad:
                    log(f"POZYCJA {sym}: nowe ostrzeżenie bezpieczeństwa -> wyjście ({bad[0].name})")
                    close_all("rug_recheck")
                    self.mark_rug(mint, wallets, "rug_recheck")
                    continue
                base = plist[0][1].info.get("creator_balance_pct")
                cur = actx.get("creator_balance_pct")
                if cfg.exit_dev_sell and base and base >= 1 and cur is not None \
                        and cur <= base * (1 - cfg.dev_sell_drop_pct / 100):
                    log(f"POZYCJA {sym}: twórca sprzedał saldo {base:.1f}% -> {cur:.1f}% - wychodzę")
                    close_all("dev_sell")

    # ------------------------------------------------------------ skan nowych tokenów
    def process_stream(self):
        """Zdarzenia PumpPortal z kolejki: starty -> historia twórców; graduacje -> kandydaci do analizy po DEX-ie."""
        if not self.stream:
            return
        launches = grads = 0
        for ev in self.stream.drain():
            if ev["type"] == "create":
                self.store.log_launch(ev["mint"], ev.get("creator"), ev.get("symbol"), ev.get("name"),
                                      ev.get("initial_buy_sol"), ev.get("mcap_sol"))
                launches += 1
            elif ev["type"] == "migrate":
                self.store.log_migration(ev["mint"], ev.get("pool"))
                self.tag_source([ev["mint"]], "graduation")
                grads += 1
                if ev["mint"] not in self.blacklist:
                    self.watch.setdefault(ev["mint"], time.time())     # analiza, gdy DexScreener zaindeksuje parę
                    self.cooldown.pop(ev["mint"], None)
        self.store.db.commit()
        if grads:
            log(f"PumpPortal: {grads} graduacji do analizy, {launches} nowych startów | {self.stream.status()}")

    def scan(self):
        cfg = self.cfg
        self.loop_no += 1
        self.process_stream()
        self.engine.refresh()
        self.refresh_trending()
        candidates = self.discover()
        pairs_by_mint = self.dex.pairs_for_tokens(candidates) if candidates else {}
        best = {m: self.dex.best_pair(ps) for m, ps in pairs_by_mint.items()}
        for m, p in best.items():
            if p:
                self.prices[m] = float(p.get("priceUsd") or 0)
                self.snapshot(m, p)          # szereg czasowy także dla tokenów, których nie kupimy
        self.update_market(best)
        prices = self.prices

        for mint in candidates:
            pair = best.get(mint)
            if not pair:
                continue
            sym = (pair.get("baseToken") or {}).get("symbol", "?")
            v, ctx = self.evaluate(mint, pair, prices)
            ctx["mint"] = mint
            if strategies._clean(v):                   # cechy startu tylko dla czystych tokenów (koszt zapytań)
                ctx["launch"] = self.launch.check(mint)
                if not isinstance(ctx.get("features"), dict):
                    ctx["features"] = {}
                lf = ctx["features"]
                b, c = ctx["launch"].get("bundle"), ctx["launch"].get("copy")
                lf.update({"bundle_start_pct": b and round(b["bundle_start_pct"], 2), "dev_alone_pct": b and round(b["dev_alone_pct"], 2),
                           "copy_cat": c and c["copy_cat"], "copy_n": c and c["copy_n"], "img_copy": c and c["img_copy"],
                           "img_ref": c and c["img_ref"], "img_known": c and c["img_known"]})
            first_watch = v.decision == "WATCH" and mint not in self.watch
            wanting = [n for n in self.portfolios if strategies.wants(n, v, cfg, ctx)]
            # strategie tylko-sygnałowe (np. TA): bez kapitału, oceniane po zwrocie ceny tokenów, które wskazały
            signal_only = [n for n in cfg.signal_strategies if strategies.wants(n, v, cfg, ctx)]

            if v.decision == "WATCH":
                self.watch.setdefault(mint, time.time())
            else:
                self.watch.pop(mint, None)
                self.cooldown[mint] = time.time() + cfg.reject_cooldown_min * 60
            if any(f.permanent for f in v.vetoes):
                self.blacklist.add(mint)
                self.store.blacklist(mint, v.reasons())
                if any(f.name in ("rugged", "honeypot", "honeypot_gt") for f in v.vetoes):
                    self.mark_rug(mint, ctx["wallets"], v.vetoes[0].name)

            # jeden wpis na token na okno cooldownu (bez duplikatów BUY blokowanych limitem pozycji) - ale ZMIANA decyzji
            # (np. WATCH -> BUY) zawsze daje nowy wpis. Do v0.9 sygnał przypinał się wtedy do starej oceny WATCH: z jej
            # czasem, ceną i niepełnymi cechami (36% sygnałów, wejście w odtworzeniach średnio ~5 min za wcześnie).
            recently = time.time() - self.logged_at.get(mint, 0) < cfg.reject_cooldown_min * 60
            same = self.logged_dec.get(mint) == v.decision
            if (v.decision != "WATCH" or first_watch) and not (recently and same and (wanting or signal_only)):
                self.last_decision_id[mint] = self.store.log_decision(mint, sym, v, pair, ctx.get("features"))
                self.logged_at[mint] = time.time()
                self.logged_dec[mint] = v.decision
            # sygnały każdej strategii zapisujemy zawsze (także w trybie RESEARCH i gdy portfel nie ma miejsca)
            if mint in self.last_decision_id:
                for n in wanting + signal_only:
                    self.store.log_signal(self.last_decision_id[mint], n)

            if wanting and cfg.mode == "PAPER":
                self.enter(mint, sym, pair, v, ctx, wanting, prices)
            elif wanting:
                log(f"SYGNAŁ [{', '.join(wanting)}] {sym} Opp {v.opportunity:.0f}/Risk {v.risk:.0f} (tryb {cfg.mode}, bez transakcji)")
            elif v.decision in ("REJECT", "SKIP"):
                log(f"{v.decision} {sym} Opp {v.opportunity:.0f}/Risk {v.risk:.0f} | {'; '.join(w for w in v.why[:2])}")
            if self.llm.enabled and not v.vetoes and v.category_scores and mint in self.last_decision_id:
                self.assess_llm(mint, sym, v, ctx)
        self.store.db.commit()

        parts = []
        for name, pf in self.portfolios.items():
            eq = pf.equity(prices)
            self.store.log_equity(eq, pf.cash, pf.open_value(prices), name)
            parts.append(f"{name} ${eq:,.0f}/{len(pf.positions)}poz")
        log(f"obieg {self.loop_no}: kandydatów {len(candidates)}, obserwowanych {len(self.watch)} | " + ", ".join(parts))

    def assess_llm(self, mint, sym, v, ctx):
        """Ocena Gemini czystego tokena - PO wejściach portfeli, więc czas odpowiedzi modelu nie spowalnia handlu.
        Wynik to tylko sygnały (gemini / gemini_hc) i cechy gemini_* w decyzji; brak odpowiedzi = brak sygnału."""
        if time.time() - self.llm_seen.get(mint, 0) < self.cfg.reject_cooldown_min * 60:
            return
        self.llm_seen[mint] = time.time()
        notes = [f"{f.name} ({f.points:+.0f}): {f.detail}"
                 for f in sorted(v.findings, key=lambda f: -abs(f.points)) if f.points][:10]
        if time.time() - self.llm_ref_ts > 1800:              # percentyle cech: ostatnie czyste tokeny (BUY/SKIP)
            self.llm_ref = llm.reference(self.store.db.execute(
                "SELECT features FROM decisions WHERE decision IN ('BUY','SKIP') ORDER BY id DESC LIMIT 400"))
            self.llm_ref_ts = time.time()
        res, meta = self.llm.ask(llm.build_prompt(sym, ctx.get("features") or {}, notes, self.llm_ref))
        did = self.last_decision_id[mint]
        self.store.log_llm(did, mint, res, meta)
        if not res:
            if meta.get("error") not in ("limit na minutę", "limit dzienny"):
                log(f"GEMINI {sym}: brak oceny ({meta.get('error')})")
            return
        if res["decision"] == "BUY":
            self.store.log_signal(did, "gemini")
            if res["confidence"] >= self.cfg.gemini_hc_confidence:
                self.store.log_signal(did, "gemini_hc")
            self.store.db.commit()
        log(f"GEMINI {res['decision']} {sym} (pewność {res['confidence']}, p(lepiej niż typowy czysty token) {res['p_tp']}%, "
            f"{meta.get('latency')} s): {res['reasoning']}")

    def enter(self, mint, sym, pair, v, ctx, wanting, prices):
        """Wejście dla wszystkich strategii, które chcą kupić ten token (jedno wspólne kwotowanie po latencji)."""
        cfg = self.cfg
        if cfg.first_look_window_min > 0:
            first = self.store.db.execute("SELECT MIN(opened_ts) FROM positions WHERE mint=?", (mint,)).fetchone()[0]
            if first and time.time() - first > cfg.first_look_window_min * 60:
                if "hybrid" in wanting:
                    log(f"BUY pominięty {sym}: spóźnione wejście (pierwszy portfel kupił "
                        f"{(time.time() - first) / 60:.0f} min temu)")
                return                                     # zostaje zwykły cooldown - token już "zjedzony"
        eligible, blocked = [], []
        for n in wanting:
            ok, why = self.portfolios[n].can_open(prices, mint)
            if ok and mint not in self.portfolios[n].positions:
                eligible.append(n)
            elif not ok:
                blocked.append(why)
                if n == "hybrid":
                    log(f"BUY pominięty {sym} (Opp {v.opportunity:.0f}/Risk {v.risk:.0f}): {why}")
        if not eligible:
            # brak miejsca w portfelu bywa chwilowy - sprawdź ponownie za 2 min; blokada ponownego wejścia trwa
            # godzinami, więc wtedy zostaje zwykły cooldown (nie oceniamy tokena co 2 min na darmo)
            if any(not w.startswith("blokada") for w in blocked):
                self.cooldown[mint] = time.time() + 120
            return
        qty, finfo = self.fill_quote(mint, ctx["size"], ctx)
        if qty is None and ctx.get("buy_qty") and finfo.get("failed"):
            log(f"WEJŚCIE NIEUDANE {sym}: {finfo['failed']} [{', '.join(eligible)}]")
            self.store.kv_set("failed_entries", self.store.kv_get("failed_entries", 0) + 1)
            return
        liq = ctx["liq"]
        for n in eligible:
            pf = self.portfolios[n]
            size = pf.entry_size(prices, liq)
            info = {"wallets": [w for w in ctx["wallets"] if w], "strategy": n, "features": ctx.get("features"),
                    "creator_balance_pct": ctx.get("creator_balance_pct"), **finfo}
            quote_qty = qty * size / ctx["size"] if (qty and cfg.use_jupiter_fills and ctx["size"]) else None
            info.update({"opportunity": round(v.opportunity, 1), "risk": round(v.risk, 1)})
            with self.fast_lock:
                pos = pf.buy(mint, sym, float(pair["priceUsd"]), liq, size, v.opportunity, info=info,
                             decimals=ctx["decimals"], quote_qty=quote_qty)
            if pos:
                log(f"KUPNO [{n}] {sym} ${size:.0f} @ {pos.entry_price:.8g} Opp {v.opportunity:.0f}/Risk {v.risk:.0f} | {v.reasons(3)}")

    # ------------------------------------------------------------ pomiar wyników decyzji po czasie
    def track_outcomes(self):
        """Dla starych decyzji (także odrzuconych!) zapisuje cenę i płynność po 1/6/24 h - paliwo dla `calibrate`."""
        cfg = self.cfg
        if not cfg.track_outcomes or time.time() - self._outcomes_ts < cfg.outcome_check_min * 60:
            return
        self._outcomes_ts = time.time()
        rows = self.store.pending_outcomes(cfg.outcome_horizons_h)
        if not rows:
            return
        mints = list(dict.fromkeys(r["mint"] for r in rows))
        pairs = self.dex.pairs_for_tokens(mints)
        if not pairs:  # awaria API nie może wyglądać jak masowy rug
            return
        for r in rows:
            p = self.dex.best_pair(pairs.get(r["mint"], []))
            price = float((p or {}).get("priceUsd") or 0)
            liq = float(((p or {}).get("liquidity") or {}).get("usd") or 0)
            self.store.save_outcome(r["id"], r["h"], price, liq)
        self.store.db.commit()
        log(f"zapisano {len(rows)} pomiarów wyników decyzji")

    # ------------------------------------------------------------ archiwum świec (do badania wyjść)
    @staticmethod
    def _pool_before(pairs: list[dict], ts: float) -> str | None:
        """Pula, która istniała w chwili decyzji (po rugu najpłynniejsza bywa inna, nowsza)."""
        older = [p for p in pairs if (p.get("pairCreatedAt") or 0) / 1000 <= ts] or pairs
        best = max(older, key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0), default=None)
        return (best or {}).get("pairAddress")

    def archive_candles(self, force: bool = False) -> int:
        """Dla decyzji z sygnałem dowolnej strategii (starszych niż archive_after_h) zapisuje świece 1-min:
        ~100 min przed decyzją (ATR, struktura) i okno po niej. Z tego `bot.py exits` liczy MAE/MFE i odtwarza wyjścia."""
        cfg = self.cfg
        if not (cfg.archive_candles and cfg.use_gecko):
            return 0
        if not force and time.time() - self._archive_ts < cfg.archive_every_min * 60:
            return 0
        self._archive_ts = time.time()
        rows = self.store.pending_candle_jobs(cfg.archive_after_h, cfg.archive_batch * 4)
        if not rows:
            return 0
        missing = list({r["mint"] for r in rows if not r["pair"] and not self.store.pool_for(r["mint"], r["ts"])})
        looked = self.dex.pairs_for_tokens(missing) if missing else {}
        fetched = 0
        for r in rows:
            pool = r["pair"] or self.store.pool_for(r["mint"], r["ts"]) or self._pool_before(looked.get(r["mint"], []), r["ts"])
            if not pool:
                self.store.save_candle_job(r["id"], r["mint"], None, r["ts"], "no_pool", 0)
                continue
            t0, t1 = r["ts"] - 100 * 60, r["ts"] + cfg.archive_after_h * 3600
            if self.store.candles_cover(pool, t0, t1):          # ta sama pula już pobrana przy innej decyzji
                self.store.save_candle_job(r["id"], r["mint"], pool, r["ts"], "ok", 0)
                continue
            if fetched >= cfg.archive_batch:                    # reszta w następnym przebiegu
                continue
            candles = self.gecko.ohlcv(pool, limit=1000, before=int(min(t1 + 60, time.time())))
            fetched += 1
            if candles is None:
                self.store.save_candle_job(r["id"], r["mint"], pool, r["ts"], "error", 0)
                continue
            n = self.store.save_candles(pool, candles)
            self.store.save_candle_job(r["id"], r["mint"], pool, r["ts"], "ok" if n else "empty", n)
        if fetched:
            log(f"archiwum świec: pobrano {fetched} zestawów")
        return fetched

    # ------------------------------------------------------------ przerwy w działaniu
    def downtime_candles(self, mint: str, t0: float, t1: float) -> list:
        """Świece 1-min tokena z okresu przerwy [t0, t1] (archiwum albo GeckoTerminal, porcjami po 1000 minut)."""
        pool = self.store.pool_for(mint, t0)
        if not pool:
            return []
        if self.store.candles_cover(pool, t0, t1) or not self.cfg.use_gecko:
            return self.store.candles_between(pool, t0 - 120, t1)
        got, before = [], int(t1)
        for _ in range(8):                                  # do ~130 h przerwy
            c = self.gecko.ohlcv(pool, limit=1000, before=before)
            if not c:
                break
            got = c + got
            if c[0][0] <= t0 or int(c[0][0]) >= before:
                break
            before = int(c[0][0])
        if got:
            self.store.save_candles(pool, got)
        return self.store.candles_between(pool, t0 - 120, t1)

    def replay_downtime(self, pf, pos, t0: float, t1: float, candles: list) -> str:
        """Odtworzenie pozycji przez przerwę: świece przechodzą przez TE SAME reguły wyjścia (Portfolio.manage,
        z parametrami strategii), w kolejności open -> low -> high -> close (stop przed TP w tej samej minucie, jak
        w exit_research). Pozycja zamknięta w przerwie dostaje powód z prefiksem 'przerwa_'; niezamknięta zostaje
        otwarta i bot prowadzi ją dalej. Bez świec albo z ceną niezgodną z ostatnim kursem -> unieważnienie."""
        snap = self.store.last_snapshot(pos.mint, before_ts=t0)
        ref = snap["price"] if snap else pos.entry_price
        pre = [c for c in candles if c[0] <= t0]
        after = [c for c in candles if c[0] + 60 > t0]
        check = pre[-1][4] if pre else (after[0][1] if after else 0)
        if not after or not ref or not 0.5 < check / ref < 2:
            pf.void(pos, "przerwa_brak_danych" if not after else "przerwa_zła_cena")
            return "void"
        liq = {"usd": pos.entry_liq or 0}

        def flat(a: float, b: float, px: float) -> None:
            # minuty bez świecy = brak transakcji = cena stoi; reguły czasowe (time stop) muszą zadziałać o czasie,
            # a nie dopiero przy następnej transakcji (5.10.2026: time stop o 03:01 zamiast 01:14)
            t = a + 60
            while t < b and pos.mint in pf.positions:
                pf.clock = t
                pf.manage(pos, {"priceUsd": px, "liquidity": liq}, now=t)
                t += 60

        try:
            prev_t, prev_px = t0, check
            for ts, o, h, l, c, _v in after:
                if prev_px > 0:
                    flat(prev_t, ts, prev_px)
                if pos.mint not in pf.positions:
                    break
                prev_t, prev_px = max(ts, t0), c or prev_px
                for k, px in enumerate((o, l, h, c)):
                    if px and px > 0:
                        pf.clock = max(ts + 15 * k, t0)
                        pf.manage(pos, {"priceUsd": px, "liquidity": liq}, now=pf.clock)
                    if pos.mint not in pf.positions:
                        break
                if pos.mint not in pf.positions:
                    break
            else:
                flat(prev_t, t1, prev_px)                   # od ostatniej świecy do końca przerwy
        finally:
            pf.clock = None
        if pos.mint in pf.positions:
            return "open"
        self.store.db.execute("UPDATE positions SET exit_reason='przerwa_'||exit_reason WHERE id=?", (pos.id,))
        self.store.db.execute("UPDATE trades SET reason='przerwa_'||reason WHERE position_id=? AND side='SELL' AND ts>=?",
                              (pos.id, t0))
        self.store.db.commit()
        return "closed"

    def close_after_downtime(self) -> int:
        """Po dłuższej przerwie (wyłączony komputer) odtwarzamy, co stałoby się z otwartymi pozycjami, gdyby bot
        działał: świece 1-min z przerwy przez reguły wyjścia strategii. Do 4.10.2026 pozycje zamykano po kursie sprzed
        przerwy (downtime_close) - to ucinało transakcje w połowie i fałszowało wyniki (trailing/TP nie miały szans)."""
        last = self.store.last_activity_ts()
        now = time.time()
        if not last or now - last < self.cfg.downtime_close_min * 60:
            return 0
        cache: dict = {}
        res = collections.Counter()
        for pf in self.portfolios.values():
            quoter, pf.sell_quoter = pf.sell_quoter, None     # nie pytamy Jupitera o dzisiejszą cenę
            try:
                for pos in list(pf.positions.values()):
                    if pos.mint not in cache:
                        cache[pos.mint] = self.downtime_candles(pos.mint, last, now)
                    res[self.replay_downtime(pf, pos, last, now, cache[pos.mint])] += 1
            finally:
                pf.sell_quoter = quoter
        n = sum(res.values())
        if n:
            log(f"przerwa {(now - last) / 60:.0f} min: odtworzono {n} pozycji ze świec - zamknięte w przerwie "
                f"{res['closed']}, dalej otwarte {res['open']}, unieważnione (brak danych) {res['void']}")
        return n

    # ------------------------------------------------------------ pętle
    def step(self):
        self.manage_positions()
        self.scan()
        self.track_outcomes()
        self.archive_candles()

    def run(self):
        started = self.stream.start() if self.stream else False
        log(f"start [{self.cfg.mode}]: strategie {list(self.portfolios)}, kapitał ${self.cfg.start_balance_usd:,.0f} "
            f"na strategię, baza {self.cfg.db_path}, PumpPortal {'włączony' if started else 'wyłączony'}")
        log(f"Gemini: {self.cfg.gemini_model}, limit {self.cfg.gemini_rpm}/min i {self.cfg.gemini_max_per_day}/dobę"
            if self.llm.enabled else "Gemini: wyłączony (brak GEMINI_API_KEY albo gemini_enabled=False)")
        self.close_after_downtime()
        if self.fast_names:
            fastexit.FastMonitor(self, self.fast_names, self.cfg.fast_stop_poll_s, log).start()
        last_scan = 0.0
        while True:
            try:
                self.manage_positions()
                if time.time() - last_scan >= self.cfg.loop_seconds:
                    last_scan = time.time()
                    self.scan()
                    self.track_outcomes()
                    self.archive_candles()
            except KeyboardInterrupt:
                raise
            except Exception as e:  # jeden zły obieg nie może zabić bota
                log(f"BŁĄD obiegu: {type(e).__name__}: {e}")
            time.sleep(self.cfg.position_loop_seconds)


# ---------------------------------------------------------------- komendy pomocnicze

def cmd_analyze(cfg: Config, mint: str):
    bot = Bot(cfg)
    bot.refresh_trending()
    pairs = bot.dex.pairs_for_tokens([mint]).get(mint)
    pair = bot.dex.best_pair(pairs or [])
    if not pair:
        print("DexScreener nie zna tego tokena (na tym łańcuchu).")
        return
    v, ctx = bot.evaluate(mint, pair, {}, full=True)
    base = pair.get("baseToken") or {}
    print(f"\n{base.get('name')} ({base.get('symbol')})  {mint}")
    print(f"cena ${pair.get('priceUsd')}  płynność ${(pair.get('liquidity') or {}).get('usd')}  "
          f"mcap ${pair.get('marketCap') or pair.get('fdv')}")
    ctx["mint"] = mint
    print(f"DECYZJA: {v.explain()}")
    print(f"(progi: Opportunity >= {cfg.opportunity_min:.0f}, Risk <= {cfg.risk_max:.0f}; dawny wynik łączny {v.score:.0f})")
    print("kategorie:", {k: round(x) for k, x in v.category_scores.items()})
    print("strategie, które by kupiły:", [n for n in strategies.REGISTRY if strategies.wants(n, v, cfg, ctx)] or "żadna", "\n")
    for f in sorted(v.findings, key=lambda f: (not f.veto, -abs(f.points))):
        print(" ", f)
    print("\ncechy:", {k: x for k, x in sorted((ctx.get("features") or {}).items())})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "once", "analyze", "report", "calibrate", "features", "wallets", "exits",
                                    "entries", "reset"])
    ap.add_argument("mint", nargs="?")
    ap.add_argument("--horizon", type=int, default=6, help="horyzont pomiaru w godzinach (1/6/24)")
    ap.add_argument("--signals", action="store_true", help="exits: sygnały wszystkich strategii zamiast pozycji")
    ap.add_argument("--since", help='exits/calibrate/entries: tylko dane od tej chwili, np. "2026-10-02 18:00"')
    ap.add_argument("--min-age", type=float, help="entries: tylko tokeny mające tyle minut przy pierwszej ocenie")
    ap.add_argument("--mode", choices=["RESEARCH", "PAPER", "LIVE"], help="nadpisuje tryb z config (domyślnie PAPER)")
    a = ap.parse_args()
    since = None
    if a.since:
        try:
            since = time.mktime(time.strptime(a.since, "%Y-%m-%d %H:%M"))
        except ValueError:
            ap.error('--since: format "RRRR-MM-DD GG:MM", np. "2026-10-02 18:00"')
    cfg = Config.load()
    if a.mode:
        cfg.mode = a.mode
    if a.cmd == "run":
        try:
            Bot(cfg).run()
        except KeyboardInterrupt:
            print("\nzatrzymano")
    elif a.cmd == "once":
        Bot(cfg).step()
    elif a.cmd == "analyze":
        if not a.mint:
            ap.error("podaj adres mintu")
        cmd_analyze(cfg, a.mint)
    elif a.cmd == "report":
        import reporting
        reporting.run(cfg)
    elif a.cmd == "calibrate":
        import calibrate
        calibrate.run(cfg, a.horizon, since)
    elif a.cmd == "features":
        import research
        research.feature_report(cfg, a.horizon)
    elif a.cmd == "wallets":
        import research
        research.wallet_report(cfg, a.horizon)
    elif a.cmd == "exits":
        import exit_research
        exit_research.run(cfg, a.horizon, signals=a.signals, since=since)
    elif a.cmd == "entries":
        import entry_research
        entry_research.run(cfg, min_age=a.min_age, since=since)
    elif a.cmd == "reset":
        from pathlib import Path
        p = Path(cfg.db_path)
        if p.exists():   # nie kasujemy: stare dane przydają się do porównania wersji strategii
            new = p.with_name(f"bot_{time.strftime('%Y%m%d_%H%M%S')}.db")
            p.rename(new)
            print(f"stara baza zarchiwizowana jako {new.name}; nowy start z czystą bazą")
        else:
            print("brak bazy do zarchiwizowania")


if __name__ == "__main__":
    main()
