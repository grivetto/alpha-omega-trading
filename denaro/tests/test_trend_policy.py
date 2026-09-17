#!/usr/bin/env python3
"""TrendPolicy di produzione: barre, indicatori e equivalenza col backtest.

Il test centrale e' l'equivalenza: la policy viva e il rig di ricerca devono
calcolare gli STESSI numeri sugli stessi dati. E' la differenza tra "il backtest
diceva cosi'" e "il backtest e la produzione fanno la stessa cosa".
"""
import sys
sys.path.insert(0, "/home/sergio/alpha-omega-trading")

import pytest

from denaro.domain.indicators import atr_wilder, ema_series
from denaro.domain.trend import TrendParams, TrendPolicy


def _tick(prezzi):
    """Un tick al giorno, a meta' giornata (now distinto per ogni giorno)."""
    return [(float(p), i * 86_400.0 + 3_600.0) for i, p in enumerate(prezzi)]


def _guida(pol, prezzi, **kw):
    ultimo = None
    for p, now in _tick(prezzi):
        ultimo = pol.decide(price=p, open_buys=kw.get("open_buys", {}),
                            open_sells=kw.get("open_sells", {}), cash=100.0,
                            capital_config=100.0, free_balance=100.0, now=now)
    return ultimo


def test_costruisce_una_barra_per_giorno():
    pol = TrendPolicy(TrendParams(canale=3, atr_period=3, trend_ema=0))
    prezzi = [100, 101, 102, 103, 104, 105, 106]
    _guida(pol, prezzi)
    assert len(pol.barre) == len(prezzi) - 1, (
        "attese %d barre chiuse, ottenute %d" % (len(prezzi) - 1, len(pol.barre)))


def test_barra_ha_ohlc_del_giorno():
    """Dentro lo stesso giorno piu' tick aggiornano h/l/c, non creano barre."""
    pol = TrendPolicy(TrendParams(canale=2, atr_period=2, trend_ema=0))
    giorno = 20_000 * 86_400.0
    for p in (100.0, 105.0, 95.0, 102.0):
        pol.decide(price=p, open_buys={}, open_sells={}, cash=100.0,
                   capital_config=100.0, free_balance=100.0, now=giorno + 100.0)
    assert len(pol.barre) == 0, "non deve chiudere barre lo stesso giorno"
    # il giorno dopo si chiude quella precedente
    pol.decide(price=103.0, open_buys={}, open_sells={}, cash=100.0,
               capital_config=100.0, free_balance=100.0, now=giorno + 86_400.0)
    b = list(pol.barre)[0]
    assert b["o"] == 100.0 and b["h"] == 105.0 and b["l"] == 95.0 and b["c"] == 102.0


def test_atr_identico_a_quello_del_backtest():
    """La policy e il rig di ricerca devono calcolare lo STESSO ATR."""
    prezzi = [100 + 3 * ((i % 7) - 3) + i * 0.4 for i in range(60)]
    pol = TrendPolicy(TrendParams(canale=5, atr_period=5, trend_ema=0))
    _guida(pol, prezzi)
    barre = list(pol.barre)
    atteso = atr_wilder([b["h"] for b in barre], [b["l"] for b in barre],
                        [b["c"] for b in barre], 5)[-1]
    assert pol.atr == pytest.approx(atteso), "ATR diverso tra policy e backtest"
    assert pol.atr > 0


def test_ema_identica_a_quella_del_backtest():
    prezzi = [100 + i * 0.5 for i in range(80)]
    pol = TrendPolicy(TrendParams(canale=5, atr_period=5, trend_ema=20))
    _guida(pol, prezzi)
    barre = list(pol.barre)
    atteso = ema_series([b["c"] for b in barre], 20)[-1]
    assert pol.ema == pytest.approx(atteso)


def test_segnale_breakout_rispecchia_la_condizione_del_backtest():
    """segnale = chiusura > massimo degli high delle N barre precedenti."""
    pol = TrendPolicy(TrendParams(canale=3, atr_period=3, trend_ema=0))
    # barre costruite a mano: 5 piatte poi una in forte rialzo
    prezzi = [100.0, 100.5, 100.2, 100.8, 100.4, 130.0]
    for i, c in enumerate(prezzi):
        pol.barre.append({"ts": i * 86_400.0, "o": c, "h": c, "l": c, "c": c})
    pol._aggiorna_indicatori()
    barre = list(pol.barre)
    canale = max(b["h"] for b in barre[-4:-1])
    assert pol.donchian == pytest.approx(canale), "il canale deve escludere l'ultima barra"
    assert pol.atr > 0
    assert pol.segnale_breakout() is True, "chiusura sopra il canale: breakout"

    # con una chiusura sotto il canale il segnale deve spegnersi
    pol.barre[-1] = dict(barre[-1], c=canale * 0.5)
    pol._aggiorna_indicatori()
    assert pol.segnale_breakout() is False


