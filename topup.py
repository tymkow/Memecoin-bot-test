"""Dopłata gotówki do portfeli, które zbankrutowały (5.10.2026). Bez gotówki na pełną stawkę portfel przestaje wchodzić,
a wtedy znika z porównań (np. safety_only jako grupa kontrolna dla safety_ts5). Stawka jest stała ($50), więc wyniki
w $ na transakcję zostają porównywalne. Dopłata trafia do kv '<strategia>:deposits' (lista [ts, kwota]); raport pokazuje
kapitał bez dopłat i liczy maxDD z equity pomniejszonego o dopłaty.

    python topup.py safety_only safety_wide --to 1000            # podgląd
    python topup.py safety_only safety_wide --to 1000 --apply    # kopia bazy + dopłata (BOT MUSI BYĆ ZATRZYMANY)"""
import argparse
import sqlite3
import time

from config import Config
from storage import Storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("strategies", nargs="+")
    ap.add_argument("--to", type=float, default=1000.0, help="gotówka po dopłacie")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    cfg = Config()
    unknown = [s for s in a.strategies if s not in cfg.strategies]
    if unknown:
        ap.error(f"nieznane strategie: {unknown}")
    topup(cfg, a.strategies, a.to, a.apply)


def topup(cfg, strategies, to: float, apply: bool) -> dict:
    """Zwraca {strategia: dopłata}; zapisuje tylko przy apply=True (z kopią bazy)."""
    done = {}
    if apply:
        bak = cfg.db_path.replace(".db", f"_przed_topup_{time.strftime('%Y%m%d_%H%M%S')}.db")
        src, dst = sqlite3.connect(cfg.db_path), sqlite3.connect(bak)
        src.backup(dst)
        src.close(); dst.close()
        print(f"kopia bazy: {bak}")
    st = Storage(cfg.db_path)
    now = time.time()
    for s in strategies:
        k = "" if s == "hybrid" else f"{s}:"
        cash = st.kv_get(k + "cash", cfg.start_balance_usd)
        add = round(to - cash, 2)
        if add <= 0:
            print(f"{s}: gotówka ${cash:,.2f} >= ${to:,.0f} - bez dopłaty")
            continue
        print(f"{s}: gotówka ${cash:,.2f} -> ${to:,.2f} (dopłata ${add:,.2f})")
        if apply:
            st.kv_set(k + "deposits", st.kv_get(k + "deposits", []) + [[now, add]])
            st.kv_set(k + "cash", cash + add)
            st.kv_set(k + "day_start_equity", st.kv_get(k + "day_start_equity", cfg.start_balance_usd) + add)
        done[s] = add
    if not apply:
        print("PODGLĄD - nic nie zmieniono (dodaj --apply)")
    return done


if __name__ == "__main__":
    main()
