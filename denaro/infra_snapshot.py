#!/usr/bin/env python3
"""Genera lo snapshot che fa da cache per /infra.json.

Perche' esiste: l'aggregator deve contattare via SSH nuvola e mc2 per leggere i
conti, quindi una richiesta HTTP diretta costa qualche secondo. Questo script gira
da cron, fa il lavoro UNA volta al minuto e scrive il risultato su disco; il
handler HTTP serve il file, istantaneo.

PERCHE' E' STATO RISCRITTO (2026-09-17). Prima duplicava ~130 righe della logica
dell'aggregator e per l'elenco dei bot usava collect_node_bots() invece di
collect(): la dashboard pubblica mostrava percio' 25 bot (paper + fossili
trend-live + kraken) mentre il percorso live ne serviva 15. Due copie della stessa
logica che dicevano cose diverse. Inoltre calcolava la directory di uscita come
"accanto a questo file", che nel repo e' denaro/health e non la HEALTH_DIR
dell'aggregator: scriveva lo snapshot nel posto sbagliato.

Ora lo snapshot E' la risposta di collect(): stessa funzione, stesso risultato,
zero possibilita' di divergenza.
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

sys_path = str(Path(__file__).resolve().parent)
spec = importlib.util.spec_from_file_location("agg", sys_path + "/infra_aggregator.py")
agg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agg)

# La STESSA directory che legge l'aggregator (env HEALTH_DIR inclusa).
OUT = Path(agg.HEALTH_DIR) / "infra_snapshot.json"


def build():
    data = agg.collect()
    data["generated"] = time.time()
    tmp = str(OUT) + ".tmp"
    Path(tmp).write_text(json.dumps(data))
    Path(tmp).replace(OUT)
    _append_trend(data)
    bot = data.get("bots") or {}
    print("snapshot scritto: %s EUR, %d bot" % (data.get("total_equity"), len(bot)))


def _append_trend(data):
    """Aggiunge il punto corrente alla serie storica del grafico.

    Prima nessuno scriveva piu' trend.json (fermo al 2026-09-17): il pannello
    "TREND EQUITY (ultime 4h)" mostrava un grafico vecchio come se fosse di
    adesso. Un punto al minuto, tenuto per 48h (2880 punti); il render legge
    gli ultimi 240 (4h)."""
    try:
        p = Path(agg.HEALTH_DIR) / "trend.json"
        try:
            punti = json.loads(p.read_text())
            if not isinstance(punti, list):
                punti = []
        except Exception:
            punti = []
        punti.append({
            "ts": int(time.time()),
            "equity": round(float(data.get("total_equity") or 0.0), 2),
            "node_pnl": round(float(data.get("node_total_pnl") or 0.0), 4),
            "win_rate": data.get("node_win_rate") or 0,
        })
        tmp = str(p) + ".tmp"
        Path(tmp).write_text(json.dumps(punti[-2880:]))
        Path(tmp).replace(p)
    except Exception:
        pass


if __name__ == "__main__":
    build()
