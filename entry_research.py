"""Badanie wejść: czy MOMENT wejścia ma znaczenie, niezależnie od zasad wyjścia.

    python bot.py entries                  # wszystkie tokeny po twardych filtrach
    python bot.py entries --min-age 60     # tylko tokeny, które przy pierwszej ocenie miały >= 60 min
    python bot.py entries --since "2026-10-03 10:00"

Co liczy (na archiwalnych świecach 1-min, które bot sam zbiera dla tokenów z sygnałem - Config.archive_*):
  1. Pierwsze spojrzenie: zwrot z samej ceny po 1/3/5/10/30/60 min od pierwszej czystej oceny tokena (po kosztach,
     bez stopów), także w podziale na wiek tokena. To jest "dryf" rynku, na którym działają wszystkie strategie.
  2. Strategie z decyzji (sygnały w tabeli signals): to samo plus wynik po obecnych zasadach wyjścia.
  3. Strażnik wejść "co minutę" (retro): reguły wejścia z analizy technicznej (wybicie, retest, kompresja, wolumen,
     sweep, powrót do średniej, wiele interwałów) sprawdzane w KAŻDEJ minucie przez SCAN_MIN min od pierwszego
     spojrzenia; wejście 60 s po pierwszym sygnale. Bot na żywo ocenia token zwykle raz (gdy pojawi się w nowościach
     DexScreenera), więc reguły minutowe prawie nigdy nie trafiają w moment oceny - tu widać, co dałyby, gdyby trafiały.
     Porównanie z wejściem przy pierwszym spojrzeniu NA TYCH SAMYCH tokenach.
  4. Czy cechy mierzą to samo (korelacja Spearmana) i czy strategie wskazują te same tokeny.

Progi reguł zamrożone 2.10.2026 przed pierwszym uruchomieniem (z opisu ChatGPT i istniejących strategii) - nie stroimy ich
na tych danych. Przy kilkudziesięciu tokenach różnice kilku-kilkunastu punktów procentowych to szum.
"""
from __future__ import annotations

import bisect
import json
import statistics
import time

import indicators
from exit_research import EC, XC, path_metrics, simulate, tp_plan
from storage import Storage

SCAN_MIN = 120            # ile minut po pierwszym spojrzeniu "strażnik" sprawdza reguły
HORIZON_MIN = 360         # okno wyniku po wejściu (archiwum sięga 6 h po decyzji)
LATENCY_S = 60            # wejście minutę po sygnale (jak w exit_research)
FWD = (1, 3, 5, 10, 30, 60)
AGE_BUCKETS = ((60, "<1 h"), (360, "1-6 h"), (1440, "6-24 h"), (float("inf"), ">24 h"))


# ------------------------------------------------------------------ reguły wejścia: (cechy TA, zamknięte świece) -> bool
def close_before(cs: list, t: float, ts: list | None = None) -> float | None:
    """Kurs zamknięcia ostatniej świecy ZAMKNIĘTEJ najpóźniej w chwili t (świeca minutowa zamyka się 60 s po starcie)."""
    ts = ts if ts is not None else [x[0] for x in cs]
    j = bisect.bisect_right(ts, t - 60) - 1
    return cs[j][4] if j >= 0 else None


def r_breakout_volume(f, w):      # istniejąca strategia breakout_volume
    return (f.get("donchian_break") == 1 and f.get("volume_ratio_1m", 0) >= 2 and f.get("price_vs_vwap", -1) > 0
            and f.get("trend_bull") == 1)


def r_breakout_simple(f, w):      # samo wybicie 20-min maksimum + wolumen 2x średniej
    return f.get("donchian_break") == 1 and f.get("volume_ratio_1m", 0) >= 2


def r_breakout_retest(f, w):      # istniejąca strategia breakout_retest
    return f.get("retest_ok") == 1 and f.get("trend_bull") == 1 and f.get("failed_breakout", 0) == 0


def r_bollinger(f, w):            # istniejąca strategia bollinger_breakout (ścieśnienie wstęg -> wybicie)
    return f.get("bb_squeeze_break") == 1 and f.get("volume_zscore", 0) >= 1.5


def r_compression(f, w):
    """Kompresja -> wybicie: zakres 20 świec w dolnych 25% historii okna, zamknięcie nad zakresem, wolumen >= 2x mediany."""
    w = w[-100:]
    if len(w) < 60:
        return False
    box, last = w[-21:-1], w[-1]
    hi, lo = max(x[2] for x in box), min(x[3] for x in box)
    if hi + lo <= 0:
        return False
    rng = (hi - lo) / ((hi + lo) / 2)
    hist = []
    for j in range(20, len(w)):
        b = w[j - 20:j]
        h_, l_ = max(x[2] for x in b), min(x[3] for x in b)
        if h_ + l_ > 0:
            hist.append((h_ - l_) / ((h_ + l_) / 2))
    pct = sum(x <= rng for x in hist) / len(hist) if hist else 1.0
    return pct <= 0.25 and last[4] > hi and last[5] >= 2 * statistics.median(x[5] for x in box)


