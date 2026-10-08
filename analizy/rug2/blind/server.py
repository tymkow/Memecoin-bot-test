"""d) Ślepy test wizualny: lokalna strona z wykresem tokena od startu do chwili T (bez nazwy, bez dalszego przebiegu),
"kupić / nie kupić", odpowiedzi do analizy/rug2/blind/oceny.csv. Sesja = 25 losowych tokenów (stała losowa kolejność,
ocenione się nie powtarzają). Wyniki pozycji widać dopiero w raporcie (`python -m analizy.rug2.blind.report`) po >= 100
ocenach - strona ich nie pokazuje.

    python -m analizy.rug2.blind.server      # http://localhost:8765
"""
from __future__ import annotations

import csv
import json
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from analizy import common as C  # noqa: E402

CSV = HERE / "oceny.csv"
PORT = 8765
SESSION = 25
SEED = 20261007
LOCK = threading.Lock()


def build_pool() -> list[dict]:
    """Wszystkie migracje żywe w T (migracja + 30 min) z danymi od startu: krzywa ze zbieracza + świece po migracji."""
    import rug_dataset as rd
    s = rd.ro(rd.STREAM_DB)
    ents = C.migration_entries(30)
    pool = []
    for e in ents:
        T, c0 = e["ts"], e["created_ts"]
        pts, vol = [], {}
        for ts, vsol, vtok, sol in s.execute("SELECT ts, vsol, vtok, sol FROM trades WHERE mint_id=? AND ts <= ? "
                                             "AND ts < ? ORDER BY slot", (e["mint_id"], T, e["mig_ts"] + 1)):
            if vtok:
                pts.append([(ts - c0) / 60, float(vsol) / 1e9 / (float(vtok) / 1e6) * C.SOL_USD])
                k = int((ts - c0) // 60)
                vol[k] = vol.get(k, 0.0) + (sol or 0) / 1e9
        for t, o, h, l, cl, v in e["pre"]:
            if t + 60 <= T and t >= e["mig_ts"] - 60:
                m = (t - c0) / 60
                pts += [[m, o], [m + 0.33, h], [m + 0.66, l], [m + 0.99, cl]]
                vol[int(m)] = vol.get(int(m), 0.0) + v / C.SOL_USD
        if len(pts) < 5:
            continue
        if len(pts) > 1500:                                  # przerzedzenie: zostaw co n-ty punkt + ostatni
            step = len(pts) // 1500 + 1
            pts = pts[::step] + [pts[-1]]
        last = pts[-1][1] or 1.0
        pool.append({"mint": e["mint"], "pts": [[round(a, 3), b / last] for a, b in pts],
                     "vol": sorted([k, round(v, 3)] for k, v in vol.items()),
                     "mig": round((e["mig_ts"] - c0) / 60, 2), "T": round((T - c0) / 60, 2)})
    random.Random(SEED).shuffle(pool)
    return pool


def rated() -> set:
    if not CSV.exists():
        return set()
    with open(CSV, encoding="utf-8") as fh:
        return {r["mint"] for r in csv.DictReader(fh)}


class H(BaseHTTPRequestHandler):
    pool: list = []
    session_left = {"n": SESSION}

    def _send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            return self._send(200, (HERE / "index.html").read_text(encoding="utf-8"), "text/html")
        if self.path.startswith("/api/next"):
            done = rated()
            left = [i for i, p in enumerate(self.pool) if p["mint"] not in done]
            if self.session_left["n"] <= 0 or not left:
                return self._send(200, json.dumps({"end": True, "total": len(done), "pool": len(self.pool)}))
            i = left[0]
            p = self.pool[i]
            return self._send(200, json.dumps({"id": i, "pts": p["pts"], "vol": p["vol"], "mig": p["mig"], "T": p["T"],
                                               "done_session": SESSION - self.session_left["n"], "session": SESSION,
                                               "total": len(done), "pool": len(self.pool)}))
        if self.path.startswith("/api/new_session"):
            self.session_left["n"] = SESSION
            return self._send(200, json.dumps({"ok": True}))
        return self._send(404, "{}")

    def do_POST(self):
        if self.path.startswith("/api/rate"):
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            i, choice = int(d.get("id", -1)), d.get("choice")
            if not (0 <= i < len(self.pool)) or choice not in ("kupic_pewny", "kupic_niepewny", "nie"):
                return self._send(400, "{}")
            with LOCK:
                new = not CSV.exists()
                with open(CSV, "a", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    if new:
                        w.writerow(["ts", "mint", "choice", "seconds"])
                    w.writerow([round(time.time()), self.pool[i]["mint"], choice, d.get("seconds")])
                self.session_left["n"] -= 1
            return self._send(200, json.dumps({"ok": True}))
        return self._send(404, "{}")


def main():
    print("ładuję tokeny...", flush=True)
    H.pool = build_pool()
    print(f"pula: {len(H.pool)} tokenów, ocenionych: {len(rated())}. http://localhost:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()


if __name__ == "__main__":
    main()