def test_emette_un_buy_sul_breakout():
    """Con un breakout netto la policy deve proporre un acquisto."""
    pol = TrendPolicy(TrendParams(canale=3, atr_period=3, trend_ema=0))
    prezzi = [100.0] * 8 + [100.0, 140.0, 140.0]
    d = _guida(pol, prezzi)
    assert len(pol.barre) > 3
    assert d is not None


def test_trailing_stop_sale_e_non_scende():
    pol = TrendPolicy(TrendParams(canale=3, atr_period=3, trail_mult=2.0, trend_ema=0))
    _guida(pol, [100 + 2 * i for i in range(20)])
    pol.stop = 100.0
    alto = pol.trailing_stop(200.0)
    assert alto > pol.stop, "il trailing stop doveva salire"
    pol.stop = alto
    basso = pol.trailing_stop(150.0)
    assert basso == alto, "il trailing stop non deve mai scendere"


def test_sell_target_e_lo_stop_iniziale_non_un_profit_target():
    pol = TrendPolicy(TrendParams(atr_period=3, stop_atr_mult=2.0, trend_ema=0))
    pol.atr = 5.0
    st = pol.sell_target(100.0)
    assert st == pytest.approx(90.0), "stop iniziale = entry - 2*ATR"


def test_on_fill_traccia_la_posizione():
    pol = TrendPolicy(TrendParams(atr_period=3, stop_atr_mult=2.0, trend_ema=0))
    pol.atr = 5.0
    pol.on_fill("o1", "buy", 100.0, 1.0)
    assert pol.in_posizione is True
    assert pol.entrata == 100.0
    assert pol.stop == pytest.approx(90.0)
    pol.on_fill("o2", "sell", 120.0, 1.0)
    assert pol.in_posizione is False
    assert pol.stop == 0.0


def test_non_compra_fuori_dalla_chiusura_giornaliera():
    """Solo alla chiusura di una barra si valuta il segnale."""
    pol = TrendPolicy(TrendParams(canale=3, atr_period=3, trend_ema=0))
    giorno = 20_000 * 86_400.0
    for i in range(10):
        pol.decide(price=100.0 + i, open_buys={}, open_sells={}, cash=100.0,
                   capital_config=100.0, free_balance=100.0, now=giorno + i)
    # tutti nello stesso giorno: nessuna barra chiusa, nessun ordine
    assert len(pol.barre) == 0

def test_equivalenza_del_segnale_su_dati_reali():
    """LA prova: su dati reali, la policy viva e il backtest devono coincidere.

    NB sul metodo: la policy si alimenta con QUATTRO tick al giorno (open, high,
    low, close) per riprodurre l'OHLC reale. Con un solo tick (la chiusura) la
    policy vedrebbe high = close e il confronto col backtest sarebbe tra mele e
    arance: la prima stesura di questo test produceva 44 finti disallineamenti
    per questo motivo.
    """
    import pathlib

    from denaro.research import eval as E

    f = pathlib.Path("/home/sergio/alpha-omega-trading/backtest_data/dl_BTC_1D.csv")
    if not f.exists():
        pytest.skip("dati reali non disponibili")
    candele = E.load_csv(f)
    canale, atr_n, ema_n = 20, 14, 100
    pol = TrendPolicy(TrendParams(canale=canale, atr_period=atr_n, trend_ema=ema_n))
    chiusure = [c["c"] for c in candele]
    alti = [c["h"] for c in candele]
    ema_l = ema_series(chiusure, ema_n)

    confronti = 0
    discrepanze = []
    for i in range(len(candele)):
        c = candele[i]
        for j, p in enumerate((c["o"], c["h"], c["l"], c["c"])):
            pol.decide(price=p, open_buys={}, open_sells={}, cash=100.0,
                       capital_config=100.0, free_balance=100.0,
                       now=i * 86_400.0 + j * 60.0)
        k = i - 1                       # barra chiusa dal primo tick del giorno i
        if k < max(canale, atr_n, ema_n) + 2 or pol.atr <= 0:
            continue
        atteso = (chiusure[k] > max(alti[k - canale:k]) and chiusure[k] > ema_l[k])
        avuto = pol.segnale_breakout()
        confronti += 1
        if atteso != avuto:
            discrepanze.append((k, atteso, avuto, chiusure[k], pol.donchian, pol.ema))
    assert confronti > 400, "confronti insufficienti: %d" % confronti
    assert not discrepanze, (
        "%d discrepanze su %d confronti, la prima: %r"
        % (len(discrepanze), confronti, discrepanze[0]))


