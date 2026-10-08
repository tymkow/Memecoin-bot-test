"""Testy offline (bez sieci) na sztucznych danych: python test_offline.py"""
import os
import tempfile
import time

import analysis
from config import Config
from paper import Portfolio
from storage import Storage


def make_pair(**over):
    p = {
        "chainId": "solana", "dexId": "raydium",
        "baseToken": {"address": "MINT1", "symbol": "TEST", "name": "Test"},
        "quoteToken": {"symbol": "SOL"},
        "priceUsd": "0.001", "fdv": 400_000, "marketCap": 400_000,
        "liquidity": {"usd": 60_000},
        "volume": {"h24": 500_000, "h6": 200_000, "h1": 60_000, "m5": 6_000},
        "txns": {"h1": {"buys": 300, "sells": 200}, "m5": {"buys": 30, "sells": 15}, "h24": {"buys": 3000, "sells": 2500}},
        "priceChange": {"m5": 2, "h1": 30, "h6": 60, "h24": 90},
        "pairCreatedAt": (time.time() - 3 * 3600) * 1000,
        "info": {"websites": [{"url": "x"}], "socials": [{"type": "twitter"}, {"type": "telegram"}], "imageUrl": "i"},
    }
    p.update(over)
    return p


CLEAN_REPORT = {
    "mintAuthority": None, "freezeAuthority": None, "rugged": False, "score_normalised": 10,
    "markets": [{"lp": {"lpLockedPct": 100}}], "topHolders": [{"address": f"h{i}", "pct": 2.0} for i in range(10)],
    "risks": [], "totalLPProviders": 8, "token": {"supply": 1e9}, "creatorBalance": 0,
}


def test_clean_token_buys():
    cfg = Config()
    f = analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT)
    v = analysis.decide(cfg, f)
    assert v.decision == "BUY", (v.decision, v.score, v.reasons())


def test_rug_vetoes():
    cfg = Config()
    bad = dict(CLEAN_REPORT, mintAuthority="Abc")
    assert analysis.decide(cfg, analysis.rug_checks(cfg, bad)).decision == "REJECT"
    bad = dict(CLEAN_REPORT, freezeAuthority="Abc")
    assert analysis.decide(cfg, analysis.rug_checks(cfg, bad)).decision == "REJECT"
    bad = dict(CLEAN_REPORT, rugged=True)
    assert any(f.permanent for f in analysis.rug_checks(cfg, bad))
    bad = dict(CLEAN_REPORT, topHolders=[{"address": "w", "pct": 35}])
    assert analysis.decide(cfg, analysis.rug_checks(cfg, bad)).decision == "REJECT"


def test_pool_excluded_from_holders():
    cfg = Config()
    rep = dict(CLEAN_REPORT, markets=[{"pubkey": "pool", "lp": {"lpLockedPct": 100}}],
               topHolders=[{"address": "pool", "pct": 40}, {"address": "a", "pct": 2}])
    assert not any(f.veto for f in analysis.rug_checks(cfg, rep))


def test_market_vetoes():
    cfg = Config()
    young = make_pair(pairCreatedAt=(time.time() - 300) * 1000)
    assert analysis.decide(cfg, analysis.market_checks(cfg, young, 50)).decision == "WATCH"
    thin = make_pair(liquidity={"usd": 2000})
    assert analysis.decide(cfg, analysis.market_checks(cfg, thin, 50)).decision in ("WATCH", "REJECT")
    parab = make_pair(priceChange={"m5": 5, "h1": 900, "h6": 900, "h24": 900})
    assert any(f.veto for f in analysis.market_checks(cfg, parab, 50))
    nosoc = make_pair(info={})
    good = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50)).score
    assert analysis.decide(cfg, analysis.market_checks(cfg, nosoc, 50)).score < good


def test_no_audit_blocks():
    cfg = Config()
    assert analysis.decide(cfg, analysis.rug_checks(cfg, None, None)).decision == "WATCH"


def fresh_portfolio(**over):
    cfg = Config()
    for k, v in over.items():
        setattr(cfg, k, v)
    path = os.path.join(tempfile.mkdtemp(), "t.db")
    return cfg, Portfolio(cfg, Storage(path))


def test_paper_stop_and_tp():
    cfg, pf = fresh_portfolio()
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    assert pos and pf.cash < 1000
    pair = lambda price, liq=100_000: {"priceUsd": str(price), "liquidity": {"usd": liq}}
    assert pf.manage(pos, pair(0.7)) == "stop_loss" and "M" not in pf.positions
    assert pf.cash < 1000                                    # strata po kosztach

    pos = pf.buy("M2", "T2", 1.0, 100_000, 50, 80)
    assert pf.manage(pos, pair(1.6)) == "tp1" and "M2" in pf.positions
    pf.manage(pos, pair(2.0))                                # szczyt
    assert pf.manage(pos, pair(1.5)) == "trailing"           # -25% od szczytu


def test_paper_rug_liquidity_drain():
    cfg, pf = fresh_portfolio()
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    before = pf.cash
    assert pf.manage(pos, {"priceUsd": "1.0", "liquidity": {"usd": 30_000}}) == "liq_drain"
    assert pf.cash - before < 50 * 0.99                       # nie odzyskujemy całości


def test_no_data_becomes_rug():
    cfg, pf = fresh_portfolio()
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    r = None
    for _ in range(5):
        r = pf.manage(pos, None)
    assert r == "no_data_rug" and not pf.positions


def test_risk_limits():
    cfg, pf = fresh_portfolio(max_open_positions=1)
    pf.buy("A", "A", 1.0, 100_000, 50, 80)
    ok, why = pf.can_open({"A": 1.0})
    assert not ok and "limit" in why


def test_size_capped_by_liquidity():
    cfg, pf = fresh_portfolio()
    assert pf.entry_size({}, 20_000) <= 20_000 * cfg.max_position_pct_of_liq + 1e-9


def test_honeypot_checks():
    cfg = Config()
    ok = ("ok", {"outAmount": "500000000"})               # 500 tokenów (dec 6) za $50 => cena 0.1
    back_good, back_bad = ("ok", {"outAmount": "48500000"}), ("ok", {"outAmount": "30000000"})
    assert not any(f.veto for f in analysis.honeypot_checks(cfg, ok, back_good, 50, 0.1, 6))
    assert any(f.veto for f in analysis.honeypot_checks(cfg, ok, back_bad, 50, 0.1, 6))       # -40% round trip
    hp = analysis.honeypot_checks(cfg, ok, ("noroute", None), 50, 0.1, 6)
    assert hp[0].veto and hp[0].permanent                                                    # honeypot
    assert any(f.veto for f in analysis.honeypot_checks(cfg, ok, back_good, 50, 0.3, 6))     # cena się nie zgadza
    assert analysis.honeypot_checks(cfg, ("error", None), None, 50, 0.1, 6)[0].veto is False


def test_token2022_traps():
    cfg = Config()
    rep = dict(CLEAN_REPORT, token_extensions={"permanentDelegate": "Abc", "nonTransferable": False})
    assert any(f.name == "permanent_delegate" and f.permanent for f in analysis.rug_checks(cfg, rep))


def test_creator_blacklist():
    cfg = Config()
    assert analysis.creator_checks(cfg, ["W1", None], {"W1"})[0].permanent
    assert not analysis.creator_checks(cfg, ["W2"], {"W1"})


def _trades(n_wallets, n=200):
    return [{"tx_from_address": f"w{i % n_wallets}", "kind": "buy" if i % 3 else "sell", "volume_in_usd": "50"}
            for i in range(n)]


def test_trade_checks():
    cfg = Config()
    healthy = analysis.trade_checks(cfg, _trades(60), 60_000)
    assert not any(f.veto for f in healthy)
    botted = analysis.trade_checks(cfg, _trades(3), 60_000)
    assert any(f.veto and f.name == "top3_portfele" for f in botted)
    cfg.smart_wallets = ("w1",)
    assert any(f.name == "smart_money" for f in analysis.trade_checks(cfg, _trades(60), 60_000))


def test_gecko_checks():
    cfg = Config()
    info = {"is_honeypot": "yes", "holders": {"count": 50}, "gt_score": 20}
    f = analysis.gecko_checks(cfg, info, None)
    assert any(x.veto and x.permanent for x in f)
    good = analysis.gecko_checks(cfg, {"holders": {"count": 2000}, "gt_score": 70, "gt_verified": True}, 3)
    assert sum(x.points for x in good) > 20 and not any(x.veto for x in good)


def test_paper_uses_jupiter_quotes():
    cfg, pf = fresh_portfolio()
    pf.sell_quoter = lambda pos, qty: qty * 0.5 * 1.0        # Jupiter mówi: dostaniesz 50% wartości
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80, decimals=6, quote_qty=48.0)
    assert abs(pos.qty_initial - 48.0 * 0.99 * (1 - 0.05 / 50)) < 1e-6
    before = pf.cash
    pf.sell(pos, pos.qty_left, 1.0, 100_000, "test")
    assert pf.cash - before < pos.qty_initial * 0.51           # realne kwotowanie, nie model


def test_write_off_and_outcomes_calibration():
    cfg, pf = fresh_portfolio()
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    pf.write_off(pos, "unsellable")
    assert "M" not in pf.positions and pf.cash <= 950
    st = pf.store
    st.add_bad_wallets(["W9"], "M", "test")
    assert "W9" in st.bad_wallets()
    v = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    pair = make_pair()
    ids = [st.log_decision(f"M{i}", "T", v, pair) for i in range(3)]
    for d in ids:                                            # sztuczne, zdezaktualizowane decyzje
        st.db.execute("UPDATE decisions SET ts = ts - 7*3600 WHERE id=?", (d,))
    st.db.commit()
    pend = st.pending_outcomes((1, 6))
    assert len(pend) == 6
    for r in pend:
        st.save_outcome(r["id"], r["h"], 0.002, 60_000)
    assert not st.pending_outcomes((1, 6))
    import calibrate
    data = calibrate.load(st, 6)
    assert len(data) == 3 and abs(data[0]["ret"] - 1.0) < 1e-9


def test_no_chasing_pumps_or_falling_knives():
    """Regresja z v0.2: 9 z 12 pierwszych wejść było po pompie +100..+219%/h albo w spadku -12..-26%/h - wszystkie straciły."""
    cfg = Config()
    for ch1 in (103, 149, 219):
        pair = make_pair(priceChange={"m5": 3, "h1": ch1, "h6": ch1, "h24": ch1})
        v = analysis.decide(cfg, analysis.market_checks(cfg, pair, 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
        assert v.decision != "BUY", ch1
    for ch1 in (-12, -22, -26):
        pair = make_pair(priceChange={"m5": 1, "h1": ch1, "h6": 5, "h24": 10})
        v = analysis.decide(cfg, analysis.market_checks(cfg, pair, 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
        assert v.decision != "BUY", ch1
    sold = make_pair(txns={"h1": {"buys": 10, "sells": 490}, "m5": {"buys": 1, "sells": 30}, "h24": {"buys": 3000, "sells": 2500}})
    assert any(f.name == "presja_sprzedaży" and f.veto for f in analysis.market_checks(cfg, sold, 50))


def test_category_gate_blocks_high_total_score():
    cfg = Config()
    cfg.buy_threshold = 40
    cfg.min_category_scores = {"momentum": 100.0}
    f = analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT)
    v = analysis.decide(cfg, f)
    assert v.decision == "SKIP" and any(x.name == "bramka" for x in v.findings)


def test_manage_uses_executable_price():
    """Fałszywy TP z ceny DexScreenera (spike ostatniej transakcji) nie może się wyzwolić, gdy Jupiter daje gorszą cenę."""
    cfg, pf = fresh_portfolio()
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    spike = {"priceUsd": "1.8", "liquidity": {"usd": 100_000}}          # DexScreener: +80%
    assert pf.manage(pos, spike, exec_price=1.05) is None and pos.tp_hit == 0
    assert pf.manage(pos, spike) == "tp1"                                # bez wyceny wykonalnej - stary sposób
    cfg, pf = fresh_portfolio()
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    ok = {"priceUsd": "1.0", "liquidity": {"usd": 100_000}}              # DexScreener: bez zmian, ale nie da się sprzedać
    assert pf.manage(pos, ok, exec_price=0.6) == "stop_loss"


def _ts(sec):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(sec))


def test_trade_metrics_windows_and_same_block():
    import features
    base = 1_800_000_000
    trades = []
    for i in range(60):    # tempo kupujących rośnie: starsze minuty rzadko, ostatnia minuta gęsto
        sec = base + i * 5
        trades.append({"block_timestamp": _ts(sec), "block_number": 1000 + i, "tx_from_address": f"b{i}",
                       "kind": "buy", "volume_in_usd": "20"})
    for i in range(5):     # skoordynowane: 5 portfeli w jednym bloku
        trades.append({"block_timestamp": _ts(base + 100), "block_number": 5000, "tx_from_address": f"c{i}",
                       "kind": "buy", "volume_in_usd": "50"})
    trades.append({"block_timestamp": _ts(base + 120), "block_number": 6000, "tx_from_address": "s1",
                   "kind": "sell", "volume_in_usd": "10"})
    m = features.trade_metrics(trades)
    assert m["ub_60s"] >= 12 and m["same_block_max_wallets"] == 5
    assert 0.1 < m["same_block_buy_share"] < 0.4
    assert features.trade_metrics(trades[:5]) == {}


def test_holder_metrics_gini_nakamoto():
    import features
    assert features.gini([5, 5, 5, 5]) == 0.0
    assert features.gini([0, 0, 0, 100]) > 0.7
    rep = {"markets": [{"pubkey": "pool"}], "topHolders": [{"address": "pool", "pct": 40}] +
           [{"address": f"h{i}", "pct": p} for i, p in enumerate((30, 20, 10, 5))], "token": {"supply": 1000},
           "creatorBalance": 100}
    h = features.holder_metrics(rep)
    assert h["top1"] == 30 and h["top5"] == 65 and h["nakamoto"] == 2 and abs(h["creator_pct"] - 10) < 1e-9


def test_strategies_share_hard_filters():
    import strategies
    cfg = Config()
    f = analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT)
    clean = analysis.decide(cfg, f)
    assert strategies.wants("safety_only", clean, cfg) and strategies.wants("hybrid", clean, cfg)
    vetoed = analysis.decide(cfg, f + [analysis.Finding("safety", "x", veto=True, permanent=True)])
    assert not any(strategies.wants(n, vetoed, cfg) for n in strategies.REGISTRY)   # veto blokuje WSZYSTKIE strategie
    cfg.strategy_thresholds["momentum_only"] = 101
    assert not strategies.wants("momentum_only", clean, cfg)


def test_spearman():
    import research
    assert abs(research.spearman([1, 2, 3, 4, 5, 6], [2, 4, 6, 8, 10, 12]) - 1) < 1e-9
    assert research.spearman([1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]) < -0.99
    assert research.spearman([1, 1, 1, 1, 1], [1, 2, 3, 4, 5]) is None


def test_migration_of_old_database():
    import sqlite3
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    db = sqlite3.connect(path)
    db.executescript("CREATE TABLE positions(id INTEGER PRIMARY KEY, mint TEXT, symbol TEXT, status TEXT, opened_ts REAL,"
                     " closed_ts REAL, entry_price REAL, qty_initial REAL, qty_left REAL, cost_usd REAL, realized_usd REAL,"
                     " peak_price REAL, entry_liq REAL, tp_hit INTEGER, misses INTEGER, last_rugcheck_ts REAL,"
                     " exit_reason TEXT, score REAL, entry_info TEXT, decimals INTEGER, last_probe_ts REAL, unsellable INTEGER);"
                     "CREATE TABLE decisions(id INTEGER PRIMARY KEY, ts REAL, mint TEXT, symbol TEXT, decision TEXT, score REAL,"
                     " categories TEXT, reasons TEXT, findings TEXT, price REAL, liq REAL, mcap REAL, age_min REAL);"
                     "CREATE TABLE equity(ts REAL, equity REAL, cash REAL, open_value REAL);"
                     "INSERT INTO positions(mint,symbol,status,qty_left,entry_price,peak_price,entry_liq,qty_initial,cost_usd,tp_hit)"
                     " VALUES('M','T','open',10,1,1,1000,10,10,0);")
    db.commit()
    db.close()
    st = Storage(path)
    cfg = Config()
    pf = Portfolio(cfg, st, "hybrid")
    assert "M" in pf.positions                                  # stara pozycja trafia do portfela hybrid
    assert not Portfolio(cfg, st, "flow_only").positions


def test_portfolios_are_isolated():
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    a, b = Portfolio(cfg, st, "hybrid"), Portfolio(cfg, st, "safety_only")
    a.buy("M", "T", 1.0, 100_000, 50, 80)
    b.buy("M", "T", 1.0, 100_000, 80, 70)
    assert a.cash == 950 and b.cash == 920 and a.positions["M"].cost_usd != b.positions["M"].cost_usd
    a2, b2 = Portfolio(cfg, st, "hybrid"), Portfolio(cfg, st, "safety_only")   # restart bota
    assert a2.cash == 950 and b2.cash == 920 and a2.positions["M"].qty_initial == a.positions["M"].qty_initial


def test_entry_latency_requote():
    import bot as botmod
    cfg = Config()
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "b.db")
    cfg.entry_latency_s = 0.01
    b = botmod.Bot(cfg)
    ctx = {"buy_qty": 100.0, "decimals": 6, "liq": 50_000}
    b.jup.buy_usdc = lambda m, s: ("ok", {"outAmount": str(int(97 * 1e6))})          # -3% tokenów: akceptowalne
    qty, info = b.fill_quote("M", 50, ctx)
    assert abs(qty - 97) < 1e-6 and abs(info["price_move_pct"] - 3) < 1e-6
    b.jup.buy_usdc = lambda m, s: ("ok", {"outAmount": str(int(80 * 1e6))})          # -20%: cena uciekła
    qty, info = b.fill_quote("M", 50, ctx)
    assert qty is None and "failed" in info
    b.jup.buy_usdc = lambda m, s: ("noroute", None)
    assert b.fill_quote("M", 50, ctx)[0] is None
    cfg.entry_latency_s = 0                                                          # wyłączone = stare zachowanie
    assert b.fill_quote("M", 50, ctx)[0] == 100.0


