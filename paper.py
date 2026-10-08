"""Symulator handlu (paper trading) z realistycznym kosztem wejścia i wyjścia.

Nie wysyła żadnych transakcji - liczy fikcyjne fille na podstawie cen i płynności z DexScreenera:
  * poślizg z modelu x*y=k (rozmiar pozycji / połowa płynności puli) + stały dodatek "z życia",
  * prowizja DEX-a na stronę + stały koszt priority fee,
  * wyjście z pustej puli (rug) automatycznie daje dramatyczny poślizg, bo płynność jest mała.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from storage import Storage


@dataclass
class Position:
    id: int
    mint: str
    symbol: str
    opened_ts: float
    entry_price: float
    qty_initial: float
    qty_left: float
    cost_usd: float
    realized_usd: float
    peak_price: float
    entry_liq: float
    tp_hit: int = 0
    misses: int = 0
    last_rugcheck_ts: float = 0.0
    decimals: int | None = None
    last_probe_ts: float = 0.0
    unsellable: int = 0
    info: dict = field(default_factory=dict)   # np. adresy twórcy - do listy rugów
    # MAE/MFE w trakcie trzymania: najgłębszy spadek i najwyższy zysk (% od ceny wejścia) oraz kiedy (min od wejścia)
    mae_pct: float = 0.0
    mfe_pct: float = 0.0
    t_mae_min: float = 0.0
    t_mfe_min: float = 0.0


def position_from_row(r) -> Position:
    """Wiersz tabeli positions -> Position."""
    return Position(
        r["id"], r["mint"], r["symbol"], r["opened_ts"], r["entry_price"], r["qty_initial"],
        r["qty_left"], r["cost_usd"], r["realized_usd"], r["peak_price"], r["entry_liq"],
        r["tp_hit"], r["misses"], r["last_rugcheck_ts"] or 0.0, r["decimals"],
        r["last_probe_ts"] or 0.0, r["unsellable"] or 0, json.loads(r["entry_info"] or "{}"),
        r["mae_pct"] or 0.0, r["mfe_pct"] or 0.0, r["t_mae_min"] or 0.0, r["t_mfe_min"] or 0.0)


def _impact(size_usd: float, liq_usd: float) -> float:
    r = max(liq_usd / 2, 1.0)
    return size_usd / (r + size_usd)


class Portfolio:
    """Jeden wirtualny portfel = jedna strategia (name). Każdy ma własną gotówkę, pozycje i limity ryzyka,
    ale wszystkie widzą te same dane - dzięki temu strategie można uczciwie porównać na tym samym rynku."""

    def __init__(self, cfg, store: Storage, name: str = "hybrid", exits: dict | None = None):
        self.cfg, self.store, self.name = cfg, store, name
        # nadpisania parametrów wyjścia dla tej strategii (np. {"stop_loss_pct": 40}); reszta z Config
        self.exits = dict(exits or {})
        unknown = [k for k in self.exits if not hasattr(cfg, k)]
        if unknown:
            raise ValueError(f"nieznane parametry wyjścia dla strategii {name}: {unknown}")
        # klucze kv: dla "hybrid" bez prefiksu (zgodność ze starymi bazami)
        self.k = "" if name == "hybrid" else f"{name}:"
        self.cash = store.kv_get(self.k + "cash", cfg.start_balance_usd)
        self.positions: dict[str, Position] = {}
        for r in store.db.execute("SELECT * FROM positions WHERE status='open' AND COALESCE(strategy,'hybrid')=?",
                                  (name,)):
            self.positions[r["mint"]] = position_from_row(r)
        self.sell_quoter = None   # hook: (pos, qty) -> USD z realnego kwotowania Jupitera albo None
        self.clock = None         # czas transakcji przy odtwarzaniu przerwy ze świec (None = teraz)
        self.consec_losses = store.kv_get(self.k + "consec_losses", 0)
        self.pause_until = store.kv_get(self.k + "pause_until", 0.0)
        day = time.strftime("%Y-%m-%d", time.gmtime())
        if store.kv_get(self.k + "day") != day:
            store.kv_set(self.k + "day", day)
            store.kv_set(self.k + "day_start_equity", self.equity({}))

    def p(self, key: str):
        """Parametr wyjścia tej strategii (nadpisanie albo wartość z Config)."""
        return self.exits.get(key, getattr(self.cfg, key))

    # ---------------- wycena ----------------
    def open_value(self, prices: dict[str, float]) -> float:
        return sum(p.qty_left * prices.get(p.mint, p.entry_price) for p in list(self.positions.values()))   # kopia: wątek szybkiego stopu zamyka pozycje

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + self.open_value(prices)

    def exposure_pct(self, prices) -> float:
        eq = self.equity(prices)
        return self.open_value(prices) / eq if eq else 1.0

    # ---------------- zgoda na wejście ----------------
    def limits_active(self) -> bool:
        """Dzienny limit strat i pauza po serii strat: zawsze w LIVE, w PAPER tylko na życzenie (Config.risk_limits_in_paper).
        W badaniu zatrzymany portfel przestaje być grupą kontrolną, a reszta handluje dalej - porównanie się psuje."""
        return self.cfg.mode == "LIVE" or self.cfg.risk_limits_in_paper

    def entry_size(self, prices: dict[str, float], liq_usd: float) -> float:
        c = self.cfg
        base = c.position_usd if c.position_usd > 0 else self.equity(prices) * c.position_pct
        size = min(base, liq_usd * c.max_position_pct_of_liq, self.cash)
        return max(size, 0.0)

    def last_exit_ts(self, mint: str) -> float | None:
        r = self.store.db.execute("SELECT MAX(closed_ts) FROM positions WHERE mint=? AND status='closed' "
                                  "AND COALESCE(strategy,'hybrid')=?", (mint, self.name)).fetchone()
        return r[0] if r and r[0] else None

    def can_open(self, prices: dict[str, float], mint: str | None = None) -> tuple[bool, str]:
        c = self.cfg
        if self.limits_active() and time.time() < self.pause_until:
            return False, f"pauza po serii strat do {time.strftime('%H:%M', time.localtime(self.pause_until))}"
        if len(self.positions) >= c.max_open_positions:
            return False, "limit otwartych pozycji"
        if self.exposure_pct(prices) >= c.max_exposure_pct:
            return False, "limit ekspozycji"
        if self.limits_active():
            start = self.store.kv_get(self.k + "day_start_equity", c.start_balance_usd)
            if start and (self.equity(prices) / start - 1) * 100 <= -c.daily_loss_limit_pct:
                return False, "dzienny limit strat"
        if mint and c.reentry_block_h > 0:
            t = self.last_exit_ts(mint)
            if t and time.time() - t < c.reentry_block_h * 3600:
                until = time.strftime('%H:%M', time.localtime(t + c.reentry_block_h * 3600))
                return False, f"blokada ponownego wejścia do {until}"
        if self.cash < max(c.position_usd, 5):   # stała stawka: bez pełnej stawki nie wchodzimy (porównywalność w $)
            return False, "brak gotówki"
        return True, ""

    # ---------------- wejście ----------------
    def buy(self, mint, symbol, price, liq_usd, size_usd, score, info=None, decimals=None,
            quote_qty=None) -> Position | None:
        """quote_qty = ilość tokenów z realnego kwotowania Jupitera (już z prowizją i poślizgiem puli)."""
        c = self.cfg
        if size_usd < 5 or price <= 0:
            return None
        if quote_qty:
            # kwotowanie ma już prowizję i poślizg puli; doliczamy tylko opóźnienie/MEV i priority fee
            qty = quote_qty * (1 - c.extra_slippage_pct / 100) * (1 - c.priority_fee_usd / size_usd)
            eff = size_usd / qty
            slip = eff / price - 1
            net = size_usd - c.priority_fee_usd
        else:
            net = size_usd * (1 - c.swap_fee_pct / 100) - c.priority_fee_usd
            slip = _impact(net, liq_usd) + c.extra_slippage_pct / 100
            eff = price * (1 + slip)
            qty = net / eff
        self.cash -= size_usd
        info = info or {}
        cur = self.store.db.execute(
            "INSERT INTO positions(mint,symbol,status,opened_ts,entry_price,qty_initial,qty_left,cost_usd,"
            "peak_price,entry_liq,score,entry_info,last_rugcheck_ts,decimals,strategy) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mint, symbol, "open", time.time(), eff, qty, qty, size_usd, eff, liq_usd, score,
             json.dumps(info), time.time(), decimals, self.name))
        pos = Position(cur.lastrowid, mint, symbol, time.time(), eff, qty, qty, size_usd, 0.0, eff, liq_usd,
                       last_rugcheck_ts=time.time(), decimals=decimals, info=info)
        self.positions[mint] = pos
        self._trade(pos, "BUY", eff, qty, size_usd, size_usd - net, slip * 100, "entry")
        self._persist(pos)
        return pos

    # ---------------- wyjście ----------------
    def sell(self, pos: Position, qty: float, price: float, liq_usd: float, reason: str) -> float:
        c = self.cfg
        qty = min(qty, pos.qty_left)
        if qty <= 0:
            return 0.0
        gross = qty * price
        quoted = self.sell_quoter(pos, qty) if self.sell_quoter and price > 0 else None
        if quoted is not None:   # realne kwotowanie Jupitera (prowizje i głębokość już w środku)
            proceeds = max(quoted * (1 - c.extra_slippage_pct / 100) - c.priority_fee_usd, 0.0)
            eff = proceeds / qty
            slip = max(1 - eff / price, 0.0)
        else:
            slip = _impact(gross, liq_usd) + c.extra_slippage_pct / 100
            eff = price * max(1 - slip, 0.0)
            proceeds = max(qty * eff * (1 - c.swap_fee_pct / 100) - c.priority_fee_usd, 0.0)
        self.cash += proceeds
        pos.qty_left -= qty
        pos.realized_usd += proceeds
        self._trade(pos, "SELL", eff, qty, proceeds, gross - proceeds, slip * 100, reason)
        if pos.qty_left <= 1e-12:
            self._close(pos, reason)
        else:
            self._persist(pos)
        return proceeds

    def _close(self, pos: Position, reason: str):
        pnl = pos.realized_usd - pos.cost_usd
        self.store.db.execute(
            "UPDATE positions SET status='closed', closed_ts=?, exit_reason=?, realized_usd=?, qty_left=0,"
            " mae_pct=?, mfe_pct=?, t_mae_min=?, t_mfe_min=? WHERE id=?",
            (self.clock or time.time(), reason, pos.realized_usd, pos.mae_pct, pos.mfe_pct, pos.t_mae_min, pos.t_mfe_min,
             pos.id))
        self.positions.pop(pos.mint, None)
        if pnl < 0:
            self.consec_losses += 1
            if self.limits_active() and self.consec_losses >= self.cfg.max_consecutive_losses:
                self.pause_until = time.time() + self.cfg.pause_after_losses_min * 60
                self.consec_losses = 0
                self.store.kv_set(self.k + "pause_until", self.pause_until)
        else:
            self.consec_losses = 0
        self.store.kv_set(self.k + "consec_losses", self.consec_losses)
        self.store.kv_set(self.k + "cash", self.cash)
        self.store.db.commit()

    # ---------------- zarządzanie pozycją ----------------
    def manage(self, pos: Position, pair: dict | None, now: float | None = None,
               exec_price: float | None = None) -> str | None:
        """Sprawdza reguły wyjścia dla jednej pozycji. Zwraca powód wyjścia (jeśli zamknięto/sprzedano).

        exec_price = cena WYKONALNA (wartość sprzedaży całej pozycji z Jupitera / ilość). Gdy jest, stopy i TP liczymy
        od niej, bo ostatnia transakcja z DexScreenera bywała o 10-30% od tego, po czym naprawdę da się sprzedać
        (fałszywe take-profity, sztucznie opóźnione stopy).

        Parametry wyjścia pochodzą z self.p(...) - każda strategia może mieć własne (Config.strategy_exits)."""
        c = self.cfg
        p = self.p
        now = now or time.time()
        if not pair and not exec_price:
            pos.misses += 1
            if pos.misses >= 5:  # token zniknął z DexScreenera - zakładamy rug, wartość 0
                self.write_off(pos, "no_data_rug")
                return "no_data_rug"
            self._persist(pos)
            return None
        pos.misses = 0
        dex_price = float((pair or {}).get("priceUsd") or 0)
        liq = float(((pair or {}).get("liquidity") or {}).get("usd") or 0)
        price = exec_price or dex_price
        if price <= 0:
            return None
        pos.peak_price = max(pos.peak_price, price)
        pnl_pct = (price / pos.entry_price - 1) * 100
        held_min = (now - pos.opened_ts) / 60
        if pnl_pct < pos.mae_pct:                   # MAE/MFE z tej samej ceny, po której działają stopy
            pos.mae_pct, pos.t_mae_min = pnl_pct, held_min
        if pnl_pct > pos.mfe_pct:
            pos.mfe_pct, pos.t_mfe_min = pnl_pct, held_min

        # 1) ucieczka przy drenażu płynności (klasyczny rug); bez danych o płynności pomijamy
        if pair and pos.entry_liq and liq <= pos.entry_liq * (1 - p("liquidity_drain_exit_pct") / 100):
            self.sell(pos, pos.qty_left, price, liq, "liq_drain")
            return "liq_drain"
        # 2) stop loss
        if pnl_pct <= -p("stop_loss_pct"):
            self.sell(pos, pos.qty_left, price, liq, "stop_loss")
            return "stop_loss"
        # 3) częściowe realizacje zysków (ułamek ORYGINALNEJ ilości; ostatni poziom sprzedaje resztę)
        reason = None
        levels = p("take_profit_levels")
        while pos.tp_hit < len(levels):
            level, frac = levels[pos.tp_hit]
            if pnl_pct < level:
                break
            last = pos.tp_hit == len(levels) - 1
            qty = pos.qty_left if last else pos.qty_initial * frac
            pos.tp_hit += 1
            self.sell(pos, qty, price, liq, f"tp{pos.tp_hit}")
            reason = f"tp{pos.tp_hit}"
            if pos.qty_left <= 1e-12:
                return reason
        # 3a) stop na cenie wejścia po pierwszym TP (opcja portfela, np. safety_s6; domyślnie wyłączona)
        be = p("breakeven_after_tp1_pct")
        if be is not None and pos.tp_hit >= 1 and pnl_pct <= be:
            self.sell(pos, pos.qty_left, price, liq, "breakeven")
            return "breakeven"
        # 4) trailing stop po pierwszym TP
        if pos.tp_hit >= 1 and price <= pos.peak_price * (1 - p("trailing_stop_pct") / 100):
            self.sell(pos, pos.qty_left, price, liq, "trailing")
            return "trailing"
        # 5) wygasanie momentum (domyślnie WYŁĄCZONE - hipoteza do przetestowania): sprzedający dominują w ostatnich 5 min
        if c.exit_momentum_decay and pair and pnl_pct < c.momentum_decay_max_pnl_pct:
            m5 = (pair.get("txns") or {}).get("m5") or {}
            b5, s5 = float(m5.get("buys") or 0), float(m5.get("sells") or 0)
            ch5 = float((pair.get("priceChange") or {}).get("m5") or 0)
            if b5 + s5 >= c.momentum_decay_min_txns and b5 / (b5 + s5) < c.momentum_decay_buy_ratio \
                    and ch5 <= c.momentum_decay_ch5_pct:
                self.sell(pos, pos.qty_left, price, liq, "momentum_decay")
                return "momentum_decay"
        # 6) time stop
        if held_min >= p("time_stop_minutes") and pnl_pct < p("time_stop_min_move_pct") and pos.tp_hit == 0:
            self.sell(pos, pos.qty_left, price, liq, "time_stop")
            return "time_stop"
        self._persist(pos)
        return reason

    def write_off(self, pos: Position, reason: str):
        """Spisanie pozycji na zero (rug / honeypot - nie da się sprzedać)."""
        self._trade(pos, "SELL", 0.0, pos.qty_left, 0.0, 0.0, 100.0, reason)
        pos.qty_left = 0
        pos.mae_pct, pos.t_mae_min = -100.0, (time.time() - pos.opened_ts) / 60
        self._close(pos, reason)

    def void(self, pos: Position, reason: str):
        """Unieważnienie pozycji (przerwa bez danych do odtworzenia): cofamy ją w całości - gotówka wraca do stanu
        sprzed kupna, transakcje znikają z kosztów, pozycja dostaje status 'void' i nie liczy się do wyników."""
        self.cash += pos.cost_usd - pos.realized_usd
        self.store.db.execute("DELETE FROM trades WHERE position_id=?", (pos.id,))
        self.store.db.execute("UPDATE positions SET status='void', closed_ts=?, exit_reason=?, qty_left=0 WHERE id=?",
                              (self.clock or time.time(), reason, pos.id))
        self.positions.pop(pos.mint, None)
        self.store.kv_set(self.k + "cash", self.cash)
        self.store.db.commit()

    def force_exit(self, pos: Position, pair: dict | None, reason: str):
        price = float((pair or {}).get("priceUsd") or 0)
        liq = float(((pair or {}).get("liquidity") or {}).get("usd") or 0)
        if price <= 0:
            price, liq = 0.0, 1.0
        self.sell(pos, pos.qty_left, price, liq, reason)

    # ---------------- pomocnicze ----------------
    def _persist(self, pos: Position):
        self.store.db.execute(
            "UPDATE positions SET qty_left=?, realized_usd=?, peak_price=?, tp_hit=?, misses=?, last_rugcheck_ts=?,"
            " last_probe_ts=?, unsellable=?, mae_pct=?, mfe_pct=?, t_mae_min=?, t_mfe_min=? WHERE id=?",
            (pos.qty_left, pos.realized_usd, pos.peak_price, pos.tp_hit, pos.misses, pos.last_rugcheck_ts,
             pos.last_probe_ts, pos.unsellable, pos.mae_pct, pos.mfe_pct, pos.t_mae_min, pos.t_mfe_min, pos.id))
        self.store.kv_set(self.k + "cash", self.cash)
        self.store.db.commit()

    def _trade(self, pos, side, price, qty, usd, fee, slip_pct, reason):
        self.store.db.execute(
            "INSERT INTO trades(position_id,ts,side,price,qty,usd,fee_usd,slippage_pct,reason) VALUES(?,?,?,?,?,?,?,?,?)",
            (pos.id, self.clock or time.time(), side, price, qty, usd, fee, slip_pct, reason))
        self.store.db.commit()
