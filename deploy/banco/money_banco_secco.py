#!/usr/bin/env python3
"""Money — banco di prova a secco (implementa docs/02_banco_di_prova_a_secco.md).

Legge il conto (trading + funding, entrambi), calcola l'equity in EUR, applica
la guardia di capitale, calcola l'ordine che SAREBBE inviato e riconcilia.
**Nessun ordine viene inviato**: nel codice l'invio e' assente, non disattivato
da un flag — `deploy/tests/test_no_order_calls.py` lo verifica staticamente e
la CI esegue il test a ogni push.

Uscite: 0 ok · 2 NON_FINANZIATO/NON_FATTIBILE · 3 autenticazione ·
4 permessi o IP non in whitelist · 5 chiave non read-only (solo con
BANCO_RICHIEDI_READ_ONLY=1) · 1 altro errore.

La riga `METRICA ...` (stdout, piu' file health e jsonl) risponde alle 5
domande di docs/02 §6 leggendo solo il log.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

HOSTNAME_EU = "eea.okx.com"
TARIFFA_ASSUNTA = "okx_eea_spot"
#: Pedaggio di giro misto spot OKX EEA, misurato il 25/09 (0,550%). Costante
#: integrata: vale quando money.costi non e' importabile sul nodo del banco.
PEDAGGIO_FALLBACK_PCT = 0.550


def _ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


# --- logica pura (testata da deploy/tests/test_banco_logic.py) ---------------------

def decimali_di_step(step: float) -> int:
    """Decimali di uno step (0.00001 -> 5) senza errori di virgola mobile."""
    testo = f"{step:.15f}".rstrip("0")
    return len(testo.split(".")[1]) if "." in testo else 0


def arrotonda_a_step(quantita: float, step: float) -> float:
    """qty = floor(q/step)*step. Mai `int(step)`: con step 0.001 vale 0."""
    if step <= 0 or quantita <= 0:
        return 0.0
    return round(math.floor(quantita / step) * step, decimali_di_step(step))


def quantita_da_nozionale(nozionale_eur: float, prezzo: float, step: float) -> float:
    """Quantita' base target = nozionale/prezzo, arrotondata allo step dello strumento."""
    if prezzo <= 0 or nozionale_eur <= 0:
        return 0.0
    return arrotonda_a_step(nozionale_eur / prezzo, step)


def saldi_nonzero(bilancio: Dict[str, Any]) -> Dict[str, float]:
    """{valuta: totale} per le valute con totale > 0.

    `total` include i fondi impegnati in ordini aperti (free+used): l'equity
    che ignorasse gli ordini aperti e' il bug storico del criterio di drawdown.
    """
    esclusi = {"info", "timestamp", "datetime", "free", "used", "total"}
    out: Dict[str, float] = {}
    for valuta, dati in (bilancio or {}).items():
        if valuta in esclusi or not isinstance(dati, dict):
            continue
        try:
            totale = float(dati.get("total") or 0.0)
        except (TypeError, ValueError):
            continue
        if totale > 0:
            out[valuta] = totale
    return out


def calcola_equity(saldi: Dict[str, float],
                   prezzo_eur: Callable[[str], Optional[float]]
                   ) -> Tuple[float, Dict[str, Any]]:
    """Equity in EUR = valute EUR + valore di mercato degli asset detenuti.

    Un asset senza prezzo NON viene contato a zero in silenzio: finisce nel
    dettaglio con la nota, e chi chiama decide se e' un errore dati.
    """
    equity = 0.0
    dettaglio: Dict[str, Any] = {}
    for valuta, quantita in sorted(saldi.items()):
        if valuta == "EUR":
            equity += quantita
            dettaglio[valuta] = {"tipo": "EUR", "quantita": quantita,
                                 "valore_eur": quantita}
            continue
        prezzo = prezzo_eur(valuta)
        if prezzo and prezzo > 0:
            valore = quantita * prezzo
            equity += valore
            dettaglio[valuta] = {"tipo": "crypto", "quantita": quantita,
                                 "prezzo_eur": prezzo, "valore_eur": valore}
        else:
            dettaglio[valuta] = {"tipo": "crypto", "quantita": quantita,
                                 "prezzo_eur": None, "valore_eur": None,
                                 "nota": "prezzo EUR non disponibile"}
    return equity, dettaglio