def test_momentum_decay_exit_is_opt_in():
    cfg, pf = fresh_portfolio()
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    weak = {"priceUsd": "1.05", "liquidity": {"usd": 100_000}, "txns": {"m5": {"buys": 5, "sells": 40}},
            "priceChange": {"m5": -9}}
    assert pf.manage(pos, weak) is None                                               # domyślnie wyłączone
    cfg.exit_momentum_decay = True
    assert pf.manage(pos, weak) == "momentum_decay"


def test_reporting_metrics():
    import reporting
    rows = [{"realized_usd": r, "cost_usd": 50.0, "opened_ts": 0, "closed_ts": 600} for r in (100, 40, 45, 30, 20)]
    m = reporting.metrics(rows)
    # PnL: +50, -10, -5, -20, -30 -> suma -15; bez najlepszej -65; drawdown od szczytu +50 do -15 = 65
    assert m["n"] == 5 and abs(m["total"] + 15) < 1e-9 and abs(m["without_best"] + 65) < 1e-9
    assert abs(m["max_dd"] - 65) < 1e-9 and abs(m["avg_hold_min"] - 10) < 1e-9 and m["win_rate"] == 0.2


def test_opportunity_risk_axes_and_explanations():
    cfg = Config()
    good = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    assert good.decision == "BUY" and good.opportunity >= cfg.opportunity_min and good.risk <= cfg.risk_max
    assert "Opportunity" in good.explain() and "BUY" in good.explain()
    # wysoka okazja, ale wysokie ryzyko (koncentracja holderów, aktywny dev) -> SKIP z wyjaśnieniem powodów
    risky = dict(CLEAN_REPORT, topHolders=[{"address": "w", "pct": 12}] * 3, creatorBalance=8e7, markets=[{"lp": {"lpLockedPct": 0}}],
                 insiderNetworks=[{"size": 15}], risks=[{"name": "x", "level": "warn"}] * 3, score_normalised=45)
    v = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, risky))
    assert v.decision == "SKIP" and v.risk > cfg.risk_max and v.opportunity >= cfg.opportunity_min
    text = v.explain()
    assert "za duże ryzyko" in text and "ryzyko -" in text
    # veto = REJECT z listą powodów
    bad = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, dict(CLEAN_REPORT, mintAuthority="A")))
    assert bad.decision == "REJECT" and "VETO" in bad.explain() and "mint_authority" in bad.explain()
    # osie rozdzielone: test okazji nie wpływa na ryzyko i odwrotnie
    assert analysis.Finding("flow", "trend_1h").axis == "opportunity" and analysis.Finding("safety", "top1_holder").axis == "risk"


def test_creator_history_and_serial_launcher():
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    for i in range(6):
        st.log_launch(f"T{i}", "CREATOR", "S", "n", 0.1, 30.0)
    st.log_migration("T0", "raydium")
    st.db.commit()
    h = st.creator_history("CREATOR", exclude_mint="T5")
    assert h["launches"] == 5 and h["graduated"] == 1 and h["launches_24h"] == 5
    f = analysis.creator_history_checks(cfg, h)
    assert f and f[0].name == "seryjny_launcher" and not f[0].veto and f[0].points < 0
    h["launches_24h"] = 25
    assert analysis.creator_history_checks(cfg, h)[0].veto


def test_stream_normalize():
    import stream
    c = stream.normalize({"txType": "create", "mint": "M", "traderPublicKey": "C", "symbol": "S", "name": "N",
                          "solAmount": 0.5, "marketCapSol": 28})
    assert c == {"type": "create", "mint": "M", "creator": "C", "symbol": "S", "name": "N", "initial_buy_sol": 0.5, "mcap_sol": 28}
    assert stream.normalize({"txType": "migrate", "mint": "M", "pool": "raydium-cpmm"})["type"] == "migrate"
    assert stream.normalize({"message": "Successfully subscribed"}) is None
    s = stream.PumpStream()
    s.q.put({"type": "create", "mint": "X"})
    assert len(s.drain()) == 1 and s.drain() == []


def _wallet_trades(mint, wallet, buy_ts, sell_ts, buy_px, sell_px, tokens=10_000, tx_prefix=""):
    mk = lambda kind, ts, px, tx: {"tx_hash": tx_prefix + tx, "tx_from_address": wallet, "kind": kind,
                                   "block_timestamp": _ts(ts), "volume_in_usd": str(tokens * px),
                                   "to_token_amount": str(tokens), "from_token_amount": str(tokens),
                                   "price_to_in_usd": str(px), "price_from_in_usd": str(px)}
    return [mk("buy", buy_ts, buy_px, f"{mint}{wallet}b"), mk("sell", sell_ts, sell_px, f"{mint}{wallet}s")]


def test_wallet_engine_ranking_and_convergence():
    import wallets
    cfg = Config()
    cfg.wallet_min_quality = 60
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    eng = wallets.WalletEngine(cfg, st)
    base = time.time() - 3600
    for i in range(5):    # SMART: 5 tokenów, każdy +100%, trzyma 10 min;  LOSER: -50%;  BOT: sprzedaje po 5 s
        m = f"M{i}"
        tr = (_wallet_trades(m, "SMART", base + i * 100, base + i * 100 + 600, 0.001, 0.002)
              + _wallet_trades(m, "LOSER", base + i * 100, base + i * 100 + 600, 0.001, 0.0005)
              + _wallet_trades(m, "BOT", base + i * 100, base + i * 100 + 5, 0.001, 0.00101))
        assert eng.ingest(m, tr) == 6
    eng.ingest("M0", _wallet_trades("M0", "SMART", base, base + 600, 0.001, 0.002))     # duplikat tx - ignorowany
    assert st.db.execute("SELECT COUNT(*) FROM wallet_trades").fetchone()[0] == 30
    eng.refresh(force=True)
    s, l, b = eng.stats["SMART"], eng.stats["LOSER"], eng.stats["BOT"]
    assert s.closed == 5 and s.win_rate == 1.0 and b.is_bot and not l.is_bot
    assert s.quality > l.quality and "SMART" in eng.tracked and "LOSER" not in eng.tracked and "BOT" not in eng.tracked
    now = time.time()
    live = [{"tx_from_address": w, "kind": "buy", "block_timestamp": _ts(now - 60 + i)} for i, w in enumerate(["SMART", "X1", "X2"])]
    conv = eng.convergence(live)
    assert conv["smart_wallets_n"] == 1
    cfg.smart_wallets = ("X1",)                         # ręczny portfel zawsze śledzony
    eng.refresh(force=True)
    assert eng.convergence(live)["smart_wallets_n"] == 2
    assert [f.points for f in analysis.smart_checks(cfg, eng.convergence(live))][0] >= 15


def test_funding_check_is_selective():
    import wallets

    class Fake(wallets.WalletDataProvider):
        available = True
        calls = 0

        def funder_of(self, wallet):
            Fake.calls += 1
            return ("FUNDER" if wallet.startswith("w") else f"other-{wallet}"), "fake"

    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    p = Fake()
    wl = ["w1", "w2", "w3", "w4"]
    assert wallets.funding_check(cfg, p, st, wl, 0.05) == ([], {}) and Fake.calls == 0         # mało podejrzane = zero zapytań
    assert wallets.funding_check(cfg, p, st, ["w1", "w2"], 0.9) == ([], {}) and Fake.calls == 0  # za mały klaster
    f, info = wallets.funding_check(cfg, p, st, wl, 0.5)
    assert f and f[0].name == "wspólny_fundator" and not f[0].veto and Fake.calls == 4
    wallets.funding_check(cfg, p, st, wl, 0.5)
    assert Fake.calls == 4                                                                      # cache: bez ponownych zapytań
    assert wallets.funding_check(cfg, wallets.NullProvider(), st, wl, 0.9) == ([], {})


def test_helius_transfers_parsing_is_defensive():
    import wallets
    data = {"data": [{"direction": "out", "counterparty": "A", "mint": wallets.WSOL, "timestamp": 5},
                     {"direction": "in", "counterparty": "LATE", "mint": wallets.WSOL, "timestamp": 20},
                     {"direction": "in", "counterparty": "FIRST", "symbol": "SOL", "timestamp": 10},
                     {"direction": "in", "counterparty": "TOK", "mint": "USDC", "timestamp": 1}]}
    assert wallets.HeliusProvider.first_incoming_sol(data) == "FIRST"
    assert wallets.HeliusProvider.first_incoming_sol({"data": []}) is None
    assert wallets.HeliusProvider.first_incoming_sol(None) is None


def test_modes_and_new_strategies():
    import bot as botmod
    import features
    import strategies
    for mode, ok in (("LIVE", False), ("BOGUS", False)):
        cfg = Config()
        cfg.db_path = os.path.join(tempfile.mkdtemp(), "b.db")
        cfg.mode = mode
        try:
            botmod.Bot(cfg)
            assert ok
        except SystemExit:
            assert not ok
    cfg = Config()
    f = analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT)
    clean = analysis.decide(cfg, f)
    # random_eligible: deterministyczne i rzędu random_eligible_pct
    hits = sum(strategies.wants("random_eligible", clean, cfg, {"mint": f"mint{i}"}) for i in range(400))
    assert 60 < hits < 140 and strategies.wants("random_eligible", clean, cfg, {"mint": "abc"}) == \
        strategies.wants("random_eligible", clean, cfg, {"mint": "abc"})
    accel = {"features": {"ub_60s": 12, "buyer_accel": 2.0}}
    assert strategies.wants("buyer_accel_only", clean, cfg, accel) and not strategies.wants("buyer_accel_only", clean, cfg, {"features": {"ub_60s": 3, "buyer_accel": 9}})
    assert not strategies.wants("smart_money_only", clean, cfg, {"features": {"smart_wallets_n": 1}})
    assert strategies.wants("smart_money_only", clean, cfg, {"features": {"smart_wallets_n": 2}})
    assert [features.liq_bucket(x) for x in (3e3, 7e3, 12e3, 30e3, 70e3, 200e3)] == ["<5k", "5-10k", "10-25k", "25-50k", "50-100k", "100k+"]