def r_volume_expansion(f, w):     # wolumen świecy >= 3x średniej i cena +2% od poprzedniej świecy
    if len(w) < 2 or not w[-2][4]:
        return False
    return f.get("volume_ratio_1m", 0) >= 3 and w[-1][4] / w[-2][4] - 1 >= 0.02


def r_momentum_5m(f, w):          # +5..+30% w 5 min, wolumen 5 min >= 2x wcześniejszego tempa, cena nad VWAP
    if len(w) < 26:
        return False
    p5 = close_before(w, w[-1][0] + 60 - 300)
    base = sum(x[5] for x in w[-25:-5]) / 4
    if not p5 or base <= 0:
        return False
    ch5 = w[-1][4] / p5 - 1
    return 0.05 <= ch5 < 0.30 and sum(x[5] for x in w[-5:]) >= 2 * base and f.get("price_vs_vwap", -1) > 0


def r_sweep_reclaim(f, w):        # "liquidity sweep" (long): przebicie dołka z 30 świec o >= 1% i powrót nad niego
    if len(w) < 34 or w[-1][4] <= w[-1][1]:
        return False
    for k in range(1, 4):
        base = w[-k - 30:-k]
        if len(base) == 30:
            sup = min(x[3] for x in base)
            if w[-k][3] < sup * 0.99 and w[-1][4] > sup:
                return True
    return False


def r_mean_reversion(f, w):       # >= 2 ATR pod VWAP, RSI < 30, zielona świeca, słabnąca podaż (wolumen 3 świec maleje)
    a, pv, rs = f.get("atr_pct"), f.get("price_vs_vwap"), f.get("rsi14")
    if a is None or pv is None or rs is None or len(w) < 7:
        return False
    return (pv <= -2 * a / 100 and rs < 30 and w[-1][4] > w[-1][1]
            and sum(x[5] for x in w[-3:]) < sum(x[5] for x in w[-6:-3]))


def r_ema_trend_rsi(f, w):        # istniejąca strategia ema_trend_rsi
    return f.get("trend_bull") == 1 and 50 <= f.get("rsi14", -1) <= 70 and f.get("volume_ratio_1m", 0) >= 1.2


def r_vwap_momentum(f, w):        # istniejąca strategia vwap_momentum
    return f.get("price_vs_vwap", -1) > 0 and f.get("vwap_slope", -1) > 0 and f.get("volume_trend_5m", -1) > 0


