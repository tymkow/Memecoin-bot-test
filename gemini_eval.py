"""Test Gemini NA ŚLEPO (5.10.2026): czy model przewidzi rug w chwili wejścia i odróżni fałszywy stop w chwili stopa,
widząc wyłącznie dane, które bot miał w tamtej chwili.

    python gemini_eval.py cases                     # zbuduj przypadki (bez sieci) i pokaż liczności
    python gemini_eval.py run [--rpm 5] [--max N]   # zapytaj Gemini (odpowiedzi w data/gemini_eval.db, wznawialne)
    python gemini_eval.py report                    # AUC, macierz pomyłek, kalibracja, porównanie z prostą cechą

Test A (wejście): wejścia bota w tokeny, które w ciągu 6 h spadły do <= 20% ceny wejścia (rug / krach; świece
GeckoTerminal z archiwum bota) + TYLE SAMO zwykłych wejść (losowanie z ziarnem), pomieszane.
Test B (stop): wszystkie wyjścia na stopie (stop_loss, exit_gap; bez odtworzonych z przerwy - bot ich nie widział na
żywo). Pozytyw = fałszywy stop: cena wróciła do >= +50% nad wejściem przed upływem 6 h od wejścia.
Model nie widzi adresu tokena, etykiety ani niczego po chwili decyzji; percentyle cech liczone tylko z decyzji
SPRZED tej chwili. Klucz z secrets.json (llm.api_key), nigdy w logach. Zapytania nie liczą się do dziennego limitu bota
(osobny licznik), ale dzielą limit Google - dlatego wolne tempo i stop po 3 kolejnych odmowach 429.
"""
from __future__ import annotations

import argparse
import bisect
import json
import random
import sqlite3
import statistics
import time
from pathlib import Path

import requests

import exit_research
import llm
from config import Config

DATA = Path(__file__).parent / "data"
BOT_DB = DATA / "bot.db"
OUT_DB = DATA / "gemini_eval.db"
H6 = 6 * 3600
VERSION = "e1"

SYSTEM_A = """You are a risk analyst for a PAPER-trading research bot on Solana memecoins (pump.fun / PumpSwap / Raydium).
You see everything the bot knew at the exact moment it BOUGHT a token: its feature snapshot (with percentiles among
other recent tokens that passed the bot's filters), the bot's rule-based findings, price/liquidity snapshots and
1-minute candles before the purchase. Nothing after the purchase is shown.
Estimate p_rug = probability (0-100) that within the next 6 hours the price falls to 20% of the purchase price or
lower (rug pull, liquidity pull, coordinated dump or collapse). Use the whole 0-100 range - you are scored on how well
p_rug RANKS tokens, so giving every token a similar number is useless. verdict = RUG if you would avoid the token
because of collapse risk, otherwise OK. Write "reason" in Polish, max 2 short sentences, citing the data you used."""

SYSTEM_B = """You are a risk analyst for a PAPER-trading research bot on Solana memecoins (pump.fun / PumpSwap / Raydium).
The bot holds a position that has JUST hit its stop-loss. You see everything the bot knew at this moment: the feature
snapshot at purchase (with percentiles among other recent tokens), the bot's findings, and the price/liquidity path
from the purchase until now. Nothing after this moment is shown.
Estimate p_recover = probability (0-100) that before 6 hours after the purchase the price rises to at least +50% above
the PURCHASE price (so selling now at the stop would be a mistake). Use the whole 0-100 range - you are scored on how
well p_recover RANKS positions. verdict = HOLD if you would keep the position, otherwise SELL.
Write "reason" in Polish, max 2 short sentences, citing the data you used."""


def schema(field: str, verdicts: list[str]) -> dict:
    return {"type": "OBJECT", "properties": {field: {"type": "INTEGER"}, "verdict": {"type": "STRING", "enum": verdicts},
                                             "reason": {"type": "STRING"}},
            "required": [field, "verdict", "reason"]}