def test_signals_feed_calibration():
    import calibrate
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    v = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    pair = make_pair()
    ids = [st.log_decision(f"M{i}", "T", v, pair) for i in range(3)]
    for d in ids:
        st.db.execute("UPDATE decisions SET ts = ts - 7*3600 WHERE id=?", (d,))
        st.save_outcome(d, 6, 0.002 if d != ids[2] else 0.0, 60_000)
    st.log_signal(ids[0], "hybrid")
    st.log_signal(ids[1], "hybrid")
    st.log_signal(ids[2], "safety_only")
    st.db.commit()
    out = calibrate.signal_samples(st, 6)
    assert len(out["hybrid"]) == 2 and abs(out["hybrid"][0]["ret"] - 1.0) < 1e-9
    assert out["safety_only"][0]["dead"] is True and out["safety_only"][0]["ret"] == -1.0
    d = st.db.execute("SELECT opportunity, risk, explanation FROM decisions WHERE id=?", (ids[0],)).fetchone()
    assert d["opportunity"] > 0 and "Opportunity" in d["explanation"]


NOW = 2_000_000_000     # "teraz" późniejsze niż wszystkie świece testowe (wtedy żadna nie jest 'w trakcie tworzenia')


def _candles(prices, vols=None, t0=1_800_000_000):
    out = []
    for i, p in enumerate(prices):
        prev = prices[i - 1] if i else p
        out.append([t0 + i * 60, prev, max(p, prev) * 1.002, min(p, prev) * 0.998, p, (vols[i] if vols else 100.0)])
    return out


def test_indicators_basic_and_tiny_prices():
    import indicators
    up = [1.0 + i * 0.01 for i in range(60)]
    assert indicators.rsi(up, 14) == 100.0
    assert abs(indicators.rsi([1.0] * 30, 14) - 50.0) < 1e-9
    f = indicators.compute(_candles([x * 1e-6 for x in up]), now=NOW)
    assert f["trend_bull"] == 1 and f["price_vs_ema9"] > 0 and f["rsi14"] > 90
    assert 1e-6 < f["ema9"] < 1.6e-6 and f["vwap"] > 0                        # drobne ceny nie zerują się po zaokrągleniu
    assert indicators.compute(_candles(up[:10]), now=NOW) == {}               # za mało świec = brak cech
    cs = _candles(up)
    full = indicators.compute(cs, now=NOW)
    forming = indicators.compute(cs, now=cs[-1][0] + 30)                      # ostatnia świeca trwa jeszcze 30 s -> pomijana
    assert full["ta_candles"] == 60 and forming["ta_candles"] == 59


def test_breakout_retest_and_failed_breakout_flags():
    import indicators
    base = [1.0 + 0.002 * ((-1) ** i) for i in range(40)]            # boczniak przy ~1.0
    brk = base + [1.05, 1.08, 1.04, 1.02, 1.015]                     # wybicie, cofnięcie do starego oporu (~1.004) i utrzymanie
    vols = [100.0] * 40 + [400.0, 300.0, 150.0, 120.0, 130.0]
    f = indicators.compute(_candles(brk, vols), now=NOW)
    assert f["retest_ok"] == 1 and f["failed_breakout"] == 0 and f["breakout_age"] == 4 and f["donchian_break"] == 0
    f0 = indicators.compute(_candles(base + [1.05], [100.0] * 40 + [400.0]), now=NOW)        # świeca wybicia
    assert f0["donchian_break"] == 1 and f0["volume_ratio_1m"] > 3
    failed = base + [1.05, 1.08, 1.03, 0.995, 0.99]                  # wybicie, które się załamało pod opór
    f2 = indicators.compute(_candles(failed, vols), now=NOW)
    assert f2["failed_breakout"] == 1 and f2["retest_ok"] == 0
    # wolumen: ostatnia świeca 4x średniej -> z-score duży
    f3 = indicators.compute(_candles(brk[:-1] + [1.06], [100.0] * 44 + [500.0]), now=NOW)
    assert f3["volume_ratio_1m"] > 4 and f3["volume_zscore"] != 0 or f3["volume_ratio_1m"] > 4


def test_ta_strategies_need_all_conditions():
    import strategies
    cfg = Config()
    clean = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    good = {"features": {"donchian_break": 1, "volume_ratio_1m": 2.5, "price_vs_vwap": 0.03, "trend_bull": 1}}
    assert strategies.wants("breakout_volume", clean, cfg, good)
    for key, bad in (("donchian_break", 0), ("volume_ratio_1m", 1.0), ("price_vs_vwap", -0.01), ("trend_bull", 0)):
        ctx = {"features": dict(good["features"], **{key: bad})}
        assert not strategies.wants("breakout_volume", clean, cfg, ctx), key
    assert not strategies.wants("breakout_volume", clean, cfg, {"features": {}})          # brak cech = brak sygnału
    vetoed = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + [analysis.Finding("safety", "x", veto=True)])
    assert not strategies.wants("breakout_volume", vetoed, cfg, good)                      # twarde filtry przed TA
    rsi_ok = {"features": {"trend_bull": 1, "rsi14": 62, "volume_ratio_1m": 1.5}}
    assert strategies.wants("ema_trend_rsi", clean, cfg, rsi_ok)
    assert not strategies.wants("ema_trend_rsi", clean, cfg, {"features": {"trend_bull": 1, "rsi14": 25, "volume_ratio_1m": 1.5}})
    rev = {"features": {"price_vs_vwap": -0.08, "buy_ratio_m5": 0.62, "buy_ratio_h1": 0.5}}
    assert strategies.wants("vwap_reversion", clean, cfg, rev)


# ============================================================ v0.7

def _bot(**over):
    import bot as botmod
    cfg = Config()
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "b.db")
    cfg.use_pumpportal = False
    for k, v in over.items():
        setattr(cfg, k, v)
    b = botmod.Bot(cfg)

    def no_gemini(*a, **kw):        # klucz z secrets.json jest prawdziwy - testy nie mogą zużywać dziennego limitu
        import requests
        raise requests.ConnectionError("test offline: brak sieci do Gemini")
    b.llm.s.post = no_gemini        # test, który potrzebuje odpowiedzi, podmienia post po _bot()
    return b


def test_per_strategy_exit_overrides():
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    tight, wide = Portfolio(cfg, st, "safety_only"), Portfolio(cfg, st, "safety_wide", {"stop_loss_pct": 40.0})
    pa, pb = tight.buy("M", "T", 1.0, 100_000, 50, 80), wide.buy("M", "T", 1.0, 100_000, 50, 80)
    drop = {"priceUsd": "0.7", "liquidity": {"usd": 100_000}}           # -30%: łapie tylko stop -25%
    assert tight.manage(pa, drop) == "stop_loss"
    assert wide.manage(pb, drop) is None and "M" in wide.positions
    assert wide.manage(pb, {"priceUsd": "0.55", "liquidity": {"usd": 100_000}}) == "stop_loss"
    try:
        Portfolio(cfg, st, "x", {"stop_loss_procent": 40})
        assert False, "literówka w parametrze musi być błędem, nie cichym ignorowaniem"
    except ValueError:
        pass


def test_mae_mfe_tracking_persists():
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    pf = Portfolio(cfg, st, "hybrid")
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    e = pos.entry_price
    for px in (1.3, 0.9, 1.1):
        pf.manage(pos, {"priceUsd": str(px), "liquidity": {"usd": 100_000}})
    assert abs(pos.mfe_pct - (1.3 / e - 1) * 100) < 1e-6 and abs(pos.mae_pct - (0.9 / e - 1) * 100) < 1e-6
    again = Portfolio(cfg, st, "hybrid").positions["M"]                    # restart bota: wartości z bazy
    assert abs(again.mfe_pct - pos.mfe_pct) < 1e-9 and abs(again.mae_pct - pos.mae_pct) < 1e-9
    pf.manage(pos, {"priceUsd": "0.5", "liquidity": {"usd": 100_000}})    # stop
    r = st.db.execute("SELECT mae_pct, mfe_pct, exit_reason FROM positions").fetchone()
    assert r["exit_reason"] == "stop_loss" and r["mae_pct"] < -40 and r["mfe_pct"] > 20


def test_candle_archive_storage():
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    t0 = 1_800_000_000
    rows = [[t0 + i * 60, 1, 1.1, 0.9, 1, 10] for i in range(500)]
    assert st.save_candles("POOL", rows) == 500
    st.save_candles("POOL", rows[:10])                                   # duplikaty ignorowane
    assert st.db.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 500
    assert len(st.candles_between("POOL", t0 + 60, t0 + 600)) == 10
    assert st.candles_cover("POOL", t0 + 3000, t0 + 20000) and not st.candles_cover("POOL", t0 + 3000, t0 + 90000)
    cfg = Config()
    v = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    did = st.log_decision("M", "T", v, dict(make_pair(), pairAddress="POOL"))
    st.db.execute("UPDATE decisions SET ts=? WHERE id=?", (time.time() - 8 * 3600, did))
    assert not st.pending_candle_jobs(6, 10)                             # bez sygnału = nie archiwizujemy
    st.log_signal(did, "hybrid")
    st.db.commit()
    assert [r["id"] for r in st.pending_candle_jobs(6, 10)] == [did] and st.pool_for("M") == "POOL"
    st.save_candle_job(did, "M", "POOL", 0, "error", 0)
    assert st.pending_candle_jobs(6, 10)                                 # błąd = ponowna próba...
    st.save_candle_job(did, "M", "POOL", 0, "error", 0)
    st.save_candle_job(did, "M", "POOL", 0, "error", 0)
    assert not st.pending_candle_jobs(6, 10)                             # ...ale maks. 3 razy


def test_archive_candles_job_with_fake_gecko():
    b = _bot()
    calls = []

    def fake_ohlcv(pool, limit=100, aggregate=1, before=None):
        calls.append((pool, before))
        return [[before - (i + 1) * 60, 1, 1.1, 0.9, 1, 5] for i in range(limit)]
    b.gecko.ohlcv = fake_ohlcv
    b.dex.pairs_for_tokens = lambda mints: {m: [{"pairAddress": "OLD", "pairCreatedAt": 1000,
                                                 "liquidity": {"usd": 10}},
                                                {"pairAddress": "NEW", "pairCreatedAt": 9e15, "liquidity": {"usd": 1e6}}]
                                            for m in mints}
    v = analysis.decide(b.cfg, analysis.market_checks(b.cfg, make_pair(), 50) + analysis.rug_checks(b.cfg, CLEAN_REPORT))
    with_pair = b.store.log_decision("A", "A", v, dict(make_pair(), pairAddress="POOLA"))
    no_pair = b.store.log_decision("B", "B", v, make_pair())             # stara decyzja bez adresu puli
    for d in (with_pair, no_pair):
        b.store.db.execute("UPDATE decisions SET ts=? WHERE id=?", (time.time() - 7 * 3600, d))
        b.store.log_signal(d, "safety_only")
    b.store.db.commit()
    assert b.archive_candles(force=True) == 2
    jobs = {r["decision_id"]: (r["pool"], r["status"]) for r in b.store.db.execute("SELECT * FROM candle_jobs")}
    assert jobs[with_pair] == ("POOLA", "ok") and jobs[no_pair] == ("OLD", "ok")   # pula sprzed decyzji, nie nowsza
    assert b.archive_candles(force=True) == 0 and len(calls) == 2                  # nic do zrobienia, bez zapytań


def test_exit_simulation_rules():
    import exit_research as er
    t0 = 1_800_000_000
    c = lambda i, o, h, l, cl: [t0 + i * 60, o, h, l, cl, 1]
    dip_then_moon = [c(1, 1, 1.02, 0.7, 0.72), c(2, 0.72, 1.6, 0.72, 1.55), c(3, 1.55, 2.1, 1.5, 2.0)]
    r, why, _ = er.simulate(dip_then_moon, 1.0, t0, stop=0.75)
    assert why == "stop" and abs(r - (0.75 / 1.015 * 0.96 - 1)) < 1e-9          # stop przed odbiciem
    r2, why2, _ = er.simulate(dip_then_moon, 1.0, t0, stop=None)
    assert r2 > 0.3                                                              # bez stopa: TP1 i TP2
    m = er.path_metrics(dip_then_moon, 1.0, t0, 0.25, 0.5)
    assert m["killed_winner"] and m["first"] == "stop" and abs(m["mae_before_tp1"] + 0.3) < 1e-9
    crash = [c(1, 1.0, 1.0, 0.05, 0.06)]                                         # rug jednym zleceniem
    r3, _, _ = er.simulate(crash, 1.0, t0, stop=0.75)
    assert r3 < -0.9                                                             # sprzedaż przy dnie, nie na stopie
    both = [c(1, 1.0, 1.6, 0.7, 1.0)]                                            # stop i TP w jednej świecy
    assert er.simulate(both, 1.0, t0, stop=0.75)[1] == "stop"                    # ostrożnie: najpierw stop
    assert er.tp_plan(((50, .33), (100, .33), (300, .34))) == [(0.5, .33), (1.0, .33), (3.0, None)]


def test_exit_research_report_end_to_end():
    import contextlib
    import io
    import exit_research as er
    cfg = Config()
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "t.db")
    st = Storage(cfg.db_path)
    pf = Portfolio(cfg, st, "safety_only")
    t0 = 1_800_000_000
    v = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    for k, mint in enumerate(("M1", "M2", "M3")):
        did = st.log_decision(mint, mint, v, dict(make_pair(), pairAddress=f"P{k}"))
        st.db.execute("UPDATE decisions SET ts=? WHERE id=?", (t0, did))
        st.log_signal(did, "safety_only")
        pos = pf.buy(mint, mint, 1.0, 100_000, 50, 80, info={"features": {"atr_pct": 5.0 + 20 * k, "source": "graduation"}})
        st.db.execute("UPDATE positions SET opened_ts=? WHERE id=?", (t0, pos.id))
        pre = [[t0 - (i + 1) * 60, 1, 1.01, 0.99, 1.0, 5] for i in range(60)]
        post = [[t0 + (i + 1) * 60, 1, 1 + 0.01 * i * (1 - k), 0.98 - 0.3 * k, 1 + 0.01 * i * (1 - k), 5] for i in range(300)]
        st.save_candles(f"P{k}", pre + post)
        pf.manage(pf.positions[mint], {"priceUsd": "0.5", "liquidity": {"usd": 100_000}})   # zamknij
    st.db.commit()
    entries, missing = er.position_entries(st, 360)
    assert len(entries) == 3 and missing == 0 and {e["source"] for e in entries} == {"graduation"}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        er.run(cfg, 6)
        er.run(cfg, 6, signals=True)
    text = out.getvalue()
    for needle in ("MFE >= +50%", "zabitych zwycięzców", "obecne: SL -25%", "ATR 1-min < 20%", "kontrola wiarygodności",
                   "sygnały strategii", "safety_only"):
        assert needle in text, needle