def guardia_capitale(equity: float, capitale_dichiarato: float) -> Dict[str, Any]:
    """equity >= capitale dichiarato -> PASS; sotto -> NON_FINANZIATO con i tre numeri."""
    if equity >= capitale_dichiarato:
        return {"esito": "PASS", "equity_eur": equity,
                "capitale_dichiarato": capitale_dichiarato,
                "differenza": equity - capitale_dichiarato, "messaggio": ""}
    diff = capitale_dichiarato - equity
    return {"esito": "NON_FINANZIATO", "equity_eur": equity,
            "capitale_dichiarato": capitale_dichiarato, "differenza": diff,
            "messaggio": (f"NON_FINANZIATO equity_reale={equity:.4f} "
                          f"capitale_dichiarato={capitale_dichiarato:.4f} "
                          f"differenza={diff:.4f}")}


def costruisci_ordine(symbol: str, quantita: float, prezzo_rif: float, *,
                      capitale: float, frazione: float, pedaggio_pct: float,
                      tariffa_nome: str) -> Dict[str, Any]:
    """L'ordine che SAREBBE inviato: descritto, mai trasmesso."""
    return {
        "symbol": symbol,
        "side": "buy",
        "type": "market",
        "quantity": quantita,
        "prezzo_riferimento_eur": prezzo_rif,
        "nozionale_eur": round(quantita * prezzo_rif, 4),
        "nozionale_teorico_eur": round(capitale * frazione, 4),
        "pedaggio_assunto_pct": pedaggio_pct,
        "tariffa_assunta": tariffa_nome,
        "etichetta": "DRY-RUN, NON INVIATO",
    }


def formatta_metrica(*, esito: str, equity_eur: float, equity_trading: float,
                     equity_funding: float, capitale_dichiarato: float,
                     nozionale_eur: float, quantita: float, symbol: str,
                     pedaggio_pct: float, tariffa_nome: str, chiave_perm: str,
                     chiave_solo_lettura: str, ordini_aperti: int,
                     riconciliazione_quadra: str, timestamp: str) -> str:
    """Una riga per esecuzione: e' l'item che Zabbix/aggregatore possono leggere."""
    return (
        f"METRICA banco_esito={esito} equity_eur={equity_eur:.4f} "
        f"equity_trading_eur={equity_trading:.4f} "
        f"equity_funding_eur={equity_funding:.4f} "
        f"capitale_dichiarato={capitale_dichiarato:.4f} "
        f"nozionale_eur={nozionale_eur:.4f} qty={quantita} symbol={symbol} "
        f"pedaggio_assunto_pct={pedaggio_pct:.3f} tariffa={tariffa_nome} "
        f"chiave_perm={chiave_perm or 'n/d'} chiave_solo_lettura={chiave_solo_lettura} "
        f"ordini_aperti={ordini_aperti} riconciliazione_quadra={riconciliazione_quadra} "
        f"timestamp={timestamp}")


# --- percorso che parla con la sede ------------------------------------------------

