"""Reguła tradera Bot D (analizy/KOL_bot_D.md) odtworzona w całości: kupno najgorętszego startu ~30-60 s po
utworzeniu, sprzedaż DOKŁADNIE po 21 s (u niego wszystkie kwartyle trzymania = 21 s). Czy działa z naszym opóźnieniem?

    python -m analizy.rule21      # -> analizy/REGULA_21S.md

Silnik i zasady jak analizy/slow_rule.py (siatka tylko na 70%, test raz, baseline = każdy żywy token w tym wieku);
d = 0 s = jego wykonanie (nieosiągalne odniesienie).
"""
from analizy import common as C
from analizy import slow_rule as R

R.AGES = (30, 45, 60)
R.DELAYS = (0, 1, 2, 5, 12)
R.SEL_D = 2
R.EXITS = ("czas_21s", "czas_60s")
R.EXIT_NAME = {"czas_21s": "stały 21 s (jak on)", "czas_60s": "stały 60 s"}
R.HORIZON = max(R.AGES) + max(R.DELAYS) + R.MAX_HOLD + 30
R.GRID = {"portfele": (10, 30, 60), "kup10": (5, 10, 16, 25), "zm": (None, 0.0, 0.3)}

if __name__ == "__main__":
    txt = R.report().replace('Reguła "przetrwał start" (z tradera Bot C)', "Reguła 21 s (z tradera Bot D)")
    (C.ROOT / "analizy" / "REGULA_21S.md").write_text(txt + "\n", encoding="utf-8")
    print(txt)