def resample(w: list, sec: int) -> list:
    out: dict = {}
    for x in w:
        k = int(x[0] // sec)
        if k not in out:
            out[k] = [k * sec, x[1], x[2], x[3], x[4], x[5]]
        else:
            o = out[k]
            o[2], o[3], o[4], o[5] = max(o[2], x[2]), min(o[3], x[3]), x[4], o[5] + x[5]
    return [out[k] for k in sorted(out)]


def r_mtf(f, w):                  # wiele interwałów: 15 min trend w górę, 5 min wybicie, 1 min zielona nad VWAP
    c15, c5 = resample(w, 900), resample(w, 300)
    if len(c15) < 10 or len(c5) < 4:
        return False
    cl = [x[4] for x in c15]
    e_now, e_prev = indicators.ema(cl, 8), indicators.ema(cl[:-1], 8)
    return bool(e_now and e_prev and cl[-1] > e_now > e_prev and c5[-1][4] > max(x[2] for x in c5[-4:-1])
                and w[-1][4] > w[-1][1] and f.get("price_vs_vwap", -1) > 0)


RULES = {   # nazwa: (funkcja, skąd)
    "breakout_volume": (r_breakout_volume, "istniejąca"), "breakout_simple": (r_breakout_simple, "ChatGPT 2"),
    "breakout_retest": (r_breakout_retest, "istniejąca"), "bollinger_breakout": (r_bollinger, "istniejąca"),
    "compression_breakout": (r_compression, "ChatGPT 4"), "volume_expansion": (r_volume_expansion, "ChatGPT 5"),
    "momentum_5m": (r_momentum_5m, "ChatGPT 1"), "sweep_reclaim": (r_sweep_reclaim, "ChatGPT 9"),
    "mean_reversion": (r_mean_reversion, "ChatGPT 10"), "ema_trend_rsi": (r_ema_trend_rsi, "istniejąca"),
    "vwap_momentum": (r_vwap_momentum, "istniejąca"), "mtf_trend": (r_mtf, "ChatGPT 13"),
}


# ------------------------------------------------------------------ wejście i wynik
def exits_kw(cfg, ref: float) -> dict:
    return {"stop": ref * (1 - cfg.stop_loss_pct / 100), "tp": tp_plan(cfg.take_profit_levels),
            "trail": cfg.trailing_stop_pct / 100, "time_stop": (cfg.time_stop_minutes, cfg.time_stop_min_move_pct / 100)}


def entry(cfg, cs: list, ts: list, t: float) -> dict | None:
    """Wejście w chwili t: kurs = zamknięcie ostatniej świecy zamkniętej do t; wynik po obecnych wyjściach + zwroty
    z samej ceny po FWD minutach (po kosztach wejścia i wyjścia, bez stopów)."""
    j = bisect.bisect_right(ts, t - 60) - 1
    if j < 0 or cs[j][4] <= 0:
        return None
    ref = cs[j][4]
    path = [x for x in cs[j + 1:] if x[0] <= t + HORIZON_MIN * 60]
    if not path:
        return None
    ret = simulate(path, ref, t, **exits_kw(cfg, ref))[0]
    m = path_metrics(path, ref, t, cfg.stop_loss_pct / 100, cfg.take_profit_levels[0][0] / 100)
    fwd = {h: (close_before(cs, t + h * 60, ts) or ref) / ref * (1 - XC) / (1 + EC) - 1 for h in FWD}
    return {"t": t, "ret": ret, "rug": m["final"] <= -0.8, "fwd": fwd}


def universe(st: Storage, min_age: float | None = None, since: float | None = None) -> list[dict]:
    """Pierwszy czysty sygnał każdego tokena (safety_only = przeszedł twarde filtry) + świece wokół niego.
    Czas sygnału ze st.signals_timed (poprawka dla sygnałów przypiętych do starej oceny WATCH sprzed v0.9)."""
    first: dict = {}
    for r in st.signals_timed("safety_only"):
        first.setdefault(r["mint"], r)
    out = []
    for mint, r in first.items():
        age = r["age_min"] + (r["ts"] - r["ts_decision"]) / 60 if r["age_min"] is not None else None
        if since and r["ts"] < since:
            continue
        if min_age is not None and (age is None or age < min_age):
            continue
        pool = st.pool_for(mint, r["ts"])
        if not pool:
            continue
        cs = [x for x in st.candles_between(pool, r["ts"] - 300 * 60, r["ts"] + (SCAN_MIN + HORIZON_MIN) * 60) if x[4] > 0]
        ts = [x[0] for x in cs]
        tk = {"mint": mint, "sym": r["symbol"], "ts0": r["ts"], "age": age, "cs": cs, "ts": ts,
              "feat": json.loads(r["features"] or "{}")}
        if cs:
            tk["base"] = None
            out.append(tk)
    return out


def scan_rules(cfg, tk: dict, rules: dict = RULES) -> dict:
    """Minuta po minucie przez SCAN_MIN od pierwszego spojrzenia: pierwszy sygnał każdej reguły -> wejście."""
    cs, ts, ts0 = tk["cs"], tk["ts"], tk["ts0"]
    hits: dict = {}
    pending = set(rules)
    for i, x in enumerate(cs):
        if not pending:
            break
        close_t = x[0] + 60
        if close_t < ts0 or close_t >= ts0 + SCAN_MIN * 60:
            continue
        w = cs[max(0, i - 299):i + 1]
        f = indicators.compute(w[-100:], now=close_t + 1)
        if not f:
            continue
        for name in list(pending):
            try:
                hit = rules[name][0](f, w)
            except (ZeroDivisionError, ValueError):
                hit = False
            if hit:
                e = entry(cfg, cs, ts, close_t + LATENCY_S)
                if e:
                    hits[name] = e
                pending.discard(name)
    return hits


def _age_bucket(a) -> str:
    if a is None:
        return "?"
    return next(lab for edge, lab in AGE_BUCKETS if a < edge)


def _pf(rets):
    p, n = sum(x for x in rets if x > 0), -sum(x for x in rets if x < 0)
    return p / n if n else float("inf")


def _fwd_line(es: list) -> str:
    return "  ".join(f"+{h}m {statistics.median(e['fwd'][h] for e in es):+6.1%}" for h in FWD)


def _table(rows: list[tuple[str, list, list]], n_all: int, half: float):
    """rows = [(nazwa, wejścia, różnice vs pierwsze spojrzenie na tych samych tokenach)]"""
    hdr = (f"  {'wejście':<24}{'tokenów':>9}{'min':>5}{'śr.':>7}{'med.':>7}{'suma $50':>9}{'PF':>6}{'rugi':>5}"
           f"{'vs 1.spojrz.':>13}{'lepiej':>8}{'+5m':>7}{'+30m':>7}{'+60m':>7}{'1.poł.':>8}{'2.poł.':>8}")
    print(hdr)
    for name, es, diffs in rows:
        if not es:
            print(f"  {name:<24}{0:>5}/{n_all:<3}")
            continue
        rets = [e["ret"] for e in es]
        h1 = [e["ret"] for e in es if e["t0"] < half]
        h2 = [e["ret"] for e in es if e["t0"] >= half]
        med = lambda h: statistics.median(e["fwd"][h] for e in es)
        print(f"  {name:<24}{len(es):>5}/{n_all:<3}{statistics.median((e['t'] - e['t0']) / 60 for e in es):>5.0f}"
              f"{statistics.mean(rets):>+7.1%}{statistics.median(rets):>+7.1%}{sum(rets) * 50:>+9.0f}{_pf(rets):>6.2f}"
              f"{sum(e['rug'] for e in es):>5}{statistics.mean(diffs):>+13.1%}{sum(x > 0.001 for x in diffs):>4}/{len(diffs):<3}"
              f"{med(5):>+7.1%}{med(30):>+7.1%}{med(60):>+7.1%}"
              f"{(statistics.mean(h1) if h1 else float('nan')):>+8.1%}{(statistics.mean(h2) if h2 else float('nan')):>+8.1%}")


def _redundancy(st: Storage):
    from research import spearman
    keys = [("ch_m5", "cena 5 min"), ("ch_h1", "cena 1 h"), ("buy_ratio_m5", "udział kupna 5m"), ("ub_60s", "kupujący 60s"),
            ("buyer_accel", "przysp. kupujących"), ("seller_accel", "przysp. sprzedających"), ("bsi", "BSI (wol. kupna)"),
            ("txns_m5", "transakcje 5m"), ("vol_m5", "wolumen 5m"), ("smart_wallets_n", "smart money"),
            ("price_vs_vwap", "cena vs VWAP"), ("rsi14", "RSI"), ("atr_pct", "ATR %"), ("age_min", "wiek")]
    feats = []
    for r in st.db.execute("SELECT features, categories, opportunity FROM decisions WHERE features IS NOT NULL"):
        f = json.loads(r["features"])
        cat = json.loads(r["categories"] or "{}")
        if "momentum" in cat:
            f["momentum_kat"] = cat["momentum"]
        feats.append(f)
    keys.insert(2, ("momentum_kat", "kat. momentum"))
    num = lambda f, k: isinstance(f.get(k), (int, float)) and not isinstance(f.get(k), bool)
    keys = [(k, lab) for k, lab in keys if sum(num(f, k) for f in feats) >= 30]
    if len(keys) < 3:
        return
    print(f"\n== czy cechy mierzą to samo: korelacja Spearmana na {len(feats)} ocenach (|r| >= 0.5 = w dużej mierze to samo) ==")
    print(" " * 22 + "".join(f"{lab[:7]:>8}" for _, lab in keys))
    for a, la in keys:
        line = f"  {la[:19]:<20}"
        for b, _ in keys:
            xs = [(f[a], f[b]) for f in feats if num(f, a) and num(f, b)]
            r = 1.0 if a == b else spearman([x for x, _ in xs], [y for _, y in xs])
            line += f"{'' if r is None else f'{r:+.2f}':>8}"
        print(line)
    sig: dict = {}
    for r in st.db.execute("SELECT s.strategy, d.mint FROM signals s JOIN decisions d ON d.id=s.decision_id"):
        sig.setdefault(r["strategy"], set()).add(r["mint"])
    names = [n for n, _ in sorted(sig.items(), key=lambda kv: -len(kv[1]))[:9]]
    print("\n== czy strategie wskazują te same tokeny (wiersz A: jaki odsetek jej tokenów wskazała też kolumna B) ==")
    print(" " * 22 + "".join(f"{n[:9]:>10}" for n in names))
    for a in names:
        print(f"  {a[:19]:<20}" + "".join(f"{len(sig[a] & sig[b]) / len(sig[a]):>10.0%}" for b in names))


def run(cfg, min_age: float | None = None, since: float | None = None):
    st = Storage(cfg.db_path)
    t_start = time.time()
    toks = universe(st, min_age, since)
    for tk in toks:
        tk["base"] = entry(cfg, tk["cs"], tk["ts"], tk["ts0"] + LATENCY_S)
    toks = [tk for tk in toks if tk["base"]]
    if st.skipped:
        print(f"(pominięto {st.skipped} starych sygnałów z nieznanym czasem - przypiętych do oceny WATCH, bez wejścia portfela)")
    print(f"tokeny po twardych filtrach z archiwum świec: {len(toks)}"
          + (f" (tylko wiek >= {min_age:.0f} min przy pierwszej ocenie)" if min_age is not None else "")
          + (f", od {time.strftime('%d.%m %H:%M', time.localtime(since))}" if since else ""))
    if len(toks) < 5:
        print("Za mało danych - archiwum świec zapełnia się samo (świece pobierane 6 h po sygnale).")
        return
    toks.sort(key=lambda tk: tk["ts0"])
    n = len(toks)
    half = toks[n // 2]["ts0"]

    base = [dict(tk["base"], t0=tk["ts0"]) for tk in toks]
    print(f"\n== 1) pierwsze spojrzenie bota: zwrot z samej ceny (po kosztach {EC + XC:.1%}, bez stopów; mediana) ==")
    print(f"  wszystkie (n={n})".ljust(24) + _fwd_line(base))
    print("  " + "udział na plusie:".ljust(22) + "  ".join(f"+{h}m {sum(e['fwd'][h] > 0 for e in base) / n:6.0%}" for h in FWD))
    by_age: dict = {}
    for tk, e in zip(toks, base):
        by_age.setdefault(_age_bucket(tk["age"]), []).append(e)
    for _, lab in AGE_BUCKETS:
        if lab in by_age:
            es = by_age[lab]
            print(f"  wiek {lab} (n={len(es)})".ljust(24) + _fwd_line(es)
                  + f"   | po wyjściach śr. {statistics.mean(e['ret'] for e in es):+.1%}")
    print("  (mediana ceny to dryf rynku; 'po wyjściach' = wynik ze stopem i take-profitami. To nie to samo: 2.10 świeże tokeny\n"
          "   spadały najmocniej, a mimo to po wyjściach wypadały lepiej - stop ucina spadek, a częściej trafiają TP)")

    print(f"\n== 2) strategie z decyzji: pierwszy sygnał na token, wejście {LATENCY_S} s po decyzji, obecne wyjścia ==")
    first_sig: dict = {}
    for r in st.signals_timed():                              # rosnąco po czasie -> pierwszy sygnał na token
        first_sig.setdefault(r["strategy"], {}).setdefault(r["mint"], r["ts"])
    rows = []
    for name, mints in sorted(first_sig.items(), key=lambda kv: -len(kv[1])):
        es, diffs = [], []
        for tk in toks:
            t = mints.get(tk["mint"])
            if t is None or t < tk["ts0"]:
                continue
            e = entry(cfg, tk["cs"], tk["ts"], t + LATENCY_S)
            if e:
                es.append(dict(e, t0=tk["ts0"]))
                diffs.append(e["ret"] - tk["base"]["ret"])
        if len(es) >= 3:
            rows.append((name, es, diffs))
    _table(rows, n, half)

    print(f"\n== 3) strażnik wejść co minutę (retro): pierwszy sygnał reguły w {SCAN_MIN} min od pierwszego spojrzenia ==")
    hits = [scan_rules(cfg, tk) for tk in toks]
    rows = [("pierwsze spojrzenie", base, [0.0] * n)]
    for name in RULES:
        es, diffs = [], []
        for tk, h in zip(toks, hits):
            if name in h:
                es.append(dict(h[name], t0=tk["ts0"]))
                diffs.append(h[name]["ret"] - tk["base"]["ret"])
        rows.append((f"{name} ({RULES[name][1][:10]})", es, diffs))
    _table(rows, n, half)
    print("  'min' = mediana minut od pierwszego spojrzenia do wejścia; 'vs 1.spojrz.' = średnia różnica wyniku na TYCH SAMYCH")
    print("  tokenach (wejście w sygnale minus wejście przy pierwszej ocenie); 'lepiej' = na ilu tokenach wejście w sygnale")
    print("  dało więcej; +5m/+30m/+60m = mediana zwrotu z samej ceny; 1./2.poł. = średni wynik w pierwszej i drugiej")
    print("  połowie tokenów (stabilność w czasie). Reguła ma sens dopiero, gdy jest na plusie PO kosztach w obu połowach.")
    _redundancy(st)
    print(f"\n(liczone {time.time() - t_start:.0f} s; to ilustracja na danych historycznych - patrz nagłówek entry_research.py)")
