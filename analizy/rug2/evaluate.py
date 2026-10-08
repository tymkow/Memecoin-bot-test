"""Eksploracja rug2 (a-c) -> analizy/rug2/EXPLORATION.md. Wersja lokalna: bez Heliusa (cache z wcześniejszych analiz).

    python -m analizy.rug2.evaluate

Zbiór: migracje żywe w T = migracja + 30 min, wynik pozycji po kosztach: s0 (wyjście bota) i s6 (S6), etykieta (e)
pomocniczo. Podział czasowy 70/30. Każdy pomysł: lista reguł USTALONA Z GÓRY, najlepsza wybrana na eksploracji (N >= 30),
TEST liczony raz. Porównanie z baseline (wszystkie tokeny okna) i z oczekiwanym random_eligible (tokeny po twardych
filtrach bota w tym samym oknie - common.re_expected). Werdykt "działa" tylko, gdy na TEŚCIE reguła bije random_eligible
o >= 2 pp przy N >= 30, bije baseline, p losowego podzbioru < 0,10 i była lepsza od baseline na eksploracji.
"""
from __future__ import annotations

import collections
import time
from pathlib import Path

from analizy import common as C
from analizy.bundles import spearman
from analizy.rug2 import features as FT
from analizy.rug2.pit import FundingGraph, LaunchIndex, dataset

OUT = Path(__file__).resolve().parent / "EXPLORATION.md"
MIN_GAIN_RE = 0.02


def m(s, col="s0"):
    return C.mean([e[col] for e in s])


def rule_rows(ex, te, rules: dict, ycol="s0"):
    """Wszystkie reguły na eksploracji; zwraca (tabela, nazwa najlepszej)."""
    rows, best = [], None
    for name, keep in rules.items():
        k = [e for e in ex if keep(e)]
        if len(k) >= C.MIN_N and len(k) < len(ex) and (best is None or m(k, ycol) > best[1]):
            best = (name, m(k, ycol))
        rows.append([name, f"{len(k)}{C.rel(len(k))}", C.pct(m(k, ycol)), C.pct(m([e for e in ex if not keep(e)], ycol))])
    return rows, (best[0] if best else None)


def test_rule(name, keep, ex, te, ycol="s0"):
    kx, kt = [e for e in ex if keep(e)], [e for e in te if keep(e)]
    re_m, re_n = C.re_expected(te, ycol)
    p = C.perm_p([e[ycol] for e in kt], [e[ycol] for e in te])
    d_base, d_re = m(kt, ycol) - m(te, ycol), m(kt, ycol) - re_m
    if not m(kx, ycol) > m(ex, ycol):
        v = "nie działa (gorsze od baseline już na eksploracji)"
    elif len(kt) < C.MIN_N:
        v = f"niejasne (N testu {len(kt)} < 30)"
    elif d_base > 0 and d_re >= MIN_GAIN_RE and p < 0.10:
        v = "**działa**"
    elif d_base <= 0:
        v = "nie działa (na teście nie bije baseline)"
    else:
        v = f"niejasne (vs random_eligible {d_re * 100:+.1f} pp, p {p:.2f})"
    row = [name, f"{C.pct(m(kx, ycol))} vs {C.pct(m(ex, ycol))} (N {len(kx)}/{len(ex)})",
           f"{C.pct(m(kt, ycol))} vs {C.pct(m(te, ycol))} (N {len(kt)}{C.rel(len(kt))}/{len(te)}; p {p:.2f})",
           f"{C.pct(re_m)} (N {re_n}{C.rel(re_n)}); różnica {d_re * 100:+.1f} pp",
           f"{C.mean([e['rug'] for e in kt]):.0%} / {C.mean([e['rug'] for e in te]):.0%}", v]
    return row, v


HEAD_TEST = ["reguła (wybrana na eksploracji)", "eksploracja: reguła vs baseline", "TEST: reguła vs baseline",
             "random_eligible oczekiwany (TEST)", "rug (e) reguła / baseline", "werdykt"]


