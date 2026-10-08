"""Badania na zebranych danych (bez zewnętrznych bibliotek): które cechy przewidują wynik i którzy kupujący są "mądrzy".

`python bot.py features`  - korelacja Spearmana cech z wynikiem po N h + prosta kontrola out-of-sample
`python bot.py wallets`   - empiryczny ranking portfeli kupujących (wynik ich zakupów po N h)

To NIE jest model uczenia maszynowego. Przy kilkudziesięciu próbkach i dziesiątkach cech część "znalezisk" to
przypadek (problem wielokrotnych porównań) - dlatego raport pokazuje, czy znak korelacji zgadza się w obu połowach
danych (pierwsza połowa czasu vs druga). Wag punktacji NIE wolno stroić na tych samych transakcjach, którymi
oceniamy strategię; dopiero osobny, późniejszy okres jest uczciwym testem.
"""
from __future__ import annotations

import json
import math
import statistics

from storage import Storage


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 5 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def _samples(st: Storage, horizon: int):
    rows = st.db.execute(
        "SELECT d.mint, d.ts, d.features, d.price, d.liq, o.price p1, o.liq l1 FROM decisions d "
        "JOIN outcomes o ON o.decision_id=d.id AND o.horizon_h=? WHERE d.price>0 AND d.features IS NOT NULL "
        "ORDER BY d.ts", (horizon,)).fetchall()
    seen, out = set(), []
    for r in rows:
        if r["mint"] in seen:
            continue
        seen.add(r["mint"])
        ret = (r["p1"] / r["price"] - 1) if r["p1"] and r["p1"] > 0 else -1.0
        out.append((json.loads(r["features"]), ret))
    return out


def feature_report(cfg, horizon: int = 6):
    st = Storage(cfg.db_path)
    data = _samples(st, horizon)
    print(f"próbek (tokeny z cechami i pomiarem po {horizon} h): {len(data)}")
    if len(data) < 30:
        print("Za mało danych na korelacje (potrzeba co najmniej ~30, sensownie 200+). Zostaw bota włączonego.")
        return
    names = sorted({k for f, _ in data for k, v in f.items() if isinstance(v, (int, float))})
    half = len(data) // 2
    rows = []
    for k in names:
        pairs = [(f[k], r) for f, r in data if isinstance(f.get(k), (int, float))]
        if len(pairs) < 30:
            continue
        rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
        if rho is None:
            continue
        # kontrola czasowa: ta sama korelacja w pierwszej i drugiej połowie danych
        a = [(f[k], r) for f, r in data[:half] if isinstance(f.get(k), (int, float))]
        b = [(f[k], r) for f, r in data[half:] if isinstance(f.get(k), (int, float))]
        ra = spearman([p[0] for p in a], [p[1] for p in a]) if len(a) >= 10 else None
        rb = spearman([p[0] for p in b], [p[1] for p in b]) if len(b) >= 10 else None
        stable = ra is not None and rb is not None and ra * rb > 0 and ra * rho > 0
        rows.append((abs(rho), k, rho, len(pairs), ra, rb, stable))
    noise = 2 / math.sqrt(len(data))
    print(f"próg szumu ~ |rho| < {noise:.2f} (2/sqrt(n)); cech testowanych: {len(rows)} - część wyników to przypadek\n")
    print(f"{'cecha':<26}{'rho':>7}{'n':>6}   1. poł.  2. poł.  stabilna")
    for _, k, rho, n, ra, rb, stable in sorted(rows, reverse=True)[:25]:
        fa = f"{ra:+.2f}" if ra is not None else "  -  "
        fb = f"{rb:+.2f}" if rb is not None else "  -  "
        print(f"{k:<26}{rho:>+7.2f}{n:>6}   {fa:>6}   {fb:>6}   {'TAK' if stable else 'nie'}")


def wallet_report(cfg, horizon: int = 6):
    """Ranking portfeli z własnego silnika (wallets.WalletEngine): jakość, skuteczność, wynik kopiowania z opóźnieniem."""
    from wallets import WalletEngine
    st = Storage(cfg.db_path)
    eng = WalletEngine(cfg, st)
    eng.refresh(force=True)
    n_tr = st.db.execute("SELECT COUNT(*) FROM wallet_trades").fetchone()[0]
    rated = [s for s in eng.stats.values() if s.quality is not None]
    print(f"transakcji w bazie: {n_tr}, portfeli: {len(eng.stats)}, ocenionych (>= {cfg.wallet_min_closed} domkniętych pozycji): "
          f"{len(rated)}, śledzonych (jakość >= {cfg.wallet_min_quality:.0f}, bez botów): {len(eng.tracked)}")
    if not rated:
        print("Za mało danych - transakcje portfeli zbierają się przy każdej ocenie tokena (tabela wallet_trades).")
        return
    print("UWAGA: widzimy tylko ostatnie ~300 transakcji każdej puli tokenów, które oceniliśmy - pozycje 'domknięte' to te,"
          " które portfel zdążył sprzedać w tym oknie. Ranking pomysłów, nie dowód 'smart money'.\n")
    print(f"{'portfel':<46}{'jakość':>7}{'tokeny':>7}{'zamkn.':>7}{'win':>6}{'śr.ROI':>9}{'kopia':>9}{'hold':>7}  flagi")
    for s in sorted(rated, key=lambda s: -s.quality)[:20]:
        copy = f"{s.copy_roi:+.0%}" if s.copy_roi is not None else "-"
        print(f"{s.wallet:<46}{s.quality:>7.0f}{s.tokens:>7}{s.closed:>7}{s.win_rate:>6.0%}{s.mean_roi:>+9.0%}{copy:>9}"
              f"{s.median_hold_s:>6.0f}s  {'BOT/MM' if s.is_bot else ''}")
    print("\nAby śledzić portfel ręcznie: wpisz adres do \"smart_wallets\" w config.json.")