def test_equivalenza_dell_atr_su_dati_reali():
    """Anche l'ATR della policy deve combaciare col backtest, barra per barra."""
    import pathlib

    from denaro.research import eval as E

    f = pathlib.Path("/home/sergio/alpha-omega-trading/backtest_data/dl_SOL_1D.csv")
    if not f.exists():
        pytest.skip("dati reali non disponibili")
    candele = E.load_csv(f)
    pol = TrendPolicy(TrendParams(canale=20, atr_period=14, trend_ema=0))
    peggiore = 0.0
    for i in range(min(len(candele), 400)):
        c = candele[i]
        for j, p in enumerate((c["o"], c["h"], c["l"], c["c"])):
            pol.decide(price=p, open_buys={}, open_sells={}, cash=100.0,
                       capital_config=100.0, free_balance=100.0,
                       now=i * 86_400.0 + j * 60.0)
        if i < 17:
            continue
        barre = list(pol.barre)
        atteso = atr_wilder([b["h"] for b in barre], [b["l"] for b in barre],
                            [b["c"] for b in barre], 14)[-1]
        peggiore = max(peggiore, abs(pol.atr - atteso))
    assert peggiore < 1e-12, "ATR divergente di %.3e" % peggiore

def test_precarica_barre_ordina_e_calcola():
    """Lo storico va accettato in qualunque ordine (OKX lo da' decrescente)."""
    pol = TrendPolicy(TrendParams(canale=3, atr_period=3, trend_ema=0))
    righe = [[(i + 1) * 86_400.0, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000.0]
             for i in range(10 - 1, -1, -1)]          # decrescente come OKX
    n = pol.precarica_barre(righe)
    assert n == 10
    ts = [b["ts"] for b in pol.barre]
    assert ts == sorted(ts), "le barre devono essere in ordine crescente"
    assert pol.atr > 0, "dopo il precaricamento l'ATR deve essere calcolato"
    barre = list(pol.barre)
    atteso = atr_wilder([b["h"] for b in barre], [b["l"] for b in barre],
                        [b["c"] for b in barre], 3)[-1]
    assert pol.atr == pytest.approx(atteso)


def test_precarica_barre_scarta_le_voci_invalide():
    pol = TrendPolicy(TrendParams(canale=2, atr_period=2, trend_ema=0))
    righe = [[86400.0, 100, 101, 99, 100, 10],
             ["x", 1, 2, 3, 4, 5],
             [172800.0, 0, 0, 0, 0, 0],
             [259200.0, 100, 99, 101, 100, 10],     # high < low
             [345600.0, 100, 101, 99, 100, 10]]
    n = pol.precarica_barre(righe)
    assert n == 2, "attese 2 barre valide, accettate %d" % n


def test_precarica_barre_lista_vuota():
    pol = TrendPolicy()
    assert pol.precarica_barre([]) == 0
    assert pol.precarica_barre(None) == 0


def test_precarica_barre_abilita_il_segnale_su_dati_reali():
    """Dopo il seeding la policy deve poter valutare il breakout come il backtest."""
    import pathlib

    from denaro.research import eval as E

    f = pathlib.Path("/home/sergio/alpha-omega-trading/backtest_data/dl_BTC_1D.csv")
    if not f.exists():
        pytest.skip("dati reali non disponibili")
    candele = E.load_csv(f)
    canale, atr_n, ema_n = 40, 14, 100
    righe = [[c["ts"] / 1000.0 if c["ts"] > 1e11 else c["ts"], c["o"], c["h"],
              c["l"], c["c"], c["v"]] for c in candele]
    righe.reverse()                                   # come le da' OKX
    pol = TrendPolicy(TrendParams(canale=canale, atr_period=atr_n, trend_ema=ema_n))
    n = pol.precarica_barre(righe)
    assert n == len(candele)
    assert pol.atr > 0 and pol.ema > 0 and pol.donchian > 0
    # la condizione deve coincidere con quella calcolata dal rig di ricerca
    chiusure = [c["c"] for c in candele]
    alti = [c["h"] for c in candele]
    ema_l = ema_series(chiusure, ema_n)
    atteso = (chiusure[-1] > max(alti[-1 - canale:-1]) and chiusure[-1] > ema_l[-1])
    assert pol.segnale_breakout() == atteso

