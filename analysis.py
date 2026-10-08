"""Ocena tokena: rug-pull, płynność, momentum, social, przepływ transakcji.

Zasada działania:
  * każdy test zwraca listę Finding (kategoria, punkty +/-, opis, ewentualne veto),
  * veto = twarde "NIE" niezależnie od wyniku (np. aktywny mint authority),
  * punkty składają się na wynik kategorii 0-100 (start 50), kategorie ważymy z Config.weights.

Dodanie nowego testu = jedna funkcja zwracająca Finding-i i wpięcie jej w evaluate_*().
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import features


# Które testy należą do osi OPPORTUNITY (czy jest okazja: momentum, kupujący, przepływ, smart money, wolumen).
# Wszystko inne to oś RISK (czy token jest groźny: holderzy, deweloper, klastry, bundle, głębokość/płynność, autentyczność).
OPPORTUNITY_TESTS = frozenset({
    "trend_1h", "zgodność_5m_1h", "dead_cat", "presja_kupna", "presja_sprzedaży", "wyprzedaż_5m",
    "przyspieszenie_wolumenu", "wygasanie_wolumenu", "spadek_5m", "spadek_1h", "parabola", "obrót24h",
    "transakcje_1h", "wolumen_1h", "cichnie", "unikalni_kupujący", "przepływ_netto", "smart_money",
    "smart_konwergencja", "przyspieszenie_kupujących", "wygasanie_kupujących", "nowi_kupujący", "trending",
})


@dataclass
class Finding:
    category: str            # safety | liquidity | momentum | social | flow
    name: str
    points: float = 0.0      # + = dobrze (więcej okazji / mniej ryzyka), - = źle
    detail: str = ""
    veto: bool = False
    retry: bool = False      # veto tymczasowe (np. za młody) - warto sprawdzić później
    permanent: bool = False  # veto dowodzące oszustwa - czarna lista

    @property
    def axis(self) -> str:
        return "opportunity" if self.name in OPPORTUNITY_TESTS else "risk"

    def __str__(self):
        tag = "VETO" if self.veto else f"{self.points:+.0f}"
        return f"[{self.category}] {self.name} ({tag}): {self.detail}"


@dataclass
class Verdict:
    decision: str                       # BUY | SKIP | WATCH | REJECT
    score: float                        # wynik łączny z wag kategorii (dawny; dla porównań wstecz)
    category_scores: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    opportunity: float = 50.0           # 0-100, wyżej = lepsza okazja
    risk: float = 50.0                  # 0-100, wyżej = groźniejszy token
    why: list = field(default_factory=list)   # wyjaśnienie decyzji (powody odrzucenia / niewejścia)

    @property
    def vetoes(self):
        return [f for f in self.findings if f.veto]

    def reasons(self, n=6) -> str:
        items = self.vetoes or sorted(self.findings, key=lambda f: -abs(f.points))
        return "; ".join(f"{f.name}: {f.detail}" for f in items[:n])

    def explain(self) -> str:
        """Czytelne uzasadnienie, np.:  Opportunity 84 | Risk 67 -> REJECT\n  - veto: ... \n  - ryzyko: ..."""
        head = f"Opportunity {self.opportunity:.0f} | Risk {self.risk:.0f} -> {self.decision}"
        return "\n".join([head] + [f"  - {w}" for w in self.why])


def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _get(d, *path, default=0.0):
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return default if d is None else d


# ============================================================ RUG / BEZPIECZEŃSTWO

def rug_checks(cfg, report: dict | None, rpc: dict | None = None) -> list[Finding]:
    """report = odpowiedź RugCheck /report; rpc = {'mint': info, 'holders': [...], 'supply': x} (zapas)."""
    out: list[Finding] = []
    S = "safety"

    if not report and not rpc:
        if cfg.require_rugcheck:
            out.append(Finding(S, "brak_audytu", veto=True, retry=True,
                               detail="RugCheck i RPC nie zwróciły danych - nie kupujemy w ciemno"))
        return out

    if report:
        token = report.get("token") or {}
        mint_auth = report.get("mintAuthority", token.get("mintAuthority"))
        freeze_auth = report.get("freezeAuthority", token.get("freezeAuthority"))
    else:  # zapas z RPC
        info = (rpc or {}).get("mint") or {}
        mint_auth, freeze_auth = info.get("mintAuthority"), info.get("freezeAuthority")

    # --- flaga "rugged" ---
    if report and report.get("rugged") and cfg.veto_if_rugged_flag:
        out.append(Finding(S, "rugged", veto=True, permanent=True, detail="RugCheck oznaczył token jako rugged"))

    # --- autorytety ---
    if mint_auth:
        out.append(Finding(S, "mint_authority", points=-30, veto=cfg.veto_mint_authority,
                           detail="dev może drukować nowe tokeny"))
    else:
        out.append(Finding(S, "mint_authority", points=+10, detail="zrzeczono się mint authority"))
    if freeze_auth:
        out.append(Finding(S, "freeze_authority", points=-30, veto=cfg.veto_freeze_authority,
                           detail="dev może zamrozić konta (honeypot)"))
    else:
        out.append(Finding(S, "freeze_authority", points=+10, detail="brak freeze authority"))

    if report:
        out += _rugcheck_details(cfg, report)
    else:
        out += _rpc_details(cfg, rpc)
    return out


def _rugcheck_details(cfg, r: dict) -> list[Finding]:
    out: list[Finding] = []
    S = "safety"
    markets = r.get("markets") or []
    pool_addrs = set()
    for m in markets:
        for k in ("pubkey", "liquidityA", "liquidityB", "mintLP"):
            if m.get(k):
                pool_addrs.add(m[k])

    # --- podatek transferu ---
    fee = _num(_get(r, "transferFee", "pct", default=0))
    if fee > cfg.max_transfer_fee_pct:
        out.append(Finding(S, "transfer_fee", veto=True, detail=f"podatek od transferu {fee:.1f}%"))
    elif fee > 0:
        out.append(Finding(S, "transfer_fee", points=-10, detail=f"podatek od transferu {fee:.1f}%"))

    # --- zablokowane LP (najlepszy market) ---
    locked = 0.0  # bierzemy największy market (wg płynności) - mała zablokowana pula nic nie znaczy
    if markets:
        main = max(markets, key=lambda m: _num(_get(m, "lp", "quoteUSD", default=0)) + _num(_get(m, "lp", "baseUSD", default=0)))
        locked = _num(_get(main, "lp", "lpLockedPct", default=0))
    if markets:
        if locked >= 90:
            out.append(Finding(S, "lp_locked", points=+15, detail=f"LP zablokowane/spalone w {locked:.0f}%"))
        elif locked >= 50:
            out.append(Finding(S, "lp_locked", points=+6, detail=f"LP zablokowane w {locked:.0f}%"))
        elif locked >= 10:
            out.append(Finding(S, "lp_locked", points=-8, detail=f"LP zablokowane tylko w {locked:.0f}%"))
        else:
            out.append(Finding(S, "lp_locked", points=-20, veto=cfg.min_lp_locked_pct > 0 and locked < cfg.min_lp_locked_pct,
                               detail=f"LP praktycznie niezablokowane ({locked:.0f}%) - dev może wycofać płynność"))

    # --- koncentracja holderów (bez pul) ---
    holders = [h for h in (r.get("topHolders") or [])
               if h.get("address") not in pool_addrs and h.get("owner") not in pool_addrs]
    pcts = sorted((_num(h.get("pct")) for h in holders), reverse=True)
    if pcts:
        top1, top10 = pcts[0], sum(pcts[:10])
        if top1 > cfg.max_top1_holder_pct:
            out.append(Finding(S, "top1_holder", veto=True, detail=f"jeden portfel trzyma {top1:.1f}%"))
        elif top1 > 10:
            out.append(Finding(S, "top1_holder", points=-10, detail=f"największy holder {top1:.1f}%"))
        elif top1 < 4:
            out.append(Finding(S, "top1_holder", points=+6, detail=f"największy holder tylko {top1:.1f}%"))
        if top10 > cfg.max_top10_holder_pct:
            out.append(Finding(S, "top10_holders", veto=True, detail=f"top10 trzyma {top10:.1f}%"))
        elif top10 > 40:
            out.append(Finding(S, "top10_holders", points=-12, detail=f"top10 trzyma {top10:.1f}%"))
        elif top10 < 25:
            out.append(Finding(S, "top10_holders", points=+8, detail=f"top10 trzyma {top10:.1f}%"))

    # --- insiderzy / klastry powiązanych portfeli (sniperzy, bundle) ---
    insiders = sum(1 for h in (r.get("topHolders") or []) if h.get("insider"))
    networks = r.get("insiderNetworks") or []
    if networks:
        size = sum(_num(n.get("size")) for n in networks if isinstance(n, dict))
        out.append(Finding(S, "insider_networks", points=-15 if size < 20 else -30,
                           veto=size >= 40, detail=f"{len(networks)} sieci powiązanych portfeli (~{size:.0f} kont)"))
    elif insiders >= 3:
        out.append(Finding(S, "insiderzy", points=-12, detail=f"{insiders} insiderów w top holderach"))

    # --- saldo twórcy ---
    supply = _num(_get(r, "token", "supply", default=0))
    cbal = _num(r.get("creatorBalance"))
    if supply > 0 and cbal > 0:
        cpct = cbal / supply * 100
        if cpct > cfg.max_creator_balance_pct:
            out.append(Finding(S, "creator_balance", veto=True, detail=f"twórca nadal trzyma {cpct:.1f}% podaży"))
        elif cpct > 5:
            out.append(Finding(S, "creator_balance", points=-8, detail=f"twórca trzyma {cpct:.1f}%"))

    # --- liczba dostawców LP ---
    lp_prov = r.get("totalLPProviders")
    if lp_prov is not None:
        if _num(lp_prov) <= 1:
            out.append(Finding(S, "lp_providers", points=-8, detail="płynność dostarcza 1 portfel"))
        elif _num(lp_prov) >= 5:
            out.append(Finding(S, "lp_providers", points=+4, detail=f"{int(_num(lp_prov))} dostawców LP"))

    # --- rozszerzenia Token-2022 (pułapki: permanent delegate = dev może zabrać tokeny z Twojego portfela) ---
    ext = r.get("token_extensions") or {}
    if isinstance(ext, dict):
        if ext.get("permanentDelegate"):
            out.append(Finding(S, "permanent_delegate", veto=True, permanent=True,
                               detail="permanentDelegate: dev może zabrać tokeny z dowolnego portfela"))
        if ext.get("nonTransferable"):
            out.append(Finding(S, "non_transferable", veto=True, permanent=True, detail="token nie do przesłania/sprzedaży"))
        if ext.get("transferHook"):
            out.append(Finding(S, "transfer_hook", points=-25, detail="transferHook: dowolny kod przy każdym transferze"))
        das = ext.get("defaultAccountState")
        if das and "frozen" in str(das).lower():
            out.append(Finding(S, "default_frozen", veto=True, permanent=True, detail="nowe konta domyślnie zamrożone"))

    # --- zmienne metadane ---
    if _get(r, "tokenMeta", "mutable", default=False):
        out.append(Finding(S, "mutable_metadata", points=-4, detail="metadane można zmienić"))

    # --- flagi RugChecka ---
    risks = r.get("risks") or []
    danger = [x for x in risks if str(x.get("level", "")).lower() == "danger"]
    warn = [x for x in risks if str(x.get("level", "")).lower() == "warn"]
    if len(danger) >= cfg.max_danger_risks:
        names = ", ".join(x.get("name", "?") for x in danger)
        out.append(Finding(S, "rugcheck_danger", veto=True, detail=f"{len(danger)} flag danger: {names}"))
    elif danger:
        out.append(Finding(S, "rugcheck_danger", points=-15, detail=danger[0].get("name", "danger")))
    if warn:
        out.append(Finding(S, "rugcheck_warn", points=-3 * min(len(warn), 4),
                           detail=", ".join(x.get("name", "?") for x in warn[:4])))
    norm = r.get("score_normalised")
    if norm is not None:
        norm = _num(norm)
        if norm > cfg.max_rugcheck_norm_score:
            out.append(Finding(S, "rugcheck_score", veto=True, detail=f"ryzyko RugCheck {norm:.0f}/100"))
        elif norm < 20:
            out.append(Finding(S, "rugcheck_score", points=+8, detail=f"ryzyko RugCheck {norm:.0f}/100"))
    return out


def _rpc_details(cfg, rpc: dict) -> list[Finding]:
    """Uboższa analiza z samego RPC: koncentracja z getTokenLargestAccounts."""
    out: list[Finding] = []
    holders, supply = (rpc or {}).get("holders"), (rpc or {}).get("supply")
    if holders and supply:
        pcts = sorted((_num(h.get("uiAmount")) / supply * 100 for h in holders), reverse=True)
        # największe konta to zwykle pula AMM - pomijamy najwyższe jeśli >30% (nie wiemy, czy to LP)
        top10 = sum(pcts[1:11])
        if top10 > cfg.max_top10_holder_pct:
            out.append(Finding("safety", "top10_holders", veto=True, detail=f"top10 (bez największego) {top10:.1f}%"))
        out.append(Finding("safety", "rpc_only", points=-10, detail="audyt tylko z RPC (bez LP/insiderów)"))
    return out


# ============================================================ RYNEK (DexScreener)

def _age_minutes(pair) -> float | None:
    ts = pair.get("pairCreatedAt")
    return (time.time() * 1000 - ts) / 60000 if ts else None


def est_slippage_pct(size_usd: float, liq_usd: float) -> float:
    """Model x*y=k: kupno za size_usd w puli z płynnością liq_usd (połowa to strona quote)."""
    r = max(liq_usd / 2, 1.0)
    return size_usd / (r + size_usd) * 100


def market_checks(cfg, pair: dict, planned_size_usd: float, imposter_pairs: list[dict] | None = None) -> list[Finding]:
    out: list[Finding] = []
    liq = _num(_get(pair, "liquidity", "usd"))
    fdv = _num(pair.get("fdv"))
    mcap = _num(pair.get("marketCap")) or fdv
    v24, v6, v1, v5 = (_num(_get(pair, "volume", k)) for k in ("h24", "h6", "h1", "m5"))
    tx = pair.get("txns") or {}
    b1, s1 = _num(_get(tx, "h1", "buys")), _num(_get(tx, "h1", "sells"))
    b5, s5 = _num(_get(tx, "m5", "buys")), _num(_get(tx, "m5", "sells"))
    b24, s24 = _num(_get(tx, "h24", "buys")), _num(_get(tx, "h24", "sells"))
    ch5, ch1, ch6, ch24 = (_num(_get(pair, "priceChange", k)) for k in ("m5", "h1", "h6", "h24"))
    age = _age_minutes(pair)
    quote = str(_get(pair, "quoteToken", "symbol", default="")).upper()
    dex = str(pair.get("dexId", "")).lower()

    # ---------------- płynność ----------------
    L = "liquidity"
    if liq < cfg.min_liquidity_usd:
        out.append(Finding(L, "płynność", veto=True, retry=True, detail=f"${liq:,.0f} < ${cfg.min_liquidity_usd:,.0f}"))
    elif liq >= 100_000:
        out.append(Finding(L, "płynność", points=+20, detail=f"${liq:,.0f}"))
    elif liq >= 40_000:
        out.append(Finding(L, "płynność", points=+12, detail=f"${liq:,.0f}"))
    else:
        out.append(Finding(L, "płynność", points=+3, detail=f"${liq:,.0f}"))

    if mcap:
        if mcap > cfg.max_mcap_usd:
            out.append(Finding(L, "mcap", veto=True, detail=f"${mcap:,.0f} za duży na memecoin z potencjałem"))
        elif mcap < cfg.min_mcap_usd:
            out.append(Finding(L, "mcap", veto=True, retry=True, detail=f"${mcap:,.0f} za mały"))
        if liq > 0:
            ratio = mcap / liq
            if ratio > cfg.max_fdv_to_liq:
                out.append(Finding(L, "mcap_do_płynności", veto=True,
                                   detail=f"{ratio:.0f}x - cienka pula pod dużą wyceną (łatwa do zrzutu)"))
            elif ratio > 60:
                out.append(Finding(L, "mcap_do_płynności", points=-10, detail=f"{ratio:.0f}x"))
            elif ratio < 15:
                out.append(Finding(L, "mcap_do_płynności", points=+8, detail=f"{ratio:.0f}x"))

    if liq > 0 and v24 > 0:
        turn = v24 / liq
        if turn > cfg.max_turnover_h24:
            out.append(Finding(L, "obrót24h", points=-15, veto=True,
                               detail=f"{turn:.0f}x płynności - podejrzenie wash tradingu"))
        elif 3 <= turn <= 30:
            out.append(Finding(L, "obrót24h", points=+6, detail=f"{turn:.1f}x płynności"))

    slip = est_slippage_pct(planned_size_usd, liq) if liq else 100
    if slip > cfg.max_slippage_pct:
        out.append(Finding(L, "slippage", veto=True, retry=True, detail=f"szac. {slip:.1f}% dla ${planned_size_usd:,.0f}"))
    else:
        out.append(Finding(L, "slippage", points=+4 if slip < 1 else 0, detail=f"szac. {slip:.2f}%"))

    if quote and quote not in cfg.allowed_quote_symbols:
        out.append(Finding(L, "quote", points=-15, veto=True,
                           detail=f"para do {quote} - egzotyczny token kwotowany, trudno wyjść"))
    if dex and dex not in cfg.allowed_dexes:
        out.append(Finding(L, "dex", points=-8, detail=f"nieznany DEX '{dex}'"))
    if dex == "pumpfun":
        out.append(Finding(L, "bonding_curve", points=-6, detail="jeszcze na krzywej pump.fun (przed migracją)"))

    # ---------------- wiek ----------------
    if age is None:
        out.append(Finding(L, "wiek", points=-5, detail="brak daty utworzenia pary"))
    elif age < cfg.min_age_minutes:
        out.append(Finding(L, "wiek", veto=True, retry=True, detail=f"{age:.0f} min - faza snajperów"))
    elif age > cfg.max_age_hours * 60:
        out.append(Finding(L, "wiek", veto=True, detail=f"{age/60:.0f} h - już nie świeży mem"))
    elif age < 180:
        out.append(Finding(L, "wiek", points=+4, detail=f"{age:.0f} min"))

    # ---------------- momentum ----------------
    M = "momentum"
    if ch5 <= cfg.max_m5_drop_pct:
        out.append(Finding(M, "spadek_5m", veto=True, retry=True, detail=f"{ch5:+.1f}% w 5 min (spadający nóż)"))
    if ch1 <= cfg.max_h1_drop_pct:
        out.append(Finding(M, "spadek_1h", veto=True, retry=True, detail=f"{ch1:+.1f}% w 1h"))
    if ch1 >= cfg.max_h1_pump_pct or ch24 >= cfg.max_h24_pump_pct:
        out.append(Finding(M, "parabola", veto=True, retry=True,
                           detail=f"+{ch1:.0f}% 1h / +{ch24:.0f}% 24h - kupowanie szczytu"))
    elif 5 <= ch1 <= 40:
        out.append(Finding(M, "trend_1h", points=+14, detail=f"{ch1:+.0f}% w 1h (zdrowy wzrost)"))
    elif 40 < ch1 < cfg.max_h1_pump_pct:
        out.append(Finding(M, "trend_1h", points=-6, detail=f"{ch1:+.0f}% w 1h (przegrzane)"))
    elif -10 < ch1 < 5:
        out.append(Finding(M, "trend_1h", points=0, detail=f"{ch1:+.0f}% w 1h (boczniak)"))
    else:
        out.append(Finding(M, "trend_1h", points=-10, detail=f"{ch1:+.0f}% w 1h"))

    if ch5 > 0 and ch1 > 0:
        out.append(Finding(M, "zgodność_5m_1h", points=+8, detail="wzrost na obu przedziałach"))
    if ch6 < -30 and ch1 > 20:
        out.append(Finding(M, "dead_cat", points=-10, detail=f"6h {ch6:+.0f}%, odbicie 1h {ch1:+.0f}% - możliwy martwy kot"))

    def pressure(b, s):
        return b / (b + s) if (b + s) else 0.5
    p1, p5, p24 = pressure(b1, s1), pressure(b5, s5), pressure(b24, s24)
    if p1 >= 0.55 and p5 >= 0.5:
        out.append(Finding(M, "presja_kupna", points=+12, detail=f"kupujący {p1:.0%} (1h), {p5:.0%} (5m)"))
    elif p1 < cfg.min_buy_pressure_h1 and (b1 + s1) >= 50:
        out.append(Finding(M, "presja_sprzedaży", veto=True, retry=True, points=-12,
                           detail=f"kupujący tylko {p1:.0%} (1h) - wyprzedaż"))
    elif p1 < 0.45:
        out.append(Finding(M, "presja_sprzedaży", points=-12, detail=f"kupujący tylko {p1:.0%} (1h)"))
    if p5 < 0.35 and (b5 + s5) >= 10:
        out.append(Finding(M, "wyprzedaż_5m", points=-10, detail=f"kupujący {p5:.0%} w 5 min"))

    if v1 > 0 and v6 > 0:
        accel = v1 / (v6 / 6)  # wolumen ostatniej godziny vs średnia godzinowa z 6h
        if accel >= 1.5:
            out.append(Finding(M, "przyspieszenie_wolumenu", points=+8, detail=f"{accel:.1f}x średniej 6h"))
        elif accel < 0.4:
            out.append(Finding(M, "wygasanie_wolumenu", points=-10, detail=f"{accel:.1f}x średniej 6h"))

    # ---------------- przepływ transakcji ----------------
    F = "flow"
    n1 = b1 + s1
    if n1 < cfg.min_txns_h1:
        out.append(Finding(F, "transakcje_1h", veto=True, retry=True, detail=f"{n1:.0f} < {cfg.min_txns_h1}"))
    elif n1 >= 400:
        out.append(Finding(F, "transakcje_1h", points=+15, detail=f"{n1:.0f}"))
    else:
        out.append(Finding(F, "transakcje_1h", points=+5, detail=f"{n1:.0f}"))
    if v1 < cfg.min_volume_h1_usd:
        out.append(Finding(F, "wolumen_1h", veto=True, retry=True, detail=f"${v1:,.0f} < ${cfg.min_volume_h1_usd:,.0f}"))
    if n1:
        avg = v1 / n1
        if avg < 8:
            out.append(Finding(F, "śr_transakcja", points=-10, detail=f"${avg:.1f} - drobnica/boty"))
        elif avg > 800 and liq < 100_000:
            out.append(Finding(F, "śr_transakcja", points=-8, detail=f"${avg:.0f} - dominują wieloryby"))
    # wash trading: idealna równowaga kupno/sprzedaż + duży obrót
    if n1 >= 100 and abs(b1 - s1) / n1 < 0.03 and liq and v1 / liq > 2:
        out.append(Finding(F, "wash_trading", points=-15, detail="niemal idealnie 50/50 przy dużym obrocie"))
    # duszenie aktywności: 5m znacznie poniżej średniej godzinowej
    if n1 and (b5 + s5) < (n1 / 12) * 0.25:
        out.append(Finding(F, "cichnie", points=-8, detail="ostatnie 5 min << średnia godzinowa"))

    # ---------------- social / autentyczność ----------------
    C = "social"
    info = pair.get("info") or {}
    socials = {str(x.get("type", "")).lower() for x in (info.get("socials") or [])}
    sites = info.get("websites") or []
    have = int(bool(sites)) + int("twitter" in socials) + int("telegram" in socials)
    if have >= 3:
        out.append(Finding(C, "social", points=+22, detail="strona + X + Telegram"))
    elif have == 2:
        out.append(Finding(C, "social", points=+12, detail="dwa kanały social"))
    elif have == 1:
        out.append(Finding(C, "social", points=+2, detail="jeden kanał social"))
    else:
        out.append(Finding(C, "social", points=-20, detail="brak jakichkolwiek linków"))
    if not info.get("imageUrl"):
        out.append(Finding(C, "grafika", points=-5, detail="brak profilu na DexScreener"))
    boosts = _num(_get(pair, "boosts", "active"))
    if boosts >= 50:
        out.append(Finding(C, "boosty", points=-6, detail=f"{boosts:.0f} płatnych boostów (reklama = często dump)"))

    if imposter_pairs is not None:
        me = (pair.get("baseToken") or {}).get("address")
        sym = str(_get(pair, "baseToken", "symbol", default="")).upper()
        clones = [p for p in imposter_pairs
                  if (p.get("baseToken") or {}).get("address") != me
                  and str((p.get("baseToken") or {}).get("symbol", "")).upper() == sym]
        stronger = [p for p in clones if _num(_get(p, "liquidity", "usd")) > liq * 1.5]
        older = [p for p in clones if (_age_minutes(p) or 0) > (age or 0) * 2 and _num(_get(p, "liquidity", "usd")) > liq * 0.3]
        if stronger or older:
            out.append(Finding(C, "imposter", points=-25, veto=len(stronger) >= 1 and len(older) >= 1,
                               detail=f"istnieje {len(clones)} tokenów o symbolu {sym}, w tym silniejszy/starszy - możliwy klon"))
        elif len(clones) >= 5:
            out.append(Finding(C, "imposter", points=-8, detail=f"{len(clones)} tokenów o tym samym symbolu"))
    return out


# ============================================================ TWÓRCA / LISTA RUGÓW

def creator_checks(cfg, wallets: list[str], bad_wallets: set[str]) -> list[Finding]:
    """Twórca (deployer) z naszej samouczącej się listy rugów = veto. Lista rośnie, gdy bot łapie rug."""
    hit = [w for w in wallets if w and w in bad_wallets]
    if hit and cfg.bad_wallet_veto:
        return [Finding("safety", "seryjny_rugger", veto=True, permanent=True,
                        detail=f"portfel {hit[0][:6]}... stał za wcześniejszym rugiem")]
    return []


def creator_history_checks(cfg, hist: dict | None) -> list[Finding]:
    """Historia twórcy z NASZEGO strumienia PumpPortal (kto ile tokenów wypuścił i ile się wygraduowało)."""
    if not hist or not hist.get("launches"):
        return []
    n24, n, grad = hist.get("launches_24h", 0), hist["launches"], hist.get("graduated", 0)
    if n24 >= cfg.serial_launcher_veto_24h:
        return [Finding("safety", "seryjny_launcher", veto=True,
                        detail=f"twórca wypuścił {n24} tokenów w 24 h (farma tokenów)")]
    if n24 >= cfg.serial_launcher_24h:
        return [Finding("safety", "seryjny_launcher", points=-12, detail=f"twórca wypuścił {n24} tokenów w 24 h")]
    if grad >= 1:
        return [Finding("safety", "historia_twórcy", points=+3, detail=f"{grad} z {n} poprzednich tokenów twórcy się wygraduowało")]
    return []


def smart_checks(cfg, conv: dict | None) -> list[Finding]:
    """Konwergencja: kilku niezależnych, dobrze ocenianych portfeli z naszego rankingu kupuje ten sam token."""
    if not conv or not conv.get("smart_wallets_n"):
        return []
    n = conv["smart_wallets_n"]
    if n >= 3:
        pts = +22
    elif n >= cfg.smart_min_wallets:
        pts = +15
    else:
        pts = +4
    return [Finding("momentum", "smart_konwergencja", points=pts,
                    detail=f"{n} śledzonych portfeli kupuje (suma jakości {conv.get('smart_quality_sum', 0):.2f})")]


# ============================================================ HONEYPOT (Jupiter)

def honeypot_checks(cfg, buy, sell, size_usd: float, dex_price: float, decimals: int | None) -> list[Finding]:
    """buy/sell = (stan, dane) z Jupiter.quote. Test: czy istnieje trasa sprzedaży i ile kosztuje kupno+sprzedaż."""
    S = "safety"
    if buy is None:
        return []
    state, b = buy
    if state == "error":
        return [Finding(S, "jupiter", points=-3, veto=cfg.require_jupiter, retry=True,
                        detail="Jupiter nie odpowiedział - nie potwierdzono trasy sprzedaży")]
    if state == "noroute":
        return [Finding(S, "trasa_kupna", veto=True, retry=True, detail="Jupiter nie widzi trasy kupna (za wcześnie?)")]
    out: list[Finding] = []
    if sell is None or sell[0] == "error":
        return [Finding(S, "jupiter", points=-3, veto=cfg.require_jupiter, retry=True,
                        detail="nie udało się zweryfikować sprzedaży")]
    if sell[0] == "noroute":
        return [Finding(S, "honeypot", veto=True, permanent=True,
                        detail="da się kupić, ale Jupiter nie znajduje trasy SPRZEDAŻY")]
    back_usd = float(sell[1]["outAmount"]) / 1e6
    loss = (1 - back_usd / size_usd) * 100 if size_usd else 100
    if loss > cfg.max_roundtrip_loss_pct:
        out.append(Finding(S, "koszt_round_trip", veto=True,
                           detail=f"kupno+sprzedaż od razu = -{loss:.1f}% (podatek/cienka pula)"))
    else:
        out.append(Finding(S, "koszt_round_trip", points=+8 if loss < 3 else 0, detail=f"-{loss:.1f}%"))
    if decimals is not None and dex_price > 0:
        tokens = float(b["outAmount"]) / 10 ** decimals
        if tokens > 0:
            jup_price = size_usd / tokens
            diff = abs(jup_price / dex_price - 1) * 100
            if diff > cfg.max_price_mismatch_pct:
                out.append(Finding(S, "cena_jupiter", veto=True, retry=True,
                                   detail=f"Jupiter {jup_price:.4g} vs DexScreener {dex_price:.4g} ({diff:.0f}% różnicy)"))
    return out


# ============================================================ GECKOTERMINAL (holderzy, trendy, transakcje)

def gecko_checks(cfg, info: dict | None, trending_rank: int | None) -> list[Finding]:
    out: list[Finding] = []
    if trending_rank is not None:
        out.append(Finding("momentum", "trending", points=+8 if trending_rank < 10 else +4,
                           detail=f"#{trending_rank + 1} w trendach GeckoTerminal (1h)"))
    if not info:
        return out
    S = "safety"
    if str(info.get("is_honeypot", "")).lower() == "yes":
        out.append(Finding(S, "honeypot_gt", veto=True, permanent=True, detail="GeckoTerminal oznacza token jako honeypot"))
    if str(info.get("mint_authority", "")).lower() == "yes":
        out.append(Finding(S, "mint_authority_gt", veto=cfg.veto_mint_authority, points=-20,
                           detail="GeckoTerminal: aktywny mint authority"))
    if str(info.get("freeze_authority", "")).lower() == "yes":
        out.append(Finding(S, "freeze_authority_gt", veto=cfg.veto_freeze_authority, points=-20,
                           detail="GeckoTerminal: aktywny freeze authority"))
    dev = _num(info.get("developer_holding_percentage"))
    if dev > cfg.max_creator_balance_pct:
        out.append(Finding(S, "dev_holding", veto=True, detail=f"deweloper trzyma {dev:.1f}%"))
    elif dev > 5:
        out.append(Finding(S, "dev_holding", points=-8, detail=f"deweloper trzyma {dev:.1f}%"))
    holders = info.get("holders") or {}
    n = _num(holders.get("count"))
    if n:
        if n < cfg.min_holders:
            out.append(Finding(S, "holderzy", points=-12, detail=f"tylko {n:.0f} holderów"))
        elif n >= 1000:
            out.append(Finding(S, "holderzy", points=+10, detail=f"{n:.0f} holderów"))
        elif n >= 300:
            out.append(Finding(S, "holderzy", points=+4, detail=f"{n:.0f} holderów"))
    top10 = _num(_get(holders, "distribution_percentage", "top_10"))
    if top10 > cfg.max_top10_holder_pct + 15:
        out.append(Finding(S, "top10_gt", points=-10, detail=f"GeckoTerminal: top10 = {top10:.0f}%"))
    gt = info.get("gt_score")
    if gt is not None:
        gt = _num(gt)
        if gt >= 60:
            out.append(Finding("social", "gt_score", points=+8, detail=f"gt_score {gt:.0f}"))
        elif gt < 30:
            out.append(Finding("social", "gt_score", points=-8, detail=f"gt_score {gt:.0f}"))
    if info.get("gt_verified"):
        out.append(Finding("social", "gt_verified", points=+6, detail="zweryfikowany przez GeckoTerminal"))
    return out


def trade_checks(cfg, trades: list[dict], liq_usd: float) -> list[Finding]:
    """Analiza ostatnich ~300 transakcji puli: boty, wash trading, wieloryby, 'smart money'."""
    F = "flow"
    if len(trades) < 40:
        return []
    vol: dict[str, float] = {}
    buys: dict[str, int] = {}
    sells: dict[str, int] = {}
    buy_usd = sell_usd = biggest_sell = 0.0
    for t in trades:
        w, usd = t.get("tx_from_address"), _num(t.get("volume_in_usd"))
        if not w:
            continue
        vol[w] = vol.get(w, 0) + usd
        if t.get("kind") == "buy":
            buys[w] = buys.get(w, 0) + 1
            buy_usd += usd
        else:
            sells[w] = sells.get(w, 0) + 1
            sell_usd += usd
            biggest_sell = max(biggest_sell, usd)
    total = sum(vol.values()) or 1.0
    out: list[Finding] = []

    top3 = sum(sorted(vol.values(), reverse=True)[:3]) / total * 100
    if top3 > cfg.trades_top3_veto_pct:
        out.append(Finding(F, "top3_portfele", veto=True, detail=f"3 portfele robią {top3:.0f}% wolumenu (boty/wash)"))
    elif top3 > cfg.trades_top3_warn_pct:
        out.append(Finding(F, "top3_portfele", points=-12, detail=f"3 portfele robią {top3:.0f}% wolumenu"))
    else:
        out.append(Finding(F, "top3_portfele", points=+6, detail=f"3 portfele robią {top3:.0f}% wolumenu"))

    wash = sum(vol[w] for w in vol if buys.get(w, 0) >= 4 and sells.get(w, 0) >= 4) / total * 100
    if wash > cfg.trades_wash_wallet_pct:
        out.append(Finding(F, "wash_portfele", points=-12, detail=f"{wash:.0f}% wolumenu od portfeli kupujących i sprzedających na zmianę"))

    uniq_buyers = len(buys)
    if uniq_buyers >= 40:
        out.append(Finding(F, "unikalni_kupujący", points=+8, detail=f"{uniq_buyers} unikalnych kupujących w ostatnich {len(trades)} transakcjach"))
    elif uniq_buyers < 15:
        out.append(Finding(F, "unikalni_kupujący", points=-12, detail=f"tylko {uniq_buyers} unikalnych kupujących"))

    if buy_usd + sell_usd > 0:
        net = (buy_usd - sell_usd) / (buy_usd + sell_usd)
        if net > 0.15:
            out.append(Finding("momentum", "przepływ_netto", points=+8, detail=f"kupno przeważa o {net:.0%} (USD)"))
        elif net < -0.15:
            out.append(Finding("momentum", "przepływ_netto", points=-10, detail=f"sprzedaż przeważa o {-net:.0%} (USD)"))

    if liq_usd and biggest_sell > liq_usd * cfg.whale_sell_pct_of_liq / 100:
        out.append(Finding(F, "wieloryb_sprzedaje", points=-10,
                           detail=f"pojedyncza sprzedaż ${biggest_sell:,.0f} ({biggest_sell / liq_usd:.1%} płynności)"))

    # --- unikalni kupujący w czasie i skoordynowane zakupy w jednym bloku (sygnały wyjaśnialne, nie wyroki) ---
    tm = features.trade_metrics(trades)
    if tm:
        if tm["ub_60s"] >= 8 and tm["buyer_accel"] >= 1.5:
            out.append(Finding(F, "przyspieszenie_kupujących", points=+10,
                               detail=f"{tm['ub_60s']} unikalnych kupujących w ostatnich 60 s, tempo {tm['buyer_accel']:.1f}x wcześniejszego"))
        elif tm["ub_180s"] >= 10 and tm["buyer_accel"] < 0.5:
            out.append(Finding(F, "wygasanie_kupujących", points=-8,
                               detail=f"tempo nowych kupujących spadło do {tm['buyer_accel']:.1f}x"))
        if tm["new_buyer_ratio"] >= 0.6 and tm["ub_180s"] >= 10:
            out.append(Finding(F, "nowi_kupujący", points=+4, detail=f"{tm['new_buyer_ratio']:.0%} kupujących z ostatnich 3 min to nowe portfele"))
        share = tm["same_block_buy_share"]
        if share > 0.6:
            out.append(Finding(F, "skoordynowane_bloki", points=-20,
                               detail=f"{share:.0%} wolumenu kupna to bloki z >=3 portfelami naraz (do {tm['same_block_max_wallets']})"))
        elif share > 0.35:
            out.append(Finding(F, "skoordynowane_bloki", points=-10,
                               detail=f"{share:.0%} wolumenu kupna w blokach z >=3 portfelami (do {tm['same_block_max_wallets']})"))

    smart = [w for w in cfg.smart_wallets if w in buys]
    if smart:
        out.append(Finding("momentum", "smart_money", points=+15, detail=f"kupują obserwowane portfele ({len(smart)})"))
    return out


# ============================================================ DECYZJA

def decide(cfg, findings: list[Finding], mint: str = "") -> Verdict:
    cats: dict[str, float] = {}
    for f in findings:
        cats[f.category] = cats.get(f.category, 50.0) + f.points
    cats = {k: max(0.0, min(100.0, v)) for k, v in cats.items()}
    wsum = sum(cfg.weights.get(k, 0) for k in cats) or 1.0
    score = sum(v * cfg.weights.get(k, 0) for k, v in cats.items()) / wsum

    # dwie niezależne osie: okazja (więcej punktów = lepiej) i ryzyko (punkty "dobre" obniżają ryzyko)
    # tanh zamiast przycinania do 0-100: dobre tokeny nie lądują wszystkie na 100 (nasycenie ukrywało różnice)
    s = cfg.axis_scale
    opp = 50.0 + 50.0 * math.tanh(sum(f.points for f in findings if f.axis == "opportunity") / s)
    risk = 50.0 - 50.0 * math.tanh(sum(f.points for f in findings if f.axis == "risk") / s)

    def verdict(decision, why):
        return Verdict(decision, score, cats, findings, opp, risk, why)

    def culprits(axis, sign, n=3):
        """Testy, które najbardziej zepsuły daną oś (sign=-1: punkty ujemne)."""
        bad = sorted((f for f in findings if f.axis == axis and f.points * sign > 0 and not f.veto),
                     key=lambda f: -abs(f.points))
        return [f"{f.name}: {f.detail} ({f.points:+.0f})" for f in bad[:n]]

    vetoes = [f for f in findings if f.veto]
    if mint and mint in cfg.whitelist_mints:  # whitelist zdejmuje tylko veto rynkowe
        vetoes = [f for f in vetoes if f.category == "safety"]
    if vetoes:
        why = [f"VETO {'(tymczasowe)' if f.retry else '(trwałe)' if f.permanent else ''} {f.name}: {f.detail}".replace("  ", " ")
               for f in vetoes]
        return verdict("WATCH" if all(f.retry for f in vetoes) else "REJECT", why)

    why = []
    if opp < cfg.opportunity_min:
        why.append(f"za mała okazja: Opportunity {opp:.0f} < {cfg.opportunity_min:.0f}")
        why += [f"okazja - {c}" for c in culprits("opportunity", -1)]
    if risk > cfg.risk_max:
        why.append(f"za duże ryzyko: Risk {risk:.0f} > {cfg.risk_max:.0f}")
        why += [f"ryzyko - {c}" for c in culprits("risk", -1)]
    for cat, minimum in cfg.min_category_scores.items():
        if cat in cats and cats[cat] < minimum:
            findings.append(Finding(cat, "bramka", detail=f"{cat} = {cats[cat]:.0f} < minimum {minimum:.0f}"))
            why.append(f"bramka kategorii: {cat} = {cats[cat]:.0f} < {minimum:.0f}")
    if why:
        return verdict("SKIP", why)
    return verdict("BUY", [f"Opportunity {opp:.0f} >= {cfg.opportunity_min:.0f} i Risk {risk:.0f} <= {cfg.risk_max:.0f}, brak veto"])