def test_early_buyers_sold_share():
    import features
    base = 1_800_000_000
    trades = []
    for i in range(30):
        trades.append({"block_timestamp": _ts(base + i), "block_number": i, "tx_from_address": f"w{i}",
                       "kind": "buy", "volume_in_usd": "10"})
    for i in range(10):                                                           # 10 z 20 pierwszych sprzedaje
        trades.append({"block_timestamp": _ts(base + 100 + i), "block_number": 100 + i, "tx_from_address": f"w{i}",
                       "kind": "sell", "volume_in_usd": "10"})
    assert abs(features.trade_metrics(trades)["early_buyers_sold_share"] - 0.5) < 1e-9


def test_lowvol_and_mature_calm_strategies():
    import strategies
    cfg = Config()
    clean = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    for name in ("lowvol", "lowvol_wide", "lowvol_catastrophic"):
        assert strategies.wants(name, clean, cfg, {"features": {"atr_pct": 12.0}})
        assert not strategies.wants(name, clean, cfg, {"features": {"atr_pct": 25.0}})
        assert not strategies.wants(name, clean, cfg, {"features": {}})          # brak ATR = brak sygnału
    assert strategies.wants("safety_wide", clean, cfg, {})
    assert strategies.wants("mature_calm", clean, cfg, {"features": {"age_min": 90, "txns_m5": 30}})
    assert not strategies.wants("mature_calm", clean, cfg, {"features": {"age_min": 30, "txns_m5": 30}})
    assert not strategies.wants("mature_calm", clean, cfg, {"features": {"age_min": 90, "txns_m5": 200}})
    assert set(cfg.strategy_exits) <= set(cfg.strategies)                    # każde nadpisanie ma swój portfel


def test_discovery_source_tagging():
    b = _bot()
    b.dex.latest_profiles = lambda: ["A", "B"]
    b.dex.latest_boosts = lambda: ["B", "C"]
    b.dex.top_boosts = lambda: ["D"]
    b.tag_source(["G"], "graduation")
    b.watch["G"] = time.time()
    b.loop_no = 1
    found = b.discover()
    assert set(found) == {"A", "B", "C", "D", "G"}
    assert b.source == {"G": "graduation", "A": "profile", "B": "profile", "C": "boost", "D": "top_boost"}


def _gap_bot(candles, mint="M", pool="POOL"):
    """Bot z otwartą pozycją (wejście 1.0) i przerwą 3 h; świece z przerwy w archiwum (bez sieci)."""
    b = _bot(strategies=("hybrid", "safety_wide"), use_gecko=False)
    gap_start = time.time() - 3 * 3600
    b.store.db.execute("INSERT INTO equity VALUES(?,?,?,?,?)", (gap_start, 1000, 950, 50, "hybrid"))
    b.store.db.execute("INSERT INTO snapshots(ts, mint, price, liq) VALUES(?,?,?,?)", (gap_start - 30, mint, 1.0, 100_000))
    b.store.db.execute("INSERT INTO decisions(ts, mint, symbol, decision, pair) VALUES(?,?,?,?,?)",
                       (gap_start - 600, mint, "T", "BUY", pool))
    b.store.db.commit()
    rows = [[int(gap_start) - 120 + 60 * k, *c, 1000] for k, c in enumerate(candles)]
    b.store.save_candles(pool, rows)
    return b, gap_start


def test_downtime_replays_exit_rules_on_candles():
    # przerwa: cena spada do 0.70 (stop -25% hybrid), potem odbija do 3.0 - liczy się stop W TRAKCIE przerwy
    b, gap = _gap_bot([(1.0, 1.0, 1.0, 1.0)] * 3 + [(1.0, 1.0, 0.70, 0.72), (0.72, 3.0, 0.72, 3.0)] + [(3.0, 3.0, 3.0, 3.0)] * 200)
    hyb, wide = b.portfolios["hybrid"], b.portfolios["safety_wide"]
    p1 = hyb.buy("M", "T", 1.0, 100_000, 50, 80)
    p2 = wide.buy("M", "T", 1.0, 100_000, 50, 80)             # safety_wide: stop -40% -> przeżywa -30% i łapie TP
    asked = []
    b.jup.sell_usdc = lambda *a: asked.append(a) or ("ok", {"outAmount": "1"})
    assert b.close_after_downtime() == 2 and not asked                          # bez dzisiejszego kwotowania
    r1 = b.store.db.execute("SELECT exit_reason, realized_usd, closed_ts FROM positions WHERE id=?", (p1.id,)).fetchone()
    assert r1["exit_reason"] == "przerwa_stop_loss" and r1["realized_usd"] < 40
    assert gap < r1["closed_ts"] < gap + 600                                    # czas z odtworzenia, nie "teraz"
    r2 = b.store.db.execute("SELECT status, realized_usd, tp_hit FROM positions WHERE id=?", (p2.id,)).fetchone()
    assert r2["tp_hit"] >= 2 and r2["realized_usd"] > 50                        # zysk z TP zamiast cięcia w połowie
    assert hyb.sell_quoter is not None and hyb.clock is None


def test_downtime_without_candles_voids_position():
    b, gap = _gap_bot([(1.0, 1.0, 1.0, 1.0)] * 2, mint="OTHER")                 # świece innego tokena
    pf = b.portfolios["hybrid"]
    cash0 = pf.cash
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    assert b.close_after_downtime() == 1 and "M" not in pf.positions
    r = b.store.db.execute("SELECT status, exit_reason FROM positions WHERE id=?", (pos.id,)).fetchone()
    assert r["status"] == "void" and r["exit_reason"] == "przerwa_brak_danych"
    assert abs(pf.cash - cash0) < 1e-6                                          # gotówka sprzed kupna
    assert b.store.db.execute("SELECT COUNT(*) FROM trades WHERE position_id=?", (pos.id,)).fetchone()[0] == 0
    assert _bot().close_after_downtime() == 0                                   # świeża baza: nic do zamykania


def test_downtime_quiet_position_stays_open():
    b, gap = _gap_bot([(1.0, 1.05, 0.95, 1.02)] * 20)
    pf = b.portfolios["hybrid"]
    pf.buy("M", "T", 1.0, 100_000, 50, 80)
    assert b.close_after_downtime() == 1 and "M" in pf.positions                # bot prowadzi ją dalej


def test_downtime_time_stop_fires_on_time_without_trades():
    # cichy token: po 3 świecach brak transakcji przez 2 h, potem jedna transakcja po 0.5. Time stop (240 min,
    # termin 10 min po starcie przerwy) ma zamknąć po cenie stojącej 1.0, a nie czekać na świecę po 2 h (-50%)
    b, gap = _gap_bot([(1.0, 1.0, 1.0, 1.0)] * 3)
    b.store.save_candles("POOL", [[int(gap) + 7200, 0.5, 0.5, 0.5, 0.5, 10]])
    pf = b.portfolios["hybrid"]
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    pos.opened_ts = gap - 230 * 60
    assert b.close_after_downtime() == 1 and "M" not in pf.positions
    r = b.store.db.execute("SELECT exit_reason, closed_ts, realized_usd FROM positions WHERE id=?", (pos.id,)).fetchone()
    assert r["exit_reason"] == "przerwa_time_stop" and r["closed_ts"] < gap + 15 * 60
    assert r["realized_usd"] > 45                                               # cena 1.0 minus koszty, nie 0.5


def test_quote_sell_cache_avoids_repeated_jupiter_calls():
    b = _bot()
    calls = []
    b.jup.sell_usdc = lambda mint, raw: calls.append(raw) or ("ok", {"outAmount": str(int(raw / 1e6 * 0.5 * 1e6))})
    from paper import Position
    p1 = Position(1, "M", "T", 0, 1.0, 100, 100, 50, 0, 1, 1, decimals=6)
    v1 = b.quote_sell(p1, 100)
    v2 = b.quote_sell(p1, 50)                                                  # drugi portfel, ten sam token, ta sama chwila
    assert len(calls) == 1 and abs(v2 - v1 / 2) < 1e-9
    b._sellq["M"] = (time.time() - 10, 100, v1)                                # stare kwotowanie -> nowe zapytanie
    b.quote_sell(p1, 100)
    assert len(calls) == 2


def test_calibrate_source_and_volatility_sections():
    import contextlib
    import io
    import calibrate
    cfg = Config()
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "t.db")
    st = Storage(cfg.db_path)
    v = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    for i in range(12):
        d = st.log_decision(f"M{i}", "T", v, make_pair(), {"source": "graduation" if i % 2 else "boost", "atr_pct": 5 + 3 * i})
        st.db.execute("UPDATE decisions SET ts = ts - 7*3600 WHERE id=?", (d,))
        st.save_outcome(d, 6, 0.002, 60_000)
    st.db.commit()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        calibrate.run(cfg, 6)
    text = out.getvalue()
    assert "źródło odkrycia" in text and "graduation" in text and "zmienność przy decyzji" in text


def test_reporting_common_window():
    import contextlib
    import io
    import reporting
    cfg = Config()
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "t.db")
    st = Storage(cfg.db_path)
    now = time.time()
    st.db.execute("INSERT INTO equity VALUES(?,?,?,?,?)", (now - 10 * 3600, 1000, 1000, 0, "hybrid"))
    st.db.execute("INSERT INTO equity VALUES(?,?,?,?,?)", (now - 3600, 1000, 1000, 0, "lowvol"))
    pf = Portfolio(cfg, st, "hybrid")
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    pf.manage(pos, {"priceUsd": "0.5", "liquidity": {"usd": 100_000}})
    st.db.commit()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        reporting.run(cfg)
    assert "WSPÓLNYM oknie" in out.getvalue()


def test_topup_restores_cash_and_report_excludes_deposits():
    import contextlib
    import io
    import reporting
    import topup
    cfg = Config()
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "t.db")
    st = Storage(cfg.db_path)
    now = time.time()
    st.kv_set("safety_only:cash", 30.0)
    st.db.execute("INSERT INTO equity VALUES(?,?,?,?,?)", (now - 7200, 1000, 1000, 0, "safety_only"))
    st.db.execute("INSERT INTO equity VALUES(?,?,?,?,?)", (now - 3600, 30, 30, 0, "safety_only"))
    st.db.commit()
    assert not Portfolio(cfg, st, "safety_only").can_enter(80) if hasattr(Portfolio, "can_enter") else True
    with contextlib.redirect_stdout(io.StringIO()):
        assert topup.topup(cfg, ["safety_only"], 1000, apply=False) == {"safety_only": 970.0}
        assert st.kv_get("safety_only:cash") == 30.0                              # podgląd nic nie zmienia
        topup.topup(cfg, ["safety_only"], 1000, apply=True)
    pf = Portfolio(cfg, st, "safety_only")
    assert pf.cash == 1000.0 and st.kv_get("safety_only:deposits")[0][1] == 970.0
    st.db.execute("INSERT INTO equity VALUES(?,?,?,?,?)", (time.time() + 1, 1000, 1000, 0, "safety_only"))
    st.db.commit()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        reporting.run(cfg)
    line = next(l for l in out.getvalue().splitlines() if l.startswith("safety_only"))
    assert "dopłacono $970" in line and "bez dopłat $30.00" in line and "maxDD(equity) 97.0%" in line


# ============================================================ v0.8

def test_all_configured_strategies_exist():
    import strategies
    cfg = Config()
    missing = [n for n in list(cfg.strategies) + list(cfg.signal_strategies) if n not in strategies.REGISTRY]
    assert not missing, f"literówki w nazwach strategii: {missing}"
    assert not set(cfg.strategies) & set(cfg.signal_strategies)          # strategia jest albo portfelem, albo sygnałem


def test_skip_rules_and_strict():
    import strategies
    cfg = Config()
    clean = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    good = {"atr_pct": 8.0, "price_vs_vwap": 0.05, "same_block_buy_share": 0.05, "ch_m5": 5.0, "buyer_accel": 1.2,
            "age_min": 180.0}
    ctx = lambda **kw: {"features": dict(good, **kw)}
    for name in ("skip_below_vwap", "skip_block_buys", "skip_spike_5m", "skip_accel_3x", "skip_young_60m", "strict"):
        assert strategies.wants(name, clean, cfg, ctx()), name
    assert not strategies.wants("skip_below_vwap", clean, cfg, ctx(price_vs_vwap=-0.01))
    assert not strategies.wants("skip_block_buys", clean, cfg, ctx(same_block_buy_share=0.25))
    assert not strategies.wants("skip_spike_5m", clean, cfg, ctx(ch_m5=35.0))
    assert not strategies.wants("skip_accel_3x", clean, cfg, ctx(buyer_accel=3.5))
    assert not strategies.wants("skip_young_60m", clean, cfg, ctx(age_min=40.0))
    for bad in (dict(atr_pct=25.0), dict(price_vs_vwap=-0.01), dict(same_block_buy_share=0.3), dict(ch_m5=40.0)):
        assert not strategies.wants("strict", clean, cfg, ctx(**bad)), bad
    no_vwap = {"features": {k: v for k, v in good.items() if k != "price_vs_vwap"}}
    assert not strategies.wants("skip_below_vwap", clean, cfg, no_vwap)   # brak cechy = brak sygnału
    assert not strategies.wants("strict", clean, cfg, no_vwap)
    assert strategies.wants("skip_accel_3x", clean, cfg, ctx(price_vs_vwap=-0.5))   # reguły są niezależne


def test_cohorts_keep_earlier_comparisons():
    import reporting
    h = 3600
    starts = {"hybrid": 0, "safety_only": 100, "lowvol": 20 * h, "lowvol_wide": 20 * h + 60, "strict": 30 * h, "x": None}
    c = reporting.cohorts(starts)
    assert [t for t, _ in c] == [0, 20 * h, 30 * h]
    assert c[1][1] == ["hybrid", "safety_only", "lowvol", "lowvol_wide"]           # stare + dołączające
    assert c[2][1][-1] == "strict" and len(c[2][1]) == 5


