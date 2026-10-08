"""Brak patrzenia w przyszłość: każda cecha rug2 policzona w chwili T nie może się zmienić od danych z po T.

    python -m pytest analizy/rug2/tests -q
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from analizy import common as C  # noqa: E402
from analizy.rug2 import features as FT  # noqa: E402
from analizy.rug2.pit import FundingGraph, LaunchIndex  # noqa: E402

T = 1_000_000.0
CREATED = T - 1800


def _index(extra_launches=(), extra_mig=None, extra_vol=None):
    launches = [("DEV", CREATED - 7200, "OLD1"), ("DEV", CREATED - 3600, "OLD2"), ("DEV", CREATED, "TOK")]
    launches += list(extra_launches)
    mig = {"OLD1": CREATED - 5000}
    mig.update(extra_mig or {})
    vol = {"OLD1": [(CREATED - 7000, 50.0)], "OLD2": [(CREATED - 3000, 3.0)]}
    for m, rows in (extra_vol or {}).items():
        vol[m] = sorted(vol.get(m, []) + rows)
    return LaunchIndex(launches, mig, vol)


def test_dev_features_ignore_future():
    base = _index().features("DEV", CREATED, T)
    assert base["dev_prev_n"] == 2 and base["dev_prev_mig_n"] == 1 and base["dev_prev_maxvol_sol"] == 50.0
    # start PO utworzeniu tokena (nawet przed T), migracja OLD2 PO T, wolumen PO T - nic się nie zmienia
    fut = _index(extra_launches=[("DEV", CREATED + 60, "NEW")], extra_mig={"OLD2": T + 10},
                 extra_vol={"OLD2": [(T + 5, 500.0)], "OLD1": [(T + 1, 900.0)]}).features("DEV", CREATED, T)
    assert fut == base
    # migracja OLD2 PRZED T już się liczy
    assert _index(extra_mig={"OLD2": T - 10}).features("DEV", CREATED, T)["dev_prev_mig_n"] == 2


def test_funding_graph_respects_T_and_hubs():
    rows = {"A": ("ok", "F1", T - 100), "F1": ("ok", "F2", T - 500), "F2": ("ok", "HUB", T - 900),
            "B": ("ok", "F1", T + 50),                     # zasilony PO T - nie istnieje w chwili T
            "C": ("ok", "HUB", T - 100), "HUB": ("aktywny", None, None)}
    g = FundingGraph(rows, hubs={"HUB"})
    assert g.ancestors("A", 3, T) == ["F1", "F2", None]   # hub przerywa łańcuch
    assert g.ancestors("B", 3, T) == [None, None, None]
    assert g.ancestors("C", 1, T) == [None]                 # przez hub nie łączymy
    assert g.chain_known("A", 3, T) and not g.chain_known("ZZZ", 1, T)


def _ent(i, t, fbs, s0):
    return {"T": t, "created_ts": t - 1800, "fb_addrs": fbs, "creator_addr": f"CR{i}", "s0": s0, "mint": f"M{i}"}


def test_source_history_uses_only_closed_earlier_tokens():
    rows = {"w1": ("ok", "SRC", 0.0), "w2": ("ok", "SRC", 0.0), "w3": ("ok", "SRC", 0.0)}
    g = FundingGraph(rows, hubs=set())
    early = _ent(1, T - C.H6 - 10, ["w1"], 0.5)          # okno 6 h zamknięte przed T -> wolno użyć wyniku
    late = _ent(2, T - 60, ["w2"], -0.9)                  # wcześniejszy, ale okno jeszcze otwarte -> NIE wolno
    cur = _ent(3, T, ["w3"], 0.0)
    ents = [early, late, cur]
    FT.add_funding(ents, g)
    assert cur["f1_src_prev_n"] == 1 and cur["f1_src_prev_s0"] == 0.5
    # wynik tokena z przyszłości nie wpływa na cechy wcześniejszego
    ents2 = copy.deepcopy([early, late, cur]) + [_ent(4, T + 3600, ["w1"], 9.9)]
    FT.add_funding(ents2, g)
    assert ents2[2]["f1_src_prev_s0"] == 0.5 and ents2[0]["f1_src_prev_n"] == 0


def test_trusted_reader(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text("trusted:\n  - addr: AAA  # ręcznie\n    note: x\nproposals:\n  - addr: BBB\n", encoding="utf-8")
    assert FT.read_trusted(p) == {"AAA"}
