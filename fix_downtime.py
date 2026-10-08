"""Jednorazowa poprawka (4.10.2026): pozycje zamknięte jako 'downtime_close' (po kursie sprzed przerwy, do v0.10)
przeliczamy tak, jak robi to teraz bot: świece 1-min z przerwy przez reguły wyjścia strategii.

    python fix_downtime.py            # podgląd: co by się zmieniło (baza bez zmian)
    python fix_downtime.py --apply    # kopia bazy + poprawka (BOT MUSI BYĆ ZATRZYMANY)

Dla każdej pozycji: cofamy transakcję 'downtime_close' (gotówka strategii -= przychód), przywracamy pozycję jako otwartą,
odtwarzamy od początku przerwy do zamknięcia (najwyżej 24 h). Pozycja nadal otwarta po 24 h -> sprzedaż po ostatniej
świecy ('przerwa_koniec_okna'); brak świec / zła cena -> unieważnienie ('void')."""
import argparse
import json
import sqlite3
import time
from collections import Counter

from bot import Bot
from config import Config
from paper import position_from_row

MAX_H = 24


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    cfg = Config()
    if not a.apply:
        tmp = cfg.db_path.replace(".db", f"_podglad_{int(time.time())}.db")
        src = sqlite3.connect(cfg.db_path)
        dst = sqlite3.connect(tmp)
        src.backup(dst)
        src.close(); dst.close()
        cfg.db_path = tmp
        print(f"PODGLĄD na kopii {tmp}")
    else:
        bak = cfg.db_path.replace(".db", f"_przed_fix_downtime_{time.strftime('%Y%m%d_%H%M%S')}.db")
        src = sqlite3.connect(cfg.db_path)
        dst = sqlite3.connect(bak)
        src.backup(dst)
        src.close(); dst.close()
        print(f"kopia bazy: {bak}")
    db = sqlite3.connect(cfg.db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute("""SELECT p.id, p.mint, p.symbol, COALESCE(p.strategy,'hybrid') s, p.realized_usd, p.cost_usd,
                                t.id tid, t.ts tts, t.usd tusd, t.qty tqty
                         FROM positions p JOIN trades t ON t.position_id=p.id AND t.reason='downtime_close'
                         WHERE p.exit_reason='downtime_close' ORDER BY p.id""").fetchall()
    known = set(cfg.strategies)
    todo, before = [], {}
    for r in rows:
        if r["s"] not in known:
            print(f"  pomijam {r['symbol']} [{r['s']}] - strategii nie ma już w konfiguracji")
            continue
        t0 = db.execute("SELECT MAX(ts) FROM equity WHERE ts < ?", (r["tts"] - 60,)).fetchone()[0]
        if not t0:
            continue
        before[r["id"]] = r["realized_usd"] - r["cost_usd"]
        k = "" if r["s"] == "hybrid" else f"{r['s']}:"
        cash = db.execute("SELECT v FROM kv WHERE k=?", (k + "cash",)).fetchone()
        db.execute("UPDATE kv SET v=? WHERE k=?", (json.dumps(json.loads(cash[0]) - r["tusd"]), k + "cash"))
        db.execute("DELETE FROM trades WHERE id=?", (r["tid"],))
        db.execute("UPDATE positions SET status='open', closed_ts=NULL, exit_reason=NULL, qty_left=?, realized_usd=? "
                   "WHERE id=?", (r["tqty"], r["realized_usd"] - r["tusd"], r["id"]))
        todo.append((r["id"], r["mint"], r["symbol"], r["s"], t0))
    db.commit()
    db.close()
    print(f"pozycji do przeliczenia: {len(todo)}")
    bot = Bot(cfg)
    reopened = {pid for pid, *_ in todo}
    for pf in bot.portfolios.values():
        pf.sell_quoter = None
        for m in [m for m, p in pf.positions.items() if p.id in reopened]:   # wczytujemy po kolei niżej
            del pf.positions[m]                                               # (ten sam token kupiony 2 razy)
    res = Counter()
    cache = {}
    for pid, mint, sym, strat, t0 in todo:
        pf = bot.portfolios[strat]
        if mint in pf.positions:
            print(f"  pomijam {sym} [{strat}] - token ma już otwartą pozycję w tej strategii")
            continue
        pos = position_from_row(bot.store.db.execute("SELECT * FROM positions WHERE id=?", (pid,)).fetchone())
        pf.positions[mint] = pos
        t1 = min(t0 + MAX_H * 3600, time.time())
        if (mint, int(t0)) not in cache:
            cache[(mint, int(t0))] = bot.downtime_candles(mint, t0, t1)
        out = bot.replay_downtime(pf, pos, t0, t1, cache[(mint, int(t0))])
        if out == "open":
            last = [c for c in cache[(mint, int(t0))] if c[0] <= t1][-1]
            pf.clock = last[0]
            pf.sell(pos, pos.qty_left, last[4], pos.entry_liq or 0, "przerwa_koniec_okna")
            pf.clock = None
            out = "koniec okna"
        res[out] += 1
    db = sqlite3.connect(cfg.db_path)
    db.row_factory = sqlite3.Row
    print(f"\n{'token':<14}{'strategia':<22}{'było $':>9}{'jest $':>9}  powód")
    tot_b = tot_a = 0.0
    for pid, mint, sym, strat, t0 in todo:
        r = db.execute("SELECT status, exit_reason, realized_usd, cost_usd FROM positions WHERE id=?", (pid,)).fetchone()
        after = 0.0 if r["status"] == "void" else r["realized_usd"] - r["cost_usd"]
        tot_b += before[pid]; tot_a += after
        print(f"{sym[:13]:<14}{strat:<22}{before[pid]:>+9.2f}{after:>+9.2f}  {r['exit_reason']} ({r['status']})")
    print(f"\nrazem: było {tot_b:+.2f} $, jest {tot_a:+.2f} $ (unieważnione liczone jako 0) | {dict(res)}")


if __name__ == "__main__":
    main()
