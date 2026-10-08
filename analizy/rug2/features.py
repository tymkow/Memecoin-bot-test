"""Cechy rug2 (wszystkie w chwili T, tylko dane sprzed T): a) historia twórcy, b) graf zasilania do K hopów,
c) zaufani twórcy (trusted_devs.yaml). Wejście: rekordy z pit.dataset()."""
from __future__ import annotations

import statistics
from pathlib import Path

from analizy import common as C
from analizy.rug2.pit import FundingGraph, LaunchIndex

K_MAX = 3
TRUSTED = Path(__file__).resolve().parent / "trusted_devs.yaml"


def add_dev(ents: list[dict], idx: LaunchIndex) -> None:
    for e in ents:
        e.update(idx.features(e.get("creator_addr"), e["created_ts"], e["T"]))


def _sets(g: FundingGraph, w: str, k: int, T: float) -> set:
    return {a for a in g.ancestors(w, k, T)[:k] if a}


def add_funding(ents: list[dict], g: FundingGraph) -> None:
    """Na każdy hop k = 1..3: udział pierwszych kupujących ze wspólnym przodkiem (z innym kupującym albo twórcą),
    powiązanie z twórcą, pokrycie (ilu kupujących ma znany łańcuch do k) i to, czy te same źródła zasilały
    WCZEŚNIEJSZE tokeny, których wynik był już znany w T (koniec ich okna 6 h przed T)."""
    for e in ents:
        T, fbs, cr = e["T"], e["fb_addrs"], e.get("creator_addr")
        for k in range(1, K_MAX + 1):
            anc = {w: _sets(g, w, k, T) | {w} for w in fbs}
            cra = (_sets(g, cr, k, T) | {cr}) if cr else set()
            shared = 0
            for w in fbs:
                others = set().union(*(anc[o] for o in fbs if o != w)) if len(fbs) > 1 else set()
                if anc[w] & (others | cra):
                    shared += 1
            n = len(fbs) or 1
            e[f"f{k}_shared"] = shared / n if fbs else None
            e[f"f{k}_creator_link"] = (sum(1 for w in fbs if anc[w] & cra) / n) if fbs and cr else None
            e[f"f{k}_cover"] = sum(1 for w in fbs if g.chain_known(w, k, T)) / n if fbs else None
            e[f"_src{k}"] = set().union(*anc.values(), cra) - set(fbs) - ({cr} if cr else set())
    by_t = sorted(ents, key=lambda e: e["T"])
    for i, e in enumerate(by_t):
        for k in range(1, K_MAX + 1):
            src = e[f"_src{k}"]
            prev = [p for p in by_t[:i] if p["T"] + C.H6 <= e["T"] and src & p[f"_src{k}"]]
            e[f"f{k}_src_prev_n"] = len(prev)
            e[f"f{k}_src_prev_s0"] = statistics.mean(p["s0"] for p in prev) if prev else None
    for e in ents:
        for k in range(1, K_MAX + 1):
            e.pop(f"_src{k}", None)


def read_trusted(path: Path = TRUSTED) -> set:
    """Minimalny czytnik: adresy z linii '- addr: ...' w sekcji 'trusted:' (bez zależności od pyyaml)."""
    if not path.exists():
        return set()
    out, sec = set(), None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0].rstrip()
        if not s.strip():
            continue
        if not s.startswith(" ") and s.endswith(":"):
            sec = s[:-1].strip()
        elif sec == "trusted" and s.strip().startswith("- addr:"):
            out.add(s.split(":", 1)[1].strip())
    return out


def add_trusted(ents: list[dict], trusted: set) -> None:
    for e in ents:
        e["dev_trusted"] = int(e.get("creator_addr") in trusted)