def univariate(ex, te, feats):
    rows = []
    for f in feats:
        vx = [e for e in ex if e.get(f) is not None]
        vt = [e for e in te if e.get(f) is not None]
        ax = C.auc([e[f] for e in vx if e["s0"] > 0], [e[f] for e in vx if e["s0"] <= 0])
        at = C.auc([e[f] for e in vt if e["s0"] > 0], [e[f] for e in vt if e["s0"] <= 0])
        rows.append([f, f"{(len(vx) + len(vt)) / max(len(ex) + len(te), 1):.0%}", f"{ax:.3f}", f"{at:.3f}",
                     f"{spearman([e[f] for e in vx], [e['s0'] for e in vx]):+.2f}",
                     f"{spearman([e[f] for e in vt], [e['s0'] for e in vt]):+.2f}"])
    return C.table(["cecha", "pokrycie", "AUC wynik>0 eksploracja", "AUC TEST", "Spearman z wynikiem eksploracja",
                    "Spearman TEST"], rows)


def section(title, ex, te, rules, feats, notes=""):
    out = [f"\n### {title}\n", notes, "\n**Pojedyncze cechy:**\n", univariate(ex, te, feats),
           "\n**Reguły ustalone z góry - eksploracja (wynik obecnego wyjścia, po kosztach):**\n"]
    verdicts = {}
    for ycol, lbl in (("s0", "obecne wyjście"), ("s6", "S6")):
        rows, best = rule_rows(ex, te, rules, ycol)
        if ycol == "s0":
            out.append(C.table(["reguła", "N wpuszczonych", "śr. wpuszczone", "śr. reszta"], rows))
            out.append(f"\n**TEST - tylko reguła najlepsza na eksploracji ({lbl} i S6 osobno):**\n")
            trows = []
        if best:
            r, v = test_rule(f"{best} ({lbl})", rules[best], ex, te, ycol)
            trows.append(r)
            verdicts[ycol] = (best, v)
    out.append(C.table(HEAD_TEST, trows) if trows else "brak reguły z N >= 30 na eksploracji")
    return "\n".join(out), verdicts


def summary_verdict(v: dict) -> str:
    vs = [x[1] for x in v.values()]
    if any("**działa**" in x for x in vs):
        return "DZIAŁA"
    if all(x.startswith("nie działa") for x in vs) and vs:
        return "NIE DZIAŁA"
    return "NIEJASNE"


def proposals(ents: list[dict]) -> list[tuple]:
    """Twórcy z >= 2 tokenami w danych z dodatnim wynikiem (do ręcznej oceny - NIE używane jako cecha, bo wynik
    tych tokenów jest z przyszłości względem wcześniejszych decyzji)."""
    by = collections.defaultdict(list)
    for e in ents:
        if e.get("creator_addr"):
            by[e["creator_addr"]].append(e)
    out = []
    for dev, es in by.items():
        good = [e for e in es if e["s0"] > 0]
        if len(good) >= 2:
            out.append((dev, len(es), len(good), C.mean([e["s0"] for e in es])))
    return sorted(out, key=lambda x: -x[3])


