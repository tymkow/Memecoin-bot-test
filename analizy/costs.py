"""7. KOSZTY - średni wynik brutto vs koszty (prowizja, poślizg, priority fee) w punktach procentowych stawki.

(A) Symulacja (części 3/4): koszty exit_research - wejście 1.5% (EC), wyjście 4% (XC) od wartości; brutto = to samo
    wejście i wyjście bez kosztów (analizy.common.no_costs).
(B) PRAWDZIWE transakcje bota (paper.py, każda zamknięta pozycja). Model kosztów bota:
    wejście z kwotowania Jupitera: ilość = kwotowanie x (1 - 1% "poślizg z życia") x (1 - priority fee / stawka);
    kwotowanie ma już prowizję DEX-a i wpływ na pulę. Wyjście: wpływy = kwotowanie x 0.99 - priority fee.
    Rozbicie na pozycję:
      priority fee      = $0.05 na każdą transakcję (config.priority_fee_usd)
      poślizg "z życia"  = 1% wartości każdej transakcji (config.extra_slippage_pct)
      DEX + pula        = reszta różnicy między ceną odniesienia (DexScreener / cena wykonalna) a faktyczną
      luka przy krachu  = ta reszta w sprzedażach z poślizgiem >= 15% (kwotowanie dużo niższe niż pokazywana cena -
                          to raczej szybki spadek ceny niż "opłata", ale obciąża wynik tak samo)
    brutto = wynik netto + wszystkie koszty (wycena po cenach odniesienia).
"""
from __future__ import annotations

import collections

from analizy import common as C
from analizy import scaling_out as SO

GAP_SLIP = 15.0


def sim_section() -> str:
    out = ["\n**(A) Symulacja: ten sam zestaw wejść co części 3/4/6, wyjście obecne (S0) i S6**\n"]
    rows = []
    for title, ents in (("wejścia bota", C.bot_entry_set()), ("migracje + 30 min", C.migration_entries(30))):
        for scheme in (list(SO.SCHEMES)[0], [s for s in SO.SCHEMES if s.startswith("S6")][0]):
            net = SO.run(ents, scheme)
            with C.no_costs():
                gross = SO.run(ents, scheme)
            with C.no_costs(entry=False):
                only_entry = SO.run(ents, scheme)
            g, n, ce = C.mean(gross), C.mean(net), C.mean(only_entry)
            rows.append([title, scheme.split(" ")[0], f"{len(ents)}", C.pct(g), C.pct(n), f"{(g - n) * 100:.1f} pp",
                         f"{(g - ce) * 100:.1f} pp", f"{(ce - n) * 100:.1f} pp"])
    out.append(C.table(["zbiór", "wyjście", "N", "brutto", "netto", "koszty razem", "w tym wejście", "w tym wyjście"], rows))
    return "\n".join(out)


def real_rows() -> list[dict]:
    """Każda zamknięta pozycja bota: strategia, czas, stawka, wynik netto i brutto ($) + składniki kosztów."""
    db = C.ro("bot.db")
    cfg = C.CFG
    pri, extra = cfg.priority_fee_usd, cfg.extra_slippage_pct / 100
    tr = collections.defaultdict(list)
    for r in db.execute("SELECT position_id, side, price, qty, usd, fee_usd, slippage_pct FROM trades"):
        tr[r[0]].append(r)
    rows = []
    for p in db.execute("SELECT id, strategy, cost_usd, realized_usd, qty_initial, opened_ts FROM positions WHERE status='closed'"):
        ts = tr.get(p["id"], [])
        buys = [t for t in ts if t["side"] == "BUY"]
        sells = [t for t in ts if t["side"] == "SELL"]
        if not buys:
            continue
        c = {"priority": 0.0, "extra": 0.0, "dex": 0.0, "gap": 0.0}
        for b in buys:
            ref = b["price"] / (1 + (b["slippage_pct"] or 0) / 100)
            total = b["usd"] - b["qty"] * ref
            c["priority"] += pri
            c["extra"] += extra * (b["usd"] - pri)
            c["dex"] += total - pri - extra * (b["usd"] - pri)
        for s in sells:
            if s["usd"] <= 0 and s["price"] <= 0:          # spisanie na zero (rug) - strata jest w brutto, nie w kosztach
                continue
            fee = s["fee_usd"] or 0.0
            quoted = (s["usd"] + pri) / (1 - extra)
            c["priority"] += pri
            c["extra"] += extra * quoted
            rest = fee - pri - extra * quoted
            c["gap" if (s["slippage_pct"] or 0) >= GAP_SLIP else "dex"] += rest
        net = p["realized_usd"] - p["cost_usd"]
        rows.append({"s": p["strategy"] or "hybrid", "ts": p["opened_ts"], "stake": p["cost_usd"], "net": net,
                     "gross": net + sum(c.values()), **c})
    return rows


def real_section() -> str:
    rows = real_rows()
    ex, te = C.split_time(rows)
    out = [f"\n**(B) PRAWDZIWE pozycje bota: {len(rows)}** (eksploracja {len(ex)}, TEST {len(te)}) - średnio na pozycję, "
           f"w pp stawki ($50):\n"]
    t = []
    for lbl, rs in (("cały okres", rows), ("eksploracja", ex), ("TEST", te)):
        pp = lambda k: C.mean([r[k] / r["stake"] for r in rs]) * 100
        costs = pp("priority") + pp("extra") + pp("dex") + pp("gap")
        t.append([lbl, f"{len(rs)}", f"{pp('gross'):+.1f}", f"{pp('priority'):.1f}", f"{pp('extra'):.1f}", f"{pp('dex'):.1f}",
                  f"{pp('gap'):.1f}", f"**{costs:.1f}**", f"{pp('net'):+.1f}"])
    out.append(C.table(["okres", "N", "brutto (pp)", "priority fee", "poślizg 'z życia' 1%", "DEX + pula",
                        "luka przy krachu", "koszty razem", "netto (pp)"], t))
    out.append("\n**Według strategii (cały okres, suma $):**\n")
    st = collections.defaultdict(list)
    for r in rows:
        st[r["s"]].append(r)
    t2 = []
    for s, rs in sorted(st.items(), key=lambda kv: sum(r["net"] for r in kv[1])):
        t2.append([s, f"{len(rs)}", f"{sum(r['gross'] for r in rs):+.0f}", f"{sum(r['priority'] + r['extra'] + r['dex'] for r in rs):.0f}",
                   f"{sum(r['gap'] for r in rs):.0f}", f"{sum(r['net'] for r in rs):+.0f}"])
    out.append(C.table(["strategia", "pozycji", "$ brutto", "$ koszty zwykłe", "$ luka przy krachu", "$ netto"], t2))
    return "\n".join(out)


def report() -> str:
    return "\n".join(["## 7. Koszty: wynik brutto vs koszty", sim_section(), real_section()])


if __name__ == "__main__":
    print(report())