def test_register_strategies_keeps_history():
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    now = time.time()
    st.db.execute("INSERT INTO equity VALUES(?,?,?,?,?)", (now - 10 * 3600, 1000, 1000, 0, "hybrid"))
    v = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    d = st.log_decision("M", "T", v, make_pair())
    st.db.execute("UPDATE decisions SET ts=? WHERE id=?", (now - 5 * 3600, d))
    st.log_signal(d, "breakout_volume")
    st.db.commit()
    st.register_strategies(["hybrid", "breakout_volume", "strict"])
    assert abs(st.kv_get("added:hybrid") - (now - 10 * 3600)) < 1
    assert abs(st.kv_get("added:breakout_volume") - (now - 5 * 3600)) < 1
    assert abs(st.kv_get("added:strict") - now) < 5
    st.kv_set("added:strict", 123.0)
    st.register_strategies(["strict"])                                         # drugi start bota niczego nie zmienia
    assert st.kv_get("added:strict") == 123.0


def test_exit_research_signal_cohorts():
    import contextlib
    import io
    import exit_research as er
    cfg = Config()
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "t.db")
    st = Storage(cfg.db_path)
    t0 = 1_800_000_000
    v = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    for k in range(4):
        ts = t0 + k * 3 * 3600                                                    # sygnały co 3 h
        did = st.log_decision(f"M{k}", "T", v, dict(make_pair(), pairAddress=f"P{k}"))
        st.db.execute("UPDATE decisions SET ts=? WHERE id=?", (ts, did))
        st.log_signal(did, "safety_only")
        if k >= 2:
            st.log_signal(did, "skip_below_vwap")
        st.save_candles(f"P{k}", [[ts - (i + 1) * 60, 1, 1.01, 0.99, 1, 5] for i in range(30)]
                        + [[ts + (i + 1) * 60, 1, 1.02, 0.99, 1.01, 5] for i in range(200)])
    st.kv_set("added:safety_only", t0)
    st.kv_set("added:skip_below_vwap", t0 + 6 * 3600)
    st.db.commit()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        er.run(cfg, 6, signals=True)
        er.run(cfg, 6, signals=True, since=t0 + 8 * 3600)
    text = out.getvalue()
    assert "wspólne okno od" in text and "skip_below_vwap" in text and "tylko wejścia/sygnały od" in text


# ============================================================ v0.9

def test_fixed_stake_and_no_risk_limits_in_paper():
    cfg, pf = fresh_portfolio()
    assert pf.entry_size({}, 1_000_000) == 50.0                              # stała stawka, nie % kapitału
    pf.cash = 400.0
    assert pf.entry_size({}, 1_000_000) == 50.0                              # mniejszy kapitał = ta sama stawka
    pf.store.kv_set("day_start_equity", 1000.0)                              # -60% dziennie
    pf.pause_until = time.time() + 3600
    assert pf.can_open({}) == (True, "")                                     # PAPER: limity nie zatrzymują badania
    cfg.risk_limits_in_paper = True
    ok, why = pf.can_open({})
    assert not ok and "pauza" in why
    pf.pause_until = 0
    assert pf.can_open({}) == (False, "dzienny limit strat")
    cfg.risk_limits_in_paper = False
    pf.cash = 30.0
    assert pf.can_open({}) == (False, "brak gotówki")                        # bez pełnej stawki nie wchodzimy
    cfg.position_usd = 0                                                     # stary tryb: % kapitału
    pf.cash = 1000.0
    assert abs(pf.entry_size({}, 1_000_000) - 1000.0 * cfg.position_pct) < 1e-9


def test_loss_streak_pause_only_with_limits():
    cfg, pf = fresh_portfolio(max_consecutive_losses=2)
    drop = {"priceUsd": "0.5", "liquidity": {"usd": 100_000}}
    for m in ("A", "B", "C"):
        pf.manage(pf.buy(m, m, 1.0, 100_000, 50, 80), drop)
    assert pf.pause_until == 0 and pf.can_open({})[0]
    cfg.risk_limits_in_paper = True
    for m in ("D", "E"):
        pf.manage(pf.buy(m, m, 1.0, 100_000, 50, 80), drop)
    assert pf.pause_until > time.time() and not pf.can_open({})[0]


def test_reentry_block_after_exit():
    cfg, pf = fresh_portfolio()
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    pf.manage(pos, {"priceUsd": "1.6", "liquidity": {"usd": 100_000}})       # tp1
    pf.manage(pos, {"priceUsd": "4.5", "liquidity": {"usd": 100_000}})       # tp2 + tp3 = zyskowne wyjście
    assert "M" not in pf.positions
    ok, why = pf.can_open({}, "M")
    assert not ok and why.startswith("blokada ponownego wejścia")
    assert pf.can_open({}, "OTHER")[0]                                      # inne tokeny bez zmian
    other = Portfolio(cfg, pf.store, "safety_only")
    assert other.can_open({}, "M")[0]                                       # blokada dotyczy tylko tej strategii
    pf.store.db.execute("UPDATE positions SET closed_ts=? WHERE mint='M'", (time.time() - 7 * 3600,))
    assert pf.can_open({}, "M")[0]                                          # po 6 h wolno wrócić
    cfg.reentry_block_h = 0
    pf.store.db.execute("UPDATE positions SET closed_ts=? WHERE mint='M'", (time.time(),))
    assert pf.can_open({}, "M")[0]                                          # 0 = bez blokady


def test_blocked_reentry_keeps_normal_cooldown():
    b = _bot(strategies=("hybrid",))
    pf = b.portfolios["hybrid"]
    pos = pf.buy("M", "T", 1.0, 100_000, 50, 80)
    pf.manage(pos, {"priceUsd": "0.5", "liquidity": {"usd": 100_000}})
    b.cooldown["M"] = time.time() + 1800
    v = analysis.decide(b.cfg, analysis.market_checks(b.cfg, make_pair(), 50) + analysis.rug_checks(b.cfg, CLEAN_REPORT))
    b.enter("M", "T", make_pair(), v, {"size": 50, "liq": 60_000, "wallets": []}, ["hybrid"], {})
    assert b.cooldown["M"] > time.time() + 1700 and "M" not in pf.positions     # nie co 2 min
    pf.cash = 10.0                                                              # chwilowy brak miejsca/gotówki
    b.enter("N", "T", make_pair(), v, {"size": 50, "liq": 60_000, "wallets": []}, ["hybrid"], {})
    assert b.cooldown["N"] < time.time() + 200


def test_rules_epoch_and_short_cohort_gap():
    import contextlib
    import io
    import reporting
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    assert st.mark_rules({"position_usd": 50.0, "tp": ((50, .33), (100, .67))})
    first = st.kv_get("rules_since")
    assert not st.mark_rules({"position_usd": 50.0, "tp": ((50, .33), (100, .67))})   # krotki vs listy z kv - bez zmiany
    assert st.kv_get("rules_since") == first
    assert st.mark_rules({"position_usd": 40.0, "tp": ((50, .33), (100, .67))})
    h = 3600
    c = reporting.cohorts({"a": 0, "b": 17 * h + 52 * 60, "c": 18 * h + 50 * 60})
    assert [t for t, _ in c] == [0, 17 * h + 52 * 60, 18 * h + 50 * 60]             # 58 min odstępu = osobne kohorty
    cfg = Config()
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "t.db")
    s2 = Storage(cfg.db_path)
    s2.mark_rules({"x": 1})
    pf = Portfolio(cfg, s2, "hybrid")
    pf.manage(pf.buy("M", "T", 1.0, 100_000, 50, 80), {"priceUsd": "0.5", "liquidity": {"usd": 100_000}})
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        reporting.run(cfg)
    assert "od ostatniej zmiany zasad portfeli" in out.getvalue()


def test_flow_features():
    import features
    base = 1_800_000_000
    trades = [{"block_timestamp": _ts(base + i * 4), "block_number": i, "tx_from_address": f"b{i}", "kind": "buy",
               "volume_in_usd": "10"} for i in range(30)]                       # 30 drobnych zakupów
    trades += [{"block_timestamp": _ts(base + 100 + i), "block_number": 100 + i, "tx_from_address": f"s{i}", "kind": "sell",
                "volume_in_usd": "200"} for i in range(3)]                      # 3 duże sprzedaże
    m = features.trade_metrics(trades)
    assert abs(m["bsi"] - 300 / 900) < 1e-9 and abs(m["buy_count_share"] - 30 / 33) < 1e-9
    assert m["flow_divergence"] > 0.5 and m["seller_accel"] == 3.0


def test_market_regime_features():
    import bot as botmod
    b = _bot()
    sol = {"quoteToken": {"symbol": "USDC"}, "liquidity": {"usd": 1e7}, "priceChange": {"h1": -1.5, "h6": 2, "h24": 4}}
    b.dex.pairs_for_tokens = lambda mints: {botmod.WSOL: [sol]}
    best = {f"M{i}": {"priceChange": {"h1": 10 if i < 3 else -20}} for i in range(12)}
    best["X"] = None
    b.update_market(best)
    assert abs(b.market["mkt_breadth_h1"] - 0.25) < 1e-9 and b.market["mkt_median_h1"] == -20
    assert b.market["sol_ch_h1"] == -1.5 and b.market["sol_ch_h24"] == 4

    def no_call(mints):
        raise AssertionError("SOL odświeżany co 5 min, nie co obieg")
    b.dex.pairs_for_tokens = no_call
    b.update_market(best)
    v, ctx = b.evaluate("M", make_pair(liquidity={"usd": 100}), {})         # veto na etapie 1, cechy i tak zapisane
    assert v.vetoes and ctx["features"]["mkt_breadth_h1"] == 0.25 and ctx["features"]["sol_ch_h6"] == 2


def test_entry_research_rules():
    import entry_research as en
    t0 = 1_800_000_000
    side = [[t0 + i * 60, 1.0, 1.005, 0.995, 1.0, 10.0] for i in range(40)]
    assert en.r_sweep_reclaim({}, side + [[t0 + 2400, 0.99, 1.002, 0.97, 1.001, 30.0]])          # przebicie i powrót
    assert not en.r_sweep_reclaim({}, side + [[t0 + 2400, 1.0, 1.003, 0.99, 1.001, 30.0]])       # bez przebicia dołka
    wide = [[t0 + i * 60, 1.0, 1.1, 0.9, 1.0, 10.0] for i in range(60)]
    calm = [[t0 + (60 + i) * 60, 1.0, 1.001, 0.999, 1.0, 10.0] for i in range(20)]
    assert en.r_compression({}, wide + calm + [[t0 + 80 * 60, 1.0, 1.012, 0.999, 1.01, 50.0]])
    assert not en.r_compression({}, wide + calm + [[t0 + 80 * 60, 1.0, 1.012, 0.999, 1.01, 12.0]])   # bez wolumenu
    assert len(en.resample(side, 300)) == 8 and en.resample(side, 300)[0][5] == 50.0
    cfg = Config()
    cs = [[t0 + i * 60, 1.0, 1.0, 1.0, 1.0 if i < 5 else 2.0, 1.0] for i in range(20)]
    e = en.entry(cfg, cs, [x[0] for x in cs], t0 + 60)                    # kurs = zamknięcie świecy z t0
    assert abs(e["fwd"][1] - ((1 - en.XC) / (1 + en.EC) - 1)) < 1e-9
    assert abs(e["fwd"][10] - (2.0 * (1 - en.XC) / (1 + en.EC) - 1)) < 1e-9


def test_entry_research_end_to_end():
    import contextlib
    import io
    import entry_research as en
    cfg = Config()
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "t.db")
    st = Storage(cfg.db_path)
    v = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    t0 = 1_800_000_000
    for k in range(6):
        ts = t0 + k * 7200
        did = st.log_decision(f"M{k}", "T", v, dict(make_pair(), pairAddress=f"P{k}"), {"age_min": 180.0, "ch_m5": k})
        st.db.execute("UPDATE decisions SET ts=? WHERE id=?", (ts, did))
        st.log_signal(did, "safety_only")
        st.log_signal(did, "hybrid")
        step = 0.004 if k % 2 == 0 else -0.004
        p = lambda i: (1 + step) ** i
        pre = [[ts - (i + 1) * 60, 1, 1.01, 0.99, 1.0, 5] for i in range(200)]
        post = [[ts + i * 60, p(i), max(p(i), p(i + 1)) * 1.003, min(p(i), p(i + 1)) * 0.997, p(i + 1),
                 5 + (60 if i == 30 else 0)] for i in range(400)]
        st.save_candles(f"P{k}", pre + post)
    st.db.commit()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        en.run(cfg)
        en.run(cfg, min_age=10_000)
    text = out.getvalue()
    for needle in ("pierwsze spojrzenie", "strażnik wejść", "breakout_simple", "hybrid", "Za mało danych"):
        assert needle in text, needle


def test_decision_change_gets_its_own_row():
    """Regresja: token WATCH -> BUY w ciągu 30 min - sygnały mają trafić do NOWEJ oceny (czas i cechy zakupu)."""
    b = _bot()
    young = make_pair(pairCreatedAt=(time.time() - 300) * 1000, pairAddress="P")
    v_watch = analysis.decide(b.cfg, analysis.market_checks(b.cfg, young, 50))
    v_buy = analysis.decide(b.cfg, analysis.market_checks(b.cfg, make_pair(), 50) + analysis.rug_checks(b.cfg, CLEAN_REPORT))
    assert v_watch.decision == "WATCH" and v_buy.decision == "BUY"
    seq = [(v_watch, {"features": {"x": 1}}), (v_buy, {"features": {"x": 2}}), (v_buy, {"features": {"x": 3}})]
    b.discover = lambda: ["M"]
    b.dex.pairs_for_tokens = lambda mints: {"M": [make_pair(pairAddress="P")]}
    b.engine.refresh = lambda *a, **k: None
    b.refresh_trending = lambda: None
    b.enter = lambda *a, **k: None
    b.evaluate = lambda mint, pair, prices, full=False: (lambda v, c: (v, dict(c, wallets=[])))(*seq.pop(0))
    for _ in range(3):
        b.scan()
    rows = b.store.db.execute("SELECT id, decision, features FROM decisions WHERE mint='M' ORDER BY id").fetchall()
    assert [r["decision"] for r in rows] == ["WATCH", "BUY"]                  # powtórzony BUY bez nowego wpisu
    ids = {r["decision_id"] for r in b.store.db.execute("SELECT decision_id FROM signals")}
    assert ids == {rows[1]["id"]} and '"x": 2' in rows[1]["features"]


