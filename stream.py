"""Centralna warstwa strumieniowa: JEDNO połączenie WebSocket z PumpPortal (darmowe zdarzenia, bez klucza).

Zdarzenia:
  create  - nowy token na pump.fun (mint, twórca, symbol, początkowy zakup)  -> dane o historii twórców
  migrate - token ukończył krzywą bondingową i przeszedł na DEX (graduacja)   -> odkrywanie tokenów po graduacji

Zasady (z dokumentacji PumpPortal): jedno połączenie na cały proces, kolejne subskrypcje wysyłamy tym samym gniazdem;
otwieranie połączenia per token grozi banem. Strumienie transakcji per token są PŁATNE (SOL) - tu ich nie używamy.

Wątek tła tylko wrzuca zdarzenia do kolejki; cały zapis do bazy robi główny wątek (bot.py), więc SQLite jest bezpieczne.
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import time

try:
    import websockets
except ImportError:          # bot działa dalej, tylko bez strumienia
    websockets = None

URL = "wss://pumpportal.fun/api/data"
SUBSCRIPTIONS = ("subscribeNewToken", "subscribeMigration")      # oba darmowe


def normalize(msg: dict) -> dict | None:
    """Surowe zdarzenie -> {'type': 'create'|'migrate', ...} albo None (potwierdzenia subskrypcji, śmieci)."""
    kind = msg.get("txType")
    mint = msg.get("mint")
    if not mint:
        return None
    if kind == "create":
        return {"type": "create", "mint": mint, "creator": msg.get("traderPublicKey"), "symbol": msg.get("symbol"),
                "name": msg.get("name"), "initial_buy_sol": msg.get("solAmount"), "mcap_sol": msg.get("marketCapSol")}
    if kind == "migrate":
        return {"type": "migrate", "mint": mint, "pool": msg.get("pool")}
    return None


class PumpStream:
    def __init__(self, url: str = URL, subscriptions=SUBSCRIPTIONS, idle_timeout_s: int = 180):
        self.url, self.subscriptions, self.idle_timeout_s = url, subscriptions, idle_timeout_s
        self.q: queue.Queue = queue.Queue(maxsize=100_000)
        self.connected = False
        self.reconnects = 0
        self.received = 0
        self.dropped = 0
        self.last_event_ts = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def available(self) -> bool:
        return websockets is not None

    def start(self) -> bool:
        if not self.available:
            return False
        if self._thread is None:
            self._thread = threading.Thread(target=lambda: asyncio.run(self._run()), name="pumpstream", daemon=True)
            self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def drain(self, max_n: int = 50_000) -> list[dict]:
        out = []
        while len(out) < max_n:
            try:
                out.append(self.q.get_nowait())
            except queue.Empty:
                break
        return out

    def status(self) -> str:
        age = f"{time.time() - self.last_event_ts:.0f}s temu" if self.last_event_ts else "brak zdarzeń"
        return f"{'połączony' if self.connected else 'rozłączony'}, zdarzeń {self.received}, ostatnie {age}, reconnecty {self.reconnects}"

    async def _run(self):
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(self.url, open_timeout=15, ping_interval=20) as ws:
                    for method in self.subscriptions:
                        await ws.send(json.dumps({"method": method}))
                    self.connected, backoff = True, 1.0
                    while not self._stop.is_set():
                        raw = await asyncio.wait_for(ws.recv(), timeout=self.idle_timeout_s)
                        try:
                            ev = normalize(json.loads(raw))
                        except ValueError:
                            continue
                        if ev is None:
                            continue
                        self.received += 1
                        self.last_event_ts = time.time()
                        try:
                            self.q.put_nowait(ev)
                        except queue.Full:
                            self.dropped += 1
            except Exception:                      # rozłączenie, timeout bezczynności, błąd sieci - łączymy ponownie
                pass
            self.connected = False
            if self._stop.is_set():
                break
            self.reconnects += 1
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