# ------------------------------------------------------------------ dane z bazy bota (tylko odczyt)
def ro() -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{BOT_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def pool_for(db, mint, ts):
    r = db.execute("SELECT pair FROM decisions WHERE mint=? AND pair IS NOT NULL ORDER BY ABS(ts-?) LIMIT 1",
                   (mint, ts)).fetchone()
    return r["pair"] if r else None


def candles(db, pool, t0, t1):
    return [list(r) for r in db.execute("SELECT ts,o,h,l,c,v FROM candles WHERE pool=? AND ts BETWEEN ? AND ? ORDER BY ts",
                                        (pool, int(t0), int(t1)))]


def entry_groups(db) -> list[dict]:
    """Pozycje różnych portfeli w ten sam token w ciągu 10 min = jedno wejście (jak exit_research.position_entries)."""
    groups: list[dict] = []
    for p in db.execute("SELECT * FROM positions WHERE status='closed' ORDER BY opened_ts"):
        for g in groups:
            if g["mint"] == p["mint"] and abs(g["ts"] - p["opened_ts"]) < 600:
                g["pos"].append(p)
                break
        else:
            groups.append({"mint": p["mint"], "ts": p["opened_ts"], "sym": p["symbol"], "pos": [p]})
    return groups


def notes_before(db, mint, ts) -> list[str]:
    r = db.execute("SELECT findings, explanation FROM decisions WHERE mint=? AND ts<=? ORDER BY ts DESC LIMIT 1",
                   (mint, ts + 5)).fetchone()
    if not r:
        return []
    out = json.loads(r["findings"] or "[]")
    return ([r["explanation"].split("\n")[0]] if r["explanation"] else []) + out


def reference_before(db, ts, cache: dict) -> dict:
    """Percentyle cech z 400 ostatnich ocenionych tokenów SPRZED chwili ts (jak w llm.reference, bez przyszłości)."""
    key = int(ts // 3600)
    if key not in cache:
        rows = db.execute("SELECT features FROM decisions WHERE decision IN ('BUY','SKIP') AND ts < ? "
                          "ORDER BY ts DESC LIMIT 400", (ts,)).fetchall()
        ref: dict = {}
        for (raw,) in rows:
            for k, v in json.loads(raw or "{}").items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    ref.setdefault(k, []).append(float(v))
        cache[key] = {k: sorted(v) for k, v in ref.items() if len(v) >= 20}
    return cache[key]


def fmt_features(features: dict, ref: dict) -> dict:
    """Wszystkie cechy z chwili wejścia; opisane nazwy z llm.FEATURES, pozostałe pod nazwą techniczną; percentyle."""
    out = {}
    for k, v in sorted(features.items()):
        if k.startswith("gemini") or v is None or isinstance(v, (dict, list)):
            continue
        name = llm.FEATURES.get(k, k)
        r = ref.get(k)
        if r and isinstance(v, (int, float)) and not isinstance(v, bool):
            out[name] = f"{v:.4g} (p{round(100 * bisect.bisect_left(r, float(v)) / len(r))})"
        else:
            out[name] = v if not isinstance(v, float) else round(v, 4)
    return out


def snaps(db, mint, t0, t1, ref_px, ref_liq=None, n=15) -> list[str]:
    rs = db.execute("SELECT ts, price, liq, vol_m5, buys_m5, sells_m5, ch_m5 FROM snapshots WHERE mint=? AND ts BETWEEN ? AND ? "
                    "ORDER BY ts", (mint, t0, t1)).fetchall()
    if len(rs) > n:
        idx = sorted({round(i * (len(rs) - 1) / (n - 1)) for i in range(n)})
        rs = [rs[i] for i in idx]
    out = []
    for r in rs:
        if not r["price"]:
            continue
        liq = ("liq ?" if not r["liq"] else f"liq {r['liq'] / ref_liq - 1:+.0%}" if ref_liq else f"liq ${r['liq']:,.0f}")
        out.append(f"t{(r['ts'] - t1) / 60:+.1f}min price {r['price'] / ref_px - 1:+.1%} {liq} vol5m ${r['vol_m5'] or 0:,.0f} "
                   f"buys/sells5m {r['buys_m5']}/{r['sells_m5']}")
    return out


def candle_rows(cs, t_now, ref_px, n=30) -> list[str]:
    if len(cs) > n:      # zawsze ostatnie 2/3 w całości, starsze co któraś - nie gubimy świecy z krachem na końcu
        tail = cs[-(2 * n // 3):]
        head = cs[:-(2 * n // 3)]
        step = max(1, len(head) // (n - len(tail)))
        cs = head[::step][: n - len(tail)] + tail
    return [f"t{(c[0] - t_now) / 60:+.0f}min o{c[1] / ref_px - 1:+.1%} h{c[2] / ref_px - 1:+.1%} l{c[3] / ref_px - 1:+.1%} "
            f"c{c[4] / ref_px - 1:+.1%} vol ${c[5]:,.0f}" for c in cs]


# ------------------------------------------------------------------ przypadki
def build_cases(seed: int = 7) -> tuple[list[dict], dict]:
    cfg = Config()
    db = ro()
    refc: dict = {}
    A, B, info = [], [], {"bez_swiec": 0, "zla_cena": 0}
    stop_reasons = ("stop_loss", "exit_gap")
    for g in entry_groups(db):
        p0 = g["pos"][0]
        ts = g["ts"]
        pool = pool_for(db, g["mint"], ts)
        cs = candles(db, pool, ts - 100 * 60, ts + H6) if pool else []
        pre = [c for c in cs if c[0] + 60 <= ts]
        post = [c for c in cs if c[0] + 60 > ts]
        if not pre or not post:
            info["bez_swiec"] += 1
            continue
        ref = pre[-1][4]
        ep = statistics.mean(p["entry_price"] for p in g["pos"])
        if not ref or not 0.5 < ep / ref < 2:
            info["zla_cena"] += 1
            continue
        feats = (json.loads(p0["entry_info"] or "{}").get("features")) or {}
        rf = reference_before(db, ts, refc)
        notes = notes_before(db, g["mint"], ts)
        base = {"sym": g["sym"], "features": fmt_features(feats, rf), "notes": notes[:14], "raw_features": feats}
        rug = min(c[3] for c in post) / ref <= 0.2
        A.append(dict(base, id=f"A:{g['mint']}:{int(ts)}", test="A", y=int(rug), ts=ts,
                      pnl=statistics.mean(p["realized_usd"] - p["cost_usd"] for p in g["pos"]),
                      snaps=snaps(db, g["mint"], ts - 3600, ts, ref), candles=candle_rows(pre[-30:], ts, ref)))
        # test B: wyjścia na stopie (jeden przypadek na poziom stopa)
        seen = set()
        for p in g["pos"]:
            if p["exit_reason"] not in stop_reasons:
                continue
            stop = (cfg.strategy_exits.get(p["strategy"] or "hybrid", {}) or {}).get("stop_loss_pct", cfg.stop_loss_pct)
            if stop in seen:
                continue
            seen.add(stop)
            te = p["closed_ts"]
            after = [c for c in cs if c[0] >= te and c[0] <= p["opened_ts"] + H6]
            hold = [c for c in cs if p["opened_ts"] - 60 <= c[0] and c[0] + 60 <= te]
            false_stop = bool(after) and max(c[2] for c in after) >= p["entry_price"] * 1.5
            # wynik "gdyby trzymać": te same TP/trailing/time stop bota od wejścia, bez stopa, od chwili wyjścia
            sim = exit_research.simulate(after, p["entry_price"], p["opened_ts"], stop=None,
                                         tp=exit_research.tp_plan(cfg.take_profit_levels), trail=cfg.trailing_stop_pct / 100,
                                         time_stop=(cfg.time_stop_minutes, cfg.time_stop_min_move_pct / 100))[0] if after else None
            px_now = db.execute("SELECT SUM(usd)/SUM(qty) FROM trades WHERE position_id=? AND side='SELL'", (p["id"],)).fetchone()[0]
            mfe = max([c[2] for c in hold] or [p["entry_price"]]) / p["entry_price"] - 1
            B.append(dict(base, id=f"B:{p['mint']}:{int(p['opened_ts'])}:{stop:g}", test="B", y=int(false_stop), ts=te,
                          stop=stop, held_min=(te - p["opened_ts"]) / 60,
                          now=(px_now / p["entry_price"] - 1) if px_now else None, mfe=mfe,
                          pnl=p["realized_usd"] - p["cost_usd"], hold_ret=sim, cost=p["cost_usd"],
                          snaps=snaps(db, p["mint"], p["opened_ts"], te, p["entry_price"], p["entry_liq"] or None, n=20),
                          candles=candle_rows(hold, te, p["entry_price"], n=40)))
    rnd = random.Random(seed)
    rugs = [c for c in A if c["y"]]
    rest = [c for c in A if not c["y"]]
    A_bal = rugs + rnd.sample(rest, min(len(rest), len(rugs)))
    info.update(A_all=len(A), A_rug=len(rugs), A_ctrl=len(A_bal) - len(rugs), B=len(B), B_false=sum(c["y"] for c in B))
    cases = A_bal + B
    rnd.shuffle(cases)
    return cases, info


def prompt(c: dict) -> str:
    head = f"Token {c['sym']}.\nFeature snapshot at purchase (percentile among recent filtered tokens in brackets):\n" \
           f"{json.dumps(c['features'], ensure_ascii=False, indent=0)}\n" \
           f"Bot's rule-based findings at purchase:\n- " + "\n- ".join(c["notes"] or ["(none)"])
    if c["test"] == "A":
        return (head + "\nPrice/liquidity snapshots before purchase (price relative to the purchase price):\n- "
                + "\n- ".join(c["snaps"] or ["(none)"])
                + "\n1-minute candles before purchase (relative to the purchase price):\n- " + "\n- ".join(c["candles"] or ["(none)"]))
    return (head + f"\n\nNOW: the position hit its stop-loss (-{c['stop']:g}% level) after {c['held_min']:.0f} min; "
            f"current executable price {c['now']:+.1%} vs purchase; best price since purchase {c['mfe']:+.1%}.\n"
            "Snapshots since purchase (price and liquidity relative to purchase):\n- " + "\n- ".join(c["snaps"] or ["(none)"])
            + "\n1-minute candles since purchase (relative to the purchase price):\n- " + "\n- ".join(c["candles"] or ["(none)"]))


# ------------------------------------------------------------------ zapytania
def out_db() -> sqlite3.Connection:
    c = sqlite3.connect(OUT_DB)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS answers(id TEXT PRIMARY KEY, test TEXT, version TEXT, ts REAL, p INTEGER, "
              "verdict TEXT, reason TEXT, error TEXT, tokens_in INTEGER, tokens_out INTEGER)")
    return c


def ask(s: requests.Session, key: str, model: str, c: dict) -> dict:
    field, verdicts, system = ("p_rug", ["RUG", "OK"], SYSTEM_A) if c["test"] == "A" else ("p_recover", ["HOLD", "SELL"], SYSTEM_B)
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt(c)}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400, "responseMimeType": "application/json",
                                 "responseSchema": schema(field, verdicts)}}
    r = s.post(llm.URL.format(model=model), json=body, timeout=40,
               headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    if r.status_code != 200:
        return {"status": r.status_code, "error": f"HTTP {r.status_code}: {r.text[:160]}"}
    j = r.json()
    u = j.get("usageMetadata") or {}
    try:
        cand = j["candidates"][0]
        d = json.loads(cand["content"]["parts"][0]["text"])
        p = int(d[field])
        if not 0 <= p <= 100 or d["verdict"] not in verdicts:
            raise ValueError("poza zakresem")
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as e:
        return {"status": 200, "error": f"odrzucona: {type(e).__name__}"}
    return {"status": 200, "p": p, "verdict": d["verdict"], "reason": str(d.get("reason", ""))[:400],
            "tokens_in": u.get("promptTokenCount"), "tokens_out": (u.get("candidatesTokenCount") or 0) + (u.get("thoughtsTokenCount") or 0)}


def run(rpm: int, max_n: int | None):
    key = llm.api_key()
    if not key:
        print("brak GEMINI_API_KEY")
        return
    cfg = Config()
    cases, info = build_cases()
    db = out_db()
    done = {r["id"] for r in db.execute("SELECT id FROM answers WHERE version=? AND error IS NULL", (VERSION,))}
    todo = [c for c in cases if c["id"] not in done][:max_n]
    print(f"przypadków: {len(cases)} ({info}), do zapytania: {len(todo)}, tempo {rpm}/min, model {cfg.gemini_model}", flush=True)
    s = requests.Session()
    refused = 0
    for i, c in enumerate(todo, 1):
        t0 = time.time()
        try:
            a = ask(s, key, cfg.gemini_model, c)
        except requests.RequestException as e:
            a = {"status": 0, "error": f"sieć: {type(e).__name__}"}
        if a.get("status") == 429:
            refused += 1
            print(f"{time.strftime('%H:%M:%S')} 429 (limit Google) - {refused}/3, czekam 90 s", flush=True)
            if refused >= 3:
                print("STOP: 3 odmowy z rzędu - dzienny limit? Wznów później tym samym poleceniem.")
                return
            time.sleep(90)
            continue
        refused = 0
        db.execute("INSERT OR REPLACE INTO answers VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (c["id"], c["test"], VERSION, time.time(), a.get("p"), a.get("verdict"), a.get("reason"), a.get("error"),
                    a.get("tokens_in"), a.get("tokens_out")))
        db.commit()
        if i % 20 == 0 or a.get("error"):
            print(f"{time.strftime('%H:%M:%S')} {i}/{len(todo)} {a.get('error') or ''}", flush=True)
        time.sleep(max(0.0, 60 / rpm - (time.time() - t0)))
    print("koniec")


# ------------------------------------------------------------------ raport
def auc(pos, neg):
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def report():
    cases, info = build_cases()
    db = out_db()
    ans = {r["id"]: r for r in db.execute("SELECT * FROM answers WHERE version=? AND error IS NULL", (VERSION,))}
    errs = db.execute("SELECT COUNT(*) FROM answers WHERE version=? AND error IS NOT NULL", (VERSION,)).fetchone()[0]
    print(f"przypadki: {info}; odpowiedzi: {len(ans)}, błędnych odpowiedzi: {errs}")
    for test, pos_name, neg_name, verdict_pos, feat in (("A", "rug", "zwykłe", "RUG", "same_block_buy_share"),
                                                        ("B", "fałszywy stop", "słuszny stop", "HOLD", "ub_60s")):
        cs = [c for c in cases if c["test"] == test and c["id"] in ans]
        if not cs:
            continue
        pos = [ans[c["id"]]["p"] for c in cs if c["y"]]
        neg = [ans[c["id"]]["p"] for c in cs if not c["y"]]
        print(f"\n== Test {test}: {pos_name} vs {neg_name} - n={len(cs)} ({len(pos)} / {len(neg)}) ==")
        print(f"  AUC Gemini: {auc(pos, neg):.3f}   (0.5 = losowo; 1.0 = idealnie)")
        # proste punkty odniesienia (bez modelu): czy Gemini wnosi coś ponad oczywistość?
        base = {f"cecha {feat}": lambda c: c["raw_features"].get(feat)}
        if test == "B":
            base.update({"cena teraz vs wejście (wyżej = częściej odbija?)": lambda c: c["now"],
                         "najlepsza cena od wejścia (MFE)": lambda c: c["mfe"],
                         "czas trzymania (min)": lambda c: c["held_min"]})
        else:
            base.update({"unikalni kupujący 60 s": lambda c: c["raw_features"].get("ub_60s"),
                         "ATR 1-min %": lambda c: c["raw_features"].get("atr_pct")})
        for name, fn in base.items():
            fv = [(fn(c), c["y"]) for c in cs if isinstance(fn(c), (int, float))]
            a = auc([v for v, y in fv if y], [v for v, y in fv if not y])
            print(f"  dla porównania {name}: AUC {a:.3f}  (odwrotny kierunek: {1 - a:.3f})")
        tp = sum(1 for c in cs if c["y"] and ans[c["id"]]["verdict"] == verdict_pos)
        fp = sum(1 for c in cs if not c["y"] and ans[c["id"]]["verdict"] == verdict_pos)
        fn = len(pos) - tp
        tn = len(neg) - fp
        print(f"  werdykt {verdict_pos}: trafione {tp}, fałszywe alarmy {fp}, przeoczone {fn}, poprawnie odrzucone {tn}")
        if tp + fp:
            print(f"  precyzja {tp / (tp + fp):.0%} (odsetek {pos_name} w próbie {len(pos) / len(cs):.0%}), czułość {tp / max(len(pos), 1):.0%}")
        print("  kalibracja (p Gemini -> faktyczny odsetek):")
        for lo, hi in ((0, 20), (20, 40), (40, 60), (60, 80), (80, 101)):
            g = [c for c in cs if lo <= ans[c["id"]]["p"] < hi]
            if g:
                print(f"    p {lo:>2}-{min(hi, 100):<3} n={len(g):>3}  faktycznie {sum(c['y'] for c in g) / len(g):.0%}")
        if test == "A":
            avoid = [c for c in cs if ans[c["id"]]["verdict"] == "RUG"]
            keep = [c for c in cs if ans[c["id"]]["verdict"] != "RUG"]
            print(f"  wynik pozycji (śr. $ na wejście, wszystkie portfele): odrzucone przez Gemini {statistics.mean(c['pnl'] for c in avoid) if avoid else 0:+.2f} "
                  f"(n={len(avoid)}), przepuszczone {statistics.mean(c['pnl'] for c in keep) if keep else 0:+.2f} (n={len(keep)})")
        else:
            hold = [c for c in cs if ans[c["id"]]["verdict"] == "HOLD" and c["hold_ret"] is not None]
            if hold:
                actual = sum(c["pnl"] for c in hold)
                alt = sum(c["hold_ret"] * c["cost"] for c in hold)
                print(f"  gdyby trzymać, gdy Gemini mówi HOLD (n={len(hold)}): wynik ${actual:+.2f} -> ${alt:+.2f} "
                      f"(różnica ${alt - actual:+.2f}; trzymanie = TP/trailing/time stop bota, bez stopa)")
        ex = sorted(cs, key=lambda c: -ans[c["id"]]["p"])
        print("  najwyżej ocenione:", ", ".join(f"{c['sym']}({ans[c['id']]['p']}, {'TAK' if c['y'] else 'nie'})" for c in ex[:8]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cases", "run", "report"])
    ap.add_argument("--rpm", type=int, default=5)
    ap.add_argument("--max", type=int)
    a = ap.parse_args()
    if a.cmd == "cases":
        cases, info = build_cases()
        print(info)
        c = next(x for x in cases if x["test"] == "B")
        print("\nPRZYKŁADOWY PROMPT (test B, bez etykiety):\n" + prompt(c)[:3000])
    elif a.cmd == "run":
        run(a.rpm, a.max)
    else:
        report()


if __name__ == "__main__":
    main()