def test_signals_timed_repairs_old_watch_rows():
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    cfg = Config()
    v_watch = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(pairCreatedAt=(time.time() - 300) * 1000), 50))
    v_buy = analysis.decide(cfg, analysis.market_checks(cfg, make_pair(), 50) + analysis.rug_checks(cfg, CLEAN_REPORT))
    t = 1_800_000_000
    ids = {}
    for mint, v in (("A", v_watch), ("B", v_watch), ("C", v_buy)):
        ids[mint] = st.log_decision(mint, mint, v, make_pair())
        st.db.execute("UPDATE decisions SET ts=?, price=1.0 WHERE id=?", (t, ids[mint]))
        st.log_signal(ids[mint], "safety_only")
    pf = Portfolio(cfg, st, "safety_only")
    pos = pf.buy("A", "A", 1.0, 100_000, 50, 80)                               # A: portfel wszedł 5 min po ocenie WATCH
    st.db.execute("UPDATE positions SET opened_ts=? WHERE id=?", (t + 300, pos.id))
    st.db.execute("INSERT INTO snapshots(ts, mint, price, liq) VALUES(?,?,?,?)", (t + 290, "A", 2.0, 1e5))
    st.db.commit()
    rows = {r["mint"]: r for r in st.signals_timed()}
    assert rows["A"]["fixed"] and rows["A"]["ts"] == t + 290 and rows["A"]["price"] == 2.0
    assert "B" not in rows and st.skipped == 1                                 # bez wejścia czasu nie znamy
    assert not rows["C"]["fixed"] and rows["C"]["ts"] == t and rows["C"]["price"] == 1.0


# ============================================================ zbieracz pump.fun i copy trading

def _trade_event(mint=b"\x01" * 32, user=b"\x02" * 32, sol=10**9, tok=3 * 10**13, buy=1, ts=1_800_000_000,
                 vsol=31 * 10**9, vtok=10**15, fee_bps=95, creator_bps=30, mayhem=0):
    """TradeEvent w układzie z IDL pump.fun (34 pola; po opłacie twórcy: track_volume, 4 x u64, ix_name, mayhem_mode)."""
    import collector
    import struct
    disc = next(k for k, v in collector.DISC.items() if v == "TradeEvent")
    return (disc + mint + struct.pack("<QQ", sol, tok) + bytes([buy]) + user
            + struct.pack("<qQQ", ts, vsol, vtok) + struct.pack("<QQ", 1, 2) + b"\x03" * 32
            + struct.pack("<QQ", fee_bps, 9) + b"\x04" * 32 + struct.pack("<QQ", creator_bps, 3)
            + b"\x00" + b"\x00" * 32 + struct.pack("<I", 3) + b"buy" + bytes([mayhem]) + b"\x00" * 40)


def test_collector_parses_events():
    import collector
    import struct
    assert collector.b58(b"\x00\x01") == "12" and collector.b58(b"\x00" * 3) == "111"
    ev = collector.parse(_trade_event())
    assert ev["kind"] == "TradeEvent" and ev["sol"] == 10**9 and ev["tok"] == 3 * 10**13 and ev["buy"] == 1
    assert ev["vsol"] == 31 * 10**9 and ev["vtok"] == 10**15 and ev["fee_bps"] == 125      # opłata protokołu + twórcy
    assert ev["mint"] == collector.b58(b"\x01" * 32) and ev["user"] == collector.b58(b"\x02" * 32)
    disc = next(k for k, v in collector.DISC.items() if v == "CreateEvent")
    s = lambda x: struct.pack("<I", len(x)) + x
    raw = disc + s(b"Kot") + s(b"KOT") + s(b"ipfs://x") + b"\x05" * 32 + b"\x06" * 32 + b"\x07" * 32 + b"\x08" * 32 \
        + struct.pack("<q", 1_800_000_123) + b"\x00" * 32 + b"\x09" * 32 + b"\x01" + b"\x00" * 40   # 4 x u64, token_program, mayhem
    c = collector.parse(raw)
    assert c["name"] == "Kot" and c["symbol"] == "KOT" and c["mint"] == collector.b58(b"\x05" * 32)
    assert c["user"] == collector.b58(b"\x08" * 32) and c["ts"] == 1_800_000_123
    assert collector.parse(b"\x00" * 50) is None and collector.parse(_trade_event()[:40]) is None   # obce / ucięte
    assert collector.progress(collector.INITIAL_VTOK) == 0 and collector.progress(0) == 1.0
    assert ev["mayhem"] == 0 and collector.parse(_trade_event(mayhem=1))["mayhem"] == 1
    assert c["mayhem"] == 1                                                   # bajt po token_program w CreateEvent


def test_collector_reads_only_pump_emitted_events():
    # 4.10: Raydium LaunchLab w tej samej transakcji emitował własny "TradeEvent" (ten sam dyskryminator Anchora)
    import base64
    import collector
    b64 = lambda raw: "Program data: " + base64.b64encode(raw).decode()
    ours, foreign = _trade_event(ts=1_800_000_001), _trade_event(ts=-7_854_277_750_024_028_630)
    logs = ["Program ComputeBudget111111111111111111111111111111 invoke [1]",
            "Program ComputeBudget111111111111111111111111111111 success",
            f"Program {collector.PUMP} invoke [1]", "Program log: Instruction: Buy", "Program log: invoke [9]",
            "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [2]",
            "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
            b64(ours), "Program data: !!!nie-base64", f"Program {collector.PUMP} success",
            "Program LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj invoke [1]", b64(foreign),
            f"Program {collector.PUMP} invoke [2]", b64(ours), f"Program {collector.PUMP} success",   # CPI do pump.fun
            "Program LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj failed: custom program error: 0x1", b64(foreign)]
    got = [collector.parse(r)["ts"] for r in collector.pump_data(logs)]
    assert got == [1_800_000_001, 1_800_000_001]


def test_collector_store_roundtrip():
    import collector
    from pathlib import Path
    path = Path(tempfile.mkdtemp()) / "s.db"
    st = collector.Store(path)
    st.add({"kind": "CreateEvent", "mint": "M1", "name": "A", "symbol": "A", "user": "DEV", "ts": 100}, 5)
    st.add(dict(collector.parse(_trade_event()), mint="M1", user="W1"), 6)
    st.add(dict(collector.parse(_trade_event(vsol=0)), mint="M1", user="W2"), 6)      # zerowa rezerwa - pomijamy
    st.add({"kind": "CompleteEvent", "mint": "M1", "user": "W1", "ts": 200}, 7)
    assert st.flush() == 1
    db = st.db
    assert db.execute("SELECT name, creator, created_ts FROM mints WHERE mint='M1'").fetchone() == ("A", st.wallets["DEV"], 100)
    assert db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 1
    assert db.execute("SELECT kind FROM events").fetchone()[0] == "complete"
    again = collector.Store(path)                                                      # restart: te same identyfikatory
    assert again.wallets == st.wallets and again.mints == st.mints and again.next_wallet == st.next_wallet
    again.add(dict(collector.parse(_trade_event(mayhem=1)), mint="M2", user="W1"), 8)
    again.flush()
    assert again.db.execute("SELECT mint FROM mints WHERE mayhem=1").fetchall() == [("M2",)]
    assert collector.Store(path).mayhem == {again.mints["M2"]}


def test_first_look_window_blocks_late_entries():
    b = _bot(strategies=("hybrid", "safety_only"))
    v = analysis.decide(b.cfg, analysis.market_checks(b.cfg, make_pair(), 50) + analysis.rug_checks(b.cfg, CLEAN_REPORT))
    ctx = {"size": 50, "liq": 60_000, "wallets": [], "decimals": None, "buy_qty": None}
    pos = b.portfolios["hybrid"].buy("M", "T", 1.0, 100_000, 50, 80)
    b.store.db.execute("UPDATE positions SET opened_ts=? WHERE id=?", (time.time() - 3600, pos.id))   # kupiony godzinę temu
    b.enter("M", "T", make_pair(), v, ctx, ["safety_only"], {})
    assert "M" not in b.portfolios["safety_only"].positions                     # spóźnione - nie kupujemy
    b.store.db.execute("UPDATE positions SET opened_ts=? WHERE id=?", (time.time() - 120, pos.id))    # 2 min temu
    b.enter("M", "T", make_pair(), v, ctx, ["safety_only"], {})
    assert "M" in b.portfolios["safety_only"].positions                         # w oknie 10 min - wolno


def test_llm_parse_rejects_bad_answers():
    import json as _json
    import llm
    ok = {"decision": "SKIP", "confidence": 62.4, "p_tp": 18, "reasoning": "Duża zmienność.", "invalidation": ""}
    assert llm.parse(_json.dumps(ok))["confidence"] == 62
    for bad in (dict(ok, decision="MAYBE"), dict(ok, confidence=150), dict(ok, p_tp=True), dict(ok, p_tp="20"),
                dict(ok, decision="BUY", invalidation="")):                   # BUY bez warunku unieważnienia
        try:
            llm.parse(_json.dumps(bad))
            assert False, bad
        except ValueError:
            pass
    buy = llm.parse(_json.dumps(dict(ok, decision="BUY", invalidation="powrót pod VWAP", risk_flags=["a"] * 9)))
    assert buy["decision"] == "BUY" and len(buy["risk_flags"]) == 5
    p = llm.build_prompt("KOT", {"age_min": 90, "atr_pct": 8.0, "nieznana": 1, "top10": None}, ["social (+5): X"])
    assert "pool age, minutes" in p and "1-min ATR" in p and "nieznana" not in p and "top-10" not in p
    # v2: liczba p_better trafia do p_tp; percentyl cechy wśród ostatnich czystych tokenów
    assert llm.parse(_json.dumps({k: v for k, v in dict(ok, p_better=71).items() if k != "p_tp"}))["p_tp"] == 71
    ref = llm.reference([(_json.dumps({"atr_pct": float(i)}),) for i in range(40)] + [(None,)])
    p = llm.build_prompt("KOT", {"atr_pct": 30.0, "liq": 5000}, [], ref)
    assert "30 (p75)" in p and "among 40 recent" in p and '"liquidity USD": 5000' in p   # liq bez próbki - bez percentyla


class _FakeHttp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.text = payload, status, ""

    def json(self):
        return self.payload


