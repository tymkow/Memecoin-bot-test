"""Raport ślepego testu: wynik pozycji tokenów oznaczonych "kupić" vs random_eligible (oczekiwany: tokeny po filtrach
bota z tej samej puli), vs "nie kupić" i vs cała pula, z 95% CI. Wyniki dopiero przy >= 100 ocenach.
Od 7.10 wieczorem odpowiedź ma pewność: kupic_pewny / kupic_niepewny (wcześniejsze "kupic" = pewność nieznana).

    python -m analizy.rug2.blind.report
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))

from analizy import common as C  # noqa: E402
from analizy.live_eval import ci, ci_diff  # noqa: E402

MIN_RATINGS = 100


def report() -> str:
    path = HERE / "oceny.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8"))) if path.exists() else []
    last = {r["mint"]: r["choice"] for r in rows}
    if len(last) < MIN_RATINGS:
        return f"Ślepy test: {len(last)} ocen - wyniki od {MIN_RATINGS}."
    ents = {e["mint"]: e for e in C.migration_entries(30)}
    C.add_outcomes(list(ents.values()))
    el = C.eligible_mints()
    groups = {"kupić (wszystkie)": lambda c: c.startswith("kupic"), "  kupić - pewny": lambda c: c == "kupic_pewny",
              "  kupić - niepewny": lambda c: c == "kupic_niepewny", "  kupić - pewność nieznana (pierwsze 120)": lambda c: c == "kupic",
              "nie kupić": lambda c: c == "nie"}
    out = [f"**Ślepy test: {len(last)} ocen.** Wyniki pozycji po kosztach (obecne wyjście / S6), etykiety pomocniczo.\n"]
    t, buy = [], []
    re_ = [e for e in ents.values() if e["mint"] in el]
    for name, cond in groups.items():
        es = [ents[m] for m, c in last.items() if m in ents and cond(c)]
        if name.startswith("kupić (w"):
            buy = es
        if not es:
            continue
        lo, hi = ci([e["s0"] for e in es])
        t.append([name, f"{len(es)}{C.rel(len(es))}", f"{C.pct(C.mean([e['s0'] for e in es]))} (CI {lo * 100:+.1f}..{hi * 100:+.1f}%)",
                  C.pct(C.mean([e['s6'] for e in es])), f"{C.mean([e['label'] == 'rug' for e in es]):.0%}",
                  f"{C.mean([e['label'] == 'pump' for e in es]):.0%}"])
    for name, es in (("cała pula", list(ents.values())), ("random_eligible (pula)", re_)):
        t.append([name, f"{len(es)}", C.pct(C.mean([e['s0'] for e in es])), C.pct(C.mean([e['s6'] for e in es])),
                  f"{C.mean([e['label'] == 'rug' for e in es]):.0%}", f"{C.mean([e['label'] == 'pump' for e in es]):.0%}"])
    out.append(C.table(["grupa", "N", "wynik (obecne wyjście)", "S6", "rug (e)", "pump"], t))
    l1, h1 = ci_diff([e["s0"] for e in buy], [e["s0"] for e in re_])
    rated = [ents[m] for m in last if m in ents]
    rug = [1 if last[e["mint"]].startswith("kupic") else 0 for e in rated if e["label"] == "rug"]
    nrug = [1 if last[e["mint"]].startswith("kupic") else 0 for e in rated if e["label"] != "rug"]
    out.append(f"\n'kupić' - random_eligible: CI {l1 * 100:+.1f}..{h1 * 100:+.1f} pp. AUC 'kupić' jako wskaźnik ruga: "
               f"{C.auc(rug, nrug):.3f} (> 0,5 = wybierane wykresy częściej rugują).")
    ok = len(buy) >= C.MIN_N
    verdict = ("niejasne (N 'kupić' < 30)" if not ok else
               ("działa" if l1 > 0.02 else "nie działa (nie bije random_eligible o >= 2 pp)"))
    out.append(f"\n**Werdykt d): {verdict}.**")
    return "\n".join(out)


if __name__ == "__main__":
    print(report())
