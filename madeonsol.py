"""MadeOnSol (madeonsol.com/developer) - darmowy plan: 200 zapytań/dzień, kanały na żywo z 5 min opóźnieniem.
Klucz: zmienna środowiskowa MADEONSOL_API_KEY albo plik secrets.json (poza gitem).

    python madeonsol.py            # odśwież listę znanych traderów (KOL) i ranking 7d/30d - 3 zapytania, raz dziennie

Odpowiedzi trzymamy w data/madeonsol/*.json, żeby analizy nie zużywały limitu.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

BASE = Path(__file__).parent
API = "https://madeonsol.com/api/v1"
CACHE = BASE / "data" / "madeonsol"


def api_key() -> str | None:
    key = os.environ.get("MADEONSOL_API_KEY")
    if not key and (BASE / "secrets.json").exists():
        key = json.loads((BASE / "secrets.json").read_text(encoding="utf-8")).get("MADEONSOL_API_KEY")
    return key or None


def get(path: str, params: dict | None = None) -> dict | None:
    key = api_key()
    if not key:
        return None
    r = requests.get(API + path, params=params, timeout=30,
                     headers={"Authorization": f"Bearer {key}", "User-Agent": "memecoin-paper-bot/research"})
    if r.status_code != 200:
        print(f"MadeOnSol {path}: HTTP {r.status_code} {r.text[:200]}")
        return None
    left = r.headers.get("x-ratelimit-remaining")
    if left is not None and int(left) < 20:
        print(f"MadeOnSol: zostało {left} zapytań na dziś")
    return r.json()


def refresh() -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, path, params in (("wallets", "/kol/wallets", None), ("leaderboard_7d", "/kol/leaderboard", {"period": "7d"}),
                               ("leaderboard_30d", "/kol/leaderboard", {"period": "30d"})):
        data = get(path, params)
        if data is not None:
            (CACHE / f"{name}.json").write_text(json.dumps({"fetched": time.time(), "data": data}), encoding="utf-8")
            out[name] = data
    return out


def cached(name: str) -> list:
    p = CACHE / f"{name}.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))["data"]
    return d.get("wallets") or d.get("leaderboard") or []


def kol_leaders(min_hold_min: float = 1.0) -> dict:
    """Portfele z rankingów 7d i 30d z zyskiem, które da się kopiować (mediana trzymania >= min_hold_min).
    Zwraca {adres: opis}."""
    out = {}
    for name in ("leaderboard_7d", "leaderboard_30d"):
        for e in cached(name):
            hold = e.get("median_hold_minutes_30d")
            if (e.get("pnl") or 0) > 0 and hold is not None and hold >= min_hold_min:
                out[e["wallet"]] = f"{e.get('name')} ({e.get('auto_strategy_tag')}, trzyma ~{hold:.0f} min)"
    return out


if __name__ == "__main__":
    got = refresh()
    print({k: len(v.get("wallets") or v.get("leaderboard") or []) for k, v in got.items()})
    print(f"kopiowalnych z rankingów (trzymanie >= 1 min, zysk): {len(kol_leaders())}")