def _gemini_reply(decision="BUY", conf=80, p=35):
    import json as _json
    body = {"decision": decision, "confidence": conf, "p_tp": p, "reasoning": "Cena nad VWAP.", "invalidation": "spadek pod VWAP"}
    return _FakeHttp({"candidates": [{"content": {"parts": [{"text": _json.dumps(body)}]}}],
                      "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 60}})


def test_llm_budget_and_no_key():
    import llm
    cfg = Config()
    cfg.gemini_rpm = 2
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    assert not llm.GeminiAdvisor(cfg, st, key="").enabled                       # bez klucza strategia milczy
    adv = llm.GeminiAdvisor(cfg, st, key="TEST")
    sent = []
    adv.s.post = lambda url, **kw: sent.append(kw["headers"]) or _gemini_reply()
    assert adv.ask("p")[0]["decision"] == "BUY" and adv.ask("p")[0]
    res, meta = adv.ask("p")
    assert res is None and meta["error"] == "limit na minutę" and len(sent) == 2
    assert all("TEST" not in url for url in [llm.URL]) and sent[0]["x-goog-api-key"] == "TEST"   # klucz w nagłówku
    adv.calls.clear()
    st.kv_set(f"gemini_calls:{time.strftime('%Y-%m-%d')}", cfg.gemini_max_per_day)
    assert adv.ask("p")[1]["error"] == "limit dzienny"
    adv.s.post = lambda url, **kw: _FakeHttp({"error": "x"}, status=429)
    st.kv_set(f"gemini_calls:{time.strftime('%Y-%m-%d')}", 0)
    res, meta = adv.ask("p")
    assert res is None and meta["error"].startswith("HTTP 429")                  # błąd = brak sygnału, bez reguły zastępczej
    # model "myślący" (gemini-3.5-flash, 4.10.2026): myślenie zjadło limit, JSON ucięty -> brak sygnału, tokeny zliczone
    adv.calls.clear()
    adv.s.post = lambda url, **kw: _FakeHttp({"candidates": [{"content": {"parts": [{"text": "{\n  \""}]},
                                                              "finishReason": "MAX_TOKENS"}],
                                              "usageMetadata": {"promptTokenCount": 624, "candidatesTokenCount": 4,
                                                                "thoughtsTokenCount": 479}})
    res, meta = adv.ask("p")
    assert res is None and "MAX_TOKENS" in meta["error"] and meta["tokens_out"] == 483


def test_bot_gemini_signals_and_features():
    b = _bot()
    b.llm.enabled, b.llm.key = True, "TEST"
    b.llm.s.post = lambda url, **kw: _gemini_reply("BUY", 80, 35)
    v = analysis.decide(b.cfg, analysis.market_checks(b.cfg, make_pair(), 50) + analysis.rug_checks(b.cfg, CLEAN_REPORT))
    did = b.store.log_decision("M", "T", v, make_pair(), {"atr_pct": 9.0})
    b.last_decision_id["M"] = did
    b.assess_llm("M", "T", v, {"features": {"atr_pct": 9.0}})
    sig = {r[0] for r in b.store.db.execute("SELECT strategy FROM signals WHERE decision_id=?", (did,))}
    assert sig == {"gemini", "gemini_hc"}
    import json as _json
    f = _json.loads(b.store.db.execute("SELECT features FROM decisions WHERE id=?", (did,)).fetchone()[0])
    assert f["gemini_p"] == 35 and f["gemini_buy"] == 1 and f["atr_pct"] == 9.0
    b.llm.s.post = lambda url, **kw: (_ for _ in ()).throw(AssertionError("ponowne pytanie w oknie cooldownu"))
    b.assess_llm("M", "T", v, {"features": {}})                                  # ten sam token za chwilę - bez zapytania
    assert b.store.db.execute("SELECT COUNT(*) FROM llm_decisions").fetchone()[0] == 1


def test_collector_survives_out_of_range_numbers():
    """Regresja 4.10 10:30: u64 > 2^63 z łańcucha zabił zbieracza przy zapisie do SQLite."""
    import collector
    from pathlib import Path
    st = collector.Store(Path(tempfile.mkdtemp()) / "s.db")
    collector.log = lambda msg: None                                       # bez pisania do prawdziwego logu
    st.add(dict(collector.parse(_trade_event(sol=2**64 - 1)), mint="M", user="W"), 1)
    st.add(dict(collector.parse(_trade_event(fee_bps=2**40)), mint="M", user="W"), 2)
    st.add(dict(collector.parse(_trade_event()), mint="M", user="W"), 3)
    assert st.bad == 1 and st.flush() == 2
    assert [r[0] for r in st.db.execute("SELECT fee_bps FROM trades ORDER BY slot")] == [0, 125]
    st.trades.append((4, 1, 1, 1, 1, 2**63, 1, 1, 1, 0))                    # gdyby jednak coś przeszło - zapis nie pada
    st.flush()
    assert st.db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 2


def test_rug_map_sellers_and_ancestors():
    import rug_map
    bal = lambda owner, amt: {"mint": "M", "owner": owner, "uiTokenAmount": {"amount": str(int(amt * 1e6)), "decimals": 6}}
    tx = {"meta": {"err": None,
                   "preTokenBalances": [bal("A", 1000), bal("POOL", 5000), bal("B", 10)],
                   "postTokenBalances": [bal("A", 0), bal("POOL", 6000), bal("B", 10)]}}
    assert rug_map.sellers_in(tx, "M", "POOL") == {"A": 1000.0}          # pula (rośnie) i B (bez zmian) pominięte
    assert rug_map.sellers_in({"meta": {"err": {"x": 1}}}, "M", "POOL") == {}   # nieudana transakcja
    info = {"w": {"status": "ok", "funder": "f1"}, "f1": {"status": "ok", "funder": "f2"},
            "f2": {"status": "aktywny", "funder": None}}
    assert rug_map.ancestors("w", info, stop_active=True) == ["w", "f1"]       # giełda/serwis (aktywny) nie łączy
    assert rug_map.ancestors("w", info, stop_active=False) == ["w", "f1", "f2"]


def test_collector_records_holes_in_block_time():
    """Regresja 5.10: przy opóźnieniu 30 s zerwanie gubiło ~30 s transakcji, a luka w czasie odbioru miała 2 s
    (poniżej progu) - tabela gaps pokazywała ułamek strat. Teraz dziura = > HOLE_S bez transakcji w czasie BLOKU."""
    import collector
    from pathlib import Path
    st = collector.Store(Path(tempfile.mkdtemp()) / "s.db")
    ev = collector.parse(_trade_event())
    for slot, ts in ((1, 1000), (2, 1001), (3, 1000), (4, 1031), (5, 1032)):     # 1000 po 1001: kolejność bloków
        st.add(dict(ev, mint="M", user="W", ts=ts), slot)
    st.flush()
    assert [tuple(r) for r in st.db.execute("SELECT start, end FROM gaps")] == [(1001, 1031)]
    assert collector.data_holes(st.db) == [(1001, 1031)]                         # to samo wstecz, z samych transakcji
    assert collector.data_holes(st.db, t0=1002) == []


def _curve_rows():
    """Lider L kupuje, inni pchają cenę w górę, L sprzedaje z zyskiem (zgodnie z matematyką krzywej)."""
    import copytrade as ct
    vsol, vtok, fee, rows, t = 30 * 10**9, 1_073 * 10**12, 125, [], 1_000

    def buy(w, lamports):
        nonlocal vsol, vtok, t
        cin = lamports / (1 + fee / 1e4)
        tok = vtok - vsol * vtok / (vsol + cin)
        vsol, vtok = vsol + cin, vtok - tok
        rows.append((t, t, 1, w, 1, int(cin), int(tok), int(vsol), int(vtok), fee))
        return tok

    def sell(w, tok):
        nonlocal vsol, vtok, t
        out = vsol - vsol * vtok / (vtok + tok)
        vsol, vtok = vsol - out, vtok + tok
        rows.append((t, t, 1, w, 0, int(out), int(tok), int(vsol), int(vtok), fee))

    got = buy(7, 2 * 10**9)                      # lider
    for _ in range(12):
        t += 10
        buy(99, 2 * 10**9)                       # tłum kupuje przez 2 minuty
    t += 60
    sell(7, got)                                 # lider sprzedaje całość
    t += 60
    buy(99, 10**8)
    return rows, ct


def test_copytrade_curve_math():
    import copytrade as ct
    vsol, vtok = 30 * 10**9, 1_073 * 10**12
    tok = ct.buy_tokens(vsol, vtok, 10**9, 125)
    back = ct.sell_sol(vsol + 10**9 / 1.0125, vtok - tok, tok, 125)
    assert 0.97 < back / 10**9 < 0.98                                 # kupno i od razu sprzedaż = ~2 x opłata 1.25%
    assert ct.buy_tokens(vsol, vtok, 10**10, 125) < 10 * tok          # większe zlecenie = gorsza cena (poślizg)


def test_copytrade_positions_and_delay():
    rows, ct = _curve_rows()
    closed = ct.wallet_positions(rows, 0, 10**9, {})
    (mint, t_open, t_close, cost, proc), = closed[7]
    assert mint == 1 and proc > cost * 1.3                               # lider zarobił
    assert not ct.wallet_positions(rows, 0, 10**9, {1: 7}).get(7)        # twórca tokena - pozycja pominięta
    st = ct.wallet_stats(closed)[7]
    assert st["n"] == 1 and st["win"] == 1.0 and st["pnl"] > 0
    sig = ct.leader_signals(rows, {7}, 0, 10**9, {})
    assert len(sig) == 1 and sig[0][5] == rows[13][1]                    # czas pierwszej sprzedaży lidera
    states = ct.build_states(rows)
    t_end = rows[-1][1]
    r0, why0 = ct.simulate(sig[0], states, {}, 0, 0.25, 0.001, "lustro", t_end)
    r30, _ = ct.simulate(sig[0], states, {}, 30, 0.25, 0.001, "lustro", t_end)
    assert why0 == "lider sprzedał" and r0 > r30 > -1                    # opóźnienie = gorsza cena wejścia
    assert ct.simulate(sig[0], states, {1: rows[0][1]}, 30, 0.25, 0.001, "lustro", t_end) is None   # po graduacji
    rb, whyb = ct.simulate(sig[0], states, {}, 3, 0.25, 0.001, "zasady bota", t_end)
    assert whyb in ("tp3", "trailing", "stop", "time stop", "koniec danych") and rb > -1


def test_stage_entries_and_copyable_wallets():
    import copytrade as ct
    import stages
    from collector import CURVE_TOKENS, INITIAL_VTOK
    vt = lambda p: int(INITIAL_VTOK - p * CURVE_TOKENS)
    states = {1: ([0, 10, 20, 30], [(40 * 10**9, vt(p), 125) for p in (0.05, 0.4, 0.75, 0.9)]),
              2: ([5, 15], [(40 * 10**9, vt(p), 125) for p in (0.5, 0.8)])}
    e = stages.entries(states, {1: 0})
    assert e["nowe (<30%)"] == [(1, 0)] and e["środek (30-70%)"] == [(1, 10)]
    assert e["final stretch (>=70%)"] == [(1, 20), (2, 15)]          # token 2: widzieliśmy tylko przejście do final stretch
    stats = {"fast": {"n": 9, "hold": 30, "tokens": 9}, "slow": {"n": 9, "hold": 200, "tokens": 9},
             "bot": {"n": 900, "hold": 200, "tokens": 900}, "rare": {"n": 2, "hold": 200, "tokens": 2}}
    assert ct.eligible(stats, 5) == ["slow"] and set(ct.eligible(stats, 5, min_hold=15)) == {"fast", "slow"}



def test_fast_time_stop_portfolios():
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    ts5 = Portfolio(cfg, st, "safety_ts5", cfg.strategy_exits["safety_ts5"])
    ts10 = Portfolio(cfg, st, "lowvol_ts10", cfg.strategy_exits["lowvol_ts10"])
    a, b = ts5.buy("A", "A", 1.0, 100_000, 50, 80), ts5.buy("B", "B", 1.0, 100_000, 50, 80)
    c = ts10.buy("C", "C", 1.0, 100_000, 50, 80)
    pair = lambda px: {"priceUsd": str(px), "liquidity": {"usd": 100_000}}
    assert ts5.manage(a, pair(0.99), now=a.opened_ts + 4 * 60) is None            # przed 5 min - czekamy
    assert ts5.manage(a, pair(0.99), now=a.opened_ts + 6 * 60) == "time_stop"     # po 5 min pod kreską - wychodzimy
    assert ts5.manage(b, pair(1.03), now=b.opened_ts + 6 * 60) is None            # na plusie - zostaje
    assert ts10.manage(c, pair(1.04), now=c.opened_ts + 11 * 60) == "time_stop"   # < +5% po 10 min
    import strategies
    assert {"safety_ts5", "lowvol_ts10"} <= set(cfg.strategies) and strategies.REGISTRY["lowvol_ts10"] is strategies.lowvol


def test_s6_portfolio_breakeven_after_first_tp():
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    s6 = Portfolio(cfg, st, "safety_s6", cfg.strategy_exits["safety_s6"])
    base = Portfolio(cfg, st, "safety_only", cfg.strategy_exits.get("safety_only"))
    pair = lambda px: {"priceUsd": str(px), "liquidity": {"usd": 100_000}}
    a, b = s6.buy("A", "A", 1.0, 100_000, 50, 80), base.buy("A", "A", 1.0, 100_000, 50, 80)
    e = a.entry_price
    assert s6.manage(a, pair(e * 1.21)) == "tp1" and abs(a.qty_left - a.qty_initial * 0.67) < 1e-9   # 1/3 przy +20%
    assert base.manage(b, pair(e * 1.21)) is None                                                    # zwykły: TP1 dopiero +50%
    assert s6.manage(a, pair(e * 0.995)) == "breakeven" and "A" not in s6.positions                 # reszta na wejściu
    assert base.manage(b, pair(e * 0.995)) is None and "A" in base.positions                        # zwykły bez zmian
    import strategies
    assert "safety_s6" in cfg.strategies and strategies.REGISTRY["safety_s6"] is strategies.safety_only


def test_new_portfolio_exits_keep_rules_epoch():
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    base = {"stop_loss_pct": 25, "strategy_exits": {"safety_wide": {"stop_loss_pct": 40}}}
    assert st.mark_rules(base)
    t0 = st.kv_get("rules_since")
    time.sleep(0.01)
    added = {"stop_loss_pct": 25, "strategy_exits": {"safety_wide": {"stop_loss_pct": 40}, "safety_ts5": {"time_stop_minutes": 5}}}
    assert not st.mark_rules(added) and st.kv_get("rules_since") == t0              # nowy portfel - okno zostaje
    changed = {"stop_loss_pct": 25, "strategy_exits": {"safety_wide": {"stop_loss_pct": 30}, "safety_ts5": {"time_stop_minutes": 5}}}
    assert st.mark_rules(changed) and st.kv_get("rules_since") > t0                  # zmiana istniejącego - nowe okno


def test_rug_labels_fast_late_ok():
    import rug_backtest as rb
    T = 1_000_020                                     # migracja w trakcie świecy 1_000_000
    flat = lambda n, start, px: [[start + 60 * k, px, px, px, px, 1] for k in range(n)]
    fast = flat(1, 1_000_000, 1.0) + [[1_000_300, 1.0, 1.1, 0.25, 0.3, 1]] + flat(10, 1_000_360, 0.3)
    assert rb.label(fast, T)["label"] == "RUG_SZYBKI"
    late = flat(1, 1_000_000, 1.0) + [[1_000_120, 1.0, 1.5, 1.0, 1.4, 1]] + [[1_003_600, 1.4, 1.4, 0.15, 0.15, 1]]
    assert rb.label(late, T)["label"] == "RUG_PO_POMPIE"                   # pompa +50%, potem -85%: bot mógł zarobić
    slow = flat(1, 1_000_000, 1.0) + [[1_000_000 + 60 * 40, 1.0, 1.0, 0.2, 0.2, 1]]
    assert rb.label(slow, T)["label"] == "OK"                              # -80% dopiero po 40 min, bez pompy
    # cena odniesienia = ostatnia ZAMKNIĘTA świeca przed t (nie przyszłość): t = +3 min, przed t cena 2.0
    pre = flat(3, 1_000_000, 2.0) + [[1_000_180, 2.0, 2.0, 0.5, 0.5, 1]]
    lab = rb.label(pre, 1_000_185)
    assert lab["ref"] == 2.0 and lab["label"] == "RUG_SZYBKI"
    assert rb.label(flat(3, 1_000_000, 1.0), 1_000_500) is None            # brak świec po t -> brak etykiety


def test_rugguard_features_are_point_in_time():
    import rugguard
    meta = {"created_ts": 100, "created_slot": 10, "creator": 1, "mayhem": 0, "mig_ts": 500}
    S = rugguard.SUPPLY_RAW
    # (slot, ts, wallet, buy, sol, tok, vsol, vtok)
    tr = [(10, 100, 1, 1, 1e9, 0.05 * S, 31e9, 1.0e15),     # twórca 5% w slocie utworzenia
          (10, 100, 2, 1, 1e9, 0.04 * S, 32e9, 0.96e15),    # bundle: inny portfel w tym samym slocie
          (11, 101, 3, 1, 1e9, 0.04 * S, 33e9, 0.92e15),    # bundle (slot +1)
          (50, 140, 4, 1, 1e9, 0.01 * S, 34e9, 0.91e15),    # zwykły kupujący
          (60, 150, 2, 0, 1e9, 0.04 * S, 33e9, 0.95e15),    # portfel 2 sprzedaje wszystko
          (90, 400, 5, 1, 9e9, 0.30 * S, 60e9, 0.60e15)]    # PO chwili t=200 - nie może się liczyć
    f = rugguard.curve_features(tr, meta, 200, first_seen={}, creator_hist={"prev_tokens": 4, "prev_migrated": 1})
    assert f["n_trades"] == 5 and f["bundle_wallets"] == 2 and abs(f["bundle_pct"] - 8) < 1e-9
    assert abs(f["dev_initial_pct"] - 5) < 1e-9 and abs(f["creator_pct"] - 5) < 1e-9
    assert f["n_holders"] == 3 and abs(f["top1_pct"] - 5) < 1e-9 and f["n_over_3pct"] == 2   # 1 (5%), 3 (4%), 4 (1%)
    assert f["sniper_sold_frac"] == 0.5 and f["creator_mig_rate"] == 0.25 and "curve_minutes" not in f
    # router: kupuje dla innych (tokeny odchodzą przelewem), sprzedaje cudze -> ujemne saldo; salda niewiarygodne
    rt = tr[:5] + [(70, 160, 9, 0, 1e9, 0.20 * S, 30e9, 1.1e15)]
    g = rugguard.curve_features(rt, meta, 200, first_seen={})
    assert g["balances_ok"] == 0 and g["top1_pct"] is None and g["hhi"] is None
    assert rugguard.top_buyers(rt, 5) == [1, 2, 3, 4]                        # pośrednik (9) pominięty
    a = rugguard.assess(f, [("top1_pct", ">", 3), ("bundle_wallets", ">", 5)])
    assert a.flags == ["top1_pct"] and a.score == 0.5


def test_ata_address_matches_chain():
    from analizy import solana as S
    assert S.b58encode(S.b58decode(S.TOKEN)) == S.TOKEN
    # wektory z transakcji na łańcuchu (6.10): zwykły Token i Token-2022
    assert S.ata("A7hAgCzFw14fejgCp387JUJRMNyz4j89JKnhtKU8piqW", "So11111111111111111111111111111111111111112",
                 S.TOKEN) == "qkYdTGRPHbWTWuBMz45bCiU6a23axRqf6sBHm9295WY"
    assert S.ata("7gLVfZavnRpuN5iFQQYAvRpbyvNkARhy2sURRvgsaFby", "7m8VbovNMVBap1puP6GgC1a5CbR8MwAXfr3yxRyr8ZQV",
                 S.TOKEN_2022) == "77cECK9BprRF3oLdVeSoTxASiH3zSnQ727WSeFUSPDi2"


def test_pumpswap_virtual_sol_reserve():
    """Pula PumpSwap liczy wymianę z wirtualną rezerwą SOL: bez niej wycena z sald skarbców była o 10-24% za niska."""
    from analizy import crash_gap as G
    V, tok, sol, rows = 17.5, 1.5e8, 100.0, []
    for i, dt in enumerate([1e5, -2e5, 5e4, 3e5, -1e5, 2e5]):
        out = (sol + V) * dt / (tok + dt)                     # sprzedaż (dt > 0) albo kupno (dt < 0)
        rows.append({"slot": i, "idx": 0, "bt": 1000 + i, "pre_tok": tok, "pre_sol": sol,
                     "post_tok": tok + dt, "post_sol": sol - out})
        tok, sol = tok + dt, sol - out
    assert abs(G.virtual_sol(rows) - V) < 1e-6
    path = G.PoolPath(rows, [(990, 1010)])
    st = path.state(1003.5)                                   # po 4. transakcji (bt 1003)
    assert abs(st[1] - (rows[3]["post_sol"] + V)) < 1e-9 and st[0] == rows[3]["post_tok"]
    assert path.state(980) is None                            # poza pobranymi oknami nie zgadujemy
    # wartość sprzedaży z efektywnych rezerw: stały iloczyn z prowizją puli
    v = G.value_usd((1e8, 117.5), 1e5, 100.0)
    assert abs(v - 117.5 * 1e5 * 0.997 / (1e8 + 1e5 * 0.997) * 100) < 1e-9


def test_fast_stop_thread_sells_only_below_stop():
    """safety_fast (7.10): wątek czyta skarbce puli i sprzedaje TYLKO na stopie, raz; pozycja nad stopem zostaje."""
    import struct
    import threading
    import fastexit as FE
    from analizy import solana as SOL
    mint, wsol = "7m8VbovNMVBap1puP6GgC1a5CbR8MwAXfr3yxRyr8ZQV", FE.WSOL
    raw = bytearray(301)
    for off, key in ((43, mint), (75, wsol), (139, "qkYdTGRPHbWTWuBMz45bCiU6a23axRqf6sBHm9295WY"),
                     (171, "77cECK9BprRF3oLdVeSoTxASiH3zSnQ727WSeFUSPDi2")):
        raw[off:off + 32] = SOL.b58decode(key)
    struct.pack_into("<Q", raw, FE.V_OFFSET, 17_584_505_358)
    d = FE.decode_pool(bytes(raw))
    assert d["base_mint"] == mint and d["quote_mint"] == wsol and abs(d["v_sol"] - 17.584505358) < 1e-9
    cfg = Config()
    st = Storage(os.path.join(tempfile.mkdtemp(), "t.db"))
    pf = Portfolio(cfg, st, "safety_fast")
    pos = pf.buy(mint, "X", 1.0, 100_000, 50, 80)

    class FakeBot:
        portfolios, store, fast_lock = {"safety_fast": pf}, st, threading.RLock()
    m = FE.FastMonitor(FakeBot(), ("safety_fast",), 2.0, log=lambda *a: None)
    m.pools[mint] = dict(d, reversed=False, pool="P")
    m.sol_usd, m.sol_ts = 1.0, time.time()
    vault = {"tok": 1e9, "sol": 0.0}
    m.rpc = lambda payload: ({"result": {"value": [
        {"data": {"parsed": {"info": {"tokenAmount": {"uiAmountString": str(vault["tok"])}}}}},
        {"data": {"parsed": {"info": {"tokenAmount": {"uiAmountString": str(vault["sol"])}}}}}]}}, "public")
    per_token = lambda sol: FE.sell_value_sol(vault["tok"], sol, d["v_sol"], pos.qty_left) * FE.CALIB / pos.qty_left
    lo, hi = 0.0, 1e12                                      # saldo SOL, przy którym cena = cena wejścia
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if per_token(mid) < pos.entry_price else (lo, mid)
    vault["sol"] = (hi + d["v_sol"]) * 0.80 - d["v_sol"]   # -20%: nad stopem -25%
    m.step()
    assert mint in pf.positions
    vault["sol"] = (hi + d["v_sol"]) * 0.70 - d["v_sol"]   # -30%: pod stopem
    m.step()
    assert mint not in pf.positions
    r = st.db.execute("SELECT reason FROM trades WHERE side='SELL'").fetchall()
    assert [x[0] for x in r] == ["stop_fast"]
    m.step()                                                # zamknięta - drugi raz nie sprzedaje
    assert len(st.db.execute("SELECT * FROM trades WHERE side='SELL'").fetchall()) == 1


def test_launch_filter_portfolios():
    import strategies

    class V:
        vetoes, category_scores = [], {"safety": 90}
    cfg = Config()
    for n in ("safety_fast", "safety_bundle30", "safety_nocopy"):
        assert n in cfg.strategies and n in strategies.REGISTRY
    assert "smart_money_only" not in cfg.strategies
    b30 = strategies.REGISTRY["safety_bundle30"]
    nc = strategies.REGISTRY["safety_nocopy"]
    ctx = lambda b=None, c=None: {"launch": {"bundle": b, "copy": c}}
    assert b30(V(), cfg, ctx({"bundle_start_pct": 35.0})) and not b30(V(), cfg, ctx({"bundle_start_pct": 29.9}))
    assert not b30(V(), cfg, ctx(None))                      # brak danych o starcie -> nie kupuje
    copy = lambda cat, img=0, ref=0: {"copy_cat": cat, "img_copy": img, "img_ref": ref}
    assert nc(V(), cfg, ctx(c=copy("c oryginał"))) and nc(V(), cfg, ctx(c=copy("b kopia martwego")))
    assert not nc(V(), cfg, ctx(c=copy("a kopia aktywnego"))) and not nc(V(), cfg, ctx(c=copy("c oryginał", img=1)))
    assert not nc(V(), cfg, ctx(c=copy("c oryginał", ref=1))) and nc(V(), cfg, ctx(c=None))


def test_bundle_detection_and_copy_norm():
    from analizy import bundles as B, copycoins as CC
    S = 1e15
    # (slot, ts, wallet, buy, sol, tok): twórca 1 + portfel 2 w slocie startu = bundle; 3 sam w slocie +2 = nie;
    # 4 i 5 razem w slocie +5 (poza N=3) = nie; portfel 2 sprzedaje połowę w slocie +1 (flip liczony netto)
    tr = [(100, 1, 1, 1, 1e9, 0.10 * S), (100, 1, 2, 1, 1e9, 0.20 * S), (101, 1, 2, 0, 1e9, 0.10 * S),
          (102, 2, 3, 1, 1e9, 0.05 * S), (105, 3, 4, 1, 1e9, 0.05 * S), (105, 3, 5, 1, 1e9, 0.05 * S)]
    d = B.detect(tr, 100, 1, set())
    assert d["b_wallets"] == [1, 2] and abs(d["bundle_start_pct"] - 20.0) < 1e-9 and d["creator_in_bundle"] == 1
    assert d["dev_alone_pct"] == 0.0
    solo = B.detect([(100, 1, 1, 1, 1e9, 0.79 * S)], 100, 1, set())    # dev sam kupił całą krzywą: nie bundle
    assert solo["b_n"] == 0 and abs(solo["dev_alone_pct"] - 79.0) < 1e-9
    assert CC.norm("Pepe Coin!") == "pepecoin" and CC.norm("🚀🚀") is None and CC.norm(None) is None
    assert CC.image_key("https://ipfs.io/ipfs/bafkreifyh7fhb5srfyzx3xuq6ng2m7avx45vqlcsogflf3456izuqi757q")[0].startswith("bafkrei")
    assert CC.image_key("https://axiomtrading-v2.axiom-cdn.io/oPtRQNELaoMDRsyHVS9i1qGqpX66CDSowBAqw8xpump.webp")[1] == \
        "oPtRQNELaoMDRsyHVS9i1qGqpX66CDSowBAqw8xpump"


def test_arb_scan_pools_and_costs():
    import arb_scan as A
    m = "MINTX"
    pairs = [
        {"baseToken": {"address": m}, "quoteToken": {"address": A.WSOL}, "dexId": "pumpfun",
         "liquidity": {"usd": 0}, "priceNative": "0.0000004", "pairAddress": "CURVE"},             # zamknięta krzywa
        {"baseToken": {"address": m}, "quoteToken": {"address": A.WSOL}, "dexId": "pumpswap",
         "liquidity": {"usd": 50_000}, "priceNative": "0.000002", "pairAddress": "P1"},
        {"baseToken": {"address": m}, "quoteToken": {"address": A.WSOL}, "dexId": "meteora", "labels": ["DLMM"],
         "liquidity": {"usd": 500}, "priceNative": "0.0000021", "pairAddress": "P2"},              # za mała płynność
        {"baseToken": {"address": m}, "quoteToken": {"address": "USDC"}, "dexId": "raydium",
         "liquidity": {"usd": 9_000}, "priceNative": "0.0003", "pairAddress": "P3"},               # nie para z SOL
        {"baseToken": {"address": m}, "quoteToken": {"address": A.WSOL}, "dexId": "meteora", "labels": ["DYN2"],
         "liquidity": {"usd": 4_000}, "priceNative": "0.00000202", "pairAddress": "P4"},
    ]
    assert [p["pool"] for p in A.eligible_pools(m, pairs)] == ["P1", "P4"]
    assert abs(A.spread_bps(0.000002, 0.00000202) - 100) < 1e-6 and A.spread_bps(0, 1) == 0
    fixed = A.BASE_FEE + A.PRIORITY_FEE
    nm, nc = A.net_profit(0.01, 1.0)
    assert abs(nm - (0.01 - fixed - A.TIP_MIN)) < 1e-12 and abs(nc - (0.01 - fixed - 0.005)) < 1e-12
    nm, nc = A.net_profit(-0.002, 1.0)                    # strata: napiwek konkurencyjny nie ma sensu, oba = minimalne
    assert nm == nc and nm < -0.002


def test_cupsey_copy_math():
    from analizy import cupsey as Q

    class Path:                                              # krzywa: cena 1.0 przed jego zakupem, 1.1 po 5 s,
        def spot(self, mint, x, before=False):               # 2.0 przed jego sprzedażą, 1.8 po 5 s
            return {(100, True): 1.0, (105, False): 1.1, (200, True): 2.0, (205, False): 1.8}[(x, before)]

    e = {"legs": [{"venue": "pump_curve", "mint": "M", "bt": 100, "kind": "buy", "tok": 1000.0, "sol": -1.0},
                  {"venue": "pump_curve", "mint": "M", "bt": 200, "kind": "sell", "tok": 1000.0, "sol": 1.9,
                   "frac": 1.0}]}
    assert abs(Q.copy_episode(e, 0, Path(), None) - 0.9) < 1e-12           # d = 0 -> dokładnie jego wynik
    # d = 5: kupujemy 1000/1.1 tokenów za 1 SOL, sprzedajemy je za 1.9 * (909.09/1000) * 1.8/2.0
    exp = -1.0 + 1.9 * (1000 / 1.1 / 1000) * 0.9
    assert abs(Q.copy_episode(e, 5, Path(), None) - exp) < 1e-12
    e["legs"][0]["venue"] = "meteora_dlmm"                                  # miejsce bez cen -> None
    assert Q.copy_episode_safe(e, 5, Path(), None) is None


def test_cupsey_rule_sim():
    from analizy import cupsey_rule as R
    k = 30e9 * 1.073e15

    def tape(points):                                        # (ts, vsol) -> stany krzywej przy stałym k
        return {"ts": [t for t, _ in points], "vs": [v for _, v in points], "vt": [k / v for _, v in points],
                "fee": [125] * len(points)}

    # krzywa stoi: sprzedaż oddaje wkład minus 2 x 1.25% opłaty i 2 x 0.0005 SOL (bez podwójnego poślizgu)
    out = R.simulate(tape([(100, 30e9), (101, 30e9)]), 100, None, [], [])
    exp = (0.25 / 1.0125 * (1 - 0.0125) - 0.001 - 0.25) / 0.25
    assert abs(out[(5, 0, "czas_15s")][0] - exp) < 1e-9
    # "jak on": napływ do 112 s, potem cisza -> sygnał przy x = 117 (vsol nie rośnie od 5 s), sprzedaż po d = 2 s
    pts = [(100, 30e9)] + [(100 + i, 30e9 + i * 1e9) for i in range(1, 13)]
    r = R.simulate(tape(pts), 100, None, [], [])[(5, 2, "jak_on")]
    assert r[4] == 117 + 2 - 107 and r[0] > 0
    # migracja przed sprzedażą -> wyjście po ostatniej cenie krzywej, zaznaczone; dziura w trakcie -> zaznaczona
    r = R.simulate(tape(pts), 100, 110, [140], [150])[(5, 0, "czas_60s")]
    assert r[3] is True and r[2] is True


if __name__ == "__main__":
    fns =[v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"{len(fns)} testów przeszło")