def _config(percorso: str) -> Dict[str, Any]:
    import yaml  # noqa: PLC0415
    with open(percorso, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _bot_banco(cfg: Dict[str, Any]) -> Dict[str, Any]:
    for bot in cfg.get("bots") or []:
        if bot.get("strategy") == "banco_secco":
            return bot
    bots = cfg.get("bots") or []
    if bots:
        return bots[0]
    raise ValueError("config senza sezione bots: niente da leggere")


def _permessi_chiave(ex: Any) -> str:
    """Permessi della chiave ('read_only,withdraw,trade' su OKX); '' se non leggibili."""
    try:
        risposta = ex.privateGetAccountConfig()
        dati = (risposta or {}).get("data") or []
        if dati:
            return str(dati[0].get("perm") or "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def _fattibilita(capitale: float, nozionale: float, min_notional: float,
                 frazione: float) -> Dict[str, Any]:
    """Usa money.costi se importabile, altrimenti il controllo esplicito locale."""
    try:
        src = os.environ.get("MONEY_SRC", "/home/sergio/money_repo/src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from money.costi import verifica_fattibilita  # noqa: PLC0415
        fatt = verifica_fattibilita(capitale=capitale, nozionale=nozionale,
                                    min_notional=min_notional,
                                    frazione_massima=frazione)
        return {"ok": bool(fatt.ok), "motivo": fatt.motivo,
                "fonte": "money.costi", "frazione_impegnata": fatt.frazione_impegnata}
    except Exception as exc:  # noqa: BLE001
        ok = nozionale >= min_notional and nozionale > 0
        motivo = ("" if ok else
                  f"nozionale {nozionale:.4f} < min_notional {min_notional:.4f} "
                  f"oppure nullo: l'ordine non esisterebbe")
        return {"ok": ok, "motivo": motivo, "fonte": "controllo locale "
                f"(money.costi non disponibile: {exc.__class__.__name__})",
                "frazione_impegnata": nozionale / capitale if capitale else 0.0}


def _pedaggio() -> Tuple[float, str]:
    """(pct, nome): la tariffa assunta, da money.costi quando disponibile."""
    try:
        src = os.environ.get("MONEY_SRC", "/home/sergio/money_repo/src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from money.costi import get_tariffa  # noqa: PLC0415
        tariffa = get_tariffa(TARIFFA_ASSUNTA)
        return float(tariffa.giro_misto) * 100.0, TARIFFA_ASSUNTA
    except Exception:  # noqa: BLE001
        return PEDAGGIO_FALLBACK_PCT, TARIFFA_ASSUNTA


def _scrivi_output(root: str, riga_metrica: str, dati: Dict[str, Any]) -> None:
    """jsonl + file health, best-effort: il log primario e' lo stdout/journal."""
    try:
        logs = os.path.join(root, "logs")
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, "banco_secco.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(dati, ensure_ascii=False) + "\n")
    except OSError as exc:
        _log(f"ATTENZIONE: jsonl non scrivibile ({exc})")
    try:
        health = os.environ.get("BANCO_HEALTH_PATH")
        if not health:
            health = os.path.join(root, "logs", "banco_secco_health.json")
        elif not os.path.isabs(health):
            health = os.path.join(root, health)
        tmp = health + ".tmp"
        os.makedirs(os.path.dirname(health), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dati, f, ensure_ascii=False, indent=1)
        os.replace(tmp, health)
    except OSError as exc:
        _log(f"ATTENZIONE: file health non scrivibile ({exc})")


def _esegui(root: str, config_path: str) -> int:
    try:
        import ccxt  # noqa: PLC0415
    except ImportError:
        _log("ERRORE: ccxt non installato: usare il venv del progetto "
             "($PROJECT_ROOT/venv/bin/python3)")
        return 1

    try:
        cfg = _config(config_path)
        bot = _bot_banco(cfg)
    except (OSError, ValueError) as exc:
        _log(f"ERRORE: configurazione non leggibile ({exc})")
        return 1

    chiave = os.environ.get("OKX_API_KEY") or ""
    segreto = os.environ.get("OKX_API_SECRET") or ""
    passphrase = os.environ.get("OKX_PASSPHRASE") or ""
    if not (chiave and segreto and passphrase):
        _log("ERRORE: OKX_API_KEY / OKX_API_SECRET / OKX_PASSPHRASE mancanti "
             "(si caricano da config/.env_banco)")
        return 1

    eea = bool((cfg.get("exchange_rest") or {}).get("eea", True))
    hostname = os.environ.get("OKX_HOSTNAME") or (HOSTNAME_EU if eea else "www.okx.com")
    symbol = str(bot.get("symbol") or "BTC/EUR")
    capitale = float(bot.get("capital") or 0.0)
    frazione = float(bot.get("frazione_per_posizione") or 0.0)
    min_notional_cfg = float(bot.get("min_notional") or 1.0)
    # health: BANCO_HEALTH_PATH (env) vince; altrimenti la config versionata del
    # bot (relativa a PROJECT_ROOT); altrimenti logs/ di default.
    if not os.environ.get("BANCO_HEALTH_PATH") and bot.get("health_path"):
        os.environ["BANCO_HEALTH_PATH"] = str(bot["health_path"])

    ex = ccxt.okx({"apiKey": chiave, "secret": segreto, "password": passphrase,
                   "enableRateLimit": True})
    ex.options["defaultType"] = "spot"
    if hostname != "www.okx.com":
        ex.urls["api"]["rest"] = f"https://{hostname}"

    _log("BANCO money — banco di prova a secco (DRY-RUN: nessun ordine verra' inviato)")
    _log(f"  host={hostname} symbol={symbol} capitale_dichiarato={capitale:.4f} "
         f"frazione={frazione:.2%}")

    esito_metrico = "PASS"
    try:
        # 0. PERMESSI DELLA CHIAVE — la politica della chiave dedicata sola-lettura
        permessi = _permessi_chiave(ex)
        solo_lettura = bool(permessi) and "trade" not in permessi and \
            "withdraw" not in permessi
        richiesto = (os.environ.get("BANCO_RICHIEDI_READ_ONLY", "").strip().lower()
                     in ("1", "true", "si", "yes"))
        _log(f"STEP 0: permessi chiave = '{permessi or 'n/d'}'")
        if richiesto and not solo_lettura:
            _log("RIFIUTO: BANCO_RICHIEDI_READ_ONLY=1 ma la chiave non e' "
                 f"solo-lettura ('{permessi or 'n/d'}'): creare la chiave dedicata "
                 "Read (docs/02 §5.4) e sostituirla in config/.env_banco")
            return 5
        if permessi and not solo_lettura:
            _log("ATTENZIONE: chiave NON solo-lettura — il banco non ha percorsi di "
                 "invio (test statico in deploy/tests), ma la spec vuole una chiave "
                 "dedicata Read: crearla e sostituirla in config/.env_banco")

        # 1. SALDO REALE: trading E funding (il bonifico atterra sul funding)
        _log("STEP 1: fetch_balance trading + funding")
        saldi_t = saldi_nonzero(ex.fetch_balance({"type": "trading"}))
        saldi_f = saldi_nonzero(ex.fetch_balance({"type": "funding"}))
        _log(f"  trading: {json.dumps(saldi_t, ensure_ascii=False)}")
        _log(f"  funding: {json.dumps(saldi_f, ensure_ascii=False)}")

        # 2. EQUITY IN EUR (trading e funding separati, poi totale)
        _log("STEP 2: calcolo equity in EUR")
        ex.load_markets()
        mercati = ex.markets or {}
        cache: Dict[str, float] = {}

        def prezzo_eur(valuta: str) -> Optional[float]:
            coppia = f"{valuta}/EUR"
            if coppia in mercati:
                ultimo = float((ex.fetch_ticker(coppia) or {}).get("last") or 0)
                if ultimo > 0:
                    return ultimo
            coppia_u = f"{valuta}/USDT"
            if coppia_u in mercati and "USDT/EUR" in mercati:
                p1 = float((ex.fetch_ticker(coppia_u) or {}).get("last") or 0)
                if "USDT/EUR" not in cache:
                    cache["USDT/EUR"] = float(
                        (ex.fetch_ticker("USDT/EUR") or {}).get("last") or 0)
                p2 = cache["USDT/EUR"]
                if p1 > 0 and p2 > 0:
                    return p1 * p2
            return None

        equity_t, dettaglio_t = calcola_equity(saldi_t, prezzo_eur)
        equity_f, dettaglio_f = calcola_equity(saldi_f, prezzo_eur)
        equity = equity_t + equity_f
        _log(f"  equity_trading={equity_t:.4f} equity_funding={equity_f:.4f} "
             f"equity_totale={equity:.4f}")
        _log(f"  dettaglio trading: {json.dumps(dettaglio_t, ensure_ascii=False)}")
        _log(f"  dettaglio funding: {json.dumps(dettaglio_f, ensure_ascii=False)}")
        senza_prezzo = [c for c, d in list(dettaglio_t.items()) + list(dettaglio_f.items())
                        if d.get("tipo") == "crypto" and d.get("prezzo_eur") is None]
        if senza_prezzo:
            _log(f"ERRORE DATI: asset senza prezzo EUR ne' via USDT {senza_prezzo}: "
                 "l'equity non si arrotonda in silenzio, il banco si ferma")
            return 1

        # 3. GUARDIA DI CAPITALE
        _log("STEP 3: guardia di capitale")
        guardia = guardia_capitale(equity, capitale)
        if guardia["esito"] != "PASS":
            _log(f"  {guardia['messaggio']}")
            esito_metrico = guardia["esito"]
            riga = _emetti_metrica(root, esito_metrico, equity, equity_t, equity_f,
                                   capitale, 0.0, 0.0, symbol, permessi, solo_lettura,
                                   0, "n/d", saldi_t, saldi_f, None, None)
            _log(riga)
            return 2
        _log(f"  PASS: equity {equity:.4f} >= capitale_dichiarato {capitale:.4f}")

        # 4. ORDINE CHE SAREBBE INVIATO
        _log("STEP 4: calcolo ordine (dry-run)")
        mercato = mercati.get(symbol) or ex.market(symbol)
        step = float((mercato.get("precision") or {}).get("amount") or 0)
        if step <= 0:
            step = float((mercato.get("limits") or {}).get("amount", {}).get("min") or 0)
        if step <= 0:
            _log("ATTENZIONE: step non dichiarato dal mercato: si assume 0.00001")
            step = 0.00001
        min_notional_mercato = (mercato.get("limits") or {}).get("cost", {}).get("min")
        min_notional = float(min_notional_mercato) if min_notional_mercato else min_notional_cfg
        prezzo_rif = float((ex.fetch_ticker(symbol) or {}).get("last") or 0)
        nozionale_teorico = capitale * frazione
        qty = quantita_da_nozionale(nozionale_teorico, prezzo_rif, step)
        nozionale_eff = qty * prezzo_rif
        pedaggio_pct, tariffa_nome = _pedaggio()
        _log(f"  step={step} min_notional={min_notional:.4f} "
             f"prezzo_rif={prezzo_rif:.4f} nozionale_teorico={nozionale_teorico:.4f} "
             f"qty={qty} nozionale_effettivo={nozionale_eff:.4f}")
        if prezzo_rif <= 0:
            _log("ERRORE DATI: prezzo di riferimento non disponibile: "
                 "impossibile calcolare l'ordine")
            return 1
        fatt = _fattibilita(capitale, nozionale_eff, min_notional, frazione)
        _log(f"  fattibilita: ok={fatt['ok']} fonte={fatt['fonte']} "
             f"motivo={fatt['motivo'] or '-'}")
        if not fatt["ok"]:
            esito_metrico = "NON_FATTIBILE"
            riga = _emetti_metrica(root, esito_metrico, equity, equity_t, equity_f,
                                   capitale, nozionale_eff, qty, symbol, permessi,
                                   solo_lettura, 0, "n/d", saldi_t, saldi_f, fatt, None)
            _log(riga)
            return 2

        # 5. ORDINE DRY-RUN
        _log("STEP 5: ordine DRY-RUN, NON INVIATO")
        ordine = costruisci_ordine(symbol, qty, prezzo_rif, capitale=capitale,
                                   frazione=frazione, pedaggio_pct=pedaggio_pct,
                                   tariffa_nome=tariffa_nome)
        ordine["fattibilita"] = fatt["motivo"] or "ok"
        _log(f"  ORDINE: {json.dumps(ordine, ensure_ascii=False)}")

        # 6. RICONCILIAZIONE
        _log("STEP 6: riconciliazione (ordini aperti, posizioni)")
        try:
            aperti = ex.fetch_open_orders(symbol) or []
        except Exception as exc:  # noqa: BLE001
            _log(f"  ERRORE riconciliazione ordini aperti: {exc.__class__.__name__}: {exc}")
            aperti = None
        for o in aperti or []:
            _log(f"    aperto: {o.get('id')} {o.get('side')} {o.get('amount')} "
                 f"@ {o.get('price')}")
        try:
            posizioni = ex.fetch_positions([symbol])
        except Exception as exc:  # noqa: BLE001
            posizioni = None
            _log(f"  posizioni: n/d su spot ({exc.__class__.__name__})")
        if posizioni is not None:
            _log(f"  posizioni: {len(posizioni)}")
            for p in posizioni:
                _log(f"    {p.get('symbol')} contracts={p.get('contracts')} "
                     f"side={p.get('side')} unrealizedPnl={p.get('unrealizedPnl')}")
        if aperti is None:
            quadra = "errore"
        else:
            quadra = "si" if (not aperti and not posizioni) else "no"
        _log(f"  ordini_aperti={len(aperti) if aperti is not None else 'n/d'} "
             f"riconciliazione_quadra={quadra}")

        # 7. METRICA
        riga = _emetti_metrica(root, esito_metrico, equity, equity_t, equity_f,
                               capitale, nozionale_eff, qty, symbol, permessi,
                               solo_lettura,
                               len(aperti) if aperti is not None else -1,
                               quadra, saldi_t, saldi_f, fatt, ordine)
        _log(riga)
        return 0

    except ccxt.AuthenticationError as exc:
        _log(f"ERRORE AUTENTICAZIONE: {exc.__class__.__name__}: {exc}")
        return 3
    except ccxt.PermissionDenied as exc:
        _log(f"ERRORE PERMESSI (IP in whitelist?): {exc.__class__.__name__}: {exc}")
        return 4
    except ccxt.BaseError as exc:
        testo = str(exc)
        extra = ""
        if "50119" in testo:
            extra = (" (codice 50119: chiave valida solo dove e' whitelistata — "
                     "il banco gira su MARCODG1 o nuvola, non su mc2)")
        _log(f"ERRORE SEDE: {exc.__class__.__name__}: {testo}{extra}")
        return 1
    except Exception as exc:  # noqa: BLE001
        _log(f"ERRORE: {exc.__class__.__name__}: {exc}")
        if os.environ.get("BANCO_DEBUG"):
            import traceback  # noqa: PLC0415
            traceback.print_exc()
        return 1


def _emetti_metrica(root: str, esito: str, equity: float, equity_t: float,
                    equity_f: float, capitale: float, nozionale: float, qty: float,
                    symbol: str, permessi: str, solo_lettura: bool, ordini_aperti: int,
                    quadra: str, saldi_t: Dict[str, float], saldi_f: Dict[str, float],
                    fatt: Optional[Dict[str, Any]],
                    ordine: Optional[Dict[str, Any]]) -> str:
    pedaggio_pct, tariffa_nome = _pedaggio()
    ts = _ts()
    riga = formatta_metrica(
        esito=esito, equity_eur=equity, equity_trading=equity_t,
        equity_funding=equity_f, capitale_dichiarato=capitale,
        nozionale_eur=nozionale, quantita=qty, symbol=symbol,
        pedaggio_pct=pedaggio_pct, tariffa_nome=tariffa_nome,
        chiave_perm=permessi,
        chiave_solo_lettura="si" if solo_lettura else ("no" if permessi else "n/d"),
        ordini_aperti=ordini_aperti, riconciliazione_quadra=quadra, timestamp=ts)
    dati = {"nome": "banco_secco", "timestamp": ts, "esito": esito,
            "equity_eur": round(equity, 6),
            "equity_trading_eur": round(equity_t, 6),
            "equity_funding_eur": round(equity_f, 6),
            "capitale_dichiarato": capitale, "nozionale_eur": round(nozionale, 6),
            "qty": qty, "symbol": symbol, "tariffa": tariffa_nome,
            "pedaggio_assunto_pct": pedaggio_pct,
            "chiave_perm": permessi or "n/d",
            "chiave_solo_lettura": "si" if solo_lettura else ("no" if permessi else "n/d"),
            "saldi_trading": saldi_t, "saldi_funding": saldi_f,
            "ordini_aperti": ordini_aperti, "riconciliazione_quadra": quadra,
            "fattibilita": (fatt or {}).get("motivo", "") or (fatt or {}).get("ok"),
            "ordine_dry_run": ordine,
            "riga_metrica": riga}
    _scrivi_output(root, riga, dati)
    return riga


def _self_test() -> int:
    """Asserzioni sulla logica pura, senza rete: e' cio' che la CI esegue."""
    casi: list = []

    def ok(cond: bool, nome: str) -> None:
        casi.append((bool(cond), nome))

    ok(decimali_di_step(0.001) == 3, "decimali di 0.001")
    ok(decimali_di_step(0.00001) == 5, "decimali di 0.00001")
    ok(decimali_di_step(1) == 0, "decimali di 1")
    ok(arrotonda_a_step(1.23456, 0.001) == 1.234, "floor su step 0.001")
    ok(arrotonda_a_step(0.00007758, 0.00001) == 0.00007,
       "floor su step 0.00001 (il caso che con int(step) valeva 0)")
    ok(decimali_di_step(0.001) != 0, "int(step) non usato: 0.001 ha decimali")
    q = quantita_da_nozionale(6.50075, 83784.2, 0.00001)
    ok(q == 0.00007, "qty da nozionale 6.50075 EUR @ 83784.2 E/BTC, step 1e-5")
    ok(quantita_da_nozionale(6.5, 0.0, 0.001) == 0.0, "prezzo nullo -> qty 0")
    g1 = guardia_capitale(26.003, 26.003)
    ok(g1["esito"] == "PASS", "guardia con equity pari -> PASS")
    g2 = guardia_capitale(25.0, 26.003)
    ok(g2["esito"] == "NON_FINANZIATO" and "differenza=1.0030" in g2["messaggio"],
       "guardia sotto -> NON_FINANZIATO con i tre numeri")
    eq, det = calcola_equity({"EUR": 6.0, "SOL": 0.1},
                             lambda c: 200.0 if c == "SOL" else None)
    ok(abs(eq - 26.0) < 1e-9, "equity = EUR + valore asset (caso SOL)")
    ok(det["SOL"]["valore_eur"] == 20.0, "dettaglio asset valorizzato")
    eq2, det2 = calcola_equity({"FOO": 5.0}, lambda c: None)
    ok(eq2 == 0.0 and det2["FOO"]["prezzo_eur"] is None,
       "asset senza prezzo: nota nel dettaglio, mai zero silenzioso")
    o = costruisci_ordine("BTC/EUR", 0.00007, 83784.2, capitale=26.003,
                          frazione=0.25, pedaggio_pct=0.550,
                          tariffa_nome=TARIFFA_ASSUNTA)
    ok(o["etichetta"] == "DRY-RUN, NON INVIATO" and o["type"] == "market",
       "ordine dry-run etichettato")
    m = formatta_metrica(esito="PASS", equity_eur=26.003, equity_trading=0.0,
                         equity_funding=26.003, capitale_dichiarato=26.003,
                         nozionale_eur=6.5008, quantita=0.00007, symbol="BTC/EUR",
                         pedaggio_pct=0.550, tariffa_nome=TARIFFA_ASSUNTA,
                         chiave_perm="read_only", chiave_solo_lettura="si",
                         ordini_aperti=0, riconciliazione_quadra="si",
                         timestamp="2026-01-01T00:00:00Z")
    ok(m.startswith("METRICA ") and "banco_esito=PASS" in m
       and "equity_funding_eur=26.0030" in m and "riconciliazione_quadra=si" in m,
       "riga metrica con tutti i campi di §6")

    falliti = [n for okk, n in casi if not okk]
    if falliti:
        print("SELF-TEST FALLITO:")
        for n in falliti:
            print(f"  - {n}")
        return 1
    print(f"SELF-TEST OK ({len(casi)} asserzioni)")
    return 0


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Money — banco di prova a secco (legge, calcola, non invia)")
    ap.add_argument("--self-test", action="store_true",
                    help="asserzioni sulla logica pura, senza rete")
    ap.add_argument("--config", default=None,
                    help="config del banco (default: $PROJECT_ROOT/config/node_banco.yaml)")
    ap.add_argument("--project-root", default=None,
                    help="root del progetto (default: $PROJECT_ROOT o due livelli sopra)")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    root = args.project_root or os.environ.get("PROJECT_ROOT") \
        or str(Path(__file__).resolve().parents[2])
    config = args.config or os.path.join(root, "config", "node_banco.yaml")
    return _esegui(root, config)


if __name__ == "__main__":
    raise SystemExit(main())