def test_precarica_esclude_la_giornata_in_corso():
    """La barra di OGGI e' incompleta e non deve entrare nella storia.

    Difetto trovato il 2026-09-17 ragionando sul percorso LIVE: OKX restituisce
    come prima riga la barra di oggi, ancora incompleta. Il Node la passava a
    precarica_barre, che la accettava; al primo cambio di giornata la policy
    appendeva la barra di oggi costruita dai tick, e la stessa giornata finiva
    DUE volte nel canale e nell'ATR, facendo divergere la policy viva dal
    backtest. Il test di equivalenza non lo vedeva perche' alimentava le barre
    direttamente, senza passare dal precaricamento del Node.
    """
    pol = TrendPolicy(TrendParams(canale=2, atr_period=2, trend_ema=0))
    righe = [[(i + 1) * 86_400.0, 100.0, 101.0, 99.0, 100.0, 1000.0] for i in range(3)]
    righe.insert(0, [4 * 86_400.0, 100.0, 105.0, 99.0, 104.0, 1000.0])
    n = pol.precarica_barre(righe, now=4 * 86_400.0 + 3600.0)
    assert n == 3, "la barra di oggi doveva essere scartata: accettate %d" % n
    assert 4.0 not in [b["ts"] / 86_400.0 for b in pol.barre]

    # il bot parte oggi, domani cambia giornata: nessun duplicato
    pol.decide(price=104.5, open_buys={}, open_sells={}, cash=100.0,
               capital_config=100.0, free_balance=100.0, now=4 * 86_400.0 + 3600.0)
    pol.decide(price=105.0, open_buys={}, open_sells={}, cash=100.0,
               capital_config=100.0, free_balance=100.0, now=5 * 86_400.0 + 3600.0)
    giorni = [b["ts"] / 86_400.0 for b in pol.barre]
    assert len(giorni) == len(set(giorni)), "giornate duplicate: %s" % giorni


def test_precarica_deduplica_per_giornata():
    """Anche senza now, due barre dello stesso giorno non devono coesistere."""
    pol = TrendPolicy(TrendParams(canale=2, atr_period=2, trend_ema=0))
    righe = [[86_400.0, 100.0, 101.0, 99.0, 100.0, 1.0],
             [86_400.0 + 3600.0, 100.0, 102.0, 99.0, 101.0, 1.0],
             [2 * 86_400.0, 101.0, 103.0, 100.0, 102.0, 1.0]]
    pol.precarica_barre(righe)
    giorni = [b["ts"] / 86_400.0 for b in pol.barre]
    assert len(giorni) == len(set(giorni)), "giornate duplicate: %s" % giorni
    assert len(pol.barre) == 2, "attese 2 giornate, trovate %d" % len(pol.barre)

def test_riavvio_non_abbassa_lo_stop_esistente():
    """Alla ripartenza lo stop gia' in essere e' un PAVIMENTO.

    Difetto trovato il 2026-09-17 con l'audit del percorso live: la policy nuova
    ha self.stop = 0, quindi il trailing ripartiva dal prezzo corrente e
    ABBASSAVA la protezione (da 96.00 a 92.00, -4.17%) cancellando attivamente
    lo stop buono. Succede a ogni deploy, riavvio o crash con posizione aperta.
    """
    pol = TrendPolicy(TrendParams(canale=5, atr_period=3, trail_mult=3.0,
                                  stop_atr_mult=2.0, trend_ema=0, risk_pct=0.02))
    pol.atr = 2.0
    assert pol.stop == 0.0 and pol.in_posizione is False   # policy appena nata
    # posizione aperta da prima del riavvio: comprata a 100, stop a 96
    open_sells = {"s1": {"amount": 1.0, "price": 96.0, "target_price": 96.0}}
    d = pol.decide(price=98.0, open_buys={}, open_sells=dict(open_sells),
                   cash=0.0, capital_config=24.9, free_balance=0.0,
                   now=5 * 86_400.0)
    assert d.to_sell == [], "non doveva riposizionare lo stop: %s" % (d.to_sell,)
    assert d.to_cancel_sell == []
    assert pol.stop >= 96.0, "lo stop non deve scendere sotto 96: %.4f" % pol.stop

    # e se il prezzo SALE, il trailing deve alzarlo normalmente
    d2 = pol.decide(price=110.0, open_buys={}, open_sells=dict(open_sells),
                    cash=0.0, capital_config=24.9, free_balance=0.0,
                    now=5 * 86_400.0 + 60)
    assert pol.stop > 96.0, "il trailing doveva salire: %.4f" % pol.stop
    assert d2.to_sell and d2.to_sell[0][1] == pol.stop