def write_trusted_template(props):
    if FT.TRUSTED.exists():
        return
    lines = ["# Zaufani twórcy - edytuj ręcznie. Używane jako CECHA (dev_trusted), nie bramka.",
             "# Przenieś adres z 'proposals' do 'trusted', jeśli się zgadzasz. Format: '  - addr: <adres>'.",
             "trusted:", "", "proposals:   # z danych: >= 2 tokeny z wynikiem > 0 (" + time.strftime('%d.%m.%Y') + ")"]
    for dev, n, g, mean in props:
        lines.append(f"  - addr: {dev}   # tokenów {n}, z zyskiem {g}, śr. wynik {mean * 100:+.1f}%")
    FT.TRUSTED.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    t0 = time.time()
    ents = dataset()
    ex, te = C.split_time(ents)
    idx = LaunchIndex.load()
    FT.add_dev(ents, idx)
    ex_wallets = {w for e in ex for w in e["fb_addrs"]} | {e["creator_addr"] for e in ex if e.get("creator_addr")}
    g = FundingGraph.load(explore_wallets=ex_wallets)
    FT.add_funding(ents, g)
    props = proposals(ents)
    write_trusted_template(props)
    FT.add_trusted(ents, FT.read_trusted())
    # c) "sprawdzony" twórca w chwili T: >= 2 wcześniejsze tokeny z zamkniętym oknem 6 h i wynikiem > 0 (point-in-time)
    by_dev = collections.defaultdict(list)
    for e in sorted(ents, key=lambda e: e["T"]):
        prev = [p for p in by_dev.get(e.get("creator_addr"), []) if p["T"] + C.H6 <= e["T"]]
        e["dev_proven_n"] = sum(1 for p in prev if p["s0"] > 0)
        e["dev_prev_eval_n"] = len(prev)
        if e.get("creator_addr"):
            by_dev[e["creator_addr"]].append(e)

    out = [f"# Eksploracja rug2 - nowe źródła sygnału ({time.strftime('%d.%m.%Y %H:%M')})\n",
           (__doc__ or "").split("Zbiór:", 1)[1].join(["Zbiór:", ""]),
           f"\nTokenów: **{len(ents)}** (eksploracja {len(ex)}, TEST {len(te)}). Baseline: eksploracja {C.pct(m(ex))}, "
           f"TEST {C.pct(m(te))}; random_eligible oczekiwany TEST {C.pct(C.re_expected(te, 's0')[0])} "
           f"(N {C.re_expected(te, 's0')[1]}). Wersja LOKALNA - bez nowych pobrań z Heliusa.\n"]
    verdicts = {}

    # a) historia twórcy
    cov = C.mean([e["dev_has_hist"] for e in ents])
    rules_a = {"twórca bez historii w danych": lambda e: e["dev_has_hist"] == 0,
               "twórca z historią (>= 1 start)": lambda e: e["dev_has_hist"] == 1,
               "twórca, którego coin już zmigrował": lambda e: e["dev_prev_mig_n"] >= 1,
               "bez seryjnych (< 5 startów)": lambda e: e["dev_prev_n"] < 5,
               "bez szybkiego ponownego startu (odstęp >= 1 h albo brak)": lambda e: e["dev_gap_h"] is None or e["dev_gap_h"] >= 1,
               "poprzedni coin miał >= 10 SOL obrotu": lambda e: (e["dev_prev_maxvol_sol"] or 0) >= 10}
    txt, v = section("a) Historia twórcy (slop / dev)", ex, te, rules_a,
                     ["dev_has_hist", "dev_prev_n", "dev_prev_mig_n", "dev_prev_mig_rate", "dev_gap_h",
                      "dev_prev_maxvol_sol", "dev_launches_per_day"],
                     f"Pokrycie: **{cov:.0%}** tokenów ma twórcę z >= 1 wcześniejszym startem w danych (zbieracz od 04.10, "
                     f"PumpPortal bota od 01.10 z nocnymi przerwami); >= 2 startów: "
                     f"{C.mean([e['dev_prev_n'] >= 2 for e in ents]):.0%}. Próg użytkownika: < 20% -> niejasne.")
    out.append(txt)
    verdicts["a) historia twórcy"] = ("NIEJASNE (za małe pokrycie)" if cov < 0.20 else summary_verdict(v), v, cov)

    # b) graf zasilania, osobno na każdy hop
    for k in (1, 2, 3):
        rules_b = {f"wspólny przodek do {k} hopów >= 10% kupujących": lambda e, k=k: (e[f"f{k}_shared"] or 0) >= 0.10,
                   f"wspólny przodek do {k} hopów >= 25%": lambda e, k=k: (e[f"f{k}_shared"] or 0) >= 0.25,
                   f"wspólny przodek do {k} hopów < 10%": lambda e, k=k: (e[f"f{k}_shared"] or 0) < 0.10,
                   f"powiązanie z twórcą do {k} hopów (> 0)": lambda e, k=k: (e[f"f{k}_creator_link"] or 0) > 0,
                   f"źródła zasilały wcześniejsze tokeny (>= 1)": lambda e, k=k: e[f"f{k}_src_prev_n"] >= 1,
                   f"wcześniejsze tokeny tych źródeł miały wynik > 0": lambda e, k=k: (e[f"f{k}_src_prev_s0"] or -9) > 0}
        covk = C.mean([e[f"f{k}_cover"] for e in ents if e[f"f{k}_cover"] is not None])
        pairs = [(w, e["T"]) for e in ents for w in e["fb_addrs"]]
        anc = sum(1 for w, T in pairs if g.ancestors(w, k, T)[k - 1] is not None) / max(len(pairs), 1)
        grew = sum(1 for e in ents if k > 1 and (e[f"f{k}_shared"] or 0) > (e[f"f{k - 1}_shared"] or 0))
        txt, v = section(f"b) Graf zasilania - hop {k}", ex, te, rules_b,
                         [f"f{k}_shared", f"f{k}_creator_link", f"f{k}_src_prev_n", f"f{k}_src_prev_s0"],
                         f"Łańcuch rozpoznany do hopu {k} (cache, bez nowych pobrań): **{covk:.0%}** pierwszych kupujących, "
                         f"ale przodka SPOZA hubów na hopie {k} ma tylko **{anc:.0%}** (56% pierwszych kupujących to portfele "
                         f"'aktywne' >= 3000 tx - źródła nie da się ustalić). Huby: {len(g.hubs)}."
                         + (f" Hop {k} dodał nowe powiązania w {grew} z {len(ents)} tokenów." if k > 1 else ""))
        out.append(txt)
        sv = summary_verdict(v)
        if anc < 0.20 and sv != "DZIAŁA":
            sv = f"NIEJASNE (za małe pokrycie: przodek spoza hubów u {anc:.0%} kupujących)"
        verdicts[f"b) graf zasilania, hop {k}"] = (sv, v, anc)

    # c) zaufani twórcy
    cov_c = C.mean([e["dev_proven_n"] >= 2 for e in ents])
    rules_c = {"twórca sprawdzony w T (>= 2 wcześniejsze tokeny z wynikiem > 0)": lambda e: e["dev_proven_n"] >= 2,
               "twórca z >= 1 wcześniejszym tokenem z wynikiem > 0": lambda e: e["dev_proven_n"] >= 1,
               "twórca z trusted_devs.yaml": lambda e: e["dev_trusted"] == 1}
    txt, v = section("c) Zaufani twórcy", ex, te, rules_c, ["dev_proven_n", "dev_prev_eval_n", "dev_trusted"],
                     f"Propozycje do analizy/rug2/trusted_devs.yaml (>= 2 tokeny w danych z wynikiem > 0): **{len(props)}** "
                     f"twórców. Pokrycie cechy point-in-time (>= 2 sprawdzone tokeny przed T): {cov_c:.1%} tokenów; "
                     f">= 1: {C.mean([e['dev_proven_n'] >= 1 for e in ents]):.1%}. Lista ręczna jest pusta, dopóki jej nie "
                     f"uzupełnisz (propozycje używają wyników z przyszłości - tylko do ręcznej oceny, nie jako cecha).")
    out.append(txt)
    verdicts["c) zaufani twórcy"] = ("NIEJASNE (za małe pokrycie)" if cov_c < 0.05 else summary_verdict(v), v, cov_c)

    from analizy.rug2.blind import report as BR
    blind = BR.report()
    out.append("\n### d) Ślepy test wizualny\n\nStrona `python -m analizy.rug2.blind.server` (wykres od startu do T, bez "
               "nazwy i dalszego przebiegu), odpowiedzi w analizy/rug2/blind/oceny.csv.\n\n" + blind + "\n")
    rows = []
    for name, (vv, v, cov) in verdicts.items():
        det = "; ".join(f"{'S0' if k == 's0' else 'S6'}: {b} -> {x}" for k, (b, x) in v.items())
        rows.append([name, f"{cov:.0%}", vv, det])
    pat = Path(__file__).resolve().parent / "PATTERNS.md"
    if pat.exists():
        out.append("\n### d2) " + pat.read_text(encoding="utf-8").lstrip("# ") +
                   "\n\nWniosek: 'prosta' i 'schodki' są gorsze w obu połowach (rug 40% vs 20%), ale twarde filtry bota już ich "
                   "nie przepuszczają (wśród tokenów po filtrach: 2/51 na eksploracji, 0/23 na teście) - dla bota bez wartości "
                   "dodanej. 'Zygzak' wychodzi odwrotnie niż intuicja (lepszy), 'V' słabo i niestabilnie.\n")
    dv = blind.split("**Werdykt d): ")[1].split(".**")[0] if "**Werdykt d)" in blind else "w toku (< 100 ocen)"
    rows.append(["d) ślepy test wizualny", "—", dv.upper() if dv.startswith(("nie", "dzia")) else dv.upper(),
                 blind.splitlines()[0].split(".")[0].strip("*")])
    if pat.exists():
        rows.append(["d2) wzorce wizualne (prosta / schodki / zygzak / V)", "10-22%",
                     "NIE DZIAŁA (dla bota)", "prosta i schodki gorsze w obu połowach, ale filtry bota już je odsiewają; "
                     "żaden filtr nie bije random_eligible"])
    out.insert(3, "\n## Werdykty\n\n" + C.table(["pomysł", "pokrycie", "werdykt", "szczegóły (reguła z eksploracji -> TEST)"], rows) + "\n")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"zapisano {OUT} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
